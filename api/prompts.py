"""Language-aware prompt construction and code extraction.

Every prompt is built from the LanguageSpec table, so none of them mention a
specific language by name.
"""

import re

from languages import LanguageSpec

# --- Review modes (analyse existing code) -----------------------------------
EXPLAIN = "explain"
CORRECT = "correct"
COMPLEXITY = "complexity"
DUPLICATION = "duplication"

# --- Writing modes (produce new code) ---------------------------------------
GENERATE = "generate"
COMPLETE = "complete"
TRANSLATE = "translate"
TESTS = "tests"

REVIEW_MODES = {EXPLAIN, CORRECT, COMPLEXITY, DUPLICATION}
WRITING_MODES = {GENERATE, COMPLETE, TRANSLATE, TESTS}
ALL_MODES = REVIEW_MODES | WRITING_MODES

# Modes whose output is a code file and is therefore worth compiling.
VERIFIABLE_MODES = {CORRECT, GENERATE, COMPLETE, TRANSLATE, TESTS}

# Modes that need a natural-language spec rather than (or as well as) code.
SPEC_MODES = {GENERATE}


def _code_only_contract(spec: LanguageSpec) -> str:
    return (
        f"Respond with a single complete {spec.label} source file and nothing "
        f"else. No explanation before or after. Wrap the file in one "
        f"```{spec.highlighter} fenced block. The file must compile as written: "
        f"include every import/header it needs and leave no placeholders or "
        f"TODOs. {spec.entrypoint_hint}\n"
        f"Style requirements: {spec.style_notes}"
    )


def system_prompt(mode: str, spec: LanguageSpec) -> str:
    """The system turn, which sets the model's role for this mode."""
    if mode in WRITING_MODES or mode == CORRECT:
        return (
            f"You are an expert {spec.label} engineer who writes correct, "
            f"idiomatic, compilable code. You are terse and you never pad your "
            f"answers with commentary the user did not ask for."
        )
    return (
        f"You are an expert {spec.label} code reviewer. You are precise, "
        f"concrete, and you cite the specific lines you are talking about."
    )


def build_prompt(
    mode: str,
    spec: LanguageSpec,
    code: str = "",
    user_spec: str = "",
    source_spec: LanguageSpec | None = None,
) -> str:
    """Build the user turn for a given mode."""
    if mode not in ALL_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Supported: {', '.join(sorted(ALL_MODES))}")

    lang = spec.label
    fence = spec.highlighter

    if mode == EXPLAIN:
        return (
            f"Explain the following {lang} code.\n\n"
            f"Cover what it does overall, then walk through the important parts "
            f"in order, then call out anything surprising or risky.\n"
            f"Format your answer as bullet points, one per line, each starting "
            f"with '- '.\n\n"
            f"```{fence}\n{code}\n```"
        )

    if mode == CORRECT:
        return (
            f"Fix every bug and compile error in this {lang} code.\n\n"
            f"Preserve the original intent and public interface. Fix logic errors "
            f"as well as syntax errors.\n\n"
            f"{_code_only_contract(spec)}\n\n"
            f"```{fence}\n{code}\n```"
        )

    if mode == COMPLEXITY:
        return (
            f"Analyse the complexity of this {lang} code and report:\n"
            f"1. Time complexity in Big-O, per function and overall\n"
            f"2. Space complexity\n"
            f"3. Cyclomatic complexity, with the worst offender named\n"
            f"4. Function length and maximum nesting depth\n"
            f"5. Concrete optimisation suggestions\n\n"
            f"Use '#' for section headers and '→' for bullet points.\n\n"
            f"```{fence}\n{code}\n```"
        )

    if mode == DUPLICATION:
        return (
            f"Find duplicated logic in this {lang} code and report:\n"
            f"1. Each duplicated pattern, quoting the repeated lines\n"
            f"2. Where each copy lives\n"
            f"3. The refactor that would remove it\n\n"
            f"If there is no meaningful duplication, say so plainly instead of "
            f"inventing some.\n"
            f"Use '#' for section headers and '→' for bullet points.\n\n"
            f"```{fence}\n{code}\n```"
        )

    if mode == GENERATE:
        request = (
            f"Write {lang} code that satisfies this specification:\n\n"
            f"{user_spec.strip()}\n\n{_code_only_contract(spec)}"
        )
        if code.strip():
            request += (
                f"\n\nUse the following existing code as context or a starting "
                f"point:\n\n```{fence}\n{code}\n```"
            )
        return request

    if mode == COMPLETE:
        return (
            f"Complete this partial {lang} code.\n\n"
            f"Implement every unfinished function, TODO, and stub. Keep the "
            f"existing structure, names, and signatures exactly as they are.\n\n"
            f"{_code_only_contract(spec)}\n\n"
            f"```{fence}\n{code}\n```"
        )

    if mode == TRANSLATE:
        origin = source_spec.label if source_spec else "the source language"
        origin_fence = source_spec.highlighter if source_spec else ""
        return (
            f"Translate this {origin} code into {lang}.\n\n"
            f"Preserve the behaviour exactly. Use {lang} idioms and data "
            f"structures rather than transliterating {origin} line by line.\n\n"
            f"{_code_only_contract(spec)}\n\n"
            f"```{origin_fence}\n{code}\n```"
        )

    # TESTS
    return (
        f"Write unit tests for this {lang} code.\n\n"
        f"Cover the normal path, edge cases, and error handling. Use the "
        f"conventional test framework for {lang}.\n\n"
        f"{_code_only_contract(spec)}\n\n"
        f"```{fence}\n{code}\n```"
    )


def repair_prompt(spec: LanguageSpec, tool: str, output: str) -> str:
    """Follow-up turn that feeds real compiler output back to the model."""
    return (
        f"That code does not compile. `{tool}` reported:\n\n"
        f"```\n{output.strip()}\n```\n\n"
        f"Fix every error above and return the corrected complete file. "
        f"Change as little as possible beyond what is needed to make it "
        f"compile.\n\n{_code_only_contract(spec)}"
    )


_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+#-]*)[ \t]*\r?\n(.*?)```", re.DOTALL)


def extract_code(text: str, spec: LanguageSpec) -> str:
    """Pull the source file out of a model response.

    Prefers a fence tagged with this language, then any fence, then the raw
    text when the model ignored the fencing instruction entirely.
    """
    if not text:
        return ""

    blocks = _FENCE.findall(text)
    if blocks:
        tag_aliases = {spec.highlighter, spec.id, spec.label.lower()}
        for tag, body in blocks:
            if tag.strip().lower() in tag_aliases:
                return body.strip("\n").rstrip()
        # Otherwise take the longest block; models sometimes emit a short
        # example fence alongside the real file.
        return max((b for _, b in blocks), key=len).strip("\n").rstrip()

    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.lstrip("`").strip()
    return stripped
