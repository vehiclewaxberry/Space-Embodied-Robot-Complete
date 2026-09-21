#!/usr/bin/env python3
"""Build a deterministic, non-circular manifest for the isolated Link2-B12 package."""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
OUTPUT = PACKAGE / "05_results/PACKAGE_MANIFEST_V1.csv"
EXCLUDED = {
    OUTPUT.resolve(),
    (PACKAGE / "05_results/PACKAGE_INVENTORY_V1.json").resolve(),
    (PACKAGE / "05_results/LOCAL_CANDIDATE_GATE_V1.json").resolve(),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def role(path: Path) -> tuple[str, str]:
    relative = path.relative_to(PACKAGE).as_posix()
    head = relative.split("/", 1)[0]
    if relative == "README.md":
        return "PACKAGE_DOCUMENT", "NAVIGATION_ONLY"
    if head == "00_contract":
        return "FROZEN_LOCAL_CONTRACT", "LOCAL_CANDIDATE_INPUT_CONTRACT"
    if head == "01_cad":
        return "PRIMARY_STEP_CANDIDATE", "LOCAL_LINK2_Q0_GEOMETRY_CANDIDATE"
    if head == "02_builder":
        return "BUILDER_SOURCE", "IMPLEMENTATION_NO_SYSTEM_CREDIT"
    if head == "02_runtime":
        return "DERIVED_RUNTIME_SIDECAR", "LOCAL_CANDIDATE_DERIVATIVE"
    if head == "04_validation":
        return "VALIDATION_SOURCE", "INDEPENDENT_OR_REPLAY_IMPLEMENTATION"
    if head == "05_results":
        return "EVIDENCE_RECEIPT", "LOCAL_CANDIDATE_EVIDENCE"
    if head == "06_tests":
        return "TEST_SOURCE", "LOCAL_VERIFICATION"
    if head == "07_reviews":
        return "DIAGNOSTIC_REVIEW", "LOCAL_DIAGNOSTIC_ZERO_SYSTEM_CREDIT"
    raise RuntimeError(f"unclassified package file: {relative}")


def main() -> None:
    files = sorted(path for path in PACKAGE.rglob("*") if path.is_file() and path.resolve() not in EXCLUDED)
    forbidden = [path for path in files if path.suffix.lower() in {".glb", ".tmp"} or "__pycache__" in path.parts]
    if forbidden:
        raise RuntimeError(f"forbidden cache/temp file in manifest: {forbidden}")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["path", "bytes", "sha256", "role", "authority"])
    for path in files:
        file_role, authority = role(path)
        writer.writerow([path.relative_to(PACKAGE).as_posix(), path.stat().st_size, sha(path), file_role, authority])
    data = stream.getvalue().encode("utf-8")
    temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(OUTPUT)
    print(f"manifest_rows={len(files)} bytes={len(data)} sha256={hashlib.sha256(data).hexdigest().upper()}")


if __name__ == "__main__":
    main()
