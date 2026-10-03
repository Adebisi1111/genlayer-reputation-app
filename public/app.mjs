// Agent Reputation Ledger — frontend for Studio dev (61997).
//
// Repointed from Bradbury to the 61997 deployment, because the Bradbury
// contract could not be staked into: `register` was not declared payable, so
// every stake was rejected and no agent could leave UNREGISTERED.
//
// Two things every write needs here:
//   * a non-zero fee distribution. Consensus v0.6 rejects a transaction with
//     none, at admission, with NO_MAJORITY.
//   * reading the leader's `execution_result` rather than the tx status. A
//     status of 5 comes back even when the method raised.
import { createClient } from 'genlayer-js';
import { studioDevnet } from 'genlayer-js/chains';

const LEDGER_ADDRESS = '0xC9DF9d35861696D963862Ee463bF432a5C028c8D';
const CHAIN_NAME = 'studioDevnet';
const EXPLORER = 'https://explorer-studio-dev.genlayer.com';

let client = null;
let account = null;
let feeOpts = null;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fees() {
  if (!feeOpts) {
    const est = await createClient({ chain: studioDevnet }).estimateTransactionFees({});
    feeOpts = { distribution: est.distribution, feeValue: est.feeValue };
  }
  return feeOpts;
}

function validateAddress(addr) {
  return /^0x[0-9a-fA-F]{40}$/.test(addr);
}

function show(el, text, kind) {
  el.textContent = text;
  el.className = 'status' + (kind ? ' ' + kind : '');
}

async function connectWallet() {
  const b = document.getElementById('addr');
  const note = document.getElementById('netNote');
  try {
    if (!window.ethereum) throw new Error('No browser wallet found (MetaMask).');
    client = createClient({ chain: studioDevnet });
    await client.connect(CHAIN_NAME);
    let address = client.account?.address;
    if (!address) {
      const accts = await window.ethereum.request({ method: 'eth_requestAccounts' });
      address = accts[0];
      client.account = { address };
    }
    account = client.account;
    b.textContent = 'Connected: ' + address;
    note.textContent = 'Studio dev 61997';
    document.getElementById('netDot').classList.add('on');
    document.getElementById('connectBtn').disabled = true;
    await loadLedger();
  } catch (e) {
    b.textContent = 'Connect failed';
    note.textContent = 'Error: ' + e.message;
  }
}

function requireWallet(bar) {
  if (!client || !account) {
    show(bar, 'Connect your wallet first.', 'err');
    return false;
  }
  return true;
}

// Submit, then wait for the leader's verdict. A status of 5 means nothing:
// the contract may have refused, and only execution_result says so.
//
// `account` MUST be passed here rather than set on the client. createClient
// builds transactionActions over an INNER client, so writeContract closes over
// that inner object's account - assigning `client.account` after connect() has
// no effect and every write fails with "No account set", including from a real
// MetaMask session. Passing it per call is what the SDK reads.
async function submitWithResult(fn, args, value = 0n) {
  const tx = await client.writeContract({
    account,
    address: LEDGER_ADDRESS,
    functionName: fn,
    args,
    value,
    fees: await fees(),
  });
  for (let i = 0; i < 40; i++) {
    await sleep(5000);
    for (const host of ['explorer-studio-dev.genlayer.com', 'explorer-studio-next.genlayer.com']) {
      try {
        const txt = await (await fetch(`https://${host}/api/transactions/${tx}`)).text();
        if (!txt.trim().startsWith('{')) continue;
        const lr = JSON.parse(txt)?.transaction?.consensus_data?.leader_receipt;
        const e = Array.isArray(lr) ? lr[0] : lr;
        if (!e?.execution_result) continue;
        return {
          tx,
          ok: e.execution_result === 'SUCCESS',
          detail: String(e.genvm_result?.stderr || '').replace(/\n/g, ' | ').slice(-260),
        };
      } catch { /* indexing race */ }
    }
  }
  return { tx, ok: null, detail: 'no leader receipt yet — check the explorer shortly' };
}

function report(bar, res, doneMsg) {
  if (res.ok === true) {
    show(bar, `${doneMsg} Tx: ${res.tx}`, 'ok');
  } else if (res.ok === false) {
    show(bar, `Refused by the contract. ${res.detail || ''}`, 'err');
  } else {
    show(bar, `Submitted — consensus still running. Tx: ${res.tx}`, '');
  }
  loadLedger();
}

async function register() {
  const bar = document.getElementById('registerStatus');
  if (!requireWallet(bar)) return;
  const amount = parseFloat(document.getElementById('stakeAmount').value || '1');
  if (isNaN(amount) || amount < 1) {
    show(bar, 'Minimum stake is 1 GEN.', 'err');
    return;
  }
  show(bar, 'Registering — confirm in your wallet…');
  try {
    const res = await submitWithResult('register', [], BigInt(Math.floor(amount * 1e18)));
    report(bar, res, 'Staked and registered.');
  } catch (e) { show(bar, 'Error: ' + e.message, 'err'); }
}

async function createJob() {
  const bar = document.getElementById('jobStatus');
  if (!requireWallet(bar)) return;
  const jobId = document.getElementById('jobId').value.trim();
  const agent = document.getElementById('jobAgent').value.trim();
  const evidenceUrl = document.getElementById('evidenceUrl').value.trim();
  const claimed = document.getElementById('claimed').value.trim();
  const resolveBlock = parseInt(document.getElementById('resolveBlock').value || '1000', 10);

  if (!jobId) return show(bar, 'Job ID required.', 'err');
  if (!validateAddress(agent)) return show(bar, 'Valid agent address required.', 'err');
  if (!evidenceUrl.startsWith('http')) return show(bar, 'Valid evidence URL required.', 'err');
  if (!claimed) return show(bar, 'Claimed delivery required.', 'err');
  if (isNaN(resolveBlock) || resolveBlock <= 0) return show(bar, 'Valid resolve block required.', 'err');

  show(bar, 'Creating job — confirm in your wallet…');
  try {
    const res = await submitWithResult('createJob', [jobId, agent, evidenceUrl, claimed, resolveBlock]);
    report(bar, res, 'Job created.');
  } catch (e) { show(bar, 'Error: ' + e.message, 'err'); }
}

async function record() {
  const bar = document.getElementById('recordStatus');
  if (!requireWallet(bar)) return;
  const jobId = document.getElementById('recordJobId').value.trim();
  if (!jobId) return show(bar, 'Job ID required.', 'err');
  show(bar, 'Recording — confirm in your wallet…');
  try {
    const res = await submitWithResult('record_delivery', [jobId]);
    report(bar, res, 'Delivery recorded.');
  } catch (e) { show(bar, 'Error: ' + e.message, 'err'); }
}

async function read() {
  const out = document.getElementById('repOut');
  out.textContent = 'Reading…';
  try {
    const agent = document.getElementById('agentRead').value.trim();
    if (!validateAddress(agent)) { out.textContent = 'Valid agent address required.'; return; }
    const result = await client.readContract({
      address: LEDGER_ADDRESS, functionName: 'get_reputation', args: [agent],
    });
    out.classList.remove('empty');
    out.textContent = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
  } catch (e) { out.textContent = 'Error: ' + e.message; }
}

async function getJob() {
  const out = document.getElementById('jobOut');
  out.textContent = 'Loading…';
  try {
    const jobId = document.getElementById('jobIdRead').value.trim();
    if (!jobId) { out.textContent = 'Job ID required.'; return; }
    const result = await client.readContract({
      address: LEDGER_ADDRESS, functionName: 'getJob', args: [jobId],
    });
    out.classList.remove('empty');
    out.textContent = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
  } catch (e) { out.textContent = 'Error: ' + e.message; }
}

// ---------------------------------------------------------------------------
// Live ledger: show real on-chain records without the visitor typing anything
// ---------------------------------------------------------------------------

const KNOWN_AGENTS = [
  ['0x919a9E373A97272D2791be6aFf661902d874bb75', 'Bob — two unsupported claims'],
  ['0x2BEaD74E45B165E8c9f58920AB4f3093C995D253', 'Alice — staked, no claims yet'],
];
const KNOWN_JOBS = [
  ['job-audit-1', 'Bob'],
  ['job-audit-2', 'Bob'],
  ['job-release', 'Alice'],
];

const GEN = 1e18;

function tile(label, value, cls) {
  const d = document.createElement('div');
  d.className = 'stat';
  const l = document.createElement('div');
  l.className = 'stat-l';
  l.textContent = label;
  const v = document.createElement('div');
  v.className = 'stat-v' + (cls ? ' ' + cls : '');
  v.textContent = value;
  d.append(l, v);
  return d;
}

function agentCard(rec, label) {
  const el = document.createElement('div');
  el.className = 'agent';

  const top = document.createElement('div');
  top.className = 'agent-top';
  const name = document.createElement('div');
  name.className = 'agent-name';
  name.textContent = label;
  const tier = document.createElement('span');
  tier.className = 'tier tier-' + String(rec.tier || '').toLowerCase();
  tier.textContent = rec.tier;
  top.append(name, tier);

  const addr = document.createElement('div');
  addr.className = 'agent-addr';
  addr.textContent = rec.agent;

  // Stake leads, because it is what reputation is actually backed by. The
  // slash figures sit beside it in red so the loss is unmissable rather than
  // one more row in a list of same-styled numbers.
  const stats = document.createElement('div');
  stats.className = 'stats';
  stats.append(
    tile('Stake at risk', (rec.staked / GEN).toFixed(2) + ' GEN', 'gen'),
    tile('Score', String(rec.score), rec.score >= 70 ? 'good' : ''),
    tile('Completed', String(rec.completed), rec.completed > 0 ? 'good' : ''),
    tile('Failed', String(rec.failed), rec.failed > 0 ? 'slash' : ''),
  );
  if (rec.slash_points > 0) {
    const wide = document.createElement('div');
    wide.className = 'stat wide';
    const l = document.createElement('div');
    l.className = 'stat-l';
    l.textContent = 'Stake burned by slashing';
    const v = document.createElement('div');
    v.className = 'stat-v slash';
    v.textContent = (rec.slash_points / GEN).toFixed(2) + ' GEN across ' + rec.slashed_count +
      (rec.slashed_count === 1 ? ' claim' : ' claims');
    wide.append(l, v);
    stats.appendChild(wide);
  }

  el.append(top, addr, stats);
  return el;
}

async function loadLedger() {
  const box = document.getElementById('ledger');
  const jobsWrap = document.getElementById('jobsWrap');
  if (!box) return;
  if (!client) client = createClient({ chain: studioDevnet });
  box.innerHTML = '<div class="empty" style="grid-column:1/-1"><span class="spinner"></span>Reading the chain…</div>';
  if (jobsWrap) jobsWrap.innerHTML = '';

  try {
    const agents = [];
    for (const [addr, label] of KNOWN_AGENTS) {
      try {
        const r = await client.readContract({
          address: LEDGER_ADDRESS, functionName: 'get_reputation', args: [addr],
        });
        agents.push([JSON.parse(r), label]);
      } catch { /* skip */ }
    }

    const jobs = [];
    for (const [id, who] of KNOWN_JOBS) {
      try {
        const r = await client.readContract({
          address: LEDGER_ADDRESS, functionName: 'getJob', args: [id],
        });
        const j = JSON.parse(r);
        if (j.exists) jobs.push([j, who]);
      } catch { /* skip */ }
    }

    if (!agents.length) {
      box.innerHTML = '<div class="empty" style="grid-column:1/-1">' +
        'No agents registered yet. Connect a wallet and stake 1 GEN to create the first record.</div>';
      return;
    }

    box.innerHTML = '';
    agents.forEach(([rec, label]) => box.appendChild(agentCard(rec, label)));

    // Jobs live below the agent grid, full width - they read as a list, not cards.
    if (jobs.length && jobsWrap) {
      const jt = document.createElement('div');
      jt.className = 'jobs-title';
      jt.textContent = 'Jobs issued';
      const list = document.createElement('div');
      list.className = 'jobs';
      jobsWrap.append(jt, list);
      for (const [j, who] of jobs) {
        const d = document.createElement('div');
        d.className = 'job' + (j.recorded ? ' done' : ' waiting');
        // build with the DOM, not innerHTML: template concatenation left a
        // dangling '+' that appended the DIV object itself, printing
        // "[object HTMLDivElement]" as the third line of every job.
        const jid = document.createElement('code');
        jid.textContent = j.job_id;
        const meta = document.createElement('span');
        meta.textContent = `${who} · ${j.recorded ? 'recorded' : 'awaiting delivery'}`;
        d.append(jid, meta);
        list.appendChild(d);
      }
    }
  } catch (e) {
    box.innerHTML = '<div class="empty" style="grid-column:1/-1">Could not read the ledger: ' +
      e.message + '</div>';
  }
}

window.connectWallet = connectWallet;
window.register = register;
window.createJob = createJob;
window.record = record;
window.read = read;
window.getJob = getJob;
window.loadLedger = loadLedger;

loadLedger();