"""
Assignment 1.2: Rule-Based Environmental Reasoner
Theme: CodeReviewBot as a Simple Reflex Agent

Architecture (Unit-1 agent loop):
    Environment (mock code-change stream)
        -> Sensors   (parse raw telemetry into a percept)
        -> Condition-Action rules (no memory, no planning: simple reflex)
        -> Actuators (trigger a review mode and log the reaction)

The agent is "simple reflex": it decides ONLY from the current percept,
using if-condition-then-action rules, exactly like the core agent
reasoning loop in Unit-1.
"""

import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional


# ---------------------------------------------------------------------------
# 1. PERCEPT: what the agent "senses" after parsing one telemetry packet
# ---------------------------------------------------------------------------
@dataclass
class Percept:
    commit_id: str
    file_name: str
    lines_changed: int
    complexity: int        # cyclomatic complexity of the changed code
    has_tests: bool        # were tests included in this change?
    secret_found: bool     # hardcoded key/password pattern detected
    doc_coverage: float    # fraction of functions with docstrings (0 to 1)
    nested_loops: int      # depth of nested loops
    style_violations: int  # linter warnings


# ---------------------------------------------------------------------------
# 2. ENVIRONMENT: mock live telemetry stream (a generator)
# ---------------------------------------------------------------------------
def telemetry_stream(n_events: int, seed: int = 42):
    """Mocks a live feed of code-change telemetry as raw strings.

    Each packet is a raw 'key=value;' string, like a real sensor line,
    so the agent has something genuine to parse.
    """
    rng = random.Random(seed)  # fixed seed so the log is reproducible
    files = ["auth.py", "db_utils.py", "api_routes.py", "parser.py",
             "stream_handler.py", "config.py", "ui_render.py"]
    for i in range(1, n_events + 1):
        packet = (
            f"commit=C{i:03d};file={rng.choice(files)};"
            f"lines={rng.randint(5, 600)};"
            f"complexity={rng.randint(1, 25)};"
            f"tests={rng.choice(['yes', 'no'])};"
            f"secret={'yes' if rng.random() < 0.15 else 'no'};"
            f"docs={rng.random():.2f};"
            f"loops={rng.randint(0, 4)};"
            f"style={rng.randint(0, 20)}"
        )
        # Occasionally inject a corrupted packet to test the parser
        if i % 9 == 0:
            packet = "commit=C%03d;file=???;lines=abc;;corrupt" % i
        yield packet
        time.sleep(0.01)  # simulates the live-stream delay


# ---------------------------------------------------------------------------
# 3. SENSOR: parsing logic (raw string -> Percept)
# ---------------------------------------------------------------------------
def parse_telemetry(raw: str) -> Optional[Percept]:
    """Parses a raw telemetry string into a Percept.

    Returns None if the packet is malformed, so the agent can ignore
    bad sensor readings instead of crashing.
    """
    try:
        # Split 'a=1;b=2' into a dict, skipping empty fragments
        fields = dict(
            pair.split("=", 1) for pair in raw.split(";") if "=" in pair
        )
        return Percept(
            commit_id=fields["commit"],
            file_name=fields["file"],
            lines_changed=int(fields["lines"]),
            complexity=int(fields["complexity"]),
            has_tests=(fields["tests"] == "yes"),
            secret_found=(fields["secret"] == "yes"),
            doc_coverage=float(fields["docs"]),
            nested_loops=int(fields["loops"]),
            style_violations=int(fields["style"]),
        )
    except (KeyError, ValueError):
        # Missing field or non-numeric value: sensor fault
        return None


# ---------------------------------------------------------------------------
# 4. RULES: Condition -> Action pairs
# ---------------------------------------------------------------------------
@dataclass
class Rule:
    name: str
    condition: Callable[[Percept], bool]   # the "IF" part
    action: str                            # the review mode to trigger
    severity: str                          # CRITICAL / HIGH / MEDIUM / LOW
    message: Callable[[Percept], str]      # reactive log text


# Rules are ordered by priority: security first, style last.
RULES: List[Rule] = [
    Rule("R1_SECRET_LEAK",
         lambda p: p.secret_found,
         "SECURITY_REVIEW", "CRITICAL",
         lambda p: f"Hardcoded secret detected in {p.file_name}. Block merge."),
    Rule("R2_HIGH_COMPLEXITY",
         lambda p: p.complexity > 15,
         "COMPLEXITY_REVIEW", "HIGH",
         lambda p: f"Complexity {p.complexity} in {p.file_name}. Suggest refactor."),
    Rule("R3_PERFORMANCE_RISK",
         lambda p: p.nested_loops >= 3,
         "PERFORMANCE_REVIEW", "HIGH",
         lambda p: f"{p.nested_loops} nested loops in {p.file_name}. Possible O(n^{p.nested_loops})."),
    Rule("R4_UNTESTED_BIG_CHANGE",
         lambda p: p.lines_changed > 300 and not p.has_tests,
         "BUG_DETECTION_REVIEW", "HIGH",
         lambda p: f"{p.lines_changed} lines changed with no tests in {p.file_name}."),
    Rule("R5_LOW_DOCS",
         lambda p: p.doc_coverage < 0.30,
         "DOCUMENTATION_REVIEW", "MEDIUM",
         lambda p: f"Docstring coverage {p.doc_coverage:.0%} in {p.file_name}."),
    Rule("R6_STYLE_NOISE",
         lambda p: p.style_violations > 10,
         "STYLE_REVIEW", "LOW",
         lambda p: f"{p.style_violations} style violations in {p.file_name}."),
]


# ---------------------------------------------------------------------------
# 5. AGENT: the perceive -> decide -> act loop
# ---------------------------------------------------------------------------
class SimpleReflexReviewAgent:
    """Simple reflex agent: acts only on the current percept (no memory
    used for decisions; counters below are only for the final report)."""

    def __init__(self, rules: List[Rule]):
        self.rules = rules
        self.stats = {"packets": 0, "bad_packets": 0, "actions": 0, "clean": 0}
        self.action_counts = {}

    def log(self, level: str, text: str):
        """Actuator: writes a timestamped reactive log line to the console."""
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{stamp}] [{level:<8}] {text}")

    def decide(self, percept: Percept) -> List[Rule]:
        """Reflex step: return every rule whose condition matches."""
        return [r for r in self.rules if r.condition(percept)]

    def step(self, raw: str):
        """One full cycle of the agent loop for a single packet."""
        self.stats["packets"] += 1

        # SENSE
        percept = parse_telemetry(raw)
        if percept is None:
            self.stats["bad_packets"] += 1
            self.log("WARN", f"Malformed telemetry ignored: '{raw}'")
            return

        self.log("SENSE", f"{percept.commit_id} {percept.file_name} "
                          f"lines={percept.lines_changed} cx={percept.complexity} "
                          f"tests={percept.has_tests} docs={percept.doc_coverage:.0%}")

        # DECIDE
        fired = self.decide(percept)

        # ACT
        if not fired:
            self.stats["clean"] += 1
            self.log("OK", f"{percept.commit_id}: no rule fired. Code looks clean.")
            return

        for rule in fired:
            self.stats["actions"] += 1
            self.action_counts[rule.action] = self.action_counts.get(rule.action, 0) + 1
            self.log(rule.severity,
                     f"{rule.name} -> trigger {rule.action}: {rule.message(percept)}")

    def run(self, stream):
        """Main loop: keep sensing until the stream ends."""
        print("=" * 78)
        print(" CodeReviewBot Rule-Based Environmental Reasoner (Simple Reflex Agent)")
        print("=" * 78)
        for raw in stream:
            self.step(raw)
            print("-" * 78)
        self.report()

    def report(self):
        """Final summary of what the agent did."""
        print("=" * 78)
        print(" EXECUTION SUMMARY")
        print("=" * 78)
        print(f" Packets received   : {self.stats['packets']}")
        print(f" Malformed packets  : {self.stats['bad_packets']}")
        print(f" Clean commits      : {self.stats['clean']}")
        print(f" Actions triggered  : {self.stats['actions']}")
        for mode, count in sorted(self.action_counts.items()):
            print(f"   - {mode:<22}: {count}")


# ---------------------------------------------------------------------------
# 6. ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    agent = SimpleReflexReviewAgent(RULES)
    agent.run(telemetry_stream(n_events=12))
