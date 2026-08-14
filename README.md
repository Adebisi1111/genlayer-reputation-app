# Agent Reputation Ledger — Interactive App

A working application that **actually interacts with a deployed GenLayer Intelligent Contract** on the Bradbury testnet. It is the app layer for the *Agent Reputation Ledger* — a consensus-verified reputation system for autonomous agents.

## What it does

- **Records outcomes** — submits a real `record_outcome` transaction to the deployed contract. The contract only records the outcome after GenLayer consensus verifies the claim against live evidence (equivalence principle: `gl.nondet.web.render` + `gl.nondet.exec_prompt` + `gl.vm.run_nondet`).
- **Reads reputation** — calls `get_reputation` on the live contract and returns the agent's on-chain record (jobs, successes, disputes, score, tier).

This is genuine app logic talking to GenLayer — not a static visualization.

## Architecture

- `server.js` — Node + Express backend using `genlayer-js` (`createClient({ chain: testnetBradbury })`). Loads the test wallet from the genlayer keystore, exposes two endpoints.
- `public/index.html` — brown/butter UI that calls the backend.
- Endpoints:
  - `GET /api/reputation/:agent` → reads live contract state
  - `POST /api/record` `{ agent, outcome, evidence_url }` → submits a write transaction

## Run locally

```bash
npm install
GENLAYER_KEYSTORE=/path/to/keystore.json GENLAYER_KEYPASS=... npm start
# open http://localhost:3000
```

The backend connects to `testnetBradbury` and signs with the imported test wallet.

## Deployed contract

- **Agent Reputation Ledger** (corrected consensus): `0x963C5A985cA799B3dCd8b2f0cC280d3225dDb6c5`
- Explorer: https://explorer-bradbury.genlayer.com/address/0x963C5A985cA799B3dCd8b2f0cC280d3225dDb6c5
- Contract source + tests: https://github.com/Adebisi1111/genlayer-reputation-ledger

## Use case

Autonomous agents increasingly perform jobs for each other and for humans. Reputation must be **tamper-resistant and verifiable** — not self-asserted. This Project stores agent reputation on GenLayer, where every recorded outcome is verified by AI consensus against real evidence before it touches the score. An agent that claims success but whose evidence says otherwise is rejected. That makes the reputation ledger a trustworthy primitive for agent marketplaces, escrow, and delegation.
