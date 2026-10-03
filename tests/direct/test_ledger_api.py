"""Tests for the ledger's ACTUAL API: register / createJob / record_delivery.

These replace an earlier file that tested `record_outcome(agent, outcome,
evidence_url)` - an interface this contract does not have. Those tests passed
against a removed API and failed against the current one, while the filename
`sync_ledger_test.py` kept pytest collecting them.

The properties worth protecting here are the ones that cost an agent money or
let one party impersonate another:

  * stake below the minimum cannot register
  * only the AUTHORIZED agent may record a delivery
  * a job records exactly once
  * an evidence URL cannot be reused under a new job id
  * an UNDELIVERED verdict slashes stake and is reflected on-chain
  * a DISPUTED verdict counts as failed without burning stake
"""

import json

ONE_GEN = 1000000000000000000


def _hex(addr) -> str:
    """Only for COMPARING addresses in assertions.

    Never pass this to createJob: the parameter is typed `Address`, and handing
    it a hex string instead of the address object makes the call fail in
    base64 decoding rather than saying so.
    """
    if isinstance(addr, bytes):
        return "0x" + addr.hex()
    if hasattr(addr, "as_hex"):
        return addr.as_hex
    return str(addr)


def _register(contract, vm, who, stake=5 * ONE_GEN):
    vm.sender = who
    vm.value = stake
    contract.register()
    vm.value = 0


def _job(contract, vm, issuer, agent, job_id, evidence, claimed="ship it",
         resolve_block=9999999999):
    vm.sender = issuer
    contract.createJob(job_id, agent, evidence, claimed, resolve_block)


def _decide(vm, decision, body="PR merged and tests pass."):
    vm.clear_mocks()
    vm.mock_web(r".*", {"status": 200, "body": body})
    vm.mock_llm(r".*", json.dumps({"decision": decision}))


# ---------------------------------------------------------------------------
# Registration and stake
# ---------------------------------------------------------------------------


def test_register_requires_the_minimum_stake(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    direct_vm.sender = direct_alice
    direct_vm.value = ONE_GEN - 1
    try:
        contract.register()
        raise AssertionError("expected revert below minimum stake")
    except Exception as exc:
        assert "minimum" in str(exc).lower(), exc

    direct_vm.value = 0
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["exists"] is False, out


def test_register_records_the_staked_amount(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice, stake=5 * ONE_GEN)

    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["exists"] is True, out
    assert out["staked"] == 5 * ONE_GEN, out
    assert out["completed"] == 0 and out["failed"] == 0, out


def test_topping_up_adds_to_the_existing_stake(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice, stake=3 * ONE_GEN)
    _register(contract, direct_vm, direct_alice, stake=2 * ONE_GEN)

    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["staked"] == 5 * ONE_GEN, out


# ---------------------------------------------------------------------------
# Job creation and its guards
# ---------------------------------------------------------------------------


def test_create_job_then_read_it_back(direct_vm, direct_deploy, direct_alice,
                                      direct_bob):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    _job(contract, direct_vm, direct_alice, direct_bob, "j1",
         "https://e.test/repo", claimed="merge the PR")

    job = json.loads(contract.getJob("j1"))
    assert job["exists"] is True, job
    assert job["recorded"] is False, job
    assert _hex(direct_bob).lower() in json.dumps(job).lower(), job


def test_duplicate_job_id_is_refused(direct_vm, direct_deploy, direct_alice,
                                     direct_bob):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    _job(contract, direct_vm, direct_alice, direct_bob, "j1", "https://e.test/a")

    try:
        _job(contract, direct_vm, direct_alice, direct_bob, "j1", "https://e.test/b")
        raise AssertionError("expected revert on duplicate job id")
    except Exception as exc:
        assert "already exists" in str(exc).lower(), exc


def test_evidence_url_cannot_be_reused_under_a_new_id(direct_vm, direct_deploy,
                                                      direct_alice, direct_bob):
    """Otherwise an issuer can re-score the same delivery repeatedly."""
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    _job(contract, direct_vm, direct_alice, direct_bob, "j1", "https://e.test/same")

    try:
        _job(contract, direct_vm, direct_alice, direct_bob, "j2", "https://e.test/same")
        raise AssertionError("expected revert on reused evidence URL")
    except Exception as exc:
        assert "already used" in str(exc).lower(), exc


# ---------------------------------------------------------------------------
# Authorization - the property that matters most
# ---------------------------------------------------------------------------


def test_only_the_authorized_agent_may_record(direct_vm, direct_deploy,
                                              direct_alice, direct_bob,
                                              direct_charlie):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    _register(contract, direct_vm, direct_bob)
    _job(contract, direct_vm, direct_alice, direct_bob, "j1", "https://e.test/x")

    _decide(direct_vm, "DELIVERED")
    direct_vm.sender = direct_charlie
    try:
        contract.record_delivery("j1")
        raise AssertionError("an unauthorized agent recorded a delivery")
    except Exception as exc:
        assert "unauthorized" in str(exc).lower(), exc

    out = json.loads(contract.get_reputation(agent=direct_bob))
    assert out["completed"] == 0, "reputation moved for an unauthorized call"


def test_the_issuer_cannot_record_on_the_agents_behalf(direct_vm, direct_deploy,
                                                       direct_alice, direct_bob):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    _register(contract, direct_vm, direct_bob)
    _job(contract, direct_vm, direct_alice, direct_bob, "j1", "https://e.test/y")

    _decide(direct_vm, "DELIVERED")
    direct_vm.sender = direct_alice
    try:
        contract.record_delivery("j1")
        raise AssertionError("the issuer recorded a delivery for the agent")
    except Exception as exc:
        assert "unauthorized" in str(exc).lower(), exc


# ---------------------------------------------------------------------------
# Verdict effects on reputation and stake
# ---------------------------------------------------------------------------


def test_delivered_increments_completed(direct_vm, direct_deploy, direct_alice,
                                        direct_bob):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    _register(contract, direct_vm, direct_bob, stake=5 * ONE_GEN)
    _job(contract, direct_vm, direct_alice, direct_bob, "j1", "https://e.test/ok")

    _decide(direct_vm, "DELIVERED")
    direct_vm.sender = direct_bob
    contract.record_delivery("j1")

    out = json.loads(contract.get_reputation(agent=direct_bob))
    assert out["completed"] == 1, out
    assert out["staked"] == 5 * ONE_GEN, "a delivered job must not touch stake"


def test_undelivered_slashes_stake(direct_vm, direct_deploy, direct_alice,
                                   direct_bob):
    """The economic core: an undelivered claim burns 10% of stake."""
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    _register(contract, direct_vm, direct_bob, stake=5 * ONE_GEN)
    _job(contract, direct_vm, direct_alice, direct_bob, "j1", "https://e.test/bad")

    _decide(direct_vm, "UNDELIVERED", body="No such PR exists.")
    direct_vm.sender = direct_bob
    contract.record_delivery("j1")

    out = json.loads(contract.get_reputation(agent=direct_bob))
    assert out["failed"] == 1, out
    assert out["slashed_count"] == 1, out
    assert out["staked"] == (5 * ONE_GEN) * 90 // 100, out
    assert out["slash_points"] == (5 * ONE_GEN) * 10 // 100, out


def test_disputed_counts_as_failed_without_burning_stake(direct_vm, direct_deploy,
                                                         direct_alice, direct_bob):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    _register(contract, direct_vm, direct_bob, stake=5 * ONE_GEN)
    _job(contract, direct_vm, direct_alice, direct_bob, "j1", "https://e.test/d")

    _decide(direct_vm, "DISPUTED")
    direct_vm.sender = direct_bob
    contract.record_delivery("j1")

    out = json.loads(contract.get_reputation(agent=direct_bob))
    assert out["failed"] == 1, out
    assert out["slashed_count"] == 0, out
    assert out["staked"] == 5 * ONE_GEN, "a disputed job must not slash"


# ---------------------------------------------------------------------------
# Replay and ordering
# ---------------------------------------------------------------------------


def test_a_job_records_exactly_once(direct_vm, direct_deploy, direct_alice,
                                    direct_bob):
    """Otherwise one delivery could be scored repeatedly to farm reputation."""
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    _register(contract, direct_vm, direct_bob, stake=5 * ONE_GEN)
    _job(contract, direct_vm, direct_alice, direct_bob, "j1", "https://e.test/r")

    _decide(direct_vm, "DELIVERED")
    direct_vm.sender = direct_bob
    contract.record_delivery("j1")

    _decide(direct_vm, "UNDELIVERED", body="contradictory evidence")
    try:
        contract.record_delivery("j1")
        raise AssertionError("a job was recorded twice")
    except Exception as exc:
        assert "already recorded" in str(exc).lower(), exc

    out = json.loads(contract.get_reputation(agent=direct_bob))
    assert out["completed"] == 1 and out["failed"] == 0, out
    assert out["staked"] == 5 * ONE_GEN, out


def test_recording_an_unknown_job_is_refused(direct_vm, direct_deploy,
                                             direct_alice):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    try:
        contract.record_delivery("nope")
        raise AssertionError("expected revert on unknown job")
    except Exception as exc:
        assert "not found" in str(exc).lower(), exc


def test_an_unregistered_agent_cannot_record(direct_vm, direct_deploy,
                                             direct_alice, direct_bob):
    """createJob does not require the agent to be staked, so this must."""
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    _register(contract, direct_vm, direct_alice)
    _job(contract, direct_vm, direct_alice, direct_bob, "j1", "https://e.test/u")

    _decide(direct_vm, "DELIVERED")
    direct_vm.sender = direct_bob
    try:
        contract.record_delivery("j1")
        raise AssertionError("an unstaked agent recorded a delivery")
    except Exception as exc:
        assert "not registered" in str(exc).lower(), exc


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def test_unknown_agent_reads_as_zeroed(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    out = json.loads(contract.get_reputation(agent=direct_alice))
    assert out["exists"] is False, out
    assert out["staked"] == 0 and out["completed"] == 0, out


def test_unknown_job_reads_as_absent(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/_local_pin_ledger.py")
    job = json.loads(contract.getJob("nope"))
    assert job["exists"] is False, job