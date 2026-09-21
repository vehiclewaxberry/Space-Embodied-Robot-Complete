from __future__ import annotations

import copy
import math
from pathlib import Path

import pytest

from conftest import (
    CONFIGURATION_CONTRACT_PATH,
    DIAGNOSTIC_ACKNOWLEDGEMENT,
    PHASE_AUTHORITY_PATH,
    RELEASE_GATE_PATH,
    REQUIRED_CONFIGURATION_IDS,
    load_mapping,
    sha256_file,
)


def _record_by_id(document: dict[str, object]) -> dict[str, dict[str, object]]:
    records = document["records"]
    assert isinstance(records, list)
    return {
        str(record["configuration_id"]): record
        for record in records
        if isinstance(record, dict)
    }


def _determinant3(matrix: list[list[float]]) -> float:
    return (
        matrix[0][0]
        * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1]
        * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2]
        * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def test_interface_is_si_hash_bound_and_diagnostic_only(
    interface_document: dict[str, object],
) -> None:
    assert interface_document["schema"] == "MECH_DYNAMICS_INTERFACE_V3"
    assert interface_document["units"] == {
        "length": "m",
        "angle": "rad",
        "mass": "kg",
        "inertia": "kg*m^2",
        "force": "N",
        "moment": "N*m",
        "impulse": "N*s",
        "couple_impulse": "N*m*s",
    }
    assert interface_document["required_acknowledgement"] == (
        DIAGNOSTIC_ACKNOWLEDGEMENT
    )
    assert interface_document["zero_fill_forbidden"] is True
    assert tuple(interface_document["configuration_ids"]) == REQUIRED_CONFIGURATION_IDS

    geometry = interface_document["geometry_capabilities"]
    loads = interface_document["loads_capabilities"]
    gates = interface_document["runtime_gates"]
    assert isinstance(geometry, dict) and isinstance(loads, dict) and isinstance(gates, dict)
    assert geometry["diagnostic_snapshots"] == 9
    assert geometry["narrow_phase_verified"] is False
    assert geometry["contact_geometry_authorized"] is False
    assert loads["hash_bound_diagnostic_impulse_solver"] is True
    assert loads["six_dof_joint_distribution"] is True
    assert loads["contact_force_time_history"] is False
    assert loads["physical_load_authority"] is False
    assert gates == {
        "geometry_diagnostic": "PASS",
        "physical_contact": "HOLD",
        "structural_analysis": "HOLD",
        "physics_gated_RL": "HOLD",
    }


def test_every_required_interface_artifact_exists_and_matches_sha256(
    project_root: Path,
    interface_document: dict[str, object],
) -> None:
    artifacts = interface_document["artifacts"]
    assert isinstance(artifacts, dict) and artifacts
    assert all(binding["required"] is True for binding in artifacts.values())
    for artifact_id, binding in artifacts.items():
        assert isinstance(binding, dict)
        path = project_root / str(binding["path"])
        assert path.is_file(), f"required M5 artifact is absent: {artifact_id}: {path}"
        expected = str(binding["sha256"])
        assert len(expected) == 64
        assert sha256_file(path) == expected.upper(), artifact_id


def test_runtime_authority_loader_verifies_full_bundle(interface_path: Path) -> None:
    from src.authority import ACKNOWLEDGEMENT, load_authority

    bundle = load_authority(interface_path)
    assert ACKNOWLEDGEMENT == DIAGNOSTIC_ACKNOWLEDGEMENT
    assert bundle.document["schema"] == "MECH_DYNAMICS_INTERFACE_V3"
    assert tuple(bundle.document["configuration_ids"]) == REQUIRED_CONFIGURATION_IDS
    assert bundle.physical_contact_ready is False
    assert bundle.production_ready is False
    assert set(bundle.artifacts) == set(bundle.document["artifacts"])
    assert bundle.configuration_contract["configuration_count"] == 9
    assert bundle.broadphase_audit["system_collision_release"] is False
    assert bundle.load_authority["formal_loads_authorized"] is False
    assert bundle.contact_contract["physical_contact_kernel_authorized"] is False
    assert bundle.structural_gate["formal_fea_authorized"] is False


def test_runtime_authority_loader_rejects_a_hash_mismatch(
    interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.authority as authority

    real_sha256_file = authority.sha256_file

    def mismatching_hash(path: Path) -> str:
        if path.name == "M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml":
            return "0" * 64
        return real_sha256_file(path)

    monkeypatch.setattr(authority, "sha256_file", mismatching_hash)
    with pytest.raises(authority.ArtifactHashMismatch):
        authority.load_authority(interface_path)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("required_acknowledgement", "I_ACCEPT_UNBOUNDED_PHYSICS"),
        ("zero_fill_forbidden", False),
    ),
)
def test_runtime_authority_loader_rejects_interface_scope_mutation(
    interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    invalid_value: object,
) -> None:
    import src.authority as authority

    real_load_mapping = authority._load_mapping

    def mutated_load(path: Path) -> object:
        document = real_load_mapping(path)
        if path.resolve() == interface_path.resolve():
            document = copy.deepcopy(document)
            document[field] = invalid_value
        return document

    monkeypatch.setattr(authority, "_load_mapping", mutated_load)
    with pytest.raises(authority.AuthorityError):
        authority.load_authority(interface_path)


def test_runtime_authority_loader_rejects_non_si_interface_unit(
    interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.authority as authority

    real_load_mapping = authority._load_mapping

    def mutated_load(path: Path) -> object:
        document = real_load_mapping(path)
        if path.resolve() == interface_path.resolve():
            document = copy.deepcopy(document)
            document["units"]["length"] = "mm"
        return document

    monkeypatch.setattr(authority, "_load_mapping", mutated_load)
    with pytest.raises(authority.AuthorityError):
        authority.load_authority(interface_path)


def test_runtime_authority_loader_rejects_configuration_contact_promotion(
    interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.authority as authority

    real_load_mapping = authority._load_mapping

    def mutated_load(path: Path) -> object:
        document = real_load_mapping(path)
        if path.name == CONFIGURATION_CONTRACT_PATH.name:
            document = copy.deepcopy(document)
            document["records"][7]["contact_enabled"] = True
        return document

    monkeypatch.setattr(authority, "_load_mapping", mutated_load)
    with pytest.raises(authority.AuthorityError):
        authority.load_authority(interface_path)


def test_exact_nine_configuration_contract_is_never_physical_authority(
    configuration_document: dict[str, object],
) -> None:
    assert configuration_document["schema"] == (
        "M5_CONFIGURATION_GEOMETRY_CONTRACT_V1"
    )
    assert configuration_document["configuration_count"] == 9
    assert tuple(configuration_document["required_ids"]) == REQUIRED_CONFIGURATION_IDS
    records = _record_by_id(configuration_document)
    assert tuple(records) == REQUIRED_CONFIGURATION_IDS
    for configuration_id, record in records.items():
        assert record["diagnostic_only"] is True, configuration_id
        assert record["contact_enabled"] is False, configuration_id
        assert record["mass_properties_authority"] is False, configuration_id
        assert record["released_mass_kg"] is None, configuration_id
        assert record["released_cg_S_m"] is None, configuration_id
        assert record["released_inertia_S_kg_m2"] is None, configuration_id
        broadphase = record["broadphase"]
        assert isinstance(broadphase, dict)
        assert broadphase["verified_system_collision_clear"] is False
        assert broadphase["possible_or_touching_hold_count"] >= 1
        assert "NO_NARROW_PHASE_OR_SYSTEM_RELEASE" in broadphase["claim_limit"]

    assert configuration_document["released_mass_count"] == 0
    assert configuration_document["released_cg_count"] == 0
    assert configuration_document["released_inertia_count"] == 0
    assert configuration_document["verified_system_collision_count"] == 0
    assert configuration_document["contact_enabled_count"] == 0


def test_configuration_snapshot_files_are_hash_bound(
    project_root: Path,
    configuration_document: dict[str, object],
) -> None:
    for configuration_id, record in _record_by_id(configuration_document).items():
        snapshot = record["snapshot"]
        assert isinstance(snapshot, dict)
        path = project_root / str(snapshot["path"])
        assert path.is_file(), configuration_id
        assert sha256_file(path) == str(snapshot["sha256"]).upper(), configuration_id


def test_solar_branch_and_stowed_configuration_do_not_mix_proxies(
    configuration_document: dict[str, object],
) -> None:
    assert "V5_R2B_3PANEL_CANDIDATE" in str(configuration_document["branch_rule"])
    assert "not mixed" in str(configuration_document["branch_rule"])
    records = _record_by_id(configuration_document)
    for configuration_id in ("C01", "C02", "C03", "C04", "C06", "C07", "C08", "C09"):
        assert records[configuration_id]["solar_geometry_variant"] == (
            "V5_R2B_3PANEL_CANDIDATE"
        )
        assert records[configuration_id]["solar_frame_reconciliation_to_M4"] == (
            "HOLD_REQUIRES_ECR"
        )
    assert records["C05"]["solar_geometry_variant"] is None
    assert records["C05"]["solar_state"] is None
    assert records["C05"]["solar_frame_reconciliation_to_M4"] == "NOT_SELECTED"


@pytest.mark.parametrize("configuration_id", ("C07", "C08", "C09"))
def test_target_transforms_are_valid_display_only_si_poses(
    configuration_document: dict[str, object],
    configuration_id: str,
) -> None:
    record = _record_by_id(configuration_document)[configuration_id]
    transform = record["target_transform_S_rows"]
    assert isinstance(transform, list) and len(transform) == 4
    assert all(isinstance(row, list) and len(row) == 4 for row in transform)
    assert transform[3] == [0.0, 0.0, 0.0, 1.0]
    rotation = [[float(transform[i][j]) for j in range(3)] for i in range(3)]
    for row_index in range(3):
        for column_index in range(3):
            dot = math.fsum(
                rotation[row_index][axis] * rotation[column_index][axis]
                for axis in range(3)
            )
            assert math.isclose(
                dot,
                1.0 if row_index == column_index else 0.0,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
    assert math.isclose(_determinant3(rotation), 1.0, rel_tol=0.0, abs_tol=1e-12)
    assert record["target_transform_authority"] == (
        "DISPLAY_ONLY_NOT_WRITTEN_BACK_TO_M4"
    )
    assert record["display_gripper_travel_m"] == pytest.approx(0.055)
    assert record["display_gripper_travel_source"] == (
        "R1_GEOMETRY_WITNESS_PREGRASP_NOT_CXX_AUTHORITY"
    )
    assert record["finger_travel_configuration_authority"] is False
    assert record["required_capture_gripper_travel_m"] is None


def test_capture_named_configuration_is_not_capture_authority(
    configuration_document: dict[str, object],
) -> None:
    capture = _record_by_id(configuration_document)["C08"]
    assert capture["name"] == "CAPTURE"
    assert capture["q_source"] == "E15_DISPLAY_ONLY_REJECTED_AS_22KG_VALIDATION"
    assert capture["contact_enabled"] is False
    assert capture["finger_travel_configuration_authority"] is False
    assert capture["required_capture_gripper_travel_m"] is None


def test_gripper_frame_registration_accepts_gripper_link_and_rejects_direct_link6(
    m5_root: Path,
) -> None:
    decision = load_mapping(
        m5_root
        / "01_geometry_authority"
        / "B601_CAD_MESH_FRAME_DECISION_V1.json"
    )
    gripper = decision["active_gripper_r1"]
    assert isinstance(gripper, dict)
    motion = gripper["motion_contract"]
    assert isinstance(motion, dict)
    registration = motion["frame_registration"]
    assert isinstance(registration, dict)

    assert motion["source_receipt_frame_label"] == "LINK6_LOCAL"
    assert motion["corrected_frame_binding"] == "gripper_link"
    assert motion["T_link6_gripper_source"] == (
        "accepted URDF gripper_joint fixed origin"
    )
    assert registration["units"] == "mm"
    assert registration["gripper_link_bbox_endpoint_max_abs_error_mm"] < 0.001
    assert registration["gripper_link_bbox_endpoint_max_abs_error_mm"] <= (
        registration["gripper_link_acceptance_mm"]
    )
    assert registration["gripper_link_registration_pass"] is True
    assert registration["direct_link6_bbox_endpoint_max_abs_error_mm"] > 100.0
    assert registration["direct_link6_binding_rejected"] is True
    assert registration["accepted_binding"] == "gripper_link"
    assert registration["source_label_conflict_status"] == (
        "HOLD_SOURCE_LABEL_IS_NOT_NUMERICAL_FRAME_AUTHORITY"
    )


def test_gripper_travel_witness_does_not_zero_fill_manufacturing_clearance(
    m5_root: Path,
) -> None:
    decision = load_mapping(
        m5_root
        / "01_geometry_authority"
        / "B601_CAD_MESH_FRAME_DECISION_V1.json"
    )
    motion = decision["active_gripper_r1"]["motion_contract"]
    assert motion["configuration_travel_authority"] is None
    assert motion["travel_conflict_disposition"] == (
        "HOLD_UNTIL_CONFIGURATION_TO_TRAVEL_MAP_IS_RATIFIED"
    )
    assert motion["manufacturing_additional_clearance_m"] is None
    assert motion["manufacturing_clearance_status"] == "PROVISIONAL_CLEARANCE_HOLD"
    assert motion["contact_and_strength_status"] == "HOLD"


def test_memory_override_is_recorded_without_relabelling_gate_pass() -> None:
    phase = load_mapping(PHASE_AUTHORITY_PATH)
    memory = phase["memory_execution"]
    assert memory["memory_gate_passed"] is False
    assert memory["memory_gate_status"] == "OWNER_OVERRIDE_LOW_MEMORY"
    assert memory["owner_override_used"] is True
    assert memory["execution_route"] == (
        "LIGHTWEIGHT_NEUTRAL_GEOMETRY_AND_ANALYTIC_LOADS"
    )
    assert phase["formal_fea_run_count"] == 0
    assert "formal FEA" in phase["explicitly_not_authorized"]
    assert "contact force or pressure" in phase["explicitly_not_authorized"]


def test_release_gate_keeps_all_physical_claims_closed() -> None:
    gate = load_mapping(RELEASE_GATE_PATH)
    rendered = str(gate).upper()
    assert gate["formal_fea_run_count"] == 0
    assert "SIM15_HASH_BOUND_DIAGNOSTIC_CAPTURE_IMPULSE_AND_JOINT_LOAD_SOFTWARE_ONLY" in rendered
    assert "CONTACT" in rendered and "HOLD" in rendered
    assert "STRUCTURAL" in rendered and "HOLD" in rendered
    assert "RL" in rendered and "HOLD" in rendered


def test_contract_mutation_example_cannot_satisfy_release_invariants(
    configuration_document: dict[str, object],
) -> None:
    """Guard against future validators trusting only the declared summary."""

    mutated = copy.deepcopy(configuration_document)
    records = _record_by_id(mutated)
    records["C08"]["contact_enabled"] = True
    # A declared summary of zero cannot override an enabled physical record.
    computed_contact_enabled = sum(
        bool(record["contact_enabled"]) for record in records.values()
    )
    assert mutated["contact_enabled_count"] == 0
    assert computed_contact_enabled == 1
    assert computed_contact_enabled != mutated["contact_enabled_count"]
