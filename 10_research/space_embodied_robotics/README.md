# Space Embodied Robotics Research Track

## 当前入口

| 阶段 | 目录 | 状态 |
|---|---|---|
| Prototype contract | `comp_prot_02/` | 合同与架构 |
| Digital body knowledge/model review | `comp_prot_03_a0_a1/` | 完成 |
| 12U+B601 candidate review | `comp_prot_03_a2_candidate_model_review/` | 完成 |
| Digital body method | `comp_prot_03_a3_g0_digital_body_method/` | 完成 |
| G0 evidence closure | `comp_prot_03_a3_g0_evidence_closure/` | `PASS_WITH_SCOPE_ISOLATION` |
| SolidWorks Geometry Only | `comp_prot_03_a3_geometry_only/` | `A3_GEOMETRY_ONLY_COMPLETE_WITH_EXPLICIT_LIMITATIONS` |
| Engineering Geometry Design Review | `comp_prot_03_a4_design_review/` | `A4_DESIGN_REVIEW_COMPLETE_READY_TO_REQUEST_ENGINEERING_VISUAL_CAD` |
| Engineering Visual CAD | `comp_prot_03_a4_b1_engineering_visual_cad/` | `A4_ENGINEERING_VISUAL_COMPLETE_WITH_PHYSICAL_LIMITATIONS` |
| V2.0 Mechanical Architecture + Agent KB | `comp_prot_03_a4_b2_v2_mechanical_architecture/` | `A4_B2_V2_MECHANICAL_ARCHITECTURE_CONTRACT_COMPLETE` |

## SolidWorks 数字机械主机

当前工程视觉主机：

- `../../20_engineering/cad/Space_Embodied_Robot_CAD_V1_0/README.md`
- `../../20_engineering/cad/Space_Embodied_Robot_CAD_V1_0/Assembly/Space_Embodied_Robot_V1_0.SLDASM`

A3 几何基线保留：

- `../../20_engineering/cad/Space_Embodied_Robot_CAD_V0_1/README.md`
- `../../20_engineering/cad/Space_Embodied_Robot_CAD_V0_1/Assembly/12U_Master_Skeleton.SLDASM`

## 当前边界

A4-B1 已经把 A3 方块骨架深化为结构化 12U、link 级 B601、安装适配器、柔性附件、任务语义参考和独立 target scene，并完成原生重开、清单、视图与哈希证据。

它仍然不是 VLA、自治捕获、动力学数字孪生、制造或飞行工程 CAD。`T_SB`、physical TCP、目标接触接口、真实传感器、聚合 CoM/惯量和全局碰撞安全仍未关闭；`DEPLOYED_REFERENCE_Q0` 的 10 处静态干涉作为负结果保留。

V2.0 的系统机械架构任务书、装配树、验收矩阵和本地
Spacecraft Mechanical Design Agent 已建立，但没有创建 V2.0 CAD。当前 profile
仍是 `NON_FLIGHT_DISPLAY_ONLY`；`T_SM` 是机械臂安装面变换，`T_SB` 仍属于未知的
自由漂浮动力学基座关系。

`V2_CAD_AUTHORING_NOT_AUTHORIZED`、`A5_NOT_AUTHORIZED`。创建
`Space_Embodied_Robot_CAD_V2_0/` 或进入 URDF round-trip、Isaac/ROS、动力学、
FEA、控制、SAFE、RL、VLA、制造或物理样机前，必须取得新的人工批准。
