# F3R2 机械收口活动 — 迁移交接规格（交由 Codex 执行，Claude 验收）

- 日期：2026-08-08
- 决策：**由 Codex 代理执行迁移，Claude 只做哈希验收**（用户裁决）
- 状态：`MIGRATION_HANDED_OFF_PENDING_CODEX_EXECUTION`

## 0. 为什么要交接

2026-08-07 晚，WAVE4 destructive cleanup（裁决
`WAVE4_DESTRUCTIVE_CLEANUP_COMPLETE_WITH_HIGH_RISK_HOLD`）把机械活动根与全部原生
CAD 血缘移出仓库，落在治理工作区
`F:/_SEI_PROJECT_CONSOLIDATION_20260807/12_WAVE4/WORKTREE_RECONCILIATION/20_engineering/`。
该位置不在 REORG04 八大业务域内。

Claude 尝试迁回时发现**两个 `codex.exe` 正在并发提交同一目录**（HEAD 于工作期间
从 `cd0ea80` 前进到 `5849b72` → `5c5adde`），并且 Claude 写入
`20_engineering/` 的四个文件被删除。两个写者进同一棵树无法安全并行，故迁移交由
已在做 CM3 资产归位的 Codex 代理执行。

**没有任何资产丢失。** 迁移未开始：零文件被拷贝，零文件被覆盖。

## 1. 源与目标

| 项 | 路径 |
|---|---|
| 源（权威快照） | `F:/_SEI_PROJECT_CONSOLIDATION_20260807/12_WAVE4/WORKTREE_RECONCILIATION/20_engineering/` |
| 备份快照（勿动） | 同级 `WORKTREE_SAFETY_SNAPSHOT/untracked_copy/` 与 `untracked_moved_out/` |
| 目标 | `F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/` |
| 体积 | 5.66 GB / 3341 个仅存于源的文件 |

三份副本已由 Claude 用 `diff -rq` 验证**逐文件一致**。

## 2. 必须迁移的顶层项（源有、仓库无）

| 目录 | 体积 | 说明 |
|---|---|---|
| `F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/` | 738 MB / **479 文件** | 进行中的终局收口活动，含全部机器裁决 |
| `F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/` | 890 MB / **363 文件** | `KEEP_UNTIL_F3R2`，F3R2 的只读输入源 |
| `F3_MECHANICAL_TERMINAL_AUDIT_20260806/` | 1 MB | 首轮只读审计 |
| `F3_P5_structural_closure_candidate/` | 1 MB | P5A/P5B/P5C/P5D（FEA/垫/配置/制造发布） |
| `design_inputs/`、`design_review/`、`parameter_registry/` | 各 1 MB | |
| `cad/` 下 15 个子目录 | 4031 MB | 见下 |

`cad/` 需迁子目录：`B5_0_B601_space_manipulator_candidate` (593MB)、
`B5_1_B601_interface_closure_candidate` (2017MB)、
`B5_1R1_B601_interface_native_rework_candidate` (133MB)、
`B5_1R1_B601_interface_collision_and_articulation_rework_candidate`、
`Space_Embodied_Robot_CAD_V0_1/V1_0/V2_0/V2_1/V2_2/V2_2_NATIVE/V2_3_NATIVE_INTEGRATION`、
`F3_MANUFACTURING_GRADE_DESIGN`、`F3_manufacturing_arm`、`_failed_builds`、`audit`。

## 3. 重叠项裁决（Claude 已逐文件预检，3528 文件）

| 分类 | 数量 | 处置 |
|---|---|---|
| 完全相同 | 101 | 跳过 |
| **仅 CRLF 差异** | 81 | **跳过，保留仓库版本**（见 §5） |
| **真实分歧** | **2** | **保留仓库版本** |
| 仅在源 | 3341 | 迁移 |
| 仅在仓库 | 3 | 保留 |

两处真实分歧，**仓库版本正确，不得用源覆盖**：

1. `cad/spacecraft_layout/arm_b601_v1/README.md` L10
2. `config/geometry/arm_b601_v1.yaml` L10 `hardware_step`

二者皆为 Codex 在 `5849b72` 中的 CM3 修复：把损坏的
`F:/Robotic arm/High_performance_robotics_arm/...` 绝对路径改成仓库相对路径。
源快照持的是**修复前**的坏路径。

`cad/freecad_authoritative/` 与 `cad/reference_donors/` 两侧**完全一致**，无需处理。

## 4. 硬约束

1. **禁止覆盖。** 目标已存在即跳过并计数。
2. **拷贝，不移动。** `WORKTREE_SAFETY_SNAPSHOT` 与 `WORKTREE_RECONCILIATION`
   保持字节完好，退役时机由用户决定。
3. **不得修改** F3R1 与 F3R2 树内任何文件内容——它们含已冻结的机器裁决，
   路径变了但语义必须逐位不变。
4. **不得触碰** accepted B601 URDF、`mass_inertia_budget_v1.csv`、两个 donor
   `.SLDASM`。

## 5. ⚠ CRLF 陷阱（迁移后验收必读）

仓库 `core.autocrlf=true`，`.gitattributes` 对 `.urdf` 为 `text: unspecified`。
checkout 会把 LF 改成 CRLF，于是**受保护资产的 `sha256_file()` 必然不匹配**，
看起来像污染。已实测证伪：

- accepted URDF 磁盘 `1BC2B748…C164` ≠ 声明 `408147DD…A3A4`
- `git show HEAD:<urdf>` → **精确等于** `408147DD…A3A4`
- 磁盘字节 `CRLF→LF` 归一化 → **精确等于** `408147DD…A3A4`
- `git diff HEAD` 空；11029 blob 字节 → 11321 磁盘字节（292 处 LF→CRLF）

**验收规则：文本类受保护资产必须同时比对 git blob 与 CRLF→LF 归一化磁盘字节；
只有两者都不等于声明值，才是真污染。** 二进制 `.SLDASM` 不受影响。

## 6. 验收口径（Claude 执行 `m2_migration_acceptance.py`）

| 判据 | 通过条件 |
|---|---|
| MA-1 活动完整性 | F3R2 目标端 **479** 文件，F3R1 **363** 文件 |
| MA-2 逐文件摘要 | 源每个文件在目标端存在且 sha256 相同（文本类允许 CRLF 归一后相同） |
| MA-3 V2_2 donor | `30C09B50A0D2967EC1F48050CAAC34D12A43565C44978D54E3785595202DEF7A` |
| MA-4 B51 臂 donor | `603B87BBD4398FDDB3F732FFBFA7E1C080ED91ED6E0A026D56CBDCBA08DE2E22` |
| MA-5 accepted URDF | 按 §5 双口径校验 |
| MA-6 质量惯量预算 | `073C802527E35C9495188EEFD5D8BA51F524D326142CF2AB31E436BAD0899392` |
| MA-7 CM3 修复保全 | 上述 2 文件仍为仓库版（相对路径），未被源覆盖 |
| MA-8 裁决语义不变 | F3R2 全部 `*_gate_check.json` / `*_DEFINITION.json` 摘要与源逐位一致 |
| MA-9 快照保留 | 两个 `WORKTREE_*` 目录仍在且文件数不减 |

全过 → `M2_MIGRATION_ACCEPTED`；任一失败 → `M2_MIGRATION_REJECTED` 并列明失败项。

## 7. 迁移后 Claude 侧待办

`r2_common.py` / `r2_env.py` / `r2_kin.py` 把 `REPO/20_engineering/F3R{1,2}...` 写死为
绝对路径。迁回原位后**无需改代码**即可继续；若 Codex 选择了别的目标路径，
需同步更新这三个文件的常量（仅路径，不动任何数值）。

## 8. 不受本次迁移影响的科学结论

以下结论从 B-rep 与 accepted URDF 测得，与目录位置无关，已冻结：

- **G3-0** `G30_TSM_STACK_FROZEN`：185.25（动力学 frame，无实体）/198（适配板面）/
  208（实体螺栓面）为同轴三特征；载荷路径 5 段连续 171→208。
- **G3-1** `G31_BASE_INTERFACE_DEFINED`：B601 的 8×M3 螺栓圈（外缘 R48.65）整体悬于
  Central_Boss 的 r50 通孔上 → 凹入式接口环，6 零件 298.9 g。
- **G3-2** `G32_SUPPORTS_V2_DEFINED`：P5B 垫规格不变，改承托头为 54×54 / 34×34 /
  34×34.4，16 零件 336.1 g。
- **G3-3a**：夹爪 **58 个 solid**（非 1 个），按 URDF 钳口轴精确镜像为
  左 24 / 右 24 / 掌 10，左右体积 43578.8 mm³ 逐位相等；逐 solid 网格实测
  OPEN 净距 **82.23 mm**、PREGRASP **50.50 mm** 不相碰。旧档
  `solids_in_cad: 1`、`SEPARATION_REQUIRED_NOT_DONE`、"张口 143 mm = 2×行程"
  三项均已证伪。
- **accepted URDF 未污染**，停机条件未触发。
