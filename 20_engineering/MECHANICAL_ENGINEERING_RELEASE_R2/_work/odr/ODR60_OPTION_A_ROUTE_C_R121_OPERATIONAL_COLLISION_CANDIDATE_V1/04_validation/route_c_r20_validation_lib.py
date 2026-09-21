"""Independent validation utilities for the Route-C root-static R20 package.

This module deliberately duplicates the small amount of STEP, BRep, mesh and
ledger logic needed for validation.  It must never import the candidate
builder or ``route_c_root_static_geometry`` module.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import math
import os
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepTools import BRepTools
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
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
TEST_DIR = PACKAGE / "06_tests"

CONTRACT_PATH = CONTRACT_DIR / "ROOT_STATIC_R20_OPERATIONAL_COLLISION_CONTRACT_V1.json"
SOURCE_LOCK_PATH = CONTRACT_DIR / "SOURCE_AUTHORITY_LOCK_V1.json"
FRAME_LEDGER_PATH = CONTRACT_DIR / "FRAME_AND_UNIT_LEDGER_V1.json"
BUILD_RECEIPT_PATH = RESULTS_DIR / "TWENTY_STEP_BUILD_RECEIPT_V1.json"
RUNTIME_RECEIPT_PATH = RESULTS_DIR / "RUNTIME_SIDECAR_DERIVATION_RECEIPT_V1.json"
GEOMETRY_INDEX_PATH = RESULTS_DIR / "ROOT_STATIC_R20_GEOMETRY_INDEX_V1.json"
INDEPENDENT_PATH = RESULTS_DIR / "INDEPENDENT_R20_STEP_VALIDATION_V1.json"
NEGATIVE_PATH = RESULTS_DIR / "NEGATIVE_CONTROLS_V1.json"
DETERMINISM_PATH = RESULTS_DIR / "FRESH_PROCESS_DETERMINISM_RECEIPT_V1.json"
PYTEST_PATH = RESULTS_DIR / "PYTEST_RECEIPT_V1.json"
R121_SOURCE_AUDIT_PATH = RESULTS_DIR / "V9F_R121_SOURCE_TOPOLOGY_AUDIT_V1.json"

SOURCE_INSPECTOR = PACKAGE / "04_validation/inspect_v9f_fcstd_source.py"
VALIDATION_LIB = Path(__file__).resolve()
INDEPENDENT_VALIDATOR = PACKAGE / "04_validation/validate_route_c_r20_independent.py"

EXPECTED_PIN_IDS = {
    "v9f_fcstd",
    "v9f_build_receipt",
    "v9f_centerline",
    "v9f_builder",
    "v9f_mesh_manifest",
    "v9f_mass_geometry",
    "v9f_mesh_preparer",
    "m01_registry",
    "m01_registry_gate",
    "m01_prebind_gate",
    "execution_mount",
    "accepted_b601_urdf",
    "route_c_negative_witness",
}
FORBIDDEN_IMPORT_NAMES = {
    "build_route_c_root_static_r20",
    "route_c_root_static_geometry",
    "extract_v9f_root_static_r20_brep",
}
LINEAR_DEFLECTION_MM = 0.05
ANGULAR_DEFLECTION_RAD = math.radians(5.0)
VERTEX_ROUND_DECIMALS_M = 12
RUNTIME_VOLUME_RELATIVE_TOLERANCE = 5.0e-3
RUNTIME_FLOAT32_TOLERANCE_M = 1.0e-6


class ValidationFailure(RuntimeError):
    """A fail-closed contract violation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationFailure(message)


def workspace_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise ValidationFailure("workspace root containing PROJECT_MAP.md not found")


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
    require(path.is_file(), f"artifact missing: {path}")
    return {
        "path": path.relative_to(workspace_root()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def verify_record(record: dict[str, Any], explicit_path: Path | None = None) -> Path:
    path = explicit_path or (workspace_root() / str(record.get("path", "")))
    require(path.is_file(), f"record target missing: {path}")
    require(path.stat().st_size == int(record.get("bytes", -1)), f"record byte drift: {path}")
    require(sha256_path(path) == str(record.get("sha256", "")).upper(), f"record hash drift: {path}")
    return path


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def relative_residual(actual: float, expected: float) -> float:
    return abs(float(actual) - float(expected)) / max(abs(float(expected)), 1.0e-300)


def require_relative(actual: float, expected: float, tolerance: float, label: str) -> float:
    residual = relative_residual(actual, expected)
    require(residual <= tolerance, f"{label} relative residual {residual} > {tolerance}")
    return residual


def require_bbox(actual: np.ndarray, expected: np.ndarray, tolerance_mm: float, label: str) -> float:
    require(actual.shape == expected.shape == (2, 3), f"{label} bbox shape drift")
    residual = float(np.max(np.abs(actual - expected)))
    require(math.isfinite(residual) and residual <= tolerance_mm, f"{label} bbox residual {residual} mm > {tolerance_mm}")
    return residual


def expected_output_name(object_id: str) -> str:
    require(object_id.startswith("R::"), f"invalid Route-C object id: {object_id}")
    return "R_" + object_id.removeprefix("R::").replace("-", "_") + "_S_V1.step"


def validate_contract_structure(contract: dict[str, Any]) -> list[dict[str, Any]]:
    require(contract.get("schema") == "ROUTE_C_ROOT_STATIC_R20_OPERATIONAL_COLLISION_CONTRACT_V1", "contract schema drift")
    selection = contract.get("object_selection", {})
    require(selection.get("category") == "R", "contract category is not R")
    require(set(selection.get("parent_frames", [])) == {"bus", "base_link"}, "R20 parent-frame selection drift")
    require(selection.get("motion_class") == "HOST_FIXED_UNLESS_REGISTERED_OTHERWISE", "R20 motion selection drift")
    require(selection.get("required_count") == 20, "R20 required count drift")
    require(selection.get("forbid_bundle_envelopes") is True, "bundle-envelope exclusion absent")
    require(selection.get("forbid_dynamic_hosts") is True, "dynamic-host exclusion absent")
    require(selection.get("forbid_source_triangle_reconstruction") is True, "triangle reconstruction not forbidden")
    specs = contract.get("objects")
    require(isinstance(specs, list) and len(specs) == 20, "contract objects are not 20")
    for field in ("object_id", "source_label", "output"):
        require(len({str(row.get(field)) for row in specs}) == 20, f"contract {field} is not unique")
    for spec in specs:
        object_id = str(spec.get("object_id"))
        label = str(spec.get("source_label"))
        require(object_id == f"R::{label}", f"object/label mapping drift: {object_id} / {label}")
        require(spec.get("parent_frame") in {"bus", "base_link"}, f"dynamic parent included: {object_id}")
        require(str(spec.get("output")) == expected_output_name(object_id), f"output mapping drift: {object_id}")
    require(contract.get("pair_eligible") is False, "contract grants pair eligibility")
    require(contract.get("system_registry_binding_authorized") is False, "contract grants registry binding")
    require(contract.get("path_search_authorized") is False, "contract grants path search")
    require(contract.get("release_credit") is False, "contract grants release credit")
    return specs


def validate_source_pins(lock: dict[str, Any], *, verify_files: bool = True) -> dict[str, dict[str, Any]]:
    require(lock.get("schema") == "ROUTE_C_R121_SOURCE_AUTHORITY_LOCK_V1", "source lock schema drift")
    rows = lock.get("source_pins")
    require(isinstance(rows, list) and len(rows) == 13, "source lock is not 13 pins")
    pins = {str(row.get("id")): row for row in rows}
    require(len(pins) == 13 and set(pins) == EXPECTED_PIN_IDS, "source pin ID set drift")
    if verify_files:
        for row in rows:
            verify_record(row)
    require(lock.get("triangle_arrays_are_primary_geometry") is False, "triangles promoted to primary geometry")
    require(lock.get("source_rebuild_authorized") is False, "source rebuild authorized")
    require(lock.get("source_document_write_authorized") is False, "source document write authorized")
    require(lock.get("release_credit") in {None, False}, "source lock grants release credit")
    return pins


def _route_parts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    groups = [row for row in manifest.get("files", []) if row.get("group") == "route_c_parts"]
    require(len(groups) == 1, "Route-C manifest group missing/duplicated")
    return list(groups[0].get("entries", []))


def validate_object_mapping(
    contract: dict[str, Any],
    registry: dict[str, Any],
    receipt: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    specs = validate_contract_structure(contract)
    registry_rows = {row["object_id"]: row for row in registry.get("objects", []) if row.get("category") == "R"}
    receipt_rows = {row["name"]: row for row in receipt.get("parts", []) if row.get("geometry_role") == "PHYSICAL"}
    route_rows = {row["name"]: row for row in _route_parts(manifest) if row.get("geometry_role") == "PHYSICAL"}
    require(len(registry_rows) == len(receipt_rows) == len(route_rows) == 121, "R121 source universe drift")
    selected = {
        object_id
        for object_id, row in registry_rows.items()
        if row.get("parent_frame") in {"bus", "base_link"}
        and row.get("motion_class") == "HOST_FIXED_UNLESS_REGISTERED_OTHERWISE"
    }
    require(selected == {row["object_id"] for row in specs}, "contract R20 is not the exact registry selection")
    rows = []
    for spec in specs:
        object_id = spec["object_id"]
        label = spec["source_label"]
        registry_row = registry_rows.get(object_id)
        receipt_row = receipt_rows.get(label)
        manifest_row = route_rows.get(label)
        require(registry_row is not None and receipt_row is not None and manifest_row is not None, f"mapping row missing: {object_id}")
        require(registry_row.get("representation_set") == f"ROUTE_C_PART::{label}", f"representation mapping drift: {object_id}")
        require(registry_row.get("parent_frame") == spec.get("parent_frame") == receipt_row.get("host_link") == manifest_row.get("host_link"), f"host mapping drift: {object_id}")
        require(registry_row.get("kind") == spec.get("kind") == receipt_row.get("kind") == manifest_row.get("kind"), f"kind mapping drift: {object_id}")
        require(receipt_row.get("geometry_role") == "PHYSICAL" and receipt_row.get("mass_counted") is True, f"nonphysical receipt row: {object_id}")
        require(manifest_row.get("geometry_role") == "PHYSICAL" and manifest_row.get("mass_counted") is True, f"nonphysical manifest row: {object_id}")
        candidate = registry_row.get("geometry", {}).get("narrowphase_candidate", {})
        require(Path(str(candidate.get("path"))).name == str(manifest_row.get("file")), f"triangle path mapping drift: {object_id}")
        require(str(candidate.get("sha256", "")).upper() == str(manifest_row.get("sha256", "")).upper(), f"triangle hash mapping drift: {object_id}")
        require(int(candidate.get("triangles", -1)) == int(manifest_row.get("tris", -2)), f"triangle count mapping drift: {object_id}")
        require(candidate.get("units") == "mm", f"source triangle unit drift: {object_id}")
        rows.append({"object_id": object_id, "source_label": label, "registry": registry_row, "receipt": receipt_row, "manifest": manifest_row})
    require(not any(str(row["source_label"]).startswith("RC-BUNDLE-") for row in rows), "bundle envelope included")
    return rows


def validate_frame_and_mount(ledger: dict[str, Any], mount: dict[str, Any]) -> np.ndarray:
    require(ledger.get("schema") == "ROUTE_C_R121_FRAME_AND_UNIT_LEDGER_V1", "frame ledger schema drift")
    storage = ledger.get("source_storage", {})
    require(storage.get("frame") == "A0_Q0_REFERENCE" and storage.get("length_unit") == "mm", "source frame/unit drift")
    require(storage.get("is_S") is False and storage.get("is_host_local") is False and storage.get("is_segment_local") is False, "source frame relabelled")
    phase = ledger.get("phase_A_root_static_R20", {})
    require(phase.get("required_count") == 20, "frame ledger object count drift")
    require(phase.get("target_frame") == "spacecraft_bus_S", "target frame drift")
    require(phase.get("target_step_length_unit") == "mm", "target STEP unit drift")
    require(phase.get("runtime_sidecar_length_unit") == "m", "runtime unit drift")
    require(phase.get("source_to_target_transform_name") == "T_S_A0", "transform name drift")
    require(phase.get("transform_application_count_per_object") == 1, "T_S_A0 application count drift")
    require(float(phase.get("step_to_runtime_scale")) == 0.001, "mm-to-m scale drift")
    require(phase.get("step_to_runtime_scale_application_count") == 1, "mm-to-m application count drift")
    strings = phase.get("canonical_matrix_decimal_strings_mm")
    require(isinstance(strings, list) and len(strings) == 4 and all(len(row) == 4 for row in strings), "ledger matrix shape drift")
    matrix = np.asarray([[float(value) for value in row] for row in strings], dtype=np.float64)
    rotation = matrix[:3, :3]
    tolerances = strict_json(CONTRACT_PATH).get("tolerances", {}) if CONTRACT_PATH.is_file() else {}
    ortho_tol = float(tolerances.get("rotation_orthonormal_max_abs", 1.0e-11))
    det_tol = float(tolerances.get("rotation_determinant_abs", 1.0e-11))
    require(float(np.max(np.abs(rotation.T @ rotation - np.eye(3)))) <= ortho_tol, "T_S_A0 is not orthonormal")
    require(abs(float(np.linalg.det(rotation)) - 1.0) <= det_tol, "T_S_A0 determinant drift")
    require(float(np.max(np.abs(matrix[3] - [0.0, 0.0, 0.0, 1.0]))) <= 1.0e-14, "homogeneous row drift")

    binding = mount.get("binding", {})
    require(mount.get("schema") == "ODR60_OPTION_A_EXECUTION_MOUNT_BINDING_V1", "execution mount schema drift")
    require(binding.get("parent_frame") == "spacecraft_bus_S" and binding.get("child_frame") == "base_link", "execution mount frame drift")
    require(binding.get("translation_unit") == "m", "execution mount unit drift")
    mount_strings = binding.get("canonical_matrix_decimal_strings")
    require(isinstance(mount_strings, list) and len(mount_strings) == 4, "execution mount matrix missing")
    mount_mm = np.asarray([[float(value) for value in row] for row in mount_strings], dtype=np.float64)
    mount_mm[:3, 3] *= 1000.0
    require(float(np.max(np.abs(matrix - mount_mm))) <= 1.0e-12, "frame ledger does not match current execution mount")
    uncertainty = ledger.get("uncertainty_and_derating", {})
    require(uncertainty.get("manufacturing_as_built_derate_mm") is None, "as-built derate zero-filled")
    require(uncertainty.get("zero_fill_for_missing_as_built_forbidden") is True, "as-built zero-fill guard absent")
    require(ledger.get("remaining_R101", {}).get("status") == "HOLD_FOR_HOST_MOTION_ADAPTER", "R101 adapter HOLD drift")
    return matrix


def locate_freecad_python() -> Path:
    candidates: list[Path] = []
    override = os.environ.get("ROUTE_C_FREECAD_PYTHON")
    if override:
        candidates.append(Path(override))
    candidates.extend(
        [
            Path(r"G:\Windows_program_file\FreeCAD\bin\python.exe"),
            Path(r"C:\Program Files\FreeCAD 1.1\bin\python.exe"),
            Path(r"C:\Program Files\FreeCAD 1.0\bin\python.exe"),
        ]
    )
    for path in candidates:
        if path.is_file():
            return path.resolve()
    raise ValidationFailure("FreeCAD-bundled python not found; set ROUTE_C_FREECAD_PYTHON")


def run_independent_source_extractor(output_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    freecad = locate_freecad_python()
    completed = subprocess.run(
        [str(freecad), str(SOURCE_INSPECTOR), "--output-dir", str(output_dir)],
        cwd=str(workspace_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    require(completed.returncode == 0, f"independent FreeCAD extraction failed:\n{completed.stdout}\n{completed.stderr}")
    require(not completed.stderr.strip(), f"independent FreeCAD extraction wrote stderr: {completed.stderr}")
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationFailure(f"independent FreeCAD extraction emitted invalid JSON: {exc}") from exc
    require(document.get("verdict") == "R20_INDEPENDENT_SOURCE_EXTRACTION_PASS__A0_Q0_BREP_ONLY_NO_TRANSFORM", "source extractor HOLD")
    return document, {"path": str(freecad), "bytes": freecad.stat().st_size, "sha256": sha256_path(freecad)}


def read_brep(path: Path):
    shape = TopoDS_Shape()
    builder = BRep_Builder()
    require(bool(BRepTools.Read_s(shape, str(path), builder)), f"BREP read failed: {path}")
    require(not shape.IsNull(), f"BREP read returned null: {path}")
    return shape


def read_step(path: Path) -> tuple[Any, dict[str, int]]:
    reader = STEPControl_Reader()
    require(reader.ReadFile(str(path)) == IFSelect_RetDone, f"STEP read failed: {path}")
    roots_available = int(reader.NbRootsForTransfer())
    roots_transferred = int(reader.TransferRoots())
    require(roots_available == 1 and roots_transferred == 1, f"STEP root count drift: {path} ({roots_available}/{roots_transferred})")
    shape = reader.OneShape()
    require(not shape.IsNull(), f"STEP transferred null shape: {path}")
    return shape, {"roots_available": roots_available, "roots_transferred": roots_transferred}


def _count(shape, kind) -> int:
    count = 0
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def bbox_mm(shape) -> np.ndarray:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    return np.asarray(box.Get(), dtype=np.float64).reshape(2, 3)


def volume_mm3(shape) -> float:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties, False, False, True)
    return float(properties.Mass())


def area_mm2(shape) -> float:
    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, properties, False, False)
    return float(properties.Mass())


def centroid_mm(shape) -> np.ndarray:
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties, False, False, True)
    center = properties.CentreOfMass()
    return np.asarray([center.X(), center.Y(), center.Z()], dtype=np.float64)


def _solid_list(shape) -> list[Any]:
    result = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        result.append(TopoDS.Solid_s(explorer.Current()))
        explorer.Next()
    return result


def shape_facts(shape, *, context: str, expected_solid_count: int = 1) -> dict[str, Any]:
    require(shape is not None and not shape.IsNull(), f"{context}: null BRep")
    solids = _solid_list(shape)
    require(len(solids) == expected_solid_count, f"{context}: solid count {len(solids)} != {expected_solid_count}")
    require(bool(BRepCheck_Analyzer(shape, True).IsValid()), f"{context}: invalid top-level BRep")
    solid_rows = []
    for index, solid in enumerate(solids):
        require(bool(BRepCheck_Analyzer(solid, True).IsValid()), f"{context}: invalid solid {index}")
        shell_count = 0
        all_closed = True
        explorer = TopExp_Explorer(solid, TopAbs_SHELL)
        while explorer.More():
            shell_count += 1
            all_closed &= bool(BRep_Tool.IsClosed_s(explorer.Current()))
            explorer.Next()
        require(shell_count > 0 and all_closed, f"{context}: open/missing shell {index}")
        solid_volume = volume_mm3(solid)
        require(math.isfinite(solid_volume) and solid_volume > 0.0, f"{context}: non-positive/nonfinite volume {index}")
        solid_rows.append({"index": index, "shell_count": shell_count, "volume_mm3": solid_volume})
    total_volume = volume_mm3(shape)
    surface_area = area_mm2(shape)
    require(math.isfinite(total_volume) and total_volume > 0.0, f"{context}: invalid aggregate volume")
    require(math.isfinite(surface_area) and surface_area > 0.0, f"{context}: invalid surface area")
    face_count = _count(shape, TopAbs_FACE)
    solid_face_count = sum(_count(solid, TopAbs_FACE) for solid in solids)
    require(face_count == solid_face_count, f"{context}: stray face outside solid")
    return {
        "solid_count": len(solids),
        "shell_count": _count(shape, TopAbs_SHELL),
        "face_count": face_count,
        "edge_count": sum(1 for _ in _iterate(shape, "edge")),
        "vertex_count": sum(1 for _ in _iterate(shape, "vertex")),
        "brep_valid": True,
        "all_shells_closed": True,
        "volume_mm3": total_volume,
        "surface_area_mm2": surface_area,
        "centroid_mm": centroid_mm(shape).tolist(),
        "bbox_mm": bbox_mm(shape).tolist(),
        "solid_rows": solid_rows,
    }


def _iterate(shape, category: str):
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX

    kind = TopAbs_EDGE if category == "edge" else TopAbs_VERTEX
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        yield explorer.Current()
        explorer.Next()


def transform_shape_once(shape, matrix: np.ndarray):
    require(matrix.shape == (4, 4), "transform matrix must be 4x4")
    transform = gp_Trsf()
    transform.SetValues(*(float(matrix[row, column]) for row in range(3) for column in range(4)))
    operation = BRepBuilderAPI_Transform(shape, transform, True)
    operation.Build()
    require(operation.IsDone(), "independent OCP transform failed")
    result = operation.Shape()
    require(not result.IsNull(), "independent OCP transform returned null")
    return result


def _cut_volume(left, right) -> tuple[bool, float, str | None]:
    try:
        operation = BRepAlgoAPI_Cut(left, right)
        if hasattr(operation, "SetFuzzyValue"):
            operation.SetFuzzyValue(1.0e-7)
        operation.Build()
        if not operation.IsDone():
            return False, math.nan, "BRepAlgoAPI_Cut.IsDone=false"
        shape = operation.Shape()
        if shape.IsNull():
            return True, 0.0, None
        value = abs(volume_mm3(shape))
        if not math.isfinite(value):
            return False, math.nan, "nonfinite cut volume"
        return True, value, None
    except Exception as exc:  # OCP raises several wrapped Standard_Failure types.
        return False, math.nan, f"{type(exc).__name__}: {exc}"


def compare_expected_to_step(expected, target, contract: dict[str, Any], *, context: str) -> dict[str, Any]:
    tolerances = contract["tolerances"]
    expected_facts = shape_facts(expected, context=f"{context} expected")
    target_facts = shape_facts(target, context=f"{context} STEP")
    require(
        [target_facts[key] for key in ("solid_count", "shell_count", "face_count", "edge_count", "vertex_count")]
        == [expected_facts[key] for key in ("solid_count", "shell_count", "face_count", "edge_count", "vertex_count")],
        f"{context}: topology count drift",
    )
    volume_relative = require_relative(
        target_facts["volume_mm3"],
        expected_facts["volume_mm3"],
        float(tolerances["step_reopen_volume_relative"]),
        f"{context} STEP volume",
    )
    area_relative = require_relative(
        target_facts["surface_area_mm2"],
        expected_facts["surface_area_mm2"],
        1.0e-9,
        f"{context} STEP area",
    )
    bbox_error = require_bbox(
        np.asarray(target_facts["bbox_mm"]),
        np.asarray(expected_facts["bbox_mm"]),
        float(tolerances["step_reopen_bbox_mm"]),
        f"{context} STEP",
    )
    centroid_error = float(np.max(np.abs(np.asarray(target_facts["centroid_mm"]) - np.asarray(expected_facts["centroid_mm"]))))
    require(centroid_error <= 1.0e-6, f"{context}: centroid drift {centroid_error} mm")
    left_done, left_volume, left_error = _cut_volume(expected, target)
    right_done, right_volume, right_error = _cut_volume(target, expected)
    boolean_available = left_done and right_done
    symmetric_relative = None
    if boolean_available:
        symmetric_relative = (left_volume + right_volume) / max(expected_facts["volume_mm3"], 1.0e-300)
        require(
            symmetric_relative <= float(tolerances["independent_brep_symmetric_difference_relative"]),
            f"{context}: Boolean symmetric difference {symmetric_relative}",
        )
    return {
        "expected": expected_facts,
        "target_step": target_facts,
        "topology_counts_exact": True,
        "volume_relative_residual": volume_relative,
        "surface_area_relative_residual": area_relative,
        "bbox_max_abs_mm": bbox_error,
        "centroid_max_abs_mm": centroid_error,
        "boolean_symmetric_difference": {
            "attempted": True,
            "available": boolean_available,
            "expected_minus_step_volume_mm3": left_volume if left_done else None,
            "step_minus_expected_volume_mm3": right_volume if right_done else None,
            "relative": symmetric_relative,
            "tolerance": float(tolerances["independent_brep_symmetric_difference_relative"]),
            "disclosed_failure": None if boolean_available else {"expected_minus_step": left_error, "step_minus_expected": right_error},
            "pass_if_available": bool(not boolean_available or symmetric_relative <= float(tolerances["independent_brep_symmetric_difference_relative"])),
        },
    }


def _transform_node(point, location: TopLoc_Location) -> tuple[float, float, float]:
    transformed = point.Transformed(location.Transformation())
    return transformed.X(), transformed.Y(), transformed.Z()


def canonical_mesh_from_step(shape) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    rows = _solid_list(shape)
    require(len(rows) == 1, "runtime derivation expects one solid")
    triangles = []
    solid_ids = []
    for solid_id, solid in enumerate(rows):
        mesher = BRepMesh_IncrementalMesh(solid, LINEAR_DEFLECTION_MM, False, ANGULAR_DEFLECTION_RAD, False)
        mesher.Perform()
        require(mesher.IsDone(), "independent runtime tessellation failed")
        explorer = TopExp_Explorer(solid, TopAbs_FACE)
        while explorer.More():
            face = TopoDS.Face_s(explorer.Current())
            location = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation_s(face, location)
            require(triangulation is not None and triangulation.NbTriangles() > 0, "STEP face lacks triangulation")
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
    require(bool(triangles), "independent runtime tessellation empty")
    flat = np.round(np.asarray(triangles).reshape(-1, 3), decimals=VERTEX_ROUND_DECIMALS_M).astype("<f8")
    vertices, inverse = np.unique(flat, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3).astype(np.int64)
    ids = np.asarray(solid_ids, dtype=np.uint16)
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
        ids = ids[~degenerate]
    volume = signed_mesh_volume_m3(vertices, faces)
    require(math.isfinite(volume) and abs(volume) > 1.0e-18, "independent runtime mesh has zero/nonfinite volume")
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
    order = np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0], ids))
    vertices = vertices.astype("<f8")
    faces = faces[order].astype("<u4")
    ids = ids[order].astype("<u2")
    return vertices, faces, ids, {"removed_zero_area_triangle_count": removed, "outward_winding_flipped": flipped}


def signed_mesh_volume_m3(vertices: np.ndarray, faces: np.ndarray) -> float:
    triangles = vertices[faces]
    return float(np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6.0)


def manifold_metrics(faces: np.ndarray) -> dict[str, int | bool]:
    local = np.asarray(faces, dtype=np.int64)
    require(local.ndim == 2 and local.shape[1] == 3 and len(local) > 0, "runtime faces shape invalid")
    directed = np.concatenate((local[:, [0, 1]], local[:, [1, 2]], local[:, [2, 0]]), axis=0)
    undirected = np.sort(directed, axis=1)
    unique_edges, inverse, counts = np.unique(undirected, axis=0, return_inverse=True, return_counts=True)
    boundary = int(np.count_nonzero(counts == 1))
    nonmanifold = int(np.count_nonzero(counts > 2))
    forward = np.bincount(inverse, weights=(directed[:, 0] < directed[:, 1]).astype(np.int8), minlength=len(unique_edges))
    orientation = int(np.count_nonzero(forward != counts - forward))
    require(boundary == nonmanifold == orientation == 0, "runtime mesh is not a closed oriented two-manifold")
    return {
        "boundary_edge_count": boundary,
        "nonmanifold_edge_count": nonmanifold,
        "orientation_mismatch_edge_count": orientation,
        "closed_oriented_two_manifold": True,
    }


def read_npz_runtime(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as archive:
        require(set(archive.files) == {"faces", "metadata_utf8", "solid_ids", "vertices_m"}, f"NPZ member set drift: {path}")
        vertices = np.asarray(archive["vertices_m"])
        faces = np.asarray(archive["faces"])
        solid_ids = np.asarray(archive["solid_ids"])
        metadata_raw = np.asarray(archive["metadata_utf8"])
    require(vertices.dtype == np.dtype("<f8") and vertices.ndim == 2 and vertices.shape[1] == 3, "NPZ vertices dtype/shape drift")
    require(faces.dtype == np.dtype("<u4") and faces.ndim == 2 and faces.shape[1] == 3, "NPZ faces dtype/shape drift")
    require(solid_ids.dtype == np.dtype("<u2") and solid_ids.shape == (len(faces),), "NPZ solid_ids drift")
    require(metadata_raw.dtype == np.dtype("uint8"), "NPZ metadata encoding drift")
    require(bool(np.isfinite(vertices).all()), "NPZ contains nonfinite vertex")
    require(len(vertices) > 0 and len(faces) > 0 and int(faces.max()) < len(vertices), "NPZ indices invalid")
    try:
        metadata = json.loads(bytes(metadata_raw.tolist()).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"NPZ metadata invalid: {path}: {exc}") from exc
    return {"vertices": vertices, "faces": faces, "solid_ids": solid_ids, "metadata": metadata}


def read_binary_ply(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    marker = b"end_header\n"
    offset = data.find(marker)
    require(offset >= 0, f"PLY header terminator missing: {path}")
    header_end = offset + len(marker)
    try:
        header = data[:header_end].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValidationFailure(f"PLY header is not ASCII: {path}") from exc
    require("format binary_little_endian 1.0\n" in header, "PLY format drift")
    vertex_match = re.search(r"^element vertex (\d+)$", header, re.MULTILINE)
    face_match = re.search(r"^element face (\d+)$", header, re.MULTILINE)
    require(vertex_match is not None and face_match is not None, "PLY counts missing")
    vertex_count = int(vertex_match.group(1))
    face_count = int(face_match.group(1))
    vertex_bytes = vertex_count * 3 * 8
    require(len(data) >= header_end + vertex_bytes, "PLY vertex payload truncated")
    vertices = np.frombuffer(data, dtype="<f8", count=vertex_count * 3, offset=header_end).reshape(vertex_count, 3).copy()
    cursor = header_end + vertex_bytes
    faces = np.empty((face_count, 3), dtype=np.uint32)
    for index in range(face_count):
        require(cursor + 13 <= len(data), "PLY face payload truncated")
        count, a, b, c = struct.unpack_from("<BIII", data, cursor)
        require(count == 3, "PLY contains non-triangle face")
        faces[index] = (a, b, c)
        cursor += 13
    require(cursor == len(data), "PLY has trailing/short payload")
    return {"header": header, "vertices": vertices, "faces": faces}


def read_binary_stl(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    require(len(data) >= 84, "binary STL too short")
    count = struct.unpack_from("<I", data, 80)[0]
    require(len(data) == 84 + count * 50, "binary STL length/count mismatch")
    triangles = np.empty((count, 3, 3), dtype=np.float32)
    normals = np.empty((count, 3), dtype=np.float32)
    for index in range(count):
        values = struct.unpack_from("<12fH", data, 84 + index * 50)
        normals[index] = values[:3]
        triangles[index] = np.asarray(values[3:12], dtype=np.float32).reshape(3, 3)
        require(values[12] == 0, "STL attribute byte count drift")
    require(bool(np.isfinite(triangles).all()) and bool(np.isfinite(normals).all()), "STL contains nonfinite values")
    areas = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1)
    require(bool(np.all(areas > 0.0)), "STL contains degenerate triangle")
    return {"header": data[:80].rstrip(b"\0").decode("ascii"), "triangles": triangles, "normals": normals}


def validate_runtime_metadata(metadata: dict[str, Any], *, object_id: str, step_record: dict[str, Any]) -> None:
    require(metadata.get("schema") == "ROUTE_C_ROOT_STATIC_RUNTIME_MESH_V1", "runtime metadata schema drift")
    require(metadata.get("object_id") == object_id, "runtime metadata object ID drift")
    require(metadata.get("frame") == "S" and metadata.get("length_unit") == "m", "runtime frame/unit drift")
    require(float(metadata.get("linear_deflection_mm")) == LINEAR_DEFLECTION_MM, "runtime deflection drift")
    require(metadata.get("primary_step_is_geometry_authority") is True, "primary STEP authority missing")
    require(metadata.get("runtime_is_geometry_authority") is False, "runtime promoted to primary authority")
    require(metadata.get("as_built_derate_mm") is None, "runtime as-built derate zero-filled")
    require(str(metadata.get("primary_step_sha256", "")).upper() == str(step_record["sha256"]).upper(), "runtime primary STEP hash drift")
    require(str(metadata.get("primary_step")) == str(step_record["path"]), "runtime primary STEP path drift")


def validate_runtime_arrays(vertices: np.ndarray, faces: np.ndarray, solid_ids: np.ndarray) -> dict[str, Any]:
    require(vertices.ndim == 2 and vertices.shape[1] == 3 and len(vertices) > 0, "runtime vertex shape drift")
    require(faces.ndim == 2 and faces.shape[1] == 3 and len(faces) > 0, "runtime face shape drift")
    require(solid_ids.shape == (len(faces),), "runtime solid_ids shape drift")
    require(bool(np.isfinite(vertices).all()), "runtime vertex nonfinite")
    require(int(faces.min()) >= 0 and int(faces.max()) < len(vertices), "runtime face index out of bounds")
    cross = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    require(bool(np.all(np.linalg.norm(cross, axis=1) > 0.0)), "runtime degenerate face")
    manifold = manifold_metrics(faces)
    volume = signed_mesh_volume_m3(vertices, faces)
    require(math.isfinite(volume) and volume > 0.0, "runtime mesh volume is not positive/outward")
    return {"manifold": manifold, "signed_volume_m3": volume}


def validate_runtime_object(
    *,
    object_id: str,
    step_path: Path,
    step_shape,
    npz_path: Path,
    ply_path: Path,
    stl_path: Path,
    runtime_receipt_row: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    step_record = file_record(step_path)
    npz_record = file_record(npz_path)
    ply_record = file_record(ply_path)
    stl_record = file_record(stl_path)
    for key, record in (("npz", npz_record), ("ply", ply_record), ("stl", stl_record)):
        expected = runtime_receipt_row.get("artifacts", {}).get(key, {})
        require(record["path"] == expected.get("path") and record["bytes"] == expected.get("bytes") and record["sha256"] == expected.get("sha256"), f"runtime receipt {key} record drift: {object_id}")
    require(str(runtime_receipt_row.get("derived_from_primary_step_sha256", "")).upper() == step_record["sha256"], f"runtime receipt source hash drift: {object_id}")
    require(runtime_receipt_row.get("frame") == "S" and runtime_receipt_row.get("unit") == "m", f"runtime receipt frame/unit drift: {object_id}")

    npz = read_npz_runtime(npz_path)
    validate_runtime_metadata(npz["metadata"], object_id=object_id, step_record=step_record)
    array_metrics = validate_runtime_arrays(npz["vertices"], npz["faces"], npz["solid_ids"])
    expected_vertices, expected_faces, expected_ids, cleanup = canonical_mesh_from_step(step_shape)
    require(np.array_equal(npz["vertices"], expected_vertices), f"NPZ vertices not independently derived from STEP: {object_id}")
    require(np.array_equal(npz["faces"], expected_faces), f"NPZ faces not independently derived from STEP: {object_id}")
    require(np.array_equal(npz["solid_ids"], expected_ids), f"NPZ solid IDs not independently derived from STEP: {object_id}")

    ply = read_binary_ply(ply_path)
    require(f"comment object_id={object_id}\n" in ply["header"], f"PLY object ID comment drift: {object_id}")
    require("comment units=m\n" in ply["header"] and "comment frame=S\n" in ply["header"], f"PLY frame/unit comment drift: {object_id}")
    require(np.array_equal(ply["vertices"], npz["vertices"]), f"PLY/NPZ vertex mismatch: {object_id}")
    require(np.array_equal(ply["faces"], npz["faces"]), f"PLY/NPZ face mismatch: {object_id}")

    stl = read_binary_stl(stl_path)
    require(f"OBJECT={object_id}" in stl["header"] and "UNITS=M" in stl["header"] and "FRAME=S" in stl["header"], f"STL header drift: {object_id}")
    expected_triangles = npz["vertices"][npz["faces"]]
    require(stl["triangles"].shape == expected_triangles.shape, f"STL triangle count drift: {object_id}")
    stl_coordinate_error = float(np.max(np.abs(stl["triangles"].astype(np.float64) - expected_triangles)))
    require(stl_coordinate_error <= RUNTIME_FLOAT32_TOLERANCE_M, f"STL/NPZ coordinate mismatch: {object_id}")

    step_bbox = bbox_mm(step_shape)
    runtime_bbox = np.asarray([npz["vertices"].min(axis=0), npz["vertices"].max(axis=0)]) * 1000.0
    bbox_error = require_bbox(runtime_bbox, step_bbox, float(contract["tolerances"]["runtime_mesh_step_bbox_mm"]), f"runtime/STEP {object_id}")
    step_volume_m3 = volume_mm3(step_shape) * 1.0e-9
    mesh_volume_relative = require_relative(array_metrics["signed_volume_m3"], step_volume_m3, RUNTIME_VOLUME_RELATIVE_TOLERANCE, f"runtime/STEP mesh volume {object_id}")
    return {
        "object_id": object_id,
        "artifacts": {"npz": npz_record, "ply": ply_record, "stl": stl_record},
        "vertices": int(len(npz["vertices"])),
        "triangles": int(len(npz["faces"])),
        "independent_step_tessellation_exact": True,
        "ply_npz_exact": True,
        "stl_npz_max_abs_m": stl_coordinate_error,
        "runtime_step_bbox_max_abs_mm": bbox_error,
        "runtime_step_volume_relative": mesh_volume_relative,
        "manifold": array_metrics["manifold"],
        "cleanup_reproduced": cleanup,
        "frame": "S",
        "unit": "m",
        "step_to_runtime_scale": 0.001,
        "scale_application_count": 1,
        "as_built_derate_mm": None,
    }


def audit_independent_imports(paths: Sequence[Path]) -> dict[str, Any]:
    imports: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
    forbidden = sorted(
        name
        for name in imports
        if any(name == forbidden or name.startswith(forbidden + ".") for forbidden in FORBIDDEN_IMPORT_NAMES)
    )
    require(not forbidden, f"independent validator imports candidate code: {forbidden}")
    loaded = sorted(name for name in sys.modules if any(name == forbidden or name.startswith(forbidden + ".") for forbidden in FORBIDDEN_IMPORT_NAMES))
    require(not loaded, f"candidate modules loaded in validator process: {loaded}")
    return {"files_audited": [path.relative_to(PACKAGE).as_posix() for path in paths], "imports_seen": sorted(set(imports)), "forbidden_imports": forbidden, "forbidden_modules_loaded": loaded, "pass": True}


def system_state_from_authorities(pins: dict[str, dict[str, Any]]) -> dict[str, Any]:
    root = workspace_root()
    registry_gate = strict_json(root / pins["m01_registry_gate"]["path"])
    prebind = strict_json(root / pins["m01_prebind_gate"]["path"])
    witness = strict_json(root / pins["route_c_negative_witness"]["path"])
    release_gate = strict_json(root / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json")
    g12_path = root / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/15_UNIFIED_R2_SYSTEM_INTERFACE.yaml"
    require(g12_path.is_file(), "G12 interface authority missing")
    require("HANDOFF_V2_FAILS_ON_G12_HARNESS" in g12_path.read_text(encoding="utf-8"), "G12 FAIL spelling absent")
    tmg4_rows = [row for row in release_gate.get("tmg", []) if row.get("id") == "TMG-4"]
    require(len(tmg4_rows) == 1, "TMG-4 row missing/duplicated")
    state = {
        "known_active_objects": registry_gate.get("known_active_object_count"),
        "system_operational_authority_rows": prebind.get("asset_accounting", {}).get("operational_authority_rows"),
        "required_unassessed_pairs": registry_gate.get("pair_coverage", {}).get("status_counts", {}).get("UNASSESSED_FAIL_CLOSED"),
        "system_pair_queries": prebind.get("system_execution_state", {}).get("system_pair_queries_executed"),
        "safe_certificates": 0,
        "system_edges_certified": prebind.get("system_execution_state", {}).get("system_edges_certified"),
        "stage_instances_bound": prebind.get("scene_accounting", {}).get("stage_instances_bound"),
        "stage_instances_required": prebind.get("scene_accounting", {}).get("stage_instances_required"),
        "path_search_executed": prebind.get("system_execution_state", {}).get("path_search_executed"),
        "TMG4": tmg4_rows[0].get("state"),
        "G12": "FAIL",
        "gate_a_pass": release_gate.get("gate_a_pass"),
        "next_stage_authorized": prebind.get("next_stage_authorized"),
        "release_credit": prebind.get("release_credit"),
        "negative_witness_raw_mm": witness.get("legacy_witness", {}).get("signed_raw_clearance_mm"),
        "negative_witness_gated_mm": witness.get("legacy_witness", {}).get("legacy_gated_clearance_mm"),
        "negative_witness_current_pair_credit": witness.get("scope_controls", {}).get("counts_as_pair_query_executed"),
    }
    validate_system_state(state)
    validate_negative_witness(witness)
    return state


def validate_system_state(state: dict[str, Any]) -> None:
    expected = {
        "known_active_objects": 150,
        "system_operational_authority_rows": 1,
        "required_unassessed_pairs": 11166,
        "system_pair_queries": 0,
        "safe_certificates": 0,
        "system_edges_certified": 0,
        "stage_instances_bound": 0,
        "stage_instances_required": 3,
        "path_search_executed": False,
        "TMG4": "HOLD",
        "G12": "FAIL",
        "gate_a_pass": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "negative_witness_current_pair_credit": False,
    }
    for key, value in expected.items():
        require(state.get(key) == value, f"system invariant drift: {key}={state.get(key)!r}, expected {value!r}")
    require(float(state.get("negative_witness_raw_mm")) == -10.729480331980062, "negative raw witness drift")
    require(float(state.get("negative_witness_gated_mm")) == -17.313396996697108, "negative gated witness drift")


def validate_negative_witness(witness: dict[str, Any]) -> None:
    require(witness.get("schema") == "ROUTE_C_NEGATIVE_WITNESS_QUARANTINE_V1", "negative witness schema drift")
    require(witness.get("authority") == "HISTORICAL_NEGATIVE_CONTROL_ONLY__NOT_A_CURRENT_SYSTEM_PAIR_RESULT", "negative witness authority drift")
    legacy = witness.get("legacy_witness", {})
    require(legacy.get("raw_physical_penetration") is True, "negative physical penetration suppressed")
    require(float(legacy.get("signed_raw_clearance_mm")) == -10.729480331980062, "negative raw clearance drift")
    require(float(legacy.get("legacy_derate_mm")) == 6.583916664717045, "negative derate drift")
    require(float(legacy.get("legacy_gated_clearance_mm")) == -17.313396996697108, "negative gated clearance drift")
    controls = witness.get("scope_controls", {})
    for key in ("counts_as_edge_certificate", "counts_as_pair_query_executed", "counts_as_path_search", "imported_as_current_system_pair_result"):
        require(controls.get(key) is False, f"negative witness overclaim: {key}")
    for key in ("edge_evaluation_authorized", "pair_evaluation_authorized", "path_search_authorized", "next_stage_authorized", "release_credit"):
        require(witness.get(key) is False, f"negative witness grants authority: {key}")


def validate_build_receipts(contract: dict[str, Any]) -> dict[str, Any]:
    build = strict_json(BUILD_RECEIPT_PATH)
    geometry = strict_json(GEOMETRY_INDEX_PATH)
    runtime = strict_json(RUNTIME_RECEIPT_PATH)
    require(build.get("schema") == "ROUTE_C_ROOT_STATIC_R20_TWENTY_STEP_BUILD_RECEIPT_V1", "build receipt schema drift")
    require(build.get("source_pins_verified") == 13, "build source pins are not 13/13")
    require(build.get("objects_requested") == build.get("objects_emitted") == build.get("primary_step_files") == 20, "build receipt object count drift")
    require(build.get("runtime_sidecar_files") == 60, "build runtime count drift")
    require(build.get("transform", {}).get("application_count_per_object") == 1, "build transform count drift")
    require(build.get("pair_eligible") is False and build.get("system_operational_credit") is False, "build grants system/pair credit")
    require(build.get("system_pair_query_credit") == 0 and build.get("safe_edge_path_credit") is False, "build grants query/edge/path credit")
    require(build.get("release_credit") is False, "build grants release credit")
    require(build.get("source_document_opened_read_only") is True and build.get("source_document_saved_or_recomputed") is False, "build source read-only boundary drift")
    verify_record(build["geometry_index"], GEOMETRY_INDEX_PATH)
    verify_record(build["runtime_sidecar_receipt"], RUNTIME_RECEIPT_PATH)
    require(geometry.get("schema") == "ROUTE_C_ROOT_STATIC_R20_GEOMETRY_INDEX_V1", "geometry index schema drift")
    require(geometry.get("object_count") == 20 and len(geometry.get("objects", [])) == 20, "geometry index count drift")
    require(geometry.get("output_valid_closed_single_positive_step_count") == 20, "geometry index STEP pass count drift")
    require(geometry.get("source_valid_closed_single_positive_brep_count") == 20, "geometry index source pass count drift")
    require(geometry.get("transform_application_count_per_object") == 1, "geometry index transform count drift")
    require(geometry.get("system_registry_rows_modified") == 0 and geometry.get("system_pair_query_credit") == 0, "geometry index grants system credit")
    require(runtime.get("schema") == "ROUTE_C_ROOT_STATIC_R20_RUNTIME_SIDECAR_DERIVATION_V1", "runtime receipt schema drift")
    require(runtime.get("object_count") == 20 and len(runtime.get("objects", [])) == 20, "runtime receipt object count drift")
    require(runtime.get("frame") == "S" and runtime.get("length_unit") == "m", "runtime receipt frame/unit drift")
    require(float(runtime.get("linear_deflection_mm")) == LINEAR_DEFLECTION_MM, "runtime receipt deflection drift")
    require(runtime.get("runtime_is_primary_geometry_authority") is False, "runtime authority boundary drift")
    require(float(runtime.get("step_to_runtime_scale")) == 0.001 and runtime.get("scale_application_count") == 1, "runtime scale ledger drift")
    require(runtime.get("sidecar_artifact_count") == 60 and runtime.get("sidecar_set_count") == 20, "runtime sidecar count drift")
    contract_ids = {row["object_id"] for row in validate_contract_structure(contract)}
    require({row["object_id"] for row in geometry["objects"]} == contract_ids, "geometry index object set drift")
    require({row["object_id"] for row in runtime["objects"]} == contract_ids, "runtime receipt object set drift")
    return {"build": build, "geometry": geometry, "runtime": runtime}
