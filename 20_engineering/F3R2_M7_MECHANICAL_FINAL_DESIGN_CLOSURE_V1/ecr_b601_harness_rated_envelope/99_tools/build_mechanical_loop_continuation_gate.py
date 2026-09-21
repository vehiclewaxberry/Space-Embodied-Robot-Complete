"""Bind Route-C product/RFI evidence and e17 seeds into a continuation gate.

This is a later evidence layer over the existing stage gate.  It records real
engineering progress while preserving every authority and physical-release
hold.  No geometry, hardware selection or mission trajectory is released.
"""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml


REPO = Path(__file__).resolve().parents[4]
BASE_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_b601_harness_rated_envelope"
)
OUT_REL = f"{BASE_REL}/11_loop_continuation"
PRODUCT_REL = f"{BASE_REL}/08_route_c/01_minimum_product_inputs"
E17_REL = "30_simulation/e17_b601_mission_trajectory_candidates/results"
GENERATED_LOCAL = "2026-08-23T16:05:00+08:00"

INPUTS = {
    "prior_loop_gate": f"{BASE_REL}/10_loop_integration/MECHANICAL_LOOP_ENGINEERING_STAGE_GATE_V1.json",
    "prior_loop_validation": f"{BASE_REL}/10_loop_integration/MECHANICAL_LOOP_ENGINEERING_VALIDATION_REPORT_V1.json",
    "product_input_gate": f"{PRODUCT_REL}/ROUTE_C_PRODUCT_INPUT_GATE_V1.json",
    "product_input_validation": f"{PRODUCT_REL}/ROUTE_C_PRODUCT_INPUT_VALIDATION_V1.json",
    "vendor_rfi_gate": f"{PRODUCT_REL}/ROUTE_C_VENDOR_RFI_DECISION_GATE_V1.json",
    "vendor_rfi_validation": f"{PRODUCT_REL}/ROUTE_C_VENDOR_RFI_VALIDATION_V1.json",
    "vendor_rfi_manifest": f"{PRODUCT_REL}/ROUTE_C_VENDOR_RFI_OUTPUT_MANIFEST_V1.json",
    "e17_gate": f"{E17_REL}/B601_MISSION_TRAJECTORY_CANDIDATE_GATE_V1.json",
    "e17_validation": f"{E17_REL}/E17_VALIDATION_V1.json",
    "e17_manifest": f"{E17_REL}/E17_OUTPUT_MANIFEST_V1.json",
    "sim13_binding_audit": (
        f"{BASE_REL}/09_downstream_rebind/"
        "SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json"
    ),
    "odr42_request": f"{BASE_REL}/08_route_c/ROUTE_C_OWNER_DECISION_REQUEST_ODR42_V1.yaml",
    "gripper_engineering_pack": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V1.yaml"
    ),
    "accepted_urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "solar_r2": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step"
    ),
}

EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
EXPECTED_SOLAR_SHA256 = (
    "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"
)
EXPECTED_PRIOR_VERDICT = (
    "MECHANICAL_LOOP_ENGINEERING_PRE_CAD_HOLD_WITH_ACTIONABLE_ROUTE_C_"
    "PACKAGE_AND_SIM13_FAIL_CLOSED_SUPERSESSION"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(relative_path: str) -> dict[str, Any]:
    return json.loads((REPO / relative_path).read_text(encoding="utf-8"))


def read_yaml(relative_path: str) -> dict[str, Any]:
    return yaml.safe_load((REPO / relative_path).read_text(encoding="utf-8"))


def write_json(relative_path: str, value: Any) -> None:
    path = REPO / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(relative_path: str, value: str) -> None:
    path = REPO / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")


def bind_inputs() -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for name, relative_path in INPUTS.items():
        path = REPO / relative_path
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"missing or empty input: {relative_path}")
        bindings.append(
            {
                "name": name,
                "path": relative_path,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return bindings


def find_criterion(gate: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    return next(item for item in gate["criteria"] if item["id"] == criterion_id)


def build_gate() -> dict[str, Any]:
    prior = read_json(INPUTS["prior_loop_gate"])
    prior_validation = read_json(INPUTS["prior_loop_validation"])
    product = read_json(INPUTS["product_input_gate"])
    product_validation = read_json(INPUTS["product_input_validation"])
    rfi = read_json(INPUTS["vendor_rfi_gate"])
    rfi_validation = read_json(INPUTS["vendor_rfi_validation"])
    e17 = read_json(INPUTS["e17_gate"])
    e17_validation = read_json(INPUTS["e17_validation"])
    e17_manifest = read_json(INPUTS["e17_manifest"])
    sim13 = read_json(INPUTS["sim13_binding_audit"])
    odr42 = read_yaml(INPUTS["odr42_request"])
    gripper = read_yaml(INPUTS["gripper_engineering_pack"])
    urdf_root = ET.parse(REPO / INPUTS["accepted_urdf"]).getroot()
    urdf_gripper_velocities_m_s = [
        float(joint.find("limit").attrib["velocity"])
        for joint in urdf_root.findall("joint")
        if joint.attrib.get("name") in {"gripper_joint1", "gripper_joint2"}
        and joint.attrib.get("type") == "prismatic"
        and joint.find("limit") is not None
    ]
    e17_counts = e17["counts"]

    facts = [
        {
            "id": "LC-01",
            "name": "PRIOR_LOOP_GATE_VALID_AND_HOLD",
            "observed": (
                prior["verdict"] == EXPECTED_PRIOR_VERDICT
                and prior["next_stage_authorized"] is False
                and prior_validation["verdict"] == "PASS"
                and prior_validation["checks_passed"] == prior_validation["checks_total"]
                and prior_validation["negative_controls_passed"]
                == prior_validation["negative_controls_total"]
            ),
            "evidence": {
                "verdict": prior["verdict"],
                "validation_checks": f'{prior_validation["checks_passed"]}/{prior_validation["checks_total"]}',
                "negative_controls": f'{prior_validation["negative_controls_passed"]}/{prior_validation["negative_controls_total"]}',
            },
        },
        {
            "id": "LC-02",
            "name": "PRODUCT_INPUT_LIBRARY_VALID_BUT_MPI_ZERO_OF_EIGHT",
            "observed": (
                product_validation["package_integrity_pass"] is True
                and product_validation["checks_passed"] == product_validation["checks_total"]
                and product_validation["negative_controls_passed"]
                == product_validation["negative_controls_total"]
                and product["criteria_controlled"] == 0
                and product["criteria_total"] == 8
                and product["rc_ceg_03"] == "HOLD"
            ),
            "evidence": {
                "validation": product_validation["verdict"],
                "checks": f'{product_validation["checks_passed"]}/{product_validation["checks_total"]}',
                "negative_controls": f'{product_validation["negative_controls_passed"]}/{product_validation["negative_controls_total"]}',
                "minimum_inputs": "0/8 CONTROLLED",
                "rc_ceg_03": product["rc_ceg_03"],
            },
        },
        {
            "id": "LC-03",
            "name": "SUPPLIER_RFI_SHORTLIST_VALID_WITH_ZERO_SELECTIONS",
            "observed": (
                rfi_validation["package_integrity_pass"] is True
                and rfi_validation["checks_passed"] == rfi_validation["checks_total"]
                and rfi_validation["negative_controls_passed"]
                == rfi_validation["negative_controls_total"]
                and rfi["candidate_routes"]["candidate_routes"] == 4
                and rfi["candidate_routes"]["selected_routes"] == 0
                and rfi["next_stage_authorized"] is False
            ),
            "evidence": {
                "verdict": rfi["verdict"],
                "checks": f'{rfi_validation["checks_passed"]}/{rfi_validation["checks_total"]}',
                "negative_controls": f'{rfi_validation["negative_controls_passed"]}/{rfi_validation["negative_controls_total"]}',
                "candidate_routes": rfi["candidate_routes"],
            },
        },
        {
            "id": "LC-04",
            "name": "E17_SEED_INTEGRITY_VALID_WITH_ZERO_MISSION_RELEASES",
            "observed": (
                e17_validation["package_integrity_pass"] is True
                and e17_validation["checks_passed"] == e17_validation["checks_total"]
                and e17_validation["negative_controls_passed"]
                == e17_validation["negative_controls_total"]
                and e17_counts["mission_segments_total"] == 8
                and e17_counts["numeric_arm_only_seed_segments"] == 5
                and e17_counts["symbolic_scaffold_segments"] == 1
                and e17_counts["blocked_uninstantiated_segments"] == 2
                and (
                    e17_counts["numeric_arm_only_seed_segments"]
                    + e17_counts["symbolic_scaffold_segments"]
                    + e17_counts["blocked_uninstantiated_segments"]
                    == e17_counts["mission_segments_total"]
                )
                and e17_counts["released_segments"] == 0
                and e17["released_for_mission_gate"] is False
            ),
            "evidence": {
                "validation": e17_validation["verdict"],
                "checks": f'{e17_validation["checks_passed"]}/{e17_validation["checks_total"]}',
                "negative_controls": f'{e17_validation["negative_controls_passed"]}/{e17_validation["negative_controls_total"]}',
                "counts": e17_counts,
            },
        },
        {
            "id": "LC-05",
            "name": "GRIPPER_UNIT_CONFLICT_REMAINS_FAIL_CLOSED",
            "observed": (
                find_criterion(e17, "E17-G10")["state"] == "HOLD_UNIT_CONFLICT"
                and find_criterion(e17, "E17-G10")["release_credit"] is False
                and urdf_gripper_velocities_m_s == [15.0, 15.0]
                and gripper["frozen_inputs"]["urdf_velocity_limit_mm_s"] == 15.0
                and gripper["frozen_inputs"]["urdf_limit_role"]
                == "MODEL_LIMIT_NOT_DESIGN_OR_QUALIFICATION_LOAD"
            ),
            "evidence": {
                "urdf_prismatic_velocity_values_m_s": urdf_gripper_velocities_m_s,
                "engineering_pack_velocity_value_mm_s": gripper["frozen_inputs"]["urdf_velocity_limit_mm_s"],
                "engineering_pack_value_role": gripper["frozen_inputs"]["urdf_limit_role"],
                "state": find_criterion(e17, "E17-G10")["state"],
                "physical_gripper_timing_authorized": False,
            },
        },
        {
            "id": "LC-06",
            "name": "ODR42_REMAINS_PENDING",
            "observed": (
                rfi["odr42"] == "PENDING"
                and odr42["record_type"] == "APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD"
                and odr42["owner_decision"] == "PENDING"
                and odr42["next_stage_authorized"] is False
            ),
            "evidence": {
                "record_type": odr42["record_type"],
                "owner_decision": odr42["owner_decision"],
                "next_stage_authorized": odr42["next_stage_authorized"],
                "request_path": INPUTS["odr42_request"],
            },
        },
        {
            "id": "LC-07",
            "name": "NO_GEOMETRY_CREATED_BY_CONTINUATION_WORK",
            "observed": (
                e17_manifest["geometry_artifact_count"] == 0
                and all(
                    not item["path"].lower().endswith((".step", ".stp", ".iges", ".igs", ".stl", ".obj"))
                    for item in read_json(INPUTS["vendor_rfi_manifest"])["outputs"]
                )
            ),
            "evidence": {
                "e17_geometry_artifact_count": e17_manifest["geometry_artifact_count"],
                "route_c_rfi_geometry_artifact_count": 0,
            },
        },
        {
            "id": "LC-08",
            "name": "IMMUTABLE_MECHANICAL_ASSETS_UNCHANGED",
            "observed": (
                sha256_file(REPO / INPUTS["accepted_urdf"]) == EXPECTED_URDF_SHA256
                and sha256_file(REPO / INPUTS["solar_r2"]) == EXPECTED_SOLAR_SHA256
            ),
            "evidence": {
                "accepted_urdf_sha256": sha256_file(REPO / INPUTS["accepted_urdf"]),
                "solar_r2_sha256": sha256_file(REPO / INPUTS["solar_r2"]),
            },
        },
        {
            "id": "LC-09",
            "name": "SIM13_CURRENT_PRODUCTION_BINDING_REMAINS_INVALID",
            "observed": (
                sim13["verdict"]
                == "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE"
                and sim13["verdict_issued"] is True
                and sim13["current_authority"]["diagnostic_kinematic_bootstrap_only"] is True
                and sim13["current_authority"]["production_dynamics_ready"] is False
                and sim13["current_authority"]["physical_contact_ready"] is False
                and sim13["current_authority"]["physics_gated_rl_ready"] is False
                and sim13["next_stage_authorized"] is False
            ),
            "evidence": {
                "verdict": sim13["verdict"],
                "current_authority": sim13["current_authority"],
                "next_stage_authorized": sim13["next_stage_authorized"],
            },
        },
    ]
    confirmed = sum(bool(item["observed"]) for item in facts)
    all_confirmed = confirmed == len(facts)
    current_release = {
        "product_candidate_research_integrity": True,
        "supplier_rfi_package_ready": True,
        "arm_only_numeric_seed_integrity": True,
        "owner_detailed_design_authority": False,
        "route_c_product_selected": False,
        "route_c_cad_entry_ready": False,
        "mission_trajectories_released": 0,
        "mission_trajectories_total": 8,
        "full_path_collision_solar_safe": False,
        "physical_gripper_timing_ready": False,
        "mechanical_design_released": False,
        "production_dynamics_ready": False,
        "physical_contact_rl_ready": False,
        "hardware_motion_ready": False,
        "flight_qualification_ready": False,
    }
    return {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": "LATEST_BOUND_E17_VALIDATION_TIMESTAMP",
        "authority_scope": "PRE_CAD_ENGINEERING_CONTINUATION__NO_NEW_OWNER_OR_RELEASE_AUTHORITY",
        "decision_rule": "Authority > later evidence > independent reproduction > opinion",
        "fail_closed_invariants": [
            "UNKNOWN is never PASS",
            "catalog/RFI integrity is not product selection",
            "numeric seed integrity is not mission trajectory release",
            "test PASS is not a science, CAD, hardware or qualification release",
            "ODR-42 must be an independent Owner record and cannot be inferred from user intent",
            "accepted URDF frame and SI joint semantics remain immutable",
        ],
        "input_bindings": bind_inputs(),
        "facts": facts,
        "facts_total": len(facts),
        "facts_confirmed": confirmed,
        "current_release": current_release,
        "engineering_progress": {
            "route_c_product_input_pack": "VALIDATED_51_OF_51_WITH_4_OF_4_NEGATIVE_CONTROLS",
            "route_c_vendor_rfi_pack": "VALIDATED_53_OF_53_WITH_15_OF_15_NEGATIVE_CONTROLS",
            "e17_trajectory_candidate_pack": "VALIDATED_42_OF_42_WITH_10_OF_10_NEGATIVE_CONTROLS",
            "candidate_route_shape": "4 RFI routes; 3 flight-enquiry routes + 1 engineering-model-only route; 0 selected",
            "trajectory_shape": "5 numeric arm-only + 1 symbolic + 2 blocked uninstantiated; 0/8 released",
        },
        "blocking_fronts": [
            {
                "id": "BF-01",
                "front": "OWNER_AUTHORITY",
                "state": "HOLD_ODR42_PENDING",
                "exit": "independent ODR-42 disposition referencing the current request hash",
            },
            {
                "id": "BF-02",
                "front": "PRODUCT_AND_INTERFACE_INPUTS",
                "state": "HOLD_MPI_0_OF_8_CONTROLLED",
                "exit": "configuration-control MPI-01..MPI-08 with named owners and exact units/revisions",
            },
            {
                "id": "BF-03",
                "front": "MISSION_TRAJECTORIES",
                "state": "HOLD_RELEASE_0_OF_8",
                "exit": "resolve M01 authority, 22kg target state/contact, collision/Solar/harness/SAFE predicates and gripper units",
            },
            {
                "id": "BF-04",
                "front": "DOWNSTREAM_BINDING",
                "state": "HOLD_CURRENT_SIM13_PRODUCTION_BINDING_INVALID",
                "exit": "rebind only after a released Route-C mechanical package and all downstream gates exist",
            },
        ],
        "immediately_executable_without_new_design_authority": [
            "issue non-binding RFIs using RFI-01..RFI-09",
            "collect PRJ-01 B601 load map, PRJ-02 protocol/EMC definition and PRJ-03 circuit/pin map",
            "control HN-00..HN-03 and J1..J6 installation datums without creating Route-C geometry",
            "resolve the gripper velocity-unit authority conflict",
            "acquire M01 release-sweep and 22kg target-state/contact inputs",
            "independently reproduce the five non-release arm-only numeric seeds",
        ],
        "one_pass_sequence_after_both_entry_fronts_close": [
            "C2 create separately versioned STEP-first Route-C parametric guide/carrier design",
            "C3 instantiate and independently release all eight continuous mission trajectory segments",
            "C4 evaluate exact coupled mission-first clearance/bend/pinch/length/Solar/SAFE predicate",
            "C5 recompute Route-C and nine-configuration mass/CG/inertia plus restoring-load uncertainty budgets",
            "C6 close abrasion, TVAC, flex-life and post-install electrical verification evidence",
            "C7 issue new hash-bound interface, runtime harness and mechanical handoff gates with negative controls",
            "enter production dynamics/contact/RL only after their independent release gates pass",
        ],
        "verdict": (
            "MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_VERIFIED_RFI_AND_TRAJECTORY_SEEDS__"
            "PRE_CAD_AND_MISSION_RELEASE_HOLD"
            if all_confirmed
            else "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_INPUT_INTEGRITY_HOLD"
        ),
        "gate": "HOLD",
        "next_stage_authorized": False,
        "required_owner_statement": (
            "批准 ODR-42：APPROVE_BOUNDED_DETAILED_DESIGN；冻结 accepted URDF 与 Solar R2；"
            "完成最低产品/接口输入后生成 Route-C CAD。"
        ),
        "prohibition": (
            "No Route-C CAD/STEP, product selection, mission release, production dynamics, physical-contact RL, "
            "hardware motion, manufacturing release or flight claim from this continuation gate."
        ),
    }


def build_brief(gate: dict[str, Any]) -> str:
    return f"""
# 机械 Loop Engineering 续接裁决 V1

## 当前结论

- 机械研究已经推进到“可发出供应商 RFI + 可复算非发布轨迹种子”的阶段。
- Route-C 产品/接口最低输入仍为 **0/8 CONTROLLED**，RC-CEG-03 保持 **HOLD**。
- e17 已形成 **5 条数值臂轨迹种子 + 1 条符号骨架 + 2 条阻断未实例化段**，任务发布仍为 **0/8**。
- ODR-42 仍为 **PENDING**；accepted URDF 与 Solar R2 哈希保持不变；本续接包生成几何数量为 **0**。

机器裁决：`{gate['verdict']}`

## 现在可直接执行

1. 用 `ROUTE_C_VENDOR_RFI_REQUIREMENTS_V1.yaml` 向候选供应商索取精确料号、总成图、成品外径/公差、动态弯扭寿命、质量、恢复力矩、电气降额、环境及交付证据。
2. 由 B601 电气/航电负责人填写 PRJ-01..PRJ-03：负载表、协议/EMC、回路—针脚—导体表。
3. 由机械接口负责人冻结 HN-00..HN-03、J1..J6 的坐标、姿态、基准、公差和安装可达性。
4. 由夹爪负责人裁决 `15 m/s` 与 `15 mm/s` 的单位冲突；未裁决前禁止推导物理闭合时间。
5. 补 M01 释放扫掠权威和 22 kg 目标相对状态/接触边界，再把 e17 从数值种子升级为非发布任务轨迹候选。

## 进入 Route-C CAD 的双入口

- 入口 A：独立签发 ODR-42 `APPROVE_BOUNDED_DETAILED_DESIGN`。
- 入口 B：MPI-01..MPI-08 全部由具名 Owner 配置受控；目录典型值、TBD、null 或 Route-B 种子不得代替。

只有 A 与 B 同时闭合，才允许创建单独版本的 Route-C 参数化 CAD/STEP；随后仍需逐级完成八段轨迹、耦合 SAFE、质量/质心/惯量、恢复力矩、环境与寿命验证，不能直接宣称机械发布或飞行资格。
"""


def main() -> None:
    gate_rel = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V1.json"
    brief_rel = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V1.md"
    manifest_rel = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V1.json"
    gate = build_gate()
    write_json(gate_rel, gate)
    write_text(brief_rel, build_brief(gate))

    outputs = [gate_rel, brief_rel]
    sources = [
        f"{BASE_REL}/99_tools/build_mechanical_loop_continuation_gate.py",
        f"{BASE_REL}/99_tools/validate_mechanical_loop_continuation_gate.py",
    ]
    manifest = {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V1",
        "generated_local": GENERATED_LOCAL,
        "hash_algorithm": "SHA-256",
        "outputs": [
            {
                "path": path,
                "sha256": sha256_file(REPO / path),
                "bytes": (REPO / path).stat().st_size,
            }
            for path in outputs
        ],
        "sources": [
            {
                "path": path,
                "sha256": sha256_file(REPO / path),
                "bytes": (REPO / path).stat().st_size,
            }
            for path in sources
        ],
        "output_count": len(outputs),
        "source_count": len(sources),
        "validation_report_excluded_to_avoid_recursive_hash": True,
    }
    write_json(manifest_rel, manifest)
    print(
        json.dumps(
            {
                "verdict": gate["verdict"],
                "facts": f'{gate["facts_confirmed"]}/{gate["facts_total"]}',
                "gate_sha256": sha256_file(REPO / gate_rel),
                "manifest_sha256": sha256_file(REPO / manifest_rel),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
