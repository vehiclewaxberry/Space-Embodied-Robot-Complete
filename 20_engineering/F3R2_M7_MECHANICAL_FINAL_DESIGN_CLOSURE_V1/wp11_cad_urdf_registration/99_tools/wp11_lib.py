"""WP11 CAD<->accepted-URDF registration library.

Self-contained: binary-STL / ASCII+binary-PLY readers, URDF parse, forward
kinematics, rigid registration (Kabsch + ICP), point-to-triangle distance.
No FreeCAD, no SolidWorks, no trimesh.  numpy + scipy only.

Units: everything internal is MILLIMETRES unless a name says _m.
"""
import hashlib
import os
import struct
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial import cKDTree

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


# ----------------------------------------------------------------- hashing ---
def sha256_and_size(path):
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            n += len(b)
            h.update(b)
    return h.hexdigest().upper(), n


def sha256_lf_normalised(path):
    """SHA-256 of the file with CRLF collapsed to LF (see CRLF false-alarm note)."""
    raw = open(path, "rb").read()
    norm = raw.replace(b"\r\n", b"\n")
    return (
        hashlib.sha256(raw).hexdigest().upper(),
        len(raw),
        hashlib.sha256(norm).hexdigest().upper(),
        len(norm),
    )


# --------------------------------------------------------------- mesh I/O ---
def read_binary_stl(path, scale=1.0):
    """Return (tri (N,3,3) float64, ntri).  Verifies the declared triangle
    count against the real file size (silent truncation guard)."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        f.read(80)
        ntri = struct.unpack("<I", f.read(4))[0]
        if size != 84 + 50 * ntri:
            raise ValueError(
                "STL size/count mismatch %s: size=%d declared=%d" % (path, size, ntri)
            )
        buf = f.read(50 * ntri)
    a = np.frombuffer(buf, dtype=np.uint8).reshape(ntri, 50)
    vf = np.frombuffer(a[:, :48].tobytes(), dtype="<f4").reshape(ntri, 4, 3)
    tri = vf[:, 1:, :].astype(np.float64) * scale
    return tri, ntri


def read_ply(path, scale=1.0):
    """Minimal PLY reader (ascii + binary_little_endian) -> (verts, faces)."""
    with open(path, "rb") as f:
        raw = f.read()
    idx = raw.find(b"end_header")
    header = raw[:idx].decode("ascii", "replace")
    body_off = raw.find(b"\n", idx) + 1
    fmt = None
    n_v = n_f = 0
    vprops = []
    section = None
    for line in header.splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] == "format":
            fmt = t[1]
        elif t[0] == "element":
            section = t[1]
            if t[1] == "vertex":
                n_v = int(t[2])
            elif t[1] == "face":
                n_f = int(t[2])
        elif t[0] == "property" and section == "vertex":
            vprops.append((t[1], t[2]))
    if fmt == "ascii":
        toks = raw[body_off:].split()
        nv_props = len(vprops)
        vals = np.array(toks[: n_v * nv_props], dtype=np.float64).reshape(n_v, nv_props)
        verts = vals[:, :3] * scale
        faces = None
        if n_f:
            rest = toks[n_v * nv_props :]
            faces = []
            k = 0
            for _ in range(n_f):
                c = int(rest[k])
                faces.append([int(x) for x in rest[k + 1 : k + 1 + c]][:3])
                k += 1 + c
            faces = np.array(faces, dtype=np.int64)
        return verts, faces
    if fmt != "binary_little_endian":
        raise ValueError("unsupported ply format %r in %s" % (fmt, path))
    np_of = {
        "float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8",
        "uchar": "u1", "uint8": "u1", "char": "i1", "int8": "i1",
        "ushort": "<u2", "uint16": "<u2", "short": "<i2", "int16": "<i2",
        "uint": "<u4", "uint32": "<u4", "int": "<i4", "int32": "<i4",
    }
    dt = np.dtype([("p%d" % i, np_of[p[0]]) for i, p in enumerate(vprops)])
    vb = np.frombuffer(raw, dtype=dt, count=n_v, offset=body_off)
    verts = np.stack([vb["p0"], vb["p1"], vb["p2"]], axis=1).astype(np.float64) * scale
    off = body_off + n_v * dt.itemsize
    faces = None
    if n_f:
        # assume uchar count + int32 indices, triangles
        rec = np.dtype([("n", "u1"), ("i", "<i4", 3)])
        fb = np.frombuffer(raw, dtype=rec, count=n_f, offset=off)
        faces = fb["i"].astype(np.int64)
    return verts, faces


def tri_to_verts(tri):
    return tri.reshape(-1, 3)


def mesh_volume_and_area(tri):
    a, b, c = tri[:, 0, :], tri[:, 1, :], tri[:, 2, :]
    cr = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(cr, axis=1)
    vol = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
    return float(vol.sum()), float(area.sum())


def unique_verts(v, decimals=6):
    q = np.round(v, decimals)
    _, idx = np.unique(q, axis=0, return_index=True)
    return v[np.sort(idx)]


# -------------------------------------------------------------- transforms ---
def T(R=None, t=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if t is not None:
        M[:3, 3] = t
    return M


def rpy_to_R(r, p, y):
    cr, sr = np.cos(r), np.sin(r)
    cp, sp = np.cos(p), np.sin(p)
    cy, sy = np.cos(y), np.sin(y)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def axis_angle_R(axis, ang):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * (K @ K)


def apply_T(M, pts):
    return pts @ M[:3, :3].T + M[:3, 3]


def inv_T(M):
    R = M[:3, :3]
    out = np.eye(4)
    out[:3, :3] = R.T
    out[:3, 3] = -R.T @ M[:3, 3]
    return out


def R_to_axis_angle(R):
    """Return (axis unit, angle rad) from a rotation matrix."""
    c = (np.trace(R) - 1.0) / 2.0
    c = max(-1.0, min(1.0, c))
    ang = float(np.arccos(c))
    if ang < 1e-12:
        return np.array([0.0, 0.0, 1.0]), 0.0
    if abs(np.pi - ang) < 1e-6:
        A = (R + np.eye(3)) / 2.0
        i = int(np.argmax(np.diag(A)))
        ax = A[:, i] / np.sqrt(max(A[i, i], 1e-300))
        return ax / np.linalg.norm(ax), ang
    ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (
        2 * np.sin(ang)
    )
    return ax / np.linalg.norm(ax), ang


# --------------------------------------------------------------- URDF / FK ---
class Urdf(object):
    def __init__(self, path):
        self.path = path
        tree = ET.parse(path)
        root = tree.getroot()
        self.name = root.get("name")
        self.links = []
        self.link_mesh = {}
        self.inertial = {}
        for lk in root.findall("link"):
            n = lk.get("name")
            self.links.append(n)
            col = lk.find("collision/geometry/mesh")
            if col is not None:
                self.link_mesh[n] = col.get("filename")
            ine = lk.find("inertial")
            if ine is not None:
                o = ine.find("origin")
                self.inertial[n] = {
                    "mass": float(ine.find("mass").get("value")),
                    "com": [float(x) for x in (o.get("xyz") if o is not None else "0 0 0").split()],
                }
        self.joints = []
        for j in root.findall("joint"):
            o = j.find("origin")
            xyz = [float(x) for x in (o.get("xyz") if o is not None else "0 0 0").split()]
            rpy = [float(x) for x in ((o.get("rpy") if o is not None else None) or "0 0 0").split()]
            ax = j.find("axis")
            lim = j.find("limit")
            self.joints.append(
                {
                    "name": j.get("name"),
                    "type": j.get("type"),
                    "parent": j.find("parent").get("link"),
                    "child": j.find("child").get("link"),
                    "xyz_m": xyz,
                    "rpy": rpy,
                    "axis": [float(x) for x in (ax.get("xyz") if ax is not None else "0 0 1").split()],
                    "lower": None if lim is None or lim.get("lower") is None else float(lim.get("lower")),
                    "upper": None if lim is None or lim.get("upper") is None else float(lim.get("upper")),
                }
            )
        parents = set(j["child"] for j in self.joints)
        self.root_link = [l for l in self.links if l not in parents]

    def fk(self, q, T_mount_mm, gripper_travel_m=0.0):
        """q = 6 revolute values (rad).  Returns {link: 4x4 in mount parent frame,
        translation in MM}.  T_mount_mm maps base_link -> S (mm)."""
        out = {self.root_link[0]: np.array(T_mount_mm, float)}
        qi = 0
        for j in self.joints:
            Tp = out[j["parent"]]
            Tj = T(rpy_to_R(*j["rpy"]), np.array(j["xyz_m"]) * 1000.0)
            if j["type"] == "revolute":
                Tq = T(axis_angle_R(j["axis"], q[qi]))
                qi += 1
            elif j["type"] == "prismatic":
                Tq = T(None, np.asarray(j["axis"], float) * gripper_travel_m * 1000.0)
            else:
                Tq = np.eye(4)
            out[j["child"]] = Tp @ Tj @ Tq
        return out


# ------------------------------------------------------- rigid registration ---
def kabsch(P, Q):
    """Best rigid transform M with M*P ~= Q (no scaling). P,Q (N,3)."""
    cp, cq = P.mean(0), Q.mean(0)
    H = (P - cp).T @ (Q - cq)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T
    return T(R, cq - R @ cp)


def _octahedral_rotations():
    """The 24 proper rotations of the cube (axis-permutation datum candidates)."""
    out = []
    base = np.eye(3)
    for perm in [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]:
        Pm = base[list(perm), :]
        for s in range(8):
            S = np.diag([1 - 2 * ((s >> k) & 1) for k in range(3)]).astype(float)
            R = S @ Pm
            if abs(np.linalg.det(R) - 1.0) < 1e-9:
                out.append(R)
    return out


OCT24 = _octahedral_rotations()


def icp(src, dst_tree, dst_pts, M0, iters=60, tol=1e-10, trim=1.0):
    """Point-to-point ICP.  src (N,3) moving, dst KD-tree + points fixed."""
    M = M0.copy()
    prev = None
    for _ in range(iters):
        p = apply_T(M, src)
        d, idx = dst_tree.query(p, k=1, workers=-1)
        if trim < 1.0:
            keep = d <= np.quantile(d, trim)
        else:
            keep = np.ones(len(d), bool)
        M = kabsch(src[keep], dst_pts[idx[keep]])
        rms = float(np.sqrt((d[keep] ** 2).mean()))
        if prev is not None and abs(prev - rms) < tol:
            break
        prev = rms
    p = apply_T(M, src)
    d, _ = dst_tree.query(p, k=1, workers=-1)
    return M, d


class _Bucket(object):
    def __init__(self, tri, rmax):
        self.a = tri[:, 0, :]
        self.b = tri[:, 1, :]
        self.c = tri[:, 2, :]
        self.rmax = float(rmax)
        self.n = len(tri)
        self.tree = cKDTree((self.a + self.b + self.c) / 3.0)


class TriDist(object):
    """EXACT unsigned point->triangle-soup distance with a *proved* broad phase.

    A triangle j can hold a point closer than d only if |p - centroid_j| <
    d + circumradius_j.  A single global r_max is useless when a soup mixes
    0.1 mm and 200 mm triangles (a flat face tessellates into a few huge
    triangles), so triangles are bucketed by circumradius in octaves; each
    bucket carries its own r_max and its own KD-tree, and k grows per bucket
    until the bound holds.  `unverified_count` is the number of query points
    for which the bound could not be established -- it is reported, never
    silently treated as verified.
    """

    def __init__(self, tri):
        a, b, c = tri[:, 0, :], tri[:, 1, :], tri[:, 2, :]
        cen = (a + b + c) / 3.0
        rad = np.maximum.reduce(
            [
                np.linalg.norm(a - cen, axis=1),
                np.linalg.norm(b - cen, axis=1),
                np.linalg.norm(c - cen, axis=1),
            ]
        )
        self.n = len(tri)
        self.rmax = float(rad.max())
        edges = [0.0]
        r = 0.25
        while r < self.rmax * 2:
            edges.append(r)
            r *= 4.0
        edges.append(np.inf)
        self.buckets = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (rad > lo) & (rad <= hi)
            if m.sum():
                self.buckets.append(_Bucket(tri[m], rad[m].max()))

    def query(self, pts, k0=24, kmax=8192, chunk_budget=2.0e7):
        best = np.full(len(pts), np.inf)
        unver = np.zeros(len(pts), bool)
        for B in self.buckets:
            todo = np.arange(len(pts))
            k = k0
            while len(todo):
                k_eff = min(k, B.n)
                step = max(32, min(8192, int(chunk_budget / max(k_eff, 1))))
                ok = np.zeros(len(todo), bool)
                for s in range(0, len(todo), step):
                    sel = todo[s : s + step]
                    P = pts[sel]
                    dc, ic = B.tree.query(P, k=k_eff, workers=-1)
                    if k_eff == 1:
                        dc = dc[:, None]
                        ic = ic[:, None]
                    ic = np.minimum(ic, B.n - 1)
                    d = _pt_tri_min_batch(P, B.a[ic], B.b[ic], B.c[ic])
                    best[sel] = np.minimum(best[sel], d)
                    ok[s : s + len(sel)] = (k_eff >= B.n) | (
                        dc[:, -1] >= best[sel] + B.rmax
                    )
                todo = todo[~ok]
                if k_eff >= B.n or k >= kmax:
                    break
                k *= 8
            if len(todo):
                unver[todo] = True
        self.unverified_count = int(unver.sum())
        return best


def _pt_tri_min_batch(P, A, B, C):
    """Min distance from each point P[i] (N,3) to its own triangle batch
    A/B/C[i] (N,K,3).  Fully vectorised; returns (N,)."""
    p = P[:, None, :]
    E0 = B - A
    E1 = C - A
    D = A - p
    aa = np.einsum("ijk,ijk->ij", E0, E0)
    bb = np.einsum("ijk,ijk->ij", E0, E1)
    cc = np.einsum("ijk,ijk->ij", E1, E1)
    dd = np.einsum("ijk,ijk->ij", E0, D)
    ee = np.einsum("ijk,ijk->ij", E1, D)
    det = np.maximum(aa * cc - bb * bb, 1e-300)
    s = np.clip((bb * ee - cc * dd) / det, 0.0, 1.0)
    t = np.clip((bb * dd - aa * ee) / det, 0.0, 1.0)
    over = (s + t) > 1.0
    den = np.maximum(aa - 2 * bb + cc, 1e-300)
    u = np.clip((cc + ee - bb - dd) / den, 0.0, 1.0)
    s = np.where(over, u, s)
    t = np.where(over, 1.0 - u, t)
    q = A + s[..., None] * E0 + t[..., None] * E1
    d = np.linalg.norm(q - p, axis=2)
    for X, Y in ((A, B), (B, C), (C, A)):
        Ed = Y - X
        L2 = np.maximum(np.einsum("ijk,ijk->ij", Ed, Ed), 1e-300)
        w = np.clip(np.einsum("ijk,ijk->ij", p - X, Ed) / L2, 0.0, 1.0)
        d = np.minimum(d, np.linalg.norm(X + w[..., None] * Ed - p, axis=2))
    return d.min(axis=1)


def _pt_tri_min(p, A, B, C):
    """Min distance from a single point to a batch of triangles (Eberly)."""
    E0 = B - A
    E1 = C - A
    D = A - p
    aa = np.einsum("ij,ij->i", E0, E0)
    bb = np.einsum("ij,ij->i", E0, E1)
    cc = np.einsum("ij,ij->i", E1, E1)
    dd = np.einsum("ij,ij->i", E0, D)
    ee = np.einsum("ij,ij->i", E1, D)
    ff = np.einsum("ij,ij->i", D, D)
    det = np.maximum(aa * cc - bb * bb, 1e-300)
    s = bb * ee - cc * dd
    t = bb * dd - aa * ee
    s = s / det
    t = t / det
    # clamp to the triangle by projecting onto the 3 edges + 3 vertices
    s = np.clip(s, 0.0, 1.0)
    t = np.clip(t, 0.0, 1.0)
    over = s + t > 1.0
    if over.any():
        # project onto edge s+t=1
        num = (cc + ee - bb - dd)[over]
        den = (aa - 2 * bb + cc)[over]
        u = np.clip(np.where(den > 1e-300, num / np.maximum(den, 1e-300), 0.0), 0.0, 1.0)
        s[over] = u
        t[over] = 1.0 - u
    q = A + s[:, None] * E0 + t[:, None] * E1
    d_face = np.linalg.norm(q - p, axis=1)
    # unconditional vertex/edge fallbacks keep it an upper bound that is tight
    d = d_face
    for X, Y in ((A, B), (B, C), (C, A)):
        Ed = Y - X
        L2 = np.maximum(np.einsum("ij,ij->i", Ed, Ed), 1e-300)
        u = np.clip(np.einsum("ij,ij->i", p - X, Ed) / L2, 0.0, 1.0)
        d = np.minimum(d, np.linalg.norm(X + u[:, None] * Ed - p, axis=1))
    return float(d.min())


def sample_surface(tri, n, seed=0):
    """Area-weighted uniform surface sampling (barycentric)."""
    rng = np.random.default_rng(seed)
    a, b, c = tri[:, 0, :], tri[:, 1, :], tri[:, 2, :]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    tot = area.sum()
    if tot <= 0:
        idx = rng.integers(0, len(tri), n)
    else:
        idx = rng.choice(len(tri), size=n, p=area / tot)
    u = rng.random(n)
    v = rng.random(n)
    m = u + v > 1
    u[m] = 1 - u[m]
    v[m] = 1 - v[m]
    return a[idx] + u[:, None] * (b[idx] - a[idx]) + v[:, None] * (c[idx] - a[idx])


def stats(d):
    d = np.asarray(d, float)
    return {
        "n": int(d.size),
        "mean_mm": float(d.mean()),
        "median_mm": float(np.median(d)),
        "p95_mm": float(np.percentile(d, 95)),
        "p99_mm": float(np.percentile(d, 99)),
        "max_mm": float(d.max()),
        "rms_mm": float(np.sqrt((d ** 2).mean())),
        "frac_le_0p5mm": float((d <= 0.5).mean()),
        "frac_le_1mm": float((d <= 1.0).mean()),
        "frac_le_2mm": float((d <= 2.0).mean()),
    }


def aabb(v):
    return v.min(0), v.max(0)


def pca_extents(v):
    """Principal-axis extents (sorted desc) of a point cloud, plus the axes."""
    c = v.mean(0)
    X = v - c
    C = X.T @ X / len(X)
    w, V = np.linalg.eigh(C)
    order = np.argsort(-w)
    V = V[:, order]
    P = X @ V
    ext = P.max(0) - P.min(0)
    return ext, V, c
