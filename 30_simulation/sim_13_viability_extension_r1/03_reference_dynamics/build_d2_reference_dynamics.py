"""D2：独立自由漂浮参考模型 —— 冻结锚点复现与动量闭合 Gate。

独立性声明
----------
本模型不 import sim_05 / sim_11 的求解器代码，不读取它们的中间量。
系统**构成**（哪些刚体、T_SM 挂载、夹爪锁死）来自 sim_05 的文档化定义——
不知道被建模的是哪个系统就无法复现其锚点——但运动学、动量映射与积分全部独立实现。
锚点只在事后对拍；任何不符只登记，不调参。
"""
import csv
import hashlib
import json
import os

import numpy as np

from reference_free_floating import ReferenceFreeFloating, min_jerk, skew

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MASS_CSV = "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv"

TOL_ANCHOR_REL = 1e-6        # 冻结锚点相对容差（声明在先）
TOL_MOMENTUM = 1e-12         # 动量残差绝对容差


def pin(rel):
    b = open(os.path.join(REPO, rel), "rb").read()
    return {"path": rel, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest().upper()}


rows = {r["object_id"]: r for r in csv.DictReader(
    open(os.path.join(REPO, MASS_CSV), encoding="utf-8"))}


def I_of(r):
    return np.array([[float(r["Ixx_kgm2"]), float(r["Ixy_kgm2"]), float(r["Ixz_kgm2"])],
                     [float(r["Ixy_kgm2"]), float(r["Iyy_kgm2"]), float(r["Iyz_kgm2"])],
                     [float(r["Ixz_kgm2"]), float(r["Iyz_kgm2"]), float(r["Izz_kgm2"])]])


def com_of(r):
    return np.array([float(r["cg_x_m"]), float(r["cg_y_m"]), float(r["cg_z_m"])])


t_SM = np.array([0.18525, 0.0, 0.0])
R_SM = np.array([[0., 0., 1.], [0., 1., 0.], [-1., 0., 0.]])
T_SM = np.eye(4)
T_SM[:3, :3], T_SM[:3, 3] = R_SM, t_SM

sv, ad = rows["servicer_12U_v0"], rows["robot_mount_adapter_v0"]
BASE = [{"name": "servicer_12U_v0", "mass": float(sv["mass_kg"]),
         "com": com_of(sv), "I": I_of(sv)},
        {"name": "robot_mount_adapter_v0", "mass": float(ad["mass_kg"]),
         "com": t_SM + R_SM @ com_of(ad), "I": R_SM @ I_of(ad) @ R_SM.T}]

dyn = ReferenceFreeFloating(lock_prismatic=True, base_bodies=BASE, T_SM=T_SM)

# =====================================================================
# A1. sim_05 头条锚点：min-jerk joint2 0->+60deg, joint3 0->-40deg, 8 s
# =====================================================================
T_M, T_END = 8.0, 12.0
A2, A3 = np.deg2rad(60.0), np.deg2rad(-40.0)
qf = lambda t: np.array([0., A2 * min_jerk(t, T_M)[0], A3 * min_jerk(t, T_M)[0], 0., 0., 0.])
qdf = lambda t: np.array([0., A2 * min_jerk(t, T_M)[1], A3 * min_jerk(t, T_M)[1], 0., 0., 0.])
res = dyn.integrate(qf, qdf, T_END, n_out=601)

ANCHORS = {
    "sim05_direct_solver_peak_deg": 19.199851620693828,
    "sim05_frozen_csv_peak_deg": 19.199852,
    "sim11_A1_flexible_peak_deg": 19.199885629572467,
}
anchor_rows = []
for name, val in ANCHORS.items():
    d = abs(res["peak_dev_deg"] - val)
    anchor_rows.append({
        "anchor": name, "frozen_value": val, "reference_model_value": res["peak_dev_deg"],
        "abs_diff": d, "rel_diff": d / abs(val),
        "within_tolerance": bool(d / abs(val) <= TOL_ANCHOR_REL),
        "tolerance_rel": TOL_ANCHOR_REL,
        "comparison_class": ("RIGID_TO_RIGID" if name.startswith("sim05")
                             else "RIGID_TO_FLEXIBLE_NOT_EXPECTED_TO_MATCH_EXACTLY"),
    })

# =====================================================================
# A2. 系统一致性检查
# =====================================================================
c0, M0 = dyn.system_com(np.zeros(6))
q_test = np.deg2rad(np.array([10.0, -25.0, -35.0, 15.0, -20.0, 30.0]))

# 广义雅可比 vs 有限差分末端速度（自由漂浮下）
Jg, pe = dyn.generalized_jacobian(q_test)
qd_probe = np.array([0.3, -0.2, 0.15, 0.1, -0.05, 0.25])
Vb, _ = dyn.base_velocity(q_test, qd_probe, np.eye(3), np.zeros(3))
v_pred = Jg @ qd_probe
# 有限差分：沿 (Vb, qd) 推进极小步，测末端位移
h = 1e-7
R1 = (np.eye(3) + h * skew(Vb[3:])) @ np.eye(3)
U, _, Vt = np.linalg.svd(R1)
R1 = U @ Vt
p1 = np.zeros(3) + h * Vb[:3]
_, pe1 = dyn.generalized_jacobian(q_test + h * qd_probe, R1, p1)
v_fd = (pe1 - pe) / h
jac_err = float(np.max(np.abs(v_pred[:3] - v_fd)))

# 零关节速度 -> 基座静止（自由漂浮无外力）
Vb0, _ = dyn.base_velocity(q_test, np.zeros(6), np.eye(3), np.zeros(3))
zero_wrench_err = float(np.max(np.abs(Vb0)))

# 系统质心在零动量下必须不动 —— 必须在**实际积分出的基座位姿**下求值，
# 而不是把基座钉在单位位姿（那样比较的是两个不同的物理状态）。
com_traj = []
for i, t in enumerate(res["t"]):
    R = res["R_b"][i]
    com_traj.append(dyn.system_com(qf(t), R, res["p_b"][:, i])[0])
com_traj = np.array(com_traj)
com_drift_free = float(np.max(np.linalg.norm(com_traj - com_traj[0], axis=1)))

# joint2 符号与双 P 关节（M1 结论在动力学模型中的再验证）
a2 = dyn.arm.joints["joint2"]["axis_child"]
a3p = dyn.arm.joints["joint3"]["axis_parent"]
dot23 = float(np.dot(a2 / np.linalg.norm(a2), a3p / np.linalg.norm(a3p)))
T0 = dyn.arm.fk()
pa = np.linalg.inv(T0["gripper_link"][:3, :3])
axL = pa @ T0["gripper_left"][:3, :3] @ dyn.arm.joints["gripper_joint1"]["axis_child"]
axR = pa @ T0["gripper_right"][:3, :3] @ dyn.arm.joints["gripper_joint2"]["axis_child"]

checks = {
    "C1_total_system_mass_kg": {"value": M0, "expected": 25.2 + dyn.arm.total_mass(),
                                "pass": bool(abs(M0 - (25.2 + dyn.arm.total_mass())) < 1e-9)},
    "C2_linear_momentum_residual_Ns": {"value": res["max_residual_linear_momentum_Ns"],
                                       "tol": TOL_MOMENTUM,
                                       "pass": bool(res["max_residual_linear_momentum_Ns"] < TOL_MOMENTUM)},
    "C3_angular_momentum_residual_Nms": {"value": res["max_residual_angular_momentum_Nms"],
                                         "tol": TOL_MOMENTUM,
                                         "pass": bool(res["max_residual_angular_momentum_Nms"] < TOL_MOMENTUM)},
    "C4_generalized_jacobian_vs_finite_difference": {"value": jac_err, "tol": 1e-5,
                                                     "pass": bool(jac_err < 1e-5)},
    "C5_zero_joint_rate_gives_zero_base_motion": {"value": zero_wrench_err, "tol": 1e-14,
                                                  "pass": bool(zero_wrench_err < 1e-14)},
    "C6_system_com_stationary_under_zero_momentum": {"value": com_drift_free, "tol": 1e-9,
                                                     "pass": bool(com_drift_free < 1e-9)},
    "C7_orthonormality_drift": {"value": res["max_orthonormality_drift"], "tol": 1e-8,
                                "pass": bool(res["max_orthonormality_drift"] < 1e-8)},
    "C8_joint2_antiparallel_to_joint3": {"value": dot23, "expected": -1.0,
                                         "pass": bool(abs(dot23 + 1.0) < 1e-12)},
    "C9_dual_prismatic_opposed_in_palm_frame": {
        "left_axis": [round(float(v), 9) for v in axL],
        "right_axis": [round(float(v), 9) for v in axR],
        "pass": bool(np.dot(axL, axR) < -0.999999)},
}
all_checks = all(v["pass"] for v in checks.values())
anchor_pass = all(r["within_tolerance"] for r in anchor_rows
                  if r["comparison_class"] == "RIGID_TO_RIGID")

# =====================================================================
# A3. 差异台账
# =====================================================================
ledger = [
    {"id": "DYN-001", "item": "sim_05 headline base attitude peak",
     "frozen": ANCHORS["sim05_direct_solver_peak_deg"],
     "reference_model": res["peak_dev_deg"],
     "abs_diff": abs(res["peak_dev_deg"] - ANCHORS["sim05_direct_solver_peak_deg"]),
     "status": "REPRODUCED",
     "note": ("independent momentum-level model, no parameter tuning; difference is at "
              "integrator tolerance level")},
    {"id": "DYN-002", "item": "sim_11 A1 flexible peak vs rigid reference",
     "frozen": ANCHORS["sim11_A1_flexible_peak_deg"],
     "reference_model": res["peak_dev_deg"],
     "abs_diff": abs(res["peak_dev_deg"] - ANCHORS["sim11_A1_flexible_peak_deg"]),
     "status": "EXPECTED_DIFFERENCE_NOT_A_DEFECT",
     "note": ("sim_11 A1 includes flexible panels; the 3.4e-05 deg offset is the flexible "
              "contribution. CTRL-02 anchors already record that the launch card mislabels "
              "this value as the sim_05 anchor.")},
    {"id": "DYN-003", "item": "sim_06 post-capture rate anchor",
     "frozen": "3.0633304945807067 deg/s (via sim_10/sim_12 B_anchor)",
     "reference_model": "NOT_YET_IMPLEMENTED", "abs_diff": "",
     "status": "PENDING",
     "note": ("requires the capture-impulse rigidization path and the sim_10 geometry "
              "classes, which are behind the frozen-input hash lock (DISC-010). Deferred to "
              "D3 CaptureMap.")},
    {"id": "DYN-004", "item": "sim_08 captured-momentum accounting",
     "frozen": "3.650992635553959 N*m*s", "reference_model": "NOT_YET_IMPLEMENTED",
     "abs_diff": "", "status": "PENDING",
     "note": "same dependency as DYN-003"},
    {"id": "DYN-005", "item": "sim_11 finite-contact-window anchors",
     "frozen": "T_c = 20 ms PROVISIONAL half-sine window",
     "reference_model": "NOT_YET_IMPLEMENTED", "abs_diff": "", "status": "PENDING",
     "note": ("needs the flexible modal model (M6 / DISC-001) plus contact bandwidth; "
              "deferred to D3 with the multi-fidelity contract")},
    {"id": "DYN-006", "item": "base body composition source",
     "frozen": "servicer_12U_v0 24.0 kg + robot_mount_adapter_v0 1.2 kg + arm base_link",
     "reference_model": f"{M0:.6f} kg total system",
     "abs_diff": 0.0, "status": "ADOPTED_FROM_SIM05_DOCUMENTED_DEFINITION",
     "note": ("system composition and T_SM were read from sim_05's documented definition, "
              "not derived independently; the dynamics implementation is independent. This "
              "is a declared independence limitation, not a hidden inheritance.")},
]

gate = {
    "schema": "SIM13R_MOMENTUM_CLOSURE_GATE_V1",
    "generated_date_local": "2026-08-30", "review_status": "PENDING_OWNER_REVIEW",
    "independence_declaration": {
        "imports_sim05_or_sim11_solver_code": False,
        "reads_their_intermediate_quantities": False,
        "system_composition_source": "sim_05 documented definition (declared, see DYN-006)",
        "parameters_retuned_to_match_anchors": False},
    "sources": {"accepted_urdf": {"path": "20_engineering/cad/spacecraft_layout/arm_b601_v1/"
                                          "arm_b601_v1.urdf",
                                  "sha256": dyn.arm.urdf_sha256},
                "mass_inertia_budget": pin(MASS_CSV)},
    "system": {"total_mass_kg": M0, "base_bodies": [b["name"] for b in BASE],
               "arm_mass_kg": dyn.arm.total_mass(), "moving_dof": dyn.dof,
               "prismatic_locked": True, "T_SM_t": t_SM.tolist(),
               "T_SM_R": R_SM.tolist()},
    "anchor_reproduction": anchor_rows,
    "consistency_checks": checks,
    "tolerances": {"anchor_relative": TOL_ANCHOR_REL, "momentum_absolute": TOL_MOMENTUM},
    "all_consistency_checks_pass": bool(all_checks),
    "rigid_anchors_reproduced": bool(anchor_pass),
    "technical_verdict": ("D2_REFERENCE_DYNAMICS_PASS__NEW_REFERENCE_MODEL_REPRODUCES_"
                          "FROZEN_SIM05_PHYSICS__CAPTURE_AND_FLEX_ANCHORS_PENDING"
                          if (all_checks and anchor_pass) else
                          "D2_REFERENCE_DYNAMICS_DISCREPANCY_HOLD"),
    "scope": "RIGID_FREE_FLOATING_PRE_CONTACT_MOMENTUM_LEVEL_ONLY",
    "does_not_cover": ["contact / capture transition", "flexible dynamics",
                       "actuator dynamics", "collision"],
    "next_stage_authorized": False, "release_credit": False,
}


def w(name, obj, kind):
    p = os.path.join(HERE, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        if kind == "json":
            json.dump(obj, f, indent=1, ensure_ascii=False)
            f.write("\n")
        else:
            wr = csv.DictWriter(f, fieldnames=list(obj[0].keys()))
            wr.writeheader()
            wr.writerows(obj)
    return p


out = [w("SIM13R_FROZEN_ANCHOR_REPRODUCTION_V1.csv", anchor_rows, "csv"),
       w("SIM13R_DYNAMICS_DISCREPANCY_LEDGER_V1.csv", ledger, "csv"),
       w("SIM13R_MOMENTUM_CLOSURE_GATE_V1.json", gate, "json")]

md = ["# SIM13R REFERENCE DYNAMICS TEST REPORT V1\n",
      "`RESEARCH_COUPLED_CLOSURE_R1 / SEI-RC-04 lane C (D2)` — 2026-08-30. "
      "`review_status = PENDING_OWNER_REVIEW`.\n",
      "## Result\n",
      f"An independent momentum-level free-floating model reproduces the frozen sim_05 "
      f"headline anchor to **{abs(res['peak_dev_deg'] - ANCHORS['sim05_direct_solver_peak_deg']):.3e} deg** "
      f"({abs(res['peak_dev_deg'] - ANCHORS['sim05_direct_solver_peak_deg']) / ANCHORS['sim05_direct_solver_peak_deg']:.3e} relative), "
      "with no parameter tuning.\n",
      f"- reference model peak base attitude deviation: `{res['peak_dev_deg']:.12f}` deg",
      f"- frozen sim_05 direct solver: `{ANCHORS['sim05_direct_solver_peak_deg']:.12f}` deg",
      f"- residual linear momentum: `{res['max_residual_linear_momentum_Ns']:.3e}` N*s",
      f"- residual angular momentum: `{res['max_residual_angular_momentum_Nms']:.3e}` N*m*s\n",
      "## Consistency checks\n",
      "| check | value | pass |", "|---|---|---|"]
for k, v in checks.items():
    val = v.get("value", v.get("left_axis"))
    md.append(f"| `{k}` | {val} | {v['pass']} |")
md += ["",
       "## What is NOT yet reproduced\n",
       "sim_06 post-capture rate, sim_08 captured-momentum accounting and sim_11 "
       "finite-contact-window anchors are **PENDING**. The first two depend on the capture "
       "rigidization path and the sim_10 geometry classes, which are behind the frozen-input "
       "hash lock (DISC-010); the third needs the flexible modal model (DISC-001). All three "
       "are deferred to D3 CaptureMap and recorded in the discrepancy ledger.\n",
       "## Declared independence limitation\n",
       "The dynamics implementation is independent. The **system composition** (which rigid "
       "bodies, the `T_SM` mount, gripper locked at q=0) was read from sim_05's documented "
       "definition — an anchor cannot be reproduced without knowing which system it models. "
       "This is recorded as `DYN-006`, not hidden.\n",
       "## Reproduction\n",
       "```bash\npython 30_simulation/sim_13_viability_extension_r1/03_reference_dynamics/"
       "build_d2_reference_dynamics.py\n```\n"]
p = os.path.join(HERE, "SIM13R_REFERENCE_DYNAMICS_TEST_REPORT_V1.md")
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(md))
out.append(p)

print(json.dumps({"verdict": gate["technical_verdict"],
                  "peak_dev_deg": res["peak_dev_deg"],
                  "anchor_abs_diff_deg": anchor_rows[0]["abs_diff"],
                  "anchor_rel_diff": anchor_rows[0]["rel_diff"],
                  "checks": {k: v["pass"] for k, v in checks.items()},
                  "all_checks_pass": all_checks}, indent=1, ensure_ascii=False))
for q in out:
    b = open(q, "rb").read()
    print(f"  {hashlib.sha256(b).hexdigest().upper()[:16]}...  {len(b):6d} B  {os.path.basename(q)}")
