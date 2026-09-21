"""Independent B601 visual-chain renderer (VIZ-Gate 0).

Assembles the per-link VISUAL transform chain of 20_engineering/cad/spacecraft_layout/
arm_b601_v1/arm_b601_v1.urdf from scratch (own URDF parse, own rpy->R, own
axis-angle) -- deliberately NOT importing the kinematics of
30_simulation/sim_05_free_floating_arm/b601_model.py, so that the two chains can be
cross-checked against each other (VIZ-Gate FK alignment criterion:
position < 1 mm, orientation < 0.1 deg).  b601_model.B601Arm.fk is imported
ONLY inside fk_alignment_selftest() as the numerical truth reference.

Chain (all from the URDF, nothing hardcoded except the frozen T_SM which is
read from 20_engineering/config/geometry/frame_tree_v1.yaml):

    T_S_base   = T_SM  (frame M == URDF base_link frame A0, T_MA0 = identity
                        per the URDF header comment / SSOT sec 3.1)
    T_S_linkN  = T_S_parent @ T_joint_origin @ Rot(axis, q_i)      (revolute)
    T_S_child  = T_S_parent @ T_joint_origin @ Trans(axis * q_i)   (prismatic)
    visual pose of a link's mesh = T_S_link @ T_visual_origin

Gripper: gripper_joint is fixed; gripper_joint1/2 prismatic fingers are locked
at q = 0 (capture-ready), matching the dynamics-v1 convention.

E convention frame (matches b601_model): origin = gripper_joint origin
translation applied in link6 axes (URDF xyz "0 0 0.15971"), axes = link6 axes
(the URDF gripper_link frame itself carries an extra rpy which is NOT part of
the E convention -- it IS applied to the gripper meshes).
"""
import _viz_bootstrap  # noqa: F401  (env pins BEFORE numpy)
import os
import xml.etree.ElementTree as ET

import numpy as np
import yaml

URDF_PATH = _viz_bootstrap.URDF_PATH

CHAIN_JOINTS = ("joint1", "joint2", "joint3", "joint4", "joint5", "joint6")
GRIPPER_JOINTS = ("gripper_joint", "gripper_joint1", "gripper_joint2")
ALL_LINKS = ("base_link", "link1", "link2", "link3", "link4", "link5", "link6",
             "gripper_link", "gripper_left", "gripper_right")


# ------------------------------------------------------------- own math
def _rpy_to_R(rpy):
    """URDF rpy (fixed-axis extrinsic XYZ): R = Rz(y) @ Ry(p) @ Rx(r)."""
    r, p, y = float(rpy[0]), float(rpy[1]), float(rpy[2])
    sr, cr = np.sin(r), np.cos(r)
    sp, cp = np.sin(p), np.cos(p)
    sy, cy = np.sin(y), np.cos(y)
    return np.array([
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp,     cp * sr,                cp * cr]])


def _axis_angle_R(axis, q):
    """Rodrigues, own implementation."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    x, y, z = a
    c, s, C = np.cos(q), np.sin(q), 1.0 - np.cos(q)
    return np.array([
        [c + x * x * C,     x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, c + y * y * C,     y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def _T(R=None, p=None):
    T = np.eye(4)
    if R is not None:
        T[:3, :3] = R
    if p is not None:
        T[:3, 3] = np.asarray(p, float)
    return T


def load_T_SM(frame_tree_yaml=_viz_bootstrap.FRAME_TREE_YAML):
    """Frozen T_SM read from the geometry SSOT frame tree (mm -> m)."""
    with open(frame_tree_yaml, encoding="utf-8") as f:
        tree = yaml.safe_load(f)
    m = tree["frames"]["M"]["transform_S_M"]
    t = np.asarray(m["translation_mm"], float) / 1000.0
    rot = m["rotation"]
    assert rot["type"] == "R_y", rot
    ang = np.deg2rad(float(rot["deg"]))
    R = _axis_angle_R([0.0, 1.0, 0.0], ang)
    return _T(R, t)


# ------------------------------------------------------------- URDF parse
def _origin_of(el):
    xyz, rpy = np.zeros(3), np.zeros(3)
    o = el.find("origin")
    if o is not None:
        if o.get("xyz"):
            xyz = np.array([float(v) for v in o.get("xyz").split()])
        if o.get("rpy"):
            rpy = np.array([float(v) for v in o.get("rpy").split()])
    return xyz, rpy


class B601VisualChain:
    """Visual transform chain for arm_b601_v1.urdf (display side)."""

    def __init__(self, urdf_path=URDF_PATH):
        self.urdf_path = urdf_path
        root = ET.parse(urdf_path).getroot()
        self.joints = {}
        for je in root.findall("joint"):
            xyz, rpy = _origin_of(je)
            ax = je.find("axis")
            axis = (np.array([float(v) for v in ax.get("xyz").split()])
                    if ax is not None else np.array([0.0, 0.0, 1.0]))
            self.joints[je.get("name")] = {
                "type": je.get("type"),
                "parent": je.find("parent").get("link"),
                "child": je.find("child").get("link"),
                "T_origin": _T(_rpy_to_R(rpy), xyz),
                "axis": axis,
            }
        # visuals: mesh filename (relative to URDF dir) + visual origin
        self.visuals = {}
        urdf_dir = os.path.dirname(os.path.abspath(urdf_path))
        for le in root.findall("link"):
            vis = le.find("visual")
            if vis is None:
                continue
            xyz, rpy = _origin_of(vis)
            mesh = vis.find("geometry/mesh")
            self.visuals[le.get("name")] = {
                "mesh_path": os.path.normpath(
                    os.path.join(urdf_dir, mesh.get("filename"))),
                "T_visual": _T(_rpy_to_R(rpy), xyz),
            }
        # E convention offset: translation of gripper_joint, applied in link6
        # axes (rotation of that joint origin intentionally NOT applied to E).
        self.ee_offset_link6 = self.joints["gripper_joint"]["T_origin"][:3, 3].copy()

    def link_poses(self, q, T_base=None):
        """Poses of ALL links (incl. gripper bodies, fingers locked at 0) and
        the E convention frame, in the T_base frame (default: frozen T_SM ->
        output frame = servicer body frame S)."""
        q = np.asarray(q, float).reshape(6)
        if T_base is None:
            T_base = load_T_SM()
        T = {"base_link": np.array(T_base, float)}
        for i, jname in enumerate(CHAIN_JOINTS):
            j = self.joints[jname]
            Tj = T[j["parent"]] @ j["T_origin"]
            T[j["child"]] = Tj @ _T(_axis_angle_R(j["axis"], q[i]))
        for jname in GRIPPER_JOINTS:
            j = self.joints[jname]
            Tj = T[j["parent"]] @ j["T_origin"]
            if j["type"] == "prismatic":          # locked at q = 0
                T[j["child"]] = Tj
            else:                                 # fixed
                T[j["child"]] = Tj
        T_E = T["link6"] @ _T(None, self.ee_offset_link6)
        return {"T": T, "T_E": T_E}

    def visual_poses(self, q, T_base=None):
        """[(link_name, mesh_path, T_world_mesh 4x4), ...] for display."""
        lp = self.link_poses(q, T_base)["T"]
        out = []
        for name, vis in self.visuals.items():
            out.append((name, vis["mesh_path"], lp[name] @ vis["T_visual"]))
        return out


# ------------------------------------------------------------- self-test
def _ori_err_deg(Ra, Rb):
    c = (np.trace(Ra.T @ Rb) - 1.0) / 2.0
    return float(np.rad2deg(np.arccos(np.clip(c, -1.0, 1.0))))


def fk_alignment_selftest(n_random=50, seed=20260714, verbose=True):
    """Cross-check this independent visual chain against the numerical truth
    b601_model.B601Arm.fk. Criterion: pos < 1 mm, ori < 0.1 deg over link1..6
    and E, at q = 0, the E1.5 selected configuration, and n_random samples
    within the joint limits."""
    from b601_model import B601Arm, T_SM_4x4  # truth source (read-only import)
    arm = B601Arm()
    chain = B601VisualChain()
    T_SM = load_T_SM()
    err_T_SM = np.max(np.abs(T_SM - T_SM_4x4()))

    rng = np.random.default_rng(seed)
    limits = [(arm.joints_all[j]["lower"], arm.joints_all[j]["upper"])
              for j in CHAIN_JOINTS]
    q_e15_selected = np.array([-1.4722592995215e-05, -1.0482002296028672,
                               -1.3989828152470143, -1.220010067943876,
                               3.673218594813444e-06, 1.8395811591278994e-05])
    q_list = [np.zeros(6), q_e15_selected]
    for _ in range(n_random):
        q_list.append(np.array([rng.uniform(lo, hi) for lo, hi in limits]))

    max_pos_mm, max_ori_deg = 0.0, 0.0
    for q in q_list:
        truth = arm.fk(q)                 # default T_base = frozen T_SM
        mine = chain.link_poses(q)
        for ln in ("link1", "link2", "link3", "link4", "link5", "link6"):
            dp = np.linalg.norm(truth["T"][ln][:3, 3] - mine["T"][ln][:3, 3])
            do = _ori_err_deg(truth["T"][ln][:3, :3], mine["T"][ln][:3, :3])
            max_pos_mm = max(max_pos_mm, dp * 1e3)
            max_ori_deg = max(max_ori_deg, do)
        dpE = np.linalg.norm(truth["T_E"][:3, 3] - mine["T_E"][:3, 3])
        doE = _ori_err_deg(truth["T_E"][:3, :3], mine["T_E"][:3, :3])
        max_pos_mm = max(max_pos_mm, dpE * 1e3)
        max_ori_deg = max(max_ori_deg, doE)

    ok = (max_pos_mm < 1.0) and (max_ori_deg < 0.1) and (err_T_SM < 1e-9)
    report = {
        "n_configs": len(q_list),
        "max_pos_err_mm": max_pos_mm,
        "max_ori_err_deg": max_ori_deg,
        "T_SM_yaml_vs_b601model_maxabs": float(err_T_SM),
        "criterion": "pos < 1 mm AND ori < 0.1 deg",
        "pass": bool(ok),
    }
    if verbose:
        for k, v in report.items():
            print(f"  {k}: {v}")
    return report


if __name__ == "__main__":
    print("FK alignment self-test (independent visual chain vs B601Arm.fk):")
    rep = fk_alignment_selftest()
    raise SystemExit(0 if rep["pass"] else 1)
