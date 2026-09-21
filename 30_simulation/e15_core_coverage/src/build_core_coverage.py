"""Build a deterministic, read-only P0-A core evidence map from frozen E1.5 rows.

This program never runs a flexible solver.  Geometry-invalid candidates retain
explicit NOT_APPLICABLE downstream fields instead of zero-filled physics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
DEFAULT_CONFIG = REPO_ROOT / "30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "30_simulation" / "e15_core_coverage"

SCHEMA_VERSION = "e15-core-coverage-v1"
ALLOWED_STATES = {
    "CORE_SAFE_FLEX_VALIDATED",
    "CORE_SAFE_FLEX_UNKNOWN",
    "CORE_UNSAFE",
    "GEOMETRY_INVALID",
    "EVIDENCE_MISSING",
}

FIELDNAMES = [
    "grid_index", "case_id", "target_id", "grasp_point_id", "t_c_s",
    "v_app_mps", "task_constraint_mode", "capture_mode", "chaser_mode",
    "selected_roll_angle_deg", "geometry_group_key", "scenario_hash",
    "full_scenario_hash", "e15_case_hash", "source_commit",
    "source_results_sha256", "source_schema_version", "core_schema_version",
    "threshold_registry_version", "threshold_registry_sha256",
    "geometry_stage_status", "collision_stage_status",
    "base_reaction_stage_status", "capture_impulse_stage_status",
    "post_capture_stage_status", "actuator_budget_stage_status",
    "flex_stage_status", "downstream_numeric_semantics",
    "geometry_input_valid", "geometry_chain_valid", "ik_feasible",
    "n_ik_solutions", "joint_limit_margin_rad",
    "joint_limit_margin_min_rad", "joint_limit_margin_pass",
    "jacobian_condition", "jacobian_condition_max", "jacobian_condition_pass",
    "collision_margin_m", "collision_margin_min_limit_m", "collision_margin_pass",
    "base_attitude_change_deg", "base_attitude_change_max_deg",
    "base_attitude_change_pass", "base_angular_velocity_metric_dps",
    "capture_impulse_linear_x_Ns", "capture_impulse_linear_y_Ns",
    "capture_impulse_linear_z_Ns", "capture_impulse_linear_norm_Ns",
    "capture_impulse_angular_x_Nms", "capture_impulse_angular_y_Nms",
    "capture_impulse_angular_z_Nms", "capture_impulse_angular_norm_Nms",
    "lock_impulse_linear_norm_Ns", "lock_impulse_angular_norm_Nms",
    "net_target_impulse_linear_norm_Ns", "net_target_impulse_angular_norm_Nms",
    "post_capture_angular_velocity_dps", "post_capture_rate_max_dps",
    "post_capture_rate_pass", "wheel_momentum_required_Nms",
    "wheel_momentum_max_Nms", "wheel_momentum_pass",
    "thruster_impulse_required_Ns", "thruster_impulse_max_Ns",
    "thruster_impulse_pass", "propellant_required_g",
    "propellant_budget_max_g", "propellant_budget_pass",
    "flex_status", "flex_safety_evaluation_eligible", "flex_energy_J",
    "flex_energy_max_J", "flex_energy_pass", "core_chain_applicable",
    "core_numeric_complete", "evidence_missing", "evidence_status",
    "not_applicable_reason", "core_state", "primary_binding_cause",
    "binding_metric", "binding_value", "binding_limit", "binding_relation",
    "binding_margin", "threshold_source_version", "solver_provenance_json",
    "row_deterministic_hash",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _float(row: dict[str, str], name: str) -> float:
    text = row.get(name, "")
    if text == "":
        raise ValueError(f"{row.get('case_id')}: missing {name}")
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"{row.get('case_id')}: non-finite {name}")
    return value


def _norm(vec: list[float]) -> float:
    if len(vec) != 3 or not all(math.isfinite(float(v)) for v in vec):
        raise ValueError(f"invalid 3-vector: {vec!r}")
    return math.sqrt(sum(float(v) ** 2 for v in vec))


def _close(a: float, b: float, tol: float = 1.0e-10) -> None:
    if not math.isclose(a, b, rel_tol=tol, abs_tol=tol):
        raise ValueError(f"numeric evidence mismatch: {a:.17g} != {b:.17g}")


def _threshold(config: dict[str, Any], name: str) -> float:
    return float(config["thresholds"][name]["value"])


def _blank_numeric(out: dict[str, Any]) -> None:
    for name in FIELDNAMES:
        if name in {
            "grid_index", "case_id", "target_id", "grasp_point_id", "t_c_s",
            "v_app_mps", "task_constraint_mode", "capture_mode", "chaser_mode",
            "selected_roll_angle_deg", "geometry_group_key", "scenario_hash",
            "full_scenario_hash", "e15_case_hash", "source_commit",
            "source_results_sha256", "source_schema_version", "core_schema_version",
            "threshold_registry_version", "threshold_registry_sha256",
            "geometry_stage_status", "collision_stage_status",
            "base_reaction_stage_status", "capture_impulse_stage_status",
            "post_capture_stage_status", "actuator_budget_stage_status",
            "flex_stage_status", "downstream_numeric_semantics",
            "geometry_input_valid", "geometry_chain_valid", "ik_feasible",
            "n_ik_solutions", "joint_limit_margin_min_rad", "jacobian_condition_max",
            "collision_margin_min_limit_m", "base_attitude_change_max_deg",
            "post_capture_rate_max_dps", "wheel_momentum_max_Nms",
            "thruster_impulse_max_Ns", "propellant_budget_max_g", "flex_energy_max_J",
            "core_chain_applicable", "core_numeric_complete", "evidence_missing",
            "evidence_status", "not_applicable_reason", "core_state",
            "primary_binding_cause", "binding_metric", "binding_value",
            "binding_limit", "binding_relation", "binding_margin",
            "threshold_source_version", "solver_provenance_json",
            "flex_status", "flex_safety_evaluation_eligible", "row_deterministic_hash",
        }:
            continue
        out.setdefault(name, "")


def _finalize_row(out: dict[str, Any]) -> dict[str, Any]:
    _blank_numeric(out)
    string_payload = {name: str(out.get(name, "")) for name in FIELDNAMES if name != "row_deterministic_hash"}
    out["row_deterministic_hash"] = _canonical_hash(string_payload)
    return out


def _base_row(
    source: dict[str, str], source_sha: str, config: dict[str, Any], config_sha: str
) -> dict[str, Any]:
    return {
        "grid_index": int(source["grid_index"]),
        "case_id": source["case_id"],
        "target_id": source["target_id"],
        "grasp_point_id": source["grasp_point_id"],
        "t_c_s": float(source["t_c_s"]),
        "v_app_mps": float(source["v_app_mps"]),
        "task_constraint_mode": source["task_constraint_mode"],
        "capture_mode": source["capture_mode"],
        "chaser_mode": source["chaser_mode"],
        "selected_roll_angle_deg": float(source["selected_roll_angle_deg"]),
        "geometry_group_key": source["geometry_group_key"],
        "scenario_hash": source["scenario_hash"],
        "full_scenario_hash": source["full_scenario_hash"],
        "e15_case_hash": source["e15_case_hash"],
        "source_commit": source["source_commit"],
        "source_results_sha256": source_sha,
        "source_schema_version": source["integration_schema_version"],
        "core_schema_version": SCHEMA_VERSION,
        "threshold_registry_version": config["schema_version"],
        "threshold_registry_sha256": config_sha,
        "geometry_input_valid": 1,
        "joint_limit_margin_min_rad": _threshold(config, "joint_limit_margin_min_rad"),
        "jacobian_condition_max": _threshold(config, "condition_number_max"),
        "collision_margin_min_limit_m": _threshold(config, "collision_margin_min_m"),
        "base_attitude_change_max_deg": _threshold(config, "base_attitude_change_max_deg"),
        "post_capture_rate_max_dps": _threshold(config, "post_capture_rate_max_dps"),
        "wheel_momentum_max_Nms": _threshold(config, "wheel_momentum_max_Nms"),
        "thruster_impulse_max_Ns": _threshold(config, "thruster_impulse_max_Ns"),
        "propellant_budget_max_g": _threshold(config, "propellant_budget_max_g"),
        "flex_energy_max_J": _threshold(config, "flexible_energy_max_J"),
        "threshold_source_version": "core-threshold-registry-v1|hard-constraints-v1|collision-v1",
        "solver_provenance_json": source["solver_provenance_json"],
    }


def _binding(
    cause: str, metric: str, value: float, limit: float, relation: str
) -> dict[str, Any]:
    margin = value - limit if relation == ">=" else limit - value
    return {
        "primary_binding_cause": cause,
        "binding_metric": metric,
        "binding_value": value,
        "binding_limit": limit,
        "binding_relation": relation,
        "binding_margin": margin,
    }


def _classify_row(
    source: dict[str, str], source_sha: str, config: dict[str, Any], config_sha: str
) -> dict[str, Any]:
    out = _base_row(source, source_sha, config, config_sha)
    out["ik_feasible"] = int(source["ik_feasible"])
    out["n_ik_solutions"] = int(source["n_ik_solutions"])
    out["flex_status"] = source["flex_status"]
    out["flex_safety_evaluation_eligible"] = int(source["flex_safety_evaluation_eligible"] or 0)

    if not out["ik_feasible"]:
        out.update({
            "geometry_stage_status": "FAILED_IK_UNREACHABLE",
            "collision_stage_status": "NOT_RUN_DUE_TO_UPSTREAM_IK",
            "base_reaction_stage_status": "NOT_RUN_DUE_TO_UPSTREAM_IK",
            "capture_impulse_stage_status": "NOT_RUN_DUE_TO_UPSTREAM_IK",
            "post_capture_stage_status": "NOT_RUN_DUE_TO_UPSTREAM_IK",
            "actuator_budget_stage_status": "NOT_RUN_DUE_TO_UPSTREAM_IK",
            "flex_stage_status": "NOT_RUN_DUE_TO_UPSTREAM_IK",
            "downstream_numeric_semantics": "NOT_APPLICABLE_NOT_MISSING",
            "geometry_chain_valid": 0,
            "core_chain_applicable": 0,
            "core_numeric_complete": 0,
            "evidence_missing": 0,
            "evidence_status": "COMPLETE_NOT_APPLICABLE_AFTER_IK",
            "not_applicable_reason": "GEOMETRY_CHAIN_FAILED_AT_IK",
            "core_state": "GEOMETRY_INVALID",
        })
        out.update(_binding("IK_UNREACHABLE", "ik_feasible", 0.0, 1.0, ">="))
        return _finalize_row(out)

    required = [
        "joint_limit_margin_rad", "condition_number", "collision_margin_min_m",
        "base_attitude_change_deg", "base_rate_peak_dps", "Jt_norm_Ns",
        "Lgrasp_norm_Nms", "Jlock_norm_Ns", "Llock_norm_Nms", "Jnet_norm_Ns",
        "Lnet_norm_Nms", "post_capture_rate_dps", "H_RW_Nms", "J_thr_Ns", "m_prop_g",
    ]
    missing = [name for name in required if source.get(name, "") == ""]
    if missing:
        out.update({
            "geometry_stage_status": "PASSED_IK_BUT_CORE_FIELDS_MISSING",
            "collision_stage_status": "EVIDENCE_MISSING",
            "base_reaction_stage_status": "EVIDENCE_MISSING",
            "capture_impulse_stage_status": "EVIDENCE_MISSING",
            "post_capture_stage_status": "EVIDENCE_MISSING",
            "actuator_budget_stage_status": "EVIDENCE_MISSING",
            "flex_stage_status": "SOURCE_STATUS_" + source["flex_status"],
            "downstream_numeric_semantics": "MISSING_REQUIRED_EVIDENCE",
            "geometry_chain_valid": 0,
            "core_chain_applicable": 1,
            "core_numeric_complete": 0,
            "evidence_missing": 1,
            "evidence_status": "MISSING_REQUIRED_CORE_NUMERICS",
            "not_applicable_reason": "",
            "core_state": "EVIDENCE_MISSING",
            "primary_binding_cause": "MISSING_CORE_FIELDS:" + ";".join(missing),
            "binding_metric": missing[0],
            "binding_value": "",
            "binding_limit": "",
            "binding_relation": "required",
            "binding_margin": "",
        })
        return _finalize_row(out)

    contact = json.loads(source["initial_contact_wrench_json"])
    jt = [float(v) for v in contact["J_t_Ns"]]
    lt = [float(v) for v in contact["L_grasp_Nms"]]
    jt_norm = _norm(jt)
    lt_norm = _norm(lt)
    _close(jt_norm, _float(source, "Jt_norm_Ns"))
    _close(lt_norm, _float(source, "Lgrasp_norm_Nms"))

    lever = float(config["actuator_model"]["lever_m"])
    isp = float(config["actuator_model"]["isp_s"])
    g0 = float(config["actuator_model"]["g0_mps2"])
    h_rw = _float(source, "H_RW_Nms")
    j_thr = h_rw / lever
    propellant = 1000.0 * j_thr / (isp * g0)
    _close(j_thr, _float(source, "J_thr_Ns"))
    _close(propellant, _float(source, "m_prop_g"))

    joint = _float(source, "joint_limit_margin_rad")
    cond = _float(source, "condition_number")
    collision = _float(source, "collision_margin_min_m")
    theta = _float(source, "base_attitude_change_deg")
    base_rate = _float(source, "base_rate_peak_dps")
    post_rate = _float(source, "post_capture_rate_dps")

    out.update({
        "geometry_stage_status": "VERIFIED_FROM_FROZEN_E15",
        "collision_stage_status": "VERIFIED_NUMERIC",
        "base_reaction_stage_status": "VERIFIED_NUMERIC",
        "capture_impulse_stage_status": "VERIFIED_6D_NUMERIC",
        "post_capture_stage_status": "VERIFIED_NUMERIC",
        "actuator_budget_stage_status": "VERIFIED_DERIVED_NUMERIC",
        "flex_stage_status": "SOURCE_STATUS_" + source["flex_status"],
        "downstream_numeric_semantics": "NUMERIC_EVIDENCE_PRESENT",
        "joint_limit_margin_rad": joint,
        "joint_limit_margin_pass": int(joint >= out["joint_limit_margin_min_rad"]),
        "jacobian_condition": cond,
        "jacobian_condition_pass": int(cond <= out["jacobian_condition_max"]),
        "collision_margin_m": collision,
        "collision_margin_pass": int(collision >= out["collision_margin_min_limit_m"]),
        "base_attitude_change_deg": theta,
        "base_attitude_change_pass": int(theta <= out["base_attitude_change_max_deg"]),
        "base_angular_velocity_metric_dps": base_rate,
        "capture_impulse_linear_x_Ns": jt[0],
        "capture_impulse_linear_y_Ns": jt[1],
        "capture_impulse_linear_z_Ns": jt[2],
        "capture_impulse_linear_norm_Ns": jt_norm,
        "capture_impulse_angular_x_Nms": lt[0],
        "capture_impulse_angular_y_Nms": lt[1],
        "capture_impulse_angular_z_Nms": lt[2],
        "capture_impulse_angular_norm_Nms": lt_norm,
        "lock_impulse_linear_norm_Ns": _float(source, "Jlock_norm_Ns"),
        "lock_impulse_angular_norm_Nms": _float(source, "Llock_norm_Nms"),
        "net_target_impulse_linear_norm_Ns": _float(source, "Jnet_norm_Ns"),
        "net_target_impulse_angular_norm_Nms": _float(source, "Lnet_norm_Nms"),
        "post_capture_angular_velocity_dps": post_rate,
        "post_capture_rate_pass": int(post_rate <= out["post_capture_rate_max_dps"]),
        "wheel_momentum_required_Nms": h_rw,
        "wheel_momentum_pass": int(h_rw <= out["wheel_momentum_max_Nms"]),
        "thruster_impulse_required_Ns": j_thr,
        "thruster_impulse_pass": int(j_thr <= out["thruster_impulse_max_Ns"]),
        "propellant_required_g": propellant,
        "propellant_budget_pass": int(propellant <= out["propellant_budget_max_g"]),
        "core_chain_applicable": 1,
        "core_numeric_complete": 1,
        "evidence_missing": 0,
        "evidence_status": "COMPLETE_CORE_CHAIN",
        "not_applicable_reason": "",
    })

    geometry_failures = []
    if not out["collision_margin_pass"]:
        geometry_failures.append(_binding("COLLISION_MARGIN_BELOW_LIMIT", "collision_margin_m", collision, out["collision_margin_min_limit_m"], ">="))
    if not out["joint_limit_margin_pass"]:
        geometry_failures.append(_binding("JOINT_LIMIT_MARGIN_BELOW_LIMIT", "joint_limit_margin_rad", joint, out["joint_limit_margin_min_rad"], ">="))
    if not out["jacobian_condition_pass"]:
        geometry_failures.append(_binding("JACOBIAN_CONDITION_EXCEEDS_LIMIT", "jacobian_condition", cond, out["jacobian_condition_max"], "<="))

    out["geometry_chain_valid"] = int(not geometry_failures)
    if geometry_failures:
        out["core_state"] = "GEOMETRY_INVALID"
        out.update(geometry_failures[0])
    else:
        core_failures = []
        if not out["base_attitude_change_pass"]:
            core_failures.append(_binding("BASE_ATTITUDE_CHANGE_EXCEEDS_LIMIT", "base_attitude_change_deg", theta, out["base_attitude_change_max_deg"], "<="))
        if not out["post_capture_rate_pass"]:
            core_failures.append(_binding("POST_CAPTURE_RATE_EXCEEDS_LIMIT", "post_capture_angular_velocity_dps", post_rate, out["post_capture_rate_max_dps"], "<="))
        if not out["wheel_momentum_pass"]:
            core_failures.append(_binding("WHEEL_MOMENTUM_EXCEEDS_LIMIT", "wheel_momentum_required_Nms", h_rw, out["wheel_momentum_max_Nms"], "<="))

        flex_eligible = bool(out["flex_safety_evaluation_eligible"])
        if flex_eligible:
            flex_energy = _float(source, "E_flex_J")
            out["flex_energy_J"] = flex_energy
            out["flex_energy_pass"] = int(flex_energy <= out["flex_energy_max_J"])
            if not out["flex_energy_pass"]:
                core_failures.append(_binding("FLEX_ENERGY_EXCEEDS_LIMIT", "flex_energy_J", flex_energy, out["flex_energy_max_J"], "<="))
        else:
            out["flex_energy_J"] = ""
            out["flex_energy_pass"] = ""

        if core_failures:
            out["core_state"] = "CORE_UNSAFE"
            out.update(core_failures[0])
        elif flex_eligible:
            out["core_state"] = "CORE_SAFE_FLEX_VALIDATED"
            out.update(_binding("NONE_CORE_CLEAR", "all_independent_core_gates", 1.0, 1.0, ">="))
        else:
            out["core_state"] = "CORE_SAFE_FLEX_UNKNOWN"
            out.update(_binding("FLEX_NOT_VALIDATED", "flex_safety_evaluation_eligible", 0.0, 1.0, ">="))

    if out["core_state"] not in ALLOWED_STATES:
        raise ValueError(f"invalid state {out['core_state']}")
    return _finalize_row(out)


def build(config_path: Path, output_root: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    output_root = output_root.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_sha = _sha256(config_path)
    source_path = REPO_ROOT / config["source_evidence"]["path"]
    source_sha = _sha256(source_path)
    expected_source_sha = str(config["source_evidence"]["sha256"]).lower()
    if source_sha != expected_source_sha:
        raise ValueError(f"frozen source hash mismatch: {source_sha} != {expected_source_sha}")

    with source_path.open("r", encoding="utf-8", newline="") as f:
        source_rows = list(csv.DictReader(f))
    if len(source_rows) != 72:
        raise ValueError(f"expected 72 source rows, got {len(source_rows)}")
    if [int(row["grid_index"]) for row in source_rows] != list(range(72)):
        raise ValueError("source grid_index must be exactly 0..71")
    if len({row["case_id"] for row in source_rows}) != 72:
        raise ValueError("source case_id values are not unique")

    rows = [_classify_row(row, source_sha, config, config_sha) for row in source_rows]
    results_path = output_root / "results/core_evidence_72cases.csv"
    _csv(results_path, FIELDNAMES, rows)

    state_counts = Counter(str(row["core_state"]) for row in rows)
    all_state_counts = {state: state_counts.get(state, 0) for state in sorted(ALLOWED_STATES)}
    cause_counts = Counter(str(row["primary_binding_cause"]) for row in rows)
    status_rows = [{"core_state": state, "count": state_counts.get(state, 0)} for state in sorted(ALLOWED_STATES)]
    cause_rows = [{"primary_binding_cause": cause, "count": count} for cause, count in sorted(cause_counts.items())]
    threshold_rows = []
    for name, item in config["thresholds"].items():
        threshold_rows.append({
            "metric": name,
            "value": item["value"],
            "unit": item["unit"],
            "relation": item["relation"],
            "source_type": item["source_type"],
            "source": item["source"],
            "verification_status": item["verification_status"],
        })
    _csv(output_root / "tables/status_summary.csv", ["core_state", "count"], status_rows)
    _csv(output_root / "tables/primary_binding_summary.csv", ["primary_binding_cause", "count"], cause_rows)
    _csv(
        output_root / "tables/threshold_registry_flat.csv",
        ["metric", "value", "unit", "relation", "source_type", "source", "verification_status"],
        threshold_rows,
    )

    evidence_missing = state_counts.get("EVIDENCE_MISSING", 0)
    unique_primary = all(bool(row["primary_binding_cause"]) and ";" not in str(row["primary_binding_cause"]) for row in rows)
    gate_pass = len(rows) == 72 and evidence_missing == 0 and unique_primary
    artifact_paths = [
        results_path,
        output_root / "tables/status_summary.csv",
        output_root / "tables/primary_binding_summary.csv",
        output_root / "tables/threshold_registry_flat.csv",
    ]
    artifacts = {path.relative_to(output_root).as_posix(): _sha256(path) for path in artifact_paths}
    manifest = {
        "schema_version": "e15-core-run-manifest-v1",
        "generation_mode": "DETERMINISTIC_NO_RUNTIME_TIMESTAMP",
        "source_results": config["source_evidence"]["path"],
        "source_results_sha256": source_sha,
        "threshold_registry_sha256": config_sha,
        "row_count": len(rows),
        "row_hash_chain_sha256": _canonical_hash([row["row_deterministic_hash"] for row in rows]),
        "artifacts": artifacts,
        "ancf_executed": False,
    }
    manifest_path = output_root / "results/core_run_manifest.json"
    _json(manifest_path, manifest)
    gate = {
        "schema_version": "e15-core-gate-v1",
        "gate": "P0_A_CORE_COVERAGE_PASS" if gate_pass else "P0_A_CORE_COVERAGE_FAIL",
        "row_count": len(rows),
        "case_id_unique_count": len({row["case_id"] for row in rows}),
        "state_counts": all_state_counts,
        "primary_binding_counts": dict(sorted(cause_counts.items())),
        "evidence_missing_count": evidence_missing,
        "unique_primary_binding_per_row": unique_primary,
        "all_geometry_invalid_rows_explicitly_not_applicable": all(
            row["not_applicable_reason"] == "GEOMETRY_CHAIN_FAILED_AT_IK"
            for row in rows if row["core_state"] == "GEOMETRY_INVALID"
        ),
        "core_numeric_rows": sum(int(row["core_numeric_complete"]) for row in rows),
        "ancf_executed": False,
        "threshold_registry_status": config["registry_status"],
        "thresholds_widened": False,
        "safe_candidate_count": state_counts.get("CORE_SAFE_FLEX_VALIDATED", 0) + state_counts.get("CORE_SAFE_FLEX_UNKNOWN", 0),
        "next_stage_authorized": False,
        "scientific_verdict": "REPEAT_CORE_NO_SAFE_CANDIDATE" if gate_pass and not (
            state_counts.get("CORE_SAFE_FLEX_VALIDATED", 0) + state_counts.get("CORE_SAFE_FLEX_UNKNOWN", 0)
        ) else "CORE_COVERAGE_REVIEW_REQUIRED",
        "source_results_sha256": source_sha,
        "threshold_registry_sha256": config_sha,
        "manifest_sha256": _sha256(manifest_path),
    }
    _json(output_root / "results/core_gate_check.json", gate)
    return gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    gate = build(args.config, args.output_root)
    print(json.dumps(gate, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
