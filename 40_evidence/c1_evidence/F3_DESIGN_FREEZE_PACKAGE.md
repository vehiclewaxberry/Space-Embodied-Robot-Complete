# F3 设计冻结包 — B601 制造级结构架构冻结（F3-P0）

- 任务：`FREECAD-F3-P0-MECHANICAL-ARCHITECTURE-DESIGN-FREEZE`
- 日期：2026-08-04
- 前置：F0–F2 PASS（骨架/载体/运动装配/基座适配器试点）
- 性质：**架构冻结文档，不建模**。冻结后 F3-P1/P2/P3 方可启动。

## 1. 冻结的制造级结构树（见 `B601_STRUCTURE_TREE.yaml`）

八模块：S00 vendor 核心（BUY）·S01 基座适配器（F2 PASS）·S02 收拢约束·S03 HDRM·S04 末端执行器·S05 线束·S06 连杆覆盖（可选）·S07 载荷扩散。

**关键分类**：vendor 电机/减速器/轴承/编码器内部 = BUY（不重新设计，与迁移指令§三一致）；自研 = 壳体/接口/鞍座/HDRM/EE/线束路由/扩散框。

## 2. BOM 规划（见 `F3_BOM_PLAN.csv`）

27 行，覆盖 S01–S07 + vendor 核心；置信度分级（base adapter HIGH、stowage/HDRM/EE LOW）。

## 3. 参数表增量（见 `F3_PARAMETER_REGISTER_DELTA.csv`）

21 项候选参数（关节 PCD/bolt/dowel、连杆壳体、线束弯半径、G07/G08/HDRM/EE 几何与刚度），全部 `PROPOSED_FREEZE_CANDIDATE`，依赖 D1/vendor/载荷工况。

## 4. 关节接口控制文件（见 `JOINT_INTERFACE_CONTROL_DOCUMENTS.yaml`）

J01–J06 全部从 accepted URDF 提取 axis/origin/limits/effort；PCD/bolt_count 标 TBD 待 D1+vendor 图纸；每个关节含输出承载链与线束旋转包络判据。

## 5. 载荷路径（见 `LOAD_PATH_ANALYSIS.md`）

三路径 mermaid：发射收拢（G07/G08→扩散框→适配器→纵梁）、展开捕获（EE→链→关节→适配器）、HDRM 释放。F4 准入 8 项判据冻结。

## 6. 同步动力学种子（见 `FREECAD_MASS_REGISTER.yaml` / `B601_FLEX_MODEL.yaml`）

- 质量账本：URDF 全量 4.6956 kg（HIGH）+ base adapter 1.0395 kg（HIGH）+ 其余 TBD；CAD 估计永远 additive，不替代 URDF
- 柔性模型：link/joint/base/support 刚度全 TBD（pending D1 vendor 关节刚度、D8 覆盖裁决、D4 接触资格）；模态 Case1/Case2 NOT_RUN；与 sim_07/sim_11 口径一致性已登记

## 7. 待裁决决策（冻结前置/并行）

| ID | 决策 | 阻塞 | 现状 |
|---|---|---|---|
| D1 | 保留 vendor 核心不重新外壳化 | F3-P1 全部关节/连杆 PCD | 倾向保留（与迁移指令一致）；需人工签署 |
| D2 | STOW_Z_LIMIT 收拢 Z 上限 | F3-C 闭合、发射包络合规 | UNKNOWN；禁止默认合规 |
| D3 | 唯一顶层装配路线1/2 | F4 集成 | 已逾期 7 天 |
| D4 | G07 接触面资格 | F3-C 几何候选→资格 | HOLD |
| D5 | T_SM 双轨 185.25 vs 198 | 适配器真值位 | O3 未决 |
| D6 | H9 mode A/B | 控制接口 | 已判 retain both |
| D7 | EE 范围 V1+V2 优先、V3 延后 | F3-P3 | 建议确认 |
| D8 | 连杆覆盖热控/MMOD 理由 | S06 可选件 | 延后 |

## 8. F3 子阶段授权边界

| 阶段 | 范围 | 入口 | 出口 Gate |
|---|---|---|---|
| **F3-P1** | 关节模块 + 连杆（A1+A2） | D1 签署 | F3-P1：6 关节 ICD 闭合 + link 制造报告 + 质量账本行 |
| **F3-P2** | 收拢/释放（G07/G08/HDRM/扩散框） | D2/D4 进展 | F3-P2：载荷路径 1 闭合 + HDRM 功能设计 + 质量账本 |
| **F3-P3** | 末端执行器 V1+V2 | D7 确认 | F3-P3：EE 接口 + 柔顺 + 捕获中心 |
| **F3-E**（并行） | 动力学/结构同步 | 每完成一结构即更新 | 模态 Case1/Case2 + 柔性模型填充 |

**禁止**：F3 任一子阶段未过，不得进入 F4 顶层 `SPACECRAFT_TOP_ASSEMBLY_FREECAD.FCStd`。

## 9. 不做（维持禁止）

vendor 内部重设计、飞行级 HDRM、EE V3 抓取指（延后）、Text2CAD 入基线、双平台并行权威、默认 STOW_Z 合规、CAD 质量覆盖 URDF。

## 10. 推进顺序铁律

载荷路径 → 接口 → 关节 → 连杆 → 末端 → 控制模型。禁止按零件序逐个画。
