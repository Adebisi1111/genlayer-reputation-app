import json


def test_register_stake_builds_trusted(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 6000000000000000000
    contract.register()
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "Delivered successfully."})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "DELIVERED"}))
    for i in range(6):
        contract.record_delivery(agent=direct_alice, bounty_id=str(i),
                                 evidence_url="https://e.test/" + str(i),
                                 claimed="done")
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["staked"] == 6000000000000000000
    assert out["completed"] == 6
    assert out["tier"] == "TRUSTED"
    direct_vm.clear_mocks()


def test_undelivered_slashes_stake(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 10000000000000000000
    contract.register()
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "No delivery."})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "UNDELIVERED"}))
    contract.record_delivery(agent=direct_alice, bounty_id="x",
                             evidence_url="https://e.test/fail", claimed="done")
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["slashed_count"] == 1
    assert out["slash_points"] == 1000000000000000000
    assert out["staked"] == 9000000000000000000
    assert out["failed"] == 1
    direct_vm.clear_mocks()


def test_unregistered_agent_reverts(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "ok"})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "DELIVERED"}))
    try:
        contract.record_delivery(agent=direct_alice, bounty_id="1",
                                 evidence_url="https://e.test/1", claimed="x")
        raise AssertionError("expected revert for unregistered agent")
    except Exception:
        pass
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["exists"] is False
    direct_vm.clear_mocks()


def test_authorization_only_agent_can_record(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Steward asked: test unauthorized writes."""
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 6000000000000000000
    contract.register()
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "ok"})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "DELIVERED"}))
    # bob tries to record for alice — should revert (authorization)
    direct_vm.sender = direct_bob
    try:
        contract.record_delivery(agent=direct_alice, bounty_id="1",
                                 evidence_url="https://e.test/1", claimed="x")
        raise AssertionError("expected revert: bob cannot record for alice")
    except Exception as e:
        assert "Unauthorized" in str(e) or "unauthorized" in str(e).lower()
    direct_vm.clear_mocks()


def test_replay_protection_same_bounty_reverts(direct_vm, direct_deploy, direct_alice):
    """Steward asked: test duplicate evidence."""
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 6000000000000000000
    contract.register()
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "Delivered."})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "DELIVERED"}))
    contract.record_delivery(agent=direct_alice, bounty_id="b1",
                             evidence_url="https://e.test/1", claimed="done")
    # try recording same bounty again — should revert (replay protection)
    try:
        contract.record_delivery(agent=direct_alice, bounty_id="b1",
                                 evidence_url="https://e.test/1", claimed="done")
        raise AssertionError("expected revert: same bounty recorded twice")
    except Exception as e:
        assert "already recorded" in str(e).lower() or "replay" in str(e).lower()
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["completed"] == 1
    direct_vm.clear_mocks()


def test_fetch_failure_treated_as_undelivered(direct_vm, direct_deploy, direct_alice):
    """Steward asked: test fetch failures. A bad evidence URL should not revert the tx — it should be treated as UNDELIVERED."""
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 6000000000000000000
    contract.register()
    # mock_web raises -> fetch failure path
    direct_vm.mock_web(r".*bad-url.*", Exception("fetch failed"))
    direct_vm.mock_llm(r".*", json.dumps({"decision": "DELIVERED"}))
    # should NOT revert — fetch failure is caught and treated as UNDELIVERED
    contract.record_delivery(agent=direct_alice, bounty_id="b1",
                             evidence_url="https://bad-url.test/nonexistent", claimed="done")
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["failed"] == 1
    assert out["completed"] == 0
    assert out["slashed_count"] == 1  # slash applies for UNDELIVERED
    direct_vm.clear_mocks()


def test_low_score_dispute_arithmetic(direct_vm, direct_deploy, direct_alice):
    """Steward asked: test low-score dispute arithmetic. Score should clamp at 0, never negative."""
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 1000000000000000000  # minimum stake
    contract.register()
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "No delivery."})
    direct_vm.mock_llm(r".*", json.dumps({"decision": "UNDELIVERED"}))
    # multiple failed disputes drive score down
    for i in range(5):
        contract.record_delivery(agent=direct_alice, bounty_id=str(i),
                                 evidence_url="https://e.test/" + str(i),
                                 claimed="done")
    out = json.loads(contract.get_reputation(agent=direct_alice))
    # score should be 0 (clamped), NOT negative
    assert out["score"] == 0
    assert out["tier"] == "UNPROVEN"
    assert out["failed"] == 5
    direct_vm.clear_mocks()


def test_malformed_model_decision_defaults_undelivered(direct_vm, direct_deploy, direct_alice):
    """Steward asked: reject malformed model decisions. Invalid JSON decision should default to UNDELIVERED."""
    contract = direct_deploy("contracts/agent_reputation_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 6000000000000000000
    contract.register()
    direct_vm.mock_web(r".*e\.test.*", {"status": 200, "body": "evidence"})
    # LLM returns invalid decision (not one of ALLOWED)
    direct_vm.mock_llm(r".*", json.dumps({"decision": "MAYBE"}))
    contract.record_delivery(agent=direct_alice, bounty_id="b1",
                             evidence_url="https://e.test/1", claimed="done")
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["failed"] == 1  # UNDELIVERED (slash applies)
    assert out["completed"] == 0
    direct_vm.clear_mocks()
