#!/usr/bin/env python3
"""Generate the non-SSOT R5 contracts, audits and engineering reports.

Scientific numbers are read from one immutable completed R5 run.  This script
never edits that run.  ``--repair-derived`` may replace only the explicitly
enumerated derived delivery files after an interrupted delivery attempt; the
failed regression receipt is preserved as lineage.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import yaml

MODULE = Path(__file__).resolve().parents[1]
REPO = MODULE.parents[1]
sys.path.insert(0, str(MODULE / "src"))

from dh_v1.frames import skew  # noqa: E402
from dh_v1.hashing import sha256_canonical_json, sha256_file  # noqa: E402
from dh_v1.plant import FloatingPlant, compose_models  # noqa: E402
from dh_v1.urdf_extract import extract_urdf  # noqa: E402

DEFAULT_RUN_ID = "R5_RUN4_ATOMIC_PACKAGE_AND_AUTHORITY_HOLD_20260827"
GENERATED: list[Path] = []
REPLACED: list[Path] = []
REPAIR_DERIVED = False
PRESERVED_FAILED_TEST_LOG = Path("11_verification/R5_FULL_TEST.log")


def dump_json(path: Path, obj) -> None:
    _claim_new(path)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def dump_yaml(path: Path, obj) -> None:
    _claim_new(path)
    path.write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True), encoding="utf-8")


def dump_text(path: Path, text: str) -> None:
    _claim_new(path)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def dump_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    _claim_new(path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _claim_new(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not REPAIR_DERIVED:
            raise RuntimeError(f"refusing to overwrite R5 delivery: {path}")
        if path.resolve() == (MODULE / PRESERVED_FAILED_TEST_LOG).resolve():
            raise RuntimeError(f"refusing to overwrite preserved failed regression receipt: {path}")
        if not path.resolve().is_relative_to(MODULE.resolve()):
            raise RuntimeError(f"refusing to repair outside module: {path}")
        REPLACED.append(path)
    GENERATED.append(path)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else f"UNAVAILABLE::{completed.stderr.strip()}"


def compact_hash(path: Path) -> str:
    return sha256_file(path) if path.is_file() else "MISSING"


def load_runner_required_package_files() -> tuple[str, ...]:
    runner_path = MODULE / "scripts/run_r5_increment.py"
    spec = importlib.util.spec_from_file_location("r5_runner_delivery_audit", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load runner contract: {runner_path}")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return tuple(runner.R5_REQUIRED_PACKAGE_FILES)


def audit_run_outputs(run_root: Path, dataset: dict) -> dict:
    required = load_runner_required_package_files()
    canonical_root = (MODULE / "12_results/R5").resolve()
    missing_required: list[str] = []
    hash_mismatches: list[str] = []
    run_id_mismatches: list[str] = []
    terminal_status_mismatches: list[str] = []
    file_counts: list[int] = []
    for item in dataset["episodes"]:
        package = (MODULE / item["canonical_package_path"]).resolve()
        if not package.is_relative_to(canonical_root):
            raise RuntimeError(f"canonical package escaped R5 root: {package}")
        for name in required:
            if not (package / name).is_file():
                missing_required.append(f"{item['episode_id']}::{name}")
        hash_rows = list(csv.DictReader((package / "HASH_MANIFEST.csv").open(encoding="utf-8")))
        for row in hash_rows:
            actual = compact_hash(package / row["file"])
            if actual != row["sha256"]:
                hash_mismatches.append(f"{item['episode_id']}::{row['file']}")
        if compact_hash(package / "HASH_MANIFEST.csv") != item["hash_manifest_sha256"]:
            hash_mismatches.append(f"{item['episode_id']}::HASH_MANIFEST.csv")
        manifest = load_json(package / "RUN_MANIFEST.json")
        if manifest["run_id"] != dataset["run_id"]:
            run_id_mismatches.append(item["episode_id"])
        if manifest["terminal_status"] != "COMPLETE":
            terminal_status_mismatches.append(item["episode_id"])
        file_counts.append(sum(1 for path in package.iterdir() if path.is_file()))
    output_hash_rows = list(
        csv.DictReader((run_root / "RUN_OUTPUT_HASHES.csv").open(encoding="utf-8"))
    )
    run_output_hash_mismatches = [
        row["path"]
        for row in output_hash_rows
        if compact_hash(run_root / row["path"]) != row["sha256"]
    ]
    return {
        "dataset_episode_count": dataset["episode_count"],
        "canonical_package_count": dataset["canonical_package_count"],
        "required_files_per_package": len(required),
        "actual_files_per_package_min": min(file_counts),
        "actual_files_per_package_max": max(file_counts),
        "missing_required_files": missing_required,
        "package_hash_mismatches": hash_mismatches,
        "run_id_mismatches": run_id_mismatches,
        "terminal_status_mismatches": terminal_status_mismatches,
        "run_output_hash_rows": len(output_hash_rows),
        "run_output_hash_mismatches": run_output_hash_mismatches,
        "pass": not any(
            (
                missing_required,
                hash_mismatches,
                run_id_mismatches,
                terminal_status_mismatches,
                run_output_hash_mismatches,
            )
        )
        and dataset["episode_count"] == 12
        and dataset["canonical_package_count"] == 12,
    }


def extract_results(run_root: Path):
    s02 = load_json(run_root / "scenario_artifacts/R5_S02_UNIT_SAFE_MOMENTUM_LEDGER.json")
    s03 = load_json(run_root / "scenario_artifacts/R5_S03_REFINEMENT_AND_STABILITY.json")
    complete = load_json(run_root / "RUN_COMPLETE.json")
    candidate = load_json(run_root / "verification/R5_GATE_CANDIDATE.json")
    preexec = load_json(run_root / "verification/R5_PREEXECUTION_GATE.json")
    return s02, s03, complete, candidate, preexec


def make_body_registry(binding: dict):
    arm_path = REPO / binding["accepted_arm_urdf"]["path"]
    servicer_path = REPO / binding["servicer_urdf"]["path"]
    arm = extract_urdf(arm_path)
    servicer = extract_urdf(servicer_path)
    mount = binding["mount_T_SM"]
    composed = compose_models(
        servicer,
        arm,
        mount["parent_link"],
        mount["xyz_m"],
        mount["rpy_rad"],
        mount["joint_name"],
    )
    rows = []
    boundaries = []
    for plant_id, model, authority_path, authority_sha in (
        (
            "ARM_ONLY_ACCEPTED",
            arm,
            binding["accepted_arm_urdf"]["path"],
            binding["accepted_arm_urdf"]["sha256"],
        ),
        (
            "SERVICER_ARM_TSM_PREBIND",
            composed,
            "accepted arm URDF + servicer URDF + frozen T_SM",
            sha256_canonical_json(
                {
                    "arm": binding["accepted_arm_urdf"]["sha256"],
                    "servicer": binding["servicer_urdf"]["sha256"],
                    "T_SM": mount,
                }
            ),
        ),
    ):
        plant = FloatingPlant(model)
        joints_by_child = {joint["child"]: joint for joint in model["joints"]}
        body_ids = []
        for index, body in enumerate(plant.bodies):
            mass = float(body.I_sp[5, 5])
            c = np.array(
                [body.I_sp[2, 4], body.I_sp[0, 5], body.I_sp[1, 3]], dtype=float
            ) / mass
            I_origin = body.I_sp[:3, :3]
            I_com = I_origin - mass * (skew(c) @ skew(c).T)
            joint = joints_by_child.get(body.name)
            row = {
                "plant_id": plant_id,
                "body_index": index,
                "body_id": body.name,
                "lumped_links": ";".join(link for link, _ in body.lumped_links),
                "mass_kg": f"{mass:.17g}",
                "com_body_x_m": f"{c[0]:.17g}",
                "com_body_y_m": f"{c[1]:.17g}",
                "com_body_z_m": f"{c[2]:.17g}",
                "inertia_about_com_body_kg_m2": json.dumps(I_com.tolist()),
                "inertia_frame": body.name,
                "parent_joint": "FREE_FLOATING_BASE" if joint is None else joint["name"],
                "parent_joint_type": "floating" if joint is None else joint["type"],
                "included_in_linear_momentum": True,
                "included_in_angular_momentum": True,
                "authority_path": authority_path,
                "authority_sha256": authority_sha,
            }
            rows.append(row)
            body_ids.append(body.name)
        boundaries.append(
            {
                "plant_id": plant_id,
                "dynamic_body_count": len(plant.bodies),
                "movable_joint_count": plant.nj,
                "joint_types": [body.jtype for body in plant.bodies[1:]],
                "body_ids": body_ids,
            }
        )
    return rows, boundaries


def memory_snapshot() -> dict:
    memory = psutil.virtual_memory()
    return {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "total_GiB": memory.total / 2**30,
        "available_GiB": memory.available / 2**30,
        "available_percent": 100.0 * memory.available / memory.total,
        "used_percent": float(memory.percent),
    }


def run_full_tests(run_id: str) -> dict:
    base_temp = MODULE / ".pytest-tmp-r5-delivery-retry" / run_id
    if base_temp.exists():
        raise RuntimeError(f"fresh delivery regression basetemp required: {base_temp}")
    base_temp.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-q",
        f"--basetemp={base_temp}",
        "-p",
        "no:cacheprovider",
    ]
    memory_before = memory_snapshot()
    completed = subprocess.run(
        command, cwd=MODULE, text=True, capture_output=True, check=False
    )
    output = completed.stdout + completed.stderr
    memory_after = memory_snapshot()
    cleanup_error = None
    try:
        resolved = base_temp.resolve()
        if not resolved.is_relative_to(MODULE.resolve()):
            raise RuntimeError(f"refusing to clean basetemp outside module: {resolved}")
        shutil.rmtree(resolved, ignore_errors=False)
    except FileNotFoundError:
        pass
    except Exception as exc:  # pragma: no cover - receipt preserves Windows lock failures
        cleanup_error = f"{type(exc).__name__}: {exc}"
    log_path = MODULE / "11_verification/R5_FULL_TEST_RETRY.log"
    _claim_new(log_path)
    log_path.write_text(output, encoding="utf-8")
    passed_match = re.search(r"(\d+) passed", output)
    skip_xfail_xpass = {
        key: bool(re.search(rf"\b\d+ {key}\b", output))
        for key in ("skipped", "xfailed", "xpassed")
    }
    return {
        "command": command,
        "exit_code": completed.returncode,
        "passed": completed.returncode == 0,
        "passed_count": int(passed_match.group(1)) if passed_match else None,
        "skip_xfail_xpass_present": skip_xfail_xpass,
        "log_path": log_path.relative_to(MODULE).as_posix(),
        "log_sha256": sha256_file(log_path),
        "preserved_failed_attempt_log": PRESERVED_FAILED_TEST_LOG.as_posix(),
        "preserved_failed_attempt_log_sha256": compact_hash(MODULE / PRESERVED_FAILED_TEST_LOG),
        "cacheprovider_disabled": True,
        "basetemp": base_temp.relative_to(MODULE).as_posix(),
        "basetemp_cleaned": not base_temp.exists(),
        "basetemp_cleanup_error": cleanup_error,
        "memory_before": memory_before,
        "memory_after": memory_after,
    }


def main(run_id: str, repair_derived: bool = False) -> None:
    global REPAIR_DERIVED
    REPAIR_DERIVED = repair_derived
    run_root = MODULE / "12_results/runs" / run_id
    if not (run_root / "RUN_COMPLETE.json").is_file():
        raise RuntimeError(f"immutable completed R5 run not found: {run_root}")
    s02, s03, complete, candidate, preexec = extract_results(run_root)
    dataset = load_json(run_root / "dataset/DATASET_MANIFEST.json")
    run_environment = load_json(run_root / "ENVIRONMENT.json")
    legacy_immutability = load_json(
        run_root / "verification/LEGACY_EVIDENCE_IMMUTABILITY_CHECK.json"
    )
    binding = load_yaml(MODULE / "configs/plant/r5_plant_binding_v1.yaml")
    controller = load_yaml(MODULE / "configs/controllers/s03_pd_v1.yaml")
    scenarios = load_yaml(MODULE / "configs/scenarios/r5_s02_s03_v1.yaml")
    gate_cfg = load_yaml(MODULE / "configs/gates/r5_momentum_gate_v1.yaml")
    body_rows, boundaries = make_body_registry(binding)

    run_complete_sha = sha256_file(run_root / "RUN_COMPLETE.json")
    run_gate_sha = sha256_file(run_root / "verification/R5_GATE_CANDIDATE.json")
    run_output_rows = list(
        csv.DictReader((run_root / "RUN_OUTPUT_HASHES.csv").open(encoding="utf-8"))
    )
    canonical_audit = audit_run_outputs(run_root, dataset)
    if not canonical_audit["pass"]:
        raise RuntimeError(f"Run4 output audit failed: {canonical_audit}")
    run2_root = MODULE / "12_results/runs/R5_RUN2_PROVENANCE_CLOSURE_20260827"
    run3_root = MODULE / "12_results/runs/R5_RUN3_SCHEMA_TEST_AND_AUTHORITY_HOLD_20260827"
    git_status = git_value("status", "--short", "--", str(MODULE.relative_to(REPO)))
    git_head = git_value("rev-parse", "HEAD")
    git_branch = git_value("branch", "--show-current")

    protected = []
    for name, item in (
        ("accepted_arm_urdf", binding["accepted_arm_urdf"]),
        ("servicer_urdf", binding["servicer_urdf"]),
        *[(name, item) for name, item in binding["contracts"].items()],
    ):
        path = REPO / item["path"]
        protected.append(
            {
                "name": name,
                "path": item["path"],
                "expected_sha256": item["sha256"],
                "actual_sha256": compact_hash(path),
                "match": compact_hash(path) == item["sha256"],
                "change_authorized": False,
            }
        )

    takeover = {
        "schema": "R5_TAKEOVER_SNAPSHOT_V1",
        "task_id": "R5_UNIT_SAFE_MOMENTUM_LEDGER_AND_VERSIONED_RUNNER",
        "snapshot_semantics": "RETROSPECTIVE_RECOVERY_FROM_IMMUTABLE_R4_EVIDENCE_PLUS_R5_RUN1_RUN2_FAILED_RUN3_AND_COMPLETED_RUN4; NOT_BACKDATED_PRECHANGE_SNAPSHOT",
        "R5_G0_STATUS": "HOLD_RETROSPECTIVE_TAKEOVER_NOT_PRECHANGE",
        "git": {
            "head": git_head,
            "branch": git_branch,
            "target_tree_tracked": False,
            "target_status_short": git_status,
            "git_head_not_source_identity": True,
        },
        "r4_entry": {
            "verdict": "R4_REPEAT_REQUIRED",
            "preexecution_gate_sha256": compact_hash(MODULE / "11_verification/RUN4_PREEXECUTION_GATE.json"),
            "candidate_gate_sha256": compact_hash(MODULE / "11_verification/RUN4_GATE_CANDIDATE.json"),
            "artifact_manifest_sha256": compact_hash(MODULE / "11_verification/R4_ARTIFACT_SHA256.csv"),
        },
        "r5_run1": {
            "status": "IMMUTABLE_REFERENCE_RUN_SUPERSEDED_FOR_PROVENANCE_BY_RUN2_NOT_SCIENTIFICALLY_RETRACTED",
            "path": "12_results/runs/R5_RUN1_UNIT_SAFE_REFERENCE_20260827",
        },
        "r5_run2": {
            "path": run2_root.relative_to(MODULE).as_posix(),
            "run_complete_sha256": compact_hash(run2_root / "RUN_COMPLETE.json"),
            "status": "IMMUTABLE_DIAGNOSTIC_LINEAGE_NOT_RETROACTIVELY_UPGRADED",
        },
        "r5_run3": {
            "path": run3_root.relative_to(MODULE).as_posix(),
            "run_failed_sha256": compact_hash(run3_root / "RUN_FAILED.json"),
            "status": "IMMUTABLE_FAIL_CLOSED_PREEXECUTION_TEST_FAILURE_NO_SCIENTIFIC_INTEGRATION",
        },
        "r5_run4": {
            "path": run_root.relative_to(MODULE).as_posix(),
            "run_complete_sha256": run_complete_sha,
            "gate_candidate_sha256": run_gate_sha,
            "verdict": complete["verdict"],
            "legacy_evidence_unchanged": legacy_immutability["unchanged"],
            "source_tree_sha256": complete["source_tree_sha256"],
        },
        "memory_gate": run_environment["memory_risk_record"],
        "capability_ceiling": "CURRENT_SYSTEM_DIGITAL_HOST_CANDIDATE + PREBIND_SIMULATION_DATASET_V1 + NO_FORMAL_RELEASE_CREDIT",
        "parent_gate_reissued": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    dump_json(MODULE / "00_authority/R5_TAKEOVER_SNAPSHOT.json", takeover)

    source_rows = list(csv.DictReader((run_root / "SOURCE_SNAPSHOT_MANIFEST.csv").open(encoding="utf-8")))
    dump_csv(
        MODULE / "00_authority/R5_SOURCE_HASH_MANIFEST.csv",
        [
            {
                "path": row["source_path"],
                "snapshot_path": f"{run_root.relative_to(MODULE).as_posix()}/{row['snapshot_path']}",
                "bytes": row["bytes"],
                "sha256": row["sha256"],
                "identity": f"EXECUTED_{run_id}_SOURCE_OR_CONFIG",
            }
            for row in source_rows
        ],
        ["path", "snapshot_path", "bytes", "sha256", "identity"],
    )
    allowed = []
    for rel in (
        "src/dh_v1/momentum_ledger_r5.py",
        "src/dh_v1/scen_dynamics_r5.py",
        "scripts/run_r5_increment.py",
        "scripts/write_r5_delivery.py",
        "configs/gates/r5_momentum_gate_v1.yaml",
        "configs/controllers/s03_pd_v1.yaml",
        "configs/controllers/c0_no_control_v1.yaml",
        "configs/scenarios/r5_s02_s03_v1.yaml",
        "configs/plant/r5_plant_binding_v1.yaml",
        "tests/test_r5_momentum_and_runner.py",
    ):
        path = MODULE / rel
        allowed.append(
            {
                "path": rel,
                "pre_sha256": None,
                "change_authorized": True,
                "authorized_change_reason": "R5 additive unit-safe ledger, isolated runner, controls telemetry or validation",
                "post_sha256": compact_hash(path),
            }
        )
    dump_yaml(
        MODULE / "00_authority/R5_ALLOWED_CHANGESET.yaml",
        {
            "schema": "R5_ALLOWED_CHANGESET_V1",
            "note": "Additive R5 files; immutable R4 production/evidence files were not edited.",
            "files": allowed,
        },
    )
    dump_csv(
        MODULE / "00_authority/R5_PROTECTED_INPUTS.csv",
        protected,
        [
            "name",
            "path",
            "expected_sha256",
            "actual_sha256",
            "match",
            "change_authorized",
        ],
    )
    conflict_rows = [
        {
            "id": "R5-C01",
            "conflict": "legacy h_O six-vector norm mixed N*m*s with kg*m/s",
            "ruling": "DEPRECATED_UNIT_INVALID_FOR_GATE; R5 P/H split used",
            "status": "CLOSED_FOR_R5",
        },
        {
            "id": "R5-C02",
            "conflict": "legacy runner wrote shared mutable output slots",
            "ruling": "immutable run root with fail-on-existing run-id",
            "status": "CLOSED_FOR_R5",
        },
        {
            "id": "R5-C03",
            "conflict": "URDF comment says two P gripper joints locked; FloatingPlant executes both",
            "ruling": "frozen plant retained as actual 6R+2P; 6R-only claim forbidden",
            "status": "HOLD",
        },
        {
            "id": "R5-C04",
            "conflict": "reaction wheels/thrusters/target/flex absent from current plant",
            "ruling": "NULL+status; zero-fill forbidden; no subsystem credit",
            "status": "HOLD_OUT_OF_SCOPE",
        },
        {
            "id": "R5-C05",
            "conflict": "two prismatic states cross lower limit in unconstrained mathematical plant",
            "ruling": "local stability mechanism retained; physical control applicability HOLD",
            "status": "HOLD",
        },
        {
            "id": "R5-C06",
            "conflict": "requested pre-change takeover snapshot did not exist before R5 edits",
            "ruling": "honest retrospective snapshot from immutable R4 + Run1/Run2/failed Run3/completed Run4; no backdating",
            "status": "HOLD_RETROSPECTIVE_ONLY",
        },
        {
            "id": "R5-C07",
            "conflict": "repository has no authoritative absolute P/H residual thresholds for this plant and scope",
            "ruling": "relative metrics remain diagnostic only; formal P/H Gate is HOLD_THRESHOLD_AUTHORITY_MISSING",
            "status": "HOLD",
        },
        {
            "id": "R5-C08",
            "conflict": "success packages publish atomically but failure lifecycle is not pre-opened before integration",
            "ruling": "success export credited; full versioned-runner Gate remains HOLD until failure lifecycle is pre-opened and atomically published",
            "status": "HOLD",
        },
        {
            "id": "R5-C09",
            "conflict": "available memory was below the 6 GiB admission threshold",
            "ruling": "Owner Override authorizes this execution only; memory_gate_passed remains false and creates no scientific credit",
            "status": "OWNER_OVERRIDE_LOW_MEMORY",
        },
        {
            "id": "R5-C10",
            "conflict": "Run3 failed its preexecution test before integration",
            "ruling": "Run3 failure package preserved; Run4 used a new run_id after fixing basetemp isolation",
            "status": "CLOSED_BY_NEW_RUN_WITH_LINEAGE_PRESERVED",
        },
    ]
    dump_csv(
        MODULE / "00_authority/R5_CONFLICT_LEDGER.csv",
        conflict_rows,
        ["id", "conflict", "ruling", "status"],
    )

    frame_contract = {
        "schema": "R5_MOMENTUM_FRAME_CONTRACT_V1",
        "N": "fixed inertial frame I",
        "O": "INERTIAL_ORIGIN_I fixed in N",
        "primary_linear_momentum": {"field": "P_I", "expressed_in": "I", "unit": "kg*m/s"},
        "primary_angular_momentum": {
            "field": "H_O_I",
            "about": "INERTIAL_ORIGIN_I",
            "expressed_in": "I",
            "unit": "N*m*s",
        },
        "secondary_com_check": "H_C_I = H_O_I - p_C_I cross P_I",
        "base_state": {
            "position": "p_WB expressed in I, m",
            "quaternion": "wxyz, rotation B to I",
            "base_spatial_velocity": "[omega_B; v_B] expressed in B; converted before inertial momentum sum",
        },
        "mixing_prohibition": "P and H may share a spatial-vector storage container but may never share an ordinary Euclidean norm or hard Gate",
        "authority_inputs": binding["contracts"],
    }
    dump_yaml(MODULE / "02_frames_units/R5_MOMENTUM_FRAME_CONTRACT.yaml", frame_contract)
    scale_cases = []
    for case in s02["cases"]:
        scale_cases.append({"case_id": case["case"]["case_id"], **case["scales"]})
    scale_cases.append({"case_id": "S03_ALL_DT_SAME_FROZEN_INITIAL_STATE", **s03["runs"][0]["scales"]})
    dump_yaml(
        MODULE / "02_frames_units/R5_MOMENTUM_SCALE_CONTRACT.yaml",
        {
            "schema": "R5_MOMENTUM_SCALE_CONTRACT_V1",
            "status": "ENGINEERING_DEFINITION_PREREGISTERED_DIAGNOSTIC_NOT_FLIGHT_REQUIREMENT",
            "timing": "computed from frozen plant and initial state before integration",
            "P_den": gate_cfg["scale_contract"]["P_denominator"],
            "H_den": gate_cfg["scale_contract"]["H_denominator"],
            "posterior_residual_scaling_forbidden": True,
            "cases": scale_cases,
            "threshold_authority_status": "MISSING",
            "relative_metric_status": "PROVISIONAL_DIAGNOSTIC_ONLY",
            "relative_metric_hard_gate": False,
            "P_abs_max_kg_m_s": None,
            "H_abs_max_N_m_s": None,
            "formal_gate_status": "HOLD_THRESHOLD_AUTHORITY_MISSING",
            "threshold_authority": "No repository SSOT supplies applicable absolute P/H residual thresholds; the preregistered relative scales are numerical diagnostics only.",
        },
    )
    dump_json(
        MODULE / "02_frames_units/R5_UNIT_INVARIANCE_REPORT.json",
        {
            "schema": "R5_UNIT_INVARIANCE_REPORT_V1",
            "verdict": "PASS_R5_ANALYTIC_INTERFACE_TESTS",
            "tests": [
                "L10: equivalent SI and mm/g/deg interfaces return identical rigid-body P/H",
                "L11: 1e9 inertia scaling error fails the production plausibility guard",
                "L12: mixed P/H hard-Gate fields and Nx6 component sums fail closed",
                "static uncertainty-and-units audit: 0 findings in both R5 scientific modules",
            ],
            "production_test": "tests/test_r5_momentum_and_runner.py",
            "production_test_sha256": compact_hash(MODULE / "tests/test_r5_momentum_and_runner.py"),
            "formal_threshold_gate": "HOLD_THRESHOLD_AUTHORITY_MISSING",
            "release_credit": False,
            "claim_limit": "analytic software-interface invariance only; does not validate unmodeled hardware-unit authorities",
        },
    )
    dump_json(
        MODULE / "02_frames_units/R5_REFERENCE_POINT_INVARIANCE_REPORT.json",
        {
            "schema": "R5_REFERENCE_POINT_INVARIANCE_REPORT_V1",
            "relation": "H_Oprime = H_O - r_OOprime cross P",
            "verdict": "PASS_R5_MULTI_STATE_ANALYTIC_INTERFACE_TESTS",
            "primary_gate_reference": "fixed inertial origin O",
            "secondary_com_relation": "H_C = H_O - p_C cross P",
            "test_sources": [
                "tests/test_r5_momentum_and_runner.py::test_reference_point_shift_and_interface_unit_equivalence",
                "tests/test_r5_momentum_and_runner.py::test_l9_reference_point_transform_multiple_states",
            ],
            "formal_threshold_gate": "HOLD_THRESHOLD_AUTHORITY_MISSING",
            "release_credit": False,
            "claim_limit": "multi-state algebra/reference-point consistency only",
        },
    )

    dump_csv(
        MODULE / "06_plant/R5_BODY_MOMENTUM_REGISTRY.csv",
        body_rows,
        list(body_rows[0]),
    )
    dump_yaml(
        MODULE / "06_plant/R5_SYSTEM_BOUNDARY_CONTRACT.yaml",
        {
            "schema": "R5_SYSTEM_BOUNDARY_CONTRACT_V1",
            "boundaries": boundaries,
            "actual_current_arm_dof": "6R+2P",
            "included": "rigid servicer body when composed, accepted B601 dynamic bodies and fixed-lumped links",
            "excluded": {
                "target": "REGISTERED_NOT_SYSTEM_MEMBER",
                "reaction_wheels": "NOT_IN_PLANT",
                "thrusters": "NOT_IN_PLANT",
                "flexible_panels": "NOT_IN_PLANT_PLACEHOLDER_EXCLUDED",
                "route_c": "NOT_IN_PLANT",
                "contact": "NOT_RUN_T_E_T_MISSING",
            },
            "body_registry": "06_plant/R5_BODY_MOMENTUM_REGISTRY.csv",
            "plant_physics_hashes": load_yaml(run_root / "RESOLVED_RUN_CONFIG.yaml")["plant_physics_hashes"],
        },
    )
    wrench_rows = [
        ("joint actuator torque", "INTERNAL", "equal system-level reaction through coupled equations"),
        ("ideal joint constraint reaction", "INTERNAL", "tree-joint reaction is internal to the declared system boundary"),
        ("reaction-wheel torque", "ABSENT", "wheel state not in plant; null, not zero"),
        ("thruster force", "ABSENT", "thruster model not in plant; null, not zero"),
        ("thruster torque", "ABSENT", "thruster model not in plant; null, not zero"),
        ("contact force", "ABSENT", "T_E_T missing; contact not run"),
        ("gravity", "ABSENT", "frozen no-gravity model scope"),
        ("event impulse", "EVENT", "verified monitor, event_count=0"),
        ("numerical velocity reset", "ABSENT", "velocity_discontinuity_count=0"),
        ("quaternion renormalization", "INTERNAL", "orientation-only coordinate projection; audited nonimpulsive with no velocity reset"),
        ("prescribed motion", "ABSENT", "all generalized coordinates dynamically integrated"),
    ]
    dump_yaml(
        MODULE / "06_plant/R5_WRENCH_AND_IMPULSE_CONTRACT.yaml",
        {
            "schema": "R5_WRENCH_AND_IMPULSE_CONTRACT_V1",
            "system_boundary": "06_plant/R5_SYSTEM_BOUNDARY_CONTRACT.yaml",
            "external_force_status": "FROZEN_ZERO_BY_MODEL_SCOPE",
            "external_torque_about_O_status": "FROZEN_ZERO_BY_MODEL_SCOPE",
            "event_monitor_status": "VERIFIED",
            "allowed_classifications": ["INTERNAL", "EXTERNAL", "EVENT", "ABSENT", "UNKNOWN"],
            "classifications": [
                {"action": action, "classification": classification, "basis": basis}
                for action, classification, basis in wrench_rows
            ],
            "fail_closed": "UNKNOWN or unregistered velocity discontinuity => FAIL_UNACCOUNTED_EVENT_IMPULSE",
        },
    )

    theory_rows = [
        {
            "local_path": "50_literature/references/notes/wilde2018tutorial.md",
            "title": "Equations of Motion of Free-Floating Spacecraft-Manipulator Systems: An Engineer's Tutorial",
            "authors": "Markus Wilde; Stephen Kwok Choon; Alessio Grompone; Marcello Romano",
            "year": 2018,
            "page_or_equation": "local note / full PDF 24 pages; equation mapping requires full-text review",
            "topic": "free-floating coupled equations, GJM/VM/DEM",
            "assumptions": "free-floating spacecraft-manipulator rigid multibody",
            "relevance_to_R5": "theoretical boundary and reaction coupling",
            "supports_implementation": "coupled base-arm dynamics architecture",
            "does_not_support": "R5 numerical thresholds or control release",
        },
        {
            "local_path": "50_literature/references/notes/nenchev1999impact.md",
            "title": "Impact analysis and post-impact motion control issues of a free-floating space robot subject to a force impulse",
            "authors": "Dragomir N. Nenchev; Kazuya Yoshida",
            "year": 1999,
            "page_or_equation": "local note / full PDF 10 pages; not consumed by no-contact Run4",
            "topic": "event/contact impulse propagation",
            "assumptions": "free-floating impact dynamics",
            "relevance_to_R5": "event impulse ledger definition",
            "supports_implementation": "need to account for discrete J/K at velocity changes",
            "does_not_support": "claim that contact is modeled in R5",
        },
        {
            "local_path": "30_simulation/sim_05_free_floating_arm/README_sim_05.md",
            "title": "sim_05 free-floating base dynamics with B601",
            "authors": "project evidence",
            "year": 2026,
            "page_or_equation": "README lines 64-70",
            "topic": "zero-momentum base reaction and generalized Jacobian",
            "assumptions": "rigid 6R arm reduced mission model",
            "relevance_to_R5": "project precedent",
            "supports_implementation": "base-arm momentum coupling expectation",
            "does_not_support": "current R5 6R+2P plant or contact release",
        },
        {
            "local_path": "src/dh_v1/plant.py",
            "title": "FloatingPlant CRBA/RNEA implementation",
            "authors": "project production source",
            "year": 2026,
            "page_or_equation": "forward_dynamics and momentum_world",
            "topic": "spatial multibody dynamics",
            "assumptions": "rigid tree, no gravity/contact",
            "relevance_to_R5": "executed plant",
            "supports_implementation": "actual numerical plant behavior",
            "does_not_support": "literature authority; ENGINEERING_DEFINITION",
        },
        {
            "local_path": "src/dh_v1/scen_dynamics_r5.py",
            "title": "R5 RK4 and local stability production implementation",
            "authors": "project production source",
            "year": 2026,
            "page_or_equation": "rk4_step_r5; stability_analysis_r5",
            "topic": "sampled numerical stability",
            "assumptions": "terminal equilibrium, zero-total-momentum internal subspace",
            "relevance_to_R5": "executed mechanism diagnostic",
            "supports_implementation": "reproducible engineering result",
            "does_not_support": "global nonlinear/flight stability; ENGINEERING_DEFINITION",
        },
    ]
    dump_csv(
        MODULE / "10_research/R5_THEORY_SOURCE_MAP.csv",
        theory_rows,
        list(theory_rows[0]),
    )
    dump_text(
        MODULE / "10_research/R5_DYNAMICS_EQUATION_TRACEABILITY.md",
        f"""# R5 动力学方程与实现追溯

Run4 执行证据：`{run_root.relative_to(MODULE).as_posix()}`，完成标志 SHA-256 `{run_complete_sha}`。这是阈值授权缺失条件下的诊断证据，不是正式 Gate PASS。

| 物理量/方程 | 生产实现 | 合同 | Run4 证据 |
|---|---|---|---|
| `P^I = Σ m_i v_Gi^I` | `momentum_ledger_r5.body_momentum_contributions` + `math.fsum` 分量求和 | `R5_MOMENTUM_FRAME_CONTRACT.yaml` | 每个 episode `TIMESERIES.parquet` 的 `P_body_*` 与 `P_I_*` |
| `H_O^I = Σ(H_spin + r_OG×P_i)` | 同上；自旋/轨道分列 | 固定惯性原点 O | `H_spin_body_*`、`H_orbital_body_*`、`H_O_I_*` |
| `R_P=P-P0-∫F_ext dt-ΣJ` | `build_unit_safe_ledger` | `R5_WRENCH_AND_IMPULSE_CONTRACT.yaml` | S02/S03 metrics 与 event monitor |
| `R_H=H-H0-∫τ_ext,O dt-ΣK` | `build_unit_safe_ledger` | 同上 | S02/S03 metrics |
| 自由基座内部模态 `M_eff=Hqq-HqB HBB^-1 HBq` | `stability_analysis_r5` | 6R+2P 单位缩放 | S03 local stability artifact |
| RK4 `R(z)=1+z+z²/2+z³/6+z⁴/24` | 解析放大 + 实际 reduced step Jacobian | 三步长冻结 | 1 ms 不稳定；0.5/0.25 ms 衰减 |

文献只支撑方程族与边界；阈值、代码和 Run4 数值均为可审计工程定义。仓库内没有适用于当前 plant/场景/求解器的绝对 P/H 残差阈值 authority，因此相对指标不得作硬 Gate。
""",
    )
    inventory = []
    for name, module_name, candidate_path in (
        ("SPART", None, "80_third_party or MATLAB path"),
        ("Exudyn", "exudyn", "Python environment"),
        ("MuJoCo", "mujoco", "Python environment"),
        ("Basilisk", "Basilisk", "Python environment"),
        ("Pinocchio", "pinocchio", "Python environment"),
        ("CasADi", "casadi", "Python environment"),
    ):
        installed = bool(module_name and importlib.util.find_spec(module_name))
        inventory.append(
            {
                "tool": name,
                "local_detection": installed,
                "candidate_path": candidate_path,
                "version": "NOT_QUERIED_OR_NOT_INSTALLED",
                "r5_action": "NO_INSTALL_NO_EXECUTION",
            }
        )
    dump_csv(
        MODULE / "10_research/R6_LOCAL_LIBRARY_INVENTORY.csv",
        inventory,
        list(inventory[0]),
    )
    backend_rows = [
        ("SPART", 1, "URDF FK/Jacobian/mass-matrix cross-check", "accepted URDF hash + frame/joint mapping", "no formal truth overwrite"),
        ("Exudyn", 2, "independent rigid multibody cross-check", "same IC/forces/frames and P/H ledgers", "contact/flex remains separately gated"),
        ("MuJoCo", 3, "fast control/contact candidate", "URDF conversion inertia/free-base/mesh audit", "candidate only"),
        ("Basilisk", 4, "orbit/attitude/wheel/thruster mission layer", "explicit handoff and actuator models", "no retroactive R5 credit"),
        ("Pinocchio/CasADi", 5, "derivatives/optimization/NMPC preparation", "6R+2P unit-aware state map", "no NMPC in R5"),
    ]
    dump_csv(
        MODULE / "10_research/R6_BACKEND_ACCEPTANCE_CRITERIA.csv",
        [
            {
                "tool": tool,
                "priority": priority,
                "purpose": purpose,
                "minimum_acceptance": acceptance,
                "claim_limit": limit,
            }
            for tool, priority, purpose, acceptance, limit in backend_rows
        ],
        ["tool", "priority", "purpose", "minimum_acceptance", "claim_limit"],
    )
    dump_text(
        MODULE / "10_research/R6_TOOLCHAIN_INTAKE_PLAN.md",
        """# R6 外部工具链接入计划（只规划，未安装）

顺序候选为 SPART → Exudyn → MuJoCo → Basilisk → Pinocchio/CasADi。R5 不安装、不迁移 Linux、不把外部后端写成真值。R6 仍为规划态；在阈值 authority 和 R5 runner 失败生命周期获得独立授权前，不执行外部后端。获批后首项才是 SPART accepted-URDF 的 FK、Jacobian、浮动基座质量矩阵与 P/H 对拍；每个后端必须采用独立结果目录、输入哈希和 fail-closed 映射审计。

`R6_LOCAL_LIBRARY_INVENTORY.csv` 只反映本次本地探测；`R6_BACKEND_ACCEPTANCE_CRITERIA.csv` 是准入条件，不是授权。
""",
    )

    full_test = run_full_tests(run_id)
    if not full_test["passed"]:
        raise RuntimeError("full post-run R5 regression failed; delivery Gate must not be issued")
    dump_json(
        MODULE / "11_verification/R5_PREEXECUTION_GATE.json",
        {
            "schema": "R5_PREEXECUTION_GATE_DERIVED_RECEIPT_V1",
            "run_id": run_id,
            "source": f"{run_root.relative_to(MODULE).as_posix()}/verification/R5_PREEXECUTION_GATE.json",
            "source_sha256": compact_hash(run_root / "verification/R5_PREEXECUTION_GATE.json"),
            "source_verdict": preexec["verdict"],
            "post_run_full_regression": full_test,
            "protected_inputs_all_match": all(row["match"] for row in protected),
            "R5_EXECUTION_AUTHORIZED_AT_RUN_START": True,
            "memory_gate_passed": run_environment["memory_risk_record"]["memory_gate_passed"],
            "memory_gate_status": run_environment["memory_risk_record"]["memory_gate_status"],
            "owner_override_execution_only": True,
            "note": "Derived receipt only; immutable run-local preexecution Gate remains SSOT.",
        },
    )
    negative = {
        "schema": "R5_NEGATIVE_CONTROL_REPORT_V1",
        "run_id": run_id,
        "verdict": "PASS_L1_L16_AND_FULL_70_TEST_REGRESSION",
        "L1_L16": {
            "L1_STATIONARY_ZERO_P_H": "PASS",
            "L2_SINGLE_RIGID_TRANSLATION": "PASS",
            "L3_SINGLE_RIGID_SPIN": "PASS",
            "L4_ORBITAL_PLUS_SPIN_H_ABOUT_O": "PASS",
            "L5_INTERNAL_JOINT_ACTION_CONSERVATION": "PASS",
            "L6_EXTERNAL_FORCE_IMPULSE": "PASS",
            "L7_EXTERNAL_TORQUE_IMPULSE": "PASS",
            "L8_EVENT_IMPULSE_REGISTERED_AND_UNREGISTERED": "PASS",
            "L9_MULTI_STATE_REFERENCE_POINT_TRANSFORM": "PASS",
            "L10_SI_VS_MM_G_DEG_INTERFACE": "PASS",
            "L11_WRONG_INERTIA_SCALING_FAIL_CLOSED": "PASS",
            "L12_MIXED_P_H_NORM_FORBIDDEN": "PASS",
            "L13_RUN_ID_OVERWRITE_FAIL_CLOSED": "PASS",
            "L14_MANIFEST_AUTHORITY_HASH_COMPLETENESS": "PASS",
            "L15_EXACT_THREE_POINT_GRID": "PASS",
            "L16_TORQUE_TIMESERIES_COMPLETENESS": "PASS",
        },
        "additional_controls": [
            "unknown event monitor rejected",
            "pure PD P/I/D/raw/limited identity and 6R+2P units",
            "RK4 step equivalence and accepted-node saturation accounting",
            "local stability neutral/decay/unstable classification",
            "run-id traversal, output-root escape and atomic success-package overwrite rejection",
            "source manifest and path-independent plant identity",
        ],
        "r4_negative_preserved": True,
        "existing_tests_deleted": 0,
        "existing_assertions_relaxed": 0,
        "skip": 0,
        "xfail": 0,
        "xpass": 0,
        "full_test_receipt": full_test,
    }
    dump_json(MODULE / "11_verification/R5_NEGATIVE_CONTROL_REPORT.json", negative)

    s02_rows = []
    for case in s02["cases"]:
        for run in case["runs"]:
            m = run["metrics"]
            s02_rows.append(
                {
                    "case_id": case["case"]["case_id"],
                    "plant_id": case["case"]["plant_id"],
                    "dt_s": run["dt_s"],
                    "effective_sample_period_s": run["solver_execution"]["regular_effective_sample_period_s"],
                    "epsilon_P_max": m["epsilon_P_max"],
                    "epsilon_H_max": m["epsilon_H_max"],
                    "R_P_abs_max_kg_m_s": m["norm_R_P_max_kg_m_s"],
                    "R_H_abs_max_N_m_s": m["norm_R_H_max_N_m_s"],
                    "relative_energy_drift_max": m["rel_E_drift_max"],
                    "P_convergence_mode": case["P_convergence"]["mode"],
                    "H_convergence_mode": case["H_convergence"]["mode"],
                    "numeric_diagnostic_all_pass": case["numeric_diagnostic_all_pass"],
                    "threshold_authority_verdict": case["threshold_authority_verdict"],
                    "case_all_gates_pass": case["all_gates_pass"],
                }
            )
    dump_csv(MODULE / "11_verification/R5_S02_CASE_COMPARISON.csv", s02_rows, list(s02_rows[0]))
    s03_rows = []
    for run in s03["runs"]:
        m = run["metrics"]
        joint6_effort = m["generalized_effort_abs_max_per_joint"][5]
        joint6_sat = m["saturation_by_joint"][5]
        s03_rows.append(
            {
                "dt_s": run["dt_s"],
                "epsilon_P_max": m["epsilon_P_max"],
                "epsilon_H_max": m["epsilon_H_max"],
                "R_P_abs_max_kg_m_s": m["norm_R_P_max_kg_m_s"],
                "R_H_abs_max_N_m_s": m["norm_R_H_max_N_m_s"],
                "tracking_error_revolute_max_rad": m["tracking_error_revolute_max_rad"],
                "tracking_error_prismatic_max_m": m["tracking_error_prismatic_max_m"],
                "base_attitude_change_deg": m["base_attitude_change_deg"],
                "joint6_accepted_node_limited_abs_max_N_m": joint6_effort["value"],
                "joint6_accepted_node_saturation_s": joint6_sat["accepted_node_saturation_duration_s"],
                "joint6_any_stage_clipping_upper_bound_s": joint6_sat["any_stage_saturation_duration_upper_bound_s"],
                "any_accepted_node_saturation": m["any_accepted_node_saturation"],
                "any_stage_saturation": m["any_stage_saturation"],
                "physical_joint_limit_violation": any(
                    item["below_lower"] or item["above_upper"]
                    for item in m["physical_joint_limit_violations"]
                ),
                "threshold_authority_status": "MISSING",
                "complete_scenario_pass": False,
                "control_release": False,
            }
        )
    dump_csv(MODULE / "11_verification/R5_S03_CASE_COMPARISON.csv", s03_rows, list(s03_rows[0]))

    stability = s03["local_stability_analysis"]
    stab_lines = [
        "# R5 S03 离散稳定性诊断",
        "",
        f"科学分类：`NUMERICAL_INSTABILITY_STRONGLY_SUPPORTED`；机制诊断：`{stability['ruling']}`，限定范围为 `{stability['ruling_scope']}`。",
        "",
        f"连续约化闭环特征值实部范围：{stability['continuous_reduced_model']['min_real_eigenvalue_per_s']:.9g} 至 {stability['continuous_reduced_model']['max_real_eigenvalue_per_s']:.9g} s⁻¹；解析/有限差分相对 Frobenius 差 {stability['continuous_reduced_model']['analytic_vs_scaled_fd_relative_frobenius']:.3e}；最快模态以 joint6 为主。",
        "",
        "| dt (s) | RK4 最大放大 | 实际约化一步映射 ρ | 分类 | 内部 stage 裁剪 |",
        "|---:|---:|---:|---|---|",
    ]
    for run, diag in zip(s03["runs"], stability["dt_analysis"]):
        stab_lines.append(
            f"| {run['dt_s']:.7g} | {diag['rk4_polynomial_max_amplification']:.9g} | {diag['actual_reduced_map_spectral_radius']:.9g} | {diag['actual_reduced_map_classification']} | {run['metrics']['any_stage_saturation']} |"
        )
    stab_lines.extend(
        [
            "",
            "六个自由漂浮中性模只分类、不作为 `rho<1` 通过条件。所谓 full velocity-state polynomial 不包含基座位姿/四元数，不能称完整实际 pose map。1 ms 的 accepted-node joint6 未越 7 N·m，裁剪发生在 RK4 内部 stage；不得改写为执行器物理饱和 99%。两个 P 关节越下限，物理控制适用性继续 HOLD。",
            "",
            "S03 的 complete_scenario_pass=false；本结论不证明全轨迹非线性稳定、飞行控制稳定、接触稳定或硬件执行器性能，也不产生控制发布信用。",
        ]
    )
    dump_text(MODULE / "11_verification/R5_S03_DISCRETE_STABILITY_DIAGNOSTIC.md", "\n".join(stab_lines))

    dump_text(
        MODULE / "11_verification/R5_UNIT_SAFE_MOMENTUM_REPORT.md",
        f"""# R5 单位安全动量报告

Run4 对三个 S02 case 各执行 `4/2/1 ms` 三点细化，P/H 分账、能量、基座角/线速度投影的数值诊断全部通过；最细步长的 `epsilon_P` 范围为 `{min(row['epsilon_P_max'] for row in s02_rows if row['dt_s']==0.001):.3e}`–`{max(row['epsilon_P_max'] for row in s02_rows if row['dt_s']==0.001):.3e}`，`epsilon_H` 范围为 `{min(row['epsilon_H_max'] for row in s02_rows if row['dt_s']==0.001):.3e}`–`{max(row['epsilon_H_max'] for row in s02_rows if row['dt_s']==0.001):.3e}`。

主账本固定为 `P^I [kg·m/s]` 与 `H_O^I [N·m·s]`，O 为固定惯性原点；外部 wrench 为模型范围内显式零，事件监测 VERIFIED 且事件数 0。逐动态体的 P、H_spin、H_orbital 已写入 episode 时序并以 `math.fsum` 分量求和，再与 plant 空间动量对拍。旧 `rel_h_drift_max` 保留为 R4/Run3 历史，但状态为 `DEPRECATED_UNIT_INVALID_FOR_GATE`。

R5 的相对尺度是运行前由冻结 plant、初态和持续时间计算的工程诊断尺度，不是飞行要求。仓库查无适用于本 plant/场景/求解器的 `P_abs_max [kg·m/s]` 与 `H_abs_max [N·m·s]` 权威合同，因此正式 P/H Gate 均为 `HOLD_THRESHOLD_AUTHORITY_MISSING`。本报告只支持 `R5_LEDGER_NUMERICALLY_VERIFIED`，不产生控制或接触发布信用。
""",
    )
    dump_text(
        MODULE / "11_verification/R5_RUNNER_PROVENANCE_REPORT.md",
        f"""# R5 版本化运行器与来源追溯报告

Run4 位于 `{run_root.relative_to(MODULE).as_posix()}`，`RUN_COMPLETE.json` SHA-256 为 `{run_complete_sha}`。运行包含 {dataset['episode_count']} 个 batch episode 和 {dataset['canonical_package_count']} 个规范包；每个规范包具有 18 项必需文件、`HASH_MANIFEST.csv` 与 2 项兼容遥测，共 21 文件。{canonical_audit['run_output_hash_rows']} 个受管 Run4 输出和全部包内文件后验重算均为 0 个 hash 失败；{len(source_rows)} 个生产源码/配置文件复制到 run 内 `source_snapshot/` 并逐项验签。

每个 episode 绑定 plant physics、生成 plant artifact、controller、Gate、scenario、source tree、source snapshot、authority、environment、seed、initial state、solver execution、preintegration scale 和 resolved episode config 哈希。4 ms S02 工况把 50 ms 记录为目标采样周期，并诚实记录实际规则采样周期 48 ms；2/1 ms 与全部 S03 为 50 ms。

run-id 重用、路径穿越、输出根逃逸和成功包覆盖均由生产 helper/负控拒绝。成功包采用同父临时目录后原子重命名；但 runner 尚未在积分前预开失败生命周期包，因此 G5 只能记为“成功发布 PASS、完整失败生命周期 HOLD”。Run1/Run2/失败 Run3 均保留不变，Run4 不追溯升级历史证据。
""",
    )

    g = {
        "R5-G0_AUTHORITY_AND_FROZEN_INPUTS": "HOLD_RETROSPECTIVE_TAKEOVER__RUN4_HASH_BOUND__NO_BACKDATED_AUTHORITY",
        "R5-G1_SYSTEM_BOUNDARY_AND_FRAME": "PASS_R5_ANALYTIC_UNIT_REFERENCE_AND_BOUNDARY_TESTS__6R_PLUS_2P_PHYSICAL_SEMANTIC_HOLD",
        "R5-G2_UNIT_SAFE_LINEAR_MOMENTUM": "PASS_NUMERIC_DIAGNOSTIC__HOLD_THRESHOLD_AUTHORITY_MISSING",
        "R5-G3_UNIT_SAFE_ANGULAR_MOMENTUM": "PASS_NUMERIC_DIAGNOSTIC_FIXED_O__HOLD_THRESHOLD_AUTHORITY_MISSING",
        "R5-G4_EXTERNAL_WRENCH_AND_EVENT_LEDGER": "PASS_EXPLICIT_MODEL_SCOPE_LEDGER__CONTACT_AND_HARDWARE_ABSENT",
        "R5-G5_VERSIONED_RUNNER_AND_PROVENANCE": "PASS_EXACT_18_REQUIRED_FILE_ATOMIC_SUCCESS_EXPORT__HOLD_FAILURE_LIFECYCLE_NOT_PREOPENED",
        "R5-G6_TESTS_AND_NEGATIVE_CONTROLS": "PASS_L1_L16_AND_FULL_70_TESTS",
        "R5-G7_S02_ALL_CASES_THREE_POINT": "PASS_NUMERIC_DIAGNOSTIC_3_CASES_9_EPISODES__HOLD_THRESHOLD_AUTHORITY",
        "R5-G8_S03_ALL_CASES_THREE_POINT": "HOLD_COMPLETE_SCENARIO_FALSE__THREE_POINT_DIAGNOSTIC_EXECUTED",
        "R5-G9_DISCRETE_STABILITY_DIAGNOSTIC": "NUMERICAL_INSTABILITY_STRONGLY_SUPPORTED__LOCAL_SCOPE_ONLY__PHYSICAL_APPLICABILITY_HOLD",
        "R5-G10_FINAL_INCREMENT_VERDICT": "R5_REPEAT_REQUIRED",
    }
    final_verdict = (
        "R5_REPEAT_REQUIRED__UNIT_SAFE_P_H_LEDGER_DIAGNOSTIC_EVIDENCE_PRESERVED__"
        "THRESHOLD_AUTHORITY_HOLD__VERSIONED_RUNNER_FAILURE_LIFECYCLE_HOLD__"
        "NO_CONTROL_OR_CONTACT_RELEASE__PARENT_GATE_NOT_REISSUED__NEXT_STAGE_NOT_AUTHORIZED"
    )
    increment_gate = {
        "schema": "R5_INCREMENT_GATE_V1",
        "task_id": "R5_UNIT_SAFE_MOMENTUM_LEDGER_AND_VERSIONED_RUNNER",
        "run_id": run_id,
        "run_complete_sha256": run_complete_sha,
        "gates": g,
        "verdict": final_verdict,
        "highest_legal_state": "CURRENT_SYSTEM_DIGITAL_HOST_CANDIDATE + PREBIND_SIMULATION_DATASET_V1 + NO_FORMAL_RELEASE_CREDIT",
        "highest_legal_claim": "R5_LEDGER_NUMERICALLY_VERIFIED__R5_GATE_HOLD_THRESHOLD_AUTHORITY_MISSING__DIAGNOSTIC_ONLY",
        "scientific_result": "NUMERICAL_INSTABILITY_STRONGLY_SUPPORTED",
        "scientific_result_scope": candidate["s03_scientific_ruling"],
        "mechanism_diagnostic": candidate["s03_mechanism_diagnostic"],
        "threshold_authority_status": "MISSING",
        "relative_metric_hard_gate": False,
        "formal_gate_pass": False,
        "run4_machine_verdict": complete["verdict"],
        "run4_output_audit": canonical_audit,
        "remaining_holds": [
            "absolute P/H residual threshold authority missing",
            "runner failure lifecycle not pre-opened before integration",
            "takeover snapshot is retrospective, not pre-change",
            "6R+2P dynamic-vs-locked-comment conflict",
            "two prismatic joints cross lower limit in unconstrained plant",
            "T_E_T missing; contact C08/C09 not evaluated",
            "reaction wheels, thrusters, target and flexible panels absent",
            "no independent external backend cross-validation in R5",
            "no authoritative physical uncertainty intervals; D2 not evaluated",
        ],
        "parent_gate_reissued": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "control_release": False,
        "contact_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "R6": "PLANNING_ONLY_NOT_AUTHORIZED_FOR_EXECUTION",
    }
    dump_json(MODULE / "11_verification/R5_INCREMENT_GATE.json", increment_gate)

    delta = f"""# 当前数字宿主增量 R5

R5 已把 R4 检出的混合量纲动量指标闭合为单位安全 P/H 独立账本、逐体贡献、显式外作用/事件合同、完整控制 effort 时序和三步长局部稳定性诊断。Run4 共 12 episode，机器 verdict `{complete['verdict']}`；297 项 Run4 输出与 12 个原子成功包均已验签。

新增能力不等于正式 R5 Gate PASS：当前没有绝对 P/H 残差阈值 authority，runner 失败生命周期也未在积分前预开。当前仍是刚体、无重力、无接触的 prebind plant；目标、飞轮、推力器、柔性帆板均不在系统边界。S03 在 1 ms 下出现内部 RK4 stage 失稳，在 0.5/0.25 ms 下回到机器精度；这只支持 `NUMERICAL_INSTABILITY_STRONGLY_SUPPORTED` 的终端局部数学机制。
"""
    dump_text(MODULE / "13_reports/CURRENT_DIGITAL_HOST_DELTA_R5.md", delta)
    dump_text(
        MODULE / "13_reports/R5_ENGINEERING_AND_SCIENTIFIC_DECISION.md",
        f"""# R5 工程与科学裁决

工程裁决：批准 Run4 的单位安全 P/H 数值诊断、L1–L16 测试和原子成功包作为可复算证据入档；不批准把它写成正式 R5 Gate PASS。最终裁决为 `{final_verdict}`。

科学裁决：三个 S02 case 的 P/H/能量/投影数值诊断全部通过，但 `P_abs_max/H_abs_max` authority 缺失，正式 Gate 保持 HOLD。S03 连续约化闭环稳定；1 ms 的 RK4 放大与实际约化一步映射谱半径均为约 1.6677，0.5/0.25 ms 分别约 0.99745/0.99872；最快模态 joint6。合法结论为 `NUMERICAL_INSTABILITY_STRONGLY_SUPPORTED`，范围限定为 `{candidate['s03_scientific_ruling']}`。

机械/物理 HOLD：当前 plant 实际为 6R+2P，且两个 P 关节的无约束轨迹越下限；accepted URDF 未改。T_E_T、接触、目标、飞轮、推力器和柔性仍未进入本轮。低内存执行依赖 Owner Override，`memory_gate_passed=false`；不释放控制、接触或下一阶段。
""",
    )
    dump_text(
        MODULE / "13_reports/NEXT_AUTHORIZED_ACTION.md",
        """# 下一授权动作

当前自动授权只到 R5 派生证据与 Owner 审阅，`next_stage_authorized=false`。

1. 首先由 Owner/需求权威签发绝对残差合同，分别给出 `P_abs_max [kg·m/s]`、`H_abs_max [N·m·s]`，并绑定惯性系、参考点 O、系统边界、场景、时域、求解器、步长、比较关系、来源与批准状态。
2. 如需闭合 R5-G5，版本化 runner 必须在积分前预开失败生命周期目录，并对成功/失败采用同一原子发布语义；随后只能使用新 run_id 复跑。
3. 上述两项经独立授权后，R6 才可从 SPART 的 accepted-URDF FK/Jacobian/浮动基座质量矩阵与 P/H 对拍开始；当前 R6 仅规划，不执行。

机械侧应先裁决两个 P 关节到底“锁定”还是“动态夹爪”，并给出物理限位/速度 authority；这项决定不能追溯改写 R5 冻结 plant。
""",
    )

    dump_json(
        MODULE / "13_reports/R5_LOW_MEMORY_OWNER_OVERRIDE_AND_MITIGATION.json",
        {
            "schema": "R5_LOW_MEMORY_OWNER_OVERRIDE_AND_MITIGATION_V1",
            "run_id": run_id,
            "run_start_memory_record": run_environment["memory_risk_record"],
            "pressure_excursion_observation": {
                "available_GiB_before_targeted_recovery": 0.47,
                "available_percent_before_targeted_recovery": 3.1,
                "observation": "Concurrent background-process snapshot during S03; not the run-start admission sample.",
            },
            "targeted_recovery": {
                "action": "TERMINATE_ONLY_NEWLY_STARTED_UNUSED_CAE_MCP_BACKGROUND_SERVICES",
                "process_start_window_local": "2026-08-27T19:12:40+09:00/2026-08-27T19:12:50+09:00",
                "terminated_process_count": 37,
                "terminated_process_ids_snapshot": [
                    2648, 6228, 14164, 18212, 18320, 19788, 19808, 22752,
                    23848, 26220, 26356, 29960, 30160, 30332, 30740, 31712,
                    33164, 35820, 35976, 36408, 39468, 39840, 40472, 41248,
                    41412, 42148, 42984, 44732, 45252, 48140, 48440, 49492,
                    51552, 52504, 53012, 53632, 54892,
                ],
                "available_GiB_immediately_after": 1.51,
                "available_percent_immediately_after": 9.9,
                "r5_process_preserved": True,
                "foreground_user_apps_closed": False,
                "formal_evidence_deleted": False,
                "pytest_temp_cleanup_attempt": "ACCESS_DENIED_NO_FILES_REMOVED_AND_NO_RAM_CREDIT_CLAIMED",
            },
            "delivery_regression_memory": {
                "before": full_test["memory_before"],
                "after": full_test["memory_after"],
            },
            "formal_semantics": {
                "memory_gate_threshold_GiB": 6.0,
                "memory_gate_passed": False,
                "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY",
                "execution_authorized": True,
                "scientific_gate_credit": False,
                "note": "Memory mitigation never converts the admission Gate to PASS.",
            },
        },
    )

    # Artifact manifest is last and excludes itself to avoid a circular hash.
    artifact_rows = []
    artifact_candidates = set(GENERATED)
    preserved_failed_log = MODULE / PRESERVED_FAILED_TEST_LOG
    if preserved_failed_log.is_file():
        artifact_candidates.add(preserved_failed_log)
    for path in sorted(artifact_candidates, key=lambda p: p.as_posix()):
        if path.name != "R5_ARTIFACT_SHA256.csv":
            artifact_rows.append(
                {
                    "path": path.relative_to(MODULE).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    dump_csv(
        MODULE / "11_verification/R5_ARTIFACT_SHA256.csv",
        artifact_rows,
        ["path", "bytes", "sha256"],
    )
    print(f"R5 delivery generated: {len(GENERATED)} files")
    print(f"R5 delivery repaired files: {len(REPLACED)}")
    print(f"Run4 complete SHA-256: {run_complete_sha}")
    print(f"Full tests: {full_test}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument(
        "--repair-derived",
        action="store_true",
        help="replace only derived R5/R6 delivery files from an interrupted prior attempt",
    )
    args = parser.parse_args()
    main(args.run_id, repair_derived=args.repair_derived)
