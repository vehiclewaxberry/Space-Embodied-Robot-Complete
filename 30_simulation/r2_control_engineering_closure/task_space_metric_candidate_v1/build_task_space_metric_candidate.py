"""Build deterministic task-space metric candidate artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


PACKAGE = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE.parents[2]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from task_space_metric import (  # noqa: E402
    CONTRACT_PATH,
    evaluate_candidate,
    load_json_strict,
    load_contract,
    run_negative_controls,
)


RESULTS = PACKAGE / "results"
ALLOWED_FILES = {
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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def record(path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
    }


def build() -> dict[str, Any]:
    contract = load_contract()
    evidence, gate = evaluate_candidate(contract, PROJECT_ROOT)
    negative = run_negative_controls(contract, PROJECT_ROOT)
    evidence_path = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_EVIDENCE_V1.json"
    negative_path = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_NEGATIVE_CONTROL_RESULTS_V1.json"
    manifest_path = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_MANIFEST_V1.json"
    gate_path = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1.json"
    sha_path = RESULTS / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_SHA256_V1.csv"
    write_json(evidence_path, evidence)
    write_json(negative_path, negative)
    local_files = [
        (CONTRACT_PATH, "CONTRACT"),
        (PACKAGE / "src" / "__init__.py", "SOURCE_PACKAGE_INIT"),
        (PACKAGE / "src" / "task_space_metric.py", "IMPLEMENTATION"),
        (PACKAGE / "build_task_space_metric_candidate.py", "BUILDER"),
        (PACKAGE / "standalone_validate_task_space_metric.py", "STANDALONE_INTERNAL_VALIDATOR"),
        (PACKAGE / "tests" / "test_task_space_metric.py", "TEST_SUITE"),
        (PACKAGE / "README.md", "DOCUMENTATION"),
        (evidence_path, "EVIDENCE"),
        (negative_path, "NEGATIVE_CONTROL_EVIDENCE"),
    ]
    local_records = [record(path, role) for path, role in local_files]
    config_pin = next(row for row in contract["source_pins"] if row["id"] == "control_engineering_config")
    parent_config = load_json_strict(PROJECT_ROOT / config_pin["path"])
    actual_files = {path.relative_to(PACKAGE).as_posix() for path in PACKAGE.rglob("*") if path.is_file()}
    forbidden = [
        path.relative_to(PACKAGE).as_posix() for path in PACKAGE.rglob("*")
        if path.name in {"__pycache__", ".pytest_cache"} or path.suffix == ".pyc"
    ]
    extras = sorted(actual_files - ALLOWED_FILES)
    inventory_pass = not extras and not forbidden
    manifest = {
        "schema": "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_MANIFEST_V1",
        "source_pins": contract["source_pins"],
        "parent_transitive_source_pins": parent_config["source_pins"],
        "parent_transitive_source_pin_count": len(parent_config["source_pins"]),
        "local_records": local_records,
        "local_record_count": len(local_records),
        "claim": "HASH_BOUND_ADDITIVE_CANDIDATE_ONLY",
        "inventory_policy": {
            "allowed_files": sorted(ALLOWED_FILES),
            "observed_extra_files": extras,
            "observed_forbidden_cache_or_bytecode": sorted(forbidden),
            "pass": inventory_pass,
        },
        "parent_control_gate_reissued": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_json(manifest_path, manifest)
    gate["negative_controls"] = {
        "passed": negative["passed"],
        "total": negative["total"],
        "all_pass": negative["all_pass"],
    }
    gate["artifact_bindings"] = {
        "evidence": record(evidence_path, "EVIDENCE"),
        "negative_controls": record(negative_path, "NEGATIVE_CONTROL_EVIDENCE"),
        "manifest": record(manifest_path, "MANIFEST"),
    }
    gate["inventory_no_extra_or_cache"] = inventory_pass
    gate["artifact_package_complete"] = bool(gate["all_checks_pass"] and negative["all_pass"] and inventory_pass)
    write_json(gate_path, gate)
    rows = local_records + [record(manifest_path, "MANIFEST"), record(gate_path, "MACHINE_GATE")]
    with sha_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["role", "path", "bytes", "sha256"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return gate


if __name__ == "__main__":
    result = build()
    print(json.dumps({
        "schema": result["schema"],
        "passed": result["passed"],
        "total": result["total"],
        "negative_controls": result["negative_controls"],
        "verdict": result["technical_verdict"],
    }, ensure_ascii=False, indent=2))
