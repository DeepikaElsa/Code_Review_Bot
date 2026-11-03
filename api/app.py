"""Flask API for CodeReviewBot.

Endpoints:
  POST /api/generate  NDJSON stream of progress events (tokens, verify, done)
  POST /api/review    blocking JSON, one response when finished
  GET  /api/health    provider/auth/toolchain status
  GET  /api/models    configured models and whether each is usable
  GET  /api/languages supported languages and verifier status
  GET  /api/me        the authenticated user (or 401)

Auth: when CRB_REQUIRE_AUTH is on, /api/generate and /api/review require a
valid Supabase access token (Authorization: Bearer). The verify-and-repair
loop runs only for authenticated callers.
"""

import json

from flask import Flask, Response, jsonify, request, stream_with_context

import config
import pipeline
import prompts
from auth import AuthError, authenticate
from languages import LANGUAGES, get_language, toolchain_report
from llm import LLMError, installed_models

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    allowed = config.CORS_ORIGINS
    if "*" in allowed:
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif origin in allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


class BadRequest(Exception):
    """A client error with a message worth showing the user."""


def parse_request(body: dict, authenticated: bool) -> dict:
    """Validate the request body and resolve it into pipeline arguments."""
    if not isinstance(body, dict):
        raise BadRequest("Request body must be a JSON object.")

    mode = (body.get("mode") or "").strip().lower()
    if mode not in prompts.ALL_MODES:
        raise BadRequest(
            f"Invalid mode '{mode}'. Supported: {', '.join(sorted(prompts.ALL_MODES))}"
        )

    code = body.get("code") or ""
    user_spec = body.get("spec") or ""

    if mode in prompts.SPEC_MODES:
        if not user_spec.strip():
            raise BadRequest("Describe what you want built in the specification field.")
    elif not code.strip():
        raise BadRequest("No code supplied.")

    if len(code) > config.MAX_CODE_CHARS or len(user_spec) > config.MAX_CODE_CHARS:
        raise BadRequest(
            f"Input too large; the limit is {config.MAX_CODE_CHARS} characters."
        )

    try:
        spec = get_language(body.get("language"))
        source_spec = (
            get_language(body.get("sourceLanguage"))
            if mode == prompts.TRANSLATE and body.get("sourceLanguage")
            else None
        )
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc

    if mode == prompts.TRANSLATE and source_spec and source_spec.id == spec.id:
        raise BadRequest("Pick a different target language to translate into.")

    try:
        model, _entry = config.resolve_model(body.get("model"))
    except PermissionError as exc:
        raise BadRequest(str(exc)) from exc

    return {
        "mode": mode,
        "spec": spec,
        "model": model,
        "code": code,
        "user_spec": user_spec,
        "source_spec": source_spec,
        "authenticated": authenticated,
    }


def _prepare():
    """Shared auth + parse for the two POST endpoints. Returns pipeline args."""
    user = authenticate(request)  # raises AuthError -> handled by caller
    return parse_request(request.get_json(silent=True), authenticated=user is not None)


@app.route("/api/review", methods=["POST", "OPTIONS"])
def review():
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        args = _prepare()
    except AuthError as exc:
        return jsonify({"error": exc.message}), exc.status
    except BadRequest as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        return jsonify(pipeline.run(**args))
    except LLMError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Unhandled error in /api/review")
        return jsonify({"error": f"Unexpected server error: {exc}"}), 500


@app.route("/api/generate", methods=["POST", "OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        args = _prepare()
    except AuthError as exc:
        return jsonify({"error": exc.message}), exc.status
    except BadRequest as exc:
        return jsonify({"error": str(exc)}), 400

    def events():
        try:
            for event in pipeline.run_streaming(**args):
                yield json.dumps(event) + "\n"
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Unhandled error in /api/generate")
            yield json.dumps({"type": "error", "message": str(exc)}) + "\n"

    response = Response(stream_with_context(events()), mimetype="application/x-ndjson")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@app.route("/api/me", methods=["GET"])
def me():
    try:
        user = authenticate(request)
    except AuthError as exc:
        return jsonify({"error": exc.message}), exc.status
    if user is None:
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "user": user})


@app.route("/api/health", methods=["GET"])
def health():
    local = installed_models()
    configured = {key: entry["id"] for key, entry in config.MODELS.items()}

    return jsonify(
        {
            "status": "ok" if local else "provider_unreachable",
            "provider": config.PROVIDER,
            "remoteInference": config.REMOTE_INFERENCE,
            "requireAuth": config.REQUIRE_AUTH,
            "installedModels": local,
            "configuredModels": configured,
            "missingModels": [
                model_id
                for key, model_id in configured.items()
                if not config.MODELS[key]["cloud"] and model_id not in local
            ],
            "verifyEnabled": config.VERIFY_ENABLED,
            "toolchains": toolchain_report(),
        }
    )


@app.route("/api/languages", methods=["GET"])
def languages():
    tools = toolchain_report()
    return jsonify(
        [
            {
                "id": spec.id,
                "label": spec.label,
                "extension": spec.extension,
                "highlighter": spec.highlighter,
                "verifierAvailable": tools[spec.id]["available"],
                "compiler": spec.compiler,
            }
            for spec in LANGUAGES.values()
        ]
    )


@app.route("/api/models", methods=["GET"])
def models():
    local = installed_models()
    return jsonify(
        [
            {
                "key": key,
                "label": entry["label"],
                "description": entry["description"],
                "cloud": entry["cloud"],
                "id": entry["id"],
                "available": (
                    config.ALLOW_CLOUD if entry["cloud"] else entry["id"] in local
                ),
                "default": key == config.DEFAULT_MODEL_KEY,
            }
            for key, entry in config.MODELS.items()
        ]
    )


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)
