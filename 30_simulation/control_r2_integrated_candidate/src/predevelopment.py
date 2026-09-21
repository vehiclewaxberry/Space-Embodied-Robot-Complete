"""Deterministic, fail-closed helpers for CTRL_R2_PREDEVELOPMENT."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


MODULE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ROOT = MODULE_ROOT.parents[1]
CONFIG_PATH = MODULE_ROOT / "config" / "CTRL_R2_PREDEVELOPMENT_CONFIG_V1.json"
AUTHORITY_PATH = MODULE_ROOT / "contracts" / "CTRL_R2_PREDEVELOPMENT_AUTHORITY_V1.json"
RESULTS_DIR = MODULE_ROOT / "results"


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        out[key] = value
    return out


def load_json_strict(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def normalized_text_sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest().upper()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def validate_source_pins(repo_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    records = []
    for pin in config["source_pins"]:
        path = repo_root / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha256 = sha256_file(path) if exists else None
        match = (
            exists
            and actual_bytes == int(pin["bytes"])
            and actual_sha256 == pin["sha256"].upper()
        )
        actual_normalized_sha256 = (
            normalized_text_sha256(path)
            if exists and "normalized_sha256" in pin
            else None
        )
        if "normalized_sha256" in pin:
            match = match and actual_normalized_sha256 == pin["normalized_sha256"].upper()
        records.append(
            {
                **pin,
                "exists": exists,
                "actual_bytes": actual_bytes,
                "actual_sha256": actual_sha256,
                "actual_normalized_sha256": actual_normalized_sha256,
                "match": match,
            }
        )
    mismatches = [row["id"] for row in records if not row["match"]]
    return {
        "schema": "CTRL_R2_MODEL_BINDING_V1",
        "hash_mode": "RAW_BYTES_SHA256",
        "pin_count": len(records),
        "match_count": len(records) - len(mismatches),
        "hash_mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "pins": records,
        "pass": not mismatches,
    }


def _install_ctrl01_imports(repo_root: Path) -> None:
    ctrl_src = repo_root / "30_simulation" / "control_01_end_effector_tracking" / "src"
    value = str(ctrl_src)
    if value not in sys.path:
        sys.path.insert(0, value)


def _probe_once(repo_root: Path, probe_cfg: dict[str, Any]) -> dict[str, Any]:
    _install_ctrl01_imports(repo_root)
    from contracts import load_config  # type: ignore
    from controller import ResolvedRateController  # type: ignore
    import coupled_dynamics  # type: ignore
    from repo_imports import CoupledModel  # type: ignore
    from trajectories import build_t2_reference  # type: ignore

    cfg = load_config()
    # REORG04 moved the accepted URDF into 20_engineering/cad.  The frozen
    # sim_05 FK source remains byte-pinned by E23 and therefore must not be
    # edited merely to change its default locator.  Bind the explicit accepted
    # URDF to the CoupledModel constructor for this isolated predevelopment run.
    accepted_urdf = (
        repo_root
        / "20_engineering"
        / "cad"
        / "spacecraft_layout"
        / "arm_b601_v1"
        / "arm_b601_v1.urdf"
    )
    original_arm_factory = coupled_dynamics.B601Arm

    def _reorg04_arm_factory():
        return original_arm_factory(str(accepted_urdf))

    coupled_dynamics.B601Arm = _reorg04_arm_factory
    try:
        model = CoupledModel()
    finally:
        coupled_dynamics.B601Arm = original_arm_factory
    theta = np.asarray(cfg["trajectories"]["T2"]["q_initial_rad"], dtype=float)
    eta = np.zeros(2 * model.n_modes, dtype=float)
    reference = build_t2_reference(model, cfg).sample(int(probe_cfg["sample_index"]))
    variants = []
    for item in probe_cfg["controller_variants"]:
        output = ResolvedRateController(
            model, cfg, item["method"], item["task_mode"]
        ).command(
            theta,
            eta,
            eta,
            np.eye(3),
            reference["position_I"],
            reference["rotation_IE"],
            reference,
        )
        row = {
            "method": item["method"],
            "task_mode": item["task_mode"],
            "theta_dot_command": output.theta_dot_command.tolist(),
            "theta_dot_command_norm": float(np.linalg.norm(output.theta_dot_command)),
            "task_sigma_min": output.task_sigma_min,
            "task_condition": output.task_condition,
            "task_rank": output.task_rank,
            "task_nullity": output.task_nullity,
            "nullspace_active": output.nullspace_active,
            "nullspace_leakage": output.nullspace_leakage,
            "reaction_primary_norm": output.reaction_primary_norm,
            "reaction_command_norm": output.reaction_command_norm,
            "predicted_base_twist": output.predicted_base_twist.tolist(),
            "predicted_base_twist_norm": float(np.linalg.norm(output.predicted_base_twist)),
            "feedforward_norm": output.feedforward_norm,
        }
        values = np.asarray(
            row["theta_dot_command"] + row["predicted_base_twist"], dtype=float
        )
        row["all_finite"] = bool(np.all(np.isfinite(values)))
        variants.append(row)

    by_method = {row["method"]: row for row in variants}
    checks = {
        "all_outputs_finite": all(row["all_finite"] for row in variants),
        "c0_exact_pose_zero_without_feedforward": by_method["C0"]["theta_dot_command_norm"]
        <= float(probe_cfg["zero_command_abs_max"]),
        "c1_exact_pose_zero_without_feedforward": by_method["C1"]["theta_dot_command_norm"]
        <= float(probe_cfg["zero_command_abs_max"]),
        "c2_feedforward_nonzero": by_method["C2"]["theta_dot_command_norm"]
        >= float(probe_cfg["feedforward_command_norm_min"]),
        "c3_feedforward_nonzero": by_method["C3"]["theta_dot_command_norm"]
        >= float(probe_cfg["feedforward_command_norm_min"]),
        "c3_rank5_nullity1": by_method["C3"]["task_rank"] == 5
        and by_method["C3"]["task_nullity"] == 1,
        "c3_exact_projector_leakage_bounded": by_method["C3"]["nullspace_leakage"]
        <= float(probe_cfg["c3_nullspace_leakage_max"]),
    }
    return {
        "model": "CTRL01_SIM11_COUPLED_MODEL_WITH_EXPLICIT_REORG04_ACCEPTED_URDF_ADAPTER",
        "locator_adapter": {
            "accepted_urdf": accepted_urdf.relative_to(repo_root).as_posix(),
            "frozen_fk_source_modified": False,
            "e23_hash_pin_preserved": True,
        },
        "scope": "SINGLE_STATE_NONCONTACT_NOMINAL_RESOLVED_RATE_DIAGNOSTIC",
        "trajectory": probe_cfg["trajectory"],
        "sample_index": int(probe_cfg["sample_index"]),
        "n_modes_per_panel": int(model.n_modes),
        "variants": variants,
        "checks": checks,
        "pass": all(checks.values()),
    }


def run_nominal_probe(repo_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    first = _probe_once(repo_root, config["probe"])
    second = _probe_once(repo_root, config["probe"])
    first_hash = canonical_sha256(first)
    second_hash = canonical_sha256(second)
    return {
        "schema": "CTRL_R2_NOMINAL_DLS_PROBE_V1",
        "scope": "NONCONTACT_MODEL_LEVEL_SINGLE_STATE_PROBE_NO_PERFORMANCE_CREDIT",
        "first": first,
        "determinism": {
            "first_canonical_sha256": first_hash,
            "replay_canonical_sha256": second_hash,
            "bitwise_canonical_equal": first_hash == second_hash,
        },
        "pass": first["pass"] and first_hash == second_hash,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def classify_ctrl01(gate: dict[str, Any]) -> dict[str, Any]:
    gates = gate["gates"]
    constraints = gates["GC1_E_constraints"]
    values = constraints["values"]
    return {
        "schema": "CTRL01_FAILURE_CLASSIFICATION_V1",
        "source_verdict": gate["verdict"],
        "classification_scope": "EVIDENCE_BOUND_DIAGNOSTIC_NOT_NEW_CAUSAL_CERTIFICATION",
        "categories": {
            "tracking": {
                "state": "CONFIRMED_FAILURE",
                "evidence": {
                    "C1_T1_anchor_delta_deg": gates["GC1_A2_closed_loop_C1_T1_anchor"]["delta_deg"],
                    "threshold_deg": gates["GC1_A2_closed_loop_C1_T1_anchor"]["threshold_deg"],
                    "bounded_error_violations": gates["GC1_F_bounded_error_C1_C2_C3"]["violations"],
                },
                "interpretation": "frozen-gain feedback lag and T3 bounded-position error remain unresolved",
            },
            "singularity": {
                "state": "OBSERVED_CONSTRAINT_RISK",
                "minimum_task_sigma": values["task_sigma_min"],
                "global_limit": constraints["conservative_global_limits"]["singular_value_min"],
            },
            "joint_limit": {
                "state": "CONFIRMED_VIOLATION",
                "minimum_margin_rad": values["joint_limit_margin_min_rad"],
            },
            "base_reaction": {
                "state": "COMPENSATION_INEFFECTIVE_UNDER_FROZEN_COMPARATOR",
                "c3_vs_c2_match5_improvement_pct": gates["GC1_D_incremental_effectiveness"]["C3_vs_C2_MATCH5_T2_base_rate_improvement_pct"],
                "required_pct": gates["GC1_D_incremental_effectiveness"]["C3_threshold_pct"],
            },
            "numerical": {
                "state": "NOT_SUPPORTED_AS_ROOT_CAUSE",
                "momentum_max_abs": gates["GC1_B_conservation_and_energy"]["momentum_max_abs"],
                "energy_audit_relative_max": gates["GC1_B_conservation_and_energy"]["energy_audit_relative_max"],
                "fast_plant_equivalence_worst": gates["GC1_H_fast_plant_ssot_equivalence"]["overall_worst"],
            },
            "task_infeasibility": {
                "state": "SUPPORTED_BY_PREREGISTERED_CONSTRAINT_CONFLICTS",
                "t1_anchor_joint_limit_conflict_preregistered": constraints["T1_anchor_joint_limit_conflict_preregistered"],
                "t3_joint_limit_or_error_violations_present": True,
            },
            "missing_actuator_model": {
                "state": "OPEN_HARDWARE_TRIGGER",
                "evidence": "CTRL-02 L0 stability is NOT_EVALUATED_NO_ACTUATOR_DYNAMICS",
            },
        },
        "disposition": "RETAIN_REPEAT__DO_NOT_GAIN_TUNE_TO_PASS__REDESIGN_TASK_AND_ACTUATOR_AUTHORITY_BEFORE_RERUN",
        "next_stage_authorized": False,
    }
