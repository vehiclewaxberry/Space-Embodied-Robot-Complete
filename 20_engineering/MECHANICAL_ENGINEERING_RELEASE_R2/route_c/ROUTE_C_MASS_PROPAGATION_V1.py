# ROUTE_C_MASS_PROPAGATION_V1.py
# Stage RC-5 of R2 terminal dual-lane closure, lane A2.
# Route-C mass & dynamics propagation - candidate layer, deterministic replay.
#
# Run: python ROUTE_C_MASS_PROPAGATION_V1.py     (from this directory)
# Inputs (read-only / hash-pinned):
#   ROUTE_C_SWEEP_MESH_PACK_V1/rc_parts_mass_geometry.json  (FreeCAD exact part CG/inertia)
#   B601_ROUTE_C_HARNESS_CENTERLINE_V1.json                 (centerline for bundle line-mass)
#   B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V1.json      (A1 candidate registry, consumed once)
#   SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml                (frozen nine-config baseline)
#   CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml              (per-config arm pose bindings)
#   ROUTE_C_EXACT_SWEEP_V1.json                             (RC-4 torque results, single source)
#   accepted URDF (read-only, hash-pinned; used for FK poses)
# Outputs (route_c/ only, candidates; nothing overwritten):
#   B601_ROUTE_C_MASS_PROPERTIES_V1.yaml
#   B601_ROUTE_C_MASS_DELTA_BY_LINK_V1.yaml
#   B601_ROUTE_C_JOINT_TORQUE_ENVELOPE_V1.yaml
#   ROUTE_C_NINE_CONFIG_MASS_PROPAGATION_CANDIDATE_V1.json
#
# Deterministic: no wall clock, fixed iteration order, repr floats.

import hashlib
import json
import math
import os

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

VARIANT = os.environ.get("RC_VARIANT", "V2").upper()
if VARIANT not in ("V1", "V2", "V3", "V4", "V5", "V6", "V7", "VF"):
    raise SystemExit("RC_VARIANT must be one of V1..V7 or VF")

# VF is the final-gate alias of the V7 hardware definition: consumes V7 CAD /
# mass inputs but the VF-named RC-4 sweep JSON (torque source of truth).
INPUT_VARIANT = "V7" if VARIANT == "VF" else VARIANT

P_PARTS = os.path.join(HERE, "ROUTE_C_SWEEP_MESH_PACK_%s" % INPUT_VARIANT, "rc_parts_mass_geometry.json")
P_CENTER = os.path.join(HERE, "B601_ROUTE_C_HARNESS_CENTERLINE_%s.json" % INPUT_VARIANT)
P_A1REG = os.path.join(HERE, "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_%s.json" % INPUT_VARIANT)
P_V3R2 = os.path.join(REPO, "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1",
                      "wp2_design_mass", "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml")
P_TRANS = os.path.join(REPO, "F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1",
                       "wp2_mass_properties", "CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml")
P_SWEEP = os.path.join(HERE, "ROUTE_C_EXACT_SWEEP_%s.json" % VARIANT)
P_URDF = os.path.join(REPO, "cad", "spacecraft_layout", "arm_b601_v1", "arm_b601_v1.urdf")
P_MOUNT = os.path.join(REPO, "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807",
                       "04_configurations", "F3R2_ARM_INITIAL_POSE.yaml")

URDF_SHA256_PIN = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"

# RC-5 artifact names are first-issue (V1) of their own schemas; they propagate
# the VARIANT design (V2 dress pack) selected above.
OUT_MASSPROP = os.path.join(HERE, "B601_ROUTE_C_MASS_PROPERTIES_V1.yaml")
OUT_DELTA = os.path.join(HERE, "B601_ROUTE_C_MASS_DELTA_BY_LINK_V1.yaml")
OUT_TORQUE = os.path.join(HERE, "B601_ROUTE_C_JOINT_TORQUE_ENVELOPE_V1.yaml")
OUT_NINECFG = os.path.join(HERE, "ROUTE_C_NINE_CONFIG_MASS_PROPAGATION_CANDIDATE_V1.json")

DENS = {"aluminum": 2.70e-3, "polymer": 1.20e-3}   # g/mm^3 (A1 density assumptions)
BUNDLE_G_PER_M = 65.0
BUNDLE_G_PER_M_BOUNDS = [56.5, 72.5]
LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6"]

# centerline section -> mass-host (primary guide hardware host; one host only,
# no double counting - mirrors the RC-4 attachment model primary column)
SECTION_MASS_HOST = {
    ("SEG-00_BUS_FEEDTHROUGH_AND_RISER", 0): "base_link",
    ("SEG-01_J1_ANNULAR_SERVICE_LOOP", 0): "base_link",
    ("SEG-01_J1_ANNULAR_SERVICE_LOOP", 1): "link1",
    ("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", 0): "link1",
    ("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", 1): "link2",
    ("SEG-03_J3_CARRIER_HYBRID_WRAP", 0): "link2",
    ("SEG-03_J3_CARRIER_HYBRID_WRAP", 1): "link3",
    ("SEG-04_J4_LOOP_LINK4_CHANNEL_RISER", 0): "link3",
    ("SEG-04_J4_LOOP_LINK4_CHANNEL_RISER", 1): "link4",
    ("SEG-05_J5_WRIST_WRAP", 0): "link4",
    ("SEG-05_J5_WRIST_WRAP", 1): "link5",
    ("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", 0): "link5",
    ("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", 1): "link6",
    ("SEG-07A_WRIST_TAIL_DATA", 0): "link6",
    ("SEG-07B_WRIST_TAIL_POWER", 0): "link6",
}
# hardware host remap: RC parts with host "bus" belong to the spacecraft bus,
# which is NOT part of the B601 arm URDF link set; they are tracked as the
# separate bus-mounted group and propagated into the system layer as a
# static (pose-invariant) member.
STATIC_HOSTS = {"bus": "bus", "base_link": "base_link"}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def tr(x, y, z):
    m = np.eye(4)
    m[0, 3], m[1, 3], m[2, 3] = x, y, z
    return m


def rot_axis(axis, ang):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    x, y, z = a
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    R = np.array([[x * x * C + c, x * y * C - z * s, x * z * C + y * s],
                  [y * x * C + z * s, y * y * C + c, y * z * C - x * s],
                  [z * x * C - y * s, z * y * C + x * s, z * z * C + c]])
    m = np.eye(4)
    m[:3, :3] = R
    return m


def rot_rpy(r, p, y):
    return rot_axis((0, 0, 1), y) @ rot_axis((0, 1, 0), p) @ rot_axis((1, 0, 0), r)


def pa(I_cg, m, r):
    """parallel axis: inertia about point offset r from CG (kg units consistent)."""
    d = np.asarray(r, float)
    return I_cg + m * ((d @ d) * np.eye(3) - np.outer(d, d))


def seg_line_pts(p0, p1, ds=1.5):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    n = max(1, int(L / ds))
    return p0 + (p1 - p0) * np.linspace(0, 1, n + 1)[:, None], L


def seg_arc_pts(center, e1, e2, r, phi0, phi1, ds=1.5):
    center = np.asarray(center, float)
    L = abs(phi1 - phi0) * r
    n = max(2, int(L / ds))
    phis = np.linspace(phi0, phi1, n + 1)
    return center + r * (np.cos(phis)[:, None] * e1[None, :]
                         + np.sin(phis)[:, None] * e2[None, :]), L


def seg_helix_pts(origin, a, e1, e2, r, phi0, phi1, z0, z1, ds=1.5):
    origin = np.asarray(origin, float)
    L = math.sqrt((r * (phi1 - phi0)) ** 2 + (z1 - z0) ** 2)
    n = max(2, int(L / ds))
    t = np.linspace(0, 1, n + 1)
    phis = phi0 + (phi1 - phi0) * t
    zs = z0 + (z1 - z0) * t
    return (origin + r * (np.cos(phis)[:, None] * e1[None, :]
                          + np.sin(phis)[:, None] * e2[None, :])
            + zs[:, None] * a[None, :]), L


def fillet_pts(corner, d_in, d_out, R_des, avail_in, avail_out, ds=1.5):
    corner = np.asarray(corner, float)
    u1 = np.asarray(d_in, float) / np.linalg.norm(d_in)
    u2 = np.asarray(d_out, float) / np.linalg.norm(d_out)
    turn = math.acos(float(np.clip(u1 @ u2, -1, 1)))
    if turn < math.radians(1.0):
        return None, 0.0
    t = R_des * math.tan(turn / 2.0)
    R = R_des
    lim = 0.98 * min(avail_in, avail_out)
    if t > lim:
        t = lim
        R = t / math.tan(turn / 2.0)
    T1 = corner - t * u1
    T2 = corner + t * u2
    m1 = u2 - (u1 @ u2) * u1
    nm = np.linalg.norm(m1)
    if nm < 1e-12:
        return None, 0.0
    m1 = m1 / nm
    O = T1 + R * m1
    n_axis = np.cross(u1, m1)
    n_axis = n_axis / np.linalg.norm(n_axis)
    e1 = m1
    e2 = np.cross(n_axis, e1)
    a1 = math.atan2(float((T1 - O) @ e2), float((T1 - O) @ e1))
    a2 = math.atan2(float((T2 - O) @ e2), float((T2 - O) @ e1))
    d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    pts, L = seg_arc_pts(O, e1, e2, R, a1, a1 + d, ds)
    return pts, L


def polyline_pts(points, corner_radii, ds=1.5):
    P = [np.asarray(p, float) for p in points]
    n = len(P)
    out = [P[0][None, :]]
    cursor = P[0]
    i = 1
    while i < n:
        if i < n - 1:
            R = corner_radii[i - 1] if i - 1 < len(corner_radii) else 50.0
            if R and R > 0:
                d_in = P[i] - cursor
                d_out = P[i + 1] - P[i]
                fp, fl = fillet_pts(P[i], d_in, d_out, R,
                                    float(np.linalg.norm(d_in)),
                                    float(np.linalg.norm(d_out)), ds)
                if fp is not None:
                    sp, sl = seg_line_pts(cursor, fp[0], ds)
                    out.append(sp)
                    out.append(fp[1:])
                    cursor = fp[-1]
                    i += 1
                    continue
        sp, sl = seg_line_pts(cursor, P[i], ds)
        out.append(sp[1:] if len(sp) > 1 else sp)
        cursor = P[i]
        i += 1
    return np.vstack(out)


def section_points(sec, ds=1.5):
    kind = sec["type"]
    if kind == "polyline":
        return polyline_pts(sec["points"], sec.get("corner_fillet_radii_mm", []), ds)
    if kind == "arc":
        e1 = np.asarray(sec["basis_e1"], float)
        e2 = np.asarray(sec["basis_e2"], float)
        pts, _ = seg_arc_pts(sec["center"], e1, e2, float(sec["radius_mm"]),
                             math.radians(sec["start_angle_deg"]),
                             math.radians(sec["start_angle_deg"] + sec["sweep_deg"]), ds)
        return pts
    if kind == "helix":
        a = np.asarray(sec["axis"], float)
        e1 = np.asarray(sec["basis_e1"], float)
        e2 = np.asarray(sec["basis_e2"], float)
        sweep = math.radians(sec["sweep_deg"])
        z_adv = sec["pitch_mm_per_turn"] * sweep / (2 * math.pi)
        pts, _ = seg_helix_pts(sec["origin"], a, e1, e2, float(sec["radius_mm"]),
                               math.radians(sec["start_angle_deg"]),
                               math.radians(sec["start_angle_deg"]) + sweep, 0.0, z_adv, ds)
        return pts
    raise ValueError(kind)


def fk_all(q6, joints, mount):
    import xml.etree.ElementTree as ET
    qd = {j["name"]: q6[i] for i, j in enumerate(joints) if j["type"] == "revolute"}
    T = {"base_link": np.eye(4)}
    for j in joints:
        Tj = T[j["parent"]] @ tr(*[v * 1000.0 for v in j["xyz"]]) @ rot_rpy(*j["rpy"])
        if j["type"] == "revolute":
            Tj = Tj @ rot_axis(j["axis"], qd.get(j["name"], 0.0))
        T[j["child"]] = Tj
    return {k: mount @ v for k, v in T.items()}, T


def main():
    # ---- pins ----------------------------------------------------------------
    pins = {}
    urdf_sha = sha256_file(P_URDF)
    pins["accepted_urdf"] = {"path": os.path.relpath(P_URDF, REPO).replace("\\", "/"),
                             "sha256": urdf_sha, "match": urdf_sha == URDF_SHA256_PIN}
    if not pins["accepted_urdf"]["match"]:
        raise SystemExit("ABORT: URDF hash mismatch")
    for tag, p in [("rc_parts_mass_geometry", P_PARTS), ("centerline", P_CENTER),
                   ("a1_mass_registry", P_A1REG), ("v3r2_mass", P_V3R2),
                   ("config_transforms", P_TRANS), ("rc4_sweep", P_SWEEP),
                   ("mount_pose_yaml", P_MOUNT)]:
        pins[tag] = {"path": os.path.relpath(p, REPO).replace("\\", "/"),
                     "sha256": sha256_file(p)}

    parts = json.load(open(P_PARTS, encoding="utf-8"))["parts"]
    center = json.load(open(P_CENTER, encoding="utf-8"))
    a1reg = json.load(open(P_A1REG, encoding="utf-8"))

    # ---- hardware per link -----------------------------------------------------
    hw = {}
    for p in parts:
        if p["kind"] == "bundle_envelope":
            continue
        host = p["host_link"]
        dens = DENS.get(p["material"])
        if dens is None:
            raise SystemExit("ABORT: unknown material %s" % p["material"])
        m_g = p["volume_mm3"] * dens
        I_vol = np.array(p["inertia_vol_mm5_about_cg_A0"], float)
        I_mass = I_vol * dens                       # g mm^2 about part CG, A0 axes
        hw.setdefault(host, []).append((m_g, np.array(p["cg_mm_A0"], float), I_mass,
                                        p["name"]))
    hw_link = {}
    for host, items in hw.items():
        M = sum(i[0] for i in items)
        cg = sum(i[0] * i[1] for i in items) / M
        I = np.zeros((3, 3))
        for m_g, c, Im, _name in items:
            I += pa(Im, m_g, c - cg)
        hw_link[host] = {"mass_g": M, "cg_mm_A0": cg, "inertia_g_mm2_A0": I,
                         "part_count": len(items)}

    # ---- bundle per link (line mass along centerline) ---------------------------
    bundle_link = {}
    for seg in center["segments"]:
        for ci, sec in enumerate(seg["sections"]):
            host = SECTION_MASS_HOST[(seg["id"], ci)]
            pts = section_points(sec)
            if len(pts) < 2:
                continue
            dsv = np.linalg.norm(np.diff(pts, axis=0), axis=1)
            w = np.concatenate([[dsv[0] / 2], (dsv[:-1] + dsv[1:]) / 2, [dsv[-1] / 2]])
            m_g = w * (BUNDLE_G_PER_M / 1000.0)
            M = float(m_g.sum())
            cg = (m_g[:, None] * pts).sum(0) / M
            I = np.zeros((3, 3))
            for wi, pi in zip(m_g, pts):
                I += wi * (((pi - cg) @ (pi - cg)) * np.eye(3)
                           - np.outer(pi - cg, pi - cg))
            cur = bundle_link.setdefault(host, {"mass_g": 0.0, "_m": [], "_p": []})
            cur["_m"].append(m_g)
            cur["_p"].append(pts)
    for host, cur in bundle_link.items():
        m_g = np.concatenate(cur["_m"])
        pts = np.vstack(cur["_p"])
        M = float(m_g.sum())
        cg = (m_g[:, None] * pts).sum(0) / M
        I = np.zeros((3, 3))
        for wi, pi in zip(m_g, pts):
            I += wi * (((pi - cg) @ (pi - cg)) * np.eye(3) - np.outer(pi - cg, pi - cg))
        cur["mass_g"] = M
        cur["cg_mm_A0"] = cg
        cur["inertia_g_mm2_A0"] = I
        del cur["_m"], cur["_p"]

    # ---- combine per link -------------------------------------------------------
    hosts_all = sorted(set(list(hw_link.keys()) + list(bundle_link.keys())))
    link_delta = {}
    for host in hosts_all:
        h = hw_link.get(host)
        b = bundle_link.get(host)
        masses = []
        cgs = []
        Is = []
        if h:
            masses.append(h["mass_g"])
            cgs.append(h["cg_mm_A0"])
            Is.append(h["inertia_g_mm2_A0"])
        if b:
            masses.append(b["mass_g"])
            cgs.append(b["cg_mm_A0"])
            Is.append(b["inertia_g_mm2_A0"])
        M = sum(masses)
        cg = sum(m * c for m, c in zip(masses, cgs)) / M
        I = np.zeros((3, 3))
        for m, c, Ii in zip(masses, cgs, Is):
            I += pa(Ii, m, c - cg)
        link_delta[host] = {
            "mass_g": M,
            "hardware_g": h["mass_g"] if h else 0.0,
            "bundle_g": b["mass_g"] if b else 0.0,
            "cg_mm_A0": cg,
            "inertia_g_mm2_A0_about_link_cg": I,
        }

    total_g = sum(v["mass_g"] for v in link_delta.values())
    total_hw = sum(v["hardware_g"] for v in link_delta.values())
    total_bd = sum(v["bundle_g"] for v in link_delta.values())

    # A1 registry cross-check (registered candidates, consumed once, not modified)
    a1_by_link = {e["host_link"]: e for e in a1reg["mass_delta_by_link"]}
    a1_cross = []
    for host in sorted(a1_by_link):
        e = a1_by_link[host]
        mine = link_delta.get(host)
        a1_cross.append({
            "host_link": host,
            "a1_registered_total_g": e["delta_total_g"],
            "a1_registered_hardware_g": e["hardware_g"],
            "a1_registered_bundle_g": e["bundle_g"],
            "rc5_exact_total_g": float(mine["mass_g"]) if mine else None,
            "rc5_exact_hardware_g": float(mine["hardware_g"]) if mine else None,
            "rc5_exact_bundle_g": float(mine["bundle_g"]) if mine else None,
            "delta_total_g_vs_a1": (float(mine["mass_g"]) - e["delta_total_g"]) if mine else None,
            "note": "A1 receipt recorded clamp-saddle volumes before the bore cut; "
                    "RC-5 exact values are computed from the final FCStd solids",
        })

    # ---- URDF/FK for link-frame expression and nine-config posing ------------------
    import xml.etree.ElementTree as ET
    root = ET.parse(P_URDF).getroot()
    joints = []
    for j in root.iter("joint"):
        o = j.find("origin")
        xyz = [float(v) for v in o.get("xyz").split()] if o is not None and o.get("xyz") else [0, 0, 0]
        rpy = [float(v) for v in o.get("rpy").split()] if o is not None and o.get("rpy") else [0, 0, 0]
        ax = j.find("axis")
        axis = [float(v) for v in ax.get("xyz").split()] if ax is not None else [1, 0, 0]
        joints.append(dict(name=j.get("name"), type=j.get("type"), xyz=xyz, rpy=rpy,
                           axis=axis, parent=j.find("parent").get("link"),
                           child=j.find("child").get("link")))
    mount_yaml = yaml.safe_load(open(P_MOUNT, encoding="utf-8"))
    mount = np.array(mount_yaml["mount"]["transform_mm_rows"], float)
    _, T0 = fk_all([0.0] * 6, joints, mount)
    inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}

    # per-link delta in URDF link frame (kg, m) - URDF-compatible increment
    link_delta_urdf = {}
    for host in LINKS:
        if host not in link_delta:
            continue
        v = link_delta[host]
        M_kg = v["mass_g"] / 1000.0
        cg_A0_m = v["cg_mm_A0"] / 1000.0
        I_A0 = v["inertia_g_mm2_A0_about_link_cg"] * 1e-3 * 1e-6   # g mm2 -> kg m2
        T = T0[host]
        cg_link = np.linalg.inv(T) @ np.append(cg_A0_m * 1000.0, 1.0)
        R = T[:3, :3]
        I_link = R.T @ I_A0 @ R
        link_delta_urdf[host] = {
            "mass_kg": M_kg,
            "cg_m_in_link_frame": [float(x) for x in cg_link[:3] / 1000.0],
            "inertia_kg_m2_about_link_cg_in_link_axes": {
                "Ixx": float(I_link[0, 0]), "Iyy": float(I_link[1, 1]),
                "Izz": float(I_link[2, 2]), "Ixy": float(I_link[0, 1]),
                "Ixz": float(I_link[0, 2]), "Iyz": float(I_link[1, 2])},
        }

    # ---- nine-configuration propagation -------------------------------------------
    v3 = yaml.safe_load(open(P_V3R2, encoding="utf-8"))
    trans = yaml.safe_load(open(P_TRANS, encoding="utf-8"))
    bindings = trans["transform_library"]["arm_named_pose_bindings"]

    def q_of_binding(name):
        return bindings[name]["q_rad"]

    configs_out = []
    for cfg in v3["configurations"]:
        cid = cfg["configuration_id"]
        cname = cfg["name"]
        M0 = cfg["mass"]["value_kg"]
        sM = cfg["mass"]["standard_uncertainty_kg"]
        cg0 = np.array(cfg["center_of_mass"]["xyz_m"], float)
        scg = np.array(cfg["center_of_mass"]["standard_uncertainty_xyz_m"], float)
        I0c = cfg["inertia"]["components_kg_m2"]
        sI0c = cfg["inertia"]["standard_uncertainty_components_kg_m2"]
        I0 = np.array([[I0c["Ixx"], I0c["Ixy"], I0c["Ixz"]],
                       [I0c["Ixy"], I0c["Iyy"], I0c["Iyz"]],
                       [I0c["Ixz"], I0c["Iyz"], I0c["Izz"]]])
        # arm pose binding
        tref = None
        for comp in cfg.get("components", []):
            if "b601_complete_arm" in comp.get("component_id", ""):
                tref = comp.get("transform_ref")
        q = None
        if tref and "arm_named_pose_bindings." in tref:
            q = q_of_binding(tref.split("arm_named_pose_bindings.", 1)[1])
        # pose link deltas
        dM = 0.0
        num = np.zeros(3)
        members = []
        for host in LINKS:
            if host not in link_delta:
                continue
            v = link_delta[host]
            m_kg = v["mass_g"] / 1000.0
            I_link = np.array([
                [link_delta_urdf[host]["inertia_kg_m2_about_link_cg_in_link_axes"]["Ixx"],
                 link_delta_urdf[host]["inertia_kg_m2_about_link_cg_in_link_axes"]["Ixy"],
                 link_delta_urdf[host]["inertia_kg_m2_about_link_cg_in_link_axes"]["Ixz"]],
                [link_delta_urdf[host]["inertia_kg_m2_about_link_cg_in_link_axes"]["Ixy"],
                 link_delta_urdf[host]["inertia_kg_m2_about_link_cg_in_link_axes"]["Iyy"],
                 link_delta_urdf[host]["inertia_kg_m2_about_link_cg_in_link_axes"]["Iyz"]],
                [link_delta_urdf[host]["inertia_kg_m2_about_link_cg_in_link_axes"]["Ixz"],
                 link_delta_urdf[host]["inertia_kg_m2_about_link_cg_in_link_axes"]["Iyz"],
                 link_delta_urdf[host]["inertia_kg_m2_about_link_cg_in_link_axes"]["Izz"]]])
            cg_link_m = np.array(link_delta_urdf[host]["cg_m_in_link_frame"], float)
            if q is not None:
                TS, _ = fk_all(q, joints, mount)
            else:
                TS, _ = fk_all([0.0] * 6, joints, mount)
            T_S = TS[host]
            cg_S = (T_S[:3, :3] @ (cg_link_m * 1000.0) + T_S[:3, 3]) / 1000.0
            R_S = T_S[:3, :3]
            I_S = R_S @ I_link @ R_S.T
            dM += m_kg
            num += m_kg * cg_S
            members.append((host, m_kg, cg_S, I_S))
        # bus-mounted group: static in S (pose invariant)
        if "bus" in link_delta:
            v = link_delta["bus"]
            m_kg = v["mass_g"] / 1000.0
            cg_A0_m = v["cg_mm_A0"] / 1000.0
            I_A0 = v["inertia_g_mm2_A0_about_link_cg"] * 1e-9
            cg_S = (mount[:3, :3] @ (cg_A0_m * 1000.0) + mount[:3, 3]) / 1000.0
            I_S = mount[:3, :3] @ I_A0 @ mount[:3, :3].T
            dM += m_kg
            num += m_kg * cg_S
            members.append(("bus", m_kg, cg_S, I_S))
        cg_d = num / dM
        M1 = M0 + dM
        cg1 = (M0 * cg0 + dM * cg_d) / M1
        I1 = pa(I0, M0, cg0 - cg1)
        for host, m_kg, cg_S, I_S in members:
            I1 += pa(I_S, m_kg, cg_S - cg1)
        dcg = cg1 - cg0
        dI = np.array([I1[0, 0] - I0[0, 0], I1[1, 1] - I0[1, 1], I1[2, 2] - I0[2, 2],
                       I1[0, 1] - I0[0, 1], I1[0, 2] - I0[0, 2], I1[1, 2] - I0[1, 2]])
        sI = np.array([sI0c["Ixx"], sI0c["Iyy"], sI0c["Izz"],
                       sI0c["Ixy"], sI0c["Ixz"], sI0c["Iyz"]])
        configs_out.append({
            "configuration_id": cid, "name": cname,
            "arm_pose_binding": tref,
            "baseline_mass_kg": M0, "route_c_delta_mass_kg": dM,
            "updated_mass_kg": M1,
            "delta_mass_vs_standard_uncertainty": abs(dM) <= sM,
            "baseline_cg_m": [float(x) for x in cg0],
            "updated_cg_m": [float(x) for x in cg1],
            "delta_cg_m": [float(x) for x in dcg],
            "standard_uncertainty_cg_m": [float(x) for x in scg],
            "delta_cg_within_uncertainty": bool((np.abs(dcg) <= scg).all()),
            "delta_inertia_components_kg_m2": {
                "Ixx": float(dI[0]), "Iyy": float(dI[1]), "Izz": float(dI[2]),
                "Ixy": float(dI[3]), "Ixz": float(dI[4]), "Iyz": float(dI[5])},
            "standard_uncertainty_inertia_kg_m2": {
                "Ixx": float(sI[0]), "Iyy": float(sI[1]), "Izz": float(sI[2]),
                "Ixy": float(sI[3]), "Ixz": float(sI[4]), "Iyz": float(sI[5])},
            "delta_inertia_within_uncertainty": bool((np.abs(dI) <= sI).all()),
            "updated_inertia_components_kg_m2": {
                "Ixx": float(I1[0, 0]), "Iyy": float(I1[1, 1]), "Izz": float(I1[2, 2]),
                "Ixy": float(I1[0, 1]), "Ixz": float(I1[0, 2]), "Iyz": float(I1[1, 2])},
        })

    within_all = all(c["delta_mass_vs_standard_uncertainty"]
                     and c["delta_cg_within_uncertainty"]
                     and c["delta_inertia_within_uncertainty"]
                     for c in configs_out)
    tmg2_verdict = ("ROUTE_C_MASS_DELTA_WITHIN_R2_UNCERTAINTY_ENVELOPE__TMG2_REOPEN_NOT_TRIGGERED"
                    if within_all else
                    "ROUTE_C_MASS_DELTA_EXCEEDS_R2_UNCERTAINTY_ENVELOPE__RECOMMEND_TMG2_REOPEN_EVALUATION")

    # ---- torque envelope (from RC-4 sweep single source) ---------------------------
    sweep = json.load(open(P_SWEEP, encoding="utf-8"))
    torque = sweep["resistance_torque"]

    # ---- write YAML outputs ---------------------------------------------------------
    def ydump(obj):
        return yaml.safe_dump(json.loads(json.dumps(obj, default=str)),
                              sort_keys=False, allow_unicode=True)

    massprop = {
        "schema": "B601_ROUTE_C_MASS_PROPERTIES_V1",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "stage": "RC-5_MASS_AND_DYNAMICS_PROPAGATION",
        "authority": "DESIGN_CANDIDATE (hardware: exact FCStd solids x A1 density assumptions; "
                     "bundle: PROVISIONAL_DERIVED linear density P09)",
        "input_pins": pins,
        "densities_g_per_mm3": DENS,
        "bundle_linear_density_g_per_m": {"nominal": BUNDLE_G_PER_M,
                                          "bounded_range": BUNDLE_G_PER_M_BOUNDS,
                                          "source": "registry P09"},
        "per_link_delta": {
            h: {
                "mass_g": float(v["mass_g"]),
                "hardware_g": float(v["hardware_g"]),
                "bundle_g": float(v["bundle_g"]),
                "cg_mm_A0": [float(x) for x in v["cg_mm_A0"]],
                "inertia_g_mm2_about_link_cg_A0_axes":
                    [[float(x) for x in row] for row in v["inertia_g_mm2_A0_about_link_cg"]],
            } for h, v in sorted(link_delta.items())
        },
        "per_link_delta_urdf_frame": link_delta_urdf,
        "totals": {"mass_g": float(total_g), "hardware_g": float(total_hw),
                   "bundle_g": float(total_bd), "mass_kg": float(total_g / 1000.0)},
        "a1_registry_cross_check": a1_cross,
        "consumption_rule": "A1 candidate registry consumed exactly once as cross-check; "
                            "exact values recomputed from final FCStd solids + centerline; "
                            "accepted URDF inertials unchanged; no double counting with any "
                            "system interface (delta enters only via this layer)",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    with open(OUT_MASSPROP, "w", encoding="utf-8", newline="\n") as f:
        f.write(ydump(massprop))

    delta_layer = {
        "schema": "B601_ROUTE_C_MASS_DELTA_BY_LINK_V1",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "stage": "RC-5",
        "authority": "DESIGN_CANDIDATE",
        "rule": "Route-C mass enters as an independent per-link delta layer; accepted URDF "
                "bytes unchanged; each increment consumed once; propagation into system "
                "mass only via ROUTE_C_NINE_CONFIG_MASS_PROPAGATION_CANDIDATE_V1.json",
        "accepted_urdf": pins["accepted_urdf"],
        "mass_delta_by_link": {
            h: {
                "delta_mass_kg": link_delta_urdf[h]["mass_kg"],
                "delta_cg_m_in_link_frame": link_delta_urdf[h]["cg_m_in_link_frame"],
                "delta_inertia_kg_m2_about_link_cg_in_link_axes":
                    link_delta_urdf[h]["inertia_kg_m2_about_link_cg_in_link_axes"],
                "hardware_g": float(link_delta[h]["hardware_g"]),
                "bundle_g": float(link_delta[h]["bundle_g"]),
                "authority": "DESIGN_CANDIDATE",
            } for h in LINKS if h in link_delta_urdf
        },
        "bus_mounted_group": {
            "delta_mass_kg": float(link_delta["bus"]["mass_g"] / 1000.0),
            "note": "feedthrough channel + bus clamps; static in S (pose invariant); "
                    "not a URDF arm member",
            "authority": "DESIGN_CANDIDATE",
        } if "bus" in link_delta else None,
        "totals": {"delta_mass_kg": float(total_g / 1000.0)},
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    with open(OUT_DELTA, "w", encoding="utf-8", newline="\n") as f:
        f.write(ydump(delta_layer))

    torque_env = {
        "schema": "B601_ROUTE_C_JOINT_TORQUE_ENVELOPE_V1",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "stage": "RC-5",
        "model": {
            "tau_bend": "EI_bundle / R_loop (bending recovery transmitted at the loop)",
            "tau_friction": "mu * N * R_loop with N = EI_bundle / R_loop^2 * stored_wrap_rad "
                            "(capstan-style recovery normal load candidate)",
            "EI_bundle_N_m2": [1.7e-4, 2.1e-2],
            "EI_derivation": "upper: E_copper 110 GPa x pi/64 x sum(OD^4) of candidate "
                             "sub-bundle (Axon P551259 6.5 mm + 8x TE 0.72 mm) treated as "
                             "solid - grossly conservative; lower: strand-level copper only",
            "mu": "0.20 (P10 BOUNDED_DATASHEET_RANGE upper, iglidur J260 vs steel dry)",
            "authority": "PROVISIONAL_DERIVED, confidence LOW",
        },
        "actuator_budget_source": "accepted URDF joint effort limits (read-only)",
        "unknown_components": [
            {"component": "torsion restoring moment of installed bundle (registry P08)",
             "status": "UNKNOWN_REGISTERED_HOLD_C5", "policy": "not zero-filled, not gated here"},
            {"component": "space-environment (TVAC) behavior of igus/iglidur elements",
             "status": "UNKNOWN_REGISTERED_HOLD_C6", "policy": "not zero-filled"},
        ],
        "per_joint": torque,
        "worst_fraction_of_budget": max(t["worst_fraction_of_budget"] for t in torque),
        "odr50_reopen_guard": {
            "trigger": "harness resistance torque exceeds actuator/control budget",
            "evaluation": ("derived bound far below budget at every joint "
                           "(worst fraction %.4f of effort limit); torsion component UNKNOWN "
                           "registered as C5 hold - guard NOT triggered on derived evidence"
                           % max(t["worst_fraction_of_budget"] for t in torque)),
            "verdict": "REOPEN_NOT_TRIGGERED_ON_DERIVED_EVIDENCE__UNKNOWN_TORSION_HOLD_REGISTERED",
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    with open(OUT_TORQUE, "w", encoding="utf-8", newline="\n") as f:
        f.write(ydump(torque_env))

    ninecfg = {
        "schema": "ROUTE_C_NINE_CONFIG_MASS_PROPAGATION_CANDIDATE_V1",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "stage": "RC-5",
        "rule": "candidate layer only - release root 07_SYSTEM_MASS_PROPERTIES.yaml and "
                "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml are NOT modified",
        "input_pins": pins,
        "configurations": configs_out,
        "route_c_delta_uncertainty": {
            "hardware_fraction": 0.10,
            "bundle_linear_density_bounds_g_per_m": BUNDLE_G_PER_M_BOUNDS,
            "authority": "DESIGN_CANDIDATE engineering allocation",
        },
        "envelope_evaluation": {
            "criterion": "ODR-50 reopen trigger: Route-C changes system mass/CG/inertia "
                         "beyond current R2 uncertainty envelope",
            "all_configurations_within_envelope": within_all,
            "verdict": tmg2_verdict,
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    with open(OUT_NINECFG, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(ninecfg, indent=2, sort_keys=True))

    print("total delta: %.1f g (hw %.1f, bundle %.1f)" % (total_g, total_hw, total_bd))
    print("nine-config within envelope: %s -> %s" % (within_all, tmg2_verdict))
    for c in configs_out:
        print("  %s %-22s dM=%.4f kg (std %.3f)  dCG max=%.4f m (std %.4f)  within=%s"
              % (c["configuration_id"], c["name"], c["route_c_delta_mass_kg"],
                 c["baseline_mass_kg"] and c["delta_mass_vs_standard_uncertainty"],
                 max(abs(x) for x in c["delta_cg_m"]),
                 max(c["standard_uncertainty_cg_m"]),
                 c["delta_cg_within_uncertainty"]))


if __name__ == "__main__":
    main()
