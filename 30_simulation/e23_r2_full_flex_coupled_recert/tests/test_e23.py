"""Executable tests for the E23 R2 coupled recertification package."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from pathlib import Path

# Establish deterministic BLAS execution before importing NumPy or e22_model.
for _thread_env in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_env] = "1"

import numpy as np

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

HERE = Path(__file__).resolve()
E22_DIR = HERE.parents[1]
PROJECT_ROOT = HERE.parents[3]
sys.path.insert(0, str(E22_DIR / "src"))

from e23_model import (assemble_chaser_model, load_context,
                       rom5_falsifier_contract_pass, rom5_falsifier_summary,
                       sha256, simulate_case, target_contract_pass)
from build_e23 import disposition_guards_pass


def test_fail_closed_authority_preflight_and_mass_matrix() -> None:
    ctx = load_context()
    preflight = ctx["authority_audits"]["preflight"]
    assert preflight["pass"] is True
    assert (preflight["passed"], preflight["total"]) == (13, 13)
    assert ctx["pins"]["round4_gate"]["sha256"] == \
        "233A56CF04B8C781F0931E227164661A7BC2C1B685FC5B8F9960B78A5546E131"
    mass = ctx["authority_audits"]["coupled_mass_matrix"]
    assert abs(mass["min_eigenvalue"] - 0.21274617160144768) < 1.0e-12
    assert abs(mass["condition_number"] - 147.26326742561199) < 1.0e-9
    assert abs(mass["schur_min_eigenvalue"] - 0.5560347386921011) < 1.0e-12

    summary = rom5_falsifier_summary(ctx)
    base_delta = np.asarray(ctx["rom5_falsifier"]["input_contract"]["base_delta_twist_6"], float)
    assert rom5_falsifier_contract_pass(ctx, summary, base_delta)
    assert summary["source_artifact_sha256"] == \
        "D219E69FE8D3555228BB007774F0B59F4F5BDFAD7711569EB7CD074130104E18"
    mutated = copy.deepcopy(summary)
    mutated["best_five_dimensional_subset"]["max_relative_error"] *= 0.5
    assert not rom5_falsifier_contract_pass(ctx, mutated, base_delta)

    scope = copy.deepcopy(ctx["cfg"]["authority_scope"])
    standing = ctx["cfg"]["standing_authority_dispositions"]
    hf_guard = {"legacy_ancf_status": "REPEAT_ANCF_CERTIFICATION",
                "e15_inheritance": "NOT_INHERITED"}
    assert disposition_guards_pass(scope, standing, "FAIL_AT_MANDATORY_KEY_STATES", hf_guard)
    scope["next_stage_authorized"] = True
    assert not disposition_guards_pass(scope, standing, "FAIL_AT_MANDATORY_KEY_STATES", hf_guard)


def test_target_contract_field_specific_thresholds_and_mutations() -> None:
    ctx = load_context()
    checks = ctx["authority_audits"]["target_contract_checks"]
    thresholds = ctx["cfg"]["diagnostic_thresholds"]
    assert target_contract_pass(checks, thresholds)

    mass_mutation = copy.deepcopy(checks)
    mass_mutation["TARGET_22KG_0P5DPS"]["mass_max_abs_residual_kg"] = 1.0e-10
    assert not target_contract_pass(mass_mutation, thresholds)

    tensor_mutation = copy.deepcopy(checks)
    tensor_mutation["TARGET_150KG_3DPS"][
        "Rflip_Icad_RflipT_vs_ledger_max_abs_kgm2"
    ] = 1.0e-10
    assert not target_contract_pass(tensor_mutation, thresholds)

    spatial_mutation = copy.deepcopy(checks)
    spatial_mutation["TARGET_150KG_3DPS"][
        "post_Mbb_minus_C07_minus_target_spatial_max_abs"
    ] = 1.0e-10
    assert not target_contract_pass(spatial_mutation, thresholds)


def test_solar_mass_not_double_counted_and_common_axis_consumed() -> None:
    ctx = load_context()
    solar = ctx["authority_audits"]["solar_decomposition"]
    assert solar["solar_members_count"] == 2
    assert abs(solar["solar_mass_total_kg"] - 1.56) < 1.0e-14
    assert solar["Mbb_reclose_max_abs"] < 1.0e-12
    assert solar["negative_control"]["detected_classification"] == "DOUBLE_COUNT_SOLAR_R2"
    assert solar["negative_control"]["detected"] is True
    cfg_axis = np.asarray(ctx["cfg"]["physics"]["tumble_axis_target"], float)
    cfg_axis /= np.linalg.norm(cfg_axis)
    assert np.max(np.abs(cfg_axis-np.asarray(
        ctx["authority_audits"]["common_tumble_axis_normalized"], float))) < 1.0e-15


def test_nested_mode_order_and_undamped_gate_lane() -> None:
    ctx = load_context()
    nested = [0, 3, 4, 1, 5, 6, 2]
    expected_indices = {n: nested[:n] for n in (3, 4, 5, 6, 7)}
    expected_labels = ["BENDING_1", "TORSION_1", "TORSION_2", "BENDING_2",
                       "TORSION_3", "TORSION_4", "BENDING_3"]
    for n in (3, 4, 5, 6, 7):
        model = assemble_chaser_model(ctx, "C07", "NOMINAL", n,
                                      "UNDAMPED_CONSERVATION_GATE")
        assert model["stored_mode_indices"].tolist() == expected_indices[n]
        assert model["retained_mode_labels"] == expected_labels[:n]
        assert np.count_nonzero(model["C"]) == 0
    damped = assemble_chaser_model(ctx, "C07", "NOMINAL", 7,
                                   "PROVISIONAL_DAMPED_SENSITIVITY")
    assert np.linalg.norm(damped["C"]) > 0.0


def test_short_current_r2_case_is_finite_and_classified_from_equivalent_rate() -> None:
    ctx = load_context()
    case = simulate_case(
        ctx, "TARGET_22KG_0P5DPS", "SOLAR_R2_FLEX_CURRENT",
        corner="NOMINAL", modes_per_wing=7, post_window_s=0.03,
        damping_lane="UNDAMPED_CONSERVATION_GATE",
    )
    assert case["damping_lane"] == "UNDAMPED_CONSERVATION_GATE"
    assert case["damping_gate_credit"] is True
    assert case["retained_stored_indices"] == [0, 3, 4, 1, 5, 6, 2]
    assert case["post_capture"]["energy_balance_relative"] <= 1.0e-8
    assert case["post_capture"]["linear_momentum_relative_peak"] <= 1.0e-8
    assert case["post_capture"]["angular_momentum_relative_peak"] <= 1.0e-8
    assert case["post_capture"]["linear_momentum_absolute_peak_Ns"] <= 1.0e-12
    assert case["post_capture"]["angular_momentum_absolute_peak_Nms"] <= 1.0e-12
    assert case["linearity_domain"]["pass"] is True
    assert case["diagnostic_gate_classification"] == "WHEELS_SMALL_TIER"
    assert case["post_capture"]["omega_plus_equiv_semantics"].startswith(
        "E23_DIAGNOSTIC_PROXY")


def test_final_gate_and_evidence_hashes() -> None:
    gate_path = E22_DIR / "results" / "E23_R2_FULL_FLEX_COUPLED_GATE_V1.json"
    assert gate_path.exists(), "run src/build_e23.py before the final test suite"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    assert gate["technical_verdict"] == "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS"
    assert gate["authority_dispositions"]["linear_subset"] == "E15_R2_LINEAR_SUBSET_PASS"
    assert gate["authority_dispositions"]["e15_current"] == "REPEAT_ANCF_CERTIFICATION"
    assert gate["authority_dispositions"]["e15_inheritance"] == "NOT_INHERITED"
    assert gate["authority_dispositions"]["next_stage_authorized"] is False
    assert gate["authority_dispositions"]["release_credit"] is False
    criteria = {x["id"]: x["pass"] for x in gate["criteria"]}
    assert criteria["G11"] is True
    assert all(criteria.values())
    assert 0.0 < gate["key_metrics"]["hf_to_rom_seven_mode_max_relative"] <= 0.01
    falsifier = gate["risk_and_followup"]["independent_falsifier"]
    assert falsifier["first_12_HF_modes_all_five_dimensional_subsets_tested"] == 792
    assert falsifier["all_five_dimensional_subsets_fail_1pct"] is True
    assert falsifier["best_five_dimensional_subset"]["max_relative_error"] > 0.01
    assert falsifier["minimum_passing_six_dimensional_subset"]["max_relative_error"] < 0.01
    for rel, expected in gate["evidence_hashes"].items():
        path = PROJECT_ROOT / rel
        assert path.exists()
        assert sha256(path) == expected


def test_round4_hash_negative_control() -> None:
    ctx = load_context()
    path = PROJECT_ROOT / ctx["pins"]["round4_gate"]["path"]
    mutated = hashlib.sha256(path.read_bytes()+b"E22_TEST_MUTATION").hexdigest().upper()
    assert mutated != ctx["pins"]["round4_gate"]["sha256"]
