"""Independent helpers for the fixed-platform local collision candidate.

This module lives exclusively in ``04_validation``.  It intentionally does not
import ``02_builder`` or any candidate geometry source.  Primary geometry is
reopened through OpenCascade and all source authority is read from frozen files.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import struct
import tempfile
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_FORWARD, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
from OCP.TopoDS import TopoDS, TopoDS_Shape, TopoDS_Solid
from OCP.gp import gp_Trsf


PACKAGE = Path(__file__).resolve().parents[1]
WORKSPACE_MARKER = "PROJECT_MAP.md"
CONTRACT = PACKAGE / "00_contract" / "FIXED_PLATFORM_OPERATIONAL_COLLISION_CONTRACT_V1.json"
SOURCE_LOCK = PACKAGE / "00_contract" / "SOURCE_AUTHORITY_LOCK_V1.json"
FRAME_LEDGER = PACKAGE / "00_contract" / "FRAME_AND_UNIT_LEDGER_V1.json"
CAD_DIR = PACKAGE / "01_cad"
RUNTIME_DIR = PACKAGE / "02_runtime"
RESULTS_DIR = PACKAGE / "05_results"
REVIEWS_DIR = PACKAGE / "07_reviews"

T_S_M3R_LOCAL = np.asarray(
    [
        [0.0, 0.0, 1.0, 208.0],
        [0.422618483193, 0.906307683772, 0.0, 0.015994151],
        [-0.906307683772, 0.422618483193, 0.0, -0.08636607],
        [0.0, 0.0, 0.0, 1.0],
    ],
    dtype=np.float64,
)

CANDIDATES: dict[str, dict[str, Any]] = {
    "load_bridge": {
        "object_id": "F::LOAD_BRIDGE",
        "frame": "S",
        "step": "F_LOAD_BRIDGE_S_V1.step",
        "ply": "F_LOAD_BRIDGE_S_M_V1.ply",
        "npz": "F_LOAD_BRIDGE_S_M_V1.npz",
        "stl": "F_LOAD_BRIDGE_S_M_V1.stl",
        "source": "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_CANDIDATE_V1.step",
        "source_storage_frame": "S",
        "transform_count": 0,
        "receipt": "F_LOAD_BRIDGE_GEOMETRY_RECEIPT_V1.json",
    },
    "m3r_stage_a": {
        "object_id": "F::M3R_STAGE_A",
        "frame": "S",
        "step": "F_M3R_STAGE_A_S_V1.step",
        "ply": "F_M3R_STAGE_A_S_M_V1.ply",
        "npz": "F_M3R_STAGE_A_S_M_V1.npz",
        "stl": "F_M3R_STAGE_A_S_M_V1.stl",
        "source": "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_STAGE_A_REVB_WORKING.step",
        "source_storage_frame": "M3R_LOCAL",
        "transform_count": 1,
        "receipt": "F_M3R_STAGE_A_GEOMETRY_RECEIPT_V1.json",
    },
    "m3r_stage_b": {
        "object_id": "F::M3R_STAGE_B",
        "frame": "S",
        "step": "F_M3R_STAGE_B_S_V1.step",
        "ply": "F_M3R_STAGE_B_S_M_V1.ply",
        "npz": "F_M3R_STAGE_B_S_M_V1.npz",
        "stl": "F_M3R_STAGE_B_S_M_V1.stl",
        "source": "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_STAGE_B_REVB2_WORKING.step",
        "source_storage_frame": "M3R_LOCAL",
        "transform_count": 1,
        "receipt": "F_M3R_STAGE_B_GEOMETRY_RECEIPT_V1.json",
    },
}

EXPECTED_SYSTEM_INVARIANTS = {
    "active_object_rows": 150,
    "asset_level_operational_authority_rows": 1,
    "local_pending_candidate_rows_before_this_package": 9,
    "local_pending_candidate_rows_after_local_pass": 12,
    "system_object_rows_promoted_by_this_package": 0,
    "required_pair_queries": 11166,
    "system_pair_queries_executed": 0,
    "system_edges_certified": 0,
    "stage_instances_bound": 0,
    "stage_instances_required": 3,
    "system_safe_certificates": 0,
    "system_pair_evaluation_authorized": False,
    "path_search_authorized": False,
    "path_search_executed": False,
    "parent_gate_credit": False,
    "next_stage_authorized": False,
    "release_credit": False,
}

FORBIDDEN_TRUE_KEYS = {
    "system_safe",
    "system_registry_reissued",
    "system_pair_evaluation_authorized",
    "pair_evaluation_authorized",
    "edge_evaluation_authorized",
    "path_search_authorized",
    "path_search_executed",
    "parent_mechanical_gate_reissued",
    "parent_gate_credit",
    "next_stage_authorized",
    "release_credit",
}

HEX64 = re.compile(r"^[0-9A-F]{64}$")


class ValidationFailure(RuntimeError):
    """Fail-closed validation exception."""


def require(condition: Any, message: str) -> None:
    if not bool(condition):
        raise ValidationFailure(message)


def workspace_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / WORKSPACE_MARKER).is_file():
            return candidate
    raise ValidationFailure(f"workspace root containing {WORKSPACE_MARKER} was not found")


def strict_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required JSON missing: {path}")

    def no_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {key!r}: {path}")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"cannot parse deterministic JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def stable_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_path(path: Path) -> str:
    require(path.is_file(), f"hash target missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root().resolve()).as_posix()
    except ValueError as exc:
        raise ValidationFailure(f"path escapes workspace: {path}") from exc


def file_record(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"required file missing: {path}")
    return {"path": relative_path(path), "bytes": path.stat().st_size, "sha256": sha256_path(path)}


def resolve_record_path(record: dict[str, Any]) -> Path:
    raw = record.get("path")
    require(isinstance(raw, str) and raw, "file record path must be non-empty")
    candidate = Path(raw)
    path = candidate if candidate.is_absolute() else workspace_root() / candidate
    resolved = path.resolve()
    try:
        resolved.relative_to(workspace_root().resolve())
    except ValueError as exc:
        raise ValidationFailure(f"file record escapes workspace: {raw}") from exc
    return resolved


def verify_record(record: dict[str, Any], expected_path: Path | None = None) -> dict[str, Any]:
    require(isinstance(record, dict), "file record must be an object")
    path = resolve_record_path(record)
    if expected_path is not None:
        require(path == expected_path.resolve(), f"file record path mismatch: {path} != {expected_path}")
    actual = file_record(path)
    require(isinstance(record.get("bytes"), int) and not isinstance(record.get("bytes"), bool), "file record bytes must be integer")
    require(int(record["bytes"]) == actual["bytes"], f"file record byte drift: {path}")
    require(isinstance(record.get("sha256"), str) and HEX64.fullmatch(record["sha256"]), f"invalid uppercase SHA-256: {path}")
    require(record["sha256"] == actual["sha256"], f"file record SHA-256 drift: {path}")
    return actual


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def walk(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, (*path, str(index)))
    else:
        yield path, value


def values_for_key(value: Any, wanted: str) -> list[Any]:
    return [scalar for path, scalar in walk(value) if path and path[-1] == wanted]


def audit_forbidden_true(value: Any, label: str) -> None:
    for path, scalar in walk(value):
        if path and path[-1] in FORBIDDEN_TRUE_KEYS and scalar is True:
            raise ValidationFailure(f"{label} illegally sets {'.'.join(path)}=true")


def validate_system_invariants(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict), "system invariants must be an object")
    for key, expected in EXPECTED_SYSTEM_INVARIANTS.items():
        require(value.get(key) == expected, f"system invariant drift: {key}={value.get(key)!r}, expected {expected!r}")
    return dict(EXPECTED_SYSTEM_INVARIANTS)


def count_subshapes(shape: TopoDS_Shape, shape_type: Any) -> int:
    explorer = TopExp_Explorer(shape, shape_type)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def bbox(shape: TopoDS_Shape) -> list[float]:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    require(not box.IsVoid(), "OpenCascade returned a void bounding box")
    result = [float(value) for value in box.Get()]
    require(len(result) == 6 and all(math.isfinite(value) for value in result), "non-finite OpenCascade bounds")
    return result


def solid_fingerprint(solid: TopoDS_Solid) -> dict[str, Any]:
    volume_props = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, volume_props)
    surface_props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(solid, surface_props)
    volume = float(volume_props.Mass())
    area = float(surface_props.Mass())
    center = [float(value) for value in volume_props.CentreOfMass().Coord()]
    require(math.isfinite(volume) and volume > 0.0, "solid volume is not finite and positive")
    require(math.isfinite(area) and area > 0.0, "solid surface area is not finite and positive")
    require(all(math.isfinite(value) for value in center), "solid center of volume is non-finite")

    shell_closed = True
    shells = TopExp_Explorer(solid, TopAbs_SHELL)
    while shells.More():
        shell_closed = shell_closed and bool(TopoDS.Shell_s(shells.Current()).Closed())
        shells.Next()

    edge_faces = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(solid, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    boundary_edges = 0
    closed_seam_edges = 0
    nonmanifold_edges = 0
    for index in range(1, edge_faces.Extent() + 1):
        degree = int(edge_faces.FindFromIndex(index).Extent())
        if degree == 1:
            edge = TopoDS.Edge_s(edge_faces.FindKey(index))
            if BRep_Tool.IsClosed_s(edge):
                closed_seam_edges += 1
            else:
                boundary_edges += 1
        elif degree != 2:
            nonmanifold_edges += 1

    valid = bool(BRepCheck_Analyzer(solid, True).IsValid())
    closed = shell_closed and boundary_edges == 0 and nonmanifold_edges == 0
    require(valid, "solid failed BRepCheck_Analyzer")
    require(closed, "solid is not closed and two-manifold")
    return {
        "valid": True,
        "closed": True,
        "positive_volume": True,
        "bbox_mm": bbox(solid),
        "center_of_volume_mm": center,
        "volume_mm3": volume,
        "surface_area_mm2": area,
        "face_count": count_subshapes(solid, TopAbs_FACE),
        "shell_count": count_subshapes(solid, TopAbs_SHELL),
        "boundary_edge_count": boundary_edges,
        "closed_seam_edge_count": closed_seam_edges,
        "nonmanifold_edge_count": nonmanifold_edges,
        "forward_orientation": int(solid.Orientation()) == int(TopAbs_FORWARD),
    }


def reopen_single_solid_step(path: Path, label: str) -> tuple[TopoDS_Shape, TopoDS_Solid, dict[str, Any]]:
    require(path.is_file(), f"{label} STEP missing: {path}")
    reader = STEPControl_Reader()
    try:
        status = reader.ReadFile(str(path))
        roots = int(reader.NbRootsForTransfer())
        transferred = int(reader.TransferRoots())
        shape = reader.OneShape()
    except Exception as exc:
        raise ValidationFailure(f"OpenCascade STEP reopen failed for {label}: {exc}") from exc
    require(status == IFSelect_RetDone, f"STEP reader status not RetDone: {label}")
    require(roots == 1 and transferred == 1, f"{label} must contain exactly one transferable root")
    require(not shape.IsNull(), f"{label} STEP reopened as null shape")
    solids: list[TopoDS_Solid] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solids.append(TopoDS.Solid_s(explorer.Current()))
        explorer.Next()
    require(len(solids) == 1, f"{label} must contain exactly one solid, got {len(solids)}")
    detail = solid_fingerprint(solids[0])
    detail.update({
        "reader_status": "IFSelect_RetDone",
        "root_count": roots,
        "transferred_root_count": transferred,
        "solid_count": 1,
        "step": file_record(path),
    })
    return shape, solids[0], detail


def transform_shape(shape: TopoDS_Shape, matrix: np.ndarray) -> TopoDS_Shape:
    require(matrix.shape == (4, 4), "transform matrix must be 4x4")
    require(np.all(np.isfinite(matrix)), "transform matrix is non-finite")
    transform = gp_Trsf()
    transform.SetValues(*(float(matrix[row, column]) for row in range(3) for column in range(4)))
    result = BRepBuilderAPI_Transform(shape, transform, True).Shape()
    require(not result.IsNull(), "OpenCascade rigid transform returned null shape")
    return result


def max_abs_delta(left: Sequence[float], right: Sequence[float]) -> float:
    require(len(left) == len(right), "vector length mismatch")
    return max(abs(float(a) - float(b)) for a, b in zip(left, right, strict=True))


def relative_delta(left: float, right: float) -> float:
    scale = max(abs(float(left)), abs(float(right)), 1.0e-30)
    return abs(float(left) - float(right)) / scale


def npz_scalar(payload: dict[str, np.ndarray], key: str) -> Any:
    require(key in payload, f"NPZ missing scalar key {key}")
    array = payload[key]
    require(array.size == 1, f"NPZ key {key} is not scalar")
    return array.reshape(()).item()


def read_runtime_npz(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"runtime NPZ missing: {path}")
    try:
        with np.load(path, allow_pickle=False) as archive:
            arrays = {key: np.array(archive[key]) for key in archive.files}
    except Exception as exc:
        raise ValidationFailure(f"cannot read runtime NPZ {path}: {exc}") from exc
    require("vertices_m" in arrays and "faces" in arrays, f"runtime NPZ lacks vertices_m/faces: {path}")
    vertices = arrays["vertices_m"]
    faces = arrays["faces"]
    require(vertices.ndim == 2 and vertices.shape[1] == 3 and len(vertices) >= 4, "runtime vertices_m shape invalid")
    require(np.issubdtype(vertices.dtype, np.floating) and np.all(np.isfinite(vertices)), "runtime vertices_m invalid")
    require(faces.ndim == 2 and faces.shape[1] == 3 and len(faces) >= 4, "runtime faces shape invalid")
    require(np.issubdtype(faces.dtype, np.integer), "runtime faces must be integer")
    require(int(faces.min()) >= 0 and int(faces.max()) < len(vertices), "runtime face index out of bounds")
    require(np.all(faces[:, 0] != faces[:, 1]) and np.all(faces[:, 1] != faces[:, 2]) and np.all(faces[:, 0] != faces[:, 2]), "runtime contains degenerate face indices")
    metadata: dict[str, Any] = {}
    if "metadata_json_utf8" in arrays:
        raw = arrays["metadata_json_utf8"]
        require(raw.ndim == 1 and np.issubdtype(raw.dtype, np.unsignedinteger), "metadata_json_utf8 must be a uint byte vector")
        try:
            metadata = json.loads(bytes(raw.tolist()).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValidationFailure(f"invalid metadata_json_utf8 in {path}: {exc}") from exc
        require(isinstance(metadata, dict), "runtime metadata JSON root must be an object")
    return {
        "arrays": arrays,
        "metadata": metadata,
        "vertices_m": vertices.astype(np.float64, copy=False),
        "faces": faces,
        "bbox_m": np.concatenate((vertices.min(axis=0), vertices.max(axis=0))).astype(float).tolist(),
        "vertex_count": int(len(vertices)),
        "triangle_count": int(len(faces)),
        "file": file_record(path),
    }


def read_ply_vertices(path: Path) -> np.ndarray:
    require(path.is_file(), f"runtime PLY missing: {path}")
    data = path.read_bytes()
    end = data.find(b"end_header\n")
    ending = len(b"end_header\n")
    if end < 0:
        end = data.find(b"end_header\r\n")
        ending = len(b"end_header\r\n")
    require(end >= 0, f"PLY end_header missing: {path}")
    header = data[: end + ending].decode("ascii", errors="strict").splitlines()
    formats = [line.split()[1] for line in header if line.startswith("format ")]
    require(len(formats) == 1, f"PLY format declaration invalid: {path}")
    counts = [int(line.split()[2]) for line in header if line.startswith("element vertex ")]
    require(len(counts) == 1 and counts[0] > 0, f"PLY vertex count invalid: {path}")
    vertex_count = counts[0]
    body = data[end + ending :]
    if formats[0] == "ascii":
        rows = body.decode("ascii", errors="strict").splitlines()[:vertex_count]
        vertices = np.asarray([[float(value) for value in row.split()[:3]] for row in rows], dtype=np.float64)
    else:
        require(formats[0] == "binary_little_endian", f"unsupported PLY format: {formats[0]}")
        properties: list[str] = []
        in_vertices = False
        for line in header:
            if line.startswith("element vertex "):
                in_vertices = True
                continue
            if line.startswith("element ") and in_vertices:
                break
            if in_vertices and line.startswith("property "):
                tokens = line.split()
                require(len(tokens) == 3 and tokens[1] in {"float", "float32", "double", "float64"}, "unsupported PLY vertex property")
                properties.append(tokens[1])
        require(len(properties) >= 3, "PLY must have at least x/y/z properties")
        format_map = {"float": "f", "float32": "f", "double": "d", "float64": "d"}
        row_format = "<" + "".join(format_map[value] for value in properties)
        row_size = struct.calcsize(row_format)
        require(len(body) >= vertex_count * row_size, "truncated binary PLY vertex block")
        vertices = np.asarray(
            [struct.unpack_from(row_format, body, index * row_size)[:3] for index in range(vertex_count)],
            dtype=np.float64,
        )
    require(vertices.shape == (vertex_count, 3) and np.all(np.isfinite(vertices)), "PLY vertices invalid")
    return vertices


def read_stl_vertices(path: Path) -> np.ndarray:
    require(path.is_file(), f"runtime STL missing: {path}")
    data = path.read_bytes()
    vertices: np.ndarray
    if len(data) >= 84:
        triangle_count = struct.unpack_from("<I", data, 80)[0]
        if 84 + triangle_count * 50 == len(data):
            rows: list[tuple[float, float, float]] = []
            for index in range(triangle_count):
                offset = 84 + index * 50 + 12
                rows.extend(struct.unpack_from("<9f", data, offset)[i : i + 3] for i in (0, 3, 6))
            vertices = np.asarray(rows, dtype=np.float64)
        else:
            text = data.decode("ascii", errors="strict")
            rows = [tuple(float(value) for value in line.split()[1:4]) for line in text.splitlines() if line.strip().startswith("vertex ")]
            vertices = np.asarray(rows, dtype=np.float64)
    else:
        text = data.decode("ascii", errors="strict")
        rows = [tuple(float(value) for value in line.split()[1:4]) for line in text.splitlines() if line.strip().startswith("vertex ")]
        vertices = np.asarray(rows, dtype=np.float64)
    require(vertices.ndim == 2 and vertices.shape[1] == 3 and len(vertices) >= 12, "STL vertices invalid")
    require(np.all(np.isfinite(vertices)), "STL vertices non-finite")
    return vertices


def find_system_invariants(*documents: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for document in documents:
        if isinstance(document.get("current_system_authority_invariants"), dict):
            candidates.append(document["current_system_authority_invariants"])
        for path, scalar in walk(document):
            if path and path[-1] == "current_system_authority_invariants" and isinstance(scalar, dict):
                candidates.append(scalar)
    require(candidates, "no current_system_authority_invariants found in contract controls")
    for candidate in candidates:
        validate_system_invariants(candidate)
    return dict(EXPECTED_SYSTEM_INVARIANTS)
