"""Deterministic rigid-body kernel for the P0-C synchronized-capture slice.

The module is deliberately contained by ``e16_sync_capture``.  It imports the
already verified sim05 free-floating dynamics and sim06 N-body rigidization
solver read-only, then reproduces the accepted E1.5 two-stage capture model:

1. an articulated 6-D Delassus impulse closes the contact twist;
2. all manipulator joints lock plastically through the verified N-body solver.

No ANCF solve is imported or run.  New synchronized terminal states therefore
carry ``flex_status=UNKNOWN`` and can never authorize a SAFE claim.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np
import yaml


E16_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = E16_ROOT.parents[1]
for _p in (
    REPO_ROOT / "30_simulation" / "common",
    REPO_ROOT / "30_simulation" / "sim_05_free_floating_arm",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from capture_impulse import junction_couple, rigidize  # noqa: E402
from dynamics import FreeFloatingB601, min_jerk  # noqa: E402
from rigid_body import load_object  # noqa: E402


CONFIG_PATH = E16_ROOT / "20_engineering" / "config" / "experiment_v1.yaml"
N_A = "N/A"
CONTACT_TOL = 1.0e-9


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def verify_protected_sources(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    expected = dict(cfg["protected_sources"])
    line = cfg["line_A_geometry_source"]
    expected[line["path"]] = line["sha256"]
    for rel, wanted in expected.items():
        path = REPO_ROOT / rel
        actual = _sha256(path) if path.is_file() else "MISSING"
        records.append({
            "path": rel,
            "expected_sha256": str(wanted),
            "actual_sha256": actual,
            "matched": actual == str(wanted),
        })
    if not all(r["matched"] for r in records):
        bad = [r for r in records if not r["matched"]]
        raise RuntimeError(f"protected-source hash mismatch: {bad}")
    return records


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def load_line_a_selected(cfg: dict[str, Any]) -> dict[tuple[str, float, str], dict[str, Any]]:
    source = REPO_ROOT / cfg["line_A_geometry_source"]["path"]
    with source.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != int(cfg["line_A_geometry_source"]["expected_rows"]):
        raise RuntimeError(f"Line A detail cardinality {len(rows)} != 96")
    selected = [r for r in rows if _as_bool(r["selected_for_group"])]
    groups: dict[tuple[str, float, str], dict[str, Any]] = {}
    for row in selected:
        key = (row["grasp_point_id"], float(row["t_c_s"]), row["task_constraint_mode"])
        if key in groups:
            raise RuntimeError(f"duplicate Line A selected row: {key}")
        groups[key] = row
    expected = int(cfg["line_A_geometry_source"]["expected_groups"])
    if len(groups) != expected:
        raise RuntimeError(f"Line A selected groups {len(groups)} != {expected}")
    return groups


def skew(a: np.ndarray) -> np.ndarray:
    x, y, z = np.asarray(a, float).reshape(3)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def rodrigues(omega_I: np.ndarray, t_s: float) -> np.ndarray:
    omega = np.asarray(omega_I, float).reshape(3)
    mag = float(np.linalg.norm(omega))
    if mag == 0.0:
        return np.eye(3)
    axis = omega / mag
    K = skew(axis)
    theta = mag * float(t_s)
    return np.eye(3) + math.sin(theta) * K + (1.0 - math.cos(theta)) * (K @ K)


def _system_invariants(bodies: list[dict[str, Any]]) -> dict[str, Any]:
    P = np.zeros(3)
    H = np.zeros(3)
    kinetic = 0.0
    for body in bodies:
        m = float(body["m"])
        I = np.asarray(body["I"], float)
        r = np.asarray(body["r"], float)
        v = np.asarray(body["v"], float)
        w = np.asarray(body["w"], float)
        P += m * v
        H += I @ w + m * np.cross(r, v)
        kinetic += 0.5 * m * float(v @ v) + 0.5 * float(w @ (I @ w))
    return {"P": P, "H_origin": H, "KE": float(kinetic)}


def _momentum_residual(pre: dict[str, Any], post: dict[str, Any]) -> dict[str, float]:
    dP = np.asarray(post["P"]) - np.asarray(pre["P"])
    dH = np.asarray(post["H_origin"]) - np.asarray(pre["H_origin"])
    return {
        "P_residual_inf": float(np.max(np.abs(dP))),
        "H_origin_residual_inf": float(np.max(np.abs(dH))),
    }


class SyncCaptureKernel:
    """Reusable deterministic physics context for all 216 terminal cases."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.dyn = FreeFloatingB601()
        self.target = load_object(cfg["scope"]["target_id"])
        self.R_IB = np.asarray(cfg["scene"]["common_base_R_IB"], float)
        self.R_BI = self.R_IB.T
        self.t_IB = np.asarray(cfg["scene"]["common_base_t_IB_m"], float)
        axis = np.asarray(cfg["scope"]["target_tumble_axis_I"], float)
        self.omega_I = (np.deg2rad(float(cfg["scope"]["target_tumble_rate_dps"]))
                        * axis / np.linalg.norm(axis))
        self._base_reaction_cache: dict[tuple[float, ...], dict[str, float]] = {}

    def target_state(self, point_id: str, phase_s: float) -> dict[str, np.ndarray]:
        grasp = self.cfg["grasp_geometry"][point_id]
        R_IT = rodrigues(self.omega_I, phase_s)
        r_g_I = R_IT @ np.asarray(grasp["point_T_m"], float)
        n_I = R_IT @ np.asarray(grasp["outward_normal_T"], float)
        n_I /= np.linalg.norm(n_I)
        v_g_I = np.cross(self.omega_I, r_g_I)
        return {"R_IT": R_IT, "r_g_I": r_g_I, "n_I": n_I, "v_g_I": v_g_I}

    def synchronized_twist(self, state: dict[str, np.ndarray], alpha: float,
                           closure_speed_mps: float) -> dict[str, np.ndarray]:
        xi_g_I = np.concatenate([state["v_g_I"], self.omega_I])
        xi_closure_I = np.concatenate([
            -float(closure_speed_mps) * state["n_I"], np.zeros(3)
        ])
        xi_des_I = float(alpha) * xi_g_I + xi_closure_I
        xi_des_B = np.concatenate([
            self.R_BI @ xi_des_I[:3], self.R_BI @ xi_des_I[3:]
        ])
        return {"xi_g_I": xi_g_I, "xi_closure_I": xi_closure_I,
                "xi_des_I": xi_des_I, "xi_des_B": xi_des_B}

    def terminal_tracking(self, q: np.ndarray, xi_des_B: np.ndarray) -> dict[str, Any]:
        q = np.asarray(q, float).reshape(6)
        desired = np.asarray(xi_des_B, float).reshape(6)
        Jg, parts = self.dyn.generalized_jacobian(q, return_parts=True)
        singular = np.linalg.svd(Jg, compute_uv=False)
        cond = float(singular[0] / singular[-1]) if singular[-1] > 0.0 else float("inf")
        limit = float(self.cfg["scene"]["terminal_generalized_jacobian_condition_max"])
        if not np.isfinite(cond) or cond > limit:
            raise RuntimeError(f"terminal generalized Jacobian condition {cond} > {limit}")
        qdot = np.linalg.solve(Jg, desired)
        Vb = self.dyn.base_velocity_zero_momentum(q, qdot)
        actual = parts["J_b"] @ Vb + parts["J_m"] @ qdot
        residual = actual - desired
        momentum = self.dyn.momentum_base_frame(q, Vb, qdot)
        rtol = float(self.cfg["scene"]["terminal_tracking_residual_tol"])
        mtol = float(self.cfg["scene"]["terminal_momentum_tol"])
        if (float(np.max(np.abs(residual))) > rtol
                or float(np.max(np.abs(momentum))) > mtol):
            raise RuntimeError("terminal tracking residual exceeded tolerance")
        return {
            "qdot": qdot, "Vb": Vb, "Jg": Jg,
            "condition": cond,
            "twist_residual_inf": float(np.max(np.abs(residual))),
            "momentum_residual_inf": float(np.max(np.abs(momentum))),
        }

    def materialize_chaser(self, q: np.ndarray, tracking: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        q = np.asarray(q, float).reshape(6)
        qdot = np.asarray(tracking["qdot"], float).reshape(6)
        Vb = np.asarray(tracking["Vb"], float).reshape(6)
        source = self.dyn._bodies(q)  # accepted sim05 decomposition, read-only
        bodies: list[dict[str, Any]] = []
        for index, body in enumerate(source):
            c_B = np.asarray(body["c"], float)
            v_B = (Vb[:3] + np.cross(Vb[3:], c_B)
                   + np.asarray(body["Jv"], float) @ qdot)
            w_B = Vb[3:] + np.asarray(body["Jw"], float) @ qdot
            bodies.append({
                "m": float(body["mass"]),
                "I": self.R_IB @ np.asarray(body["I"], float) @ self.R_IB.T,
                "r": self.t_IB + self.R_IB @ c_B,
                "v": self.R_IB @ v_B,
                "w": self.R_IB @ w_B,
                "source_body_index": index,
            })
        last = source[-1]
        p_E_B = self.dyn.arm.fk(q)["T_E"][:3, 3]
        c_last = np.asarray(last["c"], float)
        v_last_B = (Vb[:3] + np.cross(Vb[3:], c_last)
                    + np.asarray(last["Jv"], float) @ qdot)
        w_last_B = Vb[3:] + np.asarray(last["Jw"], float) @ qdot
        v_E_B = v_last_B + np.cross(w_last_B, p_E_B - c_last)
        twist_E_B = np.concatenate([v_E_B, w_last_B])
        invariants = _system_invariants(bodies)
        return bodies, {
            "source": source,
            "p_E_B": p_E_B,
            "p_E_I": self.t_IB + self.R_IB @ p_E_B,
            "twist_E_B": twist_E_B,
            "P_inf": float(np.max(np.abs(invariants["P"]))),
            "H_inf": float(np.max(np.abs(invariants["H_origin"]))),
        }

    def target_body(self, state: dict[str, np.ndarray]) -> dict[str, Any]:
        return {
            "m": float(self.target["mass"]),
            "I": state["R_IT"] @ np.asarray(self.target["I"], float) @ state["R_IT"].T,
            "r": np.zeros(3), "v": np.zeros(3), "w": self.omega_I.copy(),
        }

    def articulated_contact(self, q: np.ndarray, tracking: dict[str, Any],
                            chaser: list[dict[str, Any]], target: dict[str, Any],
                            r_g_I: np.ndarray) -> dict[str, Any]:
        q = np.asarray(q, float).reshape(6)
        source = self.dyn._bodies(q)
        M = np.zeros((12, 12))
        for body in source:
            c_B = np.asarray(body["c"], float)
            Av = np.hstack((np.eye(3), -skew(c_B), np.asarray(body["Jv"], float)))
            Aw = np.hstack((np.zeros((3, 3)), np.eye(3), np.asarray(body["Jw"], float)))
            M += (float(body["mass"]) * (Av.T @ Av)
                  + Aw.T @ np.asarray(body["I"], float) @ Aw)
        _, jac = self.dyn.generalized_jacobian(q, return_parts=True)
        Jc = np.hstack((np.asarray(jac["J_b"], float), np.asarray(jac["J_m"], float)))

        d_t_B = self.R_BI @ (np.asarray(r_g_I, float) - np.asarray(target["r"], float))
        I_t_B = self.R_BI @ np.asarray(target["I"], float) @ self.R_IB
        Mt = np.zeros((6, 6))
        Mt[:3, :3] = float(target["m"]) * np.eye(3)
        Mt[3:, 3:] = I_t_B
        Jt = np.eye(6)
        Jt[:3, 3:] = -skew(d_t_B)

        u0 = np.concatenate([tracking["Vb"], tracking["qdot"]])
        z0 = np.concatenate([self.R_BI @ np.asarray(target["v"], float),
                             self.R_BI @ np.asarray(target["w"], float)])
        MinvJ = np.linalg.solve(M, Jc.T)
        MtinvJ = np.linalg.solve(Mt, Jt.T)
        K = Jc @ MinvJ + Jt @ MtinvJ
        relative_pre = Jc @ u0 - Jt @ z0
        W_B = np.linalg.solve(K, relative_pre)
        u1 = u0 - MinvJ @ W_B
        z1 = z0 + MtinvJ @ W_B
        residual = Jc @ u1 - Jt @ z1

        post_chaser, _ = self._materialize_arbitrary(q, u1[:6], u1[6:])
        target_post = dict(target)
        target_post["v"] = self.R_IB @ z1[:3]
        target_post["w"] = self.R_IB @ z1[3:]
        post_bodies = post_chaser + [target_post]
        W_I = np.concatenate([self.R_IB @ W_B[:3], self.R_IB @ W_B[3:]])
        pre_inv = _system_invariants(chaser + [target])
        post_inv = _system_invariants(post_bodies)
        momentum = _momentum_residual(pre_inv, post_inv)
        dT = float(pre_inv["KE"] - post_inv["KE"])
        if (float(np.max(np.abs(residual))) > CONTACT_TOL
                or momentum["P_residual_inf"] > CONTACT_TOL
                or momentum["H_origin_residual_inf"] > CONTACT_TOL
                or dT < -CONTACT_TOL * max(pre_inv["KE"], 1.0)):
            raise RuntimeError("articulated contact conservation failure")
        return {
            "post_bodies": post_bodies,
            "W_I": W_I,
            "relative_pre_B": relative_pre,
            "twist_residual_inf": float(np.max(np.abs(residual))),
            "P_residual_inf": momentum["P_residual_inf"],
            "H_residual_inf": momentum["H_origin_residual_inf"],
            "dT_contact": dT,
            "M_condition": float(np.linalg.cond(M)),
            "K_condition": float(np.linalg.cond(K)),
        }

    def _materialize_arbitrary(self, q: np.ndarray, Vb: np.ndarray,
                               qdot: np.ndarray) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        source = self.dyn._bodies(np.asarray(q, float))
        bodies: list[dict[str, Any]] = []
        for index, body in enumerate(source):
            c_B = np.asarray(body["c"], float)
            v_B = (np.asarray(Vb[:3]) + np.cross(Vb[3:], c_B)
                   + np.asarray(body["Jv"], float) @ qdot)
            w_B = np.asarray(Vb[3:]) + np.asarray(body["Jw"], float) @ qdot
            bodies.append({
                "m": float(body["mass"]),
                "I": self.R_IB @ np.asarray(body["I"], float) @ self.R_IB.T,
                "r": self.t_IB + self.R_IB @ c_B,
                "v": self.R_IB @ v_B,
                "w": self.R_IB @ w_B,
                "source_body_index": index,
            })
        return bodies, {"invariants": _system_invariants(bodies)}

    def two_stage_capture(self, q: np.ndarray, tracking: dict[str, Any],
                          state: dict[str, np.ndarray]) -> dict[str, Any]:
        chaser, material = self.materialize_chaser(q, tracking)
        target = self.target_body(state)
        if max(material["P_inf"], material["H_inf"]) > CONTACT_TOL:
            raise RuntimeError("pre-contact chaser is not zero momentum")
        contact_position_error = float(np.linalg.norm(material["p_E_I"] - state["r_g_I"]))
        # The actual desired twist comparison is performed by the caller; the
        # contact-position error is the geometry invariant needed here.
        if contact_position_error > 1.0e-6:
            raise RuntimeError(f"EE/contact position mismatch {contact_position_error}")

        bodies = chaser + [target]
        contact = self.articulated_contact(q, tracking, chaser, target, state["r_g_I"])
        contact_bodies = contact["post_bodies"]
        target_index = len(chaser)
        base_index = 0
        final = rigidize(contact_bodies)
        J_lock, L_lock = junction_couple(final, contact_bodies, target_index, state["r_g_I"])
        W_lock = np.concatenate([np.asarray(J_lock, float), np.asarray(L_lock, float)])
        W_initial = np.asarray(contact["W_I"], float)
        W_net = W_initial + W_lock

        direct = rigidize(bodies)
        J_direct, L_direct = junction_couple(direct, bodies, target_index, state["r_g_I"])
        W_direct = np.concatenate([np.asarray(J_direct), np.asarray(L_direct)])
        wrench_closure = float(np.max(np.abs(W_net - W_direct)))
        energy_closure = float(contact["dT_contact"] + final["dT"] - direct["dT"])

        pre_inv = _system_invariants(bodies)
        final_inv = {
            "P": float(final["M"]) * np.asarray(final["v_com"]),
            "H_origin": (np.asarray(final["I_comb"]) @ np.asarray(final["w_plus"])
                         + float(final["M"]) * np.cross(np.asarray(final["r_com"]),
                                                         np.asarray(final["v_com"]))),
            "KE": float(final["KE_post"]),
        }
        two_stage_residual = _momentum_residual(pre_inv, final_inv)
        if (wrench_closure > CONTACT_TOL or abs(energy_closure) > CONTACT_TOL
                or max(two_stage_residual.values()) > CONTACT_TOL):
            raise RuntimeError("two-stage closure failure")

        base_pre = bodies[base_index]
        base_r = np.asarray(base_pre["r"], float)
        v_base_final = (np.asarray(final["v_com"])
                        + np.cross(np.asarray(final["w_plus"]),
                                   base_r - np.asarray(final["r_com"])))
        w_base_final = np.asarray(final["w_plus"])
        dv_total = v_base_final - np.asarray(base_pre["v"])
        dw_total = w_base_final - np.asarray(base_pre["w"])
        H_c = np.asarray(final["I_comb"]) @ w_base_final
        return {
            "W_initial_I": W_initial,
            "W_lock_I": W_lock,
            "W_net_I": W_net,
            "post_rate_dps": float(np.rad2deg(np.linalg.norm(w_base_final))),
            "w_plus_I": w_base_final,
            "H_c_I": H_c,
            "H_norm_Nms": float(np.linalg.norm(H_c)),
            "dv_base_total": dv_total,
            "dw_base_total": dw_total,
            "contact_relative_twist_pre_B": contact["relative_pre_B"],
            "contact_twist_residual_inf": contact["twist_residual_inf"],
            "contact_P_residual_inf": contact["P_residual_inf"],
            "contact_H_residual_inf": contact["H_residual_inf"],
            "two_stage_P_residual_inf": two_stage_residual["P_residual_inf"],
            "two_stage_H_residual_inf": two_stage_residual["H_origin_residual_inf"],
            "wrench_closure_inf": wrench_closure,
            "energy_closure_J": energy_closure,
            "dT_contact_J": contact["dT_contact"],
            "dT_lock_J": float(final["dT"]),
            "contact_position_error_m": contact_position_error,
            "M_condition": contact["M_condition"],
            "K_condition": contact["K_condition"],
        }

    def base_reaction(self, q: np.ndarray) -> dict[str, float]:
        q = np.asarray(q, float).reshape(6)
        key = tuple(np.round(q, 12))
        if key in self._base_reaction_cache:
            return dict(self._base_reaction_cache[key])
        duration = float(self.cfg["scene"]["approach_duration_s"])

        def q_fun(t: float) -> np.ndarray:
            return min_jerk(t, duration, q)[0]

        def qd_fun(t: float) -> np.ndarray:
            return min_jerk(t, duration, q)[1]

        traj = self.dyn.integrate_trajectory(q_fun, qd_fun, duration, n_out=800)
        rates = np.rad2deg(np.linalg.norm(traj["Vb"][:, 3:], axis=1))
        momentum_residual = 0.0
        for t, Vb in zip(traj["t"], traj["Vb"]):
            momentum = self.dyn.momentum_base_frame(q_fun(float(t)), Vb,
                                                    qd_fun(float(t)))
            momentum_residual = max(momentum_residual,
                                    float(np.max(np.abs(momentum))))
        result = {
            "base_attitude_change_deg": float(np.max(traj["dev_angle_deg"])),
            "base_rate_peak_approach_dps": float(np.max(rates)),
            "base_momentum_residual_inf": momentum_residual,
        }
        self._base_reaction_cache[key] = result
        return dict(result)


def _json(value: Any) -> str:
    if isinstance(value, np.ndarray):
        value = value.tolist()
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _case_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("ascii")).hexdigest()[:16]


DOWNSTREAM_FIELDS = (
    "xi_G_I_json", "xi_closure_I_json", "xi_EE_des_I_json",
    "terminal_qdot_json", "terminal_base_velocity_B_json",
    "terminal_joint_speed_max_radps", "terminal_base_rate_dps",
    "joint_velocity_limit_radps", "joint_velocity_limit_status",
    "joint_torque_limit_status",
    "terminal_generalized_condition", "terminal_twist_residual_inf",
    "terminal_momentum_residual_inf", "base_attitude_change_deg",
    "base_rate_peak_approach_dps", "base_momentum_residual_inf",
    "capture_impulse_linear_I_json", "capture_impulse_angular_I_json",
    "capture_impulse_linear_norm_Ns", "capture_impulse_angular_norm_Nms",
    "capture_impulse_6d_norm", "lock_impulse_linear_norm_Ns",
    "lock_impulse_angular_norm_Nms", "net_target_wrench_6d_norm",
    "relative_twist_pre_norm", "post_capture_omega_I_json",
    "post_capture_omega_dps", "wheel_momentum_required_Nms",
    "thruster_impulse_required_Ns", "propellant_required_g",
    "base_capture_dv_norm_mps", "base_capture_dw_norm_radps",
    "contact_position_error_m", "contact_twist_residual_inf",
    "contact_P_residual_inf", "contact_H_residual_inf",
    "two_stage_P_residual_inf", "two_stage_H_residual_inf",
    "wrench_closure_inf", "energy_closure_J", "dT_contact_J",
    "dT_lock_J", "contact_delassus_condition",
    "post_capture_rate_margin", "wheel_momentum_margin",
    "thruster_impulse_margin", "core_margin",
)


def _upstream_rejected_row(base: dict[str, Any], reason: str) -> dict[str, Any]:
    row = dict(base)
    row.update({name: N_A for name in DOWNSTREAM_FIELDS})
    row.update({
        "case_terminal_status": "COMPLETE_UPSTREAM_REJECTED",
        "dynamics_status": "NOT_RUN_DUE_TO_UPSTREAM",
        "flex_status": "UNKNOWN_NOT_RUN",
        "flex_value": "UNKNOWN",
        "evidence_status": "COMPLETE_FOR_APPLICABLE_STAGES",
        "classification": "GEOMETRY_INVALID",
        "binding_constraint": reason,
        "safe_claim_permitted": False,
        "post_capture_rate_pass": N_A,
        "wheel_momentum_pass": N_A,
        "thruster_impulse_pass": N_A,
        "actuator_limit_status": "NOT_RUN_DUE_TO_UPSTREAM",
    })
    return row


def evaluate_case(kernel: SyncCaptureKernel, cfg: dict[str, Any],
                  line_row: dict[str, Any], point_id: str, phase_s: float,
                  speed_mps: float, task_mode: str, alpha: float) -> dict[str, Any]:
    key_payload = {
        "schema": cfg["schema_version"], "point": point_id,
        "phase_s": float(phase_s), "closure_speed_mps": float(speed_mps),
        "task_mode": task_mode, "alpha": float(alpha),
        "capture_mode": cfg["scope"]["capture_mode"],
        "line_A_group": line_row["geometry_group_key"],
    }
    case_hash = _case_hash(key_payload)
    case_id = (f"{point_id}_tc{int(phase_s):02d}_v{int(round(speed_mps*1000)):02d}mm_"
               f"{task_mode}_a{str(alpha).replace('.', 'p')}")
    geometry_flags = {
        name: _as_bool(line_row[name]) for name in (
            "ik_feasible", "collision_feasible", "condition_feasible",
            "joint_limit_feasible", "terminal_tracking_feasible")
    }
    base = {
        "case_id": case_id, "scenario_hash": case_hash,
        "grasp_point_id": point_id, "capture_phase_s": float(phase_s),
        "closure_speed_mps": float(speed_mps), "task_mode": task_mode,
        "alpha": float(alpha), "capture_mode": cfg["scope"]["capture_mode"],
        "line_A_geometry_group_key": line_row["geometry_group_key"],
        "line_A_roll_angle_deg": float(line_row["roll_angle_deg"]),
        "line_A_realized_roll_angle_deg": (float(line_row["realized_roll_angle_deg"])
                                             if line_row["realized_roll_angle_deg"] else N_A),
        "geometry_status": "FEASIBLE" if all(geometry_flags.values()) else "UNREACHABLE",
        **geometry_flags,
        "manipulability": (float(line_row["manipulability"])
                            if line_row["manipulability"] not in {"", "-inf"} else N_A),
        "condition_number": (float(line_row["condition_number"])
                             if line_row["condition_number"] else N_A),
        "joint_limit_margin_rad": (float(line_row["joint_limit_margin_rad"])
                                    if line_row["joint_limit_margin_rad"] else N_A),
        "collision_margin_m": (float(line_row["collision_margin_m"])
                               if line_row["collision_margin_m"] else N_A),
        "geometry_source_hash": line_row["full_scenario_hash"],
    }
    if not all(geometry_flags.values()) or not line_row["selected_q_json"]:
        reason = next((name.upper() for name, ok in geometry_flags.items() if not ok),
                      "LINE_A_UNREACHABLE")
        reason = "IK_FAIL" if reason == "IK_FEASIBLE" else reason
        return _upstream_rejected_row(base, reason)

    q = np.asarray(json.loads(line_row["selected_q_json"]), float)
    state = kernel.target_state(point_id, phase_s)
    sync = kernel.synchronized_twist(state, alpha, speed_mps)
    tracking = kernel.terminal_tracking(q, sync["xi_des_B"])
    material, material_meta = kernel.materialize_chaser(q, tracking)
    material_twist_error = float(np.max(np.abs(
        material_meta["twist_E_B"] - sync["xi_des_B"])))
    if material_twist_error > CONTACT_TOL:
        raise RuntimeError(f"material EE twist mismatch {material_twist_error}")
    capture = kernel.two_stage_capture(q, tracking, state)
    reaction = kernel.base_reaction(q)

    W0 = capture["W_initial_I"]
    Wlock = capture["W_lock_I"]
    Wnet = capture["W_net_I"]
    Jlin = float(np.linalg.norm(W0[:3]))
    Jang = float(np.linalg.norm(W0[3:]))
    H = float(capture["H_norm_Nms"])
    hc = cfg["hard_constraints_frozen"]
    thruster = H / float(hc["thruster_lever_m"])
    prop_g = thruster / (float(hc["cold_gas_isp_s"]) * float(hc["g0_mps2"])) * 1000.0
    post = float(capture["post_rate_dps"])
    post_margin = 1.0 - post / float(hc["post_capture_rate_max_dps"])
    wheel_margin = 1.0 - H / float(hc["wheel_momentum_max_Nms"])
    thruster_margin = 1.0 - thruster / float(hc["thruster_total_impulse_max_Ns"])
    core_margin = min(post_margin, wheel_margin, thruster_margin)
    post_pass = post <= float(hc["post_capture_rate_max_dps"])
    wheel_pass = H <= float(hc["wheel_momentum_max_Nms"])
    thruster_pass = thruster <= float(hc["thruster_total_impulse_max_Ns"])

    failures: list[tuple[str, float]] = []
    if not post_pass:
        failures.append(("POST_CAPTURE_RATE_EXCEED", post_margin))
    if not wheel_pass:
        failures.append(("WHEEL_MOMENTUM_EXCEED", wheel_margin))
    if not thruster_pass:
        failures.append(("THRUSTER_IMPULSE_EXCEED", thruster_margin))
    if failures:
        binding = min(failures, key=lambda item: (item[1], item[0]))[0]
        classification = "CORE_UNSAFE"
    else:
        binding = "FLEX_UNKNOWN"
        classification = "CORE_SAFE_FLEX_UNKNOWN"

    row = dict(base)
    row.update({
        "case_terminal_status": "COMPLETE_DYNAMIC_EVALUATED",
        "dynamics_status": "EVALUATED",
        "xi_G_I_json": _json(sync["xi_g_I"]),
        "xi_closure_I_json": _json(sync["xi_closure_I"]),
        "xi_EE_des_I_json": _json(sync["xi_des_I"]),
        "terminal_qdot_json": _json(tracking["qdot"]),
        "terminal_base_velocity_B_json": _json(tracking["Vb"]),
        "terminal_joint_speed_max_radps": float(np.max(np.abs(tracking["qdot"]))),
        "terminal_base_rate_dps": float(np.rad2deg(np.linalg.norm(tracking["Vb"][3:]))),
        "joint_velocity_limit_radps": "UNKNOWN_NOT_FROZEN",
        "joint_velocity_limit_status": "UNKNOWN_NO_FROZEN_LIMIT",
        "joint_torque_limit_status": "UNKNOWN_NOT_MODELED_IN_TERMINAL_KINEMATICS",
        "terminal_generalized_condition": tracking["condition"],
        "terminal_twist_residual_inf": tracking["twist_residual_inf"],
        "terminal_momentum_residual_inf": tracking["momentum_residual_inf"],
        **reaction,
        "capture_impulse_linear_I_json": _json(W0[:3]),
        "capture_impulse_angular_I_json": _json(W0[3:]),
        "capture_impulse_linear_norm_Ns": Jlin,
        "capture_impulse_angular_norm_Nms": Jang,
        "capture_impulse_6d_norm": float(np.linalg.norm(W0)),
        "lock_impulse_linear_norm_Ns": float(np.linalg.norm(Wlock[:3])),
        "lock_impulse_angular_norm_Nms": float(np.linalg.norm(Wlock[3:])),
        "net_target_wrench_6d_norm": float(np.linalg.norm(Wnet)),
        "relative_twist_pre_norm": float(np.linalg.norm(capture["contact_relative_twist_pre_B"])),
        "post_capture_omega_I_json": _json(capture["w_plus_I"]),
        "post_capture_omega_dps": post,
        "wheel_momentum_required_Nms": H,
        "thruster_impulse_required_Ns": thruster,
        "propellant_required_g": prop_g,
        "base_capture_dv_norm_mps": float(np.linalg.norm(capture["dv_base_total"])),
        "base_capture_dw_norm_radps": float(np.linalg.norm(capture["dw_base_total"])),
        "contact_position_error_m": capture["contact_position_error_m"],
        "contact_twist_residual_inf": capture["contact_twist_residual_inf"],
        "contact_P_residual_inf": capture["contact_P_residual_inf"],
        "contact_H_residual_inf": capture["contact_H_residual_inf"],
        "two_stage_P_residual_inf": capture["two_stage_P_residual_inf"],
        "two_stage_H_residual_inf": capture["two_stage_H_residual_inf"],
        "wrench_closure_inf": capture["wrench_closure_inf"],
        "energy_closure_J": capture["energy_closure_J"],
        "dT_contact_J": capture["dT_contact_J"],
        "dT_lock_J": capture["dT_lock_J"],
        "contact_delassus_condition": capture["K_condition"],
        "post_capture_rate_margin": post_margin,
        "wheel_momentum_margin": wheel_margin,
        "thruster_impulse_margin": thruster_margin,
        "core_margin": core_margin,
        "post_capture_rate_pass": post_pass,
        "wheel_momentum_pass": wheel_pass,
        "thruster_impulse_pass": thruster_pass,
        "actuator_limit_status": ("PARTIAL_PASS_WHEEL_THRUSTER_JOINT_LIMITS_UNKNOWN"
                                  if wheel_pass and thruster_pass else
                                  "FAIL_WHEEL_OR_THRUSTER"),
        "flex_status": "UNKNOWN_NOT_RUN",
        "flex_value": "UNKNOWN",
        "evidence_status": "COMPLETE_RIGID_FLEX_UNKNOWN",
        "classification": classification,
        "binding_constraint": binding,
        "safe_claim_permitted": False,
    })
    return row


def run_campaign(cfg: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = load_config() if cfg is None else cfg
    source_records = verify_protected_sources(cfg)
    groups = load_line_a_selected(cfg)
    kernel = SyncCaptureKernel(cfg)
    rows: list[dict[str, Any]] = []
    scope = cfg["scope"]
    for point in scope["grasp_points"]:
        for phase in scope["capture_phases_s"]:
            for speed in scope["closure_speeds_mps"]:
                for mode in scope["task_modes"]:
                    line = groups[(point, float(phase), mode)]
                    for alpha in scope["alpha_values"]:
                        rows.append(evaluate_case(kernel, cfg, line, point, float(phase),
                                                  float(speed), mode, float(alpha)))
    expected = int(scope["expected_cases"])
    if len(rows) != expected or len({r["scenario_hash"] for r in rows}) != expected:
        raise RuntimeError("campaign cardinality/hash uniqueness failure")
    terminal = sum(str(r["case_terminal_status"]).startswith("COMPLETE") for r in rows)
    dynamics = sum(r["dynamics_status"] == "EVALUATED" for r in rows)
    upstream = sum(r["dynamics_status"] == "NOT_RUN_DUE_TO_UPSTREAM" for r in rows)
    summary = {
        "expected_cases": expected,
        "terminal_cases": terminal,
        "dynamic_evaluated_cases": dynamics,
        "upstream_rejected_cases": upstream,
        "source_hashes": source_records,
        "all_terminal": terminal == expected,
        "all_dynamics_accounted": dynamics + upstream == expected,
    }
    return rows, summary


def canonical_rows_digest(rows: list[dict[str, Any]]) -> str:
    blob = json.dumps(rows, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()
