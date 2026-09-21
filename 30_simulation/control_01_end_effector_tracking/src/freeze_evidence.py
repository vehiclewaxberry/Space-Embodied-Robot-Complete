"""Freeze a portable LOOP-7 evidence manifest for the committed CTRL-01 source."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from repo_imports import MODULE_ROOT, REPO_ROOT, RESULTS_DIR


MANIFEST_PATH = RESULTS_DIR / "loop7_evidence_manifest.json"
# CTRL-01-R remediation base = last v0-loop evidence commit on wave1/ctrl-01.
REVIEW_REMEDIATION_BASE_COMMIT = "20cc50b937f2effc9d8f6f151f2ffd231424362e"
OWNED_PREFIXES = (
    "20_engineering/config/control_scene/",
    "30_simulation/control_01_end_effector_tracking/",
)
TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def _normalize_text(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _hash_row(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    relative = path.relative_to(REPO_ROOT).as_posix()
    row: dict[str, Any] = {
        "path": relative,
        "bytes": len(data),
        "raw_sha256": hashlib.sha256(data).hexdigest(),
    }
    if path.suffix.lower() in TEXT_SUFFIXES:
        row["normalized_semantic_sha256"] = hashlib.sha256(
            _normalize_text(data)
        ).hexdigest()
        row["hash_mode_for_gate"] = "normalized_semantic_sha256"
    else:
        row["hash_mode_for_gate"] = "raw_sha256"
    return row


def _owned_files() -> list[Path]:
    roots = (
        REPO_ROOT / "20_engineering" / "config" / "control_scene",
        MODULE_ROOT,
    )
    paths: list[Path] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path == MANIFEST_PATH:
                continue
            paths.append(path)
    return sorted(paths, key=lambda item: item.relative_to(REPO_ROOT).as_posix())


def _changed_paths() -> list[str]:
    lines = _git("status", "--porcelain=v1", "--untracked-files=all").splitlines()
    paths: list[str] = []
    for line in lines:
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value.replace("\\", "/").strip('"'))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-commit",
        required=True,
        help="Committed implementation/results revision represented by the manifest",
    )
    args = parser.parse_args()

    _git("cat-file", "-e", f"{args.source_commit}^{{commit}}")
    current_head = _git("rev-parse", "HEAD")
    if current_head != args.source_commit:
        raise RuntimeError(
            f"HEAD {current_head} does not match --source-commit {args.source_commit}"
        )

    gate = json.loads(
        (RESULTS_DIR / "control_01_gate_check.json").read_text(encoding="utf-8")
    )
    tests = json.loads(
        (RESULTS_DIR / "test_results.json").read_text(encoding="utf-8")
    )
    run = json.loads(
        (RESULTS_DIR / "control_01_run_summary.json").read_text(encoding="utf-8")
    )
    changed = _changed_paths()
    non_owned = [
        path
        for path in changed
        if not any(path.startswith(prefix) for prefix in OWNED_PREFIXES)
    ]
    if non_owned:
        raise RuntimeError(f"non-owned changes detected: {non_owned}")

    rows = [_hash_row(path) for path in _owned_files()]
    semantic_tree_payload = json.dumps(
        [
            {
                "path": row["path"],
                "hash_mode": row["hash_mode_for_gate"],
                "digest": row[row["hash_mode_for_gate"]],
            }
            for row in rows
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    manifest = {
        "schema_version": "control-01-loop7-evidence-v1",
        "task_id": "CTRL-01",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": _git("branch", "--show-current"),
        "source_commit": args.source_commit,
        "source_commit_parent": _git("rev-parse", f"{args.source_commit}^"),
        "source_git_tree_oid": _git(
            "rev-parse", f"{args.source_commit}^{{tree}}"
        ),
        "owned_evidence_semantic_tree_sha256": hashlib.sha256(
            semantic_tree_payload
        ).hexdigest(),
        "review_remediation_base_commit": REVIEW_REMEDIATION_BASE_COMMIT,
        "baseline_commit": "926522f199cae3b9d88ee6797089d57300fea994",
        "gate": {
            "verdict": gate["verdict"],
            "next_stage_authorized": gate["next_stage_authorized"],
            "scenario_count": gate["scenario_count"],
            "evidence_complete": gate["evidence_complete"],
        },
        "tests": {
            "overall": tests["overall"],
            "passed": tests["tests_passed"],
            "total": tests["tests_total"],
            "tests_are_not_gate": tests["tests_are_not_gate"],
        },
        "run": {
            "n_main_scenarios": run["n_main_scenarios"],
            "n_matched_5d_scenarios": run["n_matched_5d_scenarios"],
            "PROVISIONAL_PARAMS": run["PROVISIONAL_PARAMS"],
            "preregistration_evidence_status": run[
                "preregistration_evidence_status"
            ],
            "T3_collision_evaluation_status": run["T3"][
                "collision_evaluation"
            ]["evaluation_status"],
            "T3_collision_plan_contract_status": run["T3"][
                "collision_evaluation"
            ]["plan_contract_status"],
        },
        "independent_red_team_status": gate["independent_red_team_status"],
        "hash_policy": {
            "text": "normalized_semantic_sha256",
            "binary": "raw_sha256",
            "raw_hash_also_recorded_for_text": True,
        },
        "scope_guard": {
            "owned_prefixes": list(OWNED_PREFIXES),
            "non_owned_changed_paths": non_owned,
            "formal_safety_classification_emitted": False,
        },
        "reproduction_commands": [
            "python 30_simulation/control_01_end_effector_tracking/src/run_experiments.py",
            "python 30_simulation/control_01_end_effector_tracking/tests/run_all.py",
            "python 30_simulation/control_01_end_effector_tracking/src/run_gates.py",
        ],
        "files": rows,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "manifest": MANIFEST_PATH.relative_to(REPO_ROOT).as_posix(),
                "source_commit": args.source_commit,
                "files": len(rows),
                "verdict": gate["verdict"],
                "tests": f"{tests['tests_passed']}/{tests['tests_total']}",
                "independent_red_team_status": gate["independent_red_team_status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
