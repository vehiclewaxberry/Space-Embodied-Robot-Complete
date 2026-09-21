"""B3-03 主结构机器核验（fail-closed）。

  1. 14 零件包围盒逐件对拍 b3_build_spec.yaml 推导的期望区间（±0.01mm）；
  2. 装配重开+重建+组件计数（14）+ 每组件恒等位姿（AddComponent 于原点）；
  3. 等轴测证据截图。
结果 → evidence/b3_03/primary_structure_machine_check.json。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, cast, connect,
                            get_com_member, open_document)

PARTS_DIR = V2_ROOT / "01_Primary_Structure/parts"
ASM_PATH = V2_ROOT / "01_Primary_Structure/SV2_Primary_Structure.SLDASM"
EVID = V2_ROOT / "evidence/b3_03"
TOL = 0.01  # mm

HB, NW = 113.15, 15.0
HIN = HB - NW
EXPECTED = {
    "FRM_FRONT_TASK":    ([158.25, 170.25], [-HB, HB], [-HB, HB]),
    "FRM_REAR_BOUNDARY": ([-170.25, -158.25], [-HB, HB], [-HB, HB]),
    "FRM_REAR_MID":      ([-62.75, -50.75], [-HB, HB], [-HB, HB]),
    "FRM_MID_FRONT":     ([50.75, 62.75], [-HB, HB], [-HB, HB]),
    "LNG_PY_PZ": ([-170.25, 170.25], [HIN, HB], [HIN, HB]),
    "LNG_PY_NZ": ([-170.25, 170.25], [HIN, HB], [-HB, -HIN]),
    "LNG_NY_PZ": ([-170.25, 170.25], [-HB, -HIN], [HIN, HB]),
    "LNG_NY_NZ": ([-170.25, 170.25], [-HB, -HIN], [-HB, -HIN]),
    "DECK_REAR_MID":  ([-60.75, -52.75], [-HIN, HIN], [-HIN, HIN]),
    "DECK_MID_FRONT": ([52.75, 60.75], [-HIN, HIN], [-HIN, HIN]),
    "PNL_TOP":    ([-158.25, 158.25], [-HIN, HIN], [110.15, 113.15]),
    "PNL_BOTTOM": ([-158.25, 158.25], [-HIN, HIN], [-113.15, -110.15]),
    "PNL_LEFT":   ([-158.25, 158.25], [110.15, 113.15], [-HIN, HIN]),
    "PNL_RIGHT":  ([-158.25, 158.25], [-113.15, -110.15], [-HIN, HIN]),
}
IDENT = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def main():
    log = BuildLog("b3_03_verify")
    EVID.mkdir(parents=True, exist_ok=True)
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "parts": {}, "assembly": {}, "failures": []}
    sw = connect(log)
    sw.CloseAllDocuments(True)

    for name, (ex, ey, ez) in EXPECTED.items():
        path = PARTS_DIR / f"{name}.SLDPRT"
        if not path.exists():
            report["failures"].append(f"{name}: 文件缺失")
            continue
        m = open_document(sw, log, path, read_only=True)
        box = [v * 1000 for v in cast(m, "IPartDoc").GetPartBox(True)]
        actual = ([box[0], box[3]], [box[1], box[4]], [box[2], box[5]])
        ok = all(abs(a - e) <= TOL
                 for exp, act in zip((ex, ey, ez), actual)
                 for a, e in zip(act, exp))
        report["parts"][name] = {"expected_mm": [ex, ey, ez],
                                 "actual_mm": [[round(v, 4) for v in s]
                                               for s in actual], "match": ok}
        if not ok:
            report["failures"].append(f"{name}: 包围盒超差")
        sw.CloseAllDocuments(True)

    m = open_document(sw, log, ASM_PATH, read_only=False)
    if not m.ForceRebuild3(False):
        report["failures"].append("装配重建失败")
    asm = cast(m, "IAssemblyDoc")
    n = asm.GetComponentCount(False)
    report["assembly"]["component_count"] = n
    if n != len(EXPECTED):
        report["failures"].append(f"组件数 {n} != {len(EXPECTED)}")
    comps = asm.GetComponents(True)
    for c in comps or []:
        c2 = cast(c, "IComponent2")
        xf = get_com_member(c2, "Transform2")
        data = list(get_com_member(xf, "ArrayData"))[:12]
        ok = all(abs(a - e) <= 1e-9 for a, e in zip(data, IDENT))
        nm = c2.Name2
        report["assembly"][nm] = {"identity_placement": ok}
        if not ok:
            report["failures"].append(f"{nm}: 非恒等位姿 {data}")

    m.ShowNamedView2("", 7)
    m.ViewZoomtofit2()
    shot = EVID / "primary_structure_isometric_raw.bmp"
    if m.SaveBMP(str(shot), 1600, 1200):
        report["screenshot"] = str(shot.relative_to(V2_ROOT))
    else:
        report["failures"].append("截图失败")
    sw.CloseAllDocuments(True)

    report["verdict"] = ("B3_03_PRIMARY_STRUCTURE_VERIFIED"
                         if not report["failures"] else "B3_03_VERIFY_FAIL")
    (EVID / "primary_structure_machine_check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"],
                      "failures": report["failures"]}, ensure_ascii=False))
    sys.exit(0 if not report["failures"] else 1)


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
