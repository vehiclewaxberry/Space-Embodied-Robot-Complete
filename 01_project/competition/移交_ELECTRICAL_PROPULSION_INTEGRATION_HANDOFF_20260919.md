# 电控与推进动力系统集成收口移交文档

日期：2026-09-19（Asia/Tokyo）。移交方：本轮机械/溯源线（Kimi Work，构建者 agent-12 + 独立审阅者 agent-11 双链）。接收方：负责电控与推进动力系统集成收口的下一任 agent。

本文档是状态移交与纪律说明，**不是**工程通过回执、制造批准或任何 Gate 重发。所有科学/工程结论以各 run 的机器裁决 JSON 为准。

接续核对：Codex 于 2026-09-19 从已提交的本文档 `b0b09ccc` 接手，先核对现有 HANDOFF 前滚链，再补充本文。机械/溯源阶段一收口证据成立；WP10 前滚链存在一项绑定哈希失配，接收方须先按 §5 第 1 项处理，详见 §6。

路径约定：下文 `runs/` 均相对于 `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/`；WP10 各小节的 `results/`、`ecad/`、`coupled_closure/` 均相对于 `runs/wp10_mechatronic_closure_20260908/implementation/`。WP03 的 `results/` 则位于其工程目录内。

## 1. 仓库状态

- 接续前基点：分支 `docs/fix-third-party-notices-link`，HEAD=`b0b09ccc`（本文档首次提交）；`bf4cb95a` 为独立复验收口提交。宿主侧只读 `git status --porcelain=v1` 确认工作区干净；本次文档补充以随后 Git 提交为准，避免把文档创建前的提交误称为最新提交。
- 机械侧阶段一（局部数字装配整改）已于本日整体收口：R01（甲板紧固）、R07 五边中 E1–E4、R17（交付链）、严格验证器接入 + R14 扰动，全部"构建者 → 独立复验"双链闭环，复验裁决均为 PASS 或 PASS_WITH_OBSERVATIONS。
- 整星实例口径：结构态 487 / 全态 497=487+10 臂（BOM 497 行，15 列，214 分配 / 283 未分配 null——null 是纪律不是缺陷）。

接续前最近 6 笔提交按时间顺序如下（包括 R07-E4 两笔；单列 R17、验证器和首次移交只涉及后 4 笔）：

| 提交 | 工作包 | 已记录结果 |
|---|---|---|
| `d1a3b70a` | R07-E4 构建 | 后隔框 4 角阶梯夹套，结构态 483→487 |
| `664d7388` | R07-E4 独立复验 | PASS_WITH_OBSERVATIONS；负控 5/5、抽查 10/10 |
| `de892b81` | R17 交付链来源时序修复 | HANDOFF 逐项 fail-closed；负控 8/8；`--bom-only` 零 CAD 依赖；9 项交付物哈希对照 |
| `d29b06d6` | 严格验证器接入 + R14 扰动 | 期望配对由快照派生；负控 11/11；扰动预期效应确认与恢复 bit-identical |
| `bf4cb95a` | 两包独立复验 | 均 PASS_WITH_OBSERVATIONS；R17 负控重放 6/6、静态复核 5/5；验证器负控 7/7、沙箱全链逐位一致；OB2 两文件纳入提交 |
| `b0b09ccc` | 首次移交文档 | 本文档初版；本次接续补充在此基础上提交 |

## 2. 已完成资产索引（接收方直接可用）

### 2.1 结构/机械（WP03，`20_engineering/service_robot_wp03_spacecraft_body_r1/`）
- R01：甲板—角材—剪力板 32 组紧固，V2 候选复验 PASS（`runs/r01_deck_fastening_20260917/` + `..._review/`）。
- R07-E1：根部桥/横梁→主纵梁 10 组 16 栓位锚固（`runs/r07_root_longeron_anchoring_20260917/` + `r07_e1_anchoring_review_20260918/`）。
- R07-E2：纵梁→端塞 8 站分段短销（`runs/r07_e2_endplug_retention_20260918/` + `..._review_20260918/`）。
- R07-E3：保持横梁→纵梁 4 组 + 足叉→耳座 2 组（`runs/r07_e3_retention_joints_20260918/` + `..._review_20260918/`）。
- R07-E4：端框→后保留隔框 4 角阶梯夹套（`runs/r07_e4_rear_bulkhead_20260918/` + `..._review_20260918/`）。
- R17：交付链 fail-closed 来源校验（`runs/r17_export_chain_20260919/`）；BOM 写出前 HANDOFF 逐项校验。校验拒绝 `HandoffRejected` 为 exit 2 + 字节恢复；其他异常同样恢复交付物，但不保证 exit 2（独立复验 OA1）。
- 验证器：pose_screen 期望配对快照派生（35/36），strict_surface_integration.py fail-closed，R14 扰动预期效应确认（`runs/validator_integration_r14_20260919/`）。
- 复验总裁决：`runs/stage1_closure_review_20260919/REVIEW_VERDICT_R17.json` + `REVIEW_VERDICT_VALIDATOR_R14.json`。
- 复验观察项继续携带：OB1 的 `require_physical_view()` 仅为独立守卫，尚未接入 `aggregate()/main()`，爆炸视图负控只证明守卫行为；OB2 两文件已由 `bf4cb95a` 纳入；OB4 的扰动质量/体积有 2/6 行出现 1 ULP 差异（相对 ≤2.06e-16，复验容差 1e-12），不外推为所有扰动字段逐位相同。
- 阶段一收口指上述候选与复验链完成。R17 验收仍保留 `ticket_closure=NOT_CLOSED`，`issues.json` 票字段留 owner；`finalize_delivery.py`、`geometry_checks.py`、`integrate_checks.py` 在本次收口链未重跑，展示视图刷新亦未包含。

### 2.2 电控（WP10，`runs/wp10_mechatronic_closure_20260908/implementation/`）
- STOP 控制板：KiCad 布线完成，DRC 0/0（按 5 条已声明忽略规则），1043 走线/98 过孔，板级热 1.483W（不含 Q101）。`STOP_PCB_implemented=false`；上述检查不提供载流、瞬态、EMC、热裕度或硬件试验证据。
- 选型著录：rating/substitution 缺口 224→**45**＝4 行 STOP UNKNOWN（TPS3431/TLV6700×3）＋41 行系统侧 UNKNOWN。系统侧按待办拆分为 38 行无 MPN 占位/裸值，以及 3 行缺手册：U207 TPS26600PWPR、U303 MAX5048CAUT+T、U304 MAX16053AUT+T。**按结构化 MPN 字段直接统计则有 39 行空值**，因为 U304 的型号只在 value/缺项说明中，须归档手册并回填 MPN 列。不得将 41 行全部称为无 MPN 占位。证据：`results/electrical_selection_20260917/SYSTEM_RATING_ANNOTATION_20260917.json` + `SELECTION_GAPS_UPDATE2_20260917.json`。
- 现行交接指针：`coupled_closure/HANDOFF_LATEST.json` → `HANDOFF_DELTA_20260917_STOP_REVIEW_COMPLETE.json`（2026-09-17 前滚）。指针自身绑定匹配，但 delta 的 `working_revision` 绑定失配（§6），故尚不能视为整条前滚链已验证。
- delta 中“224 行缺口”是当时快照；电控缺口接续须再读 `SELECTION_GAPS_UPDATE2_20260917.json` 的 45 行口径，原历史 delta 保留。

### 2.3 推进（WP10 贸易研究，未定型）
- `results/propulsion_trade_20260917/PROPULSION_TRADE_STUDY_20260917.md` + `PROPULSION_TRADE_MATRIX_20260917.json`：8 候选，Dawn B1/B20 与 HPGP 1N 过推力窗；**选型未冻结**；矩阵列 9 项 OEM ICD 缺项（厂家数据）；任务需求 |H_c|=3.65 N·m·s、2×12mN@0.17m、推进剂预算 54.735g、总冲量下限 42.9 N·s。42.9 N·s 属目录盒假设下的下限，实际安装力臂与任务预算尚未闭环：`mission_budget_closed=false`、实际任务可行性 UNKNOWN。

### 2.4 热控（WP10，FE/试验必需）
- 架构 A 137.2°C FAIL（95°C 限）；架构 B 筛选：B1a FAIL、B1b/B2 区间跨限 UNKNOWN。
- 设计目标已反解：`results/thermal_architecture_20260917/THERMAL_ARCHITECTURE_B_DESIGN_TARGETS_20260917.json`——B1b 需 R_eff ≤0.237 K/W（85°C 目标不可达，MARGIN_NOT_ACHIEVABLE）；B2 双纵梁并联可达 83.2–86.9°C（ACHIEVABLE_WITH_COMBINED_LEVERS__DUAL_RAIL_PER_SIDE_REQUIRED），不确定性须 FE/试验压缩。

## 3. 未闭环项与输入阻塞（接收方须知）

| 项 | 状态 | 阻塞原因 |
|---|---|---|
| WP10 HANDOFF 前滚链 | 绑定失配，待核对 | delta 中 `working_revision.sha256` 与现文件不一致；见 §6 |
| R07 第 6 边 A/B 支承约束与反力 | 输入阻塞登记 | 需保持器接触刚度/装配误差/预紧实测（硬件组） |
| 推进选型冻结 | SELECTION_NOT_FROZEN | 9 项 OEM ICD 字段待厂家 |
| 热控 B2 定版 | FE_OR_TEST_REQUIRED | 双梁方案不确定性须 FE/试验压缩 |
| 选型 45 行缺口 | UNKNOWN 保留 | 38 行占位须确认料号；3 行系统器件及 4 行 STOP UNKNOWN 须归档手册/补录额定；U304 另须回填 MPN 字段 |
| 全部机械候选 | DIGITAL_GEOMETRY_CANDIDATE 级 | 载荷/强度/选型/材料/制造性均 NOT_RUN |

## 4. 纪律红线（违反即返工）

1. FAIL 历史不被 PASS 覆盖；新裁决引用旧裁决原样保留。
2. UNKNOWN 显式保留，禁止零填；未分配质量保持 null。
3. 每个证据 JSON/CSV/STEP 配 .sha256 边车：`open(path,'wb')` 二进制写、LF 行尾、run 根相对路径（`hash + 两空格 + 相对路径`）。
4. 禁止宣布 whole_design_complete / manufacturing_release；禁止改写 issues.json 票字段、gate 文件、CURRENT 指针。
5. 布尔干涉一律 OCP `BRepAlgoAPI_Common` 原生路径（build123d `Shape.intersect` 对 import_step 读回件会静默返 None 伪装零干涉——E2 勘误 O2）；bit-identical 声明须注明操作数次序口径（E4 观察项 O6）。
6. CAD 重任务串行、唯一构建者；构建者不接受自己的修改——独立复验是闭环的必要条件。
7. WP02 原始文件只读；WP03 改动走参数驱动 + 唯一几何来源函数 + 最小修改。
8. KiCad 写操作走 `tools/native_delta_guard.py`（cwd=WP10 implementation）；Sim13 验证用 `G:/Windows_program_file/Anaconda/python.exe`。

## 5. 建议接手顺序

1. 先读：`PROJECT_MAP.md` → 本文档 → `HANDOFF_LATEST.json` → 各 run 的 ACCEPTANCE_SUMMARY / REVIEW_VERDICT。优先核对 §6 的 `WORKING_REVISION.json` 哈希失配；明确版本差异、保留旧 delta 后，由接手电控线按受控前滚流程生成新绑定并复验。失配解除前，不宣称 WP10 HANDOFF 全链通过。
2. 电控收口：读取 `SELECTION_GAPS_UPDATE2_20260917.json`，按 §2.2 拆分 45 行待办 → STOP 板 Q101 热核算并入板级热 → 与热控 B2 设计目标对账。
3. 推进收口：9 项 OEM ICD 缺项列询价/数据申请表 → 选型冻结评审 → 推进模块与 WP03 结构接口（储箱/推力器安装）数字装配。
4. 热控：B2 双纵梁方案 FE 建模压缩不确定性 → 定版。本次会话已发现 Ansys Workbench/Mechanical MCP 工具入口，尚未验证求解器连接、许可证或运行状态；接手时先执行环境检测。
5. 每一线仍按"构建者 → 独立复验"双链执行。

## 6. 本次中断现场只读核对（2026-09-19，基点 b0b09ccc）

| 核对项 | 实际结果 |
|---|---|
| Git 现场 | 宿主侧工作区干净，无暂存改动。沙箱曾将历史 `.tmp_*` 下 125 项显示为删除；宿主只读复核为 0 项，未对这些文件执行恢复或删除 |
| R17 交付物 | `r17_deliverables_hash_compare.json` 中 9 项 `sha256_after` 均与现文件匹配 |
| 收口链边车 | R17 40 条、验证器/R14 38 条、独立复验 12 条，共 90 条 SHA-256 全匹配（不含 `_work` 沙箱副本） |
| R17 只读校验 | 调用 `validate_handoff_provenance`、三态 `validate_receipt_for_bom`、`cross_validate`，违规 0；未载入 CAD 模块，未执行导出写文件 |
| 严格汇总器只读复算 | 使用现行 `POSE_SCREEN.json` 与已冻结 `inputs/snapshot_binding.json`；协议 PASS、36 对/延期 1 对/3 姿态；机械为 `DISJOINT_WITHIN_DECLARED_SCOPE` |
| BOM | 497 行、15 列；214 分配、283 空单元（null）、分配质量零填 0 行 |
| WP10 前滚指针 | `entry_sha256` 匹配，`previous_snapshot_sha256` 匹配；delta 内 9 项 evidence 绑定有 8 项匹配、1 项失配 |

上述为现存证据完整性与只读校验，未重跑 CAD、负控、扰动或硬件试验，不替代 `bf4cb95a` 的独立复验裁决。

WP10 唯一失配项为 `ecad/revisions/v36/WORKING_REVISION.json`：

- delta 期望 SHA-256：`50a6f1796f48dbfc0a6d18e4c65683920692bfed87bf625321653031fe8c6671`。
- 现文件 SHA-256：`9f95e871e5dc772d671ed4c0dad9f51727d648c5b0dfb4c6b96b4d96580e3fbb`。
- 该文件最近更新提交为 `c3b29a19`（AUX V36 继承回执），较前一版本 `1084d089` 改动 `status` 并增加 `AUX_PCB_V36`。`1084d089` 版本哈希为 `6b9f77d33a44fbaeb79fae49963ea3b998eaa7eb965ff8cc6488b8cf54a388f0`，也不等于 delta 期望值，因此不能将失配原因仅归于最后一次 AUX 更新。
- STOP 板本体、DRC、工程评审、验证回执、颈部加宽回执、公开来源、热范围及热预算共 8 项绑定仍匹配。原 delta、指针、票字段和机器裁决均保留；本次只在移交文档登记失配及接手动作。
