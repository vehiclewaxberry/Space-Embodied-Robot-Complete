# COMP-PROT-03-A3 Geometry Only 执行计划

_12U+B601 参数化 SolidWorks 数字机械主机，2026-07-23_

---

> `STATUS: COMPLETE`  
> `MODEL_SCOPE: GEOMETRY_ONLY`  
> `SCIENTIFIC_GATE: false`  
> `NO_DYNAMICS_USE: true`  
> `TARGET_EXCLUDED: true`

## 🎯 科学与工程问题

本阶段只回答一个工程问题：现有 Digital Mechanical Host 合同能否落成一套可在 SolidWorks 2024 中打开、编辑、追溯的几何数字样机，同时保持所有动力学、目标接触和物理 TCP 未知量为关闭状态。

本阶段不检验任务可行性，不产生新的动力学、控制、结构强度、发射合规或空间验证结论。

## 📋 人工批准与输入

用户已在本轮明确批准 `COMP-PROT-03-A3-GEOMETRY-ONLY-ENTRY`，允许：

- 创建 SolidWorks Master Skeleton
- 创建 `COMPETITION_DISPLAY_V0` 的 12U 显示包络
- 创建 B601 嵌入式安装适配器的几何原型
- 创建机械装配层级
- 映射自定义属性和证据来源

主要输入为：

- `../comp_prot_03_a3_g0_evidence_closure/solidworks_skeleton_input_v0_1.yaml`
- `../comp_prot_03_a3_g0_evidence_closure/digital_mechanical_host_v0_1.yaml`
- `../comp_prot_03_a3_g0_evidence_closure/frame_tree_v2_candidate.yaml`
- `../../../20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`

## ⚙️ 实施方法

1. 在 `20_engineering/cad/Space_Embodied_Robot_CAD_V0_1/` 新建独立 CAD 包，不覆盖旧 CAD。
2. 使用 SolidWorks 2024 原生 API 创建参数化零件；主要尺寸以可编辑的命名尺寸和自定义属性保存。
3. 创建 `SER_Master_Skeleton.SLDPRT`，仅包含包络骨架、任务面、`S/M/A0` 基准和禁用分支说明。
4. 创建 `01_Service_Bus.SLDPRT`，使用 `340.5 × 226.3 × 226.3 mm` 的非飞行显示 profile。
5. 创建 `02_B601_Mount_Adapter.SLDPRT`；采用嵌入式 v0.1 堆叠，使 `M=A0` 保持在 `x_S=185.25 mm`，并把未签核紧固件与线缆通道保留为参考草图。
6. 创建 B601 `REFERENCE_ONLY` 简化装配，保持 accepted URDF 的 10-link/9-joint身份与来源，不导入或复制上游 STEP。
7. 创建 `12U_Master_Skeleton.SLDASM` 总装，固定于 `S` 几何 frame，仅用于几何审查。
8. 导出模型树、frame、包络和干涉审查证据；所有证据带 `GEOMETRY_ONLY` 水印语义。

## 🧪 验收标准

| ID | 验收项 | 通过条件 |
|---|---|---|
| `A3-GEO-01` | 原生文件 | 主要 `.SLDPRT/.SLDASM` 均由 SolidWorks 2024 打开并保存 |
| `A3-GEO-02` | 参数化 | 总体、主体和适配器存在可编辑命名尺寸 |
| `A3-GEO-03` | Profile | 包络精确为 `340.5 × 226.3 × 226.3 mm`，并标记 `NON_FLIGHT_DISPLAY_ONLY` |
| `A3-GEO-04` | Frame | `S/M/A0` 单值；`T_SB` 与 physical TCP 不建立 |
| `A3-GEO-05` | 适配器 | 160 mm 接口、160 × 160 × 12 mm 板和 Ø100 × 15 mm boss 分层可追溯 |
| `A3-GEO-06` | B601 | 10-link/9-joint身份存在，明确为简化参考表示 |
| `A3-GEO-07` | 目标隔离 | CAD 包不包含目标星、碎片或接触几何 |
| `A3-GEO-08` | 证据 | 文件哈希、模型树、frame 导出、截图和干涉裁决可读取 |
| `A3-GEO-09` | 冻结边界 | 不修改现有 Gate JSON、仿真结果或 `20_engineering/config/geometry/` |

## 🚫 禁止项

- 不生成 URDF、USD、ROS、Isaac、Basilisk 或控制代码
- 不运行任何科学仿真
- 不计算或发布整机 CoM、惯量或任务性能
- 不定义 `T_SB`、physical TCP、目标接触面或 6DOF lock
- 不把参考 B601 包络称为供应商精确 CAD
- 不声称 CDS/部署器合规、结构强度合格、无碰撞可抓取或已实现空间具身智能

## 🔄 回滚方案

所有新增资产位于两个独立新目录：

- `10_research/space_embodied_robotics/comp_prot_03_a3_geometry_only/`
- `20_engineering/cad/Space_Embodied_Robot_CAD_V0_1/`

若原生 CAD 创建、链接或验收失败，停止在当前文件，不改旧 CAD 和冻结 Gate；报告具体失败项，不把部分结果升级为完成。
