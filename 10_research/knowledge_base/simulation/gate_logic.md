# Gate 与证据裁决逻辑

## 两个互不替代的维度

`FROZEN` 表示当前基线不得改动；其余标签表示证据成熟度：

| 标签 | 含义 |
|---|---|
| `VERIFIED` | 在明确适用范围内有最终机器 Gate 或完整性核验 |
| `LIMITED` | 资产可用，但含 provisional、待审或覆盖缺口 |
| `NEGATIVE_RESULT` | 实验完成，最终裁决为 REPEAT 或没有安全候选 |
| `PLANNED` | 只有方案、协议、任务卡或候选工具 |
| `BLOCKED` | 缺参数、接口、授权、硬件或上游 Gate |

## Fail-closed 原则

1. UNKNOWN、缺失值、哈希漂移和来源冲突不得自动填成零或 SAFE。
2. 测试 `PASS` 只证明软件合同，不自动构成 scientific Gate `PASS`。
3. 模块 Gate `PASS` 不等于下阶段得到授权；例如 SAFE-00 可以 `PASS` 且 next=false。
4. partial、中间诊断和摘要不得覆盖同一模块的最终 Gate。
5. REPEAT 和没有安全候选是有效科学负结果，不得通过放宽阈值或删除失败样本改写。
6. `LOCAL_ONLY_UNTRACKED` 可报告，但不能提升 committed baseline 的成熟度。

## 证据优先级

1. 最终机器 Gate JSON、原始结果和绑定哈希；
2. 冻结配置、接口 SSOT 和授权记录；
3. 状态真值报告与证据矩阵；
4. 文献 manifest、阅读卡和 PDF 完整性；
5. 显式标注的本地未跟踪资产；
6. 本知识库、叙述报告、展示材料和历史记忆。

## 当前主要 Gate 入口

| Gate | 路径 |
|---|---|
| sim_10 | [`sim_10_gate_check.json`](../../../30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json) |
| sim_11 final | [`sim_11_gate_check.json`](../../../30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json) |
| sim_12 | [`sim_12_gate_check.json`](../../../30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json) |
| SAFE-00 | [`safety_00_gate_check.json`](../../../30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json) |
| CTRL-01 | [`control_01_gate_check.json`](../../../30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json) |
| CTRL-02 | [`control_02_gate_check.json`](../../../30_simulation/control_02_base_attitude/results/control_02_gate_check.json) |
| e15 core | [`core_gate_check.json`](../../../30_simulation/e15_core_coverage/results/core_gate_check.json) |
| e15 ANCF | [`gate_summary.json`](../../../30_simulation/e15_ancf_certification/results/gate_summary.json) |
| e16 | [`gate_check.json`](../../../30_simulation/e16_sync_capture/results/gate_check.json) |
| Wave 1 | [`wave1_gate_check.json`](../../partner_requirement_closure/wave1_results/wave1_gate_check.json) |

全部 15 个 Gate JSON、历史快照和 partial/final 区分见 [`simulation_scenario_map.md`](../../00_project_architecture/simulation_scenario_map.md)。
