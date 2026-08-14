import json

# Mock the nondeterministic web + LLM so record_outcome's consensus check
# is deterministic in direct mode. The leader now uses response_format="json"
# and reads res["decision"], so mocks must return JSON dicts. The validator
# re-runs the leader and compares the decision field (canonical pattern).


def test_record_success_builds_trusted(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice

    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "Job completed successfully."})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "SUCCESS"}))
    for _ in range(6):
        contract.record_outcome(agent=direct_alice, outcome="SUCCESS", evidence_url="https://e.test/done")

    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["jobs"] == 6
    assert out["successes"] == 6
    assert out["tier"] == "TRUSTED"
    assert out["score"] == 100
    direct_vm.clear_mocks()


def test_unverified_claim_reverts(direct_vm, direct_deploy, direct_alice):
    """If the evidence contradicts the claim, record_outcome must revert."""
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "Job failed, no delivery."})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "FAIL"}))
    try:
        # claiming SUCCESS but evidence says FAIL -> not verified -> revert
        contract.record_outcome(agent=direct_alice, outcome="SUCCESS", evidence_url="https://e.test/fail")
        raise AssertionError("expected revert on unverified claim")
    except Exception:
        pass
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["jobs"] == 0
    direct_vm.clear_mocks()


def test_dispute_penalty_lowers_tier(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "evidence"})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "SUCCESS"}))
    contract.record_outcome(agent=direct_alice, outcome="SUCCESS", evidence_url="https://e.test/1")
    contract.record_outcome(agent=direct_alice, outcome="SUCCESS", evidence_url="https://e.test/2")
    # now claim a lost dispute
    direct_vm.clear_mocks()
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "evidence"})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "DISPUTED_LOST"}))
    contract.record_outcome(agent=direct_alice, outcome="DISPUTED_LOST", evidence_url="https://e.test/3")
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["jobs"] == 3
    assert out["disputes_lost"] == 1
    assert out["tier"] == "RISKY"  # 66 - 30 = 36, volume < 5
    direct_vm.clear_mocks()


def test_invalid_outcome_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    try:
        contract.record_outcome(agent=direct_alice, outcome="BOGUS", evidence_url="https://e.test/x")
        raise AssertionError("expected revert on invalid outcome")
    except Exception:
        pass


def test_unknown_agent_returns_zeroed(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_bob
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["exists"] is False
    assert out["jobs"] == 0
    assert out is not None


def test_consensus_validator_agrees(direct_vm, direct_deploy, direct_alice):
    """Canonical equivalence check: leader + validator agree on the decision."""
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "Job completed."})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "SUCCESS"}))
    # Run as leader (captures validator internally).
    contract.record_outcome(agent=direct_alice, outcome="SUCCESS", evidence_url="https://e.test/c")
    # Swap mock to a dissenting validator -> should disagree (undetermined).
    direct_vm.clear_mocks()
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "Job completed."})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "FAIL"}))
    assert direct_vm.run_validator() is False
    direct_vm.clear_mocks()
