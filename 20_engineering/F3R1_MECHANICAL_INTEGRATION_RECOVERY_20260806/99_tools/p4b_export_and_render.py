# -*- coding: utf-8 -*-
"""P4b: export the F3R1 top assembly (active config STOWED_LOCKED) to STEP,
then render witness views via FreeCAD (CAD API viewport export).

Rationale (registered): this machine's SolidWorks SaveBMP renders a fixed
internal camera regardless of view ops (B3 trap #3) -- image hashes do not
change across views. The proven witness route is config-bound STEP export +
FreeCAD viewport rendering of that exact STEP (hash-bound to the assembly).
"""
import json
import sys
import traceback

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss

log = JLog("p4b_export")
NC = F3R1 / "03_native_cad"
TOP = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM"
OUT_STEP = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_STOWED.step"
OUT = F3R1 / "11_screenshots" / "F3R1_EXPORT_RECORD.json"


def main():
    check_protected("P4B_PRE")
    rep = {"schema": "F3R1_EXPORT_RECORD_V1"}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("p4b")
    try:
        app = ss.connect(log)
        top = swc.open_document(app, blog, str(TOP))
        swc.activate_configuration(top, blog, "STOWED_LOCKED")
        swc.rebuild_or_fail(top, blog, "pre-export rebuild")
        if OUT_STEP.exists():
            OUT_STEP.unlink()  # re-export is idempotent witness, not evidence loss
        swc.save_as(top, blog, OUT_STEP, overwrite=True)
        rep["step"] = {"path": str(OUT_STEP), "sha256": sha256_file(OUT_STEP),
                       "bytes": OUT_STEP.stat().st_size,
                       "source_sldasm_sha256": sha256_file(TOP),
                       "configuration": "STOWED_LOCKED"}
        swc.close_document(app, top, blog)
        rep["verdict"] = "STEP_EXPORTED"
    except Exception as exc:
        rep["verdict"] = "FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]
    finally:
        wd.stop()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"])
    sys.exit(0 if rep["verdict"] == "STEP_EXPORTED" else 1)


if __name__ == "__main__":
    main()
