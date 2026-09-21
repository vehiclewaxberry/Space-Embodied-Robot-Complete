"""M6 WP2 — nine-configuration diagnostic mass/CG/inertia aggregation.

Reads the M4 mass ledger (SYSTEM_MASS_PROPERTIES_V3.yaml), the M4 named-pose
revalidation, and this WP's candidate transform library
(CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml), then aggregates diagnostic
mass / CG / inertia / aggregation-scope bbox for C01..C09 under candidate
transform semantics.

Fail-closed rules enforced here:
  * strict SI units (kg, m, kg*m^2, rad);
  * tensor rotation into the spacecraft assembly frame (identity alias of S)
    plus the parallel-axis theorem, inertia taken about each configuration's
    own system CG;
  * per-quantity classification and source_ref carried through;
  * every uncertainty stays null/HOLD -- no zero filling, no invented values;
  * release_aggregation_active stays False everywhere; nothing is written
    back to any baseline;
  * the accepted URDF arm mass (L0) is used as-is and never overridden;
  * Branch B CG/inertia stay null/HOLD because the M3R component CG/inertia
    and the bus-core CG allocation are not ratified (legacy flange boundary
    ruling preserved by reference).

The script performs no FEA and creates no release, flight, manufacturing, or
qualification authority. Re-runnable: same inputs -> same diagnostic numbers.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

WORKSPACE = Path(__file__).resolve().parents[3]
M4 = WORKSPACE / "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1"
M5 = WORKSPACE / "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1"
WP2 = WORKSPACE / "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp2_mass_properties"

V3_PATH = M4 / "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml"
CONFIG_LIB_PATH = M4 / "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml"
FRAME_TREE_PATH = M4 / "01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml"
REVALIDATION_PATH = M4 / "11_validation/B601_NAMED_POSE_REVALIDATION_V1.json"
M5_CONTRACT_PATH = M5 / "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml"
SERVICE_SPACECRAFT_PATH = WORKSPACE / "20_engineering/config/geometry/service_spacecraft_v1.yaml"
FLEXIBLE_APPENDAGE_PATH = WORKSPACE / "20_engineering/config/geometry/flexible_appendage_v1.yaml"
GEOMETRY_FRAME_TREE_PATH = WORKSPACE / "20_engineering/config/geometry/frame_tree_v1.yaml"
STAGE1_BUDGET_PATH = WORKSPACE / "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv"
TARGET_MODELS_PATH = WORKSPACE / "20_engineering/config/geometry/target_models_v1.yaml"
URDF_PATH = WORKSPACE / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
TRANSFORM_CANDIDATES_PATH = WP2 / "CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml"
OUTPUT_PATH = WP2 / "SYSTEM_MASS_PROPERTIES_V4_DIAGNOSTIC.yaml"

# Bus primitive box (SSOT bays: 3 x [113.5, 226.3, 226.3] mm about the 12U
# geometric centre = S origin) plus the legacy 140 x 140 x 15 mm flange at
# x 170.25..185.25 mm (M4 ADR rev2 legacy-flange ruling, Branch A scope).
BUS_BAYS_MIN_M = np.array([-0.17025, -0.11315, -0.11315])
BUS_BAYS_MAX_M = np.array([0.17025, 0.11315, 0.11315])
LEGACY_FLANGE_MIN_M = np.array([0.17025, -0.07, -0.07])
LEGACY_FLANGE_MAX_M = np.array([0.18525, 0.07, 0.07])

# Panel plate half-extents about the panel COM in the local F frame
# (flexible_appendage_v1: chord 0.227 along X_F, span 0.200 along Y_F,
# thickness 0.006 along Z_F).
PANEL_HALF_M = np.array([0.1135, 0.1, 0.003])

BRANCH_A_ID = "M4-DIAG-LEGACY-A"
BRANCH_B_ID = "M4-DIAG-M3R-B"

BRANCH_B_CG_INERTIA_HOLD = (
    "HOLD_M3R_COMPONENT_COM_INERTIA_UNKNOWN_AND_BUS_CORE_COM_ALLOCATION_NOT_RATIFIED_"
    "LEGACY_FLANGE_BOUNDARY_RULING_PRESERVED"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def now_local() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def rows_to_transform(rows: list[list[float]]) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray(rows, dtype=float)
    assert matrix.shape == (4, 4), f"expected 4x4 transform rows, got {matrix.shape}"
    rotation = matrix[:3, :3]
    translation = matrix[:3, 3]
    assert np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0]), "last row must be [0 0 0 1]"
    det = float(np.linalg.det(rotation))
    assert abs(det - 1.0) < 1e-9, f"rotation determinant {det} != 1"
    assert np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-9), "rotation not orthonormal"
    return rotation, translation


def steiner(mass: float, offset: np.ndarray) -> np.ndarray:
    """Parallel-axis shift of an inertia tensor by `offset` from the component COM."""
    return mass * (float(offset @ offset) * np.eye(3) - np.outer(offset, offset))


def aggregate(members: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate mass, system CG, and inertia about the system CG (S frame, SI)."""
    total_mass = sum(member["mass_kg"] for member in members)
    weighted = sum(member["mass_kg"] * member["com_S_m"] for member in members)
    system_cg = weighted / total_mass
    inertia = np.zeros((3, 3))
    for member in members:
        rotated = member["rotation_S"] @ member["inertia_own_com"] @ member["rotation_S"].T
        inertia += rotated + steiner(member["mass_kg"], member["com_S_m"] - system_cg)
    inertia = 0.5 * (inertia + inertia.T)  # exact symmetry hygiene
    return {
        "mass_kg": float(total_mass),
        "cg_S_m": system_cg,
        "inertia_about_system_cg_S_kg_m2": inertia,
    }


def panel_bbox_corners(rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    signs = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
    return (rotation @ (signs * PANEL_HALF_M).T).T + translation


def main() -> None:
    v3 = load_yaml(V3_PATH)
    config_lib = load_yaml(CONFIG_LIB_PATH)
    revalidation = json.loads(REVALIDATION_PATH.read_text(encoding="utf-8"))
    m5_contract = load_yaml(M5_CONTRACT_PATH)
    candidates = load_yaml(TRANSFORM_CANDIDATES_PATH)
    stage1_rows = {}
    with open(STAGE1_BUDGET_PATH, encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        for line in handle:
            values = line.strip().split(",")
            stage1_rows[values[0]] = dict(zip(header, values))

    # --- component source data pulled programmatically from the M4 ledger ---
    records = v3["component_records"]
    bus = records["spacecraft_bus_no_panels"]
    panel_left = records["solar_array_left"]
    panel_right = records["solar_array_right"]
    arm_record = records["b601_complete_arm_including_gripper_urdf_links"]
    m3r_record = records["m3r_stage_a_plus_stage_b_budget_envelope"]
    target_22 = records["target_22kg_scenario"]
    target_150 = records["target_150kg_scenario"]
    bus_core = v3["diagnostic_derived_components"]["spacecraft_bus_core_no_panels_no_legacy_flange"]
    branches = v3["diagnostic_nonrelease_branches"]

    arm_mass = float(arm_record["mass"]["estimate_kg"])
    urdf_witness_mass_kg = 4.695555949342986
    assert abs(arm_mass - urdf_witness_mass_kg) < 1e-12, "L0 URDF arm mass mismatch"

    pose_props = {
        "Q_DEPLOYED_HOME": revalidation["pose_results"]["Q_DEPLOYED_HOME"],
        "Q_DEPLOYED_HOME_DISPLAY_ONLY_FOR_FAILURE_BRANCH": revalidation["pose_results"]["Q_DEPLOYED_HOME"],
        "Q_STOW_ENGINEERING_CANDIDATE": revalidation["pose_results"]["Q_STOW_ENGINEERING_CANDIDATE"],
        "Q_SERVICE_READY": revalidation["pose_results"]["Q_SERVICE_READY"],
        "PREGRASP_SCENE_CANDIDATE": revalidation["pregrasp_scene_candidate"],
    }

    panel_transforms = candidates["transform_library"]["panel_transforms"]
    target_poses = candidates["transform_library"]["target_capture_pose_candidates"]
    bindings = {item["configuration_id"]: item for item in candidates["configuration_bindings"]}
    m5_records = {item["configuration_id"]: item for item in m5_contract["records"]}
    lib_records = {item["configuration_id"]: item for item in config_lib["configurations"]}

    def bus_member() -> dict[str, Any]:
        return {
            "component_id": "spacecraft_bus_no_panels",
            "mass_kg": float(bus["mass"]["estimate_kg"]),
            "mass_classification": bus["mass"]["classification"],
            "com_S_m": np.asarray(bus["center_of_mass"]["estimate_xyz_m"], dtype=float),
            "rotation_S": np.eye(3),
            "inertia_own_com": np.asarray(bus["inertia_about_own_com"]["matrix_kg_m2"], dtype=float),
            "property_classification": bus["center_of_mass"]["classification"],
            "transform_classification": "NOT_REQUIRED_ALREADY_IN_S",
            "source_ref": "m4_system_mass_properties_v3",
        }

    def panel_member(side: str, transform_key: str) -> dict[str, Any]:
        record = panel_left if side == "left" else panel_right
        rotation, translation = rows_to_transform(panel_transforms[transform_key]["T_S_child_rows"])
        return {
            "component_id": f"solar_array_{side}",
            "mass_kg": float(record["mass"]["estimate_kg"]),
            "mass_classification": record["mass"]["classification"],
            "com_S_m": translation,
            "rotation_S": rotation,
            "inertia_own_com": np.asarray(record["inertia_about_own_com"]["matrix_kg_m2"], dtype=float),
            "property_classification": record["center_of_mass"]["classification"],
            "transform_classification": "CANDIDATE_TRANSFORM",
            "transform_ref": f"CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml#transform_library.panel_transforms.{transform_key}",
            "source_ref": "stage1_mass_budget",
        }

    pose_status_map = {
        "Q_DEPLOYED_HOME": "PASS_RUNTIME_FK_AND_INERTIA_NO_SOURCE_HOLD",
        "Q_DEPLOYED_HOME_DISPLAY_ONLY_FOR_FAILURE_BRANCH": "PASS_RUNTIME_FK_AND_INERTIA_NO_SOURCE_HOLD_DISPLAY_ONLY_BINDING",
        "Q_STOW_ENGINEERING_CANDIDATE": "HELD_CANDIDATE_FK_REGRESSION_FAIL_MAX_RESIDUAL_567P734_MM",
        "Q_SERVICE_READY": "PASS_RUNTIME_FK_AND_INERTIA_WITH_SOURCE_CONFIGURATION_RATIFICATION_HOLD",
        "PREGRASP_SCENE_CANDIDATE": "DIAGNOSTIC_CANDIDATE_HOLD_FOR_CAPTURE_DYNAMICS",
    }

    def arm_member(pose_ref: str) -> dict[str, Any]:
        props = pose_props[pose_ref]
        return {
            "component_id": "b601_complete_arm_including_gripper_urdf_links",
            "mass_kg": arm_mass,
            "mass_classification": arm_record["mass"]["classification"],
            "com_S_m": np.asarray(props["digital_arm_center_of_mass_S_m"], dtype=float),
            "rotation_S": np.eye(3),  # revalidation values are already expressed in S
            "inertia_own_com": np.asarray(props["digital_arm_inertia_about_arm_com_S_kg_m2"], dtype=float),
            "property_classification": "DIGITAL_MODEL_DERIVED",
            "transform_classification": "CANDIDATE_BINDING",
            "transform_ref": f"CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml#transform_library.arm_named_pose_bindings.{pose_ref}",
            "pose_status": pose_status_map[pose_ref],
            "source_ref": "b601_named_pose_revalidation",
        }

    def target_member(config_id: str) -> dict[str, Any] | None:
        binding = bindings[config_id]["target"]
        if binding is None or not binding["system_mass_member"]:
            return None
        pose = target_poses[binding["pose_ref"]]
        rotation, translation = rows_to_transform(pose["T_S_target_rows"])
        record = target_22 if config_id == "C08" else target_150
        com_local = np.asarray(record["center_of_mass"]["estimate_xyz_m"], dtype=float)
        return {
            "component_id": "target_22kg_scenario" if config_id == "C08" else "target_150kg_scenario",
            "mass_kg": float(record["mass"]["estimate_kg"]),
            "mass_classification": record["mass"]["classification"],
            "com_S_m": rotation @ com_local + translation,
            "rotation_S": rotation,
            "inertia_own_com": np.asarray(record["inertia_about_own_com"]["matrix_kg_m2"], dtype=float),
            "property_classification": record["center_of_mass"]["classification"],
            "transform_classification": "CANDIDATE_TRANSFORM",
            "transform_ref": f"CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml#transform_library.target_capture_pose_candidates.{binding['pose_ref']}",
            "source_ref": "stage1_mass_budget",
        }

    def aggregation_scope_bbox(members: list[dict[str, Any]]) -> dict[str, list[float]]:
        boxes = [np.vstack([BUS_BAYS_MIN_M, BUS_BAYS_MAX_M]),
                 np.vstack([LEGACY_FLANGE_MIN_M, LEGACY_FLANGE_MAX_M])]
        for member in members:
            if member["component_id"].startswith("solar_array_"):
                corners = panel_bbox_corners(member["rotation_S"], member["com_S_m"])
                boxes.append(np.vstack([corners.min(axis=0), corners.max(axis=0)]))
        stacked = np.stack(boxes)  # (n_boxes, 2, 3)
        mins = stacked[:, 0, :].min(axis=0)
        maxs = stacked[:, 1, :].max(axis=0)
        return {
            "min_xyz_m": [float(v) for v in mins],
            "max_xyz_m": [float(v) for v in maxs],
            "extent_xyz_m": [float(v) for v in (maxs - mins)],
        }

    configurations_out: list[dict[str, Any]] = []
    checks = {
        "m4_branch_mass_regression": [],
        "target_transform_matches_m5_contract": [],
        "inertia_symmetric_positive_definite_branch_A": [],
    }

    for config_id in [f"C{index:02d}" for index in range(1, 10)]:
        binding = bindings[config_id]
        lib = lib_records[config_id]
        m5_record = m5_records[config_id]

        members = [
            bus_member(),
            panel_member("left", binding["solar_panel_transforms"]["left"]["transform_ref"]),
            panel_member("right", binding["solar_panel_transforms"]["right"]["transform_ref"]),
            arm_member(binding["arm_named_pose_binding"]["pose_ref"]),
        ]
        target = target_member(config_id)
        if target is not None:
            members.append(target)

        branch_a = aggregate(members)

        # Branch B mass-only diagnostic: bus core + panels + arm + M3R (+ target).
        branch_b_mass = (
            float(bus_core["estimate_kg"])
            + float(panel_left["mass"]["estimate_kg"])
            + float(panel_right["mass"]["estimate_kg"])
            + arm_mass
            + float(m3r_record["mass"]["estimate_kg"])
            + (target["mass_kg"] if target is not None else 0.0)
        )

        # --- regression checks against the M4 ledger values ---
        expected_a = float(lib["mass"]["diagnostic_branches"]["legacy_A_value_kg"])
        expected_b = float(lib["mass"]["diagnostic_branches"]["m3r_B_value_kg"])
        checks["m4_branch_mass_regression"].append({
            "configuration_id": config_id,
            "branch_A_abs_err_kg": abs(branch_a["mass_kg"] - expected_a),
            "branch_B_abs_err_kg": abs(branch_b_mass - expected_b),
            "pass": abs(branch_a["mass_kg"] - expected_a) < 1e-12 and abs(branch_b_mass - expected_b) < 1e-12,
        })

        if binding["target"] is not None:
            m5_rows = np.asarray(m5_record["target_transform_S_rows"], dtype=float)
            cand_rows = np.asarray(target_poses[binding["target"]["pose_ref"]]["T_S_target_rows"], dtype=float)
            checks["target_transform_matches_m5_contract"].append({
                "configuration_id": config_id,
                "max_abs_err_m": float(np.max(np.abs(m5_rows - cand_rows))),
                "pass": bool(np.allclose(m5_rows, cand_rows, atol=1e-12)),
            })

        eigenvalues = np.linalg.eigvalsh(branch_a["inertia_about_system_cg_S_kg_m2"])
        symmetric = np.allclose(
            branch_a["inertia_about_system_cg_S_kg_m2"], branch_a["inertia_about_system_cg_S_kg_m2"].T, atol=1e-15
        )
        checks["inertia_symmetric_positive_definite_branch_A"].append({
            "configuration_id": config_id,
            "min_eigenvalue_kg_m2": float(eigenvalues.min()),
            "symmetric": bool(symmetric),
            "pass": bool(symmetric and eigenvalues.min() > 0.0),
        })

        bbox = aggregation_scope_bbox(members)
        components_out = []
        for member in members:
            components_out.append({
                "component_id": member["component_id"],
                "mass_kg": member["mass_kg"],
                "mass_classification": member["mass_classification"],
                "com_S_m": [float(v) for v in member["com_S_m"]],
                "com_classification": member["property_classification"],
                "transform_classification": member["transform_classification"],
                "transform_ref": member.get("transform_ref"),
                "inertia_role": "own_com_tensor_rotated_into_S_plus_parallel_axis",
                "inertia_classification": member["property_classification"],
                "standard_uncertainty": None,
                "uncertainty_status": "HOLD",
                "source_ref": member["source_ref"],
                **({"pose_status": member["pose_status"]} if member.get("pose_status") else {}),
            })

        bbox_cross_refs = {
            "m5_whole_assembly_diagnostic_bbox_S_m": m5_record["bbox_S_m"],
            "m5_snapshot": m5_record["snapshot"],
        }
        if config_id == "C01":
            bbox_cross_refs["m4_bus_and_deployed_panels_extent_xyz_m"] = lib["bbox"]["diagnostic_bus_and_deployed_panels_extent_xyz_m"]

        configurations_out.append({
            "configuration_id": config_id,
            "name": lib["name"],
            "legacy_mapping": lib["legacy_mapping"],
            "transform_binding": f"CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml#configuration_bindings[{config_id}]",
            "release_aggregation_active": False,
            "mass": {
                "released_value_kg": None,
                "released_standard_uncertainty_kg": None,
                "diagnostic_branches": {
                    "legacy_A_value_kg": branch_a["mass_kg"],
                    "legacy_A_model": lib["mass"]["diagnostic_branches"].get("legacy_A_model") or lib["mass"]["diagnostic_branches"].get("legacy_A_assumption"),
                    "m3r_B_value_kg": float(branch_b_mass),
                    "m3r_B_model": lib["mass"]["diagnostic_branches"]["m3r_B_model"],
                    "branch_definition_source": "SYSTEM_MASS_PROPERTIES_V3.yaml#diagnostic_nonrelease_branches",
                },
                "diagnostic_standard_uncertainty_kg": None,
                "status": "HOLD_COMPONENT_COVERAGE_AND_UNCERTAINTY",
            },
            "cg": {
                "released_xyz_m": None,
                "reference_frame": "spacecraft_assembly_frame",
                "released_standard_uncertainty_xyz_m": None,
                "diagnostic_branch_A_xyz_m": [float(v) for v in branch_a["cg_S_m"]],
                "diagnostic_branch_A_scope": "BUS_NO_PANELS_PLUS_TWO_PANELS_PLUS_B601" + ("_PLUS_TARGET_SCENARIO" if target else ""),
                "diagnostic_branch_B_xyz_m": None,
                "diagnostic_branch_B_status": BRANCH_B_CG_INERTIA_HOLD,
                "diagnostic_standard_uncertainty_xyz_m": None,
                "status": "DIAGNOSTIC_BRANCH_A_NUMERIC_UNDER_CANDIDATE_TRANSFORMS_RELEASE_HOLD",
            },
            "inertia": {
                "released_matrix_kg_m2": None,
                "reference_frame": "spacecraft_assembly_frame",
                "reference_point": "configuration_system_CG",
                "released_standard_uncertainty_matrix_kg_m2": None,
                "diagnostic_branch_A_matrix_kg_m2": [
                    [float(v) for v in row] for row in branch_a["inertia_about_system_cg_S_kg_m2"]
                ],
                "diagnostic_branch_B_matrix_kg_m2": None,
                "diagnostic_branch_B_status": BRANCH_B_CG_INERTIA_HOLD,
                "diagnostic_standard_uncertainty_matrix_kg_m2": None,
                "status": "DIAGNOSTIC_BRANCH_A_NUMERIC_UNDER_CANDIDATE_TRANSFORMS_RELEASE_HOLD",
            },
            "bbox": {
                "released_min_xyz_m": None,
                "released_max_xyz_m": None,
                "released_extent_xyz_m": None,
                "reference_frame": "spacecraft_assembly_frame",
                "diagnostic_aggregation_scope_min_xyz_m": bbox["min_xyz_m"],
                "diagnostic_aggregation_scope_max_xyz_m": bbox["max_xyz_m"],
                "diagnostic_aggregation_scope_extent_xyz_m": bbox["extent_xyz_m"],
                "diagnostic_scope": (
                    "BUS_BAYS_BOX_PLUS_LEGACY_FLANGE_BOX_PLUS_PANEL_PLATE_BOXES_UNDER_CANDIDATE_TRANSFORMS_"
                    "NOT_ARM_NOT_TARGET_NOT_WHOLE_ASSEMBLY"
                ),
                "cross_references": bbox_cross_refs,
                "status": "DIAGNOSTIC_PRIMITIVE_SCOPE_ONLY_WHOLE_ASSEMBLY_BBOX_HOLD",
            },
            "components_diagnostic_branch_A": components_out,
            "collision": {
                "whole_assembly_evaluated": False,
                "status": "HOLD_SEE_M5_BROADPHASE_CONTRACT_NO_NARROW_PHASE_OR_SYSTEM_RELEASE",
            },
            "confidence": lib["confidence"],
            "status": "DIAGNOSTIC_VALUES_UNDER_CANDIDATE_TRANSFORMS_RELEASE_PROPERTIES_HOLD",
        })

    # --- whole-sat closure check: bus + 2 deployed panels must rebuild servicer_12U_v0 ---
    whole = stage1_rows["servicer_12U_v0"]
    closure_members = [
        bus_member(),
        panel_member("left", "panel_left_deployed"),
        panel_member("right", "panel_right_deployed"),
    ]
    closure = aggregate(closure_members)
    whole_cg = np.array([float(whole["cg_x_m"]), float(whole["cg_y_m"]), float(whole["cg_z_m"])])
    whole_inertia = np.array([
        [float(whole["Ixx_kgm2"]), float(whole["Ixy_kgm2"]), float(whole["Ixz_kgm2"])],
        [float(whole["Ixy_kgm2"]), float(whole["Iyy_kgm2"]), float(whole["Iyz_kgm2"])],
        [float(whole["Ixz_kgm2"]), float(whole["Iyz_kgm2"]), float(whole["Izz_kgm2"])],
    ])
    # servicer_12U_v0 inertia is about its own CoM; our aggregate is about the
    # recomputed system CG, so the comparison is direct.
    closure_check = {
        "reference_row": "servicer_12U_v0 (stage1 mass_inertia_budget_v1.csv, CSV 7-decimal rounding)",
        "mass_abs_err_kg": abs(closure["mass_kg"] - float(whole["mass_kg"])),
        "cg_max_abs_err_m": float(np.max(np.abs(closure["cg_S_m"] - whole_cg))),
        "inertia_max_abs_err_kg_m2": float(np.max(np.abs(closure["inertia_about_system_cg_S_kg_m2"] - whole_inertia))),
        "tolerances": {"mass_kg": 1e-9, "cg_m": 5e-6, "inertia_kg_m2": 5e-6},
    }
    closure_check["pass"] = (
        closure_check["mass_abs_err_kg"] < 1e-9
        and closure_check["cg_max_abs_err_m"] < 5e-6
        and closure_check["inertia_max_abs_err_kg_m2"] < 5e-6
    )

    def flatten_pass(items: list[dict[str, Any]]) -> bool:
        return all(item["pass"] for item in items)

    # --- governance scans, computed over the assembled output (not asserted) ---
    def scan_governance(node: Any, hits: dict[str, list[str]], path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if (
                    "uncertainty" in key.lower()
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                ):
                    hits["numeric_uncertainty"].append(f"{path}/{key}")
                if key == "release_aggregation_active" and value is not False:
                    hits["release_active"].append(f"{path}/{key}")
                scan_governance(value, hits, f"{path}/{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                scan_governance(item, hits, f"{path}[{index}]")

    diagnostic_checks = {
        "m4_branch_mass_regression_18_values": {
            "pass": flatten_pass(checks["m4_branch_mass_regression"]),
            "max_abs_err_kg": max(
                max(item["branch_A_abs_err_kg"], item["branch_B_abs_err_kg"])
                for item in checks["m4_branch_mass_regression"]
            ),
            "detail": checks["m4_branch_mass_regression"],
        },
        "deployed_panels_whole_sat_closure_vs_stage1_row": closure_check,
        "target_capture_transforms_match_m5_display_rows": {
            "pass": flatten_pass(checks["target_transform_matches_m5_contract"]),
            "detail": checks["target_transform_matches_m5_contract"],
        },
        "branch_A_inertia_symmetric_positive_definite_all_configs": {
            "pass": flatten_pass(checks["inertia_symmetric_positive_definite_branch_A"]),
            "detail": checks["inertia_symmetric_positive_definite_branch_A"],
        },
        # filled after the output mapping is assembled
        "uncertainty_fields_all_null": None,
        "release_aggregation_active_all_false": None,
    }
    all_pass = (
        diagnostic_checks["m4_branch_mass_regression_18_values"]["pass"]
        and closure_check["pass"]
        and diagnostic_checks["target_capture_transforms_match_m5_display_rows"]["pass"]
        and diagnostic_checks["branch_A_inertia_symmetric_positive_definite_all_configs"]["pass"]
    )

    def rel(path: Path) -> str:
        return path.relative_to(WORKSPACE).as_posix()

    source_register = {
        "m4_system_mass_properties_v3": {"path": rel(V3_PATH), "sha256": sha256(V3_PATH)},
        "m4_configuration_library_v1": {"path": rel(CONFIG_LIB_PATH), "sha256": sha256(CONFIG_LIB_PATH)},
        "m4_frame_tree": {"path": rel(FRAME_TREE_PATH), "sha256": sha256(FRAME_TREE_PATH)},
        "b601_named_pose_revalidation": {"path": rel(REVALIDATION_PATH), "sha256": sha256(REVALIDATION_PATH)},
        "m5_configuration_geometry_contract": {"path": rel(M5_CONTRACT_PATH), "sha256": sha256(M5_CONTRACT_PATH)},
        "geometry_ssot_service_spacecraft": {"path": rel(SERVICE_SPACECRAFT_PATH), "sha256": sha256(SERVICE_SPACECRAFT_PATH)},
        "geometry_ssot_flexible_appendage": {"path": rel(FLEXIBLE_APPENDAGE_PATH), "sha256": sha256(FLEXIBLE_APPENDAGE_PATH)},
        "geometry_ssot_frame_tree": {"path": rel(GEOMETRY_FRAME_TREE_PATH), "sha256": sha256(GEOMETRY_FRAME_TREE_PATH)},
        "stage1_mass_budget": {"path": rel(STAGE1_BUDGET_PATH), "sha256": sha256(STAGE1_BUDGET_PATH)},
        "target_models_ssot": {"path": rel(TARGET_MODELS_PATH), "sha256": sha256(TARGET_MODELS_PATH)},
        "accepted_b601_urdf_L0_witness": {"path": rel(URDF_PATH), "sha256": sha256(URDF_PATH)},
        "m6_wp2_transform_candidates": {"path": rel(TRANSFORM_CANDIDATES_PATH), "sha256": sha256(TRANSFORM_CANDIDATES_PATH)},
    }

    output = {
        "schema_version": "SYSTEM_MASS_PROPERTIES_V4_DIAGNOSTIC",
        "generated_local": now_local(),
        "phase": "M6_CANDIDATE_AUTHORITY_CLOSURE",
        "work_package": "WP2_MASS9",
        "scope": "NINE_CONFIGURATION_DIAGNOSTIC_MASS_CG_INERTIA_BBOX_UNDER_CANDIDATE_TRANSFORMS",
        "release_aggregation_active": False,
        "release_status": "DIAGNOSTIC_ONLY_NOT_RELEASED_NO_WRITEBACK_TO_M4_M5_CDR_SIM_BASELINES",
        "overall_status": "DIAGNOSTIC_BRANCH_A_NUMERIC_9_OF_9_BRANCH_B_MASS_ONLY_9_OF_9_ALL_RELEASE_FIELDS_HOLD",
        "units": {"mass": "kg", "center_of_mass": "m", "inertia": "kg*m^2", "linear_dimension": "m", "angle": "rad"},
        "aggregation_contract": {
            "target_frame": "spacecraft_assembly_frame (frozen identity alias of S, M4 frame tree)",
            "mass_model": "m_system = sum(m_i) over the declared non-overlapping member set",
            "center_of_mass_model": "r_system = sum(m_i*r_i)/sum(m_i) under the candidate transforms",
            "inertia_model": "rotate each own-COM tensor into S, then parallel-axis shift to the configuration system CG",
            "tensor_matrix_order": [[ "Ixx", "Ixy", "Ixz" ], [ "Ixy", "Iyy", "Iyz" ], [ "Ixz", "Iyz", "Izz" ]],
            "zero_fill_forbidden": True,
            "diagnostic_values_authoritative_for_simulation": False,
            "candidate_density_as_measurement_forbidden": True,
        },
        "branch_semantics_preserved": {
            "branch_A": branches["branch_A_legacy_bus_as_is_plus_b601"]["branch_id"],
            "branch_B": branches["branch_B_bus_minus_legacy_flange_plus_m3r_plus_b601"]["branch_id"],
            "legacy_flange_boundary_ruling_ref": "SYSTEM_MASS_PROPERTIES_V3.yaml#diagnostic_nonrelease_branches.legacy_flange_boundary_ruling",
            "branch_B_mass_basis": "diagnostic bus core 22.927194215348 kg + 2*panel + B601 + M3R 0.7619 kg (+ target scenario where bound)",
            "branch_B_cg_inertia_policy": BRANCH_B_CG_INERTIA_HOLD,
        },
        "aggregator": {
            "path": "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp2_mass_properties/aggregate_m6_mass_properties.py",
            "rerun_command": "python 20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp2_mass_properties/aggregate_m6_mass_properties.py",
        },
        "source_register": source_register,
        "diagnostic_checks": diagnostic_checks,
        "configurations": configurations_out,
        "summary": {
            "configuration_count": 9,
            "released_mass_count": 0,
            "released_cg_count": 0,
            "released_inertia_count": 0,
            "released_bbox_count": 0,
            "diagnostic_mass_count": 9,
            "diagnostic_cg_branch_A_count": 9,
            "diagnostic_inertia_branch_A_count": 9,
            "diagnostic_cg_branch_B_count": 0,
            "diagnostic_inertia_branch_B_count": 0,
            "all_checks_pass": all_pass,
            "diagnostic_use_authorization": "DIGITAL_WIRING_SANITY_AND_RANGE_CHECK_ONLY_NOT_RELEASE_LOADS_FEA_MARGIN_OR_QUALIFICATION",
        },
        "missing_authorities_preserved": v3["missing_authorities"] + [
            "PANEL_FULL_HINGE_KINEMATICS_RATIFICATION",
            "PANEL_FAILURE_RETAINED_OR_JETTISONED_APPROVAL",
            "TARGET_CAPTURE_TRANSFORM_RATIFICATION",
        ],
        "release_prohibitions": v3["release_prohibitions"] + [
            "DO_NOT_TREAT_CANDIDATE_TRANSFORMS_AS_RATIFIED_HINGE_OR_CAPTURE_KINEMATICS",
            "DO_NOT_WRITE_ANY_VALUE_OF_THIS_FILE_BACK_INTO_M4_M5_CDR_OR_SIM_BASELINES",
        ],
    }

    # Governance scans computed over the assembled output mapping.
    governance_hits: dict[str, list[str]] = {"numeric_uncertainty": [], "release_active": []}
    scan_governance(output, governance_hits)
    output["diagnostic_checks"]["uncertainty_fields_all_null"] = not governance_hits["numeric_uncertainty"]
    output["diagnostic_checks"]["release_aggregation_active_all_false"] = not governance_hits["release_active"]
    all_pass = (
        all_pass
        and output["diagnostic_checks"]["uncertainty_fields_all_null"]
        and output["diagnostic_checks"]["release_aggregation_active_all_false"]
    )
    output["summary"]["all_checks_pass"] = all_pass

    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(output, handle, sort_keys=False, allow_unicode=True, width=120)

    print(json.dumps({
        "output": rel(OUTPUT_PATH),
        "all_checks_pass": all_pass,
        "branch_mass_regression_max_abs_err_kg": diagnostic_checks["m4_branch_mass_regression_18_values"]["max_abs_err_kg"],
        "whole_sat_closure": closure_check,
    }, indent=2))
    if not all_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
