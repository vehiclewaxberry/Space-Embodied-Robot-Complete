from __future__ import annotations

import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = next(candidate for candidate in (PACKAGE, *PACKAGE.parents) if (candidate / "PROJECT_MAP.md").is_file())


def read(relative: str):
    return json.loads((PACKAGE / relative).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_source_lock_is_exact_and_live():
    lock = read("00_contract/SOURCE_AUTHORITY_LOCK_V1.json")
    assert lock["source_pin_count"] == len(lock["source_pins"]) == 10
    assert len({row["id"] for row in lock["source_pins"]}) == 10
    for row in lock["source_pins"]:
        path = ROOT / row["path"]
        assert path.stat().st_size == row["bytes"]
        assert sha(path) == row["sha256"]


def test_exact_twelve_link2_objects_are_frozen_and_j3_carriage_is_excluded():
    contract = read("00_contract/LINK2_B12_OPERATIONAL_COLLISION_CONTRACT_V1.json")
    expected = {
        "R::RC-CHN-L2-BASE", "R::RC-CHN-L2-LINER", "R::RC-CHN-L2-WALL-A", "R::RC-CHN-L2-WALL-B",
        "R::RC-CLP-J2-MOV", "R::RC-CLP-L2-01", "R::RC-CLP-L2-02", "R::RC-GDE-J3-SADDLE",
        "R::RC-GDE-J3-SADDLE-LINER", "R::RC-TRK-J3-RAIL", "R::RC-TRK-J3-STOP-A", "R::RC-TRK-J3-STOP-B",
    }
    excluded = {"R::RC-CAR-J3-CARRIAGE", "R::RC-CLP-J3-MOV", *(f"R::RC-CHN-E210-LINK-0{i}" for i in range(6))}
    assert len(contract["objects"]) == 12
    assert {row["object_id"] for row in contract["objects"]} == expected
    assert set(contract["excluded_j3_carriage_objects"]) == excluded
    assert expected.isdisjoint(excluded)
    assert all(row["parent_frame"] == "link2" for row in contract["objects"])


def test_builder_receipt_has_twelve_steps_and_thirty_six_sidecars():
    receipt = read("05_results/TWELVE_STEP_BUILD_RECEIPT_V1.json")
    assert receipt["objects_requested"] == receipt["objects_emitted"] == receipt["primary_step_files"] == 12
    assert receipt["runtime_sidecar_files"] == 36
    assert receipt["source_shape_object_placement_consumed_separately"] is False
    assert receipt["verdict"] == "LINK2_B12_PRIMARY_STEP_RUNTIME_AND_POSE_ADAPTER_BUILD_PASS__SYSTEM_AUTHORITY_UNCHANGED"


def test_independent_geometry_and_bilateral_brep_difference_pass():
    result = read("05_results/INDEPENDENT_LINK2_B12_VALIDATION_V1.json")
    limit = read("00_contract/LINK2_B12_OPERATIONAL_COLLISION_CONTRACT_V1.json")["tolerances"]["brep_roundtrip_symmetric_difference_mm3"]
    assert result["validator_imports_builder"] is False
    assert result["object_count"] == result["bilateral_brep_difference_pass_count"] == 12
    for row in result["objects"]:
        assert row["step_transfer_root_count"] == 1
        assert row["source_valid_closed_positive_single_solid"]
        assert row["step_valid_closed_positive_single_solid"]
        assert max(row["expected_to_step_cut_mm3"], row["step_to_expected_cut_mm3"], row["source_to_roundtrip_cut_mm3"], row["roundtrip_to_source_cut_mm3"]) <= limit


def test_runtime_sidecars_are_closed_oriented_manifolds():
    result = read("05_results/INDEPENDENT_LINK2_B12_VALIDATION_V1.json")
    assert result["runtime_closed_oriented_two_manifold_pass_count"] == 12
    for row in result["objects"]:
        assert row["runtime_manifold"]["closed_oriented_two_manifold"]
        assert row["runtime_manifold"]["boundary_edge_count"] == 0
        assert row["runtime_manifold"]["nonmanifold_edge_count"] == 0


def test_pose_adapter_uses_raw_urdf_and_12dp_mount():
    result = read("05_results/INDEPENDENT_POSE_ADAPTER_VALIDATION_V1.json")
    assert result["validator_imports_builder"] is False
    assert result["execution_mount_reconstructed_from_25deg"] is False
    assert result["historical_D6_mount_used"] is False
    joints = result["accepted_urdf_raw_numeric_spelling"]
    assert joints["joint1"]["origin_xyz_m"] == ["-8.416E-05", "0", "0.08465"]
    assert joints["joint2"]["origin_xyz_m"] == ["0.020084", "0.031625", "0.05555"]
    assert joints["joint2"]["origin_rpy_rad"] == ["-1.5708", "0", "0"]
    assert joints["joint2"]["axis"] == ["0", "0", "-1"]
    assert result["sample_count"] == len(result["samples"]) == 9
    assert [(row["q1_rad"], row["q2_rad"]) for row in result["samples"]] == [
        (q1, q2) for q1 in (-2.8, 0.0, 2.8) for q2 in (-3.14, -1.57, 0.0)
    ]
    assert max(row["matrix_max_abs_residual"] for row in result["samples"]) <= 1e-12
    assert result["q1_fault_sensitivity"]["ignored_q1_rejected"] is True
    assert result["q1_fault_sensitivity"]["sign_reversed_q1_rejected"] is True


def test_all_negative_controls_reject():
    result = read("05_results/NEGATIVE_CONTROLS_V1.json")
    assert result["case_count"] == result["pass_count"] == 51
    assert result["fail_count"] == 0
    assert all(row["actual"] == "REJECT" and row["pass"] for row in result["cases"])
    by_id = {row["case_id"]: row for row in result["cases"]}
    assert max(by_id["NC50_Q1_IGNORED_ADAPTER"]["sample_residuals"]) > 1e-12
    assert max(by_id["NC51_Q1_SIGN_REVERSED_ADAPTER"]["sample_residuals"]) > 1e-12


def test_fresh_process_replay_is_byte_stable():
    result = read("05_results/FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json")
    assert result["artifact_count"] == 52
    assert len(result["builder_fresh_process_runs"]) == len(result["validator_fresh_process_runs"]) == 2
    assert result["artifacts_after_identical"] is True
    assert result["builder_command"][1] == result["validator_command"][1] == "-B"
    assert result["fixed_environment"] == {
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONUTF8": "1"
    }
    clean = {"pycache_directories": 0, "pyc_files": 0, "temporary_files": 0}
    assert result["package_hygiene_before"] == result["package_hygiene_after"] == clean
    assert not list(PACKAGE.rglob("__pycache__"))
    assert not list(PACKAGE.rglob("*.pyc"))
    assert not [path for path in PACKAGE.rglob("*") if path.is_file() and path.name.endswith(".tmp")]


def test_current_system_authority_is_not_upgraded():
    expected = {"operational_geometry_count": "1/150", "pair_queries": "0/11166", "safe_count": 0, "edge_count": 0, "stage_clearance": "0/3", "path_exists": False, "TMG4": "HOLD", "G12": "FAIL", "next_stage_authorized": False, "release_credit": False}
    contract = read("00_contract/LINK2_B12_OPERATIONAL_COLLISION_CONTRACT_V1.json")
    build = read("05_results/TWELVE_STEP_BUILD_RECEIPT_V1.json")
    assert contract["system_status_invariant"] == expected
    assert build["system_status_invariant"] == expected
    assert build["system_operational_credit"] is False
    assert build["system_pair_query_credit"] == 0


def test_all_primary_steps_exist_and_match_index_pins():
    index = read("05_results/LINK2_B12_GEOMETRY_INDEX_V1.json")
    assert index["object_count"] == 12
    for row in index["objects"]:
        path = ROOT / row["primary_step"]["path"]
        assert path.stat().st_size == row["primary_step"]["bytes"]
        assert sha(path) == row["primary_step"]["sha256"]
