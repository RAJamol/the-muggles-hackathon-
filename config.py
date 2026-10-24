import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)

# -------------------------------------------------------------------------
# Explicit Top-Level Module Attributes (Ensures hasattr is always True)
# -------------------------------------------------------------------------
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "") or os.getenv("XAI_API_KEY", "")
GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/carebridge")
EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "384"))

APP_NAME: str = os.getenv("APP_NAME", "CareBridge AI")
HOSPITAL_NAME: str = os.getenv("HOSPITAL_NAME", "Metro General Hospital")
DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

DATA_DIR: Path = BASE_DIR / "data"
POLICIES_DIR: Path = DATA_DIR / "policies"
POLICIES_DIR.mkdir(parents=True, exist_ok=True)

def reload_config():
    """Reload settings from .env file and update module globals."""
    global GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL, DATABASE_URL, EMBEDDING_MODEL_NAME, EMBEDDING_DIM
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=True)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "") or os.getenv("XAI_API_KEY", "")
    GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/carebridge")
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

def save_groq_key(new_key: str):
    """Save Groq API key to .env and reload in-memory config."""
    clean = new_key.strip()
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    set_key(str(ENV_PATH), "GROQ_API_KEY", clean)
    reload_config()

def __getattr__(name: str) -> Any:
    """Fail-safe attribute getter so module attribute access never fails with AttributeError."""
    if name == "GROQ_API_KEY":
        return os.getenv("GROQ_API_KEY", "") or os.getenv("XAI_API_KEY", "")
    if name == "GROQ_BASE_URL":
        return os.getenv("GROQ_BASE_URL", "https://api.groq.com")
    if name == "GROQ_MODEL":
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    if name == "DATABASE_URL":
        return os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/carebridge")
    if name == "EMBEDDING_MODEL_NAME":
        return os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    if name == "EMBEDDING_DIM":
        return int(os.getenv("EMBEDDING_DIM", "384"))
    val = os.getenv(name)
    if val is not None:
        return val
    raise AttributeError(f"module 'config' has no attribute '{name}'")
