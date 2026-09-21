"""Shared pytest fixtures for the V2 fail-closed backend package."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
V2_REBIND_ROOT = PACKAGE_ROOT.parent
PROJECT_ROOT = V2_REBIND_ROOT.parents[2]
for candidate in (str(PACKAGE_ROOT), str(V2_REBIND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)


@pytest.fixture()
def package_root() -> Path:
    return PACKAGE_ROOT


@pytest.fixture()
def project_root() -> Path:
    return PROJECT_ROOT
