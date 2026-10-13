"""
Severity logic (ported from the validated pipeline: severity_estimator.py).

1. Prefer the learned severity model when one of its boxes overlaps the
   damage box (IoU >= 0.30).
2. Otherwise fall back to the project heuristic (damage type -> severity,
   escalated one level if the box covers >= 30% of the image).
"""

SEVERITY_MAP = {
    "scratch": "Minor",
    "dent": "Moderate",
    "crack": "Moderate",
    "lamp broken": "Moderate",
    "glass shatter": "Severe",
    "tire flat": "Severe",
}

VALID_SEVERITIES = {"Minor", "Moderate", "Severe"}

SEVERITY_ORDER = {"Minor": 1, "Moderate": 2, "Severe": 3}

_ORDERED = ["Minor", "Moderate", "Severe"]

AREA_ESCALATION_THRESHOLD = 0.30
IOU_MATCH_THRESHOLD = 0.30


def normalize_damage_name(name: str) -> str:
    return str(name).strip().lower().replace("_", " ")


def project_severity(damage_type: str) -> str | None:
    return SEVERITY_MAP.get(normalize_damage_name(damage_type))


def _escalate(label: str) -> str:
    idx = _ORDERED.index(label)
    return _ORDERED[min(idx + 1, len(_ORDERED) - 1)]


def estimate_severity(damage_type, bbox=None, img_area=None, use_area_escalation=True) -> str:
    # Unknown damage types default to Moderate (never understate).
    base = project_severity(damage_type) or "Moderate"

    if not use_area_escalation or bbox is None or not img_area:
        return base

    x1, y1, x2, y2 = bbox
    box_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    ratio = box_area / img_area if img_area > 0 else 0.0

    return _escalate(base) if ratio >= AREA_ESCALATION_THRESHOLD else base


def box_iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter

    return inter / union if union > 0 else 0.0


def resolve_severity(
    damage_type,
    damage_bbox,
    img_area,
    severity_detections,
    iou_threshold=IOU_MATCH_THRESHOLD,
    use_area_escalation=True,
) -> dict:
    """
    Returns {"severity", "source": "model"|"heuristic", "confidence", "iou"}.
    """
    best, best_iou = None, 0.0
    for det in severity_detections or []:
        iou = box_iou(damage_bbox, det["bbox"])
        if iou > best_iou:
            best, best_iou = det, iou

    if best is not None and best_iou >= iou_threshold:
        return {
            "severity": best["severity"],
            "source": "model",
            "confidence": best["confidence"],
            "iou": round(best_iou, 3),
        }

    return {
        "severity": estimate_severity(
            damage_type,
            bbox=damage_bbox,
            img_area=img_area,
            use_area_escalation=use_area_escalation,
        ),
        "source": "heuristic",
        "confidence": None,
        "iou": round(best_iou, 3) if best else 0.0,
    }
