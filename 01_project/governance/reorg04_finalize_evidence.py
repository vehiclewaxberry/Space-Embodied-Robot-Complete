"""Generate REORG04 integrity evidence without running scientific simulations."""
from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

import yaml


GATE_MAP = {
    r"artifacts\visualization\e15_gate_evidence_snapshot_20260714\results__sim_09_grasp_evaluator__e15_gate_check.json": "40_evidence/artifacts/visualization/e15_gate_evidence_snapshot_20260714/results__sim_09_grasp_evaluator__e15_gate_check.json",
    r"assembly_research\ASM-00_interface_ssot\results\asm_00_gate_check.json": "30_simulation/asm_00_interface_preflight/results/asm_00_gate_check.json",
    r"e15_ancf_certification\results\gate_summary.json": "30_simulation/e15_ancf_certification/results/gate_summary.json",
    r"e15_core_coverage\results\core_gate_check.json": "30_simulation/e15_core_coverage/results/core_gate_check.json",
    r"e16_sync_capture\results\gate_check.json": "30_simulation/e16_sync_capture/results/gate_check.json",
    r"research\competition_convergence\competition_gate_check.json": "10_research/competition_convergence/competition_gate_check.json",
    r"research\partner_requirement_closure\wave1_results\wave1_gate_check.json": "10_research/partner_requirement_closure/wave1_results/wave1_gate_check.json",
    r"results\sim_09_grasp_evaluator\e1_gate_check.json": "30_simulation/sim_09_grasp_evaluator/results/e1_gate_check.json",
    r"sim\control_01_end_effector_tracking\results\control_01_gate_check.json": "30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json",
    r"sim\control_02_base_attitude\results\control_02_gate_check.json": "30_simulation/control_02_base_attitude/results/control_02_gate_check.json",
    r"sim\safety_00_runtime_gate\results\safety_00_gate_check.json": "30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json",
    r"sim\sim_10_mission_feasibility\results\sim_10_gate_check.json": "30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json",
    r"sim\sim_11_coupled_dynamics\results\gates_inline_partial.json": "30_simulation/sim_11_coupled_dynamics/results/gates_inline_partial.json",
    r"sim\sim_11_coupled_dynamics\results\sim_11_gate_check.json": "30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json",
    r"sim\sim_12_strategy_feasibility\results\sim_12_gate_check.json": "30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json",
}

BUSINESS_ROOTS = (
    "01_project", "10_research", "20_engineering", "30_simulation",
    "40_evidence", "50_literature", "70_tools", "80_third_party",
)
LEGACY_ROOTS = (
    "artifacts", "assembly_research", "cad", "config", "docs",
    "e15_ancf_certification", "e15_core_coverage", "e16_sync_capture",
    "external", "figures", "knowledge_base", "pdf", "research", "results",
    "sim", "src", "tables", "tests", "tools", "vendor", "videos", "补充论文",
)
TEXT_SUFFIXES = {
    ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".py", ".ps1",
    ".sh", ".bat", ".cmd", ".toml", ".ini", ".cfg", ".html", ".htm",
    ".js", ".ts", ".css", ".xml", ".rst", ".tex", ".bib",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_rewriter(root: Path):
    path = root / "01_project/governance/reorg04_rewrite_paths.py"
    spec = importlib.util.spec_from_file_location("reorg04_paths", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def transform_string(value: str, root: Path, rewriter) -> str:
    root_text = str(root)
    if re.match(r"^[A-Za-z]:[\\/]", value):
        if value.lower().startswith(root_text.lower() + "\\"):
            relative = value[len(root_text) + 1 :].replace("\\", "/")
            mapped = rewriter.map_old_rel_to_new(relative).replace("/", "\\")
            return root_text + "\\" + mapped
        return value
    transformed, _ = rewriter.generic_rewrite(value)
    transformed, _ = rewriter.repair_generated_duplicates(transformed)
    return transformed


def transform_value(value, root: Path, rewriter):
    if isinstance(value, str):
        return transform_string(value, root, rewriter)
    if isinstance(value, list):
        return [transform_value(item, root, rewriter) for item in value]
    if isinstance(value, dict):
        return {
            transform_string(str(key), root, rewriter): transform_value(item, root, rewriter)
            for key, item in value.items()
        }
    return value


def deep_diff(left, right, pointer: str = "$") -> list[str]:
    if type(left) is not type(right):
        return [f"{pointer}: type {type(left).__name__} != {type(right).__name__}"]
    if isinstance(left, dict):
        output: list[str] = []
        for key in sorted(set(left) - set(right)):
            output.append(f"{pointer}.{key}: missing current key")
        for key in sorted(set(right) - set(left)):
            output.append(f"{pointer}.{key}: unexpected current key")
        for key in sorted(set(left) & set(right)):
            output.extend(deep_diff(left[key], right[key], f"{pointer}.{key}"))
        return output
    if isinstance(left, list):
        output = [] if len(left) == len(right) else [f"{pointer}: length mismatch"]
        for index, (a, b) in enumerate(zip(left, right)):
            output.extend(deep_diff(a, b, f"{pointer}[{index}]"))
        return output
    return [] if left == right else [f"{pointer}: value mismatch"]


def gate_evidence(root: Path, backup: Path, rewriter, output: Path) -> dict:
    baseline_rows = list(
        csv.DictReader((backup / "baseline_gate_hashes.csv").open(encoding="utf-8-sig"))
    )
    rows = []
    non_path_differences = 0
    for baseline in baseline_rows:
        old_path = baseline["path"]
        new_path = GATE_MAP[old_path]
        old_bytes = (backup / "gate_bytes" / baseline["backup_file"]).read_bytes()
        new_bytes = (root / new_path).read_bytes()
        expected = transform_value(json.loads(old_bytes.decode("utf-8-sig")), root, rewriter)
        current = json.loads(new_bytes.decode("utf-8-sig"))
        differences = deep_diff(expected, current)
        non_path_differences += len(differences)
        rows.append(
            {
                "old_path": old_path.replace("\\", "/"),
                "new_path": new_path,
                "bytes_before": len(old_bytes),
                "bytes_after": len(new_bytes),
                "sha256_before": sha256_bytes(old_bytes),
                "sha256_after": sha256_bytes(new_bytes),
                "path_only_verified": str(not differences).lower(),
                "non_path_difference_count": len(differences),
            }
        )
    with (output / "reorg04_gate_refreeze.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return {
        "count": len(rows),
        "path_only_verified": non_path_differences == 0,
        "non_path_difference_count": non_path_differences,
    }


def pdf_evidence(root: Path, backup: Path, output: Path) -> dict:
    baseline_rows = list(
        csv.DictReader((backup / "baseline_pdf_hashes.csv").open(encoding="utf-8-sig"))
    )
    rows = []
    for baseline in baseline_rows:
        old_path = baseline["path"].replace("\\", "/")
        new_path = "50_literature/pdf/" + old_path.split("/", 1)[1]
        current = root / new_path
        current_hash = sha256_bytes(current.read_bytes())
        rows.append(
            {
                "old_path": old_path,
                "new_path": new_path,
                "bytes_before": baseline["bytes"],
                "bytes_after": current.stat().st_size,
                "sha256_before": baseline["sha256"],
                "sha256_after": current_hash,
                "byte_identical": str(
                    int(baseline["bytes"]) == current.stat().st_size
                    and baseline["sha256"] == current_hash
                ).lower(),
            }
        )
    with (output / "reorg04_pdf_integrity.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return {
        "count": len(rows),
        "all_byte_identical": all(row["byte_identical"] == "true" for row in rows),
    }


def root_evidence(root: Path, output: Path) -> dict:
    roles = {
        "01_project": "project_governance_and_competition",
        "10_research": "research_governance",
        "20_engineering": "engineering_definition",
        "30_simulation": "simulation_and_machine_gates",
        "40_evidence": "evidence_and_visualization",
        "50_literature": "literature_library",
        "70_tools": "offline_tools",
        "80_third_party": "third_party_dependencies",
    }
    rows = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        rows.append(
            {
                "entry": path.name,
                "type": "directory" if path.is_dir() else "file",
                "business_root": str(path.name in BUSINESS_ROOTS).lower(),
                "role": roles.get(path.name, "root_entry_or_metadata"),
            }
        )
    with (output / "reorg04_root_inventory.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return {
        "entry_count": len(rows),
        "business_root_count": sum(row["business_root"] == "true" for row in rows),
        "business_roots_exact": all((root / name).is_dir() for name in BUSINESS_ROOTS),
        "legacy_roots_absent": all(not (root / name).exists() for name in LEGACY_ROOTS),
    }


def markdown_links(root: Path) -> dict:
    inline = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
    reference = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)", re.MULTILINE)
    html = re.compile(r"(?i)(?:href|src)\s*=\s*[\"']([^\"']+)[\"']")
    broken = []
    checked = 0
    for path in root.rglob("*.md"):
        relative = path.relative_to(root).as_posix()
        if relative.startswith((".git/", "80_third_party/", "50_literature/pdf/")):
            continue
        text = path.read_text(encoding="utf-8-sig")
        targets = [match.group(1) for match in inline.finditer(text)]
        targets += [match.group(1) for match in reference.finditer(text)]
        targets += [match.group(1) for match in html.finditer(text)]
        for raw in targets:
            raw = raw.strip()
            if not raw or raw.startswith("#") or re.match(
                r"(?i)^(?:https?://|mailto:|data:|javascript:|tel:)", raw
            ):
                continue
            if raw.startswith("<") and ">" in raw:
                target = raw[1 : raw.index(">")]
            else:
                target = raw.split()[0]
            target = unquote(target).replace("\\", "/")
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue
            checked += 1
            if re.match(r"^[A-Za-z]:/", target):
                candidate = Path(target)
                try:
                    candidate.resolve().relative_to(root)
                except ValueError:
                    continue
            elif target.startswith("/"):
                candidate = root / target.lstrip("/")
            else:
                candidate = (path.parent / target).resolve()
            if not candidate.exists():
                broken.append({"source": relative, "target": raw})
    return {"checked": checked, "broken_count": len(broken), "broken": broken}


def syntax_evidence(root: Path, baseline_commit: str, rewriter) -> dict:
    counts = {"python_ok": 0, "json_ok": 0, "yaml_ok": 0}
    failures = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith((".git/", "80_third_party/", "50_literature/pdf/")):
            continue
        try:
            if path.suffix.lower() == ".py":
                ast.parse(path.read_text(encoding="utf-8-sig"))
                counts["python_ok"] += 1
            elif path.suffix.lower() == ".json":
                json.loads(path.read_text(encoding="utf-8-sig"))
                counts["json_ok"] += 1
            elif path.suffix.lower() in {".yaml", ".yml"}:
                list(yaml.safe_load_all(path.read_text(encoding="utf-8-sig")))
                counts["yaml_ok"] += 1
        except Exception as error:  # evidence collection, exact exception retained below
            item = {"path": relative, "error": f"{type(error).__name__}: {error}"}
            old_relative = rewriter.map_new_source_to_old(relative)
            try:
                baseline = subprocess.check_output(
                    ["git", "show", f"{baseline_commit}:{old_relative}"], cwd=root
                ).decode("utf-8-sig")
                if path.suffix.lower() in {".yaml", ".yml"}:
                    try:
                        list(yaml.safe_load_all(baseline))
                        baseline_invalid = False
                    except Exception:
                        baseline_invalid = True
                    expected, _ = rewriter.generic_rewrite(baseline)
                    expected, _ = rewriter.repair_generated_duplicates(expected)
                    item["preexisting_invalid"] = baseline_invalid
                    item["current_equals_path_transformed_baseline"] = (
                        path.read_text(encoding="utf-8-sig") == expected
                    )
            except Exception:
                item["preexisting_invalid"] = None
            failures.append(item)
    return {**counts, "failure_count": len(failures), "failures": failures}


def stale_references(root: Path) -> dict:
    legacy_body = (
        r"(?:research|knowledge_base|e15_ancf_certification|e15_core_coverage|"
        r"e16_sync_capture|assembly_research|external|vendor)[/\\]"
        r"|sim[/\\](?:sim_|common|control_|safety_)"
        r"|config[/\\](?:attitude_stab|control_scene|coupled_scene|geometry|"
        r"grasp_evaluator|mission_feasibility|safety_gate|strategy_feasibility|"
        r"visualization|assembly)"
        r"|docs[/\\](?:00_|20_|90_|95_|stage1)"
        r"|artifacts[/\\](?:visualization|competition_convergence)"
        r"|cad[/\\]spacecraft_layout"
        r"|tools[/\\]research_dashboard"
        r"|src[/\\](?:sim_09_grasp_evaluator|visualization)"
        r"|tests[/\\](?:sim_09_grasp_evaluator|visualization)"
        r"|results[/\\]sim_09_grasp_evaluator"
        r"|figures[/\\](?:sim_09_grasp_evaluator|visualization)"
        r"|tables[/\\](?:sim_09_grasp_evaluator|visualization)"
        r"|videos[/\\]visualization"
        r"|pdf[/\\]0[1-8]_"
    )
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_./\\])(?P<path>(?:\.\.?[/\\])*(?:{legacy_body}))"
    )
    provenance_only_files = {
        "40_evidence/artifacts/visualization/tables/gate_artifact_protection_manifest.csv",
        "40_evidence/artifacts/visualization/viz_gate0_freeze_manifest_20260714.csv",
        "70_tools/research_dashboard/tests/run_all.py",
    }
    hits = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        # These files deliberately retain pre-REORG04 paths in named provenance
        # fields or tagged-blob checks.  Their active paths and hashes are
        # validated independently by refrozen_evidence().
        if relative in provenance_only_files:
            continue
        if relative.startswith(
            (
                ".git/", "80_third_party/", "50_literature/pdf/",
                "01_project/competition/archive/", "01_project/governance/reorg02",
                "01_project/governance/reorg03", "01_project/governance/reorg04",
            )
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        for match in pattern.finditer(text):
            token = match.group("path").replace("\\", "/")
            if token.startswith("."):
                candidate = (path.parent / token).resolve()
                if candidate.exists():
                    continue
            hits.append({"path": relative, "legacy_path": token})
    return {"active_hit_count": len(hits), "hits": hits}


def vendor_evidence(root: Path) -> dict:
    rows = []
    vendor = root / "80_third_party/vendor"
    for path in sorted(vendor.iterdir()):
        if not path.is_dir() or not (path / ".git").exists():
            continue
        head = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(path), "status", "--porcelain"], text=True
        ).strip()
        rows.append({"repository": path.name, "head": head, "clean": not bool(dirty)})
    return {"count": len(rows), "all_clean": all(row["clean"] for row in rows), "repositories": rows}


def refrozen_evidence(root: Path) -> dict:
    protection_path = root / "40_evidence/artifacts/visualization/tables/gate_artifact_protection_manifest.csv"
    freeze_path = root / "40_evidence/artifacts/visualization/viz_gate0_freeze_manifest_20260714.csv"
    ledger_path = root / "01_project/governance/reorg04_evidence_refreeze.csv"
    test_path = root / "70_tools/research_dashboard/tests/test_results.json"

    with protection_path.open(encoding="utf-8-sig", newline="") as handle:
        protection_rows = list(csv.DictReader(handle))
    with freeze_path.open(encoding="utf-8-sig", newline="") as handle:
        freeze_rows = list(csv.DictReader(handle))
    with ledger_path.open(encoding="utf-8-sig", newline="") as handle:
        ledger_rows = list(csv.DictReader(handle))

    protection_mismatches = []
    for row in protection_rows:
        snapshot = root / row["snapshot_path"].replace("\\", "/")
        current_hash = sha256_bytes(snapshot.read_bytes()).upper() if snapshot.is_file() else ""
        if (
            not snapshot.is_file()
            or current_hash != row["expected_sha256"].upper()
            or row["actual_sha256"].upper() != row["expected_sha256"].upper()
            or row["match_expected"].lower() != "true"
            or row["snapshot_hash_match"].lower() != "true"
            or not row.get("pre_reorg04_expected_sha256")
            or row.get("refreeze_reason") != "root_namespace_path_refreeze_reorg04"
        ):
            protection_mismatches.append(row["snapshot_path"])

    freeze_mismatches = []
    for row in freeze_rows:
        path = root / row["path"].replace("\\", "/")
        current_hash = sha256_bytes(path.read_bytes()).upper() if path.is_file() else ""
        if (
            not path.is_file()
            or current_hash != row["sha256"].upper()
            or path.stat().st_size != int(row["size_bytes"])
            or not row.get("pre_reorg04_sha256")
            or row.get("refreeze_reason") != "root_namespace_path_refreeze_reorg04"
        ):
            freeze_mismatches.append(row["path"])

    test_result = json.loads(test_path.read_text(encoding="utf-8-sig"))
    return {
        "protection_rows": len(protection_rows),
        "protection_mismatch_count": len(protection_mismatches),
        "protection_mismatches": protection_mismatches,
        "freeze_rows": len(freeze_rows),
        "freeze_mismatch_count": len(freeze_mismatches),
        "freeze_mismatches": freeze_mismatches,
        "provenance_ledger_rows": len(ledger_rows),
        "offline_acceptance": {
            "passed": test_result.get("passed"),
            "total": test_result.get("total"),
            "overall": test_result.get("overall"),
        },
        "all_verified": (
            len(protection_rows) == 22
            and not protection_mismatches
            and len(freeze_rows) == 29
            and not freeze_mismatches
            and len(ledger_rows) == 51
            and test_result.get("overall") == "PASS"
            and test_result.get("passed") == test_result.get("total") == 18
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--backup-root", required=True)
    parser.add_argument("--baseline-commit", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    backup = Path(args.backup_root).resolve()
    output = root / "01_project/governance"
    rewriter = load_rewriter(root)
    validation_path = output / "reorg04_validation.json"
    if not validation_path.exists():
        validation_path.write_text("{}\n", encoding="utf-8")

    gate = gate_evidence(root, backup, rewriter, output)
    pdf = pdf_evidence(root, backup, output)
    root_state = root_evidence(root, output)
    links = markdown_links(root)
    syntax = syntax_evidence(root, args.baseline_commit, rewriter)
    stale = stale_references(root)
    vendor = vendor_evidence(root)
    evidence_refreeze = refrozen_evidence(root)
    known_syntax_exception = (
        syntax["failure_count"] == 1
        and syntax["failures"][0].get("preexisting_invalid") is True
        and syntax["failures"][0].get("current_equals_path_transformed_baseline") is True
    )
    overall = all(
        (
            gate["path_only_verified"],
            pdf["all_byte_identical"],
            root_state["business_roots_exact"],
            root_state["legacy_roots_absent"],
            links["broken_count"] == 0,
            stale["active_hit_count"] == 0,
            vendor["all_clean"],
            evidence_refreeze["all_verified"],
            syntax["failure_count"] == 0 or known_syntax_exception,
        )
    )
    summary = {
        "schema": "reorg04-validation-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": args.baseline_commit,
        "scientific_simulations_run": False,
        "gate": gate,
        "pdf": pdf,
        "root": root_state,
        "markdown_links": links,
        "syntax": syntax,
        "known_preexisting_syntax_exception_accepted": known_syntax_exception,
        "stale_active_root_references": stale,
        "third_party_vendor": vendor,
        "path_bound_evidence_refreeze": evidence_refreeze,
        "overall": "PASS" if overall else "FAIL",
    }
    validation_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"overall": summary["overall"], "gate": gate, "pdf": pdf,
                      "root": root_state, "links": links["broken_count"],
                      "syntax_failures": syntax["failure_count"],
                      "stale": stale["active_hit_count"], "vendor": vendor["count"],
                      "evidence_refreeze": evidence_refreeze},
                     ensure_ascii=False))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
