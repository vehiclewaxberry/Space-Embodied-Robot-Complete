"""Extract the frozen Route-C root-static R20 BReps without rebuilding V9F.

Run with the FreeCAD-bundled Python interpreter.  The source FCStd is opened
read-only and never saved or recomputed.  Each selected ``obj.Shape`` is
serialized once to a temporary BREP for the normal-Python OCP builder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import FreeCAD as App


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def workspace_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if candidate.is_dir() and (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root not found")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def stable_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def bbox(shape) -> list[list[float]]:
    box = shape.BoundBox
    return [
        [float(box.XMin), float(box.YMin), float(box.ZMin)],
        [float(box.XMax), float(box.YMax), float(box.ZMax)],
    ]


def placement_matrix(placement) -> list[list[float]]:
    matrix = placement.toMatrix()
    return [
        [float(matrix.A11), float(matrix.A12), float(matrix.A13), float(matrix.A14)],
        [float(matrix.A21), float(matrix.A22), float(matrix.A23), float(matrix.A24)],
        [float(matrix.A31), float(matrix.A32), float(matrix.A33), float(matrix.A34)],
        [float(matrix.A41), float(matrix.A42), float(matrix.A43), float(matrix.A44)],
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = workspace_root()
    package = Path(__file__).resolve().parents[1]
    contract_path = package / "00_contract/ROOT_STATIC_R20_OPERATIONAL_COLLISION_CONTRACT_V1.json"
    source_lock_path = package / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    source_lock = json.loads(source_lock_path.read_text(encoding="utf-8"))
    pins = {row["id"]: row for row in source_lock["source_pins"]}
    require(len(pins) == 13, "source lock must contain exactly 13 unique pins")
    for row in pins.values():
        path = root / row["path"]
        require(path.is_file(), f"pinned source missing: {row['path']}")
        require(path.stat().st_size == int(row["bytes"]), f"byte drift: {row['path']}")
        require(sha256(path) == row["sha256"], f"hash drift: {row['path']}")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    require(not any(output_dir.iterdir()), "temporary BREP output directory must be empty")

    fcstd = root / pins["v9f_fcstd"]["path"]
    document = App.openDocument(str(fcstd))
    try:
        labels = {}
        duplicates = []
        for obj in document.Objects:
            label = str(obj.Label)
            if label in labels:
                duplicates.append(label)
            labels[label] = obj
        require(not duplicates, f"duplicate FCStd labels: {duplicates}")

        rows = []
        seen_ids = set()
        seen_labels = set()
        seen_outputs = set()
        for index, spec in enumerate(contract["objects"]):
            object_id = str(spec["object_id"])
            label = str(spec["source_label"])
            output_name = str(spec["output"])
            require(object_id not in seen_ids, f"duplicate object_id: {object_id}")
            require(label not in seen_labels, f"duplicate source_label: {label}")
            require(output_name not in seen_outputs, f"duplicate output: {output_name}")
            seen_ids.add(object_id)
            seen_labels.add(label)
            seen_outputs.add(output_name)
            obj = labels.get(label)
            require(obj is not None, f"FCStd selector missing: {label}")
            shape = getattr(obj, "Shape", None)
            require(shape is not None and not shape.isNull(), f"null shape: {label}")
            require(bool(shape.isValid()), f"invalid shape: {label}")
            require(bool(shape.isClosed()), f"open shape: {label}")
            require(len(shape.Solids) == 1, f"R20 source must be one solid: {label}")
            require(float(shape.Volume) > 0.0, f"non-positive volume: {label}")
            brep_path = output_dir / f"{index:02d}_{label.replace('-', '_')}.brep"
            shape.exportBrep(str(brep_path))
            require(brep_path.is_file() and brep_path.stat().st_size > 0, f"BREP export failed: {label}")
            rows.append(
                {
                    "index": index,
                    "object_id": object_id,
                    "source_label": label,
                    "source_internal_name": str(obj.Name),
                    "source_type_id": str(obj.TypeId),
                    "source_frame": "A0_Q0_REFERENCE",
                    "source_unit": "mm",
                    "source_shape_object_placement_consumed_separately": False,
                    "source_object_placement": placement_matrix(obj.Placement),
                    "source_shape_placement": placement_matrix(shape.Placement),
                    "source_shape_type": str(shape.ShapeType),
                    "source_solid_count": len(shape.Solids),
                    "source_shell_count": len(shape.Shells),
                    "source_face_count": len(shape.Faces),
                    "source_edge_count": len(shape.Edges),
                    "source_vertex_count": len(shape.Vertexes),
                    "source_bbox_mm": bbox(shape),
                    "source_volume_mm3": float(shape.Volume),
                    "temporary_brep": {
                        "filename": brep_path.name,
                        "bytes": brep_path.stat().st_size,
                        "sha256": sha256(brep_path),
                    },
                }
            )

        require(len(rows) == 20, "R20 extractor did not emit exactly 20 BReps")
        result = {
            "schema": "ROUTE_C_ROOT_STATIC_R20_TRANSIENT_BREP_EXTRACTION_V1",
            "generated_utc": "DETERMINISTIC_EXTRACTION_NO_WALLCLOCK",
            "source": {
                "path": fcstd.relative_to(root).as_posix(),
                "bytes": fcstd.stat().st_size,
                "sha256": sha256(fcstd),
            },
            "source_document_object_count": len(document.Objects),
            "source_document_saved": False,
            "source_document_recomputed": False,
            "selection_count": len(rows),
            "valid_closed_single_positive_brep_count": len(rows),
            "objects": rows,
            "temporary_brep_is_release_artifact": False,
            "verdict": "R20_TRANSIENT_BREP_EXTRACTION_PASS__SOURCE_OPENED_READ_ONLY",
        }
        print(stable_json(result), end="")
    finally:
        App.closeDocument(document.Name)


if __name__ == "__main__":
    main()
