import copy
import json

from jsonschema import Draft202012Validator, FormatChecker

from case_factory import decide_test_vector, make_case
from safety_core import (
    EVIDENCE_SCHEMA_PATH,
    REQUEST_SCHEMA_PATH,
    RESPONSE_SCHEMA_PATH,
    compute_scenario_hash,
    load_policy,
    load_schema,
)


def _errors(document, schema_path):
    return list(Draft202012Validator(
        load_schema(schema_path), format_checker=FormatChecker()
    ).iter_errors(document))


def _assert_all_objects_closed(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False, node
        for value in node.values():
            _assert_all_objects_closed(value)
    elif isinstance(node, list):
        for value in node:
            _assert_all_objects_closed(value)


def test_t01_all_schema_objects_are_closed():
    for path in (REQUEST_SCHEMA_PATH, EVIDENCE_SCHEMA_PATH, RESPONSE_SCHEMA_PATH):
        _assert_all_objects_closed(load_schema(path))
    return 0.0


def test_t02_action_vocabulary_is_exactly_five():
    schema = load_schema(RESPONSE_SCHEMA_PATH)
    values = schema["properties"]["decision"]["enum"]
    assert values == ["ALLOW", "MODIFY", "WAIT", "BACKOFF", "ABORT"]
    assert "HOLD" not in values and "INSUFFICIENT_EVIDENCE" not in values
    return len(values)


def test_t03_normal_request_conforms():
    request, _ = make_case("N1_NORMAL_ALLOW")
    errors = _errors(request, REQUEST_SCHEMA_PATH)
    assert not errors, errors
    return 0.0


def test_t04_independent_evidence_conforms():
    _, evidence = make_case("N1_NORMAL_ALLOW")
    errors = _errors(evidence, EVIDENCE_SCHEMA_PATH)
    assert not errors, errors
    return 0.0


def test_t05_normal_response_conforms():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    response = decide_test_vector(request, evidence)
    errors = _errors(response, RESPONSE_SCHEMA_PATH)
    assert not errors, errors
    return 0.0


def test_t06_unknown_request_property_is_rejected():
    request, _ = make_case("N1_NORMAL_ALLOW")
    request["threshold_override"] = 1.0
    assert _errors(request, REQUEST_SCHEMA_PATH)
    return 0.0


def test_t07_legacy_hold_is_rejected():
    request, _ = make_case("N1_NORMAL_ALLOW")
    request["proposed_action"]["task_action"] = "HOLD"
    assert _errors(request, REQUEST_SCHEMA_PATH)
    return 0.0


def test_t08_scenario_hash_binds_decision_fields():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    before = compute_scenario_hash(request, evidence)
    request["state_estimate"]["omega_dps"] += 0.001
    after = compute_scenario_hash(request, evidence)
    assert before != after
    request, evidence = make_case("N1_NORMAL_ALLOW")
    before = compute_scenario_hash(request, evidence)
    evidence["decision_time"] = "2026-07-19T00:00:01.001Z"
    assert before != compute_scenario_hash(request, evidence)
    return 0.0


def test_t09_policy_has_no_threshold_widening():
    policy = load_policy()
    assert policy["thresholds_widened"] is False
    assert policy["status"] == "FROZEN_FOR_SAFE_00_WAVE1"
    assert policy["policy_version"] == "safety-gate-policy-v1.2"
    assert all(
        artifact["hash_mode"] == "CANONICAL_JSON_SHA256_V1"
        and len(artifact["canonical_json_sha256"]) == 64
        for artifact in policy["gate_artifacts"].values()
    )
    assert policy["threshold_registry"]["sha256"] == (
        "400bcedce5af6ad5c4135e67f87bb524ee2fdafb1c26aeae07e495ff387b2873")
    binding = policy["candidate_binding"]
    assert binding["candidate_id"] == "A_low-S1_passive"
    assert binding["row_ref"] == "A_low|S1_passive"
    assert binding["row_source"]["key"] == {
        "case": "A_low", "strategy": "S1_passive"}
    assert policy["time_policy"]["max_clock_skew_s"] == 0.0
    assert policy["authorization"] == {
        "scheme": "HMAC-SHA256",
        "production_key_required": True,
        "minimum_key_bytes": 32,
        "test_vector_key_id": "TEST_VECTOR_SAFE00_V1",
        "test_vector_is_production_secret": False,
    }
    return 0.0


def test_t10_contract_json_is_canonicalizable():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    assert json.loads(json.dumps(request, sort_keys=True)) == request
    assert json.loads(json.dumps(evidence, sort_keys=True)) == evidence
    return 0.0


def test_t36_nominal_capture_state_matches_frozen_a_low_case():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    assert request["candidate_id"] == "A_low-S1_passive"
    assert request["proposed_action"]["task_action"] == "CAPTURE"
    assert request["state_estimate"]["geometry_class"] == "G2_cubesat"
    assert request["state_estimate"]["omega_dps"] == 0.5
    assert request["state_estimate"]["mu"] == 22.0 / 24.0
    sim12 = next(
        record for record in evidence["artifact_records"]
        if record["artifact_id"] == "sim12")
    assert sim12["artifact_scope"] == "SCENARIO_ROW"
    assert sim12["data_row_refs"] == ["A_low|S1_passive"]
    assert sim12["row_binding"]["key"] == {
        "case": "A_low", "strategy": "S1_passive"}
    sim11 = next(
        record for record in evidence["artifact_records"]
        if record["artifact_id"] == "sim11")
    assert sim11["artifact_scope"] == "GLOBAL_GATE_NON_SCENARIO"
    assert sim11["row_binding"] is None
    return 0.0
