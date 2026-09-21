"""Shared v0 rigid-body utilities: load inertia from mass_inertia_budget_v1.csv,
torque-free attitude propagation (Euler's equations + quaternion kinematics),
and angular-momentum / kinetic-energy diagnostics. Pure numpy/scipy — no external
astrodynamics framework. Quaternion convention: scalar-first [w,x,y,z]."""
import os, csv
import numpy as np
from scipy.integrate import solve_ivp
from scipy.spatial.transform import Rotation

CSV_V1 = os.path.join(os.path.dirname(__file__), "..", "..", "docs",
                      "stage1_spacecraft_layout", "04_mass_inertia_budget", "mass_inertia_budget_v1.csv")

def load_object(object_id, csv_path=CSV_V1):
    with open(os.path.abspath(csv_path), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["object_id"] == object_id:
                m = float(r["mass_kg"])
                cg = np.array([float(r["cg_x_m"]), float(r["cg_y_m"]), float(r["cg_z_m"])])
                Ixx, Iyy, Izz = float(r["Ixx_kgm2"]), float(r["Iyy_kgm2"]), float(r["Izz_kgm2"])
                Ixy, Ixz, Iyz = float(r["Ixy_kgm2"]), float(r["Ixz_kgm2"]), float(r["Iyz_kgm2"])
                I = np.array([[Ixx, Ixy, Ixz], [Ixy, Iyy, Iyz], [Ixz, Iyz, Izz]])
                return {"id": object_id, "mass": m, "cg": cg, "I": I, "frame": r["frame"]}
    raise KeyError(object_id)

def qmult(a, b):
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2])

def q_to_R(q):  # [w,x,y,z] -> Rotation (body->inertial)
    w, x, y, z = q
    return Rotation.from_quat([x, y, z, w])

def q_to_euler_deg(q):
    return q_to_R(q).as_euler("xyz", degrees=True)

def propagate_torque_free(I, w0, t_end, n=1500, q0=(1.0, 0, 0, 0)):
    """Integrate torque-free rigid body. Returns dict of time histories."""
    Iinv = np.linalg.inv(I)
    def deriv(t, s):
        q = s[:4]; w = s[4:]
        qdot = 0.5 * qmult(q, np.array([0.0, w[0], w[1], w[2]]))
        wdot = Iinv @ (-np.cross(w, I @ w))
        return np.concatenate([qdot, wdot])
    s0 = np.concatenate([np.array(q0, float), np.array(w0, float)])
    ts = np.linspace(0, t_end, n)
    sol = solve_ivp(deriv, (0, t_end), s0, t_eval=ts, rtol=1e-10, atol=1e-12, method="DOP853")
    Q = sol.y[:4].T; Q = Q / np.linalg.norm(Q, axis=1, keepdims=True)
    W = sol.y[4:].T
    eul = np.array([q_to_euler_deg(q) for q in Q])
    Hmag = np.array([np.linalg.norm(q_to_R(q).apply(I @ w)) for q, w in zip(Q, W)])  # |H| inertial (conserved)
    E = np.array([0.5 * w @ (I @ w) for w in W])                                     # rotational KE (conserved)
    return {"t": sol.t, "Q": Q, "W": W, "euler": eul, "Hmag": Hmag, "E": E}

def conservation_report(res):
    H0, E0 = res["Hmag"][0], res["E"][0]
    dH = np.max(np.abs(res["Hmag"] - H0)) / (H0 if H0 else 1)
    dE = np.max(np.abs(res["E"] - E0)) / (E0 if E0 else 1)
    return {"H0": H0, "E0": E0, "max_rel_dH": dH, "max_rel_dE": dE}
