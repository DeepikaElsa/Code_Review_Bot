"""
Assignment 1.2: Rule-Based Environmental Reasoner
Project: Local AI Code Review Bot

Objective:
Implement a simple reflex agent that receives incoming
source-code telemetry, parses it, evaluates condition-action
rules, and produces automated reactive review logs.

The source code acts as the agent's environment.
The agent perceives measurable properties of the code and
reacts according to predefined rules.
"""

from dataclasses import dataclass
from typing import List


# ============================================================
# 1. SENSOR DATA / TELEMETRY
# ============================================================

@dataclass
class CodeTelemetry:
    """
    Represents the sensory information perceived by the agent
    from an incoming source-code stream.
    """

    total_lines: int
    blank_lines: int
    comment_lines: int
    long_lines: int
    todo_count: int
    print_count: int
    bare_except_count: int
    function_count: int
    class_count: int


# ============================================================
# 2. CONDITION-ACTION RULE
# ============================================================

@dataclass
class Rule:
    """
    Represents a simple condition-action rule.

    If the condition is true:
        IF condition
        THEN action
    """

    name: str
    condition: callable
    action: str


# ============================================================
# 3. SENSOR / PARSER
# ============================================================

class CodeSensor:
    """
    Parses incoming source code and converts it into
    structured telemetry.
    """

    def sense(self, code: str) -> CodeTelemetry:

        lines = code.splitlines()

        total_lines = len(lines)

        blank_lines = sum(
            1 for line in lines
            if not line.strip()
        )

        comment_lines = sum(
            1 for line in lines
            if line.strip().startswith("#")
        )

        long_lines = sum(
            1 for line in lines
            if len(line) > 79
        )

        todo_count = sum(
            1 for line in lines
            if "TODO" in line.upper()
        )

        print_count = sum(
            1 for line in lines
            if "print(" in line
        )

        bare_except_count = sum(
            1 for line in lines
            if line.strip() == "except:"
        )

        function_count = sum(
            1 for line in lines
            if line.strip().startswith("def ")
        )

        class_count = sum(
            1 for line in lines
            if line.strip().startswith("class ")
        )

        return CodeTelemetry(
            total_lines=total_lines,
            blank_lines=blank_lines,
            comment_lines=comment_lines,
            long_lines=long_lines,
            todo_count=todo_count,
            print_count=print_count,
            bare_except_count=bare_except_count,
            function_count=function_count,
            class_count=class_count
        )


# ============================================================
# 4. SIMPLE REFLEX AGENT
# ============================================================

class CodeReviewReflexAgent:
    """
    Simple reflex agent.

    It does not maintain complex internal reasoning.
    It simply maps perceived telemetry to actions using
    predefined condition-action rules.
    """

    def __init__(self):

        self.rules = [
            Rule(
                name="Long Line Detection",
                condition=lambda t: t.long_lines > 0,
                action=(
                    "WARNING: Long lines detected. "
                    "Consider following the PEP 8 line-length guideline."
                )
            ),

            Rule(
                name="TODO Detection",
                condition=lambda t: t.todo_count > 0,
                action=(
                    "ACTION: TODO comments detected. "
                    "Complete or track unfinished tasks."
                )
            ),

            Rule(
                name="Debug Print Detection",
                condition=lambda t: t.print_count > 0,
                action=(
                    "WARNING: print() statements detected. "
                    "Consider using logging for production code."
                )
            ),

            Rule(
                name="Bare Exception Detection",
                condition=lambda t: t.bare_except_count > 0,
                action=(
                    "CRITICAL: Bare 'except:' detected. "
                    "Catch specific exceptions instead."
                )
            ),

            Rule(
                name="Missing Comments",
                condition=lambda t: (
                    t.total_lines > 10
                    and t.comment_lines == 0
                ),
                action=(
                    "SUGGESTION: No comments detected in a relatively "
                    "large code block. Consider adding documentation."
                )
            ),

            Rule(
                name="Function Detection",
                condition=lambda t: t.function_count > 0,
                action=(
                    "PASS: Functions detected. "
                    "Code contains reusable functional components."
                )
            ),

            Rule(
                name="Class Detection",
                condition=lambda t: t.class_count > 0,
                action=(
                    "PASS: Class structure detected. "
                    "Object-oriented organization is present."
                )
            ),

            Rule(
                name="Clean Code",
                condition=lambda t: (
                    t.long_lines == 0
                    and t.todo_count == 0
                    and t.bare_except_count == 0
                ),
                action=(
                    "PASS: No major rule violations detected."
                )
            )
        ]


    def evaluate(self, telemetry: CodeTelemetry) -> List[str]:
        """
        Evaluate all condition-action rules against the
        perceived telemetry.
        """

        actions = []

        for rule in self.rules:

            if rule.condition(telemetry):

                actions.append(
                    f"[TRIGGERED] {rule.name} -> {rule.action}"
                )

        return actions


# ============================================================
# 5. REACTIVE LOGGING
# ============================================================

def print_telemetry(telemetry: CodeTelemetry):
    """
    Displays the sensory data perceived by the agent.
    """

    print("\n--- SENSOR TELEMETRY ---")
    print(f"Total lines       : {telemetry.total_lines}")
    print(f"Blank lines       : {telemetry.blank_lines}")
    print(f"Comment lines     : {telemetry.comment_lines}")
    print(f"Long lines        : {telemetry.long_lines}")
    print(f"TODO count        : {telemetry.todo_count}")
    print(f"print() count     : {telemetry.print_count}")
    print(f"Bare except count : {telemetry.bare_except_count}")
    print(f"Functions         : {telemetry.function_count}")
    print(f"Classes           : {telemetry.class_count}")


def review_code(agent, sensor, code, stream_id):
    """
    Processes one incoming code sample from the mock
    live data stream.
    """

    print("\n" + "=" * 65)
    print(f"INCOMING CODE STREAM #{stream_id}")
    print("=" * 65)

    telemetry = sensor.sense(code)

    print_telemetry(telemetry)

    print("\n--- CONDITION-ACTION ENGINE ---")

    actions = agent.evaluate(telemetry)

    if actions:

        for action in actions:
            print(action)

    else:
        print("[NO ACTION] No rules were triggered.")


# ============================================================
# 6. MOCK LIVE ENVIRONMENTAL DATA STREAM
# ============================================================

def main():

    print("=" * 65)
    print("RULE-BASED ENVIRONMENTAL REASONER")
    print("CODE REVIEW BOT - SIMPLE REFLEX AGENT")
    print("=" * 65)

    sensor = CodeSensor()
    agent = CodeReviewReflexAgent()

    # --------------------------------------------------------
    # Mock incoming source-code stream
    # Each element represents a new piece of code submitted
    # to the Code Review Bot.
    # --------------------------------------------------------

    code_stream = [

        """
def calculate_sum(a, b):
    return a + b
""",

        """
def process_data(data):
    # TODO: optimize this function
    print("Processing data")

    try:
        result = data / 10
    except:
        result = 0

    return result
""",

        """
class CodeAnalyzer:
    def analyze(self, code):
        # Analyze incoming source code
        return len(code)

    def report(self, result):
        return result
"""
    ]

    # --------------------------------------------------------
    # Process each incoming data sample
    # --------------------------------------------------------

    for stream_id, code in enumerate(code_stream, start=1):

        review_code(
            agent,
            sensor,
            code,
            stream_id
        )

    print("\n" + "=" * 65)
    print("AGENT EXECUTION COMPLETE")
    print("=" * 65)


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()