# -*- coding: utf-8 -*-
"""Create the hash-bound input contract for the future attach-only SW round."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
V4 = ROOT / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
F3R2 = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
BUILD = V4 / "10_validation/MFINAL_FREECAD_BUILD_RECEIPT.json"
OUT = V4 / "99_tools/MFINAL_SOLIDWORKS_INPUT_MANIFEST.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def source(role: str, path: Path):
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "role": role,
        "path": str(path).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main():
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    inputs = []
    part_names = []
    for package in build["packages"]:
        for part in package.get("parts", []):
            steps = [Path(path) for path in part.get("outputs", []) if str(path).lower().endswith(".step")]
            if len(steps) != 1:
                raise ValueError(f"{part['part_number']} does not have exactly one STEP")
            inputs.append(source(f"NEUTRAL_{part['part_number']}", steps[0]))
            part_names.append(part["part_number"])
    inputs.extend(
        [
            source(
                "FROZEN_PARENT_TOP_ASSEMBLY",
                F3R2 / "03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM",
            ),
            source(
                "GRIPPER_58_SOLID_NATIVE_DONOR",
                F3R2
                / "03_native_cad/B601_ARM_B51_COPY/inputs/vendor_link_parts/B51_REF_gripper_detail_LINKLOCAL.SLDPRT",
            ),
        ]
    )
    templates = [
        source("PART_TEMPLATE", Path("F:/Windows_profile/solidworks/DocumentTemplates/零件.PRTDOT")),
        source("ASSEMBLY_TEMPLATE", Path("F:/Windows_profile/solidworks/DocumentTemplates/装配体.asmdot")),
        source("A3_DRAWING_TEMPLATE", Path("F:/Windows_profile/solidworks/DocumentTemplates/A3工程图.drwdot")),
        source("BOM_TEMPLATE", Path("F:/Windows_profile/solidworks/BOMTemplates/材料明细表.sldbomtbt")),
    ]
    expected = [
        {"role": f"NATIVE_{name}", "relative_path": f"native/parts/{name}.SLDPRT"}
        for name in part_names
    ]
    for name in ("V4_GRIPPER_PALM", "V4_GRIPPER_LEFT", "V4_GRIPPER_RIGHT"):
        expected.append({"role": f"NATIVE_{name}", "relative_path": f"native/gripper/{name}.SLDPRT"})
    expected.extend(
        [
            {"role": "V4_GRIPPER_ASSEMBLY", "relative_path": "native/gripper/V4_GRIPPER_ASSEMBLY.SLDASM"},
            {"role": "V4_PRIMARY_ASSEMBLY", "relative_path": "native/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE.SLDASM"},
            {"role": "STAGE_A_DRAWING", "relative_path": "drawings/V4_B601_STAGE_A_INTERFACE_RING_REVB.SLDDRW"},
            {"role": "STAGE_A_PDF", "relative_path": "drawings/V4_B601_STAGE_A_INTERFACE_RING_REVB.pdf"},
            {"role": "STAGE_B_DRAWING", "relative_path": "drawings/V4_B601_STAGE_B_LOAD_ADAPTER_REVB2.SLDDRW"},
            {"role": "STAGE_B_PDF", "relative_path": "drawings/V4_B601_STAGE_B_LOAD_ADAPTER_REVB2.pdf"},
            {"role": "TOP_DRAWING", "relative_path": "drawings/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE.SLDDRW"},
            {"role": "TOP_DRAWING_PDF", "relative_path": "drawings/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE.pdf"},
            {"role": "NATIVE_BOM", "relative_path": "bom/F3R2_V4_NATIVE_BOM.csv"},
            {"role": "NATIVE_VALIDATION_RECEIPT", "relative_path": "evidence/F3R2_V4_NATIVE_VALIDATION.json"},
        ]
    )
    payload = {
        "schema": "F3R2_V4_SOLIDWORKS_ATTACH_INPUT_V1",
        "run_id": "MFINAL_NATIVE_R01",
        "package_relative_root": "package",
        "inputs": inputs,
        "templates": templates,
        "expected_outputs": expected,
        "primary_document": "native/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE.SLDASM",
        "minimum_dependency_count": 23,
        "authority_note": "This is an input/output contract, not permission to bypass resource, attach-only, native build, cold-reopen or human gates.",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "inputs": len(inputs),
        "templates": len(templates),
        "expected_outputs": len(expected),
        "manifest": str(OUT),
        "sha256": sha256(OUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
