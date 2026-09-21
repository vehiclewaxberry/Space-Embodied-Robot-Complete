from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import pair_oracle_backend as backend


PACKAGE = Path(__file__).resolve().parent
FIXTURE_A = PACKAGE / "fixtures" / "BOX_A_10MM.brep"
FIXTURE_B = PACKAGE / "fixtures" / "BOX_B_10MM.brep"
UPSTREAM_CONTRACT = (
    PACKAGE.parent
    / "ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1"
    / "SYSTEM_PAIR_ORACLE_CONTRACT_V1.json"
)
EXCEPTION_PAIR = "FIXTURE::ADJ_A||FIXTURE::ADJ_B"


def pose_x_m(value: float) -> list[float]:
    return [
        1.0, 0.0, 0.0, float(value),
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def geometric_request(x_m: float = 0.02, request_id: str = "TEST") -> dict:
    assert FIXTURE_A.is_file() and FIXTURE_B.is_file(), (
        "synthetic BRep fixtures are missing; run the deterministic builder --write first"
    )
    bindings = backend.synthetic_binding_hashes()
    q = [0.0] * 6
    return {
        "schema": "M01_SYSTEM_PAIR_ORACLE_REQUEST_V1",
        "row_kind": "GEOMETRIC_RESULT",
        "request_id": request_id,
        "pair_id": "FIXTURE::BOX_A||FIXTURE::BOX_B",
        "object_id_a": "FIXTURE::BOX_A",
        "object_id_b": "FIXTURE::BOX_B",
        "q_order": list(backend.Q_ORDER),
        "q_rad_binary64": q,
        "q_bytes_sha256": backend.q_bytes_sha256(q),
        "scene_state": "SYNTHETIC_FIXTURE_SCENE_V1",
        "scene_state_sha256": bindings["scene_state_sha256"],
        "registry_sha256": bindings["registry_sha256"],
        "pair_oracle_contract_sha256": backend.PAIR_CONTRACT_SHA256,
        "allowed_collision_exact_pair_set_sha256": bindings[
            "allowed_collision_exact_pair_set_sha256"
        ],
        "clearance_policy_sha256": bindings["clearance_policy_sha256"],
        "object_a_geometry_path": str(FIXTURE_A),
        "object_b_geometry_path": str(FIXTURE_B),
        "object_a_geometry_asset_sha256": backend.sha256_path(FIXTURE_A),
        "object_b_geometry_asset_sha256": backend.sha256_path(FIXTURE_B),
        "object_a_motion_binding_sha256": bindings["object_a_motion_binding_sha256"],
        "object_b_motion_binding_sha256": bindings["object_b_motion_binding_sha256"],
        "mount_binding_sha256": bindings["mount_binding_sha256"],
        "authorized_pair_min_mm": 5.0,
        "required_clearance_mm": 5.0,
        "object_a_hausdorff_derate_mm": 0.0,
        "object_b_hausdorff_derate_mm": 0.0,
        "backend_numeric_derate_mm": backend.BACKEND_NUMERIC_DERATE_MM,
        "backend_id": backend.BACKEND_ID,
        "backend_version": backend.BACKEND_VERSION,
        "backend_configuration_sha256": bindings["backend_configuration_sha256"],
        "backend_determinism_receipt_sha256": bindings[
            "backend_determinism_receipt_sha256"
        ],
        "geometry_a_pose_S_row_major_binary64": pose_x_m(0.0),
        "geometry_b_pose_S_row_major_binary64": pose_x_m(x_m),
        "pose_frame": "S",
        "pose_translation_unit": "m",
        "brep_native_length_unit": "mm",
        "distance_output_unit": "mm",
        "joint_unit": "rad",
        "exception_exact_pair_ids": [EXCEPTION_PAIR],
        "fixture_only": True,
    }


def exception_request() -> dict:
    bindings = backend.synthetic_binding_hashes()
    q = [0.0] * 6
    return {
        "schema": "M01_SYSTEM_PAIR_ORACLE_REQUEST_V1",
        "row_kind": "EXCEPTION_RESULT",
        "request_id": "EXCEPTION_TEST",
        "pair_id": EXCEPTION_PAIR,
        "object_id_a": "FIXTURE::ADJ_A",
        "object_id_b": "FIXTURE::ADJ_B",
        "q_order": list(backend.Q_ORDER),
        "q_rad_binary64": q,
        "q_bytes_sha256": backend.q_bytes_sha256(q),
        "scene_state": "SYNTHETIC_FIXTURE_SCENE_V1",
        "scene_state_sha256": bindings["scene_state_sha256"],
        "registry_sha256": bindings["registry_sha256"],
        "pair_oracle_contract_sha256": backend.PAIR_CONTRACT_SHA256,
        "allowed_collision_exact_pair_set_sha256": bindings[
            "allowed_collision_exact_pair_set_sha256"
        ],
        "clearance_policy_sha256": bindings["clearance_policy_sha256"],
        "exception_rule_id": "SYNTHETIC_EXACT_ADJACENT_V1",
        "exception_rule_sha256": bindings["exception_rule_sha256"],
        "exception_exact_pair_ids": [EXCEPTION_PAIR],
        "fixture_only": True,
    }


def test_canonical_pair_identity_and_reject_self_pair() -> None:
    assert backend.canonical_pair_id("B", "A") == "A||B"
    with pytest.raises(ValueError):
        backend.canonical_pair_id("A", "A")


def test_synthetic_bindings_are_deterministic_uppercase_sha256() -> None:
    first = backend.synthetic_binding_hashes()
    second = backend.synthetic_binding_hashes()
    assert first == second
    assert all(len(value) == 64 and value == value.upper() for value in first.values())


@pytest.mark.parametrize(
    ("x_m", "expected_status", "expected_raw_mm"),
    [
        (0.02, "SAFE", 10.0),
        (0.012, "UNSAFE", 2.0),
        (0.0150000005, "UNKNOWN", 5.0000005),
        (0.01, "UNSAFE", 0.0),
    ],
)
def test_nominal_fixture_statuses(x_m: float, expected_status: str, expected_raw_mm: float) -> None:
    result = backend.evaluate_pair(geometric_request(x_m, expected_status))
    assert result["status"] == expected_status
    assert result["raw_backend_separation_mm"] == pytest.approx(expected_raw_mm, abs=1.0e-12)
    assert result["complete"] is True and result["finite"] is True
    assert result["comparison_set_size"] > 0


def test_safe_uses_strict_positive_lower_margin_and_left_associative_debit() -> None:
    result = backend.evaluate_pair(geometric_request(0.02))
    expected_lower = ((10.0 - 0.0) - 0.0) - backend.BACKEND_NUMERIC_DERATE_MM
    assert result["certified_separation_lower_bound_mm"].hex() == expected_lower.hex()
    assert result["certified_margin_lower_bound_mm"] > 0.0


def test_lower_only_nonpositive_is_unknown_not_unsafe() -> None:
    result = backend.evaluate_pair(geometric_request(0.0150000005))
    assert result["certified_margin_lower_bound_mm"] <= 0.0
    assert result["certified_margin_upper_bound_mm"] > 0.0
    assert result["status"] == "UNKNOWN"


def test_contact_has_zero_upper_and_witness_authority() -> None:
    result = backend.evaluate_pair(geometric_request(0.01))
    assert result["intersection_or_contact_certified"] is True
    assert result["certified_separation_upper_bound_mm"] == 0.0
    assert len(result["unsafe_witness_authority_sha256"]) == 64


def test_exact_exception_contains_no_geometric_fields() -> None:
    result = backend.evaluate_pair(exception_request())
    assert result["status"] == "EXEMPT_ADJACENT"
    assert not (set(result) & backend.GEOMETRIC_FIELDS)
    assert len(result["exception_pair_set_membership_proof_sha256"]) == 64


@pytest.mark.parametrize(
    ("mutator", "expected_status", "reason_fragment"),
    [
        (lambda r: r.__setitem__("q_bytes_sha256", "A" * 64), "UNKNOWN", "Q_BYTES_SHA256_MISMATCH"),
        (lambda r: r.__setitem__("pose_translation_unit", "mm"), "FAIL", "POSE_TRANSLATION_UNIT_NOT_M"),
        (lambda r: r.__setitem__("pose_frame", "A"), "FAIL", "POSE_FRAME_NOT_S"),
        (lambda r: r.__setitem__("required_clearance_mm", 4.0), "FAIL", "REQUIRED_CLEARANCE_BELOW_AUTHORIZED_MIN"),
        (lambda r: r.__setitem__("object_a_geometry_asset_sha256", "F" * 64), "UNKNOWN", "GEOMETRY_ASSET_SHA256_MISMATCH"),
        (lambda r: r.__setitem__("object_a_hausdorff_derate_mm", -1.0), "FAIL", "OBJECT_A_HAUSDORFF_DERATE_MM_INVALID"),
        (lambda r: r.__setitem__("required_clearance_mm", float("nan")), "FAIL", "REQUIRED_CLEARANCE_INVALID"),
        (lambda r: r.__setitem__("backend_numeric_derate_mm", 0.0), "UNKNOWN", "BACKEND_NUMERIC_DERATE_MISMATCH"),
        (lambda r: r.__setitem__("pair_oracle_contract_sha256", "0" * 64), "UNKNOWN", "PAIR_ORACLE_CONTRACT_SHA256_MISMATCH"),
        (lambda r: r.__setitem__("fixture_only", False), "UNKNOWN", "PRODUCTION_ADMISSION_NOT_BOUND"),
    ],
)
def test_fail_closed_mutations(mutator, expected_status: str, reason_fragment: str) -> None:
    request = geometric_request()
    mutator(request)
    result = backend.evaluate_pair(request)
    assert result["status"] == expected_status
    assert any(reason_fragment in reason for reason in result["reason_codes"])
    assert result["status"] != "SAFE"


def test_reflected_pose_is_rejected() -> None:
    request = geometric_request()
    request["geometry_b_pose_S_row_major_binary64"][0] = -1.0
    result = backend.evaluate_pair(request)
    assert result["status"] == "FAIL"
    assert any("POSE_DETERMINANT_INVALID" in reason for reason in result["reason_codes"])


def test_nonfixture_path_fails_before_geometry_load() -> None:
    request = geometric_request()
    request["object_a_geometry_path"] = str(UPSTREAM_CONTRACT)
    request["object_a_geometry_asset_sha256"] = backend.sha256_path(UPSTREAM_CONTRACT)
    result = backend.evaluate_pair(request)
    assert result["status"] == "UNKNOWN"
    assert "NON_FIXTURE_GEOMETRY_FORBIDDEN" in result["reason_codes"]


def test_missing_fixture_backend_read_failure_is_unknown() -> None:
    request = geometric_request()
    request["object_b_geometry_path"] = str(PACKAGE / "fixtures" / "MISSING.brep")
    result = backend.evaluate_pair(request)
    assert result["status"] == "UNKNOWN"
    assert "GEOMETRY_FILE_MISSING" in result["reason_codes"]


def test_illegal_and_wildcard_exceptions_fail() -> None:
    illegal = exception_request()
    illegal["pair_id"] = "FIXTURE::ADJ_A||FIXTURE::BOX_A"
    illegal["object_id_b"] = "FIXTURE::BOX_A"
    assert backend.evaluate_pair(illegal)["status"] == "FAIL"

    wildcard = exception_request()
    wildcard["exception_exact_pair_ids"] = ["FIXTURE::*||FIXTURE::ADJ_B"]
    result = backend.evaluate_pair(wildcard)
    assert result["status"] == "FAIL"
    assert "WILDCARD_EXCEPTION_FORBIDDEN" in result["reason_codes"]


def test_geometric_row_cannot_claim_exception_pair() -> None:
    request = geometric_request()
    request["object_id_a"] = "FIXTURE::ADJ_A"
    request["object_id_b"] = "FIXTURE::ADJ_B"
    request["pair_id"] = EXCEPTION_PAIR
    result = backend.evaluate_pair(request)
    assert result["status"] == "FAIL"
    assert "EXCEPTION_PAIR_CANNOT_USE_GEOMETRIC_ROW" in result["reason_codes"]


def test_result_evidence_hash_and_replay_are_deterministic() -> None:
    request = geometric_request(0.02, "REPLAY")
    first = backend.evaluate_pair(request)
    second = backend.evaluate_pair(copy.deepcopy(request))
    assert first == second
    payload = dict(first)
    digest = payload.pop("evidence_sha256")
    assert digest == backend.canonical_sha256(payload)


def test_complete_geometric_output_contains_all_current_contract_fields() -> None:
    contract = json.loads(UPSTREAM_CONTRACT.read_text(encoding="utf-8"))
    result = backend.evaluate_pair(geometric_request())
    required = set(contract["required_common_row_output_fields"]) | set(
        contract["required_geometric_result_output_fields"]
    )
    assert required <= set(result)


def test_exact_threshold_is_not_safe() -> None:
    result = backend.evaluate_pair(geometric_request(0.015))
    assert result["certified_margin_lower_bound_mm"] < 0.0
    assert result["certified_margin_upper_bound_mm"] == pytest.approx(0.0, abs=1.0e-12)
    assert result["status"] == "UNSAFE"  # witnessed upper is exactly the 5 mm requirement


def test_no_nan_is_emitted_by_nominal_results() -> None:
    for x_m in (0.02, 0.012, 0.0150000005, 0.01):
        result = backend.evaluate_pair(geometric_request(x_m))
        encoded = json.dumps(result, allow_nan=False, sort_keys=True)
        assert "NaN" not in encoded and "Infinity" not in encoded
