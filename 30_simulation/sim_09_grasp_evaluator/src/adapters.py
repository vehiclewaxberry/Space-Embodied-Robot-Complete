"""sim_09 -- read-only adapters onto the five validated solvers.

Every adapter IMPORTS the physics core (never copies it) and returns a
provenance record {module, commit, units, wall_time_ms}.

  capture        30_simulation/common/capture_impulse.py   rigidize / rigidize_point_contact
  base_reaction  30_simulation/sim_05_free_floating_arm/dynamics.py  FreeFloatingB601
  flexible       30_simulation/sim_07_ancf_flexible/{ancf_beam,sim_07a_task_response}.py
  actuator       30_simulation/sim_08 formulas (algebraic; cross-checked in t6 against
                 results/actuator_budget_sweep.csv)
  propagation    (see target_propagation.py -> 30_simulation/common/rigid_body.py)

Scene-placement convention (documented; mirrors sim_04/sim_06)
--------------------------------------------------------------
Scene inertial frame I: target CoM at the origin, translationally at rest.
  a_I  = R_T(t_c) @ approach_direction_target        (outward approach normal)
  R_IS = minimal rotation taking +X_S -> -a_I; if a_I is exactly +X the
         antiparallel tie-break is a pi rotation about +Z, i.e. diag(-1,-1,1)
         == the legacy R_flip of capture_impulse.build_capture_scenario.
  t_IS = r_g_I(t_c) - R_IS @ p_cap_S     with p_cap_S = configured capture
         point in S (the grasp point is station-kept at p_cap_S; GNC standoff
         assumption, config key scenario.capture_point_S).
Desired EE task in S:  p_des = p_cap_S,  tool z axis a_des = R_SI @ (-a_I)
(== +X_S by construction),  full 6D orientation R_des = R_SI @ R_T @ R_C @
Rx(pi)  (grasp frame C flipped so the tool z opposes the outward normal).

Chaser stack modes for the capture scenario:
  legacy_v0  chaser_stack() of capture_impulse (2-DOF placeholder stack,
             ANCHORING ONLY -- reproduces build_capture_scenario bit-exactly
             for the nominal +X candidate, test t1)
  b601       servicer 24 kg whole-craft + adapter 1.2 kg + real B601 arm at
             q_c (link_com_states + combine_inertials) -- E1 mainline.
"""
import _bootstrap  # noqa: F401
import os
import subprocess
import time

import numpy as np

from capture_impulse import (rigidize, rigidize_point_contact, junction_couple,
                             chaser_stack)
from rigid_body import load_object
from b601_model import (B601Arm, T_SM_4x4, transform_inertial, combine_inertials)
from dynamics import FreeFloatingB601, min_jerk
import target_propagation  # noqa: F401  (re-exported for evaluator provenance)

G0 = 9.80665                       # m/s^2 (same constant as sim_08)
ISP_S = {"cold_gas_60s": 60.0, "green_mono_220s": 220.0}   # sim_08 assumptions.yaml

_CACHE = {}


def repo_commit():
    if "commit" not in _CACHE:
        try:
            out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                 cwd=_bootstrap.REPO_ROOT, capture_output=True,
                                 text=True, timeout=10)
            _CACHE["commit"] = out.stdout.strip() or "unknown"
        except Exception:
            _CACHE["commit"] = "unknown"
    return _CACHE["commit"]


def provenance(module, units, t0):
    return {"module": module, "commit": repo_commit(), "units": units,
            "wall_time_ms": round(1000.0 * (time.time() - t0), 3)}


def get_arm():
    if "arm" not in _CACHE:
        _CACHE["arm"] = B601Arm()
    return _CACHE["arm"]


def get_dyn():
    if "dyn" not in _CACHE:
        _CACHE["dyn"] = FreeFloatingB601()
    return _CACHE["dyn"]


# ---------------- scene placement ----------------

def rotation_x_to(v):
    """Minimal rotation R with R @ e_x = v (unit). Antiparallel tie-break:
    pi about +Z -> diag(-1,-1,1), matching the legacy R_flip convention."""
    v = np.asarray(v, float)
    v = v / np.linalg.norm(v)
    c = float(v[0])                       # e_x . v
    if c > 1.0 - 1e-12:
        return np.eye(3)
    if c < -1.0 + 1e-12:
        return np.diag([-1.0, -1.0, 1.0])
    axis = np.cross(np.array([1.0, 0.0, 0.0]), v)
    axis /= np.linalg.norm(axis)
    K = np.array([[0.0, -axis[2], axis[1]],
                  [axis[2], 0.0, -axis[0]],
                  [-axis[1], axis[0], 0.0]])
    s = np.sqrt(max(1.0 - c * c, 0.0))
    return np.eye(3) + s * K + (1.0 - c) * (K @ K)


ROT_X_PI = np.diag([1.0, -1.0, -1.0])     # Rx(pi): flips grasp-frame z (and y)


def scene_placement(candidate, prop, p_cap_S):
    """Scene pose bookkeeping. Returns dict with a_I, R_IS, R_SI, t_IS and the
    desired EE task quantities in S (p_des, a_des, R_des)."""
    a_I = prop["R_T"] @ candidate.approach_direction_target
    a_I = a_I / np.linalg.norm(a_I)
    R_IS = rotation_x_to(-a_I)
    R_SI = R_IS.T
    p_cap_S = np.asarray(p_cap_S, float).reshape(3)
    t_IS = prop["r_g_I"] - R_IS @ p_cap_S
    R_C = candidate.grasp_pose_target[:3, :3]
    R_des_S = R_SI @ prop["R_T"] @ R_C @ ROT_X_PI
    return {"a_I": a_I, "R_IS": R_IS, "R_SI": R_SI, "t_IS": t_IS,
            "p_des_S": p_cap_S, "a_des_S": R_SI @ (-a_I), "R_des_S": R_des_S,
            "r_T_S": -(R_SI @ t_IS), "R_TS": R_SI @ prop["R_T"]}


# ---------------- capture (30_simulation/common/capture_impulse.py) ----------------

def b601_chaser_stack(q_c):
    """Whole-chaser rigid stack in S at arm configuration q_c:
    servicer_12U_v0 (24 kg whole-craft line) + robot_mount_adapter_v0 (1.2 kg,
    placed via frozen T_SM) + arm base_link + link1..6 (gripper merged).
    Returns (m, cg_S, I_S about cg, p_E_S)."""
    arm = get_arm()
    srv = load_object("servicer_12U_v0")
    adp = load_object("robot_mount_adapter_v0")
    parts = [(srv["mass"], np.asarray(srv["cg"], float), np.asarray(srv["I"], float)),
             transform_inertial(T_SM_4x4(), adp["mass"], adp["cg"], adp["I"]),
             arm.base_link_inertial_in_S()]
    for s in arm.link_com_states(q_c):
        parts.append((s["mass"], s["c"], s["I"]))
    m, cg, I = combine_inertials(parts)
    p_E_S = arm.fk(q_c)["T_E"][:3, 3]
    return m, cg, I, p_E_S


def general_capture_scenario(candidate, prop, placement, chaser_mode="b601", q_c=None):
    """bodies = [chaser, target] in the scene inertial frame at the capture
    instant. Target: attitude R_T(t_c) (inertia tensor co-rotated, inertia_scale
    applied), CoM at origin at rest, spinning at omega_I. Chaser: EE at the
    propagated grasp point, stack extending outward along +a_I, closing speed
    v_app along -a_I, attitude held (w = 0)."""
    r_g_I, a_I, R_IS = prop["r_g_I"], placement["a_I"], placement["R_IS"]
    ti = candidate.target_inertia
    I_T = np.asarray(ti["I"], float) * float(ti.get("inertia_scale", 1.0))
    R_T = prop["R_T"]
    target = {"m": float(ti["mass"]), "I": R_T @ I_T @ R_T.T,
              "r": np.zeros(3), "v": np.zeros(3), "w": prop["omega_I"]}

    if chaser_mode == "legacy_v0":
        # EXACT generalization of capture_impulse.build_capture_scenario:
        # r = r_g + A*(ee_x - com_x), I rotated by R_IS (== R_flip for +X).
        m_c, com_c, I_c, ee_x = chaser_stack()
        chaser = {"m": m_c, "I": R_IS @ I_c @ R_IS.T,
                  "r": r_g_I + a_I * (ee_x - com_c[0]),
                  "v": -candidate.approach_velocity * a_I, "w": np.zeros(3)}
        meta = {"chaser_mode": chaser_mode, "com_chaser_S": com_c, "m_chaser": m_c}
    elif chaser_mode == "b601":
        if q_c is None:
            raise ValueError("b601 chaser mode requires q_c")
        m_c, cg_S, I_S, p_E_S = b601_chaser_stack(np.asarray(q_c, float))
        chaser = {"m": m_c, "I": R_IS @ I_S @ R_IS.T,
                  "r": r_g_I + R_IS @ (cg_S - p_E_S),
                  "v": -candidate.approach_velocity * a_I, "w": np.zeros(3)}
        meta = {"chaser_mode": chaser_mode, "com_chaser_S": cg_S, "m_chaser": m_c,
                "p_E_S": p_E_S}
    else:
        raise ValueError(f"unknown chaser mode {chaser_mode}")
    meta.update({"r_g_I": r_g_I, "a_I": a_I, "R_IS": R_IS})
    return [chaser, target], meta


def capture_adapter(candidate, prop, placement, chaser_mode="b601", q_c=None):
    """Run the validated rigidization solver on the general scenario.
    rigid_6dof -> rigidize (6-DOF plastic lock), point_3dof ->
    rigidize_point_contact (ideal ball joint, force impulse only)."""
    t0 = time.time()
    bodies, meta = general_capture_scenario(candidate, prop, placement,
                                            chaser_mode, q_c)
    r_g_I = meta["r_g_I"]
    res6 = rigidize(bodies)                       # combined-CoM bookkeeping;
    H_c = res6["I_comb"] @ res6["w_plus"]         # |H_com| == momentum to remove
    if candidate.capture_mode == "rigid_6dof":
        assert res6["validity"]["momentum_ok"], res6["validity"]
        J_t, L_g = junction_couple(res6, bodies, 1, r_g_I)
        out = {
            "post_rate_dps": float(np.rad2deg(np.linalg.norm(res6["w_plus"]))),
            "w_plus_rps": [float(v) for v in res6["w_plus"]],
            "J_t_Ns": [float(v) for v in J_t],
            "L_grasp_Nms": [float(v) for v in L_g],
            "dv_chaser": np.asarray(res6["impulses"][0]["dv"], float),
            "dw_chaser": np.asarray(res6["impulses"][0]["dw"], float),
            "dT_J": float(res6["dT"]),
        }
    else:                                          # point_3dof
        resp = rigidize_point_contact(bodies, r_g_I)
        w_t_post = np.asarray(bodies[1]["w"], float) + resp["impulses"][1]["dw"]
        out = {
            # post rate of the TARGET body (rotations stay free at a point joint)
            "post_rate_dps": float(np.rad2deg(np.linalg.norm(w_t_post))),
            "w_plus_rps": [float(v) for v in w_t_post],
            "J_t_Ns": [float(v) for v in (-resp["J"])],   # impulse ON target
            "L_grasp_Nms": [0.0, 0.0, 0.0],               # no couple transmitted
            "dv_chaser": np.asarray(resp["impulses"][0]["dv"], float),
            "dw_chaser": np.asarray(resp["impulses"][0]["dw"], float),
            "dT_J": float(resp["dT"]),
        }
    out.update({
        "H_c_Nms": [float(v) for v in H_c],
        "H_c_norm_Nms": float(np.linalg.norm(H_c)),
        "bodies": bodies, "meta": meta,
        "provenance": provenance(
            "30_simulation/common/capture_impulse.py",
            {"J_t": "N*s", "L_grasp": "N*m*s", "H_c": "N*m*s",
             "post_rate": "deg/s", "dT": "J"}, t0),
    })
    return out


# ---------------- base reaction (sim_05 FreeFloatingB601) ----------------

def approach_trajectory(q0, q_c, duration_s=8.0):
    """Joint-space min-jerk q0 -> q_c over [0, duration]. Returns (q_fun, qd_fun)."""
    q0 = np.asarray(q0, float)
    dq = np.asarray(q_c, float) - q0

    def q_fun(t):
        return q0 + min_jerk(t, duration_s, dq)[0]

    def qd_fun(t):
        return min_jerk(t, duration_s, dq)[1]
    return q_fun, qd_fun


def base_reaction_adapter(q0, q_c, duration_s=8.0, n_out=800):
    """Free-floating base response to the approach trajectory (zero momentum).
    Returns peak attitude deviation [deg], peak base rate [deg/s], |H_bm qdot|
    history, and the raw trajectory dict (used by anchoring test t3)."""
    t0 = time.time()
    if n_out < 800:
        n_out = 800
    dyn = get_dyn()
    q_fun, qd_fun = approach_trajectory(q0, q_c, duration_s)
    traj = dyn.integrate_trajectory(q_fun, qd_fun, duration_s, n_out=n_out)
    rate_hist_dps = np.rad2deg(np.linalg.norm(traj["Vb"][:, 3:], axis=1))
    hbm_hist = np.linalg.norm(traj["hbm_qdot"], axis=1)
    return {
        "peak_attitude_deg": float(np.max(traj["dev_angle_deg"])),
        "peak_base_rate_dps": float(np.max(rate_hist_dps)),
        "hbm_qdot_norm_hist": [float(v) for v in hbm_hist],
        "traj": traj, "q_fun": q_fun, "qd_fun": qd_fun, "dyn": dyn,
        "provenance": provenance(
            "30_simulation/sim_05_free_floating_arm/dynamics.py",
            {"attitude": "deg", "base_rate": "deg/s", "hbm_qdot": "N*m*s"}, t0),
    }


# ---------------- flexible (sim_07 ANCF, one-way base-jump model) ----------------

def flexible_adapter(dv, dw, R_IS, com_chaser_S, t_end_s=15.0, n_eval=1500,
                     rtol=1e-6, ei_case="nominal"):
    """ANCF panel response to the chaser base velocity jump (dv, dw) from the
    capture solver -- same excitation projection, beam build (nominal f1,
    Rayleigh zeta=0.01) and integrator (Radau rtol 1e-6, constant tangent
    Jacobian) as the validated sim_07a scan. Generalized only in the frame
    bookkeeping: the legacy R_FLIP/chaser CoM become (R_IS, com_chaser_S); for
    the nominal +X candidate the numbers reduce bit-exactly to sim_07a's.

    E_flex = max over time of (strain + kinetic) energy of the +Y_S panel."""
    t0 = time.time()
    import sim_07a_task_response as s07     # heavy import (matplotlib) -- lazy

    r_rel_I = R_IS @ (s07.R_F_S - np.asarray(com_chaser_S, float))
    yF_I = R_IS @ s07.Y_F_S
    zS_I = R_IS @ np.array([0.0, 0.0, 1.0])
    xS_I = R_IS @ s07.X_S
    dv_F = np.asarray(dv, float) + np.cross(np.asarray(dw, float), r_rel_I)
    wxy = np.cross(np.asarray(dw, float), yF_I)
    a_tr = -float(dv_F @ zS_I)               # transverse (panel normal) field
    b_tr = -float(wxy @ zS_I)
    dropped = {"axial_mm_s": -float(dv_F @ yF_I) * 1e3,          # audit trail
               "inplane_root_mm_s": -float(dv_F @ xS_I) * 1e3}

    beam, info = s07.build_beam(ei_case)
    ed0 = beam.initial_velocity_field(lambda y: a_tr + b_tr * y, None)
    r = s07.simulate(beam, ed0, t_end_s, n_eval, rtol, damped=True, method="Radau")
    E = r["U"] + r["T"]
    return {
        "E_flex_J": float(np.max(E)),
        "U_max_J": float(np.max(r["U"])),
        "tip_peak_mm": float(np.max(np.abs(r["tip"])) * 1e3),
        "Mroot_peak_mNm": float(np.max(np.abs(r["Mroot"])) * 1e3),
        "f1_hz": float(info["f1"]),
        "v0_root_mm_s": a_tr * 1e3, "v0_tip_mm_s": (a_tr + b_tr * s07.L_TOT) * 1e3,
        "dropped_components": dropped,
        "provenance": provenance(
            "30_simulation/sim_07_ancf_flexible/{ancf_beam,sim_07a_task_response}.py",
            {"E_flex": "J", "tip": "mm", "Mroot": "mN*m"}, t0),
    }


# ---------------- actuator (sim_08 algebra) ----------------

def actuator_adapter(H_norm_Nms, t_detumble_s=900.0, lever_m=0.17,
                     isp_class="cold_gas_60s"):
    """sim_08 two-thruster couple detumble budget (algebraic, cross-checked
    against results/actuator_budget_sweep.csv in test t6):
        tau = |H_c| / t_d,  F = tau / (2 l),  J = |H_c| / l,
        m_p = J / (Isp g0)   [grams]"""
    t0 = time.time()
    H = float(H_norm_Nms)
    tau = H / float(t_detumble_s)
    F = tau / (2.0 * float(lever_m))
    J = H / float(lever_m)
    prop_g = {name: J / (isp * G0) * 1000.0 for name, isp in ISP_S.items()}
    return {
        "H_Nms": H, "torque_Nm": tau, "thruster_force_N": F,
        "total_impulse_Ns": J, "propellant_g": prop_g,
        "propellant_selected_g": prop_g[isp_class], "isp_class": isp_class,
        "t_detumble_s": float(t_detumble_s), "lever_m": float(lever_m),
        "provenance": provenance(
            "30_simulation/sim_08_detumble_actuator_budget/actuator_budget.py (formulas)",
            {"torque": "N*m", "force": "N", "impulse": "N*s", "propellant": "g"}, t0),
    }
