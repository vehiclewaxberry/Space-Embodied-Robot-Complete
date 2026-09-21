"""Contract-layer tests: S00/S01 scenario functions, SAFE fail-closed kernel,
URDF tree negative controls, and the episode writer."""
import numpy as np
import pytest

from dh_v1.safe_prebind import AuthorityItem, SafeContractViolation, decide, label_from_decision
from dh_v1.scen_static import run_s00, run_s01
from dh_v1.urdf_extract import UrdfContractViolation, validate_tree


def test_s00_all_positive_and_negative_pass(arm_model):
    rep = run_s00(arm_model)
    failed = [c for c in rep["checks"] if not c["passed"]]
    assert rep["all_passed"], f"S00 failures: {failed}"
    assert rep["negative_total"] >= 8


def test_s01_topology_and_fk(accepted_urdf_path):
    rep = run_s01(accepted_urdf_path)
    failed = [c for c in rep["checks"] if not c["passed"]]
    assert rep["all_passed"], f"S01 failures: {failed}"
    assert rep["topology"]["joints_by_type"] == {"revolute": 6, "fixed": 1, "prismatic": 2}


def _mini(joints):
    links = sorted({j["parent"] for j in joints} | {j["child"] for j in joints})
    return {
        "robot_name": "mini",
        "links": [{"name": n, "inertial": None, "has_visual": False, "has_collision": False} for n in links],
        "joints": [
            {
                "name": f"j{i}",
                "type": "fixed",
                "parent": j["parent"],
                "child": j["child"],
                "origin_xyz": [0, 0, 0],
                "origin_rpy": [0, 0, 0],
                "axis": None,
                "limits": None,
            }
            for i, j in enumerate(joints)
        ],
        "provenance": {},
    }


def test_tree_negative_controls():
    with pytest.raises(UrdfContractViolation):  # two parents
        validate_tree(_mini([{"parent": "a", "child": "c"}, {"parent": "b", "child": "c"}]))
    with pytest.raises(UrdfContractViolation):  # two roots / disconnected
        validate_tree(
            {
                "robot_name": "x",
                "links": [
                    {"name": n, "inertial": None, "has_visual": False, "has_collision": False}
                    for n in ("a", "b", "c", "d")
                ],
                "joints": _mini([{"parent": "a", "child": "b"}])["joints"]
                + _mini([{"parent": "c", "child": "d"}])["joints"],
                "provenance": {},
            }
        )


def test_safe_kernel_fail_closed_matrix():
    base = [AuthorityItem("A", "VERIFIED"), AuthorityItem("B", "VERIFIED")]
    assert decide(base).decision == "EXECUTE"
    for bad in ("MISSING", "UNKNOWN", "MISMATCH", "NOT_EVALUATED"):
        d = decide([AuthorityItem("A", bad), AuthorityItem("B", "VERIFIED")])
        assert d.decision == "ABORT", bad
    d = decide([AuthorityItem("A", "STALE", stale_age_s=0.5), AuthorityItem("B", "VERIFIED")])
    assert d.decision == "WAIT"
    d = decide([AuthorityItem("A", "STALE", stale_age_s=99.0)])
    assert d.decision == "ABORT"
    # provisional caps EXECUTE to MODIFY when admissible, ABORT otherwise
    d = decide([AuthorityItem("A", "PROVISIONAL", provisional_allowed=True)])
    assert d.decision == "MODIFY"
    d = decide([AuthorityItem("A", "PROVISIONAL", provisional_allowed=False)])
    assert d.decision == "ABORT"
    # non-required items never unblock ABORT paths
    d = decide([AuthorityItem("A", "MISSING", required=False), AuthorityItem("B", "VERIFIED")])
    assert d.decision == "EXECUTE"
    with pytest.raises(SafeContractViolation):
        AuthorityItem("A", "GOOD")
    with pytest.raises(SafeContractViolation):
        decide(base, requested_action="ABORT")


def test_label_taxonomy_guards():
    assert label_from_decision("ABORT", evaluated=False) == "NOT_EVALUATED"
    assert label_from_decision("ABORT", evaluated=True) == "ABORT"
    with pytest.raises(SafeContractViolation):
        label_from_decision("LAUNCH", evaluated=True)


def test_episode_writer_roundtrip_and_guards(tmp_path, accepted_urdf_path):
    import pandas as pd

    from dh_v1.episode_writer import EpisodeWriteError, EpisodeWriter
    from dh_v1.hashing import sha256_file

    w = EpisodeWriter(tmp_path / "episodes")
    manifest = {
        "episode_id": "T-0001",
        "base_state_id": "PREBIND_NULL",
        "scenario_id": "S00",
        "strategy_id": "NONE",
        "seed": 1,
        "accepted_urdf_sha256": sha256_file(accepted_urdf_path),
        "step_state_sha256": None,
        "collision_manifest_sha256": None,
        "frame_contract_sha256": "0" * 64,
        "unit_contract_sha256": "0" * 64,
        "controller_config_sha256": None,
        "safe_config_sha256": "0" * 64,
        "plant_sha256": "0" * 64,
        "geometry_authority": "MISSING",
        "dynamics_authority": "ACCEPTED_URDF",
        "contact_authority": "NOT_EVALUATED",
        "T_E_T_status": "MISSING",
        "evidence_level": "PREBIND",
        "claim_ceiling": "CURRENT_SYSTEM_DIGITAL_HOST_CANDIDATE_PREBIND_ONLY",
        "binding_gate": "DH-G0",
        "terminal_decision": "ABORT",
        "label": "ABORT",
    }
    ts = pd.DataFrame({"t": [0.0, 0.1], "E": [1.0, 1.0]})
    ep = w.write(manifest, {"snapshot": True}, {"cfg": 1}, [{"path": "x", "sha256": "y", "role": "r", "status": "s"}], ts)
    for f in (
        "RUN_MANIFEST.json",
        "AUTHORITY_SNAPSHOT.json",
        "RESOLVED_CONFIG.yaml",
        "INPUT_HASHES.csv",
        "TIMESERIES.parquet",
        "EVENTS.jsonl",
        "METRICS.json",
        "SAFETY_DECISION.json",
        "GATE_RESULT.json",
        "FAILURE_CONTEXT.json",
        "STDOUT.log",
        "HASH_MANIFEST.csv",
    ):
        assert (ep / f).exists(), f
    with pytest.raises(EpisodeWriteError):  # immutability
        w.write(manifest, {}, {}, [])
    bad = dict(manifest, episode_id="T-0002", label="EXECUTE", terminal_decision="EXECUTE")
    with pytest.raises(EpisodeWriteError):  # EXECUTE with missing T_E_T forbidden
        w.write(bad, {}, {}, [])
