from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "30_simulation" / "e15_core_coverage"
RESULTS = PACKAGE / "results/core_evidence_72cases.csv"
CONFIG = PACKAGE / "config/threshold_registry_core_v1.yaml"
BUILDER = PACKAGE / "src/build_core_coverage.py"
GATE = PACKAGE / "results/core_gate_check.json"

STATES = {
    "CORE_SAFE_FLEX_VALIDATED",
    "CORE_SAFE_FLEX_UNKNOWN",
    "CORE_UNSAFE",
    "GEOMETRY_INVALID",
    "EVIDENCE_MISSING",
}


def _rows() -> list[dict[str, str]]:
    with RESULTS.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def test_cardinality_states_and_unique_binding() -> None:
    rows = _rows()
    assert len(rows) == 72
    assert {int(row["grid_index"]) for row in rows} == set(range(72))
    assert len({row["case_id"] for row in rows}) == 72
    assert {row["core_state"] for row in rows} <= STATES
    assert sum(row["core_state"] == "EVIDENCE_MISSING" for row in rows) == 0
    assert all(row["primary_binding_cause"] and ";" not in row["primary_binding_cause"] for row in rows)
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    assert gate["gate"] == "P0_A_CORE_COVERAGE_PASS"
    assert set(gate["state_counts"]) == STATES
    assert gate["evidence_missing_count"] == 0
    assert gate["unique_primary_binding_per_row"] is True


def test_geometry_invalid_is_explicit_not_applicable() -> None:
    invalid = [row for row in _rows() if row["core_state"] == "GEOMETRY_INVALID"]
    assert len(invalid) == 66
    assert all(row["ik_feasible"] == "0" for row in invalid)
    assert all(row["primary_binding_cause"] == "IK_UNREACHABLE" for row in invalid)
    assert all(row["not_applicable_reason"] == "GEOMETRY_CHAIN_FAILED_AT_IK" for row in invalid)
    assert all(row["evidence_status"] == "COMPLETE_NOT_APPLICABLE_AFTER_IK" for row in invalid)
    assert all(row["core_chain_applicable"] == "0" for row in invalid)
    assert all(row["geometry_stage_status"] == "FAILED_IK_UNREACHABLE" for row in invalid)
    downstream_statuses = [
        "collision_stage_status", "base_reaction_stage_status",
        "capture_impulse_stage_status", "post_capture_stage_status",
        "actuator_budget_stage_status", "flex_stage_status",
    ]
    assert all(row["downstream_numeric_semantics"] == "NOT_APPLICABLE_NOT_MISSING" for row in invalid)
    assert all(all(row[name] == "NOT_RUN_DUE_TO_UPSTREAM_IK" for name in downstream_statuses) for row in invalid)
    assert all(row["capture_impulse_linear_norm_Ns"] == "" for row in invalid)
    assert all(row["wheel_momentum_required_Nms"] == "" for row in invalid)
    assert all(row["thruster_impulse_required_Ns"] == "" for row in invalid)
    assert all(row["propellant_required_g"] == "" for row in invalid)


def test_numeric_chain_and_derived_budget_closure() -> None:
    rows = [row for row in _rows() if row["core_chain_applicable"] == "1"]
    assert len(rows) == 6
    required = [
        "collision_margin_m", "jacobian_condition", "base_attitude_change_deg",
        "base_angular_velocity_metric_dps", "capture_impulse_linear_norm_Ns",
        "capture_impulse_angular_norm_Nms", "post_capture_angular_velocity_dps",
        "wheel_momentum_required_Nms", "thruster_impulse_required_Ns",
        "propellant_required_g",
    ]
    for row in rows:
        assert all(math.isfinite(float(row[name])) for name in required)
        linear = [float(row[f"capture_impulse_linear_{axis}_Ns"]) for axis in "xyz"]
        angular = [float(row[f"capture_impulse_angular_{axis}_Nms"]) for axis in "xyz"]
        assert math.isclose(math.sqrt(sum(v * v for v in linear)), float(row["capture_impulse_linear_norm_Ns"]), rel_tol=1e-12)
        assert math.isclose(math.sqrt(sum(v * v for v in angular)), float(row["capture_impulse_angular_norm_Nms"]), rel_tol=1e-12)
        h = float(row["wheel_momentum_required_Nms"])
        j = float(row["thruster_impulse_required_Ns"])
        m = float(row["propellant_required_g"])
        assert math.isclose(j, h / 0.17, rel_tol=1e-12)
        assert math.isclose(m, 1000.0 * j / (60.0 * 9.80665), rel_tol=1e-12)
        assert row["core_state"] == "CORE_UNSAFE"
        assert row["primary_binding_cause"] == "POST_CAPTURE_RATE_EXCEEDS_LIMIT"


def test_thresholds_not_widened_and_source_bound() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    t = cfg["thresholds"]
    assert t["collision_margin_min_m"]["value"] == 0.02
    assert t["joint_limit_margin_min_rad"]["value"] == 0.05
    assert t["condition_number_max"]["value"] == 1.0e4
    assert t["base_attitude_change_max_deg"]["value"] == 20.0
    assert t["post_capture_rate_max_dps"]["value"] == 2.0
    assert t["wheel_momentum_max_Nms"]["value"] == 5.475
    assert t["flexible_energy_max_J"]["value"] == 1.0e-3
    assert math.isclose(t["thruster_impulse_max_Ns"]["value"], 5.475 / 0.17, rel_tol=1e-15)
    assert math.isclose(t["propellant_budget_max_g"]["value"], 1000 * 5.475 / (0.17 * 60 * 9.80665), rel_tol=1e-15)
    source = ROOT / cfg["source_evidence"]["path"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == cfg["source_evidence"]["sha256"]
    assert cfg["policy"]["forbidden_threshold_action"] == "widen_limits_to_create_safe_candidates"


def test_deterministic_rebuild() -> None:
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        subprocess.run([sys.executable, str(BUILDER), "--output-root", a], cwd=ROOT, check=True, capture_output=True, text=True)
        subprocess.run([sys.executable, str(BUILDER), "--output-root", b], cwd=ROOT, check=True, capture_output=True, text=True)
        assert _hash_tree(Path(a)) == _hash_tree(Path(b))


def test_no_flexible_solver_execution_path() -> None:
    source = BUILDER.read_text(encoding="utf-8")
    banned = ["solve_ivp", "sim_07a_task_response", "ancf_runner", "scipy.integrate"]
    assert all(token not in source for token in banned)
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert cfg["policy"]["ancf_execution"] == "FORBIDDEN"
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    assert gate["ancf_executed"] is False


def test_row_hashes_recompute() -> None:
    for row in _rows():
        expected = row.pop("row_deterministic_hash")
        canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert actual == expected
