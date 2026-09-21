"""Build the isolated M5 physical-geometry and loads closure package.

The builder performs no FEA and creates no flight or manufacturing authority.
It converts the B51 per-configuration assembly-coordinate meshes into true
link-local indexed surfaces, proves the conversion against an independent
stowed pose, builds conservative broad-phase boxes and diagnostic C01--C09
snapshots, and emits fail-closed load/contact/structural contracts.
"""

from __future__ import annotations

import csv
import gc
import hashlib
import importlib.util
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
import yaml
from scipy.spatial import cKDTree


M5 = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[3]
M4 = WORKSPACE / "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1"
TERMINAL = WORKSPACE / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
V5R = WORKSPACE / "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
V5N = WORKSPACE / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
Q1 = WORKSPACE / "20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/02_wp1_loads"
CAD = WORKSPACE / "20_engineering/cad"

URDF = CAD / "spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
POSES = TERMINAL / "04_configurations/F3R2_ARM_INITIAL_POSE.yaml"
SCENE = WORKSPACE / "20_engineering/config/visualization/scene_manifest_v1.yaml"
TARGET_MODELS = WORKSPACE / "20_engineering/config/geometry/target_models_v1.yaml"
ENV_DEPLOYED = TERMINAL / "05_clearance/mesh/ENV_MESH_DEPLOYED.json"
ENV_STOWED = TERMINAL / "05_clearance/mesh/ENV_MESH_STOWED.json"
ENV_EXPORTER = TERMINAL / "99_tools/fc_export_env_mesh.py"
DEPLOYED_PARTS = TERMINAL / "05_clearance/mesh/parts_DEPLOYED"
STOWED_PARTS = TERMINAL / "05_clearance/mesh/parts_STOWED"
GRIPPER_DIR = V5R / "01_native_cad/gripper_r1"
GRIPPER_VALIDATION = V5R / "04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json"
ALT_GRIPPER_CONFIG = V5R / "06_pack_and_go/V5R_NEUTRAL_OPERATIONAL_PACKAGE/interface/CONFIGURATION_MATRIX.csv"
SOLAR_AUTHORITY = V5N / "00_authority/V5_SOLAR_STATE_AUTHORITY_R2B.json"
SOLAR_ORACLE = V5N / "13_validation/V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_20260812T181333.205056Z.json"
M3R_A = WORKSPACE / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/02_neutral_cad/adapter/V4_B601_STAGE_A_INTERFACE_RING_REVB.stl"
M3R_B = WORKSPACE / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/02_neutral_cad/adapter/V4_B601_STAGE_B_LOAD_ADAPTER_REVB2.stl"
MODEL = WORKSPACE / "30_simulation/sim_05_free_floating_arm/b601_model.py"
TARGET_SATELLITE = CAD / "spacecraft_layout/target_satellite_v0/target_satellite_v0.stl"
TARGET_DEBRIS = CAD / "spacecraft_layout/target_debris_v0/target_debris_v0.stl"

TRUE_LOCAL_DIR = M5 / "01_geometry_authority/assets/b601_link_local_surfaces"
BROAD_DIR = M5 / "01_geometry_authority/assets/broadphase_boxes"
SNAPSHOT_DIR = M5 / "02_configurations/snapshots"


def now_local() -> str:
    return datetime.now().astimezone().isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def clean(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if abs(number) < 5.0e-15:
            return 0.0
        return number
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(clean(payload), sort_keys=False, allow_unicode=True), encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def memory_snapshot() -> dict[str, Any]:
    available = None
    total = None
    try:
        import psutil

        snapshot = psutil.virtual_memory()
        available = snapshot.available / 1024**3
        total = snapshot.total / 1024**3
    except Exception:
        pass
    return {
        "sampled_local": now_local(),
        "available_physical_memory_GiB": available,
        "total_physical_memory_GiB": total,
        "legacy_threshold_GiB": 6.0,
        "memory_gate_passed": False,
        "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY",
        "owner_override_used": True,
        "execution_route": "LIGHTWEIGHT_NEUTRAL_GEOMETRY_AND_ANALYTIC_LOADS",
        "note": "The historical 6 GiB gate is not re-labelled PASS even if a later sample rises above the threshold.",
    }


def load_b601_model():
    spec = importlib.util.spec_from_file_location("m5_b601_model", MODEL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import B601 model: {MODEL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transform_m(matrix_m: np.ndarray) -> np.ndarray:
    return np.asarray(matrix_m, dtype=float)


def transform_mm(matrix_m: np.ndarray) -> np.ndarray:
    result = np.asarray(matrix_m, dtype=float).copy()
    result[:3, 3] *= 1000.0
    return result


def merge_surface(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    result = trimesh.Trimesh(vertices=mesh.vertices.copy(), faces=mesh.faces.copy(), process=False)
    result.merge_vertices(digits_vertex=9)
    if len(result.faces):
        result.update_faces(result.unique_faces())
    result.remove_unreferenced_vertices()
    return result


def box_from_bounds(bounds: np.ndarray) -> trimesh.Trimesh:
    bounds = np.asarray(bounds, dtype=float)
    extents = bounds[1] - bounds[0]
    center = (bounds[1] + bounds[0]) / 2.0
    matrix = np.eye(4)
    matrix[:3, 3] = center
    return trimesh.creation.box(extents=extents, transform=matrix)


def sample_vertices(vertices: np.ndarray, maximum: int = 50_000) -> np.ndarray:
    stride = max(1, int(math.ceil(len(vertices) / maximum)))
    return vertices[::stride]


def nearest_residual(source: np.ndarray, target: np.ndarray) -> dict[str, float]:
    query = sample_vertices(source)
    distances, _ = cKDTree(target).query(query, k=1)
    return {
        "sample_count": int(len(query)),
        "maximum_mm": float(np.max(distances)),
        "p99_mm": float(np.quantile(distances, 0.99)),
        "median_mm": float(np.median(distances)),
    }


def load_scene_candidate() -> dict[str, Any]:
    import re

    text = SCENE.read_text(encoding="utf-8")
    q_match = re.search(r"q_rad:\s*\[([^\]]+)\]", text, flags=re.DOTALL)
    capture_match = re.search(r"capture_point_S_m:\s*\[([^\]]+)\]", text)
    if q_match is None or capture_match is None:
        raise RuntimeError("scene candidate fields not found")
    parse = lambda item: [float(value.strip()) for value in item.split(",")]
    return {"q_rad": parse(q_match.group(1)), "capture_point_S_m": parse(capture_match.group(1))}


def create_true_local_assets(arm: Any, base_m: np.ndarray, pose_doc: dict[str, Any]) -> tuple[dict[str, Any], dict[str, trimesh.Trimesh]]:
    TRUE_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    BROAD_DIR.mkdir(parents=True, exist_ok=True)
    q_zero = np.zeros(6)
    q_stow = np.asarray(pose_doc["poses"]["Q_STOW_ENGINEERING_CANDIDATE"]["q_rad"], dtype=float)
    fk_zero = arm.fk(q_zero, T_base=base_m)["T"]
    fk_stow = arm.fk(q_stow, T_base=base_m)["T"]
    rows: dict[str, Any] = {}
    boxes: dict[str, trimesh.Trimesh] = {}

    carriers = list(arm.CHAIN_LINKS) if hasattr(arm, "CHAIN_LINKS") else []
    if not carriers:
        carriers = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6"]
    for link in carriers:
        source_name = f"B51_REF_{link}_LINKLOCAL.stl"
        deployed_path = DEPLOYED_PARTS / source_name
        stowed_path = STOWED_PARTS / source_name
        deployed = trimesh.load_mesh(deployed_path, process=False)
        stowed = trimesh.load_mesh(stowed_path, process=False)
        t_zero_mm = transform_mm(fk_zero[link])
        t_stow_mm = transform_mm(fk_stow[link])
        local_vertices_mm = trimesh.transform_points(deployed.vertices, np.linalg.inv(t_zero_mm))
        reconstructed_stow_mm = trimesh.transform_points(local_vertices_mm, t_stow_mm)
        forward = nearest_residual(reconstructed_stow_mm, stowed.vertices)
        reverse = nearest_residual(stowed.vertices, reconstructed_stow_mm)
        local = trimesh.Trimesh(
            vertices=local_vertices_mm / 1000.0,
            faces=deployed.faces,
            process=False,
        )
        indexed = merge_surface(local)
        surface_path = TRUE_LOCAL_DIR / f"B601_{link}_CAD_SURFACE_LINK_LOCAL_M.ply"
        indexed.export(surface_path, file_type="ply")
        broad = box_from_bounds(indexed.bounds)
        broad_path = BROAD_DIR / f"B601_{link}_CONSERVATIVE_LINK_AABB_M.stl"
        broad.export(broad_path, file_type="stl")
        boxes[link] = broad
        rows[link] = {
            "source_component_label": source_name.replace(".stl", ""),
            "source_coordinate_reality": "TOP_ASSEMBLY_FRAME_MM_DESPITE_LINKLOCAL_COMPONENT_LABEL",
            "carrier_frame": link,
            "deployed_source": {"path": rel(deployed_path), "sha256": sha256(deployed_path)},
            "stowed_source": {"path": rel(stowed_path), "sha256": sha256(stowed_path)},
            "T_link_from_assembly_at_q0_rows": np.linalg.inv(t_zero_mm),
            "local_surface": {
                "path": rel(surface_path),
                "sha256": sha256(surface_path),
                "units": "m",
                "vertices": int(len(indexed.vertices)),
                "faces": int(len(indexed.faces)),
                "watertight": bool(indexed.is_watertight),
                "bounds_link_m": indexed.bounds,
            },
            "conservative_broadphase_box": {
                "path": rel(broad_path),
                "sha256": sha256(broad_path),
                "units": "m",
                "contains_source_vertices": bool(
                    np.all(indexed.vertices >= broad.bounds[0] - 1.0e-12)
                    and np.all(indexed.vertices <= broad.bounds[1] + 1.0e-12)
                ),
            },
            "independent_q0_to_stow_registration": {
                "forward_reconstructed_to_stowed": forward,
                "reverse_stowed_to_reconstructed": reverse,
                "bbox_endpoint_max_abs_residual_mm": float(
                    np.max(np.abs(np.vstack([reconstructed_stow_mm.min(axis=0), reconstructed_stow_mm.max(axis=0)]) - stowed.bounds))
                ),
                "numerical_acceptance_mm": 0.1,
                "source_mesh_linear_deflection_mm": 0.5,
                "pass": max(forward["maximum_mm"], reverse["maximum_mm"]) <= 0.1,
            },
            "use_limit": "SOURCE_BOUND_SURFACE_AND_CONSERVATIVE_BROADPHASE_ONLY_NOT_CONTACT_OR_STRENGTH_AUTHORITY",
        }
        del deployed, stowed, local, indexed, reconstructed_stow_mm, local_vertices_mm
        gc.collect()

    # Legacy gripper is validated as a link6-carried assembly-coordinate object,
    # but is deliberately not exported as the active gripper asset.
    legacy_name = "B51_REF_gripper_detail_LINKLOCAL.stl"
    deployed_path = DEPLOYED_PARTS / legacy_name
    stowed_path = STOWED_PARTS / legacy_name
    deployed = trimesh.load_mesh(deployed_path, process=False)
    stowed = trimesh.load_mesh(stowed_path, process=False)
    t_zero_mm = transform_mm(fk_zero["link6"])
    t_stow_mm = transform_mm(fk_stow["link6"])
    local_vertices_mm = trimesh.transform_points(deployed.vertices, np.linalg.inv(t_zero_mm))
    reconstructed_stow_mm = trimesh.transform_points(local_vertices_mm, t_stow_mm)
    forward = nearest_residual(reconstructed_stow_mm, stowed.vertices)
    reverse = nearest_residual(stowed.vertices, reconstructed_stow_mm)
    rows["legacy_gripper_detail"] = {
        "source_component_label": legacy_name.replace(".stl", ""),
        "source_coordinate_reality": "TOP_ASSEMBLY_FRAME_MM_DESPITE_LINKLOCAL_COMPONENT_LABEL",
        "carrier_frame": "link6",
        "deployed_source": {"path": rel(deployed_path), "sha256": sha256(deployed_path)},
        "stowed_source": {"path": rel(stowed_path), "sha256": sha256(stowed_path)},
        "independent_q0_to_stow_registration": {
            "forward_reconstructed_to_stowed": forward,
            "reverse_stowed_to_reconstructed": reverse,
            "bbox_endpoint_max_abs_residual_mm": float(
                np.max(np.abs(np.vstack([reconstructed_stow_mm.min(axis=0), reconstructed_stow_mm.max(axis=0)]) - stowed.bounds))
            ),
            "numerical_acceptance_mm": 0.1,
            "source_mesh_linear_deflection_mm": 0.5,
            "pass": max(forward["maximum_mm"], reverse["maximum_mm"]) <= 0.1,
        },
        "disposition": "SUPERSEDED_FOR_ACTIVE_GRIPPER_GEOMETRY_BY_R1_SEPARATED_PALM_AND_FINGERS",
    }
    return rows, boxes


def create_gripper_assets(arm: Any, base_m: np.ndarray) -> tuple[dict[str, Any], dict[str, trimesh.Trimesh]]:
    source_names = {
        "palm": "B601_GRIPPER_PALM_RAIL_SLOT_R1.stl",
        "left_finger": "B601_GRIPPER_LEFT_FINGER_NEUTRAL_SOURCE.stl",
        "right_finger": "B601_GRIPPER_RIGHT_FINGER_NEUTRAL_SOURCE.stl",
    }
    records: dict[str, Any] = {}
    boxes: dict[str, trimesh.Trimesh] = {}
    r1_vertices_mm: list[np.ndarray] = []
    for role, filename in source_names.items():
        source = GRIPPER_DIR / filename
        mesh = trimesh.load_mesh(source, process=False)
        r1_vertices_mm.append(np.asarray(mesh.vertices, dtype=float))
        local = trimesh.Trimesh(vertices=mesh.vertices / 1000.0, faces=mesh.faces, process=False)
        indexed = merge_surface(local)
        output = TRUE_LOCAL_DIR / f"B601_GRIPPER_R1_{role.upper()}_GRIPPER_LINK_LOCAL_M.ply"
        indexed.export(output, file_type="ply")
        broad = box_from_bounds(indexed.bounds)
        broad_output = BROAD_DIR / f"B601_GRIPPER_R1_{role.upper()}_CONSERVATIVE_AABB_M.stl"
        broad.export(broad_output, file_type="stl")
        boxes[role] = broad
        records[role] = {
            "source": {"path": rel(source), "sha256": sha256(source), "source_units": "mm"},
            "local_surface": {"path": rel(output), "sha256": sha256(output), "units": "m", "bounds_gripper_link_m": indexed.bounds},
            "broadphase_box": {"path": rel(broad_output), "sha256": sha256(broad_output), "units": "m"},
            "frame": "gripper_link",
        }
    # The R1 receipt calls the meshes LINK6_LOCAL.  Prove the numerical frame
    # independently against the accepted q=0 URDF assembly: the R1 aggregate
    # matches gripper_link, whereas a direct link6 binding misses by the fixed
    # gripper_joint offset/rotation.  This prevents a visually plausible but
    # mechanically wrong 125 mm placement error.
    q_zero = np.zeros(6)
    fk_zero = arm.fk(q_zero, T_base=base_m)["T"]
    t_s_link6_m = np.asarray(fk_zero["link6"], dtype=float)
    t_link6_gripper_m = np.asarray(arm.joints_all["gripper_joint"]["T_origin"], dtype=float)
    t_s_gripper_m = t_s_link6_m @ t_link6_gripper_m
    legacy_deployed = trimesh.load_mesh(DEPLOYED_PARTS / "B51_REF_gripper_detail_LINKLOCAL.stl", process=False)
    legacy_in_gripper_mm = trimesh.transform_points(legacy_deployed.vertices, np.linalg.inv(transform_mm(t_s_gripper_m)))
    legacy_in_link6_mm = trimesh.transform_points(legacy_deployed.vertices, np.linalg.inv(transform_mm(t_s_link6_m)))
    r1_bounds_mm = np.vstack([np.vstack(r1_vertices_mm).min(axis=0), np.vstack(r1_vertices_mm).max(axis=0)])
    legacy_gripper_bounds_mm = np.vstack([legacy_in_gripper_mm.min(axis=0), legacy_in_gripper_mm.max(axis=0)])
    legacy_link6_bounds_mm = np.vstack([legacy_in_link6_mm.min(axis=0), legacy_in_link6_mm.max(axis=0)])
    gripper_binding_error_mm = float(np.max(np.abs(legacy_gripper_bounds_mm - r1_bounds_mm)))
    link6_binding_error_mm = float(np.max(np.abs(legacy_link6_bounds_mm - r1_bounds_mm)))

    records["motion_contract"] = {
        "neutral_source_semantics": "CLOSED_TRAVEL_ZERO",
        "source_receipt_frame_label": "LINK6_LOCAL",
        "corrected_frame_binding": "gripper_link",
        "correction_basis": "Absolute q0 bbox registration to accepted URDF gripper_link; direct link6 binding is displaced by the fixed 0.15971 m and Ry(-1.5708) transform.",
        "T_link6_gripper_source": "accepted URDF gripper_joint fixed origin",
        "frame_registration": {
            "method": "q0 absolute assembly bbox registration of legacy B51 gripper against aggregate R1 sources",
            "units": "mm",
            "R1_aggregate_bounds_in_candidate_local_frame_mm": r1_bounds_mm,
            "legacy_bounds_after_inverse_gripper_link_transform_mm": legacy_gripper_bounds_mm,
            "legacy_bounds_after_inverse_link6_transform_mm": legacy_link6_bounds_mm,
            "gripper_link_bbox_endpoint_max_abs_error_mm": gripper_binding_error_mm,
            "direct_link6_bbox_endpoint_max_abs_error_mm": link6_binding_error_mm,
            "gripper_link_acceptance_mm": 0.001,
            "gripper_link_registration_pass": gripper_binding_error_mm <= 0.001,
            "direct_link6_binding_rejected": link6_binding_error_mm > 100.0,
            "accepted_binding": "gripper_link",
            "source_label_conflict_status": "HOLD_SOURCE_LABEL_IS_NOT_NUMERICAL_FRAME_AUTHORITY",
        },
        "axis_in_gripper_link": [0.0, 1.0, 0.0],
        "left_translation_m": [0.0, -0.0715],
        "right_translation_m": [0.0, 0.0715],
        "named_travel_m": {"CLOSED": 0.0, "PARTIAL": 0.03575, "PREGRASP": 0.055, "OPEN": 0.0715},
        "configuration_travel_authority": None,
        "conflicting_non_authoritative_travel_witnesses_m": {
            "R1_geometry_witness": {
                "values_m": [0.0, 0.03575, 0.055, 0.0715],
                "source": {"path": rel(GRIPPER_VALIDATION), "sha256": sha256(GRIPPER_VALIDATION)},
            },
            "alternate_equal_increment_witness": {
                "values_m": [0.0, 0.023833, 0.047667, 0.0715],
                "source": {"path": rel(ALT_GRIPPER_CONFIG), "sha256": sha256(ALT_GRIPPER_CONFIG)},
                "source_status": "SEMANTIC_ONLY_NATIVE_TOP_ASSEMBLY_HOLD",
            },
        },
        "travel_conflict_disposition": "HOLD_UNTIL_CONFIGURATION_TO_TRAVEL_MAP_IS_RATIFIED",
        "manufacturing_additional_clearance_m": None,
        "manufacturing_clearance_status": "PROVISIONAL_CLEARANCE_HOLD",
        "contact_and_strength_status": "HOLD",
        "source_validation": {"path": rel(GRIPPER_VALIDATION), "sha256": sha256(GRIPPER_VALIDATION)},
    }
    return records, boxes


def rx(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def solar_panels(state_name: str, oracle_doc: dict[str, Any]) -> list[tuple[str, trimesh.Trimesh]]:
    """Return the hash-bound R2B oracle panel bounding geometry.

    The oracle records the candidate B-rep solid bounding boxes for all seven
    endpoint states.  Using those boxes avoids silently replacing the relieved
    panel edges with a full-pitch plate.
    """
    state = next(item for item in oracle_doc["states"] if item["state"] == state_name)
    output: list[tuple[str, trimesh.Trimesh]] = []
    for side in ("left", "right"):
        for panel in state[side]["panels"]:
            raw_bounds = panel["solid_bbox_mm"]
            if isinstance(raw_bounds, str):
                raw_bounds = raw_bounds.split()
            values = np.asarray([float(value) for value in raw_bounds], dtype=float) / 1000.0
            bounds = np.vstack([values[:3], values[3:]])
            output.append((f"solar_{panel['panel'].lower()}", box_from_bounds(bounds)))
    return output


def moved_box(local_box: trimesh.Trimesh, transform: np.ndarray) -> trimesh.Trimesh:
    result = local_box.copy()
    result.apply_transform(transform)
    return result


def bounds_union(meshes: list[trimesh.Trimesh]) -> list[list[float]] | None:
    if not meshes:
        return None
    return np.vstack([np.min([mesh.bounds[0] for mesh in meshes], axis=0), np.max([mesh.bounds[1] for mesh in meshes], axis=0)]).tolist()


def aabb_overlap(a: trimesh.Trimesh, b: trimesh.Trimesh, tolerance: float = 1.0e-12) -> bool:
    return bool(np.all(a.bounds[1] >= b.bounds[0] - tolerance) and np.all(b.bounds[1] >= a.bounds[0] - tolerance))


def apply_color(mesh: trimesh.Trimesh, color: list[int]) -> None:
    mesh.visual.face_colors = np.tile(np.asarray(color, dtype=np.uint8), (len(mesh.faces), 1))


def build_configuration_snapshots(
    arm: Any,
    base_m: np.ndarray,
    pose_doc: dict[str, Any],
    arm_boxes: dict[str, trimesh.Trimesh],
    gripper_boxes: dict[str, trimesh.Trimesh],
    solar_doc: dict[str, Any],
    solar_oracle: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scene_candidate = load_scene_candidate()
    q_home = pose_doc["poses"]["Q_DEPLOYED_HOME"]["q_rad"]
    q_stow = pose_doc["poses"]["Q_STOW_ENGINEERING_CANDIDATE"]["q_rad"]
    q_ready = pose_doc["poses"]["Q_SERVICE_READY"]["q_rad"]
    configs = [
        {"id": "C01", "name": "DEPLOYED_NOMINAL", "q": q_home, "q_source": "Q_DEPLOYED_HOME", "solar": "SOLAR_DEPLOYED_NOMINAL", "target": None},
        {"id": "C02", "name": "LEFT_PANEL_FAIL", "q": q_home, "q_source": "Q_DEPLOYED_HOME_DISPLAY_ONLY_FOR_FAILURE_BRANCH", "solar": "SOLAR_LEFT_FAIL", "target": None},
        {"id": "C03", "name": "RIGHT_PANEL_FAIL", "q": q_home, "q_source": "Q_DEPLOYED_HOME_DISPLAY_ONLY_FOR_FAILURE_BRANCH", "solar": "SOLAR_RIGHT_FAIL", "target": None},
        {"id": "C04", "name": "BOTH_PANEL_FAIL", "q": q_home, "q_source": "Q_DEPLOYED_HOME_DISPLAY_ONLY_FOR_FAILURE_BRANCH", "solar": "SOLAR_BOTH_FAIL", "target": None},
        {"id": "C05", "name": "ARM_STOWED_ONORBIT", "q": q_stow, "q_source": "Q_STOW_ENGINEERING_CANDIDATE", "solar": None, "target": None},
        {"id": "C06", "name": "ARM_TASK_READY", "q": q_ready, "q_source": "Q_SERVICE_READY_RATIFICATION_HOLD", "solar": "SOLAR_DEPLOYED_NOMINAL", "target": None},
        {"id": "C07", "name": "PREGRASP", "q": scene_candidate["q_rad"], "q_source": "E15_P1_DISPLAY_CANDIDATE", "solar": "SOLAR_DEPLOYED_NOMINAL", "target": "debris"},
        {"id": "C08", "name": "CAPTURE", "q": scene_candidate["q_rad"], "q_source": "E15_DISPLAY_ONLY_REJECTED_AS_22KG_VALIDATION", "solar": "SOLAR_DEPLOYED_NOMINAL", "target": "satellite"},
        {"id": "C09", "name": "POST_CAPTURE", "q": scene_candidate["q_rad"], "q_source": "E15_0_OF_72_ADMISSIBLE_DISPLAY_CANDIDATE", "solar": "SOLAR_DEPLOYED_NOMINAL", "target": "debris"},
    ]
    target_paths = {
        "satellite": TARGET_SATELLITE,
        "debris": TARGET_DEBRIS,
    }
    target_meshes = {name: merge_surface(trimesh.load_mesh(path, process=False)) for name, path in target_paths.items()}
    target_transforms = {
        "satellite": np.array([[-1.0, 0.0, 0.0, 1.24], [0.0, -1.0, 0.0, 0.0], [0.0, 0.0, 1.0, -0.1], [0.0, 0.0, 0.0, 1.0]]),
        "debris": np.array([[-1.0, 0.0, 0.0, 1.61], [0.0, -1.0, 0.0, 0.0], [0.0, 0.0, 1.0, -1.05], [0.0, 0.0, 0.0, 1.0]]),
    }
    bus = trimesh.creation.box(extents=[0.366, 0.2203, 0.2203])
    m3r_transform = base_m.copy()
    m3r_transform[:3, 3] += np.array([0.0, 0.000015994151, -0.00008636607])
    m3r_meshes = []
    for path in (M3R_A, M3R_B):
        source = trimesh.load_mesh(path, process=False)
        source.vertices = source.vertices / 1000.0
        source.apply_transform(m3r_transform)
        m3r_meshes.append(source)

    records: list[dict[str, Any]] = []
    collision_records: dict[str, Any] = {}
    for config in configs:
        q = np.asarray(config["q"], dtype=float)
        fk = arm.fk(q, T_base=base_m)
        components: list[tuple[str, trimesh.Trimesh, list[int]]] = [("bus_core_diagnostic", bus.copy(), [100, 120, 150, 180])]
        for index, mesh in enumerate(m3r_meshes):
            components.append((f"m3r_stage_{'a' if index == 0 else 'b'}_candidate", mesh.copy(), [210, 140, 40, 210]))
        arm_global: dict[str, trimesh.Trimesh] = {}
        for link in ["base_link", "link1", "link2", "link3", "link4", "link5", "link6"]:
            transformed = moved_box(arm_boxes[link], fk["T"][link])
            arm_global[link] = transformed
            components.append((link, transformed, [60, 150, 220, 220]))

        display_gripper_travel_m = 0.055 if config["id"] in {"C07", "C08", "C09"} else None
        t_gripper = fk["T"]["link6"] @ arm.joints_all["gripper_joint"]["T_origin"]
        palm = moved_box(gripper_boxes["palm"], t_gripper)
        components.append(("gripper_r1_palm", palm, [240, 170, 40, 230]))
        if display_gripper_travel_m is not None:
            for side, sign in (("left_finger", -1.0), ("right_finger", 1.0)):
                translate = np.eye(4)
                translate[1, 3] = sign * display_gripper_travel_m
                transformed = moved_box(gripper_boxes[side], t_gripper @ translate)
                components.append((f"gripper_r1_{side}", transformed, [245, 205, 70, 230]))

        if config["solar"] is not None:
            for name, panel in solar_panels(config["solar"], solar_oracle):
                components.append((name, panel, [40, 100, 200, 170]))

        target_mesh = None
        if config["target"] is not None:
            target_mesh = target_meshes[config["target"]].copy()
            target_mesh.apply_transform(target_transforms[config["target"]])
            components.append((f"target_{config['target']}_display", target_mesh, [210, 70, 80, 150]))

        # AABB-on-link broad-phase.  Clear is conservative; overlap is only
        # ambiguous because every active arm geometry is an enclosing box.
        nonadjacent_pairs = []
        order = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6"]
        for i, left in enumerate(order):
            for j in range(i + 2, len(order)):
                right = order[j]
                possible = aabb_overlap(arm_global[left], arm_global[right])
                nonadjacent_pairs.append({"a": left, "b": right, "result": "POSSIBLE_OR_TOUCHING_HOLD" if possible else "CONSERVATIVE_CLEAR"})
        possible_count = sum(row["result"] != "CONSERVATIVE_CLEAR" for row in nonadjacent_pairs)
        target_possible = None
        if target_mesh is not None:
            target_possible = any(aabb_overlap(target_mesh, mesh) for mesh in arm_global.values()) or aabb_overlap(target_mesh, palm)

        scene = trimesh.Scene()
        for name, mesh, color in components:
            apply_color(mesh, color)
            scene.add_geometry(mesh, node_name=name, geom_name=name)
        snapshot_path = SNAPSHOT_DIR / f"{config['id']}_{config['name']}_DIAGNOSTIC.glb"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(scene.export(file_type="glb"))

        all_meshes = [mesh for _, mesh, _ in components]
        record = {
            "configuration_id": config["id"],
            "name": config["name"],
            "diagnostic_only": True,
            "contact_enabled": False,
            "mass_properties_authority": False,
            "q_rad": q,
            "q_source": config["q_source"],
            "joint_limits_valid": bool(all(arm.joints_all[name]["lower"] <= q[index] <= arm.joints_all[name]["upper"] for index, name in enumerate(["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]))),
            "solar_geometry_variant": "V5_R2B_3PANEL_CANDIDATE" if config["solar"] is not None else None,
            "solar_state": config["solar"],
            "solar_frame_reconciliation_to_M4": "HOLD_REQUIRES_ECR" if config["solar"] is not None else "NOT_SELECTED",
            "target_geometry": config["target"],
            "target_transform_S_rows": target_transforms[config["target"]] if config["target"] else None,
            "target_transform_authority": "DISPLAY_ONLY_NOT_WRITTEN_BACK_TO_M4" if config["target"] else None,
            "display_gripper_travel_m": display_gripper_travel_m,
            "display_gripper_travel_source": "R1_GEOMETRY_WITNESS_PREGRASP_NOT_CXX_AUTHORITY" if display_gripper_travel_m is not None else None,
            "finger_travel_configuration_authority": False,
            "required_capture_gripper_travel_m": None,
            "bbox_S_m": bounds_union(all_meshes),
            "snapshot": {"path": rel(snapshot_path), "sha256": sha256(snapshot_path)},
            "broadphase": {
                "method": "LINK_LOCAL_CONSERVATIVE_AABB_TRANSFORMED_BY_ACCEPTED_URDF_FK",
                "nonadjacent_pair_count": len(nonadjacent_pairs),
                "conservative_clear_count": len(nonadjacent_pairs) - possible_count,
                "possible_or_touching_hold_count": possible_count,
                "target_possible_overlap": target_possible,
                "verified_system_collision_clear": False,
                "claim_limit": "CLEAR_RESULTS_ARE_CONSERVATIVE_FOR_BOXED_COMPONENTS; OVERLAPS_ARE_AMBIGUOUS; NO_NARROW_PHASE_OR_SYSTEM_RELEASE",
            },
            "released_mass_kg": None,
            "released_cg_S_m": None,
            "released_inertia_S_kg_m2": None,
            "status": "DIAGNOSTIC_GEOMETRY_SNAPSHOT_HOLD_FOR_SYSTEM_COLLISION_MASS_AND_CONTACT",
        }
        records.append(record)
        collision_records[config["id"]] = {"pairs": nonadjacent_pairs, "target_possible_overlap": target_possible}
    return records, collision_records


def frozen_inputs(extra_paths: list[Path]) -> dict[str, Any]:
    paths = [
        URDF, POSES, SCENE, TARGET_MODELS, ENV_DEPLOYED, ENV_STOWED, ENV_EXPORTER, GRIPPER_VALIDATION,
        SOLAR_AUTHORITY, SOLAR_ORACLE, M3R_A, M3R_B, ALT_GRIPPER_CONFIG,
        MODEL, TARGET_SATELLITE, TARGET_DEBRIS,
        M4 / "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml",
        M4 / "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
        M4 / "07_structural_model/STRUCTURAL_ANALYSIS_ENTRY_GATE.json",
        M4 / "12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json",
        Q1 / "LOAD_CASE_MATRIX.csv", Q1 / "LOAD_COMBINATION_MATRIX.csv",
        Q1 / "LOAD_SOURCE_GAP_REGISTER.csv", Q1 / "BOUNDARY_CONDITION_AUTHORITY.json",
    ] + extra_paths
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append(path)
            seen.add(resolved)
    missing = [str(path) for path in unique if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    return {
        "schema": "M5_FROZEN_INPUT_MANIFEST_V1",
        "generated_local": now_local(),
        "record_count": len(unique),
        "records": [{"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in unique],
        "status": "PASS_ALL_INPUTS_PRESENT_AND_HASH_BOUND",
    }


def migrate_load_authority() -> dict[str, Any]:
    load_rows = list(csv.DictReader((Q1 / "LOAD_CASE_MATRIX.csv").open(encoding="utf-8")))
    migrated: list[dict[str, Any]] = []
    for row in load_rows:
        disposition = "RETAINED_HOLD_NO_NEW_PHYSICAL_AUTHORITY"
        m5_status = row["status"]
        note = "Source case retained with original claim limit."
        if row["case_id"] == "LC-010":
            disposition = "REJECTED_AS_NUMERICAL_LOAD_INPUT"
            m5_status = "REJECTED_JOINT2_PLUS_60_DEG_VIOLATES_ACCEPTED_UPPER_LIMIT_ZERO"
            note = "A coordinate-sign reconciliation or a new controlled trajectory is required."
        elif row["case_id"] in {"LC-013", "LC-014"}:
            disposition = "SUPERSEDED_FOR_REPRODUCIBILITY_BY_SIM15_DIAGNOSTIC_ENVELOPE"
            m5_status = "DIAGNOSTIC_IMPULSE_ONLY_CONTACT_FORCE_HOLD"
            note = "The M5/Sim15 rerun binds current fixture, target properties, solver, and output hashes."
        elif row["case_id"] == "LC-021":
            disposition = "ADMITTED_TO_M5_ANALYTIC_JOINT_SENSITIVITY_ONLY"
            m5_status = "AUTHORIZED_ANALYTIC_GEOMETRY_CHARACTERIZATION_NO_FEA"
            note = "No strength, preload, slip, separation, or margin conclusion is created."
        migrated.append({
            "case_id": row["case_id"], "load_family": row["load_family"],
            "source_status": row["status"], "m5_disposition": disposition,
            "m5_status": m5_status, "coordinate_frame": row["coordinate_frame"],
            "claim_limit": row["claim_limit"], "note": note,
        })
    write_csv(
        M5 / "03_load_authority/M5_LOAD_CASE_MIGRATION_REGISTER_V1.csv",
        ["case_id", "load_family", "source_status", "m5_disposition", "m5_status", "coordinate_frame", "claim_limit", "note"],
        migrated,
    )
    combos = list(csv.DictReader((Q1 / "LOAD_COMBINATION_MATRIX.csv").open(encoding="utf-8")))
    gaps = list(csv.DictReader((Q1 / "LOAD_SOURCE_GAP_REGISTER.csv").open(encoding="utf-8")))
    boundary = json.loads((Q1 / "BOUNDARY_CONDITION_AUTHORITY.json").read_text(encoding="utf-8"))
    old_m3r = next(item for item in boundary["boundaries"] if item["boundary_id"] == "BC-M3R-001")
    payload = {
        "schema": "M5_LOAD_AUTHORITY_MIGRATION_V1",
        "generated_local": now_local(),
        "source_counts": {"load_cases": len(load_rows), "combinations": len(combos), "gaps": len(gaps)},
        "old_boundary_ruling": {
            "boundary_id": old_m3r["boundary_id"],
            "parent_frame": old_m3r["parent_frame"],
            "disposition": "REJECTED_FOR_PHYSICAL_LOAD_APPLICATION",
            "reason": "M_FRAME at x=185.25 mm is a nonphysical dynamics origin and is not the spacecraft load-bridge mating datum.",
        },
        "replacement_boundary_contract": {
            "interface": "SPACECRAFT_LOAD_BRIDGE_MATING_DATUM_TO_M3R_TO_B601",
            "T_M_DYNAMICS_FROM_SPACECRAFT_LOAD_BRIDGE_MATING_DATUM": None,
            "stiffness_6x6": None,
            "fastener_preload_N": None,
            "friction_coefficient": None,
            "status": "HOLD_LOAD_BRIDGE_GEOMETRY_TRANSFORM_STIFFNESS_AND_JOINT_AUTHORITY",
            "formal_fea_use": "PROHIBITED",
        },
        "invalid_trajectory_ruling": {
            "source_case": "LC-010",
            "source_joint2_command_deg": 60.0,
            "accepted_joint2_limits_deg": [-179.908748, 0.0],
            "disposition": "REJECTED_AS_LOAD_INPUT",
        },
        "gap_closure": {
            "LG-019_capture_impulse_reproducibility": "PENDING_SIM15_HASH_BOUND_RERUN",
            "remaining_open_gap_count": len(gaps),
            "physical_load_authority_gap_count": len(gaps),
        },
        "formal_loads_authorized": False,
        "status": "PASS_MIGRATION_AND_REJECTION_LOGIC_WITH_PHYSICAL_LOAD_AUTHORITY_HOLD",
    }
    write_yaml(M5 / "03_load_authority/M5_LOAD_AUTHORITY_MIGRATION_V1.yaml", payload)
    return payload


def joint_patterns() -> dict[str, Any]:
    patterns = {
        "B601_TO_STAGE_A_4XM4_64MM": [[-0.032, -0.032], [-0.032, 0.032], [0.032, -0.032], [0.032, 0.032]],
        "STAGE_A_TO_B_8XM5_R62P5MM": [[0.0625 * math.cos(2.0 * math.pi * i / 8.0), 0.0625 * math.sin(2.0 * math.pi * i / 8.0)] for i in range(8)],
        "STAGE_B_TO_SPACECRAFT_4XM6_140MM": [[-0.07, -0.07], [-0.07, 0.07], [0.07, -0.07], [0.07, 0.07]],
    }
    records = {}
    matrix_rows = []
    for name, points in patterns.items():
        yz = np.asarray(points, dtype=float)
        sy2 = float(np.sum(yz[:, 0] ** 2))
        sz2 = float(np.sum(yz[:, 1] ** 2))
        sr2 = sy2 + sz2
        influence = []
        for index, (y, z) in enumerate(yz, start=1):
            # [N, qy, qz] = A_i [Fx,Fy,Fz,Mx,My,Mz]
            matrix = np.array([
                [1.0 / len(yz), 0.0, 0.0, 0.0, z / sz2, -y / sy2],
                [0.0, 1.0 / len(yz), 0.0, -z / sr2, 0.0, 0.0],
                [0.0, 0.0, 1.0 / len(yz), y / sr2, 0.0, 0.0],
            ])
            influence.append(matrix.tolist())
            for response, row in zip(("N_axial", "Qy", "Qz"), matrix):
                matrix_rows.append({
                    "pattern": name, "fastener_index": index, "y_m": y, "z_m": z,
                    "response": response, "Fx": row[0], "Fy": row[1], "Fz": row[2],
                    "Mx_per_m": row[3], "My_per_m": row[4], "Mz_per_m": row[5],
                })
        records[name] = {
            "coordinates_yz_m": yz,
            "fastener_count": len(yz),
            "sum_y2_m2": sy2,
            "sum_z2_m2": sz2,
            "sum_r2_m2": sr2,
            "influence_matrices": influence,
            "direct_force_fraction": 1.0 / len(yz),
            "maximum_bending_axial_coefficient_per_m": max(float(np.max(np.abs(yz[:, 0] / sy2))), float(np.max(np.abs(yz[:, 1] / sz2)))),
            "torsion_shear_magnitude_coefficient_per_m": float(np.max(np.linalg.norm(yz, axis=1) / sr2)),
        }
    write_csv(
        M5 / "04_joint_load_model/M5_FASTENER_GROUP_INFLUENCE_MATRIX_V1.csv",
        ["pattern", "fastener_index", "y_m", "z_m", "response", "Fx", "Fy", "Fz", "Mx_per_m", "My_per_m", "Mz_per_m"],
        matrix_rows,
    )
    payload = {
        "schema": "M5_ANALYTIC_JOINT_LOAD_MODEL_V1",
        "units": {"force": "N", "moment": "N*m", "coordinate": "m", "influence_moment_terms": "1/m"},
        "coordinate_contract": "x is interface normal; y,z lie in the joint plane; wrench=[Fx,Fy,Fz,Mx,My,Mz]",
        "measurement_model": {
            "axial": "N_i=Fx/n + My*z_i/sum(z^2) - Mz*y_i/sum(y^2)",
            "in_plane": "[Qy_i,Qz_i]=[Fy,Fz]/n + Mx*[-z_i,y_i]/sum(r^2)",
        },
        "assumptions": ["rigid plates", "equal fastener stiffness", "no clearance", "no slip", "no preload effect", "small deformation"],
        "patterns": records,
        "uncertainty": {
            "estimate": "nominal pattern coordinates_yz_m above",
            "coordinate_standard_uncertainty_m": None,
            "distribution": None,
            "degrees_of_freedom": None,
            "source": "digital nominal geometry only",
            "correlation_group": None,
            "status": "HOLD_NO_METROLOGY_INPUT",
        },
        "allowed_use": "GEOMETRIC_WRENCH_DISTRIBUTION_SENSITIVITY_AND_SOFTWARE_VERIFICATION",
        "prohibited_uses": ["FASTENER_STRENGTH", "PRELOAD_MARGIN", "SLIP_OR_SEPARATION", "PLATE_STRESS", "FLIGHT_MOS"],
        "status": "PASS_ANALYTIC_GEOMETRY_MODEL_WITH_STRENGTH_AND_JOINT_MECHANICS_HOLD",
    }
    write_yaml(M5 / "04_joint_load_model/M5_ANALYTIC_JOINT_LOAD_MODEL_V1.yaml", payload)
    return payload


def parameter(value: Any, unit: str, status: str, source: str | None = None) -> dict[str, Any]:
    return {
        "estimate": value,
        "unit": unit,
        "standard_uncertainty": None,
        "distribution": None,
        "degrees_of_freedom": None,
        "correlation_group": None,
        "source": source,
        "status": status,
    }


def contact_contract() -> dict[str, Any]:
    payload = {
        "schema": "M5_CONTACT_MODEL_PARAMETER_CONTRACT_V1",
        "units_policy": "SI_AT_API_BOUNDARY_AND_EXPLICIT_CONVERSION_FROM_SOURCE_MM",
        "zero_fill_forbidden": True,
        "normal_contact": {
            "model_family": None,
            "normal_stiffness_N_per_m": parameter(None, "N/m", "HOLD_TEST_IDENTIFICATION_REQUIRED"),
            "normal_damping_N_s_per_m": parameter(None, "N*s/m", "HOLD_TEST_IDENTIFICATION_REQUIRED"),
            "exponent": parameter(None, "1", "HOLD_MODEL_SELECTION_REQUIRED"),
            "coefficient_of_restitution": parameter(None, "1", "HOLD_TEST_IDENTIFICATION_REQUIRED"),
            "regularization_velocity_mps": parameter(None, "m/s", "HOLD_NUMERICAL_VV_REQUIRED"),
        },
        "tangential_contact": {
            "static_friction": parameter(None, "1", "HOLD_MATERIAL_PAIR_AND_TEST_REQUIRED"),
            "kinetic_friction": parameter(None, "1", "HOLD_MATERIAL_PAIR_AND_TEST_REQUIRED"),
            "tangential_stiffness_N_per_m": parameter(None, "N/m", "HOLD_TEST_IDENTIFICATION_REQUIRED"),
            "tangential_damping_N_s_per_m": parameter(None, "N*s/m", "HOLD_TEST_IDENTIFICATION_REQUIRED"),
            "stick_slip_transition_velocity_mps": parameter(None, "m/s", "HOLD_TEST_IDENTIFICATION_REQUIRED"),
        },
        "gripper_actuator": {
            "stroke_m": parameter(0.0715, "m", "DIGITAL_GEOMETRY_VALUE_UNCERTAINTY_HOLD", rel(GRIPPER_VALIDATION)),
            "first_contact_closing_velocity_mps": parameter(None, "m/s", "HOLD_ACTUATOR_CONTROL_AUTHORITY"),
            "continuous_force_N": parameter(None, "N", "HOLD_HARDWARE_AUTHORITY"),
            "peak_force_N": parameter(None, "N", "HOLD_HARDWARE_AUTHORITY"),
            "power_off_holding_force_N": parameter(None, "N", "HOLD_HARDWARE_AUTHORITY"),
            "control_latency_s": parameter(None, "s", "HOLD_HARDWARE_AND_SOFTWARE_MEASUREMENT"),
        },
        "contact_geometry": {
            "left_contact_frame_T_gripper_link": None,
            "right_contact_frame_T_gripper_link": None,
            "target_surface_normal": None,
            "effective_area_m2": parameter(None, "m^2", "HOLD_CONTACT_PATCH_DEFINITION"),
            "initial_gap_m": parameter(None, "m", "HOLD_CAPTURE_CONFIGURATION_AND_TOLERANCE"),
        },
        "structural_mapping": {
            "T_wrist_from_contact": None,
            "T_arm_base_from_wrist": "AVAILABLE_AS_FUNCTION_OF_Q_FROM_ACCEPTED_URDF",
            "T_m3r_from_arm_base": "DIGITAL_GEOMETRY_ONLY",
            "T_load_bridge_from_m3r": None,
            "status": "HOLD_COMPLETE_6D_PHYSICAL_LOAD_PATH",
        },
        "computed_contact_force_N": None,
        "computed_contact_pressure_Pa": None,
        "physical_contact_kernel_authorized": False,
        "status": "HOLD_ALL_PHYSICAL_CONTACT_PARAMETERS_AND_FRAMES_INCOMPLETE",
    }
    write_yaml(M5 / "05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml", payload)
    plan = {
        "schema": "M5_CONTACT_IDENTIFICATION_TEST_PLAN_V1",
        "status": "PLAN_READY_EXECUTION_AND_ACCEPTANCE_CRITERIA_HOLD",
        "metrology_rule": "Every fitted input requires estimate, standard uncertainty, distribution, degrees of freedom, calibration source, and correlation group.",
        "tests": [
            {"id": "CT-01", "purpose": "identify normal force-displacement and rate dependence", "specimen": "R1 contact insert plus representative target coupon", "raw_channels": ["force_N", "displacement_m", "velocity_mps", "time_s", "temperature_K"], "outputs": ["model_family", "normal_stiffness", "exponent", "normal_damping"], "status": "HOLD_SPECIMEN_MATERIAL_SURFACE_AND_RANGE"},
            {"id": "CT-02", "purpose": "identify restitution over approach-speed range", "specimen": "same material/surface pair", "raw_channels": ["pre_velocity_mps", "post_velocity_mps", "force_N", "time_s"], "outputs": ["coefficient_of_restitution", "contact_duration_s"], "status": "HOLD_TEST_RANGE_AND_FIXTURE"},
            {"id": "CT-03", "purpose": "identify static and kinetic friction with vacuum/thermal conditioning", "raw_channels": ["normal_force_N", "tangential_force_N", "slip_velocity_mps", "temperature_K"], "outputs": ["mu_static", "mu_kinetic", "stick_slip_transition"], "status": "HOLD_MATERIAL_PAIR_ENVIRONMENT_AND_CYCLE_COUNT"},
            {"id": "CT-04", "purpose": "identify gripper force-speed-latency and power-off hold", "raw_channels": ["command", "position_m", "velocity_mps", "force_N", "current_A", "time_s"], "outputs": ["force_speed_curve", "continuous_force", "peak_force", "latency", "holding_force"], "status": "HOLD_ACTUATOR_SELECTION"},
            {"id": "CT-05", "purpose": "correlate integrated capture impulse, rebound, slip and pressure witness", "raw_channels": ["six_axis_wrench", "high_speed_pose", "finger_position", "pressure_witness", "time_s"], "outputs": ["impulse", "couple_impulse", "peak_force", "duration", "rebound", "slip", "pressure_footprint"], "status": "HOLD_CT01_TO_CT04_AND_TARGET_SURROGATE"},
        ],
        "analysis": {"gum_linearized": "REQUIRED", "monte_carlo": "REQUIRED_FOR_NONLINEAR_OR_GT20_PERCENT_RELATIVE_UNCERTAINTY", "correlations": "MUST_BE_PRESERVED", "acceptance_thresholds": None},
    }
    write_yaml(M5 / "05_contact_identification/CONTACT_IDENTIFICATION_TEST_PLAN_V1.yaml", plan)
    return payload


def main() -> int:
    for directory in [
        "00_authority", "01_geometry_authority", "02_configurations", "03_load_authority",
        "04_joint_load_model", "05_contact_identification", "06_structural_entry",
        "07_simulation_handoff", "08_validation", "12_release", "99_tools",
    ]:
        (M5 / directory).mkdir(parents=True, exist_ok=True)

    pose_doc = yaml.safe_load(POSES.read_text(encoding="utf-8"))
    solar_doc = json.loads(SOLAR_AUTHORITY.read_text(encoding="utf-8"))
    solar_oracle = json.loads(SOLAR_ORACLE.read_text(encoding="utf-8"))
    model = load_b601_model()
    arm = model.B601Arm(str(URDF))
    # Expose chain constants to the object for deterministic downstream use.
    arm.CHAIN_LINKS = model.CHAIN_LINKS
    base_m = np.asarray(pose_doc["mount"]["transform_mm_rows"], dtype=float)
    base_m[:3, 3] /= 1000.0

    geometry_rows, arm_boxes = create_true_local_assets(arm, base_m, pose_doc)
    gripper_records, gripper_boxes = create_gripper_assets(arm, base_m)
    frame_pass = all(
        item["independent_q0_to_stow_registration"]["pass"]
        for item in geometry_rows.values()
    )
    geometry_decision = {
        "schema": "M5_B601_CAD_MESH_FRAME_DECISION_V1",
        "generated_local": now_local(),
        "source_export_frame": json.loads(ENV_DEPLOYED.read_text(encoding="utf-8"))["frame"],
        "source_exporter": {"path": rel(ENV_EXPORTER), "sha256": sha256(ENV_EXPORTER)},
        "decision": "SOURCE_LINKLOCAL_NAMED_STLS_ARE_ASSEMBLY_COORDINATE_MESHES_AND_MUST_BE_INVERSE_Q0_LOCALIZED",
        "method": "inv(T_S_link(q0))*vertices_DEPLOYED then T_S_link(Q_STOW)*vertices_local compared independently with STOWED source",
        "registration_component_count": len(geometry_rows),
        "all_components_below_0p1mm": frame_pass,
        "numerical_acceptance_mm": 0.1,
        "source_tessellation_linear_deflection_mm": 0.5,
        "physical_clearance_or_metrology_claim": False,
        "components": geometry_rows,
        "active_gripper_r1": gripper_records,
        "status": "PASS_SOURCE_BOUND_LINK_LOCALIZATION_FOR_DIGITAL_GEOMETRY" if frame_pass else "HOLD_REGISTRATION_FAILURE",
    }
    write_json(M5 / "01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json", geometry_decision)

    config_records, collision_records = build_configuration_snapshots(
        arm, base_m, pose_doc, arm_boxes, gripper_boxes, solar_doc, solar_oracle
    )
    configuration_contract = {
        "schema": "M5_CONFIGURATION_GEOMETRY_CONTRACT_V1",
        "generated_local": now_local(),
        "configuration_count": len(config_records),
        "required_ids": [f"C{index:02d}" for index in range(1, 10)],
        "branch_rule": "All snapshots use the isolated V5_R2B_3PANEL_CANDIDATE where a solar state is shown; this candidate is not mixed with the M4 deployed-box proxy.",
        "records": config_records,
        "released_mass_count": 0,
        "released_cg_count": 0,
        "released_inertia_count": 0,
        "verified_system_collision_count": 0,
        "contact_enabled_count": 0,
        "status": "PASS_EXACT_NINE_DIAGNOSTIC_GEOMETRY_SNAPSHOTS_WITH_ALL_PHYSICAL_RELEASE_FIELDS_HOLD",
    }
    write_yaml(M5 / "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml", configuration_contract)
    write_json(M5 / "02_configurations/M5_BROADPHASE_COLLISION_AUDIT_V1.json", {
        "schema": "M5_BROADPHASE_COLLISION_AUDIT_V1",
        "method": "CONSERVATIVE_LINK_AABB_ONLY",
        "clear_semantics": "A clear separated pair is conservative for the enclosed component geometry.",
        "overlap_semantics": "AABB overlap is ambiguous and remains HOLD; it is not proof of physical penetration.",
        "narrow_phase_available": False,
        "configuration_results": collision_records,
        "system_collision_release": False,
        "status": "DIAGNOSTIC_BROADPHASE_COMPLETE_NARROW_PHASE_AND_SYSTEM_RELEASE_HOLD",
    })

    load_migration = migrate_load_authority()
    joint_model = joint_patterns()
    contact = contact_contract()

    structural_gate = {
        "schema": "M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1",
        "generated_local": now_local(),
        "gate_status": "HOLD",
        "pass_token": "STRUCTURAL_ANALYSIS_READY",
        "pass_token_issued": False,
        "formal_fea_authorized": False,
        "formal_fea_run_count": 0,
        "mandatory_subgates": {
            "controlled_structural_geometry": "HOLD_SPACECRAFT_LOAD_BRIDGE_AND_JOINT_DETAILS",
            "load_cases_and_factors": "HOLD_NO_FLIGHT_OR_PHYSICAL_CONTACT_LOAD_AUTHORITY",
            "boundary_conditions": "HOLD_REJECTED_M_FRAME_REPLACEMENT_TRANSFORM_NULL",
            "contact_and_fastener_definition": "HOLD_PHYSICAL_PARAMETERS_NULL",
            "material_allowables": "HOLD_PROCUREMENT_TEMPERATURE_AND_STATISTICAL_BASIS",
            "configuration_mass_properties": "HOLD_0_OF_9_RELEASED",
            "mesh_convergence_and_quality_plan": "PENDING_CONTROLLED_MODEL_SCOPE",
            "acceptance_criteria": "HOLD_PROJECT_TAILORING_AND_OWNER_APPROVAL",
        },
        "analytic_work_completed": ["B601 mesh frame localization", "diagnostic impulse input chain", "six-DOF fastener-group influence matrices"],
        "rule": "No formal FEA execution or margin credit until every mandatory subgate is PASS.",
    }
    write_json(M5 / "06_structural_entry/M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1.json", structural_gate)

    source_paths = []
    for item in geometry_rows.values():
        source_paths.extend([WORKSPACE / item["deployed_source"]["path"], WORKSPACE / item["stowed_source"]["path"]])
    for role in ("palm", "left_finger", "right_finger"):
        source_paths.append(WORKSPACE / gripper_records[role]["source"]["path"])
    input_manifest = frozen_inputs(source_paths)
    write_json(M5 / "00_authority/M5_FROZEN_INPUT_MANIFEST_V1.json", input_manifest)

    phase = {
        "schema": "M5_PHASE_AUTHORITY_AND_BOUNDARY_V1",
        "generated_local": now_local(),
        "phase": "M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE",
        "predecessor": rel(M4 / "12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json"),
        "authorized_scope": ["source-bound link geometry", "diagnostic configuration snapshots", "rigid plastic-capture impulse envelope", "analytic joint load sensitivities", "contact identification plan"],
        "explicitly_not_authorized": ["formal FEA", "contact force or pressure", "flight loads", "strength or margin", "manufacturing release", "RL policy training", "HIL or hardware execution"],
        "memory_execution": memory_snapshot(),
        "formal_fea_run_count": 0,
        "status": "ACTIVE_SCOPED_ENGINEERING_CLOSURE",
    }
    write_yaml(M5 / "00_authority/M5_PHASE_AUTHORITY_AND_BOUNDARY.yaml", phase)

    interface = {
        "schema": "MECH_DYNAMICS_INTERFACE_V3",
        "generated_local": now_local(),
        "scope": "M5_SOURCE_BOUND_GEOMETRY_AND_DIAGNOSTIC_IMPULSE_HANDOFF",
        "units": {"length": "m", "angle": "rad", "mass": "kg", "inertia": "kg*m^2", "force": "N", "moment": "N*m", "impulse": "N*s", "couple_impulse": "N*m*s"},
        "artifacts": {},
        "configuration_ids": [row["configuration_id"] for row in config_records],
        "geometry_capabilities": {"true_link_local_surfaces": True, "conservative_link_boxes": True, "diagnostic_snapshots": 9, "narrow_phase_verified": False, "contact_geometry_authorized": False},
        "loads_capabilities": {"hash_bound_diagnostic_impulse_solver": True, "six_dof_joint_distribution": True, "contact_force_time_history": False, "physical_load_authority": False},
        "runtime_gates": {"geometry_diagnostic": "PASS", "physical_contact": "HOLD", "structural_analysis": "HOLD", "physics_gated_RL": "HOLD"},
        "required_acknowledgement": "I_ACKNOWLEDGE_M5_VALUES_ARE_DIAGNOSTIC_NOT_PHYSICAL_CONTACT_OR_FLIGHT_AUTHORITY",
        "zero_fill_forbidden": True,
    }
    artifact_paths = {
        "accepted_b601_urdf": URDF,
        "frozen_input_manifest": M5 / "00_authority/M5_FROZEN_INPUT_MANIFEST_V1.json",
        "mesh_frame_decision": M5 / "01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json",
        "configuration_contract": M5 / "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml",
        "broadphase_audit": M5 / "02_configurations/M5_BROADPHASE_COLLISION_AUDIT_V1.json",
        "load_authority_migration": M5 / "03_load_authority/M5_LOAD_AUTHORITY_MIGRATION_V1.yaml",
        "joint_load_model": M5 / "04_joint_load_model/M5_ANALYTIC_JOINT_LOAD_MODEL_V1.yaml",
        "contact_parameter_contract": M5 / "05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml",
        "structural_entry_gate": M5 / "06_structural_entry/M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1.json",
        "sim14_fixture": WORKSPACE / "30_simulation/sim_14_m4_digital_prototype_grasping/config/SIM14_DIAGNOSTIC_FIXTURE_V1.json",
        "m4_mass_properties": M4 / "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml",
        "target_models": TARGET_MODELS,
        "solar_r2b_static_oracle": SOLAR_ORACLE,
    }
    interface["artifacts"] = {name: {"path": rel(path), "sha256": sha256(path), "required": True} for name, path in artifact_paths.items()}
    write_yaml(M5 / "07_simulation_handoff/MECH_DYNAMICS_INTERFACE_V3.yaml", interface)

    readme = """# M5 physical geometry and loads closure\n\nThis isolated package advances M4 into source-bound B601 link geometry, exact nine diagnostic geometry snapshots, a corrected load-authority migration, analytic six-DOF joint load distribution, and a metrology-ready contact identification contract.\n\nIt does **not** authorize formal FEA, physical contact force/pressure, strength or margin, flight/launch qualification, manufacturing, RL policy training, HIL, or hardware execution. Unknown physical values remain null/HOLD. The historical 6 GiB gate remains `memory_gate_passed: false`; the recorded Owner Override only authorizes the bounded lightweight route.\n\nThe decisive geometry result is that the source files named `*_LINKLOCAL.stl` are actually top-assembly-coordinate exports. M5 inverse-localizes them at q=0 and independently reconstructs the stowed source pose before exporting true link-local indexed PLY surfaces in metres.\n"""
    (M5 / "README.md").write_text(readme, encoding="utf-8")

    gate = {
        "schema": "M5_GEOMETRY_AND_LOADS_CLOSURE_GATE_V1",
        "generated_local": now_local(),
        "scope": "COMPETITION_PROTOTYPE_SOURCE_BOUND_GEOMETRY_AND_DIAGNOSTIC_LOADS",
        "memory_gate_passed": False,
        "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY",
        "owner_override_used": True,
        "b601_mesh_frame_localization_pass": frame_pass,
        "true_link_local_surface_count": 7,
        "gripper_r1_separated_surface_count": 3,
        "diagnostic_configuration_snapshot_count": len(config_records),
        "verified_system_collision_configuration_count": 0,
        "load_case_migration_count": load_migration["source_counts"]["load_cases"],
        "load_combination_count": load_migration["source_counts"]["combinations"],
        "load_gap_count": load_migration["source_counts"]["gaps"],
        "diagnostic_reproducibility_gap_closed_count": 0,
        "joint_pattern_count": len(joint_model["patterns"]),
        "physical_contact_parameters_ready": False,
        "structural_analysis_ready": False,
        "formal_fea_run_count": 0,
        "physics_gated_contact_rl_ready": False,
        "next_stage_authorized": True,
        "next_stage_scope": "SIM15_HASH_BOUND_DIAGNOSTIC_CAPTURE_IMPULSE_AND_JOINT_LOAD_SOFTWARE_ONLY",
        "prohibited_claims": ["MEMORY_GATE_PASS", "SYSTEM_COLLISION_PASS", "CONTACT_FORCE_PASS", "STRUCTURAL_ANALYSIS_READY", "FLIGHT_OR_MANUFACTURING_RELEASE", "RL_POLICY_READY"],
        "critical_evidence": {
            "mesh_frame_decision": {"path": rel(M5 / "01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json"), "sha256": sha256(M5 / "01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json")},
            "configuration_contract": {"path": rel(M5 / "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml"), "sha256": sha256(M5 / "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml")},
            "interface": {"path": rel(M5 / "07_simulation_handoff/MECH_DYNAMICS_INTERFACE_V3.yaml"), "sha256": sha256(M5 / "07_simulation_handoff/MECH_DYNAMICS_INTERFACE_V3.yaml")},
            "contact_contract": {"path": rel(M5 / "05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml"), "sha256": sha256(M5 / "05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml")},
            "structural_gate": {"path": rel(M5 / "06_structural_entry/M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1.json"), "sha256": sha256(M5 / "06_structural_entry/M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1.json")},
        },
        "status": "M5_SCOPED_GEOMETRY_AND_LOADS_CLOSURE_PASS_WITH_PHYSICAL_CONTACT_STRUCTURAL_AND_FLIGHT_HOLDS" if frame_pass and len(config_records) == 9 else "HOLD",
    }
    write_json(M5 / "12_release/M5_GEOMETRY_AND_LOADS_CLOSURE_GATE_V1.json", gate)

    # Output manifest intentionally excludes itself and the one independently
    # generated receipt.  Host/interpreter caches are forbidden in the release
    # tree rather than silently omitted, so closed-file coverage stays exact.
    manifest_path = M5 / "12_release/M5_OUTPUT_MANIFEST_V1.json"
    receipt_path = M5 / "08_validation/M5_VALIDATION_RECEIPT_V1.json"
    host_cache_files = sorted(
        path
        for path in M5.rglob("*")
        if path.is_file()
        and ("__pycache__" in path.relative_to(M5).parts or path.suffix.lower() == ".pyc")
    )
    if host_cache_files:
        raise RuntimeError(
            "host/interpreter caches must be removed before M5 release: "
            + ", ".join(path.relative_to(M5).as_posix() for path in host_cache_files)
        )
    files = sorted(
        path
        for path in M5.rglob("*")
        if path.is_file()
        and path != manifest_path
        and path != receipt_path
    )
    output_manifest = {
        "schema": "M5_OUTPUT_MANIFEST_V1",
        "generated_local": now_local(),
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "records": [{"path": path.relative_to(M5).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in files],
        "exclusion_policy": [
            "12_release/M5_OUTPUT_MANIFEST_V1.json",
            "08_validation/M5_VALIDATION_RECEIPT_V1.json",
        ],
        "host_or_interpreter_cache_files_present": False,
        "status": "PASS_OUTPUTS_HASH_BOUND",
    }
    write_json(manifest_path, output_manifest)

    print(json.dumps({
        "status": gate["status"],
        "mesh_frame_pass": frame_pass,
        "configuration_count": len(config_records),
        "output_file_count": output_manifest["file_count"],
        "output_total_bytes": output_manifest["total_bytes"],
        "memory_gate_passed": False,
        "owner_override_used": True,
        "formal_fea_run_count": 0,
    }, indent=2))
    return 0 if gate["status"].startswith("M5_SCOPED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
