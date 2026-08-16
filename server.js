// GenLayer Project: Agent Reputation Ledger — interactive app (OPTION A: per-user wallet signing).
//
// SECURITY MODEL (per GenLayer Portal steward review):
//   This server holds NO private keys and signs NOTHING. It is a stateless
//   read-only relay + static file host. All on-chain WRITES (record_outcome) are
//   signed in the user's own browser via genlayer-js + MetaMask (see public/index.html).
//   The browser user is the on-chain payer/signer, so no unauthenticated endpoint
//   can spend a backend wallet's value. The only state-touching endpoint is
//   /api/reputation/:agent, a read-only view call (no account, no value, no signing).

import express from "express";
import { createClient } from "genlayer-js";
import { testnetBradbury } from "genlayer-js/chains";

// Read-only client — no account attached, so it can never sign or send value.
const client = createClient({ chain: testnetBradbury });

const LEDGER_ADDRESS = "0xFd714076A377cb6cc23B809a0Fb66e001D5aD409"; // deployed reputation ledger (corrected consensus, project instance)

const app = express();
app.use(express.json());
app.use(express.static("public"));

// Read reputation (view only — no account, no value, no signing).
app.get("/api/reputation/:agent", async (req, res) => {
  try {
    const result = await client.readContract({
      address: LEDGER_ADDRESS,
      functionName: "get_reputation",
      args: [req.params.agent],
    });
    res.json({ reputation: result });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Reputation app (read-only relay) on http://localhost:${PORT}`));
