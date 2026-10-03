// Demonstrates the slashing contrast the milestone needs:
//   job A, evidence URL that GenVM CAN reach  -> DELIVERED, score rises, no slash
//   job B, evidence URL that GenVM CANNOT reach -> UNDELIVERED, 10% burned
// Before this, both demonstrated agents had only ever been slashed, so a reader
// could not tell a working verifier from a permanently failing one.
import { createClient, createAccount } from 'genlayer-js';
import { studioDevnet } from 'genlayer-js/chains';

const PK = process.env.UI_PK;
const A = '0xC9DF9d35861696D963862Ee463bF432a5C028c8D';
const wallet = createAccount(PK);
const issuer = createAccount(process.env.ISSUER_PK);

const c = createClient({ chain: studioDevnet, account: issuer });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Consensus v0.6 rejects a transaction with no fee distribution at admission
// with FeeValueMustBeNonZero. Estimating is the only reliable way to build one.
const FEES = await createClient({ chain: studioDevnet }).estimateTransactionFees({});
const fees = { distribution: FEES.distribution, feeValue: FEES.feeValue };
console.log('feeValue', String(FEES.feeValue));

async function leaderResult(tx) {
  for (let i = 0; i < 40; i++) {
    await sleep(5000);
    for (const host of ['explorer-studio-dev.genlayer.com', 'explorer-studio-next.genlayer.com']) {
      try {
        const txt = await (await fetch(`https://${host}/api/transactions/${tx}`)).text();
        if (!txt.trim().startsWith('{')) continue;
        // The explorer emits raw newlines inside string values, which is not
        // valid JSON; strip control characters before parsing or the receipt is
        // silently lost and the transaction looks like it produced nothing.
        const clean = txt.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, ' ');
        const lr = JSON.parse(clean)?.transaction?.consensus_data?.leader_receipt;
        const e = Array.isArray(lr) ? lr[0] : lr;
        if (e?.execution_result) return e.execution_result;
      } catch { /* indexing race */ }
    }
  }
  return null;
}

async function rep(addr) {
  const r = await c.readContract({ address: A, functionName: 'get_reputation', args: [addr] });
  return JSON.parse(typeof r === 'string' ? r : JSON.stringify(r, (k, v) => (typeof v === 'bigint' ? v.toString() : v)));
}

// A leader's SUCCESS does not mean the state is readable yet: reads lag the
// verdict by tens of seconds. Recording a delivery before `register` commits
// fails with "Agent not registered", so poll until the agent exists.
async function waitRegistered(addr, tries = 30) {
  for (let i = 0; i < tries; i++) {
    const r = await rep(addr);
    if (r.exists) return r;
    await sleep(5000);
  }
  throw new Error('agent never became registered');
}

const AGENT = wallet.address;
console.log('agent:', AGENT);
// `register` stakes for gl.message.sender_address, so the AGENT must send it.
// Sending it from the issuer stakes the issuer and leaves the agent UNREGISTERED.
const regTx = await c.writeContract({ account: wallet, address: A, functionName: 'register', args: [], value: 5n * 10n ** 18n,
  fees });
const regRes = await leaderResult(regTx);
console.log('register leader result:', regRes, '| tx', regTx);
console.log('registered with 5 GEN as agent');

const before = await waitRegistered(AGENT);
console.log('agent visible on-chain, stake', before.staked);
console.log('BEFORE', JSON.stringify(before));

// A: a URL GenVM is known to reach (see genlayer-web-fetch-guide skill).
// The contract refuses an evidence URL that has been used before, so each run
// needs a distinct URL. Wikipedia is reachable from GenVM (see the
// genlayer-web-fetch-guide skill); GitHub and most CDNs are not.
const goodUrl = 'https://en.wikipedia.org/wiki/Autonomous_agent?run=' + Date.now();
// Unreachable from anywhere, so gl.nondet.web.render raises and the leader
// returns UNDELIVERED. Per-run nonce keeps the evidence-dedup guard happy.
const badUrl = 'https://genlayer-definitely-does-not-exist-9f3a2b.example/audit-' + Date.now() + '.pdf';

const stamp = Date.now();
// Same commit lag as register: wait until the job is actually readable before
// trying to record a delivery against it.
async function issue(jobId, url, claimed) {
  const tx = await c.writeContract({ account: issuer, address: A, functionName: 'createJob',
    args: [jobId, AGENT, url, claimed, 1000],
    fees });
  const res = await leaderResult(tx);
  for (let i = 0; i < 30; i++) {
    const j = await c.readContract({ address: A, functionName: 'getJob', args: [jobId] });
    const parsed = JSON.parse(typeof j === 'string' ? j : JSON.stringify(j, (k, v) => (typeof v === 'bigint' ? v.toString() : v)));
    if (parsed.exists) { console.log('created', jobId, '| leader', res); return; }
    await sleep(5000);
  }
  throw new Error('job never appeared: ' + jobId);
}
await issue('job-reachable-' + stamp, goodUrl, 'A cited source page supporting the claim.');
await issue('job-unreachable-' + stamp, badUrl, 'A deliverable the agent cannot actually produce.');
await sleep(4000);

// The AGENT records delivery, in both cases. Same action, different evidence.
for (const [jobId, label] of [['job-reachable-' + stamp, 'REACHABLE'], ['job-unreachable-' + stamp, 'UNREACHABLE']]) {
  const tx = await c.writeContract({ account: wallet, address: A, functionName: 'record_delivery', args: [jobId],
    fees });
  const res = await leaderResult(tx);
  console.log(`  ${label} recorded | tx ${tx} | leader ${res}`);
}

await sleep(8000);
const after = await rep(AGENT);
console.log('AFTER', JSON.stringify(after));
console.log('DELTA staked  ', (after.staked - before.staked).toFixed(4));
console.log('DELTA completed', after.completed - before.completed);
console.log('DELTA failed   ', after.failed - before.failed);
console.log('DELTA slashed  ', after.slashed_count - before.slashed_count);
console.log('DELTA slashPts ', (after.slash_points - before.slash_points).toFixed(4));
console.log('TIER', before.tier, '->', after.tier);
