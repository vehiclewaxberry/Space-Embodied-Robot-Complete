"""E22 R2 free-floating locked-arm contact/flex diagnostic core.

The model is deliberately bounded: C07/C08/C09 provide the current rigid spatial
inertia in S; the Round3 five-mode data add *relative-coordinate* M_bq/M_qq/K/C
blocks.  No solar mass is added to C07 a second time.  Contact is a frozen-inertial
six-dimensional equal-impulse half-sine window followed by a residual Delassus
lockup.  Post lock, the body-frame Euler-Poincare equations exchange momentum
between the base and modal coordinates without an external wrench.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import ast
import os
import re
import sys
from pathlib import Path
from typing import Any

# Reproducibility must be established before NumPy/SciPy loads a BLAS runtime.
# The explicit threadpoolctl scope at every generalized eigensolve remains the
# authoritative guard when this module is imported into an existing process.
for _thread_env in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_env] = "1"

import numpy as np
import yaml
from scipy.integrate import solve_ivp
from scipy.linalg import block_diag, eigh, expm
from threadpoolctl import threadpool_limits


HERE = Path(__file__).resolve()
E22_DIR = HERE.parents[1]
PROJECT_ROOT = HERE.parents[3]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def skew(a: np.ndarray) -> np.ndarray:
    x, y, z = np.asarray(a, dtype=float)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def inertia_from_components(v: dict[str, float]) -> np.ndarray:
    return np.array(
        [[v["Ixx"], v["Ixy"], v["Ixz"]],
         [v["Ixy"], v["Iyy"], v["Iyz"]],
         [v["Ixz"], v["Iyz"], v["Izz"]]], dtype=float
    )


def spatial_inertia(mass: float, cg: np.ndarray, inertia_cg: np.ndarray) -> np.ndarray:
    """Spatial mass for twist [v_origin, omega], both expressed in body frame."""
    c = np.asarray(cg, dtype=float)
    return np.block([
        [mass * np.eye(3), -mass * skew(c)],
        [mass * skew(c), inertia_cg + mass * ((c @ c) * np.eye(3) - np.outer(c, c))],
    ])


def quat_mul(q: np.ndarray, r: np.ndarray) -> np.ndarray:
    w, x, y, z = q
    a, b, c, d = r
    return np.array([
        w*a - x*b - y*c - z*d,
        w*b + x*a + y*d - z*c,
        w*c - x*d + y*a + z*b,
        w*d + x*c - y*b + z*a,
    ])


def quat_to_rot(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    q = q / np.linalg.norm(q)
    w, x, y, z = q
    return np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
    ])


def relnorm(a: np.ndarray, b: np.ndarray, floor: float = 1.0e-14) -> float:
    return float(np.linalg.norm(np.asarray(a)-np.asarray(b)) /
                 max(np.linalg.norm(a), np.linalg.norm(b), floor))


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def target_contract_pass(checks: dict[str, Any], thresholds: dict[str, float]) -> bool:
    return all(
        v["mass_max_abs_residual_kg"] <= float(thresholds["mass_reconstruction_kg"]) and
        v["SSOT_diag_vs_CAD_diag_max_abs_kgm2"] <= float(thresholds["inertia_reconstruction_kgm2"]) and
        v["Rflip_Icad_RflipT_vs_ledger_max_abs_kgm2"] <= float(thresholds["inertia_reconstruction_kgm2"]) and
        v["post_Mbb_minus_C07_minus_target_spatial_max_abs"] <= float(thresholds["inertia_reconstruction_kgm2"]) and
        v["grasp_alignment_max_abs_m"] <= float(thresholds["geometry_alignment_m"])
        for v in checks.values())


def rom5_falsifier_summary(ctx: dict[str, Any]) -> dict[str, Any]:
    """Extract the E22 risk summary from the hash-pinned red-team artifact."""
    doc = ctx["rom5_falsifier"]
    dim = doc["dimension_combination_falsifier"]
    best5 = dim["best_five_dimensional_subset"]
    best6 = dim["best_six_dimensional_subset"]
    best7 = dim["best_seven_dimensional_subset_preserving_three_bending_modes"]
    inventory = {int(x["hf_index_0based"]): x for x in doc["mode_inventory_first12"]}
    return {
        "provenance": "HASH_PINNED_CHECKPOINT_A_RED_TEAM_FALSIFIER",
        "source_artifact_sha256": ctx["pins"]["rom5_dimension_falsifier"]["sha256"],
        "source_recompute_script_sha256": ctx["pins"]["rom5_dimension_falsifier_script"]["sha256"],
        "definition": dim["score"],
        "first_12_HF_modes_all_five_dimensional_subsets_tested": int(
            dim["five_dimensional_combination_count"]),
        "all_five_dimensional_subsets_fail_1pct": bool(
            dim["all_792_five_dimensional_subsets_evaluated"] and not best5["passes_1pct"]),
        "best_five_dimensional_subset": {
            "HF_indices_0based": best5["hf_indices_0based"],
            "labels": [x["label"] for x in best5["modes"]],
            "max_relative_error": best5["global_max_relative_error"],
            "governing_metrics": best5["governing_metrics"],
        },
        "minimum_passing_six_dimensional_subset": {
            "HF_indices_0based": best6["hf_indices_0based"],
            "labels": [x["label"] for x in best6["modes"]],
            "max_relative_error": best6["global_max_relative_error"],
            "governing_metrics": best6["governing_metrics"],
        },
        "passing_subset_retaining_three_bending_modes": {
            "HF_indices_0based": best7["hf_indices_0based"],
            "labels": [x["label"] for x in best7["modes"]],
            "max_relative_error": best7["global_max_relative_error"],
            "governing_metrics": best7["governing_metrics"],
        },
        "additional_torsion_frequencies_hz": {
            "TORSION_3": inventory[4]["frequency_hz"],
            "TORSION_4": inventory[5]["frequency_hz"],
        },
        "P2_max_modes_per_wing": 5,
        "disposition": (
            "ROM_DIMENSION_INSUFFICIENT_WITHIN_P2_MAX5; do not change basis, "
            "threshold or upstream Round3 silently"
        ),
    }


def rom5_falsifier_contract_pass(
    ctx: dict[str, Any], summary: dict[str, Any], base_delta_twist_6: np.ndarray | None = None,
) -> bool:
    """Field-level, fail-closed binding of the red-team falsifier into E22."""
    doc = ctx["rom5_falsifier"]
    script = ctx["rom5_falsifier_script_source"]
    dim = doc.get("dimension_combination_falsifier", {})
    source_rows = doc.get("source_hashes", {}).values()
    guards = (
        doc.get("schema") == "ROM5_DIMENSION_FALSIFIER_V1" and
        doc.get("verdict") == "ROM5_FULL_FIELD_TRUNCATION_FALSIFIED_AT_1PCT" and
        doc.get("deterministic_recompute") is True and
        doc.get("review_status") == "PENDING_OWNER_REVIEW" and
        doc.get("next_stage_authorized") is False and
        doc.get("release_credit") is False and
        dim.get("five_dimensional_combination_count") == 792 and
        dim.get("expected_five_dimensional_combination_count") == 792 and
        dim.get("all_792_five_dimensional_subsets_evaluated") is True and
        dim.get("minimum_passing_dimension_within_first12") == 6 and
        dim.get("minimum_passing_dimension_preserving_all_three_bending_modes") == 7 and
        all(x.get("match") is True and x.get("actual_sha256") == x.get("expected_sha256")
            for x in source_rows) and
        "itertools.combinations" in script and
        '"five_dimensional_combination_count"' in script and
        summary == rom5_falsifier_summary(ctx)
    )
    if base_delta_twist_6 is not None:
        guards = guards and np.max(np.abs(
            np.asarray(doc["input_contract"]["base_delta_twist_6"], float) -
            np.asarray(base_delta_twist_6, float)
        )) <= 1.0e-15
    return bool(guards)


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _config_entry(doc: dict[str, Any], cid: str) -> dict[str, Any]:
    return next(x for x in doc["configurations"] if x["configuration_id"] == cid)


def _bridged_config_entry(doc: dict[str, Any], cid: str) -> dict[str, Any]:
    return next(x for x in doc["configurations"] if x["configuration_id"] == cid)


def _mass_record_from_source_and_bridge(
    source: dict[str, Any], bridged: dict[str, Any], cid: str
) -> dict[str, Any]:
    src = _config_entry(source, cid)
    br = _bridged_config_entry(bridged, cid)["bridged_candidate"]
    inertia_src = inertia_from_components(src["inertia_about_system_cg_S_kg_m2"])
    inertia_br = np.asarray(br["inertia_about_system_cg_S_kg_m2"], dtype=float)
    cross = {
        "mass_abs_kg": abs(float(src["mass"]["value_kg"]) - float(br["mass_kg"])),
        "cg_max_abs_m": float(np.max(np.abs(np.asarray(src["cg_S_m"], float) - np.asarray(br["cg_S_m"], float)))),
        "inertia_max_abs_kgm2": float(np.max(np.abs(inertia_src - inertia_br))),
    }
    return {
        "configuration_id": cid,
        "mass": float(br["mass_kg"]),
        "cg": np.asarray(br["cg_S_m"], dtype=float),
        "Icg": inertia_br,
        "Mbb": spatial_inertia(float(br["mass_kg"]), np.asarray(br["cg_S_m"], float), inertia_br),
        "composition": src["composition"],
        "source_vs_bridged": cross,
    }


def _component_spatial(component: dict[str, Any]) -> np.ndarray:
    return spatial_inertia(
        float(component["mass_kg"]),
        np.asarray(component["com_S_m"], dtype=float),
        np.asarray(component["inertia_about_own_com_S_kg_m2"], dtype=float),
    )


def _import_fk_module(path: Path):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("e22_accepted_b601_fk", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import FK module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_context(config_path: Path | None = None) -> dict[str, Any]:
    config_path = config_path or E22_DIR / "config" / "e22_config.yaml"
    cfg = _read_yaml(config_path)
    pins: dict[str, Any] = {}
    for key, item in cfg["source_pins"].items():
        path = PROJECT_ROOT / item["path"]
        actual = sha256(path)
        if actual != str(item["sha256"]).upper():
            raise RuntimeError(f"HASH_MISMATCH:{key}:{actual}:{item['sha256']}")
        pins[key] = {"path": item["path"], "sha256": actual}

    source_ledger = _read_yaml(PROJECT_ROOT / pins["r2_mass_ledger"]["path"])
    bridged_ledger = _read_yaml(PROJECT_ROOT / pins["bridged_r2_mass_ledger"]["path"])
    masses = {cid: _mass_record_from_source_and_bridge(source_ledger, bridged_ledger, cid)
              for cid in ("C07", "C08", "C09")}

    mission = _read_yaml(PROJECT_ROOT / pins["pregrasp_mission_contract"]["path"])
    q_pre = np.asarray(mission["states"]["PREGRASP"]["q_rad"], dtype=float)
    bridge = _read_yaml(PROJECT_ROOT / pins["confirmed_bridge"]["path"])
    T_S_A0 = np.asarray(
        bridge["frame_semantics"]["T_S_A0_dynamics"]["transform_S_A0_rows_m"], dtype=float
    )
    fk_mod = _import_fk_module(PROJECT_ROOT / pins["accepted_fk_module"]["path"])
    arm = fk_mod.B601Arm(str(PROJECT_ROOT / pins["accepted_b601_urdf"]["path"]))
    fk = arm.fk(q_pre, T_base=T_S_A0)
    T_E = np.asarray(fk["T_E"], dtype=float)

    rom_npz = np.load(PROJECT_ROOT / pins["round3_rom_npz"]["path"])
    rom_contract = _read_json(PROJECT_ROOT / pins["round3_rom_contract"]["path"])
    envelope = _read_json(PROJECT_ROOT / pins["round3_validity_envelope"]["path"])
    target_ssot = _read_yaml(PROJECT_ROOT / pins["target_ssot"]["path"])
    target_cad = {
        "target_satellite_v0": _read_json(PROJECT_ROOT / pins["target_satellite_full_tensor"]["path"]),
        "target_debris_v0": _read_json(PROJECT_ROOT / pins["target_debris_full_tensor"]["path"]),
    }
    harness_gate = _read_json(PROJECT_ROOT / pins["harness_mission_gate"]["path"])
    bridge_gate = _read_json(PROJECT_ROOT / pins["confirmed_bridge_gate"]["path"])
    round3_gate = _read_json(PROJECT_ROOT / pins["round3_gate"]["path"])
    contact_scene = _read_yaml(PROJECT_ROOT / pins["contact_scene"]["path"])
    contact_window_source = (PROJECT_ROOT / pins["contact_window_implementation"]["path"]).read_text(encoding="utf-8")
    common_capture_source = (PROJECT_ROOT / pins["common_capture_axis_source"]["path"]).read_text(encoding="utf-8")
    rom5_falsifier = _read_json(PROJECT_ROOT / pins["rom5_dimension_falsifier"]["path"])
    rom5_falsifier_script_source = (
        PROJECT_ROOT / pins["rom5_dimension_falsifier_script"]["path"]
    ).read_text(encoding="utf-8")

    owner = _read_yaml(PROJECT_ROOT / pins["latest_owner_transcription"]["path"])
    owner_keys = list(owner["directives"].keys())
    required_owner = cfg["authority_scope"]["owner_decisions_consumed"]
    if owner_keys != required_owner:
        raise RuntimeError(f"OWNER_AUTHORITY_MISMATCH:{owner_keys}")

    context = {
        "cfg": cfg,
        "config_path": str(config_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "pins": pins,
        "source_ledger": source_ledger,
        "bridged_ledger": bridged_ledger,
        "masses": masses,
        "q_pre": q_pre,
        "T_S_A0": T_S_A0,
        "T_E": T_E,
        "rom": rom_npz,
        "rom_contract": rom_contract,
        "envelope": envelope,
        "target_ssot": target_ssot,
        "target_cad": target_cad,
        "harness_gate": harness_gate,
        "bridge_gate": bridge_gate,
        "round3_gate": round3_gate,
        "contact_scene": contact_scene,
        "contact_window_source": contact_window_source,
        "common_capture_source": common_capture_source,
        "rom5_falsifier": rom5_falsifier,
        "rom5_falsifier_script_source": rom5_falsifier_script_source,
    }
    context["authority_audits"] = build_authority_audits(context)
    if not context["authority_audits"]["preflight"]["pass"]:
        failed = [x["id"] for x in context["authority_audits"]["preflight"]["criteria"] if not x["pass"]]
        raise RuntimeError("FAIL_CLOSED_AUTHORITY_PREFLIGHT:"+",".join(failed))
    return context


def build_authority_audits(ctx: dict[str, Any]) -> dict[str, Any]:
    cfg, masses = ctx["cfg"], ctx["masses"]
    # C07 exact subtract/re-add proof: the full Mbb already transports both 0.78 kg wings.
    c07_components = masses["C07"]["composition"]
    solar = [x for x in c07_components if x["component_id"] in
             ("solar_array_r2_left", "solar_array_r2_right")]
    nonsolar = [x for x in c07_components if x not in solar]
    M_solar = sum((_component_spatial(x) for x in solar), np.zeros((6, 6)))
    M_residual = sum((_component_spatial(x) for x in nonsolar), np.zeros((6, 6)))
    M_reclosed = M_residual + M_solar
    M_c07 = masses["C07"]["Mbb"]
    solar_mass = sum(float(x["mass_kg"]) for x in solar)
    double_count_mass = masses["C07"]["mass"] + solar_mass

    z = ctx["rom"]
    Mbq = np.block([
        [z["Gamma_t_L"].T, z["Gamma_t_R"].T],
        [z["Gamma_r_L"].T, z["Gamma_r_R"].T],
    ])
    Mqq = block_diag(z["Mrom"], z["Mrom"])
    Mc = np.block([[M_c07, Mbq], [Mbq.T, Mqq]])
    schur = Mqq - Mbq.T @ np.linalg.solve(M_c07, Mbq)

    target_geometry: dict[str, Any] = {}
    Rflip = np.diag(cfg["physics"]["target_to_S_rotation_diag"])
    pE = ctx["T_E"][:3, 3]
    for sid, sc in cfg["scenarios"].items():
        post = masses[sc["post_configuration"]]
        comp = next(x for x in post["composition"] if x["component_id"] == sc["target_component"])
        cad = ctx["target_cad"][sc["target_key"]]
        if sc["target_key"] == "target_satellite_v0":
            gp = next(x for x in cad["features"]["grasp_points_mm"] if x.get("name") == "launch_adapter_ring")
            grasp_origin = np.asarray(gp["point_mm"], float) / 1000.0
        else:
            grasp_origin = np.asarray(cad["features"]["grasp_points_mm"][0], float) / 1000.0
        r_cad_S = Rflip @ (grasp_origin - np.asarray(cad["cg_m"], float))
        r_ledger = pE - np.asarray(comp["com_S_m"], float)
        target_geometry[sid] = {
            "target_com_S_m": np.asarray(comp["com_S_m"], float),
            "grasp_lever_S_from_ledger_m": r_ledger,
            "grasp_lever_S_from_target_full_tensor_m": r_cad_S,
            "max_abs_alignment_residual_m": float(np.max(np.abs(r_ledger-r_cad_S))),
            "target_inertia_S_kgm2": np.asarray(comp["inertia_about_own_com_S_kg_m2"], float),
            "target_CAD_frame_raw_Ixz_kgm2": float(cad["inertia_kg_m2_about_com"]["Ixz"]),
            "target_Rflip_transformed_S_frame_Ixz_kgm2": float(np.asarray(comp["inertia_about_own_com_S_kg_m2"], float)[0, 2]),
        }

    scan_card = _read_yaml(PROJECT_ROOT / ctx["pins"]["sim10_scan_card_historical_pin_drift_witness"]["path"])
    live_hash = ctx["pins"]["live_threshold_registry"]["sha256"]
    scan_registry_hash = str(scan_card["frozen_inputs"]["threshold_registry"]["sha256"]).upper()

    # Fail-closed target and post-assembly audit.
    target_contract_checks: dict[str, Any] = {}
    spatial_residuals = []
    for sid, sc in cfg["scenarios"].items():
        post = masses[sc["post_configuration"]]
        comp = next(x for x in post["composition"] if x["component_id"] == sc["target_component"])
        cad = ctx["target_cad"][sc["target_key"]]
        ssot = ctx["target_ssot"][sc["target_key"]]
        Icad = inertia_from_components(cad["inertia_kg_m2_about_com"])
        Iexpected = Rflip @ Icad @ Rflip.T
        Iledger = np.asarray(comp["inertia_about_own_com_S_kg_m2"], float)
        target_spatial = _component_spatial(comp)
        spatial_res = post["Mbb"] - masses["C07"]["Mbb"] - target_spatial
        spatial_residuals.append(float(np.max(np.abs(spatial_res))))
        diag_ssot = np.asarray(ssot["inertia_diag_kgm2"], float)
        target_contract_checks[sid] = {
            "mass_max_abs_residual_kg": float(max(
                abs(float(sc["mass_kg"])-float(comp["mass_kg"])),
                abs(float(cad["mass_kg"])-float(comp["mass_kg"])),
                abs(float(ssot["mass_kg"])-float(comp["mass_kg"])))),
            "SSOT_diag_vs_CAD_diag_max_abs_kgm2": float(np.max(np.abs(diag_ssot-np.diag(Icad)))),
            "Rflip_Icad_RflipT_vs_ledger_max_abs_kgm2": float(np.max(np.abs(Iexpected-Iledger))),
            "post_Mbb_minus_C07_minus_target_spatial_max_abs": float(np.max(np.abs(spatial_res))),
            "grasp_alignment_max_abs_m": target_geometry[sid]["max_abs_alignment_residual_m"],
        }

    Rfull = full_reconstruction_operators(ctx)
    Phi = z["Phi_rom"]
    operator_residuals = {
        "w_nodes": float(np.max(np.abs(Rfull["w_nodes"]@Phi-z["R_w_nodes"]))),
        "theta_dofs": float(np.max(np.abs(Rfull["theta_dofs"]@Phi-z["R_theta_dofs"]))),
        "torsion_nodes": float(np.max(np.abs(Rfull["torsion_nodes"]@Phi-z["R_torsion_nodes"]))),
        "hinge_relative": float(np.max(np.abs(Rfull["hinge_relative"]@Phi-z["R_hinge_relative"]))),
        "tip_w": float(np.max(np.abs(Rfull["tip_w"]@Phi-z["R_tip_w"]))),
    }
    round3_ok = (ctx["round3_gate"].get("technical_verdict") == "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS" and
                 ctx["round3_gate"].get("summary") == {"passed": 17, "total": 17} and
                 ctx["round3_gate"].get("review_status") == "PENDING_OWNER_REVIEW" and
                 ctx["round3_gate"].get("next_stage_authorized") is False and
                 ctx["round3_gate"].get("release_credit") is False)
    bridge_ok = (ctx["bridge_gate"].get("mpi_gate") == "PASS" and
                 ctx["bridge_gate"].get("criterion_counts", {}).get("pass") == 9 and
                 ctx["bridge_gate"].get("bottom_line_metrics", {}).get("hash_mismatch") == 0 and
                 ctx["bridge_gate"].get("next_stage_authorized") is False and
                 ctx["bridge_gate"].get("release_credit") is False)
    contact_cfg = ctx["contact_scene"]["contact"]
    half_sine_source_ok = ("np.pi / (2.0 * T_c)" in ctx["contact_window_source"] and
                           "np.sin(np.pi * t / T_c)" in ctx["contact_window_source"] and
                           contact_cfg["model"] == "half_sine_equal_impulse" and
                           float(contact_cfg["T_c_ms_nominal"]) == 20.0 and
                           [float(x) for x in contact_cfg["T_c_ms_sweep"]] == [5.0, 10.0, 20.0, 50.0, 100.0] and
                           bool(contact_cfg["lockup_after_window"]))
    shape_ok = (z["M"].shape == (183, 183) and z["Phi_rom"].shape == (183, 5) and
                z["Gamma_t_L"].shape == (5, 3) and z["Gamma_r_L"].shape == (5, 3) and
                np.max(np.abs(z["M"]-z["M"].T)) < 1.0e-12 and
                np.linalg.eigvalsh(z["M"])[0] > 0.0)
    linearity_limits = ctx["envelope"]["quantitative_linearity_contract"]["limits"]
    linearity_contract_ok = (
        ctx["envelope"]["quantitative_linearity_contract"]["out_of_domain_policy"] == "FAIL_CLOSED__NO_LINEAR_ROM_EXTRAPOLATION" and
        float(linearity_limits["max_abs_bending_slope_rad"]) == 0.05 and
        float(linearity_limits["max_abs_transverse_node_displacement_m"]) == 0.030000000000000006 and
        max(operator_residuals.values()) <= 1.0e-12)
    axis_match = re.search(r"TUMBLE_AXIS\s*=\s*np\.array\((\[[^\]]+\])\)", ctx["common_capture_source"])
    if axis_match is None:
        common_axis_ok = False
        common_axis = np.full(3, np.nan)
    else:
        common_axis = np.asarray(ast.literal_eval(axis_match.group(1)), float)
        common_axis /= np.linalg.norm(common_axis)
        cfg_axis = np.asarray(cfg["physics"]["tumble_axis_target"], float)
        cfg_axis /= np.linalg.norm(cfg_axis)
        common_axis_ok = np.max(np.abs(common_axis-cfg_axis)) <= 1.0e-15
    th = cfg["diagnostic_thresholds"]
    target_contract_ok = target_contract_pass(target_contract_checks, th)
    falsifier_contract_ok = rom5_falsifier_contract_pass(ctx, rom5_falsifier_summary(ctx))
    criteria = [
        {"id": "PF01_HASH_PINS", "pass": True, "detail": "all configured sources byte-hash verified before parse"},
        {"id": "PF02_LATEST_OWNER_AUTHORITY", "pass": True, "detail": "ODR-GPT-01..06 exact transcription consumed"},
        {"id": "PF03_BRIDGE_GATE", "pass": bool(bridge_ok), "detail": "bridge Gate scoped PASS, 9/9, zero hash mismatch, no release"},
        {"id": "PF04_ROUND3_GATE", "pass": bool(round3_ok), "detail": "Round3 provisional physics Gate 17/17, review pending, no release"},
        {"id": "PF05_BRIDGED_MASS_CROSS", "pass": all(max(v.values()) <= 1.0e-12 for v in (masses[c]["source_vs_bridged"] for c in masses)), "detail": "C07-C09 source and bridged rows identical"},
        {"id": "PF06_TARGET_FULL_TENSOR_PLACEMENT", "pass": bool(target_contract_ok), "detail": "field-specific mass<=1e-12kg, inertia/spatial<=1e-12kgm2, grasp<=1e-9m"},
        {"id": "PF07_MATRIX_SHAPE_SYMMETRY_SPD", "pass": bool(shape_ok and np.linalg.eigvalsh(Mc)[0] > 0 and np.linalg.eigvalsh(schur)[0] > 0), "detail": "183-DOF and 16x16 coupled matrices"},
        {"id": "PF08_LINEarity_RECONSTRUCTION", "pass": bool(linearity_contract_ok), "detail": "machine-readable operators and 0.05rad/0.03m fail-closed domain"},
        {"id": "PF09_CONTACT_WINDOW", "pass": bool(half_sine_source_ok), "detail": "unit-integral half sine, 20ms nominal, 5-100ms sweep, lockup"},
        {"id": "PF10_THRESHOLD_DRIFT", "pass": bool(scan_registry_hash != live_hash), "detail": "drift positively detected; sim10 authority cannot be inherited"},
        {"id": "PF11_COMMON_TUMBLE_AXIS", "pass": bool(common_axis_ok), "detail": "normalized config axis equals hash-pinned common capture axis"},
        {"id": "PF12_ROM5_DIMENSION_FALSIFIER", "pass": bool(falsifier_contract_ok), "detail": "hash-pinned red-team artifact/script; 792 combinations and 5D/6D/7D fields bound"},
    ]

    return {
        "pregrasp_q_rad": ctx["q_pre"],
        "pregrasp_q_source_sha256": ctx["pins"]["pregrasp_mission_contract"]["sha256"],
        "fk_T_S_E": ctx["T_E"],
        "fk_contact_point_S_m": pE,
        "target_geometry": target_geometry,
        "bridged_mass_source_cross": {cid: masses[cid]["source_vs_bridged"] for cid in masses},
        "solar_decomposition": {
            "solar_members_count": len(solar),
            "solar_mass_total_kg": solar_mass,
            "nonsolar_residual_mass_kg": masses["C07"]["mass"] - solar_mass,
            "reclosed_mass_kg": masses["C07"]["mass"],
            "Mbb_reclose_max_abs": float(np.max(np.abs(M_reclosed-M_c07))),
            "semantics": "C07 Mbb includes both rigid-wing transport terms; Gamma/Mqq are relative-coordinate blocks and add no rigid mass",
            "negative_control": {
                "injected_operation": "add both 0.78 kg rigid solar members to already-complete C07",
                "detected_classification": "DOUBLE_COUNT_SOLAR_R2",
                "wrong_total_mass_kg": double_count_mass,
                "excess_mass_kg": solar_mass,
                "detected": abs(double_count_mass - masses["C07"]["mass"]) > 1.0,
            },
        },
        "coupled_mass_matrix": {
            "shape": list(Mc.shape),
            "min_eigenvalue": float(np.linalg.eigvalsh(Mc)[0]),
            "condition_number": float(np.linalg.cond(Mc)),
            "schur_min_eigenvalue": float(np.linalg.eigvalsh(schur)[0]),
        },
        "threshold_authority": {
            "diagnostic_thresholds_explicit_from_integration_spec": cfg["diagnostic_thresholds"],
            "live_registry_sha256": live_hash,
            "sim10_scan_card_sha256": ctx["pins"]["sim10_scan_card_historical_pin_drift_witness"]["sha256"],
            "scan_card_pinned_registry_sha256": scan_registry_hash,
            "scan_card_contains_live_registry_hash": scan_registry_hash == live_hash,
            "threshold_hash_drift_detected": scan_registry_hash != live_hash,
            "sim10_authority_inheritance": "NOT_INHERITED_THRESHOLD_HASH_DRIFT",
        },
        "harness_independent_fact": {
            "harness_gate": ctx["harness_gate"].get("harness_gate"),
            "mission_candidate_release": False,
            "dynamics_candidate_classification_does_not_override_harness": True,
        },
        "target_contract_checks": target_contract_checks,
        "response_operator_backcheck_max_abs": operator_residuals,
        "common_tumble_axis_normalized": common_axis,
        "contact_momentum_semantics": "chaser M*[v_S,omega] angular block is already about S origin; target Mt angular block is about target CG, so only target receives +c_target cross P shift",
        "preflight": {"criteria": criteria, "passed": sum(int(x["pass"]) for x in criteria),
                      "total": len(criteria), "pass": all(x["pass"] for x in criteria)},
    }


def assemble_chaser_model(
    ctx: dict[str, Any], configuration_id: str, corner: str, modes_per_wing: int,
    damping_lane: str = "UNDAMPED_CONSERVATION_GATE",
) -> dict[str, Any]:
    base = ctx["masses"][configuration_id]
    z = ctx["rom"]
    n = int(modes_per_wing)
    if n == 0:
        return {
            "M": base["Mbb"].copy(), "Mbb": base["Mbb"].copy(),
            "Mbq": np.zeros((6, 0)), "Mqq": np.zeros((0, 0)),
            "K": np.zeros((0, 0)), "C": np.zeros((0, 0)),
            "n": 0, "modes_per_wing": 0, "configuration": configuration_id,
            "damping_lane": "NOT_APPLICABLE_RIGID",
        }
    if not 1 <= n <= 5:
        raise ValueError("modes_per_wing must be 0..5")
    # Pre-registered nested order by nominal frequency, mapped from stored
    # [B1,B2,B3,T1,T2] to [B1,T1,T2,B2,B3].
    nested_all = np.array([0, 3, 4, 1, 2], dtype=int)
    idx = nested_all[:n]
    labels_all = np.array(["BENDING_1", "TORSION_1", "TORSION_2", "BENDING_2", "BENDING_3"])
    GtL, GtR = z["Gamma_t_L"][idx], z["Gamma_t_R"][idx]
    GrL, GrR = z["Gamma_r_L"][idx], z["Gamma_r_R"][idx]
    Mbq = np.block([[GtL.T, GtR.T], [GrL.T, GrR.T]])
    Mwing = z["Mrom"][np.ix_(idx, idx)]
    Kwing = z[f"Krom_{corner}"][np.ix_(idx, idx)]
    if damping_lane == "UNDAMPED_CONSERVATION_GATE":
        Cwing = np.zeros((n, n))
    elif damping_lane == "PROVISIONAL_DAMPED_SENSITIVITY":
        Cwing = z[f"Crom_{corner}"][np.ix_(idx, idx)]
    else:
        raise ValueError(f"unknown damping_lane {damping_lane}")
    Mqq = block_diag(Mwing, Mwing)
    K = block_diag(Kwing, Kwing)
    C = block_diag(Cwing, Cwing)
    M = np.block([[base["Mbb"], Mbq], [Mbq.T, Mqq]])
    return {
        "M": M, "Mbb": base["Mbb"], "Mbq": Mbq, "Mqq": Mqq,
        "K": K, "C": C, "n": 2*n, "modes_per_wing": n,
        "configuration": configuration_id, "stored_mode_indices": idx,
        "retained_mode_labels": labels_all[:n].tolist(),
        "damping_lane": damping_lane,
    }


def target_record(ctx: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    sc = ctx["cfg"]["scenarios"][scenario_id]
    post = ctx["masses"][sc["post_configuration"]]
    comp = next(x for x in post["composition"] if x["component_id"] == sc["target_component"])
    mass = float(comp["mass_kg"])
    cg = np.asarray(comp["com_S_m"], dtype=float)
    I = np.asarray(comp["inertia_about_own_com_S_kg_m2"], dtype=float)
    pE = ctx["T_E"][:3, 3]
    r = pE - cg
    Mt = block_diag(mass*np.eye(3), I)
    Jt = np.block([[np.eye(3), -skew(r)], [np.zeros((3, 3)), np.eye(3)]])
    axis_T = np.asarray(ctx["cfg"]["physics"]["tumble_axis_target"], dtype=float)
    axis_T /= np.linalg.norm(axis_T)
    Rflip = np.diag(ctx["cfg"]["physics"]["target_to_S_rotation_diag"])
    axis_S = Rflip @ axis_T
    omega = math.radians(float(sc["tumble_dps"])) * axis_S
    return {
        "mass": mass, "cg": cg, "I": I, "Mt": Mt, "Jt": Jt,
        "grasp_lever": r, "axis_S": axis_S, "omega": omega,
        "post_configuration": sc["post_configuration"], "scenario": sc,
    }


def _contact_momentum(Mc: np.ndarray, uc: np.ndarray, Mt: np.ndarray,
                      ut: np.ndarray, target_cg: np.ndarray) -> np.ndarray:
    pc = Mc @ uc
    pt = Mt @ ut
    return np.r_[pc[:3] + pt[:3], pc[3:6] + pt[3:6] + np.cross(target_cg, pt[:3])]


def _mechanical_energy(M: np.ndarray, u: np.ndarray, K: np.ndarray,
                       eta: np.ndarray) -> float:
    return float(0.5*u @ (M @ u) + (0.5*eta @ (K @ eta) if eta.size else 0.0))


def _linearity_metrics(ctx: dict[str, Any], eta_contact: np.ndarray,
                       eta_post: np.ndarray, modes_per_wing: int) -> dict[str, Any]:
    if modes_per_wing == 0:
        return {"evaluated": False, "state": "NOT_APPLICABLE_RIGID_LANE", "pass": True}
    z, env = ctx["rom"], ctx["envelope"]
    limits = env["quantitative_linearity_contract"]["limits"]
    names = {
        "w_nodes": (z["R_w_nodes"], "max_abs_transverse_node_displacement_m"),
        "theta_dofs": (z["R_theta_dofs"], "max_abs_bending_slope_rad"),
        "hinge_relative": (z["R_hinge_relative"], "max_abs_hinge_relative_rotation_rad"),
        "torsion_nodes": (z["R_torsion_nodes"], "max_abs_torsion_angle_rad"),
        "tip_w": (z["R_tip_w"], "max_abs_tip_transverse_deflection_m"),
    }
    histories = np.hstack([eta_contact, eta_post]) if eta_contact.size and eta_post.size else (
        eta_contact if eta_contact.size else eta_post
    )
    out: dict[str, Any] = {"evaluated": True, "authority": env["quantitative_linearity_contract"]["authority"]}
    wing_results = {}
    for iw, wing in enumerate(("LEFT", "RIGHT")):
        eta5 = np.zeros((5, histories.shape[1]))
        start = iw*modes_per_wing
        nested_all = np.array([0, 3, 4, 1, 2], dtype=int)
        eta5[nested_all[:modes_per_wing]] = histories[start:start+modes_per_wing]
        checks = {}
        for name, (Rop, limit_key) in names.items():
            peak = float(np.max(np.abs(Rop @ eta5))) if histories.shape[1] else 0.0
            limit = float(limits[limit_key])
            checks[name] = {"peak": peak, "limit": limit, "margin": limit-peak, "pass": peak <= limit}
        wing_results[wing] = {"checks": checks, "pass": all(x["pass"] for x in checks.values())}
    out["wings"] = wing_results
    out["pass"] = all(x["pass"] for x in wing_results.values())
    out["state"] = "IN_DOMAIN" if out["pass"] else "FAIL_CLOSED_OUT_OF_LINEAR_ROM_DOMAIN"
    return out


def _post_rhs(M: np.ndarray, K: np.ndarray, C: np.ndarray, n: int):
    def rhs(_t: float, y: np.ndarray) -> np.ndarray:
        r = y[:3]
        q = y[3:7]
        eta = y[7:7+n]
        u = y[7+n:7+n+6+n]
        v, w = u[:3], u[3:6]
        qd = u[6:]
        R = quat_to_rot(q)
        p = M @ u
        base_rhs = np.r_[-np.cross(w, p[:3]), -np.cross(w, p[3:6])-np.cross(v, p[:3])]
        modal_rhs = -K @ eta - C @ qd if n else np.zeros(0)
        udot = np.linalg.solve(M, np.r_[base_rhs, modal_rhs])
        qdot = 0.5 * quat_mul(q/np.linalg.norm(q), np.r_[0.0, w])
        damping_power = float(qd @ (C @ qd)) if n else 0.0
        return np.r_[R @ v, qdot, qd, udot, damping_power]
    return rhs


def _run_post_ode(
    model: dict[str, Any], u0: np.ndarray, eta0: np.ndarray, mass_record: dict[str, Any],
    duration: float, method: str, rtol: float, atol: float
) -> dict[str, Any]:
    M, K, C, n = model["M"], model["K"], model["C"], model["n"]
    y0 = np.r_[np.zeros(3), np.array([1.0, 0.0, 0.0, 0.0]), eta0, u0, 0.0]
    sol = solve_ivp(_post_rhs(M, K, C, n), (0.0, duration), y0,
                    method=method, rtol=rtol, atol=atol)
    if not sol.success:
        raise RuntimeError(f"POST_SOLVER_FAILED:{method}:{sol.message}")
    Y = sol.y
    eta = Y[7:7+n] if n else np.zeros((0, Y.shape[1]))
    U = Y[7+n:7+n+6+n]
    damping = float(Y[-1, -1])
    E0 = _mechanical_energy(M, u0, K, eta0)
    Ef = _mechanical_energy(M, U[:, -1], K, eta[:, -1] if n else np.zeros(0))
    energy_rel = abs(Ef + damping - E0) / max(abs(E0), 1.0e-14)

    p0 = M @ u0
    P0 = p0[:3]
    L0 = p0[3:6]
    linear_momentum_rel_peak = 0.0
    angular_momentum_rel_peak = 0.0
    linear_momentum_abs_peak = 0.0
    angular_momentum_abs_peak = 0.0
    attitude = []
    qnorm = []
    rates = []
    for j in range(Y.shape[1]):
        r, q = Y[:3, j], Y[3:7, j]
        R = quat_to_rot(q)
        p = M @ U[:, j]
        Pi = R @ p[:3]
        Li = R @ p[3:6] + np.cross(r, Pi)
        linear_momentum_rel_peak = max(linear_momentum_rel_peak, relnorm(Pi, P0))
        angular_momentum_rel_peak = max(angular_momentum_rel_peak, relnorm(Li, L0))
        linear_momentum_abs_peak = max(linear_momentum_abs_peak, float(np.linalg.norm(Pi-P0)))
        angular_momentum_abs_peak = max(angular_momentum_abs_peak, float(np.linalg.norm(Li-L0)))
        qn = np.linalg.norm(q)
        qnorm.append(abs(qn-1.0))
        qh = q / qn
        attitude.append(math.degrees(2.0*math.atan2(np.linalg.norm(qh[1:]), abs(qh[0]))))
        rates.append(math.degrees(np.linalg.norm(U[3:6, j])))
    if n:
        qdot = U[6:]
        modal_energy = 0.5*np.einsum("it,ij,jt->t", qdot, model["Mqq"], qdot) + \
                       0.5*np.einsum("it,ij,jt->t", eta, K, eta)
    else:
        modal_energy = np.zeros(Y.shape[1])
    p_initial = M @ u0
    Lcg = p_initial[3:6] - np.cross(mass_record["cg"], p_initial[:3])
    omega_equiv = np.linalg.solve(mass_record["Icg"], Lcg)
    return {
        "success": True, "method": method, "nfev": int(sol.nfev), "njev": int(sol.njev),
        "nlu": int(sol.nlu), "steps": int(sol.t.size), "t_final_s": float(sol.t[-1]),
        "eta_history": eta, "u_history": U, "time": sol.t,
        "post_capture_rate_initial_dps": float(math.degrees(np.linalg.norm(u0[3:6]))),
        "post_capture_rate_max_dps": float(max(rates)),
        "post_capture_rate_final_dps": float(math.degrees(np.linalg.norm(U[3:6, -1]))),
        "omega_plus_equiv_dps": float(math.degrees(np.linalg.norm(omega_equiv))),
        "omega_plus_equiv_semantics": "E22_DIAGNOSTIC_PROXY__Icg_inverse_times_L_about_combined_CG",
        "base_attitude_excursion_max_deg": float(max(attitude)),
        "modal_energy_max_J": float(np.max(modal_energy)),
        "modal_energy_final_J": float(modal_energy[-1]),
        "wheel_momentum_required_Nms": float(np.linalg.norm(Lcg)),
        "linear_momentum_relative_peak": float(linear_momentum_rel_peak),
        "angular_momentum_relative_peak": float(angular_momentum_rel_peak),
        "linear_momentum_absolute_peak_Ns": float(linear_momentum_abs_peak),
        "angular_momentum_absolute_peak_Nms": float(angular_momentum_abs_peak),
        "energy_balance_relative": float(energy_rel),
        "quaternion_norm_error_max": float(max(qnorm)),
        "damping_dissipation_J": damping,
        "energy_initial_J": E0, "energy_final_J": Ef,
    }


def _quat_increment(rotvec: np.ndarray) -> np.ndarray:
    angle = float(np.linalg.norm(rotvec))
    if angle < 1.0e-14:
        return np.r_[1.0, 0.5*np.asarray(rotvec, float)]
    axis = np.asarray(rotvec, float) / angle
    return np.r_[math.cos(0.5*angle), axis*math.sin(0.5*angle)]


def _run_post_projected_exponential(
    model: dict[str, Any], u0: np.ndarray, eta0: np.ndarray, mass_record: dict[str, Any],
    duration: float
) -> dict[str, Any]:
    """Stiff-linear-exact, nonlinear momentum-projected 40 s propagation.

    The K/C/modal-inertia part is advanced with an exponential trapezoidal step.
    Slow Euler-Poincare transport is a corrected exponential forcing and every
    accepted step is projected onto the invariant inertial P/H manifold while
    retaining modal conjugate momentum.  This avoids resolving 125 Hz modes for
    40 s with a monolithic implicit solver; Radau/BDF are used independently on
    the bounded cross window.
    """
    M, K, C, n = model["M"], model["K"], model["C"], model["n"]
    d = 6+n
    nz = n+d
    A = np.zeros((nz, nz))
    if n:
        A[:n, n+6:] = np.eye(n)
        Feta = np.vstack([np.zeros((6, n)), -K])
        Fqd = np.vstack([np.zeros((6, n)), -C])
        A[n:, :n] = np.linalg.solve(M, Feta)
        A[n:, n+6:] = np.linalg.solve(M, Fqd)
    z = np.r_[eta0, u0]
    q = np.array([1.0, 0.0, 0.0, 0.0])
    r = np.zeros(3)
    p0 = M @ u0
    P_I0, L_I0 = p0[:3].copy(), p0[3:6].copy()
    E0 = _mechanical_energy(M, u0, K, eta0)
    damping = 0.0
    linear_velocity_projection_rel_peak = 0.0
    angular_velocity_projection_rel_peak = 0.0
    modal_rate_projection_rel_peak = 0.0
    energy_projection_alpha_peak = 0.0

    times = [0.0]
    etas = [eta0.copy()]
    us = [u0.copy()]
    attitudes = [0.0]
    linear_momentum_errors = [0.0]
    angular_momentum_errors = [0.0]
    linear_momentum_abs_errors = [0.0]
    angular_momentum_abs_errors = [0.0]
    quat_errors = [0.0]
    cache: dict[float, tuple[np.ndarray, np.ndarray]] = {}

    def propagator(dt: float) -> tuple[np.ndarray, np.ndarray]:
        key = round(float(dt), 12)
        if key not in cache:
            aug = np.block([[A, np.eye(nz)], [np.zeros((nz, nz)), np.zeros((nz, nz))]])
            e = expm(aug*dt)
            cache[key] = (e[:nz, :nz], e[:nz, nz:])
        return cache[key]

    def nonlinear(zz: np.ndarray) -> np.ndarray:
        u = zz[n:]
        v, w = u[:3], u[3:6]
        p = M @ u
        b = np.r_[-np.cross(w, p[:3]), -np.cross(w, p[3:6])-np.cross(v, p[:3])]
        g = np.zeros(nz)
        g[n:] = np.linalg.solve(M, np.r_[b, np.zeros(n)])
        return g

    segments = [(min(duration, 0.5), 2.0e-4),
                (min(duration, 5.0), 1.0e-3),
                (duration, 5.0e-3)]
    t = 0.0
    for tend, dt_nom in segments:
        while t < tend-1.0e-15:
            dt = min(dt_nom, tend-t)
            Pm, Phim = propagator(dt)
            g0 = nonlinear(z)
            pred = Pm @ z + Phim @ g0
            cand = Pm @ z + Phim @ (0.5*(g0+nonlinear(pred)))
            u_old = z[n:]
            eta_old = z[:n]
            E_old = _mechanical_energy(M, u_old, K, eta_old)
            u_cand = cand[n:]
            v_mid = 0.5*(u_old[:3]+u_cand[:3])
            w_mid = 0.5*(u_old[3:6]+u_cand[3:6])
            R0 = quat_to_rot(q)
            r = r + R0 @ v_mid * dt
            q = quat_mul(q, _quat_increment(w_mid*dt))
            q = q/np.linalg.norm(q)

            # Enforce exact inertial P/H, preserve the candidate modal canonical momentum.
            R = quat_to_rot(q)
            p_cand = M @ u_cand
            base_body = np.r_[R.T @ P_I0, R.T @ (L_I0-np.cross(r, P_I0))]
            p_projected = np.r_[base_body, p_cand[6:]]
            u_projected = np.linalg.solve(M, p_projected)
            if n:
                # A second, scalar projection enforces the physical energy-minus-
                # damping balance while retaining P/H.  It scales only momentum
                # away from the zero-relative-modal-velocity minimum.
                pmin_tail = model["Mbq"].T @ np.linalg.solve(model["Mbb"], base_body)
                dp_tail = p_cand[6:] - pmin_tail
                p_min = np.r_[base_body, pmin_tail]
                u_min = np.linalg.solve(M, p_min)
                eta_new = cand[:n]
                E_min = _mechanical_energy(M, u_min, K, eta_new)
                for _ in range(3):
                    qd1 = u_projected[6:]
                    damp_step = 0.5*(float(u_old[6:]@(C@u_old[6:]))+
                                     float(qd1@(C@qd1)))*dt
                    E_target = E_old-damp_step
                    p_one = np.r_[base_body, pmin_tail+dp_tail]
                    u_one = np.linalg.solve(M, p_one)
                    E_one = _mechanical_energy(M, u_one, K, eta_new)
                    available = E_one-E_min
                    ratio = max((E_target-E_min)/max(available, 1.0e-30), 0.0)
                    alpha = math.sqrt(ratio)
                    p_projected = np.r_[base_body, pmin_tail+alpha*dp_tail]
                    u_projected = np.linalg.solve(M, p_projected)
                energy_projection_alpha_peak = max(energy_projection_alpha_peak, abs(alpha-1.0))
                qd1 = u_projected[6:]
                damp_step = 0.5*(float(u_old[6:]@(C@u_old[6:]))+
                                 float(qd1@(C@qd1)))*dt
            else:
                damp_step = 0.0
            linear_velocity_projection_rel_peak = max(
                linear_velocity_projection_rel_peak,
                relnorm(u_projected[:3], u_cand[:3]),
            )
            angular_velocity_projection_rel_peak = max(
                angular_velocity_projection_rel_peak,
                relnorm(u_projected[3:6], u_cand[3:6]),
            )
            if n:
                modal_rate_projection_rel_peak = max(
                    modal_rate_projection_rel_peak,
                    relnorm(u_projected[6:], u_cand[6:]),
                )
            cand[n:] = u_projected
            damping += damp_step
            z = cand
            t += dt
            p = M @ u_projected
            Pi = R @ p[:3]
            Li = R @ p[3:6] + np.cross(r, Pi)
            times.append(t)
            etas.append(z[:n].copy())
            us.append(u_projected.copy())
            attitudes.append(math.degrees(2.0*math.atan2(np.linalg.norm(q[1:]), abs(q[0]))))
            linear_momentum_errors.append(relnorm(Pi, P_I0))
            angular_momentum_errors.append(relnorm(Li, L_I0))
            linear_momentum_abs_errors.append(float(np.linalg.norm(Pi-P_I0)))
            angular_momentum_abs_errors.append(float(np.linalg.norm(Li-L_I0)))
            quat_errors.append(abs(np.linalg.norm(q)-1.0))

    eta_hist = np.asarray(etas, dtype=float).T if n else np.zeros((0, len(times)))
    U = np.asarray(us, dtype=float).T
    Ef = _mechanical_energy(M, U[:, -1], K, eta_hist[:, -1] if n else np.zeros(0))
    energy_rel = abs(Ef+damping-E0)/max(abs(E0), 1.0e-14)
    rates = np.degrees(np.linalg.norm(U[3:6], axis=0))
    if n:
        qdot = U[6:]
        modal_energy = 0.5*np.einsum("it,ij,jt->t", qdot, model["Mqq"], qdot) + \
                       0.5*np.einsum("it,ij,jt->t", eta_hist, K, eta_hist)
    else:
        modal_energy = np.zeros(U.shape[1])
    Lcg = p0[3:6] - np.cross(mass_record["cg"], p0[:3])
    omega_equiv = np.linalg.solve(mass_record["Icg"], Lcg)
    return {
        "success": True, "method": "PROJECTED_EXPONENTIAL_TRAPEZOID",
        "steps": len(times), "t_final_s": float(times[-1]),
        "eta_history": eta_hist, "u_history": U, "time": np.asarray(times),
        "post_capture_rate_initial_dps": float(math.degrees(np.linalg.norm(u0[3:6]))),
        "post_capture_rate_max_dps": float(np.max(rates)),
        "post_capture_rate_final_dps": float(rates[-1]),
        "omega_plus_equiv_dps": float(math.degrees(np.linalg.norm(omega_equiv))),
        "omega_plus_equiv_semantics": "E22_DIAGNOSTIC_PROXY__Icg_inverse_times_L_about_combined_CG",
        "base_attitude_excursion_max_deg": float(max(attitudes)),
        "modal_energy_max_J": float(np.max(modal_energy)),
        "modal_energy_final_J": float(modal_energy[-1]),
        "wheel_momentum_required_Nms": float(np.linalg.norm(Lcg)),
        "linear_momentum_relative_peak": float(max(linear_momentum_errors)),
        "angular_momentum_relative_peak": float(max(angular_momentum_errors)),
        "linear_momentum_absolute_peak_Ns": float(max(linear_momentum_abs_errors)),
        "angular_momentum_absolute_peak_Nms": float(max(angular_momentum_abs_errors)),
        "energy_balance_relative": float(energy_rel),
        "quaternion_norm_error_max": float(max(quat_errors)),
        "damping_dissipation_J": float(damping),
        "energy_initial_J": E0, "energy_final_J": Ef,
        "linear_velocity_projection_relative_peak": float(linear_velocity_projection_rel_peak),
        "angular_velocity_projection_relative_peak": float(angular_velocity_projection_rel_peak),
        "modal_rate_projection_relative_peak": float(modal_rate_projection_rel_peak),
        "energy_projection_alpha_deviation_peak": float(energy_projection_alpha_peak),
        "propagation_contract": (
            "stiff linear exact; corrected Euler-Poincare forcing; invariant inertial P/H "
            "projection plus physical energy-minus-damping scalar projection"
        ),
    }


def diagnostic_classification(rate_dps: float, momentum_Nms: float,
                              thresholds: dict[str, float]) -> str:
    if rate_dps > float(thresholds["post_capture_rate_max_dps"]):
        return "INFEASIBLE_RATE"
    if momentum_Nms <= float(thresholds["wheel_small_Nms"]):
        return "WHEELS_SMALL_TIER"
    if momentum_Nms <= float(thresholds["wheel_large_Nms"]):
        return "WHEELS_LARGE_TIER"
    return "THRUSTER_REQUIRED"


def simulate_case(
    ctx: dict[str, Any], scenario_id: str, lane: str, corner: str = "NOMINAL",
    modes_per_wing: int = 5, contact_window_ms: float = 20.0,
    method: str = "Radau", post_window_s: float | None = None,
    post_propagator: str = "PROJECTED_EXPONENTIAL",
    damping_lane: str = "UNDAMPED_CONSERVATION_GATE",
) -> dict[str, Any]:
    if lane == "RIGID_R2_CURRENT":
        modes_per_wing = 0
    elif lane != "SOLAR_R2_FLEX_CURRENT":
        raise ValueError(f"simulate_case cannot numerically run lane {lane}")
    cfg = ctx["cfg"]
    post_window_s = float(post_window_s if post_window_s is not None else cfg["physics"]["post_window_s"])
    rtol = float(cfg["physics"]["solver"]["rtol"])
    atol = float(cfg["physics"]["solver"]["atol"])
    pre = assemble_chaser_model(ctx, "C07", corner, modes_per_wing, damping_lane)
    tgt = target_record(ctx, scenario_id)
    post = assemble_chaser_model(ctx, tgt["post_configuration"], corner, modes_per_wing, damping_lane)
    n = pre["n"]
    pE = ctx["T_E"][:3, 3]
    Jbase = np.block([[np.eye(3), -skew(pE)], [np.zeros((3, 3)), np.eye(3)]])
    Jc = np.hstack([Jbase, np.zeros((6, n))])
    W = Jc @ np.linalg.solve(pre["M"], Jc.T) + tgt["Jt"] @ np.linalg.solve(tgt["Mt"], tgt["Jt"].T)
    W = 0.5*(W+W.T)
    approach_axis = ctx["T_E"][:3, 2]
    approach_axis = approach_axis / np.linalg.norm(approach_axis)
    uc0 = np.zeros(6+n)
    uc0[:3] = float(cfg["physics"]["approach_speed_mps"]) * approach_axis
    ut0 = np.r_[np.zeros(3), tgt["omega"]]
    eta0 = np.zeros(n)
    rel0 = Jc @ uc0 - tgt["Jt"] @ ut0
    lam = -np.linalg.solve(W, rel0)
    Tc = float(contact_window_ms) / 1000.0

    def contact_rhs(t: float, y: np.ndarray) -> np.ndarray:
        eta = y[:n]
        uc = y[n:n+6+n]
        ut = y[n+6+n:n+12+n]
        qd = uc[6:]
        shape = math.pi/(2.0*Tc) * math.sin(math.pi*t/Tc)
        wrench = lam*shape
        modal = -pre["K"] @ eta - pre["C"] @ qd if n else np.zeros(0)
        ucd = np.linalg.solve(pre["M"], np.r_[np.zeros(6), modal] + Jc.T @ wrench)
        utd = np.linalg.solve(tgt["Mt"], -tgt["Jt"].T @ wrench)
        power = float((Jc@uc - tgt["Jt"]@ut) @ wrench)
        damp = float(qd @ (pre["C"] @ qd)) if n else 0.0
        return np.r_[qd, ucd, utd, power, damp]

    y0 = np.r_[eta0, uc0, ut0, 0.0, 0.0]
    E_contact0 = _mechanical_energy(pre["M"], uc0, pre["K"], eta0) + 0.5*ut0 @ (tgt["Mt"] @ ut0)
    mom0 = _contact_momentum(pre["M"], uc0, tgt["Mt"], ut0, tgt["cg"])
    # Work and damping ledgers are O(1e-3 J) differences of larger kinetic
    # terms; give those two scalar states a stricter absolute tolerance so the
    # 1e-8 relative energy audit is not limited by their integration scale.
    contact_atol = np.full(y0.size, atol, dtype=float)
    ledger_atol = float(cfg["physics"]["solver"]["contact_work_damping_ledger_atol"])
    contact_atol[-2:] = min(atol, ledger_atol)
    contact_step_divisions = int(cfg["physics"]["solver"]["contact_max_step_divisions"])
    contact = solve_ivp(contact_rhs, (0.0, Tc), y0, method=method, rtol=rtol,
                        atol=contact_atol, max_step=Tc/contact_step_divisions)
    if not contact.success:
        raise RuntimeError(f"CONTACT_SOLVER_FAILED:{method}:{contact.message}")
    eta_end = contact.y[:n, -1]
    uc_end = contact.y[n:n+6+n, -1]
    ut_end = contact.y[n+6+n:n+12+n, -1]
    work = float(contact.y[-2, -1])
    damp_contact = float(contact.y[-1, -1])
    E_contact_end = _mechanical_energy(pre["M"], uc_end, pre["K"], eta_end) + 0.5*ut_end @ (tgt["Mt"] @ ut_end)
    energy_contact_abs = abs(E_contact_end + damp_contact - E_contact0 - work)
    energy_contact_reference = max(abs(E_contact0), abs(work), 1.0e-14)
    energy_contact_rel = energy_contact_abs / energy_contact_reference
    mom_window = _contact_momentum(pre["M"], uc_end, tgt["Mt"], ut_end, tgt["cg"])
    mom_window_linear_rel = relnorm(mom_window[:3], mom0[:3])
    mom_window_angular_rel = relnorm(mom_window[3:], mom0[3:])

    rel_end = Jc @ uc_end - tgt["Jt"] @ ut_end
    dlam = -np.linalg.solve(W, rel_end)
    uc_lock = uc_end + np.linalg.solve(pre["M"], Jc.T @ dlam)
    ut_lock = ut_end - np.linalg.solve(tgt["Mt"], tgt["Jt"].T @ dlam)
    lock_rel = Jc @ uc_lock - tgt["Jt"] @ ut_lock
    mom_lock = _contact_momentum(pre["M"], uc_lock, tgt["Mt"], ut_lock, tgt["cg"])
    mom_lock_linear_rel = relnorm(mom_lock[:3], mom0[:3])
    mom_lock_angular_rel = relnorm(mom_lock[3:], mom0[3:])
    E_before_lock = _mechanical_energy(pre["M"], uc_end, pre["K"], eta_end) + 0.5*ut_end @ (tgt["Mt"] @ ut_end)
    E_after_lock = _mechanical_energy(pre["M"], uc_lock, pre["K"], eta_end) + 0.5*ut_lock @ (tgt["Mt"] @ ut_lock)

    pc_lock = pre["M"] @ uc_lock
    ptotal = mom_lock
    generalized_post_momentum = np.r_[ptotal, pc_lock[6:]]
    u_post = np.linalg.solve(post["M"], generalized_post_momentum)
    attach_reconstructed = post["M"] @ u_post
    attach_linear_rel = relnorm(attach_reconstructed[:3], generalized_post_momentum[:3])
    attach_angular_rel = relnorm(attach_reconstructed[3:6], generalized_post_momentum[3:6])
    attach_modal_rel = relnorm(attach_reconstructed[6:], generalized_post_momentum[6:]) if n else 0.0
    E_post0 = _mechanical_energy(post["M"], u_post, post["K"], eta_end)
    attach_energy_drop = E_after_lock - E_post0

    if post_propagator == "PROJECTED_EXPONENTIAL":
        post_result = _run_post_projected_exponential(
            post, u_post, eta_end, ctx["masses"][tgt["post_configuration"]], post_window_s)
    elif post_propagator == "IMPLICIT_ODE":
        post_result = _run_post_ode(
            post, u_post, eta_end, ctx["masses"][tgt["post_configuration"]],
            post_window_s, method, rtol, atol)
    else:
        raise ValueError(f"unknown post_propagator {post_propagator}")
    eta_contact = contact.y[:n] if n else np.zeros((0, contact.t.size))
    linearity = _linearity_metrics(ctx, eta_contact, post_result["eta_history"], modes_per_wing)
    cls = diagnostic_classification(post_result["omega_plus_equiv_dps"],
                                    post_result["wheel_momentum_required_Nms"],
                                    cfg["diagnostic_thresholds"])
    stabilization = {
        "rate_within_2dps": post_result["omega_plus_equiv_dps"] <= float(cfg["diagnostic_thresholds"]["post_capture_rate_max_dps"]),
        "wheel_momentum_within_large_tier": post_result["wheel_momentum_required_Nms"] <= float(cfg["diagnostic_thresholds"]["wheel_large_Nms"]),
        "linearity_domain": bool(linearity["pass"]),
    }
    stabilization["proxy_pass"] = all(stabilization.values())
    return jsonable({
        "case_id": f"{lane}__{scenario_id}__{corner}__M{modes_per_wing}__TC{contact_window_ms:g}MS__{method}",
        "lane": lane, "scenario": scenario_id, "corner": corner,
        "modes_per_wing": modes_per_wing, "contact_window_ms": contact_window_ms,
        "retained_mode_labels": pre.get("retained_mode_labels", []),
        "retained_stored_indices": pre.get("stored_mode_indices", np.zeros(0, dtype=int)),
        "method": method, "post_window_s": post_window_s, "post_propagator": post_propagator,
        "damping_lane": damping_lane,
        "damping_gate_credit": damping_lane == "UNDAMPED_CONSERVATION_GATE",
        "mass_matrix_audit": {
            "pre_shape": list(pre["M"].shape), "post_shape": list(post["M"].shape),
            "pre_min_eigenvalue": float(np.linalg.eigvalsh(pre["M"])[0]),
            "post_min_eigenvalue": float(np.linalg.eigvalsh(post["M"])[0]),
            "pre_condition_number": float(np.linalg.cond(pre["M"])),
            "delassus_min_eigenvalue": float(np.linalg.eigvalsh(W)[0]),
            "delassus_condition_number": float(np.linalg.cond(W)),
        },
        "contact": {
            "impulse_lambda_6d": lam, "impulse_force_norm_Ns": float(np.linalg.norm(lam[:3])),
            "impulse_couple_norm_Nms": float(np.linalg.norm(lam[3:])),
            "lockup_delta_lambda_6d": dlam,
            "lockup_force_impulse_ratio": float(
                np.linalg.norm(dlam[:3])/max(np.linalg.norm(lam[:3]), 1.0e-30)),
            "lockup_couple_impulse_ratio": float(
                np.linalg.norm(dlam[3:])/max(np.linalg.norm(lam[3:]), 1.0e-30)),
            "post_lock_linear_velocity_residual_mps": float(np.linalg.norm(lock_rel[:3])),
            "post_lock_angular_velocity_residual_radps": float(np.linalg.norm(lock_rel[3:])),
            "linear_momentum_window_relative": mom_window_linear_rel,
            "linear_momentum_window_absolute_Ns": float(np.linalg.norm(mom_window[:3]-mom0[:3])),
            "angular_momentum_window_relative": mom_window_angular_rel,
            "angular_momentum_window_absolute_Nms": float(np.linalg.norm(mom_window[3:]-mom0[3:])),
            "linear_momentum_post_lock_relative": mom_lock_linear_rel,
            "linear_momentum_post_lock_absolute_Ns": float(np.linalg.norm(mom_lock[:3]-mom0[:3])),
            "angular_momentum_post_lock_relative": mom_lock_angular_rel,
            "angular_momentum_post_lock_absolute_Nms": float(np.linalg.norm(mom_lock[3:]-mom0[3:])),
            "energy_window_relative": energy_contact_rel,
            "energy_window_absolute_J": float(energy_contact_abs),
            "energy_window_reference_J": float(energy_contact_reference),
            "energy_initial_J": float(E_contact0),
            "energy_end_J": float(E_contact_end),
            "external_work_J": work,
            "damping_dissipation_J": damp_contact,
            "lockup_dissipation_J": float(E_before_lock-E_after_lock),
            "solver": {"success": True, "nfev": int(contact.nfev), "njev": int(contact.njev),
                       "nlu": int(contact.nlu), "steps": int(contact.t.size),
                       "rtol": rtol, "state_atol": atol,
                       "work_damping_ledger_atol": ledger_atol,
                       "max_step_s": Tc/contact_step_divisions},
            "base_delta_twist": uc_lock[:6]-uc0[:6],
        },
        "attach": {
            "linear_momentum_relative": attach_linear_rel,
            "linear_momentum_absolute_Ns": float(np.linalg.norm(
                attach_reconstructed[:3]-generalized_post_momentum[:3])),
            "angular_momentum_relative": attach_angular_rel,
            "angular_momentum_absolute_Nms": float(np.linalg.norm(
                attach_reconstructed[3:6]-generalized_post_momentum[3:6])),
            "modal_canonical_momentum_relative": attach_modal_rel,
            "modal_canonical_momentum_absolute_generalized": float(np.linalg.norm(
                attach_reconstructed[6:]-generalized_post_momentum[6:])) if n else 0.0,
            "ledger_semantics": (
                "linear N*s, angular N*m*s and modal canonical blocks are audited "
                "separately; unlike-dimension blocks are never concatenated into a norm"
            ),
            "energy_drop_J": float(attach_energy_drop),
            "pre_attach_energy_J": float(E_after_lock), "post_attach_energy_J": float(E_post0),
        },
        "post_capture": {k: v for k, v in post_result.items()
                         if k not in ("eta_history", "u_history", "time")},
        "linearity_domain": linearity,
        "diagnostic_gate_classification": cls,
        "stabilization_proxy": stabilization,
        "authority": {
            "classification_scope": "DIAGNOSTIC_ONLY_BEFORE_E15_RECERTIFICATION",
            "sim10_authority_inheritance": "NOT_INHERITED_THRESHOLD_HASH_DRIFT",
            "e15_inheritance": "NOT_INHERITED",
            "harness_state_independent": "UNSAFE",
            "next_stage_authorized": False,
            "release_credit": False,
        },
    })


def full_reconstruction_operators(ctx: dict[str, Any]) -> dict[str, np.ndarray]:
    semantics = ctx["rom_contract"]["reduced_hf_dof_semantics"]
    nd = len(semantics)
    def row(idx: int) -> np.ndarray:
        r = np.zeros(nd)
        r[idx] = 1.0
        return r
    w_items = sorted((x for x in semantics if x["kind"] == "TRANSVERSE_W"), key=lambda x: x["node"])
    theta_items = [x for x in semantics if x["kind"] == "BENDING_SLOPE_THETA"]
    torsion_items = sorted((x for x in semantics if x["kind"] == "TORSION_PHI"), key=lambda x: x["node"])
    Rw = np.vstack([np.zeros(nd)] + [row(x["reduced_index_0based"]) for x in w_items])
    Rt = np.vstack([row(x["reduced_index_0based"]) for x in theta_items])
    Rtor = np.vstack([np.zeros(nd)] + [row(x["reduced_index_0based"]) for x in torsion_items])
    by_node: dict[int, list[dict[str, Any]]] = {}
    for x in theta_items:
        by_node.setdefault(int(x["node"]), []).append(x)
    Rhinge = [row(by_node[0][0]["reduced_index_0based"])]
    for inode in (20, 40):
        L = next(x for x in by_node[inode] if x["side"] == "L")
        R = next(x for x in by_node[inode] if x["side"] == "R")
        Rhinge.append(row(R["reduced_index_0based"])-row(L["reduced_index_0based"]))
    Rtip = row(w_items[-1]["reduced_index_0based"])[None, :]
    return {"w_nodes": Rw, "theta_dofs": Rt, "torsion_nodes": Rtor,
            "hinge_relative": np.vstack(Rhinge), "tip_w": Rtip}


def _modal_half_sine(
    M: np.ndarray, K: np.ndarray, f_impulse: np.ndarray, zeta: float, Tc: float,
    t_contact: np.ndarray, t_post: np.ndarray,
) -> dict[str, Any]:
    # Near-degenerate bending/torsion subspaces rotate with threaded LAPACK and
    # change discretely sampled response peaks at O(1e-7).  The physical answer
    # is invariant, but evidence hashes are not.  Pin one BLAS thread and the
    # generalized symmetric-definite GVD driver inside the call itself.
    with threadpool_limits(limits=1, user_api="blas"):
        lam, V = eigh(K, M, driver="gvd", check_finite=True)
    if np.min(lam) <= 0:
        raise RuntimeError("HF_DYNAMIC_VALIDATION_NONPOSITIVE_EIGENVALUE")
    omega = np.sqrt(lam)
    wd = omega*np.sqrt(1.0-zeta*zeta)
    a = zeta*omega
    Om = math.pi/Tc
    amp = math.pi/(2.0*Tc)
    F = V.T @ f_impulse
    den = (omega*omega-Om*Om)**2 + (2.0*zeta*omega*Om)**2
    Cc = F*amp*(omega*omega-Om*Om)/den
    Dd = -F*amp*(2.0*zeta*omega*Om)/den
    E = -Dd
    G = (-Cc*Om+a*E)/wd

    tc = np.asarray(t_contact, float)[None, :]
    expc = np.exp(-a[:, None]*tc)
    yc = Cc[:, None]*np.sin(Om*tc) + Dd[:, None]*np.cos(Om*tc) + \
         expc*(E[:, None]*np.cos(wd[:, None]*tc)+G[:, None]*np.sin(wd[:, None]*tc))
    ydc = Cc[:, None]*Om*np.cos(Om*tc) - Dd[:, None]*Om*np.sin(Om*tc) + expc*(
        (-a*E+wd*G)[:, None]*np.cos(wd[:, None]*tc) +
        (-a*G-wd*E)[:, None]*np.sin(wd[:, None]*tc))
    yT, ydT = yc[:, -1], ydc[:, -1]
    tp = np.asarray(t_post, float)[None, :]
    A2 = (ydT+a*yT)/wd
    expp = np.exp(-a[:, None]*tp)
    yp = expp*(yT[:, None]*np.cos(wd[:, None]*tp)+A2[:, None]*np.sin(wd[:, None]*tp))
    ydp = expp*((-a*yT+wd*A2)[:, None]*np.cos(wd[:, None]*tp)+
                (-a*A2-wd*yT)[:, None]*np.sin(wd[:, None]*tp))
    y = np.hstack([yc, yp[:, 1:]])
    yd = np.hstack([ydc, ydp[:, 1:]])
    energy = 0.5*np.sum(yd*yd+(omega[:, None]*y)**2, axis=0)
    time = np.r_[np.asarray(t_contact, float), Tc+np.asarray(t_post, float)[1:]]
    return {"eigenvalues": lam, "modes": V, "eta_modal": y, "etad_modal": yd,
            "energy": energy, "frequency_hz": omega/(2.0*math.pi), "time": time}


def _response_metrics(modal: dict[str, Any], operators_physical: dict[str, np.ndarray]) -> dict[str, float]:
    V, y = modal["modes"], modal["eta_modal"]
    values = {name: R @ V @ y for name, R in operators_physical.items()}
    def peak(name: str) -> tuple[float, float]:
        envelope = np.max(np.abs(values[name]), axis=0)
        i = int(np.argmax(envelope))
        return float(envelope[i]), float(modal["time"][i])
    tip, t_tip = peak("tip_w")
    node, t_node = peak("w_nodes")
    slope, t_slope = peak("theta_dofs")
    hinge, t_hinge = peak("hinge_relative")
    torsion, t_torsion = peak("torsion_nodes")
    ie = int(np.argmax(modal["energy"]))
    return {
        "tip_peak_m": tip, "tip_peak_time_s": t_tip,
        "node_peak_m": node, "node_peak_time_s": t_node,
        "slope_peak_rad": slope, "slope_peak_time_s": t_slope,
        "hinge_peak_rad": hinge, "hinge_peak_time_s": t_hinge,
        "torsion_peak_rad": torsion, "torsion_peak_time_s": t_torsion,
        "modal_energy_peak_J": float(np.max(modal["energy"])),
        "modal_energy_peak_time_s": float(modal["time"][ie]),
        "modal_energy_final_J": float(modal["energy"][-1]),
    }


def _standalone_rom_implicit(
    M: np.ndarray, K: np.ndarray, C: np.ndarray, fimp: np.ndarray,
    operators: dict[str, np.ndarray], Tc: float, post_s: float,
    method: str, rtol: float, atol: float,
) -> dict[str, Any]:
    n = M.shape[0]
    def rhs(t: float, y: np.ndarray) -> np.ndarray:
        q, qd = y[:n], y[n:]
        shape = math.pi/(2.0*Tc)*math.sin(math.pi*t/Tc) if t <= Tc else 0.0
        qdd = np.linalg.solve(M, fimp*shape-C@qd-K@q)
        return np.r_[qd, qdd]
    sol = solve_ivp(rhs, (0.0, Tc+post_s), np.zeros(2*n), method=method,
                    rtol=rtol, atol=atol, max_step=min(Tc/20.0, 0.002))
    if not sol.success:
        raise RuntimeError(f"HF_ROM_{method}_FAILED:{sol.message}")
    q, qd = sol.y[:n], sol.y[n:]
    energy = 0.5*np.einsum("it,ij,jt->t", qd, M, qd) + 0.5*np.einsum("it,ij,jt->t", q, K, q)
    metrics = {
        "tip_peak_m": float(np.max(np.abs(operators["tip_w"]@q))),
        "node_peak_m": float(np.max(np.abs(operators["w_nodes"]@q))),
        "slope_peak_rad": float(np.max(np.abs(operators["theta_dofs"]@q))),
        "hinge_peak_rad": float(np.max(np.abs(operators["hinge_relative"]@q))),
        "torsion_peak_rad": float(np.max(np.abs(operators["torsion_nodes"]@q))),
        "modal_energy_peak_J": float(np.max(energy)),
        "modal_energy_final_J": float(energy[-1]),
    }
    return {"method": method, "success": True, "nfev": int(sol.nfev), "steps": int(sol.t.size), "metrics": metrics}


def run_hf_to_rom_dynamic_validation(
    ctx: dict[str, Any], base_delta_twist_6: np.ndarray,
    forcing_scenario: str = "TARGET_150KG_3DPS",
) -> dict[str, Any]:
    cfg = ctx["cfg"]
    hcfg = cfg["physics"]["hf_to_rom_validation"]
    Tc = float(hcfg["contact_window_ms"])/1000.0
    post_s = float(hcfg["post_window_s"])
    tc = np.linspace(0.0, Tc, int(hcfg["full_time_contact_samples"]))
    tp = np.linspace(0.0, post_s, int(hcfg["full_time_post_samples"]))
    z = ctx["rom"]
    Rfull = full_reconstruction_operators(ctx)
    Phi5 = z["Phi_rom"]
    op_backcheck = {
        "w_nodes": float(np.max(np.abs(Rfull["w_nodes"]@Phi5-z["R_w_nodes"]))),
        "theta_dofs": float(np.max(np.abs(Rfull["theta_dofs"]@Phi5-z["R_theta_dofs"]))),
        "torsion_nodes": float(np.max(np.abs(Rfull["torsion_nodes"]@Phi5-z["R_torsion_nodes"]))),
        "hinge_relative": float(np.max(np.abs(Rfull["hinge_relative"]@Phi5-z["R_hinge_relative"]))),
        "tip_w": float(np.max(np.abs(Rfull["tip_w"]@Phi5-z["R_tip_w"]))),
    }
    dv = np.asarray(base_delta_twist_6[:3], float)
    dw = np.asarray(base_delta_twist_6[3:], float)
    out_wings = {}
    all_five_errors = []
    cross_errors = []
    for wing in ("L", "R"):
        fimp = -(z[f"Bt_{wing}"]@dv + z[f"Br_{wing}"]@dw)
        full_modal = _modal_half_sine(z["M"], z["K_nominal"], fimp,
                                      float(hcfg["damping_ratio"]), Tc, tc, tp)
        full_metrics = _response_metrics(full_modal, Rfull)
        trunc = {}
        nested_all = np.array([0, 3, 4, 1, 2], dtype=int)
        nested_labels = ["BENDING_1", "TORSION_1", "TORSION_2", "BENDING_2", "BENDING_3"]
        for nm in (3, 4, 5):
            idx = nested_all[:nm]
            Phi = Phi5[:, idx]
            Mr = z["Mrom"][np.ix_(idx, idx)]
            Kr = z["Krom_NOMINAL"][np.ix_(idx, idx)]
            fr = Phi.T @ fimp
            rom_modal = _modal_half_sine(Mr, Kr, fr, float(hcfg["damping_ratio"]), Tc, tc, tp)
            ops = {name: R@Phi for name, R in Rfull.items()}
            metrics = _response_metrics(rom_modal, ops)
            compare_keys = [k for k in metrics if not k.endswith("_time_s")]
            abs_errors = {k: abs(metrics[k]-full_metrics[k]) for k in compare_keys}
            errors = {k: abs_errors[k]/max(abs(full_metrics[k]), 1.0e-14) for k in compare_keys}
            trunc[str(nm)] = {"stored_mode_indices": idx.tolist(), "retained_mode_labels": nested_labels[:nm],
                              "metrics": metrics, "absolute_error_vs_183dof": abs_errors,
                              "relative_error_vs_183dof": errors,
                              "max_relative_error": float(max(errors.values()))}
        all_five_errors.append(trunc["5"]["max_relative_error"])

        idx5 = nested_all
        Phi_ordered = Phi5[:, idx5]
        Mr5 = z["Mrom"][np.ix_(idx5, idx5)]
        Kr5 = z["Krom_NOMINAL"][np.ix_(idx5, idx5)]
        Cr5 = np.zeros_like(z["Crom_NOMINAL"][np.ix_(idx5, idx5)])
        f5 = Phi_ordered.T @ fimp
        ops5 = {name: R@Phi_ordered for name, R in Rfull.items()}
        rad = _standalone_rom_implicit(Mr5, Kr5, Cr5, f5, ops5, Tc, post_s,
                                       "Radau", float(cfg["physics"]["solver"]["rtol"]), float(cfg["physics"]["solver"]["atol"]))
        bdf = _standalone_rom_implicit(Mr5, Kr5, Cr5, f5, ops5, Tc, post_s,
                                       "BDF", float(cfg["physics"]["solver"]["rtol"]), float(cfg["physics"]["solver"]["atol"]))
        cross_keys = [k for k in rad["metrics"] if not k.endswith("_time_s")]
        cross = {k: abs(rad["metrics"][k]-bdf["metrics"][k]) /
                    max(abs(rad["metrics"][k]), abs(bdf["metrics"][k]), 1.0e-14)
                 for k in cross_keys}
        cross_max = float(max(cross.values()))
        cross_errors.append(cross_max)
        out_wings[wing] = {
            "forcing_impulse_generalized_norm": float(np.linalg.norm(fimp)),
            "full_183dof_frequency_min_hz": float(full_modal["frequency_hz"][0]),
            "full_183dof_frequency_max_hz": float(full_modal["frequency_hz"][-1]),
            "full_183dof_metrics": full_metrics,
            "truncation": trunc,
            "radau_bdf": {"Radau": rad, "BDF": bdf, "relative_differences": cross,
                           "max_relative_difference": cross_max},
        }
    limit = float(hcfg["truncation_relative_limit"])
    five_max = float(max(all_five_errors))
    cross_max = float(max(cross_errors))
    subset_pass = five_max <= limit and cross_max <= float(cfg["diagnostic_thresholds"]["solver_cross_relative_max"])
    falsifier_summary = rom5_falsifier_summary(ctx)
    if not rom5_falsifier_contract_pass(ctx, falsifier_summary, base_delta_twist_6):
        raise RuntimeError("ROM5_DIMENSION_FALSIFIER_FIELD_BINDING_FAILED")
    return jsonable({
        "schema": "R2_HF_TO_ROM_DYNAMIC_VALIDATION_V1",
        "scope": "linear R2 HF-to-five-mode subset only; not ANCF certification",
        "forcing_scenario": forcing_scenario,
        "forcing_contract": "per-wing -Bt*delta_vbase - Br*delta_omega_base under nominal 20 ms equal-impulse half-sine",
        "base_delta_twist_6": base_delta_twist_6,
        "full_model": "183-DOF generalized eigh of Round3 M/K_nominal; zeta=0 undamped conservation Gate lane",
        "damping_lane": "UNDAMPED_CONSERVATION_GATE",
        "operator_backcheck_max_abs": op_backcheck,
        "wings": out_wings,
        "five_mode_max_relative_error_vs_183dof": five_max,
        "truncation_limit": limit,
        "radau_bdf_max_relative_difference": cross_max,
        "radau_bdf_limit": float(cfg["diagnostic_thresholds"]["solver_cross_relative_max"]),
        "independent_red_team_falsifier_finding": falsifier_summary,
        "linear_subset_verdict": "E15_R2_LINEAR_SUBSET_PASS" if subset_pass else "E15_R2_LINEAR_SUBSET_FAIL",
        "legacy_ancf_status": "REPEAT_ANCF_CERTIFICATION",
        "e15_inheritance": "NOT_INHERITED",
        "pass": subset_pass,
    })
