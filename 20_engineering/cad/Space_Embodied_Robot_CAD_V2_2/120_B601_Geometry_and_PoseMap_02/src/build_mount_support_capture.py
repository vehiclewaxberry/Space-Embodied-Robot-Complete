"""POSEMAP-02 S4：安装模块 / 收拢支承模块 / 捕获头候选（STEP-first）。

- 安装模块：Adapter_Ring + Interface_Plate_160x160x12 + Central_D100 +
  Reinforced_Base_Carrier + Front_Spreader + Four_Load_Bridges + Gussets +
  线束/连接器预留（NON_PHYSICAL keepout，单独实体标注）。
- 收拢支承：上纵梁横梁 ×2 + 主鞍座（X+40..+90）+ 腕鞍座（X-150..-110）+
  HDRM×4 + 接触垫；鞍座高度/横向偏置由 LOD2 STOW 臂实体 bbox 实测导出
  （非种子 z=145——见 stow JSON saddle_height_implication）。
  三点发射支承 = 安装法兰 + 主鞍座 + 腕鞍座。
- 捕获头候选：与 B601 夹爪互斥（EE 二选一）；独立模块 STEP（局部原点）。
- 所有接触资格 = STOW_CONTACT_QUALIFICATION=HOLD（无强度/刚度权威）。
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from build123d import (Box, Color, Compound, Cylinder, Location, Plane, Pos,
                       Rot, Vector, export_step)

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "src"))
from build_lod2_arm import build_arm, fk_frames
from urdf_frame_map_and_stow_fit import parse_chain

NOW = datetime.now(timezone.utc).isoformat()

# 冻结平台参数（V2.2 显示轨）
PLAT_X, PLAT_Y, PLAT_ZTOP = 183.0, 113.15, 113.15
LONGERON_Y = 105.65          # 上纵梁 ±Y
MOUNT_X = 198.0              # B601 安装面（显示轨）
COL_STRUCT = Color(0.28, 0.34, 0.42, 1.0)
COL_SADDLE = Color(0.86, 0.48, 0.14, 1.0)
COL_HDRM = Color(0.75, 0.15, 0.15, 1.0)
COL_PAD = Color(0.15, 0.65, 0.35, 1.0)
COL_RES = Color(0.80, 0.20, 0.75, 0.45)   # NON_PHYSICAL 预留
COL_CAP = Color(0.20, 0.55, 0.85, 1.0)


def _lab(s, color, label):
    s.color, s.label = color, label
    return s


def arm_underside(solids, x_lo, x_hi, clamp_labels):
    """STOW 臂在 X 窗口内的接触实测：只夹持 clamp_labels 指定主承力件；
    共窗其余件登记为非夹持净空件（鞍座钳口须避开）。"""
    zmin, ylo, yhi, hit, bystander = None, None, None, [], []
    for s in solids:
        if s.label.split("_")[0] in ("G1", "G2", "G3"):
            continue
        bb = s.bounding_box()
        if bb.max.X < x_lo or bb.min.X > x_hi:
            continue
        if not any(s.label.startswith(p) for p in clamp_labels):
            bystander.append(s.label)
            continue
        hit.append(s.label)
        zmin = bb.min.Z if zmin is None else min(zmin, bb.min.Z)
        ylo = bb.min.Y if ylo is None else min(ylo, bb.min.Y)
        yhi = bb.max.Y if yhi is None else max(yhi, bb.max.Y)
    return {"z_bottom_mm": round(float(zmin), 2), "y_min_mm": round(float(ylo), 2),
            "y_max_mm": round(float(yhi), 2), "supported_labels": hit,
            "unclamped_bystanders_in_window": bystander}


def build_mount():
    """安装模块（CS_S 世界坐标；安装面 X=198 显示轨）。"""
    s = []
    # 接口板 160×160×12：X 186..198
    s.append(_lab(Plane(origin=Vector(192.0, 0, 0), z_dir=Vector(1, 0, 0),
                        x_dir=Vector(0, 1, 0)).location * Box(160, 160, 12),
                  COL_STRUCT, "MNT_INTERFACE_PLATE_160x160x12"))
    # 适配环：Φ130/内 Φ100（Central_D100 通道以内外环表达）
    ring = Plane(origin=Vector(184.0, 0, 0), z_dir=Vector(1, 0, 0)).location * \
        (Cylinder(65.0, 8.0) - Cylinder(50.0, 10.0))
    s.append(_lab(ring, COL_STRUCT, "MNT_ADAPTER_RING_D130_D100"))
    # 加强基座载体：舱内 X 150..180，190×190×30 背板
    s.append(_lab(Plane(origin=Vector(165.0, 0, 0), z_dir=Vector(1, 0, 0),
                        x_dir=Vector(0, 1, 0)).location * Box(190, 190, 30),
                  COL_STRUCT, "MNT_REINFORCED_BASE_CARRIER"))
    # 前扩载板：X=180..183 面板内衬 210×210×3
    s.append(_lab(Plane(origin=Vector(181.5, 0, 0), z_dir=Vector(1, 0, 0),
                        x_dir=Vector(0, 1, 0)).location * Box(210, 210, 3),
                  COL_STRUCT, "MNT_FRONT_SPREADER"))
    # 四载荷桥：从载体角到 ±Y 纵梁（沿 Y 的梁，20×20）
    for sy in (1, -1):
        for sz in (1, -1):
            p1 = np.array([165.0, sy * 95.0, sz * 95.0])
            p2 = np.array([165.0, sy * LONGERON_Y, sz * 95.0])
            L = abs(p2[1] - p1[1]) + 14.0
            b = Plane(origin=Vector(165.0, (p1[1] + p2[1]) / 2, sz * 95.0),
                      z_dir=Vector(0, sy, 0), x_dir=Vector(1, 0, 0)).location * \
                Box(24, 24, L)
            s.append(_lab(b, COL_STRUCT, f"MNT_LOAD_BRIDGE_{'P' if sy>0 else 'N'}{'U' if sz>0 else 'D'}"))
    # 角撑（gussets）：接口板背面四角 45° 楔（LOD2 以斜置箱体表达）
    for sy in (1, -1):
        for sz in (1, -1):
            g = (Pos(178.0, sy * 70.0, sz * 70.0) *
                 Rot(0, 45 if sz > 0 else -45, 0) * Box(26, 14, 26))
            s.append(_lab(g, COL_STRUCT, f"MNT_GUSSET_{'P' if sy>0 else 'N'}{'U' if sz>0 else 'D'}"))
    # 线束+连接器预留（NON_PHYSICAL）：接口板下方 -Z 侧
    s.append(_lab(Pos(188.0, 0, -95.0) * Box(24, 80, 40), COL_RES,
                  "MNT_HARNESS_CONNECTOR_RESERVATION_NON_PHYSICAL"))
    return s


def build_support(main_c, wrist_c):
    """收拢支承（世界坐标）。main_c/wrist_c = arm_underside 实测。"""
    s = []
    beams = {"MAIN": (40.0, 90.0, main_c), "WRIST": (-150.0, -110.0, wrist_c)}
    for tag, (x_lo, x_hi, c) in beams.items():
        xm = (x_lo + x_hi) / 2.0
        bw = x_hi - x_lo
        # 上纵梁横梁：跨 ±105.65，30 高、bw 宽，顶面 = 平台顶
        s.append(_lab(Plane(origin=Vector(xm, 0, PLAT_ZTOP - 15.0),
                            z_dir=Vector(0, 0, 1), x_dir=Vector(1, 0, 0)).location *
                      Box(bw, 2 * LONGERON_Y, 30), COL_STRUCT,
                      f"SUP_{tag}_CROSSBEAM"))
        # 鞍座塔：从横梁顶到臂底下 3mm（垫厚），塔在实测 Y 中心
        yc = (c["y_min_mm"] + c["y_max_mm"]) / 2.0
        z_pad_top = c["z_bottom_mm"]
        tower_h = z_pad_top - 3.0 - PLAT_ZTOP
        s.append(_lab(Plane(origin=Vector(xm, yc, PLAT_ZTOP + tower_h / 2.0),
                            z_dir=Vector(0, 0, 1), x_dir=Vector(1, 0, 0)).location *
                      Box(bw, 46, tower_h), COL_SADDLE, f"SUP_{tag}_SADDLE_TOWER"))
        # 鞍座 U 形侧墙 ×2：钳口按 ±113.15 支承包络裁剪；裁后 <3mm 弃用→顶部绑带 HOLD
        grip_w = (c["y_max_mm"] - c["y_min_mm"]) + 6.0
        for sy in (1, -1):
            inner = yc + sy * (grip_w / 2.0 + 2.0)
            outer = inner + sy * 8.0
            if sy > 0:
                outer = min(outer, PLAT_Y)
            else:
                outer = max(outer, -PLAT_Y)
            th = abs(outer - inner)
            if th < 3.0:
                c.setdefault("jaw_notes", []).append(
                    f"{tag}_{'P' if sy>0 else 'N'}: 钳口被 ±113.15 包络裁剪至 "
                    f"{th:.1f}mm<3mm，弃用；以顶部绑带替代（HOLD）")
                continue
            s.append(_lab(Pos(xm, (inner + outer) / 2.0, z_pad_top + 14.0) *
                          Box(bw, th, 40), COL_SADDLE,
                          f"SUP_{tag}_JAW_{'P' if sy>0 else 'N'}"))
        # 接触垫（3mm，STOW_CONTACT_QUALIFICATION=HOLD）
        s.append(_lab(Pos(xm, yc, z_pad_top - 1.5) * Box(bw, grip_w, 3),
                      COL_PAD, f"SUP_{tag}_CONTACT_PAD_HOLD"))
        # HDRM ×2 / 鞍座（Φ16×36 竖直，位于鞍座 X 两端外沿）
        for sx in (1, -1):
            h = Plane(origin=Vector(xm + sx * (bw / 2.0 + 12.0), yc,
                                    z_pad_top - 8.0),
                      z_dir=Vector(0, 0, 1)).location * Cylinder(8.0, 36.0)
            s.append(_lab(h, COL_HDRM, f"SUP_{tag}_HDRM_{'F' if sx>0 else 'A'}"))
    return s


def build_capture_head():
    """捕获头候选（局部原点，+Z 为接近轴；与 B601 夹爪互斥）。"""
    s = []
    s.append(_lab(Plane.XY.location * (Cylinder(60.0, 15.0) - Cylinder(30.0, 16.0)),
                  COL_CAP, "CAP_INTERFACE_RING_D120"))
    s.append(_lab(Pos(0, 0, 47.5) * (Cylinder(70.0, 80.0) - Cylinder(20.0, 82.0)),
                  COL_CAP, "CAP_HOUSING_D140_VISION_D40"))
    for k in range(3):
        a = math.radians(120 * k)
        r0 = 62.0
        base = np.array([r0 * math.cos(a), r0 * math.sin(a), 90.0])
        tip = np.array([(r0 + 34) * math.cos(a), (r0 + 34) * math.sin(a), 175.0])
        d = tip - base
        L = float(np.linalg.norm(d))
        f = Plane(origin=Vector(*(base + d / 2.0)), z_dir=Vector(*(d / L)),
                  x_dir=Vector(-math.sin(a), math.cos(a), 0)).location * \
            Box(22, 16, L)
        s.append(_lab(f, COL_CAP, f"CAP_RADIAL_FINGER_{k+1}"))
    s.append(_lab(Pos(0, 0, 89.0) * (Cylinder(46.0, 6.0) - Cylinder(34.0, 8.0)),
                  COL_CAP, "CAP_LED_RING"))
    return s


def main():
    joints, order = parse_chain()
    stow = json.loads((HERE / "design/b601_stow_joint_vector.json")
                      .read_text(encoding="utf-8"))
    arm = build_arm(fk_frames(joints, order, np.array(stow["q_rad"], float)))
    main_c = arm_underside(arm, 40.0, 90.0, ("G6_WRIST_LINK", "G6_J5_MOTOR"))
    wrist_c = arm_underside(arm, -150.0, -110.0, ("G8_RAIL", "G8_FINGER"))

    outputs = {}
    for name, solids in (("B601_MOUNT_MODULE", build_mount()),
                         ("B601_STOW_SUPPORT", build_support(main_c, wrist_c)),
                         ("CAPTURE_HEAD_CANDIDATE", build_capture_head())):
        comp = Compound(children=solids)
        comp.label = name
        path = HERE / f"cad/{name}.step"
        export_step(comp, str(path))
        bb = comp.bounding_box()
        outputs[name] = {"step": path.name, "n_solids": len(solids),
                         "bbox_mm": {"min": [round(bb.min.X, 2), round(bb.min.Y, 2),
                                              round(bb.min.Z, 2)],
                                     "max": [round(bb.max.X, 2), round(bb.max.Y, 2),
                                              round(bb.max.Z, 2)]}}
        print(name, outputs[name]["bbox_mm"])

    registry = {"registry_id": "B601_STOW_CONTACT_REGISTRY", "generated_utc": NOW,
                "STOW_CONTACT_QUALIFICATION": "HOLD",
                "basis": "鞍座接触高度/夹持宽度由 LOD2 STOW 臂实体 bbox 实测导出；"
                          "无强度/刚度/预紧权威；T_c、垫材料、HDRM 型号均未定",
                "three_point_launch_support": ["MNT_INTERFACE_PLATE(X=198 根部)",
                                                "SUP_MAIN_SADDLE(X 40..90)",
                                                "SUP_WRIST_SADDLE(X -150..-110)"],
                "contacts": {
                    "MAIN": {**main_c, "station_x_mm": [40.0, 90.0],
                             "note": "支承段=腕连接件/前臂板下缘（FK 真值 z≈184-195 段）"},
                    "WRIST": {**wrist_c, "station_x_mm": [-150.0, -110.0],
                              "note": "支承段=夹爪指尖区（FK 真值 z≈151-161 段）"}},
                "ee_mutual_exclusivity": {
                    "rule": "B601_GRIPPER 与 CAPTURE_HEAD_CANDIDATE 互斥（EE 二选一）",
                    "staging_default": "B601_GRIPPER（capture head 独立模块 STEP 不入 7 态）"},
                "outputs": outputs}
    (HERE / "design/stow_contact_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    print("contacts:", json.dumps({"MAIN": main_c, "WRIST": wrist_c},
                                   ensure_ascii=False))


if __name__ == "__main__":
    main()
