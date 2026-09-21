#!/usr/bin/env python3
"""Temporary registration check for the existing R1 palm STEP."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AUDIT = HERE / "audit_extract_finger_breps.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("finger_audit", AUDIT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audit helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    palm = module.import_step(module.PALM_STEP)
    r1_stl = module.R1_DIR / "B601_GRIPPER_PALM_RAIL_SLOT_R1.stl"
    m5_ply = module.M5_DIR / "B601_GRIPPER_R1_PALM_GRIPPER_LINK_LOCAL_M.ply"
    report = {
        "schema": "TEMP_B601_GRIPPER_R1_PALM_REGISTRATION_PROBE_V1",
        "authority": "TEMPORARY_READ_ONLY_NO_CREDIT",
        "shape_facts": module.shape_facts(palm),
        "registration": module.mesh_comparison(palm, r1_stl, r1_stl, m5_ply),
    }
    output = HERE / "TEMP_B601_GRIPPER_R1_PALM_REGISTRATION_PROBE_V1.json"
    if output.exists():
        raise RuntimeError(f"refusing overwrite: {output}")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
