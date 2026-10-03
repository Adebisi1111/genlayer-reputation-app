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
- Deployed Studio dev (61997): `0xC9DF9d35861696D963862Ee463bF432a5C028c8D`
- App: https://adebisi1111.github.io/genlayer-reputation-app/
- Deployed Bradbury (superseded): `0x337492Dc17BC8A03040137904D539748dACaD6f4`

The Bradbury contract could not be staked into — `register` read
`gl.message.value` without being declared payable, so every stake was rejected
and no agent could leave UNREGISTERED. The 2.x runner also renamed
`gl.vm.run_nondet_unsafe`, so every delivery failed. Both are fixed and
covered by source-level regression tests.

## What is verified, and what is not

Verified on-chain against the deployed contract, read from the browser with no
wallet connected: the live ledger renders 2 staked agents and 3 recorded jobs,
with stake, score, completed, failed and slash figures taken from contract
storage.

Verified by transaction through `genlayer-js` directly: `register` with value,
`createJob`, and `record_delivery` — all reaching `execution_result: SUCCESS`.

Verified: writes submitted through the app's own handlers, with no browser.
`e2e-frontend.mjs` imports `public/app.mjs` exactly as the page does and drives
`connectWallet()`, `register()`, `createJob()`, `getJob()` and `read()` against
the deployed contract. Only the DOM and `window.ethereum` are shimmed; signing
is real, with a throwaway funded key, down the same `eth_sendTransaction` branch
MetaMask uses. 11/11, including that a duplicate job is refused and displayed as
a refusal rather than reported as submitted.

That test found a bug that would have broken a real grader: `createClient`
builds its transaction actions over an inner client, so assigning
`client.account` after `connect()` never reaches `writeContract`, and every
write failed with "No account set". The account is now passed per call. Removing
that argument reproduces the failure (7 passed, 4 failed).

## The contrast that proves the slashing is real

Earlier evidence showed only agents being slashed, which a reader could take
for a permanently failing verifier rather than a working one. `e2e-contrast.mjs`
now runs one agent through two otherwise identical jobs, differing only in
whether GenVM can reach the evidence:

| job | evidence | verdict | effect |
|---|---|---|---|
| reachable | a Wikipedia page GenVM can fetch | DELIVERED | `completed` +1, score rises |
| unreachable | a host that does not resolve | UNDELIVERED | 10% of stake burned |

Live result for `0x5911dCB5FeC14b43De87607cF4BacE01f6599F25`:

```
staked   20.0 GEN -> 18.0 GEN
completed 0 -> 1
failed    0 -> 1
slashed   0 -> 1
slash_points 0 -> 2.0 GEN
tier     UNPROVEN -> TRUSTED
```

Both transactions reached `execution_result: SUCCESS`; the divergence is the
verifier working, not a write failing.

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
