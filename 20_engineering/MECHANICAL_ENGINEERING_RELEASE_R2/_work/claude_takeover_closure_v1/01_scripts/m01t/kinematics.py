"""Kinematics + pose authority for the takeover M01 machinery.

All internal transforms are 4x4 numpy arrays in MILLIMETRES, S frame.
Sources (hash-verified at load):
  - accepted B601 URDF (hardware truth, E_HW limits, metres/rad)
  - EXECUTION_MOUNT_BINDING_V1 canonical 12dp matrix (metres)
  - V9F centerline JSON (J4 cable-law constants, A0 q0, mm)
  - Link2 ledger J3 carriage law: dx3 = clip(32.5*(q3-(-1.57)), -55, +55) mm

Pose law (mirrors the pinned V9F evaluator semantics):
  host-follow(object on link h): M = MOUNT @ FK[h](q) @ inv(FK[h](0))
  J3 carriage parts:             M = MOUNT @ FK[link2](q) @ tr(dx3) @ inv(FK0[link2])
  travel fractions (J4 stages):  M = M3 @ tr(gain*dx4) with dx4 = -27.5*q4 mm
  FIXED_LINK3/4, FOLLOWER_LINK4: M3 / M4
  static S objects:              identity
  C capsules: per-section point laws (J4 exact, other sections rigid host-follow)
"""
import math
import xml.etree.ElementTree as ET

import numpy as np

from .common import abspath, jload, sha256_rel

# ------------------------------------------------------------------ URDF FK
URDF_REL = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"

Q_ORDER = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
E_HW_LIMITS = [(-2.8, 2.8), (-3.14, 0.0), (-3.14, 0.0),
               (-1.87, 1.57), (-1.57, 1.57), (-3.14, 3.14)]


def _rpy(roll, pitch, yaw):
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return np.array([
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ])


def _tr(xyz, R=None):
    T = np.eye(4)
    T[:3, :3] = np.eye(3) if R is None else R
    T[:3, 3] = np.asarray(xyz, float)
    return T


def _axis_rot(axis, angle):
    a = np.asarray(axis, float)
    n = float(np.linalg.norm(a))
    if n == 0.0:
        return np.eye(3)
    a = a / n
    x, y, z = a
    c, s = math.cos(angle), math.sin(angle)
    C = 1.0 - c
    return np.array([
        [x * x * C + c, x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, y * y * C + c, y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, z * z * C + c],
    ])


class ArmModel:
    """Accepted-URDF kinematics in millimetres (hash-verified)."""

    def __init__(self):
        actual = sha256_rel(URDF_REL)
        assert actual == URDF_SHA256, f"accepted URDF hash drift: {actual}"
        root = ET.parse(abspath(URDF_REL)).getroot()
        joints = {}
        child_of = {}
        for j in root.findall("joint"):
            name = j.get("name")
            org = j.find("origin")
            xyz = [float(v) for v in org.get("xyz").split()] if org is not None else [0, 0, 0]
            rpy = [float(v) for v in org.get("rpy").split()] if org is not None and org.get("rpy") else [0, 0, 0]
            ax = j.find("axis")
            axis = [float(v) for v in ax.get("xyz").split()] if ax is not None else [1, 0, 0]
            lim = j.find("limit")
            limits = (float(lim.get("lower")), float(lim.get("upper"))) if lim is not None else None
            parent = j.find("parent").get("link")
            child = j.find("child").get("link")
            joints[name] = {
                "type": j.get("type"), "xyz_m": xyz, "rpy": rpy, "axis": axis,
                "limits": limits, "parent": parent, "child": child,
            }
            child_of[child] = name
        self.joints = joints
        # verify E_HW limits byte-for-byte against the release authority
        for i, name in enumerate(Q_ORDER):
            lo, hi = joints[name]["limits"]
            elo, ehi = E_HW_LIMITS[i]
            assert (lo, hi) == (elo, ehi), f"{name} limit {(lo, hi)} != E_HW {(elo, ehi)}"
        # chain base_link -> gripper_right
        self.order = []
        link = "base_link"
        while link in child_of:
            jname = child_of[link]
            self.order.append(jname)
            link = joints[jname]["parent"]
        assert link == "base_link"

    def fk_m(self, q6, g1=0.0, g2=0.0):
        """FK in METRES, A0 (=base_link) frame. q6: 6 revolute rad; g1/g2: 2P m."""
        qmap = {name: float(v) for name, v in zip(Q_ORDER, q6)}
        qmap["gripper_joint1"] = float(g1)
        qmap["gripper_joint2"] = float(g2)
        T = {"base_link": np.eye(4)}
        # walk from base_link down the tree
        children = {}
        for name, j in self.joints.items():
            children.setdefault(j["parent"], []).append(name)
        stack = ["base_link"]
        while stack:
            parent = stack.pop()
            for jname in children.get(parent, []):
                j = self.joints[jname]
                To = _tr(j["xyz_m"], _rpy(*j["rpy"]))
                if j["type"] == "revolute":
                    M = _tr([0, 0, 0], _axis_rot(j["axis"], qmap.get(jname, 0.0)))
                elif j["type"] == "prismatic":
                    d = qmap.get(jname, 0.0)
                    a = np.asarray(j["axis"], float)
                    M = _tr((a * d).tolist())
                else:  # fixed
                    M = np.eye(4)
                T[j["child"]] = T[parent] @ To @ M
                stack.append(j["child"])
        return T


# ------------------------------------------------------------------ mount
_MOUNT_DOC = "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/EXECUTION_MOUNT_BINDING_V1.json"


def load_mount_mm():
    doc = jload(_MOUNT_DOC)
    rows = doc["binding"]["canonical_matrix_decimal_strings"]
    M = np.array([[float(v) for v in row] for row in rows], dtype=float)
    assert M.shape == (4, 4)
    M[:3, 3] *= 1000.0  # m -> mm, the only length conversion
    return M


MOUNT_MM = load_mount_mm()
ARM = ArmModel()
FK0_M = ARM.fk_m([0.0] * 6)
INV_FK0_MM = {}
for _k, _v in FK0_M.items():
    _mm = _v.copy()
    _mm[:3, 3] *= 1000.0
    INV_FK0_MM[_k] = np.linalg.inv(_mm)


def fk_mm(q6, g1=0.0, g2=0.0):
    """FK in MILLIMETRES, A0 frame."""
    T = ARM.fk_m(q6, g1, g2)
    out = {}
    for k, v in T.items():
        m = v.copy()
        m[:3, 3] *= 1000.0
        out[k] = m
    return out


# ------------------------------------------------------------------ J4 law constants
CENTERLINE_REL = "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_HARNESS_CENTERLINE_V9F.json"
J4_SEGMENT_ID = "SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER"
J4_CARRIER_GAIN_MM_PER_RAD = 27.5
J4_Q_MID_RAD = -0.15
J4_CARRIER_X_MID_MM = -205.0
J4_CARRIER_X_Q0_MM = J4_CARRIER_X_MID_MM - J4_CARRIER_GAIN_MM_PER_RAD * (0.0 - J4_Q_MID_RAD)
J4_Q_MIN_RAD, J4_Q_MAX_RAD = -1.87, 1.57
J4_ANNULUS_SEED_RAD = math.radians(20.0)
J3_CARRIAGE_PARTS = frozenset(
    ["RC-CAR-J3-CARRIAGE", "RC-CLP-J3-MOV"]
    + ["RC-CHN-E210-LINK-%02d" % i for i in range(6)])
J3_Q_DATUM = -1.57
J3_GAIN_MM_PER_RAD = 32.5
J3_TRAVEL_LIMIT_MM = 55.0


def _section_endpoints(sec):
    kind = sec["type"]
    if kind == "polyline":
        pts = [np.asarray(p, float) for p in sec["points"]]
        return pts[0], pts[-1]
    if kind == "arc":
        c = np.asarray(sec["center"], float)
        e1 = np.asarray(sec["basis_e1"], float)
        e2 = np.asarray(sec["basis_e2"], float)
        r = float(sec["radius_mm"])
        a0 = math.radians(float(sec["start_angle_deg"]))
        a1 = a0 + math.radians(float(sec["sweep_deg"]))
        return (c + r * (math.cos(a0) * e1 + math.sin(a0) * e2),
                c + r * (math.cos(a1) * e1 + math.sin(a1) * e2))
    if kind == "helix":
        o = np.asarray(sec["origin"], float)
        a = np.asarray(sec["axis"], float)
        e1 = np.asarray(sec["basis_e1"], float)
        e2 = np.asarray(sec["basis_e2"], float)
        r = float(sec["radius_mm"])
        p0 = math.radians(float(sec["start_angle_deg"]))
        p1 = p0 + math.radians(float(sec["sweep_deg"]))
        pitch = float(sec["pitch_mm_per_turn"])

        def pt(phi):
            return (o + r * (math.cos(phi) * e1 + math.sin(phi) * e2)
                    + a * (pitch * phi / (2 * math.pi)))
        return pt(p0), pt(p1)
    raise ValueError(f"unknown section type {kind}")


class J4Law:
    """Exact V9F J4 chainless trombone + external annular follower constants."""

    def __init__(self):
        center = jload(CENTERLINE_REL)
        assert center.get("schema") == "B601_ROUTE_C_HARNESS_CENTERLINE_V9F"
        seg = next(s for s in center["segments"] if s["id"] == J4_SEGMENT_ID)
        sections = seg["sections"]
        assert len(sections) == 7
        self.sections = sections
        self.F_A, self.P_A_Q0 = _section_endpoints(sections[1])
        self.P_B_Q0, self.F_B = _section_endpoints(sections[3])
        ann = sections[5]
        self.ANN_CENTER = np.asarray(ann["center"], float)
        self.ANN_AXIS = np.asarray(ann["normal"], float)
        self.ANN_E1 = np.asarray(ann["basis_e1"], float)
        self.ANN_E2 = np.asarray(ann["basis_e2"], float)
        self.ANN_RADIUS = float(ann["radius_mm"])
        self.ANN_ALPHA_FIXED = math.radians(float(ann["start_angle_deg"]))
        self.ANN_BETA_Q0 = abs(math.radians(float(ann["sweep_deg"])))
        usec = sections[2]
        self.U_CENTER_Q0 = np.asarray(usec["center"], float)
        self.U_E1 = np.asarray(usec["basis_e1"], float)
        self.U_RADIUS = float(usec["radius_mm"])

    def dx_mm(self, q4):
        # x_c(q4) = -205 - 27.5*(q4+0.15); dx = x_c(q4) - x_c(0) = -27.5*q4 exactly
        return -J4_CARRIER_GAIN_MM_PER_RAD * q4

    def beta(self, q4):
        return J4_ANNULUS_SEED_RAD + (J4_Q_MAX_RAD - q4)


J4 = J4Law()

# host plan per (segment_id, section_index): primary host for rigid follow
SECTION_HOST = {
    ("SEG-00_BUS_FEEDTHROUGH_AND_RISER", 0): "base_link",
    ("SEG-01_J1_ANNULAR_SERVICE_LOOP", 0): "base_link",
    ("SEG-01_J1_ANNULAR_SERVICE_LOOP", 1): "link1",
    ("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", 0): "link1",
    ("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", 1): "link2",
    ("SEG-03_J3_CARRIER_HYBRID_WRAP", 0): "link2",
    ("SEG-03_J3_CARRIER_HYBRID_WRAP", 1): "link2",
    ("SEG-03_J3_CARRIER_HYBRID_WRAP", 2): "link2",
    ("SEG-03_J3_CARRIER_HYBRID_WRAP", 3): "link3",
    (J4_SEGMENT_ID, 0): "link3",
    (J4_SEGMENT_ID, 1): "link3",
    (J4_SEGMENT_ID, 2): "link3",
    (J4_SEGMENT_ID, 3): "link3",
    (J4_SEGMENT_ID, 4): "link3",
    (J4_SEGMENT_ID, 5): "link3",
    (J4_SEGMENT_ID, 6): "link4",
    ("SEG-05_J5_WRIST_WRAP", 0): "link4",
    ("SEG-05_J5_WRIST_WRAP", 1): "link5",
    ("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", 0): "link5",
    ("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", 1): "link6",
    ("SEG-07A_WRIST_TAIL_DATA", 0): "link6",
    ("SEG-07B_WRIST_TAIL_POWER", 0): "link6",
}


def host_follow_mm(host, q6, g1=0.0, g2=0.0):
    T = fk_mm(q6, g1, g2)
    return MOUNT_MM @ T[host] @ INV_FK0_MM[host]


def dx3_mm(q3):
    return float(np.clip(J3_GAIN_MM_PER_RAD * (q3 - J3_Q_DATUM),
                         -J3_TRAVEL_LIMIT_MM, J3_TRAVEL_LIMIT_MM))


def tr_mm(dx, dy=0.0, dz=0.0):
    T = np.eye(4)
    T[0, 3], T[1, 3], T[2, 3] = dx, dy, dz
    return T


def pose_r_object_mm(part_name, host, motion_class, q6):
    """S-frame pose (mm) for an R object stored in A0 q0 coordinates."""
    q3, q4 = float(q6[2]), float(q6[3])
    if part_name in J3_CARRIAGE_PARTS:
        T = fk_mm(q6)
        return MOUNT_MM @ T[host] @ tr_mm(dx3_mm(q3)) @ INV_FK0_MM[host]
    if motion_class == "FIXED_LINK3":
        return host_follow_mm("link3", q6)
    if motion_class in ("ONE_THIRD_TRAVEL", "TWO_THIRDS_TRAVEL", "FULL_TRAVEL"):
        gain = {"ONE_THIRD_TRAVEL": 1.0 / 3.0, "TWO_THIRDS_TRAVEL": 2.0 / 3.0,
                "FULL_TRAVEL": 1.0}[motion_class]
        return host_follow_mm("link3", q6) @ tr_mm(gain * (-27.5 * q4))
    if motion_class in ("FIXED_LINK4", "FOLLOWER_LINK4"):
        return host_follow_mm("link4", q6)
    return host_follow_mm(host, q6)


def map_c_points_mm(seg_id, sec_idx, pts_A0, q6):
    """Map A0 q0 points of a C section to S (mm) at q6. Exact V9F point laws."""
    T = fk_mm(q6)
    M3 = MOUNT_MM @ T["link3"] @ INV_FK0_MM["link3"]
    q4 = float(q6[3])
    pts = np.asarray(pts_A0, float)
    if seg_id != J4_SEGMENT_ID:
        host = SECTION_HOST[(seg_id, sec_idx)]
        M = MOUNT_MM @ T[host] @ INV_FK0_MM[host]
        return pts @ M[:3, :3].T + M[:3, 3]
    if sec_idx in (0, 4):
        return pts @ M3[:3, :3].T + M3[:3, 3]
    if sec_idx == 6:
        M4 = MOUNT_MM @ T["link4"] @ INV_FK0_MM["link4"]
        return pts @ M4[:3, :3].T + M4[:3, 3]
    dx = -27.5 * q4
    if sec_idx == 2:
        p = pts.copy()
        p[:, 0] += dx
        return p @ M3[:3, :3].T + M3[:3, 3]
    if sec_idx == 1:
        d0 = J4.P_A_Q0 - J4.F_A
        u = ((pts - J4.F_A) @ d0) / max(float(d0 @ d0), 1e-12)
        pa = J4.U_CENTER_Q0 + np.array([dx, 0.0, 0.0]) + J4.U_RADIUS * J4.U_E1
        p = J4.F_A + u[:, None] * (pa - J4.F_A)
        return p @ M3[:3, :3].T + M3[:3, 3]
    if sec_idx == 3:
        d0 = J4.F_B - J4.P_B_Q0
        u = ((pts - J4.P_B_Q0) @ d0) / max(float(d0 @ d0), 1e-12)
        pb = J4.U_CENTER_Q0 + np.array([dx, 0.0, 0.0]) - J4.U_RADIUS * J4.U_E1
        p = pb + u[:, None] * (J4.F_B - pb)
        return p @ M3[:3, :3].T + M3[:3, 3]
    if sec_idx == 5:
        rel = pts - J4.ANN_CENTER
        alpha0 = np.arctan2(rel @ J4.ANN_E2, rel @ J4.ANN_E1)
        u = np.clip((J4.ANN_ALPHA_FIXED - alpha0) / J4.ANN_BETA_Q0, 0.0, 1.0)
        alpha = J4.ANN_ALPHA_FIXED - J4.beta(q4) * u
        p = (J4.ANN_CENTER
             + J4.ANN_RADIUS * (np.cos(alpha)[:, None] * J4.ANN_E1
                                + np.sin(alpha)[:, None] * J4.ANN_E2))
        return p @ M3[:3, :3].T + M3[:3, 3]
    raise ValueError(f"bad J4 section {sec_idx}")


def annulus_chord_inflation_mm(a_A0, b_A0, q4):
    """Conservative radius inflation for an annulus capsule mapped by the
    angular re-occupation law: true mapped body follows the circle while the
    certified capsule chords between mapped endpoints."""
    beta = J4.beta(q4)
    scale = beta / J4.ANN_BETA_Q0
    rel_a = np.asarray(a_A0, float) - J4.ANN_CENTER
    rel_b = np.asarray(b_A0, float) - J4.ANN_CENTER
    al_a = math.atan2(float(rel_a @ J4.ANN_E2), float(rel_a @ J4.ANN_E1))
    al_b = math.atan2(float(rel_b @ J4.ANN_E2), float(rel_b @ J4.ANN_E1))
    dth = abs(al_b - al_a) * scale
    return J4.ANN_RADIUS * (1.0 - math.cos(dth / 2.0))
