
// Deploy the Agent Reputation Ledger to Studio Next (61997).
// genlayer-js 2.0.0-rc.1 exports studioDevnet natively; 1.1.8 does not.
import fs from 'fs';
import { createClient, createAccount } from 'genlayer-js';
import { studioDevnet } from 'genlayer-js/chains';

const PK = process.env.DEPLOY_PK;
if (!PK) { console.error('DEPLOY_PK not set'); process.exit(1); }
const CONTRACT = process.env.CONTRACT_PATH
  || '/home/administrator/genlayer-reputation-app/contracts/agent_reputation_ledger.py';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function leaderExec(hash) {
  for (let i = 0; i < 30; i++) {
    for (const host of ['explorer-studio-dev.genlayer.com', 'explorer-studio-next.genlayer.com']) {
      try {
        const txt = await (await fetch(`https://${host}/api/transactions/${hash}`)).text();
        if (txt.trim().startsWith('{')) {
          const j = JSON.parse(txt);
          const lr = j?.transaction?.consensus_data?.leader_receipt;
          const e = Array.isArray(lr) ? lr[0] : lr;
          if (e?.execution_result) {
            return {
              exec: e.execution_result,
              result: e.result ? Buffer.from(e.result, 'base64').toString().replace(/^\x00/, '') : '',
            };
          }
        }
      } catch { /* indexing race */ }
    }
    await sleep(7000);
  }
  return { exec: 'UNAVAILABLE', result: '' };
}

const client = createClient({ chain: studioDevnet, account: createAccount(PK) });
const code = fs.readFileSync(CONTRACT);
console.log('chain id   :', studioDevnet.id);
console.log('bytes      :', code.length);

const fees = await client.estimateTransactionFees({});
const tx = await client.deployContract({
  code: new Uint8Array(code),
  args: [],
  fees: { distribution: fees.distribution, feeValue: fees.feeValue },
});
console.log('Deploy TX  :', tx);

const receipt = await client.waitForTransactionReceipt({
  hash: tx, waitUntil: 'decided', retries: 300, interval: 3000, fullTransaction: true,
});
const ca = receipt?.data?.contract_address ?? receipt?.contract_address ?? receipt?.logs?.[0]?.address;
console.log('contract   :', ca);

const { exec, result } = await leaderExec(tx);
console.log('Leader exec:', exec, '|', result.slice(0, 120));
if (exec === 'SUCCESS' && ca) fs.writeFileSync('/tmp/ledger_new.txt', ca);
