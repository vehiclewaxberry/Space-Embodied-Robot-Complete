from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[3]
TZ = timezone(timedelta(hours=8))


SOURCES: dict[str, dict[str, Any]] = {
    "owner_attachment": {
        "path": Path(r"C:\Users\stude\.codex\attachments\097124c4-bbc4-4459-85c4-748019414866\pasted-text.txt"),
        "sha256": "67821E04869BE8202CF2473980B73AA4CE595B9689CC9D54F340820C0D38F773",
    },
    "owner_odr_gpt_01_06": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR_GPT_01_TO_06_TERMINAL_CLOSURE_V1.yaml"),
        "sha256": "B7EE60281935DD7417027D5428B9291BEE7D3F6528022509ACA168FB39B68689",
    },
    "owner_odr_35_41": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR35_TO_ODR41_B601_HARNESS_RATED_ENVELOPE_V1.yaml"),
        "sha256": "7655FA44BA4CD2B0369184100A18DF1001B8C40CC6B4D9731D4E4ACEE9D6433E",
    },
    "route_b_terminal_freeze": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/00_authority/ROUTE_B_NEGATIVE_RESULT_TERMINAL_FREEZE_V1.yaml"),
        "sha256": "74EADB7A239C3A88B99C89999E49036EB3033654CE8D988A0D2F007F020DFA61",
    },
    "route_b_frozen_pins": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/00_authority/ROUTE_B_FROZEN_INPUT_PINS_V1.yaml"),
        "sha256": "6BB8E9C5FF6910BE07D1720D320C4CB560A2CF07AD254DEB83E931AF4731C588",
    },
    "route_b_product_definition": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/01_product_definition/B601_HARNESS_ROUTING_PRODUCT_DEFINITION_V1.yaml"),
        "sha256": "4294D08E246A99DB37A47A38B432B7DC2324436ED96FB2F0B771D4B08EA4BA9E",
    },
    "exact_predicate_contract": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/02_exact_predicate/B601_HARNESS_EXACT_PREDICATE_CONTRACT_V1.yaml"),
        "sha256": "FB21D09602F6CDCF7CF21E60615FDEE9C795DFA29D11609B4FBE237789C5C295",
    },
    "exact_predicate_wrapper": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/02_exact_predicate/harness_exact_check.py"),
        "sha256": "327F6C907A1F9281071E74BA931C3A42C36AA1782897CCC3D6972B66E1129C28",
    },
    "mission_probe_source": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/99_tools/probe_current_route_mission_states.py"),
        "sha256": "607ADF4A5C7EEB41D1418E9FF59FC5C4F5B679CCEEA587CFE7BE5B470611E75F",
    },
    "route_b_geometry_kernel": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/sweep_b601_harness_full_fk.py"),
        "sha256": "F99FF775B20940D4F5338E2AECA6F9C03D565FF718170B92B6C97CBDEB499261",
    },
    "full_fk_negative_result": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/HARNESS_B601_FULL_FK_SWEEP_V2.json"),
        "sha256": "DB86348B8276FB2DCEB48DA30D1969948B37AAC4DF6D67D7588D928CF8281FAE",
    },
    "mandatory_state_probe": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/02_exact_predicate/CURRENT_ROUTE_KEY_STATE_PROBE_V1.json"),
        "sha256": "96FCBDA104ADDD3194ED3EDAA5A3CFD8E230ACCA8D4608BE18A4258636EADD70",
    },
    "rated_envelope": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/03_envelope/B601_HARNESS_RATED_ENVELOPE_V1.yaml"),
        "sha256": "A63A93DE5B6B3BEE37819379757ABE5B9F7FC457641F852E06676B686BC416C6",
    },
    "envelope_map_csv": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/03_envelope/B601_HARNESS_ENVELOPE_MAP_V1.csv"),
        "sha256": "0159FB6D525D7390E5929839610E30F4E94DA112CC3F49314369BD17EA2D6EF7",
    },
    "envelope_map_npz": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/03_envelope/B601_HARNESS_ENVELOPE_MAP_V1.npz"),
        "sha256": "21CB19FE3281090A834CCFA672C0E7CC8D1EEFCC7D55F11CB4A9E09E3E3B392B",
    },
    "mission_pose_rebind": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_MISSION_POSE_AUTHORITY_REBIND_V1.yaml"),
        "sha256": "2954AA16DE68CE6550C0A281DD309BF14585970087EBE35663485E0E932AA62A",
    },
    "mission_trajectory_contract": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml"),
        "sha256": "C06A40DE171F0517ACB34CCC14C918A9A4252F7B55A425B2CBAC95229B44A98A",
    },
    "mission_coverage_gate": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json"),
        "sha256": "F3B444222E87509B66F712E623A4903748C7309C6396708EC02A0C1A54CDAA5C",
    },
    "harness_terminal_gate": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/07_release/B601_HARNESS_TERMINAL_GATE_V1.json"),
        "sha256": "D65BD945B3F0C93041BFD10CFABCD9E423596B3FC19400C45FA58CB08DE96AF4",
    },
    "handoff_gate_v2": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json"),
        "sha256": "13722965D5C558D3439A7CB1E77ABBF3C2094B88E9D62F80D664D0C4C90D4E21",
    },
    "checkpoint_b": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/checkpoint_b/ROUTE_C_CHECKPOINT_B_GATE_V1.json"),
        "sha256": "C9E7526D790E1FB7F5522A113EDF41F5913207C15A68E12468FD9EBA157349D1",
    },
    "route_c_admission": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_C2_ADMISSION_GATE_V1.yaml"),
        "sha256": "0AE3888EDBE9A2DCD85792AA0E8800432911E4ED1C11D48C2206B60BED2521B8",
    },
    "route_c_registry": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_C2_01_REGISTRY_SKELETON_V1.yaml"),
        "sha256": "6264A0A45F6A497787F3D96205CEF7799A19A225CD23CEA66D5AD31E335A3E8E",
    },
    "route_c_rfi": {
        "path": Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_RFI_EFG_ISSUANCE_V1.yaml"),
        "sha256": "77187CF362A9AA41B287A269D4AA827BA8B8A8385576DB0FD003E4BBE63EC1A2",
    },
}

EXPECTED_SEGMENTS = {"M01", "M02", "M03", "M04", "M05_22", "M06_22", "M07_22", "M05_150"}


def locate(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def label(path: Path) -> str:
    full = locate(path)
    try:
        return full.relative_to(ROOT).as_posix()
    except ValueError:
        return str(full)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(source_id: str) -> dict[str, Any]:
    return json.loads(locate(SOURCES[source_id]["path"]).read_text(encoding="utf-8"))


def load_yaml(source_id: str) -> dict[str, Any]:
    return yaml.safe_load(locate(SOURCES[source_id]["path"]).read_text(encoding="utf-8"))


def pin_sources() -> dict[str, dict[str, Any]]:
    pins: dict[str, dict[str, Any]] = {}
    for source_id, item in SOURCES.items():
        path = locate(item["path"])
        require(path.is_file(), f"missing source: {path}")
        actual = sha256(path)
        require(actual == item["sha256"], f"source hash drift: {source_id}")
        pins[source_id] = {
            "id": source_id,
            "path": label(item["path"]),
            "bytes": path.stat().st_size,
            "sha256": actual,
        }
    return pins


def source_semantics() -> dict[str, bool]:
    kernel = locate(SOURCES["route_b_geometry_kernel"]["path"]).read_text(encoding="utf-8")
    wrapper = locate(SOURCES["exact_predicate_wrapper"]["path"]).read_text(encoding="utf-8")
    return {
        "spans_derived_once_during_initialization": (
            "self._derive()" in kernel and "self._derive_spans()" in kernel
        ),
        "link5_span_cached_in_link_local_coordinates": (
            'self.spans[child] = self._make_span(child, c["exit_F"], tgt_l,' in kernel
        ),
        "build_reuses_cached_child_span": (
            "sp_pts, sp_L, sp_R, sp_dm, sp_st = self.spans[child]" in kernel
        ),
        "build_applies_only_rigid_fk_transform_to_cached_points": (
            'sp_S = sp_pts @ TS[child][:3, :3].T + TS[child][:3, 3]' in kernel
        ),
        "cached_span_radius_is_reported_without_q_dependent_redesign": (
            "min_radius_mm=round(sp_R, 2)" in kernel
        ),
        "global_minimum_includes_each_connector_radius": (
            "if Rc < min_R:" in kernel and "min_R = Rc" in kernel
        ),
        "terminal_predicate_requires_nonnegative_bend_margin": (
            '"bend_margin_mm"' in wrapper
            and 'and all(float(result["margins"][key]) >= 0.0 for key in keys)' in wrapper
        ),
        "terminal_bend_requirement_is_30mm": (
            "required_bend_radius_mm: float = 30.0" in wrapper
        ),
        "final_connectors_are_fillet_trimmed_and_resampled": (
            "trims = [[0.0, 0.0] for _ in conns]" in kernel
            and "trims[ni - 1][1] = f[3]" in kernel
            and "trims[ni][0] = f[3]" in kernel
            and "pts, L, Rc = con.sample(t0, t1)" in kernel
        ),
        "fillet_trim_global_invariance_proved": False,
    }


def q_key(q: list[float]) -> tuple[float, ...]:
    return tuple(round(float(value), 12) for value in q)


def snapshot_fingerprint(snapshot: dict[str, Any]) -> str:
    payload = {key: value for key, value in snapshot.items() if key != "live_snapshot_sha256"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def evaluate_snapshot(snapshot: dict[str, Any]) -> dict[str, bool]:
    required = set(snapshot["required_state_ids"])
    expected = set(snapshot["expected_required_state_ids"])
    statuses = snapshot["required_state_status"]
    bends = snapshot["required_state_bend_radius_mm"]
    locations = snapshot["required_state_minimum_bend_location"]
    required_radius = float(snapshot["bend_radius_required_mm"])
    return {
        "required_state_set_exact": required == expected and len(snapshot["required_state_ids"]) == len(expected),
        "all_required_states_present_in_probe": set(statuses) == expected,
        "all_required_states_unsafe": all(statuses.get(state) == "UNSAFE" for state in expected),
        "all_required_state_bend_values_finite": all(state in bends and math.isfinite(float(bends[state])) for state in expected),
        "all_required_state_bend_values_below_requirement": all(state in bends and math.isfinite(float(bends[state])) and float(bends[state]) < required_radius for state in expected),
        "all_required_state_bend_argmins_are_span_link5": all(locations.get(state) == "span_link5" for state in expected),
        "source_diagnostic_and_global_q_scope_guarded": (
            all(value for key, value in snapshot["source_semantics"].items() if key != "fillet_trim_global_invariance_proved")
            and snapshot["source_semantics"]["fillet_trim_global_invariance_proved"] is False
            and snapshot["global_q_no_go_claim_made"] is False
        ),
        "route_b_reopening_forbidden": snapshot["route_b_reopening"] == "NONE_PERMITTED",
        "route_b_disposition_rejected": snapshot["route_b_disposition"] == "REJECTED_BY_EXACT_KINEMATIC_SWEEP",
        "mission_coverage_is_fail": snapshot["mission_coverage"] == "FAIL",
        "mandatory_trajectory_set_exact": set(snapshot["trajectory_segment_ids"]) == EXPECTED_SEGMENTS and len(snapshot["trajectory_segment_ids"]) == len(EXPECTED_SEGMENTS),
        "no_trajectory_released": snapshot["released_trajectory_count"] == 0,
        "sample_map_has_no_safe_point": snapshot["sample_map_safe_count"] == 0,
        "route_c_registry_still_all_hold": snapshot["route_c_non_null"] == 0 and snapshot["route_c_hold"] == 13,
        "route_c_cad_still_prohibited": snapshot["route_c_cad_authorized"] is False,
        "joint6_null_risk_surfaced": set(snapshot["joint6_pinch_null_state_ids"]) == expected,
        "clearance_null_risk_surfaced": set(snapshot["clearance_null_fields_by_state"]) == expected and all(snapshot["clearance_null_fields_by_state"][state] for state in expected),
        "live_snapshot_fingerprint_self_consistent": snapshot.get("live_snapshot_sha256") == snapshot_fingerprint(snapshot),
    }


def build_snapshot() -> tuple[dict[str, Any], dict[str, Any]]:
    owner = load_yaml("owner_odr_gpt_01_06")
    directives = {item["id"]: item for item in owner["directives"]}
    require("ODR-GPT-04" in directives, "ODR-GPT-04 missing from direct Owner register")
    odr04 = directives["ODR-GPT-04"]
    require(odr04["condition_evaluation"]["result"] == "NOT_SATISFIED", "ODR-GPT-04 recorded state drift")
    require(odr04["recorded_effect"]["deferred_full_range_harness_hold_allowed_now"] is False, "ODR-GPT-04 deferment was silently enabled")

    freeze = load_yaml("route_b_terminal_freeze")
    probe = load_json("mandatory_state_probe")
    envelope = load_yaml("rated_envelope")
    mission = load_json("mission_coverage_gate")
    mission_contract = load_yaml("mission_trajectory_contract")
    checkpoint_b = load_json("checkpoint_b")
    registry = load_yaml("route_c_registry")

    required_ids = list(mission["required_states"])
    result_by_id = {item["state_id"]: item for item in probe["results"]}
    require(len(required_ids) == 10 and len(set(required_ids)) == 10, "mandatory state contract is not 10 unique semantic states")
    require(set(required_ids) <= set(result_by_id), "mandatory probe omits a required state")
    required_results = [result_by_id[state_id] for state_id in required_ids]
    required_radius_values = {float(item["margins"]["bend_radius_required_mm"]) for item in required_results}
    require(required_radius_values == {30.0}, "bend requirement drift")

    with locate(SOURCES["envelope_map_csv"]["path"]).open("r", encoding="utf-8-sig", newline="") as stream:
        map_rows = list(csv.DictReader(stream))
    require(len(map_rows) == 75, "rated-envelope sample count drift")

    segment_ids = [item["id"] for item in mission_contract["segments"]]
    require(set(segment_ids) == EXPECTED_SEGMENTS and len(segment_ids) == 8, "mission segment set drift")

    semantics = source_semantics()
    require(all(value for key, value in semantics.items() if key != "fillet_trim_global_invariance_proved"), "frozen source diagnostic semantics drift")
    require(semantics["fillet_trim_global_invariance_proved"] is False, "global fillet-trim proof was fabricated")

    statuses = {item["state_id"]: item["status"] for item in required_results}
    bend_radii = {item["state_id"]: float(item["margins"]["bend_radius_mm"]) for item in required_results}
    bend_locations = {item["state_id"]: item["minimum_bend_location"] for item in required_results}
    clearances = {item["state_id"]: float(item["margins"]["clearance_mm"]) for item in required_results}
    pinches = {item["state_id"]: float(item["margins"]["pinch_mm"]) for item in required_results}
    lengths = {item["state_id"]: float(item["margins"]["length_margin_mm"]) for item in required_results}
    joint_limits = {item["state_id"]: float(item["margins"]["joint_limit_margin_rad"]) for item in required_results}
    section_link5 = {item["state_id"]: item["sections"]["span_link5"]["min_radius_mm"] for item in required_results}
    joint6_null = [item["state_id"] for item in required_results if item["per_joint_pinch_mm"].get("joint6") is None]
    clearance_null_fields = {
        item["state_id"]: sorted(field for field, value in item["per_field_clearance_mm"].items() if value is None)
        for item in required_results
    }

    snapshot = {
        "expected_required_state_ids": list(required_ids),
        "required_state_ids": list(required_ids),
        "required_state_status": statuses,
        "required_state_bend_radius_mm": bend_radii,
        "required_state_minimum_bend_location": bend_locations,
        "bend_radius_required_mm": 30.0,
        "source_semantics": semantics,
        "global_q_no_go_claim_made": False,
        "route_b_reopening": freeze["closure"]["reopening"],
        "route_b_disposition": directives["ODR-GPT-02"]["recorded_effect"]["disposition"],
        "mission_coverage": mission["mission_coverage"],
        "trajectory_segment_ids": segment_ids,
        "released_trajectory_count": int(mission["trajectory_segments_with_released_authority"]),
        "sample_map_safe_count": sum(row["status"] == "SAFE" for row in map_rows),
        "route_c_non_null": int(registry["summary"]["value_non_null"]),
        "route_c_hold": int(registry["summary"]["status_HOLD"]),
        "route_c_cad_authorized": bool(checkpoint_b["admission"]["ROUTE_C_CAD_AUTHORIZED"]),
        "joint6_pinch_null_state_ids": joint6_null,
        "clearance_null_fields_by_state": clearance_null_fields,
    }
    snapshot["live_snapshot_sha256"] = snapshot_fingerprint(snapshot)
    checks = evaluate_snapshot(snapshot)
    require(all(checks.values()), f"falsifier precondition failed: {[key for key, value in checks.items() if not value]}")

    exact_bend_min = min(bend_radii.values())
    exact_bend_max = max(bend_radii.values())
    exact_deficit_min = 30.0 - exact_bend_max
    exact_deficit_max = 30.0 - exact_bend_min
    unique_q = {q_key(item["q_rad"]) for item in required_results}
    external_gates = dict(mission["external_trajectory_gates"])

    analysis = {
        "required_states": {
            "total": len(required_ids),
            "safe": sum(value == "SAFE" for value in statuses.values()),
            "unsafe": sum(value == "UNSAFE" for value in statuses.values()),
            "unknown": sum(value == "UNKNOWN" for value in statuses.values()),
            "unique_q_count": len(unique_q),
            "ids": required_ids,
        },
        "mandatory_trajectory_segments": {
            "required": len(segment_ids),
            "released": int(mission["trajectory_segments_with_released_authority"]),
            "unknown": int(mission["trajectory_segments_unknown"]),
            "ids": segment_ids,
            "external_gates": external_gates,
        },
        "deterministic_model_outputs": {
            "unit_statement": {
                "clearance": "mm",
                "bend_radius": "mm",
                "bend_margin": "mm",
                "pinch": "mm",
                "length_margin": "mm",
                "joint_limit_margin": "rad",
            },
            "uncertainty_statement": "NO_METROLOGICAL_UNCERTAINTY_AVAILABLE__DETERMINISTIC_FROZEN_MODEL_OUTPUTS_ONLY__NOT_PHYSICAL_QUALIFICATION_DATA",
            "numerical_discretization_error_bound": "NOT_ESTABLISHED",
            "model_form_uncertainty": "NOT_QUANTIFIED",
            "bend_radius_required_mm": 30.0,
            "required_state_bend_radius_mm_min": exact_bend_min,
            "required_state_bend_radius_mm_max": exact_bend_max,
            "required_state_bend_deficit_mm_min": exact_deficit_min,
            "required_state_bend_deficit_mm_max": exact_deficit_max,
            "section_reported_span_link5_radius_mm_values": sorted({float(value) for value in section_link5.values()}),
            "clearance_mm_range": [min(clearances.values()), max(clearances.values())],
            "pinch_mm_range": [min(pinches.values()), max(pinches.values())],
            "length_margin_mm_range": [min(lengths.values()), max(lengths.values())],
            "joint_limit_margin_rad_range": [min(joint_limits.values()), max(joint_limits.values())],
            "conformity_rule": "current frozen software contract requires every margin >= 0 and empty_comparison_sets == 0; no uncertainty guard-band or physical qualification claim is introduced here",
        },
        "registered_branch_certificate": {
            "claim_under_test": "CURRENT_FROZEN_ROUTE_B_CAN_EARN_ODR_GPT_04_WITHOUT_A_NEW_OWNER_AUTHORIZED_ECR",
            "result": "FALSIFIED_BY_CURRENT_GATE_STATE_PLUS_TERMINAL_FREEZE",
            "proof_chain": [
                "ODR-GPT-04 requires every registered mandatory state and all eight released trajectories to pass the harness and external Gates.",
                "The current registered evidence has 0/10 mandatory states SAFE, 0/8 released trajectories and Mission Coverage FAIL.",
                "The Route-B terminal freeze records reopening=NONE_PERMITTED and further_mechanical_design_time_on_route_b=NONE.",
                "Therefore the current frozen Route-B branch cannot earn ODR-GPT-04; changing the centerline, predicate or task-state authority requires a separate direct Owner ECR and a new graph version.",
            ],
            "global_q_no_go_claim": "NOT_MADE",
        },
        "candidate_root_cause_diagnostic_not_global_proof": {
            "observation": "all registered mandatory states report the terminal bend argmin at span_link5 near 0.100123 mm versus the 30 mm frozen requirement",
            "cached_span_rigid_transform_structure": True,
            "fillet_trim_and_resample_present": True,
            "fillet_trim_global_invariance_proved": False,
            "consequence": "supports a root-cause hypothesis for the registered failures but does not prove that every q in E_HW is UNSAFE",
            "source_semantics": semantics,
            "observed_required_state_argmins": sorted(set(bend_locations.values())),
            "rate_scaling_relevance_for_a_fixed_q_path": "NONE__CURRENT_STATIC_PREDICATE_CONTAINS_NO_qdot_OR_qddot_INPUT",
        },
        "sample_map": {
            "samples_total": len(map_rows),
            "safe": sum(row["status"] == "SAFE" for row in map_rows),
            "unsafe": sum(row["status"] == "UNSAFE" for row in map_rows),
            "unknown": sum(row["status"] == "UNKNOWN" for row in map_rows),
            "families": sorted({row["family"] for row in map_rows}),
            "scope_limit": "THREE q2-by-q3 SLICES_ONLY__NOT_A_STANDALONE_6D_EMPTY_SET_CERTIFICATE",
        },
        "route_c_state": {
            "checkpoint_b_outcome": checkpoint_b["checkpoint_outcome"],
            "admission_passed": checkpoint_b["admission"]["summary"]["pass"],
            "admission_total": checkpoint_b["admission"]["summary"]["conditions_total"],
            "registry_non_null": registry["summary"]["value_non_null"],
            "registry_available": registry["summary"]["status_AVAILABLE"],
            "registry_hold": registry["summary"]["status_HOLD"],
            "route_c_cad_authorized": checkpoint_b["admission"]["ROUTE_C_CAD_AUTHORIZED"],
        },
        "red_team_findings": [
            {
                "id": "RT-HRN-01",
                "severity_for_current_negative_result": "NONE",
                "severity_for_future_positive_predicate": "HIGH",
                "finding": "per_joint_pinch_mm.joint6 is null in every required-state result while aggregate empty_comparison_sets remains zero",
                "disposition": "current negative result survives because bend, clearance and pinch aggregate margins are already negative; any new positive Route-C predicate must require every named field and joint comparison to be finite, otherwise UNKNOWN/ABORT",
                "affected_state_count": len(joint6_null),
            },
            {
                "id": "RT-HRN-02",
                "severity_for_current_negative_result": "NONE",
                "severity_for_physical_interpretation": "MEDIUM",
                "finding": "protected feedthrough/clamp/backshell contact zones are not exempted and may create conservative clearance or pinch false negatives",
                "disposition": "do not weaken frozen V1; a future version requires physical connector/clamp/backshell CAD and finite named contact volumes; the currently registered states remain failed independently of this possible conservatism",
            },
            {
                "id": "RT-HRN-03",
                "severity_for_current_negative_result": "NONE",
                "severity_for_continuous_claim": "HIGH",
                "finding": "the 75-point map has no error bound and cannot prove the unsampled six-dimensional domain; the existing exact kernel is also a frozen discretized evaluator rather than a mathematical continuum certificate",
                "disposition": "do not extrapolate the map to the unsampled 6D domain; any new Route-C positive release needs a versioned state oracle and conservative continuous-trajectory certificate",
            },
            {
                "id": "RT-HRN-04",
                "severity_for_global_q_claim": "HIGH",
                "severity_for_current_registered_branch_closure": "NONE",
                "finding": "final Connector(poly) geometry is fillet-trimmed and resampled; the current evidence does not prove that trim bounds preserve the span_link5 curvature minimum over all E_HW",
                "disposition": "the global-q no-go claim was removed; closure rests on the 0/10, 0/8, Mission FAIL state plus the Owner terminal freeze",
            },
            {
                "id": "RT-HRN-05",
                "severity_for_current_negative_result": "NONE",
                "severity_for_future_positive_predicate": "HIGH",
                "finding": "required-state per_field_clearance_mm contains null fields in every state, in addition to joint6 pinch null",
                "disposition": "the exact null-field map is machine-recorded; any future positive predicate must require every named field and joint comparison finite or return UNKNOWN/ABORT",
                "null_fields_by_state": clearance_null_fields,
            },
        ],
        "scope_and_nonclaims": [
            "This falsifies only the ODR-GPT-04 deferment path for the current frozen Route-B centerline and predicate.",
            "It does not prove that every external harness topology is physically impossible.",
            "It does not prove that every q in E_HW is UNSAFE; fillet-trim invariance over the full domain is not established.",
            "It does not convert deterministic model output into measurement or qualification evidence.",
            "It does not resolve protected-contact semantics, joint6 coverage, trajectory authority, IK, collision, Solar keep-out, SAFE-00, or dynamic harness torque.",
            "It does not authorize Route-C CAD, a Route-B reopening, a new Route-B2, Sim13 production binding, terminal release, or flight qualification.",
        ],
        "engineering_ruling": {
            "current_frozen_route_b_path_search": "STOP__CURRENT_BRANCH_FAILS_ODR_GPT_04_AND_ROUTE_B_REOPENING_IS_PROHIBITED",
            "odr_gpt_04_deferment": "NOT_EARNED",
            "current_release_path": "ROUTE_C_PHYSICAL_INPUTS_TO_CHECKPOINT_B_TO_SEPARATE_CAD_AUTHORITY_TO_NEW_PHYSICAL_SWEEP",
            "alternate_new_route_rule": "only a separately Owner-authorized, version-isolated new centerline and predicate can be evaluated; it is not a reopening or relabelling of frozen Route-B",
            "future_positive_predicate_minimum_additions": [
                "finite coverage for every required clearance field and every required joint pinch comparison; missing value => UNKNOWN/ABORT",
                "physical connector/clamp/backshell/guide contact volumes with owner matching",
                "controlled P01-P13 values with units, uncertainty/tolerance, source and authority class",
                "eight complete trajectory authorities plus continuous conservative interval or swept-volume proof",
            ],
        },
    }
    return snapshot, {"checks": checks, "analysis": analysis}


def mutation_controls(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    controls: list[tuple[str, str, Any]] = []

    def add(control_id: str, target_check: str, mutate) -> None:
        altered = copy.deepcopy(snapshot)
        mutate(altered)
        result = evaluate_snapshot(altered)
        controls.append((control_id, target_check, result))

    first_state = snapshot["expected_required_state_ids"][0]
    add("NC-01_FORCE_ONE_REQUIRED_STATE_SAFE", "all_required_states_unsafe", lambda data: data["required_state_status"].__setitem__(first_state, "SAFE"))
    add("NC-02_DROP_ONE_REQUIRED_STATE", "required_state_set_exact", lambda data: data["required_state_ids"].pop())
    add("NC-03_RAISE_ONE_BEND_RADIUS_ABOVE_REQUIREMENT", "all_required_state_bend_values_below_requirement", lambda data: data["required_state_bend_radius_mm"].__setitem__(first_state, 30.001))
    add("NC-04_CHANGE_BEND_ARGMIN", "all_required_state_bend_argmins_are_span_link5", lambda data: data["required_state_minimum_bend_location"].__setitem__(first_state, "joint5_wrap"))
    add("NC-05_FABRICATE_GLOBAL_Q_NO_GO", "source_diagnostic_and_global_q_scope_guarded", lambda data: data.__setitem__("global_q_no_go_claim_made", True))
    add("NC-06_REOPEN_FROZEN_ROUTE_B", "route_b_reopening_forbidden", lambda data: data.__setitem__("route_b_reopening", "ALLOWED"))
    add("NC-07_INJECT_SAFE_MAP_SAMPLE", "sample_map_has_no_safe_point", lambda data: data.__setitem__("sample_map_safe_count", 1))
    add("NC-08_FABRICATE_EIGHT_RELEASED_TRAJECTORIES", "no_trajectory_released", lambda data: data.__setitem__("released_trajectory_count", 8))
    add("NC-09_FABRICATE_ROUTE_C_REGISTRY_COMPLETE", "route_c_registry_still_all_hold", lambda data: (data.__setitem__("route_c_non_null", 13), data.__setitem__("route_c_hold", 0)))
    add("NC-10_SILENTLY_AUTHORIZE_ROUTE_C_CAD", "route_c_cad_still_prohibited", lambda data: data.__setitem__("route_c_cad_authorized", True))
    add("NC-11_HIDE_JOINT6_NULL_RISK", "joint6_null_risk_surfaced", lambda data: data.__setitem__("joint6_pinch_null_state_ids", []))
    add("NC-12_HIDE_CLEARANCE_NULL_RISK", "clearance_null_risk_surfaced", lambda data: data.__setitem__("clearance_null_fields_by_state", {}))
    add("NC-13_APPEND_DUPLICATE_TRAJECTORY", "mandatory_trajectory_set_exact", lambda data: data["trajectory_segment_ids"].append(data["trajectory_segment_ids"][0]))
    add("NC-14_INJECT_NONFINITE_BEND", "all_required_state_bend_values_finite", lambda data: data["required_state_bend_radius_mm"].__setitem__(first_state, float("nan")))
    add("NC-15_DROP_REQUIRED_PROBE_STATUS", "all_required_states_present_in_probe", lambda data: data["required_state_status"].pop(first_state))
    add("NC-16_CHANGE_ROUTE_B_DISPOSITION", "route_b_disposition_rejected", lambda data: data.__setitem__("route_b_disposition", "PASS"))
    add("NC-17_FABRICATE_MISSION_PASS", "mission_coverage_is_fail", lambda data: data.__setitem__("mission_coverage", "PASS"))
    add("NC-18_CORRUPT_NUMERIC_SNAPSHOT", "live_snapshot_fingerprint_self_consistent", lambda data: data["required_state_bend_radius_mm"].__setitem__(first_state, -999.0))

    output = []
    for control_id, target, result in controls:
        require(result[target] is False, f"negative control did not trip target check: {control_id}")
        require(not all(result.values()), f"negative control did not fail closed: {control_id}")
        output.append({
            "id": control_id,
            "target_check": target,
            "expected_gate_result": "FAIL_CLOSED",
            "observed_target_check": result[target],
            "observed_all_checks_pass": all(result.values()),
            "pass": result[target] is False and not all(result.values()),
        })
    return output


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    generated_local = datetime.now(TZ).isoformat()
    pins = pin_sources()
    snapshot, result = build_snapshot()
    controls = mutation_controls(snapshot)

    evidence = {
        "schema": "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_FALSIFIER_V1",
        "generated_local": generated_local,
        "generator": "GPT mechanical chief / harness mission-envelope falsifier",
        "scope": "current hash-frozen Route-B centerline, evaluator and ODR-GPT-04 branch only",
        "source_pins": list(pins.values()),
        "snapshot": snapshot,
        **result["analysis"],
        "technical_verdict": "ODR_GPT_04_DEFERMENT_NOT_EARNED_FOR_FROZEN_ROUTE_B__REGISTERED_MANDATORY_STATES_UNSAFE__ROUTE_B_REOPENING_PROHIBITED__ROUTE_C_REQUIRED_UNLESS_SEPARATELY_AUTHORIZED_NEW_VERSIONED_ROUTE",
        "owner_accepted": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    evidence_path = PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_FALSIFIER_V1.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    control_payload = {
        "schema": "ODR_GPT_04_FROZEN_ROUTE_B_ADVERSARIAL_CONTROLS_V1",
        "generated_local": generated_local,
        "method": "in-memory single-fault mutations against an independently enumerable fail-closed predicate",
        "controls": controls,
        "summary": {"passed": sum(item["pass"] for item in controls), "total": len(controls), "failed": [item["id"] for item in controls if not item["pass"]]},
        "nonclaim": "mutation PASS proves guard sensitivity, not physical qualification",
    }
    controls_path = PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_ADVERSARIAL_CONTROLS_V1.json"
    controls_path.write_text(json.dumps(control_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    checks = result["checks"]
    criteria = [
        {"id": f"FZ-{index:02d}", "name": name, "pass": bool(value)}
        for index, (name, value) in enumerate(checks.items(), start=1)
    ]
    gate = {
        "schema": "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_GATE_V1",
        "generated_local": generated_local,
        "scope": "integrity and current-branch no-go certification; PASS here is a PASS of the falsifier, not a harness PASS",
        "outcome": "PASS_FALSIFIER__FROZEN_ROUTE_B_ODR_GPT_04_BRANCH_CLOSED_NEGATIVE",
        "technical_verdict": evidence["technical_verdict"],
        "criteria": criteria,
        "summary": {"passed": sum(item["pass"] for item in criteria), "total": len(criteria), "failed": [item["id"] for item in criteria if not item["pass"]]},
        "negative_controls": control_payload["summary"],
        "branch_state": {
            "current_frozen_route_b_rated_envelope_path": "TERMINAL_NEGATIVE_CURRENT_REGISTERED_BRANCH",
            "odr_gpt_04_deferment_earned": False,
            "mission_coverage": "FAIL",
            "route_c_required_to_continue": True,
            "route_c_cad_authorized": False,
        },
        "red_team_survivor": {
            "id": "RT-HRN-01",
            "current_negative_result_affected": False,
            "future_positive_predicate_action": "REQUIRE_FINITE_PER_NAMED_JOINT_AND_FIELD_OR_UNKNOWN_ABORT",
        },
        "proof_scope_guard": {
            "global_q_no_go_claim_made": False,
            "fillet_trim_global_invariance_proved": False,
            "closure_basis": "REGISTERED_0_OF_10_SAFE__0_OF_8_RELEASED__MISSION_FAIL__ROUTE_B_REOPENING_NONE_PERMITTED",
        },
        "owner_accepted": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
        "terminal_release_candidate_generated": False,
        "self_hash_policy": "SELF_REFERENCE_EXCLUDED; package manifest pins this Gate after emission",
    }
    require(gate["summary"]["passed"] == gate["summary"]["total"], "falsifier Gate is not internally complete")
    require(control_payload["summary"]["passed"] == control_payload["summary"]["total"], "negative control failure")
    gate_path = PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_GATE_V1.json"
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    receipt = f"""# ODR-GPT-04 冻结 Route-B 分支证伪收据 V1

生成时间：{generated_local}

## 裁决

- 证伪器完整性：{gate['summary']['passed']}/{gate['summary']['total']} PASS；负控：{control_payload['summary']['passed']}/{control_payload['summary']['total']} PASS。
- 当前冻结 Route-B 的 ODR-GPT-04 额定任务包络分支：**已证伪**。
- 直接原因：当前注册证据为 10 个强制状态 0/10 SAFE、8 条轨迹 0/8 released、Mission Coverage FAIL，同时 Route-B 终局冻结明确 `reopening=NONE_PERMITTED`。因此当前冻结分支没有合法的继续搜索或发布路径。
- `span_link5` 在这些注册状态下的确定性模型输出约 0.100123 mm，对 30 mm 要求的最小缺口约 {result['analysis']['deterministic_model_outputs']['required_state_bend_deficit_mm_min']:.6f} mm；它是根因诊断，不是“任意 q 均失败”的全域证明，因为最终连接器还存在构型相关圆角裁剪与重采样。
- 10 个强制状态 0/10 SAFE；8 条轨迹 0/8 released；Mission Coverage 保持 FAIL。
- 当前不再对冻结 Route-B 投入轨迹搜索、姿态重绑或限速优化算力。

## 边界

这不是“所有外置线束拓扑都不可能”的结论，也不是“所有 q 均 UNSAFE”的结论或物理资格鉴定结论。75 点地图不是六维空集证明；圆角裁剪的全域不变量尚未建立。所有数值均带 mm/rad 量纲，但没有可用的计量不确定度，故只作为冻结模型/软件合同证据。

红队还发现：10/10 强制状态的 `per_joint_pinch_mm.joint6` 均为 null；每个状态也有一个或多个 `per_field_clearance_mm` 为 null，而 V1 聚合仍记 `empty_comparison_sets=0`。它们不改变当前负结果，但任何未来正向 Route-C 谓词必须把任一必需 joint/field 的 null 判为 UNKNOWN/ABORT。

## 唯一受控前进方向

继续 Route-C 的 P01-P13 物理输入闭环，达到 Checkpoint-B 8/8 后再取得独立 CAD 授权并建立新物理路线；或者由 Owner 另行授权一个版本隔离的新中心线/新谓词 ECR。两者都不得重开、改名或美化当前冻结 Route-B。

Owner acceptance、Route-C CAD authority、next-stage authority、release credit 均保持 false。
"""
    receipt_path = PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_RECEIPT_V1.md"
    receipt_path.write_text(receipt, encoding="utf-8", newline="\n")

    outputs = [
        evidence_path,
        controls_path,
        gate_path,
        receipt_path,
        Path(__file__),
        PACKAGE / "validate_odr_gpt04_frozen_route_b_falsifier.py",
    ]
    rows = [
        {"class": "INPUT", "id": source_id, "path": pin["path"], "bytes": pin["bytes"], "sha256": pin["sha256"]}
        for source_id, pin in pins.items()
    ]
    for path in outputs:
        require(path.is_file(), f"output/script missing before manifest emission: {path}")
        rows.append({
            "class": "OUTPUT",
            "id": path.name,
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    rows.sort(key=lambda row: (row["class"], row["path"]))
    write_csv(PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_SHA256.csv", ["class", "id", "path", "bytes", "sha256"], rows)


if __name__ == "__main__":
    main()
