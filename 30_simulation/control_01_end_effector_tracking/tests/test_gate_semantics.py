import json
from pathlib import Path

from contracts import GATE_RESULT_ENUM
from repo_imports import RESULTS_DIR


def test_gate_verdict_enum_and_test_separation():
    path = RESULTS_DIR / "control_01_gate_check.json"
    if not path.exists():
        return 0.0
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["verdict"] in GATE_RESULT_ENUM
    assert data["tests_are_not_gate"] is True
    for gate in data["gates"].values():
        assert gate["status"] in GATE_RESULT_ENUM
    hashes = json.loads(
        (RESULTS_DIR / "artifacts_sha256.json").read_text(encoding="utf-8")
    )
    assert all(not Path(row["path"]).is_absolute() for row in hashes["artifacts"])
    assert not Path(data["artifact_manifest"]).is_absolute()
    increment = data["gates"]["GC1_D_incremental_effectiveness"]
    assert increment["isolated_nullspace_comparator"] == "C2_MATCH5"
    assert "C3_vs_C2_MATCH5_T2_base_rate_improvement_pct" in increment
    assert increment["C3_vs_C2_MATCH5_isolates_nullspace_effect"] is True
    assert "previous_loop_negative_results_preserved" in increment
    preserved = increment["previous_loop_negative_results_preserved"]
    assert (
        preserved["C2_vs_C1_T2_position_improvement_pct"] == -51.9137123236204
    )
    forbidden = data["claim_scope"]["forbidden"]
    assert "C3 versus C1_MATCH5 isolates the nullspace effect" in forbidden
    collision_gate = data["gates"]["GC1_E_constraints"][
        "collision_evaluation"
    ]
    assert collision_gate["target_status"] == "EVALUATED"
    assert collision_gate["combined_status"] == "EVALUATED"
    equivalence = data["gates"]["GC1_H_fast_plant_ssot_equivalence"]
    assert equivalence["status"] == "PASS"
    return 0.0


def test_pending_review_is_not_self_certified():
    path = RESULTS_DIR / "control_01_gate_check.json"
    if not path.exists():
        return 0.0
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["independent_red_team_status"] == "PENDING_REVIEW"
    return 0.0
