"""sim_09 -- multi-start damped-least-squares IK for the B601 6R arm.

Task modes (task Jacobian J_task is m x 6):
  pose_6d     m=6: EE position (3) + full orientation (3, rotation-vector error)
  approach_5d m=5: EE position (3) + tool-z / approach-axis alignment (2)
              (rows 4-5 identical to the validated B601Arm.J5 construction)
  position_3d m=3: EE position only

Solver: damped least squares (Levenberg style adaptive damping), joint updates
clipped into the URDF limits (parsed by sim_05 b601_model -- single source).
Multi-start: q0 of the candidate + N_SEEDS deterministic uniform seeds drawn
inside the limits with a FIXED rng seed (20260712) -> the solver is bitwise
deterministic across calls.

ALL converged solutions are kept (deduplicated at joint-space distance
> 0.1 rad); each carries residuals, joint-limit margin, task-Jacobian singular
values, condition number, task rank and nullity. The SELECTED solution (index 0)
is the converged solution closest to q0 in joint space (ties broken
lexicographically) -- documented deterministic policy.

Arm base pose = frozen T_SM (b601_model.T_SM_4x4(), decision D-2); all task
quantities expressed in the servicer frame S.
"""
import _bootstrap  # noqa: F401
import numpy as np
from scipy.spatial.transform import Rotation

from b601_model import B601Arm, skew  # validated sim_05 model (read-only import)

IK_SEED = 20260712
N_SEEDS = 8
MAX_ITER = 300
POS_TOL = 1e-9          # m   (t2 requirement is 1e-6 -- solved 3 decades tighter)
ORI_TOL = 1e-8          # rad-equivalent on orientation/alignment rows
DEDUP_DIST = 0.1        # rad joint-space deduplication distance
RANK_RTOL = 1e-8        # singular values below RANK_RTOL*sigma_max count as zero

_ARM_CACHE = {}


def get_arm():
    if "arm" not in _ARM_CACHE:
        _ARM_CACHE["arm"] = B601Arm()
    return _ARM_CACHE["arm"]


def joint_limits(arm=None):
    arm = arm or get_arm()
    lo = np.array([j["lower"] for j in arm.joints], float)
    hi = np.array([j["upper"] for j in arm.joints], float)
    return lo, hi


def _axis_plane_basis(a_des):
    """Orthonormal (n1, n2) spanning the plane perpendicular to a_des.
    EXACT mirror of the deterministic construction inside B601Arm.J5 so the
    residual rows and the Jacobian rows use the same basis."""
    a_des = np.asarray(a_des, float)
    a_des = a_des / np.linalg.norm(a_des)
    seed = np.array([1.0, 0.0, 0.0])
    if abs(a_des @ seed) > 0.9:
        seed = np.array([0.0, 1.0, 0.0])
    n1 = np.cross(a_des, seed)
    n1 /= np.linalg.norm(n1)
    n2 = np.cross(a_des, n1)
    return n1, n2


def make_task(mode, p_des, R_des=None, a_des=None):
    """Task descriptor. p_des in S; R_des = desired EE rotation (pose_6d);
    a_des = desired tool-z axis in S (approach_5d)."""
    task = {"mode": mode, "p_des": np.asarray(p_des, float).reshape(3)}
    if mode == "pose_6d":
        if R_des is None:
            raise ValueError("pose_6d needs R_des")
        task["R_des"] = np.asarray(R_des, float).reshape(3, 3)
    elif mode == "approach_5d":
        if a_des is None:
            raise ValueError("approach_5d needs a_des")
        a = np.asarray(a_des, float).reshape(3)
        task["a_des"] = a / np.linalg.norm(a)
    elif mode != "position_3d":
        raise ValueError(f"unknown task mode {mode}")
    return task


def residual_and_jacobian(arm, q, task):
    """Return (residual r (m,), J_task (m,6), aux). Convention: J_task @ dq = r
    drives the error to zero (r is the desired instantaneous task-space move)."""
    f = arm.fk(q)
    J = arm.jacobian(q, fk_out=f)
    pE = f["T_E"][:3, 3]
    r_pos = task["p_des"] - pE
    mode = task["mode"]
    aux = {"fk": f}
    if mode == "position_3d":
        return r_pos, J[:3, :], aux
    if mode == "pose_6d":
        R_E = f["T_E"][:3, :3]
        r_vec = Rotation.from_matrix(task["R_des"] @ R_E.T).as_rotvec()
        aux["ori_err_rad"] = float(np.linalg.norm(r_vec))
        return np.concatenate([r_pos, r_vec]), J, aux
    # approach_5d
    a = f["T_E"][:3, 2]
    a_des = task["a_des"]
    n1, n2 = _axis_plane_basis(a_des)
    N = np.vstack([n1, n2])
    # J5 rows (identical algebra to B601Arm.J5): d(e)/dt = N [a_des]x [a]x w
    rows_att = N @ skew(a_des) @ skew(a) @ J[3:, :]
    # alignment error e = a x a_des -> desired change -e (projected)
    r_att = -(N @ np.cross(a, a_des))
    aux["ori_err_rad"] = float(np.arccos(np.clip(a @ a_des, -1.0, 1.0)))
    return np.concatenate([r_pos, r_att]), np.vstack([J[:3, :], rows_att]), aux


def _converged(r, mode):
    if np.linalg.norm(r[:3]) >= POS_TOL:
        return False
    if mode == "position_3d":
        return True
    return np.linalg.norm(r[3:]) < ORI_TOL


def _dls_solve(arm, task, q_init, lo, hi):
    """Single-start adaptive DLS. Returns q or None."""
    q = np.clip(np.asarray(q_init, float).copy(), lo, hi)
    lam = 1e-3
    r, J, _ = residual_and_jacobian(arm, q, task)
    cost = float(r @ r)
    for _ in range(MAX_ITER):
        if _converged(r, task["mode"]):
            return q
        m = J.shape[0]
        dq = J.T @ np.linalg.solve(J @ J.T + lam * np.eye(m), r)
        step = np.linalg.norm(dq)
        if step > 0.5:                       # trust-region style step clamp [rad]
            dq *= 0.5 / step
        q_new = np.clip(q + dq, lo, hi)
        r_new, J_new, _ = residual_and_jacobian(arm, q_new, task)
        cost_new = float(r_new @ r_new)
        if cost_new < cost:
            q, r, J, cost = q_new, r_new, J_new, cost_new
            lam = max(lam * 0.5, 1e-12)
        else:
            lam = min(lam * 10.0, 1e6)
            if lam >= 1e6 and step < 1e-14:
                break                        # stagnated
    return q if _converged(r, task["mode"]) else None


def _diagnose(arm, q, task, lo, hi):
    r, J, aux = residual_and_jacobian(arm, q, task)
    sv = np.linalg.svd(J, compute_uv=False)
    smax = float(sv[0])
    rank = int(np.sum(sv > RANK_RTOL * smax))
    return {
        "q": [float(v) for v in q],
        "residual_position": float(np.linalg.norm(r[:3])),
        "residual_orientation": float(aux.get("ori_err_rad", 0.0)),
        "joint_limit_margin": float(np.min(np.minimum(q - lo, hi - q))),
        "jacobian_singular_values": [float(s) for s in sv],
        "condition_number": float(smax / sv[-1]) if sv[-1] > 0 else float("inf"),
        "task_rank": rank,
        "task_nullity": int(6 - rank),
    }


def solve_ik(task, q0, arm=None, n_seeds=N_SEEDS):
    """Multi-start DLS-IK. Returns list of solution dicts, deterministic order:
    index 0 = converged solution closest to q0 (joint-space 2-norm, ties broken
    by lexicographic q). Empty list = IK failure."""
    arm = arm or get_arm()
    lo, hi = joint_limits(arm)
    q0 = np.asarray(q0, float).reshape(6)
    rng = np.random.default_rng(IK_SEED)     # fixed seed -> identical every call
    starts = [q0] + [rng.uniform(lo + 0.05, hi - 0.05) for _ in range(n_seeds)]

    sols = []
    for qs in starts:
        q = _dls_solve(arm, task, qs, lo, hi)
        if q is None:
            continue
        if any(np.linalg.norm(q - np.asarray(s["q"])) <= DEDUP_DIST for s in sols):
            continue
        sols.append(_diagnose(arm, q, task, lo, hi))
    sols.sort(key=lambda s: (float(np.linalg.norm(np.asarray(s["q"]) - q0)),
                             tuple(s["q"])))
    return sols
