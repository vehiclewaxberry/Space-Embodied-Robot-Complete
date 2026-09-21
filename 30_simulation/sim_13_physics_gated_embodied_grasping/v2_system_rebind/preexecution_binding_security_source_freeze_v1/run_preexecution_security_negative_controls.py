#!/usr/bin/env python3
"""Print the deterministic NC15/NC16/NC20 source-only execution record."""

from __future__ import annotations

import json

from preexec_security.negative_controls import run_security_negative_controls


def main() -> int:
    result = run_security_negative_controls()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["all_requested_controls_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
