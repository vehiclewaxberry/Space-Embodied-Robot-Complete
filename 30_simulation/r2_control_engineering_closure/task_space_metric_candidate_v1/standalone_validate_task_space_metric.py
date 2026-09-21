"""Standalone-internal validator for the task-space metric candidate.

This validator does not import the candidate implementation.  It is still an
internal package artifact, not an independent audit authority; the sibling
external-audit package provides the immutable outside source lock.
"""
from __future__ import annotations

import csv
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
CONTRACT = PACKAGE / "contracts" / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_CONTRACT_V1.json"
RESULTS = PACKAGE / "results"
RECEIPT = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_STANDALONE_INTERNAL_VALIDATION_V1.json"
EXPECTED_VERDICT = "TASK_SPACE_METRIC_CANDIDATE_PASS__PARENT_CONTROL_TIME_DOMAIN_MECHANICAL_HARDWARE_AND_SAFE_HOLD"
EXPECTED_CLAIM = "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY"
EXPECTED_FALSE_GATE = (
    "parent_control_gate_reissued", "precontact_tracking_validated",
    "time_domain_tracking_executed", "m01_path_bound", "collision_valid",
    "hardware_valid", "safe_review_pass", "next_stage_authorized", "release_credit",
)
EXPECTED_FILES = {
    "README.md",
    "build_task_space_metric_candidate.py",
    "standalone_validate_task_space_metric.py",
    "contracts/CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_CONTRACT_V1.json",
    "src/__init__.py",
    "src/task_space_metric.py",
    "tests/test_task_space_metric.py",
    "results/CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_EVIDENCE_V1.json",
    "results/CTRL_R2_TASK_SPACE_METRIC_NEGATIVE_CONTROL_RESULTS_V1.json",
    "results/CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_MANIFEST_V1.json",
    "results/CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1.json",
    "results/CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_SHA256_V1.csv",
    "results/CTRL_R2_TASK_SPACE_METRIC_STANDALONE_INTERNAL_VALIDATION_V1.json",
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


def close(a: Any, b: Any, atol: float = 2.0e-12) -> bool:
    aa = np.asarray(a, dtype=float)
    bb = np.asarray(b, dtype=float)
    return aa.shape == bb.shape and bool(np.allclose(aa, bb, atol=atol, rtol=2.0e-13))


def source_closure(contract: dict[str, Any]) -> dict[str, Any]:
    direct = []
    for pin in contract["source_pins"]:
        path = PROJECT_ROOT / pin["path"]
        direct.append(path.is_file() and path.stat().st_size == pin["bytes"] and digest(path) == pin["sha256"])
    config_pin = next(row for row in contract["source_pins"] if row["id"] == "control_engineering_config")
    config = load(PROJECT_ROOT / config_pin["path"])
    transitive = []
    for pin in config["source_pins"]:
        path = PROJECT_ROOT / pin["path"]
        transitive.append(path.is_file() and path.stat().st_size == pin["bytes"] and digest(path) == pin["sha256"])
    return {
        "direct_count": len(direct), "direct_all_match": len(direct) == 7 and all(direct),
        "parent_transitive_count": len(transitive),
        "parent_transitive_all_match": len(transitive) == 24 and all(transitive),
        "parent_config": config,
    }


def independent_physics(contract: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    urdf_pin = next(row for row in contract["source_pins"] if row["id"] == "unified_r2_urdf")
    root = ET.parse(PROJECT_ROOT / urdf_pin["path"]).getroot()
    by_child = {}
    for joint in root.findall("joint"):
        child = joint.find("child").attrib["link"]
        if child in by_child:
            raise ValueError("URDF_MULTIPLE_PARENT")
        by_child[child] = joint
    link = contract["derivation"]["tool_link"]
    chain = []
    while link != contract["derivation"]["root_link"]:
        joint = by_child[link]
        origin = joint.find("origin")
        xyz = np.asarray([float(x) for x in (origin.attrib.get("xyz", "0 0 0") if origin is not None else "0 0 0").split()])
        chain.append((joint.attrib["name"], float(np.linalg.norm(xyz))))
        link = joint.find("parent").attrib["link"]
    chain.reverse()
    length = float(math.fsum(x[1] for x in chain))
    masses = []
    for item in root.findall("link"):
        node = item.find("inertial/mass")
        if node is not None:
            mass = float(node.attrib["value"])
            if not math.isfinite(mass) or mass <= 0.0:
                raise ValueError("URDF_MASS_INVALID")
            masses.append(mass)
    reference_mass = float(math.fsum(masses))
    reference_inertia = reference_mass * length * length

    control_pin = next(row for row in contract["source_pins"] if row["id"] == "control_engineering_source")
    spec = importlib.util.spec_from_file_location("metric_standalone_parent", PROJECT_ROOT / control_pin["path"])
    if spec is None or spec.loader is None:
        raise ValueError("PARENT_IMPORT_FAILED")
    parent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parent)
    parent._install_unified_imports(PROJECT_ROOT)
    from sim13_v2_backends.dynamics_backend import UnifiedR2DynamicsBackend

    backend = UnifiedR2DynamicsBackend(project_root=PROJECT_ROOT)
    q = np.asarray(contract["diagnostic_state"]["q8_mixed_rad_m"], dtype=float)
    transform, fixed, generalized, connection = parent._tool_jacobians(backend, q, "gripper_link")
    mass6 = np.asarray(backend.reduced_mass_matrix(q), dtype=float)[:6, :6]
    axis = transform[:3, 2]
    basis = parent._approach_plane_basis(axis)
    axis_map = -parent._skew(axis)
    task_matrices = {
        "FAR_APPROACH_5D": (
            np.vstack((fixed[:3, :6], basis @ axis_map @ fixed[3:, :6])),
            np.vstack((generalized[:3, :6], basis @ axis_map @ generalized[3:, :6])),
        ),
        "FINAL_ALIGNMENT_6D": (fixed[:, :6], generalized[:, :6]),
    }
    tasks = {}
    for name, (fixed_j, general_j) in task_matrices.items():
        dim = general_j.shape[0]
        weight = np.diag(np.r_[np.full(3, 1.0 / length), np.ones(dim - 3)])
        jbar = weight @ general_j
        desired_bar = weight @ np.asarray(config["diagnostic_task_twists"][name]["value"], dtype=float)
        mbar = mass6 / reference_inertia
        mbar_inv = np.linalg.inv(mbar)
        lam = float(contract["dls"]["lambda_dimensionless"])
        normal = jbar @ mbar_inv @ jbar.T + lam * lam * np.eye(dim)
        qdot = mbar_inv @ jbar.T @ np.linalg.solve(normal, desired_bar)
        singular = np.linalg.svd(jbar, compute_uv=False)
        rank = int(np.sum(singular > float(contract["dls"]["rank_rtol"]) * singular[0]))
        tasks[name] = {
            "metric_diagonal": np.diag(weight), "weighted_generalized": jbar,
            "weighted_desired": desired_bar, "normalized_mass": mbar,
            "normal": normal, "qdot": qdot,
            "residual": float(np.linalg.norm(jbar @ qdot - desired_bar)),
            "base_angular": float(np.linalg.norm((connection[:, :6] @ qdot)[3:])),
            "singular": singular, "rank": rank,
        }
    return {
        "chain_names": [x[0] for x in chain], "length": length,
        "reference_mass": reference_mass, "reference_inertia": reference_inertia,
        "inertial_link_count": len(masses), "tasks": tasks,
    }


def validate() -> dict[str, Any]:
    contract = load(CONTRACT)
    evidence_path = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_EVIDENCE_V1.json"
    negative_path = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_NEGATIVE_CONTROL_RESULTS_V1.json"
    manifest_path = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_MANIFEST_V1.json"
    gate_path = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1.json"
    sha_path = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_SHA256_V1.csv"
    evidence, negative, manifest, gate = map(load, (evidence_path, negative_path, manifest_path, gate_path))
    closure = source_closure(contract)
    physics = independent_physics(contract, closure["parent_config"])
    manifest_checks = []
    for row in manifest["local_records"]:
        path = PROJECT_ROOT / row["path"]
        manifest_checks.append(path.is_file() and path.stat().st_size == row["bytes"] and digest(path) == row["sha256"])
    with sha_path.open(encoding="utf-8", newline="") as handle:
        sha_rows = list(csv.DictReader(handle))
    sha_checks = []
    for row in sha_rows:
        path = PROJECT_ROOT / row["path"]
        sha_checks.append(path.is_file() and path.stat().st_size == int(row["bytes"]) and digest(path) == row["sha256"])
    task_checks = []
    for row in evidence["tasks"]:
        recomputed = physics["tasks"][row["task"]]
        audit = row["free_floating_mass_weighted"]["dimensionless_dls_audit"]
        kg_g = row["free_floating_mass_weighted"]["kilogram_gram_reparameterization"]
        task_checks.append(all((
            close(row["metric_diagonal"], recomputed["metric_diagonal"]),
            row["guard"]["rank"] == recomputed["rank"],
            close(row["guard"]["singular_values_dimensionless"], recomputed["singular"]),
            close(audit["normalized_mass_matrix"], recomputed["normalized_mass"]),
            close(audit["normalized_jacobian"], recomputed["weighted_generalized"]),
            close(audit["dimensionless_normal_matrix"], recomputed["normal"]),
            close(row["free_floating_mass_weighted"]["joint_rate_rad_s"], recomputed["qdot"]),
            abs(row["free_floating_mass_weighted"]["actual_weighted_task_residual_per_s"] - recomputed["residual"]) <= 2e-12,
            abs(row["free_floating_mass_weighted"]["predicted_base_angular_rate_norm_rad_s"] - recomputed["base_angular"]) <= 2e-12,
            kg_g["pass"] is True,
            kg_g["joint_rate_max_abs_rad_s"] <= contract["thresholds"]["kilogram_gram_joint_rate_max_abs_rad_s"],
            kg_g["normal_matrix_max_abs"] <= contract["thresholds"]["kilogram_gram_normal_matrix_max_abs"],
            kg_g["normal_matrix_max_relative"] <= contract["thresholds"]["kilogram_gram_normal_matrix_max_relative"],
            kg_g["normalization_path"] == "COMMON_UNIT_SCALE_CANCELLED_BEFORE_INVERSION__SHARED_DIMENSIONLESS_M_BAR",
            row["command_emitted"] is False and row["time_domain_tracking_executed"] is False,
        )))
    actual_files = {
        path.relative_to(PACKAGE).as_posix() for path in PACKAGE.rglob("*") if path.is_file()
    }
    forbidden = [x for x in PACKAGE.rglob("*") if x.name in {"__pycache__", ".pytest_cache"} or x.suffix == ".pyc"]
    dg = load(PROJECT_ROOT / next(x for x in contract["source_pins"] if x["id"] == "dg1_dg2_candidate_gate")["path"])
    tv = load(PROJECT_ROOT / next(x for x in contract["source_pins"] if x["id"] == "time_varying_rigid_plant_gate")["path"])
    evidence_false = ("parent_control_gate_reissued", "precontact_tracking_validated", "time_domain_tracking_executed", "hardware_valid", "next_stage_authorized", "release_credit")
    checks = {
        "S01_direct_and_parent_24_pin_source_closure_exact": closure["direct_all_match"] and closure["parent_transitive_all_match"],
        "S02_chain_length_mass_inertia_independently_recomputed": physics["chain_names"] == contract["derivation"]["expected_chain_joint_names"] and abs(physics["length"] - contract["derivation"]["characteristic_length_m"]) <= contract["thresholds"]["characteristic_length_abs_m"] and abs(physics["reference_mass"] - contract["generalized_coordinate_metric"]["reference_mass_kg"]) <= contract["thresholds"]["reference_mass_abs_kg"] and abs(physics["reference_inertia"] - contract["generalized_coordinate_metric"]["reference_inertia_kg_m2"]) <= contract["thresholds"]["reference_inertia_abs_kg_m2"],
        "S03_all_task_evidence_numeric_fields_independently_match": len(task_checks) == 2 and all(task_checks),
        "S04_evidence_claim_and_authority_fields_exact": evidence["authority_scope"] == EXPECTED_CLAIM and evidence["candidate_metric_bound"] is True and len(evidence["checks"]) == 17 and all(evidence["checks"].values()) and all(evidence[x] is False for x in evidence_false),
        "S05_gate_verdict_claim_and_authority_fields_exact": gate["technical_verdict"] == EXPECTED_VERDICT and gate["maximum_claim"] == EXPECTED_CLAIM and gate["review_status"] == "PENDING_OWNER_REVIEW" and gate["candidate_metric_bound"] is True and gate["all_checks_pass"] is True and gate["passed"] == gate["total"] == 17 and all(gate[x] is False for x in EXPECTED_FALSE_GATE),
        "S06_gate_checks_match_evidence_checks_fieldwise": gate["checks"] == evidence["checks"] and len(gate["checks"]) == 17 and all(gate["checks"].values()),
        "S07_dg1_dg2_and_time_varying_sources_actually_parsed": dg.get("candidate_DG1_satisfied") is True and dg.get("candidate_DG2_satisfied") is True and dg.get("next_stage_authorized") is False and tv.get("passed") == tv.get("total") == 24 and tv.get("all_checks_pass") is True and all(tv.get(x) is False for x in ("flex_valid", "contact_valid", "target_attachment_valid", "hardware_valid", "control_valid", "next_stage_authorized", "release_credit")),
        "S08_negative_controls_fieldwise_closed": negative["all_pass"] is True and negative["passed"] == negative["total"] == len(negative["records"]) == 29 and all(x["caught"] is True and x["observed"] for x in negative["records"]),
        "S09_manifest_records_exact_and_authority_false": len(manifest_checks) == manifest["local_record_count"] == 9 and all(manifest_checks) and any(x["path"].endswith("/src/__init__.py") and x["role"] == "SOURCE_PACKAGE_INIT" for x in manifest["local_records"]) and manifest["claim"] == "HASH_BOUND_ADDITIVE_CANDIDATE_ONLY" and manifest["parent_control_gate_reissued"] is False and manifest["next_stage_authorized"] is False and manifest["release_credit"] is False,
        "S10_gate_artifact_bindings_exact": gate["artifact_bindings"]["evidence"]["sha256"] == digest(evidence_path) and gate["artifact_bindings"]["negative_controls"]["sha256"] == digest(negative_path) and gate["artifact_bindings"]["manifest"]["sha256"] == digest(manifest_path),
        "S11_sha_table_rows_exact": len(sha_rows) == len(sha_checks) and len(sha_rows) >= 10 and all(sha_checks),
        "S12_inventory_exact_no_extra_or_cache": actual_files <= EXPECTED_FILES and not forbidden,
    }
    receipt = {
        "schema": "CTRL_R2_TASK_SPACE_METRIC_STANDALONE_INTERNAL_VALIDATION_V1",
        "validator_class": "STANDALONE_INTERNAL__NOT_INDEPENDENT_AUTHORITY",
        "checks": checks, "passed": sum(checks.values()), "total": len(checks),
        "all_pass": all(checks.values()),
        "source_closure": {k: v for k, v in closure.items() if k != "parent_config"},
        "independent_recompute": {
            "chain_length_m": physics["length"], "reference_mass_kg": physics["reference_mass"],
            "reference_inertia_kg_m2": physics["reference_inertia"],
            "task_ranks": {k: v["rank"] for k, v in physics["tasks"].items()},
        },
        "candidate_evidence_sha256": digest(evidence_path), "candidate_gate_sha256": digest(gate_path),
        "candidate_manifest_sha256": digest(manifest_path), "candidate_sha_table_sha256": digest(sha_path),
        "parent_control_gate_reissued": False, "next_stage_authorized": False, "release_credit": False,
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return receipt


if __name__ == "__main__":
    result = validate()
    print(json.dumps({"passed": result["passed"], "total": result["total"], "all_pass": result["all_pass"]}, indent=2))
    raise SystemExit(0 if result["all_pass"] else 1)
