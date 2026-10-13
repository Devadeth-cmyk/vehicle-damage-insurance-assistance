"""
Claim Package Service

Production backend orchestration for the vehicle-damage insurance system.

Pipeline:

Evidence
    ↓
Damage Detection
    ↓
Vehicle-Part Detection
    ↓
Damage ↔ Part Fusion
    ↓
Severity
    ↓
Technician Verification
    ↓
Claim/Evidence Consistency
    ↓
Repair Estimation
    ↓
Annotated Evidence
    ↓
claim_package.json
    ↓
claim_pdf_v2.py
    ↓
PACKAGE_MANIFEST.json
    ↓
ZIP
    ↓
Validation
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
from PIL import Image as PILImage

# ------------------------------------------------------------------
# Existing project services
# ------------------------------------------------------------------

from app.ai.damage_detector import detect_damage
from app.ai.parts_detector import detect_parts
from app.ai.fusion_service import fuse_damage_to_parts

from app.services.repair_estimation import (
    build_repair_estimate,
)

# External PDF generator
from app.claim_package.claim_pdf_v2 import (
    build_claim_pdf,
    compute_submission_status,
)


# ================================================================
# CONFIGURATION
# ================================================================

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
}

MIN_SHORT_SIDE_PX = 640
MIN_SHARPNESS = 60.0


# ================================================================
# GENERAL UTILITIES
# ================================================================

def utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def sha256_file(path: Path) -> str:
    """Calculate SHA-256 hash of a file."""

    digest = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def safe_mkdir(path: Path) -> Path:
    """Create directory if necessary."""

    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


# ================================================================
# EVIDENCE DISCOVERY
# ================================================================

def list_images(
    input_dir: Path,
) -> list[Path]:
    """Return all supported images recursively."""

    if not input_dir.exists():
        return []

    return sorted(
        p
        for p in input_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTENSIONS
    )


# ================================================================
# IMAGE QUALITY
# ================================================================

def photo_quality_report(
    path: Path,
) -> dict[str, Any]:
    """
    Generate informational evidence-quality metadata.

    These checks are NOT authenticity/fraud checks.
    """

    record: dict[str, Any] = {
        "file": path.name,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "flags": [],
    }

    try:

        with PILImage.open(path) as image:

            record["width"] = image.width
            record["height"] = image.height

            exif = image.getexif()

            record["exif_datetime"] = (
                str(exif.get(306) or "")
                or None
            )

            record["camera"] = (
                " ".join(
                    str(
                        exif.get(key, "")
                    )
                    for key in (271, 272)
                ).strip()
                or None
            )

            try:
                record["has_gps"] = bool(
                    exif.get_ifd(0x8825)
                )
            except Exception:
                record["has_gps"] = False

    except Exception as exc:

        record.update(
            {
                "width": None,
                "height": None,
                "exif_datetime": None,
                "camera": None,
                "has_gps": False,
            }
        )

        record["flags"].append(
            f"unreadable_by_pil:{exc}"
        )

        return record

    gray = cv2.imread(
        str(path),
        cv2.IMREAD_GRAYSCALE,
    )

    if gray is None:

        record["flags"].append(
            "unreadable_by_opencv"
        )

        return record

    # Resize large images before sharpness calculation.
    scale = 800 / max(gray.shape)

    if scale < 1:
        gray = cv2.resize(
            gray,
            None,
            fx=scale,
            fy=scale,
        )

    sharpness = float(
        cv2.Laplacian(
            gray,
            cv2.CV_64F,
        ).var()
    )

    record["sharpness"] = round(
        sharpness,
        1,
    )

    if min(
        record["width"],
        record["height"],
    ) < MIN_SHORT_SIDE_PX:

        record["flags"].append(
            "low_resolution"
        )

    if sharpness < MIN_SHARPNESS:

        record["flags"].append(
            "possibly_blurry"
        )

    if not record["exif_datetime"]:

        record["flags"].append(
            "no_exif_timestamp"
        )

    return record


# ================================================================
# EVIDENCE VALIDATION
# ================================================================

def inspect_evidence(
    input_dir: Path,
) -> tuple[
    list[Path],
    list[dict[str, Any]],
]:
    """
    Discover photographs and create quality/integrity records.
    """

    image_paths = list_images(
        input_dir
    )

    if not image_paths:

        raise ValueError(
            f"No supported images found in: {input_dir}"
        )

    # Prevent ambiguous package filenames.
    stems = [
        p.stem
        for p in image_paths
    ]

    duplicates = sorted(
        {
            stem
            for stem in stems
            if stems.count(stem) > 1
        }
    )

    if duplicates:

        raise ValueError(
            "Duplicate image stems detected: "
            f"{duplicates}. Rename the files."
        )

    quality = [
        photo_quality_report(path)
        for path in image_paths
    ]

    # Exact duplicate detection.
    for i in range(
        len(quality)
    ):

        for j in range(i):

            if (
                quality[i]["sha256"]
                == quality[j]["sha256"]
            ):

                quality[i]["flags"].append(
                    "possible_duplicate_of:"
                    + quality[j]["file"]
                )

    return (
        image_paths,
        quality,
    )


# ================================================================
# TECHNICIAN VERIFICATION
# ================================================================

def is_rejected(
    finding: dict[str, Any],
) -> bool:

    return (
        finding.get(
            "verification_status"
        )
        == "TECHNICIAN_REJECTED"
    )


def is_verified(
    finding: dict[str, Any],
) -> bool:

    return (
        finding.get(
            "verification_status"
        )
        == "TECHNICIAN_VERIFIED"
    )


def apply_technician_verification(
    analysis: dict[str, Any],
    overrides: dict[str, dict[str, Any]] | None,
    technician_name: str,
) -> dict[str, Any]:
    """
    Apply technician corrections to AI findings.

    Override format:

    {
        "image1_D1": {
            "verified": True,
            "part": "front_bumper",
            "damage_type": "dent",
            "severity": "Moderate",
            "review_note": "Confirmed",
            "verified_by": "Technician"
        }
    }
    """

    overrides = overrides or {}

    timestamp = utc_now_iso()

    matched_keys: set[str] = set()

    for image_result in analysis.get(
        "images",
        [],
    ):

        image_name = image_result.get(
            "image",
            ""
        )

        stem = Path(
            image_name
        ).stem

        for finding in safe_get_detections(image_result):

            damage_id = finding.get(
                "damage_id"
            )

            detection_id = (
                f"{stem}_D{damage_id}"
            )

            finding[
                "detection_id"
            ] = detection_id

            override = overrides.get(
                detection_id
            )

            if override is None:
                continue

            matched_keys.add(
                detection_id
            )

            # Preserve original AI result.
            finding[
                "ai_original"
            ] = {
                "part": finding.get(
                    "part"
                ),
                "damage_type": finding.get(
                    "damage_type"
                ),
                "severity": finding.get(
                    "severity"
                ),
            }

            verified = bool(
                override.get(
                    "verified",
                    True,
                )
            )

            finding[
                "verified"
            ] = verified

            finding[
                "verification_status"
            ] = (
                "TECHNICIAN_VERIFIED"
                if verified
                else "TECHNICIAN_REJECTED"
            )

            if "part" in override:

                finding[
                    "part"
                ] = override["part"]

            if "damage_type" in override:

                finding[
                    "damage_type"
                ] = override[
                    "damage_type"
                ]

            if "severity" in override:

                finding[
                    "severity"
                ] = override[
                    "severity"
                ]

            if "review_note" in override:

                finding[
                    "technician_note"
                ] = override[
                    "review_note"
                ]

            finding[
                "technician_override"
            ] = True

            finding[
                "verified_by"
            ] = override.get(
                "verified_by",
                technician_name,
            )

            finding[
                "verified_at_utc"
            ] = timestamp

    # Keep unmatched overrides visible.
    unmatched = sorted(
        set(overrides)
        - matched_keys
    )

    if unmatched:

        analysis[
            "technician_override_warnings"
        ] = [
            f"Override does not match a detection: {key}"
            for key in unmatched
        ]

    return analysis


# ================================================================
# FINDING HELPERS
# ================================================================

def safe_get_detections(image_result: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(image_result, dict):
        return []
    dets = image_result.get("detections", [])
    if isinstance(dets, dict):
        dets = dets.get("fused_items", []) or dets.get("detections", []) or dets.get("images", [])
    if not isinstance(dets, list):
        return []
    return [d for d in dets if isinstance(d, dict)]


def all_detections(
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for image in analysis.get("images", []):
        results.extend(safe_get_detections(image))
    return results


def active_detections(
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:

    return [
        detection
        for detection in all_detections(
            analysis
        )
        if not is_rejected(
            detection
        )
    ]


def assign_finding_references(
    analysis: dict[str, Any],
) -> None:
    counter = 1

    for image in analysis.get(
        "images",
        [],
    ):
        for finding in safe_get_detections(image):
            finding["ref"] = f"F{counter:02d}"
            counter += 1


# ================================================================
# CLAIM/EVIDENCE CONSISTENCY
# ================================================================

def normalize_text(
    text: str,
) -> str:

    return (
        str(text)
        .lower()
        .strip()
    )


def consistency_check(
    accident_description: str,
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Lightweight deterministic consistency check.

    This is intentionally a REVIEW FLAG.

    It does not make fraud or claim decisions.
    """

    narrative = normalize_text(
        accident_description
    )

    if len(narrative) < 25:

        return {
            "status": "NOT_ASSESSED",
            "mentioned_and_detected": [],
            "detected_but_not_explicitly_reported": [],
            "claimed_but_not_detected": [],
            "note": (
                "Accident description is empty "
                "or too short for meaningful "
                "comparison."
            ),
        }

    if not findings:

        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "mentioned_and_detected": [],
            "detected_but_not_explicitly_reported": [],
            "claimed_but_not_detected": [],
            "note": (
                "No active AI findings are available."
            ),
        }

    mentioned = []
    not_reported = []

    for finding in findings:

        part = str(
            finding.get(
                "part",
                "",
            )
        ).replace(
            "_",
            " ",
        )

        damage = str(
            finding.get(
                "damage_type",
                "",
            )
        ).replace(
            "_",
            " ",
        )

        part_present = (
            part
            and part in narrative
        )

        damage_present = (
            damage
            and damage in narrative
        )

        record = {
            "part": part,
            "damage_type": damage,
            "refs": [
                finding.get("ref")
            ],
        }

        if part_present and damage_present:

            mentioned.append(
                record
            )

        else:

            record["reason"] = (
                "part_not_mentioned"
                if not part_present
                else "damage_type_not_mentioned"
            )

            not_reported.append(
                record
            )

    status = (
        "POTENTIAL_MISMATCH"
        if not_reported
        else "CONSISTENT"
    )

    return {
        "status": status,
        "mentioned_and_detected": mentioned,
        "detected_but_not_explicitly_reported": not_reported,
        "claimed_but_not_detected": [],
        "note": (
            "Review flag only. This is a deterministic "
            "text comparison and is not a fraud "
            "determination or claim decision."
        ),
    }


# ================================================================
# CLAIM SUMMARY
# ================================================================

def build_claim_summary(
    analysis: dict[str, Any],
) -> dict[str, Any]:

    all_findings = all_detections(
        analysis
    )

    active = active_detections(
        analysis
    )

    severity_counts: dict[
        str,
        int,
    ] = {}

    for finding in active:

        severity = finding.get(
            "severity"
        )

        if severity:

            severity_counts[
                severity
            ] = (
                severity_counts.get(
                    severity,
                    0,
                )
                + 1
            )

    estimate = analysis.get(
        "repair_estimate",
        {},
    )

    return {
        "total_images": len(
            analysis.get(
                "images",
                [],
            )
        ),

        "total_findings_by_ai": len(
            all_findings
        ),

        "rejected_by_technician": sum(
            is_rejected(f)
            for f in all_findings
        ),

        "active_findings": len(
            active
        ),

        "affected_parts": sorted(
            {
                f.get(
                    "part"
                )
                for f in active
                if f.get("part")
            }
        ),

        "severity_counts": severity_counts,

        "technician_verified_count": sum(
            is_verified(f)
            for f in active
        ),

        "unverified_count": sum(
            not is_verified(f)
            for f in active
        ),

        "pending_review_count": sum(
            bool(
                f.get(
                    "requires_review"
                )
            )
            and not is_verified(f)
            and not is_rejected(f)
            for f in active
        ),

        "claim_consistency": analysis.get(
            "consistency_check",
            {},
        ).get(
            "status",
            "INSUFFICIENT_EVIDENCE",
        ),

        "ai_indicative_estimate_inr": estimate.get(
            "ai_preliminary_total",
            0.0,
        ),

        "workshop_estimate_inr": estimate.get(
            "workshop_total",
            0.0,
        ),

        "estimate_review_required": estimate.get(
            "review_required",
            True,
        ),
    }


# ================================================================
# SUPPORTING DOCUMENTS
# ================================================================

def inspect_supporting_documents(
    documents_dir: Path,
) -> dict[str, Any]:

    if not documents_dir.exists():

        return {
            "files": [],
            "file_details": [],
            "note": (
                "No supporting documents directory found."
            ),
        }

    files = sorted(
        p
        for p in documents_dir.rglob("*")
        if p.is_file()
    )

    details = []

    for file in files:

        details.append(
            {
                "file": file.name,
                "size_bytes": file.stat().st_size,
                "sha256": sha256_file(
                    file
                ),
            }
        )

    return {
        "files": [
            item["file"]
            for item in details
        ],
        "file_details": details,
        "note": (
            "Document presence and hashes are "
            "recorded. This service does not "
            "determine whether documents satisfy "
            "insurer-specific requirements."
        ),
    }


# ================================================================
# ANNOTATED EVIDENCE
# ================================================================

def create_annotated_evidence(
    original_path: Path,
    image_result: dict[str, Any],
    output_path: Path,
) -> str:
    """
    Create an annotated copy.

    Original photograph is never modified.
    """

    image = cv2.imread(
        str(original_path)
    )

    if image is None:

        raise ValueError(
            f"Unable to read image: {original_path}"
        )

    height, width = image.shape[:2]

    for finding in image_result.get(
        "detections",
        [],
    ):

        if is_rejected(finding):
            continue

        bbox = finding.get(
            "bbox"
        )

        if not bbox:
            continue

        x1, y1, x2, y2 = [
            int(round(v))
            for v in bbox
        ]

        x1 = max(
            0,
            min(width - 1, x1),
        )

        y1 = max(
            0,
            min(height - 1, y1),
        )

        x2 = max(
            0,
            min(width - 1, x2),
        )

        y2 = max(
            0,
            min(height - 1, y2),
        )

        severity = finding.get(
            "severity",
            "Unknown",
        )

        # OpenCV BGR.
        severity_colors = {
            "Minor": (50, 160, 40),
            "Moderate": (0, 140, 255),
            "Severe": (40, 40, 210),
        }

        color = severity_colors.get(
            severity,
            (150, 150, 150),
        )

        needs_review = (
            finding.get(
                "requires_review",
                False,
            )
            and not is_verified(
                finding
            )
        )

        if needs_review:

            # Dashed-style approximation.
            cv2.rectangle(
                image,
                (x1, y1),
                (x2, y2),
                color,
                2,
            )

        else:

            cv2.rectangle(
                image,
                (x1, y1),
                (x2, y2),
                color,
                3,
            )

        label = (
            f"{finding.get('ref', '')} "
            f"{finding.get('part', 'unknown')} | "
            f"{finding.get('damage_type', '')} | "
            f"{severity}"
        )

        cv2.putText(
            image,
            label,
            (
                x1,
                max(20, y1 - 8),
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    safe_mkdir(
        output_path.parent
    )

    cv2.imwrite(
        str(output_path),
        image,
        [
            cv2.IMWRITE_JPEG_QUALITY,
            92,
        ],
    )

    return str(
        output_path
    )


# ================================================================
# PACKAGE FOLDER
# ================================================================

def build_package_directories(
    package_dir: Path,
) -> dict[str, Path]:

    if package_dir.exists():

        shutil.rmtree(
            package_dir
        )

    original_dir = safe_mkdir(
        package_dir
        / "original_evidence"
    )

    annotated_dir = safe_mkdir(
        package_dir
        / "annotated_evidence"
    )

    supporting_dir = safe_mkdir(
        package_dir
        / "supporting_documents"
    )

    return {
        "package": package_dir,
        "original": original_dir,
        "annotated": annotated_dir,
        "supporting": supporting_dir,
    }


# ================================================================
# COPY EVIDENCE
# ================================================================

def copy_evidence(
    image_paths: list[Path],
    image_results: list[dict[str, Any]],
    directories: dict[str, Path],
) -> None:

    original_dir = directories[
        "original"
    ]

    annotated_dir = directories[
        "annotated"
    ]

    for image_path, image_result in zip(
        image_paths,
        image_results,
    ):

        # Original evidence.
        shutil.copy2(
            image_path,
            original_dir
            / image_path.name,
        )

        # Annotated evidence.
        create_annotated_evidence(
            image_path,
            image_result,
            annotated_dir
            / f"{image_path.stem}_annotated.jpg",
        )


# ================================================================
# COPY SUPPORTING DOCUMENTS
# ================================================================

def copy_supporting_documents(
    source_dir: Path,
    destination_dir: Path,
) -> None:

    if not source_dir.exists():
        return

    files = [
        p
        for p in source_dir.rglob("*")
        if p.is_file()
    ]

    names = [
        p.name
        for p in files
    ]

    if len(names) != len(
        set(names)
    ):

        raise ValueError(
            "Supporting documents contain duplicate "
            "file names. Rename them before packaging."
        )

    for source in files:

        destination = (
            destination_dir
            / source.name
        )

        shutil.copy2(
            source,
            destination,
        )


# ================================================================
# BUILD CLAIM JSON
# ================================================================

def build_claim_package_json(
    *,
    claim_id: str,
    claim_info: dict[str, Any],
    analysis: dict[str, Any],
    quality: list[dict[str, Any]],
    model_metadata: dict[str, Any],
) -> dict[str, Any]:

    summary = analysis[
        "claim_summary"
    ]

    package = {

        "package_type":
            "DIGITAL_VEHICLE_INSURANCE_CLAIM_PACKAGE",

        "package_version":
            "2.0",

        "claim_id":
            claim_id,

        "generated_at_utc":
            utc_now_iso(),

        "submission_status":
            None,

        "open_items":
            [],

        "customer": {
            key: claim_info.get(
                key,
                "",
            )
            for key in (
                "customer_name",
                "contact_number",
                "email",
            )
        },

        "vehicle": {
            key: claim_info.get(
                key,
                "",
            )
            for key in (
                "vehicle_registration",
                "make",
                "model",
                "variant",
                "vin",
                "policy_number",
                "insurance_company",
            )
        },

        "accident": {
            key: claim_info.get(
                key,
                "",
            )
            for key in (
                "accident_date",
                "accident_time",
                "accident_location",
                "accident_description",
            )
        },

        "workshop": {
            key: claim_info.get(
                key,
                "",
            )
            for key in (
                "workshop_name",
                "technician_name",
            )
        },

        "ai_assessment": {

            "damage_model_version":
                model_metadata.get(
                    "damage_model_version"
                ),

            "parts_model_version":
                model_metadata.get(
                    "parts_model_version"
                ),

            "severity_version":
                model_metadata.get(
                    "severity_version"
                ),

            "model_file_sha256":
                model_metadata.get(
                    "model_file_sha256",
                    {},
                ),

            "config":
                model_metadata.get(
                    "config",
                    {},
                ),

            "analysis_timestamp_utc":
                analysis.get(
                    "analysis_timestamp_utc"
                ),

            "images":
                analysis.get(
                    "images",
                    [],
                ),

            "summary":
                summary,
        },

        "technician_verification": {

            "completed": (
                bool(
                    summary[
                        "active_findings"
                    ]
                )
                and summary[
                    "unverified_count"
                ] == 0
            ),

            "verified_count":
                summary[
                    "technician_verified_count"
                ],

            "rejected_count":
                summary[
                    "rejected_by_technician"
                ],

            "unverified_count":
                summary[
                    "unverified_count"
                ],

            "overrides":
                analysis.get(
                    "technician_overrides",
                    {},
                ),

            "note":
                (
                    "AI results must be reviewed "
                    "by a technician before insurer "
                    "submission."
                ),
        },

        "evidence_consistency":
            analysis.get(
                "consistency_check",
                {},
            ),

        "repair_estimate":
            analysis.get(
                "repair_estimate",
                {},
            ),

        "document_status":
            analysis.get(
                "document_status",
                {},
            ),

        "evidence": {

            "original_evidence_folder":
                "original_evidence/",

            "annotated_evidence_folder":
                "annotated_evidence/",

            "supporting_documents_folder":
                "supporting_documents/",

            "quality":
                quality,
        },

        "human_review": {

            "required": (
                summary[
                    "pending_review_count"
                ] > 0
                or summary[
                    "unverified_count"
                ] > 0
            ),

            "note":
                (
                    "AI confidence scores are "
                    "evidence-quality indicators, "
                    "not claim probabilities."
                ),
        },

        "disclaimer": (
            "This package contains AI-assisted "
            "evidence organisation and damage "
            "assessment. The workshop/technician "
            "verifies the assessment and the "
            "insurer/surveyor makes the final "
            "claim decision."
        ),
    }

    return package


# ================================================================
# MANIFEST
# ================================================================

def create_manifest(
    package_dir: Path,
    claim_id: str,
    submission_status: str,
) -> dict[str, Any]:

    files = []

    for path in sorted(
        package_dir.rglob("*")
    ):

        if (
            not path.is_file()
            or path.name
            == "PACKAGE_MANIFEST.json"
        ):
            continue

        relative = (
            path
            .relative_to(package_dir)
            .as_posix()
        )

        top_level = relative.split(
            "/",
            1,
        )[0]

        roles = {
            "original_evidence":
                "original_photograph",

            "annotated_evidence":
                "ai_annotated_copy",

            "supporting_documents":
                "supporting_document",

            "claim_package.json":
                "structured_claim_data",

            "claim_report.pdf":
                "human_readable_report",
        }

        role = roles.get(
            top_level,
            "other",
        )

        files.append(
            {
                "path": relative,
                "role": role,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(
                    path
                ),
            }
        )

    return {

        "package_type":
            "DIGITAL_VEHICLE_INSURANCE_CLAIM_PACKAGE_MANIFEST",

        "claim_id":
            claim_id,

        "generated_at_utc":
            utc_now_iso(),

        "submission_status":
            submission_status,

        "hash_algorithm":
            "SHA-256",

        "file_count":
            len(files),

        "files":
            files,
    }


# ================================================================
# ZIP CREATION
# ================================================================

def create_zip_package(
    package_dir: Path,
    zip_path: Path,
) -> Path:

    safe_mkdir(
        zip_path.parent
    )

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as archive:

        for path in sorted(
            package_dir.rglob("*")
        ):

            if not path.is_file():
                continue

            archive.write(
                path,
                path.relative_to(
                    package_dir
                ).as_posix(),
            )

    return zip_path


# ================================================================
# PACKAGE VALIDATION
# ================================================================

def validate_package(
    zip_path: Path,
    claim_id: str,
) -> dict[str, Any]:

    checks = []

    def add_check(
        name: str,
        passed: bool,
        detail: str = "",
    ):

        checks.append(
            {
                "check": name,
                "result": (
                    "PASS"
                    if passed
                    else "FAIL"
                ),
                "detail": detail,
            }
        )

    with zipfile.ZipFile(
        zip_path,
        "r",
    ) as archive:

        add_check(
            "ZIP integrity",
            archive.testzip() is None,
        )

        names = set(
            archive.namelist()
        )

        for required in (
            "claim_package.json",
            "claim_report.pdf",
            "PACKAGE_MANIFEST.json",
        ):

            add_check(
                f"contains {required}",
                required in names,
            )

        if (
            "PACKAGE_MANIFEST.json"
            in names
        ):

            manifest = json.loads(
                archive.read(
                    "PACKAGE_MANIFEST.json"
                )
            )

            bad_hashes = []

            for item in manifest.get(
                "files",
                [],
            ):

                path = item[
                    "path"
                ]

                if path not in names:

                    bad_hashes.append(
                        path
                    )

                    continue

                actual_hash = hashlib.sha256(
                    archive.read(path)
                ).hexdigest()

                if (
                    actual_hash
                    != item["sha256"]
                ):

                    bad_hashes.append(
                        path
                    )

            add_check(
                "manifest hashes",
                not bad_hashes,
                ", ".join(
                    bad_hashes
                ),
            )

        if (
            "claim_package.json"
            in names
        ):

            package = json.loads(
                archive.read(
                    "claim_package.json"
                )
            )

            add_check(
                "claim_id matches",
                package.get(
                    "claim_id"
                )
                == claim_id,
            )

            required_sections = {
                "customer",
                "vehicle",
                "accident",
                "ai_assessment",
                "technician_verification",
                "evidence_consistency",
                "repair_estimate",
                "document_status",
                "evidence",
                "disclaimer",
            }

            missing = sorted(
                required_sections
                - set(package.keys())
            )

            add_check(
                "JSON required sections",
                not missing,
                ", ".join(missing),
            )

        if (
            "claim_report.pdf"
            in names
        ):

            pdf = archive.read(
                "claim_report.pdf"
            )

            add_check(
                "PDF validity",
                pdf[:5] == b"%PDF-"
                and len(pdf) > 5000,
                f"{len(pdf) / 1024:.0f} KB",
            )

    passed = all(
        check["result"]
        == "PASS"
        for check in checks
    )

    return {
        "valid": passed,
        "checks": checks,
    }


def compute_submission_status(
    package: dict[str, Any],
) -> tuple[str, str, list[str]]:
    """
    Compute submission status code, human-readable status text, and open action items.
    Returns: (status_code, status_text, open_items)
    """
    open_items = []

    tech_verif = package.get("technician_verification", {})
    if not tech_verif.get("completed", False):
        open_items.append("Technician verification is incomplete.")

    human_rev = package.get("human_review", {})
    if human_rev.get("required", False):
        open_items.append("Human-in-the-loop technician review is required.")

    repair_est = package.get("repair_estimate", {})
    if not repair_est.get("ai_preliminary_items") and not repair_est.get("workshop_items"):
        open_items.append("No preliminary repair line items compiled.")

    if not open_items:
        status_code = "READY_FOR_INSURER_SUBMISSION"
        status_text = "Claim package compiled and verified, ready for insurer submission."
    elif tech_verif.get("completed", False):
        status_code = "VERIFIED_WITH_OPEN_ITEMS"
        status_text = "Technician verified, minor open items remain."
    else:
        status_code = "ACTION_REQUIRED"
        status_text = "Technician review or evidence updates required before submission."

    return status_code, status_text, open_items


# ================================================================
# MAIN SERVICE
# ================================================================

def generate_claim_package(
    *,
    claim_id: str,
    claim_info: dict[str, Any],
    existing_assessment: dict[str, Any],
    evidence_dir: str | Path,
    supporting_documents_dir: str | Path,
    output_dir: str | Path,
    workshop_items: list[dict[str, Any]] | None = None,
    technician_overrides: dict[str, dict[str, Any]] | None = None,
    model_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Main entry point used by the FastAPI assessment endpoint.

    Returns:

    {
        "claim_id": "...",
        "status": "...",
        "json_path": "...",
        "pdf_path": "...",
        "zip_path": "...",
        "validation": {...},
        "package": {...}
    }
    """

    evidence_dir = Path(
        evidence_dir
    )

    supporting_documents_dir = Path(
        supporting_documents_dir
    )

    output_dir = Path(
        output_dir
    )

    package_dir = (
        output_dir
        / claim_id
    )

    zip_path = (
        output_dir
        / f"{claim_id}_digital_claim_package.zip"
    )

    # ------------------------------------------------------------
    # 1. Evidence
    # ------------------------------------------------------------

    image_paths, quality = inspect_evidence(
        evidence_dir
    )

    # ------------------------------------------------------------
    # 2. AI analysis
    # ------------------------------------------------------------

    image_results = []

    for image_path in image_paths:

        image = cv2.imread(
            str(image_path)
        )

        if image is None:

            image_results.append(
                {
                    "image":
                        image_path.name,

                    "status":
                        "INVALID_IMAGE",

                    "detections":
                        [],
                }
            )

            continue

        height, width = image.shape[:2]

        try:

            damages = detect_damage(
                str(image_path)
            )

        except Exception as exc:

            image_results.append(
                {
                    "image":
                        image_path.name,

                    "status":
                        "DAMAGE_MODEL_ERROR",

                    "error":
                        str(exc),

                    "detections":
                        [],
                }
            )

            continue

        try:

            parts = detect_parts(
                str(image_path)
            )

        except Exception as exc:

            image_results.append(
                {
                    "image":
                        image_path.name,

                    "status":
                        "PARTS_MODEL_ERROR",

                    "error":
                        str(exc),

                    "detections":
                        [],
                }
            )

            continue

        fused = (
            fuse_damage_to_parts(
                damages,
                parts,
                height,
                width,
            )
            if damages
            else []
        )

        if isinstance(fused, dict):
            fused_list = fused.get("fused_items", [])
        elif isinstance(fused, list):
            fused_list = fused
        else:
            fused_list = []

        image_results.append(
            {
                "image":
                    image_path.name,

                "status":
                    "completed",

                "image_size":
                    [width, height],

                "detections":
                    fused_list,

                "model_outputs":
                    {
                        "damage_count":
                            len(damages),

                        "part_count":
                            len(parts),
                    },
            }
        )

    analysis = {
        "claim_id":
            claim_id,

        "analysis_timestamp_utc":
            utc_now_iso(),

        "images":
            image_results,
    }

    # ------------------------------------------------------------
    # 3. Technician verification
    # ------------------------------------------------------------

    analysis = (
        apply_technician_verification(
            analysis,
            technician_overrides,
            claim_info.get(
                "technician_name",
                "",
            ),
        )
    )

    analysis[
        "technician_overrides"
    ] = technician_overrides or {}

    # Stable F01/F02/... references.
    assign_finding_references(
        analysis
    )

    # ------------------------------------------------------------
    # 4. Consistency
    # ------------------------------------------------------------

    consistency = consistency_check(
        claim_info.get(
            "accident_description",
            "",
        ),
        active_detections(
            analysis
        ),
    )

    analysis[
        "consistency_check"
    ] = consistency

    # ------------------------------------------------------------
    # 5. Repair estimation
    # ------------------------------------------------------------

    repair_estimate = (
        build_repair_estimate(
            analysis,
            workshop_items,
        )
    )

    analysis[
        "repair_estimate"
    ] = repair_estimate

    # ------------------------------------------------------------
    # 6. Summary
    # ------------------------------------------------------------

    analysis[
        "claim_summary"
    ] = build_claim_summary(
        analysis
    )

    # ------------------------------------------------------------
    # 7. Supporting documents
    # ------------------------------------------------------------

    analysis[
        "document_status"
    ] = inspect_supporting_documents(
        supporting_documents_dir
    )

    # ------------------------------------------------------------
    # 8. Package directories
    # ------------------------------------------------------------

    directories = (
        build_package_directories(
            package_dir
        )
    )

    # ------------------------------------------------------------
    # 9. Copy original + annotated evidence
    # ------------------------------------------------------------

    copy_evidence(
        image_paths,
        image_results,
        directories,
    )

    # ------------------------------------------------------------
    # 10. Copy supporting documents
    # ------------------------------------------------------------

    copy_supporting_documents(
        supporting_documents_dir,
        directories[
            "supporting"
        ],
    )

    # ------------------------------------------------------------
    # 11. Build claim JSON
    # ------------------------------------------------------------

    model_metadata = (
        model_metadata or {}
    )

    package = (
        build_claim_package_json(
            claim_id=claim_id,
            claim_info=claim_info,
            analysis=analysis,
            quality=quality,
            model_metadata=model_metadata,
        )
    )

    # ------------------------------------------------------------
    # 12. Compute submission status
    # ------------------------------------------------------------

    status_code, status_text, open_items = (
        compute_submission_status(
            package
        )
    )

    package[
        "submission_status"
    ] = status_code

    package[
        "open_items"
    ] = open_items

    # ------------------------------------------------------------
    # 13. Save JSON
    # ------------------------------------------------------------

    json_path = (
        package_dir
        / "claim_package.json"
    )

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            package,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    # ------------------------------------------------------------
    # 14. Generate PDF
    # ------------------------------------------------------------

    pdf_path = (
        package_dir
        / "claim_report.pdf"
    )

    build_claim_pdf(
        pkg=package,
        out_path=pdf_path,
        original_dir=directories[
            "original"
        ],
        annotated_dir=directories[
            "annotated"
        ],
        supporting_dir=directories[
            "supporting"
        ],
    )

    # ------------------------------------------------------------
    # 15. Manifest
    # ------------------------------------------------------------

    manifest = create_manifest(
        package_dir,
        claim_id,
        status_code,
    )

    manifest_path = (
        package_dir
        / "PACKAGE_MANIFEST.json"
    )

    with manifest_path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2,
        )

    # ------------------------------------------------------------
    # 16. ZIP
    # ------------------------------------------------------------

    create_zip_package(
        package_dir,
        zip_path,
    )

    # ------------------------------------------------------------
    # 17. Validate
    # ------------------------------------------------------------

    validation = validate_package(
        zip_path,
        claim_id,
    )

    # ------------------------------------------------------------
    # 18. Return API-friendly result
    # ------------------------------------------------------------

    return {

        "claim_id":
            claim_id,

        "status":
            status_code,

        "status_text":
            status_text,

        "open_items":
            open_items,

        "json_path":
            str(json_path),

        "pdf_path":
            str(pdf_path),

        "zip_path":
            str(zip_path),

        "package_directory":
            str(package_dir),

        "validation":
            validation,

        "summary":
            package[
                "ai_assessment"
            ][
                "summary"
            ],

        "repair_estimate":
            package[
                "repair_estimate"
            ],
    }