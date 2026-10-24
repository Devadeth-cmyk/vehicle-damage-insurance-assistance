import logging

from app.ai.model_loader import INFERENCE_LOCK, get_damage_model
from app.ai.severity_service import estimate_severity, resolve_severity
from app.core.config import settings

logger = logging.getLogger(__name__)


def _predict_kwargs(conf: float) -> dict:
    kwargs = {"conf": conf, "verbose": False}
    if settings.IMG_SIZE:
        kwargs["imgsz"] = settings.IMG_SIZE
    return kwargs


def detect_damage(image_path: str, severity_detections: list[dict] | None = None) -> list[dict]:
    """
    Returns normalised damage detections:
    [{"damage_id", "damage_type", "bbox", "confidence", "severity", "severity_source"}]

    Raises RuntimeError if the damage model is not available, so a missing
    model is reported instead of silently looking like "no damage found".
    """
    model = get_damage_model()
    if model is None:
        raise RuntimeError(
            "Damage model is not loaded - check DAMAGE_MODEL_PATH in .env"
        )

    with INFERENCE_LOCK:
        result = model.predict(source=str(image_path), **_predict_kwargs(settings.DAMAGE_CONF))[0]

    img_h, img_w = result.orig_shape
    img_area = img_h * img_w

    detections: list[dict] = []

    for box in result.boxes:
        conf = float(box.conf[0])
        if conf < settings.DAMAGE_CONF:
            continue

        damage_type = model.names[int(box.cls[0])]
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        bbox = [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)]

        if severity_detections:
            sev = resolve_severity(damage_type, bbox, img_area, severity_detections)
            severity, source = sev["severity"], sev["source"]
        else:
            severity = estimate_severity(damage_type, bbox=bbox, img_area=img_area)
            source = "heuristic"

        detections.append(
            {
                "damage_id": len(detections) + 1,
                "damage_type": damage_type,
                "bbox": bbox,
                "confidence": round(conf, 3),
                "severity": severity,
                "severity_source": source,
            }
        )

    return detections