import numpy as np

from contracts import exact_svd_projector, load_config, reaction_map_about_base_origin
from repo_imports import CoupledModel


def _model():
    return CoupledModel()


def test_zero_momentum_independent_path():
    model = _model()
    q = np.asarray(load_config()["trajectories"]["T2"]["q_initial_rad"], float)
    eta = np.zeros(2 * model.n_modes)
    eta_dot = np.zeros_like(eta)
    qdot = np.array([0.01, -0.02, 0.015, 0.0, 0.005, -0.003])
    A = model.momentum_matrix(q, eta)
    rate = np.concatenate([qdot, eta_dot])
    Vb = -np.linalg.solve(A[:, :6], A[:, 6:] @ rate)
    h = model.momentum_inertial(
        np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0]), q, eta,
        np.concatenate([Vb, rate]),
    )
    worst = float(np.max(np.abs(h)))
    assert worst <= 1e-12
    return worst


def test_reaction_map_is_hbb_inverse_hbm_angular_rows():
    model = _model()
    q = np.asarray(load_config()["trajectories"]["T2"]["q_initial_rad"], float)
    eta = np.zeros(2 * model.n_modes)
    A = model.momentum_matrix(q, eta)
    expected = np.linalg.solve(A[:, :6], A[:, 6:12])[3:6, :]
    actual = reaction_map_about_base_origin(model, q, eta)
    worst = float(np.max(np.abs(expected - actual)))
    assert worst < 1e-14
    return worst


def test_jstar_identity_and_c0_c1_difference():
    model = _model()
    q = np.asarray(load_config()["trajectories"]["T2"]["q_initial_rad"], float)
    eta = np.zeros(2 * model.n_modes)
    qdot_m = np.linspace(-0.02, 0.02, 6 + 2 * model.n_modes)
    A = model.momentum_matrix(q, eta)
    Vb = -np.linalg.solve(A[:, :6], A[:, 6:] @ qdot_m)
    f = model.arm.fk(q)
    Jm = model.arm.jacobian(q, fk_out=f)
    rE = f["T_E"][:3, 3]
    Jb = np.eye(6)
    Jb[:3, 3:] = -np.array(
        [[0.0, -rE[2], rE[1]], [rE[2], 0.0, -rE[0]], [-rE[1], rE[0], 0.0]]
    )
    direct = Jb @ Vb + Jm @ qdot_m[:6]
    mapped = model.generalized_jacobian(q, eta) @ qdot_m
    identity_error = float(np.max(np.abs(direct - mapped)))
    delta = float(
        np.linalg.norm(model.generalized_jacobian(q, eta)[:, :6] - Jm)
    )
    assert identity_error < 1e-12
    assert delta > 1e-3
    return max(identity_error, 1.0 / delta)


def test_exact_nullspace_projector_is_not_dls_projector():
    model = _model()
    q = np.asarray(load_config()["trajectories"]["T2"]["q_initial_rad"], float)
    eta = np.zeros(2 * model.n_modes)
    J6 = model.generalized_jacobian(q, eta)[:, :6]
    J5 = J6[:5, :]
    projector, rank = exact_svd_projector(J5, 1e-8)
    leak = float(np.linalg.norm(J5 @ projector, ord=2))
    assert rank == 5
    assert leak < 1e-12
    return leak
