# FREECAD_LINEAGE_NOTES.md

- 任务：SEI-PL1-PROJECT-MAINLINE-RECONSTRUCTION / PL1-F（谱系与索引收口；不移动/删除资产）
- 主题：FreeCAD 权威子集/参考层 vs 当前原生机械候选 vs HAG donor vs 已退役 FreeCAD roots 的谱系
- 日期：2026-08-08
- 一句话结论：**`20_engineering/cad/freecad_authoritative/` 是 C1-A、git 跟踪的 FreeCAD 权威子集/参数化参考层，不是当前 L1 原生顶层；当前机器选择的机械候选是 F3R2 operational package（F3R1-V3 原生字节 + F3R2 定义/姿态/数字线程），仍 `PENDING_HUMAN_REVIEW`。HAGA_HIFI_FREECAD 是视觉 donor（C1-B，NOT_CURRENT_TOP）。三者角色正交，未发现双权威冲突。**

---

## 1. 当前（CURRENT）

### 1.1 C1-A FreeCAD authoritative — 权威子集/参数化参考层（非当前原生顶层）
- 路径：`F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\freecad_authoritative\`
- 实测：36 文件 / 9.5 MB，平铺布局。`ASSET_AUTHORITY_MATRIX.csv` 行：`C1_A_FREECAD_AUTHORITATIVE, IMPORTED_TRUTH, Wave3 36项, hash-verified, TRACKED_IN_GIT`。
- 内容（实测 ls）：`B51R1_MASTER_SKELETON_FREECAD.FCStd`（44 参数 + 13 datum，零实体）；`B601_CARRIER_*.FCStd`×10（DATUM_ONLY_NO_MASS）；`B601_KINEMATIC_ASSEMBLY.FCStd`（F1_PASS）+ 5 个状态 witness STEP（Q0/STOWED/SERVICE/PARTIAL/DEPLOYED_NOMINAL）；`B601_BASE_ADAPTER(.FCStd/.step/_DRAWING/_FEM)`（F2_PASS 试点，AL6061-T6 1.0395 kg 标注 DESIGN_ESTIMATE_ONLY_EXCLUDED）；SSOT 参数 CSV/YAML、`B601_STRUCTURE_TREE.yaml`、`JOINT_INTERFACE_CONTROL_DOCUMENTS.yaml`、`joint_states.yaml`、`F3_BOM_PLAN.csv`、`F3_PARAMETER_REGISTER_DELTA.csv`、`FREECAD_MASS_REGISTER.yaml`。
- 工具链裁定：FreeCAD **1.1.3 pinned**（`FREECAD_CAD_TOOLCHAIN_HUMAN_OVERRIDE_20260803.yaml`；文本锁 1.1.1 vs 实装 1.1.3 → 负责人裁定 ACCEPT_1.1.3_AS_PINNED，禁再变动、禁 weekly）。

### 1.2 L0 运动学/质量权威（配套）
- Accepted URDF：`20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`，实测 sha256 `1bc2b7483cd8025d…`（raw）——与权威登记一致；质量 4.695555949342986 kg；normalized `408147dd…`（登记值，未重算）。
- 几何 SSOT：`20_engineering/config/geometry/arm_b601_v1.yaml`（hardware_step 已 repo-relative，CM3）。
- 注意路径漂移（登记滞后）：`FREECAD_FREECAD_AUTHORITY_REGISTER.yaml`（2026-08-04）记的路径是迁移工作区布局——`00_authority/input_bundle/urdf/...`、`01_skeleton/`、`02_carriers/`、`04_assemblies/`、`09_scripts/`；Wave3 收口后实体平铺落入 `freecad_authoritative/`，URDF 落入 `spacecraft_layout/arm_b601_v1/`。`PROJECT_START_HERE.md` 已在 2026-08-08 重指向实体路径；旧 `20_engineering/cad/B5_1R1_.../00_BASELINE/AUTHORITIES/accepted_urdf/...` 仅残留在 CM SSOT 的 `PROJECT_LIBRARY_INDEX` / `ASSET_AUTHORITY_MATRIX` 路径字段，需人裁后治理更新。

### 1.3 尚未关闭的人裁事项（来自权威登记，原样转录）
- STOW_Z_LIMIT: UNKNOWN；T_SM dual-track: 185.25 vs 198（O3，待人裁）；H9_mode: MODE_A/MODE_B 双保留；O13_saddles: CANDIDATE_HOLD。

## 2. Donor（在主仓内但 ≠ CURRENT）

### C1-B HAGA_HIFI_FREECAD — HiFi 视觉 donor
- 路径：`20_engineering/cad/reference_donors/HAGA_HIFI_FREECAD\`；实测 21 文件 / 168 MB，git 跟踪。
- 内容：B601 逐连杆 HiFi 视觉 FCStd（base_link、link1–6、gripper×3，含 FCBak）+ `F3_P3_TOP_ASSEMBLY.FCStd`（43.9 MB）+ `SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3.FCStd`。
- 登记角色：`C1_B_HIFI_DONOR, LINEAGE_DONOR, NOT_CURRENT_TOP`（ASSET_AUTHORITY_MATRIX）。
- 来源链：vendor HiFi STEP `reBot_B601_DM_v1.1_20260425.step`（sha256 `87a0537d…`，CERN-OHL-W-2.0，HAGA 权威输入登记 ZERO_MODIFICATION）→ HAG_A 工作区（已删）→ Wave3 收口入主仓。权威登记中其角色为 GEOMETRY_REFERENCE_ONLY（"interactive import only; NOT auto-processed"）。
- 用途边界：视觉/包络/比对 donor；不得作为结构真值、不得覆盖 URDF 质量。F3R2 已于 2026-08-07 执行，未以它作为原生修复输入；未来视觉/出图工作可继续只读引用。

## 3. 已退役 / 被取代（SUPERSEDED / RETIRED）

| 根/目录 | 状态 | 证据 |
|---|---|---|
| `F:\Space-Embedded-Robot-Complete_FREECAD_MIGRATION_20260803` | **已删除**（CM3-D） | CANONICAL_ROOT_REGISTER deleted_roots / PROJECT_LIBRARY_INDEX retired_roots；F0–F2 报告与 132 项清单已归档（DESIGN_LINEAGE） |
| `F:\Space-Embodied-Robot-HAG_A_20260804` | **已删除** | 同上；HAGA 66 份证据已归档 |
| 主仓内旧 CAD 目录：`20_engineering/cad/B5_0_B601_space_manipulator_candidate`、`B5_1R1_B601_interface_native_rework_candidate`、`Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION`、`F3_manufacturing_arm`、`F3_MANUFACTURING_GRADE_DESIGN` | **已从主仓工作树迁出**（Wave4 reconcile，commit `cd0ea80` "preserve verified pre-Wave4 active worktree assets"）；现仅存于 L5 临时区 `…\12_WAVE4\WORKTREE_RECONCILIATION\`（实测 find：ROOT A 中无这些目录） | MIGRATION_SOURCE_REGISTER（14 项 raw+LF 双哈希）证明其权威件已抽提到 `00_authority`/现行落点；V2_3 顶层 SLDASM 曾记 HASH_DRIFT_VS_PHASE0（仅基线哈希用途） |
| SolidWorks 原生旧线（V2_3 等） | L3 `FROZEN_LEGACY_EVIDENCE_AND_DONOR`：冻结遗产/供体，禁双向编辑，FreeCAD gate 过了的件逐件取代 | FREECAD_FREECAD_AUTHORITY_REGISTER.yaml L3 层 |
| F3R1 SolidWorks 原生集成（`20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806`，363 文件） | **实体位置已解决**：PL1-G 从 L5 保留源救援至 ROOT A，363/363 SHA 相同；当前为 F3R2 前身证据，不是 current candidate | ROOT A 副本仍 untracked / 未 CM 接受 / 无冷备份；L5 源保留至接受完成 |

## 4. 谱系时间线（证据锚点）

1. 上游：Seeed reBot-DevArm（CERN-OHL-W-2.0）→ 本地工作仓 HPRA（`F:\Robotic arm\High_performance_robotics_arm`，commits `6dff06f`/`2d769d7`，产出 portable URDF 与 mesh）。
2. B5.0/B5.1R1 接口返工（SolidWorks 原生，主仓旧目录）→ accepted URDF 定版（raw `1bc2b748…`）。
3. 2026-08-03→04：FreeCAD 迁移工作区 F0/F1/F2 三 gate 全 PASS（`FREECAD_FREECAD_MIGRATION_F0_F2_REPORT.md`：骨架 9/9、10 carrier、独立 FK 五状态 <1e-6 mm、适配器 12/12、CalculiX 单位载荷可复现）。
4. 2026-08-04→05：HAG_A HiFi donor 加工（F3_P1–P4 gate、frame mapping、handedness、link ownership 证据组）。
5. 2026-08-07 Wave3/CM：C1 资产抽提入主仓现行位置（commit `e14b224`），旧目录迁 L5（commit `cd0ea80`），vendor 与断链修复（commit `5849b72`），入口文档（commit `5c5adde`）。ASSET_AUTHORITY_MATRIX 定版 C1-A/C1-B 角色。
6. 2026-08-07→08：F3R2 已执行（最终 gate 11/14，4 HOLD，`PENDING_HUMAN_REVIEW`）；PL1-G 随后把 F3R1 363/363 与 F3R2 482/482 SHA-identically 救援回 ROOT A，L5 源保留。当前原生机械候选因此是 F3R2，而不是 C1-A FreeCAD 子集。

## 5. 证据清单（可复核）

- `F:\SEI_PROJECT_ARCHIVE\DESIGN_LINEAGE\`：FREECAD_* 20 份（F0/F1/F2/F3_P0 gate JSON、AUTHORITY_REGISTER、MASS_REGISTER、MIGRATION_F0_F2_REPORT、TOOLCHAIN_CHECK 结果、MIGRATION_SOURCE_REGISTER、SOURCE_REPOSITORY_NON_MODIFICATION_REPORT、FREECAD_WITNESS\ 下 8 个 witness STEP + smoke 测试）+ HAGA_* 66 份（gate/报告/映射/日志/脚本）。
- `F:\SEI_PROJECT_ARCHIVE\CONFIGURATION_MANAGEMENT\20260807_CONSOLIDATION\ASSET_AUTHORITY_MATRIX.csv`：C1_A / C1_B / DESIGN_LINEAGE / DELETED_HAGA_F4INT 行。
- `F:\SEI_PROJECT_ARCHIVE\GIT_LINEAGE\`：主仓三个 git bundle（不含 HPRA——见退役计划判据 2）。
- 主仓实测：freecad_authoritative 36 文件、HAGA_HIFI_FREECAD 21 文件、spacecraft_layout 40 文件（含 URDF+mesh+5 个布局体 v0）。

## 6. F3R2 已执行后的边界（仅陈述，不启动新 CAD 工作）

- F3R2 已于 2026-08-07 执行；`03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM` 与 F3R1 V3 字节相同（sha256 `19D85E9C…B590D0`），F3R2 增加定义、姿态、间隙与数字线程证据。它是 `CURRENT_MACHINE_SELECTED_MECHANICAL_CANDIDATE`，不是人类批准的 baseline（gate 11/14、4 HOLD、`PENDING_HUMAN_REVIEW`）。
- F3R1 物理位置矛盾已通过 363/363 SHA-identical 救援关闭；剩余的是 ROOT A untracked、未 CM 接受、无冷备份。`freecad_authoritative` 与 HAGA donor 均保持只读，不得覆盖 F3R2 原生候选或 accepted URDF。
- CAE 库（L4）仍是“独立学习库，不参与比赛真值判定，不并入主仓”；CAD-D10/D11 仅为 license-unknown 的可选小几何索引/拷贝候选，不得向 F3R2 取数。
