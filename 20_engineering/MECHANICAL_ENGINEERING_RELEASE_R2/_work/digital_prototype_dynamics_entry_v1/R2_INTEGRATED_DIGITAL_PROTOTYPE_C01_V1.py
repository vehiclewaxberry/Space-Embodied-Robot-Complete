"""Guarded STEP-first R2 servicer + full B601 fixed-q0 research candidate.

This generator does not modify the frozen R2 master STEP or the accepted B601
URDF.  It removes the master STEP's axis-witness and detached palm-overlay
solids, then installs the pinned B5.0 full-arm q0 B-rep at the frozen M3R mount
transform.  The output is a visual/assembly-positioning candidate only: its
fixed B-rep does not retain robot DOF, carry mass authority, close Route-C, or
authorize contact, path search, production dynamics, or flight release.

No CAD kernel is imported at module load.  ``gen_step()`` first verifies every
pinned source and then enforces fresh run-specific execution authority.  Below
6 GiB available physical memory it additionally consumes a fresh, time-bounded,
single-use Owner Override before any OCP/build123d import.
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


DISPLAY_NAME = "R2 Integrated Digital Prototype C01 V1 (Research Candidate)"
PACKAGE = Path(__file__).resolve().parent
INPUTS_PATH = PACKAGE / "INTEGRATED_CANDIDATE_INPUTS_V1.json"
OUTPUT_STEP_PATH = PACKAGE / "R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step"
ACTIVE_RUN_LOCK_PATH = PACKAGE / ".r2_integrated_candidate_active_run.lock"
RUN_CONSUMPTION_DIR = PACKAGE / ".r2_integrated_candidate_run_consumption"
OVERRIDE_CONSUMPTION_DIR = PACKAGE / ".r2_integrated_candidate_override_consumption"
AUTHORITY_RECEIPT_DIR = PACKAGE / "candidate_authority_receipts"

MEMORY_GATE_GIB = 6.0
MAX_OVERRIDE_VALIDITY_SECONDS = 7200.0
REQUIRED_LOW_MEMORY_RISK_ACK = "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK"
EXPECTED_SOURCE_SOLID_COUNT = 41
EXPECTED_ARM_SOLID_COUNT = 388
EXPECTED_OUTPUT_SOLID_COUNT = 399
RETAINED_ONE_BASED_INDICES = (1, 2, 3, 4, 5, 6, 7, 8, 27, 28, 41)


def _workspace_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("WORKSPACE_ROOT_NOT_FOUND: PROJECT_MAP.md is required")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json_exclusive(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")


def _parse_utc(value: str, field: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RuntimeError(f"LOW_MEMORY_OVERRIDE_INVALID_{field}: ISO-8601 UTC required") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError(f"LOW_MEMORY_OVERRIDE_INVALID_{field}: explicit UTC required")
    parsed = parsed.astimezone(timezone.utc)
    if parsed.utcoffset().total_seconds() != 0.0:
        raise RuntimeError(f"LOW_MEMORY_OVERRIDE_INVALID_{field}: UTC required")
    return parsed


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
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
        return page_size * available_pages / (1024.0**3)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _safe_identifier(name: str, field: str) -> str:
    value = name.strip()
    if not (12 <= len(value) <= 128) or any(
        not (character.isalnum() or character in "-_:.") for character in value
    ):
        raise RuntimeError(f"{field}_INVALID: expected a fresh 12..128 character safe identifier")
    return value


def _verify_inputs() -> tuple[dict[str, Any], dict[str, Path]]:
    inputs = json.loads(INPUTS_PATH.read_text(encoding="utf-8"))
    workspace = _workspace_root()
    resolved: dict[str, Path] = {}
    for key, record in inputs["sources"].items():
        path = workspace / Path(record["path"])
        if not path.is_file():
            raise FileNotFoundError(f"PINNED_SOURCE_MISSING: {path}")
        if path.stat().st_size != int(record["bytes"]):
            raise RuntimeError(f"PINNED_SOURCE_BYTE_COUNT_CHANGED: {key}")
        if _sha256(path) != str(record["sha256"]).upper():
            raise RuntimeError(f"PINNED_SOURCE_SHA256_CHANGED: {key}")
        resolved[key] = path
    if _sha256(INPUTS_PATH) == "":
        raise RuntimeError("INPUT_CONTRACT_HASH_UNAVAILABLE")
    return inputs, resolved


def _execution_authority(inputs: dict[str, Any], resolved: dict[str, Path]) -> dict[str, Any]:
    if os.environ.get("R2_DP_EXECUTION_AUTHORIZED", "").strip().upper() != "YES":
        raise RuntimeError(
            "GENERATION_NOT_AUTHORIZED_SOURCE_ONLY: set R2_DP_EXECUTION_AUTHORIZED=YES "
            "only for a fresh Owner-authorized run"
        )

    run_id = _safe_identifier(os.environ.get("R2_DP_RUN_ID", ""), "R2_DP_RUN_ID")
    if OUTPUT_STEP_PATH.exists() and os.environ.get("R2_DP_ALLOW_OVERWRITE", "").strip().upper() != "YES":
        raise FileExistsError(
            "CANDIDATE_OUTPUT_EXISTS_NO_OVERWRITE_AUTHORITY: set R2_DP_ALLOW_OVERWRITE=YES "
            "only for an explicitly authorized candidate reissue"
        )

    available_gib = _available_memory_gib()
    below_gate = available_gib is None or available_gib < MEMORY_GATE_GIB
    now = _utc_now()
    override_payload: dict[str, Any] | None = None
    if below_gate:
        override_id = _safe_identifier(
            os.environ.get("R2_DP_OWNER_OVERRIDE_ID", ""),
            "R2_DP_OWNER_OVERRIDE_ID",
        )
        risk_ack = os.environ.get("R2_DP_OWNER_OVERRIDE_RISK_ACK", "").strip()
        if risk_ack != REQUIRED_LOW_MEMORY_RISK_ACK:
            raise RuntimeError(
                "LOW_MEMORY_OVERRIDE_RISK_NOT_ACKNOWLEDGED: set "
                f"R2_DP_OWNER_OVERRIDE_RISK_ACK={REQUIRED_LOW_MEMORY_RISK_ACK}"
            )
        issued = _parse_utc(
            os.environ.get("R2_DP_OWNER_OVERRIDE_ISSUED_UTC", ""),
            "ISSUED_UTC",
        )
        expires = _parse_utc(
            os.environ.get("R2_DP_OWNER_OVERRIDE_EXPIRES_UTC", ""),
            "EXPIRES_UTC",
        )
        validity_seconds = (expires - issued).total_seconds()
        if not (issued <= now < expires):
            raise RuntimeError("LOW_MEMORY_OVERRIDE_NOT_CURRENT: current UTC must lie in [issued, expires)")
        if not (0.0 < validity_seconds <= MAX_OVERRIDE_VALIDITY_SECONDS):
            raise RuntimeError("LOW_MEMORY_OVERRIDE_VALIDITY_TOO_LONG: maximum validity is 7200 seconds")
        override_payload = {
            "owner_override_id": override_id,
            "owner_override_id_sha256": hashlib.sha256(override_id.encode("utf-8")).hexdigest().upper(),
            "issued_utc": _utc_text(issued),
            "expires_utc": _utc_text(expires),
            "validity_seconds": validity_seconds,
            "risk_ack": risk_ack,
            "risk_statement": (
                "Owner accepts elevated out-of-memory/process-instability risk for this single "
                "candidate-generation run; this does not alter any mechanical, scientific, "
                "contact, Sim13, production, or flight Gate."
            ),
        }

    run_digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper()
    run_marker = RUN_CONSUMPTION_DIR / f"{run_digest}.json"
    if run_marker.exists():
        raise RuntimeError("RUN_ID_ALREADY_CONSUMED: every candidate run ID is single-use")
    override_marker: Path | None = None
    if override_payload is not None:
        override_marker = OVERRIDE_CONSUMPTION_DIR / f"{override_payload['owner_override_id_sha256']}.json"
        if override_marker.exists():
            raise RuntimeError("LOW_MEMORY_OVERRIDE_ALREADY_CONSUMED: Owner Override IDs are single-use")

    lock_payload = {
        "schema": "R2_INTEGRATED_CANDIDATE_ACTIVE_WRITER_LOCK_V1",
        "run_id": run_id,
        "run_id_sha256": run_digest,
        "acquired_utc": _utc_text(now),
        "process_id": os.getpid(),
        "normal_release_condition": "STANDARD_CAD_TOOL_SUCCESS_AND_EXECUTION_RECEIPT_COMMITTED",
        "exception_policy": "RETAIN_FOR_OWNER_INSPECTION",
    }
    _write_json_exclusive(ACTIVE_RUN_LOCK_PATH, lock_payload)

    authority = {
        "schema": "R2_INTEGRATED_CANDIDATE_PREIMPORT_AUTHORITY_V1",
        "run_id": run_id,
        "run_id_sha256": run_digest,
        "authorized_utc": _utc_text(now),
        "available_physical_memory_gib": available_gib,
        "memory_gate_gib": MEMORY_GATE_GIB,
        "memory_gate_passed": not below_gate,
        "owner_override_used": override_payload is not None,
        "owner_override": override_payload,
        "input_contract": {
            "path": INPUTS_PATH.name,
            "sha256": _sha256(INPUTS_PATH),
        },
        "pinned_sources": {
            key: {
                "path": inputs["sources"][key]["path"],
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for key, path in resolved.items()
        },
        "claim_limit": inputs["scope"],
    }
    try:
        _write_json_exclusive(run_marker, authority)
        if override_marker is not None:
            override_record = dict(override_payload or {})
            override_record["consumed_utc"] = _utc_text(_utc_now())
            override_record["run_id_sha256"] = run_digest
            _write_json_exclusive(override_marker, override_record)
        receipt_path = AUTHORITY_RECEIPT_DIR / f"{run_digest}.json"
        _write_json_exclusive(receipt_path, authority)
    except Exception:
        # The active writer lock deliberately remains on every partial failure.
        raise
    return authority


def gen_step():
    inputs, resolved = _verify_inputs()
    _execution_authority(inputs, resolved)

    # CAD imports are intentionally delayed until all source and authority gates pass.
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepGProp import BRepGProp
    from OCP.Bnd import Bnd_Box
    from OCP.Font import Font_FontMgr
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TCollection import TCollection_AsciiString
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Trsf

    font_manager = Font_FontMgr.GetInstance_s()
    font_manager.AddFontAlias(
        TCollection_AsciiString("singleline"),
        TCollection_AsciiString("Arial"),
    )
    from build123d import Color, Compound, Solid

    def read_shape(path: Path):
        reader = STEPControl_Reader()
        if reader.ReadFile(str(path)) != IFSelect_RetDone:
            raise RuntimeError(f"STEP_READ_FAILED: {path}")
        transferred = int(reader.TransferRoots())
        shape = reader.OneShape()
        if transferred < 1 or shape.IsNull():
            raise RuntimeError(f"STEP_TRANSFER_FAILED: roots={transferred}, path={path}")
        return shape

    def solids(shape) -> list:
        result = []
        explorer = TopExp_Explorer(shape, TopAbs_SOLID)
        while explorer.More():
            result.append(TopoDS.Solid_s(explorer.Current()))
            explorer.Next()
        return result

    def volume_mm3(shape) -> float:
        properties = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, properties)
        return float(properties.Mass())

    def bounds_mm(shapes: list) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        box = Bnd_Box()
        for shape in shapes:
            BRepBndLib.AddOptimal_s(shape, box, False, True)
        values = tuple(float(value) for value in box.Get())
        return values[:3], values[3:]

    master_shape = read_shape(resolved["frozen_r2_master_geometry"])
    master_solids = solids(master_shape)
    if len(master_solids) != EXPECTED_SOURCE_SOLID_COUNT:
        raise RuntimeError(
            f"R2_MASTER_SOLID_COUNT_CHANGED: expected {EXPECTED_SOURCE_SOLID_COUNT}, found {len(master_solids)}"
        )

    selected = [master_solids[index - 1] for index in RETAINED_ONE_BASED_INDICES]
    expected_volumes = inputs["r2_master_filter_contract"]["retained_expected_volume_mm3"]
    for index, shape in zip(RETAINED_ONE_BASED_INDICES, selected, strict=True):
        expected = float(expected_volumes[str(index)])
        actual = volume_mm3(shape)
        tolerance = max(1.0e-3, abs(expected) * 5.0e-9)
        if not math.isfinite(actual) or abs(actual - expected) > tolerance:
            raise RuntimeError(
                f"R2_MASTER_TRAVERSAL_OR_GEOMETRY_DRIFT: s{index} volume {actual} != {expected} mm3"
            )

    arm_shape = read_shape(resolved["b601_fixed_q0_reference"])
    arm_solids = solids(arm_shape)
    if len(arm_solids) != EXPECTED_ARM_SOLID_COUNT:
        raise RuntimeError(
            f"B601_Q0_SOLID_COUNT_CHANGED: expected {EXPECTED_ARM_SOLID_COUNT}, found {len(arm_solids)}"
        )
    arm_source_bounds = bounds_mm(arm_solids)
    expected_arm_bounds = inputs["sources"]["b601_fixed_q0_reference"]["expected_local_bounds_mm"]
    for row, key in enumerate(("min", "max")):
        for axis in range(3):
            if abs(arm_source_bounds[row][axis] - float(expected_arm_bounds[key][axis])) > 0.01:
                raise RuntimeError("B601_Q0_LOCAL_BOUNDS_CHANGED")

    matrix = inputs["mounting_contract"]["row_major_homogeneous_transform_mm"]
    transform = gp_Trsf()
    transform.SetValues(
        float(matrix[0]), float(matrix[1]), float(matrix[2]), float(matrix[3]),
        float(matrix[4]), float(matrix[5]), float(matrix[6]), float(matrix[7]),
        float(matrix[8]), float(matrix[9]), float(matrix[10]), float(matrix[11]),
    )
    transformed_arm_solids = [
        BRepBuilderAPI_Transform(shape, transform, True).Shape()
        for shape in arm_solids
    ]

    datum = inputs["mounting_contract"]["datum_coincidence"]
    installed_arm_min_x = bounds_mm(transformed_arm_solids)[0][0]
    m3r_outer_x = bounds_mm([master_solids[27]])[1][0]
    datum_error = abs(installed_arm_min_x - m3r_outer_x)
    if datum_error > float(datum["absolute_tolerance_mm"]):
        raise RuntimeError(
            f"MOUNT_DATUM_COINCIDENCE_FAILED: error={datum_error:.9g} mm"
        )

    bus_color = Color(0.67, 0.70, 0.74, 1.0)
    solar_color = Color(0.10, 0.30, 0.63, 1.0)
    interface_color = Color(0.92, 0.55, 0.12, 1.0)
    arm_color = Color(0.78, 0.80, 0.83, 1.0)
    retained_labels = inputs["r2_master_filter_contract"]["retained_labels"]
    spacecraft_children = []
    for index, shape in zip(RETAINED_ONE_BASED_INDICES, selected, strict=True):
        wrapped = Solid.cast(shape)
        wrapped.label = f"R2_S{index:02d}_{retained_labels[str(index)]}"
        wrapped.color = solar_color if index in (7, 8) else interface_color if index in (27, 28, 41) else bus_color
        wrapped.material = "PINNED_R2_MASTER_BREP__RESEARCH_CANDIDATE_NO_MASS_AUTHORITY"
        spacecraft_children.append(wrapped)

    arm_children = []
    for index, shape in enumerate(transformed_arm_solids, start=1):
        wrapped = Solid.cast(shape)
        wrapped.label = f"B601_FIXED_Q0_SOLID_{index:03d}"
        wrapped.color = arm_color
        wrapped.material = "PINNED_B50_FIXED_Q0_BREP__NO_RETAINED_DOF__NO_MASS_OR_CONTACT_AUTHORITY"
        arm_children.append(wrapped)

    spacecraft_group = Compound(children=spacecraft_children, label="R2_SERVICER_WITHOUT_AXIS_WITNESS")
    spacecraft_group.material = "FROZEN_R2_GEOMETRY_FILTERED_BY_HASH_AND_TRAVERSAL_CONTRACT"
    arm_group = Compound(children=arm_children, label="B601_FULL_ARM_FIXED_Q0_INSTALLED")
    arm_group.material = "FIXED_Q0_VISUAL_AND_ASSEMBLY_POSITIONING_REFERENCE_ONLY"
    result = Compound(
        children=[spacecraft_group, arm_group],
        label="R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1_RESEARCH_CANDIDATE",
    )
    result.material = (
        "RESEARCH_CANDIDATE_ONLY;UNITS_MM;C01_DEPLOYED_FIXED_SOLAR;B601_FIXED_Q0;"
        "ACCEPTED_URDF_REMAINS_KINEMATIC_AND_MASS_TRUTH;NO_CONTACT_PATH_SEARCH_PRODUCTION_OR_FLIGHT_AUTHORITY"
    )

    if len(result.solids()) != EXPECTED_OUTPUT_SOLID_COUNT:
        raise RuntimeError(
            f"CANDIDATE_SOLID_COUNT_FAILED: expected {EXPECTED_OUTPUT_SOLID_COUNT}, found {len(result.solids())}"
        )
    actual_box = result.bounding_box()
    actual_bounds = (
        (actual_box.min.X, actual_box.min.Y, actual_box.min.Z),
        (actual_box.max.X, actual_box.max.Y, actual_box.max.Z),
    )
    expected_box = inputs["expected_candidate"]["expected_bounds_mm"]
    box_tolerance = float(expected_box["absolute_tolerance_mm"])
    for row, key in enumerate(("min", "max")):
        for axis in range(3):
            if abs(actual_bounds[row][axis] - float(expected_box[key][axis])) > box_tolerance:
                raise RuntimeError(
                    f"CANDIDATE_BOUNDS_FAILED: {key}[{axis}]={actual_bounds[row][axis]}"
                )
    return result


if __name__ == "__main__":
    raise SystemExit(
        "SOURCE_ONLY: run execute_integrated_candidate_v1.py after fresh Owner authorization"
    )
