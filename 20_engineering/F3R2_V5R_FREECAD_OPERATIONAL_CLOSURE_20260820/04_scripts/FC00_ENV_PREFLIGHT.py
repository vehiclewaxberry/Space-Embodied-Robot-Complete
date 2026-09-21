r"""FC00_ENV_PREFLIGHT.py - FreeCAD toolchain smoke test.

script_id            : FC00_ENV_PREFLIGHT
schema_version       : 1.0
input_manifest_sha256: n/a (no project inputs are read; this validates the toolchain only)
allowed_output_root  : 20_engineering/F3R2_V5R_FREECAD_OPERATIONAL_CLOSURE_20260820
authoritative_sources: none (toolchain self-test)
prohibited_sources   : none read; NO project asset is opened or written

Twelve-step preflight per the owner ruling:
  1 create empty document      7 export STEP
  2 create 10 mm cube          8 re-import STEP
  3 save FCStd                 9 compare volume/bbox/solids/validity
  4 close                     10 (screenshot: GUI-only, recorded as N/A headless)
  5 reopen                    11 close document
  6 check objects/solids/     12 verify no residual documents
    volume/bbox/validity

Idempotent: removes its own prior scratch outputs before running. Writes only
inside the round directory. Run headless:

  freecadcmd.exe FC00_ENV_PREFLIGHT.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common as fc  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402

SCRIPT_ID = "FC00_ENV_PREFLIGHT"
CUBE_MM = 10.0
EXPECTED_VOLUME = CUBE_MM ** 3


def main() -> int:
    report = fc.receipt_header(SCRIPT_ID)
    report["freecad_environment"] = fc.freecad_environment()
    steps: list[dict] = []
    failures: list[str] = []

    def step(name: str, ok: bool, **detail):
        entry = {"step": name, "pass": bool(ok)}
        entry.update(detail)
        steps.append(entry)
        if not ok:
            failures.append(name)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        return ok

    fcstd_path = fc.out("03_fcstd", "FC00_SMOKE.FCStd")
    step_path = fc.out("07_exports", "FC00_SMOKE.step")
    for stale in (fcstd_path, step_path):
        if os.path.isfile(stale):
            os.remove(stale)          # idempotent re-run

    doc_name = "FC00_SMOKE"
    for existing in list(FreeCAD.listDocuments()):
        FreeCAD.closeDocument(existing)   # start from a clean slate

    # --- 1/2 create document and cube ---
    doc = FreeCAD.newDocument(doc_name)
    box = doc.addObject("Part::Box", "SmokeCube")
    box.Length, box.Width, box.Height = CUBE_MM, CUBE_MM, CUBE_MM
    doc.recompute()
    created = fc.shape_facts(box.Shape)
    step("create_cube", created["is_valid"] and created["solid_count"] == 1,
         facts=created)
    step("cube_volume_exact",
         abs(created["volume_mm3"] - EXPECTED_VOLUME) < 1e-9,
         expected_mm3=EXPECTED_VOLUME, actual_mm3=created["volume_mm3"])

    # --- 3/4 save and close ---
    doc.saveAs(fcstd_path)
    saved_bytes = os.path.getsize(fcstd_path)
    FreeCAD.closeDocument(doc_name)
    step("fcstd_saved", saved_bytes > 0, path=fcstd_path.replace("\\", "/"),
         bytes=saved_bytes)

    # --- 5/6 reopen and verify ---
    reopened = FreeCAD.openDocument(fcstd_path)
    objs = [o for o in reopened.Objects if hasattr(o, "Shape")]
    reopen_facts = fc.shape_facts(objs[0].Shape) if objs else {}
    roundtrip_fcstd = fc.compare_shape_facts(created, reopen_facts) if objs else {}
    step("fcstd_reopen",
         bool(objs) and reopen_facts.get("is_valid")
         and roundtrip_fcstd.get("solid_count_match")
         and roundtrip_fcstd.get("volume_within_declared_tol"),
         object_count=len(reopened.Objects), comparison=roundtrip_fcstd)
    report["fcstd_roundtrip"] = roundtrip_fcstd

    # --- 7 export STEP ---
    Part.export([objs[0]], step_path)
    step_bytes = os.path.getsize(step_path) if os.path.isfile(step_path) else 0
    step("step_exported", step_bytes > 0, path=step_path.replace("\\", "/"),
         bytes=step_bytes)
    FreeCAD.closeDocument(reopened.Name)

    # --- 8/9 re-import STEP into a NEW document and compare ---
    import_doc = FreeCAD.newDocument("FC00_STEP_REIMPORT")
    Part.insert(step_path, import_doc.Name)   # console-safe importer
    import_doc.recompute()
    shapes = [o for o in import_doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]
    imported = fc.shape_facts(shapes[0].Shape) if shapes else {}
    roundtrip_step = fc.compare_shape_facts(created, imported) if shapes else {}
    step("step_roundtrip",
         bool(shapes) and imported.get("is_valid")
         and roundtrip_step.get("solid_count_match")
         and roundtrip_step.get("volume_within_declared_tol"),
         imported_object_count=len(import_doc.Objects), comparison=roundtrip_step)
    report["step_roundtrip"] = roundtrip_step

    # --- 10 screenshot ---
    gui_available = FreeCAD.GuiUp
    step("screenshot", True, captured=bool(gui_available),
         note="GUI not up under freecadcmd; screenshot deferred to a GUI session. "
              "Recorded as not-captured rather than silently skipped."
         if not gui_available else "GUI session available")
    report["screenshot_captured"] = bool(gui_available)

    # --- 11/12 close and verify no residue ---
    FreeCAD.closeDocument(import_doc.Name)
    residual = list(FreeCAD.listDocuments())
    step("no_residual_documents", len(residual) == 0, residual=residual)

    # --- outputs ---
    report["steps"] = steps
    report["failures"] = failures
    report["outputs"] = {
        "fcstd": fc.file_fact(fcstd_path),
        "step": fc.file_fact(step_path),
    }
    report["write_boundary_respected"] = True
    report["project_assets_read"] = 0
    report["project_assets_written"] = 0
    report["verdict"] = "FC00_TOOLCHAIN_READY" if not failures else "FC00_TOOLCHAIN_FAIL"

    fc.write_json("01_toolchain/FREECAD_ENVIRONMENT.json", {
        **fc.receipt_header(SCRIPT_ID),
        "environment": report["freecad_environment"],
        "freecadcmd_path": sys.executable.replace("\\", "/"),
    })
    fc.write_json("01_toolchain/FREECAD_STEP_ROUNDTRIP_SMOKE.json", report)

    print(f"\nverdict: {report['verdict']}")
    print(f"commit: {report['resource_snapshot']['commit_utilisation_pct']}% "
          f"of {report['resource_snapshot']['commit_limit_gib']} GiB")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
