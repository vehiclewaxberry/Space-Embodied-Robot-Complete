# V2.0 顶层建模与验收矩阵

> `STATUS: FUTURE_B3_ACCEPTANCE_CONTRACT`  
> 本表定义未来 CAD 阶段的检查，不代表任何条目现在已经通过。

## A. B3 入口前置条件

| ID | 条件 | 当前 |
|---|---|---|
| B3-ENTRY-01 | 新的人工授权明确允许创建独立 V2.0 CAD | `NOT_AUTHORIZED` |
| B3-ENTRY-02 | V1.0 seal hash 复核一致 | `RECHECK_AT_ENTRY` |
| B3-ENTRY-03 | 任务书、装配树、KB 和 Agent 合同可解析 | `READY` |
| B3-ENTRY-04 | 继续采用 `COMPETITION_DISPLAY_V0` 与 `T_SM`，或有正式变更裁决 | `FROZEN_UNTIL_CHANGE_CONTROL` |
| B3-ENTRY-05 | 所有未知量保持 null/blocked，不以默认值填补 | `REQUIRED` |

## B. 未来 V2-CAD 验收

| ID | 验收内容 | 必需证据 |
|---|---|---|
| V2-CAD-01 | 在独立 `Space_Embodied_Robot_CAD_V2_0/` 创建，不覆盖 V1.0 | 路径、V1 hash、V2 manifest |
| V2-CAD-02 | Master Skeleton 是总体尺寸和基准的唯一驱动者 | feature/external-reference inventory |
| V2-CAD-03 | `S/M/A0/G/E_virtual` 与 `T_SM` 一致 | frame export + numeric comparison |
| V2-CAD-04 | 未把 `T_SB` 当作 mount transform | property scan + report |
| V2-CAD-05 | 主结构、次结构、设备占位和 reference 分离 | structure-class inventory |
| V2-CAD-06 | front/mid/rear 舱段具有独立 owner、边界和接口 | assembly tree + bay register |
| V2-CAD-07 | robot mount 反力链从 B601 base 闭合到 bus primary structure | load-path view + interface inventory |
| V2-CAD-08 | mount 未声称材料、刚度、强度或模态通过 | property/claim audit |
| V2-CAD-09 | OBC/EPS/PMAD/battery/RW/IMU 为独立 volume owner | equipment-volume register |
| V2-CAD-10 | 后服务模块分离 propulsion/comm/thermal/service 区域 | service-zone register |
| V2-CAD-11 | 外板拆卸、设备托盘抽取、工具访问和线束走廊可审查 | serviceability views/matrix |
| V2-CAD-12 | B601 10-link/9-joint、源哈希和 q0 身份保持 | URDF/STL/CAD comparison |
| V2-CAD-13 | 太阳翼状态与接口分离，飞行收拢/部署不被宣称 | configuration/property audit |
| V2-CAD-14 | sensor、physical TCP、contact 和 target 仍按合同隔离 | zero-solid / excluded-component checks |
| V2-CAD-15 | V1 的 10 处静态干涉负结果未被隐藏或改写 | inherited-negative-result record |
| V2-CAD-16 | 每次干涉检查绑定具名配置和姿态，不外推 | scoped interference reports |
| V2-CAD-17 | 无默认材料、质量、CoM 或惯量污染 | mass/material authority audit |
| V2-CAD-18 | 外部参考无直接复制、改名或原创性误导 | provenance/license/deviation manifest |
| V2-CAD-19 | 原生文件可重开、重建且引用完整 | native inspection + hash manifest |
| V2-CAD-20 | 冻结 Gate、仿真、配置、URDF 和 V1.0 均未改 | boundary diff/hash audit |

## C. 必须提供的评审视图

1. 整星等轴测与一级模块着色；
2. 主结构单独视图；
3. 主/次结构状态图；
4. 前/中/后三舱剖切；
5. robot mount 局部剖切；
6. B601→mount→任务面框→纵梁反力链；
7. avionics/EPS/ADCS volume owner；
8. 后服务模块分区；
9. 外板拆卸与设备托盘抽取方向；
10. 线束/服务通道 reference；
11. 太阳翼/机械臂具名配置与 keepout；
12. `EVIDENCE_BOUND / DESIGN_PROPOSAL / UNKNOWN_BLOCKED / EXCLUDED` 总览；
13. V1→V2 对照；
14. 独立 target scene，并带 `NO_CONTACT / NO_AUTONOMOUS_CAPTURE CLAIM` 水印。

## D. 允许的退出裁决

| 裁决 | 条件 |
|---|---|
| `V2_SYSTEM_MECHANICAL_CAD_COMPLETE_WITH_PHYSICAL_LIMITATIONS` | V2-CAD-01..20 全部满足，且所有未知量仍被正确隔离 |
| `V2_SYSTEM_MECHANICAL_CAD_PARTIAL` | 原生模型可复验，但非安全/非证据污染项未闭合 |
| `V2_BLOCKED_BY_INTERFACE_OR_SOURCE` | frame、来源、接口或关键 owner 不闭合 |
| `V2_REJECTED_BY_EVIDENCE_POLLUTION` | V1、Gate、仿真、配置、URDF 或物性真值被污染 |

上述任何退出裁决均不自动授权 FEA、URDF round-trip、动力学、控制、Isaac/ROS、制造、A5 或硬件。
