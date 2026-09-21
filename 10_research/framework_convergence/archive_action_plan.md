# Archive Action Plan — PLAN ONLY

## 结论

HEAD `c7f09ab` 已通过 R100 完成七份被替代文档的归档，并建立
`01_project/competition/archive/README.md`。本轮不得再次移动它们。

对 380 个已跟踪的 md/txt/csv/yaml/yml/json 文件做 SHA-256 精确内容去重，
重复组为 0；不存在可据“完全相同内容”直接归档的新增对象。

本轮归档部分只产动作计划，**未执行 `git mv` 或删除**。为消除活跃状态冲突，
已对中央索引/总览和若干预注册历史文件增加最小状态覆盖与现行证据指针；未改历史
科学结果。

## ALREADY_COMPLETE

- c7f09ab 归档的七份文档与 archive README。
- panel 两文件迁入 `10_research/panel/`。
- `research_state_v4.md` 作为现行薄状态指针。
- `research_state_v3.md` 已被明确界定为 Wave0 前历史快照。

## 高置信新增归档候选

### A1 `项目现状总览_20260715.md`

- 替代者：`项目现状总览_20260720.md`。
- 动作：人工批准后 `git mv` 入现有 archive，追加 README。
- 不删除、不改写历史结论。

### A2 `sim10_mission_feasibility_design.md`

- 已被现行报告与 `SIM10_GATES_PASS` 取代，但仍称“未实施”。
- 移动前必须更新或明确以下引用的历史性质：
  - `01_project/competition/研究战略裁决_第二收敛点_20260717.md`
  - `30_simulation/sim_10_mission_feasibility/src/feasibility_core.py`
  - `30_simulation/sim_11_coupled_dynamics/README_sim_11.md`
  - `30_simulation/sim_11_coupled_dynamics/docs/sim_11_耦合动力学报告_20260717.md`
- 本轮不移动。

## 原位更新，不归档

本轮已完成：

- `.codex/AGENTS.md`：移除“sim_12 唯一在研”旧状态，登记 Wave A
  `PLANNED_NOT_AUTHORIZED`。
- `.codex/agents/physics-agent-architect.md`：加 Phase1 PASS 与工具未实现覆盖。
- `.codex/skills/README.md`：现行状态基准由 v3 改为 v4。
- `10_research/paper1_architecture.md`：加 sim_12 ALREADY_COMPLETE 与 Gate 指针。
- 两份 control 预注册计划：保留原文，只加执行结果横幅。
- 20260720 总览与 `10_research/README.md`：补 sim_01–08 证据层级、SAFE review、
  CTRL-02 provisional、J/H 与 DT2 限定。

仍待人工决定的原位更新：

- `.codex/agents/` 其余历史角色卡是否统一加现行框架横幅；
- 老战略/日历文档是否只加冻结横幅或移入 archive。

## MANUAL_REVIEW

- `研究战略裁决_第二收敛点_20260717.md`：战略逻辑仍有价值，状态与日历已过期；
  优先加“冻结战略裁决/当前状态见 20260720 总览”横幅，不自动归档。
- `repo_status_snapshot_v0.md`：历史回退快照；是否进入 stage1 专用 archive 需人工决定。
- `stage1c_cad_modeling_entry_plan.md`、12U baseline/requirements：文件存在不等于
  CAD、间隙、惯量验收闭合，必须逐项审查。
- `arm_mount_v1.yaml` 的 6U `native_part` 路径：可能只是资产存放，也可能是 SSOT
  污染；禁止自动修改。
- 活跃可视化构建脚本和 v0 HTML 仍有旧路径
  `01_project/competition/00_repo_truth_audit_20260711.md`；冻结 HTML 不改，
  构建脚本应在后续维护轮改指 archive 路径或现行状态报告。

## NO_ACTION

- 已归档七份文档及 README。
- `research_state_v3.md` 的历史快照功能。
- 6U quick-layout 文档和 CAD 资产；其非主线定位已明确。
- 所有 Gate JSON、原始 CSV/JSON、测试、参数卡、代码、CAD/URDF/STEP/STL。

## 执行门

只有人工批准 A1/A2，且先完成交叉引用核查，才允许后续轮执行 `git mv`。

当前状态（2026-07-20 更新）：A1（20260715 总览）已 `git mv` 入 archive 并追加 README；
A2（sim10 设计稿）加历史横幅原位保留（4 处引用未改，不移动）。其余项仍 PLAN_ONLY。
