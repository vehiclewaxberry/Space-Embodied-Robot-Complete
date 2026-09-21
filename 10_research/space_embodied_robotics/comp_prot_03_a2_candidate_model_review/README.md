# COMP-PROT-03-A2 候选数字机体设计入口

*Candidate 12U + B601 mechanical configuration and Digital Skeleton Model, 2026-07-23*

---

> `PHASE: COMP-PROT-03-A2-CANDIDATE-MODEL-REVIEW`<br>
> `STATUS: CANDIDATE_MODEL_DESIGN_ONLY`<br>
> `DOCUMENT_VERDICT: DOCUMENT_COMPLETE_WITH_RECORDED_DOWNSTREAM_BLOCKS`<br>
> `CAD_ENTRY_VERDICT: CAD_ENTRY_BLOCKED_BY_EVIDENCE`<br>
> `CAD_GENERATION_AUTHORIZED: false`<br>
> `URDF_GENERATION_AUTHORIZED: false`<br>
> `SIMULATION_AUTHORIZED: false`<br>
> `SCIENTIFIC_GATE: false`<br>
> `NEXT_GATE: CAD-SKELETON-G0 / separate human authorization required`

## 📋 阶段结论

本目录已把现有 12U、B601、安装适配器、柔性帆板和目标组件整理成一份**候选构型合同**与一份**数字骨架图**。它解决的是“哪些对象属于同一候选、怎样连接、哪些质量不得重复计数、哪些 frame 必须存在、CAD 能消费什么”的设计问题，不是完成 CAD、URDF、动力学模型或空间级验证。

主候选为 `A_CENTERLINE_TASK_FACE_SINGLE_ARM`：沿现有 `+X_S` 任务端面中心线布置单套 B601。选择理由仅是它复用当前 12U/B601 身份、`T_SM` 锚点和单臂主线，减少平行模型；**不表示该构型的力矩、扰动、可达性或任务性能已经优于其他构型**。`B_SIDE_MOUNT_SINGLE_ARM` 只作差异审查，`C_DUAL_ARM` 本阶段排除。

15 项 DB blocker 已逐项分流为“设计关闭、证据关闭、范围隔离、仍阻塞”四类。当前仍有必须补证或签核的 CAD 输入项，因此本阶段裁决为 `CAD_ENTRY_BLOCKED_BY_EVIDENCE`；不会自动进入 A3，也不会在本轮生成 CAD。

## 📦 交付物

| 文件 | 用途 | 权威边界 |
|---|---|---|
| [机械构型设计标准](./mechanical_configuration_design_standard.md) | 冻结拓扑、构型、质量、frame、接口与 CAD 消费规则 | 设计合同，不是工程验证 |
| [12U Appendix B 目视复核记录](./cds_appendix_b_12u_review_record.md) | 记录 CDS Rev.14.1 第 34 页 12U 图纸的人工复核证据 | 只关闭 12U 候选输入，不证明现有 CAD 合规 |
| [候选构型清单](./candidate_configuration_v0.yaml) | 记录 A/B/C、主候选选择、来源和禁止继承项 | 不是运行配置 |
| [数字骨架模型](./digital_skeleton_model_v0.yaml) | 记录 node、edge、transform、质量所有权和消费者边界 | 逻辑骨架，不是 CAD/URDF |
| [DB blocker 处置账本](./db_blocker_resolution_ledger.yaml) | 逐项给出 A2 处置、证据状态、CAD 影响和责任人 | 不用“计划”冒充关闭 |
| [多智能体构型评审](./configuration_review.yaml) | 汇总 Geometry、Dynamics/Robotics、Mission/Red-Team 与 Chair 裁决 | 不以多数票创造真值 |
| [CAD 入口闸门](./cad_entry_gate.md) | 定义 A3 前必须满足的证据和 A3 退出项 | 当前为 HOLD，不是授权 |
| [验证报告](./verification_report.md) | 汇总最终哈希、结构校验、多智能体回归和冻结边界 | raw-byte 快照，不替代 Git commit |

## 🔐 当前允许与禁止

允许表述：

> 已完成 12U+B601 候选机械构型标准和 Digital Skeleton Model；所有 15 项 DB blocker 已纳入证据化处置，当前 CAD 入口仍因证据项未闭合而保持 HOLD。

禁止表述：

- “12U+B601 数字机体已经集成或验证”；
- “构型 A 已证明最优、反作用更小或可完成捕获”；
- “现有 340.5 mm 12U CAD 已符合 CDS Appendix B”；
- “B601 地面模型已经证明自由漂浮在轨性能”；
- “E16、sim05 或旧 Gate 已自动继承到本候选”；
- “已实现 CAD、URDF、Basilisk、ROS、Isaac、控制器、RL、VLA 或自主捕获”。

## 🚫 本轮未发生的动作

- 未创建、修改或导出 CAD、STEP、STL、URDF、USD；
- 未修改 `20_engineering/config/geometry/`、`30_simulation/`、`40_evidence/` 或任何 Gate JSON；
- 未运行科学仿真、控制、训练或新模型求解；
- 未把外部 B601 STEP 或许可证文件复制进交付包；
- 未把候选设计升级为科学结论或工程验收。
