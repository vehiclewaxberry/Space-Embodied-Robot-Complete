# -*- coding: utf-8 -*-
"""Self-audit of FEA1B_ELEMENT_FORMULATION_EVIDENCE_V1.json before signing."""
import csv, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
E = json.load(open(os.path.join(HERE, "FEA1B_ELEMENT_FORMULATION_EVIDENCE_V1.json")))
L1, L2, L3 = (E["layer_1_solver_validity"], E["layer_2_numerical_credibility"],
              E["layer_3_engineering_interpretation"])
MC = L2["mesh_credibility_components"]
R = L2["primary_convergence_series"]["observed_order_and_verified_extrapolation"]

print("=== LAYER 1 ===")
for k in ["jobs_total", "all_completed_normally", "all_odb_nonzero", "all_dat_nonzero",
          "total_fatal_errors", "worst_relative_force_residual",
          "worst_relative_moment_residual", "reaction_balance_verdict"]:
    print("  %-38s %s" % (k, L1[k]))
w = L1["warning_classification_summary"]
print("  jobs w/ zero analysis warnings         %s of %s" % (
    w["jobs_with_zero_analysis_warnings"], L1["jobs_total"]))
print("  jobs w/ numerical-problem msgs         %d  %s" % (
    len(w["jobs_with_numerical_problem_messages"]),
    [j.split("_qs_")[-1] for j in w["jobs_with_numerical_problem_messages"]]))
print("  negative eigenvalue msgs total         %s" % w["negative_eigenvalue_messages_total"])
nonfixed = sorted({j for j, v in L1["per_job"].items()
                   if v["reaction_balance"]["nonzero_RF_nodes_outside_NFIXED"]})
print("  jobs with reactions outside NFIXED     %d" % len(nonfixed))

print()
print("=== LAYER 2: hourglass ===")
h = L2["headline_artificial_energy_test"]
print("  baseline C3D8R ALLAE/ALLIE range       %.6g .. %.6g" % tuple(h["baseline_C3D8R_range"]))
print("  FEA-1B range                           %.6g .. %.6g  all_exactly_zero=%s"
      % (h["fea1b_range"][0], h["fea1b_range"][1], h["fea1b_all_exactly_zero"]))

print()
print("=== LAYER 2: mesh credibility criteria ===")
for k in sorted(MC):
    v = MC[k]
    if isinstance(v, dict) and ("pass" in v or "status" in v):
        extra = ""
        for f in ("worst", "worst_prediction_error_pct", "measured_range",
                  "n_verification_points"):
            if f in v:
                extra += "  %s=%s" % (f, v[f])
        print("  %-58s %s%s" % (k, v.get("pass", v.get("status")), extra))
print("  mesh_credibility_pass = %s" % L2["mesh_credibility_pass"])
print("  %s" % MC["mesh_convergence_demonstrated"])

print()
print("=== LAYER 2: verified extrapolation, governing case ===")
Q = R["CAPTURE_150KG_QS"]["quantities"]
print("  %-42s %-6s %-11s %-9s %s" % ("quantity", "p", "limit", "rem@kz6", "verify err kz8/kz12"))
for n, d in Q.items():
    f = d["richardson_fit_from_kz_3_4_6"]
    if f.get("status") != "OK":
        print("  %-42s %s" % (n, f["status"])); continue
    v = d["verification_against_independently_solved_levels"]
    ve = "/".join("%+.3f%%" % v[k]["prediction_error_pct"] for k in sorted(v)
                  if "prediction_error_pct" in v[k])
    print("  %-42s %-6.3f %-11.6g %+8.3f%%  %s  [%s]" % (
        n, f["observed_order_p"], f["extrapolated_limit"],
        f["estimated_remaining_discretization_error_pct_at_finest_fitted"], ve,
        d["class"].split("_")[0]))

print()
print("=== LAYER 2: C3D8I vs C3D8 triangulation ===")
for lid, v in L2["cross_formulation_triangulation"]["levels"].items():
    print("  %-14s dALLIE=%+8.4f%%  dPeakElAvg=%+8.4f%%  dU2=%+8.4f%%  C3D8_stiffer=%s" % (
        lid, v["ALLIE_difference_pct"], v["peak_element_averaged_difference_pct"],
        v["rp_U2_difference_pct"], v["C3D8_ALLIE"] < v["C3D8I_ALLIE"]))
print()
print("=== LAYER 2: linearity (estop must be exactly 2x maneuver) ===")
for k, v in L2["linearity_self_check"]["per_level"].items():
    print("  %-7s stress=%.15f U2=%.15f energy=%.15f" % (
        k, v["ratio_peak_element_averaged"], v["ratio_rp_U2"], v["ratio_ALLIE"]))

print()
print("=== DELTA vs C3D8R baseline (identical meshes) ===")
D = E["delta_vs_c3d8r_baseline"]
for k, v in D["per_case_and_level"].items():
    print("  %-30s HG %.4f->%.1f | peak %+7.2f%% | disp %+8.2f%% | ALLIE %+8.2f%% | zone %s->%s" % (
        k, v["baseline_artificial_energy_fraction"], v["new_artificial_energy_fraction"],
        v["like_for_like_peak_stress_change_pct"], v["peak_displacement_change_pct"],
        v["ALLIE_change_pct"], v["critical_location_baseline"]["zone"],
        v["critical_location_new"]["zone"]))
hw = D["how_wrong_the_baseline_was"]
for k in ("governing_case_peak_stress_at_fine",
          "governing_case_peak_displacement_at_fine",
          "governing_case_strain_energy_at_coarse"):
    v = hw[k]
    print("  %-42s baseline_excess_over_corrected=%+.3f%%  corrected_change_from_baseline=%+.3f%%"
          % (k, v["baseline_excess_over_corrected_pct"],
             v["corrected_change_from_baseline_pct"]))
print("  critical zone unchanged in all comparisons: %s" % hw["critical_zone_unchanged"])

print()
print("=== LAYER 3: five answers ===")
a = L3["a_which_load_case_controls"]
print("  (a) %s | x22kg=%.3f x_estop=%.3f" % (a["answer"], a["ratio_over_capture_22kg"], a["ratio_over_arm_estop"]))
print("  (b) %s | %s" % (L3["b_which_part_controls"]["answer"],
                         {k: round(v, 6) for k, v in L3["b_which_part_controls"]["ordering_at_reference_level"].items()}))
c = L3["c_is_150kg_genuinely_more_controlling_than_22kg"]
print("  (c) %s | stress %.3fx  Mz %.3fx  Fy %.3fx" % (
    c["answer"], c["factor_on_peak_element_averaged_stress"],
    c["factor_on_applied_Mz"], c["factor_on_applied_Fy"]))
d = L3["d_is_arm_emergency_stop_more_severe_than_capture"]
print("  (d) %s | 150/estop=%.2f  22/estop=%.2f" % (
    d["answer"], d["capture_150kg_over_estop"], d["capture_22kg_over_estop"]))
e = L3["e_does_6061_to_7075_change_the_controlling_location"]
print("  (e) %s" % e["answer"])
for lid, v in e["evidence"].items():
    print("      %-13s stress_bitwise_identical=%s  loc_moved=%s  disp %+.4f%% (E-ratio %+.4f%%)" % (
        lid, v["peak_ip_identical_bitwise"], v["controlling_location_moved"],
        v["peak_disp_change_pct"], v["predicted_disp_change_pct_from_E_ratio"]))
u = L3["utilization_against_candidate_typical_property"]
b = u["bounding_values_from_the_verified_extrapolation"]
print("  utilization: elavg %.6f MPa=%.4f%% | peakIP %.6f=%.4f%% | collar %.6f=%.4f%%" % (
    u["peak_element_averaged_MPa_kz6"], u["utilization_pct_element_averaged"],
    u["peak_ip_MPa_kz6"], u["utilization_pct_peak_ip"],
    u["singularity_free_collar_MPa_kz6"], u["utilization_pct_collar"]))
print("  extrapolated bound: peakIP %.6f MPa = %.4f%% of candidate typical yield; headroom %.1fx" % (
    b["peak_ip_limit_MPa"], b["utilization_pct_at_peak_ip_limit"],
    b["headroom_factor_to_candidate_typical_yield_at_that_limit"]))

print()
print("=== LOAD TRACEABILITY ===")
T = E["load_traceability"]["adjudication"]
print("  which row correct: %s | Mz bias %+.3f%% | pass=%s" % (
    T["which_row_is_correct"], T["conservatism_vs_row_consistent_CAP150_030_pct"],
    T["load_traceability_pass"]))
for lid, v in T["quantified_not_argued"].items():
    print("    %-13s Mz %.6f->%.6f (%+.3f%%) => stress %+.4f%%, disp %+.4f%%, loc_moved=%s" % (
        lid, v["envelope_Mz_N_mm"], v["row_consistent_Mz_N_mm"], v["Mz_bias_pct"],
        v["peak_stress_effect_pct"], v["peak_disp_effect_pct"], v["critical_location_moved"]))
print("  22kg single-row label valid: %s" % T["22kg_case_status"]["single_row_label_valid"])

print()
print("=== REGISTERS ===")
RG = E["registers"]
def chk(lst, name):
    bad = [x for x in lst if x.get("bytes") is None or x.get("sha256") is None]
    print("  %-36s n=%3d missing_sha_or_bytes=%d" % (name, len(lst), len(bad)))
chk(RG["source_register"], "source_register")
chk(RG["deck_register"], "deck_register")
print("  deck sidecar sha match all      %s" % all(x["sidecar_sha_matches_file"] for x in RG["deck_register"]))
print("  solved copy identical all       %s" % all(x["solved_copy_identical"] for x in RG["deck_register"]))
for nm in ("solve_artifact_register", "baseline_artifact_register_readonly"):
    lst = RG[nm]
    bad = sum(1 for e in lst for k in e if k != "job_name"
              and (e[k].get("bytes") is None or e[k].get("sha256") is None))
    print("  %-36s n=%3d missing=%d" % (nm, len(lst), bad))
hexok = all(all(ch in "0123456789ABCDEF" for ch in x["sha256"]) and len(x["sha256"]) == 64
            for x in RG["deck_register"] + RG["source_register"])
print("  all sha256 uppercase 64-hex     %s" % hexok)

print()
print("=== CSV ===")
rows = list(csv.DictReader(open(os.path.join(HERE, "FEA1B_RESULTS_V1.csv"))))
print("  rows=%d cols=%d" % (len(rows), len(rows[0])))
blanks = {k: sum(1 for r in rows if r[k] in ("", None)) for k in rows[0]}
print("  columns with blanks: %s" % {k: v for k, v in blanks.items() if v})
print("  distinct element types: %s" % sorted({r["element_type"] for r in rows}))
print("  distinct series: %s" % sorted({r["series"] for r in rows}))
print("  all solve_status COMPLETED_SUCCESSFULLY: %s"
      % all(r["solve_status"] == "COMPLETED_SUCCESSFULLY" for r in rows))
print("  max utilization pct: %.6f" % max(
    float(r["utilization_pct_of_candidate_typical_yield_element_averaged"]) for r in rows))

print()
print("=== PROHIBITIONS ===")
blob = json.dumps(E)
for bad in ["STRUCTURAL_QUALIFICATION_PASS", "FLIGHT_MOS_PASS", "LAUNCH_LOAD_PASS"]:
    print("  %-34s occurrences=%d" % (bad, blob.count(bad)))
print("  occurrences are only inside %s" % E["forbidden_verdicts_explicitly_not_asserted"])
print("  verdict=%s" % E["verdict"])
print("  next_stage_authorized=%s gate_b=%s MoS_asserted=%s review_status=%s" % (
    E["authorization"]["next_stage_authorized"], E["authorization"]["gate_b"],
    E["margin_of_safety_asserted"], E["authorization"]["review_status"]))
print("  holds carried: %d" % len(E["holds_carried"]))
print("  findings:")
for f in E["findings"]:
    sev = f.get("severity") or f.get(
        "severity_against_any_in_plane_discretization_claim")
    print("    %-16s sev=%-24s open=%-5s blocks_gate_a_15=%s" % (
        f["id"], sev, f.get("open"), f.get("blocks_gate_a_criterion_15")))
G = E["gate_a_criterion_15_input_for_A0"]
print("  gate_a_criterion_15 recommendation (INPUT ONLY): %s" % G["recommended_state_odr14"])
print("  declared open items: %d" % len(G["declared_open_items"]))
