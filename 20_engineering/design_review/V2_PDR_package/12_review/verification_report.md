# COMP-PROT-03-A4-B2.8 PDR Verification Report

> `VERIFICATION_ID: SV2-PDR-VERIFY-2026-07-24`  
> `OVERALL: PASS_PRELIMINARY_DESIGN_ONLY`  
> `CAD_AUTHORING_AUTHORIZED: false`

## Verdict

```text
COMP-PROT-03-A4-B2.8-PDR-COMPLETE
B3_CAD_READY_TO_REQUEST_HUMAN_APPROVAL
B3_CAD_AUTHORING_NOT_AUTHORIZED
V1_0_UNMODIFIED
```

## Machine verification

| Check | Result |
|---|---|
| PDR YAML parse | `14/14 PASS` |
| B2.5 requirement IDs | `27 unique / PDR disposition present` |
| mechanical interface IDs | `10/10 exact, ordered, unique` |
| subsystem volume IDs | `12/12 exact, ordered, unique` |
| selected source mass strings | `5/5 exact match to B2.5 CSV` |
| B601 URDF topology mapping | `10 links / 9 joints / link names exact` |
| B601 URDF SHA-256 | `1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164 MATCH` |
| PDR Markdown relative links | `30/30 RESOLVED` |
| prohibited completed-capability phrases | `0` |
| PDR deliverable extensions | `.md / .yaml / .csv only` |
| PDR packet SHA-256 manifest | `30/30 HASH_MATCH`; manifest excludes itself |
| B2.5 input packet | `27/27 HASH_MATCH` |
| A4-B2 architecture packet | `21/21 HASH_MATCH` |
| V1.0 native CAD manifest | `32/32 HASH_MATCH` |
| V1.0 evidence seal | `43/43 HASH_MATCH` |
| V1.0 evidence seal manifest SHA-256 | `dce2b66ac9f60a32329388c4579fec8d7174b7be3c1dfc60dccc716c7a8969f0 MATCH` |
| geometry SSOT tracked/staged diff | `0 / 0` |
| simulation tracked/staged diff | `0 / 0` |
| evidence tracked/staged diff | `0 / 0` |
| accepted B601 URDF tracked/staged diff | `0 / 0` |
| V1.0 CAD tracked/staged diff | `0 / 0` |
| V2 SolidWorks root | `NOT_CREATED` |
| FEA/dynamics/control/Isaac/ROS/VLA/RL/hardware | `NONE` |

仓库在本阶段开始前已有大量未提交和未跟踪资产。因此“0/0”只针对具名冻结边界，不把整个工作树描述为 clean。

## Loop Engineering verification

| Loop | Outcome |
|---|---|
| Constraint lock | profile/frame/unknown/negative result preserved |
| Topology synthesis | primary structure, robot reaction path, three-bay owner logic complete |
| Digital-thread review | CAD ID, frame, mass, URDF and simulation contracts consistent |
| Red-flag review | no invented physical values, binary CAD or completed-capability claims |

两项文档层 finding 已关闭：

1. B601 精确质量小数改为字符串保存，避免 YAML 浮点显示截断；
2. root/master 文件名恢复为 B2.5 预留名称，并作为 CAD 命名受控例外。

## Preserved blockers

17 项 B2.5 unknown/excluded 全部保持开放，包括：

- standard/deployer/rail/tab；
- `T_SB`；
- robot mount、launch 和 operational loads；
- material/section/joints；
- physical mass/CoM/inertia；
- solar stowed/hinge/release/loads；
- sensor/physical TCP/target；
- hardware envelopes、serviceability、harness/thermal/EMC；
- B3 human authorization。

十处 `DEPLOYED_REFERENCE_Q0` 静态干涉继续保持：

`NEGATIVE_RESULT / COLLISION_SAFETY_BLOCKED`

## Delivery inventory

本阶段新增 31 个文件：

- 1 个 `design_review` 导航；
- 28 个 PDR 设计、合同和评审文件；
- 1 个 verification report；
- 1 个 SHA-256 manifest。

没有创建原生 CAD、STEP、STL、URDF、图片、仿真结果或科学 Gate。

## Next gate

`COMP-PROT-03-A4-B3-V2-SYSTEM-MECHANICAL-CAD`

当前仅为：

`READY_TO_REQUEST_HUMAN_APPROVAL / NOT_GRANTED`
