"""VENDOR-CAD-03 S4c：航天器适配器（25° 时钟）+ 收拢支承（顶点级接触实测）。

适配器（用户任务表'新建'项）：160×160×12 接口板 + Ø100 中央通道 + 25° 时钟
法兰盘（对接厂商 92×92 加强板 + HM4-75 支柱脚窝）+ 扩散板 + 四载荷桥 + 角撑 +
热接口垫 + 线束穿舱预留（NON_PHYSICAL）。
支承：真实臂 STOW 网格顶点实测接触（MAIN=G07 腕组 X[10,60]；GRIP=G08 夹爪
X[-100,-40]）；钳口 ±113.15 包络裁剪纪律沿用 120；HDRM×4；三点支承=适配器+双鞍座。
STOW_CONTACT_QUALIFICATION=HOLD。
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from build123d import (Box, Color, Compound, Cylinder, Plane, Pos, Rot, Vector,
                       export_step)

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "src"))
import s4_repose as s4
from s4b_mesh_cache import SCRATCH

NOW = datetime.now(timezone.utc).isoformat()
PLAT_Y, PLAT_ZTOP = 113.15, 113.15
COL_S = Color(0.28, 0.34, 0.42, 1.0)
COL_SD = Color(0.86, 0.48, 0.14, 1.0)
COL_H = Color(0.75, 0.15, 0.15, 1.0)
COL_P = Color(0.15, 0.65, 0.35, 1.0)
COL_R = Color(0.80, 0.20, 0.75, 0.45)


def _lab(s, c, l):
    s.color, s.label = c, l
    return s


def stow_vertices():
    """网格缓存顶点 → STOW 位姿世界坐标（按组）。"""
    cache = np.load(SCRATCH / "mesh_cache.npz")
    adopted = json.loads((HERE / "design/group_link_transforms.json")
                         .read_text(encoding="utf-8"))["adopted"]
    stow = json.loads(s4.STOW_JSON.read_text(encoding="utf-8"))
    frames = s4.link_frames_cs_s(np.array(stow["q_rad"], float))
    out = {}
    for gid, a in adopted.items():
        R_fk, p_fk = frames[a["urdf_link_frame"]]
        R_l, t_l = np.array(a["R_rows"]), np.array(a["t_mm"])
        R = R_fk @ R_l
        t = R_fk @ t_l + p_fk
        out[gid] = cache[f"{gid}_v"].astype(float) @ R.T + t
    return out


def contact(verts, x_lo, x_hi):
    m = (verts[:, 0] >= x_lo) & (verts[:, 0] <= x_hi)
    v = verts[m]
    return {"z_bottom_mm": round(float(v[:, 2].min()), 2),
            "y_min_mm": round(float(v[:, 1].min()), 2),
            "y_max_mm": round(float(v[:, 1].max()), 2),
            "n_vertices": int(m.sum())}


def contact_all(sv, x_lo, x_hi):
    """窗口内全组顶点接触测量（V12 教训：被夹持件≠最低件，必须全组测）。"""
    vs = [v[(v[:, 0] >= x_lo) & (v[:, 0] <= x_hi)] for v in sv.values()]
    vs = [v for v in vs if len(v)]
    allv = np.vstack(vs)
    owner = None
    zmin = float(allv[:, 2].min())
    for gid, v in sv.items():
        m = (v[:, 0] >= x_lo) & (v[:, 0] <= x_hi)
        if m.any() and abs(float(v[m][:, 2].min()) - zmin) < 1e-6:
            owner = gid
    return {"z_bottom_mm": round(zmin, 2),
            "y_min_mm": round(float(allv[:, 1].min()), 2),
            "y_max_mm": round(float(allv[:, 1].max()), 2),
            "lowest_member": owner, "n_vertices": int(len(allv))}


def build_adapter(clock_deg):
    s = []
    s.append(_lab(Plane(origin=Vector(192, 0, 0), z_dir=Vector(1, 0, 0),
                        x_dir=Vector(0, 1, 0)).location *
                  (Box(160, 160, 12) - Cylinder(50, 14)), COL_S,
                  "ADP_INTERFACE_PLATE_160x160x12_D100"))
    # 时钟法兰：Ø130×4 盘 + 92×92×4 对接垫（绕 X 转 clock_deg）+ 4 支柱脚窝标记
    ring = Plane(origin=Vector(200, 0, 0), z_dir=Vector(1, 0, 0)).location * \
        (Cylinder(65, 4) - Cylinder(50, 6))
    s.append(_lab(ring, COL_S, "ADP_CLOCKING_FLANGE_D130"))
    pad = (Pos(200.4, 0, 0) * Rot(clock_deg, 0, 0) *
           Plane(origin=Vector(0, 0, 0), z_dir=Vector(1, 0, 0),
                 x_dir=Vector(0, 1, 0)).location * (Box(92, 92, 4) - Cylinder(46, 6)))
    s.append(_lab(pad, COL_S, f"ADP_BASE_MATE_PAD_92x92_CLOCK{clock_deg:g}DEG"))
    c = math.radians(clock_deg)
    for sy in (1, -1):
        for sz in (1, -1):
            y0, z0 = sy * 32.0, sz * 32.0
            y = y0 * math.cos(c) - z0 * math.sin(c)
            z = y0 * math.sin(c) + z0 * math.cos(c)
            s.append(_lab(Plane(origin=Vector(199.5, y, z),
                                z_dir=Vector(1, 0, 0)).location * Cylinder(5, 3),
                          COL_S, f"ADP_STANDOFF_POCKET_{'P' if sy>0 else 'N'}{'U' if sz>0 else 'D'}"))
    s.append(_lab(Plane(origin=Vector(181.5, 0, 0), z_dir=Vector(1, 0, 0),
                        x_dir=Vector(0, 1, 0)).location * Box(210, 210, 3),
                  COL_S, "ADP_SPREADER"))
    for sy in (1, -1):
        for sz in (1, -1):
            b = Plane(origin=Vector(170, sy * 100.35, sz * 95),
                      z_dir=Vector(0, sy, 0), x_dir=Vector(1, 0, 0)).location * \
                Box(24, 24, 25.3)
            s.append(_lab(b, COL_S, f"ADP_LOAD_BRIDGE_{'P' if sy>0 else 'N'}{'U' if sz>0 else 'D'}"))
            g = (Pos(178, sy * 70, sz * 70) * Rot(0, 45 if sz > 0 else -45, 0) *
                 Box(26, 14, 26))
            s.append(_lab(g, COL_S, f"ADP_GUSSET_{'P' if sy>0 else 'N'}{'U' if sz>0 else 'D'}"))
    s.append(_lab(Pos(188, 0, 78) * Box(20, 60, 2), COL_P,
                  "ADP_THERMAL_INTERFACE_PAD_60x2_HOLD"))
    s.append(_lab(Pos(188, 0, -95) * Box(24, 80, 40), COL_R,
                  "ADP_HARNESS_PASSTHROUGH_RESERVATION_NON_PHYSICAL"))
    return s


def build_support(main_c, grip_c, windows):
    """V2 设计（V12 侵入教训后）：全组测量 + 低导块 + 垫下嵌入 HDRM。

    - 垫顶=窗口内全组最低面；垫上方仅有横向±2mm 间隙外的低导块（高 24）——
      构造上不与臂相交；
    - HDRM 垂直嵌于塔内，顶面=垫底（z_bot-3），不高出垫面；
    - 横向锁紧由 HDRM 预紧 + 顶部绑带（HOLD）承担，不再用高钳口。
    """
    s = []
    for tag, (x_lo, x_hi), c in (("MAIN", windows["MAIN"], main_c),
                                   ("GRIP", windows["GRIP"], grip_c)):
        xm, bw = (x_lo + x_hi) / 2, x_hi - x_lo
        yc = (c["y_min_mm"] + c["y_max_mm"]) / 2
        z_bot = c["z_bottom_mm"]
        s.append(_lab(Plane(origin=Vector(xm, 0, PLAT_ZTOP - 15),
                            z_dir=Vector(0, 0, 1), x_dir=Vector(1, 0, 0)).location *
                      Box(bw, 2 * 105.65, 30), COL_S, f"SUP_{tag}_CROSSBEAM"))
        th = z_bot - 3 - PLAT_ZTOP
        s.append(_lab(Plane(origin=Vector(xm, yc, PLAT_ZTOP + th / 2),
                            z_dir=Vector(0, 0, 1), x_dir=Vector(1, 0, 0)).location *
                      Box(bw, 46, th), COL_SD, f"SUP_{tag}_SADDLE_TOWER_H{th:.0f}"))
        grip_w = (c["y_max_mm"] - c["y_min_mm"]) + 6
        s.append(_lab(Pos(xm, yc, z_bot - 1.5) * Box(bw, grip_w, 3), COL_P,
                      f"SUP_{tag}_CONTACT_PAD_HOLD"))
        for sy in (1, -1):   # 低导块：横向 ±2mm 间隙外，高 24，不高出臂底+24
            inner = (c["y_max_mm"] + 2.0) if sy > 0 else (c["y_min_mm"] - 2.0)
            outer = inner + sy * 8.0
            outer = min(outer, PLAT_Y) if sy > 0 else max(outer, -PLAT_Y)
            tg = abs(outer - inner)
            if tg < 3.0:
                c.setdefault("guide_notes", []).append(
                    f"{tag}_{'P' if sy>0 else 'N'}: 导块被 ±113.15 裁剪至 "
                    f"{tg:.1f}mm<3 弃用→顶部绑带 HOLD")
                continue
            s.append(_lab(Pos(xm, (inner + outer) / 2, z_bot + 9) *
                          Box(bw, tg, 24), COL_SD,
                          f"SUP_{tag}_GUIDE_{'P' if sy>0 else 'N'}"))
        for sx in (1, -1):   # HDRM 垂直嵌入塔内，顶面=垫底
            s.append(_lab(Plane(origin=Vector(xm + sx * (bw / 2 - 10), yc,
                                               z_bot - 3 - 18),
                                z_dir=Vector(0, 0, 1)).location * Cylinder(8, 36),
                          COL_H, f"SUP_{tag}_HDRM_{'F' if sx>0 else 'A'}"))
    return s


def main():
    clock = s4._clock_deg()
    sv = stow_vertices()
    windows = {"MAIN": (10.0, 60.0), "GRIP": (-100.0, -40.0)}
    main_c = contact_all(sv, *windows["MAIN"])
    grip_c = contact_all(sv, *windows["GRIP"])

    outputs = {}
    for name, solids in (("B601_SPACECRAFT_ADAPTER", build_adapter(clock)),
                         ("B601_STOW_SUPPORT_V2", build_support(main_c, grip_c,
                                                                  windows))):
        comp = Compound(children=solids)
        comp.label = name
        path = HERE / f"cad/{name}.step"
        export_step(comp, str(path))
        bb = comp.bounding_box()
        outputs[name] = {"step": path.name, "n_solids": len(solids),
                         "bbox_mm": [round(bb.min.X, 2), round(bb.min.Y, 2),
                                      round(bb.min.Z, 2), round(bb.max.X, 2),
                                      round(bb.max.Y, 2), round(bb.max.Z, 2)]}
        print(name, outputs[name]["bbox_mm"])

    reg = {"registry_id": "VENDORCAD03_STOW_CONTACT_REGISTRY",
           "generated_utc": NOW,
           "STOW_CONTACT_QUALIFICATION": "HOLD",
           "adapter_clock_deg": clock,
           "measurement": "真实厂商几何网格顶点级（2mm 挠度缓存）",
           "three_point_launch_support": ["ADP_INTERFACE_PLATE(X=198)",
                                           "SUP_MAIN(X 10..60, 夹持 G07 腕组)",
                                           "SUP_GRIP(X -100..-40, 夹持 G08 夹爪)"],
           "contacts": {"MAIN": {**main_c, "station_x": list(windows["MAIN"])},
                         "GRIP": {**grip_c, "station_x": list(windows["GRIP"])}},
           "design_revision": "V12 侵入教训：全组最低面承托（非单件）+低导块+"
                                "垫下嵌入 HDRM；高钳口废止，横向锁紧=预紧+绑带 HOLD",
           "tower_slenderness_note": "塔高 ~100-135mm（越顶链 z≈222-249）——"
                                       "长细比与频率未评估，属 HOLD 项",
           "station_update_vs_120": "120 推荐工位 X[40,90]/[-150,-110] 基于种子鞍高；"
                                      "真实几何越顶链上移+前移，工位改为 [10,60]/[-100,-40]",
           "outputs": outputs}
    (HERE / "design/stow_contact_registry.json").write_text(
        json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("contacts:", json.dumps({"MAIN": main_c, "GRIP": grip_c},
                                    ensure_ascii=False))


if __name__ == "__main__":
    main()
