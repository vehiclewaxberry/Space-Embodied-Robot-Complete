#!/usr/bin/env python3
"""Read-only FreeCAD extraction of the exact twelve link2 V9F source Shapes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import FreeCAD as App


PACKAGE = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root not found")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def matrix(placement) -> list[list[float]]:
    value = placement.toMatrix()
    return [
        [float(value.A11), float(value.A12), float(value.A13), float(value.A14)],
        [float(value.A21), float(value.A22), float(value.A23), float(value.A24)],
        [float(value.A31), float(value.A32), float(value.A33), float(value.A34)],
        [float(value.A41), float(value.A42), float(value.A43), float(value.A44)],
    ]


def bbox(shape) -> list[list[float]]:
    box = shape.BoundBox
    return [[float(box.XMin), float(box.YMin), float(box.ZMin)], [float(box.XMax), float(box.YMax), float(box.ZMax)]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), "temporary extraction directory must be empty")
    contract = json.loads((PACKAGE / "00_contract/LINK2_B12_OPERATIONAL_COLLISION_CONTRACT_V1.json").read_text(encoding="utf-8"))
    lock = json.loads((PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json").read_text(encoding="utf-8"))
    pins = {row["id"]: row for row in lock["source_pins"]}
    source = root() / pins["v9f_fcstd"]["path"]
    require(source.stat().st_size == pins["v9f_fcstd"]["bytes"] and sha256(source) == pins["v9f_fcstd"]["sha256"], "V9F FCStd pin drift")
    document = App.openDocument(str(source))
    try:
        labels = {}
        for obj in document.Objects:
            require(str(obj.Label) not in labels, f"duplicate FCStd label: {obj.Label}")
            labels[str(obj.Label)] = obj
        rows = []
        for index, spec in enumerate(contract["objects"]):
            obj = labels.get(spec["source_label"])
            require(obj is not None and str(obj.Name) == spec["source_internal_name"], f"source selector drift: {spec['object_id']}")
            shape = obj.Shape
            require(shape is not None and not shape.isNull(), f"null source Shape: {spec['object_id']}")
            require(bool(shape.isValid()) and bool(shape.isClosed()), f"invalid/open source Shape: {spec['object_id']}")
            require(len(shape.Solids) == 1 and float(shape.Volume) > 0.0, f"source not one positive solid: {spec['object_id']}")
            path = output / f"{index:02d}_{spec['source_internal_name']}.brep"
            shape.exportBrep(str(path))
            object_placement = matrix(obj.Placement)
            rows.append({
                "object_id": spec["object_id"],
                "source_internal_name": str(obj.Name),
                "source_label": str(obj.Label),
                "source_shape_object_placement_consumed_separately": False,
                "source_object_placement_diagnostic_only": object_placement,
                "source_object_placement_is_identity": object_placement == [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
                "source_shape_placement_diagnostic_only": matrix(shape.Placement),
                "source_bbox_mm": bbox(shape),
                "source_volume_mm3": float(shape.Volume),
                "source_solid_count": len(shape.Solids),
                "source_shell_count": len(shape.Shells),
                "source_face_count": len(shape.Faces),
                "temporary_brep": {"filename": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)},
            })
        require(len(rows) == 12, "extractor did not emit exactly twelve objects")
        require(sum(not row["source_object_placement_is_identity"] for row in rows) == 7, "nonidentity placement count drift")
        print(json.dumps({
            "schema": "ROUTE_C_LINK2_B12_TRANSIENT_BREP_EXTRACTION_V1",
            "generated_utc": "DETERMINISTIC_EXTRACTION_NO_WALLCLOCK",
            "source": {"path": source.relative_to(root()).as_posix(), "bytes": source.stat().st_size, "sha256": sha256(source)},
            "source_document_opened_read_only": True,
            "source_document_saved": False,
            "source_document_recomputed": False,
            "selection_count": len(rows),
            "objects": rows,
            "verdict": "LINK2_B12_TRANSIENT_BREP_EXTRACTION_PASS__OBJECT_PLACEMENT_NOT_REAPPLIED",
        }, indent=2, sort_keys=True), end="\n")
    finally:
        App.closeDocument(document.Name)


if __name__ == "__main__":
    main()

