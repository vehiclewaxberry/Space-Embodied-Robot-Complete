#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Materialize immutable V5 authority seeds after G0 and Loop-1 import pass.

The script never creates a V5 root and never connects to SOLIDWORKS.  In audit
mode it is read-only.  In execute mode it writes only previously absent text
artifacts inside the already claimed V5 root.  It deliberately preserves all
camera, pose, flight-load and qualification holds instead of promoting missing
evidence to authority.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
V4 = ENGINEERING / "F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
F3R2 = ENGINEERING / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
G0_RUN = ENGINEERING / "_MFINAL_G0_SMOKE_20260809T172928_P4E8"
G0_READY = G0_RUN / "G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json"
G0_CLAIM = G0_RUN / "G0_V5_EXCLUSIVE_RUN_CLAIM.json"
RELEASE_RE = re.compile(
    r"^F3R2_V5_NATIVE_MECHANICAL_RELEASE_([0-9]{8}T[0-9]{6}_[A-Z0-9]{4,12})$"
)

SOURCES: Dict[str, Dict[str, Any]] = {
    "v4_control_baseline": {
        "path": V4 / "01_authority/MFINAL_CONTROL_BASELINE.yaml",
        "bytes": 3211,
        "sha256": "837E5F1F304D9F4DA7247D276B804F4C07E7111AFF3EDA28482FE0AA4279F512",
    },
    "v4_hdrm_camera_ruling": {
        "path": V4 / "01_authority/MFINAL_HDRM_CAMERA_AUTHORITY_RULING.json",
        "bytes": 17266,
        "sha256": "5A0F6E16C8F215B8C952D7BD008C15979E04013171541DF6373A9747F18F1B57",
    },
    "v4_pose_authority": {
        "path": V4 / "08_poses_paths/MFINAL_POSE_AUTHORITY_REGISTER.csv",
        "bytes": 1735,
        "sha256": "1EB0D4CF3A7CC2B0F785B7C465C3BD89990A6F0647806B12C06BC931F0A3C326",
    },
    "v4_provisional_bom": {
        "path": V4 / "09_bom/MFINAL_PROVISIONAL_BOM.csv",
        "bytes": 6308,
        "sha256": "23AA891C87365F527AE62A32184DCDDD2DE53F08307E6368AA8563BEBBEF63B9",
    },
    "f3r2_pose_register": {
        "path": F3R2 / "04_configurations/F3R2_ARM_POSE_REGISTER.csv",
        "bytes": 3029,
        "sha256": "999163799109D34F369AB634AFC3DA48DAC52D0A09836EE4787B12336D60CE2E",
    },
    "f3r2_pose_freeze": {
        "path": F3R2 / "04_configurations/F3R2_POSE_FREEZE.json",
        "bytes": 970,
        "sha256": "05E399AD909965367C95F9D42019FE4C23C507100CE0C46EFCA3C89B00CE44AC",
    },
}

REQUIRED_DIRS = (
    "00_authority",
    "01_native_parts",
    "04_configurations",
    "06_mass_properties",
    "08_bom",
    "09_digital_thread",
    "13_validation",
    "14_release",
)

OUTPUTS = (
    "00_authority/V5_CONTROL_BASELINE.yaml",
    "00_authority/V5_HDRM_AUTHORITY.yaml",
    "00_authority/SERVICE_CAMERA_DOWNSELECT.md",
    "00_authority/POSE_AUTHORIZATION_REQUIRED.md",
    "00_authority/MFINAL01_LOCATING_SCHEME.yaml",
    "00_authority/MFINAL01_FASTENER_INTERFACE_REGISTER.csv",
    "00_authority/V5_AUTHORITY_SOURCE_REGISTER.json",
    "04_configurations/V5_POSE_AUTHORITY_REGISTER.csv",
    "06_mass_properties/V5_MASS_BOUNDARY.yaml",
    "08_bom/V5_PROVISIONAL_BOM_SEED.csv",
    "13_validation/V5_AUTHORITY_SEED_RECEIPT.json",
    "14_release/V5_AUTHORITY_SEED_MANIFEST_SHA256.txt",
)


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise GateError("JSON_ROOT_FAIL", f"JSON root is not an object: {path}")
    return value


def write_text_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def write_json_once(path: Path, payload: Dict[str, Any]) -> None:
    write_text_once(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def copy_once(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output, source.open("rb") as input_stream:
        shutil.copyfileobj(input_stream, output)


def normalize(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def validate_run_root(raw: str) -> Path:
    candidate = Path(raw).resolve()
    if candidate.parent != ENGINEERING.resolve() or not RELEASE_RE.fullmatch(candidate.name):
        raise GateError(
            "RUN_ROOT_SCOPE_FAIL",
            "run root must be the unique formal V5 root directly under 20_engineering",
            {"actual": str(candidate).replace("\\", "/")},
        )
    return candidate


def audit_sources() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for name, contract in SOURCES.items():
        path = Path(contract["path"])
        row = {
            "name": name,
            "path": str(path).replace("\\", "/"),
            "exists": path.is_file(),
            "expected_bytes": int(contract["bytes"]),
            "actual_bytes": path.stat().st_size if path.is_file() else None,
            "expected_sha256": contract["sha256"],
            "actual_sha256": sha256(path) if path.is_file() else None,
        }
        row["pass"] = bool(
            row["exists"]
            and row["actual_bytes"] == row["expected_bytes"]
            and row["actual_sha256"] == row["expected_sha256"]
        )
        rows.append(row)
    return rows


def validate_chain(root: Path) -> Dict[str, Any]:
    if not root.is_dir():
        raise GateError("V5_ROOT_MISSING", "formal V5 root does not exist")
    missing_dirs = [relative for relative in REQUIRED_DIRS if not (root / relative).is_dir()]
    if missing_dirs:
        raise GateError("V5_DIRECTORY_CONTRACT_FAIL", "required V5 directories are missing", {"missing": missing_dirs})
    if not G0_READY.is_file():
        raise GateError("G0_READY_MISSING", "G0 final receipt is absent")
    g0 = load_json(G0_READY)
    if g0.get("verdict") != "G0_SOLIDWORKS_NATIVE_EXECUTION_READY":
        raise GateError("G0_READY_VERDICT_FAIL", "G0 receipt does not authorize execution")
    if not G0_CLAIM.is_file():
        raise GateError("G0_CLAIM_MISSING", "exclusive G0-to-V5 run claim is absent")
    claim = load_json(G0_CLAIM)
    if claim.get("schema") != "F3R2_V5_EXCLUSIVE_RUN_CLAIM_V1":
        raise GateError("G0_CLAIM_SCHEMA_FAIL", "exclusive run claim schema is invalid")
    if normalize(Path(str(claim.get("target", "")))) != normalize(root):
        raise GateError("G0_CLAIM_TARGET_FAIL", "exclusive run claim targets another root")
    if claim.get("g0_ready_receipt_sha256") != sha256(G0_READY):
        raise GateError("G0_CLAIM_HASH_FAIL", "exclusive run claim does not bind the current G0 receipt")
    receipt_path = root / "13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
    if not receipt_path.is_file():
        raise GateError("LOOP1_IMPORT_RECEIPT_MISSING", "Loop-1 neutral import receipt is absent")
    receipt = load_json(receipt_path)
    if receipt.get("verdict") != "V5_LOOP1_NEUTRAL_NATIVE_PART_IMPORT_PASS" or receipt.get("native_part_count") != 20:
        raise GateError("LOOP1_IMPORT_RECEIPT_FAIL", "Loop-1 neutral import is not a 20-part PASS")
    native_parts = receipt.get("native_parts")
    if not isinstance(native_parts, list) or len(native_parts) != 20:
        raise GateError("LOOP1_NATIVE_PART_LIST_FAIL", "Loop-1 native part evidence is incomplete")
    for item in native_parts:
        if not isinstance(item, dict) or not isinstance(item.get("target"), dict):
            raise GateError("LOOP1_NATIVE_PART_ROW_FAIL", "malformed native part evidence")
        target = Path(str(item["target"].get("path", ""))).resolve()
        if root.resolve() not in target.parents or not target.is_file():
            raise GateError("LOOP1_NATIVE_PART_PATH_FAIL", "native part is absent or outside V5", {"path": str(target)})
        expected_hash = item["target"].get("sha256")
        expected_bytes = item["target"].get("bytes")
        if sha256(target) != expected_hash or target.stat().st_size != expected_bytes:
            raise GateError("LOOP1_NATIVE_PART_DRIFT", "native part changed after import", {"path": str(target)})
    return {
        "g0_ready": str(G0_READY).replace("\\", "/"),
        "g0_ready_sha256": sha256(G0_READY),
        "exclusive_claim": str(G0_CLAIM).replace("\\", "/"),
        "exclusive_claim_sha256": sha256(G0_CLAIM),
        "loop1_import_receipt": str(receipt_path).replace("\\", "/"),
        "loop1_import_receipt_sha256": sha256(receipt_path),
        "native_part_count": 20,
    }


def control_baseline_yaml(run_id: str, sources: List[Dict[str, Any]]) -> str:
    source_lines = "\n".join(
        f"  {row['name']}: {row['actual_sha256']}" for row in sources
    )
    return f"""schema: F3R2_V5_CONTROL_BASELINE_V1
baseline_id: F3R2_V5_NATIVE_MECHANICAL_RELEASE_{run_id}
parent: F3R2_V4_COMPETITION_NEUTRAL_MECHANICAL_DESIGN_BASIS
current_maturity: LOOP1_NATIVE_PART_IMPORT_PASS_AUTHORITY_SEEDED_NOT_ASSEMBLED
immutable_truth:
  l0: accepted_B601_URDF
  joint_topology_axes_lengths_mass_inertia: DO_NOT_MODIFY
  b601_competition_interface: 4_x_M4_CLASS_at_64_x_64_mm_square
  equivalent_pcd_mm: 90.509642
  rejected_claim: 8_x_M3
native_candidate:
  stage_a: RevB2_native_part
  stage_b: RevB2_native_part
  locating: central_round_pilot_plus_one_relief_or_diamond_locator
hdrm:
  preload: +X
  operational_release: -X
  ground_unlock: +Z
  stroke_candidate_mm: 6.0
camera:
  selection: UNSELECTED
  interface_and_envelope_freeze_allowed: true
  camera_model_selection_hold: true
pose_authority:
  authorized_runtime_inputs: [Q_DEPLOYED_HOME, Q_RELEASE_CLEAR, Q_SERVICE_READY]
  candidate_only: [Q_STOW_ENGINEERING_CANDIDATE]
  not_authorized: [Q_SERVICE_DOCKING, Q_SERVICE_GRASP, Q_SERVICE_TRANSPORT, Q_SERVICE_ASSEMBLY, Q_RETRIEVED]
prohibited_claims:
  - FINAL_NATIVE_CAD_BASELINE
  - MANUFACTURING_RELEASED_BASELINE
  - FLIGHT_READY
  - LAUNCH_QUALIFIED
  - FULLY_AUTHORIZED_SERVICE_AND_GRASP_TRAJECTORY
source_sha256:
{source_lines}
"""


def hdrm_yaml() -> str:
    return """schema: F3R2_V5_HDRM_AUTHORITY_V1
designation: ARM_HDRM
scope: COMPETITION_DEMONSTRATOR_FUNCTIONAL_ENVELOPE
controlling_chain: P4D_to_P5B_to_P5D
directions:
  preload: [+1.0, 0.0, 0.0]
  operational_release: [-1.0, 0.0, 0.0]
  ground_removal_unlock: [0.0, 0.0, 1.0]
release_stroke_candidate_mm: 6.0
working_preload_candidate_N: 50.0
mechanism_route: ELECTROMAGNET_HOLD_RELEASE_PLUS_COMPRESSION_SPRING_PLUS_MECHANICAL_STOP
required_native_states: [LOCKED, RELEASE_ARMED, RELEASE_START, RELEASED, RELEASE_FAILED, GROUND_UNLOCK]
physical_status: FUNCTIONAL_ENVELOPE_PENDING_NATIVE_ASSEMBLY
holds:
  - FLIGHT_ACTUATOR_PROCUREMENT_TBD
  - PRODUCT_FORCE_CURRENT_THERMAL_DUTY_TBD
  - MATING_BREP_AND_CLOCKING_TBD
  - PHYSICAL_RELEASE_TEST_TBD
  - FLIGHT_QUALIFICATION_HOLD
"""


def camera_downselect_md() -> str:
    return """# SERVICE_CAMERA down-select — V5 authority seed

Decision: `SERVICE_CAMERA = UNSELECTED`; freeze only `CAMERA_INTERFACE_STANDARD` and `CAMERA_ENVELOPE`.
The current conditional prototype preference is Intel RealSense D405 with the local `D405_305_Mount.step`, but this is not a purchase, model-selection, calibration, or release authority.

| Candidate donor | Local mount envelope (mm) | Mass | FOV / working distance / minimum range | Data | Mountability | Occlusion evidence | Disposition |
|---|---:|---|---|---|---|---|---|
| D435/Gemini2 mount | 95.761 × 53.515 × 28.464 | Camera and mount mass not authorized | No authoritative local camera model or optical data | Connector/USB route not closed | B601 wrist donor geometry exists; camera-side interface is geometry-only | Not evaluated with a selected camera | `VENDOR_DONOR_ONLY` |
| D405/305 mount | 94.448 × 70.906 × 33.962 | Camera, cable and printed mount mass not authorized | Driver, depth, intrinsics, FOV, working distance and minimum range not locally closed | Eye-in-hand TF clue exists; USB/data implementation not closed | Best local evidence: mounted-photo plus TF clue; physical fit still required | Final wrist/gripper/FOV sweep missing | `CONDITIONAL_PROTOTYPE_ROUTE_NOT_RELEASED` |
| UVC32 mount | 70.002 × 69.444 × 32.311 | Not authorized | No authoritative local intrinsics/FOV/range evidence | USB/data and connector details not closed | Four-hole donor geometry only | Not evaluated | `VENDOR_DONOR_ONLY_LOWEST_LOCAL_MATURITY` |

Frozen wrist-side candidate interface: contact cylinder radius 28.5 mm, two geometry-only Ø2.7 mm holes at 22.0 mm spacing, nominal mount-plane tilt 15°. These values are not thread, tolerance, optical-frame or calibration authority.

Activation requires exact camera part number, OEM ICD/CAD, physical fit, mass/CoM, connector and cable, driver/depth/intrinsics, hand–eye calibration, FOV/occlusion and swept-clearance PASS. Until then: `CAMERA_MODEL_SELECTION_HOLD`.
"""


def pose_authorization_md() -> str:
    return """# Pose authorization required — V5

No service pose is promoted by CAD automation. L0 joint topology, axes, limits and accepted dynamics remain unchanged.

| Pose | q (deg) | Class | Permitted V5 use |
|---|---|---|---|
| Q_DEPLOYED_HOME | [-90,-120,-60,0,-30,0] | `AUTHORIZED_RUNTIME_INPUT` | Control/dynamics initialization; must be revalidated against V5 geometry |
| Q_RELEASE_CLEAR | [-90,-120,-120,-60,-30,0] | `AUTHORIZED_GEOMETRIC_END_STATE` | End state only; release sequence still requires authority and native validation |
| Q_SERVICE_READY | [-90,-60,-120,-30,0,0] | `AUTHORIZED_RUNTIME_INPUT_WITH_SERVICE_RATIFICATION_HOLD` | Pre-service staging only |
| Q_STOW_ENGINEERING | [145.572,-168,-57,-41.143,-20.954,-3] | `CANDIDATE` | Engineering fit-up seed; not a runtime/control authority |
| Q_SERVICE_DOCKING | — | `NOT_AUTHORIZED` | Candidate search only |
| Q_SERVICE_GRASP | — | `NOT_AUTHORIZED` | Candidate search only |
| Q_SERVICE_TRANSPORT | — | `NOT_AUTHORIZED` | Candidate search only |
| Q_SERVICE_ASSEMBLY | — | `NOT_AUTHORIZED` | Candidate search only |
| Q_RETRIEVED | — | `NOT_AUTHORIZED` | Candidate search only |

For each missing service state, Loop 2 may emit an `IK_CANDIDATE_SET` ranked by joint margin, arm–bus/wing clearance, base reaction, camera visibility and EE pose error. Human approval is required before any candidate becomes authoritative.
"""


def locating_yaml() -> str:
    return """schema: MFINAL01_V5_LOCATING_SCHEME_V1
assembly: B601_BASE_ADAPTER_REV_B2
status: DESIGN_INTENT_PENDING_NATIVE_MATE_AND_BREP_MEASUREMENT
primary_locator:
  type: ROUND_CENTRAL_PILOT
  role: radial_location
secondary_locator:
  type: RELIEVED_OR_DIAMOND_DOWEL
  nominal_center_mm: [55.0, 0.0]
  role: single_clocking_constraint_without_second_round-hole_overconstraint
axial_location:
  type: MATING_FACE_COINCIDENT
prohibited:
  - TWO_PARALLEL_ROUND_DOWELS_WITH_FULL_RADIAL_CONSTRAINT
  - EIGHT_X_M3_B601_INTERFACE
native_gate:
  required: [mate_error_zero, not_overdefined, face_measurement, minimum_distance, cold_reopen]
  current: HOLD_PENDING_LOOP1_ASSEMBLY
"""


def fastener_csv() -> str:
    rows = [
        ["interface", "quantity", "size_class", "pattern", "hole_candidate_mm", "washer_envelope", "grade_material", "thread_engagement", "assembly_torque", "locking", "status"],
        ["B601_to_Stage_A", "4", "M4-class", "64x64 square / PCD 90.509642", "4.6 CB 7.5", "NATIVE_CHECK_REQUIRED", "TBD_FROM_AS_BUILT_HARDWARE", "TBD", "TBD", "TBD", "AS_BUILT_PATTERN_AUTHORIZED_PRELOAD_HOLD"],
        ["Stage_A_to_Stage_B", "8", "M5", "R62.5 equal pattern", "CLEARANCE_CANDIDATE", "NATIVE_CHECK_REQUIRED", "A2-70_OR_EQUIVALENT_CANDIDATE", "MIN_1.0D_CANDIDATE", "TBD_AFTER_FRICTION_AND_THREAD_SELECTION", "ALL_METAL_LOCKNUT_OR_THREADLOCK_CANDIDATE", "COMPETITION_TRANSITION_CANDIDATE"],
        ["Stage_B_to_load_bridge", "4", "M6", "140x140 square", "6.6", "OD12_CANDIDATE_NATIVE_CHECK", "A2-70_OR_EQUIVALENT_CANDIDATE", "MIN_1.0D_CANDIDATE", "TBD_AFTER_FRICTION_AND_COUNTERPART", "ALL_METAL_LOCKNUT_OR_THREADLOCK_CANDIDATE", "PRIMARY_LOAD_PATTERN_CANDIDATE_COUNTERPART_HOLD"],
        ["clocking_locator", "1", "4mm diamond/relieved", "center [55,0] mm", "SOURCE_HOLE_CANDIDATE", "N/A", "HARDENED_STAINLESS_CANDIDATE", "PRESS_SLIP_PAIR_TBD", "N/A", "POSITIVE_RETENTION_TBD", "DESIGN_INTENT_NATIVE_MATE_HOLD"],
    ]
    return "\n".join(",".join(f'"{cell}"' if "," in cell else cell for cell in row) for row in rows) + "\n"


def mass_boundary_yaml() -> str:
    return """schema: F3R2_V5_MASS_BOUNDARY_V1
l0_accepted_b601:
  source: 20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf
  role: IMMUTABLE_DYNAMICS_TRUTH
  cad_override_allowed: false
v5_external_mechanical:
  role: SEPARATE_ADDED_HARDWARE_BUDGET
  v4_known_material_candidate_mass_g: 1293.360439
  value_status: PROVISIONAL_PARENT_VALUE_TO_BE_REPLACED_BY_V5_NATIVE_MEASUREMENTS
  required_source_classes: [MEASURED_CAD, VENDOR, ESTIMATED]
  required_items: [Stage_A, Stage_B, wing_root_left, wing_root_right, G07, G08, Mid, pads, springs, HDRM, camera_bracket, camera_or_envelope, harness, gripper, fasteners, pins]
inertia:
  accepted_b601: DO_NOT_MODIFY
  v5_external_added: RECOMPUTE_SEPARATELY_AFTER_NATIVE_MATERIAL_ASSIGNMENT
flight_claim: PROHIBITED
"""


def static_audit(raw_root: str) -> Dict[str, Any]:
    root = validate_run_root(raw_root)
    sources = audit_sources()
    return {
        "schema": "F3R2_V5_AUTHORITY_SEED_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "run_root": str(root).replace("\\", "/"),
        "run_root_exists": root.is_dir(),
        "sources": sources,
        "sources_pass": all(row["pass"] for row in sources),
        "g0_ready_exists": G0_READY.is_file(),
        "exclusive_claim_exists": G0_CLAIM.is_file(),
        "loop1_import_receipt_exists": (root / "13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json").is_file(),
        "outputs_existing": [relative for relative in OUTPUTS if (root / relative).exists()],
        "execution_authorized": bool(
            root.is_dir()
            and all(row["pass"] for row in sources)
            and G0_READY.is_file()
            and G0_CLAIM.is_file()
            and (root / "13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json").is_file()
            and not any((root / relative).exists() for relative in OUTPUTS)
        ),
        "verdict": "AUTHORITY_SEED_INPUTS_PASS_RUNTIME_CHAIN_PENDING"
        if all(row["pass"] for row in sources)
        else "AUTHORITY_SEED_SOURCE_AUDIT_FAIL",
    }


def execute(raw_root: str) -> int:
    root = validate_run_root(raw_root)
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_AUTHORITY_SEED_RECEIPT_V1",
        "timestamp_start_utc": utc_now(),
        "run_root": str(root).replace("\\", "/"),
    }
    try:
        sources = audit_sources()
        if not all(row["pass"] for row in sources):
            raise GateError("AUTHORITY_SOURCE_DRIFT", "one or more authority sources changed", {"sources": sources})
        chain = validate_chain(root)
        existing = [relative for relative in OUTPUTS if (root / relative).exists()]
        if existing:
            raise GateError("AUTHORITY_OUTPUT_ALREADY_EXISTS", "write-once authority output exists", {"existing": existing})
        run_id = RELEASE_RE.fullmatch(root.name).group(1)  # type: ignore[union-attr]

        write_text_once(root / "00_authority/V5_CONTROL_BASELINE.yaml", control_baseline_yaml(run_id, sources))
        write_text_once(root / "00_authority/V5_HDRM_AUTHORITY.yaml", hdrm_yaml())
        write_text_once(root / "00_authority/SERVICE_CAMERA_DOWNSELECT.md", camera_downselect_md())
        write_text_once(root / "00_authority/POSE_AUTHORIZATION_REQUIRED.md", pose_authorization_md())
        write_text_once(root / "00_authority/MFINAL01_LOCATING_SCHEME.yaml", locating_yaml())
        write_text_once(root / "00_authority/MFINAL01_FASTENER_INTERFACE_REGISTER.csv", fastener_csv())
        write_json_once(
            root / "00_authority/V5_AUTHORITY_SOURCE_REGISTER.json",
            {"schema": "F3R2_V5_AUTHORITY_SOURCE_REGISTER_V1", "timestamp_utc": utc_now(), "sources": sources, "chain": chain},
        )
        copy_once(Path(SOURCES["v4_pose_authority"]["path"]), root / "04_configurations/V5_POSE_AUTHORITY_REGISTER.csv")
        write_text_once(root / "06_mass_properties/V5_MASS_BOUNDARY.yaml", mass_boundary_yaml())
        copy_once(Path(SOURCES["v4_provisional_bom"]["path"]), root / "08_bom/V5_PROVISIONAL_BOM_SEED.csv")

        manifest_rows = []
        for relative in OUTPUTS:
            if relative.startswith("13_validation/") or relative.startswith("14_release/"):
                continue
            path = root / relative
            manifest_rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
        result.update(
            {
                "source_audit": sources,
                "runtime_chain": chain,
                "materialized": manifest_rows,
                "timestamp_end_utc": utc_now(),
                "verdict": "V5_AUTHORITY_SEEDS_MATERIALIZED_PASS",
                "remaining_holds": [
                    "NATIVE_ASSEMBLY_MATES_CONFIGURATIONS_HOLD",
                    "CAMERA_MODEL_SELECTION_HOLD",
                    "SERVICE_POSE_HUMAN_AUTHORITY_HOLD",
                    "FASTENER_PRELOAD_MOS_AND_COUNTERPART_HOLD",
                    "FLIGHT_QUALIFICATION_HOLD",
                ],
            }
        )
        receipt = root / "13_validation/V5_AUTHORITY_SEED_RECEIPT.json"
        write_json_once(receipt, result)
        lines = [f"{row['sha256']}  {row['bytes']}  {row['path']}" for row in manifest_rows]
        lines.append(f"{sha256(receipt)}  {receipt.stat().st_size}  {receipt.relative_to(root).as_posix()}")
        manifest = root / "14_release/V5_AUTHORITY_SEED_MANIFEST_SHA256.txt"
        write_text_once(manifest, "\n".join(sorted(lines)) + "\n")
        print(json.dumps({"verdict": result["verdict"], "receipt": str(receipt).replace("\\", "/"), "receipt_sha256": sha256(receipt), "manifest_sha256": sha256(manifest), "file_count": len(manifest_rows) + 2}, ensure_ascii=False, indent=2))
        return 0
    except GateError as exc:
        result.update({"verdict": exc.code, "reason": str(exc), "detail": exc.detail, "timestamp_end_utc": utc_now()})
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("audit", "execute"):
        child = sub.add_parser(name)
        child.add_argument("--run-root", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        print(json.dumps(static_audit(args.run_root), ensure_ascii=False, indent=2))
        return 0
    return execute(args.run_root)


if __name__ == "__main__":
    raise SystemExit(main())
