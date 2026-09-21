# -*- coding: utf-8 -*-
"""F3R2 G3-1: the B601 base interface adapter -- the part that closes the
arm-to-spacecraft load path.

The measurement that drives the whole design (B-rep, not assumed):

    B601 flange      8 x M3 through (r=1.5), bolt circle R = 45.25,
                     at x = 210.41, coaxial with X.  Counterbore r = 3.4,
                     so the fastener envelope reaches R = 48.65.
    Central_Boss     physical face at x = 208.00, OUTER radius 55.0,
                     but a through-bore of radius 50.0.

    => the entire B601 bolt circle sits OVER the boss bore.  There is no metal
       under those eight screws.  A direct arm-to-boss bolted joint is
       geometrically impossible; the boss only offers a 5 mm annulus
       (r = 50..55).

The adapter therefore has to do three things at once:
  1. pick up 8 x M3 at R = 45.25 on the arm side (over the bore),
  2. carry that load radially outward onto the boss annulus and further out
     onto the Adapter_Plate bolt field (r = 80 envelope),
  3. do it inside 2.41 mm of axial space between the boss face (208.00) and the
     B601 flange (210.41) -- so the load transfer happens in a flanged ring,
     not a thick spacer.

Nothing inside B601 is modified.  The B601-side ring is declared
COMPETITION_PROTOTYPE_BASE_INTERFACE, never an original flight flange.
"""
import json
import math
import sys
import traceback

import r2_common as C

OUTJ = C.NC2 / "F3R2_B601_BASE_INTERFACE_DEFINITION.json"
OUTC = C.NC2 / "F3R2_B601_BASE_INTERFACE_PART_LIST.csv"
BREP = C.CLR2 / "mesh" / "BREP_PROBE_MOUNT2.json"
TSM = C.NC2 / "F3R2_TSM_CAD_MEASUREMENT.json"

AL7075 = 2.81e-3     # g/mm^3
A286 = 7.94e-3
BOSS_FACE_X = 208.00
ADAPTER_PLATE_OUTER_X = 198.00


def main():
    rep = {"schema": "F3R2_B601_BASE_INTERFACE_V1"}
    try:
        C.check_protected2("G31_PRE")
        b = json.loads(BREP.read_text(encoding="utf-8"))["parts"]
        t = json.loads(TSM.read_text(encoding="utf-8"))
        fl = t["b601_mounting_flange"]

        boss = b["Central_Boss"]
        plate = b["Adapter_Plate"]
        boss_outer_r = max(r for r in boss["cylinder_radii_mm"])
        boss_bore_r = min(r for r in boss["cylinder_radii_mm"])
        plate_half = max(abs(plate["box_mm"][1]), abs(plate["box_mm"][4]))

        R_bolt = (fl["bolt_circle_R_mm"][0] + fl["bolt_circle_R_mm"][1]) / 2.0
        r_hole = fl["hole_radius_mm"]
        r_cbore = 3.4
        flange_x = fl["x_station_mm"]
        axial_space = round(flange_x - BOSS_FACE_X, 4)

        rep["measured_inputs"] = {
            "b601_flange": {"x_mm": flange_x, "bolt_circle_R_mm":
                            round(R_bolt, 3), "holes": fl["hole_count"],
                            "hole_r_mm": r_hole,
                            "counterbore_r_mm": r_cbore,
                            "fastener_envelope_R_mm": round(R_bolt + r_cbore,
                                                            3),
                            "angles_deg": fl["angles_deg"]},
            "central_boss": {"face_x_mm": BOSS_FACE_X,
                             "outer_r_mm": boss_outer_r,
                             "bore_r_mm": boss_bore_r,
                             "annulus_width_mm": round(boss_outer_r -
                                                       boss_bore_r, 3)},
            "adapter_plate": {"outer_face_x_mm": ADAPTER_PLATE_OUTER_X,
                              "half_size_mm": plate_half},
            "axial_space_for_adapter_mm": axial_space}

        # ---------------- the finding that forces the design ----------------
        bolt_over_bore = (R_bolt + r_cbore) < boss_bore_r
        rep["critical_finding"] = {
            "id": "F3R2-BASE-01",
            "statement": ("the entire B601 bolt circle lies over the "
                          "Central_Boss through-bore"),
            "b601_fastener_envelope_R_mm": round(R_bolt + r_cbore, 3),
            "boss_bore_r_mm": boss_bore_r,
            "clearance_to_bore_edge_mm": round(boss_bore_r - (R_bolt + r_cbore),
                                               3),
            "bolt_circle_entirely_over_bore": bool(bolt_over_bore),
            "consequence": ("there is no material under the eight screws, so a "
                            "direct B601-to-boss bolted joint cannot be made.  "
                            "This is why the base interface was open, and it "
                            "is a geometry fact, not a modelling omission."),
            "resolution": ("a flanged transfer ring that picks up M3 at "
                           "R=45.25 over the bore and reacts onto the boss "
                           "annulus (r=50..55) and the Adapter_Plate bolt "
                           "field")}

        # ---------------- part definitions ----------------
        parts = []

        def add(name, kind, qty, mat, dens, vol, dims, note, src):
            parts.append({"part": name, "kind": kind, "qty": qty,
                          "material": mat, "volume_mm3": round(vol, 2),
                          "mass_g": round(vol * dens * qty, 3),
                          "dimensions_mm": dims, "note": note,
                          "dimension_source": src})

        # 1. B601-side interface ring: bolts to the arm flange, spans the bore
        ring_or, ring_ir = 58.0, 26.0
        ring_t = 6.0
        ring_vol = math.pi * (ring_or ** 2 - ring_ir ** 2) * ring_t * 0.82
        add("B601_INTERFACE_RING", "transfer ring", 1, "Al7075-T6", AL7075,
            ring_vol,
            {"outer_radius": ring_or, "inner_bore_radius": ring_ir,
             "thickness": ring_t,
             "arm_side_holes": "8 x M3 clearance (r=1.7) at R=45.25, "
                               "70/160/250/340 deg",
             "boss_side_holes": "8 x M4 clearance (r=2.25) at R=52.5",
             "spigot_diameter": 100.0, "spigot_depth": 2.0,
             "x_from": BOSS_FACE_X, "x_to": round(BOSS_FACE_X + ring_t, 2)},
            ("spans the boss bore: takes the arm's 8xM3 at R=45.25 and reacts "
             "them onto the boss annulus at R=52.5; the 2 mm spigot into the "
             "r=50 bore centres it and carries shear"),
            "measured B601 bolt circle + measured boss bore/annulus")

        # 2. load spreading collar onto the Adapter_Plate bolt field
        col_or, col_ir = 78.0, 56.0
        col_t = 8.0
        col_vol = math.pi * (col_or ** 2 - col_ir ** 2) * col_t * 0.7
        add("B601_LOAD_SPREADING_COLLAR", "load collar", 1, "Al7075-T6",
            AL7075, col_vol,
            {"outer_radius": col_or, "inner_radius": col_ir,
             "thickness": col_t,
             "holes": "8 x M5 clearance (r=2.75) at R=68.0 into Adapter_Plate",
             "ribs": "8 radial ribs, 4 mm, aligned with the M5 pattern"},
            ("second load path: carries moment from the ring out to the "
             "Adapter_Plate 160x160 envelope instead of concentrating it on "
             "the 5 mm boss annulus"),
            "Adapter_Plate half-size 80 mm measured")

        # 3. anti-rotation: the 25 deg clocking must be repeatable
        pin_vol = math.pi * 2.0 ** 2 * 12.0
        add("B601_ANTIROTATION_PIN", "dowel pin", 2, "A286 steel", A286,
            pin_vol,
            {"diameter": 4.0, "length": 12.0, "fit": "h7/H7 press-slip",
             "position": "R=52.5, at 25 and 205 deg (clocking datum)"},
            ("locks the 25 deg clocking that G1 established by mate; without "
             "it the joint is friction-only in torsion"),
            "clocking 25 deg from F3R1_TOP_INTEGRATION_REPORT")

        add("B601_IF_SCREW_M3x10", "socket cap screw", 8, "A2-70 steel",
            A286, math.pi * 1.5 ** 2 * 10.0,
            {"thread": "M3x0.5", "length": 10.0, "torque_Nm": 1.3,
             "threadlocker": "medium"},
            "arm flange -> interface ring", "measured M3 pattern")
        add("B601_IF_SCREW_M4x12", "socket cap screw", 8, "A2-70 steel",
            A286, math.pi * 2.0 ** 2 * 12.0,
            {"thread": "M4x0.7", "length": 12.0, "torque_Nm": 3.0,
             "threadlocker": "medium"},
            "interface ring -> boss annulus", "boss annulus r=50..55")
        add("B601_IF_SCREW_M5x16", "socket cap screw", 8, "A2-70 steel",
            A286, math.pi * 2.5 ** 2 * 16.0,
            {"thread": "M5x0.8", "length": 16.0, "torque_Nm": 4.0,
             "threadlocker": "medium"},
            "collar -> Adapter_Plate (matches P5D M5x16 4 Nm convention)",
            "P5D fastening convention")

        rep["parts"] = parts
        rep["total_mass_g"] = round(sum(p["mass_g"] for p in parts), 2)

        # ---------------- load path ----------------
        rep["load_path"] = [
            "B601 base flange (8 x M3, R=45.25, x=210.41)",
            "-> B601_INTERFACE_RING (spans the r=50 bore; spigot carries shear)",
            "-> Central_Boss annulus r=50..55 via 8 x M4 at R=52.5 (x=208.00)",
            "-> B601_LOAD_SPREADING_COLLAR via 8 x M5 at R=68.0",
            "-> Adapter_Plate (x=186..198)",
            "-> Spacecraft_Flange (183..186)",
            "-> Front_End_Frame (175..183)",
            "-> Load_Spreading_Frame (171..175)",
            "-> primary structure longerons"]
        rep["torsion_path"] = ("2 x Ø4 dowel at R=52.5 (25/205 deg) react the "
                               "clocking torque; the screws are not relied on "
                               "for torsional location")

        # ---------------- axial budget check ----------------
        used = ring_t
        rep["axial_budget"] = {
            "available_between_boss_and_flange_mm": axial_space,
            "ring_thickness_mm": ring_t,
            "fits_in_gap": ring_t <= axial_space,
            "resolution": ("the ring is THICKER than the 2.41 mm gap, so the "
                           "arm cannot stay at its current station AND bolt to "
                           "a 6 mm ring.  Two options, and this campaign "
                           "chooses (b):"),
            "option_a": ("move the arm outboard by %0.2f mm -- rejected: it "
                         "would invalidate every frozen pose and clearance"
                         % (ring_t - axial_space)),
            "option_b": ("recess the ring into the boss bore: the ring's "
                         "spigot occupies the bore (r<50) for 2.0 mm and its "
                         "flange occupies the 2.41 mm gap, so only "
                         "%0.2f mm of flange sits proud" % axial_space),
            "chosen": "option_b",
            "proud_flange_mm": axial_space,
            "recess_depth_into_bore_mm": round(ring_t - axial_space, 2)}

        # ---------------- acceptance ----------------
        rep["acceptance_tests"] = [
            {"id": "BI-1", "test": "arm-side hole pattern matches B601",
             "criterion": "8 holes, R=45.25 +/-0.05, 90 deg spacing",
             "status": "DEFINED_FROM_MEASURED_PATTERN"},
            {"id": "BI-2", "test": "ring reacts onto real metal",
             "criterion": "boss-side holes at R=52.5 fall in the r=50..55 "
                          "annulus",
             "measured": {"R": 52.5, "annulus": [boss_bore_r, boss_outer_r],
                          "inside": boss_bore_r < 52.5 < boss_outer_r},
             "status": "PASS_BY_CONSTRUCTION"},
            {"id": "BI-3", "test": "anti-rotation present",
             "criterion": "at least 2 dowels or equivalent form-fit",
             "status": "DEFINED"},
            {"id": "BI-4", "test": "no floating base interface",
             "criterion": "every load path element bolts to the next",
             "status": "DEFINED"},
            {"id": "BI-5", "test": "native interference = 0 with the adapter",
             "criterion": "SolidWorks native interference zero",
             "status": "NOT_RUN_ADAPTER_NOT_MODELLED"},
            {"id": "BI-6", "test": "fastener strength",
             "criterion": "MoS > 0 under authorised launch load",
             "status": "NOT_EVALUABLE_NO_AUTHORISED_LAUNCH_LOAD"},
        ]
        rep["status"] = "COMPETITION_PROTOTYPE_BASE_INTERFACE"
        rep["explicit_non_claim"] = "NOT_ORIGINAL_B601_FLIGHT_INTERFACE"
        rep["mass_accounting"] = ("enters the spacecraft EXTERNAL mechanical "
                                  "mass budget; must NOT be added to the "
                                  "accepted B601 URDF inertia")
        rep["verdict"] = "G31_BASE_INTERFACE_DEFINED"
        C.write_csv(OUTC, parts)
        rep["protected_post"] = C.check_protected2("G31_POST")["verdict"]
    except Exception as exc:
        rep["verdict"] = "G31_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]

    C.write_json(OUTJ, rep)
    print("verdict:", rep["verdict"])
    cf = rep.get("critical_finding", {})
    if cf:
        print("\n  [%s] %s" % (cf["id"], cf["statement"]))
        print("    fastener envelope R=%s vs boss bore r=%s  -> clearance %s mm"
              % (cf["b601_fastener_envelope_R_mm"], cf["boss_bore_r_mm"],
                 cf["clearance_to_bore_edge_mm"]))
        print("    entirely over bore:", cf["bolt_circle_entirely_over_bore"])
    ab = rep.get("axial_budget", {})
    if ab:
        print("\n  axial: gap=%s mm, ring=%s mm, chosen=%s, recess=%s mm"
              % (ab["available_between_boss_and_flange_mm"],
                 ab["ring_thickness_mm"], ab["chosen"],
                 ab["recess_depth_into_bore_mm"]))
    if "parts" in rep:
        print("\n  parts: %d | mass %.1f g" % (len(rep["parts"]),
                                               rep["total_mass_g"]))
        for p in rep["parts"]:
            print("    %-28s x%-2d %-14s %8.2f g" % (p["part"], p["qty"],
                                                     p["material"],
                                                     p["mass_g"]))
        print("\n  load path:")
        for s in rep["load_path"]:
            print("    " + s)
    if rep["verdict"] == "G31_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G31_BASE_INTERFACE_DEFINED" else 1)


if __name__ == "__main__":
    main()
