// GenLayer Project: Agent Reputation Ledger — interactive frontend + backend
// that ACTUALLY interacts with the deployed Intelligent Contract on Bradbury testnet.
//
// Use case: track tamper-resistant reputation for autonomous agents. The backend
// calls the deployed AgentReputationLedger contract (record_outcome / get_reputation)
// using genlayer-js. The frontend lets a user record an outcome and read reputation.

import express from "express";
import { createClient } from "genlayer-js";
import { testnetBradbury } from "genlayer-js/chains";
import { privateKeyToAccount } from "viem/accounts";
import { readFileSync } from "fs";

// --- Config -----------------------------------------------------------------
const LEDGER_ADDRESS = "0x963C5A985cA799B3dCd8b2f0cC280d3225dDb6c5"; // deployed reputation ledger (corrected consensus)
const KEYSTORE = "/home/administrator/.genlayer/keystores/testwallet.json";
const KEY_PASSWORD = "genlayer2026"; // keystore password set at import time

// --- Wallet (test wallet, separate from main) --------------------------------
import { scryptSync, createDecipheriv } from "crypto";
import { keccak256 } from "viem";
import { toBytes } from "viem";

// Decrypt a geth-style v3 keystore ({ Crypto: {...} }, capital C) produced by the genlayer CLI.
function decryptKeystoreV3(ks, password) {
  const c = ks.Crypto || ks.crypto;
  const kdfparams = c.kdfparams;
  const salt = Buffer.from(kdfparams.salt, "hex");
  const derivedKey = scryptSync(Buffer.from(password, "utf8"), salt, kdfparams.dklen, {
    N: kdfparams.n, r: kdfparams.r, p: kdfparams.p, maxmem: 256 * 1024 * 1024,
  });
  const ciphertext = Buffer.from(c.ciphertext, "hex");
  const iv = Buffer.from(c.cipherparams.iv, "hex");
  const decipher = createDecipheriv(c.cipher, derivedKey.slice(0, 16), iv);
  const key = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  const mac = Buffer.from(c.mac, "hex");
  const macCheck = keccak256(toBytes("0x" + Buffer.concat([derivedKey.slice(16, 32), ciphertext]).toString("hex")));
  const macCheckHex = Buffer.from(macCheck.replace(/^0x/, ""), "hex");
  if (!mac.equals(macCheckHex)) throw new Error("keystore mac mismatch");
  return "0x" + key.toString("hex");
}

const keystoreJson = JSON.parse(readFileSync(KEYSTORE, "utf8"));
const privateKey = decryptKeystoreV3(keystoreJson, KEY_PASSWORD);
const account = privateKeyToAccount(privateKey);

// --- GenLayer client ---------------------------------------------------------
const client = createClient({ chain: testnetBradbury });
client.account = account;

// --- Express app -------------------------------------------------------------
const app = express();
app.use(express.json());
app.use(express.static("public"));

// Record a verified outcome on-chain (write)
app.post("/api/record", async (req, res) => {
  try {
    const { agent, outcome, evidence_url } = req.body;
    if (!["SUCCESS", "FAIL", "DISPUTED_LOST"].includes(outcome)) {
      return res.status(400).json({ error: "invalid outcome" });
    }
    const txHash = await client.writeContract({
      address: LEDGER_ADDRESS,
      functionName: "record_outcome",
      args: [agent, outcome, evidence_url],
      value: 0n,
      account,
    });
    res.json({ txHash });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

// Read reputation (read)
app.get("/api/reputation/:agent", async (req, res) => {
  try {
    const result = await client.readContract({
      address: LEDGER_ADDRESS,
      functionName: "get_reputation",
      args: [req.params.agent],
      account,
    });
    res.json({ reputation: result });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Reputation app on http://localhost:${PORT}`));
