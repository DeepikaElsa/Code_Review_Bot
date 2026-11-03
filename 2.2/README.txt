Assignment 2.2: Distributed Agent Messaging using Sockets
Theme: CodeReviewBot, Agent-A transfers its active state to Agent-B

FILES
    protocol.py   shared wire protocol (framing, JSON, checksum, validation)
    agent_b.py    Agent-B, reviewer / server (Terminal 1)
    agent_a.py    Agent-A, orchestrator / client (Terminal 2)
    agent_a_log.txt, agent_b_log.txt   captured output of both terminals

HOW TO RUN (dual terminal scenario, Python 3.8+, standard library only)
    Terminal 1:  python agent_b.py            (add --once to exit after demo)
    Terminal 2:  python agent_a.py
Optional: --host and --port on both (default 127.0.0.1:5050).

SCENARIO
 1. Agent-A connects (retry with exponential backoff) and sends HELLO.
 2. Agent-A transfers its CURRENT STATE (review mode, 6 available modes,
    queued files, stats, thresholds) as a STATE_TRANSFER message.
 3. Agent-B verifies the checksum, stores it, and on its own initiative
    pushes a PARAM_UPDATE (sensitive file auth.py is queued, so switch to
    SECURITY mode). Agent-A applies it autonomously.
 4. Agent-A pushes proactive ALERTs. Agent-B answers by severity:
    CRITICAL -> ACTION BLOCK_MERGE, HIGH -> ACTION SCHEDULE_REVIEW,
    LOW -> ACK. Agent-A obeys the ACTION and changes its own state.
 5. Agent-A sends a REVIEW_REQUEST. Agent-B uses the thresholds from the
    transferred state and streams REVIEW_CHUNK messages plus a final
    REVIEW_RESULT (matches CodeReviewBot's streaming feature).
 6. A malformed frame is sent on purpose. Agent-B replies ERROR and the
    connection stays alive.
 7. Clean BYE / BYE_ACK shutdown.

RUBRIC MAPPING
Network socket stability (2 marks)
    - TCP sockets with SO_REUSEADDR, listen backlog, accept timeout loop
    - thread per client on the server, reader thread on the client
    - recv_exact() loops until the full frame arrives (TCP is a byte stream)
    - sendall(), idle timeout, connect retry with backoff
    - frame size limit, malformed frame survives, clean close and cleanup
Data serialization and transport (1.5 marks)
    - length prefixed frames: 4 byte big-endian length + UTF-8 JSON
    - typed envelope: version, type, msg_id, in_reply_to, sender, sent_at,
      checksum, payload
    - SHA-256 checksum of the canonical payload, verified on receipt
    - schema validation (required fields, known type, payload is an object)
Proactive remote message handling (1.5 marks)
    - Agent-B pushes PARAM_UPDATE without being asked; Agent-A applies it
    - ALERT triggers an autonomous ACTION decision on Agent-B
    - Agent-A reacts to ACTION by changing its own review mode and stats
    - the state is guarded by a lock because reader and main threads share it

NOTES
 - ACK and ERROR are never answered, which prevents endless ping-pong.
 - Code review rules in Agent-B are simple regex rules, enough to show
   the networking; they are not a full static analyzer.
