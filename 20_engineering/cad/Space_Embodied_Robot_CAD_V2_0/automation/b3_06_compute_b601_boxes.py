"""B3-06 离线计算：accepted B601 URDF q0 正运动学 + STL 顶点界 → S 系轴对齐包围盒。

消费方式合规（A3）：URDF read_only_topology_and_q0_transforms；STL
read_only_axis_aligned_min_max_bounds；产物为保守包络代理，非精确供应商几何。
顶点先变换到 A0 系再取界（每链节逐顶点变换，保守且精确到网格）；A0→S 用
R_y(+90°) 轴置换保持轴对齐。输出 evidence/b3_06/b601_q0_boxes.json。
"""
import json
import math
import struct
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition")
V2 = REPO / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_0"
URDF = REPO / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
MESH_DIR = REPO / "20_engineering/cad/spacecraft_layout/arm_b601_v1/meshes_b601_gripper"
OUT = V2 / "evidence/b3_06"

T_SM_T = np.array([0.18525, 0.0, 0.0])
R_SM = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], float)   # 列=M 轴在 S 中


def rpy_to_R(r, p, y):
    cr, sr, cp, sp, cy, sy = (math.cos(r), math.sin(r), math.cos(p),
                              math.sin(p), math.cos(y), math.sin(y))
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def read_stl_vertices(path: Path):
    raw = path.read_bytes()
    n = struct.unpack_from("<I", raw, 80)[0]
    rec = np.frombuffer(raw, dtype=np.uint8, count=n * 50, offset=84)
    rec = rec.reshape(n, 50)
    tri = rec[:, 12:48].copy().view("<f4").reshape(n, 3, 3)
    return tri.reshape(-1, 3).astype(float)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tree = ET.parse(URDF)
    root = tree.getroot()
    joints = {}
    for j in root.findall("joint"):
        parent = j.find("parent").get("link")
        child = j.find("child").get("link")
        o = j.find("origin")
        xyz = [float(v) for v in (o.get("xyz") or "0 0 0").split()]
        rpy = [float(v) for v in (o.get("rpy") or "0 0 0").split()]
        joints[child] = (parent, np.array(xyz), rpy_to_R(*rpy))
    link_mesh_origin = {}
    for l in root.findall("link"):
        name = l.get("name")
        vis = l.find("visual")
        xyz = [0.0, 0.0, 0.0]
        R = np.eye(3)
        if vis is not None and vis.find("origin") is not None:
            o = vis.find("origin")
            xyz = [float(v) for v in (o.get("xyz") or "0 0 0").split()]
            R = rpy_to_R(*[float(v) for v in (o.get("rpy") or "0 0 0").split()])
        link_mesh_origin[name] = (np.array(xyz), R)

    def pose_in_base(link):
        T_t, T_R = np.zeros(3), np.eye(3)
        chain = []
        cur = link
        while cur in joints:
            chain.append(cur)
            cur = joints[cur][0]
        for child in reversed(chain):
            _, xyz, R = joints[child]
            T_t = T_t + T_R @ xyz
            T_R = T_R @ R
        return T_t, T_R

    result = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "consumption": "read_only_topology_q0 + axis_aligned_bounds",
              "frame_note": "boxes axis-aligned in A0 then permuted to S via R_y(+90)",
              "links": {}}
    for link in ["base_link", "link1", "link2", "link3", "link4", "link5",
                 "link6", "gripper_link", "gripper_left", "gripper_right"]:
        stl = MESH_DIR / f"{link}.STL"
        verts = read_stl_vertices(stl)
        mo_t, mo_R = link_mesh_origin[link]
        t, R = pose_in_base(link)
        local = verts @ mo_R.T + mo_t          # visual origin 变换
        world = local @ R.T + t                # q0 链变换到 A0 系
        a0_min, a0_max = world.min(axis=0), world.max(axis=0)
        corners_a0 = np.array([[x, y, z] for x in (a0_min[0], a0_max[0])
                               for y in (a0_min[1], a0_max[1])
                               for z in (a0_min[2], a0_max[2])])
        corners_s = (R_SM @ corners_a0.T).T + T_SM_T
        s_min = corners_s.min(axis=0) * 1000
        s_max = corners_s.max(axis=0) * 1000
        result["links"][link] = {
            "n_vertices": int(len(verts)),
            "a0_box_mm": [list(np.round(a0_min * 1000, 3)),
                          list(np.round(a0_max * 1000, 3))],
            "s_box_mm": [list(np.round(s_min, 3)), list(np.round(s_max, 3))],
        }
        print(link, "S-box mm:", np.round(s_min, 1), "→", np.round(s_max, 1))
    (OUT / "b601_q0_boxes.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BOXES_COMPUTED", len(result["links"]))


if __name__ == "__main__":
    main()
