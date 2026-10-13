"""
AI assessment service.

Pipeline per evidence image (same order/logic as the validated backend):

    severity model (optional)
        -> damage model (+ severity resolution)
        -> parts segmentation model
        -> FUSION (damage box <-> part mask overlap, centroid fallback)
        -> repair estimate (one line per part+damage, not per detection)

Persisted layout (all JSON-safe, one record per evidence image, in the same
order as claim.evidence, each carrying the image file name):

    damage_results   = {"images": [{"image", "status", "image_size", "detections": [...]}]}
    parts_results    = {"images": [{"image", "status", "image_size", "detections": [...]}]}
    severity_results = {"images": [{"image", "status", "image_size", "detections": [...]}]}
    fusion_results   = {"images": [{"image", "status", "image_size", "detections": [fused...]}],
                        "summary": {...warnings, counts...},
                        "technician_overrides": {finding_id: decision}, ...}
    repair_results   = {"items": [...workshop...], "ai_estimate": {...}}  # workshop items preserved

Every fused finding carries a stable ``finding_id`` = "<image>_D<damage_id>".
Technician overrides and the UI reference findings by that id, so nothing in
the review / estimate screens needs to be hard-coded.
"""
import hashlib
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import cv2
from sqlalchemy.orm import Session

from app.ai.damage_detector import detect_damage
from app.ai.fusion_service import fuse_detections
from app.ai.model_loader import model_status
from app.ai.parts_detector import detect_parts, strip_masks
from app.ai.repair_estimator import estimate_claim_repair_total
from app.ai.severity_detector import detect_severity
from app.core.config import settings
from app.db.models.assessment import Assessment, AssessmentStatus
from app.db.models.claim import Claim, ClaimStatus

logger = logging.getLogger(__name__)

DAMAGE_MODEL_VERSION = "cardd-v1"
PARTS_MODEL_VERSION = "parts-v1"
SEVERITY_MODEL_VERSION = "severity-v1"

# Keys written by the service-center screens that must survive a re-run.
_PRESERVED_FUSION_KEYS = ("technician_overrides", "review_notes", "technician_name")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VALID_SEGMENTS = {"economy", "mid-range", "luxury"}

# Evidence whose category / file name contains one of these is a document
# (policy, RC, licence ...), not a photograph of the damaged vehicle. Running the
# damage model on a scanned licence produces nonsense detections that end up in
# the repair cost, so these are excluded from the assessment.
_NON_PHOTO_KEYWORDS = (
    "policy", "registration", "rc book", "rc_book", "rcbook", "licen", "driving",
    "insurance", "document", "certificate", "aadhaar", "aadhar", "pan card",
    "pan_card", "id proof", "id_proof", "invoice", "supporting",
)

_SEVERITY_RANK = {"minor": 1, "moderate": 2, "severe": 3}

# The UI used to ship a hard-coded repair table and persisted it as if a
# workshop had entered it. Recognise exactly that signature so it can be purged.
_LEGACY_PLACEHOLDER_LINES = {
    ("Front Bumper Assembly", 140.0, 80.0),
    ("Headlamp Cluster", 210.0, 40.0),
}


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def _select_damage_photos(evidence_items) -> tuple[list[tuple], list[dict]]:
    """
    Returns ([(evidence, image_name), ...], skipped) where skipped explains every
    evidence row that was NOT analysed (document / not an image / duplicate file).
    image_name is the evidence.file_name, which is what the claim package uses
    to refer to the photo.
    """
    selected: list[tuple] = []
    skipped: list[dict] = []
    seen_paths: set[str] = set()

    for evidence in evidence_items:
        path = Path(evidence.file_path)
        name = Path(str(getattr(evidence, "file_name", None) or path.name)).name
        category = str(getattr(evidence, "file_type", "") or "")
        label = f"{category} {name}".lower()

        reason = None
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            reason = "not_an_image"
        elif any(keyword in label for keyword in _NON_PHOTO_KEYWORDS):
            reason = "document_not_a_damage_photo"
        else:
            key = os.path.normcase(str(path.resolve()))
            if key in seen_paths:
                reason = "duplicate_file"
            else:
                seen_paths.add(key)

        if reason:
            skipped.append({"image": name, "file_type": category, "reason": reason})
        else:
            selected.append((evidence, name))

    return selected, skipped


def _resolve_vehicle_segment(claim: Claim) -> tuple[str, str]:
    """
    Pricing segment for the claim: taken from the claim / vehicle when set,
    otherwise the configured default. The source is returned (and stored in the
    results) so a default is never mistaken for real data.
    """
    vehicle = getattr(claim, "vehicle", None)
    candidates = (
        ("claim", getattr(claim, "vehicle_segment", None)),
        ("vehicle", getattr(vehicle, "vehicle_segment", None)),
        ("vehicle", getattr(vehicle, "segment", None)),
    )
    for source, value in candidates:
        normalised = str(getattr(value, "value", value) or "").strip().lower().replace("_", "-")
        if normalised in VALID_SEGMENTS:
            return normalised, source

    default = str(getattr(settings, "VEHICLE_SEGMENT_DEFAULT", "") or "").strip().lower()
    return (default if default in VALID_SEGMENTS else "economy"), "default"


@lru_cache(maxsize=8)
def _fingerprint(path_str: str, mtime: float) -> str:
    digest = hashlib.sha256()
    with open(path_str, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def _weights_fingerprint(setting_name: str) -> str | None:
    """Short hash of the weight file actually loaded, for real traceability."""
    raw = getattr(settings, setting_name, None)
    if not raw:
        return None
    try:
        path = Path(raw)
        return _fingerprint(str(path), path.stat().st_mtime)
    except (TypeError, OSError):
        return None


def _is_legacy_placeholder_items(items) -> bool:
    if not isinstance(items, list) or not items:
        return False
    try:
        signature = {
            (i.get("part"), float(i.get("partsCost")), float(i.get("laborCost")))
            for i in items
        }
    except (TypeError, ValueError, AttributeError):
        return False
    return signature == _LEGACY_PLACEHOLDER_LINES


def _severity_rank(value) -> int:
    return _SEVERITY_RANK.get(str(value or "").lower(), 0)


def _consolidate_for_estimate(fused: list[dict]) -> list[dict]:
    """
    One estimate line per (part, damage_type) across the whole claim.

    Without this, the same dent photographed from three angles is priced three
    times, and five scratches on one bumper are priced as five bumper repairs.
    Detections with no matched part cannot be matched across photos, so each
    stays on its own line (and is flagged for review).
    """
    groups: dict[tuple, list[dict]] = {}
    for det in fused:
        part = det.get("part") or "unknown"
        key = ("unknown", det.get("finding_id")) if part == "unknown" else (part, det.get("damage_type"))
        groups.setdefault(key, []).append(det)

    consolidated: list[dict] = []
    for members in groups.values():
        representative = max(
            members,
            key=lambda d: (_severity_rank(d.get("severity")), d.get("damage_confidence") or 0.0),
        )
        line = dict(representative)
        line["finding_ids"] = [m["finding_id"] for m in members if m.get("finding_id")]
        line["source_images"] = sorted({m["image"] for m in members if m.get("image")})
        line["merged_detections"] = len(members)
        line["requires_review"] = any(m.get("requires_review") for m in members)
        consolidated.append(line)

    return consolidated


def _build_summary(analysed, all_fused, skipped, segment, segment_source, purged_placeholder) -> dict:
    completed = [a for a in analysed if a["status"] == "completed"]
    failed = [
        {"image": a["image"], "status": a["status"], **({"error": a["error"]} if a.get("error") else {})}
        for a in analysed
        if a["status"] != "completed"
    ]
    heuristic = sum(1 for d in all_fused if d.get("severity_source") != "model")
    needs_review = sum(1 for d in all_fused if d.get("requires_review"))
    unmatched = sum(1 for d in all_fused if d.get("part") == "unknown")

    warnings: list[str] = []
    if completed and not all_fused:
        warnings.append(
            f"The AI found no damage in {len(completed)} analysed photo(s). "
            "This can be a model miss - the technician must inspect the vehicle manually."
        )
    if all_fused and heuristic:
        warnings.append(
            f"Severity for {heuristic} of {len(all_fused)} finding(s) is a rule-based estimate "
            "from the damage type, not a prediction of the severity model."
        )
    if unmatched:
        warnings.append(f"{unmatched} finding(s) could not be matched to a vehicle part.")
    if segment_source == "default":
        warnings.append(
            f"Vehicle segment is not set on the claim - the default '{segment}' price multiplier was used."
        )
    if skipped:
        warnings.append(
            f"{len(skipped)} evidence file(s) were excluded from the assessment "
            "(documents, non-images or duplicates)."
        )
    if failed:
        warnings.append(f"{len(failed)} photo(s) could not be analysed: " + ", ".join(f["image"] for f in failed))
    if purged_placeholder:
        warnings.append(
            "Placeholder repair lines saved by an earlier version of the portal were removed."
        )

    return {
        "images_total": len(analysed),
        "images_analysed": len(completed),
        "images_failed": failed,
        "findings": len(all_fused),
        "findings_model_severity": len(all_fused) - heuristic,
        "findings_heuristic_severity": heuristic,
        "findings_needing_review": needs_review,
        "findings_unmatched_part": unmatched,
        "vehicle_segment": segment,
        "vehicle_segment_source": segment_source,
        "warnings": warnings,
    }


def _empty_image_record(name: str, status: str, error: str | None = None) -> dict:
    record = {"image": name, "status": status, "damage": [], "parts": [], "severity": [], "fused": []}
    if error:
        record["error"] = error
    return record


def _analyse_image(image_path: Path, image_name: str) -> dict:
    """Run the full pipeline on one image. Raises if a required model is missing."""
    img = cv2.imread(str(image_path))
    if img is None:
        return _empty_image_record(image_name, "INVALID_IMAGE")

    img_h, img_w = img.shape[:2]

    severity_dets = detect_severity(str(image_path))
    damage_dets = detect_damage(str(image_path), severity_detections=severity_dets)
    part_dets = detect_parts(str(image_path))          # includes numpy masks

    fused = (
        fuse_detections(damage_dets, part_dets, img_h, img_w)
        if damage_dets
        else []
    )

    # fuse_detections() returns results in the same order as damage_dets but
    # drops the id. Technician overrides / the claim package reference
    # findings as "<image>_D<damage_id>", so carry the id through.
    for damage, fused_item in zip(damage_dets, fused):
        fused_item["damage_id"] = damage["damage_id"]
        fused_item["finding_id"] = f"{image_name}_D{damage['damage_id']}"
        fused_item["image"] = image_name

    return {
        "image": image_name,
        "status": "completed",
        "image_size": [img_w, img_h],
        "damage": damage_dets,
        "parts": strip_masks(part_dets),                # JSON-safe
        "severity": severity_dets,
        "fused": fused,
    }


# ----------------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------------
def run_assessment(claim: Claim, db: Session) -> Assessment:

    selected, skipped = _select_damage_photos(claim.evidence)
    if not selected:
        detail = ""
        if skipped:
            detail = f" ({len(skipped)} evidence file(s) were skipped: documents, non-images or duplicates)"
        raise ValueError(f"No vehicle damage photos found for this claim{detail}.")

    assessment = claim.assessment

    if assessment is None:
        assessment = Assessment(
            claim_id=claim.id,
            status=AssessmentStatus.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(assessment)
    else:
        assessment.status = AssessmentStatus.PROCESSING
        assessment.started_at = datetime.now(timezone.utc)
        assessment.error_message = None

    claim.status = ClaimStatus.ASSESSMENT_IN_PROGRESS
    db.commit()

    try:
        # Fail fast and loudly when a required model is missing, instead of
        # discovering it half-way through and mislabelling every image.
        status = model_status()
        missing = [
            name
            for name, flag in (("damage", "damage_model_loaded"), ("parts", "parts_model_loaded"))
            if not status.get(flag)
        ]
        if missing:
            raise RuntimeError(
                f"Required AI model(s) not loaded: {', '.join(missing)}. Check the model paths in .env."
            )

        segment, segment_source = _resolve_vehicle_segment(claim)

        analysed: list[dict] = []
        for evidence, image_name in selected:
            image_path = Path(evidence.file_path)

            if not image_path.exists():
                logger.warning("Evidence file missing on disk: %s", image_path)
                analysed.append(_empty_image_record(image_name, "FILE_NOT_FOUND"))
                continue

            # One bad photo must not sink the whole claim.
            try:
                analysed.append(_analyse_image(image_path, image_name))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Analysis failed for image %s", image_name)
                analysed.append(_empty_image_record(image_name, "ANALYSIS_ERROR", str(exc)))

        if not any(a["status"] == "completed" for a in analysed):
            raise RuntimeError(
                "None of the evidence images could be analysed "
                f"({[a['status'] for a in analysed]})."
            )

        def per_image(key: str) -> dict:
            records = []
            for a in analysed:
                record = {"image": a["image"], "status": a["status"], "detections": a[key]}
                if a.get("image_size"):
                    record["image_size"] = a["image_size"]
                if a.get("error"):
                    record["error"] = a["error"]
                records.append(record)
            return {"images": records}

        all_fused = [d for a in analysed for d in a["fused"]]

        # -------------------- model outputs --------------------
        assessment.damage_results = per_image("damage")
        assessment.parts_results = per_image("parts")
        assessment.severity_results = per_image("severity")

        # -------------------- repair (keep real workshop data) --
        repair = dict(assessment.repair_results) if isinstance(assessment.repair_results, dict) else {}
        repair.pop("status", None)
        repair.pop("message", None)          # old "pending" placeholder
        purged_placeholder = False
        if _is_legacy_placeholder_items(repair.get("items")):
            repair.pop("items", None)
            repair.pop("total_estimated_cost", None)
            purged_placeholder = True

        consolidated = _consolidate_for_estimate(all_fused)
        ai_estimate = estimate_claim_repair_total(consolidated, vehicle_segment=segment)

        line_items = ai_estimate.get("line_items") or []
        if len(line_items) == len(consolidated):
            for line, source in zip(line_items, consolidated):
                line["finding_ids"] = source["finding_ids"]
                line["source_images"] = source["source_images"]
                line["merged_detections"] = source["merged_detections"]
                line["severity_source"] = source.get("severity_source")
        ai_estimate["vehicle_segment"] = segment
        ai_estimate["vehicle_segment_source"] = segment_source
        ai_estimate["consolidated_from_detections"] = len(all_fused)
        ai_estimate["generic_fallback_lines"] = sum(
            1 for line in line_items if line.get("source") == "generic_fallback"
        )
        ai_estimate["provisional_lines"] = sum(1 for line in line_items if line.get("provisional"))

        repair["ai_estimate"] = ai_estimate
        assessment.repair_results = repair

        # -------------------- fusion (keep technician data) ----
        previous_fusion = assessment.fusion_results
        fusion = per_image("fused")
        fusion["status"] = "fused"
        fusion["model_versions"] = {
            "damage": DAMAGE_MODEL_VERSION,
            "parts": PARTS_MODEL_VERSION,
            "severity": SEVERITY_MODEL_VERSION,
        }
        fusion["model_weights"] = {
            "damage": _weights_fingerprint("DAMAGE_MODEL_PATH"),
            "parts": _weights_fingerprint("PARTS_MODEL_PATH"),
            "severity": _weights_fingerprint("SEVERITY_MODEL_PATH"),
        }
        fusion["models_loaded"] = {
            k: v for k, v in model_status().items() if k != "errors"
        }
        fusion["skipped_evidence"] = skipped
        fusion["summary"] = _build_summary(
            analysed, all_fused, skipped, segment, segment_source, purged_placeholder
        )

        if isinstance(previous_fusion, dict):
            for key in _PRESERVED_FUSION_KEYS:
                if key in previous_fusion:
                    fusion[key] = previous_fusion[key]

            # Overrides are keyed by finding id: keep the ones that still refer to a
            # finding in this run, and record the rest instead of silently applying
            # them to something else.
            overrides = fusion.get("technician_overrides")
            if isinstance(overrides, dict):
                valid_ids = {d["finding_id"] for d in all_fused if d.get("finding_id")}
                kept = {k: v for k, v in overrides.items() if k in valid_ids}
                dropped = sorted(set(overrides) - set(kept))
                fusion["technician_overrides"] = kept
                if dropped:
                    fusion["dropped_overrides"] = dropped

        assessment.fusion_results = fusion

        assessment.status = AssessmentStatus.COMPLETED
        assessment.completed_at = datetime.now(timezone.utc)
        claim.status = ClaimStatus.ASSESSMENT_COMPLETED

        db.commit()
        db.refresh(assessment)
        return assessment

    except Exception as exc:
        logger.exception("Assessment failed for claim %s", getattr(claim, "claim_id", claim.id))

        db.rollback()

        assessment = claim.assessment or assessment
        assessment.status = AssessmentStatus.FAILED
        assessment.error_message = str(exc)
        claim.status = ClaimStatus.HUMAN_REVIEW
        db.commit()

        raise
