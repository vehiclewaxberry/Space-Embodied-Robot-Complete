"""B3-02 Master Skeleton 机器核验（fail-closed）。

对拍内容：
  1. CS_S / CS_M / CS_A0 的 MathTransform ArrayData vs frame_export_v0_1.yaml 期望值
     （CS_M/CS_A0 期望 [0,0,-1, 0,1,0, 1,0,0, 0.18525,0,0, ...]，CS_S 期望恒等）；
  2. 七个参考面的世界位姿（IRefPlane.Transform 平移分量）vs b3_build_spec.yaml；
  3. 15 项治理属性 + PARAM_* 冗余参数属性存在性；
  4. 等轴测证据截图（raw）。
结果写 evidence/b3_02/master_skeleton_machine_check.json，任何超差 = 退出码 1。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, cast, connect,
                            get_com_member, open_document, read_custom_properties)

PART = V2_ROOT / "00_Master_Skeleton/Master_Skeleton_V2_0.SLDPRT"
EVID = V2_ROOT / "evidence/b3_02"
TOL = 1e-9

EXPECTED_CS = {
    # ArrayData 前 9 = 旋转（frame_export 行向量约定），10-12 = 平移（米）
    "CS_S":  [1, 0, 0, 0, 1, 0, 0, 0, 1, 0.0, 0.0, 0.0],
    "CS_M":  [0, 0, -1, 0, 1, 0, 1, 0, 0, 0.18525, 0.0, 0.0],
    "CS_A0": [0, 0, -1, 0, 1, 0, 1, 0, 0, 0.18525, 0.0, 0.0],
}
# 平面期望：法向轴 + 沿该轴的世界偏移（米）
EXPECTED_PLANES = {
    "PLANE_REAR_BODY_FACE":    ("x", -0.17025),
    "PLANE_REAR_MID_BOUNDARY": ("x", -0.05675),
    "PLANE_MID_FRONT_BOUNDARY": ("x", 0.05675),
    "PLANE_TASK_FACE":         ("x", 0.17025),
    "PLANE_MOUNT_M":           ("x", 0.18525),
    "PLANE_SOLAR_ROOT_L":      ("y", 0.11315),
    "PLANE_SOLAR_ROOT_R":      ("y", -0.11315),
}
REQUIRED_PROPS = ["OBJECT_ID", "SYSTEM_OWNER", "PARENT_ID", "STRUCTURE_CLASS",
                  "REPRESENTATION_LAYER", "EVIDENCE_STATE", "SOURCE_REFERENCE",
                  "FRAME_ID", "INTERFACE_IDS", "MASS_OWNER", "NO_DYNAMICS_USE",
                  "MANUFACTURING_AUTHORITY", "EXECUTION_AUTHORITY", "CLAIM_LIMIT",
                  "BLOCKED_CONSUMERS"]


def check_cs(model, report):
    ext = model.Extension
    for name, exp in EXPECTED_CS.items():
        xf = ext.GetCoordinateSystemTransformByName(name)
        if xf is None:
            report["failures"].append(f"{name}: 坐标系不存在")
            continue
        data = list(xf.ArrayData)[:12]
        bad = [(i, a, e) for i, (a, e) in enumerate(zip(data, exp))
               if abs(a - e) > TOL]
        report["coordinate_systems"][name] = {
            "actual": data, "expected": exp, "match": not bad}
        if bad:
            report["failures"].append(f"{name}: ArrayData 超差 {bad[:3]}")


def check_planes(model, report):
    f = cast(get_com_member(model, "FirstFeature"), "IFeature")
    found = {}
    while f is not None:
        nm = f.Name
        if nm in EXPECTED_PLANES:
            rp = cast(get_com_member(f, "GetSpecificFeature2"), "IRefPlane")
            xf = get_com_member(rp, "Transform")
            data = list(get_com_member(xf, "ArrayData"))
            found[nm] = data
        f = cast(get_com_member(f, "GetNextFeature"), "IFeature")
    for nm, (axis, exp_off) in EXPECTED_PLANES.items():
        if nm not in found:
            report["failures"].append(f"{nm}: 参考面不存在")
            continue
        data = found[nm]
        origin = data[9:12]
        actual = origin[{"x": 0, "y": 1, "z": 2}[axis]]
        ok = abs(actual - exp_off) <= 1e-7
        report["planes"][nm] = {"axis": axis, "expected_m": exp_off,
                                "actual_m": actual, "origin": origin, "match": ok}
        if not ok:
            report["failures"].append(
                f"{nm}: 期望 {axis}={exp_off} 实际 {actual}")


def screenshot(sw, model, out_png: Path):
    model.ShowNamedView2("", 7)      # 7 = isometric
    model.ViewZoomtofit2()
    ok = model.SaveBMP(str(out_png), 1600, 1200)
    return bool(ok)


def main():
    log = BuildLog("b3_02_verify")
    EVID.mkdir(parents=True, exist_ok=True)
    report = {"part": str(PART.relative_to(V2_ROOT)),
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "coordinate_systems": {}, "planes": {}, "properties": {},
              "failures": []}
    sw = connect(log)
    sw.CloseAllDocuments(True)
    model = open_document(sw, log, PART, read_only=False)

    check_cs(model, report)
    check_planes(model, report)

    props = read_custom_properties(model)
    missing = [p for p in REQUIRED_PROPS if p not in props]
    n_params = len([k for k in props if k.startswith("PARAM_")])
    report["properties"] = {"present": len(props), "missing_required": missing,
                            "param_redundancy_count": n_params}
    if missing:
        report["failures"].append(f"缺治理属性: {missing}")

    shot = EVID / "master_skeleton_isometric_raw.bmp"
    if not screenshot(sw, model, shot):
        report["failures"].append("等轴测截图失败")
    else:
        report["screenshot"] = str(shot.relative_to(V2_ROOT))

    report["verdict"] = ("B3_02_MASTER_SKELETON_VERIFIED" if not report["failures"]
                         else "B3_02_VERIFY_FAIL")
    (EVID / "master_skeleton_machine_check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sw.CloseAllDocuments(True)
    print(json.dumps({"verdict": report["verdict"],
                      "failures": report["failures"]}, ensure_ascii=False, indent=2))
    sys.exit(0 if not report["failures"] else 1)


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
