from __future__ import annotations

import copy
import math
from pathlib import Path

import pytest
import yaml
import src.interface_loader as interface_loader

from src.contracts import (
    ActionCommand,
    EventPhase,
    ExecutionMode,
    GateState,
    HighLevelAction,
    RuntimeGateSnapshot,
)
from src.env import (
    ANCHOR_150KG,
    ANCHOR_22KG,
    M4DigitalPrototypeGraspingEnv,
)
from src.interface_loader import (
    ArtifactHashMismatch,
    DIAGNOSTIC_ACKNOWLEDGEMENT,
    DiagnosticAuthorizationError,
    InterfaceSchemaError,
    REQUIRED_CONFIGURATION_IDS,
    load_diagnostic_fixture,
    load_mechanical_interface,
)


def _diagnostic_env(
    interface_path: Path,
    fixture_path: Path,
    anchor_id: str,
) -> M4DigitalPrototypeGraspingEnv:
    return M4DigitalPrototypeGraspingEnv(
        interface_path,
        execution_mode=ExecutionMode.BOUNDED_DIAGNOSTIC,
        diagnostic_fixture_path=fixture_path,
        diagnostic_acknowledgement=DIAGNOSTIC_ACKNOWLEDGEMENT,
        anchor_id=anchor_id,
    )


def _execute_capture(
    env: M4DigitalPrototypeGraspingEnv,
) -> tuple[dict[str, object], dict[str, object]]:
    env.reset(gates=RuntimeGateSnapshot.all_pass())
    observation, _, terminated, truncated, _ = env.step(
        ActionCommand.MOVE_PREGRASP.value
    )
    assert observation["task_phase"] == EventPhase.PREGRASP.value
    assert not terminated and not truncated
    observation, _, terminated, truncated, _ = env.step(
        ActionCommand.DECLARE_CONTACT_CANDIDATE.value
    )
    assert observation["task_phase"] == EventPhase.CONTACT_CANDIDATE.value
    assert not terminated and not truncated
    observation, reward, terminated, truncated, info = env.step(
        ActionCommand.CLOSE_GRIPPER.value
    )
    assert reward == 1.0
    assert terminated and not truncated
    assert observation["task_phase"] == EventPhase.CAPTURED.value
    return observation, info


def test_interface_loads_and_binds_resolved_assets(
    mechanical_interface_path: Path,
) -> None:
    bundle = load_mechanical_interface(mechanical_interface_path)
    resolved = {name for name, item in bundle.artifacts.items() if item.resolved}
    assert resolved == {
        "accepted_b601_urdf",
        "m3r_working_step",
        "gripper_r1_step",
        "v5r_neutral_system_step",
        "v5r_collision_mesh",
        "configuration_library",
        "system_mass_properties",
        "master_fcstd",
        "master_step",
        "frame_tree",
        "collision_asset_register",
        "geometry_audit",
        "geometry_independent_validation",
        "mass_material_tolerance_mechanism_audit",
    }
    assert len(resolved) == 14
    assert all(len(bundle.artifacts[name].sha256 or "") == 64 for name in resolved)
    assert bundle.closure_audited_artifact_count == 13


def test_exact_nine_configuration_contract(mechanical_interface_path: Path) -> None:
    bundle = load_mechanical_interface(mechanical_interface_path)
    assert bundle.required_configurations == REQUIRED_CONFIGURATION_IDS
    assert len(bundle.required_configurations) == 9
    assert dict(bundle.configuration_release_counts) == {
        "mass": 0,
        "center_of_mass": 0,
        "inertia": 0,
    }
    assert bundle.numeric_mass_diagnostic_available_count == 9
    assert bundle.full_mass_properties_loader_ready_count == 0


def test_interface_production_readiness_is_computed_fail_closed(
    mechanical_interface_path: Path,
) -> None:
    bundle = load_mechanical_interface(mechanical_interface_path)
    assert bundle.declared_production_ready is False
    assert bundle.production_ready is False
    assert bundle.unresolved_required_artifacts == ()
    assert bundle.full_mass_properties_loader_ready_count == 0
    assert "SERVICE_SYSTEM_MASS" in bundle.computed_missing_authorities
    assert "CONTACT_FRICTION" in bundle.computed_missing_authorities
    assert "NINE_CONFIGURATION_INERTIA" in bundle.computed_missing_authorities


def test_hash_mismatch_is_rejected(
    mechanical_interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_sha256_file = interface_loader.sha256_file

    def injected_hash(path: Path) -> str:
        if path.name == "arm_b601_v1.urdf":
            return "0" * 64
        return real_sha256_file(path)

    monkeypatch.setattr(interface_loader, "sha256_file", injected_hash)
    with pytest.raises(ArtifactHashMismatch, match="accepted_b601_urdf SHA-256 mismatch"):
        load_mechanical_interface(mechanical_interface_path)


def test_nested_closure_audit_hash_mismatch_is_rejected(
    mechanical_interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_sha256_file = interface_loader.sha256_file

    def injected_hash(path: Path) -> str:
        if path.name == "INTERFACE_STACKUP_B601_M3R_V1.yaml":
            return "0" * 64
        return real_sha256_file(path)

    monkeypatch.setattr(interface_loader, "sha256_file", injected_hash)
    with pytest.raises(ArtifactHashMismatch, match="closure audit SHA-256 mismatch"):
        load_mechanical_interface(mechanical_interface_path)


def test_nonidentity_spacecraft_assembly_alias_is_rejected(
    mechanical_interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_load_mapping = interface_loader._load_mapping

    def injected_mapping(path: Path) -> dict[str, object]:
        document = copy.deepcopy(real_load_mapping(path))
        if path.name == "DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml":
            document["frame_aliases"]["spacecraft_assembly_frame"][
                "T_S_spacecraft_assembly_frame_rows"
            ][0][3] = 1.0
        return document

    monkeypatch.setattr(interface_loader, "_load_mapping", injected_mapping)
    with pytest.raises(InterfaceSchemaError, match="frozen identity alias"):
        load_mechanical_interface(mechanical_interface_path)


def test_configuration_inertia_reference_point_mutation_is_rejected(
    mechanical_interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_load_mapping = interface_loader._load_mapping

    def injected_mapping(path: Path) -> dict[str, object]:
        document = copy.deepcopy(real_load_mapping(path))
        if path.name == "CONFIGURATION_LIBRARY_V1.yaml":
            document["configurations"][0]["inertia"]["reference_point"] = (
                "spacecraft_assembly_frame_origin"
            )
        return document

    monkeypatch.setattr(interface_loader, "_load_mapping", injected_mapping)
    with pytest.raises(InterfaceSchemaError, match="inertia reference point changed"):
        load_mechanical_interface(mechanical_interface_path)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("distribution", "UNIFORM"),
        ("degrees_of_freedom", 1),
        ("source", "unresolved_source"),
    ),
)
def test_system_uncertainty_contract_mutation_is_rejected(
    mechanical_interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    invalid_value: object,
) -> None:
    real_load_mapping = interface_loader._load_mapping

    def injected_mapping(path: Path) -> dict[str, object]:
        document = copy.deepcopy(real_load_mapping(path))
        if path.name == "SYSTEM_MASS_PROPERTIES_V3.yaml":
            document["component_records"]["spacecraft_bus_no_panels"][
                "center_of_mass"
            ][field_name] = invalid_value
        return document

    monkeypatch.setattr(interface_loader, "_load_mapping", injected_mapping)
    with pytest.raises(InterfaceSchemaError):
        load_mechanical_interface(mechanical_interface_path)


@pytest.mark.parametrize(
    "document_name",
    ("CONFIGURATION_LIBRARY_V1.yaml", "SYSTEM_MASS_PROPERTIES_V3.yaml"),
)
def test_full_mass_properties_loader_ready_must_remain_zero(
    mechanical_interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    document_name: str,
) -> None:
    real_load_mapping = interface_loader._load_mapping

    def injected_mapping(path: Path) -> dict[str, object]:
        document = copy.deepcopy(real_load_mapping(path))
        if path.name == document_name:
            if document_name == "CONFIGURATION_LIBRARY_V1.yaml":
                document["summary"][
                    "ready_for_full_mass_properties_diagnostic_loader_count"
                ] = 1
            else:
                document["nine_configuration_delivery"][
                    "full_mass_properties_loader_ready_count"
                ] = 1
        return document

    monkeypatch.setattr(interface_loader, "_load_mapping", injected_mapping)
    with pytest.raises(InterfaceSchemaError):
        load_mechanical_interface(mechanical_interface_path)


def test_production_mode_masks_non_abort_even_when_runtime_gates_pass(
    mechanical_interface_path: Path,
) -> None:
    env = M4DigitalPrototypeGraspingEnv(mechanical_interface_path)
    observation, _ = env.reset(gates=RuntimeGateSnapshot.all_pass())
    assert observation["target"]["mass_kg"] is None
    assert observation["service_spacecraft"]["mass_kg"] is None
    next_observation, reward, terminated, truncated, info = env.step(
        ActionCommand.MOVE_PREGRASP.value
    )
    assert terminated and not truncated and reward == -1.0
    assert next_observation["task_phase"] == EventPhase.ABORTED_SAFE.value
    assert info["executed_action"] == {"command": "ABORT"}
    assert "MECHANICAL_INTERFACE_NOT_PRODUCTION_READY" in info["shield_reason_codes"]


def test_abort_always_available_in_production(mechanical_interface_path: Path) -> None:
    env = M4DigitalPrototypeGraspingEnv(mechanical_interface_path)
    env.reset()
    decision = env.action_mask()[HighLevelAction.abort()]
    assert decision.allowed is True
    assert decision.reason_codes == ("ABORT_ALWAYS_AVAILABLE",)


def test_unknown_runtime_gate_forces_abort(
    diagnostic_env: M4DigitalPrototypeGraspingEnv,
) -> None:
    diagnostic_env.reset()
    _, _, terminated, _, info = diagnostic_env.step(ActionCommand.MOVE_PREGRASP.value)
    assert terminated
    assert info["shield_intervened"] is True
    assert info["executed_action"] == {"command": "ABORT"}
    assert all(
        f"{field_name.upper()}_UNKNOWN" in info["shield_reason_codes"]
        for field_name in RuntimeGateSnapshot.__dataclass_fields__
    )


def test_single_failed_runtime_gate_forces_abort(
    diagnostic_env: M4DigitalPrototypeGraspingEnv,
) -> None:
    gates = RuntimeGateSnapshot.all_pass()
    gates = RuntimeGateSnapshot(
        **{
            name: (
                GateState.FAIL if name == "external_collision_clear" else getattr(gates, name)
            )
            for name in RuntimeGateSnapshot.__dataclass_fields__
        }
    )
    diagnostic_env.reset(gates=gates)
    _, _, terminated, _, info = diagnostic_env.step(ActionCommand.MOVE_PREGRASP.value)
    assert terminated
    assert "EXTERNAL_COLLISION_CLEAR_FAIL" in info["shield_reason_codes"]


def test_illegal_event_transition_is_shielded(
    diagnostic_env: M4DigitalPrototypeGraspingEnv,
) -> None:
    diagnostic_env.reset(gates=RuntimeGateSnapshot.all_pass())
    observation, _, terminated, _, info = diagnostic_env.step(
        ActionCommand.CLOSE_GRIPPER.value
    )
    assert terminated
    assert observation["capture_closure"] is None
    assert "ILLEGAL_RESET_READY_TO_CLOSE_GRIPPER" in info["shield_reason_codes"]


@pytest.mark.parametrize(
    ("anchor_id", "expected_fixture_total_mass_kg"),
    (
        (ANCHOR_22KG, 51.081436764691),
        (ANCHOR_150KG, 179.081436764691),
    ),
)
def test_capture_conserves_linear_and_angular_momentum(
    mechanical_interface_path: Path,
    diagnostic_fixture_path: Path,
    anchor_id: str,
    expected_fixture_total_mass_kg: float,
) -> None:
    env = _diagnostic_env(
        mechanical_interface_path, diagnostic_fixture_path, anchor_id
    )
    observation, info = _execute_capture(env)
    closure = observation["capture_closure"]
    assert closure is not None
    assert math.isclose(
        closure["total_mass_kg"],
        expected_fixture_total_mass_kg,
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    assert closure["linear_residual_norm_kg_mps"] <= 1e-12
    assert closure["angular_residual_norm_kg_m2ps"] <= 1e-12
    assert closure["contact_force_computed"] is False
    assert closure["contact_impulse_history_computed"] is False
    assert "NOT_CONTACT_FORCE_OR_FLEXIBLE_DYNAMICS" in closure["model_scope"]
    assert info["authorized_scope"] == "BOUNDED_DIAGNOSTIC_SOFTWARE_MECHANICS_ONLY"


def test_diagnostic_capture_is_deterministic(
    mechanical_interface_path: Path,
    diagnostic_fixture_path: Path,
) -> None:
    left = _diagnostic_env(
        mechanical_interface_path, diagnostic_fixture_path, ANCHOR_22KG
    )
    right = _diagnostic_env(
        mechanical_interface_path, diagnostic_fixture_path, ANCHOR_22KG
    )
    assert _execute_capture(left) == _execute_capture(right)


def test_direct_joint_torque_action_is_rejected(
    diagnostic_env: M4DigitalPrototypeGraspingEnv,
) -> None:
    diagnostic_env.reset(gates=RuntimeGateSnapshot.all_pass())
    with pytest.raises(ValueError, match="direct joint torque/effort actions are forbidden"):
        diagnostic_env.step(
            {"command": "MOVE_PREGRASP", "joint_torques": [0.0] * 6}
        )


def test_diagnostic_fixture_requires_exact_acknowledgement(
    diagnostic_fixture_path: Path,
) -> None:
    with pytest.raises(DiagnosticAuthorizationError):
        load_diagnostic_fixture(diagnostic_fixture_path, acknowledgement=None)
    with pytest.raises(DiagnosticAuthorizationError):
        load_diagnostic_fixture(
            diagnostic_fixture_path, acknowledgement="I_ACCEPT_PLACEHOLDERS"
        )


def test_units_and_uncertainty_semantics_are_explicit(
    mechanical_interface_path: Path,
    diagnostic_fixture_path: Path,
) -> None:
    bundle = load_mechanical_interface(mechanical_interface_path)
    assert bundle.document["units"]["inertia"] == "kg*m^2"
    properties = bundle.document["mechanical_properties"]
    assert properties["service_spacecraft_system"]["mass_kg"] is None
    assert properties["service_spacecraft_system"]["standard_uncertainty"] is None
    fixture = yaml.safe_load(diagnostic_fixture_path.read_text(encoding="utf-8"))
    assert fixture["uncertainty_policy"]["standard_uncertainty"] is None
    assert fixture["uncertainty_policy"]["zero_fill_forbidden"] is True
    assert fixture["service_spacecraft_fixture"]["mass_scope"].endswith("PLUS_M3R")
    assert len(fixture["anchors"][ANCHOR_22KG]["inertia_about_com_kg_m2"]) == 3


def test_diagnostic_observation_does_not_claim_contact_or_flexible_physics(
    diagnostic_env: M4DigitalPrototypeGraspingEnv,
) -> None:
    observation, info = diagnostic_env.reset(gates=RuntimeGateSnapshot.all_pass())
    assert observation["contact"]["force_N"] is None
    assert observation["contact"]["pressure_Pa"] is None
    assert observation["flexible_body"]["enabled"] is False
    assert observation["flexible_body"]["modal_coordinates"] is None
    assert info["authorized_scope"] == "BOUNDED_DIAGNOSTIC_SOFTWARE_MECHANICS_ONLY"


def test_anchor_angular_rates_are_si_and_exactly_fixture_scoped(
    mechanical_interface_path: Path,
    diagnostic_fixture_path: Path,
) -> None:
    cases = (
        (ANCHOR_22KG, math.radians(0.5)),
        (ANCHOR_150KG, math.radians(3.0)),
    )
    for anchor_id, expected_radps in cases:
        env = _diagnostic_env(
            mechanical_interface_path, diagnostic_fixture_path, anchor_id
        )
        observation, _ = env.reset()
        assert math.isclose(
            observation["target"]["state"]["angular_velocity_radps"][2],
            expected_radps,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
        assert observation["target"]["mass_authority"] == (
            "DIAGNOSTIC_FIXTURE_NOT_ENGINEERING_AUTHORITY"
        )
