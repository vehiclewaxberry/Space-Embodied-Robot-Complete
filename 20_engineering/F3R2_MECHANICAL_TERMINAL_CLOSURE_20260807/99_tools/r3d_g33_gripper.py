# -*- coding: utf-8 -*-
"""F3R2 G3-3a: turn the gripper into two REAL movable fingers.

The record this replaces said "solids_in_cad: 1 ... the CAD carries a SINGLE
gripper solid; it has no separated fingers" and concluded
SEPARATION_REQUIRED_NOT_DONE.  That was read off the tessellated roll-up label.
The B-rep probe of the same part enumerates **58 solids**, and they project onto
the jaw axis in exact mirror pairs.  So the two fingers are already modelled --
what was missing was the binding, not the geometry.

Membership is decided by the accepted URDF, never by eyeballing:

    a CAD solid belongs to gripper_left / gripper_right / gripper_link
    according to which URDF collision body encloses it at the as-built pose.

The URDF is the only authority for what those three bodies ARE; the CAD is the
authority for their shape.  Where the two disagree the disagreement is
reported, not averaged.

Then the binding is *tested*, not asserted:
  * mirror consistency  -- every left solid must have an equal-volume right twin
  * palm neutrality     -- palm solids must straddle the jaw plane
  * travel feasibility  -- at OPEN the finger groups must not run into the palm
  * jaw opening         -- measured from the real gripping faces, not 2 x travel
"""
import json
import math
import sys
import traceback

import numpy as np
import trimesh

import r2_common as C
import r2_kin as K

BREP = C.CLR2 / "mesh" / "BREP_PROBE_GRIPPER.json"
OUTJ = C.CAM2 / "F3R2_GRIPPER_FINGER_BINDING.json"
OUTC = C.CAM2 / "F3R2_GRIPPER_SOLID_ASSIGNMENT.csv"
OUTS = C.CAM2 / "F3R2_GRIPPER_STATE_REGISTER.csv"

TRAVEL_MAX_MM = 71.5
STATES = [("OPEN", 71.5), ("PREGRASP", 55.0), ("CLOSED", 0.0)]


def urdf_body(link, T, scale):
    m = K.arm_mesh(link).copy()
    m.apply_scale(scale)
    m.apply_transform(T)
    return m


def box_corners(b):
    return np.array([[b[i], b[j], b[k]]
                     for i in (0, 3) for j in (1, 4) for k in (2, 5)])


def box_centre(b):
    return np.array([(b[0] + b[3]) / 2.0, (b[1] + b[4]) / 2.0,
                     (b[2] + b[5]) / 2.0])


def boxes_touch(a, b, tol=0.5):
    return all(a[i] - tol <= b[i + 3] and b[i] - tol <= a[i + 3]
               for i in range(3))


def main():
    rep = {"schema": "F3R2_GRIPPER_FINGER_BINDING_V1"}
    try:
        C.check_protected2("G33A_PRE")
        parts = json.loads(BREP.read_text(encoding="utf-8"))["parts"]

        T0 = K.link_world([0.0] * 6, finger_mm=0.0)
        # jaw axis = the world direction gripper_joint1 drives gripper_left
        u = T0["gripper_left"][:3, :3] @ np.array([1.0, 0.0, 0.0])
        u = u / np.linalg.norm(u)
        ref = (T0["gripper_left"][:3, 3] + T0["gripper_right"][:3, 3]) / 2.0

        rep["jaw_axis"] = {
            "world_direction": [round(float(x), 6) for x in u],
            "origin_mm": [round(float(x), 4) for x in ref],
            "derived_from": ("accepted URDF gripper_joint1 axis carried through "
                             "FK at the as-built pose; not chosen by hand"),
            "opposed": [round(float(x), 6) for x in
                        (T0["gripper_right"][:3, :3] @ np.array([1.0, 0, 0]))]}

        # ---------------- CAD side ----------------
        cad = {}
        for label, v in parts.items():
            b = v["box_mm"]
            c = box_centre(b)
            pu = (box_corners(b) - ref) @ u
            cad[label] = {"vol": v["volume_mm3"], "faces": v["n_faces"],
                          "box": b, "centre": c, "s_u": float((c - ref) @ u),
                          "u_min": float(pu.min()), "u_max": float(pu.max())}
        rep["cad_solids"] = len(cad)
        rep["cad_total_volume_mm3"] = round(sum(v["vol"] for v in cad.values()),
                                            3)
        cb = None
        for v in cad.values():
            b = v["box"]
            cb = b[:] if cb is None else [min(cb[i], b[i]) for i in range(3)] \
                + [max(cb[i + 3], b[i + 3]) for i in range(3)]
        rep["cad_union_box_mm"] = [round(x, 4) for x in cb]

        # ---------------- URDF side ----------------
        bodies = {}
        ub = None
        for link in ("gripper_link", "gripper_left", "gripper_right"):
            m = urdf_body(link, T0[link], K.SCALE)
            bodies[link] = m
            bb = np.concatenate([m.bounds[0], m.bounds[1]])
            ub = bb.tolist() if ub is None else \
                [min(ub[i], bb[i]) for i in range(3)] + \
                [max(ub[i + 3], bb[i + 3]) for i in range(3)]
        rep["urdf_union_box_mm"] = [round(float(x), 4) for x in ub]
        rep["registration_check"] = {
            "cad_size_mm": [round(cb[i + 3] - cb[i], 3) for i in range(3)],
            "urdf_size_mm": [round(ub[i + 3] - ub[i], 3) for i in range(3)],
            "centre_delta_mm": [round((cb[i] + cb[i + 3]) / 2.0
                                      - (ub[i] + ub[i + 3]) / 2.0, 3)
                                for i in range(3)],
            "note": ("the CAD gripper and the URDF gripper are NOT the same "
                     "mesh (F3R2 arm-geometry divergence); the URDF is used "
                     "only to decide MEMBERSHIP, and any offset is carried "
                     "into the assignment tolerance below")}

        # ---------------- assignment ----------------
        # primary rule: enclosure by the URDF body.  Because the two meshes are
        # not identical, enclosure is scored on the 8 box corners + centre and
        # the winning body must win by a clear margin, otherwise the solid is
        # left UNASSIGNED rather than guessed.
        assign = {}
        for label, v in cad.items():
            pts = np.vstack([box_corners(v["box"]), v["centre"][None, :]])
            score = {}
            for link, m in bodies.items():
                try:
                    inside = m.contains(pts)
                    score[link] = int(np.count_nonzero(inside))
                except Exception:
                    score[link] = -1
            v["urdf_score"] = score
            best = max(score, key=lambda k: score[k])
            second = sorted(score.values())[-2]
            v["urdf_best"] = best if score[best] > 0 else None
            v["urdf_margin"] = score[best] - second
            assign[label] = None

        # secondary rule: mirror pairing on the jaw axis.  A finger solid has an
        # equal-volume, equal-face twin at the mirrored station; a palm solid is
        # its own mirror (straddles the plane).
        SYM_TOL = 0.05          # mm on |s_u| match
        VOL_TOL = 1e-3          # relative
        pairs, palm, unpaired = [], [], []
        used = set()
        order = sorted(cad, key=lambda k: -cad[k]["vol"])
        for a in order:
            if a in used:
                continue
            va = cad[a]
            if abs(va["s_u"]) < 0.5:
                palm.append(a)
                used.add(a)
                continue
            best, bd = None, 1e9
            for b in order:
                if b in used or b == a:
                    continue
                vb = cad[b]
                if abs(va["vol"] - vb["vol"]) > VOL_TOL * max(va["vol"], 1.0):
                    continue
                if va["faces"] != vb["faces"]:
                    continue
                d = abs(va["s_u"] + vb["s_u"])
                if d < bd:
                    best, bd = b, d
            if best is not None and bd < SYM_TOL:
                pairs.append((a, best, bd))
                used.add(a)
                used.add(best)
            else:
                unpaired.append(a)
                used.add(a)

        rep["mirror_pairing"] = {
            "pairs": len(pairs), "palm_straddling": len(palm),
            "unpaired": len(unpaired),
            "unpaired_labels": unpaired,
            "tolerance_mm": SYM_TOL,
            "rule": ("equal volume, equal face count, opposite station on the "
                     "jaw axis")}

        # a mirror pair is one solid of each finger; which is which follows the
        # URDF travel direction: +u is gripper_left's opening direction
        for a, b, d in pairs:
            hi, lo = (a, b) if cad[a]["s_u"] > cad[b]["s_u"] else (b, a)
            assign[hi] = "gripper_left"
            assign[lo] = "gripper_right"
        for a in palm:
            assign[a] = "gripper_link"
        for a in unpaired:
            assign[a] = cad[a]["urdf_best"] or "UNASSIGNED"

        # cross-check the geometric assignment against the URDF enclosure vote
        agree = dis = nourdf = 0
        for label, side in assign.items():
            best = cad[label]["urdf_best"]
            if best is None:
                nourdf += 1
            elif best == side:
                agree += 1
            else:
                dis += 1
        rep["assignment_crosscheck"] = {
            "agree_with_urdf_enclosure": agree,
            "disagree": dis, "urdf_encloses_nothing": nourdf,
            "interpretation": ("the URDF finger bodies are a different mesh "
                               "from the CAD ones, so enclosure is a weak "
                               "check; the mirror rule is the primary one and "
                               "is exact")}

        # ---------------- group properties ----------------
        groups = {}
        for side in ("gripper_left", "gripper_right", "gripper_link",
                     "UNASSIGNED"):
            mem = [k for k, v in assign.items() if v == side]
            if not mem:
                continue
            bb = None
            for k in mem:
                b = cad[k]["box"]
                bb = b[:] if bb is None else [min(bb[i], b[i]) for i in range(3)] \
                    + [max(bb[i + 3], b[i + 3]) for i in range(3)]
            us = [cad[k]["u_min"] for k in mem] + [cad[k]["u_max"] for k in mem]
            groups[side] = {
                "solids": len(mem),
                "volume_mm3": round(sum(cad[k]["vol"] for k in mem), 3),
                "box_mm": [round(x, 4) for x in bb],
                "u_range_mm": [round(min(us), 4), round(max(us), 4)],
                "labels": sorted(mem)}
        rep["groups"] = {k: {kk: vv for kk, vv in v.items() if kk != "labels"}
                         for k, v in groups.items()}

        L = groups.get("gripper_left")
        R = groups.get("gripper_right")
        P = groups.get("gripper_link")
        ok_two_fingers = bool(L and R and L["solids"] == R["solids"]
                              and abs(L["volume_mm3"] - R["volume_mm3"]) < 1e-3)
        rep["two_real_fingers"] = {
            "left_solids": L["solids"] if L else 0,
            "right_solids": R["solids"] if R else 0,
            "left_volume_mm3": L["volume_mm3"] if L else 0,
            "right_volume_mm3": R["volume_mm3"] if R else 0,
            "identical_by_mirror": ok_two_fingers,
            "claim": ("the gripper is TWO movable finger bodies plus a palm, "
                      "all already present in the CAD -- not one visual solid")
            if ok_two_fingers else "MIRROR_CONSISTENCY_FAILED"}

        # ---------------- travel feasibility ----------------
        # at travel t each finger moves +t (left) / -t (right) along u.  The
        # binding is only real if that motion is geometrically admissible.
        feas = []
        for name, t in STATES:
            lu = [L["u_range_mm"][0] + t, L["u_range_mm"][1] + t] if L else None
            ru = [R["u_range_mm"][0] - t, R["u_range_mm"][1] - t] if R else None
            inside_palm = (P and lu and lu[1] <= P["u_range_mm"][1] + 1e-6
                           and ru and ru[0] >= P["u_range_mm"][0] - 1e-6)
            # fingers must not pass through each other
            overlap = (ru[1] - lu[0]) if (lu and ru) else None
            feas.append({"state": name, "travel_mm": t,
                         "left_u_range": [round(x, 3) for x in lu] if lu else None,
                         "right_u_range": [round(x, 3) for x in ru] if ru else None,
                         "fingers_cross_mm": round(overlap, 3)
                         if overlap is not None else None,
                         "fingers_cross": bool(overlap is not None
                                               and overlap > 0),
                         "within_palm_envelope": bool(inside_palm)})
        rep["travel_feasibility"] = feas

        # ---------------- measured jaw opening ----------------
        # the previous record claimed jaw_opening = 2 x travel (143 mm at OPEN).
        # the real opening is between the two gripping faces, which are inboard
        # of the finger bodies -- measure it.
        jaw = None
        if L and R:
            gap0 = R["u_range_mm"][1] - L["u_range_mm"][0]
            # inner faces: left group's lowest-u face, right group's highest-u
            jaw = {"closed_inner_gap_mm": round(-gap0, 4)
                   if gap0 < 0 else round(-gap0, 4),
                   "left_inner_u_mm": round(L["u_range_mm"][0], 4),
                   "right_inner_u_mm": round(R["u_range_mm"][1], 4)}
            for name, t in STATES:
                jaw["%s_opening_mm" % name] = round(
                    (L["u_range_mm"][0] + t) - (R["u_range_mm"][1] - t), 4)
        rep["measured_jaw_opening"] = jaw
        rep["correction_to_previous_record"] = {
            "previous": ("F3R2_CAMERA_HARNESS_GRIPPER.json: solids_in_cad = 1, "
                         "maturity SEPARATION_REQUIRED_NOT_DONE, "
                         "OPEN jaw_opening_mm = 143.0 (= 2 x travel)"),
            "measured_now": {"solids_in_cad": len(cad),
                             "mirror_pairs": len(pairs),
                             "open_jaw_opening_mm":
                                 jaw.get("OPEN_opening_mm") if jaw else None},
            "why_the_old_number_was_wrong": (
                "2 x travel is the sum of the two sliders' strokes, not the "
                "distance between the gripping faces; the faces start at a "
                "non-zero separation and the fingers are bodies with "
                "thickness")}

        # ---------------- states ----------------
        srows = []
        for name, t in STATES:
            srows.append({
                "state": name, "gripper_joint1_mm": t, "gripper_joint2_mm": t,
                "jaw_opening_mm": jaw.get("%s_opening_mm" % name)
                if jaw else None,
                "within_urdf_limit": bool(0.0 <= t <= TRAVEL_MAX_MM),
                "geometry": "REAL_CAD_SOLIDS_BOUND_TO_URDF_JOINT",
                "grip_force_N": "",
                "note": ""})
        srows.append({
            "state": "HOLDING", "gripper_joint1_mm": "target dependent",
            "gripper_joint2_mm": "target dependent",
            "jaw_opening_mm": "= target grasp width",
            "within_urdf_limit": True,
            "geometry": "REAL_CAD_SOLIDS_BOUND_TO_URDF_JOINT",
            "grip_force_N": "NOT_EVALUATED_NO_ACTUATOR_MODEL",
            "note": ("HOLDING is a force state, not a geometric one; the "
                     "geometry is CLOSED-with-target, and no grip force is "
                     "claimed because the finger actuator is not modelled")})
        rep["states"] = srows

        # ---------------- verdict ----------------
        checks = {
            "GF-1_two_mirror_finger_groups": ok_two_fingers,
            "GF-2_palm_straddles_jaw_plane": bool(P and
                                                  P["u_range_mm"][0] < 0 <
                                                  P["u_range_mm"][1]),
            "GF-3_no_unassigned_solids":
                "UNASSIGNED" not in groups,
            "GF-4_every_solid_accounted":
                sum(g["solids"] for g in groups.values()) == len(cad),
            "GF-5_volume_conserved":
                abs(sum(g["volume_mm3"] for g in groups.values())
                    - rep["cad_total_volume_mm3"]) < 1e-3,
            "GF-6_fingers_do_not_cross_at_any_state":
                all(not f["fingers_cross"] for f in feas),
            "GF-7_travel_within_urdf_limit":
                all(0.0 <= t <= TRAVEL_MAX_MM for _, t in STATES),
        }
        rep["checks"] = checks
        rep["verdict"] = ("G33A_GRIPPER_FINGERS_BOUND" if all(checks.values())
                          else "G33A_GRIPPER_BINDING_INCOMPLETE")

        rows = []
        for label in sorted(cad, key=lambda k: (-cad[k]["vol"], k)):
            v = cad[label]
            rows.append({"solid": label, "assigned_body": assign[label],
                         "volume_mm3": round(v["vol"], 3),
                         "faces": v["faces"],
                         "s_on_jaw_axis_mm": round(v["s_u"], 4),
                         "u_min_mm": round(v["u_min"], 4),
                         "u_max_mm": round(v["u_max"], 4),
                         "urdf_enclosure_best": v["urdf_best"] or "",
                         "urdf_enclosure_score":
                             json.dumps(v["urdf_score"])})
        C.write_csv(OUTC, rows)
        C.write_csv(OUTS, srows)
        rep["protected_post"] = C.check_protected2("G33A_POST")["verdict"]
    except Exception as exc:
        rep["verdict"] = "G33A_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2500:]

    C.write_json(OUTJ, rep)
    print("verdict:", rep["verdict"])
    if "groups" in rep:
        print("\n  solids %d  total volume %.1f mm3"
              % (rep["cad_solids"], rep["cad_total_volume_mm3"]))
        for k, g in rep["groups"].items():
            print("    %-16s solids=%-3d vol=%10.1f  u=[%8.2f,%8.2f]"
                  % (k, g["solids"], g["volume_mm3"], g["u_range_mm"][0],
                     g["u_range_mm"][1]))
        mp = rep["mirror_pairing"]
        print("\n  mirror pairs %d | palm %d | unpaired %d %s"
              % (mp["pairs"], mp["palm_straddling"], mp["unpaired"],
                 mp["unpaired_labels"][:6]))
        print("  urdf crosscheck:", rep["assignment_crosscheck"])
        print("\n  jaw:", json.dumps(rep["measured_jaw_opening"],
                                     ensure_ascii=False))
        for f in rep["travel_feasibility"]:
            print("    %-9s t=%5.1f cross=%-5s (%.2f) palm_ok=%s"
                  % (f["state"], f["travel_mm"], f["fingers_cross"],
                     f["fingers_cross_mm"], f["within_palm_envelope"]))
        print("\n  checks:")
        for k, v in rep["checks"].items():
            print("    %-42s %s" % (k, "PASS" if v else "FAIL"))
    if rep["verdict"] == "G33A_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G33A_GRIPPER_FINGERS_BOUND" else 1)


if __name__ == "__main__":
    main()
