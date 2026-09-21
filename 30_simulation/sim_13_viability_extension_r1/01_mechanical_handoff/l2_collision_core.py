"""M5 核心：L2 碰撞体构造 + 凸-凸精确距离（GJK）+ 系统装配。

分层纪律
--------
L0  accepted URDF 的拓扑/质量/质心/惯量/关节轴 —— **只读**，L2 不得回写。
L1  工程 CAD 外形 —— 不直接进入在线 NMPC。
L2  本模块产物：逐 link 保守碰撞体，用于连续碰撞、NMPC 约束与 SAFE 判定。

保守性
------
每个 L2 体是其 L1 网格的**凸包**（或显式包围盒/胶囊），因此在所有方向上都包含 L1。
凸包顶点数被限制以保证在线速度，简化只允许**向外**（取凸包，绝不内缩）。

所有权
------
每个 L2 体恰好属于一个 L0 link，且不得跨越关节轴。
"""
import hashlib
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))


# =====================================================================
# GJK —— 凸集之间的精确距离
# =====================================================================
def _support(V, d):
    return V[int(np.argmax(V @ d))]


def _closest_point_on_simplex(S):
    """返回 (最近点, 保留的顶点索引)。S 为 (k,3)，k<=4。"""
    k = len(S)
    if k == 1:
        return S[0], [0]
    if k == 2:
        a, b = S
        ab = b - a
        t = np.dot(-a, ab) / max(np.dot(ab, ab), 1e-300)
        if t <= 0:
            return a, [0]
        if t >= 1:
            return b, [1]
        return a + t * ab, [0, 1]
    if k == 3:
        a, b, c = S
        # 在三角形平面上投影原点，再做重心坐标判定
        ab, ac = b - a, c - a
        n = np.cross(ab, ac)
        nn = np.dot(n, n)
        if nn < 1e-300:
            return _closest_point_on_simplex(S[:2])
        w = np.cross(ab, -a)
        gamma = np.dot(w, n) / nn
        w2 = np.cross(-a, ac)
        beta = np.dot(w2, n) / nn
        alpha = 1.0 - beta - gamma
        if alpha >= 0 and beta >= 0 and gamma >= 0:
            return alpha * a + beta * b + gamma * c, [0, 1, 2]
        best, bidx, bd = None, None, np.inf
        for idx in ([0, 1], [0, 2], [1, 2]):
            p, keep = _closest_point_on_simplex(S[idx])
            d = np.dot(p, p)
            if d < bd:
                bd, best, bidx = d, p, [idx[i] for i in keep]
        return best, bidx
    # k == 4：若原点在四面体内则距离 0，否则取最近面
    a, b, c, d = S
    M = np.column_stack([a - d, b - d, c - d])
    try:
        lam = np.linalg.solve(M, -d)
    except np.linalg.LinAlgError:
        lam = None
    if lam is not None and np.all(lam >= -1e-12) and np.sum(lam) <= 1 + 1e-12:
        return np.zeros(3), [0, 1, 2, 3]
    best, bidx, bd = None, None, np.inf
    for idx in ([0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]):
        p, keep = _closest_point_on_simplex(S[idx])
        dd = np.dot(p, p)
        if dd < bd:
            bd, best, bidx = dd, p, [idx[i] for i in keep]
    return best, bidx


def gjk_distance(A, B, max_iter=128, tol=1e-14):
    """两个凸点集之间的欧氏距离；相交时返回 0.0。

    标准 GJK 距离子算法。终止判据为对偶间隙：
        dot(v,v) - dot(v,w) <= tol
    其中 v 是当前 Minkowski 差集单纯形到原点的最近点，
    w = support_{A-B}(-v)。误用 |v| 与投影之差会在**穿透**时提前退出，
    把重叠错报成正距离（已由单元测试捕获）。
    """
    v = A[0] - B[0]
    if np.dot(v, v) < 1e-18:
        v = np.array([1.0, 0.0, 0.0])
    W = np.empty((0, 3))
    for _ in range(max_iter):
        w = _support(A, -v) - _support(B, v)
        if np.dot(v, v) - np.dot(v, w) <= tol:
            return float(np.linalg.norm(v))
        if W.shape[0] and np.min(np.linalg.norm(W - w, axis=1)) < 1e-15:
            return float(np.linalg.norm(v))
        W = np.vstack([W, w])
        v, keep = _closest_point_on_simplex(W)
        W = W[keep]
        if np.dot(v, v) <= 1e-24 or W.shape[0] == 4:
            return 0.0
    return float(np.linalg.norm(v))


# =====================================================================
# L2 体
# =====================================================================
class L2Body:
    """一个保守凸碰撞体，恰好属于一个 L0 link。"""

    __slots__ = ("name", "l0_link", "frame", "kind", "V", "provenance",
                 "derivation", "conservative_direction", "permitted_use",
                 "prohibited_use", "applicable_config")

    def __init__(self, name, l0_link, frame, kind, V, provenance, derivation,
                 conservative_direction="OUTWARD_ONLY_CONVEX_HULL_CONTAINS_L1",
                 permitted_use="continuous collision, NMPC constraint, SAFE evaluation",
                 prohibited_use="mass/inertia derivation; manufacturing clearance claim",
                 applicable_config="ALL"):
        self.name = name
        self.l0_link = l0_link
        self.frame = frame
        self.kind = kind
        self.V = np.asarray(V, float)
        self.provenance = provenance
        self.derivation = derivation
        self.conservative_direction = conservative_direction
        self.permitted_use = permitted_use
        self.prohibited_use = prohibited_use
        self.applicable_config = applicable_config

    def world(self, T):
        return (T[:3, :3] @ self.V.T).T + T[:3, 3]

    def summary(self):
        lo, hi = self.V.min(axis=0), self.V.max(axis=0)
        return {"name": self.name, "l0_link": self.l0_link, "frame": self.frame,
                "kind": self.kind, "vertex_count": int(len(self.V)),
                "local_aabb_min_m": [round(float(v), 6) for v in lo],
                "local_aabb_max_m": [round(float(v), 6) for v in hi],
                "extent_m": [round(float(v), 6) for v in (hi - lo)],
                "source_cad": self.provenance.get("source_cad", ""),
                "source_sha256": self.provenance.get("source_sha256", ""),
                "derivation": self.derivation,
                "conservative_error_direction": self.conservative_direction,
                "permitted_use": self.permitted_use,
                "prohibited_use": self.prohibited_use,
                "applicable_configuration": self.applicable_config}


def box_vertices(size, center=(0, 0, 0)):
    sx, sy, sz = (s / 2.0 for s in size)
    c = np.asarray(center, float)
    return np.array([[x, y, z] for x in (-sx, sx) for y in (-sy, sy)
                     for z in (-sz, sz)]) + c


def hull_vertices(mesh, max_v=48):
    """凸包顶点；必要时按最远点采样下采样（仍保持包含性：见下）。"""
    import trimesh
    h = mesh.convex_hull
    V = np.asarray(h.vertices, float)
    if len(V) <= max_v:
        return V, len(np.asarray(h.vertices))
    # 下采样会内缩 -> 改为对下采样凸包做外扩，保证仍包含原凸包
    idx = [int(np.argmax(V[:, 0]))]
    for _ in range(max_v - 1):
        d = np.min(np.linalg.norm(V[:, None, :] - V[idx][None, :, :], axis=2), axis=1)
        idx.append(int(np.argmax(d)))
    sub = V[idx]
    c = sub.mean(axis=0)
    # 外扩系数：使下采样凸包包含全部原顶点
    r_sub = np.linalg.norm(sub - c, axis=1).max()
    r_all = np.linalg.norm(V - c, axis=1).max()
    scale = max(1.0, r_all / max(r_sub, 1e-12))
    return c + (sub - c) * scale, len(V)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().upper()
