from __future__ import annotations

import json
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]
CONTRACTS = HERE / "contracts"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def model_contract() -> dict:
    return load_json(CONTRACTS / "PHASE_B4_MODEL_CONTRACT_V1.json")


@pytest.fixture(scope="session")
def governance_contract() -> dict:
    return load_json(CONTRACTS / "PHASE_B4_GOVERNANCE_CONTRACT_V1.json")


@pytest.fixture(scope="session")
def units_ledger() -> dict:
    return load_json(CONTRACTS / "PHASE_B4_UNCERTAINTY_AND_UNITS_LEDGER_V1.json")


@pytest.fixture(scope="session")
def numerical_contract() -> dict:
    return load_json(CONTRACTS / "PHASE_B4_NUMERICAL_ACCEPTANCE_CONTRACT_V1.json")


@pytest.fixture(scope="session")
def source_bindings() -> dict:
    return load_json(CONTRACTS / "PHASE_B4_SOURCE_BINDINGS_V1.json")
