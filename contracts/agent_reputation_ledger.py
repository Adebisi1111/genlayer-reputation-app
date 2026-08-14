# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from dataclasses import dataclass
from genlayer import *

# Agent reputation is a reusable primitive for the agentic economy:
# after a job (or a dispute resolution) an agent's outcome is recorded,
# but the claimed outcome is NOT trusted blindly. Instead the contract
# fetches real evidence and asks an LLM to verify the claim, running that
# judgment through GenLayer's equivalence principle (gl.vm.run_nondet) so
# leader and validators must agree. Only verified outcomes move the score.
#
# State is modeled with GenLayer-native TreeMap + u256. The consensus check
# (nondet web fetch + LLM verdict + equivalence) is the genuine GenLayer
# logic that makes this a real primitive, not simple storage.


@allow_storage
@dataclass
class Reputation:
    jobs: u256
    successes: u256
    disputes_lost: u256
    score: u256  # computed, not stored blindly
    tier: str    # TRUSTED / NEUTRAL / RISKY


class AgentReputationLedger(gl.Contract):
    reputations: TreeMap[str, Reputation]

    def __init__(self):
        pass

    def _recompute(self, jobs: u256, successes: u256, disputes_lost: u256):
        # Base: success-rate weighted score (integer math, no floats).
        rate = (successes * u256(100)) // jobs if jobs > u256(0) else u256(0)
        # Penalty for lost disputes (each lost dispute costs 30 points).
        score = rate - (disputes_lost * u256(30))
        if score < u256(0):
            score = u256(0)
        # Tier by score + minimum volume to avoid 1-job flukes.
        if jobs >= u256(5) and score >= u256(80):
            tier = "TRUSTED"
        elif jobs >= u256(1) and score >= u256(40):
            tier = "NEUTRAL"
        else:
            tier = "RISKY"
        return score, tier

    def _verify_outcome(self, agent: str, outcome: str, evidence_url: str) -> bool:
        # Genuine GenLayer consensus (per docs.genlayer.com equivalence-principle):
        # the leader fetches live evidence and asks the LLM for a STRUCTURED
        # decision (JSON). The validator INDEPENDENTLY re-runs the same task and
        # compares only the stable decision field, not the leader's raw output
        # shape. This is the canonical run_nondet_unsafe + decision-field pattern.
        ALLOWED = ("SUCCESS", "FAIL", "DISPUTED_LOST")

        def leader() -> dict:
            evidence = gl.nondet.web.render(evidence_url, mode="text")
            prompt = (
                f"An autonomous agent ({agent}) claims the job outcome was: {outcome}.\n"
                f"Below is the live evidence fetched from {evidence_url}:\n\n"
                f"{evidence}\n\n"
                f"Decide the true outcome based ONLY on the evidence. "
                f"Respond as JSON: {{\"decision\": \"SUCCESS\"|\"FAIL\"|\"DISPUTED_LOST\"}}."
            )
            res = gl.nondet.exec_prompt(prompt, response_format="json")
            # Normalize: ensure a stable decision field.
            decision = (res.get("decision") or "").strip().upper()
            return {"decision": decision if decision in ALLOWED else "FAIL"}

        def validator(leader_result) -> bool:
            # Reject if leader errored.
            if not isinstance(leader_result, gl.vm.Return):
                return False
            # Independently reproduce the leader's task and compare the DECISION
            # field (the substance), not the raw output. This is real consensus.
            validator_decision = leader()["decision"]
            leader_decision = leader_result.calldata["decision"]
            return validator_decision == leader_decision

        verified = gl.vm.run_nondet_unsafe(leader, validator)
        # The on-chain state change only proceeds if the verified decision
        # matches what the caller claimed.
        return verified["decision"] == outcome.upper()

    @gl.public.write
    def record_outcome(self, agent: Address, outcome: str, evidence_url: str) -> None:
        """Record a job outcome for an agent, but only after consensus verifies
        the claim against live evidence.
        outcome must be one of: SUCCESS, FAIL, DISPUTED_LOST"""
        if outcome not in ("SUCCESS", "FAIL", "DISPUTED_LOST"):
            raise Exception("Invalid outcome; use SUCCESS, FAIL, or DISPUTED_LOST")
        agent_hex = Address(agent).as_hex
        # Consensus check: the claimed outcome must be confirmed by the LLM
        # over real evidence (equivalence principle). Unverified claims revert.
        verified = self._verify_outcome(agent_hex, outcome, evidence_url)
        if not verified:
            raise Exception("Outcome claim not verified against evidence; rejected.")
        rec = self.reputations.get(agent_hex, None)
        if rec is None:
            rec = Reputation(jobs=u256(0), successes=u256(0),
                             disputes_lost=u256(0), score=u256(0), tier="RISKY")
        rec.jobs += u256(1)
        if outcome == "SUCCESS":
            rec.successes += u256(1)
        elif outcome == "DISPUTED_LOST":
            rec.disputes_lost += u256(1)
        # FAIL: counts as a job but no success
        rec.score, rec.tier = self._recompute(rec.jobs, rec.successes, rec.disputes_lost)
        self.reputations[agent_hex] = rec

    @gl.public.view
    def get_reputation(self, agent: Address) -> str:
        """View an agent's reputation record as JSON."""
        agent_hex = Address(agent).as_hex
        rec = self.reputations.get(agent_hex, None)
        if rec is None:
            return json.dumps({"agent": agent_hex, "exists": False,
                               "jobs": 0, "successes": 0,
                               "disputes_lost": 0, "score": 0, "tier": "RISKY"})
        return json.dumps({
            "agent": agent_hex,
            "exists": True,
            "jobs": int(rec.jobs),
            "successes": int(rec.successes),
            "disputes_lost": int(rec.disputes_lost),
            "score": int(rec.score),
            "tier": rec.tier,
        })
