"""Deterministically derive the editable V9 FreeCAD source from frozen V8.

This is an authoring utility, not a scientific gate.  It performs only the
mechanical namespace split V8 -> V9.  Architecture and geometry changes are
then reviewed and applied to B601_ROUTE_C_BUILD_V9.py itself.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "B601_ROUTE_C_BUILD_V8.py"
TARGET = HERE / "B601_ROUTE_C_BUILD_V9.py"
SOURCE_SHA256 = "78874967B781D12F0E37F077804A2B8EEA43EFC8DBDE867CF9C6FAD2D677E0E9"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    actual = sha256(SOURCE)
    if actual != SOURCE_SHA256:
        raise SystemExit(
            f"fail-closed: frozen V8 builder hash mismatch: {actual} != {SOURCE_SHA256}"
        )
    if TARGET.exists():
        raise SystemExit(
            "fail-closed: V9 target already exists; this utility never overwrites design work"
        )

    text = SOURCE.read_text(encoding="utf-8")
    text = text.replace("V8", "V9").replace("v8", "v9")
    text = text.replace(
        "Authority: ODR-42 / ODR-52 / ODR-53 / ODR-54.",
        "Authority: ODR-42 / ODR-52 / ODR-53 / ODR-54 / ODR-58.",
    )
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"created {TARGET.name}")
    print(f"source_sha256={actual}")
    print(f"derived_sha256={sha256(TARGET)}")


if __name__ == "__main__":
    main()
