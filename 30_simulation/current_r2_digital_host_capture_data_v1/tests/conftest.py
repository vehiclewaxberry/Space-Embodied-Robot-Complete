import sys
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parents[1]
sys.path.insert(0, str(MODULE_ROOT / "src"))

ACCEPTED_URDF = (
    REPO_ROOT / "20_engineering" / "cad" / "spacecraft_layout" / "arm_b601_v1" / "arm_b601_v1.urdf"
)
SERVICER_URDF = (
    REPO_ROOT / "20_engineering" / "cad" / "spacecraft_layout" / "servicer_12U_v0" / "servicer_12U_v0.urdf"
)


@pytest.fixture(scope="session")
def accepted_urdf_path():
    assert ACCEPTED_URDF.is_file(), f"accepted URDF missing: {ACCEPTED_URDF}"
    return str(ACCEPTED_URDF)


@pytest.fixture(scope="session")
def servicer_urdf_path():
    assert SERVICER_URDF.is_file(), f"servicer URDF missing: {SERVICER_URDF}"
    return str(SERVICER_URDF)


@pytest.fixture(scope="session")
def arm_model(accepted_urdf_path):
    from dh_v1.urdf_extract import extract_urdf

    return extract_urdf(accepted_urdf_path)


@pytest.fixture(scope="session")
def arm_plant(arm_model):
    from dh_v1.plant import FloatingPlant

    return FloatingPlant(arm_model)
