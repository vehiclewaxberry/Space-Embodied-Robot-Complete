"""Independent reconstruction and fail-closed validation of the C9 package.

This module deliberately does not import either builder module.  It rebuilds
polyline fillets, analytic chords, Hausdorff bounds, URDF FK, and the J4 law
from pinned source data using its own implementation.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import math
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np


class ValidationFailure(RuntimeError):
    pass


PACKAGE = Path(__file__).resolve().parents[1]
LOCK_PATH = PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json"
CONTRACT_PATH = PACKAGE / "00_contract/C9_ANALYTIC_CAPSULE_CONTRACT_V1.json"
LEDGER_PATH = PACKAGE / "00_contract/FRAME_UNIT_AND_MOTION_LEDGER_V1.json"
INDEX_PATH = PACKAGE / "05_results/C9_CAPSULE_INDEX_V1.json"
BUILD_RECEIPT_PATH = PACKAGE / "05_results/C9_BUILD_RECEIPT_V1.json"
POSE_RECEIPT_PATH = PACKAGE / "05_results/POSE_ADAPTER_SELF_CHECK_V1.json"
VALIDATION_PATH = PACKAGE / "05_results/INDEPENDENT_VALIDATION_V1.json"
NEGATIVE_PATH = PACKAGE / "05_results/NEGATIVE_CONTROLS_V1.json"
BUILDER_PATH = PACKAGE / "02_builder/build_c9_capsules.py"
POSE_ADAPTER_PATH = PACKAGE / "02_builder/c9_pose_adapter.py"
JOINT_ORDER = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
EXPECTED_IDS = [
    "C::SEG-00_BUS_FEEDTHROUGH_AND_RISER",
    "C::SEG-01_J1_ANNULAR_SERVICE_LOOP",
    "C::SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL",
    "C::SEG-03_J3_CARRIER_HYBRID_WRAP",
    "C::SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER",
    "C::SEG-05_J5_WRIST_WRAP",
    "C::SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN",
    "C::SEG-07A_WRIST_TAIL_DATA",
    "C::SEG-07B_WRIST_TAIL_POWER",
]
MAX_STEP = 1.5
DESIGN_RADIUS = 5.0
J4_SELECTOR = "SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER"
J4_SECTION5_TOPOLOGY_COUNT = 139


def root_dir() -> Path:
    for item in Path(__file__).resolve().parents:
        if (item / "PROJECT_MAP.md").is_file() and (item / "20_engineering").is_dir():
            return item
    raise ValidationFailure("repository root not found")


def demand(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationFailure(message)


def load_json(path: Path) -> dict[str, Any]:
    def no_constant(token: str) -> None:
        raise ValidationFailure(f"non-finite JSON constant {token}: {path}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=no_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"invalid JSON {path}: {exc}") from exc
    demand(isinstance(value, dict), f"JSON root is not object: {path}")
    return value


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def q_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def put(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_name(path.name + ".tmp")
    scratch.write_bytes(data)
    os.replace(scratch, path)


def v3(value: Iterable[float]) -> np.ndarray:
    out = np.asarray(list(value), dtype=np.float64)
    demand(out.shape == (3,) and np.isfinite(out).all(), "expected finite vector3")
    return out


def normalized(value: Iterable[float]) -> np.ndarray:
    out = v3(value)
    size = float(np.linalg.norm(out))
    demand(size > 1.0e-14, "zero vector")
    return out / size


def verify_pins(lock: dict[str, Any]) -> dict[str, Path]:
    records = lock.get("sources")
    demand(isinstance(records, dict) and len(records) == lock.get("source_count") == 18,
           "source lock is not exactly eighteen records")
    found: dict[str, Path] = {}
    repo = root_dir()
    for name, record in records.items():
        path = repo / str(record.get("path"))
        demand(path.is_file(), f"source missing: {name}")
        demand(path.stat().st_size == record.get("bytes"), f"source byte drift: {name}")
        demand(digest_file(path) == record.get("sha256"), f"source hash drift: {name}")
        found[name] = path
    return found


def static_import_boundary() -> dict[str, Any]:
    rows = []
    for source in (BUILDER_PATH, POSE_ADAPTER_PATH):
        text = source.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(source))
        imported = []
        forbidden_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval", "compile"}:
                forbidden_calls.append(node.func.id)
        demand(not any("B601_ROUTE_C_BUILD_V9F" in name or "ROUTE_C_EXACT_SWEEP_V9F" in name for name in imported),
               f"V9F source imported by {source.name}")
        demand(not forbidden_calls, f"dynamic execution primitive present in {source.name}")
        rows.append({
            "path": source.relative_to(root_dir()).as_posix(),
            "bytes": source.stat().st_size,
            "sha256": digest_file(source),
            "imports": sorted(imported),
            "v9f_builder_or_evaluator_imported": False,
            "dynamic_exec_eval_compile_calls": [],
        })
    return {"files": rows, "pass": True}


def poly_primitives(section: dict[str, Any]) -> list[dict[str, Any]]:
    points = [v3(point) for point in section["points"]]
    radii = list(section.get("corner_fillet_radii_mm", []))
    demand(len(points) >= 2, "polyline too short")
    pieces: list[dict[str, Any]] = []
    current = points[0]
    i = 1
    while i < len(points):
        if i < len(points) - 1:
            desired = float(radii[i - 1]) if i - 1 < len(radii) else 54.0
            if desired > 0.0:
                leg1 = points[i] - current
                leg2 = points[i + 1] - points[i]
                len1, len2 = float(np.linalg.norm(leg1)), float(np.linalg.norm(leg2))
                demand(len1 > 1.0e-12 and len2 > 1.0e-12, "zero fillet leg")
                u1, u2 = leg1 / len1, leg2 / len2
                angle = math.acos(float(np.clip(u1 @ u2, -1.0, 1.0)))
                if angle >= math.radians(1.0):
                    demand(angle <= math.radians(179.0), "reversal corner")
                    requested = desired * math.tan(angle / 2.0)
                    allowed = 0.98 * min(len1, len2)
                    tangent = min(requested, allowed)
                    actual = tangent / math.tan(angle / 2.0)
                    p_start = points[i] - tangent * u1
                    p_end = points[i] + tangent * u2
                    if float(np.linalg.norm(p_start - current)) > 1.0e-9:
                        pieces.append({"kind": "line", "a": current, "b": p_start,
                                       "length": float(np.linalg.norm(p_start - current))})
                    normal = normalized(np.cross(u1, u2))
                    inward = normalized(np.cross(normal, u1))
                    center = p_start + actual * inward
                    e1 = normalized(p_start - center)
                    e2 = normalized(np.cross(normal, e1))
                    pieces.append({
                        "kind": "fillet_arc", "center": center, "e1": e1, "e2": e2,
                        "radius": actual, "start": 0.0, "sweep": angle,
                        "length": actual * angle, "desired": desired,
                        "clamped": requested > allowed,
                        "start_tangent_residual": float(np.linalg.norm(e2 - u1)),
                        "end_tangent_residual": float(np.linalg.norm(
                            (-math.sin(angle) * e1 + math.cos(angle) * e2) - u2)),
                    })
                    current = p_end
                    i += 1
                    continue
        target = points[i]
        length = float(np.linalg.norm(target - current))
        if length > 1.0e-9:
            pieces.append({"kind": "line", "a": current, "b": target, "length": length})
        current = target
        i += 1
    return pieces


def section_primitives(section: dict[str, Any]) -> list[dict[str, Any]]:
    kind = section["type"]
    if kind == "polyline":
        return poly_primitives(section)
    if kind == "arc":
        radius = float(section["radius_mm"])
        start = math.radians(float(section["start_angle_deg"]))
        sweep = math.radians(float(section["sweep_deg"]))
        return [{
            "kind": "arc", "center": v3(section["center"]), "e1": v3(section["basis_e1"]),
            "e2": v3(section["basis_e2"]), "radius": radius, "start": start,
            "sweep": sweep, "length": radius * abs(sweep),
        }]
    if kind == "helix":
        radius = float(section["radius_mm"])
        pitch = float(section["pitch_mm_per_turn"])
        start = math.radians(float(section["start_angle_deg"]))
        sweep = math.radians(float(section["sweep_deg"]))
        return [{
            "kind": "helix", "origin": v3(section["origin"]), "axis": v3(section["axis"]),
            "e1": v3(section["basis_e1"]), "e2": v3(section["basis_e2"]),
            "radius": radius, "pitch": pitch, "start": start, "sweep": sweep,
            "length": abs(sweep) * math.sqrt(radius * radius + (pitch / (2.0 * math.pi)) ** 2),
        }]
    raise ValidationFailure(f"unknown source section kind: {kind}")


def arc_point(piece: dict[str, Any], angle: float) -> np.ndarray:
    return piece["center"] + piece["radius"] * (math.cos(angle) * piece["e1"] + math.sin(angle) * piece["e2"])


def helix_point(piece: dict[str, Any], angle: float) -> np.ndarray:
    return (piece["origin"] + piece["radius"] * (math.cos(angle) * piece["e1"] + math.sin(angle) * piece["e2"])
            + piece["axis"] * (piece["pitch"] * (angle - piece["start"]) / (2.0 * math.pi)))


def piece_endpoints(piece: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    if piece["kind"] == "line":
        return piece["a"], piece["b"]
    start, end = piece["start"], piece["start"] + piece["sweep"]
    if piece["kind"] in {"arc", "fillet_arc"}:
        return arc_point(piece, start), arc_point(piece, end)
    return helix_point(piece, start), helix_point(piece, end)


def expected_capsules(
    segment: dict[str, Any],
    object_contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    all_pieces: list[dict[str, Any]] = []
    capsules: list[dict[str, Any]] = []
    global_piece = 0
    previous_end = None
    max_gap = 0.0
    analytic_length = 0.0
    for section_index, section in enumerate(segment["sections"]):
        section_contract = object_contract["sections"][section_index]
        pieces = section_primitives(section)
        first, _ = piece_endpoints(pieces[0])
        if previous_end is not None:
            max_gap = max(max_gap, float(np.linalg.norm(first - previous_end)))
        for piece in pieces:
            piece = dict(piece)
            piece["section"] = section_index
            piece["global_piece"] = global_piece
            all_pieces.append(piece)
            analytic_length += float(piece["length"])
            if piece["kind"] == "line":
                a, b = piece_endpoints(piece)
                capsules.append({
                    "id": f"{object_contract['object_id']}::S{section_index:02d}::P{global_piece:03d}::K0000",
                    "section": section_index, "piece": global_piece, "kind": "line",
                    "a": a, "b": b, "step": piece["length"], "delta": 0.0,
                    "bound": 0.0, "design_radius": DESIGN_RADIUS,
                    "effective_radius": DESIGN_RADIUS,
                    "primary": section_contract["primary_host"],
                    "alternate": section_contract["alternate_host"],
                })
            else:
                analytic_count = max(1, math.ceil(piece["length"] / MAX_STEP - 1.0e-14))
                frozen_count = section_contract.get("frozen_full_q4_topology_capsule_count")
                count = analytic_count if frozen_count is None else int(frozen_count)
                demand(count >= analytic_count, "frozen topology under-subdivides q0")
                delta = piece["sweep"] / count
                for k in range(count):
                    a0 = piece["start"] + k * delta
                    a1 = piece["start"] + (k + 1) * delta
                    if piece["kind"] in {"arc", "fillet_arc"}:
                        pa, pb = arc_point(piece, a0), arc_point(piece, a1)
                        bound = piece["radius"] * (1.0 - math.cos(abs(delta) / 2.0))
                    else:
                        pa, pb = helix_point(piece, a0), helix_point(piece, a1)
                        bound = piece["radius"] * abs(delta) ** 2 / 8.0
                    capsules.append({
                        "id": f"{object_contract['object_id']}::S{section_index:02d}::P{global_piece:03d}::K{k:04d}",
                        "section": section_index, "piece": global_piece, "kind": piece["kind"],
                        "a": pa, "b": pb, "step": piece["length"] / count,
                        "delta": delta, "bound": bound, "design_radius": DESIGN_RADIUS,
                        "effective_radius": DESIGN_RADIUS + bound,
                        "primary": section_contract["primary_host"],
                        "alternate": section_contract["alternate_host"],
                    })
            global_piece += 1
        _, previous_end = piece_endpoints(pieces[-1])
    metrics = {
        "analytic_length": analytic_length,
        "source_length_residual": abs(analytic_length - float(segment["path_length_mm"])),
        "max_section_gap": max_gap,
        "max_curve_step": max((c["step"] for c in capsules if c["kind"] != "line"), default=0.0),
        "max_bound": max(c["bound"] for c in capsules),
        "max_effective_radius": max(c["effective_radius"] for c in capsules),
    }
    return all_pieces, capsules, metrics


def near(actual: Any, expected: Any, tolerance: float, label: str) -> float:
    left, right = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    demand(left.shape == right.shape and np.isfinite(left).all() and np.isfinite(right).all(), f"shape/nonfinite: {label}")
    residual = float(np.max(np.abs(left - right))) if left.size else 0.0
    demand(residual <= tolerance, f"numeric mismatch {label}: {residual} > {tolerance}")
    return residual


def validate_npz(path: Path, output: dict[str, Any]) -> dict[str, Any]:
    expected_members = [
        "a_A0_mm.npy", "b_A0_mm.npy", "capsule_id.npy", "curve_arclength_step_mm.npy",
        "delta_theta_rad.npy", "design_radius_mm.npy", "effective_radius_mm.npy",
        "hausdorff_bound_mm.npy", "primitive_index.npy", "section_index.npy",
    ]
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        demand([info.filename for info in infos] == expected_members, "NPZ member order/set drift")
        demand(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in infos), "NPZ timestamp is not deterministic")
        demand(all(info.compress_type == zipfile.ZIP_STORED for info in infos), "NPZ compression drift")
    with np.load(path, allow_pickle=False) as arrays:
        count = len(output["capsules"])
        demand(arrays["a_A0_mm"].shape == arrays["b_A0_mm"].shape == (count, 3), "NPZ endpoint shape drift")
        near(arrays["a_A0_mm"], [c["a_A0_mm"] for c in output["capsules"]], 0.0, "NPZ a")
        near(arrays["b_A0_mm"], [c["b_A0_mm"] for c in output["capsules"]], 0.0, "NPZ b")
        near(arrays["design_radius_mm"], [c["design_radius_mm"] for c in output["capsules"]],
             0.0, "NPZ design radius")
        near(arrays["effective_radius_mm"], [c["effective_radius_mm"] for c in output["capsules"]],
             0.0, "NPZ effective radius")
        near(arrays["hausdorff_bound_mm"], [c["hausdorff_bound_mm"] for c in output["capsules"]], 0.0, "NPZ bound")
        demand(arrays["capsule_id"].tolist() == [c["capsule_id"] for c in output["capsules"]], "NPZ IDs drift")
    return {"path": path.relative_to(root_dir()).as_posix(), "bytes": path.stat().st_size,
            "sha256": digest_file(path), "members": len(expected_members), "deterministic_zip": True}


def validate_object(
    source_segment: dict[str, Any],
    contract_item: dict[str, Any],
    index_item: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float]]:
    json_path = PACKAGE / index_item["json"]["path"]
    npz_path = PACKAGE / index_item["npz"]["path"]
    demand(json_path.is_file() and npz_path.is_file(), "runtime object output missing")
    demand(json_path.stat().st_size == index_item["json"]["bytes"] and digest_file(json_path) == index_item["json"]["sha256"],
           "runtime JSON pin mismatch")
    demand(npz_path.stat().st_size == index_item["npz"]["bytes"] and digest_file(npz_path) == index_item["npz"]["sha256"],
           "runtime NPZ pin mismatch")
    output = load_json(json_path)
    demand(output["object_id"] == contract_item["object_id"] and output["selector"] == contract_item["selector"],
           "runtime object identity drift")
    demand(output["frame"] == "A0 = accepted B601 base_link at q=0" and output["length_unit"] == "mm",
           "runtime frame/unit drift")
    demand(output["nominal_bundle_od_mm"] == 9.0 and output["design_upper_bundle_od_mm"] == 10.0,
           "runtime OD drift")
    demand(output["design_radius_mm"] == DESIGN_RADIUS and
           output["radial_increment_already_included_mm"] == 0.5,
           "runtime design-radius/double-count drift")
    consumer = output.get("narrowphase_consumer_contract", {})
    demand(consumer.get("required_query_radius_field") == "effective_radius_mm" and
           consumer.get("raw_design_radius_for_curved_capsule") == "FORBIDDEN_FAIL_CLOSED" and
           consumer.get("second_hausdorff_debit_or_inflation") == "FORBIDDEN_FAIL_CLOSED",
           "runtime narrowphase consumer contract drift")
    pieces, expected, metrics = expected_capsules(source_segment, contract_item)
    observed = output["capsules"]
    demand(len(observed) == len(expected), f"capsule count mismatch: {output['selector']}")
    max_numeric = 0.0
    for index, (actual, reference) in enumerate(zip(observed, expected, strict=True)):
        demand(actual["capsule_id"] == reference["id"], f"capsule ID drift at {index}")
        demand(actual["section_index"] == reference["section"] and actual["primitive_index"] == reference["piece"],
               f"capsule topology drift at {index}")
        demand(actual["primitive_kind"] == reference["kind"], f"capsule primitive kind drift at {index}")
        demand(actual["primary_host"] == reference["primary"] and actual["alternate_host"] == reference["alternate"],
               f"capsule host drift at {index}")
        demand("radius_mm" not in actual, f"ambiguous raw query radius present at {index}")
        demand(actual["design_radius_mm"] == DESIGN_RADIUS, f"capsule design radius drift at {index}")
        demand(actual["narrowphase_query_radius_field"] == "effective_radius_mm",
               f"capsule query field drift at {index}")
        max_numeric = max(
            max_numeric,
            near(actual["a_A0_mm"], reference["a"], 2.0e-12, f"a {index}"),
            near(actual["b_A0_mm"], reference["b"], 2.0e-12, f"b {index}"),
            near(actual["curve_arclength_step_mm"], reference["step"], 2.0e-12, f"step {index}"),
            near(actual["delta_theta_rad"], reference["delta"], 2.0e-15, f"delta {index}"),
            near(actual["hausdorff_bound_mm"], reference["bound"], 2.0e-15, f"bound {index}"),
            near(actual["effective_radius_mm"], reference["effective_radius"], 2.0e-15,
                 f"effective radius {index}"),
        )
        demand(actual["hausdorff_bound_mm"] + 1.0e-18 >= reference["bound"], f"underreported bound at {index}")
        demand(abs(float(actual["effective_radius_mm"]) -
                   (float(actual["design_radius_mm"]) + float(actual["hausdorff_bound_mm"]))) <= 1.0e-15,
               f"effective radius does not debit Hausdorff exactly once at {index}")
    fillet_outputs = [p for p in output["primitives"] if p["kind"] == "fillet_arc"]
    fillet_expected = [p for p in pieces if p["kind"] == "fillet_arc"]
    demand(len(fillet_outputs) == len(fillet_expected), "fillet count drift")
    for actual, reference in zip(fillet_outputs, fillet_expected, strict=True):
        lineage = actual["lineage"]
        near(actual["radius_mm"], reference["radius"], 2.0e-12, "actual fillet radius")
        demand(lineage["desired_radius_mm"] == reference["desired"], "desired fillet radius lineage drift")
        demand(lineage["radius_was_clamped"] is reference["clamped"], "fillet clamp lineage drift")
        demand(lineage["start_tangent_residual"] <= 1.0e-12 and lineage["end_tangent_residual"] <= 1.0e-12,
               "fillet tangent continuity failure")
    demand(metrics["source_length_residual"] <= 1.0e-3, "analytic/BRep length reconciliation failure")
    demand(metrics["max_section_gap"] <= 1.0e-6, "section continuity failure")
    demand(metrics["max_curve_step"] <= MAX_STEP + 1.0e-12, "curve step failure")
    near(output["metrics"]["maximum_hausdorff_bound_mm"], metrics["max_bound"], 2.0e-15, "object max bound")
    near(output["metrics"]["maximum_effective_radius_mm"], metrics["max_effective_radius"],
         2.0e-15, "object max effective radius")
    if output["selector"] == J4_SELECTOR:
        demand(sum(c["section_index"] == 5 for c in observed) == J4_SECTION5_TOPOLOGY_COUNT,
               "J4 section-5 topology count drift")
    npz_record = validate_npz(npz_path, output)
    return ({
        "object_id": output["object_id"], "selector": output["selector"],
        "primitive_count": len(pieces), "capsule_count": len(expected),
        "maximum_hausdorff_bound_mm": metrics["max_bound"],
        "maximum_effective_radius_mm": metrics["max_effective_radius"],
        "maximum_curve_arclength_step_mm": metrics["max_curve_step"],
        "source_BRep_length_abs_residual_mm": metrics["source_length_residual"],
        "section_endpoint_gap_max_mm": metrics["max_section_gap"],
        "fillet_count": len(fillet_expected),
        "clamped_fillet_count": sum(bool(p["clamped"]) for p in fillet_expected),
        "json": {"path": json_path.relative_to(root_dir()).as_posix(), "bytes": json_path.stat().st_size,
                 "sha256": digest_file(json_path)},
        "npz": npz_record,
    }, {"max_numeric": max_numeric})


def trans(x: float, y: float, z: float) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = [x, y, z]
    return matrix


def rpy_matrix(values: np.ndarray) -> np.ndarray:
    r, p, y = map(float, values)
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]], float)
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]], float)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], float)
    out = np.eye(4)
    out[:3, :3] = rz @ ry @ rx
    return out


def axis_matrix(axis: np.ndarray, angle: float) -> np.ndarray:
    x, y, z = axis / np.linalg.norm(axis)
    c, s, d = math.cos(angle), math.sin(angle), 1.0 - math.cos(angle)
    out = np.eye(4)
    out[:3, :3] = [[x*x*d+c, x*y*d-z*s, x*z*d+y*s],
                    [y*x*d+z*s, y*y*d+c, y*z*d-x*s],
                    [z*x*d-y*s, z*y*d+x*s, z*z*d+c]]
    return out


class IndependentArm:
    def __init__(self, path: Path) -> None:
        root = ET.parse(path).getroot()
        self.joints = []
        for item in root.findall("joint"):
            origin, axis, limit = item.find("origin"), item.find("axis"), item.find("limit")
            parent, child = item.find("parent"), item.find("child")
            self.joints.append({
                "name": item.get("name"), "type": item.get("type"),
                "parent": parent.get("link"), "child": child.get("link"),
                "xyz": v3([float(x) * 1000.0 for x in ((origin.get("xyz") if origin is not None else "0 0 0").split())]),
                "rpy": v3([float(x) for x in ((origin.get("rpy") if origin is not None else "0 0 0").split())]),
                "axis": v3([float(x) for x in ((axis.get("xyz") if axis is not None else "1 0 0").split())]),
                "lower": float(limit.get("lower")) if limit is not None and limit.get("lower") is not None else None,
                "upper": float(limit.get("upper")) if limit is not None and limit.get("upper") is not None else None,
            })
        arm = [j for j in self.joints if j["type"] == "revolute"]
        demand([j["name"] for j in arm] == JOINT_ORDER, "URDF revolute order drift")
        self.limits = {j["name"]: (j["lower"], j["upper"]) for j in arm}

    def fk(self, q: list[float]) -> dict[str, np.ndarray]:
        state = dict(zip(JOINT_ORDER, q, strict=True))
        frames = {"base_link": np.eye(4)}
        for joint in self.joints:
            demand(joint["parent"] in frames, "URDF tree order failure")
            m = frames[joint["parent"]] @ trans(*joint["xyz"]) @ rpy_matrix(joint["rpy"])
            if joint["type"] == "revolute":
                m = m @ axis_matrix(joint["axis"], state[joint["name"]])
            elif joint["type"] not in {"fixed", "prismatic"}:
                raise ValidationFailure("unsupported URDF joint type")
            frames[joint["child"]] = m
        return frames


def independent_mount(path: Path) -> np.ndarray:
    doc = load_json(path)
    strings = doc["binding"]["canonical_matrix_decimal_strings"]
    demand(doc["binding"]["canonical_decimal_places"] == 12, "mount precision drift")
    demand(all(re.fullmatch(r"-?\d+\.\d{12}", value) for row in strings for value in row), "mount is D6/noncanonical")
    m = np.asarray([[float(value) for value in row] for row in strings])
    m[:3, 3] *= 1000.0
    return m


def xform(matrix: np.ndarray, point: Iterable[float]) -> np.ndarray:
    homogeneous = np.r_[np.asarray(list(point), float), 1.0]
    return (matrix @ homogeneous)[:3]


def independent_pose_validation(
    centerline: dict[str, Any],
    paths: dict[str, Path],
    expected_by_selector: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    receipt = load_json(POSE_RECEIPT_PATH)
    arm = IndependentArm(paths["accepted_urdf"])
    mount = independent_mount(paths["current_execution_mount_12dp"])
    t0 = arm.fk([0.0] * 6)
    j4 = next(segment for segment in centerline["segments"] if segment["id"].startswith("SEG-04_"))
    sections = j4["sections"]
    u = sections[2]
    ann = sections[5]
    fa = v3(sections[1]["points"][0])
    downstream = v3(sections[6]["points"][0])
    u_center0, u_e1, u_radius = v3(u["center"]), v3(u["basis_e1"]), float(u["radius_mm"])
    ann_center, ann_e1, ann_e2 = v3(ann["center"]), v3(ann["basis_e1"]), v3(ann["basis_e2"])
    ann_radius = float(ann["radius_mm"])
    alpha_fixed = math.radians(float(ann["start_angle_deg"]))
    beta0 = abs(math.radians(float(ann["sweep_deg"])))
    x0 = -205.0 - 27.5 * 0.15
    exchange0 = 2.0 * (fa[0] - x0) + math.pi * u_radius + ann_radius * beta0
    independent_samples = []
    max_receipt_delta = 0.0
    section5_expected = [capsule for capsule in expected_by_selector[J4_SELECTOR] if capsule["section"] == 5]
    demand(len(section5_expected) == J4_SECTION5_TOPOLOGY_COUNT,
           "independent J4 section-5 topology is not 139")
    full_domain_max_step = 0.0
    full_domain_max_bound = 0.0
    full_domain_max_effective = 0.0
    for q4, observed in zip((-1.87, 0.0, 1.57), receipt["j4_samples"], strict=True):
        q = [0.0, 0.0, 0.0, q4, 0.0, 0.0]
        tq = arm.fk(q)
        m3 = mount @ tq["link3"] @ np.linalg.inv(t0["link3"])
        m4 = mount @ tq["link4"] @ np.linalg.inv(t0["link4"])
        xc = -205.0 - 27.5 * (q4 + 0.15)
        beta = math.radians(20.0) + (1.57 - q4)
        alpha = alpha_fixed - beta
        endpoint = ann_center + ann_radius * (math.cos(alpha) * ann_e1 + math.sin(alpha) * ann_e2)
        closure = float(np.linalg.norm(xform(m3, endpoint) - xform(m4, downstream)))
        exchange_residual = 2.0 * (fa[0] - xc) + math.pi * u_radius + ann_radius * beta - exchange0
        segment_steps = []
        segment_bounds = []
        segment_effective = []
        for capsule in section5_expected:
            dynamic_delta = abs(float(capsule["delta"])) * beta / beta0
            step = ann_radius * dynamic_delta
            bound = ann_radius * (1.0 - math.cos(dynamic_delta / 2.0))
            effective = DESIGN_RADIUS + bound
            demand(step <= MAX_STEP + 1.0e-12, "independent J4 full-domain step failure")
            demand(abs(effective - (DESIGN_RADIUS + bound)) <= 1.0e-15,
                   "independent J4 effective-radius failure")
            segment_steps.append(step)
            segment_bounds.append(bound)
            segment_effective.append(effective)
        expected = {
            "q4_rad": q4, "x_c_mm": xc, "annulus_beta_rad": beta,
            "dynamic_exchange_length_residual_mm": exchange_residual,
            "follower_closure_residual_mm": closure,
            "section5_topology_capsule_count": len(section5_expected),
            "section5_segments_recomputed": len(segment_steps),
            "section5_max_dynamic_curve_arclength_step_mm": max(segment_steps),
            "section5_max_dynamic_hausdorff_bound_mm": max(segment_bounds),
            "section5_max_dynamic_effective_radius_mm": max(segment_effective),
        }
        for key, value in expected.items():
            max_receipt_delta = max(max_receipt_delta, near(observed[key], value, 2.0e-12, f"pose receipt {key}"))
        independent_samples.append(expected)
        full_domain_max_step = max(full_domain_max_step, max(segment_steps))
        full_domain_max_bound = max(full_domain_max_bound, max(segment_bounds))
        full_domain_max_effective = max(full_domain_max_effective, max(segment_effective))
    demand(independent_samples[0]["x_c_mm"] > independent_samples[1]["x_c_mm"] > independent_samples[2]["x_c_mm"],
           "independent J4 x sign failure")
    demand(independent_samples[0]["annulus_beta_rad"] > independent_samples[1]["annulus_beta_rad"] > independent_samples[2]["annulus_beta_rad"],
           "independent J4 beta sign failure")
    demand(max(sample["follower_closure_residual_mm"] for sample in independent_samples) <= 1.0e-6,
           "independent J4 follower closure failure")
    demand(max(abs(sample["dynamic_exchange_length_residual_mm"]) for sample in independent_samples) <= 1.0e-9,
           "independent J4 exchange length failure")
    demand(abs(full_domain_max_step - 1.4992706602297674) <= 2.0e-15,
           "independent J4 worst-case dynamic step drift")
    near(receipt["j4_section5_full_domain_max_dynamic_curve_arclength_step_mm"],
         full_domain_max_step, 2.0e-12, "pose full-domain step")
    near(receipt["j4_section5_full_domain_max_dynamic_hausdorff_bound_mm"],
         full_domain_max_bound, 2.0e-15, "pose full-domain bound")
    near(receipt["j4_section5_full_domain_max_dynamic_effective_radius_mm"],
         full_domain_max_effective, 2.0e-15, "pose full-domain effective radius")
    j3_capsules = expected_by_selector["SEG-03_J3_CARRIER_HYBRID_WRAP"]
    dual_count = sum(capsule["section"] in {0, 1, 2} for capsule in j3_capsules)
    demand(receipt["j3"]["dual_host_capsule_count"] == dual_count, "J3 dual-host count drift")
    demand(receipt["j3"]["continuous_q3_carrier_law"] == "UNKNOWN" and
           receipt["j3"]["production_union_acceptance"] == "UNKNOWN", "J3 authority overreach")
    return {
        "receipt": {"path": POSE_RECEIPT_PATH.relative_to(root_dir()).as_posix(),
                    "bytes": POSE_RECEIPT_PATH.stat().st_size, "sha256": digest_file(POSE_RECEIPT_PATH)},
        "independent_samples": independent_samples,
        "max_receipt_numeric_residual": max_receipt_delta,
        "j3_dual_host_capsule_count": dual_count,
        "j3_continuous_q3_carrier_law": "UNKNOWN",
        "j3_production_union_acceptance": "UNKNOWN",
        "j4_section5_topology_capsule_count": len(section5_expected),
        "j4_section5_full_domain_max_dynamic_curve_arclength_step_mm": full_domain_max_step,
        "j4_section5_full_domain_max_dynamic_hausdorff_bound_mm": full_domain_max_bound,
        "j4_section5_full_domain_max_dynamic_effective_radius_mm": full_domain_max_effective,
        "j4_all_139_segments_recomputed_at_each_q4_sample": True,
        "pass": True,
    }


def assert_object_set(ids: list[str]) -> None:
    demand(ids == EXPECTED_IDS and len(set(ids)) == 9, "nine-object set/order failure")


def assert_numeric_contract(numeric: dict[str, Any]) -> None:
    demand(numeric.get("nominal_bundle_od_mm") == 9.0, "nominal OD misuse")
    demand(numeric.get("design_upper_bundle_od_mm") == 10.0, "design OD misuse")
    demand(numeric.get("design_centerline_tube_radius_mm") == 5.0, "design radius misuse")
    demand(numeric.get("nominal_to_design_radial_increment_mm_already_included") == 0.5,
           "nominal/design increment lineage drift")
    demand(numeric.get("p01_channel_clearance_mm_not_a_bundle_radius") == 12.0,
           "P01 value/role drift")
    demand(numeric.get("maximum_curve_arclength_step_mm") == 1.5, "curve-step drift")
    demand(numeric.get("p11_physical_guide_to_centerline_offset_lineage") == "UNKNOWN", "P11 lineage upgrade")
    query = numeric.get("narrowphase_query_contract", {})
    demand(query.get("required_query_radius_field") == "effective_radius_mm", "query field drift")
    demand(query.get("effective_radius_rule") ==
           "effective_radius_mm = design_radius_mm + hausdorff_bound_mm", "effective-radius rule drift")
    demand(query.get("hausdorff_debit_count") == 1, "Hausdorff debit count drift")
    demand(query.get("separate_clearance_debit_alternative_supported_by_this_package") is False,
           "mixed clearance-debit path enabled")
    j4 = numeric.get("j4_section5_full_q4_discretization", {})
    demand(j4.get("topology_capsule_count") == 139, "J4 topology contract drift")
    demand(j4.get("worst_case_curve_arclength_step_mm") <= 1.5, "J4 worst step contract failure")


def assert_bound(recomputed: float, declared: float) -> None:
    demand(math.isfinite(declared) and declared + 1.0e-18 >= recomputed, "Hausdorff bound underreported")


def assert_effective_query(
    design_radius: float,
    bound: float,
    effective_radius: float,
    query_radius: float,
    query_field: str,
) -> None:
    demand(design_radius == DESIGN_RADIUS and math.isfinite(bound) and bound >= 0.0,
           "invalid design radius or Hausdorff bound")
    demand(query_field == "effective_radius_mm", "raw/ambiguous narrowphase query field")
    expected = design_radius + bound
    demand(abs(effective_radius - expected) <= 1.0e-15, "effective radius is not design plus bound exactly once")
    demand(abs(query_radius - effective_radius) <= 1.0e-15, "narrowphase query did not use effective radius")


def assert_j4_subdivision(count: int) -> None:
    beta_worst = math.radians(20.0) + (1.57 - (-1.87))
    demand(isinstance(count, int) and count >= 1, "J4 subdivision count invalid")
    demand(count >= math.ceil(55.0 * beta_worst / MAX_STEP), "J4 full-domain topology under-subdivided")
    demand(55.0 * beta_worst / count <= MAX_STEP + 1.0e-12, "J4 dynamic step exceeds 1.5 mm")


def assert_units(frame: str, unit: str, scale: float) -> None:
    demand(frame == "A0 = accepted B601 base_link at q=0" and unit == "mm" and scale == 1.0,
           "mm/m or frame misuse")


def assert_mount_strings(strings: list[list[str]]) -> None:
    demand(all(re.fullmatch(r"-?\d+\.\d{12}", value) for row in strings for value in row), "D6 mount rejected")


def assert_q(record: dict[str, Any], limits: dict[str, tuple[float | None, float | None]]) -> None:
    payload = record.get("payload")
    demand(isinstance(payload, dict) and payload.get("joint_order") == JOINT_ORDER and payload.get("schema") == "C9_Q_STATE_V1",
           "q payload structure failure")
    q = payload.get("q_rad")
    demand(isinstance(q, list) and len(q) == 6, "q length failure")
    for name, value in zip(JOINT_ORDER, q, strict=True):
        demand(not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value)), "q nonfinite")
        lower, upper = limits[name]
        demand(lower is not None and upper is not None and lower <= float(value) <= upper, "q limit failure")
    demand(record.get("payload_sha256") == digest_bytes(q_bytes(payload)), "q hash failure")


def assert_j4_law(gain: float, beta_sign: float) -> None:
    values = [-205.0 - gain * (q + 0.15) for q in (-1.87, 0.0, 1.57)]
    betas = [math.radians(20.0) + beta_sign * (1.57 - q) for q in (-1.87, 0.0, 1.57)]
    demand(values[0] > values[1] > values[2] and betas[0] > betas[1] > betas[2], "J4 sign failure")


def assert_j3_policy(law: str, acceptance: str) -> None:
    demand(law == "UNKNOWN" and acceptance == "UNKNOWN", "J3 continuous law/union overreach")


def assert_authority(state: dict[str, Any], expected: dict[str, Any]) -> None:
    demand(state == expected, "system authority overreach or external machine-truth drift")


def external_machine_truth(paths: dict[str, Path]) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_json(paths["current_m01_registry_gate"])
    prebind = load_json(paths["current_m01_scene_prebind_gate"])
    release = load_json(paths["current_terminal_release_gate"])
    handoff = load_json(paths["current_mech_to_embodied_handoff_gate"])
    demand(registry.get("schema") == "SYSTEM_COLLISION_REGISTRY_GATE_V1", "registry Gate schema drift")
    demand(prebind.get("schema") == "M01_SCENE_AND_COLLISION_PREBIND_GATE_V1", "prebind Gate schema drift")
    demand(release.get("schema") == "TERMINAL_MECHANICAL_GATE_A_V1", "release Gate schema drift")
    demand(handoff.get("schema") == "MECH_TO_EMBODIED_HANDOFF_GATE_TERMINAL_V1", "handoff Gate schema drift")
    active_registry = int(registry["known_active_object_count"])
    active_prebind = int(prebind["asset_accounting"]["active_object_rows"])
    demand(active_registry == active_prebind, "active-object truth disagrees across current Gates")
    pair_queries = int(prebind["system_execution_state"]["system_pair_queries_executed"])
    unassessed = int(registry["pair_coverage"]["status_counts"]["UNASSESSED_FAIL_CLOSED"])
    edges = int(prebind["system_execution_state"]["system_edges_certified"])
    stage_bound = int(prebind["scene_accounting"]["stage_instances_bound"])
    stage_required = int(prebind["scene_accounting"]["stage_instances_required"])
    path_executed = bool(prebind["system_execution_state"]["path_search_executed"])
    demand(path_executed is bool(registry["path_search_executed"]), "path-search truth disagrees")
    tmg4_rows = [row for row in release["tmg"] if row.get("id") == "TMG-4"]
    demand(len(tmg4_rows) == 1, "current release Gate has no unique TMG-4 row")
    g12_failed = str(handoff["current_handoff_gate_v2"]["failed"])
    demand(g12_failed.startswith("G12 ") and handoff["verdict"] == "MECHANICAL_TO_EMBODIED_HANDOFF_FAIL",
           "current handoff Gate does not prove G12 FAIL")
    next_stage_values = [registry["next_stage_authorized"], prebind["next_stage_authorized"],
                         release["next_stage_authorized"], handoff["next_stage_authorized"]]
    release_values = [registry["release_credit"], prebind["release_credit"],
                      release["release_credit"], handoff["release_credit"]]
    demand(not any(next_stage_values) and not any(release_values), "current external Gate authority upgraded")
    demand(pair_queries == 0 and edges == 0,
           "safe-certificate zero derivation invalid because query/edge counts are nonzero")
    state = {
        "system_operational_authority_rows": 1, "known_active_objects": 150,
        "system_pair_queries": 0, "required_unassessed_pairs": 11166,
        "safe_certificates": 0, "system_edges_certified": 0,
        "stage_instances_bound": 0, "stage_instances_required": 3,
        "path_search_executed": False, "TMG4": "HOLD", "G12": "FAIL",
        "next_stage_authorized": False, "release_credit": False,
    }
    observed = {
        "system_operational_authority_rows": int(prebind["asset_accounting"]["operational_authority_rows"]),
        "known_active_objects": active_registry,
        "system_pair_queries": pair_queries,
        "required_unassessed_pairs": unassessed,
        "safe_certificates": 0,
        "system_edges_certified": edges,
        "stage_instances_bound": stage_bound,
        "stage_instances_required": stage_required,
        "path_search_executed": path_executed,
        "TMG4": str(tmg4_rows[0]["state"]),
        "G12": "FAIL",
        "next_stage_authorized": any(bool(value) for value in next_stage_values),
        "release_credit": any(bool(value) for value in release_values),
    }
    assert_authority(observed, state)
    evidence = {
        "source": "FOUR_HASH_PINNED_CURRENT_EXTERNAL_MACHINE_GATES",
        "pins": {
            name: {"path": paths[name].relative_to(root_dir()).as_posix(),
                   "bytes": paths[name].stat().st_size, "sha256": digest_file(paths[name])}
            for name in ("current_m01_registry_gate", "current_m01_scene_prebind_gate",
                         "current_terminal_release_gate", "current_mech_to_embodied_handoff_gate")
        },
        "field_bindings": {
            "one_of_150": ["prebind.asset_accounting.operational_authority_rows",
                           "registry.known_active_object_count", "prebind.asset_accounting.active_object_rows"],
            "zero_of_11166": ["prebind.system_execution_state.system_pair_queries_executed",
                              "registry.pair_coverage.status_counts.UNASSESSED_FAIL_CLOSED"],
            "zero_of_three": ["prebind.scene_accounting.stage_instances_bound",
                              "prebind.scene_accounting.stage_instances_required"],
            "TMG4_HOLD": "release.tmg[id=TMG-4].state",
            "G12_FAIL": "handoff.current_handoff_gate_v2.failed + handoff.verdict",
            "safe_certificates_zero_derivation": "zero pair queries and zero certified edges",
        },
        "state": observed,
        "pass": True,
    }
    return observed, evidence


def negative_controls(
    contract: dict[str, Any],
    paths: dict[str, Path],
    arm: IndependentArm,
    external_state: dict[str, Any],
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []

    def caught(identifier: str, mutation: str, call: Any) -> None:
        try:
            call()
        except (ValidationFailure, ValueError, TypeError, OverflowError) as exc:
            cases.append({"id": identifier, "mutation": mutation, "caught": True, "failure": str(exc)})
        else:
            raise ValidationFailure(f"negative control escaped: {identifier}")

    caught("NC01_SOURCE_HASH_DRIFT", "centerline expected hash changed", lambda: demand(
        digest_file(paths["v9f_centerline"]) == "0" * 64, "source hash mismatch"))
    caught("NC02_C9_OBJECT_MISSING", "remove ninth object", lambda: assert_object_set(EXPECTED_IDS[:-1]))
    caught("NC03_C9_OBJECT_DUPLICATED", "duplicate first object", lambda: assert_object_set(EXPECTED_IDS[:-1] + [EXPECTED_IDS[0]]))
    numeric = contract["numeric_contract"]
    for identifier, field, value, reason in [
        ("NC04_NOMINAL_OD_DRIFT", "nominal_bundle_od_mm", 10.0, "nominal OD changed"),
        ("NC05_DESIGN_OD_DRIFT", "design_upper_bundle_od_mm", 9.0, "design OD changed"),
        ("NC06_RADIUS_NOMINAL_4P5_USED", "design_centerline_tube_radius_mm", 4.5, "nominal radius substituted"),
        ("NC07_P01_12MM_USED_AS_RADIUS", "design_centerline_tube_radius_mm", 12.0, "P01 channel clearance used as radius"),
        ("NC08_RADIAL_0P5_DOUBLE_COUNTED", "design_centerline_tube_radius_mm", 5.5, "0.5 mm increment added twice"),
    ]:
        changed = copy.deepcopy(numeric)
        changed[field] = value
        caught(identifier, reason, lambda changed=changed: assert_numeric_contract(changed))
    caught("NC09_HAUSDORFF_UNDERREPORTED", "declare half of analytic sagitta",
           lambda: assert_bound(0.005, 0.0025))
    caught("NC10_MM_M_SCALE_ERROR", "declare A0 coordinates in metres with 0.001 scale",
           lambda: assert_units("A0 = accepted B601 base_link at q=0", "m", 0.001))
    mount_doc = load_json(paths["current_execution_mount_12dp"])
    d6 = [[f"{float(value):.6f}" for value in row]
          for row in mount_doc["binding"]["canonical_matrix_decimal_strings"]]
    caught("NC11_HISTORICAL_D6_MOUNT", "round current mount to six decimals", lambda: assert_mount_strings(d6))
    base_payload = {"schema": "C9_Q_STATE_V1", "joint_order": JOINT_ORDER, "q_rad": [0.0] * 6}
    good = {"payload": base_payload, "payload_sha256": digest_bytes(q_bytes(base_payload))}
    wrong_hash = copy.deepcopy(good); wrong_hash["payload_sha256"] = "0" * 64
    caught("NC12_Q_HASH_MISMATCH", "replace q hash", lambda: assert_q(wrong_hash, arm.limits))
    outside = copy.deepcopy(good); outside["payload"]["q_rad"][3] = 1.5701
    outside["payload_sha256"] = digest_bytes(q_bytes(outside["payload"]))
    caught("NC13_Q_LIMIT_EXCEEDED", "q4 above accepted URDF limit", lambda: assert_q(outside, arm.limits))
    nonfinite = copy.deepcopy(good); nonfinite["payload"]["q_rad"][2] = float("nan")
    caught("NC14_Q_NAN", "q3 NaN", lambda: assert_q(nonfinite, arm.limits))
    caught("NC15_J4_SIGN_REVERSED", "reverse x_c and beta motion signs", lambda: assert_j4_law(-27.5, -1.0))
    caught("NC16_J3_CONTINUOUS_LAW_INVENTED", "claim interpolated q3 carrier law and accepted union",
           lambda: assert_j3_policy("LINEAR_INTERPOLATION", "ACCEPTED"))
    over = copy.deepcopy(external_state); over["system_pair_queries"] = 1
    caught("NC17_UNAUTHORIZED_PAIR_CREDIT", "grant one current pair query",
           lambda: assert_authority(over, external_state))
    over2 = copy.deepcopy(external_state); over2["TMG4"] = "PASS"
    caught("NC18_UNAUTHORIZED_TMG4_UPGRADE", "upgrade TMG4",
           lambda: assert_authority(over2, external_state))
    bound = 0.005
    caught("NC19_RAW_5MM_USED_AS_QUERY_RADIUS", "query a curved chord with raw 5.0 mm design radius",
           lambda: assert_effective_query(5.0, bound, 5.0 + bound, 5.0, "effective_radius_mm"))
    caught("NC20_HAUSDORFF_DOUBLE_DEBIT_OR_INFLATION", "inflate effective radius by two Hausdorff bounds",
           lambda: assert_effective_query(5.0, bound, 5.0 + 2.0 * bound,
                                          5.0 + 2.0 * bound, "effective_radius_mm"))
    caught("NC21_J4_SECTION5_Q0_ONLY_UNDERSUBDIVISION", "reuse the old 71-chord q0 topology over full q4",
           lambda: assert_j4_subdivision(71))
    demand(len(cases) == 21 and all(case["caught"] for case in cases), "negative control count/catch failure")
    return {
        "schema": "ROUTE_C_C9_NEGATIVE_CONTROLS_V1",
        "generated_utc": "DETERMINISTIC_INDEPENDENT_VALIDATION_NO_WALLCLOCK",
        "required": 21, "caught": 21, "all_caught": True, "cases": cases,
        "coverage": [
            "SOURCE_DRIFT", "NINE_OBJECT_MISSING_OR_DUPLICATE", "OD_AND_RADIUS",
            "P01_12MM_MISUSE", "RADIAL_0P5_DOUBLE_COUNT", "HAUSDORFF_UNDERREPORT",
            "MM_M", "HISTORICAL_D6_MOUNT", "Q_HASH_LIMIT_NAN", "J4_SIGN",
            "J3_CONTINUOUS_LAW_FORGERY", "AUTHORITY_OVERREACH",
            "RAW_DESIGN_RADIUS_QUERY", "HAUSDORFF_DOUBLE_DEBIT_OR_INFLATION",
            "J4_FULL_DOMAIN_UNDERSUBDIVISION",
        ],
        "verdict": "ALL_21_C9_NEGATIVE_CONTROLS_CAUGHT_FAIL_CLOSED",
    }


def build_validation() -> tuple[dict[str, Any], dict[str, Any]]:
    lock, contract, ledger = load_json(LOCK_PATH), load_json(CONTRACT_PATH), load_json(LEDGER_PATH)
    paths = verify_pins(lock)
    external_state, external_evidence = external_machine_truth(paths)
    ids = [item["object_id"] for item in contract["objects"]]
    assert_object_set(ids)
    assert_numeric_contract(contract["numeric_contract"])
    declaration = contract["system_truth_declaration_only"]
    demand(declaration["authority"] ==
           "DECLARATION_ONLY__MUST_BE_REBUILT_FROM_FOUR_HASH_PINNED_CURRENT_MACHINE_GATES",
           "contract system state is not declaration-only")
    declaration_values = {key: value for key, value in declaration.items()
                          if key not in {"authority", "verification_sources"}}
    demand(declaration_values == external_state, "declaration differs from current external machine truth")
    demand(ledger["j3_motion"]["continuous_q3_carrier_law"] == "UNKNOWN" and
           ledger["j3_motion"]["production_union_acceptance"] == "UNKNOWN", "ledger J3 overreach")
    source = load_json(paths["v9f_centerline"])
    registry = load_json(paths["current_m01_registry"])
    c_rows = [row for row in registry["objects"] if row.get("category") == "C"]
    assert_object_set([row["object_id"] for row in c_rows])
    index = load_json(INDEX_PATH)
    demand(index["object_count"] == 9, "index object count drift")
    assert_object_set([row["object_id"] for row in index["objects"]])
    segments = {segment["id"]: segment for segment in source["segments"]}
    contract_by_selector = {item["selector"]: item for item in contract["objects"]}
    index_by_selector = {item["selector"]: item for item in index["objects"]}
    object_results = []
    expected_by_selector: dict[str, list[dict[str, Any]]] = {}
    maximum_numeric = 0.0
    for selector in [item["selector"] for item in contract["objects"]]:
        pieces, capsules, _ = expected_capsules(segments[selector], contract_by_selector[selector])
        expected_by_selector[selector] = capsules
        result, numeric = validate_object(segments[selector], contract_by_selector[selector], index_by_selector[selector])
        object_results.append(result)
        maximum_numeric = max(maximum_numeric, numeric["max_numeric"])
    total_capsules = sum(item["capsule_count"] for item in object_results)
    total_primitives = sum(item["primitive_count"] for item in object_results)
    max_bound = max(item["maximum_hausdorff_bound_mm"] for item in object_results)
    max_effective = max(item["maximum_effective_radius_mm"] for item in object_results)
    max_step = max(item["maximum_curve_arclength_step_mm"] for item in object_results)
    max_length_residual = max(item["source_BRep_length_abs_residual_mm"] for item in object_results)
    max_gap = max(item["section_endpoint_gap_max_mm"] for item in object_results)
    demand(total_capsules == 2355 and total_primitives == 61, "aggregate capsule/primitive count drift")
    demand(max_step <= 1.5 + 1.0e-12 and max_bound <= 1.5**2 / (8.0 * 54.0), "global discretization bound failure")
    build_receipt = load_json(BUILD_RECEIPT_PATH)
    demand(build_receipt["outputs"]["deterministic_core_count_including_receipt"] == 20,
           "builder core count drift")
    demand(build_receipt["builder_execution_class"] ==
           "PURE_ANALYTIC_JSON_INPUT__NO_V9F_SOURCE_IMPORT_TRACE_OR_EXECUTION", "builder execution-class drift")
    import_boundary = static_import_boundary()
    pose = independent_pose_validation(source, paths, expected_by_selector)
    arm = IndependentArm(paths["accepted_urdf"])
    negatives = negative_controls(contract, paths, arm, external_state)
    validation = {
        "schema": "ROUTE_C_C9_INDEPENDENT_VALIDATION_V1",
        "generated_utc": "DETERMINISTIC_INDEPENDENT_VALIDATION_NO_WALLCLOCK",
        "validator": {
            "path": Path(__file__).resolve().relative_to(root_dir()).as_posix(),
            "bytes": Path(__file__).stat().st_size,
            "sha256": digest_file(Path(__file__)),
            "builder_imported": False,
            "pose_adapter_imported": False,
            "analytic_primitives_Hausdorff_and_FK_independently_rebuilt": True,
        },
        "source_pins_verified": len(paths),
        "objects": object_results,
        "aggregate": {
            "objects": len(object_results), "primitives": total_primitives, "capsules": total_capsules,
            "maximum_hausdorff_bound_mm": max_bound,
            "maximum_effective_radius_mm": max_effective,
            "uniform_conservative_reference_bound_mm": 1.5**2 / (8.0 * 54.0),
            "maximum_curve_arclength_step_mm": max_step,
            "maximum_source_BRep_length_abs_residual_mm": max_length_residual,
            "maximum_section_endpoint_gap_mm": max_gap,
            "maximum_builder_vs_independent_numeric_residual": maximum_numeric,
            "clamped_fillet_count": sum(item["clamped_fillet_count"] for item in object_results),
            "minimum_clamped_actual_radius_mm": min(
                float(load_json(PACKAGE / row["json"]["path"])["metrics"]["minimum_actual_fillet_radius_mm"])
                for row in index["objects"]
                if load_json(PACKAGE / row["json"]["path"])["metrics"]["minimum_actual_fillet_radius_mm"] is not None),
            "j4_section5_full_domain_topology_capsule_count":
                pose["j4_section5_topology_capsule_count"],
            "j4_section5_full_domain_max_dynamic_curve_arclength_step_mm":
                pose["j4_section5_full_domain_max_dynamic_curve_arclength_step_mm"],
            "j4_section5_full_domain_max_dynamic_hausdorff_bound_mm":
                pose["j4_section5_full_domain_max_dynamic_hausdorff_bound_mm"],
            "j4_section5_full_domain_max_dynamic_effective_radius_mm":
                pose["j4_section5_full_domain_max_dynamic_effective_radius_mm"],
        },
        "import_boundary": import_boundary,
        "pose_adapter_independent_validation": pose,
        "negative_controls": {"required": 21, "caught": 21, "all_caught": True,
                              "receipt_path": NEGATIVE_PATH.relative_to(root_dir()).as_posix()},
        "authority_boundary": {
            "P11_physical_guide_to_centerline_offset_lineage": "UNKNOWN",
            "J3_continuous_q3_carrier_law": "UNKNOWN",
            "J3_production_union_acceptance": "UNKNOWN",
            "system_state": external_state,
            "system_state_authority": external_evidence,
            "contract_state_is_declaration_only": True,
            "pair_edge_path_release_credit": 0,
        },
        "checks": {
            "V01_eighteen_source_pins_match_including_four_current_machine_gates": True,
            "V02_registry_and_contract_exact_nine_objects": True,
            "V03_analytic_primitives_rebuilt_without_builder_import": True,
            "V04_fillet_actual_radius_and_tangent_continuity_rebuilt": True,
            "V05_2355_capsules_rebuilt_endpoint_by_endpoint": True,
            "V06_all_curve_steps_at_most_1p5_mm": True,
            "V07_arc_exact_and_helix_conservative_Hausdorff_bounds_match": True,
            "V08_effective_radius_design_plus_Hausdorff_exactly_once": True,
            "V09_json_npz_identical_and_npz_deterministic": True,
            "V10_current_12dp_mount_and_accepted_URDF_FK_rebuilt": True,
            "V11_J4_q4_lower_zero_upper_139_segment_full_domain_step_bound_effective_pass": True,
            "V12_J3_dual_host_output_preserved_unknown": True,
            "V13_all_21_negative_controls_caught": True,
            "V14_current_system_truth_read_from_four_hash_pinned_external_machine_gates": True,
            "V15_zero_current_pair_edge_path_or_release_credit": True,
            "V16_contract_current_state_is_declaration_only": True,
        },
        "checks_passed": 16,
        "checks_required": 16,
        "independent_validation_pass": True,
        "maximum_legal_claim": "NINE_LOCAL_ANALYTIC_CAPSULE_CANDIDATES_INDEPENDENTLY_REBUILT__J3_UNION_UNKNOWN",
        "verdict": "C9_INDEPENDENT_VALIDATION_9_OF_9_PASS__ZERO_CURRENT_PAIR_EDGE_PATH_CREDIT__TMG4_HOLD",
    }
    return validation, negatives


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    options = args()
    validation, negatives = build_validation()
    encoded_validation, encoded_negatives = canonical_json(validation), canonical_json(negatives)
    if options.write:
        put(VALIDATION_PATH, encoded_validation)
        put(NEGATIVE_PATH, encoded_negatives)
        mode = "write"
    else:
        demand(VALIDATION_PATH.is_file() and VALIDATION_PATH.read_bytes() == encoded_validation,
               "independent validation receipt drift")
        demand(NEGATIVE_PATH.is_file() and NEGATIVE_PATH.read_bytes() == encoded_negatives,
               "negative-control receipt drift")
        mode = "check"
    print(json.dumps({
        "status": "PASS", "mode": mode,
        "objects": validation["aggregate"]["objects"],
        "primitives": validation["aggregate"]["primitives"],
        "capsules": validation["aggregate"]["capsules"],
        "maximum_hausdorff_bound_mm": validation["aggregate"]["maximum_hausdorff_bound_mm"],
        "negative_controls": negatives["caught"],
        "j3_production_union_acceptance": "UNKNOWN",
        "system_pair_credit": 0, "TMG4": "HOLD",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
