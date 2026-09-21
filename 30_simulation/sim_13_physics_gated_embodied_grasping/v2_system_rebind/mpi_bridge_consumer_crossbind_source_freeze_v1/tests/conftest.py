from __future__ import annotations

from pathlib import Path

import pytest

from crossbind.bridge import build_crossbind_record
from crossbind.source_bundle import load_source_bundle


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def find_repo_root() -> Path:
    for candidate in (PACKAGE_ROOT, *PACKAGE_ROOT.parents):
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    raise RuntimeError("repository root not found")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return find_repo_root()


@pytest.fixture(scope="session")
def bundle(repo_root):
    return load_source_bundle(repo_root)


@pytest.fixture(scope="session")
def record(bundle):
    return build_crossbind_record(bundle)

