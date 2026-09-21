from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def resolve_manifest_path(label: str) -> Path:
    path = Path(label)
    return path if path.is_absolute() else ROOT / path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    manifest_path = PACKAGE / "TERMINAL_DECISION_PACK_SHA256.csv"
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) >= 50, "manifest unexpectedly small")
    require(len({row["id"] for row in rows}) == len(rows), "manifest contains duplicate ids")
    require(len({row["path"] for row in rows}) == len(rows), "manifest contains duplicate paths")
    required_output_ids = {
        "M4_TO_M7_INHERITANCE_AND_GAP_MATRIX_V1.csv",
        "P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml",
        "LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml",
        "TERMINAL_CLOSURE_DEPENDENCY_GRAPH_V1.yaml",
        "TERMINAL_DECISION_PACK_GATE_V1.json",
        "TERMINAL_DECISION_PACK_RECEIPT_V1.md",
        "build_terminal_decision_pack.py",
        "validate_terminal_decision_pack.py",
    }
    require(required_output_ids <= {row["id"] for row in rows if row["class"] == "OUTPUT"}, "manifest omits a required terminal decision-pack output")
    for row in rows:
        path = resolve_manifest_path(row["path"])
        require(path.is_file(), f"missing hash-pinned file: {path}")
        require(path.stat().st_size == int(row["bytes"]), f"byte-size mismatch: {path}")
        require(sha256(path) == row["sha256"].upper(), f"sha256 mismatch: {path}")

    gate = json.loads((PACKAGE / "TERMINAL_DECISION_PACK_GATE_V1.json").read_text(encoding="utf-8"))
    p2 = yaml.safe_load((PACKAGE / "P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml").read_text(encoding="utf-8"))
    legacy = yaml.safe_load((PACKAGE / "LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml").read_text(encoding="utf-8"))
    graph = yaml.safe_load((PACKAGE / "TERMINAL_CLOSURE_DEPENDENCY_GRAPH_V1.yaml").read_text(encoding="utf-8"))

    manifest_by_id = {row["id"]: row for row in rows}
    for required_id in ("odr_gpt04_falsifier", "odr_gpt04_falsifier_controls", "odr_gpt04_falsifier_gate", "odr_gpt04_falsifier_manifest"):
        require(required_id in manifest_by_id and manifest_by_id[required_id]["class"] == "INPUT", f"ODR-GPT-04 falsifier input pin missing: {required_id}")
    nested_manifest_path = resolve_manifest_path(manifest_by_id["odr_gpt04_falsifier_manifest"]["path"])
    with nested_manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        nested_rows = list(csv.DictReader(stream))
    require(len(nested_rows) == 30, "ODR-GPT-04 nested manifest row count drift")
    require(len({row["id"] for row in nested_rows}) == len(nested_rows), "ODR-GPT-04 nested manifest duplicate id")
    require(len({row["path"] for row in nested_rows}) == len(nested_rows), "ODR-GPT-04 nested manifest duplicate path")
    for row in nested_rows:
        path = resolve_manifest_path(row["path"])
        require(path.is_file(), f"ODR-GPT-04 nested path missing: {path}")
        require(path.stat().st_size == int(row["bytes"]), f"ODR-GPT-04 nested byte drift: {path}")
        require(sha256(path) == row["sha256"].upper(), f"ODR-GPT-04 nested hash drift: {path}")
    odr04_gate = json.loads(resolve_manifest_path(manifest_by_id["odr_gpt04_falsifier_gate"]["path"]).read_text(encoding="utf-8"))
    odr04_evidence = json.loads(resolve_manifest_path(manifest_by_id["odr_gpt04_falsifier"]["path"]).read_text(encoding="utf-8"))
    odr04_controls = json.loads(resolve_manifest_path(manifest_by_id["odr_gpt04_falsifier_controls"]["path"]).read_text(encoding="utf-8"))
    require(odr04_gate["outcome"] == "PASS_FALSIFIER__FROZEN_ROUTE_B_ODR_GPT_04_BRANCH_CLOSED_NEGATIVE", "ODR-GPT-04 falsifier outcome drift")
    require(odr04_gate["technical_verdict"] == "ODR_GPT_04_DEFERMENT_NOT_EARNED_FOR_FROZEN_ROUTE_B__REGISTERED_MANDATORY_STATES_UNSAFE__ROUTE_B_REOPENING_PROHIBITED__ROUTE_C_REQUIRED_UNLESS_SEPARATELY_AUTHORIZED_NEW_VERSIONED_ROUTE", "ODR-GPT-04 falsifier verdict drift")
    require(odr04_gate["summary"] == {"passed": 18, "total": 18, "failed": []}, "ODR-GPT-04 falsifier criterion drift")
    require(odr04_controls["summary"] == {"passed": 18, "total": 18, "failed": []}, "ODR-GPT-04 falsifier negative-control drift")
    require(odr04_gate["branch_state"] == {"current_frozen_route_b_rated_envelope_path": "TERMINAL_NEGATIVE_CURRENT_REGISTERED_BRANCH", "odr_gpt_04_deferment_earned": False, "mission_coverage": "FAIL", "route_c_required_to_continue": True, "route_c_cad_authorized": False}, "ODR-GPT-04 branch-state drift")
    require(odr04_gate["proof_scope_guard"] == {"global_q_no_go_claim_made": False, "fillet_trim_global_invariance_proved": False, "closure_basis": "REGISTERED_0_OF_10_SAFE__0_OF_8_RELEASED__MISSION_FAIL__ROUTE_B_REOPENING_NONE_PERMITTED"}, "ODR-GPT-04 proof-scope guard drift")
    require(odr04_gate["owner_accepted"] is False and odr04_gate["next_stage_authorized"] is False and odr04_gate["release_credit"] is False, "ODR-GPT-04 falsifier fabricated authority")
    require(any("does not prove that every external harness topology" in item for item in odr04_evidence["scope_and_nonclaims"]), "ODR-GPT-04 physical-scope guard missing")
    for payload_name, payload in (("P2", p2), ("Legacy", legacy)):
        pin_ids = []
        for pin in payload["evidence_pins"]:
            pin_ids.append(pin["id"])
            path = resolve_manifest_path(pin["path"])
            require(path.is_file(), f"{payload_name} evidence pin missing: {path}")
            require(path.stat().st_size == int(pin["bytes"]), f"{payload_name} evidence pin byte drift: {path}")
            require(sha256(path) == pin["sha256"].upper(), f"{payload_name} evidence pin hash drift: {path}")
            require(pin["id"] in manifest_by_id and manifest_by_id[pin["id"]]["sha256"].upper() == pin["sha256"].upper(), f"{payload_name} evidence pin absent or divergent in package manifest: {pin['id']}")
        require(len(pin_ids) == len(set(pin_ids)), f"{payload_name} evidence pin ids are not unique")

    require(gate["integrity_summary"] == {"passed": 13, "total": 13, "failed": []}, "decision-pack integrity summary drift")
    require(all(item["pass"] for item in gate["integrity_criteria"]), "decision-pack integrity criterion failed")
    require(gate["checkpoint_state"]["A_R2_FULL_FLEX"]["outcome"] == "HOLD", "Checkpoint-A HOLD lost")
    require(gate["checkpoint_state"]["B_ROUTE_C_C2"]["outcome"] == "HOLD", "Checkpoint-B HOLD lost")
    require(gate["checkpoint_state"]["B_ROUTE_C_C2"]["route_c_cad_authorized"] is False, "Route-C CAD was silently authorized")
    require(gate["checkpoint_state"]["FROZEN_ROUTE_B_ODR04"] == {"outcome": "TERMINAL_NEGATIVE_CURRENT_REGISTERED_BRANCH", "deferment_earned": False, "release_edge": False, "global_q_no_go_claim": False}, "frozen Route-B ODR-GPT-04 checkpoint state drift")
    require(gate["checkpoint_state"]["C_TERMINAL_RELEASE"]["reached"] is False, "Checkpoint-C was silently reached")

    for payload, decision_id in ((p2, "ODR-GPT-07"), (legacy, "ODR-GPT-08")):
        require(payload["record_type"] == "APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD", f"{decision_id} record class drift")
        require(payload["requested_decision_id"] == decision_id, f"{decision_id} id drift")
        require(payload["status"] == "PENDING_OWNER_DECISION", f"{decision_id} status drift")
        require(payload["requested_ruling"]["selected_option"] is None, f"{decision_id} was silently selected")
        require(payload["owner_decision_record"]["selected_option"] is None, f"{decision_id} decision record was silently populated")
        require(payload["owner_accepted"] is False, f"{decision_id} owner acceptance fabricated")
        require(payload["next_stage_authorized"] is False, f"{decision_id} next stage fabricated")
        require(payload["release_credit"] is False, f"{decision_id} release credit fabricated")

    opt_a = p2["requested_ruling"]["options"]["A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE"]
    require(p2["engineering_recommendation"]["recommended_option"] == "A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE", "P2 recommendation was confused with Owner selection")
    require(p2["current_authority"]["truncation_contract"]["authority_class"] == "FROZEN_DERIVED_GATE_CONTRACT__NOT_A_DIRECT_OWNER_QUOTE", "1 percent provenance drift")
    require(opt_a["mode_count_per_wing"] == 11, "11D option drift")
    require(opt_a["claimed_discrete_contact_windows_ms"] == [5.0, 10.0, 20.0, 50.0, 100.0], "11D window set drift")
    require(abs(opt_a["worst_relative_error"] - 0.007426037032524928) <= 1e-14, "11D worst error drift")
    require(opt_a["all_other_contact_windows"] == "UNKNOWN", "11D outside-window state drift")
    require(opt_a["outside_domain_policy"] == "HF_FALLBACK_OR_FAIL_CLOSED", "11D outside-domain policy drift")
    require(opt_a["interpolation_or_extrapolation"] == "PROHIBITED", "11D interpolation guard lost")
    require(opt_a["continuous_interval_claim"] is False, "discrete evidence was promoted to continuous claim")
    opt_b = p2["requested_ruling"]["options"]["B_7D_NOMINAL_20MS_CANDIDATE"]
    require(opt_b["known_failed_windows_ms"] == [5.0, 10.0], "7D known failures lost")
    require(abs(opt_b["known_failed_window_relative_errors"]["TC_5MS"] - 0.03004217230856854) <= 1e-14, "7D 5ms failure drift")
    require(abs(opt_b["known_failed_window_relative_errors"]["TC_10MS"] - 0.017200733364448467) <= 1e-14, "7D 10ms failure drift")
    require(opt_b["outside_domain_policy"] == "HF_FALLBACK_OR_FAIL_CLOSED", "7D outside-domain policy drift")
    opt_c = p2["requested_ruling"]["options"]["C_6D_FIRST12_EIGENMODE_MINIMUM_AT_NOMINAL_20MS_NONPREFERRED"]
    require(opt_c["continuous_interval_claim"] is False, "6D discrete evidence was promoted")
    require("D_RETAIN_3_TO_5_MODE_CONTRACT_KEEP_HOLD" in p2["requested_ruling"]["options"], "retain-HOLD option missing")
    require("E_AUTHORIZE_SEPARATE_RESEARCH_ONLY_NONMODAL_BASIS" in p2["requested_ruling"]["options"], "research-only option not separated")

    p2_contract = p2["acceptance_contract_after_separate_approval"]
    require(p2_contract["applies_only_if_selected_option_in"] == [
        "A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE",
        "B_7D_NOMINAL_20MS_CANDIDATE",
        "C_6D_FIRST12_EIGENMODE_MINIMUM_AT_NOMINAL_20MS_NONPREFERRED",
    ], "P2 acceptance contract is not option-conditioned")
    require(p2_contract["nonmatching_option_effect"] == "THIS_ACCEPTANCE_CONTRACT_DOES_NOT_AUTHORIZE_EXECUTION", "P2 nonmatching-option guard lost")
    basis = p2_contract["basis_policy"]
    require(basis["construction_corner"] == "NOMINAL", "P2 basis construction corner drift")
    require(basis["corner_reselection"] is False and basis["column_reordering"] is False, "P2 basis switching guard lost")
    identity = p2_contract["mode_identity_verification"]
    require(identity["mass_weighting"] == "HASH_PINNED_ROUND4_PER_WING_183_BY_183_HF_MASS_MATRIX__NOT_REDUCED_MROM", "MAC mass matrix ambiguity returned")
    require(identity["corner_assignment"]["tie_policy"].startswith("if alternative assignment objective values differ by <=1e-12"), "MAC assignment tie policy drift")
    require(identity["family_classifier"]["proposed_minimum_dominant_fraction"] == 0.90, "mode-family classifier threshold drift")
    require(identity["proposed_nonclustered_mass_weighted_MAC_min"] == 0.90, "MAC threshold drift")
    require(identity["relative_frequency_gap_formula"] == "abs(f_i-f_j)/max(abs(f_i),abs(f_j),1e-14_Hz)", "frequency-gap formula drift")
    require("transitive union" in identity["cluster_construction"], "cross-corner cluster union missing")
    require("scenario_corner_wing_claimed_window_metric" in p2_contract["score_formula"], "P2 score aggregation incomplete")
    require(p2_contract["comparison_operator"] == "LEQ" and p2_contract["relative_limit"] == 0.01, "P2 truncation comparator drift")
    require(p2_contract["solver_cross"]["relative_limit"] == 0.05, "P2 solver cross threshold drift")
    require(p2_contract["contact_and_time_contract"]["component_post_window_s"] == 5.0, "component window drift")
    require(p2_contract["contact_and_time_contract"]["coupled_post_window_s"] == 40.0, "coupled window drift")
    p2_peak = p2_contract["contact_and_time_contract"]["peak_extractor"]
    require(p2_peak["refined_bracketing_grids"] == {"contact_samples": 801, "post_samples": 10001}, "P2 peak-refinement grid drift")
    require(p2_peak["proposed_primary_vs_refined_peak_relative_limit"] == 1.0e-4, "P2 peak-refinement threshold drift")
    require("stationary-point" in p2_peak["final_peak_source"], "P2 sampled-only peak acceptance returned")
    require(p2_contract["supplements_not_replaces"]["E22_G01_TO_G18"] is True, "P2 contract replaced E22 gates")
    require(p2_contract["supplements_not_replaces"]["G12_linearity_threshold_source"]["sha256"] == "1C42CA034F231C7161D092ECF327D6D1E337EEFEE1AB7E86A69EBF5A14931AA4", "G12 threshold authority pin drift")
    auth_matrix = p2["authorization_matrix_after_separate_owner_decision"]
    require("coupled_E22_V2_or_E23" in auth_matrix["A_B_C"]["conditioned_actions"], "P2 E22 conditional authority missing")
    require("no execution authority" in auth_matrix["D"]["effect"], "P2 option D was allowed to execute")
    require("no M7 Gate or release path" in auth_matrix["E"]["effect"], "P2 research option leaked into release")
    p2_chain_contract = p2["conditional_release_chain"]
    require(p2_chain_contract["applies_only_if_selected_option_in"] == p2_contract["applies_only_if_selected_option_in"], "P2 chain option scope drift")
    require(p2_chain_contract["requires_ODR_GPT_08_resolution_before_coupled_campaign"] is True, "P2 chain bypasses ODR-GPT-08")
    p2_chain = p2_chain_contract["steps"]
    require(p2_chain.index("A07_A09_technical_subgate_reissue_only") < p2_chain.index("MECH_DYNAMICS_INTERFACE_rebind"), "P2 chain orders interface before the A07-A09 technical subgate")
    require(p2_chain.index("Handoff_rerun") < p2_chain.index("complete_Checkpoint_A_A01_A12_reissue"), "complete Checkpoint-A was placed before A12 handoff")
    require(p2_chain.index("join_ODR_GPT_08_G17_resolution_branch") < p2_chain.index("isolated_E22_V2_or_E23_full_campaign"), "G17 branch join missing before E22")
    require(p2_chain.index("join_Route_C_physical_and_mission_harness_resolution") < p2_chain.index("MECH_DYNAMICS_INTERFACE_rebind"), "Route-C physical/mission branch join missing before interface")
    require(p2_chain.index("terminal_full_scope_redteam") < p2_chain.index("finding_level_falsifier") < p2_chain.index("TMG_1_to_TMG_7_aggregation") < p2_chain.index("release_manifest_and_hash_audit"), "P2 terminal adversarial/release chain drift")

    legacy_option = legacy["requested_ruling"]["options"]["A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR"]
    require(legacy["engineering_recommendation"]["recommended_option"] == "A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR", "Legacy recommendation was confused with Owner selection")
    require(legacy_option["owner_selection_alone_closes_G17"] is False, "Owner selection silently closed G17")
    require(legacy_option["simulation_authorized_now_by_this_request"] is False, "Legacy simulation silently authorized")
    require(legacy_option["R2_binding"]["credit_eligible_binding"] == "ODR_GPT_07_APPROVED_ROUND4_FINAL_R2_ROM_AND_HASH", "Legacy request is not bound to final Round4")
    ledger = legacy["r1_protocol_comparator_mass_ledger"]
    require(ledger["uncertainty"]["legacy_R1_contribution"] is None, "unknown R1 uncertainty was silently filled")
    require(ledger["uncertainty"]["retained_non_solar_member_uncertainties"] == "CARRIED_VERBATIM_FROM_BRIDGED_C07_COMPOSITION", "known non-solar uncertainty was discarded")
    require(abs(ledger["R1_protocol_comparator_pre_capture_mass_kg"] - 30.15965140734299) <= 1e-14, "R1 comparator mass drift")
    require(np.max(np.abs(np.asarray(ledger["legacy_R1_pair_witness"]["inertia_about_pair_cg_S_kg_m2"], float) - np.diag([0.0339817637968385, 0.00299415, 0.036971733196838504]))) <= 1e-14, "R1 pair inertia drift")
    require(np.max(np.abs(np.asarray(ledger["R1_protocol_comparator_pre_capture_cg_S_m"], float) - np.array([0.09253568086034931, 4.5015873411029815e-05, -0.0013347633708374748]))) <= 1e-14, "R1 comparator CG drift")
    require(ledger["R1_rigid_body_mass_inertia_authority"]["FFRPanel_gross_inertia_disposition"].startswith("FFRPanel quadrature"), "R1 gross inertia authority ambiguity returned")
    require(ledger["R1_rigid_body_mass_inertia_authority"]["silent_correction"] is False, "R1 inertia closure correction was made silent")
    require(legacy["protocol_fingerprint"]["canonical_case_count"] == 8, "four-lane case count drift")
    case_contract = legacy["protocol_fingerprint"]["canonical_case_key_contract"]
    expected_case_keys = {
        f"{lane}__{scenario}"
        for lane in legacy_option["canonical_lanes"]
        for scenario in ("TARGET_22KG_0P5DPS", "TARGET_150KG_3DPS")
    }
    require(set(case_contract["required_keys"]) == expected_case_keys and len(case_contract["required_keys"]) == 8, "canonical case key set is not the exact unique four-lane by two-scenario Cartesian product")
    require(case_contract["required_set"].startswith("EXACT_CARTESIAN_PRODUCT"), "canonical Cartesian-product guard missing")
    require(case_contract["rigid_lane_corner"] == "NOT_APPLICABLE" and case_contract["flex_lane_corner"] == "NOMINAL", "rigid/flex corner semantics drift")
    require(legacy["protocol_fingerprint"]["canonical_conservation_damping_ratio"] == 0.0, "conservation damping lane drift")
    require(legacy["protocol_fingerprint"]["R1_flex_definition"]["canonical_modes_per_wing"] == 5, "R1 canonical mode count drift")
    require(abs(legacy["protocol_fingerprint"]["R1_flex_definition"]["first_mode_frequency_hz_computed"] - 1.000203676127154) <= 1e-14, "R1 EI/f1 semantics drift")
    require(legacy["protocol_fingerprint"]["R1_flex_definition"]["binding_parameter"] == "EI_N_m2", "R1 stiffness binding parameter drift")
    require(legacy["protocol_fingerprint"]["canonical_flex_corner"] == "NOMINAL_FOR_BOTH_FLEX_LANES", "canonical flex corner drift")
    legacy_accept = legacy["acceptance_conditions_after_separate_approval"]
    require(legacy_accept["applies_only_if_selected_option"] == "A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR", "Legacy acceptance contract is not Option-A-conditioned")
    require(legacy_accept["nonmatching_option_effect"] == "NO_COMPARATOR_EXECUTION_AUTHORITY", "Legacy nonmatching-option guard lost")
    source_control = legacy_accept["per_lane_source_control"]
    require(set(source_control["common_whitelist_all_lanes"]) == {"confirmed_MPI_bridge", "PREGRASP_pose_and_kinematics", "target_full_tensor_contract", "contact_and_capture_axis", "parent_protocol_and_reference_implementation"}, "common four-lane whitelist incomplete")
    common_field_map = source_control["common_authority_field_map_all_lanes"]
    require(len(common_field_map) == 9, "common authority field map incomplete")
    require(all(item.get("source", {}).get("id") in manifest_by_id and item.get("pointers") and item.get("unit") and item.get("frame") for item in common_field_map), "common authority field map lacks a pinned source, pointer, unit or frame")
    e22_common_map = next(item for item in common_field_map if item["source"]["id"] == "e22_config")
    require("$.scenarios" not in e22_common_map["pointers"], "whole E22 scenario map leaked C08/C09 post configurations into common authority")
    require(set(e22_common_map["explicitly_excluded_pointers"]) == {"$.scenarios.*.post_configuration", "$.scenarios.*.target_component"}, "E22 C08/C09 reconstruction exclusion drift")
    require(len(source_control["generated_before_execution_and_hash_pinned"]) >= 6, "comparator executable/runtime source control incomplete")
    future_rule = source_control["future_manifest_authority_rule"]
    require(future_rule["manifest_relationship"].startswith("SUBSET_OF_FROZEN_AUTHORITY_WHITELIST"), "future manifest can expand authority")
    require("listing a new file never grants" in future_rule["authority_bearing_input_rule"], "future manifest authority guard missing")
    require("wildcard pointer broadening" in future_rule["forbidden"], "future manifest pointer-broadening guard missing")
    lane_maps = source_control["per_lane_authority_field_map"]
    require(set(lane_maps) == set(legacy_option["canonical_lanes"]), "per-lane authority map does not cover exactly four canonical lanes")
    for lane_id, mappings in lane_maps.items():
        require(mappings, f"empty authority field map: {lane_id}")
        for mapping in mappings:
            if "source" in mapping:
                require(mapping["source"]["id"] in manifest_by_id and mapping.get("pointers") and mapping.get("unit") and mapping.get("frame"), f"unresolved pinned field mapping: {lane_id}")
            elif "inherits_exact_map_from" in mapping:
                require(mapping["inherits_exact_map_from"] in lane_maps, f"unknown inherited lane map: {lane_id}")
            else:
                require(mapping.get("future_source_slot") == "ODR_GPT_07_APPROVED_ROUND4_FINAL_R2_ROM" and mapping.get("path_and_sha256") == "NON_NULL_AND_HASH_PINNED_BEFORE_RUN" and mapping.get("pointers") and mapping.get("unit") and mapping.get("frame"), f"uncontrolled future authority slot: {lane_id}")
    require("in-memory deep copy" in source_control["fingerprint_semantics"]["negative_control_fixture"], "negative-control fixture would mutate production hashes")
    require("authority-bearing fields consumed" in source_control["fingerprint_semantics"]["lane_input_fingerprint"], "lane fingerprint is not a consumed-field projection")
    require(source_control["fingerprint_semantics"]["intended_lane_guard"].endswith("FAIL_INPUT_NOT_CONSUMED"), "intended-lane mutation guard missing")
    require("cannot expand them" in source_control["hard_rule"] and "whole-file/wildcard fallback" in source_control["hard_rule"], "lane source-control hard rule can still expand authority")
    require(len(legacy_accept["mandatory_isolation_negative_controls"]) == 5, "lane isolation negative controls incomplete")
    require(all("intended_projection_effect" in x for x in legacy_accept["mandatory_isolation_negative_controls"][:2]), "bidirectional intended-lane projection guard missing")
    consumption = legacy_accept["mutation_consumption_witness_contract"]
    require(len(consumption["required_artifacts_per_mutation_and_lane"]) == 4, "mutation consumption evidence incomplete")
    require("DERIVED_OPERATOR_INJECTION" in consumption["required_artifacts_per_mutation_and_lane"][0] and "assembly-injection trace" in consumption["required_artifacts_per_mutation_and_lane"][0], "derived-operator injection trace semantics missing")
    require("full state-history hash must change" in consumption["solver_consumption_rule"], "solver consumption sensitivity witness missing")
    require(len(consumption["expected_effect_matrix"]) == 7, "mutation expected-effect matrix incomplete")
    require(consumption["pass_logic"].endswith("EMPTY_SET_FAIL"), "empty mutation set can pass")
    ei_effect = next(item for item in consumption["expected_effect_matrix"] if item["mutation"] == "R1_nominal_EI_plus_1_percent")
    mass_effect = next(item for item in consumption["expected_effect_matrix"] if item["mutation"] == "R1_wing_mass_plus_1_percent")
    mqq_effect = next(item for item in consumption["expected_effect_matrix"] if item["mutation"] == "R1_active_mode_Mqq_plus_1_percent")
    rom_effect = next(item for item in consumption["expected_effect_matrix"] if item["mutation"] == "R2_active_ROM_eigenvalue_plus_1_percent")
    r2_com_effect = next(item for item in consumption["expected_effect_matrix"] if item["mutation"] == "R2_solar_C07_com_component_plus_1mm")
    require(ei_effect["R1_rigid"] == "BITWISE_STABLE" and rom_effect["R2_rigid"] == "BITWISE_STABLE", "flex-only mutation changed its rigid sibling contract")
    require("m_panel_kg" in mass_effect["exact_source_pointers_and_operation"] and "mu_kg_per_m" in mass_effect["exact_source_pointers_and_operation"] and "I_own_com_kgm2" in mass_effect["exact_source_pointers_and_operation"], "R1 mass mutation is not a coherent card-field scaling")
    require(mass_effect["R1_flex"]["Mqq"] == "NUMERICALLY_STABLE_IDENTITY_LEQ_1E_12", "mass-normalized R1 Mqq was incorrectly required to change")
    require(mqq_effect["mutation_class"] == "DERIVED_OPERATOR_INJECTION" and mqq_effect["source_authority_effect"] == "NONE_TEST_FIXTURE_ONLY", "R1 Mqq injection was misclassified as a source-authority mutation")
    require("composition_candidate" in r2_com_effect["exact_source_pointers_and_operation"] and "com_S_m" in r2_com_effect["exact_source_pointers_and_operation"] and "root" not in r2_com_effect["mutation"].lower(), "R2 placement mutation lacks an authorized bridged-C07 COM pointer")
    convergence = legacy_accept["R1_mode_convergence_contract"]
    require(convergence["per_wing_metrics"] == ["tip_max_abs_m", "root_moment_max_abs_N_m", "strain_energy_max_J"], "R1 per-wing convergence metric semantics drift")
    require(convergence["system_metrics"] == ["total_energy_max_J"], "R1 system convergence metric semantics drift")
    require(convergence["peak_extractor"]["refined_bracketing"]["post_samples"] == 80001, "R1 peak temporal refinement missing")
    require(convergence["peak_extractor"]["proposed_primary_vs_refined_relative_limit"] == 1.0e-4, "R1 peak refinement threshold drift")
    require(legacy_accept["frozen_numerical_thresholds"]["solver_cross_relative_max"] == 0.05, "Legacy solver threshold drift")
    require(legacy_accept["frozen_numerical_thresholds"]["comparison_operators"]["minimum_SPD_eigenvalue"] == "STRICT_GT_1E_MINUS_12", "Legacy SPD comparator drift")
    require("no cross-family causal flexibility claim" in legacy["prohibitions"], "cross-family claim guard missing")

    require(graph["heavy_solver_authorized_now"] is False, "heavy solver silently authorized")
    require(graph["next_stage_authorized"] is False, "dependency graph silently authorized next stage")
    require(graph["release_credit"] is False, "dependency graph silently granted release credit")
    require(graph["incoming_edge_semantics_default"] == "ALL_REQUIRED", "dependency graph default join is not fail-closed AND")
    require("release_target_if_all_internal_criteria_close" not in graph, "external Route-C evidence was excluded from release target")
    require("release_target_if_all_terminal_criteria_close_including_mission_evidence_and_route_c_when_required_by_ODR_GPT_04" in graph, "terminal release target does not bind the conditional harness/Route-C evidence rule")
    require(graph["current_internal_owner_decisions_needed"] == ["ODR-GPT-07", "ODR-GPT-08"], "pending Owner decision list drift")
    nodes = {node["id"]: node for node in graph["nodes"]}
    require(len(nodes) == len(graph["nodes"]), "duplicate dependency-graph node id")
    statuses = {node_id: node["status"] for node_id, node in nodes.items()}
    require(statuses["N03_ROUND4_P2_COMPONENT"] == "NOT_AUTHORIZED", "Round4 silently authorized")
    require(statuses["N05_R1_COMPARATOR_PREP"] == "NOT_AUTHORIZED", "R1 comparator prep silently authorized")
    require(statuses["N05B_FOUR_LANE_COMPARATOR"] == "WAIT_ROUND4_AND_R1_PREP", "four-lane join state drift")
    require(statuses["N11_ROUTE_C_CAD_AND_SWEEP"] == "PROHIBITED", "Route-C CAD prohibition lost")
    require(statuses["N11B_RATED_MISSION_ENVELOPE_PROOF"] == "FALSIFIED_TERMINAL_FROZEN", "frozen Route-B ODR-GPT-04 branch was not terminally falsified")
    require(statuses["N21_CHECKPOINT_C_TERMINAL"] == "NOT_REACHED", "terminal checkpoint silently reached")

    edges = graph["edges"]
    require(all(edge["from"] in nodes and edge["to"] in nodes for edge in edges), "dependency graph contains an edge to an unknown node")
    incoming = {node_id: [] for node_id in nodes}
    outgoing = {node_id: [] for node_id in nodes}
    for edge in edges:
        incoming[edge["to"]].append(edge["from"])
        outgoing[edge["from"]].append(edge["to"])
    for node_id, predecessors in incoming.items():
        if len(predecessors) > 1:
            require("join_policy" in nodes[node_id], f"multi-input node lacks explicit join policy: {node_id}")
    for node_id in ("N05B_FOUR_LANE_COMPARATOR", "N06_E22_V2_OR_E23", "N13_INTERFACE_CONTRACT_REBIND", "N15B_CHECKPOINT_A_FULL_REISSUE", "N16_FINAL_RELEASE_CANDIDATE_CM_STAGING"):
        require(nodes[node_id]["join_policy"] == "ALL_REQUIRED", f"join node is not AND: {node_id}")
    require(nodes["N05C_G17_RESOLUTION_GATE"]["join_policy"] == "ONE_OF_MUTUALLY_EXCLUSIVE", "G17 alternative branch join ambiguity")
    require(set(nodes["N05C_G17_RESOLUTION_GATE"]["eligible_predecessors"]) == set(incoming["N05C_G17_RESOLUTION_GATE"]), "G17 eligible branch set drift")
    for node_id in ("N10C_A11_ROUTE_C_OR_DEFERMENT_RESOLUTION", "N12_MISSION_HARNESS_GATE"):
        require(nodes[node_id]["join_policy"] == "ALL_REQUIRED", f"Route-C singleton join is not fail-closed: {node_id}")
        require(set(nodes[node_id]["eligible_predecessors"]) == set(incoming[node_id]), f"Route-C eligible predecessor set drift: {node_id}")
    require(incoming["N10C_A11_ROUTE_C_OR_DEFERMENT_RESOLUTION"] == ["N10_CHECKPOINT_B_RERUN"], "A11 resolution is not Route-C-only")
    require(incoming["N12_MISSION_HARNESS_GATE"] == ["N11_ROUTE_C_CAD_AND_SWEEP"], "Mission harness Gate is not Route-C-only")
    require(outgoing["N11B_RATED_MISSION_ENVELOPE_PROOF"] == [], "falsified Route-B branch still has a release edge")
    require(nodes["N11B_RATED_MISSION_ENVELOPE_PROOF"]["release_path"] is False and nodes["N11B_RATED_MISSION_ENVELOPE_PROOF"]["reopen_allowed"] is False, "falsified Route-B branch reopening guard missing")
    require(outgoing["N02E_P2_NONMODAL_RESEARCH"] == [], "research-only P2 branch leaked into release path")

    edge_map = {(edge["from"], edge["to"]): edge["condition"] for edge in edges}
    require("selects exactly P2 Option A, B or C" in edge_map[("N02_P2_OWNER_DECISION", "N03_ROUND4_P2_COMPONENT")], "P2 decision edge is not option-conditioned")
    require("selects exactly A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR" in edge_map[("N04_G17_OWNER_DECISION", "N05_R1_COMPARATOR_PREP")], "Legacy comparator edge is not option-conditioned")
    require("selects exactly B_REMOVE_LEGACY_NUMERICAL_G17" in edge_map[("N04_G17_OWNER_DECISION", "N04B_G17_SCOPE_CHANGE_CONTRACT_REISSUE")], "Legacy rescope edge is not option-conditioned")
    require(set(incoming["N06_E22_V2_OR_E23"]) == {"N03_ROUND4_P2_COMPONENT", "N05C_G17_RESOLUTION_GATE"}, "E22 join can bypass P2 or G17 resolution")
    require(set(incoming["N13_INTERFACE_CONTRACT_REBIND"]) == {"N08_A07_A09_TECHNICAL_SUBGATE_REISSUE", "N12_MISSION_HARNESS_GATE"}, "interface rebind join drift")
    require(set(incoming["N15B_CHECKPOINT_A_FULL_REISSUE"]) == {"N08_A07_A09_TECHNICAL_SUBGATE_REISSUE", "N10C_A11_ROUTE_C_OR_DEFERMENT_RESOLUTION", "N12_MISSION_HARNESS_GATE", "N15_HANDOFF"}, "complete Checkpoint-A aggregation is incomplete")
    require(nodes["N08_A07_A09_TECHNICAL_SUBGATE_REISSUE"]["scope"].startswith("A07-A09 only"), "technical subgate was confused with complete Checkpoint-A")

    terminal_chain = [
        "N16_FINAL_RELEASE_CANDIDATE_CM_STAGING",
        "N17_TERMINAL_RED_TEAM",
        "N18_FINDING_FALSIFIER",
        "N19_FINAL_SEVEN_GATE_AGGREGATION",
        "N20_RELEASE_MANIFEST_HASH_AUDIT",
        "N21_CHECKPOINT_C_TERMINAL",
    ]
    require(all((a, b) in edge_map for a, b in zip(terminal_chain, terminal_chain[1:])), "terminal Red-Team/falsifier/seven-gate/hash chain incomplete")
    require(graph["release_root"] == "20_engineering/MECHANICAL_ENGINEERING_RELEASE_V1/", "terminal release root escaped the REORG04 engineering domain")
    require(nodes["N17_TERMINAL_RED_TEAM"]["required_output"] == graph["release_root"] + "23_RED_TEAM/", "terminal Red-Team output path drift")
    require(nodes["N18_FINDING_FALSIFIER"]["required_output"] == graph["release_root"] + "24_FALSIFIER/", "terminal falsifier output path drift")
    require(nodes["N20_RELEASE_MANIFEST_HASH_AUDIT"]["required_output"] == graph["release_root"] + "25_RELEASE_SHA256.csv", "terminal release manifest output path drift")
    require(nodes["N19_FINAL_SEVEN_GATE_AGGREGATION"]["required_gates"] == [f"TMG-{i}" for i in range(1, 8)], "terminal seven-gate set drift")
    require("machine-falsified" in graph["current_harness_resolution_needed"], "graph still treats frozen Route-B as an open proof path")
    require(not any("attempt the ODR-GPT-04" in item for item in gate["allowed_now"]), "Gate still permits retrying the falsified frozen Route-B branch")
    require(any("upgrade P01-P13 only with value, unit" in item for item in gate["allowed_now"]), "Gate omits the traceable Route-C physical-input closure action")
    require(any("reopening or relabelling of the frozen Route-B" in item for item in gate["prohibited_now"]), "Gate lacks frozen Route-B reopen/relabel guard")

    # Kahn audit: the release dependency graph must remain acyclic.
    indegree = {node_id: len(predecessors) for node_id, predecessors in incoming.items()}
    ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = []
    while ready:
        node_id = ready.pop(0)
        visited.append(node_id)
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    require(len(visited) == len(nodes), "dependency graph contains a cycle")

    with (PACKAGE / "M4_TO_M7_INHERITANCE_AND_GAP_MATRIX_V1.csv").open("r", encoding="utf-8-sig", newline="") as stream:
        matrix = list(csv.DictReader(stream))
    require([row["m4_line"] for row in matrix] == [f"L{i:02d}" for i in range(1, 9)], "M4 L01-L08 matrix incomplete")
    require(all("DO_NOT_REBUILD" in row["inheritance_decision"] or row["inheritance_decision"].startswith("SUPERSEDE_") or row["inheritance_decision"].startswith("INHERIT_SCHEMA") for row in matrix), "M4 inheritance rule drift")

    print(f"PASS: verified {len(rows)} hash rows")
    print("PASS: M4 L01-L08 inheritance matrix complete")
    print("PASS: ODR-GPT-07 and ODR-GPT-08 remain pending requests")
    print("PASS: 11D discrete-window and 7D 20ms boundaries preserved")
    print("PASS: Checkpoint A/B HOLD and Checkpoint C NOT_REACHED preserved")
    print("PASS: frozen Route-B ODR-GPT-04 branch is a hash-pinned dead-end; Route-C remains the only current graph path")
    print("PASS: no next-stage, CAD, release, qualification or Owner authority fabricated")


if __name__ == "__main__":
    main()
