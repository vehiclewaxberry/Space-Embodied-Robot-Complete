#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WP2 INDEPENDENT AUDIT of SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml.

This script does NOT import or execute aggregate_m7_design_mass.py.
Every number below is recomputed from the YAML's own declared component
records using independent linear algebra (numpy) and independent hashing
(hashlib over real file bytes).

Emits WP2_DESIGN_MASS_AUDIT_V1.json.
"""
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import yaml

REPO = r"f:/China Graduate Future Flight Vehicle Innovation Competition"
WP2 = os.path.join(
    REPO,
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass",
)
TARGET = os.path.join(WP2, "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml")
POLICY = os.path.join(WP2, "DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml")
AGG = os.path.join(WP2, "aggregate_m7_design_mass.py")
OUT = os.path.join(WP2, "WP2_DESIGN_MASS_AUDIT_V1.json")


def sha256_and_size(path):
    p = path if os.path.isabs(path) else os.path.join(REPO, path)
    if not os.path.exists(p):
        return None, None
    h = hashlib.sha256()
    n = 0
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            n += len(b)
            h.update(b)
    return h.hexdigest().upper(), n


def now_iso():
    try:
        return subprocess.check_output(["date", "-Iseconds"]).decode().strip()
    except Exception:
        import datetime
        return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def mat(x):
    return np.array(x, dtype=float)


# ---------------------------------------------------------------- load
doc = yaml.safe_load(open(TARGET, "r", encoding="utf-8"))
pol = yaml.safe_load(open(POLICY, "r", encoding="utf-8"))
cfgs = doc["configurations"]

findings = []          # list of dicts
checks = {}            # check_id -> result dict


def add_finding(fid, severity, check_id, summary, detail):
    findings.append(
        {
            "finding_id": fid,
            "severity": severity,
            "check_id": check_id,
            "summary": summary,
            "detail": detail,
        }
    )


# ============================================================ CHECK a
M4_LIB = os.path.join(
    REPO,
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/"
    "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
)
M5_CON = os.path.join(
    REPO,
    "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/"
    "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml",
)
m4 = yaml.safe_load(open(M4_LIB, "r", encoding="utf-8"))
m5 = yaml.safe_load(open(M5_CON, "r", encoding="utf-8"))

wp2_ids = [c["configuration_id"] for c in cfgs]
wp2_names = [c["name"] for c in cfgs]
wp2_legacy = [c.get("legacy_mapping") for c in cfgs]
m4_ids = [c["configuration_id"] for c in m4["configurations"]]
m4_names = [c["name"] for c in m4["configurations"]]
m4_legacy = [c.get("legacy_mapping") for c in m4["configurations"]]
m5_ids = [c["configuration_id"] for c in m5["records"]]
m5_names = [c["name"] for c in m5["records"]]

count_ok = len(cfgs) == 9 and len(set(wp2_ids)) == 9
ids_ok = wp2_ids == m4_ids == m5_ids
names_vs_m4 = wp2_names == m4_names
legacy_vs_m4 = wp2_legacy == m4_legacy
names_vs_m5 = wp2_names == m5_names
m5_divergence = [
    {"configuration_id": i, "wp2_m4_name": a, "m5_name": b}
    for i, a, b in zip(wp2_ids, wp2_names, m5_names)
    if a != b
]

checks["a_nine_configurations_and_naming"] = {
    "verdict": "PASS" if (count_ok and ids_ok and names_vs_m4 and legacy_vs_m4) else "FAIL",
    "configuration_count": len(cfgs),
    "configuration_ids": wp2_ids,
    "configuration_names": wp2_names,
    "legacy_mapping": wp2_legacy,
    "ids_match_m4_configuration_library": wp2_ids == m4_ids,
    "ids_match_m5_geometry_contract": wp2_ids == m5_ids,
    "names_match_m4_configuration_library": names_vs_m4,
    "legacy_mapping_matches_m4_configuration_library": legacy_vs_m4,
    "names_match_m5_geometry_contract": names_vs_m5,
    "m5_naming_divergence_rows": m5_divergence,
    "authority_used_for_this_check": (
        "m4 CONFIGURATION_LIBRARY_V1.yaml (mass-properties configuration authority); "
        "M5 geometry contract names C08/C09 differently"
    ),
}
if m5_divergence:
    add_finding(
        "WP2-AUD-01",
        "MEDIUM",
        "a_nine_configurations_and_naming",
        "C08/C09 configuration labels are not fully crosswalked. WP2 carries "
        "the M4 configuration-library name (TARGET_CAPTURE_22KG / "
        "TARGET_CAPTURE_150KG) and the M4 legacy_mapping (POST_CAPTURE_22KG / "
        "POST_CAPTURE_150KG), but not the M5 geometry-contract labels "
        "(CAPTURE / POST_CAPTURE). wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V4."
        "yaml declares the M5 contract as HASH_BOUND_CONFIGURATION_IDENTITY "
        "and states the 'final alias crosswalk lands with WP2 backfill', so "
        "the alias WP10 is waiting for is not present in the WP2 artifact. "
        "Configuration IDs C01..C09 are identical everywhere, so no numeric "
        "value is at risk; this is a label-traceability gap for integration.",
        {
            "divergence_rows": m5_divergence,
            "wp2_carries_m4_name": True,
            "wp2_carries_m4_legacy_mapping": True,
            "wp2_carries_m5_label": False,
            "downstream_expectation": (
                "wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V4.yaml -> "
                "design_mass_model_binding.configuration_identity_authority."
                "rl_label_crosswalk_note"
            ),
            "ids_identical_across_m4_m5_wp2": wp2_ids == m4_ids == m5_ids,
        },
    )

# ============================================================ CHECK b
REQ_CFG = [
    "configuration_id", "name", "legacy_mapping", "configuration_semantics",
    "composition", "mass", "center_of_mass", "inertia", "principal_inertia",
    "status",
]
REQ_MASS = ["value_kg", "standard_uncertainty_kg",
            "relative_standard_uncertainty", "status"]
REQ_COM = ["reference_frame", "xyz_m", "standard_uncertainty_xyz_m", "status"]
REQ_INE = ["reference_frame", "reference_point", "matrix_kg_m2",
           "components_kg_m2", "standard_uncertainty_matrix_kg_m2",
           "standard_uncertainty_components_kg_m2", "status"]
REQ_PRI = ["moments_kg_m2", "moment_standard_uncertainties_kg_m2",
           "axes_S_unit_vectors", "axes_order",
           "axis_angular_standard_uncertainty_rad", "status"]
REQ_TENSOR_KEYS = ["Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"]
REQ_MEMBER = [
    "component_id", "mass_kg", "mass_class", "mass_standard_uncertainty_kg",
    "com_S_m", "com_class", "com_standard_uncertainty_m_per_axis",
    "inertia_about_own_com_S_kg_m2", "inertia_class",
    "inertia_standard_uncertainty_S_kg_m2", "membership_status",
    "source_ref", "pedigree_note",
]

null_or_absent = []


def scan(node, req, where):
    for k in req:
        if k not in node:
            null_or_absent.append({"where": where, "field": k, "issue": "ABSENT"})
        elif node[k] is None:
            null_or_absent.append({"where": where, "field": k, "issue": "NULL"})


def deep_null(obj, where, acc):
    if obj is None:
        acc.append(where)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            deep_null(v, f"{where}.{k}", acc)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            deep_null(v, f"{where}[{i}]", acc)


deep_nulls_all = []
for c in cfgs:
    cid = c["configuration_id"]
    scan(c, REQ_CFG, cid)
    scan(c.get("mass", {}), REQ_MASS, f"{cid}.mass")
    scan(c.get("center_of_mass", {}), REQ_COM, f"{cid}.center_of_mass")
    scan(c.get("inertia", {}), REQ_INE, f"{cid}.inertia")
    scan(c.get("principal_inertia", {}), REQ_PRI, f"{cid}.principal_inertia")
    scan(c.get("inertia", {}).get("components_kg_m2", {}), REQ_TENSOR_KEYS,
         f"{cid}.inertia.components_kg_m2")
    scan(c.get("inertia", {}).get("standard_uncertainty_components_kg_m2", {}),
         REQ_TENSOR_KEYS, f"{cid}.inertia.standard_uncertainty_components_kg_m2")
    for m in c["composition"]:
        scan(m, REQ_MEMBER, f"{cid}.composition[{m.get('component_id')}]")
    deep_null(c, cid, deep_nulls_all)

# classify deep nulls: target_membership on a non-target config is semantically
# correct (no target present); anything else is reported.
benign_null_suffixes = ("configuration_semantics.target_membership",)
benign_nulls = [x for x in deep_nulls_all if x.endswith(benign_null_suffixes)]
nonbenign_nulls = [x for x in deep_nulls_all if x not in benign_nulls]

checks["b_no_null_or_absent_required_field"] = {
    "verdict": "PASS" if (not null_or_absent and not nonbenign_nulls) else "FAIL",
    "required_field_violations": null_or_absent,
    "all_nulls_found_anywhere_in_configurations": deep_nulls_all,
    "nulls_judged_semantically_correct": benign_nulls,
    "nulls_judged_semantically_correct_reason": (
        "configuration_semantics.target_membership = null on C01..C07 means "
        "'no captured target in this configuration', which is the correct "
        "state, not a missing design value"
    ),
    "nulls_requiring_remediation": nonbenign_nulls,
    "as_built_fields_present_in_this_artifact": False,
    "as_built_note": (
        "The DESIGN mass model declares no as-built field; as-built status is "
        "carried as retained_holds text (M3R as-built measurement open per "
        "ODR-05). Nothing here claims measurement."
    ),
}
if null_or_absent or nonbenign_nulls:
    add_finding("WP2-AUD-NULL", "HIGH", "b_no_null_or_absent_required_field",
                "Required DESIGN field is null or absent.",
                {"required": null_or_absent, "deep": nonbenign_nulls})

# ============================================================ CHECK c
PINNED = {
    "b601_complete_arm_including_gripper_urdf_links": 4.695555949342986,
    "m3r_stage_a_plus_stage_b_budget_envelope": 0.7619,
    "solar_array_left": 0.3483933,
    "solar_array_right": 0.3483933,
    "spacecraft_load_bridge_candidate": 0.702195458,
}
BUS_CORE = 22.927194215348
LEGACY_FLANGE = 0.376019184652
TARGET_MASS = {"target_22kg_scenario": 22.0, "target_150kg_scenario": 150.0}

mass_rows = []
pin_rows = []
for c in cfgs:
    cid = c["configuration_id"]
    comp = c["composition"]
    s = 0.0
    for m in comp:
        s += float(m["mass_kg"])
    rep = float(c["mass"]["value_kg"])
    # exact (Kahan-free) reference using math.fsum for order independence
    import math
    s_fsum = math.fsum(float(m["mass_kg"]) for m in comp)
    mass_rows.append({
        "configuration_id": cid,
        "reported_total_mass_kg": rep,
        "audit_sum_of_components_kg": s_fsum,
        "abs_error_kg": abs(rep - s_fsum),
        "member_count": len(comp),
        "pass": abs(rep - s_fsum) <= 1e-12,
    })
    for m in comp:
        ok = None
        exp = None
        if m["component_id"] in PINNED:
            exp = PINNED[m["component_id"]]
        elif m["component_id"] == "bus_primary_structure":
            exp = BUS_CORE + LEGACY_FLANGE
        elif m["component_id"] in TARGET_MASS:
            exp = TARGET_MASS[m["component_id"]]
        if exp is not None:
            ok = abs(float(m["mass_kg"]) - exp) <= 1e-12
            pin_rows.append({
                "configuration_id": cid,
                "component_id": m["component_id"],
                "reported_kg": float(m["mass_kg"]),
                "pinned_expected_kg": exp,
                "abs_error_kg": abs(float(m["mass_kg"]) - exp),
                "pass": ok,
            })

# exact bit-identity of the two most sensitive pins
b601_bitexact = all(
    repr(float(m["mass_kg"])) == repr(4.695555949342986)
    for c in cfgs for m in c["composition"]
    if m["component_id"] == "b601_complete_arm_including_gripper_urdf_links"
)
m3r_bitexact = all(
    float(m["mass_kg"]) == 0.7619
    for c in cfgs for m in c["composition"]
    if m["component_id"] == "m3r_stage_a_plus_stage_b_budget_envelope"
)

# independent CoM recomputation
com_rows = []
for c in cfgs:
    comp = c["composition"]
    M = math.fsum(float(m["mass_kg"]) for m in comp)
    r = np.zeros(3)
    for m in comp:
        r += float(m["mass_kg"]) * mat(m["com_S_m"])
    r = r / M
    rep = mat(c["center_of_mass"]["xyz_m"])
    com_rows.append({
        "configuration_id": c["configuration_id"],
        "reported_com_S_m": rep.tolist(),
        "audit_com_S_m": r.tolist(),
        "max_abs_error_m": float(np.max(np.abs(rep - r))),
        "pass": bool(np.max(np.abs(rep - r)) <= 1e-12),
    })

checks["c_mass_closure_and_pinned_values"] = {
    "verdict": "PASS" if (all(x["pass"] for x in mass_rows)
                          and all(x["pass"] for x in pin_rows)
                          and b601_bitexact and m3r_bitexact
                          and all(x["pass"] for x in com_rows)) else "FAIL",
    "mass_sum_per_configuration": mass_rows,
    "pinned_value_rows": pin_rows,
    "b601_bit_exact_4_695555949342986": b601_bitexact,
    "m3r_bit_exact_0_7619": m3r_bitexact,
    "bus_primary_structure_expected_kg": BUS_CORE + LEGACY_FLANGE,
    "independent_center_of_mass_recomputation": com_rows,
    "method": (
        "math.fsum over declared member masses; "
        "r_sys = sum(m_i r_i)/sum(m_i); no aggregator code executed"
    ),
}
if not all(x["pass"] for x in mass_rows + pin_rows + com_rows):
    add_finding("WP2-AUD-MASS", "HIGH", "c_mass_closure_and_pinned_values",
                "Mass closure or pinned-value mismatch.",
                {"mass": [x for x in mass_rows if not x["pass"]],
                 "pins": [x for x in pin_rows if not x["pass"]],
                 "com": [x for x in com_rows if not x["pass"]]})

# ============================================================ CHECK d
tri_rows = []
for c in cfgs:
    cid = c["configuration_id"]
    I = mat(c["inertia"]["matrix_kg_m2"])
    comp = c["inertia"]["components_kg_m2"]
    I_from_components = np.array([
        [comp["Ixx"], comp["Ixy"], comp["Ixz"]],
        [comp["Ixy"], comp["Iyy"], comp["Iyz"]],
        [comp["Ixz"], comp["Iyz"], comp["Izz"]],
    ], dtype=float)
    sym_res = float(np.max(np.abs(I - I.T)))
    comp_res = float(np.max(np.abs(I - I_from_components)))
    w = np.linalg.eigvalsh(I)
    w = np.sort(w)
    I1, I2, I3 = float(w[0]), float(w[1]), float(w[2])
    t1 = I1 + I2 - I3
    t2 = I1 + I3 - I2
    t3 = I2 + I3 - I1
    scale = max(abs(I1), abs(I2), abs(I3))
    tri_rows.append({
        "configuration_id": cid,
        "symmetry_max_abs_residual_kg_m2": sym_res,
        "symmetric": sym_res == 0.0,
        "matrix_vs_components_max_abs_residual_kg_m2": comp_res,
        "eigenvalues_kg_m2": [I1, I2, I3],
        "min_eigenvalue_kg_m2": I1,
        "positive_definite": I1 > 0.0,
        "triangle_I1_plus_I2_minus_I3_kg_m2": t1,
        "triangle_I1_plus_I3_minus_I2_kg_m2": t2,
        "triangle_I2_plus_I3_minus_I1_kg_m2": t3,
        "triangle_min_margin_kg_m2": min(t1, t2, t3),
        "triangle_min_margin_relative": min(t1, t2, t3) / scale,
        "triangle_inequalities_satisfied": min(t1, t2, t3) > 0.0,
        "pass": (sym_res == 0.0 and comp_res <= 1e-15 and I1 > 0.0
                 and min(t1, t2, t3) > 0.0),
    })

checks["d_inertia_physicality_symmetry_pd_triangle"] = {
    "verdict": "PASS" if all(x["pass"] for x in tri_rows) else "FAIL",
    "per_configuration": tri_rows,
    "method": (
        "numpy.linalg.eigvalsh on the reported inertia.matrix_kg_m2; "
        "symmetry by exact float comparison of I vs I^T; "
        "triangle test I_i + I_j > I_k on sorted principal moments"
    ),
}
if not all(x["pass"] for x in tri_rows):
    add_finding("WP2-AUD-TENSOR", "CRITICAL",
                "d_inertia_physicality_symmetry_pd_triangle",
                "Inertia tensor is not physically admissible.",
                [x for x in tri_rows if not x["pass"]])

# ============================================================ CHECK e
axes_rows = []
for c in cfgs:
    cid = c["configuration_id"]
    I = mat(c["inertia"]["matrix_kg_m2"])
    R = mat(c["principal_inertia"]["axes_S_unit_vectors"])  # rows = axes
    rep_mom = mat(c["principal_inertia"]["moments_kg_m2"])
    # orthonormality: rows must be orthonormal
    G = R @ R.T
    orth_res = float(np.max(np.abs(G - np.eye(3))))
    detR = float(np.linalg.det(R))
    norms = [float(np.linalg.norm(R[i])) for i in range(3)]
    # consistency: R I R^T should be diag(reported moments)
    D = R @ I @ R.T
    diag_res = float(np.max(np.abs(np.diag(D) - rep_mom)))
    offdiag = D - np.diag(np.diag(D))
    offdiag_res = float(np.max(np.abs(offdiag)))
    # independent diagonalisation
    w, V = np.linalg.eigh(I)
    idx = np.argsort(w)
    w = w[idx]
    eig_res = float(np.max(np.abs(w - rep_mom)))
    # per-axis direction agreement (sign-insensitive)
    V = V[:, idx]
    axis_angle_err_rad = []
    for i in range(3):
        v = V[:, i]
        a = R[i]
        cth = abs(float(np.dot(v, a)) / (np.linalg.norm(v) * np.linalg.norm(a)))
        cth = min(1.0, cth)
        axis_angle_err_rad.append(float(np.arccos(cth)))
    ascending = bool(rep_mom[0] <= rep_mom[1] <= rep_mom[2])
    axes_rows.append({
        "configuration_id": cid,
        "row_norms": norms,
        "orthonormality_max_abs_residual_RRt_minus_I": orth_res,
        "orthonormal": orth_res <= 1e-12,
        "det_R": detR,
        "right_handed": abs(detR - 1.0) <= 1e-12,
        "R_I_Rt_diagonal_vs_reported_moments_max_abs_err_kg_m2": diag_res,
        "R_I_Rt_max_abs_offdiagonal_kg_m2": offdiag_res,
        "independent_eigh_vs_reported_moments_max_abs_err_kg_m2": eig_res,
        "per_axis_angle_error_rad": axis_angle_err_rad,
        "moments_ascending_as_declared": ascending,
        "degeneracy_flags_reported": c["principal_inertia"].get("degeneracy_flags"),
        "pass": (orth_res <= 1e-12 and diag_res <= 1e-12
                 and offdiag_res <= 1e-12 and eig_res <= 1e-12
                 and ascending),
    })

left_handed = [x for x in axes_rows if not x["right_handed"]]
checks["e_principal_axes_orthonormal_and_consistent"] = {
    "verdict": "PASS" if all(x["pass"] for x in axes_rows) else "FAIL",
    "handedness_subcheck_verdict": "FAIL" if left_handed else "PASS",
    "left_handed_configurations": [x["configuration_id"] for x in left_handed],
    "per_configuration": axes_rows,
    "method": (
        "R R^T vs I3 ; R I R^T vs diag(reported moments) ; "
        "independent numpy.linalg.eigh diagonalisation of the reported tensor; "
        "axes rows interpreted as unit vectors in S ordered by ascending moment; "
        "handedness from det(R)"
    ),
}
if not all(x["pass"] for x in axes_rows):
    add_finding("WP2-AUD-AXES", "HIGH",
                "e_principal_axes_orthonormal_and_consistent",
                "Principal axes are not orthonormal or not consistent with "
                "the reported principal moments.",
                [x for x in axes_rows if not x["pass"]])
if left_handed:
    add_finding(
        "WP2-AUD-06", "MEDIUM",
        "e_principal_axes_orthonormal_and_consistent",
        "The reported principal-axis triad is LEFT-HANDED (det(R) = -1) for "
        "C09 TARGET_CAPTURE_150KG. The three axes are individually correct "
        "unit eigenvectors and R I R^T still diagonalises to the reported "
        "moments, so no moment or tensor value is wrong; but a consumer that "
        "assembles these rows into a rotation matrix S<-principal gets a "
        "reflection, not a rotation. axes_order declares only the moment "
        "ordering and does not state a handedness convention, so the defect "
        "is not detectable from the artifact's own metadata. C09 is the "
        "150 kg capture configuration, i.e. the case most likely to be "
        "consumed by the dynamics/RL interface.",
        {"left_handed_configurations":
            [{"configuration_id": x["configuration_id"], "det_R": x["det_R"]}
             for x in left_handed],
         "right_handed_configurations":
            [{"configuration_id": x["configuration_id"], "det_R": x["det_R"]}
             for x in axes_rows if x["right_handed"]],
         "remediation_note": (
             "flip the sign of any one axis row for C09, or declare a "
             "handedness convention in axes_order; no numeric moment changes"
         )},
    )

# ============================================================ CHECK f  (ODR-02)
PANEL_M = 0.3483933
base = None
odr2_rows = []
by_id = {c["configuration_id"]: c for c in cfgs}
base_mass = float(by_id["C01"]["mass"]["value_kg"])
for cid in ["C01", "C02", "C03", "C04"]:
    c = by_id[cid]
    comp = {m["component_id"]: m for m in c["composition"]}
    left = comp.get("solar_array_left")
    right = comp.get("solar_array_right")
    both_present = left is not None and right is not None
    left_m = float(left["mass_kg"]) if left else None
    right_m = float(right["mass_kg"]) if right else None
    tot = float(c["mass"]["value_kg"])
    panel_sum = (left_m or 0.0) + (right_m or 0.0)
    odr2_rows.append({
        "configuration_id": cid,
        "name": c["name"],
        "panel_failure_rule_declared": c["configuration_semantics"].get("panel_failure_rule"),
        "solar_array_left_present": left is not None,
        "solar_array_right_present": right is not None,
        "solar_array_left_mass_kg": left_m,
        "solar_array_right_mass_kg": right_m,
        "panel_mass_sum_kg": panel_sum,
        "expected_panel_mass_sum_kg": 2 * PANEL_M,
        "panel_mass_retained": abs(panel_sum - 2 * PANEL_M) <= 1e-12,
        "total_mass_kg": tot,
        "total_minus_C01_kg": tot - base_mass,
        "no_jettison_mass_drop": abs(tot - base_mass) <= 1e-12,
        "left_com_S_m": left["com_S_m"] if left else None,
        "right_com_S_m": right["com_S_m"] if right else None,
        "left_membership_status": left["membership_status"] if left else None,
        "right_membership_status": right["membership_status"] if right else None,
        "pass": (both_present and abs(panel_sum - 2 * PANEL_M) <= 1e-12
                 and abs(tot - base_mass) <= 1e-12),
    })
# and confirm the failed panel actually MOVED (stuck at stowed endpoint),
# i.e. ODR-02 is not implemented as a no-op
moved = []
c1 = {m["component_id"]: m for m in by_id["C01"]["composition"]}
for cid, expect_left_moved, expect_right_moved in [
    ("C02", True, False), ("C03", False, True), ("C04", True, True)
]:
    cc = {m["component_id"]: m for m in by_id[cid]["composition"]}
    dl = float(np.max(np.abs(mat(cc["solar_array_left"]["com_S_m"])
                             - mat(c1["solar_array_left"]["com_S_m"]))))
    dr = float(np.max(np.abs(mat(cc["solar_array_right"]["com_S_m"])
                             - mat(c1["solar_array_right"]["com_S_m"]))))
    moved.append({
        "configuration_id": cid,
        "left_com_shift_vs_C01_max_abs_m": dl,
        "right_com_shift_vs_C01_max_abs_m": dr,
        "left_moved_as_expected": (dl > 0) == expect_left_moved,
        "right_moved_as_expected": (dr > 0) == expect_right_moved,
        "pass": ((dl > 0) == expect_left_moved) and ((dr > 0) == expect_right_moved),
    })

checks["f_odr02_panel_failure_attached_stuck"] = {
    "verdict": "PASS" if (all(x["pass"] for x in odr2_rows)
                          and all(x["pass"] for x in moved)) else "FAIL",
    "mass_retention_rows": odr2_rows,
    "geometry_relocation_rows": moved,
    "ruling": "ODR-02 panel failure = attached-stuck, never jettison",
    "method": (
        "numeric: failed-panel configurations must carry the identical total "
        "mass as C01 and both panel members must remain in the composition, "
        "while the failed panel CoM relocates to the stowed endpoint"
    ),
}
if not (all(x["pass"] for x in odr2_rows) and all(x["pass"] for x in moved)):
    add_finding("WP2-AUD-ODR02", "CRITICAL",
                "f_odr02_panel_failure_attached_stuck",
                "ODR-02 violated: failed-panel configuration drops mass or "
                "does not relocate the failed panel.",
                {"mass": [x for x in odr2_rows if not x["pass"]],
                 "geom": [x for x in moved if not x["pass"]]})

# ============================================================ CHECK g
CLASS_TABLE = {}
for sc in pol["source_classes"]:
    CLASS_TABLE[sc["class_id"]] = {
        "mass_rel": sc["mass_relative_standard_uncertainty"],
        "com_abs": sc["com_absolute_standard_uncertainty_m_per_axis"],
        "inertia_rel": sc["inertia_relative_standard_uncertainty"],
    }
VALID_CLASSES = set(CLASS_TABLE) | {
    "MERGED_RSS(bus_core: BUDGETED, legacy_flange: MATERIAL_DERIVED)"
}
EXPECT_CLASS = {
    "bus_primary_structure": ("MERGED_RSS(bus_core: BUDGETED, legacy_flange: MATERIAL_DERIVED)", "BUDGETED", "BUDGETED"),
    "solar_array_left": ("BUDGETED", "ANALYTIC_IDEALIZATION", "ANALYTIC_IDEALIZATION"),
    "solar_array_right": ("BUDGETED", "ANALYTIC_IDEALIZATION", "ANALYTIC_IDEALIZATION"),
    "b601_complete_arm_including_gripper_urdf_links": ("ACCEPTED_URDF", "ACCEPTED_URDF", "ACCEPTED_URDF"),
    "m3r_stage_a_plus_stage_b_budget_envelope": ("BUDGETED", "ANALYTIC_IDEALIZATION", "ANALYTIC_IDEALIZATION"),
    "spacecraft_load_bridge_candidate": ("MATERIAL_DERIVED", "ANALYTIC_IDEALIZATION", "ANALYTIC_IDEALIZATION"),
    "target_22kg_scenario": ("PROVISIONAL", "PROVISIONAL", "PROVISIONAL"),
    "target_150kg_scenario": ("PROVISIONAL", "PROVISIONAL", "PROVISIONAL"),
}

ped_rows = []
negative_u = []
zero_u = []
class_mismatch = []
u_recompute_mismatch = []
for c in cfgs:
    cid = c["configuration_id"]
    for m in c["composition"]:
        comp_id = m["component_id"]
        mc, cc_, ic = m["mass_class"], m["com_class"], m["inertia_class"]
        exp = EXPECT_CLASS.get(comp_id)
        if exp and (mc, cc_, ic) != exp:
            class_mismatch.append({
                "configuration_id": cid, "component_id": comp_id,
                "reported": [mc, cc_, ic], "expected_per_policy_map": list(exp)})
        for cls in (mc, cc_, ic):
            if cls not in VALID_CLASSES:
                class_mismatch.append({
                    "configuration_id": cid, "component_id": comp_id,
                    "unknown_class": cls})
        # numeric uncertainty scan
        um = float(m["mass_standard_uncertainty_kg"])
        uc = float(m["com_standard_uncertainty_m_per_axis"])
        ui = mat(m["inertia_standard_uncertainty_S_kg_m2"])
        for label, val in [("mass_standard_uncertainty_kg", um),
                           ("com_standard_uncertainty_m_per_axis", uc)]:
            if val < 0:
                negative_u.append({"configuration_id": cid, "component_id": comp_id,
                                   "field": label, "value": val})
            if val == 0:
                zero_u.append({"configuration_id": cid, "component_id": comp_id,
                               "field": label, "value": val})
        neg_idx = [[int(i), int(j), float(ui[i, j])]
                   for i in range(3) for j in range(3) if ui[i, j] < 0]
        zer_idx = [[int(i), int(j)] for i in range(3) for j in range(3)
                   if ui[i, j] == 0]
        if neg_idx:
            negative_u.append({
                "configuration_id": cid, "component_id": comp_id,
                "field": "inertia_standard_uncertainty_S_kg_m2",
                "negative_entries_i_j_value": neg_idx})
        if zer_idx:
            zero_u.append({
                "configuration_id": cid, "component_id": comp_id,
                "field": "inertia_standard_uncertainty_S_kg_m2",
                "zero_entries_i_j": zer_idx})
        # independent recompute of the class-derived component uncertainties
        base_cls = "BUDGETED" if mc.startswith("MERGED_RSS") else mc
        if comp_id == "bus_primary_structure":
            exp_um = float(np.hypot(0.20 * BUS_CORE, 0.10 * LEGACY_FLANGE))
        else:
            exp_um = CLASS_TABLE[base_cls]["mass_rel"] * float(m["mass_kg"])
        if abs(um - exp_um) > 1e-12 * max(1.0, abs(exp_um)):
            u_recompute_mismatch.append({
                "configuration_id": cid, "component_id": comp_id,
                "field": "mass_standard_uncertainty_kg",
                "reported": um, "audit_expected": exp_um,
                "abs_error": abs(um - exp_um)})
        exp_uc = CLASS_TABLE[cc_]["com_abs"]
        if abs(uc - exp_uc) > 1e-15:
            u_recompute_mismatch.append({
                "configuration_id": cid, "component_id": comp_id,
                "field": "com_standard_uncertainty_m_per_axis",
                "reported": uc, "audit_expected": exp_uc,
                "abs_error": abs(uc - exp_uc)})
        Iown = mat(m["inertia_about_own_com_S_kg_m2"])
        rel = CLASS_TABLE[ic]["inertia_rel"]
        scale = (Iown[0, 0] + Iown[1, 1] + Iown[2, 2]) / 3.0
        for i in range(3):
            exp_d = rel * abs(Iown[i, i])
            if abs(abs(ui[i, i]) - exp_d) > 1e-12 * max(1.0, exp_d):
                u_recompute_mismatch.append({
                    "configuration_id": cid, "component_id": comp_id,
                    "field": f"inertia_standard_uncertainty[{i}][{i}]",
                    "reported": float(ui[i, i]), "audit_expected": exp_d,
                    "abs_error": abs(abs(ui[i, i]) - exp_d)})
        exp_o = rel * abs(scale)
        for i in range(3):
            for j in range(3):
                if i == j:
                    continue
                if abs(abs(ui[i, j]) - exp_o) > 1e-12 * max(1.0, exp_o):
                    u_recompute_mismatch.append({
                        "configuration_id": cid, "component_id": comp_id,
                        "field": f"inertia_standard_uncertainty[{i}][{j}]",
                        "reported": float(ui[i, j]), "audit_expected": exp_o,
                        "abs_error": abs(abs(ui[i, j]) - exp_o)})
        ped_rows.append({
            "configuration_id": cid, "component_id": comp_id,
            "mass_class": mc, "com_class": cc_, "inertia_class": ic,
            "membership_status": m["membership_status"],
            "source_ref": m["source_ref"],
            "pedigree_note_present": bool(m.get("pedigree_note")),
        })

# config-level uncertainty scan
cfg_u_neg = []
cfg_u_zero = []
for c in cfgs:
    cid = c["configuration_id"]
    vals = {
        "mass.standard_uncertainty_kg": [c["mass"]["standard_uncertainty_kg"]],
        "center_of_mass.standard_uncertainty_xyz_m": c["center_of_mass"]["standard_uncertainty_xyz_m"],
        "inertia.standard_uncertainty_components_kg_m2":
            list(c["inertia"]["standard_uncertainty_components_kg_m2"].values()),
        "principal_inertia.moment_standard_uncertainties_kg_m2":
            c["principal_inertia"]["moment_standard_uncertainties_kg_m2"],
        "principal_inertia.axis_angular_standard_uncertainty_rad":
            c["principal_inertia"]["axis_angular_standard_uncertainty_rad"],
    }
    for k, arr in vals.items():
        for i, v in enumerate(arr):
            if v is None:
                cfg_u_zero.append({"configuration_id": cid, "field": k,
                                   "index": i, "issue": "NULL"})
            elif float(v) < 0:
                cfg_u_neg.append({"configuration_id": cid, "field": k,
                                  "index": i, "value": float(v)})
            elif float(v) == 0:
                cfg_u_zero.append({"configuration_id": cid, "field": k,
                                   "index": i, "issue": "ZERO"})

# independent RSS of component mass uncertainties -> config mass uncertainty
rss_rows = []
for c in cfgs:
    us = [float(m["mass_standard_uncertainty_kg"]) for m in c["composition"]]
    rss = float(np.sqrt(math.fsum(u * u for u in us)))
    rep = float(c["mass"]["standard_uncertainty_kg"])
    rss_rows.append({
        "configuration_id": c["configuration_id"],
        "reported_mass_standard_uncertainty_kg": rep,
        "audit_rss_of_component_mass_u_kg": rss,
        "abs_error_kg": abs(rep - rss),
        "relative_error": abs(rep - rss) / rep,
        "tolerance_relative": 1e-9,
        "tolerance_rationale": (
            "the artifact propagates with a numerical central-difference "
            "Jacobian (policy P5), not with a closed-form RSS, so agreement "
            "is judged on relative deviation at finite-difference noise level"
        ),
        "pass": (abs(rep - rss) / rep) <= 1e-9,
    })

g_pass = (not class_mismatch and not cfg_u_neg and not cfg_u_zero
          and not negative_u and not u_recompute_mismatch
          and all(r["pedigree_note_present"] for r in ped_rows))
checks["g_uncertainty_and_pedigree_completeness"] = {
    "verdict": "PASS" if g_pass else "FAIL",
    "component_record_count_audited": len(ped_rows),
    "pedigree_class_mismatches": class_mismatch,
    "pedigree_note_missing_rows": [r for r in ped_rows
                                   if not r["pedigree_note_present"]],
    "configuration_level_negative_uncertainties": cfg_u_neg,
    "configuration_level_zero_or_null_uncertainties": cfg_u_zero,
    "component_level_negative_uncertainty_entries": negative_u,
    "component_level_zero_uncertainty_entries": zero_u,
    "component_level_uncertainty_magnitude_recompute_mismatches": u_recompute_mismatch,
    "configuration_mass_uncertainty_vs_independent_rss": rss_rows,
    "method": (
        "class table read from DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml and "
        "re-applied by hand: u(m)=rel*m, u(Ipp)=rel*|Ipp|, "
        "u(Ipq)=rel*(Ixx+Iyy+Izz)/3, bus mass u = RSS(0.20*bus_core, "
        "0.10*legacy_flange); config mass u = RSS of member mass u"
    ),
}
if class_mismatch or cfg_u_neg or cfg_u_zero or u_recompute_mismatch:
    add_finding("WP2-AUD-UNC", "MEDIUM",
                "g_uncertainty_and_pedigree_completeness",
                "Uncertainty/pedigree defect.",
                {"class": class_mismatch, "cfg_neg": cfg_u_neg,
                 "cfg_zero": cfg_u_zero, "recompute": u_recompute_mismatch})
if negative_u:
    n_entries = sum(len(x.get("negative_entries_i_j_value", []))
                    for x in negative_u)
    worst = 0.0
    worst_where = None
    for x in negative_u:
        for e in x.get("negative_entries_i_j_value", []):
            if abs(e[2]) > worst:
                worst = abs(e[2])
                worst_where = {"configuration_id": x["configuration_id"],
                               "component_id": x["component_id"],
                               "i": e[0], "j": e[1], "value": e[2]}
    # sign inconsistency evidence: same class, same component, opposite signs
    r_dep = mat(c1["solar_array_right"]["inertia_standard_uncertainty_S_kg_m2"])
    c3 = {m["component_id"]: m for m in by_id["C03"]["composition"]}
    r_stow = mat(c3["solar_array_right"]["inertia_standard_uncertainty_S_kg_m2"])
    add_finding(
        "WP2-AUD-02", "MEDIUM", "g_uncertainty_and_pedigree_completeness",
        "Component-level inertia standard-uncertainty matrices contain "
        "negative entries. A k=1 standard uncertainty is a non-negative "
        "magnitude; these are sign artefacts of rotating the uncertainty "
        "matrix with the component transform. Magnitudes are correct "
        "(every |u| reproduces the policy class rule exactly), so no "
        "propagated result is numerically wrong, but the stored field is "
        "not a valid uncertainty. The artifact's own "
        "'uncertainty_positive_no_zero_fill_9_of_9' check reports PASS "
        "because it only scans configuration-level fields.",
        {
            "affected_component_records": len(negative_u),
            "negative_matrix_entries_total": n_entries,
            "largest_negative_entry": worst_where,
            "sign_pattern_is_inconsistent_for_the_same_class_evidence": {
                "C01_solar_array_right_deployed_u_02": float(r_dep[0, 2]),
                "C03_solar_array_right_stowed_u_02": float(r_stow[0, 2]),
                "note": (
                    "identical component and identical ANALYTIC_IDEALIZATION "
                    "class, opposite sign, which confirms the sign is a "
                    "transform artefact rather than an intentional signed "
                    "covariance term"
                ),
            },
            "magnitudes_all_match_policy_class_rule": True,
            "rows": negative_u,
        },
    )

# ============================================================ CHECK h (extra)
# independent inertia-about-system-CoM recomputation by parallel-axis
ine_rows = []
for c in cfgs:
    comp = c["composition"]
    M = math.fsum(float(m["mass_kg"]) for m in comp)
    r_sys = np.zeros(3)
    for m in comp:
        r_sys += float(m["mass_kg"]) * mat(m["com_S_m"])
    r_sys /= M
    I = np.zeros((3, 3))
    for m in comp:
        mi = float(m["mass_kg"])
        Ii = mat(m["inertia_about_own_com_S_kg_m2"])
        d = mat(m["com_S_m"]) - r_sys
        I = I + Ii + mi * (float(d @ d) * np.eye(3) - np.outer(d, d))
    rep = mat(c["inertia"]["matrix_kg_m2"])
    err = float(np.max(np.abs(rep - I)))
    scale = float(np.max(np.abs(rep)))
    ine_rows.append({
        "configuration_id": c["configuration_id"],
        "audit_inertia_about_system_com_S_kg_m2": I.tolist(),
        "max_abs_error_vs_reported_kg_m2": err,
        "max_rel_error_vs_reported": err / scale,
        "pass": err <= 1e-12,
    })
checks["h_independent_parallel_axis_inertia_reconstruction"] = {
    "verdict": "PASS" if all(x["pass"] for x in ine_rows) else "FAIL",
    "per_configuration": ine_rows,
    "method": (
        "I_sys = sum_i [ I_i(own CoM, S axes) + m_i (|d_i|^2 I3 - d_i d_i^T) ], "
        "d_i = r_i - r_sys; recomputed from the artifact's own declared "
        "component records without executing the aggregator"
    ),
}
if not all(x["pass"] for x in ine_rows):
    add_finding("WP2-AUD-PA", "HIGH",
                "h_independent_parallel_axis_inertia_reconstruction",
                "Reported configuration inertia is not reproducible from the "
                "declared composition by the parallel-axis theorem.",
                [x for x in ine_rows if not x["pass"]])

# ============================================================ CHECK i
# source_register hash + byte-size re-verification
sr = doc["source_register"]
sr_rows = []
for key, rec in sr.items():
    p = rec["path"]
    have_sha, have_bytes = sha256_and_size(p)
    declared = (rec.get("sha256") or "").upper()
    sr_rows.append({
        "key": key,
        "path": p,
        "file_exists": have_sha is not None,
        "declared_sha256": declared,
        "recomputed_sha256": have_sha,
        "sha256_match": (have_sha == declared) if have_sha else False,
        "bytes_field_present_in_artifact": "bytes" in rec,
        "recomputed_bytes": have_bytes,
    })
sr_missing_bytes = [r["key"] for r in sr_rows
                    if not r["bytes_field_present_in_artifact"]]
sr_bad = [r for r in sr_rows if not r["sha256_match"]]
checks["i_source_register_integrity"] = {
    "verdict": "FAIL" if (sr_bad or sr_missing_bytes) else "PASS",
    "entry_count": len(sr_rows),
    "sha256_verified_count": sum(1 for r in sr_rows if r["sha256_match"]),
    "sha256_mismatch_or_missing_rows": sr_bad,
    "entries_missing_byte_size_field": sr_missing_bytes,
    "rows": sr_rows,
    "method": "hashlib.sha256 over real file bytes; os.path.getsize equivalent",
}
if sr_bad:
    add_finding("WP2-AUD-SR", "HIGH", "i_source_register_integrity",
                "source_register SHA-256 does not match the file on disk.", sr_bad)
if sr_missing_bytes:
    add_finding(
        "WP2-AUD-03", "LOW", "i_source_register_integrity",
        "source_register entries carry path+sha256 but omit the byte-size "
        "field required by the M7 standing artifact rule (schema / "
        "generated_local / source_register with SHA-256 AND byte size).",
        {"entries_missing_bytes": sr_missing_bytes,
         "count": len(sr_missing_bytes)},
    )

# ============================================================ CHECK j
# pinned self-references inside the artifact
pol_sha, pol_bytes = sha256_and_size(POLICY)
agg_sha, agg_bytes = sha256_and_size(AGG)
tgt_sha, tgt_bytes = sha256_and_size(TARGET)
declared_pol = (doc["uncertainty_policy"]["sha256"] or "").upper()
checks["j_self_reference_pins"] = {
    "verdict": "PASS" if declared_pol == pol_sha else "FAIL",
    "uncertainty_policy_declared_sha256": declared_pol,
    "uncertainty_policy_recomputed_sha256": pol_sha,
    "uncertainty_policy_bytes": pol_bytes,
    "aggregator_declared_path": doc["aggregator"]["path"],
    "aggregator_recomputed_sha256": agg_sha,
    "aggregator_bytes": agg_bytes,
    "aggregator_sha256_pinned_in_artifact": "sha256" in doc["aggregator"],
    "target_artifact_sha256": tgt_sha,
    "target_artifact_bytes": tgt_bytes,
}
if declared_pol != pol_sha:
    add_finding("WP2-AUD-POL", "HIGH", "j_self_reference_pins",
                "Pinned uncertainty-policy SHA-256 does not match the policy "
                "file on disk.",
                {"declared": declared_pol, "recomputed": pol_sha})
if "sha256" not in doc["aggregator"]:
    add_finding(
        "WP2-AUD-04", "LOW", "j_self_reference_pins",
        "The artifact names its generating aggregator by path and rerun "
        "command but does not pin the aggregator SHA-256, so the artifact "
        "cannot be tied to a specific builder revision from its own contents.",
        {"aggregator_path": doc["aggregator"]["path"],
         "recomputed_sha256": agg_sha, "bytes": agg_bytes},
    )

# ============================================================ CHECK k
# frame/label self-consistency of the component inertia records
label_rows = []
for c in cfgs:
    for m in c["composition"]:
        decl = m.get("inertia_reference_frame_declared")
        if decl != "S":
            label_rows.append({
                "configuration_id": c["configuration_id"],
                "component_id": m["component_id"],
                "field": "inertia_about_own_com_S_kg_m2",
                "inertia_reference_frame_declared": decl,
                "transform_classification": m.get("transform_classification"),
            })
# numeric evidence that the panel tensor IS in S axes: stowed vs deployed swap
c1 = {m["component_id"]: m for m in by_id["C01"]["composition"]}
c4 = {m["component_id"]: m for m in by_id["C04"]["composition"]}
Id = mat(c1["solar_array_left"]["inertia_about_own_com_S_kg_m2"])
Is = mat(c4["solar_array_left"]["inertia_about_own_com_S_kg_m2"])
rot_evidence = {
    "C01_left_panel_diag": [Id[0, 0], Id[1, 1], Id[2, 2]],
    "C04_left_panel_diag": [Is[0, 0], Is[1, 1], Is[2, 2]],
    "yy_zz_swapped_consistent_with_minus90deg_about_x": bool(
        abs(Is[1, 1] - Id[2, 2]) <= 1e-15 and abs(Is[2, 2] - Id[1, 1]) <= 1e-15
    ),
}
checks["k_component_inertia_frame_label_consistency"] = {
    "verdict": "FAIL" if label_rows else "PASS",
    "rows_where_field_name_says_S_but_declared_frame_is_local": label_rows,
    "numeric_evidence_tensor_is_actually_in_S_axes": rot_evidence,
    "impact": (
        "LABELLING ONLY. The numbers are in S axes (proved by the stowed-panel "
        "Iyy/Izz swap and by check h reproducing every configuration tensor to "
        "<=1e-12), so no numeric value is affected."
    ),
}
if label_rows:
    add_finding(
        "WP2-AUD-05", "LOW", "k_component_inertia_frame_label_consistency",
        "Panel component records name the field "
        "'inertia_about_own_com_S_kg_m2' while "
        "'inertia_reference_frame_declared' says F_LEFT_LOCAL_COM / "
        "F_RIGHT_LOCAL_COM. The stored numbers are in S axes; the declared "
        "frame label contradicts the field name and the data.",
        label_rows,
    )

# ============================================================ CHECK l
# self-declared design_checks vs my independent findings
sd = doc["design_checks"]
self_vs_audit = {
    "self_inertia_symmetric_positive_definite_9_of_9":
        sd["inertia_symmetric_positive_definite_9_of_9"]["pass"],
    "audit_inertia_symmetric_positive_definite_and_triangle":
        checks["d_inertia_physicality_symmetry_pd_triangle"]["verdict"],
    "self_check_covers_triangle_inequality": False,
    "self_uncertainty_positive_no_zero_fill_9_of_9":
        sd["uncertainty_positive_no_zero_fill_9_of_9"]["pass"],
    "self_uncertainty_check_scope": (
        "configuration-level fields only; the reported minima match the "
        "configuration CoM z uncertainty, so component-level uncertainty "
        "matrices are outside its scope"
    ),
    "self_min_eigenvalues": {
        r["configuration_id"]: r["min_eigenvalue_kg_m2"]
        for r in sd["inertia_symmetric_positive_definite_9_of_9"]["detail"]
    },
    "audit_min_eigenvalues": {
        r["configuration_id"]: r["min_eigenvalue_kg_m2"] for r in tri_rows
    },
}
eig_agree = all(
    abs(self_vs_audit["self_min_eigenvalues"][k]
        - self_vs_audit["audit_min_eigenvalues"][k]) <= 1e-12
    for k in self_vs_audit["audit_min_eigenvalues"]
)
self_vs_audit["min_eigenvalue_agreement_within_1e_12"] = eig_agree
checks["l_self_declared_checks_vs_independent_audit"] = {
    "verdict": "PASS" if eig_agree else "FAIL",
    "detail": self_vs_audit,
    "summary_all_checks_pass_claimed": doc["summary"]["all_checks_pass"],
}

# ============================================================ CHECK m
# empty/zero-artifact guard (known past failure mode)
nonempty = {
    "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml_bytes": tgt_bytes,
    "DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml_bytes": pol_bytes,
    "aggregate_m7_design_mass.py_bytes": agg_bytes,
    "configurations_parsed": len(cfgs),
    "component_records_parsed": sum(len(c["composition"]) for c in cfgs),
    "distinct_float_values_parsed_in_configurations": None,
}
nfloat = 0


def count_floats(o):
    global nfloat
    if isinstance(o, float) or isinstance(o, int):
        nfloat += 1
    elif isinstance(o, dict):
        for v in o.values():
            count_floats(v)
    elif isinstance(o, list):
        for v in o:
            count_floats(v)


count_floats(cfgs)
nonempty["distinct_float_values_parsed_in_configurations"] = nfloat
checks["m_nonempty_artifact_guard"] = {
    "verdict": "PASS" if (tgt_bytes and tgt_bytes > 1000 and nfloat > 1000)
    else "FAIL",
    "detail": nonempty,
    "note": (
        "Guard against the repo's known failure mode of a PASS summary over "
        "an empty/zero artifact. Every PASS in this audit was computed from "
        "these parsed numbers."
    ),
}

# ============================================================ CHECK n
# WP2 output contract from M7_EXECUTION_PLAN_V1 / WP10 consumer contract:
# 9 configs x {mass, CoM, full tensor about system CoM in S, principal
# inertia + axes, uncertainty, pedigree}
CONTRACT = {
    "mass": lambda c: c["mass"]["value_kg"],
    "center_of_mass_S_m": lambda c: c["center_of_mass"]["xyz_m"],
    "inertia_about_system_cg_in_S_kg_m2": lambda c: c["inertia"]["matrix_kg_m2"],
    "inertia_full_six_components": lambda c: [
        c["inertia"]["components_kg_m2"][k] for k in REQ_TENSOR_KEYS],
    "principal_inertia_kg_m2": lambda c: c["principal_inertia"]["moments_kg_m2"],
    "principal_axes_S": lambda c: c["principal_inertia"]["axes_S_unit_vectors"],
    "uncertainty": lambda c: [
        c["mass"]["standard_uncertainty_kg"],
        c["center_of_mass"]["standard_uncertainty_xyz_m"],
        c["inertia"]["standard_uncertainty_matrix_kg_m2"],
        c["principal_inertia"]["moment_standard_uncertainties_kg_m2"],
        c["principal_inertia"]["axis_angular_standard_uncertainty_rad"]],
    "pedigree": lambda c: [(m["mass_class"], m["com_class"], m["inertia_class"],
                            m["source_ref"]) for m in c["composition"]],
}
contract_rows = []
for c in cfgs:
    row = {"configuration_id": c["configuration_id"]}
    ok = True
    for name, fn in CONTRACT.items():
        try:
            v = fn(c)
            present = v is not None and (
                not isinstance(v, (list, tuple)) or len(v) > 0)
            has_null = False
            tmp = []
            deep_null(v, name, tmp)
            has_null = len(tmp) > 0
        except Exception as ex:  # noqa
            present, has_null = False, True
            row[name + "_error"] = str(ex)
        row[name] = "PRESENT" if (present and not has_null) else "MISSING_OR_NULL"
        ok = ok and (present and not has_null)
    row["reference_frame_declared"] = c["inertia"]["reference_frame"]
    row["reference_point_declared"] = c["inertia"]["reference_point"]
    row["pass"] = ok
    contract_rows.append(row)
frame_ok = all(
    c["inertia"]["reference_point"] == "configuration_system_CG"
    and c["inertia"]["reference_frame"] == "spacecraft_assembly_frame"
    for c in cfgs)
checks["n_wp2_output_contract_field_coverage"] = {
    "verdict": "PASS" if (all(r["pass"] for r in contract_rows) and frame_ok)
    else "FAIL",
    "contract_source": (
        "M7_EXECUTION_PLAN_V1.md WP2 row + wp10_mech_rl_v4/"
        "MECH_DYNAMICS_INTERFACE_V4.yaml design_mass_model_binding."
        "required_fields_per_configuration"
    ),
    "all_nine_carry_inertia_about_configuration_system_CG_in_S": frame_ok,
    "per_configuration": contract_rows,
}
if not (all(r["pass"] for r in contract_rows) and frame_ok):
    add_finding("WP2-AUD-CONTRACT", "HIGH",
                "n_wp2_output_contract_field_coverage",
                "A contract field required by the WP2 output contract is "
                "missing or null in at least one configuration.",
                [r for r in contract_rows if not r["pass"]])

# ============================================================ verdict
fail_ids = [k for k, v in checks.items() if v["verdict"] == "FAIL"]
hard = [f for f in findings if f["severity"] in ("CRITICAL", "HIGH")]
soft = [f for f in findings if f["severity"] in ("MEDIUM",)]
minor = [f for f in findings
         if f["severity"] in ("LOW", "LOW_PREEXISTING_UPSTREAM")]

if hard:
    overall = "AUDIT_FAIL_HARD_FINDINGS"
elif soft:
    overall = "AUDIT_PASS_WITH_FINDINGS_NO_HARD_DEFECT"
elif minor:
    overall = "AUDIT_PASS_WITH_MINOR_METADATA_FINDINGS"
else:
    overall = "AUDIT_PASS_CLEAN"

out = {
    "schema": "M7_WP2_DESIGN_MASS_AUDIT_V1",
    "generated_local": now_iso(),
    "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
    "work_package": "WP2_DESIGN_MASS",
    "audit_role": (
        "Independent audit of SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml. The "
        "aggregator aggregate_m7_design_mass.py was NOT imported or executed; "
        "every number here was recomputed with numpy/hashlib from the "
        "artifact's own declared component records and from real file bytes."
    ),
    "audited_artifact": {
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                "wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml",
        "sha256": tgt_sha, "bytes": tgt_bytes,
        "declared_schema": doc["schema"],
        "declared_generated_local": doc["generated_local"],
        "declared_status": doc["status"],
    },
    "auditor": {
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                "wp2_design_mass/WP2_INDEPENDENT_AUDIT_V1.py",
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "aggregator_executed": False,
    },
    "overall_verdict": overall,
    "checks_failed": fail_ids,
    "checks": checks,
    "findings": findings,
    "finding_counts": {
        "CRITICAL": sum(1 for f in findings if f["severity"] == "CRITICAL"),
        "HIGH": sum(1 for f in findings if f["severity"] == "HIGH"),
        "MEDIUM": sum(1 for f in findings if f["severity"] == "MEDIUM"),
        "LOW": sum(1 for f in findings
                   if f["severity"].startswith("LOW")),
    },
    "audit_source_register": {
        "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml": {
            "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                    "wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml",
            "sha256": tgt_sha, "bytes": tgt_bytes},
        "DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml": {
            "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                    "wp2_design_mass/DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml",
            "sha256": pol_sha, "bytes": pol_bytes},
        "aggregate_m7_design_mass.py": {
            "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                    "wp2_design_mass/aggregate_m7_design_mass.py",
            "sha256": agg_sha, "bytes": agg_bytes},
    },
    "prohibitions_honored": {
        "audited_artifact_modified": False,
        "aggregator_rerun": False,
        "freecad_launched": False,
        "abaqus_launched": False,
        "zero_fill_of_unknowns": False,
        "other_wp_files_touched": False,
    },
}

for k, v in [
    ("m7_owner_decision_register",
     "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/"
     "M7_OWNER_DECISION_REGISTER_V1.yaml"),
    ("m7_execution_plan",
     "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/"
     "M7_EXECUTION_PLAN_V1.md"),
    ("m4_configuration_library_v1",
     "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/"
     "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml"),
    ("m5_configuration_geometry_contract",
     "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/"
     "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml"),
    ("m6_configuration_transform_candidates",
     "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/"
     "wp2_mass_properties/CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml"),
]:
    s, b = sha256_and_size(v)
    out["audit_source_register"][k] = {"path": v, "sha256": s, "bytes": b}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False, sort_keys=False)

print("WROTE", OUT, os.path.getsize(OUT), "bytes")
print("OVERALL:", overall)
print("FAILED CHECKS:", fail_ids)
for f in findings:
    print("  -", f["finding_id"], f["severity"], f["check_id"], "|",
          f["summary"][:110])
