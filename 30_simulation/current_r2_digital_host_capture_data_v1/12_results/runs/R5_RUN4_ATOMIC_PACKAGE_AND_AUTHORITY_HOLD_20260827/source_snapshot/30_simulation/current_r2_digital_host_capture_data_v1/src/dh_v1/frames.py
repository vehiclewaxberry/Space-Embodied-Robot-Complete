"""Frame and transform contract (S00).

Conventions (must match 02_frames_units/TRANSFORM_CONVENTION.md):
  * R_AB maps vectors expressed in B into A:  v_A = R_AB @ v_B  (active convention,
    "pose of B seen from A").
  * Homogeneous transform T_A_B = [[R_AB, p_AB],[0,1]] where p_AB is the origin of
    B expressed in A. Composition: T_A_C = T_A_B @ T_B_C.
  * URDF <origin rpy="r p y"> is fixed-axis (extrinsic) XYZ:
    R = Rz(yaw) @ Ry(pitch) @ Rx(roll), and gives T_parent_child.
  * Quaternions are stored (w, x, y, z), unit norm, and represent R_A_B.
"""
from __future__ import annotations

import numpy as np


class FrameContractViolation(RuntimeError):
    pass


def rotx(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)


def roty(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float)


def rotz(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def rpy_to_R(rpy) -> np.ndarray:
    """URDF fixed-axis XYZ convention: R = Rz(y) @ Ry(p) @ Rx(r)."""
    r, p, y = (float(v) for v in rpy)
    return rotz(y) @ roty(p) @ rotx(r)


def make_T(R: np.ndarray, p) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = np.asarray(p, dtype=float)
    return T


def T_from_urdf_origin(xyz, rpy) -> np.ndarray:
    return make_T(rpy_to_R(rpy), xyz)


def invert_T(T: np.ndarray) -> np.ndarray:
    R = T[:3, :3]
    p = T[:3, 3]
    Ti = np.eye(4)
    Ti[:3, :3] = R.T
    Ti[:3, 3] = -R.T @ p
    return Ti


def assert_rotation(R: np.ndarray, tol: float = 1.0e-9) -> None:
    if R.shape != (3, 3):
        raise FrameContractViolation(f"rotation shape {R.shape} != (3,3)")
    err_orth = np.max(np.abs(R.T @ R - np.eye(3)))
    det = float(np.linalg.det(R))
    if err_orth > tol or abs(det - 1.0) > tol:
        raise FrameContractViolation(
            f"matrix is not a proper rotation: orthogonality error {err_orth:.3e}, det {det:.12f}"
        )


# --- quaternions (w, x, y, z), representing R_A_B ------------------------------
def quat_normalize(q, tol_warn: float = 1.0e-6):
    q = np.asarray(q, dtype=float)
    n = float(np.linalg.norm(q))
    if n == 0.0:
        raise FrameContractViolation("zero quaternion cannot be normalized")
    return q / n, abs(n - 1.0)


def quat_to_R(q) -> np.ndarray:
    q, _ = quat_normalize(q)
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ],
        dtype=float,
    )


def R_to_quat(R: np.ndarray) -> np.ndarray:
    assert_rotation(R, tol=1.0e-7)
    w = 0.5 * np.sqrt(max(0.0, 1.0 + R[0, 0] + R[1, 1] + R[2, 2]))
    if w > 1e-8:
        x = (R[2, 1] - R[1, 2]) / (4 * w)
        y = (R[0, 2] - R[2, 0]) / (4 * w)
        z = (R[1, 0] - R[0, 1]) / (4 * w)
    else:  # fall back on largest diagonal element
        i = int(np.argmax(np.diag(R)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = np.sqrt(max(0.0, R[i, i] - R[j, j] - R[k, k] + 1.0)) * 0.5
        v = np.zeros(3)
        v[i] = s
        v[j] = (R[j, i] + R[i, j]) / (4 * s)
        v[k] = (R[k, i] + R[i, k]) / (4 * s)
        w = (R[k, j] - R[j, k]) / (4 * s)
        x, y, z = v
    q = np.array([w, x, y, z])
    q, _ = quat_normalize(q)
    if q[0] < 0:
        q = -q
    return q


def quat_mul(q1, q2) -> np.ndarray:
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ],
        dtype=float,
    )


def quat_derivative(q, omega_body) -> np.ndarray:
    """dq/dt for body-frame angular velocity omega (rad/s), q = q_W_B."""
    wq = np.concatenate([[0.0], np.asarray(omega_body, dtype=float)])
    return 0.5 * quat_mul(q, wq)


def skew(v) -> np.ndarray:
    x, y, z = (float(a) for a in v)
    return np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]], dtype=float)


def parallel_axis_about_point(I_com: np.ndarray, mass: float, r_com_from_point) -> np.ndarray:
    """Inertia about an arbitrary point P given inertia about the CoM.
    r_com_from_point = position of CoM relative to P, expressed in the same frame.
    I_P = I_com + m * (|r|^2 I3 - r r^T)  [Huygens-Steiner]
    """
    r = np.asarray(r_com_from_point, dtype=float)
    return np.asarray(I_com, dtype=float) + mass * ((r @ r) * np.eye(3) - np.outer(r, r))
