#!/usr/bin/env python3
"""Independent FreeCAD source re-extraction; imports no package builder code."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import FreeCAD as App


PACKAGE = Path(__file__).resolve().parents[1]


def root() -> Path:
    return next(candidate for candidate in (PACKAGE, *PACKAGE.parents) if (candidate / "PROJECT_MAP.md").is_file())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise RuntimeError("independent extraction directory must be empty")
    contract = json.loads((PACKAGE / "00_contract/LINK1_B6_OPERATIONAL_COLLISION_CONTRACT_V1.json").read_text(encoding="utf-8"))
    lock = json.loads((PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json").read_text(encoding="utf-8"))
    pin = next(row for row in lock["source_pins"] if row["id"] == "v9f_fcstd")
    source = root() / pin["path"]
    if source.stat().st_size != pin["bytes"] or sha256(source) != pin["sha256"]:
        raise RuntimeError("independent V9F FCStd pin verification failed")
    document = App.openDocument(str(source))
    try:
        by_label = {}
        for obj in document.Objects:
            if str(obj.Label) in by_label:
                raise RuntimeError(f"duplicate FCStd label: {obj.Label}")
            by_label[str(obj.Label)] = obj
        rows = []
        for index, spec in enumerate(contract["objects"]):
            obj = by_label.get(spec["source_label"])
            if obj is None or str(obj.Name) != spec["source_internal_name"]:
                raise RuntimeError(f"independent selector mismatch: {spec['object_id']}")
            shape = obj.Shape
            if shape is None or shape.isNull() or not shape.isValid() or not shape.isClosed() or len(shape.Solids) != 1 or float(shape.Volume) <= 0:
                raise RuntimeError(f"independent invalid source Shape: {spec['object_id']}")
            path = output / f"{index:02d}_{spec['source_internal_name']}.brep"
            shape.exportBrep(str(path))
            box = shape.BoundBox
            rows.append({
                "object_id": spec["object_id"], "source_label": str(obj.Label), "source_internal_name": str(obj.Name),
                "object_placement_reapplied": False, "source_volume_mm3": float(shape.Volume),
                "source_bbox_mm": [[float(box.XMin), float(box.YMin), float(box.ZMin)], [float(box.XMax), float(box.YMax), float(box.ZMax)]],
                "brep": {"filename": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)},
            })
        if len(rows) != 6:
            raise RuntimeError("independent extractor selection count drift")
        print(json.dumps({
            "schema": "ROUTE_C_LINK1_B6_INDEPENDENT_SOURCE_REEXTRACTION_V1",
            "generated_utc": "DETERMINISTIC_VALIDATION_NO_WALLCLOCK",
            "source_opened_read_only": True, "source_saved": False, "source_recomputed": False,
            "object_placement_reapplied": False, "objects": rows,
            "verdict": "INDEPENDENT_SOURCE_REEXTRACTION_6_OF_6_PASS",
        }, indent=2, sort_keys=True), end="\n")
    finally:
        App.closeDocument(document.Name)


if __name__ == "__main__":
    main()
