"""Shared paths for the RAG scripts in this repository layout."""

from pathlib import Path


def _find_project_root() -> Path:
    """Find the repository root whether run from root scripts or backend copy."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "data").is_dir() and (candidate / "processed").is_dir():
            return candidate
    raise RuntimeError("Could not find project root containing data/ and processed/.")


PROJECT_ROOT = _find_project_root()
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = PROJECT_ROOT / "processed"
