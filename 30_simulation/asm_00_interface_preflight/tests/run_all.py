"""Run the complete ASM-00 preflight test suite."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


def main() -> int:
    test_dir = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(
        str(test_dir), pattern="test_*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
