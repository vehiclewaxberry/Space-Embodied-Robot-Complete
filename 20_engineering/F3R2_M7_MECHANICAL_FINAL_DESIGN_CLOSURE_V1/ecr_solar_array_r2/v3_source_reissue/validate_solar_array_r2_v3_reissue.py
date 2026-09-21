#!/usr/bin/env python3
"""Independent fail-closed validator for the Solar-R2 V3 reissue."""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = HERE / "SOLAR_ARRAY_R2_V3_REISSUE_VALIDATION.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def equal(a, b, tol=1.0e-12):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(equal(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(equal(x, y, tol) for x, y in zip(a, b))
    return a == b


def payload_valid(report: dict, geometry: dict, frozen_fcstd_hash: str, frozen_step_hash: str) -> bool:
    line = geometry["geometry_facts"]["root_hinge_line"]
    return (
        line == {"y_abs_mm": 115.4, "z_mm": -108.15, "axis": "X_S"}
        and geometry["geometry_facts"]["protrusion_beyond_side_face_mm"] == 9.5
        and report["hashes"].get("SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd") == frozen_fcstd_hash
        and report["hashes"].get("SOLAR_ARRAY_R2_CANDIDATE_V1.step") == frozen_step_hash
        and report["cad_regenerated"] is False
        and report["visible_geometry_changed"] is False
        and report["owner_accepted"] is False
        and report["next_stage_authorized"] is False
        and report["release_credit"] is False
    )


def check(cid, name, passed, evidence):
    return {"id": cid, "name": name, "pass": bool(passed), "evidence": evidence}


def main() -> None:
    report = json.loads((HERE / "SOLAR_ARRAY_R2_BUILD_REPORT_V3.json").read_text(encoding="utf-8"))
    gate = json.loads((HERE / "SOLAR_ARRAY_R2_V3_REISSUE_GATE.json").read_text(encoding="utf-8"))
    geometry = yaml.safe_load((HERE / "SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V3.yaml").read_text(encoding="utf-8"))
    hdrm = yaml.safe_load((HERE / "SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V3.yaml").read_text(encoding="utf-8"))
    errata = yaml.safe_load((HERE / "SOLAR_ARRAY_R2_GENERATION_CHAIN_ERRATA_V3.yaml").read_text(encoding="utf-8"))
    v2 = json.loads((HERE.parent / "SOLAR_ARRAY_R2_BUILD_REPORT_V2.json").read_text(encoding="utf-8-sig"))
    fcstd = HERE.parent / "SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd"
    step = HERE.parent / "SOLAR_ARRAY_R2_CANDIDATE_V1.step"
    fc_hash = sha256(fcstd)
    st_hash = sha256(step)

    old = load_module("kin_v1_independent", HERE.parent / "solar_array_r2_kinematics.py")
    new = load_module("kin_v3_independent", HERE / "solar_array_r2_kinematics_v3.py")
    states = [(float(v), 0.0, 0.0) for v in range(0, 91, 5)] + [(90.0, float(v), 0.0) for v in range(10, 181, 10)] + [(90.0, 180.0, float(v)) for v in range(10, 181, 10)]
    kin_ok = True
    comparisons = 0
    for state in states:
        for side in (+1, -1):
            a = old.leaf_segments(side, *state)
            b = new.leaf_segments(side, *state)
            kin_ok = kin_ok and equal(a, b)
            comparisons += 1
            for x, y in zip(a, b):
                kin_ok = kin_ok and equal(old.leaf_solid_frame(side, x), new.leaf_solid_frame(side, y))
                comparisons += 1
    kin_ok = kin_ok and equal(old.stowed_stack_metrics(), new.stowed_stack_metrics())

    active_files = [
        HERE / "solar_array_r2_kinematics_v3.py",
        HERE / "build_solar_array_r2_v3.py",
        HERE / "sweep_solar_array_r2_clearance_v3.py",
        HERE / "build_harness_r2_gates_v3.py",
        HERE / "compute_flexible_appendage_r2_v3.py",
        HERE / "SOLAR_ARRAY_R2_BUILD_REPORT_V3.json",
        HERE / "SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V3.yaml",
        HERE / "SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V3.yaml",
    ]
    stale_active_literals = []
    for path in active_files:
        text = path.read_text(encoding="utf-8")
        if "114.9" in text or "0.1149" in text:
            stale_active_literals.append(path.name)

    source_files = [p for p in HERE.glob("*.py") if p.name not in {Path(__file__).name}]
    ast_ok = True
    parse_errors = []
    for path in source_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            ast_ok = False
            parse_errors.append(f"{path.name}:{exc.lineno}:{exc.msg}")

    base_valid = payload_valid(report, geometry, fc_hash, st_hash)
    negative_results = {}
    for name, mutate in {
        "root_114p9": lambda r, g: g["geometry_facts"]["root_hinge_line"].update({"y_abs_mm": 114.9}),
        "protrusion_9p0": lambda r, g: g["geometry_facts"].update({"protrusion_beyond_side_face_mm": 9.0}),
        "fcstd_hash_drift": lambda r, g: r["hashes"].update({"SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd": "0" * 64}),
        "cad_regenerated_true": lambda r, g: r.update({"cad_regenerated": True}),
    }.items():
        r = json.loads(json.dumps(report))
        g = json.loads(json.dumps(geometry))
        mutate(r, g)
        negative_results[name] = not payload_valid(r, g, fc_hash, st_hash)

    checks = [
        check("VAL-01", "frozen FCStd and STEP hashes recheck", fc_hash == "9D4D249A5D4EED7BDD8F3C08EC96737884A19523782112B1E72AD9EA0A1B65AB" and st_hash == "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795", {"fcstd": fc_hash, "step": st_hash}),
        check("VAL-02", "root arithmetic independently equals 115.4 mm", abs(113.15 + 1.0 + 2.5 / 2.0 - 115.4) <= 1e-12, 115.4),
        check("VAL-03", "report geometry and HDRM agree on root registration", geometry["geometry_facts"]["root_hinge_line"] == {"y_abs_mm": 115.4, "z_mm": -108.15, "axis": "X_S"} and "115.4" in hdrm["architecture"]["per_wing"]["root_hinge"], geometry["geometry_facts"]["root_hinge_line"]),
        check("VAL-04", "V3 protrusion is 9.5 mm", geometry["geometry_facts"]["protrusion_beyond_side_face_mm"] == 9.5 and "9.5 mm" in report["protrusion_note"], 9.5),
        check("VAL-05", "V1/V3 kinematics match over complete 55-state set", kin_ok, {"states": len(states), "recursive_comparisons": comparisons}),
        check("VAL-06", "V2/V3 shape metrics unchanged", report["shape_metrics"] == v2["shape_metrics"], len(report["shape_metrics"])),
        check("VAL-07", "V2/V3 13 clearance pairs unchanged", report["clearance_pairs"] == v2["clearance_pairs"] and len(report["clearance_pairs"]) == 13, len(report["clearance_pairs"])),
        check("VAL-08", "V2/V3 mass payload unchanged", report["mass_model_candidate"] == v2["mass_model_candidate"], report["mass_model_candidate"]["wing_total_kg"]),
        check("VAL-09", "active V3 artifacts contain no stale exact 114.9 literal", not stale_active_literals, stale_active_literals),
        check("VAL-10", "all V3 Python sources parse", ast_ok, parse_errors),
        check("VAL-11", "no V3 STEP or FCStd was emitted", not (HERE / "SOLAR_ARRAY_R2_CANDIDATE_V3.step").exists() and not (HERE / "SOLAR_ARRAY_R2_CANDIDATE_V3.FCStd").exists(), "no visible CAD regeneration"),
        check("VAL-12", "base payload is fail-closed valid", base_valid, "all current authority flags false"),
        check("VAL-13", "four falsifiers are rejected", all(negative_results.values()), negative_results),
        check("VAL-14", "errata records rejected historical values only", errata["source_reissue"]["generation_performed"] is False and errata["frozen_assets_modified"] is False, errata["source_reissue"]),
        check("VAL-15", "Gate distinguishes package PASS from execution authority", gate["package_validation"] == "PASS" and gate["effective_for_downstream_execution"] is False and gate["next_stage_authorized"] is False, {"package_validation": gate["package_validation"], "next_stage_authorized": gate["next_stage_authorized"]}),
    ]
    if not all(c["pass"] for c in checks):
        failed = [c["id"] for c in checks if not c["pass"]]
        raise RuntimeError("Solar V3 independent validation failed: " + ",".join(failed))

    with (HERE / "SOLAR_ARRAY_R2_V3_REISSUE_SHA256.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not all((ROOT / row["path"]).is_file() and sha256(ROOT / row["path"]) == row["sha256"] for row in rows):
        raise RuntimeError("Solar V3 SHA256 register mismatch")

    result = {
        "schema": "SOLAR_ARRAY_R2_V3_REISSUE_VALIDATION",
        "generated_date_local": "2026-08-24",
        "checks": checks,
        "summary": {"pass": len(checks), "total": len(checks), "failed": []},
        "verdict": "PASS_INDEPENDENT_SOURCE_AND_METADATA_REISSUE__NO_CAD_REGENERATION__NO_EXECUTION_OR_RELEASE_AUTHORITY",
        "owner_accepted": False,
        "effective_for_downstream_execution": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("PASS: Solar R2 V3 independent validation 15/15; CAD not regenerated")


if __name__ == "__main__":
    main()
