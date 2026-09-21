from __future__ import annotations

import pytest

from crossbind.constants import EXACT_DIRECTORY_ALLOWLIST, EXACT_FILE_ALLOWLIST
from crossbind.negative_controls import run_negative_controls
from crossbind.strict_io import StrictIOError, validate_inventory_sets


def test_all_negative_controls_reject(bundle, record):
    controls = run_negative_controls(bundle, record)
    assert len(controls) == 67
    assert all(item["status"] == "PASS_REJECTED" for item in controls)


def test_declared_exact_inventory_is_valid():
    result = validate_inventory_sets(EXACT_FILE_ALLOWLIST, EXACT_DIRECTORY_ALLOWLIST)
    assert result["exact"] is True
    assert result["file_count"] == 30
    assert result["directory_count"] == 6


@pytest.mark.parametrize("name", ["shadow.sdf", "shadow.xacro", "robot.urdf", "shadow.step"])
def test_forbidden_generated_assets_rejected(name):
    with pytest.raises(StrictIOError, match="FORBIDDEN_ASSET"):
        validate_inventory_sets(set(EXACT_FILE_ALLOWLIST) | {name}, EXACT_DIRECTORY_ALLOWLIST)


def test_shadow_json_rejected():
    with pytest.raises(StrictIOError, match="EXTRA_FILE"):
        validate_inventory_sets(set(EXACT_FILE_ALLOWLIST) | {"shadow.json"}, EXACT_DIRECTORY_ALLOWLIST)
