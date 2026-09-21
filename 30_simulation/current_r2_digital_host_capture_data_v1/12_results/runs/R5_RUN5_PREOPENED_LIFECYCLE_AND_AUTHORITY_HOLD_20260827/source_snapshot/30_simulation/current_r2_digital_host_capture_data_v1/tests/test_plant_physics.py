"""Independent physics validation of the prebind plant (not a mission gate)."""
import numpy as np
import pytest

from dh_v1.frames import make_T, quat_to_R, rpy_to_R
from dh_v1.integrators import pack_state, rk4_run, unpack_state
from dh_v1.plant import FloatingPlant, compose_models
from dh_v1.spatial import X_force


def single_body_model(mass=6.0, com=(0.02, -0.01, 0.05), I_diag=(0.10, 0.18, 0.22)):
    return {
        "robot_name": "single_body",
        "links": [
            {
                "name": "body",
                "inertial": {"mass": mass, "com": list(com), "inertia_com": np.diag(I_diag).tolist(), "inertial_origin_rpy": [0, 0, 0]},
                "has_visual": False,
                "has_collision": False,
            }
        ],
        "joints": [],
        "provenance": {},
    }


def test_single_rigid_body_matches_euler_equations():
    """Torque-free tumble of one rigid body: our floating-base RNEA/CRBA + RK4
    must reproduce scipy's high-accuracy integration of Euler's equations."""
    scipy_integrate = pytest.importorskip("scipy.integrate")
    I_diag = (0.10, 0.18, 0.22)
    m = single_body_model(com=(0.0, 0.0, 0.0), I_diag=I_diag)  # com at origin: pure Euler
    plant = FloatingPlant(m)
    assert plant.nj == 0
    w0 = np.array([0.9, -0.4, 1.3])
    x0 = pack_state(np.zeros(3), np.array([1.0, 0, 0, 0]), np.zeros(0), np.concatenate([w0, np.zeros(3)]), np.zeros(0))
    t_end, dt = 4.0, 5.0e-4
    s = rk4_run(plant, x0, t_end, dt, sample_every=200)
    I = np.diag(I_diag)

    def euler(t, w):
        return np.linalg.solve(I, -np.cross(w, I @ w))

    sol = scipy_integrate.solve_ivp(euler, (0, t_end), w0, t_eval=s["t"], rtol=1e-11, atol=1e-13)
    w_ours = np.array([unpack_state(x, 0)[3][:3] for x in s["x"]])
    assert np.max(np.abs(w_ours - sol.y.T)) < 1e-7
    # world-frame momentum and kinetic energy conserved
    h0 = s["h_O"][0]
    assert np.max(np.linalg.norm(s["h_O"] - h0, axis=1)) < 1e-10
    assert np.max(np.abs(s["E"] - s["E"][0])) < 1e-10


def test_crba_top_rows_equal_momentum(arm_plant):
    """h about base origin in base coords must equal the top 6 rows of H @ u —
    two independent code paths (CRBA vs per-body ledger)."""
    rng = np.random.default_rng(7)
    for _ in range(5):
        q = rng.uniform(-1.0, 1.0, arm_plant.nj)
        v6 = rng.uniform(-0.5, 0.5, 6)
        qd = rng.uniform(-0.5, 0.5, arm_plant.nj)
        H = arm_plant.crba(q)
        h_B_from_H = H[:6, :6] @ v6 + H[:6, 6:] @ qd
        R_WB = rpy_to_R(rng.uniform(-1, 1, 3))
        p_WB = rng.uniform(-1, 1, 3)
        h_O, _, _, _, _ = arm_plant.momentum_world(R_WB, p_WB, q, v6, qd)
        h_B_direct = np.linalg.solve(X_force(make_T(R_WB, p_WB)), h_O)
        assert np.max(np.abs(h_B_from_H - h_B_direct)) < 1e-10


def test_crba_symmetric_positive_definite(arm_plant):
    rng = np.random.default_rng(3)
    for _ in range(3):
        q = rng.uniform(-1.2, 1.2, arm_plant.nj)
        H = arm_plant.crba(q)
        assert np.max(np.abs(H - H.T)) < 1e-11
        assert np.min(np.linalg.eigvalsh(H)) > 0.0


def test_bias_zero_at_zero_velocity(arm_plant):
    C = arm_plant.bias(np.full(arm_plant.nj, 0.3), np.zeros(6), np.zeros(arm_plant.nj))
    assert np.max(np.abs(C)) < 1e-14


def test_momentum_projection_inverts_ledger(arm_plant):
    rng = np.random.default_rng(11)
    q = rng.uniform(-1.0, 1.0, arm_plant.nj)
    qd = rng.uniform(-0.4, 0.4, arm_plant.nj)
    v6 = rng.uniform(-0.3, 0.3, 6)
    R_WB = rpy_to_R([0.2, -0.5, 0.8])
    p_WB = np.array([0.4, -0.2, 1.0])
    h_O, _, _, _, _ = arm_plant.momentum_world(R_WB, p_WB, q, v6, qd)
    v6_rec = arm_plant.base_velocity_from_momentum(R_WB, p_WB, q, qd, h_O)
    assert np.max(np.abs(v6_rec - v6)) < 1e-10


def test_compose_servicer_arm_mass_and_block(arm_model, servicer_urdf_path):
    from dh_v1.urdf_extract import extract_urdf, total_mass

    sv = extract_urdf(servicer_urdf_path)
    merged = compose_models(sv, arm_model, "S_servicer_12U_v0", [0, 0, 0], [0, 0, 0], "mount_arm_base_PROVISIONAL")
    plant = FloatingPlant(merged)
    m_expected = total_mass(sv) + total_mass(arm_model)
    H = plant.crba(np.zeros(plant.nj))
    # composite linear-mass block: bottom-right 3x3 of the base block = m_total * I3
    assert np.max(np.abs(H[3:6, 3:6] - m_expected * np.eye(3))) < 1e-10
    assert plant.nj == 8


def test_energy_conservation_zero_torque(arm_plant):
    nj = arm_plant.nj
    q0 = np.zeros(nj)
    q0[1], q0[2] = -1.0, -0.8
    qd0 = 0.2 * np.ones(nj)
    x0 = pack_state(np.zeros(3), np.array([1.0, 0, 0, 0]), q0, np.array([0.02, -0.01, 0.03, 0, 0, 0]), qd0)
    s = rk4_run(arm_plant, x0, 1.0, 1.0e-3, sample_every=50)
    rel = np.max(np.abs(s["E"] - s["E"][0])) / abs(s["E"][0])
    assert rel < 1e-10
