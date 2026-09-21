# -*- coding: utf-8 -*-
"""F3R2 G3-2: rebuild G07 / G08 / Mid support heads so that the pads P5B
already specified can physically sit on them.

The conflict this closes, quantified from measured geometry:

    P5B specifies      G07 pad 50 x 50 mm, G08 pad 30 x 30 mm
    the CAD tower tops measure 20 x 60 mm  (x-extent only 20 mm)

so a 50 mm pad would overhang the 20 mm tower by 15 mm each side.  The pads are
NOT changed -- P5B's material selection, stiffness and preload stay exactly as
ratified.  What changes is the head the pad sits on.

Design rule applied per side:

    pad_size + 2 x carrier_lip  <=  head structural width
    G07: 50 + 2x2 = 54 mm       G08: 30 + 2x2 = 34 mm

The 20 mm tower foot is kept (its station and deck interface are already
manufactured-released), and the load is flared out to the wide head through a
tapered transition with twin triangular ribs -- a 50 mm pad must not cantilever
off a 20 mm post.
"""
import json
import sys
import traceback

import r2_common as C
import r2_pose as P

OUTJ = C.SUP2 / "F3R2_SUPPORT_V2_DEFINITION.json"
OUTC = C.SUP2 / "F3R2_SUPPORT_V2_PART_LIST.csv"
OUTR = C.SUP2 / "F3R2_SADDLE_CONTACT_FACE_REGISTER.csv"
CFJ = C.SUP2 / "F3R2_SUPPORT_COUNTERFACE_SEARCH.json"

AL7075 = 2.81e-3
AL6061 = 2.70e-3
VESPEL = 1.43e-3
PTFE = 2.20e-3
VMQ = 1.25e-3
STEEL = 7.85e-3
TI = 4.43e-3

# P5B ratified pad specification -- carried through unchanged
PADS = {
    "G07": {"pad": "Disc_Spring_GB1972_D50_25.4_t1.5_pair + PTFE 3mm 50x50",
            "pad_x_mm": 50.0, "pad_y_mm": 50.0, "pad_t_mm": 3.0,
            "material": "modified PTFE 25% glass fibre",
            "kn_N_per_mm": 10.0, "kt_N_per_mm": 5.0,
            "preload_N": 50.0, "preload_travel_mm": 0.2,
            "source": "F3_P5B_PAD_COMPETITION_SPECIFICATION.md"},
    "G08": {"pad": "VMQ Silicone Shore60A 2mm 30x30",
            "pad_x_mm": 30.0, "pad_y_mm": 30.0, "pad_t_mm": 2.0,
            "material": "VMQ silicone 60A",
            "kn_N_per_mm": 5.0, "kt_N_per_mm": 2.0,
            "preload_N": 25.0, "preload_travel_mm": 0.1,
            "source": "F3_P5B_PAD_COMPETITION_SPECIFICATION.md"},
    "MID": {"pad": "Vespel SP-1 backup pad 30x30x3",
            "pad_x_mm": 30.0, "pad_y_mm": 30.0, "pad_t_mm": 3.0,
            "material": "Vespel SP-1",
            "kn_N_per_mm": None, "kt_N_per_mm": None,
            "preload_N": 0.0, "preload_travel_mm": 0.0,
            "source": "F3R2 G3-D backup role, no nominal contact"},
}
LIP_MM = 2.0          # pad carrier retaining lip per side
MID_GAP_MM = 2.00
OLD_TOWER = {"x_mm": 20.0, "y_mm": 60.0}


def main():
    rep = {"schema": "F3R2_SUPPORT_V2_V1",
           "closes": ("F3R2-SADDLE-01: P5B pads (50x50 / 30x30) do not fit the "
                      "20 x 60 mm placeholder tower tops"),
           "principle": ("the ratified P5B pad specification is NOT changed; "
                         "the support head is redesigned to carry it")}
    try:
        C.check_protected2("G32_PRE")
        cf = json.loads(CFJ.read_text(encoding="utf-8"))["results"]

        supports, parts, reg = {}, [], []

        def add(name, kind, qty, mat, dens, vol, dims, note, src):
            parts.append({"part": name, "kind": kind, "qty": qty,
                          "material": mat, "volume_mm3": round(vol, 2),
                          "mass_g": round(vol * dens * qty, 3),
                          "dimensions_mm": json.dumps(dims,
                                                      ensure_ascii=False),
                          "note": note, "dimension_source": src})

        for tag in ("G07", "G08", "MID"):
            c = cf[tag]
            pad = PADS[tag]
            is_mid = (tag == "MID")
            fp = c["footprint_mm"]
            counter = c["counterface"]
            top_z = c["saddle_top_z_mm"]
            arm_z = counter["lowest_z_mm"]

            # required head size: pad + retaining lip both sides
            head_x = pad["pad_x_mm"] + 2 * LIP_MM
            head_y = pad["pad_y_mm"] + 2 * LIP_MM
            # the head must also cover the measured contact band
            band_y = counter["contact_band_width_y_mm"]
            head_y = max(head_y, band_y + 2 * LIP_MM)

            # the pad face has to end up where the arm actually is
            target_gap = MID_GAP_MM if is_mid else 0.0
            pad_face_z = round(arm_z - target_gap, 4)
            carrier_top_z = round(pad_face_z - pad["pad_t_mm"], 4)
            # G07 also carries the disc-spring stack under the PTFE
            spring_h = 6.0 if tag == "G07" else 0.0
            head_top_z = round(carrier_top_z - spring_h, 4)
            flare_h = 26.0
            head_h = 12.0
            head_bot_z = round(head_top_z - head_h, 4)
            flare_bot_z = round(head_bot_z - flare_h, 4)

            fits_old = (head_x <= OLD_TOWER["x_mm"])
            overhang = round((head_x - OLD_TOWER["x_mm"]) / 2.0, 3)

            head_vol = head_x * head_y * head_h * 0.55
            flare_vol = ((head_x + OLD_TOWER["x_mm"]) / 2.0
                         * (head_y + OLD_TOWER["y_mm"]) / 2.0
                         * flare_h * 0.34)
            rib_vol = 2 * (0.5 * flare_h * overhang * 5.0) * 2
            carrier_vol = (pad["pad_x_mm"] + 2 * LIP_MM) * \
                (pad["pad_y_mm"] + 2 * LIP_MM) * 4.0 * 0.6
            pad_vol = pad["pad_x_mm"] * pad["pad_y_mm"] * pad["pad_t_mm"]

            supports[tag] = {
                "part_name": ("%s_PRIMARY_SUPPORT_V2" % tag if not is_mid
                              else "MID_BACKUP_SUPPORT_V2"),
                "role": ("primary support, pad in nominal contact"
                         if not is_mid else
                         "backup only, 2.00 mm nominal gap, 0 N nominal force"),
                "supported_arm_part": counter["arm_part"],
                "pad_specification": pad,
                "conflict_resolved": {
                    "old_tower_top_mm": OLD_TOWER,
                    "pad_mm": [pad["pad_x_mm"], pad["pad_y_mm"]],
                    "pad_fits_old_tower": bool(fits_old),
                    "overhang_per_side_mm": overhang,
                    "new_head_mm": [round(head_x, 2), round(head_y, 2)],
                    "rule": "head >= pad + 2 x %.1f mm carrier lip" % LIP_MM},
                "geometry": {
                    "head_width_x_mm": round(head_x, 2),
                    "head_width_y_mm": round(head_y, 2),
                    "head_height_mm": head_h,
                    "head_top_z_mm": head_top_z,
                    "head_bottom_z_mm": head_bot_z,
                    "flare_height_mm": flare_h,
                    "flare_bottom_z_mm": flare_bot_z,
                    "foot_x_mm": OLD_TOWER["x_mm"],
                    "foot_y_mm": OLD_TOWER["y_mm"],
                    "foot_station_unchanged": True,
                    "ribs": ("2 triangular ribs per flared side, 5 mm thick, "
                             "full flare height"),
                    "pad_carrier_top_z_mm": carrier_top_z,
                    "pad_face_z_mm": pad_face_z,
                    "spring_stack_height_mm": spring_h},
                "contact": ({"type": "flat backup pad", "nominal_gap_mm": 2.00,
                             "nominal_force_N": 0.0,
                             "abnormal_deflection_direction": "-Z"}
                            if is_mid else
                            {"type": "V-cradle two-point with flat pad seat",
                             "included_angle_deg": 120.0,
                             "nominal_gap_mm": 0.0,
                             "preload_N": pad["preload_N"],
                             "lateral_guide_height_mm": 8.0,
                             "anti_slip_lip_height_mm": LIP_MM,
                             "release_ramp_angle_deg": 15.0}),
                "mount": {"interface": "existing tower foot, 4 x M3",
                          "locating_pins": 2, "pin_diameter_mm": 3.0,
                          "station_unchanged_from_v1": True},
                "measurable_datum": {"feature": "machined pad seat face",
                                     "nominal_z_mm": carrier_top_z,
                                     "tolerance_mm": 0.05},
                "replaceable_pad": True,
                "counterface_evidence": {
                    "arm_lowest_z_mm": arm_z,
                    "contact_band_x_mm": counter["contact_band_x_mm"],
                    "contact_band_y_mm": counter["contact_band_y_mm"],
                    "contact_band_width_y_mm": band_y,
                    "points_above_old_top": counter["n_points_above_saddle_top"],
                    "method": ("arm CAD mesh vertices over the footprint, "
                               "lowest-band fit -- not a bbox pick")},
            }

            reg.append({
                "support": tag,
                "part_name": supports[tag]["part_name"],
                "supported_arm_part": counter["arm_part"],
                "arm_counterface_z_mm": arm_z,
                "old_tower_top_z_mm": top_z,
                "new_pad_face_z_mm": pad_face_z,
                "nominal_gap_mm": target_gap,
                "pad_size_mm": "%gx%g" % (pad["pad_x_mm"], pad["pad_y_mm"]),
                "old_head_x_mm": OLD_TOWER["x_mm"],
                "new_head_x_mm": round(head_x, 2),
                "new_head_y_mm": round(head_y, 2),
                "pad_overhang_on_old_head_mm": overhang,
                "contact_band_width_y_mm": band_y,
                "preload_N": pad["preload_N"],
                "kn_N_per_mm": pad["kn_N_per_mm"],
                "kt_N_per_mm": pad["kt_N_per_mm"],
                "pad_source": pad["source"]})

            base = supports[tag]["part_name"]
            add(base, "support body", 1, "Al7075-T6", AL7075,
                head_vol + flare_vol + rib_vol,
                supports[tag]["geometry"],
                "wide head + flared transition + twin ribs onto the existing "
                "20 mm tower foot", "counter-face search + P5B pad size")
            add("%s_PAD_CARRIER" % tag, "pad carrier", 1, "Al6061-T6", AL6061,
                carrier_vol,
                {"x": round(head_x, 2), "y": round(head_y, 2), "t": 4.0,
                 "lip_mm": LIP_MM},
                "removable carrier holding the pad; lip provides anti-slip "
                "retention", "pad size + lip rule")
            if tag == "G07":
                add("G07_DISC_SPRING_PAIR", "disc spring", 2, "spring steel",
                    STEEL, 3.14159 * (25.0 ** 2 - 12.7 ** 2) * 1.5,
                    {"D": 50.0, "d": 25.4, "t": 1.5,
                     "arrangement": "paired, facing"},
                    "P5B ratified; nominal 10 N/mm after 50 N preload",
                    "F3_P5B_PAD_COMPETITION_SPECIFICATION.md")
                add("G07_PTFE_PAD", "contact pad", 1, "PTFE 25% GF", PTFE,
                    50.0 * 50.0 * 3.0, {"x": 50, "y": 50, "t": 3, "Ra": 0.8},
                    "P5B ratified", "P5B")
            elif tag == "G08":
                add("G08_VMQ_PAD", "contact pad", 1, "VMQ 60A", VMQ,
                    30.0 * 30.0 * 2.0, {"x": 30, "y": 30, "t": 2, "Ra": 0.8},
                    "P5B ratified", "P5B")
            else:
                add("MID_VESPEL_PAD", "backup pad", 1, "Vespel SP-1", VESPEL,
                    30.0 * 30.0 * 3.0, {"x": 30, "y": 30, "t": 3},
                    "backup only, no nominal contact", "F3R2 G3-D")
            add("%s_LOCATING_PIN" % tag, "dowel pin", 2, "Ti-6Al-4V", TI,
                3.14159 * 1.5 ** 2 * 10.0,
                {"d": 3.0, "l": 10.0}, "repeatable station on the deck",
                "standard 3 mm dowel")
            add("%s_SCREW_M3x12" % tag, "socket cap screw", 4, "A2-70 steel",
                STEEL, 3.14159 * 1.5 ** 2 * 12.0,
                {"thread": "M3x0.5", "l": 12.0, "torque_Nm": 1.3},
                "head to tower foot", "P5D fastening convention")

        rep["supports"] = supports
        rep["parts"] = parts
        rep["total_mass_g"] = round(sum(p["mass_g"] for p in parts), 2)
        rep["pads_unchanged_from_p5b"] = True
        rep["fea_parameter_consistency"] = {
            "G07": {"kn_N_per_mm": 10.0, "kt_N_per_mm": 5.0},
            "G08": {"kn_N_per_mm": 5.0, "kt_N_per_mm": 2.0},
            "note": ("P5A used these spring rates; the V2 heads do not change "
                     "the pads, so the rates remain applicable.  What DOES "
                     "change is that the pad is now fully supported instead of "
                     "overhanging a 20 mm post, which is the condition those "
                     "rates assume.  Bench calibration per P5B still governs "
                     "(>20% deviation triggers a UL rerun).")}
        rep["acceptance_tests"] = [
            {"id": "SV2-1", "test": "pad fully supported",
             "criterion": "head width >= pad + 2 x 2 mm lip, both axes",
             "status": "PASS_BY_CONSTRUCTION"},
            {"id": "SV2-2", "test": "G07/G08 nominal contact",
             "criterion": "pad face lands on the measured arm counter-face, "
                          "0 mm nominal gap",
             "status": "DEFINED_NOT_MODELLED"},
            {"id": "SV2-3", "test": "Mid backup gap",
             "criterion": "2.00 mm nominal, 0 N nominal force",
             "status": "DEFINED_NOT_MODELLED"},
            {"id": "SV2-4", "test": "load flare, no pad cantilever",
             "criterion": "tapered transition + 2 ribs per flared side",
             "status": "DEFINED"},
            {"id": "SV2-5", "test": "tower foot station unchanged",
             "criterion": "deck interface identical to the released design",
             "status": "PASS_BY_CONSTRUCTION"},
            {"id": "SV2-6", "test": "native interference zero in stow",
             "criterion": "SolidWorks native interference = 0",
             "status": "NOT_RUN_HEADS_NOT_MODELLED"},
        ]
        rep["status"] = "DEFINED_NOT_MODELLED"
        rep["verdict"] = "G32_SUPPORTS_V2_DEFINED"
        C.write_csv(OUTC, parts)
        C.write_csv(OUTR, reg)
        rep["protected_post"] = C.check_protected2("G32_POST")["verdict"]
    except Exception as exc:
        rep["verdict"] = "G32_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]

    C.write_json(OUTJ, rep)
    print("verdict:", rep["verdict"])
    for tag, s in (rep.get("supports") or {}).items():
        cr = s["conflict_resolved"]
        g = s["geometry"]
        print("\n  %-4s %s" % (tag, s["part_name"]))
        print("     pad %gx%g on old head %gx%g -> fits=%s overhang %.1f mm/side"
              % (cr["pad_mm"][0], cr["pad_mm"][1], cr["old_tower_top_mm"]["x_mm"],
                 cr["old_tower_top_mm"]["y_mm"], cr["pad_fits_old_tower"],
                 cr["overhang_per_side_mm"]))
        print("     NEW head %.1f x %.1f mm | pad face z=%.3f | gap %.2f mm"
              % (cr["new_head_mm"][0], cr["new_head_mm"][1],
                 g["pad_face_z_mm"], s["contact"]["nominal_gap_mm"]))
        print("     supports %s (band %.1f mm)"
              % (s["supported_arm_part"][:38],
                 s["counterface_evidence"]["contact_band_width_y_mm"]))
    if "parts" in rep:
        print("\n  parts: %d | mass %.1f g" % (len(rep["parts"]),
                                               rep["total_mass_g"]))
    if rep["verdict"] == "G32_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G32_SUPPORTS_V2_DEFINED" else 1)


if __name__ == "__main__":
    main()
