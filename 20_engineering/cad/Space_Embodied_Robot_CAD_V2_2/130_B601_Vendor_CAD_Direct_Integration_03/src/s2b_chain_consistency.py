"""VENDOR-CAD-03 S2b：链一致性核验 + 终版组变换表。

原理：厂商装配位形 = URDF q=0。对每个良配组 i：
  T_A0V_i = FK_i(0) ∘ T_LG_i(direct)   应跨组一致（同一全局 vendor→A0 变换）。
以一致均值 T_A0V* 反推所有组（尤其 G05/G08）的链推导变换：
  T_LG_i(chain) = FK_i(0)^-1 ∘ T_A0V*。
采纳规则（fail-closed）：direct nn≤5mm 且 margin≥0.5mm → DIRECT；否则 CHAIN_DERIVED。
"""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc).isoformat()
URDF = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf")

LINK_JOINT = {  # link → 其父关节（None=base）
    "base_link": None, "link1": "joint1", "link2": "joint2", "link3": "joint3",
    "link4": "joint4", "link5": "joint5", "link6": "joint6",
    "gripper_link": "gripper_joint"}


def rpy_to_R(r, p, y):
    cr, sr, cp, sp, cy, sy = (math.cos(r), math.sin(r), math.cos(p),
                               math.sin(p), math.cos(y), math.sin(y))
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def link_frames_a0_q0():
    """各连杆局部系在 A0（URDF base）中的 (R, p_mm)，q=0。"""
    root = ET.parse(URDF).getroot()
    joints = {}
    for j in root.findall("joint"):
        o = j.find("origin")
        joints[j.get("name")] = {
            "parent": j.find("parent").get("link"),
            "child": j.find("child").get("link"),
            "xyz": np.array([float(v) for v in
                             (o.get("xyz") or "0 0 0").split()]) * 1000.0,
            "rpy": [float(v) for v in (o.get("rpy") or "0 0 0").split()]}
    frames = {"base_link": (np.eye(3), np.zeros(3))}
    order = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6",
             "gripper_joint"]
    for jn in order:
        J = joints[jn]
        Rp, pp = frames[J["parent"]]
        R = Rp @ rpy_to_R(*J["rpy"])       # q=0：关节旋转=恒等
        p = pp + Rp @ J["xyz"]
        frames[J["child"]] = (R, p)
    return frames


def main():
    reg = json.loads((HERE / "design/group_link_registration.json")
                     .read_text(encoding="utf-8"))
    frames = link_frames_a0_q0()

    # 良配组 → T_A0V 候选
    cands = {}
    for gid, g in reg["groups"].items():
        ln = g["urdf_links"][0]
        ok = (g["nn_mean_mm"] <= 5.0 and (g["ambiguity_margin_mm"] or 0) >= 0.5)
        R_fk, p_fk = frames[ln]
        R_reg = np.array(g["R_rows"])
        t_reg = np.array(g["t_mm"])
        R_a0v = R_fk @ R_reg
        t_a0v = R_fk @ t_reg + p_fk
        cands[gid] = {"ok": ok, "R": R_a0v, "t": t_a0v, "link": ln}

    good = [c for c in cands.values() if c["ok"]]
    # 旋转一致性（轴向阵应逐位相同）+ 平移散布
    R_ref = good[0]["R"]
    rot_dev = {gid: float(np.abs(c["R"] - R_ref).max())
               for gid, c in cands.items() if c["ok"]}
    t_stack = np.array([c["t"] for c in good])
    t_mean = t_stack.mean(axis=0)
    t_dev = {gid: round(float(np.linalg.norm(c["t"] - t_mean)), 3)
             for gid, c in cands.items() if c["ok"]}
    consistent = max(rot_dev.values()) < 1e-4   # rpy 浮点（1.5708 vs π/2）容差

    out = {"id": "VENDORCAD03_S2B_CHAIN_CONSISTENCY", "generated_utc": NOW,
           "vendor_pose_hypothesis": "vendor 装配位形 = URDF q=0",
           "rotation_consistent": bool(consistent),
           "rotation_max_dev": max(rot_dev.values()),
           "T_A0V_rotation_rows": R_ref.tolist(),
           "T_A0V_translation_mm": [round(float(x), 3) for x in t_mean],
           "translation_dev_per_group_mm": t_dev,
           "adopted": {}}
    if not consistent:
        out["verdict"] = "CHAIN_INCONSISTENT_HOLD"
    for gid, g in reg["groups"].items():
        ln = g["urdf_links"][0]
        R_fk, p_fk = frames[ln]
        if cands[gid]["ok"]:
            method, R_l, t_l = "DIRECT_NN", np.array(g["R_rows"]), np.array(g["t_mm"])
        else:
            method = "CHAIN_DERIVED"
            R_l = R_fk.T @ R_ref
            t_l = R_fk.T @ (t_mean - p_fk)
        out["adopted"][gid] = {
            "vendor_group": g["vendor_group"], "urdf_link_frame": ln,
            "method": method, "R_rows": np.round(R_l, 12).tolist(),
            "t_mm": [round(float(x), 3) for x in t_l],
            "direct_nn_mm": g["nn_mean_mm"],
            "direct_margin_mm": g["ambiguity_margin_mm"],
            "extracted_step": g["extracted_step"],
            "note": ("" if cands[gid]["ok"] else
                      "direct 配准不可靠（内容划分/开度差异）；链推导锁定")}
    (HERE / "design/group_link_transforms.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("rotation_consistent:", consistent, "max_rot_dev:", max(rot_dev.values()))
    print("translation deviations (mm):", t_dev)
    for gid, a in out["adopted"].items():
        print(gid, a["urdf_link_frame"], a["method"], "t=", a["t_mm"])


if __name__ == "__main__":
    main()
