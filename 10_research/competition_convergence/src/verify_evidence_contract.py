"""CLI for strict competition evidence-contract verification."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evidence_contract import (
    EvidenceError,
    deterministic_json_bytes,
    load_and_verify,
    repo_root_from_here,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--scenarios", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = repo_root_from_here()
    contract_path = args.contract if args.contract.is_absolute() else root / args.contract
    scenario_path = (
        args.scenarios if args.scenarios.is_absolute() else root / args.scenarios
    )
    try:
        _, _, report = load_and_verify(contract_path, scenario_path, root)
    except EvidenceError as exc:
        for error in exc.errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 2
    data = deterministic_json_bytes(report)
    if args.output:
        output = args.output if args.output.is_absolute() else root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
