from __future__ import annotations

import json
import math

from conftest import PROJECT_ROOT, canonical_bytes, canonical_hash, file_sha, has_null_leaf, load_contract
from validate_phase_b4g_r2_contract import expand_matrix, generate_schedule, project_acquisition_segment_identity, stable_quaternion_geodesic_rad


def test_six_three_step_lanes_are_frozen() -> None:
    design = load_contract("PHASE_B4G_R2_PREFLIGHT_DESIGN_V1.json")
    lanes = design["lane_grid"]
    assert len(lanes) == 6
    for method in ("rk4", "midpoint"):
        assert [row["step_s"] for row in lanes if row["method"] == method] == [0.00025, 0.000125, 0.0000625]


def test_acquisition_channels_have_explicit_units_and_floors() -> None:
    design = load_contract("PHASE_B4G_R2_PREFLIGHT_DESIGN_V1.json")
    acq = design["tracks"]["fresh_lane_acquisition_convergence"]
    assert acq["observation_count"] == 6
    assert "0.60" in acq["comparison_definitions"]["native_channel_rule"]
    assert "6.25e-5_s" in acq["comparison_definitions"]["acquisition_time_rule"]
    assert len(acq["registered_channels_and_floors"]) == 16
    assert all(row["unit"] and row["floor"] > 0 for row in acq["registered_channels_and_floors"].values())
    metric = design["quaternion_metric_contract"]
    assert metric["formula"] == "d_rad=4*atan2(norm(q1-s*q2),norm(q1+s*q2))"
    assert metric["unit_norm_absolute_tolerance"] == 1e-12
    assert stable_quaternion_geodesic_rad([1.0, 0.0, 0.0, 0.0], [-1.0, 0.0, 0.0, 0.0])["distance_rad"] == 0.0
    assert math.isclose(stable_quaternion_geodesic_rad([1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0])["distance_rad"], math.pi, rel_tol=0.0, abs_tol=1e-15)
    assert stable_quaternion_geodesic_rad([1.0 + 5e-13, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])["valid"] is True
    assert stable_quaternion_geodesic_rad([1.0 + 2e-12, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])["valid"] is False
    assert stable_quaternion_geodesic_rad([1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])["valid"] is False


def test_matrix_is_exactly_78_unique_cases() -> None:
    design = load_contract("PHASE_B4G_R2_PREFLIGHT_DESIGN_V1.json")
    schedule = load_contract("PHASE_B4G_R2_BLOCKED_SCHEDULE_V1.json")
    matrix = expand_matrix()
    applicability = design["matrix_field_applicability"]
    assert len(matrix) == len({row["case_id"] for row in matrix}) == 78
    assert sum(row["execution_family"] == "FRESH" for row in matrix) == 60
    assert sum(row["execution_family"] == "COMMON_PROP" for row in matrix) == 18
    assert canonical_hash(matrix) == design["fixed_matrix"]["canonical_expanded_matrix_sha256"]
    assert canonical_hash(matrix) == schedule["expanded_matrix_canonical_sha256"]
    assert not has_null_leaf(matrix)
    assert all(row["alpha"] == "NOT_APPLICABLE_A0" and row["command_duration_s"] == "NOT_APPLICABLE_A0" and row["sentinel"] in ("PRE", "POST") for row in matrix if row["arm"] == "A0")
    assert all(row["sentinel"] == "NOT_APPLICABLE_A1" and isinstance(row["alpha"], float) and isinstance(row["command_duration_s"], float) for row in matrix if row["arm"] == "A1")
    assert applicability["null_values_forbidden"] is True


def test_declared_analysis_views_have_exact_counts() -> None:
    matrix = expand_matrix()
    assert sum("A0_BOOKEND" in row["roles"] for row in matrix) == 12
    assert sum("FRESH_ALPHA16_PROPAGATION" in row["roles"] for row in matrix) == 18
    assert sum("FRESH_ACQ_OBSERVATION" in row["roles"] for row in matrix) == 6
    assert sum("G12_FRESH_REFERENCE" in row["roles"] for row in matrix) == 36


def test_schedule_is_seeded_complete_and_bookended() -> None:
    schedule = load_contract("PHASE_B4G_R2_BLOCKED_SCHEDULE_V1.json")
    generated = generate_schedule(schedule["seed"])
    assert generated == schedule["case_ids_in_blocked_order"]
    assert len(generated) == 78
    assert canonical_hash(generated) == schedule["case_ids_canonical_sha256"]
    for lane in ("RK4_H_MS_0P25", "RK4_H_MS_0P125", "RK4_H_MS_0P0625", "MIDPOINT_H_MS_0P25", "MIDPOINT_H_MS_0P125", "MIDPOINT_H_MS_0P0625"):
        lane_positions = [i for i, case in enumerate(generated) if f"FRESH__{lane}__" in case]
        assert generated[min(lane_positions)].endswith("__A0__PRE")
        assert generated[max(lane_positions)].endswith("__A0__POST")


def test_fresh_and_common_case_ids_and_credit_are_isolated() -> None:
    matrix = expand_matrix()
    fresh = [row for row in matrix if row["execution_family"] == "FRESH"]
    common = [row for row in matrix if row["execution_family"] == "COMMON_PROP"]
    assert not ({row["case_id"] for row in fresh} & {row["case_id"] for row in common})
    assert all(not row["g12_credit"] and not row["selector_input"] for row in common)
    assert all(row["initial_state"] == "COMMON_STATE_GROUP_396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444" for row in common)


def test_common_donor_raw_and_payload_are_byte_hash_bound() -> None:
    sources = load_contract("PHASE_B4G_R2_SOURCE_BINDINGS_V1.json")
    binding = sources["common_donor_payload_binding"]
    source = next(row for row in sources["sources"] if row["id"] == binding["source_id"])
    path = PROJECT_ROOT / source["path"]
    assert path.stat().st_size == source["bytes"] == 69249
    assert file_sha(path) == source["sha256"] == "5DF0C19A71180E1BD91816235AAD50108613C2BC0F99F950018D786119CF9D4F"
    donor = json.loads(path.read_text(encoding="utf-8"))
    payload = donor["event_provenance"]["acquisition_certificate_payload"]
    assert canonical_hash(payload) == binding["canonical_sha256"] == donor["event_provenance"]["acquisition_certificate_sha256"]
    reduced = payload["acquisition"]["z_plus_reduced"]
    group = {
        "schema": "B4G_R2_COMMON_INITIAL_STATE_GROUP_V1",
        "donor_acquisition_certificate_sha256": donor["event_provenance"]["acquisition_certificate_sha256"],
        "acquisition_time_s": payload["acquisition"]["acquisition_time_s"],
        "service": {
            "base_position_inertial_m": payload["event"]["service"]["base_position_inertial_m"],
            "base_quaternion_body_to_inertial_wxyz": payload["event"]["service"]["base_quaternion_body_to_inertial_wxyz"],
            "joint_coordinates_mixed": payload["event"]["service"]["joint_coordinates_mixed"],
            "post_acquisition_eta_mixed": reduced[:14],
        },
        "target": {
            "position_inertial_m": payload["event"]["target"]["position_inertial_m"],
            "quaternion_body_to_inertial_wxyz": payload["event"]["target"]["quaternion_body_to_inertial_wxyz"],
            "post_acquisition_twist_inertial_mixed": reduced[14:20],
        },
    }
    assert len(canonical_bytes(group)) == binding["common_initial_state_group_canonical_bytes"] == 1317
    assert canonical_hash(group) == binding["common_initial_state_group_sha256"] == "396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444"
    common = load_contract("PHASE_B4G_R2_PREFLIGHT_DESIGN_V1.json")["tracks"]["common_initial_state_propagation_convergence"]
    assert canonical_hash(common["common_initial_state_fixture"]["common_initial_state_group_field_map"]) == "74FE8F3182439BE025C3B696281423219E565C3DF46AD5B2916AD47D68249DF5"
    assert canonical_hash(common["comparison_channels_and_floors"]) == "73090EBF1735D259BA84E7617D1978C3C6E910445E7EBE3A15BDDC2987E9103B"
    identity = load_contract("PHASE_B4G_R2_PREFLIGHT_DESIGN_V1.json")["tracks"]["fresh_lane_acquisition_convergence"]["technical_repeat_identity_projection"]
    assert identity["allowed_different_json_pointers_exact"] == ["/case_id", "/event/run_id", "/acquisition/run_id"]
    projections = []
    raw_root = PROJECT_ROOT / sources["preserved_raw_inventory"]["path"]
    for basename in identity["preserved_raw_read_only_rule_sanity_anchor"]["basenames"]:
        raw_case = json.loads((raw_root / basename).read_text(encoding="utf-8"))
        projections.append(project_acquisition_segment_identity(raw_case["event_provenance"]["acquisition_certificate_payload"]))
    assert {row["status"] for row in projections} == {"PASS_IDENTITY_PROJECTION"}
    assert {row["canonical_bytes"] for row in projections} == {31050}
    assert {row["sha256"] for row in projections} == {"29DFA8D35BBBA4E615B583B09EBB1B32144C0FE39B740898F1A0EB7ED838511C"}
