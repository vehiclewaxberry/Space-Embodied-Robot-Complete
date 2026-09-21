"""VENDOR-CAD-03 S4：URDF 驱动的真实厂商实体重置位。

T_S_group(q) = FK_link(q) ∘ T_LG（S2b 采纳表）。
帧约定：CS_S；base_link 帧 = (R_SM, [198,0,0])（均匀映射；与 q0_boxes 显示轨的
B601_INHERIT_OFFSET_X=12.75 分歧显式登记，不静默混用）。
姿态：STOW = 120 候选向量（CANDIDATE_HOLD，只读引用）；Q0 = accepted URDF 参考位形。
交叉校验：Q0 重置位各组世界盒 vs b601_q0_boxes（均匀映射口径）。
"""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from OCP.BRep import BRep_Builder
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import (STEPControl_AsIs, STEPControl_Reader,
                              STEPControl_Writer)
from OCP.TopoDS import TopoDS_Compound

HERE = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc).isoformat()
URDF = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf")
_V2 = Path(__file__).resolve().parent.parent / "design/b601_stow_joint_vector_v2.json"
STOW_JSON = (_V2 if _V2.exists() else
             HERE.parent / "120_B601_Geometry_and_PoseMap_02/design/b601_stow_joint_vector.json")

R_SM = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], float)
T_SM_MM = np.array([198.0, 0.0, 0.0])


def _clock_deg():
    """适配器 J1 轴向时钟角（design/adapter_clocking.json；无则 0）。"""
    p = HERE / "design/adapter_clocking.json"
    if p.exists():
        return float(json.loads(p.read_text(encoding="utf-8"))["clock_deg"])
    return 0.0


def rpy_to_R(r, p, y):
    cr, sr, cp, sp, cy, sy = (math.cos(r), math.sin(r), math.cos(p),
                               math.sin(p), math.cos(y), math.sin(y))
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def rot_axis(axis, q):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * (K @ K)


def link_frames_cs_s(q6):
    """各连杆帧在 CS_S 的 (R, p_mm)；q6 = 6 关节角。gripper_joint 视作固定。"""
    root = ET.parse(URDF).getroot()
    joints = {}
    for j in root.findall("joint"):
        o = j.find("origin")
        ax = j.find("axis")
        joints[j.get("name")] = {
            "parent": j.find("parent").get("link"),
            "child": j.find("child").get("link"),
            "xyz": np.array([float(v) for v in
                             (o.get("xyz") or "0 0 0").split()]) * 1000.0,
            "rpy": [float(v) for v in (o.get("rpy") or "0 0 0").split()],
            "axis": ([float(v) for v in ax.get("xyz").split()]
                      if ax is not None else [0, 0, 1])}
    c = math.radians(_clock_deg())   # 适配器时钟角：绕 A0 z（=J1 轴 ∥ +X_S）
    Rz_c = np.array([[math.cos(c), -math.sin(c), 0],
                     [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    frames = {"base_link": (R_SM @ Rz_c, T_SM_MM.copy())}
    for i, jn in enumerate(["joint1", "joint2", "joint3", "joint4", "joint5",
                             "joint6"]):
        J = joints[jn]
        Rp, pp = frames[J["parent"]]
        p = pp + Rp @ J["xyz"]
        R = Rp @ rpy_to_R(*J["rpy"]) @ rot_axis(J["axis"], q6[i])
        frames[J["child"]] = (R, p)
    G = joints["gripper_joint"]
    Rp, pp = frames[G["parent"]]
    frames["gripper_link"] = (Rp @ rpy_to_R(*G["rpy"]), pp + Rp @ G["xyz"])
    return frames


def load_shape(p: Path):
    r = STEPControl_Reader()
    assert r.ReadFile(str(p)) == IFSelect_RetDone, p.name
    r.TransferRoots()
    return r.OneShape()


def apply_rt(shape, R, t):
    tr = gp_Trsf()
    tr.SetValues(R[0, 0], R[0, 1], R[0, 2], t[0],
                 R[1, 0], R[1, 1], R[1, 2], t[1],
                 R[2, 0], R[2, 1], R[2, 2], t[2])
    return BRepBuilderAPI_Transform(shape, tr, True).Shape()


def bbox_of(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return [round(v, 2) for v in (xmin, ymin, zmin, xmax, ymax, zmax)]


def main():
    adopted = json.loads((HERE / "design/group_link_transforms.json")
                         .read_text(encoding="utf-8"))["adopted"]
    stow = json.loads(STOW_JSON.read_text(encoding="utf-8"))
    q_boxes = json.loads(
        (HERE.parent.parent / "Space_Embodied_Robot_CAD_V2_0/evidence/b3_06/b601_q0_boxes.json")
        .read_text(encoding="utf-8"))["links"]

    shapes = {}
    for gid, a in adopted.items():
        fname = ("G06_Base_FILTERED.step" if gid == "G06"
                  else a["extracted_step"])
        shapes[gid] = load_shape(HERE / "vendor_groups" / fname)

    poses = {"STOW": np.array(stow["q_rad"], float), "Q0": np.zeros(6)}
    report = {"id": "VENDORCAD03_S4_REPOSE", "generated_utc": NOW,
              "stow_vector_source": "120 CANDIDATE_HOLD（只读引用；仍非 accepted）",
              "frame_convention": "均匀映射 base_link@X=198；q0_boxes 显示轨含 "
                                    "B601_INHERIT_OFFSET_X=12.75（base 组 -12.75），"
                                    "对拍时显式补偿，不静默混用",
              "poses": {}}
    for pname, q in poses.items():
        frames = link_frames_cs_s(q)
        builder = BRep_Builder()
        comp = TopoDS_Compound()
        builder.MakeCompound(comp)
        placements, xcheck = {}, {}
        for gid, a in adopted.items():
            ln = a["urdf_link_frame"]
            R_fk, p_fk = frames[ln]
            R_l, t_l = np.array(a["R_rows"]), np.array(a["t_mm"])
            R_tot = R_fk @ R_l
            t_tot = R_fk @ t_l + p_fk
            placed = apply_rt(shapes[gid], R_tot, t_tot)
            builder.Add(comp, placed)
            bb = bbox_of(placed)
            placements[gid] = {"link": ln, "bbox_mm": bb}
            if pname == "Q0":
                key = {"G06": "base_link", "G08": "gripper_link"}.get(gid, ln)
                if key in q_boxes:
                    exp = q_boxes[key]["s_box_mm"]
                    exp_lo = list(exp[0])
                    exp_hi = list(exp[1])
                    if key == "base_link":   # 显示轨 12.75 补偿
                        exp_lo[0] += 12.75
                        exp_hi[0] += 12.75
                    dev = max(abs(bb[0] - exp_lo[0]), abs(bb[1] - exp_lo[1]),
                              abs(bb[2] - exp_lo[2]), abs(bb[3] - exp_hi[0]),
                              abs(bb[4] - exp_hi[1]), abs(bb[5] - exp_hi[2]))
                    xcheck[gid] = {"vs_link": key,
                                    "max_box_dev_mm": round(dev, 2)}
        out = HERE / f"cad/B601_VENDOR_{pname}.step"
        (HERE / "cad").mkdir(exist_ok=True)
        w = STEPControl_Writer()
        w.Transfer(comp, STEPControl_AsIs)
        w.Write(str(out))
        entry = {"step": out.name, "q_rad": [round(float(v), 6) for v in q],
                 "overall_bbox_mm": bbox_of(comp), "groups": placements}
        if xcheck:
            entry["q0_box_xcheck"] = xcheck
        report["poses"][pname] = entry
        print(pname, "bbox:", entry["overall_bbox_mm"])
        if xcheck:
            for gid, x in xcheck.items():
                print(" xcheck", gid, x)
    (HERE / "design/repose_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
