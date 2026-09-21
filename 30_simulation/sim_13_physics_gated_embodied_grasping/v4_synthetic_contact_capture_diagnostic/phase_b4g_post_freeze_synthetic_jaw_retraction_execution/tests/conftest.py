from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


PHASE_ROOT = Path(__file__).resolve().parents[1]
if str(PHASE_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_ROOT))


@pytest.fixture(scope="session")
def phase_root() -> Path:
    return PHASE_ROOT


@pytest.fixture(scope="session")
def project_root(phase_root: Path) -> Path:
    return phase_root.parents[3]


@pytest.fixture(scope="session")
def contracts(phase_root: Path) -> dict[str, dict]:
    names = {
        "authorization": "PHASE_B4G_POST_FREEZE_WORK_AUTHORIZATION_V1.json",
        "run_spec": "PHASE_B4G_RUN_SPEC_V1.json",
        "schedule": "PHASE_B4G_REGISTERED_SCHEDULE_V1.json",
        "reference_force": "PHASE_B4G_REFERENCE_FORCE_V1.json",
        "mutations": "PHASE_B4G_MUTATION_HARNESS_SPEC_V1.json",
        "governance": "PHASE_B4G_GOVERNANCE_V1.json",
        "schema": "PHASE_B4G_EVIDENCE_SCHEMA_V1.json",
        "bindings": "PHASE_B4G_SOURCE_BINDINGS_V1.json",
    }
    return {
        key: json.loads((phase_root / "contracts" / name).read_text(encoding="utf-8"))
        for key, name in names.items()
    }
