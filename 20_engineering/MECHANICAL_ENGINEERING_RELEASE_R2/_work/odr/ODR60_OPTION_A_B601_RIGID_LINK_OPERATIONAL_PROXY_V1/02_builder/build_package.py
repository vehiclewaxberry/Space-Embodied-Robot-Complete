"""Emit deterministic runtime collision assets and local geometry receipts.

The six STEP files are the primary design artifacts.  This emitter reopens
those files, proves that their twelve BRep boxes agree with the frozen
analytical cover, and derives meter-unit NPZ/STL assets for later collision
backend binding.  It intentionally grants no system-pair or path authority.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np
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

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ASSETS = PACKAGE / "03_assets"
RESULTS = PACKAGE / "05_results"
sys.path.insert(0, str(HERE))

from proxy_geometry import (  # noqa: E402
    CONTRACT_PATH,
    SOURCE_LOCK_PATH,
    point_membership,
    read_json,
    sectional_convex_cover,
    sha256_path,
    workspace_root,
)


LINK_IDS = tuple(f"link{i}" for i in range(1, 7))
STEP_BBOX_TOLERANCE_MM = 2.0e-5
STEP_VOLUME_REL_TOLERANCE = 2.0e-9


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def file_record(path: Path) -> dict[str, Any]:
    root = workspace_root()
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def byte_record(path: Path, data: bytes) -> dict[str, Any]:
    root = workspace_root()
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
    }


def read_step(path: Path):
    reader = STEPControl_Reader()
    require(reader.ReadFile(str(path)) == IFSelect_RetDone, f"STEP read failed: {path.name}")
    require(int(reader.TransferRoots()) == 1, f"STEP root count invalid: {path.name}")
    shape = reader.OneShape()
    require(not shape.IsNull(), f"STEP transferred null shape: {path.name}")
    return shape


def bbox_mm(shape) -> np.ndarray:
    bound = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, bound, False, False)
    return np.asarray(bound.Get(), dtype=np.float64).reshape(2, 3)


def volume_mm3(shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, False, False, True)
    return float(props.Mass())


def reopened_step_rows(path: Path) -> list[dict[str, Any]]:
    shape = read_step(path)
    rows: list[dict[str, Any]] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = TopoDS.Solid_s(explorer.Current())
        rows.append(
            {
                "bbox_mm": bbox_mm(solid),
                "volume_mm3": volume_mm3(solid),
                "brep_valid": bool(BRepCheck_Analyzer(solid, True).IsValid()),
            }
        )
        explorer.Next()
    return rows


def box_meshes(boxes_m: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    unit_faces = np.asarray(
        [
            [0, 2, 1], [0, 3, 2],       # -Z
            [4, 5, 6], [4, 6, 7],       # +Z
            [0, 1, 5], [0, 5, 4],       # -Y
            [3, 7, 6], [3, 6, 2],       # +Y
            [0, 4, 7], [0, 7, 3],       # -X
            [1, 2, 6], [1, 6, 5],       # +X
        ],
        dtype=np.uint32,
    )
    vertices: list[np.ndarray] = []
    triangles: list[np.ndarray] = []
    vertex_offsets = [0]
    triangle_offsets = [0]
    for box in boxes_m:
        lo, hi = box
        verts = np.asarray(
            [
                [lo[0], lo[1], lo[2]], [hi[0], lo[1], lo[2]],
                [hi[0], hi[1], lo[2]], [lo[0], hi[1], lo[2]],
                [lo[0], lo[1], hi[2]], [hi[0], lo[1], hi[2]],
                [hi[0], hi[1], hi[2]], [lo[0], hi[1], hi[2]],
            ],
            dtype="<f8",
        )
        vertices.append(verts)
        triangles.append(unit_faces + np.uint32(vertex_offsets[-1]))
        vertex_offsets.append(vertex_offsets[-1] + 8)
        triangle_offsets.append(triangle_offsets[-1] + 12)
    return (
        np.vstack(vertices).astype("<f8", copy=False),
        np.vstack(triangles).astype("<u4", copy=False),
        np.asarray(vertex_offsets, dtype="<u4"),
        np.asarray(triangle_offsets, dtype="<u4"),
    )


def signed_volume(vertices: np.ndarray, triangles: np.ndarray) -> float:
    tri = vertices[triangles]
    return float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0)


def per_solid_topology(
    vertices: np.ndarray,
    triangles: np.ndarray,
    vertex_offsets: np.ndarray,
    triangle_offsets: np.ndarray,
) -> dict[str, Any]:
    closed = True
    oriented = True
    positive = True
    volumes: list[float] = []
    for index in range(12):
        faces = triangles[triangle_offsets[index] : triangle_offsets[index + 1]]
        directed: dict[tuple[int, int], int] = {}
        undirected: dict[tuple[int, int], int] = {}
        for face in faces:
            for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
                aa, bb = int(a), int(b)
                directed[(aa, bb)] = directed.get((aa, bb), 0) + 1
                key = tuple(sorted((aa, bb)))
                undirected[key] = undirected.get(key, 0) + 1
        closed &= all(count == 2 for count in undirected.values())
        oriented &= all(directed.get((b, a), 0) == count for (a, b), count in directed.items())
        volume = signed_volume(vertices, faces)
        volumes.append(volume)
        positive &= volume > 0.0
        require(int(faces.min()) >= int(vertex_offsets[index]), "solid triangle underflow")
        require(int(faces.max()) < int(vertex_offsets[index + 1]), "solid triangle overflow")
    return {
        "per_solid_closed": bool(closed),
        "per_solid_consistently_oriented": bool(oriented),
        "per_solid_positive_signed_volume": bool(positive),
        "per_solid_volume_m3": volumes,
    }


def npy_bytes(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.lib.format.write_array(buffer, np.asarray(array), allow_pickle=False)
    return buffer.getvalue()


def deterministic_npz(arrays: dict[str, np.ndarray]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(arrays):
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o600 << 16
            archive.writestr(info, npy_bytes(arrays[name]))
    return buffer.getvalue()


def binary_stl(vertices: np.ndarray, triangles: np.ndarray, link_id: str) -> bytes:
    header_text = f"B601 {link_id.upper()} OPERATIONAL COLLISION V1; UNITS=M; LINK-LOCAL"
    header = header_text.encode("ascii")[:80].ljust(80, b"\0")
    tri = vertices[triangles]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    norms = np.linalg.norm(normals, axis=1)
    require(bool(np.all(norms > 0.0)), f"degenerate runtime triangle: {link_id}")
    normals = normals / norms[:, None]
    out = io.BytesIO()
    out.write(header)
    out.write(struct.pack("<I", len(triangles)))
    for normal, points in zip(normals.astype("<f4"), tri.astype("<f4"), strict=True):
        out.write(struct.pack("<12fH", *(normal.tolist() + points.reshape(-1).tolist()), 0))
    return out.getvalue()


def build_link(link_id: str) -> dict[str, Any]:
    cover = sectional_convex_cover(link_id)
    boxes = np.asarray(cover["boxes_m"], dtype="<f8")
    vertices, triangles, vertex_offsets, triangle_offsets = box_meshes(boxes)
    topology = per_solid_topology(vertices, triangles, vertex_offsets, triangle_offsets)
    require(all(topology[key] for key in (
        "per_solid_closed",
        "per_solid_consistently_oriented",
        "per_solid_positive_signed_volume",
    )), f"runtime mesh topology invalid: {link_id}")

    step_path = ASSETS / f"B601_{link_id.upper()}_OPERATIONAL_COLLISION_PROXY_V1.step"
    require(step_path.is_file(), f"primary STEP missing: {step_path.name}")
    rows = reopened_step_rows(step_path)
    require(len(rows) == 12, f"STEP solid count is not 12: {link_id}")
    require(all(row["brep_valid"] for row in rows), f"invalid STEP BRep: {link_id}")
    axis = int(cover["long_axis"])
    rows.sort(key=lambda row: float(np.mean(row["bbox_mm"][:, axis])))
    expected_mm = boxes * 1000.0
    expected_order = np.argsort(np.mean(expected_mm[:, :, axis], axis=1))
    expected_mm = expected_mm[expected_order]
    reopened_mm = np.asarray([row["bbox_mm"] for row in rows], dtype=np.float64)
    max_bbox_error = float(np.max(np.abs(reopened_mm - expected_mm)))
    require(max_bbox_error <= STEP_BBOX_TOLERANCE_MM, f"STEP/runtime bbox mismatch: {link_id}")
    actual_volume = np.asarray([row["volume_mm3"] for row in rows], dtype=np.float64)
    expected_volume = np.prod(expected_mm[:, 1] - expected_mm[:, 0], axis=1)
    volume_relative_error = float(np.max(np.abs(actual_volume - expected_volume) / expected_volume))
    require(volume_relative_error <= STEP_VOLUME_REL_TOLERANCE, f"STEP/runtime volume mismatch: {link_id}")

    source_vertices = np.asarray(cover["mesh"].vertices, dtype=np.float64)
    source_contained = point_membership(source_vertices, boxes)
    hull_contained = point_membership(np.asarray(cover["hull_vertices_m"]), boxes)
    require(bool(np.all(source_contained)), f"source vertex escaped cover: {link_id}")
    require(bool(np.all(hull_contained)), f"hull vertex escaped cover: {link_id}")

    frame = f"B601_{link_id.upper()}_LOCAL"
    arrays = {
        "boxes_m": boxes,
        "frame": np.asarray(frame),
        "link_id": np.asarray(link_id),
        "solid_triangle_offsets": triangle_offsets,
        "solid_vertex_offsets": vertex_offsets,
        "triangles": triangles,
        "units": np.asarray("m"),
        "vertices_m": vertices,
    }
    npz_data = deterministic_npz(arrays)
    stl_data = binary_stl(vertices, triangles, link_id)
    stem = f"B601_{link_id.upper()}_OPERATIONAL_COLLISION_PROXY_V1"
    npz_path = ASSETS / f"{stem}_RUNTIME.npz"
    stl_path = ASSETS / f"{stem}_RUNTIME_M.stl"
    receipt_path = RESULTS / f"B601_{link_id.upper()}_LOCAL_GEOMETRY_RECEIPT_V1.json"
    receipt = {
        "schema": "B601_RIGID_LINK_LOCAL_GEOMETRY_RECEIPT_V1",
        "as_of_date": "2026-08-28",
        "object_id": f"A::{link_id}",
        "authority_scope": "LOCAL_ASSET_LEVEL_COLLISION_GEOMETRY_CANDIDATE_ONLY",
        "classification": "PENDING_OWNER_REVIEW",
        "source": file_record(workspace_root() / read_json(SOURCE_LOCK_PATH)["link_sources"][link_id]["path"]),
        "primary_step": file_record(step_path),
        "runtime_npz": {
            **byte_record(npz_path, npz_data),
            "units": "m",
            "frame": frame,
        },
        "runtime_stl": {
            **byte_record(stl_path, stl_data),
            "units": "m",
            "frame": frame,
            "unit_binding": "RECEIPT_AND_BINARY_HEADER",
        },
        "geometry": {
            "slab_count": 12,
            "long_axis": axis,
            "source_bbox_m": np.asarray(cover["source_bbox_m"]).tolist(),
            "runtime_bbox_m": np.vstack((vertices.min(axis=0), vertices.max(axis=0))).tolist(),
            "source_hull_volume_m3": float(cover["hull_volume_m3"]),
            "proxy_sum_volume_m3": float(cover["proxy_sum_volume_m3"]),
            "volume_over_hull_ratio": float(cover["proxy_sum_volume_m3"] / cover["hull_volume_m3"]),
            "step_reopen_max_bbox_error_mm": max_bbox_error,
            "step_reopen_max_volume_relative_error": volume_relative_error,
            "runtime_vertex_count": int(len(vertices)),
            "runtime_triangle_count": int(len(triangles)),
            **topology,
        },
        "checks": {
            "source_hash_and_bytes_match": True,
            "twelve_positive_brep_valid_solids": True,
            "step_and_runtime_geometry_agree": True,
            "complete_convex_hull_analytical_cover_method_applied": True,
            "source_surface_vertices_contained": True,
            "runtime_per_solid_closed_and_oriented": True,
        },
        "authority_flags": {
            "candidate_may_be_submitted_for_owner_binding": True,
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "parent_mechanical_gate_reissued": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "verdict": "LOCAL_GEOMETRY_CANDIDATE_PASS_PENDING_OWNER_REVIEW_NO_SYSTEM_PAIR_OR_PATH_AUTHORITY",
    }
    receipt_data = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return {
        "link_id": link_id,
        "npz_path": npz_path,
        "npz_data": npz_data,
        "stl_path": stl_path,
        "stl_data": stl_data,
        "receipt_path": receipt_path,
        "receipt_data": receipt_data,
        "receipt": receipt,
    }


def atomic_write(path: Path, data: bytes, *, replace: bool) -> None:
    if path.exists() and not replace:
        raise FileExistsError(f"output exists; use --replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def run(*, verify_existing: bool, replace: bool) -> list[dict[str, Any]]:
    builds = [build_link(link_id) for link_id in LINK_IDS]
    for build in builds:
        for path_key, data_key in (
            ("npz_path", "npz_data"),
            ("stl_path", "stl_data"),
            ("receipt_path", "receipt_data"),
        ):
            path, expected = build[path_key], build[data_key]
            if verify_existing:
                require(path.is_file(), f"existing artifact missing: {path.name}")
                require(path.read_bytes() == expected, f"deterministic replay mismatch: {path.name}")
            else:
                atomic_write(path, expected, replace=replace)
    return builds


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.verify_existing and args.replace:
        raise SystemExit("--replace cannot be used with --verify-existing")
    builds = run(verify_existing=args.verify_existing, replace=args.replace)
    print(json.dumps({"links": [row["link_id"] for row in builds], "status": "PASS"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
