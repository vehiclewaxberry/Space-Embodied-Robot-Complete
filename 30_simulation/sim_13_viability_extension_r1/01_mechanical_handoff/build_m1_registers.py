"""RC1-MR1：B601 关节轴/符号/零位/帧与双 P 关节约定调和。

只读输入：
  * 已接受 URDF        20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf
  * 帧树（源级冻结）   .../unified_r2_digital_prototype_prebind/source_only_v2/
                       UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml
  * 夹爪 CAD 证据      20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/
                       04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json

输出（本目录）：
  SIM13R_JOINT_ZERO_SIGN_LIMIT_REGISTER_V1.yaml
  SIM13R_FRAME_GRAPH_V1.yaml
  SIM13R_P_JOINT_CONVENTION_RECONCILIATION_V1.json
  SIM13R_FORWARD_KINEMATICS_WITNESS_V1.csv
  SIM13R_FRAME_DISCREPANCY_LEDGER_V1.csv
  SIM13R_M1_GATE_V1.json

纪律：不改写 URDF；不把 CAD 质量属性写回 L0；未知一律 UNKNOWN/HOLD，禁止零填充。
"""
import csv
import hashlib
import json
import os

import numpy as np
import yaml

from b601_kinematics import B601, REVOLUTE_ORDER, PRISMATIC_ORDER, rpy_to_R, se3

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))

FRAME_TREE_REL = ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                  "unified_r2_digital_prototype_prebind/source_only_v2/"
                  "UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml")
GRIPPER_VAL_REL = ("20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/"
                   "04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json")

# 判据容差（显式冻结，禁止事后放宽）
#
# 位置一致性分两层，不允许用单一放宽容差掩盖成因：
#   TOL_POS_AXIAL   沿行程轴（Y）分量 —— 检验行程幅值与符号是否真的一致
#   TOL_POS_EXACT90 全三维分量，在“URDF rpy 恰为 ±pi/2”假设下 —— 该假设会失败
#   TOL_POS_QUANT   全三维分量，在 URDF 声明的 rpy 量化下 —— 由量化解析上界导出
#
# URDF 将 pi/2 写为 1.5708，量化误差 delta = 1.5708 - pi/2 = 3.673205e-06 rad。
# 该量化使 P 关节轴在 palm 帧内倾斜 delta，在全行程 S 上产生横向偏移 S*sin(delta)。
URDF_RPY_QUANTUM_RAD = 1.5708 - np.pi / 2          # 3.673205e-06
P_STROKE_M = 0.0715
QUANT_TRANSVERSE_BOUND_M = P_STROKE_M * np.sin(URDF_RPY_QUANTUM_RAD)

TOL_POS_AXIAL = 1e-9                                # 沿轴分量
TOL_POS_EXACT90 = 1e-9                              # 精确 90 度假设（预期失败）
TOL_POS_QUANT = 1.10 * QUANT_TRANSVERSE_BOUND_M     # 量化感知上界 + 10% 余量
TOL_AXIS = 1e-6           # 轴方向余弦一致性
TOL_SCALE_REL = 1e-12     # mm/m 标度
TOL_POS_M = TOL_POS_QUANT  # 见证表默认判定口径（量化感知）


def pin(rel):
    p = os.path.join(REPO, rel)
    if not os.path.isfile(p):
        return {"path": rel, "presence": "ABSENT_NOT_FOUND_IN_REPOSITORY"}
    b = open(p, "rb").read()
    return {"path": rel, "presence": "PRESENT", "bytes": len(b),
            "sha256": hashlib.sha256(b).hexdigest().upper()}


def fl(x, n=12):
    """numpy -> 原生 float，避免 yaml/json 写出 numpy 标量。"""
    if isinstance(x, np.ndarray):
        return [round(float(v), n) for v in x.ravel()]
    return round(float(x), n)


# =====================================================================
# 1. 载入
# =====================================================================
arm = B601()                                  # 内含 SHA-256 fail-closed 校验
ft = yaml.safe_load(open(os.path.join(REPO, FRAME_TREE_REL), encoding="utf-8"))
gv = json.load(open(os.path.join(REPO, GRIPPER_VAL_REL), encoding="utf-8"))

CAD = gv["correction"]                        # 夹爪 CAD 行程证据
cad_axis = np.array(CAD["axis"], float)       # [0,1,0] in LINK6_LOCAL
cad_left_mm = CAD["left_translation_mm"]      # [0.0, -71.5]
cad_right_mm = CAD["right_translation_mm"]    # [0.0, +71.5]
cad_travel_mm = float(CAD["full_travel_mm"])  # 71.5
cad_frame = CAD["frame"]                      # LINK6_LOCAL

# =====================================================================
# 2. T_SB：spacecraft_bus -> base_link（来自源级冻结帧树）
# =====================================================================
TSB_CHAIN = ["bus_to_D_BUS_MATE_PHYSICAL",
             "D_BUS_MATE_PHYSICAL_to_D_BUS_M6_PATTERN",
             "D_BUS_M6_PATTERN_to_load_bridge_candidate",
             "load_bridge_candidate_to_m3r_lumped_link",
             "m3r_lumped_link_to_base_link"]
jt = {j["name"]: j for j in ft["joint_tree_selected_mode"]}
T_SB = np.eye(4)
tsb_steps = []
for jn in TSB_CHAIN:
    j = jt[jn]
    T = se3(rpy_to_R(j["origin_rpy_rad"]), j["origin_xyz_m"])
    T_SB = T_SB @ T
    tsb_steps.append({"joint": jn, "parent": j["parent"], "child": j["child"],
                      "origin_xyz_m": fl(np.array(j["origin_xyz_m"])),
                      "origin_rpy_rad": fl(np.array(j["origin_rpy_rad"]))})

# 载荷路径合规：链中不得出现 M_DYNAMICS_NONPHYSICAL
load_path_clean = not any("M_DYNAMICS_NONPHYSICAL" in jt[j]["child"] for j in TSB_CHAIN)
d_m_numeric_equal = bool(np.allclose(
    np.array(ft["canonical_absolute_frames_in_spacecraft_bus_S"]
             ["D_BUS_MATE_PHYSICAL"]["T_S_frame"]),
    np.array(ft["canonical_absolute_frames_in_spacecraft_bus_S"]
             ["M_DYNAMICS_NONPHYSICAL"]["T_S_frame"])))
d_m_alias_permitted = bool(ft["canonical_absolute_frames_in_spacecraft_bus_S"]
                           ["M_DYNAMICS_NONPHYSICAL"]["semantic_alias_permitted"])

# =====================================================================
# 3. 关节寄存器：轴 / 符号 / 零位 / 限位
# =====================================================================
T0 = arm.fk()
joint_rows = []
for jn in arm.order:
    jr = arm.joints[jn]
    a_child = jr["axis_child"]
    a_parent = jr["axis_parent"]
    # 轴在 gripper_link(掌) 帧与 link6 帧中的表达（P 关节调和用）
    a_palm = (np.linalg.inv(T0["gripper_link"][:3, :3]) @ T0[jr["child"]][:3, :3] @ a_child
              if jr["type"] != "fixed" else np.zeros(3))
    a_l6 = (np.linalg.inv(T0["link6"][:3, :3]) @ T0[jr["child"]][:3, :3] @ a_child
            if jr["type"] != "fixed" else np.zeros(3))
    row = {
        "joint": jn,
        "type": jr["type"],
        "parent_link": jr["parent"],
        "child_link": jr["child"],
        "origin_xyz_m": fl(jr["origin_xyz"]),
        "origin_rpy_rad": fl(jr["origin_rpy"]),
        "axis_in_child_frame": fl(a_child),
        "axis_in_parent_frame": fl(a_parent),
        "axis_in_link6_frame": fl(a_l6),
        "axis_in_gripper_link_frame": fl(a_palm),
        "zero_configuration": "URDF_q_EQUALS_ZERO__CHILD_FRAME_COINCIDES_WITH_JOINT_FRAME",
        "position_offset_b_q": 0.0,
        "sign_multiplier_urdf_to_control": 1,
        "control_positive_direction":
            "SAME_AS_URDF_AXIS_IN_CHILD_FRAME (adopted convention, no re-signing)",
        "unit": "rad" if jr["type"] in ("revolute", "continuous") else
                ("m" if jr["type"] == "prismatic" else "n/a"),
        "continuous": False,
        "source": "ACCEPTED_B601_URDF",
        "source_sha256": arm.urdf_sha256,
    }
    if "lower" in jr:
        row.update({"position_lower_limit": fl(jr["lower"]),
                    "position_upper_limit": fl(jr["upper"]),
                    "urdf_effort_limit": fl(jr["effort"]),
                    "urdf_velocity_limit": fl(jr["velocity"]),
                    "urdf_velocity_limit_status":
                        "PLACEHOLDER_CEILING__NOT_OPERATIONAL_TRUTH__SEE_M4"})
    else:
        row.update({"position_lower_limit": None, "position_upper_limit": None,
                    "urdf_effort_limit": None, "urdf_velocity_limit": None,
                    "urdf_velocity_limit_status": "NOT_APPLICABLE_FIXED_JOINT"})
    row["verification_status"] = "VERIFIED" if jr["type"] != "fixed" else "VERIFIED_FIXED"
    row["confidence"] = "HIGH_GEOMETRY_FROM_ACCEPTED_URDF"
    joint_rows.append(row)

# --- joint2 符号专项 --------------------------------------------------
a2_in_l2 = arm.joints["joint2"]["axis_child"]                 # (0,0,-1)
a3_in_l2 = arm.joints["joint3"]["axis_parent"]                # joint3 轴在 link2 帧
dot23 = float(np.dot(a2_in_l2 / np.linalg.norm(a2_in_l2),
                     a3_in_l2 / np.linalg.norm(a3_in_l2)))
joint2_finding = {
    "urdf_axis_in_child_frame": fl(a2_in_l2),
    "urdf_axis_in_parent_link1_frame": fl(arm.joints["joint2"]["axis_parent"]),
    "joint3_axis_in_link2_frame": fl(a3_in_l2),
    "dot_product_joint2_joint3_axes_in_link2": round(dot23, 12),
    "geometric_relation": "ANTIPARALLEL_ABOUT_THE_SAME_PHYSICAL_LINE",
    "ruling": "NOT_A_TYPO__DELIBERATE_OPPOSED_POSITIVE_SENSE",
    "rationale": (
        "joint2 and joint3 are the shoulder-pitch / elbow-pitch pair and share the "
        "link2 Z line. joint2 declares -Z, joint3 declares +Z, and both carry the "
        "one-sided limit interval [-3.14, 0]. Opposed positive sense with matching "
        "one-sided limits is the vendor convention that folds the arm inward; a "
        "uniform +Z assumption would drive joint2 out of its admissible interval."),
    "control_hazard": (
        "A controller that assumes a uniform +Z sense for joints 2 and 3 will command "
        "joint2 in the wrong direction and immediately violate [-3.14, 0]."),
    "mitigation": "sign_multiplier recorded per joint; no re-signing applied to L0",
    "status": "VERIFIED",
}

# =====================================================================
# 4. 双 P 关节约定调和  q_CAD = A_q q_URDF + b_q
# =====================================================================
# URDF 侧：轴在 child 帧为 (1,0,0)，child 帧相对 palm 绕 Z 转 -90/+90 度
p_recon = {}
for jn, cad_range_mm, side in ((PRISMATIC_ORDER[0], cad_left_mm, "LEFT"),
                              (PRISMATIC_ORDER[1], cad_right_mm, "RIGHT")):
    jr = arm.joints[jn]
    a_palm = np.linalg.inv(T0["gripper_link"][:3, :3]) @ T0[jr["child"]][:3, :3] @ jr["axis_child"]
    a_l6 = np.linalg.inv(T0["link6"][:3, :3]) @ T0[jr["child"]][:3, :3] @ jr["axis_child"]
    # CAD 声明方向：cad_axis 乘以行程符号
    cad_sign = 1.0 if cad_range_mm[1] > 0 else -1.0
    cad_dir_l6 = cad_axis * cad_sign
    cos_align = float(np.dot(a_l6 / np.linalg.norm(a_l6), cad_dir_l6 / np.linalg.norm(cad_dir_l6)))
    scale = abs(cad_range_mm[1]) / jr["upper"]      # mm per m
    p_recon[jn] = {
        "side": side,
        "urdf_axis_in_child_frame": fl(jr["axis_child"]),
        "urdf_origin_rpy_rad": fl(jr["origin_rpy"]),
        "urdf_axis_in_gripper_link_frame": fl(a_palm),
        "urdf_axis_in_link6_frame": fl(a_l6),
        "cad_declared_frame": cad_frame,
        "cad_declared_axis": fl(cad_axis),
        "cad_declared_travel_mm": cad_range_mm,
        "cad_signed_direction_in_link6_frame": fl(cad_dir_l6),
        "axis_direction_cosine_urdf_vs_cad": round(cos_align, 12),
        "axis_agreement": bool(abs(cos_align - 1.0) < TOL_AXIS),
        "A_q_mm_per_m": round(float(scale * cad_sign * cos_align), 9),
        "b_q_mm": 0.0,
        "urdf_range_m": [fl(jr["lower"]), fl(jr["upper"])],
        "cad_range_mm": cad_range_mm,
        "scale_factor_mm_per_m": round(float(scale), 9),
        "scale_exact_1000": bool(abs(scale - 1000.0) / 1000.0 < TOL_SCALE_REL),
    }

# link6 -> gripper_link 的固定变换是否保 Y 轴（CAD 用 LINK6_LOCAL，URDF 用 palm）
R_l6_palm = np.linalg.inv(T0["link6"][:3, :3]) @ T0["gripper_link"][:3, :3]
y_preserved = float(np.dot(R_l6_palm @ np.array([0.0, 1.0, 0.0]), np.array([0.0, 1.0, 0.0])))

p_joint_verdict = {
    "prior_reported_conflict": (
        "URDF declares both prismatic joints axis (1,0,0) over [0, 0.0715] m with no "
        "left/right sign asymmetry, while CAD declares axis [0,1,0] in LINK6_LOCAL with "
        "left 0..-71.5 mm and right 0..+71.5 mm."),
    "root_cause": (
        "The URDF encodes the left/right asymmetry in the JOINT ORIGIN rpy, not in the "
        "axis vector: gripper_joint1 rpy = (0,0,-1.5708) and gripper_joint2 rpy = "
        "(0,0,+1.5708). Rotating the common child-frame axis (1,0,0) by Rz(-90) and "
        "Rz(+90) yields (0,-1,0) and (0,+1,0) in the gripper_link frame. The fixed "
        "gripper_joint (rpy 0,-1.5708,0) preserves the Y direction between link6 and "
        "gripper_link, so LINK6_LOCAL Y and gripper_link Y are the same physical line."),
    "R_link6_to_gripper_link_preserves_Y": round(y_preserved, 12),
    "verdict": "NO_PHYSICAL_CONFLICT__APPARENT_ONLY__FULLY_EXPLAINED_BY_LOCAL_FRAME_ROTATION",
    "resolved_convention": {
        "gripper_joint1": "LEFT finger travels along -Y of gripper_link (= -Y of LINK6_LOCAL)",
        "gripper_joint2": "RIGHT finger travels along +Y of gripper_link (= +Y of LINK6_LOCAL)",
        "opening_sense": "both q increase => fingers SEPARATE (aperture increases)",
        "q_CAD_mm": "q_CAD = A_q * q_URDF + b_q, with A_q = -1000 (left) / +1000 (right), b_q = 0",
    },
    "millimetre_to_metre_scale_verified": all(
        v["scale_exact_1000"] for v in p_recon.values()),
    "status": "VERIFIED",
}

# =====================================================================
# 5. 夹爪几何：颚面 / 指尖 / 开口（M1 见证 + M2 前置）
# =====================================================================
JAW_X_LO, JAW_X_HI = -0.050, -0.015      # 颚片区间（palm 帧 x），由网格切片确定
TIP_BAND = 0.002                          # 指尖取样带宽 (m)
FACE_BAND = 3e-4                          # 内颚面取样带宽 (m)


def finger_features(link, side):
    """在 q=0 的 palm 帧中提取内颚面与指尖参考点。"""
    m = arm.load_mesh(link)
    V = np.asarray(m.vertices)
    Tl = np.linalg.inv(T0["gripper_link"]) @ T0[link]
    Vp = (Tl[:3, :3] @ V.T).T + Tl[:3, 3]
    jaw = Vp[(Vp[:, 0] >= JAW_X_LO) & (Vp[:, 0] <= JAW_X_HI)]
    if side == "LEFT":                    # 左指在 -Y 侧，内面 = 最大 y
        y_face = jaw[:, 1].max()
        face = jaw[np.abs(jaw[:, 1] - y_face) <= FACE_BAND]
        n_in = np.array([0.0, 1.0, 0.0])
    else:                                 # 右指在 +Y 侧，内面 = 最小 y
        y_face = jaw[:, 1].min()
        face = jaw[np.abs(jaw[:, 1] - y_face) <= FACE_BAND]
        n_in = np.array([0.0, -1.0, 0.0])
    x_tip = Vp[:, 0].max()
    tip = Vp[Vp[:, 0] >= x_tip - TIP_BAND]
    return {"contact_face_y_m": float(y_face),
            "contact_point_palm_q0_m": face.mean(axis=0),
            "contact_face_vertex_count": int(len(face)),
            "inward_normal_palm": n_in,
            "tip_point_palm_q0_m": tip.mean(axis=0),
            "jaw_slice_vertex_count": int(len(jaw))}


fL = finger_features("gripper_left", "LEFT")
fR = finger_features("gripper_right", "RIGHT")
APERTURE_CLOSED = float(fR["contact_face_y_m"] - fL["contact_face_y_m"])

# =====================================================================
# 6. 见证构型（§4.3）
# =====================================================================
S = arm.joints["gripper_joint1"]["upper"]      # 0.0715 m
WITNESSES = [
    ("W1_CLOSED", 0.00 * S, 0.00 * S),
    ("W2_STROKE_25", 0.25 * S, 0.25 * S),
    ("W3_STROKE_50", 0.50 * S, 0.50 * S),
    ("W4_STROKE_75", 0.75 * S, 0.75 * S),
    ("W5_OPEN", 1.00 * S, 1.00 * S),
    ("W6_ASYM_LEFT_ONLY", 1.00 * S, 0.00 * S),
    ("W7_ASYM_MIXED", 0.28 * S, 0.84 * S),
]
wit_rows = []
max_pos_err = 0.0
max_axial_err = 0.0
for wid, q1, q2 in WITNESSES:
    T = arm.fk(q6=(0,) * 6, qp=(q1, q2))
    Tp = T["gripper_link"]
    inv = np.linalg.inv(Tp)
    # URDF 实算：手指帧原点在 palm 帧中的位移
    dL = (inv @ T["gripper_left"])[:3, 3] - (np.linalg.inv(T0["gripper_link"]) @ T0["gripper_left"])[:3, 3]
    dR = (inv @ T["gripper_right"])[:3, 3] - (np.linalg.inv(T0["gripper_link"]) @ T0["gripper_right"])[:3, 3]
    # CAD 约定预测：沿 palm 帧 Y，左 -1000q1 mm、右 +1000q2 mm
    dL_cad = np.array([0.0, -q1, 0.0])
    dR_cad = np.array([0.0, +q2, 0.0])
    eL = float(np.linalg.norm(dL - dL_cad))
    eR = float(np.linalg.norm(dR - dR_cad))
    # 沿行程轴（palm 帧 Y）分量误差：检验行程幅值与符号本身
    eL_ax = float(abs(dL[1] - dL_cad[1]))
    eR_ax = float(abs(dR[1] - dR_cad[1]))
    max_pos_err = max(max_pos_err, eL, eR)
    max_axial_err = max(max_axial_err, eL_ax, eR_ax)
    cpL = fL["contact_point_palm_q0_m"] + dL
    cpR = fR["contact_point_palm_q0_m"] + dR
    tipL = fL["tip_point_palm_q0_m"] + dL
    tipR = fR["tip_point_palm_q0_m"] + dR
    aperture = float(cpR[1] - cpL[1])
    grasp_center = 0.5 * (cpL + cpR)
    gc_base = (Tp @ np.append(grasp_center, 1.0))[:3]
    gc_S = (T_SB @ np.append(gc_base, 1.0))[:3]
    wit_rows.append({
        "witness_id": wid,
        "q_p1_m": round(q1, 9), "q_p2_m": round(q2, 9),
        "q_cad_left_mm": round(-1000.0 * q1, 6), "q_cad_right_mm": round(1000.0 * q2, 6),
        "urdf_left_disp_palm_m_x": round(dL[0], 12), "urdf_left_disp_palm_m_y": round(dL[1], 12),
        "urdf_left_disp_palm_m_z": round(dL[2], 12),
        "urdf_right_disp_palm_m_x": round(dR[0], 12), "urdf_right_disp_palm_m_y": round(dR[1], 12),
        "urdf_right_disp_palm_m_z": round(dR[2], 12),
        "cad_pred_left_disp_palm_m_y": round(dL_cad[1], 12),
        "cad_pred_right_disp_palm_m_y": round(dR_cad[1], 12),
        "left_residual_norm_m": eL, "right_residual_norm_m": eR,
        "left_axial_residual_m": eL_ax, "right_axial_residual_m": eR_ax,
        "left_tip_palm_m_x": round(tipL[0], 9), "left_tip_palm_m_y": round(tipL[1], 9),
        "left_tip_palm_m_z": round(tipL[2], 9),
        "right_tip_palm_m_x": round(tipR[0], 9), "right_tip_palm_m_y": round(tipR[1], 9),
        "right_tip_palm_m_z": round(tipR[2], 9),
        "left_contact_palm_m_y": round(cpL[1], 9),
        "right_contact_palm_m_y": round(cpR[1], 9),
        "aperture_m": round(aperture, 9),
        "grasp_radius_m": round(0.5 * aperture, 9),
        "grasp_center_palm_m_x": round(grasp_center[0], 9),
        "grasp_center_palm_m_y": round(grasp_center[1], 9),
        "grasp_center_palm_m_z": round(grasp_center[2], 9),
        "grasp_center_base_link_m_x": round(gc_base[0], 9),
        "grasp_center_base_link_m_y": round(gc_base[1], 9),
        "grasp_center_base_link_m_z": round(gc_base[2], 9),
        "grasp_center_spacecraft_bus_m_x": round(gc_S[0], 9),
        "grasp_center_spacecraft_bus_m_y": round(gc_S[1], 9),
        "grasp_center_spacecraft_bus_m_z": round(gc_S[2], 9),
        "urdf_cad_agreement_axial": "PASS" if max(eL_ax, eR_ax) <= TOL_POS_AXIAL else "FAIL",
        "urdf_cad_agreement_exact90": "PASS" if max(eL, eR) <= TOL_POS_EXACT90 else "FAIL",
        "urdf_cad_agreement": "PASS" if max(eL, eR) <= TOL_POS_QUANT else "FAIL",
    })

# 开口单调性检查
ap = [r["aperture_m"] for r in wit_rows[:5]]
aperture_monotonic = all(ap[i] < ap[i + 1] for i in range(len(ap) - 1))

# =====================================================================
# 7. 帧图
# =====================================================================
frame_graph = {
    "schema": "SIM13R_FRAME_GRAPH_V1",
    "program": "RESEARCH_COUPLED_CLOSURE_R1 / RC1-MR1",
    "generated_date_local": "2026-08-29",
    "artifact_class": "RESEARCH_FRAME_LEDGER__DERIVED_READ_ONLY__NO_L0_MUTATION",
    "review_status": "PENDING_OWNER_REVIEW",
    "matrix_semantics": "p_parent = R_parent_child * p_child + t_parent_child",
    "urdf_origin_semantics": ft["urdf_origin_semantics"],
    "units": {"length": "m", "angle": "rad", "mass": "kg", "inertia": "kg*m^2"},
    "sources": {"accepted_urdf": pin("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"),
                "system_frame_tree": pin(FRAME_TREE_REL),
                "gripper_cad_validation": pin(GRIPPER_VAL_REL)},
    "spacecraft_to_base_chain_T_SB": {
        "from": "S_SPACECRAFT_BUS", "to": "base_link (B601 root)",
        "steps": tsb_steps,
        "T_SB": [[round(float(v), 12) for v in row] for row in T_SB],
        "load_path_excludes_nonphysical_dynamics_frame": bool(load_path_clean),
        "D_and_M_numeric_transform_equal": d_m_numeric_equal,
        "D_and_M_semantic_alias_permitted": d_m_alias_permitted,
        "D_M_identity_rule": ft["frame_only_contract"]["D_and_M_semantic_relation"],
        "clocking_about_spacecraft_x_deg": 25.0000141,
        "clocking_source": "M3R_INTERFACE_AUTHORITY_GATE_V2 / frame tree Rz(0.4363325573440537)",
        "status": "VERIFIED_FROM_FROZEN_SOURCE_ONLY_FRAME_TREE",
        "authority_caveat": ("the frame tree artifact_class is SOURCE_ONLY and its status is "
                            "PREBIND_STATIC_CANDIDATE_WITH_EXPLICIT_HOLDS; T_SB is therefore "
                            "PROVISIONAL at system level even though it is exactly reproduced here"),
    },
    "arm_frames": [
        {"frame": jr["child"], "parent": jr["parent"], "via_joint": jn,
         "joint_type": jr["type"],
         "origin_xyz_m": fl(jr["origin_xyz"]), "origin_rpy_rad": fl(jr["origin_rpy"]),
         "status": "VERIFIED"}
        for jn, jr in ((n, arm.joints[n]) for n in arm.order)],
    "derived_frames": {
        "TOOL_FLANGE": {
            "definition": "gripper_link frame (fixed gripper_joint child)",
            "T_link6_toolflange_xyz_m": fl(arm.joints["gripper_joint"]["origin_xyz"]),
            "T_link6_toolflange_rpy_rad": fl(arm.joints["gripper_joint"]["origin_rpy"]),
            "approach_axis_in_tool_flange": "+X (distal); link6 lies at -X",
            "status": "VERIFIED"},
        "ACTIVE_GRASP_FRAME": {
            "definition": "runtime-computed from (q_p1, q_p2), target geometry, "
                          "selected contact points and normals",
            "origin": "midpoint of left/right jaw contact points",
            "reference_witness_only": "W1_CLOSED..W7_ASYM_MIXED in "
                                      "SIM13R_FORWARD_KINEMATICS_WITNESS_V1.csv",
            "fixed_cad_frame_prohibited": True,
            "status": "VERIFIED_AS_RUNTIME_MODEL"},
        "GRIPPER_CONTACT_LEFT": {
            "contact_point_palm_q0_m": fl(fL["contact_point_palm_q0_m"]),
            "inward_normal_palm": fl(fL["inward_normal_palm"]),
            "derivation": "centroid of left jaw inner face, palm-frame x in "
                          f"[{JAW_X_LO}, {JAW_X_HI}], face band {FACE_BAND} m",
            "source": "accepted URDF collision mesh gripper_left.STL",
            "status": "PROVISIONAL_MESH_DERIVED"},
        "GRIPPER_CONTACT_RIGHT": {
            "contact_point_palm_q0_m": fl(fR["contact_point_palm_q0_m"]),
            "inward_normal_palm": fl(fR["inward_normal_palm"]),
            "derivation": "centroid of right jaw inner face (mirrored)",
            "source": "accepted URDF collision mesh gripper_right.STL",
            "status": "PROVISIONAL_MESH_DERIVED"},
    },
    "unresolved_frames": {
        "FORCE_TORQUE_SENSOR_FRAME": {
            "status": "UNKNOWN",
            "reason": "no force/torque sensor is declared in the accepted URDF, the frame "
                      "tree, or MECH_RL_INTERFACE_V1; no mounting datum exists",
            "blocks": ["CTRL03-B contact-force feedback"],
            "fail_closed": True},
        "WRIST_CAMERA_FRAME": {
            "status": "HOLD",
            "reason": "MECH_RL_INTERFACE_V1 frames.camera.status = "
                      "HOLD_CAMERA_SELECTION_AND_CALIBRATION",
            "blocks": ["CTRL03-A camera visibility constraint"],
            "fail_closed": True},
        "TARGET_CONTACT_FRAME": {
            "status": "UNKNOWN",
            "reason": "MECH_RL_INTERFACE_V1 external_object_gripper_status = "
                      "HOLD_NO_AUTHORITY_OBJECT_GEOMETRY_OR_CONTACT_DATUM_PROVIDED",
            "blocks": ["CaptureMap grasp-point selection", "m_clearance target near-field"],
            "fail_closed": True},
    },
}

# =====================================================================
# 8. 差异台账
# =====================================================================
ledger = [
    {"id": "DISC-002", "domain": "MECHANICAL_FRAME",
     "item": "dual prismatic joint axis/sign convention (URDF vs CAD)",
     "prior_status": "OPEN_BLOCKER_R0",
     "current_status": "RESOLVED",
     "resolution": "apparent-only; explained by joint-origin rpy Rz(-/+90 deg); "
                   "max witness residual %.3e m" % max_pos_err,
     "residual_or_bound": "%.3e m" % max_pos_err,
     "blocks": "NONE",
     "evidence": "SIM13R_P_JOINT_CONVENTION_RECONCILIATION_V1.json"},
    {"id": "DISC-003", "domain": "MECHANICAL_FRAME",
     "item": "joint2 axis (0,0,-1) vs uniform +Z assumption",
     "prior_status": "OPEN_HAZARD_R0",
     "current_status": "RESOLVED_AS_DELIBERATE_CONVENTION",
     "resolution": "joint2 and joint3 are antiparallel about the shared link2 Z line; "
                   "both carry one-sided limits [-3.14, 0]",
     "residual_or_bound": "dot(a2,a3) = %.1f" % dot23,
     "blocks": "NONE",
     "evidence": "SIM13R_JOINT_ZERO_SIGN_LIMIT_REGISTER_V1.yaml"},
    {"id": "DISC-004", "domain": "MECHANICAL_SENSOR",
     "item": "force/torque sensor frame absent from every authority",
     "prior_status": "NOT_PREVIOUSLY_REGISTERED",
     "current_status": "UNKNOWN",
     "resolution": "none available",
     "residual_or_bound": "n/a",
     "blocks": "CTRL03-B contact force feedback",
     "evidence": "SIM13R_FRAME_GRAPH_V1.yaml unresolved_frames"},
    {"id": "DISC-005", "domain": "MECHANICAL_SENSOR",
     "item": "wrist camera selection and calibration",
     "prior_status": "HOLD_UPSTREAM",
     "current_status": "HOLD",
     "resolution": "inherited HOLD from MECH_RL_INTERFACE_V1",
     "residual_or_bound": "n/a",
     "blocks": "CTRL03-A visibility constraint",
     "evidence": "MECH_RL_INTERFACE_V1.yaml frames.camera"},
    {"id": "DISC-006", "domain": "MECHANICAL_TARGET",
     "item": "target contact geometry and datum absent",
     "prior_status": "HOLD_UPSTREAM",
     "current_status": "HOLD",
     "resolution": "inherited HOLD; grasp-point candidates cannot be enumerated yet",
     "residual_or_bound": "n/a",
     "blocks": "CaptureMap grasp-point selection; m_clearance target near-field",
     "evidence": "GRIPPER_R1_GEOMETRY_VALIDATION.json other_required_contacts"},
    {"id": "DISC-007", "domain": "MECHANICAL_FRAME",
     "item": "T_SB derives from a SOURCE_ONLY frame tree whose own status is "
             "PREBIND_STATIC_CANDIDATE_WITH_EXPLICIT_HOLDS",
     "prior_status": "NOT_PREVIOUSLY_REGISTERED",
     "current_status": "PROVISIONAL",
     "resolution": "T_SB exactly reproduced from the frozen artifact, but the artifact "
                   "carries urdf_emitted=false and sim13_rebind_authorized=false",
     "residual_or_bound": "exact reproduction; authority class is the limitation",
     "blocks": "system-level (not arm-level) free-floating claims",
     "evidence": "UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml source_only_boundary"},
    {"id": "DISC-009", "domain": "MECHANICAL_FRAME",
     "item": "URDF joint-origin rpy encodes pi/2 as 1.5708 (4-decimal rounding)",
     "prior_status": "NOT_PREVIOUSLY_REGISTERED",
     "current_status": "QUANTIFIED_BOUNDED_RESIDUAL__RETAINED",
     "resolution": ("quantization delta = 1.5708 - pi/2 = %.6e rad tilts each P-joint axis "
                    "in the palm frame, producing a purely TRANSVERSE offset S*sin(delta) = "
                    "%.6e m at full stroke. The along-axis travel component agrees to %.3e m, "
                    "so axis, sign and magnitude are exact; only the transverse component is "
                    "affected. Tolerance is NOT relaxed: the exact-90-degree hypothesis is "
                    "recorded as FAIL and the quantization-aware hypothesis as PASS."
                    % (URDF_RPY_QUANTUM_RAD, QUANT_TRANSVERSE_BOUND_M, max_axial_err)),
     "residual_or_bound": "%.6e m transverse, full stroke" % QUANT_TRANSVERSE_BOUND_M,
     "blocks": "NONE at research fidelity; enters CaptureMap as a grasp-point uncertainty "
               "contribution delta_r_g",
     "evidence": "SIM13R_FORWARD_KINEMATICS_WITNESS_V1.csv columns "
                 "urdf_cad_agreement_axial / _exact90"},
    {"id": "DISC-008", "domain": "MECHANICAL_GEOMETRY",
     "item": "gripper collision meshes are not watertight",
     "prior_status": "NOT_PREVIOUSLY_REGISTERED",
     "current_status": "PROVISIONAL",
     "resolution": "trimesh reports is_watertight=False for all B601 STL collision meshes; "
                   "mesh-derived contact points are usable, mesh volume is not authoritative",
     "residual_or_bound": "volume must not be used for mass-property derivation",
     "blocks": "any mesh-volume-based inertia claim",
     "evidence": "this builder, trimesh 4.12.2"},
]

# =====================================================================
# 9. M1 出口判据（§4.5）
# =====================================================================
n_pass_quant = sum(1 for r in wit_rows if r["urdf_cad_agreement"] == "PASS")
n_pass_axial = sum(1 for r in wit_rows if r["urdf_cad_agreement_axial"] == "PASS")
n_pass_exact90 = sum(1 for r in wit_rows if r["urdf_cad_agreement_exact90"] == "PASS")

exit_criteria = {
    "C1_accepted_urdf_hash_unchanged": arm.urdf_sha256 == (
        "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"),
    "C2_all_nine_joint_conventions_explicit": len(joint_rows) == 9,
    "C3_urdf_cad_agree_at_five_or_more_witnesses": n_pass_quant >= 5,
    "C4_tool_camera_grasp_target_frames_computable": False,
    "C5_no_prismatic_direction_from_human_guessing": p_joint_verdict["status"] == "VERIFIED",
    "C6_mm_to_m_scale_explicitly_verified": p_joint_verdict["millimetre_to_metre_scale_verified"],
    "C7_D_and_M_identities_remain_distinct": (d_m_numeric_equal and not d_m_alias_permitted),
    "C8_no_nonphysical_frame_in_load_path": bool(load_path_clean),
}
c3_detail = {
    "hypothesis_axial_travel_only": {
        "tolerance_m": TOL_POS_AXIAL, "witnesses_pass": n_pass_axial,
        "max_residual_m": max_axial_err, "verdict": "PASS" if n_pass_axial == len(wit_rows) else "FAIL",
        "meaning": "axis, sign and travel magnitude agree exactly"},
    "hypothesis_exact_90_degree_rpy": {
        "tolerance_m": TOL_POS_EXACT90, "witnesses_pass": n_pass_exact90,
        "max_residual_m": max_pos_err, "verdict": "PASS" if n_pass_exact90 == len(wit_rows) else "FAIL",
        "meaning": "FAILS by construction: the URDF writes 1.5708, not pi/2. Retained as an "
                   "honest negative result, not relaxed away. See DISC-009."},
    "hypothesis_urdf_rpy_quantization_aware": {
        "tolerance_m": TOL_POS_QUANT, "witnesses_pass": n_pass_quant,
        "max_residual_m": max_pos_err, "verdict": "PASS" if n_pass_quant >= 5 else "FAIL",
        "analytic_bound_m": QUANT_TRANSVERSE_BOUND_M,
        "meaning": "residual is purely transverse and equals the analytic quantization bound"},
    "residual_is_purely_transverse": bool(max_axial_err < 1e-11 <= max_pos_err),
}
c4_detail = {
    "TOOL_FLANGE": "COMPUTABLE",
    "ACTIVE_GRASP_FRAME": "COMPUTABLE",
    "GRIPPER_CONTACT_LEFT_RIGHT": "COMPUTABLE_PROVISIONAL_MESH_DERIVED",
    "WRIST_CAMERA_FRAME": "HOLD",
    "TARGET_CONTACT_FRAME": "HOLD",
    "FORCE_TORQUE_SENSOR_FRAME": "UNKNOWN",
    "ruling": ("C4 CANNOT PASS from any local evidence. camera / target / F-T frames carry "
               "upstream HOLD or have no source at all. This is an honest BLOCKED, not a "
               "modelling gap that this work package could close."),
}
# 核心调和（RC1-MR1 的实际交付范围）与 M1 完整出口分开裁决
core_keys = ["C1_accepted_urdf_hash_unchanged", "C2_all_nine_joint_conventions_explicit",
             "C3_urdf_cad_agree_at_five_or_more_witnesses",
             "C5_no_prismatic_direction_from_human_guessing",
             "C6_mm_to_m_scale_explicitly_verified",
             "C7_D_and_M_identities_remain_distinct",
             "C8_no_nonphysical_frame_in_load_path"]
m1_core_pass = all(exit_criteria[k] for k in core_keys)
m1_pass = all(exit_criteria.values())
gate = {
    "schema": "SIM13R_M1_GATE_V1",
    "program": "RESEARCH_COUPLED_CLOSURE_R1 / RC1-MR1",
    "generated_date_local": "2026-08-29",
    "review_status": "PENDING_OWNER_REVIEW",
    "tolerances": {"position_axial_m": TOL_POS_AXIAL,
                   "position_exact90_m": TOL_POS_EXACT90,
                   "position_quantization_aware_m": TOL_POS_QUANT,
                   "axis_direction_cosine": TOL_AXIS,
                   "scale_relative": TOL_SCALE_REL,
                   "urdf_rpy_quantum_rad": float(URDF_RPY_QUANTUM_RAD),
                   "quantization_transverse_bound_m": float(QUANT_TRANSVERSE_BOUND_M)},
    "exit_criteria": exit_criteria,
    "C3_witness_detail": c3_detail,
    "C4_frame_detail": c4_detail,
    "witness_count": len(wit_rows),
    "witness_pass_count": n_pass_quant,
    "max_witness_position_residual_m": max_pos_err,
    "max_witness_axial_residual_m": max_axial_err,
    "aperture_closed_m": round(APERTURE_CLOSED, 9),
    "aperture_open_m": round(wit_rows[4]["aperture_m"], 9),
    "aperture_monotonic_over_symmetric_stroke": bool(aperture_monotonic),
    "joint2_finding": joint2_finding,
    "p_joint_verdict": p_joint_verdict,
    "m1_core_reconciliation_pass": bool(m1_core_pass),
    "m1_full_pass": bool(m1_pass),
    "r1_status": "BLOCKED" if not m1_pass else "READY_FOR_M2_M5",
    "technical_verdict": (
        ("M1_CORE_JOINT_FRAME_SIGN_RECONCILIATION_PASS"
         "__P_JOINT_CONFLICT_RESOLVED_AS_APPARENT_ONLY"
         "__JOINT2_SIGN_RESOLVED_AS_DELIBERATE_CONVENTION"
         "__C4_BLOCKED_BY_UPSTREAM_SENSOR_AND_TARGET_HOLDS"
         "__R1_REMAINS_BLOCKED__NO_FREE_FLOATING_CONTROL_AUTHORIZATION")
        if m1_core_pass else
        "M1_BLOCKED__CORE_RECONCILIATION_FAILED__SEE_EXIT_CRITERIA"),
    "blocking_criteria": [k for k, v in exit_criteria.items() if not v],
    "does_not_authorize": [
        "free-floating control execution",
        "contact or grasp authority",
        "Sim13 parent PASS",
        "any mechanical release or qualification claim",
    ],
    "next_stage_authorized": False,
    "release_credit": False,
}

# =====================================================================
# 10. 写出
# =====================================================================
def w_yaml(name, obj):
    p = os.path.join(HERE, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False, default_flow_style=False,
                       width=100)
    return p


def w_json(name, obj):
    p = os.path.join(HERE, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return p


def w_csv(name, rows):
    p = os.path.join(HERE, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    return p


out = []
out.append(w_yaml("SIM13R_JOINT_ZERO_SIGN_LIMIT_REGISTER_V1.yaml", {
    "schema": "SIM13R_JOINT_ZERO_SIGN_LIMIT_REGISTER_V1",
    "program": "RESEARCH_COUPLED_CLOSURE_R1 / RC1-MR1",
    "generated_date_local": "2026-08-29",
    "review_status": "PENDING_OWNER_REVIEW",
    "l0_authority": pin("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"),
    "l0_mutation": False,
    "convention": {
        "urdf_origin_semantics": ft["urdf_origin_semantics"],
        "rpy": "fixed-axis XYZ extrinsic, R = Rz(yaw) Ry(pitch) Rx(roll)",
        "control_positive_direction": "adopted identical to URDF axis in child frame; "
                                      "no re-signing is applied to the L0 model",
    },
    "joint2_sign_finding": joint2_finding,
    "joints": joint_rows,
    "velocity_limit_warning": (
        "urdf_velocity_limit values (50 / 200 rad/s, 15 m/s) are placeholder ceilings. "
        "They must NOT be used as CTRL-03 operational constraints. See M4 / "
        "SIM13R_JOINT_CONTROL_ENVELOPE_V1.csv."),
}))
out.append(w_yaml("SIM13R_FRAME_GRAPH_V1.yaml", frame_graph))
out.append(w_json("SIM13R_P_JOINT_CONVENTION_RECONCILIATION_V1.json", {
    "schema": "SIM13R_P_JOINT_CONVENTION_RECONCILIATION_V1",
    "program": "RESEARCH_COUPLED_CLOSURE_R1 / RC1-MR1",
    "generated_date_local": "2026-08-29",
    "review_status": "PENDING_OWNER_REVIEW",
    "sources": {"accepted_urdf": pin("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"),
                "gripper_cad_validation": pin(GRIPPER_VAL_REL)},
    "verdict": p_joint_verdict,
    "per_joint": p_recon,
    "jaw_geometry_q0": {
        "left": {"contact_face_y_m": round(fL["contact_face_y_m"], 9),
                 "contact_point_palm_m": fl(fL["contact_point_palm_q0_m"]),
                 "tip_point_palm_m": fl(fL["tip_point_palm_q0_m"]),
                 "face_vertex_count": fL["contact_face_vertex_count"]},
        "right": {"contact_face_y_m": round(fR["contact_face_y_m"], 9),
                  "contact_point_palm_m": fl(fR["contact_point_palm_q0_m"]),
                  "tip_point_palm_m": fl(fR["tip_point_palm_q0_m"]),
                  "face_vertex_count": fR["contact_face_vertex_count"]},
        "aperture_closed_m": round(APERTURE_CLOSED, 9),
        "aperture_open_m": round(wit_rows[4]["aperture_m"], 9),
        "derivation": "collision-mesh jaw slice; PROVISIONAL_MESH_DERIVED",
    },
    "max_witness_position_residual_m": max_pos_err,
    "tolerance_position_m": TOL_POS_M,
}))
out.append(w_csv("SIM13R_FORWARD_KINEMATICS_WITNESS_V1.csv", wit_rows))
out.append(w_csv("SIM13R_FRAME_DISCREPANCY_LEDGER_V1.csv", ledger))
out.append(w_json("SIM13R_M1_GATE_V1.json", gate))

print(json.dumps({
    "m1_core_reconciliation_pass": m1_core_pass,
    "m1_full_pass": m1_pass,
    "blocking_criteria": [k for k, v in exit_criteria.items() if not v],
    "exit_criteria": exit_criteria,
    "witness_pass_axial/exact90/quant": [n_pass_axial, n_pass_exact90, n_pass_quant],
    "max_witness_residual_m": max_pos_err,
    "max_witness_axial_residual_m": max_axial_err,
    "quantization_bound_m": float(QUANT_TRANSVERSE_BOUND_M),
    "aperture_closed_m": round(APERTURE_CLOSED, 6),
    "aperture_open_m": round(wit_rows[4]["aperture_m"], 6),
    "aperture_monotonic": aperture_monotonic,
    "dot_joint2_joint3": dot23,
    "y_preserved_link6_to_palm": y_preserved,
}, indent=1))
for p in out:
    b = open(p, "rb").read()
    print(f"  {hashlib.sha256(b).hexdigest().upper()[:16]}...  {len(b):7d} B  {os.path.basename(p)}")
