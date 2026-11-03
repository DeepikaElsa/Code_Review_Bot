"""The generate → verify → repair loop.

A small local model writes code that looks right and often is not. Compiling
it and handing the errors back is the cheapest large quality win available,
so every code-producing mode runs through here.
"""

from typing import Callable, Iterator

import config
import prompts
from languages import LanguageSpec
from llm import chat, chat_stream
from verifier import FAILED, VerificationResult, verify_code


def _temperature(mode: str) -> float:
    return (
        config.REVIEW_TEMPERATURE
        if mode in prompts.REVIEW_MODES and mode != prompts.CORRECT
        else config.GENERATE_TEMPERATURE
    )


def build_messages(
    mode: str,
    spec: LanguageSpec,
    code: str,
    user_spec: str,
    source_spec: LanguageSpec | None,
) -> list[dict]:
    return [
        {"role": "system", "content": prompts.system_prompt(mode, spec)},
        {
            "role": "user",
            "content": prompts.build_prompt(mode, spec, code, user_spec, source_spec),
        },
    ]


def run(
    mode: str,
    spec: LanguageSpec,
    model: str,
    code: str = "",
    user_spec: str = "",
    source_spec: LanguageSpec | None = None,
    emit: Callable[[dict], None] | None = None,
    stream_tokens: bool = False,
    authenticated: bool = False,
) -> dict:
    """Run one request end to end.

    `emit` receives progress events; pass None for a plain blocking call.
    Compilation runs only for authenticated callers (running compilers on
    untrusted input is an execution surface we don't expose anonymously).
    Returns the final payload: result text, extracted code, verification, and
    how many repair passes it took.
    """
    notify = emit or (lambda event: None)
    temperature = _temperature(mode)
    messages = build_messages(mode, spec, code, user_spec, source_spec)

    def complete(stage: str) -> str:
        notify({"type": "status", "stage": stage})
        if not stream_tokens:
            return chat(messages, model, temperature)
        collected = []
        for chunk in chat_stream(messages, model, temperature):
            collected.append(chunk)
            notify({"type": "token", "text": chunk})
        return "".join(collected)

    raw = complete("generating")

    # Analysis modes have no source file to compile; return the prose as-is.
    if mode not in prompts.VERIFIABLE_MODES:
        return {
            "result": raw.strip(),
            "code": "",
            "language": spec.id,
            "mode": mode,
            "model": model,
            "attempts": 1,
            "verification": None,
        }

    extracted = prompts.extract_code(raw, spec)

    # Compilation is gated to authenticated users. Anonymous callers get the
    # generated code, just without the compile-check/repair pass.
    if not authenticated:
        return {
            "result": f"```{spec.highlighter}\n{extracted}\n```" if extracted else raw.strip(),
            "code": extracted,
            "language": spec.id,
            "mode": mode,
            "model": model,
            "attempts": 1,
            "verification": {
                "ok": True,
                "status": "skipped",
                "tool": None,
                "output": "",
                "detail": "Sign in to enable compile verification and auto-repair.",
            },
        }

    verification = verify_code(extracted, spec)
    notify({"type": "verify", "attempt": 1, **verification.to_dict()})

    attempts = 1
    while verification.should_repair and attempts <= config.MAX_REPAIR_ATTEMPTS:
        attempts += 1
        messages = messages + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": prompts.repair_prompt(
                    spec, verification.tool or "the compiler", verification.output
                ),
            },
        ]
        notify({"type": "repair", "attempt": attempts, "reason": verification.detail})

        raw = complete(f"repairing (attempt {attempts})")
        extracted = prompts.extract_code(raw, spec)
        verification = verify_code(extracted, spec)
        notify({"type": "verify", "attempt": attempts, **verification.to_dict()})

    fenced = f"```{spec.highlighter}\n{extracted}\n```" if extracted else raw.strip()

    return {
        "result": fenced,
        "code": extracted,
        "language": spec.id,
        "mode": mode,
        "model": model,
        "attempts": attempts,
        "verification": verification.to_dict(),
    }


def run_streaming(**kwargs) -> Iterator[dict]:
    """Same as run(), yielded as a stream of events ending with a 'done'."""
    queue: list[dict] = []
    kwargs["emit"] = queue.append
    kwargs["stream_tokens"] = True

    # Generator-in-a-callback: drain whatever the pipeline has emitted between
    # yields. The pipeline is synchronous, so this stays in order.
    import threading

    outcome: dict = {}
    failure: list[Exception] = []

    def work():
        try:
            outcome.update(run(**kwargs))
        except Exception as exc:  # surfaced to the client as an error event
            failure.append(exc)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()

    while thread.is_alive() or queue:
        while queue:
            yield queue.pop(0)
        if thread.is_alive():
            thread.join(timeout=0.05)

    if failure:
        yield {"type": "error", "message": str(failure[0])}
    else:
        yield {"type": "done", **outcome}
