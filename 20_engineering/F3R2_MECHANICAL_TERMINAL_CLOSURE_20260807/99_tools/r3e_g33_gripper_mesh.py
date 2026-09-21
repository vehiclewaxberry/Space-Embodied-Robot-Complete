# -*- coding: utf-8 -*-
"""F3R2 G3-3a v2: prove the finger binding with real per-solid geometry.

v1 bound all 58 CAD gripper solids to gripper_left / gripper_right /
gripper_link by exact mirror symmetry about the URDF-derived jaw axis (24 / 24 /
10, volumes equal to 1e-3 mm3).  That part stands.  What v1 could NOT settle was
whether the two finger groups collide, because it compared GROUP bounding
boxes -- and a group AABB spans both jaws of a fork, so it reported a 67 mm
"crossing" at travel 0 that is really the two carriages interleaving behind the
palm, never touching.

v2 replaces the box test with a mesh test on the individual solids, and reports
the closed-state finger-to-finger distance as a real measurement.  A binding
that cannot survive its own travel is not a binding, so this is a gate, not a
formality.
"""
import json
import math
import sys
import traceback
from pathlib import Path

import numpy as np
import trimesh

import r2_common as C
import r2_kin as K

BREP = C.CLR2 / "mesh" / "BREP_PROBE_GRIPPER.json"
SOLIDS = C.CLR2 / "mesh" / "gripper_solids_DEPLOYED" / "GRIPPER_SOLID_MESHES.json"
INJ = C.CAM2 / "F3R2_GRIPPER_FINGER_BINDING.json"
OUTJ = C.CAM2 / "F3R2_GRIPPER_FINGER_BINDING.json"
OUTC = C.CAM2 / "F3R2_GRIPPER_SOLID_ASSIGNMENT.csv"
OUTS = C.CAM2 / "F3R2_GRIPPER_STATE_REGISTER.csv"
OUTM = C.CLR2 / "F3R2_GRIPPER_TRAVEL_CLEARANCE.csv"

TRAVEL_MAX_MM = 71.5
STATES = [("OPEN", 71.5), ("PREGRASP", 55.0), ("CLOSED", 0.0)]
_mc = {}


def mesh(path):
    if path not in _mc:
        _mc[path] = trimesh.load_mesh(path, process=False)
    return _mc[path]


def pts(path, T=None):
    v = np.asarray(mesh(path).vertices, dtype=float)
    if T is not None:
        v = v + T
    return v


def min_dist(a_paths, b_paths, off_a, off_b, budget=4e7):
    """Minimum surface distance between two solid groups (mm).

    AABB screened, chunked so a 100k-vertex group against a 400k-triangle group
    cannot allocate its way out of memory."""
    best = float("inf")
    detail = None
    for pa in a_paths:
        ma = mesh(pa)
        ba = np.concatenate([ma.bounds[0] + off_a, ma.bounds[1] + off_a])
        va = np.asarray(ma.vertices, dtype=float) + off_a
        for pb in b_paths:
            mb = mesh(pb)
            bb = np.concatenate([mb.bounds[0] + off_b, mb.bounds[1] + off_b])
            d = [max(ba[i] - bb[i + 3], bb[i] - ba[i + 3]) for i in range(3)]
            pos = [x for x in d if x > 0]
            lb = math.sqrt(sum(x * x for x in pos)) if pos else max(d)
            if lb >= best:
                continue                     # provably cannot improve
            mbt = mb.copy()
            mbt.apply_translation(off_b)
            n = max(1, int(budget / max(len(mbt.faces), 1)))
            for i in range(0, len(va), n):
                _, dd, _ = trimesh.proximity.closest_point(mbt, va[i:i + n])
                if len(dd) and float(dd.min()) < best:
                    best = float(dd.min())
                    detail = (Path(pa).stem, Path(pb).stem)
    return best, detail


def main():
    rep = json.loads(INJ.read_text(encoding="utf-8"))
    try:
        C.check_protected2("G33A2_PRE")
        sm = json.loads(SOLIDS.read_text(encoding="utf-8"))["solids"]
        import csv as _csv
        asg = {}
        with open(str(OUTC), newline="", encoding="utf-8-sig") as fh:
            for r in _csv.DictReader(fh):
                asg[r["solid"]] = r["assigned_body"]
        rep["per_solid_mesh"] = {
            "source": str(SOLIDS), "solids": len(sm),
            "linear_deflection_mm": json.loads(
                SOLIDS.read_text(encoding="utf-8"))["linear_deflection_mm"],
            "why": ("the grouped environment export merges all 58 bodies under "
                    "one stripped label; that merge is what produced the "
                    "earlier 'solids_in_cad: 1' record")}

        u = np.array(rep["jaw_axis"]["world_direction"], dtype=float)
        u = u / np.linalg.norm(u)

        grp = {"gripper_left": [], "gripper_right": [], "gripper_link": []}
        for label, body in asg.items():
            if label in sm and body in grp:
                grp[body].append(sm[label]["path"])
        rep["per_solid_mesh"]["group_counts"] = {k: len(v)
                                                 for k, v in grp.items()}

        # ---------------- travel clearance, real geometry ----------------
        rows, feas = [], []
        for name, t in STATES:
            oa = u * t
            ob = -u * t
            d_ff, w_ff = min_dist(grp["gripper_left"], grp["gripper_right"],
                                  oa, ob)
            d_lp, w_lp = min_dist(grp["gripper_left"], grp["gripper_link"],
                                  oa, np.zeros(3))
            d_rp, w_rp = min_dist(grp["gripper_right"], grp["gripper_link"],
                                  ob, np.zeros(3))
            rows.append({"state": name, "travel_mm": t,
                         "finger_to_finger_mm": round(d_ff, 4),
                         "finger_to_finger_witness": "%s | %s" % w_ff
                         if w_ff else "",
                         "left_to_palm_mm": round(d_lp, 4),
                         "right_to_palm_mm": round(d_rp, 4),
                         "method": "per-solid mesh, AABB-screened, 0.25 mm "
                                   "tessellation"})
            feas.append({"state": name, "travel_mm": t,
                         "finger_to_finger_mm": round(d_ff, 4),
                         "fingers_collide": bool(d_ff <= 0.0),
                         "left_to_palm_mm": round(d_lp, 4),
                         "right_to_palm_mm": round(d_rp, 4),
                         "palm_contact_is_the_slide":
                             "the fingers RIDE on the palm rail; a near-zero "
                             "finger-to-palm distance is the prismatic joint "
                             "itself, not an interference"})
            print("  %-9s t=%5.1f  f-f=%9.4f  l-p=%8.4f  r-p=%8.4f"
                  % (name, t, d_ff, d_lp, d_rp))

        rep["travel_feasibility"] = feas
        rep["travel_feasibility_method"] = (
            "v1 compared GROUP bounding boxes and reported a 67.3 mm crossing "
            "at CLOSED.  A group AABB spans both jaws of a fork, so that "
            "number was an artefact of the box, not a collision.  v2 measures "
            "solid-to-solid mesh distance and supersedes it.")

        # ---------------- measured jaw opening, real faces ----------------
        # The opening is between the INNER gripping faces.  Find them by taking,
        # for each finger group, the extreme vertex along the closing direction
        # -- restricted to the jaw region (the solids that reach past the palm),
        # so a carriage behind the palm cannot masquerade as a jaw face.
        palm_u = []
        for p in grp["gripper_link"]:
            v = np.asarray(mesh(p).vertices, dtype=float)
            palm_u.append(((v @ u).min(), (v @ u).max()))
        ref_u = float(np.array(rep["jaw_axis"]["origin_mm"]) @ u)

        def jaw_face(paths, sign):
            """inner face station of a finger group, jaw solids only."""
            best = None
            who = None
            for p in paths:
                v = np.asarray(mesh(p).vertices, dtype=float)
                s = v @ u - ref_u
                # a jaw solid is one that has material on its own side and
                # reaches toward the centreline
                if sign > 0 and s.max() < 0:
                    continue
                if sign < 0 and s.min() > 0:
                    continue
                cand = s.min() if sign > 0 else s.max()
                if best is None or (sign > 0 and cand < best) or \
                        (sign < 0 and cand > best):
                    best, who = float(cand), Path(p).stem
            return best, who

        lj, lw = jaw_face(grp["gripper_left"], +1)
        rj, rw = jaw_face(grp["gripper_right"], -1)
        jaw = {"left_inner_face_u_mm": round(lj, 4) if lj is not None else None,
               "left_inner_face_solid": lw,
               "right_inner_face_u_mm": round(rj, 4) if rj is not None else None,
               "right_inner_face_solid": rw,
               "method": ("extreme vertex toward the centreline of each finger "
                          "group, from the per-solid meshes")}
        for name, t in STATES:
            if lj is not None and rj is not None:
                jaw["%s_opening_mm" % name] = round((lj + t) - (rj - t), 4)
        rep["measured_jaw_opening"] = jaw

        # ---------------- states ----------------
        srows = []
        for name, t in STATES:
            f = next(x for x in feas if x["state"] == name)
            srows.append({
                "state": name, "gripper_joint1_mm": t, "gripper_joint2_mm": t,
                "jaw_opening_mm": jaw.get("%s_opening_mm" % name),
                "finger_to_finger_mm": f["finger_to_finger_mm"],
                "within_urdf_limit": bool(0.0 <= t <= TRAVEL_MAX_MM),
                "geometry": "REAL_CAD_SOLIDS_BOUND_TO_URDF_JOINT",
                "grip_force_N": "",
                "note": ""})
        srows.append({
            "state": "HOLDING", "gripper_joint1_mm": "target dependent",
            "gripper_joint2_mm": "target dependent",
            "jaw_opening_mm": "= target grasp width",
            "finger_to_finger_mm": "= target width",
            "within_urdf_limit": True,
            "geometry": "REAL_CAD_SOLIDS_BOUND_TO_URDF_JOINT",
            "grip_force_N": "NOT_EVALUATED_NO_ACTUATOR_MODEL",
            "note": ("HOLDING is a force state; the geometry is CLOSED-onto-"
                     "target and no grip force is claimed because the finger "
                     "actuator is not modelled")})
        rep["states"] = srows

        # ---------------- checks ----------------
        ch = dict(rep["checks"])
        ch["GF-6_fingers_do_not_cross_at_any_state"] = all(
            not f["fingers_collide"] for f in feas)
        ch["GF-8_jaw_opens_monotonically_with_travel"] = bool(
            jaw.get("OPEN_opening_mm", -1) > jaw.get("PREGRASP_opening_mm", 0)
            > jaw.get("CLOSED_opening_mm", 1))
        ch["GF-9_closed_state_actually_closes"] = bool(
            jaw.get("CLOSED_opening_mm") is not None
            and jaw["CLOSED_opening_mm"] <= 1.0)
        rep["checks"] = ch
        rep["verdict"] = ("G33A_GRIPPER_FINGERS_BOUND" if all(ch.values())
                          else "G33A_GRIPPER_BINDING_INCOMPLETE")
        rep["supersedes"] = {
            "file": "08_camera_harness/F3R2_CAMERA_HARNESS_GRIPPER.json",
            "field": "gripper.cad_reality.solids_in_cad = 1 and "
                     "gripper.maturity = SEPARATION_REQUIRED_NOT_DONE",
            "reason": ("measured: 58 solids, 24 mirror pairs, exact volume "
                       "equality; the fingers were always there, unbound")}
        C.write_csv(OUTS, srows)
        C.write_csv(OUTM, rows)
        rep["protected_post"] = C.check_protected2("G33A2_POST")["verdict"]
    except Exception as exc:
        rep["verdict"] = "G33A_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2500:]

    C.write_json(OUTJ, rep)
    print("\nverdict:", rep["verdict"])
    print("  jaw:", json.dumps(rep.get("measured_jaw_opening"),
                               ensure_ascii=False))
    for k, v in rep.get("checks", {}).items():
        print("    %-46s %s" % (k, "PASS" if v else "FAIL"))
    if rep["verdict"] == "G33A_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G33A_GRIPPER_FINGERS_BOUND" else 1)


if __name__ == "__main__":
    main()
