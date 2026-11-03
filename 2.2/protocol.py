"""
protocol.py : shared wire protocol for the CodeReviewBot network package

Wire format (every message, both directions):

    +----------------+-------------------------------------+
    | 4 bytes        | N bytes                             |
    | length N (!I)  | UTF-8 JSON envelope                 |
    +----------------+-------------------------------------+

The 4 byte length prefix solves TCP's "stream, not messages" problem:
the receiver always knows exactly how many bytes belong to one message.

JSON envelope:
    {
      "version":     "1.0",
      "type":        "STATE_TRANSFER",     # one of MESSAGE_TYPES
      "msg_id":      "a1b2c3d4",           # unique id of this message
      "in_reply_to": "9f8e7d6c" | null,    # id this message answers
      "sender":      "Agent-A",
      "sent_at":     1761277000.123,       # unix time
      "checksum":    "<sha256 of payload>",# integrity check
      "payload":     { ... typed data ... }
    }
"""

import hashlib
import json
import socket
import struct
import time
import uuid

PROTOCOL_VERSION = "1.0"
HEADER = struct.Struct("!I")          # 4 byte big-endian unsigned length
MAX_FRAME_BYTES = 1_000_000           # refuse absurdly large frames
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5050

# The same 6 review modes used across the CodeReviewBot assessments
REVIEW_MODES = ["SECURITY", "COMPLEXITY", "PERFORMANCE",
                "BUG_DETECTION", "DOCUMENTATION", "STYLE"]

# Typed messages the agents understand
MESSAGE_TYPES = {
    "HELLO", "HELLO_ACK",              # handshake
    "STATE_TRANSFER",                  # Agent-A sends its active parameters
    "ACK",                             # generic confirmation
    "ALERT",                           # proactive event pushed by an agent
    "ACTION",                          # autonomous instruction in response
    "PARAM_UPDATE",                    # proactive parameter change from B
    "REVIEW_REQUEST", "REVIEW_CHUNK",  # review job and streamed partial result
    "REVIEW_RESULT",                   # final review result
    "ERROR",                           # protocol or processing error
    "BYE", "BYE_ACK",                  # clean shutdown
}

REQUIRED_FIELDS = ("version", "type", "msg_id", "in_reply_to",
                   "sender", "sent_at", "checksum", "payload")


class ProtocolError(Exception):
    """Malformed frame, bad JSON, bad schema or checksum mismatch."""


class ConnectionClosed(Exception):
    """Peer closed the socket (cleanly or mid message)."""


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def checksum(payload: dict) -> str:
    """SHA-256 over a canonical JSON form of the payload (sorted keys, no
    spaces) so both sides compute the same digest for the same data."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_message(msg_type: str, sender: str, payload: dict = None,
                 in_reply_to: str = None) -> dict:
    """Builds a typed envelope around a payload."""
    payload = payload if payload is not None else {}
    return {
        "version": PROTOCOL_VERSION,
        "type": msg_type,
        "msg_id": uuid.uuid4().hex[:8],
        "in_reply_to": in_reply_to,
        "sender": sender,
        "sent_at": time.time(),
        "checksum": checksum(payload),
        "payload": payload,
    }


def validate(msg) -> dict:
    """Schema and integrity check for a decoded envelope."""
    if not isinstance(msg, dict):
        raise ProtocolError("envelope is not a JSON object")
    missing = [f for f in REQUIRED_FIELDS if f not in msg]
    if missing:
        raise ProtocolError(f"missing fields: {missing}")
    if msg["version"] != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported version {msg['version']!r}")
    if msg["type"] not in MESSAGE_TYPES:
        raise ProtocolError(f"unknown message type {msg['type']!r}")
    if not isinstance(msg["payload"], dict):
        raise ProtocolError("payload must be a JSON object")
    if checksum(msg["payload"]) != msg["checksum"]:
        raise ProtocolError("checksum mismatch (payload corrupted)")
    return msg


def encode(msg: dict) -> bytes:
    """dict -> length prefixed bytes."""
    body = json.dumps(msg).encode("utf-8")
    return HEADER.pack(len(body)) + body


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
def recv_exact(sock: socket.socket, n: int) -> bytes:
    """recv() may return fewer bytes than asked for, so loop until we
    have exactly n bytes. An empty read means the peer closed."""
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionClosed("peer closed the connection")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def send_message(sock: socket.socket, msg: dict) -> int:
    """Sends one framed message. Returns the number of bytes written."""
    data = encode(msg)
    sock.sendall(data)               # sendall loops until all bytes are out
    return len(data)


def send_raw_frame(sock: socket.socket, body: bytes) -> int:
    """Sends arbitrary bytes inside a valid length frame. Only used to
    test how the peer reacts to garbage (framing stays intact)."""
    data = HEADER.pack(len(body)) + body
    sock.sendall(data)
    return len(data)


def read_message(sock: socket.socket) -> dict:
    """Reads and validates exactly one message."""
    (length,) = HEADER.unpack(recv_exact(sock, HEADER.size))
    if length == 0 or length > MAX_FRAME_BYTES:
        # Framing cannot be trusted any more, caller should close
        raise ProtocolError(f"illegal frame length {length}")
    body = recv_exact(sock, length)
    try:
        msg = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"bad JSON: {exc}") from exc
    return validate(msg)
