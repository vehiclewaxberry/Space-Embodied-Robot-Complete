"""Independent validator for the isolated M01 pair-oracle backend.

This validator deliberately does *not* import ``pair_oracle_backend.py`` or the
package builder.  It reads the two hash-bound synthetic BRep boxes directly,
repeats all four geometric queries with OpenCascade, and independently applies
the frozen lower/upper-bound status rules.

The validation is fixture-only.  It never opens any current-system collision
geometry and it cannot create system pair, edge, path, parent-Gate, or release
credit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from OCP import __version__ as OCP_VERSION
from OCP.BRep import BRep_Builder
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.Precision import Precision
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Shape
from OCP.gp import gp_Trsf, gp_Vec


PACKAGE_DIR = Path(__file__).resolve().parent
CONTRACT_PATH = PACKAGE_DIR / "M01_SYSTEM_PAIR_ORACLE_BACKEND_CONTRACT_V1.json"
SOURCE_LOCK_PATH = PACKAGE_DIR / "SOURCE_AUTHORITY_LOCK_V1.json"
FIXTURE_SPEC_PATH = PACKAGE_DIR / "SYNTHETIC_FIXTURE_SPEC_V1.json"
FIXTURE_A_PATH = PACKAGE_DIR / "fixtures" / "BOX_A_10MM.brep"
FIXTURE_B_PATH = PACKAGE_DIR / "fixtures" / "BOX_B_10MM.brep"
EVIDENCE_PATH = PACKAGE_DIR / "results" / "SYNTHETIC_BACKEND_EVIDENCE_V1.json"
RESULT_PATH = PACKAGE_DIR / "results" / "INDEPENDENT_VALIDATION_V1.json"

HEX64 = re.compile(r"^[0-9A-F]{64}$")
DISTANCE_TOLERANCE_MM = 1.0e-9
WITNESS_TOLERANCE_MM = 1.0e-8
BOX_TOLERANCE_MM = 1.0e-7

POSE_FIELD_ALIASES = {
    "a": (
        "geometry_a_pose_S_row_major_binary64",
        "pose_a_S_row_major_binary64",
        "asset_a_pose_S_row_major_binary64",
    ),
    "b": (
        "geometry_b_pose_S_row_major_binary64",
        "pose_b_S_row_major_binary64",
        "asset_b_pose_S_row_major_binary64",
    ),
}

NUMERIC_FIELD_ALIASES = {
    "raw": ("raw_backend_separation_mm", "raw_separation_mm", "distance_mm"),
    "derate_a": ("object_a_hausdorff_derate_mm", "derate_a_mm"),
    "derate_b": ("object_b_hausdorff_derate_mm", "derate_b_mm"),
    "derate_backend": ("backend_numeric_derate_mm", "numeric_derate_mm"),
    "lower": ("certified_separation_lower_bound_mm", "certified_lower_bound_mm"),
    "upper": ("certified_separation_upper_bound_mm", "certified_upper_bound_mm"),
    "required": ("required_clearance_mm",),
    "authorized": ("authorized_pair_min_mm",),
    "margin_lower": ("certified_margin_lower_bound_mm", "certified_lower_margin_mm"),
    "margin_upper": ("certified_margin_upper_bound_mm", "certified_upper_margin_mm"),
}

FORBIDDEN_EXCEPTION_FIELDS = {
    "backend_id",
    "backend_version",
    "backend_configuration_sha256",
    "backend_determinism_receipt_sha256",
    "geometry_a_pose_S_row_major_binary64",
    "geometry_b_pose_S_row_major_binary64",
    "pose_a_S_row_major_binary64",
    "pose_b_S_row_major_binary64",
    "raw_backend_separation_mm",
    "raw_separation_mm",
    "distance_mm",
    "object_a_hausdorff_derate_mm",
    "object_b_hausdorff_derate_mm",
    "backend_numeric_derate_mm",
    "certified_separation_lower_bound_mm",
    "certified_separation_upper_bound_mm",
    "certified_lower_bound_mm",
    "certified_upper_bound_mm",
    "certified_upper_bound_evidence_sha256",
    "authorized_pair_min_mm",
    "required_clearance_mm",
    "certified_margin_lower_bound_mm",
    "certified_margin_upper_bound_mm",
    "certified_lower_margin_mm",
    "certified_upper_margin_mm",
    "intersection_or_contact_certified",
    "unsafe_witness_authority_sha256",
    "witness_point_a_S_mm",
    "witness_point_b_S_mm",
    "witness_feature_a",
    "witness_feature_b",
    "comparison_set_size",
    "finite",
    "complete",
}

SYSTEM_INVARIANTS = {
    "known_active_object_count": 150,
    "raw_unordered_pair_count": 11175,
    "exact_adjacent_exception_count": 9,
    "required_pair_query_count": 11166,
    "clearance_policy_rows_bound": 0,
    "system_operational_geometry_authority_rows": 1,
    "system_pair_oracle_bound": False,
    "system_pair_queries_executed": 0,
    "system_safe_pairs_certified": 0,
    "system_edges_certified": 0,
    "stage_instances_bound": 0,
    "path_search_authorized": False,
    "path_search_executed": False,
    "parent_mechanical_gate_reissued": False,
    "next_stage_authorized": False,
    "release_credit": False,
}

FORBIDDEN_TRUE_AUTHORITY_KEYS = {
    "current_system_backend_bound",
    "current_system_asset_support_claimed",
    "system_pair_oracle_bound",
    "system_pair_evaluation_authorized",
    "pair_evaluation_authorized",
    "edge_evaluation_authorized",
    "path_search_authorized",
    "path_search_executed",
    "parent_mechanical_gate_reissued",
    "parent_gate_reissued",
    "system_registry_reissued",
    "next_stage_authorized",
    "release_credit",
}


class ValidationFailure(RuntimeError):
    """Fail-closed deterministic validation failure."""


def require(condition: bool, message: str) -> None:
    if not bool(condition):
        raise ValidationFailure(message)


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        if path == EVIDENCE_PATH:
            raise ValidationFailure(
                "candidate evidence is missing; run build_m01_system_pair_oracle_backend.py "
                f"--write first: {path}"
            )
        raise ValidationFailure(f"required JSON is missing: {path}")
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationFailure(f"duplicate JSON key {key!r}: {path}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"cannot read deterministic JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def workspace_root() -> Path:
    for candidate in (PACKAGE_DIR, *PACKAGE_DIR.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise ValidationFailure("workspace root containing PROJECT_MAP.md was not found")


def sha256_path(path: Path) -> str:
    require(path.is_file(), f"hash-bound file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValidationFailure(f"path escapes workspace: {path}") from exc


def file_record(path: Path, root: Path) -> dict[str, Any]:
    require(path.is_file(), f"required file is missing: {path}")
    return {
        "path": relative_posix(path, root),
        "bytes": int(path.stat().st_size),
        "sha256": sha256_path(path),
    }


def resolve_locked_path(root: Path, raw_path: Any) -> Path:
    require(isinstance(raw_path, str) and raw_path, "source-lock path must be a non-empty string")
    path = (root / raw_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationFailure(f"source-lock path escapes workspace: {raw_path}") from exc
    return path


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def finite_float(value: Any, label: str) -> float:
    require(is_number(value), f"{label} must be a real binary64-compatible number")
    result = float(value)
    require(math.isfinite(result), f"{label} must be finite")
    return result


def nonnegative_float(value: Any, label: str) -> float:
    result = finite_float(value, label)
    require(result >= 0.0, f"{label} must be non-negative")
    return result


def binary64_equal(left: float, right: float) -> bool:
    return struct.pack("<d", float(left)) == struct.pack("<d", float(right))


def require_close(left: float, right: float, tolerance: float, label: str) -> None:
    require(
        math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance),
        f"{label} mismatch: {left!r} versus {right!r} (abs tol {tolerance})",
    )


def require_hex64(value: Any, label: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, f"{label} must be 64 uppercase hex")
    return value


def alias_value(mapping: dict[str, Any], names: Sequence[str], label: str) -> Any:
    present = [name for name in names if name in mapping]
    require(len(present) == 1, f"{label} must contain exactly one of {tuple(names)}; found {present}")
    return mapping[present[0]]


def optional_alias_value(mapping: dict[str, Any], names: Sequence[str], label: str) -> Any | None:
    present = [name for name in names if name in mapping]
    require(len(present) <= 1, f"{label} has ambiguous aliases: {present}")
    return mapping[present[0]] if present else None


def walk_scalars(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_scalars(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_scalars(child, (*path, str(index)))
    else:
        yield path, value


def values_for_key(value: Any, wanted: str) -> list[Any]:
    return [scalar for path, scalar in walk_scalars(value) if path and path[-1] == wanted]


def validate_source_pins(
    root: Path,
    contract: dict[str, Any],
    source_lock: dict[str, Any],
) -> dict[str, Any]:
    require(contract.get("schema") == "M01_SYSTEM_PAIR_ORACLE_BACKEND_CONTRACT_V1", "backend contract schema mismatch")
    require(
        source_lock.get("schema") == "M01_SYSTEM_PAIR_ORACLE_BACKEND_SOURCE_AUTHORITY_LOCK_V1",
        "source authority-lock schema mismatch",
    )

    upstream = contract.get("upstream_contract")
    require(isinstance(upstream, dict), "backend contract lacks upstream_contract")
    upstream_path = resolve_locked_path(root, upstream.get("path"))
    upstream_actual = file_record(upstream_path, root)
    require_hex64(upstream.get("sha256"), "upstream contract pin")
    require(upstream_actual["sha256"] == upstream["sha256"], "upstream pair-oracle contract SHA-256 drift")

    sources = source_lock.get("sources")
    require(isinstance(sources, list) and sources, "source authority lock must contain sources")
    seen_roles: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, row in enumerate(sources):
        require(isinstance(row, dict), f"source lock row {index} must be an object")
        role = row.get("role")
        require(isinstance(role, str) and role and role not in seen_roles, f"source lock role invalid/duplicate: {role!r}")
        seen_roles.add(role)
        path = resolve_locked_path(root, row.get("path"))
        actual = file_record(path, root)
        require(is_number(row.get("bytes")), f"source lock {role} bytes must be numeric")
        require(actual["bytes"] == int(row["bytes"]), f"source lock {role} byte-count drift")
        require_hex64(row.get("sha256"), f"source lock {role} sha256")
        require(actual["sha256"] == row["sha256"], f"source lock {role} SHA-256 drift")
        validated.append({"role": role, **actual})

    require(
        source_lock.get("next_stage_authorized") is False
        and source_lock.get("release_credit") is False,
        "source lock improperly upgrades authority",
    )
    return {
        "upstream_pair_oracle_contract": upstream_actual,
        "validated_source_count": len(validated),
        "validated_sources": validated,
    }


def count_solids(shape: TopoDS_Shape) -> int:
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def load_fixture_brep(path: Path, dimensions_mm: Sequence[Any], root: Path) -> tuple[TopoDS_Shape, dict[str, Any]]:
    require(path.is_file(), f"synthetic fixture BRep is missing: {path}")
    shape = TopoDS_Shape()
    builder = BRep_Builder()
    try:
        loaded = BRepTools.Read_s(shape, str(path), builder)
    except Exception as exc:  # OCP raises implementation-specific exceptions.
        raise ValidationFailure(f"BRepTools failed to read fixture {path.name}: {exc}") from exc
    require(bool(loaded) and not shape.IsNull(), f"BRepTools returned no shape for {path.name}")
    require(BRepCheck_Analyzer(shape, True).IsValid(), f"fixture BRep is invalid: {path.name}")
    solid_count = count_solids(shape)
    require(solid_count == 1, f"fixture must contain exactly one solid: {path.name}")

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    require(not box.IsVoid(), f"fixture BRep has void bounds: {path.name}")
    bounds = tuple(float(value) for value in box.Get())
    expected_dimensions = [finite_float(value, f"{path.name} dimension") for value in dimensions_mm]
    require(len(expected_dimensions) == 3, f"fixture dimensions must contain three values: {path.name}")
    expected_bounds = (0.0, 0.0, 0.0, *expected_dimensions)
    for index, (actual, expected) in enumerate(zip(bounds, expected_bounds, strict=True)):
        require_close(actual, expected, BOX_TOLERANCE_MM, f"{path.name} bbox[{index}]")

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    volume_mm3 = float(props.Mass())
    expected_volume_mm3 = math.prod(expected_dimensions)
    require_close(volume_mm3, expected_volume_mm3, 1.0e-5, f"{path.name} volume")

    return shape, {
        **file_record(path, root),
        "native_length_unit": "mm",
        "valid": True,
        "solid_count": solid_count,
        "bbox_mm": list(bounds),
        "volume_mm3": volume_mm3,
    }


def expected_pose_row_major_m(translation_m: Sequence[Any]) -> list[float]:
    require(len(translation_m) == 3, "fixture translation must contain three values")
    tx, ty, tz = [finite_float(value, "fixture translation") for value in translation_m]
    return [
        1.0,
        0.0,
        0.0,
        tx,
        0.0,
        1.0,
        0.0,
        ty,
        0.0,
        0.0,
        1.0,
        tz,
        0.0,
        0.0,
        0.0,
        1.0,
    ]


def validate_pose(value: Any, expected: Sequence[float], label: str) -> list[float]:
    require(isinstance(value, list) and len(value) == 16, f"{label} must be a 16-value row-major pose")
    pose = [finite_float(item, f"{label}[{index}]") for index, item in enumerate(value)]
    for index, (actual, wanted) in enumerate(zip(pose, expected, strict=True)):
        require(binary64_equal(actual, wanted), f"{label}[{index}] differs from exact metre-input pose")
    return pose


def translated_shape(shape: TopoDS_Shape, translation_m: Sequence[Any]) -> TopoDS_Shape:
    tx_m, ty_m, tz_m = [finite_float(value, "translation_m") for value in translation_m]
    # This is the sole length-boundary conversion in the independent path.
    tx_mm, ty_mm, tz_mm = 1000.0 * tx_m, 1000.0 * ty_m, 1000.0 * tz_m
    transform = gp_Trsf()
    transform.SetTranslationPart(gp_Vec(tx_mm, ty_mm, tz_mm))
    moved = BRepBuilderAPI_Transform(shape, transform, True)
    require(moved.IsDone(), "OCP fixture transformation failed")
    return moved.Shape()


def point_tuple(point: Any) -> tuple[float, float, float]:
    return tuple(float(value) for value in point.Coord())


def ocp_distance_query(
    shape_a: TopoDS_Shape,
    shape_b: TopoDS_Shape,
    translation_b_m: Sequence[Any],
) -> dict[str, Any]:
    moved_a = translated_shape(shape_a, (0.0, 0.0, 0.0))
    moved_b = translated_shape(shape_b, translation_b_m)
    try:
        query = BRepExtrema_DistShapeShape(moved_a, moved_b)
        query.SetMultiThread(False)
        query.Perform()
    except Exception as exc:
        raise ValidationFailure(f"BRepExtrema fixture query failed: {exc}") from exc
    require(query.IsDone(), "BRepExtrema fixture query is incomplete")
    comparison_set_size = int(query.NbSolution())
    require(comparison_set_size > 0, "BRepExtrema fixture query returned an empty solution set")
    raw_mm = float(query.Value())
    require(math.isfinite(raw_mm) and raw_mm >= 0.0, "BRepExtrema returned invalid unsigned distance")
    witness_pairs = sorted(
        (point_tuple(query.PointOnShape1(index)), point_tuple(query.PointOnShape2(index)))
        for index in range(1, comparison_set_size + 1)
    )
    require(witness_pairs, "BRepExtrema returned no nearest-point witness")
    return {
        "raw_backend_separation_mm": raw_mm,
        "comparison_set_size": comparison_set_size,
        "witness_pairs_S_mm": [[list(a), list(b)] for a, b in witness_pairs],
        "inner_solution": bool(query.InnerSolution()),
        "complete": True,
    }


def extract_case_rows(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    containers: list[tuple[str, Any]] = []
    for name in ("cases", "records", "results", "synthetic_cases"):
        if name in evidence:
            containers.append((name, evidence[name]))
    if not containers and isinstance(evidence.get("synthetic_validation"), dict):
        nested = evidence["synthetic_validation"]
        for name in ("cases", "records", "results", "synthetic_cases"):
            if name in nested:
                containers.append((f"synthetic_validation.{name}", nested[name]))
    list_containers = [(name, value) for name, value in containers if isinstance(value, list)]
    require(len(list_containers) == 1, f"candidate evidence must expose one cases/records/results list; found {[n for n, _ in list_containers]}")
    rows = list_containers[0][1]
    require(all(isinstance(row, dict) for row in rows), "candidate evidence case rows must be objects")
    return rows


def case_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        case_id = row.get("case_id")
        require(isinstance(case_id, str) and case_id, f"candidate evidence row {index} lacks case_id")
        require(case_id not in mapped, f"duplicate candidate evidence case_id: {case_id}")
        require(isinstance(row.get("request"), dict), f"{case_id} lacks request object")
        require(isinstance(row.get("result"), dict), f"{case_id} lacks result object")
        mapped[case_id] = row
    return mapped


def canonical_pair_id(object_a: str, object_b: str) -> str:
    left, right = sorted((object_a, object_b))
    return f"{left}||{right}"


def validate_common_identity(
    request: dict[str, Any],
    result: dict[str, Any],
    object_a: str,
    object_b: str,
    expected_row_kind: str,
    label: str,
) -> None:
    pair_id = canonical_pair_id(object_a, object_b)
    require(request.get("object_id_a") == object_a, f"{label} request object_id_a mismatch")
    require(request.get("object_id_b") == object_b, f"{label} request object_id_b mismatch")
    require(request.get("pair_id") == pair_id, f"{label} request pair_id mismatch")
    require(result.get("pair_id") == pair_id, f"{label} result pair_id mismatch")
    require(request.get("row_kind") == expected_row_kind, f"{label} request row_kind mismatch")
    require(result.get("row_kind") == expected_row_kind, f"{label} result row_kind mismatch")
    if "request_id" in result:
        require(result.get("request_id") == request.get("request_id"), f"{label} request_id round-trip mismatch")


def validate_request_hashes(
    request: dict[str, Any],
    fixture_a_sha: str,
    fixture_b_sha: str,
    upstream_contract_sha: str,
    label: str,
) -> None:
    require_hex64(request.get("object_a_geometry_asset_sha256"), f"{label} object A geometry hash")
    require_hex64(request.get("object_b_geometry_asset_sha256"), f"{label} object B geometry hash")
    require(request["object_a_geometry_asset_sha256"] == fixture_a_sha, f"{label} object A geometry hash drift")
    require(request["object_b_geometry_asset_sha256"] == fixture_b_sha, f"{label} object B geometry hash drift")
    require_hex64(request.get("pair_oracle_contract_sha256"), f"{label} pair contract hash")
    require(request["pair_oracle_contract_sha256"] == upstream_contract_sha, f"{label} pair contract source-pin drift")
    for name in (
        "q_bytes_sha256",
        "scene_state_sha256",
        "registry_sha256",
        "allowed_collision_exact_pair_set_sha256",
        "clearance_policy_sha256",
        "object_a_motion_binding_sha256",
        "object_b_motion_binding_sha256",
        "mount_binding_sha256",
        "backend_configuration_sha256",
    ):
        require_hex64(request.get(name), f"{label} request {name}")

    q_values = request.get("q_rad_binary64")
    q_order = request.get("q_order")
    require(isinstance(q_values, list) and isinstance(q_order, list), f"{label} q vector/order must be lists")
    require(len(q_values) == len(q_order), f"{label} q vector/order length mismatch")
    q_numeric = [finite_float(value, f"{label} q_rad_binary64[{index}]") for index, value in enumerate(q_values)]
    q_digest = hashlib.sha256(b"".join(struct.pack("<d", value) for value in q_numeric)).hexdigest().upper()
    require(q_digest == request["q_bytes_sha256"], f"{label} exact little-endian binary64 q hash drift")


def validate_geometric_binding_round_trip(
    request: dict[str, Any],
    result: dict[str, Any],
    expected_backend_id: str,
    label: str,
) -> None:
    require(request.get("backend_id") == expected_backend_id, f"{label} request backend_id mismatch")
    require(result.get("backend_id") == expected_backend_id, f"{label} result backend_id mismatch")
    require(
        isinstance(request.get("backend_version"), str) and request["backend_version"],
        f"{label} request backend_version is missing",
    )
    require(result.get("backend_version") == request["backend_version"], f"{label} backend_version round-trip drift")
    require(request.get("pose_frame") == "S", f"{label} pose frame must be S")
    require(request.get("pose_translation_unit") == "m", f"{label} pose translation input must be metres")
    require(request.get("brep_native_length_unit") == "mm", f"{label} BRep native unit must be millimetres")
    require(request.get("distance_output_unit") == "mm", f"{label} distance output unit must be millimetres")
    require(request.get("joint_unit") == "rad", f"{label} joint unit must be radians")
    require(request.get("fixture_only") is True, f"{label} request must remain fixture_only=true")

    for name in (
        "q_bytes_sha256",
        "scene_state_sha256",
        "pair_oracle_contract_sha256",
        "allowed_collision_exact_pair_set_sha256",
        "clearance_policy_sha256",
        "backend_configuration_sha256",
        "backend_determinism_receipt_sha256",
    ):
        require_hex64(result.get(name), f"{label} result {name}")
        require(result[name] == request[name], f"{label} result {name} round-trip drift")
    require_hex64(result.get("input_binding_sha256"), f"{label} result input binding")
    require_hex64(result.get("evidence_sha256"), f"{label} result evidence")


def witness_matches(
    point_a: Sequence[Any],
    point_b: Sequence[Any],
    recomputed_pairs: Sequence[Sequence[Sequence[float]]],
) -> bool:
    if not isinstance(point_a, list) or not isinstance(point_b, list) or len(point_a) != 3 or len(point_b) != 3:
        return False
    try:
        a = [finite_float(value, "candidate witness A") for value in point_a]
        b = [finite_float(value, "candidate witness B") for value in point_b]
    except ValidationFailure:
        return False
    for expected_a, expected_b in recomputed_pairs:
        if all(math.isclose(a[i], expected_a[i], rel_tol=0.0, abs_tol=WITNESS_TOLERANCE_MM) for i in range(3)) and all(
            math.isclose(b[i], expected_b[i], rel_tol=0.0, abs_tol=WITNESS_TOLERANCE_MM) for i in range(3)
        ):
            return True
    return False


def status_from_interval(lower_margin_mm: float, upper_margin_mm: float, contact: bool) -> str:
    if lower_margin_mm > 0.0:
        return "SAFE"
    if contact or upper_margin_mm <= 0.0:
        return "UNSAFE"
    return "UNKNOWN"


def validate_geometric_case(
    row: dict[str, Any],
    spec_row: dict[str, Any],
    shape_a: TopoDS_Shape,
    shape_b: TopoDS_Shape,
    fixture_a_sha: str,
    fixture_b_sha: str,
    upstream_contract_sha: str,
    fixture_numeric: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(spec_row["case_id"])
    request = row["request"]
    result = row["result"]
    object_a = "FIXTURE::BOX_A"
    object_b = "FIXTURE::BOX_B"
    validate_common_identity(request, result, object_a, object_b, "GEOMETRIC_RESULT", case_id)
    validate_request_hashes(request, fixture_a_sha, fixture_b_sha, upstream_contract_sha, case_id)
    validate_geometric_binding_round_trip(
        request,
        result,
        "OCP_BREP_DISTANCE_PAIR_ORACLE_V1",
        case_id,
    )

    translation_m = spec_row.get("asset_b_translation_S_m")
    require(isinstance(translation_m, list), f"{case_id} fixture spec lacks translation")
    pose_a_expected = expected_pose_row_major_m((0.0, 0.0, 0.0))
    pose_b_expected = expected_pose_row_major_m(translation_m)
    request_pose_a = alias_value(request, POSE_FIELD_ALIASES["a"], f"{case_id} request pose A")
    request_pose_b = alias_value(request, POSE_FIELD_ALIASES["b"], f"{case_id} request pose B")
    validate_pose(request_pose_a, pose_a_expected, f"{case_id} request pose A")
    validate_pose(request_pose_b, pose_b_expected, f"{case_id} request pose B")
    result_pose_a = alias_value(result, POSE_FIELD_ALIASES["a"], f"{case_id} result pose A")
    result_pose_b = alias_value(result, POSE_FIELD_ALIASES["b"], f"{case_id} result pose B")
    validate_pose(result_pose_a, pose_a_expected, f"{case_id} result pose A")
    validate_pose(result_pose_b, pose_b_expected, f"{case_id} result pose B")

    authorized = nonnegative_float(
        alias_value(request, NUMERIC_FIELD_ALIASES["authorized"], f"{case_id} authorized minimum"),
        f"{case_id} authorized minimum",
    )
    required = nonnegative_float(
        alias_value(request, NUMERIC_FIELD_ALIASES["required"], f"{case_id} required clearance"),
        f"{case_id} required clearance",
    )
    require(required >= authorized, f"{case_id} required clearance is below authorized minimum")
    require(binary64_equal(authorized, float(fixture_numeric["authorized_pair_min_mm"])), f"{case_id} authorized minimum differs from fixture spec")
    require(binary64_equal(required, float(fixture_numeric["required_clearance_mm"])), f"{case_id} required clearance differs from fixture spec")

    independent = ocp_distance_query(shape_a, shape_b, translation_m)
    independent_raw = float(independent["raw_backend_separation_mm"])
    expected_raw = nonnegative_float(spec_row.get("expected_raw_separation_mm"), f"{case_id} expected raw distance")
    require_close(independent_raw, expected_raw, DISTANCE_TOLERANCE_MM, f"{case_id} independent OCP distance")

    candidate_raw = nonnegative_float(
        alias_value(result, NUMERIC_FIELD_ALIASES["raw"], f"{case_id} raw distance"),
        f"{case_id} candidate raw distance",
    )
    require_close(candidate_raw, independent_raw, DISTANCE_TOLERANCE_MM, f"{case_id} candidate versus independent distance")

    derate_a = nonnegative_float(alias_value(result, NUMERIC_FIELD_ALIASES["derate_a"], f"{case_id} derate A"), f"{case_id} derate A")
    derate_b = nonnegative_float(alias_value(result, NUMERIC_FIELD_ALIASES["derate_b"], f"{case_id} derate B"), f"{case_id} derate B")
    derate_backend = nonnegative_float(
        alias_value(result, NUMERIC_FIELD_ALIASES["derate_backend"], f"{case_id} backend derate"),
        f"{case_id} backend derate",
    )
    require(binary64_equal(derate_a, float(fixture_numeric["object_a_hausdorff_derate_mm"])), f"{case_id} object A derate mismatch")
    require(binary64_equal(derate_b, float(fixture_numeric["object_b_hausdorff_derate_mm"])), f"{case_id} object B derate mismatch")
    expected_backend_derate = float(Precision.Approximation_s())
    require(binary64_equal(derate_backend, expected_backend_derate), f"{case_id} backend numeric derate is not OCP Precision.Approximation")

    # Deliberately left-associated; do not algebraically regroup this ledger.
    candidate_lower_expected = (((candidate_raw - derate_a) - derate_b) - derate_backend)
    candidate_lower = finite_float(alias_value(result, NUMERIC_FIELD_ALIASES["lower"], f"{case_id} lower bound"), f"{case_id} lower bound")
    require(binary64_equal(candidate_lower, candidate_lower_expected), f"{case_id} lower-bound arithmetic is not byte-identical left-associated binary64")

    candidate_upper = nonnegative_float(alias_value(result, NUMERIC_FIELD_ALIASES["upper"], f"{case_id} upper bound"), f"{case_id} upper bound")
    require_close(candidate_upper, candidate_raw, DISTANCE_TOLERANCE_MM, f"{case_id} witnessed upper bound")
    upper_evidence = require_hex64(result.get("certified_upper_bound_evidence_sha256"), f"{case_id} upper-bound evidence hash")

    result_required = nonnegative_float(alias_value(result, NUMERIC_FIELD_ALIASES["required"], f"{case_id} result required clearance"), f"{case_id} result required clearance")
    result_authorized = nonnegative_float(alias_value(result, NUMERIC_FIELD_ALIASES["authorized"], f"{case_id} result authorized minimum"), f"{case_id} result authorized minimum")
    require(binary64_equal(result_required, required), f"{case_id} required-clearance round-trip drift")
    require(binary64_equal(result_authorized, authorized), f"{case_id} authorized-minimum round-trip drift")

    lower_margin_expected = candidate_lower - required
    upper_margin_expected = candidate_upper - required
    lower_margin = finite_float(alias_value(result, NUMERIC_FIELD_ALIASES["margin_lower"], f"{case_id} lower margin"), f"{case_id} lower margin")
    upper_margin = finite_float(alias_value(result, NUMERIC_FIELD_ALIASES["margin_upper"], f"{case_id} upper margin"), f"{case_id} upper margin")
    require(binary64_equal(lower_margin, lower_margin_expected), f"{case_id} lower-margin arithmetic drift")
    require(binary64_equal(upper_margin, upper_margin_expected), f"{case_id} upper-margin arithmetic drift")
    require(candidate_lower <= candidate_upper, f"{case_id} certified interval is inverted")

    contact_expected = independent_raw <= DISTANCE_TOLERANCE_MM and expected_raw == 0.0
    contact = result.get("intersection_or_contact_certified")
    require(isinstance(contact, bool), f"{case_id} contact certification must be boolean")
    require(contact is contact_expected, f"{case_id} contact certification mismatch")
    candidate_status = result.get("status")
    independently_derived_status = status_from_interval(lower_margin, upper_margin, contact)
    expected_status = spec_row.get("expected_status")
    require(candidate_status == expected_status, f"{case_id} candidate status mismatch")
    require(independently_derived_status == expected_status, f"{case_id} independent status recomputation mismatch")
    if lower_margin <= 0.0 and upper_margin > 0.0 and not contact:
        require(candidate_status == "UNKNOWN", f"{case_id} non-positive lower bound was illegally promoted")

    require(result.get("finite") is True, f"{case_id} result must declare finite=true")
    require(result.get("complete") is True, f"{case_id} result must declare complete=true")
    comparison_set_size = result.get("comparison_set_size")
    require(isinstance(comparison_set_size, int) and not isinstance(comparison_set_size, bool) and comparison_set_size > 0, f"{case_id} comparison_set_size must be a positive integer")
    witness_a = result.get("witness_point_a_S_mm")
    witness_b = result.get("witness_point_b_S_mm")
    require(
        witness_matches(witness_a, witness_b, independent["witness_pairs_S_mm"]),
        f"{case_id} candidate nearest-point witness is absent from independent OCP solutions",
    )
    if candidate_status == "UNSAFE":
        require_hex64(result.get("unsafe_witness_authority_sha256"), f"{case_id} unsafe witness authority")

    return {
        "case_id": case_id,
        "expected_status": expected_status,
        "candidate_status": candidate_status,
        "independent_status": independently_derived_status,
        "translation_input_m": [float(value) for value in translation_m],
        "translation_applied_mm": [1000.0 * float(value) for value in translation_m],
        "independent_raw_backend_separation_mm": independent_raw,
        "candidate_raw_backend_separation_mm": candidate_raw,
        "object_a_hausdorff_derate_mm": derate_a,
        "object_b_hausdorff_derate_mm": derate_b,
        "backend_numeric_derate_mm": derate_backend,
        "certified_separation_lower_bound_mm": candidate_lower,
        "certified_separation_upper_bound_mm": candidate_upper,
        "certified_margin_lower_bound_mm": lower_margin,
        "certified_margin_upper_bound_mm": upper_margin,
        "intersection_or_contact_certified": contact,
        "independent_comparison_set_size": independent["comparison_set_size"],
        "candidate_comparison_set_size": comparison_set_size,
        "candidate_witness_matches_independent_solution": True,
        "certified_upper_bound_evidence_sha256": upper_evidence,
        "validation_pass": True,
    }


def validate_exception_case(
    row: dict[str, Any],
    spec: dict[str, Any],
    upstream_contract_sha: str,
) -> dict[str, Any]:
    case_id = str(spec.get("case_id"))
    request = row["request"]
    result = row["result"]
    object_a = str(spec.get("object_id_a"))
    object_b = str(spec.get("object_id_b"))
    validate_common_identity(request, result, object_a, object_b, "EXCEPTION_RESULT", case_id)
    require(result.get("status") == "EXEMPT_ADJACENT", f"{case_id} status must be EXEMPT_ADJACENT")
    require(request.get("fixture_only") is True, f"{case_id} exception request must remain fixture_only=true")
    require_hex64(request.get("pair_oracle_contract_sha256"), f"{case_id} request pair contract hash")
    require(request["pair_oracle_contract_sha256"] == upstream_contract_sha, f"{case_id} pair contract source-pin drift")
    for name in (
        "q_bytes_sha256",
        "scene_state_sha256",
        "registry_sha256",
        "allowed_collision_exact_pair_set_sha256",
        "clearance_policy_sha256",
    ):
        require_hex64(request.get(name), f"{case_id} request {name}")
    q_values = request.get("q_rad_binary64")
    q_order = request.get("q_order")
    require(isinstance(q_values, list) and isinstance(q_order, list), f"{case_id} q vector/order must be lists")
    require(len(q_values) == len(q_order), f"{case_id} q vector/order length mismatch")
    q_numeric = [finite_float(value, f"{case_id} q_rad_binary64[{index}]") for index, value in enumerate(q_values)]
    q_digest = hashlib.sha256(b"".join(struct.pack("<d", value) for value in q_numeric)).hexdigest().upper()
    require(q_digest == request["q_bytes_sha256"], f"{case_id} exact little-endian binary64 q hash drift")
    for name in (
        "q_bytes_sha256",
        "scene_state_sha256",
        "pair_oracle_contract_sha256",
        "allowed_collision_exact_pair_set_sha256",
        "clearance_policy_sha256",
    ):
        require_hex64(result.get(name), f"{case_id} result {name}")
        require(result[name] == request[name], f"{case_id} result {name} round-trip drift")
    require_hex64(result.get("input_binding_sha256"), f"{case_id} result input binding")
    require_hex64(result.get("evidence_sha256"), f"{case_id} result evidence")

    request_forbidden = sorted(FORBIDDEN_EXCEPTION_FIELDS.intersection(request))
    result_forbidden = sorted(FORBIDDEN_EXCEPTION_FIELDS.intersection(result))
    require(not request_forbidden, f"{case_id} exception request contains geometric fields: {request_forbidden}")
    require(not result_forbidden, f"{case_id} exception result contains geometric fields: {result_forbidden}")
    for name in (
        "exception_rule_id",
        "exception_rule_sha256",
        "exception_pair_set_membership_proof_sha256",
    ):
        require(name in result, f"{case_id} exception result lacks {name}")
    require(isinstance(result["exception_rule_id"], str) and result["exception_rule_id"], f"{case_id} exception_rule_id invalid")
    require_hex64(result["exception_rule_sha256"], f"{case_id} exception rule hash")
    require_hex64(result["exception_pair_set_membership_proof_sha256"], f"{case_id} membership proof hash")
    return {
        "case_id": case_id,
        "status": "EXEMPT_ADJACENT",
        "exact_pair_id": canonical_pair_id(object_a, object_b),
        "geometric_fields_present": [],
        "counts_as_safe": False,
        "validation_pass": True,
    }


def validate_system_invariants(evidence: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    contract_invariants = contract.get("current_system_authority_invariants")
    require(isinstance(contract_invariants, dict), "backend contract lacks current-system invariants")
    observed: dict[str, Any] = {}
    for key, expected in SYSTEM_INVARIANTS.items():
        require(contract_invariants.get(key) == expected, f"backend contract invariant drift: {key}")
        occurrences = values_for_key(evidence, key)
        require(occurrences, f"candidate evidence omits current-system invariant: {key}")
        for value in occurrences:
            if isinstance(expected, bool):
                require(isinstance(value, bool) and value is expected, f"candidate evidence authority drift: {key}={value!r}")
            else:
                require(isinstance(value, int) and not isinstance(value, bool) and value == expected, f"candidate evidence counter drift: {key}={value!r}")
        observed[key] = expected

    for path, value in walk_scalars(evidence):
        if path and path[-1] in FORBIDDEN_TRUE_AUTHORITY_KEYS:
            require(value is False, f"candidate evidence illegally sets {'.'.join(path)}={value!r}")
    return observed


def validate_all() -> dict[str, Any]:
    root = workspace_root()
    contract = read_json(CONTRACT_PATH)
    source_lock = read_json(SOURCE_LOCK_PATH)
    fixture_spec = read_json(FIXTURE_SPEC_PATH)
    evidence = read_json(EVIDENCE_PATH)

    source_validation = validate_source_pins(root, contract, source_lock)
    upstream_contract_sha = source_validation["upstream_pair_oracle_contract"]["sha256"]
    require(
        contract.get("backend", {}).get("fixture_only") is True
        and contract.get("backend", {}).get("current_system_backend_bound") is False,
        "backend contract fixture-only authority drift",
    )
    unit_contract = contract.get("unit_and_frame_contract")
    require(isinstance(unit_contract, dict), "backend contract lacks unit ledger")
    require(
        unit_contract.get("brep_native_length_unit") == "mm"
        and unit_contract.get("pose_translation_input_unit") == "m"
        and unit_contract.get("distance_output_unit") == "mm"
        and unit_contract.get("witness_output_unit") == "mm"
        and unit_contract.get("only_length_boundary_conversion") == "translation_mm = 1000.0 * translation_m",
        "backend contract mm/m boundary drift",
    )

    require(fixture_spec.get("schema") == "M01_PAIR_ORACLE_SYNTHETIC_FIXTURE_SPEC_V1", "fixture spec schema mismatch")
    geometry = fixture_spec.get("geometry")
    require(isinstance(geometry, dict), "fixture spec lacks geometry")
    asset_a_spec = geometry.get("asset_a")
    asset_b_spec = geometry.get("asset_b")
    require(isinstance(asset_a_spec, dict) and isinstance(asset_b_spec, dict), "fixture asset specs are missing")
    require(asset_a_spec.get("native_unit") == "mm" and asset_b_spec.get("native_unit") == "mm", "fixture BRep native-unit drift")
    shape_a, fixture_a_record = load_fixture_brep(FIXTURE_A_PATH, asset_a_spec.get("dimensions_mm", []), root)
    shape_b, fixture_b_record = load_fixture_brep(FIXTURE_B_PATH, asset_b_spec.get("dimensions_mm", []), root)

    evidence_rows = extract_case_rows(evidence)
    mapped_rows = case_map(evidence_rows)
    case_specs = fixture_spec.get("cases")
    exception_spec = fixture_spec.get("exception_case")
    require(isinstance(case_specs, list) and len(case_specs) == 4, "fixture spec must contain exactly four geometric cases")
    require(isinstance(exception_spec, dict), "fixture spec lacks exact exception case")
    expected_ids = {str(row.get("case_id")) for row in case_specs} | {str(exception_spec.get("case_id"))}
    require(set(mapped_rows) == expected_ids, f"candidate evidence case set mismatch: {sorted(mapped_rows)}")

    numeric = fixture_spec.get("numeric_configuration")
    require(isinstance(numeric, dict), "fixture spec lacks numeric configuration")
    require(numeric.get("backend_numeric_derate_authority") == "OCP_PRECISION_APPROXIMATION_NATIVE_MM", "fixture backend-derate authority drift")
    geometric_results: dict[str, Any] = {}
    for spec_row in case_specs:
        require(isinstance(spec_row, dict), "fixture geometric case spec must be an object")
        case_id = str(spec_row.get("case_id"))
        geometric_results[case_id] = validate_geometric_case(
            mapped_rows[case_id],
            spec_row,
            shape_a,
            shape_b,
            fixture_a_record["sha256"],
            fixture_b_record["sha256"],
            upstream_contract_sha,
            numeric,
        )

    exception_result = validate_exception_case(
        mapped_rows[str(exception_spec["case_id"])],
        exception_spec,
        upstream_contract_sha,
    )
    system_invariants = validate_system_invariants(evidence, contract)

    return {
        "schema": "M01_SYSTEM_PAIR_ORACLE_BACKEND_INDEPENDENT_VALIDATION_V1",
        "generated_utc": "DETERMINISTIC_VALIDATION_NO_WALLCLOCK",
        "authority": "INDEPENDENT_SYNTHETIC_BACKEND_VALIDATION_ONLY__NO_CURRENT_SYSTEM_GEOMETRY_OR_QUERY_AUTHORITY",
        "review_status": "PENDING_OWNER_REVIEW",
        "validator_independence": {
            "candidate_core_imported": False,
            "candidate_builder_imported": False,
            "distance_recompute": "DIRECT_OCP_BREPTOOLS_AND_BREPEXTREMA_FROM_HASH_BOUND_FIXTURES",
            "status_recompute": "INDEPENDENT_LEFT_ASSOCIATIVE_BINARY64_LOWER_UPPER_MARGIN_RULES",
            "production_geometry_loaded": False,
            "production_pair_query_executed": False,
        },
        "runtime": {
            "python": sys.version.split()[0],
            "ocp": str(OCP_VERSION),
            "backend_numeric_derate_mm": float(Precision.Approximation_s()),
            "ocp_multithread": False,
        },
        "input_files": {
            "validator": file_record(Path(__file__), root),
            "backend_contract": file_record(CONTRACT_PATH, root),
            "source_authority_lock": file_record(SOURCE_LOCK_PATH, root),
            "synthetic_fixture_spec": file_record(FIXTURE_SPEC_PATH, root),
            "candidate_evidence": file_record(EVIDENCE_PATH, root),
            "fixture_a": fixture_a_record,
            "fixture_b": fixture_b_record,
        },
        "source_pin_validation": source_validation,
        "unit_boundary_validation": {
            "brep_native_length_unit": "mm",
            "pose_translation_input_unit": "m",
            "distance_and_witness_output_unit": "mm",
            "only_length_boundary_conversion": "translation_mm = 1000.0 * translation_m",
            "mixed_unit_inference_used": False,
            "validation_pass": True,
        },
        "geometric_cases": geometric_results,
        "exception_case": exception_result,
        "status_semantics": {
            "safe_requires_strict_positive_lower_margin": True,
            "unsafe_requires_nonpositive_certified_upper_margin_or_contact": True,
            "nonpositive_lower_only_is_unknown": True,
            "unknown_auto_allow": False,
            "exception_counts_as_safe": False,
            "validation_pass": True,
        },
        "current_system_authority_invariants": system_invariants,
        "summary": {
            "geometric_cases_passed": len(geometric_results),
            "geometric_cases_required": 4,
            "exception_cases_passed": 1,
            "exception_cases_required": 1,
            "source_pins_validated": source_validation["validated_source_count"],
            "system_pair_queries_executed": 0,
            "system_safe_pairs_certified": 0,
            "system_edges_certified": 0,
            "path_search_executed": False,
        },
        "validation_pass": True,
        "parent_mechanical_gate_reissued": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "maximum_legal_claim": "PAIR_ORACLE_SCHEMA_AND_FAIL_CLOSED_BACKEND_IMPLEMENTED_AND_SYNTHETICALLY_VALIDATED__ZERO_CURRENT_SYSTEM_PAIR_QUERIES__ZERO_SAFE_PAIRS__NO_EDGE_PATH_PARENT_OR_RELEASE_CREDIT",
        "verdict": "INDEPENDENT_SYNTHETIC_PAIR_ORACLE_VALIDATION_PASS__ZERO_CURRENT_SYSTEM_PAIR_QUERIES__NO_EDGE_PATH_PARENT_OR_RELEASE_CREDIT",
    }


def encode_result(result: dict[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help=f"atomically write {RESULT_PATH.name}")
    mode.add_argument("--check", action="store_true", help="recompute and require byte-identical existing validation JSON")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = validate_all()
        payload = encode_result(result)
        if args.check:
            require(RESULT_PATH.is_file(), f"independent validation output is missing: {RESULT_PATH}")
            require(RESULT_PATH.read_bytes() == payload, "independent validation output differs from fresh deterministic recomputation")
        elif args.write:
            atomic_write(RESULT_PATH, payload)
        sys.stdout.buffer.write(payload)
        return 0
    except ValidationFailure as exc:
        print(f"VALIDATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
