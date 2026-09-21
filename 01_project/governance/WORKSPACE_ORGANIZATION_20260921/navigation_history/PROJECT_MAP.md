# 项目总导航

更新日期：2026-09-21。本页负责工作入口、目录职责与历史范围；工程和科学结论仍以对应源文件及机器裁决为准。

当前工作围绕可装配、可参数化、可验证的服务星与 B601 机械设计，并保留论文复现所需的模型、输入和负结果。既有比赛截止日期不再决定当前机械工作的进度。

## 从这里开始

| 工作 | 入口 | 使用范围 |
|---|---|---|
| 查看当前硬件精简设计 | [硬件设计包](./20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/README.md) | 以R6H后续集成总装为机械入口，电气线束、能源热控和推进主文件独立整理；原件保留 |
| 查看上游完整机械基线 | [WP03 设计包](./20_engineering/service_robot_wp03_spacecraft_body_r1/README.md) | 完整 B601、星体、双翼、随星保持器与设备接口的上游来源；不替代当前R6H |
| 接续机械装配与整改 | [装配程序](./20_engineering/service_robot_wp03_spacecraft_body_r1/ASSEMBLY_SEQUENCE.md)、[集成报告](./20_engineering/service_robot_wp03_spacecraft_body_r1/INTEGRATION_REPORT.md) | 区分已建几何、已有检查及待完成的选型、连接与实物试验 |
| 查看本轮整理与后续动作 | [CURRENT_candidate 工作入口](./01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/CURRENT_candidate.md) | 全项目整理和机械接续的会话入口；执行范围及结果以该入口与账本为准 |
| 检索文件、依赖、审阅和备份 | [统一 SQLite 目录](./01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/loop0_20260905/screening/full_project_catalog.sqlite) | 文件目录及压缩快照，不替代原始工程证据 |
| 查阅跨域治理记录 | [current 治理入口](./01_project/current/README_CURRENT.md)、[发布指针](./01_project/current/CURRENT_RELEASE_POINTERS_V1.yaml) | 按其声明日期、对象和范围使用，文件名 CURRENT 本身不构成更新或工程合格证明 |

## 八个业务域

| 目录 | 职责 | 域入口 |
|---|---|---|
| [01_project/](./01_project/) | 项目治理、人工输入、协作、比赛历史及整理记录 | [README](./01_project/README.md) |
| [10_research/](./10_research/) | 研究问题、架构、论文与知识导航 | [README](./10_research/README.md) |
| [20_engineering/](./20_engineering/) | CAD、参数、接口、BOM 与机械系统设计 | [README](./20_engineering/README.md) |
| [30_simulation/](./30_simulation/) | 动力学、控制、安全与模块验证记录 | [README](./30_simulation/README.md) |
| [40_evidence/](./40_evidence/) | 图表、媒体、展示与证据快照 | [README](./40_evidence/README.md) |
| [50_literature/](./50_literature/) | 文献题录、原文、阅读卡与引用证据 | [README](./50_literature/README.md) |
| [70_tools/](./70_tools/) | 项目工具、索引、看板与可视化程序 | [README](./70_tools/README.md) |
| [80_third_party/](./80_third_party/) | 第三方代码、厂家来源与许可 | [README](./80_third_party/README.md) |

新增业务资产按职责进入上述域。根层保留导航与 Git/Agent/工具配置；现存非标准目录的处理与路径映射记入本轮账本，不根据目录名推定其已迁移或可删除。

## WP03 与 R2 分别查阅

**WP03 是保留的上游完整机械候选，当前硬件总装以 [R6H指针](./20_engineering/SERVICE_STAR_CORE_INSTALLATION_LATEST.json)为准。** WP03的[设计参数](./20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json)、[几何检查](./20_engineering/service_robot_wp03_spacecraft_body_r1/results/GEOMETRY_CHECK.json)、[路径检查](./20_engineering/service_robot_wp03_spacecraft_body_r1/results/INTEGRATE_CHECKS.json)和[质量惯量摘要](./20_engineering/service_robot_wp03_spacecraft_body_r1/results/DYNAMICS_SUMMARY_ZH.md)分别声明原对象与范围。静态非臂检查不覆盖完整连续动作；已分配数字质量不等于实测完整飞行质量。

**R2 原机器结论独立保留。** [MECHANICAL_ENGINEERING_RELEASE_R2](./20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/)的[原终裁](./20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json)记录 Gate A 未通过、内部阻断已登记及无发布信用，`review_status=PENDING_OWNER_REVIEW`、`next_stage_authorized=false`。这些结论属于该 R2 发布包，不因 WP03 或文件整理而改写，也不自动转移到另一构型。

WP03 实际读取的 [WP01](./20_engineering/service_robot_wp01_20260905/)和[WP02](./20_engineering/service_robot_wp02_20260905/)仍有上游依赖职责。旧 30 mm 释放失败、源拓扑缺陷、厂家来源和冻结输入按自身证据身份保留与使用，不能按日期或相似名称判为无用。

## 研究与协作

- [研究知识入口](./10_research/knowledge_base/README.md)用于查找现有证据；[文献主清单](./50_literature/references/manifest.yaml)用于定位论文来源。
- 仿真与控制结论回到各模块原始裁决和声明工况。整理目录、生成展示或重建文件本身不新增科学结论。
- [AGENTS.md](./AGENTS.md)和[CLAUDE.md](./CLAUDE.md)保留客户端协作约定；历史阶段状态应结合日期、对象与最新用户任务理解。

## 历史内容已合并，旧文件已移出根目录

| 内容 | 现在的位置 | 本轮实际处理 |
|---|---|---|
| 旧启动指南、状态总结与入驻说明 | [历史综述](./01_project/competition/archive/ROOT_HISTORY_20260729_20260810.md) | 17 份 Markdown 合为一份，原文件已删除；保留源到段落映射 |
| 原 knowledge 两份方法笔记 | [结构与仿真资产方法](./10_research/knowledge_base/spacecraft_mechanical_design/legacy_structure_methods_20260728.md) | 两份合为一份，原文件已删除 |
| 原 structure 的合同和结构说明 | [结构历史材料](./20_engineering/system_design/legacy_root_structure/) | 8 件独有文件原字节归档 |
| 根级 F3R2 脚本 | [历史工具目录](./70_tools/legacy_f3r2_root_scripts/) | 9 个 Python 与 1 个 PowerShell 移入工具域；消费路径已修正 |
| 原 90_competition_closeout | [历史收尾记录](./01_project/competition/archive/90_competition_closeout/) | 55 件记录保留原字节 |
| 入驻包独有图示与 JSON | [2026-07-29 入驻快照](./01_project/competition/archive/onboarding_20260729/) | 3 件保留归档 |
| 根 B51 压缩包与展开副本 | [规范授权来源](./20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/00_BASELINE/AUTHORIZATION_PACKAGE/) | 删除根部重复 ZIP 及 3 份展开副本，验证程序读取保留副本 |
| 旧模型优先级 YAML | [2026-08-08 历史快照](./01_project/current/archive/PROJECT_MODEL_TRUTH_HIERARCHY_20260808.yaml) | 原值不变，旧消费者按归档路径读取 |

根目录现在保留八个业务域、必要的 Git/客户端配置，以及 PROJECT_MAP、AGENTS、CLAUDE 三份 Markdown。此次根部整理没有重跑或升级 CAD、仿真与科学裁决。

详细原路径→新位置、删除动作与修改前原件保存在同一 SQLite：`root_layout_actions`、`reviews`、`snapshots`；恢复阶段为 `BEFORE_ROOT_PHYSICAL_CONSOLIDATION_20260906`。旧冻结记录仍声明当时的路径与哈希；它们不会因本次路径变更自动变成新版验证结果。

## 八域内部整理（2026-09-06）

已将 31 份重复说明归并、删除 2 份同字节报告与 159 个已核实可再生字节码，原始字节可恢复；本轮共删除 192 文件，新增 2 份合并文。各域现用入口见上表，详细合并去向、检查及未完成范围见 [整理工作入口](./01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/CURRENT_candidate.md)。

可访问文件均有处置记录；原生内容与未精读正文仍明确保留待审阅。12 个已空缓存目录被自动审批拒绝删除，未计入已清理目录。
