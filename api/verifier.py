"""Compile-checks generated code so the model can be told what it got wrong.

This is the quality multiplier: a small local model writes plausible-looking
code, the real compiler rejects it, and the error text goes back into the
conversation for a repair pass.

Safety note: generated code is COMPILED, never executed. gcc runs with
-fsyntax-only and javac only emits class files into a temp directory that is
deleted immediately afterwards.
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass, asdict

from config import COMPILE_MEMORY_MB, COMPILE_TIMEOUT, VERIFY_ENABLED
from languages import LanguageSpec, toolchain_path

MAX_OUTPUT_CHARS = 4000


def _rlimit_preexec():
    """Cap CPU time and address space for the compiler child (POSIX only).

    A hosted backend compiles untrusted input; these limits stop a pathological
    input from exhausting the host even before the wall-clock timeout fires.
    Returns None on platforms without os.setrlimit (e.g. Windows), where
    subprocess ignores preexec_fn anyway.
    """
    try:
        import resource
    except ImportError:
        return None

    def _apply():
        cpu = max(1, COMPILE_TIMEOUT)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        if COMPILE_MEMORY_MB > 0:
            nbytes = COMPILE_MEMORY_MB * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (nbytes, nbytes))

    return _apply

# Verification outcomes.
PASSED = "passed"           # compiler accepted it
FAILED = "failed"           # compiler rejected it -> worth a repair pass
UNAVAILABLE = "unavailable"  # compiler not installed on this machine
SKIPPED = "skipped"         # nothing to check, or verification switched off
ERROR = "error"             # the verifier itself broke


@dataclass
class VerificationResult:
    ok: bool
    status: str
    tool: str | None
    output: str
    detail: str

    @property
    def should_repair(self) -> bool:
        return self.status == FAILED

    def to_dict(self) -> dict:
        return asdict(self)


def _truncate(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n... (output truncated)"


def _scrub(text: str, workdir: str, filename: str) -> str:
    """Strip temp-directory paths so errors read cleanly and stay portable."""
    if not text:
        return ""
    for variant in {workdir, workdir.replace("\\", "/"), os.path.realpath(workdir)}:
        text = text.replace(os.path.join(variant, filename), filename)
        text = text.replace(variant + os.sep, "")
        text = text.replace(variant + "/", "")
        text = text.replace(variant, "")
    return text


def verify_code(code: str, spec: LanguageSpec) -> VerificationResult:
    """Compile `code` as `spec` and report whether the toolchain accepted it."""
    if not VERIFY_ENABLED:
        return VerificationResult(
            True, SKIPPED, None, "", "Verification disabled (CRB_VERIFY=false)."
        )

    if not code or not code.strip():
        return VerificationResult(
            True, SKIPPED, None, "", "No code produced, nothing to verify."
        )

    exe = toolchain_path(spec)
    if not exe:
        return VerificationResult(
            True,
            UNAVAILABLE,
            spec.compiler,
            "",
            f"'{spec.compiler}' is not on PATH, so {spec.label} code could not be "
            f"compile-checked. Install it to enable automatic verification.",
        )

    with tempfile.TemporaryDirectory(prefix="crb_verify_") as workdir:
        filename = spec.filename_for(code)
        path = os.path.join(workdir, filename)

        try:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(code)

            completed = subprocess.run(
                spec.compile_args(exe, path),
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=COMPILE_TIMEOUT,
                encoding="utf-8",
                errors="replace",
                preexec_fn=_rlimit_preexec() if os.name == "posix" else None,
                env={"PATH": os.environ.get("PATH", ""), "HOME": workdir},
            )
        except subprocess.TimeoutExpired:
            return VerificationResult(
                False,
                FAILED,
                spec.compiler,
                f"Compilation timed out after {COMPILE_TIMEOUT}s.",
                "The compiler did not finish in time.",
            )
        except OSError as exc:
            return VerificationResult(
                True, ERROR, spec.compiler, str(exc), "Could not run the compiler."
            )

        stream = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        stream = _truncate(_scrub(stream, workdir, filename))

    if completed.returncode == 0:
        extra = _python_lint(code) if spec.id == "python" else ""
        if extra:
            return VerificationResult(
                False,
                FAILED,
                "pyflakes",
                _truncate(extra),
                "Compiles, but static analysis found problems.",
            )
        detail = f"{spec.label} code compiles cleanly."
        if stream:
            detail += " Compiler emitted warnings."
        return VerificationResult(True, PASSED, spec.compiler, stream, detail)

    return VerificationResult(
        False,
        FAILED,
        spec.compiler,
        stream or f"{spec.compiler} exited with code {completed.returncode}.",
        f"{spec.label} code failed to compile.",
    )


def _python_lint(code: str) -> str:
    """Optional pyflakes pass. py_compile only catches syntax errors, so this
    adds undefined names and unused imports. Silently skipped if not installed.
    """
    try:
        import io
        from pyflakes.api import check
        from pyflakes.reporter import Reporter
    except ImportError:
        return ""

    out, err = io.StringIO(), io.StringIO()
    try:
        problems = check(code, "main.py", Reporter(out, err))
    except Exception:
        return ""

    return out.getvalue().strip() if problems else ""
