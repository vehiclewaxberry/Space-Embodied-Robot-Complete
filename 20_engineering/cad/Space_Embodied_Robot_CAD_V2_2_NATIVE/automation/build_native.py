"""SOLIDWORKS-NATIVE-MECHANICAL-REALIZATION-01 第一阶段构建器（A–F）。

唯一写入者。产出真实 .SLDPRT/.SLDASM，可重入（已存在即跳过）。
用法：python build_native.py <stage>   stage ∈ A|B|C|D|E|F|ALL
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

V22_AUTO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/automation")
sys.path.insert(0, str(V22_AUTO))
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from b3_lib.sw_core import (BuildLog, cast, close_document, connect,
                            create_offset_plane, get_com_member,
                            insert_components_identity, new_document,
                            open_document, rebuild_or_fail, rename_last_feature,
                            save_as, set_custom_properties)
from b3_lib.sw_part_factory import (FRONT, RIGHT, TOP, build_x_extruded_part)
import native_spec as S

ROOT = HERE.parent
OWNER = "SOLIDWORKS_NATIVE_CAD_BUILDER"
TOP_ASM = "Space_Embodied_Service_Spacecraft_V2_2"


def _m(v):
    return v / 1000.0


def cut_circle(model, log, plane_off_mm, yc, zc, d_mm, depth_mm, name):
    """在既有实体上开真实圆孔（V2.2 已验证：FeatureCut3 26 参，Dir 必须 False）。"""
    create_offset_plane(model, log, RIGHT, plane_off_mm, f"PLN_{name}",
                        flip=plane_off_mm < 0)
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(f"PLN_{name}", "PLANE", 0, 0, 0, False,
                                       0, None, 0):
        log.fail("选择开孔基面失败", cut=name)
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreateCircleByRadius(_m(-zc), _m(yc), 0.0, _m(d_mm / 2))
    sk.InsertSketch(True)
    f = model.FeatureManager.FeatureCut3(
        True, False, False, 0, 0, _m(depth_mm), 0.0, False, False, False,
        False, 0.0, 0.0, False, False, False, False, False, True, True, True,
        True, False, 0, 0.0, False)
    if f is None:
        log.fail("FeatureCut3 失败", cut=name)
    rename_last_feature(model, log, f"CUT_{name}")


def part(sw, log, out_dir, name, rects, x_span, role, status, parent,
         extra=None, cuts=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.SLDPRT"
    if path.exists():
        log.event("SKIP_EXISTS", part=name)
        return path
    p = S.props(name, role, status, OWNER, S.CLAIM, parent, extra)
    if not cuts:
        build_x_extruded_part(sw, log, path, name, rects, x_span, p)
        return path
    # 需开孔：自建流程（工厂函数不含 cut）
    from b3_lib.sw_part_factory import extrude_checked, yz_rect_to_sketch
    model = new_document(sw, log, "part")
    x_min, x_max = x_span
    create_offset_plane(model, log, RIGHT, x_min, f"PLN_{name}_BASE",
                        flip=x_min < 0)
    for i, r in enumerate(rects):
        model.ClearSelection2(True)
        model.Extension.SelectByID2(f"PLN_{name}_BASE", "PLANE", 0, 0, 0,
                                    False, 0, None, 0)
        sk = model.SketchManager
        sk.InsertSketch(True)
        if len(r) == 3:
            sk.CreateCircleByRadius(_m(-r[1]), _m(r[0]), 0.0, _m(r[2]))
        else:
            sk.CreateCenterRectangle(*yz_rect_to_sketch(*r))
        sk.InsertSketch(True)
        sfx = f"_{i+1}" if len(rects) > 1 else ""
        extrude_checked(model, log, x_max - x_min, "x", x_min, x_max,
                        f"EX_{name}{sfx}", plane_off_mm=x_min)
    for j, (yc, zc, d) in enumerate(cuts):
        cut_circle(model, log, x_max + 5.0, yc, zc, d, x_max - x_min + 10.0,
                   f"{name}_{j+1}")
    set_custom_properties(model, log, p)
    rebuild_or_fail(model, log, name)
    save_as(model, log, path)
    sw.CloseDoc(get_com_member(model, "GetTitle"))
    log.event("PART_BUILT", part=name, path=str(path))
    return path


def cut_rect(model, log, plane_off_mm, yc, zc, hy, hz, depth_mm, name):
    """矩形切除（外板穿板开槽）。基面法向 +X，草图映射同 build_x_extruded_part。"""
    from b3_lib.sw_part_factory import yz_rect_to_sketch
    create_offset_plane(model, log, RIGHT, plane_off_mm, f"PLN_{name}",
                        flip=plane_off_mm < 0)
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(f"PLN_{name}", "PLANE", 0, 0, 0, False,
                                       0, None, 0):
        log.fail("选择开槽基面失败", cut=name)
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreateCenterRectangle(*yz_rect_to_sketch(yc, zc, hy, hz))
    sk.InsertSketch(True)
    f = model.FeatureManager.FeatureCut3(
        True, False, False, 0, 0, _m(depth_mm), 0.0, False, False, False,
        False, 0.0, 0.0, False, False, False, False, False, True, True, True,
        True, False, 0, 0.0, False)
    if f is None:
        log.fail("FeatureCut3(rect) 失败", cut=name)
    rename_last_feature(model, log, f"SLOT_{name}")


def part_y(sw, log, out_dir, name, profiles_xz, y_span, role, status, parent,
           extra=None, cuts=None):
    """沿 Y 挤出的零件。Top 面草图映射实测：(sx,sy) → 全局 (X=sx, Z=-sy)；
    dir=False 沿 +Y。profiles_xz = [(xc,zc,hx,hz) 矩形 | (xc,zc,r) 圆]。"""
    from b3_lib.sw_part_factory import extrude_checked
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.SLDPRT"
    if path.exists():
        log.event("SKIP_EXISTS", part=name)
        return path
    y_min, y_max = min(y_span), max(y_span)
    model = new_document(sw, log, "part")
    create_offset_plane(model, log, TOP, y_min, f"PLN_{name}_BASE",
                        flip=y_min < 0)
    for i, p in enumerate(profiles_xz):
        model.ClearSelection2(True)
        model.Extension.SelectByID2(f"PLN_{name}_BASE", "PLANE", 0, 0, 0,
                                    False, 0, None, 0)
        sk = model.SketchManager
        sk.InsertSketch(True)
        if len(p) == 3:
            sk.CreateCircleByRadius(_m(p[0]), _m(-p[1]), 0.0, _m(p[2]))
        else:
            xc, zc, hx, hz = p
            sk.CreateCenterRectangle(_m(xc), _m(-zc), 0.0,
                                     _m(xc + hx), _m(-zc + hz), 0.0)
        sk.InsertSketch(True)
        sfx = f"_{i+1}" if len(profiles_xz) > 1 else ""
        extrude_checked(model, log, y_max - y_min, "y", y_min, y_max,
                        f"EY_{name}{sfx}", plane_off_mm=y_min)
    set_custom_properties(model, log, S.props(name, role, status, OWNER,
                                               S.CLAIM, parent, extra))
    rebuild_or_fail(model, log, name)
    save_as(model, log, path)
    sw.CloseDoc(get_com_member(model, "GetTitle"))
    log.event("PART_BUILT", part=name, path=str(path))
    return path


def assembly(sw, log, path: Path, members, role, status, parent, extra=None):
    if path.exists():
        log.event("SKIP_EXISTS", asm=path.name)
        return path
    m = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, m, members)
    set_custom_properties(m, log, S.props(path.stem, role, status, OWNER,
                                           S.CLAIM, parent, extra))
    rebuild_or_fail(m, log, path.stem)
    save_as(m, log, path)
    sw.CloseAllDocuments(True)
    log.event("ASM_BUILT", asm=path.name, members=len(members))
    return path


# ── A. Master Skeleton ──────────────────────────────────────────────────
def stage_A(sw, log):
    d = ROOT / "00_Master_Skeleton"
    d.mkdir(parents=True, exist_ok=True)
    out = d / "00_Master_Skeleton_V2_2.SLDPRT"
    if out.exists():
        log.event("SKIP_EXISTS", part=out.name)
        return out
    m = new_document(sw, log, "part")
    for nm, off in [("STA_X_REAR_END", -183.0), ("STA_X_MID2", -61.0),
                    ("STA_X_MID1", 61.0), ("STA_X_FRONT_TRANS", 122.0),
                    ("STA_X_FRONT_END", 183.0),
                    ("STA_X_MOUNT_FACE", S.MOUNT_FACE_X_DISPLAY)]:
        create_offset_plane(m, log, RIGHT, off, nm, flip=off < 0)
    for nm, off, base in [("PLN_ENV_YP", S.ENV, TOP), ("PLN_ENV_YN", -S.ENV, TOP),
                          ("PLN_LONGERON_YP", S.LONG_C, TOP),
                          ("PLN_LONGERON_YN", -S.LONG_C, TOP),
                          ("PLN_HINGE_YP", S.HINGE_PIN_Y, TOP),
                          ("PLN_HINGE_YN", -S.HINGE_PIN_Y, TOP),
                          ("PLN_ENV_ZP", S.ENV, FRONT), ("PLN_ENV_ZN", -S.ENV, FRONT),
                          ("PLN_LONGERON_ZP", S.LONG_C, FRONT),
                          ("PLN_LONGERON_ZN", -S.LONG_C, FRONT),
                          ("PLN_HINGE_Z", S.HINGE_PIN_Z, FRONT),
                          ("PLN_DECK", S.DECK_Z[0], FRONT)]:
        create_offset_plane(m, log, base, off, nm, flip=off < 0)
    sk = m.SketchManager
    sk.Insert3DSketch(True)
    hx, hy, hz = _m(183.0), _m(S.ENV), _m(S.ENV)
    c = [(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1)
         for sz in (-1, 1)]
    for a, b in [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7),
                 (0, 4), (1, 5), (2, 6), (3, 7)]:
        sk.CreateLine(c[a][0], c[a][1], c[a][2], c[b][0], c[b][1], c[b][2])
    sk.Insert3DSketch(True)
    rename_last_feature(m, log, "SK3D_BUS_ENVELOPE_366x226p3x226p3")
    pr = S.props("00_Master_Skeleton_V2_2", "SKELETON_DATUM_NO_SOLID",
                 "FROZEN_PARAM_CARRIER", OWNER, S.CLAIM, TOP_ASM)
    pr.update({f"PARAM_{k}": str(v) for k, v in {
        "BUS_X_TOTAL": 366.0, "X_FRONT": S.X_FRONT, "X_REAR": S.X_REAR,
        "ENVELOPE_YZ": S.ENV, "PANEL_THICK": S.PANEL_T,
        "LONGERON_CENTER": S.LONG_C, "LONGERON_HALF": S.LONG_H,
        "MOUNT_FACE_X": S.MOUNT_FACE_X_DISPLAY,
        "ADAPTER_PLATE_SIDE": S.ADAPTER_PLATE[0],
        "ADAPTER_PLATE_THICK": S.ADAPTER_PLATE[1],
        "CENTRAL_BORE_D": S.CENTRAL_BORE_D,
        "HINGE_PIN_Y": S.HINGE_PIN_Y, "HINGE_PIN_Z": S.HINGE_PIN_Z,
        "EAR_OUTER_Y": S.EAR_Y[1], "ROOT_BASE_X": str(S.ROOT_BASE_X),
        "PANEL_ROOT_Y": S.PANEL_ROOT_Y, "PANEL_ROOT_Z": S.PANEL_ROOT_Z,
        "CLEARANCE_MIN": 2.0,
        "C5_BUS_AVAILABLE_WIDTH": S.C5_BUS_AVAILABLE_WIDTH,
        "C5_STOWED_PACKAGE_WIDTH": S.C5_STOWED_PACKAGE_WIDTH,
        "C5_OVERAGE": S.C5_OVERAGE,
        "SOLAR_ROOT_MECHANISM_LOWER_BOUND_WIDTH":
            S.SOLAR_ROOT_MECHANISM_LOWER_BOUND_WIDTH,
        "SADDLE_UPPER_ARM_Z": S.SADDLE["UPPER_ARM"][2],
        "SADDLE_FOREARM_Z": S.SADDLE["FOREARM"][2],
        "SADDLE_WRIST_Z": S.SADDLE["WRIST"][2],
    }.items()})
    pr.update(S.UNKNOWNS)
    set_custom_properties(m, log, pr)
    rebuild_or_fail(m, log, "skeleton")
    save_as(m, log, out)
    sw.CloseDoc(get_com_member(m, "GetTitle"))
    log.event("SKELETON_BUILT", planes=18)
    return out


def panel_with_slot(sw, log, out_dir, name, yc, x_span, slot):
    """±Y 外板；slot 非空时开矩形穿板槽（翼根节点脊板让位）。"""
    from b3_lib.sw_part_factory import extrude_checked, yz_rect_to_sketch
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.SLDPRT"
    if path.exists():
        log.event("SKIP_EXISTS", part=name)
        return path
    extra = ({"SLOT_FOR": "SOLAR_ROOT_NODE_SPINE 穿板让位（O9）",
              "SLOT_X": str(slot["x"]), "SLOT_Z": str(slot["z"]),
              "SLOT_CLEARANCE_MM": str(slot["clear"])} if slot else None)
    p = S.props(name, "REMOVABLE_PANEL", "DESIGN_PROPOSAL", OWNER, S.CLAIM,
                "Removable_Panels", extra)
    x_min, x_max = x_span
    model = new_document(sw, log, "part")
    create_offset_plane(model, log, RIGHT, x_min, f"PLN_{name}_BASE",
                        flip=x_min < 0)
    model.ClearSelection2(True)
    model.Extension.SelectByID2(f"PLN_{name}_BASE", "PLANE", 0, 0, 0, False,
                                0, None, 0)
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreateCenterRectangle(*yz_rect_to_sketch(yc, 0.0, S.PANEL_T / 2, S.ENV))
    sk.InsertSketch(True)
    extrude_checked(model, log, x_max - x_min, "x", x_min, x_max,
                    f"EX_{name}", plane_off_mm=x_min)
    if slot:
        c = slot["clear"]
        sx0, sx1 = slot["x"][0] - c, slot["x"][1] + c
        zlo, zhi = slot["z"][0] - c, slot["z"][1] + c
        # FeatureCut3 的 Dir=False 沿 **-X**（与 FeatureExtrusion2 相反，本轮实测：
        # 基面置于 sx0 会把槽开到 X[sx0-len, sx0]）→ 基面须置于槽的 +X 端 sx1
        create_offset_plane(model, log, RIGHT, sx1, f"PLN_{name}_SLOTBASE",
                            flip=sx1 < 0)
        model.ClearSelection2(True)
        model.Extension.SelectByID2(f"PLN_{name}_SLOTBASE", "PLANE", 0, 0, 0,
                                    False, 0, None, 0)
        sk.InsertSketch(True)
        sk.CreateCenterRectangle(*yz_rect_to_sketch(
            yc, (zlo + zhi) / 2, S.PANEL_T, (zhi - zlo) / 2))
        sk.InsertSketch(True)
        f = model.FeatureManager.FeatureCut3(
            True, False, False, 0, 0, _m(sx1 - sx0), 0.0, False, False, False,
            False, 0.0, 0.0, False, False, False, False, False, True, True,
            True, True, False, 0, 0.0, False)
        if f is None:
            log.fail("外板开槽失败", part=name)
        rename_last_feature(model, log, f"SLOT_{name}_ROOT_SPINE")
    set_custom_properties(model, log, p)
    rebuild_or_fail(model, log, name)
    save_as(model, log, path)
    sw.CloseDoc(get_com_member(model, "GetTitle"))
    log.event("PART_BUILT", part=name, path=str(path))
    return path


# ── B. Primary Structure ────────────────────────────────────────────────
def stage_B(sw, log):
    base = ROOT / "01_Primary_Structure"
    pd = base / "parts"
    P = "01_Primary_Structure_V2_2"
    frames = [("Front_End_Frame", S.STA["FRONT_END"]),
              ("Rear_End_Frame", S.STA["REAR_END"]),
              ("Front_Transverse_Frame", S.STA["FRONT_TRANS"]),
              ("Mid_Transverse_Frame_1", S.STA["MID1"]),
              ("Mid_Transverse_Frame_2", S.STA["MID2"])]
    members = []
    for nm, span in frames:
        members.append(part(sw, log, pd, nm, S.ring_rects(), span,
                             "PRIMARY_STRUCTURE_RING_FRAME", "DESIGN_PROPOSAL", P))
    members.append(part(sw, log, pd, "Longerons_4X", S.longeron_rects(),
                         (S.X_REAR, S.X_FRONT), "PRIMARY_STRUCTURE_LONGERON",
                         "DESIGN_PROPOSAL", P))
    # 设备甲板（三舱）
    dd = base / "Equipment_Decks/parts"
    deck_rect = [(0.0, (S.DECK_Z[0] + S.DECK_Z[1]) / 2, S.RAIL_IN,
                  (S.DECK_Z[1] - S.DECK_Z[0]) / 2)]
    decks = [("Deck_Front_Bay", (64.0, 119.0)), ("Deck_Mid_Bay", (-58.0, 58.0)),
             ("Deck_Rear_Bay", (-175.0, -64.0))]
    dm = [part(sw, log, dd, nm, deck_rect, span, "EQUIPMENT_DECK",
                "DESIGN_PROPOSAL", "Equipment_Decks") for nm, span in decks]
    decks_asm = assembly(sw, log, base / "Equipment_Decks/Equipment_Decks.SLDASM",
                          dm, "EQUIPMENT_DECK_GROUP", "DESIGN_PROPOSAL", P)
    # 可拆外板（±Y 前后分缝 + ±Z）
    pp = base / "Removable_Panels/parts"
    yo = S.ENV - S.PANEL_T / 2
    pnls = []
    for sy, tag in ((1, "PY"), (-1, "NY")):
        for x0, x1, half in ((0.0, 183.0, "Front"), (-183.0, 0.0, "Rear")):
            # 后段板须为翼根节点脊板让位（O9：脊板 Y 从 110.15 穿到 121.15）
            slot = None
            if half == "Rear":
                slot = {"x": S.ROOT_SPINE_X, "z": S.ROOT_SPINE_Z, "clear": 1.0}
            pnls.append(panel_with_slot(sw, log, pp, f"Panel_{tag}_{half}",
                                         sy * yo, (x0, x1), slot))
    for sz, tag in ((1, "PZ"), (-1, "NZ")):
        pnls.append(part(sw, log, pp, f"Panel_{tag}",
                          [(0.0, sz * yo, S.SKIN_IN, S.PANEL_T / 2)],
                          (S.X_REAR, S.X_FRONT), "REMOVABLE_PANEL",
                          "DESIGN_PROPOSAL", "Removable_Panels"))
    assembly(sw, log, base / "Removable_Panels/Removable_Panels.SLDASM",
             pnls, "REMOVABLE_PANEL_GROUP", "DESIGN_PROPOSAL", TOP_ASM,
             extra={"DEVIATION": "D-NATIVE-01：外板组不嵌入 01_Primary_Structure，"
                                  "而作为顶层组件——子装配子件的配置级抑制在本机"
                                  "不可持久（V2.2 两次复现），MAINTENANCE 态要求"
                                  "外板可抑制。装配树层级偏离任务书示意树，语义不变"})
    # D-NATIVE-01：外板不进入 01（否则与顶层那份重复装入，抑制失效且重合件掩盖干涉）
    return assembly(sw, log, base / f"{P}.SLDASM", members + [decks_asm],
                     "PRIMARY_STRUCTURE", "DESIGN_PROPOSAL", TOP_ASM,
                     extra={"DEVIATION": "D-NATIVE-01 见 Removable_Panels 装配属性"})


# ── C. B601 Mount and Load Path ─────────────────────────────────────────
def stage_C(sw, log):
    base = ROOT / "02_B601_Mount_and_Load_Path"
    pd = base / "parts"
    P = "02_B601_Mount_and_Load_Path"
    bore = S.CENTRAL_BORE_D
    mem = []
    # 扩散板缩至纵梁内净空 ±93.15（原 ±105 与四纵梁互穿 4 处，已修）
    mem.append(part(sw, log, pd, "Load_Spreading_Frame",
                     [(0.0, 0.0, S.RAIL_IN, S.RAIL_IN)],
                     (171.0, 175.0), "LOAD_SPREADER", "DESIGN_PROPOSAL", P,
                     cuts=[(0.0, 0.0, bore)]))
    mem.append(part(sw, log, pd, "Spacecraft_Flange", [(0.0, 0.0, 75.0)],
                     (183.0, 186.0), "SPACECRAFT_SIDE_FLANGE", "DESIGN_PROPOSAL",
                     P, cuts=[(0.0, 0.0, bore)]))
    mem.append(part(sw, log, pd, "Adapter_Plate",
                     [(0.0, 0.0, S.ADAPTER_PLATE[0] / 2, S.ADAPTER_PLATE[0] / 2)],
                     (186.0, S.MOUNT_FACE_X_DISPLAY), "B601_ADAPTER_PLATE",
                     "DESIGN_PROPOSAL", P, cuts=[(0.0, 0.0, bore)],
                     extra={"INTERFACE": "160x160x12; central bore D100"}))
    mem.append(part(sw, log, pd, "Central_Boss", [(0.0, 0.0, 55.0)],
                     (S.MOUNT_FACE_X_DISPLAY, 208.0), "PILOT_BOSS",
                     "DESIGN_PROPOSAL", P, cuts=[(0.0, 0.0, bore)]))
    for sy, tag in ((1, "Left"), (-1, "Right")):
        mem.append(part(sw, log, pd, f"Load_Bridge_{tag}",
                         [(sy * 80.0, 0.0, 12.0, 15.0)], (64.0, 171.0),
                         "LOAD_PATH_BRIDGE", "DESIGN_PROPOSAL", P))
    mem.append(part(sw, log, pd, "Harness_Passage", [(0.0, -70.0, 30.0, 12.0)],
                     (64.0, 171.0), "HARNESS_PASSAGE_DUCT", "DESIGN_PROPOSAL", P))
    # X 起点 100→126：避开前横框（119..125），原互穿 2160mm³ 已修
    mem.append(part(sw, log, pd, "Maintenance_Access_Cover",
                     [(0.0, -108.65, 60.0, 1.5)], (126.0, 170.0),
                     "MAINTENANCE_COVER_INNER", "DESIGN_PROPOSAL", P))
    return assembly(sw, log, base / f"{P}.SLDASM", mem, "B601_MOUNT_LOAD_PATH",
                     "DESIGN_PROPOSAL", TOP_ASM,
                     extra={"T_SM_TRACK_CONFLICT": S.UNKNOWNS["T_SM_TRACK_CONFLICT"]})


# ── D. ARM STOW SUPPORT ─────────────────────────────────────────────────
def stage_D(sw, log):
    """O13 返工：鞍座按 v3 收拢向量的精确支承站位重建（塔高全部 ≤150mm）。"""
    base = ROOT / "04_ARM_STOW_SUPPORT"
    pd = base / "parts"
    P = "04_ARM_STOW_SUPPORT"
    mem = []
    st = json.loads((ROOT / "design/o13_saddle_stations.json")
                    .read_text(encoding="utf-8"))
    names = {"AFT": "Aft_Saddle", "MID": "Mid_Saddle", "FWD": "Fwd_Saddle"}
    for s in st["selected_saddles"]:
        nm = names[s["tag"]]
        x0, x1 = s["x_window"]
        yc = max(-60.0, min(60.0, round(sum(s["y_range"]) / 2, 2)))
        z_pad_top = s["contact_z"]
        tower_h = z_pad_top - 3.0 - S.ENV
        rects = [(yc, S.ENV + tower_h / 2, 26.0, tower_h / 2),   # 塔
                 (yc, z_pad_top - 1.5, 30.0, 1.5)]                # 接触垫
        mem.append(part(sw, log, pd, nm, rects, (x0, x1), "ARM_STOW_SADDLE",
                         "CANDIDATE_HOLD", P,
                         extra={"CONTACT_Z_SOURCE": "O13 v3 位形精确顶点实测",
                                "TOWER_H_MM": str(round(tower_h, 2)),
                                "TOWER_LIMIT_MM": "150",
                                "STOW_VECTOR": "b601_stow_joint_vector_v3.json",
                                "CONTACT_QUALIFICATION": "HOLD"}))
    mem.append(part(sw, log, pd, "Launch_Lock_Interface_Reference",
                     [(-70.0, 150.0, 14.0, 18.0), (70.0, 150.0, 14.0, 18.0)],
                     (-10.0, 10.0), "LAUNCH_LOCK_INTERFACE_REF",
                     "REFERENCE_TBD", P,
                     extra={"HDRM_TYPE": "TBD", "PRELOAD": "TBD"}))
    # 下沿抬到 z=256（各鞍座垫顶最高 253.8 之上）——原 245 与鞍座互穿，已修
    S.SADDLE = {s["tag"]: (s["x_window"][0], s["x_window"][1], s["contact_z"],
                            s["y_range"][0], s["y_range"][1])
                for s in st["selected_saddles"]}
    # 下沿须高于最高鞍座垫顶（v3: Aft 261.08）；原 256 被 Aft_Saddle 顶穿 5763mm³
    z_lo = max(s["contact_z"] for s in st["selected_saddles"]) + 3.0
    mem.append(part(sw, log, pd, "Release_Clearance_Envelope",
                     [(20.0, (z_lo + 354.0) / 2, 90.0, (354.0 - z_lo) / 2)],
                     (-110.0, 70.0),
                     "RELEASE_CLEARANCE_ENVELOPE_NON_PHYSICAL", "REFERENCE_TBD", P,
                     extra={"CLASS": "NON_PHYSICAL_ENVELOPE",
                            "Z_LOWER_MM": str(round(z_lo, 2)),
                            "RELEASE_DIRECTION": "+Z then -X retract (proposal)"}))
    return assembly(sw, log, base / f"{P}.SLDASM", mem, "ARM_STOW_SUPPORT",
                     "CANDIDATE_HOLD", TOP_ASM,
                     extra={"COMPARATOR_NOTE": "STOW_NO_CLOCK_COMPARATOR 的鞍座"
                                                "尚未设计；该配置下本子装配抑制"})


# ── E. Solar Array Root Mechanism (L/R) ─────────────────────────────────
def stage_E(sw, log):
    """O9 返工：按 Codex 100_Mechanical_Continuation / SOURCE_B5 外挂式几何重建。"""
    out = []
    for sy, side, num in ((1, "Left", "05"), (-1, "Right", "06")):
        base = ROOT / f"{num}_Solar_Array_Root_{side}"
        pd = base / "parts"
        P = f"{num}_Solar_Array_Root_{side}"
        pin_y, pin_z = sy * S.HINGE_PIN_Y, S.HINGE_PIN_Z
        codex = {"SOURCE": "Codex 100_Mechanical_Continuation SOLAR-ROOT-01 / SOURCE_B5",
                 "RECONCILIATION": "O9 站位返工（原 X[126,174] 内置版本作废）"}
        mem = []

        def yc_hy(pair):
            return sy * (pair[0] + pair[1]) / 2, (pair[1] - pair[0]) / 2

        yb, hb = yc_hy(S.ROOT_BASE_Y)
        mem.append(part(sw, log, pd, f"Root_Base_{side}",
                         [(yb, sum(S.ROOT_BASE_Z) / 2, hb,
                           (S.ROOT_BASE_Z[1] - S.ROOT_BASE_Z[0]) / 2)],
                         S.ROOT_BASE_X, "SOLAR_ROOT_BASE_OUTBOARD",
                         "DESIGN_PROPOSAL", P, extra=codex))
        ys, hs = yc_hy(S.ROOT_SPINE_Y)
        mem.append(part(sw, log, pd, f"Root_Node_Spine_{side}",
                         [(ys, 0.0, hs,
                           (S.ROOT_SPINE_Z[1] - S.ROOT_SPINE_Z[0]) / 2)],
                         S.ROOT_SPINE_X, "SOLAR_ROOT_NODE_SPINE_STAGING",
                         "DESIGN_PROPOSAL", P,
                         extra={**codex,
                                "EMBEDDED_NOTE": "Codex 故意嵌入式桥接；本轮改为"
                                                  "外板开槽让位，功能保留、零干涉"}))
        ye, he = yc_hy(S.EAR_Y)
        for i, ex in enumerate(S.EAR_X, 1):
            mem.append(part(sw, log, pd, f"Hinge_Ear_{i}_{side}",
                             [(ye, 0.0, he, S.EAR_HALF_T)], ex,
                             "SOLAR_HINGE_EAR", "DESIGN_PROPOSAL", P,
                             cuts=[(pin_y, pin_z, S.HINGE_BORE_D)], extra=codex))
        # 单根通销贯穿双耳（Codex 建两段销，X 区间重叠 301.6mm³ 为源显示伪影）
        pin_x = (sum(S.EAR_X[0]) / 2 - S.HINGE_PIN_LEN / 2,
                 sum(S.EAR_X[1]) / 2 + S.HINGE_PIN_LEN / 2)
        mem.append(part(sw, log, pd, f"Hinge_Pin_{side}",
                         [(pin_y, pin_z, S.HINGE_PIN_R)], pin_x,
                         "SOLAR_HINGE_PIN_THROUGH_BOTH_EARS", "REFERENCE_TBD", P,
                         extra={**codex, "PIN_SPEC": "ICD_PENDING",
                                "DEVIATION": "合并为单根通销（Codex 两段销 X 重叠）"}))
        # 扭簧：置于耳对两侧外档（Codex 原 X 位与耳2 重叠，本轮外移并开孔穿销）
        for i, sx0 in enumerate(((S.EAR_X[0][0] - 18.0), (S.EAR_X[1][1] + 0.0)), 1):
            mem.append(part(sw, log, pd, f"Torsion_Spring_{i}_{side}",
                             [(pin_y, pin_z, S.SPRING_R)],
                             (sx0, sx0 + S.SPRING_LEN),
                             "SOLAR_HINGE_TORSION_SPRING_ENVELOPE", "REFERENCE_TBD",
                             P, cuts=[(pin_y, pin_z, S.HINGE_BORE_D)],
                             extra={**codex, "STIFFNESS": "UNKNOWN",
                                    "DEVIATION": "X 位外移（Codex 原位与耳2 实体重叠）"}))
        yh, hh = yc_hy(S.HDRM_BASE_Y)
        for i, xc in enumerate(S.HDRM_STATIONS_X, 1):
            mem.append(part(sw, log, pd, f"HDRM_Base_{i}_{side}",
                             [(yh, S.HDRM_BASE_ZC, hh, S.HDRM_BASE_HALF)],
                             (xc - S.HDRM_BASE_HALF, xc + S.HDRM_BASE_HALF),
                             "SOLAR_HDRM_BASE", "DESIGN_PROPOSAL", P,
                             extra={**codex, "RELEASE_MECHANISM": "ICD_PENDING"}))
            mem.append(part_y(sw, log, pd, f"HDRM_Rod_{i}_{side}",
                               [(xc, S.HDRM_BASE_ZC, S.HDRM_ROD_R)],
                               (sy * S.HDRM_ROD_Y[0], sy * S.HDRM_ROD_Y[1]),
                               "SOLAR_HDRM_ROD", "REFERENCE_TBD", P,
                               extra={**codex, "RELEASE_RELIABILITY": "UNKNOWN",
                                      "AXIS": "Y（径向）"}))
        yhs, hhs = yc_hy(S.HARD_STOP_Y)
        mem.append(part(sw, log, pd, f"Hard_Stop_{side}",
                         [(yhs, S.HARD_STOP_ZC, hhs, S.HARD_STOP_HALF)],
                         S.HARD_STOP_X, "SOLAR_HINGE_HARD_STOP",
                         "DESIGN_PROPOSAL", P,
                         extra={**codex, "STOP_LOAD": "UNKNOWN"}))
        mem.append(part(sw, log, pd, f"Harness_Service_Loop_{side}",
                         [(sy * 122.15, -20.0, 9.0, 10.0)], (-110.0, -90.0),
                         "SOLAR_HARNESS_SERVICE_LOOP_ENVELOPE", "REFERENCE_TBD", P,
                         extra={**codex, "CLASS": "NON_PHYSICAL_ENVELOPE",
                                "BEND_RADIUS": "TBD"}))
        out.append(assembly(sw, log, base / f"{P}.SLDASM", mem,
                             "SOLAR_ARRAY_ROOT_MECHANISM", "DESIGN_PROPOSAL",
                             TOP_ASM,
                             extra={**codex,
                                    "C5_NEGATIVE": S.UNKNOWNS["C5_PACKAGE_NEGATIVE"],
                                    "WIDTH_NEGATIVE":
                                        S.UNKNOWNS["SOLAR_ROOT_WIDTH_NEGATIVE"]}))
    return out


def _stage_E_old_unused(sw, log):
    out = []
    for sy, side, num in ((1, "Left", "05"), (-1, "Right", "06")):
        base = ROOT / f"{num}_Solar_Array_Root_{side}"
        pd = base / "parts"
        P = f"{num}_Solar_Array_Root_{side}"
        y = sy * 76.0
        z = -105.15
        mem = []
        # 层次（修 8+4+2+2 处互穿）：SC 支座板 z[-100.15,-93.15] 贴纵梁内侧 y≤93.15；
        # 铰链耳/叶片挂在其下 z[-110.15,-100.15]、y[64,88] 让开纵梁；销穿孔不干涉
        mem.append(part(sw, log, pd, f"Root_Bracket_Spacecraft_{side}",
                         [(sy * 76.575, -96.65, 16.575, 3.5)], (126.0, 174.0),
                         "SOLAR_ROOT_BRACKET_SC_SIDE", "DESIGN_PROPOSAL", P))
        for tag, span in (("Fwd", S.HINGE_X["EAR_FWD"]),
                          ("Aft", S.HINGE_X["EAR_AFT"])):
            mem.append(part(sw, log, pd, f"Hinge_Ear_{tag}_{side}",
                             [(y, z, 12.0, 5.0)], span, "SOLAR_HINGE_EAR",
                             "DESIGN_PROPOSAL", P,
                             cuts=[(y, z, S.HINGE_BORE_D)]))
        mem.append(part(sw, log, pd, f"Hinge_Pin_Envelope_{side}",
                         [(y, z, S.HINGE_PIN_R)], S.HINGE_X["PIN"],
                         "SOLAR_HINGE_PIN_ENVELOPE", "REFERENCE_TBD", P,
                         extra={"PIN_DIAMETER": "TBD (envelope D8, bore D8.4)",
                                "MATERIAL": "TBD"}))
        mem.append(part(sw, log, pd, f"Root_Bracket_Panel_{side}",
                         [(y, z, 11.0, 5.0)], S.HINGE_X["BLADE"],
                         "SOLAR_ROOT_BRACKET_PANEL_SIDE", "DESIGN_PROPOSAL", P,
                         cuts=[(y, z, S.HINGE_BORE_D)],
                         extra={"PANEL_ROOT_Y_TARGET": str(S.PANEL_ROOT_Y),
                                "ARM_TO_PANEL_ROOT": "TBD（翼板本体不在第一阶段）"}))
        mem.append(part(sw, log, pd, f"Mechanical_Stop_{side}",
                         [(sy * 54.0, -96.65, 6.0, 3.5)], (144.0, 156.0),
                         "SOLAR_HINGE_MECHANICAL_STOP", "DESIGN_PROPOSAL", P,
                         extra={"STOP_ANGLE": "TBD"}))
        mem.append(part(sw, log, pd, f"HDRM_Seat_{side}",
                         [(sy * 60.0, -104.0, 14.0, 6.0)], (-20.0, 8.0),
                         "SOLAR_HDRM_SEAT", "DESIGN_PROPOSAL", P,
                         extra={"HDRM_TYPE": "TBD", "PRELOAD": "TBD"}))
        mem.append(part(sw, log, pd, f"Release_Mechanism_Envelope_{side}",
                         [(sy * 60.0, -86.0, 18.0, 12.0)], (-24.0, 12.0),
                         "SOLAR_RELEASE_MECHANISM_ENVELOPE_NON_PHYSICAL",
                         "REFERENCE_TBD", P, extra={"CLASS": "NON_PHYSICAL_ENVELOPE"}))
        mem.append(part(sw, log, pd, f"Harness_Service_Loop_{side}",
                         [(sy * 74.0, -84.0, 10.0, 8.0)], (100.0, 118.0),
                         "SOLAR_HARNESS_SERVICE_LOOP_ENVELOPE", "REFERENCE_TBD",
                         P, extra={"CLASS": "NON_PHYSICAL_ENVELOPE",
                                    "STRAIN_RELIEF": "TBD"}))
        out.append(assembly(sw, log, base / f"{P}.SLDASM", mem,
                             "SOLAR_ARRAY_ROOT_MECHANISM", "DESIGN_PROPOSAL",
                             TOP_ASM))
    return out


# ── F. Top Assembly + configurations ────────────────────────────────────
CONFIGS = ["STOWED", "DEPLOYED_NOMINAL", "DEPLOY_FAILED_BOTH", "L_FAIL",
           "R_FAIL", "PARTIAL_DEPLOYMENT", "MAINTENANCE",
           "STOW_VENDOR_25DEG_PROPOSAL", "STOW_NO_CLOCK_COMPARATOR"]
SUP_SUPPRESSED, SUP_RESOLVED = 0, 2     # swComponentSuppressionState_e（实测）
SUPPRESS = {   # config -> 需抑制的顶层组件（其余解析）
    "MAINTENANCE": ["Removable_Panels"],
    "STOW_NO_CLOCK_COMPARATOR": ["04_ARM_STOW_SUPPORT"],
}


def stage_F(sw, log):
    asm_dir = ROOT / "Assembly"
    asm_dir.mkdir(parents=True, exist_ok=True)
    path = asm_dir / f"{TOP_ASM}.SLDASM"
    if path.exists():
        log.event("SKIP_EXISTS", asm=path.name)
        return path
    members = [ROOT / "00_Master_Skeleton/00_Master_Skeleton_V2_2.SLDPRT",
               ROOT / "01_Primary_Structure/01_Primary_Structure_V2_2.SLDASM",
               ROOT / "01_Primary_Structure/Removable_Panels/Removable_Panels.SLDASM",
               ROOT / "02_B601_Mount_and_Load_Path/02_B601_Mount_and_Load_Path.SLDASM",
               ROOT / "04_ARM_STOW_SUPPORT/04_ARM_STOW_SUPPORT.SLDASM",
               ROOT / "05_Solar_Array_Root_Left/05_Solar_Array_Root_Left.SLDASM",
               ROOT / "06_Solar_Array_Root_Right/06_Solar_Array_Root_Right.SLDASM"]
    for p in members:
        if not p.exists():
            log.fail("顶装缺件", missing=str(p))
    m = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, m, members)
    cfg = m.ConfigurationManager
    for cname in CONFIGS:
        if cname == "STOWED":
            act = cast(m, "IModelDoc2").ConfigurationManager.ActiveConfiguration
            act.Name = "STOWED"
            continue
        if cfg.AddConfiguration2(cname, "", "", 0, "", False, False) is None:
            log.fail("AddConfiguration2 失败", config=cname)
    asm = cast(m, "IAssemblyDoc")
    for cname in CONFIGS:
        m.ShowConfiguration2(cname)
        if cast(m, "IModelDoc2").ConfigurationManager.ActiveConfiguration.Name != cname:
            log.fail("配置激活读回失败", config=cname)
        for c in asm.GetComponents(True):
            c2 = cast(c, "IComponent2")
            stem = Path(get_com_member(c2, "GetPathName")).stem
            want_sup = any(stem == s for s in SUPPRESS.get(cname, []))
            # swComponentSuppressionState_e 实测：0=Suppressed，2=FullyResolved
            # （用反会把整装配抑制成空——本轮已复现，见 D-NATIVE-03）
            c2.SetSuppression2(SUP_SUPPRESSED if want_sup else SUP_RESOLVED)
        rebuild_or_fail(m, log, f"config_{cname}")
    m.ShowConfiguration2("STOWED")
    set_custom_properties(m, log, S.props(TOP_ASM, "TOP_LEVEL_SPACECRAFT",
                                           "PHASE1_NATIVE_BUILT", OWNER, S.CLAIM,
                                           "NONE", extra=S.UNKNOWNS))
    rebuild_or_fail(m, log, "top")
    save_as(m, log, path)
    sw.CloseAllDocuments(True)
    log.event("TOP_ASM_BUILT", configs=len(CONFIGS))
    return path


STAGES = {"A": stage_A, "B": stage_B, "C": stage_C, "D": stage_D, "E": stage_E,
          "F": stage_F}


def main():
    which = (sys.argv[1] if len(sys.argv) > 1 else "ALL").upper()
    log = BuildLog(f"native01_{which}")
    sw = connect(log)
    try:
        for k in (STAGES if which == "ALL" else [which]):
            print(f"--- stage {k} ---")
            STAGES[k](sw, log)
            print(f"--- stage {k} done ---")
    finally:
        try:
            sw.CloseAllDocuments(True)
        except Exception:
            pass
    print("OK", which)


if __name__ == "__main__":
    main()
