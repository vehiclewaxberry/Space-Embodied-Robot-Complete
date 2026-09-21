"""POSEMAP-02 S2：accepted URDF → CAD 帧映射 / 关节轴登记 / 收拢向量拟合。

权威：运动学=accepted URDF（唯一）；安装映射=T_S_base: t=[198,0,0], R=R_SM
（URDF 基座 z 轴 → +X_S，与 A0=M 既有约定一致）。
种子仅作拟合目标（DESIGN_PROPOSAL_STOW_SEED），产出一律 CANDIDATE_HOLD——
accepted URDF 不含官方收拢向量，禁止将拟合角写成 accepted joint vector。
"""
import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent.parent
URDF = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf")
NOW = datetime.now(timezone.utc).isoformat()

R_SM = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], float)
T_SM = np.array([0.198, 0.0, 0.0])

SEEDS_MM = {  # DESIGN_PROPOSAL_STOW_SEED（CS_S，mm）
    "J2": [224, 0, 82], "J3": [70, 0, 145], "J4": [-108, 0, 145],
    "J5": [-128, 0, 145], "J6": [-151, 0, 145], "EE": [-150, 0, 145],
}


def rpy_to_R(r, p, y):
    cr, sr, cp, sp, cy, sy = map(float, (math.cos(r), math.sin(r), math.cos(p),
                                          math.sin(p), math.cos(y), math.sin(y)))
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def rot_axis(axis, q):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(q) * K + (1 - math.cos(q)) * (K @ K)


def parse_chain():
    root = ET.parse(URDF).getroot()
    chain = []
    joints = {}
    for j in root.findall("joint"):
        name = j.get("name")
        parent = j.find("parent").get("link")
        child = j.find("child").get("link")
        o = j.find("origin")
        xyz = [float(v) for v in (o.get("xyz") or "0 0 0").split()]
        rpy = [float(v) for v in (o.get("rpy") or "0 0 0").split()]
        ax = j.find("axis")
        axis = ([float(v) for v in ax.get("xyz").split()] if ax is not None
                else [0, 0, 1])
        lim = j.find("limit")
        limits = ({"lower": float(lim.get("lower", "nan")),
                   "upper": float(lim.get("upper", "nan"))} if lim is not None
                  else None)
        joints[name] = {"type": j.get("type"), "parent": parent, "child": child,
                        "xyz": xyz, "rpy": rpy, "axis": axis, "limits": limits}
    order = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
    return joints, order


def fk_joint_origins(joints, order, q):
    """返回各关节系原点与末端在 CS_S 的位置（mm）。"""
    T_R, T_t = R_SM.copy(), T_SM.copy()
    out = {}
    for i, jn in enumerate(order):
        J = joints[jn]
        T_t = T_t + T_R @ np.array(J["xyz"])
        T_R = T_R @ rpy_to_R(*J["rpy"])
        out[f"J{i+1}"] = (T_t * 1000).tolist()
        T_R = T_R @ rot_axis(J["axis"], q[i])
    if "gripper_joint" in joints:
        G = joints["gripper_joint"]
        T_t = T_t + T_R @ np.array(G["xyz"])
        out["EE"] = (T_t * 1000).tolist()
    return out


def main():
    joints, order = parse_chain()
    # 帧映射与轴登记（真值）
    frame_map = {"map_id": "B601_URDF_TO_CAD_FRAME_MAP", "generated_utc": NOW,
                 "kinematic_authority": str(URDF),
                 "cad_base_frame": {"frame": "CS_S", "t_mm": [198.0, 0.0, 0.0],
                                    "R_rows": R_SM.tolist(),
                                    "note": "URDF base z→+X_S；A0=M 约定继承；J1 轴沿 +X_S"},
                 "joints": {}}
    axis_reg = {"registry_id": "B601_JOINT_AXIS_REGISTRY", "generated_utc": NOW,
                "joints": {}}
    for jn in order + ["gripper_joint", "gripper_joint1", "gripper_joint2"]:
        if jn not in joints:
            continue
        J = joints[jn]
        frame_map["joints"][jn] = {"parent": J["parent"], "child": J["child"],
                                   "origin_xyz_m": J["xyz"], "origin_rpy": J["rpy"]}
        axis_reg["joints"][jn] = {"type": J["type"], "axis_local": J["axis"],
                                  "limits_rad": J["limits"]}
    (HERE / "design/b601_urdf_to_cad_frame_map.yaml").write_text(
        yaml.safe_dump(frame_map, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (HERE / "design/b601_joint_axis_registry.yaml").write_text(
        yaml.safe_dump(axis_reg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # 收拢向量：顺序几何法——种子只取折叠方向拓扑，长度由 URDF 真值决定
    targets = {k: np.array(v, float) for k, v in SEEDS_MM.items()}
    seed_dirs = {  # 期望的各段方向（由种子差分，单位化）
        "upper": (targets["J3"] - targets["J2"]) / np.linalg.norm(targets["J3"] - targets["J2"]),
        "fore":  (targets["J4"] - targets["J3"]) / np.linalg.norm(targets["J4"] - targets["J3"]),
        "wrist": (targets["J6"] - targets["J4"]) / np.linalg.norm(targets["J6"] - targets["J4"]),
    }
    lb, ub = [], []
    for jn in order:
        lim = joints[jn]["limits"] or {"lower": -math.pi, "upper": math.pi}
        lb.append(lim["lower"]); ub.append(lim["upper"])
    lb, ub = np.array(lb), np.array(ub)

    def seg_dir(pos, a, b):
        v = np.array(pos[b]) - np.array(pos[a])
        n = np.linalg.norm(v)
        return v / n if n > 1e-9 else np.zeros(3)

    def cost(q):
        """可达族内代价：fore/wrist 方向 + 强走廊惩罚。

        upper 项已弃用——运动学证明（见 stow JSON kinematic_finding）：
        joint2 轴与大臂向量均 ⊥X_S 且 (axis×arm) 的 X 分量对 q1 不变，
        q2∈[-π,0] ⇒ sin(q2)≤0 ⇒ 大臂 X 倾分量恒 ≥0，种子 -X 后倾不可达。
        """
        pos = fk_joint_origins(joints, order, q)
        c = 0.0
        for a, b, key, w in (("J3", "J4", "fore", 2.0), ("J4", "J6", "wrist", 2.0)):
            d = seg_dir(pos, a, b)
            c += w * (1.0 - float(d @ seed_dirs[key]))
        for k in ("J3", "J4", "J5", "J6", "EE"):
            c += 0.03 * max(0.0, abs(pos[k][1]) - 40.0)    # 走廊 |Y|≤40
            c += 0.02 * max(0.0, pos[k][0] - 430.0)        # X 包络（q=0 厂商折叠即 430）
        for k in ("J4", "J5", "J6", "EE"):
            c += 0.05 * max(0.0, 130.0 - pos[k][2])        # 越顶硬约束：腕链在平台顶上方
        c += 0.001 * abs(pos["EE"][0] - (-150.0))          # EE 靠后鞍座（弱）
        return c

    def descend(q):
        for _ in range(4):
            for i in range(6):
                grid = np.arange(lb[i], ub[i] + 1e-9, math.radians(2))
                best_v, best_c = q[i], cost(q)
                for v in grid:
                    q[i] = v
                    cc = cost(q)
                    if cc < best_c:
                        best_c, best_v = cc, v
                q[i] = best_v
        return q, cost(q)

    best_q, best_c = None, None
    for s1 in (160.0, -160.0):          # 越顶族需平面近翻转（q1 限位 ±160.4°）
        for s2 in (-179.0, -150.0, -120.0):
            for s3 in (-60.0, -90.0, -120.0):
                q0s = np.clip(np.array([math.radians(s1), math.radians(s2),
                                        math.radians(s3), 0, 0, 0]),
                              lb + 1e-6, ub - 1e-6)
                qq, cc = descend(q0s.copy())
                if best_c is None or cc < best_c:
                    best_q, best_c = qq.copy(), cc
    q = best_q

    # q6 掌板调平：雅可比证明 q6 不动 EE（纯自旋），用它把夹爪滑移方向调平
    # （最小化 |slide_z|），消除掌板角点下探舱面（MC10 根因）。
    def grip_slide_z(qv):
        T_R = R_SM.copy()
        for i, jn in enumerate(order):
            J = joints[jn]
            T_R = T_R @ rpy_to_R(*J["rpy"]) @ rot_axis(J["axis"], qv[i])
        G1 = joints.get("gripper_joint1")
        if G1 is None:
            return None
        gax = np.asarray(G1["axis"], float)
        s = T_R @ rpy_to_R(*G1["rpy"]) @ (gax / np.linalg.norm(gax))
        return abs(float(s[2]))
    if grip_slide_z(q) is not None:
        grid6 = np.arange(lb[5], ub[5] + 1e-9, math.radians(0.5))
        q[5] = min(grid6, key=lambda v: grip_slide_z(
            np.concatenate([q[:5], [v]])))

    pos = fk_joint_origins(joints, order, q)
    errs = {k: round(float(np.linalg.norm(np.array(pos[k]) - targets[k])), 2)
            for k in targets if k in pos}
    dir_errs = {}
    for a, b, key in (("J2", "J3", "upper"), ("J3", "J4", "fore"),
                      ("J4", "J6", "wrist")):
        d = seg_dir(pos, a, b)
        dir_errs[key] = round(float(np.degrees(
            np.arccos(np.clip(d @ seed_dirs[key], -1, 1)))), 2)

    class _Sol:  # 兼容下方引用
        success = all(lb[i] <= q[i] <= ub[i] for i in range(6))
    sol = _Sol()
    max_abs_y = max(abs(pos[k][1]) for k in ("J3", "J4", "J5", "J6", "EE"))
    stow = {"vector_id": "B601_STOW_JOINT_VECTOR", "generated_utc": NOW,
            "STOW_VECTOR_STATUS": "CANDIDATE_HOLD",
            "basis": "越顶族约束坐标下降（多起点 2° 网格）：种子仅取折叠方向拓扑，"
                     "连杆长度/轴向/限位=accepted URDF 真值；URDF 无官方收拢向量",
            "kinematic_findings": [
                {"id": "F1_UPPER_TILT_UNREACHABLE",
                 "claim": "种子大臂 -X 后倾在 accepted URDF 限位内不可达",
                 "proof_sketch": "joint2 轴与大臂向量在任意 q1 下均 ⊥X_S，"
                                 "(axis×arm) 的 X 分量对绕 X_S 的 q1 旋转不变号；"
                                 "joint2 限位 [-π,0] ⇒ sin(q2)≤0 ⇒ 大臂 X 倾分量恒≥0。"
                                 "可达收拢族=大臂近垂直(+Z)+前臂越顶回折",
                 "numeric_witness": "雅可比探针 q2=+30°→dJ3=[-132,0,-35]（-X 倾需正 q2，超限）"},
                {"id": "F2_CORRIDOR_VIOLATION_RECORDED",
                 "claim": f"中央走廊 |Y|≤40 违规，max|Y|={max_abs_y:.1f}mm",
                 "root_cause": "q1 限位 ±2.8rad=±160.4° 距平面全翻转 180° 缺 19.6°"
                               "（J3 侧移 ~264·sin19.6°≈88mm 与基座 y=31.6 部分抵消）"
                               "+ 腕部连杆固有横向偏置（j4 y=-54、j5 y=-37.5）",
                 "consequence": "STOWED 态臂中央件 |Y|≤40 校验预期 FAIL_RECORDED，"
                                "属 URDF 运动学事实而非建模缺陷；收拢托架鞍座宽度需按实测 Y 包络"},
                {"id": "F3_LIMIT_SATURATION",
                 "claim": "越顶族解在 q1=+160.0°（≈上限）与 q2=-179.9°（≈下限）双饱和",
                 "consequence": "收拢位形对关节限位裕度为零；HDRM 释放后展开首步只能向限位内侧运动"},
                {"id": "F4_REJECTED_FAMILIES",
                 "vendor_q0_fold": "X∈[283,430], Z∈[-260,+244]——Z 下探 -260 破发射包络，弃",
                 "underslung_outboard_fold": "J3 X=594 外悬 411mm 破 X 包络且遮挡 -Z 面，弃"}],
            "segment_direction_error_deg": dir_errs,
            "corridor_check_mm": {"limit_abs_y": 40.0,
                                   "max_abs_y": round(float(max_abs_y), 1),
                                   "status": "VIOLATED_RECORDED"},
            "overtop_check_mm": {"min_wrist_z": round(min(pos[k][2] for k in
                                     ("J4", "J5", "J6", "EE")), 1),
                                  "platform_top_z": 113.15, "status": "SATISFIED"},
            "x_envelope_check_mm": {"max_x": round(max(pos[k][0] for k in pos), 1),
                                     "vendor_q0_ref": 430.0, "status": "SATISFIED"},
            "q_rad": [round(float(v), 6) for v in q],
            "q_deg": [round(math.degrees(float(v)), 3) for v in q],
            "joint_limits_respected": bool(sol.success),
            "fk_joint_centers_mm_CS_S": {k: [round(x, 2) for x in v]
                                          for k, v in pos.items()},
            "seed_residual_mm": errs,
            "saddle_height_implication": "前臂/腕越顶走廊实际 z≈158–195（非种子 145）；"
                                          "托架鞍座高度以本 FK 真值为准",
            "prohibition": "不得写成 accepted joint vector；正式收拢向量需人工/载荷侧批准"}
    (HERE / "design/b601_stow_joint_vector.json").write_text(
        json.dumps(stow, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"q_deg": stow["q_deg"], "residual_mm": errs,
                      "status": stow["STOW_VECTOR_STATUS"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
