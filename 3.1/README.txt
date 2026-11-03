Assignment 3.1: Multi-Agent Coordination Protocol Execution
Theme: CodeReviewBot agents negotiating a review contract

FILES
    multi_agent_negotiation.py   source code (standard library only)
    execution_timeline.txt       captured terminal timeline of both scenarios

HOW TO RUN (Python 3.8+)
    python multi_agent_negotiation.py

THE AGENTS (three instances of the agent class, one thread each)
    Requester    buyer, owns a review job (file, review mode, budget, deadline)
    SecBot       reviewer, security specialist (quality 0.95), expensive
    GeneralBot   reviewer, all rounder (quality 0.60 on SECURITY), cheaper
They share no variables. All communication goes through MessageBus, which
also prints the numbered timeline (T01, T02, ...).

PROTOCOL (Contract Net Protocol plus bilateral bargaining)
    1. CFP                    Requester broadcasts the job
    2. PROPOSE / REFUSE       reviewers bid, or decline if they cannot meet
                              the budget or deadline
    3. AWARD / REJECT_PROPOSAL  Requester ranks bids by utility, shortlists
                              the best and rejects the rest
    4. COUNTER_PROPOSE x N    multi-turn bargaining on price and turnaround
    5. Handshake              ACCEPT_PROPOSAL -> CONFIRM -> FINAL_ACK
                              or NO_DEAL -> FINAL_ACK, then SHUTDOWN

UTILITY FORMULAS (private to each agent, never sent over the bus)
    Requester:  U = 0.40*(1 - price/budget) + 0.25*(1 - time/deadline)
                    + 0.35*quality
    Reviewer:   U = 0.70*(price - cost)/(budget - cost) + 0.30*(time/deadline)
    cost = rate_per_100_lines * lines / 100, reviewer keeps a 10% minimum margin

CONCESSION STRATEGY
    offer(k) = start + (reserve - start) * (k / MAX_ROUNDS)^(1/beta)
    beta < 1 holds firm early (SecBot, 0.7), beta = 1 is linear (Requester).

ACCEPTANCE RULE (both sides)
    Accept an incoming offer if it respects hard limits (feasible) and its
    utility is at least the utility of the offer I would send next.

SCENARIOS
    A  deadline 60 min: SecBot wins the award and the agents agree in
       round 6 (74.0 credits, 37.7 min). GeneralBot is rejected cleanly.
    B  deadline 30 min: SecBot refuses (needs 32 min), GeneralBot cannot
       get below 26.7 min but the Requester's hard limit is 25.5 min, so
       no zone of agreement exists. After 8 rounds the Requester sends
       NO_DEAL, GeneralBot acknowledges, and every thread stops.

RUBRIC MAPPING
    Multi-instance setup stability (1.5)
        3 agent instances spawned as threads with their own inboxes, a
        thread safe bus with a lock, receive timeouts so no thread can
        hang, unknown messages ignored instead of crashing, and all
        threads joined at the end ("threads alive: none").
    Negotiation protocol implementation (2)
        Contract Net phases, FIPA style performatives, utility formulas
        on both sides, time dependent concessions, multi-turn counter
        proposals, hard feasibility limits, award and rejection.
    Consensus handshake termination (1.5)
        Three step handshake (ACCEPT_PROPOSAL, CONFIRM, FINAL_ACK) on
        success, NO_DEAL with acknowledgement on failure, SHUTDOWN to
        every agent, and a round limit so negotiation always ends.

READING THE TIMELINE
    The table at the end of each scenario shows every offer with both
    agents' utilities as bars. You can see the two utility curves move
    toward each other until they cross and a deal is struck.
