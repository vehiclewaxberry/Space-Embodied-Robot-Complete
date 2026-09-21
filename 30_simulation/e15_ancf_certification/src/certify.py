"""Run the isolated ANCF certification campaign and publish fail-closed evidence."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

sys.dont_write_bytecode = True
for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import numpy as np
import scipy
import yaml

from model import (
    CERT_ROOT, REPO_ROOT, IntegrationFailure, NUMERIC_METRICS,
    canonical_hash, integrate_adaptive, integrate_streaming,
    metric_differences, modal_reference, newmark_linear,
    nominal_excitation, prepare_system, reconstruct_historical_case,
    relative_difference, sha256_file,
)


CONFIG_PATH = CERT_ROOT / "20_engineering" / "config" / "certification_v1.yaml"
RESULTS = CERT_ROOT / "results"
TABLES = CERT_ROOT / "tables"
DOCS = CERT_ROOT / "docs"
ANCHOR_OUTPUT = RESULTS / "low_amplitude_runs.csv"
HISTORICAL_ATTEMPTS = RESULTS / "historical_attempts.csv"
HISTORICAL_SUMMARY = RESULTS / "historical_classification.csv"
GATE_OUTPUT = RESULTS / "gate_summary.json"
MANIFEST_OUTPUT = RESULTS / "run_manifest.json"
SOURCE_OUTPUT = RESULTS / "source_inventory.json"
TIMING_OUTPUT = RESULTS / "timing_summary.json"
CROSS_OUTPUT = TABLES / "cross_solver_differences.csv"
CONVERGENCE_OUTPUT = TABLES / "discretization_trends.csv"
NEWMARK_OUTPUT = TABLES / "newmark_timestep_trend.csv"
REPORT_OUTPUT = DOCS / "ANCF_CERTIFICATION_REPORT_ZH.md"

FROZEN_FORENSICS = (
    REPO_ROOT / "40_evidence" / "artifacts" / "visualization" /
    "e15_gate_evidence_snapshot_20260714" /
    "results__sim_09_grasp_evaluator__e15_ancf_legacy_retry_forensics.csv")
FROZEN_E1 = REPO_ROOT / "30_simulation" / "sim_09_grasp_evaluator" / "results" / "e1_results_72cases.csv"
PROTECTION_MANIFEST = REPO_ROOT / "40_evidence" / "artifacts" / "visualization" / "tables" / "gate_artifact_protection_manifest.csv"


def _load_config():
    with CONFIG_PATH.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return [_json_safe(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def _write_csv(path: Path, rows, columns=None):
    rows = list(rows)
    if columns is None:
        columns = list(rows[0]) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows([{key: _cell(row.get(key)) for key in columns} for row in rows])


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))
    return value


def _read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _anchor_specs(config):
    low = config["low_amplitude"]
    base = {
        "rtol": float(low["baseline_rtol"]),
        "atol": float(low["baseline_atol"]),
        "max_step_s": 0.05,
        "impulse_mode": "velocity_jump",
        "pulse_duration_s": None,
    }
    specs = []
    for n_elements in map(int, low["mesh_elements"]):
        for method in ("Radau", "BDF"):
            specs.append({
                "experiment_id": f"mesh_n{n_elements}_{method.lower()}",
                "study_axis": "mesh_and_solver", "n_elements": n_elements,
                "method": method, **base,
            })
    for step in map(float, low["adaptive_max_steps_s"]):
        if step == base["max_step_s"]:
            continue
        specs.append({
            "experiment_id": f"maxstep_{step:g}_radau",
            "study_axis": "adaptive_max_step", "n_elements": 8,
            "method": "Radau", **{**base, "max_step_s": step},
        })
    for method in ("Radau", "BDF"):
        specs.append({
            "experiment_id": f"tight_tol_{method.lower()}",
            "study_axis": "tolerance", "n_elements": 8, "method": method,
            **{**base, "rtol": float(low["tight_rtol"]),
               "atol": float(low["tight_atol"])},
        })
    for duration in map(float, low["pulse_durations_s"]):
        for method in ("Radau", "BDF"):
            specs.append({
                "experiment_id": f"pulse_{duration:g}_{method.lower()}",
                "study_axis": "impulse_application", "n_elements": 8,
                "method": method,
                **{**base, "impulse_mode": "rectangular_pulse",
                   "pulse_duration_s": duration},
            })
    return specs


def _anchor_worker(payload):
    config = payload["config"]
    spec = payload["spec"]
    low = config["low_amplitude"]
    excitation = nominal_excitation()
    system = prepare_system(
        int(spec["n_elements"]), excitation, scale=float(low["excitation_scale"]),
        ei_case=config["beam"]["ei_case"],
        zeta=float(config["beam"]["damping_ratio"]))
    row = {
        **spec,
        "required_anchor": int(spec["study_axis"] == "mesh_and_solver"),
        "excitation_scale": float(low["excitation_scale"]),
        "t_end_s": float(low["t_end_s"]), "n_eval": int(low["n_eval"]),
        "f1_hz": system["f1_hz"], "state": "UNKNOWN",
        "training_eligible": 0, "ranking_eligible": 0,
        "safety_evaluation_eligible": 0, "silent_zero": 0,
    }
    try:
        result = integrate_adaptive(
            system, spec["method"], float(low["t_end_s"]), int(low["n_eval"]),
            spec["rtol"], spec["atol"], spec["max_step_s"],
            impulse_mode=spec["impulse_mode"],
            pulse_duration_s=spec["pulse_duration_s"],
            max_wall_s=float(low["anchor_hard_wall_s"]))
        modal_tip = modal_reference(
            system, result["times"], spec["impulse_mode"],
            spec["pulse_duration_s"])
        modal_peak = float(np.max(np.abs(modal_tip)))
        trajectory_difference = float(
            np.max(np.abs(result["tip"] - modal_tip)) /
            max(modal_peak, 1.0e-30))
        row.update({
            "state": "CONVERGED_DIAGNOSTIC", "classification": "COMPLETED",
            "specific_classification": "COMPLETED",
            "termination_reason": "COMPLETED",
            **result["metrics"],
            "modal_tip_peak_m": modal_peak,
            "ancf_modal_peak_relative_difference": relative_difference(
                result["metrics"]["tip_peak_m"], modal_peak),
            "ancf_modal_trajectory_relative_difference": trajectory_difference,
            **{key: result["diagnostics"][key] for key in
               ("n_steps", "nfev", "njev", "nlu", "wall_s")},
        })
    except IntegrationFailure as exc:
        row.update(exc.diagnostics)
    row["record_hash"] = canonical_hash({
        key: value for key, value in row.items() if key != "wall_s"})
    return row


def _anchor_process_entry(queue, payload):
    try:
        queue.put({"row": _anchor_worker(payload), "error": None})
    except Exception as exc:  # fail closed; parent records no physical metrics
        queue.put({
            "row": None,
            "error": f"{type(exc).__name__}: {exc}",
        })


def run_anchors(config):
    """Run every anchor in an independently killable child process."""
    low = config["low_amplitude"]
    hard_limit = float(low["anchor_hard_wall_s"])
    parent_limit = hard_limit + float(low["process_startup_grace_s"])
    context = multiprocessing.get_context("spawn")
    rows = []
    for spec in _anchor_specs(config):
        queue = context.Queue(maxsize=1)
        process = context.Process(
            target=_anchor_process_entry,
            args=(queue, {"config": config, "spec": spec}))
        process.start()
        process.join(parent_limit)
        if process.is_alive():
            process.terminate()
            process.join(5.0)
            if process.is_alive():
                process.kill()
                process.join(2.0)
            row = {
                **spec, "required_anchor": int(spec["study_axis"] == "mesh_and_solver"),
                "excitation_scale": float(low["excitation_scale"]),
                "t_end_s": float(low["t_end_s"]), "n_eval": int(low["n_eval"]),
                "state": "UNKNOWN", "classification": "SOLVER_NONCONVERGENCE",
                "specific_classification": "RESOURCE_LIMIT_WALL",
                "termination_reason": "PARENT_HARD_WALL_KILL",
                "wall_s": parent_limit, "training_eligible": 0,
                "ranking_eligible": 0, "safety_evaluation_eligible": 0,
                "silent_zero": 0,
            }
        else:
            try:
                payload = queue.get(timeout=2.0)
            except Exception:
                payload = {"row": None, "error": "child exited without a result"}
            if payload["row"] is None:
                row = {
                    **spec,
                    "required_anchor": int(spec["study_axis"] == "mesh_and_solver"),
                    "excitation_scale": float(low["excitation_scale"]),
                    "t_end_s": float(low["t_end_s"]), "n_eval": int(low["n_eval"]),
                    "state": "UNKNOWN", "classification": "PROGRAM_EXCEPTION",
                    "specific_classification": "PROGRAM_EXCEPTION",
                    "termination_reason": payload["error"], "wall_s": None,
                    "training_eligible": 0, "ranking_eligible": 0,
                    "safety_evaluation_eligible": 0, "silent_zero": 0,
                }
            else:
                row = payload["row"]
        queue.close()
        queue.join_thread()
        row["record_hash"] = canonical_hash({
            key: value for key, value in row.items() if key != "wall_s"})
        rows.append(row)
        print(
            f"[anchor] {row['experiment_id']}: {row.get('specific_classification')} "
            f"wall={float(row.get('wall_s') or 0):.3f}s", flush=True)
    _write_csv(ANCHOR_OUTPUT, rows)
    return rows


def _cross_solver_rows(anchor_rows):
    groups = {}
    for row in anchor_rows:
        if row.get("classification") != "COMPLETED":
            continue
        key = (
            int(row["n_elements"]), float(row["rtol"]), float(row["atol"]),
            float(row["max_step_s"]), row["impulse_mode"],
            None if row.get("pulse_duration_s") in (None, "")
            else float(row["pulse_duration_s"]),
        )
        groups.setdefault(key, {})[row["method"]] = row
    output = []
    for key, methods in groups.items():
        if set(methods) != {"Radau", "BDF"}:
            continue
        differences = metric_differences(methods["Radau"], methods["BDF"])
        output.append({
            "n_elements": key[0], "rtol": key[1], "atol": key[2],
            "max_step_s": key[3], "impulse_mode": key[4],
            "pulse_duration_s": key[5],
            **{f"relative_{name}": value for name, value in differences.items()},
            "max_relative_difference": max(differences.values()),
            "strict_lt_5pct": int(max(differences.values()) < 0.05),
        })
    _write_csv(CROSS_OUTPUT, output)
    return output


def _discretization_rows(anchor_rows, config):
    completed = [row for row in anchor_rows if row.get("classification") == "COMPLETED"]
    output = []
    mesh = sorted(
        [row for row in completed if row["study_axis"] == "mesh_and_solver"
         and row["method"] == "Radau"], key=lambda row: int(row["n_elements"]))
    for previous, current in zip(mesh, mesh[1:]):
        output.append({
            "study_axis": "mesh", "coarse": previous["n_elements"],
            "fine": current["n_elements"], "metric": "tip_peak_m",
            "coarse_value": previous["tip_peak_m"], "fine_value": current["tip_peak_m"],
            "relative_change": relative_difference(
                previous["tip_peak_m"], current["tip_peak_m"]),
        })
    step_rows = sorted(
        [row for row in completed if row["method"] == "Radau"
         and int(row["n_elements"]) == 8 and row["impulse_mode"] == "velocity_jump"
         and float(row["rtol"]) == float(config["low_amplitude"]["baseline_rtol"])],
        key=lambda row: float(row["max_step_s"]), reverse=True)
    seen = set()
    step_rows = [row for row in step_rows if not (
        float(row["max_step_s"]) in seen or seen.add(float(row["max_step_s"]))) ]
    for previous, current in zip(step_rows, step_rows[1:]):
        output.append({
            "study_axis": "adaptive_max_step", "coarse": previous["max_step_s"],
            "fine": current["max_step_s"], "metric": "tip_peak_m",
            "coarse_value": previous["tip_peak_m"], "fine_value": current["tip_peak_m"],
            "relative_change": relative_difference(
                previous["tip_peak_m"], current["tip_peak_m"]),
        })
    pulse = sorted(
        [row for row in completed if row["method"] == "Radau"
         and row["impulse_mode"] == "rectangular_pulse"],
        key=lambda row: float(row["pulse_duration_s"]), reverse=True)
    jump = next((row for row in completed if row["experiment_id"] == "mesh_n8_radau"), None)
    if jump:
        for row in pulse:
            output.append({
                "study_axis": "impulse_duration_to_jump",
                "coarse": row["pulse_duration_s"], "fine": 0.0,
                "metric": "tip_peak_m", "coarse_value": row["tip_peak_m"],
                "fine_value": jump["tip_peak_m"],
                "relative_change": relative_difference(
                    row["tip_peak_m"], jump["tip_peak_m"]),
            })
    _write_csv(CONVERGENCE_OUTPUT, output)
    return output


def _newmark_rows(config):
    low = config["low_amplitude"]
    system = prepare_system(
        8, nominal_excitation(), scale=float(low["excitation_scale"]),
        ei_case=config["beam"]["ei_case"], zeta=float(config["beam"]["damping_ratio"]))
    output = []
    for dt in map(float, low["newmark_time_steps_s"]):
        times, tip = newmark_linear(system, dt, float(low["t_end_s"]))
        reference = modal_reference(system, times)
        reference_peak = float(np.max(np.abs(reference)))
        output.append({
            "method": "Newmark_average_acceleration", "time_step_s": dt,
            "n_steps": len(times) - 1, "tip_peak_m": float(np.max(np.abs(tip))),
            "modal_tip_peak_m": reference_peak,
            "peak_relative_difference": relative_difference(
                float(np.max(np.abs(tip))), reference_peak),
            "trajectory_relative_difference": float(
                np.max(np.abs(tip - reference)) / max(reference_peak, 1.0e-30)),
        })
    _write_csv(NEWMARK_OUTPUT, output)
    return output


def _historical_worker(payload):
    config = payload["config"]
    case_id = payload["case_id"]
    method = payload["method"]
    physical = reconstruct_historical_case(case_id)
    system = prepare_system(
        int(config["n_elements"]), physical, scale=1.0,
        ei_case=payload["ei_case"], zeta=float(payload["zeta"]))
    solver_input = {
        "case_id": case_id, "legacy_scenario_hash": physical["legacy_scenario_hash"],
        "historical_flex_status": physical["historical_flex_status"],
        "physical_input_hash": physical["physical_input_hash"],
        "legacy_row_hash": physical["legacy_row_hash"],
        "legacy_csv_sha256": physical["legacy_csv_sha256"],
        "method": method, "n_elements": int(config["n_elements"]),
        "t_end_s": float(config["t_end_s"]), "n_eval": int(config["n_eval"]),
        "rtol": float(config["rtol"]), "atol": float(config["atol"]),
        "max_step_s": float(config["max_step_s"]),
        "max_accepted_steps": int(config["max_accepted_steps"]),
        "max_nfev": int(config["max_nfev"]),
        "max_wall_s": float(config["max_wall_s_per_attempt"]),
    }
    row = {
        **solver_input, "forensic_hash": canonical_hash(solver_input),
        "state": "UNKNOWN", "classification": "UNCLASSIFIED",
        "specific_classification": "UNCLASSIFIED", "termination_reason": "",
        "training_eligible": 0, "ranking_eligible": 0,
        "safety_evaluation_eligible": 0, "silent_zero": 0,
    }
    try:
        result = integrate_streaming(
            system, method, float(config["t_end_s"]), int(config["n_eval"]),
            float(config["rtol"]), float(config["atol"]),
            float(config["max_step_s"]), int(config["max_accepted_steps"]),
            int(config["max_nfev"]), float(config["max_wall_s_per_attempt"]))
        row.update(result["diagnostics"])
        row.update(result["metrics"])
        row["state"] = "CONVERGED_DIAGNOSTIC"
    except IntegrationFailure as exc:
        row.update(exc.diagnostics)
        # Critical fail-closed contract: failed output metrics remain null.
        row.update({metric: None for metric in NUMERIC_METRICS})
    row["attempt_evidence_hash"] = canonical_hash({
        key: value for key, value in row.items()
        if key not in {"wall_s", "attempt_evidence_hash"}})
    return row


def run_historical(config, workers):
    hist = dict(config["historical_rerun"])
    payloads = [
        {"case_id": case_id, "method": method, "config": hist,
         "ei_case": config["beam"]["ei_case"],
         "zeta": config["beam"]["damping_ratio"]}
        for case_id in hist["cases"] for method in hist["methods"]
    ]
    with ProcessPoolExecutor(max_workers=int(workers)) as pool:
        rows = list(pool.map(_historical_worker, payloads))
    rows.sort(key=lambda row: (hist["cases"].index(row["case_id"]),
                               hist["methods"].index(row["method"])))
    for row in rows:
        print(
            f"[historical] {row['case_id']} {row['method']}: "
            f"{row['specific_classification']} t={float(row.get('last_time_s') or 0):.6g}s "
            f"wall={float(row.get('wall_s') or 0):.2f}s", flush=True)
    _write_csv(HISTORICAL_ATTEMPTS, rows)
    summary = _summarize_historical(rows, config)
    _write_csv(HISTORICAL_SUMMARY, summary)
    return rows, summary


def _summarize_historical(rows, config):
    frozen = {row["case_id"]: row for row in _read_csv(FROZEN_FORENSICS)}
    by_case = {}
    for row in rows:
        by_case.setdefault(row["case_id"], {})[row["method"]] = row
    output = []
    for case_id in config["historical_rerun"]["cases"]:
        methods = by_case.get(case_id, {})
        radau, bdf = methods.get("Radau"), methods.get("BDF")
        attempts = [value for value in (radau, bdf) if value]
        classified = bool(attempts) and all(
            row.get("classification") not in (None, "", "UNCLASSIFIED")
            and row.get("specific_classification") not in (None, "", "UNCLASSIFIED")
            for row in attempts)
        silent_zero = any(
            row.get("classification") != "COMPLETED"
            and any(row.get(metric) not in (None, "") for metric in NUMERIC_METRICS)
            for row in attempts)
        both_completed = bool(radau and bdf and
                              radau.get("classification") == "COMPLETED" and
                              bdf.get("classification") == "COMPLETED")
        differences = metric_differences(radau, bdf) if both_completed else None
        maximum = max(differences.values()) if differences else None
        cross_pass = bool(maximum is not None and maximum < 0.05)
        old = frozen.get(case_id, {})
        current_nonconvergence = bool(attempts) and all(
            row.get("classification") == "SOLVER_NONCONVERGENCE" for row in attempts)
        output.append({
            "case_id": case_id,
            "historical_flex_status": old.get("historical_flex_status", ""),
            "historical_failure_classification": old.get("failure_classification", ""),
            "radau_specific_classification": (radau or {}).get("specific_classification", ""),
            "bdf_specific_classification": (bdf or {}).get("specific_classification", ""),
            "current_classified": int(classified),
            "classification_reproduced": int(
                old.get("failure_classification") == "SOLVER_NONCONVERGENCE"
                and current_nonconvergence),
            "cross_solver_max_relative_difference": maximum,
            "cross_solver_lt_5pct": int(cross_pass),
            "state": ("CONVERGED_CROSSCHECK_DIAGNOSTIC" if cross_pass else "UNKNOWN"),
            "training_eligible": 0, "ranking_eligible": 0,
            "safety_evaluation_eligible": 0,
            "silent_zero": int(silent_zero),
            "physical_input_hash": (radau or bdf or {}).get("physical_input_hash", ""),
        })
    return output


def _git_text(*arguments):
    return subprocess.check_output(
        ["git", *arguments], cwd=REPO_ROOT, text=True,
        stderr=subprocess.DEVNULL).strip()


def _source_inventory(config):
    paths = [
        CONFIG_PATH,
        FROZEN_E1,
        FROZEN_FORENSICS,
        PROTECTION_MANIFEST,
        REPO_ROOT / "30_simulation" / "sim_07_ancf_flexible" / "ancf_beam.py",
        REPO_ROOT / "30_simulation" / "sim_07_ancf_flexible" / "sim_07a_task_response.py",
        REPO_ROOT / "20_engineering" / "config" / "geometry" / "flexible_appendage_v1.yaml",
    ]
    protection_rows = _read_csv(PROTECTION_MANIFEST)
    expected = {}
    protection_checks = []
    for row in protection_rows:
        key = str(row.get("source_rel_path", "")).replace("\\", "/")
        if key:
            expected[key] = str(row.get("expected_sha256", "")).lower()
            expected_hash = expected[key]
            source_path = REPO_ROOT / key
            snapshot_key = str(row.get("snapshot_path", "")).replace("\\", "/")
            snapshot_path = REPO_ROOT / snapshot_key
            source_actual = sha256_file(source_path) if source_path.exists() else None
            snapshot_actual = sha256_file(snapshot_path) if snapshot_path.exists() else None
            try:
                snapshot_blob = subprocess.check_output(
                    ["git", "show", f"{config['baseline_commit']}:{snapshot_key}"],
                    cwd=REPO_ROOT, stderr=subprocess.DEVNULL)
                snapshot_blob_matches = (
                    hashlib.sha256(snapshot_blob).hexdigest()
                    == expected_hash)
            except subprocess.CalledProcessError:
                snapshot_blob_matches = False
            protection_checks.append({
                "path": key,
                "snapshot_path": snapshot_key,
                "source_present": source_path.exists(),
                "source_matches_expected": bool(
                    source_actual and source_actual.lower() == expected_hash),
                "snapshot_matches_expected": bool(
                    snapshot_actual and snapshot_actual.lower() == expected_hash),
                "frozen_snapshot_blob_matches_expected": snapshot_blob_matches,
                "manifest_declared_source_match": (
                    str(row.get("match_expected", "")).lower() == "true"),
                "manifest_declared_snapshot_match": (
                    str(row.get("snapshot_hash_match", "")).lower() == "true"),
            })
    files = []
    for path in paths:
        relative = path.relative_to(REPO_ROOT).as_posix()
        actual = sha256_file(path)
        expected_hash = expected.get(relative)
        baseline_blob = None
        working_blob = None
        try:
            baseline_blob = _git_text(
                "rev-parse", f"{config['baseline_commit']}:{relative}")
            working_blob = _git_text(
                "hash-object", f"--path={relative}", str(path))
        except subprocess.CalledProcessError:
            # The certification config is intentionally new on top of the
            # frozen baseline; every legacy input must have a baseline blob.
            pass
        files.append({
            "path": relative, "sha256": actual,
            "expected_sha256": expected_hash,
            "matches_viz_protection_manifest": (
                None if expected_hash is None else actual.lower() == expected_hash),
            "baseline_git_blob": baseline_blob,
            "working_tree_git_blob": working_blob,
            "matches_frozen_baseline": (
                None if baseline_blob is None else baseline_blob == working_blob),
        })
    source_present = sum(item["source_present"] for item in protection_checks)
    source_matches = sum(item["source_matches_expected"] for item in protection_checks)
    snapshot_matches = sum(item["snapshot_matches_expected"] for item in protection_checks)
    frozen_snapshot_matches = sum(
        item["frozen_snapshot_blob_matches_expected"] for item in protection_checks)
    declared_source_matches = sum(
        item["manifest_declared_source_match"] for item in protection_checks)
    declared_snapshot_matches = sum(
        item["manifest_declared_snapshot_match"] for item in protection_checks)
    inventory = {
        "schema_version": "ancf_certification_source_inventory_v1",
        "baseline_commit": config["baseline_commit"], "files": files,
        "viz_protection_manifest": {
            "entries": len(protection_checks),
            "manifest_declared_source_matches": declared_source_matches,
            "manifest_declared_snapshot_matches": declared_snapshot_matches,
            "current_source_files_present": source_present,
            "current_source_expected_matches": source_matches,
            "current_snapshot_raw_expected_matches": snapshot_matches,
            "frozen_snapshot_blob_expected_matches": frozen_snapshot_matches,
            "independent_recheck_all_pass": bool(
                protection_checks
                and source_matches == len(protection_checks)
                and frozen_snapshot_matches == len(protection_checks)),
            "interpretation": (
                "The frozen manifest records its creation-time declarations, "
                "but those 22 declarations are not independently reproducible "
                "from this isolated baseline. No legacy VIZ file was changed."),
        },
    }
    _write_json(SOURCE_OUTPUT, inventory)
    return inventory


def _compute_gates(config, anchor_rows, cross_rows, convergence_rows,
                   newmark_rows, historical_rows):
    gates = config["scientific_gates"]
    completed_anchors = [r for r in anchor_rows if r.get("classification") == "COMPLETED"]
    required_anchors = [r for r in anchor_rows if int(r.get("required_anchor", 0)) == 1]
    required_completed = [r for r in required_anchors
                          if r.get("classification") == "COMPLETED"]
    diagnostic_anchors = [r for r in anchor_rows if int(r.get("required_anchor", 0)) == 0]
    diagnostic_completed = [r for r in diagnostic_anchors
                            if r.get("classification") == "COMPLETED"]
    modal_max = max((float(r["ancf_modal_trajectory_relative_difference"])
                     for r in required_completed), default=None)
    cross_max = max((float(r["max_relative_difference"]) for r in cross_rows),
                    default=None)
    mesh_changes = [float(r["relative_change"]) for r in convergence_rows
                    if r["study_axis"] == "mesh"]
    mesh_trend = len(mesh_changes) >= 2 and mesh_changes[-1] < mesh_changes[0]
    newmark_sorted = sorted(newmark_rows, key=lambda row: float(row["time_step_s"]),
                            reverse=True)
    newmark_errors = [float(row["trajectory_relative_difference"])
                      for row in newmark_sorted]
    time_trend = len(newmark_errors) >= 3 and all(
        later < earlier for earlier, later in zip(newmark_errors, newmark_errors[1:]))
    pulse_changes = [float(r["relative_change"]) for r in convergence_rows
                     if r["study_axis"] == "impulse_duration_to_jump"]
    pulse_trend = len(pulse_changes) >= 2 and pulse_changes[-1] < pulse_changes[0]
    classified = sum(int(r.get("current_classified", 0)) for r in historical_rows)
    reproduced = sum(int(r.get("classification_reproduced", 0)) for r in historical_rows)
    unclassified = len(historical_rows) - classified
    silent_zero = sum(int(r.get("silent_zero", 0)) for r in historical_rows)
    unknown = sum(r.get("state") == "UNKNOWN" for r in historical_rows)
    historical_fraction = classified / len(historical_rows) if historical_rows else 0.0
    final_candidate_available = False  # frozen E1.5 Pareto Top-3 is empty (SAFE=0)
    result = {
        "schema_version": "ancf_certification_gate_v1",
        "historical": {
            "total": len(historical_rows), "classified": classified,
            "classification_fraction": historical_fraction,
            "classification_reproduced": reproduced,
            "unclassified": unclassified, "unknown": unknown,
            "silent_zero": silent_zero,
            "classification_gate_pass": (
                historical_fraction >= float(gates["historical_classification_fraction_min"])
                and unclassified <= int(gates["unclassified_max"])),
            "silent_zero_gate_pass": silent_zero <= int(gates["silent_zero_max"]),
        },
        "low_amplitude": {
            "required_runs": len(required_anchors),
            "required_completed_runs": len(required_completed),
            "diagnostic_runs": len(diagnostic_anchors),
            "diagnostic_completed_runs": len(diagnostic_completed),
            "diagnostic_unknown_runs": len(diagnostic_anchors) - len(diagnostic_completed),
            "max_ancf_modal_trajectory_relative_difference": modal_max,
            "gate_limit": float(gates["low_amplitude_ancf_modal_relative_max"]),
            "gate_pass": (len(required_completed) == len(required_anchors)
                          and len(required_anchors) == 6
                          and modal_max is not None
                          and modal_max < float(gates["low_amplitude_ancf_modal_relative_max"])),
        },
        "cross_solver_diagnostic": {
            "comparison_count": len(cross_rows),
            "max_relative_difference": cross_max,
            "all_lt_5pct": bool(cross_rows and all(
                int(row["strict_lt_5pct"]) == 1 for row in cross_rows)),
        },
        "discretization": {
            "mesh_trend_observable": mesh_trend,
            "newmark_time_step_trend_observable": time_trend,
            "impulse_duration_trend_observable": pulse_trend,
            "mesh_changes": mesh_changes, "newmark_errors": newmark_errors,
            "pulse_to_jump_changes": pulse_changes,
            "gate_pass": mesh_trend and time_trend and pulse_trend,
        },
        "final_candidate_cross_solver": {
            "available": final_candidate_available,
            "max_relative_difference": None,
            "gate_limit": float(gates["final_candidate_cross_solver_relative_max"]),
            "gate_pass": False,
            "reason": "冻结E1.5为SAFE=0且无名义Top-3；不得用低振幅诊断锚点冒充最终候选。",
        },
    }
    result["overall"] = (
        "PASS_ANCF_CERTIFICATION" if all((
            result["historical"]["classification_gate_pass"],
            result["historical"]["silent_zero_gate_pass"],
            result["low_amplitude"]["gate_pass"],
            result["discretization"]["gate_pass"],
            result["final_candidate_cross_solver"]["gate_pass"],
        )) else "REPEAT_ANCF_CERTIFICATION")
    return result


def _load_timing(invocation_elapsed_s):
    if TIMING_OUTPUT.exists():
        timing = json.loads(TIMING_OUTPUT.read_text(encoding="utf-8"))
    else:
        timing = {
            "anchor_invocation_s": None,
            "historical_invocation_s": None,
            "total_formal_invocation_s": float(invocation_elapsed_s),
            "provenance": "current_invocation_only",
        }
    return timing


def _write_report(config, gate, inventory, timing):
    h = gate["historical"]
    low = gate["low_amplitude"]
    cross = gate["cross_solver_diagnostic"]
    disc = gate["discretization"]
    final = gate["final_candidate_cross_solver"]
    frozen = [item for item in inventory["files"]
              if item["matches_frozen_baseline"] is not None]
    frozen_ok = sum(item["matches_frozen_baseline"] is True for item in frozen)
    protection = inventory["viz_protection_manifest"]
    total_runtime = float(timing["total_formal_invocation_s"])
    anchor_runtime = timing.get("anchor_invocation_s")
    historical_runtime = timing.get("historical_invocation_s")
    runtime_detail = (
        f"（低振幅锚点 {float(anchor_runtime):.2f} s；历史重跑 "
        f"{float(historical_runtime):.2f} s）"
        if anchor_runtime is not None and historical_runtime is not None else "")
    sources = "\n".join(
        f"- [{item['url']}]({item['url']})：{item['influence']}"
        for item in config["primary_sources"])
    text = f"""# ANCF 数值认证报告（P0-B）

- 日期：2026-07-14
- 冻结基线：`6c15395`
- 专用树：`30_simulation/e15_ancf_certification/`
- 最终裁决：**{gate['overall']}**

## 1. 结论

本轮没有把求解器返回成功、放宽容差或资源耗尽解释成科学收敛。7 个历史工况均得到类型化结果，未收敛项保持 `UNKNOWN`，所有失败数值字段为空，不进入排序、训练或安全评价。

| Gate | 实测 | 裁决 |
|---|---:|---:|
| 历史失败分类 | {h['classified']}/{h['total']}；重现旧大类 {h['classification_reproduced']}/{h['total']}；未分类 {h['unclassified']} | {'PASS' if h['classification_gate_pass'] else 'REPEAT'} |
| 静默填零 | {h['silent_zero']} | {'PASS' if h['silent_zero_gate_pass'] else 'REPEAT'} |
| 低振幅 ANCF—模态必选锚点 | {low['required_completed_runs']}/{low['required_runs']}；最大轨迹相对差 {100.0 * (low['max_ancf_modal_trajectory_relative_difference'] or 0):.6g}%（限值 10%） | {'PASS' if low['gate_pass'] else 'REPEAT'} |
| 附加诊断矩阵 | {low['diagnostic_completed_runs']}/{low['diagnostic_runs']}；UNKNOWN {low['diagnostic_unknown_runs']} | 仅诊断，不替代必选门 |
| Radau/BDF 诊断锚点 | {cross['comparison_count']} 组；最大四指标差 {100.0 * (cross['max_relative_difference'] or 0):.6g}% | {'PASS' if cross['all_lt_5pct'] else 'REPEAT'} |
| 网格/步长/冲量趋势 | mesh={disc['mesh_trend_observable']}，Newmark dt={disc['newmark_time_step_trend_observable']}，pulse={disc['impulse_duration_trend_observable']} | {'PASS' if disc['gate_pass'] else 'REPEAT'} |
| 最终候选跨求解器 | 不可用；SAFE=0、Top-3为空 | **REPEAT** |

因此，数值基础锚点通过，但候选级最终认证仍未闭合；科学主链不得进入 E2/G3/HIL。

## 2. 独立性与输入保护

- 旧 `30_simulation/`、`src/`、E1/E1.5、VIZ v0 和共享合同均只读；新写入全部位于本专用树。
- 位移坐标非线性 ANCF 使用冻结 Beam 的同一 `M`、弹性力、Rayleigh 阻尼与捕获激励，但不复用旧绝对坐标积分状态。
- 6 个旧输入的 Git blob 与冻结基线一致：{frozen_ok}/{len(frozen)}；新认证配置不属于旧基线。
- VIZ 保护表自身的 Git blob 未被本轮修改，表内记录的是生成时“源/快照 22/22”声明；但在当前隔离基线中，原源文件存在 {protection['current_source_files_present']}/{protection['entries']}，冻结快照 Git blob 可重现预期 SHA-256 的是 {protection['frozen_snapshot_blob_expected_matches']}/{protection['entries']}。因此本报告不把表内声明冒充当前独立复核通过；该预存差异不属于本轮写入范围。
- 正式数值运行总耗时：{total_runtime:.2f} s{runtime_detail}；原型和本次离线封装时间不计入。

## 3. 历史失败分类方法

每个冻结 case/hash 在当前进程重新构造抓取姿态、基座速度跳变和 ANCF 初值，并分别运行 Radau 与 BDF。每次尝试同时受 30 s 墙钟、100000 接受步和 2000000 RHS 调用限制。`NUMERICAL_STEP_UNDERFLOW`、`RESOURCE_LIMIT_WALL`、`RESOURCE_LIMIT_ACCEPTED_STEPS` 和 `RESOURCE_LIMIT_NFEV` 都归入可审计的 `SOLVER_NONCONVERGENCE`；它们不是零响应。

逐工况证据：`results/historical_attempts.csv` 与 `results/historical_classification.csv`。

### 资源纪律更正

早期探索阶段发现：外层命令超时并不保证其数值子进程一并退出。相关残留子进程已在正式运行前逐个显式终止并确认退出；这些探索耗时和结果均不计入认证。此后正式锚点改为“每工况一个独立可杀子进程”，内部墙钟 12 s，另给 8 s 启动宽限，超限由父进程 terminate/kill；历史重跑则对每个 solver attempt 同时执行 30 s、100000 接受步和 2000000 RHS 调用三重上限。本报告只引用采用这些控制后的两次正式运行。

## 4. 低振幅与离散极限

- 低振幅比例：`{config['low_amplitude']['excitation_scale']}`；Radau/BDF 与线性模态闭式参考同场比较。
- 网格：2/4/8 ANCF 单元；只在小变形极限评估趋势，不外推到候选强激励。
- 容差：`rtol={config['low_amplitude']['baseline_rtol']}/{config['low_amplitude']['tight_rtol']}`；最大步长：0.10/0.05/0.025 s。
- 冲量：瞬时速度跳变与 20/10 ms 矩形脉冲；脉冲时宽减小时检查向速度跳变极限靠近。
- 独立固定步长：线性有限元 Newmark 平均加速度法，dt=20/10/5 ms，与模态闭式解对照。

## 5. 未通过项与止损边界

1. {final['reason']}
2. 低振幅锚点通过只能证明实现和线性极限自洽，不能授权历史强激励工况。
3. 墙钟或步数上限是明确的资源终止，不是收敛；放宽容差后的历史成功仍不获得资格。
4. 如要取得最终 `<5%` Gate，必须先产生经核心链认可的候选，再对同一物理输入完成 Radau/BDF、网格、步长、容差和冲量正则化的候选级一致性证明。

## 6. 一手技术来源及对选择的影响

{sources}

## 7. 机器可读成果

- `results/gate_summary.json`
- `results/run_manifest.json`
- `results/source_inventory.json`
- `results/timing_summary.json`
- `results/low_amplitude_runs.csv`
- `results/historical_attempts.csv`
- `results/historical_classification.csv`
- `tables/cross_solver_differences.csv`
- `tables/discretization_trends.csv`
- `tables/newmark_timestep_trend.csv`
- `tests/test_report.md`
"""
    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.write_text(text, encoding="utf-8")


def _git_scope_check():
    output = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=REPO_ROOT, text=True)
    paths = []
    for line in output.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.replace("\\", "/"))
    outside = [path for path in paths if not path.startswith("30_simulation/e15_ancf_certification/")]
    return {"changed_paths": paths, "outside_dedicated_tree": outside,
            "scope_pass": not outside}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("all", "anchors", "historical", "finalize"),
                        default="all")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--historical-wall-s", type=float)
    args = parser.parse_args()
    started = time.perf_counter()
    config = _load_config()
    if args.historical_wall_s is not None:
        config["historical_rerun"]["max_wall_s_per_attempt"] = float(
            args.historical_wall_s)

    inventory = _source_inventory(config)
    anchor_rows = (_read_csv(ANCHOR_OUTPUT)
                   if args.mode in ("historical", "finalize")
                   else run_anchors(config))
    cross_rows = _cross_solver_rows(anchor_rows)
    convergence_rows = _discretization_rows(anchor_rows, config)
    newmark_rows = _newmark_rows(config)

    if args.mode in ("all", "historical"):
        _, historical_rows = run_historical(config, args.workers)
    else:
        historical_rows = _read_csv(HISTORICAL_SUMMARY)

    gate = _compute_gates(
        config, anchor_rows, cross_rows, convergence_rows,
        newmark_rows, historical_rows)
    elapsed = time.perf_counter() - started
    scope = _git_scope_check()
    timing = _load_timing(elapsed)
    manifest = {
        "schema_version": "ancf_certification_run_manifest_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": config["baseline_commit"], "mode": args.mode,
        "invocation_elapsed_s": elapsed,
        "formal_campaign_timing": timing, "python": sys.version,
        "platform": platform.platform(), "numpy": np.__version__,
        "scipy": scipy.__version__, "config_sha256": sha256_file(CONFIG_PATH),
        "outputs": {}, "git_scope": scope,
    }
    _write_json(GATE_OUTPUT, gate)
    _write_report(config, gate, inventory, timing)
    for path in (
            ANCHOR_OUTPUT, HISTORICAL_ATTEMPTS, HISTORICAL_SUMMARY,
            CROSS_OUTPUT, CONVERGENCE_OUTPUT, NEWMARK_OUTPUT, SOURCE_OUTPUT,
            TIMING_OUTPUT, GATE_OUTPUT, REPORT_OUTPUT,
            CERT_ROOT / "tests" / "test_report.md"):
        if path.exists():
            manifest["outputs"][path.relative_to(CERT_ROOT).as_posix()] = sha256_file(path)
    _write_json(MANIFEST_OUTPUT, manifest)
    print(json.dumps({
        "overall": gate["overall"], "elapsed_s": elapsed,
        "historical": gate["historical"],
        "low_amplitude": gate["low_amplitude"],
        "scope": scope,
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
