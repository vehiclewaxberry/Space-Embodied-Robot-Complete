import copy
import json
import tempfile
from pathlib import Path

import yaml

from case_factory import (
    TEST_VECTOR_KEY,
    TEST_VECTOR_KEY_ID,
    decide_test_vector,
    make_case,
    rehash_case,
)
from safety_core import (
    MODULE,
    REPO,
    authorization_mac_hex,
    decide,
    load_policy,
    response_sha256,
    verify_authorization,
)


def test_t11_nominal_safe_is_allowed():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    response = decide_test_vector(request, evidence)
    assert response["physical_state"] == "SAFE"
    assert response["decision"] == "ALLOW"
    return 0.0


def test_t12_modify_has_frozen_boundary():
    request, evidence = make_case("N2_NORMAL_MODIFY")
    response = decide_test_vector(request, evidence)
    assert response["physical_state"] == "SAFE"
    assert response["decision"] == "MODIFY"
    assert response["modified_action"]["boundary_policy_id"] == "MOD-EXACT-SOLVER-V1"
    return 0.0


def test_t13_identical_input_is_bitwise_deterministic():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    first = decide_test_vector(
        copy.deepcopy(request), copy.deepcopy(evidence))
    second = decide_test_vector(
        copy.deepcopy(request), copy.deepcopy(evidence))
    assert response_sha256(first) == response_sha256(second)
    assert first == second
    return 0.0


def test_t14_unknown_never_allows():
    request, evidence = make_case("X_UNKNOWN")
    response = decide_test_vector(request, evidence)
    assert response["physical_state"] == "UNKNOWN"
    assert response["decision"] not in {"ALLOW", "MODIFY"}
    return 0.0


def test_t15_unsafe_never_allows():
    request, evidence = make_case("X_UNSAFE")
    response = decide_test_vector(request, evidence)
    assert response["physical_state"] == "UNSAFE"
    assert response["decision"] in {"BACKOFF", "ABORT"}
    return 0.0


def test_t16_stale_artifact_waits():
    request, evidence = make_case("B2_STALE_EVIDENCE")
    response = decide_test_vector(request, evidence)
    assert response["physical_state"] == "UNKNOWN"
    assert response["decision"] == "WAIT"
    return 0.0


def test_t17_registry_mismatch_aborts():
    request, evidence = make_case("C1_REGISTRY_MISMATCH")
    response = decide_test_vector(request, evidence)
    assert response["physical_state"] == "UNKNOWN"
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "REGISTRY_HASH_MISMATCH"
    return 0.0


def test_t18_authorization_is_valid_before_expiry():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    response = decide_test_vector(request, evidence)
    assert verify_authorization(
        response, evidence["decision_time"],
        TEST_VECTOR_KEY, TEST_VECTOR_KEY_ID)
    return 0.0


def test_t19_authorization_expires():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    response = decide_test_vector(request, evidence)
    assert not verify_authorization(
        response, "2026-07-19T00:06:00Z",
        TEST_VECTOR_KEY, TEST_VECTOR_KEY_ID)
    return 0.0


def test_t20_reason_code_is_digest_bound():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    response = decide_test_vector(request, evidence)
    response["reason_code"] = "TAMPERED_REASON"
    response["reason_codes"][0] = "TAMPERED_REASON"
    assert not verify_authorization(
        response, evidence["decision_time"],
        TEST_VECTOR_KEY, TEST_VECTOR_KEY_ID)
    return 0.0


def test_t21_authorizations_have_complete_provenance():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    response = decide_test_vector(request, evidence)
    assert response["provenance"]["complete"]
    assert len(response["provenance"]["records"]) == 2
    assert all(
        record["gate_json_hash_mode"] == "CANONICAL_JSON_SHA256_V1"
        for record in response["provenance"]["records"])
    assert all(
        record["model_level"] == "L1"
        and record["certification"] == "PROVISIONAL"
        and "provisional_flags" in record
        and "flex_status" in record
        for record in response["provenance"]["records"])
    assert len(response["evidence_hashes"]) >= 3
    return 0.0


def test_t22_unverified_modification_aborts():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    evidence["required_modification"] = {
        "kind": "USE_EXACT_SOLVER",
        "solver": "EXACT_SOLVER",
        "boundary_policy_id": "MOD-EXACT-SOLVER-V1",
    }
    rehash_case(request, evidence)
    response = decide_test_vector(request, evidence)
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "MODIFICATION_BOUNDARY_UNVERIFIED"
    return 0.0


def _temporary_reformatted_artifacts(request, evidence):
    policy = load_policy()
    temporary = tempfile.TemporaryDirectory(
        prefix="rehash_", dir=MODULE / "results")
    temp = Path(temporary.name)
    for artifact_id in ("sim11", "sim12"):
        source = REPO / policy["gate_artifacts"][artifact_id]["path"]
        target = temp / source.name
        document = json.loads(source.read_text(encoding="utf-8"))
        crlf = json.dumps(
            document, indent=7, ensure_ascii=False).replace("\n", "\r\n")
        target.write_bytes(crlf.encode("utf-8"))
        relative = target.relative_to(REPO).as_posix()
        policy["gate_artifacts"][artifact_id]["path"] = relative
        for record in evidence["artifact_records"]:
            if record["artifact_id"] == artifact_id:
                record["gate_json_path"] = relative
    rehash_case(request, evidence)
    policy_path = temp / "policy.yaml"
    policy_path.write_text(yaml.safe_dump(policy, sort_keys=False),
                           encoding="utf-8")
    return temporary, temp, policy_path


def test_t34_gate_json_crlf_lf_and_formatting_are_equivalent():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    temporary, _, policy_path = _temporary_reformatted_artifacts(
        request, evidence)
    try:
        first = decide_test_vector(
            request, evidence, policy_path=policy_path)
        assert first["decision"] == "ALLOW"
        assert all(record["gate_json_hash_mode"] == "CANONICAL_JSON_SHA256_V1"
                   for record in first["provenance"]["records"])
    finally:
        temporary.cleanup()
    return 0.0


def test_t35_gate_json_semantic_tamper_is_blocked_on_next_call():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    temporary, temp, policy_path = _temporary_reformatted_artifacts(
        request, evidence)
    try:
        first = decide_test_vector(
            request, evidence, policy_path=policy_path)
        assert first["decision"] == "ALLOW"
        sim11 = temp / "sim_11_gate_check.json"
        document = json.loads(sim11.read_text(encoding="utf-8"))
        document["verdict"] = "SIM11_GATES_FAIL_TAMPERED"
        sim11.write_text(json.dumps(document, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        second = decide_test_vector(
            request, evidence, policy_path=policy_path)
        assert second["decision"] == "ABORT"
        assert second["reason_code"] == "GATE_ARTIFACT_HASH_MISMATCH"
    finally:
        temporary.cleanup()
    return 0.0


def test_t37_production_without_injected_key_fails_closed():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    response = decide(request, evidence)
    assert response["physical_state"] == "UNKNOWN"
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "AUTHORIZATION_KEY_UNAVAILABLE"
    assert response["authorization"] is None
    return 0.0


def test_t47_short_hmac_key_fails_closed_at_issue_and_verify():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    short_key = b"x" * 31
    response = decide(
        request,
        evidence,
        authorization_key=short_key,
        authorization_key_id="PRODUCTION_SHORT_KEY_TEST",
    )
    assert response["physical_state"] == "UNKNOWN"
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "AUTHORIZATION_KEY_UNAVAILABLE"

    signed = decide_test_vector(request, evidence)
    assert not verify_authorization(
        signed, evidence["decision_time"],
        short_key, TEST_VECTOR_KEY_ID)
    return 0.0


def test_t38_public_recomputation_cannot_forge_hmac():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    response = decide_test_vector(request, evidence)
    assert response["authorization"]["scheme"] == "HMAC-SHA256"
    assert response["authorization"]["key_id"] == TEST_VECTOR_KEY_ID
    assert not verify_authorization(
        response, evidence["decision_time"],
        b"PUBLIC-CHECKSUM-HAS-NO-SECRET", TEST_VECTOR_KEY_ID)
    response["authorization"]["mac_hex"] = authorization_mac_hex(
        response, response["authorization"], b"")
    assert not verify_authorization(
        response, evidence["decision_time"],
        TEST_VECTOR_KEY, TEST_VECTOR_KEY_ID)
    return 0.0


def test_t39_authorization_rejects_unknown_state_and_empty_provenance():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    response = decide_test_vector(request, evidence)
    response["physical_state"] = "UNKNOWN"
    response["authorization"]["mac_hex"] = authorization_mac_hex(
        response, response["authorization"], TEST_VECTOR_KEY)
    assert not verify_authorization(
        response, evidence["decision_time"],
        TEST_VECTOR_KEY, TEST_VECTOR_KEY_ID)

    response = decide_test_vector(request, evidence)
    response["provenance"] = {"complete": False, "records": []}
    response["authorization"]["mac_hex"] = authorization_mac_hex(
        response, response["authorization"], TEST_VECTOR_KEY)
    assert not verify_authorization(
        response, evidence["decision_time"],
        TEST_VECTOR_KEY, TEST_VECTOR_KEY_ID)
    return 0.0


def _temporary_candidate_row_source(request, evidence):
    policy = load_policy()
    temporary = tempfile.TemporaryDirectory(
        prefix="candidate_row_", dir=MODULE / "results")
    temp = Path(temporary.name)
    source = REPO / policy["candidate_binding"]["row_source"]["path"]
    target = temp / "strategy_results.csv"
    target.write_bytes(source.read_bytes())
    relative = target.relative_to(REPO).as_posix()
    policy["candidate_binding"]["row_source"]["path"] = relative
    sim12 = next(
        record for record in evidence["artifact_records"]
        if record["artifact_id"] == "sim12")
    sim12["row_binding"]["source_path"] = relative
    rehash_case(request, evidence)
    policy_path = temp / "policy.yaml"
    policy_path.write_text(
        yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
    return temporary, target, policy_path


def test_t40_candidate_row_is_rehashed_on_every_call():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    temporary, row_source, policy_path = _temporary_candidate_row_source(
        request, evidence)
    try:
        first = decide_test_vector(
            request, evidence, policy_path=policy_path)
        assert first["decision"] == "ALLOW"
        original = row_source.read_text(encoding="utf-8")
        tampered = original.replace(
            "0.12021626868793249", "0.12021626868793250", 1)
        assert tampered != original
        row_source.write_text(tampered, encoding="utf-8")
        second = decide_test_vector(
            request, evidence, policy_path=policy_path)
        assert second["decision"] == "ABORT"
        assert second["reason_code"] == "CANDIDATE_ROW_HASH_MISMATCH"
    finally:
        temporary.cleanup()
    return 0.0


def test_t41_temporal_order_and_deadline_binding_fail_closed():
    request, evidence = make_case("B10_FUTURE_STATE")
    response = decide_test_vector(request, evidence)
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "TEMPORAL_ORDER_INVALID"

    request, evidence = make_case("B11_DEADLINE_REBIND")
    response = decide_test_vector(request, evidence)
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "SCENARIO_HASH_MISMATCH"

    request, evidence = make_case("N1_NORMAL_ALLOW")
    request["decision_deadline"] = "2026-07-19T00:10:00Z"
    rehash_case(request, evidence)
    response = decide_test_vector(request, evidence)
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "DEADLINE_HORIZON_INVALID"
    return 0.0


def test_t42_gate_payload_is_repeatable_and_contains_no_latency():
    from run_gates import evaluate

    first = evaluate()
    second = evaluate()
    assert first == second
    assert "decision_latency_us_observed_not_gated" not in first["metrics"]
    return 0.0


def test_t46_candidate_case_config_is_rehashed_on_every_call():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    policy = load_policy()
    temporary = tempfile.TemporaryDirectory(
        prefix="candidate_case_", dir=MODULE / "results")
    temp = Path(temporary.name)
    try:
        source = REPO / policy["candidate_binding"]["case_source"]["path"]
        target = temp / "strategies_v0.yaml"
        target.write_bytes(source.read_bytes())
        relative = target.relative_to(REPO).as_posix()
        policy["candidate_binding"]["case_source"]["path"] = relative
        sim12 = next(
            record for record in evidence["artifact_records"]
            if record["artifact_id"] == "sim12")
        sim12["row_binding"]["case_config_path"] = relative
        rehash_case(request, evidence)
        policy_path = temp / "policy.yaml"
        policy_path.write_text(
            yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

        first = decide_test_vector(
            request, evidence, policy_path=policy_path)
        assert first["decision"] == "ALLOW"
        original = target.read_text(encoding="utf-8")
        tampered = original.replace("omega_dps: 0.5", "omega_dps: 0.6", 1)
        assert tampered != original
        target.write_text(tampered, encoding="utf-8")
        second = decide_test_vector(
            request, evidence, policy_path=policy_path)
        assert second["decision"] == "ABORT"
        assert second["reason_code"] == (
            "CANDIDATE_CASE_CONFIG_HASH_MISMATCH")
    finally:
        temporary.cleanup()
    return 0.0
