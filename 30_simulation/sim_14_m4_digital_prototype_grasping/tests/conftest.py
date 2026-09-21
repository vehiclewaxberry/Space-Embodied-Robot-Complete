from __future__ import annotations

from pathlib import Path

import pytest

from src.contracts import ExecutionMode
from src.env import ANCHOR_22KG, M4DigitalPrototypeGraspingEnv
from src.interface_loader import DIAGNOSTIC_ACKNOWLEDGEMENT


SIM14_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SIM14_ROOT.parents[1]
INTERFACE_PATH = (
    PROJECT_ROOT
    / "20_engineering"
    / "F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1"
    / "08_simulation_assets"
    / "MECH_RL_INTERFACE_V2.yaml"
)
DIAGNOSTIC_FIXTURE_PATH = (
    SIM14_ROOT / "config" / "SIM14_DIAGNOSTIC_FIXTURE_V1.json"
)


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def mechanical_interface_path() -> Path:
    return INTERFACE_PATH


@pytest.fixture(scope="session")
def diagnostic_fixture_path() -> Path:
    return DIAGNOSTIC_FIXTURE_PATH


@pytest.fixture
def diagnostic_env(
    mechanical_interface_path: Path,
    diagnostic_fixture_path: Path,
) -> M4DigitalPrototypeGraspingEnv:
    return M4DigitalPrototypeGraspingEnv(
        mechanical_interface_path,
        execution_mode=ExecutionMode.BOUNDED_DIAGNOSTIC,
        diagnostic_fixture_path=diagnostic_fixture_path,
        diagnostic_acknowledgement=DIAGNOSTIC_ACKNOWLEDGEMENT,
        anchor_id=ANCHOR_22KG,
    )
