from __future__ import annotations

from pathlib import Path

from conftest import HERE


def test_governance_authorizes_contract_tools_but_not_solver(governance_contract: dict) -> None:
    scope = governance_contract["authorized_scope"]
    assert scope == {
        "read_existing_sources": True,
        "freeze_synthetic_model_contract": True,
        "implement_contract_validator_and_independent_contract_audit": True,
        "implement_dynamics_solver": False,
        "modify_upstream_b3": False,
        "modify_or_generate_urdf": False,
        "instantiate_system_interface": False,
        "invoke_unified_private_builder_or_generator": False,
    }


def test_all_physical_current_formal_release_flags_are_false(governance_contract: dict) -> None:
    assert governance_contract["required_false"]
    assert not any(governance_contract["required_false"].values())


def test_formal_sim13_state_is_frozen_at_15_of_20(governance_contract: dict) -> None:
    formal = governance_contract["formal_sim13_v2_state_unchanged"]
    assert formal == {
        "passed": 15,
        "declared": 20,
        "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
    }


def test_forbidden_actions_cover_all_authority_escalations(governance_contract: dict) -> None:
    actions = set(governance_contract["forbidden_actions"])
    assert {
        "CALL_UNIFIED_PRIVATE_BUILDER",
        "CALL_UNIFIED_GENERATOR",
        "CREATE_FORMAL_INTERFACE_INSTANCE",
        "CLAIM_PHYSICAL_LOCK_OR_HELD_CAPTURE",
        "CLAIM_GRASP_SUCCESS",
        "CREDIT_THIS_PACKAGE_TO_FORMAL_NC19",
        "AUTHORIZE_PRODUCTION_RELEASE_OR_NEXT_STAGE",
    } <= actions


def test_b4_tree_contains_no_urdf_or_formal_interface_instance() -> None:
    assert not list(HERE.rglob("*.urdf"))
    assert not list(HERE.rglob("MECH_RL_SYSTEM_INTERFACE_V2.yaml"))
    assert not list(HERE.rglob("UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json"))


def test_units_policy_forbids_mixed_dimension_aggregation(units_ledger: dict) -> None:
    assert units_ledger["units_policy"] == "SI_AT_ALL_MODEL_AND_EVIDENCE_BOUNDARIES"
    assert "never combine linear and angular quantities" in units_ledger["mixed_dimension_policy"]
    channels = units_ledger["required_native_unit_channels"]
    assert channels["linear_impulse"] == "N*s"
    assert channels["angular_impulse"] == "N*m*s"


def test_every_physical_b4_quantity_remains_hold(units_ledger: dict) -> None:
    physical = [row for row in units_ledger["quantities"] if row["id"].startswith("physical_")]
    assert physical
    for row in physical:
        assert row["estimate"] is None
        assert row["standard_uncertainty"] is None
        assert row["distribution"] is None
        assert row["source"] is None
        assert row["status"].startswith("HOLD_")


def test_synthetic_timing_values_are_not_misreported_as_measurements(units_ledger: dict) -> None:
    rows = {row["id"]: row for row in units_ledger["quantities"]}
    for key in ("minimum_active_diagnostic_dwell", "clearance_dwell", "post_release_observation_horizon"):
        assert rows[key]["distribution"] == "exact algorithmic registration"
        assert "NOT_" in rows[key]["status"]
        assert rows[key]["standard_uncertainty"] is None


def test_future_physical_replacement_requires_full_uncertainty_fields(units_ledger: dict) -> None:
    rule = units_ledger["future_physical_replacement_rule"]
    for token in ("estimate", "standard uncertainty", "distribution", "degrees of freedom", "source", "correlation group"):
        assert token in rule
    assert "no null may be zero-filled" in rule
