from __future__ import annotations

from pathlib import Path
import sys
import tempfile

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


@pytest.fixture
def tmp_path():
    """Use a package-local, auto-removed root; the host TEMP ACL is unusable."""

    with tempfile.TemporaryDirectory(prefix=".technical-fixture-", dir=PACKAGE_ROOT) as directory:
        yield Path(directory)
