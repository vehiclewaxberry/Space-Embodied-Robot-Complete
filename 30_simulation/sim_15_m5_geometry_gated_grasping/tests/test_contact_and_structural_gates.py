from __future__ import annotations

import copy
from dataclasses import is_dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from conftest import public_mapping


def _estimated_parameters(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    found: dict[str, Mapping[str, Any]] = {}

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, Mapping):
            if "estimate" in value and "status" in value:
                found[".".join(path)] = value
            for key, child in value.items():
                visit(child, (*path, str(key)))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, (*path, str(index)))

    visit(document, ())
    return found


def _with_contact_contract(authority: Any, contact_contract: dict[str, Any]) -> Any:
    if is_dataclass(authority):
        return replace(authority, contact_contract=contact_contract)
    values = dict(vars(authority))
    values["contact_contract"] = contact_contract
    return SimpleNamespace(**values)


def _decision_allows_physical_contact(decision: Any) -> bool:
    mapping = public_mapping(decision)
    authorization_fields = {
        "allowed",
        "authorized",
        "ready",
        "physical_contact_ready",
        "physical_contact_authorized",
    }
    return any(bool(value) for key, value in mapping.items() if key in authorization_fields)


def test_contact_contract_is_si_and_forbids_zero_fill(
    contact_document: dict[str, object],
) -> None:
    assert contact_document["schema"] == "M5_CONTACT_MODEL_PARAMETER_CONTRACT_V1"
    assert contact_document["units_policy"] == (
        "SI_AT_API_BOUNDARY_AND_EXPLICIT_CONVERSION_FROM_SOURCE_MM"
    )
    assert contact_document["zero_fill_forbidden"] is True
    assert contact_document["physical_contact_kernel_authorized"] is False
    assert contact_document["computed_contact_force_N"] is None
    assert contact_document["computed_contact_pressure_Pa"] is None
    assert contact_document["status"] == (
        "HOLD_ALL_PHYSICAL_CONTACT_PARAMETERS_AND_FRAMES_INCOMPLETE"
    )


def test_all_physical_contact_parameters_remain_null_except_geometry_stroke(
    contact_document: dict[str, object],
) -> None:
    parameters = _estimated_parameters(contact_document)
    assert parameters
    non_null = {
        path: parameter["estimate"]
        for path, parameter in parameters.items()
        if parameter["estimate"] is not None
    }
    assert non_null == {"gripper_actuator.stroke_m": pytest.approx(0.0715)}
    stroke = parameters["gripper_actuator.stroke_m"]
    assert stroke["unit"] == "m"
    assert stroke["standard_uncertainty"] is None
    assert stroke["distribution"] is None
    assert stroke["degrees_of_freedom"] is None
    assert "UNCERTAINTY_HOLD" in str(stroke["status"])


def test_contact_frames_and_complete_structural_path_are_absent(
    contact_document: dict[str, object],
) -> None:
    geometry = contact_document["contact_geometry"]
    mapping = contact_document["structural_mapping"]
    assert isinstance(geometry, dict) and isinstance(mapping, dict)
    assert geometry["left_contact_frame_T_gripper_link"] is None
    assert geometry["right_contact_frame_T_gripper_link"] is None
    assert geometry["target_surface_normal"] is None
    assert geometry["effective_area_m2"]["estimate"] is None
    assert geometry["initial_gap_m"]["estimate"] is None
    assert mapping["T_wrist_from_contact"] is None
    assert mapping["T_load_bridge_from_m3r"] is None
    assert mapping["status"] == "HOLD_COMPLETE_6D_PHYSICAL_LOAD_PATH"


def test_runtime_contact_gate_computes_hold_from_authority(interface_path: Path) -> None:
    from src.authority import load_authority
    from src.contact_gate import PhysicalContactGate

    authority = load_authority(interface_path)
    decision = PhysicalContactGate.evaluate(authority)
    assert _decision_allows_physical_contact(decision) is False
    rendered = str(public_mapping(decision)).upper()
    assert "HOLD" in rendered or "NOT_AUTHORIZED" in rendered
    assert "CONTACT" in rendered


def test_runtime_contact_gate_require_always_fails_closed(interface_path: Path) -> None:
    from src.authority import load_authority
    from src.contact_gate import PhysicalContactGate, PhysicalContactNotAuthorized

    authority = load_authority(interface_path)
    with pytest.raises(PhysicalContactNotAuthorized):
        PhysicalContactGate.require(authority)


def test_declared_contact_authorization_cannot_override_missing_parameters(
    interface_path: Path,
) -> None:
    from src.authority import load_authority
    from src.contact_gate import PhysicalContactGate

    authority = load_authority(interface_path)
    mutated_contract = copy.deepcopy(authority.contact_contract)
    mutated_contract["physical_contact_kernel_authorized"] = True
    mutated_authority = _with_contact_contract(authority, mutated_contract)
    decision = PhysicalContactGate.evaluate(mutated_authority)
    assert _decision_allows_physical_contact(decision) is False


def test_populating_parameters_cannot_override_missing_frames_and_structural_path(
    interface_path: Path,
) -> None:
    from src.authority import load_authority
    from src.contact_gate import PhysicalContactGate

    authority = load_authority(interface_path)
    mutated_contract = copy.deepcopy(authority.contact_contract)
    for parameter in _estimated_parameters(mutated_contract).values():
        if parameter["estimate"] is None:
            parameter["estimate"] = 1.0
            parameter["standard_uncertainty"] = 0.1
            parameter["distribution"] = "NORMAL"
            parameter["degrees_of_freedom"] = 30
    mutated_contract["physical_contact_kernel_authorized"] = True
    # Deliberately leave the contact frames and load-bridge transform null.
    mutated_authority = _with_contact_contract(authority, mutated_contract)
    decision = PhysicalContactGate.evaluate(mutated_authority)
    assert _decision_allows_physical_contact(decision) is False


def test_structural_gate_is_a_computed_hold_not_a_pass_token(
    structural_gate_document: dict[str, object],
) -> None:
    assert structural_gate_document["schema"] == (
        "M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1"
    )
    assert structural_gate_document["gate_status"] == "HOLD"
    assert structural_gate_document["pass_token"] == "STRUCTURAL_ANALYSIS_READY"
    assert structural_gate_document["pass_token_issued"] is False
    assert structural_gate_document["formal_fea_authorized"] is False
    assert structural_gate_document["formal_fea_run_count"] == 0
    subgates = structural_gate_document["mandatory_subgates"]
    assert isinstance(subgates, dict) and len(subgates) == 8
    assert all(
        str(status).startswith(("HOLD", "PENDING")) for status in subgates.values()
    )
    assert not any(status == "PASS" for status in subgates.values())
    assert "every mandatory subgate is PASS" in structural_gate_document["rule"]


@pytest.mark.parametrize(
    ("document_name", "mutation"),
    (
        (
            "CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml",
            "contact_force_zero_fill",
        ),
        (
            "M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1.json",
            "formal_fea_promotion",
        ),
    ),
)
def test_authority_loader_rejects_contact_or_structural_promotion(
    interface_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    document_name: str,
    mutation: str,
) -> None:
    import src.authority as authority_module

    real_load_mapping = authority_module._load_mapping

    def mutated_load(path: Path) -> object:
        document = real_load_mapping(path)
        if path.name != document_name:
            return document
        document = copy.deepcopy(document)
        if mutation == "contact_force_zero_fill":
            document["computed_contact_force_N"] = 0.0
        else:
            document["gate_status"] = "PASS"
            document["pass_token_issued"] = True
            document["formal_fea_authorized"] = True
        return document

    monkeypatch.setattr(authority_module, "_load_mapping", mutated_load)
    with pytest.raises(authority_module.AuthorityError):
        authority_module.load_authority(interface_path)


def test_analytic_completion_does_not_unlock_formal_fea(
    structural_gate_document: dict[str, object],
) -> None:
    completed = structural_gate_document["analytic_work_completed"]
    assert set(completed) == {
        "B601 mesh frame localization",
        "diagnostic impulse input chain",
        "six-DOF fastener-group influence matrices",
    }
    assert structural_gate_document["gate_status"] == "HOLD"
    assert structural_gate_document["formal_fea_authorized"] is False
    assert structural_gate_document["formal_fea_run_count"] == 0
