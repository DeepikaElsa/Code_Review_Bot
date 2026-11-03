"""
agent_b.py : CodeReviewBot Agent-B (the reviewer / server side)

Run in Terminal 1:
    python agent_b.py            (keeps serving)
    python agent_b.py --once     (exits after the first client says BYE)

What Agent-B does:
  1. Listens on a TCP socket and accepts Agent-A (one thread per client).
  2. Receives Agent-A's STATE_TRANSFER, verifies the checksum, stores it.
  3. PROACTIVELY pushes a PARAM_UPDATE back if the transferred state shows
     sensitive files queued (it decides this on its own).
  4. Reacts autonomously to ALERT messages (block merge, schedule review).
  5. Runs a small rule-based code review for REVIEW_REQUEST and streams
     the findings back as REVIEW_CHUNK messages plus a REVIEW_RESULT.
  6. Survives malformed frames: replies ERROR and keeps the link alive.
"""

import argparse
import re
import socket
import threading
import time
from typing import Dict, List

from protocol import (DEFAULT_HOST, DEFAULT_PORT, ConnectionClosed,
                      ProtocolError, make_message, read_message,
                      send_message)

NAME = "Agent-B"
SENSITIVE_FILES = {"auth.py", "config.py", "db_utils.py"}
REQUIRED_STATE_KEYS = {"agent_name", "review_mode", "available_modes",
                       "files_queued", "thresholds"}


def log(tag: str, text: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] [{NAME}] [{tag:<5}] {text}",
          flush=True)


# ---------------------------------------------------------------------------
# Small rule-based reviewer (the "work" Agent-B does for Agent-A)
# ---------------------------------------------------------------------------
def review_code(code: str, mode: str, thresholds: dict) -> List[Dict]:
    """Returns a list of findings for the requested review mode
    (or every mode when mode == 'ALL')."""
    findings: List[Dict] = []
    lines = code.splitlines()
    run = (lambda m: mode in ("ALL", m))

    if run("SECURITY"):
        for i, line in enumerate(lines, 1):
            if re.search(r"(password|passwd|secret|api_key|token)\s*=\s*[\"'][^\"']+[\"']",
                         line, re.I):
                findings.append({"line": i, "severity": "CRITICAL",
                                 "rule": "HARDCODED_SECRET",
                                 "message": "Credential stored in source code"})
            if re.search(r"\b(eval|exec)\(", line):
                findings.append({"line": i, "severity": "HIGH",
                                 "rule": "DANGEROUS_CALL",
                                 "message": "eval/exec on dynamic input"})

    if run("PERFORMANCE"):
        stack: List[int] = []                 # indents of open loops
        for i, line in enumerate(lines, 1):
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            while stack and indent <= stack[-1]:
                stack.pop()
            if re.match(r"\s*(for|while)\b", line):
                stack.append(indent)
                if len(stack) >= 3:
                    findings.append({"line": i, "severity": "HIGH",
                                     "rule": "NESTED_LOOPS",
                                     "message": f"{len(stack)} nested loops"})

    if run("BUG_DETECTION"):
        for i, line in enumerate(lines, 1):
            if re.match(r"\s*except\s*:", line):
                findings.append({"line": i, "severity": "MEDIUM",
                                 "rule": "BARE_EXCEPT",
                                 "message": "Bare except hides real errors"})

    if run("COMPLEXITY"):
        branches = sum(len(re.findall(r"\b(if|elif|for|while|except|and|or)\b", l))
                       for l in lines)
        limit = thresholds.get("max_complexity", 15)   # from Agent-A's state
        if 1 + branches > limit:
            findings.append({"line": 1, "severity": "MEDIUM",
                             "rule": "HIGH_COMPLEXITY",
                             "message": f"Complexity {1 + branches} exceeds "
                                        f"limit {limit}"})

    if run("DOCUMENTATION"):
        for i, line in enumerate(lines):
            if re.match(r"\s*def\s+\w+", line):
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if not nxt.startswith(('"""', "'''")):
                    findings.append({"line": i + 1, "severity": "LOW",
                                     "rule": "MISSING_DOCSTRING",
                                     "message": "Function has no docstring"})

    if run("STYLE"):
        for i, line in enumerate(lines, 1):
            if len(line) > 100:
                findings.append({"line": i, "severity": "LOW",
                                 "rule": "LONG_LINE",
                                 "message": f"{len(line)} characters"})
    return findings


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
class ReviewerAgent:
    def __init__(self, host: str, port: int, once: bool):
        self.host, self.port, self.once = host, port, once
        self.stop = threading.Event()

    def serve_forever(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Lets us restart immediately without "Address already in use"
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(5)
        srv.settimeout(0.5)           # so the loop can notice self.stop
        log("INFO", f"listening on {self.host}:{self.port}")
        try:
            while not self.stop.is_set():
                try:
                    conn, addr = srv.accept()
                except socket.timeout:
                    continue
                log("INFO", f"connection from {addr[0]}:{addr[1]}")
                threading.Thread(target=self.handle_client,
                                 args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            log("INFO", "Ctrl+C received, shutting down")
        finally:
            srv.close()
            log("INFO", "server socket closed")

    # -- one thread per connected peer ---------------------------------------
    def handle_client(self, conn: socket.socket, addr) -> None:
        conn.settimeout(30)                       # idle timeout
        peer_state: dict = {}
        try:
            while True:
                try:
                    msg = read_message(conn)
                except ProtocolError as exc:
                    log("ERROR", f"rejected bad frame: {exc}")
                    send_message(conn, make_message(
                        "ERROR", NAME, {"reason": str(exc),
                                        "fatal": False}))
                    continue                      # link stays alive
                log("RECV", f"{msg['type']:<14} id={msg['msg_id']} "
                            f"from={msg['sender']}")
                if not self.dispatch(conn, msg, peer_state):
                    break
        except ConnectionClosed:
            log("INFO", f"{addr[0]}:{addr[1]} disconnected")
        except socket.timeout:
            log("WARN", "idle timeout, closing connection")
        except OSError as exc:
            log("ERROR", f"socket error: {exc}")
        finally:
            conn.close()
            if self.once:
                self.stop.set()

    def reply(self, conn, msg_type, payload, to) -> None:
        out = make_message(msg_type, NAME, payload, in_reply_to=to)
        send_message(conn, out)
        log("SEND", f"{msg_type:<14} id={out['msg_id']} reply_to={to}")

    # -- message handlers --------------------------------------------------------
    def dispatch(self, conn, msg, peer_state: dict) -> bool:
        """Returns False when the conversation should end."""
        kind, payload, mid = msg["type"], msg["payload"], msg["msg_id"]

        if kind == "HELLO":
            self.reply(conn, "HELLO_ACK",
                       {"agent": NAME, "role": "reviewer",
                        "supports": ["STATE_TRANSFER", "ALERT",
                                     "REVIEW_REQUEST"]}, mid)

        elif kind == "STATE_TRANSFER":
            missing = REQUIRED_STATE_KEYS - payload.keys()
            if missing:
                self.reply(conn, "ERROR",
                           {"reason": f"state missing keys {sorted(missing)}"},
                           mid)
                return True
            peer_state.clear()
            peer_state.update(payload)
            log("STATE", f"stored state of {payload['agent_name']}: "
                         f"mode={payload['review_mode']} "
                         f"files={payload['files_queued']} "
                         f"thresholds={payload['thresholds']}")
            self.reply(conn, "ACK", {"status": "stored",
                                     "fields": len(payload),
                                     "checksum_verified": True}, mid)
            # PROACTIVE behaviour: B decides by itself to push a change
            risky = [f for f in payload["files_queued"]
                     if f in SENSITIVE_FILES]
            if risky and payload["review_mode"] != "SECURITY":
                log("AUTO", f"sensitive files {risky} queued, "
                            f"pushing PARAM_UPDATE to switch mode")
                out = make_message("PARAM_UPDATE", NAME, {
                    "review_mode": "SECURITY",
                    "reason": f"sensitive files queued: {risky}"})
                send_message(conn, out)
                log("SEND", f"{'PARAM_UPDATE':<14} id={out['msg_id']} "
                            f"(unsolicited)")

        elif kind == "ALERT":
            sev = payload.get("severity", "LOW")
            if sev == "CRITICAL":
                log("AUTO", "CRITICAL alert: ordering merge block")
                self.reply(conn, "ACTION",
                           {"action": "BLOCK_MERGE",
                            "trigger_mode": "SECURITY",
                            "file": payload.get("file")}, mid)
            elif sev == "HIGH":
                log("AUTO", "HIGH alert: scheduling focused review")
                self.reply(conn, "ACTION",
                           {"action": "SCHEDULE_REVIEW",
                            "trigger_mode": payload.get("mode", "BUG_DETECTION"),
                            "file": payload.get("file")}, mid)
            else:
                log("AUTO", f"{sev} alert: logged only")
                self.reply(conn, "ACK", {"status": "logged"}, mid)

        elif kind == "REVIEW_REQUEST":
            mode = payload.get("mode", "ALL")
            fname = payload.get("file_name", "unknown.py")
            findings = review_code(payload.get("code", ""), mode,
                                   peer_state.get("thresholds", {}))
            log("AUTO", f"reviewing {fname} in {mode} mode: "
                        f"{len(findings)} finding(s)")
            for n, f in enumerate(findings, 1):          # streaming
                self.reply(conn, "REVIEW_CHUNK",
                           {"seq": n, "of": len(findings), **f}, mid)
                time.sleep(0.05)
            worst = max((f["severity"] for f in findings),
                        key=["LOW", "MEDIUM", "HIGH", "CRITICAL"].index,
                        default="NONE")
            self.reply(conn, "REVIEW_RESULT",
                       {"file_name": fname, "mode": mode,
                        "total_findings": len(findings),
                        "worst_severity": worst}, mid)

        elif kind in ("ACK", "ERROR"):
            # Peer confirming (or rejecting) something B pushed, e.g. the
            # PARAM_UPDATE. Never answer an ACK or the two sides would
            # ping-pong forever.
            log("INFO", f"peer {kind} for {msg['in_reply_to']}: {payload}")

        elif kind == "BYE":
            self.reply(conn, "BYE_ACK", {"status": "closing"}, mid)
            return False

        else:
            self.reply(conn, "ERROR",
                       {"reason": f"unexpected message type {kind}"}, mid)
        return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CodeReviewBot Agent-B (server)")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--once", action="store_true",
                    help="exit after the first client disconnects")
    args = ap.parse_args()
    ReviewerAgent(args.host, args.port, args.once).serve_forever()
