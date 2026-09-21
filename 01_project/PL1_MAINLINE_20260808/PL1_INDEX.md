# PL1_INDEX.md — PL1 主线重建总索引

- **Task**: SEI-PL1-PROJECT-MAINLINE-RECONSTRUCTION · **Date**: 2026-08-08 · **Created by**: PL1-G (consolidation planner)
- **Scope**: ROOT A `F:\China Graduate Future Flight Vehicle Innovation Competition` (HEAD `5c5adde`) · ROOT B `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY` · ARCHIVE `F:\SEI_PROJECT_ARCHIVE` (bound to A)
- **Reading order**: `PROJECT_START_HERE.md` → `SEI_PROJECT_MAINLINE_MAP.md` → `PROJECT_CURRENT_STATUS.md` → (机械域) `MECHANICAL_START_HERE.md` → 需要的 PL1-* 专图。

| 总图 | 一句话 |
|---|---|
| `SEI_PROJECT_MAINLINE_MAP.md` | M0–M14 系统工程主线；每一 M 均列 authority/files/status/result/superseded/holds/next task |

## PL1-A — 项目边界（boundary closed, UNKNOWN=0）

| 文件 | 一句话 |
|---|---|
| `PL1-A\PL1_PROJECT_ASSET_DISCOVERY.csv` | F:\ 全部 39 个顶层条目逐一分类/实测（文件数、大小、git、归类） |
| `PL1-A\SEI_PROJECT_RELEVANCE_BOUNDARY.yaml` | 边界定版：3 包含根 + 5 临时兼容根 + 外部工具 + 19 排除 + 3 退役候选；UNKNOWN=0 |
| `PL1-A\PROJECT_BOUNDARY_REPORT.md` | HEAD 实测 5c5adde；root-level UNKNOWN=0；结构健康项全 PASS，当前只因 dirty worktree 为 FAIL 1 |

## PL1-B — 机械主线

| 文件 | 一句话 |
|---|---|
| `PL1-B\MECHANICAL_ENGINEERING_MAINLINE.md` | 21 环节逐环裁决（权威/状态/被取代/挂起）+ 长期禁令 |
| `PL1-B\MECHANICAL_CONFIGURATION_LINEAGE.md` | CAD v0→F3R2 全谱系代表（每代 gate/verdict/后继） |
| `PL1-B\CURRENT_MECHANICAL_BASELINE_RULING.md` | 唯一机器选定候选 = F3R2 代（URDF L0 + F3R1-V3 字节 L1）；待人审、CM/备份/reference HOLD |
| `PL1-B\MECHANICAL_CURRENT_STATUS.md` | 机械域逐条状态板（DONE/ACTIVE/HOLD/NOT_STARTED） |
| `PL1-B\MECHANICAL_MODEL_MAP.md` | URDF→骨架→工程 CAD→总装→碰撞→仿真→SAFE-00 一页图（mermaid） |
| `PL1-B\F3R2_EXECUTION_ORDER.md` | F3R2 残余执行顺序 P0（人审+已复制内容的 CM/备份/reference 收口+WING_ROOT_LUG）→P1→P2 |
| `PL1-B\B601_DIGITAL_THREAD_MAP.yaml` | L0–L3 数字线程全图（hash/路径/姿态/定义/证据/断点） |

## PL1-C — 动力学/仿真主线

| 文件 | 一句话 |
|---|---|
| `PL1-C\DYNAMICS_MAINLINE.md` | M5 动力学（sim_11 v1.1 权威）/ M6 捕获链 / M9 外部引擎（reference checkout 存在、项目集成为零）三线裁决 |
| `PL1-C\DYNAMICS_SIMULATION_ASSET_REGISTER.csv` | 52 项仿真资产台账（verdict/配置/hash/依赖；ROOT B、SpaceRobotEnv 与 CAE 含内） |
| `PL1-C\SIMULATION_TRUTH_HIERARCHY.md` | Tier0–6 真值层级 + ROOT B 零运行时依赖验证 + NC-01/02 |

## PL1-D — 参考库（ROOT B）

| 文件 | 一句话 |
|---|---|
| `PL1-D\OPEN_SOURCE_PROJECT_REGISTER.csv` | 27 行开源项目台账（上游/commit/许可/verdict；全部 runtime_dependency=false；8 项许可 HOLD） |
| `PL1-D\REFERENCE_LIBRARY_ARCHITECTURE.md` | R1–R7 逻辑 overlay 设计（零物理移动）+ 物理怪癖清单 |
| `PL1-D\REFERENCE_TO_PROJECT_MAPPING.csv` | ROOT B↔ROOT A 映射（零运行时引用实测；vendor 重复/偏斜登记） |
| `PL1-D\REFERENCE_LIBRARY_START_HERE.md` | 库入口文档草稿（已由 PL1-G 安装为库根正式入口） |

## PL1-E — 控制 / 安全 / 具身智能 / 演示 / 论文

| 文件 | 一句话 |
|---|---|
| `PL1-E\INTELLIGENCE_CONTROL_MAINLINE.md` | M7 控制+SAFE-00 / M8 具身（规划态）/ M12 演示 DONE / M13 论文 ACTIVE |
| `PL1-E\SAFE00_DIGITAL_THREAD.md` | SAFE-00 输入→9 步裁决→输出全线程（hash 绑定、16 案例、T1–T7 断点表） |
| `PL1-E\INTELLIGENCE_ASSET_REGISTER.csv` | 29 项控制/安全/演示/论文资产台账 |

## PL1-F — CAD 供体 / 退役 / FreeCAD 谱系

| 文件 | 一句话 |
|---|---|
| `PL1-F\CAD_DONOR_REGISTER.csv` | CAD-D01..D15 供体/谱系台账（覆盖/唯一见证/处置建议；donor ≠ current） |
| `PL1-F\CAE_PROJECT_RELEVANCE_REGISTER.csv` | CAE 库 30 项：26 index_only / 2 exclude / 2 optional copy_to_B |
| `PL1-F\ROBOTIC_ARM_RETIREMENT_PLAN.md` | `F:\Robotic arm` 裁决 HOLD（3 PASS/3 HOLD）+ Stage 1–6 退役路线 |
| `PL1-F\FREECAD_LINEAGE_NOTES.md` | FreeCAD 线收口：C1-A 当前权威 / C1-B 视觉供体 / 退役根证据 |

## PL1-G — 整合（本目录）+ SSOT 落地

| 文件 | 一句话 |
|---|---|
| `PL1-G\SALVAGE_COPY_MANIFEST.md` | 抢救清单：F3R1 363 + F3R2 482 + 15 个唯一目录 364 = 1,209 文件 ≈1.63 GB，sha256 全等；源区未动 |
| `PL1-G\manifests\` | 逐文件 sha256 清单 ×6（F3R1/F3R2/EXTRAS 各 source+dest） |
| `PL1-G\TWO_ROOT_CONSOLIDATION_MATRIX.csv` | 全部 SEI 相关资产/根归类（六类归属 × action × risk × 证据；UNKNOWN=0） |
| `PL1-G\ROOT_A_CANONICAL_STRUCTURE_PLAN.md` | 逻辑域→现有路径映射（不重编号；HIL/DATASET=NOT_STARTED 明示） |
| `PL1-G\ROOT_B_LIBRARY_STRUCTURE_PLAN.md` | R1–R7 索引 overlay 定版 + 库 HOLD 清单 |
| `PL1-G\ARCHIVE_INTO_ROOT_A_MIGRATION_PLAN.md` | 归档绑定 ROOT A：phase 0 指针（已完成）/ phase 1 依赖审计 / phase 2 可选物理迁移 |
| `PL1-G\TWO_ROOT_EXECUTION_PLAN.md` | Stage 0（已完成）→ Stage 1 低风险文档 → Stage 2 见证捕获 → Stage 3 CAD 依赖岛 → Stage 4 退役；copy-verify 协议 |
| `PL1-G\NEW_CONTRADICTION_REGISTER.md` | 全六路矛盾合并；已执行项与剩余工程/CM/DR/许可 HOLD 分开记录，禁止静默改写历史 |

## PL1-V — 独立复核

| 文件 | 一句话 |
|---|---|
| `PL1-V\validate_pl1.py` | 只读机器复核：格式、边界、hash、Root B 同步、runtime=0、健康检查与 M0–M14 完整性 |
| `PL1-V\PL1_INDEPENDENT_REVIEW.md` | PL1-G0..G12 独立 Gate 与最终 `PL1_COMPLETE_WITH_EXPLICIT_ENGINEERING_HOLDS` 裁定 |

**ROOT A 根目录 SSOT（PL1-G 2026-08-08 落地/更新）**：`PROJECT_START_HERE.md`（修正 HEAD/§3/§4/§5/§8/§11/§12 + PL1 指针）· `PROJECT_CURRENT_STATUS.md`（十域当前状态板，新建）· `MECHANICAL_START_HERE.md`（机械入口，新建）· `PROJECT_MODEL_TRUTH_HIERARCHY.yaml`（分域权威真值，新建）。
**ROOT B 根目录（PL1-G 安装）**：`REFERENCE_LIBRARY_START_HERE.md` + `OPEN_SOURCE_PROJECT_REGISTER.csv` + `DYNAMICS_SIMULATION_LIBRARY_INDEX.csv` + `CAD_DONOR_REGISTER.csv`。
