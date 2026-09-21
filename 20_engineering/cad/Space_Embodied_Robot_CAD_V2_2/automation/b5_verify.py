"""V2.2 终验（fail-closed）：重开全检 / 八态翼抑制对拍 / B601 偏移实测 /
关键包围盒 / 视图导出。→ evidence/b5_verify/machine_check.json"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import b3_lib.sw_core as core
from b3_lib.sw_core import (B3FailClosed, BuildLog, activate_configuration, cast,
                            connect, get_com_member, open_document)

V22 = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_2")
core.V2_ROOT = V22
core.LOG_DIR = V22 / "evidence" / "build_logs"
S = yaml.safe_load((V22 / "automation/b5_build_spec.yaml").read_text(encoding="utf-8"))
TOP = V22 / "Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM"
EVID = V22 / "evidence/b5_verify"

PLAN = {"STOWED": ("stowed", "stowed"), "DEPLOYED_NOMINAL": ("deployed", "deployed"),
        "DEPLOY_FAILED_BOTH": ("stowed", "stowed"), "L_FAIL": ("stowed", "deployed"),
        "R_FAIL": ("deployed", "stowed"), "PARTIAL": ("none", "none"),
        "SERVICE": ("deployed", "deployed"), "CAPTURE_SAFE": ("deployed", "deployed")}

BBOX = {
    "10_Primary_Structure/parts/LNG_PY_PZ.SLDPRT": ([-183.0, 183.0], [98.15, 113.15], [98.15, 113.15]),
    "10_Primary_Structure/parts/FRM_FRONT.SLDPRT": ([171.0, 183.0], [-113.15, 113.15], [-113.15, 113.15]),
    "20_B601_Interface/parts/BOSS.SLDPRT": ([156.0, 171.0], [-50.0, 50.0], [-50.0, 50.0]),
    "50_Solar_Array_Left/parts/WING_L_DEPLOYED.SLDPRT": ([-174.5, 52.5], [113.15, 313.15], [-3.0, 3.0]),
    "50_Solar_Array_Left/parts/WING_L_STOWED.SLDPRT": ([-174.5, 52.5], [113.15, 119.15], [-200.0, 0.0]),
    "50_Solar_Array_Right/parts/WING_R_DEPLOYED.SLDPRT": ([-174.5, 52.5], [-313.15, -113.15], [-3.0, 3.0]),
}


def main():
    log = BuildLog("b5_verify")
    EVID.mkdir(parents=True, exist_ok=True)
    rep = {"generated_utc": datetime.now(timezone.utc).isoformat(),
           "reopen": {}, "bbox": {}, "states": {}, "b601_offset": {},
           "failures": []}
    sw = connect(log)
    sw.CloseAllDocuments(True)

    natives = sorted(V22.rglob("*.SLDPRT")) + sorted(V22.rglob("*.SLDASM"))
    ok = 0
    for p in natives:
        try:
            m = open_document(sw, log, p, read_only=True)
            if m.ForceRebuild3(False):
                ok += 1
            else:
                rep["failures"].append(f"rebuild:{p.name}")
        except B3FailClosed:
            rep["failures"].append(f"reopen:{p.name}")
        sw.CloseAllDocuments(True)
    rep["reopen"] = {"total": len(natives), "pass": ok}
    if ok != len(natives):
        pass  # failures 已记录

    for rel, (ex, ey, ez) in BBOX.items():
        m = open_document(sw, log, V22 / rel, read_only=True)
        b = [v * 1000 for v in cast(m, "IPartDoc").GetPartBox(True)]
        act = ([b[0], b[3]], [b[1], b[4]], [b[2], b[5]])
        good = all(abs(a - e) <= 0.01 for exp, a2 in zip((ex, ey, ez), act)
                   for a, e in zip(a2, exp))
        rep["bbox"][rel] = good
        if not good:
            rep["failures"].append(f"bbox:{rel}")
        sw.CloseAllDocuments(True)

    m = open_document(sw, log, TOP)
    asm = cast(m, "IAssemblyDoc")
    sw.CloseAllDocuments(True)
    pm = open_document(sw, log, V22 / "30_B601_Controlled_Subassembly/parts/B601V22_base_link.SLDPRT", read_only=True)
    x0 = round(cast(pm, "IPartDoc").GetPartBox(True)[0] * 1000, 3)
    sw.CloseAllDocuments(True)
    rep["b601_offset"] = {"mode": "geometry_baked", "base_link_x_mm": x0,
                          "expected": 198.0, "match": abs(x0 - 198.0) < 0.05}
    if not rep["b601_offset"]["match"]:
        rep["failures"].append(f"b601_proxy_x:{x0}")
    m = open_document(sw, log, TOP)
    asm = cast(m, "IAssemblyDoc")
    for cname, (lm, rm) in PLAN.items():
        activate_configuration(m, log, cname)
        m.ForceRebuild3(False)
        got, want = {}, {}
        for c in asm.GetComponents(True) or []:
            c2 = cast(c, "IComponent2")
            nm = c2.Name2
            if "WING_" in nm:
                key = nm.rsplit("-", 1)[0]
                got[key] = bool(get_com_member(c2, "IsSuppressed"))
        for side, mode in (("L", lm), ("R", rm)):
            want[f"WING_{side}_DEPLOYED"] = mode in ("stowed", "none")
            want[f"WING_{side}_STOWED"] = mode in ("deployed", "none")
        match = all(got.get(k) == v for k, v in want.items())
        rep["states"][cname] = match
        if not match:
            rep["failures"].append(f"state:{cname}:{got}")
    # 视图导出
    sw.Visible = True
    shots = []
    for cfg, tag in [("DEPLOYED_NOMINAL", "deployed_iso"), ("STOWED", "stowed_iso"),
                     ("CAPTURE_SAFE", "capture_safe_iso")]:
        activate_configuration(m, log, cfg)
        m.ForceRebuild3(False)
        m.ShowNamedView2("", 7)
        m.ViewZoomtofit2()
        p = EVID / f"v22_{tag}.bmp"
        if m.SaveBMP(str(p), 1600, 1200):
            shots.append(p.name)
        else:
            rep["failures"].append(f"shot:{tag}")
    rep["views"] = shots
    activate_configuration(m, log, "DEPLOYED_NOMINAL")
    sw.CloseAllDocuments(True)
    sw.Visible = False

    rep["verdict"] = ("V22_MACHINE_CHECK_PASS" if not rep["failures"]
                      else "V22_MACHINE_CHECK_FAIL")
    (EVID / "machine_check.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": rep["verdict"], "reopen": rep["reopen"],
                      "b601_offset": rep["b601_offset"],
                      "failures": rep["failures"][:8]}, ensure_ascii=False))
    sys.exit(0 if not rep["failures"] else 1)


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
