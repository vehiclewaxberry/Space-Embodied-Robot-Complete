#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Emit wp2_design_mass/receipt.json from the real bytes on disk.

Every sha256/bytes pair below is computed with hashlib over the actual file
at emit time. Nothing is copied from a sibling receipt.
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
        return {"path": rel, "sha256": None, "bytes": None,
                "status": "FILE_ABSENT"}
    h = hashlib.sha256()
    n = 0
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return {"path": rel, "sha256": h.hexdigest().upper(), "bytes": n}


now = subprocess.check_output(["date", "-Iseconds"]).decode().strip()

audit = json.load(open(os.path.join(REPO, WP2,
                                    "WP2_DESIGN_MASS_AUDIT_V1.json"),
                       encoding="utf-8"))
doc = yaml.safe_load(open(os.path.join(REPO, WP2,
                                       "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml"),
                          encoding="utf-8"))
ch = audit["checks"]

# --------------------------------------------------------------- sources
src_keys = {}
for k, rec in doc["source_register"].items():
    src_keys[k] = hb(rec["path"])
    src_keys[k]["declared_sha256_in_artifact"] = rec["sha256"].upper()
    src_keys[k]["sha256_reverified_this_loop"] = (
        src_keys[k]["sha256"] == rec["sha256"].upper())
src_keys["wp10_mech_dynamics_interface_v4"] = hb(
    M7 + "/wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V4.yaml")

# ------------------------------------------------------------- verdicts
failed = [k for k, v in ch.items() if v["verdict"] == "FAIL"]
passed = [k for k, v in ch.items() if v["verdict"] == "PASS"]
fc = audit["finding_counts"]

status = (
    "WP2_COMPLETE_9_OF_9_CONFIGURATIONS_AUDITED_"
    "PHYSICS_AND_PINNED_VALUES_PASS_"
    "3_MEDIUM_3_LOW_METADATA_FINDINGS_OPEN"
)
verdict = (
    "9/9 configurations carry mass, CoM, full symmetric inertia tensor about "
    "the configuration system CG in S, principal moments, principal axes, "
    "uncertainty and pedigree; independently recomputed. HARD PHYSICS PASS: "
    "all 9 tensors exactly symmetric, positive-definite (min eigenvalue "
    "0.2481925641 kg*m^2 at C06) and triangle-inequality satisfied (tightest "
    "margin 0.423480 kg*m^2 = 2.34% of I3 at C08); parallel-axis "
    "reconstruction of every tensor from the declared composition agrees to "
    "<=3.6e-15 kg*m^2; mass closure exact to <=7.1e-15 kg; all 56 pinned "
    "component-mass rows bit-exact. ODR-02 VERIFIED NUMERICALLY: C02/C03/C04 "
    "totals equal C01 to 0.0 kg with both panels retained and the failed "
    "panel CoM relocated 0.1 m to the stowed endpoint - no jettison mass "
    "drop. NOT CLEAN: 3 MEDIUM findings (WP2-AUD-02 44 negative entries in "
    "component inertia standard-uncertainty matrices; WP2-AUD-06 C09 "
    "principal-axis triad is left-handed det(R)=-1; WP2-AUD-01 M5 C08/C09 "
    "label crosswalk absent) and 3 LOW schema findings (source_register "
    "byte-size omitted on all 19 entries; aggregator SHA not pinned; panel/"
    "target inertia_reference_frame_declared contradicts the field name). No "
    "finding changes any mass, CoM, tensor, principal moment or pinned "
    "value. The artifact's own summary.all_checks_pass=true is therefore "
    "NARROWER than the truth: its uncertainty check scans only "
    "configuration-level fields and it runs no triangle-inequality, "
    "handedness or byte-size test."
)

receipt = {
    "schema": "M7_WP2_DESIGN_MASS_RECEIPT_V1",
    "generated_local": now,
    "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
    "work_package": "WP2_DESIGN_MASS",
    "status": status,
    "verdict": verdict,
    "receipt_role": (
        "This receipt is issued on the strength of an INDEPENDENT audit of "
        "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml, not on the strength of the "
        "aggregator's own self-declared design_checks. The aggregator was "
        "NOT re-executed this loop; the audit recomputed every number with "
        "numpy from the artifact's own declared component records and "
        "re-hashed every source file with hashlib."
    ),
    "builder": hb(WP2 + "/aggregate_m7_design_mass.py"),
    "auditor": hb(WP2 + "/WP2_INDEPENDENT_AUDIT_V1.py"),
    "receipt_builder": hb(WP2 + "/build_wp2_receipt.py"),
    "contract_outputs": [
        hb(WP2 + "/DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml"),
        hb(WP2 + "/aggregate_m7_design_mass.py"),
        hb(WP2 + "/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml"),
    ],
    "produced_files": [
        hb(WP2 + "/WP2_DESIGN_MASS_AUDIT_V1.json"),
        hb(WP2 + "/WP2_INDEPENDENT_AUDIT_V1.py"),
        hb(WP2 + "/build_wp2_receipt.py"),
    ],
    "audited_artifact_unmodified": {
        "path": WP2 + "/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml",
        "sha256": hb(WP2 + "/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml")["sha256"],
        "bytes": hb(WP2 + "/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml")["bytes"],
        "declared_generated_local": doc["generated_local"],
        "edited_by_this_audit": False,
        "note": (
            "The audit was forbidden from editing this file to make checks "
            "pass; discrepancies are reported, remediation is a later "
            "phase's call."
        ),
    },
    "source_register": src_keys,
    "audit_summary": {
        "audit_artifact": WP2 + "/WP2_DESIGN_MASS_AUDIT_V1.json",
        "overall_verdict": audit["overall_verdict"],
        "checks_total": len(ch),
        "checks_pass": len(passed),
        "checks_fail": len(failed),
        "checks_failed_ids": failed,
        "finding_counts": fc,
        "aggregator_re_executed": False,
        "per_check": {k: v["verdict"] for k, v in ch.items()},
        "findings": [
            {"finding_id": f["finding_id"], "severity": f["severity"],
             "check_id": f["check_id"], "summary": f["summary"]}
            for f in audit["findings"]
        ],
    },
    "numeric_summary": {
        "configuration_count": len(doc["configurations"]),
        "component_records_audited": ch[
            "g_uncertainty_and_pedigree_completeness"][
            "component_record_count_audited"],
        "design_mass_C01_to_C07_kg": 30.159651407342988,
        "design_mass_C08_TARGET_CAPTURE_22KG_kg": 52.15965140734299,
        "design_mass_C09_TARGET_CAPTURE_150KG_kg": 180.15965140734298,
        "mass_closure_max_abs_error_kg": max(
            r["abs_error_kg"] for r in ch[
                "c_mass_closure_and_pinned_values"][
                "mass_sum_per_configuration"]),
        "pinned_component_mass_rows_checked": len(
            ch["c_mass_closure_and_pinned_values"]["pinned_value_rows"]),
        "pinned_component_mass_max_abs_error_kg": max(
            r["abs_error_kg"] for r in ch[
                "c_mass_closure_and_pinned_values"]["pinned_value_rows"]),
        "b601_arm_mass_kg_bit_exact": 4.695555949342986,
        "m3r_design_budget_kg_bit_exact": 0.7619,
        "solar_panel_each_kg": 0.3483933,
        "bus_core_diagnostic_kg": 22.927194215348,
        "legacy_flange_diagnostic_kg": 0.376019184652,
        "bus_primary_structure_merged_kg": 23.3032134,
        "load_bridge_candidate_kg": 0.702195458,
        "center_of_mass_recompute_max_abs_error_m": max(
            r["max_abs_error_m"] for r in ch[
                "c_mass_closure_and_pinned_values"][
                "independent_center_of_mass_recomputation"]),
        "parallel_axis_tensor_recompute_max_abs_error_kg_m2": max(
            r["max_abs_error_vs_reported_kg_m2"] for r in ch[
                "h_independent_parallel_axis_inertia_reconstruction"][
                "per_configuration"]),
        "inertia_symmetry_max_abs_residual_kg_m2": max(
            r["symmetry_max_abs_residual_kg_m2"] for r in ch[
                "d_inertia_physicality_symmetry_pd_triangle"][
                "per_configuration"]),
        "min_eigenvalue_over_all_configurations_kg_m2": min(
            r["min_eigenvalue_kg_m2"] for r in ch[
                "d_inertia_physicality_symmetry_pd_triangle"][
                "per_configuration"]),
        "min_eigenvalue_configuration": min(
            ch["d_inertia_physicality_symmetry_pd_triangle"][
                "per_configuration"],
            key=lambda r: r["min_eigenvalue_kg_m2"])["configuration_id"],
        "triangle_inequality_tightest_absolute_margin_kg_m2": min(
            r["triangle_min_margin_kg_m2"] for r in ch[
                "d_inertia_physicality_symmetry_pd_triangle"][
                "per_configuration"]),
        "triangle_inequality_tightest_relative_margin": min(
            r["triangle_min_margin_relative"] for r in ch[
                "d_inertia_physicality_symmetry_pd_triangle"][
                "per_configuration"]),
        "triangle_inequality_tightest_configuration": min(
            ch["d_inertia_physicality_symmetry_pd_triangle"][
                "per_configuration"],
            key=lambda r: r["triangle_min_margin_relative"])[
                "configuration_id"],
        "principal_axes_orthonormality_max_residual": max(
            r["orthonormality_max_abs_residual_RRt_minus_I"] for r in ch[
                "e_principal_axes_orthonormal_and_consistent"][
                "per_configuration"]),
        "principal_moment_diagonalisation_max_abs_error_kg_m2": max(
            r["independent_eigh_vs_reported_moments_max_abs_err_kg_m2"]
            for r in ch["e_principal_axes_orthonormal_and_consistent"][
                "per_configuration"]),
        "left_handed_principal_triad_configurations": ch[
            "e_principal_axes_orthonormal_and_consistent"][
            "left_handed_configurations"],
        "odr02_panel_mass_retained_all_failure_configs": True,
        "odr02_total_mass_delta_vs_C01_kg": 0.0,
        "odr02_failed_panel_com_relocation_m": 0.1,
        "negative_component_inertia_uncertainty_entries": 44,
        "negative_component_inertia_uncertainty_records": 11,
        "largest_negative_uncertainty_entry_kg_m2": -23.497082533333334,
        "source_register_entries": ch["i_source_register_integrity"][
            "entry_count"],
        "source_register_sha256_reverified": ch[
            "i_source_register_integrity"]["sha256_verified_count"],
        "source_register_entries_missing_byte_size": len(
            ch["i_source_register_integrity"][
                "entries_missing_byte_size_field"]),
        "config_mass_uncertainty_vs_analytic_rss_max_relative_deviation": max(
            r["relative_error"] for r in ch[
                "g_uncertainty_and_pedigree_completeness"][
                "configuration_mass_uncertainty_vs_independent_rss"]),
        "nulls_in_configurations_total": 7,
        "nulls_semantically_correct": 7,
        "nulls_requiring_remediation": 0,
    },
    "open_findings_for_remediation": [
        {
            "finding_id": "WP2-AUD-02",
            "severity": "MEDIUM",
            "title": "negative component inertia standard uncertainties",
            "scope": "44 matrix entries across 11 component records",
            "numeric_effect_on_design_values": "NONE (|u| all match policy)",
            "remediation_owner": "WP2 aggregator revision (later phase)",
        },
        {
            "finding_id": "WP2-AUD-06",
            "severity": "MEDIUM",
            "title": "C09 principal-axis triad left-handed, det(R) = -1.0",
            "scope": "C09 TARGET_CAPTURE_150KG only",
            "numeric_effect_on_design_values":
                "NONE for moments/tensor; affects any consumer that builds a "
                "rotation matrix from the axis rows",
            "remediation_owner": "WP2 aggregator revision or WP10 consumer "
                                 "guard (later phase)",
        },
        {
            "finding_id": "WP2-AUD-01",
            "severity": "MEDIUM",
            "title": "M5 C08/C09 label crosswalk (CAPTURE / POST_CAPTURE) "
                     "not carried",
            "scope": "label traceability only; C01..C09 IDs identical",
            "numeric_effect_on_design_values": "NONE",
            "remediation_owner": "M7 integration "
                                 "(M7_CROSS_WP_REFERENCE_RECONCILIATION_V1)",
        },
        {
            "finding_id": "WP2-AUD-03",
            "severity": "LOW",
            "title": "source_register omits byte size on all 19 entries",
            "scope": "schema compliance with the M7 standing artifact rule",
            "numeric_effect_on_design_values": "NONE (all 19 SHA-256 "
                                               "re-verified against disk)",
            "remediation_owner": "WP2 aggregator revision (later phase)",
        },
        {
            "finding_id": "WP2-AUD-04",
            "severity": "LOW",
            "title": "generating aggregator SHA-256 not pinned in the artifact",
            "scope": "provenance self-containment",
            "numeric_effect_on_design_values": "NONE",
            "remediation_owner": "WP2 aggregator revision (later phase)",
        },
        {
            "finding_id": "WP2-AUD-05",
            "severity": "LOW",
            "title": "inertia_reference_frame_declared contradicts the "
                     "field name on 20 component records",
            "scope": "18 panel + 2 target records; numbers are in S axes",
            "numeric_effect_on_design_values": "NONE (proved by the "
                                               "parallel-axis reconstruction)",
            "remediation_owner": "WP2 aggregator revision (later phase)",
        },
    ],
    "retained_holds": list(doc["retained_holds"]) + [
        "WP2_AUDIT_FINDINGS_OPEN: 3 MEDIUM + 3 LOW findings recorded in "
        "WP2_DESIGN_MASS_AUDIT_V1.json are NOT remediated this loop",
        "SELF_DECLARED_all_checks_pass_IS_NARROWER_THAN_THE_AUDIT: the "
        "artifact runs no triangle-inequality, handedness, component-level "
        "uncertainty-sign or byte-size test",
        "MECHANICAL_FLIGHT_QUALIFICATION_RELEASED (Gate B) remains HOLD",
        "MEMORY_GATE_6GIB_FAILED_ON_THIS_HOST_DECLARED_FAILED",
    ],
    "integration_interfaces": {
        "wp1_structure_cad/PRODUCT_STRUCTURE_V1": "PENDING_SIBLING_HASH",
        "wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1":
            "PENDING_SIBLING_HASH (load bridge remains "
            "CANDIDATE_MEMBER_AWAITING_WP1_STRUCTURE_CONFIRMATION)",
        "wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1":
            "PENDING_SIBLING_HASH (6061-T6 2700 kg/m3 candidate density "
            "behind the MATERIAL_DERIVED class)",
        "wp7_fea_operational/FEA1_RESULTS_V1":
            "PENDING_SIBLING_HASH (consumes design mass/inertia)",
        "wp9_release_package/BOM_V3_DESIGN":
            "SIBLING_PRESENT_HASH_BACKFILL_BY_INTEGRATION",
        "wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V4":
            "SIBLING_PRESENT_AND_READ_THIS_LOOP; its "
            "design_mass_model_binding still carries "
            "sha256: PENDING_SIBLING_HASH for both WP2 files and expects the "
            "C08/C09 alias crosswalk from WP2 (see WP2-AUD-01)",
        "12_release/M7_CROSS_WP_REFERENCE_RECONCILIATION_V1":
            "PENDING_INTEGRATION_BACKFILL",
    },
    "authority_statements": {
        "ODR-01": "T_SM = [185.25,0,0] mm + Ry(90 deg); stations 198.0/208.0/"
                  "210.405 mm are a geometric feature stack, not a second "
                  "dynamics frame",
        "ODR-02": "panel failure = attached-stuck, never jettison - VERIFIED "
                  "NUMERICALLY in this audit",
        "ODR-03": "FreeCAD/STEP neutral chain is system geometry authority; "
                  "SolidWorks native line NATIVE_REINTEGRATION_HOLD",
        "ODR-05": "M3R 0.7619 kg = DESIGN_BUDGET, confidence B; as-built open",
        "ODR-06": "operational FEA authorized; launch-qualification FEA HOLD",
        "L0": "B601 arm 4.695555949342986 kg ACCEPTED_URDF, never overridden "
              "by CAD - verified bit-exact in all 9 configurations",
        "classification": "candidate != authority; design != "
                          "flight-qualified; analysis != test",
    },
    "prohibitions_honored": {
        "audited_yaml_modified_to_make_checks_pass": False,
        "aggregator_re_executed": False,
        "freecad_launched": False,
        "abaqus_launched": False,
        "formal_fea_run_count": 0,
        "zero_fill_of_unknowns": False,
        "fabricated_or_copied_hash": False,
        "l0_urdf_overridden": False,
        "other_wp_files_modified": False,
        "candidate_promoted_to_manufacturing_authority": False,
        "flight_launcher_or_qualification_claim_made": False,
        "memory_gate_heavy_ops": 0,
        "memory_gate_6gib_status": "FAILED_ON_THIS_HOST_DECLARED_FAILED",
    },
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(receipt, f, indent=2, ensure_ascii=False)

print("WROTE", OUT, os.path.getsize(OUT), "bytes")
print("status :", status)
print("failed checks:", failed)
print("findings:", fc)
