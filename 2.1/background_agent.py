"""
Assignment 2.1: Concurrent Task Daemonization using Threads and Workers
Theme: CodeReviewBot with a background monitor daemon and a worker pool

Structure (maps to the rubric):
    1. Multi-threading / worker infrastructure
         - ReviewWorker threads (a pool) pull review jobs from a queue
         - The main thread plays the "UI / event loop" and never blocks
    2. Daemon monitoring
         - RepoMonitor is a daemon thread that polls a mock repository
           every POLL_INTERVAL seconds and enqueues a review job for
           every new commit it finds
    3. Thread safety and concurrency handling
         - queue.Queue (thread-safe) passes jobs between threads
         - threading.Lock protects the shared counters and latency lists
         - threading.Event signals a clean shutdown to every thread
         - a separate print lock keeps console lines from interleaving

Unit-2 pattern (Java Beans style):
    ReviewState is a "bean": private state, getters/setters, and
    PropertyChange listeners that get notified when a property changes
    (the observer idea behind Beans bound properties).
"""

import queue
import random
import statistics
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NUM_WORKERS = 3          # size of the worker pool
POLL_INTERVAL = 0.5      # seconds between repository polls
RUN_SECONDS = 5.0        # how long the main "UI loop" keeps running
UI_TICK = 0.1            # UI heartbeat period (seconds)
REVIEW_MODES = ["SECURITY", "COMPLEXITY", "PERFORMANCE",
                "BUG_DETECTION", "DOCUMENTATION", "STYLE"]
FILES = ["auth.py", "db_utils.py", "api_routes.py", "parser.py",
         "stream_handler.py", "config.py", "ui_render.py"]

# ---------------------------------------------------------------------------
# Thread-safe logging helper
# ---------------------------------------------------------------------------
_print_lock = threading.Lock()
_t0 = time.perf_counter()


def log(source: str, text: str) -> None:
    """Prints one timestamped line. The lock stops two threads from
    interleaving characters of their output."""
    elapsed = time.perf_counter() - _t0
    with _print_lock:
        print(f"[{elapsed:7.3f}s] [{source:<10}] {text}", flush=True)


# ---------------------------------------------------------------------------
# Bean-style shared state with property change listeners
# ---------------------------------------------------------------------------
class ReviewState:
    """Shared state, written to by many threads.

    Bean pattern: values are only touched through getters/setters, and
    listeners are told about changes (like PropertyChangeSupport).
    Every access to the shared fields happens under self._lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._submitted = 0
        self._completed = 0
        self._wait_times: List[float] = []      # queue wait per job
        self._run_times: List[float] = []       # processing time per job
        self._per_worker: Dict[str, int] = {}
        self._listeners: List[Callable[[str, int, int], None]] = []

    # -- listener registration (observer) ---------------------------------
    def add_listener(self, fn: Callable[[str, int, int], None]) -> None:
        self._listeners.append(fn)

    def _fire(self, prop: str, old: int, new: int) -> None:
        for fn in self._listeners:
            fn(prop, old, new)

    # -- bean properties ---------------------------------------------------
    def increment_submitted(self) -> int:
        with self._lock:
            old = self._submitted
            self._submitted += 1
            new = self._submitted
        self._fire("submitted", old, new)   # fire outside the lock
        return new

    def record_completion(self, worker: str, wait: float, run: float) -> int:
        with self._lock:
            old = self._completed
            self._completed += 1
            new = self._completed
            self._wait_times.append(wait)
            self._run_times.append(run)
            self._per_worker[worker] = self._per_worker.get(worker, 0) + 1
        self._fire("completed", old, new)
        return new

    def snapshot(self) -> dict:
        """Returns a consistent copy so callers never read half-updated data."""
        with self._lock:
            return {
                "submitted": self._submitted,
                "completed": self._completed,
                "wait": list(self._wait_times),
                "run": list(self._run_times),
                "per_worker": dict(self._per_worker),
            }


# ---------------------------------------------------------------------------
# A unit of work
# ---------------------------------------------------------------------------
@dataclass
class ReviewJob:
    job_id: int
    commit: str
    file_name: str
    mode: str
    enqueued_at: float      # perf_counter value when it entered the queue


# ---------------------------------------------------------------------------
# Worker: consumes review jobs in the background
# ---------------------------------------------------------------------------
class ReviewWorker(threading.Thread):
    """Pool worker. Blocks on the queue with a timeout so it can notice
    the stop event and exit cleanly."""

    def __init__(self, name: str, jobs: "queue.Queue[ReviewJob]",
                 state: ReviewState, stop: threading.Event, seed: int):
        super().__init__(name=name, daemon=True)
        self.jobs = jobs
        self.state = state
        self.stop = stop
        self.rng = random.Random(seed)   # own RNG: no shared random state

    def run(self) -> None:
        log(self.name, "worker started")
        while not self.stop.is_set() or not self.jobs.empty():
            try:
                job = self.jobs.get(timeout=0.2)
            except queue.Empty:
                continue                  # nothing to do, re-check stop flag

            started = time.perf_counter()
            wait = started - job.enqueued_at

            # Simulated review work (this is the slow part that must NOT
            # block the main thread)
            time.sleep(self.rng.uniform(0.05, 0.30))

            run = time.perf_counter() - started
            done = self.state.record_completion(self.name, wait, run)
            log(self.name,
                f"job#{job.job_id} {job.mode}_REVIEW {job.file_name} "
                f"({job.commit}) wait={wait*1000:6.1f}ms run={run*1000:6.1f}ms "
                f"[completed={done}]")
            self.jobs.task_done()
        log(self.name, "worker stopped")


# ---------------------------------------------------------------------------
# Daemon monitor: polls the "repository" for new commits
# ---------------------------------------------------------------------------
class RepoMonitor(threading.Thread):
    """Daemon thread that periodically polls a mock repository and turns
    every new commit into a review job."""

    def __init__(self, jobs: "queue.Queue[ReviewJob]", state: ReviewState,
                 stop: threading.Event, seed: int = 7):
        super().__init__(name="RepoMonitor", daemon=True)
        self.jobs = jobs
        self.state = state
        self.stop = stop
        self.rng = random.Random(seed)
        self.commit_no = 0
        self.job_no = 0
        self.poll_latencies: List[float] = []   # only this thread writes it

    def poll_repository(self) -> List[str]:
        """Mock network call: returns the IDs of new commits."""
        time.sleep(self.rng.uniform(0.01, 0.05))   # simulated network delay
        new = self.rng.randint(0, 3)
        commits = []
        for _ in range(new):
            self.commit_no += 1
            commits.append(f"C{self.commit_no:03d}")
        return commits

    def run(self) -> None:
        log(self.name, f"daemon started, polling every {POLL_INTERVAL}s")
        poll = 0
        # Event.wait doubles as an interruptible sleep: it returns True
        # immediately when stop is set, so shutdown is instant.
        while not self.stop.wait(POLL_INTERVAL):
            poll += 1
            t = time.perf_counter()
            commits = self.poll_repository()
            latency = time.perf_counter() - t
            self.poll_latencies.append(latency)

            if not commits:
                log(self.name, f"poll#{poll}: no new commits "
                               f"(poll latency {latency*1000:.1f}ms)")
                continue

            log(self.name, f"poll#{poll}: {len(commits)} new commit(s) "
                           f"{commits} (poll latency {latency*1000:.1f}ms)")
            for commit in commits:
                self.job_no += 1
                job = ReviewJob(
                    job_id=self.job_no,
                    commit=commit,
                    file_name=self.rng.choice(FILES),
                    mode=self.rng.choice(REVIEW_MODES),
                    enqueued_at=time.perf_counter(),
                )
                self.jobs.put(job)               # thread-safe hand-off
                self.state.increment_submitted()
        log(self.name, "daemon stopped")


# ---------------------------------------------------------------------------
# Main thread: the "UI / core event loop"
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 84)
    print(" CodeReviewBot: Background Daemon + Worker Pool (Assignment 2.1)")
    print("=" * 84)

    jobs: "queue.Queue[ReviewJob]" = queue.Queue()
    state = ReviewState()
    stop = threading.Event()

    # Bean-style listener: reacts to property changes from ANY thread
    def on_change(prop: str, old: int, new: int) -> None:
        if prop == "completed" and new % 5 == 0:
            log("LISTENER", f"property '{prop}' changed {old} -> {new}")

    state.add_listener(on_change)

    monitor = RepoMonitor(jobs, state, stop)
    workers = [ReviewWorker(f"Worker-{i+1}", jobs, state, stop, seed=100 + i)
               for i in range(NUM_WORKERS)]

    monitor.start()
    for w in workers:
        w.start()

    # ---- UI loop: keeps ticking while the background work runs ----------
    # We measure how late each tick is. If background work blocked the
    # main thread, the gaps would be large. They stay close to UI_TICK.
    ui_gaps: List[float] = []
    loop_start = time.perf_counter()
    last = loop_start
    next_report = loop_start + 1.0
    while time.perf_counter() - loop_start < RUN_SECONDS:
        time.sleep(UI_TICK)
        now = time.perf_counter()
        ui_gaps.append(now - last)
        last = now
        if now >= next_report:
            snap = state.snapshot()
            log("UI", f"heartbeat | queue={jobs.qsize()} "
                      f"submitted={snap['submitted']} completed={snap['completed']}")
            next_report += 1.0

    # ---- Graceful shutdown ----------------------------------------------
    log("MAIN", "stopping: no more polling, draining queue")
    stop.set()
    monitor.join(timeout=2)
    jobs.join()                    # waits until every queued job is done
    for w in workers:
        w.join(timeout=2)

    # ---- Performance report ---------------------------------------------
    snap = state.snapshot()
    waits = [w * 1000 for w in snap["wait"]]
    runs = [r * 1000 for r in snap["run"]]
    polls = [p * 1000 for p in monitor.poll_latencies]
    gaps = [g * 1000 for g in ui_gaps]

    def p95(values: List[float]) -> float:
        values = sorted(values)
        return values[min(len(values) - 1, int(0.95 * len(values)))]

    print("=" * 84)
    print(" EXECUTION LATENCY PERFORMANCE LOG")
    print("=" * 84)
    print(f" Jobs submitted / completed   : {snap['submitted']} / {snap['completed']}")
    print(f" Jobs left in queue           : {jobs.qsize()}")
    print(f" Worker distribution          : {snap['per_worker']}")
    print(f" Queue wait   (ms)  avg={statistics.mean(waits):7.1f}  "
          f"max={max(waits):7.1f}  p95={p95(waits):7.1f}")
    print(f" Review time  (ms)  avg={statistics.mean(runs):7.1f}  "
          f"max={max(runs):7.1f}  p95={p95(runs):7.1f}")
    print(f" Poll latency (ms)  avg={statistics.mean(polls):7.1f}  "
          f"max={max(polls):7.1f}  ({len(polls)} polls)")
    print(f" UI tick gap  (ms)  avg={statistics.mean(gaps):7.1f}  "
          f"max={max(gaps):7.1f}  (target {UI_TICK*1000:.0f})")

    # Thread-safety self check: no job lost or double counted
    ok = (snap["submitted"] == snap["completed"]
          and sum(snap["per_worker"].values()) == snap["completed"])
    print(f" Thread-safety check          : {'PASS' if ok else 'FAIL'} "
          f"(submitted == completed == sum of per-worker counts)")
    print("=" * 84)


if __name__ == "__main__":
    main()
