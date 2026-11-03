"""
agent_a.py : CodeReviewBot Agent-A (the client that owns the active state)

Run in Terminal 2 (after starting agent_b.py in Terminal 1):
    python agent_a.py

Scenario:
  1. Connect to Agent-B (with retry and backoff).
  2. HELLO handshake.
  3. Transfer the CURRENT STATE (review mode, thresholds, queued files,
     stats) as a serialized STATE_TRANSFER message.
  4. Agent-B proactively answers with a PARAM_UPDATE. Agent-A's reader
     thread applies it autonomously and acknowledges.
  5. Push proactive ALERTs and obey the ACTION that comes back.
  6. Send a REVIEW_REQUEST and receive streamed REVIEW_CHUNKs + result.
  7. Send a deliberately malformed frame to prove the link survives.
  8. Clean BYE.
"""

import argparse
import copy
import queue
import socket
import threading
import time

from protocol import (DEFAULT_HOST, DEFAULT_PORT, REVIEW_MODES,
                      ConnectionClosed, ProtocolError, make_message,
                      read_message, send_message, send_raw_frame)

NAME = "Agent-A"
FINAL_TYPES = {"ACK", "ACTION", "REVIEW_RESULT", "ERROR", "HELLO_ACK",
               "BYE_ACK"}

DEMO_CODE = '''def login(user, pwd):
    password = "admin123"
    try:
        for a in user.items:
            for b in a.tags:
                for c in b.refs:
                    check(c)
    except:
        pass
    return eval(pwd)
'''


def log(tag: str, text: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [{NAME}] [{tag:<5}] {text}",
          flush=True)


class ReviewBotClient:
    def __init__(self, host: str, port: int):
        self.host, self.port = host, port
        self.sock: socket.socket = None
        self.send_lock = threading.Lock()          # main + reader both send
        self.state_lock = threading.Lock()         # guards self.state
        self.pending = {}                          # msg_id -> (Event, [reply])
        self.pending_lock = threading.Lock()
        self.unmatched = queue.Queue()             # replies we did not expect
        self.rtts = []                             # round trip times (ms)

        # ---- the agent's current state (this is what gets transferred) ----
        self.state = {
            "agent_name": "CodeReviewBot-A",
            "review_mode": "COMPLEXITY",
            "available_modes": REVIEW_MODES,
            "streaming": True,
            "runtime": "local",
            "files_queued": ["ui_render.py", "auth.py", "parser.py"],
            "stats": {"reviews_done": 12, "issues_found": 31},
            # strict limit chosen so the demo snippet triggers a finding
            "thresholds": {"max_complexity": 4, "min_doc_coverage": 0.30},
        }

    # -- connection -----------------------------------------------------------
    def connect(self, attempts: int = 5) -> None:
        delay = 0.5
        for n in range(1, attempts + 1):
            try:
                self.sock = socket.create_connection((self.host, self.port),
                                                     timeout=5)
                self.sock.settimeout(None)   # reader thread blocks on recv
                log("INFO", f"connected to {self.host}:{self.port}")
                return
            except OSError as exc:
                log("WARN", f"connect attempt {n}/{attempts} failed: {exc}")
                time.sleep(delay)
                delay *= 2                    # exponential backoff
        raise SystemExit("could not reach Agent-B, is it running?")

    # -- sending ------------------------------------------------------------------
    def send(self, msg_type: str, payload: dict = None,
             in_reply_to: str = None) -> dict:
        msg = make_message(msg_type, NAME, payload, in_reply_to)
        with self.send_lock:
            n = send_message(self.sock, msg)
        log("SEND", f"{msg_type:<14} id={msg['msg_id']} ({n} bytes)")
        return msg

    def request(self, msg_type: str, payload: dict = None,
                timeout: float = 5.0) -> dict:
        """Send and block until the matching final reply arrives."""
        evt, holder = threading.Event(), []
        msg = make_message(msg_type, NAME, payload)
        with self.pending_lock:
            self.pending[msg["msg_id"]] = (evt, holder)
        t0 = time.perf_counter()
        with self.send_lock:
            n = send_message(self.sock, msg)
        log("SEND", f"{msg_type:<14} id={msg['msg_id']} ({n} bytes)")
        if not evt.wait(timeout):
            raise TimeoutError(f"no reply to {msg_type} within {timeout}s")
        rtt = (time.perf_counter() - t0) * 1000
        self.rtts.append(rtt)
        log("RTT", f"{msg_type} round trip {rtt:.1f} ms")
        return holder[0]

    # -- receiving: runs in its own thread -----------------------------------
    def reader_loop(self) -> None:
        try:
            while True:
                try:
                    msg = read_message(self.sock)
                except ProtocolError as exc:
                    log("ERROR", f"bad frame from B: {exc}")
                    continue
                self.on_message(msg)
        except (ConnectionClosed, OSError):
            log("INFO", "reader thread: connection closed")

    def on_message(self, msg: dict) -> None:
        kind, payload = msg["type"], msg["payload"]
        log("RECV", f"{kind:<14} id={msg['msg_id']} "
                    f"reply_to={msg['in_reply_to']}")

        if kind == "PARAM_UPDATE":               # PROACTIVE message from B
            self.apply_param_update(msg)
        elif kind == "REVIEW_CHUNK":             # streamed partial result
            log("CHUNK", f"{payload['seq']}/{payload['of']} "
                         f"{payload['severity']:<8} line {payload['line']}: "
                         f"{payload['rule']} - {payload['message']}")
        elif kind in FINAL_TYPES:
            with self.pending_lock:
                entry = self.pending.pop(msg["in_reply_to"], None)
            if entry:
                entry[1].append(msg)
                entry[0].set()
            else:
                self.unmatched.put(msg)

    def apply_param_update(self, msg: dict) -> None:
        """Autonomous reaction to a remote instruction."""
        new_mode = msg["payload"].get("review_mode")
        if new_mode in REVIEW_MODES:
            with self.state_lock:
                old = self.state["review_mode"]
                self.state["review_mode"] = new_mode
            log("AUTO", f"PARAM_UPDATE applied: mode {old} -> {new_mode} "
                        f"(reason: {msg['payload'].get('reason')})")
            self.send("ACK", {"status": "applied", "review_mode": new_mode},
                      in_reply_to=msg["msg_id"])
        else:
            self.send("ERROR", {"reason": f"unknown mode {new_mode!r}"},
                      in_reply_to=msg["msg_id"])

    def apply_action(self, reply: dict) -> None:
        """Autonomous reaction to an ACTION ordered by Agent-B."""
        p = reply["payload"]
        with self.state_lock:
            self.state["review_mode"] = p.get("trigger_mode",
                                              self.state["review_mode"])
            self.state["stats"]["issues_found"] += 1
        log("AUTO", f"ACTION {p['action']} on {p.get('file')}, "
                    f"mode now {p.get('trigger_mode')}")

    # -- the demo scenario ---------------------------------------------------------
    def run_scenario(self) -> None:
        threading.Thread(target=self.reader_loop, daemon=True).start()

        log("STEP", "1. handshake")
        hello = self.request("HELLO", {"agent": NAME, "role": "orchestrator"})
        log("INFO", f"peer capabilities: {hello['payload']['supports']}")

        log("STEP", "2. transfer current state to Agent-B")
        with self.state_lock:
            snapshot = copy.deepcopy(self.state)
        log("STATE", f"sending mode={snapshot['review_mode']} "
                     f"files={snapshot['files_queued']}")
        ack = self.request("STATE_TRANSFER", snapshot)
        log("INFO", f"B stored state: {ack['payload']}")
        time.sleep(0.4)               # let B's proactive PARAM_UPDATE land
        with self.state_lock:
            log("STATE", f"state after B's update: mode="
                         f"{self.state['review_mode']}")

        log("STEP", "3. push proactive ALERTs, obey the replies")
        r = self.request("ALERT", {"severity": "CRITICAL", "file": "auth.py",
                                   "rule": "HARDCODED_SECRET",
                                   "detail": "API key found in commit C002"})
        if r["type"] == "ACTION":
            self.apply_action(r)
        r = self.request("ALERT", {"severity": "HIGH", "file": "parser.py",
                                   "mode": "PERFORMANCE",
                                   "rule": "NESTED_LOOPS",
                                   "detail": "4 nested loops in C005"})
        if r["type"] == "ACTION":
            self.apply_action(r)
        r = self.request("ALERT", {"severity": "LOW", "file": "ui_render.py",
                                   "rule": "LONG_LINE",
                                   "detail": "112 character line"})
        log("INFO", f"LOW alert answer: {r['type']} {r['payload']}")

        log("STEP", "4. streamed review request")
        res = self.request("REVIEW_REQUEST", {"file_name": "login.py",
                                              "mode": "ALL",
                                              "code": DEMO_CODE})
        log("INFO", f"review finished: {res['payload']}")

        log("STEP", "5. stability test: send a malformed frame")
        with self.send_lock:
            send_raw_frame(self.sock, b"{this is not valid json")
        log("SEND", "RAW garbage frame (22 bytes)")
        try:
            err = self.unmatched.get(timeout=3)
            log("INFO", f"B rejected it with {err['type']}: "
                        f"{err['payload']['reason']}")
        except queue.Empty:
            log("WARN", "no ERROR reply received")
        post = self.request("ALERT", {"severity": "LOW", "file": "config.py",
                                      "rule": "STYLE",
                                      "detail": "link still alive?"})
        log("INFO", f"link survived the bad frame, got {post['type']}")

        log("STEP", "6. clean shutdown")
        self.request("BYE", {"reason": "demo finished"})
        self.sock.close()

        if self.rtts:
            log("PERF", f"{len(self.rtts)} round trips, avg "
                        f"{sum(self.rtts)/len(self.rtts):.1f} ms, "
                        f"max {max(self.rtts):.1f} ms")
        with self.state_lock:
            log("STATE", f"final state: mode={self.state['review_mode']} "
                         f"stats={self.state['stats']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CodeReviewBot Agent-A (client)")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()
    client = ReviewBotClient(args.host, args.port)
    client.connect()
    client.run_scenario()
