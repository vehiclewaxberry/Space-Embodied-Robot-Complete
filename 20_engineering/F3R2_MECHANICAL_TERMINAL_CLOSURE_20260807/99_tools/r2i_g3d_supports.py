# -*- coding: utf-8 -*-
"""F3R2 G3-D: find the REAL counter-faces for G07 / G08 / Mid and define
supports that actually touch the arm.

The three existing blocks are placeholders: the B-rep probe shows 10 planar
faces each, no cradle, no pad, no locating feature -- a rectangular box whose
top plane happens to sit under the arm.  They are therefore demoted to
ENVELOPE_REFERENCE_ONLY, and real supports are defined against the arm surface
that is genuinely above them.

Counter-faces are found from the arm MESH, not from bounding boxes: for each
saddle footprint the arm vertices lying over it are collected and the lowest
ones are fitted, which gives the true local surface height, its slope and its
width.  A bbox would have given the corner of a link that is nowhere near the
saddle -- that is exactly the fail-open this replaces.
"""
import json
import sys
import traceback

import numpy as np
import trimesh

import r2_common as C
import r2_pose as P

OUTJ = C.SUP2 / "F3R2_STOW_SUPPORT_DEFINITION.json"
OUTC = C.SUP2 / "F3R2_STOW_SUPPORT_PART_LIST.csv"
CFJ = C.SUP2 / "F3R2_SUPPORT_COUNTERFACE_SEARCH.json"

SADDLE_TAG = {"Aft_Saddle": "G07", "Fwd_Saddle": "G08", "Mid_Saddle": "MID"}
AL = 2.70e-3
VESPEL = 1.43e-3
TI = 4.43e-3
# design intent
PAD_STACK_MM = 3.0        # G07/G08 nominal support: pad presses the link
MID_GAP_MM = 2.00         # Mid is a backup: nominal 2.00 mm gap, zero force


def arm_points_over(footprint, arms, margin=0.0):
    """Every arm vertex whose (x, y) lies over a saddle footprint."""
    x0, y0, _, x1, y1, _ = footprint
    out = []
    for cad, a in arms.items():
        m = trimesh.load_mesh(a["path"], process=False)
        v = np.asarray(m.vertices, dtype=float)
        sel = ((v[:, 0] >= x0 - margin) & (v[:, 0] <= x1 + margin)
               & (v[:, 1] >= y0 - margin) & (v[:, 1] <= y1 + margin))
        if sel.any():
            out.append((cad, v[sel]))
    return out


def analyse(tag, saddle, arms):
    """Real counter-face description above one saddle."""
    fp = saddle["box"]
    top_z = float(fp[5])
    got = arm_points_over(fp, arms)
    if not got:
        return {"saddle": tag, "status": "NO_ARM_MATERIAL_OVER_FOOTPRINT",
                "footprint_mm": [round(v, 3) for v in fp],
                "saddle_top_z_mm": round(top_z, 3),
                "meaning": ("nothing to support: this saddle does not lie "
                            "under the arm in the stow pose")}
    # only points ABOVE the saddle top can be supported by it
    per = []
    for cad, v in got:
        above = v[v[:, 2] >= top_z - 1.0]
        if not len(above):
            continue
        lo = float(above[:, 2].min())
        band = above[above[:, 2] <= lo + 2.0]
        per.append({
            "arm_part": cad,
            "n_points_over_footprint": int(len(v)),
            "n_points_above_saddle_top": int(len(above)),
            "lowest_z_mm": round(lo, 4),
            "gap_to_saddle_top_mm": round(lo - top_z, 4),
            "contact_band_x_mm": [round(float(band[:, 0].min()), 3),
                                  round(float(band[:, 0].max()), 3)],
            "contact_band_y_mm": [round(float(band[:, 1].min()), 3),
                                  round(float(band[:, 1].max()), 3)],
            "contact_band_width_y_mm": round(
                float(band[:, 1].max() - band[:, 1].min()), 3),
            "local_z_spread_mm": round(
                float(above[:, 2].max() - above[:, 2].min()), 3)})
    per.sort(key=lambda d: d["lowest_z_mm"])
    if not per:
        return {"saddle": tag, "status": "ARM_BELOW_SADDLE_TOP_ONLY",
                "footprint_mm": [round(v, 3) for v in fp],
                "saddle_top_z_mm": round(top_z, 3),
                "meaning": ("arm material exists over the footprint but all "
                            "of it is BELOW the block top -- the block is not "
                            "supporting, it is intersecting or beside it")}
    best = per[0]
    return {"saddle": tag, "status": "COUNTERFACE_FOUND",
            "footprint_mm": [round(v, 3) for v in fp],
            "saddle_top_z_mm": round(top_z, 3),
            "supported_arm_part": best["arm_part"],
            "counterface": best,
            "other_candidates": per[1:4]}


def main():
    rep = {"schema": "F3R2_STOW_SUPPORT_V1",
           "demotion": {
               "parts": list(SADDLE_TAG),
               "from": "implied structural support",
               "to": "ENVELOPE_REFERENCE_ONLY",
               "evidence": ("B-rep probe: 10 planar faces each, zero "
                            "cylindrical or cradle geometry, no pad, no "
                            "locating pin, no fastener provision "
                            "(BREP_PROBE_WINGROOT.json)")},
           "counterface_method": ("arm MESH vertices over each saddle "
                                  "footprint, lowest-band fit -- explicitly "
                                  "NOT a bounding-box face pick")}
    try:
        C.check_protected2("G3D_PRE")
        arms = P.arm_parts("STOWED")
        envs = P.env_parts("STOWED", wings=("WING_L_STOWED", "WING_R_STOWED"))
        found = {}
        for name, tag in SADDLE_TAG.items():
            found[tag] = analyse(tag, envs[name], arms)
            c = found[tag]
            print("  %-4s %-28s %s" % (tag, c["status"],
                                       c.get("counterface", {})
                                       .get("arm_part", "")))
            if c["status"] == "COUNTERFACE_FOUND":
                cf = c["counterface"]
                print("        lowest_z=%.3f saddle_top=%.3f gap=%.3f "
                      "band_y=%.1f mm pts=%d"
                      % (cf["lowest_z_mm"], c["saddle_top_z_mm"],
                         cf["gap_to_saddle_top_mm"],
                         cf["contact_band_width_y_mm"],
                         cf["n_points_above_saddle_top"]))
        rep["counterface_search"] = found
        C.write_json(CFJ, {"schema": "F3R2_COUNTERFACE_SEARCH_V1",
                           "results": found})

        # ---------------- define the real supports ----------------
        parts, supports = [], {}
        for name, tag in SADDLE_TAG.items():
            c = found[tag]
            if c["status"] != "COUNTERFACE_FOUND":
                supports[tag] = {"status": "CANNOT_DEFINE_NO_COUNTERFACE",
                                 "reason": c["status"],
                                 "detail": c.get("meaning")}
                continue
            cf = c["counterface"]
            is_mid = (tag == "MID")
            target_gap = MID_GAP_MM if is_mid else 0.0
            # how much taller/shorter the real support must be than the block
            delta = cf["gap_to_saddle_top_mm"] - target_gap
            body_h = 40.0
            width = max(24.0, min(60.0, cf["contact_band_width_y_mm"] + 12.0))
            depth = float(c["footprint_mm"][3] - c["footprint_mm"][0])
            vol_body = width * depth * body_h * 0.42     # ribbed, not solid
            vol_pad = width * depth * 3.0 * 0.8
            supports[tag] = {
                "status": "DEFINED",
                "part_name": ("%s_PRIMARY_SUPPORT" % tag if not is_mid
                              else "MID_BACKUP_SUPPORT"),
                "role": ("primary two-point cradle support" if not is_mid
                         else "backup only, no nominal contact force"),
                "supported_arm_part": cf["arm_part"],
                "counterface_z_mm": cf["lowest_z_mm"],
                "existing_block_top_z_mm": c["saddle_top_z_mm"],
                "required_height_change_mm": round(delta, 4),
                "new_support_top_z_mm": round(cf["lowest_z_mm"] - target_gap,
                                              4),
                "nominal_gap_mm": target_gap,
                "nominal_contact_force_N": 0.0 if is_mid else "TBD_LOAD_CASE",
                "contact_geometry": (
                    {"type": "flat backup pad", "pad_thickness_mm": 3.0,
                     "abnormal_deflection_direction": "-Z (arm sags onto pad)"}
                    if is_mid else
                    {"type": "V-cradle, two-point", "included_angle_deg": 120.0,
                     "contact_line_separation_mm": round(width * 0.55, 2),
                     "pad_thickness_mm": 3.0,
                     "lateral_guide_height_mm": 8.0,
                     "anti_slip_lip_height_mm": 2.5,
                     "release_ramp_angle_deg": 15.0}),
                "footprint_mm": c["footprint_mm"],
                "width_mm": round(width, 2), "depth_mm": round(depth, 2),
                "body_height_mm": body_h,
                "mount": {"interface": "bus deck, 4x M3",
                          "locating_pins": 2, "pin_diameter_mm": 3.0,
                          "fastener_clearance_mm": 12.0},
                "measurable_datum": {
                    "type": "machined datum pad on the support top face",
                    "nominal_z_mm": round(cf["lowest_z_mm"] - target_gap, 4),
                    "tolerance_mm": 0.1},
                "replaceable_pad": True,
            }
            add = parts.append
            add({"part": supports[tag]["part_name"], "kind": "support body",
                 "qty": 1, "material": "Al 6061-T6", "volume_mm3":
                     round(vol_body, 2),
                 "mass_g": round(vol_body * AL, 2),
                 "note": supports[tag]["role"],
                 "dimension_source": "counter-face search on the CAD arm mesh"})
            add({"part": "%s_CONTACT_PAD" % tag, "kind": "replaceable pad",
                 "qty": 1 if is_mid else 2, "material": "Vespel SP-1",
                 "volume_mm3": round(vol_pad, 2),
                 "mass_g": round(vol_pad * VESPEL * (1 if is_mid else 2), 2),
                 "note": "replaceable contact face; protects the arm finish",
                 "dimension_source": "contact band width from the same search"})
            add({"part": "%s_LOCATING_PIN" % tag, "kind": "locating pin",
                 "qty": 2, "material": "Ti-6Al-4V",
                 "volume_mm3": round(3.14159 * 1.5 ** 2 * 10.0, 2),
                 "mass_g": round(3.14159 * 1.5 ** 2 * 10.0 * TI * 2, 3),
                 "note": "repeatable position on the deck",
                 "dimension_source": "standard 3 mm dowel"})

        rep["supports"] = supports
        rep["parts"] = parts
        rep["total_mass_g"] = round(sum(p["mass_g"] for p in parts), 2)
        rep["known_prior_numbers"] = {
            "note": ("the +0.1 mm gripper/G07 and -0.4 mm link5/Mid figures "
                     "from the earlier audit were search STARTING POINTS "
                     "only, computed against the placeholder blocks with a "
                     "bbox method; they are not acceptance results and are "
                     "superseded by the counter-face search above")}
        rep["acceptance_tests"] = [
            {"id": "SUP-1", "test": "G07 nominal support",
             "criterion": "cradle contacts its counter-face, 0 mm nominal gap",
             "status": "DEFINED_NOT_MODELLED"},
            {"id": "SUP-2", "test": "G08 nominal support",
             "criterion": "cradle contacts its counter-face, 0 mm nominal gap",
             "status": "DEFINED_NOT_MODELLED"},
            {"id": "SUP-3", "test": "Mid backup gap",
             "criterion": "2.00 mm nominal gap, 0 N nominal contact force",
             "status": "DEFINED_NOT_MODELLED"},
            {"id": "SUP-4", "test": "native interference zero in stow",
             "criterion": "SolidWorks native interference = 0",
             "status": "NOT_RUN_NATIVE_UNAVAILABLE"},
        ]
        rep["verdict"] = "G3D_SUPPORTS_DEFINED_NOT_MODELLED"
        C.write_csv(OUTC, parts)
        rep["protected_post"] = C.check_protected2("G3D_POST")["verdict"]
    except Exception as exc:
        rep["verdict"] = "G3D_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]

    C.write_json(OUTJ, rep)
    print("\nverdict:", rep["verdict"])
    for tag, s in (rep.get("supports") or {}).items():
        if s["status"] != "DEFINED":
            print("  %-4s %s (%s)" % (tag, s["status"], s.get("reason")))
            continue
        print("  %-4s %-24s supports %-34s top_z %.3f -> %.3f (%+.3f) gap %.2f"
              % (tag, s["part_name"], s["supported_arm_part"][:34],
                 s["existing_block_top_z_mm"], s["new_support_top_z_mm"],
                 s["required_height_change_mm"], s["nominal_gap_mm"]))
    if "total_mass_g" in rep:
        print("  parts:", len(rep["parts"]), "| mass %.1f g" % rep["total_mass_g"])
    if rep["verdict"] == "G3D_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"].startswith("G3D_SUPPORTS") else 1)


if __name__ == "__main__":
    main()
