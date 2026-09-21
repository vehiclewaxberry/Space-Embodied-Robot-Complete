from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


PHASE_ROOT = Path(__file__).resolve().parents[1]
if str(PHASE_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_ROOT))

import b4_solver.constraint_solver as solver  # noqa: E402


@pytest.fixture(scope="session")
def primary_event():
    return solver.extract_frozen_primary_event()


@pytest.fixture(scope="session")
def primary_run(primary_event):
    return solver.execute_run(primary_event)


@pytest.fixture(scope="session")
def primary_acquisition(primary_run):
    return primary_run.acquisition


@pytest.fixture(scope="session")
def phase_root() -> Path:
    return PHASE_ROOT


@pytest.fixture(scope="session")
def read_json():
    def read(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))
    return read
