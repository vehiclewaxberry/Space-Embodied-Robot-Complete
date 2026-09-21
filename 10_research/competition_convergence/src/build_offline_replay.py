"""CLI for deterministic, no-command competition replay packaging."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evidence_contract import (
    EvidenceError,
    deterministic_json_bytes,
    repo_root_from_here,
    write_replay_package,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--scenarios", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = repo_root_from_here()
    contract_path = args.contract if args.contract.is_absolute() else root / args.contract
    scenario_path = (
        args.scenarios if args.scenarios.is_absolute() else root / args.scenarios
    )
    try:
        manifest = write_replay_package(
            contract_path, scenario_path, args.output, root
        )
    except EvidenceError as exc:
        for error in exc.errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(deterministic_json_bytes(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
