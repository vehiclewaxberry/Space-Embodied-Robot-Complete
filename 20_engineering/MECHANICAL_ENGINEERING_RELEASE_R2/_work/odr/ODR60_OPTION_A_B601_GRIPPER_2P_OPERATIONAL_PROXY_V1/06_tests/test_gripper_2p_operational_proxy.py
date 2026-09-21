"""Fast release-facing checks for the B601 three-container gripper proxy.

These tests intentionally consume only the frozen contracts and emitted evidence.
They never import or invoke the builder: OCCT deterministic replay is performed by
``verify_fresh_process_determinism.py`` in a separate CPython process.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pytest


PACKAGE_DIR = Path(__file__).resolve().parents[1]
CONTRACT_DIR = PACKAGE_DIR / "00_contract"
RUNTIME_DIR = PACKAGE_DIR / "02_runtime"
RESULTS_DIR = PACKAGE_DIR / "05_results"
REVIEWS_DIR = PACKAGE_DIR / "07_reviews"

CONTRACT_PATH = CONTRACT_DIR / "GRIPPER_2P_OPERATIONAL_PROXY_CONTRACT_V1.json"
SOURCE_LOCK_PATH = CONTRACT_DIR / "SOURCE_AUTHORITY_LOCK_V1.json"
FRAME_LEDGER_PATH = CONTRACT_DIR / "URDF_FRAME_AND_STATE_LEDGER_V1.json"

OBJECTS = ("gripper_link", "gripper_left", "gripper_right")
OBJECT_IDS = {
    "gripper_link": "A::gripper_link",
    "gripper_left": "A::gripper_left",
    "gripper_right": "A::gripper_right",
}
EXPECTED_SOLID_COUNTS = {
    "gripper_link": 12,
    "gripper_left": 24,
    "gripper_right": 24,
}
EXPECTED_RUNTIME_COUNTS = {
    "gripper_link": (25615, 51822),
    "gripper_left": (62093, 125000),
    "gripper_right": (62133, 125000),
}
RECEIPT_PATHS = {
    "gripper_link": RESULTS_DIR / "B601_GRIPPER_LINK_LOCAL_GEOMETRY_RECEIPT_V1.json",
    "gripper_left": RESULTS_DIR / "B601_GRIPPER_LEFT_LOCAL_GEOMETRY_RECEIPT_V1.json",
    "gripper_right": RESULTS_DIR / "B601_GRIPPER_RIGHT_LOCAL_GEOMETRY_RECEIPT_V1.json",
}
FORBIDDEN_AUTHORITY_FLAGS = (
    "contact_authority",
    "next_stage_authorized",
    "owner_named_state_map_resolved",
    "parent_gate_credit",
    "parent_mechanical_gate_reissued",
    "path_search_authorized",
    "path_search_executed",
    "release_credit",
    "system_pair_evaluation_authorized",
    "system_registry_reissued",
    "system_safe",
)

EXPECTED_SCHEMAS = {
    "00_contract/GRIPPER_2P_OPERATIONAL_PROXY_CONTRACT_V1.json": (
        "ODR60_OPTION_A_B601_GRIPPER_2P_OPERATIONAL_PROXY_CONTRACT_V1"
    ),
    "00_contract/SOURCE_AUTHORITY_LOCK_V1.json": (
        "ODR60_OPTION_A_B601_GRIPPER_2P_OPERATIONAL_PROXY_SOURCE_AUTHORITY_LOCK_V1"
    ),
    "00_contract/URDF_FRAME_AND_STATE_LEDGER_V1.json": (
        "ODR60_OPTION_A_B601_GRIPPER_2P_URDF_FRAME_AND_STATE_LEDGER_V1"
    ),
    "05_results/B601_GRIPPER_LINK_LOCAL_GEOMETRY_RECEIPT_V1.json": (
        "B601_GRIPPER_2P_LOCAL_GEOMETRY_RECEIPT_V1"
    ),
    "05_results/B601_GRIPPER_LEFT_LOCAL_GEOMETRY_RECEIPT_V1.json": (
        "B601_GRIPPER_2P_LOCAL_GEOMETRY_RECEIPT_V1"
    ),
    "05_results/B601_GRIPPER_RIGHT_LOCAL_GEOMETRY_RECEIPT_V1.json": (
        "B601_GRIPPER_2P_LOCAL_GEOMETRY_RECEIPT_V1"
    ),
    "05_results/BUILDER_EVIDENCE_V1.json": "B601_GRIPPER_2P_BUILDER_EVIDENCE_V1",
    "05_results/CAD_INSPECT_REFS_SUMMARY_V1.json": (
        "B601_GRIPPER_2P_CAD_INSPECT_REFS_SUMMARY_V1"
    ),
    "05_results/FRAME_AND_UNIT_TRANSFORM_AUDIT_V1.json": (
        "B601_GRIPPER_2P_FRAME_AND_UNIT_TRANSFORM_AUDIT_V1"
    ),
    "05_results/FRESH_PROCESS_DETERMINISTIC_REPLAY_V1.json": (
        "B601_GRIPPER_2P_FRESH_PROCESS_DETERMINISTIC_REPLAY_V1"
    ),
    "05_results/NEGATIVE_CONTROLS_V1.json": "B601_GRIPPER_2P_NEGATIVE_CONTROLS_V1",
    "05_results/RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json": (
        "B601_GRIPPER_2P_RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1"
    ),
    "05_results/SOURCE_PIN_RECHECK_V1.json": "B601_GRIPPER_2P_SOURCE_PIN_RECHECK_V1",
    "05_results/STATE_AND_FRAME_EVIDENCE_V1.json": (
        "B601_GRIPPER_2P_STATE_AND_FRAME_EVIDENCE_V1"
    ),
    "05_results/THREE_CONTAINER_SOLID_IDENTITY_AND_VALIDITY_LEDGER_V1.json": (
        "B601_GRIPPER_2P_THREE_CONTAINER_SOLID_IDENTITY_AND_VALIDITY_LEDGER_V1"
    ),
    "05_results/UNIT_AND_UNCERTAINTY_AUDIT_V1.json": (
        "B601_GRIPPER_2P_UNIT_AND_UNCERTAINTY_AUDIT_V1"
    ),
    "07_reviews/CAD_SNAPSHOT_REVIEW_V1.json": (
        "B601_GRIPPER_2P_CAD_SNAPSHOT_REVIEW_V1"
    ),
    "07_reviews/CAD_VIEWER_STARTUP_RECEIPT_V1.json": (
        "B601_GRIPPER_2P_CAD_VIEWER_STARTUP_RECEIPT_V1"
    ),
}


def _strict_json(path: Path) -> dict:
    """Load JSON while rejecting duplicate keys and non-finite constants."""

    def no_duplicates(pairs: list[tuple[str, object]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            if key in result:
                raise AssertionError(f"duplicate JSON key {key!r} in {path}")
            result[key] = value
        return result

    def no_nonfinite(token: str) -> None:
        raise AssertionError(f"non-finite JSON constant {token!r} in {path}")

    result = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=no_duplicates,
        parse_constant=no_nonfinite,
    )
    assert isinstance(result, dict), f"top-level JSON object required: {path}"
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _workspace_root() -> Path:
    for candidate in (PACKAGE_DIR, *PACKAGE_DIR.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise AssertionError("workspace root containing PROJECT_MAP.md was not found")


WORKSPACE_ROOT = _workspace_root()


def _assert_bound_file(record: dict) -> Path:
    path = WORKSPACE_ROOT / record["path"]
    assert path.is_file(), path
    assert path.stat().st_size == record["bytes"], path
    assert _sha256(path) == record["sha256"], path
    return path


def _receipt(object_name: str) -> dict:
    return _strict_json(RECEIPT_PATHS[object_name])


def _npz_scalar(payload: dict[str, np.ndarray], key: str) -> object:
    value = np.asarray(payload[key])
    assert value.ndim == 0, key
    return value.item()


@pytest.fixture(scope="module")
def runtime_npz_payloads() -> dict[str, dict[str, np.ndarray]]:
    runtime = _strict_json(RESULTS_DIR / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json")
    payloads: dict[str, dict[str, np.ndarray]] = {}
    for object_name in OBJECTS:
        path = WORKSPACE_ROOT / runtime["objects"][object_name]["runtime_npz"]["path"]
        with np.load(path, allow_pickle=False) as archive:
            payloads[object_name] = {key: np.array(archive[key], copy=True) for key in archive.files}
    return payloads


def test_json_documents_are_strict_and_schema_bound() -> None:
    observed = set()
    for directory in (CONTRACT_DIR, RESULTS_DIR, REVIEWS_DIR):
        for path in directory.glob("*.json"):
            document = _strict_json(path)
            assert isinstance(document.get("schema"), str) and document["schema"]
            observed.add(path.relative_to(PACKAGE_DIR).as_posix())

    for relative_path, expected_schema in EXPECTED_SCHEMAS.items():
        assert relative_path in observed
        assert _strict_json(PACKAGE_DIR / relative_path)["schema"] == expected_schema


def test_contract_scope_is_three_container_step_first_and_local_only() -> None:
    contract = _strict_json(CONTRACT_PATH)
    candidates = contract["candidate_set"]
    requirements = contract["geometry_integrity_requirements"]
    assert contract["authority_scope"] == (
        "THREE_LOCAL_STEP_FIRST_B601_GRIPPER_GEOMETRY_CANDIDATES_ONLY"
    )
    assert candidates["container_count_required"] == 3
    assert candidates["single_solid_requirement"] is False
    assert candidates["aggregate_assembly_container_authorized"] is False
    assert requirements["step_first"] is True
    assert requirements["primary_format"] == "STEP"
    assert contract["review_status"] == "CONTRACT_DRAFT_PENDING_INDEPENDENT_BUILD_AND_OWNER_REVIEW"
    assert contract["next_stage_authorized"] is False
    assert contract["parent_gate_credit"] is False
    assert contract["release_credit"] is False


def test_contract_candidate_frames_and_expected_counts_are_exact() -> None:
    contract = _strict_json(CONTRACT_PATH)
    candidates = contract["candidate_set"]["authorized_candidates"]
    by_link = {candidate["owning_urdf_link"]: candidate for candidate in candidates}
    assert set(by_link) == set(OBJECTS)
    for object_name in OBJECTS:
        candidate = by_link[object_name]
        assert candidate["registry_object_id"] == OBJECT_IDS[object_name]
        assert candidate["output_frame"] == object_name
        assert candidate["output_step_length_unit"] == "mm"
        assert candidate["expected_output_solid_count"] == EXPECTED_SOLID_COUNTS[object_name]
    assert by_link["gripper_link"]["frame_operation"] == "IDENTITY"
    assert "INVERSE" in by_link["gripper_left"]["frame_operation"]
    assert "INVERSE" in by_link["gripper_right"]["frame_operation"]


def test_source_authority_lock_has_28_unique_byte_exact_pins() -> None:
    lock = _strict_json(SOURCE_LOCK_PATH)
    pins = lock["source_pins"]
    assert len(pins) == 28
    assert len({pin["source_id"] for pin in pins}) == 28
    assert len({pin["path"] for pin in pins}) == 28
    for pin in pins:
        assert len(pin["sha256"]) == 64
        assert pin["sha256"] == pin["sha256"].upper()
        _assert_bound_file(pin)

    contract_binding = _strict_json(CONTRACT_PATH)["source_authority_lock"]
    bound_lock = CONTRACT_DIR / contract_binding["path"]
    assert bound_lock.resolve() == SOURCE_LOCK_PATH.resolve()
    assert bound_lock.stat().st_size == contract_binding["bytes"]
    assert _sha256(bound_lock) == contract_binding["sha256"]


def test_source_pin_recheck_reproduces_lock_without_authority_change() -> None:
    lock = _strict_json(SOURCE_LOCK_PATH)
    recheck = _strict_json(RESULTS_DIR / "SOURCE_PIN_RECHECK_V1.json")
    assert recheck["source_pin_count"] == 28
    assert recheck["source_pin_count_verified"] == 28
    assert recheck["all_bytes_and_sha256_match"] is True
    assert len(recheck["pins"]) == 28
    locked = {pin["source_id"]: pin for pin in lock["source_pins"]}
    for pin in recheck["pins"]:
        original = locked[pin["source_id"]]
        assert pin["match"] is True
        assert (pin["path"], pin["bytes"], pin["sha256"]) == (
            original["path"],
            original["bytes"],
            original["sha256"],
        )
    assert all(value is False for value in recheck["authority_flags"].values())


def test_primary_step_records_are_hash_bound_in_mm_and_owning_frames() -> None:
    runtime = _strict_json(RESULTS_DIR / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json")
    builder = _strict_json(RESULTS_DIR / "BUILDER_EVIDENCE_V1.json")
    seen_paths = set()
    for object_name in OBJECTS:
        step = runtime["objects"][object_name]["source_step"]
        path = _assert_bound_file(step)
        assert step == builder["outputs"][object_name]["step"]
        assert step["units"] == "mm"
        assert step["frame"] == object_name
        assert path.suffix.lower() == ".step"
        seen_paths.add(path.resolve())
    assert len(seen_paths) == 3


def test_all_step_runtime_and_receipt_outputs_match_builder_hashes() -> None:
    builder = _strict_json(RESULTS_DIR / "BUILDER_EVIDENCE_V1.json")
    expected_keys = {"step", "runtime_ply", "runtime_npz", "runtime_stl", "receipt"}
    observed_paths = set()
    for object_name in OBJECTS:
        records = builder["outputs"][object_name]
        assert set(records) == expected_keys
        for key in expected_keys:
            path = _assert_bound_file(records[key])
            observed_paths.add(path.resolve())
            if key.startswith("runtime_"):
                assert records[key]["units"] == "m"
    assert len(observed_paths) == 15


def test_fresh_process_receipt_is_external_single_invocation_evidence() -> None:
    replay = _strict_json(RESULTS_DIR / "FRESH_PROCESS_DETERMINISTIC_REPLAY_V1.json")
    assert replay["status"] == "PASS"
    assert replay["artifact_count"] == 22
    assert replay["checks"] and all(replay["checks"].values())
    process = replay["process_contract"]
    assert process["fresh_cpython_process"] is True
    assert process["maximum_builder_invocations_in_child_process"] == 1
    assert process["builder_invocation"].endswith("--check")
    assert all(value is False for value in replay["authority_flags"].values())


def test_native_lineage_is_9_24_24_with_wrapper_excluded() -> None:
    contract = _strict_json(CONTRACT_PATH)
    lock = _strict_json(SOURCE_LOCK_PATH)
    ledger = _strict_json(
        RESULTS_DIR / "THREE_CONTAINER_SOLID_IDENTITY_AND_VALIDITY_LEDGER_V1.json"
    )
    lineage = contract["solid_accounting_contract"]["native_lineage"]
    assert lineage["physical_body_count_excluding_aggregate_wrapper"] == 57
    assert lineage["grouping"] == {"palm": 9, "left": 24, "right": 24}
    assert lineage["excluded_aggregate_wrapper"] == "B51_REF_gripper_detail_LINKLOCAL057"
    assert lock["solid_accounting_lock"]["native_lineage_physical_body_count"] == 57
    assert ledger["native_lineage_physical_body_count"] == 57
    assert ledger["native_aggregate_wrapper_excluded"] == lineage["excluded_aggregate_wrapper"]


def test_reopened_container_counts_are_12_24_24_total_60() -> None:
    contract = _strict_json(CONTRACT_PATH)
    ledger = _strict_json(
        RESULTS_DIR / "THREE_CONTAINER_SOLID_IDENTITY_AND_VALIDITY_LEDGER_V1.json"
    )
    assert contract["solid_accounting_contract"]["new_candidate_expected_reopen_counts"] == {
        "palm": 12,
        "left": 24,
        "right": 24,
        "total": 60,
    }
    assert ledger["container_count"] == 3
    assert ledger["output_solid_count"] == 60
    assert {
        name: ledger["containers"][name]["solid_count"] for name in OBJECTS
    } == EXPECTED_SOLID_COUNTS
    assert ledger["checks"]["output_counts_12_24_24_total_60"] is True


def test_all_60_solid_records_are_valid_closed_and_positive() -> None:
    ledger = _strict_json(
        RESULTS_DIR / "THREE_CONTAINER_SOLID_IDENTITY_AND_VALIDITY_LEDGER_V1.json"
    )
    solids = [
        solid
        for object_name in OBJECTS
        for solid in ledger["containers"][object_name]["solids"]
    ]
    assert len(solids) == 60
    for solid in solids:
        assert solid["brep_valid"] is True
        assert solid["all_shells_closed"] is True
        assert solid["shell_count"] >= 1
        assert solid["face_count"] >= 1
        assert math.isfinite(solid["volume_mm3"]) and solid["volume_mm3"] > 0.0
        bbox = np.asarray(solid["bbox_mm"], dtype=np.float64)
        assert bbox.shape == (2, 3)
        assert np.all(np.isfinite(bbox))
        assert np.all(bbox[1] > bbox[0])
    assert ledger["checks"]["all_solids_valid_closed_and_positive"] is True


def test_solid_identity_indices_membership_and_wrapper_exclusion() -> None:
    ledger = _strict_json(
        RESULTS_DIR / "THREE_CONTAINER_SOLID_IDENTITY_AND_VALIDITY_LEDGER_V1.json"
    )
    wrapper = ledger["native_aggregate_wrapper_excluded"]
    for object_name in OBJECTS:
        solids = ledger["containers"][object_name]["solids"]
        assert [solid["output_solid_index"] for solid in solids] == list(range(len(solids)))
        source_ids = [solid["source_member_id"] for solid in solids]
        assert len(source_ids) == len(set(source_ids))
        assert wrapper not in source_ids
    assert ledger["checks"]["all_source_member_ids_unique_per_container"] is True
    assert ledger["checks"]["no_fusion_envelope_connector_or_wrapper"] is True
    assert ledger["system_authority_increment"] == 0


def test_local_receipts_are_pending_local_candidates_only() -> None:
    for object_name in OBJECTS:
        receipt = _receipt(object_name)
        assert receipt["object_id"] == OBJECT_IDS[object_name]
        assert receipt["classification"] == "PENDING_OWNER_REVIEW"
        assert receipt["authority_scope"] == "LOCAL_STEP_FIRST_COLLISION_GEOMETRY_CANDIDATE_ONLY"
        assert receipt["verdict"] == (
            "LOCAL_GEOMETRY_CANDIDATE_PASS__PENDING_OWNER_STATE_MAP_AND_SYSTEM_BIND__"
            "NO_PAIR_EDGE_PATH_RELEASE_CREDIT"
        )
        assert receipt["authority_flags"]["candidate_may_be_submitted_for_owner_binding"] is True
        for flag in FORBIDDEN_AUTHORITY_FLAGS:
            if flag in receipt["authority_flags"]:
                assert receipt["authority_flags"][flag] is False


def test_local_receipt_geometry_checks_and_topology_counts_pass() -> None:
    for object_name in OBJECTS:
        receipt = _receipt(object_name)
        geometry = receipt["geometry"]
        assert receipt["checks"] and all(receipt["checks"].values())
        assert geometry["solid_count"] == EXPECTED_SOLID_COUNTS[object_name]
        assert geometry["shell_count"] == EXPECTED_SOLID_COUNTS[object_name]
        assert len(geometry["solid_identity"]) == EXPECTED_SOLID_COUNTS[object_name]
        assert geometry["per_solid_closed"] is True
        assert geometry["per_solid_consistently_oriented"] is True
        assert geometry["boundary_edge_count"] == 0
        assert geometry["nonmanifold_edge_count"] == 0
        assert geometry["orientation_mismatch_edge_count"] == 0
        assert geometry["runtime_step_bbox_max_abs_error_mm"] <= 0.10
        assert geometry["runtime_mesh_brep_volume_relative_error"] <= 0.005
        assert geometry["primary_brep_to_m5_q0_bbox_max_abs_error_mm"] <= 0.001
        assert geometry["runtime_mesh_to_m5_q0_bbox_max_abs_error_mm"] <= 0.001


def test_accepted_urdf_is_byte_pinned() -> None:
    ledger = _strict_json(FRAME_LEDGER_PATH)
    urdf_record = ledger["source_pins"]["accepted_b601_urdf"]
    urdf_path = _assert_bound_file(urdf_record)
    source_lock = _strict_json(SOURCE_LOCK_PATH)
    locked = {
        pin["source_id"]: pin for pin in source_lock["source_pins"]
    }["accepted_b601_urdf"]
    assert (locked["path"], locked["bytes"], locked["sha256"]) == (
        urdf_record["path"],
        urdf_record["bytes"],
        urdf_record["sha256"],
    )
    assert urdf_path.suffix.lower() == ".urdf"


def test_urdf_literal_prismatic_axes_and_limits_are_preserved() -> None:
    ledger = _strict_json(FRAME_LEDGER_PATH)
    urdf_path = WORKSPACE_ROOT / ledger["source_pins"]["accepted_b601_urdf"]["path"]
    root = ET.parse(urdf_path).getroot()
    for joint_name in ("gripper_joint1", "gripper_joint2"):
        joint = root.find(f"./joint[@name='{joint_name}']")
        assert joint is not None and joint.attrib == {"name": joint_name, "type": "prismatic"}
        assert joint.find("axis").attrib["xyz"] == "1 0 0"  # type: ignore[union-attr]
        assert joint.find("limit").attrib == {  # type: ignore[union-attr]
            "lower": "0",
            "upper": "0.0715",
            "effort": "100",
            "velocity": "15",
        }


def test_urdf_literal_origins_and_gripper_topology_are_preserved() -> None:
    ledger = _strict_json(FRAME_LEDGER_PATH)
    urdf_path = WORKSPACE_ROOT / ledger["source_pins"]["accepted_b601_urdf"]["path"]
    root = ET.parse(urdf_path).getroot()
    expected = {
        "gripper_joint": ("link6", "gripper_link", "0 0 0.15971", "0 -1.5708 0"),
        "gripper_joint1": (
            "gripper_link", "gripper_left", "-0.042091 2.7531E-05 -1.3031E-05", "0 0 -1.5708"
        ),
        "gripper_joint2": (
            "gripper_link", "gripper_right", "-0.042091 -2.7531E-05 1.3031E-05", "0 0 1.5708"
        ),
    }
    for joint_name, (parent, child, xyz, rpy) in expected.items():
        joint = root.find(f"./joint[@name='{joint_name}']")
        assert joint is not None
        assert joint.find("parent").attrib["link"] == parent  # type: ignore[union-attr]
        assert joint.find("child").attrib["link"] == child  # type: ignore[union-attr]
        assert joint.find("origin").attrib == {"xyz": xyz, "rpy": rpy}  # type: ignore[union-attr]


def test_frame_transform_evidence_preserves_child_link_ownership() -> None:
    evidence = _strict_json(RESULTS_DIR / "STATE_AND_FRAME_EVIDENCE_V1.json")
    audit = _strict_json(RESULTS_DIR / "FRAME_AND_UNIT_TRANSFORM_AUDIT_V1.json")
    rule = evidence["frame_rule"]
    assert rule["direct_link6_binding_rejected"] is True
    assert rule["double_application_forbidden"] is True
    assert rule["palm_primary_frame"] == "gripper_link"
    assert rule["left_primary_frame"] == "gripper_left"
    assert rule["right_primary_frame"] == "gripper_right"
    assert "APPLIED_ONCE" in rule["runtime_application"]
    assert audit["checks"] and all(audit["checks"].values())
    joints = evidence["urdf_contract"]["joints"]
    assert joints["gripper_joint1"]["child"] == "gripper_left"
    assert joints["gripper_joint2"]["child"] == "gripper_right"
    assert joints["gripper_joint1"]["axis_joint"] == [1.0, 0.0, 0.0]
    assert joints["gripper_joint2"]["axis_joint"] == [1.0, 0.0, 0.0]


def test_owner_state_map_remains_false_null_and_zero_fill_forbidden() -> None:
    contract = _strict_json(CONTRACT_PATH)
    frame_ledger = _strict_json(FRAME_LEDGER_PATH)
    state = _strict_json(RESULTS_DIR / "STATE_AND_FRAME_EVIDENCE_V1.json")
    hold = contract["owner_configuration_to_travel_hold"]
    assert hold["configuration_travel_authority"] is None
    assert hold["authoritative_gripper_joint_values"] is None
    assert hold["zero_fill_forbidden"] is True
    assert hold["named_state_geometry_emission_authorized"] is False
    assert hold["scene_instance_binding_authorized"] is False

    state_ledger = frame_ledger["configuration_state_ledger"]
    assert state_ledger["configuration_travel_authority"] is None
    assert state_ledger["production_complete_state_vector_count"] == 0
    assert len(state_ledger["configurations"]) == 9
    assert all(
        row["gripper_joint1_m"] is None and row["gripper_joint2_m"] is None
        for row in state_ledger["configurations"]
    )
    assert state["raw_numeric_state_contract"]["named_state_labels_authorized"] is False
    assert state["raw_numeric_state_contract"]["owner_state_map_conflict_resolved"] is False


def test_runtime_npz_metadata_units_frames_and_keysets(
    runtime_npz_payloads: dict[str, dict[str, np.ndarray]],
) -> None:
    expected_keys = {
        "faces", "frame", "object_id", "solid_ids", "transform_application_count", "units", "vertices_m"
    }
    for object_name, payload in runtime_npz_payloads.items():
        assert set(payload) == expected_keys
        assert _npz_scalar(payload, "units") == "m"
        assert _npz_scalar(payload, "frame") == object_name
        assert _npz_scalar(payload, "object_id") == OBJECT_IDS[object_name]
        assert int(_npz_scalar(payload, "transform_application_count")) == 1


def test_runtime_npz_topology_is_finite_nondegenerate_and_in_bounds(
    runtime_npz_payloads: dict[str, dict[str, np.ndarray]],
) -> None:
    for payload in runtime_npz_payloads.values():
        vertices = payload["vertices_m"]
        faces = payload["faces"]
        solid_ids = payload["solid_ids"]
        assert vertices.ndim == 2 and vertices.shape[1] == 3
        assert vertices.dtype == np.float64 and np.all(np.isfinite(vertices))
        assert faces.ndim == 2 and faces.shape[1] == 3
        assert np.issubdtype(faces.dtype, np.unsignedinteger)
        assert solid_ids.shape == (len(faces),)
        assert np.issubdtype(solid_ids.dtype, np.unsignedinteger)
        assert len(faces) > 0 and int(faces.min()) >= 0 and int(faces.max()) < len(vertices)
        assert np.all(faces[:, 0] != faces[:, 1])
        assert np.all(faces[:, 1] != faces[:, 2])
        assert np.all(faces[:, 0] != faces[:, 2])


def test_runtime_npz_counts_bounds_and_solid_ids_match_receipts(
    runtime_npz_payloads: dict[str, dict[str, np.ndarray]],
) -> None:
    runtime = _strict_json(RESULTS_DIR / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json")
    for object_name, payload in runtime_npz_payloads.items():
        vertices = payload["vertices_m"]
        faces = payload["faces"]
        solid_ids = payload["solid_ids"]
        vertex_count, triangle_count = EXPECTED_RUNTIME_COUNTS[object_name]
        assert vertices.shape == (vertex_count, 3)
        assert faces.shape == (triangle_count, 3)
        assert np.array_equal(np.unique(solid_ids), np.arange(EXPECTED_SOLID_COUNTS[object_name]))
        record = runtime["objects"][object_name]
        assert record["runtime_vertex_count"] == vertex_count
        assert record["runtime_triangle_count"] == triangle_count
        actual_bounds = np.stack((vertices.min(axis=0), vertices.max(axis=0)))
        max_delta_mm = float(
            np.max(np.abs(actual_bounds - np.asarray(record["bounds_m"], dtype=np.float64)))
            * 1000.0
        )
        assert max_delta_mm <= _receipt(object_name)["geometry"][
            "runtime_step_bbox_max_abs_error_mm"
        ] + 1e-12
        assert max_delta_mm <= record["runtime_mesh_chordal_derate_mm"]


def test_single_mm_to_m_scale_and_pair_derate_are_exact() -> None:
    runtime = _strict_json(RESULTS_DIR / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json")
    audit = _strict_json(RESULTS_DIR / "UNIT_AND_UNCERTAINTY_AUDIT_V1.json")
    assert runtime["derivation"] == (
        "VALIDATED_PRIMARY_STEP_MM_TO_OWNING_LINK_LOCAL_RUNTIME_PLY_NPZ_STL_M"
    )
    for object_name in OBJECTS:
        record = runtime["objects"][object_name]
        assert record["source_step"]["units"] == "mm"
        assert record["runtime_npz"]["units"] == "m"
        assert record["runtime_ply"]["units"] == "m"
        assert record["runtime_stl"]["units"] == "m"
        assert record["scale_application_count"] == 1
        assert record["scale_factor"] == 0.001
        assert record["runtime_mesh_chordal_derate_mm"] == 0.05

    derates = audit["derates"]
    assert audit["checks"] and all(audit["checks"].values())
    assert derates["manufacturing_as_built_mm"] is None
    assert derates["primary_step_numeric_mm_per_object"] == 1e-6
    assert derates["runtime_mesh_chordal_mm_per_object"] == 0.05
    assert derates["runtime_mesh_pair_lower_bound_debit_mm"] == 2.0 * (0.05 + 1e-6)
    assert "CANNOT_BE_ZERO_FILLED" in audit["unknown_policy"]


def test_system_counters_and_authority_remain_zero_or_false() -> None:
    contract = _strict_json(CONTRACT_PATH)
    invariants = contract["current_system_authority_invariants"]
    assert invariants == {
        "active_object_rows": 150,
        "asset_level_operational_authority_rows": 1,
        "required_pair_queries": 11166,
        "system_pair_queries_executed": 0,
        "system_edges_certified": 0,
        "stage_instances_bound": 0,
        "stage_instances_required": 3,
        "system_safe_certificates": 0,
        "complete_system_operational_collision_asset_set_bound": False,
        "system_pair_evaluation_authorized": False,
        "path_search_authorized": False,
        "path_search_executed": False,
        "parent_gate_credit": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    for path in (
        RESULTS_DIR / "BUILDER_EVIDENCE_V1.json",
        RESULTS_DIR / "NEGATIVE_CONTROLS_V1.json",
        RESULTS_DIR / "SOURCE_PIN_RECHECK_V1.json",
    ):
        document = _strict_json(path)
        for flag in FORBIDDEN_AUTHORITY_FLAGS:
            if flag in document.get("authority_flags", {}):
                assert document["authority_flags"][flag] is False


def test_negative_controls_are_20_of_20_and_44_of_44() -> None:
    negative = _strict_json(RESULTS_DIR / "NEGATIVE_CONTROLS_V1.json")
    summary = negative["summary"]
    assert summary == {
        "all_controls_caught": True,
        "controls_caught": 20,
        "controls_executed": 20,
        "controls_required": 20,
        "subcases_caught": 44,
        "subcases_executed": 44,
    }
    controls = negative["controls"]
    assert len(controls) == 20
    assert len({control["control_id"] for control in controls}) == 20
    assert sum(control["case_count"] for control in controls) == 44
    for control in controls:
        assert control["status"] == "CAUGHT"
        assert control["caught_count"] == control["case_count"] == len(control["cases"])
        for case in control["cases"]:
            assert case["status"] == "CAUGHT"
            assert case["caught_message"].startswith(case["expected_rejection_code"])
    assert negative["verdict"].startswith(
        "PASS_20_OF_20_CONTRACT_NEGATIVE_CONTROLS_AND_44_OF_44_MUTATION_SUBCASES_CAUGHT"
    )


def test_negative_controls_are_isolated_and_preserve_system_snapshot() -> None:
    negative = _strict_json(RESULTS_DIR / "NEGATIVE_CONTROLS_V1.json")
    isolation = negative["execution_isolation"]
    assert isolation["cad_or_brep_execution_called"] is False
    assert isolation["pair_query_called"] is False
    assert isolation["path_search_called"] is False
    assert isolation["real_source_or_output_assets_modified"] is False
    assert isolation["temporary_directory_deleted_after_cases"] is True
    snapshot = negative["system_invariant_snapshot"]
    assert snapshot["unchanged"] is True
    assert snapshot["before_sha256"] == snapshot["after_sha256"]
    assert negative["current_system_authority_invariants"] == _strict_json(CONTRACT_PATH)[
        "current_system_authority_invariants"
    ]
    assert all(value is False for value in negative["authority_flags"].values())


def test_cad_inspect_refs_is_three_of_three_with_expected_counts() -> None:
    inspect = _strict_json(RESULTS_DIR / "CAD_INSPECT_REFS_SUMMARY_V1.json")
    assert inspect["rerun"] == {
        "environment": "PYTHONUTF8=1",
        "errors": 0,
        "entries_passed": 3,
        "entries_required": 3,
        "status": "PASS",
    }
    for object_name in OBJECTS:
        entry = inspect["entries"][object_name]
        expected_count = EXPECTED_SOLID_COUNTS[object_name]
        assert entry["tool_ok"] is True
        assert entry["warnings"] == []
        assert entry["kind"] == "assembly"
        assert entry["shape_count"] == expected_count
        assert entry["leaf_occurrence_count"] == expected_count
        assert entry["occurrence_count"] == expected_count + 1
        assert entry["step_sha256"] == _receipt(object_name)["primary_step"]["sha256"]
    assert inspect["first_attempt"]["asset_hashes_changed"] is False


def test_snapshot_review_has_hash_bound_three_by_three_coverage() -> None:
    review = _strict_json(REVIEWS_DIR / "CAD_SNAPSHOT_REVIEW_V1.json")
    assert review["visual_review_pass"] is True
    assert review["checks"] and all(review["checks"].values())
    assert len(review["images"]) == 9
    observed_views = set()
    for image in review["images"]:
        path = REVIEWS_DIR / image["name"]
        assert path.is_file() and path.stat().st_size == image["bytes"]
        assert _sha256(path) == image["sha256"]
        tokens = image["name"].split("_")
        observed_views.add((tokens[0], tokens[1]))
    assert observed_views == {
        (object_name, view)
        for object_name in ("palm", "left", "right")
        for view in ("front", "iso", "top")
    }
    assert "DOES_NOT_PROVE" in review["visual_review_use_limit"]


def test_viewer_startup_failure_does_not_upgrade_gate_or_authority() -> None:
    viewer = _strict_json(REVIEWS_DIR / "CAD_VIEWER_STARTUP_RECEIPT_V1.json")
    contract = _strict_json(CONTRACT_PATH)
    assert viewer["viewer_started"] is False
    assert viewer["attempt"]["exit_code"] == 1
    assert viewer["disposition"] == "VIEWER_UNAVAILABLE_MISSING_AGENT_START"
    assert viewer["geometry_or_authority_impact"] is False
    assert viewer["raw_start_or_serve_used_as_unapproved_substitute"] is False
    assert viewer["fallback_evidence"] == {
        "cad_inspect_refs_three_of_three_pass": True,
        "cad_snapshot_images_reviewed": 9,
        "ocp_independent_reopen_required_separately": True,
    }
    assert contract["next_stage_authorized"] is False
    assert contract["parent_gate_credit"] is False
    assert contract["release_credit"] is False
    for object_name in OBJECTS:
        flags = _receipt(object_name)["authority_flags"]
        assert flags["system_pair_evaluation_authorized"] is False
        assert flags["path_search_authorized"] is False
        assert flags["next_stage_authorized"] is False
        assert flags["release_credit"] is False
