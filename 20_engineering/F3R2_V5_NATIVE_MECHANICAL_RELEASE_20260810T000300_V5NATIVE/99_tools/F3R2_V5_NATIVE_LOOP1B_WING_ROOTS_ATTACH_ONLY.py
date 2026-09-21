#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F3R2 V5 Loop-1B dual wing-root native closure.

This file is intentionally split into two write-once stages:

* 1B0 independently clones the two physical panel donors and the V2.2
  pin/spring/stop/service-loop donors into the one claimed V5 root, breaks all
  file links, and cold-reopens every native part.
* 1B1 creates one native U-lug and one native axial retainer per side, builds
  two true-hinge assemblies with real lock/concentric/coincident mates, writes
  the six authorised configurations, and cold-reopens both assemblies.

The only application attachment call is GetActiveObject.  The program neither
starts nor terminates the application and never changes UI ownership settings.
All CAD/receipt writes are confined to the fixed V5 root.  Existing Loop-1,
Loop-1A, G0, frozen-parent and protected files are hash-audited PRE and POST.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
RUN_ROOT = ENGINEERING / "F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
RUN_ID = "20260810T000300_V5NATIVE"
sys.path.insert(0, str(RUN_ROOT / "99_tools"))
import F3R2_V5_SESSION_BINDING as sbin
import F3R2_V5_MEMORY_OVERRIDE as mo
G0_READY = ENGINEERING / "_MFINAL_G0_SMOKE_20260809T172928_P4E8/G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json"
IMPORT_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
LOOP1A_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1A_SUBASSEMBLY_RECEIPT.json"
PROTECTED_PRE_RECEIPT = RUN_ROOT / "00_authority/V5_PROTECTED_BASELINE_PRE.json"
AUTHORITY_RECEIPT = RUN_ROOT / "13_validation/V5_AUTHORITY_SEED_RECEIPT.json"
LOOP1_MANIFEST = RUN_ROOT / "14_release/V5_LOOP1_NATIVE_PART_MANIFEST_SHA256.txt"
LOOP1A_MANIFEST = RUN_ROOT / "14_release/V5_LOOP1A_SUBASSEMBLY_MANIFEST_SHA256.txt"
POSE_REGISTER = RUN_ROOT / "04_configurations/V5_POSE_AUTHORITY_REGISTER.csv"
ANGLE_AUTHORITY = ENGINEERING / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/04_configurations/G2/F3R1_G2_CONFIG_ANGLE_AUTHORITY.json"

FIXED_INPUTS: Tuple[Tuple[Path, str], ...] = (
    (G0_READY, "58F8240B1D158867C1B61B09B4A098F5AB670141A3CFEE983F5AD2A637CA5CA6"),
    (IMPORT_RECEIPT, "9FC8D1DBBBDD7D1FE37F5FCCA4359838827282A0D7A961D8EEB511E75BE7160D"),
    (LOOP1A_RECEIPT, "F946A361A7CFF8143753853911F23178AF68592D2F7BBE09990575ED86E9BF49"),
    (PROTECTED_PRE_RECEIPT, "EB95A5B4F611BBFB119B6F88A8F25C8DA81B4EA2A3626406C009BF9D05B0B69C"),
    (AUTHORITY_RECEIPT, "7251758420639907CAB4F4C134A278B0F860535BCC62A8E264E6862B7ECBED0F"),
    (LOOP1_MANIFEST, "23D4E4F87CB94C41BB193919BD62751AB18A65ECA898E813842E02E8CDBA8CAF"),
    (LOOP1A_MANIFEST, "5F0E03E49424DCB832D9B2A992459C23053F0CB96963E7CEBEFCF4810DF7C20D"),
    (POSE_REGISTER, "1EB0D4CF3A7CC2B0F785B7C465C3BD89990A6F0647806B12C06BC931F0A3C326"),
    (ANGLE_AUTHORITY, "1BDBCD3598B6C262E16CE3DF10CEA5BDE11FBF382F4192BAB92D6729CA9F5AF1"),
)

PART_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot")
ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot")
TEMPLATES = (
    (PART_TEMPLATE, "5DA21678EFE07EF465770630BEB4FFE540F23D47FCA07715F74D2AFDBEA87271"),
    (ASSEMBLY_TEMPLATE, "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC"),
)

PROTECTED: Tuple[Tuple[str, Path, str], ...] = (
    ("accepted_b601_urdf", ENGINEERING / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf", "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"),
    ("mass_inertia_budget", ENGINEERING / "stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv", "073C802527E35C9495188EEFD5D8BA51F524D326142CF2AB31E436BAD0899392"),
    ("v2_2_native_donor_top", ENGINEERING / "cad/Space_Embodied_Robot_CAD_V2_2_NATIVE/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM", "30C09B50A0D2967EC1F48050CAAC34D12A43565C44978D54E3785595202DEF7A"),
    ("b51_articulated_arm_donor", ENGINEERING / "cad/B5_1_B601_interface_closure_candidate/03_CAD/native_articulated/B51_ARTICULATED_20260728T008/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM", "603B87BBD4398FDDB3F732FFBFA7E1C080ED91ED6E0A026D56CBDCBA08DE2E22"),
    ("f3r1_frozen_top", ENGINEERING / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM", "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0"),
    ("f3r2_frozen_top", ENGINEERING / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM", "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0"),
)

DONOR_ROOT = ENGINEERING / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad"
LOCAL_PARTS = RUN_ROOT / "01_native_parts/wing_root/loop1b"
LOCAL_ASSEMBLIES = RUN_ROOT / "02_native_subassemblies"
VALIDATION = RUN_ROOT / "13_validation"
RELEASE = RUN_ROOT / "14_release"
TOOLS = RUN_ROOT / "99_tools"


def _donor(key: str, relative: str, target: str, size: int, digest: str, bbox: Sequence[float]) -> Dict[str, Any]:
    return {
        "key": key,
        "source": DONOR_ROOT / relative,
        "target": LOCAL_PARTS / target,
        "bytes": size,
        "sha256": digest,
        "bbox_mm": list(bbox),
    }


DONORS: Dict[str, Dict[str, Any]] = {
    row["key"]: row
    for row in (
        _donor("L_PANEL", "WING_PANEL_DONORS/WING_L_DEPLOYED.SLDPRT", "LEFT_WING_PANEL_PHYSICAL.SLDPRT", 59302, "E9C4C7E73C5B09CEFCCA2F69CDDAD94734E139D253F88331399530A8E344829E", [-174.5, 113.15, -3.0, 52.5, 313.15, 3.0]),
        _donor("R_PANEL", "WING_PANEL_DONORS/WING_R_DEPLOYED.SLDPRT", "RIGHT_WING_PANEL_PHYSICAL.SLDPRT", 59007, "2CFC2127657A719B9FEB9D4C305471D0C8621B49A961B97170A5B99EC1CFE41E", [-174.5, -313.15, -3.0, 52.5, -113.15, 3.0]),
        _donor("L_PIN", "SPACECRAFT_V2_2_NATIVE_COPY/05_Solar_Array_Root_Left/parts/Hinge_Pin_Left.SLDPRT", "LEFT_HINGE_PIN_V22_ISOLATED.SLDPRT", 80281, "56CC018D8B38F0AA5390352700DBF45401164BEA816122CCD752AFCE8540B8A3", [-82.0, 139.15, -4.0, -40.0, 147.15, 4.0]),
        _donor("L_SPRING_1", "SPACECRAFT_V2_2_NATIVE_COPY/05_Solar_Array_Root_Left/parts/Torsion_Spring_1_Left.SLDPRT", "LEFT_TORSION_SPRING_1_V22_ISOLATED.SLDPRT", 110838, "36D2B35533FBC23AF179558733748F02165D9510F92E566D4C7634205D9D55D7", [-93.0, 135.15, -8.0, -75.0, 151.15, 8.0]),
        _donor("L_SPRING_2", "SPACECRAFT_V2_2_NATIVE_COPY/05_Solar_Array_Root_Left/parts/Torsion_Spring_2_Left.SLDPRT", "LEFT_TORSION_SPRING_2_V22_ISOLATED.SLDPRT", 111772, "365E11C3A0B57DE7D5930F3AC2CBC2099152BAB0E0CBE41BF4527F0D8DA594F7", [-47.0, 135.15, -8.0, -29.0, 151.15, 8.0]),
        _donor("L_STOP", "SPACECRAFT_V2_2_NATIVE_COPY/05_Solar_Array_Root_Left/parts/Hard_Stop_Left.SLDPRT", "LEFT_HARD_STOP_V22_ISOLATED.SLDPRT", 83555, "7E85674A08506F771130087EB0E705FCA1B0C2CB529816CE2EAA0932529B4C47", [-64.0, 121.15, 23.0, -58.0, 129.15, 37.0]),
        _donor("L_LOOP", "SPACECRAFT_V2_2_NATIVE_COPY/05_Solar_Array_Root_Left/parts/Harness_Service_Loop_Left.SLDPRT", "LEFT_HARNESS_SERVICE_LOOP_V22_ISOLATED.SLDPRT", 82003, "8622257C5DFE7E9DAA9C9A471BB206D2D7257F7A55D9B8FBEA24FE6CD818BAE2", [-110.0, 113.15, -30.0, -90.0, 131.15, -10.0]),
        _donor("R_PIN", "SPACECRAFT_V2_2_NATIVE_COPY/06_Solar_Array_Root_Right/parts/Hinge_Pin_Right.SLDPRT", "RIGHT_HINGE_PIN_V22_ISOLATED.SLDPRT", 80720, "8935CF08C7A202E40242A73D307574CDFC6355296A0CB0ADB21BCC8F5C899AFD", [-82.0, -147.15, -4.0, -40.0, -139.15, 4.0]),
        _donor("R_SPRING_1", "SPACECRAFT_V2_2_NATIVE_COPY/06_Solar_Array_Root_Right/parts/Torsion_Spring_1_Right.SLDPRT", "RIGHT_TORSION_SPRING_1_V22_ISOLATED.SLDPRT", 111072, "BEB17DC196CB8D9C5BAAA33FDC6AC1268E5DB7DAF8F0377E411817ED66F8F590", [-93.0, -151.15, -8.0, -75.0, -135.15, 8.0]),
        _donor("R_SPRING_2", "SPACECRAFT_V2_2_NATIVE_COPY/06_Solar_Array_Root_Right/parts/Torsion_Spring_2_Right.SLDPRT", "RIGHT_TORSION_SPRING_2_V22_ISOLATED.SLDPRT", 111683, "7FE2B4A0C074CA49F6A8DB69F2F023B50CDA142E2EF43D959F475EA2A30E1256", [-47.0, -151.15, -8.0, -29.0, -135.15, 8.0]),
        _donor("R_STOP", "SPACECRAFT_V2_2_NATIVE_COPY/06_Solar_Array_Root_Right/parts/Hard_Stop_Right.SLDPRT", "RIGHT_HARD_STOP_V22_ISOLATED.SLDPRT", 83614, "63FF1F13F98919D3ABC5D3133829AE97970D0FAD0678756244909278013CF31E", [-64.0, -129.15, 23.0, -58.0, -121.15, 37.0]),
        _donor("R_LOOP", "SPACECRAFT_V2_2_NATIVE_COPY/06_Solar_Array_Root_Right/parts/Harness_Service_Loop_Right.SLDPRT", "RIGHT_HARNESS_SERVICE_LOOP_V22_ISOLATED.SLDPRT", 82471, "92107125133430F1145C340839CBD7855403C88CB7F6CDE83E6E4BC862CF7C31", [-110.0, -131.15, -30.0, -90.0, -113.15, -10.0]),
    )
}

V5_PART = {
    "L_CLEVIS": RUN_ROOT / "01_native_parts/wing_root/LEFT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT",
    "R_CLEVIS": RUN_ROOT / "01_native_parts/wing_root/RIGHT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT",
    "SPACER": RUN_ROOT / "01_native_parts/wing_root/WING_HINGE_AXIAL_SPACER.SLDPRT",
    "GROMMET": RUN_ROOT / "01_native_parts/wing_root/WING_HARNESS_GROMMET.SLDPRT",
    "STOP_PAD": RUN_ROOT / "01_native_parts/wing_root/WING_MECHANICAL_STOP_PAD.SLDPRT",
}

SIDES: Dict[str, Dict[str, Any]] = {
    "L": {
        "axis_y_mm": 143.15,
        "stowed_rotation_rad": -math.pi / 2.0,
        "panel": DONORS["L_PANEL"]["target"],
        "pin": DONORS["L_PIN"]["target"],
        "springs": (DONORS["L_SPRING_1"]["target"], DONORS["L_SPRING_2"]["target"]),
        "stop": DONORS["L_STOP"]["target"],
        "loop": DONORS["L_LOOP"]["target"],
        "clevis": V5_PART["L_CLEVIS"],
        "lug": LOCAL_PARTS / "LEFT_PANEL_SIDE_U_LUG_NATIVE.SLDPRT",
        "retainer": LOCAL_PARTS / "LEFT_HINGE_AXIAL_RETAINER_NATIVE.SLDPRT",
        "assembly": LOCAL_ASSEMBLIES / "LEFT_WING_ROOT_TRUE_HINGE.SLDASM",
    },
    "R": {
        "axis_y_mm": -143.15,
        "stowed_rotation_rad": math.pi / 2.0,
        "panel": DONORS["R_PANEL"]["target"],
        "pin": DONORS["R_PIN"]["target"],
        "springs": (DONORS["R_SPRING_1"]["target"], DONORS["R_SPRING_2"]["target"]),
        "stop": DONORS["R_STOP"]["target"],
        "loop": DONORS["R_LOOP"]["target"],
        "clevis": V5_PART["R_CLEVIS"],
        "lug": LOCAL_PARTS / "RIGHT_PANEL_SIDE_U_LUG_NATIVE.SLDPRT",
        "retainer": LOCAL_PARTS / "RIGHT_HINGE_AXIAL_RETAINER_NATIVE.SLDPRT",
        "assembly": LOCAL_ASSEMBLIES / "RIGHT_WING_ROOT_TRUE_HINGE.SLDASM",
    },
}

CONFIG_ANGLES: Dict[str, Dict[str, Optional[float]]] = {
    "STOWED": {"L": 0.0, "R": 0.0},
    "DEPLOYING": {"L": None, "R": None},
    "DEPLOYED": {"L": 90.0, "R": 90.0},
    "L_FAIL": {"L": 0.0, "R": 90.0},
    "R_FAIL": {"L": 90.0, "R": 0.0},
    "BOTH_FAIL": {"L": 0.0, "R": 0.0},
}

STAGE_1B0 = VALIDATION / "V5_LOOP1B0_DONOR_IMPORT_CHECKPOINT.json"
STAGE_1B1 = VALIDATION / "V5_LOOP1B1_WING_ROOT_CHECKPOINT.json"
FINAL_RECEIPT = VALIDATION / "V5_LOOP1B_WING_ROOT_RECEIPT.json"
FINAL_MANIFEST = RELEASE / "V5_LOOP1B_WING_ROOT_MANIFEST_SHA256.txt"
SCRIPT_COPY = TOOLS / Path(__file__).name

# Narrow, write-once checkpoint migration for the exact script revision that
# created the verified Loop-1B0 donors and L/R lug/retainer artifacts.  The
# predecessor failed only because SW2024 AddMate3 returns IMate2, not IFeature;
# all target bytes and fixed-input bindings remain independently re-audited.
CHECKPOINT_SCRIPT_PREDECESSOR_SHA256 = "93332FEA56F8D363C6F139163D7396CAFE58EA21388B1C169693A69C50239C15"

SW_TLB = ("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)
SW_PROG_ID = "SldWorks.Application"
SW_EXE = Path(r"F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe")
SW_PART = 1
SW_ASSEMBLY = 2
SW_OPEN_SILENT = 1
SW_OPEN_READ_ONLY = 2
SW_MATE_COINCIDENT = 0
SW_MATE_CONCENTRIC = 1
SW_MATE_LOCK = 16
SW_ALIGN_ALIGNED = 0
SW_ALIGN_ANTI_ALIGNED = 1
SW_ALIGN_CLOSEST = 2
SW_ADD_MATE_NO_ERROR = 1
SW_UNKNOWN_CONSTRAINT = 1
SW_UNDER_CONSTRAINED = 2
SW_FULLY_CONSTRAINED = 3
SW_OVER_CONSTRAINED = 4
SW_NO_SOLUTION = 5
SW_INVALID_SOLUTION = 6
SW_AUTOSOLVE_OFF = 7
SW_CONSTRAINED_STATUS_NAMES = {
    SW_UNKNOWN_CONSTRAINT: "swUnknownConstraint",
    SW_UNDER_CONSTRAINED: "swUnderConstrained",
    SW_FULLY_CONSTRAINED: "swFullyConstrained",
    SW_OVER_CONSTRAINED: "swOverConstrained",
    SW_NO_SOLUTION: "swNoSolution",
    SW_INVALID_SOLUTION: "swInvalidSolution",
    SW_AUTOSOLVE_OFF: "swAutosolveOff",
}
SW_GET_REMAINING_DOFS_SUCCESS = 0
SW_SUPPRESS_FEATURE = 0
SW_UNSUPPRESS_FEATURE = 1
SW_ALL_CONFIGURATIONS = 2


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def memory_gate() -> List[float]:
    """Require ten consecutive pre-write samples at or above 6 GiB."""
    import psutil

    samples: List[float] = []
    for _ in range(10):
        samples.append(round(float(psutil.virtual_memory().available) / (1024.0 ** 3), 6))
        time.sleep(0.25)
    if not mo.override_allowed() and min(samples) < 6.0:
        raise GateError("AVAILABLE_RAM_HOLD", "Loop-1B native write requires ten consecutive samples >= 6 GiB", {"samples_gib": samples, "minimum_gib": min(samples)})
    return samples


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def accepted_checkpoint_script_hash(digest: Any) -> bool:
    return isinstance(digest, str) and digest in {
        sha256(Path(__file__)),
        CHECKPOINT_SCRIPT_PREDECESSOR_SHA256,
    }


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise GateError("JSON_ROOT_FAIL", "JSON root must be an object", {"path": norm(path)})
    return value


def write_json_once(path: Path, payload: Dict[str, Any]) -> None:
    if RUN_ROOT.resolve() not in path.resolve().parents:
        raise GateError("WRITE_SCOPE_FAIL", "write target is outside unique V5 root", {"path": str(path)})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_text_once(path: Path, text: str) -> None:
    if RUN_ROOT.resolve() not in path.resolve().parents:
        raise GateError("WRITE_SCOPE_FAIL", "write target is outside unique V5 root", {"path": str(path)})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def file_fact(path: Path) -> Dict[str, Any]:
    return {"path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def value(obj: Any, name: str, *args: Any) -> Any:
    member = getattr(obj, name)
    return member(*args) if callable(member) else member


def unpack(result: Any) -> Tuple[Any, List[Any]]:
    return (result[0], list(result[1:])) if isinstance(result, tuple) else (result, [])


def as_list(item: Any) -> List[Any]:
    if item is None:
        return []
    return list(item) if isinstance(item, (tuple, list)) else [item]


def wrap(obj: Any, interface: str, types: Any, pythoncom: Any) -> Any:
    klass = getattr(types, interface)
    ole = obj._oleobj_.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch)
    return klass(ole)


def audit_hash_rows(rows: Iterable[Tuple[Path, str]], code: str) -> List[Dict[str, Any]]:
    out = []
    for path, expected in rows:
        actual = sha256(path) if path.is_file() else None
        row = {"path": norm(path) if path.exists() else str(path).replace("\\", "/"), "exists": path.is_file(), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected}
        out.append(row)
    if not all(row["pass"] for row in out):
        raise GateError(code, "fixed input hash audit failed", {"rows": out})
    return out


def audit_protected() -> List[Dict[str, Any]]:
    rows = []
    for name, path, expected in PROTECTED:
        actual = sha256(path) if path.is_file() else None
        rows.append({"name": name, "path": norm(path) if path.exists() else str(path), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    if not all(row["pass"] for row in rows):
        raise GateError("PROTECTED_HASH_DRIFT", "protected PRE/POST audit failed", {"rows": rows})
    return rows


def registered_baseline() -> Dict[str, Any]:
    receipt = load_json(IMPORT_RECEIPT)
    if receipt.get("schema") != "F3R2_V5_LOOP1_NEUTRAL_IMPORT_RECEIPT_V1" or receipt.get("verdict") != "V5_LOOP1_NEUTRAL_NATIVE_PART_IMPORT_PASS" or receipt.get("native_part_count") != 20:
        raise GateError("LOOP1_RECEIPT_CONTRACT_FAIL", "Loop-1 receipt is not the exact 20-part PASS")
    parts = []
    for item in receipt.get("native_parts", []):
        target = item.get("target", {})
        path = Path(str(target.get("path", ""))).resolve()
        actual = file_fact(path) if path.is_file() else {"path": str(path), "bytes": None, "sha256": None}
        expected = {"path": norm(path), "bytes": target.get("bytes"), "sha256": target.get("sha256")}
        row = {"expected": expected, "actual": actual, "pass": actual == expected}
        parts.append(row)
    if len(parts) != 20 or not all(row["pass"] for row in parts):
        raise GateError("LOOP1_20_PART_DRIFT", "one or more Loop-1 parts drifted", {"parts": parts})
    loop1a = load_json(LOOP1A_RECEIPT)
    if loop1a.get("schema") != "F3R2_V5_LOOP1A_SUBASSEMBLY_RECEIPT_V2" or loop1a.get("verdict") != "V5_LOOP1A_ADAPTER_SUPPORT_SUBASSEMBLIES_PASS" or len(loop1a.get("subassemblies", [])) != 4:
        raise GateError("LOOP1A_RECEIPT_CONTRACT_FAIL", "Loop-1A four-subassembly PASS is absent")
    assemblies = []
    for item in loop1a["subassemblies"]:
        target = item["target"]
        path = Path(str(target["path"])).resolve()
        expected = {"path": norm(path), "bytes": target["bytes"], "sha256": target["sha256"]}
        actual = file_fact(path) if path.is_file() else {"path": norm(path), "bytes": None, "sha256": None}
        assemblies.append({"expected": expected, "actual": actual, "pass": expected == actual})
    if not all(row["pass"] for row in assemblies):
        raise GateError("LOOP1A_ASSEMBLY_DRIFT", "Loop-1A subassembly drift detected", {"assemblies": assemblies})
    return {
        "parts": parts,
        "assemblies": assemblies,
        "session_b_pid": int(sbin.resolve_pid(receipt["solidworks"]["pid"])),
    }


def audit_authority() -> Dict[str, Any]:
    authority = load_json(ANGLE_AUTHORITY)
    if authority.get("schema") != "F3R1_G2_CONFIG_ANGLE_AUTHORITY_V1":
        raise GateError("ANGLE_AUTHORITY_SCHEMA_FAIL", "unexpected angle authority schema")
    text = ANGLE_AUTHORITY.read_text(encoding="utf-8")
    if '"solar_left_deg": 45' in text or '"solar_right_deg": 45' in text:
        raise GateError("UNAUTHORISED_INTERMEDIATE_ANGLE", "angle authority unexpectedly contains a 45-degree wing state")
    return {
        "path": norm(ANGLE_AUTHORITY),
        "sha256": sha256(ANGLE_AUTHORITY),
        "states": CONFIG_ANGLES,
        "deploying_contract": "NO_FIXED_ANGLE_TRUE_1R",
        "diagnostic_samples_define_partial": False,
    }


def donor_source_audit() -> List[Dict[str, Any]]:
    rows = []
    for item in DONORS.values():
        source = Path(item["source"])
        row = {"key": item["key"], "path": norm(source) if source.exists() else str(source), "expected_bytes": item["bytes"], "actual_bytes": source.stat().st_size if source.is_file() else None, "expected_sha256": item["sha256"], "actual_sha256": sha256(source) if source.is_file() else None}
        row["pass"] = row["actual_bytes"] == row["expected_bytes"] and row["actual_sha256"] == row["expected_sha256"]
        rows.append(row)
    if not all(row["pass"] for row in rows):
        raise GateError("DONOR_SOURCE_DRIFT", "panel or V2.2 wing-root donor drifted", {"rows": rows})
    return rows


def artifact_checkpoint(key: str) -> Path:
    return VALIDATION / f"V5_LOOP1B_ARTIFACT_{key}.json"


def pair_state(key: str, target: Path) -> Dict[str, Any]:
    checkpoint = artifact_checkpoint(key)
    if not target.exists() and not checkpoint.exists():
        return {"key": key, "target": norm(target.parent) + "/" + target.name, "checkpoint": norm(checkpoint.parent) + "/" + checkpoint.name, "status": "PENDING", "pass": True}
    if target.is_file() and checkpoint.is_file():
        payload = load_json(checkpoint)
        valid = (
            payload.get("schema") == "F3R2_V5_LOOP1B_ARTIFACT_CHECKPOINT_V1"
            and payload.get("key") == key
            and accepted_checkpoint_script_hash(payload.get("script_sha256"))
            and payload.get("g0_sha256") == FIXED_INPUTS[0][1]
            and payload.get("loop1_sha256") == FIXED_INPUTS[1][1]
            and payload.get("loop1a_sha256") == FIXED_INPUTS[2][1]
            and payload.get("target") == file_fact(target)
            and payload.get("verdict") == "V5_LOOP1B_ARTIFACT_CHECKPOINT_PASS"
        )
        return {"key": key, "target": norm(target), "checkpoint": norm(checkpoint), "status": "VERIFIED_RESUME" if valid else "CHECKPOINT_DRIFT", "pass": valid}
    return {"key": key, "target": str(target), "checkpoint": str(checkpoint), "status": "UNPAIRED_PARTIAL_ARTIFACT_HOLD", "pass": False}


def static_audit() -> Dict[str, Any]:
    roots = sorted(path.resolve() for path in ENGINEERING.glob("F3R2_V5_NATIVE_MECHANICAL_RELEASE_*") if path.is_dir())
    if roots != [RUN_ROOT.resolve()]:
        raise GateError("V5_UNIQUENESS_FAIL", "exactly one fixed V5 root is required", {"roots": [norm(path) for path in roots]})
    fixed = audit_hash_rows((*FIXED_INPUTS, *TEMPLATES), "FIXED_INPUT_HASH_FAIL")
    baseline = registered_baseline()
    protected = audit_protected()
    donors = donor_source_audit()
    authority = audit_authority()
    states = [pair_state(key, Path(item["target"])) for key, item in DONORS.items()]
    for side, spec in SIDES.items():
        states.append(pair_state(f"{side}_LUG", spec["lug"]))
        states.append(pair_state(f"{side}_RETAINER", spec["retainer"]))
        states.append(pair_state(f"{side}_ASSEMBLY", spec["assembly"]))
    packaging_clear = not FINAL_RECEIPT.exists() and not FINAL_MANIFEST.exists() and (not SCRIPT_COPY.exists() or sha256(SCRIPT_COPY) == sha256(Path(__file__)))
    return {
        "schema": "F3R2_V5_LOOP1B_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "run_root": norm(RUN_ROOT),
        "fixed_inputs": fixed,
        "baseline": baseline,
        "protected": protected,
        "donors": donors,
        "authority": authority,
        "artifacts": states,
        "stage_1b0_checkpoint_exists": STAGE_1B0.exists(),
        "stage_1b1_checkpoint_exists": STAGE_1B1.exists(),
        "packaging_clear": packaging_clear,
        "execution_authorized": all(row["pass"] for row in states) and packaging_clear,
        "verdict": "V5_LOOP1B_STATIC_PASS_OR_VERIFIED_RESUME" if all(row["pass"] for row in states) and packaging_clear else "V5_LOOP1B_STATIC_HOLD_OR_COMPLETE",
    }


def attach_empty_session(expected_pid: int) -> Tuple[Any, Any, Any, Dict[str, Any]]:
    import psutil
    import pythoncom
    import win32com.client
    from win32com.client import gencache

    pythoncom.CoInitialize()
    types = gencache.GetModuleForTypelib(*SW_TLB)
    raw = win32com.client.GetActiveObject(SW_PROG_ID)
    sw = wrap(raw, "ISldWorks", types, pythoncom)
    revision = str(value(sw, "RevisionNumber"))
    pid = int(value(sw, "GetProcessID"))
    executable = Path(psutil.Process(pid).exe()).resolve()
    if not revision.startswith("32.5.") or pid != expected_pid or os.path.normcase(str(executable)) != os.path.normcase(str(SW_EXE.resolve())):
        raise GateError("SESSION_B_IDENTITY_FAIL", "attached application is not the fixed qualified Session B", {"revision": revision, "pid": pid, "expected_pid": expected_pid, "executable": str(executable)})
    count = int(value(sw, "GetDocumentCount"))
    if count != 0 or value(sw, "ActiveDoc") is not None:
        raise GateError("SESSION_B_NOT_EMPTY", "Session B must be document-empty", {"document_count": count})
    return sw, types, pythoncom, {"attach_only": True, "revision": revision, "pid": pid, "executable": norm(executable), "document_count": count}


def unpack_document(result: Any, label: str) -> Tuple[Any, int, int]:
    if not isinstance(result, tuple) or len(result) < 3:
        raise GateError(f"{label}_RETURN_SHAPE_FAIL", "typed open did not return model/errors/warnings", {"returned": repr(result)})
    model, outs = unpack(result)
    return model, int(outs[0]), int(outs[1])


def open_doc(sw: Any, path: Path, doc_type: int, read_only: bool, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    raw, errors, warnings = unpack_document(sw.OpenDoc6(str(path), doc_type, SW_OPEN_SILENT | (SW_OPEN_READ_ONLY if read_only else 0), "", 0, 0), "OPEN_DOC")
    if raw is None or errors != 0 or warnings != 0:
        raise GateError("OPEN_DOC_FAIL", "document open failed", {"path": norm(path), "errors": errors, "warnings": warnings})
    model = wrap(raw, "IModelDoc2", types, pythoncom)
    if bool(value(model, "IsOpenedReadOnly")) != read_only:
        raise GateError("OPEN_MODE_FAIL", "document read-only state mismatch", {"path": norm(path), "expected_read_only": read_only})
    return model, {"errors": errors, "warnings": warnings, "read_only": read_only}


def close_doc(sw: Any, model: Any) -> None:
    if model is not None:
        sw.CloseDoc(str(value(model, "GetTitle")))


def close_owned_documents(sw: Any) -> None:
    if sw is None:
        return
    for _ in range(200):
        docs = as_list(value(sw, "GetDocuments"))
        if not docs:
            return
        progress = False
        for raw in docs:
            try:
                sw.CloseDoc(str(value(raw, "GetTitle")))
                progress = True
            except Exception:
                pass
        if not progress:
            break


def external_reference_count(model: Any) -> int:
    failures = []
    for name, args in (("ListExternalFileReferencesCount2", ()), ("ListExternalFileReferencesCount", (False,))):
        try:
            return int(value(model, name, *args))
        except Exception as exc:
            failures.append({"api": name, "exception": repr(exc)})
    raise GateError("EXTERNAL_REFERENCE_QUERY_FAIL", "cannot prove external reference count", {"failures": failures})


def auxiliary_reference_count(model: Any) -> int:
    try:
        return int(value(model, "ListAuxiliaryExternalFileReferencesCount"))
    except Exception as exc:
        raise GateError("AUXILIARY_REFERENCE_QUERY_FAIL", "cannot prove auxiliary external reference count", {"exception": repr(exc)}) from exc


def interconnect_features(model: Any, types: Any, pythoncom: Any) -> List[str]:
    found = []
    feature = value(model, "FirstFeature")
    for _ in range(10000):
        if feature is None:
            return found
        typed = wrap(feature, "IFeature", types, pythoncom)
        if bool(value(typed, "Is3DInterconnectFeature")):
            found.append(str(value(typed, "Name")))
        feature = value(typed, "GetNextFeature")
    raise GateError("FEATURE_TRAVERSAL_LIMIT", "feature traversal exceeded guard")


def body_facts(model: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    part = wrap(model, "IPartDoc", types, pythoncom)
    bodies = [wrap(raw, "IBody2", types, pythoncom) for raw in as_list(part.GetBodies2(0, False))]
    boxes = [[float(number) * 1000.0 for number in as_list(value(body, "GetBodyBox"))] for body in bodies]
    overall = [min(box[i] for box in boxes) for i in range(3)] + [max(box[i] for box in boxes) for i in range(3, 6)] if boxes else None
    return {"solid_body_count": len(bodies), "bounding_box_mm": overall}


def bbox_close(actual: Sequence[float], expected: Sequence[float], tolerance_mm: float = 0.12) -> bool:
    return len(actual) == len(expected) == 6 and max(abs(float(a) - float(b)) for a, b in zip(actual, expected)) <= tolerance_mm


def set_properties(model: Any, values: Dict[str, str]) -> None:
    manager = model.Extension.CustomPropertyManager("")
    for name, property_value in values.items():
        if int(manager.Add3(name, 30, str(property_value), 2)) < 0:
            raise GateError("PROPERTY_WRITE_FAIL", "custom property write failed", {"name": name})


def save3(model: Any) -> Dict[str, int]:
    returned = model.Save3(1, 0, 0)
    ok, outs = unpack(returned)
    errors = int(outs[0]) if outs else -1
    warnings = int(outs[1]) if len(outs) > 1 else -1
    if not bool(ok) or errors != 0 or warnings != 0:
        raise GateError("SAVE3_FAIL", "native document final save failed", {"ok": bool(ok), "errors": errors, "warnings": warnings})
    return {"errors": errors, "warnings": warnings}


def save_as(model: Any, target: Path) -> Dict[str, Any]:
    if target.exists():
        raise GateError("WRITE_ONCE_TARGET_EXISTS", "native target already exists", {"path": norm(target)})
    target.parent.mkdir(parents=True, exist_ok=True)
    returned = model.Extension.SaveAs(str(target), 0, 1, None, 0, 0)
    ok, outs = unpack(returned)
    errors = int(outs[0]) if outs else -1
    warnings = int(outs[1]) if len(outs) > 1 else -1
    if not bool(ok) or errors != 0 or warnings != 0 or not target.is_file():
        raise GateError("SAVE_AS_FAIL", "native SaveAs failed", {"target": norm(target), "ok": bool(ok), "errors": errors, "warnings": warnings})
    final = save3(model)
    return {**file_fact(target), "save_as_errors": errors, "save_as_warnings": warnings, "save3": final}


def checkpoint_artifact(key: str, target: Path, result: Dict[str, Any]) -> Dict[str, Any]:
    checkpoint = artifact_checkpoint(key)
    payload = {"schema": "F3R2_V5_LOOP1B_ARTIFACT_CHECKPOINT_V1", "timestamp_utc": utc_now(), "key": key, "script_sha256": sha256(Path(__file__)), "g0_sha256": FIXED_INPUTS[0][1], "loop1_sha256": FIXED_INPUTS[1][1], "loop1a_sha256": FIXED_INPUTS[2][1], "target": file_fact(target), "result": result, "verdict": "V5_LOOP1B_ARTIFACT_CHECKPOINT_PASS"}
    write_json_once(checkpoint, payload)
    return file_fact(checkpoint)


def load_artifact_result(key: str, target: Path) -> Dict[str, Any]:
    state = pair_state(key, target)
    if not state["pass"] or state["status"] != "VERIFIED_RESUME":
        raise GateError("ARTIFACT_RESUME_FAIL", "target/checkpoint pair is not resumable", {"state": state})
    return load_json(artifact_checkpoint(key))["result"]


def isolate_donor(sw: Any, types: Any, pythoncom: Any, item: Dict[str, Any]) -> Dict[str, Any]:
    key = item["key"]
    source = Path(item["source"])
    target = Path(item["target"])
    if target.exists():
        result = load_artifact_result(key, target)
        result = {**result, "resumed_from_checkpoint": True}
        return result
    source_pre = file_fact(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if not target.is_file() or target.stat().st_size != source.stat().st_size:
        raise GateError("INDEPENDENT_NATIVE_CLONE_FAIL", "independent native clone failed", {"key": key})
    model = None
    try:
        model, opened = open_doc(sw, target, SW_PART, False, types, pythoncom)
        before = {"external": external_reference_count(model), "auxiliary": auxiliary_reference_count(model), "interconnect": interconnect_features(model, types, pythoncom)}
        model.Extension.BreakAllExternalFileReferences2(True)
        after = {"external": external_reference_count(model), "auxiliary": auxiliary_reference_count(model), "interconnect": interconnect_features(model, types, pythoncom)}
        if after != {"external": 0, "auxiliary": 0, "interconnect": []}:
            raise GateError("DONOR_ZERO_LINK_FAIL", "isolated donor retains an external link", {"key": key, "after": after})
        set_properties(model, {"PartNumber": f"SEI-V5-{key}", "Revision": "V5-A", "SOURCE_SHA256": item["sha256"], "IMPORT_MODE": "INDEPENDENT_NATIVE_CLONE_BREAK_ALL_LINKS", "RUN_ID": RUN_ID, "FLIGHT_QUALIFICATION": "HOLD"})
        if not bool(model.ForceRebuild3(True)):
            raise GateError("DONOR_REBUILD_FAIL", "isolated donor rebuild failed", {"key": key})
        saved = save3(model)
    finally:
        close_doc(sw, model)
    cold = None
    try:
        cold, cold_open = open_doc(sw, target, SW_PART, True, types, pythoncom)
        facts = body_facts(cold, types, pythoncom)
        cold_links = {"external": external_reference_count(cold), "auxiliary": auxiliary_reference_count(cold), "interconnect": interconnect_features(cold, types, pythoncom)}
        if facts["solid_body_count"] < 1 or not bbox_close(facts["bounding_box_mm"], item["bbox_mm"]) or cold_links != {"external": 0, "auxiliary": 0, "interconnect": []}:
            raise GateError("DONOR_COLD_VERIFY_FAIL", "isolated donor cold verification failed", {"key": key, "facts": facts, "links": cold_links, "expected_bbox_mm": item["bbox_mm"]})
    finally:
        close_doc(sw, cold)
    source_post = file_fact(source)
    if source_pre != source_post:
        raise GateError("DONOR_SOURCE_POST_DRIFT", "source donor changed during independent import", {"key": key, "pre": source_pre, "post": source_post})
    result = {"key": key, "source_pre": source_pre, "source_post": source_post, "target": file_fact(target), "open": opened, "links_before_break": before, "links_after_break": after, "save": saved, "cold_open": cold_open, "cold_facts": facts, "cold_links": cold_links, "verdict": "V5_LOOP1B0_INDEPENDENT_NATIVE_ZERO_LINK_PASS"}
    result["checkpoint"] = checkpoint_artifact(key, target, result)
    return result


def select_base_plane(model: Any, candidates: Sequence[str]) -> str:
    model.ClearSelection2(True)
    for name in candidates:
        if bool(model.Extension.SelectByID2(name, "PLANE", 0.0, 0.0, 0.0, False, 0, None, 0)):
            return name
    raise GateError("BASE_PLANE_SELECTION_FAIL", "cannot select native base plane", {"candidates": list(candidates)})


def create_offset_plane(model: Any, candidates: Sequence[str], offset_mm: float, name: str) -> None:
    select_base_plane(model, candidates)
    flag = 8 | (256 if offset_mm < 0 else 0)
    feature = model.FeatureManager.InsertRefPlane(flag, abs(offset_mm) / 1000.0, 0, 0, 0, 0)
    if feature is None:
        raise GateError("OFFSET_PLANE_FAIL", "InsertRefPlane returned null", {"name": name, "offset_mm": offset_mm})
    feature.Name = name
    model.ClearSelection2(True)


def new_part(sw: Any, types: Any, pythoncom: Any) -> Any:
    raw = sw.NewDocument(str(PART_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = value(sw, "ActiveDoc")
    if raw is None:
        raise GateError("NEW_PART_FAIL", "cannot create native part")
    return wrap(raw, "IModelDoc2", types, pythoncom)


def make_lug(sw: Any, types: Any, pythoncom: Any, side: str) -> Dict[str, Any]:
    spec = SIDES[side]
    key, target = f"{side}_LUG", Path(spec["lug"])
    if target.exists():
        return {**load_artifact_result(key, target), "resumed_from_checkpoint": True}
    model = None
    try:
        model = new_part(sw, types, pythoncom)
        create_offset_plane(model, ("前视基准面", "Front Plane"), -5.0, f"PLN_{side}_LUG_ZMIN")
        if not bool(model.Extension.SelectByID2(f"PLN_{side}_LUG_ZMIN", "PLANE", 0, 0, 0, False, 0, None, 0)):
            raise GateError("LUG_SKETCH_PLANE_FAIL", "cannot select lug sketch plane")
        sign = 1.0 if side == "L" else -1.0
        y0, y1, y2 = sign * 105.15, sign * 113.15, sign * 151.15
        points = [(-75.0, y0), (-47.0, y0), (-47.0, y2), (-57.0, y2), (-57.0, y1), (-65.0, y1), (-65.0, y2), (-75.0, y2), (-75.0, y0)]
        sketch = model.SketchManager
        sketch.InsertSketch(True)
        for (x1, yy1), (x2, yy2) in zip(points[:-1], points[1:]):
            if sketch.CreateLine(x1 / 1000.0, yy1 / 1000.0, 0.0, x2 / 1000.0, yy2 / 1000.0, 0.0) is None:
                raise GateError("LUG_PROFILE_FAIL", "lug U-profile line creation failed")
        sketch.InsertSketch(True)
        extrusion = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, 0.010, 0.0, False, False, False, False, 0.0, 0.0, False, False, False, False, True, True, True, 0, 0.0, False)
        if extrusion is None:
            raise GateError("LUG_EXTRUSION_FAIL", "lug extrusion returned null")
        create_offset_plane(model, ("右视基准面", "Right Plane"), -42.0, f"PLN_{side}_LUG_BORE")
        if not bool(model.Extension.SelectByID2(f"PLN_{side}_LUG_BORE", "PLANE", 0, 0, 0, False, 0, None, 0)):
            raise GateError("LUG_BORE_PLANE_FAIL", "cannot select lug bore plane")
        sketch.InsertSketch(True)
        sketch.CreateCircleByRadius(0.0, float(spec["axis_y_mm"]) / 1000.0, 0.0, 0.0042)
        sketch.InsertSketch(True)
        cut = model.FeatureManager.FeatureCut3(True, False, False, 0, 0, 0.040, 0.0, False, False, False, False, 0.0, 0.0, False, False, False, False, False, True, True, True, True, False, 0, 0.0, False)
        if cut is None:
            raise GateError("LUG_BORE_CUT_FAIL", "lug through-bore cut returned null")
        set_properties(model, {"PartNumber": f"SEI-MECH-WR-{side}-U-LUG", "Description": "native dual-ear panel-side hinge lug", "MaterialSpecification": "AL7075-T6_CANDIDATE", "HINGE_AXIS": f"X@Y={spec['axis_y_mm']}mm,Z=0", "BORE_DIAMETER_MM": "8.4", "RUN_ID": RUN_ID, "FLIGHT_QUALIFICATION": "HOLD"})
        saved = save_as(model, target)
    finally:
        close_doc(sw, model)
    cold = None
    try:
        cold, opened = open_doc(sw, target, SW_PART, True, types, pythoncom)
        facts = body_facts(cold, types, pythoncom)
        expected = [-75.0, 105.15, -5.0, -47.0, 151.15, 5.0] if side == "L" else [-75.0, -151.15, -5.0, -47.0, -105.15, 5.0]
        if facts["solid_body_count"] != 1 or not bbox_close(facts["bounding_box_mm"], expected):
            raise GateError("LUG_COLD_GEOMETRY_FAIL", "native lug cold geometry mismatch", {"facts": facts, "expected_bbox_mm": expected})
    finally:
        close_doc(sw, cold)
    result = {"key": key, "target": saved, "cold_open": opened, "cold_facts": facts, "geometry_contract": {"axis": "X", "axis_y_mm": spec["axis_y_mm"], "axis_z_mm": 0.0, "bore_diameter_mm": 8.4, "ear_x_spans_mm": [[-75.0, -65.0], [-57.0, -47.0]], "clevis_gaps_mm": [[-75.5, -64.5], [-57.5, -46.5]], "side_clearance_mm": 0.5}, "verdict": "V5_LOOP1B1_NATIVE_PANEL_LUG_PASS"}
    result["checkpoint"] = checkpoint_artifact(key, target, result)
    return result


def make_retainer(sw: Any, types: Any, pythoncom: Any, side: str) -> Dict[str, Any]:
    spec = SIDES[side]
    key, target = f"{side}_RETAINER", Path(spec["retainer"])
    if target.exists():
        return {**load_artifact_result(key, target), "resumed_from_checkpoint": True}
    model = None
    try:
        model = new_part(sw, types, pythoncom)
        create_offset_plane(model, ("右视基准面", "Right Plane"), -84.0, f"PLN_{side}_RETAINER_XMIN")
        if not bool(model.Extension.SelectByID2(f"PLN_{side}_RETAINER_XMIN", "PLANE", 0, 0, 0, False, 0, None, 0)):
            raise GateError("RETAINER_PLANE_FAIL", "cannot select retainer plane")
        sketch = model.SketchManager
        sketch.InsertSketch(True)
        yc = float(spec["axis_y_mm"]) / 1000.0
        sketch.CreateCircleByRadius(0.0, yc, 0.0, 0.0070)
        sketch.CreateCircleByRadius(0.0, yc, 0.0, 0.0041)
        sketch.InsertSketch(True)
        extrusion = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, 0.002, 0.0, False, False, False, False, 0.0, 0.0, False, False, False, False, True, True, True, 0, 0.0, False)
        if extrusion is None:
            raise GateError("RETAINER_EXTRUSION_FAIL", "retainer extrusion returned null")
        set_properties(model, {"PartNumber": f"SEI-MECH-WR-{side}-RET", "Description": "native hinge axial retainer collar", "MaterialSpecification": "17-4PH_H900_CANDIDATE", "OD_MM": "14.0", "ID_MM": "8.2", "THICKNESS_MM": "2.0", "RUN_ID": RUN_ID, "FLIGHT_QUALIFICATION": "HOLD"})
        saved = save_as(model, target)
    finally:
        close_doc(sw, model)
    cold = None
    try:
        cold, opened = open_doc(sw, target, SW_PART, True, types, pythoncom)
        facts = body_facts(cold, types, pythoncom)
        ay = float(spec["axis_y_mm"])
        expected = [-84.0, ay - 7.0, -7.0, -82.0, ay + 7.0, 7.0]
        if facts["solid_body_count"] != 1 or not bbox_close(facts["bounding_box_mm"], expected):
            raise GateError("RETAINER_COLD_GEOMETRY_FAIL", "native retainer cold geometry mismatch", {"facts": facts, "expected_bbox_mm": expected})
    finally:
        close_doc(sw, cold)
    result = {"key": key, "target": saved, "cold_open": opened, "cold_facts": facts, "geometry_contract": {"axis": "X", "axis_y_mm": spec["axis_y_mm"], "id_mm": 8.2, "od_mm": 14.0, "x_span_mm": [-84.0, -82.0]}, "verdict": "V5_LOOP1B1_NATIVE_AXIAL_RETAINER_PASS"}
    result["checkpoint"] = checkpoint_artifact(key, target, result)
    return result


def transform_data(translation: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> List[float]:
    return [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, *translation, 1.0, 0.0, 0.0, 0.0]


def rotation_x_about_y_data(angle: float, axis_y_m: float) -> List[float]:
    c, s = math.cos(angle), math.sin(angle)
    return [1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c, 0.0, axis_y_m * (1.0 - c), -axis_y_m * s, 1.0, 0.0, 0.0, 0.0]


def make_transform(sw: Any, data: Sequence[float], types: Any, pythoncom: Any) -> Any:
    from win32com.client import VARIANT

    utility = wrap(value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
    transform = utility.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, list(data)))
    if transform is None:
        raise GateError("CREATE_TRANSFORM_FAIL", "CreateTransform returned null")
    return transform


def activate(sw: Any, title: str) -> Any:
    returned = sw.ActivateDoc3(title, True, 0, 0)
    model, outs = unpack(returned)
    error = int(outs[0]) if outs else 0
    if model is None or error != 0:
        raise GateError("ACTIVATE_ASSEMBLY_FAIL", "cannot activate owned assembly", {"title": title, "error": error})
    return model


def insert_component(sw: Any, model: Any, assembly: Any, path: Path, fixed: bool, translation: Tuple[float, float, float], types: Any, pythoncom: Any) -> Any:
    part = None
    title = str(value(model, "GetTitle"))
    try:
        part, _opened = open_doc(sw, path, SW_PART, True, types, pythoncom)
        activate(sw, title)
        raw = assembly.AddComponent5(str(path), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw is None:
            raise GateError("ADD_COMPONENT5_FAIL", "AddComponent5 returned null", {"path": norm(path)})
        component = wrap(raw, "IComponent2", types, pythoncom)
        if not bool(component.SetTransformAndSolve3(make_transform(sw, transform_data(translation), types, pythoncom), True)):
            raise GateError("COMPONENT_TRANSFORM_FAIL", "component identity/translation transform failed", {"path": norm(path)})
        model.EditRebuild3()
        model.ClearSelection2(True)
        if not bool(component.Select4(False, None, False)):
            raise GateError("COMPONENT_SELECTION_FAIL", "cannot select inserted component", {"path": norm(path)})
        assembly.FixComponent() if fixed else assembly.UnfixComponent()
        model.ClearSelection2(True)
        if bool(value(component, "IsFixed")) != fixed:
            raise GateError("FIXED_STATE_FAIL", "component fixed-state readback mismatch", {"path": norm(path), "fixed": fixed})
        return component
    finally:
        close_doc(sw, part)
        activate(sw, title)


def component_bodies(component: Any, types: Any, pythoncom: Any) -> List[Any]:
    for name, args in (("GetBodies2", (0,)), ("GetBodies2", (1,)), ("GetBody", ())):
        try:
            bodies = as_list(value(component, name, *args))
        except Exception:
            continue
        if bodies:
            return [wrap(body, "IBody2", types, pythoncom) for body in bodies]
    raise GateError("COMPONENT_BODY_FAIL", "component exposes no body", {"component": str(value(component, "Name2"))})


def cylinder_entity(component: Any, radius_mm: float, axis_y_mm: float, expected_count: int, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    candidates = []
    for body in component_bodies(component, types, pythoncom):
        for raw_face in as_list(value(body, "GetFaces")):
            face = wrap(raw_face, "IFace2", types, pythoncom)
            surface = wrap(value(face, "GetSurface"), "ISurface", types, pythoncom)
            if not bool(surface.IsCylinder()):
                continue
            params = [float(v) for v in as_list(value(surface, "CylinderParams"))]
            if len(params) >= 7 and abs(abs(params[3]) - 1.0) < 1e-5 and abs(params[1] * 1000.0 - axis_y_mm) <= 0.06 and abs(params[2] * 1000.0) <= 0.06 and abs(params[6] * 1000.0 - radius_mm) <= 0.06:
                candidates.append((params[0], float(value(face, "GetArea")), face, params))
    if len(candidates) != expected_count:
        raise GateError("CYLINDER_SIGNATURE_FAIL", "cylindrical face count mismatch", {"component": str(value(component, "Name2")), "radius_mm": radius_mm, "axis_y_mm": axis_y_mm, "expected_count": expected_count, "actual_count": len(candidates)})
    candidates.sort(key=lambda row: (row[0], -row[1]))
    chosen = candidates[0]
    return wrap(chosen[2], "IEntity", types, pythoncom), {"radius_mm": radius_mm, "axis_y_mm": axis_y_mm, "candidate_count": len(candidates), "cylinder_params": chosen[3], "area_mm2": chosen[1] * 1e6}


def plane_entity_x(component: Any, x_mm: float, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    candidates = []
    for body in component_bodies(component, types, pythoncom):
        for raw_face in as_list(value(body, "GetFaces")):
            face = wrap(raw_face, "IFace2", types, pythoncom)
            surface = wrap(value(face, "GetSurface"), "ISurface", types, pythoncom)
            if not bool(surface.IsPlane()):
                continue
            params = [float(v) for v in as_list(value(surface, "PlaneParams"))]
            if len(params) >= 6 and abs(abs(params[0]) - 1.0) < 1e-5 and abs(params[3] * 1000.0 - x_mm) <= 0.06:
                candidates.append((float(value(face, "GetArea")), face, params))
    if len(candidates) != 1:
        raise GateError("X_PLANE_SIGNATURE_FAIL", "expected one exact X-plane face", {"component": str(value(component, "Name2")), "x_mm": x_mm, "candidate_count": len(candidates), "areas_mm2": [row[0] * 1e6 for row in candidates]})
    area, face, params = candidates[0]
    return wrap(face, "IEntity", types, pythoncom), {"x_mm": x_mm, "plane_params": params, "area_mm2": area * 1e6, "candidate_count": 1}


def spacer_axial_plane_entity(component: Any, axis_y_mm: float, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    expected_path = V5_PART["SPACER"].resolve()
    actual_path = Path(str(value(component, "GetPathName"))).resolve()
    if actual_path != expected_path:
        raise GateError("SPACER_COMPONENT_PATH_FAIL", "axial spacer occurrence references the wrong native part", {"expected": norm(expected_path), "actual": norm(actual_path)})

    raw_transform = value(component, "Transform2")
    if raw_transform is None:
        raise GateError("SPACER_TRANSFORM_NULL", "axial spacer occurrence has no Transform2")
    transform = [float(number) for number in as_list(value(raw_transform, "ArrayData"))]
    expected_transform = transform_data((-0.0755, float(axis_y_mm) / 1000.0, 0.0))
    if len(transform) != 16 or max((abs(actual - expected) for actual, expected in zip(transform, expected_transform)), default=float("inf")) > 1e-9:
        raise GateError(
            "SPACER_TRANSFORM_CONTRACT_FAIL",
            "axial spacer must retain the exact identity rotation plus registered translation",
            {"expected_transform16": expected_transform, "actual_transform16": transform, "axis_y_mm": axis_y_mm},
        )

    x_planes: List[Dict[str, Any]] = []
    for body in component_bodies(component, types, pythoncom):
        for raw_face in as_list(value(body, "GetFaces")):
            face = wrap(raw_face, "IFace2", types, pythoncom)
            surface = wrap(value(face, "GetSurface"), "ISurface", types, pythoncom)
            if not bool(surface.IsPlane()):
                continue
            params = [float(number) for number in as_list(value(surface, "PlaneParams"))]
            if len(params) < 6 or abs(abs(params[0]) - 1.0) >= 1e-8 or abs(params[1]) >= 1e-8 or abs(params[2]) >= 1e-8:
                continue
            bbox = [float(number) * 1000.0 for number in as_list(value(face, "GetBox"))]
            if len(bbox) != 6:
                raise GateError("SPACER_FACE_BBOX_SHAPE_FAIL", "spacer axial face GetBox is not six-valued", {"bbox_mm": bbox})
            local_x_mm = params[3] * 1000.0
            area_mm2 = float(value(face, "GetArea")) * 1e6
            fact = {
                "local_x_mm": local_x_mm,
                "area_mm2": area_mm2,
                "normal_local": params[:3],
                "plane_params_local_m": params,
                "face_bbox_local_mm": bbox,
            }
            if abs(bbox[0] - local_x_mm) > 1e-5 or abs(bbox[3] - local_x_mm) > 1e-5:
                raise GateError("SPACER_FACE_BBOX_X_FAIL", "spacer axial planar face bbox does not collapse at its local X plane", fact)
            x_planes.append({"face": face, "params": params, "fact": fact})

    x_planes.sort(key=lambda row: row["fact"]["local_x_mm"])
    expected_local_signature = ((0.0, 196.3809568), (0.5, 196.3809568))
    actual_local_signature = [(row["fact"]["local_x_mm"], row["fact"]["area_mm2"]) for row in x_planes]
    signature_ok = len(actual_local_signature) == len(expected_local_signature) and all(
        abs(actual_x - expected_x) <= 1e-5 and abs(actual_area - expected_area) <= 1e-4
        for (actual_x, actual_area), (expected_x, expected_area) in zip(actual_local_signature, expected_local_signature)
    )
    if not signature_ok:
        raise GateError(
            "SPACER_LOCAL_BREP_SIGNATURE_FAIL",
            "axial spacer must expose exactly the two proven local X faces; no largest-face fallback is allowed",
            {"expected_local_signature": expected_local_signature, "actual_x_planes": [row["fact"] for row in x_planes]},
        )
    selected = [row for row in x_planes if abs(row["fact"]["local_x_mm"] - 0.5) <= 1e-5]
    if len(selected) != 1:
        raise GateError("SPACER_LOCAL_FACE_CARDINALITY_FAIL", "expected exactly one local X=+0.5 mm spacer bearing face", {"actual_x_planes": [row["fact"] for row in x_planes]})

    chosen = selected[0]
    params = chosen["params"]
    world_x_mm = 1000.0 * (params[3] * transform[0] + params[4] * transform[3] + params[5] * transform[6] + transform[9])
    if abs(world_x_mm - (-75.0)) > 1e-5:
        raise GateError(
            "SPACER_LOCAL_TO_WORLD_X_FAIL",
            "local +0.5 mm spacer bearing face does not map to registered world X=-75.0 mm",
            {"local_x_mm": chosen["fact"]["local_x_mm"], "world_x_mm": world_x_mm, "transform16": transform},
        )
    evidence = {
        "selection_contract": "UNIQUE_LOCAL_X_PLUS_0P5_MM; NO_LARGEST_FACE_FALLBACK",
        "component_path": norm(actual_path),
        "local_brep_x_planes": [row["fact"] for row in x_planes],
        "selected_local_x_mm": chosen["fact"]["local_x_mm"],
        "selected_area_mm2": chosen["fact"]["area_mm2"],
        "component_transform16": transform,
        "transform_contract": {"rotation": "IDENTITY", "translation_mm": [transform[9] * 1000.0, transform[10] * 1000.0, transform[11] * 1000.0], "scale": transform[12]},
        "mapped_world_x_mm": world_x_mm,
        "expected_world_x_mm": -75.0,
        "mapping_equation": "world_x = R00*local_x + R10*local_y + R20*local_z + Tx",
        "candidate_count_at_local_x_plus_0p5": 1,
    }
    return wrap(chosen["face"], "IEntity", types, pythoncom), evidence


def selection_manager(model: Any, types: Any, pythoncom: Any) -> Any:
    for name in ("ISelectionManager", "SelectionManager"):
        try:
            raw = getattr(model, name)
            if raw is not None:
                return wrap(raw, "ISelectionMgr", types, pythoncom)
        except Exception:
            pass
    raise GateError("SELECTION_MANAGER_FAIL", "cannot obtain selection manager")


def feature_error_state(feature: Any) -> Dict[str, Any]:
    legacy_code = int(value(feature, "GetErrorCode"))
    returned = value(feature, "GetErrorCode2", False)
    code2, outs = unpack(returned)
    if len(outs) != 1:
        raise GateError(
            "FEATURE_ERROR_CODE2_SHAPE_FAIL",
            "SW2024 IFeature.GetErrorCode2 did not return code plus IsWarning",
            {"returned": repr(returned)},
        )
    code2 = int(code2)
    is_warning = bool(outs[0])
    if code2 != legacy_code:
        raise GateError(
            "FEATURE_ERROR_CODE_DISAGREEMENT",
            "IFeature.GetErrorCode and GetErrorCode2 disagree",
            {"get_error_code": legacy_code, "get_error_code2": code2, "is_warning": is_warning},
        )
    return {
        "feature_error_code": legacy_code,
        "feature_error_code2": code2,
        "feature_is_warning": is_warning,
        "suppressed": bool(value(feature, "IsSuppressed")),
    }


def mate_object_fact(mate: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    count = int(value(mate, "GetMateEntityCount"))
    paths: List[str] = []
    reference_types: List[int] = []
    for index in range(count):
        raw_entity = mate.MateEntity(index)
        if raw_entity is None:
            raise GateError("MATE_ENTITY_NULL", "IMate2.MateEntity returned null", {"index": index, "count": count})
        entity = wrap(raw_entity, "IMateEntity2", types, pythoncom)
        raw_component = value(entity, "ReferenceComponent")
        if raw_component is None:
            raise GateError("MATE_ENDPOINT_COMPONENT_NULL", "mate entity has no ReferenceComponent", {"index": index, "count": count})
        component = wrap(raw_component, "IComponent2", types, pythoncom)
        path = Path(str(value(component, "GetPathName"))).resolve()
        if not path.is_file():
            raise GateError("MATE_ENDPOINT_PATH_FAIL", "mate endpoint component path is not a file", {"index": index, "path": str(path)})
        paths.append(norm(path))
        reference_types.append(int(value(entity, "ReferenceType2")))
    return {
        "mate_type": int(value(mate, "Type")),
        "alignment": int(value(mate, "Alignment")),
        "entity_count": count,
        "component_paths": sorted(paths),
        "reference_types": sorted(reference_types),
    }


def mate_ledger(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    feature = value(model, "FirstFeature")
    for _ in range(10000):
        if feature is None:
            names = [row["feature_name"] for row in rows]
            if len(names) != len(set(names)):
                raise GateError("MATE_FEATURE_NAME_COLLISION", "MateGroup contains duplicate mate feature names", {"names": names})
            return rows
        typed = wrap(feature, "IFeature", types, pythoncom)
        if str(value(typed, "GetTypeName2")) == "MateGroup":
            sub = value(typed, "GetFirstSubFeature")
            for _sub_index in range(10000):
                if sub is None:
                    break
                sf = wrap(sub, "IFeature", types, pythoncom)
                raw_mate = value(sf, "GetSpecificFeature2")
                if raw_mate is None:
                    raise GateError("MATE_SPECIFIC_FEATURE_NULL", "MateGroup subfeature has no IMate2", {"feature_name": str(value(sf, "Name"))})
                mate = wrap(raw_mate, "IMate2", types, pythoncom)
                row = {
                    "feature_name": str(value(sf, "Name")),
                    **feature_error_state(sf),
                    **mate_object_fact(mate, types, pythoncom),
                }
                if row["feature_error_code"] != 0 or row["feature_error_code2"] != 0 or row["feature_is_warning"] or row["suppressed"] or row["entity_count"] != 2:
                    raise GateError("MATE_LEDGER_FAIL", "mate IFeature is errored, warned, suppressed, or not two-ended", row)
                rows.append(row)
                sub = value(sf, "GetNextSubFeature")
            else:
                raise GateError("MATE_SUBFEATURE_TRAVERSAL_LIMIT", "mate subfeature traversal exceeded guard")
        feature = value(typed, "GetNextFeature")
    raise GateError("MATE_LEDGER_TRAVERSAL_LIMIT", "mate traversal exceeded guard")


def resolve_created_mate(
    model: Any,
    returned: Any,
    before: Sequence[Dict[str, Any]],
    expected_type: int,
    expected_align: int,
    expected_components: Sequence[Any],
    selected_count: int,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    raw_mate, outs = unpack(returned)
    error = int(outs[0]) if len(outs) == 1 else -1
    if raw_mate is None or len(outs) != 1 or error != SW_ADD_MATE_NO_ERROR or selected_count != 2:
        raise GateError(
            "ADD_MATE_RETURN_FAIL",
            "AddMate3 did not return the SW2024 IMate2 plus one successful ErrorStatus",
            {"error": error, "out_count": len(outs), "selected_count": selected_count, "returned_object": raw_mate is not None},
        )
    try:
        returned_mate = wrap(raw_mate, "IMate2", types, pythoncom)
    except Exception as exc:
        raise GateError("ADD_MATE_IMATE2_CAST_FAIL", "AddMate3 return object is not IMate2", {"exception": repr(exc)}) from exc
    returned_fact = mate_object_fact(returned_mate, types, pythoncom)
    after = mate_ledger(model, types, pythoncom)
    before_names = [str(row["feature_name"]) for row in before]
    after_names = [str(row["feature_name"]) for row in after]
    created = [row for row in after if row["feature_name"] not in set(before_names)]
    expected_paths = sorted(norm(component_path(component)) for component in expected_components)
    expected = {
        "mate_type": int(expected_type),
        "entity_count": 2,
        "component_paths": expected_paths,
    }
    if len(after) != len(before) + 1 or len(created) != 1:
        raise GateError(
            "ADD_MATE_FEATURE_DELTA_FAIL",
            "MateGroup traversal did not resolve exactly one newly created IFeature",
            {"before_names": before_names, "after_names": after_names, "created": created},
        )
    created_semantics = {key: created[0][key] for key in expected}
    returned_semantics = {key: returned_fact[key] for key in expected}
    # CLOSEST is an input instruction for ordinary geometric mates.  SW2024
    # resolves it to the actual ALIGNED/ANTI_ALIGNED state stored on IMate2;
    # component LOCK is the proven exception and remains CLOSEST in the model.
    allowed_alignments = (
        {SW_ALIGN_ALIGNED, SW_ALIGN_ANTI_ALIGNED}
        if expected_align == SW_ALIGN_CLOSEST and expected_type != SW_MATE_LOCK
        else {int(expected_align)}
    )
    resolved_alignment = int(created[0]["alignment"])
    if (
        created_semantics != expected
        or returned_semantics != expected
        or int(returned_fact["alignment"]) != resolved_alignment
        or resolved_alignment not in allowed_alignments
    ):
        raise GateError(
            "ADD_MATE_SEMANTIC_FAIL",
            "returned IMate2 or resolved MateGroup IFeature does not match the requested exact mate",
            {"expected": {**expected, "requested_alignment": expected_align, "allowed_resolved_alignments": sorted(allowed_alignments)}, "returned_imate2": returned_fact, "resolved_feature": created[0]},
        )
    return {
        "feature_name": created[0]["feature_name"],
        "feature_resolution": "MateGroup.GetFirstSubFeature/GetNextSubFeature -> IFeature; unique before/after name delta",
        "mate_object_returned": True,
        "return_interface": "IMate2",
        "mate_type": expected_type,
        "align": expected_align,
        "resolved_alignment": resolved_alignment,
        "error_status": error,
        "selected_count": selected_count,
        "component_paths": expected_paths,
    }


def add_entity_mate(model: Any, assembly: Any, first: Any, second: Any, mate_type: int, align: int, expected_components: Sequence[Any], types: Any, pythoncom: Any) -> Dict[str, Any]:
    before = mate_ledger(model, types, pythoncom)
    model.ClearSelection2(True)
    manager = selection_manager(model, types, pythoncom)
    data = wrap(manager.CreateSelectData(), "ISelectData", types, pythoncom)
    data.Mark = 1
    if not bool(first.Select4(False, data)) or not bool(second.Select4(True, data)):
        raise GateError("ENTITY_SELECTION_FAIL", "IEntity.Select4 failed")
    selected = int(manager.GetSelectedObjectCount2(1))
    returned = assembly.AddMate3(mate_type, align, False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
    model.ClearSelection2(True)
    return resolve_created_mate(model, returned, before, mate_type, align, expected_components, selected, types, pythoncom)


def add_lock_mate(model: Any, assembly: Any, first: Any, second: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    before = mate_ledger(model, types, pythoncom)
    model.ClearSelection2(True)
    manager = selection_manager(model, types, pythoncom)
    data = wrap(manager.CreateSelectData(), "ISelectData", types, pythoncom)
    data.Mark = 1
    if not bool(first.Select4(False, data, False)) or not bool(second.Select4(True, data, False)):
        raise GateError("LOCK_SELECTION_FAIL", "cannot select panel/lug components")
    selected = int(manager.GetSelectedObjectCount2(1))
    returned = assembly.AddMate3(SW_MATE_LOCK, SW_ALIGN_CLOSEST, False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
    model.ClearSelection2(True)
    return resolve_created_mate(model, returned, before, SW_MATE_LOCK, SW_ALIGN_CLOSEST, (first, second), selected, types, pythoncom)


def get_components(model: Any, types: Any, pythoncom: Any) -> List[Any]:
    assembly = wrap(model, "IAssemblyDoc", types, pythoncom)
    return [wrap(raw, "IComponent2", types, pythoncom) for raw in as_list(assembly.GetComponents(False))]


def component_path(component: Any) -> Path:
    return Path(str(value(component, "GetPathName"))).resolve()


def component_by_path(model: Any, target: Path, types: Any, pythoncom: Any) -> Any:
    matches = [component for component in get_components(model, types, pythoncom) if component_path(component) == target.resolve()]
    if len(matches) != 1:
        raise GateError("COMPONENT_PATH_CARDINALITY_FAIL", "component path is not unique", {"target": norm(target), "count": len(matches)})
    return matches[0]


def transform_array(component: Any) -> List[float]:
    return [float(v) for v in as_list(value(value(component, "Transform2"), "ArrayData"))]


def math_xyz(raw: Any, interface: str, types: Any, pythoncom: Any) -> Optional[List[float]]:
    if raw is None:
        return None
    try:
        typed = wrap(raw, interface, types, pythoncom)
        data = [float(number) for number in as_list(value(typed, "ArrayData"))]
    except Exception as exc:
        raise GateError("REMAINING_DOF_MATH_OBJECT_FAIL", "GetRemainingDOFs returned an unreadable math object", {"interface": interface, "exception": repr(exc)}) from exc
    if len(data) != 3 or not all(math.isfinite(number) for number in data):
        raise GateError("REMAINING_DOF_MATH_SHAPE_FAIL", "remaining-DOF point/vector must contain three finite values", {"interface": interface, "array": data})
    return data


def remaining_dof_ledger(component: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw = component.GetRemainingDOFs()
    if not isinstance(raw, tuple) or len(raw) != 13:
        raise GateError(
            "REMAINING_DOF_RETURN_SHAPE_FAIL",
            "SW2024 IComponent2.GetRemainingDOFs must return one API result plus twelve out parameters",
            {"component": str(value(component, "Name2")), "returned_type": type(raw).__name__, "returned_repr": repr(raw)},
        )
    specifications = (
        ("Rpoint1", "IMathPoint"),
        ("Rdirection1", "IMathVector"),
        ("Rpoint2", "IMathPoint"),
        ("Rdirection2", "IMathVector"),
        ("Tdirection1", "IMathVector"),
        ("Tdirection2", "IMathVector"),
    )
    slots: Dict[str, Dict[str, Any]] = {}
    output12: List[Dict[str, Any]] = []
    for slot_index, (name, interface) in enumerate(specifications):
        status = int(raw[1 + 2 * slot_index])
        coordinates = math_xyz(raw[2 + 2 * slot_index], interface, types, pythoncom)
        slots[name] = {"status": status, "value": coordinates, "interface": interface}
        output12.extend((
            {"parameter": f"{name}_status", "value": status},
            {"parameter": name, "value": coordinates, "interface": interface},
        ))
    return {
        "component_name2": str(value(component, "Name2")),
        "component_path": norm(component_path(component)),
        "api_return": int(raw[0]),
        "api_return_semantics": "0=CALL_SUCCESS; DOF_CLASSIFICATION_IS_IN_THE_12_OUT_PARAMETERS",
        "output12": output12,
        "slots": slots,
    }


def constrained_status_ledger(component: Any) -> Dict[str, Any]:
    status = int(value(component, "GetConstrainedStatus"))
    return {
        "value": status,
        "name": SW_CONSTRAINED_STATUS_NAMES.get(status, "UNRECOGNIZED_SW2024_STATUS"),
    }


def prove_component_true_1r(component: Any, axis_y_mm: float, types: Any, pythoncom: Any) -> Dict[str, Any]:
    constrained = constrained_status_ledger(component)
    dof = remaining_dof_ledger(component, types, pythoncom)
    slots = dof["slots"]
    rotation_point = slots["Rpoint1"]["value"]
    rotation_direction = slots["Rdirection1"]["value"]
    absent_statuses = {
        name: slots[name]["status"]
        for name in ("Rpoint2", "Rdirection2", "Tdirection1", "Tdirection2")
    }
    axis_length = math.sqrt(sum(number * number for number in rotation_direction)) if rotation_direction is not None else None
    exact_1r = (
        constrained["value"] == SW_UNDER_CONSTRAINED
        and dof["api_return"] == SW_GET_REMAINING_DOFS_SUCCESS
        and slots["Rpoint1"]["status"] == 1
        and slots["Rdirection1"]["status"] == 1
        and rotation_point is not None
        and rotation_direction is not None
        and all(status == 0 for status in absent_statuses.values())
        and abs(rotation_point[1] * 1000.0 - axis_y_mm) <= 1e-5
        and abs(rotation_point[2] * 1000.0) <= 1e-5
        and axis_length is not None
        and abs(axis_length - 1.0) <= 1e-8
        and abs(abs(rotation_direction[0]) - 1.0) <= 1e-8
        and abs(rotation_direction[1]) <= 1e-8
        and abs(rotation_direction[2]) <= 1e-8
    )
    result = {
        "component_name2": str(value(component, "Name2")),
        "constrained_status": constrained,
        "remaining_dofs": dof,
        "expected_axis": {"axis": "+/-X", "y_mm": axis_y_mm, "z_mm": 0.0},
        "rotation_axis_length": axis_length,
        "absent_dof_statuses": absent_statuses,
        "exact_true_1r": exact_1r,
    }
    if not exact_1r:
        raise GateError("TRUE_1R_COMPONENT_FAIL", "component does not expose exactly one rotational DOF about the registered X hinge axis", result)
    return result


def max_transform_error(actual: Sequence[float], expected: Sequence[float]) -> float:
    if len(actual) != 16 or len(expected) != 16:
        return float("inf")
    return max(abs(float(a) - float(b)) for a, b in zip(actual, expected))


def mate_signature(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{
        "feature_name": row["feature_name"],
        "feature_error_code": row["feature_error_code"],
        "feature_error_code2": row["feature_error_code2"],
        "feature_is_warning": row["feature_is_warning"],
        "suppressed": row["suppressed"],
        "mate_type": row["mate_type"],
        "alignment": row["alignment"],
        "entity_count": row["entity_count"],
        "component_paths": row["component_paths"],
    } for row in rows]


def lock_mate_feature(model: Any, types: Any, pythoncom: Any) -> Any:
    """Return the IFeature of the single type-16 lock mate in the MateGroup."""
    feature = value(model, "FirstFeature")
    for _ in range(10000):
        if feature is None:
            break
        typed = wrap(feature, "IFeature", types, pythoncom)
        if str(value(typed, "GetTypeName2")) == "MateGroup":
            sub = value(typed, "GetFirstSubFeature")
            for _sub_index in range(10000):
                if sub is None:
                    break
                sf = wrap(sub, "IFeature", types, pythoncom)
                raw_mate = value(sf, "GetSpecificFeature2")
                if raw_mate is not None and int(value(wrap(raw_mate, "IMate2", types, pythoncom), "Type")) == SW_MATE_LOCK:
                    return sf
                sub = value(sf, "GetNextSubFeature")
        feature = value(typed, "GetNextFeature")
    raise GateError("LOCK_MATE_FEATURE_NOT_FOUND", "no lock mate IFeature in MateGroup traversal")


def apply_hinge_group_pose(
    sw: Any,
    model: Any,
    panel: Any,
    lug: Any,
    side: str,
    angle_rad: float,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    expected = rotation_x_about_y_data(angle_rad, float(SIDES[side]["axis_y_mm"]) / 1000.0)
    # Proven SW2024 drive mechanism (in-memory probes 1-4, receipts in
    # 13_validation/V5_DIAG_LOOP1B_PROBE*.log): a lock mate does NOT transmit
    # motion under SetTransformAndSolve3, and a lock-mated follower cannot be
    # placed exactly while the lock is active.  The deterministic sequence is:
    # suppress the lock mate (PANEL becomes a free component and places
    # exactly), place LUG and PANEL with solve-free absolute transforms (the
    # commanded pose is a pure rotation about the registered hinge axis and
    # satisfies every entity mate identically), restore the lock — satisfied
    # identically at the commanded pose — and rebuild.  All downstream gates
    # (2e-7 transform readback, rigid-group, pivot, mate ledger, true-1R,
    # cold reopen) remain fail-closed and unchanged.
    lock = lock_mate_feature(model, types, pythoncom)
    lock.SetSuppression2(SW_SUPPRESS_FEATURE, SW_ALL_CONFIGURATIONS, None)
    if not bool(value(lock, "IsSuppressed")):
        raise GateError("LOCK_SUPPRESS_FAIL", "lock mate suppression readback failed", {"side": side, "angle_rad": angle_rad})
    if not bool(model.EditRebuild3()):
        raise GateError("HINGE_GROUP_REBUILD_FAIL", "lock suppression rebuild failed", {"side": side, "angle_rad": angle_rad})
    target = make_transform(sw, expected, types, pythoncom)
    if not bool(lug.SetTransformAndSolve3(target, False)):
        raise GateError("HINGE_GROUP_POSE_SOLVE_FAIL", "LUG rigid hinge group transform failed", {"side": side, "angle_rad": angle_rad})
    if not bool(panel.SetTransformAndSolve3(make_transform(sw, expected, types, pythoncom), False)):
        raise GateError("HINGE_GROUP_POSE_SOLVE_FAIL", "PANEL rigid hinge group transform failed", {"side": side, "angle_rad": angle_rad})
    lock.SetSuppression2(SW_UNSUPPRESS_FEATURE, SW_ALL_CONFIGURATIONS, None)
    if bool(value(lock, "IsSuppressed")):
        raise GateError("LOCK_UNSUPPRESS_FAIL", "lock mate restore readback failed", {"side": side, "angle_rad": angle_rad})
    if not bool(model.EditRebuild3()):
        raise GateError("HINGE_GROUP_REBUILD_FAIL", "hinge rigid group rebuild failed", {"side": side, "angle_rad": angle_rad})
    panel_transform = transform_array(panel)
    lug_transform = transform_array(lug)
    panel_error = max_transform_error(panel_transform, expected)
    lug_error = max_transform_error(lug_transform, expected)
    rigid_group_error = max_transform_error(panel_transform, lug_transform)
    panel_angle = math.atan2(panel_transform[5], panel_transform[4]) if len(panel_transform) == 16 else float("nan")
    lug_angle = math.atan2(lug_transform[5], lug_transform[4]) if len(lug_transform) == 16 else float("nan")
    axis_y_m = float(SIDES[side]["axis_y_mm"]) / 1000.0
    pivot_after = [
        expected[0] * 0.0 + expected[3] * axis_y_m + expected[6] * 0.0 + expected[9],
        expected[1] * 0.0 + expected[4] * axis_y_m + expected[7] * 0.0 + expected[10],
        expected[2] * 0.0 + expected[5] * axis_y_m + expected[8] * 0.0 + expected[11],
    ]
    transform_pass = (
        panel_error <= 2e-7
        and lug_error <= 2e-7
        and rigid_group_error <= 2e-7
        and abs(panel_angle - angle_rad) <= 1e-6
        and abs(lug_angle - angle_rad) <= 1e-6
        and max(abs(pivot_after[0]), abs(pivot_after[1] - axis_y_m), abs(pivot_after[2])) <= 1e-9
    )
    if not transform_pass:
        raise GateError(
            "HINGE_GROUP_KINEMATIC_DRIFT",
            "PANEL/LUG did not move as one rigid body in pure rotation about the registered X axis",
            {"side": side, "angle_rad": angle_rad, "expected_transform": expected, "panel_transform": panel_transform, "lug_transform": lug_transform, "panel_error": panel_error, "lug_error": lug_error, "rigid_group_error": rigid_group_error, "pivot_after_m": pivot_after},
        )
    panel_state = prove_component_true_1r(panel, float(SIDES[side]["axis_y_mm"]), types, pythoncom)
    lug_state = prove_component_true_1r(lug, float(SIDES[side]["axis_y_mm"]), types, pythoncom)
    ledger = mate_ledger(model, types, pythoncom)
    if len(ledger) != 5:
        raise GateError("HINGE_POSE_MATE_COUNT_FAIL", "hinge pose does not retain exactly five healthy real mates", {"angle_rad": angle_rad, "ledger": ledger})
    return {
        "command_driver": "LOCK_SUPPRESSED_SOLVE_FREE_EXACT_PLACEMENT_THEN_LOCK_RESTORED",
        "angle_rad": angle_rad,
        "expected_transform": expected,
        "panel_transform": panel_transform,
        "lug_transform": lug_transform,
        "panel_expected_max_abs_error": panel_error,
        "lug_expected_max_abs_error": lug_error,
        "panel_lug_rigid_max_abs_error": rigid_group_error,
        "panel_readback_angle_rad": panel_angle,
        "lug_readback_angle_rad": lug_angle,
        "hinge_pivot_after_m": pivot_after,
        "panel_state": panel_state,
        "lug_state": lug_state,
        "mate_ledger": ledger,
    }


def prove_hinge_rigid_group_motion(sw: Any, model: Any, components: Dict[str, Any], side: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    panel, lug = components["PANEL"], components["LUG"]
    baseline = apply_hinge_group_pose(sw, model, panel, lug, side, 0.0, types, pythoncom)
    baseline_mates = mate_signature(baseline["mate_ledger"])
    group_names = {str(value(panel, "Name2")), str(value(lug, "Name2"))}
    other_components = [component for component in get_components(model, types, pythoncom) if str(value(component, "Name2")) not in group_names]
    other_baseline = {str(value(component, "Name2")): transform_array(component) for component in other_components}
    samples = []
    for angle_deg in (0.5, -0.5):
        sample = apply_hinge_group_pose(sw, model, panel, lug, side, math.radians(angle_deg), types, pythoncom)
        if mate_signature(sample["mate_ledger"]) != baseline_mates:
            raise GateError("HINGE_DIAGNOSTIC_MATE_DRIFT", "native mate ledger changed during +/- small-angle motion proof", {"angle_deg": angle_deg, "baseline": baseline_mates, "actual": mate_signature(sample["mate_ledger"])})
        other_drift = {}
        for component in other_components:
            name = str(value(component, "Name2"))
            error = max_transform_error(transform_array(component), other_baseline[name])
            other_drift[name] = error
            if error > 2e-7:
                raise GateError("HINGE_DIAGNOSTIC_OTHER_COMPONENT_DRIFT", "non-hinge component translated or tilted during 1R proof", {"angle_deg": angle_deg, "component": name, "max_abs_error": error})
        sample["diagnostic_angle_deg"] = angle_deg
        sample["other_component_transform_drift"] = other_drift
        samples.append(sample)
    restored = apply_hinge_group_pose(sw, model, panel, lug, side, 0.0, types, pythoncom)
    if mate_signature(restored["mate_ledger"]) != baseline_mates:
        raise GateError("HINGE_DIAGNOSTIC_RESTORE_MATE_DRIFT", "mate ledger drifted after restoring diagnostic motion")
    return {
        "diagnostic_only": True,
        "diagnostic_angles_deg": [0.5, -0.5],
        "configuration_authority_created": False,
        "intermediate_angle_authority": "NONE",
        "driver": "PANEL_AND_LUG_EXACT_TRANSFORM_NOSOLVE_UNDER_LOCK_SUPPRESSION",
        "follower": "NONE; LOCK_RESTORED_AFTER_PLACEMENT_AND_RIGIDITY_PROVEN_BY_READBACK",
        "baseline": baseline,
        "samples": samples,
        "restored_zero": restored,
        "verdict": "PANEL_LUG_RIGID_GROUP_TRUE_1R_PLUS_MINUS_SMALL_ANGLE_PASS",
    }


def add_configurations(sw: Any, model: Any, side: str, panel_path: Path, lug_path: Path, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    manager = value(model, "ConfigurationManager")
    existing = [str(name) for name in as_list(value(model, "GetConfigurationNames"))]
    for name in CONFIG_ANGLES:
        if name not in existing:
            created = manager.AddConfiguration2(name, "F3R2 V5 authoritative 0/90 wing state; DEPLOYING remains free 1R", "", 0, "", False, False)
            if created is None:
                raise GateError("CONFIG_CREATE_FAIL", "AddConfiguration2 returned null", {"configuration": name})
            existing.append(name)
    rows = []
    for name, angles in CONFIG_ANGLES.items():
        if not bool(model.ShowConfiguration2(name)) or str(value(value(model, "ConfigurationManager"), "ActiveConfiguration").Name) != name:
            raise GateError("CONFIG_ACTIVATE_FAIL", "configuration activation failed", {"configuration": name})
        panel = component_by_path(model, panel_path, types, pythoncom)
        lug = component_by_path(model, lug_path, types, pythoncom)
        angle_deg = angles[side]
        command = 0.0 if angle_deg in (None, 90.0) else float(SIDES[side]["stowed_rotation_rad"])
        pose = apply_hinge_group_pose(sw, model, panel, lug, side, command, types, pythoncom)
        props = model.Extension.CustomPropertyManager(name)
        for key, val in {"WingSide": side, "AuthorityAngleDeg": "FREE_1R" if angle_deg is None else str(angle_deg), "AuthoritySourceSHA256": FIXED_INPUTS[-1][1], "IntermediateAngleAuthority": "NONE", "PhysicalPanelInstanceCount": "1", "HingeAxis": f"X@Y={SIDES[side]['axis_y_mm']}mm,Z=0"}.items():
            if int(props.Add3(key, 30, val, 2)) < 0:
                raise GateError("CONFIG_PROPERTY_FAIL", "configuration property write failed", {"configuration": name, "property": key})
        if name == "DEPLOYING" and (not pose["panel_state"]["exact_true_1r"] or not pose["lug_state"]["exact_true_1r"]):
            raise GateError("DEPLOYING_1R_FAIL", "DEPLOYING does not retain exact PANEL/LUG group 1R", {"pose": pose})
        rows.append({"configuration": name, "authority_angle_deg": angle_deg, "saved_rotation_rad": pose["panel_readback_angle_rad"], "physical_panel_path": norm(panel_path), "physical_lug_path": norm(lug_path), "physical_panel_instance_count": 1, "intermediate_angle_written": False, "rigid_group_pose": pose})
    return rows


def component_reference_ledger(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows = []
    for component in get_components(model, types, pythoncom):
        path = component_path(component)
        if RUN_ROOT.resolve() not in path.parents or not path.is_file():
            raise GateError("REFERENCE_OUTSIDE_V5", "assembly component is absent or outside unique V5 root", {"path": str(path)})
        rows.append({"name2": str(value(component, "Name2")), "path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path), "fixed": bool(value(component, "IsFixed")), "suppression": int(value(component, "GetSuppression")), "transform": transform_array(component)})
    return sorted(rows, key=lambda row: (row["path"], row["name2"]))


def save_assembly(model: Any, target: Path) -> Dict[str, Any]:
    if not bool(model.ForceRebuild3(True)):
        raise GateError("ASSEMBLY_REBUILD_FAIL", "assembly rebuild failed before save")
    return save_as(model, target)


def build_wing_assembly(sw: Any, types: Any, pythoncom: Any, side: str) -> Dict[str, Any]:
    spec = SIDES[side]
    key, target = f"{side}_ASSEMBLY", Path(spec["assembly"])
    if target.exists():
        return {**load_artifact_result(key, target), "resumed_from_checkpoint": True}
    model = None
    try:
        raw = sw.NewDocument(str(ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        if raw is None:
            raw = value(sw, "ActiveDoc")
        if raw is None:
            raise GateError("NEW_ASSEMBLY_FAIL", "cannot create wing-root assembly")
        model = wrap(raw, "IModelDoc2", types, pythoncom)
        assembly = wrap(model, "IAssemblyDoc", types, pythoncom)
        ay = float(spec["axis_y_mm"]) / 1000.0
        sign = 1.0 if side == "L" else -1.0
        entries = [
            ("CLEVIS", Path(spec["clevis"]), True, (0.0, 0.0, 0.0)),
            ("PANEL", Path(spec["panel"]), False, (0.0, 0.0, 0.0)),
            ("LUG", Path(spec["lug"]), False, (0.0, 0.0, 0.0)),
            ("PIN", Path(spec["pin"]), True, (0.0, 0.0, 0.0)),
            ("SPRING_1", Path(spec["springs"][0]), True, (0.0, 0.0, 0.0)),
            ("SPRING_2", Path(spec["springs"][1]), True, (0.0, 0.0, 0.0)),
            ("DONOR_STOP", Path(spec["stop"]), True, (0.0, 0.0, 0.0)),
            ("SERVICE_LOOP", Path(spec["loop"]), True, (0.0, 0.0, 0.0)),
            ("RETAINER", Path(spec["retainer"]), False, (0.0, 0.0, 0.0)),
            ("AXIAL_SPACER", V5_PART["SPACER"], True, (-0.0755, ay, 0.0)),
            ("GROMMET", V5_PART["GROMMET"], True, (-0.110, ay, -0.020)),
            ("STOP_PAD", V5_PART["STOP_PAD"], True, (-0.058, sign * 0.12115, 0.037)),
        ]
        components = {role: insert_component(sw, model, assembly, path, fixed, translation, types, pythoncom) for role, path, fixed, translation in entries}
        if sum(1 for _role, path, _fixed, _translation in entries if path.resolve() == Path(spec["panel"]).resolve()) != 1:
            raise GateError("PHYSICAL_PANEL_COUNT_FAIL", "each side must contain exactly one physical panel instance")
        # Align the physical panel to the lug before the native lock mate so
        # that driving the lug later moves PANEL and LUG as one rigid group.
        lug_initial = transform_array(components["LUG"])
        if not bool(components["PANEL"].SetTransformAndSolve3(make_transform(sw, lug_initial, types, pythoncom), True)):
            raise GateError("PANEL_LUG_ALIGN_FAIL", "PANEL could not be aligned to LUG before lock", {"side": side})
        if not bool(model.EditRebuild3()):
            raise GateError("PANEL_LUG_ALIGN_REBUILD_FAIL", "rebuild failed after PANEL/LUG alignment", {"side": side})
        geometry = []
        mates = [add_lock_mate(model, assembly, components["PANEL"], components["LUG"], types, pythoncom)]
        lug_cyl, row = cylinder_entity(components["LUG"], 4.2, float(spec["axis_y_mm"]), 2, types, pythoncom); geometry.append({"role": "LUG_BORE", **row})
        pin_cyl, row = cylinder_entity(components["PIN"], 4.0, float(spec["axis_y_mm"]), 1, types, pythoncom); geometry.append({"role": "PIN_OD", **row})
        # SW2024 concentric-mate alignment convention (proven by in-memory
        # probes 1-4): the lug inner bore vs pin OD pair must be ANTI_ALIGNED,
        # otherwise AddMate3 flips the PANEL/LUG lock group 180 deg about Z at
        # creation; the retainer ID vs pin OD pair is the opposite sense.
        mates.append(add_entity_mate(model, assembly, lug_cyl, pin_cyl, SW_MATE_CONCENTRIC, SW_ALIGN_ANTI_ALIGNED, (components["LUG"], components["PIN"]), types, pythoncom))
        lug_face, row = plane_entity_x(components["LUG"], -75.0, types, pythoncom); geometry.append({"role": "LUG_AXIAL_FACE", **row})
        spacer_face, row = spacer_axial_plane_entity(components["AXIAL_SPACER"], float(spec["axis_y_mm"]), types, pythoncom); geometry.append({"role": "SPACER_AXIAL_FACE", **row})
        mates.append(add_entity_mate(model, assembly, lug_face, spacer_face, SW_MATE_COINCIDENT, SW_ALIGN_CLOSEST, (components["LUG"], components["AXIAL_SPACER"]), types, pythoncom))
        retainer_cyl, row = cylinder_entity(components["RETAINER"], 4.1, float(spec["axis_y_mm"]), 1, types, pythoncom); geometry.append({"role": "RETAINER_ID", **row})
        mates.append(add_entity_mate(model, assembly, retainer_cyl, pin_cyl, SW_MATE_CONCENTRIC, SW_ALIGN_ALIGNED, (components["RETAINER"], components["PIN"]), types, pythoncom))
        retainer_face, row = plane_entity_x(components["RETAINER"], -82.0, types, pythoncom); geometry.append({"role": "RETAINER_FACE", **row})
        pin_face, row = plane_entity_x(components["PIN"], -82.0, types, pythoncom); geometry.append({"role": "PIN_END_FACE", **row})
        mates.append(add_entity_mate(model, assembly, retainer_face, pin_face, SW_MATE_COINCIDENT, SW_ALIGN_CLOSEST, (components["RETAINER"], components["PIN"]), types, pythoncom))
        # Fail-closed no-motion invariant (probe-proven): mate creation must not
        # relocate the as-built PANEL/LUG/RETAINER (all inserted at identity).
        identity16 = transform_data((0.0, 0.0, 0.0))
        for role in ("PANEL", "LUG", "RETAINER"):
            actual16 = transform_array(components[role])
            if max_transform_error(actual16, identity16) > 1e-9:
                raise GateError("MATE_CREATION_MOTION_FAIL", "mate creation relocated a hinge component off its as-built pose", {"side": side, "role": role, "actual_transform": actual16})
        motion_proof = prove_hinge_rigid_group_motion(sw, model, components, side, types, pythoncom)
        configs = add_configurations(sw, model, side, Path(spec["panel"]), Path(spec["lug"]), types, pythoncom)
        if not bool(model.ShowConfiguration2("DEPLOYING")):
            raise GateError("DEPLOYING_FINAL_ACTIVATE_FAIL", "cannot make DEPLOYING the saved active configuration")
        ledger = mate_ledger(model, types, pythoncom)
        if len(ledger) != 5:
            raise GateError("MATE_COUNT_FAIL", "wing-root mate ledger must contain exactly five real mates", {"ledger": ledger})
        references = component_reference_ledger(model, types, pythoncom)
        if sum(1 for row in references if row["path"] == norm(Path(spec["panel"]))) != 1:
            raise GateError("PANEL_REFERENCE_CARDINALITY_FAIL", "assembly reference ledger does not contain exactly one panel")
        saved = save_assembly(model, target)
    finally:
        close_doc(sw, model)
    cold = None
    try:
        cold, opened = open_doc(sw, target, SW_ASSEMBLY, True, types, pythoncom)
        cold_refs = component_reference_ledger(cold, types, pythoncom)
        cold_mates = mate_ledger(cold, types, pythoncom)
        if [(r["path"], r["sha256"]) for r in cold_refs] != [(r["path"], r["sha256"]) for r in references] or [(r["mate_type"], r["component_paths"]) for r in cold_mates] != [(r["mate_type"], r["component_paths"]) for r in ledger]:
            raise GateError("COLD_REFERENCE_OR_MATE_DRIFT", "cold assembly reference/mate semantics drifted")
        cold_configs = []
        names = [str(name) for name in as_list(value(cold, "GetConfigurationNames"))]
        if not set(CONFIG_ANGLES).issubset(names):
            raise GateError("COLD_CONFIG_SET_FAIL", "cold assembly is missing required configurations", {"names": names})
        for name, angles in CONFIG_ANGLES.items():
            if not bool(cold.ShowConfiguration2(name)):
                raise GateError("COLD_CONFIG_ACTIVATE_FAIL", "cold configuration activation failed", {"name": name})
            # Probe 7: in some saved configurations the remaining-DOF solver
            # state is stale after cold open (GetRemainingDOFs returns 2 with
            # zeroed slots); EditRebuild3 does NOT cure it, ForceRebuild3 does.
            # The force rebuild runs in memory only (document is read-only and
            # never saved), so the write-once file is untouched.
            if not bool(cold.ForceRebuild3(True)):
                raise GateError("COLD_CONFIG_REBUILD_FAIL", "cold configuration force rebuild failed", {"name": name})
            panel = component_by_path(cold, Path(spec["panel"]), types, pythoncom)
            lug = component_by_path(cold, Path(spec["lug"]), types, pythoncom)
            panel_transform = transform_array(panel)
            lug_transform = transform_array(lug)
            expected_angle = 0.0 if angles[side] in (None, 90.0) else float(spec["stowed_rotation_rad"])
            expected_transform = rotation_x_about_y_data(expected_angle, float(spec["axis_y_mm"]) / 1000.0)
            panel_error = max_transform_error(panel_transform, expected_transform)
            lug_error = max_transform_error(lug_transform, expected_transform)
            group_error = max_transform_error(panel_transform, lug_transform)
            actual = math.atan2(panel_transform[5], panel_transform[4]) if len(panel_transform) == 16 else float("nan")
            if panel_error > 2e-7 or lug_error > 2e-7 or group_error > 2e-7 or abs(actual - expected_angle) > 1e-6:
                raise GateError("COLD_CONFIG_POSE_FAIL", "cold PANEL/LUG rigid-group pose drifted", {"name": name, "expected_rad": expected_angle, "actual_rad": actual, "panel_error": panel_error, "lug_error": lug_error, "group_error": group_error, "panel_transform": panel_transform, "lug_transform": lug_transform})
            panel_state = prove_component_true_1r(panel, float(spec["axis_y_mm"]), types, pythoncom)
            lug_state = prove_component_true_1r(lug, float(spec["axis_y_mm"]), types, pythoncom)
            config_mates = mate_ledger(cold, types, pythoncom)
            if len(config_mates) != 5 or mate_signature(config_mates) != mate_signature(ledger):
                raise GateError("COLD_CONFIG_MATE_LEDGER_FAIL", "cold configuration mate ledger drifted from saved five-mate contract", {"name": name, "expected": mate_signature(ledger), "actual": mate_signature(config_mates)})
            if name == "DEPLOYING" and (not panel_state["exact_true_1r"] or not lug_state["exact_true_1r"]):
                raise GateError("COLD_DEPLOYING_1R_FAIL", "cold DEPLOYING state lost exact PANEL/LUG group 1R", {"panel_state": panel_state, "lug_state": lug_state})
            cold_configs.append({"configuration": name, "authority_angle_deg": angles[side], "saved_rotation_rad": actual, "panel_transform": panel_transform, "lug_transform": lug_transform, "panel_expected_max_abs_error": panel_error, "lug_expected_max_abs_error": lug_error, "panel_lug_rigid_max_abs_error": group_error, "panel_state": panel_state, "lug_state": lug_state, "mate_ledger": config_mates, "panel_instance_count": 1})
    finally:
        close_doc(sw, cold)
    result = {"key": key, "side": side, "target": saved, "hinge_axis": {"axis": "X", "y_mm": spec["axis_y_mm"], "z_mm": 0.0}, "physical_panel": {"path": norm(Path(spec["panel"])), "instance_count": 1, "same_instance_all_configurations": True}, "components": references, "geometry_selection": geometry, "mates_created": mates, "mate_ledger": ledger, "rigid_group_motion_proof": motion_proof, "configurations": configs, "cold_open": opened, "cold_components": cold_refs, "cold_mate_ledger": cold_mates, "cold_configurations": cold_configs, "constrained_status_enum": SW_CONSTRAINED_STATUS_NAMES, "remaining_dof_contract": "API_RETURN_ZERO_PLUS_EXACT_12_OUT_PARAMETER_PATTERN_PROVES_PANEL_AND_LUG_1R_ABOUT_REGISTERED_X_AXIS; NO_INTERMEDIATE_ANGLE_AUTHORITY", "interference_closure_claimed": False, "verdict": "V5_LOOP1B1_TRUE_HINGE_ASSEMBLY_COLD_REOPEN_PASS"}
    result["checkpoint"] = checkpoint_artifact(key, target, result)
    return result


def stage_checkpoint(path: Path, schema: str, items: Sequence[Dict[str, Any]], verdict: str) -> Dict[str, Any]:
    if path.exists():
        payload = load_json(path)
        if (
            payload.get("schema") != schema
            or not accepted_checkpoint_script_hash(payload.get("script_sha256"))
            or payload.get("g0_sha256") != FIXED_INPUTS[0][1]
            or payload.get("loop1_sha256") != FIXED_INPUTS[1][1]
            or payload.get("loop1a_sha256") != FIXED_INPUTS[2][1]
            or payload.get("verdict") != verdict
        ):
            raise GateError("STAGE_CHECKPOINT_DRIFT", "existing stage checkpoint is invalid", {"path": norm(path)})
        return file_fact(path)
    payload = {"schema": schema, "timestamp_utc": utc_now(), "script_sha256": sha256(Path(__file__)), "g0_sha256": FIXED_INPUTS[0][1], "loop1_sha256": FIXED_INPUTS[1][1], "loop1a_sha256": FIXED_INPUTS[2][1], "items": list(items), "verdict": verdict}
    write_json_once(path, payload)
    return file_fact(path)


def execute(stage: str) -> int:
    result: Dict[str, Any] = {"schema": "F3R2_V5_LOOP1B_WING_ROOT_RECEIPT_V1", "timestamp_start_utc": utc_now(), "run_root": norm(RUN_ROOT), "requested_stage": stage, "donor_imports": [], "native_parts": [], "assemblies": []}
    sw = types = pythoncom = None
    try:
        audit = static_audit()
        if not audit["execution_authorized"]:
            raise GateError("STATIC_EXECUTION_HOLD", "static audit does not authorize Loop-1B execution", {"audit": audit})
        result["input_audit"] = audit
        result["protected_pre"] = audit_protected()
        result["baseline_pre"] = registered_baseline()
        result["memory_samples_gib"] = memory_gate()
        sw, types, pythoncom, session = attach_empty_session(result["baseline_pre"]["session_b_pid"])
        result["solidworks"] = session
        if stage in ("1B0", "ALL"):
            for item in DONORS.values():
                result["donor_imports"].append(isolate_donor(sw, types, pythoncom, item))
            result["stage_1b0_checkpoint"] = stage_checkpoint(STAGE_1B0, "F3R2_V5_LOOP1B0_DONOR_IMPORT_CHECKPOINT_V1", result["donor_imports"], "V5_LOOP1B0_DONORS_LOCAL_NATIVE_ZERO_LINK_PASS")
        elif not STAGE_1B0.is_file():
            raise GateError("STAGE_1B0_REQUIRED", "1B1 requires the write-once 1B0 checkpoint")
        if stage in ("1B1", "ALL"):
            if not STAGE_1B0.is_file():
                raise GateError("STAGE_1B0_REQUIRED", "1B1 cannot run before 1B0")
            for side in ("L", "R"):
                result["native_parts"].append(make_lug(sw, types, pythoncom, side))
                result["native_parts"].append(make_retainer(sw, types, pythoncom, side))
            for side in ("L", "R"):
                result["assemblies"].append(build_wing_assembly(sw, types, pythoncom, side))
            result["stage_1b1_checkpoint"] = stage_checkpoint(STAGE_1B1, "F3R2_V5_LOOP1B1_WING_ROOT_CHECKPOINT_V1", [*result["native_parts"], *result["assemblies"]], "V5_LOOP1B1_DUAL_TRUE_HINGE_COLD_REOPEN_PASS")
        result["baseline_post"] = registered_baseline()
        result["protected_post"] = audit_protected()
        if result["baseline_pre"] != result["baseline_post"] or result["protected_pre"] != result["protected_post"]:
            raise GateError("PROTECTED_POST_DRIFT", "protected or 20-part/Loop-1A baseline changed")
        if int(value(sw, "GetDocumentCount")) != 0 or value(sw, "ActiveDoc") is not None:
            raise GateError("DOCUMENT_CLEANUP_FAIL", "owned documents remain open after Loop-1B", {"document_count": int(value(sw, "GetDocumentCount"))})
        if stage == "1B0":
            result.update({"timestamp_end_utc": utc_now(), "verdict": "V5_LOOP1B0_DONOR_IMPORT_PASS_CONTINUE_1B1"})
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if SCRIPT_COPY.exists():
            if sha256(SCRIPT_COPY) != sha256(Path(__file__)):
                raise GateError("SCRIPT_COPY_DRIFT", "existing V5 tool copy differs from executing script")
        else:
            shutil.copy2(Path(__file__).resolve(), SCRIPT_COPY)
        manifest_paths = [Path(item["target"]) for item in DONORS.values()] + [Path(SIDES[s]["lug"]) for s in SIDES] + [Path(SIDES[s]["retainer"]) for s in SIDES] + [Path(SIDES[s]["assembly"]) for s in SIDES] + [artifact_checkpoint(key) for key in DONORS] + [artifact_checkpoint(f"{s}_LUG") for s in SIDES] + [artifact_checkpoint(f"{s}_RETAINER") for s in SIDES] + [artifact_checkpoint(f"{s}_ASSEMBLY") for s in SIDES] + [STAGE_1B0, STAGE_1B1, SCRIPT_COPY, G0_READY, IMPORT_RECEIPT, LOOP1A_RECEIPT]
        lines = [f"{sha256(path)}  {path.stat().st_size}  {path.relative_to(RUN_ROOT).as_posix() if RUN_ROOT.resolve() in path.resolve().parents else norm(path)}" for path in manifest_paths]
        write_text_once(FINAL_MANIFEST, "\n".join(sorted(lines)) + "\n")
        result.update({"timestamp_end_utc": utc_now(), "verdict": "V5_LOOP1B_DUAL_WING_ROOT_NATIVE_CLOSURE_PASS", "manifest": file_fact(FINAL_MANIFEST), "claims": {"same_physical_panel_per_side": True, "true_hinge_mates": True, "deploying_retains_1r": True, "intermediate_angle_created": False, "external_donor_links": 0, "interference_closed": False, "flight_qualified": False}, "remaining_holds": ["PANEL_ROOT_LUG_FASTENER_AND_LOCAL_NOTCH_DETAIL_REQUIRES_DESIGN_AUTHORITY", "SPRING_PRELOAD_TORQUE_AND_CYCLE_LIFE_NOT_QUALIFIED", "HARD_STOP_CONTACT_STRESS_AND_TOLERANCE_STACK_NOT_CLOSED", "HARNESS_SERVICE_LOOP_BEND_RADIUS_AND_CONNECTOR_RELEASE_NOT_QUALIFIED", "LOOP2_NATIVE_INTERFERENCE_AND_EXPECTED_CONTACT_WHITELIST_PENDING", "TOP_ASSEMBLY_INTEGRATION_PENDING"]})
        write_json_once(FINAL_RECEIPT, result)
        print(json.dumps({"verdict": result["verdict"], "receipt": norm(FINAL_RECEIPT), "receipt_sha256": sha256(FINAL_RECEIPT), "manifest_sha256": sha256(FINAL_MANIFEST), "solidworks_document_count": int(value(sw, "GetDocumentCount"))}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        result.update({"timestamp_end_utc": utc_now(), "verdict": getattr(exc, "code", "V5_LOOP1B_UNEXPECTED_EXCEPTION"), "reason": str(exc), "detail": getattr(exc, "detail", {}), "traceback": traceback.format_exc()})
        failure = VALIDATION / f"V5_LOOP1B_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
        try:
            write_json_once(failure, result)
            result["failure_receipt"] = file_fact(failure)
        except Exception:
            pass
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    finally:
        if sw is not None:
            try:
                close_owned_documents(sw)
            except Exception:
                pass
        sw = None
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F3R2 V5 Loop-1B wing-root native closure")
    parser.add_argument("command", choices=("audit", "execute"))
    parser.add_argument("--stage", choices=("1B0", "1B1", "ALL"), default="ALL")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        print(json.dumps(static_audit(), ensure_ascii=False, indent=2))
        return 0
    return execute(args.stage)


if __name__ == "__main__":
    raise SystemExit(main())
