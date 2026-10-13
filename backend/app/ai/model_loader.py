"""
Model loading for the AI pipeline.

Fixes compared to the previous version:
  * Paths are resolved against the backend root (and a few fallbacks), so the
    result no longer depends on the directory uvicorn was started from.
  * A failed load is NOT cached (the old `lru_cache` cached `None` forever, so
    one bad start silently disabled the detector until a full restart).
  * A single lock is exposed so YOLO models are never called concurrently
    from FastAPI's thread pool.
"""
import logging
import threading
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# <backend_root>/app/ai/model_loader.py -> <backend_root>
BACKEND_ROOT = Path(__file__).resolve().parents[2]

# One lock shared by every detector (YOLO objects are not thread-safe).
INFERENCE_LOCK = threading.RLock()

_MODELS: dict[str, object] = {}
_LOAD_ERRORS: dict[str, str] = {}


def resolve_model_path(configured: Optional[str], kind: str) -> Optional[Path]:
    """Find the weight file. Returns None if nothing usable is found."""
    if not configured:
        return None

    raw = Path(configured)
    candidates: list[Path] = []

    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(BACKEND_ROOT / raw)          # <backend>/models/...
        candidates.append(Path.cwd() / raw)            # legacy: relative to cwd
        candidates.append(BACKEND_ROOT.parent / raw)   # <backend>/../models/...

    # Convenience: parts weights are called parts.pt in some setups and
    # best.pt in others.
    for base in list(candidates):
        if base.name in ("parts.pt", "best.pt"):
            alt = "best.pt" if base.name == "parts.pt" else "parts.pt"
            candidates.append(base.with_name(alt))

    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_size >= 1000:
                return candidate.resolve()
        except OSError:
            continue

    return None


def _load(kind: str, configured: Optional[str]):
    if kind in _MODELS:
        return _MODELS[kind]

    path = resolve_model_path(configured, kind)
    if path is None:
        _LOAD_ERRORS[kind] = (
            f"{kind} model weights not found (configured: {configured!r}, "
            f"backend root: {BACKEND_ROOT})"
        )
        logger.error(_LOAD_ERRORS[kind])
        return None

    try:
        from ultralytics import YOLO

        model = YOLO(str(path))
    except Exception as exc:  # noqa: BLE001
        _LOAD_ERRORS[kind] = f"Failed to load {kind} model from {path}: {exc}"
        logger.error(_LOAD_ERRORS[kind])
        return None

    _MODELS[kind] = model
    _LOAD_ERRORS.pop(kind, None)
    logger.info("Loaded %s model from %s", kind, path)
    return model


def get_damage_model():
    return _load("damage", settings.DAMAGE_MODEL_PATH)


def get_parts_model():
    return _load("parts", settings.PARTS_MODEL_PATH)


def get_severity_model():
    return _load("severity", settings.SEVERITY_MODEL_PATH)


def preload_models() -> dict:
    """Load everything once (called at application startup)."""
    get_damage_model()
    get_parts_model()
    get_severity_model()
    return model_status()


def model_status() -> dict:
    return {
        "damage_model_loaded": "damage" in _MODELS,
        "parts_model_loaded": "parts" in _MODELS,
        "severity_model_loaded": "severity" in _MODELS,
        "errors": dict(_LOAD_ERRORS),
    }
