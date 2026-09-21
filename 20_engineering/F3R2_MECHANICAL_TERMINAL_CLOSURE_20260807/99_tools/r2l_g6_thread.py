# -*- coding: utf-8 -*-
"""F3R2 G6: external mass budget and the digital thread.

"External" means everything F3R2 adds OUTSIDE the accepted B601 URDF: the
wing-root interface, the three stow supports, the ARM HDRM, the camera, the
harness and their fasteners.  The accepted URDF's mass and inertia are NOT
touched -- they are a protected asset -- so this budget is a separate ledger
that a dynamics model adds to the arm, never a rewrite of it.

Mass source priority is recorded per line, in the required order:
  1 measured, 2 vendor, 3 CAD volume x density, 4 nominal/min/max estimate.
Nothing in this campaign is 1 or 2, so every line is 3 or 4 and says so.

Also emitted: frame mapping, link/component mapping, collision-asset manifest,
action-mask rules and the mechanical state machine -- the interfaces the
control and embodied-policy work will consume.
"""
import json
import sys
import traceback

import numpy as np

import r2_common as C
import r2_kin as K
import r2_pose as P

OUT = C.THREAD2
AL = 2.70e-3


def yaml_dump(obj, ind=0):
    sp = "  " * ind
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                out.append("%s%s:" % (sp, k))
                out.append(yaml_dump(v, ind + 1))
            elif isinstance(v, (dict, list)):
                out.append("%s%s: %s" % (sp, k,
                                         "{}" if isinstance(v, dict) else "[]"))
            else:
                out.append("%s%s: %s" % (sp, k, sc(v)))
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, (dict, list)):
                out.append("%s-" % sp)
                out.append(yaml_dump(v, ind + 1))
            else:
                out.append("%s- %s" % (sp, sc(v)))
    return "\n".join(out)


def sc(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(round(v, 6))
    if isinstance(v, str):
        return v if (v and all(c.isalnum() or c in "._-/+" for c in v)) \
            else json.dumps(v, ensure_ascii=False)
    return str(v)


def main():
    rep = {"schema": "F3R2_DIGITAL_THREAD_V1"}
    try:
        C.check_protected2("G6_PRE")
        wr = json.loads((C.SUP2 / "F3R2_WING_ROOT_INTERFACE.json")
                        .read_text(encoding="utf-8"))
        sup = json.loads((C.SUP2 / "F3R2_STOW_SUPPORT_DEFINITION.json")
                         .read_text(encoding="utf-8"))
        g4 = json.loads((C.HDRM2 / "F3R2_ARM_HDRM_DEFINITION.json")
                        .read_text(encoding="utf-8"))
        poses = json.loads((C.CFG2 / "F3R2_POSE_SEARCH.json")
                           .read_text(encoding="utf-8"))

        # ---------------- mass budget ----------------
        lines = []

        def add(group, part, qty, mass_g, source_tier, source, note,
                mounted_on, in_arm_inertia):
            lines.append({
                "group": group, "part": part, "qty": qty,
                "mass_g_total": round(mass_g, 3),
                "mass_source_tier": source_tier,
                "mass_source": source, "note": note,
                "mounted_on": mounted_on,
                "counts_in_accepted_arm_inertia": in_arm_inertia})

        for p in wr["parts"]:
            add("WING_ROOT_INTERFACE", p["part"], p["qty_per_side"] * 2,
                p["mass_g_per_side"] * 2, 3,
                "CAD volume x density (%s)" % p["material"],
                p["note"][:120], "solar wing panel / root", False)
        for p in sup["parts"]:
            add("STOW_SUPPORT", p["part"], p["qty"], p["mass_g"], 3,
                "CAD volume x density (%s)" % p["material"],
                p["note"][:120], "bus deck", False)
        for p in g4["parts"]:
            tier = 4 if p["part"] in ("SERVICE_CAMERA", "ARM_HDRM_SWITCH") else 3
            src = ("nominal class estimate, no part selected"
                   if tier == 4 else
                   "CAD volume x density (%s)" % p["material"])
            host = ("link6" if "CAMERA" in p["part"]
                    else "arm + bus" if "HARNESS" in p["part"]
                    else "bus deck")
            add("ARM_HDRM_CAMERA_HARNESS", p["part"], p["qty"], p["mass_g"],
                tier, src, p["note"][:120], host, False)

        # fasteners: counted, not hand-waved
        n_m3 = 4 * 3 + 4          # three supports + HDRM base
        add("FASTENERS", "M3x8 socket cap, A286", n_m3, n_m3 * 1.15, 4,
            "standard fastener mass table", "support and HDRM attachment",
            "bus deck", False)
        n_pin = 2 * 3
        add("FASTENERS", "3 mm dowel pin, Ti", n_pin, n_pin * 0.31, 4,
            "standard dowel mass", "support location", "bus deck", False)

        total = sum(l["mass_g_total"] for l in lines)
        by_group = {}
        for l in lines:
            by_group[l["group"]] = round(
                by_group.get(l["group"], 0.0) + l["mass_g_total"], 3)
        # honest uncertainty: tier-4 lines carry a wide band
        t4 = sum(l["mass_g_total"] for l in lines
                 if l["mass_source_tier"] == 4)
        t3 = total - t4
        budget = {
            "total_g": round(total, 2),
            "by_group_g": by_group,
            "tier3_cad_volume_g": round(t3, 2),
            "tier4_estimate_g": round(t4, 2),
            "min_estimate_g": round(t3 * 0.95 + t4 * 0.6, 2),
            "max_estimate_g": round(t3 * 1.15 + t4 * 1.8, 2),
            "uncertainty_note": (
                "tier-3 lines are CAD volume x handbook density with a "
                "ribbing factor, so +/-15%; tier-4 lines are class estimates "
                "with no part selected, so -40% / +80%.  No line is measured "
                "or vendor-confirmed."),
            "explicitly_excluded": [
                "accepted B601 arm mass and inertia (protected asset, "
                "unchanged)",
                "spacecraft V2_2 structure (unchanged)",
                "solar panel mass (SSOT placeholder issue, out of scope here)"],
        }
        C.write_csv(OUT / "F3R2_EXTERNAL_MECHANICAL_MASS_BUDGET.csv", lines,
                    fields=["group", "part", "qty", "mass_g_total",
                            "mass_source_tier", "mass_source", "mounted_on",
                            "counts_in_accepted_arm_inertia", "note"])

        # ---------------- external mass / inertia yaml ----------------
        mi = {"schema": "F3R2_EXTERNAL_MASS_INERTIA_V1",
              "frame": "spacecraft assembly frame (mm, g)",
              "accepted_arm_urdf": {"sha256": C.R.URDF_SHA,
                                    "modified_by_f3r2": False},
              "budget": budget,
              "inertia": {
                  "status": "NOT_COMPUTED",
                  "why": ("inertia requires the parts to exist as solids; all "
                          "F3R2 external hardware is DEFINED_NOT_MODELLED, so "
                          "an inertia tensor here would be fabricated"),
                  "what_is_available": ("per-part mass and mounting station, "
                                        "sufficient for a point-mass "
                                        "perturbation study")},
              "how_dynamics_should_use_this": [
                  "add these masses at their mounting stations as point "
                  "masses on the spacecraft body, NOT on the arm links",
                  "do not modify the accepted arm URDF inertia",
                  "treat the totals as provisional until parts are modelled"]}
        (OUT / "F3R2_EXTERNAL_MASS_INERTIA.yaml").write_text(
            yaml_dump(mi) + "\n", encoding="utf-8")

        # ---------------- frame mapping ----------------
        T = P.K.T_MOUNT
        frames = {
            "schema": "F3R2_FRAME_MAPPING_V1",
            "root_frame": "spacecraft_assembly_frame",
            "units": "mm, radians",
            "frames": {
                "spacecraft_assembly_frame": {
                    "parent": None,
                    "definition": ("the top-level assembly origin of "
                                   "F3R2_..._OPERATIONAL_BASELINE.SLDASM")},
                "arm_base_frame": {
                    "parent": "spacecraft_assembly_frame",
                    "transform_mm_rows": T.tolist(),
                    "equals": "URDF base_link frame",
                    "clock_deg": P.K.CLOCK_DEG,
                    "station": P.K.MOUNT_STATION,
                    "source": ("F3R1_TOP_INTEGRATION_REPORT.json "
                               "arm_mount_transform_mm")},
                "camera_optical_frame": {
                    "parent": "link6",
                    "status": "PROPOSED_NOT_CALIBRATED",
                    "source": "F3R2_CAMERA_HARNESS_GRIPPER.json"},
                "hinge_axis_left": {
                    "parent": "spacecraft_assembly_frame",
                    "axis": [1.0, 0.0, 0.0], "point_mm": [-61.0, 143.15, 0.0],
                    "source": "B-rep probe of Hinge_Pin_Left"},
                "hinge_axis_right": {
                    "parent": "spacecraft_assembly_frame",
                    "axis": [1.0, 0.0, 0.0], "point_mm": [-61.0, -143.15, 0.0],
                    "source": "B-rep probe of Hinge_Pin_Right"},
            },
            "urdf_link_frames": {l: "URDF-defined, see accepted arm_b601_v1.urdf"
                                 for l in K.LINK_MESHES},
        }
        (OUT / "F3R2_FRAME_MAPPING.yaml").write_text(
            yaml_dump(frames) + "\n", encoding="utf-8")

        # ---------------- link <-> component mapping ----------------
        arms = P.arm_parts("DEPLOYED")
        lc = []
        for cad, a in arms.items():
            lc.append({"urdf_link": a["link"], "cad_component": cad,
                       "status": "MAPPED",
                       "collision_mesh_source": "CAD STEP tessellation",
                       "triangles": a["triangles"]})
        for miss in ("gripper_left", "gripper_right"):
            lc.append({"urdf_link": miss, "cad_component": "",
                       "status": "MISSING_GRIPPER_NOT_SEPARATED",
                       "collision_mesh_source": "",
                       "triangles": 0})
        C.write_csv(OUT / "F3R2_LINK_COMPONENT_MAPPING.csv", lc)

        # ---------------- collision asset manifest ----------------
        man = P.load_manifest("DEPLOYED")
        cam = []
        for cad, a in arms.items():
            cam.append({"asset": cad, "role": "ARM_LINK_COLLISION",
                        "urdf_link": a["link"], "path": a["path"],
                        "triangles": a["triangles"],
                        "deflection_mm": man["linear_deflection_mm"],
                        "frame": "spacecraft_assembly_frame at q_as_built",
                        "posed_by": "URDF FK relative transform",
                        "authoritative": False,
                        "authority_note": ("tessellation of the CAD B-rep; "
                                           "the B-rep is authoritative")})
        for name, e in P.env_parts("DEPLOYED").items():
            cam.append({"asset": name, "role": e["role"], "urdf_link": "",
                        "path": e["path"], "triangles": e["triangles"],
                        "deflection_mm": man["linear_deflection_mm"],
                        "frame": "spacecraft_assembly_frame",
                        "posed_by": "static",
                        "authoritative": False,
                        "authority_note": (
                            "REFERENCE ONLY -- must never be used as physical "
                            "collision evidence"
                            if e["role"] == "REFERENCE_ONLY" else
                            "placeholder block, not a real support"
                            if e["role"] == "SADDLE_PLACEHOLDER" else
                            "tessellation of the CAD B-rep")})
        C.write_csv(OUT / "F3R2_COLLISION_ASSET_MANIFEST.csv", cam)

        # ---------------- action mask rules ----------------
        pv = poses["results"]
        mask = {
            "schema": "F3R2_ACTION_MASK_RULES_V1",
            "purpose": ("what an embodied policy is mechanically ALLOWED to "
                        "command, given only what this campaign proved"),
            "joint_limits_deg": {j: list(K.LIMITS_DEG[j])
                                 for j in K.ARM_JOINTS},
            "hard_rules": [
                {"id": "AM-1",
                 "rule": "never command outside the accepted URDF joint limits",
                 "enforcement": "clamp and reject, fail-closed"},
                {"id": "AM-2",
                 "rule": ("keep >= 3.0 deg from any joint limit during "
                          "autonomous motion"),
                 "enforcement": "reject the action"},
                {"id": "AM-3",
                 "rule": ("only the frozen runtime poses and swept segments "
                          "between them are authorised as autonomous motion"),
                 "authorised_poses": ["Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR",
                                      "Q_SERVICE_READY"],
                 "enforcement": "reject unlisted targets"},
                {"id": "AM-4",
                 "rule": ("never rely on G07/G08/Mid contact: they are "
                          "placeholder blocks, not supports"),
                 "enforcement": "no contact-based state estimation there"},
                {"id": "AM-5",
                 "rule": ("never treat Release_Clearance_Envelope or "
                          "Launch_Lock_Interface_Reference as physical bodies"),
                 "enforcement": "excluded from the collision set"},
                {"id": "AM-6",
                 "rule": ("gripper clearance is valid only for the single "
                          "closed-looking CAD solid; OPEN jaw clearance is "
                          "unverified"),
                 "enforcement": ("no autonomous jaw opening near structure "
                                 "until the fingers are separated")},
                {"id": "AM-7",
                 "rule": ("STOW and the HDRM release sequence are not "
                          "autonomous states"),
                 "enforcement": "ground command only"},
            ],
            "clearance_budget_mm": {
                "target": 5.0,
                "measured_at_home": pv["Q_DEPLOYED_HOME"]["chosen"]
                ["evaluation"]["min_moving_link_to_bus_mm"],
                "tessellation_deflection": man["linear_deflection_mm"],
                "note": ("mesh tier; add the deflection as tolerance when "
                         "sizing a runtime safety margin")},
        }
        (OUT / "F3R2_ACTION_MASK_RULES.yaml").write_text(
            yaml_dump(mask) + "\n", encoding="utf-8")

        # ---------------- mechanical state machine ----------------
        sm = {
            "schema": "F3R2_MECHANICAL_STATE_MACHINE_V1",
            "runtime_states": [
                {"state": "DEPLOYED_NOMINAL", "arm_pose": "Q_DEPLOYED_HOME",
                 "wings": "both deployed 90 deg", "autonomous": True},
                {"state": "SERVICE_STAGING", "arm_pose": "Q_SERVICE_READY",
                 "wings": "both deployed 90 deg", "autonomous": True},
                {"state": "SAFE_STOP", "arm_pose": "hold current",
                 "wings": "unchanged", "autonomous": True,
                 "note": "brakes engaged, no new motion accepted"},
                {"state": "MANUAL_RECOVERY", "arm_pose": "ground commanded",
                 "wings": "unchanged", "autonomous": False},
            ],
            "non_runtime_states": [
                {"state": "STOWED_ENGINEERING_CANDIDATE",
                 "arm_pose": "Q_STOW_ENGINEERING_CANDIDATE",
                 "hold": "O13_V3_CANDIDATE_HOLD_PROVISIONAL"},
                {"state": "SOLAR_DEPLOY_ARM_LOCKED",
                 "arm_pose": "Q_STOW_ENGINEERING_CANDIDATE",
                 "hold": "wing deploy TRANSIT unauthorised"},
                {"state": "L_FAIL / R_FAIL / DEPLOY_FAILED_BOTH",
                 "arm_pose": "Q_STOW_ENGINEERING_CANDIDATE",
                 "hold": "off-nominal wing states, arm stays restrained"},
                {"state": "PARTIAL",
                 "hold": "REGISTERED_NOT_GEOMETRICALLY_DIFFERENTIATED; not in "
                         "the runtime enum"},
                {"state": "SERVICE",
                 "hold": "PENDING_RATIFICATION_HOLD (G2)"},
            ],
            "transitions_authorised": [
                {"from": "DEPLOYED_NOMINAL", "to": "SERVICE_STAGING",
                 "evidence": "G5 swept"},
                {"from": "SERVICE_STAGING", "to": "DEPLOYED_NOMINAL",
                 "evidence": "G5 swept (reverse of the same segment)"},
                {"from": "any", "to": "SAFE_STOP", "evidence": "always allowed"},
            ],
            "transitions_not_authorised": [
                "anything into or out of STOW (HDRM release chain incomplete)",
                "SERVICE_DOCKING / GRASP / TRANSPORT / ASSEMBLY / "
                "RETRIEVED_NOMINAL (no q vectors exist)",
                "wing deployment TRANSIT",
            ],
        }
        (OUT / "F3R2_MECHANICAL_STATE_MACHINE.yaml").write_text(
            yaml_dump(sm) + "\n", encoding="utf-8")

        rep["mass_budget"] = budget
        rep["outputs"] = sorted(p.name for p in OUT.iterdir())
        rep["verdict"] = "G6_DIGITAL_THREAD_EMITTED"
        rep["protected_post"] = C.check_protected2("G6_POST")["verdict"]
    except Exception as exc:
        rep["verdict"] = "G6_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]

    C.write_json(OUT / "F3R2_DIGITAL_THREAD.json", rep)
    print("verdict:", rep["verdict"])
    if "mass_budget" in rep:
        b = rep["mass_budget"]
        print("  external mass total: %.1f g  (tier3 %.1f / tier4 %.1f)"
              % (b["total_g"], b["tier3_cad_volume_g"], b["tier4_estimate_g"]))
        print("  range: %.1f .. %.1f g" % (b["min_estimate_g"],
                                           b["max_estimate_g"]))
        for g, m in b["by_group_g"].items():
            print("    %-28s %8.2f g" % (g, m))
        print("  outputs:", rep["outputs"])
    else:
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G6_DIGITAL_THREAD_EMITTED" else 1)


if __name__ == "__main__":
    main()
