#!/usr/bin/env python3
"""Generate bounded CAD CLI inspection, snapshot, and cache-relocation evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = next(candidate for candidate in (PACKAGE, *PACKAGE.parents) if (candidate / "PROJECT_MAP.md").is_file())
CAD = PACKAGE / "01_cad"
REVIEWS = PACKAGE / "07_reviews"
SNAPSHOTS = REVIEWS / "snapshots"
CACHE = REVIEWS / "cad_cache"
CONTRACT = PACKAGE / "00_contract/LINK2_B12_OPERATIONAL_COLLISION_CONTRACT_V1.json"
INSPECT = Path(r"F:\codex_skill\AgentSkills\agents-skills\cad\scripts\inspect")
SNAPSHOT = Path(r"F:\codex_skill\AgentSkills\agents-skills\cad\scripts\snapshot")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def atomic_json(path: Path, document: dict[str, Any]) -> None:
    data = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        command,
        cwd=str(ROOT),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    step_names = [row["output"] for row in contract["objects"]]
    require(len(step_names) == len(set(step_names)) == 12, "expected exact twelve distinct STEP names")
    steps = [CAD / name for name in step_names]
    require(all(path.is_file() for path in steps), "one or more primary STEP files are missing")
    require({path.name for path in CAD.iterdir() if path.is_file() and path.suffix.lower() == ".step"} == set(step_names), "01_cad STEP set drift")

    inspect_rows = []
    for step in steps:
        command = [
            sys.executable,
            "-X",
            "utf8",
            str(INSPECT),
            "refs",
            str(step.resolve()),
            "--facts",
            "--planes",
            "--positioning",
            "--format",
            "json",
            "--quiet",
        ]
        completed = run(command)
        require(completed.returncode == 0, f"CAD inspect failed for {step.name}: {completed.stdout} {completed.stderr}")
        document = json.loads(completed.stdout)
        require(document.get("ok") is True and document.get("errors") == [] and len(document.get("tokens", [])) == 1, f"CAD inspect response drift: {step.name}")
        token = document["tokens"][0]
        summary = token["summary"]
        require(summary["occurrenceCount"] == summary["leafOccurrenceCount"] == summary["shapeCount"] == 1, f"CAD inspect root drift: {step.name}")
        require(summary["faceCount"] > 0 and summary["edgeCount"] > 0, f"CAD inspect empty topology: {step.name}")
        inspect_rows.append({
            "bbox_mm": [summary["bounds"]["min"], summary["bounds"]["max"]],
            "edge_count": summary["edgeCount"],
            "face_count": summary["faceCount"],
            "file": step.name,
            "leaf_occurrence_count": summary["leafOccurrenceCount"],
            "occurrence_count": summary["occurrenceCount"],
            "shape_count": summary["shapeCount"],
            "step_sha256": token["stepHash"].upper(),
            "warnings": token.get("warnings", []),
        })

    snapshot_rows = []
    for step in steps:
        pattern = f"{step.stem}_iso_*.png"
        matches = sorted(SNAPSHOTS.glob(pattern))
        if not matches:
            requested = SNAPSHOTS / f"{step.stem}_iso.png"
            command = [
                sys.executable,
                "-X",
                "utf8",
                str(SNAPSHOT),
                "--input",
                str(step.resolve()),
                "--output",
                str(requested.resolve()),
                "--appearance",
                "workbench",
                "--camera",
                "iso",
                "--size-profile",
                "diagnostic",
            ]
            completed = run(command)
            require(completed.returncode == 0, f"CAD snapshot failed for {step.name}: {completed.stdout} {completed.stderr}")
            output_match = re.search(r"saved snapshot:\s*(.+\.png)\s*$", completed.stdout.strip(), flags=re.IGNORECASE)
            require(output_match is not None, f"CAD snapshot output path missing: {step.name}: {completed.stdout}")
            matches = [Path(output_match.group(1))]
        require(len(matches) == 1 and matches[0].is_file(), f"snapshot multiplicity drift for {step.name}: {matches}")
        snapshot = matches[0]
        snapshot_rows.append({
            "file": step.name,
            "snapshot": {
                "bytes": snapshot.stat().st_size,
                "path": snapshot.relative_to(PACKAGE).as_posix(),
                "sha256": sha(snapshot),
            },
        })

    hidden_glbs = sorted(path for path in CAD.iterdir() if path.is_file() and path.name.startswith(".") and path.name.endswith(".step.glb"))
    expected_glbs = {f".{name}.glb" for name in step_names}
    require({path.name for path in hidden_glbs} == expected_glbs, f"CAD diagnostic GLB set drift: {[path.name for path in hidden_glbs]}")
    cache_rows = []
    for source in hidden_glbs:
        require(source.resolve().parent == CAD.resolve(), f"unsafe cache source: {source}")
        target = CACHE / source.name
        require(target.resolve().parent == CACHE.resolve() and not target.exists(), f"unsafe or pre-existing cache target: {target}")
        source.replace(target)
        cache_rows.append({"bytes": target.stat().st_size, "name": target.name, "sha256": sha(target)})
    cad_files = sorted(path for path in CAD.iterdir() if path.is_file())
    require(len(cad_files) == 12 and all(path.suffix.lower() == ".step" for path in cad_files), "01_cad did not return to STEP-only state")

    inspect_document = {
        "command": "python -X utf8 F:/codex_skill/AgentSkills/agents-skills/cad/scripts/inspect refs <explicit-step> --facts --planes --positioning --format json --quiet",
        "errors_total": 0,
        "generated_utc": "EXECUTED_2026-08-28_LOCAL_NO_WALLCLOCK_CLAIM",
        "objects": inspect_rows,
        "requested": 12,
        "responses_ok": 12,
        "schema": "ROUTE_C_LINK2_B12_CAD_INSPECT_REFS_SUMMARY_V1",
        "verdict": "CAD_INSPECT_REFS_FACTS_PLANES_POSITIONING_12_OF_12_PASS",
    }
    snapshot_index = {
        "diagnostic_scope": "LOCAL_VISIBLE_GEOMETRY_ONLY__NOT_ASSEMBLY_CLEARANCE_OR_RELEASE_AUTHORITY",
        "generated_utc": "EXECUTED_2026-08-28_LOCAL_NO_WALLCLOCK_CLAIM",
        "objects": snapshot_rows,
        "review_method": "CAD scripts/snapshot ISO workbench solid diagnostic PNG; visual findings are recorded separately after agent inspection",
        "schema": "ROUTE_C_LINK2_B12_CAD_SNAPSHOT_INDEX_V1",
        "snapshot_count": 12,
        "verdict": "TWELVE_PRIMARY_STEP_SNAPSHOTS_RENDERED__VISUAL_REVIEW_PENDING",
    }
    cache_document = {
        "cache_artifacts": cache_rows,
        "cache_count": len(cache_rows),
        "cache_destination": "07_reviews/cad_cache",
        "cache_is_diagnostic": True,
        "cache_is_primary_geometry_authority": False,
        "cache_is_part_of_deterministic_core": False,
        "cad_directory_after_relocation": {"other_file_count": 0, "step_file_count": 12, "total_file_count": 12},
        "generated_utc": "EXECUTED_2026-08-28_LOCAL_NO_WALLCLOCK_CLAIM",
        "schema": "ROUTE_C_LINK2_B12_CAD_CACHE_RELOCATION_RECEIPT_V1",
        "verdict": "TWELVE_CAD_DIAGNOSTIC_GLB_CACHES_RELOCATED__01_CAD_CONTAINS_EXACTLY_TWELVE_STEP_FILES",
    }
    atomic_json(REVIEWS / "CAD_INSPECT_REFS_SUMMARY_V1.json", inspect_document)
    atomic_json(REVIEWS / "CAD_SNAPSHOT_INDEX_V1.json", snapshot_index)
    atomic_json(REVIEWS / "CAD_CACHE_RELOCATION_RECEIPT_V1.json", cache_document)
    print(json.dumps({"inspected": len(inspect_rows), "snapshots": len(snapshot_rows), "caches_relocated": len(cache_rows), "verdict": "CAD_CLI_EVIDENCE_12_OF_12_PASS"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
