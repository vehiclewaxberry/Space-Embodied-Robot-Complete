# -*- coding: utf-8 -*-
"""P5 G1 pre-probe #2 (READ-ONLY): reference planes / axes available for mates.

The B601 base_link visual shell exposes NO flange face (largest plane 10 mm^2,
largest cylinder r=1.0) so a face-based coaxial+coincident mate to Central_Boss
(r=55 / r=50, end face x=208.0) is NOT constructible from solid faces alone.

The engineering-valid fallback is a DATUM-based mate set: mate the arm
sub-assembly's reference planes / origin to the spacecraft's, which still
expresses design intent (axis + clock + station) and is fully traceable --
unlike FixComponent absolute coordinates. This probe enumerates what datums
actually exist in each document so the mate script selects real entities.

Reports per component: reference planes (name), axes, coordinate systems, and
the sub-assembly's own top-level reference geometry.
SAVE_CALLS_ALLOWED = 0.
"""
import json
import sys
import traceback

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss

log = JLog("p5g1_datum")
NC = F3R1 / "03_native_cad"
TOP = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V2_MATED.SLDASM"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
SC = NC / "SPACECRAFT_V2_2_NATIVE_COPY/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM"
OUT = NC / "F3R1_DATUM_PROBE.json"
gm = swc.get_com_member

DATUM_TYPES = {"RefPlane", "RefAxis", "CoordSys", "RefPoint", "OriginProfileFeature"}


def doc_datums(model, limit=400):
    """Top-level reference geometry of a document (planes/axes/coordsys)."""
    out = []
    feat = gm(model, "FirstFeature")
    n = 0
    while feat is not None and n < limit:
        f = swc.cast(feat, "IFeature")
        tn = str(gm(f, "GetTypeName2"))
        if tn in DATUM_TYPES:
            out.append({"name": str(gm(f, "Name")), "type": tn})
        feat = gm(f, "GetNextFeature")
        n += 1
    return out


def main():
    check_protected("P5G1_DATUM_PRE")
    rep = {"schema": "F3R1_DATUM_PROBE_V1"}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("p5g1_datum")
    try:
        app = ss.connect(log)
        for tag, path in (("arm", ARM), ("spacecraft", SC), ("top", TOP)):
            m = swc.open_document(app, blog, str(path), read_only=True)
            rep[tag] = {"path": str(path), "datums": doc_datums(m)}
            rep[tag]["n_datums"] = len(rep[tag]["datums"])
            swc.close_document(app, m, blog)
        rep["verdict"] = "DATUM_PROBE_OK"
    except Exception as exc:
        rep["verdict"] = "DATUM_PROBE_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]
    finally:
        wd.stop()
    check_protected("P5G1_DATUM_POST")
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"])
    for tag in ("arm", "spacecraft", "top"):
        d = rep.get(tag) or {}
        print("\n%s: %d datums" % (tag, d.get("n_datums", 0)))
        for x in (d.get("datums") or [])[:14]:
            print("   %-30s %s" % (x["name"], x["type"]))
    if rep["verdict"] != "DATUM_PROBE_OK":
        print(rep.get("traceback"))


if __name__ == "__main__":
    main()
