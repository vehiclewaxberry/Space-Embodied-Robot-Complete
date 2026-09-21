import numpy as np

from controller import ResolvedRateController
from contracts import load_config
from repo_imports import CoupledModel
from trajectories import ReferenceTrajectory, build_t2_reference
from simulator import run_closed_loop


def test_controller_method_differences_are_only_contract_terms():
    cfg = load_config()
    model = CoupledModel()
    q = np.asarray(cfg["trajectories"]["T2"]["q_initial_rad"], float)
    eta = np.zeros(2 * model.n_modes)
    reference = build_t2_reference(model, cfg)
    sample = reference.sample(0)
    p = sample["position_I"]
    R = sample["rotation_IE"]
    Rb = np.eye(3)
    c0 = ResolvedRateController(model, cfg, "C0", "pose_6d").command(
        q, eta, eta, Rb, p, R, sample
    )
    c1 = ResolvedRateController(model, cfg, "C1", "pose_6d").command(
        q, eta, eta, Rb, p, R, sample
    )
    c2 = ResolvedRateController(model, cfg, "C2", "pose_6d").command(
        q, eta, eta, Rb, p, R, sample
    )
    assert np.linalg.norm(c0.theta_dot_command) < 1e-12
    assert np.linalg.norm(c1.theta_dot_command) < 1e-12
    assert np.linalg.norm(c2.theta_dot_command) > 1e-3
    assert c0.feedforward_norm == 0.0
    assert c1.feedforward_norm == 0.0
    assert c2.feedforward_norm > 0.0
    return float(np.linalg.norm(c2.theta_dot_command))


def test_c3_rank_nullity_and_exact_projection():
    cfg = load_config()
    model = CoupledModel()
    q = np.asarray(cfg["trajectories"]["T2"]["q_initial_rad"], float)
    eta = np.zeros(2 * model.n_modes)
    reference = build_t2_reference(model, cfg)
    sample = reference.sample(0)
    output = ResolvedRateController(model, cfg, "C3", "approach_5d").command(
        q,
        eta,
        eta,
        np.eye(3),
        sample["position_I"],
        sample["rotation_IE"],
        sample,
    )
    assert output.task_rank == 5
    assert output.task_nullity == 1
    assert output.nullspace_leakage < 1e-12
    return output.nullspace_leakage


def test_c2_match5_contract_is_feedforward_without_nullspace():
    cfg = load_config()
    from contracts import method_contract

    contract = method_contract("C2", "approach_5d", cfg)
    assert contract.uses_generalized_jacobian is True
    assert contract.uses_reference_feedforward is True
    assert contract.uses_reaction_nullspace is False
    c3 = method_contract("C3", "approach_5d", cfg)
    assert c3.uses_reference_feedforward is True
    assert c3.uses_reaction_nullspace is True
    model = CoupledModel()
    reference = build_t2_reference(model, cfg)
    sample = reference.sample(0)
    q = np.asarray(cfg["trajectories"]["T2"]["q_initial_rad"], float)
    eta = np.zeros(2 * model.n_modes)
    output = ResolvedRateController(model, cfg, "C2", "approach_5d").command(
        q,
        eta,
        eta,
        np.eye(3),
        sample["position_I"],
        sample["rotation_IE"],
        sample,
    )
    assert output.task_rank == 5
    assert output.feedforward_norm > 0.0
    assert output.nullspace_active is False
    return output.feedforward_norm


def test_fixed_step_short_smoke_conserves_momentum():
    cfg = load_config()
    model = CoupledModel()
    full = build_t2_reference(model, cfg)
    n = 6
    short = ReferenceTrajectory(
        trajectory_id="T2",
        t=full.t[:n],
        position_I=full.position_I[:n],
        rotation_IE=full.rotation_IE[:n],
        twist_I=full.twist_I[:n],
        theta_initial=full.theta_initial,
        theta_nominal=None,
        open_loop=full.open_loop,
    )
    summary, _ = run_closed_loop(model, cfg, "C2", "pose_6d", short)
    assert summary["momentum_max_abs"] <= 1e-12
    assert summary["n_steps"] == n
    return summary["momentum_max_abs"]
