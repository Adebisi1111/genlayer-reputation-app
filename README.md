# Agent Reputation Ledger — Interactive App

A working application that **actually interacts with a deployed GenLayer Intelligent Contract** on the Bradbury testnet. It is the app layer for the *Agent Reputation Ledger* — a consensus-verified reputation system for autonomous agents.

## What it does

- **Records outcomes** — submits a real `record_outcome` transaction to the deployed contract. The contract only records the outcome after GenLayer consensus verifies the claim against live evidence (equivalence principle: `gl.nondet.web.render` + `gl.nondet.exec_prompt` + `gl.vm.run_nondet`).
- **Reads reputation** — calls `get_reputation` on the live contract and returns the agent's on-chain record (jobs, successes, disputes, score, tier).

This is genuine app logic talking to GenLayer — not a static visualization.

## Security model — per-user wallet signing (Portal-steward compliant)

This app implements **per-user wallet signing**, the model requested by the GenLayer Portal review:

- **The server holds NO private keys and signs NOTHING.** `server.js` is a stateless, read-only relay: it serves the static UI and proxies the read-only `get_reputation` view. It cannot send value or sign any transaction.
- **All writes are signed in the user's own browser** via `genlayer-js` + MetaMask (`client.connect()` → `window.ethereum`). The connected wallet is the on-chain signer for `record_outcome`. The browser user — not a backend wallet — pays gas.
- **No unauthenticated spend is possible:** there is no backend key to spend, and write endpoints do not exist server-side.
- **Testnet only.** The app targets GenLayer Bradbury testnet; no mainnet value is at risk.

## Architecture

- `server.js` — Node + Express, **read-only relay**. `createClient({ chain: testnetBradbury })` with no account. Serves `public/` and `GET /api/reputation/:agent` (view call only).
- `public/index.html` — brown/butter UI. "Connect Wallet" uses `genlayer-js` `connect()` (MetaMask). `record_outcome` runs client-side via `client.writeContract` with the user's account.
- Endpoints:
  - `GET /api/reputation/:agent` → reads live contract state (view, no key, no value)
  - Writes (`record_outcome`) → executed in-browser by the user's wallet

## Run locally

```bash
npm install
npm start
# open http://localhost:3000 and click "Connect Wallet" (MetaMask on Bradbury testnet)
```

## Deployed contract

- **Agent Reputation Ledger** (corrected consensus): `0xFd714076A377cb6cc23B809a0Fb66e001D5aD409`
- Explorer: https://explorer-bradbury.genlayer.com/address/0xFd714076A377cb6cc23B809a0Fb66e001D5aD409
- Contract source + tests: https://github.com/Adebisi1111/genlayer-reputation-ledger

## Use case

Autonomous agents increasingly perform jobs for each other and for humans. Reputation must be **tamper-resistant and verifiable** — not self-asserted. This Project stores agent reputation on GenLayer, where every recorded outcome is verified by AI consensus against real evidence before it touches the score. An agent that claims success but whose evidence says otherwise is rejected. That makes the reputation ledger a trustworthy primitive for agent marketplaces, escrow, and delegation.
