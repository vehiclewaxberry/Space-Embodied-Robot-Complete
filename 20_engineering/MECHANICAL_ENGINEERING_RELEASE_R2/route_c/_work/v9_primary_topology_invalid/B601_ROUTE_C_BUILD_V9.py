# B601 Route-C Guided Dress Pack V9 primary architecture - headless FreeCAD build script.
# Stage RC-3 of R2 terminal dual-lane closure, lane A1 (Route-C task-level guided harness).
# Authority: ODR-42 / ODR-52 / ODR-53 / ODR-54 / ODR-58. All geometry is DESIGN_CANDIDATE.
# Architecture: SEGMENTED_CONSTRAINED_MOVING_CARRIER + LOW_PROFILE_DUAL_PLANE_SADDLE.
# Run: FreeCADCmd.exe B601_ROUTE_C_BUILD_V9.py
# Outputs (same directory): FCStd, STEP, centerline JSON, clamp register CSV,
# mass-delta candidates JSON, build receipt JSON.

import os
import json
import math
import hashlib

import FreeCAD as App
import Part

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_MANIFEST = os.path.join(SCRIPT_DIR, "ROUTE_C_V9_INPUT_MANIFEST.json")
INPUT_MANIFEST_SHA256 = "24B9E2BFB21930E44945C0BA979351CFB9EB23358755D1018FCC4602CDED7E7C"
OUT_FCSTD = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V9.FCStd")
OUT_STEP = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V9.step")
OUT_CENTERLINE = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_HARNESS_CENTERLINE_V9.json")
OUT_CLAMPS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V9.csv")
OUT_MASS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V9.json")
OUT_RECEIPT = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_BUILD_RECEIPT_V9.json")

REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
MESH_DIR = os.path.join(REPO_ROOT, "cad", "spacecraft_layout", "arm_b601_v1", "meshes_b601_gripper")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


_manifest_sha = sha256_file(INPUT_MANIFEST)
if _manifest_sha != INPUT_MANIFEST_SHA256:
    raise RuntimeError("fail-closed V9 input manifest hash mismatch: %s" % _manifest_sha)

P = {
    "bundle_od_mm": 9.0,
    "bundle_r": 4.5,
    "bundle_od_upper_mm": 10.0,
    "bundle_r_upper": 5.0,
    "clamp_bore_r_mm": 6.0,
    "clamp_install_allow_mm": 0.5,
    "guide_outer_r_mm": 9.5,
    "guide_support_bore_r_mm": 11.0,
    "channel_clear_mm": 12.0,
    "r_path_min": 54.0,
    "carrier_travel_mm": 110.0,
    "j4_carrier_hard_stop_travel_mm": 100.0,
    "j4_carrier_center_x_mid_mm": 160.0,
    "j4_carrier_gain_mm_per_rad": 27.5,
    "j4_q_mid_rad": -0.15,
    "carrier_pitch_mm": 20.0,
    "carrier_cross_mm": [10.0, 16.0],
    "linear_density_g_m": 65.0,
    "rho_alu_g_mm3": 2.70e-3,
    "rho_poly_g_mm3": 1.20e-3,
    "joint_ranges_rad": {"J1": 5.6, "J2": 3.14, "J3": 3.14, "J4": 3.44, "J5": 3.14, "J6": 6.28},
}
DENS = {"aluminum": P["rho_alu_g_mm3"], "polymer": P["rho_poly_g_mm3"]}

# ---------------- vector helpers (tuples, mm) ----------------
def v_add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def v_sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def v_mul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def v_dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def v_cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def v_len(a): return math.sqrt(v_dot(a, a))
def v_norm(a):
    l = v_len(a)
    if l < 1e-12:
        raise ValueError("zero-length direction")
    return (a[0]/l, a[1]/l, a[2]/l)
def v_dist(a, b): return v_len(v_sub(a, b))
def fc_vec(t): return App.Vector(t[0], t[1], t[2])

# ---------------- URDF FK at q=0 (read-only reference) ----------------
def urdf_placements():
    def pl(t, rpy_deg):
        return App.Placement(fc_vec(t), App.Rotation(rpy_deg[2], rpy_deg[1], rpy_deg[0]))
    frames = {}
    frames["base_link"] = App.Placement()
    j1 = pl((-0.08416, 0.0, 84.65), (0, 0, 0))
    j2 = pl((20.084, 31.625, 55.55), (-90.0, 0, 0))
    j3 = pl((-264.0, 0.0, 0.0), (0, 0, 0))
    j4 = pl((242.6, -54.0, -1.625), (0, 0, 0))
    j5 = pl((78.308, -37.5, -30.0), (-90.0, 0, 0))
    j6 = pl((23.692, 0.0, 40.0), (0, 90.0, 0))
    jg = pl((0.0, 0.0, 159.71), (0, -90.0, 0))
    frames["link1"] = frames["base_link"].multiply(j1)
    frames["link2"] = frames["link1"].multiply(j2)
    frames["link3"] = frames["link2"].multiply(j3)
    frames["link4"] = frames["link3"].multiply(j4)
    frames["link5"] = frames["link4"].multiply(j5)
    frames["link6"] = frames["link5"].multiply(j6)
    frames["gripper_link"] = frames["link6"].multiply(jg)
    return frames

FRAMES = urdf_placements()

def world_to_host(pt_world, host):
    inv = FRAMES[host].inverse()
    v = inv.multVec(fc_vec(pt_world))
    return (v.x, v.y, v.z)

def world_dir_to_host(dir_world, host):
    inv_r = FRAMES[host].Rotation.inverted()
    v = inv_r.multVec(fc_vec(dir_world))
    return v_norm((v.x, v.y, v.z))

# ---------------- geometry helpers ----------------
def circle_point(center, e1, e2, R, ang_deg):
    a = math.radians(ang_deg)
    return v_add(center, v_add(v_mul(e1, R*math.cos(a)), v_mul(e2, R*math.sin(a))))

def tangent_dir_circle(e1, e2, ang_deg, sense):
    a = math.radians(ang_deg)
    if sense > 0:
        return v_norm(v_add(v_mul(e1, -math.sin(a)), v_mul(e2, math.cos(a))))
    return v_norm(v_add(v_mul(e1, math.sin(a)), v_mul(e2, -math.cos(a))))

def tangent_point_from_external(center2d, R, p2d, sense):
    """2D tangent from external point to circle; returns (tangent_point2d, ang_deg)
    whose sense-tangent points along (T1 - p)."""
    dx = p2d[0] - center2d[0]
    dy = p2d[1] - center2d[1]
    d = math.hypot(dx, dy)
    if d <= R:
        raise ValueError("external point inside circle: d=%.2f R=%.2f" % (d, R))
    base_ang = math.degrees(math.atan2(dy, dx))
    alpha = math.degrees(math.acos(R / d))
    t_leg = math.sqrt(d*d - R*R)
    cands = []
    for sign in (+1, -1):
        ang = base_ang + sign * alpha
        tx = center2d[0] + R * math.cos(math.radians(ang))
        ty = center2d[1] + R * math.sin(math.radians(ang))
        if sense > 0:
            tdir = (-math.sin(math.radians(ang)), math.cos(math.radians(ang)))
        else:
            tdir = (math.sin(math.radians(ang)), -math.cos(math.radians(ang)))
        approach = ((tx - p2d[0]) / t_leg, (ty - p2d[1]) / t_leg)
        dot = tdir[0]*approach[0] + tdir[1]*approach[1]
        cands.append((dot, (tx, ty), ang))
    cands.sort(key=lambda c: -c[0])
    best = cands[0]
    if best[0] < 0.99:
        raise ValueError("no tangent point with matching sense (best dot %.4f)" % best[0])
    return best[1], best[2]

def helix_tangent(axis, e1, e2, R, pitch, ang_deg, sense):
    a = math.radians(ang_deg)
    axial = pitch / (2.0*math.pi) * sense
    tang = v_add(v_mul(axis, axial),
                 v_mul(tangent_dir_circle(e1, e2, ang_deg, sense), R))
    return v_norm(tang)

# ---------------- section builders ----------------
class SegReport:
    def __init__(self, seg_id):
        self.seg_id = seg_id
        self.corners = []
        self.violations = []
        self.adjustments = []
        self.junctions = []
        self.min_bend_radius = 1e9

def fillet_edges(p0, p1, p2, R, rep, corner_idx):
    """Return (edges, t2) for a fillet of radius R at corner p1.
    If the tangent length exceeds the adjacent legs, the fillet radius is
    clamped locally (recorded as violation) to avoid reversed edges."""
    u = v_norm(v_sub(p1, p0))
    v = v_norm(v_sub(p2, p1))
    cos_t = max(-1.0, min(1.0, v_dot(u, v)))
    theta = math.degrees(math.acos(cos_t))
    l1 = v_dist(p0, p1)
    l2 = v_dist(p1, p2)
    if theta < 1.0:
        return None, None
    if theta > 179.0:
        rep.violations.append("%s corner %d: reversal angle %.1f deg" % (rep.seg_id, corner_idx, theta))
        return None, None
    tan_half = math.tan(math.radians(theta/2.0))
    T = R * tan_half
    R_eff = R
    if T > 0.98*min(l1, l2):
        T = 0.98*min(l1, l2)
        R_eff = T / tan_half
        msg = ("%s corner %d: fillet radius adjusted %.2f -> %.2f mm "
               "(theta %.1f deg, legs %.2f/%.2f)"
               % (rep.seg_id, corner_idx, R, R_eff, theta, l1, l2))
        if R_eff < P["r_path_min"] - 1e-9:
            rep.violations.append(msg)
        else:
            rep.adjustments.append(msg + "; remains above controlled minimum")
    rep.corners.append({"corner": corner_idx, "theta_deg": round(theta, 2), "R": round(R_eff, 2),
                        "tangent_len": round(T, 2), "leg_in": round(l1, 2), "leg_out": round(l2, 2)})
    if R_eff < rep.min_bend_radius:
        rep.min_bend_radius = R_eff
    if R_eff < P["r_path_min"] - 1e-9:
        rep.violations.append("%s corner %d: effective fillet R %.2f < r_path_min %.2f"
                              % (rep.seg_id, corner_idx, R_eff, P["r_path_min"]))
    t1 = v_sub(p1, v_mul(u, T))
    t2 = v_add(p1, v_mul(v, T))
    w = v_norm(v_cross(u, v))
    n1 = v_norm(v_cross(w, u))
    center = v_add(t1, v_mul(n1, R_eff))
    mid = v_add(center, v_mul(v_norm(v_sub(p1, center)), R_eff))
    edges = []
    if v_dist(p0, t1) > 1e-6:
        edges.append(Part.makeLine(fc_vec(p0), fc_vec(t1)))
    edges.append(Part.Arc(fc_vec(t1), fc_vec(mid), fc_vec(t2)).toShape())
    return edges, t2

def canonical_fillet_section(p0, p1, p2, R):
    """Return an explicit canonical arc section and its tangent endpoints.

    This is used at a real kinematic host boundary: the cable geometry remains
    identical to the rounded polyline, while the post-fillet run can be bound
    to one physical host instead of inheriting an unbounded alternate host.
    """
    u = v_norm(v_sub(p1, p0))
    v = v_norm(v_sub(p2, p1))
    cos_t = max(-1.0, min(1.0, v_dot(u, v)))
    theta = math.acos(cos_t)
    if theta < math.radians(1.0) or theta > math.radians(179.0):
        raise ValueError("canonical fillet requires a bounded non-degenerate corner")
    l1 = v_dist(p0, p1)
    l2 = v_dist(p1, p2)
    tan_half = math.tan(theta/2.0)
    tangent_len = R * tan_half
    r_eff = R
    if tangent_len > 0.98*min(l1, l2):
        tangent_len = 0.98*min(l1, l2)
        r_eff = tangent_len/tan_half
    t1 = v_sub(p1, v_mul(u, tangent_len))
    t2 = v_add(p1, v_mul(v, tangent_len))
    normal = v_norm(v_cross(u, v))
    n1 = v_norm(v_cross(normal, u))
    center = v_add(t1, v_mul(n1, r_eff))
    radial_start = v_mul(n1, -1.0)
    section = ("arc", (center, normal, radial_start, u, r_eff,
                       0.0, math.degrees(theta)))
    return section, t1, t2

def poly_edges(points, corner_radii, rep):
    n = len(points)
    edges = []
    cursor = points[0]
    i = 1
    while i < n:
        if i < n-1:
            R = corner_radii[i-1] if i-1 < len(corner_radii) else P["r_path_min"]
            if R and R > 0:
                fe, t2 = fillet_edges(cursor, points[i], points[i+1], R, rep, i)
                if fe is not None:
                    edges.extend(fe)
                    cursor = t2
                    i += 1
                    continue
        edges.append(Part.makeLine(fc_vec(cursor), fc_vec(points[i])))
        cursor = points[i]
        i += 1
    return edges

def arc_edge(center, normal, e1, e2, R, start_deg, sweep_deg, rep):
    p0 = circle_point(center, e1, e2, R, start_deg)
    pm = circle_point(center, e1, e2, R, start_deg + sweep_deg/2.0)
    p1 = circle_point(center, e1, e2, R, start_deg + sweep_deg)
    if R < rep.min_bend_radius:
        rep.min_bend_radius = R
    return Part.Arc(fc_vec(p0), fc_vec(pm), fc_vec(p1)).toShape()

def helix_edge(origin, axis, e1, e2, R, pitch, start_deg, sweep_deg, rep):
    nstp = max(8, int(abs(sweep_deg)/10.0))
    pts = []
    for k in range(nstp+1):
        ang = start_deg + sweep_deg*k/nstp
        p = circle_point(origin, e1, e2, R, ang)
        along = pitch * math.radians(ang - start_deg) / (2.0*math.pi)
        p = v_add(p, v_mul(axis, along))
        pts.append(fc_vec(p))
    bs = Part.BSplineCurve()
    bs.interpolate(pts)
    if R < rep.min_bend_radius:
        rep.min_bend_radius = R
    return bs.toShape()

def build_segment_wire(sections, rep):
    edges = []
    for sec in sections:
        kind = sec[0]
        if kind == "poly":
            edges.extend(poly_edges(sec[1], sec[2], rep))
        elif kind == "arc":
            edges.append(arc_edge(*sec[1], rep))
        elif kind == "helix":
            edges.append(helix_edge(*sec[1], rep))
        else:
            raise ValueError("unknown section kind %s" % kind)
    for k in range(len(edges)-1):
        e0 = edges[k]
        e1 = edges[k+1]
        t0 = e0.tangentAt(e0.LastParameter)
        t1 = e1.tangentAt(e1.FirstParameter)
        d = max(-1.0, min(1.0, v_dot(v_norm((t0.x, t0.y, t0.z)), v_norm((t1.x, t1.y, t1.z)))))
        ang = math.degrees(math.acos(d))
        rep.junctions.append({"junction": k, "angle_deg": round(ang, 3)})
        if ang > 3.0:
            rep.violations.append("%s junction %d: tangent mismatch %.2f deg" % (rep.seg_id, k, ang))
    return Part.Wire(edges)

def sweep_tube(wire, r_tube, seg_id):
    first_edge = wire.Edges[0]
    pa = first_edge.valueAt(first_edge.FirstParameter)
    tang = first_edge.tangentAt(first_edge.FirstParameter)
    prof = Part.Wire([Part.makeCircle(r_tube, pa, tang)])
    try:
        shape = wire.makePipeShell([prof], True, False)
        if shape is not None and shape.isValid() and shape.Volume > 0:
            return shape, "makePipeShell"
    except Exception as exc:
        print("WARN pipe failed for %s: %s" % (seg_id, exc))
    parts = []
    for e in wire.Edges:
        nseg = max(2, int(e.Length/5.0))
        prev = e.valueAt(e.FirstParameter)
        for k in range(1, nseg+1):
            t = e.FirstParameter + (e.LastParameter-e.FirstParameter)*k/nseg
            cur = e.valueAt(t)
            d = (cur.x-prev.x, cur.y-prev.y, cur.z-prev.z)
            if v_len(d) < 1e-9:
                continue
            parts.append(Part.makeCylinder(r_tube, v_len(d), prev, fc_vec(v_norm(d))))
            prev = cur
    if not parts:
        return None, "FAILED"
    shape = parts[0]
    for pp in parts[1:]:
        shape = shape.fuse(pp)
    try:
        shape = shape.removeSplitter()
    except Exception:
        pass
    return shape, "chorded_cylinder_fallback"

# ==========================================================================
# ROUTE DEFINITION (world frame A0 = B601 base_link frame, mm)
# ==========================================================================
YC = 81.625
HN00 = (-29.58, -63.44, -70.0)
HN01 = (-29.58, -63.44, -39.41)
HN02 = (-29.58, -63.44, -18.41)
HN03 = (-19.02, -40.78, 4.59)
C1 = (-29.58, -63.44, -8.0)
C2 = (-22.08, -65.94, 15.73)
C2B = (-9.06, -70.24, 30.0)
JV = (14.56, -77.98, 50.0)
KP = (-0.084, -165.0, 126.0)
WP_OUT = (-0.084, -165.0, -10.0)
RISER_DIR = v_norm(v_sub(KP, HN02))
RISER_MID = v_add(HN02, v_mul(RISER_DIR, 75.9))
# V9 D2-A: enlarge the J1 service-loop radius without changing the joint axis,
# angular coverage or pitch.  The D3-A guide relief is defined in hardware
# below; it never modifies the frozen donor B601 geometry.
J1_C = (-0.084, 0.0, 126.0)
J1_R = 66.0
j1_t1_2d, j1_start_ang = tangent_point_from_external((J1_C[0], J1_C[1]), J1_R, (KP[0], KP[1]), -1)
T1_COIL = (j1_t1_2d[0], j1_t1_2d[1], 126.0)
j1_sweep = -420.0
j1_end_ang = j1_start_ang + j1_sweep
j1_pitch = -12.0
j1_end_z = J1_C[2] + j1_pitch * math.radians(j1_sweep) / (2.0*math.pi)
j1_end = circle_point(J1_C, (1, 0, 0), (0, 1, 0), J1_R, j1_end_ang)
j1_end = (j1_end[0], j1_end[1], j1_end_z)
j1_exit_tan = helix_tangent((0, 0, 1), (1, 0, 0), (0, 1, 0), J1_R, j1_pitch, j1_end_ang, -1)
# D3 candidate-2: actual unwrapped helix crossings of the 100..190 deg
# annulus relief.  The first passage is complete; the second ends at the
# moving-clamp exit.  These stations replace the former nominal z=126 points.
def j1_point_at_unwrapped_angle(ang_deg):
    p = circle_point(J1_C, (1, 0, 0), (0, 1, 0), J1_R, ang_deg)
    dz = j1_pitch * (ang_deg - j1_start_ang) / 360.0
    return v_add(p, (0.0, 0.0, dz))

J1_RELIEF_A1_ANGLE = -170.0   # 190 deg, first-pass entry
J1_RELIEF_B1_ANGLE = -260.0   # 100 deg, first-pass exit
J1_RELIEF_A2_ANGLE = -530.0   # 190 deg, second-pass entry
j1_relief_a1 = j1_point_at_unwrapped_angle(J1_RELIEF_A1_ANGLE)
j1_relief_b1 = j1_point_at_unwrapped_angle(J1_RELIEF_B1_ANGLE)
j1_relief_a2 = j1_point_at_unwrapped_angle(J1_RELIEF_A2_ANGLE)
j1_relief_tan_a1 = helix_tangent((0, 0, 1), (1, 0, 0), (0, 1, 0),
                                 J1_R, j1_pitch, J1_RELIEF_A1_ANGLE, -1)
j1_relief_tan_b1 = helix_tangent((0, 0, 1), (1, 0, 0), (0, 1, 0),
                                 J1_R, j1_pitch, J1_RELIEF_B1_ANGLE, -1)
j1_relief_tan_a2 = helix_tangent((0, 0, 1), (1, 0, 0), (0, 1, 0),
                                 J1_R, j1_pitch, J1_RELIEF_A2_ANGLE, -1)
s_stub = (YC - j1_end[1]) / j1_exit_tan[1]
P_J1OUT = v_add(j1_end, v_mul(j1_exit_tan, s_stub))

# J2 loop: circle C=(15, YC, 85), R50, CW, entry = tangent from P_J1OUT, sweep -270
J2_C = (15.0, YC, 85.0)
j2_t1_xz, j2_start_ang = tangent_point_from_external((J2_C[0], J2_C[2]), 55.0, (P_J1OUT[0], P_J1OUT[2]), -1)
T1_J2 = circle_point(J2_C, (1, 0, 0), (0, 0, 1), 55.0, j2_start_ang)
j2_sweep = -250.0
j2_end_ang = j2_start_ang + j2_sweep
j2_end = circle_point(J2_C, (1, 0, 0), (0, 0, 1), 55.0, j2_end_ang)
j2_exit_tan = tangent_dir_circle((1, 0, 0), (0, 0, 1), j2_end_ang, -1)
s_j2 = (145.0 - j2_end[2]) / j2_exit_tan[2]
M2 = v_add(j2_end, v_mul(j2_exit_tan, s_j2))
M2 = (M2[0], YC, 145.0)

# J3 saddle: circle C=(-255, YC, 82), R63, CCW from top (90 deg), sweep +200
J3_C = (-255.0, YC, 82.0)
j3_start_ang = 90.0
j3_sweep = 200.0
j3_end_ang = j3_start_ang + j3_sweep
j3_end = circle_point(J3_C, (1, 0, 0), (0, 0, 1), 65.0, j3_end_ang)
j3_exit_tan = tangent_dir_circle((1, 0, 0), (0, 0, 1), j3_end_ang, +1)
M3 = v_add(j3_end, v_mul(j3_exit_tan, 60.0))
F4 = (-25.0, YC, 185.0)
T1_J4 = (5.0, YC, 190.0)
J3_HOST_TRANSITION_ARC, J3_HOST_TRANSITION_T1, J3_HOST_BOUNDARY = \
    canonical_fillet_section(j3_end, M3, F4, 55.0)

# V9 J4 external passive carrier.  The old same-plane 315 deg J4 loop,
# J4 moving clamp at the SEG-03 boundary, and narrow link4 channel are removed.
# A single OD<=10 mm bundle runs sequentially through Plane A (y=104) and
# Plane B (y=58); these are transport/return planes, not electrical branches.
J4_SWITCH = (-112.074144, 81.625000, 102.428253)
J4_W1 = (-75.0, 90.0, 140.0)
J4_W2 = (-25.0, 104.0, 185.0)
J4_PLANE_A_DATUM = (20.0, 104.0, 185.0)

J4_CARRIER_R = math.sqrt(23.0**2 + 50.0**2)  # 55.0363516 mm
J4_CARRIER_E1 = (0.0, 23.0/J4_CARRIER_R, -50.0/J4_CARRIER_R)
J4_CARRIER_E2 = (1.0, 0.0, 0.0)
J4_CARRIER_NORMAL = v_norm(v_cross(J4_CARRIER_E1, J4_CARRIER_E2))
J4_CARRIER_SWEEP = 180.0
J4_CARRIER_C0_X = (P["j4_carrier_center_x_mid_mm"] +
                   P["j4_carrier_gain_mm_per_rad"] * (0.0 - P["j4_q_mid_rad"]))
J4_CARRIER_C0 = (J4_CARRIER_C0_X, 81.0, 235.0)
J4_PLANE_A_TANGENCY = v_add(J4_CARRIER_C0, v_mul(J4_CARRIER_E1, J4_CARRIER_R))
J4_PLANE_B_TANGENCY = v_sub(J4_CARRIER_C0, v_mul(J4_CARRIER_E1, J4_CARRIER_R))
J4_HOST_BOUNDARY = (75.0, 58.0, 285.0)
J4_DOWNSTREAM_TURN_1 = (-100.0, 58.0, 285.0)
J4_DOWNSTREAM_TURN_2 = (-100.0, -100.0, 285.0)
E1_J5 = (180.0, -60.0, 320.0)
E2_J5 = (160.0, -180.0, 260.0)

# Outer high-standoff J5 wrap, R55, CW 185 deg.
J5_C = (105.0, -150.0, 260.0)
j5_t1_xy, j5_start_ang = tangent_point_from_external((J5_C[0], J5_C[1]), 55.0, (E2_J5[0], E2_J5[1]), -1)
T1_J5 = (j5_t1_xy[0], j5_t1_xy[1], J5_C[2])
j5_sweep = -185.0
j5_end_ang = j5_start_ang + j5_sweep
j5_end = circle_point(J5_C, (1, 0, 0), (0, 1, 0), 55.0, j5_end_ang)
j5_exit_tan = tangent_dir_circle((1, 0, 0), (0, 1, 0), j5_end_ang, -1)
W1 = v_add(j5_end, v_mul(j5_exit_tan, 70.0))
W2 = v_add(j5_end, v_mul(j5_exit_tan, 210.0))

# J6 helix: axis +x through (170, 0, 191.7), R50, pitch 20, start 180 deg, sweep +630
J6_ORIGIN = (105.0, 0.0, 191.7)
j6_pitch = 20.0
j6_start_ang = 180.0
j6_sweep = 630.0
j6_end_ang = j6_start_ang + j6_sweep
H0 = circle_point(J6_ORIGIN, (0, 1, 0), (0, 0, 1), 55.0, j6_start_ang)
j6_entry_tan = helix_tangent((1, 0, 0), (0, 1, 0), (0, 0, 1), 55.0, j6_pitch, j6_start_ang, +1)
A6 = v_sub(H0, v_mul(j6_entry_tan, 180.0))
W3 = (W2[0], W2[1], A6[2])
j6_end = circle_point(J6_ORIGIN, (0, 1, 0), (0, 0, 1), 55.0, j6_end_ang)
j6_end = v_add(j6_end, v_mul((1, 0, 0), j6_pitch * math.radians(j6_sweep) / (2.0*math.pi)))
j6_exit_tan = helix_tangent((1, 0, 0), (0, 1, 0), (0, 0, 1), 55.0, j6_pitch, j6_end_ang, +1)
STUB_END = v_add(j6_end, v_mul(j6_exit_tan, 55.0))
PLATE = (262.0, -55.0, 241.7)
TAIL1 = (280.0, -30.0, 232.0)
TAIL2 = (282.0, -28.0, 250.0)

SEGMENTS = [
    {
        "id": "SEG-00_BUS_FEEDTHROUGH_AND_RISER",
        "host_links": ["bus", "base_link"],
        "sections": [("poly", [HN00, HN02, WP_OUT, KP, T1_COIL],
                      [55.0, 55.0, 55.0])],
        "take_up_required_mm": 0.0,
        "take_up_capacity_mm": 0.0,
        "note": "static bus feedthrough channel, gentle riser flare to annulus tangent entry (annulus at z=126)",
    },
    {
        "id": "SEG-01_J1_ANNULAR_SERVICE_LOOP",
        "host_links": ["base_link", "link1"],
        "sections": [
            ("helix", (J1_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), J1_R, j1_pitch, j1_start_ang, j1_sweep)),
            ("poly", [j1_end, P_J1OUT, T1_J2], [55.0]),
        ],
        "take_up_required_mm": J1_R*5.6,
        "take_up_capacity_mm": J1_R*math.radians(abs(j1_sweep)),
        "note": "V9 D2-A protected annular service loop: 1.2-turn CW coil R66 pitch -12; tangent exit to J2",
    },
    {
        "id": "SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL",
        "host_links": ["link1", "link2"],
        "sections": [
            ("arc", (J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j2_start_ang, j2_sweep)),
            ("poly", [j2_end, M2, (-208.0, YC, 147.0), (-255.0, YC, 147.0)], [55.0, 0.0, 0.0]),
        ],
        "take_up_required_mm": 55.0*3.14,
        "take_up_capacity_mm": 55.0*math.radians(abs(j2_sweep)),
        "note": "semi-captive guided U-loop R50 CW 250 deg, tangent exit to link2 channel and J3 carrier straight",
    },
    {
        "id": "SEG-03_J3_CARRIER_HYBRID_WRAP",
        "host_links": ["link2", "link3"],
        "sections": [
            ("arc", (J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 65.0, j3_start_ang, j3_sweep)),
            ("poly", [j3_end, J3_HOST_TRANSITION_T1], []),
            J3_HOST_TRANSITION_ARC,
            ("poly", [J3_HOST_BOUNDARY, J4_SWITCH], []),
        ],
        "take_up_required_mm": 65.0*3.14,
        "take_up_capacity_mm": 2.0*P["carrier_travel_mm"],
        "note": ("festoon take-up via moving carriage (2x110=220), R63 guide saddle, "
                 "and explicit R55 J3 host transition; post-boundary channel is link3-only and terminates at V9 J4 switch station"),
    },
    {
        "id": "SEG-04_J4_SEGMENTED_MOVING_CARRIER_DUAL_PLANE_SADDLE",
        "host_links": ["link3", "link4"],
        "sections": [
            ("poly", [J4_SWITCH, J4_W1, J4_W2, J4_PLANE_A_DATUM], [55.0, 55.0]),
            ("poly", [J4_PLANE_A_DATUM, J4_PLANE_A_TANGENCY], []),
            ("arc", (J4_CARRIER_C0, J4_CARRIER_NORMAL,
                     J4_CARRIER_E1, J4_CARRIER_E2,
                     J4_CARRIER_R, 0.0, J4_CARRIER_SWEEP)),
            ("poly", [J4_PLANE_B_TANGENCY, J4_HOST_BOUNDARY], []),
            ("poly", [J4_HOST_BOUNDARY, J4_DOWNSTREAM_TURN_1,
                      J4_DOWNSTREAM_TURN_2, E1_J5, E2_J5, T1_J5],
             [55.0, 55.0, 55.0, 55.0]),
        ],
        "take_up_required_mm": 55.0*3.44,
        "take_up_capacity_mm": 2.0*P["j4_carrier_hard_stop_travel_mm"],
        "note": ("V9 ODR-58 primary topology: link3 fixed Plane-A transport, q4-generated "
                 "passive moving 180deg R55.036 saddle, Plane-B return to link4 host boundary, "
                 "then link4-only external R55 downstream route; no same-plane J4 near-full-circle"),
    },
    {
        "id": "SEG-05_J5_WRIST_WRAP",
        "host_links": ["link4", "link5"],
        "sections": [
            ("arc", (J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 55.0, j5_start_ang, j5_sweep)),
            ("poly", [j5_end, W2, W3, A6, H0], [55.0, 55.0, 55.0]),
        ],
        "take_up_required_mm": 55.0*3.14,
        "take_up_capacity_mm": 55.0*math.radians(abs(j5_sweep)),
        "note": "V9 D1-A external J5 wrap R55 CW 185 deg and R55 high return dogleg to the frozen J6 entry tangent",
    },
    {
        "id": "SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN",
        "host_links": ["link5", "link6"],
        "sections": [
            ("helix", (J6_ORIGIN, (1, 0, 0), (0, 1, 0), (0, 0, 1), 55.0, j6_pitch, j6_start_ang, j6_sweep)),
            ("poly", [j6_end, STUB_END, PLATE], [55.0]),
        ],
        "take_up_required_mm": 55.0*6.28,
        "take_up_capacity_mm": 55.0*math.radians(abs(j6_sweep))*1.002,
        "note": "helical wrist wrap R50 pitch 20, 1.75 turns around link6 axis line; axial wrist run to split plate",
    },
    {
        "id": "SEG-07A_WRIST_TAIL_DATA",
        "host_links": ["link6"],
        "sections": [("poly", [PLATE, TAIL1], [])],
        "take_up_required_mm": 0.0,
        "take_up_capacity_mm": 0.0,
        "note": "data connector fan-out tail; branch bend accommodated inside RC-PLT-WRIST-SPLIT hardware",
    },
    {
        "id": "SEG-07B_WRIST_TAIL_POWER",
        "host_links": ["link6"],
        "sections": [("poly", [PLATE, TAIL2], [])],
        "take_up_required_mm": 0.0,
        "take_up_capacity_mm": 0.0,
        "note": "power/sensor connector fan-out tail; branch bend accommodated inside RC-PLT-WRIST-SPLIT hardware",
    },
]

# ==========================================================================
# FreeCAD build
# ==========================================================================
doc = App.newDocument("B601_ROUTE_C_GUIDED_DRESS_PACK_V9")
part_registry = []
part_objects = {}
receipt_parts = []
part_axis_registry = {}
part_bore_registry = {}

def add_shape(shape, name, kind, material, host_link, role,
              geometry_role="PHYSICAL", mass_counted=True,
              overlap_disposition="NON_OVERLAPPING_BY_CONSTRUCTION"):
    if shape is None:
        receipt_parts.append({"name": name, "valid": False, "error": "no shape"})
        return None
    internal = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in name)
    obj = doc.addObject("Part::Feature", internal)
    obj.Label = name
    obj.Shape = shape
    part_objects[name] = obj
    part_registry.append({"name": name, "kind": kind, "material": material,
                          "host_link": host_link, "role": role,
                          "geometry_role": geometry_role,
                          "mass_counted": bool(mass_counted),
                          "overlap_disposition": overlap_disposition})
    vol = shape.Volume if shape.isValid() else 0.0
    mass_g = vol * DENS[material] if (mass_counted and material in DENS) else None
    receipt_parts.append({"name": name, "valid": bool(shape.isValid()), "volume_mm3": vol,
                          "material": material, "mass_g_estimate": mass_g,
                          "host_link": host_link, "kind": kind, "role": role,
                          "geometry_role": geometry_role,
                          "mass_counted": bool(mass_counted),
                          "overlap_disposition": overlap_disposition})
    return obj

def refresh_part_metrics(name):
    """Refresh receipt/mass metrics after a post-creation cut operation."""
    obj = part_objects.get(name)
    if obj is None:
        return
    for rec in receipt_parts:
        if rec.get("name") == name:
            vol = obj.Shape.Volume if obj.Shape.isValid() else 0.0
            rec["valid"] = bool(obj.Shape.isValid())
            rec["volume_mm3"] = vol
            mat = rec.get("material")
            rec["mass_g_estimate"] = (vol * DENS[mat]
                                       if rec.get("mass_counted") and mat in DENS else None)
            return

def oriented_box(name, center, size, x_dir, y_dir, material, host_link, role, kind="hardware"):
    xd = v_norm(x_dir)
    yd = v_norm(y_dir)
    zd = v_norm(v_cross(xd, yd))
    M = App.Matrix(xd[0], yd[0], zd[0], 0,
                   xd[1], yd[1], zd[1], 0,
                   xd[2], yd[2], zd[2], 0,
                   0, 0, 0, 1)
    sh = Part.makeBox(size[0], size[1], size[2])
    sh = sh.transformGeometry(M)
    sh.Placement = App.Placement(fc_vec((center[0]-xd[0]*size[0]/2-yd[0]*size[1]/2-zd[0]*size[2]/2,
                                         center[1]-xd[1]*size[0]/2-yd[1]*size[1]/2-zd[1]*size[2]/2,
                                         center[2]-xd[2]*size[0]/2-yd[2]*size[1]/2-zd[2]*size[2]/2)),
                                 App.Rotation())
    return add_shape(sh, name, kind, material, host_link, role)

def box_at(name, center, size, material, host_link, role):
    return oriented_box(name, center, size, (1, 0, 0), (0, 1, 0), material, host_link, role)

def ring(name, center, axis, r_out, r_in, h, material, host_link, role):
    a = v_norm(axis)
    base = v_sub(center, v_mul(a, h/2.0))
    outer = Part.makeCylinder(r_out, h, fc_vec(base), fc_vec(a))
    inner = Part.makeCylinder(r_in, h, fc_vec(base), fc_vec(a))
    return add_shape(outer.cut(inner), name, "guide_ring", material, host_link, role)

def cut_annulus_sector_z(obj, center_xy, z_min, z_max, start_deg, end_deg,
                         radius=100.0):
    """Cut an inclusive XY fan sector through a z-axis annular part."""
    if obj is None:
        return
    pts = [App.Vector(center_xy[0], center_xy[1], z_min)]
    n = max(8, int(math.ceil(abs(end_deg-start_deg)/5.0)))
    for i in range(n+1):
        a = math.radians(start_deg + (end_deg-start_deg)*i/n)
        pts.append(App.Vector(center_xy[0] + radius*math.cos(a),
                              center_xy[1] + radius*math.sin(a), z_min))
    pts.append(pts[0])
    fan = Part.Face(Part.makePolygon(pts)).extrude(App.Vector(0, 0, z_max-z_min))
    obj.Shape = obj.Shape.cut(fan)
    refresh_part_metrics(obj.Label)

def clamp_saddle(name, pt, direction, material, host_link, role, width=14.0,
                 bore_r=None, kind="clamp"):
    if bore_r is None:
        bore_r = P["clamp_bore_r_mm"]
    d = v_norm(direction)
    part_axis_registry[name] = d
    part_bore_registry[name] = float(bore_r)
    ref = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (0.0, 1.0, 0.0)
    yd = v_norm(v_cross(d, ref))
    cross = max(20.0, 2.0*bore_r + 4.0)
    oriented_box(name, pt, (width, cross, cross), d, yd, material, host_link, role, kind=kind)
    bore = Part.makeCylinder(bore_r, width+4.0,
                             fc_vec(v_sub(pt, v_mul(d, width/2.0+2.0))), fc_vec(d))
    obj = part_objects.get(name)
    if obj is not None:
        obj.Shape = obj.Shape.cut(bore)
        refresh_part_metrics(name)
    return obj

def guide_support_saddle(name, pt, direction, material, host_link, role, width=14.0):
    return clamp_saddle(name, pt, direction, material, host_link, role, width=width,
                        bore_r=P["guide_support_bore_r_mm"], kind="guide_support")


def j4_carrier_link(name, center, host_link, role):
    """Low-profile 16x14 mm outer / 12x12 mm clear articulated link at q4=0."""
    outer = Part.makeBox(8.0, 16.0, 14.0,
                         fc_vec((center[0]-4.0, center[1]-8.0, center[2]-7.0)))
    inner = Part.makeBox(12.0, 12.0, 12.0,
                         fc_vec((center[0]-6.0, center[1]-6.0, center[2]-6.0)))
    return add_shape(outer.cut(inner), name, "carrier_link", "polymer", host_link, role,
                     geometry_role="PHYSICAL", mass_counted=True,
                     overlap_disposition="RECTANGULAR_FRAME_CLEAR_12X12_AROUND_OD10_BUNDLE")

def channel_section(name, p0, p1, width, height, material, host_link, role):
    d = v_norm(v_sub(p1, p0))
    L = v_dist(p0, p1)
    up = (0.0, 0.0, 1.0)
    yv = v_norm(v_cross(d, up)) if abs(d[2]) < 0.95 else v_norm(v_cross(d, (0, 1, 0)))
    zv = v_norm(v_cross(yv, d))
    t = 2.0
    def plate(name2, off_along, off_side, off_up, sx, sy, sz, mat, kind):
        c = v_add(p0, v_add(v_mul(d, off_along), v_add(v_mul(yv, off_side), v_mul(zv, off_up))))
        return oriented_box(name2, c, (sx, sy, sz), d, yv, mat, host_link, role, kind=kind)
    plate(name+"-BASE", L/2.0, 0.0, -height/2.0-t/2.0, L, width+2*t, t, material, "guide_channel")
    plate(name+"-WALL-A", L/2.0, -(width/2.0+t/2.0), 0.0, L, t, height, material, "guide_channel")
    plate(name+"-WALL-B", L/2.0, (width/2.0+t/2.0), 0.0, L, t, height, material, "guide_channel")
    plate(name+"-LINER", L/2.0, 0.0, -height/2.0+0.5, L, width-1.0, 0.8, "polymer", "liner")

def guide_tube(name, center, normal, e1, e2, R, start_deg, sweep_deg, r_tube, material, host_link, role, kind):
    rep = SegReport(name)
    e = arc_edge(center, normal, e1, e2, R, start_deg, sweep_deg, rep)
    w = Part.Wire([e])
    sh, method = sweep_tube(w, r_tube, name)
    add_shape(sh, name, kind, material, host_link, role)
    return sh

def guide_tube_poly(name, points, corner_radii, r_tube, material, host_link, role, kind):
    rep = SegReport(name)
    edges = poly_edges(points, corner_radii, rep)
    w = Part.Wire(edges)
    sh, method = sweep_tube(w, r_tube, name)
    add_shape(sh, name, kind, material, host_link, role)
    return sh


def tube_shell_on_wire(name, wire, r_outer, r_inner, material, host_link, role, kind):
    if not (r_outer > r_inner > P["bundle_r_upper"]):
        raise ValueError("invalid guide shell radii for %s" % name)
    outer, _ = sweep_tube(wire, r_outer, name + "-OUTER")
    inner, _ = sweep_tube(wire, r_inner, name + "-INNER")
    shell = outer.cut(inner)
    add_shape(shell, name, kind, material, host_link, role,
              geometry_role="PHYSICAL", mass_counted=True,
              overlap_disposition="ANNULAR_SHELL_EXCLUDES_CABLE_AND_NESTED_LINER")
    return shell


def guide_tube_shell(name, center, normal, e1, e2, R, start_deg, sweep_deg,
                     r_outer, r_inner, material, host_link, role, kind):
    rep = SegReport(name)
    edge = arc_edge(center, normal, e1, e2, R, start_deg, sweep_deg, rep)
    return tube_shell_on_wire(name, Part.Wire([edge]), r_outer, r_inner,
                              material, host_link, role, kind)


def guide_tube_poly_shell(name, points, corner_radii, r_outer, r_inner,
                          material, host_link, role, kind):
    rep = SegReport(name)
    wire = Part.Wire(poly_edges(points, corner_radii, rep))
    return tube_shell_on_wire(name, wire, r_outer, r_inner,
                              material, host_link, role, kind)

# --- bundle tubes per segment ----------------------------------------------
segment_reports = []
bundle_solids = {}
bundle_wires = {}
for seg in SEGMENTS:
    rep = SegReport(seg["id"])
    wire = build_segment_wire(seg["sections"], rep)
    shape, method = sweep_tube(wire, P["bundle_r"], seg["id"])
    name = "RC-BUNDLE-" + seg["id"].replace("_", "-")
    add_shape(shape, name, "bundle_envelope", "bundle", seg["host_links"][-1],
              "harness bundle envelope OD %.1f mm" % P["bundle_od_mm"],
              geometry_role="BUNDLE_ENVELOPE", mass_counted=False,
              overlap_disposition="LOGICAL_COLLISION_ENVELOPE_NOT_A_HARDWARE_SOLID")
    bundle_solids[seg["id"]] = shape
    bundle_wires[seg["id"]] = wire
    segment_reports.append({
        "segment": seg["id"], "host_links": seg["host_links"],
        "path_length_mm": wire.Length,
        "min_bend_radius_mm": (None if rep.min_bend_radius > 1e8 else rep.min_bend_radius),
        "take_up_required_mm": seg["take_up_required_mm"],
        "take_up_capacity_mm": seg["take_up_capacity_mm"],
        "corners": rep.corners, "junctions": rep.junctions,
        "adjustments": rep.adjustments, "violations": rep.violations,
        "sweep_method": method,
    })

# Deterministic exact-curve stations used by physical clamps/supports.  Points
# are evaluated on the actual FreeCAD wire, not on rounded design vertices.
_wire_sample_cache = {}
def wire_samples(seg_id, max_step=0.10):
    key = (seg_id, max_step)
    if key in _wire_sample_cache:
        return _wire_sample_cache[key]
    out = []
    cum = 0.0
    last = None
    for edge in bundle_wires[seg_id].Edges:
        n = max(2, int(math.ceil(edge.Length/max_step)))
        for k in range(n+1):
            u = edge.FirstParameter + (edge.LastParameter-edge.FirstParameter)*k/n
            p = edge.valueAt(u)
            t = edge.tangentAt(u)
            pt = (p.x, p.y, p.z)
            if last is not None:
                cum += v_dist(last, pt)
            if out and v_dist(out[-1][1], pt) < 1e-9:
                out[-1] = (cum, pt, v_norm((t.x, t.y, t.z)))
            else:
                out.append((cum, pt, v_norm((t.x, t.y, t.z))))
            last = pt
    _wire_sample_cache[key] = out
    return out

def route_station_near(seg_id, target):
    return min(wire_samples(seg_id), key=lambda r: v_dist(r[1], target))[1:]

def route_station_length(seg_id, station_mm):
    samples = wire_samples(seg_id)
    target = max(0.0, min(float(station_mm), samples[-1][0]))
    return min(samples, key=lambda r: abs(r[0]-target))[1:]

# SEG-00 stations are intentional along-route offsets.  The prior HN vertex
# coordinates sat tens of millimetres away from the R55 filleted cable axis.
BUS00_PT, BUS00_TAN = route_station_length("SEG-00_BUS_FEEDTHROUGH_AND_RISER", 25.0)
BUS01_PT, BUS01_TAN = route_station_length("SEG-00_BUS_FEEDTHROUGH_AND_RISER", 50.0)
BUS02_PT, BUS02_TAN = route_station_length("SEG-00_BUS_FEEDTHROUGH_AND_RISER", 130.0)
BUS03_PT, BUS03_TAN = route_station_length("SEG-00_BUS_FEEDTHROUGH_AND_RISER", 210.0)

L1_PT, L1_TAN = route_station_near("SEG-01_J1_ANNULAR_SERVICE_LOOP",
                                    v_add(j1_end, v_mul(j1_exit_tan, 30.0)))
J2_MOV_PT, J2_MOV_TAN = route_station_near("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", M2)
L2_01_PT, L2_01_TAN = route_station_near("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL",
                                         (-80.0, YC, 147.0))
J3_CARR_PT, J3_CARR_TAN = route_station_near("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL",
                                             (-140.0, YC, 147.0))
_l3_seed_dir = v_norm(v_sub(J4_SWITCH, J3_HOST_BOUNDARY))
_l3_seed_1 = v_add(J3_HOST_BOUNDARY,
                    v_mul(_l3_seed_dir, v_dist(J3_HOST_BOUNDARY, J4_SWITCH)/3.0))
_l3_seed_2 = v_add(J3_HOST_BOUNDARY,
                    v_mul(_l3_seed_dir, 2.0*v_dist(J3_HOST_BOUNDARY, J4_SWITCH)/3.0))
L3_01_PT, L3_01_TAN = route_station_near("SEG-03_J3_CARRIER_HYBRID_WRAP", _l3_seed_1)
L3_02_PT, L3_02_TAN = route_station_near("SEG-03_J3_CARRIER_HYBRID_WRAP", _l3_seed_2)
J4_FIX_PT, J4_FIX_TAN = route_station_near(
    "SEG-04_J4_SEGMENTED_MOVING_CARRIER_DUAL_PLANE_SADDLE", J4_PLANE_A_DATUM)
J4_PA_PT, J4_PA_TAN = route_station_near(
    "SEG-04_J4_SEGMENTED_MOVING_CARRIER_DUAL_PLANE_SADDLE", J4_PLANE_A_TANGENCY)
J4_PB_PT, J4_PB_TAN = route_station_near(
    "SEG-04_J4_SEGMENTED_MOVING_CARRIER_DUAL_PLANE_SADDLE", J4_PLANE_B_TANGENCY)
L4_01_PT, L4_01_TAN = route_station_near(
    "SEG-04_J4_SEGMENTED_MOVING_CARRIER_DUAL_PLANE_SADDLE", J4_DOWNSTREAM_TURN_1)
L4_E1_PT, L4_E1_TAN = route_station_near(
    "SEG-04_J4_SEGMENTED_MOVING_CARRIER_DUAL_PLANE_SADDLE", J4_DOWNSTREAM_TURN_2)
L4_E2_PT, L4_E2_TAN = route_station_near(
    "SEG-04_J4_SEGMENTED_MOVING_CARRIER_DUAL_PLANE_SADDLE", E2_J5)
J5_W2_PT, J5_W2_TAN = route_station_near("SEG-05_J5_WRIST_WRAP", W2)
J5_W3_PT, J5_W3_TAN = route_station_near("SEG-05_J5_WRIST_WRAP", W3)
J5_A6_PT, J5_A6_TAN = route_station_near("SEG-05_J5_WRIST_WRAP", A6)
WR_SR_PT, WR_SR_TAN = route_station_near("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN",
                                         (225.0, -55.0, 241.7))

# --- hardware ---------------------------------------------------------------
# bus feedthrough channel + flange + connector + clamps
channel_section("RC-CHN-BUS-FT", (-29.58, -63.44, -70.0), (-29.58, -63.44, -6.0),
                12.0, 12.0, "aluminum", "bus", "bus passage feedthrough channel (HN-00..C1)")
box_at("RC-BRK-BUS-FLANGE", (-29.58, -63.44, -60.0), (30.0, 30.0, 4.0), "aluminum", "bus",
       "feedthrough mounting flange at HN-00, fasteners 4xM3")
box_at("RC-PLT-BUS-CONN", (-29.58, -63.44, -58.0), (26.0, 8.0, 6.0), "polymer", "bus",
       "CN-BUS-00 connector plate at HN-00 (Micro-D style candidate)")
clamp_saddle("RC-CLP-BUS-HN01", BUS00_PT, BUS00_TAN, "aluminum", "bus",
             "CF-BUS-00 fixed clamp at exact SEG-00 s=25 mm station")
clamp_saddle("RC-CLP-BUS-HN02", BUS01_PT, BUS01_TAN, "aluminum", "bus",
             "CF-BUS-01 fixed clamp + strain relief at exact SEG-00 s=50 mm station")

# base collar bracket + HN-03 connector plate + riser clamps
ring("RC-BRK-BASE-COLLAR", (0.0, 0.0, 6.0), (0, 0, 1), 52.0, 44.5, 12.0, "aluminum", "base_link",
     "derived collar clamp ring on base_link collar (no donor modification), fasteners 8xM3 at R45.25 pattern face")
box_at("RC-PLT-BASE-CONN", HN03, (26.0, 8.0, 10.0), "polymer", "base_link",
       "CN-BASE-00 connector plate at HN-03 station")
clamp_saddle("RC-CLP-BUS-HN03", BUS02_PT, BUS02_TAN, "aluminum", "base_link",
             "CF-BUS-02 route clamp at exact SEG-00 s=130 mm station")
clamp_saddle("RC-CLP-BUS-RISER", BUS03_PT, BUS03_TAN, "aluminum", "base_link",
             "CF-BUS-03 riser clamp at exact SEG-00 s=210 mm station")
oriented_box("RC-BRK-J1-RISER", (-0.084, -165.0, 58.0), (8.0, 12.0, 136.0), (0, 0, 1), (0, 1, 0),
             "aluminum", "base_link", "riser guide bracket along vertical riser JV->KP", kind="bracket")

# J1 annular channel, V9 D2-A radial capacity + D3-A full sector relief.
ann_low = ring("RC-GDE-J1-ANNULUS-LOW", (J1_C[0], J1_C[1], J1_C[2]-1.5), (0, 0, 1), 74.0, 52.0, 3.0, "aluminum", "base_link",
               "V9 annular service-loop lower cheek, R66 capacity, 100-190 deg relief")
ann_up = ring("RC-GDE-J1-ANNULUS-UP", (J1_C[0], J1_C[1], J1_C[2]+16.0), (0, 0, 1), 74.0, 52.0, 3.0, "aluminum", "base_link",
              "V9 annular service-loop upper cheek, R66 capacity, 100-190 deg relief")
wall = ring("RC-GDE-J1-ANNULUS-WALL", (J1_C[0], J1_C[1], J1_C[2]+7.25), (0, 0, 1), 78.0, 74.0, 17.5, "aluminum", "base_link",
            "V9 annulus outer containment wall, 100-190 deg relief")
liner = ring("RC-GDE-J1-LINER", (J1_C[0], J1_C[1], J1_C[2]+1.6), (0, 0, 1), 69.0, 63.0, 1.0, "polymer", "base_link",
             "V9 annulus liner band, 100-190 deg relief")
for ann_obj in (ann_low, ann_up, wall, liner):
    cut_annulus_sector_z(ann_obj, (J1_C[0], J1_C[1]), 110.0, 152.0,
                         100.0, 190.0, radius=100.0)
if wall is not None:
    notch_center = v_add(T1_COIL, v_mul(v_norm(v_sub(T1_COIL, KP)), -12.0))
    notch = Part.makeBox(22.0, 22.0, 22.0, fc_vec(v_sub(notch_center, (11.0, 11.0, 11.0))))
    wall.Shape = wall.Shape.cut(notch)
    refresh_part_metrics("RC-GDE-J1-ANNULUS-WALL")
# D3 candidate-2 relief-end retainers sit on the actual two-layer helix.
# First-pass A1->B1 free span = R*90deg; second-pass A2->moving exit is
# R*46.422deg.  Both are below the controlled P13 150 mm maximum.
clamp_saddle("RC-CLP-J1-RELIEF-A1", j1_relief_a1, j1_relief_tan_a1,
             "polymer", "base_link", "V9 D3 first-pass 190deg relief-entry retainer", width=10.0)
clamp_saddle("RC-CLP-J1-RELIEF-B1", j1_relief_b1, j1_relief_tan_b1,
             "polymer", "base_link", "V9 D3 first-pass 100deg relief-exit retainer", width=10.0)
clamp_saddle("RC-CLP-J1-RELIEF-A2", j1_relief_a2, j1_relief_tan_a2,
             "polymer", "base_link", "V9 D3 second-pass 190deg relief-entry retainer", width=10.0)
clamp_saddle("RC-CLP-J1-MOV", j1_end, j1_exit_tan, "aluminum", "link1", "CM-J1-M rotating clamp on link1 at annulus exit")
clamp_saddle("RC-CLP-L1-01", L1_PT, L1_TAN, "aluminum", "link1",
             "CF-L1-01 fixed clamp on link1 annulus exit stub")
box_at("RC-BRK-L1-01", (j1_end[0]+10.0, j1_end[1]+10.0, j1_end[2]-12.0), (20.0, 20.0, 6.0), "aluminum", "link1",
       "link1 derived bracket pad for CM-J1-M / CF-L1-01 (2xM3 each)")

# J2 mandrel + liner + clamps
guide_tube_shell("RC-GDE-J2-MANDREL", J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1),
                 55.0, j2_start_ang, j2_sweep, 9.5, 7.2,
                 "aluminum", "link1", "J2 split-shell U-loop guide R55", "guide_mandrel")
guide_tube_shell("RC-GDE-J2-MANDREL-LINER", J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1),
                 55.0, j2_start_ang, j2_sweep, 7.2, 5.8,
                 "polymer", "link1", "J2 replaceable low-friction liner shell", "liner")
clamp_saddle("RC-CLP-J2-FIX", T1_J2, tangent_dir_circle((1, 0, 0), (0, 0, 1), j2_start_ang, -1), "aluminum", "link1",
             "CF-J2-F fixed clamp on link1 side of J2 loop")
clamp_saddle("RC-CLP-J2-MOV", J2_MOV_PT, J2_MOV_TAN, "aluminum", "link2", "CM-J2-M moving clamp on link2 side of J2 loop")

# link2 channel + carrier track + carriage + e-chain links
channel_section("RC-CHN-L2", M2, (-208.0, YC, 147.0), 12.0, 12.0, "aluminum", "link2",
                "link2 fixed channel incl. carrier straight section")
clamp_saddle("RC-CLP-L2-01", L2_01_PT, L2_01_TAN, "aluminum", "link2", "CF-L2-01 fixed clamp")
clamp_saddle("RC-CLP-L2-02", (-208.0, YC, 147.0), (-1, 0, 0), "aluminum", "link2", "CF-L2-02 fixed clamp at channel end")
box_at("RC-TRK-J3-RAIL", (-140.0, YC+10.0, 138.0), (120.0, 6.0, 4.0), "aluminum", "link2",
       "J3 carrier track rail, travel zone x -85..-195")
box_at("RC-TRK-J3-STOP-A", (-85.0, YC+10.0, 141.0), (4.0, 8.0, 10.0), "aluminum", "link2", "carrier hard stop A (x=-85)")
box_at("RC-TRK-J3-STOP-B", (-195.0, YC+10.0, 141.0), (4.0, 8.0, 10.0), "aluminum", "link2", "carrier hard stop B (x=-195)")
oriented_box("RC-CAR-J3-CARRIAGE", (-140.0, YC, 147.0), (36.0, 24.0, 22.0), (1, 0, 0), (0, 1, 0), "aluminum", "link2",
             "J3 moving carriage (nominal mid-travel x=-140), bore for bundle, E2.10-class guide channel", kind="carrier")
clamp_saddle("RC-CLP-J3-MOV", J3_CARR_PT, J3_CARR_TAN, "polymer", "link2", "CM-J3-M moving clamp on carriage")
for i in range(6):
    box_at("RC-CHN-E210-LINK-%02d" % i, (-95.0 - i*20.0, YC, 147.0), (18.0, 16.0, 10.0), "polymer", "link2",
           "igus E2.10 e-chain link %d/6 (pitch 20, inner 10x16)" % (i+1))

# J3 saddle + liner
guide_tube_shell("RC-GDE-J3-SADDLE", J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1),
                 65.0, j3_start_ang, j3_sweep, 9.5, 7.2,
                 "aluminum", "link2", "J3 split-shell guide saddle R65", "guide_saddle")
guide_tube_shell("RC-GDE-J3-SADDLE-LINER", J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1),
                 65.0, j3_start_ang, j3_sweep, 7.2, 5.8,
                 "polymer", "link2", "J3 replaceable saddle liner shell", "liner")

# link3 host-boundary clamp, channel + clamps.  The physical clamp is the
# kinematic ownership boundary; the J3 saddle/transition upstream remains a
# dual-host compliance section while the downstream channel is link3-only.
clamp_saddle("RC-CLP-J3-HOST-BOUNDARY", J3_HOST_BOUNDARY,
             v_norm(v_sub(J4_SWITCH, J3_HOST_BOUNDARY)), "aluminum", "link3",
             "CM-J3-HB physical host-boundary clamp on link3")
channel_section("RC-CHN-L3", J3_HOST_BOUNDARY, J4_SWITCH, 12.0, 12.0, "aluminum", "link3",
                "link3-only fixed channel ending at V9 J4 switch station")
l3_dir = v_norm(v_sub(J4_SWITCH, J3_HOST_BOUNDARY))
l3_p1 = v_add(J3_HOST_BOUNDARY, v_mul(l3_dir, v_dist(J3_HOST_BOUNDARY, J4_SWITCH)/3.0))
l3_p2 = v_add(J3_HOST_BOUNDARY, v_mul(l3_dir, 2.0*v_dist(J3_HOST_BOUNDARY, J4_SWITCH)/3.0))
clamp_saddle("RC-CLP-L3-01", L3_01_PT, L3_01_TAN, "aluminum", "link3", "CF-L3-01 fixed clamp")
clamp_saddle("RC-CLP-L3-02", L3_02_PT, L3_02_TAN, "aluminum", "link3", "CF-L3-02 fixed clamp")
clamp_saddle("RC-CLP-J4-FIX", J4_FIX_PT, J4_FIX_TAN, "aluminum", "link3",
             "CF-J4-F fixed clamp at Plane-A datum before passive carrier")

# V9 J4 Plane-A transport shell, passive carriage/rail, dual-plane saddle and
# Plane-B host-boundary clamp.  All solids are additive removable accessories;
# the accepted B601 body and URDF are read-only.
guide_tube_poly_shell("RC-GDE-J4-PLANE-A", [J4_SWITCH, J4_W1, J4_W2, J4_PLANE_A_DATUM],
                      [55.0, 55.0], 9.5, 7.2, "aluminum", "link3",
                      "V9 fixed Plane-A split transport conduit", "guide_channel")
guide_tube_poly_shell("RC-GDE-J4-PLANE-A-LINER", [J4_SWITCH, J4_W1, J4_W2, J4_PLANE_A_DATUM],
                      [55.0, 55.0], 7.2, 5.8, "polymer", "link3",
                      "V9 Plane-A replaceable low-friction liner shell", "liner")
box_at("RC-TRK-J4-RAIL", (160.0, 81.0, 235.0), (110.0, 6.0, 6.0), "aluminum", "link3",
       "V9 passive carriage rail, hard-stop centers x=110..210")
box_at("RC-TRK-J4-STOP-A", (110.0, 81.0, 235.0), (5.0, 14.0, 18.0), "aluminum", "link3",
       "V9 J4 carrier negative hard stop x=110")
box_at("RC-TRK-J4-STOP-B", (210.0, 81.0, 235.0), (5.0, 14.0, 18.0), "aluminum", "link3",
       "V9 J4 carrier positive hard stop x=210")
oriented_box("RC-CAR-J4-CARRIAGE", J4_CARRIER_C0, (30.0, 18.0, 16.0),
             (1, 0, 0), (0, 1, 0), "aluminum", "link3",
             "V9 passive J4 carriage at q4=0 datum", kind="carrier")
for i, x in enumerate([32.0, 52.0, 72.0, 92.0, 112.0, 132.0, 152.0]):
    j4_carrier_link("RC-CHN-J4-PLANE-A-LINK-%02d" % i, (x, 104.0, 185.0), "link3",
                    "V9 low-profile Plane-A articulated carrier link %d/7 at q4=0" % (i+1))
for i, x in enumerate([85.0, 105.0, 125.0, 145.0]):
    j4_carrier_link("RC-CHN-J4-PLANE-B-LINK-%02d" % i, (x, 58.0, 285.0), "link3",
                    "V9 low-profile Plane-B articulated return link %d/4 at q4=0" % (i+1))
guide_tube_shell("RC-GDE-J4-CARRIER-SADDLE", J4_CARRIER_C0, J4_CARRIER_NORMAL,
                 J4_CARRIER_E1, J4_CARRIER_E2, J4_CARRIER_R, 0.0, J4_CARRIER_SWEEP,
                 9.5, 7.2, "aluminum", "link3",
                 "V9 carriage-mounted oblique 180deg dual-plane saddle", "guide_saddle")
guide_tube_shell("RC-GDE-J4-CARRIER-SADDLE-LINER", J4_CARRIER_C0, J4_CARRIER_NORMAL,
                 J4_CARRIER_E1, J4_CARRIER_E2, J4_CARRIER_R, 0.0, J4_CARRIER_SWEEP,
                 7.2, 5.8, "polymer", "link3",
                 "V9 replaceable carrier-saddle liner shell", "liner")
clamp_saddle("RC-CLP-J4-MOV", J4_HOST_BOUNDARY, (-1.0, 0.0, 0.0), "aluminum", "link4",
             "CM-J4-M moving host-boundary clamp on link4 after Plane-B return")

# Link4-only external downstream route to the frozen J5 interface.
l4_clamp_pt = L4_01_PT
clamp_saddle("RC-CLP-L4-01", L4_01_PT, L4_01_TAN, "aluminum", "link4",
             "CF-L4-01 fixed clamp at external turn 1")
guide_tube_poly_shell("RC-GDE-J5-HIGH-BYPASS",
                      [J4_HOST_BOUNDARY, J4_DOWNSTREAM_TURN_1,
                       J4_DOWNSTREAM_TURN_2, E1_J5, E2_J5, T1_J5],
                      [55.0, 55.0, 55.0, 55.0], 9.5, 7.2, "aluminum", "link4",
                      "V9 link4-only external R55 split conduit", "guide_channel")
guide_tube_poly_shell("RC-GDE-J5-HIGH-BYPASS-LINER",
                      [J4_HOST_BOUNDARY, J4_DOWNSTREAM_TURN_1,
                       J4_DOWNSTREAM_TURN_2, E1_J5, E2_J5, T1_J5],
                      [55.0, 55.0, 55.0, 55.0], 7.2, 5.8, "polymer", "link4",
                      "V9 link4-only replaceable low-friction liner shell", "liner")
guide_support_saddle("RC-GSP-L4-HIGH-E1", L4_E1_PT, L4_E1_TAN, "aluminum", "link4",
                     "V9 external downstream conduit support at turn 2")
guide_support_saddle("RC-GSP-L4-HIGH-E2", L4_E2_PT, L4_E2_TAN, "aluminum", "link4",
                     "V9 external downstream conduit support before J5")
clamp_saddle("RC-CLP-J5-FIX", T1_J5,
             tangent_dir_circle((1, 0, 0), (0, 1, 0), j5_start_ang, -1),
             "aluminum", "link4", "CF-J5-F fixed clamp at external J5 wrap entry")

# J5 wrap mandrel + liner + clamps
guide_tube_shell("RC-GDE-J5-WRAP", J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0),
                 55.0, j5_start_ang, j5_sweep, 9.5, 7.2,
                 "aluminum", "link5", "J5 split-shell wrist wrap R55", "guide_mandrel")
guide_tube_shell("RC-GDE-J5-WRAP-LINER", J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0),
                 55.0, j5_start_ang, j5_sweep, 7.2, 5.8,
                 "polymer", "link5", "J5 replaceable wrap liner shell", "liner")
clamp_saddle("RC-CLP-J5-MOV", j5_end, j5_exit_tan, "aluminum", "link5", "CM-J5-M moving clamp at J5 wrap exit")
guide_tube_poly_shell("RC-GDE-J5-HIGH-RETURN", [j5_end, W2, W3, A6, H0],
                      [55.0, 55.0, 55.0], 9.5, 7.2, "aluminum", "link5",
                      "V9 R55 high-return split conduit to J6 entry", "guide_channel")
guide_tube_poly_shell("RC-GDE-J5-HIGH-RETURN-LINER", [j5_end, W2, W3, A6, H0],
                      [55.0, 55.0, 55.0], 7.2, 5.8, "polymer", "link5",
                      "V9 high-return replaceable low-friction liner shell", "liner")
guide_support_saddle("RC-GSP-J5-HIGH-W2", J5_W2_PT, J5_W2_TAN, "aluminum", "link5",
                     "V9 candidate-2 high-return conduit support W2")
guide_support_saddle("RC-GSP-J5-HIGH-W3", J5_W3_PT, J5_W3_TAN, "aluminum", "link5",
                     "V9 candidate-2 high-return conduit support W3")
guide_support_saddle("RC-GSP-J5-HIGH-A6", J5_A6_PT, J5_A6_TAN, "aluminum", "link5",
                     "V9 candidate-2 J6-entry conduit support A6")

# J6 helix guide rings + brackets + clamps
for idx, ang in enumerate([180.0, 360.0, 540.0, 720.0]):
    along = j6_pitch * math.radians(ang - j6_start_ang) / (2.0*math.pi)
    c = (J6_ORIGIN[0] + along, J6_ORIGIN[1], J6_ORIGIN[2])
    robj = ring("RC-GDE-J6-RING-%d" % idx, c, (1, 0, 0), 66.0, 60.0, 4.0, "polymer", "link6",
                "J6 helix guide ring %d (open-sector, opening az 105-225 deg) at wrap angle %.0f deg" % (idx, ang))
    if robj is not None:
        a1_, a2_ = math.radians(105.0), math.radians(225.0)
        w0 = App.Vector(c[0] - 7.0, 0.0, c[2])
        w1 = App.Vector(c[0] - 7.0, 100.0 * math.cos(a1_), c[2] + 100.0 * math.sin(a1_))
        w2 = App.Vector(c[0] - 7.0, 100.0 * math.cos(a2_), c[2] + 100.0 * math.sin(a2_))
        wedge = Part.Face(Part.makePolygon([w0, w1, w2, w0])).extrude(App.Vector(14.0, 0.0, 0.0))
        robj.Shape = robj.Shape.cut(wedge)
        refresh_part_metrics("RC-GDE-J6-RING-%d" % idx)
box_at("RC-BRK-J6-GUIDE-A", (160.0, 0.0, 250.0), (8.0, 30.0, 6.0), "aluminum", "link6", "J6 guide ring support arm A")
box_at("RC-BRK-J6-GUIDE-B", (180.0, 0.0, 250.0), (8.0, 30.0, 6.0), "aluminum", "link6", "J6 guide ring support arm B")
clamp_saddle("RC-CLP-J6-FIX", H0, j6_entry_tan, "aluminum", "link5", "CM-J6-F fixed clamp at J6 helix entry")
clamp_saddle("RC-CLP-J6-MOV", j6_end, j6_exit_tan, "aluminum", "link6", "CM-J6-M moving clamp at J6 helix exit")

# wrist strain relief + split plate + connectors
clamp_saddle("RC-SR-WRIST", WR_SR_PT, WR_SR_TAN, "aluminum", "link6", "CF-WR-SR wrist strain relief clamp")
cone = Part.makeCone(8.0, 3.0, 25.0, fc_vec((237.0, -55.0, 241.7)), fc_vec((1, 0, 0)))
add_shape(cone, "RC-SR-WRIST-BOOT", "strain_relief_boot", "polymer", "link6", "wrist strain relief boot (elastomer candidate)")
box_at("RC-PLT-WRIST-SPLIT", PLATE, (10.0, 30.0, 20.0), "aluminum", "link6", "CF-WR-PL connector split plate")
box_at("RC-CONN-WR-D1", TAIL1, (12.0, 8.0, 6.0), "polymer", "link6", "CN-WR-D1 data connector block (Micro-D style candidate)")
box_at("RC-CONN-WR-P1", TAIL2, (14.0, 9.0, 7.0), "polymer", "link6", "CN-WR-P1 power/sensor connector block")

# --- reference B601 meshes (frozen, read-only, NOT exported) -----------------
mesh_report = []
try:
    import Mesh
    ref_group = doc.addObject("App::DocumentObjectGroup", "REF_FROZEN_B601")
    for ln in ["base_link", "link1", "link2", "link3", "link4", "link5", "link6"]:
        stl = os.path.join(MESH_DIR, ln + ".STL")
        if not os.path.isfile(stl):
            mesh_report.append({"link": ln, "status": "MISSING_FILE"})
            continue
        m = Mesh.read(stl)
        diag = math.sqrt((m.BoundBox.XMax-m.BoundBox.XMin)**2 + (m.BoundBox.YMax-m.BoundBox.YMin)**2 + (m.BoundBox.ZMax-m.BoundBox.ZMin)**2)
        scale_note = "as_is"
        if diag < 5.0:
            mat = App.Matrix(1000, 0, 0, 0, 0, 1000, 0, 0, 0, 0, 1000, 0, 0, 0, 0, 1)
            m.transform(mat)
            scale_note = "scaled_m_to_mm"
        mobj = doc.addObject("Mesh::Feature", "REF_" + ln)
        mobj.Mesh = m
        mobj.Placement = FRAMES[ln]
        mobj.Label = "REF_FROZEN_" + ln + " (read-only reference, not exported)"
        ref_group.addObject(mobj)
        mesh_report.append({"link": ln, "status": "imported", "scale": scale_note,
                            "bbox_diag_mm": diag * (1000.0 if scale_note == "scaled_m_to_mm" else 1.0)})
except Exception as exc:
    mesh_report.append({"status": "mesh_import_failed", "error": str(exc)})

# --- clamp / guide register --------------------------------------------------
CLAMPS = [
    ("CF-BUS-00", "bus", BUS00_PT, "FIXED", "2xM3 on RC-CHN-BUS-FT", "exact SEG-00 s=25 mm cable-axis station"),
    ("CF-BUS-01", "bus", BUS01_PT, "FIXED+STRAIN_RELIEF", "2xM3 on RC-CHN-BUS-FT", "exact SEG-00 s=50 mm cable-axis station"),
    ("CF-BUS-02", "base_link", BUS02_PT, "FIXED", "2xM3 on bracket arm", "exact SEG-00 s=130 mm cable-axis station"),
    ("CF-BUS-03", "base_link", BUS03_PT, "FIXED", "2xM3 on bracket arm", "exact SEG-00 s=210 mm cable-axis station"),
    ("CF-J1-REL-A1", "base_link", j1_relief_a1, "RELIEF_END", "2xM3 on V9 annulus cheek", "first-pass 190deg entry on actual helix"),
    ("CF-J1-REL-B1", "base_link", j1_relief_b1, "RELIEF_END", "2xM3 on V9 annulus cheek", "first-pass 100deg exit on actual helix"),
    ("CF-J1-REL-A2", "base_link", j1_relief_a2, "RELIEF_END", "2xM3 on V9 annulus cheek", "second-pass 190deg entry on actual helix"),
    ("CM-J1-M", "link1", j1_end, "MOVING", "2xM3 on RC-BRK-L1-01", "rotating clamp at annulus exit"),
    ("CF-L1-01", "link1", L1_PT, "FIXED", "2xM3 on RC-BRK-L1-01",
     "fixed clamp on link1 annulus exit stub"),
    ("CF-J2-F", "link1", T1_J2, "FIXED", "2xM3 on link1 derived pad", "J2 loop fixed clamp (link1 side)"),
    ("CM-J2-M", "link2", J2_MOV_PT, "MOVING", "2xM3 on RC-CHN-L2", "J2 loop moving clamp (link2 side)"),
    ("CF-L2-01", "link2", L2_01_PT, "FIXED", "2xM3 on RC-CHN-L2", "link2 channel fixed clamp"),
    ("CM-J3-M", "link2", J3_CARR_PT, "MOVING_CARRIER", "carriage RC-CAR-J3-CARRIAGE",
     "J3 carrier moving clamp, travel x -85..-195 (link2 frame)"),
    ("CF-L2-02", "link2", (-208.0, YC, 147.0), "FIXED", "2xM3 on RC-CHN-L2", "link2 channel end clamp"),
    ("CG-J3-S", "link2", (-255.0, YC, 147.0), "GUIDE_SADDLE", "4xM3 saddle bracket", "J3 guide saddle entry tangent"),
    ("CM-J3-HB", "link3", J3_HOST_BOUNDARY, "MOVING_HOST_BOUNDARY",
     "2xM3 on RC-CHN-L3", "J3 physical host-boundary clamp; downstream route is link3-only"),
    ("CF-L3-01", "link3", L3_01_PT, "FIXED", "2xM3 on RC-CHN-L3", "link3 channel fixed clamp"),
    ("CF-L3-02", "link3", L3_02_PT, "FIXED", "2xM3 on RC-CHN-L3", "link3 channel fixed clamp"),
    ("CF-J4-F", "link3", J4_FIX_PT, "FIXED", "2xM3 on removable Plane-A bracket; torque HOLD", "V9 fixed Plane-A clamp before passive free leg"),
    ("CG-J4-CAR", "link3", J4_CARRIER_C0, "GUIDE_SADDLE", "carriage split saddle interface; M3 definition HOLD", "V9 q4-generated passive carriage/saddle datum at q4=0"),
    ("CM-J4-M", "link4", J4_HOST_BOUNDARY, "MOVING_HOST_BOUNDARY", "2xM3 on removable Plane-B bracket; torque HOLD", "V9 physical host-boundary clamp on link4"),
    ("CF-L4-01", "link4", l4_clamp_pt, "FIXED", "2xM3 on external split conduit; torque HOLD", "link4 external turn-1 clamp"),
    ("GS-L4-HIGH-E1", "link4", L4_E1_PT, "GUIDE_SUPPORT", "2xM3 on V9 high-bypass guide", "conduit-axis support E1; not a cable clamp"),
    ("GS-L4-HIGH-E2", "link4", L4_E2_PT, "GUIDE_SUPPORT", "2xM3 on V9 high-bypass guide", "conduit-axis support E2; not a cable clamp"),
    ("CF-J5-F", "link4", T1_J5, "FIXED", "2xM3 on V9 high-bypass guide", "V9 external J5 wrap entry fixed clamp"),
    ("CM-J5-M", "link5", j5_end, "MOVING", "2xM3 on link5 derived pad", "J5 wrap exit moving clamp"),
    ("GS-J5-HIGH-W2", "link5", J5_W2_PT, "GUIDE_SUPPORT", "2xM3 on V9 high-return guide", "conduit-axis support W2; not a cable clamp"),
    ("GS-J5-HIGH-W3", "link5", J5_W3_PT, "GUIDE_SUPPORT", "2xM3 on V9 high-return guide", "conduit-axis support W3; not a cable clamp"),
    ("GS-J5-HIGH-A6", "link5", J5_A6_PT, "GUIDE_SUPPORT", "2xM3 on V9 high-return guide", "conduit-axis support A6; not a cable clamp"),
    ("CM-J6-F", "link5", H0, "FIXED", "2xM3 on link5 end pad", "J6 helix entry fixed clamp"),
    ("CM-J6-M", "link6", j6_end, "MOVING", "2xM3 on link6 derived pad", "J6 helix exit moving clamp"),
    ("CF-WR-SR", "link6", WR_SR_PT, "STRAIN_RELIEF", "2xM3 on link6 wrist pad", "wrist strain relief"),
    ("CF-WR-PL", "link6", PLATE, "CONNECTOR_PLATE", "4xM3 on RC-PLT-WRIST-SPLIT", "wrist connector split plate; not a cable clamp"),
]

CAD_PART_BY_CLAMP_ID = {
    "CF-BUS-00": "RC-CLP-BUS-HN01", "CF-BUS-01": "RC-CLP-BUS-HN02",
    "CF-BUS-02": "RC-CLP-BUS-HN03", "CF-BUS-03": "RC-CLP-BUS-RISER",
    "CF-J1-REL-A1": "RC-CLP-J1-RELIEF-A1", "CF-J1-REL-B1": "RC-CLP-J1-RELIEF-B1",
    "CF-J1-REL-A2": "RC-CLP-J1-RELIEF-A2", "CM-J1-M": "RC-CLP-J1-MOV",
    "CF-L1-01": "RC-CLP-L1-01", "CF-J2-F": "RC-CLP-J2-FIX",
    "CM-J2-M": "RC-CLP-J2-MOV", "CF-L2-01": "RC-CLP-L2-01",
    "CM-J3-M": "RC-CLP-J3-MOV", "CF-L2-02": "RC-CLP-L2-02",
    "CM-J3-HB": "RC-CLP-J3-HOST-BOUNDARY",
    "CF-L3-01": "RC-CLP-L3-01", "CF-L3-02": "RC-CLP-L3-02",
    "CF-J4-F": "RC-CLP-J4-FIX", "CM-J4-M": "RC-CLP-J4-MOV",
    "CG-J4-CAR": "RC-GDE-J4-CARRIER-SADDLE",
    "CF-L4-01": "RC-CLP-L4-01", "GS-L4-HIGH-E1": "RC-GSP-L4-HIGH-E1",
    "GS-L4-HIGH-E2": "RC-GSP-L4-HIGH-E2", "CF-J5-F": "RC-CLP-J5-FIX",
    "CM-J5-M": "RC-CLP-J5-MOV", "GS-J5-HIGH-W2": "RC-GSP-J5-HIGH-W2",
    "GS-J5-HIGH-W3": "RC-GSP-J5-HIGH-W3", "GS-J5-HIGH-A6": "RC-GSP-J5-HIGH-A6",
    "CM-J6-F": "RC-CLP-J6-FIX", "CM-J6-M": "RC-CLP-J6-MOV",
    "CF-WR-SR": "RC-SR-WRIST", "CF-WR-PL": "RC-PLT-WRIST-SPLIT",
    "CG-J3-S": "RC-GDE-J3-SADDLE",
}

with open(OUT_CLAMPS, "w", newline="") as f:
    f.write("clamp_id,cad_part_name,host_link,type,frame,x_mm,y_mm,z_mm,axis_dx,axis_dy,axis_dz,bore_radius_mm,retained_radius_mm,install_allowance_mm,colocation_budget_mm,fastener_interface,note\n")
    for cid, host, pw, ctype, fastener, note in CLAMPS:
        local = world_to_host(pw, host) if host in FRAMES else pw
        frame_name = "S" if host == "bus" else host + "_frame"
        cad_part = CAD_PART_BY_CLAMP_ID[cid]
        axis_world = part_axis_registry.get(cad_part)
        axis = (world_dir_to_host(axis_world, host)
                if axis_world is not None and host in FRAMES else axis_world)
        if ctype == "GUIDE_SUPPORT":
            bore_r = part_bore_registry.get(cad_part, P["guide_support_bore_r_mm"])
            retained_r = P["guide_outer_r_mm"]
            install = P["clamp_install_allow_mm"]
        elif ctype in ("CONNECTOR_PLATE", "GUIDE_SADDLE"):
            bore_r = retained_r = install = None
        else:
            bore_r = part_bore_registry.get(cad_part, P["clamp_bore_r_mm"])
            retained_r = P["bundle_r_upper"]
            install = P["clamp_install_allow_mm"]
        budget = None if bore_r is None else bore_r-retained_r-install
        nums = ["" if x is None else "%.3f" % x for x in (bore_r, retained_r, install, budget)]
        axis_nums = ["" if axis is None else "%.9f" % x for x in (axis or (0, 0, 0))]
        f.write("%s,%s,%s,%s,%s,%.3f,%.3f,%.3f,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (
            cid, cad_part, host, ctype, frame_name, local[0], local[1], local[2],
            axis_nums[0], axis_nums[1], axis_nums[2], nums[0], nums[1], nums[2], nums[3],
            fastener, note))

# --- mass delta candidates ----------------------------------------------------
mass_by_link = {}
for rp in receipt_parts:
    if not rp.get("valid"):
        continue
    host = rp.get("host_link", "bus")
    if rp.get("material") == "bundle":
        continue
    mass_by_link.setdefault(host, {"hardware_g": 0.0, "bundle_g": 0.0})
    mass_by_link[host]["hardware_g"] += rp.get("mass_g_estimate") or 0.0
for srep in segment_reports:
    if not bundle_solids.get(srep["segment"]):
        continue
    m = srep["path_length_mm"] / 1000.0 * P["linear_density_g_m"]
    hosts = srep["host_links"]
    share = m / len(hosts)
    for h in hosts:
        mass_by_link.setdefault(h, {"hardware_g": 0.0, "bundle_g": 0.0})
        mass_by_link[h]["bundle_g"] += share

tot_h = sum(e["hardware_g"] for e in mass_by_link.values())
tot_b = sum(e["bundle_g"] for e in mass_by_link.values())
mass_delta_doc = {
    "schema": "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V9",
    "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
    "authority": "DESIGN_CANDIDATE mass registration only; propagation to dynamics SSOT is RC-5 scope and is FORBIDDEN at this stage",
    "density_assumptions": {
        "aluminum_6061_T6_g_per_mm3": P["rho_alu_g_mm3"],
        "polymer_igumid_iglidur_g_per_mm3": P["rho_poly_g_mm3"],
        "note_polymer": "DESIGN_CANDIDATE estimate; igus datasheet confirmation pending",
        "bundle_linear_density_g_per_m": P["linear_density_g_m"],
        "note_bundle": "PROVISIONAL_DERIVED from registry P09 bounded [56.5, 72.5] g/m",
    },
    "mass_delta_by_link": [
        {"host_link": h, "hardware_g": round(e["hardware_g"], 2), "bundle_g": round(e["bundle_g"], 2),
         "delta_total_g": round(e["hardware_g"] + e["bundle_g"], 2), "authority": "DESIGN_CANDIDATE"}
        for h, e in sorted(mass_by_link.items())
    ],
    "totals": {"hardware_g": round(tot_h, 2), "bundle_g": round(tot_b, 2),
               "delta_total_g": round(tot_h + tot_b, 2), "delta_total_kg": round((tot_h + tot_b)/1000.0, 4)},
}
with open(OUT_MASS, "w") as f:
    json.dump(mass_delta_doc, f, indent=2)

# --- centerline JSON -----------------------------------------------------------
def section_to_json(sec):
    kind = sec[0]
    if kind == "poly":
        return {"type": "polyline", "points": [[round(c, 3) for c in p] for p in sec[1]],
                "corner_fillet_radii_mm": sec[2]}
    if kind == "arc":
        c, n, e1, e2, R, a0, sw = sec[1]
        return {"type": "arc", "center": [round(v, 3) for v in c], "normal": list(n),
                "basis_e1": list(e1), "basis_e2": list(e2), "radius_mm": R,
                "start_angle_deg": round(a0, 3), "sweep_deg": round(sw, 3)}
    if kind == "helix":
        o, ax, e1, e2, R, pitch, a0, sw = sec[1]
        return {"type": "helix", "origin": [round(v, 3) for v in o], "axis": list(ax),
                "basis_e1": list(e1), "basis_e2": list(e2), "radius_mm": R, "pitch_mm_per_turn": pitch,
                "start_angle_deg": round(a0, 3), "sweep_deg": round(sw, 3)}
    return {"type": "unknown"}

tot_req = 0.0
tot_cap = 0.0
def helix_span_length_mm(radius_mm, pitch_mm_per_turn, delta_angle_deg):
    da = math.radians(abs(delta_angle_deg))
    return math.sqrt((radius_mm*da)**2 +
                     (pitch_mm_per_turn*da/(2.0*math.pi))**2)

_d3_span_first = helix_span_length_mm(J1_R, j1_pitch,
                                      J1_RELIEF_B1_ANGLE-J1_RELIEF_A1_ANGLE)
_d3_span_second = helix_span_length_mm(J1_R, j1_pitch,
                                       j1_end_ang-J1_RELIEF_A2_ANGLE)
centerline_doc = {
    "schema": "B601_ROUTE_C_HARNESS_CENTERLINE_V9",
    "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
    "design_candidate_sequence": 1,
    "owner_authority": {"decision_id": "ODR-58",
                        "input_manifest_sha256": INPUT_MANIFEST_SHA256},
    "architecture": "SEGMENTED_CONSTRAINED_MOVING_CARRIER__LOW_PROFILE_DUAL_PLANE_SADDLE",
    "frame_convention": {
        "root": "A0 = B601 base_link frame (accepted URDF), mm",
        "host_link_frames": "accepted URDF link frames at q=0; joint origins/axes per accepted URDF sha256 1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
        "bus_stations": "S-frame stations mapped through mount semantics x=208.0 mm / 25 deg clock about +X_S (FK_SWEEP_V2 single semantics, not averaged)",
        "bundle_od_mm": P["bundle_od_mm"],
        "min_bend_radius_mm": P["r_path_min"],
    },
    "segments": [],
    "carrier": {
        "id": "J3-CARRIER",
        "type": "festoon moving guide (igus E2.10 class)",
        "travel_mm": P["carrier_travel_mm"],
        "travel_zone_world_x_mm": [-195.0, -85.0],
        "hard_stop_world_x_mm": [-195.0, -85.0],
        "take_up_rule": "cable take-up = 2 x carriage travel",
        "pitch_mm": P["carrier_pitch_mm"],
        "cross_section_inner_mm": P["carrier_cross_mm"],
    },
    "j4_carrier": {
        "id": "J4-SEGMENTED-PASSIVE-CARRIER",
        "type": "passive linear carriage plus oblique 180deg split-shell saddle",
        "motion_authority": "q4-generated kinematic design law; no active robot DOF",
        "q4_law": "x_C_mm = 160.0 + 27.5*(q4_rad + 0.15)",
        "q4_hardware_limits_rad": [-1.87, 1.57],
        "center_x_at_limits_mm": [112.7, 207.3],
        "hard_stop_center_x_mm": [110.0, 210.0],
        "hard_stop_margin_each_end_mm": 2.7,
        "physical_travel_mm": P["j4_carrier_hard_stop_travel_mm"],
        "mission_required_travel_mm": 94.6,
        "take_up_rule": "cable take-up capacity = 2 x physical carriage travel",
        "take_up_capacity_mm": 2.0*P["j4_carrier_hard_stop_travel_mm"],
        "take_up_required_mm": 55.0*P["joint_ranges_rad"]["J4"],
        "saddle_radius_mm": J4_CARRIER_R,
        "plane_A_y_mm": 104.0,
        "plane_B_y_mm": 58.0,
        "single_bundle_not_branches": True,
        "bundle_upper_diameter_mm": P["bundle_od_upper_mm"],
        "carrier_clear_section_mm": [12.0, 12.0],
        "carrier_outer_section_mm": [16.0, 14.0],
        "dynamic_evaluator_required": True,
    },
    "d3_open_sector_retention": {
        "relief_sector_deg": [100.0, 190.0],
        "p13_max_spacing_mm": 150.0,
        "required_retainer_ids": ["CF-J1-REL-A1", "CF-J1-REL-B1",
                                   "CF-J1-REL-A2", "CM-J1-M"],
        "open_passages": [
            {"id": "PASSAGE_1_FULL", "entry_unwrapped_angle_deg": J1_RELIEF_A1_ANGLE,
             "exit_unwrapped_angle_deg": J1_RELIEF_B1_ANGLE,
             "entry_z_mm": j1_relief_a1[2], "exit_z_mm": j1_relief_b1[2],
             "free_span_mm": round(_d3_span_first, 3),
             "end_retainers": ["CF-J1-REL-A1", "CF-J1-REL-B1"]},
            {"id": "PASSAGE_2_PARTIAL", "entry_unwrapped_angle_deg": J1_RELIEF_A2_ANGLE,
             "exit_unwrapped_angle_deg": j1_end_ang,
             "entry_z_mm": j1_relief_a2[2], "exit_z_mm": j1_end[2],
             "free_span_mm": round(_d3_span_second, 3),
             "end_retainers": ["CF-J1-REL-A2", "CM-J1-M"]}
        ],
        "authority": "PROVISIONAL_DERIVED from P13 [55,150] mm and exact candidate helix; retention/fretting qualification remains HOLD"
    },
    "take_up_summary": {},
}
for seg, srep in zip(SEGMENTS, segment_reports):
    centerline_doc["segments"].append({
        "id": seg["id"],
        "host_links": seg["host_links"],
        "sections": [section_to_json(sec) for sec in seg["sections"]],
        "min_bend_radius_rule_mm": P["r_path_min"],
        "path_length_mm": round(srep["path_length_mm"], 3),
        "take_up_required_mm": round(seg["take_up_required_mm"], 3),
        "take_up_capacity_mm": round(seg["take_up_capacity_mm"], 3),
        "note": seg["note"],
    })
    tot_req += seg["take_up_required_mm"]
    tot_cap += seg["take_up_capacity_mm"]
centerline_doc["take_up_summary"] = {
    "required_total_mm": round(tot_req, 3),
    "capacity_total_mm": round(tot_cap, 3),
    "margin_mm": round(tot_cap - tot_req, 3),
    "margin_percent_of_required": round(100.0*(tot_cap - tot_req)/tot_req, 2) if tot_req > 0 else None,
}
with open(OUT_CENTERLINE, "w") as f:
    json.dump(centerline_doc, f, indent=2)

# --- save FCStd + export STEP ---------------------------------------------------
doc.saveAs(OUT_FCSTD)
export_objs = [part_objects[r["name"]] for r in part_registry if r["name"] in part_objects]
try:
    import Import
    Import.export(export_objs, OUT_STEP)
    step_status = "exported"
except Exception as exc:
    step_status = "export_failed: %s" % exc

# --- build receipt ----------------------------------------------------------------
all_violations = []
all_adjustments = []
for srep in segment_reports:
    all_violations.extend(srep["violations"])
    all_adjustments.extend(srep.get("adjustments", []))
min_bend_all = [s["min_bend_radius_mm"] for s in segment_reports if s["min_bend_radius_mm"] is not None]
receipt = {
    "schema": "B601_ROUTE_C_BUILD_RECEIPT_V9",
    "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
    "design_candidate_sequence": 1,
    "architecture": "SEGMENTED_CONSTRAINED_MOVING_CARRIER__LOW_PROFILE_DUAL_PLANE_SADDLE",
    "supersedes_candidate": "V8_CANDIDATE_3_REJECTED (immutable negative history)",
    "input_manifest": {"path": INPUT_MANIFEST,
                       "sha256": _manifest_sha,
                       "expected_sha256": INPUT_MANIFEST_SHA256,
                       "match": _manifest_sha == INPUT_MANIFEST_SHA256},
    "authority": "DESIGN_CANDIDATE; review_status PENDING_OWNER_REVIEW; next_stage_authorized false; release_credit false",
    "outputs": {"fcstd": OUT_FCSTD, "step": OUT_STEP, "step_status": step_status,
                "centerline_json": OUT_CENTERLINE, "clamp_register_csv": OUT_CLAMPS,
                "mass_delta_json": OUT_MASS},
    "part_count_exported": len(export_objs),
    "parts": receipt_parts,
    "segment_reports": segment_reports,
    "min_bend_radius_mm_overall": min(min_bend_all) if min_bend_all else None,
    "r_path_min_required_mm": P["r_path_min"],
    "violations": all_violations,
    "bounded_geometry_adjustments": all_adjustments,
    "mesh_reference_report": mesh_report,
    "take_up_summary": centerline_doc["take_up_summary"],
    "mass_delta_totals": mass_delta_doc["totals"],
    "accepted_urdf_unchanged": True,
    "frozen_assets_modified": False,
    "v9_primary_changes": {
        "J4_topology": "old same-plane near-full-circle mandrel and narrow L4 channel removed; storage moved to an external passive linear carriage",
        "dual_plane": "one continuous bundle uses Plane A y=104 then Plane B y=58 through one oblique 180deg R55.036 saddle",
        "host_boundary": "fixed link3 transport terminates before carrier; CM-J4-M at Plane-B return is the link4 host boundary",
        "passive_motion": "x_C_mm=160+27.5*(q4+0.15); hard stops 110..210; no new active or URDF DOF",
        "physical_realization": "16x14 outer / 12x12 clear articulated carrier links plus non-overlapping aluminum and polymer guide shells",
        "preserved": "V9 does not alter accepted URDF, vendor links, M3R, Gripper R1, Solar R2, Full-Flex authority or Route-B/V8 evidence",
        "qualification_boundary": "M3 definition/torque, installed-bundle restoring torque and space-environment qualification remain explicit holds"
    },
}
with open(OUT_RECEIPT, "w") as f:
    json.dump(receipt, f, indent=2)

print("=== B601 Route-C build complete ===")
print("parts exported: %d" % len(export_objs))
print("step: %s" % step_status)
print("min bend radius: %s" % str(receipt["min_bend_radius_mm_overall"]))
print("violations: %d" % len(all_violations))
for v in all_violations:
    print("  VIOLATION: %s" % v)
print("take-up: required %.1f capacity %.1f margin %.1f mm" % (
    tot_req, tot_cap, tot_cap - tot_req))
print("mass delta total: %.1f g" % (tot_h + tot_b))
