# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from dataclasses import dataclass
from genlayer import *

# Stake-Weighted Reputation with Slashing + full edge case handling.
#
# Authorization: only the agent can record their own delivery.
# Replay protection: each bounty_id recorded once per agent.
# Malformed decisions: default to UNDELIVERED.
# Fetch failures: caught and treated as UNDELIVERED (not a NO).


@allow_storage
@dataclass
class AgentRecord:
    staked: u256
    locked_bounties: u256
    completed: u256
    failed: u256
    slashed_count: u256
    slash_points: u256


class AgentReputationLedger(gl.Contract):
    agents: TreeMap[str, AgentRecord]
    # replay protection: "agent:bounty_id" -> "recorded"
    recorded_bounties: TreeMap[str, str]

    def __init__(self):
        pass

    def _repute(self, r: AgentRecord) -> dict:
        total = r.completed + r.failed
        if total == u256(0):
            return {"score": u256(0), "tier": "UNPROVEN", "effective_stake": r.staked}
        base = (r.completed * r.staked) // total
        penalty = r.slash_points
        # Low-score dispute arithmetic: clamp at 0, never negative
        score = base - penalty if base > penalty else u256(0)
        if r.staked >= u256(5000000000000000000) and score >= u256(3000000000000000000):
            tier = "TRUSTED"
        elif r.staked >= u256(1000000000000000000) and score >= u256(500000000000000000):
            tier = "ESTABLISHED"
        elif r.staked >= u256(1000000000000000000):
            tier = "NEW"
        else:
            tier = "UNPROVEN"
        return {"score": score, "tier": tier, "effective_stake": r.staked - penalty}

    def _verify_delivery(self, agent: str, bounty_id: str, evidence_url: str, claimed: str) -> str:
        ALLOWED = ("DELIVERED", "UNDELIVERED", "DISPUTED")

        def leader() -> dict:
            try:
                evidence = gl.nondet.web.render(evidence_url, mode="text")
            except Exception:
                # Fetch failure: malformed URL, network error, 404, etc.
                return {"decision": "UNDELIVERED"}
            prompt = (
                f"Agent {agent} claims delivery of bounty {bounty_id}: {claimed}.\n"
                f"Live evidence from {evidence_url}:\n\n{evidence}\n\n"
                f"Was the obligation fulfilled? Respond as JSON: "
                f'{{"decision": "DELIVERED"|"UNDELIVERED"|"DISPUTED", "reason": "..."}}.'
            )
            res = gl.nondet.exec_prompt(prompt, response_format="json")
            decision = (res.get("decision") or "").strip().upper()
            # Reject malformed model decisions: default to UNDELIVERED
            return {"decision": decision if decision in ALLOWED else "UNDELIVERED"}

        def validator(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            validator_decision = leader()["decision"]
            leader_decision = leader_result.calldata["decision"]
            return validator_decision == leader_decision

        verified = gl.vm.run_nondet_unsafe(leader, validator)
        return verified["decision"]

    @gl.public.write
    def register(self) -> None:
        minimum_stake = u256(1000000000000000000)
        sender = gl.message.sender_address.as_hex
        if gl.message.value < minimum_stake:
            raise Exception("Stake below minimum (1 GEN)")
        rec = self.agents.get(sender, None)
        if rec is None:
            rec = AgentRecord(staked=u256(0), locked_bounties=u256(0),
                              completed=u256(0), failed=u256(0),
                              slashed_count=u256(0), slash_points=u256(0))
        rec.staked += gl.message.value
        self.agents[sender] = rec

    @gl.public.write
    def record_delivery(self, agent: Address, bounty_id: str, evidence_url: str, claimed: str) -> None:
        slash_rate = u256(10)
        slash_divisor = u256(100)
        sender = gl.message.sender_address.as_hex
        agent_hex = Address(agent).as_hex

        # AUTHORIZATION: only the agent themselves can record their own delivery
        if sender != agent_hex:
            raise Exception("Unauthorized: only the agent can record their own delivery.")

        # REPLAY PROTECTION: bounty_id must not have been recorded before
        key = f"{agent_hex}:{bounty_id}"
        if self.recorded_bounties.get(key, "") == "1":
            raise Exception(f"Bounty {bounty_id} already recorded for agent {agent_hex}.")

        rec = self.agents.get(agent_hex, None)
        if rec is None:
            raise Exception("Agent not registered; call register() first.")

        verdict = self._verify_delivery(agent_hex, bounty_id, evidence_url, claimed)
        if verdict == "DELIVERED":
            rec.completed += u256(1)
        elif verdict == "UNDELIVERED":
            rec.failed += u256(1)
            slash_amount = (rec.staked * slash_rate) // slash_divisor
            rec.slashed_count += u256(1)
            rec.slash_points += slash_amount
            rec.staked -= slash_amount
        elif verdict == "DISPUTED":
            rec.failed += u256(1)
        self.agents[agent_hex] = rec
        # mark bounty as recorded for replay protection
        self.recorded_bounties[key] = "1"

    @gl.public.view
    def get_reputation(self, agent: Address) -> str:
        agent_hex = Address(agent).as_hex
        rec = self.agents.get(agent_hex, None)
        if rec is None:
            return json.dumps({"agent": agent_hex, "exists": False,
                               "staked": 0, "completed": 0, "failed": 0,
                               "slashed_count": 0, "slash_points": 0,
                               "score": 0, "tier": "UNREGISTERED", "effective_stake": 0})
        r = self._repute(rec)
        return json.dumps({
            "agent": agent_hex,
            "exists": True,
            "staked": int(rec.staked),
            "completed": int(rec.completed),
            "failed": int(rec.failed),
            "slashed_count": int(rec.slashed_count),
            "slash_points": int(rec.slash_points),
            "score": int(r["score"]),
            "tier": r["tier"],
            "effective_stake": int(r["effective_stake"]),
        })
