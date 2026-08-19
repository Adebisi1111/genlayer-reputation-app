# Agent Reputation Ledger

Stake-weighted reputation primitive with slashing.

## Features
- Authorization: only agent can record own delivery
- Replay protection: each bounty_id recorded once per agent
- Fetch failure handling: bad URLs treated as UNDELIVERED
- Malformed model decisions: default to UNDELIVERED
- Low-score arithmetic: score clamps at 0

## Contract
- `contracts/agent_reputation_ledger.py`
- Deployed Bradbury: `0x029372cd1C6d26FDe883586F056C61dD9FA9190B`

## Tests
- `tests/direct/test_agent_reputation_ledger.py` (8 tests, all passing)
