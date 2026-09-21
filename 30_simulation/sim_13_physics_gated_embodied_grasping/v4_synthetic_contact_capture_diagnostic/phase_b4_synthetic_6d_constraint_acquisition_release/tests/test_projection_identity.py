from __future__ import annotations

import numpy as np


def _fixture() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows = np.arange(6, dtype=float)[:, None]
    cols = np.arange(14, dtype=float)[None, :]
    a = 0.02 * np.sin(0.31 * (rows + 1.0) * (cols + 1.0))
    a[:, :6] += np.array(
        [
            [1.0, 0.0, 0.0, 0.0, 0.12, -0.08],
            [0.0, 1.0, 0.0, -0.12, 0.0, 0.09],
            [0.0, 0.0, 1.0, 0.08, -0.09, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ]
    )
    l_map = np.vstack((np.eye(14), a))
    j_c = np.hstack((-a, np.eye(6)))
    seed = np.arange(400, dtype=float).reshape(20, 20)
    b = np.sin(0.017 * (seed + 1.0))
    mass = b.T @ b + np.diag(np.linspace(1.0, 3.0, 20))
    z_minus = 0.01 * np.cos(np.arange(20, dtype=float) + 0.2)
    d = np.diag([1.0, 1.0, 1.0, 0.17, 0.17, 0.17])
    return mass, l_map, j_c, z_minus, d


def test_embedding_and_constraint_are_full_rank_and_exact_nullspaces() -> None:
    _, l_map, j_c, _, d = _fixture()
    reference_length = float(d[3, 3])
    s_eta_diag = np.array([1.0] * 3 + [reference_length] * 3 + [reference_length] * 6 + [1.0] * 2)
    s_z_diag = np.concatenate((s_eta_diag, np.ones(3), np.full(3, reference_length)))
    l_hat = np.diag(s_z_diag) @ l_map @ np.diag(1.0 / s_eta_diag)
    j_hat = d @ j_c @ np.diag(1.0 / s_z_diag)
    assert np.linalg.matrix_rank(l_hat) == 14
    assert np.linalg.matrix_rank(j_hat) == 6
    assert np.linalg.norm(j_hat @ l_hat, ord=np.inf) < 1e-14


def test_reduced_and_scaled_kkt_projection_are_equivalent() -> None:
    mass, l_map, j_c, z_minus, d = _fixture()
    eta_plus = np.linalg.solve(l_map.T @ mass @ l_map, l_map.T @ mass @ z_minus)
    z_reduced = l_map @ eta_plus
    j_bar = d @ j_c
    w_bar = j_bar @ np.linalg.solve(mass, j_bar.T)
    block = np.block([[mass, -j_bar.T], [j_bar, np.zeros((6, 6))]])
    solution = np.linalg.solve(block, np.concatenate((mass @ z_minus, np.zeros(6))))
    z_kkt = solution[:20]
    assert np.linalg.norm(z_reduced - z_kkt, ord=np.inf) < 1e-12
    assert np.linalg.norm(j_bar @ z_kkt, ord=np.inf) < 1e-12


def test_scaled_effective_mass_is_spd_and_projection_dissipates() -> None:
    mass, _, j_c, z_minus, d = _fixture()
    j_bar = d @ j_c
    w_bar = j_bar @ np.linalg.solve(mass, j_bar.T)
    assert np.min(np.linalg.eigvalsh(0.5 * (w_bar + w_bar.T))) > 0.0
    gamma = j_bar @ z_minus
    loss_formula = 0.5 * gamma @ np.linalg.solve(w_bar, gamma)
    block = np.block([[mass, -j_bar.T], [j_bar, np.zeros((6, 6))]])
    solution = np.linalg.solve(block, np.concatenate((mass @ z_minus, np.zeros(6))))
    z_plus = solution[:20]
    loss_direct = 0.5 * z_minus @ mass @ z_minus - 0.5 * z_plus @ mass @ z_plus
    assert loss_formula >= 0.0
    assert abs(loss_direct - loss_formula) < 1e-13


def test_deleting_axial_row_is_detected_as_rank_loss() -> None:
    _, _, j_c, _, _ = _fixture()
    mutated = j_c.copy()
    mutated[5] = mutated[4]
    assert np.linalg.matrix_rank(mutated) == 5
