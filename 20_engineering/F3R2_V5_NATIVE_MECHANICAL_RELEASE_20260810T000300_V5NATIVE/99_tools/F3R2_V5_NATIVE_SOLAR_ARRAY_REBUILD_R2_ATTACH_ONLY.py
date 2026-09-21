#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write-once V5 solar-array R2 successor builder (attach-only).

This is the production builder for the quarantined pre-R2 solar candidate.  It
does not resume, repair, replace, or overwrite an existing CAD file.  Production
``execute`` is intentionally impossible until a clean-process SolidWorks 2024
SP5 microfixture has proven this exact builder source and the exact 3R mate /
serial-drive contract below.

The builder creates six native panel bodies, native per-panel mechanical
interface bodies, and two successor SLDASM files.  It reuses the already
accepted V5 root clevis and isolated root pin as read-only inputs.  Solar cells,
material layup, flight mechanism selection, and L0 mass/inertia writes are
outside this script's authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


sys.dont_write_bytecode = True

RUN_ROOT = Path(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition"
    r"\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
)
ENGINEERING = RUN_ROOT.parent
TOOLS = RUN_ROOT / "99_tools"
PART_DIR = RUN_ROOT / "01_native_parts" / "solar_array_r2"
SUBASM_DIR = RUN_ROOT / "02_native_subassemblies"
VALIDATION = RUN_ROOT / "13_validation"
RELEASE = RUN_ROOT / "14_release"

sys.path.insert(0, str(TOOLS))
import F3R2_V5_SESSION_BINDING as sbin
import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base
import F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY as loop1b
import F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY as loop1d


INTERFACE_REQUIREMENTS = RUN_ROOT / "00_authority/SOLAR_ARRAY_INTERFACE_REQUIREMENTS.md"
INTERFACE_FREEZE = RUN_ROOT / "13_validation/V5_SOLAR_ARRAY_INTERFACE_REQUIREMENTS_FREEZE_R2.json"
QUARANTINE_RECEIPT = (
    RUN_ROOT
    / "13_validation/quarantine/V5_SOLAR_ARRAY_INVALID_CANDIDATE_20260812T162256.8949918Z"
    / "V5_SOLAR_ARRAY_INVALID_CANDIDATE_QUARANTINE_RECEIPT.json"
)
ACCEPTED_URDF = ENGINEERING / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
MICROFIXTURE_RECEIPT = VALIDATION / "V5_SOLAR_R2_3R_MICROFIXTURE_RECEIPT.json"
SUCCESS_RECEIPT = VALIDATION / "V5_SOLAR_R2_SUCCESSOR_BUILD_RECEIPT.json"
FINAL_MANIFEST = RELEASE / "V5_SOLAR_R2_SUCCESSOR_NATIVE_MANIFEST_SHA256.txt"

FIXED_INPUTS: Tuple[Tuple[str, Path, str], ...] = (
    ("interface_requirements", INTERFACE_REQUIREMENTS, "62DDF827056D5199CCA68FD1714874E52FFB06398D4B856175435DD576504014"),
    ("interface_freeze", INTERFACE_FREEZE, "B60D8C635A030B0DB49DF7129D6B7F50ACB0F5B9FC912C2E5DED4405FF6542C8"),
    ("invalid_candidate_quarantine", QUARANTINE_RECEIPT, "C4FDE3D4435E14FC767E714D40CDA8124C89D77B4AB0D65661694B37C02DF81E"),
    ("accepted_b601_urdf", ACCEPTED_URDF, "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"),
)

ROOT_INPUTS: Dict[str, Dict[str, Any]] = {
    "L": {
        "axis_y_mm": 143.15,
        "clevis": RUN_ROOT / "01_native_parts/wing_root/LEFT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT",
        "clevis_sha256": "AC60E3A07C84F21CF6E20D01533333345713EE3B28F9966BAAC4B452A4FCE673",
        "pin": RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_HINGE_PIN_V22_ISOLATED.SLDPRT",
        "pin_sha256": "97F6BE610F93605B098590A0C0CD157BE3C14A620B58976AA8A74FF00368733F",
    },
    "R": {
        "axis_y_mm": -143.15,
        "clevis": RUN_ROOT / "01_native_parts/wing_root/RIGHT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT",
        "clevis_sha256": "2D8121989230723A9D29C43672D8534D719D2AF7A64C110D0B0D16EAA31B1894",
        "pin": RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_HINGE_PIN_V22_ISOLATED.SLDPRT",
        "pin_sha256": "82E009F39F2320F53BC8651F7F4282898B0D2ABB4F62C8144A1EAC27B1014AC6",
    },
}

ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot")
ASSEMBLY_TEMPLATE_SHA256 = "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC"

PANEL_X_CENTER_MM = -61.0
PANEL_X_MM = 227.0
PANEL_SPAN_MM = 170.0 / 3.0
PANEL_T_MM = 6.0
HINGE_DEPTH_MM = 28.0
HINGE_PIN_R_MM = 4.0
HINGE_BORE_R_MM = 4.2
ROOT_COLLAR_X_CENTER_MM = -68.0
INTERPANEL_HINGE_X_CENTER_MM = -61.0
TRANS_TOL_MM = 0.05
ROT_TOL_DEG = 0.1

CONFIGS: Tuple[str, ...] = (
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
)

# Normalized logical joint angles [root->P1, P1->P2, P2->P3].  This is the
# side-aware table; no function is allowed to ignore its ``side`` argument.
STATE_ANGLES: Dict[str, Dict[str, Tuple[float, float, float]]] = {
    "SOLAR_STOWED": {"L": (0.0, 0.0, 0.0), "R": (0.0, 0.0, 0.0)},
    "SOLAR_DEPLOY_STAGE1": {"L": (90.0, 0.0, 0.0), "R": (90.0, 0.0, 0.0)},
    "SOLAR_DEPLOY_STAGE2": {"L": (90.0, 90.0, 0.0), "R": (90.0, 90.0, 0.0)},
    "SOLAR_DEPLOYED_NOMINAL": {"L": (90.0, 90.0, 90.0), "R": (90.0, 90.0, 90.0)},
    "SOLAR_LEFT_FAIL": {"L": (0.0, 0.0, 0.0), "R": (90.0, 90.0, 90.0)},
    "SOLAR_RIGHT_FAIL": {"L": (90.0, 90.0, 90.0), "R": (0.0, 0.0, 0.0)},
    "SOLAR_BOTH_FAIL": {"L": (0.0, 0.0, 0.0), "R": (0.0, 0.0, 0.0)},
}

# The root logical angle rotates a link from -Z to outboard Y.  H12 folds by
# +180 deg at logical 0; H23 folds by -180 deg.  At logical 90 all three links
# are coplanar.  This alternating accordion convention is a V5 candidate only.
FK_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2_SERIAL_FK_CONTRACT_V1",
    "logical_angles_deg": "[root_to_P1,P1_to_P2,P2_to_P3]; 0=folded,90=deployed",
    "root_link_psi_deg": "alpha1-90",
    "relative_folds_deg": {"H12": "+2*(90-alpha2)", "H23": "-2*(90-alpha3)"},
    "mirror": "RIGHT=Mirror_XZ(LEFT); y changes sign exactly once",
    "root_axes_mm": {"L": [-40.0, 143.15, 0.0], "R": [-40.0, -143.15, 0.0]},
    "panel_span_mm": PANEL_SPAN_MM,
    "deployed_centers_y_mm": {
        "L": [143.15 + PANEL_SPAN_MM * (index - 0.5) for index in (1, 2, 3)],
        "R": [-(143.15 + PANEL_SPAN_MM * (index - 0.5)) for index in (1, 2, 3)],
    },
    "states": STATE_ANGLES,
}

MATE_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2_3R_MATE_CONTRACT_V1",
    "hinges_per_side": 3,
    "each_hinge": ["CONCENTRIC_PIN_BORE", "COINCIDENT_AXIAL_FACE"],
    "root_anchor": "REUSE_V5_LOOP1B_ISOLATED_ROOT_PIN_AND_THREE_WEB_CLEVIS",
    "moving_panels_fixed": False,
    "rigid_interfaces": "LOCK_MATE_EACH_INTERFACE_PART_TO_ITS_ONE_PANEL",
    "configuration_driver": "SERIAL_PARENT_TO_CHILD_SETTRANSFORMANDSOLVE3_SOLVE_TRUE",
    "native_stop_semantics": "PER_PANEL_DEPLOY_STOP_RAIL; H12/H23_CONTACT_READBACK_REQUIRED_LATER",
    "continuous_motion_authority": "NONE; MICROFIXTURE_DIAGNOSTIC_SAMPLES_ONLY",
}

SUCCESSOR_ASSEMBLIES = {
    "L": SUBASM_DIR / "L_SOLAR_ARRAY_R2_SUCCESSOR.SLDASM",
    "R": SUBASM_DIR / "R_SOLAR_ARRAY_R2_SUCCESSOR.SLDASM",
}


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = detail or {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def fact(path: Path) -> Dict[str, Any]:
    return {"path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def contract_sha256() -> str:
    payload = {"fk": FK_CONTRACT, "mates": MATE_CONTRACT}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def canonical_json(value: Any) -> str:
    """Normalize tuple/list differences introduced by JSON persistence."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_text_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def rx(degrees: float) -> List[List[float]]:
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]


def ry(degrees: float) -> List[List[float]]:
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]


def mmul(first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]) -> List[List[float]]:
    return [
        [sum(float(first[row][k]) * float(second[k][column]) for k in range(3)) for column in range(3)]
        for row in range(3)
    ]


def mvec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> List[float]:
    return [sum(float(matrix[row][column]) * float(vector[column]) for column in range(3)) for row in range(3)]


def vadd(first: Sequence[float], second: Sequence[float]) -> List[float]:
    return [float(first[index]) + float(second[index]) for index in range(3)]


def transform_for_center(
    rotation: Sequence[Sequence[float]], desired_center_mm: Sequence[float], local_center_mm: Sequence[float]
) -> List[float]:
    local_m = [float(value) / 1000.0 for value in local_center_mm]
    desired_m = [float(value) / 1000.0 for value in desired_center_mm]
    rotated = mvec(rotation, local_m)
    translation = [desired_m[index] - rotated[index] for index in range(3)]
    return [
        rotation[0][0], rotation[1][0], rotation[2][0],
        rotation[0][1], rotation[1][1], rotation[2][1],
        rotation[0][2], rotation[1][2], rotation[2][2],
        translation[0], translation[1], translation[2],
        1.0, 0.0, 0.0, 0.0,
    ]


def serial_fk(side: str, angles_deg: Sequence[float]) -> List[Dict[str, Any]]:
    if side not in ("L", "R") or len(angles_deg) != 3:
        raise ValueError("serial_fk requires side L/R and exactly three angles")
    if any(float(angle) not in (0.0, 90.0) for angle in angles_deg):
        raise ValueError("production FK accepts only frozen static anchors 0/90 deg")
    sign = 1.0 if side == "L" else -1.0
    a1, a2, a3 = (float(value) for value in angles_deg)
    psi = [a1 - 90.0, 0.0, 0.0]
    psi[1] = psi[0] + 2.0 * (90.0 - a2)
    psi[2] = psi[1] - 2.0 * (90.0 - a3)
    hinge = [0.0, sign * 143.15, 0.0]
    rows: List[Dict[str, Any]] = []
    for index, psi_deg in enumerate(psi, start=1):
        angle = math.radians(psi_deg)
        delta = [0.0, sign * PANEL_SPAN_MM * math.cos(angle), PANEL_SPAN_MM * math.sin(angle)]
        outboard = vadd(hinge, delta)
        center = [(hinge[0] + outboard[0]) / 2.0, (hinge[1] + outboard[1]) / 2.0, (hinge[2] + outboard[2]) / 2.0]
        rows.append({
            "panel_index": index,
            "logical_angle_deg": float(angles_deg[index - 1]),
            "psi_deg": psi_deg,
            "inboard_hinge_mm": list(hinge),
            "centerline_center_mm": center,
            "outboard_hinge_mm": outboard,
        })
        hinge = outboard
    return rows


def oracle_self_check() -> Dict[str, Any]:
    failures: List[str] = []
    if tuple(STATE_ANGLES) != CONFIGS or set(STATE_ANGLES) != set(CONFIGS):
        failures.append("configuration set/order mismatch")
    if STATE_ANGLES["SOLAR_LEFT_FAIL"] != {"L": (0.0, 0.0, 0.0), "R": (90.0, 90.0, 90.0)}:
        failures.append("LEFT_FAIL side semantics drift")
    if STATE_ANGLES["SOLAR_RIGHT_FAIL"] != {"L": (90.0, 90.0, 90.0), "R": (0.0, 0.0, 0.0)}:
        failures.append("RIGHT_FAIL side semantics drift")
    deployed = {side: serial_fk(side, STATE_ANGLES["SOLAR_DEPLOYED_NOMINAL"][side]) for side in ("L", "R")}
    for index, (left, right) in enumerate(zip(deployed["L"], deployed["R"]), start=1):
        lc, rc = left["centerline_center_mm"], right["centerline_center_mm"]
        if max(abs(lc[0] - rc[0]), abs(lc[1] + rc[1]), abs(lc[2] - rc[2])) > 1e-9:
            failures.append(f"deployed mirror mismatch panel {index}")
        expected = 143.15 + PANEL_SPAN_MM * (index - 0.5)
        if abs(lc[1] - expected) > 1e-9 or abs(rc[1] + expected) > 1e-9:
            failures.append(f"deployed centroid mismatch panel {index}")
    for state in ("SOLAR_STOWED", "SOLAR_DEPLOY_STAGE1", "SOLAR_DEPLOY_STAGE2", "SOLAR_DEPLOYED_NOMINAL", "SOLAR_BOTH_FAIL"):
        left = serial_fk("L", STATE_ANGLES[state]["L"])
        right = serial_fk("R", STATE_ANGLES[state]["R"])
        for index, (lrow, rrow) in enumerate(zip(left, right), start=1):
            for key in ("inboard_hinge_mm", "centerline_center_mm", "outboard_hinge_mm"):
                lp, rp = lrow[key], rrow[key]
                if max(abs(lp[0] - rp[0]), abs(lp[1] + rp[1]), abs(lp[2] - rp[2])) > 1e-9:
                    failures.append(f"{state} XZ mirror mismatch panel {index} {key}")
    for state in CONFIGS:
        for side in ("L", "R"):
            rows = serial_fk(side, STATE_ANGLES[state][side])
            for parent, child in zip(rows[:-1], rows[1:]):
                error = max(abs(a - b) for a, b in zip(parent["outboard_hinge_mm"], child["inboard_hinge_mm"]))
                if error > 1e-9:
                    failures.append(f"{state}/{side} serial closure {parent['panel_index']}->{child['panel_index']}")
    return {
        "contract_sha256": contract_sha256(),
        "states_checked": len(CONFIGS),
        "mirror_states_checked": 5,
        "failures": failures,
        "verdict": "V5_SOLAR_R2_SERIAL_FK_ORACLE_PASS" if not failures else "V5_SOLAR_R2_SERIAL_FK_ORACLE_FAIL",
    }


def part_key(side: str, index: int, role: str) -> str:
    return f"SOLAR_{side}{index}_{role}_R2"


def part_specs() -> Dict[str, Dict[str, Any]]:
    specs: Dict[str, Dict[str, Any]] = {}
    for side in ("L", "R"):
        for index in (1, 2, 3):
            common = {
                "SIDE": side,
                "PANEL_INDEX": str(index),
                "SOLAR_CELL_DETAIL": "PROHIBITED",
                "MASS_SOURCE": "EXTERNAL_MECHANICAL_ONLY",
                "MASS_AUTHORITY": "ESTIMATED_PLACEHOLDER_PENDING_NATIVE_READBACK",
                "BOM_ROW_REQUIRED": "TRUE",
                "FLIGHT_QUALIFICATION": "HOLD",
            }
            key = part_key(side, index, "PANEL_STRUCTURE")
            specs[key] = {
                "target": PART_DIR / f"{key}.SLDPRT",
                "geometry": {"kind": "box", "width_mm": PANEL_X_MM, "height_mm": PANEL_SPAN_MM, "depth_mm": PANEL_T_MM},
                "expected_sorted_mm": sorted((PANEL_X_MM, PANEL_SPAN_MM, PANEL_T_MM)),
                "local_center_mm": [0.0, 0.0, PANEL_T_MM / 2.0],
                "properties": {**common, "FUNCTION": "SIMPLIFIED_NATIVE_PANEL_STRUCTURE", "FOLD_RELATION": "SINGLE_BODY_SHARED_ACROSS_ALL_CONFIGURATIONS"},
            }
            key = part_key(side, index, "INBOARD_HINGE_IF")
            specs[key] = {
                "target": PART_DIR / f"{key}.SLDPRT",
                "geometry": {"kind": "annulus_holes", "outer_r_mm": 6.0, "inner_r_mm": HINGE_BORE_R_MM, "holes": [], "depth_mm": HINGE_DEPTH_MM},
                "expected_sorted_mm": sorted((12.0, 12.0, HINGE_DEPTH_MM)),
                "local_center_mm": [0.0, 0.0, HINGE_DEPTH_MM / 2.0],
                "properties": {**common, "FUNCTION": "INBOARD_HINGE_AXIS_INTERFACE", "BORE_DIAMETER_MM": str(2.0 * HINGE_BORE_R_MM), "BEARING_SELECTION": "UNKNOWN_HOLD"},
            }
            if index < 3:
                key = part_key(side, index, "OUTBOARD_HINGE_PIN_IF")
                specs[key] = {
                    "target": PART_DIR / f"{key}.SLDPRT",
                    "geometry": {"kind": "cylinder", "radius_mm": HINGE_PIN_R_MM, "depth_mm": HINGE_DEPTH_MM},
                    "expected_sorted_mm": sorted((2.0 * HINGE_PIN_R_MM, 2.0 * HINGE_PIN_R_MM, HINGE_DEPTH_MM)),
                    "local_center_mm": [0.0, 0.0, HINGE_DEPTH_MM / 2.0],
                    "properties": {**common, "FUNCTION": "OUTBOARD_HINGE_AXIS_PLACEHOLDER", "PIN_DIAMETER_MM": str(2.0 * HINGE_PIN_R_MM), "PRODUCT_SELECTION": "UNKNOWN_HOLD"},
                }
            for role, geometry, expected, local_center, function in (
                ("STOW_PAD_IF", {"kind": "box", "width_mm": 20.0, "height_mm": 6.0, "depth_mm": 3.0}, (20.0, 6.0, 3.0), [0.0, 0.0, 1.5], "STOW_CONTACT_INTERFACE"),
                ("DEPLOY_STOP_IF", {"kind": "box", "width_mm": 16.0, "height_mm": PANEL_SPAN_MM, "depth_mm": 2.0}, (16.0, PANEL_SPAN_MM, 2.0), [0.0, 0.0, 1.0], "DEPLOYED_STOP_CONTACT_RAIL"),
                ("HARNESS_EXIT_IF", {"kind": "box", "width_mm": 8.0, "height_mm": 8.0, "depth_mm": 4.0}, (8.0, 8.0, 4.0), [0.0, 0.0, 2.0], "HARNESS_EXIT_DATUM_PLACEHOLDER"),
            ):
                key = part_key(side, index, role)
                specs[key] = {
                    "target": PART_DIR / f"{key}.SLDPRT",
                    "geometry": geometry,
                    "expected_sorted_mm": sorted(expected),
                    "local_center_mm": local_center,
                    "properties": {**common, "FUNCTION": function, "CONNECTOR_OR_CABLE_SELECTION": "UNKNOWN_HOLD" if role == "HARNESS_EXIT_IF" else "NOT_APPLICABLE"},
                }
    return specs


def output_targets() -> List[Path]:
    return [Path(spec["target"]) for spec in part_specs().values()] + list(SUCCESSOR_ASSEMBLIES.values()) + [SUCCESS_RECEIPT, FINAL_MANIFEST]


def load_microfixture_gate() -> Dict[str, Any]:
    if not MICROFIXTURE_RECEIPT.is_file():
        raise GateError("MICROFIXTURE_REQUIRED", "production execute is forbidden before the R2 3R microfixture PASS", {"required": norm(MICROFIXTURE_RECEIPT)})
    payload = json.loads(MICROFIXTURE_RECEIPT.read_text(encoding="utf-8"))
    required = {
        "schema": "F3R2_V5_SOLAR_R2_3R_MICROFIXTURE_RECEIPT_V1",
        "builder_sha256": sha256(Path(__file__)),
        "contract_sha256": contract_sha256(),
        "verdict": "V5_SOLAR_R2_3R_MICROFIXTURE_COLD_REOPEN_PASS",
    }
    actual = {key: payload.get(key) for key in required}
    if actual != required:
        raise GateError("MICROFIXTURE_CONTRACT_DRIFT", "microfixture does not prove this exact builder and contract", {"expected": required, "actual": actual})
    if payload.get("fresh_process") is not True or payload.get("cold_reopen") is not True:
        raise GateError("MICROFIXTURE_PROCESS_EVIDENCE_FAIL", "microfixture lacks fresh-process cold-reopen proof")
    if canonical_json(payload.get("mate_contract")) != canonical_json(MATE_CONTRACT) or canonical_json(payload.get("fk_contract")) != canonical_json(FK_CONTRACT):
        raise GateError("MICROFIXTURE_PAYLOAD_CONTRACT_FAIL", "microfixture embedded contract differs")
    if canonical_json(payload.get("tested_state_angles")) != canonical_json(STATE_ANGLES):
        raise GateError("MICROFIXTURE_STATE_SET_FAIL", "microfixture did not test the exact seven-state angle table")
    return {"receipt": fact(MICROFIXTURE_RECEIPT), "payload_verdict": payload["verdict"]}


def static_audit(require_microfixture: bool = True) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    for label, path, expected in FIXED_INPUTS:
        actual = sha256(path) if path.is_file() else None
        checks.append({"label": label, "path": norm(path), "exists": path.is_file(), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    for side, spec in ROOT_INPUTS.items():
        for role in ("clevis", "pin"):
            path = Path(spec[role])
            expected = str(spec[f"{role}_sha256"])
            actual = sha256(path) if path.is_file() else None
            checks.append({"label": f"root_{side}_{role}", "path": norm(path), "exists": path.is_file(), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    actual_template = sha256(ASSEMBLY_TEMPLATE) if ASSEMBLY_TEMPLATE.is_file() else None
    checks.append({"label": "assembly_template", "path": norm(ASSEMBLY_TEMPLATE), "exists": ASSEMBLY_TEMPLATE.is_file(), "expected_sha256": ASSEMBLY_TEMPLATE_SHA256, "actual_sha256": actual_template, "pass": actual_template == ASSEMBLY_TEMPLATE_SHA256})
    oracle = oracle_self_check()
    existing = [norm(path) for path in output_targets() if path.exists()]
    microfixture: Dict[str, Any]
    try:
        microfixture = load_microfixture_gate() if require_microfixture else {"required_for_execute": True, "checked": False}
        microfixture_ok = not require_microfixture or "receipt" in microfixture
    except Exception as exc:
        microfixture = {"error": str(exc), "required_for_execute": True}
        microfixture_ok = False
    execution_authorized = all(row["pass"] for row in checks) and oracle["verdict"].endswith("_PASS") and not existing and microfixture_ok
    return {
        "schema": "F3R2_V5_SOLAR_R2_SUCCESSOR_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "builder": fact(Path(__file__)),
        "fixed_inputs": checks,
        "oracle": oracle,
        "microfixture": microfixture,
        "output_target_count": len(output_targets()),
        "existing_output_targets": existing,
        "write_policy": "WRITE_ONCE_NO_RESUME_NO_OVERWRITE",
        "successor_assemblies": {side: norm(path) for side, path in SUCCESSOR_ASSEMBLIES.items()},
        "execution_authorized": execution_authorized,
        "verdict": "V5_SOLAR_R2_SUCCESSOR_EXECUTION_READY" if execution_authorized else "V5_SOLAR_R2_SUCCESSOR_EXECUTION_HOLD",
    }


def component_transform_specs(side: str, angles: Sequence[float]) -> Dict[str, List[float]]:
    rows = serial_fk(side, angles)
    transforms: Dict[str, List[float]] = {}
    for row in rows:
        index = int(row["panel_index"])
        frame_r = rx(float(row["psi_deg"]))
        inboard = row["inboard_hinge_mm"]
        outboard = row["outboard_hinge_mm"]
        centerline = row["centerline_center_mm"]
        panel_center = vadd(centerline, mvec(frame_r, [PANEL_X_CENTER_MM, 0.0, PANEL_T_MM / 2.0]))
        key = part_key(side, index, "PANEL_STRUCTURE")
        transforms[key] = transform_for_center(frame_r, panel_center, [0.0, 0.0, PANEL_T_MM / 2.0])
        hinge_r = mmul(frame_r, ry(90.0))
        collar_x = ROOT_COLLAR_X_CENTER_MM if index == 1 else INTERPANEL_HINGE_X_CENTER_MM
        collar_center = [collar_x, inboard[1], inboard[2]]
        key = part_key(side, index, "INBOARD_HINGE_IF")
        transforms[key] = transform_for_center(hinge_r, collar_center, [0.0, 0.0, HINGE_DEPTH_MM / 2.0])
        if index < 3:
            key = part_key(side, index, "OUTBOARD_HINGE_PIN_IF")
            pin_center = [INTERPANEL_HINGE_X_CENTER_MM, outboard[1], outboard[2]]
            transforms[key] = transform_for_center(hinge_r, pin_center, [0.0, 0.0, HINGE_DEPTH_MM / 2.0])
        local_roles = {
            "STOW_PAD_IF": ([PANEL_X_CENTER_MM - 70.0, 0.0, 1.5], [0.0, 0.0, 1.5]),
            "DEPLOY_STOP_IF": ([PANEL_X_CENTER_MM + 82.0, 0.0, 1.0], [0.0, 0.0, 1.0]),
            "HARNESS_EXIT_IF": ([45.0, PANEL_SPAN_MM * 0.25, 2.0], [0.0, 0.0, 2.0]),
        }
        for role, (local_in_frame, local_center) in local_roles.items():
            desired = vadd(inboard, mvec(frame_r, local_in_frame))
            key = part_key(side, index, role)
            transforms[key] = transform_for_center(frame_r, desired, local_center)
    return transforms


def transform_error(actual: Sequence[float], expected: Sequence[float]) -> Dict[str, float]:
    if len(actual) != 16 or len(expected) != 16:
        return {"translation_mm": float("inf"), "rotation_deg": float("inf")}
    translation_mm = math.sqrt(sum((float(actual[index]) - float(expected[index])) ** 2 for index in (9, 10, 11))) * 1000.0
    ar = [[float(actual[column * 3 + row]) for column in range(3)] for row in range(3)]
    er = [[float(expected[column * 3 + row]) for column in range(3)] for row in range(3)]
    trace = sum(sum(er[k][row] * ar[k][row] for k in range(3)) for row in range(3))
    cosine = max(-1.0, min(1.0, (trace - 1.0) / 2.0))
    return {"translation_mm": translation_mm, "rotation_deg": math.degrees(math.acos(cosine))}


def make_transform(sw: Any, data: Sequence[float], types: Any, pythoncom: Any) -> Any:
    from win32com.client import VARIANT
    utility = base.wrap(base.value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
    transform = utility.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(value) for value in data]))
    if transform is None:
        raise GateError("CREATE_TRANSFORM_FAIL", "IMathUtility.CreateTransform returned null")
    return transform


def insert_component_transform(sw: Any, model: Any, assembly: Any, path: Path, transform: Sequence[float], fixed: bool, types: Any, pythoncom: Any) -> Any:
    title = str(base.value(model, "GetTitle"))
    opened = None
    try:
        opened, _ = loop1b.open_doc(sw, path, loop1b.SW_PART, True, types, pythoncom)
        loop1b.activate(sw, title)
        raw = assembly.AddComponent5(str(path), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw is None:
            raise GateError("ADD_COMPONENT_FAIL", "AddComponent5 returned null", {"path": norm(path)})
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        if not bool(component.SetTransformAndSolve3(make_transform(sw, transform, types, pythoncom), True)):
            raise GateError("INITIAL_COMPONENT_TRANSFORM_FAIL", "SetTransformAndSolve3 failed", {"path": norm(path)})
        model.ClearSelection2(True)
        if not bool(component.Select4(False, None, False)):
            raise GateError("COMPONENT_SELECT_FAIL", "cannot select inserted component", {"path": norm(path)})
        assembly.FixComponent() if fixed else assembly.UnfixComponent()
        model.ClearSelection2(True)
        if bool(base.value(component, "IsFixed")) != fixed:
            raise GateError("COMPONENT_FIXED_READBACK_FAIL", "fixed-state mismatch", {"path": norm(path), "expected": fixed})
        return component
    finally:
        loop1b.close_doc(sw, opened)
        loop1b.activate(sw, title)


def component_map(model: Any, side: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    expected = {Path(spec["target"]).resolve(): key for key, spec in part_specs().items() if key.startswith(f"SOLAR_{side}")}
    found: Dict[str, Any] = {}
    for component in loop1b.get_components(model, types, pythoncom):
        path = loop1b.component_path(component)
        if path in expected:
            found[expected[path]] = component
    if set(found) != set(expected.values()):
        raise GateError("SIDE_COMPONENT_SET_FAIL", "successor assembly has missing/duplicate R2 component paths", {"side": side, "expected": sorted(expected.values()), "actual": sorted(found)})
    return found


def drive_and_read_state(sw: Any, model: Any, side: str, state: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    expected = component_transform_specs(side, STATE_ANGLES[state][side])
    components = component_map(model, side, types, pythoncom)
    # This exact root-to-tip driver must first be proven by MICROFIXTURE_RECEIPT.
    for index in (1, 2, 3):
        key = part_key(side, index, "PANEL_STRUCTURE")
        if not bool(components[key].SetTransformAndSolve3(make_transform(sw, expected[key], types, pythoncom), True)):
            raise GateError("SERIAL_CONFIG_DRIVE_FAIL", "microfixture-proven panel drive failed", {"side": side, "state": state, "panel": index})
        if not bool(model.EditRebuild3()):
            raise GateError("SERIAL_CONFIG_REBUILD_FAIL", "rebuild failed during serial drive", {"side": side, "state": state, "panel": index})
    if not bool(model.ForceRebuild3(True)):
        raise GateError("SERIAL_CONFIG_FORCE_REBUILD_FAIL", "final state rebuild failed", {"side": side, "state": state})
    readback = []
    for key, wanted in expected.items():
        actual = loop1b.transform_array(components[key])
        error = transform_error(actual, wanted)
        if error["translation_mm"] > TRANS_TOL_MM or error["rotation_deg"] > ROT_TOL_DEG:
            raise GateError("STATE_TRANSFORM_READBACK_FAIL", "native component differs from serial FK oracle", {"side": side, "state": state, "component": key, "error": error})
        readback.append({"component": key, "transform16": actual, "error": error})
    return {"state": state, "side": side, "angles_deg": list(STATE_ANGLES[state][side]), "fk": serial_fk(side, STATE_ANGLES[state][side]), "components": readback, "verdict": "V5_SOLAR_R2_STATE_FK_READBACK_PASS"}


def add_configurations(sw: Any, model: Any, side: str, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    manager = base.value(model, "ConfigurationManager")
    active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    active.Name = "SOLAR_DEPLOYED_NOMINAL"
    existing = {str(name) for name in base.as_list(base.value(model, "GetConfigurationNames"))}
    for name in CONFIGS:
        if name not in existing:
            created = manager.AddConfiguration2(name, "V5 solar R2 frozen static anchor", "", 0, "", False, False)
            if created is None:
                raise GateError("CONFIG_CREATE_FAIL", "AddConfiguration2 returned null", {"side": side, "state": name})
            existing.add(name)
    rows = []
    for state in CONFIGS:
        if not bool(model.ShowConfiguration2(state)):
            raise GateError("CONFIG_ACTIVATE_FAIL", "ShowConfiguration2 failed", {"side": side, "state": state})
        row = drive_and_read_state(sw, model, side, state, types, pythoncom)
        props = model.Extension.CustomPropertyManager(state)
        for name, value in {
            "SolarSide": side,
            "NormalizedLogicalAnglesDeg": "/".join(str(value) for value in STATE_ANGLES[state][side]),
            "Authority": "SOLAR_ARRAY_INTERFACE_REQUIREMENTS_FROZEN_R2",
            "FKContractSHA256": contract_sha256(),
            "ContinuousMotionAuthority": "NONE",
        }.items():
            if int(props.Add3(name, 30, str(value), 2)) < 0:
                raise GateError("CONFIG_PROPERTY_FAIL", "cannot write configuration property", {"side": side, "state": state, "property": name})
        rows.append(row)
    if not bool(model.ShowConfiguration2("SOLAR_DEPLOYED_NOMINAL")):
        raise GateError("NOMINAL_RESTORE_FAIL", "cannot restore nominal configuration", {"side": side})
    return rows


def create_hinge_mates(model: Any, assembly: Any, side: str, components: Dict[str, Any], types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    root = ROOT_INPUTS[side]
    root_pin = loop1b.component_by_path(model, Path(root["pin"]), types, pythoncom)
    rows: List[Dict[str, Any]] = []
    for index in (1, 2, 3):
        collar = components[part_key(side, index, "INBOARD_HINGE_IF")]
        if index == 1:
            pin = root_pin
            axis_y = float(root["axis_y_mm"])
            collar_face_x = pin_face_x = -82.0
        else:
            pin = components[part_key(side, index - 1, "OUTBOARD_HINGE_PIN_IF")]
            nominal = serial_fk(side, (90.0, 90.0, 90.0))[index - 1]["inboard_hinge_mm"]
            axis_y = float(nominal[1])
            collar_face_x = pin_face_x = -75.0
        collar_cyl, collar_fact = loop1b.cylinder_entity(collar, HINGE_BORE_R_MM, axis_y, 1, types, pythoncom)
        pin_cyl, pin_fact = loop1b.cylinder_entity(pin, HINGE_PIN_R_MM, axis_y, 1, types, pythoncom)
        concentric = loop1b.add_entity_mate(model, assembly, collar_cyl, pin_cyl, loop1b.SW_MATE_CONCENTRIC, loop1b.SW_ALIGN_CLOSEST, (collar, pin), types, pythoncom)
        collar_face, collar_plane = loop1b.plane_entity_x(collar, collar_face_x, types, pythoncom)
        pin_face, pin_plane = loop1b.plane_entity_x(pin, pin_face_x, types, pythoncom)
        axial = loop1b.add_entity_mate(model, assembly, collar_face, pin_face, loop1b.SW_MATE_COINCIDENT, loop1b.SW_ALIGN_CLOSEST, (collar, pin), types, pythoncom)
        rows.append({"joint": ("ROOT" if index == 1 else f"H{index - 1}{index}"), "axis_y_mm": axis_y, "concentric": concentric, "axial": axial, "geometry": {"collar": collar_fact, "pin": pin_fact, "collar_plane": collar_plane, "pin_plane": pin_plane}})
    return rows


def build_side_assembly(sw: Any, side: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    target = SUCCESSOR_ASSEMBLIES[side]
    if target.exists():
        raise GateError("ASSEMBLY_TARGET_EXISTS", "write-once successor assembly target exists", {"target": norm(target)})
    raw = sw.NewDocument(str(ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = base.value(sw, "ActiveDoc")
    if raw is None:
        raise GateError("NEW_ASSEMBLY_FAIL", "cannot create successor assembly", {"side": side})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    try:
        identity = loop1b.transform_data((0.0, 0.0, 0.0))
        root_clevis = insert_component_transform(sw, model, assembly, Path(ROOT_INPUTS[side]["clevis"]), identity, True, types, pythoncom)
        root_pin = insert_component_transform(sw, model, assembly, Path(ROOT_INPUTS[side]["pin"]), identity, True, types, pythoncom)
        nominal = component_transform_specs(side, STATE_ANGLES["SOLAR_DEPLOYED_NOMINAL"][side])
        components: Dict[str, Any] = {}
        for key, spec in part_specs().items():
            if not key.startswith(f"SOLAR_{side}"):
                continue
            components[key] = insert_component_transform(sw, model, assembly, Path(spec["target"]), nominal[key], False, types, pythoncom)
        lock_mates = []
        for index in (1, 2, 3):
            panel = components[part_key(side, index, "PANEL_STRUCTURE")]
            roles = ["INBOARD_HINGE_IF", "STOW_PAD_IF", "DEPLOY_STOP_IF", "HARNESS_EXIT_IF"]
            if index < 3:
                roles.append("OUTBOARD_HINGE_PIN_IF")
            for role in roles:
                lock_mates.append(loop1b.add_lock_mate(model, assembly, panel, components[part_key(side, index, role)], types, pythoncom))
        hinge_mates = create_hinge_mates(model, assembly, side, components, types, pythoncom)
        if bool(base.value(root_clevis, "IsFixed")) is not True or bool(base.value(root_pin, "IsFixed")) is not True:
            raise GateError("ROOT_ANCHOR_FIXED_FAIL", "root clevis/pin anchor is not fixed", {"side": side})
        if any(bool(base.value(components[part_key(side, index, "PANEL_STRUCTURE")], "IsFixed")) for index in (1, 2, 3)):
            raise GateError("PANEL_FIXED_PROHIBITED", "a moving panel was fixed", {"side": side})
        configurations = add_configurations(sw, model, side, types, pythoncom)
        ledger = loop1b.mate_ledger(model, types, pythoncom)
        expected_mates = len(lock_mates) + 2 * 3
        if len(ledger) != expected_mates:
            raise GateError("MATE_LEDGER_COUNT_FAIL", "3R successor mate count mismatch", {"side": side, "expected": expected_mates, "actual": len(ledger)})
        references = loop1b.component_reference_ledger(model, types, pythoncom)
        saved = loop1b.save_assembly(model, target)
    finally:
        loop1b.close_doc(sw, model)
    return {"side": side, "target": saved, "root_inputs": {"clevis": norm(Path(ROOT_INPUTS[side]["clevis"])), "pin": norm(Path(ROOT_INPUTS[side]["pin"]))}, "lock_mates": lock_mates, "hinges": hinge_mates, "mate_ledger": ledger, "references": references, "configurations": configurations, "verdict": "V5_SOLAR_R2_SUCCESSOR_SIDE_BUILD_PASS"}


def cold_verify_side(sw: Any, side: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    target = SUCCESSOR_ASSEMBLIES[side]
    model = None
    try:
        model, opened = loop1b.open_doc(sw, target, loop1b.SW_ASSEMBLY, True, types, pythoncom)
        names = [str(name) for name in base.as_list(base.value(model, "GetConfigurationNames"))]
        if set(names) != set(CONFIGS):
            raise GateError("COLD_CONFIG_SET_FAIL", "cold successor configuration set mismatch", {"side": side, "actual": names})
        state_rows = []
        for state in CONFIGS:
            if not bool(model.ShowConfiguration2(state)) or not bool(model.ForceRebuild3(True)):
                raise GateError("COLD_CONFIG_ACTIVATE_FAIL", "cold configuration activation/rebuild failed", {"side": side, "state": state})
            state_rows.append(drive_and_read_state(sw, model, side, state, types, pythoncom))
        ledger = loop1b.mate_ledger(model, types, pythoncom)
        refs = loop1b.component_reference_ledger(model, types, pythoncom)
        if any(row["feature_error_code"] != 0 or row["suppressed"] for row in ledger):
            raise GateError("COLD_MATE_LEDGER_FAIL", "cold mate ledger has error/suppression", {"side": side})
        return {"side": side, "target": fact(target), "open": opened, "mate_ledger": ledger, "references": refs, "states": state_rows, "verdict": "V5_SOLAR_R2_SUCCESSOR_SIDE_COLD_READBACK_PASS"}
    finally:
        loop1b.close_doc(sw, model)


def close_owned_documents(sw: Any) -> None:
    for raw in base.as_list(base.value(sw, "GetDocuments")):
        try:
            sw.CloseDoc(str(base.value(raw, "GetTitle")))
        except Exception:
            pass


def execute() -> int:
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_SOLAR_R2_SUCCESSOR_BUILD_RECEIPT_V1",
        "timestamp_start_utc": utc_now(),
        "builder": fact(Path(__file__)),
        "contract_sha256": contract_sha256(),
        "parts": [],
        "assemblies": [],
        "cold_reopen": [],
        "write_policy": "WRITE_ONCE_NO_RESUME_NO_OVERWRITE",
    }
    sw = types = pythoncom = None
    protected_pre = {label: fact(path) for label, path, _digest in FIXED_INPUTS}
    try:
        audit = static_audit(require_microfixture=True)
        result["static_audit"] = audit
        if not audit["execution_authorized"]:
            raise GateError("STATIC_EXECUTION_HOLD", "R2 production execution is not authorized", {"audit": audit})
        result["memory_samples_gib"] = base.memory_gate()
        sw, types, pythoncom, session = base.attach_empty_session()
        expected_pid = sbin.resolve_pid(42276)
        if int(session["pid"]) != int(expected_pid):
            raise GateError("SESSION_PID_FAIL", "attached SolidWorks PID differs from requalified Session B", {"expected": expected_pid, "actual": session["pid"]})
        result["solidworks"] = session
        for key, spec in part_specs().items():
            result["parts"].append(loop1d.build_part(sw, types, pythoncom, key, spec))
        for side in ("L", "R"):
            result["assemblies"].append(build_side_assembly(sw, side, types, pythoncom))
        for side in ("L", "R"):
            result["cold_reopen"].append(cold_verify_side(sw, side, types, pythoncom))
        if int(base.value(sw, "GetDocumentCount")) != 0 or base.value(sw, "ActiveDoc") is not None:
            raise GateError("DOCUMENT_CLEANUP_FAIL", "owned documents remain open after cold verification")
        protected_post = {label: fact(path) for label, path, _digest in FIXED_INPUTS}
        if protected_pre != protected_post:
            raise GateError("PROTECTED_INPUT_DRIFT", "protected input changed during R2 build")
        manifest_paths = [Path(spec["target"]) for spec in part_specs().values()] + list(SUCCESSOR_ASSEMBLIES.values()) + [Path(__file__), MICROFIXTURE_RECEIPT, *[path for _label, path, _digest in FIXED_INPUTS]]
        lines = [f"{sha256(path)}  {path.stat().st_size}  {path.relative_to(RUN_ROOT).as_posix() if RUN_ROOT.resolve() in path.resolve().parents else norm(path)}" for path in manifest_paths]
        write_text_once(FINAL_MANIFEST, "\n".join(sorted(lines)) + "\n")
        result.update({
            "timestamp_end_utc": utc_now(),
            "protected_pre": protected_pre,
            "protected_post": protected_post,
            "manifest": fact(FINAL_MANIFEST),
            "claims": {
                "native_panel_count": 6,
                "native_interface_part_count": len(part_specs()) - 6,
                "successor_sldasm_count": 2,
                "true_serial_hinge_count": 6,
                "right_is_xz_mirror_for_symmetric_states": True,
                "left_right_failure_semantics_correct": True,
                "l0_mass_inertia_modified": False,
                "flight_ready": False,
            },
            "remaining_holds": [
                "TOP_LEVEL_INTEGRATION_PENDING",
                "NATIVE_BREP_CLEARANCE_PENDING",
                "CAMERA_MODEL_SELECTION_HOLD",
                "SOLAR_HARNESS_SWEEP_AND_BEND_RADIUS_HOLD",
                "INTERPANEL_MECHANISM_PRODUCT_LIFE_RELIABILITY_HOLD",
                "LAUNCH_LOAD_THERMAL_VACUUM_RANDOM_VIBRATION_FASTENER_MOS_HOLD",
            ],
            "verdict": "V5_SOLAR_R2_NATIVE_SUCCESSOR_BUILD_COLD_REOPEN_PASS",
        })
        write_json_once(SUCCESS_RECEIPT, result)
        print(json.dumps({"verdict": result["verdict"], "receipt": fact(SUCCESS_RECEIPT), "manifest": fact(FINAL_MANIFEST)}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        result.update({"timestamp_end_utc": utc_now(), "verdict": getattr(exc, "code", "V5_SOLAR_R2_SUCCESSOR_UNEXPECTED_FAIL"), "reason": str(exc), "detail": getattr(exc, "detail", {}), "traceback": traceback.format_exc()})
        failure = VALIDATION / f"V5_SOLAR_R2_SUCCESSOR_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
        try:
            write_json_once(failure, result)
        except Exception:
            pass
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    finally:
        if sw is not None:
            close_owned_documents(sw)
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F3R2 V5 solar-array R2 write-once successor builder")
    parser.add_argument("command", choices=("audit", "execute"))
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        print(json.dumps(static_audit(require_microfixture=True), ensure_ascii=False, indent=2))
        return 0
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
