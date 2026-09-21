#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Emit wp2_design_mass/receipt.json (V2) from the real bytes on disk.

Every sha256/bytes pair is computed with hashlib over the actual file at emit
time. Every number in numeric_summary is read out of the INDEPENDENT audit's
recomputed values, not copied from a sibling document and not restated from the
builder's own claim.

The previous receipt is preserved byte-identical as receipt_V1_SUPERSEDED.json
so its own pinned hashes stay verifiable.
"""
import hashlib
import json
import os
import subprocess

import yaml

REPO = r"f:/China Graduate Future Flight Vehicle Innovation Competition"
M7 = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
WP2 = M7 + "/wp2_design_mass"
OUT = os.path.join(REPO, WP2, "receipt.json")


def hb(rel):
    p = os.path.join(REPO, rel)
    if not os.path.exists(p):
        return {"path": rel, "sha256": None, "bytes": None, "status": "FILE_ABSENT"}
    h = hashlib.sha256()
    n = 0
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return {"path": rel, "sha256": h.hexdigest().upper(), "bytes": n}


now = subprocess.check_output(["date", "-Iseconds"]).decode().strip()

audit = json.load(open(os.path.join(REPO, WP2, "WP2_DESIGN_MASS_AUDIT_V2.json"), encoding="utf-8"))
audit_v1 = json.load(open(os.path.join(REPO, WP2, "WP2_DESIGN_MASS_AUDIT_V1.json"), encoding="utf-8"))
negctl = json.load(open(os.path.join(REPO, WP2, "WP2_AUDIT_NEGATIVE_CONTROL_V1.json"), encoding="utf-8"))
doc = yaml.safe_load(open(os.path.join(REPO, WP2, "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml"), encoding="utf-8"))
ch = audit["checks"]

failed = [k for k, v in ch.items() if v["verdict"] == "FAIL"]
passed = [k for k, v in ch.items() if v["verdict"] == "PASS"]

# self-check breadth, counted from the two artifacts rather than asserted
doc_v1 = yaml.safe_load(open(os.path.join(REPO, WP2, "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml"),
                             encoding="utf-8"))


def check_group_counts(d):
    dcx = d["design_checks"]
    return {"groups": len(dcx),
            "groups_with_explicit_pass_flag": sum(
                1 for v in dcx.values() if isinstance(v, dict) and "pass" in v)}


SC_V1 = check_group_counts(doc_v1)
SC_V2 = check_group_counts(doc)
cov_rows = ch["g_uncertainty_covariance_semantics_and_pedigree"]["per_component_rows"]
axes_rows = ch["e_principal_axes_orthonormal_right_handed_and_consistent"]["per_configuration"]
reg_rows = ch["o_v1_to_v2_regression"]["per_configuration"]
tri_rows = ch["d_inertia_physicality_symmetry_pd_triangle"]["per_configuration"]

status = (
    "WP2_ODR07_REMEDIATION_COMPLETE_"
    "AUD_01_02_03_04_05_06_CLOSED_WITH_INDEPENDENT_EVIDENCE_"
    "NO_PHYSICS_VALUE_MOVED_"
    "DESIGN_LEVEL_PENDING_CALIBRATION_NOT_MEASURED_NOT_FLIGHT_QUALIFIED"
)
verdict = (
    "All three MEDIUM and all three LOW findings of WP2_DESIGN_MASS_AUDIT_V1.json are closed "
    "and re-verified by an independent audit that does not import either aggregator. "
    "WP2-AUD-02: component inertia uncertainty is now a COVARIANCE per ODR-07 "
    "(C_global = T(R) C_local T(R)^T on [Ixx,Iyy,Izz,Ixy,Ixz,Iyz], signed off-diagonals "
    "permitted, sigma_i = sqrt(C_global[i,i])); all 44 negative entries in 11 component records "
    "are gone, 0 negative sigmas remain over 56 component records x 6 components, and the four "
    "ODR-07 checks (covariance_symmetric, covariance_positive_semidefinite, "
    "variance_diagonal_nonnegative, reported_sigma_nonnegative) pass on every record. The "
    "forbidden remediations (abs, clipping, deletion) were not used: the auditor re-derived every "
    "covariance and sigma from the published local sigma and rotation with 0.0 error, proved all "
    "56 component rotations are signed permutations, and demonstrated on a generic 30 deg "
    "rotation that the covariance result differs from abs(R U R^T) by 0.2489 kg*m^2 while the "
    "covariance carries genuinely negative off-diagonal entries. WP2-AUD-06: the C09 "
    "principal-axis triad is right-handed, det(R) = +1.0000000000000002 after a declared minimal "
    "sign repair of the third axis; all nine configurations now satisfy det(R) = +1 within "
    "1e-12 and R I R^T still reproduces the reported moments. WP2-AUD-01: a bidirectional "
    "9-row M4 / M4-legacy / M5 crosswalk with injective reverse maps and a POST_CAPTURE "
    "token-collision warning is published; neither side renamed. WP2-AUD-03/04/05: byte sizes on "
    "all 25 source_register entries, aggregator sha256 pinned, and "
    "inertia_reference_frame_declared resolved to S with the source frame and rotation carried "
    "separately. NO PHYSICS VALUE MOVED: every mass, CoM, inertia tensor, tensor uncertainty, "
    "principal moment, moment uncertainty and angular uncertainty is bit-identical to V1 by "
    "exact float comparison in 9/9 configurations and 56/56 component records. The self-check "
    f"was widened from {SC_V1['groups']} to {SC_V2['groups']} groups "
    f"({SC_V1['groups_with_explicit_pass_flag']} -> "
    f"{SC_V2['groups_with_explicit_pass_flag']} carrying an explicit pass flag) so its scope "
    "matches its claim, with 0 scope gaps against the independent audit's 18 check families, and "
    "its clean PASS is falsification-tested: 5 of 6 deliberate corruptions are caught and the "
    "6th is proven to be a null mutation. DESIGN LEVEL ONLY: PENDING_CALIBRATION, nothing "
    "measured, nothing as-built, Gate B untouched, next_stage_authorized false."
)

receipt = {
    "schema": "M7_WP2_DESIGN_MASS_RECEIPT_V2",
    "generated_local": now,
    "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
    "work_package": "WP2_DESIGN_MASS",
    "role": "A2_MASS_FRAMES",
    "status": status,
    "verdict": verdict,
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "receipt_role": (
        "Issued on the strength of an INDEPENDENT audit (WP2_INDEPENDENT_AUDIT_V2.py) of "
        "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml plus a negative control on that audit, not on "
        "the strength of the aggregator's own design_checks. The aggregator WAS re-executed this "
        "loop (that is what produced V2); the audit did not execute it."),
    "supersedes_receipt": {
        **hb(WP2 + "/receipt_V1_SUPERSEDED.json"),
        "note": ("byte-identical copy of the previous receipt.json, preserved so its own pinned "
                 "hashes remain verifiable after this file replaced it"),
        "previous_status": "WP2_COMPLETE_9_OF_9_CONFIGURATIONS_AUDITED_PHYSICS_AND_PINNED_VALUES_PASS_3_MEDIUM_3_LOW_METADATA_FINDINGS_OPEN",
    },
    "builder": hb(WP2 + "/aggregate_m7_design_mass_v2.py"),
    "builder_reused_module": hb(WP2 + "/aggregate_m7_design_mass.py"),
    "policy_builder": hb(WP2 + "/build_uncertainty_policy_v2.py"),
    "auditor": hb(WP2 + "/WP2_INDEPENDENT_AUDIT_V2.py"),
    "auditor_v1_superseded": hb(WP2 + "/WP2_INDEPENDENT_AUDIT_V1.py"),
    "negative_control": hb(WP2 + "/wp2_audit_negative_control.py"),
    "receipt_builder": hb(WP2 + "/build_wp2_receipt_v2.py"),
    "receipt_builder_v1_superseded": hb(WP2 + "/build_wp2_receipt.py"),
    "contract_outputs": [
        hb(WP2 + "/DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml"),
        hb(WP2 + "/aggregate_m7_design_mass_v2.py"),
        hb(WP2 + "/SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml"),
    ],
    "produced_files_this_loop": [
        hb(WP2 + "/DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml"),
        hb(WP2 + "/build_uncertainty_policy_v2.py"),
        hb(WP2 + "/aggregate_m7_design_mass_v2.py"),
        hb(WP2 + "/SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml"),
        hb(WP2 + "/WP2_INDEPENDENT_AUDIT_V2.py"),
        hb(WP2 + "/WP2_DESIGN_MASS_AUDIT_V2.json"),
        hb(WP2 + "/wp2_audit_negative_control.py"),
        hb(WP2 + "/WP2_AUDIT_NEGATIVE_CONTROL_V1.json"),
        hb(WP2 + "/build_wp2_receipt_v2.py"),
        hb(WP2 + "/receipt_V1_SUPERSEDED.json"),
    ],
    "self_hash_note": (
        "receipt.json is deliberately absent from produced_files_this_loop: a receipt cannot "
        "hash itself before it is written, and hashing the file that is about to be replaced "
        "would pin the superseded bytes under a current-file label. The previous receipt's bytes "
        "are pinned instead under supersedes_receipt (receipt_V1_SUPERSEDED.json)."),
    "superseded_but_retained_unmodified": [
        {**hb(WP2 + "/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml"),
         "why": "byte-level V1->V2 comparison base; audit V1 and the V1 receipt pin this hash"},
        {**hb(WP2 + "/DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml"),
         "why": "pinned by SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml; class values proved identical in V2"},
        {**hb(WP2 + "/aggregate_m7_design_mass.py"),
         "why": "imported by the V2 builder for the physics; keeps V1 independently reproducible"},
        {**hb(WP2 + "/WP2_DESIGN_MASS_AUDIT_V1.json"),
         "why": "the finding register this loop closes; must stay intact as the before-state"},
        {**hb(WP2 + "/WP2_INDEPENDENT_AUDIT_V1.py"), "why": "V2 auditor is a superset of it"},
        {**hb(WP2 + "/build_wp2_receipt.py"), "why": "builder of the superseded receipt"},
    ],
    "findings_closed": {
        fid: {
            "severity_in_v1": rec["severity_in_v1"],
            "closing_audit_check": rec["closing_check"],
            "supporting_checks": rec.get("supporting_checks", []),
            "closed": rec["closed"],
        } for fid, rec in audit["v1_finding_closure"].items()
    },
    "all_v1_findings_closed": audit["v1_findings_all_closed"],
    "audit_summary": {
        "audit_artifact": WP2 + "/WP2_DESIGN_MASS_AUDIT_V2.json",
        "overall_verdict": audit["overall_verdict"],
        "checks_total": len(ch),
        "checks_pass": len(passed),
        "checks_fail": len(failed),
        "checks_failed_ids": failed,
        "finding_counts": audit["finding_counts"],
        "per_check": {k: v["verdict"] for k, v in ch.items()},
        "aggregator_executed_by_auditor": False,
        "v1_audit_for_comparison": {
            **hb(WP2 + "/WP2_DESIGN_MASS_AUDIT_V1.json"),
            "overall_verdict": audit_v1["overall_verdict"],
            "checks_failed_ids": audit_v1["checks_failed"],
            "finding_counts": audit_v1["finding_counts"],
        },
    },
    "audit_negative_control": {
        "artifact": WP2 + "/WP2_AUDIT_NEGATIVE_CONTROL_V1.json",
        "mutations_run": negctl["summary"]["mutations_run"],
        "mutations_detected": negctl["summary"]["mutations_detected"],
        "all_expectations_met": negctl["summary"]["all_expectations_met"],
        "real_artifact_unmodified": negctl["real_artifact_unmodified"]["unchanged"],
        "undetected_mutation_is_null": [
            r["tag"] for r in negctl["results"]
            if not r["detected"] and r["is_null_mutation_on_reported_sigmas"]],
        "why_it_matters": (
            "a clean audit PASS is worthless unless the audit fails on defective input; this "
            "records that it does"),
    },
    "numeric_summary": {
        "configuration_count": len(doc["configurations"]),
        "component_records": ch["g_uncertainty_covariance_semantics_and_pedigree"][
            "component_record_count_audited"],
        "design_mass_C01_to_C07_kg": float(doc["configurations"][0]["mass"]["value_kg"]),
        "design_mass_C08_kg": float([c for c in doc["configurations"]
                                     if c["configuration_id"] == "C08"][0]["mass"]["value_kg"]),
        "design_mass_C09_kg": float([c for c in doc["configurations"]
                                     if c["configuration_id"] == "C09"][0]["mass"]["value_kg"]),
        "mass_closure_max_abs_error_kg": max(
            r["abs_error_kg"] for r in ch["c_mass_closure_and_pinned_values"][
                "mass_sum_per_configuration"]),
        "pinned_component_mass_rows_checked": ch["c_mass_closure_and_pinned_values"][
            "pinned_row_count"],
        "pinned_component_mass_max_abs_error_kg": max(
            r["abs_error_kg"] for r in ch["c_mass_closure_and_pinned_values"]["pinned_value_rows"]),
        "b601_arm_mass_kg_bit_exact": 4.695555949342986,
        "m3r_design_budget_kg_bit_exact": 0.7619,
        "parallel_axis_tensor_recompute_max_abs_error_kg_m2": max(
            r["max_abs_error_vs_reported_kg_m2"] for r in ch[
                "h_independent_parallel_axis_inertia_reconstruction"]["per_configuration"]),
        "min_eigenvalue_over_all_configurations_kg_m2": min(
            r["min_eigenvalue_kg_m2"] for r in tri_rows),
        "triangle_inequality_tightest_relative_margin": min(
            r["triangle_min_margin_relative"] for r in tri_rows),
        "det_R_before_repair": {
            c["configuration_id"]: c["principal_inertia"]["axes_determinant_before_repair"]
            for c in doc["configurations"]},
        "det_R_after_repair_recomputed_by_audit": ch[
            "e_principal_axes_orthonormal_right_handed_and_consistent"]["det_R_all_configurations"],
        "left_handed_configurations_after_fix": ch[
            "e_principal_axes_orthonormal_right_handed_and_consistent"]["left_handed_configurations"],
        "handedness_repairs_applied": [c["configuration_id"] for c in doc["configurations"]
                                       if c["principal_inertia"]["axes_handedness_repair_applied"]],
        "principal_axes_orthonormality_max_residual": max(
            r["orthonormality_max_abs_residual_RRt_minus_I"] for r in axes_rows),
        "principal_moment_diagonalisation_max_abs_error_kg_m2": max(
            r["R_I_Rt_diagonal_vs_reported_moments_max_abs_err_kg_m2"] for r in axes_rows),
        "v1_negative_component_sigma_entries": ch["o_v1_to_v2_regression"][
            "v1_negative_component_sigma_entries"],
        "v1_negative_component_sigma_records": ch["o_v1_to_v2_regression"][
            "v1_negative_component_sigma_records"],
        "v2_negative_component_sigma_entries": ch["o_v1_to_v2_regression"][
            "v2_negative_component_sigma_entries"],
        "covariance_records_checked": len(cov_rows),
        "covariance_symmetry_max_abs_residual_kg2_m4": max(
            r["covariance_symmetry_max_abs_residual_kg2_m4"] for r in cov_rows),
        "covariance_min_eigenvalue_over_all_records_kg2_m4": min(
            r["covariance_min_eigenvalue_kg2_m4"] for r in cov_rows),
        "variance_diagonal_min_over_all_records_kg2_m4": min(
            r["variance_diagonal_min_kg2_m4"] for r in cov_rows),
        "reported_sigma_min_over_all_records_kg_m2": min(
            r["reported_sigma_min_kg_m2"] for r in cov_rows),
        "audit_rederived_covariance_max_abs_error_kg2_m4": max(
            r["audit_rederived_covariance_max_abs_err_kg2_m4"] for r in cov_rows),
        "audit_rederived_sigma_max_abs_error_kg_m2": max(
            r["audit_rederived_sigma_max_abs_err_kg_m2"] for r in cov_rows),
        "local_sigma_vs_policy_P7_max_abs_error_kg_m2": max(
            r["local_sigma_vs_policy_P7_max_abs_err_kg_m2"] for r in cov_rows),
        "component_rotations_that_are_signed_permutations": sum(
            1 for r in cov_rows if r["rotation_is_signed_permutation"]),
        "method_discrimination_generic_rotation_delta_kg_m2": ch[
            "p_covariance_method_discrimination"]["audit_recomputed_max_abs_difference_kg_m2"],
        "method_discrimination_generic_rotation_min_signed_off_diagonal_kg2_m4": ch[
            "p_covariance_method_discrimination"][
            "generic_rotation_covariance_min_signed_off_diagonal_kg2_m4"],
        "regression_configurations_bit_identical": sum(1 for r in reg_rows if r["pass"]),
        "regression_component_rows_checked": sum(len(r["component_rows"]) for r in reg_rows),
        "source_register_entries": ch["i_source_register_integrity_sha_and_bytes"]["entry_count"],
        "source_register_sha256_verified": ch["i_source_register_integrity_sha_and_bytes"][
            "sha256_verified_count"],
        "source_register_bytes_verified": ch["i_source_register_integrity_sha_and_bytes"][
            "bytes_verified_count"],
        "self_check_groups_v1": SC_V1["groups"],
        "self_check_groups_v2": SC_V2["groups"],
        "self_check_groups_with_pass_flag_v1": SC_V1["groups_with_explicit_pass_flag"],
        "self_check_groups_with_pass_flag_v2": SC_V2["groups_with_explicit_pass_flag"],
        "independent_audit_check_families": len(ch),
        "self_declared_check_groups": ch["l_self_declared_checks_vs_independent_audit"][
            "self_declared_check_count"],
        "self_check_scope_gaps": len(ch["l_self_declared_checks_vs_independent_audit"]["scope_gaps"]),
        "numeric_values_parsed_in_configurations": ch["m_nonempty_artifact_guard"]["detail"][
            "numeric_values_parsed_in_configurations"],
    },
    "what_changed_v1_to_v2": [
        "component inertia uncertainty replaced by inertia_uncertainty{covariance_matrix_kg2_m4, "
        "component_standard_uncertainty_kg_m2, local_frame_standard_uncertainty_kg_m2, checks}",
        "C09 principal-axis third axis sign-repaired so det(R) = +1; handedness convention declared",
        "configuration_label_crosswalk section added; m5_geometry_contract_name added per configuration",
        "source_register: byte sizes on every entry, plus V1 artifact / V1 aggregator / policy "
        "lineage entries; every V1 pinned hash re-verified against disk",
        "aggregator and policy pinned by sha256+bytes inside the artifact",
        "inertia_reference_frame_declared = S; source_tensor_local_frame, "
        "source_to_S_rotation_rows and inertia_about_own_com_source_frame_kg_m2 added",
        "configuration-level uncertainty_covariance (6x6 from the same GUM Jacobian) added; the "
        "3x3 sigma layout is retained and explicitly labelled as not-a-covariance",
        "generated_clock_source, review_status, next_stage_authorized added",
        "header mass constants derived from the computed C01 mass instead of hand-written",
        "design_checks widened from 7 to 22 groups with an explicit scope declaration",
    ],
    "what_did_not_change": [
        "every configuration mass, CoM and inertia tensor (bit-identical)",
        "every configuration-level standard uncertainty (bit-identical)",
        "every principal moment and moment uncertainty (bit-identical)",
        "every axis angular standard uncertainty and degeneracy flag (bit-identical)",
        "every component mass, component CoM and component S-frame inertia tensor (bit-identical)",
        "every uncertainty class value in the policy (asserted identical to V1)",
        "the member set, the composition ruling and all pedigree classes",
    ],
    "retained_holds": list(doc["retained_holds"]) + [
        "PENDING_CALIBRATION: every uncertainty here is a declared Type-B policy value; no "
        "weighing or metrology exists anywhere in the input chain",
        "CORRELATION_REVIEW_REQUIRED: policy P8 declares component independence, so the input "
        "covariance is diagonal; rotation-induced correlation is captured but source correlation "
        "is not, and a correlation review is required before any calibration upgrade",
        "COMPONENT_UNCERTAINTY_ABS_COINCIDENCE_IS_DATA_SPECIFIC: all 56 component transforms in "
        "this design are signed permutations, so the covariance-derived sigma happens to equal "
        "the magnitude of the V1 rotated entries; a future non-axis-aligned mounting will make "
        "the two diverge and MUST use the covariance path",
        "LOAD_BRIDGE_CANDIDATE_MEMBER_PENDING_WP1_STRUCTURE_CONFIRMATION",
        "M3R_AS_BUILT_MEASUREMENT_OPEN (ODR-05 retained item)",
        "MECHANICAL_FLIGHT_QUALIFICATION_RELEASED (Gate B) remains HOLD",
        "MEMORY_GATE_6GIB_FAILED_ON_THIS_HOST_DECLARED_FAILED",
    ],
    "integration_actions_required_by_a0_a7": [
        "re-point wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V4.yaml design_mass_model_binding at "
        "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml and DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml and "
        "backfill both sha256 values (they still read PENDING_SIBLING_HASH against the V1 "
        "filenames). WP2 must not edit a sibling work package's files.",
        "the C08/C09 alias crosswalk WP10 was waiting for is now published in "
        "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml -> configuration_label_crosswalk",
        "re-point wp9_release_package references (receipt.json list, VERIFICATION_MATRIX_V1.csv, "
        "BOM_V3_DESIGN.csv) from the V1 to the V2 filename",
        "record in 12_release/M7_CROSS_WP_REFERENCE_RECONCILIATION_V1 that V1 is superseded but "
        "retained, so an old pinned V1 hash is lineage, not drift",
        "Gate A criterion 10: WP2 evidence now supports it (ODR-07 blockers WP2-AUD-02 and "
        "WP2-AUD-06 are closed); the criterion state itself remains A0's ruling",
    ],
    "authority_statements": {
        "ODR-01": "T_SM = [185.25,0,0] mm + Ry(90 deg); stations 198.0/208.0/210.405 mm are a "
                  "geometric feature stack, not a second dynamics frame",
        "ODR-02": "panel failure = attached-stuck, never jettison - re-verified numerically",
        "ODR-05": "M3R 0.7619 kg = DESIGN_BUDGET, confidence B; as-built open",
        "ODR-07": "component inertia uncertainty is a covariance; abs/clip/delete forbidden; "
                  "four covariance checks mandatory - implemented and independently re-derived",
        "ODR-14": "Gate A criterion 10 could not be PASS while WP2-AUD-02 or WP2-AUD-06 was "
                  "open; both are now closed with evidence, and closing them is not the same "
                  "act as declaring the criterion PASS",
        "ODR-16": "right-handed principal frames are required for frame_tree_matched in the "
                  "MECHANICAL_TO_EMBODIED handoff gate; all nine are now proper rotations",
        "L0": "B601 arm 4.695555949342986 kg ACCEPTED_URDF, never overridden - bit-exact in all "
              "9 configurations",
        "classification": "candidate != authority; design != flight-qualified; analysis != test",
    },
    "prohibitions_honored": {
        "physics_value_changed_to_make_a_check_pass": False,
        "forbidden_abs_clip_or_delete_remediation_used": False,
        "v1_artifact_modified": False,
        "v1_audit_modified": False,
        "sibling_work_package_files_modified": False,
        "freecad_launched": False,
        "solidworks_launched": False,
        "abaqus_launched": False,
        "formal_fea_run_count": 0,
        "zero_fill_of_unknowns": False,
        "fabricated_or_copied_hash": False,
        "l0_urdf_overridden": False,
        "candidate_promoted_to_manufacturing_authority": False,
        "flight_launcher_or_qualification_claim_made": False,
        "m8_or_m9_planning_artifact_created": False,
        "self_authorized_next_stage": False,
        "memory_gate_6gib_status": "FAILED_ON_THIS_HOST_DECLARED_FAILED",
    },
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(receipt, f, indent=2, ensure_ascii=False)

print("WROTE", OUT, os.path.getsize(OUT), "bytes")
print("status  :", status)
print("audit   :", audit["overall_verdict"], "failed:", failed)
print("closed  :", receipt["all_v1_findings_closed"])
print("negctl  :", negctl["summary"]["mutations_detected"], "/", negctl["summary"]["mutations_run"],
      "expectations met:", negctl["summary"]["all_expectations_met"])
