from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


@pytest.fixture
def tmp_path():
    """Workspace-local temporary root; removed after every test.

    The host's default pytest temp root is ACL-denied in this Windows image.
    """

    with TemporaryDirectory(prefix=".r2_raw_test_", dir=PACKAGE_ROOT) as directory:
        yield Path(directory)
