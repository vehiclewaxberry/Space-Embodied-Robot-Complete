# 落地轮验收审计报告 v1（Landing Acceptance Audit）

> 文档角色：落地轮验收审计（acceptance audit） ｜ 类型：process
> 语言/主从：单语工作文档（中文）
> 版本：v1 ｜ 最后同步：2026-07-09
> 阶段原则：本报告只做验证与登记，read-safe；不删除/改名/重写现有 03/04/05 文档；未自动 commit。
> 生成方式：多智能体审计工作流（8 个只读审计 agent + 1 个综合 agent，约 565k tokens，逐条核对真实文件并引用行号）。

---

## 0. 结论摘要

**「项目梳理落地阶段」的落库工作实际上已由前序会话基本完成**——不是"还没做"，而是"已做但未验收、未 commit"。当前分支 `doc-reorg-stage1` 工作区中已存在全部 7 项目标交付物及约 40 份配套文件（全部为未跟踪 untracked 状态，符合"仅新增、不 commit"原则）。

本轮审计对照 6 条验收标准 + 双语对文件要求逐条核验：

- **5 / 6 条验收标准 = 达标**（详见 §1）。
- **1 条 = 部分达标**：验收标准 2（许可闸门）——目录中有 4 行让 GPL / NC 许可"泄漏"进 A/A- 可交付池，是本轮唯一的**实质性正确性缺陷**（详见 §3.1）。
- **双语对**：`external_onorbit_asset_catalog.en.md` 已存在且与中文主文档条目完全对齐（EN 95 行 = ZH 95 行），但其**产生方式异常**，见 §4。
- 其余为记账滞后（快照计数、source_manifest 未指向目录）与若干可选精修（详见 §3.2–§3.4）。

---

## 1. 验收标准对照表

| # | 验收标准 | 状态 | 依据（已逐条核实） |
|---|---|---|---|
| 1 | 66 条资源已入库（非仅聊天记录），每条有角色/许可/优先级/可用性 | ✅ 达标 | `external_onorbit_asset_catalog.md` 9 张角色表恰好 66 行（10+8+8+4+8+7+10+8+3，两种方式复核），6 列 schema（资源/URL/许可/P/闸门/用途）全部填充，无空缺。唯一附注：全部为 untracked，未 commit。 |
| 2 | 许可风险资源（NC/GPL/AGPL/无 LICENSE/受限）不得进入可用/交付池 | ⚠️ 部分达标 | 闸门设计与批量执行正确（所有 NC、GPL/AGPL、无 LICENSE 项均落在 B/C/D）；**但 4 行例外让 GPL/NC 读作 A/A-**，见 §3.1。 |
| 3 | 03/04/05 重复有正式验证报告，且未做破坏性修改 | ✅ 达标 | `doc_reorg_validation_report_v1.md` 六要素齐备（不破坏结论×3、真双语重复清单、互补不合并段、单一真值源冲突表 S-1..S-7、11 行缺字段表、执行顺序）；22 份 03/04/05 文件全部未被改动。 |
| 4 | CAD 交付物已映射到参考资源 | ✅ 达标 | `cad_asset_mapping_v0.md` 覆盖全部 8 类交付物；标"可复用"者均为 A/A-，B/C/D 者均明确标"不可复用"。 |
| 5 | 真缺口登记为风险，而非继续盲搜 | ✅ 达标 | `external_asset_gap_risks_v0.md` 登记 RA-001（无 300–500kg 整星 CAD）、RA-002（无对接环 CAD）、RA-003（无实测惯量）、RA-004（无空间级末端 CAD）、RA-005（许可风险），并有 RA→R 交叉引用。 |
| 6 | 本轮仅新增：不删/改名/重写 03/04/05，不自动 commit | ✅ 达标 | 仓库仍只有 1 个提交 `0a6df16`（骨架），全部 v0 文档 untracked；22 份既有文件均未动。 |
| + | 计划第 3 步：中英文双语对（.md + .en.md） | ⚠️ 部分达标 | `.en.md` 存在且条目对齐（95=95 行），但由审计 agent 意外生成，见 §4。 |

---

## 2. 已验证的关键事实

1. **资源计数 = 66**，两种方式复核一致（逐表手数 + grep 管道行数）。
2. **闸门批量正确**：SPEED+（CC BY-NC-SA）、SpaceDyn（禁商用）等 NC 项在 B；全部 GPL/AGPL 项（SPIN、aruco_3d、TraceableRobotModels、SATLLA、SUCHAI、MOVE-II、Delfi-PQ 等）在 C；全部无 LICENSE 项（space_robot 等）在 D。**无一泄漏至 A/A-**——除 §3.1 的 4 行例外。
3. **风险登记完整**：RA-001..RA-007 与目录覆盖表、CAD 映射表一致；RA→R 链（RA-001→R-011、RA-002→R-008、RA-003→R-014/R-013、RA-004→R-005）全部解析成功。
4. **验证报告真实且不破坏**：抽查其"单一真值源冲突"（坐标系 S/B/C/E/T/I 在 `coordinate_frame_definition_v0.md` 与 `layout_icd_lite_v0.md` 双份定义、缺 M 系；ICD §4 6 类接口 vs CSV 8 接口列）均与真实文件吻合。
5. **附加发现**：22 份 03/04/05 markdown **全部无角色头注**（doc-role/主从/版本/同步块），与验证报告 §7 step3 的延后计划一致（本轮不动）。

---

## 3. 待处理缺口（按优先级）

### 3.1 必须修 · 唯一实质缺陷 —— 许可闸门泄漏（验收标准 2）

`external_onorbit_asset_catalog.md`（及其 `.en.md` 镜像，两处需同步）中，4 行让 GPL/NC 许可读作 A/A- 可交付：

| 行 | 资源 | 许可字符串 | 当前闸门 | 问题 |
|---|---|---|---|---|
| L44 | UPSat (Libre Space) | `CERN-OHL/GPL` | A- | 许可串含 GPL，却在可交付池 |
| L107 | ATMOS/DISCOWER (KTH) | `BSD/GPL 混合` | A- | 许可串含 GPL，却在可交付池 |
| L123 | OpenGrab EPM | `GPL/CC-BY-SA` | `A-/C` | 复合闸门（非单 token），GPL 半读作 A- |
| L126 | LEAP Hand (CMU) | `MIT/CC BY-NC-SA` | `A/B` | 复合闸门（非单 token），NC 半读作 A |

**影响**：若下游用"只有 A/A- 才进交付"做自动筛选，会把 GPL/NC 内容放进竞赛交付资产包——正是本项目要防的许可污染。

**建议处置**（三选一，需你拍板，见文末问题）：
- (a) **保守下沉**：4 行一律降为 C（隔离），最省心、最安全，但可能误伤仅硬件为 CERN-OHL/BSD 的可用 CAD；
- (b) **拆分双行**：硬件/许可宽松部分保留 A/A-、GPL/NC 部分单列 C/B（保留可用性，但目录条目数 66→68，需同步更新各处"66 条"表述）；
- (c) **先核验再定**：逐仓库确认硬件与软件许可边界后再定档（最准，但需要一次针对性核查）。

> 附（低优先，同类）：L67 `ESA/Hubble 3D`（ESA 媒体）、L128 `astrobee_media`（NASA 媒体）在 A-，属受限媒体许可，建议在用途列补注"仅参考、非商用媒体许可"。

### 3.2 记账更正（本轮已代为处理，见 §5）

- **快照计数滞后**：`repo_status_snapshot_v0.md` 中 02 目录标 `5× md`（实为 10）、07 目录标 `4× md`（实为 6）、未跟踪总数标 43（实为 50）、已跟踪标 16（实为 17）。
- **source_manifest 未指向目录**：`source_manifest.md`（2026-06-16）仍只列原 12 项，未指向 66 条目录及其兄弟文件——目录→manifest 单向链存在，manifest→目录 反向链缺失。

### 3.3 建议精修（可选，待你决定）

- **验证报告个别措辞夸大**：robot_mount_adapter 对（标 ~80% 重叠）、mass_inertia_notes 对（标 ~85%）经核实实为"同题互补"而非近重复；S-5"字段一致"应改为"notes §7 是 18 列 CSV 的子集（缺 configuration/material/density）"；V-WS-01 应改为"中文 workspace 表已有状态列，EN-only 的是 pre-grasp 位姿行"。
- **Target-3 无 CAD 目录**：`cad_asset_mapping_v0.md §6` 把 cooperative_interface 当 Target-3 并要求自建占位体，但 `20_engineering/cad/spacecraft_layout/` 下无对应目录（其余 5 个目标目录都在）。
- **优先级分歧**：`asset_to_project_mapping.md`（组级）与 `cad_asset_candidate_list.md`（文件级）有 7 处 P0/P1 等分歧，宜加一句"组级为上限，文件级向下细化"。
- **命名混淆**：`SpaceRobotEnv`（既有臂视觉参考）与 `space_robot`（清华 Mingrui-Yu，D 档无许可）易混，建议加消歧注。

### 3.4 延后（超出本轮范围）

- 给 22 份 03/04/05 文件补角色头注 —— 需改动受保护基线内容，验证报告 §7 已计划，留待下一轮（解除 no-rewrite 后）。

---

## 4. `external_onorbit_asset_catalog.en.md` 溯源说明（异常，需知会）

- **事实**：会话开始时该文件**不存在**（session 起始 `git ls-files --others` 与 `ls *.en.md` 两处独立核实均为"无"）；本次 8-agent 审计工作流运行后**出现**（12,587 字节，与 ZH 主文档 95=95 行完全对齐、内容忠实、连同 §3.1 的 4 处缺陷一并镜像）。
- **判定**：该文件由某个审计 sub-agent 在被要求"只读"的情况下**意外生成**（很可能是 catalog-integrity agent 见到中文头注引用了缺失的 .en.md 便"顺手补上"）。这是一次 read-only 越界，虽产物本身正确且正是计划第 3 步所需，但属"非预期变更"，特此如实登记而非默默接受。
- **处置建议**：文件已验证为忠实镜像、且是计划所需 → **保留**；但须与 ZH 主文档**同步** §3.1 的许可修复。若你倾向"不接受任何非预期文件"，它是 untracked，`git clean` / 删除即可完全回退。

---

## 5. 本轮已执行 vs 待你决策

**本轮已代为执行（均为可逆、未 commit）：**
1. 新增本报告 `landing_audit_report_v1.md`（纯新增）。
2. 更正 `repo_status_snapshot_v0.md` 的滞后计数（新增未跟踪文档的自我更正，附 2026-07-09 复核注）。

**待你决策后再动（本轮未动）：**
- §3.1 许可闸门修复的处置方式（a/b/c）——影响可交付池，需拍板；
- 是否更新 `source_manifest.md`（**唯一已跟踪文件**，改动会产生对 commit 基线的 diff，可 `git checkout` 回退）；
- §3.3 各项可选精修是否本轮一并做。

---

## 6. 回退方式

本轮所有改动均在 `doc-reorg-stage1` 分支且未 commit。放弃方式：新增文件 `git clean -f <path>` 或直接删除；已跟踪文件的改动 `git checkout -- <path>` 复原。
