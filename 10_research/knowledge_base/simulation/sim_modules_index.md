# 仿真与证据模块索引

> 本页只做导航。精确数量、阈值和 verdict 必须回到 [`simulation_scenario_map.md`](../../00_project_architecture/simulation_scenario_map.md) 与原始 Gate JSON；关键主链的只读知识卡见 [`30_simulation/module_cards/`](../../../30_simulation/module_cards/README.md)。

## 基础与候选链

| 模块 | 主要问题 | 状态 |
|---|---|---|
| sim_01 | 自由飞行姿态/角速度基础场景 | `LIMITED + FROZEN` |
| sim_02 | 翻滚目标和抓取点运动学 | `LIMITED + FROZEN` |
| sim_03 | 平面机械臂—基座反作用趋势 | `LIMITED + FROZEN` |
| sim_04 | 早期捕获走廊筛选 | `LIMITED + FROZEN` |
| sim_05 | 6R 自由漂浮刚体基线 | `VERIFIED + FROZEN` |
| sim_06 | 捕获冲量与组合体状态锚点 | `VERIFIED + FROZEN` |
| sim_07 | ANCF 柔性组件响应 | `LIMITED + FROZEN` |
| sim_08 | 轮组/推力器资源预算 | `LIMITED + FROZEN` |
| sim_09/E1 | 抓取候选评价 | `LIMITED + FROZEN` |
| sim_09/E1.5 | 核心安全候选筛选 | `NEGATIVE_RESULT + FROZEN` |

## 当前竞赛脊柱

| 模块 | 精确裁决摘要 | 状态 |
|---|---|---|
| sim_10 | `SIM10_GATES_PASS` | `VERIFIED + FROZEN` |
| sim_11 | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS` | `LIMITED + FROZEN` |
| sim_12 Phase 1 | `SIM12_PHASE1_GATES_PASS` | `VERIFIED + FROZEN` |
| SAFE-00 | `PASS`，但 `PENDING_REVIEW`、next=false | `VERIFIED + FROZEN` |
| CTRL-01 | `REPEAT` | `NEGATIVE_RESULT + FROZEN` |
| CTRL-02 | 模块 `PASS`，对外 provisional | `LIMITED + FROZEN` |
| Wave 1 | `WAVE1_REPEAT` | `NEGATIVE_RESULT + FROZEN` |

## 认证与规划支路

| 模块 | 角色 | 状态 |
|---|---|---|
| e15 core | 核心安全覆盖与候选裁决 | `NEGATIVE_RESULT + FROZEN` |
| e15 ANCF | 候选级跨求解器柔性认证 | `NEGATIVE_RESULT + FROZEN` |
| e16 | 同步捕获离线扫描 | `LIMITED + FROZEN` |
| ASM-00 历史前检 | 接口字段与授权前检 | `BLOCKED + LOCAL_ONLY_UNTRACKED` |
| ASM-01/ASM-02 | 持续接触与分阶段装配控制 | `BLOCKED` |

## 后续数字样机与非发布诊断胶囊

| 模块 | 机器裁决/范围 | 状态 |
|---|---|---|
| sim_13 | `SIM13_ENVIRONMENT_BOOTSTRAP_PASS`，仅确定性运动学 bootstrap，next=false | `DIAGNOSTIC + LOCAL_ONLY` |
| sim_14 | `PASS_DIAGNOSTIC_KERNEL_HOLD_PRODUCTION_DYNAMICS` | `DIAGNOSTIC + HOLD_PRODUCTION` |
| sim_15 | `PASS_SIM15_DIAGNOSTIC_REPRODUCIBILITY_ONLY` | `DIAGNOSTIC_ONLY` |
| e17 | `E17_NUMERIC_SEEDS_WELL_FORMED_ONLY__MISSION_TRAJECTORY_RELEASE_REMAINS_HOLD` | `LOCAL_ONLY + HOLD` |
| e18 | `E18_NON_RELEASE_BRANCHES_WELL_FORMED__MISSION_PHYSICAL_HARDWARE_AND_PRODUCTION_RELEASE_HOLD` | `LOCAL_ONLY + HOLD` |
| [e19](../../../30_simulation/module_cards/README.md#e19) | `E19_ISOLATED_NUMERIC_REPRODUCIBILITY_CLOSED__END_TO_END_PHYSICAL_CONTACT_ATTACHED_RECOVERY_AND_MISSION_RELEASE_HOLD` | `DIAGNOSTIC + HOLD` |
| [e20](../../../30_simulation/module_cards/README.md#e20) | `E20_INDEPENDENT_SURROGATE_MASS_BRANCH_SIM11_COUPLED_ARM_ONLY_DIAGNOSTICS_CLOSED__E15_ANCF_PROVISIONAL_PANEL_CONTACT_ATTACHED_RECOVERY_CAD_MISSION_PRODUCTION_AND_FLIGHT_HOLD` | `DIAGNOSTIC + HOLD` |
| [e21](../../../30_simulation/module_cards/README.md#e21) | `E21_M7_R2_MIXED_ARM_PLACEMENT_DETECTED__CURRENT_R2_RIGID_WING_FREE_FLOATING_ARM_ONLY_TWO_PLACEMENT_SENSITIVITY_AND_FIXED_BASE_ROM_REPRODUCTION_CLOSED__SINGLE_PLACEMENT_R2_FULL_FLEX_COUPLING_E15_HARNESS_CONTACT_MISSION_PRODUCTION_AND_FLIGHT_HOLD` | `DIAGNOSTIC + HOLD` |

## 路径规则

- 新模块应使用 `30_simulation/<module>/{src,tests,results,docs}` 自包含结构。
- 冻结主链、e15/e16 和历史 ASM-00 裁决不因后续导航补充而迁移或改写。
- [`asm_00_interface_preflight/README.md`](../../../30_simulation/asm_00_interface_preflight/MIGRATION_NOTICE.md) 只是职责占位，不是第二份 ASM-00。
- 当前禁止重跑、改阈值、修改 Gate JSON 或用新摘要覆盖最终机器裁决。
