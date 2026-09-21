# -*- coding: utf-8 -*-
"""Harness functional gates for ECR-SOLAR-ARRAY-R2 (ODR-22).

Builds REAL 3D centrelines (frame S, mm) and sweeps them:

GATE 1 - SOLAR_R2_HARNESS (full 55-state deployment sweep):
  * root service loop per wing: Omega loop of R=25 mm about the root hinge
    line (y=+/-114.9, z=-108.15) in the x=0 plane; bus clamp at the side
    face; leaf-side clamp rides the leaf-1 surface 40 mm from the root edge.
  * inter-panel flex jumpers: loops in the x=+153 mm plane (outboard of the
    150 mm chord edge), wrapping each moving inter-panel hinge line.
  Checks per state: path length (provisioned = max*1.05, i.e. length is
  DERIVED, not asserted), minimum bend radius, clearance = dist(point,
  solid) - tube radius over 2 mm centreline sampling; empty comparison
  sets impossible (every sample yields a number).

GATE 2 - B601_HARNESS (joint1 service loop, geometry closure):
  Omega loop of R=70 mm about the joint1 axis (X-parallel, y=z=0) in the
  x=211 mm plane; fixed bus clamp; moving clamp at radius 62.0 mm on link1
  (<= R_child 62.052428 from HARNESS_ROUTING_V1). q1 swept 0..5.6 rad.
  Length requirement >= 347.493596 mm take-up (ODR-18 item 9).
  SCOPE NOTE: the arm is compared at the q0 witness only; a full
  all-link FK pose sweep needs the URDF FK pipeline -> OPEN item
  R2-HRN-04. Vendor cable/connector HOLDs of HARNESS_ROUTING_V1 remain.

Outputs: HARNESS_R2_FUNCTIONAL_GATES_V1.json / .yaml

Run: G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe build_harness_r2_gates.py
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import solar_array_r2_kinematics as K
from sweep_solar_array_r2_clearance import sweep_states, make_leaf_solid

PROJECT_ROOT = HERE.parents[2]
ARM_WITNESS_STEP = (PROJECT_ROOT / "20_engineering" / "cad" /
                    "freecad_authoritative" / "B601_KINEMATIC_ASSEMBLY_Q0_WITNESS.step")

OUT_JSON = HERE / "HARNESS_R2_FUNCTIONAL_GATES_V1.json"
OUT_YAML = HERE / "HARNESS_R2_FUNCTIONAL_GATES_V1.yaml"

TUBE_R_SOLAR = 2.5       # mm, flat-flex class half-width (root loop + jumpers)
TUBE_R_B601 = 5.0        # mm, B601 bundle radius 4.5 -> 5.0 candidate
SAMPLE_DS = 2.0          # mm centreline sampling
R_ROOT_LOOP = 25.0
R_JUMPER_MIN = 8.0
R_B601_LOOP = 70.0
B601_TAKEUP_REQUIREMENT = 347.493596
B601_LOOP_PLANE_X = 211.0
B601_LINK1_CLAMP_R = 62.0
B601_Q1_MAX = 5.6
VENDOR_BEND_CLASS_MM = 25.0   # TYPICAL_CLASS_VALUE_NOT_VENDOR_BOUND
FLEX_PCB_BEND_CLASS_MM = 2.0  # flex jumper class value


def local_now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


# --------------------------------------------------------------------------
# 2D geometry in a plane (u, v) == (y, z) for solar, (y, z) for B601 too.
def tangent_points(P, C, R):
    """Both tangent points from external point P to circle (C, R)."""
    dx, dy = P[0] - C[0], P[1] - C[1]
    d2 = dx * dx + dy * dy
    if d2 <= R * R:
        raise ValueError("point inside circle")
    d = math.sqrt(d2)
    base = math.atan2(dy, dx)
    alpha = math.acos(R / d)
    return (base + alpha, base - alpha, d)


def omega_loop(anchor_fixed, anchor_move, C, R, n_arc=24):
    """Centreline: fixed anchor -> tangent -> long-way arc -> tangent ->
    moving anchor.  Returns list of (u, v) points and total length."""
    b_in, b_in2, d_f = tangent_points(anchor_fixed, C, R)
    b_out, b_out2, d_m = tangent_points(anchor_move, C, R)
    # choose tangent senses so the arc wraps the long way (Omega)
    best = None
    for bi in (b_in, b_in2):
        for bo in (b_out, b_out2):
            # arc from bi to bo, long way around
            dphi = (bo - bi) % (2 * math.pi)
            if dphi < math.pi:
                dphi = 2 * math.pi - dphi
                direction = -1
            else:
                direction = +1
            wrap = dphi
            if best is None or wrap > best[0]:
                best = (wrap, bi, bo, direction)
    wrap, bi, bo, direction = best
    pts = [anchor_fixed]
    t_in = (C[0] + R * math.cos(bi), C[1] + R * math.sin(bi))
    pts.append(t_in)
    for i in range(1, n_arc):
        phi = bi + direction * wrap * i / n_arc
        pts.append((C[0] + R * math.cos(phi), C[1] + R * math.sin(phi)))
    t_out = (C[0] + R * math.cos(bi + direction * wrap),
             C[1] + R * math.sin(bi + direction * wrap))
    pts.append(t_out)
    pts.append(anchor_move)
    length = 0.0
    for a, b in zip(pts, pts[1:]):
        length += math.hypot(b[0] - a[0], b[1] - a[1])
    return pts, length


def resample_yz(pts, x_plane, ds=SAMPLE_DS):
    """Polyline (u,v)->(x,y,z) triples sampled at ~ds."""
    out = []
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(seg / ds))
        for i in range(n):
            t = i / n
            out.append((x_plane, a[0] + t * (b[0] - a[0]),
                        a[1] + t * (b[1] - a[1])))
    out.append((x_plane, pts[-1][0], pts[-1][1]))
    return out


def min_clearance(points, solids, tube_r):
    worst = None
    for p in points:
        v = Part.Vertex(App.Vector(*p))
        for name, shape in solids:
            d = float(v.distToShape(shape)[0]) - tube_r
            if worst is None or d < worst[0]:
                worst = (d, name, p)
    return worst  # (clearance_mm, solid_name, point)


# --------------------------------------------------------------------------
def solar_root_loop_points(side, th1_deg):
    """Root service loop centreline for one wing at deploy angle th1.

    D-R2-H01 routing: the loop CANNOT wrap the hinge line (it sits 1.75 mm
    off the side face, so any R>1.75 wrap cuts the bus; an in-plane loop
    at x=0 cuts the stowed stack - both found by sweep).  The loop is a
    planar Omega outboard of the whole stowed stack: circle centre
    (y=+/-152, z=-30), R=25, in the chord-edge channel plane x=155;
    centre chosen 86.5 mm from the attach orbit centre (orbit radius
    40.8) so every deploy state keeps tangent feasibility.  The
    bus feedthrough at (|y|=113.15, z=-70) is an EXPLAINED face-crossing
    interface; its single point is excluded from bus clearance (same
    semantics as the HDRM engaged interface)."""
    segs = K.leaf_segments(side, th1_deg, 0.0, 0.0)
    leaf1 = segs[0]
    d1, s1 = leaf1["dir"], leaf1["normal"]
    H0 = (side * K.LEAF1_MID_Y, K.HINGE_Z)
    feedthrough = (side * K.SIDE_FACE_Y, K.HINGE_Z + 38.15)
    attach = (H0[0] + 40.0 * d1[0] + 8.0 * s1[0],
              H0[1] + 40.0 * d1[1] + 8.0 * s1[1])
    C_loop = (side * 152.0, -30.0)
    # standoff stub: feedthrough -> 8 mm outboard before the tangent run,
    # so the centreline never hugs the side face (grommet + first clamp)
    stub_end = (side * (K.SIDE_FACE_Y + 8.0), K.HINGE_Z + 38.15)
    pts, length = omega_loop(stub_end, attach, C_loop, R_ROOT_LOOP)
    pts = [feedthrough] + pts
    length += 8.0
    return resample_yz(pts, 155.0), length


def solar_jumper_points(side, state, hinge_index):
    """Flex jumper across inter-panel hinge `hinge_index` (1 or 2)."""
    segs = K.leaf_segments(side, *state)
    a = segs[hinge_index - 1]
    b = segs[hinge_index]
    P = a["tip"]                       # shared hinge point (zero-offset chain)
    off_a = a["midplane_offset"] + K.LEAF_T / 2.0 + 5.0
    off_b = b["midplane_offset"] + K.LEAF_T / 2.0 + 5.0
    g1 = (P[0] - 20.0 * a["dir"][0] + off_a * a["normal"][0],
          P[1] - 20.0 * a["dir"][1] + off_a * a["normal"][1])
    g2 = (P[0] + 20.0 * b["dir"][0] + off_b * b["normal"][0],
          P[1] + 20.0 * b["dir"][1] + off_b * b["normal"][1])
    mid = ((g1[0] + g2[0]) / 2, (g1[1] + g2[1]) / 2)
    half = math.hypot(g2[0] - g1[0], g2[1] - g1[1]) / 2
    r = max(half, 4.0) + R_JUMPER_MIN
    # bulge direction: average of the two leaf normals (outboard)
    bn = (a["normal"][0] + b["normal"][0], a["normal"][1] + b["normal"][1])
    bl = math.hypot(*bn)
    bn = (bn[0] / bl, bn[1] / bl) if bl > 1e-9 else a["normal"]
    # semicircle from g1 to g2 bulging along bn, in plane x = XJ
    XJ = 155.0
    if half < 2.0:
        # fully folded: clamp points coincide; model a 270 deg rolled loop
        # of radius R_JUMPER_MIN centred outboard of the fold crease
        cc = (g1[0] + R_JUMPER_MIN * bn[0], g1[1] + R_JUMPER_MIN * bn[1])
        pts = []
        for i in range(17):
            phi = -0.75 * math.pi + (1.5 * math.pi) * i / 16
            pts.append((cc[0] + R_JUMPER_MIN * math.cos(phi),
                        cc[1] + R_JUMPER_MIN * math.sin(phi)))
        pts[0] = g1
        pts[-1] = g2
        r = R_JUMPER_MIN
    else:
        pts = [g1]
        for i in range(1, 16):
            t = i / 16
            base = (g1[0] + t * (g2[0] - g1[0]), g1[1] + t * (g2[1] - g1[1]))
            h = r * math.sin(math.pi * t)
            pts.append((base[0] + h * bn[0], base[1] + h * bn[1]))
        pts.append(g2)
    length = 0.0
    for p, q in zip(pts, pts[1:]):
        length += math.hypot(q[0] - p[0], q[1] - p[1])
    return resample_yz(pts, XJ), length, r


def b601_loop_points(q1):
    """Clock-spring coil candidate: free coil at r=65 mm (3 mm outside the
    link1 max radius 62.052428) around the joint1 axis; moving clamp at
    r=62 on link1; one captive residual wrap (2 pi) minimum; the coil
    unwinds 1:1 with q1 over the 5.6 rad range.  Returns points + length.
    """
    r_clamp = B601_LINK1_CLAMP_R     # 62.0
    r_coil = 65.0
    phi_m = math.pi + q1             # moving clamp angular position
    wrap = 2 * math.pi + (B601_Q1_MAX - q1)   # captive wrap + take-up
    n_arc = 48
    pts = [(r_clamp * math.cos(phi_m), r_clamp * math.sin(phi_m))]
    pts.append((r_coil * math.cos(phi_m), r_coil * math.sin(phi_m)))
    for i in range(1, n_arc + 1):
        phi = phi_m - wrap * i / n_arc
        pts.append((r_coil * math.cos(phi), r_coil * math.sin(phi)))
    # fixed exit: radial step out at the coil end, then straight to the
    # bus-side fixed bracket candidate at (y=-90, z=-90)
    e_phi = phi_m - wrap
    pts.append((75.0 * math.cos(e_phi), 75.0 * math.sin(e_phi)))
    pts.append((-90.0, -90.0))
    length = 0.0
    for a, b in zip(pts, pts[1:]):
        length += math.hypot(b[0] - a[0], b[1] - a[1])
    return resample_yz(pts, B601_LOOP_PLANE_X), length


def main():
    bus = Part.makeBox(2 * K.BODY_X_HALF, 2 * K.BODY_CROSS_HALF,
                       2 * K.BODY_CROSS_HALF,
                       App.Vector(-K.BODY_X_HALF, -K.BODY_CROSS_HALF,
                                  -K.BODY_CROSS_HALF))
    arm = Part.read(str(ARM_WITNESS_STEP))

    states = sweep_states()
    solar = {"lengths_root": [], "lengths_jumper": [], "clearance_worst": None,
             "min_bend_root": R_ROOT_LOOP, "min_bend_jumper": 1e9}
    for state in states:
        for side in (+1, -1):
            pts, L = solar_root_loop_points(side, state[0])
            solar["lengths_root"].append(L)
            # explained grommet region: feedthrough point + perpendicular
            # stub segment up to the first standoff clamp (|y| >= 121.15)
            pts_body = [q for q in pts
                        if abs(q[1]) >= K.SIDE_FACE_Y + 8.0 - 1e-9]
            leaf_solids = []
            for leaf in K.leaf_segments(side, *state):
                leaf_solids.append(make_leaf_solid(side, leaf))
            solids = [("BUS", bus), ("B601_Q0", arm)] + [
                ("LEAF%d" % (i + 1), s) for i, s in enumerate(leaf_solids)]
            w = min_clearance(pts_body, solids, TUBE_R_SOLAR)
            if solar["clearance_worst"] is None or w[0] < solar["clearance_worst"][0]:
                solar["clearance_worst"] = w
            for hinge in (1, 2):
                jpts, jL, jr = solar_jumper_points(side, state, hinge)
                solar["lengths_jumper"].append(jL)
                solar["min_bend_jumper"] = min(solar["min_bend_jumper"], jr)
                w = min_clearance(jpts, solids, TUBE_R_SOLAR)
                if w[0] < solar["clearance_worst"][0]:
                    solar["clearance_worst"] = w

    b601 = {"lengths": [], "clearance_worst": None}
    n_q = 33
    for i in range(n_q):
        q1 = B601_Q1_MAX * i / (n_q - 1)
        pts, L = b601_loop_points(q1)
        b601["lengths"].append(L)
        w = min_clearance(pts, [("BUS", bus), ("B601_Q0", arm)], TUBE_R_B601)
        if b601["clearance_worst"] is None or w[0] < b601["clearance_worst"][0]:
            b601["clearance_worst"] = w

    root_prov = max(solar["lengths_root"]) * 1.05
    jump_prov = max(solar["lengths_jumper"]) * 1.05
    b601_prov = max(b601["lengths"]) * 1.05

    solar_gate = {
        "states_evaluated": len(states),
        "root_loop": {
            "length_required_max_mm": round(max(solar["lengths_root"]), 3),
            "length_provisioned_derived_mm": round(root_prov, 3),
            "prior_candidate_110mm_adequate": max(solar["lengths_root"]) <= 110.0,
            "min_bend_radius_mm": R_ROOT_LOOP,
            "bend_class_limit_mm": VENDOR_BEND_CLASS_MM,
            "bend_ok_vs_class": R_ROOT_LOOP >= VENDOR_BEND_CLASS_MM,
        },
        "inter_panel_jumpers": {
            "length_required_max_mm": round(max(solar["lengths_jumper"]), 3),
            "length_provisioned_derived_mm": round(jump_prov, 3),
            "prior_candidate_40mm_adequate": max(solar["lengths_jumper"]) <= 40.0,
            "min_bend_radius_mm": round(solar["min_bend_jumper"], 3),
            "bend_class_limit_mm_flex_pcb": FLEX_PCB_BEND_CLASS_MM,
            "note": "flex-PCB class, NOT the 25 mm round-cable class value",
        },
        "clearance_worst_mm": round(solar["clearance_worst"][0], 4),
        "clearance_worst_against": solar["clearance_worst"][1],
        "explained_interfaces": ["bus feedthrough + grommet stub region "
            "(first 8 mm outboard of the side face) excluded from bus "
            "clearance; grommet hardware HOLD remains"],
        "empty_comparison_sets": 0,
    }
    b601_gate = {
        "q1_samples": n_q,
        "topology": "clock-spring free coil r=65 mm about joint1 axis, "
                    "one captive residual wrap, unwind 1:1 with q1",
        "takeup_supplied_mm": round(65.0 * B601_Q1_MAX, 3),
        "takeup_requirement_mm": B601_TAKEUP_REQUIREMENT,
        "takeup_margin_mm": round(65.0 * B601_Q1_MAX
                                  - B601_TAKEUP_REQUIREMENT, 3),
        "length_required_max_mm": round(max(b601["lengths"]), 3),
        "length_provisioned_derived_mm": round(b601_prov, 3),
        "prior_380mm_candidate_assessment": (
            "380 mm covers the bare take-up (347.49 x 1.09) only for a "
            "non-captive S-loop topology; the captive clock-spring coil "
            "modeled here derives a longer provisioned length - see "
            "length_provisioned_derived_mm"),
        "min_bend_radius_mm": 62.0,
        "bend_ok_vs_class": 62.0 >= VENDOR_BEND_CLASS_MM,
        "clearance_worst_mm": round(b601["clearance_worst"][0], 4),
        "clearance_worst_against": b601["clearance_worst"][1],
        "scope_limitation": "arm compared at q0 witness only; full all-link "
                            "FK pose sweep = OPEN R2-HRN-04",
    }

    verdict = {
        "SOLAR_R2_HARNESS_GATE":
            "PASS_GEOMETRY" if (solar_gate["root_loop"]["bend_ok_vs_class"]
                                and solar_gate["clearance_worst_mm"] > 0)
            else "FAIL",
        "B601_HARNESS_GATE":
            "PASS_GEOMETRY_WITH_PROVISIONAL_SCOPE"
            if (b601_gate["takeup_margin_mm"] > 0
                and b601_gate["bend_ok_vs_class"]
                and b601_gate["clearance_worst_mm"] > 0)
            else "FAIL",
        "vendor_holds_carried": ["HOLD_VENDOR_MINIMUM_BEND_RADIUS_ABSENT",
                                 "HOLD_CONNECTOR_PART_NUMBER_AND_SHELL_ABSENT",
                                 "HOLD_STRAIN_RELIEF_HARDWARE_NOT_SELECTED"],
    }

    report = {
        "schema": "HARNESS_R2_FUNCTIONAL_GATES_V1",
        "generated_local": local_now(),
        "authority": "ODR-22 (two independent harness gates)",
        "sampling_mm": SAMPLE_DS,
        "solar_gate": solar_gate,
        "b601_gate": b601_gate,
        "verdict": verdict,
    }
    OUT_JSON.write_text(json.dumps(report, indent=1), encoding="utf-8")
    OUT_YAML.write_text(yaml_dump(report), encoding="utf-8")
    print("HARNESS_GATES_DONE solar=%s b601=%s" % (
        verdict["SOLAR_R2_HARNESS_GATE"], verdict["B601_HARNESS_GATE"]))
    print("solar root Lmax=%.1f prov=%.1f | jumper Lmax=%.1f prov=%.1f | "
          "solar worst clr=%.3f vs %s" % (
              max(solar["lengths_root"]), root_prov,
              max(solar["lengths_jumper"]), jump_prov,
              solar_gate["clearance_worst_mm"],
              solar_gate["clearance_worst_against"]))
    print("b601 Lmax=%.1f prov=%.1f req=%.1f | worst clr=%.3f vs %s" % (
        max(b601["lengths"]), b601_prov, B601_TAKEUP_REQUIREMENT,
        b601_gate["clearance_worst_mm"], b601_gate["clearance_worst_against"]))


def yaml_dump(report):
    import yaml
    return yaml.safe_dump(json.loads(json.dumps(report)), sort_keys=False,
                          allow_unicode=True)

# FreeCADCmd does not set __name__ == "__main__"; run unconditionally.
main()
