# COMP-PROT-03-A4-B2 核验报告

_核验日期：2026-07-24；本报告是机械架构/知识库验收，不是科学 Gate。_

## 裁决

`A4_B2_V2_MECHANICAL_ARCHITECTURE_CONTRACT_COMPLETE`

同时保持：

- `V2_CAD_AUTHORING_NOT_AUTHORIZED`
- `V1_0_UNMODIFIED`
- `A5_NOT_AUTHORIZED`
- `NO_SIMULATION / NO_FEA / NO_URDF_CHANGE / NO_HARDWARE_ACTION`

## 交付物

### V2.0 架构包

1. `README.md`
2. `12U_autonomous_servicing_spacecraft_v2_mechanical_architecture_taskbook.md`
3. `v1_to_v2_correction_matrix.md`
4. `v2_assembly_tree.yaml`
5. `v2_review_and_acceptance_matrix.md`
6. `v2_entry_gate.yaml`
7. `verification_report.md`
8. `v2_packet_hash_manifest.csv`

### 本地知识库

1. `README.md`
2. `knowledge_contract.yaml`
3. `source_registry.yaml`
4. `01_CubeSat_standard/cubesat_structure_and_integration_rules.md`
5. `02_servicing_cases/case_transfer_cards.md`
6. `03_space_structure/structural_and_bay_patterns.md`
7. `04_robot_interface/robot_mount_load_path_rules.md`
8. `05_cad_rules/top_down_solidworks_rules.md`
9. `06_agent_protocol/learning_and_review_workflow.md`
10. `06_agent_protocol/blocked_unknowns.yaml`

### Agent 与导航

- `.codex/agents/spacecraft-mechanical-design-agent.md`
- 更新 `10_research/space_embodied_robotics/README.md`
- 更新 `10_research/knowledge_base/README.md`
- 更新 `CLAUDE.md` 的机械设计入口

## 来源核验

| 来源 | 结果 |
|---|---|
| CubeSat Design Specification Rev.14.1 本地 PDF | `HASH_MATCH` |
| NASA CubeSat 101 本地 PDF | `HASH_MATCH` |
| NASA Small Spacecraft SOA 2026 本地 PDF | `HASH_MATCH` |
| A4-B1 evidence seal | SHA-256 与封存值一致 |
| OreSat Structure 本地固定仓 | HEAD `4c02299f908e`；上游 README 明确 old SolidWorks repository deprecated |
| NASA OSAM-1 当前页面 | `CANCELLED / ORDERLY_SHUTDOWN`；仅作历史案例 |
| JAXA ETS-VII 页面 | 历史 rendezvous-docking / space robotics 案例 |
| DLR DEOS 页面 | 历史 completed-project / servicing phase 案例 |

## 机器核验

| 检查 | 结果 |
|---|---|
| 新增 YAML 语法解析 | `5/5 PASS` |
| 新增/更新导航的相对 Markdown 链接 | `PASS` |
| source registry 本地路径 | `6/6 EXISTS` |
| source registry 具名文件哈希 | `4/4 HASH_MATCH` |
| OreSat 固定 HEAD | `4c02299f908e MATCH` |
| V1.0 原生 CAD manifest | `32/32 HASH_MATCH` |
| V1.0 evidence seal manifest SHA-256 | `DCE2...9F0 MATCH` |
| `20_engineering/config/geometry/` tracked/staged diff | `0 / 0` |
| `30_simulation/` tracked/staged diff | `0 / 0` |
| `40_evidence/` tracked/staged diff | `0 / 0` |
| accepted B601 URDF tracked/staged diff | `0 / 0` |
| V2.0 CAD 根目录 | `NOT_CREATED` |
| 仿真、FEA、控制、训练或硬件动作 | `NONE` |

工作树在本阶段开始前已经包含大量未提交资产；本报告的“0”只指具名冻结边界的 tracked/staged diff，不把整个仓库描述为 clean。

## 关键纠正闭环

1. 机械臂 mount transform 统一为 `T_SM`；旧的 robot-base `T_SB` 语义被拒绝。
2. `T_SB` 保留为 `S → B` 自由漂浮动力学基座未知量。
3. OSAM-1 被正确标记为已取消历史任务。
4. OreSat 被降为 fixed legacy layout reference，不作为现行设计真值。
5. 项目显示 profile 与 NASA SOA 12U 尺寸冲突已登记为 blocker，不宣称标准/发射合规。
6. A4-B1 的 10 处静态干涉负结果继续保持 `COLLISION_SAFETY_BLOCKED`。

## 未闭合边界

机械知识库保留 12 项具名 unknown/excluded 项，核心包括：

- 标准尺寸与当前显示 profile 冲突；
- Appendix B 人工图纸复核和 rail/tab 选择；
- `T_SB`、整星 mass/CoM/inertia；
- robot mount 载荷、材料、连接、强度/刚度/模态；
- 太阳翼收拢/锁定/释放；
- camera/`T_SC`、physical TCP/`T_E_TCP`；
- target 接口与 `T_ST/T_SD`。

这些项目没有被默认值或常识补齐。

## 下一 Gate

`COMP-PROT-03-A4-B3-V2-SYSTEM-MECHANICAL-CAD`

当前仅为：

`READY_TO_REQUEST_HUMAN_APPROVAL`

该 Gate 获批前，不创建 `20_engineering/cad/Space_Embodied_Robot_CAD_V2_0/`。
