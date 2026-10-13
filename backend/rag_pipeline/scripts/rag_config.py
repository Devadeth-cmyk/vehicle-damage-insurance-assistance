"""Central configuration for the RAG pipeline.

Every setting can be overridden with an environment variable (or a .env file).
The Groq API key is read ONLY from the GROQ_API_KEY environment variable and is
never written to disk by this code.
"""

import os
from pathlib import Path

try:  # python-dotenv is optional
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

SCRIPTS_DIR = Path(__file__).resolve().parent
try:
    from .project_paths import PROJECT_ROOT
except ImportError:  # Running a script directly from scripts/.
    from project_paths import PROJECT_ROOT

BASE_DIR = PROJECT_ROOT

if load_dotenv:
    for _env in (BASE_DIR / ".env", BASE_DIR / "backend" / ".env", SCRIPTS_DIR / ".env"):
        if _env.exists():
            load_dotenv(_env, override=False)


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name, default):
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


# ---------------------------------------------------------------- paths
CHUNKS_FILE = BASE_DIR / "processed" / "chunks" / "all_chunks.json"
VECTOR_DB_DIR = BASE_DIR / "processed" / "vector_db"
COLLECTION_NAME = "insurance_policies"

# ---------------------------------------------------------------- retrieval
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
TOP_K = _int("RAG_TOP_K", 5)
SIMILARITY_THRESHOLD = _float("RAG_MIN_SIMILARITY", 0.25)
MAX_CHARS_PER_CHUNK = _int("RAG_MAX_CHARS_PER_CHUNK", 1800)

# Chunks whose "company" contains one of these are indexed but not offered as
# selectable insurers (they are reference documents, not insurers).
EXCLUDED_COMPANY_MARKERS = ("Vehicle Damage Description",)

# ---------------------------------------------------------------- Groq LLM
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
GROQ_TIMEOUT = _int("GROQ_TIMEOUT", 30)
GROQ_MAX_RETRIES = _int("GROQ_MAX_RETRIES", 2)
LLM_TEMPERATURE = _float("LLM_TEMPERATURE", 0.1)
LLM_MAX_TOKENS = _int("LLM_MAX_TOKENS", 600)

# ---------------------------------------------------------------- chat
MAX_QUESTION_CHARS = 1000
MAX_HISTORY_TURNS = 4


def get_groq_api_key():
    """Read the key at call time so it can be set after import."""
    return os.getenv("GROQ_API_KEY", "").strip()
