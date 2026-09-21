"""Build the complete E22 R2 coupled diagnostic evidence package, serially."""
from __future__ import annotations

import copy
import csv
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

# Set deterministic linear-algebra execution before importing NumPy/SciPy via
# either this module or e22_model.
for _thread_env in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_env] = "1"

import numpy as np

sys.dont_write_bytecode = True

from e22_model import (E22_DIR, PROJECT_ROOT, jsonable, load_context,
                       rom5_falsifier_contract_pass, rom5_falsifier_summary,
                       run_hf_to_rom_dynamic_validation, sha256, simulate_case,
                       target_contract_pass)


RESULTS = E22_DIR / "results"


def disposition_guards_pass(
    authority_scope: dict[str, Any], standing: dict[str, Any],
    harness_gate: str, hf_validation: dict[str, Any],
) -> bool:
    """Fail closed if any e15, harness, review or release guard drifts."""
    return bool(
        authority_scope.get("e15_ancf_status") == "REPEAT_ANCF_CERTIFICATION" and
        authority_scope.get("e15_inheritance") == "NOT_INHERITED" and
        authority_scope.get("review_status") == "PENDING_OWNER_REVIEW" and
        authority_scope.get("next_stage_authorized") is False and
        authority_scope.get("release_credit") is False and
        standing.get("e15_current_result") == "REPEAT_ANCF_CERTIFICATION" and
        standing.get("e15_inheritance") == "NOT_INHERITED" and
        standing.get("harness_mission_state") == "UNSAFE_INDEPENDENT_FACT" and
        standing.get("next_stage_authorized") is False and
        standing.get("release_credit") is False and
        harness_gate == "FAIL_AT_MANDATORY_KEY_STATES" and
        hf_validation.get("legacy_ancf_status") == "REPEAT_ANCF_CERTIFICATION" and
        hf_validation.get("e15_inheritance") == "NOT_INHERITED"
    )


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(data), indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")


def selected_case_metrics(case: dict[str, Any]) -> dict[str, float]:
    post = case["post_capture"]
    lin = case["linearity_domain"]
    reconstruction_peaks = {
        "node_peak_m": 0.0,
        "tip_peak_m": 0.0,
        "slope_peak_rad": 0.0,
        "hinge_peak_rad": 0.0,
        "torsion_peak_rad": 0.0,
    }
    reconstruction_map = {
        "w_nodes": "node_peak_m",
        "tip_w": "tip_peak_m",
        "theta_dofs": "slope_peak_rad",
        "hinge_relative": "hinge_peak_rad",
        "torsion_nodes": "torsion_peak_rad",
    }
    if lin.get("evaluated"):
        for wing in lin["wings"].values():
            for source_name, output_name in reconstruction_map.items():
                reconstruction_peaks[output_name] = max(
                    reconstruction_peaks[output_name],
                    float(wing["checks"][source_name]["peak"]),
                )
    metrics = {
        "omega_plus_equiv_dps": float(post["omega_plus_equiv_dps"]),
        "base_rate_max_dps": float(post["post_capture_rate_max_dps"]),
        "attitude_excursion_deg": float(post["base_attitude_excursion_max_deg"]),
        "modal_energy_max_J": float(post["modal_energy_max_J"]),
        "wheel_momentum_Nms": float(post["wheel_momentum_required_Nms"]),
        "impulse_force_Ns": float(case["contact"]["impulse_force_norm_Ns"]),
        "impulse_couple_Nms": float(case["contact"]["impulse_couple_norm_Nms"]),
    }
    metrics.update(reconstruction_peaks)
    return metrics


def compare_cases(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    ma, mb = selected_case_metrics(a), selected_case_metrics(b)
    diff = {k: abs(ma[k]-mb[k])/max(abs(ma[k]), abs(mb[k]), 1.0e-14) for k in ma}
    return {"a": a["case_id"], "b": b["case_id"], "relative_differences": diff,
            "max_relative_difference": max(diff.values())}


def finite_case(case: dict[str, Any]) -> bool:
    required = [
        case["contact"]["linear_momentum_window_relative"],
        case["contact"]["angular_momentum_window_relative"],
        case["contact"]["linear_momentum_window_absolute_Ns"],
        case["contact"]["angular_momentum_window_absolute_Nms"],
        case["contact"]["energy_window_relative"],
        case["attach"]["linear_momentum_relative"],
        case["attach"]["angular_momentum_relative"],
        case["attach"]["modal_canonical_momentum_relative"],
        case["post_capture"]["omega_plus_equiv_dps"],
        case["post_capture"]["wheel_momentum_required_Nms"],
        case["post_capture"]["linear_momentum_relative_peak"],
        case["post_capture"]["angular_momentum_relative_peak"],
        case["post_capture"]["linear_momentum_absolute_peak_Ns"],
        case["post_capture"]["angular_momentum_absolute_peak_Nms"],
        case["post_capture"]["energy_balance_relative"],
    ]
    return all(v is not None and math.isfinite(float(v)) for v in required)


def legacy_records(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    historical = json.loads((PROJECT_ROOT / ctx["pins"]["legacy_r1_scene_a2_summary"]["path"]).read_text(encoding="utf-8"))
    return [
        {
            "lane": "LEGACY_R1_FLEX_HISTORICAL_REFERENCE_ONLY",
            "scenario": "TARGET_22KG_0P5DPS",
            "availability": "NOT_AVAILABLE_SAME_SCOPE",
            "numeric_comparison_authorized": False,
            "reason": "no legacy R1 22kg artifact exists at the requested state; no interpolation or parameter substitution",
        },
        {
            "lane": "LEGACY_R1_FLEX_HISTORICAL_REFERENCE_ONLY",
            "scenario": "TARGET_150KG_3DPS",
            "availability": "HISTORICAL_REPRODUCTION_RECORD_ONLY",
            "numeric_comparison_authorized": False,
            "source_sha256": ctx["pins"]["legacy_r1_scene_a2_summary"]["sha256"],
            "legacy_mass_scope": "R1 placeholder stack and 0.348kg-per-panel parameters; forbidden from current R2 matrices",
            "metrics": {
                "base_rate_peak_dps": historical["post"]["base_rate_peak_dps"],
                "attitude_final_deg": historical["post"]["base_dev_final_deg"],
                "modal_energy_peak_J": historical["post"]["panel_modal_energy_peak_J"],
                "tip_L_peak_mm": historical["post"]["tip_L_peak_mm"],
                "tip_R_peak_mm": historical["post"]["tip_R_peak_mm"],
            },
            "causal_guard": "difference from current R2 cannot be attributed wholly to flexibility because mass, placement, arm state, modal basis and initial state differ",
        },
    ]


def build() -> dict[str, Any]:
    RESULTS.mkdir(parents=True, exist_ok=True)
    ctx = load_context()
    cfg = ctx["cfg"]
    thresholds = cfg["diagnostic_thresholds"]
    scenarios = list(cfg["scenarios"])
    corners = cfg["physics"]["corners"]

    rigid = []
    for sid in scenarios:
        rigid.append(simulate_case(ctx, sid, "RIGID_R2_CURRENT", corner="NOMINAL",
                                   post_window_s=40.0, post_propagator="IMPLICIT_ODE"))

    flex_main = []
    for sid in scenarios:
        for corner in corners:
            flex_main.append(simulate_case(
                ctx, sid, "SOLAR_R2_FLEX_CURRENT", corner=corner, modes_per_wing=5,
                contact_window_ms=20.0, post_window_s=40.0,
                damping_lane="UNDAMPED_CONSERVATION_GATE"))

    # Isolated provisional damping sensitivity. It receives no scientific Gate credit.
    damped = []
    for sid in scenarios:
        for corner in corners:
            damped.append(simulate_case(
                ctx, sid, "SOLAR_R2_FLEX_CURRENT", corner=corner, modes_per_wing=5,
                contact_window_ms=20.0, post_window_s=40.0,
                damping_lane="PROVISIONAL_DAMPED_SENSITIVITY"))

    contact_sweep = []
    for sid in scenarios:
        for Tc in cfg["physics"]["contact_window_ms_sweep"]:
            contact_sweep.append(simulate_case(
                ctx, sid, "SOLAR_R2_FLEX_CURRENT", corner="NOMINAL", modes_per_wing=5,
                contact_window_ms=float(Tc), post_window_s=2.0,
                damping_lane="UNDAMPED_CONSERVATION_GATE"))

    truncation_cases = []
    for sid in scenarios:
        for nm in cfg["physics"]["mode_truncation_per_wing"]:
            truncation_cases.append(simulate_case(
                ctx, sid, "SOLAR_R2_FLEX_CURRENT", corner="NOMINAL", modes_per_wing=int(nm),
                contact_window_ms=20.0, post_window_s=5.0,
                damping_lane="UNDAMPED_CONSERVATION_GATE"))

    cross_pairs = []
    for sid in scenarios:
        for corner in corners:
            rad = simulate_case(ctx, sid, "SOLAR_R2_FLEX_CURRENT", corner=corner,
                                modes_per_wing=5, post_window_s=0.5, method="Radau",
                                post_propagator="IMPLICIT_ODE", damping_lane="UNDAMPED_CONSERVATION_GATE")
            bdf = simulate_case(ctx, sid, "SOLAR_R2_FLEX_CURRENT", corner=corner,
                                modes_per_wing=5, post_window_s=0.5, method="BDF",
                                post_propagator="IMPLICIT_ODE", damping_lane="UNDAMPED_CONSERVATION_GATE")
            cross_pairs.append({"scenario": sid, "corner": corner, "Radau": rad, "BDF": bdf,
                                "comparison": compare_cases(rad, bdf)})

    degeneration = []
    for sid, rigid_case in zip(scenarios, rigid):
        deg = simulate_case(ctx, sid, "SOLAR_R2_FLEX_CURRENT", corner="NOMINAL",
                            modes_per_wing=0, post_window_s=40.0,
                            post_propagator="IMPLICIT_ODE")
        degeneration.append({"scenario": sid, "rigid": rigid_case, "zero_Mbq_rigidified": deg,
                             "comparison": compare_cases(rigid_case, deg)})

    worst_rigid = next(x for x in rigid if x["scenario"] == "TARGET_150KG_3DPS")
    hf_validation = run_hf_to_rom_dynamic_validation(
        ctx, np.asarray(worst_rigid["contact"]["base_delta_twist"], float), "TARGET_150KG_3DPS")
    guards_ok = disposition_guards_pass(
        cfg["authority_scope"], cfg["standing_authority_dispositions"],
        ctx["authority_audits"]["harness_independent_fact"]["harness_gate"], hf_validation,
    )

    # Coupled m=3/4/5 trend uses an identical five-second horizon and nested
    # [B1,T1,T2,B2,B3] ordering.
    truncation_summary = {}
    trunc_passes = []
    for sid in scenarios:
        cs = {int(x["modes_per_wing"]): x for x in truncation_cases if x["scenario"] == sid}
        c34, c45 = compare_cases(cs[3], cs[4]), compare_cases(cs[4], cs[5])
        pass45 = c45["max_relative_difference"] <= float(cfg["diagnostic_thresholds"]["rom_truncation_relative_max"])
        trunc_passes.append(pass45)
        truncation_summary[sid] = {"nested_order": ["BENDING_1", "TORSION_1", "TORSION_2", "BENDING_2", "BENDING_3"],
                                    "m3_to_m4": c34, "m4_to_m5": c45,
                                    "m4_to_m5_under_1pct": pass45}

    damped_summary = []
    for dcase in damped:
        ucase = next(x for x in flex_main if x["scenario"] == dcase["scenario"] and x["corner"] == dcase["corner"])
        damped_summary.append({
            "scenario": dcase["scenario"], "corner": dcase["corner"],
            "scope": "PROVISIONAL_DAMPED_SENSITIVITY__NO_GATE_CREDIT__NO_DECAY_QUALIFICATION",
            "undamped": selected_case_metrics(ucase), "provisional_damped": selected_case_metrics(dcase),
            "comparison": compare_cases(ucase, dcase),
        })

    # Executed negative controls.
    sample = copy.deepcopy(flex_main[0])
    sample["post_capture"]["omega_plus_equiv_dps"] = float("nan")
    nan_rejected = not finite_case(sample)
    sample2 = copy.deepcopy(flex_main[0])
    sample2["post_capture"]["wheel_momentum_required_Nms"] = None
    null_rejected = not finite_case(sample2)
    original = (PROJECT_ROOT / ctx["pins"]["round3_gate"]["path"]).read_bytes()
    hash_mutation_rejected = __import__("hashlib").sha256(original+b"E22_NEGATIVE_CONTROL").hexdigest().upper() != ctx["pins"]["round3_gate"]["sha256"]
    try:
        simulate_case(ctx, scenarios[0], "LEGACY_R1_FLEX_HISTORICAL_REFERENCE_ONLY")
        source_lane_rejected = False
    except ValueError:
        source_lane_rejected = True
    mutated_target = copy.deepcopy(ctx["authority_audits"]["target_contract_checks"])
    mutated_target[scenarios[0]]["mass_max_abs_residual_kg"] = 1.0e-10
    mass_mutation_rejected = not target_contract_pass(mutated_target, thresholds)
    mutated_tensor = copy.deepcopy(ctx["authority_audits"]["target_contract_checks"])
    mutated_tensor[scenarios[1]]["Rflip_Icad_RflipT_vs_ledger_max_abs_kgm2"] = 1.0e-10
    tensor_mutation_rejected = not target_contract_pass(mutated_tensor, thresholds)
    falsifier_summary = rom5_falsifier_summary(ctx)
    falsifier_binding_pass = rom5_falsifier_contract_pass(
        ctx, falsifier_summary, np.asarray(hf_validation["base_delta_twist_6"], float))
    mutated_falsifier = copy.deepcopy(falsifier_summary)
    mutated_falsifier["best_five_dimensional_subset"]["max_relative_error"] *= 0.5
    falsifier_field_mutation_rejected = not rom5_falsifier_contract_pass(
        ctx, mutated_falsifier, np.asarray(hf_validation["base_delta_twist_6"], float))
    mutated_guard_scope = copy.deepcopy(cfg["authority_scope"])
    mutated_guard_scope["next_stage_authorized"] = True
    guard_mutation_rejected = not disposition_guards_pass(
        mutated_guard_scope, cfg["standing_authority_dispositions"],
        ctx["authority_audits"]["harness_independent_fact"]["harness_gate"], hf_validation)
    negative_controls = {
        "NaN_required_metric_rejected": nan_rejected,
        "null_required_metric_rejected": null_rejected,
        "mutated_hash_rejected": hash_mutation_rejected,
        "legacy_lane_as_current_solver_source_rejected": source_lane_rejected,
        "double_count_solar_detected": ctx["authority_audits"]["solar_decomposition"]["negative_control"]["detected"],
        "mass_1e-10kg_mutation_rejected": mass_mutation_rejected,
        "tensor_1e-10kgm2_mutation_rejected": tensor_mutation_rejected,
        "rom5_falsifier_field_binding_pass": falsifier_binding_pass,
        "rom5_falsifier_score_mutation_rejected": falsifier_field_mutation_rejected,
        "guard_next_stage_true_mutation_rejected": guard_mutation_rejected,
        "pass": all((nan_rejected, null_rejected, hash_mutation_rejected, source_lane_rejected,
                    mass_mutation_rejected, tensor_mutation_rejected, falsifier_binding_pass,
                    falsifier_field_mutation_rejected, guard_mutation_rejected,
                    ctx["authority_audits"]["solar_decomposition"]["negative_control"]["detected"])),
    }

    all_current = rigid + flex_main + contact_sweep + truncation_cases + \
                  [p[m] for p in cross_pairs for m in ("Radau", "BDF")] + \
                  [d["zero_Mbq_rigidified"] for d in degeneration]
    all_with_sensitivity = all_current + damped
    finite_ok = all(finite_case(x) for x in all_with_sensitivity)
    spd_ok = all(x["mass_matrix_audit"]["pre_min_eigenvalue"] > thresholds["spd_min_eigenvalue"] and
                 x["mass_matrix_audit"]["post_min_eigenvalue"] > thresholds["spd_min_eigenvalue"] and
                 x["mass_matrix_audit"]["delassus_min_eigenvalue"] > thresholds["spd_min_eigenvalue"]
                 for x in all_with_sensitivity)
    contact_ok = all(x["contact"]["linear_momentum_window_relative"] <= thresholds["coupled_momentum_relative_max"] and
                     x["contact"]["angular_momentum_window_relative"] <= thresholds["coupled_momentum_relative_max"] and
                     x["contact"]["linear_momentum_post_lock_relative"] <= thresholds["coupled_momentum_relative_max"] and
                     x["contact"]["angular_momentum_post_lock_relative"] <= thresholds["coupled_momentum_relative_max"] and
                     x["contact"]["linear_momentum_window_absolute_Ns"] <= thresholds["momentum_absolute_max"] and
                     x["contact"]["angular_momentum_window_absolute_Nms"] <= thresholds["momentum_absolute_max"] and
                     x["contact"]["linear_momentum_post_lock_absolute_Ns"] <= thresholds["momentum_absolute_max"] and
                     x["contact"]["angular_momentum_post_lock_absolute_Nms"] <= thresholds["momentum_absolute_max"] and
                     x["contact"]["energy_window_relative"] <= thresholds["energy_relative_max"]
                     for x in all_current)
    attach_ok = all(x["attach"]["linear_momentum_relative"] <= thresholds["attach_momentum_relative_max"] and
                    x["attach"]["angular_momentum_relative"] <= thresholds["attach_momentum_relative_max"] and
                    x["attach"]["modal_canonical_momentum_relative"] <= thresholds["attach_momentum_relative_max"] and
                    x["attach"]["linear_momentum_absolute_Ns"] <= thresholds["momentum_absolute_max"] and
                    x["attach"]["angular_momentum_absolute_Nms"] <= thresholds["momentum_absolute_max"]
                    for x in all_current)
    post_ok = all(x["post_capture"]["linear_momentum_relative_peak"] <= thresholds["coupled_momentum_relative_max"] and
                  x["post_capture"]["angular_momentum_relative_peak"] <= thresholds["coupled_momentum_relative_max"] and
                  x["post_capture"]["linear_momentum_absolute_peak_Ns"] <= thresholds["momentum_absolute_max"] and
                  x["post_capture"]["angular_momentum_absolute_peak_Nms"] <= thresholds["momentum_absolute_max"] and
                  x["post_capture"]["energy_balance_relative"] <= thresholds["energy_relative_max"] for x in all_current)
    cross_max = max(x["comparison"]["max_relative_difference"] for x in cross_pairs)
    cross_ok = cross_max <= thresholds["solver_cross_relative_max"]
    linearity_ok = all(x["linearity_domain"]["pass"] for x in all_with_sensitivity)
    degeneration_max = max(x["comparison"]["max_relative_difference"] for x in degeneration)
    degeneration_ok = degeneration_max <= 1.0e-10
    expected_classes = all(
        (x["scenario"] == "TARGET_22KG_0P5DPS" and x["diagnostic_gate_classification"] == "WHEELS_SMALL_TIER") or
        (x["scenario"] == "TARGET_150KG_3DPS" and x["diagnostic_gate_classification"] == "INFEASIBLE_RATE")
        for x in rigid+flex_main)

    legacy = legacy_records(ctx)
    legacy_comparison_complete = all(
        x["availability"] == "SAME_SCOPE_NUMERIC_COMPARISON_AVAILABLE" and
        x["numeric_comparison_authorized"] is True
        for x in legacy
    )
    cases_doc = {
        "schema": "E22_R2_COUPLED_CASES_V1",
        "lane_scope": cfg["lanes"],
        "rigid_R2_current": rigid,
        "solar_R2_flex_current_undamped_gate": flex_main,
        "legacy_R1_flex_historical_reference_only": legacy,
        "three_lane_two_scenario_comparison": {
            "state": "COMPLETE" if legacy_comparison_complete else "PARTIAL_FAIL_CLOSED",
            "complete": legacy_comparison_complete,
            "reason": (
                "Legacy R1 22kg same-scope evidence is unavailable; the 150kg artifact "
                "has incompatible mass/placement/arm/modal/initial-state semantics and is "
                "historical reproduction only"
            ),
        },
    }
    sensitivity_doc = {
        "schema": "E22_R2_SENSITIVITY_AND_VALIDATION_V1",
        "contact_window_sweep": contact_sweep,
        "mode_truncation_cases": truncation_cases,
        "mode_truncation_summary": truncation_summary,
        "radau_bdf_cross": cross_pairs,
        "rigid_degeneration": degeneration,
        "provisional_damped_sensitivity_cases": damped,
        "provisional_damped_sensitivity_summary": damped_summary,
        "negative_controls": negative_controls,
    }
    authority_doc = {
        "schema": "E22_SOURCE_AND_AUTHORITY_AUDIT_V1",
        "config_path": ctx["config_path"], "source_pins": ctx["pins"],
        "authority_audits": ctx["authority_audits"],
        "owner_authority_consumed": cfg["authority_scope"]["owner_decisions_consumed"],
        "sim10_authority_inheritance": "NOT_INHERITED_THRESHOLD_HASH_DRIFT",
        "e15_current": "REPEAT_ANCF_CERTIFICATION", "e15_inheritance": "NOT_INHERITED",
        "harness_state": "UNSAFE_INDEPENDENT_FACT", "next_stage_authorized": False,
        "release_credit": False,
    }
    write_json(RESULTS/"E22_SOURCE_AND_AUTHORITY_AUDIT_V1.json", authority_doc)
    write_json(RESULTS/"E22_R2_COUPLED_CASES_V1.json", cases_doc)
    write_json(RESULTS/"E22_R2_SENSITIVITY_AND_VALIDATION_V1.json", sensitivity_doc)
    write_json(RESULTS/"R2_HF_TO_ROM_DYNAMIC_VALIDATION_V1.json", hf_validation)

    rows = []
    for x in rigid+flex_main+damped:
        rows.append({
            "case_id": x["case_id"], "lane": x["lane"], "scenario": x["scenario"],
            "corner": x["corner"], "damping_lane": x["damping_lane"],
            "omega_plus_equiv_dps": x["post_capture"]["omega_plus_equiv_dps"],
            "base_rate_initial_dps": x["post_capture"]["post_capture_rate_initial_dps"],
            "base_rate_peak_dps": x["post_capture"]["post_capture_rate_max_dps"],
            "base_rate_final_dps": x["post_capture"]["post_capture_rate_final_dps"],
            "attitude_excursion_deg": x["post_capture"]["base_attitude_excursion_max_deg"],
            "modal_energy_peak_J": x["post_capture"]["modal_energy_max_J"],
            "wheel_momentum_Nms": x["post_capture"]["wheel_momentum_required_Nms"],
            "classification": x["diagnostic_gate_classification"],
            "linearity_pass": x["linearity_domain"]["pass"],
        })
    with (RESULTS/"E22_CASE_MATRIX_V1.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    criteria = [
        {"id": "G01", "name": "fail-closed authority preflight", "pass": ctx["authority_audits"]["preflight"]["pass"]},
        {"id": "G02", "name": "all numerical outputs finite", "pass": finite_ok},
        {"id": "G03", "name": "pre/post/Delassus SPD", "pass": spd_ok},
        {"id": "G04", "name": "contact linear/angular momentum absolute+relative and work-energy audits", "pass": contact_ok},
        {"id": "G05", "name": "attach linear/angular/modal momentum blocks", "pass": attach_ok},
        {"id": "G06", "name": "post linear/angular momentum absolute+relative and energy audits", "pass": post_ok},
        {"id": "G07", "name": "Radau/BDF bounded-window cross <=5%", "pass": cross_ok},
        {"id": "G08", "name": "5/10/20/50/100 ms contact coverage", "pass": len(contact_sweep) == 10},
        {"id": "G09", "name": "LOW/NOMINAL/HIGH current R2 coverage", "pass": len(flex_main) == 6},
        {"id": "G10", "name": "nested coupled m4->m5 truncation <=1%", "pass": all(trunc_passes)},
        {"id": "G11", "name": "183-DOF HF to five-mode dynamic truncation <=1%", "pass": bool(hf_validation["pass"])},
        {"id": "G12", "name": "all current R2 response reconstruction inside linearity domain", "pass": linearity_ok},
        {"id": "G13", "name": "rigid degeneration returns RIGID_R2", "pass": degeneration_ok},
        {"id": "G14", "name": "source-lane/NaN/null/hash/double-count negative controls", "pass": negative_controls["pass"]},
        {"id": "G15", "name": "diagnostic classifications match rate/H tiers", "pass": expected_classes},
        {"id": "G16", "name": "provisional damping isolated without Gate credit", "pass": len(damped) == 6 and all(not x["damping_gate_credit"] for x in damped)},
        {"id": "G17", "name": "three-lane/two-scenario same-scope comparison completeness", "pass": legacy_comparison_complete},
        {"id": "G18", "name": "e15/harness/review/next/release guards retained", "pass": guards_ok},
    ]
    failed = [x["id"] for x in criteria if not x["pass"]]
    if not hf_validation["pass"]:
        verdict = "HOLD_R2_HF_TO_ROM_DYNAMIC_VALIDATION_FAILED"
    elif not linearity_ok:
        verdict = "HOLD_LINEARITY_DOMAIN_EXCEEDED"
    elif failed:
        verdict = "FAIL_INTERNAL_NUMERICAL_OR_COVERAGE_CRITERIA"
    else:
        verdict = "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS"

    evidence_paths = [
        E22_DIR/"config/e22_config.yaml", E22_DIR/"src/e22_model.py", E22_DIR/"src/build_e22.py",
        E22_DIR/"README.md", E22_DIR/"tests/test_e22.py", E22_DIR/"tests/independent_recompute.py",
        E22_DIR/"tests/replay_determinism.py",
        PROJECT_ROOT/ctx["pins"]["rom5_dimension_falsifier"]["path"],
        PROJECT_ROOT/ctx["pins"]["rom5_dimension_falsifier_script"]["path"],
        RESULTS/"E22_SOURCE_AND_AUTHORITY_AUDIT_V1.json",
        RESULTS/"E22_R2_COUPLED_CASES_V1.json",
        RESULTS/"E22_R2_SENSITIVITY_AND_VALIDATION_V1.json",
        RESULTS/"R2_HF_TO_ROM_DYNAMIC_VALIDATION_V1.json", RESULTS/"E22_CASE_MATRIX_V1.csv",
    ]
    evidence_hashes = {str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"): sha256(p) for p in evidence_paths}
    gate = {
        "schema": "E22_R2_FULL_FLEX_COUPLED_GATE_V1",
        "technical_verdict": verdict,
        "scope": "CHECKPOINT-A current R2 rigid/flexible coupled diagnostics; no mission release",
        "criteria": criteria, "summary": {"passed": sum(int(x["pass"]) for x in criteria), "total": len(criteria), "failed": failed},
        "key_metrics": {
            "cross_solver_max_relative": cross_max,
            "rigid_degeneration_max_relative": degeneration_max,
            "hf_to_rom_five_mode_max_relative": hf_validation["five_mode_max_relative_error_vs_183dof"],
            "hf_to_rom_limit": hf_validation["truncation_limit"],
            "independent_best_any_5D_HF_subset_max_relative": hf_validation[
                "independent_red_team_falsifier_finding"
            ]["best_five_dimensional_subset"]["max_relative_error"],
            "independent_minimum_passing_dimension": 6,
            "linearity_all_current_R2": linearity_ok,
            "three_lane_comparison_state": "COMPLETE" if legacy_comparison_complete else "PARTIAL_FAIL_CLOSED",
            "current_max_linear_momentum_absolute_Ns": max(
                x["post_capture"]["linear_momentum_absolute_peak_Ns"] for x in all_current),
            "current_max_angular_momentum_absolute_Nms": max(
                x["post_capture"]["angular_momentum_absolute_peak_Nms"] for x in all_current),
            "current_max_contact_energy_relative": max(
                x["contact"]["energy_window_relative"] for x in all_current),
            "22kg_nominal_omega_plus_equiv_dps": next(x for x in flex_main if x["scenario"]=="TARGET_22KG_0P5DPS" and x["corner"]=="NOMINAL")["post_capture"]["omega_plus_equiv_dps"],
            "22kg_nominal_Hc_Nms": next(x for x in flex_main if x["scenario"]=="TARGET_22KG_0P5DPS" and x["corner"]=="NOMINAL")["post_capture"]["wheel_momentum_required_Nms"],
            "150kg_nominal_omega_plus_equiv_dps": next(x for x in flex_main if x["scenario"]=="TARGET_150KG_3DPS" and x["corner"]=="NOMINAL")["post_capture"]["omega_plus_equiv_dps"],
            "150kg_nominal_Hc_Nms": next(x for x in flex_main if x["scenario"]=="TARGET_150KG_3DPS" and x["corner"]=="NOMINAL")["post_capture"]["wheel_momentum_required_Nms"],
        },
        "authority_dispositions": {
            "diagnostic_gate_classification": "PROVISIONAL_E22_DIAGNOSTIC",
            "sim10_authority_inheritance": "NOT_INHERITED_THRESHOLD_HASH_DRIFT",
            "e15_current": "REPEAT_ANCF_CERTIFICATION", "e15_inheritance": "NOT_INHERITED",
            "linear_subset": hf_validation["linear_subset_verdict"],
            "harness": "UNSAFE_INDEPENDENT_FACT",
            "review_status": "PENDING_OWNER_REVIEW", "next_stage_authorized": False,
            "release_credit": False,
        },
        "risk_and_followup": {
            "root_cause": "CONTRACT_BOUNDED_ROM_DIMENSION_INSUFFICIENT_FOR_1PCT_DYNAMIC_RECONSTRUCTION",
            "independent_falsifier": hf_validation["independent_red_team_falsifier_finding"],
            "required_resolution": (
                "Owner/P2 contract change and upstream ROM regeneration: use a reselected 6D "
                "B1+B2+T1-T4 family, or 7D B1-B3+T1-T4 if preserving Round3's three-bending "
                "family; alternatively establish a new independently justified observable-specific "
                "acceptance contract. None is authorized in E22"
            ),
            "projected_propagator_cross_scope": (
                "G07 binds Radau/BDF only on the bounded implicit-ODE window. A separate "
                "read-only 0.5 s PROJECTED_EXPONENTIAL versus implicit witness is about 1.59e-5, "
                "but is not machine-bound by this Gate; projected P/H/E enforcement is therefore "
                "not claimed as an independent long-horizon algorithm validation"
            ),
        },
        "evidence_hashes": evidence_hashes,
        "self_hash_policy": "SELF_REFERENCE_EXCLUDED",
        "review_status": "PENDING_OWNER_REVIEW", "next_stage_authorized": False,
        "release_credit": False,
    }
    write_json(RESULTS/"E22_R2_FULL_FLEX_COUPLED_GATE_V1.json", gate)
    return gate


if __name__ == "__main__":
    gate = build()
    print(json.dumps({"technical_verdict": gate["technical_verdict"], "summary": gate["summary"],
                      "key_metrics": gate["key_metrics"]}, indent=2, ensure_ascii=False))
