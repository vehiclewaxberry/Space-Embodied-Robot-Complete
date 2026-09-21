"""Mesh loading / display decimation / shading helpers (VIZ-Gate 0).

trimesh 4.12.2 is available but fast_simplification / open3d are NOT installed
(iron rule 5: no heavy pip installs), so display decimation is done with a
deterministic vertex-clustering reducer implemented here: vertices are snapped
to a voxel grid, clusters merged, degenerate faces dropped; the pitch is grown
geometrically until the face budget is met. Display-only -- the decimated
meshes are never used for any physics/geometry claim.
"""
import _viz_bootstrap  # noqa: F401
import hashlib

import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

_MESH_CACHE = {}


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def load_mesh(path):
    if path not in _MESH_CACHE:
        _MESH_CACHE[path] = trimesh.load(path, force="mesh")
    return _MESH_CACHE[path]


def decimate_vertex_cluster(mesh, target_faces=20000, max_iter=12):
    """Deterministic vertex-clustering decimation to <= target_faces.
    Returns (vertices, faces) as plain arrays (display use only)."""
    V = np.asarray(mesh.vertices, float)
    F = np.asarray(mesh.faces, np.int64)
    if len(F) <= target_faces:
        return V.copy(), F.copy()
    diag = float(np.linalg.norm(V.max(axis=0) - V.min(axis=0)))
    pitch = diag / 256.0
    for _ in range(max_iter):
        keys = np.floor(V / pitch).astype(np.int64)
        # cluster id per vertex
        _, inv = np.unique(keys, axis=0, return_inverse=True)
        # new vertex = mean of cluster members
        n_clusters = int(inv.max()) + 1
        sums = np.zeros((n_clusters, 3))
        counts = np.zeros(n_clusters)
        np.add.at(sums, inv, V)
        np.add.at(counts, inv, 1.0)
        NV = sums / counts[:, None]
        NF = inv[F]
        good = ((NF[:, 0] != NF[:, 1]) & (NF[:, 1] != NF[:, 2])
                & (NF[:, 0] != NF[:, 2]))
        NF = NF[good]
        # dedupe faces (orientation-preserving key)
        NF = np.unique(NF, axis=0)
        if len(NF) <= target_faces:
            return NV, NF
        pitch *= 1.5
    return NV, NF  # best effort


def transform_vf(V, F, T):
    """Apply a 4x4 transform to vertices."""
    Vh = V @ T[:3, :3].T + T[:3, 3]
    return Vh, F


def shaded_collection(V, F, color, alpha=1.0, light=(0.35, -0.5, 0.8),
                      shade=(0.45, 1.0), edge=False):
    """Poly3DCollection with simple Lambertian shading of `color`."""
    tri = V[F]                                     # (n,3,3)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1)
    ln[ln == 0] = 1.0
    n = n / ln[:, None]
    L = np.asarray(light, float)
    L = L / np.linalg.norm(L)
    lam = np.abs(n @ L)                            # two-sided
    lo, hi = shade
    k = lo + (hi - lo) * lam
    base = np.asarray(color, float)[:3]
    face_rgba = np.empty((len(F), 4))
    face_rgba[:, :3] = np.clip(base[None, :] * k[:, None], 0, 1)
    face_rgba[:, 3] = alpha
    pc = Poly3DCollection(tri, facecolors=face_rgba,
                          edgecolors=("k" if edge else "none"),
                          linewidths=0.1 if edge else 0.0)
    return pc


def cylinder_vf(radius, z0, z1, n=48, cap=True):
    """Cylinder about local +Z between z0..z1. Returns (V, F)."""
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring0 = np.stack([radius * np.cos(th), radius * np.sin(th),
                      np.full(n, float(z0))], axis=1)
    ring1 = np.stack([radius * np.cos(th), radius * np.sin(th),
                      np.full(n, float(z1))], axis=1)
    V = [ring0, ring1]
    F = []
    for i in range(n):
        j = (i + 1) % n
        F.append([i, j, n + j])
        F.append([i, n + j, n + i])
    idx = 2 * n
    if cap:
        V.append(np.array([[0.0, 0.0, z0], [0.0, 0.0, z1]]))
        for i in range(n):
            j = (i + 1) % n
            F.append([idx, j, i])          # bottom cap
            F.append([idx + 1, n + i, n + j])
    return np.vstack(V), np.asarray(F, np.int64)


def cone_vf(apex, axis, half_angle_deg, length, n=40):
    """Open cone from apex along axis. Returns (V, F)."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    seed = np.array([0.0, 0.0, 1.0]) if abs(a[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(a, seed)
    u /= np.linalg.norm(u)
    v = np.cross(a, u)
    r = length * np.tan(np.deg2rad(half_angle_deg))
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rim = (np.asarray(apex, float) + length * a
           + r * (np.cos(th)[:, None] * u + np.sin(th)[:, None] * v))
    V = np.vstack([np.asarray(apex, float)[None, :], rim])
    F = [[0, 1 + i, 1 + (i + 1) % n] for i in range(n)]
    return V, np.asarray(F, np.int64)


def box_vf(center, dims):
    """Axis-aligned box. Returns (V, F)."""
    c = np.asarray(center, float)
    d = np.asarray(dims, float) / 2.0
    sgn = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1)
                    for sz in (-1, 1)], float)
    V = c + sgn * d
    F = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5],
                  [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6],
                  [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]], np.int64)
    return V, F
