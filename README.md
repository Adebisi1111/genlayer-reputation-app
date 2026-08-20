# Agent Reputation Ledger

Stake-weighted reputation primitive with slashing, authorization, replay protection, and on-chain job creation.

## Workflow
1. **register()** — Agent stakes GEN to register
2. **createJob()** — Issuer creates a job with unique ID + authorized agent
3. **record_delivery()** — Authorized agent records delivery (LLM consensus)

## Safeguards
- Authorization: only agent can record own delivery
- Replay protection: each job recorded once
- Evidence dedup: same evidence URL can't be reused
- Fetch failures: handled safely (UNDELIVERED)
- Malformed decisions: default to UNDELIVERED
- Low-score arithmetic: clamps at 0

## Contract
- `contracts/agent_reputation_ledger.py`
- Deployed Bradbury: `0x337492Dc17BC8A03040137904D539748dACaD6f4`

## Tests
- `tests/direct/test_agent_reputation_ledger.py` (7 tests, all passing)
# rebuild trigger
