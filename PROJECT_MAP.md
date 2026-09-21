# 航天服务星具身智能机械臂机器人 · 项目总导航

更新：2026-09-21。项目英文名称：Space Service Robot with Embodied Intelligence。项目按长期硬件研发推进，比赛期限不作为工程验收门槛。本页负责文件用途和入口；工程与科学结论仍以各包的原始裁决为准。

**全项目归档导航：[可搜索目录总览](01_project/governance/WORKSPACE_ORGANIZATION_20260921/WORKSPACE_INDEX.html) · [整理结果与规则](01_project/governance/WORKSPACE_ORGANIZATION_20260921/README.md)。** 原始来源与历史证据多数按用途归档、原位保存，避免破坏引用。

## 日常从这里进入

| 要做的事 | 入口 | 对象与范围 |
|---|---|---|
| 查看四系统硬件主设计 | [硬件精简设计包](20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/README.md) | 机械、电气线束、能源热控、动力推进；当前候选与未完成项均有说明 |
| 打开后续机械臂—服务星总装 | [R6H原总装](20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/native/SERVICE_STAR_SERVICE_R6H.SLDASM)、[可移植副本](20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/01_mechanical/native/SERVICE_STAR_SERVICE_R6H.SLDASM) | 原件保留；没有回退为早期WP03 |
| 接续电气与安装设计 | [R5E电气指针](20_engineering/SERVICE_STAR_ELECTRICAL_LATEST.json)、[R7布局草案](20_engineering/SERVICE_STAR_AUX_STOP_INSTALLATION_R7_20260921/) | 选型候选和未安装草案分别看待，不按日期推定完工 |
| 查上游机械来源 | [WP03](20_engineering/service_robot_wp03_spacecraft_body_r1/README.md)、[工程域](20_engineering/README.md) | WP01/02、R1/R4等仍有消费者；旧目录不是可批量删除清单 |
| 找研究问题与知识 | [研究域](10_research/README.md) | 主题、合同、论文和知识导航 |
| 找计算程序与原始结果 | [仿真域](30_simulation/README.md) | 按模块保留源码、测试、结果和Gate；不集中搬走结果 |
| 找文献和图表 | [文献域](50_literature/README.md)、[展示证据域](40_evidence/README.md) | 全文、阅读卡、题录及生成图表各有用途 |
| 查历史来源或恢复记录 | [治理入口](01_project/README.md)、[本轮归档账本](01_project/governance/WORKSPACE_ORGANIZATION_20260921/README.md) | 物理移动/删除与逻辑分类分开记录 |

## 八个业务域

| 目录 | 保存什么 | 怎样归档 |
|---|---|---|
| [01_project](01_project/README.md) | 项目入口、治理、协作原件与历次工作记录 | competition是沿用的历史名称，其中不少仍是工程来源；按工作包与日期索引 |
| [10_research](10_research/README.md) | 研究主题、方法、合同、知识与论文材料 | 按主题导航，旧阶段计划保留日期 |
| [20_engineering](20_engineering/README.md) | CAD、电气、BOM、参数、接口和设计证据 | 现行设计、上游依赖、历史验证分栏；保持原生引用 |
| [30_simulation](30_simulation/README.md) | 模型、程序、测试、结果、机器裁决 | 模块自包含，保留失败和UNKNOWN |
| [40_evidence](40_evidence/README.md) | 图表、媒体和离线展示 | 原始证据与纯复制展示件区分；可证明的重复件指回规范源 |
| [50_literature](50_literature/README.md) | 题录、阅读卡、BibTeX与全文 | manifest导航；全文与阅读卡不互相替代 |
| [70_tools](70_tools/README.md) | 编目、展示、校验工具及运行环境 | 工具源码、运行时、可再生缓存分开处理 |
| [80_third_party](80_third_party/README.md) | 外部代码、厂家模型与许可 | 保留来源版本、许可、消费者和独立历史 |

## 根配置与保存规则

- `.git`保存版本与LFS对象；`.codex/.agents/.claude`为客户端配置。它们不属于可随意去重的设计副本。
- `AGENTS.md`、`CLAUDE.md`保留客户端工作约定；本页保持唯一全项目根导航，不再建立平行src/docs/results业务树。
- 停用的根MCP配置已原字节移入本地私有档案；活跃配置没有修改。见[归档映射](01_project/governance/WORKSPACE_ORGANIZATION_20260921/ROOT_ARCHIVE_ACTIONS.json)。
- 同名、同日期或位于archive/_work/__cadgen__都不足以证明文件无用。实际清理只认精确候选、可恢复来源与引用核验。
- 本轮导航更新前的说明已原字节保存于[导航历史](01_project/governance/WORKSPACE_ORGANIZATION_20260921/navigation_history/)。历史文中的相对路径仍按其原目录解释。
