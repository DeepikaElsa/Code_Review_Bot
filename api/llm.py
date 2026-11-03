"""LLM transport, provider-agnostic.

Two backends behind one interface, chosen by config.PROVIDER:
  - "ollama"  -> Ollama /api/chat  (local, or Ollama Cloud at https://ollama.com)
  - "openai"  -> OpenAI-compatible /chat/completions (Groq, OpenRouter, OpenAI)

The verify-and-repair loop needs multi-turn chat, so both use chat endpoints.
"""

import json
from typing import Iterator

import requests

import config

# --- Ollama endpoints --------------------------------------------------------
OLLAMA_CHAT_URL = f"{config.OLLAMA_HOST}/api/chat"
OLLAMA_TAGS_URL = f"{config.OLLAMA_HOST}/api/tags"

# --- OpenAI-compatible endpoint ---------------------------------------------
OPENAI_CHAT_URL = f"{config.OPENAI_BASE_URL}/chat/completions"


class LLMError(RuntimeError):
    """Raised with a message that is safe and useful to show the user."""


def _explain_failure(exc: Exception, model: str, host: str) -> str:
    if isinstance(exc, requests.exceptions.ConnectionError):
        return f"Could not reach the model provider at {host}."
    if isinstance(exc, requests.exceptions.Timeout):
        return (
            f"'{model}' did not respond within {config.REQUEST_TIMEOUT}s. Try a "
            f"smaller model or a shorter request."
        )
    if isinstance(exc, requests.exceptions.HTTPError):
        response = exc.response
        status = response.status_code if response is not None else "?"
        if status == 404:
            return f"Model '{model}' was not found by the provider."
        if status in (401, 403):
            return "The provider rejected the API key. Check your inference key."
        if status == 429:
            return "Rate limited by the provider. Wait a moment and try again."
        body = (response.text or "")[:300] if response is not None else ""
        return f"Provider returned HTTP {status}: {body}"
    return f"Request to the model provider failed: {exc}"


# ============================================================================
# Ollama transport
# ============================================================================

def _ollama_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if config.OLLAMA_API_KEY:  # only Ollama Cloud needs this
        headers["Authorization"] = f"Bearer {config.OLLAMA_API_KEY}"
    return headers


def _ollama_payload(messages, model, temperature, stream) -> dict:
    return {
        "model": model,
        "messages": messages,
        "stream": stream,
        # These belong under "options"; at the top level Ollama ignores them.
        "options": {
            "temperature": temperature,
            "num_ctx": config.NUM_CTX,
            "top_p": 0.9,
            "repeat_penalty": 1.05,
        },
    }


def _ollama_chat(messages, model, temperature) -> str:
    try:
        response = requests.post(
            OLLAMA_CHAT_URL,
            json=_ollama_payload(messages, model, temperature, False),
            headers=_ollama_headers(),
            timeout=config.REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        raise LLMError(_explain_failure(exc, model, config.OLLAMA_HOST)) from exc
    except ValueError as exc:
        raise LLMError(f"Provider returned malformed JSON: {exc}") from exc

    if "error" in data:
        raise LLMError(str(data["error"]))
    return (data.get("message") or {}).get("content", "")


def _ollama_stream(messages, model, temperature) -> Iterator[str]:
    try:
        with requests.post(
            OLLAMA_CHAT_URL,
            json=_ollama_payload(messages, model, temperature, True),
            headers=_ollama_headers(),
            timeout=config.REQUEST_TIMEOUT,
            stream=True,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if "error" in event:
                    raise LLMError(str(event["error"]))
                chunk = (event.get("message") or {}).get("content", "")
                if chunk:
                    yield chunk
                if event.get("done"):
                    break
    except requests.exceptions.RequestException as exc:
        raise LLMError(_explain_failure(exc, model, config.OLLAMA_HOST)) from exc


# ============================================================================
# OpenAI-compatible transport
# ============================================================================

def _openai_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
    }


def _openai_payload(messages, model, temperature, stream) -> dict:
    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.9,
        "stream": stream,
    }


def _openai_chat(messages, model, temperature) -> str:
    if not config.OPENAI_API_KEY:
        raise LLMError("No inference API key configured (OPENAI_API_KEY).")
    try:
        response = requests.post(
            OPENAI_CHAT_URL,
            json=_openai_payload(messages, model, temperature, False),
            headers=_openai_headers(),
            timeout=config.REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        raise LLMError(_explain_failure(exc, model, config.OPENAI_BASE_URL)) from exc
    except ValueError as exc:
        raise LLMError(f"Provider returned malformed JSON: {exc}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise LLMError(str(data.get("error", "Provider returned no choices.")))
    return (choices[0].get("message") or {}).get("content", "")


def _openai_stream(messages, model, temperature) -> Iterator[str]:
    if not config.OPENAI_API_KEY:
        raise LLMError("No inference API key configured (OPENAI_API_KEY).")
    try:
        with requests.post(
            OPENAI_CHAT_URL,
            json=_openai_payload(messages, model, temperature, True),
            headers=_openai_headers(),
            timeout=config.REQUEST_TIMEOUT,
            stream=True,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                except ValueError:
                    continue
                choices = event.get("choices") or []
                if not choices:
                    continue
                chunk = (choices[0].get("delta") or {}).get("content", "")
                if chunk:
                    yield chunk
    except requests.exceptions.RequestException as exc:
        raise LLMError(_explain_failure(exc, model, config.OPENAI_BASE_URL)) from exc


# ============================================================================
# Public interface (dispatches on provider)
# ============================================================================

def chat(messages: list[dict], model: str, temperature: float | None = None) -> str:
    temperature = config.GENERATE_TEMPERATURE if temperature is None else temperature
    if config.PROVIDER == "openai":
        return _openai_chat(messages, model, temperature)
    return _ollama_chat(messages, model, temperature)


def chat_stream(
    messages: list[dict], model: str, temperature: float | None = None
) -> Iterator[str]:
    temperature = config.GENERATE_TEMPERATURE if temperature is None else temperature
    if config.PROVIDER == "openai":
        yield from _openai_stream(messages, model, temperature)
    else:
        yield from _ollama_stream(messages, model, temperature)


def installed_models() -> list[str]:
    """Model names the provider can serve right now.

    For a hosted OpenAI-compatible provider we don't probe (listing isn't
    uniform); we trust the configured ids. For Ollama we query /api/tags.
    """
    if config.PROVIDER == "openai":
        return [entry["id"] for entry in config.MODELS.values()]
    try:
        response = requests.get(OLLAMA_TAGS_URL, headers=_ollama_headers(), timeout=5)
        response.raise_for_status()
        return [m.get("name", "") for m in response.json().get("models", [])]
    except (requests.exceptions.RequestException, ValueError):
        return []
