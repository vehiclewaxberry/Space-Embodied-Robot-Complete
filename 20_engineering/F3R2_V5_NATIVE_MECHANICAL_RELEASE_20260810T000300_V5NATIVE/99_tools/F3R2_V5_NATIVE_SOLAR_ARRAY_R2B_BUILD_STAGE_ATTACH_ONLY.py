#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R2B-A write-once native solar-array build stage (attach-only).

This program is deliberately only the *build* half of a two-process
transaction.  It attaches to one explicitly authorised, already-running and
empty SOLIDWORKS 2024 SP5 process, writes every new CAD file below one unique
attempt root, performs same-PID sanity checks only, and emits a handoff for a
different-PID, read-only, zero-mutation verifier.  It never promotes an
attempt, never overwrites/resumes one, never starts/exits SOLIDWORKS, and never
changes the frozen B601 URDF or L0 mass/inertia truth.

Native attempt payload:
  * 38 SLDPRT mechanical placeholders;
  * 6 rigid panel-module SLDASM files;
  * 2 three-link side SLDASM files, each owning all seven solar states and
    three native hinges (concentric + coincident + advanced limit angle 0..90).
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import re
import sys
import traceback
from collections import Counter
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
AUTHORITY_DIR = RUN_ROOT / "00_authority"
VALIDATION = RUN_ROOT / "13_validation"
ATTEMPT_PARENT = VALIDATION / "solar_r2_attempts"

sys.path.insert(0, str(TOOLS))
import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base
import F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY as loop1b
import F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY as loop1d


STATE_AUTHORITY = AUTHORITY_DIR / "V5_SOLAR_STATE_AUTHORITY_R2B.json"
ARCHITECTURE_DECISION = AUTHORITY_DIR / "V5_SOLAR_R2_ASSEMBLY_ARCHITECTURE_DECISION.json"
STATIC_ORACLE = VALIDATION / "V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_20260812T181333.205056Z.json"
BUILD_AUTHORIZATION = VALIDATION / "V5_SOLAR_R2B_BUILD_AUTHORIZATION.json"
PRODUCTION_ROOT_FLIP_AUTHORIZATION = VALIDATION / "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_V1.json"
PRODUCTION_ROOT_FLIP_AUTHORIZER_SOURCE = TOOLS / "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZE.py"
PRODUCTION_ROOT_BRANCH_PROBE_SOURCE = TOOLS / "F3R2_V5_DIAG_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_PROTOCOL_ATTACH_ONLY.py"
PRODUCTION_ROOT_BRANCH_PROBE_RESULT = (
    TOOLS
    / "probe_logs/V5_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_20260813T_ROOTPROTOCOL_G1/RESULT.json"
)
P5_ROOT_BRANCH_FAILURE = (
    VALIDATION
    / "solar_r2_attempts/20260813T164200Z_P5A5/evidence/BUILD_FAILURE_20260813T084845.277077Z.json"
)
INTERFACE_REQUIREMENTS = AUTHORITY_DIR / "SOLAR_ARRAY_INTERFACE_REQUIREMENTS.md"
INTERFACE_FREEZE = VALIDATION / "V5_SOLAR_ARRAY_INTERFACE_REQUIREMENTS_FREEZE_R2.json"
QUARANTINE_RECEIPT = (
    VALIDATION
    / "quarantine/V5_SOLAR_ARRAY_INVALID_CANDIDATE_20260812T162256.8949918Z"
    / "V5_SOLAR_ARRAY_INVALID_CANDIDATE_QUARANTINE_RECEIPT.json"
)
ACCEPTED_URDF = ENGINEERING / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
BRANCH_PROBE_SOURCE = TOOLS / "F3R2_V5_DIAG_SOLAR_R2B_ROOT_BRANCH_PROBE_ATTACH_ONLY.py"
BRANCH_PROBE_RESULT = (
    TOOLS
    / "probe_logs/V5_SOLAR_R2B_ROOT_BRANCH_20260813T1232Z_BRANCH1/RESULT.json"
)

EXPECTED_BINDINGS: Tuple[Tuple[str, Path, str], ...] = (
    ("state_authority_r2b", STATE_AUTHORITY, "BA639C6BF4F0875B6FD9AFFF2E6CA7A5AA3BA1AF77C6BD5FEC07A8EB62D8E6D8"),
    ("assembly_architecture", ARCHITECTURE_DECISION, "3CC38465A6B7FA6E91F275BAE4052E1787B5A44A6F196AFCEFA88AA7D209D545"),
    ("static_oracle_r2b", VALIDATION / "V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_20260812T181333.205056Z.json", "F4E5E0CD5A8559991B60826C6221294948CD07889836500D81527AE0982196F6"),
    ("r2b_build_authorization", BUILD_AUTHORIZATION, "BAD16D48EAEDCF27B3953831B7108A4ADB95CC3DD8F476FB02CB29EAE454FCCB"),
    ("interface_requirements", INTERFACE_REQUIREMENTS, "62DDF827056D5199CCA68FD1714874E52FFB06398D4B856175435DD576504014"),
    ("interface_freeze", INTERFACE_FREEZE, "B60D8C635A030B0DB49DF7129D6B7F50ACB0F5B9FC912C2E5DED4405FF6542C8"),
    ("invalid_candidate_quarantine", QUARANTINE_RECEIPT, "C4FDE3D4435E14FC767E714D40CDA8124C89D77B4AB0D65661694B37C02DF81E"),
    ("accepted_b601_urdf", ACCEPTED_URDF, "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"),
    ("r2b_angle_branch_probe_source", BRANCH_PROBE_SOURCE, "3680D614AD10728FC54309D4E8CFC64DB518FA3864989F86B968ED45E119FFE8"),
    ("r2b_angle_branch_probe_result", BRANCH_PROBE_RESULT, "52FF2A64E874FD782008E5971CB3154C976E10068C994337CB0611195E97A77A"),
    ("production_root_flip_authorization", PRODUCTION_ROOT_FLIP_AUTHORIZATION, "07D3D9380668E0308981D0BF85D4EB0951789793F90EAB97503BB23C82C7280E"),
    ("production_root_flip_authorizer_source", PRODUCTION_ROOT_FLIP_AUTHORIZER_SOURCE, "A05E0492CEB5CB6D9A7710BFEB4D04EE9FC1F3E5F54EA51B3360A64B01175726"),
    ("production_root_branch_probe_source", PRODUCTION_ROOT_BRANCH_PROBE_SOURCE, "FBF3F0D53E3078D9E5A5B2CB0060A4EDBCC8BD7F01E6DE7B3C19F9A4ABD3F1D2"),
    ("production_root_branch_probe_result", PRODUCTION_ROOT_BRANCH_PROBE_RESULT, "18393CAC2423032AFF309361E37D5CE3612AA086C9EA5FD16D991EC2DF593DA0"),
    ("p5_root_branch_failure", P5_ROOT_BRANCH_FAILURE, "745F069350F1E04158C9D3479AEDDBAD1E55BB258CE07ED97FD061DBEE249A3E"),
)

EXPECTED_ROOT_FLIP_AUTHORIZATION_SHA256 = "07D3D9380668E0308981D0BF85D4EB0951789793F90EAB97503BB23C82C7280E"
EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256 = "316A433EF215A38A7E090E0AE88E3E6362D6079B25ACBB01596C810CD2790889"
PRE_PATCH_BUILDER_SHA256 = "A91EC2A29F28F5BA64FD552F75AB6204BA32318604DEB3569D4ACA4C61C05D43"
PRE_PATCH_CONTRACT_SHA256 = "891052B9291FCE299DCEBB7B539D8056525A1F242E8BD5B7417EF347138ABC44"

PART_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot")
ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot")
TEMPLATE_BINDINGS = (
    ("part_template", PART_TEMPLATE, "5DA21678EFE07EF465770630BEB4FFE540F23D47FCA07715F74D2AFDBEA87271"),
    ("assembly_template", ASSEMBLY_TEMPLATE, "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC"),
)

HELPER_SOURCES = (
    TOOLS / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py",
    TOOLS / "F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY.py",
    TOOLS / "F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY.py",
)
HELPER_SHA256 = {
    HELPER_SOURCES[0]: "E44BC52CFBDECCC107E361ACB0EDD993EFC46248EB663A994564B77BDA30F906",
    HELPER_SOURCES[1]: "32BC06FC6A1EFCD6426FE4608D03EABCBD2902CBA228E95B2AD7A91B4E0F283F",
    HELPER_SOURCES[2]: "55EBD4D0CF8C6E88E51F9F643A5E21ACE31ADE9AF45E0BBFE7FB0B54095BA782",
}

ROOT_INPUTS: Dict[str, Dict[str, Tuple[Path, str]]] = {
    "L": {
        "clevis": (RUN_ROOT / "01_native_parts/wing_root/LEFT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT", "AC60E3A07C84F21CF6E20D01533333345713EE3B28F9966BAAC4B452A4FCE673"),
        "pin": (RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_HINGE_PIN_V22_ISOLATED.SLDPRT", "97F6BE610F93605B098590A0C0CD157BE3C14A620B58976AA8A74FF00368733F"),
        "u_lug": (RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_PANEL_SIDE_U_LUG_NATIVE.SLDPRT", "5E8BDB76637B7F394560A95A938C3FF363DDAE88950E93266CFE66837ABCD749"),
        "retainer": (RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_HINGE_AXIAL_RETAINER_NATIVE.SLDPRT", "501BA210A1200E641922D696E27DC9E09A86320D454A0C214A0B57E941BF153A"),
    },
    "R": {
        "clevis": (RUN_ROOT / "01_native_parts/wing_root/RIGHT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT", "2D8121989230723A9D29C43672D8534D719D2AF7A64C110D0B0D16EAA31B1894"),
        "pin": (RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_HINGE_PIN_V22_ISOLATED.SLDPRT", "82E009F39F2320F53BC8651F7F4282898B0D2ABB4F62C8144A1EAC27B1014AC6"),
        "u_lug": (RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_PANEL_SIDE_U_LUG_NATIVE.SLDPRT", "A5A86890E07990706D106170B99DA0E68A31103EA73BF7161497669BCA4C557B"),
        "retainer": (RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_HINGE_AXIAL_RETAINER_NATIVE.SLDPRT", "94A9BB7CE3BD14B38E9664B824B2E970D930DA0145072F0A4FA4F7AF097442EC"),
    },
}
SHARED_SPACER = (
    RUN_ROOT / "01_native_parts/wing_root/WING_HINGE_AXIAL_SPACER.SLDPRT",
    "821B9484AB4B7B11A59A0136EDD4C537D37C317AC45830A5C1252ECD0A31577D",
)
SHARED_GROMMET = (
    RUN_ROOT / "01_native_parts/wing_root/WING_HARNESS_GROMMET.SLDPRT",
    "300A486B9E620A4301E9402577736BF0D71002C3F86499C6285E51A23AEAE4A4",
)
SHARED_STOP_PAD = (
    RUN_ROOT / "01_native_parts/wing_root/WING_MECHANICAL_STOP_PAD.SLDPRT",
    "F968A76B57987450814A02B260E654EA98E7E170449CD83DEAF7E7DDAEE2B445",
)
ROOT_ENVELOPE_INPUTS: Dict[str, Dict[str, Tuple[Path, str]]] = {
    "L": {
        "torsion_spring_1": (RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_TORSION_SPRING_1_V22_ISOLATED.SLDPRT", "EA364E7FBDFBA43635FCBF9F47D1E9DAC3DE9F6DED2F269FB0DE2F18790EDFE3"),
        "torsion_spring_2": (RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_TORSION_SPRING_2_V22_ISOLATED.SLDPRT", "3722582CED07A70FAE34798274B6897510033B9867EBD3E99F5FECC70B0B4E33"),
        "hard_stop": (RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_HARD_STOP_V22_ISOLATED.SLDPRT", "AEA6D3374539658894BABFA0F18E7507FD2F6D552A543DC29417CD31B232786C"),
        "harness_service_loop": (RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_HARNESS_SERVICE_LOOP_V22_ISOLATED.SLDPRT", "E652A34F87F12C920EF2CE90CBD7E58CBD7E8C082A4A9356E9AE9E6177321758"),
    },
    "R": {
        "torsion_spring_1": (RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_TORSION_SPRING_1_V22_ISOLATED.SLDPRT", "82F2E9EBD193D7EA39C6D48ED7D2E3818AA37B1C8D6CFFA94BE68BAA8BA2679C"),
        "torsion_spring_2": (RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_TORSION_SPRING_2_V22_ISOLATED.SLDPRT", "24DEFC92428657C0EC695C4FCA7A6DD49949FD1009C572B5CCFC4BF1214B6066"),
        "hard_stop": (RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_HARD_STOP_V22_ISOLATED.SLDPRT", "30C890D4E4D5C3A0BC850EA30C37CD1D9A0EEE0C7DF7B8A408DA99650A92FB54"),
        "harness_service_loop": (RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_HARNESS_SERVICE_LOOP_V22_ISOLATED.SLDPRT", "5884494BB30D49A515625D7D1F82980F8245341580DB13024EBC92B52F019D16"),
    },
}

CONFIGS: Tuple[str, ...] = (
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
)
ATTEMPT_RE = re.compile(r"^V5_SOLAR_R2B_BUILD_20\d{6}T\d{6}Z_[A-Z0-9]{4,16}$")
MUTEX_NAME = r"Local\F3R2_V5_SOLAR_R2B_A_BUILD_STAGE_V1"

SW_MATE_COINCIDENT = 0
SW_MATE_CONCENTRIC = 1
SW_MATE_ANGLE = 6
SW_MATE_LOCK = 16
SW_ALIGN_ALIGNED = 0
SW_ALIGN_CLOSEST = 2
SW_SET_VALUE_IN_SPECIFIC_CONFIGS = 3
SW_SET_VALUE_SUCCESS = 0
ANGLE_LOWER_RAD = 0.0
ANGLE_UPPER_RAD = math.pi / 2.0
ANGLE_CREATION_RAD = 0.0
TRANS_TOL_MM = 0.08
ROT_TOL_DEG = 0.15

PANEL_X_CENTER_MM = -61.0
INTERPANEL_X_CENTER_MM = -61.0
INTERPANEL_DEPTH_MM = 28.0
INTERPANEL_PIN_R_MM = 2.0
INTERPANEL_BORE_R_MM = 2.2
INTERPANEL_COLLAR_R_MM = 2.75

PRE_PATCH_FLIP_SIDES: Dict[str, Dict[str, bool]] = {
    "L": {"ROOT": True, "H12": False, "H23": True},
    "R": {"ROOT": False, "H12": True, "H23": False},
}
PRODUCTION_FLIP_SIDES: Dict[str, Dict[str, bool]] = {
    "L": {"ROOT": False, "H12": False, "H23": True},
    "R": {"ROOT": True, "H12": True, "H23": False},
}
SIGNED_FOLD_DIRECTION: Dict[str, Dict[str, int]] = {
    "L": {"ROOT": -1, "H12": +1, "H23": -1},
    "R": {"ROOT": +1, "H12": -1, "H23": +1},
}

FLIP_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2B_A_LIMIT_ANGLE_BRANCH_CONTRACT_V2",
    "selection_order": "PARENT_THEN_CHILD",
    "alignment": SW_ALIGN_ALIGNED,
    "alignment_name": "SW_ALIGN_ALIGNED",
    "interpanel_false_branch": "POSITIVE",
    "interpanel_true_branch": "NEGATIVE",
    "root_branch_semantics": "SIDE_SPECIFIC_ACCEPTED_CLEVIS_ENDPOINT_AUTHORIZATION",
    "sides": PRODUCTION_FLIP_SIDES,
    "evidence": {
        "interpanel_generic_probe": {
            "scope": "H12_H23_BRANCH_POLARITY_ONLY",
            "probe_script_sha256": "3680D614AD10728FC54309D4E8CFC64DB518FA3864989F86B968ED45E119FFE8",
            "probe_result_sha256": "52FF2A64E874FD782008E5971CB3154C976E10068C994337CB0611195E97A77A",
            "angles_deg": [1.0, 89.0, 90.0],
            "selection_order_in_probe": "ROOT_FIRST",
            "selected_case_count": 6,
        },
        "production_root_authorization": {
            "scope": "ROOT_ONLY_ACCEPTED_CLEVIS_TO_P1_MODULE",
            "authorization_receipt_sha256": EXPECTED_ROOT_FLIP_AUTHORIZATION_SHA256,
            "evidence_chain_sha256": EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256,
            "probe_source_sha256": "FBF3F0D53E3078D9E5A5B2CB0060A4EDBCC8BD7F01E6DE7B3C19F9A4ABD3F1D2",
            "probe_result_sha256": "18393CAC2423032AFF309361E37D5CE3612AA086C9EA5FD16D991EC2DF593DA0",
            "protocols": ["FULL_TABLE_LIKE", "PER_STATE_SUPPRESS_BEFORE_DIMENSION"],
            "angles_deg": [1.0, 89.0, 90.0],
            "case_count": 24,
            "winner_flips": {"L": False, "R": True},
        },
    },
}

MATE_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2B_A_3R_MATE_CONTRACT_V1",
    "hinges_per_side": 3,
    "each_hinge": ["CONCENTRIC", "COINCIDENT", "ADVANCED_LIMIT_ANGLE_0_TO_90_DEG"],
    "root": "ACCEPTED_U_LUG_TO_ACCEPTED_PIN_AND_SPACER",
    "interpanel": "OUTBOARD_PIN_TO_NEXT_MODULE_INBOARD_COLLAR",
    "module_internal": "PANEL_STRUCTURE_FIXED_PLUS_LOCK_MATE_FOR_EVERY_OTHER_CHILD",
    "configuration_owner": "SIDE_SLDASM_ONLY",
    "top_level_second_driver": "PROHIBITED",
    "angle_branch_contract": FLIP_CONTRACT,
}

ANNULUS_NATIVE_FEATURE_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2B_A_ANNULUS_NATIVE_FEATURE_CONTRACT_V1",
    "production_part_count": 4,
    "outer_radius_mm": INTERPANEL_COLLAR_R_MM,
    "bore_radius_mm": INTERPANEL_BORE_R_MM,
    "body_depth_mm": INTERPANEL_DEPTH_MM,
    "auxiliary_holes": "EMPTY_LIST_ONLY",
    "feature_sequence": [
        "FRONT_PLANE_SINGLE_OUTER_CIRCLE_FEATUREEXTRUSION2_BOSS",
        "POSITIVE_DEPTH_END_PLANE_SINGLE_INNER_CIRCLE_FEATURECUT3_OVERSHOOT",
    ],
    "cut_depth_multiplier": 2.0,
    "solid_body_count_after_outer_boss": 1,
    "solid_body_count_after_bore_cut": 1,
    "bore_brep": {
        "local_axis": "+/-Z",
        "axis_point_xy_mm": [0.0, 0.0],
        "candidate_count": 1,
        "radius_tolerance_mm": 0.06,
        "axis_point_tolerance_mm": 0.08,
        "axial_length_tolerance_mm": 0.12,
    },
}

ROOT_LUG_BORE_SELECTION_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2B_A_ROOT_LUG_BORE_SELECTION_CONTRACT_V1",
    "helper": "loop1b.cylinder_entity",
    "candidate_count": 2,
    "radius_mm": 4.2,
    "coaxial_axis": "+/-X",
    "axis_z_mm": 0.0,
    "candidate_order": "ASCENDING_CYLINDER_PARAMS_X_THEN_DESCENDING_FACE_AREA",
    "chosen_candidate": "FIRST_MINIMUM_WORLD_X",
    "chosen_axis_x_mm": -82.0,
    "chosen_face_axial_length_mm": 10.0,
    "coordinate_frame_at_mate_creation": "SIDE_ASSEMBLY_WORLD_WITH_NOMINAL_MODULE_IDENTITY",
    "tolerances_mm": {"axis_point": 0.06, "radius": 0.06, "axial_length": 0.12},
    "sides": {
        side: {
            "u_lug_path": ROOT_INPUTS[side]["u_lug"][0].relative_to(RUN_ROOT).as_posix(),
            "u_lug_sha256": ROOT_INPUTS[side]["u_lug"][1],
            "axis_y_mm": 143.15 if side == "L" else -143.15,
        }
        for side in ("L", "R")
    },
}

INTERPANEL_NESTED_BREP_FRAME_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2B_A_INTERPANEL_NESTED_BREP_FRAME_CONTRACT_V1",
    "scope": "L/R H12/H23 NESTED RIGID MODULE CHILDREN",
    "entity_signature_coordinate_frame": "NESTED_CHILD_PART_LOCAL",
    "cylinder": {
        "local_axis": "+/-Z",
        "local_axis_point_xy_mm": [0.0, 0.0],
        "candidate_count": 1,
        "pin_radius_mm": INTERPANEL_PIN_R_MM,
        "collar_bore_radius_mm": INTERPANEL_BORE_R_MM,
        "axial_length_mm": INTERPANEL_DEPTH_MM,
    },
    "axial_face": {"local_plane_z_mm": 0.0, "candidate_count": 1, "normal": "+/-Z"},
    "canonical_local_axis_points_mm": [[0.0, 0.0, 0.0], [0.0, 0.0, INTERPANEL_DEPTH_MM]],
    "nominal_world": {
        "local_z0_world_x_mm": -75.0,
        "local_z28_world_x_mm": -47.0,
        "axis_direction": "+/-X",
        "axis_z_mm": 0.0,
        "hinge_y_mm": {
            "L": {"H12": 199.81666666666666, "H23": 256.48333333333335},
            "R": {"H12": -199.81666666666666, "H23": -256.48333333333335},
        },
    },
    "world_continuity": "PIN_AND_COLLAR_CANONICAL_LOCAL_Z0_POINTS_COINCIDE_AND_AXES_ARE_COLLINEAR",
    "pose_stability": "UPSTREAM_AND_DOWNSTREAM_MODULE_TRANSFORMS_UNCHANGED_ACROSS_CONCENTRIC_AND_COINCIDENT_CREATION",
    "tolerances": {
        "local_axis_point_mm": 0.08,
        "radius_mm": 0.06,
        "axial_length_mm": 0.12,
        "world_point_mm": 0.08,
        "world_direction_cross_norm": 1.0e-6,
        "module_transform_max_abs": 2.0e-7,
    },
}

TRANSACTION_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2B_A_BUILD_TRANSACTION_V1",
    "cad_root": "13_validation/solar_r2_attempts/<storage_id>/cad",
    "storage_id": "attempt_id with the fixed V5_SOLAR_R2B_BUILD_ prefix removed; semantic attempt_id is preserved in every receipt",
    "write_policy": "EXCLUSIVE_CREATE_WRITE_ONCE_NO_RESUME_NO_OVERWRITE",
    "mutex": MUTEX_NAME,
    "build_process": "EXPLICIT_G0_BOUND_PID_ATTACH_ONLY",
    "same_pid_scope": "SANITY_ONLY_NO_RELEASE_CLAIM",
    "fresh_verifier": "DIFFERENT_PID_READ_ONLY_ZERO_MUTATION_REQUIRED",
    "promotion": "FORBIDDEN_IN_BUILD_STAGE",
    "failure": "PRESERVE_ATTEMPT_NO_DELETE",
}


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = detail or {}


class WindowsNamedMutex:
    """Single-writer guard; no filesystem lock is created outside the attempt."""

    ERROR_ALREADY_EXISTS = 183

    def __init__(self, name: str):
        self.name = name
        self.handle: Optional[int] = None

    def __enter__(self) -> "WindowsNamedMutex":
        if sys.platform != "win32":
            raise GateError("WINDOWS_MUTEX_PLATFORM_FAIL", "R2B native execution is Windows-only")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, True, self.name)
        error = ctypes.get_last_error()
        if not handle:
            raise GateError("NAMED_MUTEX_CREATE_FAIL", "CreateMutexW returned null", {"winerror": error, "name": self.name})
        self.handle = int(handle)
        if error == self.ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(ctypes.c_void_p(self.handle))
            self.handle = None
            raise GateError("NAMED_MUTEX_BUSY", "another R2B-A build owns the named mutex", {"name": self.name})
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.handle is None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.ReleaseMutex(ctypes.c_void_p(self.handle))
        kernel32.CloseHandle(ctypes.c_void_p(self.handle))
        self.handle = None


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


def file_fact(path: Path) -> Dict[str, Any]:
    return {"path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest().upper()


def write_json_once(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_text_once(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def require_under_attempt(path: Path, attempt_root: Path) -> None:
    if not under(path, attempt_root):
        raise GateError("ATTEMPT_PATH_ESCAPE", "new output escapes the unique attempt root", {"path": norm(path), "attempt_root": norm(attempt_root)})


def rx(degrees: float) -> List[List[float]]:
    angle = math.radians(float(degrees))
    c, s = math.cos(angle), math.sin(angle)
    return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]


def ry(degrees: float) -> List[List[float]]:
    angle = math.radians(float(degrees))
    c, s = math.cos(angle), math.sin(angle)
    return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]


def mat_mul(first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[sum(float(first[row][k]) * float(second[k][column]) for k in range(3)) for column in range(3)] for row in range(3)]


def mat_vec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> List[float]:
    return [sum(float(matrix[row][column]) * float(vector[column]) for column in range(3)) for row in range(3)]


def transpose(matrix: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[float(matrix[column][row]) for column in range(3)] for row in range(3)]


def add(first: Sequence[float], second: Sequence[float]) -> List[float]:
    return [float(first[index]) + float(second[index]) for index in range(3)]


def subtract(first: Sequence[float], second: Sequence[float]) -> List[float]:
    return [float(first[index]) - float(second[index]) for index in range(3)]


def frame(rotation: Sequence[Sequence[float]], translation_mm: Sequence[float]) -> Dict[str, Any]:
    return {"rotation": [[float(v) for v in row] for row in rotation], "translation_mm": [float(v) for v in translation_mm]}


def compose(first: Mapping[str, Any], second: Mapping[str, Any]) -> Dict[str, Any]:
    rotation = mat_mul(first["rotation"], second["rotation"])
    translation = add(first["translation_mm"], mat_vec(first["rotation"], second["translation_mm"]))
    return frame(rotation, translation)


def inverse_rigid(value: Mapping[str, Any]) -> Dict[str, Any]:
    rotation = transpose(value["rotation"])
    translation = mat_vec(rotation, [-float(v) for v in value["translation_mm"]])
    return frame(rotation, translation)


def mirror_frame_xz(value: Mapping[str, Any]) -> Dict[str, Any]:
    mirror = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]
    return frame(mat_mul(mat_mul(mirror, value["rotation"]), mirror), mat_vec(mirror, value["translation_mm"]))


def sw_transform(value: Mapping[str, Any]) -> List[float]:
    rotation = value["rotation"]
    translation = [float(v) / 1000.0 for v in value["translation_mm"]]
    return [
        rotation[0][0], rotation[1][0], rotation[2][0],
        rotation[0][1], rotation[1][1], rotation[2][1],
        rotation[0][2], rotation[1][2], rotation[2][2],
        translation[0], translation[1], translation[2],
        1.0, 0.0, 0.0, 0.0,
    ]


def frame_from_sw_transform(values: Sequence[float]) -> Dict[str, Any]:
    if len(values) != 16:
        raise ValueError("SOLIDWORKS transform must have 16 values")
    rotation = [[float(values[column * 3 + row]) for column in range(3)] for row in range(3)]
    translation = [float(values[index]) * 1000.0 for index in (9, 10, 11)]
    return frame(rotation, translation)


def transform_for_center(rotation: Sequence[Sequence[float]], desired_center_mm: Sequence[float], local_center_mm: Sequence[float]) -> List[float]:
    rotated = mat_vec(rotation, local_center_mm)
    translation = subtract(desired_center_mm, rotated)
    return sw_transform(frame(rotation, translation))


def transform_error(actual: Sequence[float], expected: Sequence[float]) -> Dict[str, float]:
    if len(actual) != 16 or len(expected) != 16:
        return {"translation_mm": float("inf"), "rotation_deg": float("inf")}
    translation = math.sqrt(sum((float(actual[index]) - float(expected[index])) ** 2 for index in (9, 10, 11))) * 1000.0
    ar = [[float(actual[column * 3 + row]) for column in range(3)] for row in range(3)]
    er = [[float(expected[column * 3 + row]) for column in range(3)] for row in range(3)]
    relative = mat_mul(transpose(er), ar)
    cosine = max(-1.0, min(1.0, (sum(relative[i][i] for i in range(3)) - 1.0) / 2.0))
    return {"translation_mm": translation, "rotation_deg": math.degrees(math.acos(cosine))}


def left_fk(angles_deg: Sequence[float], authority: Mapping[str, Any]) -> List[Dict[str, Any]]:
    if len(angles_deg) != 3 or any(float(value) not in (0.0, 90.0) for value in angles_deg):
        raise GateError("FK_INPUT_FAIL", "R2B-A build accepts exactly three frozen 0/90 anchors", {"angles": list(angles_deg)})
    a1, a2, a3 = (float(value) for value in angles_deg)
    phi = [a1 - 90.0, 0.0, 0.0]
    phi[1] = phi[0] + (90.0 - a2)
    phi[2] = phi[1] - (90.0 - a3)
    pitch = float(authority["candidate_geometry"]["panel_pitch_mm"])
    hinge = [-61.0, 143.15, 0.0]
    rows: List[Dict[str, Any]] = []
    for index, angle in enumerate(phi, start=1):
        rotation = rx(angle)
        outboard = add(hinge, mat_vec(rotation, [0.0, pitch, 0.0]))
        center = [(hinge[axis] + outboard[axis]) / 2.0 for axis in range(3)]
        rows.append({
            "panel_index": index,
            "logical_angle_deg": float(angles_deg[index - 1]),
            "native_absolute_rotation_deg": angle,
            "rotation": rotation,
            "center_mm": center,
            "inboard_hinge_mm": list(hinge),
            "outboard_hinge_mm": list(outboard) if index < 3 else None,
        })
        hinge = outboard
    return rows


def right_from_left(left_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    mirror = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]

    def point(value: Optional[Sequence[float]]) -> Optional[List[float]]:
        return None if value is None else mat_vec(mirror, value)

    rows: List[Dict[str, Any]] = []
    for source in left_rows:
        rows.append({
            **source,
            # Every RIGHT module is authored directly in mirrored spacecraft-
            # world nominal geometry.  Therefore its occurrence rotation is
            # the proper M*R*M conjugate and is identity at deployed nominal.
            "rotation": mat_mul(mat_mul(mirror, source["rotation"]), mirror),
            "center_mm": point(source["center_mm"]),
            "inboard_hinge_mm": point(source["inboard_hinge_mm"]),
            "outboard_hinge_mm": point(source["outboard_hinge_mm"]),
        })
    return rows


def side_fk(side: str, angles_deg: Sequence[float], authority: Mapping[str, Any]) -> List[Dict[str, Any]]:
    left = left_fk(angles_deg, authority)
    if side == "L":
        return left
    if side == "R":
        return right_from_left(left)
    raise GateError("SIDE_FAIL", "side must be L or R", {"side": side})


def module_delta(side: str, angles_deg: Sequence[float], panel_index: int, authority: Mapping[str, Any]) -> List[float]:
    # RIGHT is never independently parameterised: it is M * LEFT * M.
    left_state = left_fk(angles_deg, authority)[panel_index - 1]
    left_nominal = left_fk((90.0, 90.0, 90.0), authority)[panel_index - 1]
    delta_left = compose(
        frame(left_state["rotation"], left_state["inboard_hinge_mm"]),
        inverse_rigid(frame(left_nominal["rotation"], left_nominal["inboard_hinge_mm"])),
    )
    value = delta_left if side == "L" else mirror_frame_xz(delta_left)
    return sw_transform(value)


def part_key(side: str, index: int, role: str) -> str:
    return f"SOLAR_{side}{index}_{role}_R2B"


def part_specs(attempt_root: Path, authority: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    geometry = authority["candidate_geometry"]
    x_span = float(geometry["panel_x_span_mm"][1]) - float(geometry["panel_x_span_mm"][0])
    thickness = float(geometry["panel_thickness_mm"])
    edge = geometry["panel_structure_edge_contract"]
    ranges = {
        1: tuple(float(v) for v in edge["L1_main_plate_v_min_max_mm"]),
        2: tuple(float(v) for v in edge["L2_v_min_max_mm"]),
        3: tuple(float(v) for v in edge["L3_v_min_max_mm"]),
    }
    part_dir = attempt_root / "cad/parts"
    specs: Dict[str, Dict[str, Any]] = {}
    for side in ("L", "R"):
        for index in (1, 2, 3):
            common = {
                "SIDE": side,
                "PANEL_INDEX": str(index),
                "ARTIFACT_CLASS": "V5_R2B_A_COMPETITION_PROTOTYPE_CANDIDATE",
                "SOLAR_CELL_DETAIL": "PROHIBITED",
                "MASS_SOURCE": "EXTERNAL_MECHANICAL_ONLY",
                "L0_MASS_TRUTH_UPDATED": "FALSE",
                "FLIGHT_QUALIFICATION": "HOLD",
            }
            v_min, v_max = ranges[index]
            if index == 1:
                relief = geometry["p1_root_structure_relief"]
                tab_y_left = [
                    float(relief["bridge_tabs_world_y_span_left_mm"][0]) - float(geometry["deployed_panel_centroid_abs_y_mm"][0]),
                    float(relief["bridge_tabs_world_y_span_left_mm"][1]) - float(geometry["deployed_panel_centroid_abs_y_mm"][0]),
                ]
                tab_v = tab_y_left if side == "L" else [-tab_y_left[1], -tab_y_left[0]]
                main_v = [v_min, v_max] if side == "L" else [-v_max, -v_min]
                tab_x = [[float(a) - PANEL_X_CENTER_MM, float(b) - PANEL_X_CENTER_MM] for a, b in relief["bridge_tabs_world_x_spans_mm"]]
                panel_geometry = {
                    "kind": "p1_root_relief_plate",
                    "main_x_min_max_mm": [float(geometry["panel_x_span_mm"][0]) - PANEL_X_CENTER_MM, float(geometry["panel_x_span_mm"][1]) - PANEL_X_CENTER_MM],
                    "main_v_min_max_mm": main_v,
                    "bridge_tab_x_spans_mm": tab_x,
                    "bridge_tab_v_min_max_mm": tab_v,
                    "depth_mm": thickness,
                }
                panel_expected = sorted((x_span, max(main_v[1], tab_v[1]) - min(main_v[0], tab_v[0]), thickness))
                panel_local_center = [0.0, 0.0, thickness / 2.0]
                panel_function = "P1_ROOT_RELIEVED_MAIN_PLATE_WITH_TWIN_CLEVIS_GAP_BRIDGE_TABS"
            else:
                panel_geometry = {"kind": "box", "width_mm": x_span, "height_mm": v_max - v_min, "depth_mm": thickness}
                panel_expected = sorted((x_span, v_max - v_min, thickness))
                panel_local_center = [0.0, 0.0, thickness / 2.0]
                panel_function = "SIMPLIFIED_PANEL_STRUCTURE_WITH_INTERPANEL_EDGE_RELIEF"
            definitions = {
                "PANEL_STRUCTURE": (
                    panel_geometry,
                    panel_expected,
                    panel_local_center,
                    panel_function,
                ),
                "DEPLOY_STOP_IF": (
                    {"kind": "box", "width_mm": 16.0, "height_mm": 10.0, "depth_mm": 2.0},
                    sorted((16.0, 10.0, 2.0)), [0.0, 0.0, 1.0], "DEPLOYED_STOP_CONTACT_INTERFACE",
                ),
                "STOW_PAD_IF": (
                    {"kind": "box", "width_mm": 20.0, "height_mm": 6.0, "depth_mm": 3.0},
                    sorted((20.0, 6.0, 3.0)), [0.0, 0.0, 1.5], "STOW_CONTACT_INTERFACE",
                ),
                "HARNESS_EXIT_IF": (
                    {"kind": "box", "width_mm": 8.0, "height_mm": 8.0, "depth_mm": 4.0},
                    sorted((8.0, 8.0, 4.0)), [0.0, 0.0, 2.0], "HARNESS_EXIT_DATUM_PLACEHOLDER",
                ),
                "MASS_PLACEHOLDER_IF": (
                    {"kind": "box", "width_mm": 30.0, "height_mm": 12.0, "depth_mm": 2.0},
                    sorted((30.0, 12.0, 2.0)), [0.0, 0.0, 1.0], "EXTERNAL_MECHANICAL_MASS_INTERFACE_ONLY",
                ),
            }
            if index < 3:
                definitions["OUTBOARD_HINGE_PIN_IF"] = (
                    {"kind": "cylinder", "radius_mm": INTERPANEL_PIN_R_MM, "depth_mm": INTERPANEL_DEPTH_MM},
                    sorted((2.0 * INTERPANEL_PIN_R_MM, 2.0 * INTERPANEL_PIN_R_MM, INTERPANEL_DEPTH_MM)),
                    [0.0, 0.0, INTERPANEL_DEPTH_MM / 2.0], "OUTBOARD_HINGE_PIN_INTERFACE",
                )
            if index > 1:
                definitions["INBOARD_HINGE_COLLAR_IF"] = (
                    {"kind": "annulus_holes", "outer_r_mm": INTERPANEL_COLLAR_R_MM, "inner_r_mm": INTERPANEL_BORE_R_MM, "holes": [], "depth_mm": INTERPANEL_DEPTH_MM},
                    sorted((2.0 * INTERPANEL_COLLAR_R_MM, 2.0 * INTERPANEL_COLLAR_R_MM, INTERPANEL_DEPTH_MM)),
                    [0.0, 0.0, INTERPANEL_DEPTH_MM / 2.0], "INBOARD_HINGE_COLLAR_INTERFACE",
                )
            for role, (primitive, expected, local_center, function) in definitions.items():
                key = part_key(side, index, role)
                specs[key] = {
                    "target": part_dir / f"{key}.SLDPRT",
                    "geometry": primitive,
                    "expected_sorted_mm": expected,
                    "local_center_mm": local_center,
                    "properties": {**common, "FUNCTION": function, "BOM_ROW_REQUIRED": "TRUE"},
                }
    return specs


def module_paths(attempt_root: Path) -> Dict[Tuple[str, int], Path]:
    return {(side, index): attempt_root / "cad/modules" / f"SOLAR_PANEL_MODULE_{side}{index}_R2B.SLDASM" for side in ("L", "R") for index in (1, 2, 3)}


def side_paths(attempt_root: Path) -> Dict[str, Path]:
    return {side: attempt_root / "cad/sides" / f"{side}_SOLAR_ARRAY_R2B_SUCCESSOR.SLDASM" for side in ("L", "R")}


def module_part_keys(side: str, index: int) -> List[str]:
    roles = ["PANEL_STRUCTURE", "DEPLOY_STOP_IF", "STOW_PAD_IF", "HARNESS_EXIT_IF", "MASS_PLACEHOLDER_IF"]
    if index < 3:
        roles.append("OUTBOARD_HINGE_PIN_IF")
    if index > 1:
        roles.append("INBOARD_HINGE_COLLAR_IF")
    return [part_key(side, index, role) for role in roles]


def cad_targets(attempt_root: Path, authority: Mapping[str, Any]) -> List[Path]:
    return [Path(spec["target"]) for spec in part_specs(attempt_root, authority).values()] + list(module_paths(attempt_root).values()) + list(side_paths(attempt_root).values())


def nominal_part_transforms(side: str, index: int, authority: Mapping[str, Any], specs: Mapping[str, Mapping[str, Any]]) -> Dict[str, List[float]]:
    row = side_fk(side, (90.0, 90.0, 90.0), authority)[index - 1]
    rotation = row["rotation"]
    center = row["center_mm"]
    edge = authority["candidate_geometry"]["panel_structure_edge_contract"]
    edge_key = "L1_main_plate_v_min_max_mm" if index == 1 else f"L{index}_v_min_max_mm"
    v_min, v_max = (float(v) for v in edge[edge_key])
    if side == "R":
        v_min, v_max = -v_max, -v_min
    side_sign = 1.0 if side == "L" else -1.0
    local_positions = {
        # P1's custom sketch is already authored about the world-panel centre
        # with explicit root-relief coordinates; P2/P3 use centred rectangles
        # and therefore retain the edge-range midpoint placement.
        "PANEL_STRUCTURE": [0.0, 0.0 if index == 1 else (v_min + v_max) / 2.0, 0.0],
        "DEPLOY_STOP_IF": [82.0, 0.0, 4.0],
        "STOW_PAD_IF": [-70.0, 0.0, 4.5],
        "HARNESS_EXIT_IF": [101.0, side_sign * float(authority["candidate_geometry"]["panel_pitch_mm"]) * 0.20, 5.0],
        "MASS_PLACEHOLDER_IF": [0.0, -side_sign * float(authority["candidate_geometry"]["panel_pitch_mm"]) * 0.20, 4.0],
    }
    transforms: Dict[str, List[float]] = {}
    for role, offset in local_positions.items():
        key = part_key(side, index, role)
        desired = add(center, mat_vec(rotation, offset))
        transforms[key] = transform_for_center(rotation, desired, specs[key]["local_center_mm"])
    hinge_rotation = mat_mul(rotation, ry(90.0))
    if index < 3:
        key = part_key(side, index, "OUTBOARD_HINGE_PIN_IF")
        hinge = row["outboard_hinge_mm"]
        desired = [INTERPANEL_X_CENTER_MM, float(hinge[1]), float(hinge[2])]
        transforms[key] = transform_for_center(hinge_rotation, desired, specs[key]["local_center_mm"])
    if index > 1:
        key = part_key(side, index, "INBOARD_HINGE_COLLAR_IF")
        hinge = row["inboard_hinge_mm"]
        desired = [INTERPANEL_X_CENTER_MM, float(hinge[1]), float(hinge[2])]
        transforms[key] = transform_for_center(hinge_rotation, desired, specs[key]["local_center_mm"])
    return transforms


def production_root_flip_authorization_gate() -> Dict[str, Any]:
    """Validate the hash-sealed evidence bridge that authorizes only the two ROOT Flip changes."""
    if not PRODUCTION_ROOT_FLIP_AUTHORIZATION.is_file():
        raise GateError(
            "ROOT_FLIP_AUTHORIZATION_MISSING",
            "production ROOT Flip authorization receipt is missing",
            {"path": norm(PRODUCTION_ROOT_FLIP_AUTHORIZATION)},
        )
    receipt_fact = file_fact(PRODUCTION_ROOT_FLIP_AUTHORIZATION)
    if receipt_fact["sha256"] != EXPECTED_ROOT_FLIP_AUTHORIZATION_SHA256:
        raise GateError(
            "ROOT_FLIP_AUTHORIZATION_HASH_FAIL",
            "production ROOT Flip authorization receipt hash differs",
            {"expected": EXPECTED_ROOT_FLIP_AUTHORIZATION_SHA256, "actual": receipt_fact},
        )
    payload = json.loads(PRODUCTION_ROOT_FLIP_AUTHORIZATION.read_text(encoding="utf-8"))
    expected_patch = {
        "authorization_scope": "PRODUCTION_ROOT_LIMIT_ANGLE_FLIP_ONLY",
        "before": PRE_PATCH_FLIP_SIDES,
        "after": PRODUCTION_FLIP_SIDES,
        "changed_cells": [
            {"side": "L", "joint": "ROOT", "before": True, "after": False},
            {"side": "R", "joint": "ROOT", "before": False, "after": True},
        ],
        "unchanged_cells": [
            {"side": side, "joint": joint, "value": PRE_PATCH_FLIP_SIDES[side][joint]}
            for side in ("L", "R")
            for joint in ("H12", "H23")
        ],
    }
    authorized_patch = payload.get("authorized_patch", {})
    winner_summary = payload.get("production_root_probe_validation", {}).get("winner_summary", {})
    expected_winners = {
        side: {
            protocol: {
                "winner_flip": PRODUCTION_FLIP_SIDES[side]["ROOT"],
                "winner_flips": [PRODUCTION_FLIP_SIDES[side]["ROOT"]],
                "betas_deg": [1.0, 89.0, 90.0],
                "all_winner_cases_side_expected": True,
                "all_loser_cases_opposite_mirror": True,
            }
            for protocol in ("FULL_TABLE_LIKE", "PER_STATE_SUPPRESS_BEFORE_DIMENSION")
        }
        for side in ("L", "R")
    }
    lineage = payload.get("lineage", {})
    expected_lineage_facts = {
        "producer": file_fact(PRODUCTION_ROOT_FLIP_AUTHORIZER_SOURCE),
        "p5_failure_receipt": file_fact(P5_ROOT_BRANCH_FAILURE),
        "production_root_probe_source": file_fact(PRODUCTION_ROOT_BRANCH_PROBE_SOURCE),
        "production_root_probe_result": file_fact(PRODUCTION_ROOT_BRANCH_PROBE_RESULT),
        "state_authority": file_fact(STATE_AUTHORITY),
        "static_oracle": file_fact(STATIC_ORACLE),
    }
    lineage_checks = {label: lineage.get(label) == fact for label, fact in expected_lineage_facts.items()}
    pre_patch_builder = lineage.get("pre_patch_builder", {})
    lineage_checks.update({
        "pre_patch_builder": (
            isinstance(pre_patch_builder, dict)
            and pre_patch_builder.get("path") == norm(Path(__file__))
            and pre_patch_builder.get("sha256") == PRE_PATCH_BUILDER_SHA256
            and pre_patch_builder.get("bytes") == 152050
        ),
        "pre_patch_contract": lineage.get("pre_patch_contract_sha256") == PRE_PATCH_CONTRACT_SHA256,
        "probe_input_manifest": lineage.get("probe_input_manifest_sha256") == "13EE8094C8D2492185E770620CD2ADE15B7D10C058575390E649D789F3AE399A",
        "probe_case_semantics": lineage.get("probe_case_semantics_sha256") == "788354B55B10AFE2463C96978BDB59EB849261AD47A6FF3B1CC9FA089DF12C4A",
        "p5_cad_manifest": lineage.get("p5_cad_manifest_sha256") == "50E1D492599F882B488F53CE0D317D2219C96A98BCC76545A4B732F024CF0DF8",
    })
    claims = payload.get("claims", {})
    checks = {
        "schema": payload.get("schema") == "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_V1",
        "verdict": payload.get("verdict") == "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_PATCH_ONLY_AUTHORIZED",
        "classification": payload.get("classification") == "ENGINEERING_EVIDENCE_BRIDGE__PATCH_AUTHORIZATION_ONLY",
        "scope": payload.get("scope") == "V5_NATIVE_FINALIZATION/MULTI_PANEL_SOLAR_ARRAY_CANDIDATE/ROOT_LIMIT_ANGLE_BRANCH",
        "pre_patch_contract": (
            payload.get("pre_patch_flip_contract", {}).get("schema") == "F3R2_V5_SOLAR_R2B_A_LIMIT_ANGLE_BRANCH_CONTRACT_V1"
            and payload.get("pre_patch_flip_contract", {}).get("sides") == PRE_PATCH_FLIP_SIDES
        ),
        "patch_core": all(authorized_patch.get(key) == value for key, value in expected_patch.items()),
        "patch_policy": (
            authorized_patch.get("post_patch_build_required") is True
            and authorized_patch.get("different_pid_read_only_fresh_verification_required") is True
            and authorized_patch.get("promotion_authorized") is False
            and "H12_OR_H23_FLIP" in authorized_patch.get("prohibited_changes", [])
            and "DIMENSION_WRITE_OR_POSE_RESTORE_PROTOCOL" in authorized_patch.get("prohibited_changes", [])
        ),
        "winner_summary": winner_summary == expected_winners,
        "probe_case_count": payload.get("production_root_probe_validation", {}).get("factorial", {}).get("case_count") == 24,
        "probe_semantics": (
            payload.get("production_root_probe_validation", {}).get("all_driver_readbacks_exact") is True
            and payload.get("production_root_probe_validation", {}).get("all_angle_definitions_advanced_0_to_90") is True
            and payload.get("production_root_probe_validation", {}).get("all_final_mates_healthy_and_unsuppressed") is True
        ),
        "claims": (
            claims.get("solidworks_touched") is False
            and claims.get("cad_write_calls") == 0
            and claims.get("cad_files_mutated") == 0
            and claims.get("probe_history_modified") is False
            and claims.get("production_build_passed") is False
            and claims.get("fresh_pid_verified") is False
            and claims.get("promotion_authorized") is False
        ),
        "lineage": all(lineage_checks.values()),
    }
    digest_payload = {
        "lineage": lineage,
        "failure_signature": payload.get("p5_failure_lineage", {}).get("failure_signature"),
        "winner_summary": winner_summary,
        "authorized_patch": authorized_patch,
    }
    computed_digest = digest_json(digest_payload)
    checks["evidence_digest"] = (
        payload.get("evidence_chain_sha256") == EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256
        and computed_digest == EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256
    )
    if not all(checks.values()):
        raise GateError(
            "ROOT_FLIP_AUTHORIZATION_SEMANTICS_FAIL",
            "production ROOT Flip authorization receipt semantics or lineage differ",
            {"checks": checks, "lineage_checks": lineage_checks, "computed_digest": computed_digest},
        )
    return {
        "receipt": receipt_fact,
        "schema": payload["schema"],
        "verdict": payload["verdict"],
        "evidence_chain_sha256": payload["evidence_chain_sha256"],
        "authorized_patch": authorized_patch,
        "lineage": lineage,
        "winner_summary": winner_summary,
        "case_count": 24,
        "checks": checks,
    }


def branch_evidence_gate() -> Dict[str, Any]:
    """Bind generic interpanel polarity plus the accepted-clevis ROOT authorization."""
    payload = json.loads(BRANCH_PROBE_RESULT.read_text(encoding="utf-8"))
    if (
        payload.get("schema") != "F3R2_V5_SOLAR_R2B_ROOT_BRANCH_MATRIX_V1"
        or payload.get("verdict") != "V5_SOLAR_R2B_ROOT_BRANCH_MATRIX_COMPLETE"
        or payload.get("case_count_planned") != 24
        or payload.get("case_count_complete") != 24
        or not isinstance(payload.get("cases"), list)
        or len(payload["cases"]) != 24
    ):
        raise GateError(
            "ANGLE_BRANCH_EVIDENCE_GATE_FAIL",
            "root branch probe is not the complete frozen 24-case matrix",
            {"schema": payload.get("schema"), "verdict": payload.get("verdict")},
        )
    selected: List[Dict[str, Any]] = []
    required_negative_labels: List[str] = []
    for angle_deg in (1.0, 89.0, 90.0):
        for requested_flip in (False, True):
            matches = [
                row
                for row in payload["cases"]
                if isinstance(row, dict)
                and abs(float(row.get("angle_deg", math.inf)) - angle_deg) <= 1.0e-12
                and row.get("requested_alignment") == SW_ALIGN_ALIGNED
                and row.get("requested_flip") is requested_flip
                and row.get("swap_selection_order") is False
            ]
            if len(matches) != 1:
                raise GateError(
                    "ANGLE_BRANCH_EVIDENCE_CASE_FAIL",
                    "probe lacks one parent-first/aligned flip case",
                    {"angle_deg": angle_deg, "requested_flip": requested_flip, "matches": len(matches)},
                )
            row = matches[0]
            creation = row.get("creation", {})
            creation_readback = creation.get("readback_at_creation", {}) if isinstance(creation, dict) else {}
            final_readback = row.get("final_mate_readback", {})
            pose = row.get("pose_after_restore", {})
            signed_rx_deg = float(pose.get("signed_rx_deg", math.nan)) if isinstance(pose, dict) else math.nan
            expected_branch = "NEGATIVE_EXPECTED" if requested_flip else "POSITIVE_MIRROR"
            readbacks_match = (
                creation.get("selection_order") == "ROOT_FIRST"
                and creation.get("requested_alignment") == SW_ALIGN_ALIGNED
                and creation.get("requested_flip") is requested_flip
                and creation_readback.get("alignment") == SW_ALIGN_ALIGNED
                and creation_readback.get("flipped") is requested_flip
                and isinstance(final_readback, dict)
                and final_readback.get("alignment") == SW_ALIGN_ALIGNED
                and final_readback.get("flipped") is requested_flip
            )
            magnitude_matches = (
                math.isfinite(signed_rx_deg)
                and abs(abs(signed_rx_deg) - angle_deg) <= 2.0e-6
                and abs(float(row.get("driven_readback_rad", math.inf)) - math.radians(angle_deg)) <= 2.0e-9
                and abs(float(final_readback.get("angle_rad", math.inf)) - math.radians(angle_deg)) <= 2.0e-9
            )
            sign_matches = signed_rx_deg < 0.0 if requested_flip else signed_rx_deg > 0.0
            if (
                row.get("case_complete") is not True
                or row.get("restored_branch") != expected_branch
                or not readbacks_match
                or not magnitude_matches
                or not sign_matches
            ):
                raise GateError(
                    "ANGLE_BRANCH_EVIDENCE_SEMANTICS_FAIL",
                    "parent-first/aligned branch evidence differs from Flip=False positive / Flip=True negative",
                    {"case": row.get("label"), "expected_branch": expected_branch, "signed_rx_deg": signed_rx_deg},
                )
            if requested_flip:
                required_negative_labels.append(str(row.get("label")))
            selected.append({
                "label": str(row.get("label")),
                "angle_deg": angle_deg,
                "requested_alignment": SW_ALIGN_ALIGNED,
                "requested_flip": requested_flip,
                "selection_order": "PARENT_THEN_CHILD",
                "restored_branch": expected_branch,
                "signed_rx_deg": signed_rx_deg,
                "creation_readback": creation_readback,
                "final_readback": final_readback,
            })
    winners = payload.get("negative_branch_winners", [])
    if not isinstance(winners, list) or not set(required_negative_labels).issubset(set(winners)):
        raise GateError(
            "ANGLE_BRANCH_NEGATIVE_WINNER_FAIL",
            "required parent-first aligned Flip=True cases are absent from negative winners",
            {"required": required_negative_labels, "actual": winners},
        )
    generic_interpanel = {
        "scope": "H12_H23_BRANCH_POLARITY_ONLY",
        "probe_source": file_fact(BRANCH_PROBE_SOURCE),
        "probe_result": file_fact(BRANCH_PROBE_RESULT),
        "case_count_complete": 24,
        "selected_cases": selected,
        "selected_case_count": len(selected),
        "verdict": "V5_SOLAR_R2B_A_INTERPANEL_BRANCH_EVIDENCE_PASS",
    }
    root_authorization = production_root_flip_authorization_gate()
    return {
        "schema": "F3R2_V5_SOLAR_R2B_A_ANGLE_BRANCH_EVIDENCE_V2",
        "generic_interpanel_evidence": generic_interpanel,
        "production_root_authorization": root_authorization,
        "contract": FLIP_CONTRACT,
        "verdict": "V5_SOLAR_R2B_A_ANGLE_BRANCH_EVIDENCE_V2_PASS",
    }


def load_authority_bundle() -> Dict[str, Any]:
    facts: Dict[str, Any] = {}
    for label, path, expected in EXPECTED_BINDINGS:
        if not path.is_file():
            raise GateError("AUTHORITY_INPUT_MISSING", "required frozen input is missing", {"label": label, "path": norm(path)})
        actual = sha256(path)
        if actual != expected:
            raise GateError("AUTHORITY_HASH_DRIFT", "frozen input hash drift", {"label": label, "expected": expected, "actual": actual})
        facts[label] = file_fact(path)
    authority = json.loads(STATE_AUTHORITY.read_text(encoding="utf-8"))
    architecture = json.loads(ARCHITECTURE_DECISION.read_text(encoding="utf-8"))
    oracle = json.loads(STATIC_ORACLE.read_text(encoding="utf-8"))
    if authority.get("schema") != "F3R2_V5_SOLAR_STATE_AUTHORITY_R2B" or tuple(authority.get("states", {})) != CONFIGS:
        raise GateError("STATE_AUTHORITY_SCHEMA_FAIL", "R2B state schema/order drift")
    if architecture.get("status") != "V5_NATIVE_FINALIZATION_ARCHITECTURE_FROZEN_FOR_R2B_A_BUILD" or architecture.get("decision") != "PANEL_MODULE_RIGID_ARCHITECTURE":
        raise GateError("ARCHITECTURE_DECISION_FAIL", "R2B-A rigid-module architecture is not frozen")
    if architecture.get("kinematic_authority", {}).get("sha256") != facts["state_authority_r2b"]["sha256"]:
        raise GateError("ARCHITECTURE_AUTHORITY_BINDING_FAIL", "architecture does not bind current state authority")
    if architecture.get("static_oracle", {}).get("sha256") != facts["static_oracle_r2b"]["sha256"]:
        raise GateError("ARCHITECTURE_ORACLE_BINDING_FAIL", "architecture does not bind current static oracle")
    counts = architecture.get("new_native_artifacts_per_attempt", {})
    if (counts.get("solar_sldprt_count"), counts.get("panel_module_sldasm_count"), counts.get("side_sldasm_count")) != (38, 6, 2):
        raise GateError("ARCHITECTURE_COUNT_FAIL", "authority artifact counts are not 38/6/2", {"counts": counts})
    if oracle.get("verdict") != "V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_PASS" or oracle.get("gates", {}).get("state_count") != 7:
        raise GateError("STATIC_ORACLE_VERDICT_FAIL", "latest R2B-A static oracle is not PASS")
    oracle_inputs = {Path(row["path"]).name: row["sha256"] for row in oracle.get("inputs", [])}
    if oracle_inputs.get(STATE_AUTHORITY.name) != facts["state_authority_r2b"]["sha256"]:
        raise GateError("ORACLE_AUTHORITY_BINDING_FAIL", "static oracle does not bind the frozen R2B authority")
    branch_evidence = branch_evidence_gate()
    return {"authority": authority, "architecture": architecture, "oracle": oracle, "facts": facts, "branch_evidence": branch_evidence}


def g0_gate(receipt: Path, expected_sha256: str, expected_pid: int) -> Dict[str, Any]:
    if not receipt.is_file():
        raise GateError("G0_RECEIPT_MISSING", "explicit G0 Session-B receipt is missing", {"path": norm(receipt)})
    actual_sha = sha256(receipt)
    if actual_sha != expected_sha256.upper():
        raise GateError("G0_RECEIPT_HASH_FAIL", "explicit G0 receipt hash mismatch", {"expected": expected_sha256.upper(), "actual": actual_sha})
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    process = payload.get("session_b_process", {})
    checks = {
        "schema": payload.get("schema") == "F3R2_V5_G0_SMOKE_SESSION_B_V1",
        "verdict": payload.get("verdict") == "G0_SOLIDWORKS_NATIVE_EXECUTION_READY",
        "pid": int(process.get("pid", -1)) == int(expected_pid),
        "different_pid": process.get("different_pid_from_session_a") is True,
        "empty_pre": process.get("doc_count_pre") == 0 and process.get("active_doc_is_null_pre") is True,
        "read_only_cold": payload.get("cold_reopen", {}).get("open_options") == ["SILENT", "READ_ONLY"],
        "temporary_deleted": payload.get("temporary_asset", {}).get("deleted") is True,
        "attach_only": payload.get("safety", {}).get("attach_only") is True and payload.get("safety", {}).get("script_start_solidworks") is False,
    }
    if not all(checks.values()):
        raise GateError("G0_RECEIPT_SEMANTICS_FAIL", "G0 receipt does not authorise the explicit PID", {"checks": checks, "expected_pid": expected_pid})
    return {"receipt": file_fact(receipt), "session_b_process": process, "checks": checks}


def microfixture_gate(receipt: Path, expected_sha256: str) -> Dict[str, Any]:
    if not receipt.is_file():
        raise GateError("MICROFIXTURE_RECEIPT_MISSING", "exact R2B module-chain microfixture receipt is missing", {"path": norm(receipt)})
    actual_sha = sha256(receipt)
    if actual_sha != expected_sha256.upper():
        raise GateError("MICROFIXTURE_RECEIPT_HASH_FAIL", "explicit microfixture receipt hash mismatch", {"expected": expected_sha256.upper(), "actual": actual_sha})
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    bindings = dict((label, expected) for label, _path, expected in EXPECTED_BINDINGS)
    build_session = payload.get("build_session", {})
    verify_session = payload.get("verify_session", {})
    checks = {
        "schema": payload.get("schema") == "F3R2_V5_SOLAR_R2B_MODULE_CHAIN_MICROFIXTURE_RECEIPT_V1",
        "verdict": payload.get("verdict") == "V5_SOLAR_R2B_MODULE_CHAIN_FRESH_PID_READ_ONLY_PASS",
        "builder": payload.get("production_builder_sha256") == sha256(Path(__file__)),
        "authority": payload.get("authority_sha256") == bindings["state_authority_r2b"],
        "architecture": payload.get("architecture_sha256") == bindings["assembly_architecture"],
        "oracle": payload.get("oracle_sha256") == bindings["static_oracle_r2b"],
        "authorization": payload.get("authorization_sha256") == bindings["r2b_build_authorization"],
        "build_session": isinstance(build_session.get("pid"), int) and bool(build_session.get("create_time_utc")),
        "verify_session": isinstance(verify_session.get("pid"), int) and bool(verify_session.get("create_time_utc")),
        "different_pid_and_create_time": payload.get("different_pid_and_create_time") is True and build_session.get("pid") != verify_session.get("pid") and build_session.get("create_time_utc") != verify_session.get("create_time_utc"),
        "fresh_read_only": payload.get("fresh_pid_read_only") is True,
        "zero_mutation": payload.get("fresh_verifier_mutation_call_count") == 0,
        "counts": (payload.get("state_count"), payload.get("module_count"), payload.get("hinge_count"), payload.get("advanced_limit_angle_count")) == (7, 3, 3, 3),
        "zero_interference": payload.get("positive_volume_interference_count") == 0,
        "production_use_permitted": payload.get("production_use_permitted") is True,
    }
    if not all(checks.values()):
        raise GateError("MICROFIXTURE_SEMANTICS_FAIL", "microfixture does not prove the exact frozen builder/contract", {"checks": checks})
    return {"receipt": file_fact(receipt), "checks": checks, "build_session": build_session, "verify_session": verify_session}


def state_angles(authority: Mapping[str, Any], state: str, side: str) -> Tuple[float, float, float]:
    key = "LEFT" if side == "L" else "RIGHT"
    values = authority["states"][state][key]
    return tuple(float(value) for value in values)  # type: ignore[return-value]


def configuration_activation_semantics(show_return: bool, active_name: str, target: str) -> Dict[str, Any]:
    """Fail closed on active-name readback while accepting SW2024 no-op False."""
    fact = {
        "target_configuration": target,
        "show_configuration2_return": bool(show_return),
        "active_configuration_name": str(active_name),
        "noop_accepted": not bool(show_return) and str(active_name) == target,
    }
    if str(active_name) != target:
        raise GateError(
            "CONFIGURATION_ACTIVE_READBACK_FAIL",
            "active configuration differs from requested target",
            fact,
        )
    return fact


def active_configuration_name(model: Any, types: Any, pythoncom: Any) -> str:
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    return str(base.value(active, "Name"))


def show_configuration_fact(model: Any, target: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    show_return = bool(model.ShowConfiguration2(target))
    fact = configuration_activation_semantics(
        show_return,
        active_configuration_name(model, types, pythoncom),
        target,
    )
    rebuild_return = bool(model.ForceRebuild3(True))
    post_rebuild_active = active_configuration_name(model, types, pythoncom)
    fact.update({
        "force_rebuild3_return": rebuild_return,
        "post_rebuild_active_configuration_name": post_rebuild_active,
    })
    if not rebuild_return:
        raise GateError("CONFIGURATION_REBUILD_FAIL", "full rebuild failed after configuration activation", fact)
    if post_rebuild_active != target:
        raise GateError(
            "CONFIGURATION_POST_REBUILD_READBACK_FAIL",
            "active configuration changed during full rebuild",
            fact,
        )
    return fact


def contract_sha256() -> str:
    return digest_json({
        "authority_sha256": dict((label, expected) for label, _path, expected in EXPECTED_BINDINGS)["state_authority_r2b"],
        "architecture_sha256": dict((label, expected) for label, _path, expected in EXPECTED_BINDINGS)["assembly_architecture"],
        "oracle_sha256": dict((label, expected) for label, _path, expected in EXPECTED_BINDINGS)["static_oracle_r2b"],
        "production_root_flip_authorization_sha256": EXPECTED_ROOT_FLIP_AUTHORIZATION_SHA256,
        "production_root_flip_evidence_chain_sha256": EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256,
        "mate_contract": MATE_CONTRACT,
        "annulus_native_feature_contract": ANNULUS_NATIVE_FEATURE_CONTRACT,
        "root_lug_bore_selection_contract": ROOT_LUG_BORE_SELECTION_CONTRACT,
        "interpanel_nested_brep_frame_contract": INTERPANEL_NESTED_BREP_FRAME_CONTRACT,
        "transaction_contract": TRANSACTION_CONTRACT,
        "configs": CONFIGS,
    })


def selftest() -> Dict[str, Any]:
    failures: List[str] = []
    activation_semantics_tests: Dict[str, Any] = {}
    try:
        bundle = load_authority_bundle()
        authority, oracle = bundle["authority"], bundle["oracle"]
        expected_flips = PRODUCTION_FLIP_SIDES
        if (
            FLIP_CONTRACT.get("schema") != "F3R2_V5_SOLAR_R2B_A_LIMIT_ANGLE_BRANCH_CONTRACT_V2"
            or FLIP_CONTRACT.get("root_branch_semantics") != "SIDE_SPECIFIC_ACCEPTED_CLEVIS_ENDPOINT_AUTHORIZATION"
            or FLIP_CONTRACT.get("selection_order") != "PARENT_THEN_CHILD"
            or FLIP_CONTRACT.get("alignment") != SW_ALIGN_ALIGNED
            or FLIP_CONTRACT.get("sides") != expected_flips
            or SIGNED_FOLD_DIRECTION != {
                "L": {"ROOT": -1, "H12": +1, "H23": -1},
                "R": {"ROOT": +1, "H12": -1, "H23": +1},
            }
        ):
            failures.append("angle_flip_contract")
        branch_evidence = bundle.get("branch_evidence", {})
        if branch_evidence.get("generic_interpanel_evidence", {}).get("selected_case_count") != 6:
            failures.append("angle_branch_evidence_case_count")
        root_authorization = branch_evidence.get("production_root_authorization", {})
        if (
            root_authorization.get("case_count") != 24
            or root_authorization.get("evidence_chain_sha256") != EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256
            or root_authorization.get("authorized_patch", {}).get("after") != PRODUCTION_FLIP_SIDES
        ):
            failures.append("production_root_flip_authorization")
        synthetic = ATTEMPT_PARENT / "V5_SOLAR_R2B_BUILD_20991231T235959Z_SELFTEST"
        specs = part_specs(synthetic, authority)
        modules = module_paths(synthetic)
        sides = side_paths(synthetic)
        targets = cad_targets(synthetic, authority)
        if len(specs) != 38:
            failures.append(f"part_count={len(specs)}")
        annulus_specs = [spec for spec in specs.values() if spec.get("geometry", {}).get("kind") == "annulus_holes"]
        expected_annulus_geometry = {
            "kind": "annulus_holes",
            "outer_r_mm": INTERPANEL_COLLAR_R_MM,
            "inner_r_mm": INTERPANEL_BORE_R_MM,
            "holes": [],
            "depth_mm": INTERPANEL_DEPTH_MM,
        }
        if len(annulus_specs) != int(ANNULUS_NATIVE_FEATURE_CONTRACT["production_part_count"]) or any(spec.get("geometry") != expected_annulus_geometry for spec in annulus_specs):
            failures.append("annulus_part_count_or_geometry_contract")
        if (
            ANNULUS_NATIVE_FEATURE_CONTRACT.get("feature_sequence") != [
                "FRONT_PLANE_SINGLE_OUTER_CIRCLE_FEATUREEXTRUSION2_BOSS",
                "POSITIVE_DEPTH_END_PLANE_SINGLE_INNER_CIRCLE_FEATURECUT3_OVERSHOOT",
            ]
            or ANNULUS_NATIVE_FEATURE_CONTRACT.get("solid_body_count_after_outer_boss") != 1
            or ANNULUS_NATIVE_FEATURE_CONTRACT.get("solid_body_count_after_bore_cut") != 1
            or ANNULUS_NATIVE_FEATURE_CONTRACT.get("bore_brep", {}).get("candidate_count") != 1
        ):
            failures.append("annulus_native_feature_contract")
        if (
            ROOT_LUG_BORE_SELECTION_CONTRACT.get("candidate_count") != 2
            or ROOT_LUG_BORE_SELECTION_CONTRACT.get("chosen_candidate") != "FIRST_MINIMUM_WORLD_X"
            or ROOT_LUG_BORE_SELECTION_CONTRACT.get("chosen_axis_x_mm") != -82.0
            or {side: row.get("axis_y_mm") for side, row in ROOT_LUG_BORE_SELECTION_CONTRACT.get("sides", {}).items()} != {"L": 143.15, "R": -143.15}
            or {side: row.get("u_lug_sha256") for side, row in ROOT_LUG_BORE_SELECTION_CONTRACT.get("sides", {}).items()} != {side: ROOT_INPUTS[side]["u_lug"][1] for side in ("L", "R")}
        ):
            failures.append("root_lug_bore_selection_contract")
        if (
            INTERPANEL_NESTED_BREP_FRAME_CONTRACT.get("entity_signature_coordinate_frame") != "NESTED_CHILD_PART_LOCAL"
            or INTERPANEL_NESTED_BREP_FRAME_CONTRACT.get("cylinder", {}).get("local_axis") != "+/-Z"
            or INTERPANEL_NESTED_BREP_FRAME_CONTRACT.get("axial_face", {}).get("local_plane_z_mm") != 0.0
            or INTERPANEL_NESTED_BREP_FRAME_CONTRACT.get("canonical_local_axis_points_mm") != [[0.0, 0.0, 0.0], [0.0, 0.0, 28.0]]
            or INTERPANEL_NESTED_BREP_FRAME_CONTRACT.get("nominal_world", {}).get("local_z0_world_x_mm") != -75.0
            or INTERPANEL_NESTED_BREP_FRAME_CONTRACT.get("nominal_world", {}).get("local_z28_world_x_mm") != -47.0
            or INTERPANEL_NESTED_BREP_FRAME_CONTRACT.get("nominal_world", {}).get("hinge_y_mm") != {
                "L": {"H12": 199.81666666666666, "H23": 256.48333333333335},
                "R": {"H12": -199.81666666666666, "H23": -256.48333333333335},
            }
        ):
            failures.append("interpanel_nested_brep_frame_contract")
        if len(modules) != 6 or len(sides) != 2 or len(targets) != 46 or len(set(targets)) != 46:
            failures.append("native_output_count_or_uniqueness")
        if any(not under(path, synthetic) for path in targets):
            failures.append("attempt_path_escape")
        if [len(module_part_keys("L", index)) for index in (1, 2, 3)] != [6, 7, 6]:
            failures.append("module_part_partition")
        oracle_states = {row["state"]: row for row in oracle["states"]}
        max_oracle_error = 0.0
        max_mirror_error = 0.0
        for state in CONFIGS:
            for side, oracle_key in (("L", "left"), ("R", "right")):
                rows = side_fk(side, state_angles(authority, state, side), authority)
                wanted = oracle_states[state][oracle_key]["panels"]
                for actual, expected in zip(rows, wanted):
                    max_oracle_error = max(
                        max_oracle_error,
                        max(abs(a - b) for a, b in zip(actual["center_mm"], expected["center_mm"])),
                        max(abs(a - b) for ar, er in zip(actual["rotation"], expected["rotation_3x3"]) for a, b in zip(ar, er)),
                    )
            left = side_fk("L", state_angles(authority, state, "R"), authority)
            right = side_fk("R", state_angles(authority, state, "R"), authority)
            mirrored = right_from_left(left)
            for actual, expected in zip(right, mirrored):
                max_mirror_error = max(max_mirror_error, max(abs(a - b) for a, b in zip(actual["center_mm"], expected["center_mm"])))
        if max_oracle_error > 1.0e-9:
            failures.append(f"oracle_error={max_oracle_error}")
        if max_mirror_error > 1.0e-9:
            failures.append(f"mirror_error={max_mirror_error}")
        for side in ("L", "R"):
            for index in (1, 2, 3):
                delta = module_delta(side, (90.0, 90.0, 90.0), index, authority)
                expected = loop1b.transform_data((0.0, 0.0, 0.0))
                if max(abs(a - b) for a, b in zip(delta, expected)) > 1.0e-12:
                    failures.append(f"nominal_delta_{side}{index}")
        for index in (1, 2, 3):
            left_transforms = nominal_part_transforms("L", index, authority, specs)
            right_transforms = nominal_part_transforms("R", index, authority, specs)
            for left_key in module_part_keys("L", index):
                right_key = left_key.replace(f"SOLAR_L{index}_", f"SOLAR_R{index}_", 1)
                expected_right = sw_transform(mirror_frame_xz(frame_from_sw_transform(left_transforms[left_key])))
                actual_right = right_transforms[right_key]
                if max(abs(a - b) for a, b in zip(expected_right, actual_right)) > 1.0e-12:
                    failures.append(f"nominal_child_mirror_{left_key}")
        if state_angles(authority, "SOLAR_LEFT_FAIL", "L") != (0.0, 0.0, 0.0) or state_angles(authority, "SOLAR_LEFT_FAIL", "R") != (90.0, 90.0, 90.0):
            failures.append("left_fail_semantics")
        if state_angles(authority, "SOLAR_RIGHT_FAIL", "L") != (90.0, 90.0, 90.0) or state_angles(authority, "SOLAR_RIGHT_FAIL", "R") != (0.0, 0.0, 0.0):
            failures.append("right_fail_semantics")
        try:
            no_op = configuration_activation_semantics(False, "SOLAR_DEPLOYED_NOMINAL", "SOLAR_DEPLOYED_NOMINAL")
            activation_semantics_tests["false_with_active_target_pass"] = bool(no_op.get("noop_accepted"))
            if activation_semantics_tests["false_with_active_target_pass"] is not True:
                failures.append("configuration_noop_false_active_target")
        except Exception as exc:
            activation_semantics_tests["false_with_active_target_pass"] = False
            activation_semantics_tests["false_with_active_target_error"] = repr(exc)
            failures.append("configuration_noop_false_active_target")
        try:
            configuration_activation_semantics(True, "SOLAR_STOWED", "SOLAR_DEPLOYED_NOMINAL")
            activation_semantics_tests["true_with_wrong_active_fail"] = False
            failures.append("configuration_true_wrong_active_target")
        except GateError as exc:
            activation_semantics_tests["true_with_wrong_active_fail"] = exc.code == "CONFIGURATION_ACTIVE_READBACK_FAIL"
            if activation_semantics_tests["true_with_wrong_active_fail"] is not True:
                failures.append("configuration_true_wrong_active_target")
        source = Path(__file__).read_text(encoding="utf-8")
        forbidden_tokens = (
            "Dispatch" + "Ex(",
            "Dispatch" + "(",
            "Start" + "-Process",
            "." + "Quit(",
            "os." + "startfile",
        )
        forbidden = [token for token in forbidden_tokens if token in source]
        if forbidden:
            failures.append(f"forbidden_start_exit_tokens={forbidden}")
    except Exception as exc:
        failures.append(f"exception={exc!r}")
        max_oracle_error = max_mirror_error = float("inf")
    return {
        "schema": "F3R2_V5_SOLAR_R2B_A_BUILD_SELFTEST_V1",
        "builder": file_fact(Path(__file__)),
        "contract_sha256": contract_sha256(),
        "part_count": 38,
        "module_count": 6,
        "side_assembly_count": 2,
        "annulus_native_feature_contract": ANNULUS_NATIVE_FEATURE_CONTRACT,
        "root_lug_bore_selection_contract": ROOT_LUG_BORE_SELECTION_CONTRACT,
        "interpanel_nested_brep_frame_contract": INTERPANEL_NESTED_BREP_FRAME_CONTRACT,
        "production_root_flip_authorization": None if "root_authorization" not in locals() else root_authorization,
        "configuration_activation_semantics_tests": activation_semantics_tests,
        "max_oracle_error": max_oracle_error,
        "max_mirror_error": max_mirror_error,
        "failures": failures,
        "verdict": "V5_SOLAR_R2B_A_BUILD_SELFTEST_PASS" if not failures else "V5_SOLAR_R2B_A_BUILD_SELFTEST_FAIL",
    }


def root_input_checks() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for side in ("L", "R"):
        for role, (path, expected) in ROOT_INPUTS[side].items():
            actual = sha256(path) if path.is_file() else None
            rows.append({"label": f"root_{side}_{role}", "path": norm(path), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    path, expected = SHARED_SPACER
    actual = sha256(path) if path.is_file() else None
    rows.append({"label": "root_shared_spacer", "path": norm(path), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    for label, (path, expected) in (("root_shared_grommet", SHARED_GROMMET), ("root_shared_stop_pad", SHARED_STOP_PAD)):
        actual = sha256(path) if path.is_file() else None
        rows.append({"label": label, "path": norm(path), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    for side in ("L", "R"):
        for role, (path, expected) in ROOT_ENVELOPE_INPUTS[side].items():
            actual = sha256(path) if path.is_file() else None
            rows.append({"label": f"root_envelope_{side}_{role}", "path": norm(path), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    return rows


def allowed_external_reference_facts() -> List[Dict[str, Any]]:
    paths: List[Path] = [SHARED_SPACER[0], SHARED_GROMMET[0], SHARED_STOP_PAD[0]]
    for side in ("L", "R"):
        paths.extend(path for path, _sha in ROOT_INPUTS[side].values())
        paths.extend(path for path, _sha in ROOT_ENVELOPE_INPUTS[side].values())
    unique = sorted({path.resolve() for path in paths}, key=lambda item: norm(item))
    return [file_fact(path) for path in unique]


def static_audit(g0_receipt: Optional[Path] = None, g0_sha256: Optional[str] = None, expected_pid: Optional[int] = None, microfixture_receipt: Optional[Path] = None, microfixture_sha256: Optional[str] = None) -> Dict[str, Any]:
    errors: List[Dict[str, Any]] = []
    bundle: Optional[Dict[str, Any]] = None
    try:
        bundle = load_authority_bundle()
    except Exception as exc:
        errors.append({"gate": "authority_bundle", "error": str(exc), "detail": getattr(exc, "detail", {})})
    roots = root_input_checks()
    templates = []
    for label, path, expected in TEMPLATE_BINDINGS:
        actual = sha256(path) if path.is_file() else None
        templates.append({"label": label, "path": norm(path), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    helpers = []
    for path in HELPER_SOURCES:
        if not path.is_file():
            helpers.append({"path": norm(path), "missing": True, "pass": False})
            continue
        fact = file_fact(path)
        expected = HELPER_SHA256[path]
        helpers.append({**fact, "expected_sha256": expected, "pass": fact["sha256"] == expected})
    test = selftest()
    g0: Dict[str, Any] = {"provided": False, "required_for_execute": True}
    if g0_receipt is not None or g0_sha256 is not None or expected_pid is not None:
        if g0_receipt is None or g0_sha256 is None or expected_pid is None:
            errors.append({"gate": "g0", "error": "receipt, sha256 and expected PID must be supplied together"})
        else:
            try:
                g0 = {"provided": True, **g0_gate(g0_receipt, g0_sha256, expected_pid)}
            except Exception as exc:
                errors.append({"gate": "g0", "error": str(exc), "detail": getattr(exc, "detail", {})})
    microfixture: Dict[str, Any] = {"provided": False, "required_for_execute": True}
    if microfixture_receipt is not None or microfixture_sha256 is not None:
        if microfixture_receipt is None or microfixture_sha256 is None:
            errors.append({"gate": "microfixture", "error": "receipt and sha256 must be supplied together"})
        else:
            try:
                microfixture = {"provided": True, **microfixture_gate(microfixture_receipt, microfixture_sha256)}
            except Exception as exc:
                errors.append({"gate": "microfixture", "error": str(exc), "detail": getattr(exc, "detail", {})})
    static_ready = bundle is not None and all(row["pass"] for row in roots + templates + helpers) and test["verdict"].endswith("_PASS") and not errors
    execution_authorized = static_ready and g0.get("provided") is True and "receipt" in g0 and microfixture.get("provided") is True and "receipt" in microfixture
    return {
        "schema": "F3R2_V5_SOLAR_R2B_A_BUILD_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "builder": file_fact(Path(__file__)),
        "contract_sha256": contract_sha256(),
        "authority_bundle": None if bundle is None else bundle["facts"],
        "angle_branch_contract": FLIP_CONTRACT,
        "annulus_native_feature_contract": ANNULUS_NATIVE_FEATURE_CONTRACT,
        "root_lug_bore_selection_contract": ROOT_LUG_BORE_SELECTION_CONTRACT,
        "interpanel_nested_brep_frame_contract": INTERPANEL_NESTED_BREP_FRAME_CONTRACT,
        "angle_branch_evidence": None if bundle is None else bundle["branch_evidence"],
        "production_root_flip_authorization": None if bundle is None else bundle["branch_evidence"]["production_root_authorization"],
        "root_inputs": roots,
        "templates": templates,
        "helper_sources": helpers,
        "selftest": test,
        "g0": g0,
        "microfixture": microfixture,
        "transaction_contract": TRANSACTION_CONTRACT,
        "errors": errors,
        "static_ready": static_ready,
        "execution_authorized": execution_authorized,
        "verdict": "V5_SOLAR_R2B_A_BUILD_EXECUTION_READY" if execution_authorized else ("V5_SOLAR_R2B_A_BUILD_STATIC_READY_EXPECTING_EXPLICIT_SESSION" if static_ready else "V5_SOLAR_R2B_A_BUILD_HOLD"),
    }


def set_properties(model: Any, properties: Mapping[str, Any], attempt_id: str) -> None:
    manager = model.Extension.CustomPropertyManager("")
    common = {
        "Revision": "V5-R2B-A",
        "RUN_ID": attempt_id,
        "RELEASE_SCOPE": "COMPETITION_PROTOTYPE_BASELINE_CANDIDATE",
        "REPRESENTATION_LAYER": "V5_NATIVE_SOLAR_R2B_A",
        "EXISTING_CAD_MODIFIED": "FALSE",
        "L0_MASS_TRUTH_UPDATED": "FALSE",
        "FLIGHT_QUALIFICATION": "HOLD",
        "AuthoritySHA256": EXPECTED_BINDINGS[0][2],
        "ArchitectureSHA256": EXPECTED_BINDINGS[1][2],
        "StaticOracleSHA256": EXPECTED_BINDINGS[2][2],
        "BuildContractSHA256": contract_sha256(),
    }
    for name, value in {**common, **dict(properties)}.items():
        if int(manager.Add3(str(name), 30, str(value), 2)) < 0:
            raise GateError("CUSTOM_PROPERTY_FAIL", "cannot write native custom property", {"name": name, "value": value})


def part_cylinder_signature(
    model: Any,
    radius_mm: float,
    axial_length_mm: float,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    """Prove one local-Z cylindrical face and its full axial B-rep length."""
    part = loop1b.wrap(model, "IPartDoc", types, pythoncom)
    candidates: List[Tuple[float, List[float]]] = []
    for raw_body in loop1b.as_list(part.GetBodies2(0, False)):
        body = loop1b.wrap(raw_body, "IBody2", types, pythoncom)
        for raw_face in loop1b.as_list(loop1b.value(body, "GetFaces")):
            face = loop1b.wrap(raw_face, "IFace2", types, pythoncom)
            surface = loop1b.wrap(loop1b.value(face, "GetSurface"), "ISurface", types, pythoncom)
            if not bool(surface.IsCylinder()):
                continue
            params = [float(value) for value in loop1b.as_list(loop1b.value(surface, "CylinderParams"))]
            if (
                len(params) >= 7
                and abs(params[3]) < 1.0e-5
                and abs(params[4]) < 1.0e-5
                and abs(abs(params[5]) - 1.0) < 1.0e-5
                and abs(params[0] * 1000.0) <= float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["axis_point_tolerance_mm"])
                and abs(params[1] * 1000.0) <= float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["axis_point_tolerance_mm"])
                and abs(params[6] * 1000.0 - radius_mm) <= float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["radius_tolerance_mm"])
            ):
                candidates.append((float(loop1b.value(face, "GetArea")) * 1.0e6, params))
    if len(candidates) != int(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["candidate_count"]):
        raise GateError(
            "ANNULUS_BORE_BREP_COUNT_FAIL",
            "annulus does not expose exactly one local-Z bore cylindrical face",
            {"radius_mm": radius_mm, "axial_length_mm": axial_length_mm, "candidate_count": len(candidates)},
        )
    area_mm2, params = candidates[0]
    actual_radius_mm = float(params[6]) * 1000.0
    actual_axial_length_mm = area_mm2 / (2.0 * math.pi * actual_radius_mm)
    if abs(actual_axial_length_mm - axial_length_mm) > float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["axial_length_tolerance_mm"]):
        raise GateError(
            "ANNULUS_BORE_LENGTH_FAIL",
            "annulus bore cylindrical face does not span the full body depth",
            {"expected_mm": axial_length_mm, "actual_mm": actual_axial_length_mm, "area_mm2": area_mm2, "cylinder_params": params},
        )
    return {
        "local_axis": "+/-Z",
        "expected_radius_mm": radius_mm,
        "actual_radius_mm": actual_radius_mm,
        "expected_axial_length_mm": axial_length_mm,
        "actual_axial_length_mm": actual_axial_length_mm,
        "area_mm2": area_mm2,
        "candidate_count": 1,
        "cylinder_params": params,
    }


def create_native_primitive(model: Any, geometry: Mapping[str, Any], types: Any, pythoncom: Any) -> Dict[str, Any]:
    """Create the small production primitive set and its native B-rep witnesses."""
    kind = str(geometry.get("kind", ""))
    if kind not in {"p1_root_relief_plate", "annulus_holes"}:
        return loop1d.create_native_primitive(model, dict(geometry))
    if kind == "annulus_holes":
        outer_radius_mm = float(geometry["outer_r_mm"])
        inner_radius_mm = float(geometry["inner_r_mm"])
        depth_mm = float(geometry["depth_mm"])
        holes = geometry.get("holes")
        if (
            holes != []
            or not outer_radius_mm > inner_radius_mm > 0.0
            or depth_mm <= 0.0
            or abs(outer_radius_mm - INTERPANEL_COLLAR_R_MM) > 1.0e-9
            or abs(inner_radius_mm - INTERPANEL_BORE_R_MM) > 1.0e-9
            or abs(depth_mm - INTERPANEL_DEPTH_MM) > 1.0e-9
        ):
            raise GateError("ANNULUS_GEOMETRY_CONTRACT_FAIL", "production annulus geometry differs from the frozen collar contract", {"geometry": dict(geometry), "contract": ANNULUS_NATIVE_FEATURE_CONTRACT})

        outer_plane = loop1d.select_front_plane(model)
        sketch = model.SketchManager
        sketch.InsertSketch(True)
        loop1d.sketch_circle(sketch, 0.0, 0.0, outer_radius_mm)
        sketch.InsertSketch(True)
        outer_boss = model.FeatureManager.FeatureExtrusion2(
            True, False, False, 0, 0, depth_mm / 1000.0, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False, True, True, True,
            0, 0.0, False,
        )
        if outer_boss is None:
            raise GateError("ANNULUS_OUTER_BOSS_FAIL", "single-contour annulus outer FeatureExtrusion2 returned null", {"geometry": dict(geometry)})
        outer_boss.Name = "R2B_ANNULUS_OUTER_BOSS"
        body_after_outer = loop1b.body_facts(model, types, pythoncom)
        if body_after_outer.get("solid_body_count") != int(ANNULUS_NATIVE_FEATURE_CONTRACT["solid_body_count_after_outer_boss"]):
            raise GateError("ANNULUS_OUTER_BODY_COUNT_FAIL", "annulus outer boss is not exactly one solid body", {"body_facts": body_after_outer})

        bore_plane_name = "PLN_R2B_ANNULUS_BORE_EXIT"
        loop1b.create_offset_plane(model, ("前视基准面", "Front Plane"), depth_mm, bore_plane_name)
        if not bool(model.Extension.SelectByID2(bore_plane_name, "PLANE", 0.0, 0.0, 0.0, False, 0, None, 0)):
            raise GateError("ANNULUS_BORE_PLANE_FAIL", "cannot select the annulus positive-depth end plane")
        sketch.InsertSketch(True)
        loop1d.sketch_circle(sketch, 0.0, 0.0, inner_radius_mm)
        sketch.InsertSketch(True)
        cut_depth_mm = float(ANNULUS_NATIVE_FEATURE_CONTRACT["cut_depth_multiplier"]) * depth_mm
        bore_cut = model.FeatureManager.FeatureCut3(
            True, False, False, 0, 0, cut_depth_mm / 1000.0, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False, False, True, True, True, True,
            False, 0, 0.0, False,
        )
        if bore_cut is None:
            raise GateError("ANNULUS_BORE_CUT_FAIL", "end-plane annulus bore FeatureCut3 returned null", {"geometry": dict(geometry), "cut_depth_mm": cut_depth_mm})
        bore_cut.Name = "R2B_ANNULUS_BORE_THROUGH_CUT"
        body_after_cut = loop1b.body_facts(model, types, pythoncom)
        if body_after_cut.get("solid_body_count") != int(ANNULUS_NATIVE_FEATURE_CONTRACT["solid_body_count_after_bore_cut"]):
            raise GateError("ANNULUS_CUT_BODY_COUNT_FAIL", "annulus after bore cut is not exactly one solid body", {"body_facts": body_after_cut})
        bore_brep = part_cylinder_signature(model, inner_radius_mm, depth_mm, types, pythoncom)
        return {
            "plane_selection": outer_plane,
            "primitive": "annulus_holes",
            "depth_mm": depth_mm,
            "feature_api": ["FeatureExtrusion2", "FeatureCut3"],
            "feature_sequence": list(ANNULUS_NATIVE_FEATURE_CONTRACT["feature_sequence"]),
            "outer_boss": {"feature_name": "R2B_ANNULUS_OUTER_BOSS", "radius_mm": outer_radius_mm, "body_readback": body_after_outer},
            "bore_cut": {"feature_name": "R2B_ANNULUS_BORE_THROUGH_CUT", "radius_mm": inner_radius_mm, "cut_depth_mm": cut_depth_mm, "body_readback": body_after_cut},
            "bore_brep_readback": bore_brep,
            "annulus_native_feature_contract": ANNULUS_NATIVE_FEATURE_CONTRACT,
        }
    loop1d.select_front_plane(model)
    sketch = model.SketchManager
    sketch.InsertSketch(True)
    main_x = [float(v) for v in geometry["main_x_min_max_mm"]]
    main_v = [float(v) for v in geometry["main_v_min_max_mm"]]
    tab_v = [float(v) for v in geometry["bridge_tab_v_min_max_mm"]]
    tab_x = sorted(([float(a), float(b)] for a, b in geometry["bridge_tab_x_spans_mm"]), key=lambda row: row[0])
    if not (
        main_x[0] < main_x[1]
        and main_v[0] < main_v[1]
        and tab_v[0] < tab_v[1]
        and all(main_x[0] < a < b < main_x[1] for a, b in tab_x)
        and all(tab_x[index][1] < tab_x[index + 1][0] for index in range(len(tab_x) - 1))
        and min(main_v[1], tab_v[1]) > max(main_v[0], tab_v[0])
    ):
        raise GateError("P1_RELIEF_PROFILE_CONTRACT_FAIL", "P1 main plate and bridge-tab union is not one connected, non-degenerate profile", {"geometry": dict(geometry)})

    # Author one non-self-intersecting outer boundary.  Three overlapping
    # rectangles in one sketch are deliberately prohibited: SOLIDWORKS can
    # interpret their 0.05 mm overlap as ambiguous contours.  The LEFT tabs
    # extend below the main plate and the mirrored RIGHT tabs extend above it.
    if (tab_v[0] + tab_v[1]) < (main_v[0] + main_v[1]):
        interface_v, extreme_v = main_v[0], tab_v[0]
        points: List[Tuple[float, float]] = [(main_x[0], interface_v)]
        for x_min, x_max in tab_x:
            points.extend(((x_min, interface_v), (x_min, extreme_v), (x_max, extreme_v), (x_max, interface_v)))
        points.extend(((main_x[1], interface_v), (main_x[1], main_v[1]), (main_x[0], main_v[1])))
    else:
        interface_v, extreme_v = main_v[1], tab_v[1]
        points = [(main_x[0], main_v[0]), (main_x[1], main_v[0]), (main_x[1], interface_v)]
        for x_min, x_max in reversed(tab_x):
            points.extend(((x_max, interface_v), (x_max, extreme_v), (x_min, extreme_v), (x_min, interface_v)))
        points.append((main_x[0], interface_v))
    points.append(points[0])
    for first, second in zip(points[:-1], points[1:]):
        segment = sketch.CreateLine(first[0] / 1000.0, first[1] / 1000.0, 0.0, second[0] / 1000.0, second[1] / 1000.0, 0.0)
        if segment is None:
            raise GateError("P1_RELIEF_SKETCH_LINE_FAIL", "P1 relief union boundary line creation returned null", {"first_mm": first, "second_mm": second})
    sketch.InsertSketch(True)
    feature = model.FeatureManager.FeatureExtrusion2(
        True, False, False, 0, 0, float(geometry["depth_mm"]) / 1000.0, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, True, True,
        0, 0.0, False,
    )
    if feature is None:
        raise GateError("P1_RELIEF_EXTRUSION_FAIL", "P1 relief/twin-tab FeatureExtrusion2 returned null", {"geometry": dict(geometry)})
    return {
        "plane_selection": "FRONT_PLANE",
        "primitive": "p1_root_relief_plate",
        "depth_mm": float(geometry["depth_mm"]),
        "feature_api": "FeatureExtrusion2",
        "profile": {
            "main_x_min_max_mm": main_x,
            "main_v_min_max_mm": main_v,
            "bridge_tab_x_spans_mm": tab_x,
            "bridge_tab_v_min_max_mm": tab_v,
            "profile_topology": "SINGLE_NON_SELF_INTERSECTING_UNION_OUTER_BOUNDARY",
            "boundary_points_mm": points,
        },
    }


def make_transform(sw: Any, values: Sequence[float], types: Any, pythoncom: Any) -> Any:
    from win32com.client import VARIANT
    utility = base.wrap(base.value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
    result = utility.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in values]))
    if result is None:
        raise GateError("CREATE_TRANSFORM_FAIL", "IMathUtility.CreateTransform returned null")
    return result


def insert_component_transform(sw: Any, model: Any, assembly: Any, path: Path, transform16: Sequence[float], fixed: bool, types: Any, pythoncom: Any) -> Any:
    doc_type = loop1b.SW_ASSEMBLY if path.suffix.upper() == ".SLDASM" else loop1b.SW_PART
    opened_model = None
    title = str(base.value(model, "GetTitle"))
    try:
        opened_model, _ = loop1b.open_doc(sw, path, doc_type, True, types, pythoncom)
        loop1b.activate(sw, title)
        raw = assembly.AddComponent5(str(path), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw is None:
            raise GateError("ADD_COMPONENT_FAIL", "AddComponent5 returned null", {"path": norm(path)})
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        if not bool(component.SetTransformAndSolve3(make_transform(sw, transform16, types, pythoncom), True)):
            raise GateError("COMPONENT_INITIAL_TRANSFORM_FAIL", "cannot apply exact occurrence transform", {"path": norm(path)})
        model.ClearSelection2(True)
        if not bool(component.Select4(False, None, False)):
            raise GateError("COMPONENT_SELECT_FAIL", "cannot select inserted occurrence", {"path": norm(path)})
        assembly.FixComponent() if fixed else assembly.UnfixComponent()
        model.ClearSelection2(True)
        if bool(base.value(component, "IsFixed")) != bool(fixed):
            raise GateError("COMPONENT_FIXED_STATE_FAIL", "fixed-state readback differs", {"path": norm(path), "expected": fixed})
        return component
    finally:
        loop1b.close_doc(sw, opened_model)
        loop1b.activate(sw, title)


def build_part(sw: Any, key: str, spec: Mapping[str, Any], attempt_root: Path, attempt_id: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    target = Path(spec["target"])
    require_under_attempt(target, attempt_root)
    if target.exists():
        raise GateError("PART_TARGET_EXISTS", "write-once attempt part exists", {"target": norm(target)})
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = sw.NewDocument(str(PART_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = base.value(sw, "ActiveDoc")
    if raw is None:
        raise GateError("PART_NEW_DOCUMENT_FAIL", "cannot create native part", {"key": key})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    original_title = str(base.value(model, "GetTitle"))
    try:
        primitive = create_native_primitive(model, dict(spec["geometry"]), types, pythoncom)
        body_readback = loop1b.body_facts(model, types, pythoncom)
        if body_readback.get("solid_body_count") != 1:
            raise GateError(
                "PART_SOLID_BODY_COUNT_FAIL",
                "new native solar part must contain exactly one solid body before save",
                {"key": key, "geometry": dict(spec["geometry"]), "body_readback": body_readback},
            )
        set_properties(model, {
            "PartNumber": f"SEI-MECH-V5-{key}",
            "Description": key.replace("_", " "),
            "MaterialSpecification": "CANDIDATE_NOT_RELEASED",
            **dict(spec["properties"]),
        }, attempt_id)
        saved = base.save_native_part(model, target)
        if Path(str(base.value(model, "GetPathName"))).resolve() != target.resolve():
            raise GateError("PART_SAVE_PATH_FAIL", "part save path readback differs", {"target": norm(target)})
    finally:
        try:
            sw.CloseDoc(str(base.value(model, "GetTitle")))
        except Exception:
            sw.CloseDoc(original_title)
    if not target.is_file():
        raise GateError("PART_FILE_MISSING", "saved part is absent", {"target": norm(target)})
    return {
        "key": key,
        "target": file_fact(target),
        "geometry_contract": dict(spec["geometry"]),
        "expected_sorted_mm": [float(value) for value in spec["expected_sorted_mm"]],
        "primitive": primitive,
        "body_readback_before_save": body_readback,
        "bore_brep_readback_before_save": primitive.get("bore_brep_readback") if dict(spec["geometry"]).get("kind") == "annulus_holes" else None,
        "save": saved,
        "same_pid_scope": "SAVE_PATH_AND_FILE_FACT_SANITY_ONLY",
    }


def mate_feature_map(model: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    rows: Dict[str, Any] = {}
    raw = base.value(model, "FirstFeature")
    for _ in range(10000):
        if raw is None:
            return rows
        feature = base.wrap(raw, "IFeature", types, pythoncom)
        if str(base.value(feature, "GetTypeName2")) == "MateGroup":
            sub = base.value(feature, "GetFirstSubFeature")
            for _sub in range(10000):
                if sub is None:
                    break
                typed = base.wrap(sub, "IFeature", types, pythoncom)
                name = str(base.value(typed, "Name"))
                if name in rows:
                    raise GateError("MATE_NAME_COLLISION", "duplicate mate feature name", {"name": name})
                rows[name] = typed
                sub = base.value(typed, "GetNextSubFeature")
            else:
                raise GateError("MATE_SUBFEATURE_LIMIT", "mate subfeature traversal exceeded guard")
        raw = base.value(feature, "GetNextFeature")
    raise GateError("MATE_FEATURE_LIMIT", "feature traversal exceeded guard")


def rename_mate(model: Any, old_name: str, new_name: str, types: Any, pythoncom: Any) -> Any:
    before = mate_feature_map(model, types, pythoncom)
    if old_name not in before or new_name in before:
        raise GateError("MATE_RENAME_PRECONDITION_FAIL", "mate rename is not unique", {"old": old_name, "new": new_name})
    before[old_name].Name = new_name
    after = mate_feature_map(model, types, pythoncom)
    if old_name in after or new_name not in after:
        raise GateError("MATE_RENAME_FAIL", "mate deterministic name did not persist", {"old": old_name, "new": new_name})
    return after[new_name]


def add_named_entity_mate(model: Any, assembly: Any, first: Any, second: Any, mate_type: int, components: Sequence[Any], name: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    result = loop1b.add_entity_mate(model, assembly, first, second, mate_type, SW_ALIGN_CLOSEST, components, types, pythoncom)
    rename_mate(model, result["feature_name"], name, types, pythoncom)
    return {**result, "feature_name": name}


def component_ref_plane(component: Any, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    planes: List[Any] = []
    raw = base.value(component, "FirstFeature")
    for _ in range(10000):
        if raw is None:
            break
        feature = base.wrap(raw, "IFeature", types, pythoncom)
        if str(base.value(feature, "GetTypeName2")) == "RefPlane":
            planes.append(feature)
        raw = base.value(feature, "GetNextFeature")
    else:
        raise GateError("COMPONENT_FEATURE_LIMIT", "component feature traversal exceeded guard")
    names = {"Top Plane", "上视基准面"}
    named = [feature for feature in planes if str(base.value(feature, "Name")) in names]
    candidates = named or (planes[1:2] if len(planes) >= 2 else [])
    if len(candidates) != 1:
        raise GateError("ANGLE_PLANE_CARDINALITY_FAIL", "cannot resolve one module Top plane", {"component": str(base.value(component, "Name2")), "planes": [str(base.value(p, "Name")) for p in planes]})
    return candidates[0], {"component": str(base.value(component, "Name2")), "selected": str(base.value(candidates[0], "Name"))}


def angle_flip_readback(mate: Any, definition: Any) -> Dict[str, Any]:
    values: Dict[str, bool] = {}
    errors: Dict[str, str] = {}
    for label, obj, member in (
        ("IMate2.Flipped", mate, "Flipped"),
        ("IAngleMateFeatureData.FlipDimension", definition, "FlipDimension"),
    ):
        try:
            values[label] = bool(base.value(obj, member))
        except Exception as exc:
            errors[label] = repr(exc)
    if not values:
        raise GateError(
            "ANGLE_FLIP_READBACK_UNAVAILABLE",
            "neither IMate2.Flipped nor IAngleMateFeatureData.FlipDimension is readable",
            {"errors": errors},
        )
    if len(set(values.values())) != 1:
        raise GateError(
            "ANGLE_FLIP_READBACK_DISAGREEMENT",
            "IMate2 and angle-definition flip readbacks disagree",
            {"values": values, "errors": errors},
        )
    normalized = next(iter(values.values()))
    return {"flipped": normalized, "sources": values, "unavailable_sources": errors}


def angle_mate_fact(feature: Any, expected_flip: bool, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_mate = base.value(feature, "GetSpecificFeature2")
    raw_definition = base.value(feature, "GetDefinition")
    if raw_mate is None or raw_definition is None:
        raise GateError("ANGLE_MATE_OBJECT_NULL", "limit-angle feature has no mate/definition")
    mate = base.wrap(raw_mate, "IMate2", types, pythoncom)
    definition = base.wrap(raw_definition, "IAngleMateFeatureData", types, pythoncom)
    flip = angle_flip_readback(mate, definition)
    fact = {
        "feature_name": str(base.value(feature, "Name")),
        "mate_type": int(base.value(mate, "Type")),
        "alignment": int(base.value(mate, "Alignment")),
        "flipped": flip["flipped"],
        "flip_readback": flip,
        "expected_alignment": SW_ALIGN_ALIGNED,
        "expected_flip": bool(expected_flip),
        "advanced": bool(base.value(definition, "IsAdvancedMate")),
        "minimum_angle_rad": float(base.value(definition, "MinimumAngle")),
        "maximum_angle_rad": float(base.value(definition, "MaximumAngle")),
        "angle_rad": float(base.value(definition, "Angle")),
        "feature_health": loop1b.feature_error_state(feature),
    }
    if fact["mate_type"] != SW_MATE_ANGLE or fact["alignment"] != SW_ALIGN_ALIGNED or fact["flipped"] is not bool(expected_flip) or not fact["advanced"] or abs(fact["minimum_angle_rad"] - ANGLE_LOWER_RAD) > 1.0e-9 or abs(fact["maximum_angle_rad"] - ANGLE_UPPER_RAD) > 1.0e-9 or fact["feature_health"]["feature_error_code"] != 0 or fact["feature_health"]["suppressed"]:
        raise GateError("ADVANCED_LIMIT_ANGLE_READBACK_FAIL", "native limit angle differs from 0..90 contract", fact)
    return fact


def angle_mate_dimension(feature: Any, types: Any, pythoncom: Any) -> Any:
    raw_mate = base.value(feature, "GetSpecificFeature2")
    if raw_mate is None:
        raise GateError("ANGLE_MATE_NULL", "angle mate feature has no IMate2", {"feature": str(base.value(feature, "Name"))})
    mate = base.wrap(raw_mate, "IMate2", types, pythoncom)
    raw_display = mate.DisplayDimension2(0)
    if raw_display is None:
        raise GateError("ANGLE_DISPLAY_DIMENSION_NULL", "angle mate has no DisplayDimension2(0)", {"feature": str(base.value(feature, "Name"))})
    display = base.wrap(raw_display, "IDisplayDimension", types, pythoncom)
    raw_dimension = display.GetDimension2(0)
    if raw_dimension is None:
        raise GateError("ANGLE_DIMENSION_NULL", "angle mate display has no IDimension", {"feature": str(base.value(feature, "Name"))})
    return base.wrap(raw_dimension, "IDimension", types, pythoncom)


def add_named_limit_angle(model: Any, assembly: Any, first_component: Any, second_component: Any, name: str, expected_flip: bool, types: Any, pythoncom: Any) -> Dict[str, Any]:
    before = loop1b.mate_ledger(model, types, pythoncom)
    first_plane, first_fact = component_ref_plane(first_component, types, pythoncom)
    second_plane, second_fact = component_ref_plane(second_component, types, pythoncom)
    model.ClearSelection2(True)
    if not bool(first_plane.Select2(False, 1)) or not bool(second_plane.Select2(True, 1)):
        raise GateError("ANGLE_PLANE_SELECTION_FAIL", "cannot select both angle planes", {"name": name})
    manager = loop1b.selection_manager(model, types, pythoncom)
    selected = int(manager.GetSelectedObjectCount2(1))
    returned = assembly.AddMate3(SW_MATE_ANGLE, SW_ALIGN_ALIGNED, bool(expected_flip), 0.0, 0.0, 0.0, 0.0, 0.0, ANGLE_CREATION_RAD, ANGLE_UPPER_RAD, ANGLE_LOWER_RAD, False, 0)
    model.ClearSelection2(True)
    created = loop1b.resolve_created_mate(model, returned, before, SW_MATE_ANGLE, SW_ALIGN_ALIGNED, (first_component, second_component), selected, types, pythoncom)
    feature = rename_mate(model, created["feature_name"], name, types, pythoncom)
    return {
        **created,
        "feature_name": name,
        "first_plane": first_fact,
        "second_plane": second_fact,
        "branch_contract": {
            "selection_order": "PARENT_THEN_CHILD",
            "requested_alignment": SW_ALIGN_ALIGNED,
            "requested_flip": bool(expected_flip),
        },
        "readback": angle_mate_fact(feature, expected_flip, types, pythoncom),
        "creation_api": "IAssemblyDoc.AddMate3",
    }


def add_named_lock(model: Any, assembly: Any, first: Any, second: Any, name: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    result = loop1b.add_lock_mate(model, assembly, first, second, types, pythoncom)
    rename_mate(model, result["feature_name"], name, types, pythoncom)
    return {**result, "feature_name": name}


def reference_path_set(model: Any, types: Any, pythoncom: Any) -> Tuple[List[Dict[str, Any]], set[Path]]:
    ledger = loop1b.component_reference_ledger(model, types, pythoncom)
    paths = {Path(row["path"]).resolve() for row in ledger}
    return ledger, paths


def build_module(sw: Any, side: str, index: int, attempt_root: Path, attempt_id: str, authority: Mapping[str, Any], specs: Mapping[str, Mapping[str, Any]], types: Any, pythoncom: Any) -> Dict[str, Any]:
    target = module_paths(attempt_root)[(side, index)]
    require_under_attempt(target, attempt_root)
    if target.exists():
        raise GateError("MODULE_TARGET_EXISTS", "write-once module exists", {"target": norm(target)})
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = sw.NewDocument(str(ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = base.value(sw, "ActiveDoc")
    if raw is None:
        raise GateError("MODULE_NEW_DOCUMENT_FAIL", "cannot create module", {"side": side, "index": index})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    try:
        transforms = nominal_part_transforms(side, index, authority, specs)
        components: Dict[str, Any] = {}
        panel_key = part_key(side, index, "PANEL_STRUCTURE")
        for key in module_part_keys(side, index):
            components[key] = insert_component_transform(sw, model, assembly, Path(specs[key]["target"]), transforms[key], key == panel_key, types, pythoncom)
        if index == 1:
            lug_path = ROOT_INPUTS[side]["u_lug"][0]
            components["ACCEPTED_SIDE_U_LUG"] = insert_component_transform(sw, model, assembly, lug_path, loop1b.transform_data((0.0, 0.0, 0.0)), False, types, pythoncom)
        locks: List[Dict[str, Any]] = []
        for key, component in components.items():
            if key == panel_key:
                continue
            locks.append(add_named_lock(model, assembly, components[panel_key], component, f"R2B_{side}{index}_RIGID_{key}", types, pythoncom))
        if not bool(model.ForceRebuild3(True)):
            raise GateError("MODULE_REBUILD_FAIL", "module rebuild failed", {"side": side, "index": index})
        ledger = loop1b.mate_ledger(model, types, pythoncom)
        if len(ledger) != len(components) - 1 or Counter(row["mate_type"] for row in ledger) != Counter({SW_MATE_LOCK: len(components) - 1}):
            raise GateError("MODULE_RIGID_MATE_SET_FAIL", "module is not fully lock-constrained", {"side": side, "index": index, "mate_ledger": ledger})
        references, actual_paths = reference_path_set(model, types, pythoncom)
        expected_paths = {Path(specs[key]["target"]).resolve() for key in module_part_keys(side, index)}
        if index == 1:
            expected_paths.add(ROOT_INPUTS[side]["u_lug"][0].resolve())
        if actual_paths != expected_paths:
            raise GateError("MODULE_REFERENCE_SET_FAIL", "module reference set differs", {"expected": sorted(map(norm, expected_paths)), "actual": sorted(map(norm, actual_paths))})
        set_properties(model, {
            "PartNumber": f"SEI-MECH-V5-SOLAR-MODULE-{side}{index}-R2B",
            "Description": f"Rigid solar panel module {side}{index} R2B-A",
            "MODULE_RIGID": "TRUE",
            "SOLAR_STATE_CONFIGURATIONS": "NONE_DEFAULT_ONLY",
            "CHILD_LOCK_MATE_COUNT": str(len(locks)),
        }, attempt_id)
        saved = loop1b.save_assembly(model, target)
    finally:
        loop1b.close_doc(sw, model)
    return {
        "side": side,
        "panel_index": index,
        "target": file_fact(target),
        "expected_component_count": len(expected_paths),
        "expected_component_paths": sorted(map(norm, expected_paths)),
        "child_count": len(components),
        "lock_mates": locks,
        "mate_ledger": ledger,
        "references": references,
        "save": saved,
        "verdict": "V5_SOLAR_R2B_RIGID_MODULE_BUILD_SANITY_PASS",
    }


def component_by_path(model: Any, path: Path, types: Any, pythoncom: Any) -> Any:
    return loop1b.component_by_path(model, path, types, pythoncom)


def root_axis_y(side: str) -> float:
    return 143.15 if side == "L" else -143.15


def validate_root_lug_bore_selection(side: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    side_contract = ROOT_LUG_BORE_SELECTION_CONTRACT["sides"][side]
    params_raw = row.get("cylinder_params")
    if not isinstance(params_raw, list) or len(params_raw) < 7:
        raise GateError("ROOT_LUG_BORE_PARAMS_FAIL", "selected root lug bore lacks seven CylinderParams values", {"side": side, "row": dict(row)})
    try:
        params = [float(value) for value in params_raw]
        area_mm2 = float(row.get("area_mm2"))
        radius_mm = float(params[6]) * 1000.0
        axial_length_mm = area_mm2 / (2.0 * math.pi * radius_mm) if radius_mm > 0.0 else float("inf")
        candidate_count = int(row.get("candidate_count"))
    except (TypeError, ValueError) as exc:
        raise GateError("ROOT_LUG_BORE_NUMERIC_FAIL", "selected root lug bore contains a non-numeric B-rep value", {"side": side, "row": dict(row)}) from exc
    tolerance = ROOT_LUG_BORE_SELECTION_CONTRACT["tolerances_mm"]
    checks = {
        "finite": all(math.isfinite(value) for value in (*params, area_mm2, radius_mm, axial_length_mm)),
        "candidate_count": candidate_count == int(ROOT_LUG_BORE_SELECTION_CONTRACT["candidate_count"]),
        "reported_radius": abs(float(row.get("radius_mm", math.inf)) - float(ROOT_LUG_BORE_SELECTION_CONTRACT["radius_mm"])) <= 1.0e-9,
        "reported_axis_y": abs(float(row.get("axis_y_mm", math.inf)) - float(side_contract["axis_y_mm"])) <= 1.0e-9,
        "axis_direction": abs(abs(params[3]) - 1.0) < 1.0e-5 and abs(params[4]) < 1.0e-5 and abs(params[5]) < 1.0e-5,
        "chosen_minimum_x": abs(params[0] * 1000.0 - float(ROOT_LUG_BORE_SELECTION_CONTRACT["chosen_axis_x_mm"])) <= float(tolerance["axis_point"]),
        "axis_y": abs(params[1] * 1000.0 - float(side_contract["axis_y_mm"])) <= float(tolerance["axis_point"]),
        "axis_z": abs(params[2] * 1000.0 - float(ROOT_LUG_BORE_SELECTION_CONTRACT["axis_z_mm"])) <= float(tolerance["axis_point"]),
        "radius": abs(radius_mm - float(ROOT_LUG_BORE_SELECTION_CONTRACT["radius_mm"])) <= float(tolerance["radius"]),
        "axial_length": abs(axial_length_mm - float(ROOT_LUG_BORE_SELECTION_CONTRACT["chosen_face_axial_length_mm"])) <= float(tolerance["axial_length"]),
        "positive_area": area_mm2 > 0.0,
    }
    if not all(checks.values()):
        raise GateError("ROOT_LUG_BORE_SELECTION_FAIL", "dual-ear root lug bore selection differs from the frozen minimum-X contract", {"side": side, "checks": checks, "row": dict(row), "axial_length_mm": axial_length_mm})
    return {
        **dict(row),
        "cylinder_params": params,
        "area_mm2": area_mm2,
        "actual_radius_mm": radius_mm,
        "actual_axial_length_mm": axial_length_mm,
        "selection_contract": ROOT_LUG_BORE_SELECTION_CONTRACT,
        "selection_verdict": "V5_SOLAR_R2B_A_ROOT_LUG_DUAL_EAR_MIN_X_SELECTION_PASS",
    }


def transform_point_mm(transform: Sequence[float], point_mm: Sequence[float]) -> List[float]:
    if len(transform) != 16 or len(point_mm) != 3:
        raise GateError("NESTED_TRANSFORM_POINT_SHAPE_FAIL", "nested transform/point shape differs")
    x, y, z = (float(value_in) / 1000.0 for value_in in point_mm)
    return [
        (transform[0] * x + transform[3] * y + transform[6] * z + transform[9]) * 1000.0,
        (transform[1] * x + transform[4] * y + transform[7] * z + transform[10]) * 1000.0,
        (transform[2] * x + transform[5] * y + transform[8] * z + transform[11]) * 1000.0,
    ]


def transform_direction(transform: Sequence[float], direction: Sequence[float]) -> List[float]:
    x, y, z = (float(value_in) for value_in in direction)
    result = [
        transform[0] * x + transform[3] * y + transform[6] * z,
        transform[1] * x + transform[4] * y + transform[7] * z,
        transform[2] * x + transform[5] * y + transform[8] * z,
    ]
    length = math.sqrt(sum(value_in * value_in for value_in in result))
    if length <= 1.0e-12:
        raise GateError("NESTED_TRANSFORM_DIRECTION_ZERO", "nested transform maps local axis to zero")
    return [value_in / length for value_in in result]


def distance_mm(first: Sequence[float], second: Sequence[float]) -> float:
    return math.sqrt(sum((float(first[index]) - float(second[index])) ** 2 for index in range(3)))


def cross_norm(first: Sequence[float], second: Sequence[float]) -> float:
    cross = [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    ]
    return math.sqrt(sum(value_in * value_in for value_in in cross))


def nested_local_z_hinge_entities(component: Any, radius_mm: float, expected_world_z0_mm: Sequence[float], label: str, types: Any, pythoncom: Any) -> Tuple[Any, Any, Dict[str, Any]]:
    cylinder_rows: List[Tuple[Any, List[float], float]] = []
    all_cylinders: List[Dict[str, Any]] = []
    plane_rows: List[Tuple[Any, List[float], float]] = []
    all_planes: List[Dict[str, Any]] = []
    tolerances = INTERPANEL_NESTED_BREP_FRAME_CONTRACT["tolerances"]
    for body in loop1b.component_bodies(component, types, pythoncom):
        for raw_face in loop1b.as_list(loop1b.value(body, "GetFaces")):
            face = loop1b.wrap(raw_face, "IFace2", types, pythoncom)
            surface = loop1b.wrap(loop1b.value(face, "GetSurface"), "ISurface", types, pythoncom)
            area_mm2 = float(loop1b.value(face, "GetArea")) * 1.0e6
            if bool(surface.IsCylinder()):
                params = [float(value_in) for value_in in loop1b.as_list(loop1b.value(surface, "CylinderParams"))]
                all_cylinders.append({"cylinder_params": params, "area_mm2": area_mm2})
                if (
                    len(params) >= 7
                    and abs(params[3]) < 1.0e-5
                    and abs(params[4]) < 1.0e-5
                    and abs(abs(params[5]) - 1.0) < 1.0e-5
                    and abs(params[0] * 1000.0) <= float(tolerances["local_axis_point_mm"])
                    and abs(params[1] * 1000.0) <= float(tolerances["local_axis_point_mm"])
                    and abs(params[6] * 1000.0 - radius_mm) <= float(tolerances["radius_mm"])
                ):
                    cylinder_rows.append((face, params, area_mm2))
            elif bool(surface.IsPlane()):
                params = [float(value_in) for value_in in loop1b.as_list(loop1b.value(surface, "PlaneParams"))]
                all_planes.append({"plane_params": params, "area_mm2": area_mm2})
                if len(params) >= 6 and abs(params[0]) < 1.0e-5 and abs(params[1]) < 1.0e-5 and abs(abs(params[2]) - 1.0) < 1.0e-5 and abs(params[5] * 1000.0) <= float(tolerances["local_axis_point_mm"]):
                    plane_rows.append((face, params, area_mm2))
    if len(cylinder_rows) != 1 or len(plane_rows) != 1:
        raise GateError("NESTED_LOCAL_Z_SIGNATURE_FAIL", "nested child lacks one local-Z cylinder and one local-Z=0 end face", {"label": label, "radius_mm": radius_mm, "cylinder_count": len(cylinder_rows), "plane_count": len(plane_rows), "all_cylinders": all_cylinders, "all_planes": all_planes})
    cylinder_face, cylinder_params, cylinder_area = cylinder_rows[0]
    plane_face, plane_params, plane_area = plane_rows[0]
    actual_radius_mm = cylinder_params[6] * 1000.0
    axial_length_mm = cylinder_area / (2.0 * math.pi * actual_radius_mm)
    transform = loop1b.transform_array(component)
    world_z0 = transform_point_mm(transform, [0.0, 0.0, 0.0])
    world_z28 = transform_point_mm(transform, [0.0, 0.0, INTERPANEL_DEPTH_MM])
    world_direction = transform_direction(transform, [0.0, 0.0, 1.0])
    expected_z28 = [float(expected_world_z0_mm[0]) + INTERPANEL_DEPTH_MM, float(expected_world_z0_mm[1]), float(expected_world_z0_mm[2])]
    checks = {
        "axial_length": abs(axial_length_mm - INTERPANEL_DEPTH_MM) <= float(tolerances["axial_length_mm"]),
        "world_z0": distance_mm(world_z0, expected_world_z0_mm) <= float(tolerances["world_point_mm"]),
        "world_z28": distance_mm(world_z28, expected_z28) <= float(tolerances["world_point_mm"]),
        "world_axis_x": abs(abs(world_direction[0]) - 1.0) <= float(tolerances["world_direction_cross_norm"]) and abs(world_direction[1]) <= float(tolerances["world_direction_cross_norm"]) and abs(world_direction[2]) <= float(tolerances["world_direction_cross_norm"]),
    }
    if not all(checks.values()):
        raise GateError("NESTED_LOCAL_TO_WORLD_FAIL", "local-Z nested hinge B-rep does not map to its nominal world X axis", {"label": label, "checks": checks, "world_z0_mm": world_z0, "world_z28_mm": world_z28, "world_direction": world_direction, "expected_world_z0_mm": list(expected_world_z0_mm), "expected_world_z28_mm": expected_z28})
    fact = {
        "label": label,
        "component": str(loop1b.value(component, "Name2")),
        "component_file": file_fact(loop1b.component_path(component)),
        "entity_signature_coordinate_frame": "NESTED_CHILD_PART_LOCAL",
        "all_raw_cylinders": all_cylinders,
        "selected_cylinder_params": cylinder_params,
        "selected_cylinder_area_mm2": cylinder_area,
        "selected_cylinder_axial_length_mm": axial_length_mm,
        "cylinder_candidate_count": 1,
        "all_raw_planes": all_planes,
        "selected_end_plane_params": plane_params,
        "selected_end_plane_area_mm2": plane_area,
        "end_plane_candidate_count": 1,
        "child_transform16": transform,
        "canonical_local_z0_world_mm": world_z0,
        "canonical_local_z28_world_mm": world_z28,
        "canonical_local_plus_z_world_direction": world_direction,
        "expected_world_z0_mm": list(expected_world_z0_mm),
        "expected_world_z28_mm": expected_z28,
        "checks": checks,
    }
    return loop1b.wrap(cylinder_face, "IEntity", types, pythoncom), loop1b.wrap(plane_face, "IEntity", types, pythoncom), fact


def validate_interpanel_world_continuity(pin_fact: Mapping[str, Any], collar_fact: Mapping[str, Any], expected_world_z0_mm: Sequence[float]) -> Dict[str, Any]:
    tolerance = INTERPANEL_NESTED_BREP_FRAME_CONTRACT["tolerances"]
    pin_point = pin_fact["canonical_local_z0_world_mm"]
    collar_point = collar_fact["canonical_local_z0_world_mm"]
    pin_direction = pin_fact["canonical_local_plus_z_world_direction"]
    collar_direction = collar_fact["canonical_local_plus_z_world_direction"]
    point_delta = distance_mm(pin_point, collar_point)
    direction_error = cross_norm(pin_direction, collar_direction)
    expected_pin_error = distance_mm(pin_point, expected_world_z0_mm)
    expected_collar_error = distance_mm(collar_point, expected_world_z0_mm)
    if point_delta > float(tolerance["world_point_mm"]) or direction_error > float(tolerance["world_direction_cross_norm"]) or max(expected_pin_error, expected_collar_error) > float(tolerance["world_point_mm"]):
        raise GateError("INTERPANEL_WORLD_AXIS_CONTINUITY_FAIL", "pin/collar local B-reps do not map to one expected world hinge axis", {"pin_point_mm": pin_point, "collar_point_mm": collar_point, "expected_world_z0_mm": list(expected_world_z0_mm), "point_delta_mm": point_delta, "direction_cross_norm": direction_error, "pin_expected_error_mm": expected_pin_error, "collar_expected_error_mm": expected_collar_error})
    return {"pin_world_z0_mm": pin_point, "collar_world_z0_mm": collar_point, "expected_world_z0_mm": list(expected_world_z0_mm), "point_delta_mm": point_delta, "direction_cross_norm": direction_error, "pin_expected_error_mm": expected_pin_error, "collar_expected_error_mm": expected_collar_error, "verdict": "V5_SOLAR_R2B_A_INTERPANEL_WORLD_AXIS_CONTINUITY_PASS"}


def module_pose_pair(model: Any, first_path: Path, second_path: Path, types: Any, pythoncom: Any) -> Dict[str, List[float]]:
    return {
        "upstream": loop1b.transform_array(component_by_path(model, first_path, types, pythoncom)),
        "downstream": loop1b.transform_array(component_by_path(model, second_path, types, pythoncom)),
    }


def pose_pair_error(first: Mapping[str, Sequence[float]], second: Mapping[str, Sequence[float]]) -> float:
    return max(abs(float(first[key][index]) - float(second[key][index])) for key in ("upstream", "downstream") for index in range(16))


def build_root_retainer_mates(model: Any, assembly: Any, side: str, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    pin = component_by_path(model, ROOT_INPUTS[side]["pin"][0], types, pythoncom)
    retainer = component_by_path(model, ROOT_INPUTS[side]["retainer"][0], types, pythoncom)
    axis_y = root_axis_y(side)
    retainer_cyl, _ = loop1b.cylinder_entity(retainer, 4.1, axis_y, 1, types, pythoncom)
    pin_cyl, _ = loop1b.cylinder_entity(pin, 4.0, axis_y, 1, types, pythoncom)
    concentric = add_named_entity_mate(model, assembly, retainer_cyl, pin_cyl, SW_MATE_CONCENTRIC, (retainer, pin), f"R2B_{side}_ROOT_RETAINER_CONCENTRIC", types, pythoncom)
    retainer = component_by_path(model, ROOT_INPUTS[side]["retainer"][0], types, pythoncom)
    pin = component_by_path(model, ROOT_INPUTS[side]["pin"][0], types, pythoncom)
    retainer_face, _ = loop1b.plane_entity_x(retainer, -82.0, types, pythoncom)
    pin_face, _ = loop1b.plane_entity_x(pin, -82.0, types, pythoncom)
    coincident = add_named_entity_mate(model, assembly, retainer_face, pin_face, SW_MATE_COINCIDENT, (retainer, pin), f"R2B_{side}_ROOT_RETAINER_COINCIDENT", types, pythoncom)
    return [concentric, coincident]


def build_hinge_mates(model: Any, assembly: Any, side: str, attempt_root: Path, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    modules = module_paths(attempt_root)
    specs = part_specs(attempt_root, load_authority_bundle()["authority"])
    rows: List[Dict[str, Any]] = []
    for index, joint in ((1, "ROOT"), (2, "H12"), (3, "H23")):
        module = component_by_path(model, modules[(side, index)], types, pythoncom)
        if index == 1:
            parent = component_by_path(model, ROOT_INPUTS[side]["clevis"][0], types, pythoncom)
            lug = component_by_path(model, ROOT_INPUTS[side]["u_lug"][0], types, pythoncom)
            pin = component_by_path(model, ROOT_INPUTS[side]["pin"][0], types, pythoncom)
            spacer = component_by_path(model, SHARED_SPACER[0], types, pythoncom)
            lug_cyl, lug_fact_raw = loop1b.cylinder_entity(
                lug,
                float(ROOT_LUG_BORE_SELECTION_CONTRACT["radius_mm"]),
                root_axis_y(side),
                int(ROOT_LUG_BORE_SELECTION_CONTRACT["candidate_count"]),
                types,
                pythoncom,
            )
            lug_fact = validate_root_lug_bore_selection(side, lug_fact_raw)
            pin_cyl, pin_fact = loop1b.cylinder_entity(pin, 4.0, root_axis_y(side), 1, types, pythoncom)
            concentric = add_named_entity_mate(model, assembly, lug_cyl, pin_cyl, SW_MATE_CONCENTRIC, (lug, pin), f"R2B_{side}_{joint}_CONCENTRIC", types, pythoncom)
            lug = component_by_path(model, ROOT_INPUTS[side]["u_lug"][0], types, pythoncom)
            spacer = component_by_path(model, SHARED_SPACER[0], types, pythoncom)
            lug_face, lug_plane = loop1b.plane_entity_x(lug, -75.0, types, pythoncom)
            spacer_face, spacer_plane = loop1b.spacer_axial_plane_entity(spacer, root_axis_y(side), types, pythoncom)
            coincident = add_named_entity_mate(model, assembly, lug_face, spacer_face, SW_MATE_COINCIDENT, (lug, spacer), f"R2B_{side}_{joint}_COINCIDENT", types, pythoncom)
            geometry = {
                "moving_bore": lug_fact,
                "root_lug_bore_selection_contract": ROOT_LUG_BORE_SELECTION_CONTRACT,
                "u_lug": file_fact(ROOT_INPUTS[side]["u_lug"][0]),
                "pin": pin_fact,
                "moving_face": lug_plane,
                "fixed_face": spacer_plane,
            }
        else:
            parent = component_by_path(model, modules[(side, index - 1)], types, pythoncom)
            pin_path = Path(specs[part_key(side, index - 1, "OUTBOARD_HINGE_PIN_IF")]["target"])
            collar_path = Path(specs[part_key(side, index, "INBOARD_HINGE_COLLAR_IF")]["target"])
            pin = component_by_path(model, pin_path, types, pythoncom)
            collar = component_by_path(model, collar_path, types, pythoncom)
            axis_y = float(INTERPANEL_NESTED_BREP_FRAME_CONTRACT["nominal_world"]["hinge_y_mm"][side][joint])
            expected_world_z0 = [float(INTERPANEL_NESTED_BREP_FRAME_CONTRACT["nominal_world"]["local_z0_world_x_mm"]), axis_y, 0.0]
            pose_pre = module_pose_pair(model, modules[(side, index - 1)], modules[(side, index)], types, pythoncom)
            pin_cyl, _pin_face, pin_fact = nested_local_z_hinge_entities(pin, INTERPANEL_PIN_R_MM, expected_world_z0, f"{side}/{joint}/PIN", types, pythoncom)
            collar_cyl, _collar_face, collar_fact = nested_local_z_hinge_entities(collar, INTERPANEL_BORE_R_MM, expected_world_z0, f"{side}/{joint}/COLLAR", types, pythoncom)
            world_continuity = validate_interpanel_world_continuity(pin_fact, collar_fact, expected_world_z0)
            concentric = add_named_entity_mate(model, assembly, pin_cyl, collar_cyl, SW_MATE_CONCENTRIC, (pin, collar), f"R2B_{side}_{joint}_CONCENTRIC", types, pythoncom)
            pose_post_concentric = module_pose_pair(model, modules[(side, index - 1)], modules[(side, index)], types, pythoncom)
            pin = component_by_path(model, pin_path, types, pythoncom)
            collar = component_by_path(model, collar_path, types, pythoncom)
            _pin_cyl, pin_face, pin_after_concentric = nested_local_z_hinge_entities(pin, INTERPANEL_PIN_R_MM, expected_world_z0, f"{side}/{joint}/PIN_POST_CONCENTRIC", types, pythoncom)
            _collar_cyl, collar_face, collar_after_concentric = nested_local_z_hinge_entities(collar, INTERPANEL_BORE_R_MM, expected_world_z0, f"{side}/{joint}/COLLAR_POST_CONCENTRIC", types, pythoncom)
            post_concentric_continuity = validate_interpanel_world_continuity(pin_after_concentric, collar_after_concentric, expected_world_z0)
            coincident = add_named_entity_mate(model, assembly, pin_face, collar_face, SW_MATE_COINCIDENT, (pin, collar), f"R2B_{side}_{joint}_COINCIDENT", types, pythoncom)
            pose_post_coincident = module_pose_pair(model, modules[(side, index - 1)], modules[(side, index)], types, pythoncom)
            concentric_pose_error = pose_pair_error(pose_pre, pose_post_concentric)
            coincident_pose_error = pose_pair_error(pose_pre, pose_post_coincident)
            pose_tolerance = float(INTERPANEL_NESTED_BREP_FRAME_CONTRACT["tolerances"]["module_transform_max_abs"])
            if max(concentric_pose_error, coincident_pose_error) > pose_tolerance:
                raise GateError("INTERPANEL_MATE_POSE_JUMP_FAIL", "concentric/coincident creation moved an authored module occurrence", {"side": side, "joint": joint, "pre": pose_pre, "post_concentric": pose_post_concentric, "post_coincident": pose_post_coincident, "concentric_max_abs_error": concentric_pose_error, "coincident_max_abs_error": coincident_pose_error, "tolerance": pose_tolerance})
            geometry = {
                "interpanel_nested_brep_frame_contract": INTERPANEL_NESTED_BREP_FRAME_CONTRACT,
                "pin": pin_fact,
                "collar": collar_fact,
                "world_axis_continuity": world_continuity,
                "post_concentric_world_axis_continuity": post_concentric_continuity,
                "mate_pose_stability": {
                    "pre": pose_pre,
                    "post_concentric": pose_post_concentric,
                    "post_coincident": pose_post_coincident,
                    "concentric_max_abs_error": concentric_pose_error,
                    "coincident_max_abs_error": coincident_pose_error,
                    "tolerance": pose_tolerance,
                    "verdict": "V5_SOLAR_R2B_A_INTERPANEL_MATE_POSE_STABILITY_PASS",
                },
            }
        # Reacquire top-level occurrences after each B-rep mate/rebuild.
        parent = component_by_path(model, ROOT_INPUTS[side]["clevis"][0] if index == 1 else modules[(side, index - 1)], types, pythoncom)
        module = component_by_path(model, modules[(side, index)], types, pythoncom)
        expected_flip = bool(FLIP_CONTRACT["sides"][side][joint])
        limit_angle = add_named_limit_angle(
            model,
            assembly,
            parent,
            module,
            f"R2B_{side}_{joint}_LIMIT_ANGLE_0_90",
            expected_flip,
            types,
            pythoncom,
        )
        rows.append({
            "joint": joint,
            "branch_contract": {
                "selection_order": "PARENT_THEN_CHILD",
                "alignment": SW_ALIGN_ALIGNED,
                "flip": expected_flip,
                "branch": "NEGATIVE" if SIGNED_FOLD_DIRECTION[side][joint] < 0 else "POSITIVE",
            },
            "concentric": concentric,
            "coincident": coincident,
            "advanced_limit_angle": limit_angle,
            "geometry": geometry,
        })
    return rows


def set_feature_suppression(feature: Any, suppress: bool) -> None:
    """Apply and read back one mate suppression state in this configuration."""
    # swFeatureSuppressionAction_e: 0=suppress, 1=unsuppress;
    # swInConfigurationOpts_e: 2=this configuration.
    feature.SetSuppression2(0 if suppress else 1, 2, None)
    if bool(base.value(feature, "IsSuppressed")) != suppress:
        raise GateError(
            "CONFIG_MATE_SUPPRESSION_FAIL",
            "configuration-specific mate suppression readback differs",
            {"feature": str(base.value(feature, "Name")), "requested_suppressed": suppress},
        )


def drive_configurations(sw: Any, model: Any, side: str, attempt_root: Path, attempt_id: str, authority: Mapping[str, Any], types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    manager = base.value(model, "ConfigurationManager")
    active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    active.Name = "SOLAR_DEPLOYED_NOMINAL"
    existing = {str(name) for name in base.as_list(base.value(model, "GetConfigurationNames"))}
    for state in CONFIGS:
        if state not in existing:
            created = manager.AddConfiguration2(state, "R2B-A frozen static anchor", "", 0, "", False, False)
            if created is None:
                raise GateError("CONFIG_CREATE_FAIL", "cannot create side state", {"side": side, "state": state})
            existing.add(state)
    if set(existing) != set(CONFIGS):
        raise GateError("CONFIG_SET_FAIL", "side configuration set is not exactly the seven frozen states", {"side": side, "actual": sorted(existing), "expected": sorted(CONFIGS)})

    # SW2024 installation-specific persistence path proven in Loop1C1:
    # SetSystemValue3 + swSetValue_InSpecificConfigs + typed VT_BSTR array.
    # Feature and dimension handles are always reacquired after configuration
    # creation and after every activation.  Inline readback is prohibited
    # because the COM read can lag one write; the complete table is read only
    # after every cell has been stored and a rebuild has completed.
    from win32com.client import VARIANT

    joint_by_index = {1: "ROOT", 2: "H12", 3: "H23"}
    signed_direction = SIGNED_FOLD_DIRECTION
    pending_dimensions: List[Dict[str, Any]] = []
    for state in CONFIGS:
        if not bool(model.ShowConfiguration2(state)):
            raise GateError("CONFIG_ANGLE_ACTIVATE_FAIL", "cannot activate state before angle-table write", {"side": side, "state": state})
        angles = state_angles(authority, state, side)
        fresh = mate_feature_map(model, types, pythoncom)
        for index in (1, 2, 3):
            joint = joint_by_index[index]
            feature_name = f"R2B_{side}_{joint}_LIMIT_ANGLE_0_90"
            if feature_name not in fresh:
                raise GateError("CONFIG_ANGLE_FEATURE_REFETCH_FAIL", "named limit-angle mate missing after activation", {"side": side, "state": state, "feature": feature_name})
            feature = fresh[feature_name]
            expected_flip = bool(FLIP_CONTRACT["sides"][side][joint])
            angle_mate_fact(feature, expected_flip, types, pythoncom)
            dimension = angle_mate_dimension(feature, types, pythoncom)
            requested_rad = math.radians(90.0 - float(angles[index - 1]))
            names = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [state])
            status = int(dimension.SetSystemValue3(requested_rad, SW_SET_VALUE_IN_SPECIFIC_CONFIGS, names))
            if status != SW_SET_VALUE_SUCCESS:
                raise GateError("CONFIG_ANGLE_DIMENSION_WRITE_FAIL", "configuration-specific angle write failed", {"side": side, "state": state, "joint": joint, "status": status, "requested_rad": requested_rad})
            pending_dimensions.append({
                "state": state,
                "joint": joint,
                "feature_name": feature_name,
                "logical_alpha_deg": float(angles[index - 1]),
                "requested_physical_magnitude_deg": 90.0 - float(angles[index - 1]),
                "requested_rad": requested_rad,
                "signed_fold_direction_about_world_x": signed_direction[side][joint],
                "selection_order": "PARENT_THEN_CHILD",
                "requested_alignment": SW_ALIGN_ALIGNED,
                "requested_flip": expected_flip,
                "mate_alignment": "SW_ALIGN_ALIGNED_PARENT_THEN_CHILD",
                "status": status,
            })
    if not bool(model.ForceRebuild3(True)):
        raise GateError("CONFIG_ANGLE_TABLE_REBUILD_FAIL", "rebuild failed after complete angle-table write", {"side": side})

    dimension_readback: Dict[str, List[Dict[str, Any]]] = {state: [] for state in CONFIGS}
    for state in CONFIGS:
        if not bool(model.ShowConfiguration2(state)):
            raise GateError("CONFIG_ANGLE_READBACK_ACTIVATE_FAIL", "cannot activate state for complete angle-table readback", {"side": side, "state": state})
        fresh = mate_feature_map(model, types, pythoncom)
        for pending in (row for row in pending_dimensions if row["state"] == state):
            feature = fresh.get(pending["feature_name"])
            if feature is None:
                raise GateError("CONFIG_ANGLE_READBACK_FEATURE_FAIL", "named limit-angle mate missing during full-table readback", {"side": side, **pending})
            branch_readback = angle_mate_fact(feature, bool(pending["requested_flip"]), types, pythoncom)
            dimension = angle_mate_dimension(feature, types, pythoncom)
            readback_rad = float(dimension.GetSystemValue2(state))
            if abs(readback_rad - float(pending["requested_rad"])) > 2.0e-6:
                raise GateError("CONFIG_ANGLE_DIMENSION_NOOP_OR_CROSS_SLOT", "angle dimension full-table readback differs after SetSystemValue3", {"side": side, **pending, "readback_rad": readback_rad})
            dimension_readback[state].append({
                **pending,
                "readback_rad": readback_rad,
                "readback_deg": math.degrees(readback_rad),
                "angle_mate_readback": branch_readback,
            })

    rows: List[Dict[str, Any]] = []
    paths = module_paths(attempt_root)
    for state in CONFIGS:
        if not bool(model.ShowConfiguration2(state)):
            raise GateError("CONFIG_ACTIVATE_FAIL", "cannot activate side state", {"side": side, "state": state})
        angles = state_angles(authority, state, side)
        readback = []
        angle_feature_names = [f"R2B_{side}_{joint}_LIMIT_ANGLE_0_90" for joint in ("ROOT", "H12", "H23")]
        fresh = mate_feature_map(model, types, pythoncom)
        for joint, name in zip(("ROOT", "H12", "H23"), angle_feature_names):
            feature = fresh.get(name)
            if feature is None:
                raise GateError("CONFIG_POSE_ANGLE_FEATURE_FAIL", "named limit-angle mate is missing before pose placement", {"side": side, "state": state, "feature": name})
            angle_mate_fact(feature, bool(FLIP_CONTRACT["sides"][side][joint]), types, pythoncom)
            set_feature_suppression(feature, True)
        if not bool(model.EditRebuild3()):
            raise GateError("CONFIG_POSE_SUPPRESSION_REBUILD_FAIL", "rebuild failed after temporary angle-mate suppression", {"side": side, "state": state})
        # This is the hash-bound microfixture protocol: keep the physical
        # concentric/coincident chain live, suppress only the three angle
        # drivers, place rigid modules root-to-tip without solver propagation,
        # restore all drivers, then perform one full solve/rebuild.
        for index in (1, 2, 3):
            component = component_by_path(model, paths[(side, index)], types, pythoncom)
            wanted = module_delta(side, angles, index, authority)
            if not bool(component.SetTransformAndSolve3(make_transform(sw, wanted, types, pythoncom), False)):
                raise GateError("CONFIG_MODULE_DRIVE_FAIL", "cannot drive exact rigid-module pose", {"side": side, "state": state, "panel": index})
        fresh = mate_feature_map(model, types, pythoncom)
        for name in angle_feature_names:
            feature = fresh.get(name)
            if feature is None:
                raise GateError("CONFIG_POSE_ANGLE_FEATURE_RESTORE_FAIL", "named limit-angle mate is missing before restore", {"side": side, "state": state, "feature": name})
            set_feature_suppression(feature, False)
        if not bool(model.ForceRebuild3(True)):
            raise GateError("CONFIG_FORCE_REBUILD_FAIL", "state force rebuild failed", {"side": side, "state": state})
        restored_branch_readback = []
        fresh = mate_feature_map(model, types, pythoncom)
        for joint, name in zip(("ROOT", "H12", "H23"), angle_feature_names):
            feature = fresh.get(name)
            if feature is None:
                raise GateError("CONFIG_POSE_ANGLE_FEATURE_POST_RESTORE_FAIL", "named limit-angle mate is missing after restore", {"side": side, "state": state, "feature": name})
            restored_branch_readback.append({
                "joint": joint,
                "readback": angle_mate_fact(feature, bool(FLIP_CONTRACT["sides"][side][joint]), types, pythoncom),
            })
        for index in (1, 2, 3):
            component = component_by_path(model, paths[(side, index)], types, pythoncom)
            wanted = module_delta(side, angles, index, authority)
            actual = loop1b.transform_array(component)
            error = transform_error(actual, wanted)
            if error["translation_mm"] > TRANS_TOL_MM or error["rotation_deg"] > ROT_TOL_DEG:
                raise GateError("CONFIG_TRANSFORM_READBACK_FAIL", "same-PID exact module pose differs", {"side": side, "state": state, "panel": index, "error": error})
            readback.append({"module": f"{side}{index}", "transform16": actual, "error": error})
        props = model.Extension.CustomPropertyManager(state)
        for name, value in {
            "SolarSide": side,
            "NormalizedLogicalAnglesDeg": "/".join(str(int(value)) for value in angles),
            "StateAuthoritySHA256": EXPECTED_BINDINGS[0][2],
            "StaticOracleSHA256": EXPECTED_BINDINGS[2][2],
            "ConfigurationOwner": "SIDE_SLDASM_ONLY",
            "ContinuousMotionAuthority": "NONE_STATIC_ANCHORS_ONLY",
        }.items():
            if int(props.Add3(name, 30, str(value), 2)) < 0:
                raise GateError("CONFIG_PROPERTY_FAIL", "cannot write configuration property", {"side": side, "state": state, "property": name})
        rows.append({
            "state": state,
            "angles_deg": list(angles),
            "angle_dimension_readback": dimension_readback[state],
            "restored_angle_branch_readback": restored_branch_readback,
            "module_readback": readback,
            "driver_contract": "CONFIG_SPECIFIC_NATIVE_LIMIT_ANGLE_DIMENSION_PLUS_SUPPRESS_PLACE_ROOT_TO_TIP_SOLVE_FALSE_RESTORE",
            "pose_drive_protocol": "SUPPRESS_3_LIMIT_ANGLES__PLACE_ROOT_TO_TIP_SOLVE_FALSE__RESTORE_3_LIMIT_ANGLES__FORCE_REBUILD",
            "classification": "SAME_PID_BUILD_SANITY_NOT_FRESH_VERIFICATION",
        })
    # A second complete-table pass is mandatory.  It catches both
    # SetTransformAndSolve3 all-configuration leakage and a dimension value
    # that was silently changed while the exact rigid-module pose was solved.
    for row in rows:
        state = str(row["state"])
        angles = state_angles(authority, state, side)
        if not bool(model.ShowConfiguration2(state)) or not bool(model.ForceRebuild3(True)):
            raise GateError("CONFIG_FINAL_TABLE_ACTIVATE_FAIL", "cannot activate/rebuild state for final persistence table", {"side": side, "state": state})
        final_modules = []
        for index in (1, 2, 3):
            component = component_by_path(model, paths[(side, index)], types, pythoncom)
            wanted = module_delta(side, angles, index, authority)
            actual = loop1b.transform_array(component)
            error = transform_error(actual, wanted)
            if error["translation_mm"] > TRANS_TOL_MM or error["rotation_deg"] > ROT_TOL_DEG:
                raise GateError("CONFIG_FINAL_TABLE_TRANSFORM_FAIL", "saved configuration transform leaked or drifted", {"side": side, "state": state, "panel": index, "error": error})
            final_modules.append({"module": f"{side}{index}", "transform16": actual, "error": error})
        fresh = mate_feature_map(model, types, pythoncom)
        final_angles = []
        for index in (1, 2, 3):
            joint = joint_by_index[index]
            feature_name = f"R2B_{side}_{joint}_LIMIT_ANGLE_0_90"
            feature = fresh.get(feature_name)
            if feature is None:
                raise GateError("CONFIG_FINAL_TABLE_ANGLE_FEATURE_FAIL", "named angle mate missing after exact pose solve", {"side": side, "state": state, "feature": feature_name})
            branch_readback = angle_mate_fact(feature, bool(FLIP_CONTRACT["sides"][side][joint]), types, pythoncom)
            dimension = angle_mate_dimension(feature, types, pythoncom)
            expected_rad = math.radians(90.0 - float(angles[index - 1]))
            actual_rad = float(dimension.GetSystemValue2(state))
            if abs(actual_rad - expected_rad) > 2.0e-6:
                raise GateError("CONFIG_FINAL_TABLE_ANGLE_FAIL", "native limit-angle value drifted after module pose solve", {"side": side, "state": state, "joint": joint, "expected_rad": expected_rad, "actual_rad": actual_rad})
            final_angles.append({
                "joint": joint,
                "logical_alpha_deg": float(angles[index - 1]),
                "expected_rad": expected_rad,
                "readback_rad": actual_rad,
                "signed_fold_direction_about_world_x": signed_direction[side][joint],
                "branch_readback": branch_readback,
            })
        row["final_full_table_module_readback"] = final_modules
        row["final_full_table_angle_readback"] = final_angles
    if not bool(model.ShowConfiguration2("SOLAR_DEPLOYED_NOMINAL")):
        raise GateError("CONFIG_NOMINAL_RESTORE_FAIL", "cannot restore nominal state", {"side": side})
    return rows


def expected_side_references(side: str, attempt_root: Path, authority: Mapping[str, Any]) -> set[Path]:
    specs = part_specs(attempt_root, authority)
    paths = {Path(specs[key]["target"]).resolve() for index in (1, 2, 3) for key in module_part_keys(side, index)}
    paths.update(path.resolve() for path in module_paths(attempt_root).values() if path.name.startswith(f"SOLAR_PANEL_MODULE_{side}"))
    paths.update(ROOT_INPUTS[side][role][0].resolve() for role in ("clevis", "pin", "u_lug", "retainer"))
    paths.add(SHARED_SPACER[0].resolve())
    paths.add(SHARED_GROMMET[0].resolve())
    paths.add(SHARED_STOP_PAD[0].resolve())
    paths.update(path.resolve() for path, _sha in ROOT_ENVELOPE_INPUTS[side].values())
    return paths


def build_side(sw: Any, side: str, attempt_root: Path, attempt_id: str, authority: Mapping[str, Any], types: Any, pythoncom: Any) -> Dict[str, Any]:
    target = side_paths(attempt_root)[side]
    require_under_attempt(target, attempt_root)
    if target.exists():
        raise GateError("SIDE_TARGET_EXISTS", "write-once side assembly exists", {"target": norm(target)})
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = sw.NewDocument(str(ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = base.value(sw, "ActiveDoc")
    if raw is None:
        raise GateError("SIDE_NEW_DOCUMENT_FAIL", "cannot create side assembly", {"side": side})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    try:
        identity = loop1b.transform_data((0.0, 0.0, 0.0))
        root_components = {
            "clevis": insert_component_transform(sw, model, assembly, ROOT_INPUTS[side]["clevis"][0], identity, True, types, pythoncom),
            "pin": insert_component_transform(sw, model, assembly, ROOT_INPUTS[side]["pin"][0], identity, True, types, pythoncom),
            "spacer": insert_component_transform(sw, model, assembly, SHARED_SPACER[0], loop1b.transform_data((-0.0755, root_axis_y(side) / 1000.0, 0.0)), True, types, pythoncom),
            "grommet": insert_component_transform(sw, model, assembly, SHARED_GROMMET[0], loop1b.transform_data((-0.110, root_axis_y(side) / 1000.0, -0.020)), True, types, pythoncom),
            "stop_pad": insert_component_transform(sw, model, assembly, SHARED_STOP_PAD[0], loop1b.transform_data((-0.058, (121.15 if side == "L" else -121.15) / 1000.0, 0.037)), True, types, pythoncom),
            "retainer": insert_component_transform(sw, model, assembly, ROOT_INPUTS[side]["retainer"][0], identity, False, types, pythoncom),
        }
        envelope_components = {
            role: insert_component_transform(sw, model, assembly, path, identity, True, types, pythoncom)
            for role, (path, _sha) in ROOT_ENVELOPE_INPUTS[side].items()
        }
        modules = {}
        for index in (1, 2, 3):
            modules[index] = insert_component_transform(sw, model, assembly, module_paths(attempt_root)[(side, index)], identity, False, types, pythoncom)
        retainer_mates = build_root_retainer_mates(model, assembly, side, types, pythoncom)
        hinge_mates = build_hinge_mates(model, assembly, side, attempt_root, types, pythoncom)
        configurations = drive_configurations(sw, model, side, attempt_root, attempt_id, authority, types, pythoncom)
        nominal_ledger_activation = show_configuration_fact(
            model,
            "SOLAR_DEPLOYED_NOMINAL",
            types,
            pythoncom,
        )
        ledger = loop1b.mate_ledger(model, types, pythoncom)
        expected_names = {f"R2B_{side}_ROOT_RETAINER_CONCENTRIC", f"R2B_{side}_ROOT_RETAINER_COINCIDENT"}
        for joint in ("ROOT", "H12", "H23"):
            expected_names.update({f"R2B_{side}_{joint}_CONCENTRIC", f"R2B_{side}_{joint}_COINCIDENT", f"R2B_{side}_{joint}_LIMIT_ANGLE_0_90"})
        type_counts = Counter(row["mate_type"] for row in ledger)
        if len(ledger) != 11 or {row["feature_name"] for row in ledger} != expected_names or type_counts != Counter({SW_MATE_CONCENTRIC: 4, SW_MATE_COINCIDENT: 4, SW_MATE_ANGLE: 3}):
            raise GateError("SIDE_MATE_SET_FAIL", "side assembly mate set differs from 3R contract", {"side": side, "mate_ledger": ledger, "type_counts": dict(type_counts)})
        if any(row["feature_error_code"] != 0 or row["suppressed"] for row in ledger):
            raise GateError("SIDE_MATE_HEALTH_FAIL", "nominal side mate is suppressed or unhealthy", {"side": side, "mate_ledger": ledger})
        fresh_angle_features = mate_feature_map(model, types, pythoncom)
        final_angle_branch_readback = []
        for joint in ("ROOT", "H12", "H23"):
            feature_name = f"R2B_{side}_{joint}_LIMIT_ANGLE_0_90"
            feature = fresh_angle_features.get(feature_name)
            if feature is None:
                raise GateError("SIDE_ANGLE_BRANCH_FEATURE_FAIL", "nominal side lacks a named angle feature", {"side": side, "joint": joint})
            final_angle_branch_readback.append({
                "joint": joint,
                "selection_order": "PARENT_THEN_CHILD",
                "alignment": SW_ALIGN_ALIGNED,
                "flip": bool(FLIP_CONTRACT["sides"][side][joint]),
                "readback": angle_mate_fact(feature, bool(FLIP_CONTRACT["sides"][side][joint]), types, pythoncom),
            })
        references, actual_paths = reference_path_set(model, types, pythoncom)
        expected_paths = expected_side_references(side, attempt_root, authority)
        if actual_paths != expected_paths:
            raise GateError("SIDE_REFERENCE_SET_FAIL", "side recursive reference set differs", {"side": side, "expected": sorted(map(norm, expected_paths)), "actual": sorted(map(norm, actual_paths))})
        set_properties(model, {
            "PartNumber": f"SEI-MECH-V5-{side}-SOLAR-ARRAY-R2B",
            "Description": f"{side} three-panel solar-array R2B-A successor",
            "SIDE_CONFIGURATION_OWNER": "TRUE",
            "SOLAR_CONFIGURATION_COUNT": "7",
            "SERIAL_HINGE_COUNT": "3",
            "MATE_CONTRACT": "3x(CONCENTRIC+COINCIDENT+ADVANCED_LIMIT_ANGLE_0..90)",
            "LIMIT_ANGLE_BRANCH_CONTRACT": "/".join(f"{joint}:{int(bool(FLIP_CONTRACT['sides'][side][joint]))}" for joint in ("ROOT", "H12", "H23")),
            "RIGHT_GENERATION": "STRICT_XZ_MIRROR_OF_LEFT" if side == "R" else "LEFT_MASTER",
        }, attempt_id)
        saved = loop1b.save_assembly(model, target)
    finally:
        loop1b.close_doc(sw, model)
    return {
        "side": side,
        "target": file_fact(target),
            "root_reuse": {role: file_fact(path) for role, (path, _sha) in ROOT_INPUTS[side].items()},
        "root_functional_envelope_reuse": {role: file_fact(path) for role, (path, _sha) in ROOT_ENVELOPE_INPUTS[side].items()},
        "root_functional_envelope_classification": "FIXED_FUNCTIONAL_ENVELOPE_ONLY_NO_TORQUE_PRELOAD_LIFE_OR_BEND_RADIUS_CLAIM",
        "shared_spacer": file_fact(SHARED_SPACER[0]),
        "shared_grommet": file_fact(SHARED_GROMMET[0]),
        "shared_stop_pad": file_fact(SHARED_STOP_PAD[0]),
        "root_retainer_mates": retainer_mates,
        "flip_contract": {
            "selection_order": FLIP_CONTRACT["selection_order"],
            "alignment": FLIP_CONTRACT["alignment"],
            "hinges": dict(FLIP_CONTRACT["sides"][side]),
        },
        "hinges": hinge_mates,
        "final_angle_branch_readback": final_angle_branch_readback,
        "mate_ledger": ledger,
        "references": references,
        "expected_reference_paths": sorted(map(norm, expected_paths)),
        "configurations": configurations,
        "nominal_ledger_activation": nominal_ledger_activation,
        "save": saved,
        "verdict": "V5_SOLAR_R2B_SIDE_BUILD_SAME_PID_SANITY_PASS",
    }


def same_pid_sanity(sw: Any, attempt_root: Path, authority: Mapping[str, Any], types: Any, pythoncom: Any) -> Dict[str, Any]:
    cad = cad_targets(attempt_root, authority)
    missing = [norm(path) for path in cad if not path.is_file()]
    if missing:
        raise GateError("SAME_PID_FILE_SET_FAIL", "attempt CAD set is incomplete", {"missing": missing})
    sides = []
    for side, target in side_paths(attempt_root).items():
        model = None
        try:
            model, opened = loop1b.open_doc(sw, target, loop1b.SW_ASSEMBLY, True, types, pythoncom)
            names = [str(name) for name in base.as_list(base.value(model, "GetConfigurationNames"))]
            save_flag = bool(base.value(model, "GetSaveFlag"))
            if set(names) != set(CONFIGS) or len(names) != 7:
                raise GateError("SAME_PID_CONFIG_NAME_FAIL", "saved side configuration-name set differs", {"side": side, "actual": names})
            references, paths = reference_path_set(model, types, pythoncom)
            if paths != expected_side_references(side, attempt_root, authority):
                raise GateError("SAME_PID_REFERENCE_FAIL", "saved side recursive references differ", {"side": side})
            sides.append({"side": side, "target": file_fact(target), "open": opened, "configuration_names": names, "save_flag": save_flag, "references": references})
        finally:
            loop1b.close_doc(sw, model)
    if int(base.value(sw, "GetDocumentCount")) != 0 or base.value(sw, "ActiveDoc") is not None:
        raise GateError("SAME_PID_DOCUMENT_CLEANUP_FAIL", "owned build documents remain open after sanity")
    return {
        "scope": "SAME_PID_SANITY_ONLY_NO_COLD_OR_RELEASE_CLAIM",
        "mutation_apis_during_reopen": [],
        "cad_file_count": len(cad),
        "cad_files": [file_fact(path) for path in cad],
        "side_read_only_reopen": sides,
        "verdict": "V5_SOLAR_R2B_BUILD_SAME_PID_SANITY_PASS",
    }


def protected_snapshot(g0_receipt: Path, microfixture_receipt: Path) -> Dict[str, Any]:
    paths: List[Tuple[str, Path]] = [(label, path) for label, path, _sha in EXPECTED_BINDINGS]
    paths.extend((label, path) for label, path, _sha in TEMPLATE_BINDINGS)
    paths.extend((f"helper_{index}", path) for index, path in enumerate(HELPER_SOURCES, start=1))
    for side in ("L", "R"):
        paths.extend((f"root_{side}_{role}", path) for role, (path, _sha) in ROOT_INPUTS[side].items())
        paths.extend((f"root_envelope_{side}_{role}", path) for role, (path, _sha) in ROOT_ENVELOPE_INPUTS[side].items())
    paths.extend((("root_shared_spacer", SHARED_SPACER[0]), ("root_shared_grommet", SHARED_GROMMET[0]), ("root_shared_stop_pad", SHARED_STOP_PAD[0]), ("explicit_g0_receipt", g0_receipt), ("exact_r2b_microfixture_receipt", microfixture_receipt), ("builder_source", Path(__file__))))
    return {label: file_fact(path) for label, path in paths}


def attempt_layout(attempt_id: str) -> Dict[str, Path]:
    if ATTEMPT_RE.fullmatch(attempt_id) is None:
        raise GateError("ATTEMPT_ID_FAIL", "attempt id does not match controlled write-once grammar", {"attempt_id": attempt_id, "grammar": ATTEMPT_RE.pattern})
    storage_id = attempt_id.removeprefix("V5_SOLAR_R2B_BUILD_")
    if not storage_id or any(token in storage_id for token in ("/", "\\", ".", ":")):
        raise GateError("STORAGE_ID_FAIL", "physical attempt storage id is not one safe injective token", {"attempt_id": attempt_id, "storage_id": storage_id})
    root = ATTEMPT_PARENT / storage_id
    layout = {
        "root": root,
        "storage_id": storage_id,
        "evidence": root / "evidence",
        "start": root / "evidence/ATTEMPT_STARTED.json",
        "manifest_json": root / "evidence/CAD_MANIFEST.json",
        "manifest_sha": root / "evidence/CAD_MANIFEST_SHA256.txt",
        "handoff": root / "evidence/FRESH_PID_VERIFIER_HANDOFF.json",
        "receipt": root / "evidence/BUILD_STAGE_RECEIPT.json",
    }
    authority = load_authority_bundle()["authority"]
    longest = max((len(str(path.resolve())), str(path.resolve())) for path in cad_targets(root, authority))
    if longest[0] > 248:
        raise GateError("CAD_PATH_MARGIN_FAIL", "native CAD target exceeds the conservative 248-character SolidWorks path budget", {"length": longest[0], "path": longest[1]})
    return layout


def execute(args: argparse.Namespace) -> int:
    layout = attempt_layout(args.attempt_id)
    attempt_root = layout["root"]
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_SOLAR_R2B_A_BUILD_STAGE_RECEIPT_V1",
        "timestamp_start_utc": utc_now(),
        "attempt_id": args.attempt_id,
        "storage_id": layout["storage_id"],
        "attempt_root": norm(attempt_root),
        "builder": file_fact(Path(__file__)),
        "contract_sha256": contract_sha256(),
        "transaction_contract": TRANSACTION_CONTRACT,
        "angle_branch_contract": FLIP_CONTRACT,
        "production_root_flip_authorization": {
            "receipt": file_fact(PRODUCTION_ROOT_FLIP_AUTHORIZATION),
            "evidence_chain_sha256": EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256,
        },
        "annulus_native_feature_contract": ANNULUS_NATIVE_FEATURE_CONTRACT,
        "root_lug_bore_selection_contract": ROOT_LUG_BORE_SELECTION_CONTRACT,
        "interpanel_nested_brep_frame_contract": INTERPANEL_NESTED_BREP_FRAME_CONTRACT,
        "parts": [],
        "modules": [],
        "side_assemblies": [],
    }
    sw = types = pythoncom = None
    attempt_created = False
    try:
        with WindowsNamedMutex(MUTEX_NAME):
            audit = static_audit(args.g0_receipt, args.g0_sha256, args.expected_pid, args.microfixture_receipt, args.microfixture_sha256)
            result["static_audit"] = audit
            if not audit["execution_authorized"]:
                raise GateError("STATIC_EXECUTION_HOLD", "R2B-A build execution is not authorised", {"audit": audit})
            if attempt_root.exists():
                raise GateError("ATTEMPT_ROOT_EXISTS", "attempt root already exists; resume/overwrite is prohibited", {"attempt_root": norm(attempt_root)})
            attempt_root.mkdir(parents=True, exist_ok=False)
            attempt_created = True
            layout["evidence"].mkdir(parents=True, exist_ok=False)
            bundle = load_authority_bundle()
            authority = bundle["authority"]
            root_flip_authorization = bundle["branch_evidence"]["production_root_authorization"]
            g0 = g0_gate(args.g0_receipt, args.g0_sha256, args.expected_pid)
            microfixture = microfixture_gate(args.microfixture_receipt, args.microfixture_sha256)
            protected_pre = protected_snapshot(args.g0_receipt, args.microfixture_receipt)
            write_json_once(layout["start"], {
                "schema": "F3R2_V5_SOLAR_R2B_A_ATTEMPT_START_V1",
                "timestamp_utc": utc_now(),
                "attempt_id": args.attempt_id,
                "storage_id": layout["storage_id"],
                "attempt_root": norm(attempt_root),
                "builder": file_fact(Path(__file__)),
                "contract_sha256": contract_sha256(),
                "production_root_flip_authorization": root_flip_authorization,
                "g0": g0,
                "microfixture": microfixture,
                "protected_pre": protected_pre,
                "policy": "PRESERVE_ON_FAILURE_NO_RESUME_NO_DELETE",
            })
            result["attempt_start"] = file_fact(layout["start"])
            result["g0"] = g0
            result["microfixture"] = microfixture
            result["authority_bundle"] = bundle["facts"]
            result["angle_branch_evidence"] = bundle["branch_evidence"]
            result["production_root_flip_authorization"] = root_flip_authorization
            result["protected_pre"] = protected_pre
            result["protected_inputs"] = protected_pre
            result["allowed_external_references"] = allowed_external_reference_facts()
            result["memory_samples_gib"] = base.memory_gate()
            sw, types, pythoncom, session = base.attach_empty_session()
            if int(session["pid"]) != int(args.expected_pid):
                raise GateError("SESSION_PID_FAIL", "attached PID differs from explicit G0-bound PID", {"expected": args.expected_pid, "actual": session["pid"]})
            result["solidworks_build_session"] = session
            result["session"] = {
                "pid": int(session["pid"]),
                "process_create_time": g0["session_b_process"].get("process_start_utc"),
                "revision": session.get("revision"),
                "executable": session.get("executable"),
            }
            specs = part_specs(attempt_root, authority)
            for key, spec in specs.items():
                result["parts"].append(build_part(sw, key, spec, attempt_root, args.attempt_id, types, pythoncom))
            for side in ("L", "R"):
                for index in (1, 2, 3):
                    result["modules"].append(build_module(sw, side, index, attempt_root, args.attempt_id, authority, specs, types, pythoncom))
            for side in ("L", "R"):
                result["side_assemblies"].append(build_side(sw, side, attempt_root, args.attempt_id, authority, types, pythoncom))
            result["same_pid_sanity"] = same_pid_sanity(sw, attempt_root, authority, types, pythoncom)
            protected_post = protected_snapshot(args.g0_receipt, args.microfixture_receipt)
            result["protected_post"] = protected_post
            if protected_pre != protected_post:
                raise GateError("PROTECTED_INPUT_DRIFT", "authority/root/template/source input changed during attempt")
            cad = cad_targets(attempt_root, authority)
            facts = [file_fact(path) for path in cad]
            if (sum(path.suffix.upper() == ".SLDPRT" for path in cad), sum(path.suffix.upper() == ".SLDASM" for path in cad)) != (38, 8):
                raise GateError("CAD_OUTPUT_COUNT_FAIL", "attempt CAD extension count differs from 38 parts + 8 assemblies")
            manifest = {
                "schema": "F3R2_V5_SOLAR_R2B_A_CAD_MANIFEST_V1",
                "attempt_id": args.attempt_id,
                "storage_id": layout["storage_id"],
                "builder": file_fact(Path(__file__)),
                "contract_sha256": contract_sha256(),
                "production_root_flip_authorization": root_flip_authorization,
                "counts": {"SLDPRT": 38, "MODULE_SLDASM": 6, "SIDE_SLDASM": 2, "TOTAL_CAD": 46},
                "files": facts,
            }
            write_json_once(layout["manifest_json"], manifest)
            lines = [f"{row['sha256']}  {row['bytes']}  {Path(row['path']).relative_to(attempt_root).as_posix()}" for row in facts]
            write_text_once(layout["manifest_sha"], "\n".join(sorted(lines)) + "\n")
            handoff = {
                "schema": "F3R2_V5_SOLAR_R2B_A_FRESH_PID_VERIFIER_HANDOFF_V1",
                "timestamp_utc": utc_now(),
                "attempt_id": args.attempt_id,
                "storage_id": layout["storage_id"],
                "attempt_root": norm(attempt_root),
                "build_pid": int(session["pid"]),
                "build_process_start_utc": session.get("process_start_utc"),
                "g0_receipt": file_fact(args.g0_receipt),
                "exact_r2b_module_chain_microfixture_receipt": file_fact(args.microfixture_receipt),
                "builder": file_fact(Path(__file__)),
                "contract_sha256": contract_sha256(),
                "production_root_flip_authorization": root_flip_authorization,
                "authority_bundle": bundle["facts"],
                "cad_manifest": file_fact(layout["manifest_json"]),
                "cad_manifest_sha256_text": file_fact(layout["manifest_sha"]),
                "pre_verifier_cad_facts": facts,
                "required_verifier_process": {
                    "different_pid_from_build": True,
                    "different_process_start_from_build": True,
                    "attach_only": True,
                    "empty_session_pre": True,
                    "open_options": ["SILENT", "READ_ONLY"],
                    "zero_mutation_apis": True,
                    "forbidden_calls": ["Save3", "SaveAs", "SetTransformAndSolve3", "EditRebuild3", "ForceRebuild3", "AddConfiguration", "ModifyDefinition"],
                },
                "required_checks": [
                    "PRE_POST_SHA256_EQUAL_FOR_ALL_46_CAD_FILES",
                    "38_PARTS_ONE_SOLID_EXPECTED_DIMENSIONS_AND_ZERO_EXTERNAL_LINKS",
                    "4_COLLAR_PARTS_OUTER_BOSS_PLUS_SEPARATE_THROUGH_CUT_AND_UNIQUE_BORE_BREP",
                    "6_MODULES_RIGID_INTERNAL_LOCK_MATE_SET_AND_REFERENCE_SET",
                    "2_SIDE_ASSEMBLIES_EXACT_SEVEN_CONFIGURATIONS",
                    "EACH_SIDE_EXACT_3X_CONCENTRIC_COINCIDENT_ADVANCED_LIMIT_ANGLE_0_TO_90",
                    "PRODUCTION_ROOT_FLIP_AUTHORIZATION_HASH_SEMANTICS_AND_EVIDENCE_DIGEST",
                    "EXACT_V2_FLIP_MATRIX_L_F_F_T_R_T_T_F_IN_ALL_SEVEN_CONFIGURATIONS",
                    "ALL_CONFIGURATION_TRANSFORMS_MATCH_STATIC_ORACLE",
                    "RIGHT_BREP_AND_TRANSFORMS_ARE_XZ_MIRROR_OF_LEFT",
                    "NO_SAVE_FLAG_AND_EMPTY_SESSION_POST",
                ],
                "promotion_authorized": False,
                "status": "AWAITING_DIFFERENT_PID_READ_ONLY_ZERO_MUTATION_VERIFICATION",
            }
            write_json_once(layout["handoff"], handoff)
            result.update({
                "timestamp_end_utc": utc_now(),
                "cad_manifest": file_fact(layout["manifest_json"]),
                "cad_manifest_sha256_text": file_fact(layout["manifest_sha"]),
                "artifacts": [
                    *[{"role": "SLDPRT", **row["target"]} for row in result["parts"]],
                    *[{"role": "RIGID_PANEL_MODULE_SLDASM", **row["target"]} for row in result["modules"]],
                    *[{"role": "SIDE_STATE_OWNER_SLDASM", **row["target"]} for row in result["side_assemblies"]],
                ],
                "fresh_pid_verifier_handoff": file_fact(layout["handoff"]),
                "claims": {
                    "new_sldprt_count": 38,
                    "rigid_panel_module_sldasm_count": 6,
                    "side_sldasm_count": 2,
                    "side_configuration_count_each": 7,
                    "native_serial_hinge_count_total": 6,
                    "right_generated_strictly_by_xz_mirror": True,
                    "l0_mass_inertia_modified": False,
                    "fresh_pid_verified": False,
                    "promotion_authorized": False,
                    "flight_ready": False,
                    "launch_qualified": False,
                },
                "remaining_holds": [
                    "FRESH_PID_READ_ONLY_ZERO_MUTATION_VERIFICATION_REQUIRED",
                    "TOP_LEVEL_INTEGRATION_AND_NATIVE_BREP_CLEARANCE_PENDING",
                    "CAMERA_VISIBILITY_AND_HARNESS_SWEEP_PENDING",
                    "DRAWING_BOM_PACK_AND_GO_RELEASE_EVIDENCE_PENDING",
                    "LAUNCH_LOAD_THERMAL_VACUUM_RANDOM_VIBRATION_FASTENER_MOS_HOLD",
                ],
                "verdict": "V5_SOLAR_R2B_A_BUILD_STAGE_PASS_AWAITING_FRESH_PID_VERIFIER",
            })
            write_json_once(layout["receipt"], result)
            print(json.dumps({"verdict": result["verdict"], "attempt_root": norm(attempt_root), "receipt": file_fact(layout["receipt"]), "handoff": file_fact(layout["handoff"])}, ensure_ascii=False, indent=2))
            return 0
    except Exception as exc:
        result.update({"timestamp_end_utc": utc_now(), "verdict": getattr(exc, "code", "V5_SOLAR_R2B_A_BUILD_UNEXPECTED_FAIL"), "reason": str(exc), "detail": getattr(exc, "detail", {}), "traceback": traceback.format_exc(), "attempt_preserved": attempt_created})
        if attempt_created:
            failure = attempt_root / f"evidence/BUILD_FAILURE_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
            try:
                write_json_once(failure, result)
            except Exception:
                pass
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    finally:
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F3R2 V5 R2B-A attempt-root native solar-array build stage")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit", help="read-only authority/hash/static audit; never touches SOLIDWORKS")
    sub.add_parser("selftest", help="pure-Python count/FK/mirror/transaction self-test")
    execute_parser = sub.add_parser("execute", help="attach to the explicit G0-bound PID and create one attempt")
    execute_parser.add_argument("--attempt-id", required=True)
    execute_parser.add_argument("--expected-pid", required=True, type=int)
    execute_parser.add_argument("--g0-receipt", required=True, type=Path)
    execute_parser.add_argument("--g0-sha256", required=True)
    execute_parser.add_argument("--microfixture-receipt", required=True, type=Path)
    execute_parser.add_argument("--microfixture-sha256", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "selftest":
        result = selftest()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["verdict"].endswith("_PASS") else 2
    if args.command == "audit":
        result = static_audit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["static_ready"] else 2
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
