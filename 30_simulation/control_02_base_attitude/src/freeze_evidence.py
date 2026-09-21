"""Freeze LOOP-7 pre-review evidence without modifying frozen modules."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path

from config_loader import MODULE, REPO, load_config


RESULTS = MODULE / "results"


def _normalized(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_text(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO,
        text=True,
        encoding="utf-8",
        stderr=subprocess.STDOUT,
    ).strip()


def source_commit_record(requested: str, require_current_head: bool) -> dict:
    """Resolve and validate the immutable source commit bound to the evidence."""
    try:
        resolved = _git_text("rev-parse", "--verify", f"{requested}^{{commit}}")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"source commit does not exist: {requested}") from exc

    current_head = _git_text("rev-parse", "HEAD")
    if require_current_head and current_head != resolved:
        raise RuntimeError(
            "freeze must run from the bound source commit: "
            f"HEAD={current_head}, source_commit={resolved}"
        )

    parent_line = _git_text("rev-list", "--parents", "-n", "1", resolved).split()
    parent = parent_line[1] if len(parent_line) > 1 else None
    try:
        branch = _git_text("symbolic-ref", "--short", "HEAD")
    except subprocess.CalledProcessError:
        branch = "DETACHED"
    return {
        "source_commit": resolved,
        "source_commit_parent": parent,
        "source_git_tree_oid": _git_text(
            "rev-parse", "--verify", f"{resolved}^{{tree}}"
        ),
        "branch": branch,
        "current_head": current_head,
    }


def source_tree_record() -> dict:
    """Hash the owned, non-result source tree with line-ending normalization."""
    entries = {}
    roots = [MODULE, REPO / "20_engineering" / "config" / "attitude_stab"]
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if root == MODULE and "results" in path.relative_to(MODULE).parts:
                continue
            rel = path.relative_to(REPO).as_posix()
            normalized = _normalized(path.read_bytes())
            entries[rel] = {
                "normalized_lf_sha256": _sha(normalized),
                "normalized_lf_bytes": len(normalized),
            }
    tree_payload = "".join(
        f"{rel}\0{spec['normalized_lf_sha256']}\n"
        for rel, spec in sorted(entries.items())
    ).encode("utf-8")
    return {
        "algorithm": "sha256",
        "hash_mode": "normalized_lf",
        "scope": [
            "20_engineering/config/attitude_stab/**",
            "30_simulation/control_02_base_attitude/** excluding results/** and __pycache__/**",
        ],
        "file_count": len(entries),
        "sha256": _sha(tree_payload),
        "files": entries,
    }


def environment_record() -> dict:
    packages = {}
    for distribution in ("numpy", "scipy", "PyYAML", "matplotlib"):
        try:
            packages[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            packages[distribution] = "NOT_INSTALLED"
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": packages,
    }


def _artifact_consistency(artifacts: dict) -> dict:
    mismatches = []
    for rel, expected in artifacts.items():
        path = REPO / rel
        if not path.is_file():
            mismatches.append({"path": rel, "reason": "missing"})
            continue
        data = path.read_bytes()
        if _sha(data) != expected["sha256"] or len(data) != expected["bytes"]:
            mismatches.append({"path": rel, "reason": "hash_or_size_mismatch"})
    return {
        "status": "PASS" if not mismatches else "BLOCKED",
        "checked_artifact_count": len(artifacts),
        "mismatches": mismatches,
    }


def verify_manifest() -> dict:
    manifest = json.loads(
        (RESULTS / "evidence_manifest_pre_review.json").read_text(encoding="utf-8")
    )
    artifact_check = _artifact_consistency(manifest["artifacts"])
    current_tree = source_tree_record()
    source_match = (
        current_tree["sha256"] == manifest["source_tree"]["sha256"]
        and current_tree["file_count"] == manifest["source_tree"]["file_count"]
        and current_tree["files"] == manifest["source_tree"]["files"]
    )
    source_git = source_commit_record(
        manifest["source_commit"], require_current_head=False
    )
    source_commit_metadata_match = (
        source_git["source_commit"] == manifest["source_commit"]
        and source_git["source_commit_parent"] == manifest["source_commit_parent"]
        and source_git["source_git_tree_oid"] == manifest["source_git_tree_oid"]
        and source_git["branch"] == manifest["branch"]
    )
    return {
        "status": (
            "PASS"
            if (
                artifact_check["status"] == "PASS"
                and source_match
                and source_commit_metadata_match
            )
            else "BLOCKED"
        ),
        "artifact_check": artifact_check,
        "source_tree_match": source_match,
        "source_commit_metadata_match": source_commit_metadata_match,
    }


def write_autocrlf_audit(cfg: dict) -> dict:
    rows = {}
    for key, spec in cfg["frozen_inputs"].items():
        path = REPO / spec["path"]
        working = path.read_bytes()
        # Git blobs are the byte source a clean core.autocrlf=false checkout uses.
        canonical = subprocess.check_output(
            ["git", "-c", "core.autocrlf=false", "show", f"HEAD:{spec['path']}"],
            cwd=REPO,
        )
        expected = spec["sha256"]
        rows[key] = {
            "path": spec["path"],
            "expected_normalized_lf_sha256": expected,
            "working_raw_sha256": _sha(working),
            "working_normalized_lf_sha256": _sha(_normalized(working)),
            "git_canonical_raw_sha256": _sha(canonical),
            "git_canonical_normalized_lf_sha256": _sha(_normalized(canonical)),
            "working_match": _sha(_normalized(working)) == expected,
            "core_autocrlf_false_equivalent_match": _sha(_normalized(canonical))
            == expected,
        }
    out = {
        "schema_version": "control02-autocrlf-audit-v1",
        "method": (
            "Compare normalized working bytes with the canonical Git blob used by a "
            "clean core.autocrlf=false checkout; separately retain raw hashes."
        ),
        "all_match": all(
            r["working_match"] and r["core_autocrlf_false_equivalent_match"]
            for r in rows.values()
        ),
        "files": rows,
    }
    with (RESULTS / "autocrlf_false_hash_audit.json").open(
        "w", encoding="utf-8", newline="\n"
    ) as f:
        f.write(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    return out


def freeze(source_commit: str) -> dict:
    source_git = source_commit_record(source_commit, require_current_head=True)
    cfg = load_config()
    audit = write_autocrlf_audit(cfg)
    gate = json.loads(
        (RESULTS / "control_02_gate_check.json").read_text(encoding="utf-8")
    )
    tests = json.loads((RESULTS / "test_report.json").read_text(encoding="utf-8"))
    roots = [MODULE, REPO / "20_engineering" / "config" / "attitude_stab"]
    artifacts = {}
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            rel = path.relative_to(REPO).as_posix()
            if rel.endswith("results/evidence_manifest_pre_review.json"):
                continue
            data = path.read_bytes()
            artifacts[rel] = {
                "sha256": _sha(data),
                "bytes": len(data),
            }
    out = {
        "schema_version": "control02-loop7-pre-review-v3",
        "baseline_commit": cfg["baseline_commit"],
        "source_commit": source_git["source_commit"],
        "source_commit_parent": source_git["source_commit_parent"],
        "source_git_tree_oid": source_git["source_git_tree_oid"],
        "branch": source_git["branch"],
        "scientific_gate_verdict": gate["verdict"],
        "machine_gates": {k: v["status"] for k, v in gate["gates"].items()},
        "tests": {
            "passed": tests["tests_passed"],
            "total": tests["tests_total"],
        },
        "review_status": "PENDING_REVIEW",
        "loop6_independent_red_team_complete": False,
        "autocrlf_false_hash_audit": (
            "PASS" if audit["all_match"] else "BLOCKED"
        ),
        "source_tree": source_tree_record(),
        "environment": environment_record(),
        "reproduction_and_freeze_commands": [
            "python 30_simulation/control_02_base_attitude/tests/run_all.py",
            "python 30_simulation/control_02_base_attitude/src/run_gates.py",
            (
                "python 30_simulation/control_02_base_attitude/src/freeze_evidence.py "
                f"--source-commit {source_git['source_commit']}"
            ),
        ],
        "post_result_scene_edit_audit": {
            "observed": True,
            "edit": "M2 q2/q3 start was temporarily changed from 0 deg to -5 deg after observing margin=0 (first round).",
            "disposition": "WITHDRAWN_BEFORE_FINAL_FREEZE",
            "historical_first_round_start_deg": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "repeat_registration": (
                "10_research/partner_requirement_closure/wave1_repeat/"
                "repeat_preregistration.md (R-4/R-5, CP3 approved)"
            ),
            "final_registered_start_deg": [0.0, -15.0, -15.0, 0.0, 0.0, 0.0],
            "withdrawn_probe_reused": False,
            "final_margin_min_rad": gate["gates"][
                "GC1_stage_A_anchor_and_reduction"
            ]["M2_joint_limit_margin_min_rad"],
            "final_gate_status": gate["gates"][
                "GC1_stage_A_anchor_and_reduction"
            ]["status"],
            "note": (
                "The withdrawn post-result -5 deg probe was never reused. The "
                "current -15 deg interior start is the CTRL-02-R R4 revision, "
                "registered in repeat_preregistration.md BEFORE this rerun, "
                "with all thresholds frozen."
            ),
        },
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "self_consistency": {
            "status": "PENDING_WRITE_AND_REOPEN",
        },
    }
    with (RESULTS / "evidence_manifest_pre_review.json").open(
        "w", encoding="utf-8", newline="\n"
    ) as f:
        f.write(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    consistency = verify_manifest()
    if consistency["status"] != "PASS":
        raise RuntimeError(f"evidence manifest self-check failed: {consistency}")
    out["self_consistency"] = consistency
    with (RESULTS / "evidence_manifest_pre_review.json").open(
        "w", encoding="utf-8", newline="\n"
    ) as f:
        f.write(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    final_consistency = verify_manifest()
    if final_consistency["status"] != "PASS":
        raise RuntimeError(
            f"evidence manifest final self-check failed: {final_consistency}"
        )
    print(
        json.dumps(
            {
                "scientific_gate_verdict": out["scientific_gate_verdict"],
                "tests": out["tests"],
                "review_status": out["review_status"],
                "artifact_count": out["artifact_count"],
                "autocrlf_false_hash_audit": out[
                    "autocrlf_false_hash_audit"
                ],
                "source_tree_sha256": out["source_tree"]["sha256"],
                "self_consistency": final_consistency["status"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Freeze CTRL-02 evidence against an explicit source commit."
    )
    parser.add_argument(
        "--source-commit",
        required=True,
        help="existing commit that must exactly equal current HEAD",
    )
    args = parser.parse_args()
    freeze(args.source_commit)
