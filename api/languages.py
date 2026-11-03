"""Per-language knowledge: file naming, compilers, and style guidance.

Adding a fourth language means adding one LanguageSpec here; nothing else in
the backend hardcodes a language.
"""

import re
import shutil
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class LanguageSpec:
    id: str
    label: str
    extension: str
    highlighter: str          # react-syntax-highlighter language name
    line_comment: str
    style_notes: str
    entrypoint_hint: str
    # Tool that must be on PATH for verification, and the command builder.
    compiler: str | None = None
    compile_args: Callable[[str, str], list[str]] = field(default=None, repr=False)
    filename_for: Callable[[str], str] = field(default=None, repr=False)


def _python_filename(code: str) -> str:
    return "main.py"


def _c_filename(code: str) -> str:
    return "main.c"


_JAVA_PUBLIC_TYPE = re.compile(
    r"\bpublic\s+(?:final\s+|abstract\s+|static\s+|sealed\s+)*"
    r"(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)"
)
_JAVA_ANY_TYPE = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)")


def _java_filename(code: str) -> str:
    """javac requires the file name to match the public type name."""
    match = _JAVA_PUBLIC_TYPE.search(code) or _JAVA_ANY_TYPE.search(code)
    return f"{match.group(1)}.java" if match else "Main.java"


LANGUAGES: dict[str, LanguageSpec] = {
    "python": LanguageSpec(
        id="python",
        label="Python",
        extension=".py",
        highlighter="python",
        line_comment="#",
        style_notes=(
            "Follow PEP 8. Use type hints, docstrings, f-strings, and specific "
            "exception types rather than bare 'except:'. Prefer the standard "
            "library over third-party packages."
        ),
        entrypoint_hint="Guard executable code with `if __name__ == \"__main__\":`.",
        compiler="python",
        compile_args=lambda exe, path: [exe, "-m", "py_compile", path],
        filename_for=_python_filename,
    ),
    "c": LanguageSpec(
        id="c",
        label="C",
        extension=".c",
        highlighter="c",
        line_comment="//",
        style_notes=(
            "Target C11. Include every header you use. Check the return value of "
            "malloc/calloc, free everything you allocate, avoid gets/strcpy in "
            "favour of bounded alternatives, and never return a pointer to a local."
        ),
        entrypoint_hint="Provide `int main(void)` returning 0 on success.",
        compiler="gcc",
        compile_args=lambda exe, path: [
            exe, "-fsyntax-only", "-std=c11", "-Wall", "-Wextra", path
        ],
        filename_for=_c_filename,
    ),
    "java": LanguageSpec(
        id="java",
        label="Java",
        extension=".java",
        highlighter="java",
        line_comment="//",
        style_notes=(
            "Target Java 17. Put everything in one file with a single public "
            "class and no package declaration. Use generics, prefer List/Map "
            "interfaces over concrete types, and catch specific exceptions."
        ),
        entrypoint_hint="Provide `public static void main(String[] args)`.",
        compiler="javac",
        compile_args=lambda exe, path: [exe, "-Xlint:all", path],
        filename_for=_java_filename,
    ),
}

DEFAULT_LANGUAGE = "python"


def get_language(language_id: str | None) -> LanguageSpec:
    """Look up a language, raising ValueError for anything unsupported."""
    key = (language_id or DEFAULT_LANGUAGE).strip().lower()
    if key not in LANGUAGES:
        supported = ", ".join(sorted(LANGUAGES))
        raise ValueError(f"Unsupported language '{language_id}'. Supported: {supported}")
    return LANGUAGES[key]


def toolchain_path(spec: LanguageSpec) -> str | None:
    """Absolute path to this language's compiler, or None if not installed."""
    if not spec.compiler:
        return None
    if spec.compiler == "python":
        import sys
        return sys.executable
    return shutil.which(spec.compiler)


def toolchain_report() -> dict[str, dict]:
    """Which verifiers are actually usable on this machine."""
    report = {}
    for key, spec in LANGUAGES.items():
        path = toolchain_path(spec)
        report[key] = {
            "label": spec.label,
            "compiler": spec.compiler,
            "available": path is not None,
            "path": path,
        }
    return report
