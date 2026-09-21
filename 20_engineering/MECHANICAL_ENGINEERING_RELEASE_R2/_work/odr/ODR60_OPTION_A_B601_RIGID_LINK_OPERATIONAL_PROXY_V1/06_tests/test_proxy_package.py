"""Release-facing tests for the six-link operational-proxy candidate package."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


PACKAGE_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = PACKAGE_DIR / "05_results"
CONTRACT_PATH = (
    PACKAGE_DIR / "00_contract" / "B601_RIGID_LINK_OPERATIONAL_COLLISION_CONTRACT_V1.json"
)
SOURCE_LOCK_PATH = PACKAGE_DIR / "01_sources" / "SOURCE_AUTHORITY_LOCK_V1.json"
NEGATIVE_SCRIPT = PACKAGE_DIR / "04_validation" / "run_negative_controls.py"
NEGATIVE_RESULT = RESULTS_DIR / "NEGATIVE_CONTROLS_V1.json"
INDEPENDENT_RESULT = RESULTS_DIR / "INDEPENDENT_VALIDATION_V1.json"
LOCAL_GATE_PATH = RESULTS_DIR / "B601_RIGID_LINK_OPERATIONAL_PROXY_LOCAL_GATE_V1.json"
LINK_IDS = tuple(f"link{index}" for index in range(1, 7))
OBJECT_IDS = tuple(f"A::{link_id}" for link_id in LINK_IDS)
FORBIDDEN_IDS = {
    "A::base_link",
    "A::gripper_link",
    "A::gripper_left",
    "A::gripper_right",
}
AUTHORITY_FLAGS = (
    "parent_mechanical_gate_reissued",
    "system_registry_reissued",
    "system_pair_evaluation_authorized",
    "path_search_authorized",
    "next_stage_authorized",
    "release_credit",
)


def _strict_json(path: Path) -> dict:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            if key in result:
                raise AssertionError(f"duplicate JSON key {key!r} in {path}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


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
    raise AssertionError("workspace root not found")


def _load_negative_module():
    spec = importlib.util.spec_from_file_location("b601_proxy_negative_controls", NEGATIVE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _values_for_key(value: object, key: str) -> list[object]:
    values: list[object] = []
    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if current_key == key:
                values.append(current_value)
            values.extend(_values_for_key(current_value, key))
    elif isinstance(value, list):
        for current_value in value:
            values.extend(_values_for_key(current_value, key))
    return values


def _strings(value: object) -> list[str]:
    result: list[str] = []
    if isinstance(value, str):
        result.append(value)
    elif isinstance(value, dict):
        for current in value.values():
            result.extend(_strings(current))
    elif isinstance(value, list):
        for current in value:
            result.extend(_strings(current))
    return result


def _npz_scalar(archive: np.lib.npyio.NpzFile, key: str) -> str:
    value = np.asarray(archive[key])
    assert value.size == 1, f"{key} must be a scalar-like one-element array"
    return str(value.reshape(-1)[0])


def test_contract_scope_and_authority_are_exact() -> None:
    contract = _strict_json(CONTRACT_PATH)
    assert contract["schema"] == "B601_RIGID_LINK_OPERATIONAL_COLLISION_CONTRACT_V1"
    assert tuple(contract["object_ids"]) == OBJECT_IDS
    assert set(contract["excluded_objects"]) == FORBIDDEN_IDS
    assert contract["geometry_method"]["slab_count"] == 12
    assert contract["geometry_method"]["source_unit"] == "m"
    assert contract["geometry_method"]["step_unit"] == "mm"
    assert contract["geometry_method"]["runtime_unit"] == "m"
    assert contract["geometry_method"]["transverse_guard_mm"] == 0.005
    assert contract["geometry_method"]["longitudinal_guard_mm"] == 0.0
    for flag in AUTHORITY_FLAGS:
        assert contract["authority_flags"][flag] is False


def test_source_lock_and_parent_state_are_byte_preserved() -> None:
    lock = _strict_json(SOURCE_LOCK_PATH)
    root = _workspace_root()
    assert tuple(lock["link_sources"]) == LINK_IDS
    for record in list(lock["immutable_sources"].values()) + list(lock["link_sources"].values()):
        path = root / record["path"]
        assert path.is_file(), path
        assert path.stat().st_size == record["bytes"], path
        assert _sha256(path) == record["sha256"], path
    assert lock["source_mutation_authorized"] is False
    assert lock["accepted_urdf_mutation_authorized"] is False
    assert lock["parent_gate_mutation_authorized"] is False

    parent_gate = _strict_json(
        root / lock["immutable_sources"]["current_mechanical_parent_gate"]["path"]
    )
    assert parent_gate["gate_a_pass"] is False
    assert parent_gate["next_stage_authorized"] is False
    assert parent_gate["release_credit"] is False

    registry = _strict_json(
        root / lock["immutable_sources"]["m01_system_collision_registry"]["path"]
    )
    assert registry["object_summary"]["known_active_object_count"] == 150
    assert registry["object_summary"]["category_counts"] == {
        "A": 10,
        "C": 9,
        "F": 4,
        "R": 121,
        "S": 6,
    }

    prebind_gate = _strict_json(
        root / lock["immutable_sources"]["m01_scene_prebind_gate"]["path"]
    )
    assert prebind_gate["asset_accounting"]["operational_authority_rows"] == 1
    assert prebind_gate["scene_accounting"]["stage_instances_bound"] == 0
    assert prebind_gate["system_execution_state"]["system_pair_queries_executed"] == 0
    assert prebind_gate["system_execution_state"]["system_edges_certified"] == 0
    assert prebind_gate["system_execution_state"]["path_search_executed"] is False
    assert prebind_gate["next_stage_authorized"] is False
    assert prebind_gate["release_credit"] is False


def test_six_primary_and_runtime_assets_are_complete() -> None:
    expected_npz_keys = {
        "boxes_m",
        "vertices_m",
        "triangles",
        "solid_vertex_offsets",
        "solid_triangle_offsets",
        "link_id",
        "units",
        "frame",
    }
    observed_object_ids: list[str] = []
    for link_id in LINK_IDS:
        stem = f"B601_{link_id.upper()}_OPERATIONAL_COLLISION_PROXY_V1"
        step_path = PACKAGE_DIR / "03_assets" / f"{stem}.step"
        npz_path = PACKAGE_DIR / "03_assets" / f"{stem}_RUNTIME.npz"
        stl_path = PACKAGE_DIR / "03_assets" / f"{stem}_RUNTIME_M.stl"
        receipt_path = RESULTS_DIR / f"B601_{link_id.upper()}_LOCAL_GEOMETRY_RECEIPT_V1.json"
        for path in (step_path, npz_path, stl_path, receipt_path):
            assert path.is_file() and path.stat().st_size > 0, path

        with np.load(npz_path, allow_pickle=False) as archive:
            assert set(archive.files) == expected_npz_keys
            boxes = np.asarray(archive["boxes_m"], dtype=np.float64)
            vertices = np.asarray(archive["vertices_m"], dtype=np.float64)
            triangles = np.asarray(archive["triangles"])
            vertex_offsets = np.asarray(archive["solid_vertex_offsets"])
            triangle_offsets = np.asarray(archive["solid_triangle_offsets"])
            assert boxes.shape == (12, 2, 3)
            assert vertices.ndim == 2 and vertices.shape[1] == 3 and len(vertices) > 0
            assert triangles.ndim == 2 and triangles.shape[1] == 3 and len(triangles) > 0
            assert np.issubdtype(triangles.dtype, np.integer)
            assert np.all(np.isfinite(boxes)) and np.all(boxes[:, 1] > boxes[:, 0])
            assert np.all(np.isfinite(vertices))
            assert int(triangles.min()) >= 0 and int(triangles.max()) < len(vertices)
            assert vertex_offsets.shape == (13,) and triangle_offsets.shape == (13,)
            assert int(vertex_offsets[0]) == 0 and int(vertex_offsets[-1]) == len(vertices)
            assert int(triangle_offsets[0]) == 0 and int(triangle_offsets[-1]) == len(triangles)
            assert np.all(np.diff(vertex_offsets) > 0)
            assert np.all(np.diff(triangle_offsets) > 0)
            assert _npz_scalar(archive, "link_id") == link_id
            assert _npz_scalar(archive, "units") == "m"
            assert _npz_scalar(archive, "frame") == f"B601_{link_id.upper()}_LOCAL"

        receipt = _strict_json(receipt_path)
        assert receipt["schema"] == "B601_RIGID_LINK_LOCAL_GEOMETRY_RECEIPT_V1"
        assert receipt["object_id"] == f"A::{link_id}"
        assert receipt["classification"] == "PENDING_OWNER_REVIEW"
        assert receipt["authority_scope"] == "LOCAL_ASSET_LEVEL_COLLISION_GEOMETRY_CANDIDATE_ONLY"
        assert receipt["verdict"] == (
            "LOCAL_GEOMETRY_CANDIDATE_PASS_PENDING_OWNER_REVIEW_NO_SYSTEM_PAIR_OR_PATH_AUTHORITY"
        )
        assert receipt["geometry"]["slab_count"] == 12
        assert receipt["authority_flags"]["candidate_may_be_submitted_for_owner_binding"] is True
        observed_object_ids.append(f"A::{link_id}")
        for flag in AUTHORITY_FLAGS:
            values = _values_for_key(receipt, flag)
            assert not values or all(value is False for value in values), (receipt_path, flag)

    assert tuple(observed_object_ids) == OBJECT_IDS
    assert not (set(observed_object_ids) & FORBIDDEN_IDS)


def test_negative_control_campaign_is_complete_and_deterministic() -> None:
    module = _load_negative_module()
    first = module.run_campaign()
    second = module.run_campaign()
    assert _canonical_bytes(first) == _canonical_bytes(second)
    assert first["baseline_valid"] is True
    assert first["baseline_issues"] == []
    assert first["baseline_counts"] == {
        "local_pending_owner_review_candidate_count": 6,
        "system_registry_operational_asset_count_unchanged": 1,
        "system_active_object_count": 150,
    }
    assert first["case_count"] >= 18
    assert first["cases_detected"] == first["case_count"]
    assert first["all_negative_controls_detected"] is True
    assert all(case["detected"] for case in first["cases"])
    assert first["verdict"].endswith("NEGATIVE_CONTROLS_ALL_CAUGHT")


def test_written_negative_result_matches_fresh_replay() -> None:
    assert NEGATIVE_RESULT.is_file(), NEGATIVE_RESULT
    written = _strict_json(NEGATIVE_RESULT)
    fresh = _load_negative_module().run_campaign()
    assert _canonical_bytes(written) == _canonical_bytes(fresh)
    assert written["baseline_counts"]["local_pending_owner_review_candidate_count"] == 6
    assert (
        written["baseline_counts"]["system_registry_operational_asset_count_unchanged"]
        == 1
    )


def test_independent_validation_and_local_gate_remain_local_only() -> None:
    independent = _strict_json(INDEPENDENT_RESULT)
    gate = _strict_json(LOCAL_GATE_PATH)

    assert independent["schema"] == (
        "B601_RIGID_LINK_OPERATIONAL_PROXY_INDEPENDENT_VALIDATION_V1"
    )
    assert independent["validation_pass"] is True
    assert independent["formal_gate_pass"] is True
    assert independent["review_status"] == "PENDING_OWNER_REVIEW"
    assert independent["summary"]["required_link_count"] == 6
    assert independent["summary"]["passed_link_count"] == 6
    assert independent["summary"]["failed_link_count"] == 0
    assert independent["failures"] == []
    assert independent["global_checks"] and all(independent["global_checks"].values())
    assert set(independent["per_link"]) == set(LINK_IDS)
    for link_id in LINK_IDS:
        link = independent["per_link"][link_id]
        assert link["object_id"] == f"A::{link_id}"
        assert link["runtime_frame"] == f"B601_{link_id.upper()}_LOCAL"
        assert link["validation_pass"] is True
        assert link["checks"] and all(link["checks"].values())

    assert gate["schema"] == "B601_RIGID_LINK_OPERATIONAL_PROXY_LOCAL_GATE_V1"
    assert gate["classification"] == "PENDING_OWNER_REVIEW"
    assert gate["review_status"] == "PENDING_OWNER_REVIEW"
    assert gate["local_candidate_asset_count"] == 6
    candidates = gate["candidate_objects"]
    assert [candidate["object_id"] for candidate in candidates] == list(OBJECT_IDS)
    assert all(candidate["local_geometry_candidate_pass"] is True for candidate in candidates)
    assert all(candidate["system_registry_bound"] is False for candidate in candidates)
    assert not (FORBIDDEN_IDS & {candidate["object_id"] for candidate in candidates})

    system_state = gate["system_state_preserved"]
    assert system_state["known_active_object_count"] == 150
    assert system_state["system_registry_operational_authority_rows"] == 1
    assert system_state["system_registry_candidate_assets_added"] == 0
    assert system_state["system_required_pair_queries"] == 11166
    assert system_state["system_pair_queries_executed"] == 0
    assert system_state["system_edges_certified"] == 0
    assert system_state["stage_instances_bound"] == 0
    assert system_state["path_search_executed"] is False
    assert system_state["TMG4"] == "HOLD"
    assert system_state["G12"] == "FAIL"
    assert gate["criteria_passed"] == gate["criteria_total"] == 6
    assert gate["verdict"] == (
        "6_OF_6_LOCAL_GEOMETRY_CRITERIA_PASS__PENDING_OWNER_REVIEW__TMG4_HOLD__"
        "G12_FAIL__NO_SYSTEM_PAIR_OR_PATH_AUTHORITY__NO_RELEASE_CREDIT"
    )
    for flag in AUTHORITY_FLAGS:
        values = _values_for_key(gate, flag)
        assert values and all(value is False for value in values), flag

    negative = _strict_json(NEGATIVE_RESULT)
    assert negative["all_negative_controls_detected"] is True
    assert negative["cases_detected"] == negative["case_count"]
