"""CLI for the frozen 144-slot B4G campaign orchestrator.

This workflow deliberately stops after campaign evidence.  Registered negative
controls, validation, independent audit and final signing are separate modules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PHASE_ROOT = Path(__file__).resolve().parent
if str(PHASE_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_ROOT))

from b4g_execution import B4GExecutionError, execute_campaign, execute_smoke  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute or resume the exact registered Sim13 V4B4G campaign.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--full-campaign", action="store_true",
        help="execute/resume all 144 registered logical slots in the phase evidence tree",
    )
    mode.add_argument(
        "--smoke-slot-index", type=int, metavar="INDEX",
        help="execute one unconditional slot without publication credit",
    )
    parser.add_argument(
        "--output-root", type=Path,
        help=(
            "required explicit owned diagnostic root for smoke; full campaign "
            "rejects every root other than the canonical phase root"
        ),
    )
    parser.add_argument(
        "--execution-source-freeze-terminal",
        type=Path,
        help=(
            "externally signed execution-source terminal; mandatory for --full-campaign"
        ),
    )
    parser.add_argument(
        "--expected-execution-source-freeze-terminal-sha256",
        help=(
            "expected 64-hex SHA-256 of the external terminal; mandatory for "
            "--full-campaign"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        if arguments.smoke_slot_index is not None:
            if arguments.output_root is None:
                raise B4GExecutionError("SMOKE_OUTPUT_ROOT_REQUIRED")
            result = execute_smoke(
                slot_index=arguments.smoke_slot_index,
                output_root=arguments.output_root,
            )
        else:
            result = execute_campaign(
                output_root=arguments.output_root,
                execution_source_freeze_terminal=arguments.execution_source_freeze_terminal,
                expected_execution_source_freeze_terminal_sha256=(
                    arguments.expected_execution_source_freeze_terminal_sha256
                ),
            )
    except (
        B4GExecutionError,
        RuntimeError,
        ValueError,
        OSError,
        IndexError,
        KeyboardInterrupt,
    ) as error:
        print(json.dumps({
            "status": "DIAGNOSTIC_FAIL_CLOSED_B4G_ORCHESTRATION",
            "error_type": type(error).__name__,
            "error": str(error),
            "final_artifacts_signed": False,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
