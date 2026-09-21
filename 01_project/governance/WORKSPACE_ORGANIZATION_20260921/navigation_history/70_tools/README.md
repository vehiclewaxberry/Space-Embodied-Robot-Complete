# 项目整理、研究环境与展示工具

导航整理：2026-09-06。本域保存非业务结论型工具；工具运行记录与原始科学、工程结论分开。

- [全项目文件目录工具](mechanical_asset_index/scan_service_robot_assets.py)：使用 `--full-project` 转入[静态目录解析器](mechanical_asset_index/full_project_catalog.py)，登记文件、依赖、阅读范围与整理处置。
- [统一目录数据库](../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/loop0_20260905/screening/full_project_catalog.sqlite)：保存本轮目录、阅读记录、逐文件审阅、操作及压缩前件备份；[会话入口](../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/CURRENT_candidate.md)。
- [来源索引构建器](current_authority_index/README.md)：生成 R2 等既有来源的派生导航。
- [研究仪表板](research_dashboard/README.md)与[可视化源码](project_visualization/src/)：构建离线展示，不新增科学结论。
- [科研环境说明](research_env/README.md)：工具链的有日期记录，软件能力及安装情况按实际环境核实。

在项目根目录运行全项目静态编目，或读取已存摘要：

```powershell
python -B 70_tools/mechanical_asset_index/scan_service_robot_assets.py --full-project
python -B 70_tools/mechanical_asset_index/scan_service_robot_assets.py --full-project --summary
```

这些入口不执行仿真或 CAD 生成。文件整理的操作范围和结果由本轮会话及数据库记录，不由旧索引中的删除候选数量决定。

- [根级 F3R2 历史脚本](legacy_f3r2_root_scripts/)已归入本域；它们与发布包 99_tools 的同名版本不同，固定输入哈希保留。旧辅助模块缺失仍是已知历史问题。
- [本次根目录合并工具](mechanical_asset_index/consolidate_root_layout.py)与 SQLite `root_layout_actions` 保存已执行映射；该工具为已完成的一次性操作，不作为日常 CAD/仿真入口。`--full-project` 是原编目快照的续跑，不是目录迁移后的全新扫描。

## 子目录职责

| 子目录 | 用途与保留范围 |
|---|---|
| [current_authority_index/](current_authority_index/README.md) | 派生来源导航生成器及其独立测试；不拥有机器结论 |
| [mechanical_asset_index/](mechanical_asset_index/) | 本次全项目编目与整理工具；由主线程维护 |
| [legacy_f3r2_root_scripts/](legacy_f3r2_root_scripts/) | 已归位的历史 F3R2 脚本，固定输入与旧版本差异保留 |
| [preauthorization_readiness/](preauthorization_readiness/unified_r2_v2/README.md) | Unified R2 历史预执行探测与就绪性检查，保留对应源码与记录 |
| [project_visualization/](project_visualization/) | VIZ 离线展示源码与独立验证；[历史比赛启动说明](../10_research/competition_convergence/launch_manifest.md) |
| [research_dashboard/](research_dashboard/README.md) | P0 历史研究证据集成；报告和输入/产物清单相互绑定，原位保留 |
| [research_env/](research_env/README.md) | 有日期的软件环境与工具能力记录，不是科学参数或当前安装保证 |

旧域说明中的重复导航已并入本页。报告构建、可视化和回放从本域进入；本轮不重写工具包的冻结 Gate、结果 manifest 或输入哈希。
