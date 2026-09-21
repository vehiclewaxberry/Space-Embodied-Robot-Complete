"""Featherstone 6D spatial algebra. Vector ordering: [angular(3); linear(3)].

Motion vectors (twists) transform with X_motion; force-type covectors (wrenches,
momenta) transform with X_force. Both are built from T_A_B = (R_AB, p_AB) as
defined in dh_v1.frames (v_A = R_AB v_B, p_AB = origin of B expressed in A).
"""
from __future__ import annotations

import numpy as np

from .frames import skew


def X_motion(T_A_B: np.ndarray) -> np.ndarray:
    """Motion transform: v_A = X_motion(T_A_B) @ v_B (spatial velocity about the
    respective frame origins, expressed in the respective frames)."""
    R = T_A_B[:3, :3]
    p = T_A_B[:3, 3]
    X = np.zeros((6, 6))
    X[:3, :3] = R
    X[3:, :3] = skew(p) @ R
    X[3:, 3:] = R
    return X


def X_force(T_A_B: np.ndarray) -> np.ndarray:
    """Force/momentum transform: f_A = X_force(T_A_B) @ f_B."""
    R = T_A_B[:3, :3]
    p = T_A_B[:3, 3]
    X = np.zeros((6, 6))
    X[:3, :3] = R
    X[:3, 3:] = skew(p) @ R
    X[3:, 3:] = R
    return X


def crm(v: np.ndarray) -> np.ndarray:
    """Spatial motion cross product matrix: crm(v) @ m = v x m (motion)."""
    w = v[:3]
    vl = v[3:]
    C = np.zeros((6, 6))
    C[:3, :3] = skew(w)
    C[3:, :3] = skew(vl)
    C[3:, 3:] = skew(w)
    return C


def crf(v: np.ndarray) -> np.ndarray:
    """Spatial force cross product matrix: crf(v) @ f = v x* f (force)."""
    return -crm(v).T


def spatial_inertia(mass: float, com, I_com: np.ndarray) -> np.ndarray:
    """6x6 spatial inertia about the body-frame origin, expressed in body frame.
    com = CoM position in body frame; I_com = 3x3 inertia about CoM in body frame.
    """
    c = skew(com)
    I = np.zeros((6, 6))
    I[:3, :3] = np.asarray(I_com, dtype=float) + mass * (c @ c.T)
    I[:3, 3:] = mass * c
    I[3:, :3] = mass * c.T
    I[3:, 3:] = mass * np.eye(3)
    return I


def transform_spatial_inertia(I_B: np.ndarray, T_A_B: np.ndarray) -> np.ndarray:
    """Re-express a spatial inertia given in frame B into frame A:
    I_A = X_force(T_A_B) @ I_B @ X_motion(T_B_A) = Xf @ I_B @ Xm^{-1}."""
    Xf = X_force(T_A_B)
    from .frames import invert_T

    Xm_inv = X_motion(invert_T(T_A_B))
    return Xf @ I_B @ Xm_inv
