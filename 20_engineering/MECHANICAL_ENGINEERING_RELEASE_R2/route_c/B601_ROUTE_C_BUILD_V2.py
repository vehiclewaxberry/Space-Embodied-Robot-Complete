# B601 Route-C Guided Dress Pack V2 - headless FreeCAD build script (derived from V1 by route_c_v2_derive_build.py)
# Stage RC-3 of R2 terminal dual-lane closure, lane A1 (Route-C task-level guided harness).
# Authority: ODR-42 / ODR-52 / ODR-53 / ODR-54. All geometry is DESIGN_CANDIDATE.
# Run: FreeCADCmd.exe B601_ROUTE_C_BUILD_V1.py
# Outputs (same directory): FCStd, STEP, centerline JSON, clamp register CSV,
# mass-delta candidates JSON, build receipt JSON.

import os
import json
import math

import FreeCAD as App
import Part

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_FCSTD = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V2.FCStd")
OUT_STEP = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V2.step")
OUT_CENTERLINE = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_HARNESS_CENTERLINE_V2.json")
OUT_CLAMPS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V2.csv")
OUT_MASS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V2.json")
OUT_RECEIPT = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_BUILD_RECEIPT_V2.json")

REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
MESH_DIR = os.path.join(REPO_ROOT, "cad", "spacecraft_layout", "arm_b601_v1", "meshes_b601_gripper")

P = {
    "bundle_od_mm": 9.0,
    "bundle_r": 4.5,
    "channel_clear_mm": 12.0,
    "r_path_min": 55.0,
    "carrier_travel_mm": 110.0,
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
        rep.violations.append(
            "%s corner %d: fillet radius clamped %.2f -> %.2f mm (theta %.1f deg, legs %.2f/%.2f)"
            % (rep.seg_id, corner_idx, R, R_eff, theta, l1, l2))
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
HN00 = (-29.58, -63.44, -60.41)
HN01 = (-29.58, -63.44, -39.41)
HN02 = (-29.58, -63.44, -18.41)
HN03 = (-19.02, -40.78, 4.59)
C1 = (-29.58, -63.44, -8.0)
C2 = (-22.08, -65.94, 15.73)
C2B = (-9.06, -70.24, 30.0)
JV = (14.56, -77.98, 50.0)
KP = (14.56, -100.0, 126.0)
RISER_DIR = v_norm(v_sub(KP, HN02))
RISER_MID = v_add(HN02, v_mul(RISER_DIR, 75.9))
# J1 annulus: center z=126, R60, CW coil 1.2 turns, pitch -12 (rising)
J1_C = (-0.084, 0.0, 126.0)
j1_t1_2d, j1_start_ang = tangent_point_from_external((J1_C[0], J1_C[1]), 60.0, (KP[0], KP[1]), -1)
T1_COIL = (j1_t1_2d[0], j1_t1_2d[1], 126.0)
j1_sweep = -432.0
j1_end_ang = j1_start_ang + j1_sweep
j1_pitch = -12.0
j1_end_z = 126.0 + j1_pitch * math.radians(j1_sweep) / (2.0*math.pi)
j1_end = circle_point(J1_C, (1, 0, 0), (0, 1, 0), 60.0, j1_end_ang)
j1_end = (j1_end[0], j1_end[1], j1_end_z)
j1_exit_tan = helix_tangent((0, 0, 1), (1, 0, 0), (0, 1, 0), 60.0, j1_pitch, j1_end_ang, -1)
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

# J4 loop: circle C=(5, YC, 135), R50, CW from top (90 deg), sweep -315
J4_C = (5.0, YC, 135.0)
j4_start_ang = 90.0
j4_sweep = -315.0
j4_end_ang = j4_start_ang + j4_sweep
j4_end = circle_point(J4_C, (1, 0, 0), (0, 0, 1), 55.0, j4_end_ang)
j4_exit_tan = tangent_dir_circle((1, 0, 0), (0, 0, 1), j4_end_ang, -1)
s_j4 = (195.1 - j4_end[2]) / j4_exit_tan[2]
M4 = v_add(j4_end, v_mul(j4_exit_tan, s_j4))
M4 = (M4[0], YC, 195.1)
K2 = (115.0, YC, 210.0)

# J5 wrap: circle C=(76.908, 0, 210), R50, CW, entry = tangent from K2, sweep -185
J5_C = (76.908, 0.0, 210.0)
j5_t1_xy, j5_start_ang = tangent_point_from_external((J5_C[0], J5_C[1]), 55.0, (K2[0], K2[1]), -1)
T1_J5 = (j5_t1_xy[0], j5_t1_xy[1], 210.0)
j5_sweep = -185.0
j5_end_ang = j5_start_ang + j5_sweep
j5_end = circle_point(J5_C, (1, 0, 0), (0, 1, 0), 55.0, j5_end_ang)
j5_exit_tan = tangent_dir_circle((1, 0, 0), (0, 1, 0), j5_end_ang, -1)
W1 = v_add(j5_end, v_mul(j5_exit_tan, 70.0))
W2 = v_add(W1, v_mul(v_norm(v_sub((73.11, 89.04, 227.3), W1)), 130.0))

# J6 helix: axis +x through (170, 0, 191.7), R50, pitch 20, start 180 deg, sweep +630
J6_ORIGIN = (150.0, 0.0, 191.7)
j6_pitch = 20.0
j6_start_ang = 180.0
j6_sweep = 630.0
j6_end_ang = j6_start_ang + j6_sweep
H0 = circle_point(J6_ORIGIN, (0, 1, 0), (0, 0, 1), 55.0, j6_start_ang)
j6_entry_tan = helix_tangent((1, 0, 0), (0, 1, 0), (0, 0, 1), 55.0, j6_pitch, j6_start_ang, +1)
A6 = v_sub(H0, v_mul(j6_entry_tan, 110.0))
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
        "sections": [("poly", [HN00, HN01, HN02, KP, T1_COIL],
                      [0.0, 55.0, 54.0])],
        "take_up_required_mm": 0.0,
        "take_up_capacity_mm": 0.0,
        "note": "static bus feedthrough channel, gentle riser flare to annulus tangent entry (annulus at z=126)",
    },
    {
        "id": "SEG-01_J1_ANNULAR_SERVICE_LOOP",
        "host_links": ["base_link", "link1"],
        "sections": [
            ("helix", (J1_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 60.0, j1_pitch, j1_start_ang, j1_sweep)),
            ("poly", [j1_end, P_J1OUT, T1_J2], [55.0]),
        ],
        "take_up_required_mm": 60.0*5.6,
        "take_up_capacity_mm": 60.0*math.radians(abs(j1_sweep)),
        "note": "protected annular service loop: 1.2-turn CW coil R60 pitch -12 in annular channel; tangent exit to J2",
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
            ("poly", [j3_end, M3, F4, T1_J4], [55.0, 55.0, 0.0]),
        ],
        "take_up_required_mm": 65.0*3.14,
        "take_up_capacity_mm": 2.0*P["carrier_travel_mm"],
        "note": "festoon take-up via moving carriage (2x110=220) plus R63 guide saddle wrap CCW 200 deg",
    },
    {
        "id": "SEG-04_J4_LOOP_LINK4_CHANNEL_RISER",
        "host_links": ["link3", "link4"],
        "sections": [
            ("arc", (J4_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j4_start_ang, j4_sweep)),
            ("poly", [j4_end, M4, K2, T1_J5], [55.0, 55.0, 55.0]),
        ],
        "take_up_required_mm": 55.0*3.44,
        "take_up_capacity_mm": 55.0*math.radians(abs(j4_sweep)),
        "note": "joint-local omega loop R50 CW 315 deg, tilted link4 channel rising to J5 wrap plane z=210",
    },
    {
        "id": "SEG-05_J5_WRIST_WRAP",
        "host_links": ["link4", "link5"],
        "sections": [
            ("arc", (J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 55.0, j5_start_ang, j5_sweep)),
            ("poly", [j5_end, W1, W2, A6, H0], [55.0, 55.0, 55.0]),
        ],
        "take_up_required_mm": 55.0*3.14,
        "take_up_capacity_mm": 55.0*math.radians(abs(j5_sweep)),
        "note": "fixed-curvature wrist wrap R50 CW 185 deg in plane z=210, gentle descent to J6 helix entry",
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
doc = App.newDocument("B601_ROUTE_C_GUIDED_DRESS_PACK_V2")
part_registry = []
part_objects = {}
receipt_parts = []

def add_shape(shape, name, kind, material, host_link, role):
    if shape is None:
        receipt_parts.append({"name": name, "valid": False, "error": "no shape"})
        return None
    internal = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in name)
    obj = doc.addObject("Part::Feature", internal)
    obj.Label = name
    obj.Shape = shape
    part_objects[name] = obj
    part_registry.append({"name": name, "kind": kind, "material": material,
                          "host_link": host_link, "role": role})
    vol = shape.Volume if shape.isValid() else 0.0
    mass_g = vol * DENS[material] if material in DENS else None
    receipt_parts.append({"name": name, "valid": bool(shape.isValid()), "volume_mm3": vol,
                          "material": material, "mass_g_estimate": mass_g,
                          "host_link": host_link, "kind": kind, "role": role})
    return obj

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

def clamp_saddle(name, pt, direction, material, host_link, role, width=14.0):
    d = v_norm(direction)
    ref = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (0.0, 1.0, 0.0)
    yd = v_norm(v_cross(d, ref))
    oriented_box(name, pt, (width, 18.0, 18.0), d, yd, material, host_link, role, kind="clamp")
    bore = Part.makeCylinder(5.0, width+4.0, fc_vec(v_sub(pt, v_mul(d, width/2.0+2.0))), fc_vec(d))
    obj = part_objects.get(name)
    if obj is not None:
        obj.Shape = obj.Shape.cut(bore)
    return obj

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

# --- bundle tubes per segment ----------------------------------------------
segment_reports = []
bundle_solids = {}
for seg in SEGMENTS:
    rep = SegReport(seg["id"])
    wire = build_segment_wire(seg["sections"], rep)
    shape, method = sweep_tube(wire, P["bundle_r"], seg["id"])
    name = "RC-BUNDLE-" + seg["id"].replace("_", "-")
    add_shape(shape, name, "bundle_envelope", "bundle", seg["host_links"][-1],
              "harness bundle envelope OD %.1f mm" % P["bundle_od_mm"])
    bundle_solids[seg["id"]] = shape
    segment_reports.append({
        "segment": seg["id"], "host_links": seg["host_links"],
        "path_length_mm": wire.Length,
        "min_bend_radius_mm": (None if rep.min_bend_radius > 1e8 else rep.min_bend_radius),
        "take_up_required_mm": seg["take_up_required_mm"],
        "take_up_capacity_mm": seg["take_up_capacity_mm"],
        "corners": rep.corners, "junctions": rep.junctions, "violations": rep.violations,
        "sweep_method": method,
    })

# --- hardware ---------------------------------------------------------------
# bus feedthrough channel + flange + connector + clamps
channel_section("RC-CHN-BUS-FT", (-29.58, -63.44, -62.0), (-29.58, -63.44, -6.0),
                12.0, 12.0, "aluminum", "bus", "bus passage feedthrough channel (HN-00..C1)")
box_at("RC-BRK-BUS-FLANGE", (-29.58, -63.44, -60.0), (30.0, 30.0, 4.0), "aluminum", "bus",
       "feedthrough mounting flange at HN-00, fasteners 4xM3")
box_at("RC-PLT-BUS-CONN", (-29.58, -63.44, -58.0), (26.0, 8.0, 6.0), "polymer", "bus",
       "CN-BUS-00 connector plate at HN-00 (Micro-D style candidate)")
clamp_saddle("RC-CLP-BUS-HN01", HN01, (0, 0, 1), "aluminum", "bus", "CF-BUS-00 fixed clamp at HN-01")
clamp_saddle("RC-CLP-BUS-HN02", HN02, (0, 0, 1), "aluminum", "bus", "CF-BUS-01 fixed clamp + strain relief at HN-02")

# base collar bracket + HN-03 connector plate + riser clamps
ring("RC-BRK-BASE-COLLAR", (0.0, 0.0, 6.0), (0, 0, 1), 52.0, 44.5, 12.0, "aluminum", "base_link",
     "derived collar clamp ring on base_link collar (no donor modification), fasteners 8xM3 at R45.25 pattern face")
box_at("RC-PLT-BASE-CONN", HN03, (26.0, 8.0, 10.0), "polymer", "base_link",
       "CN-BASE-00 connector plate at HN-03 station")
clamp_saddle("RC-CLP-BUS-HN03", (-25.60, -64.77, 4.59), v_norm(v_sub(C2, C1)), "aluminum", "base_link",
             "CF-BUS-02 route clamp with bracket arm to CN-BASE-00 at HN-03")
clamp_saddle("RC-CLP-BUS-RISER", RISER_MID, RISER_DIR, "aluminum", "base_link",
             "CF-BUS-03 riser clamp, bracket arm to collar ring at HN-04 station")
oriented_box("RC-BRK-J1-RISER", RISER_MID, (8.0, 12.0, 140.0), RISER_DIR, (0, 1, 0),
             "aluminum", "base_link", "riser guide bracket along vertical riser JV->KP", kind="bracket")

# J1 annular channel (cheeks + outer wall + liner + entry notch)
ring("RC-GDE-J1-ANNULUS-LOW", (J1_C[0], J1_C[1], J1_C[2]-1.5), (0, 0, 1), 68.0, 52.0, 3.0, "aluminum", "base_link",
     "annular service-loop channel lower cheek")
ring("RC-GDE-J1-ANNULUS-UP", (J1_C[0], J1_C[1], J1_C[2]+16.0), (0, 0, 1), 68.0, 52.0, 3.0, "aluminum", "base_link",
     "annular service-loop channel upper cheek")
wall = ring("RC-GDE-J1-ANNULUS-WALL", (J1_C[0], J1_C[1], J1_C[2]+7.25), (0, 0, 1), 71.0, 68.0, 17.5, "aluminum", "base_link",
            "annulus outer containment wall with entry notch")
ring("RC-GDE-J1-LINER", (J1_C[0], J1_C[1], J1_C[2]+1.6), (0, 0, 1), 63.0, 57.0, 1.0, "polymer", "base_link",
     "annulus liner band (iglidur candidate)")
if wall is not None:
    notch_center = v_add(T1_COIL, v_mul(v_norm(v_sub(T1_COIL, KP)), -12.0))
    notch = Part.makeBox(22.0, 22.0, 22.0, fc_vec(v_sub(notch_center, (11.0, 11.0, 11.0))))
    wall.Shape = wall.Shape.cut(notch)
clamp_saddle("RC-CLP-J1-MOV", j1_end, j1_exit_tan, "aluminum", "link1", "CM-J1-M rotating clamp on link1 at annulus exit")
clamp_saddle("RC-CLP-L1-01", v_add(j1_end, v_mul(j1_exit_tan, 30.0)), j1_exit_tan, "aluminum", "link1",
             "CF-L1-01 fixed clamp on link1 annulus exit stub")
box_at("RC-BRK-L1-01", (j1_end[0]+10.0, j1_end[1]+10.0, j1_end[2]-12.0), (20.0, 20.0, 6.0), "aluminum", "link1",
       "link1 derived bracket pad for CM-J1-M / CF-L1-01 (2xM3 each)")

# J2 mandrel + liner + clamps
guide_tube("RC-GDE-J2-MANDREL", J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j2_start_ang, j2_sweep, 6.0,
           "aluminum", "link1", "J2 U-loop guide mandrel R50 270 deg", "guide_mandrel")
guide_tube("RC-GDE-J2-MANDREL-LINER", J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j2_start_ang, j2_sweep, 7.5,
           "polymer", "link1", "J2 mandrel liner sleeve (iglidur candidate)", "liner")
clamp_saddle("RC-CLP-J2-FIX", T1_J2, tangent_dir_circle((1, 0, 0), (0, 0, 1), j2_start_ang, -1), "aluminum", "link1",
             "CF-J2-F fixed clamp on link1 side of J2 loop")
clamp_saddle("RC-CLP-J2-MOV", M2, (-1, 0, 0), "aluminum", "link2", "CM-J2-M moving clamp on link2 side of J2 loop")

# link2 channel + carrier track + carriage + e-chain links
channel_section("RC-CHN-L2", M2, (-208.0, YC, 147.0), 12.0, 12.0, "aluminum", "link2",
                "link2 fixed channel incl. carrier straight section")
clamp_saddle("RC-CLP-L2-01", (-80.0, YC, 147.0), (-1, 0, 0), "aluminum", "link2", "CF-L2-01 fixed clamp")
clamp_saddle("RC-CLP-L2-02", (-208.0, YC, 147.0), (-1, 0, 0), "aluminum", "link2", "CF-L2-02 fixed clamp at channel end")
box_at("RC-TRK-J3-RAIL", (-140.0, YC+10.0, 138.0), (120.0, 6.0, 4.0), "aluminum", "link2",
       "J3 carrier track rail, travel zone x -85..-195")
box_at("RC-TRK-J3-STOP-A", (-85.0, YC+10.0, 141.0), (4.0, 8.0, 10.0), "aluminum", "link2", "carrier hard stop A (x=-85)")
box_at("RC-TRK-J3-STOP-B", (-195.0, YC+10.0, 141.0), (4.0, 8.0, 10.0), "aluminum", "link2", "carrier hard stop B (x=-195)")
oriented_box("RC-CAR-J3-CARRIAGE", (-140.0, YC, 147.0), (36.0, 24.0, 22.0), (1, 0, 0), (0, 1, 0), "aluminum", "link2",
             "J3 moving carriage (nominal mid-travel x=-140), bore for bundle, E2.10-class guide channel", kind="carrier")
clamp_saddle("RC-CLP-J3-MOV", (-140.0, YC, 147.0), (-1, 0, 0), "polymer", "link2", "CM-J3-M moving clamp on carriage")
for i in range(6):
    box_at("RC-CHN-E210-LINK-%02d" % i, (-95.0 - i*20.0, YC, 147.0), (18.0, 16.0, 10.0), "polymer", "link2",
           "igus E2.10 e-chain link %d/6 (pitch 20, inner 10x16)" % (i+1))

# J3 saddle + liner
guide_tube("RC-GDE-J3-SADDLE", J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 65.0, j3_start_ang, j3_sweep, 7.0,
           "aluminum", "link2", "J3 guide saddle R63 200 deg", "guide_saddle")
guide_tube("RC-GDE-J3-SADDLE-LINER", J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 65.0, j3_start_ang, j3_sweep, 8.6,
           "polymer", "link2", "J3 saddle liner sleeve", "liner")

# link3 channel + clamps
channel_section("RC-CHN-L3", M3, F4, 12.0, 12.0, "aluminum", "link3", "link3 fixed channel (rising)")
l3_dir = v_norm(v_sub(F4, M3))
l3_p1 = v_add(M3, v_mul(l3_dir, v_dist(M3, F4)/3.0))
l3_p2 = v_add(M3, v_mul(l3_dir, 2.0*v_dist(M3, F4)/3.0))
clamp_saddle("RC-CLP-L3-01", l3_p1, l3_dir, "aluminum", "link3", "CF-L3-01 fixed clamp")
clamp_saddle("RC-CLP-L3-02", l3_p2, l3_dir, "aluminum", "link3", "CF-L3-02 fixed clamp")
clamp_saddle("RC-CLP-J4-FIX", F4, (1, 0, 0), "aluminum", "link3", "CF-J4-F fixed clamp on link3 side of J4 loop")

# J4 mandrel + liner + clamps
guide_tube("RC-GDE-J4-MANDREL", J4_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j4_start_ang, j4_sweep, 6.0,
           "aluminum", "link3", "J4 loop guide mandrel R50 315 deg", "guide_mandrel")
guide_tube("RC-GDE-J4-MANDREL-LINER", J4_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j4_start_ang, j4_sweep, 7.5,
           "polymer", "link3", "J4 mandrel liner sleeve", "liner")
clamp_saddle("RC-CLP-J4-MOV", M4, (1, 0, 0), "aluminum", "link4", "CM-J4-M moving clamp on link4")

# link4 tilted channel (rises to J5 wrap plane) + clamps
channel_section("RC-CHN-L4", M4, K2, 12.0, 12.0, "aluminum", "link4", "link4 tilted fixed channel rising to J5 wrap plane")
l4_clamp_pt = v_add(M4, v_mul(v_norm(v_sub(K2, M4)), 0.544*v_dist(M4, K2)))
clamp_saddle("RC-CLP-L4-01", l4_clamp_pt, v_norm(v_sub(K2, M4)), "aluminum", "link4", "CF-L4-01 fixed clamp at channel mid")
clamp_saddle("RC-CLP-J5-FIX", K2, v_norm(v_sub(T1_J5, K2)), "aluminum", "link4", "CF-J5-F fixed clamp at J5 wrap entry")

# J5 wrap mandrel + liner + clamps
guide_tube("RC-GDE-J5-WRAP", J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 55.0, j5_start_ang, j5_sweep, 6.0,
           "aluminum", "link5", "J5 wrist wrap mandrel R50 185 deg", "guide_mandrel")
guide_tube("RC-GDE-J5-WRAP-LINER", J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 55.0, j5_start_ang, j5_sweep, 7.5,
           "polymer", "link5", "J5 wrap liner sleeve", "liner")
clamp_saddle("RC-CLP-J5-MOV", j5_end, j5_exit_tan, "aluminum", "link5", "CM-J5-M moving clamp at J5 wrap exit")

# J6 helix guide rings + brackets + clamps
for idx, ang in enumerate([180.0, 360.0, 540.0, 720.0]):
    along = j6_pitch * math.radians(ang - j6_start_ang) / (2.0*math.pi)
    c = (J6_ORIGIN[0] + along, J6_ORIGIN[1], J6_ORIGIN[2])
    ring("RC-GDE-J6-RING-%d" % idx, c, (1, 0, 0), 62.0, 58.0, 4.0, "polymer", "link6",
         "J6 helix guide ring %d at wrap angle %.0f deg" % (idx, ang))
box_at("RC-BRK-J6-GUIDE-A", (160.0, 0.0, 250.0), (8.0, 30.0, 6.0), "aluminum", "link6", "J6 guide ring support arm A")
box_at("RC-BRK-J6-GUIDE-B", (180.0, 0.0, 250.0), (8.0, 30.0, 6.0), "aluminum", "link6", "J6 guide ring support arm B")
clamp_saddle("RC-CLP-J6-FIX", H0, j6_entry_tan, "aluminum", "link5", "CM-J6-F fixed clamp at J6 helix entry")
clamp_saddle("RC-CLP-J6-MOV", j6_end, j6_exit_tan, "aluminum", "link6", "CM-J6-M moving clamp at J6 helix exit")

# wrist strain relief + split plate + connectors
clamp_saddle("RC-SR-WRIST", (225.0, -55.0, 241.7), (1, 0, 0), "aluminum", "link6", "CF-WR-SR wrist strain relief clamp")
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
    ("CF-BUS-00", "bus", HN01, "FIXED", "2xM3 on RC-CHN-BUS-FT", "fixed clamp at HN-01 (passage mouth)"),
    ("CF-BUS-01", "bus", HN02, "FIXED+STRAIN_RELIEF", "2xM3 on RC-CHN-BUS-FT", "fixed clamp + strain relief at HN-02"),
    ("CF-BUS-02", "base_link", (-25.60, -64.77, 4.59), "FIXED", "2xM3 on bracket arm",
     "route clamp with bracket arm to CN-BASE-00 at HN-03 station (S 215,0,-45)"),
    ("CF-BUS-03", "base_link", RISER_MID, "FIXED", "2xM3 on bracket arm",
     "riser clamp, bracket arm to collar ring at HN-04 station (S 220,0,-30)"),
    ("CM-J1-M", "link1", j1_end, "MOVING", "2xM3 on RC-BRK-L1-01", "rotating clamp at annulus exit"),
    ("CF-L1-01", "link1", v_add(j1_end, v_mul(j1_exit_tan, 30.0)), "FIXED", "2xM3 on RC-BRK-L1-01",
     "fixed clamp on link1 annulus exit stub"),
    ("CF-J2-F", "link1", T1_J2, "FIXED", "2xM3 on link1 derived pad", "J2 loop fixed clamp (link1 side)"),
    ("CM-J2-M", "link2", M2, "MOVING", "2xM3 on RC-CHN-L2", "J2 loop moving clamp (link2 side)"),
    ("CF-L2-01", "link2", (-80.0, YC, 147.0), "FIXED", "2xM3 on RC-CHN-L2", "link2 channel fixed clamp"),
    ("CM-J3-M", "link2", (-140.0, YC, 147.0), "MOVING_CARRIER", "carriage RC-CAR-J3-CARRIAGE",
     "J3 carrier moving clamp, travel x -85..-195 (link2 frame)"),
    ("CF-L2-02", "link2", (-208.0, YC, 147.0), "FIXED", "2xM3 on RC-CHN-L2", "link2 channel end clamp"),
    ("CG-J3-S", "link2", (-255.0, YC, 147.0), "GUIDE_SADDLE", "4xM3 saddle bracket", "J3 guide saddle entry tangent"),
    ("CF-L3-01", "link3", l3_p1, "FIXED", "2xM3 on RC-CHN-L3", "link3 channel fixed clamp"),
    ("CF-L3-02", "link3", l3_p2, "FIXED", "2xM3 on RC-CHN-L3", "link3 channel fixed clamp"),
    ("CF-J4-F", "link3", F4, "FIXED", "2xM3 on RC-CHN-L3", "J4 loop fixed clamp (link3 side)"),
    ("CM-J4-M", "link4", M4, "MOVING", "2xM3 on RC-CHN-L4", "J4 loop moving clamp (link4 side)"),
    ("CF-L4-01", "link4", l4_clamp_pt, "FIXED", "2xM3 on RC-CHN-L4", "link4 channel end clamp"),
    ("CF-J5-F", "link4", K2, "FIXED", "2xM3 on riser guide tube", "J5 wrap entry fixed clamp"),
    ("CM-J5-M", "link5", j5_end, "MOVING", "2xM3 on link5 derived pad", "J5 wrap exit moving clamp"),
    ("CM-J6-F", "link5", H0, "FIXED", "2xM3 on link5 end pad", "J6 helix entry fixed clamp"),
    ("CM-J6-M", "link6", j6_end, "MOVING", "2xM3 on link6 derived pad", "J6 helix exit moving clamp"),
    ("CF-WR-SR", "link6", (225.0, -55.0, 241.7), "STRAIN_RELIEF", "2xM3 on link6 wrist pad", "wrist strain relief"),
    ("CF-WR-PL", "link6", PLATE, "FIXED", "4xM3 on RC-PLT-WRIST-SPLIT", "wrist connector split plate"),
]

with open(OUT_CLAMPS, "w", newline="") as f:
    f.write("clamp_id,host_link,type,frame,x_mm,y_mm,z_mm,fastener_interface,note\n")
    for cid, host, pw, ctype, fastener, note in CLAMPS:
        local = world_to_host(pw, host) if host in FRAMES else pw
        frame_name = "S" if host == "bus" else host + "_frame"
        f.write("%s,%s,%s,%s,%.3f,%.3f,%.3f,%s,%s\n" % (
            cid, host, ctype, frame_name, local[0], local[1], local[2], fastener, note))

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
    "schema": "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V2",
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
centerline_doc = {
    "schema": "B601_ROUTE_C_HARNESS_CENTERLINE_V2",
    "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
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
for srep in segment_reports:
    all_violations.extend(srep["violations"])
min_bend_all = [s["min_bend_radius_mm"] for s in segment_reports if s["min_bend_radius_mm"] is not None]
receipt = {
    "schema": "B601_ROUTE_C_BUILD_RECEIPT_V2",
    "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
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
    "mesh_reference_report": mesh_report,
    "take_up_summary": centerline_doc["take_up_summary"],
    "mass_delta_totals": mass_delta_doc["totals"],
    "accepted_urdf_unchanged": True,
    "frozen_assets_modified": False,
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
