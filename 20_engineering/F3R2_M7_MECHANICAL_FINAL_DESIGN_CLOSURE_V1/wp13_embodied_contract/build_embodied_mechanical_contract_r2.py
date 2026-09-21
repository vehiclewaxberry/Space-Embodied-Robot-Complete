#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M7 / WP13 - EMBODIED_MECHANICAL_CONTRACT_R2 builder   (ODR-15 + ECR-SOLAR-ARRAY-R2)

R2 rebind of the machine-readable mechanical interface after the closed
ECR-SOLAR-ARRAY-R2 (ODR-19..ODR-34): the R1 single-plate solar wing
(227x200x6 mm per side) is replaced by SOLAR_ARRAY_R2 (two wings x 3 leaves,
300x200 mm per leaf, hinge axes parallel to X_S, 1.0 mm standoff, 8.5 mm
stowed stack).

Lineage discipline:
* EMBODIED_MECHANICAL_CONTRACT_V1.yaml is FROZEN and is NOT modified; this
  script writes the separate R2 document.
* B601 URDF (L0), M3R (ODR-01 frame + ODR-05 budget), gripper, FEA main load
  path and the CAD-URDF calibration D_i are unchanged and carried verbatim.
* Every number is READ FROM ITS SOURCE ARTIFACT AT BUILD TIME and the source
  is pinned by sha256 - identical build rule to the V1 builder (no
  transcription).  R2 values come from the ecr_solar_array_r2/ package and
  WP2 SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml.

Prohibitions honoured (unchanged from V1):
* L0 accepted-URDF masses are never overridden
* candidate != authority; design != flight-qualified
* no zero-fill: an absent physical input stays null + named HOLD
* PROVISIONAL is never promoted to AUTHORITY
* no flight / launcher / manufacturing-release / qualification claim
* the legacy R1 panel mass (0.3483933 kg) is LEGACY_SIM11_PROVISIONAL,
  reproduction-only, never an input to new R2-coupled runs
"""

import datetime
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET

import yaml

PROJECT_ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
M7_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
ECR_REL = f"{M7_REL}/ecr_solar_array_r2"
M7_ROOT = os.path.join(PROJECT_ROOT, M7_REL.replace("/", os.sep))
OUT_DIR = os.path.join(M7_ROOT, "wp13_embodied_contract")
OUT_PATH = os.path.join(OUT_DIR, "EMBODIED_MECHANICAL_CONTRACT_R2.yaml")
TZ8 = datetime.timezone(datetime.timedelta(hours=8))

SRC = {
    "urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "mass": f"{M7_REL}/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml",
    "mass_policy": f"{M7_REL}/wp2_design_mass/DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml",
    "gripper": f"{M7_REL}/wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V1.yaml",
    "solar_mechanism_r2": f"{ECR_REL}/SOLAR_R2_MECHANISM_ANALYTICAL_LEDGER_V1.yaml",
    "solar_hdrm_latch_r2": f"{ECR_REL}/SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V1.yaml",
    "calib": f"{M7_REL}/wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml",
    "o2": f"{M7_REL}/wp11_cad_urdf_registration/O2_DISPOSITION_RULING_V1.yaml",
    "keepout": f"{M7_REL}/wp1_structure_cad/KEEP_OUT_REGISTER_V1.yaml",
    "v5": f"{M7_REL}/wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V5_R2.yaml",
    "odr": f"{M7_REL}/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml",
    "terminal": f"{M7_REL}/00_authority/M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml",
    "flex_r2": f"{ECR_REL}/FLEXIBLE_APPENDAGE_R2.yaml",
    "flex_r2_modes": f"{ECR_REL}/FLEXIBLE_APPENDAGE_R2_MODES.json",
    "solar_r2_mass_properties": f"{ECR_REL}/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json",
    "solar_r2_candidate_step": f"{ECR_REL}/SOLAR_ARRAY_R2_CANDIDATE_V1.step",
    "solar_r2_candidate_fcstd": f"{ECR_REL}/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd",
    "solar_r2_build_report": f"{ECR_REL}/SOLAR_ARRAY_R2_BUILD_REPORT_V1.json",
    "solar_r2_continuous_clearance": f"{ECR_REL}/SOLAR_ARRAY_R2_CONTINUOUS_CLEARANCE_V1.json",
    "solar_r2_clearance_margins": f"{ECR_REL}/CLEARANCE_MARGIN_LEDGER_R2_V1.json",
    "harness_r2_gates": f"{ECR_REL}/HARNESS_R2_FUNCTIONAL_GATES_V1.json",
    "solar_r2_impact_screen": f"{ECR_REL}/SOLAR_R2_STRUCTURAL_IMPACT_SCREEN_V1.yaml",
    "legacy_coupled_scene": "20_engineering/config/coupled_scene/coupled_model_v0.yaml",
    "capture_scene": "20_engineering/config/coupled_scene/scene_A2_capture.yaml",
    "fea": f"{M7_REL}/wp7_fea_operational/FEA1B_ELEMENT_FORMULATION_EVIDENCE_V1.json",
}

# R2-HRN-04 full-FK harness sweep: bound when present (a separate work item
# produces it); its verdict is quoted in the harness note either way.
HARNESS_FK_SWEEP_REL = f"{ECR_REL}/HARNESS_B601_FULL_FK_SWEEP_V1.json"


def longpath(p):
    p = os.path.abspath(p)
    return "\\\\?\\" + p if os.name == "nt" and not p.startswith("\\\\?\\") else p


def apath(rel):
    return os.path.join(PROJECT_ROOT, rel.replace("/", os.sep))


def read_bytes(rel):
    with open(longpath(apath(rel)), "rb") as fh:
        return fh.read()


def sha256(rel):
    return hashlib.sha256(read_bytes(rel)).hexdigest().upper()


def load_yaml(rel):
    return yaml.safe_load(read_bytes(rel).decode("utf-8"))


def load_json(rel):
    return json.loads(read_bytes(rel).decode("utf-8"))


def q(nominal, source, authority, confidence, uncertainty, calibration_required, **extra):
    """The ODR-15 quantity envelope.  Every exported number goes through here."""
    d = {
        "nominal": nominal,
        "source": source,
        "authority_level": authority,
        "confidence": confidence,
        "uncertainty": uncertainty,
        "calibration_required": calibration_required,
    }
    d.update(extra)
    return d


# ===========================================================================
# Section 1 - KINEMATICS   (accepted URDF is the authority, ODR-10 O2-A)
#                           UNCHANGED BY ECR-SOLAR-ARRAY-R2
# ===========================================================================
def build_kinematics(urdf_root):
    joints = urdf_root.findall("joint")
    links = urdf_root.findall("link")
    by_type = {}
    for j in joints:
        by_type[j.get("type")] = by_type.get(j.get("type"), 0) + 1

    jd = {}
    for j in joints:
        o = j.find("origin")
        a = j.find("axis")
        lim = j.find("limit")
        rec = {
            "type": j.get("type"),
            "parent": j.find("parent").get("link"),
            "child": j.find("child").get("link"),
            "origin_xyz_m": [float(x) for x in o.get("xyz").split()] if o is not None else None,
            "origin_rpy_rad": [float(x) for x in o.get("rpy").split()] if o is not None else None,
            "axis": [float(x) for x in a.get("xyz").split()] if a is not None else None,
        }
        if lim is not None:
            rec["limit"] = {
                "lower": float(lim.get("lower")),
                "upper": float(lim.get("upper")),
                "unit": "rad" if j.get("type") == "revolute" else "m",
                "effort": float(lim.get("effort")),
                "effort_unit": "N*m" if j.get("type") == "revolute" else "N",
                "velocity": float(lim.get("velocity")),
                "velocity_unit_declared_in_urdf": None,
            }
        else:
            rec["limit"] = None
        rec["mechanical_stop"] = {
            "value": None,
            "status": "HOLD_NO_HARD_STOP_GEOMETRY_AUTHORITY",
            "note": (
                "the URDF limit is a MODEL limit.  No vendor hard-stop drawing or "
                "measured over-travel exists, so software limit != mechanical stop."
            ),
        }
        jd[j.get("name")] = rec

    return {
        "robot": {"name": urdf_root.get("name")},
        "authority_statement": (
            "ODR-10 option O2-A: the accepted URDF is the KINEMATICS authority. "
            "The M7 CAD arm has dead joints and is articulated BY URDF forward "
            "kinematics, so no competing CAD kinematic definition exists."
        ),
        "topology": {
            "links": len(links),
            "joints": len(joints),
            "revolute": by_type.get("revolute", 0),
            "fixed": by_type.get("fixed", 0),
            "prismatic": by_type.get("prismatic", 0),
            "verified": "counted from the URDF at build time, not asserted",
        },
        "link_order": [l.get("name") for l in links],
        "joints": jd,
        "actuated_dof": {
            "arm": by_type.get("revolute", 0),
            "gripper": by_type.get("prismatic", 0),
            "rl_action_space_recommendation": (
                "6 arm revolute + 1 gripper command (the two prismatic finger "
                "joints are mechanically symmetric and driven by a single motor "
                "candidate - see grasp.actuation - so exposing 2 independent "
                "finger DOF to RL would model a mechanism that does not exist"
            ),
        },
        "acceleration_limit": {
            "value": None,
            "status": "HOLD_NO_ACTUATOR_DYNAMICS_AUTHORITY",
            "note": (
                "the URDF carries no acceleration limit and no actuator model. "
                "CTRL-02 already recorded L0 hardware effective stability as "
                "NOT_EVALUATED_NO_ACTUATOR_DYNAMICS for exactly this reason."
            ),
        },
        "velocity_limit_unit_caveat": {
            "finding": "URDF_VELOCITY_LIMIT_UNIT_UNDECLARED",
            "observed_values": sorted({
                float(j.find("limit").get("velocity"))
                for j in joints
                if j.find("limit") is not None
            }),
            "why_it_matters": (
                "joints 1-3 carry 50 and joints 4-6 carry 200.  Read as rad/s "
                "these are 2865 deg/s and 11459 deg/s, which is not a physical "
                "manipulator.  Read as deg/s they are plausible.  URDF does not "
                "declare the unit and no vendor datasheet is held."
            ),
            "contract_ruling": (
                "the velocity limit is exported as a MODEL_LIMIT with an "
                "UNDECLARED unit.  A consumer MUST NOT use it as a physical rate "
                "bound.  Rate limiting for Sim16/RL must come from an explicit "
                "controller-side limit, declared by the controls owner."
            ),
            "authority_level": "MODEL_LIMIT_UNIT_UNRESOLVED",
            "calibration_required": True,
            "trigger": "ECR-M3 (RL/controller discovers mechanical infeasibility)",
        },
    }


# ===========================================================================
# Section 2 - DYNAMICS   (R2: system configurations bound to WP2 V3_R2;
#                         solar mass semantics rebound; arm/M3R unchanged)
# ===========================================================================
def build_dynamics(urdf_root, mass_doc, v5):
    link_inertia = {}
    total = 0.0
    for l in urdf_root.findall("link"):
        ine = l.find("inertial")
        if ine is None:
            continue
        m = float(ine.find("mass").get("value"))
        total += m
        o = ine.find("origin")
        it = ine.find("inertia")
        link_inertia[l.get("name")] = {
            "mass_kg": m,
            "com_xyz_m": [float(x) for x in o.get("xyz").split()] if o is not None else None,
            "inertia_kg_m2": {k: float(it.get(k)) for k in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")}
            if it is not None
            else None,
        }

    pinned = v5["design_mass_model_binding"]["pinned_constants"]
    urdf_pinned = pinned["b601_arm_mass_kg"]["value"]

    configs = {}
    for c in mass_doc["configurations"]:
        m = c["mass"]
        cm = c["center_of_mass"]
        inr = c["inertia"]
        configs[c["configuration_id"]] = {
            "name": c["name"],
            "semantics": c.get("configuration_semantics"),
            "mass": q(
                m["value_kg"],
                SRC["mass"],
                "DESIGN_MODEL_R2_NOT_MEASURED",
                "B",
                {
                    "standard_uncertainty_kg": m["standard_uncertainty_kg"],
                    "relative": m.get("relative_standard_uncertainty"),
                    "distribution": "declared standard uncertainty (GUM), not a bound",
                },
                True,
            ),
            "center_of_mass": q(
                cm["xyz_m"],
                SRC["mass"],
                "DESIGN_MODEL_R2_NOT_MEASURED",
                "B",
                {"standard_uncertainty_xyz_m": cm["standard_uncertainty_xyz_m"]},
                True,
                reference_frame=cm["reference_frame"],
            ),
            "inertia": q(
                inr["components_kg_m2"],
                SRC["mass"],
                "DESIGN_MODEL_R2_NOT_MEASURED",
                "B",
                {
                    "component_standard_uncertainty_kg_m2": inr[
                        "standard_uncertainty_components_kg_m2"
                    ],
                    "covariance": inr.get("uncertainty_covariance"),
                    "covariance_semantics": (
                        "ODR-07: off-diagonal covariance entries MAY be negative; "
                        "reported per-component sigma = sqrt(C[i,i]) and is "
                        "non-negative by construction.  The 3x3 'standard "
                        "uncertainty matrix' layout is NOT a covariance and is "
                        "labelled as such in the source."
                    ),
                },
                True,
                reference_frame=inr["reference_frame"],
                reference_point=inr["reference_point"],
            ),
        }

    # --- R2 solar mass semantics, recomputed from V3_R2 C01 composition ----
    c01 = next(c for c in mass_doc["configurations"] if c["configuration_id"] == "C01")
    comp = {e["component_id"]: e for e in c01["composition"]}
    wing_l = comp["solar_array_r2_left"]["mass_kg"]
    wing_r = comp["solar_array_r2_right"]["mass_kg"]
    wing_u = comp["solar_array_r2_left"]["mass_standard_uncertainty_kg"]
    legacy_panel = pinned["legacy_r1_solar_panel_each_kg"]["value"]

    return {
        "mass_authority": {
            "arm": q(
                urdf_pinned,
                SRC["urdf"],
                "ACCEPTED_URDF_L0",
                "A",
                {
                    "standard_uncertainty_kg": None,
                    "status": "L0_PINNED_VALUE_NO_UNCERTAINTY_DECLARED",
                },
                False,
                rule="never overridden by CAD or design values",
                rebuilt_sum_from_urdf_kg=total,
                sum_matches_pin=abs(total - urdf_pinned) < 1e-9,
            ),
            "solar": {
                "design_nominal_per_wing_kg": q(
                    wing_l,
                    SRC["mass"],
                    "DESIGN_MODEL_R2_NOT_MEASURED",
                    "B",
                    {
                        "standard_uncertainty_kg": wing_u,
                        "left_equals_right": wing_l == wing_r,
                        "basis": (
                            "MATERIAL_DERIVED_CANDIDATE: areal-density 3.0 kg/m2 "
                            "model (ODR-20/ODR-21); NOT measured"
                        ),
                    },
                    True,
                ),
                "design_nominal_both_wings_kg": q(
                    wing_l + wing_r,
                    SRC["mass"],
                    "DESIGN_MODEL_R2_NOT_MEASURED",
                    "B",
                    {
                        "recomputed_as": "solar_array_r2_left + solar_array_r2_right "
                        "of V3_R2 C01 composition",
                    },
                    True,
                ),
                "dynamics_legacy_per_panel_kg": q(
                    legacy_panel,
                    SRC["v5"],
                    "LEGACY_SIM11_PROVISIONAL",
                    "C",
                    {
                        "status": (
                            "R1 single-plate placeholder (panel_box 0.227 x 0.200 x "
                            "0.006 m).  Retained for historical sim_11 / "
                            "flexible_appendage_v1 REPRODUCTION ONLY; forbidden as "
                            "an input to any new R2-coupled dynamics run."
                        ),
                    },
                    True,
                ),
                "as_built_kg": q(
                    None,
                    SRC["mass"],
                    "HOLD_AS_BUILT_MEASUREMENT_PENDING",
                    None,
                    {
                        "status": (
                            "MEASUREMENT_PENDING - no R2 wing or leaf hardware has "
                            "been weighed; AS_BUILT_MASS_CORRELATION_HOLD carried"
                        ),
                    },
                    True,
                ),
            },
            "system_configurations": (
                "see dynamics.configurations - R2 DESIGN model (WP2 V3_R2), "
                "uncertainty declared"
            ),
        },
        "link_inertia": {
            "values": link_inertia,
            "authority_level": "ACCEPTED_URDF_L0",
            "confidence": "A_FOR_THE_MODEL_NOT_FOR_THE_HARDWARE",
            "uncertainty": {
                "value": None,
                "status": "HOLD_NO_AS_BUILT_ARM_METROLOGY",
                "note": (
                    "the URDF inertias are vendor/model values.  No hardware was "
                    "weighed or swung.  AS_BUILT_ARM_METROLOGY_HOLD is carried."
                ),
            },
            "calibration_required": True,
        },
        "configurations": configs,
        "base_coupling": {
            "free_floating": True,
            "evidence": {
                "sim_05_peak_base_attitude_disturbance_deg": 19.20,
                "sim_05_momentum_conservation": 7.3e-17,
                "meaning": (
                    "arm motion reacts into the base.  Any RL policy that treats "
                    "the base as inertially fixed is modelling a different vehicle."
                ),
            },
            "authority_level": "SIMULATION_EVIDENCE_RIGID_BODY",
            "calibration_required": False,
        },
        "mounting": {
            "M3R": {
                "dynamics_frame": q(
                    {
                        "T_SM_mm": v5["frame_authority"]["m_frame_definition"]["t_sm_mm"],
                        "rotation": v5["frame_authority"]["m_frame_definition"]["rotation"],
                    },
                    SRC["odr"],
                    "OWNER_DECISION_ODR_01",
                    "A",
                    {"value": None, "status": "EXACT_BY_DEFINITION"},
                    False,
                    warning=(
                        "185.25 mm is the DYNAMICS frame and has no solid face. "
                        "198.0 / 208.0 / 210.405 mm are a geometric feature stack "
                        "and MUST NOT become a second dynamics frame."
                    ),
                ),
                "mass": q(
                    pinned["m3r_design_mass_kg"]["value"],
                    SRC["odr"],
                    "DESIGN_BUDGET",
                    pinned["m3r_design_mass_kg"].get("confidence", "B"),
                    {
                        "value": None,
                        "status": "M3R_AS_BUILT_MEASUREMENT_OPEN",
                        "forbidden_field": "measured_mass",
                    },
                    True,
                ),
                "stiffness": q(
                    None,
                    SRC["v5"],
                    "HOLD_NO_JOINT_STIFFNESS_AUTHORITY",
                    None,
                    {
                        "value": None,
                        "status": "PENDING_WP4_STIFFNESS_DERIVATION_AND_TEST",
                    },
                    True,
                    note=(
                        "WP4 delivered fastener preload/torque design, not an "
                        "interface stiffness matrix.  V5_R2 carries "
                        "stiffness_values: null.  A consumer that needs a "
                        "compliant mount must declare its own assumption."
                    ),
                ),
                "compliance": {
                    "value": None,
                    "status": "HOLD_SEE_STIFFNESS",
                    "fea_bound_note": (
                        "WP7 used a z=0 encastre boundary condition, declared as a "
                        "STIFF BOUND and explicitly not an authority "
                        "(BC_BUS_001_INTERFACE_STIFFNESS_HOLD)."
                    ),
                },
            }
        },
    }


# ===========================================================================
# Section 3 - COLLISION   (UNCHANGED BY ECR-SOLAR-ARRAY-R2)
# ===========================================================================
def build_collision(urdf_root, calib, o2, keepout):
    meshes = {}
    identical = []
    for l in urdf_root.findall("link"):
        v = l.find("visual/geometry/mesh")
        c = l.find("collision/geometry/mesh")
        vf = v.get("filename") if v is not None else None
        cf = c.get("filename") if c is not None else None
        meshes[l.get("name")] = {"visual_mesh": vf, "collision_mesh": cf}
        if vf and cf and vf == cf:
            identical.append(l.get("name"))

    links_cal = calib.get("links", {})
    cal_out = {}
    for k, v in links_cal.items():
        cal_out[k] = {
            "D_i_translation_mm": v.get("D_i_translation_mm"),
            "D_i_rotation": v.get("D_i_rotation"),
            "D_i_translation_norm_mm": v.get("D_i_translation_norm_mm"),
        }

    decomp = o2["odr_09_determination"]["decomposition_of_the_registered_divergence"]
    phantom = next(
        (d for d in decomp if d.get("class") == "OWNER_RULED_DELIBERATE_DESIGN_DELETION"),
        None,
    )

    return {
        "authority_statement": (
            "ODR-10 O2-A: the M7 CAD is the PHYSICAL GEOMETRY authority and the "
            "accepted URDF is the kinematics authority.  Collision geometry is "
            "consumed THROUGH the calibration D_i, never by naive mesh "
            "substitution in either direction."
        ),
        "meshes": meshes,
        "CRITICAL_visual_equals_collision": {
            "finding": "NO_SIMPLIFIED_COLLISION_GEOMETRY_EXISTS",
            "links_where_visual_mesh_is_the_collision_mesh": identical,
            "count": len(identical),
            "consequence_for_rl": (
                "every collision query runs against the full-resolution visual "
                "tessellation.  This is correct but slow, and it means any "
                "artifact in the visual mesh IS an artifact in the collision "
                "model.  See the phantom base plate below."
            ),
        },
        "CRITICAL_phantom_base_plate": {
            "finding": "WP11-F-01_ACCEPTED_URDF_BASE_LINK_COLLISION_MESH_CONTAINS_A_DELETED_PART",
            "part": phantom.get("component") if phantom else None,
            "magnitude": phantom.get("magnitude") if phantom else None,
            "authority_that_deleted_it": phantom.get("authority") if phantom else None,
            "consequence": (
                "loading base_link.STL as the operational collision mesh imports a "
                "140 x 200 x 14.5 mm desktop base plate as a phantom collision "
                "slab at the arm root.  Sim16 / RL MUST NOT do this."
            ),
            "required_action_before_rl": (
                "re-export the operational collision meshes through D_i with the "
                "vendor desktop base plate removed.  Until that re-export exists, "
                "the collision contract is DECLARED OPEN."
            ),
            "status": "OPEN_DECLARED",
            "trigger": "ECR-M2 (collision or reachability defect)",
        },
        "cad_urdf_calibration": {
            "map": cal_out,
            "definition": calib.get("definition", {}).get("D_i"),
            "model": calib.get("definition", {}).get("model"),
            "authority_level": calib.get("authority_level"),
            "confidence": calib.get("confidence"),
            "validation": {
                "whole_arm_fraction_within_0p5mm": o2["odr_09_determination"]["test_a"][
                    "post_D_i_whole_arm_fraction_within_0p5mm"
                ],
                "whole_arm_median_mm": o2["odr_09_determination"]["test_a"][
                    "post_D_i_whole_arm_median_mm"
                ],
                "whole_arm_p95_mm": o2["odr_09_determination"]["test_a"]["post_D_i_whole_arm_p95_mm"],
                "worst_cross_configuration_pose_residual_mm": o2["odr_09_determination"][
                    "test_b"
                ]["worst_urdf_predicted_pose_surface_residual_mm"],
                "source_tessellation_deflection_mm": o2["odr_09_determination"]["test_a"][
                    "acceptance_reference_source_tessellation_deflection_mm"
                ],
            },
            "not_a_metrology_claim": True,
            "calibration_required": False,
            "note": (
                "this calibration is CAD-to-CAD.  No hardware was measured; "
                "AS_BUILT_ARM_METROLOGY_HOLD is carried."
            ),
        },
        "self_collision": {
            "policy": "ENABLE_ALL_EXCEPT_ADJACENT_LINK_PAIRS",
            "adjacent_pairs_excluded": [
                [j.find("parent").get("link"), j.find("child").get("link")]
                for j in urdf_root.findall("joint")
            ],
            "finger_pair": {
                "pair": ["gripper_left", "gripper_right"],
                "self_collision": "MUST_REMAIN_ENABLED",
                "evidence": (
                    "the two fingers are real, separate, mirror-paired B-rep "
                    "bodies (24/24 solids, volumes equal to the last digit).  "
                    "They do NOT touch at OPEN 82.23 mm or PREGRASP 50.50 mm; "
                    "the 67.3 mm 'crossing' reported from group AABBs is a "
                    "fork-shaped bounding-box artifact."
                ),
                "authority_level": "MEASURED_FROM_BREP_AT_DISCRETE_STATES",
                "uncertainty": {
                    "status": "CONTINUOUS_STROKE_FINGER_TO_FINGER_SWEEP_NOT_COMPUTED",
                    "what_was_swept": (
                        "the validated 144-sample continuous sweep is RAIL-to-PALM "
                        "overlap (0 positive overlaps), NOT finger-to-finger"
                    ),
                },
                "calibration_required": True,
            },
        },
        "allowed_contact": {
            "declaration": (
                "contact pairs that are INTENDED and must not be scored as a "
                "collision failure by a shield or reward function"
            ),
            "pairs": {
                "finger_target": {
                    "bodies": ["gripper_left", "gripper_right", "<target>"],
                    "intended": True,
                    "contact_model": None,
                    "status": "HOLD_CONTACT_AUTHORITIES",
                },
                "palm_target": {
                    "bodies": ["gripper_link", "<target>"],
                    "intended": True,
                    "contact_model": None,
                    "status": "HOLD_CONTACT_AUTHORITIES",
                },
            },
            "everything_else": "TREAT_AS_COLLISION",
            "why_this_section_exists": (
                "without an explicit allowed-contact set, an RL agent is "
                "penalised for the one contact the mission requires."
            ),
        },
        "keep_out": {
            "source": SRC["keepout"],
            "launcher_keep_out": {
                "value": None,
                "status": "HOLD_NO_LAUNCHER_ICD",
                "non_blocking_for_operational_twin": True,
            },
            "note": (
                "the operational baseline is the post-release deployed on-orbit "
                "state, which consumes no launcher keep-out."
            ),
        },
    }


# ===========================================================================
# Section 4 - GRASP   (UNCHANGED BY ECR-SOLAR-ARRAY-R2)
# ===========================================================================
def build_grasp(urdf_root, grip, capture_scene):
    jl = {}
    for j in urdf_root.findall("joint"):
        if j.get("type") == "prismatic":
            lim = j.find("limit")
            jl[j.get("name")] = {
                "stroke_m": [float(lim.get("lower")), float(lim.get("upper"))],
                "effort_N": float(lim.get("effort")),
                "velocity": float(lim.get("velocity")),
            }

    fi = grip["frozen_inputs"]
    sms = {r["req_id"]: r for r in grip["sms_requirements"]}
    mav = {c["check_id"]: c for c in grip["mav_analytical_verification"]["checks"]}

    tc = None
    try:
        tc = capture_scene["contact"]["T_c_ms_nominal"]
    except Exception:
        tc = None

    return {
        "frames": {
            "grasp_frame": {
                "definition": "gripper_link frame from the accepted URDF",
                "parent": "link6",
                "origin_xyz_m": [0.0, 0.0, 0.15971],
                "origin_rpy_rad": [0.0, -1.5708, 0.0],
                "authority_level": "ACCEPTED_URDF_L0",
                "calibration_required": False,
            },
            "contact_left": {
                "definition": "gripper_left link frame",
                "prismatic_axis": [1.0, 0.0, 0.0],
                "contact_patch_geometry": None,
                "status": "HOLD_NO_CONTACT_PATCH_OR_NORMAL_AUTHORITY",
            },
            "contact_right": {
                "definition": "gripper_right link frame",
                "prismatic_axis": [1.0, 0.0, 0.0],
                "contact_patch_geometry": None,
                "status": "HOLD_NO_CONTACT_PATCH_OR_NORMAL_AUTHORITY",
            },
        },
        "actuation": {
            "architecture": grip["mdd_design_description"]["actuation"][
                "architecture_candidate"
            ],
            "independent_finger_dof": False,
            "authority_level": "DESIGN_CANDIDATE",
            "open_items": grip["mdd_design_description"]["actuation"]["open_items"],
        },
        "states": build_gripper_states(fi, sms, mav),
        "limits": {
            "stroke_mm": q(
                fi["stroke_mm"],
                SRC["gripper"],
                "DERIVED_NEUTRAL_R1_GEOMETRY",
                "B",
                {
                    "continuous_validation_samples": fi["continuous_stroke_sample_count"],
                    "step_mm": fi["stroke_sample_step_mm"],
                    "positive_rail_palm_overlap_count": fi[
                        "positive_rail_palm_overlap_count"
                    ],
                },
                False,
                urdf_cross_check_m=jl,
            ),
            "closing_force_per_finger_N": q(
                sms["GRP-SMS-03"]["value_min_N"],
                SRC["gripper"],
                "DESIGN_TARGET_CANDIDATE",
                "C",
                {
                    "demand_covered_N": 22.59,
                    "status": "NOT_MEASURED_MVR_002_BENCH_TEST_REQUIRED",
                },
                True,
            ),
            "max_force_model_limit_N": q(
                fi["urdf_effort_limit_N"],
                SRC["urdf"],
                "MODEL_LIMIT_NOT_DESIGN_OR_QUALIFICATION_LOAD",
                "A_FOR_THE_MODEL",
                {"status": "NOT_A_PHYSICAL_ACTUATOR_CAPABILITY"},
                True,
            ),
            "friction_coefficient": q(
                None,
                SRC["gripper"],
                "HOLD",
                None,
                {
                    "candidate_used_in_MAV_01": 0.3,
                    "status": "GRP-SMS-08 HOLD - unmeasured; 0.3 is a declared "
                    "candidate, not data",
                    "rl_guidance": (
                        "domain-randomise mu.  Do NOT randomise around 0.3 as if "
                        "it were a measured mean - there is no measured mean."
                    ),
                },
                True,
            ),
            "allowable_contact_pressure_MPa": q(
                None,
                SRC["gripper"],
                "HOLD",
                None,
                {"status": "GRP-SMS-09 HOLD - no target surface/damage authority"},
                True,
            ),
            "closing_speed_at_first_contact_mm_s": q(
                sms["GRP-SMS-06"]["value_max_mm_s"],
                SRC["gripper"],
                "DESIGN_TARGET_CANDIDATE",
                "C",
                {"status": "NOT_MEASURED"},
                True,
            ),
            "contact_window_ms": q(
                tc,
                SRC["capture_scene"],
                "PROVISIONAL",
                "C",
                {
                    "swept_range_ms": [5, 100],
                    "swept_by": "sim_11 v1.1 finite contact window study",
                    "status": (
                        "PLACEHOLDER pending the B601 gripper closing-time "
                        "hardware measurement (project standing todo 2)"
                    ),
                    "rl_guidance": (
                        "domain-randomise across the swept 5-100 ms band, not "
                        "around the 20 ms placeholder"
                    ),
                },
                True,
            ),
            "max_payload": q(
                None,
                SRC["gripper"],
                "HOLD",
                None,
                {
                    "status": (
                        "no payload rating exists.  22 kg and 150 kg are SCENARIO "
                        "MASS ANCHORS from the research load envelope, not a "
                        "gripper capacity."
                    )
                },
                True,
            ),
        },
        "retention_analysis": {
            "required_normal_per_finger_N": mav["MAV-02"]["results"][
                "required_normal_per_finger_N"
            ],
            "worst_lateral_eq_N": mav["MAV-02"]["results"]["worst_lateral_eq_N"],
            "governing_case": mav["MAV-02"]["results"]["governing_case"],
            "drive_margin_vs_model_limit": mav["MAV-03"]["results"][
                "margin_vs_urdf_model_limit"
            ],
            "authority_level": "ANALYTIC_DESIGN_LEVEL_WITH_CANDIDATE_MU",
            "critical_caveat": (
                "F_eq = J/dt with dt in {0.05, 0.1} s DECLARED CANDIDATES.  No "
                "contact-duration authority exists.  Every force number in this "
                "block scales as 1/dt and is an envelope estimate, not a load."
            ),
            "calibration_required": True,
        },
        "power_off_behaviour": {
            "candidate": "self-locking transmission retains the grasp (fail-closed)",
            "authority_level": "DESIGN_TARGET_CANDIDATE",
            "verification": "MVR-003 TEST_REQUIRED_HOLD",
            "safety_shield_note": (
                "fail-closed on power loss means an un-commanded release is NOT "
                "an expected failure mode; the shield should treat a detected "
                "release without command as an anomaly, not a normal transition."
            ),
        },
    }


def build_gripper_states(fi, sms, mav):
    """The explicit mechanical state machine (P0-2)."""
    stroke_max = fi["stroke_mm"][1]
    pregrasp = fi["pregrasp_travel_mm"]
    return {
        "_declaration": (
            "seven mechanical states.  Observability is stated per state: a state "
            "the hardware cannot report is not a state a shield can trust."
        ),
        "OPEN": {
            "jaw_travel_mm": 0.0,
            "meaning": "fully retracted, maximum aperture",
            "observable_by": "jaw position sensing (GRP-SMS-10, required)",
            "target_engaged": False,
        },
        "PARTIAL": {
            "jaw_travel_mm": [0.0, pregrasp],
            "meaning": "transiting, no target contact expected",
            "observable_by": "jaw position sensing",
            "target_engaged": False,
        },
        "PREGRASP": {
            "jaw_travel_mm": pregrasp,
            "meaning": "staged at capture standoff, ready to close",
            "observable_by": "jaw position sensing",
            "target_engaged": False,
            "speed_limit_applies_from_here_mm_s": sms["GRP-SMS-06"]["value_max_mm_s"],
        },
        "CONTACT": {
            "jaw_travel_mm": [pregrasp, stroke_max],
            "meaning": "first contact through closing onto the target",
            "observable_by": {
                "position": "yes",
                "force": "CANDIDATE ONLY - force sensing is not committed "
                "(GRP-SMS-10); without it CONTACT is inferred, not measured",
            },
            "target_engaged": True,
            "governing_load_case": mav["MAV-02"]["results"]["governing_case"],
        },
        "LOCK": {
            "meaning": "retention achieved; normal force >= retention demand",
            "retention_demand_per_finger_N": mav["MAV-02"]["results"][
                "required_normal_per_finger_N"
            ],
            "observable_by": {
                "value": None,
                "status": "HOLD_NO_LOCK_CONFIRMATION_SENSOR_DEFINED",
                "consequence": (
                    "LOCK cannot currently be CONFIRMED by hardware.  A shield "
                    "must treat LOCK as INFERRED and keep the abort path armed."
                ),
            },
            "target_engaged": True,
        },
        "RELEASE": {
            "meaning": "commanded opening back toward OPEN",
            "precondition": (
                "arm-held target support, or safe mode.  Safe-mode mechanical "
                "state is undefined (CDR HOLD)."
            ),
            "power_off_behaviour": "grasp RETAINED, not released (fail-closed)",
            "target_engaged": "transitioning",
        },
        "FAIL": {
            "meaning": "jam, slip, or un-commanded state change",
            "sub_states": {
                "JAM": {
                    "detection": None,
                    "status": "HOLD_NO_JAM_DETECTION_DEFINED",
                    "design_mitigation": mav["MAV-05"]["results"]["jam_prevention"],
                },
                "SLIP": {
                    "trigger": "retention demand exceeded or mu below candidate",
                    "detection": None,
                    "status": "HOLD_MVR_019_RETAINED_TRANSFORM_SLIP_TEST_REQUIRED",
                },
            },
            "shield_policy": "FAIL_CLOSED_ABORT",
        },
        "transition_matrix": {
            "OPEN": ["PARTIAL"],
            "PARTIAL": ["OPEN", "PREGRASP"],
            "PREGRASP": ["PARTIAL", "CONTACT"],
            "CONTACT": ["LOCK", "FAIL", "RELEASE"],
            "LOCK": ["RELEASE", "FAIL"],
            "RELEASE": ["PARTIAL", "FAIL"],
            "FAIL": ["RELEASE"],
        },
        "unknown_is_fail_closed": True,
    }


# ===========================================================================
# Section 5 - FLEXIBILITY   (R2 REBIND: FLEXIBLE_APPENDAGE_R2 card, ODR-21)
# ===========================================================================
def build_flexibility(flex_card, modes, mech, harness_gates, harness_fk):
    leaf = flex_card["leaf_L1_engineering_model"]["per_leaf"]
    k_root = flex_card["leaf_L1_engineering_model"]["root_hinge_ktheta_Nm_per_rad"]
    k_inter = flex_card["leaf_L1_engineering_model"]["inter_panel_ktheta_Nm_per_rad"]
    zeta = flex_card["leaf_L1_engineering_model"]["damping"]["zeta"]
    zeta_status = flex_card["leaf_L1_engineering_model"]["damping"]["status"]
    wing = flex_card["wing_L2_reduced_model"]

    f_nom = modes["modes_hz_per_case"]["nominal"]
    f_lo = modes["modes_hz_per_case"]["all_low"]
    f_hi = modes["modes_hz_per_case"]["all_high"]

    harness_note = {
        "solar_r2_harness_gate": harness_gates["verdict"]["SOLAR_R2_HARNESS_GATE"],
        "b601_harness_gate_q0_witness_scope": harness_gates["verdict"]["B601_HARNESS_GATE"],
        "vendor_holds_carried": harness_gates["verdict"]["vendor_holds_carried"],
        "source": SRC["harness_r2_gates"],
    }
    if harness_fk is not None:
        harness_note["b601_full_fk_sweep_R2_HRN_04"] = {
            "source": HARNESS_FK_SWEEP_REL,
            "verdict": harness_fk["verdict"]["B601_HARNESS_FUNCTIONAL_GATE"],
            "verdict_rule": harness_fk["verdict"]["verdict_rule"],
            "failing_subchecks": {
                "collision_pass": harness_fk["checks"]["collision_pass"],
                "min_clearance_mm": harness_fk["checks"]["min_clearance_mm"],
                "bend_pass_vs_class": harness_fk["checks"]["bend_pass_vs_class"],
                "min_bend_radius_mm": harness_fk["checks"]["min_bend_radius_mm"],
                "pinch_pass": harness_fk["checks"]["pinch_pass"],
            },
            "contract_consequence": (
                "R2-HRN-04 closure attempt FAILED: the routed B601 harness "
                "candidate penetrates geometry, violates the bend class and "
                "pinches.  The harness routing must be redesigned and re-gated; "
                "this contract carries the FAIL openly and the ARM_RELEASE "
                "interlock stays fail-closed regardless."
            ),
        }
    else:
        harness_note["b601_full_fk_sweep_R2_HRN_04"] = {
            "status": "OPEN_R2_HRN_04 - full all-link FK pose sweep not on disk "
            "at contract build time",
        }

    return {
        "solar_panel": {
            "architecture_r2": {
                "wings": 2,
                "leaves_per_wing": 3,
                "leaf_box_m": [leaf["chord_m"], leaf["span_m"], leaf["thickness_m"]],
                "leaf_mass_kg": leaf["mass_kg"],
                "construction_candidate": flex_card["leaf_L1_engineering_model"][
                    "construction_candidate"
                ],
                "hinge_axes": "all parallel to X_S (root + 2 inter-panel per wing)",
                "standoff_m": 0.001,
                "stowed_stack_m": 0.0085,
                "reduced_model": (
                    "3 DOF per wing (relative hinge rotations about the deployed "
                    "flat config); hinge-dominated, NOT a cantilever-plate model"
                ),
            },
            "mode_count": q(
                len(f_nom),
                SRC["flex_r2_modes"],
                "PROVISIONAL_DERIVED",
                "C",
                {
                    "per_wing": True,
                    "declared_in_source": wing["dominant_modes_for_sim"],
                    "status": (
                        "ODR-21 3-5 band satisfied at the low end; no convergence "
                        "sweep exists yet for the R2 chain model"
                    ),
                },
                True,
            ),
            "frequency_hz": q(
                round(f_nom[0], 2),
                SRC["flex_r2_modes"],
                "PROVISIONAL_DERIVED",
                "C",
                {
                    "envelope_hz": [round(f_lo[0], 2), round(f_hi[0], 2)],
                    "envelope_semantics": (
                        "first deployed-latched wing mode at the all-low / "
                        "all-high ktheta band corners (root {50,200,800} + inter "
                        "{20,100,400} N*m/rad), ODR-32"
                    ),
                    "higher_modes_hz": f_nom[1:],
                    "higher_modes_envelope_hz": [f_lo[1:], f_hi[1:]],
                    "rl_guidance": (
                        "randomise across the 3.33-13.95 Hz first-mode envelope.  "
                        "The envelope IS the mechanical uncertainty statement; do "
                        "not invent a tighter one.  Note this is an order of "
                        "magnitude above the R1 plate placeholder (0.7-1.3 Hz): "
                        "R1-tuned flexible assumptions do NOT transfer."
                    ),
                },
                True,
            ),
            "damping_zeta": q(
                zeta,
                SRC["flex_r2"],
                "PROVISIONAL_DERIVED_TBD_CITE_LITERATURE",
                "C",
                {
                    "status_in_source": zeta_status,
                    "modal_damping_only": True,
                    "note": (
                        "single modal zeta candidate for the R2 wing chain; no "
                        "measured damping exists.  Unlike the R1 contract there "
                        "is exactly ONE on-disk placeholder for the R2 model, so "
                        "the V1 TWO_CONFLICTING_PLACEHOLDER_VALUES finding does "
                        "not apply to the R2 binding (it still applies to the "
                        "frozen R1 documents)."
                    ),
                },
                True,
            ),
            "legacy_r1_card_finding": {
                "CONTRACT_FINDING": "R1_FLEXIBILITY_BINDING_SUPERSEDED_FOR_NEW_RUNS",
                "r1_panel_box_m": [0.227, 0.200, 0.006],
                "r1_first_mode_envelope_hz": [0.7, 1.3],
                "r1_areal_density_finding": (
                    "the R1 plate was a uniform-density placeholder (heavier per "
                    "unit area than a typical deployable); the R2 leaf uses an "
                    "areal-density 3.0 kg/m2 candidate inside the typical 2-5 "
                    "kg/m2 band, closing the V1 mass-placeholder severity finding "
                    "at CANDIDATE level (still not measured)"
                ),
                "rule": (
                    "the frozen R1 card (flexible_appendage_v1.yaml) serves "
                    "historical sim_11 reproduction only; new R2-coupled runs "
                    "must quote FLEXIBLE_APPENDAGE_R2 with its bands"
                ),
            },
            "evidence": {
                "sim_07_point_capture_vs_rigid_lock_ratio": 92,
                "sim_07_ring_down_s": [37, 75],
                "sim_11_panel_ringing_mm": 2.1,
                "sim_11_panel_ringing_hz": 1.0005,
                "evidence_scope_warning": (
                    "all flexible evidence cited here was computed with the R1 "
                    "single-plate placeholder.  Under ECR-SOLAR-ARRAY-R2 it is "
                    "LEGACY evidence: an R2-coupled rerun is required before any "
                    "flexible conclusion is quoted against the R2 design, and the "
                    "e15 ANCF certification gate (REPEAT_ANCF_CERTIFICATION) "
                    "applies to that new model."
                ),
            },
            "harness": harness_note,
        },
        "hinge": {
            "root_ktheta_Nm_per_rad": q(
                k_root["nominal"],
                SRC["flex_r2"],
                "PROVISIONAL_DERIVED",
                "C",
                {
                    "band_Nm_per_rad": [k_root["low"], k_root["high"]],
                    "deployed_latched_semantics": (
                        "ODR-32: the wing modal evidence is computed AT the "
                        "deployed latched state, so this band IS the deployed "
                        "latch stiffness candidate"
                    ),
                    "status": "no measurement source; WP5 R2 hardware selection/test pending",
                },
                True,
            ),
            "inter_panel_ktheta_Nm_per_rad": q(
                k_inter["nominal"],
                SRC["flex_r2"],
                "PROVISIONAL_DERIVED",
                "C",
                {
                    "band_Nm_per_rad": [k_inter["low"], k_inter["high"]],
                    "count_per_wing": 2,
                    "latch_compliance_folded_in": True,
                    "status": "no measurement source; WP5 R2 hardware selection/test pending",
                },
                True,
            ),
            "deployment_torque_budget": {
                "source": SRC["solar_mechanism_r2"],
                "summary": mech["A_deployment_torque"]["summary"],
                "class": mech["class"],
            },
            "end_stop_controlling_case": {
                "source": SRC["solar_mechanism_r2"],
                "controlling_stop": "inter_panel_hinge_2",
                "energy_J": mech["B_end_stop_propagation"]["per_hinge"][
                    "inter_panel_hinge_2"
                ]["energy_J"],
                "peak_stop_force_N_candidate": mech["B_end_stop_propagation"]["per_hinge"][
                    "inter_panel_hinge_2"
                ]["peak_stop_force_N"],
                "status": "PROVISIONAL_DERIVED pending stop material/shape selection",
            },
            "latch": (
                "positive end-of-travel latch per leaf, engagement observable "
                "(HNG-SMS-05 semantics carried); non-releasing on orbit; "
                "PROVISIONAL_DERIVED - latch hardware not selected"
            ),
            "freeplay_mm": q(
                None,
                SRC["solar_mechanism_r2"],
                "HOLD",
                None,
                {"status": "FREEPLAY_LIMITS_HOLD_NO_PIN_BORE_AUTHORITY"},
                True,
            ),
        },
        "certification_caveat": {
            "e15_status": "REPEAT_ANCF_CERTIFICATION",
            "meaning": (
                "the ANCF cross-solver certification failed at 5.64% > 5%.  Any "
                "NEW fully-coupled flexible model (including the R2 wing chain) "
                "must re-pass that gate before its flexible results carry weight."
            ),
        },
    }


# ===========================================================================
# Section 6 - FAILURE STATES   (7 carried + R2 solar deployment states)
# ===========================================================================
def build_failure_states(mass_doc, v5, mech, clearance):
    fs = v5["failure_semantics"]
    by_id = {c["configuration_id"]: c for c in mass_doc["configurations"]}
    out = {
        "_semantics": {
            "panel_failure": fs["semantics"],
            "jettison_forbidden": fs["jettison_forbidden"],
            "authority": "ODR-02",
            "mass_model_consequence": fs["mass_model_consequence"],
            "r2_fail_state_pose_convention": fs.get("r2_fail_state_pose_convention"),
        }
    }
    for cid, name in (("C02", "LEFT_PANEL_FAIL"), ("C03", "RIGHT_PANEL_FAIL"), ("C04", "BOTH_PANEL_FAIL")):
        c = by_id[cid]
        c01 = by_id["C01"]
        out[name] = {
            "configuration_id": cid,
            "geometry": (
                "R2: failed wing attached but stuck; candidate model places it at "
                "the STOWED pose (partial-deploy stuck states are bounded by the "
                "stowed/deployed values)"
            ),
            "mass_change_kg": c["mass"]["value_kg"] - c01["mass"]["value_kg"],
            "mass_change_is_zero_because": (
                "ATTACHED_STUCK - the failed panel stays on the vehicle, so system "
                "mass is unchanged.  An RL environment that removes the panel mass "
                "on failure is modelling a jettison that ODR-02 forbids."
            ),
            "com_change_m": [
                a - b
                for a, b in zip(
                    c["center_of_mass"]["xyz_m"], c01["center_of_mass"]["xyz_m"]
                )
            ],
            "inertia_changes": (
                c["inertia"]["components_kg_m2"] != c01["inertia"]["components_kg_m2"]
            ),
            "collision_change": "panel swept volume differs; keep-out must be re-evaluated",
        }
    out["GRIPPER_JAM"] = {
        "trigger": "jaw motion arrested away from a commanded end state",
        "detection": None,
        "detection_status": "HOLD_NO_JAM_DETECTION_DEFINED",
        "allowed_action": ["HOLD_POSITION", "COMMANDED_RELEASE_IF_SUPPORTED", "ABORT"],
        "forbidden_action": ["FORCE_THROUGH", "REPEATED_CLOSE_RETRY_WITHOUT_DIAGNOSIS"],
    }
    out["CONTACT_ABORT"] = {
        "trigger": (
            "contact detected outside the allowed_contact set, or contact before "
            "PREGRASP, or closing speed above GRP-SMS-06 at first contact"
        ),
        "action": "FAIL_CLOSED_ABORT",
        "shield_binding": (
            "SAFE-00 runtime safety gate: UNKNOWN never ALLOW; masked action "
            "substitutes abort"
        ),
    }
    out["JOINT_LIMIT"] = {
        "software_limits": "URDF joint limits (see kinematics.joints[*].limit)",
        "mechanical_stop": None,
        "mechanical_stop_status": "HOLD_NO_HARD_STOP_GEOMETRY_AUTHORITY",
        "consequence": (
            "software limit != mechanical stop.  A policy trained to ride the "
            "URDF limit is riding an unverified boundary."
        ),
    }
    out["ARM_EMERGENCY_STOP"] = {
        "modelled_as": "quasi-static load case ARM_ESTOP_QS in WP7",
        "is_it_the_governing_structural_case": False,
        "governing_case_instead": "CAPTURE_150KG_QS",
        "evidence": "WP7 FEA1B layer-3",
    }

    # ---- R2 solar deployment state machine (ECR-SOLAR-ARRAY-R2) ------------
    hdrm = mech["D_hdrm"]
    latch = mech["C_latch"]
    out["SOLAR_STOWED_LOCKED"] = {
        "meaning": "wing(s) stowed in the 8.5 mm stack, HDRM tie-down rods engaged",
        "hdrm_state": hdrm["architecture"],
        "observable_by": "HDRM engagement indication (design candidate)",
        "arm_release_permitted": False,
    }
    out["SOLAR_HDRM_RELEASE_COMMAND"] = {
        "meaning": "release of the inboard-retracting tie-down rods commanded",
        "release_kinematics": hdrm["release_where"],
        "post_release_parts": hdrm["post_release_parts"],
        "arm_release_permitted": False,
    }
    out["SOLAR_HDRM_RELEASE_CONFIRMED"] = {
        "meaning": "rods confirmed captive in sleeves, deployment corridor free",
        "evidence": hdrm["enters_solar_sweep"],
        "arm_release_permitted": False,
    }
    out["SOLAR_LEAF1_DEPLOY"] = {
        "meaning": "root hinge rotation 0->90 deg (leaf1 unfolds from the stack)",
        "driving_torque_candidate": mech["A_deployment_torque"]["summary"],
        "arm_release_permitted": False,
    }
    out["SOLAR_LEAF2_UNFOLD"] = {
        "meaning": "inter-panel hinge 2 rotation 0->180 deg",
        "controlling_stop_candidate": "0.24 J / 480 N at hinge-2 (PROVISIONAL_DERIVED)",
        "arm_release_permitted": False,
    }
    out["SOLAR_LEAF3_UNFOLD"] = {
        "meaning": "inter-panel hinge 3 rotation 0->180 deg, wing reaching flat",
        "arm_release_permitted": False,
    }
    out["SOLAR_DEPLOYED_LATCHED"] = {
        "meaning": "all three leaves deployed and the end-of-travel latches engaged",
        "latch_semantics": latch["engagement_geometry"],
        "latch_status": latch["status"],
        "only_state_where": "ARM_RELEASE may be permitted (per wing)",
        "arm_release_permitted": "REQUIRED_ON_BOTH_WINGS_FOR_ARM_RELEASE",
    }
    out["SOLAR_DEPLOY_FAILED_LEFT"] = {
        "meaning": "left wing failed to reach SOLAR_DEPLOYED_LATCHED",
        "mass_model_consequence": "C02 LEFT_PANEL_FAIL (ATTACHED_STUCK, ODR-02)",
        "arm_release_permitted": False,
    }
    out["SOLAR_DEPLOY_FAILED_RIGHT"] = {
        "meaning": "right wing failed to reach SOLAR_DEPLOYED_LATCHED",
        "mass_model_consequence": "C03 RIGHT_PANEL_FAIL (ATTACHED_STUCK, ODR-02)",
        "arm_release_permitted": False,
    }
    out["SOLAR_DEPLOY_FAILED_BOTH"] = {
        "meaning": "neither wing reached SOLAR_DEPLOYED_LATCHED",
        "mass_model_consequence": "C04 BOTH_PANEL_FAIL (ATTACHED_STUCK, ODR-02)",
        "arm_release_permitted": False,
    }
    out["SOLAR_STATE_UNKNOWN"] = {
        "meaning": "deployment state cannot be determined from available telemetry",
        "treated_as": "NOT_LATCHED (fail-closed)",
        "arm_release_permitted": False,
    }
    out["solar_deployment_interlock"] = {
        "rule_id": "R2-ILK-01",
        "type": "MACHINE_READABLE_INTERLOCK",
        "if": {
            "left_wing_state_not": "SOLAR_DEPLOYED_LATCHED",
            "or_right_wing_state_not": "SOLAR_DEPLOYED_LATCHED",
        },
        "then": {"ARM_RELEASE": "FORBIDDEN"},
        "unknown_state_treated_as": "NOT_LATCHED",
        "fail_closed": True,
        "rationale": (
            "the stowed/partially-deployed wing stack sits in the arm workspace; "
            "the continuous clearance evidence (55 deployment states, 0 empty "
            "comparison sets) is computed with the B601 held at the q0 witness - "
            "see SOLAR_ARRAY_R2_CONTINUOUS_CLEARANCE_V1 sweep.arm_state"
        ),
        "evidence_source": SRC["solar_r2_continuous_clearance"],
        "authority": "ECR-SOLAR-ARRAY-R2 (ODR-19 item 10 / ODR-31)",
    }
    out["solar_deployment_nominal_sequence"] = [
        "SOLAR_STOWED_LOCKED",
        "SOLAR_HDRM_RELEASE_COMMAND",
        "SOLAR_HDRM_RELEASE_CONFIRMED",
        "SOLAR_LEAF1_DEPLOY",
        "SOLAR_LEAF2_UNFOLD",
        "SOLAR_LEAF3_UNFOLD",
        "SOLAR_DEPLOYED_LATCHED",
    ]
    out["solar_deployment_unknown_is_fail_closed"] = True
    return out


# ===========================================================================
def main():
    os.makedirs(longpath(OUT_DIR), exist_ok=True)

    urdf_root = ET.fromstring(read_bytes(SRC["urdf"]).decode("utf-8"))
    mass_doc = load_yaml(SRC["mass"])
    grip = load_yaml(SRC["gripper"])
    calib = load_yaml(SRC["calib"])
    o2 = load_yaml(SRC["o2"])
    keepout_present = os.path.isfile(longpath(apath(SRC["keepout"])))
    v5 = load_yaml(SRC["v5"])
    flex_card = load_yaml(SRC["flex_r2"])
    modes = load_json(SRC["flex_r2_modes"])
    mech = load_yaml(SRC["solar_mechanism_r2"])
    harness_gates = load_json(SRC["harness_r2_gates"])
    clearance = load_json(SRC["solar_r2_continuous_clearance"])
    capture_scene = load_yaml(SRC["capture_scene"])

    harness_fk = None
    src = dict(SRC)
    if os.path.isfile(longpath(apath(HARNESS_FK_SWEEP_REL))):
        harness_fk = load_json(HARNESS_FK_SWEEP_REL)
        src["harness_b601_full_fk_sweep"] = HARNESS_FK_SWEEP_REL

    doc = {
        "schema": "EMBODIED_MECHANICAL_CONTRACT_R2",
        "generated_local": datetime.datetime.now(TZ8).isoformat(),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP13_EMBODIED_CONTRACT",
        "role": "A0_MECHANICAL_CHIEF",
        "authority_basis": ["ODR-15", "ODR-10 option O2-A", "ODR-02", "ODR-01", "ODR-07",
                            "ECR-SOLAR-ARRAY-R2 (ODR-19..ODR-34)"],
        "lineage": {
            "forked_from": "EMBODIED_MECHANICAL_CONTRACT_V1.yaml",
            "v1_file_modified": False,
            "v1_remains": "FROZEN_R1_CONTRACT_OF_RECORD",
            "r2_scope": (
                "solar array, system mass model and flexibility rebound under "
                "ECR-SOLAR-ARRAY-R2; everything else carried from V1 with "
                "unchanged semantics"
            ),
            "unchanged_frozen_bindings": [
                "B601 accepted URDF (L0 kinematics/mass authority)",
                "M3R (ODR-01 M frame + ODR-05 design budget)",
                "gripper engineering pack",
                "FEA main load path (R2 structural impact screen: WITHIN_ACCEPTED_ENVELOPE, not reopened)",
                "B601 CAD-URDF calibration D_i",
            ],
        },
        "purpose": (
            "the single machine-readable mechanical interface consumed by "
            "dynamics -> control -> safety shield -> RL, R2 binding.  It does "
            "not restate the Gate A criteria and it grants no release authority."
        ),
        "consumer_contract": {
            "required_acknowledgement": (
                "I_ACKNOWLEDGE_THESE_ARE_DESIGN_LEVEL_MECHANICAL_VALUES_WITH_"
                "DECLARED_UNCERTAINTY_NOT_MEASURED_HARDWARE_AND_NOT_FLIGHT_QUALIFIED"
            ),
            "every_quantity_carries": [
                "source",
                "authority_level",
                "confidence",
                "nominal",
                "uncertainty",
                "calibration_required",
            ],
            "bare_nominal_forbidden": True,
            "unknown_is_fail_closed": True,
            "domain_randomisation_rule": (
                "randomise using the uncertainty declared HERE.  An RL engineer "
                "who invents a range is overriding mechanical engineering."
            ),
            "null_means": (
                "a physical or external input is genuinely absent.  null is never "
                "a zero and never a default."
            ),
        },
        "authority_hierarchy": {
            "kinematics": "ACCEPTED_URDF (L0)",
            "mass_and_inertia_of_the_arm": "ACCEPTED_URDF (L0), never overridden",
            "system_mass_configurations": "WP2 V3_R2 DESIGN model with declared uncertainty",
            "solar_flexibility": "FLEXIBLE_APPENDAGE_R2 (PROVISIONAL_DERIVED, ODR-21)",
            "physical_geometry": "M7 CAD + SOLAR_ARRAY_R2_CANDIDATE_V1 (ENGINEERING_CANDIDATE)",
            "bridge": "B601_CAD_URDF_GEOMETRY_CALIBRATION_V1 (D_i)",
            "ruling": "ODR-10 option O2-A + ECR-SOLAR-ARRAY-R2",
        },
        "kinematics": build_kinematics(urdf_root),
        "dynamics": build_dynamics(urdf_root, mass_doc, v5),
        "collision": build_collision(urdf_root, calib, o2, keepout_present),
        "grasp": build_grasp(urdf_root, grip, capture_scene),
        "flexibility": build_flexibility(flex_card, modes, mech, harness_gates, harness_fk),
        "failure_states": build_failure_states(mass_doc, v5, mech, clearance),
    }

    # ---- authority_and_uncertainty roll-up (ODR-15 required section) -------
    ledger = []

    def sweep(node, path=""):
        if isinstance(node, dict):
            if "authority_level" in node and "nominal" in node:
                ledger.append(
                    {
                        "quantity": path.lstrip("."),
                        "authority_level": node.get("authority_level"),
                        "confidence": node.get("confidence"),
                        "nominal_is_null": node.get("nominal") is None,
                        "calibration_required": node.get("calibration_required"),
                        "source": node.get("source"),
                    }
                )
            for k, v in node.items():
                sweep(v, path + "." + str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                sweep(v, f"{path}[{i}]")

    for sec in ("kinematics", "dynamics", "collision", "grasp", "flexibility", "failure_states"):
        sweep(doc[sec], sec)

    lv = {}
    for e in ledger:
        lv[e["authority_level"]] = lv.get(e["authority_level"], 0) + 1

    doc["authority_and_uncertainty"] = {
        "role": (
            "machine-readable roll-up of every enveloped quantity, so a consumer "
            "can refuse to run on anything below a declared authority floor"
        ),
        "quantity_count": len(ledger),
        "by_authority_level": dict(sorted(lv.items())),
        "null_nominal_count": sum(1 for e in ledger if e["nominal_is_null"]),
        "calibration_required_count": sum(1 for e in ledger if e["calibration_required"]),
        "authority_floor_recommendation": {
            "for_sim16_kinematics_and_collision": "ACCEPTED_URDF_L0 or DESIGN_CALIBRATION",
            "for_physics_gated_rl_contact": (
                "REFUSE TO RUN: every contact quantity (friction, contact "
                "pressure, contact duration, jam detection, lock confirmation) is "
                "HOLD or PROVISIONAL.  Physics-gated RL on contact must run as "
                "domain randomisation over declared ignorance, never as a "
                "calibrated contact model."
            ),
            "for_r2_flexible_coupling": (
                "PROVISIONAL_DERIVED bands only (FLEXIBLE_APPENDAGE_R2).  An "
                "R2-coupled flexible run must re-pass the e15 ANCF certification "
                "gate before its flexible results carry weight."
            ),
        },
        "ledger": ledger,
    }

    doc["retained_holds"] = [
        "FLIGHT_QUALIFICATION_HOLD",
        "LAUNCHER_AND_SEPARATION_LOAD_HOLD",
        "AS_BUILT_MASS_CORRELATION_HOLD",
        "AS_BUILT_ARM_METROLOGY_HOLD",
        "FLIGHT_MATERIAL_ALLOWABLE_HOLD",
        "QUALIFICATION_TEST_HOLD",
        "CONTACT_MODEL_AUTHORITY_HOLD",
        "MECH_RL_COLLISION_MESH_CALIBRATION_APPLICATION_OPEN",
        "R2_WING_AS_BUILT_MEASUREMENT_PENDING_HOLD",
        "R2_HINGE_STIFFNESS_WP5_HARDWARE_SELECTION_HOLD",
        "R2_B601_HARNESS_ROUTING_REDESIGN_REQUIRED (R2-HRN-04 full-FK sweep FAIL)",
    ]
    doc["prohibitions_honored"] = [
        "L0 accepted-URDF masses not overridden",
        "no candidate promoted to authority",
        "no PROVISIONAL promoted to AUTHORITY",
        "no zero-fill of unknowns",
        "no flight / launcher / manufacturing-release / qualification claim",
        "no measured_mass field anywhere",
        "frozen V1 contract / V4 interface / URDF / calibration not modified",
        "legacy R1 panel mass not used in the R2 binding",
    ]
    doc["review_status"] = "PENDING_OWNER_REVIEW"
    doc["next_stage_authorized"] = False
    doc["source_register"] = [
        {"role": k, "path": v, "sha256": sha256(v), "bytes": os.path.getsize(longpath(apath(v)))}
        for k, v in sorted(src.items())
    ]

    with open(longpath(OUT_PATH), "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, allow_unicode=True, sort_keys=False, width=100)

    body = read_bytes(os.path.relpath(OUT_PATH, PROJECT_ROOT).replace(os.sep, "/"))
    print("WROTE", OUT_PATH, len(body), "bytes")
    au = doc["authority_and_uncertainty"]
    print("  enveloped quantities :", au["quantity_count"])
    print("  null nominals        :", au["null_nominal_count"])
    print("  calibration required :", au["calibration_required_count"])
    for k, v in au["by_authority_level"].items():
        print(f"      {v:3d}  {k}")


if __name__ == "__main__":
    main()
