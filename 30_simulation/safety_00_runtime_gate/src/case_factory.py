"""Deterministic preregistered SAFE-00 request/evidence cases."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Tuple

from safety_core import (
    candidate_row_claim,
    compute_scenario_hash,
    decide,
    load_policy,
)


NOW = "2026-07-19T00:00:01Z"
CAPTURED = "2026-07-19T00:00:00Z"
VALID = "2026-07-19T00:05:00Z"
DEADLINE = "2026-07-19T00:04:00Z"
EXPIRED = "2026-07-18T23:59:59Z"
TEST_VECTOR_KEY = b"SAFE00-TEST-VECTOR-NOT-A-PRODUCTION-SECRET-V1"
TEST_VECTOR_KEY_ID = "TEST_VECTOR_SAFE00_V1"


def _artifact_record(
    artifact_id: str, scenario_hash: str, row_ref: str,
    provisional_flags: list[str], flex_status: str,
    model_level: str, certification: str,
) -> Dict[str, Any]:
    policy = load_policy()
    artifact = policy["gate_artifacts"][artifact_id]
    return {
        "artifact_id": artifact_id,
        "artifact_scope": artifact["scenario_scope"],
        "gate_json_path": artifact["path"],
        "gate_json_hash_mode": artifact["hash_mode"],
        "gate_json_sha256": artifact["canonical_json_sha256"],
        "gate_verdict": artifact["expected_verdict"],
        "registry_sha256": policy["threshold_registry"]["sha256"],
        "scenario_hash": scenario_hash,
        "data_row_refs": [row_ref],
        "row_binding": (
            candidate_row_claim(policy)
            if artifact["scenario_scope"] == "SCENARIO_ROW"
            else None
        ),
        "valid_until": VALID,
        "model_level": model_level,
        "certification": certification,
        "provisional_flags": provisional_flags,
        "flex_status": flex_status,
    }


def _base() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    policy = load_policy()
    provisional = ["n_modes", "mode_shape", "stiffness_case",
                   "zeta_modal", "contact_T_c"]
    request: Dict[str, Any] = {
        "contract_version": "safety-gate-v1",
        "request_id": "SAFE00-NOMINAL-001",
        "timestamp": CAPTURED,
        "state_estimate": {
            "source": "HARNESS_TRUTH",
            "captured_at": CAPTURED,
            "valid_until": VALID,
            "frame": "SERVICER_BODY_RELATIVE",
            "geometry_class": "G2_cubesat",
            "mu": 0.9166666666666666,
            "omega_dps": 0.5,
            "lambda_actual": 1.0,
            "lambda_grid": 1.0,
            "alpha": 0.0,
            "contact_T_c_ms": 20.0,
            "panel_f1_hz": 1.0005,
            "perception_branch": "HARNESS_TRUTH",
        },
        "state_covariance": {
            "representation": "DIAGONAL_VARIANCES",
            "diagonal": [0.0, 0.0, 0.0],
            "assessment": "PASS",
        },
        "candidate_id": "A_low-S1_passive",
        "proposed_action": {
            "task_action": "CAPTURE",
            "requested_modification": None,
        },
        "model_level": "L1",
        "model_validity": {
            "reported_status": "PASS",
            "reported_in_domain": True,
            "certification": "PROVISIONAL",
            "selection_mode": "EXACT_SOLVER",
            "valid_until": VALID,
            "condition_language": "STRUCTURED_V1",
            "evaluated_conditions": [
                {"metric": "IN_DOMAIN", "operator": "EQ",
                 "value": True, "unit": "BOOLEAN"},
                {"metric": "MODEL_GATE_PASS", "operator": "EQ",
                 "value": True, "unit": "BOOLEAN"},
            ],
            "provisional_flags": provisional,
            "flex_status": "PROVISIONAL",
            "fallback_chain": [],
        },
        "resource_state": {
            "status": "WITHIN_LIMITS",
            "captured_at": CAPTURED,
            "valid_until": VALID,
            "backoff_available": True,
        },
        "decision_deadline": DEADLINE,
        "scenario_hash": "0" * 64,
        "threshold_registry_hash": policy["threshold_registry"]["sha256"],
    }
    evidence = {
        "contract_version": "safety-gate-v1",
        "source_channel": "HARNESS_TRUTH",
        "decision_time": NOW,
        "physical_state": "SAFE",
        "reason_codes": ["HARNESS_RULES_PASS"],
        "required_modification": None,
        "scenario_hash": "0" * 64,
        "artifact_records": [
            _artifact_record(
                "sim11", "0" * 64, "sim11:G1/G4/G5",
                provisional, "PROVISIONAL", "L1", "PROVISIONAL"),
            _artifact_record(
                "sim12", "0" * 64, "A_low|S1_passive",
                [], "UNKNOWN_NOT_IN_CRITERIA", "L1", "PROVISIONAL"),
        ],
    }
    _rehash(request, evidence)
    return request, evidence


def _rehash(request: Dict[str, Any], evidence: Dict[str, Any]) -> None:
    request["scenario_hash"] = compute_scenario_hash(request, evidence)
    evidence["scenario_hash"] = request["scenario_hash"]
    for record in evidence["artifact_records"]:
        record["scenario_hash"] = request["scenario_hash"]


def _as_l2(request: Dict[str, Any], evidence: Dict[str, Any]) -> None:
    policy = load_policy()
    request["model_level"] = "L2"
    request["model_validity"]["reported_status"] = "FAIL"
    request["model_validity"]["certification"] = "UNAVAILABLE"
    request["model_validity"]["provisional_flags"] = []
    request["model_validity"]["flex_status"] = "UNKNOWN_NOT_IN_CRITERIA"
    evidence["physical_state"] = "UNKNOWN"
    evidence["reason_codes"] = ["L2_E15_REPEAT"]
    evidence["artifact_records"] = [
        _artifact_record("e15_ancf", "0" * 64, "e15:overall",
                         [], "UNKNOWN_NOT_IN_CRITERIA",
                         "L2", "UNAVAILABLE"),
        _artifact_record("sim12", "0" * 64, "A_low|S1_passive",
                         [], "UNKNOWN_NOT_IN_CRITERIA",
                         "L2", "UNAVAILABLE"),
    ]
    request["threshold_registry_hash"] = policy["threshold_registry"]["sha256"]
    _rehash(request, evidence)


def make_case(case_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    request, evidence = copy.deepcopy(_base())
    request["request_id"] = case_id
    if case_id == "N1_NORMAL_ALLOW":
        return request, evidence
    if case_id == "N2_NORMAL_MODIFY":
        modification = {
            "kind": "USE_EXACT_SOLVER",
            "solver": "EXACT_SOLVER",
            "boundary_policy_id": "MOD-EXACT-SOLVER-V1",
        }
        request["proposed_action"]["requested_modification"] = modification
        evidence["required_modification"] = copy.deepcopy(modification)
        _rehash(request, evidence)
        return request, evidence
    if case_id == "B1_FORGED_PROVENANCE":
        evidence["artifact_records"][0]["gate_json_sha256"] = "f" * 64
        _rehash(request, evidence)
        return request, evidence
    if case_id == "B2_STALE_EVIDENCE":
        for record in evidence["artifact_records"]:
            record["valid_until"] = EXPIRED
        _rehash(request, evidence)
        return request, evidence
    if case_id == "B3_OUT_OF_DOMAIN":
        request["state_estimate"]["contact_T_c_ms"] = 120.0
        _rehash(request, evidence)
        return request, evidence
    if case_id == "B4_LAMBDA_ROUNDING_SMUGGLING":
        request["state_estimate"]["lambda_actual"] = 0.35
        request["state_estimate"]["lambda_grid"] = 0.5
        request["model_validity"]["selection_mode"] = "GRID_CELL"
        _rehash(request, evidence)
        return request, evidence
    if case_id == "B5_PROVISIONAL_FIELD_MISSING":
        del request["model_validity"]["provisional_flags"]
        return request, evidence
    if case_id == "B6_UNCERTIFIED_L2":
        _as_l2(request, evidence)
        request["model_validity"]["fallback_chain"] = []
        _rehash(request, evidence)
        return request, evidence
    if case_id == "B7_PROSE_CONDITION":
        request["model_validity"]["condition_text"] = "tau_tail >= 0.03 或连续两档不降"
        return request, evidence
    if case_id == "B8_WRONG_ROW_REF":
        sim12 = next(
            record for record in evidence["artifact_records"]
            if record["artifact_id"] == "sim12")
        sim12["data_row_refs"] = ["B_anchor|S1_passive"]
        sim12["row_binding"]["key"]["case"] = "B_anchor"
        _rehash(request, evidence)
        return request, evidence
    if case_id == "B9_ARBITRARY_CANDIDATE":
        request["candidate_id"] = "UNREGISTERED-CANDIDATE"
        _rehash(request, evidence)
        return request, evidence
    if case_id == "B10_FUTURE_STATE":
        request["state_estimate"]["captured_at"] = (
            "2026-07-19T00:00:00.500000Z")
        _rehash(request, evidence)
        return request, evidence
    if case_id == "B11_DEADLINE_REBIND":
        request["decision_deadline"] = "2026-07-19T00:03:59Z"
        return request, evidence
    if case_id == "B12_NO_AUTH_KEY":
        return request, evidence
    if case_id == "D1_L2_TO_L0_UNCHECKED":
        _as_l2(request, evidence)
        request["model_validity"]["fallback_chain"] = [{
            "target_level": "L0",
            "domain_checked": False,
            "reported_in_domain": None,
            "certification": "CERTIFIED",
        }]
        _rehash(request, evidence)
        return request, evidence
    if case_id == "D2_L2_TO_L1_RECHECKED":
        _as_l2(request, evidence)
        request["model_validity"]["fallback_chain"] = [{
            "target_level": "L1",
            "domain_checked": True,
            "reported_in_domain": True,
            "certification": "PROVISIONAL",
        }]
        _rehash(request, evidence)
        return request, evidence
    if case_id == "C1_REGISTRY_MISMATCH":
        request["threshold_registry_hash"] = "0" * 64
        _rehash(request, evidence)
        return request, evidence
    if case_id == "X_UNSAFE":
        evidence["physical_state"] = "UNSAFE"
        evidence["reason_codes"] = ["HARD_CONSTRAINT_FAIL"]
        _rehash(request, evidence)
        return request, evidence
    if case_id == "X_UNKNOWN":
        evidence["physical_state"] = "UNKNOWN"
        evidence["reason_codes"] = ["INDEPENDENT_CHECK_INCONCLUSIVE"]
        _rehash(request, evidence)
        return request, evidence
    raise KeyError(case_id)


def rehash_case(request: Dict[str, Any], evidence: Dict[str, Any]) -> None:
    """Refresh the bound scenario hash after an intentional test mutation."""
    _rehash(request, evidence)


def decide_test_vector(
    request: Dict[str, Any],
    evidence: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """Use the public TEST_VECTOR key; never use this helper in production."""
    return decide(
        request,
        evidence,
        authorization_key=TEST_VECTOR_KEY,
        authorization_key_id=TEST_VECTOR_KEY_ID,
        **kwargs,
    )
