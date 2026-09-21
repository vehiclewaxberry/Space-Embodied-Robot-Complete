from __future__ import annotations

from pathlib import Path
import sys

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


def _project_root() -> Path:
    for candidate in (PACKAGE_ROOT, *PACKAGE_ROOT.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("PROJECT_ROOT_NOT_FOUND")


@pytest.fixture(scope="session")
def package_root() -> Path:
    return PACKAGE_ROOT


@pytest.fixture(scope="session")
def project_root() -> Path:
    return _project_root()


@pytest.fixture(scope="session")
def donor(project_root: Path):
    from r2_preflight.rehydrator import load_donor_fixture

    path = project_root / (
        "30_simulation/sim_13_physics_gated_embodied_grasping/"
        "v4_synthetic_contact_capture_diagnostic/"
        "phase_b4g_post_freeze_synthetic_jaw_retraction_execution/evidence/raw_cases/"
        "052__RK4_REFERENCE__A1__ALPHA_16__TCMD_MS_10.json"
    )
    return load_donor_fixture(path)
