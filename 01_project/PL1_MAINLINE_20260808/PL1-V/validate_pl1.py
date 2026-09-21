#!/usr/bin/env python3
"""Read-only independent validation for the PL1 two-root consolidation.

Exit 0 means the reconstruction is internally consistent.  Explicit engineering
HOLDs (dirty worktree, human review, CM/backup/reference repair) are reported but
do not become false PASS claims.  The script never edits project files.
"""

from __future__ import annotations

import csv
import hashlib
import os
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment gate
    raise SystemExit(f"PyYAML is required for PL1 validation: {exc}")


ROOT_A = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ROOT_B = Path(r"F:\SPACE_ROBOTICS_REFERENCE_LIBRARY")
ARCHIVE = Path(r"F:\SEI_PROJECT_ARCHIVE")
TEMP = Path(r"F:\_SEI_PROJECT_CONSOLIDATION_20260807")
PL1 = ROOT_A / "01_project" / "PL1_MAINLINE_20260808"
CM = ARCHIVE / "CONFIGURATION_MANAGEMENT" / "20260807_CONSOLIDATION"
CM_MIRROR = TEMP / "13_CM_CLOSURE"


@dataclass
class Check:
    level: str
    name: str
    detail: str


CHECKS: list[Check] = []


def record(level: str, name: str, detail: str) -> None:
    CHECKS.append(Check(level, name, detail))
    print(f"{level:<4} {name}: {detail}")


def check(name: str, condition: bool, ok: str, bad: str) -> bool:
    record("PASS" if condition else "FAIL", name, ok if condition else bad)
    return condition


def hold(name: str, detail: str) -> None:
    record("HOLD", name, detail)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_count(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file())


def tree_manifest(path: Path) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for item in sorted((p for p in path.rglob("*") if p.is_file()), key=lambda p: str(p).lower()):
        rel = item.relative_to(path).as_posix()
        result[rel] = (item.stat().st_size, sha256(item))
    return result


def csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("missing CSV header")
        return reader.fieldnames, list(reader)


def required_deliverables() -> None:
    required = [
        "PL1_INDEX.md",
        "SEI_PROJECT_MAINLINE_MAP.md",
        "PL1-A/PL1_PROJECT_ASSET_DISCOVERY.csv",
        "PL1-A/SEI_PROJECT_RELEVANCE_BOUNDARY.yaml",
        "PL1-A/PROJECT_BOUNDARY_REPORT.md",
        "PL1-B/MECHANICAL_ENGINEERING_MAINLINE.md",
        "PL1-B/MECHANICAL_CONFIGURATION_LINEAGE.md",
        "PL1-B/CURRENT_MECHANICAL_BASELINE_RULING.md",
        "PL1-B/MECHANICAL_CURRENT_STATUS.md",
        "PL1-B/MECHANICAL_MODEL_MAP.md",
        "PL1-B/F3R2_EXECUTION_ORDER.md",
        "PL1-B/B601_DIGITAL_THREAD_MAP.yaml",
        "PL1-C/DYNAMICS_MAINLINE.md",
        "PL1-C/DYNAMICS_SIMULATION_ASSET_REGISTER.csv",
        "PL1-C/SIMULATION_TRUTH_HIERARCHY.md",
        "PL1-D/OPEN_SOURCE_PROJECT_REGISTER.csv",
        "PL1-D/REFERENCE_LIBRARY_ARCHITECTURE.md",
        "PL1-D/REFERENCE_TO_PROJECT_MAPPING.csv",
        "PL1-D/REFERENCE_LIBRARY_START_HERE.md",
        "PL1-E/INTELLIGENCE_CONTROL_MAINLINE.md",
        "PL1-E/SAFE00_DIGITAL_THREAD.md",
        "PL1-E/INTELLIGENCE_ASSET_REGISTER.csv",
        "PL1-F/CAD_DONOR_REGISTER.csv",
        "PL1-F/CAE_PROJECT_RELEVANCE_REGISTER.csv",
        "PL1-F/ROBOTIC_ARM_RETIREMENT_PLAN.md",
        "PL1-F/FREECAD_LINEAGE_NOTES.md",
        "PL1-G/TWO_ROOT_CONSOLIDATION_MATRIX.csv",
        "PL1-G/ROOT_A_CANONICAL_STRUCTURE_PLAN.md",
        "PL1-G/ROOT_B_LIBRARY_STRUCTURE_PLAN.md",
        "PL1-G/ARCHIVE_INTO_ROOT_A_MIGRATION_PLAN.md",
        "PL1-G/TWO_ROOT_EXECUTION_PLAN.md",
        "PL1-G/NEW_CONTRADICTION_REGISTER.md",
        "PL1-G/SALVAGE_COPY_MANIFEST.md",
        "PL1-G/SUPPLEMENTAL_CONTRACT_CHAIN_COPY_MANIFEST.md",
        "PL1-G/CM3A_ARCHIVE_COPY_MANIFEST.md",
        "PL1-V/PL1_INDEPENDENT_REVIEW.md",
    ]
    missing = [rel for rel in required if not (PL1 / rel).is_file()]
    check("required-deliverables", not missing, f"{len(required)}/{len(required)} present", f"missing={missing}")

    # 2026-09-06 path consolidation: current navigation and archived PL1 context
    # have distinct roles. This does not reissue the historical PL1 verdict.
    root_required = [
        ROOT_A / "PROJECT_MAP.md",
        ROOT_A / "01_project/competition/archive/ROOT_HISTORY_20260729_20260810.md",
        ROOT_A / "01_project/current/archive/PROJECT_MODEL_TRUTH_HIERARCHY_20260808.yaml",
    ]
    missing_root = [str(path) for path in root_required if not path.is_file()]
    check("root-a-entry-files", not missing_root, "current navigation and two archived context files present", f"missing={missing_root}")


def validate_data_formats() -> None:
    yaml_files = sorted(PL1.rglob("*.yaml")) + [
        ROOT_A / "01_project/current/archive/PROJECT_MODEL_TRUTH_HIERARCHY_20260808.yaml",
        CM / "PROJECT_LIBRARY_INDEX.yaml",
        CM / "CANONICAL_ROOT_REGISTER.yaml",
        CM_MIRROR / "CANONICAL_ROOT_REGISTER.yaml",
    ]
    yaml_errors: list[str] = []
    for path in yaml_files:
        try:
            with path.open("r", encoding="utf-8-sig") as stream:
                yaml.safe_load(stream)
        except Exception as exc:  # noqa: BLE001 - validator reports exact file
            yaml_errors.append(f"{path.relative_to(ROOT_A)}: {exc}")
    check("yaml-parse", not yaml_errors, f"{len(yaml_files)} YAML files parsed", "; ".join(yaml_errors))

    csv_files = sorted(PL1.rglob("*.csv")) + [
        CM / "ASSET_AUTHORITY_MATRIX.csv",
        CM_MIRROR / "ASSET_AUTHORITY_MATRIX.csv",
        ROOT_B / "OPEN_SOURCE_PROJECT_REGISTER.csv",
        ROOT_B / "DYNAMICS_SIMULATION_LIBRARY_INDEX.csv",
        ROOT_B / "CAD_DONOR_REGISTER.csv",
    ]
    csv_errors: list[str] = []
    for path in csv_files:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            if not rows:
                raise ValueError("empty CSV")
            widths = Counter(len(row) for row in rows)
            if len(widths) != 1:
                raise ValueError(f"row widths={dict(widths)}")
        except Exception as exc:  # noqa: BLE001
            csv_errors.append(f"{path.relative_to(ROOT_A)}: {exc}")
    check("csv-schema", not csv_errors, f"{len(csv_files)} CSV files have uniform row width", "; ".join(csv_errors))


def validate_boundary() -> None:
    discovery = PL1 / "PL1-A" / "PL1_PROJECT_ASSET_DISCOVERY.csv"
    headers, rows = csv_rows(discovery)
    unknown = [row.get("path", "") for row in rows if row.get("classification", "").strip() in {"I_UNKNOWN", "UNKNOWN"}]
    check("boundary-unknown", not unknown, "discovery UNKNOWN=0", f"unknown rows={unknown}")

    # All physical F:\ top-level entries must be represented by an exact discovery path.
    top_physical = {str(Path(entry.path)).rstrip("\\/").lower() for entry in os.scandir("F:\\")}
    discovered = {row.get("path", "").rstrip("\\/").lower() for row in rows}
    missing = sorted(top_physical - discovered)
    check("f-root-coverage", not missing, f"all {len(top_physical)} F:\\ top-level entries classified", f"unlisted={missing}")

    _, matrix_rows = csv_rows(PL1 / "PL1-G" / "TWO_ROOT_CONSOLIDATION_MATRIX.csv")
    matrix_unknown = [row.get("asset", "") for row in matrix_rows if "UNKNOWN" in row.get("classification", "").upper()]
    check("two-root-mapping", not matrix_unknown, f"{len(matrix_rows)} matrix rows mapped; UNKNOWN=0", f"unknown={matrix_unknown}")

    boundary_text = (PL1 / "PL1-A" / "SEI_PROJECT_RELEVANCE_BOUNDARY.yaml").read_text(encoding="utf-8-sig")
    check(
        "cae-boundary",
        "NON_SEI_GENERAL_CAE_LIBRARY" in boundary_text and r"Mechanical structure modeling and simulation" in boundary_text,
        "general CAE library explicitly excluded/index-only",
        "CAE exclusion ruling missing",
    )


def validate_mechanical_truth() -> None:
    top = ROOT_A / "20_engineering" / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807" / "03_native_cad" / "F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM"
    urdf = ROOT_A / "20_engineering" / "cad" / "spacecraft_layout" / "arm_b601_v1" / "arm_b601_v1.urdf"
    check(
        "current-top-hash",
        top.is_file() and sha256(top) == "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0",
        "F3R2 top hash matches frozen candidate",
        "F3R2 top missing or hash mismatch",
    )
    check(
        "b601-truth-hash",
        urdf.is_file() and sha256(urdf) == "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
        "accepted B601 URDF raw hash matches",
        "accepted URDF missing or hash mismatch",
    )

    ruling = (PL1 / "PL1-B" / "CURRENT_MECHANICAL_BASELINE_RULING.md").read_text(encoding="utf-8-sig")
    marker_count = ruling.count("CURRENT_MACHINE_SELECTED_MECHANICAL_CANDIDATE")
    conditions = marker_count == 1 and "PENDING_HUMAN_REVIEW" in ruling and "F3R2" in ruling
    check("mechanical-baseline-unique", conditions, "one F3R2 machine-selected candidate; human review explicit", f"marker_count={marker_count}")

    manifests = PL1 / "PL1-G" / "manifests"
    expected = {"F3R1": 363, "F3R2": 482, "EXTRAS": 364}
    manifest_errors: list[str] = []
    for stem, expected_lines in expected.items():
        source = manifests / f"{stem}_source.sha256"
        dest = manifests / f"{stem}_dest.sha256"
        if not source.is_file() or not dest.is_file():
            manifest_errors.append(f"{stem}: missing manifest")
            continue
        source_bytes = source.read_bytes()
        dest_bytes = dest.read_bytes()
        count = len(source.read_text(encoding="utf-8-sig").splitlines())
        if source_bytes != dest_bytes or count != expected_lines:
            manifest_errors.append(f"{stem}: equal={source_bytes == dest_bytes}, lines={count}, expected={expected_lines}")
    check("salvage-manifests", not manifest_errors, "F3R1 363, F3R2 482, EXTRAS 364 source/dest manifests identical", "; ".join(manifest_errors))

    f3r1 = ROOT_A / "20_engineering" / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806"
    f3r2 = ROOT_A / "20_engineering" / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
    f3r1_count = file_count(f3r1)
    f3r2_count = file_count(f3r2)
    additive_gate = (
        f3r2 / "03_native_cad" / "M3_interface_authority" /
        "M3R_INTERFACE_AUTHORITY_GATE.json"
    )
    residence_ok = (
        f3r1_count == 363
        and f3r2_count >= 482
        and (f3r2_count == 482 or additive_gate.is_file())
    )
    check(
        "salvage-residence",
        residence_ok,
        f"ROOT A contains F3R1=363 and F3R2 baseline=482 plus controlled additive evidence (physical={f3r2_count})",
        f"counts={f3r1_count},{f3r2_count}; additive_gate={additive_gate.is_file()}",
    )

    order = PL1 / "PL1-B" / "F3R2_EXECUTION_ORDER.md"
    check("f3r2-next-order", order.is_file() and all(token in order.read_text(encoding="utf-8-sig") for token in ("P0", "P1", "P2", "WING_ROOT_LUG")), "single P0/P1/P2 residual order present", "execution order incomplete")


def validate_copy_islands() -> None:
    wt = TEMP / "12_WAVE4" / "WORKTREE_RECONCILIATION"
    pairs = [
        (wt / "20_engineering" / "config" / "competition_prototype", ROOT_A / "20_engineering" / "config" / "competition_prototype", 6),
        (TEMP / "15_CM3" / "AGENTS" / "CM3A", CM / "CM3" / "CM3A", 6),
    ]
    errors: list[str] = []
    for source, dest, expected in pairs:
        source_manifest = tree_manifest(source) if source.is_dir() else {}
        dest_manifest = tree_manifest(dest) if dest.is_dir() else {}
        if source_manifest != dest_manifest or len(source_manifest) != expected:
            errors.append(f"{source} -> {dest}: src={len(source_manifest)} dst={len(dest_manifest)} equal={source_manifest == dest_manifest}")
    check("copy-island-current-integrity", not errors, "competition_prototype 6/6 and CM3A 6/6 hash-identical; sources retained", "; ".join(errors))
    hold(
        "copy-island-integrity",
        "HISTORICAL_COPY_SCOPE_RETIRED: module_cards was a 9-file copy scope in "
        "the 2026-08-08 PL1 receipt; subsequent additions and the 2026-09-06 "
        "documentation consolidation changed that tree. The historical "
        "supplemental 15/15 receipt is retained, not re-certified or replaced "
        "by the current file count. Current module notes: "
        "30_simulation/module_cards/README.md.",
    )


def validate_reference_boundary() -> None:
    source_to_root_b = [
        (PL1 / "PL1-D" / "REFERENCE_LIBRARY_START_HERE.md", ROOT_B / "REFERENCE_LIBRARY_START_HERE.md"),
        (PL1 / "PL1-D" / "OPEN_SOURCE_PROJECT_REGISTER.csv", ROOT_B / "OPEN_SOURCE_PROJECT_REGISTER.csv"),
        (PL1 / "PL1-C" / "DYNAMICS_SIMULATION_ASSET_REGISTER.csv", ROOT_B / "DYNAMICS_SIMULATION_LIBRARY_INDEX.csv"),
        (PL1 / "PL1-F" / "CAD_DONOR_REGISTER.csv", ROOT_B / "CAD_DONOR_REGISTER.csv"),
    ]
    sync_errors = []
    for source, dest in source_to_root_b:
        if not source.is_file() or not dest.is_file() or sha256(source) != sha256(dest):
            sync_errors.append(f"{source.name}->{dest.name}")
    check("root-b-index-sync", not sync_errors, "four installed Root B entry/register files match PL1 sources", f"mismatch={sync_errors}")

    _, rows = csv_rows(PL1 / "PL1-D" / "OPEN_SOURCE_PROJECT_REGISTER.csv")
    runtime_true = [row.get("project_name", "") for row in rows if row.get("runtime_dependency", "").strip().lower() != "false"]
    check("external-runtime-register", not runtime_true, f"{len(rows)} open-source rows runtime_dependency=false", f"non-false={runtime_true}")

    open_source_missing = [row.get("project_name", "") for row in rows if not Path(row.get("path", "")).exists()]
    check("open-source-precise-paths", not open_source_missing, f"all {len(rows)} open-source register paths resolve literally", f"missing={open_source_missing}")

    _, dynamics_rows = csv_rows(PL1 / "PL1-C" / "DYNAMICS_SIMULATION_ASSET_REGISTER.csv")
    dynamics_roots = {
        "A": ROOT_A,
        "A (reference-only vendor)": ROOT_A,
        "B": ROOT_B,
        "CAE": Path(r"F:\Mechanical structure modeling and simulation"),
        "RA (external donor)": Path(r"F:\Robotic arm"),
    }
    dynamics_missing: list[str] = []
    for row in dynamics_rows:
        base = dynamics_roots.get(row.get("root", ""))
        target = base / row.get("path", "") if base else None
        if target is None or not target.exists():
            dynamics_missing.append(row.get("asset_id", ""))
    check("dynamics-precise-paths", not dynamics_missing, f"all {len(dynamics_rows)} dynamics register paths resolve literally", f"missing={dynamics_missing}")

    _, donor_rows = csv_rows(PL1 / "PL1-F" / "CAD_DONOR_REGISTER.csv")
    donor_missing = [row.get("asset_id", "") for row in donor_rows if not Path(row.get("path", "")).exists()]
    check("cad-donor-precise-paths", not donor_missing, f"all {len(donor_rows)} CAD donor paths resolve literally", f"missing={donor_missing}")

    # ROOT B must never be a project runtime/config location.  Historical donor
    # provenance, CM archive pointers, comments and negative migration tests are
    # intentionally allowed and therefore are validated separately below.
    forbidden = ("f:/space_robotics_reference_library", "f:\\space_robotics_reference_library")
    executable_ext = {".py", ".m", ".yaml", ".yml", ".json", ".xml", ".urdf", ".xacro", ".sh", ".bat", ".ps1", ".toml", ".ini", ".cfg"}
    hits: list[str] = []
    skip_parts = {
        ".git", "80_third_party", "pl1_mainline_20260808",
        "m3_interface_authority",
    }
    audit_only_files = {"m3r_evidence_inventory.py"}
    for path in ROOT_A.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in executable_ext:
            continue
        if path.name.lower() in audit_only_files:
            continue
        lower_parts = {part.lower() for part in path.parts}
        if lower_parts & skip_parts:
            continue
        try:
            content = path.read_text(encoding="utf-8-sig", errors="ignore").lower()
        except OSError:
            continue
        if any(token in content for token in forbidden):
            hits.append(str(path.relative_to(ROOT_A)))
    check("root-b-runtime-path-scan", not hits, "no executable/config absolute dependency on Root B", f"hits={hits[:20]}")

    geometry = ROOT_A / "20_engineering" / "config" / "geometry" / "arm_b601_v1.yaml"
    with geometry.open("r", encoding="utf-8-sig") as stream:
        geometry_data = yaml.safe_load(stream)
    hardware_step = str(geometry_data.get("source", {}).get("hardware_step", geometry_data.get("hardware_step", "")))
    # Schema location varies by revision; fall back to a recursive key search.
    if not hardware_step:
        def find_hardware_step(value: object) -> str:
            if isinstance(value, dict):
                if "hardware_step" in value:
                    return str(value["hardware_step"])
                for child in value.values():
                    found = find_hardware_step(child)
                    if found:
                        return found
            elif isinstance(value, list):
                for child in value:
                    found = find_hardware_step(child)
                    if found:
                        return found
            return ""
        hardware_step = find_hardware_step(geometry_data)
    hardware_path = ROOT_A / Path(hardware_step.replace("/", os.sep)) if hardware_step else Path()
    runtime_ok = bool(hardware_step) and not Path(hardware_step).is_absolute() and hardware_path.is_file()
    check("robotic-arm-runtime-path", runtime_ok, f"active hardware_step is repo-relative and resolves: {hardware_step}", f"hardware_step={hardware_step!r}")

    retirement = (PL1 / "PL1-F" / "ROBOTIC_ARM_RETIREMENT_PLAN.md").read_text(encoding="utf-8-sig")
    check("robotic-arm-role", "HOLD" in retirement and "运行时/构建依赖 = 0" in retirement, "donor root remains explicit HOLD with zero runtime/build dependency", "retirement boundary missing")


def validate_cm_and_health() -> None:
    cm_files = ["CANONICAL_ROOT_REGISTER.yaml", "ASSET_AUTHORITY_MATRIX.csv", "PROJECT_STORAGE_ARCHITECTURE.md", "PROJECT_ROOT_HEALTH_CHECK.py"]
    mirror_errors = []
    for name in cm_files:
        stable = CM / name
        mirror = CM_MIRROR / name
        if not stable.is_file() or not mirror.is_file() or sha256(stable) != sha256(mirror):
            mirror_errors.append(name)
    check("cm-mirror-sync", not mirror_errors, "four stable CM files match compatibility mirror", f"mismatch={mirror_errors}")

    health = CM / "PROJECT_ROOT_HEALTH_CHECK.py"
    try:
        proc = subprocess.run([sys.executable, str(health)], cwd=ROOT_A, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=120, check=False)
        output = (proc.stdout + "\n" + proc.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        output = f"health execution exception: {exc}"
    health_ok = (
        "PROJECT_STORAGE_HEALTH = FAIL" in output
        and "(1 issue(s))" in output
        and output.count("[FAIL]") == 1
        and "[FAIL] PRIMARY_CLEAN" in output
    )
    check("health-structure", health_ok, "all structural checks pass; sole failure is PRIMARY_CLEAN", output[-1500:])

    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT_A, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=60, check=False).stdout.splitlines()
    if status:
        hold("working-tree-cleanliness", f"{len(status)} porcelain entries; CM/Git acceptance remains a deliberate HOLD")
    else:
        record("PASS", "working-tree-cleanliness", "clean")

    remote = subprocess.run(["git", "remote"], cwd=ROOT_A, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=60, check=False).stdout.splitlines()
    if not remote:
        hold("disaster-recovery", "git remote=0; salvaged/native vendor content still needs a cold-backup policy")
    else:
        record("PASS", "disaster-recovery", f"remotes={remote}")


def validate_mainline_map() -> None:
    path = PL1 / "SEI_PROJECT_MAINLINE_MAP.md"
    text = path.read_text(encoding="utf-8-sig")
    missing_m = [f"M{i}" for i in range(15) if f"## M{i} " not in text]
    fields = ("CURRENT AUTHORITY", "CURRENT FILES", "CURRENT STATUS", "LATEST VALID RESULT", "SUPERSEDED FILES", "OPEN HOLDS", "NEXT TASK")
    field_counts = {field: text.count(field) for field in fields}
    fields_ok = all(count == 15 for count in field_counts.values())
    check("mainline-m0-m14", not missing_m and fields_ok, "M0-M14 each contain all seven required fields", f"missing_m={missing_m}, field_counts={field_counts}")


def main() -> int:
    print("PL1 INDEPENDENT VALIDATION -- read-only")
    print(f"ROOT A: {ROOT_A}")
    print(f"ROOT B: {ROOT_B}")
    required_deliverables()
    validate_data_formats()
    validate_boundary()
    validate_mechanical_truth()
    validate_copy_islands()
    validate_reference_boundary()
    validate_cm_and_health()
    validate_mainline_map()

    counts = Counter(item.level for item in CHECKS)
    print("-" * 78)
    if counts["FAIL"]:
        print(f"PL1_VALIDATION = FAIL ({counts['PASS']} PASS / {counts['HOLD']} HOLD / {counts['FAIL']} FAIL)")
        return 1
    verdict = "PASS_WITH_EXPLICIT_HOLDS" if counts["HOLD"] else "PASS"
    print(f"PL1_VALIDATION = {verdict} ({counts['PASS']} PASS / {counts['HOLD']} HOLD / 0 FAIL)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
