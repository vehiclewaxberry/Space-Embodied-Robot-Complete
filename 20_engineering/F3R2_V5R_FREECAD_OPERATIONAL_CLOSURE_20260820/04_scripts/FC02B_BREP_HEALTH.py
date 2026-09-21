r"""FC02B_BREP_HEALTH.py - characterise and attempt repair of invalid solids.

script_id            : FC02B_BREP_HEALTH
schema_version       : 1.0
allowed_output_root  : 20_engineering/F3R2_V5R_FREECAD_OPERATIONAL_CLOSURE_20260820
authoritative_sources: FC02 import FCStd (derived, not a donor)
prohibited_sources   : does NOT modify the source STEP or any donor asset

FC02 found 6 of 457 solids failing OCC validity. They are 3 identical pairs
(2232-face @ ~127376 mm3, 169-face @ 1054.9297 mm3), i.e. one defect in two part
types instanced three times.

This script, per owner ruling section 19 (gripper boolean failure procedure,
applied to import health):
  1. reports WHY each is invalid (shape check messages)
  2. attempts removeSplitter / refine
  3. attempts a fix() pass with declared tolerances
  4. re-validates and reports the RAW outcome

It does NOT delete, silently drop, or hide an unrepairable solid. Anything still
invalid is carried forward as an explicit HOLD so it cannot leak into the
collision model unnoticed.

Writes a NEW FCStd; never overwrites the FC02 import.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common as fc  # noqa: E402

import FreeCAD  # noqa: E402

SCRIPT_ID = "FC02B_BREP_HEALTH"
SRC_FCSTD = "03_fcstd/FC02_FULL_SYSTEM_IMPORT.FCStd"
OUT_FCSTD = "03_fcstd/FC02B_FULL_SYSTEM_REPAIRED.FCStd"


def describe(shape) -> dict:
    """Collect validity evidence without throwing."""
    info = {
        "is_valid": bool(shape.isValid()),
        "shape_type": shape.ShapeType,
        "solids": len(shape.Solids),
        "shells": len(shape.Shells),
        "faces": len(shape.Faces),
        "closed": None,
        "volume_mm3": round(float(shape.Volume), 6),
    }
    try:
        info["closed"] = bool(shape.isClosed())
    except Exception as exc:  # noqa: BLE001 - isClosed throws on some bad shells
        info["closed_error"] = f"{type(exc).__name__}: {exc}"
    try:
        shape.check(True)
        info["check_message"] = "check() raised nothing"
    except Exception as exc:  # noqa: BLE001
        info["check_message"] = f"{type(exc).__name__}: {exc}"[:400]
    return info


def main() -> int:
    report = fc.receipt_header(SCRIPT_ID)
    src = fc.out(*SRC_FCSTD.split("/"))
    if not os.path.isfile(src):
        report["verdict"] = "FC02B_SOURCE_FCSTD_ABSENT"
        fc.write_json("06_validation/BREP_HEALTH_REPORT.json", report)
        return 2

    for existing in list(FreeCAD.listDocuments()):
        FreeCAD.closeDocument(existing)

    doc = FreeCAD.openDocument(src)
    shaped = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]
    invalid = [o for o in shaped if not o.Shape.isValid()]
    report["total_shapes"] = len(shaped)
    report["invalid_before"] = len(invalid)
    print(f"{len(invalid)} invalid of {len(shaped)}")

    results = []
    repaired_count = 0
    for obj in invalid:
        entry = {"name": obj.Name, "label": obj.Label}
        entry["before"] = describe(obj.Shape)
        shape = obj.Shape
        strategy_used = None

        # strategy 1: removeSplitter (merges redundant coplanar faces)
        try:
            candidate = shape.removeSplitter()
            if candidate.isValid() and candidate.Solids:
                shape, strategy_used = candidate, "removeSplitter"
        except Exception as exc:  # noqa: BLE001
            entry["removeSplitter_error"] = f"{type(exc).__name__}: {exc}"[:200]

        # strategy 2: fix() with explicit tolerances
        if strategy_used is None:
            try:
                candidate = obj.Shape.copy()
                candidate.fix(1e-7, 1e-7, 1e-7)
                if candidate.isValid() and candidate.Solids:
                    shape, strategy_used = candidate, "fix(1e-7)"
            except Exception as exc:  # noqa: BLE001
                entry["fix_error"] = f"{type(exc).__name__}: {exc}"[:200]

        # strategy 3: looser fix
        if strategy_used is None:
            try:
                candidate = obj.Shape.copy()
                candidate.fix(1e-5, 1e-5, 1e-5)
                if candidate.isValid() and candidate.Solids:
                    shape, strategy_used = candidate, "fix(1e-5)"
            except Exception as exc:  # noqa: BLE001
                entry["fix_loose_error"] = f"{type(exc).__name__}: {exc}"[:200]

        entry["repair_strategy"] = strategy_used
        if strategy_used:
            after = describe(shape)
            entry["after"] = after
            entry["volume_rel_delta"] = round(
                abs(after["volume_mm3"] - entry["before"]["volume_mm3"])
                / max(abs(entry["before"]["volume_mm3"]), 1e-12), 12)
            # only accept a repair that does NOT move geometry materially
            accepted = after["is_valid"] and entry["volume_rel_delta"] < 1e-6
            entry["repair_accepted"] = accepted
            if accepted:
                obj.Shape = shape
                repaired_count += 1
        else:
            entry["repair_accepted"] = False
            entry["disposition"] = "UNREPAIRED_CARRIED_AS_HOLD"
        results.append(entry)
        print(f"  {obj.Name[-6:]}: strategy={strategy_used} accepted={entry['repair_accepted']}")

    doc.recompute()
    still_invalid = [o.Name for o in doc.Objects
                     if hasattr(o, "Shape") and not o.Shape.isNull() and not o.Shape.isValid()]

    out_path = fc.out(*OUT_FCSTD.split("/"))
    if os.path.isfile(out_path):
        os.remove(out_path)
    doc.saveAs(out_path)
    saved = os.path.getsize(out_path)
    FreeCAD.closeDocument(doc.Name)

    # cold verify
    re = FreeCAD.openDocument(out_path)
    re_invalid = [o.Name for o in re.Objects
                  if hasattr(o, "Shape") and not o.Shape.isNull() and not o.Shape.isValid()]
    re_solids = sum(len(o.Shape.Solids) for o in re.Objects
                    if hasattr(o, "Shape") and not o.Shape.isNull())
    FreeCAD.closeDocument(re.Name)

    report["details"] = results
    report["repaired_count"] = repaired_count
    report["invalid_after_repair"] = len(still_invalid)
    report["invalid_after_reopen"] = len(re_invalid)
    report["invalid_names_remaining"] = re_invalid
    report["solid_count_after_reopen"] = re_solids
    report["output_fcstd"] = fc.file_fact(out_path)
    report["fcstd_bytes"] = saved
    report["residual_documents"] = list(FreeCAD.listDocuments())

    if not re_invalid:
        report["verdict"] = "FC02B_BREP_HEALTH_PASS_ALL_REPAIRED"
    elif repaired_count:
        report["verdict"] = "FC02B_BREP_PARTIAL_REPAIR_RESIDUAL_HOLD"
    else:
        report["verdict"] = "FC02B_BREP_UNREPAIRED_HOLD"
    report["hold_policy"] = (
        "any solid still invalid is excluded from the collision model and recorded as "
        "an explicit HOLD. It is NOT deleted and NOT silently passed."
    )
    fc.write_json("06_validation/BREP_HEALTH_REPORT.json", report)
    print(f"\nverdict: {report['verdict']}  repaired={repaired_count} "
          f"remaining={len(re_invalid)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
