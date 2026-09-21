#!/usr/bin/env python3
"""Independent fail-closed validation for the Unified R2 prebind package."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Callable
import xml.etree.ElementTree as ET

import yaml


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]

EXPECTED_SOURCES = {
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json": (5440, "0C0994E3E59EDBB5FD43B1D75FC048C8414A735D28CA4FC36E8FC23E03692577"),
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml": (26528, "DCE40C1DB8A318A077F0DD92A47F236BE55EAF2FD32B4E514D2BB67C9B19B4A2"),
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml": (6236, "67293323A45237FB9B415871A4160732EFB156DE74776C9E11ABA9C4202134CA"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/12_release/MECHANICAL_ENGINEERING_RELEASE_GATE_V1.json": (48538, "2D9C8580701BD087A2DB52F57AE9ED23A919DEBC7476727467214411F952859E"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json": (29415, "105BCB020FAF9F535C3A18F9A37831679F89070A8CA69C5960F959A686F332C1"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/PRODUCT_STRUCTURE_V1.yaml": (48807, "0F9897EF4E41666DDB29CB0FC621DD737FDD8CCDE3F5527030E53A9D1604681A"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.FCStd": (579603, "013DA84FE9A5C388252DB18516628411C484BB818959FA1A5CF8D950485636E7"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.step": (1373004, "8C85585E9C051AEBB849E48F56354B48BF4204F61103B550BD92FC77BA99EA9E"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V2.json": (16118, "4286EA2BBD84FB8EC33DDADE329534DA29194650AD22429245ECF8757B9AED1C"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd": (23733, "9D4D249A5D4EED7BDD8F3C08EC96737884A19523782112B1E72AD9EA0A1B65AB"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step": (131834, "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml": (223714, "3FD2557318E98748A37927977FA2925C18803668FE16391D824C184F646486BB"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp11_cad_urdf_registration/receipt.json": (23885, "83E36583E370BD3A6563330C9B34E0CDB0400DC6952BFC91D9DA5C77536BCB9B"),
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf": (11321, "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml": (13398, "C31938668746C6B5D3C8C6879D8F2B14BDF8FE78000274ADD8411E7FBB58CEF6"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/01_interface/GRIPPER_ACTIVE_CONSUMPTION_POINTER_V1.yaml": (1010, "B0DDADE5F5CCD6F6CFF2A9B0E7EA23908CE7558EBA002BE26A193D4DEC38A7D8"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/02_gate/GRIPPER_VELOCITY_UNIT_GATE_V1.json": (2692, "A93B08B56CB46623A0E8B96234B7FA48C1C59492F950A543BB164AD4CF4A0E7B"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/checkpoint_b/ROUTE_C_CHECKPOINT_B_GATE_V1.json": (14887, "C9E7526D790E1FB7F5522A113EDF41F5913207C15A68E12468FD9EBA157349D1"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_C2_01_REGISTRY_SKELETON_V1.yaml": (19773, "6264A0A45F6A497787F3D96205CEF7799A19A225CD23CEA66D5AD31E335A3E8E"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack/TERMINAL_DECISION_PACK_GATE_V1.json": (25452, "0C9DC0353630A402745B3CE5235DC75A2FC51A65B189E2580A7FA5484A5F3325"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack/P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml": (23043, "679DC5D2BA2B814F584379C28E47A9F487D03277F0F1EAA45DFB85D150367D25"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack/LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml": (46441, "5ED037AE057F7119678DECF890C9C0E64740C1443E5E9B9682FC09B8610046F6"),
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/09_downstream_rebind/SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json": (6345, "7FD3C63AF46BE4BA3055CCF87EFD1A71C13517EC872B1F3EDC52304B070D9153"),
    "30_simulation/sim_13_physics_gated_embodied_grasping/config/sim13_bootstrap.json": (647, "4624C5BA2A016A002531FCF6FB6EFD661AA488D6C9420197789263D4B0E42B8D"),
    "30_simulation/sim_13_physics_gated_embodied_grasping/src/mechanical_asset_loader.py": (23753, "C0797E5786888E357784369F6601B380C4E94FAE76B3FBFCF4C46717A833E851"),
}

EXPECTED_OUTPUTS = {
    "UNIFIED_R2_CAD_BRIEF_V1.md",
    "UNIFIED_R2_URDF_DESIGN_LEDGER_V1.yaml",
    "UNIFIED_R2_DIGITAL_PROTOTYPE_REBASE_CONTRACT_V1.yaml",
    "UNIFIED_R2_PREBIND_READINESS_V1.json",
    "UNIFIED_R2_PREBIND_GATE_V1.json",
    "UNIFIED_R2_PREBIND_RECEIPT_V1.md",
    "UNIFIED_R2_PREBIND_SHA256.csv",
}

EXPECTED_CONFIGURATIONS = [
    ("C01", "DEPLOYED_NOMINAL", 31.022864807342987),
    ("C02", "LEFT_PANEL_FAIL", 31.022864807342987),
    ("C03", "RIGHT_PANEL_FAIL", 31.022864807342987),
    ("C04", "BOTH_PANEL_FAIL", 31.022864807342987),
    ("C05", "ARM_STOWED_ONORBIT", 31.022864807342987),
    ("C06", "ARM_TASK_READY", 31.022864807342987),
    ("C07", "PREGRASP", 31.022864807342987),
    ("C08", "TARGET_CAPTURE_22KG", 53.022864807342984),
    ("C09", "TARGET_CAPTURE_150KG", 181.02286480734298),
]

FALSE_AUTHORITY_FLAGS = {
    "engineering_specification_complete",
    "geometry_execution_authorized",
    "full_flex_validation_authorized",
    "consumer_rebind_authorized",
    "rebase_execution_authorized",
    "route_c_cad_authorized",
    "heavy_solver_authorized",
    "sim13_baseline_mutation_authorized",
    "production_dynamics_ready",
    "physical_contact_ready",
    "physics_gated_rl_ready",
    "owner_accepted",
    "next_stage_authorized",
    "release_credit",
    "terminal_release_candidate_generated",
}

EXPECTED_CONTRACT_TOP_LEVEL_KEYS = {
    "schema",
    "generated_date_local",
    "status",
    "artifact_class",
    "purpose",
    "predecessor_state",
    "future_baseline",
    "component_rebase_matrix",
    "frame_contract",
    "solar_r2_root_frame_reconciliation",
    "bus_12u_geometry_authority",
    "configuration_contract",
    "future_output_contract",
    "validation_contract",
    "current_authority_inputs",
    "authorization_state_machine",
    "entry_sequence",
    "execution_record",
    "source_pins",
    "authority_flags",
}

checks: list[dict[str, Any]] = []


def check(identifier: str, name: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception as exc:
        checks.append({"id": identifier, "name": name, "pass": False, "detail": f"{type(exc).__name__}: {exc}"})
    else:
        checks.append({"id": identifier, "name": name, "pass": True, "detail": "PASS"})


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def independently_parse_urdf(path: Path) -> dict[str, Any]:
    robot = ET.parse(path).getroot()
    links = robot.findall("link")
    joints = robot.findall("joint")
    link_names = {link.get("name") for link in links}
    child_names = {joint.find("child").get("link") for joint in joints}
    masses = [float(link.find("inertial/mass").get("value")) for link in links]
    mesh_elements = robot.findall("link/visual/geometry/mesh") + robot.findall("link/collision/geometry/mesh")
    mesh_paths = [path.parent / mesh.get("filename") for mesh in mesh_elements]
    return {
        "robot_name": robot.get("name"),
        "link_count": len(links),
        "joint_count": len(joints),
        "root_links": sorted(link_names - child_names),
        "joint_type_counts": dict(sorted(Counter(joint.get("type") for joint in joints).items())),
        "links_with_inertial": len(masses),
        "total_declared_link_mass_kg": sum(masses),
        "visual_count": len(robot.findall("link/visual")),
        "collision_count": len(robot.findall("link/collision")),
        "mesh_reference_occurrence_count": len(mesh_elements),
        "unique_mesh_reference_count": len({mesh.get("filename") for mesh in mesh_elements}),
        "all_local_mesh_references_exist": all(mesh_path.is_file() for mesh_path in mesh_paths),
    }


def assert_false_authority_map(flags: dict[str, Any]) -> None:
    require(set(flags) == FALSE_AUTHORITY_FLAGS, f"authority flag set drift: {set(flags) ^ FALSE_AUTHORITY_FLAGS}")
    require(all(flags[key] is False for key in FALSE_AUTHORITY_FLAGS), "one or more authority flags became true")


def evaluate_all_required_exact_true(inputs: dict[str, Any]) -> bool:
    return bool(inputs) and all(value is True for value in inputs.values())


def validate_sources() -> None:
    for relative, (expected_bytes, expected_hash) in EXPECTED_SOURCES.items():
        path = ROOT / relative
        require(path.is_file(), f"missing {relative}")
        require(path.stat().st_size == expected_bytes, f"byte drift {relative}")
        require(sha256(path) == expected_hash, f"hash drift {relative}")


def validate_package_file_types() -> None:
    actual_paths = {str(path.relative_to(PACKAGE)).replace("\\", "/") for path in PACKAGE.rglob("*") if path.is_file()}
    expected_all = EXPECTED_OUTPUTS | {"build_unified_r2_prebind.py", "validate_unified_r2_prebind.py"}
    require(actual_paths == expected_all, f"unexpected/missing/nested package files: {actual_paths ^ expected_all}")
    forbidden = {".fcstd", ".step", ".stp", ".stl", ".glb", ".gltf", ".obj", ".dae", ".urdf", ".inp", ".odb"}
    require(not any(path.suffix.lower() in forbidden for path in PACKAGE.rglob("*") if path.is_file()), "forbidden geometry/solver artifact in prebind package")


def validate_manifest() -> None:
    with (PACKAGE / "UNIFIED_R2_PREBIND_SHA256.csv").open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    source_rows = [row for row in rows if row["class"] == "SOURCE_PIN"]
    package_rows = [row for row in rows if row["class"] == "PACKAGE_SOURCE"]
    output_rows = [row for row in rows if row["class"] == "GENERATED_OUTPUT"]
    require(len(source_rows) == 25, "manifest source row count")
    require(len(package_rows) == 2, "manifest package-source row count")
    require(len(output_rows) == 6, "manifest generated-output row count")
    require({row["path"] for row in source_rows} == set(EXPECTED_SOURCES), "manifest source set drift")
    expected_package_sources = {
        str((PACKAGE / "build_unified_r2_prebind.py").relative_to(ROOT)).replace("\\", "/"),
        str((PACKAGE / "validate_unified_r2_prebind.py").relative_to(ROOT)).replace("\\", "/"),
    }
    require({row["path"] for row in package_rows} == expected_package_sources, "manifest package-source set drift")
    expected_manifest_outputs = {str((PACKAGE / name).relative_to(ROOT)).replace("\\", "/") for name in EXPECTED_OUTPUTS if not name.endswith("SHA256.csv")}
    require({row["path"] for row in output_rows} == expected_manifest_outputs, "manifest output set drift")
    for row in rows:
        path = ROOT / row["path"]
        require(path.is_file(), f"manifest missing file {row['path']}")
        require(path.stat().st_size == int(row["bytes"]), f"manifest byte drift {row['path']}")
        require(sha256(path) == row["sha256"], f"manifest hash drift {row['path']}")


def validate_urdf_ledger(ledger: dict[str, Any]) -> None:
    urdf_path = ROOT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
    independent = independently_parse_urdf(urdf_path)
    parsed = ledger["parsed_robot"]
    for key, value in independent.items():
        if key == "total_declared_link_mass_kg":
            require(abs(parsed[key] - value) < 1e-14, "ledger mass differs from independent parser")
        else:
            require(parsed[key] == value, f"ledger URDF summary drift: {key}")
    require(independent == {
        "robot_name": "arm_b601_v1",
        "link_count": 10,
        "joint_count": 9,
        "root_links": ["base_link"],
        "joint_type_counts": {"fixed": 1, "prismatic": 2, "revolute": 6},
        "links_with_inertial": 10,
        "total_declared_link_mass_kg": independent["total_declared_link_mass_kg"],
        "visual_count": 10,
        "collision_count": 10,
        "mesh_reference_occurrence_count": 20,
        "unique_mesh_reference_count": 10,
        "all_local_mesh_references_exist": True,
    }, "independent B601 topology summary drift")
    require(abs(independent["total_declared_link_mass_kg"] - 4.695555949342986) < 1e-14, "independent B601 mass drift")
    require(ledger["source_artifact"]["project_gen_urdf_source"] is None, "fabricated gen_urdf source")
    require(ledger["unit_contract"]["prismatic_velocity_semantic"] == "m/s", "prismatic velocity SI semantic missing")
    require(ledger["unit_contract"]["revolute_velocity_semantic"] == "rad/s", "revolute velocity SI semantic missing")
    for link in parsed["links"]:
        require(bool(link["frame_role"]), f"missing link role: {link['name']}")
        require(len(link["visual_geometries"]) == 1 and len(link["collision_geometries"]) == 1, f"geometry ledger gap: {link['name']}")
        for geometry in link["visual_geometries"] + link["collision_geometries"]:
            require(geometry["mesh_scale"] == [1.0, 1.0, 1.0], f"unexpected mesh scale: {link['name']}")
            require(geometry["mesh_source_unit_status"] == "HOLD_SOURCE_UNIT_AUDIT", f"mesh unit HOLD lost: {link['name']}")
            require(geometry["exists"] is True, f"mesh missing: {link['name']}")
        require(link["collision_authority"] == "MODEL_GEOMETRY_ONLY__NOT_OPERATIONAL_COLLISION_AUTHORITY", f"collision authority upgraded: {link['name']}")
    annotations = {item["joint_name"]: item for item in ledger["joint_authority_annotations"]}
    require(set(annotations) == {"joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint", "gripper_joint1", "gripper_joint2"}, "joint authority annotation set drift")
    for name in ("gripper_joint1", "gripper_joint2"):
        require(annotations[name]["velocity_literal"] == 15.0, f"gripper velocity literal drift: {name}")
        require(annotations[name]["velocity_si_semantic_unit"] == "m/s", f"gripper velocity unit drift: {name}")
        require(annotations[name]["physical_velocity_authority"] == "HOLD_UNVALIDATED_AUTO_EXPORTED_MODEL_LIMIT", f"gripper physical authority drift: {name}")
    active = ledger["active_gripper_velocity_authority"]
    pack = load_yaml(ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml")
    pointer = load_yaml(ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/01_interface/GRIPPER_ACTIVE_CONSUMPTION_POINTER_V1.yaml")
    gripper_gate = load_json(ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/02_gate/GRIPPER_VELOCITY_UNIT_GATE_V1.json")
    require(active["active_consumption_pointer"]["selected_pack"] == pointer["active_pack"], "active gripper pointer not propagated")
    require(active["active_engineering_pack"]["urdf_velocity_semantic_value_m_s"] == pack["frozen_inputs"]["urdf_velocity_semantic_value_m_s"] == 15.0, "active gripper velocity not propagated")
    require(active["active_engineering_pack"]["urdf_velocity_source_classification"] == "UNVALIDATED_AUTO_EXPORTED_MODEL_LIMIT", "gripper model-limit class lost")
    require(active["active_engineering_pack"]["physical_capability_m_s"] is None and active["active_engineering_pack"]["physical_uncertainty_m_s"] is None, "gripper physical value fabricated")
    require(active["companion_gate"]["verdict"] == gripper_gate["verdict"], "gripper Gate verdict not propagated")
    require(active["companion_gate"]["physical_actuator_speed_authority"] == "HOLD" and active["companion_gate"]["physical_gripper_timing_ready"] is False, "gripper physical HOLD lost")
    required_outputs = ledger["future_generator_contract"]["required_outputs"]
    require("versioned explicit system URDF" in required_outputs, "explicit URDF output missing")
    require(not any("mesh" in item.lower() for item in required_outputs), "gen_urdf incorrectly owns mesh generation")
    require(len(ledger["future_generator_contract"]["mesh_dependencies_from_cad_workflow"]) == 2, "CAD mesh dependency contract missing")
    require(len(ledger["assumption_ledger"]) >= 4, "URDF assumption ledger incomplete")
    require(ledger["authority_flags"] == {
        "new_urdf_generated": False,
        "system_urdf_complete": False,
        "collision_authority": False,
        "production_dynamics_ready": False,
        "sim13_production_binding_authorized": False,
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }, "URDF ledger authority drift")


def validate_configuration_contract(contract: dict[str, Any]) -> None:
    rows = contract["configuration_contract"]
    require(len(rows) == 9, "configuration contract is not 9/9")
    actual = [(row["configuration_id"], row["name"], row["m7_r2_design_model_candidate"]["mass_kg"]) for row in rows]
    require(actual == EXPECTED_CONFIGURATIONS, "configuration identity/mass drift")
    m4 = load_yaml(ROOT / "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml")
    m7 = load_yaml(ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml")
    m4_by_id = {item["configuration_id"]: item for item in m4["configurations"]}
    m7_by_id = {item["configuration_id"]: item for item in m7["configurations"]}
    for row in rows:
        old = m4_by_id[row["configuration_id"]]
        new = m7_by_id[row["configuration_id"]]
        require(row["name"] == old["name"] == new["name"], "configuration name source binding drift")
        require(row["m7_r2_design_model_candidate"] == {
            "mass_kg": new["mass"]["value_kg"],
            "mass_standard_uncertainty_kg": new["mass"]["standard_uncertainty_kg"],
            "center_of_mass_S_m": new["center_of_mass"]["xyz_m"],
            "center_of_mass_standard_uncertainty_m": new["center_of_mass"]["standard_uncertainty_xyz_m"],
            "inertia_about_system_cg_S_kg_m2": new["inertia"]["components_kg_m2"],
            "inertia_standard_uncertainty_components_kg_m2": new["inertia"]["standard_uncertainty_components_kg_m2"],
            "authority": new["mass"]["authority"],
        }, f"full mass/CG/inertia/uncertainty projection drift: {row['configuration_id']}")
        require(row["m4_release_state"] == {
            "mass": old["mass"]["status"],
            "center_of_mass": old["cg"]["status"],
            "inertia": old["inertia"]["status"],
            "bounding_box": old["bbox"]["status"],
            "collision": old["collision"]["status"],
            "overall": old["status"],
        }, f"M4 release-state projection drift: {row['configuration_id']}")
        require(row["m7_r2_design_model_candidate"]["authority"] == "DESIGN_MODEL_R2", "mass authority upgraded")
        require(row["m7_to_m4_binding_field"] == {
            "m4_configuration_library_name": "",
            "status": "HOLD_EMPTY_SOURCE_BINDING_FIELD__IDENTITY_MATCHED_BY_ID_AND_NAME_FOR_PREBIND_ONLY",
        }, "empty M7-to-M4 source binding gap not preserved")
        require(row["binding_state"] == "PREBIND_ONLY__NOT_M4_RELEASED__NOT_SIM13_PRODUCTION_BOUND", "configuration binding overclaim")
        require(row["m4_release_state"]["overall"] == "HOLD_RELEASE_PROPERTIES_INCOMPLETE", "M4 release hold lost")


def validate_upstream_truths(contract: dict[str, Any]) -> None:
    m4 = load_json(ROOT / next(path for path in EXPECTED_SOURCES if path.endswith("MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json")))
    m4_cfg = load_yaml(ROOT / next(path for path in EXPECTED_SOURCES if path.endswith("CONFIGURATION_LIBRARY_V1.yaml")))
    checkpoint = load_json(ROOT / next(path for path in EXPECTED_SOURCES if path.endswith("ROUTE_C_CHECKPOINT_B_GATE_V1.json")))
    registry = load_yaml(ROOT / next(path for path in EXPECTED_SOURCES if path.endswith("ROUTE_C_C2_01_REGISTRY_SKELETON_V1.yaml")))
    odr07 = load_yaml(ROOT / next(path for path in EXPECTED_SOURCES if path.endswith("P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml")))
    odr08 = load_yaml(ROOT / next(path for path in EXPECTED_SOURCES if path.endswith("LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml")))
    sim13 = load_json(ROOT / next(path for path in EXPECTED_SOURCES if path.endswith("SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json")))
    bootstrap = load_json(ROOT / next(path for path in EXPECTED_SOURCES if path.endswith("sim13_bootstrap.json")))
    require(m4["release_tokens"]["digital_prototype"]["issued"] is True, "M4 scoped token lost")
    require(all(item["mass"]["released_value_kg"] is None for item in m4_cfg["configurations"]), "M4 released mass fabricated")
    require(all(item["cg"]["released_xyz_m"] is None for item in m4_cfg["configurations"]), "M4 released CG fabricated")
    require(all(item["inertia"]["released_matrix_kg_m2"] is None for item in m4_cfg["configurations"]), "M4 released inertia fabricated")
    require(checkpoint["checkpoint_outcome"] == "HOLD", "Checkpoint-B no longer HOLD")
    require(checkpoint["admission"]["summary"]["pass"] == 2 and checkpoint["admission"]["summary"]["fail"] == 6, "Checkpoint-B tally drift")
    require(checkpoint["admission"]["ROUTE_C_CAD_AUTHORIZED"] is False, "Route-C CAD authority fabricated")
    require(registry["summary"]["entries_total"] == 13 and registry["summary"]["value_non_null"] == 0 and registry["summary"]["status_HOLD"] == 13, "Route-C registry drift")
    for request in (odr07, odr08):
        require(request["record_type"] == "APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD", "decision request type drift")
        require(request["status"] == "PENDING_OWNER_DECISION", "decision request no longer pending")
        require(request["owner_decision_record"]["selected_option"] is None, "decision selection fabricated")
        require(request["owner_accepted"] is False and request["next_stage_authorized"] is False and request["release_credit"] is False, "decision request fabricated authority")
    require(sim13["verdict"] == "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE", "Sim13 verdict drift")
    require(sim13["baseline_mutation_authorized"] is False and sim13["next_stage_authorized"] is False, "Sim13 authority drift")
    require("MECH_RL_INTERFACE_V1.yaml" in bootstrap["mechanical_interface_path"], "Sim13 is no longer V1-bound")
    require(bootstrap["training_success_claimed"] is False, "Sim13 training claim fabricated")
    current = contract["current_authority_inputs"]
    require(current["odr_gpt_07"] == {
        "status": odr07["status"],
        "selected_option": odr07["owner_decision_record"]["selected_option"],
        "recommended_option": odr07["engineering_recommendation"]["recommended_option"],
    }, "ODR-GPT-07 output projection drift")
    require(current["odr_gpt_08"] == {
        "status": odr08["status"],
        "selected_option": odr08["owner_decision_record"]["selected_option"],
        "recommended_option": odr08["engineering_recommendation"]["recommended_option"],
    }, "ODR-GPT-08 output projection drift")
    require(current["route_c_checkpoint_b"] == {
        "outcome": checkpoint["checkpoint_outcome"],
        "admission_pass": checkpoint["admission"]["summary"]["pass"],
        "admission_total": checkpoint["admission"]["summary"]["conditions_total"],
        "route_c_cad_authorized": checkpoint["admission"]["ROUTE_C_CAD_AUTHORIZED"],
    }, "Route-C checkpoint output projection drift")
    require(current["route_c_registry"] == registry["summary"], "Route-C registry output projection drift")
    require(current["sim13"] == {
        "binding_audit_verdict": sim13["verdict"],
        "baseline_mutation_authorized": sim13["baseline_mutation_authorized"],
        "current_mechanical_interface_path": bootstrap["mechanical_interface_path"],
        "training_success_claimed": bootstrap["training_success_claimed"],
    }, "Sim13 output projection drift")


def validate_contract_source_pins(contract: dict[str, Any]) -> None:
    rows = contract["source_pins"]
    require(len(rows) == 25, "contract source-pin count drift")
    by_path = {row["path"]: row for row in rows}
    require(set(by_path) == set(EXPECTED_SOURCES), "contract source-pin path set drift")
    for path, (expected_bytes, expected_hash) in EXPECTED_SOURCES.items():
        row = by_path[path]
        require(row["bytes"] == expected_bytes and row["sha256"] == expected_hash, f"contract source pin drift: {path}")
        require(row["verified"] is True, f"contract source not verified: {path}")


def validate_contract_shape(contract: dict[str, Any]) -> None:
    require(set(contract) == EXPECTED_CONTRACT_TOP_LEVEL_KEYS, f"contract top-level key drift: {set(contract) ^ EXPECTED_CONTRACT_TOP_LEVEL_KEYS}")
    require(contract["schema"] == "UNIFIED_R2_DIGITAL_PROTOTYPE_REBASE_CONTRACT_V1", "contract schema drift")
    require(contract["generated_date_local"] == "2026-08-24", "contract generation date drift")
    require(contract["status"] == "PREBIND_DOCUMENT_SET_COMPLETE__ENGINEERING_SPECIFICATION_INCOMPLETE__EXECUTION_HOLD", "contract status drift")
    require(contract["artifact_class"] == "DOCUMENTATION_ONLY__NOT_CAD_NOT_URDF_NOT_RELEASE", "contract artifact class drift")
    require(bool(contract["purpose"]), "contract purpose missing")
    require(contract["predecessor_state"]["m4_must_not_be_rebuilt"] is True, "M4 no-rebuild rule lost")
    require(contract["future_baseline"]["baseline_id"] == "DESIGN_FREEZE_ASSEMBLY_R2_V1", "future baseline identity drift")
    require(contract["frame_contract"]["forbidden_alias"] == "M_DYNAMICS != B601_ARM_BASE_PHYSICAL", "forbidden frame alias lost")
    require(contract["future_output_contract"]["neutral_cad"] == "DESIGN_FREEZE_ASSEMBLY_R2_V1.step", "STEP-first neutral artifact drift")
    require(set(contract["validation_contract"]) == {"geometry", "interfaces", "motion_and_collision", "mass_properties", "visual_review", "consumer"}, "validation-contract section drift")
    require(len(contract["component_rebase_matrix"]) == 8, "component rebase matrix row count drift")
    require(len(contract["entry_sequence"]) == 9, "entry sequence row count drift")


def validate_bus_solar_gripper_contract(contract: dict[str, Any]) -> None:
    product = load_yaml(ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/PRODUCT_STRUCTURE_V1.yaml")
    frame_tree = load_yaml(ROOT / "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml")
    solar = load_json(ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V2.json")
    gripper_pack = load_yaml(ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml")
    gripper_gate = load_json(ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/02_gate/GRIPPER_VELOCITY_UNIT_GATE_V1.json")
    bus_source = next(item for item in product["product_tree"] if item["id"] == "BUS_PRIMARY_STRUCTURE")
    bus = contract["bus_12u_geometry_authority"]
    require(bus["status"] == "HOLD_12U_PHYSICAL_STRUCTURE_AUTHORITY_AND_LENGTH_RECONCILIATION", "12U physical-structure HOLD missing")
    require(bus["current_geometry_class"] == "DISPLAY_AND_ENVELOPE_PROXY_ONLY", "12U proxy upgraded")
    require(bus["source_solids"] == bus_source["solids"] == 6, "12U proxy solid count drift")
    require(bus["composition_note"] == bus_source["composition_note"], "12U composition note not source-bound")
    require(bus["holds"] == bus_source["holds"] and bus["model_to_model_delta"] == bus_source["model_to_model_delta"], "12U holds/delta not source-bound")
    component_rows = {row["component"]: row for row in contract["component_rebase_matrix"]}
    require("ENVELOPE_PROXY_ONLY__NOT_PHYSICAL_STRUCTURE_AUTHORITY" in component_rows["12U bus"]["inherit"], "12U component matrix overclaims physical geometry")

    reconciliation = contract["solar_r2_root_frame_reconciliation"]
    legacy_left = frame_tree["frames"]["F_L"]["origin_S_mm"]
    legacy_right = frame_tree["frames"]["F_R"]["origin_S_mm"]
    hinge = solar["parameters"]["root_hinge_line"]
    require(reconciliation["status"] == "HOLD_PANEL_ROOT_TO_HINGE_AXIS_REGISTRATION_NOT_ESTABLISHED", "Solar R2 frame HOLD missing")
    require(reconciliation["legacy_r1_frames"]["F_L_origin_S_mm"] == legacy_left == [-56.75, 113.15, 0.0], "legacy F_L not source-bound")
    require(reconciliation["legacy_r1_frames"]["F_R_origin_S_mm"] == legacy_right == [-56.75, -113.15, 0.0], "legacy F_R not source-bound")
    require(reconciliation["solar_r2_candidate_hinge_line"]["left_origin_partial_S_mm"] == [None, hinge["y_abs_mm"], hinge["z_mm"]], "Solar R2 left hinge line drift")
    require(reconciliation["solar_r2_candidate_hinge_line"]["right_origin_partial_S_mm"] == [None, -hinge["y_abs_mm"], hinge["z_mm"]], "Solar R2 right hinge line drift")
    require(reconciliation["solar_r2_candidate_hinge_line"]["axis"] == "X_S", "Solar R2 hinge axis drift")
    require(legacy_left[2] != hinge["z_mm"] and abs(legacy_left[2] - hinge["z_mm"]) > 100.0, "legacy/R2 frame difference was erased")
    require("legacy R1 F_L/F_R transforms excluded" in component_rows["solar arrays"]["inherit"], "Solar R2 component matrix permits legacy frame inheritance")

    gripper = contract["current_authority_inputs"]["gripper_velocity"]
    require(gripper == {
        "urdf_velocity_semantic_value_m_s": gripper_pack["frozen_inputs"]["urdf_velocity_semantic_value_m_s"],
        "urdf_velocity_source_classification": gripper_pack["frozen_inputs"]["urdf_velocity_source_classification"],
        "physical_capability_m_s": gripper_pack["frozen_inputs"]["urdf_velocity_physical_capability_m_s"],
        "physical_uncertainty_m_s": gripper_pack["frozen_inputs"]["urdf_velocity_physical_uncertainty_m_s"],
        "gate_verdict": gripper_gate["verdict"],
        "physical_actuator_speed_authority": gripper_gate["physical_actuator_speed_authority"],
        "physical_gripper_timing_ready": gripper_gate["physical_gripper_timing_ready"],
    }, "gripper velocity authority not source-bound")
    require(gripper["physical_capability_m_s"] is None and gripper["physical_uncertainty_m_s"] is None, "gripper physical velocity fabricated")
    require("never consume the 15 m/s model literal" in component_rows["gripper"]["future_action"], "gripper timing prohibition missing")


def validate_authorization_state_machine(contract: dict[str, Any]) -> None:
    machine = contract["authorization_state_machine"]
    expected_keys = {
        "cad_urdf_execution_prerequisites": {
            "unified_r2_rebase_execution_authorization_recorded",
            "bus_physical_authority_resolved",
            "solar_r2_root_frames_frozen",
            "route_c_registry_13_of_13",
            "checkpoint_b_8_of_8",
            "separate_route_c_cad_authority",
            "memory_admitted_for_this_execution",
        },
        "parallel_full_flex_decision_prerequisites": {"odr_gpt_07_selected", "odr_gpt_08_selected"},
        "downstream_release_joins_after_geometry": {
            "unified_r2_geometry_and_sweeps_pass",
            "full_flex_gate_pass",
            "mission_harness_coverage_pass",
            "gripper_physical_actuator_gate_pass",
            "nine_configuration_properties_released",
            "versioned_sim13_rebind_gate_pass",
            "mechanical_to_embodied_handoff_pass",
        },
    }
    require(set(machine) == set(expected_keys), "authorization stage set drift")
    for stage_name, keys in expected_keys.items():
        stage = machine[stage_name]
        require(set(stage["current_inputs"]) == keys, f"authorization input set drift: {stage_name}")
        require(all(value is False for value in stage["current_inputs"].values()), f"current authority fabricated: {stage_name}")
        require(stage["rule"] == "ALL_REQUIRED_EXACT_TRUE", f"authorization rule drift: {stage_name}")
        result_key = "released" if stage_name == "downstream_release_joins_after_geometry" else "authorized"
        independently_evaluated = evaluate_all_required_exact_true(stage["current_inputs"])
        require(stage[result_key] is independently_evaluated, f"builder/validator stage result mismatch: {stage_name}")
        require(independently_evaluated is False, f"stage evaluator unexpectedly true: {stage_name}")
    sequence = contract["entry_sequence"]
    route_index = next(i for i, text in enumerate(sequence) if "Route-C P01-P13" in text)
    geometry_index = next(i for i, text in enumerate(sequence) if "Execute one versioned Unified R2" in text)
    mission_index = next(i for i, text in enumerate(sequence) if "rated-envelope mission coverage" in text)
    sim13_index = next(i for i, text in enumerate(sequence) if "update Sim13 loader" in text)
    require(route_index < geometry_index < mission_index < sim13_index, "CAD→sweep/mission→Sim13 ordering cycle detected")


def validate_gate_and_readiness(gate: dict[str, Any], readiness: dict[str, Any], contract: dict[str, Any]) -> None:
    expected_verdict = "HOLD_PREBIND_DOCUMENT_SET_COMPLETE__ENGINEERING_SPECIFICATION_INCOMPLETE__GEOMETRY_BLOCKED_BY_REBASE_AUTHORITY_BUS_SOLAR_ROUTE_C_AND_MEMORY__RELEASE_BLOCKED_BY_FULL_FLEX_HARNESS_GRIPPER_AND_RUNTIME_JOINS"
    require(gate["technical_verdict"] == expected_verdict, "gate verdict drift")
    require(gate["outcome"] == "HOLD", "gate outcome drift")
    require(gate["document_set_complete"] is True, "document-set completeness lost")
    require(gate["engineering_specification_complete"] is False and gate["specification_complete"] is False, "engineering specification overclaim")
    require(readiness["summary"] == {"criteria_total": 20, "pass": 5, "hold": 15}, "readiness tally drift")
    require(gate["readiness_summary"] == readiness["summary"], "Gate/readiness summary split")
    criteria = readiness["criteria"]
    require(len(criteria) == 20, "readiness criterion list length drift")
    require(len({item["id"] for item in criteria}) == len(criteria), "duplicate readiness criterion id")
    for item in criteria:
        require(type(item["pass"]) is bool, f"criterion pass is not strict boolean: {item['id']}")
        require(item["state"] == ("PASS" if item["pass"] else "HOLD"), f"criterion state/pass split: {item['id']}")
        require(isinstance(item["name"], str) and bool(item["name"].strip()), f"criterion name missing: {item['id']}")
        require(isinstance(item["evidence"], str) and bool(item["evidence"].strip()), f"criterion evidence missing: {item['id']}")
    states = {item["id"]: item["pass"] for item in criteria}
    require(states == {f"PRB-{number:02d}": number <= 5 for number in range(1, 21)}, "readiness state vector drift")
    assert_false_authority_map(gate["authority_flags"])
    assert_false_authority_map(readiness["authority_flags"])
    assert_false_authority_map(contract["authority_flags"])
    for key in ("owner_accepted", "next_stage_authorized", "release_credit", "terminal_release_candidate_generated"):
        require(gate[key] is False, f"top-level gate authority drift: {key}")
    execution = gate["execution_receipt"]
    for key in ("cad_files_generated", "mesh_files_generated", "urdf_files_generated", "fea_runs", "simulation_runs"):
        require(type(execution[key]) is int and execution[key] == 0, f"nonzero/noninteger execution count: {key}")
    require(execution["documentation_files_generated"] == 7, "documentation output count drift")
    require(execution["snapshot_review_performed"] is False, "snapshot review fabricated")
    require(execution["memory_gate_passed"] is False and execution["owner_override_used"] is False, "memory authority fabricated")
    memory = contract["execution_record"]["prebuild_memory_observation"]
    require(type(memory["available_physical_gib"]) in (int, float) and math.isfinite(memory["available_physical_gib"]) and memory["available_physical_gib"] >= 0.0, "memory sample is non-finite or negative")
    require(type(memory["threshold_gib"]) in (int, float) and math.isfinite(memory["threshold_gib"]) and memory["threshold_gib"] > 0.0, "memory threshold is invalid")
    require(memory["available_physical_gib"] < memory["threshold_gib"] and memory["memory_gate_passed"] is False, "memory gate semantics drift")
    require(memory["observation_time_local"] is None and memory["classification"] == "NONAUTHORITATIVE_ROUNDED_READ_ONLY_SAMPLE__NOT_EXECUTION_ADMISSION", "memory sample overclaimed authority")
    require(contract["execution_record"]["historical_m4_owner_override_inherited"] is False, "historical override silently inherited")


def expect_rejection(operation: Callable[[], None], name: str) -> None:
    caught = False
    try:
        operation()
    except (AssertionError, KeyError, TypeError):
        caught = True
    require(caught, f"negative control was not rejected: {name}")


def validate_negative_controls(
    ledger: dict[str, Any], contract: dict[str, Any], readiness: dict[str, Any], gate: dict[str, Any]
) -> None:
    for stage_name, stage in contract["authorization_state_machine"].items():
        all_true = {key: True for key in stage["current_inputs"]}
        require(evaluate_all_required_exact_true(all_true) is True, f"positive control failed: {stage_name}")
        for missing_key in all_true:
            mutated = copy.deepcopy(all_true)
            mutated[missing_key] = False
            require(evaluate_all_required_exact_true(mutated) is False, f"all-true-minus-one bypass: {stage_name}/{missing_key}")
        string_false = copy.deepcopy(all_true)
        string_false[next(iter(string_false))] = "false"
        require(evaluate_all_required_exact_true(string_false) is False, f"truthy-string bypass: {stage_name}")

    for key in FALSE_AUTHORITY_FLAGS:
        mutated = copy.deepcopy(gate)
        mutated["authority_flags"][key] = True
        expect_rejection(lambda mutated=mutated: validate_gate_and_readiness(mutated, readiness, contract), f"authority flag {key}")
    for key in ("owner_accepted", "next_stage_authorized", "release_credit", "terminal_release_candidate_generated"):
        mutated = copy.deepcopy(gate)
        mutated[key] = True
        expect_rejection(lambda mutated=mutated: validate_gate_and_readiness(mutated, readiness, contract), f"top-level {key}")
    for key in ("cad_files_generated", "mesh_files_generated", "urdf_files_generated", "fea_runs", "simulation_runs"):
        mutated = copy.deepcopy(gate)
        mutated["execution_receipt"][key] = 1
        expect_rejection(lambda mutated=mutated: validate_gate_and_readiness(mutated, readiness, contract), f"execution count {key}")
    mutated = copy.deepcopy(gate)
    mutated["engineering_specification_complete"] = True
    expect_rejection(lambda: validate_gate_and_readiness(mutated, readiness, contract), "engineering specification overclaim")

    mutated = copy.deepcopy(gate)
    mutated["readiness_summary"] = {"criteria_total": 20, "pass": 20, "hold": 0}
    expect_rejection(lambda: validate_gate_and_readiness(mutated, readiness, contract), "Gate/readiness summary split")
    mutated_readiness = copy.deepcopy(readiness)
    mutated_readiness["criteria"][5]["state"] = "PASS"
    expect_rejection(lambda: validate_gate_and_readiness(gate, mutated_readiness, contract), "criterion state/pass split")
    mutated_readiness = copy.deepcopy(readiness)
    mutated_readiness["criteria"][6]["id"] = mutated_readiness["criteria"][5]["id"]
    expect_rejection(lambda: validate_gate_and_readiness(gate, mutated_readiness, contract), "duplicate criterion id")
    mutated_readiness = copy.deepcopy(readiness)
    mutated_readiness["criteria"][5]["evidence"] = ""
    expect_rejection(lambda: validate_gate_and_readiness(gate, mutated_readiness, contract), "empty criterion evidence")

    for missing_key in EXPECTED_CONTRACT_TOP_LEVEL_KEYS:
        mutated_contract = copy.deepcopy(contract)
        del mutated_contract[missing_key]
        expect_rejection(lambda mutated_contract=mutated_contract: validate_contract_shape(mutated_contract), f"missing contract block {missing_key}")
    mutated_contract = copy.deepcopy(contract)
    mutated_contract["authorization_state_machine"]["cad_urdf_execution_prerequisites"]["authorized"] = True
    expect_rejection(lambda: validate_authorization_state_machine(mutated_contract), "builder stage result forced true")
    mutated_contract = copy.deepcopy(contract)
    mutated_contract["execution_record"]["prebuild_memory_observation"]["available_physical_gib"] = -1.0
    expect_rejection(lambda: validate_gate_and_readiness(gate, readiness, mutated_contract), "negative memory sample")
    mutated_contract = copy.deepcopy(contract)
    mutated_contract["configuration_contract"][0]["m7_r2_design_model_candidate"]["center_of_mass_S_m"][0] += 0.001
    expect_rejection(lambda: validate_configuration_contract(mutated_contract), "configuration CG mutation")
    mutated_contract = copy.deepcopy(contract)
    mutated_contract["solar_r2_root_frame_reconciliation"]["solar_r2_candidate_hinge_line"]["left_origin_partial_S_mm"] = [None, 113.15, 0.0]
    expect_rejection(lambda: validate_bus_solar_gripper_contract(mutated_contract), "Solar R2 frame replaced by legacy R1")
    mutated_ledger = copy.deepcopy(ledger)
    mutated_ledger["active_gripper_velocity_authority"]["active_engineering_pack"]["physical_capability_m_s"] = 15.0
    expect_rejection(lambda: validate_urdf_ledger(mutated_ledger), "gripper model literal promoted to physical speed")


def main() -> None:
    ledger = load_yaml(PACKAGE / "UNIFIED_R2_URDF_DESIGN_LEDGER_V1.yaml")
    contract = load_yaml(PACKAGE / "UNIFIED_R2_DIGITAL_PROTOTYPE_REBASE_CONTRACT_V1.yaml")
    readiness = load_json(PACKAGE / "UNIFIED_R2_PREBIND_READINESS_V1.json")
    gate = load_json(PACKAGE / "UNIFIED_R2_PREBIND_GATE_V1.json")

    check("PRV-01", "all 25 upstream files retain exact bytes and SHA-256", validate_sources)
    check("PRV-02", "package contains only the exact documentation/source set and no CAD/URDF/solver artifact", validate_package_file_types)
    check("PRV-03", "manifest independently matches all source and generated files", validate_manifest)
    check("PRV-04", "B601 URDF ledger matches an independent XML parse", lambda: validate_urdf_ledger(ledger))
    check("PRV-05", "C01-C09 mass, CG, inertia, uncertainty, identity and nonbinding status are source-exact", lambda: validate_configuration_contract(contract))
    check("PRV-06", "M4, Route-C, ODR and Sim13 upstream truths are preserved", lambda: validate_upstream_truths(contract))
    check("PRV-07", "contract contains the exact 25-file source-to-output pin set", lambda: validate_contract_source_pins(contract))
    check("PRV-08", "12U proxy, Solar R2 root-frame and gripper velocity HOLDs are source-bound", lambda: validate_bus_solar_gripper_contract(contract))
    check("PRV-09", "CAD admission, parallel Full-Flex decisions and downstream release joins are acyclic and fail closed", lambda: validate_authorization_state_machine(contract))
    check("PRV-10", "readiness and Gate retain all fail-closed authority and zero-execution fields", lambda: validate_gate_and_readiness(gate, readiness, contract))
    check("PRV-11", "all-true-minus-one, truthy-string, deletion and field-mutation controls are rejected", lambda: validate_negative_controls(ledger, contract, readiness, gate))
    check("PRV-12", "CAD brief explicitly prohibits current geometry execution", lambda: require("HOLD_PREBIND_DOCUMENT_SET_COMPLETE__ENGINEERING_SPECIFICATION_INCOMPLETE__NO_GEOMETRY_EXECUTION_AUTHORITY" in (PACKAGE / "UNIFIED_R2_CAD_BRIEF_V1.md").read_text(encoding="utf-8"), "CAD brief execution guard missing"))
    check("PRV-13", "receipt explicitly records zero CAD, URDF, FEA and simulation outputs", lambda: require("本轮未生成：FCStd、STEP、STL、GLB、URDF/Xacro、FEA、仿真或训练结果" in (PACKAGE / "UNIFIED_R2_PREBIND_RECEIPT_V1.md").read_text(encoding="utf-8"), "receipt zero-execution statement missing"))
    check("PRV-14", "contract schema, exact top-level blocks and STEP-first baseline contract are complete", lambda: validate_contract_shape(contract))

    failed = [item for item in checks if not item["pass"]]
    report = {
        "validator": "validate_unified_r2_prebind.py",
        "checks_passed": len(checks) - len(failed),
        "checks_total": len(checks),
        "checks_failed": len(failed),
        "status": "PASS_PREBIND_DOCUMENT_SET_FAIL_CLOSED__ENGINEERING_SPECIFICATION_REMAINS_HOLD" if not failed else "FAIL_PREBIND_PACKAGE",
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
