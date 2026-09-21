from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def phase_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def project_root(phase_root: Path) -> Path:
    return phase_root.parents[3]


@pytest.fixture(scope="session")
def contracts(phase_root: Path) -> dict[str, dict]:
    paths = {
        "authorization": "PHASE_B4F_WORK_AUTHORIZATION_V1.json",
        "model": "PHASE_B4F_MODEL_AND_ENERGY_CONTRACT_V1.json",
        "experiment": "PHASE_B4F_EXPERIMENT_DESIGN_V1.json",
        "numerical": "PHASE_B4F_NUMERICAL_ACCEPTANCE_V1.json",
        "governance": "PHASE_B4F_GOVERNANCE_V1.json",
        "bindings": "PHASE_B4F_SOURCE_BINDINGS_V1.json",
        "schema": "PHASE_B4F_EVIDENCE_SCHEMA_V1.json",
        "inventory": "PHASE_B4F_TEST_INVENTORY_V1.json",
    }
    return {
        key: json.loads((phase_root / "contracts" / name).read_text(encoding="utf-8"))
        for key, name in paths.items()
    }

