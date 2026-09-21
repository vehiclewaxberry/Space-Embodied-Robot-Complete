#!/usr/bin/env python3
"""Write a deterministic SHA-256 manifest for additive M3R deliverables.

The frozen F3R1/F3R2 evidence is not repackaged.  This manifest covers only the
new authority-recovery, adapter-candidate, path-repair, G33 addendum, mass,
asset-register and current-entry updates.  The manifest excludes itself.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
F3R2 = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
M3 = F3R2 / "03_native_cad/M3_interface_authority"
OUT = M3 / "M3R_SCOPE_MANIFEST_SHA256.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> int:
    files = [p for p in M3.rglob("*") if p.is_file() and p != OUT]
    files.extend([
        F3R2 / "99_tools/f3r2_path_resolver.py",
        F3R2 / "99_tools/test_f3r2_path_resolver.py",
        F3R2 / "99_tools/m3r_evidence_inventory.py",
        F3R2 / "99_tools/m3r_build_adapter_freecad.py",
        F3R2 / "99_tools/m3r_solidworks_native.py",
        F3R2 / "99_tools/m3r_g33a_gripper_addendum.py",
        F3R2 / "99_tools/m3r_scope_manifest.py",
        F3R2 / "08_camera_harness/F3R2_GRIPPER_FINGER_BINDING_ADDENDUM_M3R.json",
        F3R2 / "08_camera_harness/F3R2_GRIPPER_STATE_REGISTER_ADDENDUM_M3R.csv",
        F3R2 / "08_camera_harness/F3R2_GRIPPER_FINGER_BINDING_ADDENDUM_M3R_V2.json",
        F3R2 / "08_camera_harness/F3R2_GRIPPER_STATE_REGISTER_ADDENDUM_M3R_V2.csv",
        F3R2 / "10_digital_thread/M3R_ADAPTER_PROVISIONAL_MASS_ADDENDUM.csv",
        F3R2 / "15_change_control/M3R_REMAINING_REQUIRED_ASSET_REGISTER.csv",
        # Historical entry updates were merged during root consolidation.
        # A future manifest is a new scope snapshot, not the frozen M3R receipt.
        ROOT / "01_project/competition/archive/ROOT_HISTORY_20260729_20260810.md",
        ROOT / "01_project/PL1_MAINLINE_20260808/PL1-B/MECHANICAL_ENGINEERING_MAINLINE.md",
        ROOT / "01_project/PL1_MAINLINE_20260808/PL1-B/MECHANICAL_CURRENT_STATUS.md",
        ROOT / "01_project/PL1_MAINLINE_20260808/PL1-B/F3R2_EXECUTION_ORDER.md",
        ROOT / "01_project/PL1_MAINLINE_20260808/PL1-B/B601_DIGITAL_THREAD_MAP.yaml",
    ])
    unique = {}
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
        unique[str(path.resolve()).lower()] = path.resolve()
    rows = []
    for path in sorted(unique.values(), key=lambda p: p.as_posix().lower()):
        rel = path.relative_to(ROOT).as_posix()
        rows.append(f"{sha256(path)}  {path.stat().st_size:>12d}  {rel}")
    header = [
        "# M3R_SCOPE_MANIFEST_SHA256_V1",
        "# SHA256  BYTES  PROJECT_RELATIVE_PATH",
        f"# FILE_COUNT {len(rows)}",
    ]
    OUT.write_text("\n".join(header + rows) + "\n", encoding="utf-8")
    print(f"manifest={OUT}")
    print(f"files={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
