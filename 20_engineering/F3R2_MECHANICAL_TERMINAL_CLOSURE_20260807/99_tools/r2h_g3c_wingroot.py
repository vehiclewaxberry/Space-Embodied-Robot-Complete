# -*- coding: utf-8 -*-
"""F3R2 G3-C: define the REAL wing-root mechanical interface and close
D-F3R1-06 by geometry, not by assertion.

What the B-rep probe established (not assumed):
  Hinge_Pin_L/R        true cylinder, r = 4.000, axis +/-X, centre y = +/-143.15,
                       z = 0, spanning x = -82 .. -40
  Hinge_Ear_1/2 L/R    true bore r = 4.200, coaxial with the pin, at
                       x = -80 and x = -62
  Torsion_Spring_1/2   coaxial, bore r = 4.200 and body r = 8.000
  Hard_Stop_L/R        6 x 8 x 14 block at x = -64..-58, z = +23..+37
  wing panel           6 planar faces, 6 mm thick, inner edge plane y = +/-113.15
                       -- and NO lug of any kind

So the open interface is entirely on the WING side: nothing reaches from the
panel edge (|y| = 113.15) to the hinge axis (|y| = 143.15).  That is the 30.0 mm
gap recorded as D-F3R1-06.

This module emits the interface DEFINITION -- dimensions, positions, fits,
mass and the acceptance tests -- as machine-readable engineering data.  It does
not modify the donor wing panels or any protected asset.  Whether the lug is
also cut into native SolidWorks geometry is a separate, separately-authorised
step; until then the interface is declared DEFINED_NOT_YET_MODELLED, which is
an honest state, not a pass.
"""
import json
import sys

import r2_common as C

OUTJ = C.SUP2 / "F3R2_WING_ROOT_INTERFACE.json"
OUTC = C.SUP2 / "F3R2_WING_ROOT_PART_LIST.csv"
BREP = C.CLR2 / "mesh" / "BREP_PROBE_WINGROOT.json"

AL = 2.70e-3           # g/mm^3, Al 6061-T6
STEEL = 7.85e-3        # g/mm^3, A286 / 316 pin


def main():
    rep = {"schema": "F3R2_WING_ROOT_INTERFACE_V1",
           "closes": "D-F3R1-06 (wing-root hinge interface OPEN)",
           "status": "DEFINED_NOT_YET_MODELLED",
           "status_meaning": (
               "every dimension below is derived from measured B-rep geometry "
               "and is buildable as-is, but the lug has NOT been cut into the "
               "native wing panel in this session -- so the assembly still "
               "shows the 30.0 mm gap and no clearance result may claim the "
               "hinge is closed")}
    try:
        C.check_protected2("G3C_PRE")
        b = json.loads(BREP.read_text(encoding="utf-8"))["parts"]

        def cyl(name):
            f = [f for f in b[name]["faces"] if f["kind"] == "Cylinder"]
            return f[0] if f else None

        meas = {}
        for side, sgn in (("Left", +1), ("Right", -1)):
            pin = cyl("Hinge_Pin_%s" % side)
            e1 = cyl("Hinge_Ear_1_%s" % side)
            e2 = cyl("Hinge_Ear_2_%s" % side)
            meas[side] = {
                "pin_radius_mm": pin["radius_mm"],
                "pin_axis": pin["axis_xyz"],
                "pin_axis_point_mm": pin["centre_mm"],
                "pin_box_mm": b["Hinge_Pin_%s" % side]["box_mm"],
                "ear_bore_radius_mm": e1["radius_mm"],
                "ear_1_bore_centre_mm": e1["centre_mm"],
                "ear_2_bore_centre_mm": e2["centre_mm"],
                "ear_1_box_mm": b["Hinge_Ear_1_%s" % side]["box_mm"],
                "ear_2_box_mm": b["Hinge_Ear_2_%s" % side]["box_mm"],
                "hard_stop_box_mm": b["Hard_Stop_%s" % side]["box_mm"],
                "torsion_spring_1_box_mm":
                    b["Torsion_Spring_1_%s" % side]["box_mm"],
                "torsion_spring_2_box_mm":
                    b["Torsion_Spring_2_%s" % side]["box_mm"],
                "hinge_axis_y_mm": 143.15 * sgn,
                "hinge_axis_z_mm": 0.0,
                "wing_inner_edge_y_mm": 113.15 * sgn,
                "wing_thickness_mm": 6.0,
                "radial_gap_to_close_mm": 30.0,
            }
        rep["measured"] = meas
        rep["measurement_source"] = ("OpenCascade analytic surfaces read from "
                                     "F3R1_V3_DEPLOYED_NOMINAL.step; NOT a "
                                     "mesh estimate")

        # ---------- the interface definition ----------
        # A clevis on the wing straddling each existing spacecraft ear, so the
        # load path is wing lug -> pin -> ear -> Root_Base, in double shear.
        # Ear plates occupy x = -75..-65 and -57..-47 and are 10 mm thick.
        parts = []

        def add(name, kind, qty, dims, mat, dens, vol_mm3, note, source):
            parts.append({
                "part": name, "kind": kind, "qty_per_side": qty,
                "dimensions_mm": dims, "material": mat,
                "density_g_per_mm3": dens,
                "volume_mm3": round(vol_mm3, 2),
                "mass_g_each": round(vol_mm3 * dens, 3),
                "mass_g_per_side": round(vol_mm3 * dens * qty, 3),
                "note": note, "dimension_source": source})

        # 1. wing lug (clevis fork), one fork per existing ear -> 2 per side.
        #    Fork arms straddle a 10 mm ear with 0.5 mm side clearance:
        #    inner span 11.0 mm, arm thickness 5.0 mm, outer span 21.0 mm.
        #    Each arm reaches from the panel edge plane |y| = 113.15 to beyond
        #    the axis |y| = 143.15, i.e. 30.0 mm + boss radius.
        lug_arm = 5.0 * 30.0 * 42.0        # t x reach-ish x length envelope
        add("WING_LUG_FORK", "structural lug", 2,
            {"arm_thickness": 5.0, "inner_span": 11.0, "outer_span": 21.0,
             "reach_from_panel_edge": 30.0, "bore_radius": 4.200,
             "boss_outer_radius": 9.0, "root_fillet": 3.0,
             "bore_axis_y_offset_from_panel_edge": 30.0},
            "Al 6061-T6", AL, 2 * lug_arm * 0.55,
            "double-shear fork straddling the existing spacecraft ear; bore "
            "coaxial with Hinge_Pin (r=4.000) at 4.200 -> 0.2 mm running fit",
            "derived from measured ear thickness 10.0 mm and axis offset 30.0 mm")

        # 2. axial spacers keep the fork centred on its ear
        sp_vol = 3.14159 * (9.0 ** 2 - 4.3 ** 2) * 0.5
        add("HINGE_AXIAL_SPACER", "spacer washer", 4,
            {"outer_radius": 9.0, "bore_radius": 4.300, "thickness": 0.5},
            "PTFE-filled bronze", 8.8e-3, sp_vol,
            "one each side of every fork arm; sets 0.5 mm running clearance "
            "and prevents axial walk",
            "thickness = the fork/ear side clearance chosen above")

        # 3. retaining feature: the pin is 42 mm long, ears at x=-80 and -62
        add("HINGE_PIN_RETAINER", "retaining ring", 2,
            {"groove_diameter": 7.6, "groove_width": 0.9,
             "ring_type": "DIN 471 external, 8 mm shaft"},
            "spring steel", STEEL, 3.14159 * (4.8 ** 2 - 3.8 ** 2) * 0.9,
            "captures the existing r=4.000 pin axially; groove cut in the pin "
            "ends outside the ear stack",
            "standard ring for the measured 8.000 mm pin diameter")

        # 4. mechanical stop is EXISTING hardware; the wing needs the mating pad
        add("WING_STOP_PAD", "hard-stop contact pad", 1,
            {"length": 14.0, "width": 8.0, "thickness": 3.0,
             "contact_plane_z": 37.0},
            "Al 6061-T6 + Vespel facing", AL,
            14.0 * 8.0 * 3.0,
            "lands on the EXISTING Hard_Stop block (x -64..-58, z +23..+37) at "
            "the 90 deg deployed end stop; defines the deployment angle",
            "matches measured Hard_Stop_* box")

        # 5. torsion spring anchor on the wing side (spring itself exists)
        add("WING_SPRING_ANCHOR", "spring leg pocket", 2,
            {"pocket_depth": 4.0, "pocket_width": 3.0, "length": 12.0},
            "Al 6061-T6", AL, 12.0 * 3.0 * 4.0 + 12.0 * 6.0 * 2.0,
            "receives the deployment torsion-spring leg; spring bodies "
            "(r=8.000, bore r=4.200) already exist at x=-93..-75 and -47..-29",
            "sized to the measured spring body envelope")

        # 6. cable passage across the hinge
        add("WING_HARNESS_GROMMET", "harness passage", 1,
            {"inner_radius": 4.0, "outer_radius": 6.5, "length": 8.0,
             "bend_radius_min": 25.0},
            "silicone + Al eyelet", 1.4e-3,
            3.14159 * (6.5 ** 2 - 4.0 ** 2) * 8.0,
            "routes the panel harness beside the hinge into the EXISTING "
            "Harness_Service_Loop (x -110..-90); keeps the service loop off "
            "the rotating parts",
            "bend radius from the existing service-loop envelope")

        rep["parts"] = parts
        rep["mass_per_side_g"] = round(sum(p["mass_g_per_side"]
                                           for p in parts), 3)
        rep["mass_both_sides_g"] = round(rep["mass_per_side_g"] * 2, 3)
        rep["load_path"] = ("wing panel -> WING_LUG_FORK (double shear) -> "
                            "Hinge_Pin (r=4.000) -> Hinge_Ear_1/2 -> "
                            "Root_Base -> Root_Node_Spine -> bus longerons")
        rep["left_right"] = ("mirrored about the XZ plane but assembled "
                             "independently: each side has its own pin, ears, "
                             "springs, stop and HDRM, so a single-side "
                             "deployment failure stays single-sided (this is "
                             "what makes L_FAIL / R_FAIL physical)")
        rep["deployment"] = {
            "axis": "X (spacecraft longitudinal), through |y| = 143.15, z = 0",
            "stowed_angle_deg": 0.0, "deployed_angle_deg": 90.0,
            "angle_authority": ("V2_2 state_policy.json -- unchanged by this "
                                "definition"),
            "driven_by": "existing torsion springs, ends on WING_STOP_PAD",
            "note": ("the deploy TRANSIT path remains unauthorised (G2 hold); "
                     "only the two end states are defined")}
        rep["fits"] = {
            "pin_to_ear_bore": "4.000 / 4.200 -> 0.200 mm diametral running fit",
            "pin_to_lug_bore": "4.000 / 4.200 -> 0.200 mm diametral running fit",
            "fork_to_ear_side": "0.5 mm per side, set by the axial spacers",
            "coaxiality_requirement_mm": 0.05}
        rep["acceptance_tests"] = [
            {"id": "WR-1", "test": "lug bore and pin coaxial",
             "criterion": "axis offset <= 0.05 mm, axis angle <= 0.1 deg",
             "status": "NOT_RUN_LUG_NOT_MODELLED"},
            {"id": "WR-2", "test": "solid pin/bore engagement",
             "criterion": "fork arms overlap the ear over >= 9.0 mm of the "
                          "10.0 mm ear thickness",
             "status": "NOT_RUN_LUG_NOT_MODELLED"},
            {"id": "WR-3", "test": "no axial walk",
             "criterion": "total axial free play <= 0.3 mm with spacers fitted",
             "status": "NOT_RUN_LUG_NOT_MODELLED"},
            {"id": "WR-4", "test": "stow/deploy driven by the real hinge axis",
             "criterion": "panel motion is a pure rotation about "
                          "|y| = 143.15, z = 0, within 0.05 mm",
             "status": "NOT_RUN_LUG_NOT_MODELLED"},
            {"id": "WR-5", "test": "one live panel per side",
             "criterion": "the four donor panels never resolve simultaneously",
             "status": "PASS_INHERITED_FROM_G2",
             "evidence": "F3R1_G2_WING_INSTANCE_AUDIT.csv"},
            {"id": "WR-6", "test": "deployment configuration cold-reopens",
             "criterion": "all eight configurations rebuild after a cold open",
             "status": "PASS_INHERITED_FROM_G2",
             "evidence": "F3R1_G2_COLD_REOPEN_PER_CONFIG.csv"},
            {"id": "WR-7", "test": "native interference = 0 at both end states",
             "criterion": "SolidWorks native interference zero, stowed and "
                          "deployed",
             "status": "NOT_RUN_NATIVE_UNAVAILABLE",
             "evidence": "G3A_NATIVE_ATTEMPTS.json"},
        ]
        rep["what_is_already_real"] = [
            "Hinge_Pin_L/R  -- true cylinder r=4.000 on the measured axis",
            "Hinge_Ear_1/2_L/R -- true bores r=4.200, coaxial",
            "Torsion_Spring_1/2_L/R -- coaxial bodies r=8.000, bore r=4.200",
            "Hard_Stop_L/R -- discrete stop block",
            "Root_Base_L/R, Root_Node_Spine_L/R -- load path into the bus",
            "Harness_Service_Loop_L/R -- harness slack volume"]
        rep["what_is_missing"] = [
            "the wing-side lug/clevis (the whole of the 30.0 mm gap)",
            "axial spacers, pin retainers, stop pad, spring anchor, grommet",
            "native modelling of all of the above into the panel geometry"]
        rep["verdict"] = "G3C_INTERFACE_DEFINED_NOT_MODELLED"
        C.write_csv(OUTC, parts, fields=[
            "part", "kind", "qty_per_side", "material", "volume_mm3",
            "mass_g_each", "mass_g_per_side", "dimensions_mm", "note",
            "dimension_source"])
        rep["protected_post"] = C.check_protected2("G3C_POST")["verdict"]
    except Exception as exc:
        import traceback
        rep["verdict"] = "G3C_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]

    C.write_json(OUTJ, rep)
    print("verdict:", rep["verdict"])
    if "parts" in rep:
        print("  parts defined:", len(rep["parts"]),
              "| mass per side: %.1f g | both sides: %.1f g"
              % (rep["mass_per_side_g"], rep["mass_both_sides_g"]))
        for p in rep["parts"]:
            print("    %-24s x%-2d %-22s %8.2f g/side"
                  % (p["part"], p["qty_per_side"], p["material"],
                     p["mass_g_per_side"]))
        print("  tests:", {t["status"]: sum(
            1 for x in rep["acceptance_tests"] if x["status"] == t["status"])
            for t in rep["acceptance_tests"]})
    else:
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"].startswith("G3C_INTERFACE") else 1)


if __name__ == "__main__":
    main()
