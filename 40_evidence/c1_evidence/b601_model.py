"""b601_model.py -- arm_b601_v1 model loading + kinematics (sim_05).

Parses 20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf (xml.etree, no external
URDF library) and provides FK / geometric Jacobians for the 6R chain
joint1..joint6 (all revolute about the local z axis; joint2 axis is (0,0,-1)).

Gripper handling (dynamics v1): gripper_joint is fixed, gripper_joint1/2 are
prismatic finger joints which are LOCKED at q=0 (capture-ready position).
The three gripper bodies (gripper_link, gripper_left, gripper_right) are merged
rigidly into link6 by composite mass / CoM / parallel-axis inertia.

Frames
------
S   servicer body frame (SSOT). The arm URDF base frame A0 (= base_link frame,
    = mounting-face frame M since T_MA0 = identity) is placed at T_SM:
        t_SM = [0.18525, 0, 0] m,  R_SM = R_y(+90 deg)
        (columns of R_SM are the M axes in S: +Z_M=+X_S, +Y_M=+Y_S, +X_M=-Z_S)
    Frozen per coordinate_frame_definition_v0.md sec 3.1 (nominal_frozen_v1,
    decision D-2). DO NOT change the numbers here.
E   end-effector frame. Origin = origin of gripper_link (child of gripper_joint)
    = link6 origin + 0.15971 m along +z_link6 (URDF: <origin xyz="0 0 0.15971">).
    Orientation: axes ALIGNED WITH link6, so +z_E is the tool approach axis
    (the URDF gripper_link frame itself carries an extra rpy=(0,-1.5708,0);
    its +x axis coincides with our +z_E; we keep link6 axes so that "tool z"
    means the approach direction).

URDF rpy convention: fixed-axis extrinsic XYZ,  R = Rz(yaw) @ Ry(pitch) @ Rx(roll).
Inertial handling: URDF <inertia> is expressed in the <inertial><origin> frame
(about the CoM). If that origin carries a non-zero rpy the tensor is rotated
into the link frame (B601 has rpy=0 everywhere, but it is handled generally).

Pure numpy. No files outside 30_simulation/sim_05_free_floating_arm are modified.
"""
import os
import xml.etree.ElementTree as ET
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
URDF_PATH = os.path.normpath(os.path.join(
    HERE, "..", "..", "cad", "spacecraft_layout", "arm_b601_v1", "arm_b601_v1.urdf"))

# ---------------------------------------------------------------- T_SM (frozen)
T_SM_t = np.array([0.18525, 0.0, 0.0])
R_SM = np.array([[0.0, 0.0, 1.0],
                 [0.0, 1.0, 0.0],
                 [-1.0, 0.0, 0.0]])
EE_OFFSET_LINK6 = np.array([0.0, 0.0, 0.15971])   # E origin in link6 frame [m]

CHAIN_JOINTS = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
CHAIN_LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6"]


# ---------------------------------------------------------------- math helpers
def skew(v):
    return np.array([[0.0, -v[2], v[1]],
                     [v[2], 0.0, -v[0]],
                     [-v[1], v[0], 0.0]])


def rpy_to_R(rpy):
    """URDF rpy -> rotation matrix. R = Rz(yaw) @ Ry(pitch) @ Rx(roll)."""
    r, p, y = rpy
    cr, sr = np.cos(r), np.sin(r)
    cp, sp = np.cos(p), np.sin(p)
    cy, sy = np.cos(y), np.sin(y)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def rot_axis(axis, q):
    """Rodrigues rotation about a unit axis by angle q."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    K = skew(a)
    return np.eye(3) + np.sin(q) * K + (1.0 - np.cos(q)) * (K @ K)


def make_T(R=None, p=None):
    T = np.eye(4)
    if R is not None:
        T[:3, :3] = R
    if p is not None:
        T[:3, 3] = p
    return T


def T_SM_4x4():
    return make_T(R_SM, T_SM_t)


def transform_inertial(T, m, cg, I):
    """Re-express a body inertial (m, CoM position, inertia about CoM) given the
    body-frame pose T (4x4) in the new frame. Inertia stays about the CoM."""
    R, p = T[:3, :3], T[:3, 3]
    return m, R @ cg + p, R @ I @ R.T


def combine_inertials(bodies):
    """Combine rigid bodies [(m, cg, I_about_cg), ...] expressed in one common
    frame into a single (m, cg, I_about_combined_cg) via parallel-axis theorem."""
    m_tot = sum(b[0] for b in bodies)
    cg = sum(b[0] * np.asarray(b[1], float) for b in bodies) / m_tot
    I = np.zeros((3, 3))
    for m, c, Ic in bodies:
        d = np.asarray(c, float) - cg
        I += Ic + m * ((d @ d) * np.eye(3) - np.outer(d, d))
    return m_tot, cg, I


# ---------------------------------------------------------------- URDF parsing
def _parse_origin(el):
    xyz = np.zeros(3)
    rpy = np.zeros(3)
    if el is not None:
        if el.get("xyz"):
            xyz = np.array([float(v) for v in el.get("xyz").split()])
        if el.get("rpy"):
            rpy = np.array([float(v) for v in el.get("rpy").split()])
    return xyz, rpy


def parse_urdf(path=URDF_PATH):
    """Return (links, joints): links[name] = {mass, cg, I} in the LINK frame
    (I about CoM, link axes); joints[name] = dict with origin T, axis, type,
    parent, child, limits."""
    root = ET.parse(path).getroot()
    links, joints = {}, {}
    for le in root.findall("link"):
        name = le.get("name")
        ine = le.find("inertial")
        m = float(ine.find("mass").get("value"))
        oxyz, orpy = _parse_origin(ine.find("origin"))
        ie = ine.find("inertia")
        ixx, iyy, izz = (float(ie.get(k)) for k in ("ixx", "iyy", "izz"))
        ixy, ixz, iyz = (float(ie.get(k)) for k in ("ixy", "ixz", "iyz"))
        I = np.array([[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]])
        Rin = rpy_to_R(orpy)              # inertia given in inertial-origin frame
        I_link = Rin @ I @ Rin.T          # -> link-frame axes (about CoM)
        links[name] = {"mass": m, "cg": oxyz, "I": I_link}
    for je in root.findall("joint"):
        name = je.get("name")
        oxyz, orpy = _parse_origin(je.find("origin"))
        ax = je.find("axis")
        axis = (np.array([float(v) for v in ax.get("xyz").split()])
                if ax is not None else np.array([0.0, 0.0, 1.0]))
        lim = je.find("limit")
        joints[name] = {
            "name": name, "type": je.get("type"),
            "parent": je.find("parent").get("link"),
            "child": je.find("child").get("link"),
            "T_origin": make_T(rpy_to_R(orpy), oxyz),
            "axis": axis,
            "lower": float(lim.get("lower")) if lim is not None and lim.get("lower") else None,
            "upper": float(lim.get("upper")) if lim is not None and lim.get("upper") else None,
        }
    return links, joints


# ---------------------------------------------------------------- arm model
class B601Arm:
    """6R arm model with gripper bodies rigidly merged into link6."""

    def __init__(self, urdf_path=URDF_PATH):
        self.urdf_path = urdf_path
        self.links_raw, self.joints_all = parse_urdf(urdf_path)
        self.joints = [self.joints_all[j] for j in CHAIN_JOINTS]
        self.body = {ln: dict(self.links_raw[ln]) for ln in CHAIN_LINKS}
        self._merge_gripper_into_link6()
        self.total_mass = sum(self.body[ln]["mass"] for ln in CHAIN_LINKS)

    # -- gripper merge (fingers locked at q=0, capture-ready) ------------------
    def _merge_gripper_into_link6(self):
        jg = self.joints_all["gripper_joint"]        # fixed
        jl = self.joints_all["gripper_joint1"]       # prismatic, locked q=0
        jr = self.joints_all["gripper_joint2"]       # prismatic, locked q=0
        T6_g = jg["T_origin"]                        # gripper_link in link6
        T6_l = T6_g @ jl["T_origin"]                 # gripper_left in link6
        T6_r = T6_g @ jr["T_origin"]                 # gripper_right in link6
        parts = [(np.eye(4), self.links_raw["link6"]),
                 (T6_g, self.links_raw["gripper_link"]),
                 (T6_l, self.links_raw["gripper_left"]),
                 (T6_r, self.links_raw["gripper_right"])]
        merged = combine_inertials(
            [transform_inertial(T, b["mass"], b["cg"], b["I"]) for T, b in parts])
        self.body["link6"] = {"mass": merged[0], "cg": merged[1], "I": merged[2]}
        self.T_link6_gripper = T6_g                  # kept for reference / E doc

    # -- forward kinematics -----------------------------------------------------
    def fk(self, q, T_base=None):
        """FK for q (6,). T_base = pose of base_link (frame A0=M) in the output
        frame; default T_SM (output frame = servicer body frame S).
        Returns dict: T[linkname] 4x4, T_E 4x4 (E axes = link6 axes),
        joint_origins (6,3), joint_axes (6,3) in the output frame."""
        q = np.asarray(q, float)
        if T_base is None:
            T_base = T_SM_4x4()
        T = {CHAIN_LINKS[0]: np.array(T_base, float)}
        origins = np.zeros((6, 3))
        axes = np.zeros((6, 3))
        Tcur = T[CHAIN_LINKS[0]]
        for i, jnt in enumerate(self.joints):
            Tj = Tcur @ jnt["T_origin"]              # joint frame before rotation
            origins[i] = Tj[:3, 3]
            axes[i] = Tj[:3, :3] @ jnt["axis"]       # world axis (invariant to q_i)
            Tcur = Tj @ make_T(rot_axis(jnt["axis"], q[i]))
            T[jnt["child"]] = Tcur
        T_E = Tcur @ make_T(None, EE_OFFSET_LINK6)   # E: link6 axes, offset origin
        return {"T": T, "T_E": T_E, "joint_origins": origins, "joint_axes": axes}

    # -- geometric Jacobian of E ------------------------------------------------
    def jacobian(self, q, T_base=None, fk_out=None):
        """6x6 geometric Jacobian of E ([v; w], base frame fixed), expressed in
        the same frame as fk (default S). Column i: [a_i x (p_E - o_i); a_i]."""
        f = fk_out if fk_out is not None else self.fk(q, T_base)
        pE = f["T_E"][:3, 3]
        J = np.zeros((6, 6))
        for i in range(6):
            a, o = f["joint_axes"][i], f["joint_origins"][i]
            J[:3, i] = np.cross(a, pE - o)
            J[3:, i] = a
        return J

    def Jp(self, q, T_base=None):
        """3x6 position task Jacobian."""
        return self.jacobian(q, T_base)[:3, :]

    def tool_axis(self, q, T_base=None, fk_out=None):
        """Tool approach axis = +z_E = +z_link6, in the fk output frame."""
        f = fk_out if fk_out is not None else self.fk(q, T_base)
        return f["T_E"][:3, 2].copy()

    def J5(self, q, a_des=None, T_base=None):
        """5x6 task Jacobian: rows 1-3 EE position; rows 4-5 tool-axis alignment
        error rates. Alignment error e = a x a_des (a = current tool z axis);
        de/dt = (w x a) x a_des = [a_des]x [a]x w, projected on two orthonormal
        directions n1, n2 spanning the plane perpendicular to a_des."""
        f = self.fk(q, T_base)
        J = self.jacobian(q, fk_out=f)
        a = self.tool_axis(q, fk_out=f)
        if a_des is None:
            a_des = a.copy()
        a_des = np.asarray(a_des, float)
        a_des = a_des / np.linalg.norm(a_des)
        seed = np.array([1.0, 0.0, 0.0])
        if abs(a_des @ seed) > 0.9:
            seed = np.array([0.0, 1.0, 0.0])
        n1 = np.cross(a_des, seed)
        n1 /= np.linalg.norm(n1)
        n2 = np.cross(a_des, n1)
        N = np.vstack([n1, n2])                      # 2x3
        rows_att = N @ skew(a_des) @ skew(a) @ J[3:, :]
        return np.vstack([J[:3, :], rows_att])

    # -- per-link CoM kinematics for dynamics ------------------------------------
    def link_com_states(self, q, T_base=None):
        """For each moving link k=1..6 (link6 = composite with gripper) return
        dict(name, mass, c (CoM pos), R (link rotation), I (about CoM, output-
        frame axes), Jv (3x6), Jw (3x6)) -- Jacobians of the CoM w.r.t. qdot with
        the base held fixed, all in the fk output frame (default S)."""
        f = self.fk(q, T_base)
        out = []
        for k, ln in enumerate(CHAIN_LINKS[1:], start=1):   # link1..link6
            Tk = f["T"][ln]
            Rk, pk = Tk[:3, :3], Tk[:3, 3]
            b = self.body[ln]
            c = Rk @ b["cg"] + pk
            I = Rk @ b["I"] @ Rk.T
            Jv = np.zeros((3, 6))
            Jw = np.zeros((3, 6))
            for i in range(k):                              # joints 1..k move link k
                a, o = f["joint_axes"][i], f["joint_origins"][i]
                Jv[:, i] = np.cross(a, c - o)
                Jw[:, i] = a
            out.append({"name": ln, "mass": b["mass"], "c": c, "R": Rk,
                        "I": I, "Jv": Jv, "Jw": Jw})
        return out

    def base_link_inertial_in_S(self):
        """Arm base_link body (rigid with the mount) expressed in S."""
        b = self.body["base_link"]
        return transform_inertial(T_SM_4x4(), b["mass"], b["cg"], b["I"])


if __name__ == "__main__":
    arm = B601Arm()
    q0 = np.zeros(6)
    f0 = arm.fk(q0, T_base=np.eye(4))
    fS = arm.fk(q0)
    print("total arm mass [kg]:", round(arm.total_mass, 6))
    print("link6 composite mass [kg]:", round(arm.body["link6"]["mass"], 6))
    print("E @ q=0 in A0:", np.round(f0["T_E"][:3, 3], 6))
    print("E @ q=0 in S :", np.round(fS["T_E"][:3, 3], 6))
    print("tool z @ q=0 in S:", np.round(arm.tool_axis(q0), 6))
