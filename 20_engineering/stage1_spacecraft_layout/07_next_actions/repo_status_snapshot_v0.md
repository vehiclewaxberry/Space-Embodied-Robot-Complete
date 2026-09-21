# 仓库只读状态快照 v0

> 文档角色：只读状态快照（read-safe snapshot） ｜ 类型：process
> 语言/主从：单语工作文档（中文）
> 版本：v0 ｜ 最后同步：2026-07-08（计数于 2026-07-09 落地验收审计中复核更正，明细见下方复核注）
> 阶段原则：本轮 read-safe，仅新增，不删除/改名/重写现有 03/04/05 文档；未自动 commit。

本快照在开始"项目梳理落地阶段"前生成，用于保证后续所有整理动作可回退。生成时**未修改任何已有文件**。

> **⚠️ 2026-07-09 复核注**：本快照 v0 由落地会话中途生成，低估了自身产出（02、07 目录在其之后继续新增文件）。下列计数已按当前工作区实况更正；更正明细与整体验收见 [`landing_audit_report_v1.md`](./landing_audit_report_v1.md)。

## 1. Git 状态

| 项 | 值 |
|---|---|
| 当前分支 | `doc-reorg-stage1`（本轮新建，基于 `main`） |
| 主分支 | `main` |
| 提交历史 | 仅 1 个提交：`0a6df16 Add stage 1 spacecraft layout library` |
| 工作区 | 大量未跟踪文件（见 §3），落地文件均在此分支以未跟踪状态新增 |

## 2. 目录树（项目自有，excl `80_third_party/external/`、`.git/`）

```
20_engineering/stage1_spacecraft_layout/
  00_source_manifest/        source_manifest.md
  01_standards/              3× PDF + 5× 提取 md（standards_manifest / 约束提取 / 汇总）
  02_open_bus_reference/     10× md（catalog + .en / license_gate / cad_mapping / gap_risks / audit / mapping / policy / candidate lists）
  03_mechanical_layout_notes/ 14× md（brief / ICD / 6U·12U·target·adapter 的 requirements/baseline/reference_inputs / appendix_b_todo）
  04_mass_inertia_budget/    3× md + 2× csv（notes / coord_frame / template.csv / interface_table.csv）
  05_workspace_and_clearance/ 6× md（workspace / collision / keepout / deployable / dimension checklists）
  06_competition_figures/    （空，仅 .gitkeep）
  07_next_actions/           7× md（risk_register / transition / cad_entry / stage2_inputs / doc_reorg_validation / repo_status_snapshot / landing_audit）
  README.md
20_engineering/cad/spacecraft_layout/       5× 交付目录，均仅 .gitkeep（无 CAD 模型）
30_simulation/free_floating_servicer/  README_stage1.md（占位说明）
```

## 3. 跟踪 / 未跟踪清单

- **已跟踪（17 项）**：仅 `.gitignore`、`README.md`、`00_source_manifest/source_manifest.md`、各目录 `.gitkeep`、`80_third_party/README.md#librecube-notes`、`30_simulation/.../README_stage1.md`。即：**只有占位骨架进了版本管理。**
- **未跟踪（51 项）**：全部实质内容 —— 01 的 3 PDF + 5 提取 md、02 的 10 md、03 的 14 md、04 的 3 md + 2 csv、05 的 6 md、07 的 7 md，**外加根目录一个游离文件 `01_project/inbox/source_documents/空间机械臂.docx`**（本轮不处理，仅记录）。其中 02 的 `external_onorbit_asset_catalog.en.md` 系审计期间由 agent 生成（见 `landing_audit_report_v1.md` §4）。

## 4. `source_manifest.md` 资源状态（滞后项已标注）

| 类别 | 状态 | 备注 |
|---|---|---|
| 8× GitHub 参考仓库（OreSat×3 / BIRDS / PyCubed×2 / SpaceRobotEnv / SPOT） | `cloned_ok`，记录 HEAD | 正常 |
| 3× 标准 PDF（CDS Rev.14.1 / NASA CubeSat 101 / SmallSat SOA 2026） | manifest 标 `manual_download_needed` | **⚠️ 滞后**：PDF 实际已下载在 `01_standards/`，状态未回填 |
| LibreCube Notes | `manual_download_needed`（本阶段暂缓 clone） | 正常 |

## 5. 需在后续阶段处理的既有问题（本轮不动，仅登记）

1. **内容未入库**：51 项实质文档处于未跟踪状态，无法被团队引用/评审/追踪。
2. **manifest 滞后**：3 份 PDF 状态未回填。
3. **CAD 目录全空**：5 个交付目录仅 `.gitkeep`。
4. **游离文件**：根目录 `01_project/inbox/source_documents/空间机械臂.docx`（来源不明，未纳入目录结构）。
5. **文档双语重复 / 命名歧义**：详见 `doc_reorg_validation_report_v1.md`。

> 回退方式：本轮所有新增均在 `doc-reorg-stage1` 分支且未 commit；如需放弃，`git checkout main` 即可，新增文件保留在工作区或按需 `git clean` 处理。
