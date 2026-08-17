import { createClient } from "genlayer-js";
import { testnetBradbury } from "genlayer-js/chains";

const LEDGER_ADDRESS = "0xFd714076A377cb6cc23B809a0Fb66e001D5aD409";
let client = null;
let account = null;

async function connectWallet(){
  const b = document.getElementById('addr');
  const note = document.getElementById('netNote');
  try {
    if (!window.ethereum) throw new Error("MetaMask is not installed. Please install the MetaMask browser extension.");
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
    note.textContent = "Signing with your MetaMask wallet (GenLayer snap) on Bradbury testnet.";
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

async function record(){
  const btn=document.getElementById('recordBtn');
  const st=document.getElementById('recordStatus');
  if(!requireWallet(st)) return;
  btn.disabled=true; st.className='status'; st.textContent='Submitting — confirm in MetaMask…';
  try{
    const txHash = await client.writeContract({
      address: LEDGER_ADDRESS,
      functionName: "record_outcome",
      args: [document.getElementById('agent').value,
             document.getElementById('outcome').value,
             document.getElementById('evidence').value],
      value: 0n,
    });
    st.className='status ok'; st.textContent='Recorded. Tx: '+txHash;
  }catch(e){ st.className='status err'; st.textContent='Error: '+e.message; }
  btn.disabled=false;
}

async function read(){
  const out=document.getElementById('repOut'); out.textContent='Reading…';
  try{
    const agent=document.getElementById('agentRead').value;
    const r=await fetch('/api/reputation/'+agent);
    const d=await r.json();
    out.textContent=JSON.stringify(d,null,2);
  }catch(e){out.textContent='Error: '+e;}
}

window.connectWallet = connectWallet;
window.record = record;
window.read = read;
