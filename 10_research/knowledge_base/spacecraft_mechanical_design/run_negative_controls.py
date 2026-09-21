#!/usr/bin/env python3
"""Temporary-copy semantic negative controls for MECH-TI-01.

Artifact identity: RECONSTRUCTED_NAVIGATION_ENTRY_NOT_HISTORICAL.
All mutations occur under a system temporary directory; the workspace is read-only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable

sys.dont_write_bytecode = True

import yaml


IDENTITY = "RECONSTRUCTED_NAVIGATION_ENTRY_NOT_HISTORICAL"


def load_validator(package_root: Path):
    spec = importlib.util.spec_from_file_location("mech_ti_01_validator", package_root / "validate_mech_ti_01.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("validator import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mutate_json(package_root: Path, relative: str, mutator: Callable[[dict], None]) -> None:
    path = package_root / relative
    value = json.loads(path.read_text(encoding="utf-8"))
    mutator(value)
    write_json(path, value)


def mutate_yaml(package_root: Path, relative: str, mutator: Callable[[dict], None]) -> None:
    path = package_root / relative
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutator(value)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


def refresh_local_manifest(package_root: Path) -> None:
    manifest = package_root / "MECH_TI_01_SHA256_MANIFEST_V1.csv"
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        path = package_root / row["path"]
        row["bytes"] = str(path.stat().st_size)
        row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    with manifest.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "bytes", "sha256", "role"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def set_contract_identity(package_root: Path) -> None:
    mutate_yaml(package_root, "knowledge_contract.yaml", lambda value: value.update({"artifact_identity": "HISTORICAL_ORIGINAL"}))


def claim_historical_match(package_root: Path) -> None:
    mutate_json(package_root, "MECH_TI_01_HISTORICAL_MISSING_ORIGINAL_AUDIT_V1.json", lambda value: value.update({"exact_bytes_and_sha256_matches_found": 1}))


def promote_prb17(package_root: Path) -> None:
    def mutate(value: dict) -> None:
        row = next(row for row in value["prb_matrix"] if row["id"] == "PRB-17")
        row.update({"state": "PASS", "pass": True})
    mutate_json(package_root, "MECH_TI_01_BLOCKER_MATRIX_V1.json", mutate)


def inflate_prb_summary(package_root: Path) -> None:
    mutate_json(package_root, "MECH_TI_01_BLOCKER_MATRIX_V1.json", lambda value: value["prb_summary"].update({"pass": 7, "hold": 13, "local_delta": 1}))


def promote_mpi01(package_root: Path) -> None:
    def mutate(value: dict) -> None:
        row = next(row for row in value["mpi_matrix"] if row["id"] == "MPI-01")
        row.update({"audit_state": "CONTROLLED", "controlled": True, "local_effect": "PASS"})
    mutate_json(package_root, "MECH_TI_01_BLOCKER_MATRIX_V1.json", mutate)


def inflate_mpi_summary(package_root: Path) -> None:
    mutate_json(package_root, "MECH_TI_01_BLOCKER_MATRIX_V1.json", lambda value: value["mpi_summary"].update({"controlled": 1, "hold": 7, "local_delta": 1}))


def fill_p01_with_zero(package_root: Path) -> None:
    def mutate(value: dict) -> None:
        next(row for row in value["p_matrix"] if row["id"] == "P01")["value"] = 0
    mutate_json(package_root, "MECH_TI_01_BLOCKER_MATRIX_V1.json", mutate)


def promote_p01_available(package_root: Path) -> None:
    def mutate(value: dict) -> None:
        next(row for row in value["p_matrix"] if row["id"] == "P01")["state"] = "AVAILABLE"
    mutate_json(package_root, "MECH_TI_01_BLOCKER_MATRIX_V1.json", mutate)


def grant_owner_in_graph(package_root: Path) -> None:
    mutate_json(package_root, "MECH_TI_01_AUTHORITY_GRAPH_V1.json", lambda value: value["authority_guards"].update({"owner_accepted": True}))


def grant_next_in_matrix(package_root: Path) -> None:
    mutate_json(package_root, "MECH_TI_01_BLOCKER_MATRIX_V1.json", lambda value: value["guard_flags"].update({"next_stage_authorized": True}))


def corrupt_external_pin(package_root: Path) -> None:
    def mutate(value: dict) -> None:
        value["sources"][0]["sha256"] = "0" * 64
    mutate_yaml(package_root, "source_registry.yaml", mutate)


def inject_step(package_root: Path) -> None:
    (package_root / "INJECTED_UNAUTHORIZED.step").write_bytes(b"negative-control")


CASES = [
    ("NC01", "historical identity impersonation", "V01", set_contract_identity),
    ("NC02", "false historical exact-match claim", "V03", claim_historical_match),
    ("NC03", "PRB-17 local promotion", "V10", promote_prb17),
    ("NC04", "Unified R2 7/20 summary inflation", "V10", inflate_prb_summary),
    ("NC05", "MPI-01 false controlled promotion", "V12", promote_mpi01),
    ("NC06", "MPI 1/8 summary inflation", "V12", inflate_mpi_summary),
    ("NC07", "P01 null-to-zero coercion", "V14", fill_p01_with_zero),
    ("NC08", "P01 false AVAILABLE promotion", "V14", promote_p01_available),
    ("NC09", "Owner authority forged in graph", "V19", grant_owner_in_graph),
    ("NC10", "next-stage authority forged in matrix", "V20", grant_next_in_matrix),
    ("NC11", "external source SHA-256 drift", "V04", corrupt_external_pin),
    ("NC12", "unauthorized STEP injected", "V22", inject_step),
]


def run(repo_root: Path, package_root: Path) -> dict:
    validator = load_validator(package_root)
    case_results = []
    for case_id, name, expected_check, mutator in CASES:
        with tempfile.TemporaryDirectory(prefix="mech_ti_01_nc_") as temp_dir:
            candidate = Path(temp_dir) / "package"
            shutil.copytree(package_root, candidate)
            mutator(candidate)
            refresh_local_manifest(candidate)
            result = validator.evaluate(repo_root, candidate)
            failed = result["summary"]["failed"]
            killed = expected_check in failed
            case_results.append({
                "id": case_id,
                "name": name,
                "expected_failed_check": expected_check,
                "actual_failed_checks": failed,
                "killed": killed,
            })
    survived = [row["id"] for row in case_results if not row["killed"]]
    return {
        "schema": "MECH_TI_01_NEGATIVE_CONTROL_RESULT_V1",
        "package_id": "MECH-TI-01",
        "artifact_identity": IDENTITY,
        "mode": "SYSTEM_TEMPORARY_COPY_ONLY__WORKSPACE_READ_ONLY",
        "summary": {"killed": len(case_results) - len(survived), "total": len(case_results), "survived": survived},
        "cases": case_results,
        "workspace_files_written": 0,
        "verdict": "PASS_NEGATIVE_CONTROLS_12_OF_12_KILLED" if not survived else "FAIL_NEGATIVE_CONTROL_SURVIVED",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    default_package = Path(__file__).resolve().parent
    parser.add_argument("--repo-root", type=Path, default=default_package.parents[2])
    parser.add_argument("--package-root", type=Path, default=default_package)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    result = run(args.repo_root.resolve(), args.package_root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if not result["summary"]["survived"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
