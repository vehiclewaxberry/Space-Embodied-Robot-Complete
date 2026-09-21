from __future__ import annotations

import argparse
from pathlib import Path

from system_binding_candidate.evaluator import (
    GATE_REL,
    MANIFEST_REL,
    PACKAGE_ROOT,
    RECEIPT_REL,
    build_outputs,
    sha256_bytes,
)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the read-only Unified R2 System Binding V2 research candidate.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write deterministic receipt, gate and manifest")
    mode.add_argument("--check", action="store_true", help="verify committed outputs are byte-identical")
    args = parser.parse_args()
    receipt, gate, manifest = build_outputs()
    expected = {RECEIPT_REL: receipt, GATE_REL: gate, MANIFEST_REL: manifest}
    if args.write:
        for rel, data in expected.items():
            _write(PACKAGE_ROOT / rel, data)
            print(f"WROTE {rel.as_posix()} {sha256_bytes(data)} {len(data)}")
        return 0
    stale = []
    for rel, data in expected.items():
        path = PACKAGE_ROOT / rel
        if not path.is_file() or path.read_bytes() != data:
            stale.append(rel.as_posix())
    if stale:
        print("FAIL stale or missing deterministic outputs: " + ", ".join(stale))
        return 2
    print("PASS deterministic outputs byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
