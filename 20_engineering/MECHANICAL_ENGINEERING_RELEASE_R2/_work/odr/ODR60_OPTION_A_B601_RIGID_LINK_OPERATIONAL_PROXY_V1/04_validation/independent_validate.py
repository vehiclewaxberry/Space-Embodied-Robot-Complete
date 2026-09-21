"""Independent fail-closed validator for the six B601 rigid-link proxies.

This module deliberately does not import any candidate code from ``02_builder``.
It reconstructs the contracted convex-hull slab cover directly from the pinned
PLY sources, reopens the emitted STEP files through OCCT, and audits the runtime
NPZ/STL files from their serialized data.

The validator grants local geometry evidence only.  It cannot reissue the
system registry, evaluate pairs, authorize path search, advance a parent Gate,
or grant release credit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np
import scipy
import trimesh
from OCP import __version__ as OCP_VERSION
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from scipy.spatial import ConvexHull


SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = SCRIPT_DIR.parent
CONTRACT_PATH = PACKAGE_DIR / "00_contract" / "B601_RIGID_LINK_OPERATIONAL_COLLISION_CONTRACT_V1.json"
SOURCE_LOCK_PATH = PACKAGE_DIR / "01_sources" / "SOURCE_AUTHORITY_LOCK_V1.json"
RESULT_PATH = PACKAGE_DIR / "05_results" / "INDEPENDENT_VALIDATION_V1.json"

LINK_IDS = tuple(f"link{index}" for index in range(1, 7))
SLAB_COUNT = 12
EXPECTED_NPZ_KEYS = {
    "boxes_m",
    "vertices_m",
    "triangles",
    "solid_vertex_offsets",
    "solid_triangle_offsets",
    "link_id",
    "units",
    "frame",
}
GEOMETRY_TOLERANCE_M = 2.0e-10
STEP_TOLERANCE_MM = 2.0e-7
STL_FLOAT32_TOLERANCE_M = 2.0e-7
MEMBERSHIP_TOLERANCE_M = 2.0e-12

AUTHORITY_KEYS = {
    "parent_mechanical_gate_reissued",
    "parent_gate_reissued",
    "system_registry_reissued",
    "system_pair_evaluation_authorized",
    "pair_evaluation_authorized",
    "path_search_authorized",
    "next_stage_authorized",
    "release_credit",
}


class ValidationFailure(RuntimeError):
    """A deterministic fail-closed validation error."""


def require(condition: bool, message: str) -> None:
    if not bool(condition):
        raise ValidationFailure(message)


def workspace_root() -> Path:
    for candidate in (PACKAGE_DIR, *PACKAGE_DIR.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise ValidationFailure("workspace root containing PROJECT_MAP.md was not found")


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required JSON missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_record(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "bytes": int(path.stat().st_size),
        "sha256": sha256_path(path),
    }


def resolve_locked_path(root: Path, raw_path: str) -> Path:
    path = (root / raw_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationFailure(f"locked path escapes workspace: {raw_path}") from exc
    return path


def validate_pinned_file(root: Path, label: str, record: dict[str, Any]) -> dict[str, Any]:
    for key in ("path", "bytes", "sha256"):
        require(key in record, f"{label} missing pin field: {key}")
    path = resolve_locked_path(root, str(record["path"]))
    require(path.is_file(), f"{label} pinned file missing: {record['path']}")
    actual = file_record(path, root)
    require(actual["bytes"] == int(record["bytes"]), f"{label} byte-count drift")
    require(actual["sha256"] == str(record["sha256"]).upper(), f"{label} SHA-256 drift")
    return actual


def walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def walk_scalars(value: Any, prefix: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_scalars(child, (*prefix, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_scalars(child, (*prefix, str(index)))
    else:
        yield prefix, value


def require_no_authority_true(value: Any, label: str) -> dict[str, bool]:
    observed: dict[str, bool] = {}
    for path, scalar in walk_scalars(value):
        if path and path[-1] in AUTHORITY_KEYS and isinstance(scalar, bool):
            observed[".".join(path)] = scalar
            require(scalar is False, f"{label} improperly sets {'.'.join(path)}=true")
    return observed


def scalar_text(array: np.ndarray, label: str) -> str:
    value = np.asarray(array)
    require(value.size == 1, f"{label} must be a scalar")
    return str(value.reshape(()).item())


def normalize_unit(value: Any) -> str:
    text = str(value).strip().lower().replace(" ", "")
    aliases = {
        "m": "m",
        "meter": "m",
        "metre": "m",
        "meters": "m",
        "metres": "m",
        "si_m": "m",
        "mm": "mm",
        "millimeter": "mm",
        "millimetre": "mm",
        "millimeters": "mm",
        "millimetres": "mm",
    }
    return aliases.get(text, text)


def sorted_rows(array: np.ndarray) -> np.ndarray:
    value = np.asarray(array)
    require(value.ndim == 2, "sorted_rows requires a two-dimensional array")
    if len(value) == 0:
        return value.copy()
    keys = tuple(value[:, column] for column in reversed(range(value.shape[1])))
    return value[np.lexsort(keys)]


def unique_hull_edges(simplices: np.ndarray) -> np.ndarray:
    simplices = np.asarray(simplices, dtype=np.int64)
    edges = np.concatenate(
        (simplices[:, [0, 1]], simplices[:, [1, 2]], simplices[:, [2, 0]]), axis=0
    )
    edges.sort(axis=1)
    return np.unique(edges, axis=0)


def points_in_box_union(
    points: np.ndarray, boxes_m: np.ndarray, tolerance_m: float = MEMBERSHIP_TOLERANCE_M
) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    lower = points[:, None, :] >= boxes_m[None, :, 0, :] - tolerance_m
    upper = points[:, None, :] <= boxes_m[None, :, 1, :] + tolerance_m
    return np.any(np.all(lower & upper, axis=2), axis=1)


def independent_sectional_cover(
    vertices_m: np.ndarray, slab_count: int, transverse_guard_m: float
) -> dict[str, Any]:
    """Recompute the slab AABBs without using the candidate builder."""

    vertices_m = np.asarray(vertices_m, dtype=np.float64)
    require(vertices_m.ndim == 2 and vertices_m.shape[1] == 3, "source vertices are not Nx3")
    require(np.all(np.isfinite(vertices_m)), "source vertices contain non-finite values")
    hull = ConvexHull(vertices_m, qhull_options="Qx")
    hull_vertex_indices = np.asarray(hull.vertices, dtype=np.int64)
    hull_vertices = vertices_m[hull_vertex_indices]
    hull_edges = unique_hull_edges(np.asarray(hull.simplices, dtype=np.int64))
    extents = np.ptp(hull_vertices, axis=0)
    long_axis = int(np.argmax(extents))
    lower = float(hull_vertices[:, long_axis].min())
    upper = float(hull_vertices[:, long_axis].max())
    require(upper > lower, "convex hull has zero longitudinal extent")
    boundaries = np.linspace(lower, upper, slab_count + 1, dtype=np.float64)
    other_axes = [axis for axis in range(3) if axis != long_axis]
    plane_tolerance = 2.0e-13
    boxes: list[np.ndarray] = []
    critical_points: list[np.ndarray] = []

    for slab_index in range(slab_count):
        a = float(boundaries[slab_index])
        b = float(boundaries[slab_index + 1])
        rows: list[np.ndarray] = []
        inside = (hull_vertices[:, long_axis] >= a - plane_tolerance) & (
            hull_vertices[:, long_axis] <= b + plane_tolerance
        )
        if np.any(inside):
            rows.extend(hull_vertices[inside])
        for edge in hull_edges:
            p0 = vertices_m[int(edge[0])]
            p1 = vertices_m[int(edge[1])]
            x0 = float(p0[long_axis])
            x1 = float(p1[long_axis])
            if abs(x1 - x0) <= plane_tolerance:
                continue
            for plane in (a, b):
                if plane < min(x0, x1) - plane_tolerance or plane > max(x0, x1) + plane_tolerance:
                    continue
                fraction = (plane - x0) / (x1 - x0)
                if -plane_tolerance <= fraction <= 1.0 + plane_tolerance:
                    rows.append(p0 + fraction * (p1 - p0))
        require(rows, f"independent hull cross-section empty at slab {slab_index}")
        section = np.asarray(rows, dtype=np.float64)
        box = np.zeros((2, 3), dtype=np.float64)
        box[0, long_axis] = a
        box[1, long_axis] = b
        for axis in other_axes:
            box[0, axis] = float(section[:, axis].min()) - transverse_guard_m
            box[1, axis] = float(section[:, axis].max()) + transverse_guard_m
        require(np.all(box[1] > box[0]), f"independent slab {slab_index} has non-positive extent")
        boxes.append(box)
        critical_points.append(section)

    boxes_m = np.asarray(boxes, dtype=np.float64)
    source_contained = points_in_box_union(vertices_m, boxes_m)
    require(np.all(source_contained), "independent cover does not contain every source vertex")
    return {
        "boxes_m": boxes_m,
        "critical_points": critical_points,
        "long_axis": long_axis,
        "boundaries_m": boundaries,
        "hull_vertex_count": int(len(hull_vertices)),
        "hull_edge_count": int(len(hull_edges)),
        "hull_volume_m3": float(hull.volume),
        "source_bbox_m": np.vstack((vertices_m.min(axis=0), vertices_m.max(axis=0))),
        "proxy_sum_volume_m3": float(np.prod(boxes_m[:, 1] - boxes_m[:, 0], axis=1).sum()),
        "critical_point_counts": [int(len(section)) for section in critical_points],
    }


def box_corners(box_m: np.ndarray) -> np.ndarray:
    lower, upper = np.asarray(box_m, dtype=np.float64)
    return np.asarray(
        [
            [x, y, z]
            for x in (lower[0], upper[0])
            for y in (lower[1], upper[1])
            for z in (lower[2], upper[2])
        ],
        dtype=np.float64,
    )


def signed_volume(vertices: np.ndarray, triangles: np.ndarray) -> float:
    faces = np.asarray(triangles, dtype=np.int64)
    xyz = np.asarray(vertices, dtype=np.float64)[faces]
    return float(
        np.einsum("ij,ij->i", xyz[:, 0], np.cross(xyz[:, 1], xyz[:, 2])).sum() / 6.0
    )


def closed_oriented_edge_metrics(triangles: np.ndarray) -> dict[str, int]:
    faces = np.asarray(triangles, dtype=np.int64)
    directed = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0)
    undirected = np.sort(directed, axis=1)
    unique_edges, inverse, counts = np.unique(
        undirected, axis=0, return_inverse=True, return_counts=True
    )
    forward = np.bincount(
        inverse,
        weights=(directed[:, 0] < directed[:, 1]).astype(np.int8),
        minlength=len(unique_edges),
    )
    reverse = counts - forward
    return {
        "boundary_edge_count": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edge_count": int(np.count_nonzero(counts > 2)),
        "orientation_mismatch_edge_count": int(np.count_nonzero(forward != reverse)),
    }


def triangle_signature(triangles_xyz: np.ndarray) -> np.ndarray:
    rows: list[np.ndarray] = []
    for triangle in np.asarray(triangles_xyz, dtype=np.float64):
        rows.append(sorted_rows(triangle).reshape(-1))
    return sorted_rows(np.asarray(rows, dtype=np.float64))


def find_artifact_record(receipt: dict[str, Any], artifact: Path) -> dict[str, Any]:
    basename = artifact.name.lower()
    matches: list[dict[str, Any]] = []
    for record in walk_dicts(receipt):
        has_name = any(
            isinstance(value, str) and Path(value.replace("\\", "/")).name.lower() == basename
            for value in record.values()
        )
        if has_name and "bytes" in record and "sha256" in record:
            matches.append(record)
    require(matches, f"receipt has no byte/SHA record for {artifact.name}")
    exact = [record for record in matches if "path" in record]
    return exact[0] if exact else matches[0]


def validate_receipt_artifact(receipt: dict[str, Any], artifact: Path) -> dict[str, Any]:
    record = find_artifact_record(receipt, artifact)
    require(artifact.is_file(), f"receipt-bound artifact missing: {artifact.name}")
    require(int(record["bytes"]) == artifact.stat().st_size, f"receipt byte drift: {artifact.name}")
    require(str(record["sha256"]).upper() == sha256_path(artifact), f"receipt SHA drift: {artifact.name}")
    return record


def receipt_has_runtime_metre_binding(receipt: dict[str, Any], stl_record: dict[str, Any]) -> bool:
    for key, value in stl_record.items():
        if "unit" in str(key).lower() and normalize_unit(value) == "m":
            return True
    for path, value in walk_scalars(receipt):
        joined = ".".join(part.lower() for part in path)
        if "runtime" in joined and "unit" in joined and normalize_unit(value) == "m":
            return True
    return False


def validate_receipt(
    receipt_path: Path, link_id: str, artifacts: tuple[Path, Path, Path]
) -> dict[str, Any]:
    receipt = read_json(receipt_path)
    schema = str(receipt.get("schema", ""))
    require("RECEIPT" in schema.upper() and schema.upper().endswith("V1"), "receipt schema mismatch")
    review_status = receipt.get("review_status", receipt.get("classification"))
    require(
        review_status == "PENDING_OWNER_REVIEW",
        f"{link_id} receipt review classification must remain PENDING_OWNER_REVIEW",
    )
    authority_observed = require_no_authority_true(receipt, f"{link_id} receipt")
    step_path, npz_path, stl_path = artifacts
    step_record = validate_receipt_artifact(receipt, step_path)
    npz_record = validate_receipt_artifact(receipt, npz_path)
    stl_record = validate_receipt_artifact(receipt, stl_path)
    require(
        receipt_has_runtime_metre_binding(receipt, stl_record),
        f"{link_id} receipt does not bind runtime STL units to metres",
    )
    expected_frame = f"B601_{link_id.upper()}_LOCAL"
    frame_values = [
        str(value)
        for path, value in walk_scalars(receipt)
        if path and "frame" in path[-1].lower() and isinstance(value, str)
    ]
    require(expected_frame in frame_values, f"{link_id} receipt lacks exact runtime-frame binding")
    return {
        "record": receipt,
        "summary": {
            "schema": schema,
            "review_status": review_status,
            "authority_fields_observed": authority_observed,
            "step_record": {key: step_record[key] for key in ("bytes", "sha256")},
            "npz_record": {key: npz_record[key] for key in ("bytes", "sha256")},
            "stl_record": {key: stl_record[key] for key in ("bytes", "sha256")},
            "runtime_stl_unit_binding": "m",
            "runtime_frame_binding": expected_frame,
        },
    }


def validate_npz(
    npz_path: Path,
    link_id: str,
    source_vertices_m: np.ndarray,
    expected_cover: dict[str, Any],
) -> dict[str, Any]:
    require(npz_path.is_file(), f"runtime NPZ missing: {npz_path.name}")
    with np.load(npz_path, allow_pickle=False) as archive:
        require(set(archive.files) == EXPECTED_NPZ_KEYS, f"{link_id} NPZ member-set mismatch")
        boxes_m = np.asarray(archive["boxes_m"])
        vertices_m = np.asarray(archive["vertices_m"])
        triangles = np.asarray(archive["triangles"])
        vertex_offsets = np.asarray(archive["solid_vertex_offsets"])
        triangle_offsets = np.asarray(archive["solid_triangle_offsets"])
        archive_link_id = scalar_text(archive["link_id"], f"{link_id} NPZ link_id")
        units = scalar_text(archive["units"], f"{link_id} NPZ units")
        frame = scalar_text(archive["frame"], f"{link_id} NPZ frame")

    require(boxes_m.dtype == np.dtype("<f8"), f"{link_id} boxes_m must be little-endian float64")
    require(vertices_m.dtype == np.dtype("<f8"), f"{link_id} vertices_m must be little-endian float64")
    require(np.issubdtype(triangles.dtype, np.integer), f"{link_id} triangles must be integers")
    require(np.issubdtype(vertex_offsets.dtype, np.integer), f"{link_id} vertex offsets must be integers")
    require(np.issubdtype(triangle_offsets.dtype, np.integer), f"{link_id} triangle offsets must be integers")
    require(boxes_m.shape == (SLAB_COUNT, 2, 3), f"{link_id} boxes_m shape mismatch")
    require(vertices_m.shape == (96, 3), f"{link_id} vertices_m shape mismatch")
    require(triangles.shape == (144, 3), f"{link_id} triangles shape mismatch")
    require(vertex_offsets.shape == (13,), f"{link_id} solid_vertex_offsets shape mismatch")
    require(triangle_offsets.shape == (13,), f"{link_id} solid_triangle_offsets shape mismatch")
    require(np.all(np.isfinite(boxes_m)) and np.all(np.isfinite(vertices_m)), f"{link_id} NPZ non-finite geometry")
    require(np.all(boxes_m[:, 1] > boxes_m[:, 0]), f"{link_id} NPZ has non-positive box")
    require(archive_link_id == link_id, f"{link_id} NPZ link_id mismatch")
    require(normalize_unit(units) == "m", f"{link_id} NPZ units are not metres")
    expected_frame = f"B601_{link_id.upper()}_LOCAL"
    require(frame == expected_frame, f"{link_id} NPZ frame mismatch")
    require(
        np.array_equal(vertex_offsets, np.arange(13, dtype=vertex_offsets.dtype) * 8),
        f"{link_id} vertex offsets are not 12 contiguous eight-vertex solids",
    )
    require(
        np.array_equal(triangle_offsets, np.arange(13, dtype=triangle_offsets.dtype) * 12),
        f"{link_id} triangle offsets are not 12 contiguous twelve-triangle solids",
    )
    require(np.all(triangles >= 0) and int(triangles.max()) < len(vertices_m), f"{link_id} triangle index out of range")

    independent_boxes = np.asarray(expected_cover["boxes_m"], dtype=np.float64)
    max_box_error = float(np.max(np.abs(boxes_m - independent_boxes)))
    require(max_box_error <= GEOMETRY_TOLERANCE_M, f"{link_id} NPZ differs from independent slab cover")
    source_mask = points_in_box_union(source_vertices_m, boxes_m)
    require(np.all(source_mask), f"{link_id} NPZ union excludes source surface vertices")
    for slab_index, critical in enumerate(expected_cover["critical_points"]):
        box = boxes_m[slab_index]
        inside = np.all(
            (critical >= box[0] - MEMBERSHIP_TOLERANCE_M)
            & (critical <= box[1] + MEMBERSHIP_TOLERANCE_M),
            axis=1,
        )
        require(np.all(inside), f"{link_id} slab {slab_index} excludes analytical hull critical points")

    solid_metrics: list[dict[str, Any]] = []
    for solid_index in range(SLAB_COUNT):
        vertex_start = int(vertex_offsets[solid_index])
        vertex_stop = int(vertex_offsets[solid_index + 1])
        triangle_start = int(triangle_offsets[solid_index])
        triangle_stop = int(triangle_offsets[solid_index + 1])
        local_vertices = vertices_m[vertex_start:vertex_stop]
        local_triangles = triangles[triangle_start:triangle_stop].astype(np.int64)
        require(
            np.all((local_triangles >= vertex_start) & (local_triangles < vertex_stop)),
            f"{link_id} solid {solid_index} triangle crosses solid offsets",
        )
        require(
            np.allclose(
                sorted_rows(local_vertices),
                sorted_rows(box_corners(boxes_m[solid_index])),
                rtol=0.0,
                atol=GEOMETRY_TOLERANCE_M,
            ),
            f"{link_id} solid {solid_index} vertices are not the contracted box corners",
        )
        edge_metrics = closed_oriented_edge_metrics(local_triangles)
        require(all(value == 0 for value in edge_metrics.values()), f"{link_id} solid {solid_index} is not closed/oriented")
        volume_m3 = signed_volume(vertices_m, local_triangles)
        expected_volume = float(np.prod(boxes_m[solid_index, 1] - boxes_m[solid_index, 0]))
        require(volume_m3 > 0.0, f"{link_id} solid {solid_index} signed volume is not positive")
        require(
            math.isclose(volume_m3, expected_volume, rel_tol=2.0e-10, abs_tol=1.0e-15),
            f"{link_id} solid {solid_index} mesh/box volume mismatch",
        )
        solid_metrics.append(
            {
                "solid_index": solid_index,
                **edge_metrics,
                "signed_volume_m3": volume_m3,
            }
        )

    return {
        "boxes_m": boxes_m,
        "vertices_m": vertices_m,
        "triangles": triangles.astype(np.int64),
        "vertex_offsets": vertex_offsets.astype(np.int64),
        "triangle_offsets": triangle_offsets.astype(np.int64),
        "metrics": {
            "member_set": sorted(EXPECTED_NPZ_KEYS),
            "dtypes": {
                "boxes_m": str(boxes_m.dtype),
                "vertices_m": str(vertices_m.dtype),
                "triangles": str(triangles.dtype),
                "solid_vertex_offsets": str(vertex_offsets.dtype),
                "solid_triangle_offsets": str(triangle_offsets.dtype),
            },
            "box_count": int(len(boxes_m)),
            "vertex_count": int(len(vertices_m)),
            "triangle_count": int(len(triangles)),
            "frame": frame,
            "units": "m",
            "max_independent_box_abs_error_m": max_box_error,
            "source_vertex_count": int(len(source_vertices_m)),
            "source_vertices_contained": int(np.count_nonzero(source_mask)),
            "per_solid_closed_and_oriented": True,
            "solid_metrics": solid_metrics,
        },
    }


def step_declares_millimetres(step_path: Path) -> tuple[bool, int]:
    text = step_path.read_text(encoding="latin-1", errors="strict").upper()
    declarations = re.findall(
        r"LENGTH_UNIT\s*\(\s*\)\s*NAMED_UNIT\s*\(\s*\*\s*\)\s*"
        r"SI_UNIT\s*\(\s*([^,]+)\s*,\s*\.METRE\.\s*\)",
        text,
    )
    normalized = [value.replace(" ", "") for value in declarations]
    return bool(normalized) and all(value == ".MILLI." for value in normalized), len(normalized)


def occt_bbox_mm(shape: Any) -> np.ndarray:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    require(not box.IsVoid(), "OCCT bounding box is void")
    return np.asarray(box.Get(), dtype=np.float64).reshape(2, 3)


def occt_volume_mm3(shape: Any) -> float:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties, False, False, True)
    return float(properties.Mass())


def validate_step(step_path: Path, link_id: str, expected_boxes_m: np.ndarray, long_axis: int) -> dict[str, Any]:
    require(step_path.is_file(), f"STEP missing: {step_path.name}")
    units_ok, unit_declaration_count = step_declares_millimetres(step_path)
    require(units_ok, f"{link_id} STEP does not exclusively declare millimetre LENGTH_UNIT")
    step_text = step_path.read_text(encoding="latin-1", errors="strict").upper()
    require(
        f"B601_{link_id.upper()}_OPERATIONAL_COLLISION_PROXY_V1" in step_text,
        f"{link_id} STEP product label missing",
    )
    for slab_index in range(SLAB_COUNT):
        require(
            f"{link_id.upper()}_CONVEX_COVER_SLAB_{slab_index:02d}" in step_text,
            f"{link_id} STEP slab label missing: {slab_index}",
        )

    reader = STEPControl_Reader()
    require(reader.ReadFile(str(step_path)) == IFSelect_RetDone, f"{link_id} STEP read failed")
    transferred_roots = int(reader.TransferRoots())
    shape = reader.OneShape()
    require(transferred_roots == 1 and not shape.IsNull(), f"{link_id} STEP root transfer invalid")
    require(BRepCheck_Analyzer(shape, True).IsValid(), f"{link_id} STEP compound BRep invalid")

    rows: list[dict[str, Any]] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = TopoDS.Solid_s(explorer.Current())
        bbox_mm = occt_bbox_mm(solid)
        volume_mm3 = occt_volume_mm3(solid)
        rows.append(
            {
                "bbox_mm": bbox_mm,
                "volume_mm3": volume_mm3,
                "valid": bool(BRepCheck_Analyzer(solid, True).IsValid()),
            }
        )
        explorer.Next()
    require(len(rows) == SLAB_COUNT, f"{link_id} STEP solid count is {len(rows)}, expected 12")
    require(all(row["valid"] for row in rows), f"{link_id} STEP contains invalid BRep solid")
    require(
        all(math.isfinite(row["volume_mm3"]) and row["volume_mm3"] > 0.0 for row in rows),
        f"{link_id} STEP contains non-positive/non-finite solid volume",
    )
    rows.sort(key=lambda row: float(row["bbox_mm"][0, long_axis]))
    actual_boxes_mm = np.asarray([row["bbox_mm"] for row in rows], dtype=np.float64)
    expected_boxes_mm = np.asarray(expected_boxes_m, dtype=np.float64) * 1000.0
    max_bbox_error_mm = float(np.max(np.abs(actual_boxes_mm - expected_boxes_mm)))
    require(max_bbox_error_mm <= STEP_TOLERANCE_MM, f"{link_id} STEP/independent box mismatch")
    expected_volumes_mm3 = np.prod(expected_boxes_mm[:, 1] - expected_boxes_mm[:, 0], axis=1)
    actual_volumes_mm3 = np.asarray([row["volume_mm3"] for row in rows], dtype=np.float64)
    max_volume_relative_error = float(
        np.max(np.abs(actual_volumes_mm3 - expected_volumes_mm3) / expected_volumes_mm3)
    )
    require(max_volume_relative_error <= 2.0e-9, f"{link_id} STEP solid volume mismatch")
    return {
        "transferred_root_count": transferred_roots,
        "solid_count": len(rows),
        "valid_solid_count": int(sum(row["valid"] for row in rows)),
        "positive_volume_solid_count": int(sum(row["volume_mm3"] > 0.0 for row in rows)),
        "length_unit": "mm",
        "millimetre_length_unit_declaration_count": unit_declaration_count,
        "max_bbox_abs_error_mm": max_bbox_error_mm,
        "max_volume_relative_error": max_volume_relative_error,
        "aggregate_volume_mm3": float(actual_volumes_mm3.sum()),
    }


def read_stl_triangles(stl_path: Path) -> tuple[np.ndarray, str]:
    data = stl_path.read_bytes()
    require(len(data) >= 84, f"runtime STL truncated: {stl_path.name}")
    triangle_count = struct.unpack("<I", data[80:84])[0]
    if len(data) == 84 + 50 * triangle_count:
        dtype = np.dtype(
            [
                ("normal", "<f4", (3,)),
                ("vertices", "<f4", (3, 3)),
                ("attribute", "<u2"),
            ]
        )
        rows = np.frombuffer(data, dtype=dtype, count=triangle_count, offset=84)
        return np.asarray(rows["vertices"], dtype=np.float64), "binary"
    loaded = trimesh.load_mesh(stl_path, process=False)
    if isinstance(loaded, trimesh.Scene):
        require(bool(loaded.geometry), f"runtime STL scene is empty: {stl_path.name}")
        loaded = trimesh.util.concatenate(tuple(loaded.geometry.values()))
    require(isinstance(loaded, trimesh.Trimesh), f"runtime STL did not load as a mesh: {stl_path.name}")
    return np.asarray(loaded.triangles, dtype=np.float64), "ascii_or_noncanonical"


def validate_stl(
    stl_path: Path,
    link_id: str,
    expected_boxes_m: np.ndarray,
    npz_data: dict[str, Any],
) -> dict[str, Any]:
    require(stl_path.is_file(), f"runtime STL missing: {stl_path.name}")
    stl_triangles, encoding = read_stl_triangles(stl_path)
    require(stl_triangles.shape == (144, 3, 3), f"{link_id} runtime STL triangle shape mismatch")
    require(np.all(np.isfinite(stl_triangles)), f"{link_id} runtime STL contains non-finite vertices")
    npz_vertices = np.asarray(npz_data["vertices_m"], dtype=np.float64)
    npz_triangles = np.asarray(npz_data["triangles"], dtype=np.int64)
    npz_offsets = np.asarray(npz_data["triangle_offsets"], dtype=np.int64)
    stl_solid_metrics: list[dict[str, Any]] = []
    max_bbox_error_m = 0.0
    max_triangle_coordinate_error_m = 0.0

    for solid_index in range(SLAB_COUNT):
        start = solid_index * 12
        stop = start + 12
        triangles_xyz = stl_triangles[start:stop]
        flat = triangles_xyz.reshape(-1, 3)
        unique_vertices, inverse = np.unique(flat, axis=0, return_inverse=True)
        indexed = inverse.reshape(-1, 3)
        require(len(unique_vertices) == 8, f"{link_id} STL solid {solid_index} does not have 8 corners")
        edge_metrics = closed_oriented_edge_metrics(indexed)
        require(all(value == 0 for value in edge_metrics.values()), f"{link_id} STL solid {solid_index} is not closed/oriented")
        volume_m3 = signed_volume(unique_vertices, indexed)
        require(volume_m3 > 0.0, f"{link_id} STL solid {solid_index} signed volume is not positive")
        mesh = trimesh.Trimesh(vertices=flat, faces=np.arange(36).reshape(12, 3), process=True)
        require(bool(mesh.is_watertight), f"{link_id} STL solid {solid_index} is not watertight")
        require(bool(mesh.is_winding_consistent), f"{link_id} STL solid {solid_index} winding is inconsistent")
        actual_bbox = np.vstack((flat.min(axis=0), flat.max(axis=0)))
        bbox_error = float(np.max(np.abs(actual_bbox - expected_boxes_m[solid_index])))
        max_bbox_error_m = max(max_bbox_error_m, bbox_error)
        require(bbox_error <= STL_FLOAT32_TOLERANCE_M, f"{link_id} STL solid {solid_index} bbox mismatch")

        npz_start = int(npz_offsets[solid_index])
        npz_stop = int(npz_offsets[solid_index + 1])
        npz_xyz = npz_vertices[npz_triangles[npz_start:npz_stop]]
        stl_signature = triangle_signature(triangles_xyz)
        npz_signature = triangle_signature(npz_xyz)
        triangle_error = float(np.max(np.abs(stl_signature - npz_signature)))
        max_triangle_coordinate_error_m = max(max_triangle_coordinate_error_m, triangle_error)
        require(
            triangle_error <= STL_FLOAT32_TOLERANCE_M,
            f"{link_id} STL solid {solid_index} differs from canonical NPZ triangles",
        )
        stl_solid_metrics.append(
            {
                "solid_index": solid_index,
                **edge_metrics,
                "watertight": True,
                "winding_consistent": True,
                "signed_volume_m3": volume_m3,
                "bbox_abs_error_m": bbox_error,
                "npz_triangle_abs_error_m": triangle_error,
            }
        )

    return {
        "encoding": encoding,
        "unit_authority": "m (bound by per-link receipt; STL is intrinsically unitless)",
        "triangle_count": int(len(stl_triangles)),
        "solid_count": SLAB_COUNT,
        "watertight_solid_count": SLAB_COUNT,
        "closed_oriented_solid_count": SLAB_COUNT,
        "max_bbox_abs_error_m": max_bbox_error_m,
        "max_npz_triangle_abs_error_m": max_triangle_coordinate_error_m,
        "solid_metrics": stl_solid_metrics,
    }


def validate_link(
    root: Path,
    contract: dict[str, Any],
    source_lock: dict[str, Any],
    link_id: str,
) -> dict[str, Any]:
    source_record = source_lock["link_sources"][link_id]
    source_file = validate_pinned_file(root, f"{link_id} source PLY", source_record)
    source_path = resolve_locked_path(root, str(source_record["path"]))
    mesh = trimesh.load_mesh(source_path, process=False)
    require(isinstance(mesh, trimesh.Trimesh), f"{link_id} source PLY is not one mesh")
    source_vertices_m = np.asarray(mesh.vertices, dtype=np.float64)
    source_faces = np.asarray(mesh.faces)
    require(len(source_vertices_m) == int(source_record["vertices"]), f"{link_id} source vertex-count drift")
    require(len(source_faces) == int(source_record["faces"]), f"{link_id} source face-count drift")
    require(np.all(np.isfinite(source_vertices_m)), f"{link_id} source vertices are non-finite")

    method = contract["geometry_method"]
    cover = independent_sectional_cover(
        source_vertices_m,
        int(method["slab_count"]),
        float(method["transverse_guard_mm"]) * 1.0e-3,
    )
    stem = f"B601_{link_id.upper()}_OPERATIONAL_COLLISION_PROXY_V1"
    step_path = PACKAGE_DIR / "03_assets" / f"{stem}.step"
    npz_path = PACKAGE_DIR / "03_assets" / f"{stem}_RUNTIME.npz"
    stl_path = PACKAGE_DIR / "03_assets" / f"{stem}_RUNTIME_M.stl"
    receipt_path = PACKAGE_DIR / "05_results" / f"B601_{link_id.upper()}_LOCAL_GEOMETRY_RECEIPT_V1.json"
    for path in (step_path, npz_path, stl_path, receipt_path):
        require(path.is_file(), f"{link_id} expected artifact missing: {path.relative_to(PACKAGE_DIR)}")

    receipt_data = validate_receipt(receipt_path, link_id, (step_path, npz_path, stl_path))
    npz_data = validate_npz(npz_path, link_id, source_vertices_m, cover)
    step_metrics = validate_step(step_path, link_id, cover["boxes_m"], int(cover["long_axis"]))
    stl_metrics = validate_stl(stl_path, link_id, cover["boxes_m"], npz_data)

    return {
        "link_id": link_id,
        "object_id": source_record["object_id"],
        "source_frame": source_record["frame"],
        "runtime_frame": f"B601_{link_id.upper()}_LOCAL",
        "source_unit": "m",
        "step_unit": "mm",
        "runtime_unit": "m",
        "source_file": source_file,
        "step_file": file_record(step_path, root),
        "runtime_npz_file": file_record(npz_path, root),
        "runtime_stl_file": file_record(stl_path, root),
        "receipt_file": file_record(receipt_path, root),
        "receipt_validation": receipt_data["summary"],
        "independent_cover": {
            "long_axis": int(cover["long_axis"]),
            "boundaries_m": np.asarray(cover["boundaries_m"]).tolist(),
            "source_bbox_m": np.asarray(cover["source_bbox_m"]).tolist(),
            "hull_vertex_count": int(cover["hull_vertex_count"]),
            "hull_edge_count": int(cover["hull_edge_count"]),
            "hull_volume_m3": float(cover["hull_volume_m3"]),
            "proxy_sum_volume_m3": float(cover["proxy_sum_volume_m3"]),
            "critical_point_counts": cover["critical_point_counts"],
            "analytical_hull_contained": True,
            "complete_source_surface_vertices_contained": True,
        },
        "npz_validation": npz_data["metrics"],
        "step_validation": step_metrics,
        "stl_validation": stl_metrics,
        "checks": {
            "source_hash_bytes_and_topology_match": True,
            "receipt_hash_bytes_unit_frame_and_authority_match": True,
            "independent_twelve_slab_cover_reproduced": True,
            "complete_source_surface_vertices_contained": True,
            "convex_hull_critical_points_contained": True,
            "npz_schema_offsets_closed_and_oriented": True,
            "step_twelve_positive_brep_valid_solids": True,
            "step_millimetre_unit_and_link_local_geometry_match": True,
            "runtime_stl_metre_binding_watertight_closed_and_oriented": True,
            "step_npz_stl_geometry_agree": True,
        },
        "validation_pass": True,
    }


def validate_all() -> dict[str, Any]:
    failures: list[str] = []
    root: Path | None = None
    contract: dict[str, Any] | None = None
    source_lock: dict[str, Any] | None = None
    global_checks: dict[str, bool] = {
        "contract_schema_scope_and_method_locked": False,
        "contract_authority_flags_fail_closed": False,
        "source_lock_schema_and_mutation_flags_fail_closed": False,
        "immutable_authority_source_hashes_match": False,
        "six_link_source_records_present": False,
        "validator_does_not_import_candidate_builder": True,
    }
    immutable_records: dict[str, Any] = {}

    try:
        root = workspace_root()
        contract = read_json(CONTRACT_PATH)
        source_lock = read_json(SOURCE_LOCK_PATH)
        require(
            contract.get("schema") == "B601_RIGID_LINK_OPERATIONAL_COLLISION_CONTRACT_V1",
            "contract schema mismatch",
        )
        require(contract.get("scope") == "LOCAL_ASSET_LEVEL_COLLISION_GEOMETRY_ONLY", "contract scope mismatch")
        method = contract.get("geometry_method", {})
        require(method.get("name") == "CONVEX_HULL_CROSS_SECTION_12_SLAB_AABB_COVER", "geometry method mismatch")
        require(int(method.get("slab_count", -1)) == SLAB_COUNT, "contract slab count mismatch")
        require(float(method.get("transverse_guard_mm", math.nan)) == 0.005, "transverse guard mismatch")
        require(normalize_unit(method.get("source_unit")) == "m", "contract source unit mismatch")
        require(normalize_unit(method.get("step_unit")) == "mm", "contract STEP unit mismatch")
        require(normalize_unit(method.get("runtime_unit")) == "m", "contract runtime unit mismatch")
        global_checks["contract_schema_scope_and_method_locked"] = True

        contract_authority = contract.get("authority_flags", {})
        require(set(contract_authority) == {
            "parent_mechanical_gate_reissued",
            "system_registry_reissued",
            "system_pair_evaluation_authorized",
            "path_search_authorized",
            "next_stage_authorized",
            "release_credit",
        }, "contract authority-flag set mismatch")
        require(all(value is False for value in contract_authority.values()), "contract grants forbidden authority")
        require_no_authority_true(contract, "contract")
        global_checks["contract_authority_flags_fail_closed"] = True

        require(
            source_lock.get("schema") == "B601_RIGID_LINK_OPERATIONAL_COLLISION_SOURCE_AUTHORITY_LOCK_V1",
            "source-lock schema mismatch",
        )
        for flag in ("source_mutation_authorized", "accepted_urdf_mutation_authorized", "parent_gate_mutation_authorized"):
            require(source_lock.get(flag) is False, f"source lock improperly sets {flag}")
        global_checks["source_lock_schema_and_mutation_flags_fail_closed"] = True

        require(set(source_lock.get("link_sources", {})) == set(LINK_IDS), "source lock link set mismatch")
        require(
            contract.get("object_ids") == [f"A::{link_id}" for link_id in LINK_IDS],
            "contract object-id sequence mismatch",
        )
        for link_id in LINK_IDS:
            record = source_lock["link_sources"][link_id]
            require(record.get("object_id") == f"A::{link_id}", f"{link_id} object-id mismatch")
            require(record.get("frame") == link_id, f"{link_id} source frame mismatch")
        global_checks["six_link_source_records_present"] = True

        for label, record in source_lock.get("immutable_sources", {}).items():
            immutable_records[label] = validate_pinned_file(root, label, record)
        require(bool(immutable_records), "source lock has no immutable authority sources")
        global_checks["immutable_authority_source_hashes_match"] = True
    except Exception as exc:  # deterministic fail-closed aggregation
        failures.append(f"GLOBAL: {type(exc).__name__}: {exc}")

    per_link: dict[str, Any] = {}
    if root is not None and contract is not None and source_lock is not None:
        for link_id in LINK_IDS:
            try:
                per_link[link_id] = validate_link(root, contract, source_lock, link_id)
            except Exception as exc:  # preserve every link's fail-closed state
                message = f"{link_id}: {type(exc).__name__}: {exc}"
                failures.append(message)
                per_link[link_id] = {
                    "link_id": link_id,
                    "validation_pass": False,
                    "error": message,
                    "checks": {},
                }
    else:
        for link_id in LINK_IDS:
            message = f"{link_id}: global contract/source-lock prerequisites unavailable"
            failures.append(message)
            per_link[link_id] = {
                "link_id": link_id,
                "validation_pass": False,
                "error": message,
                "checks": {},
            }

    all_global = all(global_checks.values())
    links_passed = sum(bool(per_link[link_id].get("validation_pass")) for link_id in LINK_IDS)
    validation_pass = bool(all_global and links_passed == len(LINK_IDS) and not failures)
    root_for_records = root if root is not None else PACKAGE_DIR
    result: dict[str, Any] = {
        "schema": "B601_RIGID_LINK_OPERATIONAL_PROXY_INDEPENDENT_VALIDATION_V1",
        "artifact_role": "INDEPENDENT_GEOMETRY_REPRODUCTION_AND_SERIALIZED_ARTIFACT_AUDIT",
        "scope": "SIX_B601_RIGID_LINK_LOCAL_COLLISION_PROXY_CANDIDATES_ONLY",
        "independence_statement": {
            "candidate_builder_imported": False,
            "candidate_builder_source_used_as_runtime_dependency": False,
            "source_ply_read_directly": True,
            "step_reopened_with_occt": True,
            "npz_and_stl_read_from_serialized_artifacts": True,
        },
        "dependency_versions": {
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "trimesh": trimesh.__version__,
            "ocp": OCP_VERSION,
        },
        "contract": file_record(CONTRACT_PATH, root_for_records) if CONTRACT_PATH.is_file() else None,
        "source_authority_lock": file_record(SOURCE_LOCK_PATH, root_for_records) if SOURCE_LOCK_PATH.is_file() else None,
        "validator": file_record(Path(__file__), root_for_records),
        "immutable_authority_sources": immutable_records,
        "global_checks": global_checks,
        "per_link": per_link,
        "summary": {
            "required_link_count": len(LINK_IDS),
            "passed_link_count": int(links_passed),
            "failed_link_count": int(len(LINK_IDS) - links_passed),
            "global_checks_passed": int(sum(global_checks.values())),
            "global_checks_required": int(len(global_checks)),
        },
        "failures": failures,
        "validation_pass": validation_pass,
        "formal_gate_pass": validation_pass,
        "review_status": "PENDING_OWNER_REVIEW",
        "authority_flags": {
            "parent_mechanical_gate_reissued": False,
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "maximum_legal_claim": (
            "B601_RIGID_LINK_OPERATIONAL_COLLISION_PROXY_CANDIDATE_6_OF_6_INDEPENDENT_GEOMETRY_PASS__"
            "SYSTEM_REGISTRY_PAIR_EDGE_PATH_AND_RELEASE_HOLD"
            if validation_pass
            else "B601_RIGID_LINK_OPERATIONAL_COLLISION_PROXY_INDEPENDENT_VALIDATION_HOLD__"
            "FAIL_CLOSED__NO_SYSTEM_PAIR_EDGE_PATH_OR_RELEASE_AUTHORITY"
        ),
        "verdict": (
            "INDEPENDENT_VALIDATION_PASS_LOCAL_GEOMETRY_ONLY_NO_PAIR_OR_PATH_AUTHORITY"
            if validation_pass
            else "INDEPENDENT_VALIDATION_FAIL_CLOSED_INPUT_OR_GEOMETRY_HOLD"
        ),
    }
    return result


def encode_result(result: dict[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help=f"atomically write {RESULT_PATH.name}")
    mode.add_argument(
        "--verify-existing",
        action="store_true",
        help="rerun independently and require byte-identical existing validation JSON",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    result = validate_all()
    payload = encode_result(result)
    if args.verify_existing:
        require(RESULT_PATH.is_file(), f"existing validation missing: {RESULT_PATH}")
        require(RESULT_PATH.read_bytes() == payload, "existing validation differs from fresh independent run")
    elif args.write:
        atomic_write(RESULT_PATH, payload)
    print(payload.decode("utf-8"), end="")
    return 0 if result["validation_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
