from __future__ import annotations

import sys
from pathlib import Path

import pytest


PHASE = Path(__file__).resolve().parent.parent
if str(PHASE) not in sys.path:
    sys.path.insert(0, str(PHASE))

import validate_phase_b4g_r1_contract as validator


@pytest.fixture(scope="session")
def bindings():
    return validator.load_json(validator.SOURCE_BINDINGS)


@pytest.fixture(scope="session")
def closure_contract():
    return validator.load_json(validator.CLOSURE_CONTRACT)


@pytest.fixture(scope="session")
def raw_analysis(bindings, closure_contract):
    return validator.analyze_preserved_raw(bindings, closure_contract)
