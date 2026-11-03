Assignment 2.1: Concurrent Task Daemonization using Threads and Workers
Theme: CodeReviewBot with a background monitor and a worker pool

HOW TO RUN
    python background_agent.py
(Python 3.8+, standard library only. Output is saved in execution_log.txt)

WHAT IT DOES
- Main thread acts as the UI / core event loop. It keeps ticking every
  100 ms and prints a heartbeat each second while all work happens in
  the background.
- RepoMonitor (daemon thread) polls a mock repository every 0.5 s. Each
  new commit becomes a review job (one of the 6 review modes).
- 3 ReviewWorker threads take jobs from a queue and run the reviews.

RUBRIC MAPPING
1. Multi-threading / worker infrastructure (2 marks)
   - threading.Thread subclasses, worker pool of 3, daemon threads
   - jobs handed over through queue.Queue
   - clean shutdown with threading.Event, queue.join() and thread.join()
2. Daemon monitoring (1.5 marks)
   - RepoMonitor runs as a daemon and polls on a fixed interval
   - poll latency is measured with time.perf_counter()
   - Event.wait() is used as an interruptible sleep for instant shutdown
3. Thread safety and concurrency (1.5 marks)
   - queue.Queue for thread-safe job passing
   - threading.Lock around all shared counters and latency lists
   - separate print lock so log lines never interleave
   - each worker has its own random.Random (no shared random state)
   - listeners are fired outside the lock to avoid deadlocks
   - final self check: submitted == completed == sum of per-worker counts

UNIT-2 LINK (Java Beans pattern)
ReviewState works like a bean: state is private, accessed only through
getter/setter style methods, and listeners are notified on property
changes (similar to PropertyChangeSupport).

LATENCY METRICS IN THE LOG
Queue wait, review time, poll latency, and UI tick gap (avg, max, p95).
The UI tick gap staying near 100 ms shows the main loop is never blocked.
