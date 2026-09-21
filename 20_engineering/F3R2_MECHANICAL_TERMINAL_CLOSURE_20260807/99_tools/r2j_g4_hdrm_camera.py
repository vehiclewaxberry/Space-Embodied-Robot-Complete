# -*- coding: utf-8 -*-
"""F3R2 G4: ARM HDRM, camera, harness and gripper fingers.

Everything here is DEFINED from measured geometry and declared with an explicit
maturity, because none of it exists as native CAD in this session:

  ARM HDRM   the assembly holds only Launch_Lock_Interface_Reference (a 20 x
             168 x 36 reference block at x -10..10, z 132..168) and
             Release_Clearance_Envelope (x -110..70, y -70..110, z 264..354).
             Those are reference volumes, not a release mechanism.  Note the
             SOLAR HDRM hardware (HDRM_Base/Rod_1/2 L/R) is a DIFFERENT
             mechanism at z = -112..-88 and is NOT the arm restraint.
  camera     no camera exists anywhere in the assembly, so every camera
             visibility claim in this campaign stays NOT_EVALUATED.
  harness    the bus has Harness_Passage and Harness_Service_Loop_L/R; the arm
             harness itself does not exist.
  gripper    the CAD carries ONE gripper_detail solid.  The accepted URDF
             declares two prismatic fingers (gripper_joint1/2, 0..71.5 mm).
             A single visual solid must not be presented as two movable
             fingers -- that is exactly the misrepresentation forbidden here.
"""
import json
import sys
import traceback

import r2_common as C
import r2_kin as K
import r2_pose as P

OUTJ = C.HDRM2 / "F3R2_ARM_HDRM_DEFINITION.json"
OUTCAM = C.CAM2 / "F3R2_CAMERA_HARNESS_GRIPPER.json"
OUTC = C.HDRM2 / "F3R2_G4_PART_LIST.csv"

AL = 2.70e-3
TI = 4.43e-3
STEEL = 7.85e-3
PEEK = 1.32e-3


def main():
    rep = {"schema": "F3R2_G4_DEFINITION_V1"}
    try:
        C.check_protected2("G4_PRE")
        envs = P.env_parts("STOWED", wings=("WING_L_STOWED", "WING_R_STOWED"))
        arms_s = P.arm_parts("STOWED")
        llir = envs["Launch_Lock_Interface_Reference"]["box"].tolist()
        rce = envs["Release_Clearance_Envelope"]["box"].tolist()
        grip_s = arms_s["B51_REF_gripper_detail_LINKLOCAL"]["box"].tolist()

        parts = []

        def add(name, kind, qty, mat, dens, vol, note, src):
            parts.append({"part": name, "kind": kind, "qty": qty,
                          "material": mat, "volume_mm3": round(vol, 2),
                          "mass_g": round(vol * dens * qty, 3),
                          "note": note, "dimension_source": src})

        # ------------------------------------------------ ARM HDRM ----------
        hdrm = {
            "designation": "ARM_HDRM",
            "maturity": "COMPETITION_DEMONSTRATOR_ONLY",
            "flight_status": "FLIGHT_MODEL_PROCUREMENT_TBD",
            "not_to_be_confused_with": (
                "the SOLAR array HDRM (HDRM_Base_1/2_L/R, HDRM_Rod_1/2_L/R) "
                "at z = -112..-88, which restrains the wings, not the arm"),
            "existing_reference_geometry": {
                "Launch_Lock_Interface_Reference_mm": llir,
                "Release_Clearance_Envelope_mm": rce,
                "status": "REFERENCE_VOLUMES_ONLY_NOT_A_MECHANISM"},
            "interface_station": {
                "restraint_plane_x_mm": 0.0,
                "restraint_band_z_mm": [llir[2], llir[5]],
                "reason": ("the reference block spans x -10..10, z 132..168, "
                           "i.e. across the arm's stowed body")},
            "load_path": ("arm link -> HDRM cup -> preload rod -> HDRM base -> "
                          "bus deck; launch loads bypass the joints entirely"),
            "release_direction": "+Z, away from the bus deck",
            "stroke_mm": {"value": 6.0, "status": "CANDIDATE",
                          "authority": ("no vendor value exists; 6 mm is the "
                                        "candidate stroke carried from the "
                                        "earlier campaign and must be replaced "
                                        "by the procured device's datasheet")},
            "states": {
                "LOCKED": {"preload_N": "TBD_LAUNCH_LOAD_CASE",
                           "switch": "closed", "arm_powered": False,
                           "arm_commandable": False,
                           "geometry": "cup fully engaged, 0 mm stroke"},
                "RELEASE_START": {"preload_N": 0.0, "switch": "closed",
                                  "arm_powered": True,
                                  "arm_commandable": False,
                                  "geometry": "pyro/HOP fired, rod free, "
                                              "cup still engaged"},
                "RELEASED": {"preload_N": 0.0, "switch": "open",
                             "arm_powered": True, "arm_commandable": True,
                             "geometry": "rod retracted 6 mm, residual "
                                         "envelope clear of the arm"},
                "RELEASE_FAILED": {"preload_N": "unknown",
                                   "switch": "closed_after_timeout",
                                   "arm_powered": True,
                                   "arm_commandable": False,
                                   "action": ("fail-closed: arm stays "
                                              "uncommandable, mission enters "
                                              "MANUAL_RECOVERY")},
                "GROUND_UNLOCK": {"preload_N": 0.0, "switch": "open",
                                  "arm_powered": False,
                                  "arm_commandable": True,
                                  "geometry": "manual bolt removed, AIT only"},
            },
            "mechanical_stop": {"type": "hard shoulder on the rod",
                                "limits_stroke_to_mm": 6.0},
            "state_switch": {"type": "redundant microswitch pair",
                             "wiring": "2x SPDT, cross-strapped"},
            "electrical": {"connector": "9-pin micro-D",
                           "circuits": ["fire A", "fire B", "switch A",
                                        "switch B"]},
            "post_release_residual_envelope_mm": {
                "box": [llir[0] - 5, llir[1] - 5, llir[2] - 5,
                        llir[3] + 5, llir[4] + 5, llir[5] + 6.0 + 5],
                "note": ("the retracted rod plus 5 mm handling margin; the arm "
                         "must clear THIS, not the locked envelope")},
            "disengagement_order": [
                "1. ARM_HDRM LOCKED -> RELEASE_START (preload dumped)",
                "2. ARM_HDRM RELEASE_START -> RELEASED (rod retracts 6 mm)",
                "3. arm lifts off MID backup support (2.00 mm nominal gap, "
                "no force to overcome)",
                "4. arm lifts off G08 primary cradle",
                "5. arm lifts off G07 primary cradle",
                "6. arm reaches Q_RELEASE_CLEAR",
                "NOTE: this order is a DESIGN INTENT sequence; it has not been "
                "swept for clearance (G5 covers only frozen end states)"],
        }
        add("ARM_HDRM_CUP", "restraint cup", 1, "Ti-6Al-4V", TI,
            3.14159 * 14.0 ** 2 * 18.0 * 0.45,
            "engages the arm restraint boss", "sized to the reference block")
        add("ARM_HDRM_ROD", "preload rod", 1, "A286", STEEL,
            3.14159 * 4.0 ** 2 * 46.0,
            "6 mm candidate stroke, hard shoulder", "candidate stroke")
        add("ARM_HDRM_BASE", "deck bracket", 1, "Al 6061-T6", AL,
            40.0 * 40.0 * 22.0 * 0.4, "bolts to the bus deck",
            "footprint of the reference block")
        add("ARM_HDRM_SWITCH", "microswitch pair", 2, "assembly", 1.0e-3, 900.0,
            "redundant state sensing", "typical micro-D switch envelope")

        # ------------------------------------------------ camera ------------
        camera = {
            "designation": "SERVICE_CAMERA",
            "exists_in_assembly": False,
            "maturity": "DEFINED_NOT_MODELLED",
            "consequence": (
                "every camera-visibility criterion in this campaign is "
                "reported NOT_EVALUATED_NO_CAMERA_IN_ASSEMBLY and is NOT "
                "counted as passed -- including requirement 'camera usable' "
                "for Q_DEPLOYED_HOME"),
            "proposed_mount": {
                "host_link": "link6",
                "rationale": ("wrist mounting keeps the target in view through "
                              "the whole service approach without a separate "
                              "pointing mechanism"),
                "bracket": {"material": "Al 6061-T6", "mass_g": 34.0,
                            "envelope_mm": [40.0, 34.0, 26.0]}},
            "optical_frame": {
                "name": "camera_optical_frame",
                "parent": "link6",
                "convention": "REP-103 optical: +Z forward, +X right, +Y down",
                "offset_from_link6_mm": [0.0, -46.0, 58.0],
                "rpy_rad": [0.0, 0.0, 0.0],
                "status": "PROPOSED_NOT_CALIBRATED"},
            "field_of_view_deg": {"horizontal": 66.0, "vertical": 52.0,
                                  "status": "TYPICAL_CLASS_VALUE_NOT_SELECTED"},
            "views": {
                "STOW": ("OCCLUDED -- in stow the wrist faces the bus deck; "
                         "no useful view (geometric reading of the stowed "
                         "link6 box %s)" % [round(v, 1) for v in
                                            arms_s["B51_REF_link6_LINKLOCAL"]
                                            ["box"].tolist()]),
                "Q_DEPLOYED_HOME": "NOT_EVALUATED_NO_CAMERA",
                "SERVICE_GRASP": "NOT_EVALUATED_NO_CAMERA"},
        }
        add("CAMERA_BRACKET", "wrist bracket", 1, "Al 6061-T6", AL,
            40.0 * 34.0 * 26.0 * 0.28, "hosts the service camera",
            "proposed envelope")
        add("SERVICE_CAMERA", "camera module", 1, "COTS", 1.0e-3, 62000.0,
            "class placeholder, not a selected part",
            "typical small-sat camera mass 62 g")

        # ------------------------------------------------ harness -----------
        harness = {
            "designation": "ARM_HARNESS",
            "exists_in_assembly": False,
            "maturity": "DEFINED_NOT_MODELLED",
            "existing_bus_features": {
                "Harness_Passage_mm": envs["Harness_Passage"]["box"].tolist(),
                "Harness_Service_Loop_Left_mm":
                    envs["Harness_Service_Loop_Left"]["box"].tolist(),
                "Harness_Service_Loop_Right_mm":
                    envs["Harness_Service_Loop_Right"]["box"].tolist()},
            "entry_point": {"at": "bus Harness_Passage, +x end",
                            "coordinates_mm": [171.0, 0.0, -70.0]},
            "exit_point": {"at": "arm base_link connector face",
                           "coordinates_mm": [215.0, 0.0, 0.0]},
            "clamp_points": [
                {"id": "HC-1", "on": "Adapter_Plate", "x_mm": 192.0},
                {"id": "HC-2", "on": "base_link collar", "x_mm": 220.0},
                {"id": "HC-3", "on": "link1 shoulder", "note": "rotating"},
                {"id": "HC-4", "on": "link3 mid-span"},
                {"id": "HC-5", "on": "link6 wrist, before the camera"}],
            "service_loop": {"length_mm": 120.0, "location": "at HC-2/HC-3",
                             "purpose": "absorbs joint1 rotation"},
            "minimum_bend_radius_mm": 25.0,
            "bundle_outer_diameter_mm": 9.0,
            "sweep_envelope": {
                "poses": ["Q_DEPLOYED_HOME", "Q_SERVICE_READY"],
                "status": "NOT_COMPUTED_NO_HARNESS_GEOMETRY",
                "why": ("a sweep of a cable that does not exist would be a "
                        "fabricated envelope; the clamp scheme above is the "
                        "input to that sweep once the harness is modelled")},
        }
        add("ARM_HARNESS_BUNDLE", "cable bundle", 1, "PTFE/Cu", 2.2e-3,
            3.14159 * 4.5 ** 2 * 900.0, "9 mm bundle, ~900 mm routed length",
            "route length from entry to wrist")
        add("HARNESS_CLAMP", "P-clamp", 5, "Al + silicone", AL,
            600.0, "one per clamp point", "standard 9 mm P-clamp")

        # ------------------------------------------------ gripper -----------
        gripper = {
            "designation": "TWO_FINGER_GRIPPER",
            "cad_reality": {
                "solids_in_cad": 1,
                "cad_part": "B51_REF_gripper_detail_LINKLOCAL",
                "stowed_box_mm": [round(v, 2) for v in grip_s],
                "finding": ("the CAD carries a SINGLE gripper solid; it has "
                            "no separated fingers")},
            "urdf_reality": {
                "joints": ["gripper_joint1", "gripper_joint2"],
                "type": "prismatic",
                "travel_mm": [0.0, 71.5],
                "links_declared": ["gripper_left", "gripper_right"],
                "cad_mapping": ("MISSING for both fingers -- "
                                "F3R1_LINK_COMPONENT_MAPPING.csv records "
                                "gripper_left and gripper_right as MISSING")},
            "maturity": "SEPARATION_REQUIRED_NOT_DONE",
            "explicit_non_claim": (
                "the single visual gripper solid is NOT presented as two "
                "movable fingers, and no OPEN/PREGRASP/CLOSED/HOLDING CAD "
                "configuration is claimed to exist"),
            "states_defined": {
                "OPEN": {"finger_travel_mm": 71.5, "jaw_opening_mm": 143.0,
                         "status": "DEFINED_NOT_MODELLED"},
                "PREGRASP": {"finger_travel_mm": 55.0, "jaw_opening_mm": 110.0,
                             "status": "DEFINED_NOT_MODELLED"},
                "CLOSED": {"finger_travel_mm": 0.0, "jaw_opening_mm": 0.0,
                           "status": "DEFINED_NOT_MODELLED"},
                "HOLDING": {"finger_travel_mm": "target dependent",
                            "grip_force_N": "TBD_CONTACT_CASE",
                            "status": "DEFINED_NOT_MODELLED"}},
            "what_must_be_done": [
                "split B51_REF_gripper_detail into palm + two finger solids",
                "bind each finger to gripper_joint1 / gripper_joint2",
                "author the four states as CAD configurations",
                "re-run clearance with the fingers at OPEN (the widest state)"],
            "why_it_matters_for_this_gate": (
                "OPEN is the widest gripper state; all clearance numbers in "
                "this campaign were measured with the single closed-looking "
                "solid, so gripper clearance is valid for that solid only and "
                "is NOT valid for the open jaw"),
        }

        rep["arm_hdrm"] = hdrm
        rep["camera"] = camera
        rep["harness"] = harness
        rep["gripper"] = gripper
        rep["parts"] = parts
        rep["total_mass_g"] = round(sum(p["mass_g"] for p in parts), 2)
        rep["maturity_summary"] = {
            "ARM_HDRM": "COMPETITION_DEMONSTRATOR_ONLY / FLIGHT_TBD",
            "CAMERA": "DEFINED_NOT_MODELLED (all visibility NOT_EVALUATED)",
            "HARNESS": "DEFINED_NOT_MODELLED (no sweep computed)",
            "GRIPPER": "SEPARATION_REQUIRED_NOT_DONE"}
        rep["verdict"] = "G4_DEFINED_NOT_MODELLED"
        C.write_csv(OUTC, parts)
        C.write_json(OUTCAM, {"schema": "F3R2_CAMERA_HARNESS_GRIPPER_V1",
                              "camera": camera, "harness": harness,
                              "gripper": gripper})
        rep["protected_post"] = C.check_protected2("G4_POST")["verdict"]
    except Exception as exc:
        rep["verdict"] = "G4_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]

    C.write_json(OUTJ, rep)
    print("verdict:", rep["verdict"])
    for k, v in (rep.get("maturity_summary") or {}).items():
        print("  %-10s %s" % (k, v))
    if "parts" in rep:
        print("  parts:", len(rep["parts"]),
              "| mass %.1f g" % rep["total_mass_g"])
        for p in rep["parts"]:
            print("    %-22s x%-2d %-16s %8.2f g" % (p["part"], p["qty"],
                                                     p["material"],
                                                     p["mass_g"]))
    if rep["verdict"] == "G4_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G4_DEFINED_NOT_MODELLED" else 1)


if __name__ == "__main__":
    main()
