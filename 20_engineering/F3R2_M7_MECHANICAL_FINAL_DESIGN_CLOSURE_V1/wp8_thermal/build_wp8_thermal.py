#!/usr/bin/env python3
"""
M7 WP8_THERMAL builder — thermo-elastic delta-T sensitivity envelopes.

Pure analytic Python (stdlib + PyYAML). No CAD, no FEA, no thermal test,
no on-orbit measurement claim. All temperature bands are ASSUMPTION-level
candidates inherited from M6 WP4 material library ENV-ONORBIT-THERMAL-
SCREENING-V1 (environment authority HOLD). All CTE values are M6 library
candidates or explicitly flagged generic-reference assumptions; nothing
here is a flight allowable.

Outputs (this directory only):
  THERMO_ELASTIC_ENVELOPE_V1.csv
  THERMO_ELASTIC_SENSITIVITY_V1.yaml
  receipt.json
"""
import csv
import hashlib
import json
import math
import os
from datetime import datetime, timedelta, timezone

import yaml

ROOT = "F:/China Graduate Future Flight Vehicle Innovation Competition"
WP_DIR_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp8_thermal"
WP_DIR = os.path.join(ROOT, WP_DIR_REL)
TSPEC = {"timespec": "seconds"}
NOW = datetime.now(timezone(timedelta(hours=8))).isoformat(**TSPEC)
CLOCK = "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08"


def sha256_of(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def size_of(rel):
    return os.path.getsize(os.path.join(ROOT, rel))


# ---------------------------------------------------------------- inputs ----
SOURCE_FILES = [
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/README.md",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_EXECUTION_PLAN_V1.md",
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp4_materials/PROTOTYPE_MATERIAL_LIBRARY_V2.yaml",
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml",
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp3_tolerance/HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1.yaml",
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp3_tolerance/GRIPPER_CLEARANCE_SWEEP_VERDICT_V1.yaml",
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_ADAPTER_INTERFACE_SSOT.yaml",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml",
    "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/05_tolerance/gripper/GRIPPER_R1_RAIL_PALM_TOLERANCE_MODEL.yaml",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/08_camera_harness/F3R2_CAMERA_HARNESS_GRIPPER.json",
    "20_engineering/config/geometry/flexible_appendage_v1.yaml",
]

# CTE register (1/K). Status distinguishes M6-library candidates from
# generic-reference assumptions (library value null for the fastener alloys).
CTE = {
    "AL6061":  {"cte": 23.6e-6,  "status": "M6_LIBRARY_CANDIDATE_TYPICAL_MEAN_20_TO_100_DEGC"},
    "AL7075":  {"cte": 23.4e-6,  "status": "M6_LIBRARY_CANDIDATE_TYPICAL_MEAN_20_TO_100_DEGC"},
    "TI6AL4V": {"cte": 8.88e-6,  "status": "M6_LIBRARY_CANDIDATE_NASA_REFERENCE_SOURCE_INTERVAL_NULL"},
    "T700S_FIBER": {"cte": -0.38e-6, "status": "M6_LIBRARY_FIBER_REFERENCE_ONLY_NOT_A_LAMINATE_PROPERTY"},
    "A286":    {"cte": 16.5e-6,  "status": "GENERIC_ENGINEERING_REFERENCE_ASSUMPTION_LIBRARY_VALUE_NULL_UNVERIFIED"},
    "CRES304": {"cte": 17.3e-6,  "status": "GENERIC_ENGINEERING_REFERENCE_ASSUMPTION_LIBRARY_VALUE_NULL_UNVERIFIED"},
}

T_REF = 20.0  # assembly/reference temperature, ASSUMPTION (CTE source intervals start at 20 degC)

# Candidate temperature bands (M6 ENV-ONORBIT-THERMAL-SCREENING-V1; all ASSUMPTION, env authority HOLD)
BANDS = [
    {"band_id": "GEVS_TYP_MAX_PREDICTED_FLIGHT", "t_cold": -5.0,  "t_hot": 45.0,
     "flag": "ASSUMPTION_CANDIDATE_BAND_GEVS_TYPICAL"},
    {"band_id": "GEVS_TYP_OPERATIONAL",          "t_cold": -10.0, "t_hot": 50.0,
     "flag": "ASSUMPTION_CANDIDATE_BAND_GEVS_TYPICAL"},
    {"band_id": "GEVS_TYP_ACCEPTANCE_TEST",      "t_cold": -15.0, "t_hot": 55.0,
     "flag": "ASSUMPTION_CANDIDATE_BAND_GEVS_TYPICAL"},
    {"band_id": "GEVS_TYP_PROTOFLIGHT_TEST",     "t_cold": -20.0, "t_hot": 60.0,
     "flag": "ASSUMPTION_CANDIDATE_BAND_GEVS_TYPICAL"},
    {"band_id": "MIL_STD_1540_REFERENCE_PROTOQUALIFICATION_TEST", "t_cold": -29.0, "t_hot": 66.0,
     "flag": "ASSUMPTION_REFERENCE_BAND_MIL_STD_1540_BEYOND_GEVS"},
    {"band_id": "MIL_STD_1540_REFERENCE_QUALIFICATION_TEST",      "t_cold": -34.0, "t_hot": 71.0,
     "flag": "ASSUMPTION_REFERENCE_BAND_MIL_STD_1540_BEYOND_GEVS"},
]

# Contract / baseline geometry (mm)
R_PATTERN = 90.509642 / 2.0          # M3R 64x64 mm square pattern radius = PCD/2 (M7 exec plan contract)
D_HOLE = 4.6                          # Stage A clearance hole (M3R SSOT candidate)
D_BOLT = 4.0                          # M4 major diameter proxy (M6 WP3 candidate)
L_GRIP = 8.0                          # Stage A ring total thickness at bolt circle (M3R SSOT candidate)
PITCH = 0.7                           # M4x0.7 candidate thread
E_BOLT = 200000.0                     # MPa, GENERIC_REFERENCE_ASSUMPTION (library null for A286/CRES)
E_AL6061 = 68300.0                    # MPa, M6 library candidate TYPICAL_AT_20_DEGC
L_STROKE = 71.5                       # gripper R1 stroke contract (M7 exec plan)
CAM_LEVER = math.sqrt(46.0**2 + 58.0**2)  # camera optical frame offset from link6 [0,-46,58] proposed mount
CAM_ENVELOPE = [40.0, 34.0, 26.0]     # proposed bracket envelope mm
PANEL_SPAN = 200.0                    # solar panel span contract (flexible_appendage_v1 frozen)

# M6 WP3 candidate margin references (candidate class, not requirements)
REF_M3R_PATTERN_WC = 0.101015357      # B601_M4_PATTERN_ALIGNMENT worst-case min radial clearance mm
REF_RAIL_GAP_GRID_MIN = 0.05          # M4 owner example sensitivity grid min mm (NOT a requirement)
REF_HINGE_TIP_WC = 1.7453071          # hinge tip lateral WC mm (different DOF, context only)

# Derived fastener quantities (ISO 898-1 tensile stress area formula, analytic)
A_STRESS = math.pi / 4.0 * (D_BOLT - 0.9382 * PITCH) ** 2   # mm^2
K_BOLT = A_STRESS * E_BOLT / L_GRIP                          # N/mm
# Shigley frustum member stiffness, same-material (Al 6061) grip
_num = 0.5774 * math.pi * E_AL6061 * D_BOLT
_den = 2.0 * math.log(5.0 * (0.5774 * L_GRIP + 0.5 * D_BOLT) / (0.5774 * L_GRIP + 2.5 * D_BOLT))
K_MEMBER = _num / _den                                             # N/mm
K_EQ = K_BOLT * K_MEMBER / (K_BOLT + K_MEMBER)                     # N/mm
A286_PROOF_REF_N = 655.0 * A_STRESS  # M6 library public-distributor min proof reference x A_s (sanity bound only)

AUTH = "ANALYTIC_DESIGN_ASSUMPTION_LEVEL"


def margin_class(ratio):
    if ratio is None:
        return None
    a = abs(ratio)
    if a < 0.10:
        return "LOW_CONSUMES_LT_10PCT"
    if a < 0.50:
        return "MODERATE_CONSUMES_10_TO_50PCT"
    if a <= 1.0:
        return "HIGH_CONSUMES_50_TO_100PCT"
    return "EXCEEDS_REFERENCE"


ROWS = []


def emit(case_class, band, dT, interface, metric, scenario, value, unit,
         value_kind, margin_ref_id, margin_ref_val, margin_ratio, margin_impact, notes):
    ROWS.append({
        "row_id": "WP8-%04d" % (len(ROWS) + 1),
        "case_class": case_class,
        "band_id": band["band_id"] if band else "GRADIENT_ASSUMPTION_GRID",
        "band_flag": band["flag"] if band else "ASSUMPTION_THROUGH_SECTION_GRADIENT_GRID_NOT_AN_ENVIRONMENT_BAND",
        "t_hot_degC": band["t_hot"] if band else "",
        "t_cold_degC": band["t_cold"] if band else "",
        "delta_T_K": "" if dT is None else "%.6g" % dT,
        "interface": interface,
        "metric": metric,
        "material_scenario": scenario,
        "value": "%.12g" % value,
        "unit": unit,
        "value_kind": value_kind,
        "margin_reference_id": margin_ref_id or "",
        "margin_reference_value": "" if margin_ref_val is None else "%.12g" % margin_ref_val,
        "margin_consumption_ratio": "" if margin_ratio is None else "%.6g" % margin_ratio,
        "margin_impact": margin_impact,
        "authority_level": AUTH,
        "notes": notes,
    })


COLD_NOTE = ("Constant-CTE analytic model; cold side extrapolates Al CTE candidates below their 20-100 degC "
             "source interval and uses null-interval Ti/fastener values -- ASSUMPTION, not environment authority.")
HOT_NOTE = "Constant-CTE analytic model inside/near source interval; candidate CTEs, not allowables."
SWING_NOTE = ("Hot-to-cold end-state excursion (T_hot-T_cold); linear model makes the swing reference-temperature "
              "independent. " + COLD_NOTE)


def case_iter():
    for band in BANDS:
        yield "HOT", band, band["t_hot"] - T_REF, HOT_NOTE
        yield "COLD", band, band["t_cold"] - T_REF, COLD_NOTE
        yield "HOT_TO_COLD", band, band["t_hot"] - band["t_cold"], SWING_NOTE


def banded_metric(interface, metric, scenario, per_K, unit, value_kind,
                  margin_ref_id=None, margin_ref_val=None, margin_mode="ratio",
                  margin_prefix=None, extra_note=""):
    """Emit HOT/COLD/HOT_TO_COLD rows for a linear per-K coefficient."""
    for case_class, band, dT, note in case_iter():
        value = per_K * dT
        ratio, impact = None, "NOT_ASSESSED"
        if margin_ref_val and margin_mode == "context_only":
            ratio = value / margin_ref_val
            impact = "INFORMATIONAL_DIFFERENT_DOF_NO_ALLOCATED_LIMIT"
        elif margin_ref_val:
            ratio = value / margin_ref_val
            impact = "%s_%s" % (margin_class(ratio), margin_prefix)
        elif margin_mode == "pending_wp4":
            impact = "NOT_ASSESSABLE_PRELOAD_AUTHORITY_PENDING_WP4_SIBLING"
        elif margin_mode == "pending_pin":
            impact = "NOT_ASSESSABLE_HINGE_PIN_NOMINAL_HOLD_WP5_SIBLING"
        elif margin_mode == "no_requirement":
            impact = "NOT_ASSESSABLE_NO_POINTING_REQUIREMENT_AUTHORITY"
        elif margin_mode == "context_only":
            impact = "INFORMATIONAL_DIFFERENT_DOF_NO_ALLOCATED_LIMIT"
        emit(case_class, band, dT, interface, metric, scenario, value, unit,
             value_kind, margin_ref_id, margin_ref_val, ratio, impact,
             (note + " " + extra_note).strip())


# ------------------------------------------------- 1) M3R preload drift ----
# dF = (alpha_member - alpha_bolt) * dT * L_grip * k_eq ; members = Al 6061 Stage A ring.
# dT>0 with alpha_al > alpha_bolt -> preload INCREASE; dT<0 -> preload DECREASE (loss risk).
PRELOAD_SCEN = [
    ("BOLT_A286__MEMBER_AL6061", CTE["AL6061"]["cte"] - CTE["A286"]["cte"]),
    ("BOLT_CRES304__MEMBER_AL6061", CTE["AL6061"]["cte"] - CTE["CRES304"]["cte"]),
    ("BOLT_PARAMETRIC_UNIT_MISMATCH_1E6_PER_K", 1.0e-6),
]
for scen, dalpha in PRELOAD_SCEN:
    per_K = dalpha * L_GRIP * K_EQ
    vk = ("ANALYTIC_DERIVED_BOLT_CTE_ASSUMPTION_MEMBER_CTE_CANDIDATE"
          if "PARAMETRIC" not in scen else
          "ANALYTIC_DERIVED_NORMALIZED_PER_UNIT_CTE_MISMATCH_FULLY_PARAMETRIC")
    banded_metric("M3R_B601_JOINT", "preload_drift_N", scen, per_K, "N", vk,
                  margin_ref_id=None, margin_ref_val=None, margin_mode="pending_wp4",
                  extra_note="Proof-load context: A286 min-proof reference %.1f N (public distributor x derived stress area); initial preload authority = WP4 TORQUE_PRELOAD_SCHEDULE_V1 (PENDING_SIBLING_HASH)." % A286_PROOF_REF_N)

# --------------------------------------- 2) M3R pattern radial drift -------
# d_r = (alpha_stageA - alpha_b601base) * dT * R_PATTERN ; B601 base material unknown (HOLD),
# swept over three declared assumptions incl. library-anchored Ti.
PATTERN_SCEN = [
    ("BASE_AL6061_ASSUMPTION", CTE["AL6061"]["cte"] - CTE["AL6061"]["cte"]),
    ("BASE_CRES304_ASSUMPTION", CTE["AL6061"]["cte"] - CTE["CRES304"]["cte"]),
    ("BASE_TI6AL4V_ASSUMPTION", CTE["AL6061"]["cte"] - CTE["TI6AL4V"]["cte"]),
]
for scen, dalpha in PATTERN_SCEN:
    per_K = dalpha * R_PATTERN
    vk = ("ANALYTIC_DERIVED_EQUAL_CTE_COMPUTED_ZERO_NOT_ZERO_FILL" if dalpha == 0.0
          else "ANALYTIC_DERIVED_B601_BASE_MATERIAL_ASSUMPTION_MEMBER_CTE_CANDIDATE")
    banded_metric("M3R_B601_JOINT", "pattern_radial_drift_mm", scen, per_K, "mm", vk,
                  margin_ref_id="M6_WP3_B601_M4_PATTERN_WC_MIN_RADIAL_CLEARANCE_CANDIDATE_MM",
                  margin_ref_val=REF_M3R_PATTERN_WC,
                  margin_prefix="OF_M6_WP3_WC_CANDIDATE",
                  extra_note="B601 base material unidentified -- integration action for WP9 ICD_V3_DRAFT.")

# ------------------------------------ 3) M3R hole-shaft radial clearance ---
# dC = (alpha_hole*D_hole - alpha_bolt*D_bolt) * dT / 2  (radial)
HOLE_SCEN = [
    ("BOLT_A286_IN_AL6061_STAGE_A", (CTE["AL6061"]["cte"] * D_HOLE - CTE["A286"]["cte"] * D_BOLT) / 2.0),
    ("BOLT_CRES304_IN_AL6061_STAGE_A", (CTE["AL6061"]["cte"] * D_HOLE - CTE["CRES304"]["cte"] * D_BOLT) / 2.0),
]
for scen, per_K in HOLE_SCEN:
    banded_metric("M3R_B601_JOINT", "hole_shaft_radial_clearance_change_mm", scen, per_K, "mm",
                  "ANALYTIC_DERIVED_BOLT_CTE_ASSUMPTION_MEMBER_CTE_CANDIDATE",
                  margin_ref_id="M6_WP3_B601_M4_PATTERN_WC_MIN_RADIAL_CLEARANCE_CANDIDATE_MM",
                  margin_ref_val=REF_M3R_PATTERN_WC,
                  margin_prefix="OF_M6_WP3_WC_CANDIDATE",
                  extra_note="Positive = clearance grows (hot); negative = clearance shrinks (cold).")

# ------------------------------------------- 4) gripper rail clearance -----
# Al rail pair. Along-stroke relative shift over 71.5 mm contract stroke;
# across-gap coefficient per mm of rail/slot width (width nominal null -> HOLD).
GRIP_SCEN = [
    ("RAIL_AL6061__CARRIAGE_AL6061_SAME_ALLOY", 0.0),
    ("RAIL_AL6061__CARRIAGE_AL7075_MIXED", CTE["AL7075"]["cte"] - CTE["AL6061"]["cte"]),
]
for scen, dalpha in GRIP_SCEN:
    vk = ("ANALYTIC_DERIVED_EQUAL_CTE_COMPUTED_ZERO_NOT_ZERO_FILL" if dalpha == 0.0
          else "ANALYTIC_DERIVED_BOTH_CTE_M6_LIBRARY_CANDIDATES")
    banded_metric("GRIPPER_R1_RAIL_PAIR", "along_stroke_relative_shift_mm", scen,
                  dalpha * L_STROKE, "mm", vk,
                  margin_ref_id="M4_OWNER_EXAMPLE_RAIL_GAP_GRID_MIN_MM_NOT_A_REQUIREMENT",
                  margin_ref_val=REF_RAIL_GAP_GRID_MIN,
                  margin_prefix="OF_M4_EXAMPLE_GRID_MIN",
                  extra_note="Fills M6 WP3 excluded term delta_thermal analytically at design level.")
    banded_metric("GRIPPER_R1_RAIL_PAIR", "across_gap_clearance_change_per_mm_width_mm_per_mm", scen,
                  dalpha, "mm/mm", vk,
                  margin_ref_id=None, margin_ref_val=None, margin_mode="pending_pin",
                  extra_note="Multiply by authorized rail width when WP5/WP3 close rail-slot nominals; rail width stays null (no zero-fill).")

# --------------------------------------------- 5) hinge clearance change ---
# dC_diametral = (alpha_bore_Al - alpha_pin) * dT * D_pin ; pin/bore nominals HOLD (M6 TC-009)
# -> diametral change PER MM of pin diameter only.
HINGE_SCEN = [
    ("PIN_A286__BORE_AL6061", CTE["AL6061"]["cte"] - CTE["A286"]["cte"]),
    ("PIN_CRES304__BORE_AL6061", CTE["AL6061"]["cte"] - CTE["CRES304"]["cte"]),
]
for scen, dalpha in HINGE_SCEN:
    banded_metric("SOLAR_HINGE_PIN_BORE", "diametral_clearance_change_per_mm_pin_diameter_mm_per_mm", scen,
                  dalpha, "mm/mm",
                  "ANALYTIC_DERIVED_PIN_CTE_ASSUMPTION_BORE_CTE_CANDIDATE",
                  margin_ref_id=None, margin_ref_val=None, margin_mode="pending_pin",
                  extra_note="Absolute clearance stays PENDING_HINGE_PIN_NOMINAL (M6 WP3 TC-009 HOLD; WP5 sibling).")

# ------------------------------------------ 6) camera bracket pointing -----
# Uniform dT: pure translation of optical frame = alpha*lever*dT; first-order rotation = 0
# for a symmetric bracket (computed, not zero-fill). Rotation is gradient-driven:
# theta = alpha * dT_grad * L / t.
banded_metric("CAMERA_BRACKET_LINK6", "optical_frame_translation_mm",
              "BRACKET_AL6061_PROPOSED_MOUNT_DEFINED_NOT_MODELLED",
              CTE["AL6061"]["cte"] * CAM_LEVER, "mm",
              "ANALYTIC_DERIVED_MEMBER_CTE_CANDIDATE_LEVER_FROM_PROPOSED_MOUNT_OFFSET",
              margin_ref_id=None, margin_ref_val=None, margin_mode="no_requirement",
              extra_note="Uniform-dT first-order angular drift = 0 for symmetric bracket (analytic); rotation is gradient-driven (see gradient rows). Lever arm 74.026 mm from proposed optical-frame offset [0,-46,58] mm.")
for t_sec in (26.0, 40.0):
    for dTg in (1.0, 2.0, 5.0, 10.0):
        theta = CTE["AL6061"]["cte"] * dTg * CAM_LEVER / t_sec
        emit("GRADIENT", None, dTg, "CAMERA_BRACKET_LINK6",
             "pointing_drift_under_through_section_gradient_rad",
             "BRACKET_AL6061_T_%.0fMM_SECTION" % t_sec, theta, "rad",
             "ANALYTIC_DERIVED_MEMBER_CTE_CANDIDATE_ASSUMED_GRADIENT",
             None, None, None,
             "NOT_ASSESSABLE_NO_POINTING_REQUIREMENT_AUTHORITY",
             "Cantilever gradient model theta = alpha*dT_grad*L/t, L=74.026 mm, t=%.0f mm, dT_grad=%.4g K ASSUMPTION. = %.6g mrad." % (t_sec, dTg, theta * 1e3))

# ------------------------------------------------- 7) wing tip displacement
# Free in-plane growth of 200 mm span relative to hinge root: u = alpha_lam * dT * L.
# Laminate CTE unknown (library rule: fiber value is NOT a laminate property) ->
# explicit ASSUMPTION grid plus the fiber-direction reference row.
WING_GRID = [
    ("LAMINATE_CTE_MINUS_0P38E-6_T700S_FIBER_REFERENCE_ONLY", CTE["T700S_FIBER"]["cte"],
     "ANALYTIC_DERIVED_FIBER_REFERENCE_NOT_A_LAMINATE_PROPERTY"),
    ("LAMINATE_CTE_0P0E-6_ASSUMPTION_GRID_POINT", 0.0,
     "ANALYTIC_ASSUMPTION_GRID_POINT_LAMINATE_CTE_UNKNOWN"),
    ("LAMINATE_CTE_1P0E-6_ASSUMPTION_GRID_POINT", 1.0e-6,
     "ANALYTIC_ASSUMPTION_GRID_POINT_LAMINATE_CTE_UNKNOWN"),
    ("LAMINATE_CTE_2P0E-6_ASSUMPTION_GRID_POINT", 2.0e-6,
     "ANALYTIC_ASSUMPTION_GRID_POINT_LAMINATE_CTE_UNKNOWN"),
    ("LAMINATE_CTE_3P0E-6_ASSUMPTION_GRID_POINT", 3.0e-6,
     "ANALYTIC_ASSUMPTION_GRID_POINT_LAMINATE_CTE_UNKNOWN"),
]
for scen, alpha_lam, vk in WING_GRID:
    banded_metric("SOLAR_PANEL_WING_TIP", "tip_in_plane_displacement_relative_to_hinge_root_mm",
                  scen, alpha_lam * PANEL_SPAN, "mm", vk,
                  margin_ref_id="M6_WP3_HINGE_TIP_WC_LATERAL_MM_DIFFERENT_DOF_CONTEXT",
                  margin_ref_val=REF_HINGE_TIP_WC,
                  margin_mode="context_only",
                  extra_note="Free expansion, no stress under uniform dT without constraint/gradient. Ratio vs M6 hinge tip WC is cross-DOF context only. Laminate CTE characterization = WP6/HOLD.")

# ------------------------------------------------------------------ CSV ----
csv_rel = WP_DIR_REL + "/THERMO_ELASTIC_ENVELOPE_V1.csv"
csv_path = os.path.join(WP_DIR, "THERMO_ELASTIC_ENVELOPE_V1.csv")
fields = list(ROWS[0].keys())
with open(csv_path, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    w.writerows(ROWS)

# ------------------------------------------------- envelope extremes -------
def extremes(interface, metric):
    vals = [(r["material_scenario"], r["case_class"], r["band_id"], float(r["value"]))
            for r in ROWS if r["interface"] == interface and r["metric"] == metric]
    if not vals:
        return None
    lo = min(vals, key=lambda t: t[3])
    hi = max(vals, key=lambda t: t[3])
    return {"min": {"scenario": lo[0], "case": lo[1], "band": lo[2], "value": lo[3]},
            "max": {"scenario": hi[0], "case": hi[1], "band": hi[2], "value": hi[3]}}

ENVELOPE = {
    "m3r_preload_drift_N": extremes("M3R_B601_JOINT", "preload_drift_N"),
    "m3r_pattern_radial_drift_mm": extremes("M3R_B601_JOINT", "pattern_radial_drift_mm"),
    "m3r_hole_shaft_radial_clearance_change_mm": extremes("M3R_B601_JOINT", "hole_shaft_radial_clearance_change_mm"),
    "gripper_along_stroke_relative_shift_mm": extremes("GRIPPER_R1_RAIL_PAIR", "along_stroke_relative_shift_mm"),
    "hinge_diametral_clearance_per_mm_pin_mm_per_mm": extremes("SOLAR_HINGE_PIN_BORE", "diametral_clearance_change_per_mm_pin_diameter_mm_per_mm"),
    "camera_optical_frame_translation_mm": extremes("CAMERA_BRACKET_LINK6", "optical_frame_translation_mm"),
    "camera_pointing_gradient_rad": extremes("CAMERA_BRACKET_LINK6", "pointing_drift_under_through_section_gradient_rad"),
    "wing_tip_in_plane_displacement_mm": extremes("SOLAR_PANEL_WING_TIP", "tip_in_plane_displacement_relative_to_hinge_root_mm"),
}

# ------------------------------------------------------------------ YAML ---
doc = {
    "schema": "M7_WP8_THERMO_ELASTIC_SENSITIVITY_V1",
    "generated_local": NOW,
    "generated_clock_source": CLOCK,
    "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
    "work_package": "WP8_THERMAL",
    "classification": ("ANALYTIC_DESIGN_ASSUMPTION_LEVEL -- pure closed-form thermo-elastic sensitivity; "
                       "no thermal test, no on-orbit temperature measurement, no flight-qualification claim"),
    "authority_basis": {
        "owner_decisions": "00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml (ODR-01..06; none grants thermal environment authority)",
        "execution_plan": "00_authority/M7_EXECUTION_PLAN_V1.md (WP8 contract row; contract geometry quoted verbatim)",
        "gate_mapping": "Gate A operational modes (mechanism analytical + thermal) -> WP5+WP8; Gate B stays HOLD",
        "odr_scope_note": ("ODR-06 authorizes operational-load FEA only; it does not authorize thermal environments. "
                           "WP8 therefore runs at ANALYTIC_DESIGN level over ASSUMPTION candidate bands."),
    },
    "reference_temperature": {
        "t_ref_degC": T_REF,
        "basis": "ASSEMBLY_ROOM_TEMPERATURE_ASSUMPTION_CONSISTENT_WITH_AL_CTE_SOURCE_INTERVAL_LOWER_BOUND_20_DEGC",
        "hot_case": "delta_T = T_hot - T_ref (positive)",
        "cold_case": "delta_T = T_cold - T_ref (negative)",
        "hot_to_cold_case": "delta_T_span = T_hot - T_cold; linear model -> span is reference-temperature independent",
    },
    "temperature_bands": [
        dict(band, source="M6 WP4 ENV-ONORBIT-THERMAL-SCREENING-V1 candidate bands",
             environment_authority="HOLD_ASSUMPTION_ONLY_NO_ON_ORBIT_PREDICTION")
        for band in BANDS
    ],
    "cte_register": [
        {"material": k, "cte_per_K": v["cte"], "status": v["status"]} for k, v in CTE.items()
    ],
    "joint_stiffness_model": {
        "model": "Shigley frustum member stiffness + bolt spring, preload-free thermal increment dF = d_alpha*dT*L_grip*k_eq",
        "m4_stress_area_mm2": A_STRESS,
        "stress_area_basis": "ISO 898-1 analytic formula As = pi/4*(d-0.9382*p)^2, d=4.0, p=0.7 (derived, not measured)",
        "l_grip_mm": L_GRIP,
        "l_grip_basis": "M3R_ADAPTER_INTERFACE_SSOT stage_A_interface_ring.total_thickness_mm (CANDIDATE)",
        "e_bolt_MPa": E_BOLT, "e_bolt_basis": "GENERIC_REFERENCE_ASSUMPTION_LIBRARY_NULL",
        "e_member_MPa": E_AL6061, "e_member_basis": "M6 library candidate TYPICAL_AT_20_DEGC",
        "k_bolt_N_per_mm": K_BOLT, "k_member_N_per_mm": K_MEMBER, "k_eq_N_per_mm": K_EQ,
        "preload_drift_per_K_N": {
            "BOLT_A286__MEMBER_AL6061": (CTE["AL6061"]["cte"] - CTE["A286"]["cte"]) * L_GRIP * K_EQ,
            "BOLT_CRES304__MEMBER_AL6061": (CTE["AL6061"]["cte"] - CTE["CRES304"]["cte"]) * L_GRIP * K_EQ,
            "PER_UNIT_MISMATCH_1E6_PER_K": 1.0e-6 * L_GRIP * K_EQ,
        },
        "limitations": [
            "Single-frustum same-material analytic approximation; embedment, thread load distribution, plating not modelled",
            "Initial preload unknown until WP4 TORQUE_PRELOAD_SCHEDULE_V1 lands (PENDING_SIBLING_HASH)",
            "Sign convention: dT>0 with alpha_member>alpha_bolt -> preload INCREASE; dT<0 -> preload DECREASE",
        ],
    },
    "models": [
        {"interface": "M3R_B601_JOINT", "metric": "preload_drift_N",
         "equation": "dF = (alpha_Al6061 - alpha_bolt) * dT * L_grip * k_eq",
         "scenarios": [s for s, _ in PRELOAD_SCEN]},
        {"interface": "M3R_B601_JOINT", "metric": "pattern_radial_drift_mm",
         "equation": "d_r = (alpha_StageA - alpha_B601base) * dT * R_PATTERN, R_PATTERN = 45.254821 mm (PCD 90.509642/2)",
         "scenarios": [s for s, _ in PATTERN_SCEN],
         "note": "B601 base material unknown -> swept over Al/CRES/Ti declared assumptions"},
        {"interface": "M3R_B601_JOINT", "metric": "hole_shaft_radial_clearance_change_mm",
         "equation": "dC = (alpha_Al*D_hole - alpha_bolt*D_bolt) * dT / 2, D_hole=4.6, D_bolt=4.0",
         "scenarios": [s for s, _ in HOLE_SCEN]},
        {"interface": "GRIPPER_R1_RAIL_PAIR", "metric": "along_stroke_relative_shift_mm / across_gap_clearance_change_per_mm_width",
         "equation": "d_u = d_alpha * dT * L_stroke (71.5 mm contract); dC/W = d_alpha * dT per mm width",
         "scenarios": [s for s, _ in GRIP_SCEN],
         "note": "Fills M6 WP3 excluded term delta_thermal analytically; rail width nominal stays null (HOLD, no zero-fill)"},
        {"interface": "SOLAR_HINGE_PIN_BORE", "metric": "diametral_clearance_change_per_mm_pin_diameter",
         "equation": "dC_dia/D = (alpha_Al_bore - alpha_pin) * dT",
         "scenarios": [s for s, _ in HINGE_SCEN],
         "note": "Pin/bore nominals HOLD (M6 TC-009); absolute clearance = coefficient x authorized pin diameter (WP5)"},
        {"interface": "CAMERA_BRACKET_LINK6", "metric": "optical_frame_translation_mm + pointing_drift_under_gradient_rad",
         "equation": "translation = alpha*dT*L_lever (74.026 mm from proposed offset [0,-46,58]); theta = alpha*dT_grad*L/t",
         "note": "Uniform-dT first-order rotation = 0 for symmetric bracket (analytic result); gradient grid 1/2/5/10 K ASSUMPTION over t=26/40 mm sections"},
        {"interface": "SOLAR_PANEL_WING_TIP", "metric": "tip_in_plane_displacement_relative_to_hinge_root_mm",
         "equation": "u_tip = alpha_laminate * dT * L_span (200 mm contract)",
         "note": "Laminate CTE unknown (fiber -0.38e-6/K is fiber-only, not a laminate property) -> explicit ASSUMPTION grid {-0.38,0,1,2,3}e-6/K"},
    ],
    "envelope_extremes": ENVELOPE,
    "design_envelope_conclusions": {
        "level": "ANALYTIC_DESIGN -- functional retention statements over candidate bands; none is a flight or qualification claim",
        "conclusions": [
            {"interface": "M3R_B601_JOINT",
             "verdict": "FUNCTION_RETAINED_CONDITIONAL_ON_WP4_PRELOAD",
             "detail": ("Preload drift envelope +/-370..391 N (A286) / +/-327..346 N (CRES304) over the widest "
                        "qualification band ends (delta_T +51 / -54 K); hot-to-cold excursion 759 N (A286). "
                        "Drift is <7%% of the A286 public-distributor min-proof reference (%.0f N). Function is "
                        "retained at design level PROVIDED the WP4 torque-preload schedule sets initial preload "
                        "with cold-side residual > 0 plus margin (rule of thumb: initial preload >= 3x drift, "
                        "i.e. >= ~1.2 kN). No compensation hardware indicated; verification action sits with WP4/WP7." % A286_PROOF_REF_N)},
            {"interface": "M3R_B601_JOINT pattern alignment",
             "verdict": "FUNCTION_RETAINED_UNDER_AL_BASE__REQUIRES_CONFIRMATION_OF_B601_BASE_MATERIAL",
             "detail": ("Pattern radial drift is computed zero for an Al base (equal candidate CTEs), 30%% of the "
                        "M6 WP3 WC candidate clearance (0.101015 mm) for a CRES base, and up to 70%% (HIGH) for a "
                        "Ti-6Al-4V base on the 105 K qualification swing. Hole-shaft clearance change is <=1.1%% of "
                        "WC in all bands. Action: identify B601 base material (WP9 ICD_V3_DRAFT); if Ti/steel, "
                        "stay within the GEVS operational band or clock the pattern for the mid-temperature state.")},
            {"interface": "GRIPPER_R1_RAIL_PAIR",
             "verdict": "FUNCTION_RETAINED_ALL_BANDS_NO_COMPENSATION",
             "detail": ("Al/Al rail pair: along-stroke relative shift <=1.6e-3 mm even on the 105 K swing (mixed "
                        "6061/7075 worst case) = <=3%% of the M4 owner example grid minimum (0.05 mm, not a "
                        "requirement); same-alloy pair is computed zero. The M6 WP3 excluded term delta_thermal is "
                        "now analytically bounded at design level and is negligible against the candidate gap grid.")},
            {"interface": "SOLAR_HINGE_PIN_BORE",
             "verdict": "COEFFICIENT_CLOSED__ABSOLUTE_MARGIN_PENDING_HINGE_NOMINALS",
             "detail": ("Diametral clearance coefficient 7.1e-6/K (A286 pin) resp. 6.3e-6/K (CRES pin) per mm of "
                        "pin diameter; on the qualification swing this is 7.5e-4 resp. 6.6e-4 mm per mm diameter "
                        "(e.g. a 6 mm pin would see ~4.5e-3 mm). Absolute margin cannot close until WP5 fixes pin/"
                        "bore nominals (M6 TC-009 HOLD preserved; no zero-fill applied).")},
            {"interface": "CAMERA_BRACKET_LINK6",
             "verdict": "FUNCTION_RETAINED_FOR_POINTING_BUDGETS_ABOVE_ABOUT_1_MRAD__GRADIENT_CONTROL_IF_TIGHTER",
             "detail": ("Uniform-dT optical-frame translation <=0.089 mm (qualification hot end); first-order "
                        "angular drift under uniform dT is analytically zero for a symmetric bracket. Through-"
                        "section gradients drive pointing: 0.067 mrad/K for the thin (26 mm) section -- 0.34 mrad "
                        "at an assumed 5 K gradient, 0.67 mrad at 10 K. If a pointing requirement tighter than "
                        "~0.3 mrad emerges, apply gradient control (conduction path / isolation) or a thicker "
                        "bracket section; requirement authority does not exist yet (NOT_ASSESSABLE).")},
            {"interface": "SOLAR_PANEL_WING_TIP",
             "verdict": "FUNCTION_RETAINED_ALL_BANDS__LAMINATE_CTE_CHARACTERIZATION_STAYS_HOLD",
             "detail": ("In-plane tip growth <=0.063 mm over the 105 K qualification swing for laminate CTE up to "
                        "3e-6/K (assumption grid); two orders below the M6 WP3 hinge stop-driven tip WC (1.745 mm, "
                        "different DOF, context only). No compensation indicated. Laminate CTE characterization "
                        "remains WP6/HOLD; fiber value -0.38e-6/K used as reference row only, never as a laminate "
                        "property.")},
        ],
    },
    "retained_holds": [
        "HOLD_THERMAL_ENVIRONMENT_AUTHORITY (candidate bands are ASSUMPTION, no on-orbit prediction or test)",
        "HOLD_NO_THERMAL_VACUUM_TEST_OR_ON_ORBIT_TEMPERATURE_MEASUREMENT_CLAIM",
        "HOLD_BOLT_CTE_GENERIC_REFERENCE_ASSUMPTION (A286/CRES CTE null in M6 library; replace with controlled source before design freeze of preload numbers)",
        "HOLD_INITIAL_PRELOAD_AUTHORITY (WP4 TORQUE_PRELOAD_SCHEDULE_V1 sibling not landed)",
        "HOLD_HINGE_PIN_AND_BORE_NOMINALS (M6 TC-009; WP5 sibling)",
        "HOLD_GRIPPER_RAIL_WIDTH_NOMINAL (rail/slot width stays null; across-gap term reported per mm width)",
        "HOLD_CFRP_LAMINATE_CTE_UNKNOWN (assumption grid only; fiber reference never used as laminate property)",
        "HOLD_B601_BASE_MATERIAL_UNIDENTIFIED (pattern drift swept over declared assumptions)",
        "HOLD_CAMERA_REQUIREMENT_AUTHORITY_ABSENT (proposed mount DEFINED_NOT_MODELLED; no pointing budget)",
        "HOLD_LAUNCH_QUALIFICATION_THERMAL_OR_STRUCTURAL (ODR-06 scope; launcher ICD absent)",
        "HOLD_CTE_EXTRAPOLATION_BELOW_SOURCE_INTERVAL_ON_COLD_ROWS (constant-CTE analytic model flagged ASSUMPTION)",
    ],
    "sibling_interface_notes": [
        {"sibling": "wp3_tolerance_alloc/TOLERANCE_ALLOCATION_RESULTS_V1.yaml", "sha256": "PENDING_SIBLING_HASH",
         "note": "Per-K thermal coefficients herein are ready to enter M7 14-chain allocation thermal terms"},
        {"sibling": "wp4_fastener_design/TORQUE_PRELOAD_SCHEDULE_V1.csv", "sha256": "PENDING_SIBLING_HASH",
         "note": "WP8 preload drift (N/K per bolt scenario) must be stacked against WP4 initial preload; residual-preload check deferred to integration"},
        {"sibling": "wp5_mechanisms/HDRM_ENGINEERING_PACK_V1.yaml and SOLAR_HINGE_DEPLOYMENT_PACK_V1.yaml", "sha256": "PENDING_SIBLING_HASH",
         "note": "Hinge diametral coefficient (mm/mm-dia/K) awaits authorized pin diameter from WP5"},
        {"sibling": "wp7_fea_operational/FEA1_RESULTS_V1.csv", "sha256": "PENDING_SIBLING_HASH",
         "note": "ODR-06 operational FEA list contains no thermal load case; WP8 analytic envelopes are the design-level thermal evidence for Gate A"},
        {"sibling": "wp9_release_package/ICD_V3_DRAFT.yaml", "sha256": "PENDING_SIBLING_HASH",
         "note": "B601 base material identification and camera pointing budget are integration actions for the ICD draft"},
    ],
    "csv_companion": {
        "path": csv_rel,
        "sha256": sha256_of(csv_rel),
        "bytes": size_of(csv_rel),
        "row_count": len(ROWS),
    },
    "release_prohibitions": [
        "NO_FLIGHT_OR_LAUNCHER_OR_QUALIFICATION_CLAIM_FROM_THIS_ENVELOPE",
        "NO_THERMAL_TEST_OR_ON_ORBIT_TEMPERATURE_MEASUREMENT_CLAIM",
        "NO_ASSUMPTION_BAND_MAY_AUTHORIZE_ENVIRONMENT_CLOSURE",
        "NO_GENERIC_REFERENCE_FASTENER_CTE_MAY_BE_PROMOTED_TO_AUTHORITY",
        "NO_FIBER_CTE_MAY_BE_APPLIED_AS_A_LAMINATE_PROPERTY",
        "NO_ZERO_FILL_OF_UNKNOWN_NOMINALS (rail width, pin diameter, initial preload stay null/pending)",
        "DESIGN_LEVEL_RESULTS_ARE_NOT_FLIGHT_QUALIFIED",
    ],
    "source_register": {p: {"path": p, "sha256": sha256_of(p), "bytes": size_of(p)} for p in SOURCE_FILES},
}

yaml_rel = WP_DIR_REL + "/THERMO_ELASTIC_SENSITIVITY_V1.yaml"
with open(os.path.join(WP_DIR, "THERMO_ELASTIC_SENSITIVITY_V1.yaml"), "w", encoding="utf-8") as fh:
    yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True, width=140)

# --------------------------------------------------------------- receipt ---
receipt = {
    "schema": "M7_WP8_THERMAL_RECEIPT_V1",
    "generated_local": NOW,
    "generated_clock_source": CLOCK,
    "work_package": "WP8_THERMAL",
    "status": "WP8_COMPLETE_ANALYTIC_DESIGN_ASSUMPTION_LEVEL",
    "builder": {
        "path": WP_DIR_REL + "/build_wp8_thermal.py",
        "sha256": sha256_of(WP_DIR_REL + "/build_wp8_thermal.py"),
        "bytes": size_of(WP_DIR_REL + "/build_wp8_thermal.py"),
    },
    "produced_files": [
        {"path": yaml_rel, "sha256": sha256_of(yaml_rel), "bytes": size_of(yaml_rel)},
        {"path": csv_rel, "sha256": sha256_of(csv_rel), "bytes": size_of(csv_rel)},
    ],
    "numeric_summary": {
        "row_count_csv": len(ROWS),
        "bands": len(BANDS),
        "case_classes": ["HOT", "COLD", "HOT_TO_COLD", "GRADIENT"],
        "joint_stiffness": {
            "k_bolt_N_per_mm": K_BOLT, "k_member_N_per_mm": K_MEMBER, "k_eq_N_per_mm": K_EQ,
            "m4_stress_area_mm2": A_STRESS, "l_grip_mm": L_GRIP,
        },
        "preload_drift_per_K_N": doc["joint_stiffness_model"]["preload_drift_per_K_N"],
        "preload_drift_qualification_band_N": {
            "A286_hot_dT51": (CTE["AL6061"]["cte"] - CTE["A286"]["cte"]) * 8.0 * K_EQ * 51.0,
            "A286_cold_dT-54": (CTE["AL6061"]["cte"] - CTE["A286"]["cte"]) * 8.0 * K_EQ * -54.0,
            "CRES304_hot_dT51": (CTE["AL6061"]["cte"] - CTE["CRES304"]["cte"]) * 8.0 * K_EQ * 51.0,
            "CRES304_cold_dT-54": (CTE["AL6061"]["cte"] - CTE["CRES304"]["cte"]) * 8.0 * K_EQ * -54.0,
        },
        "pattern_drift_worst_mm": {
            "ti_base_qualification_swing_105K": (CTE["AL6061"]["cte"] - CTE["TI6AL4V"]["cte"]) * 105.0 * R_PATTERN,
            "ratio_of_m6_wp3_wc_candidate": (CTE["AL6061"]["cte"] - CTE["TI6AL4V"]["cte"]) * 105.0 * R_PATTERN / REF_M3R_PATTERN_WC,
        },
        "gripper_worst_along_stroke_mm_mixed_pair_swing_105K": (CTE["AL7075"]["cte"] - CTE["AL6061"]["cte"]) * 105.0 * L_STROKE,
        "camera_gradient_mrad_per_K_thin_section": CTE["AL6061"]["cte"] * CAM_LEVER / 26.0 * 1e3,
        "wing_tip_max_abs_mm_swing_105K_grid_3e-6": 3.0e-6 * 105.0 * PANEL_SPAN,
    },
    "retained_holds": doc["retained_holds"],
    "prohibitions_honored": {
        "formal_fea_run_count": 0,
        "freecad_launched": False,
        "abaqus_launched": False,
        "thermal_test_or_on_orbit_measurement_claimed": False,
        "zero_fill_of_unknowns": False,
        "baseline_files_modified": False,
        "candidate_promoted_to_authority": False,
        "l0_urdf_masses_touched": False,
        "heavy_memory_operation": False,
    },
    "source_register": doc["source_register"],
}
with open(os.path.join(WP_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
    json.dump(receipt, fh, indent=2, ensure_ascii=False)

print("WP8 build complete: %d CSV rows" % len(ROWS))
print("  k_bolt=%.1f k_member=%.1f k_eq=%.1f N/mm" % (K_BOLT, K_MEMBER, K_EQ))
print("  A_s(M4x0.7)=%.4f mm^2  A286 proof ref=%.1f N" % (A_STRESS, A286_PROOF_REF_N))
