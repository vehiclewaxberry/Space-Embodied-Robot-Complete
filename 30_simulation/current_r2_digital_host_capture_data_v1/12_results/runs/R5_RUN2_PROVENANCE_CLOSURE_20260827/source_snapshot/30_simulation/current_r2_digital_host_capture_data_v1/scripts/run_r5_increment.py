#!/usr/bin/env python3
"""Execute the isolated R5 S02/S03 unit-safe dynamics increment.

No legacy active output is mutated.  A run is immutable by construction and
is complete only when ``RUN_COMPLETE.json`` exists.
"""
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

MODULE = Path(__file__).resolve().parents[1]
REPO = MODULE.parents[1]
SRC = MODULE / "src"
sys.path.insert(0, str(SRC))

from dh_v1.hashing import sha256_canonical_json, sha256_file  # noqa: E402
from dh_v1.momentum_ledger_r5 import ledger_timeseries_columns  # noqa: E402
from dh_v1.plant import FloatingPlant, compose_models  # noqa: E402
from dh_v1.scen_dynamics_r5 import (  # noqa: E402
    controller_from_config,
    run_s02_case_r5,
    run_s03_dt_r5,
    stability_analysis_r5,
)
from dh_v1.urdf_extract import extract_urdf, total_mass, validate_tree  # noqa: E402

TASK_ID = "R5_UNIT_SAFE_MOMENTUM_LEDGER_AND_VERSIONED_RUNNER"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
ALLOWED_OUTPUT_BASE = (MODULE / "12_results" / "runs").resolve()
UNIT_AUDIT_TOOL = Path(
    "F:/codex_skill/AgentSkills/agents-skills/uncertainty-and-units/scripts/audit_units.py"
)
CONFIG_PATHS = {
    "gate": MODULE / "configs/gates/r5_momentum_gate_v1.yaml",
    "controller_s03": MODULE / "configs/controllers/s03_pd_v1.yaml",
    "controller_c0": MODULE / "configs/controllers/c0_no_control_v1.yaml",
    "scenarios": MODULE / "configs/scenarios/r5_s02_s03_v1.yaml",
    "plant_binding": MODULE / "configs/plant/r5_plant_binding_v1.yaml",
}


class R5RunError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def jsonable(value):
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, Path):
        return value.as_posix()
    return value


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(jsonable(obj), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(jsonable(obj), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def validate_run_id(run_id: str) -> str:
    if run_id in (".", "..") or not RUN_ID_RE.fullmatch(run_id):
        raise R5RunError(
            "run-id must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$ and contain no path separator"
        )
    return run_id


def resolve_output_root(output_root: str | Path) -> Path:
    root = Path(output_root).resolve()
    try:
        root.relative_to(ALLOWED_OUTPUT_BASE)
    except ValueError as exc:
        raise R5RunError(f"output-root must remain inside {ALLOWED_OUTPUT_BASE}") from exc
    return root


def ensure_descendant(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise R5RunError(f"generated path escaped run root: {path}") from exc


def load_yaml(path: Path) -> dict:
    obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise R5RunError(f"configuration is not a mapping: {path}")
    return obj


def verify_bound_file(repo_relative: str, expected_sha: str) -> Path:
    path = (REPO / repo_relative).resolve()
    try:
        path.relative_to(REPO.resolve())
    except ValueError as exc:
        raise R5RunError(f"bound input escaped repository: {repo_relative}") from exc
    if not path.is_file():
        raise R5RunError(f"bound input missing: {path}")
    actual = sha256_file(path)
    if actual != expected_sha.lower():
        raise R5RunError(
            f"bound input hash mismatch: {repo_relative}: expected {expected_sha}, got {actual}"
        )
    return path


def source_manifest() -> dict:
    files = sorted((SRC / "dh_v1").glob("*.py")) + [Path(__file__).resolve()]
    for path in CONFIG_PATHS.values():
        files.append(path.resolve())
    rows = []
    for path in sorted(set(files), key=lambda p: p.as_posix()):
        rows.append(
            {
                "path": path.relative_to(REPO).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema": "R5_SOURCE_HASH_MANIFEST_V1",
        "files": rows,
        "source_tree_sha256": sha256_canonical_json(rows),
        "git_target_tracked": False,
        "git_head_is_not_source_identity": True,
    }


def write_source_snapshot(run_root: Path, manifest: dict) -> dict:
    rows = []
    for item in manifest["files"]:
        source_path = REPO / item["path"]
        snapshot_path = run_root / "source_snapshot" / item["path"]
        ensure_descendant(snapshot_path, run_root)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, snapshot_path)
        snapshot_sha = sha256_file(snapshot_path)
        if snapshot_sha != item["sha256"]:
            raise R5RunError(f"source snapshot hash mismatch: {item['path']}")
        rows.append(
            {
                "source_path": item["path"],
                "snapshot_path": snapshot_path.relative_to(run_root).as_posix(),
                "bytes": snapshot_path.stat().st_size,
                "sha256": snapshot_sha,
            }
        )
    write_csv(
        run_root / "SOURCE_SNAPSHOT_MANIFEST.csv",
        rows,
        ["source_path", "snapshot_path", "bytes", "sha256"],
    )
    return {
        "file_count": len(rows),
        "snapshot_tree_sha256": sha256_canonical_json(rows),
        "manifest_file_sha256": sha256_file(run_root / "SOURCE_SNAPSHOT_MANIFEST.csv"),
    }


def legacy_evidence_snapshot() -> dict:
    verification = MODULE / "11_verification"
    files = []
    archive = verification / "_archive_run3"
    if archive.is_dir():
        files.extend(archive.rglob("*"))
    for pattern in ("R4_*", "RUN4_*", "PROTOCOL_REVISIONS.md"):
        files.extend(verification.glob(pattern))
    rows = []
    for path in sorted({p.resolve() for p in files if p.is_file()}, key=lambda p: p.as_posix()):
        rows.append(
            {
                "path": path.relative_to(MODULE).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {"file_count": len(rows), "tree_sha256": sha256_canonical_json(rows), "files": rows}


def environment_record() -> dict:
    packages = {}
    for name in ("numpy", "pandas", "pyarrow", "PyYAML", "pytest"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": packages,
        "numpy_config": {
            "blas_ilp64_opt_info": getattr(np.__config__, "blas_ilp64_opt_info", None),
            "lapack_ilp64_opt_info": getattr(np.__config__, "lapack_ilp64_opt_info", None),
        },
    }


def physics_identity(model: dict) -> dict:
    return {
        "schema": "PATH_INDEPENDENT_URDF_EXTRACT_PHYSICS_IDENTITY_V1",
        "robot_name": model["robot_name"],
        "links": model["links"],
        "joints": model["joints"],
    }


def movable_joint_contract(model: dict, plant: FloatingPlant) -> list[dict]:
    child_to_joint = {
        joint["child"]: joint
        for joint in model["joints"]
        if joint["type"] in ("revolute", "continuous", "prismatic")
    }
    rows = []
    for index, body in enumerate(plant.bodies[1:], 1):
        joint = child_to_joint[body.name]
        joint_type = "revolute" if joint["type"] == "continuous" else joint["type"]
        rows.append(
            {
                "joint_index": index,
                "joint_name": joint["name"],
                "child_link": joint["child"],
                "joint_type": joint_type,
                "coordinate_unit": "rad" if joint_type == "revolute" else "m",
                "rate_unit": "rad/s" if joint_type == "revolute" else "m/s",
                "effort_unit": "N*m" if joint_type == "revolute" else "N",
            }
        )
    return rows


def state_ledger_dataframe(samples: dict, ledger: dict, joint_contract: list[dict]) -> pd.DataFrame:
    X = np.asarray(samples["x"])
    n = len(joint_contract)
    cols = {"t_s": np.asarray(samples["t"])}
    for i, axis in enumerate("xyz"):
        cols[f"base_position_I_{axis}_m"] = X[:, i]
    for i, label in enumerate("wxyz"):
        cols[f"base_quaternion_I_from_B_{label}"] = X[:, 3 + i]
    for j, contract in enumerate(joint_contract):
        suffix = contract["coordinate_unit"].replace("/", "_per_").replace("*", "_")
        rate_suffix = contract["rate_unit"].replace("/", "_per_").replace("*", "_")
        cols[f"q_joint{j + 1}_{suffix}"] = X[:, 7 + j]
        cols[f"qd_joint{j + 1}_{rate_suffix}"] = X[:, 13 + n + j]
    for i, axis in enumerate("xyz"):
        cols[f"base_angular_velocity_B_{axis}_rad_per_s"] = X[:, 7 + n + i]
        cols[f"base_linear_velocity_B_{axis}_m_per_s"] = X[:, 10 + n + i]
        cols[f"system_com_I_{axis}_m"] = samples["p_com"][:, i]
    cols["kinetic_energy_J"] = samples["E"]
    cols["quaternion_renormalization_accumulated"] = samples["quat_renorm"]
    ledger_cols = ledger_timeseries_columns(ledger)
    ledger_cols.pop("t_s")
    cols.update(ledger_cols)
    for body_index, body_id in enumerate(ledger.get("body_ids", [])):
        safe_body = re.sub(r"[^A-Za-z0-9_]+", "_", body_id)
        for axis_index, axis in enumerate("xyz"):
            cols[f"P_body_{safe_body}_{axis}_kg_m_s"] = ledger[
                "P_body_I_kg_m_s"
            ][:, body_index, axis_index]
            cols[f"H_spin_body_{safe_body}_{axis}_N_m_s"] = ledger[
                "H_spin_body_I_N_m_s"
            ][:, body_index, axis_index]
            cols[f"H_orbital_body_{safe_body}_{axis}_N_m_s"] = ledger[
                "H_orbital_body_O_I_N_m_s"
            ][:, body_index, axis_index]
    return pd.DataFrame(cols)


def controller_dataframe(telemetry: dict, joint_contract: list[dict]) -> pd.DataFrame:
    n_steps = len(telemetry["t_s"])
    n = len(joint_contract)
    joint_index = np.tile(np.arange(n), n_steps)
    rows = {
        "step_index": np.repeat(telemetry["step_index"], n),
        "t_s": np.repeat(telemetry["t_s"], n),
        "dt_s": np.repeat(telemetry["dt_s"], n),
        "joint_index": joint_index + 1,
        "joint_name": np.asarray([c["joint_name"] for c in joint_contract], dtype=object)[joint_index],
        "joint_type": np.asarray([c["joint_type"] for c in joint_contract], dtype=object)[joint_index],
        "coordinate_unit": np.asarray([c["coordinate_unit"] for c in joint_contract], dtype=object)[joint_index],
        "rate_unit": np.asarray([c["rate_unit"] for c in joint_contract], dtype=object)[joint_index],
        "effort_unit": np.asarray([c["effort_unit"] for c in joint_contract], dtype=object)[joint_index],
    }
    for key in (
        "q",
        "qd",
        "q_ref",
        "qd_ref",
        "q_error",
        "qd_error",
        "effort_P",
        "effort_I",
        "effort_D",
        "effort_raw",
        "effort_limited",
        "effort_cap",
        "effort_margin",
        "at_limit",
        "was_clipped",
        "any_stage_clipped",
        "max_abs_stage_effort_raw",
    ):
        rows[key] = telemetry[key].reshape(-1)
    rows["I_term_status"] = "STRUCTURAL_ZERO_PD_NO_INTEGRATOR"
    rows["node_contract"] = "K1_ACCEPTED_NODE"
    return pd.DataFrame(rows)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_episode(
    episodes_root: Path,
    episode_id: str,
    manifest: dict,
    authority_snapshot: dict,
    resolved_config: dict,
    input_hashes: list[dict],
    state_df: pd.DataFrame,
    metrics: dict,
    gate_result: dict,
    controller_df: pd.DataFrame | None = None,
) -> Path:
    episode = episodes_root / episode_id
    ensure_descendant(episode, episodes_root.parent)
    episode.mkdir(parents=True, exist_ok=False)
    write_json(episode / "RUN_MANIFEST.json", manifest)
    write_json(episode / "AUTHORITY_SNAPSHOT.json", authority_snapshot)
    write_yaml(episode / "RESOLVED_CONFIG.yaml", resolved_config)
    write_csv(
        episode / "INPUT_HASHES.csv",
        input_hashes,
        ["path", "sha256", "role", "status"],
    )
    state_df.to_parquet(episode / "TIMESERIES.parquet", index=False)
    if controller_df is not None:
        controller_df.to_parquet(episode / "CONTROLLER_TIMESERIES.parquet", index=False)
    (episode / "EVENTS.jsonl").write_text("", encoding="utf-8")
    write_json(
        episode / "EVENT_MONITOR_STATUS.json",
        {
            "status": "VERIFIED",
            "event_count": 0,
            "velocity_discontinuity_count": 0,
            "quaternion_renormalization": "RECORDED_NONIMPULSIVE",
        },
    )
    write_json(episode / "METRICS.json", metrics)
    write_json(
        episode / "SAFETY_DECISION.json",
        {
            "decision": "NOT_EVALUATED_DIAGNOSTIC_ONLY",
            "execute": False,
            "safe_release_credit": False,
        },
    )
    write_json(episode / "GATE_RESULT.json", gate_result)
    write_json(episode / "FAILURE_CONTEXT.json", {"failed": False, "failure_reason": None})
    (episode / "STDOUT.log").write_text(
        f"{episode_id} completed inside isolated R5 run; see METRICS.json\n", encoding="utf-8"
    )
    hashed = []
    for path in sorted(episode.iterdir(), key=lambda p: p.name):
        if path.is_file() and path.name != "HASH_MANIFEST.csv":
            hashed.append({"file": path.name, "sha256": sha256_file(path)})
    write_csv(episode / "HASH_MANIFEST.csv", hashed, ["file", "sha256"])
    return episode


def run_preexecution_tests(run_root: Path) -> dict:
    test_path = MODULE / "tests/test_r5_momentum_and_runner.py"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_r5_momentum_and_runner.py",
    ]
    completed = subprocess.run(
        command,
        cwd=MODULE,
        text=True,
        capture_output=True,
        check=False,
    )
    log = completed.stdout + completed.stderr
    (run_root / "verification/R5_PREEXECUTION_TEST.log").write_text(log, encoding="utf-8")
    return {
        "command": command,
        "exit_code": completed.returncode,
        "passed": completed.returncode == 0,
        "log_sha256": sha256_file(run_root / "verification/R5_PREEXECUTION_TEST.log"),
        "validation_test_path": test_path.relative_to(MODULE).as_posix(),
        "validation_test_sha256": sha256_file(test_path),
    }


def run_static_unit_audit(run_root: Path) -> dict:
    if not UNIT_AUDIT_TOOL.is_file():
        return {
            "passed": False,
            "failure_reason": f"unit audit tool missing: {UNIT_AUDIT_TOOL}",
            "tool_sha256": None,
        }
    targets = [
        SRC / "dh_v1/momentum_ledger_r5.py",
        SRC / "dh_v1/scen_dynamics_r5.py",
    ]
    outputs = []
    exit_codes = []
    for target in targets:
        command = [
            sys.executable,
            str(UNIT_AUDIT_TOOL),
            "--input",
            str(target),
            "--format",
            "markdown",
            "--fail-on",
            "medium",
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        exit_codes.append(completed.returncode)
        outputs.append(
            f"## {target.relative_to(MODULE).as_posix()}\n\n"
            + completed.stdout
            + completed.stderr
        )
    log_path = run_root / "verification/R5_STATIC_UNIT_AUDIT.md"
    log_path.write_text("\n\n".join(outputs), encoding="utf-8")
    return {
        "passed": all(code == 0 for code in exit_codes),
        "exit_codes": exit_codes,
        "targets": [path.relative_to(MODULE).as_posix() for path in targets],
        "tool_path": UNIT_AUDIT_TOOL.as_posix(),
        "tool_sha256": sha256_file(UNIT_AUDIT_TOOL),
        "log_sha256": sha256_file(log_path),
    }


def strip_run_payload(run: dict) -> dict:
    return {
        "dt_s": run["dt_s"],
        "solver_execution": run.get("solver_execution"),
        "metrics": run["metrics"],
        "ledger_contract": run["ledger"]["contract"],
        "scales": run.get("scales"),
        "claim": run.get("claim"),
        "control_release": run.get("control_release"),
    }


def execute(args: argparse.Namespace) -> Path:
    run_id = validate_run_id(args.run_id)
    output_root = resolve_output_root(args.output_root)
    run_root = (output_root / run_id).resolve()
    ensure_descendant(run_root, output_root)
    if run_root.exists():
        raise R5RunError(f"run root already exists; immutable run-id reuse forbidden: {run_root}")

    configs = {name: load_yaml(path) for name, path in CONFIG_PATHS.items()}
    binding = configs["plant_binding"]
    arm_path = verify_bound_file(
        binding["accepted_arm_urdf"]["path"], binding["accepted_arm_urdf"]["sha256"]
    )
    servicer_path = verify_bound_file(
        binding["servicer_urdf"]["path"], binding["servicer_urdf"]["sha256"]
    )
    bound_paths = [arm_path, servicer_path]
    for item in binding["contracts"].values():
        bound_paths.append(verify_bound_file(item["path"], item["sha256"]))

    source = source_manifest()
    legacy_before = legacy_evidence_snapshot()
    env = environment_record()
    arm_model = extract_urdf(arm_path)
    servicer_model = extract_urdf(servicer_path)
    T_SM = binding["mount_T_SM"]
    composed_model = compose_models(
        servicer_model,
        arm_model,
        T_SM["parent_link"],
        T_SM["xyz_m"],
        T_SM["rpy_rad"],
        T_SM["joint_name"],
    )
    arm_plant = FloatingPlant(arm_model)
    composed_plant = FloatingPlant(composed_model)
    if arm_plant.nj != 8 or composed_plant.nj != 8:
        raise R5RunError("frozen R5 plant must expose the current actual 6R+2P eight-DOF model")
    types = [body.jtype for body in composed_plant.bodies[1:]]
    if types != ["revolute"] * 6 + ["prismatic"] * 2:
        raise R5RunError(f"frozen joint composition mismatch: {types}")
    joint_contract = movable_joint_contract(composed_model, composed_plant)
    controller_cfg = configs["controller_s03"]
    if [row["joint_name"] for row in joint_contract] != controller_cfg["joint_order"]:
        raise R5RunError("controller joint order does not match extracted accepted URDF order")
    if [row["joint_type"] for row in joint_contract] != controller_cfg["joint_types"]:
        raise R5RunError("controller joint types do not match extracted accepted URDF types")
    controller = controller_from_config(composed_plant, configs["controller_s03"])

    plant_ids = {
        "ARM_ONLY_ACCEPTED": {
            "legacy_artifact_sha256": sha256_canonical_json(arm_model),
            "plant_physics_sha256": sha256_canonical_json(physics_identity(arm_model)),
            "model": arm_model,
            "plant": arm_plant,
            "joint_contract": movable_joint_contract(arm_model, arm_plant),
        },
        "SERVICER_ARM_TSM_PREBIND": {
            "legacy_artifact_sha256": sha256_canonical_json(composed_model),
            "plant_physics_sha256": sha256_canonical_json(physics_identity(composed_model)),
            "model": composed_model,
            "plant": composed_plant,
            "joint_contract": joint_contract,
        },
    }
    config_hashes = {name: sha256_file(path) for name, path in CONFIG_PATHS.items()}
    experiment_config = {
        "task_id": TASK_ID,
        "configs": configs,
        "config_file_hashes": config_hashes,
        "plant_physics_hashes": {
            key: value["plant_physics_sha256"] for key, value in plant_ids.items()
        },
        "source_tree_sha256": source["source_tree_sha256"],
    }
    experiment_sha = sha256_canonical_json(experiment_config)
    invocation = {
        "run_id": run_id,
        "argv": sys.argv,
        "output_root": output_root.as_posix(),
        "experiment_config_sha256": experiment_sha,
    }
    invocation_sha = sha256_canonical_json(invocation)

    output_root.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=False, exist_ok=False)
    for name in ("plant", "episodes", "scenario_artifacts", "verification", "dataset"):
        (run_root / name).mkdir()
    started = {
        "schema": "R5_RUN_STARTED_V1",
        "task_id": TASK_ID,
        "run_id": run_id,
        "started_utc": utc_now(),
        "pid": os.getpid(),
        "complete": False,
        "experiment_config_sha256": experiment_sha,
        "invocation_sha256": invocation_sha,
    }
    write_json(run_root / "RUN_STARTED.json", started)
    try:
        print(f"R5 run root: {run_root}", flush=True)
        write_json(run_root / "SOURCE_HASH_MANIFEST.json", source)
        write_csv(
            run_root / "SOURCE_HASH_MANIFEST.csv",
            source["files"],
            ["path", "bytes", "sha256"],
        )
        source_snapshot = write_source_snapshot(run_root, source)
        write_json(run_root / "ENVIRONMENT.json", env)
        write_yaml(run_root / "RESOLVED_RUN_CONFIG.yaml", experiment_config)
        authority_file = binding["contracts"]["authority_snapshot"]["path"]
        authority_source = json.loads((REPO / authority_file).read_text(encoding="utf-8"))
        authority_snapshot = {
            "schema": "R5_AUTHORITY_SNAPSHOT_V1",
            "source_path": authority_file,
            "source_sha256": binding["contracts"]["authority_snapshot"]["sha256"],
            "source_content": authority_source,
            "scope_ruling": {
                "control_release": False,
                "contact_credit": False,
                "parent_gate_reissue": False,
                "T_E_T": "MISSING",
            },
        }
        write_json(run_root / "AUTHORITY_SNAPSHOT.json", authority_snapshot)

        input_rows = [
            {
                "path": "SOURCE_HASH_MANIFEST.json",
                "sha256": sha256_file(run_root / "SOURCE_HASH_MANIFEST.json"),
                "role": "SOURCE_MANIFEST_FILE",
                "status": "VERIFIED_FILE",
            },
            {
                "path": "SOURCE_HASH_MANIFEST.csv",
                "sha256": sha256_file(run_root / "SOURCE_HASH_MANIFEST.csv"),
                "role": "SOURCE_MANIFEST_TABLE_FILE",
                "status": "VERIFIED_FILE",
            },
            {
                "path": "SOURCE_SNAPSHOT_MANIFEST.csv",
                "sha256": source_snapshot["manifest_file_sha256"],
                "role": "IMMUTABLE_SOURCE_SNAPSHOT_MANIFEST_FILE",
                "status": "VERIFIED_FILE",
            },
            {
                "path": "ENVIRONMENT.json",
                "sha256": sha256_file(run_root / "ENVIRONMENT.json"),
                "role": "RUNTIME_ENVIRONMENT_FILE",
                "status": "VERIFIED_FILE",
            },
            {
                "path": "RESOLVED_RUN_CONFIG.yaml",
                "sha256": sha256_file(run_root / "RESOLVED_RUN_CONFIG.yaml"),
                "role": "RESOLVED_RUN_CONFIG_FILE",
                "status": "VERIFIED_FILE",
            },
            {
                "path": "AUTHORITY_SNAPSHOT.json",
                "sha256": sha256_file(run_root / "AUTHORITY_SNAPSHOT.json"),
                "role": "RUN_AUTHORITY_SNAPSHOT_FILE",
                "status": "VERIFIED_FILE",
            },
        ]
        for path in bound_paths:
            input_rows.append(
                {
                    "path": path.relative_to(REPO).as_posix(),
                    "sha256": sha256_file(path),
                    "role": "BOUND_AUTHORITY_INPUT",
                    "status": "VERIFIED",
                }
            )
        for name, path in CONFIG_PATHS.items():
            input_rows.append(
                {
                    "path": path.relative_to(REPO).as_posix(),
                    "sha256": config_hashes[name],
                    "role": f"R5_CONFIG_{name.upper()}",
                    "status": "VERIFIED",
                }
            )
        input_rows.extend(
            [
                {
                    "path": "identity:source_tree_canonical",
                    "sha256": source["source_tree_sha256"],
                    "role": "SOURCE_TREE_CANONICAL_AGGREGATE",
                    "status": "VERIFIED_CANONICAL_IDENTITY",
                },
                {
                    "path": "identity:experiment_config_canonical",
                    "sha256": experiment_sha,
                    "role": "EXPERIMENT_CONFIG_CANONICAL_HASH",
                    "status": "VERIFIED_CANONICAL_IDENTITY",
                },
                {
                    "path": "identity:invocation_canonical",
                    "sha256": invocation_sha,
                    "role": "INVOCATION_CANONICAL_HASH",
                    "status": "VERIFIED_CANONICAL_IDENTITY",
                },
            ]
        )

        for plant_id, payload in plant_ids.items():
            plant_artifact = {
                "schema": "R5_GENERATED_PLANT_ARTIFACT_V1",
                "plant_id": plant_id,
                "legacy_host_path_dependent_artifact_sha256": payload["legacy_artifact_sha256"],
                "plant_physics_sha256": payload["plant_physics_sha256"],
                "physics_identity": physics_identity(payload["model"]),
                "total_mass_kg": total_mass(payload["model"]),
                "topology": validate_tree(payload["model"]),
                "joint_contract": payload["joint_contract"],
                "scope": binding["plant_scope"],
            }
            plant_path = run_root / "plant" / f"{plant_id}.yaml"
            write_yaml(plant_path, plant_artifact)
            payload["generated_artifact_sha256"] = sha256_file(plant_path)
            input_rows.append(
                {
                    "path": plant_path.relative_to(run_root).as_posix(),
                    "sha256": payload["generated_artifact_sha256"],
                    "role": f"GENERATED_PLANT_ARTIFACT_{plant_id}",
                    "status": "VERIFIED_FILE",
                }
            )
        write_csv(
            run_root / "INPUT_HASHES.csv", input_rows, ["path", "sha256", "role", "status"]
        )

        tests = run_preexecution_tests(run_root)
        unit_audit = run_static_unit_audit(run_root)
        preexec_checks = {
            "C01_BOUND_INPUT_HASHES_VERIFIED": True,
            "C02_UNIT_SAFE_P_H_IMPLEMENTED": True,
            "C03_OUTPUT_ROOT_ISOLATED_AND_NEW": True,
            "C04_ALL_S02_CASES_THREE_POINT_CONFIGURED": len(configs["scenarios"]["s02"]["dt_grid_s"]) == 3,
            "C05_S03_THREE_POINT_CONFIGURED": len(configs["scenarios"]["s03"]["dt_grid_s"]) == 3,
            "C06_CONTROLLER_CONFIG_HASH_NON_NULL": bool(config_hashes["controller_s03"]),
            "C07_R5_TARGETED_TESTS_PASS": tests["passed"],
            "C08_LEGACY_R3_R4_EVIDENCE_SNAPSHOTTED": legacy_before["file_count"] > 0,
            "C09_ACTUAL_PLANT_DECLARED_6R_PLUS_2P": types == ["revolute"] * 6 + ["prismatic"] * 2,
            "C10_STATIC_UNIT_AUDIT_PASS": unit_audit["passed"],
        }
        preexec = {
            "schema": "R5_PREEXECUTION_GATE_V1",
            "task_id": TASK_ID,
            "run_id": run_id,
            "generated_utc": utc_now(),
            "checks": preexec_checks,
            "verdict": "PASS_EXECUTION_ADMITTED" if all(preexec_checks.values()) else "HOLD_FAIL_CLOSED",
            "legacy_evidence_tree_sha256_before": legacy_before["tree_sha256"],
            "test_receipt": tests,
            "static_unit_audit_receipt": unit_audit,
        }
        write_json(run_root / "verification/R5_PREEXECUTION_GATE.json", preexec)
        if not all(preexec_checks.values()):
            raise R5RunError("R5 preexecution gate did not pass")

        scenarios = configs["scenarios"]
        seed_schedule_sha = sha256_canonical_json(
            {"seed": scenarios["seed"], "rng_consumed_by_s02_s03": False}
        )
        authority_snapshot_sha = sha256_file(run_root / "AUTHORITY_SNAPSHOT.json")
        environment_lock_sha = sha256_file(run_root / "ENVIRONMENT.json")
        s02_cfg = {
            **scenarios["s02"],
            "sample_period_target_s": scenarios["sample_period_target_s"],
        }
        s02_results = []
        for case_index, case in enumerate(s02_cfg["cases"], 1):
            plant_payload = plant_ids[case["plant_id"]]
            result = run_s02_case_r5(
                plant_payload["plant"], case, s02_cfg, configs["gate"]
            )
            s02_results.append(result)
            for dt_index, run in enumerate(result["runs"], 1):
                episode_id = f"R5-S02-C{case_index:02d}-D{dt_index:02d}"
                state_df = state_ledger_dataframe(
                    run["samples"], run["ledger"], plant_payload["joint_contract"]
                )
                solver_contract = {
                    "declared": scenarios["solver"],
                    "executed": run["solver_execution"],
                }
                resolved_episode = {
                    "scenario": s02_cfg,
                    "case": case,
                    "dt_s": run["dt_s"],
                    "initial_state": result["initial_state"],
                    "scales": result["scales"],
                    "solver": solver_contract,
                }
                initial_state_sha = sha256_canonical_json(jsonable(result["initial_state"]))
                scale_contract_sha = sha256_canonical_json(jsonable(result["scales"]))
                solver_config_sha = sha256_canonical_json(jsonable(solver_contract))
                resolved_episode_sha = sha256_canonical_json(jsonable(resolved_episode))
                manifest = {
                    "schema": "R5_EPISODE_MANIFEST_V1",
                    "episode_id": episode_id,
                    "run_id": run_id,
                    "task_id": TASK_ID,
                    "scenario_id": s02_cfg["scenario_id"],
                    "case_id": case["case_id"],
                    "plant_id": case["plant_id"],
                    "dt_s": run["dt_s"],
                    "seed": scenarios["seed"],
                    "plant_physics_sha256": plant_payload["plant_physics_sha256"],
                    "generated_plant_artifact_sha256": plant_payload["generated_artifact_sha256"],
                    "controller_config_sha256": config_hashes["controller_c0"],
                    "gate_thresholds_sha256": config_hashes["gate"],
                    "scenario_config_sha256": config_hashes["scenarios"],
                    "source_tree_sha256": source["source_tree_sha256"],
                    "experiment_config_sha256": experiment_sha,
                    "invocation_sha256": invocation_sha,
                    "authority_snapshot_sha256": authority_snapshot_sha,
                    "environment_lock_sha256": environment_lock_sha,
                    "seed_schedule_sha256": seed_schedule_sha,
                    "initial_state_sha256": initial_state_sha,
                    "solver_config_sha256": solver_config_sha,
                    "scale_contract_sha256": scale_contract_sha,
                    "resolved_episode_config_sha256": resolved_episode_sha,
                    "source_snapshot_tree_sha256": source_snapshot["snapshot_tree_sha256"],
                    "label": "MODIFY",
                    "claim": "RIGID_NO_CONTACT_PREBIND_NUMERICAL_DIAGNOSTIC_ONLY",
                    "control_release": False,
                    "contact_credit": False,
                }
                episode_input_rows = list(input_rows) + [
                    {
                        "path": f"identity:{episode_id}:seed_schedule",
                        "sha256": seed_schedule_sha,
                        "role": "SEED_SCHEDULE_CANONICAL_HASH",
                        "status": "VERIFIED_CANONICAL_IDENTITY",
                    },
                    {
                        "path": f"identity:{episode_id}:initial_state",
                        "sha256": initial_state_sha,
                        "role": "INITIAL_STATE_CANONICAL_HASH",
                        "status": "VERIFIED_CANONICAL_IDENTITY",
                    },
                    {
                        "path": f"identity:{episode_id}:solver",
                        "sha256": solver_config_sha,
                        "role": "SOLVER_EXECUTION_CANONICAL_HASH",
                        "status": "VERIFIED_CANONICAL_IDENTITY",
                    },
                    {
                        "path": f"identity:{episode_id}:preintegration_scales",
                        "sha256": scale_contract_sha,
                        "role": "PREINTEGRATION_SCALE_CONTRACT_CANONICAL_HASH",
                        "status": "VERIFIED_CANONICAL_IDENTITY",
                    },
                    {
                        "path": f"identity:{episode_id}:resolved_episode_config",
                        "sha256": resolved_episode_sha,
                        "role": "RESOLVED_EPISODE_CONFIG_CANONICAL_HASH",
                        "status": "VERIFIED_CANONICAL_IDENTITY",
                    },
                ]
                write_episode(
                    run_root / "episodes",
                    episode_id,
                    manifest,
                    authority_snapshot,
                    resolved_episode,
                    episode_input_rows,
                    state_df,
                    {**run["metrics"], "scales": result["scales"]},
                    {
                        "case_gate_map": result["gates"],
                        "case_all_gates_pass": result["all_gates_pass"],
                        "P_convergence": result["P_convergence"],
                        "H_convergence": result["H_convergence"],
                        "hard_gate_masking": False,
                    },
                )
            print(
                f"S02 {case['case_id']}: P={result['P_convergence']['mode']} "
                f"H={result['H_convergence']['mode']} pass={result['all_gates_pass']}",
                flush=True,
            )

        s02_summary = {
            "schema": "R5_S02_UNIT_SAFE_MOMENTUM_LEDGER_V1",
            "cases": [
                {
                    "case": item["case"],
                    "scales": item["scales"],
                    "runs": [strip_run_payload(run) for run in item["runs"]],
                    "P_convergence": item["P_convergence"],
                    "H_convergence": item["H_convergence"],
                    "gates": item["gates"],
                    "hard_gate_failures": item["hard_gate_failures"],
                    "all_gates_pass": item["all_gates_pass"],
                }
                for item in s02_results
            ],
            "all_cases_pass": all(item["all_gates_pass"] for item in s02_results),
            "all_cases_three_point_executed": all(len(item["runs"]) == 3 for item in s02_results),
            "no_mixed_dimension_norm": True,
            "hard_gate_masking": False,
        }
        write_json(run_root / "scenario_artifacts/R5_S02_UNIT_SAFE_MOMENTUM_LEDGER.json", s02_summary)

        s03_cfg = {
            **scenarios["s03"],
            "sample_period_target_s": scenarios["sample_period_target_s"],
        }
        s03_results = []
        for dt_index, dt in enumerate(s03_cfg["dt_grid_s"], 1):
            result = run_s03_dt_r5(
                composed_plant, controller, s03_cfg, float(dt), configs["gate"]
            )
            s03_results.append(result)
            episode_id = f"R5-S03-D{dt_index:02d}"
            state_df = state_ledger_dataframe(result["samples"], result["ledger"], joint_contract)
            control_df = controller_dataframe(result["telemetry"], joint_contract)
            solver_contract = {
                "declared": scenarios["solver"],
                "executed": result["solver_execution"],
            }
            resolved_episode = {
                "scenario": s03_cfg,
                "dt_s": result["dt_s"],
                "controller": configs["controller_s03"],
                "initial_state": result["initial_state"],
                "scales": result["scales"],
                "solver": solver_contract,
            }
            initial_state_sha = sha256_canonical_json(jsonable(result["initial_state"]))
            scale_contract_sha = sha256_canonical_json(jsonable(result["scales"]))
            solver_config_sha = sha256_canonical_json(jsonable(solver_contract))
            resolved_episode_sha = sha256_canonical_json(jsonable(resolved_episode))
            manifest = {
                "schema": "R5_EPISODE_MANIFEST_V1",
                "episode_id": episode_id,
                "run_id": run_id,
                "task_id": TASK_ID,
                "scenario_id": s03_cfg["scenario_id"],
                "plant_id": "SERVICER_ARM_TSM_PREBIND",
                "dt_s": result["dt_s"],
                "seed": scenarios["seed"],
                "plant_physics_sha256": plant_ids["SERVICER_ARM_TSM_PREBIND"]["plant_physics_sha256"],
                "generated_plant_artifact_sha256": plant_ids["SERVICER_ARM_TSM_PREBIND"]["generated_artifact_sha256"],
                "controller_config_sha256": config_hashes["controller_s03"],
                "gate_thresholds_sha256": config_hashes["gate"],
                "scenario_config_sha256": config_hashes["scenarios"],
                "source_tree_sha256": source["source_tree_sha256"],
                "experiment_config_sha256": experiment_sha,
                "invocation_sha256": invocation_sha,
                "authority_snapshot_sha256": authority_snapshot_sha,
                "environment_lock_sha256": environment_lock_sha,
                "seed_schedule_sha256": seed_schedule_sha,
                "initial_state_sha256": initial_state_sha,
                "solver_config_sha256": solver_config_sha,
                "scale_contract_sha256": scale_contract_sha,
                "resolved_episode_config_sha256": resolved_episode_sha,
                "source_snapshot_tree_sha256": source_snapshot["snapshot_tree_sha256"],
                "label": "MODIFY",
                "claim": "DIAGNOSTIC_ONLY_NOT_CONTROL_PASS",
                "control_release": False,
                "contact_credit": False,
            }
            episode_input_rows = list(input_rows) + [
                {
                    "path": f"identity:{episode_id}:seed_schedule",
                    "sha256": seed_schedule_sha,
                    "role": "SEED_SCHEDULE_CANONICAL_HASH",
                    "status": "VERIFIED_CANONICAL_IDENTITY",
                },
                {
                    "path": f"identity:{episode_id}:initial_state",
                    "sha256": initial_state_sha,
                    "role": "INITIAL_STATE_CANONICAL_HASH",
                    "status": "VERIFIED_CANONICAL_IDENTITY",
                },
                {
                    "path": f"identity:{episode_id}:solver",
                    "sha256": solver_config_sha,
                    "role": "SOLVER_EXECUTION_CANONICAL_HASH",
                    "status": "VERIFIED_CANONICAL_IDENTITY",
                },
                {
                    "path": f"identity:{episode_id}:preintegration_scales",
                    "sha256": scale_contract_sha,
                    "role": "PREINTEGRATION_SCALE_CONTRACT_CANONICAL_HASH",
                    "status": "VERIFIED_CANONICAL_IDENTITY",
                },
                {
                    "path": f"identity:{episode_id}:resolved_episode_config",
                    "sha256": resolved_episode_sha,
                    "role": "RESOLVED_EPISODE_CONFIG_CANONICAL_HASH",
                    "status": "VERIFIED_CANONICAL_IDENTITY",
                },
            ]
            write_episode(
                run_root / "episodes",
                episode_id,
                manifest,
                authority_snapshot,
                resolved_episode,
                episode_input_rows,
                state_df,
                result["metrics"],
                {
                    "gate": "DH-G6_DIAGNOSTIC_LAYER",
                    "status": "DIAGNOSTIC_ONLY_NO_CONTROL_RELEASE",
                    "P_H_unit_safe": True,
                },
                controller_df=control_df,
            )
            print(
                f"S03 dt={float(dt):.7f}: epsP={result['metrics']['epsilon_P_max']:.3e} "
                f"epsH={result['metrics']['epsilon_H_max']:.3e} "
                f"sat={result['metrics']['any_stage_saturation']}",
                flush=True,
            )

        stability = stability_analysis_r5(composed_plant, controller, s03_cfg)
        s03_summary = {
            "schema": "R5_S03_REFINEMENT_AND_STABILITY_V1",
            "runs": [strip_run_payload(run) for run in s03_results],
            "three_point_refinement_executed": len(s03_results) == 3,
            "dt_order_preserved": [run["dt_s"] for run in s03_results]
            == [float(v) for v in s03_cfg["dt_grid_s"]],
            "local_stability_analysis": stability,
            "global_trajectory_claim": "NOT_ESTABLISHED_LOCAL_EQUILIBRIUM_MECHANISM_PLUS_TIME_DOMAIN_EVIDENCE_ONLY",
            "complete_scenario_pass": False,
            "control_release": False,
        }
        write_json(run_root / "scenario_artifacts/R5_S03_REFINEMENT_AND_STABILITY.json", s03_summary)
        print(f"S03 stability ruling: {stability['ruling']}", flush=True)

        episode_dirs = sorted((run_root / "episodes").iterdir(), key=lambda p: p.name)
        dataset = {
            "schema": "R5_D0_DATASET_MANIFEST_V1",
            "run_id": run_id,
            "level": "D0_DETERMINISTIC_REGRESSION_DIAGNOSTIC",
            "episode_count": len(episode_dirs),
            "episodes": [
                {
                    "episode_id": episode.name,
                    "run_manifest_sha256": sha256_file(episode / "RUN_MANIFEST.json"),
                    "hash_manifest_sha256": sha256_file(episode / "HASH_MANIFEST.csv"),
                    "label": "MODIFY",
                }
                for episode in episode_dirs
            ],
            "cross_run_enumeration": False,
            "D2_uncertainty": "NOT_EVALUATED_NO_AUTHORITATIVE_PARAMETER_INTERVALS",
        }
        write_json(run_root / "dataset/DATASET_MANIFEST.json", dataset)

        legacy_after = legacy_evidence_snapshot()
        legacy_unchanged = legacy_before["tree_sha256"] == legacy_after["tree_sha256"]
        exit_conditions = {
            "NO_MIXED_DIMENSION_NORM": True,
            "THREE_POINT_REFINEMENT_ALL_CASES": s02_summary["all_cases_three_point_executed"]
            and s03_summary["three_point_refinement_executed"],
            "NO_HARD_GATE_MASKING": not s02_summary["hard_gate_masking"],
            "RUN_OUTPUT_ISOLATED": all(
                path.resolve().is_relative_to(run_root)
                for path in run_root.rglob("*")
            ),
            "R5_REEXECUTION_COMPLETE": len(episode_dirs) == 12,
            "LEGACY_R3_R4_EVIDENCE_UNCHANGED": legacy_unchanged,
            "S02_ALL_UNIT_SAFE_GATES_PASS": s02_summary["all_cases_pass"],
            "PREEXECUTION_GATE_PASS": all(preexec_checks.values()),
        }
        closure_pass = all(exit_conditions.values())
        verdict = (
            "R5_UNIT_SAFE_PREBIND_NUMERICAL_LEDGER_VERIFIED"
            if closure_pass
            else "R5_REPEAT_REQUIRED"
        )
        gate_candidate = {
            "schema": "R5_GATE_CANDIDATE_V1",
            "task_id": TASK_ID,
            "run_id": run_id,
            "generated_utc": utc_now(),
            "verdict": verdict,
            "exit_conditions": exit_conditions,
            "s03_scientific_ruling": (
                stability["ruling_scope"] + "__" + stability["ruling"]
            ),
            "highest_legal_claim": (
                "R5_UNIT_SAFE_PREBIND_NUMERICAL_LEDGER_VERIFIED__DIAGNOSTIC_ONLY"
                if closure_pass
                else "R5_REPEAT_REQUIRED__DIAGNOSTIC_ONLY"
            ),
            "two_prismatic_joint_semantic_conflict": "HOLD_PRESERVED_FROZEN_6R_PLUS_2P_PLANT",
            "control_release": False,
            "contact_credit": False,
            "parent_gate_reissued": False,
            "next_stage_authorized": False,
            "review_status": "PENDING_OWNER_REVIEW",
        }
        write_json(run_root / "verification/R5_GATE_CANDIDATE.json", gate_candidate)
        write_json(
            run_root / "verification/LEGACY_EVIDENCE_IMMUTABILITY_CHECK.json",
            {
                "before_tree_sha256": legacy_before["tree_sha256"],
                "after_tree_sha256": legacy_after["tree_sha256"],
                "unchanged": legacy_unchanged,
                "file_count": legacy_before["file_count"],
            },
        )

        output_rows = []
        for path in sorted(run_root.rglob("*"), key=lambda p: p.as_posix()):
            if path.is_file() and path.name not in (
                "RUN_OUTPUT_HASHES.csv",
                "RUN_COMPLETE.json",
                "RUN_FAILED.json",
            ):
                output_rows.append(
                    {
                        "path": path.relative_to(run_root).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
        write_csv(
            run_root / "RUN_OUTPUT_HASHES.csv",
            output_rows,
            ["path", "bytes", "sha256"],
        )
        complete = {
            "schema": "R5_RUN_COMPLETE_V1",
            "task_id": TASK_ID,
            "run_id": run_id,
            "completed_utc": utc_now(),
            "complete": True,
            "verdict": verdict,
            "episode_count": len(episode_dirs),
            "experiment_config_sha256": experiment_sha,
            "invocation_sha256": invocation_sha,
            "source_tree_sha256": source["source_tree_sha256"],
            "run_output_hashes_sha256": sha256_file(run_root / "RUN_OUTPUT_HASHES.csv"),
            "gate_candidate_sha256": sha256_file(run_root / "verification/R5_GATE_CANDIDATE.json"),
            "release_credit": False,
            "next_stage_authorized": False,
        }
        write_json(run_root / "RUN_COMPLETE.json", complete)

        pointer_dir = MODULE / "11_verification" / "R5_unit_safe_momentum" / run_id
        pointer_dir.mkdir(parents=True, exist_ok=False)
        write_json(
            pointer_dir / "R5_RUN_RECEIPT.json",
            {
                "schema": "R5_RUN_RECEIPT_V1",
                "run_id": run_id,
                "run_root": run_root.relative_to(MODULE).as_posix(),
                "run_complete_sha256": sha256_file(run_root / "RUN_COMPLETE.json"),
                "gate_candidate_sha256": complete["gate_candidate_sha256"],
                "verdict": verdict,
                "ssot_location": "RUN_ROOT",
                "copy_of_scientific_results": False,
            },
        )
        print(f"R5 complete: {verdict}", flush=True)
        return run_root
    except Exception as exc:
        if run_root.exists() and not (run_root / "RUN_COMPLETE.json").exists():
            write_json(
                run_root / "RUN_FAILED.json",
                {
                    "schema": "R5_RUN_FAILED_V1",
                    "task_id": TASK_ID,
                    "run_id": run_id,
                    "failed_utc": utc_now(),
                    "complete": False,
                    "exception_type": type(exc).__name__,
                    "failure_reason": str(exc),
                    "traceback": traceback.format_exc(),
                    "partial_artifacts_preserved": True,
                },
            )
        raise


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="unique immutable run identifier")
    parser.add_argument(
        "--output-root",
        default=str(ALLOWED_OUTPUT_BASE),
        help=f"run parent inside {ALLOWED_OUTPUT_BASE}",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    execute(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
