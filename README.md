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
- Deployed Studio dev (61997): `0x7FD4C6eF254c0e42795cd2494deFCcBBb3D7F934`

## Tests

`python3 -m pytest tests/ -q` — 23 passing.

- `tests/test_agent_reputation_ledger.py` — core flow
- `tests/direct/test_ledger_api.py` — the guards that cost an agent money

Each guard is verified by reintroducing the defect and confirming the tests
fail: authorization (3), replay protection (1), evidence dedup (2), slashing
(2), minimum stake (1).

An earlier `tests/direct/sync_ledger_test.py` tested `record_outcome(agent,
outcome, evidence_url)` — an interface this contract does not have. It failed
against the current code while the README still claimed the suite was green.
# rebuild trigger
