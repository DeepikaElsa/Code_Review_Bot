"""Central configuration for the CodeReviewBot backend.

Everything is overridable with environment variables so no secrets or
machine-specific values are committed. See .env.example (local) and
.env.production.example (hosted) at the repo root.

Two deployment shapes:
  - Local dev: PROVIDER=ollama, points at a local Ollama, no auth required.
  - Hosted:    PROVIDER=ollama (Ollama Cloud) or openai (Groq/OpenRouter),
               REQUIRE_AUTH=true, CORS locked to the deployed frontend.
"""

import os


def _flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Inference provider ------------------------------------------------------
# "ollama"  -> Ollama's /api/chat (local, or Ollama Cloud at https://ollama.com)
# "openai"  -> any OpenAI-compatible /chat/completions (Groq, OpenRouter, ...)
PROVIDER = os.environ.get("CRB_PROVIDER", "ollama").strip().lower()

# Ollama transport
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "").strip()

# OpenAI-compatible transport (defaults target Groq's free API)
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

# A hosted provider means code leaves this machine no matter which slot is used.
REMOTE_INFERENCE = PROVIDER == "openai" or not (
    OLLAMA_HOST.startswith("http://127.0.0.1") or OLLAMA_HOST.startswith("http://localhost")
)

# --- Model selection ---------------------------------------------------------
# Model ids are env-driven because hosted providers name models differently
# from local Ollama. Set these to whatever your provider actually serves.
LOCAL_MODEL = os.environ.get("CRB_MODEL", "qwen2.5-coder:7b")
FAST_MODEL = os.environ.get("CRB_FAST_MODEL", "llama3.2:3b")
CLOUD_MODEL = os.environ.get("CRB_CLOUD_MODEL", "gpt-oss:120b-cloud")

# Local Ollama refuses ":cloud" models unless the user opts in. Irrelevant when
# inference is already remote (the whole backend is talking to a hosted API).
ALLOW_CLOUD = _flag("CRB_ALLOW_CLOUD") or REMOTE_INFERENCE

MODELS = {
    "quality": {
        "id": LOCAL_MODEL,
        "label": os.environ.get("CRB_MODEL_LABEL", "Qwen2.5-Coder (quality)"),
        "description": "Best code quality. Recommended default.",
        "cloud": False,
    },
    "fast": {
        "id": FAST_MODEL,
        "label": os.environ.get("CRB_FAST_MODEL_LABEL", "Fast model"),
        "description": "Faster, lower quality. Fallback.",
        "cloud": False,
    },
    "cloud": {
        "id": CLOUD_MODEL,
        "label": os.environ.get("CRB_CLOUD_MODEL_LABEL", "Large cloud model"),
        "description": "Strongest, but your code leaves this machine.",
        "cloud": True,
    },
}

DEFAULT_MODEL_KEY = os.environ.get("CRB_DEFAULT_MODEL_KEY", "quality")

# --- Generation tuning -------------------------------------------------------
REQUEST_TIMEOUT = int(os.environ.get("CRB_TIMEOUT", "300"))
REVIEW_TEMPERATURE = float(os.environ.get("CRB_REVIEW_TEMPERATURE", "0.2"))
GENERATE_TEMPERATURE = float(os.environ.get("CRB_GENERATE_TEMPERATURE", "0.15"))
NUM_CTX = int(os.environ.get("CRB_NUM_CTX", "8192"))

# --- Verify-and-repair loop --------------------------------------------------
MAX_REPAIR_ATTEMPTS = int(os.environ.get("CRB_MAX_REPAIR_ATTEMPTS", "2"))
COMPILE_TIMEOUT = int(os.environ.get("CRB_COMPILE_TIMEOUT", "20"))
COMPILE_MEMORY_MB = int(os.environ.get("CRB_COMPILE_MEMORY_MB", "512"))
VERIFY_ENABLED = _flag("CRB_VERIFY", "true")

# --- Authentication (Supabase) ----------------------------------------------
# When REQUIRE_AUTH is on, the API rejects requests without a valid Supabase
# access token. The verify-and-repair loop only runs for authenticated users.
REQUIRE_AUTH = _flag("CRB_REQUIRE_AUTH", "false")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
# Supabase signs access tokens with this shared secret (Dashboard → Settings →
# API → JWT Secret). Used to verify tokens locally without a network round-trip.
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
SUPABASE_JWT_AUD = os.environ.get("SUPABASE_JWT_AUD", "authenticated")

# --- Server ------------------------------------------------------------------
HOST = os.environ.get("CRB_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", os.environ.get("CRB_PORT", "5000")))  # PaaS sets $PORT
DEBUG = _flag("CRB_DEBUG", "true")
MAX_CODE_CHARS = int(os.environ.get("CRB_MAX_CODE_CHARS", "60000"))

# Comma-separated allowlist of frontend origins. "*" allows any (dev only).
CORS_ORIGINS = _list("CRB_CORS_ORIGINS", "*")


def resolve_model(model_key: str | None) -> tuple[str, dict]:
    """Map a UI model key to a concrete model id.

    Falls back to the default when the key is unknown, and refuses cloud-only
    models unless they are permitted.
    """
    key = model_key or DEFAULT_MODEL_KEY
    entry = MODELS.get(key) or MODELS[DEFAULT_MODEL_KEY]

    if entry["cloud"] and not ALLOW_CLOUD:
        raise PermissionError(
            "Cloud models are disabled. Set CRB_ALLOW_CLOUD=true (and a key) to "
            "enable them; your code will leave this machine."
        )

    return entry["id"], entry
