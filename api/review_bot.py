"""Backwards-compatible shim.

The original review_code(prompt) lived here and called Ollama's legacy
/api/generate endpoint directly. That logic now lives in llm.py (transport)
and pipeline.py (the verify-and-repair loop). This wrapper is kept so any
older script or notebook that imports review_code keeps working.
"""

import config
from llm import LLMError, chat


def review_code(prompt: str, model: str | None = None) -> str:
    """Send a raw prompt to the configured model and return its text."""
    target = model or config.MODELS[config.DEFAULT_MODEL_KEY]["id"]
    try:
        return chat(
            [{"role": "user", "content": prompt}],
            target,
            config.REVIEW_TEMPERATURE,
        )
    except LLMError as exc:
        return str(exc)
