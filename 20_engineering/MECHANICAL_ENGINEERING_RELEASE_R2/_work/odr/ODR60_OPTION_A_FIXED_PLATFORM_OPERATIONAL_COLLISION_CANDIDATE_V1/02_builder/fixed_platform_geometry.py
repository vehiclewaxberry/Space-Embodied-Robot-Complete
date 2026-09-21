#!/usr/bin/env python3
"""Deterministic geometry utilities for the three fixed-platform candidates.

This module is deliberately local to the candidate package.  It consumes
hash-pinned STEP/BRep sources, emits millimetre STEP as the primary geometry,
and derives metre runtime sidecars.  It has no authority to edit M01.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import struct
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Trsf


PACKAGE = Path(__file__).resolve().parents[1]
CONTRACT_DIR = PACKAGE / "00_contract"
CAD_DIR = PACKAGE / "01_cad"
RUNTIME_DIR = PACKAGE / "02_runtime"
RESULTS_DIR = PACKAGE / "05_results"
CONTRACT_PATH = CONTRACT_DIR / "FIXED_PLATFORM_OPERATIONAL_COLLISION_CONTRACT_V1.json"
SOURCE_LOCK_PATH = CONTRACT_DIR / "SOURCE_AUTHORITY_LOCK_V1.json"
FRAME_LEDGER_PATH = CONTRACT_DIR / "FRAME_AND_UNIT_LEDGER_V1.json"

LINEAR_DEFLECTION_MM = 0.05
ANGULAR_DEFLECTION_RAD = math.radians(5.0)
VERTEX_ROUND_DECIMALS_M = 12
STEP_BBOX_TOLERANCE_MM = 1.0e-7
STEP_VOLUME_REL_TOLERANCE = 1.0e-10
SOURCE_LEDGER_BBOX_TOLERANCE_MM = 1.0e-6
SOURCE_LEDGER_VOLUME_REL_TOLERANCE = 1.0e-9
PRIMARY_NUMERIC_DERATE_MM = 1.0e-6
RUNTIME_CHORDAL_DERATE_MM = LINEAR_DEFLECTION_MM

OBJECTS: dict[str, dict[str, Any]] = {
    "load_bridge": {
        "object_id": "F::LOAD_BRIDGE",
        "source_rel": Path("20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_CANDIDATE_V1.step"),
        "source_frame": "S",
        "output_frame": "S",
        "transform_rule": "IDENTITY_SOURCE_ALREADY_AUTHORED_IN_S",
        "step_name": "F_LOAD_BRIDGE_S_V1.step",
        "runtime_stem": "F_LOAD_BRIDGE_S_M_V1",
        "receipt_name": "F_LOAD_BRIDGE_GEOMETRY_RECEIPT_V1.json",
        "expected_local_bbox_mm": [[185.25, -104.982394538, -105.084754759], [196.0, 105.01438284, 104.912022619]],
        "expected_volume_mm3": 260072.391934165,
    },
    "m3r_stage_a": {
        "object_id": "F::M3R_STAGE_A",
        "source_rel": Path("20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_STAGE_A_REVB_WORKING.step"),
        "source_frame": "M3R_LOCAL",
        "output_frame": "S",
        "transform_rule": "APPLY_T_S_M3R_LOCAL_EXACTLY_ONCE",
        "step_name": "F_M3R_STAGE_A_S_V1.step",
        "runtime_stem": "F_M3R_STAGE_A_S_M_V1",
        "receipt_name": "F_M3R_STAGE_A_GEOMETRY_RECEIPT_V1.json",
        "expected_local_bbox_mm": [[-75.0, -75.0, -5.595], [75.0, 75.0, 2.405]],
        "expected_volume_mm3": 127784.800332951,
    },
    "m3r_stage_b": {
        "object_id": "F::M3R_STAGE_B",
        "source_rel": Path("20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_STAGE_B_REVB2_WORKING.step"),
        "source_frame": "M3R_LOCAL",
        "output_frame": "S",
        "transform_rule": "APPLY_T_S_M3R_LOCAL_EXACTLY_ONCE",
        "step_name": "F_M3R_STAGE_B_S_V1.step",
        "runtime_stem": "F_M3R_STAGE_B_S_M_V1",
        "receipt_name": "F_M3R_STAGE_B_GEOMETRY_RECEIPT_V1.json",
        "expected_local_bbox_mm": [[-85.0, -85.0, -12.0], [85.0, 85.0, 0.0]],
        "expected_volume_mm3": 161966.03222767,
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def workspace_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root containing PROJECT_MAP.md was not found")


def stable_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def strict_json(path: Path) -> dict[str, Any]:
    def no_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {key!r}: {path}")
            result[key] = value
        return result

    require(path.is_file(), f"required JSON missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(workspace_root()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def byte_record(path: Path, data: bytes) -> dict[str, Any]:
    return {
        "path": path.relative_to(workspace_root()).as_posix(),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def atomic_write(path: Path, data: bytes, *, replace: bool) -> None:
    if path.exists() and not replace:
        raise FileExistsError(f"output exists; use --replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _walk_pin_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"}.issubset(value):
            yield value
        for child in value.values():
            yield from _walk_pin_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_pin_records(child)


def verify_all_source_pins(lock: dict[str, Any]) -> int:
    rows = list(_walk_pin_records(lock))
    require(rows, "source lock contains no pins")
    root = workspace_root()
    seen: set[str] = set()
    for row in rows:
        relative = str(row["path"]).replace("\\", "/")
        require(relative not in seen, f"duplicate source pin: {relative}")
        seen.add(relative)
        candidate = Path(relative)
        path = candidate if candidate.is_absolute() else root / candidate
        require(path.is_file(), f"pinned source missing: {relative}")
        require(path.stat().st_size == int(row["bytes"]), f"pinned source byte drift: {relative}")
        require(sha256_path(path) == str(row["sha256"]).upper(), f"pinned source hash drift: {relative}")
    return len(rows)


def source_pin(lock: dict[str, Any], relative: Path) -> dict[str, Any]:
    key = relative.as_posix()
    matches = [row for row in _walk_pin_records(lock) if str(row["path"]).replace("\\", "/") == key]
    require(len(matches) == 1, f"source lock must pin exactly once: {key}")
    return matches[0]


def read_step(path: Path):
    reader = STEPControl_Reader()
    require(reader.ReadFile(str(path)) == IFSelect_RetDone, f"STEP read failed: {path}")
    require(int(reader.TransferRoots()) >= 1, f"STEP transferred no roots: {path}")
    shape = reader.OneShape()
    require(not shape.IsNull(), f"STEP transferred null shape: {path}")
    return shape


def bbox_mm(shape) -> np.ndarray:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    return np.asarray(box.Get(), dtype=np.float64).reshape(2, 3)


def volume_mm3(shape) -> float:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties, False, False, True)
    return float(properties.Mass())


def solids(shape) -> list[Any]:
    result: list[Any] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        result.append(TopoDS.Solid_s(explorer.Current()))
        explorer.Next()
    return result


def solid_rows(shape) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, solid in enumerate(solids(shape)):
        face_count = 0
        explorer = TopExp_Explorer(solid, TopAbs_FACE)
        while explorer.More():
            face_count += 1
            explorer.Next()
        shell_count = 0
        all_closed = True
        explorer = TopExp_Explorer(solid, TopAbs_SHELL)
        while explorer.More():
            shell_count += 1
            all_closed &= bool(BRep_Tool.IsClosed_s(explorer.Current()))
            explorer.Next()
        rows.append({
            "index": index,
            "shape": solid,
            "bbox_mm": bbox_mm(solid),
            "volume_mm3": volume_mm3(solid),
            "brep_valid": bool(BRepCheck_Analyzer(solid, True).IsValid()),
            "face_count": face_count,
            "shell_count": shell_count,
            "all_shells_closed": bool(shell_count > 0 and all_closed),
        })
    return rows


def validate_single_solid(shape, *, context: str) -> dict[str, Any]:
    rows = solid_rows(shape)
    require(len(rows) == 1, f"{context}: expected one solid; got {len(rows)}")
    row = rows[0]
    require(row["brep_valid"], f"{context}: invalid BRep")
    require(row["all_shells_closed"], f"{context}: open shell")
    require(math.isfinite(row["volume_mm3"]) and row["volume_mm3"] > 0.0, f"{context}: invalid volume")
    return row


def trsf_from_matrix(matrix: np.ndarray) -> gp_Trsf:
    value = np.asarray(matrix, dtype=np.float64)
    require(value.shape == (4, 4), "transform must be 4x4")
    require(np.all(np.isfinite(value)), "transform contains non-finite values")
    require(np.max(np.abs(value[3] - np.asarray([0.0, 0.0, 0.0, 1.0]))) <= 1.0e-14, "invalid homogeneous row")
    rotation = value[:3, :3]
    require(np.max(np.abs(rotation.T @ rotation - np.eye(3))) <= 2.0e-12, "rotation is not orthonormal")
    require(abs(float(np.linalg.det(rotation)) - 1.0) <= 2.0e-12, "rotation determinant is not +1")
    transform = gp_Trsf()
    transform.SetValues(*(float(value[row, column]) for row in range(3) for column in range(4)))
    return transform


def transform_shape(shape, matrix: np.ndarray):
    operation = BRepBuilderAPI_Transform(shape, trsf_from_matrix(matrix), True)
    operation.Build()
    require(operation.IsDone(), "OCP rigid transform failed")
    result = operation.Shape()
    require(not result.IsNull(), "OCP rigid transform returned null shape")
    return result


def canonicalize_step_bytes(data: bytes) -> bytes:
    text = data.decode("latin-1")
    pattern = re.compile(r"(FILE_NAME\([^,]+,')([^']+)(')")
    text, count = pattern.subn(r"\g<1>2000-01-01T00:00:00\g<3>", text, count=1)
    require(count == 1, "STEP header timestamp could not be canonicalized")
    return text.replace("\r\n", "\n").encode("latin-1")


def write_step_bytes(shape) -> bytes:
    with tempfile.TemporaryDirectory(prefix="fixed_platform_step_") as directory:
        path = Path(directory) / "candidate.step"
        writer = STEPControl_Writer()
        require(writer.Transfer(shape, STEPControl_AsIs) == IFSelect_RetDone, "STEP transfer failed")
        require(writer.Write(str(path)) == IFSelect_RetDone, "STEP write failed")
        return canonicalize_step_bytes(path.read_bytes())


def read_step_from_bytes(data: bytes):
    with tempfile.TemporaryDirectory(prefix="fixed_platform_reopen_") as directory:
        path = Path(directory) / "candidate.step"
        path.write_bytes(data)
        return read_step(path)


def _transform_node(point, location: TopLoc_Location) -> tuple[float, float, float]:
    transformed = point.Transformed(location.Transformation())
    return transformed.X(), transformed.Y(), transformed.Z()


def extract_triangles_m(shape) -> tuple[np.ndarray, np.ndarray]:
    rows = solid_rows(shape)
    require(len(rows) == 1, "runtime extraction requires one solid")
    triangles: list[np.ndarray] = []
    solid_ids: list[int] = []
    for solid_id, row in enumerate(rows):
        mesher = BRepMesh_IncrementalMesh(row["shape"], LINEAR_DEFLECTION_MM, False, ANGULAR_DEFLECTION_RAD, False)
        mesher.Perform()
        require(mesher.IsDone(), "OCP meshing failed")
        explorer = TopExp_Explorer(row["shape"], TopAbs_FACE)
        while explorer.More():
            face = TopoDS.Face_s(explorer.Current())
            location = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation_s(face, location)
            require(triangulation is not None and triangulation.NbTriangles() > 0, "face has no triangulation")
            nodes = np.asarray([
                _transform_node(triangulation.Node(index), location)
                for index in range(1, triangulation.NbNodes() + 1)
            ], dtype=np.float64) * 1.0e-3
            reverse = face.Orientation() == TopAbs_REVERSED
            for index in range(1, triangulation.NbTriangles() + 1):
                a, b, c = triangulation.Triangle(index).Get()
                indices = [a - 1, b - 1, c - 1]
                if reverse:
                    indices[1], indices[2] = indices[2], indices[1]
                triangles.append(nodes[indices])
                solid_ids.append(solid_id)
            explorer.Next()
    require(triangles, "no runtime triangles produced")
    return np.asarray(triangles, dtype=np.float64), np.asarray(solid_ids, dtype=np.uint16)


def signed_volume_m3(vertices: np.ndarray, faces: np.ndarray) -> float:
    triangles = vertices[faces]
    return float(np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6.0)


def canonicalize_mesh(triangles_m: np.ndarray, solid_ids: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    flat = np.round(triangles_m.reshape(-1, 3), decimals=VERTEX_ROUND_DECIMALS_M).astype("<f8")
    vertices, inverse = np.unique(flat, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3).astype(np.int64)
    cross = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    degenerate = ((faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2]) | (faces[:, 2] == faces[:, 0]) | (np.linalg.norm(cross, axis=1) <= 1.0e-16))
    removed = int(np.count_nonzero(degenerate))
    if removed:
        faces = faces[~degenerate]
        solid_ids = solid_ids[~degenerate]
    volume = signed_volume_m3(vertices, faces)
    require(math.isfinite(volume) and abs(volume) > 1.0e-18, "runtime mesh has zero/nonfinite volume")
    flipped = False
    if volume < 0.0:
        faces[:, 1], faces[:, 2] = faces[:, 2].copy(), faces[:, 1].copy()
        flipped = True
    keys = np.sort(faces, axis=1)
    keys = keys[np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))]
    duplicates = int(np.count_nonzero(np.all(keys[1:] == keys[:-1], axis=1)))
    require(duplicates == 0, f"runtime mesh duplicate triangles: {duplicates}")
    minimum_position = np.argmin(faces, axis=1)
    rotated = np.empty_like(faces)
    for position in range(3):
        selection = minimum_position == position
        rotated[selection] = faces[selection][:, [position, (position + 1) % 3, (position + 2) % 3]]
    faces = rotated
    order = np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0], solid_ids))
    return vertices.astype("<f8"), faces[order].astype("<u4"), solid_ids[order].astype("<u2"), {
        "removed_zero_area_triangle_count": removed,
        "within_solid_duplicate_triangle_count": duplicates,
        "outward_winding_flipped": flipped,
    }


def manifold_metrics(faces: np.ndarray) -> dict[str, Any]:
    local = faces.astype(np.int64)
    directed = np.concatenate((local[:, [0, 1]], local[:, [1, 2]], local[:, [2, 0]]), axis=0)
    undirected = np.sort(directed, axis=1)
    unique_edges, inverse, counts = np.unique(undirected, axis=0, return_inverse=True, return_counts=True)
    boundary = int(np.count_nonzero(counts == 1))
    nonmanifold = int(np.count_nonzero(counts > 2))
    forward = np.bincount(inverse, weights=(directed[:, 0] < directed[:, 1]).astype(np.int8), minlength=len(unique_edges))
    orientation_mismatch = int(np.count_nonzero(forward != counts - forward))
    require(boundary == nonmanifold == orientation_mismatch == 0, "runtime mesh is not a closed oriented 2-manifold")
    return {
        "boundary_edge_count": boundary,
        "nonmanifold_edge_count": nonmanifold,
        "orientation_mismatch_edge_count": orientation_mismatch,
        "closed_oriented_two_manifold": True,
    }


def npy_bytes(array: np.ndarray) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(stream, np.asarray(array), allow_pickle=False)
    return stream.getvalue()


def deterministic_npz(arrays: dict[str, np.ndarray]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(arrays):
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o600 << 16
            info.create_system = 3
            archive.writestr(info, npy_bytes(arrays[name]))
    return stream.getvalue()


def binary_stl(vertices_m: np.ndarray, faces: np.ndarray, object_id: str) -> bytes:
    header = f"FIXED PLATFORM LOCAL CANDIDATE; UNITS=M; FRAME=S; OBJECT={object_id}".encode("ascii")
    output = io.BytesIO()
    output.write(header[:80].ljust(80, b"\0"))
    output.write(struct.pack("<I", int(len(faces))))
    triangles = vertices_m[faces].astype(np.float64)
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    norms = np.linalg.norm(normals, axis=1)
    require(bool(np.all(norms > 0.0)), "runtime STL contains degenerate triangle")
    normals /= norms[:, None]
    for normal, triangle in zip(normals.astype("<f4"), triangles.astype("<f4"), strict=True):
        output.write(struct.pack("<12fH", *(normal.tolist() + triangle.reshape(-1).tolist()), 0))
    return output.getvalue()


def binary_ply(vertices_m: np.ndarray, faces: np.ndarray, object_id: str) -> bytes:
    require(int(faces.max()) < len(vertices_m), "runtime PLY index overflow")
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        "comment FIXED_PLATFORM_OPERATIONAL_COLLISION_CANDIDATE_V1\n"
        "comment units=m\ncomment frame=S\n"
        f"comment object_id={object_id}\n"
        f"element vertex {len(vertices_m)}\n"
        "property double x\nproperty double y\nproperty double z\n"
        f"element face {len(faces)}\nproperty list uchar uint vertex_indices\nend_header\n"
    ).encode("ascii")
    output = io.BytesIO()
    output.write(header)
    output.write(np.asarray(vertices_m, dtype="<f8").tobytes(order="C"))
    for face in np.asarray(faces, dtype="<u4"):
        output.write(struct.pack("<BIII", 3, int(face[0]), int(face[1]), int(face[2])))
    return output.getvalue()


def json_metadata_array(metadata: dict[str, Any]) -> np.ndarray:
    return np.frombuffer(json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8"), dtype=np.uint8)
