# 文档重组验证报告 v1

> 文档角色：验证报告（read-only verification） ｜ 类型：process
> 语言/主从：单语工作文档（中文）
> 版本：v1 ｜ 最后同步：2026-07-08
> 阶段原则：本报告仅基于真实仓库文件核验，**不删除、不改名、不重写、不补齐** 任何 03/04/05 文档。

## 1. 结论摘要

- 主要问题：**双语重复 + 需求/基线角色边界混乱 + `_v0` 命名歧义 + 坐标系单一真值源冲突**。
- 处置基调（依上轮决定）：**中文为规范主文档，英文为对照从文档；不删除、不改名**，仅"加头注 + 加索引 + 双向补齐字段"。
- 本轮**不执行**任何破坏性修改；下方仅给出核验结论与待补齐清单。

### 核验依据（诚实标注）
- **本会话直接逐行读取并对比**：robot_mount_adapter（中/英）、target_models（中/英）、mass_inertia_budget notes（中/英）、workspace_clearance_checklist（中/英）、servicer_6U requirements + baseline、servicer_12U requirements + baseline、`coordinate_frame_definition_v0.md`、`layout_icd_lite_v0.md`、`subsystem_interface_table_v0.csv`、`mass_inertia_budget_v0_template.csv`、`risk_register_v0.md`。
- **依据既往全文摘要（未逐行复读）**：3× `*_v0_reference_inputs.md`、`collision_avoidance_requirements.md`、`collision_keepout_zone_plan_v0.md`、`deployable_state_checklist_v0.md`、`dimension_verification_checklist_v0.md`、`stage1_layout_design_brief.md`。执行补齐前应对这些再做一次直读确认。

## 2. 文档配对关系表

| 对象 | 中文主文档 | 英文对照/基线 | 关系判定 | 处理 |
|---|---|---|---|---|
| 机械臂转接座 | `robot_mount_adapter_requirements.md` | `robot_mount_adapter_requirements_v0.md` | **真双语重复** | 双向补齐 + 主从头注 |
| 目标模型 | `target_models_requirements.md` | `target_models_requirements_v0.md` | **真双语重复** | 双向补齐 + 主从头注 |
| 质量惯量说明 | `mass_inertia_budget_notes.md` | `mass_inertia_budget_v0_notes.md` | **真双语重复** | 双向补齐 + 主从头注 |
| 工作空间避让 | `workspace_clearance_checklist.md` | `workspace_clearance_checklist_v0.md` | **部分镜像（结构不同）** | 需先对齐结构再补齐 |
| 6U 服务星 | `servicer_6U_layout_requirements.md` | `servicer_6U_quick_layout_baseline_v0.md` | **互补（需求 vs 基线）** | 头注互指，不合并 |
| 12U 服务星 | `servicer_12U_layout_requirements.md` | `servicer_12U_layout_baseline_v0.md` | **互补（需求 vs 基线）** | 头注互指，不合并 |
| 转接座/目标/12U 输入 | — | `*_v0_reference_inputs.md` | **独立（外部资产输入）** | 只标角色，不并入需求 |

## 3. 真双语重复清单（同角色、中文主 + 英文从）

1. **机械臂转接座**（重叠 ~80%）
2. **目标模型**（重叠 ~80%）
3. **质量惯量说明**（重叠 ~85%）
4. **工作空间避让**（部分镜像）——⚠️ 注意：两份**结构不同**，英文 `_v0` 以"位姿检查(5) + 间隙/遮挡检查(5) + 输出规则"组织，中文以"记录格式 + 10 项核心检查 + 图层清单 + 4 图输出"组织；不是干净镜像，补齐前需先统一表结构。

## 4. 互补而非重复清单（不得合并）

- `servicer_6U_layout_requirements.md`（约束 + 6U-LR-01~07 + 质量输出 + 检查清单）↔ `servicer_6U_quick_layout_baseline_v0.md`（Role + Required Layout Rules + Scope Limits + Minimum CAD Entry Inputs）。
- `servicer_12U_layout_requirements.md`（分舱 + 三叙事 + 12U-LR-01~05 + 图件 + GJM/RNS 参数 + 通过条件）↔ `servicer_12U_layout_baseline_v0.md`（Baseline Positioning + placeholder 表 + rail-reference + ASCII 草图 + Stage 1-C Outputs）。
- `*_v0_reference_inputs.md`（转接座/目标/12U）：外部资产输入清单，角色独立。
- `stage1_layout_design_brief.md`：项目级任务书，角色独立。

## 5. 单一真值源（冲突清单）——最高优先级

| # | 主题 | 应有的单一真值源 | 冲突/重复现状 | 建议 |
|---|---|---|---|---|
| S-1 | 坐标系 S/B/C/E/T/I | `coordinate_frame_definition_v0.md` | **同一套坐标系在 `coordinate_frame_definition_v0.md` 与 `layout_icd_lite_v0.md` 中各定义一遍（近重复）**，另在 `robot_mount_adapter_requirements.md`、6U/12U 文档中零散重述 | 定 `coordinate_frame_definition_v0.md` 为唯一真值源，其余文件改为**引用**，不再各写一套 |
| S-2 | 安装面坐标系 `M` | 同上 | ⚠️ `M` 系**只在转接座文档定义，中央坐标系文件缺 M** | 把 `M` 补入 `coordinate_frame_definition_v0.md` |
| S-3 | 变换记号 | 统一为 `T_SB` 形式 | ⚠️ **记号漂移**：中央/ICD 用 `T_SB`；转接座文档用 `^S T_B` / `^S T_M` / `^M T_B` | 全库统一为 `T_SB`（并在附录给出 `^S T_B` 等价说明） |
| S-4 | 变换 T_SB/T_SC/T_ST/T_BE | `coordinate_frame_definition_v0.md` | `coordinate_frame_definition_v0.md` 与 `layout_icd_lite_v0.md` 均列一遍（内容一致但重复） | ICD 引用坐标系文件，不重复定义 |
| S-5 | 质量/惯量字段 | `mass_inertia_budget_v0_template.csv`（表头）+ `mass_inertia_budget_notes` | 中/英两份 notes 重复；CSV 18 列与 notes §7 字段一致（无冲突） | 保留 CSV 为字段真值源，notes 双语补齐即可 |
| S-6 | 接口维度命名 | `layout_icd_lite_v0.md` §4 + `subsystem_interface_table_v0.csv` | ⚠️ ICD 接口分 6 类（mechanical/power/thermal/data/ADCS/mass-inertia），CSV 用 8 维（多出 volume/mounting/keepout） | 对齐 ICD 与接口表的维度命名 |
| S-7 | clearance 数值字段 | `collision_avoidance_requirements.md`（`clearance_robot_body_m` 等） | 数值字段**只在 collision 文档**，workspace 清单未引用 | workspace 清单头注指向 collision 文档，避免另立一套 |

## 6. 待补齐字段清单（双向）

| 编号 | 目标文件 | 缺失字段 | 来源文件 | 优先级 |
|---|---|---|---|---|
| V-ADP-01 | `robot_mount_adapter_requirements.md`(中) | 状态字段列（TBD until CAD）、rail/protrusion 6.5/8.5mm P0 检查、Non-goals | `_v0`(英) | High |
| V-ADP-02 | `robot_mount_adapter_requirements_v0.md`(英) | `M` 安装面坐标系完整定义、ADP-01~06 编号、§6 九项检查清单、`^S T_B` 矩阵展开 | 中文主 | High |
| V-TGT-01 | `target_models_requirements.md`(中) | `manual_review_required`/`TBD` 措辞、Traceability（喂 `T_ST`/Stage2） | `_v0`(英) | High |
| V-TGT-02 | `target_models_requirements_v0.md`(英) | §6 惯量记录（shape_model/reference_frame/reference_point/confidence/update_plan）、§7 通过条件 | 中文主 | High |
| V-MI-01 | `mass_inertia_budget_notes.md`(中) | Data Maturity（measured 定义）、"缺失字段须作阻塞项"、datasheet/allocation 来源行 | `_v0`(英) | Med |
| V-MI-02 | `mass_inertia_budget_v0_notes.md`(英) | §7 CSV 字段逐条说明、§8 填写原则 | 中文主 | Med |
| V-WS-01 | `workspace_clearance_checklist.md`(中) | 英文的 5 项位姿检查（zero/folded/max/pre-grasp/capture）与 status 列 | `_v0`(英) | High |
| V-WS-02 | `workspace_clearance_checklist_v0.md`(英) | 中文的检查记录格式、叠加图层清单、4 图输出要求 | 中文主 | High |
| V-WS-03 | 两份 workspace 文件 | 与 `collision_avoidance_requirements.md` 的 `clearance_*_m` 字段互指 | collision 文档 | High |
| V-SSOT-01 | `coordinate_frame_definition_v0.md` | 补 `M` 系；接收其他文件对坐标系的引用回指 | 转接座文档 | P0 |
| V-SSOT-02 | 全库含坐标符号的文件 | 统一 `T_SB` 记号，去除 `^S T_B` 混用 | — | P0 |

## 7. 建议执行顺序

1. （本报告）确认真重复 / 互补 / 单一真值源结论 —— **已完成**。
2. 先解决 **S-1~S-4 坐标系单一真值源**（补 `M`、统一记号、ICD 改引用），因为它一旦漂移会污染 CAD/仿真。
3. 给每份文件加"主从 + 类型 + 版本 + 最后同步"头注；每目录加 `_index.md`。
4. 按 §6 表**双向补齐**真双语重复 4 组（补齐前对 workspace 先统一表结构）。
5. 6U/12U requirements↔baseline 只加头注互指，不合并。
6. 完成后再进入 CAD v0（见 `cad_asset_mapping_v0.md`）。

> 本报告为**判断依据**，不是执行动作。任何补齐/改名须另行确认后在本分支进行。
