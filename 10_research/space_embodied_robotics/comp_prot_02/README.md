# COMP-PROT-02 空间机器人数字本体架构入口

*Space Embodied Robot Physical Platform — architecture-only navigation, 2026-07-23*

---

> `PHASE: COMP-PROT-02-ARCHITECTURE-DESIGN`<br>
> `PHASE_VERDICT: COMP_PROT_02_ARCHITECTURE_DESIGN_COMPLETE`<br>
> `STATUS: ARCHITECTURE_ONLY`<br>
> `SCIENTIFIC_GATE: false`<br>
> `EXECUTION_AUTHORITY: false`<br>
> `DOWNSTREAM_RESULT: COMP-PROT-03-A0/A1 / DIGITAL_MODEL_ARCHITECTURE_ONLY`<br>
> `NEXT_GATE: COMP-PROT-03-A2-CANDIDATE-MODEL-REVIEW / NOT_AUTHORIZED`

## 📋 本阶段裁决

本目录完成空间具身机器人实验平台的**数字本体、模型层级、参数所有权、CAD/URDF/动力学接口、开源资源采用边界与后续实施准入条件**。它是研究与工程之间的设计合同，不是新模型实现、仿真结果或系统能力证明。

当前唯一基线为既有 **12U 服务星 + B601 六转动关节机械臂 + 既有目标星/碎片模型**。附件中曾建议的“12–15 kg、7 自由度”不进入主线，因为它会与现有 24 kg 参考锚点、B601 6R 硬件映射和“不得重新设计卫星”的批准边界冲突。

本阶段未创建或修改 CAD、URDF、控制器、Physics Tool、SAFE、ROS 节点、Isaac Sim 工程、RL 环境、训练数据或科学仿真。

后续 A0/A1 文档子阶段已在 2026-07-23 获得范围受限人工批准并落盘，入口见 [数字机体知识库与多智能体评审框架](../comp_prot_03_a0_a1/README.md)。该结果没有授权候选模型构建、正式模型接受或任何工程实施。

## 📍 阅读顺序

| 顺序 | 文档 | 回答的问题 |
|---:|---|---|
| 1 | [空间机器人平台规格](./space_robot_platform_spec.md) | 平台是什么、数字本体如何分层、最优实验基线如何定义 |
| 2 | [模型参数规格](./model_parameter_specification.md) | 哪些数值是锚点、哪些只是暂定、怎样表达范围与不确定性 |
| 3 | [CAD/URDF/动力学接口设计](./cad_urdf_dynamics_interface_design.md) | 几何、坐标系、状态、时间和证据如何跨工具传递 |
| 4 | [开源资源调研](./open_source_resource_survey.md) | NASA/GitHub/仿真生态中哪些可采用、哪些仅供参考 |
| 5 | [COMP-PROT-03 实施要求](./comp_prot_03_implementation_requirements.md) | 下一阶段获批前必须满足什么、何时停止、如何验收 |

上游接口合同见 [Space Embodied Agent Prototype V1](../space_embodied_agent_v1_contract.md)。本目录只把该合同绑定到一个可追溯的物理平台架构，未实现合同中的任何运行时组件。

## 🎯 三项总裁决

1. **12U + 机械臂实验模型**：保留现有 12U/B601 6R 为共享基线；“最优”定义为在现有硬件、证据和比赛周期约束下最小化平行模型与参数漂移，不是全局尺寸或自由度最优。
2. **Basilisk + ROS 2 + Isaac Sim**：接受为分层候选架构，不接受一次性全栈实施。未来由 Basilisk 候选承担动力学状态，ROS 2 只传输消息/坐标变换，Isaac Sim 只承担可视化、感知与合成数据；每层必须可单独关闭。
3. **比赛 Demo 与 Paper 2**：共享同一对象身份、坐标系、参数来源和状态信封；比赛使用可解释的离线/受控展示证据，Paper 2 使用可复算的动力学与 Physics World Model 证据。展示画面不能反向成为科学真值。

## 🚫 冻结边界

- 不触碰 `30_simulation/`、`40_evidence/`、任何 Gate JSON 与冻结配置；
- 不触碰 `20_engineering/cad/spacecraft_layout/` 下既有 CAD、STEP、STL、URDF、网格或 JSON；
- 不下载外部模型到工程目录；
- 不把架构设计写成“已实现空间具身智能”“已完成自主捕获”“已完成 VLA”或“已完成安全控制”；
- 不以任何规划文档覆盖原始 Gate、哈希、实验记录或论文状态。

## 🔗 现行真值入口

- 几何与坐标系：[geometry SSOT](../../../20_engineering/config/geometry/)
- 参数登记：[parameter registry](../../../20_engineering/parameter_registry/README.md)
- 现有 CAD/URDF 清单：[spacecraft layout](../../../20_engineering/cad/spacecraft_layout/)
- 数字孪生边界：[digital twin plan](../../00_project_architecture/digital_twin_plan.md)
- 外部资产许可闸门：[license gate](../../../20_engineering/stage1_spacecraft_layout/02_open_bus_reference/license_gate_v0.md)
- 科学状态与证据：以各模块原始 Gate JSON 为准，本目录不复制其裁决。
