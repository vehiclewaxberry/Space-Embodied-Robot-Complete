from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml


SIM15_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SIM15_ROOT.parents[1]
M5_ROOT = (
    PROJECT_ROOT
    / "20_engineering"
    / "F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1"
)
INTERFACE_PATH = (
    M5_ROOT / "07_simulation_handoff" / "MECH_DYNAMICS_INTERFACE_V3.yaml"
)
CONFIGURATION_CONTRACT_PATH = (
    M5_ROOT
    / "02_configurations"
    / "M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml"
)
JOINT_MODEL_PATH = (
    M5_ROOT / "04_joint_load_model" / "M5_ANALYTIC_JOINT_LOAD_MODEL_V1.yaml"
)
CONTACT_CONTRACT_PATH = (
    M5_ROOT
    / "05_contact_identification"
    / "CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml"
)
STRUCTURAL_GATE_PATH = (
    M5_ROOT
    / "06_structural_entry"
    / "M5_STRUCTURAL_ANALYSIS_ENTRY_GATE_V1.json"
)
PHASE_AUTHORITY_PATH = (
    M5_ROOT / "00_authority" / "M5_PHASE_AUTHORITY_AND_BOUNDARY.yaml"
)
RELEASE_GATE_PATH = (
    M5_ROOT / "12_release" / "M5_GEOMETRY_AND_LOADS_CLOSURE_GATE_V1.json"
)

DIAGNOSTIC_ACKNOWLEDGEMENT = (
    "I_ACKNOWLEDGE_M5_VALUES_ARE_DIAGNOSTIC_NOT_PHYSICAL_CONTACT_OR_FLIGHT_AUTHORITY"
)
REQUIRED_CONFIGURATION_IDS = tuple(f"C{index:02d}" for index in range(1, 10))


# Put the simulation package ahead of sibling simulations that also expose a
# top-level ``src`` package.
if str(SIM15_ROOT) not in sys.path:
    sys.path.insert(0, str(SIM15_ROOT))


def load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    document = (
        json.loads(text)
        if path.suffix.casefold() == ".json"
        else yaml.safe_load(text)
    )
    assert isinstance(document, dict), f"{path} must contain a mapping"
    return document


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def public_mapping(value: Any) -> Mapping[str, Any]:
    """Normalize result objects without coupling tests to one container type."""

    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        mapped = value.to_dict()
        assert isinstance(mapped, Mapping)
        return mapped
    if hasattr(value, "as_dict"):
        mapped = value.as_dict()
        assert isinstance(mapped, Mapping)
        return mapped
    if hasattr(value, "__dict__"):
        return vars(value)
    raise AssertionError(f"unsupported public result type: {type(value)!r}")


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def m5_root() -> Path:
    return M5_ROOT


@pytest.fixture(scope="session")
def interface_path() -> Path:
    return INTERFACE_PATH


@pytest.fixture(scope="session")
def interface_document() -> dict[str, Any]:
    return load_mapping(INTERFACE_PATH)


@pytest.fixture(scope="session")
def configuration_document() -> dict[str, Any]:
    return load_mapping(CONFIGURATION_CONTRACT_PATH)


@pytest.fixture(scope="session")
def joint_model_document() -> dict[str, Any]:
    return load_mapping(JOINT_MODEL_PATH)


@pytest.fixture(scope="session")
def contact_document() -> dict[str, Any]:
    return load_mapping(CONTACT_CONTRACT_PATH)


@pytest.fixture(scope="session")
def structural_gate_document() -> dict[str, Any]:
    return load_mapping(STRUCTURAL_GATE_PATH)

