#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WP2 INDEPENDENT AUDIT of SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml (ODR-07 closure).

This script does NOT import or execute aggregate_m7_design_mass.py or
aggregate_m7_design_mass_v2.py. Every number below is recomputed from the two
YAML artifacts' own declared records using independent linear algebra (numpy)
and independent hashing (hashlib over real file bytes).

It is a superset of WP2_INDEPENDENT_AUDIT_V1.py: checks a..n are carried over
(so nothing previously audited silently stops being audited) and checks o..r are
added for the ODR-07 remediation:

  o  V1 -> V2 regression: every physics value bit-identical, recomputed from
     both files on disk, independent of the builder's own claim.
  p  covariance method discrimination: the audit builds its own generic-rotation
     counterexample and confirms the artifact's published one, proving the fix
     is a covariance propagation and not the ODR-07-forbidden abs().
  q  forbidden-remediation detector: independently re-derives every published
     component covariance and sigma from the published local sigma + rotation,
     verifies every published rotation really is a signed permutation, and
     quantifies the abs()-coincidence claim instead of trusting it.
  r  claim-hygiene scan: no measured / as-built / flight / qualification claim,
     next_stage_authorized false, review_status pending.

Emits WP2_DESIGN_MASS_AUDIT_V2.json.
"""
import hashlib
import json
import math
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
TARGET = os.path.join(WP2, "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml")
PRIOR = os.path.join(WP2, "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml")
POLICY = os.path.join(WP2, "DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml")
POLICY_V1 = os.path.join(WP2, "DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml")
AGG = os.path.join(WP2, "aggregate_m7_design_mass_v2.py")
AGG_V1 = os.path.join(WP2, "aggregate_m7_design_mass.py")
AUDIT_V1 = os.path.join(WP2, "WP2_DESIGN_MASS_AUDIT_V1.json")
OUT = os.path.join(WP2, "WP2_DESIGN_MASS_AUDIT_V2.json")

# scale-relative numerical-noise gate for identities that are exact in real
# arithmetic; never applied to a physical comparison
FP_REL_TOL = 1e-12


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


# symmetric-tensor component basis and induced 6x6 map, implemented here
# independently of the builder
_E = []
for _i, _j in [(0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2)]:
    _m = np.zeros((3, 3))
    _m[_i, _j] = 1.0
    _m[_j, _i] = 1.0
    _E.append(_m)


def comp6(m):
    return np.array([m[0, 0], m[1, 1], m[2, 2], m[0, 1], m[0, 2], m[1, 2]], dtype=float)


def induced_map(R):
    return np.column_stack([comp6(R @ B @ R.T) for B in _E])


# ---------------------------------------------------------------- load
doc = yaml.safe_load(open(TARGET, "r", encoding="utf-8"))
prior = yaml.safe_load(open(PRIOR, "r", encoding="utf-8"))
pol = yaml.safe_load(open(POLICY, "r", encoding="utf-8"))
pol_v1 = yaml.safe_load(open(POLICY_V1, "r", encoding="utf-8"))
cfgs = doc["configurations"]
prior_cfgs = {c["configuration_id"]: c for c in prior["configurations"]}

findings = []
checks = {}
KEYS6 = ["Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"]


def add_finding(fid, severity, check_id, summary, detail):
    findings.append({"finding_id": fid, "severity": severity, "check_id": check_id,
                     "summary": summary, "detail": detail})


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
wp2_m5names = [c.get("m5_geometry_contract_name") for c in cfgs]
m4_ids = [c["configuration_id"] for c in m4["configurations"]]
m4_names = [c["name"] for c in m4["configurations"]]
m4_legacy = [c.get("legacy_mapping") for c in m4["configurations"]]
m5_ids = [c["configuration_id"] for c in m5["records"]]
m5_names = [c["name"] for c in m5["records"]]

cw = doc.get("configuration_label_crosswalk") or {}
cw_rows = cw.get("rows") or []
cw_ok_rows = (
    [r["configuration_id"] for r in cw_rows] == m4_ids
    and [r["m4_configuration_library_name"] for r in cw_rows] == m4_names
    and [r["m4_legacy_mapping"] for r in cw_rows] == m4_legacy
    and [r["m5_geometry_contract_name"] for r in cw_rows] == m5_names
)
fwd = cw.get("forward_maps") or {}
rev = cw.get("reverse_maps") or {}
fwd_ok = (
    fwd.get("configuration_id_to_m4_name") == dict(zip(m4_ids, m4_names))
    and fwd.get("configuration_id_to_m4_legacy") == dict(zip(m4_ids, m4_legacy))
    and fwd.get("configuration_id_to_m5_name") == dict(zip(m5_ids, m5_names))
)
rev_ok = (
    rev.get("m4_name_to_configuration_id") == dict(zip(m4_names, m4_ids))
    and rev.get("m4_legacy_to_configuration_id") == dict(zip(m4_legacy, m4_ids))
    and rev.get("m5_name_to_configuration_id") == dict(zip(m5_names, m5_ids))
)
rev_injective = all(len(v) == 9 for v in rev.values()) if rev else False
inline_m5_ok = wp2_m5names == m5_names
divergence = [
    {"configuration_id": i, "wp2_m4_name": a, "m5_name": b}
    for i, a, b in zip(wp2_ids, wp2_names, m5_names) if a != b
]
a_pass = bool(len(cfgs) == 9 and wp2_ids == m4_ids == m5_ids
              and wp2_names == m4_names and wp2_legacy == m4_legacy
              and cw_ok_rows and fwd_ok and rev_ok and rev_injective
              and inline_m5_ok and cw.get("token_collision_warning"))
checks["a_nine_configurations_naming_and_crosswalk"] = {
    "verdict": "PASS" if a_pass else "FAIL",
    "configuration_count": len(cfgs),
    "configuration_ids": wp2_ids,
    "ids_match_m4_configuration_library": wp2_ids == m4_ids,
    "ids_match_m5_geometry_contract": wp2_ids == m5_ids,
    "names_match_m4_configuration_library": wp2_names == m4_names,
    "legacy_mapping_matches_m4": wp2_legacy == m4_legacy,
    "m5_names_still_diverge_by_design": divergence,
    "crosswalk_present": bool(cw),
    "crosswalk_rows_match_both_sources": cw_ok_rows,
    "crosswalk_forward_maps_correct": fwd_ok,
    "crosswalk_reverse_maps_correct": rev_ok,
    "crosswalk_reverse_maps_injective_9_of_9": rev_injective,
    "per_configuration_inline_m5_name_correct": inline_m5_ok,
    "token_collision_warning_present": bool(cw.get("token_collision_warning")),
    "closes_finding": "WP2-AUD-01",
    "method": ("crosswalk rebuilt from the M4 configuration library and the M5 geometry "
               "contract on disk and compared entry by entry against the artifact's "
               "published forward and reverse maps"),
}
if not a_pass:
    add_finding("WP2-AUD-V2-01", "MEDIUM", "a_nine_configurations_naming_and_crosswalk",
                "Configuration crosswalk incomplete or inconsistent with the sources.",
                {"rows_ok": cw_ok_rows, "fwd_ok": fwd_ok, "rev_ok": rev_ok,
                 "inline_ok": inline_m5_ok})

# ============================================================ CHECK b
REQ_CFG = ["configuration_id", "name", "legacy_mapping", "m5_geometry_contract_name",
           "configuration_semantics", "composition", "mass", "center_of_mass",
           "inertia", "principal_inertia", "status"]
REQ_MASS = ["value_kg", "standard_uncertainty_kg", "relative_standard_uncertainty", "status"]
REQ_COM = ["reference_frame", "xyz_m", "standard_uncertainty_xyz_m", "status"]
REQ_INE = ["reference_frame", "reference_point", "matrix_kg_m2", "components_kg_m2",
           "standard_uncertainty_matrix_kg_m2", "standard_uncertainty_components_kg_m2",
           "uncertainty_covariance", "status"]
REQ_PRI = ["moments_kg_m2", "moment_standard_uncertainties_kg_m2", "axes_S_unit_vectors",
           "axes_order", "axes_handedness", "axes_determinant",
           "axis_angular_standard_uncertainty_rad", "status"]
REQ_MEMBER = ["component_id", "mass_kg", "mass_class", "mass_standard_uncertainty_kg",
              "com_S_m", "com_class", "com_standard_uncertainty_m_per_axis",
              "inertia_about_own_com_S_kg_m2", "inertia_class", "inertia_uncertainty",
              "inertia_reference_frame_declared", "inertia_reference_point_declared",
              "source_tensor_local_frame", "source_to_S_rotation_rows",
              "inertia_about_own_com_source_frame_kg_m2",
              "membership_status", "source_ref", "pedigree_note"]
REQ_UNC = ["semantics", "component_order", "local_frame_standard_uncertainty_kg_m2",
           "covariance_matrix_kg2_m4", "component_standard_uncertainty_kg_m2", "checks"]

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
    scan(c["inertia"]["components_kg_m2"], KEYS6, f"{cid}.inertia.components_kg_m2")
    scan(c["inertia"]["standard_uncertainty_components_kg_m2"], KEYS6,
         f"{cid}.inertia.standard_uncertainty_components_kg_m2")
    for m in c["composition"]:
        w = f"{cid}.composition[{m.get('component_id')}]"
        scan(m, REQ_MEMBER, w)
        scan(m.get("inertia_uncertainty", {}), REQ_UNC, w + ".inertia_uncertainty")
        scan(m["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"], KEYS6,
             w + ".inertia_uncertainty.component_standard_uncertainty_kg_m2")
        scan(m["inertia_uncertainty"]["local_frame_standard_uncertainty_kg_m2"], KEYS6,
             w + ".inertia_uncertainty.local_frame_standard_uncertainty_kg_m2")
    deep_null(c, cid, deep_nulls_all)

benign_null_suffixes = ("configuration_semantics.target_membership",)
benign_nulls = [x for x in deep_nulls_all if x.endswith(benign_null_suffixes)]
nonbenign_nulls = [x for x in deep_nulls_all if x not in benign_nulls]
checks["b_no_null_or_absent_required_field"] = {
    "verdict": "PASS" if (not null_or_absent and not nonbenign_nulls) else "FAIL",
    "required_field_violations": null_or_absent,
    "all_nulls_found_anywhere_in_configurations": deep_nulls_all,
    "nulls_judged_semantically_correct": benign_nulls,
    "nulls_judged_semantically_correct_reason": (
        "configuration_semantics.target_membership = null on C01..C07 means 'no captured "
        "target in this configuration', which is the correct state, not a missing value"),
    "nulls_requiring_remediation": nonbenign_nulls,
    "required_member_field_count": len(REQ_MEMBER),
}
if null_or_absent or nonbenign_nulls:
    add_finding("WP2-AUD-V2-NULL", "HIGH", "b_no_null_or_absent_required_field",
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

mass_rows, pin_rows, com_rows = [], [], []
for c in cfgs:
    cid = c["configuration_id"]
    comp = c["composition"]
    rep = float(c["mass"]["value_kg"])
    s_fsum = math.fsum(float(m["mass_kg"]) for m in comp)
    mass_rows.append({
        "configuration_id": cid, "reported_total_mass_kg": rep,
        "audit_sum_of_components_kg": s_fsum, "abs_error_kg": abs(rep - s_fsum),
        "member_count": len(comp), "pass": abs(rep - s_fsum) <= 1e-12,
    })
    for m in comp:
        exp = None
        if m["component_id"] in PINNED:
            exp = PINNED[m["component_id"]]
        elif m["component_id"] == "bus_primary_structure":
            exp = BUS_CORE + LEGACY_FLANGE
        elif m["component_id"] in TARGET_MASS:
            exp = TARGET_MASS[m["component_id"]]
        if exp is not None:
            pin_rows.append({
                "configuration_id": cid, "component_id": m["component_id"],
                "reported_kg": float(m["mass_kg"]), "pinned_expected_kg": exp,
                "abs_error_kg": abs(float(m["mass_kg"]) - exp),
                "pass": abs(float(m["mass_kg"]) - exp) <= 1e-12,
            })
    M = math.fsum(float(m["mass_kg"]) for m in comp)
    r = np.zeros(3)
    for m in comp:
        r += float(m["mass_kg"]) * mat(m["com_S_m"])
    r = r / M
    rep_com = mat(c["center_of_mass"]["xyz_m"])
    com_rows.append({
        "configuration_id": cid, "reported_com_S_m": rep_com.tolist(),
        "audit_com_S_m": r.tolist(),
        "max_abs_error_m": float(np.max(np.abs(rep_com - r))),
        "pass": bool(np.max(np.abs(rep_com - r)) <= 1e-12),
    })

b601_bitexact = all(
    repr(float(m["mass_kg"])) == repr(4.695555949342986)
    for c in cfgs for m in c["composition"]
    if m["component_id"] == "b601_complete_arm_including_gripper_urdf_links")
m3r_bitexact = all(
    float(m["mass_kg"]) == 0.7619
    for c in cfgs for m in c["composition"]
    if m["component_id"] == "m3r_stage_a_plus_stage_b_budget_envelope")

checks["c_mass_closure_and_pinned_values"] = {
    "verdict": "PASS" if (all(x["pass"] for x in mass_rows + pin_rows + com_rows)
                          and b601_bitexact and m3r_bitexact) else "FAIL",
    "mass_sum_per_configuration": mass_rows,
    "pinned_value_rows": pin_rows,
    "pinned_row_count": len(pin_rows),
    "b601_bit_exact_4_695555949342986": b601_bitexact,
    "m3r_bit_exact_0_7619": m3r_bitexact,
    "independent_center_of_mass_recomputation": com_rows,
    "method": "math.fsum over declared member masses; r_sys = sum(m_i r_i)/sum(m_i)",
}
if not (all(x["pass"] for x in mass_rows + pin_rows + com_rows)
        and b601_bitexact and m3r_bitexact):
    add_finding("WP2-AUD-V2-MASS", "HIGH", "c_mass_closure_and_pinned_values",
                "Mass closure or pinned-value mismatch.",
                {"mass": [x for x in mass_rows if not x["pass"]],
                 "pins": [x for x in pin_rows if not x["pass"]],
                 "com": [x for x in com_rows if not x["pass"]]})

# ============================================================ CHECK d
tri_rows = []
for c in cfgs:
    I = mat(c["inertia"]["matrix_kg_m2"])
    cm = c["inertia"]["components_kg_m2"]
    I_from_components = np.array([[cm["Ixx"], cm["Ixy"], cm["Ixz"]],
                                  [cm["Ixy"], cm["Iyy"], cm["Iyz"]],
                                  [cm["Ixz"], cm["Iyz"], cm["Izz"]]], dtype=float)
    sym_res = float(np.max(np.abs(I - I.T)))
    comp_res = float(np.max(np.abs(I - I_from_components)))
    w = np.sort(np.linalg.eigvalsh(I))
    I1, I2, I3 = (float(x) for x in w)
    t = [I1 + I2 - I3, I1 + I3 - I2, I2 + I3 - I1]
    scale = max(abs(I1), abs(I2), abs(I3))
    tri_rows.append({
        "configuration_id": c["configuration_id"],
        "symmetry_max_abs_residual_kg_m2": sym_res, "symmetric": sym_res == 0.0,
        "matrix_vs_components_max_abs_residual_kg_m2": comp_res,
        "eigenvalues_kg_m2": [I1, I2, I3], "min_eigenvalue_kg_m2": I1,
        "positive_definite": I1 > 0.0,
        "triangle_margins_kg_m2": t, "triangle_min_margin_kg_m2": min(t),
        "triangle_min_margin_relative": min(t) / scale,
        "triangle_inequalities_satisfied": min(t) > 0.0,
        "pass": (sym_res == 0.0 and comp_res <= 1e-15 and I1 > 0.0 and min(t) > 0.0),
    })
checks["d_inertia_physicality_symmetry_pd_triangle"] = {
    "verdict": "PASS" if all(x["pass"] for x in tri_rows) else "FAIL",
    "per_configuration": tri_rows,
    "method": "numpy.linalg.eigvalsh on the reported tensor; exact symmetry test; I_i+I_j>I_k",
}
if not all(x["pass"] for x in tri_rows):
    add_finding("WP2-AUD-V2-TENSOR", "CRITICAL", "d_inertia_physicality_symmetry_pd_triangle",
                "Inertia tensor is not physically admissible.",
                [x for x in tri_rows if not x["pass"]])

# ============================================================ CHECK e
axes_rows = []
for c in cfgs:
    I = mat(c["inertia"]["matrix_kg_m2"])
    R = mat(c["principal_inertia"]["axes_S_unit_vectors"])
    rep_mom = mat(c["principal_inertia"]["moments_kg_m2"])
    orth_res = float(np.max(np.abs(R @ R.T - np.eye(3))))
    detR = float(np.linalg.det(R))
    D = R @ I @ R.T
    diag_res = float(np.max(np.abs(np.diag(D) - rep_mom)))
    offdiag_res = float(np.max(np.abs(D - np.diag(np.diag(D)))))
    w, V = np.linalg.eigh(I)
    idx = np.argsort(w)
    eig_res = float(np.max(np.abs(w[idx] - rep_mom)))
    V = V[:, idx]
    axis_angle_err = []
    for i in range(3):
        cth = min(1.0, abs(float(np.dot(V[:, i], R[i]))))
        axis_angle_err.append(float(np.arccos(cth)))
    ascending = bool(rep_mom[0] <= rep_mom[1] <= rep_mom[2])
    declared_det = c["principal_inertia"].get("axes_determinant")
    axes_rows.append({
        "configuration_id": c["configuration_id"],
        "row_norms": [float(np.linalg.norm(R[i])) for i in range(3)],
        "orthonormality_max_abs_residual_RRt_minus_I": orth_res,
        "orthonormal": orth_res <= 1e-12,
        "det_R_recomputed": detR,
        "det_R_declared_in_artifact": declared_det,
        "declared_det_matches_recomputed": bool(
            declared_det is not None and abs(float(declared_det) - detR) <= 1e-12),
        "right_handed": abs(detR - 1.0) <= 1e-12,
        "declared_handedness": c["principal_inertia"].get("axes_handedness"),
        "handedness_convention_declared": bool(
            c["principal_inertia"].get("axes_handedness_convention")),
        "R_I_Rt_diagonal_vs_reported_moments_max_abs_err_kg_m2": diag_res,
        "R_I_Rt_max_abs_offdiagonal_kg_m2": offdiag_res,
        "independent_eigh_vs_reported_moments_max_abs_err_kg_m2": eig_res,
        "per_axis_angle_error_rad": axis_angle_err,
        "moments_ascending_as_declared": ascending,
        "degeneracy_flags_reported": c["principal_inertia"].get("degeneracy_flags"),
        "pass": (orth_res <= 1e-12 and abs(detR - 1.0) <= 1e-12 and diag_res <= 1e-12
                 and offdiag_res <= 1e-9 and eig_res <= 1e-12 and ascending
                 and c["principal_inertia"].get("axes_handedness") == "RIGHT_HANDED_PROPER_ROTATION"
                 and bool(c["principal_inertia"].get("axes_handedness_convention"))),
    })
left_handed = [x for x in axes_rows if not x["right_handed"]]
checks["e_principal_axes_orthonormal_right_handed_and_consistent"] = {
    "verdict": "PASS" if all(x["pass"] for x in axes_rows) else "FAIL",
    "handedness_subcheck_verdict": "FAIL" if left_handed else "PASS",
    "left_handed_configurations": [x["configuration_id"] for x in left_handed],
    "det_R_all_configurations": {x["configuration_id"]: x["det_R_recomputed"] for x in axes_rows},
    "closes_finding": "WP2-AUD-06",
    "per_configuration": axes_rows,
    "method": ("R R^T vs I3; det(R); R I R^T vs diag(reported moments); independent "
               "numpy.linalg.eigh; per-axis direction agreement (sign-insensitive)"),
}
if left_handed:
    add_finding("WP2-AUD-V2-06", "MEDIUM",
                "e_principal_axes_orthonormal_right_handed_and_consistent",
                "A principal-axis triad is still left-handed after the ODR-07 remediation.",
                [{"configuration_id": x["configuration_id"], "det_R": x["det_R_recomputed"]}
                 for x in left_handed])
elif not all(x["pass"] for x in axes_rows):
    add_finding("WP2-AUD-V2-AXES", "HIGH",
                "e_principal_axes_orthonormal_right_handed_and_consistent",
                "Principal axes fail orthonormality, ordering or diagonalisation.",
                [x for x in axes_rows if not x["pass"]])

# ============================================================ CHECK f  (ODR-02)
PANEL_M = 0.3483933
by_id = {c["configuration_id"]: c for c in cfgs}
base_mass = float(by_id["C01"]["mass"]["value_kg"])
odr2_rows = []
for cid in ["C01", "C02", "C03", "C04"]:
    c = by_id[cid]
    comp = {m["component_id"]: m for m in c["composition"]}
    left, right = comp.get("solar_array_left"), comp.get("solar_array_right")
    tot = float(c["mass"]["value_kg"])
    panel_sum = (float(left["mass_kg"]) if left else 0.0) + (float(right["mass_kg"]) if right else 0.0)
    odr2_rows.append({
        "configuration_id": cid, "name": c["name"],
        "panel_failure_rule_declared": c["configuration_semantics"].get("panel_failure_rule"),
        "solar_array_left_present": left is not None,
        "solar_array_right_present": right is not None,
        "panel_mass_sum_kg": panel_sum, "expected_panel_mass_sum_kg": 2 * PANEL_M,
        "panel_mass_retained": abs(panel_sum - 2 * PANEL_M) <= 1e-12,
        "total_mass_kg": tot, "total_minus_C01_kg": tot - base_mass,
        "no_jettison_mass_drop": abs(tot - base_mass) <= 1e-12,
        "pass": (left is not None and right is not None
                 and abs(panel_sum - 2 * PANEL_M) <= 1e-12 and abs(tot - base_mass) <= 1e-12),
    })
moved = []
c1 = {m["component_id"]: m for m in by_id["C01"]["composition"]}
for cid, exp_l, exp_r in [("C02", True, False), ("C03", False, True), ("C04", True, True)]:
    cc = {m["component_id"]: m for m in by_id[cid]["composition"]}
    dl = float(np.max(np.abs(mat(cc["solar_array_left"]["com_S_m"]) - mat(c1["solar_array_left"]["com_S_m"]))))
    dr = float(np.max(np.abs(mat(cc["solar_array_right"]["com_S_m"]) - mat(c1["solar_array_right"]["com_S_m"]))))
    moved.append({"configuration_id": cid, "left_com_shift_vs_C01_max_abs_m": dl,
                  "right_com_shift_vs_C01_max_abs_m": dr,
                  "pass": ((dl > 0) == exp_l) and ((dr > 0) == exp_r)})
checks["f_odr02_panel_failure_attached_stuck"] = {
    "verdict": "PASS" if (all(x["pass"] for x in odr2_rows) and all(x["pass"] for x in moved)) else "FAIL",
    "mass_retention_rows": odr2_rows, "geometry_relocation_rows": moved,
    "ruling": "ODR-02 panel failure = attached-stuck, never jettison",
}
if not (all(x["pass"] for x in odr2_rows) and all(x["pass"] for x in moved)):
    add_finding("WP2-AUD-V2-ODR02", "CRITICAL", "f_odr02_panel_failure_attached_stuck",
                "ODR-02 violated.", {"mass": odr2_rows, "geom": moved})

# ============================================================ CHECK g  (ODR-07)
CLASS_TABLE = {sc["class_id"]: {"mass_rel": sc["mass_relative_standard_uncertainty"],
                                "com_abs": sc["com_absolute_standard_uncertainty_m_per_axis"],
                                "inertia_rel": sc["inertia_relative_standard_uncertainty"]}
               for sc in pol["source_classes"]}
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
policy_classes_identical = bool(pol["source_classes"] == pol_v1["source_classes"])

cov_rows, class_mismatch, negative_u, zero_u, magnitude_mismatch = [], [], [], [], []
for c in cfgs:
    cid = c["configuration_id"]
    for m in c["composition"]:
        comp_id = m["component_id"]
        mc, cc_, ic = m["mass_class"], m["com_class"], m["inertia_class"]
        exp = EXPECT_CLASS.get(comp_id)
        if exp and (mc, cc_, ic) != exp:
            class_mismatch.append({"configuration_id": cid, "component_id": comp_id,
                                   "reported": [mc, cc_, ic], "expected": list(exp)})
        unc = m["inertia_uncertainty"]
        C = mat(unc["covariance_matrix_kg2_m4"])
        sig = np.array([float(unc["component_standard_uncertainty_kg_m2"][k]) for k in KEYS6])
        loc = np.array([float(unc["local_frame_standard_uncertainty_kg_m2"][k]) for k in KEYS6])
        R = mat(m["source_to_S_rotation_rows"])
        Iloc = mat(m["inertia_about_own_com_source_frame_kg_m2"])
        IS = mat(m["inertia_about_own_com_S_kg_m2"])

        # --- the four ODR-07 checks, recomputed by the auditor ---
        scale = max(float(np.max(np.abs(C))), 1.0)
        sym_res = float(np.max(np.abs(C - C.T)))
        min_eig = float(np.min(np.linalg.eigvalsh(0.5 * (C + C.T))))
        var = np.diag(C)
        # --- independent re-derivation of C and sigma from the declared inputs ---
        T = induced_map(R)
        C_audit = T @ np.diag(loc ** 2) @ T.T
        sig_audit = np.sqrt(np.diag(C_audit))
        # --- policy class rule on the local tensor (P7) ---
        rel = CLASS_TABLE[ic]["inertia_rel"]
        iscale = (Iloc[0, 0] + Iloc[1, 1] + Iloc[2, 2]) / 3.0
        loc_expect = np.array([rel * abs(Iloc[0, 0]), rel * abs(Iloc[1, 1]), rel * abs(Iloc[2, 2]),
                               rel * abs(iscale), rel * abs(iscale), rel * abs(iscale)])
        loc_err = float(np.max(np.abs(loc - loc_expect)))
        if loc_err > 0.0:
            magnitude_mismatch.append({"configuration_id": cid, "component_id": comp_id,
                                       "field": "local_frame_standard_uncertainty_kg_m2",
                                       "max_abs_error": loc_err})
        um = float(m["mass_standard_uncertainty_kg"])
        uc = float(m["com_standard_uncertainty_m_per_axis"])
        if comp_id == "bus_primary_structure":
            exp_um = float(np.hypot(0.20 * BUS_CORE, 0.10 * LEGACY_FLANGE))
        else:
            exp_um = CLASS_TABLE[mc]["mass_rel"] * float(m["mass_kg"])
        if abs(um - exp_um) > 1e-12 * max(1.0, abs(exp_um)):
            magnitude_mismatch.append({"configuration_id": cid, "component_id": comp_id,
                                       "field": "mass_standard_uncertainty_kg",
                                       "reported": um, "expected": exp_um})
        if abs(uc - CLASS_TABLE[cc_]["com_abs"]) > 1e-15:
            magnitude_mismatch.append({"configuration_id": cid, "component_id": comp_id,
                                       "field": "com_standard_uncertainty_m_per_axis",
                                       "reported": uc, "expected": CLASS_TABLE[cc_]["com_abs"]})
        for label, val in [("mass_standard_uncertainty_kg", um),
                           ("com_standard_uncertainty_m_per_axis", uc)]:
            if val < 0:
                negative_u.append({"configuration_id": cid, "component_id": comp_id,
                                   "field": label, "value": val})
            if val == 0:
                zero_u.append({"configuration_id": cid, "component_id": comp_id, "field": label})
        neg_sigma = [[KEYS6[i], float(sig[i])] for i in range(6) if sig[i] < 0]
        if neg_sigma:
            negative_u.append({"configuration_id": cid, "component_id": comp_id,
                               "field": "component_standard_uncertainty_kg_m2",
                               "negative_entries": neg_sigma})
        zero_sigma = [KEYS6[i] for i in range(6) if sig[i] == 0]
        if zero_sigma:
            zero_u.append({"configuration_id": cid, "component_id": comp_id,
                           "field": "component_standard_uncertainty_kg_m2",
                           "zero_entries": zero_sigma})
        row = {
            "configuration_id": cid, "component_id": comp_id, "inertia_class": ic,
            "covariance_symmetric": bool(sym_res <= FP_REL_TOL * scale),
            "covariance_symmetry_max_abs_residual_kg2_m4": sym_res,
            "covariance_positive_semidefinite": bool(min_eig >= -FP_REL_TOL * scale),
            "covariance_min_eigenvalue_kg2_m4": min_eig,
            "variance_diagonal_nonnegative": bool(np.all(var >= 0.0)),
            "variance_diagonal_min_kg2_m4": float(np.min(var)),
            "reported_sigma_nonnegative": bool(np.all(sig >= 0.0)),
            "reported_sigma_min_kg_m2": float(np.min(sig)),
            "sigma_equals_sqrt_of_covariance_diagonal_max_abs_err_kg_m2":
                float(np.max(np.abs(sig - np.sqrt(np.clip(var, 0.0, None))))),
            "audit_rederived_covariance_max_abs_err_kg2_m4": float(np.max(np.abs(C - C_audit))),
            "audit_rederived_sigma_max_abs_err_kg_m2": float(np.max(np.abs(sig - sig_audit))),
            "local_sigma_vs_policy_P7_max_abs_err_kg_m2": loc_err,
            "reported_S_tensor_vs_R_Ilocal_Rt_max_abs_err_kg_m2":
                float(np.max(np.abs(IS - R @ Iloc @ R.T))),
            "rotation_is_signed_permutation": bool(
                np.all(np.isin(np.round(R, 12), [-1.0, 0.0, 1.0]))
                and np.allclose(np.abs(R).sum(axis=0), 1.0) and np.allclose(np.abs(R).sum(axis=1), 1.0)),
            "off_diagonal_min_signed_kg2_m4": float(np.min(C - np.diag(np.diag(C)))),
        }
        row["pass"] = bool(
            row["covariance_symmetric"] and row["covariance_positive_semidefinite"]
            and row["variance_diagonal_nonnegative"] and row["reported_sigma_nonnegative"]
            and row["sigma_equals_sqrt_of_covariance_diagonal_max_abs_err_kg_m2"] <= 1e-18
            and row["audit_rederived_covariance_max_abs_err_kg2_m4"] == 0.0
            and row["audit_rederived_sigma_max_abs_err_kg_m2"] == 0.0
            and row["local_sigma_vs_policy_P7_max_abs_err_kg_m2"] == 0.0
            and row["reported_S_tensor_vs_R_Ilocal_Rt_max_abs_err_kg_m2"] == 0.0)
        cov_rows.append(row)

cfg_u_neg, cfg_u_zero = [], []
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
                cfg_u_zero.append({"configuration_id": cid, "field": k, "index": i, "issue": "NULL"})
            elif float(v) < 0:
                cfg_u_neg.append({"configuration_id": cid, "field": k, "index": i, "value": float(v)})
            elif float(v) == 0:
                cfg_u_zero.append({"configuration_id": cid, "field": k, "index": i, "issue": "ZERO"})

rss_rows = []
for c in cfgs:
    us = [float(m["mass_standard_uncertainty_kg"]) for m in c["composition"]]
    rss = float(np.sqrt(math.fsum(u * u for u in us)))
    rep = float(c["mass"]["standard_uncertainty_kg"])
    rss_rows.append({"configuration_id": c["configuration_id"],
                     "reported_mass_standard_uncertainty_kg": rep,
                     "audit_rss_of_component_mass_u_kg": rss,
                     "relative_error": abs(rep - rss) / rep, "tolerance_relative": 1e-9,
                     "pass": (abs(rep - rss) / rep) <= 1e-9})

cfg_cov_rows = []
for c in cfgs:
    uc = c["inertia"]["uncertainty_covariance"]
    C = mat(uc["covariance_matrix_kg2_m4"])
    sig = np.array([float(c["inertia"]["standard_uncertainty_components_kg_m2"][k]) for k in KEYS6])
    scale = max(float(np.max(np.abs(C))), 1.0)
    sym_res = float(np.max(np.abs(C - C.T)))
    min_eig = float(np.min(np.linalg.eigvalsh(0.5 * (C + C.T))))
    var = np.diag(C)
    rel = float(np.max(np.abs(np.sqrt(np.clip(var, 0.0, None)) - sig))) / max(float(np.max(np.abs(sig))), 1e-30)
    cfg_cov_rows.append({
        "configuration_id": c["configuration_id"],
        "covariance_symmetric": bool(sym_res <= FP_REL_TOL * scale),
        "covariance_symmetry_max_abs_residual_kg2_m4": sym_res,
        "covariance_positive_semidefinite": bool(min_eig >= -FP_REL_TOL * scale),
        "covariance_min_eigenvalue_kg2_m4": min_eig,
        "variance_diagonal_nonnegative": bool(np.all(var >= 0.0)),
        "sqrt_diag_vs_reported_sigma_max_relative_err": rel,
        "pass": bool(sym_res <= FP_REL_TOL * scale and min_eig >= -FP_REL_TOL * scale
                     and np.all(var >= 0.0) and rel <= FP_REL_TOL),
    })

g_pass = bool(not class_mismatch and not cfg_u_neg and not cfg_u_zero and not negative_u
              and not zero_u and not magnitude_mismatch and policy_classes_identical
              and all(r["pass"] for r in cov_rows) and all(r["pass"] for r in rss_rows)
              and all(r["pass"] for r in cfg_cov_rows))
checks["g_uncertainty_covariance_semantics_and_pedigree"] = {
    "verdict": "PASS" if g_pass else "FAIL",
    "component_record_count_audited": len(cov_rows),
    "odr07_required_checks": ["covariance_symmetric", "covariance_positive_semidefinite",
                             "variance_diagonal_nonnegative", "reported_sigma_nonnegative"],
    "odr07_required_checks_all_pass": bool(all(
        r["covariance_symmetric"] and r["covariance_positive_semidefinite"]
        and r["variance_diagonal_nonnegative"] and r["reported_sigma_nonnegative"]
        for r in cov_rows)),
    "component_level_negative_uncertainty_entries": negative_u,
    "component_level_zero_uncertainty_entries": zero_u,
    "configuration_level_negative_uncertainties": cfg_u_neg,
    "configuration_level_zero_or_null_uncertainties": cfg_u_zero,
    "pedigree_class_mismatches": class_mismatch,
    "magnitude_mismatches_vs_policy": magnitude_mismatch,
    "policy_v2_class_values_identical_to_v1": policy_classes_identical,
    "configuration_mass_uncertainty_vs_independent_rss": rss_rows,
    "configuration_level_covariance_rows": cfg_cov_rows,
    "per_component_rows": cov_rows,
    "closes_finding": "WP2-AUD-02",
    "method": ("for every component record the auditor rebuilds T(R) from the published "
               "source_to_S rotation, rebuilds C = T diag(u_local^2) T^T and "
               "sigma = sqrt(diag(C)), re-applies policy rule P7 to the published "
               "source-frame tensor, and compares against the published covariance and "
               "sigma; class table read from DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml"),
}
if not g_pass:
    add_finding("WP2-AUD-V2-02", "MEDIUM", "g_uncertainty_covariance_semantics_and_pedigree",
                "Uncertainty covariance semantics or pedigree defect.",
                {"cov": [r for r in cov_rows if not r["pass"]], "neg": negative_u,
                 "zero": zero_u, "mag": magnitude_mismatch, "class": class_mismatch})

# ============================================================ CHECK h
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
    ine_rows.append({"configuration_id": c["configuration_id"],
                     "max_abs_error_vs_reported_kg_m2": err,
                     "max_rel_error_vs_reported": err / float(np.max(np.abs(rep))),
                     "pass": err <= 1e-12})
checks["h_independent_parallel_axis_inertia_reconstruction"] = {
    "verdict": "PASS" if all(x["pass"] for x in ine_rows) else "FAIL",
    "per_configuration": ine_rows,
    "method": "I_sys = sum_i [ I_i(own CoM, S axes) + m_i (|d_i|^2 I3 - d_i d_i^T) ]",
}
if not all(x["pass"] for x in ine_rows):
    add_finding("WP2-AUD-V2-PA", "HIGH", "h_independent_parallel_axis_inertia_reconstruction",
                "Configuration inertia not reproducible from the declared composition.",
                [x for x in ine_rows if not x["pass"]])

# ============================================================ CHECK i
sr = doc["source_register"]
sr_rows = []
for key, rec in sr.items():
    have_sha, have_bytes = sha256_and_size(rec["path"])
    declared = (rec.get("sha256") or "").upper()
    sr_rows.append({
        "key": key, "path": rec["path"], "file_exists": have_sha is not None,
        "declared_sha256": declared, "recomputed_sha256": have_sha,
        "sha256_match": (have_sha == declared) if have_sha else False,
        "declared_bytes": rec.get("bytes"), "recomputed_bytes": have_bytes,
        "bytes_field_present": "bytes" in rec,
        "bytes_match": rec.get("bytes") == have_bytes,
        "nonzero_bytes": bool(have_bytes),
    })
sr_bad = [r for r in sr_rows if not (r["sha256_match"] and r["bytes_field_present"]
                                     and r["bytes_match"] and r["nonzero_bytes"])]
checks["i_source_register_integrity_sha_and_bytes"] = {
    "verdict": "FAIL" if sr_bad else "PASS",
    "entry_count": len(sr_rows),
    "sha256_verified_count": sum(1 for r in sr_rows if r["sha256_match"]),
    "bytes_present_count": sum(1 for r in sr_rows if r["bytes_field_present"]),
    "bytes_verified_count": sum(1 for r in sr_rows if r["bytes_match"]),
    "bad_rows": sr_bad, "rows": sr_rows,
    "closes_finding": "WP2-AUD-03",
    "method": "hashlib.sha256 over real file bytes and real byte count for every entry",
}
if sr_bad:
    add_finding("WP2-AUD-V2-SR", "HIGH", "i_source_register_integrity_sha_and_bytes",
                "source_register entry fails hash or byte-size verification.", sr_bad)

# ============================================================ CHECK j
pol_sha, pol_bytes = sha256_and_size(POLICY)
polv1_sha, polv1_bytes = sha256_and_size(POLICY_V1)
agg_sha, agg_bytes = sha256_and_size(AGG)
aggv1_sha, aggv1_bytes = sha256_and_size(AGG_V1)
tgt_sha, tgt_bytes = sha256_and_size(TARGET)
prior_sha, prior_bytes = sha256_and_size(PRIOR)
declared_pol = (doc["uncertainty_policy"].get("sha256") or "").upper()
declared_agg = (doc["aggregator"].get("sha256") or "").upper()
declared_prior = (doc["supersedes"].get("sha256") or "").upper()
j_pass = bool(declared_pol == pol_sha and declared_agg == agg_sha
              and declared_prior == prior_sha
              and doc["uncertainty_policy"].get("bytes") == pol_bytes
              and doc["aggregator"].get("bytes") == agg_bytes
              and doc["supersedes"].get("bytes") == prior_bytes)
checks["j_self_reference_pins"] = {
    "verdict": "PASS" if j_pass else "FAIL",
    "uncertainty_policy_declared_sha256": declared_pol,
    "uncertainty_policy_recomputed_sha256": pol_sha,
    "uncertainty_policy_bytes_declared_vs_real": [doc["uncertainty_policy"].get("bytes"), pol_bytes],
    "aggregator_declared_sha256": declared_agg,
    "aggregator_recomputed_sha256": agg_sha,
    "aggregator_bytes_declared_vs_real": [doc["aggregator"].get("bytes"), agg_bytes],
    "aggregator_sha256_pinned_in_artifact": "sha256" in doc["aggregator"],
    "superseded_v1_declared_sha256": declared_prior,
    "superseded_v1_recomputed_sha256": prior_sha,
    "v1_aggregator_lineage_pin_matches": bool(
        (doc["aggregator"].get("reuses_v1_physics_module") or {}).get("sha256") == aggv1_sha),
    "policy_v1_lineage_pin_matches": bool(
        (doc["uncertainty_policy"].get("superseded_v1") or {}).get("sha256") == polv1_sha),
    "target_artifact_sha256": tgt_sha, "target_artifact_bytes": tgt_bytes,
    "closes_finding": "WP2-AUD-04",
}
if not j_pass:
    add_finding("WP2-AUD-V2-PIN", "HIGH", "j_self_reference_pins",
                "A self-referenced pin (policy, aggregator or superseded artifact) does not "
                "match the file on disk.",
                {"policy": [declared_pol, pol_sha], "aggregator": [declared_agg, agg_sha],
                 "v1": [declared_prior, prior_sha]})

# ============================================================ CHECK k
label_rows = []
for c in cfgs:
    for m in c["composition"]:
        decl = m.get("inertia_reference_frame_declared")
        pt = m.get("inertia_reference_point_declared")
        R = mat(m["source_to_S_rotation_rows"])
        Iloc = mat(m["inertia_about_own_com_source_frame_kg_m2"])
        IS = mat(m["inertia_about_own_com_S_kg_m2"])
        res = float(np.max(np.abs(IS - R @ Iloc @ R.T)))
        detR = float(np.linalg.det(R))
        label_rows.append({
            "configuration_id": c["configuration_id"], "component_id": m["component_id"],
            "inertia_reference_frame_declared": decl,
            "inertia_reference_point_declared": pt,
            "source_tensor_local_frame": m.get("source_tensor_local_frame"),
            "rotation_det": detR,
            "reported_equals_R_Ilocal_Rt_max_abs_err_kg_m2": res,
            "pass": bool(decl == "S" and pt == "component_own_center_of_mass"
                         and res == 0.0 and abs(detR - 1.0) <= 1e-12
                         and m.get("source_tensor_local_frame") is not None),
        })
c1 = {m["component_id"]: m for m in by_id["C01"]["composition"]}
c4 = {m["component_id"]: m for m in by_id["C04"]["composition"]}
Id = mat(c1["solar_array_left"]["inertia_about_own_com_S_kg_m2"])
Is = mat(c4["solar_array_left"]["inertia_about_own_com_S_kg_m2"])
checks["k_component_inertia_frame_label_consistency"] = {
    "verdict": "PASS" if all(r["pass"] for r in label_rows) else "FAIL",
    "records_checked": len(label_rows),
    "rows_failing": [r for r in label_rows if not r["pass"]],
    "numeric_evidence_tensor_is_in_S_axes": {
        "C01_left_panel_diag": [Id[0, 0], Id[1, 1], Id[2, 2]],
        "C04_left_panel_diag": [Is[0, 0], Is[1, 1], Is[2, 2]],
        "yy_zz_swapped_consistent_with_minus90deg_about_x": bool(
            abs(Is[1, 1] - Id[2, 2]) <= 1e-15 and abs(Is[2, 2] - Id[1, 1]) <= 1e-15),
    },
    "resolution_accepted": (
        "inertia_reference_frame_declared = S is correct: the stored matrix equals "
        "R I_local R^T on every record (residual exactly 0.0) and only S-frame component "
        "tensors close the parallel-axis reconstruction of check h. The source frame is now "
        "carried separately as source_tensor_local_frame plus the rotation used."),
    "closes_finding": "WP2-AUD-05",
    "sample_rows": label_rows[:4],
}
if not all(r["pass"] for r in label_rows):
    add_finding("WP2-AUD-V2-05", "LOW", "k_component_inertia_frame_label_consistency",
                "Component inertia frame label still inconsistent with the stored numbers.",
                [r for r in label_rows if not r["pass"]])

# ============================================================ CHECK l  (scope test)
sd = doc["design_checks"]
scope_claim = doc["summary"].get("self_check_scope") or {}
AUDIT_FAMILY_TO_SELF_CHECK = {
    "a_nine_configurations_naming_and_crosswalk": ["configuration_label_crosswalk (artifact section)"],
    "b_no_null_or_absent_required_field": ["uncertainty_positive_no_zero_fill_9_of_9"],
    "c_mass_closure_and_pinned_values": ["mass_closure_sum_of_members_9_of_9",
                                         "urdf_arm_mass_pinned_exactly"],
    "d_inertia_physicality_symmetry_pd_triangle": ["inertia_symmetric_positive_definite_9_of_9",
                                                   "triangle_inequality_9_of_9"],
    "e_principal_axes_orthonormal_right_handed_and_consistent":
        ["principal_axes_orthonormal_right_handed_9_of_9"],
    "f_odr02_panel_failure_attached_stuck": ["branch_mass_delta_constant_9_of_9"],
    "g_uncertainty_covariance_semantics_and_pedigree":
        ["component_inertia_covariance_semantics_all_records",
         "component_uncertainty_magnitude_vs_policy_class_rule",
         "covariance_method_discrimination_vs_forbidden_abs",
         "configuration_inertia_covariance_9_of_9"],
    "h_independent_parallel_axis_inertia_reconstruction": ["parallel_axis_reconstruction_9_of_9"],
    "i_source_register_integrity_sha_and_bytes": ["source_register_sha256_and_bytes_complete"],
    "j_self_reference_pins": ["self_reference_pins_complete"],
    "k_component_inertia_frame_label_consistency": ["component_inertia_frame_label_consistency"],
    "o_v1_to_v2_regression": ["regression_vs_v1_all_physics_bit_identical_9_of_9"],
}
scope_rows = []
for family, self_checks in AUDIT_FAMILY_TO_SELF_CHECK.items():
    present = [name for name in self_checks if name in sd or name.endswith("(artifact section)")]
    scope_rows.append({"audit_check_family": family,
                       "self_check_names_expected": self_checks,
                       "self_check_names_present": present,
                       "covered": len(present) == len(self_checks)})
scope_gap = [r for r in scope_rows if not r["covered"]]
self_claim = bool(doc["summary"]["all_checks_pass"])
self_check_pass_flags = {k: v.get("pass") for k, v in sd.items() if isinstance(v, dict) and "pass" in v}
self_all_true = all(v for v in self_check_pass_flags.values() if v is not None)
checks["l_self_declared_checks_vs_independent_audit"] = {
    "verdict": "PASS" if (not scope_gap and self_claim == self_all_true) else "FAIL",
    "summary_all_checks_pass_claimed": self_claim,
    "self_declared_check_count": len(self_check_pass_flags),
    "self_declared_all_true": self_all_true,
    "self_check_pass_flags": self_check_pass_flags,
    "scope_coverage_rows": scope_rows,
    "scope_gaps": scope_gap,
    "artifact_declares_its_own_scope": bool(scope_claim),
    "artifact_declares_what_it_does_not_cover": bool(scope_claim.get("explicitly_not_covered")),
    "v1_scope_defect": ("V1 claimed all_checks_pass=true while its uncertainty check scanned only "
                        "configuration-level fields and it ran no triangle-inequality, handedness "
                        "or byte-size test"),
    "method": ("each independent audit check family is mapped to the self-check that must cover "
               "it; a family with no corresponding self-check is a scope gap"),
}
if scope_gap or self_claim != self_all_true:
    add_finding("WP2-AUD-V2-SCOPE", "MEDIUM", "l_self_declared_checks_vs_independent_audit",
                "The artifact's self-check scope is narrower than its claim.",
                {"gaps": scope_gap, "claim": self_claim, "flags": self_check_pass_flags})

# ============================================================ CHECK m
nfloat = 0


def count_floats(o):
    global nfloat
    if isinstance(o, (float, int)) and not isinstance(o, bool):
        nfloat += 1
    elif isinstance(o, dict):
        for v in o.values():
            count_floats(v)
    elif isinstance(o, list):
        for v in o:
            count_floats(v)


count_floats(cfgs)
checks["m_nonempty_artifact_guard"] = {
    "verdict": "PASS" if (tgt_bytes and tgt_bytes > 1000 and nfloat > 1000) else "FAIL",
    "detail": {
        "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml_bytes": tgt_bytes,
        "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml_bytes": prior_bytes,
        "DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml_bytes": pol_bytes,
        "aggregate_m7_design_mass_v2.py_bytes": agg_bytes,
        "configurations_parsed": len(cfgs),
        "component_records_parsed": sum(len(c["composition"]) for c in cfgs),
        "numeric_values_parsed_in_configurations": nfloat,
    },
    "note": ("guard against the repo failure mode of a PASS summary over an empty artifact; "
             "every PASS in this audit was computed from these parsed numbers"),
}

# ============================================================ CHECK n
CONTRACT = {
    "mass": lambda c: c["mass"]["value_kg"],
    "center_of_mass_S_m": lambda c: c["center_of_mass"]["xyz_m"],
    "inertia_about_system_cg_in_S_kg_m2": lambda c: c["inertia"]["matrix_kg_m2"],
    "inertia_full_six_components": lambda c: [c["inertia"]["components_kg_m2"][k] for k in KEYS6],
    "principal_inertia_kg_m2": lambda c: c["principal_inertia"]["moments_kg_m2"],
    "principal_axes_S": lambda c: c["principal_inertia"]["axes_S_unit_vectors"],
    "uncertainty": lambda c: [c["mass"]["standard_uncertainty_kg"],
                              c["center_of_mass"]["standard_uncertainty_xyz_m"],
                              c["inertia"]["standard_uncertainty_matrix_kg_m2"],
                              c["inertia"]["uncertainty_covariance"]["covariance_matrix_kg2_m4"],
                              c["principal_inertia"]["moment_standard_uncertainties_kg_m2"],
                              c["principal_inertia"]["axis_angular_standard_uncertainty_rad"]],
    "pedigree": lambda c: [(m["mass_class"], m["com_class"], m["inertia_class"], m["source_ref"])
                           for m in c["composition"]],
    "component_uncertainty_covariance": lambda c: [
        m["inertia_uncertainty"]["covariance_matrix_kg2_m4"] for m in c["composition"]],
}
contract_rows = []
for c in cfgs:
    row = {"configuration_id": c["configuration_id"]}
    ok = True
    for name, fn in CONTRACT.items():
        try:
            v = fn(c)
            tmp = []
            deep_null(v, name, tmp)
            present = v is not None and (not isinstance(v, (list, tuple)) or len(v) > 0)
            good = present and not tmp
        except Exception as ex:  # noqa
            good = False
            row[name + "_error"] = str(ex)
        row[name] = "PRESENT" if good else "MISSING_OR_NULL"
        ok = ok and good
    row["pass"] = ok
    contract_rows.append(row)
frame_ok = all(c["inertia"]["reference_point"] == "configuration_system_CG"
               and c["inertia"]["reference_frame"] == "spacecraft_assembly_frame" for c in cfgs)
checks["n_wp2_output_contract_field_coverage"] = {
    "verdict": "PASS" if (all(r["pass"] for r in contract_rows) and frame_ok) else "FAIL",
    "contract_source": ("M7_EXECUTION_PLAN_V1.md WP2 row + wp10_mech_rl_v4/"
                        "MECH_DYNAMICS_INTERFACE_V4.yaml design_mass_model_binding."
                        "required_fields_per_configuration"),
    "all_nine_carry_inertia_about_configuration_system_CG_in_S": frame_ok,
    "per_configuration": contract_rows,
}
if not (all(r["pass"] for r in contract_rows) and frame_ok):
    add_finding("WP2-AUD-V2-CONTRACT", "HIGH", "n_wp2_output_contract_field_coverage",
                "A contract field required by the WP2 output contract is missing or null.",
                [r for r in contract_rows if not r["pass"]])

# ============================================================ CHECK o  (regression)
reg_rows = []
for c in cfgs:
    cid = c["configuration_id"]
    p = prior_cfgs[cid]
    repaired = bool(c["principal_inertia"].get("axes_handedness_repair_applied"))
    axes_v2 = mat(c["principal_inertia"]["axes_S_unit_vectors"])
    axes_v1 = mat(p["principal_inertia"]["axes_S_unit_vectors"])
    axes_expected = axes_v1.copy()
    if repaired:
        axes_expected[2] = -axes_expected[2]
    pairs = {
        "mass_value_kg": (float(p["mass"]["value_kg"]), float(c["mass"]["value_kg"])),
        "mass_standard_uncertainty_kg": (float(p["mass"]["standard_uncertainty_kg"]),
                                         float(c["mass"]["standard_uncertainty_kg"])),
        "mass_relative_standard_uncertainty": (float(p["mass"]["relative_standard_uncertainty"]),
                                               float(c["mass"]["relative_standard_uncertainty"])),
    }
    vec_pairs = {
        "com_xyz_m": (mat(p["center_of_mass"]["xyz_m"]), mat(c["center_of_mass"]["xyz_m"])),
        "com_u_xyz_m": (mat(p["center_of_mass"]["standard_uncertainty_xyz_m"]),
                        mat(c["center_of_mass"]["standard_uncertainty_xyz_m"])),
        "inertia_matrix": (mat(p["inertia"]["matrix_kg_m2"]), mat(c["inertia"]["matrix_kg_m2"])),
        "inertia_components": (np.array([p["inertia"]["components_kg_m2"][k] for k in KEYS6]),
                               np.array([c["inertia"]["components_kg_m2"][k] for k in KEYS6])),
        "inertia_sigma_matrix": (mat(p["inertia"]["standard_uncertainty_matrix_kg_m2"]),
                                 mat(c["inertia"]["standard_uncertainty_matrix_kg_m2"])),
        "inertia_sigma_components": (
            np.array([p["inertia"]["standard_uncertainty_components_kg_m2"][k] for k in KEYS6]),
            np.array([c["inertia"]["standard_uncertainty_components_kg_m2"][k] for k in KEYS6])),
        "principal_moments": (mat(p["principal_inertia"]["moments_kg_m2"]),
                              mat(c["principal_inertia"]["moments_kg_m2"])),
        "principal_moment_sigma": (
            mat(p["principal_inertia"]["moment_standard_uncertainties_kg_m2"]),
            mat(c["principal_inertia"]["moment_standard_uncertainties_kg_m2"])),
        "axis_angular_sigma": (
            mat(p["principal_inertia"]["axis_angular_standard_uncertainty_rad"]),
            mat(c["principal_inertia"]["axis_angular_standard_uncertainty_rad"])),
        "principal_axes_after_declared_repair": (axes_expected, axes_v2),
    }
    scalar_ok = {k: (a == b) for k, (a, b) in pairs.items()}
    vec_ok = {k: bool(np.array_equal(a, b)) for k, (a, b) in vec_pairs.items()}
    pv1 = {m["component_id"]: m for m in p["composition"]}
    comp_rows = []
    for m in c["composition"]:
        q = pv1[m["component_id"]]
        v1_sigma_matrix = mat(q["inertia_standard_uncertainty_S_kg_m2"])
        v2_sigma = m["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]
        v2_matrix = np.array([[v2_sigma["Ixx"], v2_sigma["Ixy"], v2_sigma["Ixz"]],
                              [v2_sigma["Ixy"], v2_sigma["Iyy"], v2_sigma["Iyz"]],
                              [v2_sigma["Ixz"], v2_sigma["Iyz"], v2_sigma["Izz"]]])
        comp_rows.append({
            "component_id": m["component_id"],
            "mass_identical": float(q["mass_kg"]) == float(m["mass_kg"]),
            "mass_u_identical": float(q["mass_standard_uncertainty_kg"]) == float(m["mass_standard_uncertainty_kg"]),
            "com_identical": bool(np.array_equal(mat(q["com_S_m"]), mat(m["com_S_m"]))),
            "com_u_identical": float(q["com_standard_uncertainty_m_per_axis"]) == float(m["com_standard_uncertainty_m_per_axis"]),
            "inertia_S_identical": bool(np.array_equal(mat(q["inertia_about_own_com_S_kg_m2"]),
                                                       mat(m["inertia_about_own_com_S_kg_m2"]))),
            "v1_negative_sigma_entries": int(np.sum(v1_sigma_matrix < 0.0)),
            "abs_v1_sigma_vs_v2_sigma_max_abs_diff_kg_m2": float(np.max(np.abs(
                np.abs(v1_sigma_matrix) - v2_matrix))),
        })
    row = {"configuration_id": cid, "handedness_repair_applied": repaired,
           "scalar_identity": scalar_ok, "vector_identity": vec_ok,
           "component_rows": comp_rows,
           "pass": bool(all(scalar_ok.values()) and all(vec_ok.values())
                        and all(all(v for k, v in r.items() if isinstance(v, bool))
                                for r in comp_rows))}
    reg_rows.append(row)
v1_neg_entries = sum(r["v1_negative_sigma_entries"] for row in reg_rows for r in row["component_rows"])
v1_neg_records = sum(1 for row in reg_rows for r in row["component_rows"]
                     if r["v1_negative_sigma_entries"] > 0)
checks["o_v1_to_v2_regression"] = {
    "verdict": "PASS" if all(r["pass"] for r in reg_rows) else "FAIL",
    "meaning": ("every mass, CoM, inertia tensor, tensor uncertainty, principal moment, moment "
                "uncertainty and angular uncertainty in V2 is bit-identical to V1; the only "
                "intended numeric change is the declared C09 principal-axis sign repair"),
    "v1_negative_component_sigma_entries": v1_neg_entries,
    "v1_negative_component_sigma_records": v1_neg_records,
    "v2_negative_component_sigma_entries": sum(
        1 for r in cov_rows if not r["reported_sigma_nonnegative"]),
    "configurations_with_handedness_repair": [r["configuration_id"] for r in reg_rows
                                              if r["handedness_repair_applied"]],
    "per_configuration": reg_rows,
    "method": ("both YAML files parsed independently from disk; float equality is exact (==) "
               "and array equality is numpy.array_equal, so any single-ULP drift would FAIL"),
}
if not all(r["pass"] for r in reg_rows):
    add_finding("WP2-AUD-V2-REG", "HIGH", "o_v1_to_v2_regression",
                "A physics value moved between V1 and V2; the remediation was supposed to be "
                "uncertainty-semantics and metadata only.",
                [r for r in reg_rows if not r["pass"]])

# ============================================================ CHECK p
axis = np.array([1.0, 2.0, 3.0]) / np.linalg.norm([1.0, 2.0, 3.0])
ang = math.pi / 6.0
K = np.array([[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]])
Rg = np.eye(3) + math.sin(ang) * K + (1.0 - math.cos(ang)) * (K @ K)
Iloc_t = np.diag([1.0, 2.0, 3.0])
rel_t = 0.18
iscale_t = float(np.trace(Iloc_t) / 3.0)
u_t = np.array([rel_t * 1.0, rel_t * 2.0, rel_t * 3.0,
                rel_t * iscale_t, rel_t * iscale_t, rel_t * iscale_t])
T_t = induced_map(Rg)
C_t = T_t @ np.diag(u_t ** 2) @ T_t.T
sig_t = np.sqrt(np.diag(C_t))
U_t = np.array([[u_t[0], u_t[3], u_t[4]], [u_t[3], u_t[1], u_t[5]], [u_t[4], u_t[5], u_t[2]]])
forbidden_t = np.abs(Rg @ U_t @ Rg.T)
audit_delta = float(np.max(np.abs(sig_t - comp6(forbidden_t))))
published = sd.get("covariance_method_discrimination_vs_forbidden_abs") or {}
pub_delta = published.get("max_abs_difference_kg_m2")
p_pass = bool(audit_delta > 1e-6 and np.all(sig_t >= 0.0)
              and pub_delta is not None and abs(float(pub_delta) - audit_delta) <= 1e-9
              and float(np.min(C_t - np.diag(np.diag(C_t)))) < 0.0)
checks["p_covariance_method_discrimination"] = {
    "verdict": "PASS" if p_pass else "FAIL",
    "purpose": ("prove independently that the implemented uncertainty transformation is a "
                "covariance propagation and NOT the ODR-07-forbidden abs(R U R^T): on a "
                "generic 30 deg rotation about [1,2,3] the two must differ"),
    "audit_recomputed_max_abs_difference_kg_m2": audit_delta,
    "artifact_published_max_abs_difference_kg_m2": pub_delta,
    "audit_matches_published": bool(pub_delta is not None
                                    and abs(float(pub_delta) - audit_delta) <= 1e-9),
    "generic_rotation_covariance_min_signed_off_diagonal_kg2_m4":
        float(np.min(C_t - np.diag(np.diag(C_t)))),
    "generic_rotation_sigma_all_nonnegative": bool(np.all(sig_t >= 0.0)),
    "interpretation": ("a genuinely negative off-diagonal covariance entry coexisting with "
                       "strictly non-negative reported sigmas is exactly the ODR-07 required "
                       "behaviour and is impossible for an abs() implementation"),
}
if not p_pass:
    add_finding("WP2-AUD-V2-METHOD", "HIGH", "p_covariance_method_discrimination",
                "The uncertainty transformation cannot be distinguished from the forbidden "
                "abs() remediation, or the artifact's published discrimination figure is wrong.",
                {"audit_delta": audit_delta, "published": pub_delta})

# ============================================================ CHECK q
signed_perm_rows = [{"configuration_id": r["configuration_id"], "component_id": r["component_id"],
                     "rotation_is_signed_permutation": r["rotation_is_signed_permutation"]}
                    for r in cov_rows]
all_signed_perm = all(r["rotation_is_signed_permutation"] for r in signed_perm_rows)
abs_coincidence = max(
    (r["abs_v1_sigma_vs_v2_sigma_max_abs_diff_kg_m2"]
     for row in reg_rows for r in row["component_rows"]), default=None)
claim = ((doc.get("remediation_register") or {}).get("WP2-AUD-02") or {}).get("numeric_outcome_note", "")
q_pass = bool(all_signed_perm and abs_coincidence == 0.0
              and all(r["audit_rederived_sigma_max_abs_err_kg_m2"] == 0.0 for r in cov_rows)
              and "signed permutation" in claim)
checks["q_forbidden_remediation_detector"] = {
    "verdict": "PASS" if q_pass else "FAIL",
    "question": ("V2's reported sigmas numerically equal abs(V1 entries). Is that because the "
                 "builder took an absolute value, or because every transform in this design is a "
                 "signed permutation, for which the covariance result provably coincides?"),
    "every_component_rotation_is_a_signed_permutation": all_signed_perm,
    "signed_permutation_rows": signed_perm_rows,
    "max_abs_v1_sigma_vs_v2_sigma_difference_kg_m2": abs_coincidence,
    "audit_independent_rederivation_from_covariance_max_err_kg_m2": max(
        r["audit_rederived_sigma_max_abs_err_kg_m2"] for r in cov_rows),
    "artifact_discloses_the_coincidence": bool("signed permutation" in claim),
    "verdict_reason": ("the coincidence is data-driven, not method-driven: the auditor "
                       "re-derived every sigma from T(R) diag(u_local^2) T(R)^T with zero error, "
                       "confirmed all 56 component rotations are signed permutations (for which "
                       "T(R) C T(R)^T stays diagonal so sqrt(diag) equals the magnitude), and "
                       "check p shows the two methods diverge on a generic rotation"),
}
if not q_pass:
    add_finding("WP2-AUD-V2-ABS", "HIGH", "q_forbidden_remediation_detector",
                "Cannot rule out that the uncertainty fix is an abs() of the V1 rotated matrix.",
                {"signed_perm": all_signed_perm, "coincidence": abs_coincidence})

# ============================================================ CHECK r
text = open(TARGET, "r", encoding="utf-8").read()
FORBIDDEN_TOKENS = ["FLIGHT_QUALIFIED_", "QUALIFICATION_PASS", "AS_BUILT_VERIFIED",
                    "MEASURED_MASS", "LAUNCH_LOAD_PASS", "FLIGHT_MOS_PASS",
                    "MANUFACTURING_RELEASE"]
hits = {tok: text.count(tok) for tok in FORBIDDEN_TOKENS if text.count(tok) > 0}
r_pass = bool(not hits and doc.get("next_stage_authorized") is False
              and doc.get("design_not_flight_qualified") is True
              and doc.get("review_status") == "PENDING_OWNER_REVIEW"
              and doc["summary"]["use_authorization"].startswith("ENGINEERING_DESIGN_ANALYSIS_ONLY"))
checks["r_claim_hygiene"] = {
    "verdict": "PASS" if r_pass else "FAIL",
    "forbidden_claim_tokens_found": hits,
    "next_stage_authorized": doc.get("next_stage_authorized"),
    "review_status": doc.get("review_status"),
    "design_not_flight_qualified": doc.get("design_not_flight_qualified"),
    "use_authorization": doc["summary"]["use_authorization"],
    "retained_hold_count": len(doc.get("retained_holds") or []),
    "release_prohibition_count": len(doc.get("release_prohibitions") or []),
    "method": "literal token scan over the artifact bytes plus explicit flag inspection",
}
if not r_pass:
    add_finding("WP2-AUD-V2-CLAIM", "HIGH", "r_claim_hygiene",
                "The artifact makes or implies a forbidden flight/qualification/measurement "
                "claim, or does not keep next_stage_authorized false.", hits)

# ============================================================ verdict
fail_ids = [k for k, v in checks.items() if v["verdict"] == "FAIL"]
hard = [f for f in findings if f["severity"] in ("CRITICAL", "HIGH")]
soft = [f for f in findings if f["severity"] == "MEDIUM"]
minor = [f for f in findings if f["severity"].startswith("LOW")]
if hard:
    overall = "AUDIT_FAIL_HARD_FINDINGS"
elif soft:
    overall = "AUDIT_PASS_WITH_FINDINGS_NO_HARD_DEFECT"
elif minor:
    overall = "AUDIT_PASS_WITH_MINOR_METADATA_FINDINGS"
else:
    overall = "AUDIT_PASS_CLEAN"

audit_v1 = json.load(open(AUDIT_V1, encoding="utf-8"))
v1_findings = {f["finding_id"]: f["severity"] for f in audit_v1["findings"]}
closure = {
    "WP2-AUD-01": {"severity_in_v1": v1_findings.get("WP2-AUD-01"),
                   "closing_check": "a_nine_configurations_naming_and_crosswalk",
                   "closed": checks["a_nine_configurations_naming_and_crosswalk"]["verdict"] == "PASS"},
    "WP2-AUD-02": {"severity_in_v1": v1_findings.get("WP2-AUD-02"),
                   "closing_check": "g_uncertainty_covariance_semantics_and_pedigree",
                   "supporting_checks": ["p_covariance_method_discrimination",
                                         "q_forbidden_remediation_detector"],
                   "closed": bool(checks["g_uncertainty_covariance_semantics_and_pedigree"]["verdict"] == "PASS"
                                  and checks["p_covariance_method_discrimination"]["verdict"] == "PASS"
                                  and checks["q_forbidden_remediation_detector"]["verdict"] == "PASS")},
    "WP2-AUD-03": {"severity_in_v1": v1_findings.get("WP2-AUD-03"),
                   "closing_check": "i_source_register_integrity_sha_and_bytes",
                   "closed": checks["i_source_register_integrity_sha_and_bytes"]["verdict"] == "PASS"},
    "WP2-AUD-04": {"severity_in_v1": v1_findings.get("WP2-AUD-04"),
                   "closing_check": "j_self_reference_pins",
                   "closed": checks["j_self_reference_pins"]["verdict"] == "PASS"},
    "WP2-AUD-05": {"severity_in_v1": v1_findings.get("WP2-AUD-05"),
                   "closing_check": "k_component_inertia_frame_label_consistency",
                   "closed": checks["k_component_inertia_frame_label_consistency"]["verdict"] == "PASS"},
    "WP2-AUD-06": {"severity_in_v1": v1_findings.get("WP2-AUD-06"),
                   "closing_check": "e_principal_axes_orthonormal_right_handed_and_consistent",
                   "closed": checks["e_principal_axes_orthonormal_right_handed_and_consistent"]["verdict"] == "PASS"},
}
all_closed = all(v["closed"] for v in closure.values())

out = {
    "schema": "M7_WP2_DESIGN_MASS_AUDIT_V2",
    "generated_local": now_iso(),
    "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
    "work_package": "WP2_DESIGN_MASS",
    "role": "A2_MASS_FRAMES",
    "audit_role": (
        "Independent audit of SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml and of the V1->V2 "
        "remediation. Neither aggregate_m7_design_mass.py nor aggregate_m7_design_mass_v2.py "
        "was imported or executed; every number here was recomputed with numpy from the two "
        "artifacts' own declared records and from real file bytes with hashlib. The auditor "
        "implements its own symmetric-tensor induced map, so the covariance claim is checked "
        "against an independent implementation, not against the builder's."),
    "audited_artifact": {
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/"
                "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml",
        "sha256": tgt_sha, "bytes": tgt_bytes,
        "declared_schema": doc["schema"],
        "declared_generated_local": doc["generated_local"],
        "declared_generated_clock_source": doc.get("generated_clock_source"),
        "declared_status": doc["status"],
        "declared_review_status": doc.get("review_status"),
    },
    "superseded_artifact": {
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/"
                "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml",
        "sha256": prior_sha, "bytes": prior_bytes,
        "declared_generated_local": prior["generated_local"],
        "retained_on_disk_unmodified": True,
    },
    "auditor": {
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/"
                "WP2_INDEPENDENT_AUDIT_V2.py",
        "python": sys.version.split()[0], "numpy": np.__version__,
        "aggregator_executed": False,
        "supersedes_auditor": "WP2_INDEPENDENT_AUDIT_V1.py (checks a..n carried forward)",
    },
    "overall_verdict": overall,
    "checks_failed": fail_ids,
    "v1_finding_closure": closure,
    "v1_findings_all_closed": all_closed,
    "checks": checks,
    "findings": findings,
    "finding_counts": {
        "CRITICAL": sum(1 for f in findings if f["severity"] == "CRITICAL"),
        "HIGH": sum(1 for f in findings if f["severity"] == "HIGH"),
        "MEDIUM": sum(1 for f in findings if f["severity"] == "MEDIUM"),
        "LOW": sum(1 for f in findings if f["severity"].startswith("LOW")),
    },
    "gate_a_criterion_10_input": {
        "criterion": "10 NINE_CONFIG_DESIGN_MASS",
        "odr07_blocking_findings": ["WP2-AUD-02", "WP2-AUD-06"],
        "odr07_blocking_findings_closed": bool(closure["WP2-AUD-02"]["closed"]
                                               and closure["WP2-AUD-06"]["closed"]),
        "wp2_recommendation": (
            "WP2 evidence supports Gate A criterion 10; the criterion state itself is A0's "
            "ruling, not WP2's. Design-level only: the model remains PENDING_CALIBRATION with "
            "no measured or as-built value anywhere, so criterion 10 cannot be read as an "
            "as-built or flight-qualified mass property."),
        "retained_open_items": ["AS_BUILT_MASS_CORRELATION_HOLD", "PENDING_CALIBRATION",
                                "CORRELATION_REVIEW_REQUIRED_BEFORE_CALIBRATION_UPGRADE",
                                "LOAD_BRIDGE_CANDIDATE_MEMBER_PENDING_WP1_CONFIRMATION"],
    },
    "audit_source_register": {},
    "prohibitions_honored": {
        "audited_artifact_modified_by_this_audit": False,
        "aggregator_rerun_by_this_audit": False,
        "freecad_launched": False,
        "abaqus_launched": False,
        "zero_fill_of_unknowns": False,
        "other_wp_files_touched": False,
        "hash_copied_from_sibling_document": False,
    },
}
for k, v in [
    ("SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml", TARGET),
    ("SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml", PRIOR),
    ("DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml", POLICY),
    ("DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml", POLICY_V1),
    ("aggregate_m7_design_mass_v2.py", AGG),
    ("aggregate_m7_design_mass.py", AGG_V1),
    ("WP2_DESIGN_MASS_AUDIT_V1.json", AUDIT_V1),
    ("m4_configuration_library_v1", M4_LIB),
    ("m5_configuration_geometry_contract", M5_CON),
    ("m7_owner_decision_register",
     os.path.join(REPO, "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                        "00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml")),
    ("m7_terminal_closure_contract",
     os.path.join(REPO, "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
                        "00_authority/M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml")),
]:
    s, b = sha256_and_size(v)
    out["audit_source_register"][k] = {
        "path": os.path.relpath(v, REPO).replace("\\", "/"), "sha256": s, "bytes": b}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False, sort_keys=False)

print("WROTE", OUT, os.path.getsize(OUT), "bytes")
print("OVERALL:", overall)
print("FAILED CHECKS:", fail_ids)
print("V1 FINDINGS CLOSED:", all_closed, {k: v["closed"] for k, v in closure.items()})
for f in findings:
    print("  -", f["finding_id"], f["severity"], f["check_id"], "|", f["summary"][:110])
