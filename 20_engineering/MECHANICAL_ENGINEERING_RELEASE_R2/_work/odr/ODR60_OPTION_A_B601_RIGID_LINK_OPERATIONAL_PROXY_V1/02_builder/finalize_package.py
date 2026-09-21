"""Fail-closed finalizer for the six-link local collision-geometry package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Iterable


PACKAGE = Path(__file__).resolve().parents[1]
RESULTS = PACKAGE / "05_results"
ASSETS = PACKAGE / "03_assets"
CONTRACT = PACKAGE / "00_contract" / "B601_RIGID_LINK_OPERATIONAL_COLLISION_CONTRACT_V1.json"
SOURCE_LOCK = PACKAGE / "01_sources" / "SOURCE_AUTHORITY_LOCK_V1.json"
INDEPENDENT = RESULTS / "INDEPENDENT_VALIDATION_V1.json"
NEGATIVES = RESULTS / "NEGATIVE_CONTROLS_V1.json"
MANIFEST = RESULTS / "PACKAGE_MANIFEST_V1.csv"
GATE = RESULTS / "B601_RIGID_LINK_OPERATIONAL_PROXY_LOCAL_GATE_V1.json"
LINK_IDS = tuple(f"link{i}" for i in range(1, 7))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def workspace_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root containing PROJECT_MAP.md was not found")


def strict_json(path: Path) -> dict[str, Any]:
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {key!r}: {path}")
            result[key] = value
        return result

    require(path.is_file(), f"required JSON missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(workspace_root()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def verify_record(value: dict[str, Any]) -> None:
    path = workspace_root() / value["path"]
    require(path.is_file(), f"recorded artifact missing: {value['path']}")
    require(path.stat().st_size == value["bytes"], f"byte drift: {value['path']}")
    require(sha256_path(path) == value["sha256"], f"hash drift: {value['path']}")


def all_boolean_checks_true(report: dict[str, Any]) -> bool:
    checks = report.get("checks")
    return isinstance(checks, dict) and bool(checks) and all(value is True for value in checks.values())


def independent_checks_true(report: dict[str, Any]) -> bool:
    global_checks = report.get("global_checks")
    per_link = report.get("per_link")
    if report.get("formal_gate_pass") is not True or report.get("validation_pass") is not True:
        return False
    if not isinstance(global_checks, dict) or not global_checks or not all(
        value is True for value in global_checks.values()
    ):
        return False
    if not isinstance(per_link, dict) or set(per_link) != set(LINK_IDS):
        return False
    return all(
        row.get("validation_pass") is True
        and isinstance(row.get("checks"), dict)
        and bool(row["checks"])
        and all(value is True for value in row["checks"].values())
        for row in per_link.values()
    )


def manifest_bytes() -> bytes:
    excluded = {MANIFEST.resolve(), GATE.resolve()}
    paths = [
        path
        for path in PACKAGE.rglob("*")
        if path.is_file()
        and path.resolve() not in excluded
        and "__pycache__" not in path.parts
        and not path.name.endswith((".tmp", ".pyc"))
    ]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(("path", "bytes", "sha256", "role"))
    for path in sorted(paths, key=lambda value: value.relative_to(PACKAGE).as_posix()):
        relative = path.relative_to(PACKAGE).as_posix()
        if relative.startswith("00_contract/"):
            role = "CONTRACT"
        elif relative.startswith("01_sources/"):
            role = "SOURCE_LOCK"
        elif relative.endswith(".step"):
            role = "PRIMARY_STEP"
        elif relative.endswith("_RUNTIME.npz"):
            role = "RUNTIME_COLLISION_NPZ_M"
        elif relative.endswith("_RUNTIME_M.stl"):
            role = "RUNTIME_COLLISION_STL_M"
        elif relative.startswith("07_reviews/"):
            role = "CAD_SNAPSHOT_REVIEW"
        elif relative.startswith("05_results/"):
            role = "MACHINE_EVIDENCE"
        elif relative.startswith("04_validation/") or relative.startswith("06_tests/"):
            role = "VALIDATION_SOURCE"
        elif relative.endswith(("_PREVIEW.glb", "_PREVIEW.stl", ".step.glb")):
            role = "VISUALIZATION_ONLY"
        else:
            role = "GENERATOR_OR_DOCUMENTATION"
        writer.writerow((relative, path.stat().st_size, sha256_path(path), role))
    return buffer.getvalue().encode("utf-8")


def build_gate(manifest_data: bytes) -> dict[str, Any]:
    contract = strict_json(CONTRACT)
    lock = strict_json(SOURCE_LOCK)
    independent = strict_json(INDEPENDENT)
    negatives = strict_json(NEGATIVES)
    receipts = []
    for link_id in LINK_IDS:
        path = RESULTS / f"B601_{link_id.upper()}_LOCAL_GEOMETRY_RECEIPT_V1.json"
        receipt = strict_json(path)
        require(receipt["object_id"] == f"A::{link_id}", f"receipt object mismatch: {link_id}")
        require(all_boolean_checks_true(receipt), f"receipt checks failed: {link_id}")
        for field in ("source", "primary_step", "runtime_npz", "runtime_stl"):
            verify_record(receipt[field])
        flags = receipt["authority_flags"]
        for name in (
            "system_registry_reissued",
            "system_pair_evaluation_authorized",
            "path_search_authorized",
            "parent_mechanical_gate_reissued",
            "next_stage_authorized",
            "release_credit",
        ):
            require(flags[name] is False, f"forbidden receipt authority: {link_id}/{name}")
        receipts.append(receipt)

    require(independent_checks_true(independent), "independent validation checks failed")
    require("PASS" in str(independent.get("verdict", "")), "independent validation did not PASS")
    require(negatives.get("all_negative_controls_detected") is True, "negative controls failed")
    require(negatives.get("cases_detected") == negatives.get("case_count"), "negative controls incomplete")
    for report in (independent, negatives):
        for name in contract["authority_flags"]:
            values = report.get("authority_flags", {})
            if name in values:
                require(values[name] is False, f"forbidden report authority: {name}")

    root = workspace_root()
    immutable = lock["immutable_sources"]
    parent_path = root / immutable["current_mechanical_parent_gate"]["path"]
    registry_path = root / immutable["m01_system_collision_registry"]["path"]
    prebind_path = root / immutable["m01_scene_prebind_gate"]["path"]
    parent = strict_json(parent_path)
    registry = strict_json(registry_path)
    prebind = strict_json(prebind_path)
    require(parent["gate_a_pass"] is False, "parent mechanical Gate unexpectedly passed")
    require(parent["next_stage_authorized"] is False, "parent mechanical Gate unexpectedly authorized")
    require(prebind["asset_accounting"]["operational_authority_rows"] == 1, "M01 operational count drift")
    require(prebind["system_execution_state"]["system_pair_queries_executed"] == 0, "pair query count drift")
    require(prebind["system_execution_state"]["system_edges_certified"] == 0, "edge count drift")
    require(prebind["system_execution_state"]["path_search_executed"] is False, "path search state drift")

    object_ids = [f"A::{link_id}" for link_id in LINK_IDS]
    criteria = [
        {"id": "LG1", "name": "SOURCE_AND_ACCEPTED_URDF_LOCK", "pass": True},
        {"id": "LG2", "name": "SIX_STEP_12_SOLID_BREP_REOPEN", "pass": True},
        {"id": "LG3", "name": "STEP_TO_METER_RUNTIME_GEOMETRY_AGREEMENT", "pass": True},
        {"id": "LG4", "name": "CONVEX_HULL_AND_SOURCE_SURFACE_CONTAINMENT", "pass": True},
        {"id": "LG5", "name": "INDEPENDENT_VALIDATION", "pass": True},
        {"id": "LG6", "name": "NEGATIVE_CONTROLS_AND_DETERMINISTIC_REPLAY", "pass": True},
    ]
    return {
        "schema": "B601_RIGID_LINK_OPERATIONAL_PROXY_LOCAL_GATE_V1",
        "as_of_date": "2026-08-28",
        "scope": "LOCAL_ASSET_LEVEL_COLLISION_GEOMETRY_CANDIDATES_ONLY",
        "classification": "PENDING_OWNER_REVIEW",
        "candidate_objects": [
            {
                "object_id": object_id,
                "local_geometry_candidate_pass": True,
                "system_registry_bound": False,
            }
            for object_id in object_ids
        ],
        "local_candidate_asset_count": 6,
        "system_state_preserved": {
            "known_active_object_count": registry["object_summary"]["known_active_object_count"],
            "system_registry_operational_authority_rows": 1,
            "system_registry_candidate_assets_added": 0,
            "system_required_pair_queries": 11166,
            "system_pair_queries_executed": 0,
            "system_edges_certified": 0,
            "stage_instances_bound": 0,
            "path_search_executed": False,
            "TMG4": "HOLD",
            "G12": "FAIL",
        },
        "criteria": criteria,
        "criteria_passed": 6,
        "criteria_total": 6,
        "receipt_files": [record(RESULTS / f"B601_{link.upper()}_LOCAL_GEOMETRY_RECEIPT_V1.json") for link in LINK_IDS],
        "independent_validation": record(INDEPENDENT),
        "negative_controls": record(NEGATIVES),
        "package_manifest": {
            "path": MANIFEST.relative_to(root).as_posix(),
            "bytes": len(manifest_data),
            "sha256": hashlib.sha256(manifest_data).hexdigest().upper(),
            "excludes": [MANIFEST.name, GATE.name],
        },
        "parent_state_evidence": {
            "mechanical_release_gate": record(parent_path),
            "m01_system_registry_gate": record(registry_path),
            "m01_scene_prebind_gate": record(prebind_path),
        },
        "authority_flags": {
            "candidate_geometry_may_be_submitted_for_owner_binding": True,
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "parent_mechanical_gate_reissued": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "verdict": "6_OF_6_LOCAL_GEOMETRY_CRITERIA_PASS__PENDING_OWNER_REVIEW__TMG4_HOLD__G12_FAIL__NO_SYSTEM_PAIR_OR_PATH_AUTHORITY__NO_RELEASE_CREDIT",
    }


def gate_bytes(manifest_data: bytes) -> bytes:
    return (json.dumps(build_gate(manifest_data), indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_data = manifest_bytes()
    output = gate_bytes(manifest_data)
    if args.verify_existing:
        require(MANIFEST.is_file() and MANIFEST.read_bytes() == manifest_data, "manifest replay mismatch")
        require(GATE.is_file() and GATE.read_bytes() == output, "local Gate replay mismatch")
    else:
        atomic_write(MANIFEST, manifest_data)
        atomic_write(GATE, output)
    print(json.dumps({"criteria": "6/6", "status": "PENDING_OWNER_REVIEW", "system_authority": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
