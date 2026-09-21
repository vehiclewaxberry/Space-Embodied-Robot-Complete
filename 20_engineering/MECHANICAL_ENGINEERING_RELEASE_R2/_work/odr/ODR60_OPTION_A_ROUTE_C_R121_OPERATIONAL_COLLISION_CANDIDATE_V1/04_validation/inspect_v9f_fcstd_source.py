"""Independent read-only extractor for the frozen V9F root-static R20 BReps.

This module is intentionally executable only with the pinned FreeCAD Python
runtime. It imports no candidate builder code, opens the frozen FCStd without
recompute/save, selects objects by exact ``Label``, and emits transient BREP
files plus a JSON witness. The normal-Python independent validator applies
``T_S_A0`` itself; this script never applies the candidate transform.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import FreeCAD as App


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def workspace_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root not found")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def stable_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output-dir", type=Path)
    mode.add_argument("--audit-all", action="store_true")
    return parser.parse_args()


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


def is_identity(matrix: list[list[float]], tolerance: float = 1.0e-14) -> bool:
    identity = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    return max(abs(matrix[row][column] - identity[row][column]) for row in range(4) for column in range(4)) <= tolerance


def audit_all_r121(root: Path, pins: dict[str, dict], fcstd: Path) -> dict:
    receipt = json.loads((root / pins["v9f_build_receipt"]["path"]).read_text(encoding="utf-8"))
    registry = json.loads((root / pins["m01_registry"]["path"]).read_text(encoding="utf-8"))
    manifest = json.loads((root / pins["v9f_mesh_manifest"]["path"]).read_text(encoding="utf-8"))
    mass = json.loads((root / pins["v9f_mass_geometry"]["path"]).read_text(encoding="utf-8"))
    receipt_names = {
        row["name"] for row in receipt["parts"] if row.get("geometry_role") == "PHYSICAL" and row.get("mass_counted") is True
    }
    registry_names = {row["object_id"].removeprefix("R::") for row in registry["objects"] if row.get("category") == "R"}
    route_groups = [row for row in manifest["files"] if row.get("group") == "route_c_parts"]
    require(len(route_groups) == 1, "manifest Route-C part group missing/duplicated")
    manifest_names = {
        row["name"] for row in route_groups[0]["entries"] if row.get("geometry_role") == "PHYSICAL" and row.get("mass_counted") is True
    }
    mass_names = {
        row["name"] for row in mass["parts"] if row.get("geometry_role") == "PHYSICAL" and row.get("mass_counted") is True
    }
    require(receipt_names == registry_names == manifest_names == mass_names, "R121 four-source name sets differ")
    require(len(receipt_names) == 121, "R121 name universe is not 121")

    document = App.openDocument(str(fcstd))
    try:
        labels = {}
        duplicates = []
        for obj in document.Objects:
            label = str(obj.Label)
            if label in labels:
                duplicates.append(label)
            labels[label] = obj
        require(not duplicates, f"duplicate FCStd labels: {sorted(set(duplicates))}")
        require(receipt_names <= set(labels), "one or more R121 labels absent from FCStd")
        rows = []
        total_solids = 0
        single_count = 0
        double_count = 0
        nonidentity_object_placements = 0
        for name in sorted(receipt_names):
            obj = labels[name]
            shape = getattr(obj, "Shape", None)
            require(shape is not None and not shape.isNull(), f"null R121 source shape: {name}")
            require(bool(shape.isValid()), f"invalid R121 source BRep: {name}")
            require(bool(shape.isClosed()), f"open R121 source BRep: {name}")
            solid_count = len(shape.Solids)
            require(solid_count in {1, 2}, f"unexpected R121 solid count: {name}={solid_count}")
            require(all(bool(solid.isValid()) and bool(solid.isClosed()) and float(solid.Volume) > 0.0 for solid in shape.Solids), f"invalid R121 constituent solid: {name}")
            require(math.isfinite(float(shape.Volume)) and float(shape.Volume) > 0.0, f"invalid R121 aggregate volume: {name}")
            total_solids += solid_count
            single_count += int(solid_count == 1)
            double_count += int(solid_count == 2)
            object_matrix = placement_matrix(obj.Placement)
            nonidentity_object_placements += int(not is_identity(object_matrix))
            rows.append(
                {
                    "object_id": f"R::{name}",
                    "source_label": name,
                    "source_internal_name": str(obj.Name),
                    "source_type_id": str(obj.TypeId),
                    "source_shape_type": str(shape.ShapeType),
                    "source_solid_count": solid_count,
                    "source_shell_count": len(shape.Shells),
                    "source_face_count": len(shape.Faces),
                    "source_edge_count": len(shape.Edges),
                    "source_vertex_count": len(shape.Vertexes),
                    "source_volume_mm3": float(shape.Volume),
                    "source_bbox_mm": bbox(shape),
                    "source_object_placement": object_matrix,
                    "source_object_placement_is_identity": is_identity(object_matrix),
                    "source_shape_object_placement_consumed_separately": False,
                    "valid": True,
                    "closed": True,
                    "positive_volume": True,
                }
            )
        expected_double = {"RC-GDE-J6-RING-0", "RC-GDE-J6-RING-1", "RC-GDE-J6-RING-2", "RC-GDE-J6-RING-3"}
        actual_double = {row["source_label"] for row in rows if row["source_solid_count"] == 2}
        require(actual_double == expected_double, f"R121 two-solid set drift: {sorted(actual_double)}")
        require(single_count == 117 and double_count == 4 and total_solids == 125, "R121 topology count drift")
        return {
            "schema": "ROUTE_C_V9F_R121_SOURCE_TOPOLOGY_AUDIT_V1",
            "generated_utc": "DETERMINISTIC_INDEPENDENT_COLD_OPEN_NO_WALLCLOCK",
            "source": {"path": fcstd.relative_to(root).as_posix(), "bytes": fcstd.stat().st_size, "sha256": sha256(fcstd)},
            "selection_method": "EXACT_FREECAD_LABEL_NOT_POSITIONAL_INDEX",
            "name_set_cross_check": {
                "receipt_physical": len(receipt_names),
                "registry_R": len(registry_names),
                "manifest_physical": len(manifest_names),
                "mass_geometry_physical": len(mass_names),
                "all_four_sets_exactly_equal": True,
            },
            "counts": {
                "source_document_objects": len(document.Objects),
                "objects": len(rows),
                "single_solid_objects": single_count,
                "double_solid_objects": double_count,
                "total_solids": total_solids,
                "valid_closed_positive_objects": len(rows),
                "nonidentity_freecad_object_placements": nonidentity_object_placements,
            },
            "two_solid_source_labels": sorted(actual_double),
            "objects": rows,
            "source_document_recomputed": False,
            "source_document_saved": False,
            "object_placement_reapplied": False,
            "candidate_builder_or_core_imported": False,
            "maximum_legal_claim": "R121_FROZEN_SOURCE_TOPOLOGY_AND_NAME_MAPPING_AUDIT_ONLY_NO_OUTPUT_SYSTEM_PAIR_EDGE_PATH_OR_RELEASE_CREDIT",
            "verdict": "V9F_R121_SOURCE_COLD_OPEN_PASS__121_OBJECTS_117_SINGLE_4_DOUBLE_125_SOLIDS__NO_SYSTEM_CREDIT",
        }
    finally:
        App.closeDocument(document.Name)


def main() -> None:
    args = parse_args()
    root = workspace_root()
    package = Path(__file__).resolve().parents[1]
    contract_path = package / "00_contract/ROOT_STATIC_R20_OPERATIONAL_COLLISION_CONTRACT_V1.json"
    source_lock_path = package / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    source_lock = json.loads(source_lock_path.read_text(encoding="utf-8"))
    pins = {str(row["id"]): row for row in source_lock["source_pins"]}
    require(len(pins) == len(source_lock["source_pins"]) == 13, "source pin IDs/count drift")
    for row in pins.values():
        path = root / str(row["path"])
        require(path.is_file(), f"pinned source missing: {row['path']}")
        require(path.stat().st_size == int(row["bytes"]), f"pinned source byte drift: {row['path']}")
        require(sha256(path) == str(row["sha256"]).upper(), f"pinned source hash drift: {row['path']}")

    fcstd = root / str(pins["v9f_fcstd"]["path"])
    if args.audit_all:
        print(stable_json(audit_all_r121(root, pins, fcstd)), end="")
        return

    require(args.output_dir is not None, "--output-dir is required for transient R20 extraction")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    require(not any(output_dir.iterdir()), "transient output directory must be empty")

    document = App.openDocument(str(fcstd))
    try:
        labels = {}
        duplicates = []
        for obj in document.Objects:
            label = str(obj.Label)
            if label in labels:
                duplicates.append(label)
            labels[label] = obj
        require(not duplicates, f"duplicate FCStd labels: {sorted(set(duplicates))}")

        specs = contract.get("objects", [])
        require(len(specs) == 20, "contract is not R20")
        require(len({row["object_id"] for row in specs}) == 20, "duplicate object_id")
        require(len({row["source_label"] for row in specs}) == 20, "duplicate source_label")
        rows = []
        for index, spec in enumerate(specs):
            object_id = str(spec["object_id"])
            label = str(spec["source_label"])
            obj = labels.get(label)
            require(obj is not None, f"exact FCStd Label not found: {label}")
            shape = getattr(obj, "Shape", None)
            require(shape is not None and not shape.isNull(), f"null source shape: {label}")
            require(bool(shape.isValid()), f"invalid source BRep: {label}")
            require(bool(shape.isClosed()), f"open source BRep: {label}")
            require(len(shape.Solids) == 1, f"R20 source solid count drift: {label}")
            require(all(bool(solid.isClosed()) for solid in shape.Solids), f"open source solid: {label}")
            require(math.isfinite(float(shape.Volume)) and float(shape.Volume) > 0.0, f"non-positive source volume: {label}")

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

        result = {
            "schema": "ROUTE_C_ROOT_STATIC_R20_INDEPENDENT_TRANSIENT_BREP_EXTRACTION_V1",
            "generated_utc": "DETERMINISTIC_INDEPENDENT_EXTRACTION_NO_WALLCLOCK",
            "source": {
                "path": fcstd.relative_to(root).as_posix(),
                "bytes": fcstd.stat().st_size,
                "sha256": sha256(fcstd),
            },
            "source_document_object_count": len(document.Objects),
            "source_document_recomputed": False,
            "source_document_saved": False,
            "selection_method": "EXACT_FREECAD_LABEL_NOT_POSITIONAL_INDEX",
            "selection_count": len(rows),
            "valid_closed_single_positive_brep_count": len(rows),
            "objects": rows,
            "temporary_brep_is_release_artifact": False,
            "candidate_builder_or_core_imported": False,
            "verdict": "R20_INDEPENDENT_SOURCE_EXTRACTION_PASS__A0_Q0_BREP_ONLY_NO_TRANSFORM",
        }
        print(stable_json(result), end="")
    finally:
        App.closeDocument(document.Name)


if __name__ == "__main__":
    main()
