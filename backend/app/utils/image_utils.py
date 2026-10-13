from pathlib import Path


def is_valid_image_file(file_path: str | Path) -> bool:
    path = Path(file_path)
    return path.exists() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
