# -*- coding: utf-8 -*-
"""SOLAR_ARRAY_R2 kinematics core (pure python, no FreeCAD dependency).

Authority: ODR-19 (ECR-SOLAR-ARRAY-R2).  Two symmetric wings, three leaves
per wing, leaf planform 300 x 200 mm, all hinge axes parallel to X_S,
accordion stack, passive deployment + latch.

Design decisions recorded here (ENGINEERING_CANDIDATE, not flight values):

D-R2-01  Root hinge line sits at the -Z edge of the side face
         (z = HINGE_Z = -108.15 mm, 5 mm above the bottom rail face at
         -113.15).  Rationale: the 200 mm leaf span exceeds the 113.15 mm
         half-height of the 226.3 mm cross-section, so a z = 0 hinge line
         (R1 heritage) cannot stow a 200 mm leaf against the side face.
         An edge hinge is the only single-DOF stow that keeps the stowed
         leaf inside the Z envelope (span z in [-108.15, +91.85]).
D-R2-02  Chord window x in [-150, +150] mm, centred on S origin: symmetric
         20.25 mm margins to both X end faces of the 340.5 mm MODE_OP body;
         compatible with a 366 mm MODE_FLIGHT envelope.  (Centring on the
         R1 root station x = -56.75 would overhang the -X end face by
         36.5 mm; rejected.)
D-R2-03  Leaf total assembly thickness 2.5 mm (upper bound of the ODR-19
         2.0-2.5 mm target band, conservative for clearance) + 0.5 mm
         stowed inter-leaf gap -> 8.5 mm stack, 9.0 mm protrusion beyond
         the side face.  Generic 6.5 mm CubeSat protrusion is a
         MODE_FLIGHT HOLD item per ODR-18 item 4 / ODR-19.
D-R2-04  Accordion hinge knuckle offset: leaf mid-planes step 3.0 mm
         (t + gap) along the stacking normal; deployed leaves are therefore
         not exactly coplanar (6 mm total), which is conservative for
         clearance evidence.

Angles: th1 in [0, 90] deg (0 = stowed, 90 = deployed) for the root leaf;
ph2, ph3 in [0, 180] deg (0 = folded back, 180 = unfolded flat) for the
inter-panel hinges.  Deployment sequence per ODR-19: th1 -> ph2 -> ph3.

All lengths millimetres, frame S.  side = +1 left wing (deploys +Y_S),
side = -1 right wing (deploys -Y_S).
"""

from __future__ import annotations

import math

LEAF_CHORD = 300.0          # along X_S
LEAF_SPAN = 200.0           # along Y_S deployed
LEAF_T = 2.5                # leaf total assembly thickness (D-R2-03)
LEAF_GAP = 0.5              # stowed inter-leaf gap
STACK_STEP = LEAF_T + LEAF_GAP   # 3.0 mm mid-plane step (D-R2-04)

SIDE_FACE_Y = 113.15        # bus side face (226.3 / 2)
STACK_STANDOFF = 1.0        # leaf1 inner-face clearance to side face
                            # (raised 0.5 -> 1.0 by R2-WI-07: 0.5 failed the
                            # worst-case thermal/manufacturing margin by -0.023 mm;
                            # directive-authorized standoff fix; protrusion becomes
                            # 9.5 mm, stack height unchanged 8.5 mm)
LEAF1_MID_Y = SIDE_FACE_Y + STACK_STANDOFF + LEAF_T / 2.0   # 114.9
HINGE_Z = -108.15           # root hinge line z (D-R2-01)
CHORD_X = (-150.0, 150.0)   # D-R2-02

BODY_X_HALF = 170.25        # 340.5 / 2 MODE_OP
BODY_CROSS_HALF = 113.15    # 226.3 / 2

TH1_STOWED, TH1_DEPLOYED = 0.0, 90.0
PH_STOWED, PH_DEPLOYED = 0.0, 180.0

N_LEAVES = 3


def leaf_segments(side: int, th1_deg: float, ph2_deg: float, ph3_deg: float):
    """Return per-leaf mid-plane segment data for one wing.

    Each entry: {index, start:(y,z), dir:(y,z), normal:(y,z)} where
    start is the leaf root point on the zero-offset mid-plane chain,
    dir the unit vector from root to tip (span direction), and normal
    the stacking normal (outboard at stow).  X window is CHORD_X.
    """
    assert side in (+1, -1)
    t1 = math.radians(th1_deg)
    psi1 = t1
    psi2 = psi1 + math.radians(180.0 - ph2_deg)
    psi3 = psi2 + math.radians(180.0 - ph3_deg)

    p0 = (side * LEAF1_MID_Y, HINGE_Z)
    pts = [p0]
    dirs = []
    normals = []
    psi = (psi1, psi2, psi3)
    p = p0
    for k in range(N_LEAVES):
        d = (side * math.sin(psi[k]), math.cos(psi[k]))
        # stacking normal: outboard (+/-Y) at stow, -Z when deployed,
        # identical z-behaviour for both wings (keeps z-symmetry).
        # Accordion fix: folded-back leaves (psi ~ 180 deg) would flip the
        # raw normal inboard; re-sign it so its Y component always points
        # outboard (sign = side), keeping every leaf stacked outboard.
        s = (side * math.cos(psi[k]), -math.sin(psi[k]))
        if s[0] * side < 0.0:
            s = (-s[0], -s[1])
        dirs.append(d)
        normals.append(s)
        p = (p[0] + LEAF_SPAN * d[0], p[1] + LEAF_SPAN * d[1])
        pts.append(p)

    leaves = []
    for k in range(N_LEAVES):
        leaves.append({
            "index": k + 1,
            "start": pts[k],
            "tip": pts[k + 1],
            "dir": dirs[k],
            "normal": normals[k],
            "midplane_offset": k * STACK_STEP,
        })
    return leaves


def leaf_solid_frame(side: int, leaf: dict):
    """Compose the solid placement for one leaf.

    Returns (origin_xyz, e2, e3) with e1 = (1,0,0) implicitly: the leaf
    solid is a box chord x span x thickness built on local axes
    (e1, e2, e3) where e2 = span direction, e3 chosen so the basis is
    right-handed (det +1) for both wings.
    """
    d = leaf["dir"]
    s = leaf["normal"]
    off = leaf["midplane_offset"]
    if side == +1:
        # e3 = -s ; box z in [0, T] along e3 -> origin at off + T/2 along s
        e3 = (0.0, -s[0], -s[1])
        shift = off + LEAF_T / 2.0
    else:
        # e3 = +s ; box z in [0, T] along e3 -> origin at off - T/2 along s
        e3 = (0.0, s[0], s[1])
        shift = off - LEAF_T / 2.0
    origin = (
        CHORD_X[0],
        leaf["start"][0] + shift * s[0],
        leaf["start"][1] + shift * s[1],
    )
    e2 = (0.0, d[0], d[1])
    return origin, e2, e3


def wing_segments(th1_deg: float, ph2_deg: float, ph3_deg: float):
    """Both wings: {'left': [...], 'right': [...]} leaf segment lists."""
    return {
        "left": leaf_segments(+1, th1_deg, ph2_deg, ph3_deg),
        "right": leaf_segments(-1, th1_deg, ph2_deg, ph3_deg),
    }


# Canonical configurations
STOWED = (TH1_STOWED, PH_STOWED, PH_STOWED)          # (0, 0, 0)
DEPLOYED = (TH1_DEPLOYED, PH_DEPLOYED, PH_DEPLOYED)  # (90, 180, 180)


def deployed_tip_y() -> float:
    return LEAF1_MID_Y + N_LEAVES * LEAF_SPAN


def stowed_stack_metrics() -> dict:
    inner = SIDE_FACE_Y + STACK_STANDOFF
    outer = inner + N_LEAVES * LEAF_T + (N_LEAVES - 1) * LEAF_GAP
    return {
        "stack_height_mm": round(outer - inner, 6),
        "protrusion_beyond_side_face_mm": round(outer - SIDE_FACE_Y, 6),
        "stowed_z_span_mm": [HINGE_Z, HINGE_Z + LEAF_SPAN],
        "deployed_tip_to_tip_mm": round(2.0 * deployed_tip_y(), 6),
        "chord_margins_mm": [
            round(CHORD_X[0] + BODY_X_HALF, 6),
            round(BODY_X_HALF - CHORD_X[1], 6),
        ],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(stowed_stack_metrics(), indent=2))
    for name, cfg in (("STOWED", STOWED), ("DEPLOYED", DEPLOYED)):
        segs = wing_segments(*cfg)
        print(name, "left leaf tips:",
              [(round(l["tip"][0], 3), round(l["tip"][1], 3)) for l in segs["left"]])
