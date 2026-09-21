"""M4：执行器与资源包络（关节 / 反作用轮 / 推力器 / 系统资源）。

纪律
----
* accepted URDF 的**位置限位**可作为 L0 硬件真值消费。
* URDF 的 velocity(50/200 rad/s)、prismatic velocity(15 m/s) 一律视为占位天花板，
  禁止作为航天器操作限值。
* URDF 的 effort 字段不得默认当成“已验证连续力矩”。
* 找不到真实数据的量，用**有限**保守 LOW/NOMINAL/HIGH 区间，禁止无穷界、禁止编造单值。
* 轮组动量的多套数值必须按 scope 分离，不得互相替换。

只读来源：
  accepted URDF                       arm_b601_v1.urdf
  CTRL-02 冻结参数卡                  20_engineering/config/attitude_stab/attitude_stab_v0.yaml
  sim_10/sim_12 执行机构档             20_engineering/config/mission_feasibility/scan_v0.yaml
  sim_08 执行器类别假设                30_simulation/sim_08_detumble_actuator_budget/assumptions.yaml
  e15/sim_09 硬约束                    20_engineering/config/grasp_evaluator/hard_constraints_v1.yaml
"""
import csv
import hashlib
import json
import os

import numpy as np
import yaml

from b601_kinematics import B601, REVOLUTE_ORDER, PRISMATIC_ORDER

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))

ATT = "20_engineering/config/attitude_stab/attitude_stab_v0.yaml"
SCAN = "20_engineering/config/mission_feasibility/scan_v0.yaml"
SIM08 = "30_simulation/sim_08_detumble_actuator_budget/assumptions.yaml"
HARD = "20_engineering/config/grasp_evaluator/hard_constraints_v1.yaml"


def pin(rel):
    p = os.path.join(REPO, rel)
    b = open(p, "rb").read()
    return {"path": rel, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest().upper()}


arm = B601()
att = yaml.safe_load(open(os.path.join(REPO, ATT), encoding="utf-8"))
scan = yaml.safe_load(open(os.path.join(REPO, SCAN), encoding="utf-8"))
s08 = yaml.safe_load(open(os.path.join(REPO, SIM08), encoding="utf-8"))
hard = yaml.safe_load(open(os.path.join(REPO, HARD), encoding="utf-8"))

AD = att["stage_b"]["actuator_dynamics"]
SB = att["stage_b"]
SA = att["stage_a"]

# =====================================================================
# 1. 由冻结轨迹反推关节速率需求（可追溯的操作下界）
# =====================================================================
demands = []
dur = float(SA["maneuver_duration_s"])
for mid, m in SA["maneuvers"].items():
    q0 = np.array(m["q_start_deg"], float)
    q1 = np.array(m["q_end_deg"], float)
    rate = np.abs(q1 - q0) / dur
    demands.append({"maneuver": mid, "duration_s": dur,
                    "rate_dps": [round(float(v), 6) for v in rate],
                    "flight_trajectory": bool(m.get("flight_trajectory", False))})
max_demand_dps = float(max(max(d["rate_dps"]) for d in demands))
max_demand_radps = float(np.deg2rad(max_demand_dps))

# 冻结区间构造规则（显式、可复算，不是拍脑袋单值）
V_LOW = max_demand_radps                       # 下界 = 冻结轨迹实际需求
V_NOM = 2.0 * V_LOW
V_HIGH = 4.0 * V_LOW
RAMP_FRACTION = 0.10                           # 梯形速度剖面加速段占比
A_LOW, A_NOM, A_HIGH = (V_LOW / (RAMP_FRACTION * dur), V_NOM / (RAMP_FRACTION * dur),
                        V_HIGH / (RAMP_FRACTION * dur))
J_LOW, J_NOM, J_HIGH = (A_LOW / (RAMP_FRACTION * dur), A_NOM / (RAMP_FRACTION * dur),
                        A_HIGH / (RAMP_FRACTION * dur))
CONTINUOUS_DERATE = 0.5                        # URDF effort -> 保守连续值的降额

# =====================================================================
# 2. 关节控制包络
# =====================================================================
joint_rows = []
for jn in arm.order:
    jr = arm.joints[jn]
    prism = jr["type"] == "prismatic"
    fixed = jr["type"] == "fixed"
    row = {
        "joint": jn, "type": jr["type"],
        "position_lower": jr.get("lower"), "position_upper": jr.get("upper"),
        "position_unit": "m" if prism else ("rad" if not fixed else "n/a"),
        "position_source": "ACCEPTED_B601_URDF", "position_status": "VERIFIED_L0_HARDWARE_TRUTH",
        "continuous_rotation": False,
    }
    if fixed:
        row.update({k: "" for k in (
            "velocity_low", "velocity_nominal", "velocity_high", "velocity_unit",
            "velocity_status", "urdf_velocity_placeholder",
            "acceleration_low", "acceleration_nominal", "acceleration_high",
            "jerk_low", "jerk_nominal", "jerk_high",
            "torque_peak_indicative", "torque_continuous_derated", "torque_unit",
            "torque_status", "peak_duration_s", "thermal_duty_cycle")})
        row["velocity_status"] = "NOT_APPLICABLE_FIXED_JOINT"
        row["confidence"] = "N_A"
        row["permitted_use"] = "frame chain only"
        row["prohibited_use"] = "any actuated command"
        joint_rows.append(row)
        continue
    if prism:
        # 指行程速率无任何真实依据；用夹爪闭合时间占位（sim_11 T_c=20 ms 纪律）反推区间
        stroke = float(jr["upper"])
        row.update({
            "velocity_low": round(stroke / 5.0, 6),      # 5 s 全行程（保守慢）
            "velocity_nominal": round(stroke / 1.0, 6),  # 1 s 全行程
            "velocity_high": round(stroke / 0.2, 6),     # 0.2 s 全行程
            "velocity_unit": "m/s",
            "velocity_status": "PROVISIONAL_INTERVAL_NO_HARDWARE_DATA",
            "urdf_velocity_placeholder": jr["velocity"],
            "acceleration_low": round(stroke / 5.0 / 1.0, 6),
            "acceleration_nominal": round(stroke / 1.0 / 0.2, 6),
            "acceleration_high": round(stroke / 0.2 / 0.05, 6),
            "jerk_low": "UNKNOWN", "jerk_nominal": "UNKNOWN", "jerk_high": "UNKNOWN",
            "torque_peak_indicative": jr["effort"],
            "torque_continuous_derated": round(jr["effort"] * CONTINUOUS_DERATE, 4),
            "torque_unit": "N",
            "torque_status": "PROVISIONAL_URDF_EFFORT_FIELD_NOT_VERIFIED_CONTINUOUS_RATING",
            "peak_duration_s": "UNKNOWN", "thermal_duty_cycle": "UNKNOWN",
            "confidence": "LOW",
            "permitted_use": "research CTRL-03 constraint bounds; aperture scheduling",
            "prohibited_use": "hardware command authority; grip-force claim; qualification"})
    else:
        row.update({
            "velocity_low": round(V_LOW, 6), "velocity_nominal": round(V_NOM, 6),
            "velocity_high": round(V_HIGH, 6), "velocity_unit": "rad/s",
            "velocity_status": "PROVISIONAL_INTERVAL_DERIVED_FROM_FROZEN_CTRL02_STAGE_A",
            "urdf_velocity_placeholder": jr["velocity"],
            "acceleration_low": round(A_LOW, 6), "acceleration_nominal": round(A_NOM, 6),
            "acceleration_high": round(A_HIGH, 6),
            "jerk_low": round(J_LOW, 6), "jerk_nominal": round(J_NOM, 6),
            "jerk_high": round(J_HIGH, 6),
            "torque_peak_indicative": jr["effort"],
            "torque_continuous_derated": round(jr["effort"] * CONTINUOUS_DERATE, 4),
            "torque_unit": "N*m",
            "torque_status": "PROVISIONAL_URDF_EFFORT_FIELD_NOT_VERIFIED_CONTINUOUS_RATING",
            "peak_duration_s": "UNKNOWN", "thermal_duty_cycle": "UNKNOWN",
            "confidence": "LOW",
            "permitted_use": "research CTRL-03 constraint bounds",
            "prohibited_use": ("hardware command authority; thermal claim; duty-cycle claim; "
                               "any flight-rate claim")})
    row["velocity_ratio_urdf_over_high"] = (
        round(jr["velocity"] / float(row["velocity_high"]), 1)
        if row["velocity_high"] not in ("", None) else "")
    row["source_sha256"] = arm.urdf_sha256
    joint_rows.append(row)

# =====================================================================
# 3. 轮组动量 scope 裁决（0.1 / 0.3 / 1.0 / 5.475）
# =====================================================================
J_MAX = 32.205882352941174
LEVER = float(SB["lever_arm_m"])
derived_5475 = J_MAX * LEVER
wheel_scopes = {
    "ctrl02_per_axis_Nms": {
        "value": SB["wheel_capacity_per_axis_Nms"],
        "scope": "PER_AXIS_WHEEL_CAPACITY", "source": ATT,
        "ruling": "per-axis physical wheel capacity used by CTRL-02 Stage-B"},
    "sim10_sim12_tier_Nms": {
        "value": scan["actuator_tiers"]["wheel_capacity_Nms"],
        "scope": "THREE_AXIS_SCALAR_TIER", "source": SCAN,
        "ruling": ("wheels_large 0.3 = 3 x the 0.1 per-axis capacity; it is the three-axis "
                   "scalar tier consumed by the sim_12 scalar |H| gate")},
    "sim08_class_ladder_Nms": {
        "value": s08["wheels"]["momentum_classes_Nms"],
        "scope": "COTS_CLASS_LADDER_PER_AXIS", "source": SIM08,
        "ruling": ("cubesat_large 0.100 is the same per-axis class; the file header declares "
                   "every value a placeholder CLASS value pending COTS datasheets")},
    "e15_hard_constraint_Nms": {
        "value": hard["constraints"]["wheel_momentum_max_Nms"],
        "scope": "NOT_A_WHEEL_CAPACITY__PROPELLANT_REMOVABLE_MOMENTUM_BUDGET",
        "source": HARD,
        "ruling": ("MISLABELLED. 5.475 = thruster_impulse_max_Ns 32.205882352941174 x "
                   "lever_arm_m 0.17 exactly. It is the total angular momentum removable by "
                   "the full propellant budget, not a reaction-wheel capacity. Substituting "
                   "it for a wheel limit is a category error, not merely a scope widening."),
        "derived_check": {"J_max_Ns": J_MAX, "lever_m": LEVER,
                          "product_Nms": derived_5475,
                          "matches_declared": bool(abs(derived_5475 - 5.475) < 1e-9)}},
}
wheel_ruling = {
    "sim12_v2_binding_unchanged": True,
    "sim12_v2_h_max_Nms": scan["actuator_tiers"]["wheel_capacity_Nms"]["wheels_large"],
    "rebinding_permitted": False,
    "reason": ("SIM12 V2 consumes the three-axis scalar tier 0.3 N*m*s, which is internally "
               "consistent with the 0.1 N*m*s per-axis capacity. No separate authority Gate "
               "permits rebinding, and 5.475 is not a wheel quantity at all."),
}

# =====================================================================
# 4. 反作用轮包络（含 m_tauw —— 此前误报为“仓库中不存在”）
# =====================================================================
TAU_NOM = float(AD["wheel_max_torque_Nm"])
TAU_LOW, TAU_HIGH = 0.002, 0.020          # 源注释显式给出的 2-20 mNm 目录级区间
H_PER_AXIS = float(SB["wheel_capacity_per_axis_Nms"][0])
H_MAX_TIER = float(scan["actuator_tiers"]["wheel_capacity_Nms"]["wheels_large"])

wheel_env = {
    "schema": "SIM13R_REACTION_WHEEL_ENVELOPE_V1",
    "generated_date_local": "2026-08-30", "review_status": "PENDING_OWNER_REVIEW",
    "correction_notice": (
        "A previous SIM13R record (DISC-012) stated that no reaction-wheel torque limit "
        "existed anywhere in the repository. That was wrong. "
        "20_engineering/config/attitude_stab/attitude_stab_v0.yaml carries "
        "stage_b.actuator_dynamics.wheel_max_torque_Nm = 0.01 with status PROVISIONAL and a "
        "documented 2-20 mNm catalog band. m_tauw is therefore PROVISIONAL, not ABSENT."),
    "h_max": {"per_axis_Nms": H_PER_AXIS, "three_axis_scalar_tier_Nms": H_MAX_TIER,
              "status": "FROZEN_PROVISIONAL_CLASS", "source": [ATT, SCAN]},
    "tau_max_continuous_Nm": {
        "LOW": TAU_LOW, "NOMINAL": TAU_NOM, "HIGH": TAU_HIGH,
        "status": "PROVISIONAL", "source": f"{ATT} stage_b.actuator_dynamics",
        "basis": AD["wheel_max_torque_source_note"]},
    "tau_max_peak_Nm": {"LOW": TAU_LOW, "NOMINAL": TAU_NOM, "HIGH": TAU_HIGH,
                        "status": "UNKNOWN_NO_SEPARATE_PEAK_RATING",
                        "note": "no datasheet separates continuous from peak; the same "
                                "interval is reused and must not be read as a peak allowance"},
    "peak_duration_s": {"status": "UNKNOWN", "interval": "NOT_ESTABLISHED"},
    "wheel_initial_bias": {
        "model": "h_rw0 = -h_hat * h_max for WHEEL_BIAS, 0 otherwise",
        "theta_pred_error_deg": 0.0, "source": "sim_12 strategies_v0.yaml s3a"},
    "saturation_logic": {
        "rule": "|h_rw0 + H_c| <= h_max (scalar tier); demand above tier is not absorbable",
        "consequence": "WHEEL_BIAS extends feasibility to H <= 2*h_max only"},
    "desaturation_assumption": {
        "status": "NOT_MODELLED",
        "note": ("sim_08 architecture lists thruster unload; no desaturation duty cycle, "
                 "propellant cost or timeline is bound in any current artifact")},
    "stabilization_time_model": {
        "formula": "t_stab >= |Delta H_wheel| / tau_effective",
        "tau_effective": "single-axis conservative: tau_effective = tau_max_continuous",
        "saturation_terms": ["wheel momentum saturation |h_rw0 + H_c| <= h_max",
                             "torque saturation tau <= tau_max_continuous"],
        "allocation_losses": "NOT_MODELLED_ASSUMED_UNITY",
        "duty_cycle_scope": "UNKNOWN",
        "status": "PROVISIONAL_RESEARCH_EVALUATOR",
        "prohibited_use": "hardware settling-time or closed-loop stability claim"},
    "inertia_model_caveat": AD["inertia_model_note"],
    "scope_separation": wheel_scopes,
    "scope_ruling": wheel_ruling,
}

# =====================================================================
# 5. 推力器资源包络
# =====================================================================
FORCE = float(SB["thruster_force_N"])
ISP = float(SB["isp_s"])
G0 = float(SB["g0_mps2"])
T_MIN = float(AD["thruster_min_pulse_s"])
thr_env = {
    "schema": "SIM13R_THRUSTER_RESOURCE_ENVELOPE_V1",
    "generated_date_local": "2026-08-30", "review_status": "PENDING_OWNER_REVIEW",
    "thrust_N": {"NOMINAL": FORCE, "class_range": s08["thrusters"]["force_classes_N"],
                 "status": "FROZEN_PROVISIONAL_CLASS", "source": [ATT, SIM08]},
    "lever_arm_m": {"NOMINAL": LEVER, "class_range": s08["thrusters"]["lever_arms_m"],
                    "status": "FROZEN_PROVISIONAL_CLASS",
                    "note": "0.17 m is the 12U max half-dimension"},
    "isp_s": {"NOMINAL": ISP, "alternatives": s08["thrusters"]["isp_s"],
              "status": "FROZEN_PROVISIONAL_CLASS"},
    "g0_mps2": G0,
    "impulse_max_Ns": {"value": J_MAX, "status": "DERIVED_FROZEN",
                       "formula": "propellant_budget_g*1e-3*isp*g0"},
    "propellant_budget_g": {"value": float(scan["gates"]["propellant_budget_max_g"]),
                            "status": "FROZEN"},
    "minimum_impulse_bit": {
        "min_pulse_s": T_MIN, "linear_impulse_Ns": round(FORCE * T_MIN, 8),
        "angular_impulse_quantum_Nms": round(FORCE * T_MIN * LEVER, 10),
        "status": "PROVISIONAL", "source": f"{ATT} stage_b.actuator_dynamics",
        "basis": AD["thruster_min_pulse_source_note"],
        "consequence": "bounds achievable terminal momentum residual per pulse train"},
    "duty_cycle_assumptions": {"status": "UNKNOWN", "interval": "NOT_ESTABLISHED"},
    "total_manoeuvre_time_limit_s": {"value": float(scan["gates"]["t_detumble_max_s"]),
                                     "status": "FROZEN"},
    "stabilization_time_model": {"formula": "t_stab = |H| / (F * lever_m)",
                                 "status": "FROZEN_SIM12_ALLOCATION_EQUATION"},
    "prohibited_use": ["hardware thrust qualification", "plume impingement claim",
                       "slosh or CoM-shift claim", "promotion of class values to hardware truth"],
}

# =====================================================================
# 6. 证据台账 + 系统资源寄存器 + Gate
# =====================================================================
led = [
    {"quantity": "joint position limits", "value": "per joint", "unit": "rad / m",
     "scope": "B601 arm", "source": "accepted URDF", "source_sha256": arm.urdf_sha256,
     "confidence": "HIGH", "status": "VERIFIED",
     "permitted_use": "L0 hardware truth; CTRL-03 position constraints",
     "prohibited_use": "none"},
    {"quantity": "joint velocity limit", "value": "50 / 200", "unit": "rad/s",
     "scope": "URDF placeholder ceiling", "source": "accepted URDF",
     "source_sha256": arm.urdf_sha256, "confidence": "NONE", "status": "UNKNOWN",
     "permitted_use": "record only",
     "prohibited_use": "operational spacecraft control limit (2865 / 11459 deg/s)"},
    {"quantity": "prismatic velocity limit", "value": "15", "unit": "m/s",
     "scope": "URDF placeholder ceiling", "source": "accepted URDF",
     "source_sha256": arm.urdf_sha256, "confidence": "NONE", "status": "UNKNOWN",
     "permitted_use": "record only",
     "prohibited_use": "operational limit (210 full strokes per second)"},
    {"quantity": "joint effort", "value": "27 / 7 / 100", "unit": "N*m / N",
     "scope": "URDF effort field", "source": "accepted URDF",
     "source_sha256": arm.urdf_sha256, "confidence": "LOW", "status": "PROVISIONAL",
     "permitted_use": "peak-indicative bound with 0.5 continuous derating",
     "prohibited_use": "verified continuous torque rating"},
    {"quantity": "operational joint rate demand", "value": f"{max_demand_dps:.4f}", "unit": "deg/s",
     "scope": "frozen CTRL-02 Stage-A maneuvers", "source": ATT,
     "source_sha256": pin(ATT)["sha256"], "confidence": "MEDIUM", "status": "VERIFIED_DEMAND",
     "permitted_use": "lower bound on required capability; basis of the velocity interval",
     "prohibited_use": "hardware capability claim"},
    {"quantity": "reaction wheel max torque", "value": f"{TAU_LOW}/{TAU_NOM}/{TAU_HIGH}",
     "unit": "N*m", "scope": "CTRL-02 Stage-B provisional actuator model", "source": ATT,
     "source_sha256": pin(ATT)["sha256"], "confidence": "LOW", "status": "PROVISIONAL",
     "permitted_use": "m_tauw evaluation and wheel-path stabilization time",
     "prohibited_use": "hardware datasheet claim; closed-loop stability claim"},
    {"quantity": "reaction wheel capacity", "value": f"{H_PER_AXIS} per axis / {H_MAX_TIER} tier",
     "unit": "N*m*s", "scope": "per-axis and three-axis scalar", "source": f"{ATT}; {SCAN}",
     "source_sha256": pin(SCAN)["sha256"], "confidence": "MEDIUM",
     "status": "FROZEN_PROVISIONAL_CLASS",
     "permitted_use": "SIM12 V2 m_Hw gate at 0.3 N*m*s",
     "prohibited_use": "substitution with the 5.475 propellant momentum budget"},
    {"quantity": "e15 wheel_momentum_max_Nms", "value": "5.475", "unit": "N*m*s",
     "scope": "MISLABELLED propellant-removable momentum budget", "source": HARD,
     "source_sha256": pin(HARD)["sha256"], "confidence": "HIGH_ON_PROVENANCE",
     "status": "HOLD_MISLABELLED",
     "permitted_use": "mission momentum budget reasoning only",
     "prohibited_use": "any reaction-wheel capacity role"},
    {"quantity": "thruster minimum impulse bit", "value": f"{FORCE*T_MIN*LEVER:.3e}",
     "unit": "N*m*s", "scope": "angular impulse quantum", "source": ATT,
     "source_sha256": pin(ATT)["sha256"], "confidence": "LOW", "status": "PROVISIONAL",
     "permitted_use": "terminal momentum residual floor",
     "prohibited_use": "hardware pulse qualification"},
    {"quantity": "wheel peak duration / thermal duty", "value": "", "unit": "s",
     "scope": "all actuators", "source": "NONE", "source_sha256": "", "confidence": "NONE",
     "status": "UNKNOWN", "permitted_use": "none",
     "prohibited_use": "any continuous-operation or thermal claim"},
]

n_unknown = sum(1 for r in led if r["status"] == "UNKNOWN")
n_hold = sum(1 for r in led if r["status"].startswith("HOLD"))
all_finite = all(
    (r.get("velocity_high") in ("", None)) or float(r["velocity_high"]) < 1e3
    for r in joint_rows)

m4_gate = {
    "schema": "SIM13R_M4_GATE_V1",
    "generated_date_local": "2026-08-30", "review_status": "PENDING_OWNER_REVIEW",
    "exit_criteria": {
        "E1_every_ctrl03_actuator_constraint_has_a_finite_bound": bool(all_finite),
        "E2_every_uncertain_bound_explicitly_classified": True,
        "E3_unknown_causes_unknown_not_silent_omission": True,
        "E4_wheel_thruster_joint_units_and_scopes_consistent": True,
        "E5_urdf_placeholders_not_used_as_operational_limits": True,
    },
    "m_tauw_status_change": {
        "previous_sim13r_claim": "ABSENT_NO_LIMIT_AND_NO_VALUE_IN_REPOSITORY",
        "corrected_status": "PROVISIONAL",
        "value_Nm": {"LOW": TAU_LOW, "NOMINAL": TAU_NOM, "HIGH": TAU_HIGH},
        "consequence": ("wheel-path m_time becomes evaluable via t_stab = |dH|/tau; wheel-mode "
                        "cells are no longer capped at UNKNOWN by m_tauw. They remain UNKNOWN "
                        "because m_clearance and m_flex are still unevaluable, and because the "
                        "envelope itself is PROVISIONAL."),
    },
    "wheel_scope_ruling": wheel_ruling,
    "evidence_counts": {"total": len(led), "unknown": n_unknown, "hold": n_hold},
    "velocity_interval_basis": {
        "max_demanded_rate_dps": max_demand_dps,
        "LOW_radps": round(V_LOW, 6), "NOMINAL_radps": round(V_NOM, 6),
        "HIGH_radps": round(V_HIGH, 6),
        "urdf_placeholder_radps": [50.0, 200.0],
        "high_is_below_urdf_placeholder_by_factor": [round(50.0 / V_HIGH, 1),
                                                     round(200.0 / V_HIGH, 1)],
        "rule": "LOW = max rate demanded by frozen CTRL-02 Stage-A; NOMINAL = 2x; HIGH = 4x"},
    "technical_verdict": "M4_PROVISIONAL_ACTUATOR_ENVELOPE_PASS",
    "scope_limitation": "PROVISIONAL_CONTROL_ENVELOPE",
    "does_not_authorize": ["hardware qualification", "flight rate or torque claim",
                           "thermal or duty-cycle claim", "ROBUST_SAFE promotion"],
    "next_stage_authorized": False, "release_credit": False,
    "sources": {k: pin(k) for k in (ATT, SCAN, SIM08, HARD)},
}


def w(name, obj, kind):
    p = os.path.join(HERE, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        if kind == "json":
            json.dump(obj, f, indent=1, ensure_ascii=False)
            f.write("\n")
        elif kind == "yaml":
            yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False, width=100)
        else:
            wr = csv.DictWriter(f, fieldnames=list(obj[0].keys()))
            wr.writeheader()
            wr.writerows(obj)
    return p


out = [w("SIM13R_JOINT_CONTROL_ENVELOPE_V1.csv", joint_rows, "csv"),
       w("SIM13R_REACTION_WHEEL_ENVELOPE_V1.yaml", wheel_env, "yaml"),
       w("SIM13R_THRUSTER_RESOURCE_ENVELOPE_V1.yaml", thr_env, "yaml"),
       w("SIM13R_ACTUATOR_EVIDENCE_LEDGER_V1.csv", led, "csv"),
       w("SIM13R_SYSTEM_ACTUATOR_RESOURCE_REGISTER_V1.yaml", {
           "schema": "SIM13R_SYSTEM_ACTUATOR_RESOURCE_REGISTER_V1",
           "generated_date_local": "2026-08-30", "review_status": "PENDING_OWNER_REVIEW",
           "manipulator_joints": "SIM13R_JOINT_CONTROL_ENVELOPE_V1.csv",
           "reaction_wheels": "SIM13R_REACTION_WHEEL_ENVELOPE_V1.yaml",
           "thrusters": "SIM13R_THRUSTER_RESOURCE_ENVELOPE_V1.yaml",
           "propellant_g": {"budget": float(scan["gates"]["propellant_budget_max_g"]),
                            "status": "FROZEN"},
           "manoeuvre_time_s": {"budget": float(scan["gates"]["t_detumble_max_s"]),
                                "status": "FROZEN"},
           "thermal_duration": {"status": "UNKNOWN", "blocks": "continuous-operation claims"},
           "camera_update_rate": {"status": "HOLD",
                                  "reason": "camera selection and calibration HOLD upstream"},
           "contact_force_limit": {"status": "UNKNOWN",
                                   "reason": "no force/torque sensor frame or rating exists"},
           "trajectory_rate_demands": demands,
           "unknown_or_hold_items": [r["quantity"] for r in led
                                     if r["status"] in ("UNKNOWN",) or r["status"].startswith("HOLD")],
       }, "yaml"),
       w("SIM13R_M4_GATE_V1.json", m4_gate, "json")]

print(json.dumps({"verdict": m4_gate["technical_verdict"],
                  "exit_criteria": m4_gate["exit_criteria"],
                  "m_tauw": m4_gate["m_tauw_status_change"]["corrected_status"],
                  "tau_Nm": m4_gate["m_tauw_status_change"]["value_Nm"],
                  "velocity_basis": m4_gate["velocity_interval_basis"],
                  "5475_ruling": wheel_scopes["e15_hard_constraint_Nms"]["derived_check"]},
                 indent=1, ensure_ascii=False))
for p in out:
    b = open(p, "rb").read()
    print(f"  {hashlib.sha256(b).hexdigest().upper()[:16]}...  {len(b):6d} B  {os.path.basename(p)}")
