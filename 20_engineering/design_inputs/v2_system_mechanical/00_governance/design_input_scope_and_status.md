# B2.5 Design Input Scope and Status

> `STATUS: BASELINED_PRE_CAD_INPUT_PACKAGE`  
> `SCIENTIFIC_GATE: false`  
> `CAD_EXECUTION: false`

## 授权范围

本阶段只允许：

- 建立系统需求、构型、接口、舱段、质量 owner、未知量和 CAD 输入合同；
- 建立本地 CAD pattern library 和只读结构审查 Agent；
- 复用现有 SSOT、A3/A4 证据和已核实来源；
- 形成 B3 人工审批所需的输入包和审查报告。

禁止：

- 创建或修改 `Space_Embodied_Robot_CAD_V2_0/`；
- 修改 V1.0/A3、accepted B601 URDF、几何 SSOT、Gate、仿真或证据；
- 运行 SolidWorks 建模、FEA、动力学、Isaac/ROS、控制、SAFE、RL、VLA 或硬件；
- 猜测材料、板厚、螺栓、预紧、载荷、刚度、强度、模态、真实质量或热参数；
- 把目标、physical TCP、contact 或传感器硬件纳入 active assembly。

## 上游真值

| 输入 | 当前有效状态 |
|---|---|
| A4-B2 architecture contract | `A4_B2_V2_MECHANICAL_ARCHITECTURE_CONTRACT_COMPLETE` |
| V1.0 evidence seal | SHA-256 `dce2b66a...a8969f0` |
| profile | `COMPETITION_DISPLAY_V0 / NON_FLIGHT_DISPLAY_ONLY` |
| body envelope | `340.5 × 226.3 × 226.3 mm` |
| robot mount transform | `T_SM / nominal_frozen_v1` |
| B601 | accepted `10-link / 9-joint` identity |
| `T_SB` | `UNKNOWN_DISABLED`，含义为 `S → B` |
| physical TCP | `UNKNOWN_DISABLED` |
| q0 deployed interference | `10 / NEGATIVE_RESULT / COLLISION_SAFETY_BLOCKED` |

## 证据状态

所有输入必须属于以下之一：

- `EVIDENCE_BOUND`
- `DESIGN_PROPOSAL`
- `UNKNOWN_BLOCKED`
- `EXCLUDED`

`DEFAULT`、`ASSUMED_TRUE`、`TYPICAL` 或视觉上合理不能替代上述状态。

## 变更控制

以下任一变化必须停止并请求新裁决：

- profile 或总体包络变化；
- `T_SM`、`M/A0` 或 B601 拓扑变化；
- V1.0 证据 seal 不一致；
- 未知材料、载荷或物性被要求填写；
- target、contact、sensor hardware 或 physical TCP 被要求进入 active CAD；
- B3 人工授权缺失。

## 退出条件

B2.5 只有在需求、ICD、volume owner、mass owner、unknown register、Master Skeleton 参数、B3 计划、结构审查和冻结边界核验均存在时，才能裁决：

`B2_5_SYSTEM_MECHANICAL_DESIGN_INPUT_PACKAGE_COMPLETE`

该裁决只允许申请 B3，不授予 B3。
