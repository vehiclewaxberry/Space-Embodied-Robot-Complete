from __future__ import annotations

import sys
from pathlib import Path

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


@pytest.fixture(scope="session")
def snapshot():
    from mechanical_admission.strict_io import load_default_snapshot

    return load_default_snapshot()


@pytest.fixture(scope="session")
def evaluation(snapshot):
    from mechanical_admission.evaluator import evaluate_snapshot

    return evaluate_snapshot(snapshot)
