# 12U 服务航天器 V2 系统需求冻结表

> `STATUS: SYSTEM_REQUIREMENTS_BASELINED_FOR_PRE_CAD`  
> `PROFILE: COMPETITION_DISPLAY_V0`  
> 本表描述目标任务和机械设计需求，不声明能力已经实现。

## 任务与系统需求

| ID | 需求 | 当前输入 | evidence state | CAD 含义 |
|---|---|---|---|---|
| V2-REQ-MIS-001 | 支持非合作目标在轨服务研究叙事 | target satellite / debris 两类场景 | `EVIDENCE_BOUND` | 只建立任务面和 keepout，不把 target 放入 active assembly |
| V2-REQ-MIS-002 | 目标场景覆盖 22 kg 目标星与 150 kg 碎片 | 质量预算 v1 的低置信度场景对象 | `EVIDENCE_BOUND` | 仅作任务场景标签，不作为结构载荷输入 |
| V2-REQ-MIS-003 | 以 B601 机械臂辅助捕获/操作为任务构型 | accepted B601 10-link/9-joint | `EVIDENCE_BOUND` | 保持拓扑和 `M/A0` 接口，不改 URDF |
| V2-REQ-MIS-004 | 支持自由漂浮服务研究概念 | `B/T_SB` 尚未闭合 | `UNKNOWN_BLOCKED` | CAD 不建立动力学基座或自由漂浮性能结论 |
| V2-REQ-MIS-005 | 为高层具身/VLA 任务规划保留接口 | planning reserve only | `DESIGN_PROPOSAL` | 只保留任务语义，不建立控制、传感或执行能力 |
| V2-REQ-SYS-001 | 使用当前比赛显示 profile | `340.5×226.3×226.3 mm` | `EVIDENCE_BOUND` | `NON_FLIGHT_DISPLAY_ONLY`，不称标准 12U 合规 |
| V2-REQ-SYS-002 | 保持前任务/中平台/后服务三舱 | 3 × 113.5 mm 名义分段 | `EVIDENCE_BOUND` | 由 Master Skeleton 的分舱面驱动 |
| V2-REQ-SYS-003 | 保持机械臂安装面 `M` | `T_SM` nominal_frozen_v1 | `EVIDENCE_BOUND` | mount、adapter、B601 均引用同一 transform |
| V2-REQ-SYS-004 | target 与 active servicer assembly 隔离 | A4-B1 既有规则 | `EVIDENCE_BOUND` | 独立场景；无 mate/contact/rigid lock |

## 机械架构需求

| ID | 需求 | 验收方式 | evidence state |
|---|---|---|---|
| V2-REQ-MEC-001 | 主结构、次结构、设备占位和 reference 必须分离 | structure-class inventory | `DESIGN_PROPOSAL` |
| V2-REQ-MEC-002 | 主结构形成前框—纵向构件—框环/甲板—后框的概念闭合 | load-path review view | `DESIGN_PROPOSAL` |
| V2-REQ-MEC-003 | B601 反力路径必须从 `A0/M` 进入 adapter、任务面框和 bus 主结构 | robot mount load-path view | `DESIGN_PROPOSAL` |
| V2-REQ-MEC-004 | front mission module 提供 mount、sensor reserve、任务接口和维护方向 | module/interface inventory | `DESIGN_PROPOSAL` |
| V2-REQ-MEC-005 | middle bay 提供 OBC/EPS/PMAD/battery/RW/IMU volume owner | volume-owner register | `DESIGN_PROPOSAL` |
| V2-REQ-MEC-006 | rear service module 分离 propulsion/comm/thermal/debug reserved zones | service-zone register | `DESIGN_PROPOSAL` |
| V2-REQ-MEC-007 | 外板、托盘、工具和线束具备维护方向 | serviceability matrix | `DESIGN_PROPOSAL` |
| V2-REQ-MEC-008 | 太阳翼区分 root/interface、展开参考和收拢提案 | configuration register | `DESIGN_PROPOSAL` |
| V2-REQ-MEC-009 | sensor、physical TCP、contact、真实工具保持禁用 | zero-solid/exclusion check | `UNKNOWN_BLOCKED` |
| V2-REQ-MEC-010 | q0 展开参考的 10 处静态干涉负结果必须继承 | negative-result record | `EVIDENCE_BOUND` |

## CAD 与证据需求

| ID | 需求 | 验收方式 |
|---|---|---|
| V2-REQ-CAD-001 | 采用 top-down Master Skeleton | external-reference inventory |
| V2-REQ-CAD-002 | 总体参数只由 skeleton 发布 | parameter ownership audit |
| V2-REQ-CAD-003 | 子装配不得循环引用或活动引用外部 OreSat/vendor CAD | dependency scan |
| V2-REQ-CAD-004 | 一级对象具有 object/owner/class/state/source/frame/mass/claim 属性 | property inventory |
| V2-REQ-CAD-005 | 配置、干涉和评审结果必须绑定具名状态 | configuration-scoped report |
| V2-REQ-CAD-006 | V1.0、Gate、geometry config、URDF 和 simulation 保持未修改 | hash/diff audit |
| V2-REQ-CAD-007 | V2 原生文件可重开、重建且引用完整 | native inspection |
| V2-REQ-CAD-008 | 所有输入和交付建立 SHA-256 manifest | packet/evidence seal |

## 明确不属于本需求基线

- 飞行、发射服务商或 CDS 12U 合规；
- 结构强度、刚度、模态、屈曲、热或环境资格；
- 可制造工程图、材料和紧固件选择；
- 工作空间、全局碰撞或捕获可行性；
- 自主感知、VLA、控制、SAFE、RL 或数字孪生完成状态。
