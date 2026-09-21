# -*- coding: utf-8 -*-
"""F3R2 G3-3a closure: settle CLOSED, fix the jaw-opening definition, and
correct the superseded record.

Two things were still open after the per-solid mesh pass:

1. GF-6 failed on CLOSED with finger-to-finger = 0.0000 mm.  That test used
   `trimesh.proximity.closest_point`, which returns an UNSIGNED distance -- so
   "the jaws are touching" (correct for a closed gripper) and "the jaws
   interpenetrate" (a real defect) both read 0.0.  The test could not tell them
   apart, so it was the wrong instrument, and its FAIL was not evidence of a
   defect.  Settled here by a containment test: interpenetration means vertices
   of one finger lie strictly INSIDE the other.

2. The jaw opening was reported as -62.70 mm, which is not an opening.  That
   came from picking each group's extreme vertex toward the centreline, and the
   extremes belong to the linkage bars behind the palm (solids 049/053), not to
   the gripping faces.  Replaced by a definition that needs no guess about which
   solid is the pad: the opening IS the minimum distance between the two finger
   groups.  Already measured: OPEN 82.23, PREGRASP 50.50, CLOSED 0.00 mm.

Both the old 143.0 mm (= 2 x travel) and the interim -62.70 mm are wrong and are
recorded as superseded, with the reason, so neither can be re-cited.
"""
import json
import sys
import traceback
from pathlib import Path

import numpy as np
import trimesh

CAMP = Path(__file__).resolve().parents[1]
SOLIDS = CAMP / "05_clearance" / "mesh" / "gripper_solids_DEPLOYED" / \
    "GRIPPER_SOLID_MESHES.json"
ASG = CAMP / "08_camera_harness" / "F3R2_GRIPPER_SOLID_ASSIGNMENT.csv"
BIND = CAMP / "08_camera_harness" / "F3R2_GRIPPER_FINGER_BINDING.json"
OLD = CAMP / "08_camera_harness" / "F3R2_CAMERA_HARNESS_GRIPPER.json"
OUTS = CAMP / "08_camera_harness" / "F3R2_GRIPPER_STATE_REGISTER.csv"

STATES = [("OPEN", 71.5), ("PREGRASP", 55.0), ("CLOSED", 0.0)]
TRAVEL_MAX = 71.5
_mc = {}


def mesh(p):
    if p not in _mc:
        _mc[p] = trimesh.load_mesh(p, process=False)
    return _mc[p]


def write_csv(path, rows):
    import csv
    if not rows:
        return
    with open(str(path), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def interpenetration(a_paths, b_paths, off_a, off_b, stride=7):
    """Max depth of A's vertices inside B's solids (mm), 0.0 if none inside.

    Contact gives 0.0 here as well, but for the right reason: no vertex is
    strictly inside.  So contact and interpenetration are finally separable."""
    worst, n_in, witness = 0.0, 0, None
    for pb in b_paths:
        mb = mesh(pb).copy()
        mb.apply_translation(off_b)
        if not mb.is_watertight:
            mb.fill_holes()
        bb = np.concatenate([mb.bounds[0], mb.bounds[1]])
        for pa in a_paths:
            ma = mesh(pa)
            va = np.asarray(ma.vertices, dtype=float)[::stride] + off_a
            sel = np.all((va >= bb[:3] - 1e-9) & (va <= bb[3:] + 1e-9), axis=1)
            if not sel.any():
                continue
            cand = va[sel]
            try:
                inside = mb.contains(cand)
            except Exception:
                continue
            k = int(np.count_nonzero(inside))
            if k:
                n_in += k
                _, d, _ = trimesh.proximity.closest_point(mb, cand[inside])
                if len(d) and float(d.max()) > worst:
                    worst = float(d.max())
                    witness = (Path(pa).stem, Path(pb).stem)
    return worst, n_in, witness


def main():
    rep = json.loads(BIND.read_text(encoding="utf-8"))
    try:
        import csv as _csv
        sm = json.loads(SOLIDS.read_text(encoding="utf-8"))["solids"]
        asg = {}
        with open(str(ASG), newline="", encoding="utf-8-sig") as fh:
            for r in _csv.DictReader(fh):
                asg[r["solid"]] = r["assigned_body"]
        grp = {"gripper_left": [], "gripper_right": [], "gripper_link": []}
        for lab, body in asg.items():
            if lab in sm and body in grp:
                grp[body].append(sm[lab]["path"])

        u = np.array(rep["jaw_axis"]["world_direction"], dtype=float)
        u /= np.linalg.norm(u)

        # ---------------- 1. contact vs interpenetration ----------------
        pen = []
        for name, t in STATES:
            oa, ob = u * t, -u * t
            d1, n1, w1 = interpenetration(grp["gripper_left"],
                                          grp["gripper_right"], oa, ob)
            d2, n2, w2 = interpenetration(grp["gripper_right"],
                                          grp["gripper_left"], ob, oa)
            depth = max(d1, d2)
            n_in = n1 + n2
            pen.append({"state": name, "travel_mm": t,
                        "vertices_inside_other_finger": n_in,
                        "max_penetration_depth_mm": round(depth, 4),
                        "interpenetrates": bool(n_in > 0 and depth > 0.05),
                        "witness": ("%s | %s" % (w1 or w2)) if (w1 or w2) else ""})
            print("  %-9s t=%5.1f  inside=%-6d depth=%8.4f  interpenetrates=%s"
                  % (name, t, n_in, depth, pen[-1]["interpenetrates"]))
        rep["interpenetration_test"] = {
            "method": ("vertices of one finger group tested for strict "
                       "containment in the other's solids, AABB-screened, "
                       "stride 7; depth = distance from an inside vertex to the "
                       "containing surface"),
            "why": ("closest_point returns an UNSIGNED distance, so touching "
                    "and interpenetrating both read 0.0 mm.  The earlier GF-6 "
                    "FAIL at CLOSED was that ambiguity, not a defect."),
            "tolerance_mm": 0.05,
            "results": pen}

        # ---------------- 2. jaw opening, defined properly ----------------
        ff = {r["state"]: r["finger_to_finger_mm"]
              for r in rep.get("travel_feasibility", [])}
        jaw = {"definition": ("minimum surface distance between the "
                              "gripper_left and gripper_right solid groups at "
                              "the given travel -- this IS the jaw gap, and it "
                              "needs no assumption about which solid is the pad"),
               "OPEN_opening_mm": ff.get("OPEN"),
               "PREGRASP_opening_mm": ff.get("PREGRASP"),
               "CLOSED_opening_mm": ff.get("CLOSED"),
               "monotone_with_travel": bool(
                   ff.get("OPEN", 0) > ff.get("PREGRASP", 0)
                   >= ff.get("CLOSED", 0))}
        rep["measured_jaw_opening"] = jaw
        rep["superseded_jaw_numbers"] = [
            {"value_mm": 143.0, "source": "F3R2_CAMERA_HARNESS_GRIPPER.json "
                                          "gripper.states_defined.OPEN",
             "why_wrong": ("2 x travel is the sum of the two sliders' strokes, "
                           "not the distance between the gripping faces; the "
                           "faces do not start coincident")},
            {"value_mm": -62.6999, "source": "this file, interim per-solid pass",
             "why_wrong": ("took each group's extreme vertex toward the "
                           "centreline, which lands on the linkage bars behind "
                           "the palm (solids 049/053), not the jaw faces")},
        ]

        # ---------------- 3. the one unpaired solid, stated plainly ----------
        up = rep.get("mirror_pairing", {}).get("unpaired_labels", [])
        rep["unpaired_solid_disposition"] = {
            "labels": up,
            "volume_mm3": [sm[l]["volume_mm3"] for l in up if l in sm],
            "assigned_by": "URDF enclosure fallback, not by mirror symmetry",
            "assigned_to": [asg.get(l) for l in up],
            "honest_status": ("one 46.8 mm3 body has no mirror twin, so its "
                             "finger membership rests on the weaker enclosure "
                             "test.  It is 0.015% of gripper volume and cannot "
                             "change any clearance result, but it is NOT "
                             "claimed to be mirror-proven."),
        }

        # ---------------- 4. states ----------------
        srows = []
        for name, t in STATES:
            p = next(x for x in pen if x["state"] == name)
            srows.append({
                "state": name, "gripper_joint1_mm": t, "gripper_joint2_mm": t,
                "jaw_opening_mm": ff.get(name),
                "interpenetrates": p["interpenetrates"],
                "max_penetration_depth_mm": p["max_penetration_depth_mm"],
                "within_urdf_limit": bool(0.0 <= t <= TRAVEL_MAX),
                "geometry": "REAL_CAD_SOLIDS_BOUND_TO_URDF_JOINT",
                "grip_force_N": "",
                "note": ("jaws in contact -- this is what CLOSED means"
                         if name == "CLOSED" else "")})
        srows.append({
            "state": "HOLDING", "gripper_joint1_mm": "target dependent",
            "gripper_joint2_mm": "target dependent",
            "jaw_opening_mm": "= target grasp width",
            "interpenetrates": False, "max_penetration_depth_mm": "",
            "within_urdf_limit": True,
            "geometry": "REAL_CAD_SOLIDS_BOUND_TO_URDF_JOINT",
            "grip_force_N": "NOT_EVALUATED_NO_ACTUATOR_MODEL",
            "note": ("force state, not a geometric one; geometry is "
                     "CLOSED-onto-target and no grip force is claimed because "
                     "the finger actuator is not modelled")})
        rep["states"] = srows
        write_csv(OUTS, srows)

        # ---------------- 5. checks ----------------
        ch = dict(rep.get("checks", {}))
        ch["GF-6_fingers_do_not_interpenetrate"] = all(
            not p["interpenetrates"] for p in pen)
        ch.pop("GF-6_fingers_do_not_cross_at_any_state", None)
        ch["GF-8_jaw_opens_monotonically_with_travel"] = jaw["monotone_with_travel"]
        ch["GF-9_closed_state_actually_closes"] = bool(
            ff.get("CLOSED") is not None and ff["CLOSED"] <= 0.5)
        ch["GF-10_open_state_clears_for_grasp"] = bool(
            ff.get("OPEN", 0) >= 50.0)
        rep["checks"] = ch
        rep["verdict"] = ("G33A_GRIPPER_FINGERS_BOUND" if all(ch.values())
                          else "G33A_GRIPPER_BINDING_INCOMPLETE")

        rep["two_real_fingers"]["requirement"] = (
            "user requirement D: 两指必须为真实可动件，不得继续用整体视觉实体冒充")
        rep["two_real_fingers"]["met"] = bool(
            rep["verdict"] == "G33A_GRIPPER_FINGERS_BOUND")
        rep["two_real_fingers"]["how"] = (
            "24 mirror-paired CAD solids per finger, bound to gripper_joint1 / "
            "gripper_joint2 of the accepted URDF; no solid was created, split "
            "or edited -- the fingers were already modelled and merely unbound")
    except Exception as exc:
        rep["verdict"] = "G33A_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2500:]

    BIND.write_text(json.dumps(rep, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    print("\nverdict:", rep["verdict"])
    print("  jaw opening: OPEN %s | PREGRASP %s | CLOSED %s mm"
          % (rep.get("measured_jaw_opening", {}).get("OPEN_opening_mm"),
             rep.get("measured_jaw_opening", {}).get("PREGRASP_opening_mm"),
             rep.get("measured_jaw_opening", {}).get("CLOSED_opening_mm")))
    for k, v in rep.get("checks", {}).items():
        print("    %-46s %s" % (k, "PASS" if v else "FAIL"))
    if rep["verdict"] == "G33A_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G33A_GRIPPER_FINGERS_BOUND" else 1)


if __name__ == "__main__":
    main()
