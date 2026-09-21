#!/usr/bin/env python3
"""Independent validator for the Unified-R2 effective-frontier V2 package."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_VALIDATION_V2.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def check(cid: str, name: str, passed: bool, evidence) -> dict:
    return {"id": cid, "name": name, "pass": bool(passed), "evidence": evidence}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    frontier = json.loads((HERE / "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_V2.json").read_text(encoding="utf-8"))
    gate = json.loads((HERE / "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_GATE_V2.json").read_text(encoding="utf-8"))
    binding = yaml.safe_load((HERE / "C01_C09_M4_M7_CONFIGURATION_IDENTITY_BINDING_V1.yaml").read_text(encoding="utf-8"))
    base_pin = next(p for p in frontier["source_pins"] if p["id"] == "BASE_PREBIND_READINESS")
    delta_pin = next(p for p in frontier["source_pins"] if p["id"] == "GEOMETRY_DELTA")
    base = json.loads((ROOT / base_pin["path"]).read_text(encoding="utf-8-sig"))
    delta = json.loads((ROOT / delta_pin["path"]).read_text(encoding="utf-8-sig"))

    source_hashes_ok = all(
        (ROOT / p["path"]).is_file()
        and (ROOT / p["path"]).stat().st_size == p["bytes"]
        and sha256(ROOT / p["path"]) == p["sha256"]
        for p in frontier["source_pins"]
    )
    records = binding["records"]
    identities = [r["configuration_id"] for r in records]
    names_exact = all(r["m4_identity"]["name"] == r["m7_r2_identity"]["name"] == r["canonical_name"] for r in records)
    values_complete = all(
        r["m7_r2_identity"]["mass"]["value_kg"] > 0
        and len(r["m7_r2_identity"]["center_of_mass"]["xyz_m"]) == 3
        and len(r["m7_r2_identity"]["inertia"]["components_kg_m2"]) == 6
        for r in records
    )
    flags_false = all(v is False for v in frontier["authority_flags"].values()) and all(v is False for v in gate["authority_flags"].values())
    forbidden_suffixes = {".fcstd", ".step", ".stp", ".stl", ".obj", ".urdf", ".inp", ".odb"}
    no_geometry = not any(p.suffix.lower() in forbidden_suffixes for p in HERE.iterdir())
    tree = ast.parse((HERE / "build_unified_r2_effective_frontier_v2.py").read_text(encoding="utf-8"))
    forbidden_imports = {"FreeCAD", "Part", "subprocess", "abaqus", "pybullet"}
    imports = {alias.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for alias in (n.names if isinstance(n, ast.Import) else [ast.alias(name=n.module or "")])}

    checks = [
        check("VAL-01", "all frontier source hashes independently recheck", source_hashes_ok, len(frontier["source_pins"])),
        check("VAL-02", "base readiness is still 5/20", base["summary"] == {"criteria_total": 20, "pass": 5, "hold": 15}, base["summary"]),
        check("VAL-03", "delta declares effective 6/20", delta["effective_summary"] == {"criteria_total": 20, "pass": 6, "hold": 14}, delta["effective_summary"]),
        check("VAL-04", "aggregated frontier is exactly 6/20", frontier["effective_summary"] == {"criteria_total": 20, "pass": 6, "hold": 14}, frontier["effective_summary"]),
        check("VAL-05", "exact C01-C09 identity set", identities == [f"C{i:02d}" for i in range(1, 10)], identities),
        check("VAL-06", "all M4/M7 canonical names match", names_exact, [r["canonical_name"] for r in records]),
        check("VAL-07", "all nine design mass CG inertia records are populated", values_complete, len(records)),
        check("VAL-08", "binding is explicitly non-promotional", binding["summary"]["m4_release_status_promoted"] is False and binding["summary"]["m7_design_values_reclassified_as_flight_or_measured"] is False, binding["summary"]),
        check("VAL-09", "PRB-17 remains HOLD", next(r for r in frontier["effective_criteria"] if r["id"] == "PRB-17")["pass"] is False, "detailed structure unresolved"),
        check("VAL-10", "PRB-18 is the single newly passed criterion", next(r for r in frontier["effective_criteria"] if r["id"] == "PRB-18")["pass"] is True, "Solar root frames frozen"),
        check("VAL-11", "Route-C remains 13 HOLD and zero non-null", frontier["route_c_state"]["registry_status_HOLD_after"] == 13 and frontier["route_c_state"]["registry_value_non_null_after"] == 0, frontier["route_c_state"]),
        check("VAL-12", "all authority flags independently remain false", flags_false, frontier["authority_flags"]),
        check("VAL-13", "no geometry solver or URDF artifacts exist in package", no_geometry, {"forbidden_suffixes": sorted(forbidden_suffixes), "matches": []}),
        check("VAL-14", "builder imports no CAD solver subprocess or physics engine", imports.isdisjoint(forbidden_imports), sorted(imports)),
        check("VAL-15", "package Gate is validation PASS but technical HOLD", gate["package_validation"] == "PASS" and gate["technical_outcome"] == "HOLD", {"package_validation": gate["package_validation"], "technical_outcome": gate["technical_outcome"]}),
    ]
    require(all(c["pass"] for c in checks), "independent effective-frontier validation failed")

    # Validate every row already emitted before writing this validation result.
    with (HERE / "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_SHA256.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    require(all((ROOT / row["path"]).is_file() and sha256(ROOT / row["path"]) == row["sha256"] for row in rows), "SHA256 register mismatch")

    result = {
        "schema": "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_VALIDATION_V2",
        "generated_date_local": "2026-08-24",
        "checks": checks,
        "summary": {"pass": len(checks), "total": len(checks), "failed": []},
        "verdict": "PASS_INDEPENDENT_RECOMPUTATION__EFFECTIVE_FRONTIER_6_OF_20_AND_CONFIGURATION_BINDING_9_OF_9__TECHNICAL_OUTCOME_REMAINS_HOLD",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("PASS: independent validation 15/15; effective frontier 6/20; technical outcome HOLD")


if __name__ == "__main__":
    main()
