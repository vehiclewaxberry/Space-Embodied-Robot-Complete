r"""FC02_IMPORT_AND_INDEX.py - import the full-system neutral STEP and index it.

script_id            : FC02_IMPORT_AND_INDEX
schema_version       : 1.0
allowed_output_root  : 20_engineering/F3R2_V5R_FREECAD_OPERATIONAL_CLOSURE_20260820
authoritative_sources: F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.step
                       (125,946,155 bytes, sha256 A7549D0E...)
prohibited_sources   : does NOT read SLDASM/SLDPRT; does NOT write any project asset

This is the decisive feasibility test for the FreeCAD operational line: can the
125.9 MB full-system STEP be imported, saved as FCStd, and reopened intact on
this machine, at ~93% commit utilisation.

Guards, because commit exhaustion (not free RAM) killed the last SolidWorks run:
  - samples commit charge before, during and after
  - aborts BEFORE import if commit headroom is under MIN_HEADROOM_GIB
  - writes a partial receipt on failure rather than dying silently

Idempotent. Import only - builds no assembly, moves nothing, mutates no donor.

Run:  freecadcmd.exe <this file>   (via the FC_RUN wrapper, which sets __main__)
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common as fc  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402

SCRIPT_ID = "FC02_IMPORT_AND_INDEX"
STEP_PATH = os.path.join(
    fc.PROJECT_ROOT, "20_engineering", "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807",
    "03_native_cad", "F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.step",
)
EXPECTED_BYTES = 125946155
MIN_HEADROOM_GIB = 3.0
FCSTD_OUT = "03_fcstd/FC02_FULL_SYSTEM_IMPORT.FCStd"


def main() -> int:
    report = fc.receipt_header(SCRIPT_ID)
    report["step_input"] = fc.file_fact(STEP_PATH)
    report["expected_bytes"] = EXPECTED_BYTES
    report["bytes_match"] = report["step_input"].get("bytes") == EXPECTED_BYTES

    pre = fc.resource_snapshot()
    report["resource_pre_import"] = pre
    print(f"commit before import: {pre['commit_utilisation_pct']}% "
          f"headroom {pre['commit_headroom_gib']} GiB")

    if pre["commit_headroom_gib"] < MIN_HEADROOM_GIB:
        report["verdict"] = "FC02_ABORTED_INSUFFICIENT_COMMIT_HEADROOM"
        report["min_headroom_gib"] = MIN_HEADROOM_GIB
        report["import_attempted"] = False
        report["remediation"] = (
            "close idle CAE MCP servers / browser tabs to free commit charge, then re-run. "
            "This is a resource precondition, NOT a geometry or toolchain failure."
        )
        fc.write_json("06_validation/FC02_IMPORT_INVENTORY.json", report)
        print(f"ABORT: commit headroom {pre['commit_headroom_gib']} GiB "
              f"< required {MIN_HEADROOM_GIB} GiB")
        return 2

    if not report["bytes_match"]:
        report["verdict"] = "FC02_INPUT_HASH_OR_SIZE_MISMATCH"
        fc.write_json("06_validation/FC02_IMPORT_INVENTORY.json", report)
        return 3

    for existing in list(FreeCAD.listDocuments()):
        FreeCAD.closeDocument(existing)

    doc = FreeCAD.newDocument("FC02_FULL_SYSTEM")
    t0 = time.time()
    try:
        Part.insert(STEP_PATH, doc.Name)      # console-safe; NOT Import.insert
        doc.recompute()
    except BaseException as exc:  # noqa: BLE001 - MemoryError included deliberately
        report["verdict"] = "FC02_IMPORT_FAILED"
        report["exception"] = f"{type(exc).__name__}: {exc}"
        report["elapsed_s"] = round(time.time() - t0, 1)
        report["resource_at_failure"] = fc.resource_snapshot()
        report["fallback_required"] = "subsystem split per owner ruling section 9.4"
        fc.write_json("06_validation/FC02_IMPORT_INVENTORY.json", report)
        print(f"IMPORT FAILED: {type(exc).__name__}: {exc}")
        return 4
    elapsed = round(time.time() - t0, 1)
    report["import_elapsed_s"] = elapsed
    report["resource_post_import"] = fc.resource_snapshot()
    print(f"import completed in {elapsed}s")

    # ---- inventory ----
    shaped = [o for o in doc.Objects if hasattr(o, "Shape")]
    totals = {
        "document_object_count": len(doc.Objects),
        "shape_object_count": len(shaped),
        "solid_count": 0, "shell_count": 0, "face_count": 0,
        "edge_count": 0, "vertex_count": 0, "compound_count": 0,
        "invalid_shape_count": 0, "null_shape_count": 0,
        "total_volume_mm3": 0.0,
    }
    rows = []
    bb_all = None
    for obj in shaped:
        shape = obj.Shape
        if shape.isNull():
            totals["null_shape_count"] += 1
            rows.append({"name": obj.Name, "label": obj.Label, "null": True})
            continue
        valid = bool(shape.isValid())
        if not valid:
            totals["invalid_shape_count"] += 1
        totals["solid_count"] += len(shape.Solids)
        totals["shell_count"] += len(shape.Shells)
        totals["face_count"] += len(shape.Faces)
        totals["edge_count"] += len(shape.Edges)
        totals["vertex_count"] += len(shape.Vertexes)
        if shape.ShapeType == "Compound":
            totals["compound_count"] += 1
        totals["total_volume_mm3"] += float(shape.Volume)
        bb = shape.BoundBox
        bb_all = bb if bb_all is None else (bb_all.united(bb) if hasattr(bb_all, "united") else bb_all)
        com = None
        try:
            c = shape.CenterOfMass
            com = [round(c.x, 4), round(c.y, 4), round(c.z, 4)]
        except Exception:  # noqa: BLE001
            pass
        rows.append({
            "name": obj.Name, "label": obj.Label, "shape_type": shape.ShapeType,
            "is_valid": valid, "solids": len(shape.Solids), "faces": len(shape.Faces),
            "volume_mm3": round(float(shape.Volume), 4),
            "center_of_mass_mm": com,
            "bbox_mm": [round(bb.XMin, 3), round(bb.YMin, 3), round(bb.ZMin, 3),
                        round(bb.XMax, 3), round(bb.YMax, 3), round(bb.ZMax, 3)],
            "identity": "UNRESOLVED_COMPONENT_IDENTITY",
        })
    totals["total_volume_mm3"] = round(totals["total_volume_mm3"], 4)
    if bb_all is not None:
        totals["overall_bbox_mm"] = {
            "xlen": round(bb_all.XLength, 3), "ylen": round(bb_all.YLength, 3),
            "zlen": round(bb_all.ZLength, 3),
        }
    report["inventory_totals"] = totals
    print(f"objects={totals['document_object_count']} solids={totals['solid_count']} "
          f"invalid={totals['invalid_shape_count']}")

    # ---- save / reopen ----
    fcstd = fc.out(*FCSTD_OUT.split("/"))
    if os.path.isfile(fcstd):
        os.remove(fcstd)
    doc.saveAs(fcstd)
    saved = os.path.getsize(fcstd)
    FreeCAD.closeDocument(doc.Name)
    report["fcstd_saved_bytes"] = saved

    reopened = FreeCAD.openDocument(fcstd)
    re_shaped = [o for o in reopened.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]
    re_solids = sum(len(o.Shape.Solids) for o in re_shaped)
    re_volume = round(sum(float(o.Shape.Volume) for o in re_shaped), 4)
    re_invalid = sum(0 if o.Shape.isValid() else 1 for o in re_shaped)
    report["fcstd_reopen"] = {
        "object_count": len(reopened.Objects),
        "solid_count": re_solids,
        "total_volume_mm3": re_volume,
        "invalid_shape_count": re_invalid,
        "solid_count_match": re_solids == totals["solid_count"],
        "volume_abs_delta_mm3": round(abs(re_volume - totals["total_volume_mm3"]), 6),
    }
    FreeCAD.closeDocument(reopened.Name)
    report["residual_documents"] = list(FreeCAD.listDocuments())

    # ---- CSV inventory ----
    csv_path = fc.out("06_validation", "IMPORT_INVENTORY.csv")
    with open(csv_path, "w", encoding="utf-8") as fh:
        fh.write("name,label,shape_type,is_valid,solids,faces,volume_mm3,"
                 "com_x,com_y,com_z,bb_xmin,bb_ymin,bb_zmin,bb_xmax,bb_ymax,bb_zmax,identity\n")
        for r in rows:
            com = r.get("center_of_mass_mm") or [None, None, None]
            bb = r.get("bbox_mm") or [None] * 6
            fh.write(",".join(str(x) for x in [
                r.get("name"), r.get("label"), r.get("shape_type"), r.get("is_valid"),
                r.get("solids"), r.get("faces"), r.get("volume_mm3"),
                com[0], com[1], com[2], bb[0], bb[1], bb[2], bb[3], bb[4], bb[5],
                r.get("identity"),
            ]) + "\n")
    report["inventory_csv"] = fc.file_fact(csv_path)

    ok = (
        totals["document_object_count"] > 0
        and totals["solid_count"] > 0
        and report["fcstd_reopen"]["solid_count_match"]
        and report["fcstd_reopen"]["invalid_shape_count"] == 0
        and saved > 0
        and not report["residual_documents"]
    )
    report["verdict"] = "FC02_NEUTRAL_BASELINE_IMPORTED" if ok else "FC02_IMPORT_INTEGRITY_FAIL"
    report["single_document_route_viable"] = ok
    report["recommended_route"] = (
        "SINGLE_DOCUMENT" if ok else "SUBSYSTEM_APP_LINK_SPLIT"
    )
    fc.write_json("06_validation/FC02_IMPORT_INVENTORY.json", report)
    print(f"\nverdict: {report['verdict']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
