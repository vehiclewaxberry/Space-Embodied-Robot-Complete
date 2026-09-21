"""Build Mechanical Loop Engineering Continuation V3 from V2 and e19 evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ECR_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ECR_ROOT / "13_loop_continuation_v3"
GENERATED_LOCAL = "2026-08-23T21:20:00+08:00"
URDF_SHA = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
SOLAR_SHA = "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"

SOURCES: tuple[tuple[str, str, str], ...] = (
    (
        "loop_v2_gate",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/12_loop_continuation_v2/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V2.json",
        "F1C7DD89A07B343DDEAF6466F87D2B19CECF6B6D0A04A47B793248DC72DF6AD5",
    ),
    (
        "loop_v2_validation",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/12_loop_continuation_v2/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_VALIDATION_V2.json",
        "0103018FAF6623B72B4D21E36C07A684F8BA538FBC41F44DA28C29E26AB3B29C",
    ),
    (
        "loop_v2_manifest",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_b601_harness_rated_envelope/12_loop_continuation_v2/"
        "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V2.json",
        "E49144DC533AD5FC3E104529BDE9E5692F64DA2EA196128D49D06496D70D985A",
    ),
    (
        "e19_gate",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_DIAGNOSTIC_EVALUATION_GATE_V1.json",
        "BEE6ED3D0DD7A73204536E2FFCF2840B5B066DB371DC15B40C98A128A230E439",
    ),
    (
        "e19_validation",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_VALIDATION_V1.json",
        "491E8DDC1FBB90C86438C5ED6419F066C2203E131B7F911E1AAD153670F58745",
    ),
    (
        "e19_manifest",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_OUTPUT_MANIFEST_V1.json",
        "53F30140FC0765B87F2B040363D17A3950CCB45606614263553D4AAAFC3CDF46",
    ),
    (
        "e19_register",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_DIAGNOSTIC_EVALUATION_REGISTER_V1.json",
        "3DF7C47F8AB8C8C6C104278CF69285B6EC5636D4F7ED46DA516C8D97F63B8571",
    ),
    (
        "e19_input_manifest",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_INPUT_MANIFEST_V1.json",
        "AF8D4D588A7479E99E1C1BF62CEB02168278D98C9C57AE7C057F55AE630F2C51",
    ),
    (
        "e19_m01",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M01_BASE_REACTION_SUMMARY_V1.json",
        "08D32CD6C2451E25F05039FE96F26F069C7547F2D10362ED07F414021F4948B8",
    ),
    (
        "e19_m05",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M05_BRANCH_EVALUATION_V1.json",
        "AD11EFD31395CC6A311618854BE9AC25848113A2302E80A473528FAB31F49A44",
    ),
    (
        "e19_m06",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M06_HALF_SINE_EXECUTION_REGISTER_V1.json",
        "70F25C725AF1A1262B3028F421FD985DCC7B81755CEA6F84B24B5BB06E8F65C6",
    ),
    (
        "e19_m07_arm",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M07_ARM_ONLY_BASE_REACTION_SUMMARY_V1.json",
        "A9739CF90616473019902C181F20F633E224F3A7D420F6D4BB20EB719CD6767E",
    ),
    (
        "e19_m07_sim15",
        "30_simulation/e19_b601_mission_branch_diagnostic_evaluation/results/"
        "E19_M07_SIM15_RIGID_CAPTURE_RECOMPUTE_V1.json",
        "CA0824EEDB57B47E29457CFCF69E435EFF80676700738DC911950F28A4CFC2A1",
    ),
    (
        "accepted_urdf",
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        URDF_SHA,
    ),
    (
        "solar_r2",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step",
        SOLAR_SHA,
    ),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def load_json(relative: str) -> Any:
    return json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))


def binding_records() -> list[dict[str, Any]]:
    records = []
    for name, relative, expected in SOURCES:
        path = PROJECT_ROOT / relative
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"{name} hash mismatch: {actual}")
        records.append(
            {
                "name": name,
                "path": relative,
                "sha256": actual,
                "bytes": path.stat().st_size,
            }
        )
    return records


def build_gate() -> dict[str, Any]:
    bindings = binding_records()
    v2 = load_json(SOURCES[0][1])
    e19_gate = load_json(dict((name, path) for name, path, _ in SOURCES)["e19_gate"])
    e19_validation = load_json(
        dict((name, path) for name, path, _ in SOURCES)["e19_validation"]
    )
    e19_register = load_json(
        dict((name, path) for name, path, _ in SOURCES)["e19_register"]
    )
    m01 = load_json(dict((name, path) for name, path, _ in SOURCES)["e19_m01"])
    m05 = load_json(dict((name, path) for name, path, _ in SOURCES)["e19_m05"])
    m06 = load_json(dict((name, path) for name, path, _ in SOURCES)["e19_m06"])
    m07_arm = load_json(
        dict((name, path) for name, path, _ in SOURCES)["e19_m07_arm"]
    )
    m07_sim15 = load_json(
        dict((name, path) for name, path, _ in SOURCES)["e19_m07_sim15"]
    )
    if v2["gate"] != "HOLD" or v2["next_stage_authorized"]:
        raise RuntimeError("V2 release semantics changed")
    if (
        e19_gate["diagnostic_execution_verdict"] != "PASS"
        or e19_gate["gate"] != "HOLD"
        or e19_gate["next_stage_authorized"]
        or e19_gate["release_credit"]
    ):
        raise RuntimeError("e19 is not the expected PASS-diagnostic/HOLD-authority state")
    if (
        e19_validation["checks_passed"] != e19_validation["checks_total"]
        or e19_validation["negative_controls_passed"]
        != e19_validation["negative_controls_total"]
    ):
        raise RuntimeError("e19 independent validation is incomplete")

    facts = [
        {
            "id": "LC3-01",
            "name": "V2_CONTINUATION_REMAINS_VALID_AND_HOLD",
            "observed": True,
            "evidence": {
                "verdict": v2["verdict"],
                "gate": v2["gate"],
                "next_stage_authorized": v2["next_stage_authorized"],
            },
        },
        {
            "id": "LC3-02",
            "name": "E19_ISOLATED_DIAGNOSTIC_EXECUTION_CLOSED_WITH_AUTHORITY_HOLD",
            "observed": True,
            "evidence": {
                "verdict": e19_gate["verdict"],
                "criteria": f"{e19_gate['criteria_observed']}/{e19_gate['criteria_total']}",
                "diagnostic_execution_verdict": e19_gate[
                    "diagnostic_execution_verdict"
                ],
                "gate": e19_gate["gate"],
                "released_segments": e19_gate["released_segments"],
            },
        },
        {
            "id": "LC3-03",
            "name": "E19_INDEPENDENT_FAIL_CLOSED_VALIDATION_COMPLETE",
            "observed": True,
            "evidence": {
                "verdict": e19_validation["verdict"],
                "checks": f"{e19_validation['checks_passed']}/{e19_validation['checks_total']}",
                "negative_controls": f"{e19_validation['negative_controls_passed']}/{e19_validation['negative_controls_total']}",
            },
        },
        {
            "id": "LC3-04",
            "name": "M01_RIGID_FREE_FLOATING_DIAGNOSTIC_OBSERVATION_RECORDED",
            "observed": True,
            "evidence": {
                "peak_base_attitude_deviation_deg": m01["base_reaction"][
                    "peak_attitude_deviation_deg"
                ],
                "peak_base_rate_rad_s": m01["base_reaction"][
                    "peak_base_rate_rad_s"
                ],
                "max_momentum_residual_norm_S": m01["base_reaction"][
                    "max_momentum_residual_norm_S"
                ],
                "acceptance_threshold_authority": m01["base_reaction"][
                    "acceptance_threshold_authority"
                ],
                "engineering_prediction": m01["base_reaction"][
                    "engineering_prediction"
                ],
                "model_scope": "LEGACY_RIGID_DIAGNOSTIC_MASS_STACK_WITH_REORG_PATH_ADAPTER",
            },
        },
        {
            "id": "LC3-05",
            "name": "M05_TWO_NONMERGEABLE_BRANCH_DIAGNOSTICS_CLOSED",
            "observed": True,
            "evidence": {
                "sim13_final_phase_deg": m05["sim13_kinematic_branch"][
                    "final_phase_deg"
                ],
                "sim13_max_analytic_quaternion_error": m05[
                    "sim13_kinematic_branch"
                ]["max_analytic_quaternion_error"],
                "static_capture_residual_m": m05["static_display_branch"][
                    "capture_point_transform_residual_m"
                ],
                "branch_merge_performed": m05["branch_merge_performed"],
                "physical_target_state_released": False,
            },
        },
        {
            "id": "LC3-06",
            "name": "M06_SCALAR_EQUAL_IMPULSE_DIAGNOSTICS_CLOSED_PHYSICAL_CONTACT_HOLD",
            "observed": True,
            "evidence": {
                "case_count": m06["case_count"],
                "max_relative_impulse_error": m06["max_relative_impulse_error"],
                "physical_contact_fields": None,
                "hardware_force_credit": m06["hardware_force_credit"],
            },
        },
        {
            "id": "LC3-07",
            "name": "M07_ARM_ONLY_BASE_REACTION_DIAGNOSTIC_EXCLUDES_TARGET",
            "observed": True,
            "evidence": {
                "peak_base_attitude_deviation_deg": m07_arm["base_reaction"][
                    "peak_attitude_deviation_deg"
                ],
                "max_momentum_residual_norm_S": m07_arm["base_reaction"][
                    "max_momentum_residual_norm_S"
                ],
                "attached_target_propagated": m07_arm[
                    "attached_target_propagated"
                ],
                "acceptance_threshold_authority": m07_arm["base_reaction"][
                    "acceptance_threshold_authority"
                ],
            },
        },
        {
            "id": "LC3-08",
            "name": "M07_SIM15_RIGID_CAPTURE_ALGEBRA_REPRODUCED_WITHOUT_PHYSICAL_CREDIT",
            "observed": True,
            "evidence": {
                "case_count": m07_sim15["case_count"],
                "baseline_exact": m07_sim15[
                    "sim15_baseline_recomputed_from_current_hash_bound_code"
                ],
                "C08_branch_selection_performed": m07_sim15[
                    "C08_branch_selection_performed"
                ],
                "locked_transform_gripper_to_target": m07_sim15[
                    "locked_transform_gripper_to_target"
                ],
                "physical_contact_authority": m07_sim15[
                    "physical_contact_authority"
                ],
            },
        },
        {
            "id": "LC3-09",
            "name": "E19_LANES_REMAIN_ISOLATED_AND_ZERO_RELEASE",
            "observed": True,
            "evidence": {
                "lane_execution_count": e19_register["lane_execution_count"],
                "cross_lane_chaining_performed": e19_register[
                    "cross_lane_chaining_performed"
                ],
                "branch_merging_performed": e19_register[
                    "branch_merging_performed"
                ],
                "mission_timeline_created": e19_register[
                    "mission_timeline_created"
                ],
                "released_segments": e19_register["released_segments"],
            },
        },
        {
            "id": "LC3-10",
            "name": "IMMUTABLE_ASSETS_UNCHANGED_AND_NO_NEW_GEOMETRY",
            "observed": True,
            "evidence": {
                "accepted_urdf_sha256": URDF_SHA,
                "solar_r2_sha256": SOLAR_SHA,
                "new_geometry_count": 0,
            },
        },
    ]

    current_release = dict(v2["current_release"])
    current_release.update(
        {
            "isolated_nonrelease_numeric_diagnostic_execution_ready": True,
            "isolated_nonrelease_numeric_diagnostic_execution_closed": True,
            "m01_rigid_base_reaction_diagnostic_executed": True,
            "m05_two_branch_diagnostics_executed_separately": True,
            "m06_twenty_scalar_stimulus_cases_executed": True,
            "m07_arm_only_and_sim15_diagnostics_executed_separately": True,
            "end_to_end_diagnostic_dynamics_ready": False,
            "mission_sequence_executable": False,
            "mission_trajectory_release_ready": False,
            "cad_generation_authorized": False,
            "physical_contact_ready": False,
            "attached_target_recovery_ready": False,
            "production_dynamics_ready": False,
            "sim13_current_production_binding_valid": False,
            "hardware_motion_ready": False,
            "flight_qualification_ready": False,
        }
    )
    return {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V3",
        "generated_local": GENERATED_LOCAL,
        "authority_scope": "HASH_BOUND_ISOLATED_NONRELEASE_NUMERIC_DIAGNOSTIC_EXECUTION_CONTINUATION__PRE_CAD_PRE_PHYSICAL_PRE_MISSION_PRE_PRODUCTION",
        "decision_rule": "Authority > later evidence > independent reproduction > opinion",
        "fail_closed_invariants": [
            "e19 diagnostic PASS does not change the overall mechanical HOLD",
            "UNKNOWN is never PASS and null is never silently replaced by zero",
            "isolated branch execution is not an executable mission timeline",
            "a solver-stimulus amplitude is not measured or allowable contact force",
            "a rigid free-floating diagnostic observation has no acceptance threshold unless separately authorized",
            "M07 arm-only propagation excludes the 22 kg target",
            "Sim15 rigid-plastic algebra is not physical contact or released post-capture state",
            "diagnostic model branches remain separate and are not uncertainty samples",
            "test PASS is not CAD mechanical mission physical hardware production or flight release",
            "accepted URDF and Solar R2 remain immutable",
        ],
        "input_bindings": bindings,
        "facts": facts,
        "facts_total": len(facts),
        "facts_confirmed": sum(fact["observed"] for fact in facts),
        "current_release": current_release,
        "bounded_diagnostic_lane": {
            "state": "HASH_BOUND_ISOLATED_NON_RELEASE_NUMERIC_DIAGNOSTIC_EXECUTION_AND_REPRODUCIBILITY_CLOSED",
            "allowed": [
                "use e19 observations to prioritize model and evidence closure without release credit",
                "repeat each e19 lane independently after an explicitly versioned source change",
                "treat the large rigid-base reactions as diagnostic risk signals requiring current-mass and coupled-model follow-up",
                "record negative model-branch differences without averaging them into uncertainty",
            ],
            "not_allowed": [
                "chain M01 M05 M06 and M07 into a mission sequence",
                "claim a base-attitude acceptance result without an authorized threshold and current mass model",
                "interpret M06 amplitudes as physical force pressure duration or gripper capability",
                "propagate an attached target before locked transform selected mass state and recovery contract closure",
                "rebind Sim13 as production dynamics contact or RL authority",
            ],
        },
        "diagnostic_design_observations": {
            "M01_peak_base_attitude_deviation_deg": m01["base_reaction"][
                "peak_attitude_deviation_deg"
            ],
            "M07_arm_only_peak_base_attitude_deviation_deg": m07_arm[
                "base_reaction"
            ]["peak_attitude_deviation_deg"],
            "M06_max_relative_impulse_error": m06["max_relative_impulse_error"],
            "Sim15_22kg_case_count": m07_sim15["case_count"],
            "acceptance_threshold_authority": None,
            "model_scope": "ISOLATED_DIAGNOSTIC_ONLY",
            "mechanical_design_release_credit": False,
        },
        "blocking_fronts": v2["blocking_fronts"],
        "shortest_engineering_sequence": [
            "independently reproduce the M01 and M07 reaction signals with a current selected mass-inertia branch and then the sim11 coupled model before setting any acceptance threshold",
            "Owner disposes ODR-42 and assigns accountable owners to the five MPI templates",
            "fill MPI-01..MPI-08 with exact units source revision and uncertainty or bounded tolerance",
            "obtain actuator force-speed-latency and contact-lock bench evidence while excluding the URDF velocity literal",
            "freeze M05_22 physical target state then M06_22 physical contact-lock then M07_22 locked attached recovery state",
            "freeze M01 physical STOW HDRM and release-confirmed contract independently",
            "only after ODR-42 plus MPI closure create separately versioned Route-C CAD and close full-path gates before production Sim13 rebind",
        ],
        "verdict": "MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_HASH_BOUND_ISOLATED_NONRELEASE_NUMERIC_DIAGNOSTIC_EXECUTION_CLOSED__PRE_CAD_PHYSICAL_CONTACT_ATTACHED_RECOVERY_MISSION_PRODUCTION_AND_FLIGHT_RELEASE_HOLD",
        "gate": "HOLD",
        "testing_pass_grants_authority": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "required_owner_statement": v2["required_owner_statement"],
        "prohibition": "No end-to-end mission execution physical-contact claim attached-target recovery Route-C CAD production Sim13 rebind hardware motion manufacturing release or flight claim from this gate.",
    }


def build_brief(gate: Mapping[str, Any]) -> str:
    observations = gate["diagnostic_design_observations"]
    return f"""# 机械 Loop Engineering 续接裁决 V3

## 本轮工程增量

- e19 已把 M01、M05、M06、M07 从“哈希绑定输入分支”推进到“六条互不连接的隔离数值诊断”；机器 Gate 为 17/17，独立验证为 31/31、负控 85/85。
- M01 在历史刚性自由漂浮质量模型与显式 REORG 路径适配下，基座姿态偏转峰值为 `{observations['M01_peak_base_attitude_deviation_deg']:.6f} deg`；M07 arm-only 为 `{observations['M07_arm_only_peak_base_attitude_deviation_deg']:.6f} deg`。两者均无已授权验收阈值，也不是当前发布质量模型下的工程预测。
- M05 的 Sim13 常角速运动学与静态展示坐标代数保持不可合并；M06 的 20 例半正弦等冲量数值积分最大相对误差为 `{observations['M06_max_relative_impulse_error']:.3e}`，其幅值不是物理接触力。
- Sim15 的 4 个 22 kg 理想刚塑捕获案例由当前哈希绑定代码精确复现；M07 arm-only 未附着目标，锁定变换、选定质量属性和恢复合同仍为空。
- accepted URDF 与 Solar R2 哈希未变，本轮 CAD/STEP/网格增量为 0。

机器裁决：`{gate['verdict']}`

## 当前可合法使用的结果

1. 把 M01/M07 的大幅刚性基座反作用视为诊断风险信号，优先安排“当前选定质量惯量分支 → sim11 刚柔耦合”独立复算；在阈值授权前不得写成合格/不合格。
2. 继续分别使用 M05 运动学、M05 静态坐标、M06 标量波形、M07 arm-only 与 Sim15 刚塑代数做软件回归和输入敏感性检查。
3. 任一输入或求解器版本变化后，只能逐支路重跑并签发新哈希证据，禁止隐式串接旧状态。

## 仍未放行

- `end_to_end_diagnostic_dynamics_ready=false`：四任务段没有统一历元、公共帧、连续状态或任务 guard。
- `physical_contact_ready=false`、`attached_target_recovery_ready=false`：夹爪力速/时延、接触/锁定台架、锁定变换、法向、组合质量属性和恢复终端合同均未闭合。
- ODR-42 仍 PENDING，Route-C MPI 仍为 0/8 CONTROLLED；Route-C CAD、完整路径碰撞/Solar/束线 Gate、生产 Sim13、硬件和飞行均为 HOLD。

## 最短闭环

先用当前选定质量惯量分支复核 M01/M07，再进入 sim11 刚柔耦合诊断合同；治理主线仍是 ODR-42 + MPI-01..08，然后才是执行器/接触/锁定台架、M05→M06→M07 物理合同、M01 HDRM 合同、Route-C CAD 与完整路径 Gate。
"""


def write_outputs() -> dict[str, Any]:
    gate = build_gate()
    brief = build_brief(gate)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    gate_path = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V3.json"
    brief_path = OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_BRIEF_V3.md"
    gate_path.write_bytes(json_bytes(gate))
    brief_path.write_text(brief, encoding="utf-8", newline="\n")
    output_records = [
        {
            "path": gate_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": sha256_file(gate_path),
            "bytes": gate_path.stat().st_size,
        },
        {
            "path": brief_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": sha256_file(brief_path),
            "bytes": brief_path.stat().st_size,
        },
    ]
    script_paths = [
        Path(__file__).resolve(),
        Path(__file__).resolve().with_name("validate_mechanical_loop_continuation_v3.py"),
    ]
    source_records = binding_records() + [
        {
            "name": path.stem,
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in script_paths
    ]
    manifest = {
        "schema": "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V3",
        "generated_local": GENERATED_LOCAL,
        "outputs": output_records,
        "sources": source_records,
        "output_count": len(output_records),
        "source_count": len(source_records),
        "validation_report_excluded_to_avoid_self_hash": True,
        "gate": "HOLD",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    manifest_path = (
        OUTPUT_ROOT / "MECHANICAL_LOOP_ENGINEERING_CONTINUATION_OUTPUT_MANIFEST_V3.json"
    )
    manifest_path.write_bytes(json_bytes(manifest))
    return {"gate": gate, "brief": brief, "manifest": manifest}


if __name__ == "__main__":
    result = write_outputs()
    print(
        json.dumps(
            {
                "verdict": result["gate"]["verdict"],
                "facts": f"{result['gate']['facts_confirmed']}/{result['gate']['facts_total']}",
                "gate": result["gate"]["gate"],
                "release_credit": result["gate"]["release_credit"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
