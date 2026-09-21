"""Shared plastic-capture (instantaneous rigidization) solver + capture-scenario builder.

Physics: at the capture instant N free rigid bodies lock into one combined rigid body.
With no external impulse, linear momentum P and angular momentum H about the COMBINED CoM
are conserved; kinetic energy is not (perfectly plastic junction):

    r_com = sum(m_i r_i)/M                v_com = sum(m_i v_i)/M          (P conservation)
    H     = sum[ I_i w_i + m_i (r_i - r_com) x (v_i - v_com) ]
    I_c   = sum[ I_i + m_i ((d_i.d_i)E - d_i d_i^T) ],  d_i = r_i - r_com (parallel axis)
    w+    = I_c^-1 H                      dT = KE_pre - KE_post >= 0      (plastic)

Per-body impulses follow from the velocity jump onto the combined motion:
    v_i+ = v_com + w+ x (r_i - r_com);   J_i = m_i (v_i+ - v_i);   dL_i = I_i (w+ - w_i)
and the couple transmitted at a physical junction point p (e.g. the grasp point) is
    L_i(p) = dL_i - (p - r_i) x J_i
This (J_i, L_i(p)) pair — or equivalently (dv, dw) of the base — is the correct excitation
interface for flexible-appendage models (ANCF sim_07). The scalar dissipated energy dT is
only an UPPER BOUND / consistency check on flexible-mode energy uptake, not an input.

All quantities in one common inertial frame. Deterministic, numpy only.
Consumers: sim_06 (capture impulse study), sim_04_v2 (exact corridor), sim_07 (ANCF),
sim_08 (actuator budget). Validated by 30_simulation/sim_06_capture_impulse/tests/ (conservation,
energy, frame invariance, limiting cases, independent 6x6 spatial-inertia cross-check)."""
import os
import numpy as np

from rigid_body import load_object

# ---------------- generic solver ----------------

def steiner(m, d):
    d = np.asarray(d, float)
    return m * (np.dot(d, d) * np.eye(3) - np.outer(d, d))

def rigidize(bodies):
    """bodies: list of dicts {m, I (3x3 about own CoM, inertial axes), r, v, w}.
    Returns CaptureResult dict (combined state, per-body impulses, energy, residuals)."""
    m = np.array([b["m"] for b in bodies], float)
    r = np.array([b["r"] for b in bodies], float)
    v = np.array([b["v"] for b in bodies], float)
    w = np.array([b["w"] for b in bodies], float)
    I = [np.asarray(b["I"], float) for b in bodies]

    M = float(m.sum())
    r_com = (m[:, None] * r).sum(axis=0) / M
    v_com = (m[:, None] * v).sum(axis=0) / M
    H = np.zeros(3)
    I_comb = np.zeros((3, 3))
    for i in range(len(bodies)):
        d = r[i] - r_com
        H += I[i] @ w[i] + m[i] * np.cross(d, v[i] - v_com)
        I_comb += I[i] + steiner(m[i], d)
    w_plus = np.linalg.solve(I_comb, H)

    impulses = []
    for i in range(len(bodies)):
        v_plus = v_com + np.cross(w_plus, r[i] - r_com)
        impulses.append({"dv": v_plus - v[i], "dw": w_plus - w[i],
                         "J": m[i] * (v_plus - v[i]), "dL_com": I[i] @ (w_plus - w[i])})

    KE_pre = float(sum(0.5 * m[i] * v[i] @ v[i] + 0.5 * w[i] @ (I[i] @ w[i])
                       for i in range(len(bodies))))
    KE_post = float(0.5 * M * v_com @ v_com + 0.5 * w_plus @ (I_comb @ w_plus))
    dT = KE_pre - KE_post

    # conservation residuals about the INERTIAL ORIGIN (independent of the r_com bookkeeping)
    P_pre = (m[:, None] * v).sum(axis=0)
    H0_pre = sum(I[i] @ w[i] + m[i] * np.cross(r[i], v[i]) for i in range(len(bodies)))
    H0_post = I_comb @ w_plus + M * np.cross(r_com, v_com)
    H_ref = max(np.linalg.norm(H0_pre), 1e-30)
    P_ref = max(np.linalg.norm(P_pre), 1e-30)
    res = {"M": M, "r_com": r_com, "v_com": v_com, "I_comb": I_comb,
           "w_plus": w_plus, "H_com": H, "impulses": impulses,
           "KE_pre": KE_pre, "KE_post": KE_post, "dT": dT,
           "eps_P": float(np.linalg.norm((M * v_com) - P_pre) / P_ref),
           "eps_H_origin": float(np.linalg.norm(H0_post - H0_pre) / H_ref)}
    res["validity"] = {"momentum_ok": res["eps_P"] < 1e-12 and res["eps_H_origin"] < 1e-10,
                       "plastic_dT_nonneg": dT >= -1e-12 * max(KE_pre, 1e-30)}
    return res

def rigidize_point_contact(bodies, point):
    """Plastic POINT capture (3-DOF): a pure force impulse J at `point` equalizes the two
    bodies' material-point velocities there; rotations remain free (ideal ball joint at the
    grasp instant, no couple transmitted). bodies = [b1, b2] only.

        Delassus:  K_i = (1/m_i) E - [d_i]x I_i^-1 [d_i]x ,  d_i = point - r_i
        (K_1 + K_2) J = v_p2 - v_p1 ,  body1 gets +J, body2 gets -J

    Returns dict with per-body (dv, dw), impulse J, post point velocity, dT.
    Conserves total P and H exactly (equal/opposite impulse at one point)."""
    assert len(bodies) == 2
    def skew(a):
        return np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    p = np.asarray(point, float)
    K = np.zeros((3, 3)); vp = []
    for b in bodies:
        d = p - np.asarray(b["r"], float)
        Dx = skew(d)
        K += np.eye(3)/b["m"] - Dx @ np.linalg.inv(np.asarray(b["I"], float)) @ Dx
        vp.append(np.asarray(b["v"], float) + np.cross(b["w"], d))
    J = np.linalg.solve(K, vp[1] - vp[0])
    out = {"J": J, "impulses": []}
    KE_pre = KE_post = 0.0
    for sgn, b in zip((+1.0, -1.0), bodies):
        d = p - np.asarray(b["r"], float)
        dv = sgn * J / b["m"]
        dw = sgn * np.linalg.solve(np.asarray(b["I"], float), np.cross(d, J))
        out["impulses"].append({"dv": dv, "dw": dw})
        KE_pre += 0.5*b["m"]*np.dot(b["v"], b["v"]) + 0.5*np.dot(b["w"], np.asarray(b["I"]) @ b["w"])
        v2, w2 = np.asarray(b["v"]) + dv, np.asarray(b["w"]) + dw
        KE_post += 0.5*b["m"]*np.dot(v2, v2) + 0.5*np.dot(w2, np.asarray(b["I"]) @ w2)
    out["KE_pre"], out["KE_post"], out["dT"] = KE_pre, KE_post, KE_pre - KE_post
    b1, b2 = bodies
    out["v_point_post"] = (np.asarray(b1["v"]) + out["impulses"][0]["dv"]
                           + np.cross(np.asarray(b1["w"]) + out["impulses"][0]["dw"],
                                      p - np.asarray(b1["r"])))
    return out

def junction_couple(result, bodies, i, point):
    """Couple transmitted at junction `point` to body i, assuming the whole impulse acts
    there: L_i(p) = dL_com_i - (p - r_i) x J_i. Returns (J_i, L_at_point)."""
    imp = result["impulses"][i]
    lever = np.asarray(point, float) - np.asarray(bodies[i]["r"], float)
    return imp["J"], imp["dL_com"] - np.cross(lever, imp["J"])

# ---------------- project capture-scenario builder (SSOT-consistent) ----------------

TUMBLE_AXIS = np.array([1.0, 0.15, 0.4]); TUMBLE_AXIS = TUMBLE_AXIS / np.linalg.norm(TUMBLE_AXIS)
L1, L2, M1, M2 = 0.30, 0.25, 0.80, 0.50     # reBot_arm_v0_min.urdf
MOUNT_X = 0.18525                            # T_SM X translation [m]
EE_X = MOUNT_X + L1 + L2

GRASP = {  # grasp point relative to target CoM (CAD JSON features: grasp_point - cg)
    "target_debris_v0":    np.array([0.660, 0.0, 0.950]) - np.array([0.00027, 0.0, -0.07054]),
    "target_satellite_v0": np.array([0.290, 0.0, 0.000]) - np.array([0.03827, 0.0, 0.00021]),
}

_stack_cache = {}

def chaser_stack():
    """Servicer + adapter + extended arm as one rigid stack (v0: arm frozen along +X_S).
    Returns (mass, CoM in frame S, I about stack CoM, EE x-coordinate)."""
    if "s" not in _stack_cache:
        serv = load_object("servicer_12U_v0"); adap = load_object("robot_mount_adapter_v0")
        parts = [
            (serv["mass"], np.array(serv["cg"], float), serv["I"]),
            (adap["mass"], np.array([MOUNT_X, 0.0, 0.0]), adap["I"]),
            (M1, np.array([MOUNT_X + L1/2, 0.0, 0.0]), np.diag([0.0, M1*L1**2/12, M1*L1**2/12])),
            (M2, np.array([MOUNT_X + L1 + L2/2, 0.0, 0.0]), np.diag([0.0, M2*L2**2/12, M2*L2**2/12])),
        ]
        m_tot = sum(p[0] for p in parts)
        com = sum(p[0]*p[1] for p in parts) / m_tot
        I = sum(p[2] + steiner(p[0], p[1] - com) for p in parts)
        _stack_cache["s"] = (m_tot, com, I, EE_X)
    return _stack_cache["s"]

def build_capture_scenario(target_id, tumble_dps, v_app, grasp_scale=1.0, inertia_scale=1.0):
    """Capture-instant state, target CoM at origin & translationally at rest, tumbling at
    tumble_dps about TUMBLE_AXIS. Chaser approaches along the grasp-feature normal +X
    (sim_02/sim_04 convention): EE at the grasp point, stack extending outward along +X,
    residual closing speed v_app, chaser attitude held (w=0). Stack reach axis (+X_S)
    points toward the target (-X inertial): X-flip leaves the stack inertia diagonal-blocks
    unchanged (R=diag(-1,-1,1) commutes with I up to sign-symmetric off-diagonals).
    inertia_scale scales the TARGET inertia tensor (uncertainty dimension of sim_04).
    Returns (bodies [chaser, target], meta)."""
    tgt = load_object(target_id)
    m_c, com_c, I_c, ee_x = chaser_stack()
    r_g = GRASP[target_id] * grasp_scale
    A = np.array([1.0, 0.0, 0.0])
    R_flip = np.diag([-1.0, -1.0, 1.0])          # +X_S -> -X inertial
    bodies = [
        {"m": m_c, "I": R_flip @ I_c @ R_flip.T,
         "r": r_g + A * (ee_x - com_c[0]), "v": -v_app * A, "w": np.zeros(3)},
        {"m": tgt["mass"], "I": np.asarray(tgt["I"], float) * inertia_scale,
         "r": np.zeros(3), "v": np.zeros(3), "w": np.deg2rad(tumble_dps) * TUMBLE_AXIS},
    ]
    return bodies, {"target": tgt, "r_g": r_g, "chaser_mass": m_c}

def capture_post_state(target_id, tumble_dps, v_app, grasp_scale=1.0, inertia_scale=1.0):
    """Convenience: build scenario, rigidize, return (result, bodies, meta)."""
    bodies, meta = build_capture_scenario(target_id, tumble_dps, v_app, grasp_scale, inertia_scale)
    return rigidize(bodies), bodies, meta
