from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


MODULE = Path(__file__).resolve().parents[1]


def _json(relative: str):
    return json.loads((MODULE / relative).read_text(encoding="utf-8"))


def _yaml(relative: str):
    return yaml.safe_load((MODULE / relative).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_required_first_batch_is_present():
    required = (
        "00_authority/CURRENT_GATE_SNAPSHOT.json",
        "00_authority/AUTHORITY_RESOLUTION_REPORT.md",
        "00_authority/BASELINE_HASH_MANIFEST.csv",
        "00_authority/CONFLICT_LEDGER.csv",
        "00_authority/NEGATIVE_RESULT_REGISTER.csv",
        "00_authority/PREBIND_AUTHORITY.json",
        "01_plant/ACCEPTED_PLANT.yaml",
        "01_plant/PREBIND_SENSITIVITY_PLANT.yaml",
        "01_plant/UNIFIED_R2_PLANT.yaml",
        "01_plant/PARAMETER_PROVENANCE.csv",
        "02_interfaces/FRAME_CONTRACT.yaml",
        "02_interfaces/STATE_HANDOFF_SCHEMA.json",
        "02_interfaces/SOLVER_MAPPING.yaml",
        "03_scenarios/SCENARIO_MATRIX.csv",
        "03_scenarios/CAPTURE_FSM.yaml",
        "03_scenarios/NEGATIVE_CASE_REGISTER.csv",
        "05_control/CONTROL_ARCHITECTURE.md",
        "05_control/SAFE_00_INTERFACE.md",
        "10_verification/MOMENTUM_LEDGER.json",
        "10_verification/PB_G0_GATE.json",
        "10_verification/PB_G1_GATE.json",
        "13_reports/CURRENT_STATE.md",
        "13_reports/CURRENT_STATE_DELTA.md",
        "13_reports/PREBIND_PHASE0_ACCEPTANCE_REPORT.md",
    )
    assert all((MODULE / relative).is_file() for relative in required)


def test_authority_hashes_and_route_c_exclusion_are_fail_closed():
    with (MODULE / "00_authority/BASELINE_HASH_MANIFEST.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        rows = {row["asset_id"]: row for row in csv.DictReader(stream)}
    assert rows["accepted_b601_urdf"]["sha256"] == (
        "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
    )
    assert rows["unified_r2_urdf"]["sha256"] == (
        "D84AA23CE98A2A9C697B1F32E433C01C3F0AE3BD0B5C56EF9A218DD88911CBDA"
    )
    assert rows["physical_dynamics_bridge"]["sha256"] == (
        "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C"
    )
    assert rows["route_c_mass_delta_candidate_v2"]["consumed_by_pb00"] == "false"
    plant = _yaml("01_plant/ACCEPTED_PLANT.yaml")
    assert plant["route_c"]["included"] is False
    assert plant["route_c"]["mass_delta_consumed"] is False


def test_pb00_conservation_convergence_and_replay_pass_only_as_diagnostic():
    ledger = _json("10_verification/MOMENTUM_LEDGER.json")
    assert ledger["classification"].startswith("LIMITED_DIAGNOSTIC")
    assert ledger["technical_characterization"] == "PASS"
    assert all(ledger["checks"].values())
    assert ledger["metrics"]["relative_energy_drift_max"] < 2.0e-8
    assert ledger["metrics"]["linear_momentum_residual_max_Ns"] < 2.0e-13
    assert ledger["metrics"]["angular_momentum_residual_max_Nms"] < 2.0e-13
    assert ledger["metrics"]["fine_history_sha256"] == ledger["metrics"]["replay_history_sha256"]
    assert ledger["formal_performance_credit"] is False
    assert ledger["next_stage_authorized"] is False


def test_timeseries_keeps_rotational_and_prismatic_units_separate():
    document = _json("10_verification/PB00_TIMESERIES.json")
    assert len(document["records"]) == 21
    assert document["units"]["revolute_q"] == "rad"
    assert document["units"]["prismatic_q"] == "m"
    for row in document["records"]:
        assert len(row["q_revolute_rad"]) == 6
        assert len(row["q_prismatic_m"]) == 2
        assert len(row["qdot_revolute_rad_s"]) == 6
        assert len(row["qdot_prismatic_m_s"]) == 2
        assert abs(sum(value * value for value in row["base_quaternion_body_to_inertial_wxyz"]) - 1.0) < 1.0e-12


def test_initial_generalized_state_is_inside_accepted_joint_limits():
    ledger = _json("10_verification/MOMENTUM_LEDGER.json")
    q = ledger["stimulus"]["initial_q_revolute_rad"]
    limits = [(-2.8, 2.8), (-3.14, 0.0), (-3.14, 0.0), (-1.87, 1.57), (-1.57, 1.57), (-3.14, 3.14)]
    assert all(lower <= value <= upper for value, (lower, upper) in zip(q, limits))
    assert all(0.0 <= value <= 0.0715 for value in ledger["stimulus"]["initial_q_prismatic_m"])


def test_pb_g0_and_pb_g1_remain_hold_even_when_pb00_characterization_passes():
    g0 = _json("10_verification/PB_G0_GATE.json")
    g1 = _json("10_verification/PB_G1_GATE.json")
    pb00 = _json("10_verification/PB00_CHARACTERIZATION_GATE.json")
    assert "HOLD" in g0["verdict"]
    assert g0["next_stage_authorized"] is False
    assert "HOLD_NOT_AUTHORIZED_BY_PB_G0" in g1["verdict"]
    assert g1["next_stage_authorized"] is False
    assert pb00["technical_characterization"] == "PASS"
    assert pb00["release_credit"] is False


def test_state_handoff_schema_is_valid_and_keeps_safe_layers_distinct():
    schema = _json("02_interfaces/STATE_HANDOFF_SCHEMA.json")
    Draft202012Validator.check_schema(schema)
    safe = schema["properties"]["safe00"]["properties"]
    assert safe["physical_state"]["enum"] == ["SAFE", "UNSAFE", "UNKNOWN"]
    assert safe["decision"]["enum"] == ["ALLOW", "MODIFY", "WAIT", "BACKOFF", "ABORT"]
    assert any("UNKNOWN" in rule and "ALLOW" in rule for rule in schema["x_fail_closed_rules"])


def test_output_manifest_hashes_are_raw_byte_reproducibility_receipts():
    manifest = _json("10_verification/PB00_RUN_MANIFEST.json")
    assert manifest["seed"] == 260826
    assert manifest["next_stage_authorized"] is False
    assert manifest["release_credit"] is False
    checked = 0
    for item in manifest["outputs"]:
        path = MODULE / item["path"]
        assert path.is_file()
        assert item["hash_mode"] == "RAW_BYTES_SHA256"
        assert _sha256(path) == item["sha256"]
        checked += 1
    assert checked >= 25


def test_dirty_inventory_never_marks_mechanical_assets_delete_safe():
    with (MODULE / "00_authority/WORKTREE_DIRTY_ITEM_INVENTORY.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) > 9000
    for row in rows:
        if row["path"].startswith("20_engineering/"):
            assert row["recommended_action"] != "DELETE_SAFE"
    receipt = _json("00_authority/DELETION_BATCH_01_RECEIPT.json")
    assert receipt["total_files"] == 164
    assert receipt["mechanical_assets_touched"] is False
    assert receipt["unique_negative_evidence_deleted"] is False
