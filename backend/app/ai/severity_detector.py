import logging
from pathlib import Path

from app.ai.model_loader import INFERENCE_LOCK, get_severity_model
from app.core.config import settings

logger = logging.getLogger(__name__)


def detect_severity(image_path: str, confidence: float | None = None) -> list[dict]:
    """
    Learned severity model (optional).

    Returns a plain list: [{"severity": "Minor|Moderate|Severe",
    "confidence", "bbox"}]. Returns [] when the severity model is not
    installed - the heuristic in severity_service is then used instead.
    """
    model = get_severity_model()
    if model is None:
        logger.info("Severity model not available - heuristic severity will be used")
        return []

    conf_threshold = settings.SEVERITY_CONF if confidence is None else confidence

    kwargs = {"conf": conf_threshold, "verbose": False}
    if settings.IMG_SIZE:
        kwargs["imgsz"] = settings.IMG_SIZE

    try:
        with INFERENCE_LOCK:
            result = model.predict(source=str(Path(image_path)), **kwargs)[0]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Severity detection failed, using heuristic: %s", exc)
        return []

    detections: list[dict] = []

    for box in result.boxes:
        conf = float(box.conf[0])
        if conf < conf_threshold:
            continue

        x1, y1, x2, y2 = box.xyxy[0].tolist()
        label = str(model.names[int(box.cls[0])])

        detections.append(
            {
                "severity": label.capitalize(),
                "confidence": round(conf, 3),
                "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
            }
        )

    return detections
