# -*- coding: utf-8 -*-
"""Freeze the complete V4 successor scope without circular self-hashes."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
V4 = ROOT / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
F3R2_TOP = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM"
F3R1_TOP = ROOT / "20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM"
MANIFEST = V4 / "11_release/MFINAL_SCOPE_MANIFEST_SHA256.txt"
RECEIPT = V4 / "11_release/MFINAL_RELEASE_RECEIPT.json"
EXCLUDED = {
    MANIFEST.relative_to(V4).as_posix().lower(),
    RECEIPT.relative_to(V4).as_posix().lower(),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def main():
    rows = []
    for path in sorted((item for item in V4.rglob("*") if item.is_file()), key=lambda item: item.relative_to(V4).as_posix().lower()):
        relative = path.relative_to(V4).as_posix()
        if relative.lower() in EXCLUDED:
            continue
        if relative.lower().startswith("12_history/"):
            continue
        if "__pycache__" in path.parts or path.suffix.lower() == ".pyc":
            continue
        rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(f"{row['sha256']}  {row['bytes']}  {row['path']}\n")
    extensions = Counter(Path(row["path"]).suffix.lower() or "<none>" for row in rows)
    gate = json.loads((V4 / "11_release/MFINAL_GATE.json").read_text(encoding="utf-8"))
    validation = json.loads((V4 / "10_validation/MFINAL_INDEPENDENT_VALIDATION.json").read_text(encoding="utf-8"))
    receipt = {
        "schema": "MFINAL_RELEASE_RECEIPT_V1",
        "baseline": V4.name,
        "scope_manifest": MANIFEST.relative_to(V4).as_posix(),
        "scope_manifest_sha256": sha256(MANIFEST),
        "scope_manifest_rows": len(rows),
        "scope_bytes": sum(row["bytes"] for row in rows),
        "extension_counts": dict(sorted(extensions.items())),
        "gate_verdict": gate["machine_verdict"],
        "static_validation_verdict": validation["verdict"],
        "static_validation_pass_count": validation["pass_count"],
        "static_validation_fail_count": validation["fail_count"],
        "frozen_parent_tops": [
            {"path": str(F3R2_TOP).replace("\\", "/"), "sha256": sha256(F3R2_TOP)},
            {"path": str(F3R1_TOP).replace("\\", "/"), "sha256": sha256(F3R1_TOP)},
        ],
        "native_files_created": 0,
        "solidworks_preflight": "INSUFFICIENT_MEMORY_HOLD",
        "release_scope": "STATIC_NEUTRAL_MECHANICAL_DESIGN_BASIS_ONLY",
        "verdict": "MFINAL_SCOPE_HASH_CLOSED_WITH_NATIVE_RELEASE_HOLD",
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
