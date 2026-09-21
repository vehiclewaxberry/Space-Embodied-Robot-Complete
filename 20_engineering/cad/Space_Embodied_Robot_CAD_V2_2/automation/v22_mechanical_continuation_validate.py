#!/usr/bin/env python3
"""Independent, fail-closed validation for the isolated V2.2 continuation.

The validator is intentionally read-only outside its three evidence outputs.
It does not import the CAD generator, open SolidWorks, or write the canonical
V2.2 assembly.  STEP reopen is performed in a fresh isolated Python process
whose working directory contains no CAD dependencies.
"""
from __future__ import annotations

import ast
import ctypes
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import psutil
import yaml
from ctypes import wintypes


SCRIPT = Path(__file__).resolve()
V22 = SCRIPT.parent.parent
WORKSPACE = V22.parents[2]
MECHANICAL = V22 / "100_Mechanical_Continuation"
EVIDENCE = V22 / "evidence" / "v22_b601_recovery_mechanical_unblock_01"

GENERATOR = MECHANICAL / "v22_mechanical_continuation.py"
PRIMARY_STEP = MECHANICAL / "v22_mechanical_continuation.step"
BRIEF = MECHANICAL / "V22_MECHANICAL_CONTINUATION_BRIEF.md"
INTERFACE_REGISTRY = MECHANICAL / "design" / "interface_registry.yaml"
CONFIGURATION_POLICY = MECHANICAL / "design" / "configuration_policy.yaml"

URDF = (
    WORKSPACE
    / "20_engineering"
    / "cad"
    / "spacecraft_layout"
    / "arm_b601_v1"
    / "arm_b601_v1.urdf"
)
CANONICAL_TOP = V22 / "Assembly" / "Spacecraft_Service_Vehicle_V2_2.SLDASM"

PHASE_A_NAMES = (
    "phase_a_pre_run_index.json",
    "phase_a_validation.json",
    "pre_run_01_asset00_evidence_tree.json",
    "pre_run_02_b601_controlled_subassembly.json",
    "pre_run_03_v22_authoritative_top.json",
    "pre_run_04_v20_native_57.json",
    "pre_run_05_accepted_b601_12.json",
    "pre_run_06_registered_step.json",
)
SOURCE_MANIFEST_NAMES = PHASE_A_NAMES[2:]

RESOURCE_OUTPUT = EVIDENCE / "phase_b_resource_gate.json"
JSON_OUTPUT = EVIDENCE / "v22_mechanical_continuation_validation.json"
REPORT_OUTPUT = EVIDENCE / "V22_MECHANICAL_CONTINUATION_VALIDATION_REPORT.md"

EXPECTED_URDF_MASS = Decimal("4.6955559493429862")
PHYSICAL_THRESHOLD_BYTES = 4 * 1024**3
COMMIT_THRESHOLD_BYTES = 8 * 1024**3
TOL = 1.0e-5


class ValidationError(RuntimeError):
    """Fail-closed validation error."""


class GlobalMemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "exists": True,
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


def phase_a_fingerprints() -> dict[str, dict[str, Any]]:
    return {name: fingerprint(EVIDENCE / name) for name in PHASE_A_NAMES}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationError(f"cannot parse JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"expected JSON object: {path}")
    return value


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationError(f"cannot parse YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"expected YAML mapping: {path}")
    return value


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def json_bytes(payload: dict[str, Any]) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    json.loads(data)
    return data.encode("utf-8")


def gate(
    gate_id: str,
    status: str,
    summary: str,
    evidence: Any = None,
    *,
    critical: bool = False,
) -> dict[str, Any]:
    if status not in {"PASS", "HOLD", "FAIL", "NOT_APPLICABLE"}:
        raise ValidationError(f"invalid gate status: {status}")
    record: dict[str, Any] = {
        "id": gate_id,
        "status": status,
        "critical": critical,
        "summary": summary,
    }
    if evidence is not None:
        record["evidence"] = evidence
    return record


def approx(actual: float, expected: float, tolerance: float = TOL) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance)


def bbox_matches(
    record: dict[str, Any],
    expected_min: tuple[float, float, float],
    expected_max: tuple[float, float, float],
) -> bool:
    actual_min = record.get("bbox_min", [])
    actual_max = record.get("bbox_max", [])
    return (
        len(actual_min) == 3
        and len(actual_max) == 3
        and all(approx(float(a), e) for a, e in zip(actual_min, expected_min))
        and all(approx(float(a), e) for a, e in zip(actual_max, expected_max))
    )


def collect_resource_gate() -> dict[str, Any]:
    memory = GlobalMemoryStatusEx()
    memory.dwLength = ctypes.sizeof(GlobalMemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ctypes.WinError()

    target_names = {"sldworks.exe", "sldprocmon.exe"}
    processes: dict[str, list[dict[str, Any]]] = {
        "SLDWORKS.exe": [],
        "sldProcMon.exe": [],
    }
    for process in psutil.process_iter(["pid", "name", "create_time", "memory_info"]):
        try:
            name = str(process.info.get("name") or "")
            normalized = name.casefold()
            if normalized not in target_names:
                continue
            key = "SLDWORKS.exe" if normalized == "sldworks.exe" else "sldProcMon.exe"
            memory_info = process.info.get("memory_info")
            processes[key].append(
                {
                    "pid": int(process.info["pid"]),
                    "name": name,
                    "create_time_utc": datetime.fromtimestamp(
                        float(process.info["create_time"]), timezone.utc
                    ).isoformat(),
                    "working_set_bytes": (
                        int(memory_info.rss) if memory_info is not None else None
                    ),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError, TypeError):
            continue

    physical_ok = memory.ullAvailPhys >= PHYSICAL_THRESHOLD_BYTES
    commit_ok = memory.ullAvailPageFile >= COMMIT_THRESHOLD_BYTES
    commit_used = memory.ullTotalPageFile - memory.ullAvailPageFile
    commit_percent = (
        100.0 * commit_used / memory.ullTotalPageFile
        if memory.ullTotalPageFile
        else None
    )
    return {
        "schema_version": "1.0",
        "gate_id": "V22_B601_PHASE_B_VISIBLE_RECOVERY_RESOURCE_GATE",
        "captured_utc": utc_now(),
        "collection_mode": "READ_ONLY_NO_PROCESS_CONTROL",
        "threshold_authority": (
            "PROJECT_CONSERVATIVE_RECOMMENDATION_NOT_VENDOR_SPEC"
        ),
        "thresholds": {
            "available_physical_bytes_min": PHYSICAL_THRESHOLD_BYTES,
            "available_physical_gib_min": 4.0,
            "commit_headroom_bytes_min": COMMIT_THRESHOLD_BYTES,
            "commit_headroom_gib_min": 8.0,
        },
        "memory": {
            "collection_api": "Win32_GlobalMemoryStatusEx",
            "total_physical_bytes": int(memory.ullTotalPhys),
            "available_physical_bytes": int(memory.ullAvailPhys),
            "available_physical_gib": memory.ullAvailPhys / 1024**3,
            "commit_limit_bytes": int(memory.ullTotalPageFile),
            "commit_used_bytes": int(commit_used),
            "commit_headroom_bytes": int(memory.ullAvailPageFile),
            "commit_headroom_gib": memory.ullAvailPageFile / 1024**3,
            "commit_percent": commit_percent,
            "system_memory_load_percent": int(memory.dwMemoryLoad),
        },
        "processes": {
            name: {
                "count": len(rows),
                "instances": rows,
            }
            for name, rows in processes.items()
        },
        "checks": {
            "available_physical_threshold_met": physical_ok,
            "commit_headroom_threshold_met": commit_ok,
        },
        "process_actions_started_or_stopped": [],
        "verdict": (
            "ELIGIBLE_FOR_SEPARATELY_AUTHORIZED_VISIBLE_DIAGNOSTIC"
            if physical_ok and commit_ok
            else "DEFERRED_RESOURCE_GATE"
        ),
        "authorization_effect": (
            "This read-only gate never starts SolidWorks and does not itself "
            "authorize a recovery attempt."
        ),
    }


def source_rechecks() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest_results: list[dict[str, Any]] = []
    index_results: list[dict[str, Any]] = []
    for name in SOURCE_MANIFEST_NAMES:
        manifest_path = EVIDENCE / name
        manifest = read_json(manifest_path)
        changed: list[dict[str, Any]] = []
        for captured in manifest.get("files", []):
            path = Path(captured["absolute_path"])
            current = fingerprint(path)
            match = (
                current.get("exists")
                and current.get("bytes") == captured.get("bytes")
                and current.get("sha256") == captured.get("sha256")
            )
            if not match:
                changed.append(
                    {
                        "relative_path": captured.get("relative_path"),
                        "captured_bytes": captured.get("bytes"),
                        "captured_sha256": captured.get("sha256"),
                        "current": current,
                    }
                )
        manifest_results.append(
            {
                "manifest": name,
                "manifest_id": manifest.get("manifest_id"),
                "source_file_count": len(manifest.get("files", [])),
                "changed_count": len(changed),
                "changed": changed,
                "status": "UNCHANGED" if not changed else "CHANGED",
            }
        )

    index = read_json(EVIDENCE / "phase_a_pre_run_index.json")
    for row in index.get("manifests", []):
        current = fingerprint(EVIDENCE / row["path"])
        match = (
            current.get("exists")
            and current.get("bytes") == row.get("bytes")
            and current.get("sha256") == row.get("sha256")
        )
        index_results.append(
            {
                "path": row["path"],
                "match": bool(match),
                "captured_bytes": row.get("bytes"),
                "captured_sha256": row.get("sha256"),
                "current": current,
            }
        )
    return manifest_results, index_results


def phase_a_control_state() -> dict[str, Any]:
    index = read_json(EVIDENCE / "phase_a_pre_run_index.json")
    validation = read_json(EVIDENCE / "phase_a_validation.json")
    return {
        "index_machine_verdict": index.get("machine_verdict"),
        "index_manifest_count": index.get("manifest_count"),
        "validation_machine_verdict": validation.get("machine_verdict"),
        "validation_overall": validation.get("overall"),
    }


def urdf_mass() -> dict[str, Any]:
    masses: list[Decimal] = []
    root = ET.parse(URDF).getroot()
    for mass in root.findall(".//inertial/mass"):
        value = mass.attrib.get("value")
        if value is None:
            raise ValidationError("URDF inertial mass without value")
        masses.append(Decimal(value))
    total = sum(masses, Decimal("0"))
    return {
        "path": str(URDF.resolve()),
        "sha256": sha256_file(URDF),
        "inertial_count": len(masses),
        "mass_values_kg": [str(value) for value in masses],
        "total_kg_decimal": str(total),
        "expected_total_kg_decimal": str(EXPECTED_URDF_MASS),
        "exact_decimal_match": total == EXPECTED_URDF_MASS,
    }


def safe_eval(node: ast.AST, values: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List)):
        items = [safe_eval(item, values) for item in node.elts]
        return tuple(items) if isinstance(node, ast.Tuple) else items
    if isinstance(node, ast.Dict):
        return {
            safe_eval(key, values): safe_eval(value, values)
            for key, value in zip(node.keys, node.values)
        }
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.UnaryOp):
        operand = safe_eval(node.operand, values)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
    if isinstance(node, ast.BinOp):
        left = safe_eval(node.left, values)
        right = safe_eval(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    raise ValueError(type(node).__name__)


def literal_assignments(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, Any] = {}
    for statement in tree.body:
        target: ast.expr | None = None
        value_node: ast.expr | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            value_node = statement.value
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            value_node = statement.value
        if not isinstance(target, ast.Name) or value_node is None:
            continue
        try:
            values[target.id] = safe_eval(value_node, values)
        except (ValueError, KeyError, TypeError, ZeroDivisionError):
            continue
    return values


STEP_PROBE = r"""
import json
import math
import sys
from pathlib import Path

from build123d import import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GeomAbs import GeomAbs_Cylinder

path = Path(sys.argv[1]).resolve()

def vector(value):
    return [float(value.X), float(value.Y), float(value.Z)]

root = import_step(path)
records = []

def visit(shape, depth=0):
    bbox = shape.bounding_box()
    cylinders = []
    for face in shape.faces():
        adaptor = BRepAdaptor_Surface(face.wrapped)
        if adaptor.GetType() == GeomAbs_Cylinder:
            cylinder = adaptor.Cylinder()
            direction = cylinder.Axis().Direction()
            cylinders.append({
                "radius_mm": float(cylinder.Radius()),
                "axis_direction": [
                    float(direction.X()),
                    float(direction.Y()),
                    float(direction.Z()),
                ],
            })
    records.append({
        "label": str(shape.label or ""),
        "shape_type": type(shape).__name__,
        "depth": depth,
        "solid_count": len(shape.solids()),
        "bbox_min": vector(bbox.min),
        "bbox_max": vector(bbox.max),
        "bbox_size": vector(bbox.size),
        "cylindrical_faces": cylinders,
    })
    for child in shape.children:
        visit(child, depth + 1)

visit(root)
solids = list(root.solids())
invalid = []
nonpositive = []
for index, solid in enumerate(solids, start=1):
    if not BRepCheck_Analyzer(solid.wrapped).IsValid():
        invalid.append(index)
    volume = float(solid.volume)
    if not math.isfinite(volume) or volume <= 0.0:
        nonpositive.append({"index": index, "volume": volume})

root_bbox = root.bounding_box()
print(json.dumps({
    "probe_engine": "build123d_import_step_plus_OCP_BRepCheck",
    "path": str(path),
    "root_label": str(root.label or ""),
    "root_shape_type": type(root).__name__,
    "root_valid": bool(BRepCheck_Analyzer(root.wrapped).IsValid()),
    "solid_count": len(solids),
    "compound_record_count": sum(
        row["shape_type"] == "Compound" for row in records
    ),
    "invalid_solid_indices": invalid,
    "nonpositive_volume_solids": nonpositive,
    "bbox_min": vector(root_bbox.min),
    "bbox_max": vector(root_bbox.max),
    "bbox_size": vector(root_bbox.size),
    "records": records,
}, ensure_ascii=False))
"""


def reopen_step(path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="v22_step_reopen_") as temporary:
        result = subprocess.run(
            [sys.executable, "-c", STEP_PROBE, str(path.resolve())],
            cwd=temporary,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=180,
            check=False,
        )
    if result.returncode != 0:
        return {
            "path": str(path.resolve()),
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "probe_status": "FAIL",
        }
    try:
        probe = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "path": str(path.resolve()),
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "probe_status": "FAIL",
            "parse_error": str(exc),
        }
    probe["probe_status"] = "PASS"
    probe["bytes"] = path.stat().st_size
    probe["sha256"] = sha256_file(path)
    text = path.read_text(encoding="latin-1", errors="ignore")
    probe["product_labels"] = re.findall(
        r"PRODUCT\('((?:[^']|'')*)'", text, flags=re.IGNORECASE
    )
    external_tokens = (
        "EXTERNALLY_DEFINED_ITEM",
        "EXTERNAL_SOURCE",
        "DOCUMENT_FILE",
        "APPLIED_EXTERNAL_IDENTIFICATION_ASSIGNMENT",
    )
    probe["external_reference_token_counts"] = {
        token: text.upper().count(token) for token in external_tokens
    }
    return probe


def records_containing(probe: dict[str, Any], term: str) -> list[dict[str, Any]]:
    expected = term.casefold()
    return [
        row
        for row in probe.get("records", [])
        if expected in str(row.get("label", "")).casefold()
    ]


def exact_record(
    records: list[dict[str, Any]],
    term: str,
) -> dict[str, Any] | None:
    matches = records_containing({"records": records}, term)
    return matches[0] if len(matches) == 1 else None


def geometry_gates(
    probe: dict[str, Any],
    source_values: dict[str, Any],
    interface_registry: dict[str, Any],
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    records = probe.get("records", [])
    valid = (
        probe.get("probe_status") == "PASS"
        and probe.get("root_valid") is True
        and int(probe.get("solid_count", 0)) > 0
        and not probe.get("invalid_solid_indices")
        and not probe.get("nonpositive_volume_solids")
        and probe.get("root_shape_type") in {"Compound", "CompSolid", "Solid"}
    )
    gates.append(
        gate(
            "STEP_INDEPENDENT_REOPEN_VALID_SOLIDS",
            "PASS" if valid else "FAIL",
            (
                "Fresh isolated Python/OCP process reopened a valid positive-volume "
                "STEP compound."
                if valid
                else "Fresh isolated Python/OCP process did not establish valid solids."
            ),
            {
                "probe_status": probe.get("probe_status"),
                "root_shape_type": probe.get("root_shape_type"),
                "root_valid": probe.get("root_valid"),
                "solid_count": probe.get("solid_count"),
                "invalid_solid_indices": probe.get("invalid_solid_indices"),
                "nonpositive_volume_solids": probe.get(
                    "nonpositive_volume_solids"
                ),
            },
            critical=True,
        )
    )

    required_labels = (
        "V22_MECHANICAL_CONTINUATION_ISOLATED",
        "MOD_PLATFORM_10_PRIMARY_STRUCTURE_FIDELITY_01A",
        "MOD_20_B601_ICD_AND_MOUNT_01",
        "MOD_30_ARM_STOW_01",
        "MOD_50_51_SOLAR_ROOT_01_AND_C5_NEGATIVE_PACKAGE",
        "MOD_60_90_FIDELITY_01A_EXTERNAL_INTERFACES",
        "B601_MOUNT_PLATE_WITH_B601_CENTRAL_INTERFACE_D100",
    )
    all_labels = {
        str(row.get("label", "")).casefold() for row in records
    } | {str(label).casefold() for label in probe.get("product_labels", [])}
    missing_labels = [
        label
        for label in required_labels
        if not any(label.casefold() in actual for actual in all_labels)
    ]
    gates.append(
        gate(
            "STEP_REQUIRED_MODULE_AND_INTERFACE_LABELS",
            "PASS" if not missing_labels else "FAIL",
            (
                "All required module/interface labels survived STEP export and reopen."
                if not missing_labels
                else "Required STEP labels are missing."
            ),
            {
                "required": list(required_labels),
                "missing": missing_labels,
                "label_count": len(all_labels),
            },
            critical=True,
        )
    )

    bbox = probe.get("bbox_size", [])
    plausible = (
        len(bbox) == 3
        and all(math.isfinite(float(value)) for value in bbox)
        and 300.0 <= float(bbox[0]) <= 1200.0
        and 226.3 <= float(bbox[1]) <= 600.0
        and 226.3 <= float(bbox[2]) <= 600.0
        and all(
            -2000.0 <= float(value) <= 2000.0
            for value in probe.get("bbox_min", []) + probe.get("bbox_max", [])
        )
    )
    gates.append(
        gate(
            "STEP_BOUNDING_BOX_PLAUSIBLE_MM",
            "PASS" if plausible else "FAIL",
            "Millimetre-scale bounds are finite and plausible for the staged vehicle.",
            {
                "bbox_min_mm": probe.get("bbox_min"),
                "bbox_max_mm": probe.get("bbox_max"),
                "bbox_size_mm": bbox,
            },
            critical=True,
        )
    )

    plate_rows = records_containing(probe, "B601_MOUNT_PLATE_WITH_")
    plate = plate_rows[0] if len(plate_rows) == 1 else None
    plate_bbox_ok = bool(
        plate
        and bbox_matches(
            plate,
            (171.0, -80.0, -80.0),
            (183.0, 80.0, 80.0),
        )
    )
    cylinders = plate.get("cylindrical_faces", []) if plate else []
    central_cylinder_ok = any(
        approx(float(item.get("radius_mm", -1.0)), 50.0)
        and approx(abs(float(item.get("axis_direction", [0, 0, 0])[0])), 1.0)
        and approx(float(item.get("axis_direction", [0, 0, 0])[1]), 0.0)
        and approx(float(item.get("axis_direction", [0, 0, 0])[2]), 0.0)
        for item in cylinders
    )
    source_contract = {
        "MOUNT_PLATE_WIDTH_MM": source_values.get("MOUNT_PLATE_WIDTH_MM"),
        "MOUNT_PLATE_HEIGHT_MM": source_values.get("MOUNT_PLATE_HEIGHT_MM"),
        "MOUNT_PLATE_THICKNESS_MM": source_values.get(
            "MOUNT_PLATE_THICKNESS_MM"
        ),
        "CENTRAL_INTERFACE_DIAMETER_MM": source_values.get(
            "CENTRAL_INTERFACE_DIAMETER_MM"
        ),
    }
    source_ok = (
        source_contract["MOUNT_PLATE_WIDTH_MM"] == 160.0
        and source_contract["MOUNT_PLATE_HEIGHT_MM"] == 160.0
        and source_contract["MOUNT_PLATE_THICKNESS_MM"] == 12.0
        and source_contract["CENTRAL_INTERFACE_DIAMETER_MM"] == 100.0
    )
    registry_icd = (
        interface_registry.get("interfaces", {})
        .get("B601-ICD-01", {})
        .get("items", [])
    )
    registry_plate = next(
        (
            row.get("value")
            for row in registry_icd
            if row.get("parameter") == "mount_plate_overall_mm"
        ),
        None,
    )
    registry_diameter = next(
        (
            row.get("value")
            for row in registry_icd
            if row.get("parameter") == "central_interface_diameter_mm"
        ),
        None,
    )
    registry_ok = registry_plate == [160.0, 160.0, 12.0] and registry_diameter == 100.0
    icd_ok = plate_bbox_ok and central_cylinder_ok and source_ok and registry_ok
    gates.append(
        gate(
            "B601_ICD_160X160X12_AND_D100_SUBSTANTIATED",
            "PASS" if icd_ok else "FAIL",
            (
                "AST constants, interface registry, STEP plate bounds, and its "
                "X-axis cylindrical face independently substantiate the frozen ICD."
            ),
            {
                "source_contract": source_contract,
                "registry_mount_plate_mm": registry_plate,
                "registry_central_interface_diameter_mm": registry_diameter,
                "step_plate_bbox_min_mm": plate.get("bbox_min") if plate else None,
                "step_plate_bbox_max_mm": plate.get("bbox_max") if plate else None,
                "step_plate_cylindrical_faces": cylinders,
                "plate_record_count": len(plate_rows),
            },
            critical=True,
        )
    )

    web_expected = {
        "B601_LOAD_PATH_WEB_NY": (
            (171.0, -98.15, -7.5),
            (183.0, -80.0, 7.5),
        ),
        "B601_LOAD_PATH_WEB_PY": (
            (171.0, 80.0, -7.5),
            (183.0, 98.15, 7.5),
        ),
        "B601_LOAD_PATH_WEB_NZ": (
            (171.0, -7.5, -98.15),
            (183.0, 7.5, -80.0),
        ),
        "B601_LOAD_PATH_WEB_PZ": (
            (171.0, -7.5, 80.0),
            (183.0, 7.5, 98.15),
        ),
    }
    web_checks: dict[str, Any] = {}
    for term, (expected_min, expected_max) in web_expected.items():
        matching = records_containing(probe, term)
        web_checks[term] = {
            "record_count": len(matching),
            "bbox_match": (
                len(matching) == 1
                and bbox_matches(matching[0], expected_min, expected_max)
            ),
            "bbox_min_mm": matching[0].get("bbox_min") if matching else None,
            "bbox_max_mm": matching[0].get("bbox_max") if matching else None,
        }
    web_source_ok = (
        source_values.get("FROZEN_B601_MOUNT_PLATE_X") == (171.0, 183.0)
        and source_values.get("FROZEN_B601_MOUNT_PLATE_SIZE") == 160.0
        and source_values.get("SOURCE_B5_INNER_HALF_YZ") == 98.15
    )
    webs_ok = web_source_ok and all(
        row["bbox_match"] for row in web_checks.values()
    )
    gates.append(
        gate(
            "B601_MOUNT_FOUR_WAY_WEB_GEOMETRY",
            "PASS" if webs_ok else "FAIL",
            (
                "Four staging webs occupy X=171..183 mm and bridge the ±80 mm "
                "plate edges to the ±98.15 mm task-frame inner boundary."
            ),
            {
                "source_values_match": web_source_ok,
                "web_checks": web_checks,
            },
            critical=True,
        )
    )

    spine_expected = {
        "SOLAR_ROOT_NODE_SPINE_L": (
            (-67.0, 110.15, -75.0),
            (-55.0, 121.15, 75.0),
        ),
        "SOLAR_ROOT_NODE_SPINE_R": (
            (-67.0, -121.15, -75.0),
            (-55.0, -110.15, 75.0),
        ),
    }
    spine_checks: dict[str, Any] = {}
    for term, (expected_min, expected_max) in spine_expected.items():
        matching = records_containing(probe, term)
        spine_checks[term] = {
            "record_count": len(matching),
            "bbox_match": (
                len(matching) == 1
                and bbox_matches(matching[0], expected_min, expected_max)
            ),
            "bbox_min_mm": matching[0].get("bbox_min") if matching else None,
            "bbox_max_mm": matching[0].get("bbox_max") if matching else None,
        }
    spines_ok = all(row["bbox_match"] for row in spine_checks.values())
    gates.append(
        gate(
            "SOLAR_ROOT_NODE_SPINES_GEOMETRY_PRESENT",
            "PASS" if spines_ok else "FAIL",
            "Both staging-only node spines match the registered proposal envelopes.",
            spine_checks,
            critical=True,
        )
    )

    platform = exact_record(records, "MOD_PLATFORM_10_PRIMARY_STRUCTURE_FIDELITY_01A")
    wing_module = exact_record(
        records, "MOD_50_51_SOLAR_ROOT_01_AND_C5_NEGATIVE_PACKAGE"
    )
    wing_parts = records_containing(probe, "SOLAR_WING_")
    if wing_parts:
        y_min = min(float(row["bbox_min"][1]) for row in wing_parts)
        y_max = max(float(row["bbox_max"][1]) for row in wing_parts)
        panel_width = y_max - y_min
    else:
        y_min = y_max = panel_width = None
    source_c5 = {
        "required_mm": source_values.get("C5_REQUIRED_MM"),
        "available_mm": source_values.get("C5_AVAILABLE_MM"),
    }
    registry_c5 = interface_registry.get("interfaces", {}).get(
        "C5-PACKAGE-01", {}
    )
    c5_ok = (
        source_c5 == {"required_mm": 238.3, "available_mm": 226.3}
        and source_c5["required_mm"] > source_c5["available_mm"]
        and approx(float(source_c5["required_mm"] - source_c5["available_mm"]), 12.0)
        and platform is not None
        and approx(float(platform["bbox_size"][1]), 226.3)
        and panel_width is not None
        and approx(panel_width, 238.3)
        and wing_module is not None
        and approx(float(wing_module["bbox_size"][1]), 302.3)
        and registry_c5.get("closure_claim") is False
    )
    gates.append(
        gate(
            "C5_NEGATIVE_RELATION_GEOMETRICALLY_PRESERVED",
            "PASS" if c5_ok else "FAIL",
            (
                "Panel package remains 238.3 mm > 226.3 mm (12.0 mm over); "
                "solar-root mechanism lower-bound geometry remains 302.3 mm."
            ),
            {
                "source_contract": source_c5,
                "bus_geometry_width_mm": (
                    platform.get("bbox_size", [None, None, None])[1]
                    if platform
                    else None
                ),
                "stowed_panel_union_y_mm": [y_min, y_max],
                "stowed_panel_union_width_mm": panel_width,
                "solar_root_module_width_mm": (
                    wing_module.get("bbox_size", [None, None, None])[1]
                    if wing_module
                    else None
                ),
                "registry": registry_c5,
            },
            critical=True,
        )
    )

    external_counts = probe.get("external_reference_token_counts", {})
    self_contained = (
        probe.get("probe_status") == "PASS"
        and all(int(count) == 0 for count in external_counts.values())
    )
    gates.append(
        gate(
            "STEP_SELF_CONTAINED_DEPENDENCY_CLOSURE",
            "PASS" if self_contained else "FAIL",
            (
                "The STEP reopened from an empty temporary working directory and "
                "contains no external-reference entities."
            ),
            {
                "reopen_working_directory": "fresh_empty_temporary_directory",
                "external_reference_token_counts": external_counts,
            },
            critical=True,
        )
    )
    return gates


def markdown_report(payload: dict[str, Any]) -> str:
    gates = payload["gates"]
    counts = Counter(row["status"] for row in gates)
    step = payload.get("step_validation", {})
    resource = payload["phase_b_resource_gate"]
    memory = resource["memory"]
    lines = [
        "# V22 mechanical continuation independent validation",
        "",
        f"- Overall status: `{payload['overall']}`",
        f"- Machine verdict: `{payload['machine_verdict']}`",
        f"- Validated UTC: `{payload['validated_utc']}`",
        "- Scope: isolated STEP continuation only; canonical V2.2 top remained read-only.",
        (
            f"- Gate counts: PASS={counts.get('PASS', 0)}, "
            f"HOLD={counts.get('HOLD', 0)}, FAIL={counts.get('FAIL', 0)}, "
            f"NOT_APPLICABLE={counts.get('NOT_APPLICABLE', 0)}."
        ),
        "",
        "## Gate results",
        "",
        "| Gate | Status | Evidence-backed conclusion |",
        "|---|---:|---|",
    ]
    for row in gates:
        summary = str(row["summary"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{row['id']}` | **{row['status']}** | {summary} |")

    lines.extend(
        [
            "",
            "## Independent geometry facts",
            "",
            (
                f"- STEP: `{step.get('path')}`, SHA-256 "
                f"`{step.get('sha256')}`, {step.get('solid_count')} positive-volume "
                "solids."
            ),
            (
                f"- Reopened bounds (mm): min `{step.get('bbox_min')}`, max "
                f"`{step.get('bbox_max')}`, size `{step.get('bbox_size')}`."
            ),
            (
                "- Frozen B601 interface is supported by source constants, the "
                "interface registry, a 12×160×160 mm STEP plate bound, and an "
                "X-axis cylindrical face of radius 50 mm."
            ),
            (
                "- C5 stays negative: panel package 238.3 mm exceeds the "
                "226.3 mm bus width by 12.0 mm; root-mechanism lower-bound "
                "geometry is 302.3 mm wide."
            ),
            "",
            "## Phase-B visible-recovery resource gate",
            "",
            (
                f"- Verdict: `{resource['verdict']}`. Available physical memory "
                f"{memory['available_physical_gib']:.3f} GiB (threshold 4 GiB); "
                f"commit headroom {memory['commit_headroom_gib']:.3f} GiB "
                "(threshold 8 GiB)."
            ),
            (
                "- Threshold authority: "
                "`PROJECT_CONSERVATIVE_RECOMMENDATION_NOT_VENDOR_SPEC`."
            ),
            (
                "- Read-only capture only: no SolidWorks/sldProcMon process was "
                "started or stopped."
            ),
            "",
            "## Claim boundary",
            "",
            (
                "- `B601_FULL_HIFI_358_COMPONENT_ROUTE` remains HOLD; the "
                "registered vendor STEP is unchanged and is not embedded here."
            ),
            (
                "- The accepted URDF remains the only kinematic/mass authority; "
                "the staged visual continuation declares mass authority excluded."
            ),
            (
                "- SolidWorks configuration/BOM readback is NOT_APPLICABLE to "
                "this static STEP and was not claimed."
            ),
            (
                "- Strength, stiffness, launch-load, release reliability, "
                "manufacturability, and tolerance qualification were not run and "
                "remain HOLD."
            ),
            (
                "- `SOLAR-ROOT-01` engineering closure and `C5-PACKAGE-01` closure "
                "remain HOLD despite their geometry-presence checks passing."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    phase_before = phase_a_fingerprints()
    resource_gate = collect_resource_gate()
    gates: list[dict[str, Any]] = []

    required_inputs = (
        GENERATOR,
        PRIMARY_STEP,
        BRIEF,
        INTERFACE_REGISTRY,
        CONFIGURATION_POLICY,
        URDF,
        CANONICAL_TOP,
        *(EVIDENCE / name for name in PHASE_A_NAMES),
    )
    missing = [str(path) for path in required_inputs if not path.is_file()]
    gates.append(
        gate(
            "REQUIRED_VALIDATION_INPUTS_PRESENT",
            "PASS" if not missing else "FAIL",
            "All independent validation inputs are present.",
            {"missing": missing},
            critical=True,
        )
    )
    if missing:
        raise ValidationError(f"required inputs missing: {missing}")

    manifest_results, index_results = source_rechecks()
    control_state = phase_a_control_state()
    baselines_ok = (
        all(row["status"] == "UNCHANGED" for row in manifest_results)
        and all(row["match"] for row in index_results)
        and control_state["index_machine_verdict"]
        == "PHASE_A_PRE_RUN_MANIFESTS_CAPTURED_PASS"
        and control_state["validation_machine_verdict"]
        == "PHASE_A_PRE_RUN_MANIFESTS_VALIDATED_PASS"
        and control_state["validation_overall"] == "PASS"
    )
    gates.append(
        gate(
            "PHASE_A_BASELINES_AND_FROZEN_ZONES_UNCHANGED",
            "PASS" if baselines_ok else "FAIL",
            "All six captured source sets and their indexed manifests match Phase A.",
            {
                "source_manifest_rechecks": manifest_results,
                "indexed_manifest_rechecks": index_results,
                "phase_a_control_state": control_state,
            },
            critical=True,
        )
    )

    canonical_manifest = read_json(
        EVIDENCE / "pre_run_03_v22_authoritative_top.json"
    )
    canonical_expected = canonical_manifest["files"][0]
    canonical_current = fingerprint(CANONICAL_TOP)
    canonical_hash_ok = (
        canonical_current.get("sha256") == canonical_expected.get("sha256")
        and canonical_current.get("bytes") == canonical_expected.get("bytes")
    )
    captured_mtime = datetime.fromisoformat(
        canonical_expected["mtime_utc"]
    ).timestamp()
    canonical_mtime_ok = abs(
        CANONICAL_TOP.stat().st_mtime - captured_mtime
    ) < 1.0e-6
    interface_registry = read_yaml(INTERFACE_REGISTRY)
    canonical_declaration_ok = (
        interface_registry.get("canonical_top_write") is False
    )
    canonical_ok = (
        canonical_hash_ok and canonical_mtime_ok and canonical_declaration_ok
    )
    gates.append(
        gate(
            "CANONICAL_V22_TOP_NO_WRITE",
            "PASS" if canonical_ok else "FAIL",
            "Canonical top content, size, and mtime match Phase A; staging declares no write.",
            {
                "expected": canonical_expected,
                "current": canonical_current,
                "mtime_match": canonical_mtime_ok,
                "interface_registry_canonical_top_write": (
                    interface_registry.get("canonical_top_write")
                ),
            },
            critical=True,
        )
    )

    urdf = urdf_mass()
    accepted_manifest = read_json(EVIDENCE / "pre_run_05_accepted_b601_12.json")
    captured_urdf = next(
        row
        for row in accepted_manifest["files"]
        if str(row["relative_path"]).casefold().endswith(".urdf")
    )
    urdf_ok = (
        urdf["exact_decimal_match"]
        and urdf["sha256"] == captured_urdf["sha256"]
        and urdf["inertial_count"] > 0
    )
    gates.append(
        gate(
            "ACCEPTED_URDF_MASS_AUTHORITY_UNCHANGED",
            "PASS" if urdf_ok else "FAIL",
            "Accepted URDF hash matches and inertial masses sum exactly to 4.6955559493429862 kg.",
            urdf,
            critical=True,
        )
    )

    registered_manifest = read_json(EVIDENCE / "pre_run_06_registered_step.json")
    registered_expected = registered_manifest["files"][0]
    registered_current = fingerprint(Path(registered_expected["absolute_path"]))
    registered_ok = (
        registered_current.get("sha256") == registered_expected.get("sha256")
        and registered_current.get("bytes") == registered_expected.get("bytes")
        and registered_expected.get("baseline_match") is True
    )
    gates.append(
        gate(
            "REGISTERED_VENDOR_STEP_UNCHANGED",
            "PASS" if registered_ok else "FAIL",
            "Exact registered vendor STEP still matches its captured SHA-256 and byte count.",
            {
                "expected": registered_expected,
                "current": registered_current,
            },
            critical=True,
        )
    )

    source_values = literal_assignments(GENERATOR)
    configuration_policy = read_yaml(CONFIGURATION_POLICY)
    visual_authority = interface_registry.get("authority", {}).get(
        "visual_mechanical_continuation", {}
    )
    hifi_authority = interface_registry.get("authority", {}).get(
        "b601_visual_hifi", {}
    )
    generator_text = GENERATOR.read_text(encoding="utf-8")
    mass_exclusion_ok = (
        visual_authority.get("mass_authority") == "EXCLUDED"
        and hifi_authority.get("mass_authority") == "EXCLUDED"
        and "MASS_AUTHORITY_EXCLUDED" in generator_text
        and "mass: EXCLUDED" in generator_text
    )
    gates.append(
        gate(
            "GENERATED_VISUAL_MASS_AUTHORITY_EXCLUDED",
            "PASS" if mass_exclusion_ok else "FAIL",
            "Visual continuation and future B601 HIFI both exclude mass authority.",
            {
                "visual_mechanical_continuation": visual_authority,
                "b601_visual_hifi": hifi_authority,
                "generator_declarations_found": {
                    "MASS_AUTHORITY_EXCLUDED": (
                        "MASS_AUTHORITY_EXCLUDED" in generator_text
                    ),
                    "mass: EXCLUDED": "mass: EXCLUDED" in generator_text,
                },
            },
            critical=True,
        )
    )

    states = configuration_policy.get("states", {})
    service = states.get("SERVICE", {})
    capture_safe = states.get("CAPTURE_SAFE", {})
    config_ok = (
        source_values.get("SERVICE_STATUS") == "PENDING_RATIFICATION"
        and source_values.get("CAPTURE_SAFE_STATUS")
        == "UNKNOWN_CANDIDATE_NOT_UPGRADED"
        and service.get("status") == "PENDING_RATIFICATION"
        and "PENDING_HUMAN_RATIFICATION" in {
            service.get("hifi"),
            service.get("q0_or_task_proxy"),
        }
        and str(capture_safe.get("status", "")).startswith("UNKNOWN_")
        and configuration_policy.get("applies_to_this_step") is False
    )
    gates.append(
        gate(
            "CONFIGURATION_POLICY_SERVICE_PENDING_CAPTURE_SAFE_UNKNOWN",
            "PASS" if config_ok else "FAIL",
            "SERVICE remains pending human ratification and CAPTURE_SAFE remains an unknown candidate.",
            {
                "source_service_status": source_values.get("SERVICE_STATUS"),
                "source_capture_safe_status": source_values.get(
                    "CAPTURE_SAFE_STATUS"
                ),
                "policy_service": service,
                "policy_capture_safe": capture_safe,
                "applies_to_this_step": configuration_policy.get(
                    "applies_to_this_step"
                ),
            },
            critical=True,
        )
    )

    probe = reopen_step(PRIMARY_STEP)
    gates.extend(geometry_gates(probe, source_values, interface_registry))

    process_gate_status = (
        "PASS"
        if resource_gate["verdict"].startswith("ELIGIBLE_")
        else "HOLD"
    )
    gates.append(
        gate(
            "PHASE_B_VISIBLE_RECOVERY_RESOURCE_GATE",
            process_gate_status,
            (
                "Resource thresholds are met; no process was started."
                if process_gate_status == "PASS"
                else "Visible recovery remains deferred because one or more "
                "project-conservative resource thresholds are not met."
            ),
            resource_gate,
        )
    )

    b601_hifi_status = (
        interface_registry.get("authority", {})
        .get("b601_visual_hifi", {})
        .get("current_status")
    )
    gates.extend(
        [
            gate(
                "B601_FULL_HIFI_358_COMPONENT_RECOVERY",
                "HOLD",
                "Registered geometry is unchanged but no full 358-component HIFI recovery is claimed.",
                {"registry_status": b601_hifi_status},
            ),
            gate(
                "SOLAR_ROOT_ENGINEERING_CLOSURE",
                "HOLD",
                "Root geometry is present, but joints, loads, deployment clearance, and reliability remain unqualified.",
            ),
            gate(
                "C5_PACKAGE_CLOSURE",
                "HOLD",
                "The preserved 238.3 > 226.3 mm result is negative; no package closure is claimed.",
            ),
            gate(
                "SOLIDWORKS_CONFIGURATION_READBACK",
                "NOT_APPLICABLE",
                "Static STEP contains no native SolidWorks configuration/suppression semantics.",
            ),
            gate(
                "SOLIDWORKS_BOM_AND_MASS_EXCLUSION_READBACK",
                "NOT_APPLICABLE",
                "Static STEP cannot establish native BOM or property readback.",
            ),
            gate(
                "STRUCTURAL_STRENGTH_AND_STIFFNESS_QUALIFICATION",
                "HOLD",
                "No FEA, launch-load case, stiffness, or fatigue analysis was performed.",
            ),
            gate(
                "MANUFACTURING_TOLERANCE_AND_RELEASE_QUALIFICATION",
                "HOLD",
                "No manufacturing, tolerance, fastener, HDRM, or release qualification was performed.",
            ),
        ]
    )

    phase_after = phase_a_fingerprints()
    phase_files_untouched = phase_before == phase_after
    gates.append(
        gate(
            "PHASE_A_EIGHT_JSONS_UNTOUCHED_BY_VALIDATOR",
            "PASS" if phase_files_untouched else "FAIL",
            "All eight Phase-A JSON fingerprints are identical before and after validation reads.",
            {
                "before": phase_before,
                "after": phase_after,
            },
            critical=True,
        )
    )

    any_fail = any(row["status"] == "FAIL" for row in gates)
    critical_fail = any(
        row["status"] == "FAIL" and row["critical"] for row in gates
    )
    overall = "FAIL" if any_fail else "HOLD"
    machine_verdict = (
        "V22_MECHANICAL_CONTINUATION_VALIDATION_FAIL_CLOSED"
        if any_fail
        else "B601_RECOVERY02_HOLD_PLATFORM_MECHANICAL_CONTINUES"
    )
    payload = {
        "schema_version": "1.0",
        "validation_id": "V22_MECHANICAL_CONTINUATION_INDEPENDENT_VALIDATION_01",
        "decision_id": "V22_B601_CONTINUE_01",
        "validated_utc": utc_now(),
        "validation_mode": "READ_ONLY_FAIL_CLOSED_SEPARATE_PROCESS_STEP_REOPEN",
        "overall": overall,
        "critical_failure": critical_fail,
        "machine_verdict": machine_verdict,
        "status_counts": dict(Counter(row["status"] for row in gates)),
        "paths": {
            "generator": str(GENERATOR.resolve()),
            "primary_step": str(PRIMARY_STEP.resolve()),
            "interface_registry": str(INTERFACE_REGISTRY.resolve()),
            "configuration_policy": str(CONFIGURATION_POLICY.resolve()),
            "canonical_top": str(CANONICAL_TOP.resolve()),
            "accepted_urdf": str(URDF.resolve()),
        },
        "phase_a_evidence_fingerprints_before": phase_before,
        "phase_a_evidence_fingerprints_after": phase_after,
        "phase_a_source_rechecks": manifest_results,
        "phase_a_indexed_manifest_rechecks": index_results,
        "phase_a_control_state": control_state,
        "accepted_urdf_mass": urdf,
        "registered_vendor_step": {
            "expected": registered_expected,
            "current": registered_current,
        },
        "canonical_top": {
            "expected": canonical_expected,
            "current": canonical_current,
            "mtime_match": canonical_mtime_ok,
        },
        "source_literal_contract": {
            key: source_values.get(key)
            for key in (
                "MOUNT_PLATE_WIDTH_MM",
                "MOUNT_PLATE_HEIGHT_MM",
                "MOUNT_PLATE_THICKNESS_MM",
                "CENTRAL_INTERFACE_DIAMETER_MM",
                "C5_REQUIRED_MM",
                "C5_AVAILABLE_MM",
                "SERVICE_STATUS",
                "CAPTURE_SAFE_STATUS",
                "FROZEN_B601_MOUNT_PLATE_X",
                "FROZEN_B601_MOUNT_PLATE_SIZE",
                "SOURCE_B5_INNER_HALF_YZ",
            )
        },
        "step_validation": probe,
        "phase_b_resource_gate": resource_gate,
        "gates": gates,
        "claim_limits": {
            "solidworks_configuration_readback": "NOT_APPLICABLE_NOT_RUN",
            "solidworks_bom_readback": "NOT_APPLICABLE_NOT_RUN",
            "strength": "HOLD_NOT_ANALYZED",
            "stiffness": "HOLD_NOT_ANALYZED",
            "launch_loads": "HOLD_UNKNOWN",
            "manufacturability": "HOLD_NOT_ASSESSED",
            "tolerances": "HOLD_TBD",
            "solar_root_engineering_closure": "HOLD",
            "c5_package_closure": "HOLD_NEGATIVE_PRESERVED",
        },
    }

    resource_bytes = json_bytes(resource_gate)
    payload["phase_b_resource_gate_artifact"] = {
        "path": str(RESOURCE_OUTPUT.resolve()),
        "bytes": len(resource_bytes),
        "sha256": hashlib.sha256(resource_bytes).hexdigest(),
    }
    validation_bytes = json_bytes(payload)
    report_bytes = markdown_report(payload).encode("utf-8")

    atomic_write(RESOURCE_OUTPUT, resource_bytes)
    atomic_write(JSON_OUTPUT, validation_bytes)
    atomic_write(REPORT_OUTPUT, report_bytes)

    print(
        json.dumps(
            {
                "overall": overall,
                "machine_verdict": machine_verdict,
                "status_counts": payload["status_counts"],
                "resource_verdict": resource_gate["verdict"],
                "json_output": str(JSON_OUTPUT),
                "report_output": str(REPORT_OUTPUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if any_fail else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"V22_VALIDATION_FAIL_CLOSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
