"""POSEMAP-02 S3：B601 LOD2 臂几何生成（STEP-first，8 组，FK 置位）。

权威声明：
- GEOMETRY_AUTHORITY = 本文件（LOD2 派生形状，SPACECRAFT_ADAPTATION）
- KINEMATIC_AUTHORITY = accepted URDF（关节原点/轴/限位；FK 置位唯一依据）
- MASS_AUTHORITY = EXCLUDED（4.695555949342986 kg 在 URDF，不入 CAD）
- 尺寸依据 = V2_0/evidence/b3_06/b601_q0_boxes.json（accepted URDF 网格 q0 实测盒）
  + evidence/b601_swap_01/body_mapping.yaml（8 组语义映射）
- LOD_CLASS = SPACECRAFT_INTEGRATION_LOD2：可辨识拓扑（关节电机筒/成对臂板/
  腕部支架/夹爪导轨与指），非厂商复刻；LICENSE_CLASS=E3_INTERNAL_RESEARCH_ONLY，
  DO_NOT_REDISTRIBUTE=TRUE。
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from build123d import Box, Color, Compound, Cylinder, Plane, Vector, export_step

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "src"))
from urdf_frame_map_and_stow_fit import (R_SM, T_SM, parse_chain, rpy_to_R,
                                          rot_axis)

NOW = datetime.now(timezone.utc).isoformat()
STOW_JSON = HERE / "design/b601_stow_joint_vector.json"

COL_MOTOR = Color(0.20, 0.22, 0.26, 1.0)     # 关节电机筒（深灰）
COL_PLATE = Color(0.72, 0.74, 0.78, 1.0)     # 成对臂板（铝灰）
COL_STRUCT = Color(0.45, 0.50, 0.58, 1.0)    # 连接结构
COL_GRIP = Color(0.85, 0.55, 0.15, 1.0)      # 夹爪（橙）
COL_BASE = Color(0.30, 0.36, 0.46, 1.0)      # 基座


def fk_frames(joints, order, q):
    """逐关节：原点（mm, CS_S）+ 轴方向（CS_S）；含 EE 原点与接近方向。"""
    T_R, T_t = R_SM.copy(), T_SM.copy()
    out = {}
    for i, jn in enumerate(order):
        J = joints[jn]
        T_t = T_t + T_R @ np.array(J["xyz"])
        T_R = T_R @ rpy_to_R(*J["rpy"])
        ax = np.asarray(J["axis"], float)
        ax = ax / np.linalg.norm(ax)
        out[f"J{i+1}"] = {"p": T_t * 1000.0, "axis": T_R @ ax}
        T_R = T_R @ rot_axis(J["axis"], q[i])
    G = joints["gripper_joint"]
    ee = T_t + T_R @ np.array(G["xyz"])
    out["EE"] = {"p": ee * 1000.0, "axis": T_R @ np.array([0, 0, 1.0])}
    # 夹爪滑移方向（gripper_joint1 轴，若有）
    if "gripper_joint1" in joints:
        G1 = joints["gripper_joint1"]
        R_g = T_R @ rpy_to_R(*G1["rpy"])
        gax = np.asarray(G1["axis"], float)
        out["GRIP_SLIDE"] = R_g @ (gax / np.linalg.norm(gax))
    else:
        out["GRIP_SLIDE"] = None
    return out


def _plane(origin, z_dir, x_hint=None):
    z = np.asarray(z_dir, float)
    z = z / np.linalg.norm(z)
    if x_hint is None:
        x_hint = np.array([0, 0, 1.0]) if abs(z[2]) < 0.9 else np.array([1.0, 0, 0])
    x = np.asarray(x_hint, float) - z * (np.asarray(x_hint, float) @ z)
    n = np.linalg.norm(x)
    x = x / n if n > 1e-9 else np.array([1.0, 0, 0])
    return Plane(origin=Vector(*origin), z_dir=Vector(*z), x_dir=Vector(*x))


def cyl_between(p1, p2, r, color, label):
    p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
    L = float(np.linalg.norm(p2 - p1))
    s = _plane((p1 + p2) / 2.0, (p2 - p1) / L).location * Cylinder(r, L)
    s.color, s.label = color, label
    return s


def cyl_axis(center, axis, r, L, color, label):
    """沿给定轴、以 center 为中心的电机筒。"""
    s = _plane(np.asarray(center, float), axis).location * Cylinder(r, L)
    s.color, s.label = color, label
    return s


def box_between(p1, p2, w, t, color, label, w_dir=None, extend=(0.0, 0.0)):
    """连接两点的方形梁：截面 w×t，w 沿 w_dir（默认自动），可两端延伸。"""
    p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
    d = p2 - p1
    L = float(np.linalg.norm(d))
    d = d / L
    p1e, p2e = p1 - d * extend[0], p2 + d * extend[1]
    Le = L + extend[0] + extend[1]
    s = _plane((p1e + p2e) / 2.0, d, x_hint=w_dir).location * Box(w, t, Le)
    s.color, s.label = color, label
    return s


def paired_plates(p1, p2, axis, half_gap, plate_t, width, color, label,
                  extend=(35.0, 35.0)):
    """成对臂板：沿关节轴 ±half_gap 偏置的两块平行板（B601 标志拓扑）。"""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    out = []
    for sgn, tag in ((1.0, "P"), (-1.0, "N")):
        off = a * sgn * half_gap
        out.append(box_between(np.asarray(p1) + off, np.asarray(p2) + off,
                               width, plate_t, color, f"{label}_{tag}",
                               w_dir=np.cross(a, np.asarray(p2) - np.asarray(p1)),
                               extend=extend))
    return out


def build_arm(fr):
    """8 组 LOD2 臂（世界系直建，位形由 fr=fk_frames(...,q) 决定）。"""
    J = {k: np.asarray(v["p"], float) for k, v in fr.items() if k != "GRIP_SLIDE"}
    A = {k: np.asarray(v["axis"], float) for k, v in fr.items() if k != "GRIP_SLIDE"}
    solids = []

    # G1 01-BASE-1_ASM → base_link：基座壳体 + 颈筒（X 185.25→267.9 实测盒）
    base = _plane(np.array([226.575, 0.0, 0.0]), np.array([1.0, 0, 0]),
                  x_hint=[0, 1, 0]).location * Box(140.0, 200.0, 82.65)
    base.color, base.label = COL_BASE, "G1_BASE_SHELL"
    solids.append(base)
    solids.append(cyl_between(np.array([267.9, 0.0, 0.0]), J["J1"], 50.0,
                              COL_BASE, "G1_BASE_NECK"))

    # G2 M1 转子组 → joint1 电机筒（Φ77×62 沿 J1 轴）
    solids.append(cyl_axis(J["J1"], A["J1"], 38.5, 62.0, COL_MOTOR, "G2_J1_MOTOR"))

    # G3 02-LINK-1_ASM → link1 肩部叉架 + J2 电机筒（DM4340P 级 Φ67）
    solids.append(box_between(J["J1"], J["J2"], 70.0, 70.0, COL_STRUCT,
                              "G3_SHOULDER_YOKE", extend=(0.0, 10.0)))
    solids.append(cyl_axis(J["J2"], A["J2"], 33.5, 70.0, COL_MOTOR, "G3_J2_MOTOR"))

    # G4 03-LINK-2_ASM → link2 成对大臂板（y±33.675 实测半距）+ 罩板
    solids += paired_plates(J["J2"], J["J3"], A["J2"], 30.7, 6.0, 57.0,
                            COL_PLATE, "G4_UPPER_PLATE")
    solids.append(box_between(J["J2"], J["J3"], 40.0, 46.0, COL_STRUCT,
                              "G4_UPPER_COVER", extend=(-20.0, -20.0)))

    # G5 04-LINK-3_ASM → link3 成对前臂板 + J3 肘电机筒 + J4 腕基电机筒
    solids.append(cyl_axis(J["J3"], A["J3"], 33.5, 72.0, COL_MOTOR, "G5_J3_MOTOR"))
    solids += paired_plates(J["J3"], J["J4"], A["J3"], 36.6, 6.0, 60.0,
                            COL_PLATE, "G5_FORE_PLATE")
    solids.append(cyl_axis(J["J4"], A["J4"], 28.0, 60.0, COL_MOTOR, "G5_J4_MOTOR"))

    # G6 M5 转子组 → J4→J5 腕连接 + J5 电机筒（DM4310 级 Φ56）
    solids.append(box_between(J["J4"], J["J5"], 58.0, 52.0, COL_STRUCT,
                              "G6_WRIST_LINK", extend=(-8.0, -8.0)))
    solids.append(cyl_axis(J["J5"], A["J5"], 28.0, 58.0, COL_MOTOR, "G6_J5_MOTOR"))

    # G7 05-GRIPPER_ASM → J5→J6 腕部支架 + J6 电机筒
    solids.append(box_between(J["J5"], J["J6"], 54.0, 48.0, COL_STRUCT,
                              "G7_WRIST_BRACKET", extend=(-6.0, -6.0)))
    solids.append(cyl_axis(J["J6"], A["J6"], 25.0, 56.0, COL_MOTOR, "G7_J6_MOTOR"))

    # G8 夹爪导轨+指组：掌板 + 双导轨 + 双指（滑移方向=URDF gripper_joint1 轴）
    app = J["EE"] - J["J6"]
    app = app / np.linalg.norm(app)
    slide = fr["GRIP_SLIDE"]
    if slide is None:
        slide = np.cross(app, A["J6"])
    slide = slide - app * (slide @ app)
    slide = slide / np.linalg.norm(slide)
    palm_c = J["J6"] + app * 48.0
    palm = _plane(palm_c, app, x_hint=slide).location * Box(154.0, 60.0, 40.0)
    palm.color, palm.label = COL_GRIP, "G8_PALM"
    solids.append(palm)
    rail_start = J["J6"] + app * 68.0
    for sgn, tag in ((1.0, "L"), (-1.0, "R")):
        r0 = rail_start + slide * sgn * 25.0
        solids.append(box_between(r0, r0 + app * 100.0, 16.0, 16.0, COL_GRIP,
                                  f"G8_RAIL_{tag}", w_dir=slide))
        f0 = rail_start + slide * sgn * 44.0 + app * 12.0
        solids.append(box_between(f0, f0 + app * 88.6, 39.0, 20.0, COL_GRIP,
                                  f"G8_FINGER_{tag}", w_dir=np.cross(slide, app)))
    return solids


def bbox_of(compound):
    bb = compound.bounding_box()
    return {"min": [round(bb.min.X, 2), round(bb.min.Y, 2), round(bb.min.Z, 2)],
            "max": [round(bb.max.X, 2), round(bb.max.Y, 2), round(bb.max.Z, 2)]}


def main():
    joints, order = parse_chain()
    stow = json.loads(STOW_JSON.read_text(encoding="utf-8"))
    q_stow = np.array(stow["q_rad"], float)
    q_zero = np.zeros(6)

    (HERE / "cad").mkdir(exist_ok=True)
    manifest = {"manifest_id": "B601_LOD2_BUILD_MANIFEST", "generated_utc": NOW,
                "toolchain": "STEP_FIRST_PARAMETRIC(build123d)",
                "properties": {"GEOMETRY_AUTHORITY": "THIS_LOD2_DERIVATION",
                               "KINEMATIC_AUTHORITY": "ACCEPTED_URDF",
                               "MASS_AUTHORITY": "EXCLUDED_URDF_ONLY",
                               "LICENSE_CLASS": "E3_INTERNAL_RESEARCH_ONLY",
                               "DO_NOT_REDISTRIBUTE": True,
                               "LOD_CLASS": "SPACECRAFT_INTEGRATION_LOD2",
                               "DERIVATION_CLASS": "SPACECRAFT_ADAPTATION"},
                "dimension_basis": "b601_q0_boxes.json 实测盒 + body_mapping 8 组",
                "configs": {}}
    for name, q in (("STOW", q_stow), ("Q0", q_zero)):
        fr = fk_frames(joints, order, q)
        solids = build_arm(fr)
        comp = Compound(children=solids)
        comp.label = f"B601_LOD2_{name}"
        out = HERE / f"cad/B601_LOD2_{name}.step"
        export_step(comp, str(out))
        ys = [abs(float(v)) for s in solids
              if s.label.split("_")[0] in ("G4", "G5", "G6", "G7", "G8")
              for v in (s.bounding_box().min.Y, s.bounding_box().max.Y)]
        manifest["configs"][name] = {
            "step": out.name, "q_rad": [round(float(v), 6) for v in q],
            "n_solids": len(solids), "overall_bbox_mm": bbox_of(comp),
            "central_groups_max_abs_y_mm": round(max(ys), 2),
            "fk_source": ("design/b601_stow_joint_vector.json[CANDIDATE_HOLD]"
                           if name == "STOW" else "q=0 (accepted URDF 参考位形)")}
        print(name, "solids:", len(solids), "bbox:",
              manifest["configs"][name]["overall_bbox_mm"],
              "central max|Y|:", manifest["configs"][name]["central_groups_max_abs_y_mm"])
    (HERE / "design/b601_lod2_build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
