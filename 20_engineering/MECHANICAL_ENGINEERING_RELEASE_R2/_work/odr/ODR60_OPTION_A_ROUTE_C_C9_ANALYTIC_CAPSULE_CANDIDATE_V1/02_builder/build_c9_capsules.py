"""Build nine deterministic Route-C analytic capsule-chain candidates.

The script reads the frozen V9F centerline JSON as data.  It never imports,
traces, or executes the V9F FreeCAD builder or exact evaluator.  Polyline
fillets are reconstructed from the frozen source algorithm, including the
0.98 available-leg clamp and the resulting actual rather than desired radius.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np


class BuildFailure(RuntimeError):
    """Fail-closed deterministic build error."""


PACKAGE = Path(__file__).resolve().parents[1]
SOURCE_LOCK_PATH = PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json"
CONTRACT_PATH = PACKAGE / "00_contract/C9_ANALYTIC_CAPSULE_CONTRACT_V1.json"
FRAME_LEDGER_PATH = PACKAGE / "00_contract/FRAME_UNIT_AND_MOTION_LEDGER_V1.json"
RUNTIME_REL = Path("03_runtime")
RESULTS_REL = Path("05_results")
INDEX_REL = RESULTS_REL / "C9_CAPSULE_INDEX_V1.json"
BUILD_RECEIPT_REL = RESULTS_REL / "C9_BUILD_RECEIPT_V1.json"
MAX_CURVE_STEP_MM = 1.5
DESIGN_RADIUS_MM = 5.0
J4_SELECTOR = "SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER"
J4_SECTION5 = 5
J4_SECTION5_TOPOLOGY_COUNT = 139
J4_Q4_LOWER_RAD = -1.87
J4_Q4_UPPER_RAD = 1.57
J4_ANNULUS_RADIUS_MM = 55.0
SOURCE_BREP_LENGTH_RECONCILIATION_TOL_MM = 1.0e-3
EPS = 1.0e-12


def workspace_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "20_engineering").is_dir():
            return candidate
    raise BuildFailure("workspace root not found")


def strict_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise BuildFailure(f"non-finite JSON token {value} in {path}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildFailure(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BuildFailure(f"JSON root must be an object: {path}")
    return value


def stable_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildFailure(message)


def file_record(path: Path, relative_to: Path | None = None) -> dict[str, Any]:
    require(path.is_file(), f"missing file: {path}")
    label = path.relative_to(relative_to).as_posix() if relative_to is not None else path.as_posix()
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha256_path(path)}


def verify_sources(source_lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    root = workspace_root()
    sources = source_lock.get("sources")
    require(isinstance(sources, dict) and len(sources) == source_lock.get("source_count") == 18,
            "source lock must contain exactly eighteen pins")
    verified: dict[str, dict[str, Any]] = {}
    for name, record in sources.items():
        require(isinstance(record, dict), f"source record is not an object: {name}")
        path = root / str(record.get("path"))
        require(path.is_file(), f"source missing: {name}: {path}")
        observed = {"path": record["path"], "bytes": path.stat().st_size, "sha256": sha256_path(path)}
        require(observed["bytes"] == record.get("bytes"), f"source byte drift: {name}")
        require(observed["sha256"] == record.get("sha256"), f"source hash drift: {name}")
        verified[name] = observed
    return verified


def vec(value: Iterable[float]) -> np.ndarray:
    array = np.asarray(list(value), dtype=np.float64)
    require(array.shape == (3,) and np.isfinite(array).all(), "expected finite three-vector")
    return array


def unit(value: Iterable[float]) -> np.ndarray:
    array = vec(value)
    magnitude = float(np.linalg.norm(array))
    require(magnitude > EPS, "zero-length direction")
    return array / magnitude


def clean_vector(value: np.ndarray) -> list[float]:
    require(value.shape == (3,) and np.isfinite(value).all(), "non-finite vector")
    return [float(component) for component in value]


def line_primitive(a: np.ndarray, b: np.ndarray, lineage: dict[str, Any]) -> dict[str, Any] | None:
    length = float(np.linalg.norm(b - a))
    if length <= 1.0e-9:
        return None
    return {
        "kind": "line",
        "a_A0_mm": clean_vector(a),
        "b_A0_mm": clean_vector(b),
        "length_mm": length,
        "lineage": lineage,
    }


def arc_primitive(
    center: np.ndarray,
    normal: np.ndarray,
    e1: np.ndarray,
    e2: np.ndarray,
    radius: float,
    start_rad: float,
    sweep_rad: float,
    kind: str,
    lineage: dict[str, Any],
) -> dict[str, Any]:
    require(math.isfinite(radius) and radius > 0.0, "arc radius must be finite and positive")
    require(math.isfinite(start_rad) and math.isfinite(sweep_rad) and abs(sweep_rad) > EPS,
            "arc angles must be finite and nonzero")
    require(abs(float(np.linalg.norm(normal)) - 1.0) <= 1.0e-9, "arc normal is not unit")
    require(abs(float(np.linalg.norm(e1)) - 1.0) <= 1.0e-9, "arc basis e1 is not unit")
    require(abs(float(np.linalg.norm(e2)) - 1.0) <= 1.0e-9, "arc basis e2 is not unit")
    require(abs(float(e1 @ e2)) <= 1.0e-9, "arc bases are not orthogonal")
    return {
        "kind": kind,
        "center_A0_mm": clean_vector(center),
        "normal_A0": clean_vector(normal),
        "basis_e1_A0": clean_vector(e1),
        "basis_e2_A0": clean_vector(e2),
        "radius_mm": float(radius),
        "start_angle_rad": float(start_rad),
        "sweep_angle_rad": float(sweep_rad),
        "length_mm": float(radius * abs(sweep_rad)),
        "lineage": lineage,
    }


def decompose_polyline(section: dict[str, Any], segment_id: str, section_index: int) -> list[dict[str, Any]]:
    points = [vec(point) for point in section.get("points", [])]
    radii = section.get("corner_fillet_radii_mm", [])
    require(len(points) >= 2 and isinstance(radii, list), f"invalid polyline: {segment_id} section {section_index}")
    primitives: list[dict[str, Any]] = []
    cursor = points[0].copy()
    index = 1
    while index < len(points):
        if index < len(points) - 1:
            desired_radius = float(radii[index - 1]) if index - 1 < len(radii) else 54.0
            require(math.isfinite(desired_radius) and desired_radius >= 0.0, "invalid desired fillet radius")
            if desired_radius > 0.0:
                incoming = points[index] - cursor
                outgoing = points[index + 1] - points[index]
                length_in = float(np.linalg.norm(incoming))
                length_out = float(np.linalg.norm(outgoing))
                require(length_in > EPS and length_out > EPS, "degenerate fillet leg")
                u = incoming / length_in
                v = outgoing / length_out
                theta = math.acos(float(np.clip(u @ v, -1.0, 1.0)))
                if theta >= math.radians(1.0):
                    require(theta <= math.radians(179.0), "reversal fillet is forbidden")
                    tangent_length_requested = desired_radius * math.tan(theta / 2.0)
                    tangent_length_limit = 0.98 * min(length_in, length_out)
                    tangent_length_actual = min(tangent_length_requested, tangent_length_limit)
                    actual_radius = tangent_length_actual / math.tan(theta / 2.0)
                    tangent_in = points[index] - u * tangent_length_actual
                    tangent_out = points[index] + v * tangent_length_actual
                    line = line_primitive(
                        cursor,
                        tangent_in,
                        {
                            "source": "polyline_straight_before_fillet",
                            "segment": segment_id,
                            "section": section_index,
                            "corner": index,
                        },
                    )
                    if line is not None:
                        primitives.append(line)
                    normal = unit(np.cross(u, v))
                    center_direction = unit(np.cross(normal, u))
                    center = tangent_in + center_direction * actual_radius
                    radial_start = unit(tangent_in - center)
                    tangent_basis = unit(np.cross(normal, radial_start))
                    start_tangent = tangent_basis
                    end_tangent = -math.sin(theta) * radial_start + math.cos(theta) * tangent_basis
                    primitives.append(
                        arc_primitive(
                            center,
                            normal,
                            radial_start,
                            tangent_basis,
                            actual_radius,
                            0.0,
                            theta,
                            "fillet_arc",
                            {
                                "source": "independent_reproduction_of_frozen_v9f_polyline_fillet",
                                "segment": segment_id,
                                "section": section_index,
                                "corner": index,
                                "desired_radius_mm": desired_radius,
                                "actual_radius_mm": actual_radius,
                                "radius_was_clamped": tangent_length_requested > tangent_length_limit,
                                "tangent_length_requested_mm": tangent_length_requested,
                                "tangent_length_limit_mm": tangent_length_limit,
                                "tangent_length_actual_mm": tangent_length_actual,
                                "available_in_mm": length_in,
                                "available_out_mm": length_out,
                                "turn_angle_rad": theta,
                                "endpoint_start_residual_mm": float(np.linalg.norm(
                                    center + actual_radius * radial_start - tangent_in)),
                                "endpoint_end_residual_mm": float(np.linalg.norm(
                                    center + actual_radius * (
                                        math.cos(theta) * radial_start + math.sin(theta) * tangent_basis
                                    ) - tangent_out)),
                                "start_tangent_residual": float(np.linalg.norm(start_tangent - u)),
                                "end_tangent_residual": float(np.linalg.norm(end_tangent - v)),
                            },
                        )
                    )
                    cursor = tangent_out
                    index += 1
                    continue
        line = line_primitive(
            cursor,
            points[index],
            {
                "source": "polyline_straight",
                "segment": segment_id,
                "section": section_index,
                "target_vertex": index,
            },
        )
        if line is not None:
            primitives.append(line)
        cursor = points[index].copy()
        index += 1
    require(primitives, f"polyline emitted no primitives: {segment_id} section {section_index}")
    return primitives


def decompose_section(section: dict[str, Any], segment_id: str, section_index: int) -> list[dict[str, Any]]:
    kind = section.get("type")
    if kind == "polyline":
        return decompose_polyline(section, segment_id, section_index)
    if kind == "arc":
        return [
            arc_primitive(
                vec(section["center"]),
                vec(section["normal"]),
                vec(section["basis_e1"]),
                vec(section["basis_e2"]),
                float(section["radius_mm"]),
                math.radians(float(section["start_angle_deg"])),
                math.radians(float(section["sweep_deg"])),
                "arc",
                {"source": "frozen_v9f_analytic_arc", "segment": segment_id, "section": section_index},
            )
        ]
    if kind == "helix":
        axis = vec(section["axis"])
        e1 = vec(section["basis_e1"])
        e2 = vec(section["basis_e2"])
        require(abs(float(np.linalg.norm(axis)) - 1.0) <= 1.0e-9, "helix axis is not unit")
        require(abs(float(np.linalg.norm(e1)) - 1.0) <= 1.0e-9, "helix e1 is not unit")
        require(abs(float(np.linalg.norm(e2)) - 1.0) <= 1.0e-9, "helix e2 is not unit")
        require(max(abs(float(axis @ e1)), abs(float(axis @ e2)), abs(float(e1 @ e2))) <= 1.0e-9,
                "helix basis is not orthogonal")
        radius = float(section["radius_mm"])
        pitch = float(section["pitch_mm_per_turn"])
        start = math.radians(float(section["start_angle_deg"]))
        sweep = math.radians(float(section["sweep_deg"]))
        require(radius > 0.0 and all(math.isfinite(value) for value in (radius, pitch, start, sweep)),
                "invalid helix parameters")
        length = abs(sweep) * math.sqrt(radius * radius + (pitch / (2.0 * math.pi)) ** 2)
        return [{
            "kind": "helix",
            "origin_A0_mm": clean_vector(vec(section["origin"])),
            "axis_A0": clean_vector(axis),
            "basis_e1_A0": clean_vector(e1),
            "basis_e2_A0": clean_vector(e2),
            "radius_mm": radius,
            "pitch_mm_per_turn": pitch,
            "start_angle_rad": start,
            "sweep_angle_rad": sweep,
            "length_mm": length,
            "lineage": {"source": "frozen_v9f_analytic_helix", "segment": segment_id, "section": section_index},
        }]
    raise BuildFailure(f"unsupported section type: {segment_id} section {section_index}: {kind}")


def point_on_arc(primitive: dict[str, Any], angle: float) -> np.ndarray:
    center = vec(primitive["center_A0_mm"])
    e1 = vec(primitive["basis_e1_A0"])
    e2 = vec(primitive["basis_e2_A0"])
    return center + float(primitive["radius_mm"]) * (math.cos(angle) * e1 + math.sin(angle) * e2)


def point_on_helix(primitive: dict[str, Any], angle: float) -> np.ndarray:
    origin = vec(primitive["origin_A0_mm"])
    axis = vec(primitive["axis_A0"])
    e1 = vec(primitive["basis_e1_A0"])
    e2 = vec(primitive["basis_e2_A0"])
    radius = float(primitive["radius_mm"])
    start = float(primitive["start_angle_rad"])
    pitch = float(primitive["pitch_mm_per_turn"])
    return (origin + radius * (math.cos(angle) * e1 + math.sin(angle) * e2)
            + axis * (pitch * (angle - start) / (2.0 * math.pi)))


def primitive_endpoints(primitive: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    if primitive["kind"] == "line":
        return vec(primitive["a_A0_mm"]), vec(primitive["b_A0_mm"])
    start = float(primitive["start_angle_rad"])
    end = start + float(primitive["sweep_angle_rad"])
    if primitive["kind"] in ("arc", "fillet_arc"):
        return point_on_arc(primitive, start), point_on_arc(primitive, end)
    if primitive["kind"] == "helix":
        return point_on_helix(primitive, start), point_on_helix(primitive, end)
    raise BuildFailure(f"unknown primitive kind: {primitive['kind']}")


def capsules_for_primitive(
    primitive: dict[str, Any],
    object_id: str,
    section_index: int,
    primitive_index: int,
    primary_host: str,
    alternate_host: str | None,
    frozen_curve_count: int | None,
) -> list[dict[str, Any]]:
    kind = primitive["kind"]
    if kind == "line":
        require(frozen_curve_count is None, "a line primitive cannot carry a frozen curve count")
        a, b = primitive_endpoints(primitive)
        return [{
            "capsule_id": f"{object_id}::S{section_index:02d}::P{primitive_index:03d}::K0000",
            "section_index": section_index,
            "primitive_index": primitive_index,
            "primitive_kind": kind,
            "a_A0_mm": clean_vector(a),
            "b_A0_mm": clean_vector(b),
            "design_radius_mm": DESIGN_RADIUS_MM,
            "effective_radius_mm": DESIGN_RADIUS_MM,
            "curve_arclength_step_mm": float(primitive["length_mm"]),
            "curve_step_limit_applies": False,
            "delta_theta_rad": 0.0,
            "hausdorff_bound_mm": 0.0,
            "hausdorff_formula": "LINE_EXACT_ZERO",
            "effective_radius_formula": "DESIGN_RADIUS_PLUS_HAUSDORFF_BOUND_EXACTLY_ONCE",
            "narrowphase_query_radius_field": "effective_radius_mm",
            "topology_count_authority": "LINE_SINGLE_CAPSULE",
            "primary_host": primary_host,
            "alternate_host": alternate_host,
        }]
    length = float(primitive["length_mm"])
    analytic_count = max(1, int(math.ceil(length / MAX_CURVE_STEP_MM - 1.0e-14)))
    if frozen_curve_count is None:
        count = analytic_count
        topology_authority = "STATIC_ANALYTIC_ARCLENGTH_CEILING"
    else:
        require(isinstance(frozen_curve_count, int) and frozen_curve_count >= analytic_count,
                "frozen curve count is invalid or under-subdivided at q0")
        count = frozen_curve_count
        topology_authority = "J4_SECTION5_FULL_ACCEPTED_Q4_DOMAIN_FROZEN_139"
    step = length / count
    start = float(primitive["start_angle_rad"])
    sweep = float(primitive["sweep_angle_rad"])
    delta = sweep / count
    capsules: list[dict[str, Any]] = []
    for index in range(count):
        angle0 = start + delta * index
        angle1 = start + delta * (index + 1)
        if kind in ("arc", "fillet_arc"):
            a = point_on_arc(primitive, angle0)
            b = point_on_arc(primitive, angle1)
            bound = float(primitive["radius_mm"]) * (1.0 - math.cos(abs(delta) / 2.0))
            formula = "ARC_EXACT_R_TIMES_ONE_MINUS_COS_HALF_DELTA"
        elif kind == "helix":
            a = point_on_helix(primitive, angle0)
            b = point_on_helix(primitive, angle1)
            bound = float(primitive["radius_mm"]) * abs(delta) ** 2 / 8.0
            formula = "HELIX_CONSERVATIVE_R_TIMES_DELTA_SQUARED_OVER_8"
        else:
            raise BuildFailure(f"unsupported curved primitive: {kind}")
        capsules.append({
            "capsule_id": f"{object_id}::S{section_index:02d}::P{primitive_index:03d}::K{index:04d}",
            "section_index": section_index,
            "primitive_index": primitive_index,
            "primitive_kind": kind,
            "a_A0_mm": clean_vector(a),
            "b_A0_mm": clean_vector(b),
            "design_radius_mm": DESIGN_RADIUS_MM,
            "effective_radius_mm": DESIGN_RADIUS_MM + bound,
            "curve_arclength_step_mm": step,
            "curve_step_limit_applies": True,
            "delta_theta_rad": delta,
            "hausdorff_bound_mm": bound,
            "hausdorff_formula": formula,
            "effective_radius_formula": "DESIGN_RADIUS_PLUS_HAUSDORFF_BOUND_EXACTLY_ONCE",
            "narrowphase_query_radius_field": "effective_radius_mm",
            "topology_count_authority": topology_authority,
            "primary_host": primary_host,
            "alternate_host": alternate_host,
        })
    return capsules


def deterministic_npz_bytes(arrays: dict[str, np.ndarray]) -> bytes:
    archive_stream = io.BytesIO()
    with zipfile.ZipFile(archive_stream, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(arrays):
            array_stream = io.BytesIO()
            np.lib.format.write_array(array_stream, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(filename=f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, array_stream.getvalue())
    return archive_stream.getvalue()


def safe_stem(selector: str) -> str:
    return "C_" + "".join(character if character.isalnum() else "_" for character in selector).strip("_")


def validate_registry(contract: dict[str, Any], registry: dict[str, Any]) -> None:
    expected = contract["objects"]
    rows = [row for row in registry.get("objects", []) if row.get("category") == "C"]
    require(len(rows) == len(expected) == 9, "registry C object count is not exactly nine")
    by_id = {row.get("object_id"): row for row in rows}
    require(len(by_id) == 9, "registry C object IDs are duplicated")
    for item in expected:
        row = by_id.get(item["object_id"])
        require(row is not None, f"registry C object missing: {item['object_id']}")
        geometry = row.get("geometry", {})
        require(geometry.get("container_selector") == item["selector"], "registry selector drift")
        require(float(geometry.get("diameter_mm")) == 9.0, "registry nominal diameter drift")
        require(row.get("parent_frame") == item["registry_parent_frame"], "registry parent-frame drift")
        require(geometry.get("runtime_representation") == "CAPSULE_CHAIN_REQUIRED_NOT_PREEMITTED",
                "registry runtime representation is no longer the frozen missing capsule state")


def validate_contract(contract: dict[str, Any], frame_ledger: dict[str, Any]) -> None:
    require(contract.get("schema") == "ROUTE_C_C9_ANALYTIC_CAPSULE_CONTRACT_V1", "contract schema drift")
    numeric = contract.get("numeric_contract", {})
    require(numeric.get("nominal_bundle_od_mm") == 9.0, "nominal OD drift")
    require(numeric.get("design_upper_bundle_od_mm") == 10.0, "design OD drift")
    require(numeric.get("design_centerline_tube_radius_mm") == DESIGN_RADIUS_MM, "design radius drift")
    require(numeric.get("maximum_curve_arclength_step_mm") == MAX_CURVE_STEP_MM, "curve step drift")
    require(numeric.get("p01_channel_clearance_mm_not_a_bundle_radius") == 12.0, "P01 lineage drift")
    require(numeric.get("p11_physical_guide_to_centerline_offset_lineage") == "UNKNOWN", "P11 lineage upgraded")
    query = numeric.get("narrowphase_query_contract", {})
    require(query.get("required_query_radius_field") == "effective_radius_mm", "query-radius field drift")
    require(query.get("effective_radius_rule") ==
            "effective_radius_mm = design_radius_mm + hausdorff_bound_mm", "effective-radius rule drift")
    require(query.get("hausdorff_debit_count") == 1, "Hausdorff debit must occur exactly once")
    require(query.get("separate_clearance_debit_alternative_supported_by_this_package") is False,
            "mixed clearance-debit path was enabled")
    j4_domain = numeric.get("j4_section5_full_q4_discretization", {})
    beta_worst = math.radians(20.0) + (J4_Q4_UPPER_RAD - J4_Q4_LOWER_RAD)
    required_count = math.ceil(J4_ANNULUS_RADIUS_MM * beta_worst / MAX_CURVE_STEP_MM)
    require(abs(float(j4_domain.get("worst_case_beta_rad")) - beta_worst) <= 1.0e-15,
            "J4 worst beta drift")
    require(j4_domain.get("topology_capsule_count") == required_count == J4_SECTION5_TOPOLOGY_COUNT,
            "J4 full-domain topology count drift")
    require(float(j4_domain.get("worst_case_curve_arclength_step_mm")) <= MAX_CURVE_STEP_MM,
            "J4 full-domain step contract exceeds limit")
    objects = contract.get("objects")
    require(isinstance(objects, list) and len(objects) == 9 and contract.get("object_count") == 9,
            "contract object count drift")
    ids = [item.get("object_id") for item in objects]
    selectors = [item.get("selector") for item in objects]
    require(len(set(ids)) == len(set(selectors)) == 9, "contract IDs or selectors duplicated")
    j3 = next(item for item in objects if item["selector"] == "SEG-03_J3_CARRIER_HYBRID_WRAP")
    require(j3.get("continuous_q3_carrier_law") == "UNKNOWN", "J3 continuous law was invented")
    require(j3.get("production_union_acceptance") == "UNKNOWN", "J3 production union was over-authorized")
    j4 = next(item for item in objects if item["selector"] == J4_SELECTOR)
    require(j4["sections"][J4_SECTION5].get("frozen_full_q4_topology_capsule_count") ==
            J4_SECTION5_TOPOLOGY_COUNT, "J4 section-5 frozen topology missing")
    require(frame_ledger.get("centerline_length_unit") == "mm", "centerline unit drift")
    require(frame_ledger.get("runtime_output_length_unit") == "mm", "runtime output unit drift")
    require(frame_ledger.get("j3_motion", {}).get("continuous_q3_carrier_law") == "UNKNOWN",
            "frame ledger J3 law drift")
    require(frame_ledger.get("collision_query_radius_contract", {}).get("required_per_representation_field") ==
            "effective_radius_mm", "frame ledger query-radius drift")
    require(frame_ledger.get("j4_motion", {}).get("section5_full_domain_topology", {}).get("capsule_count") ==
            J4_SECTION5_TOPOLOGY_COUNT, "frame ledger J4 topology drift")


def build_object(
    segment: dict[str, Any],
    object_contract: dict[str, Any],
) -> tuple[dict[str, Any], bytes]:
    selector = object_contract["selector"]
    require(segment.get("id") == selector, f"selector mismatch: {selector}")
    sections = segment.get("sections")
    section_contracts = object_contract.get("sections")
    require(isinstance(sections, list) and isinstance(section_contracts, list), "sections missing")
    require(len(sections) == len(section_contracts), f"section count mismatch: {selector}")
    primitives: list[dict[str, Any]] = []
    capsules: list[dict[str, Any]] = []
    section_metrics: list[dict[str, Any]] = []
    primitive_cursor = 0
    previous_section_end: np.ndarray | None = None
    max_section_gap = 0.0
    for section_index, (section, section_contract) in enumerate(zip(sections, section_contracts, strict=True)):
        require(section_contract["section"] == section_index, "contract section index drift")
        require(section_contract["type"] == section.get("type"), "contract section type drift")
        section_primitives = decompose_section(section, selector, section_index)
        section_capsule_start = len(capsules)
        section_length = 0.0
        first_endpoint, _ = primitive_endpoints(section_primitives[0])
        if previous_section_end is not None:
            max_section_gap = max(max_section_gap, float(np.linalg.norm(first_endpoint - previous_section_end)))
        for local_index, primitive in enumerate(section_primitives):
            global_index = primitive_cursor + local_index
            primitive["primitive_index"] = global_index
            primitive["section_index"] = section_index
            primitive["primary_host"] = section_contract["primary_host"]
            primitive["alternate_host"] = section_contract["alternate_host"]
            primitive["motion"] = section_contract["motion"]
            primitive_capsules = capsules_for_primitive(
                primitive,
                object_contract["object_id"],
                section_index,
                global_index,
                section_contract["primary_host"],
                section_contract["alternate_host"],
                section_contract.get("frozen_full_q4_topology_capsule_count"),
            )
            primitive["capsule_start"] = len(capsules)
            primitive["capsule_count"] = len(primitive_capsules)
            primitives.append(primitive)
            capsules.extend(primitive_capsules)
            section_length += float(primitive["length_mm"])
        _, previous_section_end = primitive_endpoints(section_primitives[-1])
        section_metrics.append({
            "section_index": section_index,
            "source_type": section["type"],
            "primary_host": section_contract["primary_host"],
            "alternate_host": section_contract["alternate_host"],
            "motion": section_contract["motion"],
            "primitive_start": primitive_cursor,
            "primitive_count": len(section_primitives),
            "capsule_start": section_capsule_start,
            "capsule_count": len(capsules) - section_capsule_start,
            "analytic_length_mm": section_length,
        })
        primitive_cursor += len(section_primitives)
    source_length = float(segment["path_length_mm"])
    analytic_length = sum(float(primitive["length_mm"]) for primitive in primitives)
    source_residual = abs(analytic_length - source_length)
    fillets = [primitive for primitive in primitives if primitive["kind"] == "fillet_arc"]
    clamped = [primitive for primitive in fillets if primitive["lineage"]["radius_was_clamped"]]
    curve_capsules = [capsule for capsule in capsules if capsule["curve_step_limit_applies"]]
    max_step = max((float(capsule["curve_arclength_step_mm"]) for capsule in curve_capsules), default=0.0)
    max_bound = max(float(capsule["hausdorff_bound_mm"]) for capsule in capsules)
    max_effective_radius = max(float(capsule["effective_radius_mm"]) for capsule in capsules)
    # V9F stored FreeCAD BRep edge lengths.  Its two helix values differ from
    # the closed-form helix length by 0.000186/0.000416 mm.  The analytic
    # centerline parameters, not that kernel quadrature residue, define this
    # capsule construction; retain and gate the reconciliation explicitly.
    require(source_residual <= SOURCE_BREP_LENGTH_RECONCILIATION_TOL_MM,
            f"analytic/BRep path length mismatch: {selector}: {source_residual}")
    require(max_step <= MAX_CURVE_STEP_MM + 1.0e-12, f"curve step exceeds contract: {selector}")
    require(max_section_gap <= 1.0e-6, f"section endpoint discontinuity: {selector}: {max_section_gap}")
    require(all(float(capsule["design_radius_mm"]) == DESIGN_RADIUS_MM for capsule in capsules),
            f"design radius drift: {selector}")
    require(all(abs(float(capsule["effective_radius_mm"]) -
                    (DESIGN_RADIUS_MM + float(capsule["hausdorff_bound_mm"]))) <= 1.0e-15
                for capsule in capsules), f"effective radius drift: {selector}")
    if selector == J4_SELECTOR:
        section5_capsules = [capsule for capsule in capsules if capsule["section_index"] == J4_SECTION5]
        require(len(section5_capsules) == J4_SECTION5_TOPOLOGY_COUNT,
                "J4 section-5 topology is not frozen to 139 capsules")
    payload = {
        "schema": "ROUTE_C_C9_ANALYTIC_CAPSULE_OBJECT_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "object_id": object_contract["object_id"],
        "selector": selector,
        "lifecycle": "LOGICAL_BUNDLE",
        "authority": "LOCAL_ANALYTIC_COLLISION_CANDIDATE_ONLY__NO_SYSTEM_BINDING_OR_PAIR_CREDIT",
        "frame": "A0 = accepted B601 base_link at q=0",
        "length_unit": "mm",
        "nominal_bundle_od_mm": 9.0,
        "design_upper_bundle_od_mm": 10.0,
        "design_radius_mm": DESIGN_RADIUS_MM,
        "radial_increment_already_included_mm": 0.5,
        "narrowphase_consumer_contract": {
            "required_query_radius_field": "effective_radius_mm",
            "effective_radius_rule": "design_radius_mm + hausdorff_bound_mm exactly once",
            "raw_design_radius_for_curved_capsule": "FORBIDDEN_FAIL_CLOSED",
            "second_hausdorff_debit_or_inflation": "FORBIDDEN_FAIL_CLOSED",
        },
        "section_plan": section_contracts,
        "primitives": primitives,
        "capsules": capsules,
        "metrics": {
            "source_path_length_mm": source_length,
            "analytic_path_length_mm": analytic_length,
            "source_path_length_abs_residual_mm": source_residual,
            "primitive_count": len(primitives),
            "capsule_count": len(capsules),
            "curve_capsule_count": len(curve_capsules),
            "maximum_curve_arclength_step_mm": max_step,
            "maximum_hausdorff_bound_mm": max_bound,
            "maximum_effective_radius_mm": max_effective_radius,
            "section_endpoint_gap_max_mm": max_section_gap,
            "fillet_count": len(fillets),
            "clamped_fillet_count": len(clamped),
            "minimum_actual_fillet_radius_mm": min(
                (float(primitive["radius_mm"]) for primitive in fillets), default=None),
        },
        "section_metrics": section_metrics,
        "p11_physical_guide_to_centerline_offset_lineage": "UNKNOWN",
        "j3_continuous_motion_law": (
            object_contract.get("continuous_q3_carrier_law", "NOT_APPLICABLE")),
        "j3_production_union_acceptance": (
            object_contract.get("production_union_acceptance", "NOT_APPLICABLE")),
        "system_credit": {
            "registry_binding": False,
            "pair_queries": 0,
            "safe_certificates": 0,
            "edges": 0,
            "path": False,
            "release": False,
        },
    }
    max_id_length = max(len(capsule["capsule_id"]) for capsule in capsules)
    arrays = {
        "a_A0_mm": np.asarray([capsule["a_A0_mm"] for capsule in capsules], dtype="<f8"),
        "b_A0_mm": np.asarray([capsule["b_A0_mm"] for capsule in capsules], dtype="<f8"),
        "capsule_id": np.asarray([capsule["capsule_id"] for capsule in capsules], dtype=f"<U{max_id_length}"),
        "curve_arclength_step_mm": np.asarray(
            [capsule["curve_arclength_step_mm"] for capsule in capsules], dtype="<f8"),
        "delta_theta_rad": np.asarray([capsule["delta_theta_rad"] for capsule in capsules], dtype="<f8"),
        "hausdorff_bound_mm": np.asarray(
            [capsule["hausdorff_bound_mm"] for capsule in capsules], dtype="<f8"),
        "design_radius_mm": np.asarray([capsule["design_radius_mm"] for capsule in capsules], dtype="<f8"),
        "effective_radius_mm": np.asarray([capsule["effective_radius_mm"] for capsule in capsules], dtype="<f8"),
        "primitive_index": np.asarray([capsule["primitive_index"] for capsule in capsules], dtype="<i4"),
        "section_index": np.asarray([capsule["section_index"] for capsule in capsules], dtype="<i4"),
    }
    return payload, deterministic_npz_bytes(arrays)


def assemble(output_root: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    source_lock = strict_json(SOURCE_LOCK_PATH)
    contract = strict_json(CONTRACT_PATH)
    frame_ledger = strict_json(FRAME_LEDGER_PATH)
    verified_sources = verify_sources(source_lock)
    validate_contract(contract, frame_ledger)
    root = workspace_root()
    centerline = strict_json(root / verified_sources["v9f_centerline"]["path"])
    registry = strict_json(root / verified_sources["current_m01_registry"]["path"])
    validate_registry(contract, registry)
    require(centerline.get("schema") == "B601_ROUTE_C_HARNESS_CENTERLINE_V9F", "centerline schema drift")
    center_segments = centerline.get("segments")
    require(isinstance(center_segments, list) and len(center_segments) == 9, "centerline must contain nine segments")
    by_selector = {segment.get("id"): segment for segment in center_segments}
    require(len(by_selector) == 9, "centerline selectors duplicated")

    files: dict[str, bytes] = {}
    index_rows: list[dict[str, Any]] = []
    total_capsules = 0
    total_primitives = 0
    max_hausdorff = 0.0
    max_effective_radius = 0.0
    max_curve_step = 0.0
    max_path_residual = 0.0
    max_section_gap = 0.0
    clamped_fillet_count = 0
    for object_contract in contract["objects"]:
        selector = object_contract["selector"]
        require(selector in by_selector, f"centerline selector missing: {selector}")
        payload, npz_bytes = build_object(by_selector[selector], object_contract)
        stem = safe_stem(selector)
        json_rel = RUNTIME_REL / f"{stem}_A0_MM_V1.json"
        npz_rel = RUNTIME_REL / f"{stem}_A0_MM_V1.npz"
        json_bytes = stable_json_bytes(payload)
        files[json_rel.as_posix()] = json_bytes
        files[npz_rel.as_posix()] = npz_bytes
        metrics = payload["metrics"]
        total_capsules += int(metrics["capsule_count"])
        total_primitives += int(metrics["primitive_count"])
        max_hausdorff = max(max_hausdorff, float(metrics["maximum_hausdorff_bound_mm"]))
        max_effective_radius = max(max_effective_radius, float(metrics["maximum_effective_radius_mm"]))
        max_curve_step = max(max_curve_step, float(metrics["maximum_curve_arclength_step_mm"]))
        max_path_residual = max(max_path_residual, float(metrics["source_path_length_abs_residual_mm"]))
        max_section_gap = max(max_section_gap, float(metrics["section_endpoint_gap_max_mm"]))
        clamped_fillet_count += int(metrics["clamped_fillet_count"])
        index_rows.append({
            "object_id": payload["object_id"],
            "selector": selector,
            "registry_parent_frame": object_contract["registry_parent_frame"],
            "json": {"path": json_rel.as_posix(), "bytes": len(json_bytes), "sha256": sha256_bytes(json_bytes)},
            "npz": {"path": npz_rel.as_posix(), "bytes": len(npz_bytes), "sha256": sha256_bytes(npz_bytes)},
            "primitive_count": metrics["primitive_count"],
            "capsule_count": metrics["capsule_count"],
            "maximum_hausdorff_bound_mm": metrics["maximum_hausdorff_bound_mm"],
            "maximum_effective_radius_mm": metrics["maximum_effective_radius_mm"],
            "maximum_curve_arclength_step_mm": metrics["maximum_curve_arclength_step_mm"],
            "j3_continuous_motion_law": payload["j3_continuous_motion_law"],
            "j3_production_union_acceptance": payload["j3_production_union_acceptance"],
        })

    index = {
        "schema": "ROUTE_C_C9_CAPSULE_INDEX_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "scope": "NINE_LOCAL_A0_MM_ANALYTIC_CAPSULE_CANDIDATES",
        "object_count": len(index_rows),
        "objects": index_rows,
        "aggregate_metrics": {
            "primitive_count": total_primitives,
            "capsule_count": total_capsules,
            "maximum_hausdorff_bound_mm": max_hausdorff,
            "maximum_effective_radius_mm": max_effective_radius,
            "maximum_curve_arclength_step_mm": max_curve_step,
            "maximum_source_path_length_abs_residual_mm": max_path_residual,
            "maximum_section_endpoint_gap_mm": max_section_gap,
            "clamped_fillet_count": clamped_fillet_count,
            "j4_section5_full_q4_topology_capsule_count": J4_SECTION5_TOPOLOGY_COUNT,
            "j4_full_domain_worst_curve_arclength_step_mm_contract":
                contract["numeric_contract"]["j4_section5_full_q4_discretization"]
                ["worst_case_curve_arclength_step_mm"],
            "j4_full_domain_worst_hausdorff_bound_mm_contract":
                contract["numeric_contract"]["j4_section5_full_q4_discretization"]
                ["worst_case_hausdorff_bound_mm"],
        },
        "numeric_authority": {
            "nominal_bundle_od_mm": 9.0,
            "design_upper_bundle_od_mm": 10.0,
            "design_radius_mm": DESIGN_RADIUS_MM,
            "required_query_radius_field": "effective_radius_mm",
            "effective_radius_rule": "design_radius_mm + hausdorff_bound_mm exactly once",
            "raw_design_radius_query_for_curved_capsule_forbidden": True,
            "second_hausdorff_debit_forbidden": True,
            "double_counted_radial_increment_mm": 0.0,
            "p11_physical_guide_to_centerline_offset_lineage": "UNKNOWN",
        },
        "j3": {
            "continuous_q3_carrier_law": "UNKNOWN",
            "production_union_acceptance": "UNKNOWN",
            "local_output": "PRIMARY_AND_ALTERNATE_HOST_REPRESENTATIONS_REQUIRED_AT_POSE_TIME",
        },
        "package_authority_boundary": {
            "registry_rows_added_by_package": 0,
            "pair_queries_executed_by_package": 0,
            "safe_certificates_issued_by_package": 0,
            "edges_certified_by_package": 0,
            "path_search_executed_by_package": False,
            "release_credit_claimed_by_package": False,
            "current_system_truth_must_be_read_from_hash_pinned_external_gates": True,
        },
    }
    index_bytes = stable_json_bytes(index)
    files[INDEX_REL.as_posix()] = index_bytes
    receipt = {
        "schema": "ROUTE_C_C9_CAPSULE_BUILD_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "builder_execution_class": "PURE_ANALYTIC_JSON_INPUT__NO_V9F_SOURCE_IMPORT_TRACE_OR_EXECUTION",
        "source_lock": file_record(SOURCE_LOCK_PATH, workspace_root()),
        "contract": file_record(CONTRACT_PATH, workspace_root()),
        "frame_unit_motion_ledger": file_record(FRAME_LEDGER_PATH, workspace_root()),
        "verified_source_count": len(verified_sources),
        "verified_sources": verified_sources,
        "outputs": {
            "runtime_json": 9,
            "runtime_npz": 9,
            "index": {"path": INDEX_REL.as_posix(), "bytes": len(index_bytes), "sha256": sha256_bytes(index_bytes)},
            "deterministic_core_count_including_receipt": 20,
        },
        "aggregate_metrics": index["aggregate_metrics"],
        "checks": {
            "exact_registry_C_object_set_9_of_9": True,
            "centerline_segments_9_of_9": True,
            "design_radius_exactly_5_mm": True,
            "effective_radius_equals_design_plus_Hausdorff_once": True,
            "raw_design_radius_query_for_curved_capsule_forbidden": True,
            "radial_increment_and_Hausdorff_not_double_counted": True,
            "maximum_curve_step_not_over_1p5_mm": max_curve_step <= MAX_CURVE_STEP_MM + 1.0e-12,
            "J4_section5_full_q4_topology_frozen_to_139": True,
            "analytic_path_length_reconciles_with_frozen_BRep_length_within_1um": (
                max_path_residual <= SOURCE_BREP_LENGTH_RECONCILIATION_TOL_MM),
            "section_endpoints_continuous": max_section_gap <= 1.0e-6,
            "P11_to_centerline_offset_lineage_unknown": True,
            "J3_continuous_law_unknown": True,
            "J3_production_union_acceptance_unknown": True,
            "current_system_credit_zero": True,
        },
        "maximum_legal_claim": "NINE_LOCAL_A0_MM_ANALYTIC_CAPSULE_CHAIN_CANDIDATES_BUILT__POSE_AND_INDEPENDENT_VALIDATION_PENDING",
        "verdict": "C9_ANALYTIC_CAPSULE_BUILD_9_OF_9_PASS__NO_CURRENT_PAIR_EDGE_PATH_OR_RELEASE_CREDIT__TMG4_HOLD",
    }
    receipt_bytes = stable_json_bytes(receipt)
    files[BUILD_RECEIPT_REL.as_posix()] = receipt_bytes
    require(len(files) == 20, "deterministic core must contain exactly twenty files")
    return files, receipt


def write_files(output_root: Path, files: dict[str, bytes]) -> None:
    for relative, data in sorted(files.items()):
        atomic_write(output_root / relative, data)


def compare_files(output_root: Path, files: dict[str, bytes]) -> None:
    for relative, expected in sorted(files.items()):
        path = output_root / relative
        require(path.is_file(), f"built artifact missing: {path}")
        observed = path.read_bytes()
        require(observed == expected, f"built artifact drift: {relative}")
    actual_runtime = {
        path.relative_to(output_root).as_posix()
        for path in (output_root / RUNTIME_REL).glob("*") if path.is_file()
    }
    expected_runtime = {relative for relative in files if relative.startswith(RUNTIME_REL.as_posix() + "/")}
    require(actual_runtime == expected_runtime, "runtime directory has missing or extra files")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output-root", type=Path, default=PACKAGE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    if args.write:
        files, receipt = assemble(output_root)
        write_files(output_root, files)
        mode = "write"
    else:
        with tempfile.TemporaryDirectory(prefix="c9_capsule_check_") as temporary:
            temporary_root = Path(temporary)
            files, receipt = assemble(temporary_root)
            write_files(temporary_root, files)
            compare_files(output_root, files)
        mode = "check"
    metrics = receipt["aggregate_metrics"]
    print(json.dumps({
        "status": "PASS",
        "mode": mode,
        "objects": 9,
        "primitives": metrics["primitive_count"],
        "capsules": metrics["capsule_count"],
        "maximum_hausdorff_bound_mm": metrics["maximum_hausdorff_bound_mm"],
        "maximum_curve_arclength_step_mm": metrics["maximum_curve_arclength_step_mm"],
        "core_artifacts": 20,
        "j3_production_union_acceptance": "UNKNOWN",
        "system_pair_credit": 0,
        "TMG4": "HOLD",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
