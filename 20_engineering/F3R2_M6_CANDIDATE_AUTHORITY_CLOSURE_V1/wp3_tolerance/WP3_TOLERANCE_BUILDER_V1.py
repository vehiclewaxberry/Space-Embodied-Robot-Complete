# -*- coding: utf-8 -*-
"""WP3_TOLERANCE builder — numeric execution of the three M4 tolerance chains.

M6 candidate-authority work package. Pure Python analysis only: no FreeCAD, no
FEA, no RL. Every computed value is CANDIDATE / DERIVED_NEUTRAL_GEOMETRY_ONLY
class. Unknown measured/manufacturing inputs stay null with explicit HOLD and
are NEVER zero-filled into a stack; stacks that exclude null terms are marked
as partial. Reads baselines read-only; writes only inside wp3_tolerance/.

Fail-closed: every input file is SHA-256 verified against the pinned register
before any computation; a mismatch aborts the run.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WP_DIR = Path(__file__).resolve().parent
LOCAL_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
GENERATED_LOCAL = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
CLOCK_SOURCE = "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08"

# ---------------------------------------------------------------------------
# Input register (project-relative path -> pinned SHA-256).
# Pinned values cross-checked against M4/M6 authority files on 2026-08-21.
# ---------------------------------------------------------------------------
INPUTS = {
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/00_authority/M6_PHASE_AUTHORITY_AND_BOUNDARY.yaml":
        "EC0511522164404E5CFA323D3065E7FB33F6FB7140F60323DFDDDC3FA468B284",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/INTERFACE_STACKUP_B601_M3R_V1.yaml":
        "A5F95A9B11ACBF04E6ABEB2E850F5E18AD7CF8CAF18D70619DF7D04A1B09DA41",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/GRIPPER_FUNCTIONAL_TOLERANCE_MAP_V1.yaml":
        "8CD92F90346EE4481172939DF1BA182383411748D1E586DF0035EF9013A06A23",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/HINGE_DEPLOYMENT_TOLERANCE_CHAIN_V1.yaml":
        "6E17090392887ACFB8C3C31DF828E67252B27DF3092DB13E7E7892EA8BEE3858",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/TOLERANCE_CLOSURE_EXECUTION_PLAN_V1.yaml":
        "42253B264E16BD14F9366D5B2EE6C4E5BD4F44AD64F1BE480EC027D2A2AAD5EC",
    "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/05_tolerance/gripper/GRIPPER_R1_RAIL_PALM_TOLERANCE_MODEL.yaml":
        "14D1D928A101868BC5263ADDA2332005D69D260BDC922FC307F551A3E5199A65",
    "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/02_interfaces/B601_BASE_ADAPTER_REV_C_INTERFACE.yaml":
        "D63B867B3183434C054A8840735A2CDD9C5106D430CC76E44B0C840A11A522E9",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_ADAPTER_INTERFACE_SSOT.yaml":
        "591958F3A3BD06F5BD26B8218BFE145B4894031EC5005BC58C638B56D77F6E51",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml":
        "172F3603E458F670323925E644BC68623EE9C85FCA7AF1200FAE2576EB43C68B",
    "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/05_tolerance/system/SYSTEM_TOLERANCE_CHAIN_REGISTER_V1.csv":
        "B12EA035554BA830D88EA426C90F5B2A5A1AAA7BBFE0D6F88C99BD754AFE6C1F",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json":
        "7BC0DF784B36159624A8A89B67207C54C5C9C780B103CB38658DE2D6BA845F47",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/04_validation/GRIPPER_R1_CONTINUOUS_STROKE_SAMPLES.csv":
        "DAE4DBD5C2300D3CEC8602FDC9B12877614A2A8E28EFCD4A9D3F4F76A231382F",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/02_interfaces/SYSTEM_FRAME_TREE.yaml":
        "71A9FFFAA30A59BB5964949371FB0F9E5E1D61F94E99F38CEAD211AE89AF51CF",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/gripper_solids_DEPLOYED/GRIPPER_SOLID_MESHES.json":
        "C52124D1AF3C66BE3D597A1AAE3870568B591B8E5E0615A19A5EA58C82676251",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/08_camera_harness/F3R2_GRIPPER_SOLID_ASSIGNMENT.csv":
        "419F63149413E5EC5677357D95639CFACF68CE143964485EFB402F2A803B2C78",
    "20_engineering/config/geometry/flexible_appendage_v1.yaml":
        "52FA88084C628CE8845E05DE0C0A892BCA5347B7146C8D1C6B99093927153786",
    "20_engineering/config/geometry/service_spacecraft_v1.yaml":
        "8DD8F22FF1F893273DE2215EA12819E4D41CC0E20B853ADC0774052237881432",
}


def verify_inputs() -> dict[str, dict]:
    register = {}
    for rel, pinned in INPUTS.items():
        path = PROJECT_ROOT / rel
        if not path.is_file():
            raise SystemExit(f"FAIL-CLOSED: missing input {rel}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        if digest != pinned:
            raise SystemExit(f"FAIL-CLOSED: sha256 mismatch for {rel}: {digest} != {pinned}")
        register[rel] = {"path": rel, "sha256": digest, "bytes": path.stat().st_size}
    return register


# ---------------------------------------------------------------------------
# ISO 286-2 candidate limit data (standard table values, micrometres).
# Used ONLY as CANDIDATE_FIT assumptions on existing frozen nominal geometry.
# ---------------------------------------------------------------------------
IT6_UM = {(3, 6): 8, (6, 10): 9, (10, 18): 11, (18, 30): 13, (30, 50): 16,
          (50, 80): 19, (80, 120): 22, (120, 180): 25}
IT7_UM = {(3, 6): 12, (6, 10): 15, (10, 18): 18, (18, 30): 21, (30, 50): 25,
          (50, 80): 30, (80, 120): 35, (120, 180): 40}
G_ES_UM = {(3, 6): -4, (6, 10): -5, (10, 18): -6, (18, 30): -7, (30, 50): -9,
           (50, 80): -10, (80, 120): -12, (120, 180): -14}
M_EI_UM = {(3, 6): 4, (6, 10): 6, (10, 18): 7, (18, 30): 8, (30, 50): 9,
           (50, 80): 11, (80, 120): 13, (120, 180): 15}


def _band(d_nom_mm: float, table: dict) -> float:
    for (lo, hi), val in table.items():
        if lo < d_nom_mm <= hi:
            return float(val)
    raise ValueError(f"no ISO 286 band for diameter {d_nom_mm}")


def iso_hole_H7(d_nom_mm: float) -> tuple[float, float]:
    """Hole basis H7: EI=0, ES=+IT7 (returns lower, upper deviation in mm)."""
    return 0.0, _band(d_nom_mm, IT7_UM) / 1000.0


def iso_shaft_g6(d_nom_mm: float) -> tuple[float, float]:
    es = _band(d_nom_mm, G_ES_UM) / 1000.0
    return es - _band(d_nom_mm, IT6_UM) / 1000.0, es


def iso_shaft_h6(d_nom_mm: float) -> tuple[float, float]:
    return -_band(d_nom_mm, IT6_UM) / 1000.0, 0.0


def iso_shaft_m6(d_nom_mm: float) -> tuple[float, float]:
    ei = _band(d_nom_mm, M_EI_UM) / 1000.0
    return ei, ei + _band(d_nom_mm, IT6_UM) / 1000.0


def u_rect(half_width: float) -> float:
    """Standard uncertainty of a rectangular (uniform) tolerance contribution."""
    return half_width / math.sqrt(3.0)


def rss(*terms: float) -> float:
    return math.sqrt(sum(t * t for t in terms))


SQRT3 = math.sqrt(3.0)
ROUND = 9


def r9(x):
    return None if x is None else round(x, ROUND)


# ---------------------------------------------------------------------------
# (a) B601 -> Stage A -> Stage B -> spacecraft interface stackup execution.
# ---------------------------------------------------------------------------
def chain_c1_b601_pattern() -> dict:
    """B601_M4_PATTERN_ALIGNMENT — 4x M4 axes through Stage A holes."""
    d_hole_nom = 4.6
    d_hole = (d_hole_nom + iso_hole_H7(4.6)[0], d_hole_nom + iso_hole_H7(4.6)[1])
    d_screw_nom = 4.000
    d_screw = (d_screw_nom + iso_shaft_h6(4.0)[0], d_screw_nom + iso_shaft_h6(4.0)[1])
    c_size_min = (d_hole[0] - d_screw[1]) / 2.0
    c_size_max = (d_hole[1] - d_screw[0]) / 2.0

    pcd_meas = 90.509641772
    r_pattern = pcd_meas / 2.0
    clocking_tol_deg = 0.10
    e_clock = r_pattern * math.tan(math.radians(clocking_tol_deg))
    offsets = {
        "b601_axis_position_candidate_mm": 0.05,
        "stage_a_hole_position_candidate_mm": 0.05,
        "datum_shift_candidate_mm": 0.02,
        "clocking_arc_candidate_mm": e_clock,
    }
    e_wc = sum(offsets.values())
    c_min_wc = c_size_min - e_wc
    u_c = 0.5 * rss(u_rect((d_hole[1] - d_hole[0]) / 2.0),
                    u_rect((d_screw[1] - d_screw[0]) / 2.0))
    u_off = rss(u_rect(0.05), u_rect(0.05), u_rect(0.02), u_rect(e_clock))
    u_total = rss(u_c, u_off)
    c_mean = (c_size_min + c_size_max) / 2.0 - 0.0  # candidate means centred
    flatness = 0.05
    tilt_wc = flatness / 64.0
    tilt_u = u_rect(flatness) / 64.0
    return {
        "chain_id": "B601_M4_PATTERN_ALIGNMENT",
        "assembly_leg": "B601 -> M3R_STAGE_A",
        "candidate_fits": {
            "stage_a_clearance_hole_4p6": {
                "fit": "ISO286_H7", "limits_mm": list(d_hole),
                "classification": "CANDIDATE_FIT_ISO286_H7"},
            "m4_fastener_major_diameter_proxy": {
                "fit": "ISO286_h6_ON_4P000_MAJOR", "limits_mm": list(d_screw),
                "classification": "CANDIDATE_FIT_ISO286_H6_THREAD_MAJOR_PROXY"},
        },
        "candidate_process_terms": {
            "b601_axis_position_mm": {"half_width": 0.05, "classification": "CANDIDATE_PROCESS_CAPABILITY"},
            "stage_a_hole_position_mm": {"half_width": 0.05, "classification": "CANDIDATE_PROCESS_CAPABILITY"},
            "datum_shift_mm": {"half_width": 0.02, "classification": "CANDIDATE_PROCESS_CAPABILITY"},
            "clocking_tolerance_deg": {"half_width": clocking_tol_deg,
                                       "arc_at_measured_pcd_radius_mm": e_clock,
                                       "classification": "CANDIDATE_PROCESS_CAPABILITY"},
            "face_flatness_mm": {"value": flatness, "span_mm": 64.0,
                                 "classification": "CANDIDATE_PROCESS_CAPABILITY"},
        },
        "results": {
            "size_radial_clearance_min_mm": c_size_min,
            "size_radial_clearance_max_mm": c_size_max,
            "worst_case_hole_offset_mm": e_wc,
            "worst_case_minimum_radial_clearance_mm": c_min_wc,
            "worst_case_axis_misalignment_mm": e_wc,
            "rss_standard_uncertainty_mm": u_total,
            "rss_estimated_mean_clearance_mm": c_mean,
            "rss_k3_minimum_clearance_mm": c_mean - 3.0 * u_total,
            "mounting_tilt_worst_case_rad": tilt_wc,
            "mounting_tilt_rss_standard_uncertainty_rad": tilt_u,
        },
        "excluded_null_terms": ["thermal_stack", "fastener_bending", "surface_finish",
                                "measured_axis_CMM_report", "preload_effects"],
        "status": "CANDIDATE_STACK_EXECUTED_POSITIVE_CLEARANCE" if c_min_wc > 0 else "CANDIDATE_STACK_NEGATIVE",
        "physical_conformity": "HOLD_MEASURED_VALUES_AND_CMM_REPORT_REQUIRED",
    }


def chain_c2_spigot() -> dict:
    d_f_nom, d_m_nom = 100.0, 99.6
    d_f = (d_f_nom + iso_hole_H7(100.0)[0], d_f_nom + iso_hole_H7(100.0)[1])
    d_m = (d_m_nom + iso_shaft_g6(99.6)[0], d_m_nom + iso_shaft_g6(99.6)[1])
    c_dia_min, c_dia_max = d_f[0] - d_m[1], d_f[1] - d_m[0]
    coax = 0.05  # diametral zone candidate
    u_f = u_rect((d_f[1] - d_f[0]) / 2.0)
    u_m = u_rect((d_m[1] - d_m[0]) / 2.0)
    rho = 0.0  # CANDIDATE_UNCORRELATED
    u_c = 0.5 * math.sqrt(u_f ** 2 + u_m ** 2 - 2 * rho * u_f * u_m)
    return {
        "chain_id": "STAGE_A_STAGE_B_SPIGOT",
        "assembly_leg": "M3R_STAGE_A -> M3R_STAGE_B",
        "candidate_fits": {
            "stage_b_receiving_bore_100p0": {
                "fit": "ISO286_H7", "limits_mm": list(d_f),
                "classification": "CANDIDATE_FIT_ISO286_H7"},
            "stage_a_spigot_99p6": {
                "fit": "ISO286_g6", "limits_mm": list(d_m),
                "classification": "CANDIDATE_FIT_ISO286_G6"},
        },
        "candidate_process_terms": {
            "coaxiality_mm": {"diametral_zone": coax,
                              "classification": "CANDIDATE_PROCESS_CAPABILITY"},
            "correlation_coefficient": {"value": rho, "classification": "CANDIDATE_UNCORRELATED_ASSUMPTION"},
        },
        "results": {
            "worst_case_minimum_radial_clearance_mm": c_dia_min / 2.0,
            "worst_case_maximum_radial_clearance_mm": c_dia_max / 2.0,
            "coaxiality_consumed_minimum_radial_location_margin_mm": c_dia_min / 2.0 - coax / 2.0,
            "combined_standard_uncertainty_mm": u_c,
            "thermal_minimum_clearance_mm": None,
        },
        "excluded_null_terms": ["thermal_stack_no_approved_CTE_or_temperature_range",
                                "surface_finish", "measured_diameters"],
        "status": "CANDIDATE_STACK_EXECUTED_POSITIVE_CLEARANCE",
        "physical_conformity": "HOLD_MEASURED_VALUES_AND_CMM_REPORT_REQUIRED",
    }


def chain_c3_skirt() -> dict:
    d_f_nom, d_m_nom = 150.4, 150.0
    d_f = (d_f_nom + iso_hole_H7(150.4)[0], d_f_nom + iso_hole_H7(150.4)[1])
    d_m = (d_m_nom + iso_shaft_g6(150.0)[0], d_m_nom + iso_shaft_g6(150.0)[1])
    c_dia_min, c_dia_max = d_f[0] - d_m[1], d_f[1] - d_m[0]
    coax = 0.05
    u_f = u_rect((d_f[1] - d_f[0]) / 2.0)
    u_m = u_rect((d_m[1] - d_m[0]) / 2.0)
    u_c = 0.5 * rss(u_f, u_m)
    return {
        "chain_id": "STAGE_A_STAGE_B_ANNULAR_SKIRT",
        "assembly_leg": "M3R_STAGE_A -> M3R_STAGE_B",
        "candidate_fits": {
            "stage_b_pocket_outer_150p4": {
                "fit": "ISO286_H7", "limits_mm": list(d_f),
                "classification": "CANDIDATE_FIT_ISO286_H7"},
            "stage_a_skirt_outer_150p0": {
                "fit": "ISO286_g6", "limits_mm": list(d_m),
                "classification": "CANDIDATE_FIT_ISO286_G6"},
        },
        "candidate_process_terms": {
            "coaxiality_mm": {"diametral_zone": coax,
                              "classification": "CANDIDATE_PROCESS_CAPABILITY"},
        },
        "results": {
            "worst_case_minimum_radial_clearance_mm": c_dia_min / 2.0,
            "worst_case_maximum_radial_clearance_mm": c_dia_max / 2.0,
            "coaxiality_consumed_minimum_radial_location_margin_mm": c_dia_min / 2.0 - coax / 2.0,
            "combined_standard_uncertainty_mm": u_c,
            "thermal_minimum_clearance_mm": None,
        },
        "excluded_null_terms": ["thermal_stack_no_approved_CTE_or_temperature_range",
                                "surface_finish", "measured_diameters"],
        "status": "CANDIDATE_STACK_EXECUTED_POSITIVE_CLEARANCE",
        "physical_conformity": "HOLD_MEASURED_VALUES_AND_CMM_REPORT_REQUIRED",
    }


def chain_c4_axial_seat() -> dict:
    d_nom = 5.595
    depth_half = 0.05
    flat = 0.02   # each face
    par = 0.02    # parallelism expressed as mm across the annular face
    g_wc_max = (d_nom + depth_half) - (d_nom - depth_half) + 2 * flat + par
    g_wc_min = (d_nom - depth_half) - (d_nom + depth_half) - 2 * flat - par
    u_g = rss(u_rect(depth_half), u_rect(depth_half),
              u_rect(flat), u_rect(flat), u_rect(par))
    return {
        "chain_id": "STAGE_A_STAGE_B_AXIAL_SEAT",
        "assembly_leg": "M3R_STAGE_A -> M3R_STAGE_B",
        "candidate_process_terms": {
            "recess_depth_limits_mm": {"nominal": d_nom, "half_width": depth_half,
                                       "classification": "CANDIDATE_PROCESS_CAPABILITY"},
            "face_flatness_mm": {"value_each_face": flat,
                                 "classification": "CANDIDATE_PROCESS_CAPABILITY"},
            "parallelism_mm_across_face": {"value": par,
                                           "classification": "CANDIDATE_PROCESS_CAPABILITY"},
        },
        "results": {
            "minimum_seating_gap_mm": g_wc_min,
            "maximum_seating_gap_mm": g_wc_max,
            "combined_standard_uncertainty_mm": u_g,
            "interpretation": ("negative minimum = candidate axial interference (preload seat); "
                               "positive maximum = candidate residual gap"),
        },
        "excluded_null_terms": ["surface_finish", "preload_deflection_mm",
                                "measured_depths", "thermal_stack"],
        "status": "CANDIDATE_STACK_EXECUTED_BIPOLAR_GAP",
        "physical_conformity": "HOLD_MEASURED_VALUES_AND_CMM_REPORT_REQUIRED",
    }


def chain_c5_m5_clocking() -> dict:
    # 8x M5 transition pattern
    d_hole_nom = 5.5
    d_hole = (d_hole_nom + iso_hole_H7(5.5)[0], d_hole_nom + iso_hole_H7(5.5)[1])
    d_screw_nom = 5.000
    d_screw = (d_screw_nom + iso_shaft_h6(5.0)[0], d_screw_nom + iso_shaft_h6(5.0)[1])
    c_size_min = (d_hole[0] - d_screw[1]) / 2.0
    c_size_max = (d_hole[1] - d_screw[0]) / 2.0
    pos_half = 0.05  # each pattern, radial
    c_min_wc = c_size_min - 2 * pos_half
    u_c = 0.5 * rss(u_rect((d_hole[1] - d_hole[0]) / 2.0),
                    u_rect((d_screw[1] - d_screw[0]) / 2.0))
    u_total = rss(u_c, u_rect(pos_half), u_rect(pos_half))
    # clocking dowel: pin m6, Stage B blind hole 4.0 H7 (press candidate),
    # Stage A hole 4.1 H7 (slip candidate)
    d_pin = (4.0 + iso_shaft_m6(4.0)[0], 4.0 + iso_shaft_m6(4.0)[1])
    d_press = (4.0 + iso_hole_H7(4.0)[0], 4.0 + iso_hole_H7(4.0)[1])
    d_slip = (4.1 + iso_hole_H7(4.1)[0], 4.1 + iso_hole_H7(4.1)[1])
    press_min, press_max = d_press[0] - d_pin[1], d_press[1] - d_pin[0]
    slip_min, slip_max = d_slip[0] - d_pin[1], d_slip[1] - d_pin[0]
    r_dowel = 55.0
    hole_pos_half = 0.025  # each dowel hole, radial
    slop_wc = slip_max / 2.0 + 2 * hole_pos_half
    theta_wc = slop_wc / r_dowel
    u_slop = rss(0.5 * rss(u_rect((d_slip[1] - d_slip[0]) / 2.0),
                           u_rect((d_pin[1] - d_pin[0]) / 2.0)),
                 u_rect(hole_pos_half), u_rect(hole_pos_half))
    theta_u = u_slop / r_dowel
    return {
        "chain_id": "STAGE_A_STAGE_B_M5_AND_CLOCKING",
        "assembly_leg": "M3R_STAGE_A -> M3R_STAGE_B",
        "candidate_fits": {
            "stage_b_m5_clearance_hole_5p5": {
                "fit": "ISO286_H7", "limits_mm": list(d_hole),
                "classification": "CANDIDATE_FIT_ISO286_H7"},
            "m5_fastener_major_diameter_proxy": {
                "fit": "ISO286_h6_ON_5P000_MAJOR", "limits_mm": list(d_screw),
                "classification": "CANDIDATE_FIT_ISO286_H6_THREAD_MAJOR_PROXY"},
            "clocking_dowel_pin_4p0": {
                "fit": "ISO286_m6", "limits_mm": list(d_pin),
                "classification": "CANDIDATE_FIT_ISO286_M6_DOWEL_PIN"},
            "stage_b_blind_hole_4p0_press_seat": {
                "fit": "ISO286_H7", "limits_mm": list(d_press),
                "classification": "CANDIDATE_FIT_ISO286_H7"},
            "stage_a_dowel_clearance_4p1_slip_seat": {
                "fit": "ISO286_H7", "limits_mm": list(d_slip),
                "classification": "CANDIDATE_FIT_ISO286_H7"},
        },
        "candidate_process_terms": {
            "m5_pattern_position_mm_each_side": {"half_width": pos_half,
                                                 "classification": "CANDIDATE_PROCESS_CAPABILITY"},
            "dowel_hole_position_mm_each_side": {"half_width": hole_pos_half,
                                                 "classification": "CANDIDATE_PROCESS_CAPABILITY"},
        },
        "results": {
            "m5_size_radial_clearance_min_mm": c_size_min,
            "m5_size_radial_clearance_max_mm": c_size_max,
            "minimum_fastener_clearance_worst_case_mm": c_min_wc,
            "m5_rss_standard_uncertainty_mm": u_total,
            "m5_rss_k3_minimum_clearance_mm": c_size_min - 3.0 * u_total,
            "locator_press_seat_diametral_fit_min_mm": press_min,
            "locator_press_seat_diametral_fit_max_mm": press_max,
            "locator_slip_seat_diametral_clearance_min_mm": slip_min,
            "locator_slip_seat_diametral_clearance_max_mm": slip_max,
            "clocking_error_worst_case_rad": theta_wc,
            "clocking_error_rss_standard_uncertainty_rad": theta_u,
            "clocking_error_rss_k3_rad": 3.0 * theta_u,
        },
        "excluded_null_terms": ["fastener_preload_and_grade", "blind_hole_depth_tolerance",
                                "locator_part_real_profile", "measured_positions",
                                "thermal_stack"],
        "status": "CANDIDATE_STACK_EXECUTED_POSITIVE_CLEARANCE",
        "physical_conformity": "HOLD_MEASURED_VALUES_AND_CMM_REPORT_REQUIRED",
    }


def chain_c6_stage_b_spacecraft() -> dict:
    d_hole_nom = 6.6
    d_hole = (d_hole_nom + iso_hole_H7(6.6)[0], d_hole_nom + iso_hole_H7(6.6)[1])
    d_screw_nom = 6.000
    d_screw = (d_screw_nom + iso_shaft_h6(6.0)[0], d_screw_nom + iso_shaft_h6(6.0)[1])
    pos_half = 0.05
    lig_nom = 160.0 / 2.0 - 70.0 - d_hole_nom / 2.0
    lig_wc = 160.0 / 2.0 - 70.0 - d_hole[1] / 2.0 - pos_half
    lig_mean = 160.0 / 2.0 - 70.0 - (d_hole[0] + d_hole[1]) / 4.0
    u_lig = rss(0.5 * u_rect((d_hole[1] - d_hole[0]) / 2.0), u_rect(pos_half))
    flat = 0.05
    tilt_wc = flat / 140.0
    tilt_u = u_rect(flat) / 140.0
    return {
        "chain_id": "STAGE_B_SPACECRAFT_M6_PATTERN",
        "assembly_leg": "M3R_STAGE_B -> SPACECRAFT_LOAD_BRIDGE",
        "candidate_fits": {
            "stage_b_m6_clearance_hole_6p6": {
                "fit": "ISO286_H7", "limits_mm": list(d_hole),
                "classification": "CANDIDATE_FIT_ISO286_H7"},
            "m6_fastener_major_diameter_proxy": {
                "fit": "ISO286_h6_ON_6P000_MAJOR", "limits_mm": list(d_screw),
                "classification": "CANDIDATE_FIT_ISO286_H6_THREAD_MAJOR_PROXY"},
        },
        "candidate_process_terms": {
            "stage_b_hole_position_mm": {"half_width": pos_half,
                                         "classification": "CANDIDATE_PROCESS_CAPABILITY"},
            "stage_b_face_flatness_mm": {"value": flat, "span_mm": 140.0,
                                         "classification": "CANDIDATE_PROCESS_CAPABILITY"},
        },
        "results": {
            "nominal_net_hole_edge_ligament_mm": lig_nom,
            "worst_case_minimum_edge_ligament_stage_b_side_only_mm": lig_wc,
            "rss_mean_edge_ligament_mm": lig_mean,
            "rss_standard_uncertainty_edge_ligament_mm": u_lig,
            "rss_k3_minimum_edge_ligament_mm": lig_mean - 3.0 * u_lig,
            "mounting_tilt_stage_b_side_only_worst_case_rad": tilt_wc,
            "mounting_tilt_stage_b_side_only_rss_rad": tilt_u,
            "minimum_fastener_clearance_to_spacecraft_mm": None,
            "interface_mounting_tilt_rad": None,
        },
        "excluded_null_terms": ["spacecraft_mating_axis_coordinates_mm",
                                "spacecraft_hole_size_limits_mm",
                                "spacecraft_position_tolerance_mm",
                                "spacecraft_load_bridge_mating_datum_definition",
                                "physical_mating_datum_to_M_DYNAMICS_transform"],
        "status": "CANDIDATE_STAGE_B_SIDE_ONLY_EXECUTED_INTERFACE_HOLD",
        "physical_conformity": "HOLD_LIVE_SPACECRAFT_MATING_GEOMETRY_MISSING",
    }


# ---------------------------------------------------------------------------
# Output writers.
# ---------------------------------------------------------------------------
def write_yaml(path: Path, doc: dict) -> None:
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True,
                                   width=120), encoding="utf-8")


def deliverable_a(src_register: dict) -> list[dict]:
    chains = [chain_c1_b601_pattern(), chain_c2_spigot(), chain_c3_skirt(),
              chain_c4_axial_seat(), chain_c5_m5_clocking(), chain_c6_stage_b_spacecraft()]
    for ch in chains:
        for k, v in ch["results"].items():
            ch["results"][k] = r9(v) if isinstance(v, float) else v

    doc = {
        "schema": "INTERFACE_STACKUP_B601_M3R_EXECUTED_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": CLOCK_SOURCE,
        "phase": "M6_CANDIDATE_AUTHORITY_CLOSURE",
        "work_package": "WP3_TOLERANCE",
        "classification": "CANDIDATE_NUMERIC_EXECUTION_NOT_A_RELEASED_TOLERANCE_PASS",
        "executes": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/INTERFACE_STACKUP_B601_M3R_V1.yaml",
        "assembly_path": "B601 -> M3R_STAGE_A -> M3R_STAGE_B -> SPACECRAFT_LOAD_BRIDGE",
        "units": {"length": "mm", "angle": "rad"},
        "method": {
            "worst_case": "arithmetic limit stack over candidate ISO 286 fits and candidate process terms",
            "rss": "root-sum-square of rectangular standard uncertainties (u = half_width/sqrt(3)); k=3 bounds reported as candidate estimates only",
            "zero_fill": "FORBIDDEN_AND_NOT_USED: unknown measured/manufacturing terms are excluded and listed, never set to zero",
            "correlations": "CANDIDATE_UNCORRELATED_ASSUMPTION where required",
            "thermal": "NOT_EVALUATED_NO_APPROVED_CTE_OR_TEMPERATURE_RANGE (terms stay null/HOLD)",
        },
        "chains": chains,
        "closure_gate": {
            "chain_count": 6,
            "candidate_numeric_chains_executed": 6,
            "chains_with_positive_worst_case_clearance": sum(
                1 for c in chains if c["status"] == "CANDIDATE_STACK_EXECUTED_POSITIVE_CLEARANCE"),
            "accepted_chain_count": 0,
            "verdict": "CANDIDATE_EXECUTION_COMPLETE_INTERFACE_AUTHORITY_HOLD",
        },
        "release_prohibitions_carried": [
            "NO_FIT_OR_INTERFERENCE_FREE_CLAIM_FROM_CANDIDATE_CLEARANCE",
            "NO_DRAWING_RELEASE_UNTIL_LIMITS_DATUMS_AND_INSPECTION_METHODS_CLOSE",
            "NO_THERMAL_CLEARANCE_CLAIM_WITHOUT_APPROVED_CTE_AND_ENVIRONMENT",
            "NO_FASTENER_PRELOAD_OR_MARGIN_CLAIM",
        ],
        "source_register": src_register,
    }
    write_yaml(WP_DIR / "INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml", doc)

    # CSV — long table; every required item (hole offset, flatness, coaxiality,
    # mounting tilt) appears explicitly per chain.
    rows = []

    def add(chain, item, unit, nominal, basis, wc_min, wc_max, rss_mean, rss_u, k3_lo, k3_hi, status):
        rows.append({
            "chain_id": chain, "item": item, "unit": unit, "nominal": nominal,
            "candidate_basis": basis,
            "worst_case_min": r9(wc_min), "worst_case_max": r9(wc_max),
            "rss_mean": r9(rss_mean), "rss_standard_uncertainty": r9(rss_u),
            "rss_k3_lower": r9(k3_lo), "rss_k3_upper": r9(k3_hi),
            "status": status,
        })

    c1, c2, c3, c4, c5, c6 = chains
    R = c1["results"]
    add("B601_M4_PATTERN_ALIGNMENT", "hole_offset", "mm", 0.0,
        "CANDIDATE_PROCESS_CAPABILITY pos 0.05+0.05 datum 0.02 clocking arc",
        -R["worst_case_hole_offset_mm"], R["worst_case_hole_offset_mm"], 0.0,
        None, None, None, c1["status"])
    add("B601_M4_PATTERN_ALIGNMENT", "radial_clearance", "mm", 0.3,
        "CANDIDATE_FIT_ISO286_H7_HOLE + H6_THREAD_MAJOR_PROXY minus candidate offsets",
        R["worst_case_minimum_radial_clearance_mm"],
        R["size_radial_clearance_max_mm"] + R["worst_case_hole_offset_mm"],
        R["rss_estimated_mean_clearance_mm"], R["rss_standard_uncertainty_mm"],
        R["rss_k3_minimum_clearance_mm"], None, c1["status"])
    add("B601_M4_PATTERN_ALIGNMENT", "flatness", "mm", None,
        "CANDIDATE_PROCESS_CAPABILITY 0.05 over 64 mm span",
        0.0, 0.05, None, u_rect(0.05), None, None, "CANDIDATE_TERM")
    add("B601_M4_PATTERN_ALIGNMENT", "mounting_tilt", "rad", 0.0,
        "flatness candidate over 64 mm pattern span",
        -R["mounting_tilt_worst_case_rad"], R["mounting_tilt_worst_case_rad"],
        0.0, R["mounting_tilt_rss_standard_uncertainty_rad"],
        -3 * R["mounting_tilt_rss_standard_uncertainty_rad"],
        3 * R["mounting_tilt_rss_standard_uncertainty_rad"], c1["status"])

    for ch, name in ((c2, "SPIGOT"), (c3, "ANNULAR_SKIRT")):
        R = ch["results"]
        add(ch["chain_id"], "radial_clearance", "mm", 0.2,
            "CANDIDATE_FIT_ISO286_H7_G6",
            R["worst_case_minimum_radial_clearance_mm"],
            R["worst_case_maximum_radial_clearance_mm"],
            None, R["combined_standard_uncertainty_mm"], None, None, ch["status"])
        add(ch["chain_id"], "coaxiality", "mm", None,
            "CANDIDATE_PROCESS_CAPABILITY diametral zone 0.05; margin after consumption",
            R["coaxiality_consumed_minimum_radial_location_margin_mm"],
            None, None, u_rect(0.025), None, None, "CANDIDATE_TERM")

    R = c4["results"]
    add("STAGE_A_STAGE_B_AXIAL_SEAT", "axial_gap", "mm", 0.0,
        "CANDIDATE_PROCESS_CAPABILITY depth +/-0.05 flatness 0.02x2 parallelism 0.02",
        R["minimum_seating_gap_mm"], R["maximum_seating_gap_mm"],
        0.0, R["combined_standard_uncertainty_mm"],
        -3 * R["combined_standard_uncertainty_mm"],
        3 * R["combined_standard_uncertainty_mm"], c4["status"])
    add("STAGE_A_STAGE_B_AXIAL_SEAT", "flatness", "mm", None,
        "CANDIDATE_PROCESS_CAPABILITY 0.02 each face",
        -0.04, 0.04, 0.0, rss(u_rect(0.02), u_rect(0.02)), None, None, "CANDIDATE_TERM")

    R = c5["results"]
    add("STAGE_A_STAGE_B_M5_AND_CLOCKING", "hole_offset", "mm", 0.0,
        "CANDIDATE_PROCESS_CAPABILITY pattern position 0.05 radial each side",
        -0.1, 0.1, 0.0, rss(u_rect(0.05), u_rect(0.05)), None, None, "CANDIDATE_TERM")
    add("STAGE_A_STAGE_B_M5_AND_CLOCKING", "radial_clearance", "mm", 0.25,
        "CANDIDATE_FIT_ISO286_H7_HOLE + H6_THREAD_MAJOR_PROXY minus candidate position",
        R["minimum_fastener_clearance_worst_case_mm"],
        R["m5_size_radial_clearance_max_mm"] + 0.1,
        None, R["m5_rss_standard_uncertainty_mm"], R["m5_rss_k3_minimum_clearance_mm"],
        None, c5["status"])
    add("STAGE_A_STAGE_B_M5_AND_CLOCKING", "dowel_fit", "mm", None,
        "CANDIDATE_FIT_ISO286_M6_DOWEL_PIN press H7/4.0 slip H7/4.1",
        R["locator_press_seat_diametral_fit_min_mm"],
        R["locator_slip_seat_diametral_clearance_max_mm"],
        None, None, None, None, "CANDIDATE_PRESS_PLUS_SLIP_PAIR")
    add("STAGE_A_STAGE_B_M5_AND_CLOCKING", "clocking_angle", "rad", 0.0,
        "slip-seat slop + candidate hole position at r=55 mm",
        -R["clocking_error_worst_case_rad"], R["clocking_error_worst_case_rad"],
        0.0, R["clocking_error_rss_standard_uncertainty_rad"],
        -R["clocking_error_rss_k3_rad"], R["clocking_error_rss_k3_rad"], c5["status"])

    R = c6["results"]
    add("STAGE_B_SPACECRAFT_M6_PATTERN", "edge_ligament", "mm",
        R["nominal_net_hole_edge_ligament_mm"],
        "CANDIDATE_FIT_ISO286_H7_HOLE + CANDIDATE_PROCESS position 0.05; STAGE_B_SIDE_ONLY",
        R["worst_case_minimum_edge_ligament_stage_b_side_only_mm"], None,
        R["rss_mean_edge_ligament_mm"], R["rss_standard_uncertainty_edge_ligament_mm"],
        R["rss_k3_minimum_edge_ligament_mm"], None, c6["status"])
    add("STAGE_B_SPACECRAFT_M6_PATTERN", "flatness", "mm", None,
        "CANDIDATE_PROCESS_CAPABILITY 0.05 over 140 mm span; STAGE_B_SIDE_ONLY",
        0.0, 0.05, None, u_rect(0.05), None, None, "CANDIDATE_TERM")
    add("STAGE_B_SPACECRAFT_M6_PATTERN", "mounting_tilt", "rad", None,
        "STAGE_B_SIDE_ONLY candidate; interface tilt null HOLD",
        -R["mounting_tilt_stage_b_side_only_worst_case_rad"],
        R["mounting_tilt_stage_b_side_only_worst_case_rad"],
        0.0, R["mounting_tilt_stage_b_side_only_rss_rad"], None, None, c6["status"])
    add("STAGE_B_SPACECRAFT_M6_PATTERN", "hole_offset", "mm", None,
        "SPACECRAFT_MATING_SIDE_UNKNOWN",
        None, None, None, None, None, None,
        "HOLD_LIVE_SPACECRAFT_MATING_GEOMETRY_MISSING")

    csv_path = WP_DIR / "INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return chains


def deliverable_b(src_register: dict) -> dict:
    sample_csv = PROJECT_ROOT / ("20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/"
                                 "04_validation/GRIPPER_R1_CONTINUOUS_STROKE_SAMPLES.csv")
    strokes: list[float] = []
    with sample_csv.open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            overlap = float(row["rail_palm_positive_overlap_upper_bound_mm3"])
            if overlap > 0.0:
                raise SystemExit("FAIL-CLOSED: pinned neutral witness shows positive overlap")
            if row["analytic_pass"].strip().lower() != "true":
                raise SystemExit("FAIL-CLOSED: pinned neutral witness row not analytic_pass")
            strokes.append(float(row["travel_mm"]))
    if len(strokes) != 144 or abs(strokes[0]) > 1e-12 or abs(strokes[-1] - 71.5) > 1e-12:
        raise SystemExit("FAIL-CLOSED: pinned stroke domain is not 144 samples over 0..71.5 mm")
    step_ok = all(abs(strokes[i + 1] - strokes[i] - 0.5) < 1e-9 for i in range(len(strokes) - 1))
    if not step_ok:
        raise SystemExit("FAIL-CLOSED: pinned stroke step is not 0.5 mm")

    gaps = [0.05, 0.10, 0.15, 0.20]
    verdict_row = "PASS_NEUTRAL_GEOMETRY_ONLY"
    rows = []
    for gap in gaps:
        for s in strokes:
            margin = gap - 0.0  # neutral geometric consumption witnessed zero; no zero-fill of unknowns
            rows.append({"rail_gap_candidate_mm": f"{gap:.2f}",
                         "stroke_mm": f"{s:.6f}",
                         "neutral_overlap_upper_bound_mm3": "0.000000",
                         "margin_mm": f"{margin:.6f}",
                         "verdict": verdict_row if margin > 0 else "NONPOSITIVE_MARGIN"})
    csv_path = WP_DIR / "GRIPPER_CLEARANCE_SWEEP_V1.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    doc = {
        "schema": "GRIPPER_CLEARANCE_SWEEP_VERDICT_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": CLOCK_SOURCE,
        "phase": "M6_CANDIDATE_AUTHORITY_CLOSURE",
        "work_package": "WP3_TOLERANCE",
        "classification": "DERIVED_NEUTRAL_GEOMETRY_ONLY_CANDIDATE_PARAMETRIC_SENSITIVITY",
        "executes": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/GRIPPER_FUNCTIONAL_TOLERANCE_MAP_V1.yaml",
        "measurement_model": ("margin_mm = rail_gap_candidate - neutral_geometric_consumption(stroke); "
                              "neutral_geometric_consumption = pinned positive-overlap upper bound = 0.0 mm3 "
                              "at every one of the 144 samples"),
        "sweep_domain": {
            "rail_gap_candidates_mm": gaps,
            "gap_source": "M4 owner example sensitivity grid (M4_PHASE_RULING_EXAMPLE_NOT_A_RELEASED_REQUIREMENT)",
            "stroke_min_mm": 0.0,
            "stroke_max_mm": 71.5,
            "stroke_step_mm": 0.5,
            "sample_count": len(strokes),
            "row_count": len(rows),
        },
        "results": {
            "positive_row_count": len(rows),
            "nonpositive_row_count": 0,
            "minimum_margin_mm": 0.05,
            "minimum_margin_at": {"rail_gap_candidate_mm": 0.05, "stroke_mm": "ALL_144_SAMPLES"},
            "margin_uniformity": "margin equals the candidate rail gap at every sample because the pinned neutral witness consumption is zero",
        },
        "excluded_null_terms_hold": [
            "t_coating_left", "t_coating_right", "delta_slot_straightness",
            "delta_rail_straightness", "delta_parallelism", "delta_assembly",
            "delta_thermal", "delta_elastic", "delta_wear_debris", "guard_band",
            "standard_uncertainties", "correlations", "conformity_decision_rule",
        ],
        "verdict": "CANDIDATE_PARAMETRIC_SWEEP_POSITIVE_UNDER_NEUTRAL_GEOMETRY_ONLY_MANUFACTURING_CLEARANCE_HOLD",
        "release_prohibitions_carried": [
            "DO_NOT_TREAT_ZERO_DIGITAL_OVERLAP_AS_POSITIVE_MANUFACTURING_CLEARANCE",
            "DO_NOT_TREAT_THE_0P05_TO_0P20_MM_GRID_AS_A_DESIGN_REQUIREMENT",
            "DO_NOT_REPORT_A_CLEARANCE_PASS_UNTIL_ALL_TERMS_AND_UNCERTAINTIES_CLOSE",
        ],
        "source_register": src_register,
    }
    write_yaml(WP_DIR / "GRIPPER_CLEARANCE_SWEEP_VERDICT_V1.yaml", doc)
    return {"rows": len(rows), "min_margin_mm": 0.05}


def deliverable_c(src_register: dict) -> dict:
    L = 200.0  # panel span_L_m = 0.200 frozen (flexible_appendage_v1.yaml), mm
    stop_repeat_deg = 0.5  # CANDIDATE_ASSUMPTION stop-angle repeatability scenario
    dtheta_wc = math.radians(stop_repeat_deg)
    dtheta_u = u_rect(dtheta_wc)
    axis_map_half = 0.05  # B-rep probe mapping candidate, translational
    samples_deg = [0.1, 0.5, 1.0, 2.0]
    lever_arms = [0.0, 100.0, 200.0]

    sensitivity = {
        "angular_deviation_to_lateral_displacement_mm_per_rad": L,
        "angular_deviation_to_lateral_displacement_mm_per_mrad": L / 1000.0,
        "radial_freeplay_to_translation_gain": 1.0,
        "axial_freeplay_to_translation_gain": 1.0,
        "root_station_lateral_displacement_under_pure_rotation_mm": 0.0,
        "note": "U(y) = y*sin(dtheta) for rotation about the hinge axis; root y=0 is invariant",
    }
    table = []
    for deg in samples_deg:
        rad = math.radians(deg)
        for y in lever_arms:
            table.append({"delta_theta_deg": deg, "lever_arm_mm": y,
                          "lateral_displacement_mm": round(y * math.sin(rad), ROUND)})

    doc = {
        "schema": "HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": CLOCK_SOURCE,
        "phase": "M6_CANDIDATE_AUTHORITY_CLOSURE",
        "work_package": "WP3_TOLERANCE",
        "classification": "CANDIDATE_SENSITIVITY_ANALYSIS_DERIVED_GEOMETRY_ONLY",
        "executes": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/HINGE_DEPLOYMENT_TOLERANCE_CHAIN_V1.yaml",
        "units": {"length": "mm", "angle": "rad"},
        "nominal_geometry": {
            "panel_span_mm": {"value": L, "classification": "FROZEN_GEOMETRY_SSOT",
                              "source": "20_engineering/config/geometry/flexible_appendage_v1.yaml span_L_m=0.200"},
            "panel_chord_mm": {"value": 227.0, "classification": "FROZEN_GEOMETRY_SSOT"},
            "left_hinge_axis": {"point_xyz_mm": [-61.0, 143.15, 0.0], "axis_xyz": [1.0, 0.0, 0.0],
                                "classification": "B_REP_PROBE_MAPPING_NOT_MANUFACTURING_DATUM"},
            "right_hinge_axis": {"point_xyz_mm": [-61.0, -143.15, 0.0], "axis_xyz": [1.0, 0.0, 0.0],
                                 "classification": "B_REP_PROBE_MAPPING_NOT_MANUFACTURING_DATUM"},
            "symmetry": "LEFT_RIGHT_SYMMETRIC_IDENTICAL_SPAN_AND_SENSITIVITIES",
        },
        "candidate_scenario_terms": {
            "stop_angle_repeatability_deg": {"half_width": stop_repeat_deg,
                                             "classification": "CANDIDATE_ASSUMPTION_NOT_A_REQUIREMENT"},
            "axis_mapping_translation_mm": {"half_width": axis_map_half,
                                            "classification": "CANDIDATE_PROCESS_CAPABILITY"},
        },
        "executed_results": {
            "deployed_angle_deviation_worst_case_rad": round(dtheta_wc, ROUND),
            "deployed_angle_deviation_rss_standard_uncertainty_rad": round(dtheta_u, ROUND),
            "deployed_angle_deviation_rss_k3_rad": round(3.0 * dtheta_u, ROUND),
            "tip_lateral_displacement_worst_case_mm": round(L * math.sin(dtheta_wc), ROUND),
            "tip_lateral_displacement_rss_k3_mm": round(L * math.sin(3.0 * dtheta_u), ROUND),
            "panel_translation_candidate_mm": axis_map_half,
            "sensitivity_coefficients": sensitivity,
            "exact_sample_table": table,
        },
        "chains_not_executed": {
            "radial_fit_chain": {"status": "HOLD", "reason": "pin and bore nominals have no numeric authority (TC-009); all limits stay null"},
            "axial_stack_chain": {"status": "HOLD", "reason": "lug gap and bushing/spacer/washer/retainer thicknesses unknown; terms stay null"},
            "deployed_stop_angle_chain_full": {"status": "HOLD_PARTIAL_CANDIDATE_ONLY",
                                               "reason": "stop geometry, compliance, thermal, wear terms null; executed above is a single-term candidate sensitivity scenario, not the full stack"},
            "deployment_clearance_and_collision": {"status": "HOLD_NOT_EVALUATED"},
        },
        "excluded_null_terms_hold": [
            "hinge_pin_and_bore_limits", "axial_stack_terms", "stop_contact_geometry_mm",
            "stop_flatness_limit_mm", "hinge_axis_position_limit_mm",
            "compliance_rad_per_Nm", "authorized_stop_torque_Nm",
            "approved_temperature_range_degC", "approved_CTE_per_K", "standard_uncertainties",
        ],
        "verdict": "CANDIDATE_SENSITIVITY_EXECUTED_DEPLOYMENT_TOLERANCE_ACCEPTANCE_HOLD",
        "source_register": src_register,
    }
    write_yaml(WP_DIR / "HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1.yaml", doc)
    return {"tip_wc_mm": round(L * math.sin(dtheta_wc), ROUND),
            "sensitivity_mm_per_mrad": L / 1000.0}


def main() -> None:
    src_register = verify_inputs()
    chains_a = deliverable_a(src_register)
    summary_b = deliverable_b(src_register)
    summary_c = deliverable_c(src_register)
    by_id = {c["chain_id"]: c["results"] for c in chains_a}

    outputs = [
        "wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml",
        "wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.csv",
        "wp3_tolerance/GRIPPER_CLEARANCE_SWEEP_V1.csv",
        "wp3_tolerance/GRIPPER_CLEARANCE_SWEEP_VERDICT_V1.yaml",
        "wp3_tolerance/HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1.yaml",
    ]
    m6_root = "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1"
    files = []
    for rel in outputs:
        path = PROJECT_ROOT / m6_root / rel
        files.append({"path": f"{m6_root}/{rel}",
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                      "bytes": path.stat().st_size})
    self_path = Path(__file__).resolve()
    builder_rel = f"{m6_root}/wp3_tolerance/WP3_TOLERANCE_BUILDER_V1.py"

    receipt = {
        "schema": "M6_WP3_TOLERANCE_RECEIPT_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": CLOCK_SOURCE,
        "work_package": "WP3_TOLERANCE",
        "status": "WP3_COMPLETE_CANDIDATE_CLASS_ONLY",
        "builder": {"path": builder_rel,
                    "sha256": hashlib.sha256(self_path.read_bytes()).hexdigest().upper(),
                    "bytes": self_path.stat().st_size},
        "produced_files": files,
        "source_register": src_register,
        "numeric_summary": {
            "interface_stackup": {
                "chains_executed": [c["chain_id"] for c in chains_a],
                "b601_m4_pattern_worst_case_min_radial_clearance_mm":
                    by_id["B601_M4_PATTERN_ALIGNMENT"]["worst_case_minimum_radial_clearance_mm"],
                "spigot_worst_case_min_radial_clearance_mm":
                    by_id["STAGE_A_STAGE_B_SPIGOT"]["worst_case_minimum_radial_clearance_mm"],
                "skirt_worst_case_min_radial_clearance_mm":
                    by_id["STAGE_A_STAGE_B_ANNULAR_SKIRT"]["worst_case_minimum_radial_clearance_mm"],
                "axial_seat_gap_range_mm": [
                    by_id["STAGE_A_STAGE_B_AXIAL_SEAT"]["minimum_seating_gap_mm"],
                    by_id["STAGE_A_STAGE_B_AXIAL_SEAT"]["maximum_seating_gap_mm"]],
                "m5_pattern_worst_case_min_radial_clearance_mm":
                    by_id["STAGE_A_STAGE_B_M5_AND_CLOCKING"]["minimum_fastener_clearance_worst_case_mm"],
                "clocking_error_worst_case_rad":
                    by_id["STAGE_A_STAGE_B_M5_AND_CLOCKING"]["clocking_error_worst_case_rad"],
                "stage_b_ligament_worst_case_mm":
                    by_id["STAGE_B_SPACECRAFT_M6_PATTERN"]["worst_case_minimum_edge_ligament_stage_b_side_only_mm"],
            },
            "gripper_sweep": summary_b,
            "hinge_sensitivity": summary_c,
        },
        "retained_holds": [
            "HOLD_ALL_MEASURED_CONFORMITY_AND_CMM_EVIDENCE",
            "HOLD_THERMAL_STACKS_NO_APPROVED_CTE_OR_TEMPERATURE_RANGE",
            "HOLD_STAGE_B_TO_SPACECRAFT_LIVE_MATING_GEOMETRY",
            "HOLD_GRIPPER_MANUFACTURING_CLEARANCE_ALL_CONSUMPTION_TERMS",
            "HOLD_HINGE_HARDWARE_NOMINALS_FITS_AND_STOP_GEOMETRY",
            "HOLD_FASTENER_PRELOAD_GRADE_AND_MOS",
            "HOLD_CDR_Q0_Q1_Q2_AND_STRUCTURAL_ENTRY_UNCHANGED",
        ],
        "prohibitions_honored": {
            "formal_fea_run_count": 0,
            "freecad_launched": False,
            "zero_fill_of_unknowns": False,
            "baseline_files_modified": False,
            "candidate_promoted_to_authority": False,
        },
    }
    (WP_DIR / "receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print("WP3 builder complete:")
    for f in files:
        print(f"  {f['path']}  {f['bytes']} B  {f['sha256'][:16]}...")


if __name__ == "__main__":
    sys.exit(main())
