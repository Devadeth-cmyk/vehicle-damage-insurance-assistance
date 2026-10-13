"""
ai/fusion_service.py  (ported unchanged from the validated pipeline)
The fusion layer: associates each damage detection with the most likely
vehicle part, using the overlap formula and centroid fallback from
Sections 12-17 of the requirements doc.
"""
import numpy as np

OVERLAP_THRESHOLD = 0.20  # Section 15
# Below this overlap, the centroid fallback is tried before giving up (Section 16)
CENTROID_FALLBACK_TRIGGER = 0.20

# Manual-review triggers (Section 25)
LOW_PART_CONFIDENCE = 0.5
LOW_DAMAGE_CONFIDENCE = 0.5
AMBIGUOUS_MARGIN = 0.10  # if top-2 candidate parts' overlap scores differ by less than this


def _bbox_to_mask(bbox, img_h, img_w):
    """Converts a damage bounding box into a binary mask matching the image dimensions."""
    x1, y1, x2, y2 = [int(round(v)) for v in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(img_w, x2), min(img_h, y2)
    mask = np.zeros((img_h, img_w), dtype=bool)
    mask[y1:y2, x1:x2] = True
    return mask


def _overlap_score(damage_mask, part_mask):
    """
    overlap_score = area(damage ∩ part) / area(damage)
    Represents what fraction of the damage region falls inside this part's mask.
    """
    damage_area = damage_mask.sum()
    if damage_area == 0:
        return 0.0
    intersection = np.logical_and(damage_mask, part_mask).sum()
    return float(intersection) / float(damage_area)


def _centroid_inside(bbox, part_mask):
    """Section 16: fallback check — is the damage box's centroid inside this part mask?"""
    x1, y1, x2, y2 = bbox
    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
    h, w = part_mask.shape
    if 0 <= cy < h and 0 <= cx < w:
        return bool(part_mask[cy, cx])
    return False


def fuse_detections(damage_detections, part_detections, img_h, img_w,
                     overlap_threshold=OVERLAP_THRESHOLD):
    """
    For every damage detection, find the best-matching vehicle part.

    Returns a list matching Section 18's Final Unified Output schema:
    [{
        "part": "front_bumper", "damage_type": "dent", "severity": None,
        "damage_confidence": 0.91, "part_confidence": 0.94, "overlap_score": 0.78,
        "bbox": [...], "requires_review": False
    }, ...]
    """
    fused_results = []

    for damage in damage_detections:
        damage_mask = _bbox_to_mask(damage["bbox"], img_h, img_w)

        # Score every detected part against this damage region
        scored_parts = []
        for part in part_detections:
            score = _overlap_score(damage_mask, part["mask"])
            scored_parts.append((part, score))

        scored_parts.sort(key=lambda x: x[1], reverse=True)

        best_part, best_score = (scored_parts[0] if scored_parts else (None, 0.0))
        second_score = scored_parts[1][1] if len(scored_parts) > 1 else 0.0

        used_centroid_fallback = False

        # Primary method: overlap threshold
        if best_part is None or best_score < overlap_threshold:
            # Centroid fallback (Section 16) — check if damage box center falls inside any part
            centroid_match = None
            for part in part_detections:
                if _centroid_inside(damage["bbox"], part["mask"]):
                    centroid_match = part
                    break
            if centroid_match is not None:
                best_part = centroid_match
                best_score = _overlap_score(damage_mask, centroid_match["mask"])
                used_centroid_fallback = True
            else:
                best_part = None  # genuinely unknown — Section 17

        # Build the result record
        if best_part is None:
            result = {
                "part": "unknown",
                "damage_type": damage["damage_type"],
                "severity": damage.get("severity"),
                "severity_source": damage.get("severity_source"),
                "damage_confidence": damage["confidence"],
                "part_confidence": None,
                "overlap_score": round(best_score, 3),
                "bbox": damage["bbox"],
                "requires_review": True,
                "review_reason": "no_part_matched",
            }
        else:
            requires_review = False
            review_reasons = []

            if best_part["confidence"] < LOW_PART_CONFIDENCE:
                requires_review = True
                review_reasons.append("low_part_confidence")
            if damage["confidence"] < LOW_DAMAGE_CONFIDENCE:
                requires_review = True
                review_reasons.append("low_damage_confidence")
            if not used_centroid_fallback and (best_score - second_score) < AMBIGUOUS_MARGIN and second_score > 0:
                requires_review = True
                review_reasons.append("ambiguous_part_match")
            if used_centroid_fallback:
                requires_review = True
                review_reasons.append("centroid_fallback_used")

            result = {
                "part": best_part["part"],
                "damage_type": damage["damage_type"],
                "severity": damage.get("severity"),
                "severity_source": damage.get("severity_source"),
                "damage_confidence": damage["confidence"],
                "part_confidence": best_part["confidence"],
                "overlap_score": round(best_score, 3),
                "bbox": damage["bbox"],
                "requires_review": requires_review,
            }
            if review_reasons:
                result["review_reason"] = ", ".join(review_reasons)

        fused_results.append(result)

    return fused_results


def fuse_damage_to_parts(damage_detections, part_detections, img_h, img_w):
    """Backward-compatible alias for the old stub name."""
    return fuse_detections(damage_detections, part_detections, img_h, img_w)
