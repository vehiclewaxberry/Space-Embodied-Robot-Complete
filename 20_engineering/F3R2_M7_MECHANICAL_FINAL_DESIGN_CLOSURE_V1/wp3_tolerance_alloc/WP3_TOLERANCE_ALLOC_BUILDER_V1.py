# -*- coding: utf-8 -*-
"""WP3_TOLERANCE_ALLOC builder — 14-chain reverse tolerance allocation (M7).

M7 final-design-closure work package. Pure Python analysis only: no FreeCAD,
no Abaqus, no FEA, no RL. Reverse allocation: from each chain's functional
margin back to per-feature allowed tolerances. WC must satisfy the function;
RSS k=3 is reported as reference. ISO 286 fit grades are labelled
CANDIDATE_FIT; process-capability values PROCESS_CAP_ASSUMED; requirements
created by this WP are DESIGN_ALLOCATED_REQUIREMENT (design-level authority
under the M7 owner directive, NOT flight/mission authority).

Fail-closed: every input file is SHA-256 verified against the pinned register
before any computation; a mismatch aborts the run. Baselines are read-only;
writes only inside wp3_tolerance_alloc/. Unknown measured/manufacturing terms
are excluded and listed, never zero-filled. Chains without any numeric
authority are recorded FUNCTIONALLY_OPEN with reasons, never hard-closed.
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
M7_ROOT = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"

# ---------------------------------------------------------------------------
# Input register (project-relative path -> pinned SHA-256).
# M4/M5/M6 pins cross-checked against the M6 wp3 receipt register on
# 2026-08-22; M7/M6 additions hashed at build-prep time on 2026-08-22.
# ---------------------------------------------------------------------------
INPUTS = {
    # M7 authority
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml":
        "F5B1572C0CFCEC35C40F262A3D7386AFA91DEC09DA94FE31FD03F5C04956F8B6",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_EXECUTION_PLAN_V1.md":
        "AD406ACA2AB12FDC794E8BBAB8B32AD33AB1ECE6FEE3BF332049DE3951D8C68B",
    # M6 executed tolerance baselines
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp3_tolerance/INTERFACE_STACKUP_B601_M3R_EXECUTED_V1.yaml":
        "483D75EE43B3214B2C18552991D2E9FB738F16ADF294F8A179AAD25DBEFDDC17",
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp3_tolerance/GRIPPER_CLEARANCE_SWEEP_VERDICT_V1.yaml":
        "DE037E3147586F1D6D22F10A44941045F9C8A3116289CFB38DD49046B41705B6",
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp3_tolerance/HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1.yaml":
        "B40F242CF52BD4568D838E0224A61D4BBA69937CDDA372EE8EA6BC5E2AA8B551",
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml":
        "0F9B413E7B6CD451E2724AD25CA4DA41E52E02C86F1D2874460274EADBAA47A2",
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp6_drawings_bom/DIGITAL_PROTOTYPE_BOM_V2_CANDIDATE.csv":
        "2FA3D479FB25295DF39C023D2204B2A75D351D81B162780908CCC700D097D544",
    # M4 tolerance and mechanism baselines
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/INTERFACE_STACKUP_B601_M3R_V1.yaml":
        "A5F95A9B11ACBF04E6ABEB2E850F5E18AD7CF8CAF18D70619DF7D04A1B09DA41",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/GRIPPER_FUNCTIONAL_TOLERANCE_MAP_V1.yaml":
        "8CD92F90346EE4481172939DF1BA182383411748D1E586DF0035EF9013A06A23",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/HINGE_DEPLOYMENT_TOLERANCE_CHAIN_V1.yaml":
        "6E17090392887ACFB8C3C31DF828E67252B27DF3092DB13E7E7892EA8BEE3858",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/05_tolerance/TOLERANCE_CLOSURE_EXECUTION_PLAN_V1.yaml":
        "42253B264E16BD14F9366D5B2EE6C4E5BD4F44AD64F1BE480EC027D2A2AAD5EC",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/06_mechanism/MECHANISM_STATUS_REGISTER_V1.yaml":
        "307A205460D746AD8B4FA3561157CA63FBAAD2EC6153D63A6FA733E695236FC9",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/06_mechanism/HDRM_PROTOTYPE_CLOSURE_PLAN_V1.yaml":
        "C6E812BAF9617C7E74112DF831562864E735344BCA3D3EE021E57618E121204A",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml":
        "67293323A45237FB9B415871A4160732EFB156DE74776C9E11ABA9C4202134CA",
    # Detailed-design / terminal-closure interface baselines
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
    # Gripper neutral witness + accepted URDF (L0, read-only)
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json":
        "7BC0DF784B36159624A8A89B67207C54C5C9C780B103CB38658DE2D6BA845F47",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/04_validation/GRIPPER_R1_CONTINUOUS_STROKE_SAMPLES.csv":
        "DAE4DBD5C2300D3CEC8602FDC9B12877614A2A8E28EFCD4A9D3F4F76A231382F",
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf":
        "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
    # Geometry SSOT
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
# Used ONLY as CANDIDATE_FIT allocations on existing frozen nominal geometry.
# ---------------------------------------------------------------------------
IT6_UM = {(3, 6): 8, (6, 10): 9, (10, 18): 11, (18, 30): 13, (30, 50): 16,
          (50, 80): 19, (80, 120): 22, (120, 180): 25}
IT7_UM = {(3, 6): 12, (6, 10): 15, (10, 18): 18, (18, 30): 21, (30, 50): 25,
          (50, 80): 30, (80, 120): 35, (120, 180): 40}
IT9_UM = {(3, 6): 30, (6, 10): 36, (10, 18): 43, (18, 30): 52, (30, 50): 62,
          (50, 80): 74, (80, 120): 87, (120, 180): 100}
IT11_UM = {(3, 6): 75, (6, 10): 90, (10, 18): 110, (18, 30): 130, (30, 50): 160,
           (50, 80): 190, (80, 120): 220, (120, 180): 250}
G_ES_UM = {(3, 6): -4, (6, 10): -5, (10, 18): -6, (18, 30): -7, (30, 50): -9,
           (50, 80): -10, (80, 120): -12, (120, 180): -14}
M_EI_UM = {(3, 6): 4, (6, 10): 6, (10, 18): 7, (18, 30): 8, (30, 50): 9,
           (50, 80): 11, (80, 120): 13, (120, 180): 15}


def _band(d_nom_mm: float, table: dict) -> float:
    for (lo, hi), val in table.items():
        if lo < d_nom_mm <= hi:
            return float(val)
    raise ValueError(f"no ISO 286 band for diameter {d_nom_mm}")


def iso_hole_H7(d): return 0.0, _band(d, IT7_UM) / 1000.0

def iso_hole_H11(d): return 0.0, _band(d, IT11_UM) / 1000.0

def iso_shaft_g6(d):
    es = _band(d, G_ES_UM) / 1000.0
    return es - _band(d, IT6_UM) / 1000.0, es

def iso_shaft_h6(d): return -_band(d, IT6_UM) / 1000.0, 0.0

def iso_shaft_h9(d): return -_band(d, IT9_UM) / 1000.0, 0.0

def iso_shaft_m6(d):
    ei = _band(d, M_EI_UM) / 1000.0
    return ei, ei + _band(d, IT6_UM) / 1000.0


def u_rect(half_width: float) -> float:
    """Standard uncertainty of a rectangular (uniform) tolerance contribution."""
    return half_width / math.sqrt(3.0)


def rss(*terms: float) -> float:
    return math.sqrt(sum(t * t for t in terms))


ROUND = 9


def r9(x):
    return None if x is None else round(x, ROUND)


# ---------------------------------------------------------------------------
# Evaluation helpers. Every functional check carries WC (must pass) and an
# RSS k=3 reference bound.
# ---------------------------------------------------------------------------
def check_min_floor(metric, unit, floor, wc_value, rss_u=None, rss_mean=None,
                    req_class="INTERFACE_PASS_THROUGH_DESIGN_FLOOR", basis=""):
    """Clearance-type function: WC minimum must be >= floor."""
    k3_bound = None if rss_u is None else rss_mean - 3.0 * rss_u
    return {
        "metric": metric, "unit": unit,
        "requirement_type": "MIN_FLOOR", "requirement_limit": floor,
        "requirement_class": req_class, "requirement_basis": basis,
        "wc_value": r9(wc_value), "wc_margin": r9(wc_value - floor),
        "wc_pass": bool(wc_value >= floor),
        "rss_standard_uncertainty": r9(rss_u),
        "rss_mean": r9(rss_mean),
        "rss_k3_bound": r9(k3_bound),
        "rss_k3_pass": None if k3_bound is None else bool(k3_bound >= floor),
    }


def check_max_ceiling(metric, unit, ceiling, wc_value, rss_u=None, rss_mean=None,
                      req_class="DESIGN_ALLOCATED_REQUIREMENT", basis=""):
    """Error-type function: WC absolute value must be <= ceiling."""
    k3_bound = None if rss_u is None else rss_mean + 3.0 * rss_u
    return {
        "metric": metric, "unit": unit,
        "requirement_type": "MAX_CEILING", "requirement_limit": ceiling,
        "requirement_class": req_class, "requirement_basis": basis,
        "wc_value": r9(wc_value), "wc_margin": r9(ceiling - wc_value),
        "wc_pass": bool(wc_value <= ceiling),
        "rss_standard_uncertainty": r9(rss_u),
        "rss_mean": r9(rss_mean),
        "rss_k3_bound": r9(k3_bound),
        "rss_k3_pass": None if k3_bound is None else bool(k3_bound <= ceiling),
    }


def check_window(metric, unit, half_window, wc_abs_max, rss_u=None,
                 req_class="DESIGN_ALLOCATED_REQUIREMENT", basis=""):
    """Bipolar function: |value| must stay within +/- half_window."""
    k3 = None if rss_u is None else 3.0 * rss_u
    return {
        "metric": metric, "unit": unit,
        "requirement_type": "WINDOW", "requirement_limit": half_window,
        "requirement_class": req_class, "requirement_basis": basis,
        "wc_value": r9(wc_abs_max), "wc_margin": r9(half_window - wc_abs_max),
        "wc_pass": bool(wc_abs_max <= half_window),
        "rss_standard_uncertainty": r9(rss_u),
        "rss_mean": 0.0,
        "rss_k3_bound": r9(k3),
        "rss_k3_pass": None if k3 is None else bool(k3 <= half_window),
    }


def fit_alloc(feature, nominal_mm, fit, limits, classification, datum, standard="ISO 286-2", notes=""):
    return {
        "feature": feature, "nominal_mm": nominal_mm, "tolerance_type": "SIZE_LIMITS",
        "allocated_fit": fit, "limits_mm": [r9(limits[0]), r9(limits[1])],
        "classification": classification, "datum_reference": datum,
        "standard_reference": standard, "notes": notes,
    }


def proc_alloc(feature, tolerance_type, value, unit, datum, classification="PROCESS_CAP_ASSUMED",
               standard="", notes=""):
    return {
        "feature": feature, "tolerance_type": tolerance_type, "allocated_value": value,
        "unit": unit, "classification": classification, "datum_reference": datum,
        "standard_reference": standard, "notes": notes,
    }


def chain_record(chain_id, title, assembly_leg, predecessor_refs, function,
                 allocations, checks, excluded_terms, retained_holds, status,
                 closure_note):
    return {
        "chain_id": chain_id, "title": title, "assembly_leg": assembly_leg,
        "predecessor_refs": predecessor_refs, "function": function,
        "reverse_allocation": allocations, "functional_checks": checks,
        "wc_overall_pass": (all(c["wc_pass"] for c in checks) if checks else None),
        "excluded_terms_not_zero_filled": excluded_terms,
        "retained_holds": retained_holds,
        "status": status, "closure_note": closure_note,
    }


# ---------------------------------------------------------------------------
# Chain builders TC-01..TC-14.
# ---------------------------------------------------------------------------
def tc01_b601_pattern():
    d_hole = (4.6 + iso_hole_H7(4.6)[0], 4.6 + iso_hole_H7(4.6)[1])
    d_screw = (4.0 + iso_shaft_h6(4.0)[0], 4.0 + iso_shaft_h6(4.0)[1])
    c_size_min, c_size_max = (d_hole[0] - d_screw[1]) / 2.0, (d_hole[1] - d_screw[0]) / 2.0
    r_pattern = 90.509641772 / 2.0
    e_clock = r_pattern * math.tan(math.radians(0.10))
    offsets = [0.05, 0.05, 0.02, e_clock]
    e_wc = sum(offsets)
    c_min_wc = c_size_min - e_wc
    u_c = 0.5 * rss(u_rect((d_hole[1] - d_hole[0]) / 2.0), u_rect((d_screw[1] - d_screw[0]) / 2.0))
    u_off = rss(*(u_rect(o) for o in offsets))
    u_total = rss(u_c, u_off)
    c_mean = (c_size_min + c_size_max) / 2.0
    flatness, span = 0.05, 64.0
    tilt_wc, tilt_u = flatness / span, u_rect(flatness) / span
    # fail-closed engine self-check against M6 executed baseline
    assert abs(c_min_wc - 0.101015357) < 1e-9, "TC-01 diverges from M6 executed baseline"
    checks = [
        check_min_floor("minimum_radial_clearance", "mm", 0.05, c_min_wc, u_total, c_mean,
                        basis="four HM4-75 axes must pass Stage A holes and counterbores at WC; "
                              "0.05 mm design assembly guard (burr/coating/insertion)"),
        check_max_ceiling("mounting_tilt", "rad", 1.5e-3, tilt_wc, tilt_u, 0.0,
                          basis="keeps flange face contact within flatness budget over 64 mm pattern span"),
    ]
    allocs = [
        fit_alloc("STAGE_A_CLEARANCE_HOLE_4P6", 4.6, "ISO286_H7", d_hole,
                  "CANDIDATE_FIT_ISO286_H7", "B601_AS_BUILT_PATTERN_DATUM"),
        fit_alloc("M4_FASTENER_MAJOR_DIAMETER_PROXY", 4.0, "ISO286_h6_ON_4P000_MAJOR", d_screw,
                  "CANDIDATE_FIT_ISO286_H6_THREAD_MAJOR_PROXY", "B601_AS_BUILT_PATTERN_DATUM",
                  notes="shaft proxy for thread major; final fastener spec WP4 PENDING_SIBLING_HASH"),
        proc_alloc("B601_AXIS_POSITION", "POSITION_RADIAL_HALF_WIDTH", 0.05, "mm",
                   "B601_AS_BUILT_PATTERN_DATUM", notes="as-built axis verification bound"),
        proc_alloc("STAGE_A_HOLE_POSITION", "POSITION_RADIAL_HALF_WIDTH", 0.05, "mm",
                   "B601_AS_BUILT_PATTERN_DATUM"),
        proc_alloc("DATUM_SHIFT", "ASSEMBLY_DATUM_SHIFT_HALF_WIDTH", 0.02, "mm",
                   "B601_AS_BUILT_PATTERN_DATUM"),
        proc_alloc("PATTERN_CLOCKING", "ANGULAR_HALF_WIDTH_DEG", 0.10, "deg",
                   "B601_AS_BUILT_PATTERN_DATUM",
                   notes=f"arc {r9(e_clock)} mm at measured PCD radius {r9(r_pattern)} mm"),
        proc_alloc("MOUNT_FACE_FLATNESS", "FLATNESS", 0.05, "mm",
                   "B601_AS_BUILT_PATTERN_DATUM", notes="over 64 mm pattern span"),
    ]
    return chain_record(
        "M7-TC-01", "B601_M4_PATTERN_ALIGNMENT", "B601 -> M3R_STAGE_A",
        {"m6_chain": "B601_M4_PATTERN_ALIGNMENT", "predecessor": "TC-004"},
        "assemble four B601 M4-class axes through Stage A holes and counterbores",
        allocs, checks,
        ["thermal_stack", "fastener_bending", "surface_finish", "measured_axis_CMM_report",
         "preload_effects"],
        ["HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE",
         "HOLD_THERMAL_STACKS_NO_APPROVED_CTE_OR_TEMPERATURE_RANGE"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        "M6 candidate values adopted as the design allocation; WC min radial clearance "
        f"{r9(c_min_wc)} mm >= 0.05 floor; RSS k3 min {r9(c_mean - 3 * u_total)} mm reference pass.")


def tc02_spigot_axial_seat():
    d_f = (100.0 + iso_hole_H7(100.0)[0], 100.0 + iso_hole_H7(100.0)[1])
    d_m = (99.6 + iso_shaft_g6(99.6)[0], 99.6 + iso_shaft_g6(99.6)[1])
    c_dia_min, c_dia_max = d_f[0] - d_m[1], d_f[1] - d_m[0]
    coax = 0.05
    u_f, u_m = u_rect((d_f[1] - d_f[0]) / 2.0), u_rect((d_m[1] - d_m[0]) / 2.0)
    u_c = 0.5 * rss(u_f, u_m)
    c_rad_min, c_rad_max = c_dia_min / 2.0, c_dia_max / 2.0
    assert abs(c_rad_min - 0.206) < 1e-12, "TC-02 radial diverges from M6 executed baseline"
    c_mean = (c_rad_min + c_rad_max) / 2.0
    # axial seat (M6 STAGE_A_STAGE_B_AXIAL_SEAT folded into this interface chain)
    d_nom, depth_half, flat, par = 5.595, 0.05, 0.02, 0.02
    g_wc = (d_nom + depth_half) - (d_nom - depth_half) + 2 * flat + par
    u_g = rss(u_rect(depth_half), u_rect(depth_half), u_rect(flat), u_rect(flat), u_rect(par))
    assert abs(g_wc - 0.16) < 1e-12, "TC-02 axial diverges from M6 executed baseline"
    checks = [
        check_min_floor("spigot_minimum_radial_clearance_after_coaxiality", "mm", 0.10,
                        c_rad_min - coax / 2.0, u_c, c_mean - coax / 2.0,
                        basis="central radial location without galling during Stage A/B assembly; "
                              "0.10 mm anti-fretting design floor"),
        check_window("axial_seating_gap", "mm", 0.20, g_wc, u_g,
                     basis="annular face preload-seat window; negative gap = controlled axial "
                           "interference (preload seat), positive = residual gap; both bounded"),
    ]
    allocs = [
        fit_alloc("STAGE_B_RECEIVING_BORE_100P0", 100.0, "ISO286_H7", d_f,
                  "CANDIDATE_FIT_ISO286_H7", "M3R_INTERFACE_DATUM"),
        fit_alloc("STAGE_A_SPIGOT_99P6", 99.6, "ISO286_g6", d_m,
                  "CANDIDATE_FIT_ISO286_G6", "M3R_INTERFACE_DATUM"),
        proc_alloc("SPIGOT_COAXIALITY", "COAXIALITY_DIAMETRAL_ZONE", 0.05, "mm",
                   "M3R_INTERFACE_DATUM"),
        proc_alloc("STAGE_A_RECESS_DEPTH_5P595", "DEPTH_LIMITS_HALF_WIDTH", 0.05, "mm",
                   "M3R_INTERFACE_DATUM"),
        proc_alloc("STAGE_B_POCKET_DEPTH_5P595", "DEPTH_LIMITS_HALF_WIDTH", 0.05, "mm",
                   "M3R_INTERFACE_DATUM"),
        proc_alloc("ANNULAR_FACE_FLATNESS_EACH", "FLATNESS", 0.02, "mm",
                   "M3R_INTERFACE_DATUM"),
        proc_alloc("ANNULAR_FACE_PARALLELISM", "PARALLELISM_ACROSS_FACE", 0.02, "mm",
                   "M3R_INTERFACE_DATUM"),
    ]
    return chain_record(
        "M7-TC-02", "STAGE_A_STAGE_B_SPIGOT_AND_AXIAL_SEAT", "M3R_STAGE_A -> M3R_STAGE_B",
        {"m6_chain": ["STAGE_A_STAGE_B_SPIGOT", "STAGE_A_STAGE_B_AXIAL_SEAT"],
         "predecessor": ["TC-001", "TC-003"]},
        "central radial location plus annular face seating and preload transfer",
        allocs, checks,
        ["thermal_stack_no_approved_CTE_or_temperature_range", "surface_finish",
         "measured_diameters", "preload_deflection_mm", "measured_depths"],
        ["HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE",
         "HOLD_THERMAL_STACKS_NO_APPROVED_CTE_OR_TEMPERATURE_RANGE"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        "Spigot WC radial after coaxiality 0.181 mm >= 0.10 floor; axial seat WC |gap| 0.16 mm "
        "inside +/-0.20 window (bipolar preload-seat design interpretation per M6).")


def tc03_skirt():
    d_f = (150.4 + iso_hole_H7(150.4)[0], 150.4 + iso_hole_H7(150.4)[1])
    d_m = (150.0 + iso_shaft_g6(150.0)[0], 150.0 + iso_shaft_g6(150.0)[1])
    c_dia_min, c_dia_max = d_f[0] - d_m[1], d_f[1] - d_m[0]
    coax = 0.05
    u_c = 0.5 * rss(u_rect((d_f[1] - d_f[0]) / 2.0), u_rect((d_m[1] - d_m[0]) / 2.0))
    c_rad_min, c_rad_max = c_dia_min / 2.0, c_dia_max / 2.0
    assert abs(c_rad_min - 0.207) < 1e-12, "TC-03 diverges from M6 executed baseline"
    c_mean = (c_rad_min + c_rad_max) / 2.0
    checks = [
        check_min_floor("skirt_minimum_radial_clearance_after_coaxiality", "mm", 0.10,
                        c_rad_min - coax / 2.0, u_c, c_mean - coax / 2.0,
                        basis="annular pocket radial location and load-seat compatibility; "
                              "0.10 mm anti-fretting design floor"),
    ]
    allocs = [
        fit_alloc("STAGE_B_POCKET_OUTER_150P4", 150.4, "ISO286_H7", d_f,
                  "CANDIDATE_FIT_ISO286_H7", "M3R_INTERFACE_DATUM"),
        fit_alloc("STAGE_A_SKIRT_OUTER_150P0", 150.0, "ISO286_g6", d_m,
                  "CANDIDATE_FIT_ISO286_G6", "M3R_INTERFACE_DATUM"),
        proc_alloc("SKIRT_COAXIALITY", "COAXIALITY_DIAMETRAL_ZONE", 0.05, "mm",
                   "M3R_INTERFACE_DATUM"),
    ]
    return chain_record(
        "M7-TC-03", "STAGE_A_STAGE_B_ANNULAR_SKIRT", "M3R_STAGE_A -> M3R_STAGE_B",
        {"m6_chain": "STAGE_A_STAGE_B_ANNULAR_SKIRT", "predecessor": "TC-002"},
        "annular pocket radial location and load-seat compatibility",
        allocs, checks,
        ["thermal_stack_no_approved_CTE_or_temperature_range", "surface_finish",
         "measured_diameters"],
        ["HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE",
         "HOLD_THERMAL_STACKS_NO_APPROVED_CTE_OR_TEMPERATURE_RANGE"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        "Skirt WC radial after coaxiality 0.182 mm >= 0.10 floor.")


def tc04_m5_pattern():
    d_hole = (5.5 + iso_hole_H7(5.5)[0], 5.5 + iso_hole_H7(5.5)[1])
    d_screw = (5.0 + iso_shaft_h6(5.0)[0], 5.0 + iso_shaft_h6(5.0)[1])
    c_size_min, c_size_max = (d_hole[0] - d_screw[1]) / 2.0, (d_hole[1] - d_screw[0]) / 2.0
    pos = 0.05
    c_min_wc = c_size_min - 2 * pos
    u_c = 0.5 * rss(u_rect((d_hole[1] - d_hole[0]) / 2.0), u_rect((d_screw[1] - d_screw[0]) / 2.0))
    u_total = rss(u_c, u_rect(pos), u_rect(pos))
    assert abs(c_min_wc - 0.15) < 1e-12, "TC-04 diverges from M6 executed baseline"
    checks = [
        check_min_floor("m5_minimum_radial_clearance", "mm", 0.05, c_min_wc, u_total, c_size_min,
                        basis="eight M5 fasteners must pass the transition pattern at WC; "
                              "0.05 mm design assembly guard; residual margin also sets the "
                              "clocking-dowel budget (M7-TC-05, CROSS_CHAIN_DERIVED)"),
    ]
    allocs = [
        fit_alloc("STAGE_B_M5_CLEARANCE_HOLE_5P5", 5.5, "ISO286_H7", d_hole,
                  "CANDIDATE_FIT_ISO286_H7", "M3R_INTERFACE_DATUM"),
        fit_alloc("M5_FASTENER_MAJOR_DIAMETER_PROXY", 5.0, "ISO286_h6_ON_5P000_MAJOR", d_screw,
                  "CANDIDATE_FIT_ISO286_H6_THREAD_MAJOR_PROXY", "M3R_INTERFACE_DATUM",
                  notes="shaft proxy for thread major; final fastener spec WP4 PENDING_SIBLING_HASH"),
        proc_alloc("M5_PATTERN_POSITION_EACH_SIDE", "POSITION_RADIAL_HALF_WIDTH", 0.05, "mm",
                   "M3R_INTERFACE_DATUM", notes="radius 62.5 mm pattern, 8 places"),
    ]
    return chain_record(
        "M7-TC-04", "STAGE_A_STAGE_B_M5_PATTERN", "M3R_STAGE_A -> M3R_STAGE_B",
        {"m6_chain": "STAGE_A_STAGE_B_M5_AND_CLOCKING (M5 part)", "predecessor": "TC-005"},
        "eight-fastener M5 transition pattern alignment at radius 62.5 mm",
        allocs, checks,
        ["fastener_preload_and_grade", "measured_positions", "thermal_stack"],
        ["HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE",
         "HOLD_FASTENER_PRELOAD_GRADE_AND_MOS (WP4 PENDING_SIBLING_HASH)"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        "M5 WC min radial clearance 0.15 mm >= 0.05 floor; RSS k3 min 0.127 mm reference pass.")


def tc05_clocking_dowel():
    d_pin = (4.0 + iso_shaft_m6(4.0)[0], 4.0 + iso_shaft_m6(4.0)[1])
    d_press = (4.0 + iso_hole_H7(4.0)[0], 4.0 + iso_hole_H7(4.0)[1])
    d_slip = (4.1 + iso_hole_H7(4.1)[0], 4.1 + iso_hole_H7(4.1)[1])
    press_min, press_max = d_press[0] - d_pin[1], d_press[1] - d_pin[0]
    slip_min, slip_max = d_slip[0] - d_pin[1], d_slip[1] - d_pin[0]
    r_dowel, hole_pos = 55.0, 0.025
    slop_wc = slip_max / 2.0 + 2 * hole_pos
    theta_wc = slop_wc / r_dowel
    u_slop = rss(0.5 * rss(u_rect((d_slip[1] - d_slip[0]) / 2.0),
                           u_rect((d_pin[1] - d_pin[0]) / 2.0)),
                 u_rect(hole_pos), u_rect(hole_pos))
    theta_u = u_slop / r_dowel
    assert abs(theta_wc - 1.890909e-3) < 1e-9, "TC-05 diverges from M6 executed baseline"
    theta_req = 0.15 / 62.5  # TC-04 WC margin at M5 pattern radius -> CROSS_CHAIN_DERIVED
    checks = [
        check_max_ceiling("clocking_error", "rad", theta_req, theta_wc, theta_u, 0.0,
                          req_class="CROSS_CHAIN_DERIVED",
                          basis="clocking-induced hole offset at M5 radius 62.5 mm must stay "
                                "inside the M7-TC-04 WC margin 0.15 mm -> theta <= 2.4e-3 rad"),
        check_min_floor("locator_press_seat_diametral_fit", "mm", -0.02, press_min,
                        req_class="DESIGN_ALLOCATED_REQUIREMENT",
                        basis="press seat may interfere down to -0.02 mm (retained fit) and must "
                              "not exceed slip fit on the press side"),
    ]
    allocs = [
        fit_alloc("CLOCKING_DOWEL_PIN_4P0", 4.0, "ISO286_m6", d_pin,
                  "CANDIDATE_FIT_ISO286_M6_DOWEL_PIN", "M3R_INTERFACE_DATUM"),
        fit_alloc("STAGE_B_BLIND_HOLE_4P0_PRESS_SEAT", 4.0, "ISO286_H7", d_press,
                  "CANDIDATE_FIT_ISO286_H7", "M3R_INTERFACE_DATUM",
                  notes=f"press fit {r9(press_min)}..{r9(press_max)} mm"),
        fit_alloc("STAGE_A_DOWEL_CLEARANCE_4P1_SLIP_SEAT", 4.1, "ISO286_H7", d_slip,
                  "CANDIDATE_FIT_ISO286_H7", "M3R_INTERFACE_DATUM",
                  notes=f"slip clearance {r9(slip_min)}..{r9(slip_max)} mm"),
        proc_alloc("DOWEL_HOLE_POSITION_EACH_SIDE", "POSITION_RADIAL_HALF_WIDTH", 0.025, "mm",
                   "M3R_INTERFACE_DATUM"),
    ]
    return chain_record(
        "M7-TC-05", "STAGE_A_STAGE_B_CLOCKING_DOWEL", "M3R_STAGE_A -> M3R_STAGE_B",
        {"m6_chain": "STAGE_A_STAGE_B_M5_AND_CLOCKING (clocking part)", "predecessor": "TC-006"},
        "asymmetric clocking locator removes Stage A/B clocking ambiguity while preserving fit",
        allocs, checks,
        ["fastener_preload_and_grade", "blind_hole_depth_tolerance", "locator_part_real_profile",
         "measured_positions", "thermal_stack"],
        ["HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        f"Clocking WC {r9(theta_wc)} rad <= 2.4e-3 cross-chain limit (TC-04 margin); "
        "press/slip seat pair bounded.")


def tc06_bridge_bus():
    d_hole = (6.6 + iso_hole_H11(6.6)[0], 6.6 + iso_hole_H11(6.6)[1])
    d_shaft = (6.0 + iso_shaft_h9(6.0)[0], 6.0 + iso_shaft_h9(6.0)[1])
    c_size_min, c_size_max = (d_hole[0] - d_shaft[1]) / 2.0, (d_hole[1] - d_shaft[0]) / 2.0
    pos = 0.05
    c_min_wc = c_size_min - 2 * pos
    u_c = 0.5 * rss(u_rect((d_hole[1] - d_hole[0]) / 2.0), u_rect((d_shaft[1] - d_shaft[0]) / 2.0))
    u_total = rss(u_c, u_rect(pos), u_rect(pos))
    c_mean = (c_size_min + c_size_max) / 2.0
    flat = 0.05
    tilt_wc, tilt_u = 2 * flat / 140.0, rss(u_rect(flat), u_rect(flat)) / 140.0
    checks = [
        check_min_floor("cobore_minimum_radial_clearance", "mm", 0.10, c_min_wc, u_total, c_mean,
                        basis="four M6 through-bolts share the 4x dia 6.6 co-bore at (+-70,+-70) "
                              "between load bridge and bus +X face (x=185.25); 0.10 mm design floor"),
        check_max_ceiling("seating_tilt", "rad", 1.5e-3, tilt_wc, tilt_u, 0.0,
                          basis="planar abutment D_BRIDGE_BUS flatness pair over 140 mm pattern span"),
    ]
    allocs = [
        fit_alloc("LOAD_BRIDGE_HOLE_6P6", 6.6, "ISO286_H11", d_hole,
                  "CANDIDATE_FIT_ISO286_H11", "D_BRIDGE_BUS",
                  notes="M6 WP1 load-bridge fit candidate (H11/h9)"),
        fit_alloc("BUS_CIBORE_HOLE_6P6", 6.6, "ISO286_H11", d_hole,
                  "CANDIDATE_FIT_ISO286_H11", "D_BRIDGE_BUS",
                  notes="new bus-side design feature allocated by this WP; adoption "
                        "WP1 DESIGN_FREEZE_ASSEMBLY_V1 PENDING_SIBLING_HASH"),
        fit_alloc("M6_FASTENER_SHAFT_PROXY", 6.0, "ISO286_h9_ON_6P000", d_shaft,
                  "CANDIDATE_FIT_ISO286_H9_SHAFT_PROXY", "D_BRIDGE_BUS",
                  notes="M6 WP1 fit candidate; final fastener spec WP4 PENDING_SIBLING_HASH"),
        proc_alloc("BRIDGE_HOLE_PATTERN_POSITION", "POSITION_RADIAL_HALF_WIDTH", 0.05, "mm",
                   "D_BRIDGE_BUS"),
        proc_alloc("BUS_CIBORE_PATTERN_POSITION", "POSITION_RADIAL_HALF_WIDTH", 0.05, "mm",
                   "D_BRIDGE_BUS"),
        proc_alloc("BUS_MATE_FACE_FLATNESS", "FLATNESS", 0.05, "mm", "D_BRIDGE_BUS"),
        proc_alloc("BRIDGE_BUS_FACE_FLATNESS", "FLATNESS", 0.05, "mm", "D_BRIDGE_BUS"),
    ]
    return chain_record(
        "M7-TC-06", "LOAD_BRIDGE_TO_BUS_FITMENT", "SPACECRAFT_BUS -> SPACECRAFT_LOAD_BRIDGE",
        {"m6_chain": "LOAD_BRIDGE_DATUMS_V1 fit_candidates (BRIDGE_HOLE_6P6_vs_M6_FASTENER_SHAFT)",
         "predecessor": "TC-007 (spacecraft side)"},
        "planar abutment and 4x M6 co-bore through-bolt attachment of the load bridge to the "
        "bus +X face at x=185.25",
        allocs, checks,
        ["bus_wall_thickness_and_tapped_stack", "through_bolt_length_and_preload",
         "measured_bus_face_flatness", "thermal_stack", "legacy_flange_ownership"],
        ["HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE",
         "HOLD_FASTENER_PRELOAD_GRADE_AND_MOS (WP4 PENDING_SIBLING_HASH)",
         "STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD (WP7 FEA PENDING_SIBLING_HASH)"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        f"Co-bore WC min radial clearance {r9(c_min_wc)} mm >= 0.10 floor; seating tilt WC "
        f"{r9(tilt_wc)} rad <= 1.5e-3. Bus-side co-bore pattern is a new design feature of this "
        "allocation (bus is project-owned geometry).")


def tc07_bridge_stage_b():
    d_hole_b = (6.6 + iso_hole_H7(6.6)[0], 6.6 + iso_hole_H7(6.6)[1])     # Stage B existing feature
    d_hole_br = (6.6 + iso_hole_H11(6.6)[0], 6.6 + iso_hole_H11(6.6)[1])  # bridge candidate
    d_shaft = (6.0 + iso_shaft_h9(6.0)[0], 6.0 + iso_shaft_h9(6.0)[1])
    c_h7_min, c_h7_max = (d_hole_b[0] - d_shaft[1]) / 2.0, (d_hole_b[1] - d_shaft[0]) / 2.0
    c_h11_min, c_h11_max = (d_hole_br[0] - d_shaft[1]) / 2.0, (d_hole_br[1] - d_shaft[0]) / 2.0
    pos = 0.05
    c_min_wc = min(c_h7_min, c_h11_min) - 2 * pos
    u_c7 = 0.5 * rss(u_rect((d_hole_b[1] - d_hole_b[0]) / 2.0), u_rect((d_shaft[1] - d_shaft[0]) / 2.0))
    u_total = rss(u_c7, u_rect(pos), u_rect(pos))
    c_mean = (min(c_h7_min, c_h11_min) + c_h7_max) / 2.0
    # edge ligaments (both sides of the interface)
    lig_b_nom = 160.0 / 2.0 - 70.0 - 6.6 / 2.0
    lig_b_wc = 160.0 / 2.0 - 70.0 - d_hole_b[1] / 2.0 - pos
    u_lig_b = rss(0.5 * u_rect((d_hole_b[1] - d_hole_b[0]) / 2.0), u_rect(pos))
    lig_b_mean = 160.0 / 2.0 - 70.0 - (d_hole_b[0] + d_hole_b[1]) / 4.0
    lig_br_wc = 160.0 / 2.0 - 70.0 - d_hole_br[1] / 2.0 - pos
    u_lig_br = rss(0.5 * u_rect((d_hole_br[1] - d_hole_br[0]) / 2.0), u_rect(pos))
    lig_br_mean = 160.0 / 2.0 - 70.0 - (d_hole_br[0] + d_hole_br[1]) / 4.0
    assert abs(lig_b_wc - 6.6425) < 1e-9, "TC-07 Stage-B ligament diverges from M6 baseline"
    flat = 0.05
    tilt_wc = 2 * flat / 140.0
    tilt_u = rss(u_rect(flat), u_rect(flat)) / 140.0
    checks = [
        check_min_floor("m6_minimum_radial_clearance_both_plates", "mm", 0.10, c_min_wc,
                        u_total, c_mean,
                        basis="4x M6 primary fasteners pass Stage B (H7) and bridge (H11) holes at "
                              "WC; 0.10 mm design floor"),
        check_min_floor("edge_ligament_minimum_both_sides", "mm", 6.0, min(lig_b_wc, lig_br_wc),
                        u_lig_br, min(lig_b_mean, lig_br_mean),
                        req_class="GEOMETRIC_DESIGN_FLOOR",
                        basis="geometric ligament floor only; structural adequacy delegated to "
                              "WP7 operational FEA PENDING_SIBLING_HASH"),
        check_max_ceiling("interface_seating_tilt", "rad", 1.5e-3, tilt_wc, tilt_u, 0.0,
                          basis="Stage B + bridge mate-face flatness pair over 140 mm pattern span"),
    ]
    allocs = [
        fit_alloc("STAGE_B_M6_CLEARANCE_HOLE_6P6", 6.6, "ISO286_H7", d_hole_b,
                  "CANDIDATE_FIT_ISO286_H7", "D_BRIDGE_M3R",
                  notes="existing M3R Stage B feature (working-loop FROZEN nominal)"),
        fit_alloc("LOAD_BRIDGE_HOLE_6P6", 6.6, "ISO286_H11", d_hole_br,
                  "CANDIDATE_FIT_ISO286_H11", "D_BRIDGE_M3R"),
        fit_alloc("M6_FASTENER_SHAFT_PROXY", 6.0, "ISO286_h9_ON_6P000", d_shaft,
                  "CANDIDATE_FIT_ISO286_H9_SHAFT_PROXY", "D_BRIDGE_M3R",
                  notes="final fastener spec WP4 PENDING_SIBLING_HASH"),
        proc_alloc("STAGE_B_HOLE_PATTERN_POSITION", "POSITION_RADIAL_HALF_WIDTH", 0.05, "mm",
                   "D_BRIDGE_M3R"),
        proc_alloc("BRIDGE_HOLE_PATTERN_POSITION", "POSITION_RADIAL_HALF_WIDTH", 0.05, "mm",
                   "D_BRIDGE_M3R"),
        proc_alloc("STAGE_B_MATE_FACE_FLATNESS", "FLATNESS", 0.05, "mm", "D_BRIDGE_M3R"),
        proc_alloc("BRIDGE_M3R_FACE_FLATNESS", "FLATNESS", 0.05, "mm", "D_BRIDGE_M3R"),
        proc_alloc("HOLE_EDGE_LIGAMENT", "MINIMUM_EDGE_LIGAMENT_FLOOR", 6.0, "mm",
                   "D_BRIDGE_M3R", classification="DESIGN_ALLOCATED_REQUIREMENT",
                   notes=f"WC ligament Stage B {r9(lig_b_wc)} mm / bridge {r9(lig_br_wc)} mm; "
                         "structural check WP7 PENDING_SIBLING_HASH"),
    ]
    return chain_record(
        "M7-TC-07", "LOAD_BRIDGE_TO_STAGE_B_FITMENT", "SPACECRAFT_LOAD_BRIDGE -> M3R_STAGE_B",
        {"m6_chain": "STAGE_B_SPACECRAFT_M6_PATTERN (upgraded: bridge side now defined)",
         "predecessor": "TC-007"},
        "planar abutment at x=196.0 and 4x M6 primary pattern (140x140) between the load bridge "
        "and M3R Stage B",
        allocs, checks,
        ["m6_threaded_stack_and_engagement", "preload_effects", "measured_flatness",
         "thermal_stack"],
        ["HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE",
         "HOLD_FASTENER_PRELOAD_GRADE_AND_MOS (WP4 PENDING_SIBLING_HASH)",
         "STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD (WP7 FEA PENDING_SIBLING_HASH)"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        f"M6 pass-through WC min radial clearance {r9(c_min_wc)} mm >= 0.10 floor; WC ligament "
        f"{r9(min(lig_b_wc, lig_br_wc))} mm >= 6.0 geometric floor; tilt WC {r9(tilt_wc)} rad "
        "<= 1.5e-3. M6 Stage-B-side-only HOLD upgraded to analytic closure: bridge-side geometry "
        "is now the M6 WP1 candidate contract (execution-plan pinned).")


def tc08_gripper_rail_palm():
    g_add = 0.20  # WP3 design-allocated nominal additional rail-palm clearance
    terms = {  # half-width consumption terms (mm), rectangular
        "slot_width_tolerance": 0.03,
        "rail_width_tolerance": 0.03,
        "slot_straightness": 0.01,
        "rail_straightness": 0.01,
        "guide_parallelism": 0.01,
        "assembly_datum_shift": 0.02,
        "coating_thickness_left": 0.005,
        "coating_thickness_right": 0.005,
    }
    guard = 0.02
    consumption_wc = sum(terms.values())
    c_wc = g_add - consumption_wc - guard
    u_c = rss(*(u_rect(v) for v in terms.values()))
    c_mean = g_add - guard
    checks = [
        check_min_floor("guarded_minimum_functional_clearance", "mm", 0.0, c_wc, u_c, c_mean,
                        req_class="DESIGN_ALLOCATED_REQUIREMENT",
                        basis="no rail-palm contact over stroke 0..71.5 mm (144-sample neutral "
                              "witness, consumption 0); strictly positive guarded clearance at WC "
                              "after all allocated consumption terms and the 0.02 mm guard band"),
    ]
    allocs = [
        proc_alloc("RAIL_PALM_NOMINAL_ADDITIONAL_CLEARANCE", "NOMINAL_GAP_REQUIREMENT", g_add,
                   "mm", "GRIPPER_CAPTURE_FRAME", classification="DESIGN_ALLOCATED_REQUIREMENT",
                   notes="requirement flowed down to WP1/WP5 geometry owners; NOT taken from the "
                         "M4 owner example grid (that grid stays non-requirement); neutral sweep "
                         "witness covers 0-overlap for the R1 slot envelope"),
        proc_alloc("SLOT_WIDTH", "WIDTH_LIMITS_HALF_WIDTH", 0.03, "mm", "GRIPPER_CAPTURE_FRAME"),
        proc_alloc("RAIL_WIDTH", "WIDTH_LIMITS_HALF_WIDTH", 0.03, "mm", "GRIPPER_CAPTURE_FRAME"),
        proc_alloc("SLOT_STRAIGHTNESS", "STRAIGHTNESS", 0.01, "mm", "GRIPPER_CAPTURE_FRAME"),
        proc_alloc("RAIL_STRAIGHTNESS", "STRAIGHTNESS", 0.01, "mm", "GRIPPER_CAPTURE_FRAME"),
        proc_alloc("GUIDE_PAIR_PARALLELISM", "PARALLELISM", 0.01, "mm", "GRIPPER_CAPTURE_FRAME"),
        proc_alloc("ASSEMBLY_DATUM_SHIFT", "ASSEMBLY_SHIFT", 0.02, "mm", "GRIPPER_CAPTURE_FRAME"),
        proc_alloc("COATING_THICKNESS_EACH_SIDE", "COATING_THICKNESS_MAX", 0.005, "mm",
                   "GRIPPER_CAPTURE_FRAME",
                   notes="thin hard-coat allowance; final coating selection WP6 "
                         "DESIGN_MATERIAL_SELECTION_V1 PENDING_SIBLING_HASH"),
        proc_alloc("GUARD_BAND", "DECISION_GUARD_BAND", guard, "mm", "GRIPPER_CAPTURE_FRAME",
                   classification="DESIGN_ALLOCATED_REQUIREMENT",
                   notes="covers inspection uncertainty decision rule at conformity assessment"),
    ]
    return chain_record(
        "M7-TC-08", "GRIPPER_RAIL_PALM_CLEARANCE", "GRIPPER_R1_RAIL -> GRIPPER_R1_PALM",
        {"m4_chain": "GRIPPER_FUNCTIONAL_TOLERANCE_MAP_V1",
         "m6_chain": "GRIPPER_CLEARANCE_SWEEP_VERDICT_V1"},
        "guarded minimum functional clearance between guide rail and palm slot over the full "
        "0..71.5 mm stroke",
        allocs, checks,
        ["thermal_stack", "elastic_deflection_under_authorized_load",
         "wear_debris_and_life_allowance", "coating_final_selection (WP6)",
         "inspection_uncertainty_type_A_B_data", "conformity_decision_rule_qualification"],
        ["HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE",
         "HOLD_THERMAL_STACKS_NO_APPROVED_CTE_OR_TEMPERATURE_RANGE",
         "HOLD_GRIPPER_ELASTIC_AND_WEAR_TERMS_REQUIRE_AUTHORIZED_LOAD_AND_LIFE_TEST"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        f"Reverse allocation sets nominal additional clearance {g_add} mm plus bounded consumption "
        f"{r9(consumption_wc)} mm and guard {guard} mm -> WC guarded clearance {r9(c_wc)} mm > 0; "
        f"RSS k3 min {r9(c_mean - 3 * u_c)} mm reference pass. Closure mode: allocation defines "
        "the nominal-gap design requirement adopted downstream (WP1/WP5 PENDING_SIBLING_HASH).")


def tc09_gripper_finger_symmetry():
    slot_pos, finger_pos, sync = 0.05, 0.05, 0.10
    wc_asym = 2 * slot_pos + finger_pos + sync  # left-right slot difference + finger + drive sync
    u_asym = rss(u_rect(slot_pos), u_rect(slot_pos), u_rect(finger_pos), u_rect(sync))
    checks = [
        check_max_ceiling("fingertip_symmetry_error", "mm", 0.5, wc_asym, u_asym, 0.0,
                          basis="two-finger symmetric capture: fingertip centre offset from the "
                                "palm centre plane must keep the capture centre within 0.5 mm "
                                "for the 22 kg / 150 kg block-model targets"),
    ]
    allocs = [
        proc_alloc("PALM_SLOT_POSITION_SYMMETRY", "POSITION_RADIAL_HALF_WIDTH_EACH", slot_pos,
                   "mm", "GRIPPER_CAPTURE_FRAME",
                   notes="left/right rail slots in the single palm part; WC relative 0.10 mm"),
        proc_alloc("FINGER_RAIL_POSITION", "POSITION_RADIAL_HALF_WIDTH_EACH", finger_pos, "mm",
                   "GRIPPER_CAPTURE_FRAME"),
        proc_alloc("DRIVE_SYNCHRONISM_ERROR", "STROKE_SYNC_HALF_WIDTH", sync, "mm",
                   "GRIPPER_CAPTURE_FRAME",
                   notes="left/right stroke synchronism allocation; drive topology to WP5 "
                         "GRIPPER_ENGINEERING_PACK_V1 PENDING_SIBLING_HASH"),
    ]
    return chain_record(
        "M7-TC-09", "GRIPPER_FINGER_SYMMETRY", "GRIPPER_R1_LEFT_FINGER <-> GRIPPER_R1_RIGHT_FINGER",
        {"urdf": "accepted arm_b601_v1.urdf gripper_joint1/joint2 mirrored prismatic pair",
         "predecessor": "TC-013 (capture centre alignment)"},
        "left/right fingertip symmetry about the palm centre plane at any stroke",
        allocs, checks,
        ["finger_pad_compliance", "target_contact_geometry", "measured_finger_positions",
         "drive_backlash_real_value"],
        ["HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        "Kinematic symmetry is exact by construction in the accepted URDF (mirrored prismatic "
        f"pair, mirrored finger CoM); manufacturing asymmetry WC {r9(wc_asym)} mm <= 0.5 ceiling; "
        f"RSS k3 {r9(3 * u_asym)} mm reference pass.")


def tc10_hinge_coaxiality():
    span = 227.0  # frozen panel chord (flexible_appendage_v1 chord_b_m=0.227), hinge reference span
    lug_pos, flat = 0.05, 0.02
    mis_pos = 2 * lug_pos / span
    mis_flat = flat / span
    mis_wc = mis_pos + mis_flat
    u_mis = rss(u_rect(lug_pos), u_rect(lug_pos), u_rect(flat)) / span
    checks = [
        check_max_ceiling("hinge_line_angular_misalignment", "rad", 1.0e-3, mis_wc, u_mis, 0.0,
                          basis="two lug bore axes of one hinge must stay aligned so the pin is "
                                "not moment-loaded and the deployed-angle budget (M7-TC-11) holds; "
                                "1.0 mrad design ceiling"),
    ]
    allocs = [
        proc_alloc("LUG_BORE_POSITION_EACH", "POSITION_RADIAL_HALF_WIDTH", lug_pos, "mm",
                   "WING_HINGE_DATUM", notes=f"evaluated over {span} mm hinge reference span "
                                             "(frozen panel chord)"),
        proc_alloc("HINGE_BRACKET_MOUNT_FLATNESS", "FLATNESS", flat, "mm", "WING_HINGE_DATUM",
                   notes=f"over {span} mm reference span"),
    ]
    return chain_record(
        "M7-TC-10", "SOLAR_HINGE_COAXIALITY", "HINGE_BRACKET_LEFT/RIGHT_LUGS (per panel)",
        {"predecessor": "TC-009 (geometric part only)",
         "m6_chain": "HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1 chains_not_executed.radial_fit_chain"},
        "coaxiality of the two lug bore axes and hinge-bracket mount flatness per panel hinge",
        allocs, checks,
        ["hinge_pin_and_bore_nominals_and_limits (TC-009, no numeric authority -> WP5)",
         "pin_bore_radial_fit", "bushing_spacer_washer_stack", "thermal_stack", "wear_life"],
        ["HOLD_HINGE_HARDWARE_NOMINALS_FITS_AND_STOP_GEOMETRY (WP5 "
         "SOLAR_HINGE_DEPLOYMENT_PACK_V1 PENDING_SIBLING_HASH)",
         "HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        f"Geometric coaxiality WC misalignment {r9(mis_wc)} rad <= 1.0e-3 ceiling over the "
        f"frozen 227 mm chord reference span; RSS k3 {r9(3 * u_mis)} rad reference pass. "
        "Pin/bore radial fit terms excluded (nominals absent, TC-009) — never zero-filled.")


def tc11_hinge_stop_angle():
    L = 200.0  # frozen panel span (flexible_appendage_v1 span_L_m=0.200), mm lever arm
    stop_repeat = math.radians(0.5)  # allocated consolidated stop-term
    coax_contrib = 5.286343e-4       # M7-TC-10 WC misalignment (2*0.05/227 + 0.02/227)
    dtheta_wc = stop_repeat + coax_contrib
    u_stop, u_coax = u_rect(stop_repeat), 1.869018e-4
    u_tot = rss(u_stop, u_coax)
    tip_wc = L * math.sin(dtheta_wc)
    req = math.radians(1.0)
    checks = [
        check_max_ceiling("deployed_angle_deviation", "rad", req, dtheta_wc, u_tot, 0.0,
                          basis="panel deployed-angle accuracy at the hard stop; 1.0 deg design "
                                "ceiling (no mission-level pointing requirement is authorized — "
                                "this is a WP3 design allocation, not a flight requirement)"),
        check_max_ceiling("tip_lateral_displacement_at_span", "mm", 5.0, tip_wc, None, None,
                          basis="consequence metric at the 200 mm frozen span tip; 5 mm design "
                                "ceiling protects the deployed keep-out envelope"),
    ]
    allocs = [
        proc_alloc("STOP_ANGLE_REPEATABILITY", "ANGULAR_HALF_WIDTH_DEG", 0.5, "deg",
                   "WING_HINGE_DATUM",
                   notes="consolidated stop-chain term (stop contact geometry, contact flatness, "
                         "pin freeplay at the stop) — single controllable drawing requirement; "
                         "decomposition to hardware features needs WP5 hinge hardware nominals"),
        proc_alloc("HINGE_LINE_MISALIGNMENT_CONTRIBUTION", "FROM_CHAIN", None, "rad",
                   "WING_HINGE_DATUM", classification="CROSS_CHAIN_REFERENCE",
                   notes="M7-TC-10 WC misalignment 5.286343e-4 rad carried into this stack"),
    ]
    return chain_record(
        "M7-TC-11", "SOLAR_HINGE_STOP_ANGLE", "HINGE_HARD_STOP (per panel)",
        {"predecessor": "TC-010",
         "m6_chain": "HINGE_DEPLOYMENT_CHAIN_EXECUTED_V1 executed_results"},
        "deployed stop-angle accuracy of the solar panel at end of travel",
        allocs, checks,
        ["stop_contact_geometry_detail", "compliance_rad_per_Nm", "authorized_stop_torque_Nm",
         "approved_temperature_range_degC", "approved_CTE_per_K", "wear_and_repeatability_test"],
        ["HOLD_HINGE_HARDWARE_NOMINALS_FITS_AND_STOP_GEOMETRY (WP5 PENDING_SIBLING_HASH)",
         "HOLD_THERMAL_STACKS_NO_APPROVED_CTE_OR_TEMPERATURE_RANGE",
         "HOLD_DEPLOYMENT_TEST_AND_LIFE_EVIDENCE"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        f"WC deployed-angle deviation {r9(dtheta_wc)} rad ({r9(math.degrees(dtheta_wc))} deg) <= "
        f"1.0 deg ceiling; RSS k3 {r9(3 * u_tot)} rad reference pass; tip consequence "
        f"{r9(tip_wc)} mm at 200 mm span. M6 single-term sensitivity upgraded to a two-term "
        "design stack (stop repeatability + TC-10 misalignment).")


def tc12_wing_root_position():
    pos_terms = [0.05, 0.05, 0.05]  # bracket hole, bus seat, panel root fitting
    wc_pos = sum(pos_terms)
    u_pos = rss(*(u_rect(p) for p in pos_terms))
    checks = [
        check_max_ceiling("wing_root_axis_position_error", "mm", 0.5, wc_pos, u_pos, 0.0,
                          basis="panel root (hinge axis) station relative to the bus must hold "
                                "the frozen deployed envelope 440.5x626.3x276.3 mm and the mass/"
                                "CoM model validity; 0.5 mm design ceiling"),
    ]
    allocs = [
        proc_alloc("HINGE_BRACKET_HOLE_POSITION", "POSITION_RADIAL_HALF_WIDTH", 0.05, "mm",
                   "F_L / F_R"),
        proc_alloc("BUS_SEAT_POSITION", "POSITION_RADIAL_HALF_WIDTH", 0.05, "mm", "F_L / F_R"),
        proc_alloc("PANEL_ROOT_FITTING_HOLE_POSITION", "POSITION_RADIAL_HALF_WIDTH", 0.05, "mm",
                   "F_L / F_R"),
    ]
    return chain_record(
        "M7-TC-12", "WING_ROOT_POSITION", "SPACECRAFT_BUS -> HINGE_BRACKET -> PANEL_ROOT",
        {"frame_tree": "F_L [-56.75,113.15,0] / F_R [-56.75,-113.15,0] frozen origins; "
                       "hinge axis B-rep probe [-61.0,+-143.15,0] axis [1,0,0]",
         "predecessor": "TC-009/TC-010 (position aspect)"},
        "position of the panel root hinge axis relative to the spacecraft assembly frame",
        allocs, checks,
        ["full_hinge_kinematics_orientation (frame tree HOLD, not gated by this position chain)",
         "measured_bracket_positions", "thermal_stack"],
        ["HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE"],
        "FUNCTIONALLY_CLOSED_ANALYTIC",
        f"Root position WC error {r9(wc_pos)} mm <= 0.5 ceiling; RSS k3 {r9(3 * u_pos)} mm "
        "reference pass. Position-only chain; hinge orientation kinematics stay with WP5.")


def tc13_camera_pointing():
    return chain_record(
        "M7-TC-13", "CAMERA_BRACKET_POINTING", "SPACECRAFT_BUS -> CAMERA_BRACKET -> SENSOR_PACKAGE",
        {"frame_tree": "SENSOR_PACKAGE UNRESOLVED_CANDIDATE_REJECTED_M3R_POSITIVE_PENETRATION",
         "bom": "DIGITAL_PROTOTYPE_BOM_V2_CANDIDATE DP-010 HARD_HOLD"},
        "pointing accuracy of the camera/sensor bracket relative to its mission datum",
        [], [], [],
        ["HOLD_CAMERA_BRACKET_POSE_NO_AUTHORIZED_GEOMETRY",
         "HOLD_POINTING_REQUIREMENT_NOT_AUTHORIZED"],
        "FUNCTIONALLY_OPEN",
        "No authorized bracket pose or pointing datum exists: the M4 sensor-package candidate "
        "origin [190.25,0,80.0] was rejected (penetrates M3R) and no replacement pose is "
        "authorized (BOM V2 DP-010 HARD_HOLD). No nominal geometry -> reverse allocation is "
        "impossible without inventing nominals (zero-fill / hard-forcing forbidden). Awaits WP1 "
        "SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml PENDING_SIBLING_HASH and an authorized pointing "
        "requirement.")


def tc14_hdrm_preload():
    return chain_record(
        "M7-TC-14", "HDRM_PRELOAD_INTERFACE", "HDRM -> ARM_AND_SPACECRAFT_RESTRAINT",
        {"m4_plan": "HDRM_PROTOTYPE_CLOSURE_PLAN_V1 gate.architecture_selected=false",
         "predecessor": "TC-012 (confidence NONE)",
         "bom": "DIGITAL_PROTOTYPE_BOM_V2_CANDIDATE DP-011 HARD_HOLD"},
        "hold-down preload interface: restraint seating, preload retention and release clearance",
        [], [], [],
        ["HOLD_HDRM_ARCHITECTURE_NOT_SELECTED",
         "HOLD_MATING_PATTERN_AND_PRELOAD_NO_NUMERIC_AUTHORITY",
         "HOLD_RELEASE_CLEARANCE_AND_LOADS_NOT_AUTHORIZED"],
        "FUNCTIONALLY_OPEN",
        "HDRM architecture is not selected (M4 closure plan: HDRM-C01..C03 unscreened), the "
        "mating pattern / preload / release clearance are all null (TC-012 confidence NONE; "
        "BOM V2 DP-011 not installed). No numeric basis for a preload-interface chain exists. "
        "Awaits WP5 HDRM_ENGINEERING_PACK_V1.yaml PENDING_SIBLING_HASH; the allocation framework "
        "in this register is ready to receive its nominals.")


# ---------------------------------------------------------------------------
# Output writers.
# ---------------------------------------------------------------------------
def write_yaml(path: Path, doc: dict) -> None:
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True,
                                   width=120), encoding="utf-8")


def build_register_doc(src_register, chains) -> dict:
    return {
        "schema": "TOLERANCE_CHAIN_REGISTER_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": CLOCK_SOURCE,
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP3_TOLERANCE_ALLOC",
        "register_role": "enumerates the 14 functional tolerance chains and their functional "
                         "requirements; allocation numbers live in "
                         "TOLERANCE_ALLOCATION_RESULTS_V1.yaml",
        "units": {"length": "mm", "angle": "rad"},
        "chain_count": 14,
        "chains": [
            {
                "chain_id": c["chain_id"], "title": c["title"], "assembly_leg": c["assembly_leg"],
                "predecessor_refs": c["predecessor_refs"], "function": c["function"],
                "functional_requirements": [
                    {"metric": ch["metric"], "unit": ch["unit"],
                     "requirement_type": ch["requirement_type"],
                     "requirement_limit": ch["requirement_limit"],
                     "requirement_class": ch["requirement_class"],
                     "requirement_basis": ch["requirement_basis"]}
                    for ch in c["functional_checks"]
                ] or None,
                "status": c["status"], "closure_note": c["closure_note"],
            }
            for c in chains
        ],
        "chain_set_notes": [
            "Chain set per WP3 charter suggested list; M6 STAGE_A_STAGE_B_AXIAL_SEAT is folded "
            "into M7-TC-02 as the axial functional requirement of the same Stage A/B interface.",
            "M7-TC-13 and M7-TC-14 carry no numeric authority and are FUNCTIONALLY_OPEN with "
            "documented reasons; they are not hard-closed.",
        ],
        "source_register": src_register,
    }


def build_results_doc(src_register, chains) -> dict:
    closed = [c for c in chains if c["status"] == "FUNCTIONALLY_CLOSED_ANALYTIC"]
    opened = [c for c in chains if c["status"] == "FUNCTIONALLY_OPEN"]
    return {
        "schema": "TOLERANCE_ALLOCATION_RESULTS_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": CLOCK_SOURCE,
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP3_TOLERANCE_ALLOC",
        "classification": "ANALYTIC_DESIGN_LEVEL_ALLOCATION_NOT_A_MANUFACTURING_CONFORMITY_PASS",
        "units": {"length": "mm", "angle": "rad"},
        "method": {
            "direction": "REVERSE_ALLOCATION: functional margin -> per-feature allowed tolerances",
            "worst_case": "arithmetic limit stack over allocated ISO 286 fits and process terms; "
                          "WC must satisfy the functional requirement",
            "rss": "root-sum-square of rectangular standard uncertainties (u = half_width/"
                   "sqrt(3)); k=3 bounds reported as reference",
            "zero_fill": "FORBIDDEN_AND_NOT_USED: unknown terms are excluded and listed, never "
                         "set to zero",
            "correlations": "UNCORRELATED_ASSUMPTION (candidate) where required",
            "thermal": "NOT_EVALUATED_NO_APPROVED_CTE_OR_TEMPERATURE_RANGE (terms stay "
                       "excluded/retained-HOLD)",
            "requirement_classes": [
                "INTERFACE_PASS_THROUGH_DESIGN_FLOOR",
                "DESIGN_ALLOCATED_REQUIREMENT",
                "CROSS_CHAIN_DERIVED",
                "GEOMETRIC_DESIGN_FLOOR",
                "CROSS_CHAIN_REFERENCE",
            ],
            "fit_classes": ["CANDIDATE_FIT (ISO 286 grade on frozen nominal)",
                            "PROCESS_CAP_ASSUMED (machining process capability)"],
        },
        "chains": chains,
        "closure_gate": {
            "chain_count": 14,
            "functionally_closed_analytic_count": len(closed),
            "functionally_open_count": len(opened),
            "open_chain_ids": [c["chain_id"] for c in opened],
            "wc_all_checks_pass_in_closed_chains": all(c["wc_overall_pass"] for c in closed),
            "verdict": "12_OF_14_FUNCTIONALLY_CLOSED_ANALYTIC_2_FUNCTIONALLY_OPEN_DOCUMENTED",
        },
        "release_prohibitions_carried": [
            "NO_MANUFACTURING_CONFORMITY_CLAIM_FROM_ANALYTIC_CLOSURE",
            "NO_FIT_OR_INTERFERENCE_FREE_CLAIM_WITHOUT_MEASURED_EVIDENCE",
            "NO_THERMAL_CLEARANCE_CLAIM_WITHOUT_APPROVED_CTE_AND_ENVIRONMENT",
            "NO_FASTENER_PRELOAD_OR_MARGIN_CLAIM",
            "M4_OWNER_EXAMPLE_GRID_NOT_USED_AS_REQUIREMENT",
            "NO_ZERO_FILL_OF_UNKNOWN_TERMS",
        ],
        "source_register": src_register,
    }


def write_results_csv(chains) -> None:
    fields = ["chain_id", "row_kind", "item", "unit", "nominal", "allocated_value",
              "allocation_class", "standard_or_basis", "requirement_limit", "wc_value",
              "wc_margin", "wc_pass", "rss_standard_uncertainty", "rss_k3_bound",
              "rss_k3_pass", "status"]
    rows = []
    for c in chains:
        for ch in c["functional_checks"]:
            rows.append({
                "chain_id": c["chain_id"], "row_kind": "FUNCTIONAL_CHECK",
                "item": ch["metric"], "unit": ch["unit"], "nominal": "",
                "allocated_value": "", "allocation_class": ch["requirement_class"],
                "standard_or_basis": ch["requirement_basis"],
                "requirement_limit": ch["requirement_limit"], "wc_value": ch["wc_value"],
                "wc_margin": ch["wc_margin"], "wc_pass": ch["wc_pass"],
                "rss_standard_uncertainty": ch["rss_standard_uncertainty"],
                "rss_k3_bound": ch["rss_k3_bound"], "rss_k3_pass": ch["rss_k3_pass"],
                "status": c["status"],
            })
        for a in c["reverse_allocation"]:
            rows.append({
                "chain_id": c["chain_id"], "row_kind": "FEATURE_ALLOCATION",
                "item": a["feature"], "unit": a.get("unit", "mm"),
                "nominal": a.get("nominal_mm", ""),
                "allocated_value": a.get("allocated_fit") or a.get("allocated_value"),
                "allocation_class": a["classification"],
                "standard_or_basis": a.get("standard_reference", "") or a.get("notes", ""),
                "requirement_limit": "", "wc_value": "", "wc_margin": "", "wc_pass": "",
                "rss_standard_uncertainty": "", "rss_k3_bound": "", "rss_k3_pass": "",
                "status": c["status"],
            })
    with (WP_DIR / "TOLERANCE_ALLOCATION_RESULTS_V1.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_drawing_scheme_csv(chains) -> None:
    fields = ["row_id", "chain_id", "part_or_assembly", "feature", "tolerance_type",
              "tolerance_value", "unit", "datum_reference", "standard_reference",
              "classification", "notes"]
    part_of = {
        "M7-TC-01": "M3R_STAGE_A / B601_BASE",
        "M7-TC-02": "M3R_STAGE_A + M3R_STAGE_B",
        "M7-TC-03": "M3R_STAGE_A + M3R_STAGE_B",
        "M7-TC-04": "M3R_STAGE_A + M3R_STAGE_B",
        "M7-TC-05": "M3R_STAGE_A + M3R_STAGE_B + CLOCKING_DOWEL",
        "M7-TC-06": "SPACECRAFT_LOAD_BRIDGE + BUS_+X_FACE",
        "M7-TC-07": "SPACECRAFT_LOAD_BRIDGE + M3R_STAGE_B",
        "M7-TC-08": "GRIPPER_R1_PALM + GRIPPER_R1_FINGERS",
        "M7-TC-09": "GRIPPER_R1_PALM + GRIPPER_R1_FINGERS",
        "M7-TC-10": "SOLAR_HINGE_BRACKETS",
        "M7-TC-11": "SOLAR_HINGE_HARD_STOP",
        "M7-TC-12": "HINGE_BRACKET + PANEL_ROOT_FITTING",
        "M7-TC-13": "CAMERA_BRACKET (NO AUTHORIZED GEOMETRY)",
        "M7-TC-14": "ARM_HDRM (ARCHITECTURE NOT SELECTED)",
    }
    rows = []
    idx = 0
    for c in chains:
        for a in c["reverse_allocation"]:
            idx += 1
            rows.append({
                "row_id": f"DTS-{idx:03d}", "chain_id": c["chain_id"],
                "part_or_assembly": part_of[c["chain_id"]],
                "feature": a["feature"], "tolerance_type": a["tolerance_type"],
                "tolerance_value": a.get("allocated_fit") or a.get("allocated_value"),
                "unit": a.get("unit", "mm"), "datum_reference": a["datum_reference"],
                "standard_reference": a.get("standard_reference", ""),
                "classification": a["classification"], "notes": a.get("notes", ""),
            })
    # drawing-default row: general untoleranced dimensions
    idx += 1
    rows.append({
        "row_id": f"DTS-{idx:03d}", "chain_id": "ALL",
        "part_or_assembly": "ALL_M7_PARTS", "feature": "UNTOLERANCED_LINEAR_AND_ANGULAR_DIMS",
        "tolerance_type": "GENERAL_TOLERANCE_DEFAULT", "tolerance_value": "ISO2768-m",
        "unit": "mm", "datum_reference": "PER_PART_DATUM_SCHEME",
        "standard_reference": "ISO 2768-1/-2 medium",
        "classification": "DESIGN_ALLOCATED_REQUIREMENT",
        "notes": "drawing default for dimensions without an explicit allocation row; explicit "
                 "rows above always win",
    })
    with (WP_DIR / "DRAWING_TOLERANCE_SCHEME_V1.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    src_register = verify_inputs()
    chains = [tc01_b601_pattern(), tc02_spigot_axial_seat(), tc03_skirt(), tc04_m5_pattern(),
              tc05_clocking_dowel(), tc06_bridge_bus(), tc07_bridge_stage_b(),
              tc08_gripper_rail_palm(), tc09_gripper_finger_symmetry(), tc10_hinge_coaxiality(),
              tc11_hinge_stop_angle(), tc12_wing_root_position(), tc13_camera_pointing(),
              tc14_hdrm_preload()]
    closed = [c for c in chains if c["status"] == "FUNCTIONALLY_CLOSED_ANALYTIC"]
    for c in closed:
        if not c["wc_overall_pass"]:
            raise SystemExit(f"FAIL-CLOSED: {c['chain_id']} marked closed but a WC check fails")

    write_yaml(WP_DIR / "TOLERANCE_CHAIN_REGISTER_V1.yaml", build_register_doc(src_register, chains))
    write_yaml(WP_DIR / "TOLERANCE_ALLOCATION_RESULTS_V1.yaml", build_results_doc(src_register, chains))
    write_results_csv(chains)
    scheme_rows = write_drawing_scheme_csv(chains)

    outputs = ["TOLERANCE_CHAIN_REGISTER_V1.yaml", "TOLERANCE_ALLOCATION_RESULTS_V1.yaml",
               "TOLERANCE_ALLOCATION_RESULTS_V1.csv", "DRAWING_TOLERANCE_SCHEME_V1.csv"]
    files = []
    for name in outputs:
        path = WP_DIR / name
        files.append({"path": f"{M7_ROOT}/wp3_tolerance_alloc/{name}",
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                      "bytes": path.stat().st_size})
    self_path = Path(__file__).resolve()

    def res(cid, metric):
        ch = next(c for c in chains if c["chain_id"] == cid)
        return next(ch for ch in ch["functional_checks"] if ch["metric"] == metric)

    receipt = {
        "schema": "M7_WP3_TOLERANCE_ALLOC_RECEIPT_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": CLOCK_SOURCE,
        "work_package": "WP3_TOLERANCE_ALLOC",
        "status": "WP3_COMPLETE_12_OF_14_FUNCTIONALLY_CLOSED_ANALYTIC_2_FUNCTIONALLY_OPEN",
        "verdict": "12/14 FUNCTIONALLY_CLOSED_ANALYTIC; M7-TC-13 CAMERA_BRACKET_POINTING and "
                   "M7-TC-14 HDRM_PRELOAD_INTERFACE FUNCTIONALLY_OPEN (no numeric authority; "
                   "reasons documented; not hard-closed)",
        "builder": {"path": f"{M7_ROOT}/wp3_tolerance_alloc/WP3_TOLERANCE_ALLOC_BUILDER_V1.py",
                    "sha256": hashlib.sha256(self_path.read_bytes()).hexdigest().upper(),
                    "bytes": self_path.stat().st_size},
        "produced_files": files,
        "source_register": src_register,
        "numeric_summary": {
            "M7-TC-01_b601_m4_wc_min_radial_clearance_mm":
                res("M7-TC-01", "minimum_radial_clearance")["wc_value"],
            "M7-TC-02_spigot_wc_radial_after_coax_mm":
                res("M7-TC-02", "spigot_minimum_radial_clearance_after_coaxiality")["wc_value"],
            "M7-TC-02_axial_seat_wc_abs_gap_mm":
                res("M7-TC-02", "axial_seating_gap")["wc_value"],
            "M7-TC-03_skirt_wc_radial_after_coax_mm":
                res("M7-TC-03", "skirt_minimum_radial_clearance_after_coaxiality")["wc_value"],
            "M7-TC-04_m5_wc_min_radial_clearance_mm":
                res("M7-TC-04", "m5_minimum_radial_clearance")["wc_value"],
            "M7-TC-05_clocking_wc_rad":
                res("M7-TC-05", "clocking_error")["wc_value"],
            "M7-TC-06_cobore_wc_min_radial_clearance_mm":
                res("M7-TC-06", "cobore_minimum_radial_clearance")["wc_value"],
            "M7-TC-07_m6_wc_min_radial_clearance_mm":
                res("M7-TC-07", "m6_minimum_radial_clearance_both_plates")["wc_value"],
            "M7-TC-07_wc_min_edge_ligament_mm":
                res("M7-TC-07", "edge_ligament_minimum_both_sides")["wc_value"],
            "M7-TC-08_gripper_guarded_clearance_wc_mm":
                res("M7-TC-08", "guarded_minimum_functional_clearance")["wc_value"],
            "M7-TC-09_finger_symmetry_wc_mm":
                res("M7-TC-09", "fingertip_symmetry_error")["wc_value"],
            "M7-TC-10_hinge_coaxiality_wc_rad":
                res("M7-TC-10", "hinge_line_angular_misalignment")["wc_value"],
            "M7-TC-11_deployed_angle_wc_rad":
                res("M7-TC-11", "deployed_angle_deviation")["wc_value"],
            "M7-TC-12_root_position_wc_mm":
                res("M7-TC-12", "wing_root_axis_position_error")["wc_value"],
            "drawing_scheme_rows": scheme_rows,
        },
        "retained_holds": [
            "HOLD_MANUFACTURING_CONFORMITY_CMM_AND_MEASURED_EVIDENCE (all 12 closed chains)",
            "HOLD_THERMAL_STACKS_NO_APPROVED_CTE_OR_TEMPERATURE_RANGE",
            "HOLD_FASTENER_PRELOAD_GRADE_AND_MOS (WP4 PENDING_SIBLING_HASH)",
            "HOLD_HINGE_HARDWARE_NOMINALS_FITS_AND_STOP_GEOMETRY (WP5 PENDING_SIBLING_HASH)",
            "HOLD_GRIPPER_ELASTIC_AND_WEAR_TERMS_REQUIRE_AUTHORIZED_LOAD_AND_LIFE_TEST",
            "STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD (WP7 operational FEA PENDING_SIBLING_HASH)",
            "HOLD_CAMERA_BRACKET_POSE_NO_AUTHORIZED_GEOMETRY (M7-TC-13 open)",
            "HOLD_HDRM_ARCHITECTURE_NOT_SELECTED (M7-TC-14 open)",
            "LAUNCH_QUALIFICATION_FEA_HOLD (ODR-06 retained)",
        ],
        "integration_interfaces": {
            "wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1": "PENDING_SIBLING_HASH",
            "wp1_structure_cad/SUPPORT_AND_BRACKET_CANDIDATES_V1": "PENDING_SIBLING_HASH",
            "wp4_fastener_design/FASTENER_SCHEDULE_V1": "PENDING_SIBLING_HASH",
            "wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V1": "PENDING_SIBLING_HASH",
            "wp5_mechanisms/SOLAR_HINGE_DEPLOYMENT_PACK_V1": "PENDING_SIBLING_HASH",
            "wp5_mechanisms/HDRM_ENGINEERING_PACK_V1": "PENDING_SIBLING_HASH",
            "wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1": "PENDING_SIBLING_HASH",
            "wp7_fea_operational/FEA1_RESULTS_V1": "PENDING_SIBLING_HASH",
            "wp9_release_package/VERIFICATION_MATRIX_V1": "PENDING_SIBLING_HASH",
            "wp9_release_package/INSPECTION_PLAN_V1": "PENDING_SIBLING_HASH",
        },
        "prohibitions_honored": {
            "formal_fea_run_count": 0,
            "freecad_launched": False,
            "abaqus_launched": False,
            "zero_fill_of_unknowns": False,
            "baseline_files_modified": False,
            "l0_urdf_overridden": False,
            "candidate_promoted_to_manufacturing_authority": False,
            "memory_gate_heavy_ops": 0,
        },
    }
    (WP_DIR / "receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print("WP3_TOLERANCE_ALLOC builder complete:")
    for f in files:
        print(f"  {f['path']}  {f['bytes']} B  {f['sha256'][:16]}...")
    print(f"  closed {len(closed)}/14, open {[c['chain_id'] for c in chains if c['status'] == 'FUNCTIONALLY_OPEN']}")


if __name__ == "__main__":
    sys.exit(main())
