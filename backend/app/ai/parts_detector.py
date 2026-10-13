import logging

import cv2
import numpy as np

from app.ai.model_loader import INFERENCE_LOCK, get_parts_model
from app.core.config import settings

logger = logging.getLogger(__name__)


def detect_parts(image_path: str) -> list[dict]:
    """
    Vehicle-part segmentation.

    Each item carries a full-resolution boolean numpy mask under "mask"
    (needed by the fusion step). Masks are NOT JSON serialisable - use
    `strip_masks()` before storing results in the database.

    Raises RuntimeError if the parts model is unavailable.
    """
    model = get_parts_model()
    if model is None:
        raise RuntimeError(
            "Parts model is not loaded - check PARTS_MODEL_PATH in .env"
        )

    # retina_masks=True makes Ultralytics return masks already mapped back onto the
    # ORIGINAL image (letterbox padding removed). Without it, `masks.data` is in the
    # padded model-input space and the plain cv2.resize below would shift every part
    # mask relative to the damage boxes, skewing the part attribution in fusion.
    kwargs = {"conf": settings.PARTS_CONF, "verbose": False, "retina_masks": True}
    if settings.IMG_SIZE:
        kwargs["imgsz"] = settings.IMG_SIZE

    with INFERENCE_LOCK:
        result = model.predict(source=str(image_path), **kwargs)[0]

    if result.masks is None:
        return []

    img_h, img_w = result.orig_shape
    detections: list[dict] = []

    for box, mask_data in zip(result.boxes, result.masks.data):
        conf = float(box.conf[0])
        if conf < settings.PARTS_CONF:
            continue

        mask_np = mask_data.cpu().numpy().astype(np.uint8)
        if mask_np.shape != (img_h, img_w):  # only if retina masks were unavailable
            mask_np = cv2.resize(mask_np, (img_w, img_h), interpolation=cv2.INTER_NEAREST)

        detections.append(
            {
                "part_id": len(detections) + 1,
                "part": model.names[int(box.cls[0])],
                "confidence": round(conf, 3),
                "bbox": [round(v, 1) for v in box.xyxy[0].tolist()],
                "mask": mask_np.astype(bool),
            }
        )

    return detections


def strip_masks(parts: list[dict]) -> list[dict]:
    """JSON-safe copy of the part detections (drops numpy masks)."""
    clean = []
    for part in parts:
        item = {k: v for k, v in part.items() if k != "mask"}
        mask = part.get("mask")
        if mask is not None:
            item["mask_area_px"] = int(mask.sum())
        clean.append(item)
    return clean
