"""
Assignment 3.2: Self-Interested Agent Utility Optimization for E-Commerce
Theme: CodeReviewBot shopping for a review plan in a marketplace

Scenario
    CodeReviewBot must review a proprietary file (auth.py, SECURITY mode).
    A marketplace lists 10 review plans (local models, cloud APIs, hybrids).
    The agent is SELF-INTERESTED: it maximises its OWN utility and does not
    care about the seller's margin. It must pick the mathematically optimal
    plan under hard constraints (budget, deadline, privacy, minimum skill).

Utility function (all terms scaled to 0..1, weights sum to 1)

    U(plan) = w_cost    * (1 - price / budget)
            + w_time    * (1 - turnaround / deadline)
            + w_quality * H(skill_mode, 1 - false_positive_rate)
            + w_privacy * privacy
            + w_stream  * streaming

    H(a, b) = 2ab / (a + b)   (harmonic mean: a plan must be BOTH able to
                               find real issues AND not drown the user in
                               false alarms; being good at one cannot hide
                               being bad at the other)

Search algorithm (4 stages)
    1. Validate    : reject malformed catalog entries (never crash)
    2. Constrain   : hard feasibility filter with recorded reasons
    3. Pareto prune: drop plans that another feasible plan beats on EVERY
                     criterion (cannot be optimal for any positive weights)
    4. Argmax      : evaluate utility only on the Pareto front, deterministic
                     tie-break (higher U, lower price, name)
    Verification   : exhaustive search over all 10 plans, an exact-arithmetic
                     (Fraction) re-evaluation, a fuzz test of 300 random
                     catalogs, and a weight-sensitivity Monte Carlo.
"""

import math
import random
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, Dict, List, Optional, Tuple

REVIEW_MODES = ["SECURITY", "COMPLEXITY", "PERFORMANCE",
                "BUG_DETECTION", "DOCUMENTATION", "STYLE"]
WEIGHT_KEYS = ("cost", "time", "quality", "privacy", "streaming")
DEFAULT_WEIGHTS = {"cost": 0.20, "time": 0.15, "quality": 0.35,
                   "privacy": 0.20, "streaming": 0.10}
EPS = 1e-9                     # tolerance so boundary values are not lost


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
class CatalogError(ValueError):
    """A marketplace entry is malformed."""


@dataclass(frozen=True)
class Plan:
    name: str
    kind: str                      # local / hybrid / cloud
    price: float                   # credits for this review
    time: float                    # turnaround in minutes
    fpr: float                     # false positive rate 0..1
    privacy: float                 # 1 = code never leaves the machine
    streaming: bool
    skills: Dict[str, float] = field(default_factory=dict, hash=False,
                                     compare=False)   # detection rate per mode


@dataclass
class Task:
    file_name: str
    lines: int
    mode: str
    budget: float                  # max credits
    deadline: float                # max minutes
    min_privacy: float             # code is proprietary
    min_skill: float               # minimum detection rate for the mode


@dataclass
class Decision:
    chosen: Optional[Plan] = None
    utility: Optional[float] = None
    ranking: List[Tuple[Plan, float]] = field(default_factory=list)
    infeasible: List[Tuple[Plan, List[str]]] = field(default_factory=list)
    dominated: List[Tuple[Plan, str]] = field(default_factory=list)
    skipped: List[Tuple[object, str]] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    note: str = ""


# ---------------------------------------------------------------------------
# Validation helpers (constraint boundary resilience)
# ---------------------------------------------------------------------------
def _finite(x, label: str) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise CatalogError(f"{label} is not a number: {x!r}")
    if not math.isfinite(v):
        raise CatalogError(f"{label} is not finite: {x!r}")
    return v


def parse_plan(raw) -> Plan:
    """dict -> Plan, raising CatalogError with a precise reason."""
    if not isinstance(raw, dict):
        raise CatalogError("entry is not an object")
    for key in ("name", "kind", "price", "time", "fpr", "privacy",
                "streaming", "skills"):
        if key not in raw:
            raise CatalogError(f"missing field '{key}'")
    price = _finite(raw["price"], "price")
    time_ = _finite(raw["time"], "time")
    fpr = _finite(raw["fpr"], "fpr")
    privacy = _finite(raw["privacy"], "privacy")
    if price < 0:
        raise CatalogError(f"negative price {price}")
    if time_ <= 0:
        raise CatalogError(f"non-positive turnaround {time_}")
    if not 0 <= fpr <= 1:
        raise CatalogError(f"fpr {fpr} outside 0..1")
    if not 0 <= privacy <= 1:
        raise CatalogError(f"privacy {privacy} outside 0..1")
    if not isinstance(raw["skills"], dict):
        raise CatalogError("skills must be an object")
    skills = {}
    for mode, val in raw["skills"].items():
        if mode not in REVIEW_MODES:
            raise CatalogError(f"unknown review mode '{mode}'")
        v = _finite(val, f"skill[{mode}]")
        if not 0 <= v <= 1:
            raise CatalogError(f"skill[{mode}]={v} outside 0..1")
        skills[mode] = v
    return Plan(str(raw["name"]), str(raw["kind"]), price, time_, fpr,
                privacy, bool(raw["streaming"]), skills)


def validate_task(t: Task) -> None:
    if t.mode not in REVIEW_MODES:
        raise ValueError(f"unknown review mode {t.mode!r}")
    for label, v in (("budget", t.budget), ("deadline", t.deadline)):
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
            raise ValueError(f"{label} must be a positive number, got {v!r}")
    for label, v in (("min_privacy", t.min_privacy),
                     ("min_skill", t.min_skill)):
        if not (isinstance(v, (int, float)) and 0 <= v <= 1):
            raise ValueError(f"{label} must be within 0..1, got {v!r}")
    if t.lines <= 0:
        raise ValueError("lines must be positive")


def normalize_weights(w: Dict[str, float]) -> Dict[str, float]:
    if set(w) != set(WEIGHT_KEYS):
        raise ValueError(f"weights must have exactly {WEIGHT_KEYS}")
    for k, v in w.items():
        if not (isinstance(v, (int, float)) and math.isfinite(v)):
            raise ValueError(f"weight '{k}' is not a finite number")
        if v < 0:
            raise ValueError(f"weight '{k}' is negative ({v})")
    total = sum(w.values())
    if total <= 0:
        raise ValueError("weights sum to zero")
    return {k: v / total for k, v in w.items()}      # rescale to sum 1


# ---------------------------------------------------------------------------
# The utility evaluator
# ---------------------------------------------------------------------------
def components(p: Plan, t: Task, cv: Callable = float) -> Dict[str, object]:
    """Each term of the utility, as numbers of type cv (float or Fraction)."""
    zero, one = cv(0), cv(1)
    clip = lambda x: max(zero, min(one, x))
    skill = cv(p.skills.get(t.mode, 0))
    precision = one - cv(p.fpr)
    q = (2 * skill * precision / (skill + precision)) if (skill + precision) else zero
    return {
        "cost": clip(one - cv(p.price) / cv(t.budget)),
        "time": clip(one - cv(p.time) / cv(t.deadline)),
        "quality": q,
        "privacy": cv(p.privacy),
        "streaming": one if p.streaming else zero,
    }


def utility(p: Plan, t: Task, w: Dict[str, float], cv: Callable = float):
    c = components(p, t, cv)
    return sum(cv(w[k]) * c[k] for k in WEIGHT_KEYS)


def exact(x) -> Fraction:
    """Exact decimal value of a float as written (avoids binary rounding)."""
    return Fraction(str(x))


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------
def violations(p: Plan, t: Task) -> List[Tuple[str, float, bool]]:
    """Returns (text, normalised gap, relaxable) for every broken constraint."""
    v = []
    if t.mode not in p.skills:
        v.append((f"mode {t.mode} not supported", 1.0, False))
        return v
    if p.skills[t.mode] < t.min_skill - EPS:
        v.append((f"skill {p.skills[t.mode]:.2f} < min {t.min_skill:.2f}",
                  t.min_skill - p.skills[t.mode], True))
    if p.price > t.budget + EPS:
        v.append((f"price {p.price:g} > budget {t.budget:g}",
                  (p.price - t.budget) / t.budget, True))
    if p.time > t.deadline + EPS:
        v.append((f"time {p.time:g} > deadline {t.deadline:g}",
                  (p.time - t.deadline) / t.deadline, True))
    if p.privacy < t.min_privacy - EPS:
        v.append((f"privacy {p.privacy:.1f} < min {t.min_privacy:.1f}",
                  t.min_privacy - p.privacy, True))
    return v


# ---------------------------------------------------------------------------
# Pareto dominance (weight independent)
# ---------------------------------------------------------------------------
def criteria(p: Plan, t: Task) -> Tuple[float, ...]:
    """Higher is better for every entry."""
    c = components(p, t)
    return (-p.price, -p.time, c["quality"], p.privacy, c["streaming"])


def dominates(a: Plan, b: Plan, t: Task) -> bool:
    ca, cb = criteria(a, t), criteria(b, t)
    return (all(x >= y - EPS for x, y in zip(ca, cb))
            and any(x > y + EPS for x, y in zip(ca, cb)))


# ---------------------------------------------------------------------------
# The optimizer
# ---------------------------------------------------------------------------
def best_key(p: Plan, u: float):
    """Deterministic ordering: higher utility, then cheaper, then by name."""
    return (-round(u, 12), p.price, p.name)


def choose(raw_catalog, task: Task, weights: Dict[str, float] = None) -> Decision:
    validate_task(task)
    w = normalize_weights(weights or DEFAULT_WEIGHTS)
    d = Decision()

    # Stage 1: validate catalog
    plans: List[Plan] = []
    for raw in (raw_catalog or []):
        try:
            plans.append(raw if isinstance(raw, Plan) else parse_plan(raw))
        except CatalogError as exc:
            label = raw.get("name", "?") if isinstance(raw, dict) else raw
            d.skipped.append((label, str(exc)))
    d.counts["raw"] = len(raw_catalog or [])
    d.counts["valid"] = len(plans)
    if not plans:
        d.note = "no valid plans in catalog"
        return d

    # Stage 2: hard constraints
    feasible: List[Plan] = []
    for p in plans:
        v = violations(p, task)
        if v:
            d.infeasible.append((p, [x[0] for x in v]))
        else:
            feasible.append(p)
    d.counts["feasible"] = len(feasible)
    if not feasible:
        d.note = relaxation_advice(plans, task)
        return d

    # Stage 3: Pareto pruning
    front: List[Plan] = []
    for p in feasible:
        killer = next((q for q in feasible if q is not p
                       and dominates(q, p, task)), None)
        if killer:
            d.dominated.append((p, f"dominated by {killer.name}"))
        else:
            front.append(p)
    d.counts["front"] = len(front)

    # Stage 4: utility argmax on the front only
    scored = [(p, utility(p, task, w)) for p in front]
    d.counts["utility_evals"] = len(scored)
    scored.sort(key=lambda s: best_key(*s))
    d.ranking = scored
    d.chosen, d.utility = scored[0]
    return d


def relaxation_advice(plans: List[Plan], t: Task) -> str:
    """No plan satisfies the constraints: say which single relaxation would
    admit the closest plan (instead of failing silently)."""
    cands = []
    for p in plans:
        v = violations(p, t)
        if v and all(x[2] for x in v):
            cands.append((len(v), sum(x[1] for x in v), p, v))
    if not cands:
        return "no feasible plan and no relaxable candidate"
    cands.sort(key=lambda c: (c[0], c[1], c[2].name))
    _, _, p, v = cands[0]
    return (f"no feasible plan; closest is {p.name} which breaks: "
            + "; ".join(x[0] for x in v))


# ---------------------------------------------------------------------------
# Independent verification
# ---------------------------------------------------------------------------
def exhaustive_best(plans: List[Plan], t: Task, w: Dict[str, float],
                    cv: Callable = float) -> Optional[Plan]:
    """Brute force over EVERY plan, no pruning, optional exact arithmetic."""
    w = normalize_weights(w)
    best = None
    for p in plans:
        if violations(p, t):
            continue
        u = utility(p, t, w, cv)
        key = (-u, cv(p.price), p.name)
        if best is None or key < best[0]:
            best = (key, p)
    return best[1] if best else None


def monte_carlo(front: List[Plan], t: Task, base: Dict[str, float],
                trials: int = 5000, spread: float = 0.30, seed: int = 2026):
    """How often does each plan win if the weights are +/-30% uncertain?"""
    rng = random.Random(seed)
    wins: Dict[str, int] = {p.name: 0 for p in front}
    for _ in range(trials):
        w = {k: base[k] * rng.uniform(1 - spread, 1 + spread) for k in base}
        w = normalize_weights(w)
        winner = min(front, key=lambda p: best_key(p, utility(p, t, w)))
        wins[winner.name] += 1
    return wins


# ---------------------------------------------------------------------------
# The marketplace: 10 complex options
# ---------------------------------------------------------------------------
CATALOG = [
    {"name": "LocalLite-7B", "kind": "local", "price": 8, "time": 40,
     "fpr": 0.20, "privacy": 1.0, "streaming": True,
     "skills": {"SECURITY": 0.60, "COMPLEXITY": 0.65, "STYLE": 0.85,
                "DOCUMENTATION": 0.80, "BUG_DETECTION": 0.55}},
    {"name": "LocalPro-34B", "kind": "local", "price": 22, "time": 28,
     "fpr": 0.10, "privacy": 1.0, "streaming": True,
     "skills": {"SECURITY": 0.82, "COMPLEXITY": 0.80, "PERFORMANCE": 0.75,
                "BUG_DETECTION": 0.78, "DOCUMENTATION": 0.70, "STYLE": 0.80}},
    {"name": "CloudTurbo", "kind": "cloud", "price": 35, "time": 8,
     "fpr": 0.08, "privacy": 0.2, "streaming": True,
     "skills": {"SECURITY": 0.90, "COMPLEXITY": 0.85, "PERFORMANCE": 0.80,
                "BUG_DETECTION": 0.85}},
    {"name": "CloudBudget", "kind": "cloud", "price": 6, "time": 55,
     "fpr": 0.30, "privacy": 0.2, "streaming": False,
     "skills": {"SECURITY": 0.50, "STYLE": 0.70, "DOCUMENTATION": 0.65}},
    {"name": "HybridGuard", "kind": "hybrid", "price": 30, "time": 15,
     "fpr": 0.07, "privacy": 0.6, "streaming": True,
     "skills": {"SECURITY": 0.88, "BUG_DETECTION": 0.80,
                "COMPLEXITY": 0.75}},
    {"name": "SecSpecialist-Cloud", "kind": "cloud", "price": 55, "time": 12,
     "fpr": 0.05, "privacy": 0.2, "streaming": True,
     "skills": {"SECURITY": 0.96}},
    {"name": "SecSpecialist-OnPrem", "kind": "local", "price": 48, "time": 30,
     "fpr": 0.06, "privacy": 1.0, "streaming": True,
     "skills": {"SECURITY": 0.94, "BUG_DETECTION": 0.82}},
    {"name": "LinterPlusLLM", "kind": "hybrid", "price": 14, "time": 20,
     "fpr": 0.15, "privacy": 0.6, "streaming": False,
     "skills": {"SECURITY": 0.70, "STYLE": 0.90, "COMPLEXITY": 0.72}},
    {"name": "CommunityBot", "kind": "cloud", "price": 0, "time": 90,
     "fpr": 0.35, "privacy": 0.2, "streaming": False,
     "skills": {"STYLE": 0.60, "DOCUMENTATION": 0.55}},
    {"name": "HybridPremium-Overpriced", "kind": "hybrid", "price": 45,
     "time": 25, "fpr": 0.12, "privacy": 0.6, "streaming": True,
     "skills": {"SECURITY": 0.78, "COMPLEXITY": 0.70}},
]

TASK = Task(file_name="auth.py", lines=320, mode="SECURITY", budget=50,
            deadline=60, min_privacy=0.5, min_skill=0.60)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def rule(ch="-", n=96):
    print(ch * n)


def show_catalog(plans: List[Plan], t: Task) -> None:
    print(f" {'#':<3}{'plan':<26}{'kind':<8}{'price':>6}{'min':>5}"
          f"{'skill':>7}{'fpr':>6}{'priv':>6}{'strm':>6}")
    for i, p in enumerate(plans, 1):
        sk = f"{p.skills[t.mode]:.2f}" if t.mode in p.skills else "n/a"
        print(f" {i:<3}{p.name:<26}{p.kind:<8}{p.price:>6g}{p.time:>5g}"
              f"{sk:>7}{p.fpr:>6.2f}{p.privacy:>6.1f}"
              f"{'yes' if p.streaming else 'no':>6}")


def main_demo() -> None:
    print("=" * 96)
    print(" CodeReviewBot: Self-Interested Utility Optimization (Assignment 3.2)")
    print("=" * 96)
    t, w = TASK, normalize_weights(DEFAULT_WEIGHTS)
    print(f" Job   : {t.file_name} ({t.lines} lines), mode {t.mode}")
    print(f" Limits: budget <= {t.budget:g} credits, deadline <= {t.deadline:g}"
          f" min, privacy >= {t.min_privacy}, skill >= {t.min_skill}")
    print(" Weights: " + ", ".join(f"{k}={v:.2f}" for k, v in w.items()))
    print("\n U = w_cost*(1-price/budget) + w_time*(1-time/deadline)"
          "\n     + w_quality*H(skill, 1-fpr) + w_privacy*privacy"
          " + w_stream*streaming")

    plans = [parse_plan(r) for r in CATALOG]
    print("\n" + "=" * 96)
    print(" THE 10 OPTIONS")
    print("=" * 96)
    show_catalog(plans, t)

    d = choose(CATALOG, t)

    print("\n" + "=" * 96)
    print(" STAGE 2: HARD CONSTRAINT FILTER")
    print("=" * 96)
    for p, why in d.infeasible:
        print(f" REJECT {p.name:<26} {'; '.join(why)}")
    print(f" -> {d.counts['feasible']} of {d.counts['valid']} plans feasible"
          f" (boundary values count: LocalLite skill 0.60 == min 0.60 passes)")

    print("\n" + "=" * 96)
    print(" STAGE 3: PARETO PRUNING (no positive weights can ever pick these)")
    print("=" * 96)
    for p, why in d.dominated:
        print(f" PRUNE  {p.name:<26} {why}")
    print(f" -> front of {d.counts['front']} plans, utility evaluated "
          f"{d.counts['utility_evals']} times instead of {d.counts['valid']}")

    print("\n" + "=" * 96)
    print(" STAGE 4: UTILITY SCORES (best first)")
    print("=" * 96)
    print(f" {'rank':<5}{'plan':<24}{'cost':>7}{'time':>7}{'quality':>9}"
          f"{'privacy':>9}{'stream':>8}{'  U':>9}")
    for r, (p, u) in enumerate(d.ranking, 1):
        c = components(p, t)
        print(f" {r:<5}{p.name:<24}{w['cost']*c['cost']:>7.3f}"
              f"{w['time']*c['time']:>7.3f}{w['quality']*c['quality']:>9.3f}"
              f"{w['privacy']*c['privacy']:>9.3f}"
              f"{w['streaming']*c['streaming']:>8.3f}{u:>9.4f}"
              f"{'   <== CHOSEN' if r == 1 else ''}")
    print(" (columns show weight x term, they add up to U)")

    print("\n" + "=" * 96)
    print(" EVIDENCE THAT THE CHOICE IS THE MATHEMATICAL OPTIMUM")
    print("=" * 96)
    brute = exhaustive_best(plans, t, DEFAULT_WEIGHTS)
    exact_pick = exhaustive_best(plans, t, DEFAULT_WEIGHTS, cv=exact)
    print(f" optimizer pick                     : {d.chosen.name}")
    print(f" exhaustive search over all 10      : {brute.name}")
    print(f" exact Fraction arithmetic (no float): {exact_pick.name}")
    assert d.chosen.name == brute.name == exact_pick.name
    runner = d.ranking[1]
    print(f" margin over runner-up ({runner[0].name}) : "
          f"{d.utility - runner[1]:.4f}")
    print(" PASS: all three methods agree")

    # fuzz test
    rng, mismatches = random.Random(7), 0
    for _ in range(300):
        cat = [{"name": f"P{i}", "kind": "x",
                "price": rng.uniform(0, 70), "time": rng.uniform(1, 90),
                "fpr": rng.uniform(0, .4), "privacy": rng.choice([.2, .6, 1]),
                "streaming": rng.random() < .6,
                "skills": {"SECURITY": rng.uniform(.3, 1)}}
               for i in range(10)]
        rw = {k: rng.uniform(0.05, 1) for k in WEIGHT_KEYS}
        got = choose(cat, t, rw).chosen
        ref = exhaustive_best([parse_plan(c) for c in cat], t, rw)
        if (got.name if got else None) != (ref.name if ref else None):
            mismatches += 1
    print(f" fuzz test: 300 random catalogs, random weights -> "
          f"{mismatches} mismatches vs exhaustive search")
    assert mismatches == 0
    print(" PASS: pruning never lost the optimum")

    wins = monte_carlo([p for p, _ in d.ranking], t, w)
    print("\n weight sensitivity (5000 trials, each weight varied +/-30%):")
    for name, n in sorted(wins.items(), key=lambda kv: -kv[1]):
        print(f"   {name:<24}{n/50:>6.1f}%  " + "#" * round(n / 5000 * 40))

    print("\n" + "=" * 96)
    print(f" DECISION: buy '{d.chosen.name}' for {d.chosen.price:g} credits, "
          f"{d.chosen.time:g} min, U = {d.utility:.4f}")
    print("=" * 96)


# ---------------------------------------------------------------------------
# Boundary and error tests
# ---------------------------------------------------------------------------
def make(name="X", **kw) -> dict:
    base = {"name": name, "kind": "local", "price": 20, "time": 20,
            "fpr": 0.1, "privacy": 1.0, "streaming": True,
            "skills": {"SECURITY": 0.8}}
    base.update(kw)
    return base


def check(label: str, cond: bool, detail: str = "") -> None:
    print(f" [{'PASS' if cond else 'FAIL'}] {label}" +
          (f"  ({detail})" if detail else ""))
    assert cond, label


def run_boundary_tests() -> None:
    print("\n" + "=" * 96)
    print(" ERROR AND CONSTRAINT BOUNDARY TESTS")
    print("=" * 96)
    t = TASK

    d = choose([make("AtBudget", price=50.0)], t)
    check("price exactly equal to budget is accepted (inclusive bound)",
          d.chosen is not None and d.chosen.name == "AtBudget")

    d = choose([make("Float", price=50.0 + 1e-10)], t)
    check("price off by 1e-10 (float noise) is still accepted",
          d.chosen is not None)

    d = choose([make("Over", price=50.01)], t)
    check("price 0.01 over budget is rejected, advice is returned",
          d.chosen is None and "Over" in d.note, d.note)

    d = choose([make("Free", price=0)], t)
    check("price 0 (free plan) is handled", d.chosen is not None)

    d = choose([], t)
    check("empty catalog returns a clean 'no decision', no crash",
          d.chosen is None and "no valid plans" in d.note, d.note)

    bad = [make("NoPrice"), make("Neg", price=-5), make("NaN", price=float("nan")),
           make("Text", time="fast"), make("BadFpr", fpr=1.5),
           make("BadMode", skills={"TYPO": 0.5}), "not a dict",
           make("Good", price=10)]
    del bad[0]["price"]
    d = choose(bad, t)
    check("7 malformed entries skipped, the 1 valid entry still chosen",
          len(d.skipped) == 7 and d.chosen.name == "Good",
          f"skipped={len(d.skipped)}")

    d1 = choose(CATALOG, t, DEFAULT_WEIGHTS)
    d2 = choose(CATALOG, t, {k: v * 10 for k, v in DEFAULT_WEIGHTS.items()})
    check("weights that do not sum to 1 are rescaled (x10 gives same result)",
          d1.chosen.name == d2.chosen.name
          and abs(d1.utility - d2.utility) < 1e-12)

    for label, bw in (("negative weight", {**DEFAULT_WEIGHTS, "cost": -0.1}),
                      ("all-zero weights", {k: 0 for k in WEIGHT_KEYS}),
                      ("missing weight key", {"cost": 1}),
                      ("NaN weight", {**DEFAULT_WEIGHTS, "time": float("nan")})):
        try:
            choose(CATALOG, t, bw)
            check(f"{label} raises ValueError", False)
        except ValueError as exc:
            check(f"{label} raises a clear ValueError", True, str(exc))

    try:
        choose(CATALOG, Task("a.py", 10, "TYPO", 50, 60, .5, .6))
        check("unknown review mode raises ValueError", False)
    except ValueError as exc:
        check("unknown review mode raises a clear ValueError", True, str(exc))

    try:
        choose(CATALOG, Task("a.py", 10, "SECURITY", 0, 60, .5, .6))
        check("zero budget raises ValueError (avoids divide by zero)", False)
    except ValueError as exc:
        check("zero budget raises ValueError (avoids divide by zero)", True,
              str(exc))

    d = choose([make("Zeta"), make("Alpha")], t)
    check("exact utility tie is broken deterministically (name order)",
          d.chosen.name == "Alpha")

    d = choose([make("Cheap", price=5), make("Dear", price=5.0)], t)
    check("identical plans do not eliminate each other (no strict dominance)",
          len(d.ranking) == 2)

    d = choose([make("OnlyStyle", skills={"STYLE": 0.9})], t)
    check("plan that does not support the mode is filtered, advice given",
          d.chosen is None, d.note)

    d = choose([make("Slow", time=61), make("Leaky", privacy=0.4)], t)
    check("no feasible plan: advice names the closest candidate",
          d.chosen is None and ("Slow" in d.note or "Leaky" in d.note), d.note)

    print(" All boundary tests passed.")


if __name__ == "__main__":
    main_demo()
    run_boundary_tests()
