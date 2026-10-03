// End-to-end test of the SHIPPED frontend code, with no browser.
//
// This imports public/app.mjs exactly as the page does and drives its own
// register(), createJob(), record(), read() and getJob() handlers. Only the DOM
// is shimmed, plus window.ethereum so connectWallet() has a wallet to talk to.
// Every other line under test is the code a visitor runs.
//
// It exists because a headless browser cannot sign, so the submission path was
// previously unproven. Here the signing is real: the SDK signs with a throwaway
// funded key, exactly as MetaMask would.
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const REPO = path.dirname(fileURLToPath(import.meta.url));
const PK = process.env.UI_PK;
const ON_ADDR = process.env.ON_ADDR;
if (!PK || !ON_ADDR) { console.error('UI_PK and ON_ADDR required'); process.exit(1); }

const { createClient, createAccount } = await import('genlayer-js');
const { studioDevnet } = await import('genlayer-js/chains');
const { createWalletClient, http } = await import('viem');
const wallet = createAccount(PK);
const pub = createWalletClient({ chain: studioDevnet, transport: http(studioDevnet.rpcUrls.default.http[0]) });

// ---------------------------------------------------------------------------
// Minimal DOM. Enough for app.mjs: element ids, textContent, className,
// classList, append, and onclick wiring.
// ---------------------------------------------------------------------------
const nodes = new Map();
function el(id = '') {
  const n = {
    id,
    value: '',
    textContent: '',
    _class: '',
    disabled: false,
    style: {},
    children: [],
    append(...kids) { this.children.push(...kids); },
    appendChild(k) { this.children.push(k); return k; },
    set className(v) { this._class = v; },
    get className() { return this._class; },
    classList: {
      add(c) { const s = new Set(node(id)._class.split(/\s+/).filter(Boolean)); s.add(c); node(id)._class = [...s].join(' '); },
      remove(c) { node(id)._class = node(id)._class.split(/\s+/).filter((x) => x && x !== c).join(' '); },
      contains(c) { return node(id)._class.split(/\s+/).includes(c); },
    },
  };
  if (id) nodes.set(id, n);
  return n;
}
function node(id) {
  if (!nodes.has(id)) nodes.set(id, el(id));
  return nodes.get(id);
}

const IDS = [
  'addr', 'netNote', 'netDot', 'connectBtn', 'ledger', 'jobsWrap', 'stakeAmount',
  'registerStatus', 'jobId', 'jobAgent', 'evidenceUrl', 'claimed', 'resolveBlock',
  'jobStatus', 'recordJobId', 'recordStatus', 'agentRead', 'repOut', 'jobIdRead',
  'jobOut',
];
IDS.forEach(el);

global.document = { getElementById: node };
// Stands in for MetaMask. The SDK's connect() asks for accounts, the chain id,
// and whether the GenLayer snap is installed - it calls Object.values() on the
// snap list, so an undefined return throws inside the SDK, not in our app.
// Signing itself is NOT stubbed: the SDK signs with `wallet` (a real key), so
// the submission path under test is the real one.
global.window = {
  ethereum: {
    request: async ({ method, params }) => {
      switch (method) {
        case 'eth_requestAccounts':
        case 'eth_accounts':
          return [wallet.address];
        case 'eth_chainId':
          return '0xf22d';
        case 'net_version':
          return '61997';
        case 'web3_clientVersion':
          return 'Mozilla/5.0';
        case 'wallet_getSnaps':
          return { 'npm:genlayer': { id: 'npm:genlayer', version: '1.0.0' } };

        // The branch a real MetaMask + GenLayer Snap takes. The SDK sends an
        // unsigned legacy tx here and expects the wallet to sign it, so we sign
        // with the throwaway key and broadcast. This is the SAME SDK code path
        // and the SAME app code path a visitor exercises - only the key differs.
        case 'eth_sendTransaction': {
          const [tx] = params;
          const hash = await pub.sendTransaction({
            account: wallet,
            to: tx.to,
            data: tx.data,
            value: BigInt(tx.value || '0x0'),
            gas: BigInt(tx.gas || '0x5208'),
            nonce: tx.nonce !== undefined ? Number(BigInt(tx.nonce)) : undefined,
            gasPrice: tx.gasPrice ? BigInt(tx.gasPrice) : undefined,
            chainId: studioDevnet.id,
            type: 'legacy',
          });
          return hash;
        }
        default:
          return null;
      }
    },
    on: () => {}, removeListener: () => {},
  },
};

await import(path.join(REPO, 'public', 'app.mjs'));
// app.mjs publishes its handlers on window - that IS what onclick="..." calls,
// so testing them means testing the same functions a visitor triggers.
const app = global.window;

let pass = 0, fail = 0;
const check = (label, ok, detail = '') => {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${detail ? ' :: ' + detail : ''}`);
  ok ? pass++ : fail++;
};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const settled = async (id, tries = 40, gap = 5000) => {
  for (let i = 0; i < tries; i++) {
    await wait(gap);
    const t = node(id).textContent;
    if (t && !/confirm|Registering|Creating|Recording|Reading|Loading/i.test(t)) return t;
  }
  return node(id).textContent;
};

console.log('=== the deployed app bundle loads ===');
check('handlers wired for onclick', ['connectWallet', 'register', 'createJob', 'record', 'read', 'getJob']
  .every((f) => typeof app[f] === 'function'));

console.log('\n=== connectWallet ===');
await app.connectWallet();
await wait(1500);
check('reports the connected address', node('addr').textContent.includes(wallet.address),
  node('addr').textContent.slice(0, 50));
check('names the network', /61997/.test(node('netNote').textContent), node('netNote').textContent);
check('lights the status dot', node('netDot').classList.contains('on'));

// With the app fixed to pass the account per call, the SDK reaches the same
// branch a MetaMask + snap takes: build a legacy tx, hand it to
// eth_sendTransaction, and sign it. Our provider signs with the throwaway key,
// so submission, nonce handling and the leader-receipt wait are all real.
console.log('\n=== register() with real stake ===');
node('stakeAmount').value = '2';
try {
  await app.register();
} catch (e) {
  console.log('  UNCAUGHT register threw:', e.message);
  console.log((e.stack || '').split('\n').slice(0, 6).join('\n'));
}
const regMsg = await settled('registerStatus');
check('stake accepted on-chain', /Staked and registered/i.test(regMsg), regMsg.slice(0, 90));

console.log('\n=== createJob() ===');
const jobId = 'job-e2e-' + Date.now();
node('jobId').value = jobId;
node('jobAgent').value = wallet.address;
node('evidenceUrl').value = 'https://github.com/genlayerlabs/genlayer/pull/42';
node('claimed').value = 'Audit report attached';
node('resolveBlock').value = '1000';
await app.createJob();
const jobMsg = await settled('jobStatus');
check('job created on-chain', /Job created/i.test(jobMsg), jobMsg.slice(0, 90));

console.log('\n=== getJob() reads it back ===');
node('jobIdRead').value = jobId;
await app.getJob();
await wait(1500);
const jobJson = node('jobOut').textContent;
check('getJob returns the job', jobJson.includes(jobId), jobJson.slice(0, 90));
check('job shows as not yet recorded', /"recorded":\s*false/.test(jobJson));

console.log('\n=== read() returns the reputation ===');
node('agentRead').value = wallet.address;
await app.read();
await wait(1500);
const repJson = node('repOut').textContent;
check('get_reputation returns JSON', repJson.includes('"exists": true'), repJson.slice(0, 110));
check('stake was recorded', /"staked":\s*2[0-9]{18}/.test(repJson));

console.log('\n=== a duplicate job is refused, visibly ===');
node('jobId').value = jobId;
node('evidenceUrl').value = 'https://github.com/genlayerlabs/genlayer/pull/43';
await app.createJob();
const dupMsg = await settled('jobStatus');
check('refusal is shown, not swallowed', /Refused|already/i.test(dupMsg), dupMsg.slice(0, 110));

console.log(`\n=== RESULT: ${pass} passed, ${fail} failed ===`);
process.exit(fail === 0 ? 0 : 1);