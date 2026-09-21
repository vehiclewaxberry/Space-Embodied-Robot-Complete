from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
MODULE_PATH = PACKAGE / "aggregate_digital_prototype_dynamics_entry_v2.py"
SPEC = importlib.util.spec_from_file_location("aggregate_entry_v2", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def gate() -> dict:
    return MODULE.load_json(
        PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V2.json"
    )


def test_four_source_pins_are_exact() -> None:
    documents, binding = MODULE.load_sources()
    assert binding["all_match"] is True
    assert binding["matched"] == binding["total"] == 4
    assert set(documents) == set(MODULE.SOURCE_PINS)


def test_aggregate_is_reproducible_and_ten_of_ten() -> None:
    expected = MODULE.canonical_bytes(MODULE.build_gate())
    assert (
        PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V2.json"
    ).read_bytes() == expected
    document = gate()
    assert document["summary"] == {"passed": 10, "total": 10, "failed": []}


def test_contact_conflict_is_only_resolved_for_bounded_consumer() -> None:
    document = gate()
    contact = document["progress_delta"][
        "contact_velocity_internal_contract_conflict"
    ]
    assert contact["current_state"] == "RESOLVED_FOR_BOUNDED_CURRENT_CONSUMER"
    assert contact["original_0p05_mps_record"].startswith("RETAINED_LINEAGE")
    assert contact["as_built_authority"] == "MEASUREMENT_PENDING"
    assert document["authorized_now"]["physical_contact_or_non_abort_grasp"] is False


def test_dg1_dg2_pass_does_not_close_parent_dynamics() -> None:
    document = gate()
    dynamics = document["progress_delta"]["dynamics"]
    assert dynamics["DG1_reference_metric"] == "PASS_CANDIDATE"
    assert dynamics["DG2_nonzero_momentum_full_pose"] == "PASS_CANDIDATE"
    assert dynamics["DG3_DG4_DG5"] == "HOLD"
    assert dynamics["production_dynamics"] is False


def test_system_binding_maximum_is_abort_only() -> None:
    document = gate()
    binding = document["progress_delta"]["system_binding"]
    assert binding["input_hashes"] == "23_OF_23_MATCH"
    assert binding["static_candidate"] == "PASS"
    assert binding["maximum_operational_state"] == "ABORT_ONLY"


def test_m4_matrix_preserves_incomplete_L01_L02_L08_and_release() -> None:
    matrix = gate()["m4_completion_matrix"]
    assert matrix["L01_total_digital_mockup"].startswith("HOLD")
    assert matrix["L02_nine_configuration_geometry_collision"].startswith("PARTIAL")
    assert matrix["L08_MECH_RL_V2"].startswith("PARTIAL")
    assert matrix["final_release_gate"] == "HOLD"


def test_authority_and_release_are_fail_closed() -> None:
    document = gate()
    assert document["review_status"] == "PENDING_OWNER_REVIEW"
    assert document["next_stage_authorized"] is False
    assert document["release_credit"] is False
    assert document["authorized_now"]["integrated_candidate_CAD_generation"] is False
    assert document["authorized_now"]["M01_collision_or_path_authority"] is False
    assert document["authorized_now"]["production_dynamics"] is False
    assert document["authorized_now"]["flight_release"] is False


def test_json_is_finite() -> None:
    json.dumps(gate(), allow_nan=False)
