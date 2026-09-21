#!/usr/bin/env python3
"""Build the documentation-only Unified R2 digital-prototype prebind package.

This builder intentionally creates no CAD, mesh, URDF, FEA, simulation, or
consumer-binding artifact.  It converts already frozen evidence into a
fail-closed, hash-bound reissue contract for the future Unified R2 baseline.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import yaml


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
GENERATED_DATE_LOCAL = "2026-08-24"
MEMORY_THRESHOLD_GIB = 6.0
PREBUILD_AVAILABLE_PHYSICAL_GIB = 1.798


SOURCE_PINS = [
    {
        "id": "M4_RELEASE_GATE",
        "path": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json",
        "bytes": 5440,
        "sha256": "0C0994E3E59EDBB5FD43B1D75FC048C8414A735D28CA4FC36E8FC23E03692577",
        "role": "scoped M4 digital-prototype release and mandatory holds",
    },
    {
        "id": "M4_CONFIGURATION_LIBRARY",
        "path": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
        "bytes": 26528,
        "sha256": "DCE40C1DB8A318A077F0DD92A47F236BE55EAF2FD32B4E514D2BB67C9B19B4A2",
        "role": "nine-configuration identity and unreleased-property contract",
    },
    {
        "id": "M4_FRAME_TREE",
        "path": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml",
        "bytes": 6236,
        "sha256": "67293323A45237FB9B415871A4160732EFB156DE74776C9E11ABA9C4202134CA",
        "role": "canonical frame semantics and null-transform policy",
    },
    {
        "id": "M7_RELEASE_GATE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/12_release/MECHANICAL_ENGINEERING_RELEASE_GATE_V1.json",
        "bytes": 48538,
        "sha256": "2D9C8580701BD087A2DB52F57AE9ED23A919DEBC7476727467214411F952859E",
        "role": "current mechanical release authority ceiling",
    },
    {
        "id": "M7_R1_ASSEMBLY_REPORT",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json",
        "bytes": 29415,
        "sha256": "105BCB020FAF9F535C3A18F9A37831679F89070A8CA69C5960F959A686F332C1",
        "role": "current valid R1 unified assembly build evidence",
    },
    {
        "id": "M7_PRODUCT_STRUCTURE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/PRODUCT_STRUCTURE_V1.yaml",
        "bytes": 48807,
        "sha256": "0F9897EF4E41666DDB29CB0FC621DD737FDD8CCDE3F5527030E53A9D1604681A",
        "role": "product-tree geometry classes, including 12U envelope-proxy limitations",
    },
    {
        "id": "M7_R1_ASSEMBLY_FCSTD",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.FCStd",
        "bytes": 579603,
        "sha256": "013DA84FE9A5C388252DB18516628411C484BB818959FA1A5CF8D950485636E7",
        "role": "current R1 native assembly predecessor; read-only",
    },
    {
        "id": "M7_R1_ASSEMBLY_STEP",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.step",
        "bytes": 1373004,
        "sha256": "8C85585E9C051AEBB849E48F56354B48BF4204F61103B550BD92FC77BA99EA9E",
        "role": "current R1 neutral assembly predecessor; read-only",
    },
    {
        "id": "SOLAR_R2_REPORT",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V2.json",
        "bytes": 16118,
        "sha256": "4286EA2BBD84FB8EC33DDADE329534DA29194650AD22429245ECF8757B9AED1C",
        "role": "separate Solar R2 engineering-candidate evidence",
    },
    {
        "id": "SOLAR_R2_FCSTD",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd",
        "bytes": 23733,
        "sha256": "9D4D249A5D4EED7BDD8F3C08EC96737884A19523782112B1E72AD9EA0A1B65AB",
        "role": "Solar R2 native candidate; separate and read-only",
    },
    {
        "id": "SOLAR_R2_STEP",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step",
        "bytes": 131834,
        "sha256": "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795",
        "role": "Solar R2 neutral candidate; separate and read-only",
    },
    {
        "id": "M7_R2_MASS_LEDGER",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml",
        "bytes": 223714,
        "sha256": "3FD2557318E98748A37927977FA2925C18803668FE16391D824C184F646486BB",
        "role": "nine-configuration R2 design-model mass properties with uncertainty",
    },
    {
        "id": "M7_CAD_URDF_REGISTRATION_RECEIPT",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp11_cad_urdf_registration/receipt.json",
        "bytes": 23885,
        "sha256": "83E36583E370BD3A6563330C9B34E0CDB0400DC6952BFC91D9DA5C77536BCB9B",
        "role": "existing CAD/URDF registration audit",
    },
    {
        "id": "B601_ACCEPTED_URDF",
        "path": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "bytes": 11321,
        "sha256": "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
        "role": "accepted imported B601 kinematic and inertial artifact",
    },
    {
        "id": "GRIPPER_ACTIVE_ENGINEERING_PACK",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml",
        "bytes": 13398,
        "sha256": "C31938668746C6B5D3C8C6879D8F2B14BDF8FE78000274ADD8411E7FBB58CEF6",
        "role": "active gripper geometry and velocity-unit interpretation pack",
    },
    {
        "id": "GRIPPER_ACTIVE_CONSUMPTION_POINTER",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/01_interface/GRIPPER_ACTIVE_CONSUMPTION_POINTER_V1.yaml",
        "bytes": 1010,
        "sha256": "B0DDADE5F5CCD6F6CFF2A9B0E7EA23908CE7558EBA002BE26A193D4DEC38A7D8",
        "role": "active-versus-historical gripper consumption selector",
    },
    {
        "id": "GRIPPER_VELOCITY_UNIT_GATE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/02_gate/GRIPPER_VELOCITY_UNIT_GATE_V1.json",
        "bytes": 2692,
        "sha256": "A93B08B56CB46623A0E8B96234B7FA48C1C59492F950A543BB164AD4CF4A0E7B",
        "role": "URDF velocity semantics and physical actuator/timing HOLD",
    },
    {
        "id": "ROUTE_C_CHECKPOINT_B",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/checkpoint_b/ROUTE_C_CHECKPOINT_B_GATE_V1.json",
        "bytes": 14887,
        "sha256": "C9E7526D790E1FB7F5522A113EDF41F5913207C15A68E12468FD9EBA157349D1",
        "role": "Route-C admission and CAD prohibition",
    },
    {
        "id": "ROUTE_C_PHYSICAL_REGISTRY",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_C2_01_REGISTRY_SKELETON_V1.yaml",
        "bytes": 19773,
        "sha256": "6264A0A45F6A497787F3D96205CEF7799A19A225CD23CEA66D5AD31E335A3E8E",
        "role": "P01-P13 physical-input registry",
    },
    {
        "id": "TERMINAL_DECISION_GATE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack/TERMINAL_DECISION_PACK_GATE_V1.json",
        "bytes": 25452,
        "sha256": "0C9DC0353630A402745B3CE5235DC75A2FC51A65B189E2580A7FA5484A5F3325",
        "role": "current terminal decision and execution authority",
    },
    {
        "id": "ODR_GPT_07_REQUEST",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack/P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml",
        "bytes": 23043,
        "sha256": "679DC5D2BA2B814F584379C28E47A9F487D03277F0F1EAA45DFB85D150367D25",
        "role": "pending ODR-GPT-07 approval request",
    },
    {
        "id": "ODR_GPT_08_REQUEST",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack/LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml",
        "bytes": 46441,
        "sha256": "5ED037AE057F7119678DECF890C9C0E64740C1443E5E9B9682FC09B8610046F6",
        "role": "pending ODR-GPT-08 approval request",
    },
    {
        "id": "SIM13_BINDING_AUDIT",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/09_downstream_rebind/SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json",
        "bytes": 6345,
        "sha256": "7FD3C63AF46BE4BA3055CCF87EFD1A71C13517EC872B1F3EDC52304B070D9153",
        "role": "current Sim13 mechanical-binding invalidation",
    },
    {
        "id": "SIM13_BOOTSTRAP_CONFIG",
        "path": "30_simulation/sim_13_physics_gated_embodied_grasping/config/sim13_bootstrap.json",
        "bytes": 647,
        "sha256": "4624C5BA2A016A002531FCF6FB6EFD661AA488D6C9420197789263D4B0E42B8D",
        "role": "current V1 bootstrap binding",
    },
    {
        "id": "SIM13_MECHANICAL_LOADER",
        "path": "30_simulation/sim_13_physics_gated_embodied_grasping/src/mechanical_asset_loader.py",
        "bytes": 23753,
        "sha256": "C0797E5786888E357784369F6601B380C4E94FAE76B3FBFCF4C46717A833E851",
        "role": "current mechanical consumer loader",
    },
]


OUTPUT_NAMES = [
    "UNIFIED_R2_CAD_BRIEF_V1.md",
    "UNIFIED_R2_URDF_DESIGN_LEDGER_V1.yaml",
    "UNIFIED_R2_DIGITAL_PROTOTYPE_REBASE_CONTRACT_V1.yaml",
    "UNIFIED_R2_PREBIND_READINESS_V1.json",
    "UNIFIED_R2_PREBIND_GATE_V1.json",
    "UNIFIED_R2_PREBIND_RECEIPT_V1.md",
    "UNIFIED_R2_PREBIND_SHA256.csv",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def all_required_exact_true(inputs: dict[str, Any]) -> bool:
    return bool(inputs) and all(value is True for value in inputs.values())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(relative_path: str) -> dict[str, Any]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def read_yaml(relative_path: str) -> dict[str, Any]:
    return yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))


def write_json(name: str, payload: Any) -> None:
    (PACKAGE / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_yaml(name: str, payload: Any) -> None:
    (PACKAGE / name).write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def write_text(name: str, text: str) -> None:
    (PACKAGE / name).write_text(text.rstrip() + "\n", encoding="utf-8")


def verify_source_pins() -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for pin in SOURCE_PINS:
        path = ROOT / pin["path"]
        require(path.is_file(), f"missing source: {pin['path']}")
        require(path.stat().st_size == pin["bytes"], f"byte count drift: {pin['path']}")
        actual_hash = sha256(path)
        require(actual_hash == pin["sha256"], f"SHA-256 drift: {pin['path']}")
        verified.append({**pin, "verified": True})
    return verified


def parse_vector(element: ET.Element | None, attribute: str, default: str) -> list[float]:
    raw = default if element is None else element.get(attribute, default)
    return [float(value) for value in raw.split()]


def parse_urdf(relative_path: str) -> dict[str, Any]:
    urdf_path = ROOT / relative_path
    robot = ET.parse(urdf_path).getroot()
    links: list[dict[str, Any]] = []
    mesh_occurrences: list[dict[str, Any]] = []

    for link in robot.findall("link"):
        inertial = link.find("inertial")
        mass_element = None if inertial is None else inertial.find("mass")
        inertia_element = None if inertial is None else inertial.find("inertia")
        inertial_origin = None if inertial is None else inertial.find("origin")
        geometry_by_use: dict[str, list[dict[str, Any]]] = {"visual": [], "collision": []}
        for use in ("visual", "collision"):
            for instance in link.findall(use):
                origin = instance.find("origin")
                mesh = instance.find("geometry/mesh")
                require(mesh is not None, f"non-mesh {use} geometry is outside this accepted-URDF parser")
                filename = mesh.get("filename")
                scale = parse_vector(mesh, "scale", "1 1 1")
                resolved = urdf_path.parent / str(filename)
                geometry_record = {
                    "origin_xyz_m": parse_vector(origin, "xyz", "0 0 0"),
                    "origin_rpy_rad": parse_vector(origin, "rpy", "0 0 0"),
                    "geometry_type": "mesh",
                    "mesh_reference": filename,
                    "mesh_scale": scale,
                    "mesh_source_unit_status": "HOLD_SOURCE_UNIT_AUDIT",
                    "resolved_relative_to_urdf": str(resolved.relative_to(ROOT)).replace("\\", "/"),
                    "exists": resolved.is_file(),
                }
                geometry_by_use[use].append(geometry_record)
                mesh_occurrences.append({"link": link.get("name"), "use": use, **geometry_record})
        visual_meshes = [item["mesh_reference"] for item in geometry_by_use["visual"]]
        collision_meshes = [item["mesh_reference"] for item in geometry_by_use["collision"]]
        link_name = str(link.get("name"))
        if link_name == "base_link":
            role = "B601 arm mounting/root link frame"
        elif link_name.startswith("link"):
            role = "B601 articulated arm link frame"
        elif link_name == "gripper_link":
            role = "gripper palm link frame"
        else:
            role = "gripper finger link frame"
        links.append(
            {
                "name": link_name,
                "frame_role": role,
                "mass_kg": None if mass_element is None else float(mass_element.get("value", "nan")),
                "inertial_origin_xyz_m": parse_vector(inertial_origin, "xyz", "0 0 0"),
                "inertial_origin_rpy_rad": parse_vector(inertial_origin, "rpy", "0 0 0"),
                "inertia_about_declared_inertial_origin_kg_m2": None
                if inertia_element is None
                else {key: float(inertia_element.get(key, "nan")) for key in ("ixx", "iyy", "izz", "ixy", "ixz", "iyz")},
                "visual_count": len(link.findall("visual")),
                "collision_count": len(link.findall("collision")),
                "visual_mesh_references": visual_meshes,
                "collision_mesh_references": collision_meshes,
                "visual_geometries": geometry_by_use["visual"],
                "collision_geometries": geometry_by_use["collision"],
                "inertial_source_class": "ACCEPTED_IMPORTED_HYBRID_URDF__MEDIUM_CONFIDENCE__NOT_AS_BUILT",
                "collision_authority": "MODEL_GEOMETRY_ONLY__NOT_OPERATIONAL_COLLISION_AUTHORITY",
                "assumptions": [
                    "mesh scale defaults to [1,1,1] where the source omits scale",
                    "mesh source units remain an explicit audit HOLD",
                    "declared inertial values are preserved without upgrading them to measured/as-built authority",
                ],
            }
        )

    joints: list[dict[str, Any]] = []
    for joint in robot.findall("joint"):
        origin = joint.find("origin")
        axis = joint.find("axis")
        limit = joint.find("limit")
        joints.append(
            {
                "name": joint.get("name"),
                "type": joint.get("type"),
                "parent": joint.find("parent").get("link"),
                "child": joint.find("child").get("link"),
                "origin_xyz_m": parse_vector(origin, "xyz", "0 0 0"),
                "origin_rpy_rad": parse_vector(origin, "rpy", "0 0 0"),
                "axis_xyz": parse_vector(axis, "xyz", "0 0 0"),
                "positive_motion_physical_description": None,
                "positive_motion_semantics_status": "HOLD_NOT_EXPLICIT_IN_ACCEPTED_URDF",
                "limit": None
                if limit is None
                else {
                    key: (None if limit.get(key) is None else float(limit.get(key)))
                    for key in ("lower", "upper", "effort", "velocity")
                },
            }
        )

    link_names = {item["name"] for item in links}
    child_names = {item["child"] for item in joints}
    masses = [item["mass_kg"] for item in links if item["mass_kg"] is not None]
    return {
        "robot_name": robot.get("name"),
        "link_count": len(links),
        "joint_count": len(joints),
        "root_links": sorted(link_names - child_names),
        "joint_type_counts": dict(sorted(Counter(item["type"] for item in joints).items())),
        "links_with_inertial": len(masses),
        "total_declared_link_mass_kg": sum(masses),
        "visual_count": sum(item["visual_count"] for item in links),
        "collision_count": sum(item["collision_count"] for item in links),
        "mesh_reference_occurrence_count": len(mesh_occurrences),
        "unique_mesh_reference_count": len({item["mesh_reference"] for item in mesh_occurrences}),
        "all_local_mesh_references_exist": all(item["exists"] for item in mesh_occurrences),
        "links": links,
        "joints": joints,
        "mesh_occurrences": mesh_occurrences,
    }


def make_configuration_contract(m4: dict[str, Any], m7: dict[str, Any]) -> list[dict[str, Any]]:
    m4_by_id = {item["configuration_id"]: item for item in m4["configurations"]}
    m7_by_id = {item["configuration_id"]: item for item in m7["configurations"]}
    require(list(m4_by_id) == list(m7_by_id), "M4/M7 configuration identifiers drift")
    result: list[dict[str, Any]] = []
    for configuration_id in m4_by_id:
        old = m4_by_id[configuration_id]
        new = m7_by_id[configuration_id]
        require(old["name"] == new["name"], f"configuration name drift: {configuration_id}")
        result.append(
            {
                "configuration_id": configuration_id,
                "name": old["name"],
                "m4_release_state": {
                    "mass": old["mass"]["status"],
                    "center_of_mass": old["cg"]["status"],
                    "inertia": old["inertia"]["status"],
                    "bounding_box": old["bbox"]["status"],
                    "collision": old["collision"]["status"],
                    "overall": old["status"],
                },
                "m7_r2_design_model_candidate": {
                    "mass_kg": new["mass"]["value_kg"],
                    "mass_standard_uncertainty_kg": new["mass"]["standard_uncertainty_kg"],
                    "center_of_mass_S_m": new["center_of_mass"]["xyz_m"],
                    "center_of_mass_standard_uncertainty_m": new["center_of_mass"]["standard_uncertainty_xyz_m"],
                    "inertia_about_system_cg_S_kg_m2": new["inertia"]["components_kg_m2"],
                    "inertia_standard_uncertainty_components_kg_m2": new["inertia"]["standard_uncertainty_components_kg_m2"],
                    "authority": new["mass"]["authority"],
                },
                "m7_to_m4_binding_field": {
                    "m4_configuration_library_name": new["m4_configuration_library_name"],
                    "status": "HOLD_EMPTY_SOURCE_BINDING_FIELD__IDENTITY_MATCHED_BY_ID_AND_NAME_FOR_PREBIND_ONLY",
                },
                "binding_state": "PREBIND_ONLY__NOT_M4_RELEASED__NOT_SIM13_PRODUCTION_BOUND",
                "required_reissue_action": "recompute from the authorized unified R2 assembly, preserve uncertainty and frame S, then bind through a versioned consumer interface",
            }
        )
    return result


def build_cad_brief(
    assembly: dict[str, Any],
    product_structure: dict[str, Any],
    solar: dict[str, Any],
    frame_tree: dict[str, Any],
) -> str:
    bus = next(item for item in product_structure["product_tree"] if item["id"] == "BUS_PRIMARY_STRUCTURE")
    solar_root = solar["parameters"]["root_hinge_line"]
    legacy_left = frame_tree["frames"]["F_L"]["origin_S_mm"]
    legacy_right = frame_tree["frames"]["F_R"]["origin_S_mm"]
    return f"""# Unified R2 数字样机 CAD Brief V1

## 1. 工程目的

在独立授权条件全部满足后，一次性重发 `DESIGN_FREEZE_ASSEMBLY_R2_V1`，供后续动力学、连续碰撞、抓取接触和具身策略门控使用。当前文件仅是**文档化预绑定 brief**，不授权也不生成 CAD、网格、URDF、FEA 或仿真结果。

## 2. 当前继承基线

- M4 受限数字样机继续有效，不重做；其发布上限为竞赛工程数字样机。
- 当前 M7 R1 装配报告裁决：`{assembly['verdict']}`；默认构型：`{assembly['default_configuration']}`。
- 当前 R1 中性 STEP 为有效组合体，报告记载 41 solids；但 B601 仍为 frame/axis witness，夹爪仅 palm，太阳翼仍为 R1 代理。
- 当前 12U `BUS_PRIMARY_STRUCTURE` 只是 {bus['solids']} 个解析实体组成的 **DISPLAY/ENVELOPE proxy**：无内部结构、舱、线束孔和检修开口，且 340.5/366.0 mm 长度尚未调和；不得作为可直接继承的物理主结构权威。
- Solar R2 为独立 `{solar['class']}`，保持候选件身份；本 brief 不把它静默并入 R1 装配。
- 根坐标系为 `{frame_tree['root_frame']}`；长度内部 CAD 单位沿用 mm，动力学边界只转换一次到 m。

## 3. 统一 R2 产品树（未来重发）

1. 12U 服务星：先冻结物理主结构来源并解决 340.5/366.0 mm 长度冲突；当前 6-primitive envelope proxy 只可用于显示/粗包络，不能冒充内部结构。
2. spacecraft load bridge 与 M3R Stage-A/Stage-B，保留已冻结接口基准、孔系和 +X_S 轴向站位语义。
3. B601 六转动关节完整物理实体；不得把 q0 frame/axis witness 当作碰撞实体。
4. Gripper R1 palm、两指、驱动/限位/保持语义及左右接触帧。
5. 左右翼 Solar R2，每翼 3 叶片；部署、单翼失效、双翼失效和收拢状态须由同一参数源生成。
6. ARM HDRM、线束/导向/夹持/连接器有限体积；Route-C 仅在 Checkpoint-B 8/8 且另有 CAD 授权后进入实体化。
7. 22 kg 目标星和 150 kg 碎片只作为场景外部资产；`T_S_target` 未冻结时不得写入主 STEP。

## 4. 帧与运动语义

- `spacecraft_assembly_frame` 与 `S` 仅按冻结 identity alias 等价。
- `M_DYNAMICS` 与 `B601_ARM_BASE_PHYSICAL` 必须保持不同，禁止静默别名。
- 任一必要变换为 null 时，该构型/动作必须被 mask 为 UNKNOWN/HOLD。
- 每个活动关节必须给出父子链、零位、正向运动的物理描述、轴、上下限、速度/力矩或推力限制以及故障锁定语义。
- M4 `F_L/F_R` 是 legacy R1 原点 `{legacy_left}` / `{legacy_right}` mm；Solar R2 候选根铰线为 `|y|={solar_root['y_abs_mm']} mm, z={solar_root['z_mm']} mm`、轴向 X_S。二者**不得数值继承或静默别名**；必须新建并冻结 R2 左/右根铰链 frame 及其变换。
- B601 六轴、夹爪两指、Solar R2 和 HDRM 必须使用一致的显式输入驱动 CAD、URDF 与构型表；夹爪 URDF `velocity=15` 的 SI 模型语义是 15 m/s，但不是物理执行器能力，禁止据此推导开合或任务时序。

## 5. STEP-first 交付合同

未来授权重发以 STEP 为主要几何验证产物，执行链固定为 `source generator → native model → STEP → independent inspect → snapshots`。必须同时生成：

- 原生参数模型：`DESIGN_FREEZE_ASSEMBLY_R2_V1.FCStd`
- 中性主模型：`DESIGN_FREEZE_ASSEMBLY_R2_V1.step`
- 可视网格：按 link/component 命名的 STL
- 简化碰撞网格：独立于 visual mesh，保留几何误差/膨胀量记录
- 原生 GLB：不得通过 STL 反向转换冒充原生 GLB
- 生成器源、构建报告、源哈希清单、系统 URDF/Xacro 生成物及消费端接口文件

## 6. 九构型一次性重发

必须覆盖 C01–C09：DEPLOYED_NOMINAL、LEFT_PANEL_FAIL、RIGHT_PANEL_FAIL、BOTH_PANEL_FAIL、ARM_STOWED_ONORBIT、ARM_TASK_READY、PREGRASP、TARGET_CAPTURE_22KG、TARGET_CAPTURE_150KG。每个构型均须重算系统质量、系统质心、关于系统质心且在 S 表达的完整惯量、整机包围盒、静态/连续碰撞状态和不确定度；禁止把现有 M7 DESIGN_MODEL_R2 数值直接改名为 M4 released value。

## 7. 验证与审图最低集

- BRep/STEP 冷启动：对象数、solid 数、closed/valid、零体积/重复实体、命名和层级一致性。
- 接口：M3R、load bridge、B601 基座、夹爪、Solar R2 根铰链与 HDRM 对齐及间隙。
- 运动：9 构型静态碰撞 + B601/太阳翼/夹爪连续扫掠；碰撞几何不得使用 witness。
- 质量：CAD/URDF/质量账本逐 link/component 对账，参考点和坐标系显式。
- 快照：等轴、反等轴、顶、前；至少给出干涉区域和每个失败/锁定构型的局部图。
- 消费：URDF 树/mesh 路径/惯量正定、Sim13 loader smoke test、FAIL/UNKNOWN 负控和版本哈希拒绝测试。

## 8. 分阶段准入（禁止循环依赖）

### 8.1 CAD/URDF 几何重发前置条件

1. 另行签发哈希绑定的 `UNIFIED_R2_REBASE_EXECUTION_AUTHORIZED=true` 执行记录；它是整机 R2 重发授权，不得与 Route-C 局部 CAD 授权混同或相互替代。
2. 12U physical-structure authority 与 340.5/366.0 mm 长度冲突完成独立裁决。
3. R2 左/右根铰链 frame 和 `T_S_R2_ROOT_L/R` 冻结，legacy R1 `F_L/F_R` 不得复用。
4. Route-C P01–P13 具有 value、unit、tolerance/uncertainty、traceable source 和 authority class。
5. Checkpoint-B 由 2/8 提升至 8/8，随后另发 `ROUTE_C_CAD_AUTHORIZED=true` 的有效授权记录。
6. 重发执行时重新测量内存；需 `available >= 6 GiB` 或得到**针对该次重发**的显式 Owner Override 与风险记录。历史 M4 override 不自动继承。

### 8.2 可并行但不构成 CAD 前置的科学决策

1. ODR-GPT-07 冻结 R2 ROM 维数/接触窗候选验证范围。
2. ODR-GPT-08 冻结 protocol-matched R1/R2 comparator 语义。

### 8.3 几何完成后的终局 Release joins

1. 对新实体 CAD 执行连续扫掠和 rated-envelope mission coverage；不得以旧几何提前宣称 PASS。
2. 用受控实测/供应商数据闭合夹爪真实速度、载荷速度、接触时序和不确定度；不得消费 URDF 15 m/s 字面量作为硬件能力。
3. 重算九构型质量属性、R2 Full-Flex 和耦合诊断，完成独立重放/红队/证伪。
4. 生成新版本机械接口并重绑 Sim13，最后通过独立 production/contact/handoff Gates。

## 9. 当前裁决

`HOLD_PREBIND_DOCUMENT_SET_COMPLETE__ENGINEERING_SPECIFICATION_INCOMPLETE__NO_GEOMETRY_EXECUTION_AUTHORITY`
"""


def build_urdf_ledger(
    urdf: dict[str, Any],
    source_pin: dict[str, Any],
    gripper_pack: dict[str, Any],
    gripper_pointer: dict[str, Any],
    gripper_gate: dict[str, Any],
    pin_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    joint_authority_annotations: list[dict[str, Any]] = []
    for joint in urdf["joints"]:
        if joint["type"] == "fixed":
            velocity_semantic = None
            physical_velocity_authority = "NOT_APPLICABLE_FIXED_JOINT"
        elif joint["type"] == "prismatic":
            velocity_semantic = "m/s"
            physical_velocity_authority = "HOLD_UNVALIDATED_AUTO_EXPORTED_MODEL_LIMIT"
        else:
            velocity_semantic = "rad/s"
            physical_velocity_authority = "HOLD_MODEL_LIMIT_NOT_PHYSICAL_ACTUATOR_CHARACTERIZATION"
        joint_authority_annotations.append(
            {
                "joint_name": joint["name"],
                "joint_type": joint["type"],
                "axis_and_position_limit_source": "accepted B601 URDF",
                "velocity_literal": None if joint["limit"] is None else joint["limit"]["velocity"],
                "velocity_si_semantic_unit": velocity_semantic,
                "velocity_source_class": "URDF_MODEL_LIMIT_ONLY",
                "physical_velocity_authority": physical_velocity_authority,
                "positive_motion_description_status": joint["positive_motion_semantics_status"],
            }
        )
    return {
        "schema": "UNIFIED_R2_URDF_DESIGN_LEDGER_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "artifact_class": "DOCUMENTATION_ONLY_PREBIND_LEDGER",
        "source_artifact": {
            "path": source_pin["path"],
            "sha256": source_pin["sha256"],
            "classification": "ACCEPTED_IMPORTED_B601_ARTIFACT__NOT_FULL_SYSTEM_URDF",
            "project_gen_urdf_source": None,
            "generator_status": "NOT_REGISTERED_IN_CURRENT_PROJECT_AUDIT",
        },
        "unit_contract": {
            "length": "m",
            "mass": "kg",
            "revolute_position": "rad",
            "prismatic_position": "m",
            "revolute_velocity_semantic": "rad/s",
            "prismatic_velocity_semantic": "m/s",
            "inertia": "kg*m^2",
            "mesh_unit_and_scale_status": "HOLD_EXPLICIT_SOURCE_UNIT_AND_SCALE_AUDIT_REQUIRED_FOR_REISSUE",
        },
        "parsed_robot": urdf,
        "joint_authority_annotations": joint_authority_annotations,
        "active_gripper_velocity_authority": {
            "active_consumption_pointer": {
                "path": pin_by_id["GRIPPER_ACTIVE_CONSUMPTION_POINTER"]["path"],
                "sha256": pin_by_id["GRIPPER_ACTIVE_CONSUMPTION_POINTER"]["sha256"],
                "selected_pack": gripper_pointer["active_pack"],
            },
            "active_engineering_pack": {
                "path": pin_by_id["GRIPPER_ACTIVE_ENGINEERING_PACK"]["path"],
                "sha256": pin_by_id["GRIPPER_ACTIVE_ENGINEERING_PACK"]["sha256"],
                "urdf_joint_type": gripper_pack["frozen_inputs"]["urdf_joint_type"],
                "urdf_velocity_limit_raw": gripper_pack["frozen_inputs"]["urdf_velocity_limit_raw"],
                "urdf_velocity_semantic_unit": gripper_pack["frozen_inputs"]["urdf_velocity_semantic_unit"],
                "urdf_velocity_semantic_value_m_s": gripper_pack["frozen_inputs"]["urdf_velocity_semantic_value_m_s"],
                "urdf_velocity_source_classification": gripper_pack["frozen_inputs"]["urdf_velocity_source_classification"],
                "physical_capability_m_s": gripper_pack["frozen_inputs"]["urdf_velocity_physical_capability_m_s"],
                "physical_uncertainty_m_s": gripper_pack["frozen_inputs"]["urdf_velocity_physical_uncertainty_m_s"],
            },
            "companion_gate": {
                "path": pin_by_id["GRIPPER_VELOCITY_UNIT_GATE"]["path"],
                "sha256": pin_by_id["GRIPPER_VELOCITY_UNIT_GATE"]["sha256"],
                "verdict": gripper_gate["verdict"],
                "physical_actuator_speed_authority": gripper_gate["physical_actuator_speed_authority"],
                "physical_gripper_timing_ready": gripper_gate["physical_gripper_timing_ready"],
                "production_dynamics_ready": gripper_gate["production_dynamics_ready"],
                "physical_contact_rl_ready": gripper_gate["physical_contact_rl_ready"],
            },
            "consumption_rule": "15 m/s is the literal SI semantic of the two prismatic URDF model limits only; never derive no-load/rated/contact speed, opening/closing time, mission timing, contact impulse, or controller limits from it",
        },
        "current_coverage": {
            "covered": [
                "B601 base_link through link6 kinematic chain",
                "gripper palm fixed joint",
                "two prismatic finger links",
                "declared per-link inertials",
                "local visual and collision mesh references",
            ],
            "not_covered_by_a_unified_system_urdf": [
                "12U spacecraft structure",
                "spacecraft load bridge",
                "M3R Stage-A/Stage-B",
                "Solar R2 left and right wings",
                "ARM HDRM",
                "Route-C harness finite volumes",
                "22 kg target satellite",
                "150 kg debris target",
            ],
        },
        "known_holds": [
            "The accepted URDF has no registered project-side gen_urdf() SSOT.",
            "Its collision meshes are not operational collision authority because current assembly audits identify phantom/desktop-base and witness limitations.",
            "Positive-motion physical semantics are not complete even though numerical axes and limits are present.",
            "Gripper R1 corrections are not reconciled into a versioned generated system URDF.",
            "The gripper 15 m/s URDF literal is not measured physical speed; physical speed, timing and uncertainty remain null/HOLD.",
            "There is no single 12U+B601+M3R+Gripper+Solar-R2 system URDF.",
            "No production Sim13 consumer binding exists for this future R2 system description.",
        ],
        "future_generator_contract": {
            "required_function": "gen_urdf()",
            "single_source_inputs": [
                "component and link identities",
                "parent-child frame transforms",
                "joint zero and positive-motion semantics",
                "joint limits with per-field model-versus-physical authority; no unknown actuator capability may be copied from a URDF literal",
                "visual and simplified collision mesh mappings",
                "per-link mass, center of mass, inertia, uncertainty and authority class",
                "nine named configurations and failure/lock semantics",
            ],
            "mesh_dependencies_from_cad_workflow": [
                "versioned visual meshes generated and inspected by the CAD/mesh workflow",
                "separate simplified collision meshes with approximation/error metadata",
            ],
            "required_outputs": [
                "versioned explicit system URDF",
                "design ledger",
                "validation report",
                "source/output SHA-256 manifest",
            ],
            "optional_output": "Xacro may be emitted in addition to, never instead of, the explicit validated URDF",
            "validation": [
                "tree has exactly one root and no disconnected links",
                "all mesh references resolve with explicit units/scales",
                "all masses are positive and inertias are symmetric positive definite",
                "joint axes, limits, origins and positive-motion descriptions agree with CAD",
                "CAD and URDF link mass totals reconcile within declared uncertainty",
                "consumer rejects stale hashes, null transforms, invalid collisions and unauthorized configurations",
                "consumer cannot derive physical timing from model-only velocity literals",
            ],
        },
        "assumption_ledger": [
            {"assumption": "omitted mesh scale follows URDF default [1,1,1]", "status": "PARSER_SEMANTIC_ONLY", "release_effect": "mesh source-unit audit still HOLD"},
            {"assumption": "accepted link inertials are hybrid vendor/imported values", "status": "MEDIUM_CONFIDENCE", "release_effect": "not as-built or qualification authority"},
            {"assumption": "numerical joint axes/limits encode complete physical positive motion", "status": "REJECTED", "release_effect": "positive-motion description must be added before generated-system release"},
            {"assumption": "URDF gripper velocity 15 means 15 mm/s hardware speed", "status": "REJECTED", "release_effect": "SI semantic is 15 m/s model limit; physical timing remains HOLD"},
        ],
        "authority_flags": {
            "new_urdf_generated": False,
            "system_urdf_complete": False,
            "collision_authority": False,
            "production_dynamics_ready": False,
            "sim13_production_binding_authorized": False,
            "owner_accepted": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
    }


def build_rebase_contract(
    pins: list[dict[str, Any]],
    m4_gate: dict[str, Any],
    frame_tree: dict[str, Any],
    assembly: dict[str, Any],
    product_structure: dict[str, Any],
    solar: dict[str, Any],
    gripper_pack: dict[str, Any],
    gripper_gate: dict[str, Any],
    configurations: list[dict[str, Any]],
    checkpoint_b: dict[str, Any],
    registry: dict[str, Any],
    odr07: dict[str, Any],
    odr08: dict[str, Any],
    sim13_audit: dict[str, Any],
    sim13_bootstrap: dict[str, Any],
) -> dict[str, Any]:
    bus = next(item for item in product_structure["product_tree"] if item["id"] == "BUS_PRIMARY_STRUCTURE")
    legacy_left = frame_tree["frames"]["F_L"]["origin_S_mm"]
    legacy_right = frame_tree["frames"]["F_R"]["origin_S_mm"]
    solar_root = solar["parameters"]["root_hinge_line"]
    cad_execution_inputs = {
        "unified_r2_rebase_execution_authorization_recorded": False,
        "bus_physical_authority_resolved": False,
        "solar_r2_root_frames_frozen": False,
        "route_c_registry_13_of_13": False,
        "checkpoint_b_8_of_8": False,
        "separate_route_c_cad_authority": False,
        "memory_admitted_for_this_execution": False,
    }
    full_flex_inputs = {"odr_gpt_07_selected": False, "odr_gpt_08_selected": False}
    downstream_release_inputs = {
        "unified_r2_geometry_and_sweeps_pass": False,
        "full_flex_gate_pass": False,
        "mission_harness_coverage_pass": False,
        "gripper_physical_actuator_gate_pass": False,
        "nine_configuration_properties_released": False,
        "versioned_sim13_rebind_gate_pass": False,
        "mechanical_to_embodied_handoff_pass": False,
    }
    return {
        "schema": "UNIFIED_R2_DIGITAL_PROTOTYPE_REBASE_CONTRACT_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "status": "PREBIND_DOCUMENT_SET_COMPLETE__ENGINEERING_SPECIFICATION_INCOMPLETE__EXECUTION_HOLD",
        "artifact_class": "DOCUMENTATION_ONLY__NOT_CAD_NOT_URDF_NOT_RELEASE",
        "purpose": "freeze a one-shot future Unified R2 CAD/URDF/configuration/consumer reissue contract without altering current evidence or authority",
        "predecessor_state": {
            "m4_scoped_release": m4_gate["overall_status"],
            "m4_digital_prototype_token_issued": m4_gate["release_tokens"]["digital_prototype"]["issued"],
            "m4_must_not_be_rebuilt": True,
            "m7_r1_assembly_verdict": assembly["verdict"],
            "solar_r2_class": solar["class"],
            "solar_r2_is_separate_from_m7_r1_assembly": True,
        },
        "future_baseline": {
            "baseline_id": "DESIGN_FREEZE_ASSEMBLY_R2_V1",
            "reissue_policy": "NEW_VERSIONED_UNIFIED_BASELINE__NO_MUTATION_OF_R1_OR_M4_HISTORY",
            "geometry_authority_order": [
                "authorized parameter/source ledger",
                "native parametric model",
                "neutral STEP",
                "visual and simplified collision meshes",
                "generated system URDF/Xacro",
                "consumer interface and runtime gate",
            ],
        },
        "component_rebase_matrix": [
            {"component": "12U bus", "inherit": "M7 R1 DISPLAY_AND_ENVELOPE_PROXY_ONLY__NOT_PHYSICAL_STRUCTURE_AUTHORITY", "future_action": "select/freeze a physical structure source, reconcile 340.5 versus 366.0 mm length, and model required internal structure/openings before release"},
            {"component": "spacecraft load bridge", "inherit": "M7 candidate and frozen datums", "future_action": "resolve physical membership and load-path continuity before release"},
            {"component": "M3R", "inherit": "M3R Stage-A/Stage-B working BRep and interface datums", "future_action": "hash-bind and revalidate alignment; do not remodel from prose"},
            {"component": "B601", "inherit": "accepted URDF kinematic/inertial chain", "future_action": "replace frame/axis witness in unified CAD with valid physical link and simplified collision geometry"},
            {"component": "gripper", "inherit": "R1 palm, accepted URDF finger chain, and active V2 unit-semantics pack", "future_action": "reconcile fingers/contact/collision and close physical actuator speed/timing; never consume the 15 m/s model literal as hardware capability"},
            {"component": "solar arrays", "inherit": "separate Solar R2 candidate geometry only; legacy R1 F_L/F_R transforms excluded", "future_action": "freeze new R2 left/right root frames before replacing R1 proxies; preserve candidate/qualification holds"},
            {"component": "Route-C harness/HDRM", "inherit": "no physical CAD authority", "future_action": "generate only after P01-P13, Checkpoint-B 8/8 and separate CAD authorization"},
            {"component": "targets", "inherit": "independent scenario assets", "future_action": "bind only after target identity/contact surface and T_S_target are frozen"},
        ],
        "frame_contract": {
            "canonical_root": frame_tree["root_frame"],
            "matrix_convention": frame_tree["matrix_convention"],
            "rotation_convention": frame_tree["rotation_convention"],
            "exact_alias": "spacecraft_assembly_frame == S",
            "forbidden_alias": "M_DYNAMICS != B601_ARM_BASE_PHYSICAL",
            "unknown_transform_policy": "null_transform_and_action_mask",
            "witness_policy": "B601 q0 frame/axis witness is never physical collision geometry",
            "unit_boundary": "CAD mm; dynamics m; convert exactly once",
        },
        "solar_r2_root_frame_reconciliation": {
            "status": "HOLD_PANEL_ROOT_TO_HINGE_AXIS_REGISTRATION_NOT_ESTABLISHED",
            "legacy_r1_frames": {
                "F_L_origin_S_mm": legacy_left,
                "F_R_origin_S_mm": legacy_right,
                "classification": "LEGACY_R1_ONLY__FORBIDDEN_AS_SOLAR_R2_ROOT_TRANSFORM",
            },
            "solar_r2_candidate_hinge_line": {
                "left_origin_partial_S_mm": [None, solar_root["y_abs_mm"], solar_root["z_mm"]],
                "right_origin_partial_S_mm": [None, -solar_root["y_abs_mm"], solar_root["z_mm"]],
                "axis": "X_S",
                "x_coordinate_status": "DERIVE_AND_FREEZE_FROM_AUTHORIZED_R2_GEOMETRY__NOT_INFER_FROM_R1_F_L_F_R",
            },
            "forbidden_operations": [
                "alias R2 root frames to M4 F_L/F_R",
                "copy the R1 F_L/F_R origins into the R2 assembly",
                "average R1 and R2 hinge positions",
                "claim deployed/stowed collision or mass properties before T_S_R2_ROOT_L/R are frozen",
            ],
            "exit_condition": "issue versioned T_S_R2_ROOT_L and T_S_R2_ROOT_R from an authorized geometry source, then independently verify hinge-axis and panel-root registration",
        },
        "bus_12u_geometry_authority": {
            "status": "HOLD_12U_PHYSICAL_STRUCTURE_AUTHORITY_AND_LENGTH_RECONCILIATION",
            "current_geometry_class": "DISPLAY_AND_ENVELOPE_PROXY_ONLY",
            "source_solids": bus["solids"],
            "composition_note": bus["composition_note"],
            "holds": bus["holds"],
            "model_to_model_delta": bus["model_to_model_delta"],
            "consumption_rule": "may support coarse display/envelope diagnostics only; must not be labelled physical primary structure, internal layout, load path, access geometry, or manufacturing definition",
        },
        "configuration_contract": configurations,
        "future_output_contract": {
            "native_cad": "DESIGN_FREEZE_ASSEMBLY_R2_V1.FCStd",
            "neutral_cad": "DESIGN_FREEZE_ASSEMBLY_R2_V1.step",
            "visual_meshes": "named per component/link STL",
            "collision_meshes": "named simplified STL with approximation/error record",
            "native_glb": "native GLB; no STL round-trip masquerade",
            "robot_description": "generated versioned explicit system URDF; Xacro optional only as an additional source form",
            "supporting": ["source generator", "build report", "design ledger", "configuration library", "validation report", "snapshot package", "SHA-256 manifest", "consumer interface"],
        },
        "validation_contract": {
            "geometry": ["native and STEP cold reopen", "BRep valid/closed/positive-volume", "object/solid/name/product-tree agreement", "no duplicate or witness collision bodies"],
            "interfaces": ["M3R-load-bridge-B601 alignment", "gripper/contact frames", "R2 root frames independently reconciled against legacy R1 F_L/F_R", "HDRM and finite harness volumes"],
            "motion_and_collision": ["C01-C09 static states", "B601 continuous sweep", "solar deployment/failure sweep", "gripper two-finger sweep", "clearance witnesses and fail-closed unknowns"],
            "mass_properties": ["nine configurations", "mass/CG/full inertia/uncertainty", "S frame and system-CG reference", "CAD-URDF-ledger reconciliation"],
            "visual_review": ["isometric", "opposite isometric", "top", "front", "local interference and failed-state views"],
            "consumer": ["system URDF validation", "mesh resolution", "Sim13 loader smoke", "stale-hash rejection", "FAIL/UNKNOWN negative controls", "independent production-binding Gate"],
        },
        "current_authority_inputs": {
            "odr_gpt_07": {
                "status": odr07["status"],
                "selected_option": odr07["owner_decision_record"]["selected_option"],
                "recommended_option": odr07["engineering_recommendation"]["recommended_option"],
            },
            "odr_gpt_08": {
                "status": odr08["status"],
                "selected_option": odr08["owner_decision_record"]["selected_option"],
                "recommended_option": odr08["engineering_recommendation"]["recommended_option"],
            },
            "route_c_checkpoint_b": {
                "outcome": checkpoint_b["checkpoint_outcome"],
                "admission_pass": checkpoint_b["admission"]["summary"]["pass"],
                "admission_total": checkpoint_b["admission"]["summary"]["conditions_total"],
                "route_c_cad_authorized": checkpoint_b["admission"]["ROUTE_C_CAD_AUTHORIZED"],
            },
            "route_c_registry": registry["summary"],
            "bus_12u": {
                "geometry_class": "DISPLAY_AND_ENVELOPE_PROXY_ONLY",
                "solid_count": bus["solids"],
                "holds": bus["holds"],
            },
            "gripper_velocity": {
                "urdf_velocity_semantic_value_m_s": gripper_pack["frozen_inputs"]["urdf_velocity_semantic_value_m_s"],
                "urdf_velocity_source_classification": gripper_pack["frozen_inputs"]["urdf_velocity_source_classification"],
                "physical_capability_m_s": gripper_pack["frozen_inputs"]["urdf_velocity_physical_capability_m_s"],
                "physical_uncertainty_m_s": gripper_pack["frozen_inputs"]["urdf_velocity_physical_uncertainty_m_s"],
                "gate_verdict": gripper_gate["verdict"],
                "physical_actuator_speed_authority": gripper_gate["physical_actuator_speed_authority"],
                "physical_gripper_timing_ready": gripper_gate["physical_gripper_timing_ready"],
            },
            "sim13": {
                "binding_audit_verdict": sim13_audit["verdict"],
                "baseline_mutation_authorized": sim13_audit["baseline_mutation_authorized"],
                "current_mechanical_interface_path": sim13_bootstrap["mechanical_interface_path"],
                "training_success_claimed": sim13_bootstrap["training_success_claimed"],
            },
        },
        "authorization_state_machine": {
            "cad_urdf_execution_prerequisites": {
                "current_inputs": cad_execution_inputs,
                "rule": "ALL_REQUIRED_EXACT_TRUE",
                "authorized": all_required_exact_true(cad_execution_inputs),
            },
            "parallel_full_flex_decision_prerequisites": {
                "current_inputs": full_flex_inputs,
                "rule": "ALL_REQUIRED_EXACT_TRUE",
                "authorized": all_required_exact_true(full_flex_inputs),
                "note": "these scientific decisions do not substitute for Route-C CAD admission and are not a geometry-predecessor loop",
            },
            "downstream_release_joins_after_geometry": {
                "current_inputs": downstream_release_inputs,
                "rule": "ALL_REQUIRED_EXACT_TRUE",
                "released": all_required_exact_true(downstream_release_inputs),
            },
        },
        "entry_sequence": [
            "Resolve 12U physical-structure authority/length and freeze the two Solar R2 root frames.",
            "Close Route-C P01-P13; re-run Checkpoint-B to 8/8; then obtain separate Route-C CAD authorization.",
            "Issue a separately hash-bound Unified R2 rebase execution authorization; Route-C CAD authority does not substitute for this record.",
            "At execution time satisfy the 6 GiB memory gate or obtain a new run-specific Owner override and risk record.",
            "Execute one versioned Unified R2 CAD/mesh/URDF reissue and complete independent geometry/configuration validation.",
            "In parallel, resolve ODR-GPT-07/08 for the Full-Flex/comparator validation branch; neither creates CAD authority.",
            "Using the new geometry, close continuous sweeps, rated-envelope mission coverage, gripper physical actuation, nine-configuration properties and Full-Flex gates.",
            "Only after those joins issue a versioned consumer interface, update Sim13 loader, and pass independent production/contact/handoff Gates.",
            "Only then admit physics-gated RL training or production grasp claims.",
        ],
        "execution_record": {
            "prebuild_memory_observation": {
                "available_physical_gib": PREBUILD_AVAILABLE_PHYSICAL_GIB,
                "threshold_gib": MEMORY_THRESHOLD_GIB,
                "memory_gate_passed": False,
                "observation_date_local": GENERATED_DATE_LOCAL,
                "observation_time_local": None,
                "classification": "NONAUTHORITATIVE_ROUNDED_READ_ONLY_SAMPLE__NOT_EXECUTION_ADMISSION",
                "observation_note": "time-of-day was not recorded; no heavy process was launched; execution must remeasure",
            },
            "historical_m4_owner_override_inherited": False,
            "current_owner_override_for_heavy_cad": False,
            "cad_or_mesh_generation_performed": False,
            "urdf_generation_performed": False,
            "fea_or_simulation_performed": False,
        },
        "source_pins": pins,
        "authority_flags": {
            "engineering_specification_complete": False,
            "geometry_execution_authorized": False,
            "full_flex_validation_authorized": False,
            "consumer_rebind_authorized": False,
            "rebase_execution_authorized": False,
            "route_c_cad_authorized": False,
            "heavy_solver_authorized": False,
            "sim13_baseline_mutation_authorized": False,
            "production_dynamics_ready": False,
            "physical_contact_ready": False,
            "physics_gated_rl_ready": False,
            "owner_accepted": False,
            "next_stage_authorized": False,
            "release_credit": False,
            "terminal_release_candidate_generated": False,
        },
    }


def criterion(identifier: str, name: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {"id": identifier, "name": name, "pass": passed, "state": "PASS" if passed else "HOLD", "evidence": evidence}


def build_readiness(urdf: dict[str, Any], terminal: dict[str, Any]) -> dict[str, Any]:
    criteria = [
        criterion("PRB-01", "M4 scoped digital prototype inherited", True, "M4_DIGITAL_PROTOTYPE_RELEASED remains issued; M4 is not rebuilt"),
        criterion("PRB-02", "M7 R1 unified assembly is a valid predecessor", True, "M7 report PASS with explicit holds; 41 STEP solids"),
        criterion("PRB-03", "Solar R2 candidate is hash-bound separately", True, "FCStd/STEP/report source pins verified; not silently merged"),
        criterion("PRB-04", "accepted B601 URDF tree and local meshes parse", True, f"{urdf['link_count']} links, {urdf['joint_count']} joints, all local mesh references exist"),
        criterion("PRB-05", "nine R2 design-model mass-property rows exist", True, "C01-C09 have mass/CG/inertia and uncertainty in M7 V3 R2"),
        criterion("PRB-06", "unified R2 physical assembly exists", False, "current unified assembly contains R1 solar proxies and B601 witnesses"),
        criterion("PRB-07", "generated full-system URDF exists", False, "only accepted B601 subassembly URDF is present; no registered project gen_urdf()"),
        criterion("PRB-08", "Route-C Checkpoint-B admission is 8/8", False, "current admission is 2/8 PASS and 6/8 FAIL"),
        criterion("PRB-09", "separate Route-C CAD authorization exists", False, "ROUTE_C_CAD_AUTHORIZED=false"),
        criterion("PRB-10", "ODR-GPT-07 has an Owner selection", False, "approval request remains PENDING_OWNER_DECISION with selected_option=null"),
        criterion("PRB-11", "ODR-GPT-08 has an Owner selection", False, "approval request remains PENDING_OWNER_DECISION with selected_option=null"),
        criterion("PRB-12", "current Sim13 production mechanical binding is valid", False, "newer M7 evidence invalidates the V1 production binding; baseline mutation is unauthorized"),
        criterion("PRB-13", "rated-envelope mission harness is closed", False, "terminal technical verdict retains MISSION_HARNESS_FAIL"),
        criterion("PRB-14", "nine-configuration system collision release exists", False, "M4 collision evaluation is 0/9 released; no unified R2 sweep"),
        criterion("PRB-15", "formal snapshot review packet exists for unified R2", False, "no unified R2 geometry was created; snapshot review is deferred to authorized reissue"),
        criterion("PRB-16", "current heavy-execution memory gate is satisfied", False, f"prebuild audit sample {PREBUILD_AVAILABLE_PHYSICAL_GIB:.3f} GiB < {MEMORY_THRESHOLD_GIB:.1f} GiB; no current override"),
        criterion("PRB-17", "12U physical primary-structure geometry is authoritative", False, "current six-primitive bus is a display/envelope proxy; internal structure absent and 340.5/366.0 mm length unresolved"),
        criterion("PRB-18", "Solar R2 left/right root frames are frozen", False, "legacy R1 F_L/F_R differs from the Solar R2 candidate hinge line; T_S_R2_ROOT_L/R not established"),
        criterion("PRB-19", "gripper physical speed and contact timing are authoritative", False, "URDF 15 m/s is an unvalidated model literal; measured/rated/contact speed, timing and uncertainty remain null/HOLD"),
        criterion("PRB-20", "independent Unified R2 rebase execution authorization exists", False, "no separately hash-bound UNIFIED_R2_REBASE_EXECUTION_AUTHORIZED=true record exists; Route-C CAD authority is not equivalent"),
    ]
    passed = sum(item["pass"] for item in criteria)
    return {
        "schema": "UNIFIED_R2_PREBIND_READINESS_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "scope": "documentation-only readiness for future Unified R2 one-shot reissue",
        "terminal_context": {
            "outcome": terminal["outcome"],
            "technical_verdict": terminal["technical_verdict"],
        },
        "criteria": criteria,
        "summary": {"criteria_total": len(criteria), "pass": passed, "hold": len(criteria) - passed},
        "current_allowed_action": "documentation, source acquisition, traceable registry closure, and Owner decision review only",
        "current_prohibited_action": "Unified R2 CAD/mesh/URDF execution, Route-C geometry, production Sim13 mutation, formal FEA, production contact or RL claims",
        "authority_flags": {
            "engineering_specification_complete": False,
            "geometry_execution_authorized": False,
            "full_flex_validation_authorized": False,
            "consumer_rebind_authorized": False,
            "rebase_execution_authorized": False,
            "route_c_cad_authorized": False,
            "heavy_solver_authorized": False,
            "sim13_baseline_mutation_authorized": False,
            "production_dynamics_ready": False,
            "physical_contact_ready": False,
            "physics_gated_rl_ready": False,
            "owner_accepted": False,
            "next_stage_authorized": False,
            "release_credit": False,
            "terminal_release_candidate_generated": False,
        },
    }


def build_gate(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "UNIFIED_R2_PREBIND_GATE_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "outcome": "HOLD",
        "technical_verdict": "HOLD_PREBIND_DOCUMENT_SET_COMPLETE__ENGINEERING_SPECIFICATION_INCOMPLETE__GEOMETRY_BLOCKED_BY_REBASE_AUTHORITY_BUS_SOLAR_ROUTE_C_AND_MEMORY__RELEASE_BLOCKED_BY_FULL_FLEX_HARNESS_GRIPPER_AND_RUNTIME_JOINS",
        "scope": "documentation-only prebind draft; no CAD, URDF, FEA, simulation, release, qualification or flight credit",
        "document_set_complete": True,
        "engineering_specification_complete": False,
        "specification_complete": False,
        "readiness_summary": readiness["summary"],
        "blocking_joins": [
            "separately hash-bound Unified R2 rebase execution authorization (not Route-C CAD authority)",
            "12U physical-structure authority and 340.5/366.0 mm length reconciliation",
            "Solar R2 root-frame reconciliation against legacy R1 F_L/F_R",
            "Route-C P01-P13 controlled physical registry",
            "Checkpoint-B 8/8 plus separate CAD authorization",
            "execution-time memory gate or a new explicit Owner override with risk record",
            "authorized Unified R2 CAD/URDF/configuration reissue and snapshot review",
            "ODR-GPT-07 and ODR-GPT-08 decisions for the parallel Full-Flex/comparator branch",
            "rated-envelope mission harness and coverage",
            "gripper physical actuator speed/contact timing characterization",
            "versioned Sim13 mechanical interface and independent production/contact Gates",
        ],
        "preserved_truths": [
            "M4 scoped digital-prototype release remains valid and is not rebuilt.",
            "M7 R1 assembly remains a valid predecessor with explicit holds, not a Unified R2 production assembly.",
            "The M7 six-primitive 12U bus is an envelope/display proxy, not physical primary-structure authority.",
            "Solar R2 remains a separate engineering candidate.",
            "Legacy R1 F_L/F_R transforms are not Solar R2 root-frame authority.",
            "M7 R2 mass properties remain DESIGN_MODEL_R2 candidates, not M4 released values or Sim13 production bindings.",
            "The accepted B601 URDF remains hash-bound imported evidence, not a generated full-system URDF or collision authority.",
            "The gripper 15 m/s URDF literal is a model semantic only; physical speed and timing remain HOLD.",
        ],
        "execution_receipt": {
            "documentation_files_generated": 7,
            "cad_files_generated": 0,
            "mesh_files_generated": 0,
            "urdf_files_generated": 0,
            "fea_runs": 0,
            "simulation_runs": 0,
            "snapshot_review_performed": False,
            "snapshot_review_reason": "inspection/prebind only; no visible geometry changed and heavy execution was not admitted",
            "memory_gate_passed": False,
            "owner_override_used": False,
        },
        "authority_flags": readiness["authority_flags"],
        "owner_accepted": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
        "terminal_release_candidate_generated": False,
    }


def build_receipt(readiness: dict[str, Any], urdf: dict[str, Any]) -> str:
    return f"""# Unified R2 数字样机预绑定回执 V1

- 裁决：`HOLD_PREBIND_DOCUMENT_SET_COMPLETE__ENGINEERING_SPECIFICATION_INCOMPLETE__GEOMETRY_BLOCKED_BY_REBASE_AUTHORITY_BUS_SOLAR_ROUTE_C_AND_MEMORY__RELEASE_BLOCKED_BY_FULL_FLEX_HARNESS_GRIPPER_AND_RUNTIME_JOINS`
- 文档集完成：是；工程规格完成：否；执行授权：否。
- 来源锁：25/25 文件的字节数与 SHA-256 在构建前匹配。
- 预绑定判据：{readiness['summary']['pass']}/{readiness['summary']['criteria_total']} PASS，{readiness['summary']['hold']} HOLD。
- B601 URDF 独立解析：{urdf['link_count']} links / {urdf['joint_count']} joints / {urdf['links_with_inertial']} inertials；声明质量合计 {urdf['total_declared_link_mass_kg']:.15f} kg；本地 mesh 引用全部存在。
- 构型合同：C01–C09 共 9/9；M7 DESIGN_MODEL_R2 数值已进入预绑定账本，但未改名为 M4 released value，也未绑定到 Sim13 production loader。
- 新增显式 HOLD：需独立 Unified R2 rebase 执行授权；12U 当前仅 envelope proxy；Solar R2 根铰链不得继承 legacy R1 `F_L/F_R`；夹爪 15 m/s URDF 字面量不得推导物理/任务时序。
- 本轮生成：CAD brief、URDF ledger、重发合同、readiness、Gate、回执、哈希清单。
- 本轮未生成：FCStd、STEP、STL、GLB、URDF/Xacro、FEA、仿真或训练结果。
- 内存记录：2026-08-24 的无时刻、非权威只读采样约 {PREBUILD_AVAILABLE_PHYSICAL_GIB:.3f} GiB 可用，低于 {MEMORY_THRESHOLD_GIB:.1f} GiB；只用于解释本轮未启动重任务，实际执行必须重测；`memory_gate_passed=false`，`owner_override_used=false`。
- 快照审查：未执行，因为本轮仅检查/预绑定且没有可见几何变更；未来几何重发必须补齐四向快照和局部干涉图。
- `owner_accepted=false`；`next_stage_authorized=false`；`release_credit=false`。
"""


def write_manifest() -> None:
    rows: list[dict[str, Any]] = []
    for pin in SOURCE_PINS:
        rows.append({"class": "SOURCE_PIN", "path": pin["path"], "bytes": pin["bytes"], "sha256": pin["sha256"], "role": pin["role"]})
    for name, role in (
        ("build_unified_r2_prebind.py", "package builder"),
        ("validate_unified_r2_prebind.py", "independent fail-closed validator"),
    ):
        path = PACKAGE / name
        rows.append({"class": "PACKAGE_SOURCE", "path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path), "role": role})
    for name in OUTPUT_NAMES:
        if name == "UNIFIED_R2_PREBIND_SHA256.csv":
            continue
        path = PACKAGE / name
        rows.append({"class": "GENERATED_OUTPUT", "path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path), "role": "documentation-only prebind output"})
    manifest_path = PACKAGE / "UNIFIED_R2_PREBIND_SHA256.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["class", "path", "bytes", "sha256", "role"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    pins = verify_source_pins()
    pin_by_id = {pin["id"]: pin for pin in pins}

    m4_gate = read_json(pin_by_id["M4_RELEASE_GATE"]["path"])
    m4_config = read_yaml(pin_by_id["M4_CONFIGURATION_LIBRARY"]["path"])
    frame_tree = read_yaml(pin_by_id["M4_FRAME_TREE"]["path"])
    m7_gate = read_json(pin_by_id["M7_RELEASE_GATE"]["path"])
    assembly = read_json(pin_by_id["M7_R1_ASSEMBLY_REPORT"]["path"])
    product_structure = read_yaml(pin_by_id["M7_PRODUCT_STRUCTURE"]["path"])
    solar = read_json(pin_by_id["SOLAR_R2_REPORT"]["path"])
    gripper_pack = read_yaml(pin_by_id["GRIPPER_ACTIVE_ENGINEERING_PACK"]["path"])
    gripper_pointer = read_yaml(pin_by_id["GRIPPER_ACTIVE_CONSUMPTION_POINTER"]["path"])
    gripper_gate = read_json(pin_by_id["GRIPPER_VELOCITY_UNIT_GATE"]["path"])
    m7_mass = read_yaml(pin_by_id["M7_R2_MASS_LEDGER"]["path"])
    checkpoint_b = read_json(pin_by_id["ROUTE_C_CHECKPOINT_B"]["path"])
    registry = read_yaml(pin_by_id["ROUTE_C_PHYSICAL_REGISTRY"]["path"])
    terminal = read_json(pin_by_id["TERMINAL_DECISION_GATE"]["path"])
    odr07 = read_yaml(pin_by_id["ODR_GPT_07_REQUEST"]["path"])
    odr08 = read_yaml(pin_by_id["ODR_GPT_08_REQUEST"]["path"])
    sim13_audit = read_json(pin_by_id["SIM13_BINDING_AUDIT"]["path"])
    sim13_bootstrap = read_json(pin_by_id["SIM13_BOOTSTRAP_CONFIG"]["path"])
    urdf = parse_urdf(pin_by_id["B601_ACCEPTED_URDF"]["path"])

    require(m4_gate["release_tokens"]["digital_prototype"]["issued"] is True, "M4 scoped release token lost")
    require(m7_gate["next_stage_authorized"] is False, "M7 unexpectedly authorized the next stage")
    require(assembly["verdict"] == "PASS_DESIGN_FREEZE_ASSEMBLY_BUILD_WITH_EXPLICIT_HOLDS", "M7 assembly verdict drift")
    bus = next(item for item in product_structure["product_tree"] if item["id"] == "BUS_PRIMARY_STRUCTURE")
    require(bus["solids"] == 6 and "12U_DIMENSION_VERIFICATION_HOLD" in bus["holds"], "12U proxy authority drift")
    require("340P5_VS_NATIVE_V2_2_366P0" in " ".join(bus["holds"]), "12U length conflict missing")
    require(solar["next_stage_authorized"] is False and solar["release_credit"] is False, "Solar R2 authority drift")
    require(frame_tree["frames"]["F_L"]["origin_S_mm"] == [-56.75, 113.15, 0.0], "legacy F_L drift")
    require(frame_tree["frames"]["F_R"]["origin_S_mm"] == [-56.75, -113.15, 0.0], "legacy F_R drift")
    require(solar["parameters"]["root_hinge_line"] == {"y_abs_mm": 115.4, "z_mm": -108.15}, "Solar R2 hinge line drift")
    require(gripper_pointer["active_pack"]["sha256"] == pin_by_id["GRIPPER_ACTIVE_ENGINEERING_PACK"]["sha256"], "gripper active pointer drift")
    require(gripper_pack["frozen_inputs"]["urdf_velocity_semantic_value_m_s"] == 15.0, "gripper URDF velocity semantic drift")
    require(gripper_pack["frozen_inputs"]["urdf_velocity_source_classification"] == "UNVALIDATED_AUTO_EXPORTED_MODEL_LIMIT", "gripper velocity class drift")
    require(gripper_pack["frozen_inputs"]["urdf_velocity_physical_capability_m_s"] is None, "gripper physical speed fabricated")
    require(gripper_gate["verdict"] == "GRIPPER_URDF_UNIT_SEMANTICS_RECONCILED__PHYSICAL_ACTUATOR_SPEED_AND_CONTACT_TIMING_HOLD", "gripper Gate drift")
    require(gripper_gate["physical_gripper_timing_ready"] is False and gripper_gate["production_dynamics_ready"] is False, "gripper authority fabricated")
    require(checkpoint_b["admission"]["summary"] == {
        "conditions_total": 8,
        "pass": 2,
        "fail": 6,
        "pass_ids": ["C2-ADM-01", "C2-ADM-07"],
        "fail_ids": ["C2-ADM-02", "C2-ADM-03", "C2-ADM-04", "C2-ADM-05", "C2-ADM-06", "C2-ADM-08"],
    }, "Route-C admission summary drift")
    require(checkpoint_b["admission"]["ROUTE_C_CAD_AUTHORIZED"] is False, "Route-C CAD authority fabricated")
    require(registry["summary"]["entries_total"] == 13 and registry["summary"]["value_non_null"] == 0, "Route-C registry drift")
    require(odr07["owner_decision_record"]["selected_option"] is None, "ODR-GPT-07 no longer pending")
    require(odr08["owner_decision_record"]["selected_option"] is None, "ODR-GPT-08 no longer pending")
    require(sim13_audit["verdict"] == "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE", "Sim13 audit drift")
    require(sim13_audit["baseline_mutation_authorized"] is False, "Sim13 mutation authority fabricated")
    require(urdf["link_count"] == 10 and urdf["joint_count"] == 9, "B601 URDF topology drift")
    require(abs(urdf["total_declared_link_mass_kg"] - 4.695555949342986) < 1e-14, "B601 URDF mass drift")
    require(urdf["all_local_mesh_references_exist"], "B601 URDF has unresolved local meshes")

    configurations = make_configuration_contract(m4_config, m7_mass)
    cad_brief = build_cad_brief(assembly, product_structure, solar, frame_tree)
    urdf_ledger = build_urdf_ledger(
        urdf,
        pin_by_id["B601_ACCEPTED_URDF"],
        gripper_pack,
        gripper_pointer,
        gripper_gate,
        pin_by_id,
    )
    contract = build_rebase_contract(
        pins,
        m4_gate,
        frame_tree,
        assembly,
        product_structure,
        solar,
        gripper_pack,
        gripper_gate,
        configurations,
        checkpoint_b,
        registry,
        odr07,
        odr08,
        sim13_audit,
        sim13_bootstrap,
    )
    readiness = build_readiness(urdf, terminal)
    gate = build_gate(readiness)
    receipt = build_receipt(readiness, urdf)

    write_text("UNIFIED_R2_CAD_BRIEF_V1.md", cad_brief)
    write_yaml("UNIFIED_R2_URDF_DESIGN_LEDGER_V1.yaml", urdf_ledger)
    write_yaml("UNIFIED_R2_DIGITAL_PROTOTYPE_REBASE_CONTRACT_V1.yaml", contract)
    write_json("UNIFIED_R2_PREBIND_READINESS_V1.json", readiness)
    write_json("UNIFIED_R2_PREBIND_GATE_V1.json", gate)
    write_text("UNIFIED_R2_PREBIND_RECEIPT_V1.md", receipt)
    write_manifest()

    print(json.dumps({
        "status": "PREBIND_PACKAGE_BUILT",
        "source_pins_verified": len(pins),
        "outputs": len(OUTPUT_NAMES),
        "readiness": readiness["summary"],
        "technical_verdict": gate["technical_verdict"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
