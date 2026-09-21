"""NATIVE-01 第一阶段验收：冷启动重开 → 装配树 → 配置抑制读回 → 全树干涉。

纪律：严禁以"当前会话看起来正确"作为持久性证据。本脚本必须在
SolidWorks 完全退出后独立运行（调用方负责先杀进程）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

V22_AUTO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/automation")
sys.path.insert(0, str(V22_AUTO))
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from b3_lib.sw_core import (BuildLog, cast, connect, get_com_member,
                            open_document, rebuild_or_fail)
from build_native import CONFIGS, SUPPRESS, SUP_RESOLVED, SUP_SUPPRESSED, TOP_ASM

ROOT = HERE.parent
NOW = datetime.now(timezone.utc).isoformat()


def walk(asm, comp=None, depth=0, out=None, seen=None):
    out = [] if out is None else out
    seen = set() if seen is None else seen
    comps = asm.GetComponents(True) if comp is None else None
    if comps is None:
        return out
    for c in comps:
        c2 = cast(c, "IComponent2")
        p = get_com_member(c2, "GetPathName")
        nm = Path(p).name
        out.append({"name": nm, "suffix": Path(p).suffix.upper(),
                    "exists": Path(p).exists(),
                    "suppressed": int(c2.GetSuppression2())})
    return out


def main():
    log = BuildLog("native01_verify")
    sw = connect(log)
    top = ROOT / "Assembly" / f"{TOP_ASM}.SLDASM"
    m = open_document(sw, log, top)
    asm = cast(m, "IAssemblyDoc")
    rep = {"verify_id": "NATIVE01_PHASE1_COLD_REOPEN_VERIFY",
           "generated_utc": NOW, "top_assembly": str(top)}

    # 1) 装配树（GetComponents(True)=仅顶层；False 会返回全部组件——实测语义）
    tree = []
    for c in asm.GetComponents(True):
        c2 = cast(c, "IComponent2")
        p = Path(get_com_member(c2, "GetPathName"))
        kids = []
        for k in (c2.GetChildren() or []):
            k2 = cast(k, "IComponent2")
            kp = Path(get_com_member(k2, "GetPathName"))
            gk = [Path(get_com_member(cast(g, "IComponent2"), "GetPathName")).name
                  for g in (k2.GetChildren() or [])]
            kids.append({"name": kp.name, "exists": kp.exists(), "children": gk})
        tree.append({"name": p.name, "exists": p.exists(),
                     "suffix": p.suffix.upper(), "children": kids})
    rep["assembly_tree_top_level"] = tree
    rep["top_level_count"] = len(tree)

    # 1b) 重复装入检测（V01/V08 教训：重合重复件会使抑制失效并掩盖干涉）
    flat = {}
    for c in asm.GetComponents(False):     # False = 全部组件（实测语义）
        c2 = cast(c, "IComponent2")
        p = get_com_member(c2, "GetPathName")
        flat[p] = flat.get(p, 0) + 1
    dups = {Path(k).name: v for k, v in flat.items() if v > 1}
    rep["duplicate_components"] = {
        "records": dups,
        "status": "PASS" if not dups else "FAIL_RECORDED",
        "note": "同一文件在装配中出现多次；重合重复件会让配置抑制形同虚设"}
    rep["broken_links"] = [t["name"] for t in tree if not t["exists"]] + \
        [k["name"] for t in tree for k in t["children"] if not k["exists"]]

    # 2) 配置抑制读回矩阵（冷启动后）
    matrix, mismatches = {}, []
    for cname in CONFIGS:
        m.ShowConfiguration2(cname)
        act = cast(m, "IModelDoc2").ConfigurationManager.ActiveConfiguration.Name
        if act != cname:
            mismatches.append({"config": cname, "activated": act,
                                "issue": "ACTIVATION_READBACK_FAILED"})
            continue
        row = {}
        for c in asm.GetComponents(True):
            c2 = cast(c, "IComponent2")
            stem = Path(get_com_member(c2, "GetPathName")).stem
            got = int(c2.GetSuppression2())
            want_sup = any(stem == s for s in SUPPRESS.get(cname, []))
            row[stem] = {"suppression": got,
                          "expected": "SUPPRESSED" if want_sup else "RESOLVED",
                          "match": (got == SUP_SUPPRESSED) == want_sup}
            if (got == SUP_SUPPRESSED) != want_sup:
                mismatches.append({"config": cname, "component": stem,
                                    "got": got, "want_suppressed": want_sup})
        matrix[cname] = row
    rep["config_suppression_matrix"] = matrix
    rep["config_mismatches"] = mismatches
    rep["config_persistence"] = "PASS" if not mismatches else "FAIL_RECORDED"

    # 3) 全树干涉（STOWED 配置，含完整主结构）
    m.ShowConfiguration2("STOWED")
    rebuild_or_fail(m, log, "verify_rebuild")
    im = asm.InterferenceDetectionManager
    im.TreatCoincidenceAsInterference = False
    im.UseTransform = False
    im.IncludeMultibodyPartInterferences = True
    im.MakeInterferingPartsTransparent = False
    results = im.GetInterferences()
    inter = []
    if results:
        for it in results:
            ii = cast(it, "IInterference")
            vol_mm3 = round(ii.Volume * 1e9, 3)
            names = []
            for c in (ii.Components or []):
                names.append(Path(get_com_member(cast(c, "IComponent2"),
                                                  "GetPathName")).stem)
            inter.append({"components": names, "volume_mm3": vol_mm3})
    rep["interference"] = {
        "count": len(inter),
        "records": sorted(inter, key=lambda x: -x["volume_mm3"])[:60],
        "total_volume_mm3": round(sum(i["volume_mm3"] for i in inter), 3),
        "status": "PASS_ZERO_INTERFERENCE" if not inter else "FAIL_RECORDED",
        "note": "TreatCoincidenceAsInterference=False：设计上的接触共面不计为干涉"}

    # 4) 原生文件清单
    files = []
    for p in sorted(ROOT.rglob("*")):
        if p.name.startswith("~$"):        # SolidWorks 锁文件，非交付产物
            continue
        if p.suffix.upper() in (".SLDPRT", ".SLDASM"):
            files.append({"path": p.relative_to(ROOT).as_posix(),
                           "bytes": p.stat().st_size})
    rep["native_files"] = {"count": len(files), "files": files}
    rep["summary"] = {
        "native_parts": sum(1 for f in files if f["path"].upper().endswith("SLDPRT")),
        "native_assemblies": sum(1 for f in files
                                  if f["path"].upper().endswith("SLDASM")),
        "broken_links": len(rep["broken_links"]),
        "config_persistence": rep["config_persistence"],
        "interference_count": len(inter)}
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence/phase1_verify.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep["summary"], ensure_ascii=False))
    if inter:
        for i in rep["interference"]["records"][:12]:
            print("  INTF", i["components"], i["volume_mm3"])
    sw.CloseAllDocuments(True)


if __name__ == "__main__":
    main()
