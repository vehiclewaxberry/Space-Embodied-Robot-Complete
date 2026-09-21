from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parent.parent
ROUTE = PACKAGE / "08_route_c"
WORKSPACE = PACKAGE.parents[2]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


checks: list[dict] = []


def check(check_id: str, condition: bool, evidence) -> None:
    checks.append({"id": check_id, "pass": bool(condition), "evidence": evidence})


primary = [
    ROUTE / "ROUTE_C_PRELIMINARY_DESIGN_CONTRACT_V1.json",
    ROUTE / "ROUTE_C_OWNER_DECISION_REQUEST_ODR42_V1.yaml",
    ROUTE / "ROUTE_C_CONCEPT_TRADE_V1.csv",
    ROUTE / "ROUTE_C_CAD_BRIEF_V1.md",
    ROUTE / "ROUTE_C_VERIFICATION_MATRIX_V1.csv",
    ROUTE / "ROUTE_C_CAD_ENTRY_GATE_V1.json",
]

for path in primary:
    check(f"FILE_{path.stem}_EXISTS", path.is_file() and path.stat().st_size > 0, rel(path))

contract = load_json(primary[0])
owner_text = primary[1].read_text(encoding="utf-8")
gate = load_json(primary[5])
terminal_path = PACKAGE / "07_release" / "B601_HARNESS_TERMINAL_GATE_V1.json"
mission_path = PACKAGE / "04_mission" / "B601_HARNESS_MISSION_COVERAGE_GATE.json"
probe_path = PACKAGE / "02_exact_predicate" / "CURRENT_ROUTE_KEY_STATE_PROBE_V1.json"
envelope_csv_path = PACKAGE / "03_envelope" / "B601_HARNESS_ENVELOPE_MAP_V1.csv"
trigger_path = ROUTE / "ECR_HARNESS_FULL_RANGE_01.yaml"
terminal = load_json(terminal_path)
mission = load_json(mission_path)
probe = load_json(probe_path)
trigger_text = trigger_path.read_text(encoding="utf-8")
with envelope_csv_path.open("r", encoding="utf-8", newline="") as stream:
    envelope_rows = list(csv.DictReader(stream))

urdf = WORKSPACE / contract["immutable_assets"]["accepted_urdf"]["path"]
solar = WORKSPACE / contract["immutable_assets"]["solar_r2_candidate_step"]["path"]
check("URDF_HASH_MATCH", sha256(urdf) == contract["immutable_assets"]["accepted_urdf"]["sha256"], sha256(urdf))
check("SOLAR_R2_HASH_MATCH", sha256(solar) == contract["immutable_assets"]["solar_r2_candidate_step"]["sha256"], sha256(solar))
check("URDF_IMMUTABLE", contract["immutable_assets"]["accepted_urdf"]["change_allowed"] is False, "change_allowed=false")
check("SOLAR_R2_IMMUTABLE", contract["immutable_assets"]["solar_r2_candidate_step"]["change_allowed"] is False, "change_allowed=false")

check("ROUTE_B_REJECTED", terminal.get("route_b") == "REJECTED", terminal.get("route_b"))
check("ROUTE_C_TRIGGERED", terminal.get("route_c") == "TRIGGERED", terminal.get("route_c"))
check("TERMINAL_NOT_RELEASED", terminal.get("mechanical_design") == "NOT_RELEASED", terminal.get("mechanical_design"))
check("TERMINAL_NEXT_FALSE", terminal.get("next_stage_authorized") is False, terminal.get("next_stage_authorized"))
check("TRIGGER_PENDING_AUTH", "TRIGGERED_PENDING_DETAILED_DESIGN_AUTHORIZATION" in trigger_text, "ECR pending authorization")
check("TRIGGER_NEXT_FALSE", "next_stage_authorized: false" in trigger_text, "ECR next_stage_authorized=false")
envelope_status_key = "status" if envelope_rows and "status" in envelope_rows[0] else "harness_status"
envelope_statuses = [row.get(envelope_status_key) for row in envelope_rows]
check("ENVELOPE_75_UNSAFE", len(envelope_rows) == 75 and envelope_statuses.count("UNSAFE") == 75 and envelope_statuses.count("SAFE") == 0, {"rows": len(envelope_rows), "unsafe": envelope_statuses.count("UNSAFE"), "safe": envelope_statuses.count("SAFE"), "status_column": envelope_status_key})
check("MANDATORY_10_UNSAFE", probe.get("mandatory_states_total") == 10 and probe.get("mandatory_states_unsafe") == 10 and probe.get("mandatory_states_safe") == 0, {k: probe.get(k) for k in ("mandatory_states_total", "mandatory_states_safe", "mandatory_states_unsafe")})
check("MISSION_0_OF_8", mission.get("required_trajectory_segments") == 8 and mission.get("trajectory_segments_with_released_authority") == 0 and mission.get("trajectory_segments_unknown") == 8, {k: mission.get(k) for k in ("required_trajectory_segments", "trajectory_segments_with_released_authority", "trajectory_segments_unknown")})
check("MISSION_FAIL", mission.get("mission_coverage") == "FAIL" and mission.get("next_stage_authorized") is False, {"mission_coverage": mission.get("mission_coverage"), "next_stage_authorized": mission.get("next_stage_authorized")})

check("CONTRACT_PRELIMINARY", contract.get("status") == "PRELIMINARY_CONTRACT__DETAILED_DESIGN_NOT_AUTHORIZED", contract.get("status"))
check("CONTRACT_NEXT_FALSE", contract.get("next_stage_authorized") is False, contract.get("next_stage_authorized"))
check("PROPOSAL_NOT_RELEASE", "NOT_RELEASED" in contract["proposed_architecture"]["selection_status"], contract["proposed_architecture"]["selection_status"])
check("ALL_SIX_JOINTS_DISPOSED", [x["joint"] for x in contract["proposed_architecture"]["joint_dispositions"]] == ["J1", "J2", "J3", "J4", "J5", "J6"], [x["joint"] for x in contract["proposed_architecture"]["joint_dispositions"]])
check("SPLIT_PACK_TRADE_ONLY", contract["proposed_architecture"]["split_power_data_option"]["status"] == "TRADE_ONLY__NOT_SELECTED", contract["proposed_architecture"]["split_power_data_option"]["status"])
seed = contract["route_b_seed_quarantine"]
check("SEED_OD_10_PROVISIONAL", seed["bundle_outer_diameter_mm"]["value"] == 10.0 and seed["bundle_outer_diameter_mm"]["project_authority"] is False, seed["bundle_outer_diameter_mm"])
check("SEED_BEND_30_PROVISIONAL", seed["terminal_bend_radius_mm"]["value"] == 30.0 and seed["terminal_bend_radius_mm"]["project_authority"] is False, seed["terminal_bend_radius_mm"])
check("SEED_LENGTH_4001_PROVISIONAL", seed["cut_length_mm"]["value"] == 4001.158 and seed["cut_length_mm"]["project_authority"] is False, seed["cut_length_mm"])
check("ROUTE_B_MASS_FORBIDDEN", seed["route_b_diagnostic_mass_kg"]["status"].startswith("FORBIDDEN_TO_INHERIT") and seed["route_b_diagnostic_mass_kg"]["project_authority"] is False, seed["route_b_diagnostic_mass_kg"])
check("METHOD_SOURCES_FOUR", len(contract["official_method_sources"]) == 4, [x["id"] for x in contract["official_method_sources"]])
check("METHOD_SOURCES_NOT_DIMENSION_AUTHORITY", all("authority" in x["forbidden_use"] for x in contract["official_method_sources"]), [x["forbidden_use"] for x in contract["official_method_sources"]])
check("C0_C7_SEQUENCE", [x["stage"] for x in contract["first_pass_closure_sequence"]] == [f"C{i}" for i in range(8)], [x["stage"] for x in contract["first_pass_closure_sequence"]])
check("SEQUENCE_FAIL_CLOSED", all(x.get("fail_closed_rollback") for x in contract["first_pass_closure_sequence"]), "8/8 rollback clauses")
check("START_GATE_TWO_INPUT_CLASSES", len(contract["gating_layers"]["detailed_design_start"]["required"]) == 2, contract["gating_layers"]["detailed_design_start"]["required"])
check("TRAJECTORY_NOT_PRE_C2_BLOCKER", "8/8 released trajectories" in contract["gating_layers"]["detailed_design_start"]["explicitly_not_required_before_C2"], contract["gating_layers"]["detailed_design_start"]["explicitly_not_required_before_C2"])

check("OWNER_REQUEST_NOT_AUTH_RECORD", "record_type: APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD" in owner_text, "request-only record")
check("OWNER_PENDING", "owner_decision: PENDING" in owner_text, "PENDING")
check("OWNER_NEXT_FALSE", "next_stage_authorized: false" in owner_text, "false")
check("OWNER_OPTIONS_EXPLICIT", all(option in owner_text for option in ("APPROVE_BOUNDED_DETAILED_DESIGN", "REVISE_SCOPE_AND_RESUBMIT", "REJECT")), "three disposition options")
check("OWNER_PRESERVES_FROZEN_ASSETS", "modification: FORBIDDEN" in owner_text and owner_text.count("modification: FORBIDDEN") == 2, "URDF and Solar R2")

check("CAD_GATE_HOLD", gate.get("gate") == "HOLD", gate.get("gate"))
check("CAD_GATE_NEXT_FALSE", gate.get("next_stage_authorized") is False, gate.get("next_stage_authorized"))
check("CAD_START_BLOCKERS", gate.get("detailed_design_start_blockers") == ["RC-CEG-01", "RC-CEG-03"], gate.get("detailed_design_start_blockers"))
check("DOWNSTREAM_BLOCKERS_SEPARATE", gate.get("parallel_and_downstream_release_blockers") == ["RC-CEG-02", "RC-CEG-04", "RC-CEG-08"], gate.get("parallel_and_downstream_release_blockers"))
check("NO_CAD_ARTIFACTS_DECLARED", gate.get("cad_artifacts_created_by_this_package") == 0, gate.get("cad_artifacts_created_by_this_package"))

with primary[2].open("r", encoding="utf-8", newline="") as stream:
    trade_rows = list(csv.DictReader(stream))
with primary[4].open("r", encoding="utf-8", newline="") as stream:
    verification_rows = list(csv.DictReader(stream))
check("TRADE_HAS_FOUR_CONCEPTS", len(trade_rows) == 4, len(trade_rows))
check("TRADE_SINGLE_PROPOSAL", sum(row["status"] == "PROPOSED_FOR_ODR42_NOT_SELECTED" for row in trade_rows) == 1, [row["status"] for row in trade_rows])
check("VERIFICATION_ROWS_17", len(verification_rows) == 17, len(verification_rows))
check("VERIFICATION_NO_PASS_CLAIMS", all(row["current_state"] not in {"PASS", "RELEASED"} for row in verification_rows), sorted({row["current_state"] for row in verification_rows}))
check("VERIFICATION_GATE_LAYERS", {row["gate_layer"] for row in verification_rows} == {"DETAILED_DESIGN_START", "C2_DESIGN", "DOWNSTREAM_RELEASE"}, sorted({row["gate_layer"] for row in verification_rows}))
c2_rows = [row for row in verification_rows if row["gate_layer"] == "C2_DESIGN"]
c2_release_leak_terms = ("trajectory", "positive coupled", "all samples safe")
check(
    "C2_ROWS_HAVE_NO_C3_C4_RELEASE_LAYER_LEAK",
    all(
        not any(
            term in " ".join(
                (row["method"], row["entry_evidence"], row["exit_criterion"])
            ).lower()
            for term in c2_release_leak_terms
        )
        for row in c2_rows
    ),
    {"c2_rows": [row["verification_id"] for row in c2_rows], "forbidden_terms": c2_release_leak_terms},
)

geometry_suffixes = {".step", ".stp", ".stl", ".glb", ".3mf", ".fcstd"}
geometry = [rel(path) for path in ROUTE.rglob("*") if path.is_file() and path.suffix.lower() in geometry_suffixes]
check("NO_GEOMETRY_CREATED_IN_ROUTE_C", not geometry, geometry)

source_bindings = [trigger_path, terminal_path, mission_path, probe_path, envelope_csv_path, urdf, solar]
manifest = {
    "schema": "ROUTE_C_PRELIMINARY_OUTPUT_MANIFEST_V1",
    "generated_local": contract["generated_local"],
    "generated_clock_source": "ROUTE_C_PRELIMINARY_DESIGN_CONTRACT_V1.generated_local",
    "scope": "authorization-front engineering package; no geometry and no release authority",
    "artifacts": [{"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size} for path in primary],
    "source_bindings": [{"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size} for path in source_bindings],
    "validator": {"path": rel(SCRIPT), "sha256": sha256(SCRIPT), "bytes": SCRIPT.stat().st_size},
    "artifact_count": len(primary),
    "geometry_artifact_count": 0,
    "owner_decision": "PENDING",
    "cad_entry_gate": "HOLD",
    "next_stage_authorized": False,
}
manifest_path = ROUTE / "ROUTE_C_PRELIMINARY_OUTPUT_MANIFEST_V1.json"
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
manifest_loaded = load_json(manifest_path)
check("MANIFEST_ARTIFACT_COUNT", manifest_loaded["artifact_count"] == len(primary), manifest_loaded["artifact_count"])
check("MANIFEST_ALL_HASHES_MATCH", all(sha256(WORKSPACE / item["path"]) == item["sha256"] for item in manifest_loaded["artifacts"] + manifest_loaded["source_bindings"]), "artifact and source hashes")
check("MANIFEST_GATE_HOLD", manifest_loaded["cad_entry_gate"] == "HOLD" and manifest_loaded["next_stage_authorized"] is False, {"gate": manifest_loaded["cad_entry_gate"], "next": manifest_loaded["next_stage_authorized"]})

failed = [item["id"] for item in checks if not item["pass"]]
report = {
    "schema": "ROUTE_C_PRELIMINARY_VALIDATION_V1",
    "generated_local": contract["generated_local"],
    "generated_clock_source": "ROUTE_C_PRELIMINARY_DESIGN_CONTRACT_V1.generated_local",
    "verdict": "PASS_PACKAGE_INTEGRITY__CAD_ENTRY_REMAINS_HOLD" if not failed else "FAIL_PACKAGE_INTEGRITY",
    "package_integrity_pass": not failed,
    "cad_entry_gate": "HOLD",
    "owner_decision": "PENDING",
    "next_stage_authorized": False,
    "checks_passed": len(checks) - len(failed),
    "checks_total": len(checks),
    "failed_checks": failed,
    "checks": checks,
    "manifest": {"path": rel(manifest_path), "sha256": sha256(manifest_path)},
    "note": "Integrity PASS confirms only that the authorization-front package is internally consistent. It does not authorize CAD, release a harness, or upgrade any scientific/mechanical gate."
}
report_path = ROUTE / "ROUTE_C_PRELIMINARY_VALIDATION_V1.json"
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"verdict": report["verdict"], "checks": f"{report['checks_passed']}/{report['checks_total']}", "failed": failed, "manifest_sha256": sha256(manifest_path), "validation_sha256": sha256(report_path)}, indent=2))
raise SystemExit(0 if not failed else 1)
