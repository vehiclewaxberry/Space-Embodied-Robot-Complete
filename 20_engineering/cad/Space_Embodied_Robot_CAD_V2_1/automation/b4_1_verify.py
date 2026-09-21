"""B4-1 机器验证（fail-closed）：
1. 全原生重开；有实体件/装配重建，零实体 reference 做零 body 断言；
2. 七态配置翼件抑制对拍；3. 关键件包围盒（翼双表示/节点垫/分段板）；
4. 18 个机构 reference 零实体断言。→ evidence/b4_1_verify/machine_check.json
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import b3_lib.sw_core as core
from b3_lib.sw_core import (B3FailClosed, BuildLog, activate_configuration, cast,
                            connect, get_com_member, open_document)

V21 = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_1")
core.V2_ROOT = V21
core.LOG_DIR = V21 / "evidence" / "build_logs"
SPEC = yaml.safe_load((V21 / "automation/b4_1_build_spec.yaml").read_text(encoding="utf-8"))
TOP = V21 / "Assembly/Spacecraft_Service_Vehicle_V2_1.SLDASM"
EVID = V21 / "evidence/b4_1_verify"

BBOX_EXPECT = {}
for side in ("L", "R"):
    for state in ("deployed", "stowed"):
        b = SPEC["solar_mechanism"]["wing_solid"][state][side]
        BBOX_EXPECT[f"08_Solar_Wing_{side}/parts/SOLAR_WING_{side}_{state.upper()}.SLDPRT"] = (
            b["x_span_mm"], b["y_span_mm"], b["z_span_mm"])
for st in SPEC["primary_structure"]["node_pads"]["stations"]:
    BBOX_EXPECT[f"01_Primary_Frame/parts/{st['id']}.SLDPRT"] = (
        st["x_span_mm"], st["y_span_mm"], st["z_span_mm"])
for nm, seg in SPEC["primary_structure"]["segmented_side_panels"].items():
    if isinstance(seg, dict) and "face" in seg:
        s = 1 if seg["face"] == "+Y" else -1
        BBOX_EXPECT[f"03_Removable_Panels/parts/{nm}.SLDPRT"] = (
            seg["x_span_mm"], sorted([s * 110.15, s * 113.15]), [-98.15, 98.15])


def main():
    log = BuildLog("b4_1_verify")
    EVID.mkdir(parents=True, exist_ok=True)
    rep = {"generated_utc": datetime.now(timezone.utc).isoformat(),
           "reopen": {}, "bbox": {}, "states": {}, "zero_solid": {}, "failures": []}
    sw = connect(log)
    sw.CloseAllDocuments(True)

    natives = sorted(V21.rglob("*.SLDPRT")) + sorted(V21.rglob("*.SLDASM"))
    zero_refs = [p for p in natives
                 if "Root_Module" in str(p) and p.suffix == ".SLDPRT"]
    zero_ref_set = set(zero_refs)
    ok = 0
    for p in natives:
        try:
            # Root-module mechanism placeholders intentionally contain only named
            # sketches/anchors. ForceRebuild3 can block indefinitely on these
            # zero-solid reference parts in SW2024; reopening plus a zero-body
            # assertion is the correct verification contract for that class.
            m = open_document(sw, log, p, read_only=True)
            if p in zero_ref_set:
                bodies = get_com_member(cast(m, "IPartDoc"),
                                        "GetBodies2", 0, True)
                if bodies in (None, False):
                    n = 0
                elif isinstance(bodies, (tuple, list)):
                    n = len(bodies)
                else:
                    n = 1
                rep["zero_solid"][p.name] = (n == 0)
                if n:
                    rep["failures"].append(f"zero_solid:{p.name}:{n}")
                ok += 1
            elif m.ForceRebuild3(False):
                ok += 1
            else:
                rep["failures"].append(f"rebuild:{p.name}")
        except B3FailClosed:
            rep["failures"].append(f"reopen:{p.name}")
        log.event("VERIFY_REOPEN_RESULT", file=p.name,
                  ok=not any(p.name in f for f in rep["failures"]))
        sw.CloseAllDocuments(True)
    rep["reopen"] = {"total": len(natives), "pass": ok}

    for rel, (ex, ey, ez) in BBOX_EXPECT.items():
        m = open_document(sw, log, V21 / rel, read_only=True)
        b = [v * 1000 for v in cast(m, "IPartDoc").GetPartBox(True)]
        act = ([b[0], b[3]], [b[1], b[4]], [b[2], b[5]])
        good = all(abs(a - e) <= 0.01 for exp, a2 in zip((ex, ey, ez), act)
                   for a, e in zip(a2, exp))
        rep["bbox"][rel] = good
        if not good:
            rep["failures"].append(f"bbox:{rel}:{[ [round(v,2) for v in s] for s in act]}")
        sw.CloseAllDocuments(True)

    m = open_document(sw, log, TOP)
    asm = cast(m, "IAssemblyDoc")
    for cname, sdef in SPEC["state_family"].items():
        activate_configuration(m, log, cname)
        m.ForceRebuild3(False)
        got = {}
        for c in asm.GetComponents(False) or []:
            c2 = cast(c, "IComponent2")
            nm = c2.Name2
            if "SOLAR_WING_" in nm:
                got[nm.split("/")[-1].rsplit("-", 1)[0]] = bool(
                    get_com_member(c2, "IsSuppressed"))
        want = {}
        for side in ("L", "R"):
            mode = sdef.get(side)
            want[f"SOLAR_WING_{side}_DEPLOYED"] = mode in ("stowed", "none")
            want[f"SOLAR_WING_{side}_STOWED"] = mode in ("deployed", "none")
        match = all(got.get(k) == v for k, v in want.items())
        rep["states"][cname] = {"want": want, "got": got, "match": match}
        if not match:
            rep["failures"].append(f"state:{cname}")
    activate_configuration(m, log, "DEPLOYED_NOMINAL")
    sw.CloseAllDocuments(True)

    rep["verdict"] = ("B4_1_MACHINE_CHECK_PASS" if not rep["failures"]
                      else "B4_1_MACHINE_CHECK_FAIL")
    (EVID / "machine_check.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": rep["verdict"], "reopen": rep["reopen"],
                      "failures": rep["failures"][:8]}, ensure_ascii=False))
    sys.exit(0 if not rep["failures"] else 1)


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
