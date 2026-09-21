from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import yaml


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[3]

EXPECTED_SOURCE_HASHES = {
    "owner_attachment": "67821E04869BE8202CF2473980B73AA4CE595B9689CC9D54F340820C0D38F773",
    "owner_odr_gpt_01_06": "B7EE60281935DD7417027D5428B9291BEE7D3F6528022509ACA168FB39B68689",
    "owner_odr_35_41": "7655FA44BA4CD2B0369184100A18DF1001B8C40CC6B4D9731D4E4ACEE9D6433E",
    "route_b_terminal_freeze": "74EADB7A239C3A88B99C89999E49036EB3033654CE8D988A0D2F007F020DFA61",
    "route_b_frozen_pins": "6BB8E9C5FF6910BE07D1720D320C4CB560A2CF07AD254DEB83E931AF4731C588",
    "route_b_product_definition": "4294D08E246A99DB37A47A38B432B7DC2324436ED96FB2F0B771D4B08EA4BA9E",
    "exact_predicate_contract": "FB21D09602F6CDCF7CF21E60615FDEE9C795DFA29D11609B4FBE237789C5C295",
    "exact_predicate_wrapper": "327F6C907A1F9281071E74BA931C3A42C36AA1782897CCC3D6972B66E1129C28",
    "mission_probe_source": "607ADF4A5C7EEB41D1418E9FF59FC5C4F5B679CCEEA587CFE7BE5B470611E75F",
    "route_b_geometry_kernel": "F99FF775B20940D4F5338E2AECA6F9C03D565FF718170B92B6C97CBDEB499261",
    "full_fk_negative_result": "DB86348B8276FB2DCEB48DA30D1969948B37AAC4DF6D67D7588D928CF8281FAE",
    "mandatory_state_probe": "96FCBDA104ADDD3194ED3EDAA5A3CFD8E230ACCA8D4608BE18A4258636EADD70",
    "rated_envelope": "A63A93DE5B6B3BEE37819379757ABE5B9F7FC457641F852E06676B686BC416C6",
    "envelope_map_csv": "0159FB6D525D7390E5929839610E30F4E94DA112CC3F49314369BD17EA2D6EF7",
    "envelope_map_npz": "21CB19FE3281090A834CCFA672C0E7CC8D1EEFCC7D55F11CB4A9E09E3E3B392B",
    "mission_pose_rebind": "2954AA16DE68CE6550C0A281DD309BF14585970087EBE35663485E0E932AA62A",
    "mission_trajectory_contract": "C06A40DE171F0517ACB34CCC14C918A9A4252F7B55A425B2CBAC95229B44A98A",
    "mission_coverage_gate": "F3B444222E87509B66F712E623A4903748C7309C6396708EC02A0C1A54CDAA5C",
    "harness_terminal_gate": "D65BD945B3F0C93041BFD10CFABCD9E423596B3FC19400C45FA58CB08DE96AF4",
    "handoff_gate_v2": "13722965D5C558D3439A7CB1E77ABBF3C2094B88E9D62F80D664D0C4C90D4E21",
    "checkpoint_b": "C9E7526D790E1FB7F5522A113EDF41F5913207C15A68E12468FD9EBA157349D1",
    "route_c_admission": "0AE3888EDBE9A2DCD85792AA0E8800432911E4ED1C11D48C2206B60BED2521B8",
    "route_c_registry": "6264A0A45F6A497787F3D96205CEF7799A19A225CD23CEA66D5AD31E335A3E8E",
    "route_c_rfi": "77187CF362A9AA41B287A269D4AA827BA8B8A8385576DB0FD003E4BBE63EC1A2",
}
EXPECTED_STATES = {
    "ARM_STOWED_ONORBIT_C05", "ARM_RELEASE_CLEAR", "Q_DEPLOYED_HOME", "ARM_TASK_READY_C06",
    "PREGRASP", "CONTACT", "CAPTURE_22KG", "POST_CAPTURE_22KG", "PHYSICS_VETO_150KG", "SAFE_RECOVERY_TARGET",
}
EXPECTED_SEGMENTS = {"M01", "M02", "M03", "M04", "M05_22", "M06_22", "M07_22", "M05_150"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def read_manifest() -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    path = PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_SHA256.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == ["class", "id", "path", "bytes", "sha256"], "manifest column contract drift")
        rows = list(reader)
    require(len(rows) == len(EXPECTED_SOURCE_HASHES) + 6, "manifest row count drift")
    require(len({row["id"] for row in rows}) == len(rows), "duplicate manifest id")
    require(len({row["path"] for row in rows}) == len(rows), "duplicate manifest path")
    by_id = {row["id"]: row for row in rows}
    for row in rows:
        path = resolve(row["path"])
        require(path.is_file(), f"manifest path missing: {path}")
        require(int(row["bytes"]) == path.stat().st_size, f"size mismatch: {row['id']}")
        require(row["sha256"].upper() == sha256(path), f"hash mismatch: {row['id']}")
    for source_id, expected in EXPECTED_SOURCE_HASHES.items():
        require(source_id in by_id, f"source absent from manifest: {source_id}")
        require(by_id[source_id]["class"] == "INPUT", f"source class drift: {source_id}")
        require(by_id[source_id]["sha256"].upper() == expected, f"source trust pin drift: {source_id}")
    required_outputs = {
        "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_FALSIFIER_V1.json",
        "ODR_GPT_04_FROZEN_ROUTE_B_ADVERSARIAL_CONTROLS_V1.json",
        "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_GATE_V1.json",
        "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_RECEIPT_V1.md",
        "build_odr_gpt04_frozen_route_b_falsifier.py",
        "validate_odr_gpt04_frozen_route_b_falsifier.py",
    }
    require(required_outputs == {row["id"] for row in rows if row["class"] == "OUTPUT"}, "output manifest set drift")
    return rows, by_id


def load_input(by_id: dict[str, dict[str, str]], source_id: str) -> Any:
    path = resolve(by_id[source_id]["path"])
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")


def discrete_radius(points: np.ndarray) -> np.ndarray:
    a, b, c = points[:-2], points[1:-1], points[2:]
    v1, v2 = b - a, c - b
    cross = np.linalg.norm(np.cross(v1, v2), axis=1)
    l1 = np.linalg.norm(v1, axis=1)
    l2 = np.linalg.norm(v2, axis=1)
    l3 = np.linalg.norm(c - a, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(cross > 1e-12, l1 * l2 * l3 / (2.0 * cross), np.inf)


def check_rigid_invariance() -> None:
    points = np.asarray([[0.0, 0.0, 0.0], [0.7, 0.2, 0.1], [1.4, 0.9, -0.2], [2.2, 1.1, 0.5], [3.0, 1.8, 0.4]], float)
    base = discrete_radius(points)
    axes = [np.asarray([1.0, 2.0, 3.0]), np.asarray([-2.0, 0.5, 1.0]), np.asarray([0.3, -0.7, 2.0])]
    angles = [0.31, -1.17, 2.03]
    for axis, angle in zip(axes, angles):
        axis = axis / np.linalg.norm(axis)
        k = np.asarray([[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]])
        rotation = np.eye(3) + math.sin(angle) * k + (1.0 - math.cos(angle)) * (k @ k)
        transformed = points @ rotation.T + np.asarray([13.0, -4.0, 9.5])
        require(np.max(np.abs(discrete_radius(transformed) - base)) < 1e-12, "discrete radius is not rigid-transform invariant")


def source_semantics(kernel: str, wrapper: str) -> dict[str, bool]:
    return {
        "spans_derived_once_during_initialization": "self._derive()" in kernel and "self._derive_spans()" in kernel,
        "link5_span_cached_in_link_local_coordinates": 'self.spans[child] = self._make_span(child, c["exit_F"], tgt_l,' in kernel,
        "build_reuses_cached_child_span": "sp_pts, sp_L, sp_R, sp_dm, sp_st = self.spans[child]" in kernel,
        "build_applies_only_rigid_fk_transform_to_cached_points": 'sp_S = sp_pts @ TS[child][:3, :3].T + TS[child][:3, 3]' in kernel,
        "cached_span_radius_is_reported_without_q_dependent_redesign": "min_radius_mm=round(sp_R, 2)" in kernel,
        "global_minimum_includes_each_connector_radius": "if Rc < min_R:" in kernel and "min_R = Rc" in kernel,
        "terminal_predicate_requires_nonnegative_bend_margin": '"bend_margin_mm"' in wrapper and 'and all(float(result["margins"][key]) >= 0.0 for key in keys)' in wrapper,
        "terminal_bend_requirement_is_30mm": "required_bend_radius_mm: float = 30.0" in wrapper,
        "final_connectors_are_fillet_trimmed_and_resampled": (
            "trims = [[0.0, 0.0] for _ in conns]" in kernel
            and "trims[ni - 1][1] = f[3]" in kernel
            and "trims[ni][0] = f[3]" in kernel
            and "pts, L, Rc = con.sample(t0, t1)" in kernel
        ),
        "fillet_trim_global_invariance_proved": False,
    }


def snapshot_fingerprint(snapshot: dict[str, Any]) -> str:
    payload = {key: value for key, value in snapshot.items() if key != "live_snapshot_sha256"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def recompute_checks(snapshot: dict[str, Any]) -> dict[str, bool]:
    required = set(snapshot["required_state_ids"])
    statuses = snapshot["required_state_status"]
    bends = snapshot["required_state_bend_radius_mm"]
    locations = snapshot["required_state_minimum_bend_location"]
    radius = float(snapshot["bend_radius_required_mm"])
    return {
        "required_state_set_exact": required == EXPECTED_STATES and len(snapshot["required_state_ids"]) == 10,
        "all_required_states_present_in_probe": set(statuses) == EXPECTED_STATES,
        "all_required_states_unsafe": all(statuses.get(state) == "UNSAFE" for state in EXPECTED_STATES),
        "all_required_state_bend_values_finite": all(state in bends and math.isfinite(float(bends[state])) for state in EXPECTED_STATES),
        "all_required_state_bend_values_below_requirement": all(state in bends and math.isfinite(float(bends[state])) and float(bends[state]) < radius for state in EXPECTED_STATES),
        "all_required_state_bend_argmins_are_span_link5": all(locations.get(state) == "span_link5" for state in EXPECTED_STATES),
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
        "joint6_null_risk_surfaced": set(snapshot["joint6_pinch_null_state_ids"]) == EXPECTED_STATES,
        "clearance_null_risk_surfaced": set(snapshot["clearance_null_fields_by_state"]) == EXPECTED_STATES and all(snapshot["clearance_null_fields_by_state"][state] for state in EXPECTED_STATES),
        "live_snapshot_fingerprint_self_consistent": snapshot.get("live_snapshot_sha256") == snapshot_fingerprint(snapshot),
    }


def build_live_snapshot(
    probe: dict[str, Any], mission: dict[str, Any], contract: dict[str, Any], map_rows: list[dict[str, str]],
    freeze: dict[str, Any], registry: dict[str, Any], checkpoint: dict[str, Any], owner: dict[str, Any],
    kernel: str, wrapper: str,
) -> dict[str, Any]:
    required_ids = list(mission["required_states"])
    results = {item["state_id"]: item for item in probe["results"]}
    required_results = [results[state] for state in required_ids]
    directives = {item["id"]: item for item in owner["directives"]}
    snapshot = {
        "expected_required_state_ids": list(required_ids),
        "required_state_ids": list(required_ids),
        "required_state_status": {item["state_id"]: item["status"] for item in required_results},
        "required_state_bend_radius_mm": {item["state_id"]: float(item["margins"]["bend_radius_mm"]) for item in required_results},
        "required_state_minimum_bend_location": {item["state_id"]: item["minimum_bend_location"] for item in required_results},
        "bend_radius_required_mm": 30.0,
        "source_semantics": source_semantics(kernel, wrapper),
        "global_q_no_go_claim_made": False,
        "route_b_reopening": freeze["closure"]["reopening"],
        "route_b_disposition": directives["ODR-GPT-02"]["recorded_effect"]["disposition"],
        "mission_coverage": mission["mission_coverage"],
        "trajectory_segment_ids": [item["id"] for item in contract["segments"]],
        "released_trajectory_count": int(mission["trajectory_segments_with_released_authority"]),
        "sample_map_safe_count": sum(row["status"] == "SAFE" for row in map_rows),
        "route_c_non_null": int(registry["summary"]["value_non_null"]),
        "route_c_hold": int(registry["summary"]["status_HOLD"]),
        "route_c_cad_authorized": bool(checkpoint["admission"]["ROUTE_C_CAD_AUTHORIZED"]),
        "joint6_pinch_null_state_ids": [item["state_id"] for item in required_results if item["per_joint_pinch_mm"].get("joint6") is None],
        "clearance_null_fields_by_state": {
            item["state_id"]: sorted(field for field, value in item["per_field_clearance_mm"].items() if value is None)
            for item in required_results
        },
    }
    snapshot["live_snapshot_sha256"] = snapshot_fingerprint(snapshot)
    return snapshot


def validate_negative_controls(snapshot: dict[str, Any], recorded: dict[str, Any]) -> None:
    expected_records = []

    def add(control_id: str, target: str, mutate) -> None:
        altered = copy.deepcopy(snapshot)
        mutate(altered)
        checks = recompute_checks(altered)
        expected_records.append({
            "id": control_id,
            "target_check": target,
            "expected_gate_result": "FAIL_CLOSED",
            "observed_target_check": checks[target],
            "observed_all_checks_pass": all(checks.values()),
            "pass": checks[target] is False and not all(checks.values()),
        })

    first = snapshot["expected_required_state_ids"][0]
    add("NC-01_FORCE_ONE_REQUIRED_STATE_SAFE", "all_required_states_unsafe", lambda data: data["required_state_status"].__setitem__(first, "SAFE"))
    add("NC-02_DROP_ONE_REQUIRED_STATE", "required_state_set_exact", lambda data: data["required_state_ids"].pop())
    add("NC-03_RAISE_ONE_BEND_RADIUS_ABOVE_REQUIREMENT", "all_required_state_bend_values_below_requirement", lambda data: data["required_state_bend_radius_mm"].__setitem__(first, 30.001))
    add("NC-04_CHANGE_BEND_ARGMIN", "all_required_state_bend_argmins_are_span_link5", lambda data: data["required_state_minimum_bend_location"].__setitem__(first, "joint5_wrap"))
    add("NC-05_FABRICATE_GLOBAL_Q_NO_GO", "source_diagnostic_and_global_q_scope_guarded", lambda data: data.__setitem__("global_q_no_go_claim_made", True))
    add("NC-06_REOPEN_FROZEN_ROUTE_B", "route_b_reopening_forbidden", lambda data: data.__setitem__("route_b_reopening", "ALLOWED"))
    add("NC-07_INJECT_SAFE_MAP_SAMPLE", "sample_map_has_no_safe_point", lambda data: data.__setitem__("sample_map_safe_count", 1))
    add("NC-08_FABRICATE_EIGHT_RELEASED_TRAJECTORIES", "no_trajectory_released", lambda data: data.__setitem__("released_trajectory_count", 8))
    add("NC-09_FABRICATE_ROUTE_C_REGISTRY_COMPLETE", "route_c_registry_still_all_hold", lambda data: (data.__setitem__("route_c_non_null", 13), data.__setitem__("route_c_hold", 0)))
    add("NC-10_SILENTLY_AUTHORIZE_ROUTE_C_CAD", "route_c_cad_still_prohibited", lambda data: data.__setitem__("route_c_cad_authorized", True))
    add("NC-11_HIDE_JOINT6_NULL_RISK", "joint6_null_risk_surfaced", lambda data: data.__setitem__("joint6_pinch_null_state_ids", []))
    add("NC-12_HIDE_CLEARANCE_NULL_RISK", "clearance_null_risk_surfaced", lambda data: data.__setitem__("clearance_null_fields_by_state", {}))
    add("NC-13_APPEND_DUPLICATE_TRAJECTORY", "mandatory_trajectory_set_exact", lambda data: data["trajectory_segment_ids"].append(data["trajectory_segment_ids"][0]))
    add("NC-14_INJECT_NONFINITE_BEND", "all_required_state_bend_values_finite", lambda data: data["required_state_bend_radius_mm"].__setitem__(first, float("nan")))
    add("NC-15_DROP_REQUIRED_PROBE_STATUS", "all_required_states_present_in_probe", lambda data: data["required_state_status"].pop(first))
    add("NC-16_CHANGE_ROUTE_B_DISPOSITION", "route_b_disposition_rejected", lambda data: data.__setitem__("route_b_disposition", "PASS"))
    add("NC-17_FABRICATE_MISSION_PASS", "mission_coverage_is_fail", lambda data: data.__setitem__("mission_coverage", "PASS"))
    add("NC-18_CORRUPT_NUMERIC_SNAPSHOT", "live_snapshot_fingerprint_self_consistent", lambda data: data["required_state_bend_radius_mm"].__setitem__(first, -999.0))
    require(all(item["pass"] for item in expected_records), "independent negative control failed")
    require(recorded["controls"] == expected_records, "recorded negative-control fields diverge from independent recompute")


def validate_complete_output_binding(
    evidence: dict[str, Any], gate: dict[str, Any], controls: dict[str, Any],
    by_id: dict[str, dict[str, str]], live_snapshot: dict[str, Any],
    independent: dict[str, bool], live: list[dict[str, Any]], mission: dict[str, Any],
    contract: dict[str, Any], map_rows: list[dict[str, str]], registry: dict[str, Any],
    checkpoint: dict[str, Any],
) -> None:
    """Bind every semantic output field to an independent live-input reconstruction."""
    evidence_keys = {
        "schema", "generated_local", "generator", "scope", "source_pins", "snapshot",
        "required_states", "mandatory_trajectory_segments", "deterministic_model_outputs",
        "registered_branch_certificate", "candidate_root_cause_diagnostic_not_global_proof",
        "sample_map", "route_c_state", "red_team_findings", "scope_and_nonclaims",
        "engineering_ruling", "technical_verdict", "owner_accepted", "review_status",
        "next_stage_authorized", "release_credit",
    }
    gate_keys = {
        "schema", "generated_local", "scope", "outcome", "technical_verdict", "criteria",
        "summary", "negative_controls", "branch_state", "red_team_survivor",
        "proof_scope_guard", "owner_accepted", "review_status", "next_stage_authorized",
        "release_credit", "terminal_release_candidate_generated", "self_hash_policy",
    }
    controls_keys = {"schema", "generated_local", "method", "controls", "summary", "nonclaim"}
    require(set(evidence) == evidence_keys, "evidence top-level field contract drift")
    require(set(gate) == gate_keys, "Gate top-level field contract drift")
    require(set(controls) == controls_keys, "negative-control top-level field contract drift")

    generated_local = evidence["generated_local"]
    require(gate["generated_local"] == generated_local and controls["generated_local"] == generated_local, "output timestamps diverge")
    parsed_timestamp = datetime.fromisoformat(generated_local)
    require(parsed_timestamp.utcoffset() == timedelta(hours=8), "generated_local must carry explicit UTC+08:00")

    expected_pin_list = [
        {
            "id": source_id,
            "path": by_id[source_id]["path"],
            "bytes": int(by_id[source_id]["bytes"]),
            "sha256": by_id[source_id]["sha256"],
        }
        for source_id in EXPECTED_SOURCE_HASHES
    ]
    require(evidence["source_pins"] == expected_pin_list, "complete ordered evidence source-pin table drift")

    required_ids = list(live_snapshot["required_state_ids"])
    statuses = dict(live_snapshot["required_state_status"])
    segment_ids = [item["id"] for item in contract["segments"]]
    bends = [float(item["margins"]["bend_radius_mm"]) for item in live]
    clearances = [float(item["margins"]["clearance_mm"]) for item in live]
    pinches = [float(item["margins"]["pinch_mm"]) for item in live]
    lengths = [float(item["margins"]["length_margin_mm"]) for item in live]
    joint_limits = [float(item["margins"]["joint_limit_margin_rad"]) for item in live]
    section_link5 = [float(item["sections"]["span_link5"]["min_radius_mm"]) for item in live]
    unique_q = {tuple(round(float(value), 12) for value in item["q_rad"]) for item in live}
    clearance_null_fields = live_snapshot["clearance_null_fields_by_state"]
    semantics = live_snapshot["source_semantics"]

    expected_required_states = {
        "total": len(required_ids),
        "safe": sum(value == "SAFE" for value in statuses.values()),
        "unsafe": sum(value == "UNSAFE" for value in statuses.values()),
        "unknown": sum(value == "UNKNOWN" for value in statuses.values()),
        "unique_q_count": len(unique_q),
        "ids": required_ids,
    }
    expected_trajectories = {
        "required": len(segment_ids),
        "released": int(mission["trajectory_segments_with_released_authority"]),
        "unknown": int(mission["trajectory_segments_unknown"]),
        "ids": segment_ids,
        "external_gates": dict(mission["external_trajectory_gates"]),
    }
    expected_deterministic = {
        "unit_statement": {
            "clearance": "mm", "bend_radius": "mm", "bend_margin": "mm", "pinch": "mm",
            "length_margin": "mm", "joint_limit_margin": "rad",
        },
        "uncertainty_statement": "NO_METROLOGICAL_UNCERTAINTY_AVAILABLE__DETERMINISTIC_FROZEN_MODEL_OUTPUTS_ONLY__NOT_PHYSICAL_QUALIFICATION_DATA",
        "numerical_discretization_error_bound": "NOT_ESTABLISHED",
        "model_form_uncertainty": "NOT_QUANTIFIED",
        "bend_radius_required_mm": 30.0,
        "required_state_bend_radius_mm_min": min(bends),
        "required_state_bend_radius_mm_max": max(bends),
        "required_state_bend_deficit_mm_min": 30.0 - max(bends),
        "required_state_bend_deficit_mm_max": 30.0 - min(bends),
        "section_reported_span_link5_radius_mm_values": sorted(set(section_link5)),
        "clearance_mm_range": [min(clearances), max(clearances)],
        "pinch_mm_range": [min(pinches), max(pinches)],
        "length_margin_mm_range": [min(lengths), max(lengths)],
        "joint_limit_margin_rad_range": [min(joint_limits), max(joint_limits)],
        "conformity_rule": "current frozen software contract requires every margin >= 0 and empty_comparison_sets == 0; no uncertainty guard-band or physical qualification claim is introduced here",
    }
    expected_certificate = {
        "claim_under_test": "CURRENT_FROZEN_ROUTE_B_CAN_EARN_ODR_GPT_04_WITHOUT_A_NEW_OWNER_AUTHORIZED_ECR",
        "result": "FALSIFIED_BY_CURRENT_GATE_STATE_PLUS_TERMINAL_FREEZE",
        "proof_chain": [
            "ODR-GPT-04 requires every registered mandatory state and all eight released trajectories to pass the harness and external Gates.",
            "The current registered evidence has 0/10 mandatory states SAFE, 0/8 released trajectories and Mission Coverage FAIL.",
            "The Route-B terminal freeze records reopening=NONE_PERMITTED and further_mechanical_design_time_on_route_b=NONE.",
            "Therefore the current frozen Route-B branch cannot earn ODR-GPT-04; changing the centerline, predicate or task-state authority requires a separate direct Owner ECR and a new graph version.",
        ],
        "global_q_no_go_claim": "NOT_MADE",
    }
    expected_root_cause = {
        "observation": "all registered mandatory states report the terminal bend argmin at span_link5 near 0.100123 mm versus the 30 mm frozen requirement",
        "cached_span_rigid_transform_structure": True,
        "fillet_trim_and_resample_present": True,
        "fillet_trim_global_invariance_proved": False,
        "consequence": "supports a root-cause hypothesis for the registered failures but does not prove that every q in E_HW is UNSAFE",
        "source_semantics": semantics,
        "observed_required_state_argmins": sorted(set(live_snapshot["required_state_minimum_bend_location"].values())),
        "rate_scaling_relevance_for_a_fixed_q_path": "NONE__CURRENT_STATIC_PREDICATE_CONTAINS_NO_qdot_OR_qddot_INPUT",
    }
    expected_sample_map = {
        "samples_total": len(map_rows),
        "safe": sum(row["status"] == "SAFE" for row in map_rows),
        "unsafe": sum(row["status"] == "UNSAFE" for row in map_rows),
        "unknown": sum(row["status"] == "UNKNOWN" for row in map_rows),
        "families": sorted({row["family"] for row in map_rows}),
        "scope_limit": "THREE q2-by-q3 SLICES_ONLY__NOT_A_STANDALONE_6D_EMPTY_SET_CERTIFICATE",
    }
    expected_route_c = {
        "checkpoint_b_outcome": checkpoint["checkpoint_outcome"],
        "admission_passed": checkpoint["admission"]["summary"]["pass"],
        "admission_total": checkpoint["admission"]["summary"]["conditions_total"],
        "registry_non_null": registry["summary"]["value_non_null"],
        "registry_available": registry["summary"]["status_AVAILABLE"],
        "registry_hold": registry["summary"]["status_HOLD"],
        "route_c_cad_authorized": checkpoint["admission"]["ROUTE_C_CAD_AUTHORIZED"],
    }
    expected_red_team = [
        {
            "id": "RT-HRN-01", "severity_for_current_negative_result": "NONE",
            "severity_for_future_positive_predicate": "HIGH",
            "finding": "per_joint_pinch_mm.joint6 is null in every required-state result while aggregate empty_comparison_sets remains zero",
            "disposition": "current negative result survives because bend, clearance and pinch aggregate margins are already negative; any new positive Route-C predicate must require every named field and joint comparison to be finite, otherwise UNKNOWN/ABORT",
            "affected_state_count": len(live_snapshot["joint6_pinch_null_state_ids"]),
        },
        {
            "id": "RT-HRN-02", "severity_for_current_negative_result": "NONE",
            "severity_for_physical_interpretation": "MEDIUM",
            "finding": "protected feedthrough/clamp/backshell contact zones are not exempted and may create conservative clearance or pinch false negatives",
            "disposition": "do not weaken frozen V1; a future version requires physical connector/clamp/backshell CAD and finite named contact volumes; the currently registered states remain failed independently of this possible conservatism",
        },
        {
            "id": "RT-HRN-03", "severity_for_current_negative_result": "NONE",
            "severity_for_continuous_claim": "HIGH",
            "finding": "the 75-point map has no error bound and cannot prove the unsampled six-dimensional domain; the existing exact kernel is also a frozen discretized evaluator rather than a mathematical continuum certificate",
            "disposition": "do not extrapolate the map to the unsampled 6D domain; any new Route-C positive release needs a versioned state oracle and conservative continuous-trajectory certificate",
        },
        {
            "id": "RT-HRN-04", "severity_for_global_q_claim": "HIGH",
            "severity_for_current_registered_branch_closure": "NONE",
            "finding": "final Connector(poly) geometry is fillet-trimmed and resampled; the current evidence does not prove that trim bounds preserve the span_link5 curvature minimum over all E_HW",
            "disposition": "the global-q no-go claim was removed; closure rests on the 0/10, 0/8, Mission FAIL state plus the Owner terminal freeze",
        },
        {
            "id": "RT-HRN-05", "severity_for_current_negative_result": "NONE",
            "severity_for_future_positive_predicate": "HIGH",
            "finding": "required-state per_field_clearance_mm contains null fields in every state, in addition to joint6 pinch null",
            "disposition": "the exact null-field map is machine-recorded; any future positive predicate must require every named field and joint comparison finite or return UNKNOWN/ABORT",
            "null_fields_by_state": clearance_null_fields,
        },
    ]
    expected_nonclaims = [
        "This falsifies only the ODR-GPT-04 deferment path for the current frozen Route-B centerline and predicate.",
        "It does not prove that every external harness topology is physically impossible.",
        "It does not prove that every q in E_HW is UNSAFE; fillet-trim invariance over the full domain is not established.",
        "It does not convert deterministic model output into measurement or qualification evidence.",
        "It does not resolve protected-contact semantics, joint6 coverage, trajectory authority, IK, collision, Solar keep-out, SAFE-00, or dynamic harness torque.",
        "It does not authorize Route-C CAD, a Route-B reopening, a new Route-B2, Sim13 production binding, terminal release, or flight qualification.",
    ]
    expected_ruling = {
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
    }
    expected_verdict = "ODR_GPT_04_DEFERMENT_NOT_EARNED_FOR_FROZEN_ROUTE_B__REGISTERED_MANDATORY_STATES_UNSAFE__ROUTE_B_REOPENING_PROHIBITED__ROUTE_C_REQUIRED_UNLESS_SEPARATELY_AUTHORIZED_NEW_VERSIONED_ROUTE"
    expected_sections = {
        "required_states": expected_required_states,
        "mandatory_trajectory_segments": expected_trajectories,
        "deterministic_model_outputs": expected_deterministic,
        "registered_branch_certificate": expected_certificate,
        "candidate_root_cause_diagnostic_not_global_proof": expected_root_cause,
        "sample_map": expected_sample_map,
        "route_c_state": expected_route_c,
        "red_team_findings": expected_red_team,
        "scope_and_nonclaims": expected_nonclaims,
        "engineering_ruling": expected_ruling,
    }
    for field, expected in expected_sections.items():
        require(evidence[field] == expected, f"complete evidence section drift: {field}")
    require(evidence["schema"] == "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_FALSIFIER_V1", "evidence schema drift")
    require(evidence["generator"] == "GPT mechanical chief / harness mission-envelope falsifier", "evidence generator drift")
    require(evidence["scope"] == "current hash-frozen Route-B centerline, evaluator and ODR-GPT-04 branch only", "evidence scope drift")
    require(evidence["technical_verdict"] == expected_verdict, "evidence verdict drift")
    require(
        evidence["owner_accepted"] is False
        and evidence["review_status"] == "PENDING_OWNER_REVIEW"
        and evidence["next_stage_authorized"] is False
        and evidence["release_credit"] is False,
        "evidence authority/release fields drift",
    )

    expected_criteria = [
        {"id": f"FZ-{index:02d}", "name": name, "pass": bool(value)}
        for index, (name, value) in enumerate(independent.items(), start=1)
    ]
    expected_summary = {
        "passed": sum(item["pass"] for item in expected_criteria),
        "total": len(expected_criteria),
        "failed": [item["id"] for item in expected_criteria if not item["pass"]],
    }
    expected_control_summary = {
        "passed": sum(item["pass"] for item in controls["controls"]),
        "total": len(controls["controls"]),
        "failed": [item["id"] for item in controls["controls"] if not item["pass"]],
    }
    expected_gate_without_time = {
        "schema": "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_GATE_V1",
        "scope": "integrity and current-branch no-go certification; PASS here is a PASS of the falsifier, not a harness PASS",
        "outcome": "PASS_FALSIFIER__FROZEN_ROUTE_B_ODR_GPT_04_BRANCH_CLOSED_NEGATIVE",
        "technical_verdict": expected_verdict,
        "criteria": expected_criteria,
        "summary": expected_summary,
        "negative_controls": expected_control_summary,
        "branch_state": {
            "current_frozen_route_b_rated_envelope_path": "TERMINAL_NEGATIVE_CURRENT_REGISTERED_BRANCH",
            "odr_gpt_04_deferment_earned": False,
            "mission_coverage": "FAIL",
            "route_c_required_to_continue": True,
            "route_c_cad_authorized": False,
        },
        "red_team_survivor": {
            "id": "RT-HRN-01", "current_negative_result_affected": False,
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
    require({key: value for key, value in gate.items() if key != "generated_local"} == expected_gate_without_time, "complete Gate payload drift")
    require(gate["negative_controls"] == controls["summary"] == expected_control_summary, "Gate/control summary binding drift")
    require(
        controls["schema"] == "ODR_GPT_04_FROZEN_ROUTE_B_ADVERSARIAL_CONTROLS_V1"
        and controls["method"] == "in-memory single-fault mutations against an independently enumerable fail-closed predicate"
        and controls["summary"] == expected_control_summary
        and controls["nonclaim"] == "mutation PASS proves guard sensitivity, not physical qualification",
        "negative-control payload contract drift",
    )

    expected_receipt = f"""# ODR-GPT-04 冻结 Route-B 分支证伪收据 V1

生成时间：{generated_local}

## 裁决

- 证伪器完整性：{expected_summary['passed']}/{expected_summary['total']} PASS；负控：{expected_control_summary['passed']}/{expected_control_summary['total']} PASS。
- 当前冻结 Route-B 的 ODR-GPT-04 额定任务包络分支：**已证伪**。
- 直接原因：当前注册证据为 10 个强制状态 0/10 SAFE、8 条轨迹 0/8 released、Mission Coverage FAIL，同时 Route-B 终局冻结明确 `reopening=NONE_PERMITTED`。因此当前冻结分支没有合法的继续搜索或发布路径。
- `span_link5` 在这些注册状态下的确定性模型输出约 0.100123 mm，对 30 mm 要求的最小缺口约 {expected_deterministic['required_state_bend_deficit_mm_min']:.6f} mm；它是根因诊断，不是“任意 q 均失败”的全域证明，因为最终连接器还存在构型相关圆角裁剪与重采样。
- 10 个强制状态 0/10 SAFE；8 条轨迹 0/8 released；Mission Coverage 保持 FAIL。
- 当前不再对冻结 Route-B 投入轨迹搜索、姿态重绑或限速优化算力。

## 边界

这不是“所有外置线束拓扑都不可能”的结论，也不是“所有 q 均 UNSAFE”的结论或物理资格鉴定结论。75 点地图不是六维空集证明；圆角裁剪的全域不变量尚未建立。所有数值均带 mm/rad 量纲，但没有可用的计量不确定度，故只作为冻结模型/软件合同证据。

红队还发现：10/10 强制状态的 `per_joint_pinch_mm.joint6` 均为 null；每个状态也有一个或多个 `per_field_clearance_mm` 为 null，而 V1 聚合仍记 `empty_comparison_sets=0`。它们不改变当前负结果，但任何未来正向 Route-C 谓词必须把任一必需 joint/field 的 null 判为 UNKNOWN/ABORT。

## 唯一受控前进方向

继续 Route-C 的 P01-P13 物理输入闭环，达到 Checkpoint-B 8/8 后再取得独立 CAD 授权并建立新物理路线；或者由 Owner 另行授权一个版本隔离的新中心线/新谓词 ECR。两者都不得重开、改名或美化当前冻结 Route-B。

Owner acceptance、Route-C CAD authority、next-stage authority、release credit 均保持 false。
"""
    receipt = (PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_RECEIPT_V1.md").read_text(encoding="utf-8")
    require(receipt == expected_receipt, "receipt content diverges from independently reconstructed decision")


def main() -> None:
    _, by_id = read_manifest()
    evidence = json.loads((PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_FALSIFIER_V1.json").read_text(encoding="utf-8"))
    gate = json.loads((PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_GATE_V1.json").read_text(encoding="utf-8"))
    controls = json.loads((PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_ADVERSARIAL_CONTROLS_V1.json").read_text(encoding="utf-8"))

    probe = load_input(by_id, "mandatory_state_probe")
    mission = load_input(by_id, "mission_coverage_gate")
    contract = load_input(by_id, "mission_trajectory_contract")
    envelope = load_input(by_id, "rated_envelope")
    freeze = load_input(by_id, "route_b_terminal_freeze")
    registry = load_input(by_id, "route_c_registry")
    checkpoint = load_input(by_id, "checkpoint_b")
    owner = load_input(by_id, "owner_odr_gpt_01_06")
    kernel = load_input(by_id, "route_b_geometry_kernel")
    wrapper = load_input(by_id, "exact_predicate_wrapper")
    map_rows = list(csv.DictReader(io.StringIO(load_input(by_id, "envelope_map_csv"))))
    npz_path = resolve(by_id["envelope_map_npz"]["path"])
    with np.load(npz_path, allow_pickle=False) as npz:
        npz_columns = npz["columns"].tolist()
        npz_samples = np.asarray(npz["samples"], dtype=float)
        npz_status = np.asarray(npz["status_code"], dtype=np.int8)
    expected_npz_columns = ["q1_rad", "q2_rad", "q3_rad", "q4_rad", "q5_rad", "q6_rad", "clearance_margin_mm", "bend_margin_mm", "pinch_margin_mm", "length_margin_mm", "joint_limit_margin_rad"]
    require(npz_columns == expected_npz_columns, "envelope NPZ column contract drift")
    csv_matrix = np.asarray([[float(row[column]) for column in expected_npz_columns] for row in map_rows], dtype=float)
    status_codes = {"SAFE": 1, "UNKNOWN": 0, "UNSAFE": -1}
    require(len(map_rows) == 75 and all(row["status"] == "UNSAFE" for row in map_rows), "CSV rated-envelope status contract drift")
    csv_status = np.asarray([status_codes[row["status"]] for row in map_rows], dtype=np.int8)
    require(npz_samples.shape == (75, 11) and np.array_equal(npz_samples, csv_matrix), "envelope NPZ/CSV numeric mismatch")
    require(npz_status.shape == (75,) and np.array_equal(npz_status, csv_status), "envelope NPZ/CSV row-wise status mismatch")

    directives = {item["id"]: item for item in owner["directives"]}
    require(directives["ODR-GPT-04"]["condition_evaluation"]["result"] == "NOT_SATISFIED", "Owner ODR-GPT-04 state drift")
    require(directives["ODR-GPT-04"]["recorded_effect"]["deferred_full_range_harness_hold_allowed_now"] is False, "ODR-GPT-04 deferment silently enabled")
    require(directives["ODR-GPT-04"]["recorded_effect"]["gate_a_release_granted"] is False, "ODR-GPT-04 Gate-A authority silently enabled")
    require(directives["ODR-GPT-04"]["recorded_effect"]["route_c_required_to_continue"] is True, "ODR-GPT-04 Route-C continuation state drift")
    require(directives["ODR-GPT-04"]["recorded_effect"]["next_stage_authorized"] is False, "ODR-GPT-04 next-stage authority silently enabled")
    require(directives["ODR-GPT-02"]["recorded_effect"]["reopen_allowed"] is False, "Route-B reopening silently enabled")
    require(directives["ODR-GPT-02"]["recorded_effect"]["disposition"] == "REJECTED_BY_EXACT_KINEMATIC_SWEEP", "Route-B disposition drift")
    require(directives["ODR-GPT-02"]["recorded_effect"]["next_stage_authorized"] is False, "Route-B negative result gained next-stage authority")
    require(
        owner["owner_acceptance_claimed"] is False
        and owner["next_stage_authorized"] is False
        and owner["release_credit"] is False
        and owner["mechanical_release_issued"] is False
        and owner["route_c_cad_authorized"] is False,
        "direct Owner register authority/release boundary drift",
    )
    require(
        freeze["closure"]["route_b_iteration"] == "CLOSED"
        and freeze["closure"]["reopening"] == "NONE_PERMITTED"
        and freeze["closure"]["re_criteria"] == "NONE_PERMITTED"
        and freeze["closure"]["further_mechanical_design_time_on_route_b"] == "NONE",
        "terminal Route-B freeze contract drift",
    )
    require(freeze["next_stage_authorized"] is False and freeze["release_credit"] is False, "terminal freeze gained authority or release credit")

    required_ids = list(mission["required_states"])
    require(set(required_ids) == EXPECTED_STATES and len(required_ids) == 10, "live mandatory-state set drift")
    results = {item["state_id"]: item for item in probe["results"]}
    require(EXPECTED_STATES <= set(results), "live probe omits mandatory state")
    live = [results[state] for state in required_ids]
    require(all(item["status"] == "UNSAFE" for item in live), "a mandatory state is no longer UNSAFE")
    require(all(item["minimum_bend_location"] == "span_link5" for item in live), "bend argmin drift")
    require(all(float(item["margins"]["bend_radius_mm"]) < 30.0 for item in live), "bend no-go no longer holds")
    require(all(float(item["margins"]["clearance_mm"]) < 0.0 and float(item["margins"]["pinch_mm"]) < 0.0 for item in live), "independent negative margins drift")
    require(all(float(item["margins"]["length_margin_mm"]) > 0.0 for item in live), "length-margin diagnostic drift")
    require(all(item["sections"]["span_link5"]["min_radius_mm"] == 0.1 for item in live), "cached span_link5 section radius drift")
    require(all(item["per_joint_pinch_mm"].get("joint6") is None for item in live), "joint6 null-risk state changed; evidence must be regenerated")
    require(all(int(item["empty_comparison_sets"]) == 0 for item in live), "empty-comparison-set diagnostic drift")

    require(set(item["id"] for item in contract["segments"]) == EXPECTED_SEGMENTS and len(contract["segments"]) == 8, "live trajectory set drift")
    require(mission["trajectory_segments_with_released_authority"] == 0 and mission["trajectory_segments_unknown"] == 8, "trajectory authority state drift")
    require(mission["mission_coverage"] == "FAIL", "Mission Coverage state drift")
    require(all(str(value).startswith("UNKNOWN") for value in mission["external_trajectory_gates"].values()), "external trajectory Gate state drift")
    require(envelope["E_HRN"]["sample_counts"] == {"SAFE": 0, "UNSAFE": 75, "UNKNOWN": 0}, "rated-envelope map summary drift")
    require(envelope["E_HRN"]["conservative_box"] is None and envelope["E_OP"]["status"] == "EMPTY_NOT_RELEASED", "rated-envelope release state drift")
    require(registry["summary"]["value_non_null"] == 0 and registry["summary"]["status_AVAILABLE"] == 0 and registry["summary"]["status_HOLD"] == 13, "Route-C registry state drift")
    require(checkpoint["checkpoint_outcome"] == "HOLD" and checkpoint["admission"]["summary"]["pass"] == 2 and checkpoint["admission"]["summary"]["conditions_total"] == 8, "Checkpoint-B state drift")
    require(checkpoint["admission"]["ROUTE_C_CAD_AUTHORIZED"] is False, "Route-C CAD authority drift")

    live_snapshot = build_live_snapshot(probe, mission, contract, map_rows, freeze, registry, checkpoint, owner, kernel, wrapper)
    require(evidence["snapshot"] == live_snapshot, "embedded snapshot diverges from independent live-input reconstruction")
    semantics = live_snapshot["source_semantics"]
    require(all(value for key, value in semantics.items() if key != "fillet_trim_global_invariance_proved"), "recorded source diagnostic semantics incomplete")
    require(semantics["fillet_trim_global_invariance_proved"] is False and live_snapshot["global_q_no_go_claim_made"] is False, "global-q scope guard lost")
    require("self._derive_spans()" in kernel, "span derivation source guard missing")
    require('sp_pts, sp_L, sp_R, sp_dm, sp_st = self.spans[child]' in kernel, "cached child span source guard missing")
    require('sp_S = sp_pts @ TS[child][:3, :3].T + TS[child][:3, 3]' in kernel, "rigid transform source guard missing")
    require('required_bend_radius_mm: float = 30.0' in wrapper, "30 mm predicate source guard missing")
    require("trims[ni - 1][1] = f[3]" in kernel and "pts, L, Rc = con.sample(t0, t1)" in kernel, "fillet-trim scope caveat source guard missing")
    check_rigid_invariance()

    independent = recompute_checks(live_snapshot)
    require(all(independent.values()), f"independent evidence check failed: {[key for key, value in independent.items() if not value]}")
    require([item["name"] for item in gate["criteria"]] == list(independent), "Gate criterion order/name drift")
    require(all(item["pass"] for item in gate["criteria"]), "Gate criterion recorded false")
    require(gate["summary"] == {"passed": 18, "total": 18, "failed": []}, "Gate summary drift")
    require(gate["outcome"] == "PASS_FALSIFIER__FROZEN_ROUTE_B_ODR_GPT_04_BRANCH_CLOSED_NEGATIVE", "Gate outcome drift")
    require(gate["technical_verdict"] == "ODR_GPT_04_DEFERMENT_NOT_EARNED_FOR_FROZEN_ROUTE_B__REGISTERED_MANDATORY_STATES_UNSAFE__ROUTE_B_REOPENING_PROHIBITED__ROUTE_C_REQUIRED_UNLESS_SEPARATELY_AUTHORIZED_NEW_VERSIONED_ROUTE", "Gate technical verdict drift")
    require(evidence["technical_verdict"] == gate["technical_verdict"], "evidence/Gate technical verdict mismatch")
    require(gate["branch_state"]["current_frozen_route_b_rated_envelope_path"] == "TERMINAL_NEGATIVE_CURRENT_REGISTERED_BRANCH", "Gate registered-branch state drift")
    require(gate["branch_state"]["odr_gpt_04_deferment_earned"] is False, "Gate claims ODR-GPT-04 deferment")
    require(gate["branch_state"]["route_c_cad_authorized"] is False, "Gate claims Route-C CAD authority")
    require(gate["owner_accepted"] is False and gate["next_stage_authorized"] is False and gate["release_credit"] is False, "authority guard drift")
    require("NO_METROLOGICAL_UNCERTAINTY_AVAILABLE" in evidence["deterministic_model_outputs"]["uncertainty_statement"], "uncertainty limitation missing")
    require(evidence["deterministic_model_outputs"]["numerical_discretization_error_bound"] == "NOT_ESTABLISHED", "numerical discretization limitation missing")
    require(evidence["deterministic_model_outputs"]["model_form_uncertainty"] == "NOT_QUANTIFIED", "model-form uncertainty limitation missing")
    require(any("does not prove that every external harness topology" in text for text in evidence["scope_and_nonclaims"]), "physical-impossibility nonclaim missing")
    require(any("does not prove that every q in E_HW" in text for text in evidence["scope_and_nonclaims"]), "global-q nonclaim missing")
    require(evidence["red_team_findings"][0]["id"] == "RT-HRN-01" and evidence["red_team_findings"][0]["affected_state_count"] == 10, "joint6 red-team finding missing")
    findings = {item["id"]: item for item in evidence["red_team_findings"]}
    require({"RT-HRN-01", "RT-HRN-02", "RT-HRN-03", "RT-HRN-04", "RT-HRN-05"} == set(findings), "red-team finding set drift")
    require(findings["RT-HRN-04"]["severity_for_global_q_claim"] == "HIGH", "fillet-trim proof gap not retained")
    require(set(findings["RT-HRN-05"]["null_fields_by_state"]) == EXPECTED_STATES, "clearance null-field map incomplete")

    live_bends = [float(item["margins"]["bend_radius_mm"]) for item in live]
    live_clear = [float(item["margins"]["clearance_mm"]) for item in live]
    live_pinch = [float(item["margins"]["pinch_mm"]) for item in live]
    live_length = [float(item["margins"]["length_margin_mm"]) for item in live]
    live_joint = [float(item["margins"]["joint_limit_margin_rad"]) for item in live]
    derived = evidence["deterministic_model_outputs"]
    require(derived["required_state_bend_radius_mm_min"] == min(live_bends) and derived["required_state_bend_radius_mm_max"] == max(live_bends), "bend derived statistics drift")
    require(derived["clearance_mm_range"] == [min(live_clear), max(live_clear)], "clearance derived statistics drift")
    require(derived["pinch_mm_range"] == [min(live_pinch), max(live_pinch)], "pinch derived statistics drift")
    require(derived["length_margin_mm_range"] == [min(live_length), max(live_length)], "length derived statistics drift")
    require(derived["joint_limit_margin_rad_range"] == [min(live_joint), max(live_joint)], "joint-limit derived statistics drift")

    evidence_pin_map = {item["id"]: item for item in evidence["source_pins"]}
    manifest_inputs = {source_id: by_id[source_id] for source_id in EXPECTED_SOURCE_HASHES}
    require(set(evidence_pin_map) == set(manifest_inputs), "embedded evidence source-pin set drift")
    for source_id, item in evidence_pin_map.items():
        require(item["path"] == manifest_inputs[source_id]["path"] and str(item["bytes"]) == manifest_inputs[source_id]["bytes"] and item["sha256"] == manifest_inputs[source_id]["sha256"], f"embedded evidence pin drift: {source_id}")

    validate_negative_controls(live_snapshot, controls)
    require(controls["summary"] == {"passed": 18, "total": 18, "failed": []}, "negative-control summary drift")
    validate_complete_output_binding(
        evidence, gate, controls, by_id, live_snapshot, independent, live, mission,
        contract, map_rows, registry, checkpoint,
    )
    receipt = (PACKAGE / "ODR_GPT_04_FROZEN_ROUTE_B_BRANCH_RECEIPT_V1.md").read_text(encoding="utf-8")
    for forbidden in ("Q_INVARIANT_BEND_FAILURE", "任意关节构型只对其施加刚体 FK 变换，不能改变曲率", "全域否定只针对当前冻结内核的 q-不变量"):
        require(forbidden not in receipt, f"receipt regressed to forbidden global-q wording: {forbidden}")
    require("不是“所有 q 均 UNSAFE”" in receipt and "reopening=NONE_PERMITTED" in receipt, "receipt proof-scope/authority wording missing")

    print("ODR-GPT-04 frozen Route-B falsifier validation: PASS")
    print("source hashes: 24/24")
    print("mandatory states: 10/10 UNSAFE in the registered branch; no global-q claim")
    print("mandatory trajectories: 0/8 released; Mission Coverage FAIL")
    print("adversarial controls: 18/18 PASS")
    print("authority: Owner acceptance=false; Route-C CAD=false; next stage=false; release credit=false")


if __name__ == "__main__":
    main()
