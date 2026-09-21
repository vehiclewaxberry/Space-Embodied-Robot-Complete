# -*- coding: utf-8 -*-
"""Independent STEP reopen and geometric-equivalence audit for M3R V2.

Run with FreeCADCmd after M3R_BUILD_INTERFACE_ASSEMBLY_V2.py.  The audit only
checks B-rep integrity/equivalence; it is not FEA, physical fit-up or release.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import FreeCAD
import Import


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RECEIPT = HERE / "M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION.json"

PAIRS = [
    {
        "part": "STAGE_A",
        "reference": ROOT / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/02_neutral_cad/adapter/V4_B601_STAGE_A_INTERFACE_RING_REVB.step",
        "working": HERE / "M3R_STAGE_A_REVB_WORKING.step",
    },
    {
        "part": "STAGE_B",
        "reference": ROOT / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/02_neutral_cad/adapter/V4_B601_STAGE_B_LOAD_ADAPTER_REVB2.step",
        "working": HERE / "M3R_STAGE_B_REVB2_WORKING.step",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_single_shape(path: Path, doc_name: str):
    doc = FreeCAD.newDocument(doc_name)
    Import.insert(str(path), doc.Name)
    doc.recompute()
    objects = [obj for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
    if len(objects) != 1:
        FreeCAD.closeDocument(doc.Name)
        raise RuntimeError(f"expected one shape object in {path}, found {len(objects)}")
    shape = objects[0].Shape.copy()
    FreeCAD.closeDocument(doc.Name)
    return shape


def bounds(shape) -> list[float]:
    box = shape.BoundBox
    return [
        round(box.XMin, 9),
        round(box.YMin, 9),
        round(box.ZMin, 9),
        round(box.XMax, 9),
        round(box.YMax, 9),
        round(box.ZMax, 9),
    ]


def main() -> None:
    records = []
    failures = []
    for index, pair in enumerate(PAIRS):
        for key in ("reference", "working"):
            if not pair[key].is_file():
                raise RuntimeError(f"missing {key} STEP: {pair[key]}")
        reference = load_single_shape(pair["reference"], f"REF_{index}")
        working = load_single_shape(pair["working"], f"WORK_{index}")
        reference_minus_working = reference.cut(working).Volume
        working_minus_reference = working.cut(reference).Volume
        common_volume = reference.common(working).Volume
        minimum_distance = reference.distToShape(working)[0]
        volume_delta = working.Volume - reference.Volume
        equivalent = (
            reference.isValid()
            and working.isValid()
            and len(reference.Solids) == 1
            and len(working.Solids) == 1
            and abs(volume_delta) <= 1.0e-6
            and reference_minus_working <= 1.0e-7
            and working_minus_reference <= 1.0e-7
            and minimum_distance <= 1.0e-7
        )
        if not equivalent:
            failures.append(pair["part"])
        records.append(
            {
                "part": pair["part"],
                "reference_path": str(pair["reference"].relative_to(ROOT)).replace("\\", "/"),
                "reference_sha256": sha256(pair["reference"]),
                "working_path": pair["working"].name,
                "working_sha256": sha256(pair["working"]),
                "reference_valid": reference.isValid(),
                "working_valid": working.isValid(),
                "reference_solid_count": len(reference.Solids),
                "working_solid_count": len(working.Solids),
                "reference_volume_mm3": round(reference.Volume, 9),
                "working_volume_mm3": round(working.Volume, 9),
                "volume_delta_mm3": round(volume_delta, 12),
                "reference_bounds_mm": bounds(reference),
                "working_bounds_mm": bounds(working),
                "reference_minus_working_volume_mm3": round(reference_minus_working, 12),
                "working_minus_reference_volume_mm3": round(working_minus_reference, 12),
                "common_volume_mm3": round(common_volume, 9),
                "minimum_distance_mm": round(minimum_distance, 12),
                "geometrically_equivalent": equivalent,
            }
        )

    receipt = {
        "schema": "M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION_V1",
        "mode": "INDEPENDENT_STEP_REOPEN_AND_BOOLEAN_EQUIVALENCE",
        "tool": "FreeCADCmd / OpenCascade Import",
        "parts": records,
        "failed_parts": failures,
        "formal_fea_performed": False,
        "physical_fitup_performed": False,
        "verdict": "PASS_WORKING_GEOMETRY_EQUIVALENT_TO_PINNED_REVB2" if not failures else "HOLD_GEOMETRY_DIFFERENCE",
        "release_status": "HOLD_NOT_MANUFACTURING_OR_FLIGHT_RELEASE",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise RuntimeError(f"geometric equivalence failed: {failures}")


main()
