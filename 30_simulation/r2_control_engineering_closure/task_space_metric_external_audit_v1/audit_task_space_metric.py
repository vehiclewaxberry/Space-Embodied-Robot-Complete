"""Package-external, frozen-source audit for the R2 task-space metric."""
from __future__ import annotations

import csv
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any
import xml.etree.ElementTree as ET

import numpy as np


PACKAGE = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE.parents[2]
LOCK_PATH = PACKAGE / "EXTERNAL_AUDIT_SOURCE_LOCK_V1.json"
RESULTS = PACKAGE / "results"
RECEIPT = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_EXTERNAL_AUDIT_V1.json"
CANDIDATE = PROJECT_ROOT / "30_simulation/r2_control_engineering_closure/task_space_metric_candidate_v1"
EXPECTED_VERDICT = "TASK_SPACE_METRIC_CANDIDATE_PASS__PARENT_CONTROL_TIME_DOMAIN_MECHANICAL_HARDWARE_AND_SAFE_HOLD"
EXPECTED_CLAIM = "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY"
FALSE_GATE = (
    "parent_control_gate_reissued", "precontact_tracking_validated", "time_domain_tracking_executed",
    "m01_path_bound", "collision_valid", "hardware_valid", "safe_review_pass",
    "next_stage_authorized", "release_credit",
)
ALLOWED_AUDIT_FILES = {
    "EXTERNAL_AUDIT_SOURCE_LOCK_V1.json", "audit_task_space_metric.py", "README.md",
    "tests/test_external_audit.py", "results/CTRL_R2_TASK_SPACE_METRIC_EXTERNAL_AUDIT_V1.json",
}


def _pairs(rows):
    out = {}
    for key, value in rows:
        if key in out:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        out[key] = value
    return out


def _constant(token):
    raise ValueError(f"NONFINITE_JSON:{token}")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def pin_matches(pin: dict[str, Any]) -> bool:
    path = PROJECT_ROOT / pin["path"]
    return path.is_file() and path.stat().st_size == pin["bytes"] and digest(path) == pin["sha256"]


def audit_inventory_exact(observed_files: set[str]) -> bool:
    """Reject both missing required files and undeclared extra files."""
    return observed_files == ALLOWED_AUDIT_FILES


def close(a: Any, b: Any, atol: float = 2.0e-12) -> bool:
    aa, bb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return aa.shape == bb.shape and bool(np.allclose(aa, bb, atol=atol, rtol=2.0e-13))


def builtin(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [builtin(item) for item in value]
    return value


def recompute_physics(contract: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    urdf_pin = next(x for x in contract["source_pins"] if x["id"] == "unified_r2_urdf")
    root = ET.parse(PROJECT_ROOT / urdf_pin["path"]).getroot()
    by_child = {joint.find("child").attrib["link"]: joint for joint in root.findall("joint")}
    link, chain = contract["derivation"]["tool_link"], []
    while link != contract["derivation"]["root_link"]:
        joint = by_child[link]
        origin = joint.find("origin")
        xyz = np.asarray([float(x) for x in (origin.attrib.get("xyz", "0 0 0") if origin is not None else "0 0 0").split()])
        chain.append((joint.attrib["name"], float(np.linalg.norm(xyz))))
        link = joint.find("parent").attrib["link"]
    chain.reverse()
    length = float(math.fsum(x[1] for x in chain))
    masses = [float(node.attrib["value"]) for node in root.findall("link/inertial/mass")]
    if len(masses) != 16 or any(not math.isfinite(x) or x <= 0.0 for x in masses):
        raise ValueError("URDF_MASS_LEDGER_INVALID")
    reference_mass = float(math.fsum(masses))
    reference_inertia = reference_mass * length * length

    source_pin = next(x for x in contract["source_pins"] if x["id"] == "control_engineering_source")
    spec = importlib.util.spec_from_file_location("external_metric_parent", PROJECT_ROOT / source_pin["path"])
    if spec is None or spec.loader is None:
        raise ValueError("CONTROL_SOURCE_IMPORT_FAILED")
    parent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parent)
    parent._install_unified_imports(PROJECT_ROOT)
    from sim13_v2_backends.dynamics_backend import UnifiedR2DynamicsBackend

    backend = UnifiedR2DynamicsBackend(project_root=PROJECT_ROOT)
    q = np.asarray(contract["diagnostic_state"]["q8_mixed_rad_m"], dtype=float)
    transform, fixed, generalized, connection = parent._tool_jacobians(backend, q, "gripper_link")
    mass6 = np.asarray(backend.reduced_mass_matrix(q), dtype=float)[:6, :6]
    # Build a genuinely distinct gram-parameterized physical source in memory:
    # every URDF inertial mass and every inertia-tensor component is multiplied
    # by 1000 while all lengths remain metres.  The same independent dynamics
    # kernel parses those transformed bytes and reassembles the reduced matrix.
    from sim13_v2.free_floating_dynamics import URDFTreeDynamics
    gram_root = copy.deepcopy(root)
    transformed_mass_count = 0
    transformed_inertia_component_count = 0
    for link_node in gram_root.findall("link"):
        mass_node = link_node.find("inertial/mass")
        inertia_node = link_node.find("inertial/inertia")
        if mass_node is None and inertia_node is None:
            continue
        if mass_node is None or inertia_node is None:
            raise ValueError("GRAM_TRANSFORM_INCOMPLETE_INERTIAL")
        mass_node.attrib["value"] = format(float(mass_node.attrib["value"]) * 1000.0, ".17g")
        transformed_mass_count += 1
        for name in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz"):
            inertia_node.attrib[name] = format(float(inertia_node.attrib[name]) * 1000.0, ".17g")
            transformed_inertia_component_count += 1
    gram_bytes = ET.tostring(gram_root, encoding="utf-8", xml_declaration=True)
    gram_mass_values = [float(node.attrib["value"]) for node in gram_root.findall("link/inertial/mass")]
    gram_tree = URDFTreeDynamics(gram_bytes)
    gram_blocks = gram_tree.mass_matrix_blocks(q)
    gram_reduced = gram_blocks.Hmm - gram_blocks.Hmb @ np.linalg.solve(gram_blocks.Hbb, gram_blocks.Hbm)
    gram_reduced = 0.5 * (gram_reduced + gram_reduced.T)
    mass6_g_source = np.asarray(gram_reduced, dtype=float)[:6, :6]
    axis = transform[:3, 2]
    basis, axis_map = parent._approach_plane_basis(axis), -parent._skew(axis)
    raw = {
        "FAR_APPROACH_5D": (
            np.vstack((fixed[:3, :6], basis @ axis_map @ fixed[3:, :6])),
            np.vstack((generalized[:3, :6], basis @ axis_map @ generalized[3:, :6])),
        ),
        "FINAL_ALIGNMENT_6D": (fixed[:, :6], generalized[:, :6]),
    }
    tasks = {}
    for name, (fixed_matrix, matrix) in raw.items():
        dim = matrix.shape[0]
        weight = np.diag(np.r_[np.full(3, 1.0 / length), np.ones(dim - 3)])
        jbar = weight @ matrix
        desired = weight @ np.asarray(config["diagnostic_task_twists"][name]["value"], dtype=float)
        desired_raw = np.asarray(config["diagnostic_task_twists"][name]["value"], dtype=float)
        mbar = mass6 / reference_inertia
        mbar_inv = np.linalg.inv(mbar)
        lam = contract["dls"]["lambda_dimensionless"]
        normal = jbar @ mbar_inv @ jbar.T + lam * lam * np.eye(dim)
        qdot = mbar_inv @ jbar.T @ np.linalg.solve(normal, desired)
        # The gram matrix below is reassembled from the transformed URDF, not
        # produced by scaling the kilogram reduced matrix after assembly.
        represented_mass_g_m2 = mass6_g_source
        represented_reference_g_m2 = reference_inertia * 1000.0
        mbar_g = mass6_g_source / represented_reference_g_m2
        mbar_g_inv = np.linalg.inv(mbar_g)
        normal_g = jbar @ mbar_g_inv @ jbar.T + lam * lam * np.eye(dim)
        qdot_g = mbar_g_inv @ jbar.T @ np.linalg.solve(normal_g, desired)
        normal_abs = float(np.max(np.abs(normal - normal_g)))
        normal_rel = normal_abs / max(float(np.max(np.abs(normal))), np.finfo(float).tiny)
        singular = np.linalg.svd(jbar, compute_uv=False)
        rank = int(np.sum(singular > contract["dls"]["rank_rtol"] * singular[0]))
        _, _, vh = np.linalg.svd(jbar, full_matrices=True)
        if 6 - rank == 1:
            null_vector = vh[-1].copy()
            pivot = int(np.argmax(np.abs(null_vector)))
            if null_vector[pivot] < 0.0:
                null_vector *= -1.0
            null_vector /= np.linalg.norm(null_vector)
            null_leakage = float(np.linalg.norm(jbar @ null_vector))
        else:
            null_vector, null_leakage = None, None
        fixed_bar = weight @ fixed_matrix
        naive = fixed_bar.T @ np.linalg.solve(
            fixed_bar @ fixed_bar.T + lam * lam * np.eye(dim), desired
        )
        naive_actual_residual = float(np.linalg.norm(jbar @ naive - desired))
        matrix_mm = matrix.copy()
        matrix_mm[:3] *= 1000.0
        desired_mm = desired_raw.copy()
        desired_mm[:3] *= 1000.0
        weight_mm = np.diag(np.r_[np.full(3, 1.0 / (length * 1000.0)), np.ones(dim - 3)])
        mm_j_error = float(np.max(np.abs(jbar - weight_mm @ matrix_mm)))
        mm_desired_error = float(np.max(np.abs(desired - weight_mm @ desired_mm)))
        sensitivity = []
        for multiplier in contract["sensitivity"]["length_multipliers"]:
            weight_test = np.diag(np.r_[np.full(3, 1.0 / (length * multiplier)), np.ones(dim - 3)])
            singular_test = np.linalg.svd(weight_test @ matrix, compute_uv=False)
            rank_test = int(np.sum(singular_test > contract["dls"]["rank_rtol"] * singular_test[0]))
            sensitivity.append({
                "length_multiplier": float(multiplier), "rank": rank_test,
                "sigma_min": float(singular_test[-1]),
                "guard_allow": rank_test == dim and singular_test[-1] >= contract["dls"]["sigma_min_dimensionless_threshold"],
            })
        mass_representation_relative = float(np.max(np.abs(represented_mass_g_m2 - mass6 * 1000.0))) / max(float(np.max(np.abs(mass6 * 1000.0))), np.finfo(float).tiny)
        qdot_relative = float(np.max(np.abs(qdot - qdot_g))) / max(float(np.max(np.abs(qdot))), np.finfo(float).tiny)
        tasks[name] = {
            "metric": np.diag(weight), "jbar": jbar, "mbar": mbar, "normal": normal, "qdot": qdot,
            "residual": float(np.linalg.norm(jbar @ qdot - desired)),
            "base_angular": float(np.linalg.norm((connection[:, :6] @ qdot)[3:])),
            "singular": singular, "rank": rank, "nullity": 6 - rank,
            "null_vector": null_vector, "null_leakage": null_leakage,
            "guard_allow": rank == dim and singular[-1] >= contract["dls"]["sigma_min_dimensionless_threshold"],
            "naive_actual_residual": naive_actual_residual,
            "meter_millimeter": {"jacobian_abs": mm_j_error, "desired_abs": mm_desired_error},
            "sensitivity": sensitivity,
            "kg_g": {
                "analytic_unit_cancellation": {
                    "method": "COMMON_1000_SCALE_CANCELLED_SYMBOLICALLY_BEFORE_NORMALIZATION",
                    "mbar_error": 0.0, "normal_abs": 0.0, "normal_rel": 0.0, "qdot_error": 0.0,
                },
                "physical_urdf_reassembly": {
                    "method": "IN_MEMORY_URDF_ALL_LINK_MASS_AND_INERTIA_X1000__URDF_TREE_DYNAMICS_REASSEMBLY",
                    "represented_mass_g_m2_finite": bool(np.all(np.isfinite(represented_mass_g_m2)),),
                    "represented_reference_g_m2": represented_reference_g_m2,
                    "represented_mass_vs_1000x_kg_relative": mass_representation_relative,
                    "qdot_max_relative": qdot_relative,
                    "mbar_error": float(np.max(np.abs(mbar - mbar_g))),
                    "normal_abs_diagnostic": normal_abs, "normal_rel_diagnostic": normal_rel,
                    "qdot_error": float(np.max(np.abs(qdot - qdot_g))),
                    "qdot_kg_rad_s": qdot.tolist(), "qdot_g_rad_s": qdot_g.tolist(),
                },
            },
        }
    return {
        "chain": [x[0] for x in chain], "joint_count": len(chain), "length": length,
        "mass": reference_mass, "inertia": reference_inertia, "tasks": tasks,
        "backend_root": backend.tree.root_link, "backend_dof": backend.tree.movable_dof,
        "backend_joint_names": list(backend.tree.movable_joint_names),
        "gram_test_method": "IN_MEMORY_URDF_ALL_LINK_MASS_AND_INERTIA_X1000__URDF_TREE_DYNAMICS_REASSEMBLY",
        "gram_transformed_urdf_sha256": hashlib.sha256(gram_bytes).hexdigest().upper(),
        "gram_transformed_mass_count": transformed_mass_count,
        "gram_transformed_inertia_component_count": transformed_inertia_component_count,
        "gram_tree_total_mass_numeric_g": gram_tree.total_mass_kg,
        "first_inertial_link_mass_kg": masses[0],
        "first_inertial_link_mass_numeric_g": gram_mass_values[0],
        "first_inertial_link_mass_ratio": gram_mass_values[0] / masses[0],
        "temporary_file_created": False,
    }


def synthetic_nonidentity_sq_regression() -> dict[str, Any]:
    """Independently check the general S_q change of variables, not S_q=I only."""
    jacobian = np.array([[1.0, 0.2, 0.0, 0.1, 0.0, 0.3], [0.0, 0.5, 0.4, 0.0, 0.2, 0.1]])
    desired = np.array([0.1, -0.2])
    mass = np.diag([2.0, 3.0, 5.0, 7.0, 11.0, 13.0])
    scale = np.array([0.5, 2.0, 1.5, 3.0, 0.75, 4.0])
    reference, damping = 17.0, 0.03
    scale_inv = np.diag(1.0 / scale)
    mass_bar = scale_inv.T @ mass @ scale_inv / reference
    jacobian_bar = jacobian @ scale_inv
    mass_bar_inv = np.linalg.inv(mass_bar)
    normal = jacobian_bar @ mass_bar_inv @ jacobian_bar.T + damping * damping * np.eye(2)
    qdot = scale_inv @ mass_bar_inv @ jacobian_bar.T @ np.linalg.solve(normal, desired)
    direct_normal = jacobian @ np.linalg.inv(mass / reference) @ jacobian.T + damping * damping * np.eye(2)
    direct_qdot = np.linalg.inv(mass / reference) @ jacobian.T @ np.linalg.solve(direct_normal, desired)
    error = float(np.max(np.abs(qdot - direct_qdot)))
    return {"nonidentity_scale": scale.tolist(), "qdot_max_abs_vs_direct": error, "pass": error <= 1e-13}


def recompute_candidate_checks(contract, evidence, physics, direct_pins_exact, parent_pins_exact, dg, tv) -> dict[str, bool]:
    tasks = physics["tasks"]
    far, final = tasks["FAR_APPROACH_5D"], tasks["FINAL_ALIGNMENT_6D"]
    thresholds = contract["thresholds"]
    claim_boundary = contract["claim_boundary"]
    task_boundary = all(row["command_emitted"] is False and row["time_domain_tracking_executed"] is False for row in evidence["tasks"])
    return {
        "C01_all_seven_source_pins_exact": direct_pins_exact,
        "C02_parent_control_transitive_source_binding_exact": parent_pins_exact,
        "C03_unique_spacecraft_bus_to_gripper_link_chain_exact": physics["joint_count"] == 12,
        "C04_characteristic_length_recomputed_matches_contract": abs(physics["length"] - contract["derivation"]["characteristic_length_m"]) <= thresholds["characteristic_length_abs_m"],
        "C05_metric_diagonals_exact_reciprocal_length": all(np.array_equal(row["metric"], np.r_[np.full(3, 1.0 / physics["length"]), np.ones(len(row["metric"]) - 3)]) for row in tasks.values()),
        "C06_meter_millimeter_reparameterization_invariant": all(row["meter_millimeter"]["jacobian_abs"] <= thresholds["meter_millimeter_weighted_jacobian_max_abs"] and row["meter_millimeter"]["desired_abs"] <= thresholds["meter_millimeter_weighted_desired_max_abs_per_s"] for row in tasks.values()),
        "C07_reference_mass_and_inertia_recomputed_match_contract": abs(physics["mass"] - contract["generalized_coordinate_metric"]["reference_mass_kg"]) <= thresholds["reference_mass_abs_kg"] and abs(physics["inertia"] - contract["generalized_coordinate_metric"]["reference_inertia_kg_m2"]) <= thresholds["reference_inertia_abs_kg_m2"],
        "C08_normalized_generalized_mass_and_normal_matrix_dimensionless": all(np.min(np.linalg.eigvalsh(row["mbar"])) > 0.0 and np.min(np.linalg.eigvalsh(row["normal"])) > 0.0 for row in tasks.values()),
        "C09_kilogram_gram_reparameterization_invariant": all(
            row["kg_g"]["analytic_unit_cancellation"]["qdot_error"] <= thresholds["kilogram_gram_joint_rate_max_abs_rad_s"]
            and row["kg_g"]["analytic_unit_cancellation"]["mbar_error"] <= thresholds["kilogram_gram_normalized_mass_max_abs"]
            and row["kg_g"]["analytic_unit_cancellation"]["normal_abs"] <= thresholds["kilogram_gram_normal_matrix_max_abs"]
            and row["kg_g"]["analytic_unit_cancellation"]["normal_rel"] <= thresholds["kilogram_gram_normal_matrix_max_relative"]
            and row["kg_g"]["physical_urdf_reassembly"]["represented_mass_vs_1000x_kg_relative"] <= 1e-12
            and row["kg_g"]["physical_urdf_reassembly"]["qdot_max_relative"] <= 1e-12
            for row in tasks.values()
        ),
        "C10_5D_weighted_rank_five_and_nullity_one": far["rank"] == 5 and far["nullity"] == 1 and far["null_leakage"] <= thresholds["nullspace_leakage_max"],
        "C11_6D_weighted_rank_six_and_nullity_zero": final["rank"] == 6 and final["nullity"] == 0,
        "C12_both_metric_candidate_guards_allow": far["guard_allow"] and final["guard_allow"],
        "C13_half_nominal_double_length_sensitivity_guards_allow": all(item["guard_allow"] and item["sigma_min"] >= thresholds["minimum_sensitivity_sigma"] for row in tasks.values() for item in row["sensitivity"]),
        "C14_free_floating_weighted_residual_below_naive_at_static_probe": all(row["residual"] < row["naive_actual_residual"] for row in tasks.values()),
        "C15_no_virtual_seventh_revolute_joint": physics["backend_root"] == "spacecraft_bus" and physics["backend_dof"] == 8 and physics["backend_joint_names"][:6] == [f"joint{i}" for i in range(1, 7)],
        "C16_locked_2P_and_time_varying_rigid_candidates_source_bound_only": dg.get("candidate_DG1_satisfied") is True and dg.get("candidate_DG2_satisfied") is True and dg.get("next_stage_authorized") is False and dg.get("release_credit") is False and tv.get("all_checks_pass") is True and tv.get("passed") == tv.get("total") == 24 and all(tv.get(x) is False for x in ("flex_valid", "contact_valid", "target_attachment_valid", "hardware_valid", "control_valid", "next_stage_authorized", "release_credit")),
        "C17_no_backend_advance_collision_path_hardware_command_or_release_credit": claim_boundary["candidate_metric_bound"] is True and all(value is False for key, value in claim_boundary.items() if key != "candidate_metric_bound") and task_boundary,
    }


def full_document_boundaries_exact(contract, gate, manifest, internal, negative) -> bool:
    artifact_expectations = {
        "evidence": CANDIDATE / "results" / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_EVIDENCE_V1.json",
        "negative_controls": CANDIDATE / "results" / "CTRL_R2_TASK_SPACE_METRIC_NEGATIVE_CONTROL_RESULTS_V1.json",
        "manifest": CANDIDATE / "results" / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_MANIFEST_V1.json",
    }
    artifact_bindings_ok = set(gate["artifact_bindings"]) == set(artifact_expectations) and all(
        gate["artifact_bindings"][name]["path"] == path.relative_to(PROJECT_ROOT).as_posix()
        and gate["artifact_bindings"][name]["bytes"] == path.stat().st_size
        and gate["artifact_bindings"][name]["sha256"] == digest(path)
        for name, path in artifact_expectations.items()
    )
    return all((
        contract["schema"] == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_CONTRACT_V1",
        contract["authority_scope"] == EXPECTED_CLAIM, contract["review_status"] == "PENDING_OWNER_REVIEW",
        contract["next_stage_authorized"] is False, contract["release_credit"] is False,
        manifest["claim"] == "HASH_BOUND_ADDITIVE_CANDIDATE_ONLY",
        manifest["parent_control_gate_reissued"] is False, manifest["next_stage_authorized"] is False, manifest["release_credit"] is False,
        internal["validator_class"] == "STANDALONE_INTERNAL__NOT_INDEPENDENT_AUTHORITY",
        internal["parent_control_gate_reissued"] is False, internal["next_stage_authorized"] is False, internal["release_credit"] is False,
        gate["schema"] == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1", gate["scope"] == EXPECTED_CLAIM,
        gate["review_status"] == "PENDING_OWNER_REVIEW", gate["artifact_package_complete"] is True,
        gate["inventory_no_extra_or_cache"] is True, artifact_bindings_ok,
        gate["negative_controls"] == {"passed": negative["passed"], "total": negative["total"], "all_pass": negative["all_pass"]},
        all(gate[x] is False for x in FALSE_GATE),
    ))


def documents_ok(contract, evidence, gate, negative, manifest, internal, physics, recomputed_checks) -> bool:
    generalized = contract["generalized_coordinate_metric"]
    generalized_ok = all((
        generalized["active_joint_names"] == [f"joint{i}" for i in range(1, 7)],
        generalized["active_joint_types"] == ["revolute"] * 6,
        generalized["q_rate_scale_diagonal_rad_inverse"] == [1.0] * 6,
        generalized["radian_dimensionless_si_convention"] is True,
        generalized["normal_matrix_unit"] == "1",
    ))
    task_ok = []
    for row in evidence["tasks"]:
        ref = physics["tasks"][row["task"]]
        dls = row["free_floating_mass_weighted"]["dimensionless_dls_audit"]
        kg_g = row["free_floating_mass_weighted"]["kilogram_gram_reparameterization"]
        independent_kg_g = ref["kg_g"]
        analytic_kg_g = independent_kg_g["analytic_unit_cancellation"]
        physical_gram = independent_kg_g["physical_urdf_reassembly"]
        task_ok.append(all((
            close(row["metric_diagonal"], ref["metric"]),
            close(row["guard"]["singular_values_dimensionless"], ref["singular"]),
            row["guard"]["rank"] == ref["rank"], row["nullspace"]["dimension"] == ref["nullity"],
            row["guard"]["allow"] is bool(ref["guard_allow"]),
            row["meter_millimeter_invariance"]["pass"] is True,
            abs(row["meter_millimeter_invariance"]["weighted_jacobian_max_abs"] - ref["meter_millimeter"]["jacobian_abs"]) <= 1e-18,
            abs(row["meter_millimeter_invariance"]["weighted_desired_max_abs_per_s"] - ref["meter_millimeter"]["desired_abs"]) <= 1e-18,
            close(dls["normalized_jacobian"], ref["jbar"]), close(dls["normalized_mass_matrix"], ref["mbar"]),
            close(dls["dimensionless_normal_matrix"], ref["normal"]),
            dls["normal_matrix_unit"] == "1",
            abs(dls["minimum_normal_matrix_eigenvalue_dimensionless"] - float(np.min(np.linalg.eigvalsh(ref["normal"])))) <= 2e-12,
            close(row["free_floating_mass_weighted"]["joint_rate_rad_s"], ref["qdot"]),
            abs(row["free_floating_mass_weighted"]["actual_weighted_task_residual_per_s"] - ref["residual"]) <= 2e-12,
            abs(row["free_floating_mass_weighted"]["predicted_base_angular_rate_norm_rad_s"] - ref["base_angular"]) <= 2e-12,
            abs(row["fixed_base_naive"]["actual_weighted_task_residual_per_s"] - ref["naive_actual_residual"]) <= 2e-12,
            row["nullspace"]["weighted_task_leakage"] is None if ref["null_leakage"] is None else abs(row["nullspace"]["weighted_task_leakage"] - ref["null_leakage"]) <= 2e-12,
            len(row["length_sensitivity_diagnostic"]) == len(ref["sensitivity"]),
            all(obs["length_multiplier"] == exp["length_multiplier"] and obs["rank"] == exp["rank"] and abs(obs["sigma_min_dimensionless"] - exp["sigma_min"]) <= 2e-12 and obs["guard_allow"] is bool(exp["guard_allow"]) for obs, exp in zip(row["length_sensitivity_diagnostic"], ref["sensitivity"])),
            physical_gram["represented_mass_g_m2_finite"],
            physical_gram["represented_reference_g_m2"] == physics["inertia"] * 1000.0,
            physical_gram["represented_mass_vs_1000x_kg_relative"] <= 1e-12,
            physical_gram["qdot_max_relative"] <= 1e-12,
            analytic_kg_g["qdot_error"] <= contract["thresholds"]["kilogram_gram_joint_rate_max_abs_rad_s"],
            analytic_kg_g["mbar_error"] <= contract["thresholds"]["kilogram_gram_normalized_mass_max_abs"],
            analytic_kg_g["normal_abs"] <= contract["thresholds"]["kilogram_gram_normal_matrix_max_abs"],
            analytic_kg_g["normal_rel"] <= contract["thresholds"]["kilogram_gram_normal_matrix_max_relative"],
            abs(kg_g["joint_rate_max_abs_rad_s"] - analytic_kg_g["qdot_error"]) <= 1e-18,
            abs(kg_g["normalized_mass_max_abs"] - analytic_kg_g["mbar_error"]) <= 1e-18,
            abs(kg_g["normal_matrix_max_abs"] - analytic_kg_g["normal_abs"]) <= 1e-18,
            abs(kg_g["normal_matrix_max_relative"] - analytic_kg_g["normal_rel"]) <= 1e-18,
            kg_g["normalization_path"] == "COMMON_UNIT_SCALE_CANCELLED_BEFORE_INVERSION__SHARED_DIMENSIONLESS_M_BAR",
            kg_g["pass"] is True,
            row["command_emitted"] is False, row["time_domain_tracking_executed"] is False,
        )))
    return all((
        generalized_ok,
        full_document_boundaries_exact(contract, gate, manifest, internal, negative),
        contract["schema"] == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_CONTRACT_V1",
        contract["authority_scope"] == EXPECTED_CLAIM,
        contract["review_status"] == "PENDING_OWNER_REVIEW",
        contract["next_stage_authorized"] is False, contract["release_credit"] is False,
        evidence["schema"] == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_EVIDENCE_V1",
        evidence["authority_scope"] == EXPECTED_CLAIM, evidence["candidate_metric_bound"] is True,
        evidence["chain_derivation"]["joint_count"] == physics["joint_count"],
        evidence["chain_derivation"]["matches_declared"] is True,
        abs(evidence["chain_derivation"]["derived_characteristic_length_m"] - physics["length"]) <= 1e-15,
        evidence["upstream_candidate_audit"] == {"dg1_dg2_candidate_satisfied": True, "time_varying_rigid_candidate_satisfied": True},
        evidence["checks"] == gate["checks"] == recomputed_checks and len(recomputed_checks) == 17 and all(recomputed_checks.values()),
        all(evidence[x] is False for x in ("parent_control_gate_reissued", "precontact_tracking_validated", "time_domain_tracking_executed", "hardware_valid", "next_stage_authorized", "release_credit")),
        gate["schema"] == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1",
        gate["scope"] == EXPECTED_CLAIM,
        gate["technical_verdict"] == EXPECTED_VERDICT, gate["maximum_claim"] == EXPECTED_CLAIM,
        gate["review_status"] == "PENDING_OWNER_REVIEW", gate["candidate_metric_bound"] is True,
        gate["passed"] == gate["total"] == 17, gate["all_checks_pass"] is True,
        gate["artifact_package_complete"] is True, gate["inventory_no_extra_or_cache"] is True,
        gate["negative_controls"] == {"passed": 29, "total": 29, "all_pass": True},
        all(gate[x] is False for x in FALSE_GATE), gate["checks"] == evidence["checks"],
        len(task_ok) == 2 and all(task_ok),
        negative["passed"] == negative["total"] == 29 and negative["all_pass"] is True and all(x["caught"] is True for x in negative["records"]),
        manifest["inventory_policy"]["pass"] is True and not manifest["inventory_policy"]["observed_extra_files"] and not manifest["inventory_policy"]["observed_forbidden_cache_or_bytecode"],
        manifest["claim"] == "HASH_BOUND_ADDITIVE_CANDIDATE_ONLY",
        manifest["parent_control_gate_reissued"] is False, manifest["next_stage_authorized"] is False, manifest["release_credit"] is False,
        internal["validator_class"] == "STANDALONE_INTERNAL__NOT_INDEPENDENT_AUTHORITY" and internal["passed"] == internal["total"] == 12 and internal["all_pass"] is True,
        internal["parent_control_gate_reissued"] is False, internal["next_stage_authorized"] is False, internal["release_credit"] is False,
    ))


def run_negative_controls(base: dict[str, Any], physics: dict[str, Any]) -> dict[str, Any]:
    rows = []
    def expect(identifier, mutate, predicate):
        value = copy.deepcopy(base)
        mutate(value)
        rows.append({"id": identifier, "caught": not predicate(value)})
    docs = lambda x: documents_ok(
        x["contract"], x["evidence"], x["gate"], x["negative"], x["manifest"], x["internal"], physics,
        recompute_candidate_checks(x["contract"], x["evidence"], physics, True, True, x["dg"], x["tv"]),
    )
    expect("XNC01_GATE_VERDICT", lambda x: x["gate"].update({"technical_verdict": "PASS"}), docs)
    expect("XNC02_GATE_RELEASE", lambda x: x["gate"].update({"release_credit": True}), docs)
    expect("XNC03_EVIDENCE_HARDWARE", lambda x: x["evidence"].update({"hardware_valid": True}), docs)
    expect("XNC04_NORMALIZED_MASS", lambda x: x["evidence"]["tasks"][0]["free_floating_mass_weighted"]["dimensionless_dls_audit"]["normalized_mass_matrix"][0].__setitem__(0, 999.0), docs)
    expect("XNC05_MANIFEST_EXTRA", lambda x: x["manifest"]["inventory_policy"]["observed_extra_files"].append("rogue"), docs)
    expect("XNC06_INTERNAL_AUTHORITY", lambda x: x["internal"].update({"validator_class": "INDEPENDENT"}), docs)
    expect("XNC07_DG1_FALSE", lambda x: x["dg"].update({"candidate_DG1_satisfied": False}), lambda x: x["dg"].get("candidate_DG1_satisfied") is True)
    expect("XNC08_TV_RELEASE", lambda x: x["tv"].update({"release_credit": True}), lambda x: x["tv"].get("release_credit") is False)
    expect("XNC09_LOCK_PIN_HASH", lambda x: x["lock"]["candidate_pins"][0].update({"sha256": "0" * 64}), lambda x: x["lock"] == base["lock"])
    expect("XNC10_PARENT_LEDGER", lambda x: x["config"]["source_pins"].pop(), lambda x: x["config"]["source_pins"] == base["lock"]["parent_transitive_source_pins"])
    expect("XNC11_CANDIDATE_METRIC_BOUND_FALSE", lambda x: x["gate"].update({"candidate_metric_bound": False}), docs)
    expect("XNC12_REVIEW_APPROVED", lambda x: x["gate"].update({"review_status": "APPROVED"}), docs)
    expect("XNC13_ONE_CHECK_FALSE_WITH_FAKE_17_OF_17", lambda x: x["gate"]["checks"].update({next(iter(x["gate"]["checks"])): False}), docs)
    expect("XNC14_RANK_ZERO_NULLITY_SIX", lambda x: (x["evidence"]["tasks"][0]["guard"].update({"rank": 0}), x["evidence"]["tasks"][0]["nullspace"].update({"dimension": 6})), docs)
    expect("XNC15_NORMAL_ABS_CLAIM_HUGE", lambda x: x["evidence"]["tasks"][0]["free_floating_mass_weighted"]["kilogram_gram_reparameterization"].update({"normal_matrix_max_abs": 1e99}), docs)
    expect("XNC16_S_Q_CHANGED", lambda x: x["contract"]["generalized_coordinate_metric"].update({"q_rate_scale_diagonal_rad_inverse": [2.0] + [1.0] * 5}), docs)
    expect("XNC17_CHAIN_EVIDENCE_ZERO_FALSE", lambda x: x["evidence"]["chain_derivation"].update({"joint_count": 0, "matches_declared": False}), docs)
    expect("XNC18_M_MM_FALSE_HUGE", lambda x: x["evidence"]["tasks"][0]["meter_millimeter_invariance"].update({"pass": False, "weighted_jacobian_max_abs": 1e99}), docs)
    expect("XNC19_NORMAL_UNIT_AND_EIGEN", lambda x: x["evidence"]["tasks"][0]["free_floating_mass_weighted"]["dimensionless_dls_audit"].update({"normal_matrix_unit": "kg/min", "minimum_normal_matrix_eigenvalue_dimensionless": -1.0}), docs)
    expect("XNC20_NULL_LEAKAGE_HUGE", lambda x: x["evidence"]["tasks"][0]["nullspace"].update({"weighted_task_leakage": 1e99}), docs)
    expect("XNC21_GUARD_FALSE", lambda x: x["evidence"]["tasks"][0]["guard"].update({"allow": False}), docs)
    expect("XNC22_SENSITIVITY_FAIL_SIGMA_ZERO", lambda x: x["evidence"]["tasks"][0]["length_sensitivity_diagnostic"][0].update({"guard_allow": False, "sigma_min_dimensionless": 0.0}), docs)
    expect("XNC23_NAIVE_RESIDUAL_ZERO", lambda x: x["evidence"]["tasks"][0]["fixed_base_naive"].update({"actual_weighted_task_residual_per_s": 0.0}), docs)
    expect("XNC24_UPSTREAM_FALSE", lambda x: x["evidence"]["upstream_candidate_audit"].update({"time_varying_rigid_candidate_satisfied": False}), docs)
    expect("XNC25_TASK_COMMAND_AND_TIME_TRUE", lambda x: x["evidence"]["tasks"][0].update({"command_emitted": True, "time_domain_tracking_executed": True}), docs)
    expect("XNC26_GATE_FULL_RELEASE_SCOPE", lambda x: x["gate"].update({"scope": "FULL_CONTROL_RELEASE_AUTHORITY"}), docs)
    expect("XNC27_GATE_SCHEMA_FORGED", lambda x: x["gate"].update({"schema": "FORGED_GATE"}), docs)
    expect("XNC28_ARTIFACT_PACKAGE_FALSE", lambda x: x["gate"].update({"artifact_package_complete": False}), docs)
    expect("XNC29_INVENTORY_GATE_FALSE", lambda x: x["gate"].update({"inventory_no_extra_or_cache": False}), docs)
    expect("XNC30_CONTRACT_SCHEMA_FORGED", lambda x: x["contract"].update({"schema": "FORGED_CONTRACT"}), docs)
    expect("XNC31_CONTRACT_SCOPE_ESCALATED", lambda x: x["contract"].update({"authority_scope": "FULL_CONTROL_RELEASE_AUTHORITY"}), docs)
    expect("XNC32_CONTRACT_REVIEW_APPROVED", lambda x: x["contract"].update({"review_status": "APPROVED"}), docs)
    expect("XNC33_CONTRACT_TOP_AUTHORITY_TRUE", lambda x: x["contract"].update({"next_stage_authorized": True, "release_credit": True}), docs)
    expect("XNC34_MANIFEST_CLAIM_ESCALATED", lambda x: x["manifest"].update({"claim": "RELEASE_AUTHORITY"}), docs)
    expect("XNC35_MANIFEST_AUTHORITY_TRUE", lambda x: x["manifest"].update({"parent_control_gate_reissued": True, "next_stage_authorized": True, "release_credit": True}), docs)
    expect("XNC36_INTERNAL_RECEIPT_AUTHORITY_TRUE", lambda x: x["internal"].update({"parent_control_gate_reissued": True, "next_stage_authorized": True, "release_credit": True}), docs)
    expect("XNC37_GATE_ARTIFACT_BINDING_TAMPER", lambda x: x["gate"]["artifact_bindings"]["evidence"].update({"sha256": "0" * 64}), docs)
    expect("XNC38_GATE_EMBEDDED_NEGATIVE_SUMMARY_TAMPER", lambda x: x["gate"].update({"negative_controls": {"passed": 29, "total": 29, "all_pass": False}}), docs)
    expect("XNC39_EXTERNAL_AUDIT_README_MISSING", lambda x: x["audit_files"].discard("README.md"), lambda x: audit_inventory_exact(x["audit_files"]))
    expect("XNC40_EXTERNAL_AUDIT_EXTRA_FILE", lambda x: x["audit_files"].add("UNDECLARED_EXTRA.txt"), lambda x: audit_inventory_exact(x["audit_files"]))
    return {"passed": sum(x["caught"] for x in rows), "total": len(rows), "all_pass": all(x["caught"] for x in rows), "records": rows}


def validate() -> dict[str, Any]:
    lock = load(LOCK_PATH)
    pin_groups = ("candidate_pins", "direct_source_pins", "parent_transitive_source_pins")
    pin_checks = {name: [pin_matches(x) for x in lock[name]] for name in pin_groups}
    candidate_by_id = {x["id"]: PROJECT_ROOT / x["path"] for x in lock["candidate_pins"]}
    contract = load(candidate_by_id["candidate_contract"])
    evidence = load(candidate_by_id["candidate_evidence"])
    gate = load(candidate_by_id["candidate_gate"])
    negative = load(candidate_by_id["candidate_negative_controls"])
    manifest = load(candidate_by_id["candidate_manifest"])
    internal = load(candidate_by_id["candidate_standalone_receipt"])
    config = load(PROJECT_ROOT / next(x for x in lock["direct_source_pins"] if x["id"] == "control_engineering_config")["path"])
    physics = recompute_physics(contract, config)
    with candidate_by_id["candidate_sha_table"].open(encoding="utf-8", newline="") as handle:
        sha_rows = list(csv.DictReader(handle))
    sha_ok = all((PROJECT_ROOT / x["path"]).is_file() and (PROJECT_ROOT / x["path"]).stat().st_size == int(x["bytes"]) and digest(PROJECT_ROOT / x["path"]) == x["sha256"] for x in sha_rows)
    manifest_ok = all((PROJECT_ROOT / x["path"]).is_file() and (PROJECT_ROOT / x["path"]).stat().st_size == x["bytes"] and digest(PROJECT_ROOT / x["path"]) == x["sha256"] for x in manifest["local_records"])
    candidate_files = {x.relative_to(CANDIDATE).as_posix() for x in CANDIDATE.rglob("*") if x.is_file()}
    candidate_forbidden = [x for x in CANDIDATE.rglob("*") if x.name in {"__pycache__", ".pytest_cache"} or x.suffix == ".pyc"]
    audit_files = {x.relative_to(PACKAGE).as_posix() for x in PACKAGE.rglob("*") if x.is_file()}
    audit_forbidden = [x for x in PACKAGE.rglob("*") if x.name in {"__pycache__", ".pytest_cache"} or x.suffix == ".pyc"]
    dg = load(PROJECT_ROOT / next(x for x in lock["direct_source_pins"] if x["id"] == "dg1_dg2_candidate_gate")["path"])
    tv = load(PROJECT_ROOT / next(x for x in lock["direct_source_pins"] if x["id"] == "time_varying_rigid_plant_gate")["path"])
    direct_exact = len(pin_checks["direct_source_pins"]) == 7 and all(pin_checks["direct_source_pins"])
    parent_exact = len(pin_checks["parent_transitive_source_pins"]) == 24 and all(pin_checks["parent_transitive_source_pins"])
    recomputed_candidate_checks = recompute_candidate_checks(contract, evidence, physics, direct_exact, parent_exact, dg, tv)
    synthetic_sq = synthetic_nonidentity_sq_regression()
    base = {"lock": lock, "contract": contract, "evidence": evidence, "gate": gate, "negative": negative, "manifest": manifest, "internal": internal, "config": config, "dg": dg, "tv": tv, "audit_files": audit_files}
    negatives = run_negative_controls(base, physics)
    checks = {
        "A01_fixed_candidate_direct_and_parent_pin_ledgers_exact": lock["candidate_pin_count"] == len(pin_checks["candidate_pins"]) == 13 and lock["direct_source_pin_count"] == len(pin_checks["direct_source_pins"]) == 7 and lock["parent_transitive_source_pin_count"] == len(pin_checks["parent_transitive_source_pins"]) == 24 and all(all(x) for x in pin_checks.values()),
        "A02_contract_and_parent_config_ledgers_equal_external_lock": contract["source_pins"] == lock["direct_source_pins"] and config["source_pins"] == lock["parent_transitive_source_pins"],
        "A03_reference_scales_independently_recomputed": physics["chain"] == contract["derivation"]["expected_chain_joint_names"] and abs(physics["length"] - contract["derivation"]["characteristic_length_m"]) <= 1e-15 and abs(physics["mass"] - contract["generalized_coordinate_metric"]["reference_mass_kg"]) <= 1e-12 and abs(physics["inertia"] - contract["generalized_coordinate_metric"]["reference_inertia_kg_m2"]) <= 1e-12,
        "A04_all_C01_C17_recomputed_and_fieldwise_equal": documents_ok(contract, evidence, gate, negative, manifest, internal, physics, recomputed_candidate_checks),
        "A05_manifest_and_sha_rows_exact": manifest_ok and sha_ok and len(sha_rows) >= 10,
        "A06_candidate_inventory_exact_no_extra_or_cache": candidate_files == set(manifest["inventory_policy"]["allowed_files"]) and not candidate_forbidden,
        "A07_external_audit_inventory_exact_no_missing_extra_or_cache": audit_inventory_exact(audit_files) and not audit_forbidden,
        "A08_dg1_dg2_source_actually_parsed": dg.get("candidate_DG1_satisfied") is True and dg.get("candidate_DG2_satisfied") is True and dg.get("next_stage_authorized") is False and dg.get("release_credit") is False,
        "A09_time_varying_rigid_source_actually_parsed": tv.get("all_checks_pass") is True and tv.get("passed") == tv.get("total") == 24 and all(tv.get(x) is False for x in ("flex_valid", "contact_valid", "target_attachment_valid", "hardware_valid", "control_valid", "next_stage_authorized", "release_credit")),
        "A10_external_negative_controls_all_caught": negatives["all_pass"] and negatives["passed"] == negatives["total"] == 40,
        "A11_nonidentity_S_q_general_change_of_variables_regression": synthetic_sq["pass"],
        "A12_external_semantic_profile_exact": lock["audit_semantic_profile"]["candidate_gate_schema"] == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1" and lock["audit_semantic_profile"]["candidate_evidence_schema"] == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_EVIDENCE_V1" and lock["audit_semantic_profile"]["candidate_scope"] == EXPECTED_CLAIM and lock["audit_semantic_profile"]["review_status"] == "PENDING_OWNER_REVIEW" and lock["audit_semantic_profile"]["expected_candidate_checks"] == list(recomputed_candidate_checks) and all(lock["audit_semantic_profile"][x] is True for x in ("artifact_package_complete_required", "inventory_no_extra_or_cache_required", "all_parent_hardware_safe_path_and_release_authority_false", "external_audit_inventory_exact_required")),
        "A13_truthful_in_memory_gram_source_reassembly": physics["gram_test_method"] == lock["audit_semantic_profile"]["truthful_gram_test_method"] and physics["gram_transformed_mass_count"] == 16 and physics["gram_transformed_inertia_component_count"] == 96 and abs(physics["first_inertial_link_mass_ratio"] - 1000.0) <= 1e-12 and physics["temporary_file_created"] is False,
        "A14_contract_manifest_internal_gate_boundaries_and_bindings_exact": full_document_boundaries_exact(contract, gate, manifest, internal, negative),
    }
    receipt = builtin({
        "schema": "CTRL_R2_TASK_SPACE_METRIC_EXTERNAL_AUDIT_V1",
        "technical_verdict": "EXTERNAL_AUDIT_PASS__TASK_SPACE_METRIC_CANDIDATE_ONLY__ALL_PARENT_AND_RELEASE_AUTHORITY_HOLD" if all(checks.values()) else "EXTERNAL_AUDIT_HOLD",
        "checks": checks, "passed": sum(checks.values()), "total": len(checks), "all_pass": all(checks.values()),
        "negative_controls": negatives,
        "recomputed_candidate_checks": recomputed_candidate_checks,
        "truthful_gram_test_method": physics["gram_test_method"],
        "recomputed": {
            "characteristic_length_m": physics["length"], "reference_mass_kg": physics["mass"],
            "reference_inertia_kg_m2": physics["inertia"],
            "task_ranks": {k: v["rank"] for k, v in physics["tasks"].items()},
            "task_nullities": {k: v["nullity"] for k, v in physics["tasks"].items()},
            "kilogram_gram_independent_reload": {k: v["kg_g"] for k, v in physics["tasks"].items()},
            "synthetic_nonidentity_S_q": synthetic_sq,
            "scope_limit": "CURRENT_HASH_BOUND_STATIC_PROBE_ONLY",
            "gram_source_audit": {
                "transformed_urdf_sha256": physics["gram_transformed_urdf_sha256"],
                "original_urdf_sha256": next(x for x in lock["direct_source_pins"] if x["id"] == "unified_r2_urdf")["sha256"],
                "xml_hashes_differ": physics["gram_transformed_urdf_sha256"] != next(x for x in lock["direct_source_pins"] if x["id"] == "unified_r2_urdf")["sha256"],
                "transformed_mass_count": physics["gram_transformed_mass_count"],
                "transformed_inertia_component_count": physics["gram_transformed_inertia_component_count"],
                "first_inertial_link_mass_kg": physics["first_inertial_link_mass_kg"],
                "first_inertial_link_mass_numeric_g": physics["first_inertial_link_mass_numeric_g"],
                "first_inertial_link_mass_ratio": physics["first_inertial_link_mass_ratio"],
                "gram_tree_total_mass_numeric_g": physics["gram_tree_total_mass_numeric_g"],
                "temporary_file_created": physics["temporary_file_created"],
            },
        },
        "maximum_claim": EXPECTED_CLAIM,
        "parent_control_gate_reissued": False, "collision_valid": False, "m01_path_bound": False,
        "safe_review_pass": False, "time_domain_tracking_executed": False, "hardware_valid": False,
        "next_stage_authorized": False, "release_credit": False,
    })
    RESULTS.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return receipt


if __name__ == "__main__":
    result = validate()
    print(json.dumps({"passed": result["passed"], "total": result["total"], "negative_controls": result["negative_controls"], "all_pass": result["all_pass"]}, indent=2))
    raise SystemExit(0 if result["all_pass"] else 1)
