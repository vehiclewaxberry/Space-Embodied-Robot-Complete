#!/usr/bin/env python3
"""Run the frozen M4-L02 falsification-control set without changing parent state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_configuration_contract import (
    NEGATIVE_FILE,
    PACKAGE,
    canonical_json_bytes,
    run_negative_controls,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = run_negative_controls()
    payload = canonical_json_bytes(result)
    path = PACKAGE / NEGATIVE_FILE
    if args.write:
        path.write_bytes(payload)
    if args.check:
        if not path.exists() or path.read_bytes() != payload:
            print("FAIL negative-control receipt mismatch")
            return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))
    else:
        print(f"{'PASS' if result['summary']['all_caught'] else 'FAIL'} {result['summary']['passed']}/{result['summary']['total']}")
    return 0 if result["summary"]["all_caught"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
