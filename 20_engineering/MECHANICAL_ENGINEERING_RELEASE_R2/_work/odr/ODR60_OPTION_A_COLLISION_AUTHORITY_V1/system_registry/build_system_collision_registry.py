#!/usr/bin/env python3
"""Build the fail-closed M01 system collision object and pair registry.

This builder enumerates the collision universe only.  It does not evaluate a
configuration, generate a path, or authorize M01 execution.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
COLLISION_PACKAGE_DIR = PACKAGE_DIR.parent

REGISTRY_NAME = "M01_SYSTEM_COLLISION_REGISTRY_V1.json"
PAIR_NAME = "M01_PAIR_COVERAGE_V1.csv"
GATE_NAME = "M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json"

RAW_URDF_BASE_LINK_SHA256 = (
    "22641C079014FE968702393F61E7F7F1A8F80C6C1DF45A61E31545F6EAFF3B65"
)

SOURCE_PINS = {
    "accepted_urdf": (
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
    ),
    "product_structure": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml",
        "0F9897EF4E41666DDB29CB0FC621DD737FDD8CCDE3F5527030E53A9D1604681A",
    ),
    "collision_contract": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/16_EMBODIED_MECHANICAL_CONTRACT.yaml",
        "5DDA627794A4B29D087D7489BECC7A98ED632BC6EAC0413CD9F7226C03AE1E7C",
    ),
    "master_geometry_step": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/04_MASTER_GEOMETRY.step",
        "8C85585E9C051AEBB849E48F56354B48BF4204F61103B550BD92FC77BA99EA9E",
    ),
    "load_bridge_step": (
        "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_CANDIDATE_V1.step",
        "545FE62ADE0E4891FCC84179D18F63B2A6C77F19AD1C96723B3C7208EA13221B",
    ),
    "load_bridge_datums": (
        "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml",
        "0F9B413E7B6CD451E2724AD25CA4DA41E52E02C86F1D2874460274EADBAA47A2",
    ),
    "m3r_step": (
        "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_WORKING.step",
        "A213804F094238B261EE5994DF563E8268FC923FDED491E38F5A4F235F748033",
    ),
    "m3r_fcstd": (
        "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_WORKING.FCStd",
        "AA7D33582E6B1EB1F73E942AD2BB3C02B7D7D7EE5A583B7C41FBBC0F92B2FA16",
    ),
    "m3r_stage_a_step": (
        "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_STAGE_A_REVB_WORKING.step",
        "359E304879C254BE54450AA9BAB4C614308CE2C9CD47CE1F79A741722098D36C",
    ),
    "m3r_stage_b_step": (
        "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_STAGE_B_REVB2_WORKING.step",
        "44BED33AEE41CFD170E744BBEEB2BD0B10BBD649C913ECA90D16FC4840A1126B",
    ),
    "m3r_stack": (
        "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml",
        "172F3603E458F670323925E644BC68623EE9C85FCA7AF1200FAE2576EB43C68B",
    ),
    "m5_geometry_decision": (
        "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json",
        "2A99484C6CE55B402CB06380F5DCB71D5A8B4BA622A371EEF72F4EC69EF124FF",
    ),
    "m5_output_manifest": (
        "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/12_release/M5_OUTPUT_MANIFEST_V1.json",
        "1B59752CAB73D6BE4976469E35D076985699DBE33D6D18FAEA9721684DEDABBD",
    ),
    "solar_fcstd": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd",
        "9D4D249A5D4EED7BDD8F3C08EC96737884A19523782112B1E72AD9EA0A1B65AB",
    ),
    "solar_step": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step",
        "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795",
    ),
    "solar_build_report": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V2.json",
        "4286EA2BBD84FB8EC33DDADE329534DA29194650AD22429245ECF8757B9AED1C",
    ),
    "solar_hdrm_latch": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V1.yaml",
        "BF8F76E654C56D31E2B9539B8239ED68CA0D8F513F5ECD1410AA7530ADDC06A5",
    ),
    "route_c_mesh_manifest": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_SWEEP_MESH_PACK_V9F/MANIFEST.json",
        "A90123580F73A7FF2DCE3F7A5BDB31DC31A1741D69A3CBFE837CB4DB53A00F25",
    ),
    "route_c_centerline": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_HARNESS_CENTERLINE_V9F.json",
        "177B6C5B8E5640018220D9C6E29ACBD6A8E900E573B560D28462B4614AEDBFFB",
    ),
    "route_c_clamp_register": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V9F.csv",
        "EA2D187D62537D0CC6043533AE5F1A24BA58837498C3173CD6556106FB021885",
    ),
    "route_c_exact_evaluator": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_EXACT_SWEEP_V9F.py",
        "9F26AC9A8DE5E2EEB57103F07B769EB43AC30A8FBAFD90FE8DF5D501FA8C8A7F",
    ),
    "local_contact_windows_source": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_LOCAL_CONTACT_WINDOWS_SOURCE_V1.json",
        "6B48C382D10E2C89EE56544707248B4D37DB55CB3BDABF5BAE39AF8AC470E47C",
    ),
}

ADJACENT_LINK_PAIRS = [
    ("base_link", "link1"),
    ("link1", "link2"),
    ("link2", "link3"),
    ("link3", "link4"),
    ("link4", "link5"),
    ("link5", "link6"),
    ("link6", "gripper_link"),
    ("gripper_link", "gripper_left"),
    ("gripper_link", "gripper_right"),
]

BUNDLE_SEGMENTS = [
    ("SEG-00_BUS_FEEDTHROUGH_AND_RISER", "base_link"),
    ("SEG-01_J1_ANNULAR_SERVICE_LOOP", "link1"),
    ("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", "link2"),
    ("SEG-03_J3_CARRIER_HYBRID_WRAP", "link3"),
    ("SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER", "link4"),
    ("SEG-05_J5_WRIST_WRAP", "link5"),
    ("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", "link6"),
    ("SEG-07A_WRIST_TAIL_DATA", "link6"),
    ("SEG-07B_WRIST_TAIL_POWER", "link6"),
]

PAIR_CLASS_NAMES = {
    ("A", "A"): "A-A",
    ("A", "F"): "A-F",
    ("A", "S"): "A-S",
    ("A", "R"): "A-R",
    ("A", "C"): "A-C",
    ("F", "F"): "F-F",
    ("F", "S"): "F-S",
    ("F", "R"): "F-R",
    ("C", "F"): "F-C",
    ("S", "S"): "S-S",
    ("R", "S"): "S-R",
    ("C", "S"): "S-C",
    ("R", "R"): "R-R",
    ("C", "R"): "R-C",
    ("C", "C"): "C-C",
}


def find_repo() -> Path:
    for candidate in [PACKAGE_DIR, *PACKAGE_DIR.parents]:
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root containing PROJECT_MAP.md not found")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def relpath(path: Path, repo: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


def pin_asset(repo: Path, relative: str, expected: str | None = None) -> dict[str, Any]:
    path = repo / relative
    if not path.is_file():
        raise RuntimeError(f"missing pinned asset: {relative}")
    actual = sha256_file(path)
    if expected is not None and actual != expected:
        raise RuntimeError(
            f"hash mismatch for {relative}: expected {expected}, got {actual}"
        )
    return {"path": relative, "bytes": path.stat().st_size, "sha256": actual}


def validate_source_pins(repo: Path) -> dict[str, dict[str, Any]]:
    return {
        name: pin_asset(repo, path, expected)
        for name, (path, expected) in sorted(SOURCE_PINS.items())
    }


def load_json(repo: Path, pin_name: str) -> Any:
    return json.loads((repo / SOURCE_PINS[pin_name][0]).read_text(encoding="utf-8"))


def load_route_entries(repo: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = load_json(repo, "route_c_mesh_manifest")
    group = next(row for row in manifest["files"] if row["group"] == "route_c_parts")
    entries = group["entries"]
    physical = [row for row in entries if row.get("geometry_role") == "PHYSICAL"]
    bundles = [row for row in entries if row.get("bundle_envelope") is True]
    if len(physical) != 121 or len(bundles) != 9:
        raise RuntimeError(
            f"Route-C object count drift: physical={len(physical)}, bundles={len(bundles)}"
        )
    return physical, bundles


def m5_asset(repo: Path, record: dict[str, Any], use_limit: str) -> dict[str, Any]:
    asset = pin_asset(repo, record["path"], record["sha256"])
    asset.update({
        "units": record.get("units"),
        "watertight": record.get("watertight"),
        "use_limit": use_limit,
    })
    for key in ("bounds_link_m", "bounds_gripper_link_m", "vertices", "faces"):
        if key in record:
            asset[key] = record[key]
    return asset


def base_proxy_assets(repo: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    proxy_dir = COLLISION_PACKAGE_DIR / "base_link_proxy_v2"
    step_path = proxy_dir / "B601_BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2.step"
    receipt_path = proxy_dir / "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2.json"
    validation_path = proxy_dir / "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V2.json"
    npz_path = proxy_dir / "BASE_LINK_OPERATIONAL_COLLISION_V2.npz"
    stl_path = proxy_dir / "BASE_LINK_OPERATIONAL_COLLISION_V2.stl"
    paths = [step_path, receipt_path, validation_path, npz_path, stl_path]
    if not any(path.exists() for path in paths):
        return None, {
            "status": "MISSING_OPERATIONAL_PROXY",
            "required_files": [relpath(path, repo) for path in paths],
        }
    if not all(path.is_file() for path in paths):
        raise RuntimeError("partial base_link operational proxy emission is fail-closed")

    receipt_text = receipt_path.read_text(encoding="utf-8")
    validation_text = validation_path.read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)
    validation = json.loads(validation_text)
    if receipt.get("schema") != "BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2":
        raise RuntimeError("base proxy receipt schema is not V2")
    if validation.get("schema") != "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V2":
        raise RuntimeError("base proxy validation schema is not V2")
    if not receipt.get("checks") or not all(receipt["checks"].values()):
        raise RuntimeError("base proxy receipt contains a failed or empty check set")
    if not validation.get("checks") or not all(validation["checks"].values()):
        raise RuntimeError("base proxy validation contains a failed or empty check set")
    for payload_name, payload in (("receipt", receipt), ("validation", validation)):
        if payload.get("next_stage_authorized") is not False:
            raise RuntimeError(f"base proxy {payload_name} improperly authorizes next stage")
        if payload.get("path_search_authorized") is not False:
            raise RuntimeError(f"base proxy {payload_name} improperly authorizes path search")
        if payload.get("system_pair_evaluation_authorized") is not False:
            raise RuntimeError(f"base proxy {payload_name} improperly authorizes pair evaluation")
        if payload.get("release_credit") is not False:
            raise RuntimeError(f"base proxy {payload_name} improperly grants release credit")
    npz_hash = sha256_file(npz_path)
    stl_hash = sha256_file(stl_path)
    required_receipt_tokens = [
        sha256_file(step_path),
        npz_hash,
        stl_hash,
        "A451B9150D00EC8E381AE69C0BB9D62B3A1FED1B1CD1AD373A719E28290F07C5",
        "7463C1309C3530A42BB32CB4A661FFA56575691DFB7A4BE801AAE9094BEB51E1",
    ]
    receipt_upper = receipt_text.upper()
    missing_tokens = [token for token in required_receipt_tokens if token not in receipt_upper]
    if missing_tokens:
        raise RuntimeError(f"base proxy receipt omits required pin(s): {missing_tokens}")
    if RAW_URDF_BASE_LINK_SHA256 in (npz_hash, stl_hash):
        raise RuntimeError("operational proxy illegally aliases the raw URDF base_link mesh")

    required_validation_tokens = [sha256_file(step_path), npz_hash, stl_hash, sha256_file(receipt_path)]
    validation_upper = validation_text.upper()
    missing_validation_tokens = [
        token for token in required_validation_tokens if token not in validation_upper
    ]
    if missing_validation_tokens:
        raise RuntimeError(
            f"base proxy validation omits required pin(s): {missing_validation_tokens}"
        )

    geometry = {
        "primary_step": {
            "path": relpath(step_path, repo),
            "bytes": step_path.stat().st_size,
            "sha256": sha256_file(step_path),
            "units": "mm",
            "frame": "base_link",
            "use_limit": "STEP_FIRST_TRACEABLE_COLLISION_GEOMETRY_NOT_MASS_OR_HARDWARE_AUTHORITY",
        },
        "canonical_machine_authority": {
            "path": relpath(npz_path, repo),
            "bytes": npz_path.stat().st_size,
            "sha256": npz_hash,
            "units": "m",
            "frame": "base_link",
        },
        "compatibility_mesh": {
            "path": relpath(stl_path, repo),
            "bytes": stl_path.stat().st_size,
            "sha256": stl_hash,
            "units": "m",
            "frame": "base_link",
        },
        "receipt": {
            "path": relpath(receipt_path, repo),
            "bytes": receipt_path.stat().st_size,
            "sha256": sha256_file(receipt_path),
        },
        "independent_validation": {
            "path": relpath(validation_path, repo),
            "bytes": validation_path.stat().st_size,
            "sha256": sha256_file(validation_path),
        },
        "substitution_scope": receipt["source_disposition"],
        "aggregate_proxy_volume_inflation_relative": receipt["brep"][
            "aggregate_proxy_volume_inflation_relative"
        ],
        "raw_accepted_urdf_base_mesh_forbidden": True,
        "pair_evaluation_state": "NOT_EVALUATED_FAIL_CLOSED",
    }
    return geometry, {
        "status": "PROXY_EMITTED_PENDING_SYSTEM_PAIR_EVALUATION",
        "receipt_schema": receipt.get("schema"),
        "receipt_verdict": receipt.get("verdict"),
        "validation_schema": validation.get("schema"),
        "validation_verdict": validation.get("verdict"),
        "geometry_validation_pass": True,
        "system_pair_evaluation_authorized": False,
        "path_search_authorized": False,
    }


def platform_objects(repo: Path, pins: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "object_id": "F::BUS",
            "category": "F",
            "lifecycle": "PHYSICAL",
            "representation_set": "BUS_OPERATIONAL_SINGLE_REPRESENTATION_REQUIRED",
            "active_when": "ALWAYS_IN_M01",
            "parent_frame": "S",
            "pose_source": "IDENTITY_IN_S",
            "geometry": {
                "container": pins["master_geometry_step"],
                "container_selector": None,
                "broadphase": {
                    "kind": "CLOSED_ANALYTIC_MAXIMUM_ENVELOPE_PROXY",
                    "bounds_S_mm": [[-183.0, -113.15, -113.15], [183.0, 113.15, 113.15]],
                    "covers_candidate_length_mm": [340.5, 366.0],
                    "safe_meaning": "SAFE_CORE_ONLY",
                    "overlap_meaning": "UNKNOWN_NOT_TRUE_INTERFERENCE",
                    "status": "SCREENING_CANDIDATE_NOT_FLIGHT_AUTHORITY",
                },
                "narrowphase": None,
            },
            "authority": "R2_MASTER_BUS_IS_A_SIX_PRIMITIVE_ENVELOPE_PROXY_NOT_FLIGHT_REPRESENTATIVE",
            "status": "CONSERVATIVE_SCREENING_PROXY_DEFINED__NARROWPHASE_AND_EXTERNAL_PROTRUSIONS_MISSING",
        },
        {
            "object_id": "F::LOAD_BRIDGE",
            "category": "F",
            "lifecycle": "PHYSICAL",
            "representation_set": "LOAD_BRIDGE_SINGLE_REPRESENTATION",
            "active_when": "ALWAYS_IN_M01",
            "parent_frame": "S",
            "pose_source": pins["load_bridge_datums"],
            "geometry": {
                "container": pins["load_bridge_step"],
                "container_selector": "ROOT_CANDIDATE",
                "broadphase": pins["load_bridge_step"],
                "narrowphase": pins["load_bridge_step"],
            },
            "authority": "CANDIDATE_BREP_WITH_PHYSICAL_FITUP_HOLD",
            "status": "MISSING_OPERATIONAL_INSTALLED_POSE_AND_INTERFACE_PATCH_BINDING",
        },
        {
            "object_id": "F::M3R_STAGE_A",
            "category": "F",
            "lifecycle": "PHYSICAL",
            "representation_set": "M3R_TWO_SOLID_COMPOUND_ONE_LOAD_ONLY",
            "active_when": "ALWAYS_IN_M01",
            "parent_frame": "S",
            "pose_source": pins["m3r_stack"],
            "geometry": {
                "container": pins["m3r_fcstd"],
                "container_selector": "M3R_STAGE_A_INTERFACE_RING_REVB_WORKING",
                "broadphase": pins["m3r_stage_a_step"],
                "narrowphase_candidate": pins["m3r_stage_a_step"],
                "expected_solid_count": 1,
                "expected_local_bbox_mm": [[-75.0, -75.0, -5.595], [75.0, 75.0, 2.405]],
                "expected_volume_mm3": 127784.800333,
            },
            "authority": "DESIGN_LEVEL_STAGE_BREP_NOT_AS_BUILT_OR_FLIGHT_QUALIFIED",
            "status": "DESIGN_GEOMETRY_AVAILABLE__INSTALLED_POSE_AND_INTERFACE_PATCH_BINDING_INCOMPLETE",
        },
        {
            "object_id": "F::M3R_STAGE_B",
            "category": "F",
            "lifecycle": "PHYSICAL",
            "representation_set": "M3R_TWO_SOLID_COMPOUND_ONE_LOAD_ONLY",
            "active_when": "ALWAYS_IN_M01",
            "parent_frame": "S",
            "pose_source": pins["m3r_stack"],
            "geometry": {
                "container": pins["m3r_fcstd"],
                "container_selector": "M3R_STAGE_B_LOAD_ADAPTER_REVB2_WORKING",
                "broadphase": pins["m3r_stage_b_step"],
                "narrowphase_candidate": pins["m3r_stage_b_step"],
                "expected_solid_count": 1,
                "expected_local_bbox_mm": [[-85.0, -85.0, -12.0], [85.0, 85.0, 0.0]],
                "expected_volume_mm3": 161966.032228,
            },
            "authority": "DESIGN_LEVEL_STAGE_BREP_NOT_AS_BUILT_OR_FLIGHT_QUALIFIED",
            "status": "DESIGN_GEOMETRY_AVAILABLE__INSTALLED_POSE_AND_INTERFACE_PATCH_BINDING_INCOMPLETE",
        },
    ]


def arm_objects(repo: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    decision = load_json(repo, "m5_geometry_decision")
    objects: list[dict[str, Any]] = []
    proxy_geometry, proxy_state = base_proxy_assets(repo)
    components = decision["components"]

    base_fallback = components["base_link"]
    base_geometry = {
        "candidate_source_surface": m5_asset(
            repo, base_fallback["local_surface"], base_fallback["use_limit"]
        ),
        "candidate_broadphase": m5_asset(
            repo,
            base_fallback["conservative_broadphase_box"],
            "CONSERVATIVE_AABB_ONLY",
        ),
        "operational_proxy": proxy_geometry,
    }
    objects.append({
        "object_id": "A::base_link",
        "category": "A",
        "lifecycle": "PHYSICAL",
        "representation_set": "B601_BASE_LINK_OPERATIONAL_PROXY_ONLY_RAW_URDF_MESH_FORBIDDEN",
        "active_when": "ALWAYS_IN_M01",
        "parent_frame": "base_link",
        "pose_source": "ACCEPTED_URDF_FK",
        "geometry": base_geometry,
        "authority": "WP11_O2_A_CAD_PHYSICAL_GEOMETRY_PLUS_ACCEPTED_URDF_KINEMATICS",
        "status": proxy_state["status"],
    })

    for link in ["link1", "link2", "link3", "link4", "link5", "link6"]:
        row = components[link]
        objects.append({
            "object_id": f"A::{link}",
            "category": "A",
            "lifecycle": "PHYSICAL",
            "representation_set": f"B601_{link}_M5_CAD_SURFACE_ONLY",
            "active_when": "ALWAYS_IN_M01",
            "parent_frame": link,
            "pose_source": "ACCEPTED_URDF_FK_PLUS_WP11_D_I_CALIBRATION_REQUIRED",
            "geometry": {
                "broadphase": m5_asset(
                    repo, row["conservative_broadphase_box"], "CONSERVATIVE_AABB_ONLY"
                ),
                "narrowphase_candidate": m5_asset(
                    repo, row["local_surface"], row["use_limit"]
                ),
            },
            "authority": "M5_SOURCE_BOUND_SCREENING_SURFACE_NOT_CONTACT_OR_STRENGTH_AUTHORITY",
            "status": "SCREENING_GEOMETRY_AVAILABLE__OPERATIONAL_NARROWPHASE_PROMOTION_ABSENT",
        })

    active = decision["active_gripper_r1"]
    gripper_map = {
        "gripper_link": ("palm", "ALWAYS_IN_M01"),
        "gripper_left": ("left_finger", "REQUIRES_gripper_joint1_m"),
        "gripper_right": ("right_finger", "REQUIRES_gripper_joint2_m"),
    }
    for link, (key, active_when) in gripper_map.items():
        row = active[key]
        state = (
            "SCREENING_GEOMETRY_AVAILABLE__CONTACT_AUTHORITY_HOLD"
            if link == "gripper_link"
            else "MISSING_EXPLICIT_M01_PRISMATIC_STATE__CONTACT_AUTHORITY_HOLD"
        )
        objects.append({
            "object_id": f"A::{link}",
            "category": "A",
            "lifecycle": "PHYSICAL",
            "representation_set": f"B601_R1_{link}_ONLY",
            "active_when": active_when,
            "parent_frame": link,
            "geometry_frame": row["frame"],
            "pose_source": "ACCEPTED_URDF_FK_PLUS_M5_R1_GRIPPER_MOTION_CONTRACT",
            "geometry": {
                "broadphase": m5_asset(repo, row["broadphase_box"], "CONSERVATIVE_AABB_ONLY"),
                "narrowphase_candidate": m5_asset(
                    repo, row["local_surface"], "R1_GEOMETRY_SCREENING_ONLY_CONTACT_AND_STRENGTH_HOLD"
                ),
            },
            "authority": "R1_NEUTRAL_GRIPPER_GEOMETRY_WITH_UNRATIFIED_CONFIGURATION_TO_TRAVEL_MAP",
            "status": state,
        })

    if len(objects) != 10:
        raise RuntimeError(f"arm object count drift: {len(objects)}")
    return objects, proxy_state


def solar_objects(pins: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    objects = []
    for side in ("LEFT", "RIGHT"):
        for leaf in (1, 2, 3):
            objects.append({
                "object_id": f"S::{side}_LEAF_{leaf}",
                "category": "S",
                "lifecycle": "PHYSICAL",
                "representation_set": f"SOLAR_{side}_LEAF_{leaf}_SINGLE_STATE_ONLY",
                "active_when": "REQUIRES_EXPLICIT_SOLAR_STATE",
                "parent_frame": "S",
                "pose_source": "FCSTD_OBJECT_PLACEMENT_SELECTED_BY_EXPLICIT_STATE",
                "geometry": {
                    "container": pins["solar_fcstd"],
                    "container_selector_by_state": {
                        "STOWED": f"R2_{side}_LEAF{leaf}_STOWED",
                        "DEPLOYED": f"R2_{side}_LEAF{leaf}_DEPLOYED",
                    },
                    "forbidden_combined_source": pins["solar_step"],
                    "forbidden_reason": "STEP_CONTAINS_6_STOWED_PLUS_6_DEPLOYED_LEAVES_AND_10_KEEPOUT_SOLIDS",
                },
                "authority": "SOLAR_R2_CANDIDATE_SINGLE_STATE_SELECTOR_REQUIRED",
                "status": "MISSING_M01_SOLAR_STATE_LATCH_AND_HDRM_BINDING",
            })
    return objects


def solar_virtual_constraint_candidates(pins: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    selectors = []
    for side in ("LEFT", "RIGHT"):
        selectors.extend([
            (f"R2_{side}_ROOT_HINGE_KEEPOUT", "ROOT_HINGE"),
            (f"R2_{side}_INTER_HINGE2_KEEPOUT", "INTERLEAF_HINGE"),
            (f"R2_{side}_INTER_HINGE3_KEEPOUT", "INTERLEAF_HINGE"),
            (f"R2_{side}_HDRM1_KEEPOUT", "HDRM"),
            (f"R2_{side}_HDRM2_KEEPOUT", "HDRM"),
        ])
    return [
        {
            "object_id": f"K::{selector}",
            "category": "K",
            "lifecycle": "VIRTUAL_KEEPOUT",
            "geometry": {
                "container": pins["solar_fcstd"],
                "container_selector": selector,
                "units": "mm",
            },
            "active_when": "REQUIRES_EXPLICIT_SOLAR_STATE_AND_LATCH_HDRM_BINDING",
            "authority": "CANDIDATE_ENVELOPE_ONLY_PHYSICAL_HARDWARE_NOT_MODELLED",
            "status": "NOT_IN_150_OBJECT_PAIR_UNIVERSE_UNTIL_STATE_ACTIVATION_IS_RATIFIED",
            "kind": kind,
        }
        for selector, kind in selectors
    ]


def route_c_objects(
    repo: Path,
    physical: list[dict[str, Any]],
    bundles: list[dict[str, Any]],
    pins: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mesh_dir = repo / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_SWEEP_MESH_PACK_V9F"
    physical_objects = []
    for row in sorted(physical, key=lambda item: item["name"]):
        mesh_path = mesh_dir / row["file"]
        mesh_asset = pin_asset(repo, relpath(mesh_path, repo), row["sha256"])
        mesh_asset.update({
            "units": "mm",
            "triangles": row["tris"],
            "watertight": None,
            "use_limit": "V9F_DESIGN_CANDIDATE_CLEARANCE_TRIANGLES_NOT_CONTACT_OR_QUALIFICATION_AUTHORITY",
        })
        physical_objects.append({
            "object_id": f"R::{row['name']}",
            "category": "R",
            "lifecycle": "PHYSICAL",
            "representation_set": f"ROUTE_C_PART::{row['name']}",
            "active_when": "ALWAYS_IN_M01_IF_ROUTE_C_CANDIDATE_IS_SELECTED",
            "parent_frame": row["host_link"],
            "pose_source": "PINNED_V9F_HOST_AND_MOTION_CLASS_LOGIC_REQUIRES_INDEPENDENT_ADAPTER",
            "geometry": {"narrowphase_candidate": mesh_asset},
            "kind": row.get("kind"),
            "motion_class": row.get("motion_class") or "HOST_FIXED_UNLESS_REGISTERED_OTHERWISE",
            "authority": "V9F_DESIGN_CANDIDATE_NO_RELEASE_CREDIT",
            "status": "DESIGN_CANDIDATE_GEOMETRY_AVAILABLE__PAIR_AND_INTERFACE_PATCH_EVALUATION_INCOMPLETE",
        })

    bundle_names = {row["name"] for row in bundles}
    logical_objects = []
    for segment_id, host in BUNDLE_SEGMENTS:
        expected_name = "RC-BUNDLE-" + segment_id.replace("_", "-")
        if expected_name not in bundle_names:
            raise RuntimeError(f"missing Route-C logical bundle entry: {expected_name}")
        logical_objects.append({
            "object_id": f"C::{segment_id}",
            "category": "C",
            "lifecycle": "LOGICAL_BUNDLE",
            "representation_set": f"ROUTE_C_BUNDLE::{segment_id}",
            "active_when": "ALWAYS_IN_M01_IF_ROUTE_C_CANDIDATE_IS_SELECTED",
            "parent_frame": host,
            "pose_source": "CENTERLINE_PLUS_ACCEPTED_URDF_FK_REQUIRES_SIDE_EFFECT_FREE_ADAPTER",
            "geometry": {
                "centerline": pins["route_c_centerline"],
                "container_selector": segment_id,
                "diameter_mm": 9.0,
                "runtime_representation": "CAPSULE_CHAIN_REQUIRED_NOT_PREEMITTED",
            },
            "authority": "LOGICAL_COLLISION_ENVELOPE_NOT_A_HARDWARE_SOLID",
            "status": "MISSING_RUNTIME_CAPSULE_CHAIN_AND_COMPLETE_PAIR_EVALUATION",
        })
    return physical_objects, logical_objects


def extract_legacy_segment_sets(repo: Path) -> dict[str, list[str]]:
    path = repo / SOURCE_PINS["route_c_exact_evaluator"][0]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    value = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "SEG_INTENDED_PARTS"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            break
    if value is None:
        raise RuntimeError("SEG_INTENDED_PARTS assignment not found")
    return {key: sorted(items) for key, items in sorted(value.items())}


def candidate_contact_windows(
    repo: Path, route_object_ids: set[str], cable_object_ids: set[str]
) -> list[dict[str, Any]]:
    window_source = load_json(repo, "local_contact_windows_source")
    if (
        window_source.get("schema") != "M01_LOCAL_CONTACT_WINDOWS_SOURCE_V1"
        or window_source.get("rule_count") != 15
        or window_source.get("expanded_candidate_pair_record_count") != 55
        or window_source.get("active_pair_exception_count") != 0
    ):
        raise RuntimeError("local contact-window source contract drift")
    rules = window_source["rules"]
    expanded = []
    for rule in rules:
        cable = f"C::{rule['segment']}"
        if cable not in cable_object_ids:
            raise RuntimeError(f"contact window references unknown cable: {cable}")
        for part_id in rule["allowed_part_ids"]:
            route = f"R::{part_id}"
            if route not in route_object_ids:
                raise RuntimeError(f"contact window references unknown Route-C part: {route}")
            expanded.append({
                "rule_id": rule["rule_id"],
                "canonical_pair": sorted([cable, route]),
                "mode": "INTENDED_CONTACT_WINDOW_CANDIDATE",
                "active_when": "M01_SCENE_STATE_BOUND_AND_ALL_SPATIAL_PREDICATES_PASS",
                "spatial_window": {
                    "segment": rule["segment"],
                    "section": rule["section"],
                    "cumulative_arclength_mm": rule["s_window_mm"],
                    "station_id": None,
                    "clamp_id": rule["witness_clamp_id"],
                    "bore_axis_pass": "REQUIRED_NOT_INHERITED",
                    "surface_selectors": None,
                },
                "status": "CANDIDATE_ONLY_NOT_AN_ACTIVE_PAIR_EXCEPTION__SURFACE_PATCH_AND_RUNTIME_PREDICATES_MISSING",
            })
    return sorted(expanded, key=lambda row: (row["rule_id"], row["canonical_pair"]))


def pair_class(a: str, b: str) -> str:
    key = tuple(sorted((a, b)))
    try:
        return PAIR_CLASS_NAMES[key]
    except KeyError as exc:
        raise RuntimeError(f"unregistered category pair: {key}") from exc


def render_pair_csv(objects: list[dict[str, Any]]) -> tuple[bytes, dict[str, Any]]:
    fieldnames = [
        "pair_index", "object_a", "category_a", "object_b", "category_b",
        "pair_class", "policy", "status", "reason",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    adjacent = {
        tuple(sorted((f"A::{left}", f"A::{right}")))
        for left, right in ADJACENT_LINK_PAIRS
    }
    class_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    ordered = sorted(objects, key=lambda row: row["object_id"])
    for index, (left, right) in enumerate(itertools.combinations(ordered, 2), start=1):
        pair = (left["object_id"], right["object_id"])
        canonical = tuple(sorted(pair))
        klass = pair_class(left["category"], right["category"])
        if canonical in adjacent:
            policy = "EXCEPT_ADJACENT_JOINT"
            status = "EXCEPTED"
            reason = "ONLY_LEGAL_PAIR_WIDE_EXCLUSION_FROM_PINNED_MECHANICAL_CONTRACT"
        else:
            policy = "FORBID"
            status = "UNASSESSED_FAIL_CLOSED"
            reason = "NO_COMPLETE_HASH_BOUND_PAIR_EVALUATION"
        class_counts[klass] += 1
        status_counts[status] += 1
        writer.writerow({
            "pair_index": index,
            "object_a": left["object_id"],
            "category_a": left["category"],
            "object_b": right["object_id"],
            "category_b": right["category"],
            "pair_class": klass,
            "policy": policy,
            "status": status,
            "reason": reason,
        })
    payload = stream.getvalue().encode("utf-8")
    return payload, {
        "expected_pairs": sum(class_counts.values()),
        "class_counts": dict(sorted(class_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
    }


def build_payloads(repo: Path) -> tuple[bytes, bytes, bytes]:
    pins = validate_source_pins(repo)
    physical, bundles = load_route_entries(repo)
    f_objects = platform_objects(repo, pins)
    a_objects, proxy_state = arm_objects(repo)
    s_objects = solar_objects(pins)
    solar_keepout_candidates = solar_virtual_constraint_candidates(pins)
    r_objects, c_objects = route_c_objects(repo, physical, bundles, pins)
    objects = f_objects + a_objects + s_objects + r_objects + c_objects
    objects = sorted(objects, key=lambda row: row["object_id"])

    category_counts = Counter(row["category"] for row in objects)
    expected_categories = {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6}
    if dict(sorted(category_counts.items())) != expected_categories:
        raise RuntimeError(f"collision object count drift: {dict(category_counts)}")
    ids = [row["object_id"] for row in objects]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate collision object id")

    route_ids = {row["object_id"] for row in r_objects}
    cable_ids = {row["object_id"] for row in c_objects}
    contact_windows = candidate_contact_windows(repo, route_ids, cable_ids)
    legacy_sets = extract_legacy_segment_sets(repo)
    j4 = "SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER"
    non_j4_sets = {key: value for key, value in legacy_sets.items() if key != j4}
    non_j4_memberships = sum(len(value) for value in non_j4_sets.values())
    if len(non_j4_sets) != 8 or non_j4_memberships != 91:
        raise RuntimeError(
            f"legacy segment-wide exclusion audit drift: groups={len(non_j4_sets)}, memberships={non_j4_memberships}"
        )

    adjacent_exceptions = [
        {
            "rule_id": f"ADJ-{index:02d}",
            "canonical_pair": sorted([f"A::{left}", f"A::{right}"]),
            "mode": "ADJACENT_JOINT",
            "active_when": "ALWAYS",
            "source_pin": "collision_contract",
            "status": "ACTIVE_ONLY_LEGAL_PAIR_WIDE_EXCLUSION",
        }
        for index, (left, right) in enumerate(ADJACENT_LINK_PAIRS, start=1)
    ]

    registry = {
        "schema": "SYSTEM_COLLISION_REGISTRY_V1",
        "generated_utc": "DETERMINISTIC_REGISTRY_NO_WALLCLOCK",
        "authority": "STRUCTURAL_ENUMERATION_AND_FAIL_CLOSED_POLICY_ONLY__NO_COLLISION_PASS_OR_PATH_SEARCH_AUTHORITY",
        "scene": {
            "id": "M01_STOW_TO_RELEASE_CLEAR",
            "required_bindings": [
                "q6", "gripper_joint1_m", "gripper_joint2_m", "solar_state",
                "solar_latch_state", "arm_hdrm_state_t0_minus",
                "arm_hdrm_state_t0_plus", "target_present", "target_attached",
            ],
            "binding_status": "INCOMPLETE",
        },
        "source_pins": pins,
        "objects": objects,
        "object_summary": {
            "known_active_object_count": len(objects),
            "category_counts": dict(sorted(category_counts.items())),
            "conditional_virtual_keepout_candidate_count_not_yet_active": len(solar_keepout_candidates),
            "omitted_missing_hardware_is_not_silently_ignored": True,
        },
        "conditional_virtual_constraint_candidates": solar_keepout_candidates,
        "conditional_pair_universe_rule": "WHEN_ANY_K_OBJECT_IS_ACTIVATED_A_NEW_REGISTRY_VERSION_MUST_ENUMERATE_ALL_K_INVOLVING_PAIRS_BEFORE_SEARCH",
        "pair_policy": {
            "default": "FORBID",
            "unknown": "ABORT",
            "missing_asset": "ABORT",
            "missing_pose_or_state": "ABORT",
            "hash_mismatch": "ABORT",
            "empty_comparison_set": "ABORT",
            "nonfinite": "ABORT",
            "backend_failure": "ABORT",
            "wildcard_or_manual_exception": "FORBIDDEN",
        },
        "active_pair_exceptions": adjacent_exceptions,
        "candidate_local_contact_windows": contact_windows,
        "candidate_local_contact_window_count": len(contact_windows),
        "legacy_behavior_rejected": {
            "segment_wide_sets": non_j4_sets,
            "segment_wide_group_count": len(non_j4_sets),
            "segment_part_membership_count": non_j4_memberships,
            "disposition": "NOT_IMPORTED__MUST_BE_REPLACED_BY_SECTION_ARCLENGTH_STATION_AND_SURFACE_PATCH_RULES",
            "j4_segment_wide_set_present_in_source_but_runtime_suppressed": len(legacy_sets[j4]),
            "fixed_route_c_part_own_host_skip": {
                "present_in_source": True,
                "disposition": "NOT_IMPORTED__EXACT_FIXED_INTERFACE_PATCH_REQUIRED",
            },
        },
        "banned_representations": [{
            "asset": "accepted_URDF_raw_base_link_collision_STL",
            "sha256": RAW_URDF_BASE_LINK_SHA256,
            "reason": "WP11_F_01_OWNER_DELETED_DESKTOP_PLATE",
            "fallback": "ABORT",
        }],
        "known_missing_objects_or_authorities": [
            "ARM_HDRM_AND_STOW_SUPPORT_GEOMETRY",
            "SENSOR_PACKAGE_AND_CAMERA_MOUNT",
            "TARGET_AND_TARGET_INTERFACE_GEOMETRY",
            "SOLAR_ROOT_AND_INTERLEAF_HINGE_PHYSICAL_GEOMETRY",
            "SOLAR_HDRM_LATCH_AND_DEPLOYED_STOP_PHYSICAL_GEOMETRY",
            "FASTENER_AND_LOCATOR_COLLISION_REPRESENTATIONS",
            "COMPLETE_BUS_PANEL_CLOSURE_AND_EXTERNAL_PROTRUSIONS",
        ],
        "base_link_proxy_state": proxy_state,
        "gate_semantics": {
            "structural_registry_complete": True,
            "complete_system_collision_pass": False,
            "path_search_legal": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
    }
    registry_bytes = (json.dumps(registry, indent=2, sort_keys=True) + "\n").encode("utf-8")
    pair_bytes, pair_summary = render_pair_csv(objects)
    if pair_summary["expected_pairs"] != 11175:
        raise RuntimeError(f"pair universe drift: {pair_summary['expected_pairs']}")
    if pair_summary["status_counts"] != {
        "EXCEPTED": 9,
        "UNASSESSED_FAIL_CLOSED": 11166,
    }:
        raise RuntimeError(f"pair status drift: {pair_summary['status_counts']}")

    gate = {
        "schema": "SYSTEM_COLLISION_REGISTRY_GATE_V1",
        "generated_utc": "DETERMINISTIC_REGISTRY_GATE_NO_WALLCLOCK",
        "authority": "STATIC_COLLISION_UNIVERSE_AUDIT_ONLY__NO_M01_EXECUTION_AUTHORITY",
        "source_pin_count": len(pins),
        "source_hash_mismatch_count": 0,
        "object_counts": dict(sorted(category_counts.items())),
        "known_active_object_count": len(objects),
        "pair_coverage": pair_summary,
        "adjacent_pair_exceptions": 9,
        "active_non_adjacent_pair_exceptions": 0,
        "candidate_local_contact_window_records": len(contact_windows),
        "conditional_virtual_keepout_candidates_not_in_current_pair_universe": len(solar_keepout_candidates),
        "legacy_segment_wide_groups_rejected": len(non_j4_sets),
        "legacy_segment_part_memberships_rejected": non_j4_memberships,
        "fixed_own_host_object_skip_inherited": False,
        "raw_urdf_base_link_mesh_consumed_by_objects": False,
        "base_link_proxy_state": proxy_state,
        "structural_registry_complete": True,
        "pair_universe_enumerated": True,
        "complete_object_authority": False,
        "complete_hash_bound_acm": False,
        "complete_system_collision_pass": False,
        "path_search_executed": False,
        "pre_search_ready": False,
        "blockers": [
            "OWNER_OPTION_A_SELECTION_ABSENT",
            "M01_SCENE_STATE_BINDINGS_INCOMPLETE",
            "PLATFORM_BUS_LOAD_BRIDGE_AND_M3R_OPERATIONAL_SELECTORS_OR_PATCHES_INCOMPLETE",
            "SOLAR_SINGLE_STATE_HDRM_AND_LATCH_AUTHORITY_INCOMPLETE",
            "10_SOLAR_VIRTUAL_KEEPOUT_CANDIDATES_NOT_ACTIVATED_OR_PAIRED",
            "ARM_NON_BASE_LINK_NARROWPHASE_PROMOTION_INCOMPLETE",
            "ROUTE_C_OWN_HOST_AND_SERVING_HARDWARE_PATCHES_INCOMPLETE",
            "11166_NON_EXCEPTED_PAIRS_UNASSESSED",
            "CONTINUOUS_EDGE_CERTIFICATE_BACKEND_ABSENT",
            "RUNTIME_MEMORY_ADMISSION_NOT_GRANTED",
        ],
        "verdict": "SYSTEM_COLLISION_REGISTRY_STRUCTURALLY_COMPLETE__11175_PAIRS_ENUMERATED__11166_UNASSESSED_FAIL_CLOSED__NO_PATH_SEARCH_AUTHORITY",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    gate_bytes = (json.dumps(gate, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return registry_bytes, pair_bytes, gate_bytes


def output_map(repo: Path) -> dict[str, bytes]:
    registry, pairs, gate = build_payloads(repo)
    return {REGISTRY_NAME: registry, PAIR_NAME: pairs, GATE_NAME: gate}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare deterministic payloads without writing")
    parser.add_argument("--output-dir", type=Path, default=PACKAGE_DIR)
    args = parser.parse_args()
    repo = find_repo()
    payloads = output_map(repo)
    output_dir = args.output_dir.resolve()
    if args.check:
        mismatches = []
        for name, payload in payloads.items():
            path = output_dir / name
            if not path.is_file() or path.read_bytes() != payload:
                mismatches.append(name)
        result = {"check": "PASS" if not mismatches else "FAIL", "mismatches": mismatches}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not mismatches else 1
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        (output_dir / name).write_bytes(payload)
    print(json.dumps({
        "written": sorted(payloads),
        "path_search_executed": False,
        "next_stage_authorized": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
