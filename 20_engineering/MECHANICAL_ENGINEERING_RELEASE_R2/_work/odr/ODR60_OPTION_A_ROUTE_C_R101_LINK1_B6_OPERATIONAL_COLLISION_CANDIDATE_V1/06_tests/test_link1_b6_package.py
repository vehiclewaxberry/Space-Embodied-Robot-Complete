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


def test_exact_six_link1_objects_are_frozen():
    contract = read("00_contract/LINK1_B6_OPERATIONAL_COLLISION_CONTRACT_V1.json")
    expected = {"R::RC-BRK-L1-01", "R::RC-CLP-J1-MOV", "R::RC-CLP-J2-FIX", "R::RC-CLP-L1-01", "R::RC-GDE-J2-MANDREL", "R::RC-GDE-J2-MANDREL-LINER"}
    assert len(contract["objects"]) == 6
    assert {row["object_id"] for row in contract["objects"]} == expected
    assert all(row["parent_frame"] == "link1" for row in contract["objects"])


def test_builder_receipt_has_six_steps_and_eighteen_sidecars():
    receipt = read("05_results/SIX_STEP_BUILD_RECEIPT_V1.json")
    assert receipt["objects_requested"] == receipt["objects_emitted"] == receipt["primary_step_files"] == 6
    assert receipt["runtime_sidecar_files"] == 18
    assert receipt["source_shape_object_placement_consumed_separately"] is False
    assert receipt["verdict"] == "LINK1_B6_PRIMARY_STEP_RUNTIME_AND_POSE_ADAPTER_BUILD_PASS__SYSTEM_AUTHORITY_UNCHANGED"


def test_independent_geometry_and_bilateral_brep_difference_pass():
    result = read("05_results/INDEPENDENT_LINK1_B6_VALIDATION_V1.json")
    limit = read("00_contract/LINK1_B6_OPERATIONAL_COLLISION_CONTRACT_V1.json")["tolerances"]["brep_roundtrip_symmetric_difference_mm3"]
    assert result["validator_imports_builder"] is False
    assert result["object_count"] == result["bilateral_brep_difference_pass_count"] == 6
    for row in result["objects"]:
        assert row["step_transfer_root_count"] == 1
        assert row["source_valid_closed_positive_single_solid"]
        assert row["step_valid_closed_positive_single_solid"]
        assert max(row["expected_to_step_cut_mm3"], row["step_to_expected_cut_mm3"], row["source_to_roundtrip_cut_mm3"], row["roundtrip_to_source_cut_mm3"]) <= limit


def test_runtime_sidecars_are_closed_oriented_manifolds():
    result = read("05_results/INDEPENDENT_LINK1_B6_VALIDATION_V1.json")
    assert result["runtime_closed_oriented_two_manifold_pass_count"] == 6
    for row in result["objects"]:
        assert row["runtime_manifold"]["closed_oriented_two_manifold"]
        assert row["runtime_manifold"]["boundary_edge_count"] == 0
        assert row["runtime_manifold"]["nonmanifold_edge_count"] == 0


def test_pose_adapter_uses_raw_urdf_and_12dp_mount():
    result = read("05_results/INDEPENDENT_POSE_ADAPTER_VALIDATION_V1.json")
    assert result["validator_imports_builder"] is False
    assert result["execution_mount_reconstructed_from_25deg"] is False
    assert result["historical_D6_mount_used"] is False
    assert result["accepted_urdf_raw_numeric_spelling"]["origin_xyz_m"] == ["-8.416E-05", "0", "0.08465"]
    assert [row["q1_rad"] for row in result["samples"]] == [-2.8, 0.0, 2.8]
    assert max(row["matrix_max_abs_residual"] for row in result["samples"]) <= 1e-12


def test_all_negative_controls_reject():
    result = read("05_results/NEGATIVE_CONTROLS_V1.json")
    assert result["case_count"] == result["pass_count"] == 44
    assert result["fail_count"] == 0
    assert all(row["actual"] == "REJECT" and row["pass"] for row in result["cases"])


def test_fresh_process_replay_is_byte_stable():
    result = read("05_results/FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json")
    assert result["artifact_count"] == 28
    assert len(result["builder_fresh_process_runs"]) == len(result["validator_fresh_process_runs"]) == 2
    assert result["artifacts_after_identical"] is True


def test_current_system_authority_is_not_upgraded():
    expected = {"operational_geometry_count": "1/150", "pair_queries": "0/11166", "safe_count": 0, "edge_count": 0, "stage_clearance": "0/3", "path_exists": False, "TMG4": "HOLD", "G12": "FAIL", "next_stage_authorized": False, "release_credit": False}
    contract = read("00_contract/LINK1_B6_OPERATIONAL_COLLISION_CONTRACT_V1.json")
    build = read("05_results/SIX_STEP_BUILD_RECEIPT_V1.json")
    assert contract["system_status_invariant"] == expected
    assert build["system_status_invariant"] == expected
    assert build["system_operational_credit"] is False
    assert build["system_pair_query_credit"] == 0


def test_all_primary_steps_exist_and_match_index_pins():
    index = read("05_results/LINK1_B6_GEOMETRY_INDEX_V1.json")
    assert index["object_count"] == 6
    for row in index["objects"]:
        path = ROOT / row["primary_step"]["path"]
        assert path.stat().st_size == row["primary_step"]["bytes"]
        assert sha(path) == row["primary_step"]["sha256"]
