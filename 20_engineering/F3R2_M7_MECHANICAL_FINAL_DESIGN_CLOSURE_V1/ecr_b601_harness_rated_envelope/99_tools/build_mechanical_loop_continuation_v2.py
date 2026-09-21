"""Build the second fail-closed mechanical loop continuation gate.

This layer binds the corrected gripper-unit semantics, the e18 non-release
mission-input branches and the Route-C minimum-product-input evidence audit.
It authorizes no CAD, mission execution, physical contact, production dynamics
or hardware motion.
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
OUT_REL = f"{BASE_REL}/12_loop_continuation_v2"
GRIPPER_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_gripper_velocity_unit_authority"
)
MPI_REL = f"{BASE_REL}/08_route_c/01_minimum_product_inputs/02_mpi_evidence_audit"
E18_REL = "30_simulation/e18_b601_mission_input_branches/results"
GENERATED_LOCAL = "2026-08-23T18:35:00+08:00"

EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
EXPECTED_SOLAR_SHA256 = (
    "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"
)

INPUTS = {
    "prior_continuation_gate": (
        f"{BASE_REL}/11_loop_continuation/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V1.json"
    ),
    "prior_continuation_validation": (
        f"{BASE_REL}/11_loop_continuation/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V1.json"
    ),
    "prior_continuation_manifest": (
        f"{BASE_REL}/11_loop_continuation/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V1.json"
    ),
    "gripper_gate": f"{GRIPPER_REL}/02_gate/GRIPPER_VELOCITY_UNIT_GATE_V1.json",
    "gripper_validation": (
        f"{GRIPPER_REL}/03_validation/GRIPPER_VELOCITY_UNIT_VALIDATION_V1.json"
    ),
    "gripper_manifest": (
        f"{GRIPPER_REL}/03_validation/GRIPPER_VELOCITY_UNIT_OUTPUT_MANIFEST_V1.json"
    ),
    "gripper_pointer": (
        f"{GRIPPER_REL}/01_interface/GRIPPER_ACTIVE_CONSUMPTION_POINTER_V1.yaml"
    ),
    "gripper_v2": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml"
    ),
    "mpi_gate": f"{MPI_REL}/ROUTE_C_MPI_EVIDENCE_GATE_V1.json",
    "mpi_validation": f"{MPI_REL}/ROUTE_C_MPI_EVIDENCE_AUDIT_VALIDATION_V1.json",
    "mpi_manifest": f"{MPI_REL}/ROUTE_C_MPI_EVIDENCE_AUDIT_OUTPUT_MANIFEST_V1.json",
    "e18_gate": f"{E18_REL}/E18_B601_MISSION_INPUT_BRANCH_GATE_V1.json",
    "e18_validation": f"{E18_REL}/E18_VALIDATION_V1.json",
    "e18_manifest": f"{E18_REL}/E18_OUTPUT_MANIFEST_V1.json",
    "e18_register": f"{E18_REL}/E18_B601_MISSION_INPUT_BRANCH_REGISTER_V1.json",
    "sim13_binding_audit": (
        f"{BASE_REL}/09_downstream_rebind/"
        "SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json"
    ),
    "odr42_request": f"{BASE_REL}/08_route_c/ROUTE_C_OWNER_DECISION_REQUEST_ODR42_V1.yaml",
    "accepted_urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "solar_r2": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step"
    ),
}


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


def segment(register: dict[str, Any], segment_id: str) -> dict[str, Any]:
    matches = [item for item in register["segments"] if item["segment_id"] == segment_id]
    if len(matches) != 1:
        raise ValueError(f"expected one e18 segment {segment_id}, got {len(matches)}")
    return matches[0]


def criterion(gate: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    matches = [item for item in gate["criteria"] if item["id"] == criterion_id]
    if len(matches) != 1:
        raise ValueError(f"expected one criterion {criterion_id}, got {len(matches)}")
    return matches[0]


def build_gate() -> dict[str, Any]:
    prior = read_json(INPUTS["prior_continuation_gate"])
    prior_validation = read_json(INPUTS["prior_continuation_validation"])
    gripper = read_json(INPUTS["gripper_gate"])
    gripper_validation = read_json(INPUTS["gripper_validation"])
    gripper_pointer = read_yaml(INPUTS["gripper_pointer"])
    gripper_v2 = read_yaml(INPUTS["gripper_v2"])
    mpi = read_json(INPUTS["mpi_gate"])
    mpi_validation = read_json(INPUTS["mpi_validation"])
    e18 = read_json(INPUTS["e18_gate"])
    e18_validation = read_json(INPUTS["e18_validation"])
    e18_register = read_json(INPUTS["e18_register"])
    sim13 = read_json(INPUTS["sim13_binding_audit"])
    odr42 = read_yaml(INPUTS["odr42_request"])

    urdf_path = REPO / INPUTS["accepted_urdf"]
    urdf_sha = sha256_file(urdf_path)
    solar_sha = sha256_file(REPO / INPUTS["solar_r2"])
    urdf_root = ET.parse(urdf_path).getroot()
    gripper_joint_facts = [
        {
            "name": joint.attrib["name"],
            "type": joint.attrib["type"],
            "velocity_literal_m_s": float(joint.find("limit").attrib["velocity"]),
        }
        for joint in urdf_root.findall("joint")
        if joint.attrib.get("name") in {"gripper_joint1", "gripper_joint2"}
        and joint.find("limit") is not None
    ]

    m01 = segment(e18_register, "M01")
    m05 = segment(e18_register, "M05_22")
    m06 = segment(e18_register, "M06_22")
    m07 = segment(e18_register, "M07_22")

    facts = [
        {
            "id": "LC2-01",
            "name": "PRIOR_CONTINUATION_REMAINS_VALID_AND_HOLD",
            "observed": (
                prior["gate"] == "HOLD"
                and prior["next_stage_authorized"] is False
                and prior_validation["package_integrity_pass"] is True
                and prior_validation["checks_passed"] == prior_validation["checks_total"]
                and prior_validation["negative_controls_passed"]
                == prior_validation["negative_controls_total"]
            ),
            "evidence": {
                "verdict": prior["verdict"],
                "checks": f'{prior_validation["checks_passed"]}/{prior_validation["checks_total"]}',
                "negative_controls": (
                    f'{prior_validation["negative_controls_passed"]}/'
                    f'{prior_validation["negative_controls_total"]}'
                ),
            },
        },
        {
            "id": "LC2-02",
            "name": "GRIPPER_UNIT_SEMANTICS_RECONCILED_WITH_PHYSICAL_SPEED_HOLD",
            "observed": (
                gripper["semantic_reconciliation"] == "PASS"
                and gripper["physical_actuator_speed_authority"] == "HOLD"
                and gripper["physical_gripper_timing_ready"] is False
                and gripper["next_stage_authorized"] is False
                and gripper_validation["package_integrity_pass"] is True
                and gripper_validation["checks_passed"] == gripper_validation["checks_total"]
                and gripper_validation["negative_controls_passed"]
                == gripper_validation["negative_controls_total"]
                and gripper_v2["schema"] == "GRIPPER_ENGINEERING_PACK_V2"
                and gripper_pointer["active_pack"]["sha256"]
                == sha256_file(REPO / INPUTS["gripper_v2"])
            ),
            "evidence": {
                "verdict": gripper["verdict"],
                "validation": gripper_validation["verdict"],
                "checks": f'{gripper_validation["checks_passed"]}/{gripper_validation["checks_total"]}',
                "negative_controls": (
                    f'{gripper_validation["negative_controls_passed"]}/'
                    f'{gripper_validation["negative_controls_total"]}'
                ),
                "active_pack": gripper["active_engineering_pack"],
                "physical_speed_m_s": gripper_v2["frozen_inputs"]["urdf_velocity_physical_capability_m_s"],
                "physical_speed_uncertainty_m_s": gripper_v2["frozen_inputs"]["urdf_velocity_physical_uncertainty_m_s"],
            },
        },
        {
            "id": "LC2-03",
            "name": "E18_NONRELEASE_BRANCH_PACKAGE_VALID_WITH_ZERO_RELEASES",
            "observed": (
                e18_validation["verdict"].startswith("PASS_NON_RELEASE_BRANCH_INTEGRITY")
                and e18_validation["checks_passed"] == e18_validation["checks_total"]
                and e18_validation["checks_total"] == 69
                and e18_validation["negative_controls_passed"]
                == e18_validation["negative_controls_total"]
                and e18_validation["negative_controls_total"] == 29
                and e18["numeric_branch_integrity_ready"] is True
                and e18["released_segments"] == 0
                and e18["mission_trajectory_release_ready"] is False
                and e18["production_dynamics_ready"] is False
                and e18["next_stage_authorized"] is False
                and e18_register["coverage"]["segments_with_hash_bound_nonrelease_branches"] == 4
                and e18_register["coverage"]["released_segments"] == 0
            ),
            "evidence": {
                "verdict": e18["verdict"],
                "validation": e18_validation["verdict"],
                "checks": f'{e18_validation["checks_passed"]}/{e18_validation["checks_total"]}',
                "negative_controls": (
                    f'{e18_validation["negative_controls_passed"]}/'
                    f'{e18_validation["negative_controls_total"]}'
                ),
                "coverage": e18_register["coverage"],
            },
        },
        {
            "id": "LC2-04",
            "name": "M01_QSPACE_CANDIDATE_READY_BUT_RELEASE_EVENT_UNBOUND",
            "observed": (
                m01["numeric_branch_count"] == 1
                and m01["released_for_mission_gate"] is False
                and criterion(e18, "E18-G03")["state"] == "PASS_NON_RELEASE_ONLY"
                and criterion(e18, "E18-G04")["state"] == "HOLD"
            ),
            "evidence": {
                "candidate": m01["candidate"],
                "duration_s": 11.5,
                "sample_period_s": 0.01,
                "samples": 1151,
                "release_confirmed_signal": "UNBOUND",
                "mission_sequence_executable": False,
            },
        },
        {
            "id": "LC2-05",
            "name": "M05_TWO_DIAGNOSTIC_TARGET_BRANCHES_REMAIN_NONMERGEABLE",
            "observed": (
                m05["numeric_branch_count"] == 2
                and m05["released_for_mission_gate"] is False
                and criterion(e18, "E18-G05")["state"] == "PASS_BRANCH_SEPARATION_ONLY"
                and criterion(e18, "E18-G06")["state"] == "HOLD"
            ),
            "evidence": {
                "candidate": m05["candidate"],
                "branch_count": 2,
                "branch_ids": [
                    "SIM13_KINEMATIC_BOOTSTRAP",
                    "SCENE_MANIFEST_STATIC_DISPLAY",
                ],
                "merge_allowed": False,
            },
        },
        {
            "id": "LC2-06",
            "name": "M06_SOLVER_STIMULUS_MATRIX_READY_WITH_PHYSICAL_FIELDS_NULL",
            "observed": (
                m06["numeric_branch_count"] == 20
                and m06["released_for_mission_gate"] is False
                and criterion(e18, "E18-G07")["state"] == "PASS_SOLVER_STIMULUS_ONLY"
                and criterion(e18, "E18-G08")["state"] == "HOLD"
                and e18["physical_contact_ready"] is False
            ),
            "evidence": {
                "candidate": m06["candidate"],
                "case_count": 20,
                "grid": "4 approach speeds x 5 solver contact windows",
                "peak_force_role": "SOLVER_STIMULUS_PROXY_NOT_HARDWARE_CONTACT",
                "physical_force_pressure_duration_normal_lock": None,
            },
        },
        {
            "id": "LC2-07",
            "name": "M07_DIAGNOSTIC_ATTACHED_BRANCHES_READY_WITH_LOCKED_TRANSFORM_HOLD",
            "observed": (
                m07["numeric_branch_count"] == 4
                and m07["released_for_mission_gate"] is False
                and criterion(e18, "E18-G10")["state"] == "PASS_NON_RELEASE_ONLY"
                and criterion(e18, "E18-G11")["state"] == "PASS_DIAGNOSTIC_ONLY"
                and criterion(e18, "E18-G12")["state"] == "HOLD"
            ),
            "evidence": {
                "candidate": m07["candidate"],
                "branch_count": 4,
                "arm_only_duration_s": 4.5,
                "arm_only_samples": 451,
                "selected_locked_transform": None,
                "released_mass_cg_inertia": None,
            },
        },
        {
            "id": "LC2-08",
            "name": "ROUTE_C_MPI_AUDIT_VALID_WITH_ZERO_OF_EIGHT_CONTROLLED",
            "observed": (
                mpi["gate"] == "HOLD"
                and mpi["criteria_total"] == 8
                and mpi["criteria_controlled"] == 0
                and mpi["criteria_hold"] == 8
                and mpi["mpi07_local_kinematics_available"] is True
                and mpi["mpi07_installation_icd_closed"] is False
                and mpi["cad_generation_authorized"] is False
                and mpi["cad_assets_created"] == 0
                and mpi_validation["all_pass"] is True
                and mpi_validation["checks_passed"] == mpi_validation["checks_total"]
                and mpi_validation["checks_total"] == 133
                and mpi_validation["negative_controls_passed"]
                == mpi_validation["negative_controls_total"]
                and mpi_validation["negative_controls_total"] == 21
            ),
            "evidence": {
                "verdict": mpi["verdict"],
                "checks": f'{mpi_validation["checks_passed"]}/{mpi_validation["checks_total"]}',
                "negative_controls": (
                    f'{mpi_validation["negative_controls_passed"]}/'
                    f'{mpi_validation["negative_controls_total"]}'
                ),
                "controlled": 0,
                "total": 8,
                "owner_templates": 5,
                "mpi07_scope": "LOCAL_J1_TO_J6_KINEMATICS_ONLY__INSTALLATION_ICD_OPEN",
            },
        },
        {
            "id": "LC2-09",
            "name": "ODR42_REMAINS_PENDING",
            "observed": (
                odr42["record_type"] == "APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD"
                and odr42["owner_decision"] == "PENDING"
                and odr42["next_stage_authorized"] is False
            ),
            "evidence": {
                "record_type": odr42["record_type"],
                "owner_decision": odr42["owner_decision"],
                "request_path": INPUTS["odr42_request"],
            },
        },
        {
            "id": "LC2-10",
            "name": "IMMUTABLE_ASSETS_UNCHANGED_AND_NO_NEW_GEOMETRY",
            "observed": (
                urdf_sha == EXPECTED_URDF_SHA256
                and solar_sha == EXPECTED_SOLAR_SHA256
                and gripper_joint_facts
                == [
                    {"name": "gripper_joint1", "type": "prismatic", "velocity_literal_m_s": 15.0},
                    {"name": "gripper_joint2", "type": "prismatic", "velocity_literal_m_s": 15.0},
                ]
                and e18_register["cad_or_geometry_created"] is False
                and mpi["cad_assets_created"] == 0
            ),
            "evidence": {
                "accepted_urdf_sha256": urdf_sha,
                "solar_r2_sha256": solar_sha,
                "urdf_gripper_joints": gripper_joint_facts,
                "new_geometry_count": 0,
            },
        },
        {
            "id": "LC2-11",
            "name": "SIM13_PRODUCTION_BINDING_REMAINS_INVALID",
            "observed": (
                sim13["verdict"]
                == "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE"
                and sim13["current_authority"]["diagnostic_kinematic_bootstrap_only"] is True
                and sim13["current_authority"]["production_dynamics_ready"] is False
                and sim13["current_authority"]["physical_contact_ready"] is False
                and sim13["current_authority"]["physics_gated_rl_ready"] is False
                and sim13["next_stage_authorized"] is False
            ),
            "evidence": {
                "verdict": sim13["verdict"],
                "current_authority": sim13["current_authority"],
            },
        },
    ]

    release = {
        "isolated_nonrelease_numeric_input_branches_ready": True,
        "hash_bound_nonrelease_branching_ready": True,
        "offline_m01_qspace_candidate_integrity": True,
        "m05_diagnostic_branch_separation_ready": True,
        "m06_solver_stimulus_matrix_ready": True,
        "m07_diagnostic_attached_branch_binding_ready": True,
        "gripper_unit_semantics_reconciled": True,
        "end_to_end_diagnostic_dynamics_ready": False,
        "mission_sequence_executable": False,
        "mission_trajectory_release_ready": False,
        "owner_detailed_design_authority": False,
        "route_c_mpi_controlled": 0,
        "route_c_mpi_total": 8,
        "route_c_product_selected": False,
        "cad_generation_authorized": False,
        "route_c_cad_entry_ready": False,
        "mission_trajectories_released": 0,
        "mission_trajectories_total": 8,
        "physical_gripper_speed_ready": False,
        "physical_contact_ready": False,
        "physical_contact_model_ready": False,
        "released_combined_mass_properties_ready": False,
        "full_path_collision_solar_harness_safe": False,
        "mechanical_design_released": False,
        "production_dynamics_ready": False,
        "sim13_current_production_binding_valid": False,
        "physical_contact_rl_ready": False,
        "hardware_motion_ready": False,
        "flight_qualification_ready": False,
    }

    return {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V2",
        "generated_local": GENERATED_LOCAL,
        "authority_scope": "HASH_BOUND_NONRELEASE_INPUT_CONTINUATION__PRE_CAD_PRE_PHYSICAL_PRE_PRODUCTION",
        "decision_rule": "Authority > later evidence > independent reproduction > opinion",
        "fail_closed_invariants": [
            "UNKNOWN is never PASS and null is never silently replaced by zero",
            "semantic unit reconciliation is not physical actuator characterization",
            "solver stimulus amplitude is not measured or allowable contact force",
            "a q-space seed with an unbound release guard is not an executable mission sequence",
            "diagnostic model branches remain separate and are never averaged into uncertainty",
            "MPI template availability is not MPI control or product selection",
            "test PASS is not CAD, mission, physical, hardware, production or flight release",
            "ODR-42 cannot be inferred from user intent or a request record",
            "accepted URDF and Solar R2 remain immutable",
        ],
        "input_bindings": bind_inputs(),
        "facts": facts,
        "facts_total": len(facts),
        "facts_confirmed": sum(item["observed"] is True for item in facts),
        "current_release": release,
        "bounded_diagnostic_lane": {
            "state": "HASH_BOUND_ISOLATED_NON_RELEASE_NUMERIC_INPUT_BRANCH_INTEGRITY_READY",
            "allowed": [
                "reproduce and perturb the M01 arm-only q-space candidate while keeping the release guard unbound",
                "run separate M05 Sim13-bootstrap and display-placement branch studies without merging them",
                "use the 20 M06 half-sine cases only as solver-stimulus inputs",
                "evaluate the M07 arm-only and explicitly named diagnostic mass/full-state branches",
                "record numerical residuals, sensitivity and negative results without release credit",
            ],
            "not_allowed": [
                "execute or claim the M01 physical release sequence",
                "treat any M05 branch as the released mission target state",
                "interpret M06 peak amplitudes as physical force or pressure",
                "select a locked target transform or released combined mass properties",
                "rebind Sim13 as production dynamics/contact/RL authority",
            ],
        },
        "blocking_fronts": [
            {
                "id": "BF2-01",
                "front": "OWNER_AUTHORITY",
                "state": "HOLD_ODR42_PENDING",
                "exit": "independent ODR-42 disposition referencing the current request hash",
            },
            {
                "id": "BF2-02",
                "front": "ROUTE_C_PRODUCT_AND_INTERFACE_INPUTS",
                "state": "HOLD_MPI_0_OF_8_CONTROLLED",
                "exit": "Owner completes and configuration-controls the five templates covering MPI-01..MPI-08",
            },
            {
                "id": "BF2-03",
                "front": "PHYSICAL_GRIPPER_AND_CONTACT",
                "state": "HOLD_NO_ACTUATOR_OR_CONTACT_CHARACTERIZATION",
                "exit": "controlled vendor data plus instrumented force-speed-latency/contact/lock tests with uncertainty",
            },
            {
                "id": "BF2-04",
                "front": "MISSION_AND_ATTACHED_STATE_AUTHORITY",
                "state": "HOLD_RELEASE_0_OF_8",
                "exit": "bind HDRM event, target SE3/twist, contact/lock, locked transform, combined state and terminal tolerances",
            },
            {
                "id": "BF2-05",
                "front": "COUPLED_PATH_AND_DOWNSTREAM_BINDING",
                "state": "HOLD_ROUTE_C_CAD_AND_FULL_PATH_GATES_ABSENT",
                "exit": "after CAD entry, close collision/Solar/harness/SAFE/mass/load gates and issue a new production binding",
            },
        ],
        "shortest_engineering_sequence": [
            "Owner disposes ODR-42 and assigns accountable owners to the five MPI templates",
            "fill MPI-01..MPI-08 with exact units, source/revision and uncertainty or bounded tolerance",
            "obtain actuator force-speed-latency and contact/lock bench evidence; keep URDF literal excluded",
            "freeze M05_22 target state, then M06_22 physical contact/lock, then M07_22 attached recovery state",
            "freeze M01 physical STOW/HDRM/release-confirmed contract independently",
            "only after ODR-42 plus MPI closure create separately versioned Route-C CAD/STEP",
            "close full-path coupled gates before any production Sim13 rebind",
        ],
        "verdict": (
            "MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_GRIPPER_SEMANTICS_AND_"
            "HASH_BOUND_NONRELEASE_INPUT_BRANCHES__PRE_CAD_PHYSICAL_CONTACT_"
            "MISSION_AND_PRODUCTION_RELEASE_HOLD"
        ),
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
        "required_owner_statement": (
            "批准 ODR-42：APPROVE_BOUNDED_DETAILED_DESIGN；冻结 accepted URDF 与 Solar R2；"
            "完成 MPI-01..MPI-08 后方可生成独立版本 Route-C CAD。"
        ),
        "prohibition": (
            "No Route-C CAD/STEP, product selection, executable mission sequence, physical-contact claim, "
            "production Sim13 rebind, hardware motion, manufacturing release or flight claim from this gate."
        ),
    }


def build_brief(gate: dict[str, Any]) -> str:
    return f"""# 机械 Loop Engineering 续接裁决 V2

## 当前工程结果

- 夹爪 URDF 速度字段的语义已纠正：棱柱关节字面值按 SI 为 `15 m/s`，只保留为未验证自动导出模型限制；物理速度、闭合时间及不确定度仍为 `null/HOLD`。
- e18 已形成四段哈希绑定的非发布输入：M01 纯关节五次候选、M05 两个不可合并的目标状态分支、M06 的 20 例求解器激励矩阵、M07 的臂轨迹/诊断质量/完整状态分支。
- Route-C MPI 证据审计完成，五份 Owner 模板可直接填写；实际受控输入仍为 `0/8`，MPI-07 只承认 J1..J6 局部运动学，不代表安装 ICD。
- accepted URDF 与 Solar R2 哈希未变，本轮新增 CAD/STEP/网格数量为 0。
- 当前仅是孤立、哈希绑定的非发布数值输入分支就绪；端到端诊断动力学仍为 `false`。

机器裁决：`{gate['verdict']}`

## 可以立即做的离线诊断

1. 复算并扰动 M01 的 11.5 s、0.01 s 关节空间候选；`release_confirmed` 未绑定，所以不得执行或声称 HDRM 释放序列。
2. 分别计算 M05 的 Sim13 bootstrap 与静态展示分支，禁止合并、平均或伪装成任务不确定度。
3. 把 M06 的 4×5 半正弦等冲量矩阵作为求解器刺激输入；峰值不是实测/允许接触力。
4. 对 M07 已命名的臂轨迹、两种诊断质量分支和 Sim15 完整状态分支做敏感性分析；锁定变换和发布质量属性仍为空。

## 尚未放行

- ODR-42 仍为 `PENDING`；MPI-01..MPI-08 为 `0/8 CONTROLLED`。
- 任务序列可执行性、八段轨迹发布、物理夹爪速度、接触/锁定模型、全路径碰撞/Solar/束线 SAFE 均未闭合。
- Route-C CAD 入口、机械设计发布、生产动力学、物理接触 RL、Sim13 生产重绑定、硬件运动和飞行资格均为 `false/HOLD`。

## 最短闭环顺序

先独立处置 ODR-42，并由具名 Owner 填写五份 MPI 模板；随后取得夹爪力速/延迟与接触/锁定台架数据。任务合同按 `M05_22 → M06_22 → M07_22` 闭合，M01 单独等待真实 STOW 与 HDRM 释放权威。只有 ODR-42 与 8/8 MPI 同时闭合，才进入独立版本 Route-C CAD；生产 Sim13 必须等完整路径 Gate 后重绑。
"""


def file_record(relative_path: str) -> dict[str, Any]:
    path = REPO / relative_path
    return {
        "path": relative_path,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def main() -> None:
    gate = build_gate()
    if gate["facts_confirmed"] != gate["facts_total"]:
        failed = [item["id"] for item in gate["facts"] if not item["observed"]]
        raise RuntimeError(f"cannot issue gate with unconfirmed facts: {failed}")

    gate_rel = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V2.json"
    brief_rel = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V2.md"
    manifest_rel = f"{OUT_REL}/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V2.json"
    write_json(gate_rel, gate)
    write_text(brief_rel, build_brief(gate))

    source_paths = [
        INPUTS["gripper_manifest"],
        INPUTS["mpi_manifest"],
        INPUTS["e18_manifest"],
        f"{BASE_REL}/99_tools/build_mechanical_loop_continuation_v2.py",
        f"{BASE_REL}/99_tools/validate_mechanical_loop_continuation_v2.py",
    ]
    manifest = {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V2",
        "generated_local": GENERATED_LOCAL,
        "outputs": [file_record(gate_rel), file_record(brief_rel)],
        "sources": [file_record(path) for path in source_paths],
        "output_count": 2,
        "source_count": len(source_paths),
        "validation_report_excluded_to_avoid_self_hash": True,
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_json(manifest_rel, manifest)

    print(
        json.dumps(
            {
                "verdict": gate["verdict"],
                "facts": f'{gate["facts_confirmed"]}/{gate["facts_total"]}',
                "input_bindings": len(gate["input_bindings"]),
                "gate_sha256": sha256_file(REPO / gate_rel),
                "manifest_sha256": sha256_file(REPO / manifest_rel),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
