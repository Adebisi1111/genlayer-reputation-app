import { createClient } from "genlayer-js";
import { testnetBradbury } from "genlayer-js/chains";

const LEDGER_ADDRESS = "0x337492Dc17BC8A03040137904D539748dACaD6f4";
let client = null;
let account = null;

async function connectWallet(){
  const b = document.getElementById('addr');
  const note = document.getElementById('netNote');
  try {
    if (!window.ethereum) throw new Error("MetaMask is not installed.");
    client = createClient({ chain: testnetBradbury });
    await client.connect('testnetBradbury');
    if (!client.account) {
      const [address] = await window.ethereum.request({ method: "eth_requestAccounts" });
      client.account = { address };
    }
    const address = typeof client.account?.address === "string"
      ? client.account.address
      : (await window.ethereum.request({ method: "eth_accounts" }))[0];
    account = client.account;
    b.textContent = "Connected: " + address;
    note.textContent = "Connected to GenLayer Bradbury testnet.";
    document.getElementById('connectBtn').disabled = true;
  } catch(e){
    b.textContent = "Connect failed";
    note.textContent = "Error: " + e.message;
  }
}

function requireWallet(bar){
  if(!client || !account){ bar.className='status err'; bar.textContent='Connect your wallet first.'; return false; }
  return true;
}

function validateAddress(addr){
  return /^0x[0-9a-fA-F]{40}$/.test(addr);
}

async function register(){
  const st=document.getElementById('registerStatus');
  if(!requireWallet(st)) return;
  const amountInput = document.getElementById('stakeAmount');
  const amount = parseFloat(amountInput.value || "1");
  if (isNaN(amount) || amount < 1) {
    st.className='status err'; st.textContent='Minimum stake is 1 GEN.'; return;
  }
  st.className='status'; st.textContent='Registering — confirm in MetaMask…';
  try{
    const txHash = await client.writeContract({
      address: LEDGER_ADDRESS,
      functionName: "register",
      args: [],
      value: BigInt(Math.floor(amount * 1e18)),
    });
    st.className='status ok'; st.textContent='Registered! Tx: '+txHash;
  }catch(e){ st.className='status err'; st.textContent='Error: '+e.message; }
}

async function createJob(){
  const st=document.getElementById('jobStatus');
  if(!requireWallet(st)) return;
  const jobId = document.getElementById('jobId').value.trim();
  const agent = document.getElementById('jobAgent').value.trim();
  const evidenceUrl = document.getElementById('evidenceUrl').value.trim();
  const claimed = document.getElementById('claimed').value.trim();
  const resolveBlock = parseInt(document.getElementById('resolveBlock').value || "1000");

  if (!jobId) { st.className='status err'; st.textContent='Job ID required.'; return; }
  if (!validateAddress(agent)) { st.className='status err'; st.textContent='Valid agent address required.'; return; }
  if (!evidenceUrl || !evidenceUrl.startsWith('http')) { st.className='status err'; st.textContent='Valid evidence URL required.'; return; }
  if (!claimed) { st.className='status err'; st.textContent='Claimed delivery required.'; return; }
  if (isNaN(resolveBlock) || resolveBlock <= 0) { st.className='status err'; st.textContent='Valid resolve block required.'; return; }

  st.className='status'; st.textContent='Creating job — confirm in MetaMask…';
  try{
    const txHash = await client.writeContract({
      address: LEDGER_ADDRESS,
      functionName: "createJob",
      args: [jobId, agent, evidenceUrl, claimed, resolveBlock],
      value: 0n,
    });
    st.className='status ok'; st.textContent='Job created! Tx: '+txHash;
  }catch(e){ st.className='status err'; st.textContent='Error: '+e.message; }
}

async function record(){
  const st=document.getElementById('recordStatus');
  if(!requireWallet(st)) return;
  const jobId = document.getElementById('recordJobId').value.trim();
  if (!jobId) { st.className='status err'; st.textContent='Job ID required.'; return; }
  st.className='status'; st.textContent='Recording — confirm in MetaMask…';
  try{
    const txHash = await client.writeContract({
      address: LEDGER_ADDRESS,
      functionName: "record_delivery",
      args: [jobId],
      value: 0n,
    });
    st.className='status ok'; st.textContent='Recorded! Tx: '+txHash;
  }catch(e){ st.className='status err'; st.textContent='Error: '+e.message; }
}

async function read(){
  const out=document.getElementById('repOut'); out.textContent='Reading…';
  try{
    const agent = document.getElementById('agentRead').value.trim();
    if (!validateAddress(agent)) { out.textContent='Valid agent address required.'; return; }
    const result = await client.readContract({
      address: LEDGER_ADDRESS,
      functionName: "get_reputation",
      args: [agent],
    });
    out.textContent = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
  }catch(e){ out.textContent='Error: '+e.message; }
}

async function getJob(){
  const out=document.getElementById('jobOut'); out.textContent='Loading…';
  try{
    const jobId = document.getElementById('jobIdRead').value.trim();
    if (!jobId) { out.textContent='Job ID required.'; return; }
    const result = await client.readContract({
      address: LEDGER_ADDRESS,
      functionName: "getJob",
      args: [jobId],
    });
    out.textContent = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
  }catch(e){ out.textContent='Error: '+e.message; }
}

window.connectWallet = connectWallet;
window.register = register;
window.createJob = createJob;
window.record = record;
window.read = read;
window.getJob = getJob;
