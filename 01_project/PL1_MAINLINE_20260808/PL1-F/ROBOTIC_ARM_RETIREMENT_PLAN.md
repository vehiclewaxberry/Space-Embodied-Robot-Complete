# ROBOTIC_ARM_RETIREMENT_PLAN.md

- 任务：SEI-PL1-PROJECT-MAINLINE-RECONSTRUCTION / PL1-F（侦察与索引收口；不执行任何移动/删除）
- 对象根：`F:\Robotic arm`
- 日期：2026-08-08
- 裁决：**HOLD — 尚不可退役（NOT YET RETIREMENT_READY）**。2 项判据 PASS / 4 项 HOLD。完成 Stage 1–2（见证捕获 + 覆盖复验）并经人工处置授权后可转 RETIREMENT_READY。

---

## 1. 当前状态（实测）

| 组成 | 实测内容 | 文件数 | 备注 |
|---|---|---|---|
| `High_performance_robotics_arm\` (HPRA) | reBot B601-DM Windows 端项目主目录；本地 git，2 commits（`6dff06f` scaffold、`2d769d7` portable B601-DM URDF），**无 remote**，branch `main`；未跟踪目录：docs/stage1、external/、memory/ | 2,474（不含 .git） | README 自述"本仓库 = Windows 端项目主目录"；无顶层 LICENSE |
| `zero-robotic-arm\` | gitee.com/dearxie/zero-robotic-arm 克隆（remote 已验证），branch `research` @ c16b4be；GPL-2.0；**26 项 porcelain**：1 staged add（`.gitignore`）、24 modified CAD/BOM、1 untracked CAD（`frame0_ZERO_ARM.SLDPRT`） | 943（不含 .git），333 MB | 上游可重新获取 clean HEAD；本地 dirty witness 不可由上游重建 |
| `zero-robotic-arm.zip` | 同一 gitee 仓库打包快照（含 .git，1074 条目，256,786,387 B，2026-05-14） | 1 | 与上一行冗余 |

- HPRA 细分：`urdf\` 51 MB（2 个 URDF + 2 套 STL mesh）；`vendor\` 442 MB（reBot-DevArm 375 MB + reBotArmController_ROS2 67 MB）；`external\` 1.9 GB（birds / librecube_notes / oresat×3 / pycubed / spacerobotenv / spot）；`sim\`/`control\` 实质为空（.gitkeep + 1 个 README）；`cad\` 仅有 spacecraft_layout 空壳；`docs\stage1_spacecraft_layout\` 仅 2 文件。
- 治理登记状态：`PROJECT_LIBRARY_INDEX.yaml` retired_roots 行 "F:\Robotic arm （外部依赖已收回， 待整体处置）"；`PROJECT_START_HERE.md` §10 "外部依赖已收回；root 保留为 HOLD（不删除，不新建依赖）"。注意：**CANONICAL_ROOT_REGISTER.yaml 的 roots 清单中没有收录 F:\Robotic arm**（既非 L0–L6 也未列 deleted_roots）——登记口径不一致，本身是一个小的登记缺口（见 §5 NEW_CONTRADICTION-2）。

## 2. 运行时依赖 = 0 的验证证据（CLAIM VERIFIED）

方法：在 ROOT A 对可执行/配置扩展名（py/m/yaml/yml/json/xml/urdf/xacro/sh/bat/ps1/toml/ini/cfg/CMakeLists；排除 PL1 报告）检索 `F:[/\\]Robotic arm`，并对命中逐项判定是否会被当前执行链加载。PL1-G 恢复 contract/support 目录后，字符串命中从旧审计的少量历史文字增加为 **11 处**，但均属于观察记录、注释或 fail-closed 禁用断言，而不是运行时读取。

| 命中文件 | 性质 | 是否活动依赖 |
|---|---|---|
| `10_research/space_embodied_robotics/comp_prot_03_a4_design_review/a4_source_traceability.yaml`；`comp_prot_03_a0_a1/digital_robot_body_manifest.yaml`；`comp_prot_03_a2_candidate_model_review/candidate_configuration_v0.yaml`；`comp_prot_03_a3_geometry_only/asset_import_manifest_v0_1.yaml`（合计 7 处） | PL1-G 恢复的 `CONTRACT_ONLY_NOT_IMPLEMENTED` / `PRESENT_UNTRACKED_HASH_VERIFIED` 原型合同；字段名为 `observed_*` / `source_traceability` / `external_path`，没有执行 authority 或 machine Gate | 否（恢复的历史观察/合同记录；需后续文档卫生重指向） |
| `20_engineering/config/geometry/arm_b601_v1.yaml:10` | 活动 `hardware_step:` 已是仓内相对路径 `80_third_party/vendor/reBot-DevArm/...`；`F:/Robotic arm` 只出现在“was broken”注释中 | 否（已收回） |
| `20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/99_tools/m2_migration_acceptance.py:66,68` | 两个 `must_not_contain` 禁止模式，用于拒绝旧绝对路径 | 否（fail-closed 反向断言） |
| `20_engineering/design_review/SER_MECH_V3_0/MECH_ARCHITECTURE_RESET_01/mechanical_truth_map.yaml:227` | 冻结设计评审中的 donor 来源见证路径，不是当前 geometry/runtime 输入 | 否（历史证据字段；文档卫生待重指向） |
| `PROJECT_START_HERE.md` 与 `01_project/competition/archive/*.md` 的其他命中 | HOLD 声明及历史 HIL/审计叙述 | 否（治理/历史描述） |

结论：**活动运行时/构建依赖 = 0**，与“外部依赖已收回”一致；11 个可执行/配置扩展名命中均已逐项判为非运行时。PL1-G 恢复的合同 YAML 暴露了新的**文档/来源路径卫生**事项，但没有重新引入依赖。退役前后应把历史 donor/ROS2 指针重写为 ROOT A canonical 路径或 upstream URL（见移交事项）。

## 3. Donor 覆盖分析（主仓/参考库已覆盖什么）

| HPRA 资产 | 覆盖位置 | 验证方式 | 判定 |
|---|---|---|---|
| vendor/reBot-DevArm（工作树 177 文件） | ROOT A `80_third_party/vendor/reBot-DevArm`（177 文件） | 文件清单 comm 对比：仅 .git/* 不同；关键 STEP `reBot_B601_DM_v1.1_20260425.step` sha256 `87a0537d…` 双侧一致且与 HAGA 登记一致 | **完全重复** |
| B601 mesh（2 套 STL） | ROOT A `20_engineering/cad/spacecraft_layout/arm_b601_v1/meshes_b601_gripper/` | 抽样 sha256（base_link/gripper_left/gripper_link）一致 | **完全重复** |
| Accepted URDF 谱系 | ROOT A `…/arm_b601_v1/arm_b601_v1.urdf`（sha256 `1bc2b748…`，质量 4.695555949342986 kg，实测与使命登记一致） | 主仓现行权威 | 已覆盖（主仓为权威，HPRA 为上游工作区） |
| **2 个 URDF 变体**（fixend `065bc4f8…`、with_gripper `667a8905…`） | **无任何位置**（哈希与 accepted 不同） | sha256 实测 | **唯一见证，未归档** |
| **HPRA git 历史（2 commits，无 remote）** | **无任何位置**（commits 不在 ROOT A git：cat-file 验证不存在；ARCHIVE/GIT_LINEAGE 三个 bundle 均为主仓 bundle） | git 验证 | **唯一见证，未归档** |
| memory/local-machine-env.md、sim/free_floating_servicer/README_stage1.md | 无（小文本） | — | 唯一小见证，未归档 |
| docs/stage1_spacecraft_layout（2 文件） | ROOT A `20_engineering/stage1_spacecraft_layout/`（62 文件，含此 2 文件：comm -23 无缺失） | 文件清单对比 | 已覆盖 |
| vendor/reBotArmController_ROS2（67 MB） | ROOT A / ROOT B 无实体；ROOT B `OPEN_SOURCE_PROJECT_REGISTER.csv` 已安装外部元数据指针 | upstream commit `319100d3…`；license UNKNOWN HOLD | 上游公开仓库可重取；本地副本非唯一内容；退役后历史 HIL 文本应指向 upstream URL |
| external/spacecraft_layout_refs（6 组上游项目） | ROOT A `80_third_party/external/spacecraft_layout_refs` 具有完整对应树；ROOT B 已安装元数据索引 | 分组文件数/字节完全相等；8 个 embedded repo 双侧 clean 且 HEAD 相同（BIRDSX `36bcee`；OreSat `0e1550`/`af8f6f`/`4c0229`；PyCubed `d1adfd`/`72ab3a`；SpaceRobotEnv `155989c2`；SPOT `66a492`） | **完整重复**；无需再向 ROOT B 物理复制，随父根处置但须先完成见证/授权 |
| zero-robotic-arm（含 zip） | 无 ROOT A/ROOT B 实体；ROOT B 已安装项目与 MuJoCo 教学例元数据指针 | remote/HEAD 已验证；`5. Deep_LR` 14 文件全 tracked/clean；父工作树 26 项 porcelain；zip 与解包 clean lineage 同源 | 上游可重取 clean HEAD；26 项本地 CAD/BOM dirty diff 是**非平凡唯一见证**，必须完整 bundle/diff 后方可退役 |

汇总：**唯一且未归档**的有——HPRA git 历史（2 commits）、2 个 URDF 变体、memory/sim 小文本、zero-robotic-arm 26 项本地改动（含 CAD/BOM）。最后一项不是 trivial 文本差异，须保存完整 git bundle、staged/unstaged diff、未跟踪 CAD 与 SHA manifest。其余大件均为 ROOT A 重复或上游可重取。

## 4. 退役判据清单（依据 RETENTION_AND_DELETION_POLICY.md §4 硬条件 + 使命三条）

| # | 判据 | 状态 | 证据/缺口 |
|---|---|---|---|
| 1 | donor 覆盖（canonical/archive 等价物或可重建方法） | **HOLD** | 大件全部已覆盖或上游可重取（§3）；但 HPRA git 历史 + 2 URDF 变体 + 小文本见证尚无 canonical/archive 等价物 |
| 2 | 唯一见证已归档 | **HOLD** | ARCHIVE/GIT_LINEAGE 无主仓以外 bundle；需 Stage 1 捕获（git bundle + URDF 变体 + diff + sha256 manifest） |
| 3 | active refs = 0 | **PASS** | §2：grep 全仓 0 活动依赖；唯一 F:/ 路径引用已在 CM3 修复为仓内相对路径 |
| 4 | 非 KEEP / HIGH_RISK / UNKNOWN / MISSING | **PASS** | 已登记"待整体处置"/HOLD；无 KEEP 标注；内容已全部盘点（本侦察） |
| 5 | 删除前 bundle 保险已验证 | **HOLD** | 尚无任何 bundle/镜像；Stage 1–2 完成后转 PASS |
| 6 | 删除后独立验收 PASS | **HOLD** | 动作后事项（Stage 5–6） |

另注意治理级前提：永久删除属 RETENTION_AND_DELETION_POLICY **最高权限**动作，需人工显式授权 + FINAL_DELETE_MANIFEST + 独立验收；本计划不含执行。

## 5. NEW_CONTRADICTION（记录，不裁决）

- **NEW_CONTRADICTION-1（F3R1 物理位置，已解决）**：PL1-G 已从 `F:\_SEI_PROJECT_CONSOLIDATION_20260807\12_WAVE4\WORKTREE_RECONCILIATION\20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806` 救援 363/363 SHA-identical 文件到 ROOT A `20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\`，源保留。剩余风险改为 ROOT A 副本 untracked / 未 CM 接受 / 无冷备份，不再是物理缺失。
- **NEW_CONTRADICTION-2（登记缺口，低优先）**：`F:\Robotic arm` 不在 CANONICAL_ROOT_REGISTER.yaml 的 roots 或 deleted_roots 清单中，但出现在 PROJECT_LIBRARY_INDEX.yaml retired_roots 与 PROJECT_START_HERE.md §10。退役执行前应在规范根注册表补齐条目，避免"未登记根被删"的审计断点。

## 6. 分阶段计划（仅规划，NOW 不执行任何一步）

- **Stage 0（已事实生效）冻结**：不新建对 F:\Robotic arm 的依赖（PROJECT_START_HERE.md §10 已声明）。
- **Stage 1 见证捕获**：① `git bundle create` HPRA 全部历史（2 commits）与 zero-robotic-arm 的 `research` 分支，并捕获 staged/unstaged diff、未跟踪 `frame0_ZERO_ARM.SLDPRT` 与 26 项状态清单；② 复制 2 个 URDF 变体、memory/local-machine-env.md、sim README 到 `F:\SEI_PROJECT_ARCHIVE` 新增见证子目录（建议 `DESIGN_LINEAGE\ROBOTIC_ARM_WITNESS\`）；③ 生成全根 sha256 manifest。
- **Stage 2 覆盖复验**：ROOT B 的 external refs / zero-robotic-arm / reBotArmController_ROS2 元数据指针已于 2026-08-08 安装；剩余工作是按 manifest 重哈希并逐条签收 reBot-DevArm↔ROOT A、meshes↔ROOT A、external/spacecraft_layout_refs↔ROOT A 的完整覆盖与 dirty witness 可恢复性。
- **Stage 3 人工处置授权**：提交本计划 + manifest，取得人工显式授权（对齐 W4-D2 先例），并在 CANONICAL_ROOT_REGISTER 补登该根。
- **Stage 4 隔离（可恢复 move）**：整体移入 QUARANTINE 区（不删除）。
- **Stage 5 冷重开 + 独立验收**：验证主仓/参考库在无 F:\Robotic arm 状态下完整可用（健康检查 PROJECT_ROOT_HEALTH_CHECK PASS + URDF/mesh 哈希复验）。
- **Stage 6 永久删除**：满足 §4 全部硬条件后按策略最高权限流程执行，FINAL_DELETE_MANIFEST 归档。

## 7. 移交事项（退役前后需同步的小改动）

- HIL 路线文档中 "F:/Robotic arm 的 ROS2 侧" 指针 → 改为上游 URL（Seeed-Projects/reBotArmController_ROS2）。
- ROOT B 索引指针（CAD-D03 组、CAD-D04、CAD-D06 / zero-arm MuJoCo）已安装；CAD-D10/D11 两个 license-unknown CAE 小几何仍仅为可选拷贝，未执行实体复制。
- PROJECT_START_HERE.md §10 的 F:\Robotic arm 行在 Stage 6 后移至"已删除 roots"。
