"""Guarded Build123d source for the 340.5 mm 12U primary-structure candidate.

This file is intentionally source-only in the current release.  Importing it has no
CAD-kernel side effects and writes no files.  ``gen_step()`` is the sole generation
entry point and requires fresh run-specific execution authority.  When available
memory is below 6 GiB, a fresh, time-bounded, single-use Owner Override and exact
risk acknowledgement are additionally required and consumed before CAD import.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE = Path(__file__).resolve().parent
INPUT_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_DESIGN_INPUTS_V1.json"
STEP_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_CANDIDATE_V1.step"
GENERATION_RECORD_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_GENERATION_RECORD_V1.json"
PREIMPORT_AUTHORITY_RECORD_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_PREIMPORT_AUTHORITY_RECORD_V1.json"
ATTEMPT_INVALIDATION_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_GATE_INVALIDATED_BY_EXECUTION_V1.json"
OVERRIDE_CONSUMPTION_DIR = PACKAGE / ".bus_primary_structure_override_consumption"
RUN_CONSUMPTION_DIR = PACKAGE / ".bus_primary_structure_run_consumption"
ACTIVE_RUN_LOCK_PATH = PACKAGE / ".bus_primary_structure_active_run.lock"
MEMORY_GATE_GIB = 6.0
MAX_OVERRIDE_VALIDITY_SECONDS = 7200.0
REQUIRED_LOW_MEMORY_RISK_ACK = "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK"


def _available_memory_gib() -> float | None:
    """Return currently available physical memory, or None if it cannot be measured."""

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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _parse_utc(value: str, field_name: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RuntimeError(f"LOW_MEMORY_OVERRIDE_INVALID_{field_name}: ISO-8601 UTC required") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0.0:
        raise RuntimeError(f"LOW_MEMORY_OVERRIDE_INVALID_{field_name}: explicit UTC offset required")
    return parsed.astimezone(timezone.utc)


def _consume_low_memory_override(payload: dict[str, Any]) -> str:
    """Atomically consume one override ID before loading the CAD kernel."""

    override_id = str(payload["owner_override_id"])
    digest = hashlib.sha256(override_id.encode("utf-8")).hexdigest().upper()
    marker = OVERRIDE_CONSUMPTION_DIR / f"{digest}.json"
    OVERRIDE_CONSUMPTION_DIR.mkdir(parents=False, exist_ok=True)
    try:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
    except FileExistsError as exc:
        raise RuntimeError(
            "LOW_MEMORY_OVERRIDE_ALREADY_CONSUMED: this Owner Override ID is single-use"
        ) from exc
    return marker.relative_to(PACKAGE).as_posix()


def _consume_run_id(payload: dict[str, Any]) -> str:
    """Atomically make the execution run ID non-reusable at every memory level."""

    run_id = str(payload["run_id"])
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper()
    marker = RUN_CONSUMPTION_DIR / f"{digest}.json"
    RUN_CONSUMPTION_DIR.mkdir(parents=False, exist_ok=True)
    try:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
    except FileExistsError as exc:
        raise RuntimeError("RUN_ID_ALREADY_CONSUMED: every execution run ID is single-use") from exc
    return marker.relative_to(PACKAGE).as_posix()


def _acquire_single_cad_writer_lock(payload: dict[str, Any]) -> str:
    """Atomically reserve the package's sole CAD writer before any run record is written.

    The lock is removed only after a complete generation record has been committed.
    If generation aborts, the lock deliberately remains for Owner inspection and
    manual clearance; this prevents an exception or killed process from silently
    admitting a second writer against the same fixed artifact paths.
    """

    try:
        with ACTIVE_RUN_LOCK_PATH.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
    except FileExistsError as exc:
        raise RuntimeError(
            "CAD_WRITER_ALREADY_ACTIVE_FAIL_CLOSED: one package-level CAD writer is already "
            "reserved; inspect the active-run lock and clear it manually only after confirming "
            "that no generator process remains"
        ) from exc
    return ACTIVE_RUN_LOCK_PATH.relative_to(PACKAGE).as_posix()


def _release_single_cad_writer_lock(run_id: str) -> None:
    """Release the writer lock only when it still belongs to the completing run."""

    try:
        payload = json.loads(ACTIVE_RUN_LOCK_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("CAD_WRITER_LOCK_UNREADABLE_OR_MISSING_FAIL_CLOSED") from exc
    if payload.get("run_id") != run_id:
        raise RuntimeError("CAD_WRITER_LOCK_OWNER_MISMATCH_FAIL_CLOSED")
    ACTIVE_RUN_LOCK_PATH.unlink()


def _execution_authority() -> dict[str, Any]:
    execution_token = os.environ.get("BUS_PRIMARY_STRUCTURE_EXECUTION_AUTHORIZED", "")
    if execution_token.strip().upper() != "YES":
        raise RuntimeError(
            "GENERATION_NOT_AUTHORIZED_SOURCE_ONLY: set a fresh "
            "BUS_PRIMARY_STRUCTURE_EXECUTION_AUTHORIZED=YES only after Owner authorization"
        )

    run_id = os.environ.get("BUS_PRIMARY_STRUCTURE_RUN_ID", "").strip()
    if not (12 <= len(run_id) <= 128) or any(
        not (character.isalnum() or character in "-_:") for character in run_id
    ):
        raise RuntimeError(
            "RUN_ID_REQUIRED_FOR_SINGLE_EXECUTION: BUS_PRIMARY_STRUCTURE_RUN_ID must be a fresh 12..128 character safe identifier"
        )

    available_gib = _available_memory_gib()
    below_gate = available_gib is None or available_gib < MEMORY_GATE_GIB
    owner_override_id = os.environ.get("BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_ID", "").strip()
    issued_text = os.environ.get("BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_ISSUED_UTC", "").strip()
    expires_text = os.environ.get("BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_EXPIRES_UTC", "").strip()
    risk_ack = os.environ.get("BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_RISK_ACK", "").strip()
    if below_gate and not owner_override_id:
        measured = "UNKNOWN" if available_gib is None else f"{available_gib:.3f} GiB"
        raise RuntimeError(
            "MEMORY_GATE_HOLD: available memory is "
            f"{measured}; this run requires a non-empty "
            "BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_ID plus issued/expiry timestamps and risk acknowledgement"
        )

    override_audit: dict[str, Any] | None = None
    if below_gate:
        if not (12 <= len(owner_override_id) <= 128) or any(
            not (character.isalnum() or character in "-_:") for character in owner_override_id
        ):
            raise RuntimeError("LOW_MEMORY_OVERRIDE_INVALID_ID: 12..128 safe identifier characters required")
        if risk_ack != REQUIRED_LOW_MEMORY_RISK_ACK:
            raise RuntimeError(
                "LOW_MEMORY_OVERRIDE_RISK_NOT_ACKNOWLEDGED: set "
                f"BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_RISK_ACK={REQUIRED_LOW_MEMORY_RISK_ACK}"
            )
        issued = _parse_utc(issued_text, "ISSUED_UTC")
        expires = _parse_utc(expires_text, "EXPIRES_UTC")
        now = datetime.now(timezone.utc)
        validity_seconds = (expires - issued).total_seconds()
        if not (issued <= now < expires):
            raise RuntimeError("LOW_MEMORY_OVERRIDE_NOT_CURRENT: current UTC must lie in [issued, expires)")
        if not (0.0 < validity_seconds <= MAX_OVERRIDE_VALIDITY_SECONDS):
            raise RuntimeError("LOW_MEMORY_OVERRIDE_VALIDITY_TOO_LONG: maximum validity is two hours")
        if PREIMPORT_AUTHORITY_RECORD_PATH.is_file():
            try:
                previous = json.loads(PREIMPORT_AUTHORITY_RECORD_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise RuntimeError("PREVIOUS_AUTHORITY_RECORD_UNREADABLE_FAIL_CLOSED") from exc
            if previous.get("owner_override_used") and previous.get("owner_override_id") == owner_override_id:
                raise RuntimeError("LOW_MEMORY_OVERRIDE_ALREADY_CONSUMED_IN_PREIMPORT_RECORD")
        override_audit = {
            "schema": "BUS_PRIMARY_STRUCTURE_LOW_MEMORY_OVERRIDE_CONSUMPTION_V1",
            "owner_override_id": owner_override_id,
            "owner_override_id_sha256": hashlib.sha256(owner_override_id.encode("utf-8")).hexdigest().upper(),
            "issued_utc": issued.isoformat().replace("+00:00", "Z"),
            "expires_utc": expires.isoformat().replace("+00:00", "Z"),
            "consumed_utc": now.isoformat().replace("+00:00", "Z"),
            "validity_seconds": validity_seconds,
            "risk_ack": risk_ack,
            "risk_statement": "Owner accepted elevated out-of-memory/process-instability risk for this single run; this is not reusable authority and does not alter any scientific or release Gate.",
        }

    if STEP_PATH.exists() and os.environ.get("BUS_PRIMARY_STRUCTURE_ALLOW_OVERWRITE", "").strip().upper() != "YES":
        raise FileExistsError(
            f"Refusing to overwrite {STEP_PATH}; set BUS_PRIMARY_STRUCTURE_ALLOW_OVERWRITE=YES "
            "only for an authorized reissue"
        )

    source_pre_hash = _sha256(Path(__file__))
    input_pre_hash = _sha256(INPUT_PATH)
    run_digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper()
    if (RUN_CONSUMPTION_DIR / f"{run_digest}.json").exists():
        raise RuntimeError("RUN_ID_ALREADY_CONSUMED: every execution run ID is single-use")
    if override_audit:
        override_digest = hashlib.sha256(owner_override_id.encode("utf-8")).hexdigest().upper()
        if (OVERRIDE_CONSUMPTION_DIR / f"{override_digest}.json").exists():
            raise RuntimeError(
                "LOW_MEMORY_OVERRIDE_ALREADY_CONSUMED: this Owner Override ID is single-use"
            )

    active_run_lock = _acquire_single_cad_writer_lock(
        {
            "schema": "BUS_PRIMARY_STRUCTURE_ACTIVE_CAD_WRITER_LOCK_V1",
            "run_id": run_id,
            "acquired_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source_sha256_preimport": source_pre_hash,
            "input_sha256_preimport": input_pre_hash,
            "owner_override_id_sha256": (
                override_audit["owner_override_id_sha256"] if override_audit else None
            ),
            "normal_release_condition": "GENERATION_RECORD_COMMITTED",
            "exception_policy": "RETAIN_FOR_OWNER_INSPECTION_AND_MANUAL_CLEARANCE",
        }
    )
    run_consumption_marker = _consume_run_id(
        {
            "schema": "BUS_PRIMARY_STRUCTURE_RUN_CONSUMPTION_V1",
            "run_id": run_id,
            "consumed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source_sha256_preimport": source_pre_hash,
            "input_sha256_preimport": input_pre_hash,
            "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY" if below_gate else "MET_WITHOUT_OVERRIDE",
        }
    )
    consumption_marker = _consume_low_memory_override(override_audit) if override_audit else None
    record = {
        "schema": "BUS_PRIMARY_STRUCTURE_RUN_AUTHORITY_V1",
        "run_id": run_id,
        "issued_at": (
            override_audit["issued_utc"]
            if override_audit
            else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        ),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "execution_authorized": True,
        "execution_authorized_for_this_run": True,
        "available_memory_gib_before_cad_import": available_gib,
        "memory_gate_gib": MEMORY_GATE_GIB,
        "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY" if below_gate else "MET_WITHOUT_OVERRIDE",
        "memory_gate_passed": not below_gate,
        "memory_gate_met_without_override": available_gib is not None and available_gib >= MEMORY_GATE_GIB,
        "owner_override_used": below_gate,
        "owner_override_id": owner_override_id if below_gate else None,
        "owner_override_issued_utc": override_audit["issued_utc"] if override_audit else None,
        "owner_override_expires_utc": override_audit["expires_utc"] if override_audit else None,
        "owner_override_risk_ack": override_audit["risk_ack"] if override_audit else None,
        "owner_override_consumption_marker": consumption_marker,
        "owner_override_single_use_enforced": bool(override_audit),
        "run_id_consumption_marker": run_consumption_marker,
        "run_id_single_use_enforced": True,
        "single_cad_writer_lock": active_run_lock,
        "single_cad_writer_enforced": True,
        "single_cad_writer_exception_policy": "RETAIN_FOR_OWNER_INSPECTION_AND_MANUAL_CLEARANCE",
        "source_sha256_preimport": source_pre_hash,
        "input_sha256_preimport": input_pre_hash,
        "risk_statement": (
            "Owner accepted elevated out-of-memory/process-instability risk for this single run; "
            "this is not reusable authority and does not alter any scientific or release Gate."
            if below_gate
            else "Memory gate met; no low-memory override used."
        ),
    }
    # This record is intentionally committed before any CAD-kernel import.  If the
    # process later fails or is killed, the run-specific low-memory risk decision
    # remains auditable and cannot be mistaken for reusable authority.
    _write_json(PREIMPORT_AUTHORITY_RECORD_PATH, record)
    return record


def _local_yz_to_s(
    u_mm: float,
    v_mm: float,
    clocking_deg: float,
    centre_y_mm: float,
    centre_z_mm: float,
) -> tuple[float, float]:
    import math

    angle = math.radians(clocking_deg)
    sine, cosine = math.sin(angle), math.cos(angle)
    return (
        centre_y_mm + sine * u_mm + cosine * v_mm,
        centre_z_mm - cosine * u_mm + sine * v_mm,
    )


def gen_step() -> str:
    """Generate one deterministic STEP assembly after fresh run-specific authorization."""

    run_authority = _execution_authority()
    _write_json(
        ATTEMPT_INVALIDATION_PATH,
        {
            **run_authority,
            "schema": "BUS_PRIMARY_STRUCTURE_GATE_INVALIDATED_BY_EXECUTION_V1",
            "status": "SOURCE_ONLY_GATE_INVALIDATED__POST_EXECUTION_REBUILD_AND_INDEPENDENT_REVIEW_REQUIRED",
            "source_gate_current": False,
            "static_validation_current": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
    )
    inputs = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    p = inputs["parameters"]
    g = inputs["operational_geometry"]

    # Deliberately delayed: an unauthorized or low-memory run never loads OCCT.
    from build123d import Align, Axis, Box, Compound, Cylinder, Location, export_step

    length = float(g["bus_body_length_mm"])
    cross = float(g["bus_cross_section_y_mm"])
    half_x = length / 2.0
    outer_half = cross / 2.0
    rail = float(p["rail_square_mm"])
    inner_half = float(p["frame_inner_half_span_mm"])
    rail_center = outer_half - rail / 2.0
    frame_t = float(p["frame_axial_thickness_mm"])
    mid_outer_half = outer_half - float(p["mid_frame_outer_inset_mm"])
    web_half = float(p["front_spider_cross_web_width_mm"]) / 2.0
    centre_y = float(p["front_interface_pattern_center_y_mm"])
    centre_z = float(p["front_interface_pattern_center_z_mm"])
    clocking = float(p["front_interface_pattern_clocking_deg"])

    def box_at(
        dims: tuple[float, float, float],
        centre: tuple[float, float, float],
        rotate_x_deg: float = 0.0,
    ):
        shape = Box(*dims, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        if rotate_x_deg:
            shape = shape.rotate(Axis.X, rotate_x_deg)
        return shape.move(Location(centre))

    def cylinder_x(length_mm: float, diameter_mm: float, centre: tuple[float, float, float]):
        shape = Cylinder(
            diameter_mm / 2.0,
            length_mm,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        ).rotate(Axis.Y, 90.0)
        return shape.move(Location(centre))

    parts = []

    for label, y, z in (
        ("LNG_PY_PZ", rail_center, rail_center),
        ("LNG_PY_NZ", rail_center, -rail_center),
        ("LNG_NY_PZ", -rail_center, rail_center),
        ("LNG_NY_NZ", -rail_center, -rail_center),
    ):
        solid = box_at((length, rail, rail), (0.0, y, z))
        solid.label = label
        parts.append(solid)

    def ring_frame(label: str, x_centre: float, out_half: float):
        solid = box_at((frame_t, 2.0 * out_half, 2.0 * out_half), (x_centre, 0.0, 0.0))
        solid -= box_at((frame_t + 0.2, 2.0 * inner_half, 2.0 * inner_half), (x_centre, 0.0, 0.0))
        slot = min(rail, out_half - inner_half)
        slot_centre = inner_half + slot / 2.0
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                solid -= box_at(
                    (frame_t + 0.2, slot, slot),
                    (x_centre, sy * slot_centre, sz * slot_centre),
                )
        solid.label = label
        return solid

    parts.append(ring_frame("FRM_REAR", -half_x + frame_t / 2.0, outer_half))
    parts.append(ring_frame("FRM_MID2", -length / 6.0, mid_outer_half))
    parts.append(ring_frame("FRM_MID1", length / 6.0, mid_outer_half))

    front_label = "FRM_FRONT_SPIDER_MONOLITHIC"
    front_back_x = half_x - frame_t / 2.0
    front = box_at((frame_t, cross, cross), (front_back_x, 0.0, 0.0))
    quadrant_window = inner_half - web_half
    quadrant_centre = (inner_half + web_half) / 2.0
    for sy in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            front -= box_at(
                (frame_t + 0.2, quadrant_window, quadrant_window),
                (front_back_x, sy * quadrant_centre, sz * quadrant_centre),
            )
            front -= box_at(
                (frame_t + 0.2, rail, rail),
                (front_back_x, sy * rail_center, sz * rail_center),
            )
    front -= cylinder_x(
        frame_t + 0.2,
        float(p["front_interface_central_passage_diameter_mm"]),
        (front_back_x, centre_y, centre_z),
    )

    land_t = float(p["front_interface_land_thickness_mm"])
    land_centre_x = half_x + land_t / 2.0
    effective_rotation = clocking - 90.0
    land = box_at(
        (land_t, float(p["front_interface_land_local_square_mm"]), float(p["front_interface_land_local_square_mm"])),
        (land_centre_x, centre_y, centre_z),
        effective_rotation,
    )
    land -= cylinder_x(
        land_t + 0.2,
        float(p["front_interface_central_passage_diameter_mm"]),
        (land_centre_x, centre_y, centre_z),
    )
    lightening_radius = float(p["front_interface_lightening_hole_radius_from_center_mm"])
    for u, v in ((lightening_radius, 0.0), (-lightening_radius, 0.0), (0.0, lightening_radius), (0.0, -lightening_radius)):
        y, z = _local_yz_to_s(u, v, clocking, centre_y, centre_z)
        land -= cylinder_x(
            land_t + 0.2,
            float(p["front_interface_lightening_hole_diameter_mm"]),
            (land_centre_x, y, z),
        )
    half_pitch = float(p["front_interface_m6_pattern_local_half_pitch_mm"])
    for u in (-half_pitch, half_pitch):
        for v in (-half_pitch, half_pitch):
            y, z = _local_yz_to_s(u, v, clocking, centre_y, centre_z)
            land -= cylinder_x(
                land_t + 0.2,
                float(p["front_interface_m6_clearance_hole_diameter_mm"]),
                (land_centre_x, y, z),
            )
    front = front + land
    front.label = front_label
    parts.append(front)

    deck_t = float(p["deck_thickness_mm"])
    deck_span = 2.0 * inner_half
    passage_d = float(p["deck_passage_diameter_mm"])
    passage_y = float(p["deck_passage_y_mm"])
    passage_z = float(p["deck_passage_z_mm"])
    doubler_t = float(p["deck_doubler_thickness_mm"])
    doubler_d = float(p["deck_doubler_outer_diameter_mm"])
    for label, x_station in (("DECK_MID2", -length / 6.0), ("DECK_MID1", length / 6.0)):
        deck = box_at((deck_t, deck_span, deck_span), (x_station, 0.0, 0.0))
        deck -= cylinder_x(deck_t + 0.2, passage_d, (x_station, passage_y, passage_z))
        deck.label = label
        parts.append(deck)
        for suffix, side in (("A", -1.0), ("B", 1.0)):
            x_doubler = x_station + side * (deck_t / 2.0 + doubler_t / 2.0)
            doubler = cylinder_x(doubler_t, doubler_d, (x_doubler, passage_y, passage_z))
            doubler -= cylinder_x(doubler_t + 0.2, passage_d, (x_doubler, passage_y, passage_z))
            doubler.label = f"{label}_DOUBLER_{suffix}"
            parts.append(doubler)

    panel_t = float(p["closure_panel_thickness_mm"])
    panel_min_x = -half_x + frame_t
    panel_max_x = half_x - frame_t
    panel_length = panel_max_x - panel_min_x
    panel_span = 2.0 * inner_half
    for label, centre, dims in (
        ("PNL_TOP", (0.0, 0.0, outer_half - panel_t / 2.0), (panel_length, panel_span, panel_t)),
        ("PNL_BOTTOM", (0.0, 0.0, -outer_half + panel_t / 2.0), (panel_length, panel_span, panel_t)),
    ):
        panel = box_at(dims, centre)
        panel.label = label
        parts.append(panel)
    split_x = length / 6.0
    for side_name, side_y in (("LEFT", 1.0), ("RIGHT", -1.0)):
        for segment, x0, x1 in (
            ("AFT", panel_min_x, split_x),
            ("FWD", split_x, panel_max_x),
        ):
            panel = box_at(
                (x1 - x0, panel_t, panel_span),
                ((x0 + x1) / 2.0, side_y * (outer_half - panel_t / 2.0), 0.0),
            )
            panel.label = f"PNL_{side_name}_{segment}"
            parts.append(panel)

    source_hash_before_export = _sha256(Path(__file__))
    input_hash_before_export = _sha256(INPUT_PATH)
    if (
        source_hash_before_export != run_authority["source_sha256_preimport"]
        or input_hash_before_export != run_authority["input_sha256_preimport"]
    ):
        raise RuntimeError("SOURCE_OR_INPUT_CHANGED_DURING_GENERATION_BEFORE_EXPORT")

    assembly = Compound(children=parts, label="BUS_PRIMARY_STRUCTURE_CANDIDATE_V1")
    export_step(assembly, STEP_PATH)
    if not STEP_PATH.is_file() or STEP_PATH.stat().st_size <= 0:
        raise RuntimeError("STEP_EXPORT_FAILED_OR_EMPTY")

    source_hash_after_export = _sha256(Path(__file__))
    input_hash_after_export = _sha256(INPUT_PATH)
    if (
        source_hash_after_export != run_authority["source_sha256_preimport"]
        or input_hash_after_export != run_authority["input_sha256_preimport"]
    ):
        raise RuntimeError("SOURCE_OR_INPUT_CHANGED_DURING_GENERATION_AFTER_EXPORT")

    record = {
        **run_authority,
        "schema": "BUS_PRIMARY_STRUCTURE_GENERATION_RECORD_V1",
        "input_sha256": input_hash_after_export,
        "source_sha256_before_record": source_hash_after_export,
        "preimport_postexport_source_hash_equal": True,
        "preimport_postexport_input_hash_equal": True,
        "output_path": STEP_PATH.name,
        "output_size_bytes": STEP_PATH.stat().st_size,
        "output_sha256": _sha256(STEP_PATH),
        "visual_inspection_required_before_any_promotion": True,
        "scientific_gate_changed": False,
        "manufacturing_release_created": False,
        "single_cad_writer_lock_release_after_record": True,
    }
    _write_json(GENERATION_RECORD_PATH, record)
    _release_single_cad_writer_lock(run_authority["run_id"])
    return str(STEP_PATH)


if __name__ == "__main__":
    print(gen_step())
