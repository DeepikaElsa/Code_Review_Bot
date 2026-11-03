"""
Assignment 3.1: Multi-Agent Coordination Protocol Execution
Theme: CodeReviewBot agents negotiating a review contract (Contract Net)

Three distinct instances of the agent class run as separate threads and
talk only through a message bus (no shared variables):

    Requester   : the "buyer", owns a review job (file, mode, budget, deadline)
    SecBot      : reviewer instance, security specialist, expensive, thorough
    GeneralBot  : reviewer instance, all rounder, cheaper, less security depth

Protocol (Contract Net Protocol + bilateral bargaining, FIPA style):

    Phase 1  CFP              Requester broadcasts the job
    Phase 2  PROPOSE/REFUSE   each reviewer bids (or declines if it cannot
                              meet budget or deadline)
    Phase 3  AWARD / REJECT   Requester ranks bids by its utility, shortlists
                              the best, rejects the others
    Phase 4  COUNTER_PROPOSE  multi-turn bargaining on price and turnaround,
                              each side concedes using a time dependent
                              strategy and judges offers by a utility formula
    Phase 5  Handshake        ACCEPT_PROPOSAL -> CONFIRM -> FINAL_ACK
                              (or NO_DEAL -> FINAL_ACK when no agreement),
                              then SHUTDOWN, so every thread terminates

Acceptance rule used by BOTH sides (standard in automated negotiation):
    accept an incoming offer iff it is feasible (hard limits respected) and
    its utility >= the utility of the offer I would send next.
"""

import queue
import threading
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

MAX_ROUNDS = 8            # negotiation deadline (in rounds)
RECV_TIMEOUT = 3.0        # seconds an agent waits before giving up
BAR_WIDTH = 20


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
@dataclass
class Job:
    file_name: str
    lines: int
    mode: str              # one of the 6 CodeReviewBot review modes
    budget: float          # max credits the requester may spend
    deadline_max: float    # latest acceptable turnaround in minutes


@dataclass
class Offer:
    price: float           # credits
    time: float            # turnaround in minutes
    quality: float         # reviewer's expertise for this mode (0..1)


@dataclass
class Message:
    turn: int
    sender: str
    receiver: str
    perf: str              # performative (message type)
    content: dict


def clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def bar(u: float) -> str:
    n = round(clip(u) * BAR_WIDTH)
    return "#" * n + "." * (BAR_WIDTH - n)


# ---------------------------------------------------------------------------
# Message bus: the only way agents communicate, and the timeline printer
# ---------------------------------------------------------------------------
class MessageBus:
    def __init__(self) -> None:
        self.inboxes: Dict[str, "queue.Queue[Message]"] = {}
        self.lock = threading.Lock()
        self.turn = 0
        self.history: List[Message] = []

    def register(self, name: str) -> "queue.Queue[Message]":
        self.inboxes[name] = queue.Queue()
        return self.inboxes[name]

    @staticmethod
    def describe(c: dict) -> str:
        parts = []
        if "round" in c:
            parts.append(f"round={c['round']}")
        o = c.get("offer")
        if o:
            parts.append(f"price={o['price']:.1f} time={o['time']:.1f}m "
                         f"q={o['quality']:.2f}")
        for key in ("file", "mode", "budget", "deadline", "reason",
                    "outcome", "final"):
            if key in c:
                parts.append(f"{key}={c[key]}")
        return " ".join(parts)

    def send(self, sender: str, receiver: str, perf: str,
             content: dict) -> Message:
        with self.lock:
            self.turn += 1
            msg = Message(self.turn, sender, receiver, perf, content)
            self.history.append(msg)
            print(f"[T{msg.turn:02d}] {sender:<10} --{perf}--> {receiver:<10} "
                  f"{self.describe(content)}", flush=True)
        self.inboxes[receiver].put(msg)
        return msg

    def note(self, who: str, text: str) -> None:
        with self.lock:
            print(f"        . {who}: {text}", flush=True)


# ---------------------------------------------------------------------------
# Base agent (one thread per instance)
# ---------------------------------------------------------------------------
class CodeReviewAgent(threading.Thread):
    def __init__(self, name: str, bus: MessageBus):
        super().__init__(name=name, daemon=True)
        self.bus = bus
        self.inbox = bus.register(name)
        self.state = "IDLE"

    def say(self, receiver: str, perf: str, content: dict) -> None:
        self.bus.send(self.name, receiver, perf, content)

    def note(self, text: str) -> None:
        self.bus.note(self.name, text)

    def recv(self) -> Optional[Message]:
        try:
            return self.inbox.get(timeout=RECV_TIMEOUT)
        except queue.Empty:
            return None


# ---------------------------------------------------------------------------
# Reviewer (seller / contractor) instance
# ---------------------------------------------------------------------------
class ReviewerAgent(CodeReviewAgent):
    def __init__(self, name, bus, expertise: Dict[str, float], rate: float,
                 speed: float, greed: float, beta: float, delay: float):
        super().__init__(name, bus)
        self.expertise = expertise    # quality per review mode
        self.rate = rate              # credits per 100 lines
        self.speed = speed            # lines reviewed per minute
        self.greed = greed            # opening price as share of budget
        self.beta = beta              # <1 stubborn (Boulware), >1 yielding
        self.delay = delay            # simulated thinking time
        self.job: Optional[Job] = None
        self.requester: Optional[str] = None

    # -- private economics (never sent over the wire) -------------------------
    def setup(self, job: Job) -> None:
        self.job = job
        self.cost = self.rate * job.lines / 100
        self.min_price = self.cost * 1.10                  # keep 10% margin
        self.min_time = job.lines / self.speed             # physical limit
        self.quality = self.expertise[job.mode]
        self.open_price = max(self.min_price, self.greed * job.budget)
        self.open_time = self.min_time + 0.6 * (job.deadline_max - self.min_time)

    def utility(self, o: Offer) -> float:
        """Reviewer wants high margin and relaxed deadlines."""
        margin = clip((o.price - self.cost) / (self.job.budget - self.cost))
        relax = clip(o.time / self.job.deadline_max)
        return 0.7 * margin + 0.3 * relax

    def offer_at(self, k: int) -> Offer:
        f = (k / MAX_ROUNDS) ** (1 / self.beta)            # concession curve
        return Offer(self.open_price + (self.min_price - self.open_price) * f,
                     self.open_time + (self.min_time - self.open_time) * f,
                     self.quality)

    def feasible(self, o: Offer) -> bool:
        return o.price >= self.min_price and o.time >= self.min_time

    # -- message loop --------------------------------------------------------------
    def run(self) -> None:
        while True:
            msg = self.recv()
            if msg is None:
                self.note("no message for a long time, stopping")
                return
            if msg.perf == "SHUTDOWN":
                return
            handler = getattr(self, "on_" + msg.perf.lower(), None)
            if handler is None:            # unknown message: ignore, stay alive
                self.note(f"ignoring unexpected {msg.perf}")
                continue
            handler(msg)

    def on_cfp(self, msg: Message) -> None:
        time.sleep(self.delay)
        self.setup(Job(**msg.content["job"]))
        self.requester = msg.sender
        if (self.min_price > self.job.budget
                or self.min_time > self.job.deadline_max):
            self.note(f"cannot serve: needs {self.min_price:.1f} credits / "
                      f"{self.min_time:.1f} min, job allows "
                      f"{self.job.budget:.0f} / {self.job.deadline_max:.0f}")
            self.say(msg.sender, "REFUSE", {"reason": "cannot meet constraints"})
            self.state = "REFUSED"
            return
        o = self.offer_at(0)
        self.note(f"cost={self.cost:.1f} floor=({self.min_price:.1f} credits, "
                  f"{self.min_time:.1f} min) U_rev(opening)={self.utility(o):.3f}")
        self.say(msg.sender, "PROPOSE", {"round": 0, "offer": asdict(o)})
        self.state = "BID_SENT"

    def on_award(self, msg: Message) -> None:
        self.state = "NEGOTIATING"
        self.note("shortlisted, entering negotiation")

    def on_reject_proposal(self, msg: Message) -> None:
        self.state = "REJECTED"
        self.note("bid rejected, standing down")

    def on_counter_propose(self, msg: Message) -> None:
        k = msg.content["round"]
        got = Offer(**msg.content["offer"])
        mine = self.offer_at(k)
        u_got, u_mine = self.utility(got), self.utility(mine)
        ok = self.feasible(got) and u_got >= u_mine
        self.note(f"U_rev(received)={u_got:.3f} vs U_rev(my round-{k} offer)="
                  f"{u_mine:.3f} feasible={self.feasible(got)} -> "
                  f"{'ACCEPT' if ok else 'counter'}")
        if ok:
            self.say(msg.sender, "ACCEPT_PROPOSAL",
                     {"round": k, "offer": asdict(got)})
            self.state = "ACCEPTED"
        else:
            self.say(msg.sender, "COUNTER_PROPOSE",
                     {"round": k, "offer": asdict(mine)})

    def on_accept_proposal(self, msg: Message) -> None:
        # Requester accepted MY offer: I confirm the final terms
        self.say(msg.sender, "CONFIRM",
                 {"offer": msg.content["offer"], "final": "terms locked"})
        self.state = "CONFIRMED"

    def on_confirm(self, msg: Message) -> None:
        # I accepted the requester's offer and it confirmed: close handshake
        self.say(msg.sender, "FINAL_ACK", {"outcome": "DEAL"})
        self.state = "DEAL"

    def on_final_ack(self, msg: Message) -> None:
        self.state = "DEAL" if msg.content.get("outcome") == "DEAL" else "NO_DEAL"

    def on_no_deal(self, msg: Message) -> None:
        self.say(msg.sender, "FINAL_ACK", {"outcome": "NO_DEAL"})
        self.state = "NO_DEAL"


# ---------------------------------------------------------------------------
# Requester (buyer) instance: runs the whole protocol
# ---------------------------------------------------------------------------
class RequesterAgent(CodeReviewAgent):
    def __init__(self, name, bus, job: Job, reviewers: List[str],
                 beta: float = 1.0):
        super().__init__(name, bus)
        self.job, self.reviewers, self.beta = job, reviewers, beta
        self.p0, self.cap_p = 0.35 * job.budget, 0.85 * job.budget
        self.t0, self.cap_t = 0.25 * job.deadline_max, 0.85 * job.deadline_max
        self.quality = 0.0
        self.winner: Optional[str] = None
        self.result: dict = {"outcome": "NOT_RUN"}

    def utility(self, o: Offer) -> float:
        """Requester wants low price, fast turnaround, high quality."""
        return clip(0.40 * (1 - o.price / self.job.budget)
                    + 0.25 * (1 - o.time / self.job.deadline_max)
                    + 0.35 * o.quality)

    def offer_at(self, k: int) -> Offer:
        f = (k / MAX_ROUNDS) ** (1 / self.beta)
        return Offer(self.p0 + (self.cap_p - self.p0) * f,
                     self.t0 + (self.cap_t - self.t0) * f, self.quality)

    def feasible(self, o: Offer) -> bool:
        return o.price <= self.cap_p and o.time <= self.cap_t

    def run(self) -> None:
        self.negotiate()
        for r in self.reviewers:                    # release every thread
            self.say(r, "SHUTDOWN", {})

    def negotiate(self) -> None:
        j = self.job
        # ---- Phase 1: call for proposals --------------------------------------
        print("\n--- PHASE 1: CALL FOR PROPOSALS ---")
        for r in self.reviewers:
            self.say(r, "CFP", {"job": asdict(j), "file": j.file_name,
                                "mode": j.mode, "budget": j.budget,
                                "deadline": j.deadline_max})

        # ---- Phase 2: collect bids -------------------------------------------------
        print("\n--- PHASE 2: BIDS ---")
        bids: Dict[str, Offer] = {}
        for _ in self.reviewers:
            m = self.recv()
            if m is None:
                break
            if m.perf == "PROPOSE":
                bids[m.sender] = Offer(**m.content["offer"])
        if not bids:
            self.result = {"outcome": "NO_DEAL", "reason": "no bidders"}
            self.note("no valid bids, aborting")
            return

        # ---- Phase 3: award --------------------------------------------------------
        print("\n--- PHASE 3: EVALUATION AND AWARD ---")
        ranked = sorted(bids, key=lambda n: self.utility(bids[n]), reverse=True)
        for n in ranked:
            self.note(f"U_req({n} opening bid) = {self.utility(bids[n]):.3f}")
        self.winner = ranked[0]
        self.quality = bids[self.winner].quality
        print(f"        > best bid: {self.winner}")
        self.say(self.winner, "AWARD", {"reason": "highest utility bid"})
        for n in ranked[1:]:
            self.say(n, "REJECT_PROPOSAL", {"reason": "lower utility"})

        # ---- Phase 4 and 5: bargaining and handshake ----------------------
        print("\n--- PHASE 4: NEGOTIATION ROUNDS ---")
        last, k = bids[self.winner], 0
        while True:
            own_next = self.offer_at(min(k + 1, MAX_ROUNDS))
            u_last, u_next = self.utility(last), self.utility(own_next)
            ok = self.feasible(last) and u_last >= u_next
            self.note(f"U_req(received)={u_last:.3f} vs U_req(my next offer)="
                      f"{u_next:.3f} feasible={self.feasible(last)} -> "
                      f"{'ACCEPT' if ok else 'continue'}")

            if ok:
                print("\n--- PHASE 5: CONSENSUS HANDSHAKE ---")
                self.say(self.winner, "ACCEPT_PROPOSAL",
                         {"round": k, "offer": asdict(last)})
                m = self.recv()
                if m is None or m.perf != "CONFIRM":
                    self.result = {"outcome": "NO_DEAL", "reason": "no confirm"}
                    return
                self.say(self.winner, "FINAL_ACK", {"outcome": "DEAL"})
                self.state = "DEAL"
                self.result = {"outcome": "DEAL", "winner": self.winner,
                               "offer": last, "round": k}
                return

            if k >= MAX_ROUNDS:
                print("\n--- PHASE 5: TERMINATION WITHOUT AGREEMENT ---")
                self.say(self.winner, "NO_DEAL",
                         {"reason": f"no agreement after {MAX_ROUNDS} rounds"})
                self.recv()                                  # FINAL_ACK
                self.state = "NO_DEAL"
                self.result = {"outcome": "NO_DEAL", "winner": self.winner,
                               "reason": "round limit reached"}
                return

            k += 1
            print(f"        -- round {k} --")
            self.say(self.winner, "COUNTER_PROPOSE",
                     {"round": k, "offer": asdict(self.offer_at(k))})
            m = self.recv()
            if m is None:
                self.result = {"outcome": "NO_DEAL", "reason": "timeout"}
                return
            if m.perf == "ACCEPT_PROPOSAL":
                print("\n--- PHASE 5: CONSENSUS HANDSHAKE ---")
                self.say(self.winner, "CONFIRM",
                         {"offer": m.content["offer"], "final": "terms locked"})
                m2 = self.recv()                              # FINAL_ACK
                self.state = "DEAL"
                self.result = {"outcome": "DEAL", "winner": self.winner,
                               "offer": Offer(**m.content["offer"]),
                               "round": k}
                return
            last = Offer(**m.content["offer"])


# ---------------------------------------------------------------------------
# Scenario runner and report
# ---------------------------------------------------------------------------
def run_scenario(title: str, job: Job) -> None:
    print("\n" + "=" * 92)
    print(f" {title}")
    print(f" job: {job.file_name} ({job.lines} lines) mode={job.mode} "
          f"budget={job.budget:.0f} credits deadline={job.deadline_max:.0f} min")
    print("=" * 92)

    bus = MessageBus()
    sec = ReviewerAgent(
        "SecBot", bus,
        {"SECURITY": .95, "COMPLEXITY": .55, "PERFORMANCE": .50,
         "BUG_DETECTION": .70, "DOCUMENTATION": .45, "STYLE": .45},
        rate=18, speed=10, greed=.95, beta=0.7, delay=0.05)
    gen = ReviewerAgent(
        "GeneralBot", bus,
        {"SECURITY": .60, "COMPLEXITY": .80, "PERFORMANCE": .75,
         "BUG_DETECTION": .70, "DOCUMENTATION": .85, "STYLE": .90},
        rate=12, speed=12, greed=.85, beta=0.8, delay=0.12)
    req = RequesterAgent("Requester", bus, job, ["SecBot", "GeneralBot"])

    agents = [sec, gen, req]
    for a in agents:                       # spawn all instances
        a.start()
    req.join(timeout=30)                   # protocol master finishes first
    for a in (sec, gen):
        a.join(timeout=5)
    alive = [a.name for a in agents if a.is_alive()]
    report(bus, req, {"SecBot": sec, "GeneralBot": gen}, alive)


def report(bus: MessageBus, req: RequesterAgent, reviewers: dict,
           alive: List[str]) -> None:
    print("\n" + "-" * 92)
    print(" NEGOTIATION TIMELINE (offers only, utilities from both private models)")
    print("-" * 92)
    w = reviewers.get(req.winner) if req.winner else None
    if w:
        print(f" {'turn':<5}{'round':<6}{'from':<11}{'price':>7}{'time':>7}   "
              f"{'U_requester':<24}{'U_reviewer':<24}")
        for m in bus.history:
            if m.perf in ("PROPOSE", "COUNTER_PROPOSE") and m.sender in (
                    req.winner, req.name):
                o = Offer(**m.content["offer"])
                ur, uv = req.utility(o), w.utility(o)
                print(f" T{m.turn:02d}  {m.content['round']:<6}{m.sender:<11}"
                      f"{o.price:7.1f}{o.time:7.1f}   "
                      f"{bar(ur)} {ur:.2f} {bar(uv)} {uv:.2f}")

    r = req.result
    print("\n" + "-" * 92)
    print(" RESULT")
    print("-" * 92)
    print(f" outcome        : {r['outcome']}")
    if r["outcome"] == "DEAL":
        o = r["offer"]
        ur, uv = req.utility(o), w.utility(o)
        print(f" contractor     : {r['winner']}  (agreed in round {r['round']})")
        print(f" agreed terms   : {o.price:.1f} credits, {o.time:.1f} minutes, "
              f"quality {o.quality:.2f}")
        print(f" U_requester    : {ur:.3f}    U_reviewer: {uv:.3f}    "
              f"joint utility: {ur + uv:.3f}")
    else:
        print(f" reason         : {r.get('reason')}")
    print(f" agent states   : " + ", ".join(
        f"{n}={a.state}" for n, a in {**reviewers, 'Requester': req}.items()))
    print(f" threads alive  : {alive if alive else 'none (clean termination)'}")
    print(f" messages sent  : {len(bus.history)}")


if __name__ == "__main__":
    print("CodeReviewBot Multi-Agent Coordination (Contract Net + bargaining)")

    # Scenario A: overlapping interests, agents should reach consensus
    run_scenario("SCENARIO A: normal review contract",
                 Job("auth.py", 320, "SECURITY", budget=100, deadline_max=60))

    # Scenario B: urgent job, deadline leaves no zone of agreement
    run_scenario("SCENARIO B: urgent review, no zone of agreement",
                 Job("auth.py", 320, "SECURITY", budget=100, deadline_max=30))
