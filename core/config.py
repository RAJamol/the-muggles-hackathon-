"""
Internal alias to root config module to prevent any external package shadowing.
"""
import sys
from pathlib import Path
import importlib.util

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import config

# Re-export all attributes from root config
for attr in dir(config):
    if not attr.startswith("__"):
        globals()[attr] = getattr(config, attr)

GROQ_API_KEY = getattr(config, "GROQ_API_KEY", "")
GROQ_BASE_URL = getattr(config, "GROQ_BASE_URL", "https://api.groq.com")
GROQ_MODEL = getattr(config, "GROQ_MODEL", "openai/gpt-oss-120b")
