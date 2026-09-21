"""Build e20 independent surrogate-mass sim11 ARM-only diagnostics.

The builder is deliberately fail-closed.  It consumes stock sim11 only through
an in-memory REORG adapter, never invokes scene A2/contact/target attachment,
and never edits an upstream asset.  The two historical C08 mass branches are
not selected or merged: each is completed by the same preregistered bus-only
uniform-density scalar surrogate and crossed independently with M01/M07.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib
import io
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml


MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parents[1]
RESULTS_ROOT = MODULE_ROOT / "results"
PREFIX = "30_simulation/e20_b601_independent_mass_branch_coupled_diagnostics"
GENERATED_LOCAL = "2026-08-23T23:10:00+08:00"

ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
SOLAR_R2_SHA256 = "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"

# name, project-relative path, frozen SHA256, solver-consumption class
SOURCE_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("loop_v3_gate", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/13_loop_continuation_v3/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V3.json", "A10FF303EE2B58DBA47339C2DC4267343CC934328C526FD9011D7C7A84869D8C", "AUTHORITY_BOUNDARY"),
    ("loop_v3_validation", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/13_loop_continuation_v3/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V3.json", "9BA7A42B66AA57A237916E17619F5726EB18E412DD4A82D432AD3DE6C90A8F0C", "AUTHORITY_BOUNDARY"),
    ("loop_v3_manifest", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/13_loop_continuation_v3/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V3.json", "0985FA10922A51738CAF79433FE759A2ADD435A6D11196F852D5CDEBF9347ED2", "AUTHORITY_BOUNDARY"),
    ("e19_gate", "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/E19_DIAGNOSTIC_EVALUATION_GATE_V1.json", "BEE6ED3D0DD7A73204536E2FFCF2840B5B066DB371DC15B40C98A128A230E439", "AUTHORITY_BOUNDARY"),
    ("e19_validation", "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/E19_VALIDATION_V1.json", "491E8DDC1FBB90C86438C5ED6419F066C2203E131B7F911E1AAD153670F58745", "AUTHORITY_BOUNDARY"),
    ("e19_manifest", "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/E19_OUTPUT_MANIFEST_V1.json", "53F30140FC0765B87F2B040363D17A3950CCB45606614263553D4AAAFC3CDF46", "AUTHORITY_BOUNDARY"),
    ("e19_register", "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/E19_DIAGNOSTIC_EVALUATION_REGISTER_V1.json", "3DF7C47F8AB8C8C6C104278CF69285B6EC5636D4F7ED46DA516C8D97F63B8571", "AUTHORITY_BOUNDARY"),
    ("e19_m07_sim15", "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/E19_M07_SIM15_RIGID_CAPTURE_RECOMPUTE_V1.json", "CA0824EEDB57B47E29457CFCF69E435EFF80676700738DC911950F28A4CFC2A1", "MASS_BRANCH_SOURCE_ONLY"),
    ("e18_m07_branch_register", "30_simulation/e18_b601_mission_input_branches/02_candidates/M07_22_ATTACHED_TARGET_RECOVERY_BRANCHES_V1.json", "0D02CE3531BC48317F5234140B03F5AC9284766DC87A9713E76D776532CFC286", "MASS_BRANCH_SOURCE_ONLY"),
    ("e15_gate", "30_simulation/e15_ancf_certification/results/gate_summary.json", "AAB4D609E219279C2563C8A38743AC1784BBF16DE399D5B8798439B0AC2DCA80", "UNRESOLVED_CERTIFICATION_DEBT"),
    ("sim11_gate", "30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json", "9309F5325271BF5EFDAA7ECAC2BCF20B4FECA3FCA771D22391A7D7D576F9366F", "HISTORICAL_GATE_BOUNDARY"),
    ("sim11_model_card", "20_engineering/config/coupled_scene/coupled_model_v0.yaml", "67A532FB29C7EF66229CB41D6D3882946A8454FF37EDD9CF5933E4C91C2663EB", "EXECUTION_INPUT_LEGACY_PROVISIONAL"),
    ("sim11_a1_card", "20_engineering/config/coupled_scene/scene_A1_arm_slew.yaml", "6E3B53F126F03644EC19F26A4B74911C737E6666DBC89B41A2D0C9D1694C7D3B", "FORMAT_REFERENCE_ONLY"),
    ("sim11_a2_card_excluded", "20_engineering/config/coupled_scene/scene_A2_capture.yaml", "4B979A1DFD183AD938D79D6EB05A8FB0D4164C0E075A5391B467CC50E173A707", "EXCLUDED_PROVISIONAL_DEBT_NOT_CONSUMED"),
    ("legacy_frame_tree", "20_engineering/config/geometry/frame_tree_v1.yaml", "958BFF23BF83434C773854FD0E78DA3B09BE4A3A213EB81A0741514750B3E55B", "EXECUTION_INPUT_M_DYNAMICS_ONLY"),
    ("legacy_flexible_appendage", "20_engineering/config/geometry/flexible_appendage_v1.yaml", "52FA88084C628CE8845E05DE0C0A892BCA5347B7146C8D1C6B99093927153786", "EXECUTION_INPUT_LEGACY_PROVISIONAL"),
    ("m4_digital_frame_tree", "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml", "67293323A45237FB9B415871A4160732EFB156DE74776C9E11ABA9C4202134CA", "PHYSICAL_FRAME_BOUNDARY_NOT_APPLIED"),
    ("m7_mass_properties_v2", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml", "151474DCD2F4EDDFC0C4417FCE7237557B5DE10BE77DB8617F5EDA3329ADF42B", "MASS_BRANCH_REFERENCE_NOT_RELEASE_AUTHORITY"),
    ("m7_dynamics_interface_v5_r2", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V5_R2.yaml", "9B6D8025D3318A66AB7DD9BD15F7EEE2CDE31DD7A0A9A4FDB5CE4AEB60DE8203", "CURRENT_R2_BOUNDARY_NOT_CONSUMED"),
    ("flexible_appendage_r2", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml", "A04ACFE440C636BB095585C74F71E3563FD35F6678FCFAA39355383A9BF6B3FD", "CURRENT_R2_BOUNDARY_NOT_CONSUMED"),
    ("flexible_appendage_r2_modes", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2_MODES.json", "E068DE078A0DC680A44807516733FDF018DD720B5F65636BB2B8D21E557593B6", "CURRENT_R2_BOUNDARY_NOT_CONSUMED"),
    ("mass_budget_v1", "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv", "073C802527E35C9495188EEFD5D8BA51F524D326142CF2AB31E436BAD0899392", "EXECUTION_INPUT_LEGACY_SPLIT"),
    ("m01_trajectory", "30_simulation/e18_b601_mission_input_branches/02_candidates/M01_HELD_STOW_TO_RELEASE_CLEAR_QUINTIC_V1.csv", "B4CB77804E6B9FC17C8910E56A0ECB34DC63B91659337E8BCAB0FCA6189E7AA9", "EXECUTION_INPUT"),
    ("m07_arm_only_trajectory", "30_simulation/e17_b601_mission_trajectory_candidates/results/candidates/M07_22_ARM_ONLY_QUINTIC_V1.csv", "8AFBE9B95E1078CA7F73A4546CE4CAE605655C413DE7AF997AA807E0C31ECBF2", "EXECUTION_INPUT"),
    ("sim11_coupled_dynamics", "30_simulation/sim_11_coupled_dynamics/src/coupled_dynamics.py", "B8727041872802CC6BB62A4977BF3393B328754BAE0959622ADA6F32B534FDD7", "EXECUTION_SOLVER"),
    ("sim11_ffr_panel", "30_simulation/sim_11_coupled_dynamics/src/ffr_panel.py", "CCD56EEC234625B180BE5CAEF0F935F5326C663E6754FA09E3CBD020512AFFCF", "EXECUTION_SOLVER"),
    ("sim11_config_loader", "30_simulation/sim_11_coupled_dynamics/src/config_loader.py", "716B92618DADF72D6BC7B7A47DBFAF9B48EA740162A33A5713EF2DA4145F3391", "EXECUTION_SOLVER"),
    ("sim05_b601_model", "30_simulation/sim_05_free_floating_arm/b601_model.py", "3E2B451476F437E482661E275073249AD101705251B78C042851C32AE741052F", "EXECUTION_SOLVER"),
    ("common_rigid_body", "30_simulation/common/rigid_body.py", "6CE88E6D0FA45B29694C43FDB6E2FAE6E8E61F309C9C1DC89A6A33FD5F32BC99", "EXECUTION_SOLVER"),
    ("accepted_urdf", "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf", ACCEPTED_URDF_SHA256, "IMMUTABLE_EXECUTION_INPUT"),
    ("solar_r2", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step", SOLAR_R2_SHA256, "IMMUTABLE_BOUNDARY_NOT_CONSUMED"),
)

STATIC_ARTIFACTS = (
    f"{PREFIX}/README.md",
    f"{PREFIX}/00_authority/E20_AUTHORITY_CONTRACT_V1.yaml",
    f"{PREFIX}/config/E20_INDEPENDENT_MASS_BRANCH_COUPLED_CAMPAIGN_V1.yaml",
    f"{PREFIX}/docs/preregistration.md",
    f"{PREFIX}/docs/method_and_limitations.md",
    f"{PREFIX}/src/build_e20_diagnostics.py",
    f"{PREFIX}/tests/validate_e20_diagnostics.py",
)

LANE_ORDER = (
    ("LEGACY_A__M01", "M4_DIAG_LEGACY_A", "M01"),
    ("LEGACY_A__M07_ARM_ONLY", "M4_DIAG_LEGACY_A", "M07_ARM_ONLY"),
    ("M3R_B__M01", "M4_DIAG_M3R_B", "M01"),
    ("M3R_B__M07_ARM_ONLY", "M4_DIAG_M3R_B", "M07_ARM_ONLY"),
)

TRAJECTORY_PATHS = {
    "M01": "30_simulation/e18_b601_mission_input_branches/02_candidates/M01_HELD_STOW_TO_RELEASE_CLEAR_QUINTIC_V1.csv",
    "M07_ARM_ONLY": "30_simulation/e17_b601_mission_trajectory_candidates/results/candidates/M07_22_ARM_ONLY_QUINTIC_V1.csv",
}
TRAJECTORY_OUTPUT_COUNTS = {"M01": 116, "M07_ARM_ONLY": 46}
BRANCH_COMPOSITE_KG = {"M4_DIAG_LEGACY_A": 50.69555594934299, "M4_DIAG_M3R_B": 51.081436764691}
BRANCH_SERVICE_KG = {"M4_DIAG_LEGACY_A": 28.69555594934299, "M4_DIAG_M3R_B": 29.081436764691}


def project_path(relative: str) -> Path:
    return PROJECT_ROOT / Path(relative)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def load_json(relative: str) -> Any:
    return json.loads(project_path(relative).read_text(encoding="utf-8"))


def load_yaml(relative: str) -> Any:
    return yaml.safe_load(project_path(relative).read_text(encoding="utf-8"))


def artifact_record(relative: str, data: bytes | None = None) -> dict[str, Any]:
    blob = project_path(relative).read_bytes() if data is None else data
    return {"path": relative.replace("\\", "/"), "sha256": sha256_bytes(blob), "bytes": len(blob)}


def relative_result(name: str) -> str:
    return f"{PREFIX}/results/{name}"


def build_input_manifest() -> dict[str, Any]:
    records = []
    for name, relative, expected, consumption in SOURCE_SPECS:
        path = project_path(relative)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"source hash drift: {name}: {actual} != {expected}")
        records.append({
            "name": name,
            "path": relative,
            "sha256": actual,
            "bytes": path.stat().st_size,
            "expected_sha256": expected,
            "exact_hash_match": True,
            "consumption_class": consumption,
        })

    sim11 = load_json("30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json")
    historical = sim11["artifacts_sha256"]
    rows = []
    for name, old_hash in historical.items():
        path = project_path(f"30_simulation/sim_11_coupled_dynamics/results/{name}")
        current = sha256_file(path)
        rows.append({"artifact": name, "historical_sha256": old_hash.upper(), "current_sha256": current, "bytewise_match": current == old_hash.upper()})
    mismatches = [row["artifact"] for row in rows if not row["bytewise_match"]]
    expected_mismatches = [name for name in historical if "_summary" in name and name.endswith(".json")]
    reorg_ok = (
        len(rows) == 58
        and sum(row["bytewise_match"] for row in rows) == 32
        and mismatches == expected_mismatches
        and all("30_simulation" in project_path(f"30_simulation/sim_11_coupled_dynamics/results/{name}").read_text(encoding="utf-8") for name in mismatches)
    )
    if not reorg_ok:
        raise RuntimeError("sim11 REORG artifact audit no longer matches frozen 32/26 route-only boundary")

    e15 = load_json("30_simulation/e15_ancf_certification/results/gate_summary.json")
    if not (
        e15["overall"] == "REPEAT_ANCF_CERTIFICATION"
        and math.isclose(e15["cross_solver_diagnostic"]["max_relative_difference"], 0.05637349419858036, rel_tol=0.0, abs_tol=0.0)
        and e15["final_candidate_cross_solver"]["gate_limit"] == 0.05
        and e15["final_candidate_cross_solver"]["available"] is False
        and e15["final_candidate_cross_solver"]["gate_pass"] is False
        and e15["final_candidate_cross_solver"]["max_relative_difference"] is None
    ):
        raise RuntimeError("e15 certification debt drift")

    return {
        "schema": "E20_INPUT_MANIFEST_V1",
        "generated_local": GENERATED_LOCAL,
        "scope": "HASH_BOUND_LEGACY_SIM11_SURROGATE_ARM_ONLY_DIAGNOSTIC_INPUTS",
        "records": records,
        "record_count": len(records),
        "source_set_sha256": sha256_bytes(canonical_json_bytes(records)),
        "all_exact_hash_match": True,
        "sim11_historical_artifact_audit": {
            "historical_manifest_count": len(rows),
            "current_bytewise_match_count": sum(row["bytewise_match"] for row in rows),
            "current_bytewise_mismatch_count": len(mismatches),
            "mismatch_artifacts": mismatches,
            "mismatch_artifacts_all_summary_json": all("_summary" in name and name.endswith(".json") for name in mismatches),
            "historical_gate_verdict": sim11["verdict"],
            "historical_gate_verdict_preserved": sim11["verdict"] == "SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS",
            "current_artifact_manifest_bytewise_complete": False,
            "reorg_route_only_semantic_diff": True,
            "historical_next_stage_authorized": bool(sim11["next_stage_authorized"]),
            "historical_next_stage_authorized_inherited": False,
            "artifact_rows": rows,
        },
        "sim11_provisional_boundary": {
            "PROVISIONAL_PARAMS": True,
            "provisional_fields": ["n_modes", "mode_shape", "stiffness_case", "zeta_modal", "contact_T_c"],
            "legacy_panel_mass_each_kg": 0.3483933,
            "legacy_stock_ffr_consumed": True,
            "current_R2_flexible_appendage_consumed": False,
            "current_R2_coupled_model_claimed": False,
            "scene_A2_consumed": False,
            "contact_T_c_consumed": False,
            "stock_loader_reads_unused_target_capture_metadata": True,
            "stock_load_model_config_used": False,
            "e20_narrow_arm_only_loader_used": True,
            "target_capture_metadata_read": False,
            "target_capture_metadata_consumed_by_dynamics": False,
        },
        "mass_authority_boundary": {
            "legacy_M4_A_B_branch_lifecycle": "TRANSITIONAL_SURROGATE_SENSITIVITY_ONLY",
            "current_M7_design_mass_v2_hash_bound_as_boundary": True,
            "current_M7_design_mass_v2_consumed_by_solver": False,
            "current_M7_design_mass_v2_superseded": False,
            "e21_rebind_required_for_current_M7_design_mass_dynamics": True,
        },
        "e15_certification_debt": {
            "ancf_certification_status": "REPEAT_ANCF_CERTIFICATION",
            "e15_cross_solver_max_relative_difference": 0.05637349419858036,
            "e15_gate_limit": 0.05,
            "e15_final_candidate_available": False,
            "ancf_certified": False,
            "flexible_safety_ready": False,
        },
        "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
        "solar_r2_sha256": SOLAR_R2_SHA256,
        "accepted_urdf_modified": False,
        "cross_lane_state_input_count": 0,
        "release_credit": False,
    }


def read_trajectory(key: str) -> dict[str, Any]:
    relative = TRAJECTORY_PATHS[key]
    with project_path(relative).open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    q_cols = [f"joint{i}_q_rad" for i in range(1, 7)]
    dq_cols = [f"joint{i}_dq_rad_s" for i in range(1, 7)]
    ddq_cols = [f"joint{i}_ddq_rad_s2" for i in range(1, 7)]
    t = np.asarray([float(row["t_s"]) for row in rows])
    q = np.asarray([[float(row[col]) for col in q_cols] for row in rows])
    dq = np.asarray([[float(row[col]) for col in dq_cols] for row in rows])
    ddq = np.asarray([[float(row[col]) for col in ddq_cols] for row in rows])
    duration = float(t[-1])
    x = np.clip(t / duration, 0.0, 1.0)
    s = 10 * x**3 - 15 * x**4 + 6 * x**5
    sd = (30 * x**2 - 60 * x**3 + 30 * x**4) / duration
    sdd = (60 * x - 180 * x**2 + 120 * x**3) / duration**2
    q0, q1 = q[0], q[-1]
    delta = q1 - q0
    q_ref = q0[None, :] + s[:, None] * delta[None, :]
    dq_ref = sd[:, None] * delta[None, :]
    ddq_ref = sdd[:, None] * delta[None, :]
    reconstruction = {
        "max_abs_q_error_rad": float(np.max(np.abs(q - q_ref))),
        "max_abs_dq_error_rad_s": float(np.max(np.abs(dq - dq_ref))),
        "max_abs_ddq_error_rad_s2": float(np.max(np.abs(ddq - ddq_ref))),
    }
    released_false = all(str(row.get("released_for_mission_gate", "")).lower() == "false" for row in rows)
    jaw_null = all(row.get("jaw_travel_m", "") == "" for row in rows) if key == "M07_ARM_ONLY" else True
    if max(reconstruction.values()) > 1.0e-11 or not released_false or not jaw_null:
        raise RuntimeError(f"trajectory audit failed: {key}")
    return {
        "key": key,
        "path": relative,
        "sha256": sha256_file(project_path(relative)),
        "t": t,
        "q": q,
        "dq": dq,
        "ddq": ddq,
        "q0": q0,
        "q1": q1,
        "duration": duration,
        "source_sample_count": len(rows),
        "release_flags_all_false": released_false,
        "jaw_travel_all_null": jaw_null,
        "reconstruction": reconstruction,
    }


def load_sim11_modules():
    for relative in ("30_simulation/common", "30_simulation/sim_05_free_floating_arm", "30_simulation/sim_11_coupled_dynamics/src"):
        absolute = str(project_path(relative))
        if absolute not in sys.path:
            sys.path.insert(0, absolute)
    config_loader = importlib.import_module("config_loader")
    coupled_dynamics = importlib.import_module("coupled_dynamics")
    return config_loader, coupled_dynamics


def load_arm_only_config(config_loader) -> dict[str, Any]:
    """Load only the legacy ARM-only subset, never target/contact metadata."""
    card_relative = "20_engineering/config/coupled_scene/coupled_model_v0.yaml"
    card = load_yaml(card_relative)
    refs = card["ssot_refs"]
    ft = load_yaml(refs["frame_tree"])["frames"]
    t_SM = np.asarray(ft["M"]["transform_S_M"]["translation_mm"], float) / 1000.0
    q_SM = np.asarray(ft["M"]["transform_S_M"]["rotation"]["quat_wxyz"], float)
    w, x, y, z = q_SM / np.linalg.norm(q_SM)
    R_SM = np.array([
        [1 - 2 * (y*y + z*z), 2 * (x*y - w*z), 2 * (x*z + w*y)],
        [2 * (x*y + w*z), 1 - 2 * (x*x + z*z), 2 * (y*z - w*x)],
        [2 * (x*z - w*y), 2 * (y*z + w*x), 1 - 2 * (x*x + y*y)],
    ])
    if np.max(np.abs(t_SM - config_loader.b601_model.T_SM_t)) >= 1e-12 or np.max(np.abs(R_SM - config_loader.b601_model.R_SM)) >= 1e-7:
        raise RuntimeError("legacy M_DYNAMICS adapter drift")
    panels_frames = {}
    for side, key in (("L", "F_L"), ("R", "F_R")):
        frame = ft[key]
        panels_frames[side] = {
            "root_S": np.asarray(frame["origin_mm"], float) / 1000.0,
            "deploy_S": config_loader.parse_axis_token(frame["axes"]["Y_F"]),
            "normal_S": config_loader.parse_axis_token(frame["axes"]["Z_F"]),
        }
    fa = load_yaml(refs["flexible_appendage"])
    panel = {
        "span_L_m": float(fa["geometry"]["span_L_m"]),
        "chord_b_m": float(fa["geometry"]["chord_b_m"]),
        "thickness_t_m": float(fa["geometry"]["thickness_t_m"]),
        "m_panel_kg": float(fa["mass"]["m_panel_kg"]),
        "mu_kg_per_m": float(fa["mass"]["mu_kg_per_m"]),
        "I_own_com_kgm2": {key: float(value) for key, value in fa["mass"]["I_own_com_kgm2"].items()},
        "EI_cases_Nm2": {key: float(value["EI_Nm2"]) for key, value in fa["stiffness"]["cases"].items()},
        "beta1_ssot": float(fa["stiffness"]["beta1"]),
    }
    csv_path = str(project_path(refs["mass_budget_csv"]))
    bus = config_loader.load_object(refs["bus_object_id"], csv_path)
    whole = config_loader.load_object(refs["whole_sat_object_id"], csv_path)
    adapter = config_loader.load_object(refs["adapter_object_id"], csv_path)
    closure = abs(float(bus["mass"]) + 2.0 * panel["m_panel_kg"] - float(whole["mass"]))
    if closure >= 1e-9:
        raise RuntimeError(f"legacy mass split drift: {closure}")
    return {
        "card": card,
        "card_path": str(project_path(card_relative)),
        "repo": str(PROJECT_ROOT),
        "t_SM": t_SM,
        "R_SM": R_SM,
        "panels_frames": panels_frames,
        "panel": panel,
        "bus": bus,
        "whole_sat": whole,
        "adapter": adapter,
        "mass_budget_csv": csv_path,
        "panel_cfg": card["panels"],
        "integrator": card["integrator"],
        "provisional": bool(card["panels"].get("provisional", False)),
        "provisional_fields": list(card["panels"].get("provisional_fields", [])),
        "target_capture_metadata_read": False,
    }


def construct_model(config_loader, coupled_dynamics, *, target_service_mass_kg: float, n_modes: int, zeta: float, rigid_panels: bool):
    cfg = copy.deepcopy(load_arm_only_config(config_loader))
    urdf = str(project_path("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"))
    original_arm_factory = coupled_dynamics.B601Arm
    coupled_dynamics.B601Arm = lambda: original_arm_factory(urdf)
    try:
        baseline = coupled_dynamics.CoupledModel(cfg=copy.deepcopy(cfg), n_modes=n_modes, zeta=zeta, rigid_panels=rigid_panels)
        q_ref = np.zeros(6)
        arm_link_mass = math.fsum(float(body["mass"]) for body in baseline.arm.link_com_states(q_ref))
        arm_base_mass = float(baseline.arm.base_link_inertial_in_S()[0])
        panel_mass_total = math.fsum(float(panel.m_nodes.sum()) for panel in baseline.panels)
        adapter_mass = float(cfg["adapter"]["mass"])
        non_bus_mass = math.fsum([arm_link_mass, arm_base_mass, panel_mass_total, adapter_mass])
        original_bus_mass = float(cfg["bus"]["mass"])
        surrogate_bus_mass = target_service_mass_kg - non_bus_mass
        scale = surrogate_bus_mass / original_bus_mass
        original_bus_cg = np.asarray(cfg["bus"]["cg"], float).copy()
        original_bus_I = np.asarray(cfg["bus"]["I"], float).copy()
        cfg["bus"] = copy.deepcopy(cfg["bus"])
        cfg["bus"]["mass"] = float(surrogate_bus_mass)
        cfg["bus"]["cg"] = original_bus_cg.copy()
        cfg["bus"]["I"] = original_bus_I * scale
        model = coupled_dynamics.CoupledModel(cfg=cfg, n_modes=n_modes, zeta=zeta, rigid_panels=rigid_panels)
    finally:
        coupled_dynamics.B601Arm = original_arm_factory
    meta = {
        "target_service_mass_kg": float(target_service_mass_kg),
        "sim11_original_bus_mass_kg": original_bus_mass,
        "surrogate_bus_mass_kg": float(surrogate_bus_mass),
        "bus_mass_scale": float(scale),
        "non_bus_mass_kg": float(non_bus_mass),
        "adapter_mass_kg": adapter_mass,
        "arm_base_mass_kg": arm_base_mass,
        "arm_moving_links_mass_kg": arm_link_mass,
        "legacy_panel_mass_total_kg": panel_mass_total,
        "bus_cg_unchanged": bool(np.array_equal(np.asarray(cfg["bus"]["cg"]), original_bus_cg)),
        "bus_inertia_linear_scale_max_abs_error_kg_m2": float(np.max(np.abs(np.asarray(cfg["bus"]["I"]) - original_bus_I * scale))),
        "scalar_mass_closure_error_kg": float(abs(math.fsum([surrogate_bus_mass, non_bus_mass]) - target_service_mass_kg)),
        "surrogate_bus_inertia_kg_m2": np.asarray(cfg["bus"]["I"], float).tolist(),
        "surrogate_bus_inertia_min_eigenvalue_kg_m2": float(np.linalg.eigvalsh(np.asarray(cfg["bus"]["I"], float)).min()),
    }
    return model, meta


def summarize_run(res: dict[str, Any], model, mass_meta: dict[str, Any]) -> dict[str, Any]:
    t = res["t"]
    dh = res["h_I"] - res["h_I"][0]
    audit = np.abs(res["W_joint"] - (res["E"] - res["E"][0]) - res["E_damp"])
    scale = max(float(np.max(np.abs(res["W_joint"]))), float(np.max(np.abs(res["E"]))), 1.0e-300)
    m = model.n_modes
    modal_E = np.zeros(len(t))
    if m:
        for i in range(len(t)):
            modal_E[i] = (
                model.panels[0].modal_energy(res["eta"][i, :m], res["etad"][i, :m])
                + model.panels[1].modal_energy(res["eta"][i, m:], res["etad"][i, m:])
            )
    return {
        "peak_base_attitude_deviation_deg": float(np.max(res["dev_angle_deg"])),
        "final_base_attitude_deviation_deg": float(res["dev_angle_deg"][-1]),
        "peak_base_rate_rad_s": float(np.max(np.linalg.norm(res["Vb"][:, 3:6], axis=1))),
        "max_base_origin_shift_m": float(np.max(np.linalg.norm(res["r"], axis=1))),
        "final_base_position_m": [float(v) for v in res["r"][-1]],
        "tip_L_peak_mm": float(np.max(np.abs(res["tip_L_m"])) * 1.0e3),
        "tip_R_peak_mm": float(np.max(np.abs(res["tip_R_m"])) * 1.0e3),
        "panel_modal_energy_peak_J": float(np.max(modal_E)),
        "panel_modal_energy_final_J": float(modal_E[-1]),
        "momentum_max_norm_dP": float(np.max(np.linalg.norm(dh[:, :3], axis=1))),
        "momentum_max_norm_dL": float(np.max(np.linalg.norm(dh[:, 3:], axis=1))),
        "energy_audit_relative": float(np.max(audit) / scale),
        "quaternion_norm_max_error": float(np.max(np.abs(np.linalg.norm(res["Q"], axis=1) - 1.0))),
        "joint_work_final_J": float(res["W_joint"][-1]),
        "damping_energy_final_J": float(res["E_damp"][-1]),
        "nfev": int(res["nfev"]),
        "mass_closure_error_kg": mass_meta["scalar_mass_closure_error_kg"],
    }


def history_bytes(res: dict[str, Any], lane_id: str) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    m2 = res["eta"].shape[1]
    writer.writerow([
        "lane_id", "sample_index", "t_s", "base_x_m", "base_y_m", "base_z_m",
        "quat_w", "quat_x", "quat_y", "quat_z", "base_wx_rad_s", "base_wy_rad_s", "base_wz_rad_s",
        "base_dev_deg", "tip_L_mm", "tip_R_mm", "energy_J", "joint_work_J", "damping_energy_J",
        "momentum_dP_norm", "momentum_dL_norm", *[f"eta_{i+1}" for i in range(m2)],
    ])
    dh = res["h_I"] - res["h_I"][0]
    for i, t in enumerate(res["t"]):
        writer.writerow([
            lane_id, i, f"{t:.12e}",
            *(f"{v:.16e}" for v in res["r"][i]),
            *(f"{v:.16e}" for v in res["Q"][i]),
            *(f"{v:.16e}" for v in res["Vb"][i, 3:6]),
            f"{res['dev_angle_deg'][i]:.16e}", f"{res['tip_L_m'][i]*1e3:.16e}", f"{res['tip_R_m'][i]*1e3:.16e}",
            f"{res['E'][i]:.16e}", f"{res['W_joint'][i]:.16e}", f"{res['E_damp'][i]:.16e}",
            f"{np.linalg.norm(dh[i,:3]):.16e}", f"{np.linalg.norm(dh[i,3:]):.16e}",
            *(f"{v:.16e}" for v in res["eta"][i]),
        ])
    return stream.getvalue().encode("utf-8")


def run_lane(config_loader, coupled_dynamics, branch_id: str, trajectory: dict[str, Any], *, n_modes: int = 3, zeta: float = 0.005, rigid_panels: bool = False, method: str = "Radau", t_end: float | None = None, n_out: int | None = None):
    target_mass = BRANCH_SERVICE_KG[branch_id]
    model, mass_meta = construct_model(config_loader, coupled_dynamics, target_service_mass_kg=target_mass, n_modes=n_modes, zeta=zeta, rigid_panels=rigid_panels)
    traj = coupled_dynamics.JointTrajectory(trajectory["q0"], trajectory["q1"], trajectory["duration"])
    horizon = trajectory["duration"] if t_end is None else float(t_end)
    count = TRAJECTORY_OUTPUT_COUNTS[trajectory["key"]] if n_out is None else int(n_out)
    res = model.integrate_reduced(traj, horizon, method=method, rtol=1.0e-8, atol=1.0e-10, n_out=count)
    metrics = summarize_run(res, model, mass_meta)
    eigs = []
    for time in (0.0, horizon / 2.0, horizon):
        q, _, _ = traj(time)
        eigs.append(float(np.linalg.eigvalsh(model.mass_matrix(q, np.zeros(2 * model.n_modes))).min()))
    metrics["mass_matrix_min_eigenvalue"] = float(min(eigs))
    return res, model, mass_meta, metrics


def metric_rel(a: float, b: float) -> float:
    return float(abs(a - b) / max(abs(a), abs(b), 1.0e-30))


def build_all() -> dict[str, bytes]:
    authority = load_yaml(f"{PREFIX}/00_authority/E20_AUTHORITY_CONTRACT_V1.yaml")
    campaign = load_yaml(f"{PREFIX}/config/E20_INDEPENDENT_MASS_BRANCH_COUPLED_CAMPAIGN_V1.yaml")
    if authority["next_stage_authorized"] or authority["release_credit"] or authority["gate"] != "HOLD":
        raise RuntimeError("authority must remain HOLD")
    input_manifest = build_input_manifest()
    outputs: dict[str, bytes] = {relative_result("E20_INPUT_MANIFEST_V1.json"): json_bytes(input_manifest)}

    trajectories = {key: read_trajectory(key) for key in TRAJECTORY_PATHS}
    config_loader, coupled_dynamics = load_sim11_modules()

    # Establish branch completion metadata once.  Each lane reconstructs its own
    # model independently; no model object or terminal state crosses a lane.
    mass_branches = []
    for branch_id in BRANCH_SERVICE_KG:
        model, meta = construct_model(config_loader, coupled_dynamics, target_service_mass_kg=BRANCH_SERVICE_KG[branch_id], n_modes=3, zeta=0.005, rigid_panels=False)
        mass_branches.append({
            "branch_id": branch_id,
            "diagnostic_composite_with_22kg_target_kg": BRANCH_COMPOSITE_KG[branch_id],
            "target_scenario_subtracted_algebraically_kg": 22.0,
            "service_scalar_branch_kg": BRANCH_SERVICE_KG[branch_id],
            "standard_uncertainty_kg": None,
            "selected": False,
            "released": False,
            **meta,
            "model_target_is_none": model.target is None,
        })
    mass_register = {
        "schema": "E20_MASS_BRANCH_COMPLETION_REGISTER_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_class": authority["authority_class"],
        "mass_completion_rule": "UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE",
        "bus_only_mass_and_inertia_scaled": True,
        "bus_geometry_and_cg_fixed": True,
        "branch_count": 2,
        "branches": mass_branches,
        "branch_delta_kg_not_uncertainty": BRANCH_SERVICE_KG["M4_DIAG_M3R_B"] - BRANCH_SERVICE_KG["M4_DIAG_LEGACY_A"],
        "branch_selection_performed": False,
        "branch_averaging_performed": False,
        "model_difference_is_measurement_uncertainty": False,
        "released_service_mass_kg": None,
        "released_service_cg_m": None,
        "released_service_inertia_kg_m2": None,
        "physical_bus_completion_authority": None,
        "branch_lifecycle": "LEGACY_TRANSITIONAL_SENSITIVITY_ONLY",
        "current_M7_design_mass_authority_consumed": False,
        "current_M7_design_mass_authority_superseded": False,
        "status": "PASS_TWO_INDEPENDENT_BUS_ONLY_SCALAR_SURROGATE_COMPLETIONS_NONRELEASE",
    }
    outputs[relative_result("E20_MASS_BRANCH_COMPLETION_REGISTER_V1.json")] = json_bytes(mass_register)

    lane_records = []
    lane_summaries: dict[str, dict[str, Any]] = {}
    for lane_id, branch_id, trajectory_key in LANE_ORDER:
        trajectory = trajectories[trajectory_key]
        res, model, mass_meta, metrics = run_lane(config_loader, coupled_dynamics, branch_id, trajectory)
        history_name = f"E20_{lane_id}_RADAU_HISTORY_V1.csv"
        history_blob = history_bytes(res, lane_id)
        history_relative = relative_result(history_name)
        outputs[history_relative] = history_blob
        summary = {
            "schema": "E20_COUPLED_ARM_ONLY_LANE_SUMMARY_V1",
            "generated_local": GENERATED_LOCAL,
            "lane_id": lane_id,
            "mass_branch_id": branch_id,
            "trajectory_id": trajectory_key,
            "authority_class": authority["authority_class"],
            "trajectory_source": {
                "path": trajectory["path"], "sha256": trajectory["sha256"],
                "q0_rad": trajectory["q0"].tolist(), "q1_rad": trajectory["q1"].tolist(),
                "duration_s": trajectory["duration"], "source_sample_count": trajectory["source_sample_count"],
                "reconstruction": trajectory["reconstruction"], "release_flags_all_false": trajectory["release_flags_all_false"],
                "jaw_travel_all_null": trajectory["jaw_travel_all_null"],
            },
            "surrogate_mass_completion": mass_meta,
            "solver": {
                "source": "SIM11_STOCK_LEGACY_FFR_WITH_SCOPED_REORG_ADAPTER",
                "mode": "reduced_momentum", "method": "Radau", "rtol": 1.0e-8, "atol": 1.0e-10,
                "n_modes_per_panel": 3, "zeta_modal": 0.005, "stiffness_case": "nominal",
                "PROVISIONAL_PARAMS": True, "current_R2_model_consumed": False,
                "mount_frame_model": "M_DYNAMICS_LEGACY_NUMERICAL",
                "physical_mount_frame_applied": False, "physical_mount_transform": None,
            },
            "initial_state": {"base_position_m": [0.0, 0.0, 0.0], "base_quaternion_wxyz": [1.0, 0.0, 0.0, 0.0], "panel_state_zero": True, "total_momentum_zero": True, "source_lane": None},
            "metrics": metrics,
            "history": {"path": history_relative, "sha256": sha256_bytes(history_blob), "bytes": len(history_blob), "sample_count": len(res["t"])},
            "cross_lane_state_input": None,
            "target_attached": model.target is not None,
            "scene_A2_invoked": False,
            "contact_window_invoked": False,
            "physical_contact_computed": False,
            "engineering_prediction": False,
            "released_for_mission_gate": False,
            "status": "PASS_INDEPENDENT_SURROGATE_COUPLED_ARM_ONLY_NUMERIC_LANE",
        }
        summary_name = f"E20_{lane_id}_RADAU_SUMMARY_V1.json"
        summary_relative = relative_result(summary_name)
        summary_blob = json_bytes(summary)
        outputs[summary_relative] = summary_blob
        lane_summaries[lane_id] = summary
        lane_records.append({"lane_id": lane_id, "summary": {"path": summary_relative, "sha256": sha256_bytes(summary_blob), "bytes": len(summary_blob)}, "history": summary["history"], "state_input_from_other_lane": None})

    # Bounded local numerical checks: independent fresh model instances.
    anchor = trajectories["M07_ARM_ONLY"]
    local_specs = (
        ("baseline_m3_radau", 3, 0.005, False, "Radau"),
        ("undamped_m3_radau", 3, 0.0, False, "Radau"),
        ("rigid_radau", 0, 0.005, True, "Radau"),
        ("m4_radau", 4, 0.005, False, "Radau"),
        ("m5_radau", 5, 0.005, False, "Radau"),
        ("m3_bdf", 3, 0.005, False, "BDF"),
    )
    variants: dict[str, dict[str, Any]] = {}
    for name, modes, zeta, rigid, method in local_specs:
        res, model, mass_meta, metrics = run_lane(config_loader, coupled_dynamics, "M4_DIAG_M3R_B", anchor, n_modes=modes, zeta=zeta, rigid_panels=rigid, method=method, t_end=1.5, n_out=31)
        variants[name] = {
            "variant": name, "method": method, "mode": "reduced_momentum", "horizon_s": 1.5,
            "n_modes_per_panel": modes, "zeta_modal": zeta, "rigid_panels": rigid,
            "metrics": metrics, "target_attached": model.target is not None,
            "scene_A2_invoked": False, "contact_window_invoked": False,
            "mass_closure_error_kg": mass_meta["scalar_mass_closure_error_kg"],
        }
    modal_observables = ("peak_base_attitude_deviation_deg", "tip_L_peak_mm", "tip_R_peak_mm", "panel_modal_energy_peak_J")
    m3_m4 = {key: metric_rel(variants["baseline_m3_radau"]["metrics"][key], variants["m4_radau"]["metrics"][key]) for key in modal_observables}
    m4_m5 = {key: metric_rel(variants["m4_radau"]["metrics"][key], variants["m5_radau"]["metrics"][key]) for key in modal_observables}
    cross_observables = ("peak_base_attitude_deviation_deg", "tip_L_peak_mm", "tip_R_peak_mm", "panel_modal_energy_peak_J", "joint_work_final_J")
    radau_bdf = {key: metric_rel(variants["baseline_m3_radau"]["metrics"][key], variants["m3_bdf"]["metrics"][key]) for key in cross_observables}
    local_register = {
        "schema": "E20_LOCAL_NUMERICAL_VERIFICATION_REGISTER_V1",
        "generated_local": GENERATED_LOCAL,
        "anchor_lane_id": "M3R_B__M07_ARM_ONLY",
        "scope": "FIRST_1P5S_LOCAL_NUMERICAL_CHECK_NOT_MISSION_ACCEPTANCE",
        "variants": [variants[name] for name, *_ in local_specs],
        "undamped_energy_audit_relative": variants["undamped_m3_radau"]["metrics"]["energy_audit_relative"],
        "rigid_degeneration": {
            "n_modes_per_panel": variants["rigid_radau"]["n_modes_per_panel"],
            "tip_L_peak_mm": variants["rigid_radau"]["metrics"]["tip_L_peak_mm"],
            "tip_R_peak_mm": variants["rigid_radau"]["metrics"]["tip_R_peak_mm"],
            "panel_modal_energy_peak_J": variants["rigid_radau"]["metrics"]["panel_modal_energy_peak_J"],
            "momentum_max_norm_dP": variants["rigid_radau"]["metrics"]["momentum_max_norm_dP"],
            "momentum_max_norm_dL": variants["rigid_radau"]["metrics"]["momentum_max_norm_dL"],
        },
        "modal_refinement_relative": {"m3_to_m4": m3_m4, "m4_to_m5": m4_m5, "gate_uses": "m4_to_m5", "limit": 0.01, "max_m4_to_m5": max(m4_m5.values())},
        "radau_vs_bdf_relative": {"observables": radau_bdf, "limit": 0.05, "maximum": max(radau_bdf.values())},
        "e15_certification_debt_cleared": False,
        "local_cross_solver_is_e15_replacement": False,
        "status": "PASS" if variants["undamped_m3_radau"]["metrics"]["energy_audit_relative"] <= 1.0e-8 and max(m4_m5.values()) < 0.01 and max(radau_bdf.values()) < 0.05 else "REPEAT_E20_LOCAL_NUMERICAL_DIAGNOSTIC",
    }
    outputs[relative_result("E20_LOCAL_NUMERICAL_VERIFICATION_REGISTER_V1.json")] = json_bytes(local_register)

    sensitivity = []
    for trajectory_key in ("M01", "M07_ARM_ONLY"):
        a = lane_summaries[f"LEGACY_A__{trajectory_key}"]["metrics"]
        b = lane_summaries[f"M3R_B__{trajectory_key}"]["metrics"]
        sensitivity.append({
            "trajectory_id": trajectory_key,
            "m3r_B_minus_legacy_A": {key: float(b[key] - a[key]) for key in ("peak_base_attitude_deviation_deg", "peak_base_rate_rad_s", "max_base_origin_shift_m", "tip_L_peak_mm", "tip_R_peak_mm", "panel_modal_energy_peak_J")},
            "difference_class": "SURROGATE_MODEL_SENSITIVITY_NOT_MEASUREMENT_UNCERTAINTY",
        })

    physical_unknowns = {
        "selected_mass_branch": None,
        "legacy_A_standard_uncertainty_kg": None,
        "m3r_B_standard_uncertainty_kg": None,
        "released_service_mass_kg": None,
        "released_service_cg_m": None,
        "released_service_inertia_kg_m2": None,
        "physical_bus_completion_authority": None,
        "measured_panel_mass_kg": None,
        "measured_panel_modes_hz": None,
        "measured_panel_EI_Nm2": None,
        "measured_panel_damping_ratio": None,
        "contact_duration_s": None,
        "contact_force_N": None,
        "contact_pressure_Pa": None,
        "contact_normal": None,
        "lock_state": None,
        "retention_state": None,
        "locked_transform_gripper_to_target": None,
        "post_capture_initial_state": None,
        "attached_recovery_terminal_state": None,
        "attached_recovery_tolerances": None,
        "mission_acceptance_thresholds": None,
        "hardware_torque_Nm": None,
        "hardware_current_A": None,
        "hardware_latency_s": None,
        "physical_mount_transform": None,
    }
    coupled_register = {
        "schema": "E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_REGISTER_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_class": authority["authority_class"],
        "input_manifest": {"path": relative_result("E20_INPUT_MANIFEST_V1.json"), "sha256": sha256_bytes(outputs[relative_result("E20_INPUT_MANIFEST_V1.json")])},
        "mass_completion_register": {"path": relative_result("E20_MASS_BRANCH_COMPLETION_REGISTER_V1.json"), "sha256": sha256_bytes(outputs[relative_result("E20_MASS_BRANCH_COMPLETION_REGISTER_V1.json")])},
        "local_verification_register": {"path": relative_result("E20_LOCAL_NUMERICAL_VERIFICATION_REGISTER_V1.json"), "sha256": sha256_bytes(outputs[relative_result("E20_LOCAL_NUMERICAL_VERIFICATION_REGISTER_V1.json")])},
        "lane_count": 4,
        "lanes": lane_records,
        "lane_initial_states_independent": True,
        "cross_lane_chaining_performed": False,
        "state_transfer_between_lanes_performed": False,
        "branch_selection_performed": False,
        "branch_averaging_performed": False,
        "branch_merging_performed": False,
        "branch_sensitivity": sensitivity,
        "target_subtraction_is_algebra_only": True,
        "attached_target_propagated": False,
        "scene_A2_invoked": False,
        "contact_window_invoked": False,
        "lockup_invoked": False,
        "mount_frame_boundary": {
            "mount_frame_model": "M_DYNAMICS_LEGACY_NUMERICAL",
            "numerical_translation_m": [0.18525, 0.0, 0.0],
            "numerical_rotation": "Ry(+90deg)",
            "physical_entity": False,
            "current_M7_unique_dynamics_M_consumed": False,
            "current_M7_design_dynamics_closure_claimed": False,
            "geometric_feature_stack_id": "B601_ARM_BASE_PHYSICAL",
            "geometric_feature_stack_x_mm": 208.0,
            "geometric_feature_stack_clock_deg": 25.000014,
            "geometric_feature_stack_is_dynamics_M_alias": False,
            "physical_mount_frame_applied": False,
            "physical_mount_transform": None,
            "m4_digital_prototype_installation_dynamics_claimed": False,
        },
        "legacy_stock_sim11_model_used": True,
        "current_R2_coupled_model_used": False,
        "current_R2_flexible_appendage_used": False,
        "legacy_M4_mass_branches_used_as_transitional_sensitivity_only": True,
        "current_M7_design_mass_v2_consumed": False,
        "current_M7_design_mass_v2_superseded": False,
        "physical_unknowns": physical_unknowns,
        "cad_or_mesh_generated": False,
        "accepted_urdf_modified": False,
        "historical_gate_modified": False,
        "physical_contact_ready": False,
        "attached_target_recovery_ready": False,
        "mission_sequence_executable": False,
        "mission_release_ready": False,
        "production_dynamics_ready": False,
        "mechanical_design_released": False,
        "hardware_motion_ready": False,
        "flight_qualification_ready": False,
        "released_segments": 0,
        "release_credit": False,
    }
    register_relative = relative_result("E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_REGISTER_V1.json")
    outputs[register_relative] = json_bytes(coupled_register)

    limits = campaign["gates"]
    all_main = list(lane_summaries.values())
    criteria_raw = [
        ("E20-G01", "all frozen source hashes exact", input_manifest["all_exact_hash_match"]),
        ("E20-G02", "sim11 historical verdict preserved with explicit 32/26 REORG byte audit", input_manifest["sim11_historical_artifact_audit"]["historical_gate_verdict_preserved"] and not input_manifest["sim11_historical_artifact_audit"]["current_artifact_manifest_bytewise_complete"] and input_manifest["sim11_historical_artifact_audit"]["reorg_route_only_semantic_diff"] and input_manifest["sim11_historical_artifact_audit"]["current_bytewise_match_count"] == 32 and input_manifest["sim11_historical_artifact_audit"]["current_bytewise_mismatch_count"] == 26),
        ("E20-G03", "sim11 provisional parameters retained and current R2 not claimed", input_manifest["sim11_provisional_boundary"]["PROVISIONAL_PARAMS"] and not input_manifest["sim11_provisional_boundary"]["current_R2_flexible_appendage_consumed"] and not coupled_register["current_R2_coupled_model_used"]),
        ("E20-G03B", "legacy M4 branches remain transitional and do not replace M7 design mass", input_manifest["mass_authority_boundary"]["legacy_M4_A_B_branch_lifecycle"] == "TRANSITIONAL_SURROGATE_SENSITIVITY_ONLY" and not input_manifest["mass_authority_boundary"]["current_M7_design_mass_v2_consumed_by_solver"] and not coupled_register["current_M7_design_mass_v2_consumed"] and not coupled_register["current_M7_design_mass_v2_superseded"]),
        ("E20-G04", "e15 REPEAT debt preserved", input_manifest["e15_certification_debt"]["ancf_certification_status"] == "REPEAT_ANCF_CERTIFICATION" and input_manifest["e15_certification_debt"]["e15_cross_solver_max_relative_difference"] > input_manifest["e15_certification_debt"]["e15_gate_limit"] and not input_manifest["e15_certification_debt"]["e15_final_candidate_available"]),
        ("E20-G05", "two C08 diagnostic composites subtract exactly 22 kg without selection", all(abs(row["diagnostic_composite_with_22kg_target_kg"] - 22.0 - row["service_scalar_branch_kg"]) <= limits["mass_closure_limit_kg"] for row in mass_branches) and not mass_register["branch_selection_performed"]),
        ("E20-G06", "bus-only scalar completion closes both masses", all(row["scalar_mass_closure_error_kg"] <= limits["mass_closure_limit_kg"] and row["bus_cg_unchanged"] and row["bus_inertia_linear_scale_max_abs_error_kg_m2"] == 0.0 for row in mass_branches)),
        ("E20-G07", "surrogate bus inertias are positive definite", all(row["surrogate_bus_inertia_min_eigenvalue_kg_m2"] > 0.0 for row in mass_branches)),
        ("E20-G08", "four exact independent branch-trajectory lanes executed", coupled_register["lane_count"] == 4 and len({row["lane_id"] for row in lane_records}) == 4 and all(row["state_input_from_other_lane"] is None for row in lane_records)),
        ("E20-G09", "M01 and M07 quintics reconstructed and remain unreleased", all(max(summary["trajectory_source"]["reconstruction"].values()) <= limits["trajectory_reconstruction_limit"] and summary["trajectory_source"]["release_flags_all_false"] for summary in all_main)),
        ("E20-G10", "all main lanes use reduced Radau legacy sim11 only", all(summary["solver"]["mode"] == "reduced_momentum" and summary["solver"]["method"] == "Radau" and summary["solver"]["n_modes_per_panel"] == 3 and not summary["solver"]["current_R2_model_consumed"] for summary in all_main)),
        ("E20-G11", "reduced momentum closes in all main lanes", all(max(summary["metrics"]["momentum_max_norm_dP"], summary["metrics"]["momentum_max_norm_dL"]) <= limits["reduced_momentum_residual_limit"] for summary in all_main)),
        ("E20-G12", "energy audit closes in all main lanes", all(summary["metrics"]["energy_audit_relative"] <= limits["energy_audit_relative_limit"] for summary in all_main)),
        ("E20-G13", "quaternion normalization closes in all main lanes", all(summary["metrics"]["quaternion_norm_max_error"] <= limits["quaternion_norm_error_limit"] for summary in all_main)),
        ("E20-G14", "all sampled generalized mass matrices are SPD", all(summary["metrics"]["mass_matrix_min_eigenvalue"] > 0.0 for summary in all_main)),
        ("E20-G15", "undamped local energy audit closes", local_register["undamped_energy_audit_relative"] <= limits["undamped_energy_audit_relative_limit"]),
        ("E20-G16", "rigid local degeneration has zero modal response and closes momentum", local_register["rigid_degeneration"]["n_modes_per_panel"] == 0 and local_register["rigid_degeneration"]["tip_L_peak_mm"] == 0.0 and local_register["rigid_degeneration"]["tip_R_peak_mm"] == 0.0 and local_register["rigid_degeneration"]["panel_modal_energy_peak_J"] == 0.0 and max(local_register["rigid_degeneration"]["momentum_max_norm_dP"], local_register["rigid_degeneration"]["momentum_max_norm_dL"]) <= limits["reduced_momentum_residual_limit"]),
        ("E20-G17", "local m4 to m5 modal refinement closes", local_register["modal_refinement_relative"]["max_m4_to_m5"] < limits["modal_m4_to_m5_relative_limit"]),
        ("E20-G18", "local Radau BDF agreement closes without clearing e15", local_register["radau_vs_bdf_relative"]["maximum"] < limits["radau_bdf_relative_limit"] and not local_register["e15_certification_debt_cleared"] and not local_register["local_cross_solver_is_e15_replacement"]),
        ("E20-G19", "no A2 contact target lock or cross-lane state transfer", not coupled_register["scene_A2_invoked"] and not coupled_register["contact_window_invoked"] and not coupled_register["attached_target_propagated"] and not coupled_register["lockup_invoked"] and not coupled_register["cross_lane_chaining_performed"]),
        ("E20-G20", "branch differences remain sensitivity not uncertainty", all(row["difference_class"] == "SURROGATE_MODEL_SENSITIVITY_NOT_MEASUREMENT_UNCERTAINTY" for row in sensitivity) and not mass_register["model_difference_is_measurement_uncertainty"] and not coupled_register["branch_averaging_performed"]),
        ("E20-G21", "M_DYNAMICS legacy numerical frame is not physical mount", coupled_register["mount_frame_boundary"]["mount_frame_model"] == "M_DYNAMICS_LEGACY_NUMERICAL" and not coupled_register["mount_frame_boundary"]["physical_mount_frame_applied"] and coupled_register["mount_frame_boundary"]["physical_mount_transform"] is None and not coupled_register["mount_frame_boundary"]["m4_digital_prototype_installation_dynamics_claimed"]),
        ("E20-G22", "all physical UNKNOWN fields remain null", all(value is None for value in physical_unknowns.values())),
        ("E20-G23", "accepted URDF and Solar R2 immutable", input_manifest["accepted_urdf_sha256"] == ACCEPTED_URDF_SHA256 and input_manifest["solar_r2_sha256"] == SOLAR_R2_SHA256 and not coupled_register["accepted_urdf_modified"]),
        ("E20-G24", "all physical mission production hardware and flight claims fail closed", not any(coupled_register[key] for key in ("physical_contact_ready", "attached_target_recovery_ready", "mission_sequence_executable", "mission_release_ready", "production_dynamics_ready", "mechanical_design_released", "hardware_motion_ready", "flight_qualification_ready")) and coupled_register["released_segments"] == 0 and not coupled_register["release_credit"]),
    ]
    criteria = [{"id": cid, "name": name, "state": "PASS_DIAGNOSTIC_ONLY" if observed else "FAIL", "observed": bool(observed), "release_credit": False} for cid, name, observed in criteria_raw]
    closed = all(item["observed"] for item in criteria)
    gate = {
        "schema": "E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_GATE_V1",
        "generated_local": GENERATED_LOCAL,
        "authority_scope": "INDEPENDENT_NONRELEASE_SURROGATE_MASS_BRANCH_SIM11_COUPLED_ARM_ONLY_DIAGNOSTIC_ONLY",
        "input_manifest": {"path": relative_result("E20_INPUT_MANIFEST_V1.json"), "sha256": sha256_bytes(outputs[relative_result("E20_INPUT_MANIFEST_V1.json")])},
        "result_register": {"path": register_relative, "sha256": sha256_bytes(outputs[register_relative])},
        "criteria": criteria,
        "criteria_total": len(criteria),
        "criteria_observed": sum(item["observed"] for item in criteria),
        "diagnostic_execution_verdict": "PASS" if closed else "REPEAT_E20_SURROGATE_MASS_BRANCH_COUPLED_DIAGNOSTIC",
        "independent_surrogate_mass_branch_sim11_coupled_arm_only_diagnostic_execution_closed": closed,
        "local_numerical_reproducibility_closed": closed,
        "mass_completion_rule": "UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE",
        "bus_only_mass_and_inertia_scaled": True,
        "mount_frame_model": "M_DYNAMICS_LEGACY_NUMERICAL",
        "physical_mount_frame_applied": False,
        "physical_mount_transform": None,
        "m4_digital_prototype_installation_dynamics_claimed": False,
        "current_M7_unique_dynamics_M_consumed": False,
        "current_M7_design_dynamics_closure_claimed": False,
        "historical_gate_verdict_preserved": True,
        "current_artifact_manifest_bytewise_complete": False,
        "reorg_route_only_semantic_diff": True,
        "ancf_certification_status": "REPEAT_ANCF_CERTIFICATION",
        "e15_cross_solver_max_relative_difference": 0.05637349419858036,
        "e15_gate_limit": 0.05,
        "e15_final_candidate_available": False,
        "ancf_certified": False,
        "flexible_safety_ready": False,
        "legacy_stock_sim11_model_used": True,
        "current_R2_coupled_model_used": False,
        "legacy_M4_mass_branches_used_as_transitional_sensitivity_only": True,
        "current_M7_design_mass_v2_consumed": False,
        "current_M7_design_mass_v2_superseded": False,
        "scene_A2_invoked": False,
        "contact_window_invoked": False,
        "attached_target_propagated": False,
        "selected_mass_branch": None,
        "released_service_mass_kg": None,
        "released_service_cg_m": None,
        "released_service_inertia_kg_m2": None,
        "end_to_end_diagnostic_dynamics_ready": False,
        "physical_contact_ready": False,
        "attached_target_recovery_ready": False,
        "mission_release_ready": False,
        "production_dynamics_ready": False,
        "mechanical_design_released": False,
        "hardware_motion_ready": False,
        "flight_qualification_ready": False,
        "released_segments": 0,
        "testing_pass_grants_authority": False,
        "gate": "HOLD",
        "verdict": "E20_INDEPENDENT_SURROGATE_MASS_BRANCH_SIM11_COUPLED_ARM_ONLY_DIAGNOSTICS_CLOSED__E15_ANCF_PROVISIONAL_PANEL_CONTACT_ATTACHED_RECOVERY_CAD_MISSION_PRODUCTION_AND_FLIGHT_HOLD" if closed else "REPEAT_E20_SURROGATE_MASS_BRANCH_COUPLED_DIAGNOSTIC__ALL_RELEASE_GATES_HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
        "allowed_next": [
            "bind this isolated surrogate sensitivity closure into Loop V4 without physical or release credit",
            "replace legacy stock sim11 panels and M_DYNAMICS only under a separately preregistered current-R2 coupled model",
            "repeat e15 ANCF certification and obtain measured panel contact mount and mass-property authority",
        ],
        "prohibited_next": [
            "promote local BDF agreement to e15 certification",
            "attach a target invoke A2 or create contact lock recovery dynamics",
            "select or average the two mass branches or call their difference uncertainty",
            "claim M4 digital-prototype installation dynamics from M_DYNAMICS",
            "claim CAD production mission hardware mechanical release or flight readiness",
        ],
    }
    gate_relative = relative_result("E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_GATE_V1.json")
    outputs[gate_relative] = json_bytes(gate)

    controlled_records = [artifact_record(path) for path in STATIC_ARTIFACTS]
    for relative, blob in outputs.items():
        controlled_records.append(artifact_record(relative, blob))
    output_manifest = {
        "schema": "E20_OUTPUT_MANIFEST_V1",
        "generated_local": GENERATED_LOCAL,
        "scope": "CONTROLLED_E20_CODE_CONTRACTS_AND_RESULTS__VALIDATION_AND_MANIFEST_SELF_EXCLUDED",
        "artifacts": controlled_records,
        "artifact_count": len(controlled_records),
        "artifact_set_sha256": sha256_bytes(canonical_json_bytes(controlled_records)),
        "input_source_set_sha256": input_manifest["source_set_sha256"],
        "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
        "solar_r2_sha256": SOLAR_R2_SHA256,
        "validation_report_excluded": True,
        "manifest_self_excluded": True,
        "gate": "HOLD",
        "released_segments": 0,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    outputs[relative_result("E20_OUTPUT_MANIFEST_V1.json")] = json_bytes(output_manifest)
    return outputs


def refresh_manifest_only() -> dict[str, Any]:
    """Refresh only the non-recursive manifest after static validator edits."""
    old = json.loads((RESULTS_ROOT / "E20_OUTPUT_MANIFEST_V1.json").read_text(encoding="utf-8"))
    input_manifest = json.loads((RESULTS_ROOT / "E20_INPUT_MANIFEST_V1.json").read_text(encoding="utf-8"))
    static_set = set(STATIC_ARTIFACTS)
    controlled = [artifact_record(path) for path in STATIC_ARTIFACTS]
    for row in old["artifacts"]:
        if row["path"] not in static_set:
            controlled.append(artifact_record(row["path"]))
    refreshed = {
        "schema": "E20_OUTPUT_MANIFEST_V1",
        "generated_local": GENERATED_LOCAL,
        "scope": "CONTROLLED_E20_CODE_CONTRACTS_AND_RESULTS__VALIDATION_AND_MANIFEST_SELF_EXCLUDED",
        "artifacts": controlled,
        "artifact_count": len(controlled),
        "artifact_set_sha256": sha256_bytes(canonical_json_bytes(controlled)),
        "input_source_set_sha256": input_manifest["source_set_sha256"],
        "accepted_urdf_sha256": ACCEPTED_URDF_SHA256,
        "solar_r2_sha256": SOLAR_R2_SHA256,
        "validation_report_excluded": True,
        "manifest_self_excluded": True,
        "gate": "HOLD",
        "released_segments": 0,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    (RESULTS_ROOT / "E20_OUTPUT_MANIFEST_V1.json").write_bytes(json_bytes(refreshed))
    return refreshed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true", help="recompute in memory and require exact byte equality")
    parser.add_argument("--refresh-manifest-only", action="store_true", help="refresh static/result hashes without rerunning dynamics")
    args = parser.parse_args()
    if args.refresh_manifest_only:
        refreshed = refresh_manifest_only()
        print(json.dumps({"schema": refreshed["schema"], "status": "PASS_MANIFEST_REFRESH_ONLY", "artifact_count": refreshed["artifact_count"]}, indent=2))
        return 0
    outputs = build_all()
    if args.check_only:
        failures = []
        for relative, expected in outputs.items():
            path = project_path(relative)
            if not path.exists():
                failures.append(f"missing:{relative}")
            elif path.read_bytes() != expected:
                failures.append(f"byte_drift:{relative}")
        if failures:
            raise RuntimeError("check-only failed: " + ", ".join(failures))
        print(json.dumps({"schema": "E20_CHECK_ONLY_V1", "status": "PASS_EXACT_REPRODUCTION", "artifact_count": len(outputs)}, indent=2))
        return 0
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    for relative, blob in outputs.items():
        path = project_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    gate = json.loads(outputs[relative_result("E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_GATE_V1.json")])
    print(json.dumps({
        "schema": gate["schema"],
        "diagnostic_execution_verdict": gate["diagnostic_execution_verdict"],
        "criteria": f"{gate['criteria_observed']}/{gate['criteria_total']}",
        "gate": gate["gate"],
        "next_stage_authorized": gate["next_stage_authorized"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
