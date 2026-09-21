"""B3 零件工厂：在 S 全局坐标内直接建模的参数化零件生成。

标定事实（probe_axis_mapping 日志）：
  - 右视基准面草图 (x_sk, y_sk) → 全局 (-Z, +Y)；即 x_sk=-z, y_sk=y。
  - 未翻转偏移面挤出 dir=False 沿 +X；翻转面法向反转，由 extrude_checked 自动纠向。
所有输入毫米；写 COM 前转米。
"""
from pathlib import Path

from .sw_core import (BuildLog, cast, create_offset_plane, get_com_member,
                      new_document, rebuild_or_fail, rename_last_feature, save_as,
                      set_custom_properties)

RIGHT = ["右视基准面", "Right Plane"]   # 法向 +X
TOP = ["上视基准面", "Top Plane"]       # 法向 +Y
FRONT = ["前视基准面", "Front Plane"]   # 法向 +Z


def _m(v):
    return v / 1000.0


def yz_rect_to_sketch(yc, zc, hy, hz):
    """全局 YZ 矩形（中心+半宽，mm）→ Right 面草图 CreateCenterRectangle 参数（米）。"""
    cx, cy = _m(-zc), _m(yc)
    return (cx, cy, 0.0, cx + _m(hz), cy + _m(hy), 0.0)


def select_plane(model, log, names):
    model.ClearSelection2(True)
    for nm in names:
        if model.Extension.SelectByID2(nm, "PLANE", 0, 0, 0, False, 0, None, 0):
            return nm
    log.fail("找不到基准面", candidates=list(names))


def extrude_checked(model, log, depth_mm, axis, lo_expect_mm, hi_expect_mm, name,
                    plane_off_mm):
    """盲挤出（方向按目标区间相对基面位置事前确定）并核对包围盒。

    标定规律：dir=False 恒沿基轴正向（与基面 flip 无关），dir=True 沿负向。
    """
    target_mid = (lo_expect_mm + hi_expect_mm) / 2.0
    dirflag = target_mid < plane_off_mm
    f = model.FeatureManager.FeatureExtrusion2(
        True, False, dirflag, 0, 0, _m(depth_mm), 0, False, False, False,
        False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    if f is None:
        log.fail("FeatureExtrusion2 失败", feature=name)
    rebuild_or_fail(model, log, name)
    box = cast(model, "IPartDoc").GetPartBox(True)
    idx = {"x": (0, 3), "y": (1, 4), "z": (2, 5)}[axis]
    lo, hi = box[idx[0]] * 1000, box[idx[1]] * 1000
    if abs(lo - lo_expect_mm) < 0.01 and abs(hi - hi_expect_mm) < 0.01:
        rename_last_feature(model, log, name)
        return
    log.fail("挤出位置超差", feature=name, got=[round(lo, 3), round(hi, 3)],
             want=[lo_expect_mm, hi_expect_mm], dirflag=dirflag)


def build_x_extruded_part(sw, log, out_path: Path, name, rects_yz, x_span_mm,
                          props):
    """沿 X 挤出的零件：rects_yz = [(yc,zc,hy,hz), ...]（每矩形一草图一挤出）。"""
    if out_path.exists():
        log.event("PART_SKIP_EXISTS", part=name)
        return
    model = new_document(sw, log, "part")
    x_min, x_max = x_span_mm
    create_offset_plane(model, log, RIGHT, x_min,
                        f"PLN_{name}_BASE", flip=x_min < 0)
    # 多轮廓草图无法免选择挤出（API 返回 None）——每轮廓独立 草图+挤出
    # 轮廓元组：(yc,zc,hy,hz)=矩形；(yc,zc,r)=圆
    for i, r in enumerate(rects_yz):
        model.ClearSelection2(True)
        if not model.Extension.SelectByID2(f"PLN_{name}_BASE", "PLANE", 0, 0, 0,
                                           False, 0, None, 0):
            log.fail("选择零件基面失败", part=name)
        sk = model.SketchManager
        sk.InsertSketch(True)
        if len(r) == 3:
            yc, zc, rad = r
            sk.CreateCircleByRadius(_m(-zc), _m(yc), 0.0, _m(rad))
        else:
            sk.CreateCenterRectangle(*yz_rect_to_sketch(*r))
        sk.InsertSketch(True)   # 退出草图后立即挤出（隐式活动草图上下文）
        suffix = f"_{i+1}" if len(rects_yz) > 1 else ""
        extrude_checked(model, log, x_max - x_min, "x", x_min, x_max,
                        f"EX_{name}{suffix}", plane_off_mm=x_min)
        feats = cast(model, "IModelDoc2").FeatureManager.GetFeatures(True)
        cast(feats[-2], "IFeature").Name = f"SK_{name}{suffix}"
    set_custom_properties(model, log, props)
    rebuild_or_fail(model, log, name)
    save_as(model, log, out_path)
    sw.CloseDoc(get_com_member(model, "GetTitle"))
    log.event("PART_BUILT", part=name, path=str(out_path))


def build_face_panel_part(sw, log, out_path: Path, name, face, props,
                          x_half_mm=158.25, width_half_mm=98.15,
                          outer_mm=113.15, thick_mm=3.0):
    """±Y/±Z 面板：外表面与包络齐平、厚度向内。轮廓全对称，免轴映射标定。"""
    if out_path.exists():
        log.event("PART_SKIP_EXISTS", part=name)
        return
    model = new_document(sw, log, "part")
    axis = "z" if face in ("+Z", "-Z") else "y"
    sign = 1 if face.startswith("+") else -1
    base_names = FRONT if axis == "z" else TOP
    inner = outer_mm - thick_mm
    base_off = sign * inner
    create_offset_plane(model, log, base_names, base_off,
                        f"PLN_{name}_BASE", flip=base_off < 0)
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(f"PLN_{name}_BASE", "PLANE", 0, 0, 0,
                                       False, 0, None, 0):
        log.fail("选择面板基面失败", part=name)
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreateCenterRectangle(0, 0, 0, _m(x_half_mm), _m(width_half_mm), 0)
    sk.InsertSketch(True)
    lo, hi = (inner, outer_mm) if sign > 0 else (-outer_mm, -inner)
    extrude_checked(model, log, thick_mm, axis, lo, hi, f"EX_{name}",
                    plane_off_mm=base_off)
    feats = cast(model, "IModelDoc2").FeatureManager.GetFeatures(True)
    cast(feats[-2], "IFeature").Name = f"SK_{name}"
    set_custom_properties(model, log, props)
    rebuild_or_fail(model, log, name)
    save_as(model, log, out_path)
    sw.CloseDoc(get_com_member(model, "GetTitle"))
    log.event("PART_BUILT", part=name, path=str(out_path))
