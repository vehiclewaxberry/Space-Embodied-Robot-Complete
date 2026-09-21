r"""fc_common.py - shared helpers for the FreeCAD operational closure round.

script_id            : FC_COMMON
schema_version       : 1.0
allowed_output_root  : 20_engineering/F3R2_V5R_FREECAD_OPERATIONAL_CLOSURE_20260820
authoritative_sources: accepted B601 URDF (kinematics/mass), M3R interface SSOT,
                       F3R2 full-system neutral STEP, V2_2_NATIVE donor
prohibited_sources   : FreeCAD-derived mass may NEVER override accepted URDF mass;
                       V4 02_neutral_cad is a DELTA set, not global geometry

The ONLY module allowed to hold shared functions this round. Every FCxx script
imports from here rather than re-defining helpers, so there is exactly one
implementation of the write-boundary guard and the receipt format.

Runs under FreeCAD's bundled Python 3.11 (freecadcmd) AND under plain CPython for
the non-FreeCAD helpers. Import of FreeCAD is deferred so hash/boundary utilities
work in either interpreter.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time

SCHEMA_VERSION = "1.0"

PROJECT_ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
ROUND_DIR = os.path.join(
    PROJECT_ROOT, "20_engineering", "F3R2_V5R_FREECAD_OPERATIONAL_CLOSURE_20260820"
)

# ---------------------------------------------------------------- boundaries

def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)).replace("\\", "/")


def assert_inside_boundary(path: str) -> str:
    """Fail closed if `path` is not under the round directory.

    This is the single enforcement point for the write boundary. Every script
    that writes anything must route through here or through write_json/receipt.
    """
    target, root = _norm(path), _norm(ROUND_DIR)
    if not target.startswith(root):
        raise RuntimeError(
            "WRITE_BOUNDARY_VIOLATION: refusing to write outside the round directory\n"
            f"  requested : {path}\n  boundary  : {ROUND_DIR}"
        )
    return path


def out(*parts: str) -> str:
    """Build a boundary-checked output path and create its parent directory."""
    path = os.path.join(ROUND_DIR, *parts)
    assert_inside_boundary(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


# ---------------------------------------------------------------- hashing

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(long_path(path), "rb") as fh:
        for block in iter(lambda: fh.read(262144), b""):
            h.update(block)
    return h.hexdigest().upper()


def long_path(path: str) -> str:
    r"""Return a \\?\ extended-length path so files past MAX_PATH are reachable.

    Required: 439 assets in this repo exceed 260 characters (longest 348), and
    core.longpaths is unset, which is why git-based enumeration silently skipped
    196 files in an earlier round.
    """
    absolute = os.path.abspath(path)
    if absolute.startswith("\\\\?\\"):
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC" + absolute[1:]
    return "\\\\?\\" + absolute


def file_fact(path: str) -> dict:
    """Path + bytes + sha256 + mtime, or an explicit absent marker."""
    if not os.path.isfile(long_path(path)):
        return {"path": path.replace("\\", "/"), "exists": False}
    stat = os.stat(long_path(path))
    return {
        "path": path.replace("\\", "/"),
        "exists": True,
        "bytes": stat.st_size,
        "sha256": sha256_file(path),
        "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)),
    }


def walk_files(root: str):
    """Long-path-safe recursive file enumeration. Never uses git."""
    for dirpath, _dirnames, filenames in os.walk(long_path(root)):
        for name in filenames:
            full = os.path.join(dirpath, name)
            if full.startswith("\\\\?\\"):
                full = full[4:]
            yield full


# ---------------------------------------------------------------- receipts

def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(relative_path: str, payload: dict) -> str:
    """Write a JSON receipt inside the boundary and return its path.

    Refuses to emit a zero-byte file - a 0-byte output is a hard stop condition,
    so it must fail loudly here rather than be discovered later.
    """
    path = out(*relative_path.split("/"))
    text = json.dumps(payload, indent=1, ensure_ascii=False)
    if not text.strip():
        raise RuntimeError("REFUSING_ZERO_BYTE_RECEIPT: " + relative_path)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    if os.path.getsize(path) == 0:
        raise RuntimeError("ZERO_BYTE_RECEIPT_WRITTEN: " + relative_path)
    return path


def receipt_header(script_id: str) -> dict:
    return {
        "script_id": script_id,
        "schema_version": SCHEMA_VERSION,
        "timestamp_utc": utc_now(),
        "allowed_output_root": ROUND_DIR.replace("\\", "/"),
        "owner_ruling": "FREECAD_OPERATIONAL_BASELINE_20260820",
        "resource_snapshot": resource_snapshot(),
    }


# ---------------------------------------------------------------- resources

def resource_snapshot() -> dict:
    """Physical memory AND commit charge.

    Commit charge is the binding metric: SolidWorks Attempt 3 died with a
    MemoryError while 1.9 GB of physical RAM was still free, because commit was
    at 84% of limit. Reporting only AvailPhys would have hidden that.
    """
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    gib = 1024.0 ** 3
    commit_total = (stat.ullTotalPageFile - stat.ullAvailPageFile) / gib
    commit_limit = stat.ullTotalPageFile / gib
    return {
        "avail_phys_gib": round(stat.ullAvailPhys / gib, 3),
        "total_phys_gib": round(stat.ullTotalPhys / gib, 3),
        "memory_load_pct": int(stat.dwMemoryLoad),
        "commit_total_gib": round(commit_total, 3),
        "commit_limit_gib": round(commit_limit, 3),
        "commit_utilisation_pct": round(100.0 * commit_total / commit_limit, 1),
        "commit_headroom_gib": round(commit_limit - commit_total, 3),
    }


# ---------------------------------------------------------------- FreeCAD

def freecad_environment() -> dict:
    import FreeCAD  # deferred: only available under freecadcmd/FreeCAD python

    version = FreeCAD.Version()
    info = {
        "freecad_version": ".".join(version[0:3]),
        "freecad_version_tuple": list(version),
        "freecad_build_date": version[5] if len(version) > 5 else None,
        "freecad_build_hash": version[7] if len(version) > 7 else None,
        "python_version": platform.python_version(),
        "python_executable": sys.executable.replace("\\", "/"),
        "user_app_data_dir": FreeCAD.getUserAppDataDir().replace("\\", "/"),
        "resource_dir": FreeCAD.getResourceDir().replace("\\", "/"),
        "platform": platform.platform(),
    }
    try:
        import Part
        info["occ_version"] = str(Part.OCC_VERSION)
    except Exception as exc:  # noqa: BLE001
        info["occ_version_error"] = f"{type(exc).__name__}: {exc}"
    return info


def shape_facts(shape) -> dict:
    """Uniform geometric fingerprint used everywhere a shape is validated."""
    bb = shape.BoundBox
    facts = {
        "is_null": bool(shape.isNull()),
        "is_valid": bool(shape.isValid()),
        "solid_count": len(shape.Solids),
        "shell_count": len(shape.Shells),
        "face_count": len(shape.Faces),
        "edge_count": len(shape.Edges),
        "vertex_count": len(shape.Vertexes),
        "volume_mm3": round(float(shape.Volume), 6),
        "area_mm2": round(float(shape.Area), 6),
        "bbox_mm": {
            "xmin": round(bb.XMin, 6), "ymin": round(bb.YMin, 6), "zmin": round(bb.ZMin, 6),
            "xmax": round(bb.XMax, 6), "ymax": round(bb.YMax, 6), "zmax": round(bb.ZMax, 6),
            "xlen": round(bb.XLength, 6), "ylen": round(bb.YLength, 6), "zlen": round(bb.ZLength, 6),
        },
    }
    try:
        com = shape.CenterOfMass
        facts["center_of_mass_mm"] = [round(com.x, 6), round(com.y, 6), round(com.z, 6)]
    except Exception:  # noqa: BLE001 - valid for shapes with no mass properties
        facts["center_of_mass_mm"] = None
    return facts


def compare_shape_facts(before: dict, after: dict, volume_rel_tol: float = 1e-9) -> dict:
    """Compare two shape_facts dicts. Reports RAW deltas.

    Deliberately does NOT invent an engineering tolerance. Where the project has
    no authoritative geometric tolerance, the caller records the raw residual and
    marks TOLERANCE_AUTHORITY_REQUIRED rather than asserting a pass threshold.
    """
    vol_before = before.get("volume_mm3") or 0.0
    vol_after = after.get("volume_mm3") or 0.0
    denom = max(abs(vol_before), 1e-12)
    result = {
        "solid_count_before": before.get("solid_count"),
        "solid_count_after": after.get("solid_count"),
        "solid_count_match": before.get("solid_count") == after.get("solid_count"),
        "volume_before_mm3": vol_before,
        "volume_after_mm3": vol_after,
        "volume_abs_delta_mm3": round(abs(vol_after - vol_before), 9),
        "volume_rel_delta": round(abs(vol_after - vol_before) / denom, 12),
        "valid_before": before.get("is_valid"),
        "valid_after": after.get("is_valid"),
    }
    bb_b, bb_a = before.get("bbox_mm") or {}, after.get("bbox_mm") or {}
    result["bbox_max_abs_delta_mm"] = round(
        max((abs(bb_a.get(k, 0.0) - bb_b.get(k, 0.0)) for k in bb_b), default=0.0), 9
    )
    result["volume_within_declared_tol"] = result["volume_rel_delta"] <= volume_rel_tol
    result["declared_volume_rel_tol"] = volume_rel_tol
    result["tolerance_basis"] = (
        "numerical round-trip tolerance for detecting representation loss, NOT an "
        "engineering fit tolerance. Engineering tolerances remain "
        "TOLERANCE_AUTHORITY_REQUIRED."
    )
    return result
