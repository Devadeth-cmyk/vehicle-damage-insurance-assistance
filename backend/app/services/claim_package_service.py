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

            # Older claim records stored technician decisions as plain strings
            # (for example, "CONFIRMED") instead of the structured object used
            # by current reviews. Normalize those records before applying them.
            if isinstance(override, str):
                decision = override.strip().upper()
                override = {
                    "verified": decision in {"CONFIRMED", "VERIFIED", "APPROVED"},
                    "review_note": override,
                    "verified_by": technician_name,
                }
            elif not isinstance(override, dict):
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
                "customer_address",
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
                "year",
                "vehicle_type",
                "fuel_type",
                "engine_number",
                "transmission",
                "color",
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
                "accident_type",
                "policy_type",
                "policy_expiry",
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
                analysis.get("technician_review_notes") or (
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
                or bool(analysis.get("technician_review_notes"))
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
        note = tech_verif.get("note")
        open_items.append(
            f"Human-in-the-loop technician review is required: {note}"
            if note else "Human-in-the-loop technician review is required."
        )

    repair_est = package.get("repair_estimate", {})
    if not repair_est.get("ai_preliminary_items") and not repair_est.get("workshop_items"):
        open_items.append("No preliminary repair line items compiled.")

    document_status = package.get("document_status", {})
    detected = document_status.get("detected_document_categories", {})
    missing_documents = [
        label for key, label in (
            ("vehicle_registration", "vehicle registration certificate (RC)"),
            ("driving_licence", "driving licence"),
            ("policy_document", "insurance policy / schedule"),
        ) if not detected.get(key)
    ]
    if missing_documents:
        open_items.append(
            "Required documents are missing or not verified: "
            + ", ".join(missing_documents)
            + "."
        )

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

def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _stored_image_name(item: dict[str, Any]) -> str:
    for key in (
        "image",
        "image_name",
        "filename",
        "file",
        "file_name",
        "source_image",
        "image_path",
    ):
        value = item.get(key)
        if value:
            return Path(str(value)).name
    return ""


def _stored_findings(value: Any) -> list[dict[str, Any]]:
    """
    Extract stored finding dictionaries without running any AI model.

    Supports the common structures used by the project's persisted
    damage/parts/fusion results.
    """
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]

    if not isinstance(value, dict):
        return []

    for key in (
        "fused_items",
        "detections",
        "findings",
        "results",
        "items",
        "predictions",
    ):
        candidate = value.get(key)
        if isinstance(candidate, list):
            return [x for x in candidate if isinstance(x, dict)]

    return []


def _stored_image_records(
    existing_assessment: dict[str, Any],
    image_paths: list[Path],
) -> list[dict[str, Any]]:
    """
    Build package image records exclusively from the assessment already
    persisted for this claim.

    The assessment_service stores damage/parts/severity results as arrays
    in the same order as claim.evidence. Therefore, when the individual
    model result does not contain a filename, the package maps result[i]
    to evidence[i]. No model is executed here.
    """
    damage = existing_assessment.get("damage_results")
    parts = existing_assessment.get("parts_results")
    severity = existing_assessment.get("severity_results")
    fusion = existing_assessment.get("fusion_results")

    def result_list(value: Any) -> list[Any]:
        if isinstance(value, dict):
            candidate = value.get("images")
            if isinstance(candidate, list):
                return candidate
            for key in ("results", "detections", "findings", "items"):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    return candidate
        if isinstance(value, list):
            return value
        return []

    damage_images = result_list(damage)
    parts_images = result_list(parts)
    severity_images = result_list(severity)

    # If a previous/future fusion implementation persists per-image
    # records, prefer those when they contain a recognizable image name.
    fusion_images = result_list(fusion)
    fusion_by_name: dict[str, dict[str, Any]] = {}

    for item in fusion_images:
        if not isinstance(item, dict):
            continue
        name = (
            item.get("image")
            or item.get("image_name")
            or item.get("filename")
            or item.get("file_name")
        )
        if name:
            fusion_by_name[Path(str(name)).name.lower()] = item

    def detections_from(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]

        if isinstance(value, dict):
            for key in (
                "detections",
                "fused_items",
                "findings",
                "results",
                "items",
            ):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    return [x for x in candidate if isinstance(x, dict)]

        return []

    results: list[dict[str, Any]] = []

    for index, image_path in enumerate(image_paths):
        image_name = image_path.name

        try:
            image = cv2.imread(str(image_path))
            height, width = image.shape[:2] if image is not None else (None, None)
        except Exception:
            height = width = None

        # First preference: an explicitly persisted fused image record.
        stored = fusion_by_name.get(image_name.lower())

        if stored is not None:
            detections = detections_from(stored)
            status = stored.get("status", "stored_assessment")
        else:
            # Current assessment_service persists model results as parallel
            # arrays without filenames. Preserve the original evidence order.
            damage_item = (
                damage_images[index]
                if index < len(damage_images)
                else []
            )
            parts_item = (
                parts_images[index]
                if index < len(parts_images)
                else []
            )
            severity_item = (
                severity_images[index]
                if index < len(severity_images)
                else []
            )

            damage_detections = detections_from(damage_item)
            part_detections = detections_from(parts_item)
            severity_detections = detections_from(severity_item)

            # Existing stored results may already be fused.
            if isinstance(damage_item, dict) and (
                "fused_items" in damage_item
                or "part" in damage_item
            ):
                detections = damage_detections
            else:
                # Do not invent a new fusion result. Preserve the stored
                # detections in a single list for the existing PDF schema.
                detections = damage_detections

                # If damage results are empty, keep the stored part/severity
                # information visible rather than rerunning inference.
                if not detections:
                    detections = part_detections or severity_detections

            status = "stored_assessment"

        result: dict[str, Any] = {
            "image": image_name,
            "status": status,
            "detections": detections,
            "assessment_source": "database",
        }

        if width is not None and height is not None:
            result["image_size"] = [width, height]

        result["model_outputs"] = {
            "damage_count": len(
                detections_from(
                    damage_images[index]
                    if index < len(damage_images)
                    else []
                )
            ),
            "part_count": len(
                detections_from(
                    parts_images[index]
                    if index < len(parts_images)
                    else []
                )
            ),
            "severity_count": len(
                detections_from(
                    severity_images[index]
                    if index < len(severity_images)
                    else []
                )
            ),
        }

        results.append(result)

    return results


def _merge_stored_repair_estimate(
    existing_assessment: dict[str, Any],
    workshop_items: list[dict[str, Any]] | None,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """
    Preserve the service-center repair result when it is already stored.

    If the DB contains the project's repair-estimate structure, use it as
    the source of truth. Otherwise fall back to the existing rate-card
    builder only for the derived AI-indicative portion.
    """
    stored = existing_assessment.get("repair_results")

    if isinstance(stored, dict):
        result = dict(stored)

        # Normalize the service-center estimate lines for the PDF. The UI
        # stores part / damage / partsCost / laborCost, while the PDF consumes
        # description / quantity / unit_price / amount.
        items = result.get("workshop_items")
        if not isinstance(items, list):
            items = result.get("items")
        if isinstance(items, list):
            normalized_items = []
            for item in items:
                if not isinstance(item, dict):
                    continue

                quantity = float(item.get("quantity") or 1)
                parts_cost = float(item.get("partsCost") or 0)
                labor_cost = float(item.get("laborCost") or 0)
                unit_price = float(
                    item.get("unit_price")
                    if item.get("unit_price") is not None
                    else parts_cost + labor_cost
                )
                description = item.get("description")
                if not description:
                    description_parts = [
                        str(item.get("part") or "Workshop repair"),
                        str(item.get("damage") or ""),
                        str(item.get("action") or ""),
                    ]
                    description = " — ".join(
                        part for part in description_parts if part
                    )

                normalized_items.append({
                    **item,
                    "description": description,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "amount": float(
                        item.get("amount")
                        if item.get("amount") is not None
                        else quantity * unit_price
                    ),
                })
            result["workshop_items"] = normalized_items

        if "workshop_total" not in result:
            for key in (
                "total",
                "grand_total",
                "total_amount",
                "estimate_total",
                "total_estimated_cost",
            ):
                if result.get(key) is not None:
                    result["workshop_total"] = result[key]
                    break

        # Preserve explicit service-center data and only fill missing
        # AI-indicative fields from the existing assessment findings.
        if (
            "ai_preliminary_items" not in result
            and analysis.get("images")
        ):
            try:
                derived = build_repair_estimate(
                    analysis,
                    result.get("workshop_items") or workshop_items or [],
                )
                for key in (
                    "ai_preliminary_items",
                    "ai_preliminary_total",
                    "review_required",
                ):
                    if key not in result and key in derived:
                        result[key] = derived[key]
            except Exception:
                result.setdefault("ai_preliminary_items", [])
                result.setdefault("ai_preliminary_total", 0.0)
                result.setdefault("review_required", True)

        result.setdefault(
            "workshop_items",
            workshop_items or [],
        )
        result.setdefault("workshop_total", 0.0)

        return result

    # No persisted repair structure: retain the existing project's
    # repair-estimation behavior rather than inventing values.
    return build_repair_estimate(
        analysis,
        workshop_items or [],
    )


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
    evidence_order: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate the claim package from the CURRENT CLAIM and the
    ALREADY-STORED assessment.

    Important:
        This function deliberately does NOT run the damage detector,
        parts detector, or fusion model again.

    The package is therefore a snapshot of:
        claim -> persisted assessment -> technician review ->
        repair estimate -> JSON -> PDF -> ZIP
    """

    evidence_dir = Path(evidence_dir)
    supporting_documents_dir = Path(supporting_documents_dir)
    output_dir = Path(output_dir)

    package_dir = output_dir / claim_id
    zip_path = output_dir / f"{claim_id}_digital_claim_package.zip"

    # ------------------------------------------------------------
    # 1. Evidence
    # ------------------------------------------------------------
    #
    # CRITICAL: assessment_service.py processes claim.evidence in its
    # database order. The old package generator used list_images(), which
    # alphabetically sorted the filesystem. That can associate the stored
    # result for evidence[0] with the physical file for evidence[1].
    #
    # The endpoint now passes the exact ClaimEvidence order used by the
    # assessment. We therefore reconstruct image_paths in that order.
    # This is the authoritative image order for the PDF.
    #
    if evidence_order:
        discovered = {
            p.name.lower(): p
            for p in evidence_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        }

        missing = [
            name for name in evidence_order
            if Path(str(name)).name.lower() not in discovered
        ]

        if missing:
            raise ValueError(
                "Evidence mapping failed. The following database evidence "
                "files are missing from the claim evidence directory: "
                + ", ".join(missing)
            )

        image_paths = [
            discovered[Path(str(name)).name.lower()]
            for name in evidence_order
        ]

        # Only the DB-linked evidence is packaged; stale/unlinked files are
        # deliberately ignored.
        quality = [
            photo_quality_report(path)
            for path in image_paths
        ]
    else:
        image_paths, quality = inspect_evidence(evidence_dir)

    # ------------------------------------------------------------
    # 2. USE THE EXISTING DATABASE ASSESSMENT
    # ------------------------------------------------------------

    image_results = _stored_image_records(
        existing_assessment,
        image_paths,
    )

    analysis = {
        "claim_id": claim_id,
        "assessment_id": existing_assessment.get("assessment_id"),
        "assessment_status": existing_assessment.get("status"),
        "analysis_timestamp_utc": utc_now_iso(),
        "images": image_results,
        "source": "persisted_database_assessment",
        "evidence_order": [p.name for p in image_paths],
    }

    # Preserve persisted technician overrides if present.
    persisted_fusion = existing_assessment.get("fusion_results")
    persisted_overrides = {}

    if isinstance(persisted_fusion, dict):
        persisted_overrides = (
            persisted_fusion.get("technician_overrides")
            or persisted_fusion.get("overrides")
            or {}
        )
        analysis["technician_review_notes"] = str(
            persisted_fusion.get("review_notes") or ""
        ).strip()

    effective_overrides = (
        technician_overrides
        or persisted_overrides
        or {}
    )

    # Apply only explicit technician overrides. Existing verification
    # fields in the DB are otherwise preserved.
    analysis = apply_technician_verification(
        analysis,
        effective_overrides,
        str(claim_info.get("technician_name") or ""),
    )

    analysis["technician_overrides"] = effective_overrides

    # Stable references for the existing PDF.
    assign_finding_references(analysis)

    # ------------------------------------------------------------
    # 3. Consistency
    # ------------------------------------------------------------

    consistency = consistency_check(
        str(claim_info.get("accident_description") or ""),
        active_detections(analysis),
    )

    analysis["consistency_check"] = consistency

    # ------------------------------------------------------------
    # 4. Repair estimate
    # ------------------------------------------------------------

    repair_estimate = _merge_stored_repair_estimate(
        existing_assessment,
        workshop_items,
        analysis,
    )

    analysis["repair_estimate"] = repair_estimate

    # ------------------------------------------------------------
    # 5. Summary
    # ------------------------------------------------------------

    analysis["claim_summary"] = build_claim_summary(analysis)

    # ------------------------------------------------------------
    # 6. Supporting documents
    # ------------------------------------------------------------

    analysis["document_status"] = inspect_supporting_documents(
        supporting_documents_dir
    )

    # ------------------------------------------------------------
    # 7. Package directories
    # ------------------------------------------------------------

    directories = build_package_directories(package_dir)

    # ------------------------------------------------------------
    # 8. Copy EXACT original evidence + matching annotations
    # ------------------------------------------------------------

    copy_evidence(
        image_paths,
        image_results,
        directories,
    )

    # ------------------------------------------------------------
    # 9. Supporting documents
    # ------------------------------------------------------------

    copy_supporting_documents(
        supporting_documents_dir,
        directories["supporting"],
    )

    # ------------------------------------------------------------
    # 10. Build JSON consumed by the existing PDF layout
    # ------------------------------------------------------------

    model_metadata = model_metadata or {}

    package = build_claim_package_json(
        claim_id=claim_id,
        claim_info=claim_info,
        analysis=analysis,
        quality=quality,
        model_metadata=model_metadata,
    )

    # Explicit evidence traceability. These filenames are the exact
    # ClaimEvidence records, in the same order used by assessment_service.py.
    package["evidence_traceability"] = [
        {
            "sequence": index + 1,
            "file_name": path.name,
            "source": "ClaimEvidence.file_path",
        }
        for index, path in enumerate(image_paths)
    ]

    status_code, status_text, open_items = compute_submission_status(
        package
    )

    package["submission_status"] = status_code
    package["open_items"] = open_items

    # Keep source-traceability information in JSON.
    package["assessment_source"] = {
        "assessment_id": existing_assessment.get("assessment_id"),
        "status": existing_assessment.get("status"),
        "source": "database",
    }

    # ------------------------------------------------------------
    # 11. Save JSON
    # ------------------------------------------------------------

    json_path = package_dir / "claim_package.json"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            package,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    # ------------------------------------------------------------
    # 12. Generate PDF
    # ------------------------------------------------------------

    pdf_path = package_dir / "claim_report.pdf"

    build_claim_pdf(
        pkg=package,
        out_path=pdf_path,
        original_dir=directories["original"],
        annotated_dir=directories["annotated"],
        supporting_dir=directories["supporting"],
    )

    # ------------------------------------------------------------
    # 13. Manifest
    # ------------------------------------------------------------

    manifest = create_manifest(
        package_dir,
        claim_id,
        status_code,
    )

    manifest_path = package_dir / "PACKAGE_MANIFEST.json"

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(
            manifest,
            f,
            indent=2,
        )

    # ------------------------------------------------------------
    # 14. ZIP
    # ------------------------------------------------------------

    create_zip_package(
        package_dir,
        zip_path,
    )

    # ------------------------------------------------------------
    # 15. Validate
    # ------------------------------------------------------------

    validation = validate_package(
        zip_path,
        claim_id,
    )

    # ------------------------------------------------------------
    # 16. Return
    # ------------------------------------------------------------

    return {
        "claim_id": claim_id,
        "status": status_code,
        "status_text": status_text,
        "open_items": open_items,
        "json_path": str(json_path),
        "pdf_path": str(pdf_path),
        "zip_path": str(zip_path),
        "package_directory": str(package_dir),
        "validation": validation,
        "summary": package["ai_assessment"]["summary"],
        "repair_estimate": package["repair_estimate"],
    }

