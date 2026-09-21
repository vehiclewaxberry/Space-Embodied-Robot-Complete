"""Guarded STEP-first generator for the non-current D01 q0 diagnostic branch.

The module is deliberately source-only in this release.  CAD imports occur
inside ``gen_step`` only after source hashes, a fresh run id, and memory
admission (or a run-bound Owner Override) pass.  Running this file directly
never imports a CAD kernel and never writes STEP.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DISPLAY_NAME = "D01 R2 Solar + B601 Fixed-q0 Diagnostic V1"
PACKAGE = Path(__file__).resolve().parent
CONTRACT_PATH = PACKAGE / "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml"
SOURCE_LOCK_PATH = PACKAGE / "SOURCE_AUTHORITY_LOCK_V1.json"
OUTPUT_STEP_PATH = PACKAGE / "D01_R2_SOLAR_B601_FIXED_Q0_DIAGNOSTIC_V1.step"
EXECUTION_RECEIPT_PATH = PACKAGE / "D01_R2_SOLAR_B601_FIXED_Q0_EXECUTION_RECEIPT_V1.json"
ACTIVE_LOCK_PATH = PACKAGE / ".d01_geometry_active_run.lock"

MEMORY_GATE_GIB = 6.0
REQUIRED_RISK_ACK = "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK"
MAX_OVERRIDE_VALIDITY_SECONDS = 7200.0
EXPECTED_MASTER_SOLIDS = 41
EXPECTED_SOLAR_SOLIDS = 22
EXPECTED_B601_SOLIDS = 388
EXPECTED_OUTPUT_SOLIDS = 403
MASTER_INDICES = (1, 2, 3, 4, 5, 6, 27, 28, 41)
SOLAR_INDICES = (7, 8, 9, 10, 11, 12)
GEOMETRY_SOURCE_IDS = ("SRC03_MASTER_STEP", "SRC08_FULL_B601_Q0_STEP", "SRC20_SOLAR_R2_STEP")
REASON_NOT_C01_CURRENT = "STATIC_CAD_Q0_CANNOT_STAND_IN_FOR_C01_QHOME"


def _workspace_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("WORKSPACE_ROOT_NOT_FOUND")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise RuntimeError(f"DUPLICATE_KEY:{path.name}:{key}")
            result[key] = value
        return result

    def reject_constant(value: str):
        raise RuntimeError(f"NONFINITE_JSON_CONSTANT:{path.name}:{value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=reject_constant,
    )


def _verify_sources() -> tuple[dict[str, Any], dict[str, Path]]:
    contract = _strict_json(CONTRACT_PATH)
    source_lock = _strict_json(SOURCE_LOCK_PATH)
    by_id = {row["id"]: row for row in source_lock["sources"]}
    if len(by_id) != source_lock["source_count"]:
        raise RuntimeError("SOURCE_LOCK_DUPLICATE_ID")
    root = _workspace_root()
    resolved: dict[str, Path] = {}
    for source_id in GEOMETRY_SOURCE_IDS:
        row = by_id[source_id]
        path = root / row["path"]
        if not path.is_file():
            raise FileNotFoundError(f"PINNED_SOURCE_MISSING:{source_id}")
        if path.stat().st_size != row["bytes"]:
            raise RuntimeError(f"PINNED_SOURCE_BYTES_CHANGED:{source_id}")
        if _sha256(path) != row["sha256"]:
            raise RuntimeError(f"PINNED_SOURCE_SHA256_CHANGED:{source_id}")
        resolved[source_id] = path
    return contract, resolved


def _available_memory_gib() -> float | None:
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullAvailPhys / (1024.0**3)
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_AVPHYS_PAGES")) / (1024.0**3)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _safe_id(value: str, field: str) -> str:
    text = value.strip()
    if not (12 <= len(text) <= 128) or any(not (ch.isalnum() or ch in "-_.:") for ch in text):
        raise RuntimeError(f"{field}_INVALID")
    return text


def _parse_utc(value: str, field: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RuntimeError(f"{field}_INVALID_UTC") from exc
    if parsed.tzinfo is None:
        raise RuntimeError(f"{field}_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _execution_authority() -> dict[str, Any]:
    if os.environ.get("M4_GEOM_EXECUTION_AUTHORIZED", "").strip().upper() != "YES":
        raise RuntimeError("GENERATION_NOT_AUTHORIZED_SOURCE_ONLY")
    run_id = _safe_id(os.environ.get("M4_GEOM_RUN_ID", ""), "M4_GEOM_RUN_ID")
    if OUTPUT_STEP_PATH.exists() and os.environ.get("M4_GEOM_ALLOW_OVERWRITE", "").strip().upper() != "YES":
        raise FileExistsError("OUTPUT_EXISTS_NO_OVERWRITE_AUTHORITY")
    if ACTIVE_LOCK_PATH.exists():
        raise RuntimeError("ACTIVE_WRITER_LOCK_PRESENT")

    available = _available_memory_gib()
    memory_pass = available is not None and available >= MEMORY_GATE_GIB
    override = None
    if not memory_pass:
        override_id = _safe_id(os.environ.get("M4_GEOM_OWNER_OVERRIDE_ID", ""), "M4_GEOM_OWNER_OVERRIDE_ID")
        if os.environ.get("M4_GEOM_OWNER_OVERRIDE_RISK_ACK", "").strip() != REQUIRED_RISK_ACK:
            raise RuntimeError("LOW_MEMORY_RISK_NOT_ACKNOWLEDGED")
        issued = _parse_utc(os.environ.get("M4_GEOM_OWNER_OVERRIDE_ISSUED_UTC", ""), "ISSUED_UTC")
        expires = _parse_utc(os.environ.get("M4_GEOM_OWNER_OVERRIDE_EXPIRES_UTC", ""), "EXPIRES_UTC")
        now = datetime.now(timezone.utc)
        validity = (expires - issued).total_seconds()
        if not (issued <= now < expires):
            raise RuntimeError("LOW_MEMORY_OVERRIDE_NOT_CURRENT")
        if not (0.0 < validity <= MAX_OVERRIDE_VALIDITY_SECONDS):
            raise RuntimeError("LOW_MEMORY_OVERRIDE_VALIDITY_TOO_LONG")
        if os.environ.get("M4_GEOM_OWNER_OVERRIDE_RUN_ID", "").strip() != run_id:
            raise RuntimeError("LOW_MEMORY_OVERRIDE_NOT_BOUND_TO_RUN")
        override = {
            "id_sha256": hashlib.sha256(override_id.encode("utf-8")).hexdigest().upper(),
            "issued_utc": issued.isoformat(),
            "expires_utc": expires.isoformat(),
            "risk_ack": REQUIRED_RISK_ACK,
        }

    authority = {
        "schema": "M4_L01_L02_D01_PREIMPORT_AUTHORITY_V1",
        "run_id_sha256": hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper(),
        "available_physical_memory_gib": available,
        "memory_gate_gib": MEMORY_GATE_GIB,
        "memory_gate_passed": memory_pass,
        "owner_override_used": override is not None,
        "owner_override": override,
        "configuration_current": False,
        "release_credit": False,
    }
    with ACTIVE_LOCK_PATH.open("x", encoding="utf-8") as stream:
        json.dump(authority, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return authority


def gen_step():
    contract, sources = _verify_sources()
    authority = _execution_authority()

    # Delayed CAD imports: no kernel is loaded until every source and run gate passes.
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepGProp import BRepGProp
    from OCP.Bnd import Bnd_Box
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Trsf
    from build123d import Color, Compound, Solid, export_step

    def read_shape(path: Path):
        reader = STEPControl_Reader()
        if reader.ReadFile(str(path)) != IFSelect_RetDone:
            raise RuntimeError(f"STEP_READ_FAILED:{path}")
        if int(reader.TransferRoots()) < 1:
            raise RuntimeError(f"STEP_TRANSFER_FAILED:{path}")
        shape = reader.OneShape()
        if shape.IsNull():
            raise RuntimeError(f"STEP_NULL_SHAPE:{path}")
        return shape

    def solids(shape) -> list:
        result = []
        explorer = TopExp_Explorer(shape, TopAbs_SOLID)
        while explorer.More():
            result.append(TopoDS.Solid_s(explorer.Current()))
            explorer.Next()
        return result

    def volume_mm3(shape) -> float:
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, props)
        return float(props.Mass())

    def bounds_mm(items: list) -> list[float]:
        box = Bnd_Box()
        for item in items:
            BRepBndLib.AddOptimal_s(item, box, False, True)
        return [float(value) for value in box.Get()]

    master = solids(read_shape(sources["SRC03_MASTER_STEP"]))
    solar = solids(read_shape(sources["SRC20_SOLAR_R2_STEP"]))
    arm = solids(read_shape(sources["SRC08_FULL_B601_Q0_STEP"]))
    if len(master) != EXPECTED_MASTER_SOLIDS:
        raise RuntimeError("MASTER_SOLID_COUNT_CHANGED")
    if len(solar) != EXPECTED_SOLAR_SOLIDS:
        raise RuntimeError("SOLAR_SOLID_COUNT_CHANGED")
    if len(arm) != EXPECTED_B601_SOLIDS:
        raise RuntimeError("B601_SOLID_COUNT_CHANGED")

    selected_master = [master[index - 1] for index in MASTER_INDICES]
    for expected, shape in zip(contract["master_retained"], selected_master, strict=True):
        actual = volume_mm3(shape)
        tolerance = max(1.0e-3, abs(expected["volume_mm3"]) * 5.0e-9)
        if not math.isfinite(actual) or abs(actual - expected["volume_mm3"]) > tolerance:
            raise RuntimeError(f"MASTER_TRAVERSAL_DRIFT:{expected['index']}")

    selected_solar = [solar[index - 1] for index in SOLAR_INDICES]
    for expected, shape in zip(contract["solar_selected"], selected_solar, strict=True):
        actual_volume = volume_mm3(shape)
        actual_bbox = bounds_mm([shape])
        if not math.isfinite(actual_volume) or abs(actual_volume - expected["volume_mm3"]) > 1.0e-3:
            raise RuntimeError(f"SOLAR_TRAVERSAL_VOLUME_DRIFT:{expected['index']}")
        if any(abs(a - b) > 0.01 for a, b in zip(actual_bbox, expected["bbox_S_mm"], strict=True)):
            raise RuntimeError(f"SOLAR_TRAVERSAL_BBOX_DRIFT:{expected['index']}")

    rows = contract["placements"]["B601_FIXED_Q0_LOCAL_TO_S_ROWS_MM"]
    transform = gp_Trsf()
    transform.SetValues(
        rows[0][0], rows[0][1], rows[0][2], rows[0][3],
        rows[1][0], rows[1][1], rows[1][2], rows[1][3],
        rows[2][0], rows[2][1], rows[2][2], rows[2][3],
    )
    installed_arm = [BRepBuilderAPI_Transform(shape, transform, True).Shape() for shape in arm]

    installed_min_x = bounds_mm(installed_arm)[0]
    master_m3r_outer_x = bounds_mm([master[27]])[3]
    datum = contract["expected"]["m3r_arm_datum"]
    if abs(installed_min_x - master_m3r_outer_x) > datum["absolute_tolerance_mm"]:
        raise RuntimeError("M3R_B601_DATUM_MISMATCH")

    core_children = []
    for expected, shape in zip(contract["master_retained"], selected_master, strict=True):
        wrapped = Solid.cast(shape)
        wrapped.label = f"MASTER_S{expected['index']:02d}_{expected['label']}"
        wrapped.material = "PINNED_MASTER_CORE__NO_MASS_AUTHORITY"
        wrapped.color = Color(0.67, 0.70, 0.74, 1.0)
        core_children.append(wrapped)

    solar_children = []
    for expected, shape in zip(contract["solar_selected"], selected_solar, strict=True):
        wrapped = Solid.cast(shape)
        wrapped.label = expected["label"]
        wrapped.material = "SOLAR_R2_DEPLOYED_LEAF_ENGINEERING_CANDIDATE__NO_HDRM_HARDWARE"
        wrapped.color = Color(0.10, 0.30, 0.63, 1.0)
        solar_children.append(wrapped)

    arm_children = []
    for index, shape in enumerate(installed_arm, start=1):
        wrapped = Solid.cast(shape)
        wrapped.label = f"B601_FIXED_Q0_SOLID_{index:03d}"
        wrapped.material = "B50_FIXED_Q0_VISUAL_REFERENCE__NO_RETAINED_DOF_OR_CONTACT_AUTHORITY"
        wrapped.color = Color(0.78, 0.80, 0.83, 1.0)
        arm_children.append(wrapped)

    core_group = Compound(children=core_children, label="R2_SERVICER_CORE_WITHOUT_LEGACY_SOLAR_AXIS_WITNESS_OR_DETACHED_PALM")
    solar_group = Compound(children=solar_children, label="SOLAR_R2_DEPLOYED_LEAVES_ONLY")
    arm_group = Compound(children=arm_children, label="B601_FULL_ARM_FIXED_Q0_INSTALLED")
    result = Compound(children=[core_group, solar_group, arm_group], label=contract["branch_id"])
    result.material = "DIAGNOSTIC_ONLY;UNITS_MM;NOT_C01_CURRENT;NO_COLLISION_CONTACT_MASS_PRODUCTION_OR_RELEASE_AUTHORITY"

    if len(result.solids()) != EXPECTED_OUTPUT_SOLIDS:
        raise RuntimeError("D01_SOLID_COUNT_FAILED")
    actual = result.bounding_box()
    actual_bbox = [actual.min.X, actual.min.Y, actual.min.Z, actual.max.X, actual.max.Y, actual.max.Z]
    expected_bbox = contract["expected"]["bbox_S_mm"]
    expected_flat = expected_bbox["min"] + expected_bbox["max"]
    if any(abs(a - b) > expected_bbox["absolute_tolerance_mm"] for a, b in zip(actual_bbox, expected_flat, strict=True)):
        raise RuntimeError("D01_BBOX_FAILED")

    export_step(result, OUTPUT_STEP_PATH)
    receipt = {
        "schema": "M4_L01_L02_D01_EXECUTION_RECEIPT_V1",
        "authority": authority,
        "output": {
            "path": OUTPUT_STEP_PATH.name,
            "bytes": OUTPUT_STEP_PATH.stat().st_size,
            "sha256": _sha256(OUTPUT_STEP_PATH),
            "expected_solid_count": EXPECTED_OUTPUT_SOLIDS,
            "expected_group_count": 3,
            "bbox_S_mm": actual_bbox,
        },
        "configuration_current": False,
        "reason_not_c01_current": REASON_NOT_C01_CURRENT,
        "collision_authority": False,
        "contact_authority": False,
        "mass_authority": False,
        "production_complete": False,
        "release_credit": False,
    }
    EXECUTION_RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ACTIVE_LOCK_PATH.unlink()
    return result


if __name__ == "__main__":
    raise SystemExit("SOURCE_ONLY: no CAD kernel loaded and no STEP generated; use a fresh authorized runner to call gen_step()")
