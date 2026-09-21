"""CTRL-01-R energy-ledger regression: the audit must close to <=1e-9.

The v0 defect (rectangle-rule ledger over a first-order state map, residual
7.9e-2) must never come back. A short closed-loop slice is enough: the audit
residual of the remediated ledger saturates within tens of samples.
"""
import numpy as np

from contracts import load_config
from fast_plant import FastPlant, cross_check_against_ssot
from repo_imports import CoupledModel
from simulator import run_closed_loop
from trajectories import (
    ReferenceTrajectory,
    build_t2_reference,
    build_t3_reference,
)


def _plant_and_cfg():
    cfg = load_config()
    slow = CoupledModel(
        n_modes=int(cfg["model"]["n_modes_per_panel"]),
        stiffness_case=cfg["model"]["stiffness_case"],
    )
    return FastPlant(slow), slow, cfg


def _truncate(reference, n):
    return ReferenceTrajectory(
        trajectory_id=reference.trajectory_id,
        t=reference.t[:n],
        position_I=reference.position_I[:n],
        rotation_IE=reference.rotation_IE[:n],
        twist_I=reference.twist_I[:n],
        theta_initial=reference.theta_initial,
        theta_nominal=None,
        open_loop=reference.open_loop,
        theta_dot_initial=reference.theta_dot_initial,
        base_position_initial=reference.base_position_initial,
        base_quaternion_initial=reference.base_quaternion_initial,
        eta_initial=reference.eta_initial,
        eta_dot_initial=reference.eta_dot_initial,
        t_offset_s=reference.t_offset_s,
        freeze_time_s=None,
        trigger=reference.trigger,
    )


def test_fast_plant_matches_frozen_ssot():
    plant, slow, _ = _plant_and_cfg()
    report = cross_check_against_ssot(slow, plant, n_samples=6)
    assert report["status"] == "PASS"
    assert report["overall_worst"] <= report["tolerance"]
    return report["overall_worst"]


def test_closed_loop_ledger_closes_below_frozen_threshold():
    plant, slow, cfg = _plant_and_cfg()
    reference = _truncate(build_t2_reference(slow, cfg), 30)
    summary, _ = run_closed_loop(plant, cfg, "C2", "pose_6d", reference)
    assert summary["energy_audit_relative"] <= 1e-9
    assert summary["momentum_max_abs"] <= 1e-12
    assert summary["ledger_integrator"] == (
        "per_interval_DOP853_reduced_momentum_FOH"
    )
    return summary["energy_audit_relative"]


def test_t3_starts_from_frozen_trigger_state():
    plant, slow, cfg = _plant_and_cfg()
    m2 = 2 * plant.n_modes
    snapshot = {
        "t_abs_s": float(cfg["trajectories"]["T3"]["trigger"]["time_s"]),
        "theta": np.asarray(
            cfg["trajectories"]["T2"]["q_initial_rad"], dtype=float
        ),
        "theta_dot": np.full(6, 0.01),
        "base_position_I": np.array([0.01, -0.02, 0.005]),
        "base_quaternion_BI": np.array([0.999, 0.02, -0.01, 0.03])
        / np.linalg.norm([0.999, 0.02, -0.01, 0.03]),
        "eta": np.full(m2, 1e-5),
        "eta_dot": np.full(m2, -1e-5),
    }
    reference = build_t3_reference(plant, cfg, snapshot)
    assert np.allclose(reference.theta_initial, snapshot["theta"])
    assert np.allclose(reference.theta_dot_initial, snapshot["theta_dot"])
    assert np.allclose(
        reference.base_position_initial, snapshot["base_position_I"]
    )
    assert reference.t_offset_s == snapshot["t_abs_s"]
    assert reference.trigger["target_phase_continuation"] is True
    summary, history = run_closed_loop(
        plant, cfg, "C1", "pose_6d", _truncate(reference, 12)
    )
    # continuity: the reference starts at the actual trigger EE pose
    assert history["position_error_m"][0] <= 1e-12
    assert summary["momentum_max_abs"] <= 1e-12
    # wrong snapshot time must be refused
    bad = dict(snapshot, t_abs_s=1.0)
    try:
        build_t3_reference(plant, cfg, bad)
    except ValueError:
        return float(history["position_error_m"][0])
    raise AssertionError("wrong trigger time was not refused")
