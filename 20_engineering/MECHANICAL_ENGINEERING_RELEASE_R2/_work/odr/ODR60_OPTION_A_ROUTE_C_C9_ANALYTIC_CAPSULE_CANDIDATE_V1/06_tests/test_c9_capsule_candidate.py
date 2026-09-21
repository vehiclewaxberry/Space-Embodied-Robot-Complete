from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = next(path for path in Path(__file__).resolve().parents if (path / "PROJECT_MAP.md").is_file())
sys.path.insert(0, str(PACKAGE / "02_builder"))
import build_c9_capsules as builder  # noqa: E402
import c9_pose_adapter as pose  # noqa: E402


def read(relative: str):
    return json.loads((PACKAGE / relative).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def contract():
    return read("00_contract/C9_ANALYTIC_CAPSULE_CONTRACT_V1.json")


@pytest.fixture(scope="module")
def index():
    return read("05_results/C9_CAPSULE_INDEX_V1.json")


def test_contract_exact_nine(contract):
    assert contract["object_count"] == len(contract["objects"]) == 9
    assert len({item["object_id"] for item in contract["objects"]}) == 9


def test_contract_numeric_radius_no_double_count(contract):
    numeric = contract["numeric_contract"]
    assert numeric["nominal_bundle_od_mm"] == 9.0
    assert numeric["design_upper_bundle_od_mm"] == 10.0
    assert numeric["design_centerline_tube_radius_mm"] == 5.0
    assert numeric["nominal_to_design_radial_increment_mm_already_included"] == 0.5
    assert numeric["double_count_increment_forbidden"] is True
    query = numeric["narrowphase_query_contract"]
    assert query["required_query_radius_field"] == "effective_radius_mm"
    assert query["hausdorff_debit_count"] == 1
    assert query["separate_clearance_debit_alternative_supported_by_this_package"] is False


def test_contract_p01_and_p11_roles(contract):
    numeric = contract["numeric_contract"]
    assert numeric["p01_channel_clearance_mm_not_a_bundle_radius"] == 12.0
    assert numeric["p11_physical_guide_to_centerline_offset_lineage"] == "UNKNOWN"


@pytest.mark.parametrize("source_name", sorted(read("00_contract/SOURCE_AUTHORITY_LOCK_V1.json")["sources"]))
def test_each_source_pin(source_name):
    lock = read("00_contract/SOURCE_AUTHORITY_LOCK_V1.json")
    source = lock["sources"][source_name]
    path = ROOT / source["path"]
    assert path.stat().st_size == source["bytes"]
    assert builder.sha256_path(path) == source["sha256"]


def test_source_lock_count():
    lock = read("00_contract/SOURCE_AUTHORITY_LOCK_V1.json")
    assert lock["source_count"] == len(lock["sources"]) == 18


def test_index_aggregate_counts(index):
    assert index["object_count"] == 9
    assert index["aggregate_metrics"]["primitive_count"] == 61
    assert index["aggregate_metrics"]["capsule_count"] == 2355


def test_index_curve_step(index):
    assert index["aggregate_metrics"]["maximum_curve_arclength_step_mm"] <= 1.5


def test_index_hausdorff(index):
    value = index["aggregate_metrics"]["maximum_hausdorff_bound_mm"]
    assert value == pytest.approx(0.005112823031626079, abs=1e-18)
    assert value <= 1.5**2 / (8.0 * 54.0)
    assert index["aggregate_metrics"]["maximum_effective_radius_mm"] == pytest.approx(5.0 + value, abs=1e-15)


@pytest.mark.parametrize("row_index", range(9))
def test_runtime_json_npz_pair(index, row_index):
    row = index["objects"][row_index]
    payload = read(row["json"]["path"])
    npz_path = PACKAGE / row["npz"]["path"]
    assert payload["object_id"] == row["object_id"]
    assert payload["metrics"]["capsule_count"] == row["capsule_count"]
    assert all(capsule["design_radius_mm"] == 5.0 for capsule in payload["capsules"])
    assert all(capsule["narrowphase_query_radius_field"] == "effective_radius_mm"
               for capsule in payload["capsules"])
    assert all(capsule["effective_radius_mm"] == pytest.approx(
        capsule["design_radius_mm"] + capsule["hausdorff_bound_mm"], abs=1e-15)
        for capsule in payload["capsules"])
    with np.load(npz_path, allow_pickle=False) as arrays:
        assert arrays["design_radius_mm"].shape == (row["capsule_count"],)
        assert np.all(arrays["design_radius_mm"] == 5.0)
        assert np.array_equal(arrays["effective_radius_mm"],
                              arrays["design_radius_mm"] + arrays["hausdorff_bound_mm"])
        assert arrays["capsule_id"].tolist() == [capsule["capsule_id"] for capsule in payload["capsules"]]
    with zipfile.ZipFile(npz_path) as archive:
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())


def test_fillet_clamp_actual_radius_lineage(index):
    rows = [read(row["json"]["path"]) for row in index["objects"]]
    clamped = [primitive for payload in rows for primitive in payload["primitives"]
               if primitive["kind"] == "fillet_arc" and primitive["lineage"]["radius_was_clamped"]]
    assert len(clamped) == 1
    assert clamped[0]["lineage"]["desired_radius_mm"] == 55.0
    assert clamped[0]["radius_mm"] == pytest.approx(54.73831022541755, abs=2e-12)
    assert clamped[0]["lineage"]["start_tangent_residual"] <= 1e-12
    assert clamped[0]["lineage"]["end_tangent_residual"] <= 1e-12


def test_j3_is_unknown(index):
    assert index["j3"]["continuous_q3_carrier_law"] == "UNKNOWN"
    assert index["j3"]["production_union_acceptance"] == "UNKNOWN"


def test_pose_receipt_q4_samples():
    receipt = read("05_results/POSE_ADAPTER_SELF_CHECK_V1.json")
    assert [row["q4_rad"] for row in receipt["j4_samples"]] == [-1.87, 0.0, 1.57]
    assert receipt["j4_max_follower_closure_residual_mm"] <= 1e-6
    assert receipt["j4_max_dynamic_exchange_length_residual_mm"] <= 1e-9
    assert receipt["j4_section5_full_domain_topology_capsule_count"] == 139
    assert receipt["j4_section5_full_domain_max_dynamic_curve_arclength_step_mm"] == pytest.approx(
        1.4992706602297674, abs=2e-15)
    assert receipt["j4_section5_full_domain_max_dynamic_hausdorff_bound_mm"] == pytest.approx(
        0.005108585715678515, abs=2e-15)
    assert receipt["j4_all_139_segments_recomputed_at_each_q4_sample"] is True


def test_pose_receipt_j4_sign():
    rows = read("05_results/POSE_ADAPTER_SELF_CHECK_V1.json")["j4_samples"]
    assert rows[0]["x_c_mm"] > rows[1]["x_c_mm"] > rows[2]["x_c_mm"]
    assert rows[0]["annulus_beta_rad"] > rows[1]["annulus_beta_rad"] > rows[2]["annulus_beta_rad"]
    assert all(row["section5_topology_capsule_count"] == 139 for row in rows)
    assert max(row["section5_max_dynamic_curve_arclength_step_mm"] for row in rows) <= 1.5


def test_pose_receipt_j3_dual_unknown():
    j3 = read("05_results/POSE_ADAPTER_SELF_CHECK_V1.json")["j3"]
    assert j3["dual_host_capsule_count"] == 169
    assert j3["maximum_primary_alternate_separation_mm"] > 0.0
    assert j3["continuous_q3_carrier_law"] == "UNKNOWN"
    assert j3["production_union_acceptance"] == "UNKNOWN"


def test_q_hash_rejected():
    _, arm, _, _ = pose.load_context()
    record = pose.make_q_record([0.0] * 6)
    record["payload_sha256"] = "0" * 64
    with pytest.raises(pose.PoseFailure):
        pose.validate_q_record(record, arm)


def test_q_limit_rejected():
    _, arm, _, _ = pose.load_context()
    record = pose.make_q_record([0.0, 0.0, 0.0, 1.5701, 0.0, 0.0])
    with pytest.raises(pose.PoseFailure):
        pose.validate_q_record(record, arm)


def test_q_nan_rejected():
    _, arm, _, _ = pose.load_context()
    record = {"payload": {"schema": "C9_Q_STATE_V1", "joint_order": pose.JOINT_ORDER,
                          "q_rad": [0.0, 0.0, float("nan"), 0.0, 0.0, 0.0]},
              "payload_sha256": "0" * 64}
    with pytest.raises(pose.PoseFailure):
        pose.validate_q_record(record, arm)


@pytest.mark.parametrize("script,argument", [
    ("02_builder/build_c9_capsules.py", "--check"),
    ("02_builder/c9_pose_adapter.py", "--check-self-check"),
    ("04_validation/validate_c9_independent.py", "--check"),
])
def test_replay_commands(script, argument):
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, str(PACKAGE / script), argument], cwd=ROOT,
                            env=environment, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert '"status": "PASS"' in result.stdout


def test_independent_validation():
    receipt = read("05_results/INDEPENDENT_VALIDATION_V1.json")
    assert receipt["checks_passed"] == receipt["checks_required"] == 16
    assert receipt["independent_validation_pass"] is True
    assert receipt["aggregate"]["capsules"] == 2355
    assert receipt["aggregate"]["j4_section5_full_domain_topology_capsule_count"] == 139


def test_negative_controls():
    receipt = read("05_results/NEGATIVE_CONTROLS_V1.json")
    assert receipt["required"] == receipt["caught"] == 21
    assert receipt["all_caught"] is True
    assert all(case["caught"] for case in receipt["cases"])


def test_fresh_process_receipt():
    receipt = read("05_results/FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json")
    assert receipt["replay_count"] == 2
    assert receipt["fresh_process_count"] == 6
    assert receipt["core_artifact_count"] == 23
    assert receipt["fresh_process_determinism_pass"] is True


def test_system_truth_from_external_machine_gates():
    validation = read("05_results/INDEPENDENT_VALIDATION_V1.json")
    state = validation["authority_boundary"]["system_state"]
    authority = validation["authority_boundary"]["system_state_authority"]
    assert authority["source"] == "FOUR_HASH_PINNED_CURRENT_EXTERNAL_MACHINE_GATES"
    assert len(authority["pins"]) == 4
    assert state["system_operational_authority_rows"] == 1
    assert state["known_active_objects"] == 150
    assert state["system_pair_queries"] == 0
    assert state["required_unassessed_pairs"] == 11166
    assert state["safe_certificates"] == state["system_edges_certified"] == 0
    assert state["stage_instances_bound"] == 0 and state["stage_instances_required"] == 3
    assert state["path_search_executed"] is False
    assert state["TMG4"] == "HOLD" and state["G12"] == "FAIL"
    assert state["next_stage_authorized"] is False and state["release_credit"] is False


def test_j4_full_domain_posed_effective_radius_every_representation():
    index_value, arm, mount, _ = pose.load_context()
    payload = pose.object_payload(index_value, pose.J4_SELECTOR)
    posed = pose.pose_object(payload, pose.make_q_record([0.0, 0.0, 0.0, -1.87, 0.0, 0.0]), arm, mount)
    section5 = [capsule for capsule in posed["capsules"] if capsule["section_index"] == 5]
    assert len(section5) == 139
    for capsule in posed["capsules"]:
        for representation in capsule["representations"]:
            assert representation["narrowphase_query_radius_field"] == "effective_radius_mm"
            assert representation["effective_radius_mm"] == pytest.approx(
                representation["design_radius_mm"] + representation["hausdorff_bound_mm"], abs=1e-15)
            if representation["curve_step_limit_applies"]:
                assert representation["curve_arclength_step_mm"] <= 1.5 + 1e-12


def test_negative_controls_cover_d1_d2():
    ids = {case["id"] for case in read("05_results/NEGATIVE_CONTROLS_V1.json")["cases"]}
    assert {
        "NC19_RAW_5MM_USED_AS_QUERY_RADIUS",
        "NC20_HAUSDORFF_DOUBLE_DEBIT_OR_INFLATION",
        "NC21_J4_SECTION5_Q0_ONLY_UNDERSUBDIVISION",
    } <= ids


def test_pre_repair_gate_is_superseded_zero_credit():
    review = read("07_reviews/C9_PRE_REPAIR_NOT_CLEAN_PASS_V1.json")
    assert review["verdict"] == "SUPERSEDED_PRE_AUTHORITY_NOT_CLEAN_PASS__ZERO_CREDIT"
    assert review["superseded_artifacts"]["gate"]["sha256"] == \
        "17C087BD1CB0016E08AE1DD0A55A16FB34662869C1693DBBE8B10FF4B6958628"
