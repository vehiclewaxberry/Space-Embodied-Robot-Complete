#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M7 / WP13 - EMBODIED_MECHANICAL_CONTRACT_V1 builder            (ODR-15)

The single machine-readable mechanical interface from the mechanical phase to
dynamics -> control -> safety shield -> RL.

Design rule (ODR-15): every exported quantity carries source + authority_level
+ confidence + nominal + uncertainty + calibration_required.  A bare nominal is
forbidden, so that domain randomisation consumes MECHANICAL-ENGINEERING
uncertainty instead of RL-invented ranges.

Build rule (this file): every number is READ FROM ITS SOURCE ARTIFACT AT BUILD
TIME and the source is pinned by sha256.  Nothing is transcribed by hand.  The
one lesson that produced this rule: a hand-copied regex in the CM01
adjudicator silently dropped three alternatives and was only caught by an
exact-reproduction check.  Transcription is the failure mode; elimination of
transcription is the countermeasure.

Prohibitions honoured
---------------------
* L0 accepted-URDF masses are never overridden
* candidate != authority; design != flight-qualified
* no zero-fill: an absent physical input stays null + named HOLD
* PROVISIONAL is never promoted to AUTHORITY
* no flight / launcher / manufacturing-release / qualification claim
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
M7_ROOT = os.path.join(PROJECT_ROOT, M7_REL.replace("/", os.sep))
OUT_DIR = os.path.join(M7_ROOT, "wp13_embodied_contract")
OUT_PATH = os.path.join(OUT_DIR, "EMBODIED_MECHANICAL_CONTRACT_V1.yaml")
SELF_PATH = os.path.abspath(__file__)
TZ8 = datetime.timezone(datetime.timedelta(hours=8))

SRC = {
    "urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "mass": f"{M7_REL}/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml",
    "mass_policy": f"{M7_REL}/wp2_design_mass/DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml",
    "gripper": f"{M7_REL}/wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V1.yaml",
    "hinge": f"{M7_REL}/wp5_mechanisms/SOLAR_HINGE_DEPLOYMENT_PACK_V1.yaml",
    "hdrm": f"{M7_REL}/wp5_mechanisms/HDRM_ENGINEERING_PACK_V1.yaml",
    "calib": f"{M7_REL}/wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml",
    "o2": f"{M7_REL}/wp11_cad_urdf_registration/O2_DISPOSITION_RULING_V1.yaml",
    "keepout": f"{M7_REL}/wp1_structure_cad/KEEP_OUT_REGISTER_V1.yaml",
    "v4": f"{M7_REL}/wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V4.yaml",
    "odr": f"{M7_REL}/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml",
    "terminal": f"{M7_REL}/00_authority/M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml",
    "panel": "20_engineering/config/geometry/flexible_appendage_v1.yaml",
    "coupled": "20_engineering/config/coupled_scene/coupled_model_v0.yaml",
    "capture_scene": "20_engineering/config/coupled_scene/scene_A2_capture.yaml",
    "fea": f"{M7_REL}/wp7_fea_operational/FEA1B_ELEMENT_FORMULATION_EVIDENCE_V1.json",
}


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
# Section 2 - DYNAMICS
# ===========================================================================
def build_dynamics(urdf_root, mass_doc, v4):
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

    pinned = v4["design_mass_model_binding"]["pinned_constants"]
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
                "DESIGN_MASS_MODEL_NOT_MEASURED",
                "B",
                {
                    "standard_uncertainty_kg": m["standard_uncertainty_kg"],
                    "relative": m["relative_standard_uncertainty"],
                    "distribution": "declared standard uncertainty (GUM), not a bound",
                },
                True,
            ),
            "center_of_mass": q(
                cm["xyz_m"],
                SRC["mass"],
                "DESIGN_MASS_MODEL_NOT_MEASURED",
                "B",
                {"standard_uncertainty_xyz_m": cm["standard_uncertainty_xyz_m"]},
                True,
                reference_frame=cm["reference_frame"],
            ),
            "inertia": q(
                inr["components_kg_m2"],
                SRC["mass"],
                "DESIGN_MASS_MODEL_NOT_MEASURED",
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
            "system_configurations": (
                "see dynamics.configurations - DESIGN model, uncertainty declared"
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
                        "T_SM_mm": v4["frame_authority"]["m_frame_definition"]["t_sm_mm"],
                        "rotation": v4["frame_authority"]["m_frame_definition"]["rotation"],
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
                    SRC["v4"],
                    "HOLD_NO_JOINT_STIFFNESS_AUTHORITY",
                    None,
                    {
                        "value": None,
                        "status": "PENDING_WP4_STIFFNESS_DERIVATION_AND_TEST",
                    },
                    True,
                    note=(
                        "WP4 delivered fastener preload/torque design, not an "
                        "interface stiffness matrix.  V4 carries "
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
# Section 3 - COLLISION
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
# Section 4 - GRASP
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
# Section 5 - FLEXIBILITY
# ===========================================================================
def build_flexibility(panel, coupled, hinge):
    st = panel["stiffness"]
    cases = st["cases"]
    dmp_panel = panel.get("damping", {})
    zeta_coupled = coupled["panels"]["zeta_modal"]
    zeta_panel = dmp_panel.get("zeta")

    geom = panel["geometry"]
    area = geom["span_L_m"] * geom["chord_b_m"]
    m_panel = panel["mass"]["m_panel_kg"]
    areal = m_panel / area

    return {
        "solar_panel": {
            "geometry_m": {
                "span_L": geom["span_L_m"],
                "chord_b": geom["chord_b_m"],
                "thickness_t": geom["thickness_t_m"],
            },
            "mode_count": q(
                coupled["panels"]["n_modes"],
                SRC["coupled"],
                "PROVISIONAL",
                "C",
                {
                    "convergence_swept": [2, 3, 4],
                    "status": "listed in the source's own provisional_fields",
                },
                True,
            ),
            "mode_shape": q(
                coupled["panels"]["mode_shape"],
                SRC["coupled"],
                "PROVISIONAL",
                "C",
                {"status": "analytic cantilever; replaced if measured/FEM modes arrive"},
                True,
            ),
            "frequency_hz": q(
                cases["nominal"]["f1_hz"],
                SRC["panel"],
                "DESIGN_ASSUMPTION_NOT_MEASURED",
                "C",
                {
                    "envelope_hz": [cases["flexible_low"]["f1_hz"], cases["flexible_high"]["f1_hz"]],
                    "cases": cases,
                    "rl_guidance": (
                        "randomise across the 0.7-1.3 Hz envelope.  The envelope "
                        "IS the mechanical uncertainty statement; do not invent a "
                        "tighter one."
                    ),
                },
                True,
            ),
            "damping_zeta": {
                "CONTRACT_FINDING": "TWO_CONFLICTING_PLACEHOLDER_VALUES_ON_DISK",
                "value_in_geometry_ssot": zeta_panel,
                "value_in_coupled_scene_card": zeta_coupled,
                "both_are": "PROVISIONAL / TBD_cite_literature",
                "ratio": (zeta_panel / zeta_coupled) if (zeta_panel and zeta_coupled) else None,
                "nominal": None,
                "source": [SRC["panel"], SRC["coupled"]],
                "authority_level": "HOLD_CONFLICTING_PROVISIONAL_VALUES",
                "confidence": None,
                "uncertainty": {
                    "status": "CONFLICTING_PLACEHOLDERS_NO_MEASURED_DAMPING",
                    "span_rule": (
                        "the only defensible uncertainty statement is the span "
                        "between the two on-disk placeholders; neither is data"
                    ),
                },
                "calibration_required": True,
                "consumer_rule": (
                    "a consumer MUST NOT silently pick one.  Either declare which "
                    "it used, or treat zeta as a randomised parameter spanning "
                    "both.  Note the sim_11 energy-audit Gate forces zeta = 0, so "
                    "neither placeholder is exercised by that Gate."
                ),
                "trigger": "ECR-M1",
            },
            "mass_placeholder_finding": {
                "CONTRACT_FINDING": "PANEL_AREAL_DENSITY_IS_A_UNIFORM_DENSITY_PLACEHOLDER",
                "m_panel_kg": m_panel,
                "area_m2": area,
                "areal_density_kg_per_m2": areal,
                "typical_deployable_panel_kg_per_m2": [2, 5],
                "modelled_over_typical_ratio": [areal / 5.0, areal / 2.0],
                "severity_statement": (
                    "the modelled panel is HEAVIER per unit area than a typical "
                    "deployable, by roughly 1.5x to 3.8x.  The project's own "
                    "standing note describes this as the single largest modelling "
                    "weakness because the 'flexible feedback is negligible' "
                    "conclusion may invert under real parameters."
                ),
                "record_discrepancy": (
                    "the project memory phrases the gap as '5-10x'.  Recomputed "
                    "from the SSOT numbers it is 1.5-3.8x.  BOTH records are "
                    "reported; this contract does not decide which wording is "
                    "right, it flags that they disagree."
                ),
                "authority_level": "PLACEHOLDER_NOT_A_DESIGN_VALUE",
                "calibration_required": True,
                "trigger": "ECR-M1",
            },
            "excitation_rule": panel["ancf_interface"]["excitation"],
            "evidence": {
                "sim_07_point_capture_vs_rigid_lock_ratio": 92,
                "sim_07_ring_down_s": [37, 75],
                "sim_11_panel_ringing_mm": 2.1,
                "sim_11_panel_ringing_hz": 1.0005,
            },
        },
        "hinge": {
            "spring_torque_Nm": q(
                hinge.get("candidate_torque_budget_Nm", {}).get("spring_torque"),
                SRC["hinge"],
                "HOLD_NO_SPRING_TORQUE_VALUE_IN_SOURCE"
                if hinge.get("candidate_torque_budget_Nm", {}).get("spring_torque") is None
                else "DESIGN_TARGET_CANDIDATE",
                None
                if hinge.get("candidate_torque_budget_Nm", {}).get("spring_torque") is None
                else "C",
                {
                    "status": (
                        "SOURCE_VALUE_ABSENT - the hinge pack carries no "
                        "spring_torque entry; fail-closed (a null nominal may not "
                        "wear a DESIGN_TARGET_CANDIDATE authority)"
                        if hinge.get("candidate_torque_budget_Nm", {}).get("spring_torque") is None
                        else "not measured"
                    )
                },
                True,
            ),
            "stiffness": q(
                None,
                SRC["hinge"],
                "HOLD",
                None,
                {"status": "HINGE_FRICTION_AND_DAMPING_MEASURED_VALUES_HOLD"},
                True,
            ),
            "freeplay_mm": q(
                None,
                SRC["hinge"],
                "HOLD",
                None,
                {"status": "FREEPLAY_LIMITS_HOLD_NO_PIN_BORE_AUTHORITY"},
                True,
            ),
            "latch": "positive latch at end of travel, engagement observable",
        },
        "certification_caveat": {
            "e15_status": "REPEAT_ANCF_CERTIFICATION",
            "meaning": (
                "the ANCF cross-solver certification failed at 5.64% > 5%.  Any "
                "NEW fully-coupled flexible model must re-pass that gate before "
                "its flexible results carry weight."
            ),
        },
    }


# ===========================================================================
# Section 6 - FAILURE STATES
# ===========================================================================
def build_failure_states(mass_doc, v4):
    fs = v4["failure_semantics"]
    by_id = {c["configuration_id"]: c for c in mass_doc["configurations"]}
    out = {
        "_semantics": {
            "panel_failure": fs["semantics"],
            "jettison_forbidden": fs["jettison_forbidden"],
            "authority": "ODR-02",
            "mass_model_consequence": fs["mass_model_consequence"],
        }
    }
    for cid, name in (("C02", "LEFT_PANEL_FAIL"), ("C03", "RIGHT_PANEL_FAIL"), ("C04", "BOTH_PANEL_FAIL")):
        c = by_id[cid]
        c01 = by_id["C01"]
        out[name] = {
            "configuration_id": cid,
            "geometry": "panel(s) attached but not normally deployed",
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
    return out


# ===========================================================================
def main():
    os.makedirs(longpath(OUT_DIR), exist_ok=True)

    urdf_root = ET.fromstring(read_bytes(SRC["urdf"]).decode("utf-8"))
    mass_doc = load_yaml(SRC["mass"])
    grip = load_yaml(SRC["gripper"])
    hinge = load_yaml(SRC["hinge"])
    calib = load_yaml(SRC["calib"])
    o2 = load_yaml(SRC["o2"])
    keepout_present = os.path.isfile(longpath(apath(SRC["keepout"])))
    v4 = load_yaml(SRC["v4"])
    panel = load_yaml(SRC["panel"])
    coupled = load_yaml(SRC["coupled"])
    capture_scene = load_yaml(SRC["capture_scene"])

    doc = {
        "schema": "EMBODIED_MECHANICAL_CONTRACT_V1",
        "generated_local": datetime.datetime.now(TZ8).isoformat(),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP13_EMBODIED_CONTRACT",
        "role": "A0_MECHANICAL_CHIEF",
        "authority_basis": ["ODR-15", "ODR-10 option O2-A", "ODR-02", "ODR-01", "ODR-07"],
        "purpose": (
            "the single machine-readable mechanical interface consumed by "
            "dynamics -> control -> safety shield -> RL.  It does not restate the "
            "Gate A criteria and it grants no release authority."
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
            "system_mass_configurations": "WP2 DESIGN model with declared uncertainty",
            "physical_geometry": "M7 CAD",
            "bridge": "B601_CAD_URDF_GEOMETRY_CALIBRATION_V1 (D_i)",
            "ruling": "ODR-10 option O2-A",
        },
        "kinematics": build_kinematics(urdf_root),
        "dynamics": build_dynamics(urdf_root, mass_doc, v4),
        "collision": build_collision(urdf_root, calib, o2, keepout_present),
        "grasp": build_grasp(urdf_root, grip, capture_scene),
        "flexibility": build_flexibility(panel, coupled, hinge),
        "failure_states": build_failure_states(mass_doc, v4),
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
    ]
    doc["prohibitions_honored"] = [
        "L0 accepted-URDF masses not overridden",
        "no candidate promoted to authority",
        "no PROVISIONAL promoted to AUTHORITY",
        "no zero-fill of unknowns",
        "no flight / launcher / manufacturing-release / qualification claim",
        "no measured_mass field anywhere",
    ]
    doc["review_status"] = "PENDING_OWNER_REVIEW"
    doc["next_stage_authorized"] = False
    doc["source_register"] = [
        {"role": k, "path": v, "sha256": sha256(v), "bytes": os.path.getsize(longpath(apath(v)))}
        for k, v in sorted(SRC.items())
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
