#!/usr/bin/env python3
"""Deterministic OCP utilities for Route-C root-static R20 candidates."""

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
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepTools import BRepTools
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Shape
from OCP.gp import gp_Trsf


PACKAGE = Path(__file__).resolve().parents[1]
CONTRACT_DIR = PACKAGE / "00_contract"
CAD_DIR = PACKAGE / "01_cad"
RUNTIME_DIR = PACKAGE / "02_runtime"
RESULTS_DIR = PACKAGE / "05_results"
CONTRACT_PATH = CONTRACT_DIR / "ROOT_STATIC_R20_OPERATIONAL_COLLISION_CONTRACT_V1.json"
SOURCE_LOCK_PATH = CONTRACT_DIR / "SOURCE_AUTHORITY_LOCK_V1.json"
FRAME_LEDGER_PATH = CONTRACT_DIR / "FRAME_AND_UNIT_LEDGER_V1.json"

LINEAR_DEFLECTION_MM = 0.05
ANGULAR_DEFLECTION_RAD = math.radians(5.0)
VERTEX_ROUND_DECIMALS_M = 12


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


def verify_source_pins(lock: dict[str, Any]) -> int:
    rows = lock["source_pins"]
    require(len(rows) == 13, "source lock must contain 13 pins")
    root = workspace_root()
    seen = set()
    for row in rows:
        relative = str(row["path"]).replace("\\", "/")
        require(relative not in seen, f"duplicate source pin: {relative}")
        seen.add(relative)
        path = root / relative
        require(path.is_file(), f"pinned source missing: {relative}")
        require(path.stat().st_size == int(row["bytes"]), f"pinned source byte drift: {relative}")
        require(sha256_path(path) == str(row["sha256"]).upper(), f"pinned source hash drift: {relative}")
    return len(rows)


def read_brep(path: Path):
    shape = TopoDS_Shape()
    builder = BRep_Builder()
    require(bool(BRepTools.Read_s(shape, str(path), builder)), f"BREP read failed: {path}")
    require(not shape.IsNull(), f"BREP returned null shape: {path}")
    return shape


def read_step(path: Path):
    reader = STEPControl_Reader()
    require(reader.ReadFile(str(path)) == IFSelect_RetDone, f"STEP read failed: {path}")
    transferred_roots = int(reader.TransferRoots())
    require(transferred_roots == 1, f"STEP must transfer exactly one root, got {transferred_roots}: {path}")
    shape = reader.OneShape()
    require(not shape.IsNull(), f"STEP transferred null shape: {path}")
    return shape


def read_step_bytes(data: bytes):
    with tempfile.TemporaryDirectory(prefix="route_c_r20_reopen_") as directory:
        path = Path(directory) / "candidate.step"
        path.write_bytes(data)
        return read_step(path)


def bbox_mm(shape) -> np.ndarray:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    return np.asarray(box.Get(), dtype=np.float64).reshape(2, 3)


def volume_mm3(shape) -> float:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties, False, False, True)
    return float(properties.Mass())


def solids(shape) -> list[Any]:
    result = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        result.append(TopoDS.Solid_s(explorer.Current()))
        explorer.Next()
    return result


def solid_rows(shape) -> list[dict[str, Any]]:
    rows = []
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
        rows.append(
            {
                "index": index,
                "shape": solid,
                "bbox_mm": bbox_mm(solid),
                "volume_mm3": volume_mm3(solid),
                "brep_valid": bool(BRepCheck_Analyzer(solid, True).IsValid()),
                "face_count": face_count,
                "shell_count": shell_count,
                "all_shells_closed": bool(shell_count > 0 and all_closed),
            }
        )
    return rows


def validate_single_solid(shape, *, context: str) -> dict[str, Any]:
    rows = solid_rows(shape)
    require(len(rows) == 1, f"{context}: expected one solid; got {len(rows)}")
    row = rows[0]
    require(row["brep_valid"], f"{context}: invalid BRep")
    require(row["all_shells_closed"], f"{context}: open shell")
    require(math.isfinite(row["volume_mm3"]) and row["volume_mm3"] > 0.0, f"{context}: invalid volume")
    return row


def matrix_from_ledger(ledger: dict[str, Any]) -> np.ndarray:
    strings = ledger["phase_A_root_static_R20"]["canonical_matrix_decimal_strings_mm"]
    matrix = np.asarray([[float(value) for value in row] for row in strings], dtype=np.float64)
    require(matrix.shape == (4, 4), "T_S_A0 must be 4x4")
    rotation = matrix[:3, :3]
    tolerance = 1.0e-11
    require(np.max(np.abs(rotation.T @ rotation - np.eye(3))) <= tolerance, "T_S_A0 rotation is not orthonormal")
    require(abs(float(np.linalg.det(rotation)) - 1.0) <= tolerance, "T_S_A0 determinant drift")
    require(np.max(np.abs(matrix[3] - [0.0, 0.0, 0.0, 1.0])) <= 1.0e-14, "invalid homogeneous row")
    return matrix


def transform_shape(shape, matrix: np.ndarray):
    transform = gp_Trsf()
    transform.SetValues(*(float(matrix[row, column]) for row in range(3) for column in range(4)))
    operation = BRepBuilderAPI_Transform(shape, transform, True)
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
    with tempfile.TemporaryDirectory(prefix="route_c_r20_step_") as directory:
        path = Path(directory) / "candidate.step"
        writer = STEPControl_Writer()
        require(writer.Transfer(shape, STEPControl_AsIs) == IFSelect_RetDone, "STEP transfer failed")
        require(writer.Write(str(path)) == IFSelect_RetDone, "STEP write failed")
        return canonicalize_step_bytes(path.read_bytes())


def _transform_node(point, location: TopLoc_Location) -> tuple[float, float, float]:
    transformed = point.Transformed(location.Transformation())
    return transformed.X(), transformed.Y(), transformed.Z()


def extract_triangles_m(shape) -> tuple[np.ndarray, np.ndarray]:
    rows = solid_rows(shape)
    require(len(rows) == 1, "R20 runtime extraction requires one solid")
    triangles = []
    solid_ids = []
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
            nodes = np.asarray(
                [_transform_node(triangulation.Node(index), location) for index in range(1, triangulation.NbNodes() + 1)],
                dtype=np.float64,
            ) * 1.0e-3
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


def canonicalize_mesh(triangles_m: np.ndarray, solid_ids: np.ndarray):
    flat = np.round(triangles_m.reshape(-1, 3), decimals=VERTEX_ROUND_DECIMALS_M).astype("<f8")
    vertices, inverse = np.unique(flat, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3).astype(np.int64)
    cross = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    degenerate = (
        (faces[:, 0] == faces[:, 1])
        | (faces[:, 1] == faces[:, 2])
        | (faces[:, 2] == faces[:, 0])
        | (np.linalg.norm(cross, axis=1) <= 1.0e-16)
    )
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
    minimum_position = np.argmin(faces, axis=1)
    rotated = np.empty_like(faces)
    for position in range(3):
        selection = minimum_position == position
        rotated[selection] = faces[selection][:, [position, (position + 1) % 3, (position + 2) % 3]]
    faces = rotated
    order = np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0], solid_ids))
    return vertices.astype("<f8"), faces[order].astype("<u4"), solid_ids[order].astype("<u2"), {
        "removed_zero_area_triangle_count": removed,
        "outward_winding_flipped": flipped,
    }


def manifold_metrics(faces: np.ndarray) -> dict[str, Any]:
    local = faces.astype(np.int64)
    directed = np.concatenate((local[:, [0, 1]], local[:, [1, 2]], local[:, [2, 0]]), axis=0)
    undirected = np.sort(directed, axis=1)
    unique_edges, inverse, counts = np.unique(undirected, axis=0, return_inverse=True, return_counts=True)
    boundary = int(np.count_nonzero(counts == 1))
    nonmanifold = int(np.count_nonzero(counts > 2))
    forward = np.bincount(
        inverse,
        weights=(directed[:, 0] < directed[:, 1]).astype(np.int8),
        minlength=len(unique_edges),
    )
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
    header = f"ROUTE-C R20 LOCAL CANDIDATE; UNITS=M; FRAME=S; OBJECT={object_id}".encode("ascii")
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
        "comment ODR60_OPTION_A_ROUTE_C_R121_PHASE_A_ROOT_STATIC_R20\n"
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
    payload = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return np.frombuffer(payload, dtype=np.uint8)
