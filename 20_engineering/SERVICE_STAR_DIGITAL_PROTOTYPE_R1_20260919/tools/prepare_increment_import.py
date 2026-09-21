"""Verify and measure incremental STEP inputs without SolidWorks or CAD mutation.

Run with G:/Windows_program_file/Anaconda/python.exe. Only the designated
INCREMENT_IMPORT_PLAN.json is written; STEP files and mapping inputs are read-only.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import sys
import traceback

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parents[1]
DEST = OUT / "inputs" / "INCREMENT_IMPORT_PLAN.json"
MAPS = {
    "WP10": OUT / "inputs" / "WP10_INCREMENT_MAP.json",
    "R17": OUT / "inputs" / "R17_FORWARD_MAP.json",
}

# Exact source-byte observation from an isolated reread on 2026-09-19.
# This is a source diagnostic, never an exemption from geometry/hash checks.
SOURCE_PARSER_OBSERVATIONS = {
    "d0f02a7cdd7b32cf7557144fcecca1addf04d2be794e36fa48131b4f4965c442": {
        "diagnostic": "ERR StepReaderData : Unresolved Reference : Fails Count : 1",
        "source": "LPS300_OEM.step",
        "verified_by": "isolated OCP STEPControl_Reader reread of this exact hash",
        "reader_result": "IFSelect_RetDone",
        "syntactic_model_check_list_empty": True,
        "disposition": "Transferred BRep measured; source semantic completeness is not certified. Native importer must independently verify 5 solids plus volume/bounds, and preserve this diagnostic.",
    }
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalized(path):
    return str(Path(path).resolve()).replace("\\", "/").casefold()


def extract(map_name, row, state):
    material = row.get("material", {}) if map_name == "WP10" else {}
    density = material.get("density_kg_m3") if map_name == "WP10" else row.get("density_kg_m3")
    supported = bool(material.get("single_bulk_material_supported")) if map_name == "WP10" else density is not None
    if density is not None:
        if not isinstance(density, (int, float)) or isinstance(density, bool) or not math.isfinite(density) or density <= 0:
            raise ValueError(f"Invalid density: {map_name}/{state}/{row['id']}")
    # Unknown/composite entries never gain a density from another same-shape use.
    accepted_density = float(density) if supported and density is not None else None
    return {
        "map": map_name, "state": state, "instance_id": row["id"],
        "operation": row.get("operation"), "step_path": row["step_path"],
        "source_sha256": row["source_sha256"].lower(),
        "representation_role": row.get("representation_role") or row.get("source_record", {}).get("representation_role") or "UNKNOWN",
        "material_id": material.get("material_id"),
        "material_density_kg_m3": accepted_density,
        "material_status": material.get("status", "UNKNOWN") if map_name == "WP10" else (
            "R17_EXISTING_DESIGN_CANDIDATE_DENSITY_NOT_AS_BUILT" if accepted_density is not None else "R17_MATERIAL_UNKNOWN_UNASSIGNED"),
        "material_evidence": material.get("evidence", []),
    }


def material_summary(refs):
    # Different named known materials, different density, or known-vs-unknown
    # same-byte uses all require unassigned native material after hash dedup.
    density_values = {r["material_density_kg_m3"] for r in refs}
    named_known = {r["material_id"] for r in refs if r["material_id"] is not None}
    conflict = len(density_values) > 1 or len(named_known) > 1
    density = next(iter(density_values)) if len(density_values) == 1 else None
    if conflict:
        return None, "SAME_HASH_MATERIAL_CONFLICT_UNASSIGNED", True
    if density is None:
        statuses = sorted({r["material_status"] for r in refs})
        return None, statuses[0] if len(statuses) == 1 else "UNASSIGNED_MULTIPLE_SOURCE_STATUSES", False
    origins = {r["map"] for r in refs}
    if origins == {"R17"}:
        return density, "R17_EXISTING_DESIGN_CANDIDATE_DENSITY_NOT_AS_BUILT", False
    return density, "SOURCE_MAPPED_MATERIAL_CANDIDATE_NOT_AS_BUILT", False


def measure_step(path):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    reader = STEPControl_Reader()
    code = reader.ReadFile(str(path))
    if code != IFSelect_RetDone:
        raise ValueError(f"STEP read failed: {code}")
    reader.SetSystemLengthUnit(1.0)  # OCCT internal length unit: millimetres.
    if reader.TransferRoots() <= 0:
        raise ValueError("STEP transfer returned no roots")
    shape = reader.OneShape()
    if shape.IsNull():
        raise ValueError("Null shape")
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    valid = bool(BRepCheck_Analyzer(shape, True).IsValid())
    box = Bnd_Box()
    box.SetGap(0.0)
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    if box.IsVoid() or box.IsOpen():
        raise ValueError("Void/unbounded bbox")
    bounds = list(box.Get())
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, True, False, False)
    volume = float(props.Mass())
    if count < 1 or not all(math.isfinite(v) for v in bounds + [volume]) or volume <= 0:
        raise ValueError(f"Not positive finite solids: solids={count}, volume={volume}")
    return {
        "expected_solids": count,
        "expected_local_bbox_mm": [bounds[:3], bounds[3:]],
        "expected_volume_mm3": volume,
        "shape_valid": valid,
        "step_target_system_length_unit_mm": reader.SystemLengthUnit(),
    }


def build():
    plan = {
        "schema": "INCREMENT_IMPORT_PLAN_V1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "BUILDING",
        "scope": "READ_ONLY_STEP_SOURCE_HASH_AND_OCP_GEOMETRY_MEASUREMENT",
        "units": {"length": "mm", "volume": "mm3", "density": "kg/m3"},
        "parts": [], "path_by_source": {}, "path_by_source_normalized": {}, "path_by_hash": {},
        "part_id_by_hash": {}, "source_checks": [], "errors": [], "excluded_identity_conflicts": [],
        "native_files_created": False, "geometry_created": False,
        "whole_design_complete": False, "fit_or_interference_pass_claimed": False,
        "source_STEP_semantic_completeness_verified": False,
        "source_parser_observations": SOURCE_PARSER_OBSERVATIONS,
        "material_policy": "WP10 mapped evidence only; R17 density is existing design candidate; same-hash material conflict stays unassigned.",
        "bbox_policy": "OCP AddOptimal(useTriangulation=False,useShapeTolerance=False) on source STEP in its local file frame; assembly T_S_step remains in upstream map.",
    }
    inputs = {}
    documents = {}
    source_expected = defaultdict(set)
    references = []
    for name, path in MAPS.items():
        inputs[name] = {"path": str(path), "sha256": sha(path)}
        documents[name] = json.loads(path.read_text(encoding="utf-8-sig"))
        for state, data in documents[name]["states"].items():
            for row in data["rows"]:
                if name == "R17" and row.get("operation") == "IDENTITY_CONFLICT":
                    plan["excluded_identity_conflicts"].append({"state": state, "id": row["id"]})
                    continue
                if not row.get("step_path") or not row.get("source_sha256"):
                    raise ValueError(f"Missing STEP/hash: {name}/{state}/{row.get('id')}")
                ref = extract(name, row, state)
                references.append(ref)
                source_expected[ref["step_path"]].add(ref["source_sha256"])
        if name == "WP10":
            # Include all 64 declared STEP files even when a mapper excludes one
            # from the final assembly; this is an import resource plan, not fit approval.
            for entry in documents[name]["source_file_checks"]:
                source_expected[entry["path"]].add(entry["recorded_sha256"].lower())
    plan["input_maps"] = inputs
    by_hash = defaultdict(list)
    for path, expected in sorted(source_expected.items()):
        actual = sha(path)
        match = len(expected) == 1 and actual in expected
        plan["source_checks"].append({
            "step_path": path, "expected_sha256": sorted(expected),
            "actual_sha256": actual, "matches": match,
        })
        if not match:
            plan["errors"].append({"path": path, "error": "SOURCE_HASH_MISMATCH"})
        by_hash[actual].append(path)
    if plan["errors"]:
        plan["status"] = "FAIL_SOURCE_HASH"
        return plan
    evidence_expected = defaultdict(set)
    for ref in references:
        for evidence in ref["material_evidence"]:
            if evidence.get("path") and evidence.get("sha256"):
                evidence_expected[evidence["path"]].add(evidence["sha256"].lower())
    plan["material_evidence_checks"] = []
    for path, expected in sorted(evidence_expected.items()):
        actual = sha(path)
        match = len(expected) == 1 and actual in expected
        plan["material_evidence_checks"].append({"path": path, "expected_sha256": sorted(expected), "actual_sha256": actual, "matches": match})
        if not match:
            plan["errors"].append({"path": path, "error": "MATERIAL_EVIDENCE_HASH_MISMATCH"})
    refs_by_hash = defaultdict(list)
    for ref in references:
        refs_by_hash[ref["source_sha256"]].append(ref)
    native_names = {}
    for i, (digest, paths) in enumerate(sorted(by_hash.items()), 1):
        name = "I_" + digest[:16]
        if name in native_names and native_names[name] != digest:
            raise ValueError("Truncated hash collision in native filename")
        native_names[name] = digest
        refs = refs_by_hash.get(digest, [])
        roles = sorted({r["representation_role"] for r in refs})
        density, material_status, material_conflict = material_summary(refs) if refs else (None, "SOURCE_FILE_ONLY_MATERIAL_UNASSIGNED", False)
        native = str(OUT / "native" / (name + ".SLDPRT"))
        part = {
            "id": name, "step_path": paths[0], "source_sha256": digest,
            "native_path": native, "source_paths": sorted(paths),
            "representation_role": roles[0] if len(roles) == 1 else "MULTIPLE_INSTANCE_REPRESENTATION_ROLES",
            "representation_roles": roles,
            "material_density_kg_m3": density, "material_status": material_status,
            "same_hash_material_conflict": material_conflict,
            "material_ids_from_sources": sorted({r["material_id"] for r in refs if r["material_id"] is not None}),
            "instance_refs": refs,
            "source_parser_diagnostic": SOURCE_PARSER_OBSERVATIONS.get(digest),
        }
        try:
            part.update(measure_step(paths[0]))
            if not part["shape_valid"]:
                plan["errors"].append({"part_id": name, "error": "INVALID_OCP_SHAPE"})
        except Exception as e:
            part.update(expected_solids=None, expected_local_bbox_mm=None, expected_volume_mm3=None, shape_valid=False, geometry_error=str(e))
            plan["errors"].append({"part_id": name, "error": str(e)})
        plan["parts"].append(part)
        plan["path_by_hash"][digest] = native
        plan["part_id_by_hash"][digest] = name
        for path in paths:
            plan["path_by_source"][path] = native
            plan["path_by_source_normalized"][normalized(path)] = native
        if i % 25 == 0 or i == len(by_hash):
            print(f"Measured {i}/{len(by_hash)} unique STEP hashes", flush=True)
    # Detect a source edit while the independent readback was running.
    for entry in plan["source_checks"]:
        entry["sha256_after_measurement"] = sha(entry["step_path"])
        entry["unchanged_during_measurement"] = entry["sha256_after_measurement"] == entry["actual_sha256"]
        if not entry["unchanged_during_measurement"]:
            plan["errors"].append({"path": entry["step_path"], "error": "SOURCE_CHANGED_DURING_MEASUREMENT"})
    for name, entry in inputs.items():
        entry["sha256_after_measurement"] = sha(entry["path"])
        if entry["sha256_after_measurement"] != entry["sha256"]:
            plan["errors"].append({"map": name, "error": "INPUT_MAP_CHANGED_DURING_MEASUREMENT"})
    plan["summary"] = {
        "source_paths": len(source_expected), "unique_step_hashes": len(plan["parts"]),
        "wp10_declared_source_files": len(documents["WP10"]["source_file_checks"]),
        "state_row_references": len(references),
        "excluded_identity_conflict_state_rows": len(plan["excluded_identity_conflicts"]),
        "valid_parts": sum(p["shape_valid"] for p in plan["parts"]),
        "candidate_density_parts": sum(p["material_density_kg_m3"] is not None for p in plan["parts"]),
        "unassigned_material_parts": sum(p["material_density_kg_m3"] is None for p in plan["parts"]),
        "material_conflict_parts": sum(p["same_hash_material_conflict"] for p in plan["parts"]),
        "solid_count_sum": sum(p["expected_solids"] or 0 for p in plan["parts"]),
        "errors": len(plan["errors"]),
    }
    plan["all_source_hashes_match"] = all(x["matches"] and x.get("unchanged_during_measurement", False) for x in plan["source_checks"])
    plan["all_source_geometries_valid"] = all(p["shape_valid"] for p in plan["parts"])
    plan["status"] = "PASS" if not plan["errors"] and plan["all_source_hashes_match"] and plan["all_source_geometries_valid"] else "FAIL"
    return plan


def main():
    try:
        plan = build()
    except Exception as exc:
        plan = {"schema": "INCREMENT_IMPORT_PLAN_V1", "status": "FAIL_EXCEPTION", "error": str(exc), "traceback": traceback.format_exc(), "parts": [], "native_files_created": False}
    DEST.write_text(json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": plan["status"], "summary": plan.get("summary"), "error": plan.get("error"), "output": str(DEST)}, ensure_ascii=False), flush=True)
    return 0 if plan["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
