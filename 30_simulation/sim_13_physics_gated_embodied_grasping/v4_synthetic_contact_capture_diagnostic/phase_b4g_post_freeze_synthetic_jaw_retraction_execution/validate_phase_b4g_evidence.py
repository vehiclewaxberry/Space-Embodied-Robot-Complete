"""Read-only command line entry point for the independent B4G validator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PHASE_ROOT = Path(__file__).resolve().parent
if str(PHASE_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_ROOT))

from b4g_validation import validate_b4g  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only fail-closed validation of B4G evidence.")
    parser.add_argument(
        "--mode", choices=("contracts", "campaign", "full"), default="full",
        help="contracts=preflight; campaign=144-slot evidence; full=campaign plus 65 mutations",
    )
    arguments = parser.parse_args()
    report = validate_b4g(mode=arguments.mode)
    print(json.dumps(report.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
