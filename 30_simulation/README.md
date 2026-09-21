# 仿真、控制与原始机器证据

<!-- WORKSPACE_NAV_START -->
**2026-09-21 目录整理入口：** [本域用途与归档总览](../01_project/governance/WORKSPACE_ORGANIZATION_20260921/WORKSPACE_INDEX.html?domain=30_simulation) · [全项目导航](../PROJECT_MAP.md)。历史来源和证据原位保留；本轮整理不改变设计或科学结论。
<!-- WORKSPACE_NAV_END -->

导航整理：2026-09-06。本域保存模型、计算程序、测试、原始结果及机器裁决。不同模型和版本的结果不互相覆盖，导航不汇总为单一通过状态。

- [冻结 sim 主链与控制场景地图](../10_research/00_project_architecture/simulation_scenario_map.md)：历史主链的场景与证据定位，运行规则按原冻结语境理解。
- [E23 七模态耦合重认证](e23_r2_full_flex_coupled_recert/README.md)及[原始 Gate](e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json)：R2 柔性证据入口；[E22](e22_r2_full_flex_coupled_diagnostics/README.md)保留早期截断反例与诊断。
- [R2 动力学候选](r2_dynamics_engineering_closure/README.md)、[R2 控制候选](r2_control_engineering_closure/README.md)、[联合闭环](r2_dynamics_control_system_closure/README.md)：各自合同、结果和未闭项的入口。
- [Sim13 后端说明](sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/README.md)及[原始注册表 Gate](sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json)：区别后端负控、模型绑定与可执行任务范围。
- [R2 各链原始来源指针](../01_project/current/CURRENT_RELEASE_POINTERS_V1.yaml)：补充机械、安全和控制接口定位。

新模块沿用 `src/`、`tests/`、`results/`、`docs/` 的自包含组织。原始失败、UNKNOWN 和受限结果留在各拥有者目录；WP03 新工程候选不能直接继承旧仿真结论。

## 目录职责

以下分类只说明资产用途；文中的历史执行限制按原记录日期理解。目录内不同版本、独立复算和原始结果保留原位。本轮仅对派生说明合并、对确认副本去重。

| 子目录 | 用途 | 保留范围 |
|---|---|---|
| [asm_00_interface_preflight](asm_00_interface_preflight/README.md) | 历史前检合同 | 接口前检、成功评价合同及原始受限裁决。 |
| [common](common/) | 共享依赖 | 刚体与捕获冲量公共算法；保留源码。 |
| [control_01_end_effector_tracking](control_01_end_effector_tracking/README.md) | 冻结基线与独立验证 | Wave 1 控制或安全合同；历史失败及限制保留。 |
| [control_02_base_attitude](control_02_base_attitude/README.md) | 冻结基线与独立验证 | Wave 1 控制或安全合同；历史失败及限制保留。 |
| [control_r2_integrated_candidate](control_r2_integrated_candidate/README.md) | 现存候选支路 | 按目录内具名合同和结果使用；不合并不同运行或独立审计。 |
| [current_r2_digital_host_capture_data_v1](current_r2_digital_host_capture_data_v1/README.md) | 现存候选支路 | 按目录内具名合同和结果使用；不合并不同运行或独立审计。 |
| [dynamics_control_prebind_r1](dynamics_control_prebind_r1/README.md) | 现存候选支路 | 按目录内具名合同和结果使用；不合并不同运行或独立审计。 |
| [e15_ancf_certification](e15_ancf_certification/README.md) | 历史独立诊断 | 覆盖、ANCF 认证和同步捕获的独立证据。 |
| [e15_core_coverage](e15_core_coverage/README.md) | 历史独立诊断 | 覆盖、ANCF 认证和同步捕获的独立证据。 |
| [e16_sync_capture](e16_sync_capture/README.md) | 历史独立诊断 | 覆盖、ANCF 认证和同步捕获的独立证据。 |
| [e17_b601_mission_trajectory_candidates](e17_b601_mission_trajectory_candidates/README.md) | 工程诊断谱系 | 候选输入、不同模型分支及重认证各自保留。 |
| [e18_b601_mission_input_branches](e18_b601_mission_input_branches/README.md) | 工程诊断谱系 | 候选输入、不同模型分支及重认证各自保留。 |
| [e19_b601_mission_branch_diagnostic_evaluation](e19_b601_mission_branch_diagnostic_evaluation/README.md) | 工程诊断谱系 | 候选输入、不同模型分支及重认证各自保留。 |
| [e20_b601_independent_mass_branch_coupled_diagnostics](e20_b601_independent_mass_branch_coupled_diagnostics/README.md) | 工程诊断谱系 | 候选输入、不同模型分支及重认证各自保留。 |
| [e21_m7_r2_arm_placement_rigid_coupled_diagnostics](e21_m7_r2_arm_placement_rigid_coupled_diagnostics/README.md) | 工程诊断谱系 | 候选输入、不同模型分支及重认证各自保留。 |
| [e22_r2_full_flex_coupled_diagnostics](e22_r2_full_flex_coupled_diagnostics/README.md) | 工程诊断谱系 | 候选输入、不同模型分支及重认证各自保留。 |
| [e23_r2_full_flex_coupled_recert](e23_r2_full_flex_coupled_recert/README.md) | 工程诊断谱系 | 候选输入、不同模型分支及重认证各自保留。 |
| [module_cards](module_cards/README.md) | 合并认知入口 | 主题知识卡集中于 README；不替代原始证据。 |
| [r2_control_engineering_closure](r2_control_engineering_closure/README.md) | 现存候选支路 | 按目录内具名合同和结果使用；不合并不同运行或独立审计。 |
| [r2_dynamics_control_system_closure](r2_dynamics_control_system_closure/README.md) | 现存候选支路 | 按目录内具名合同和结果使用；不合并不同运行或独立审计。 |
| [r2_dynamics_engineering_closure](r2_dynamics_engineering_closure/README.md) | 现存候选支路 | 按目录内具名合同和结果使用；不合并不同运行或独立审计。 |
| [r2_mujoco_free_floating_precontact_v1](r2_mujoco_free_floating_precontact_v1/README.md) | 现存候选支路 | 按目录内具名合同和结果使用；不合并不同运行或独立审计。 |
| [safety_00_runtime_gate](safety_00_runtime_gate/README.md) | 冻结基线与独立验证 | Wave 1 控制或安全合同；历史失败及限制保留。 |
| [sim_01_free_flight](sim_01_free_flight/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_02_target_tumble](sim_02_target_tumble/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_03_arm_reaction](sim_03_arm_reaction/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_04_capture_corridor](sim_04_capture_corridor/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_05_free_floating_arm](sim_05_free_floating_arm/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_06_capture_impulse](sim_06_capture_impulse/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_07_ancf_flexible](sim_07_ancf_flexible/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_08_detumble_actuator_budget](sim_08_detumble_actuator_budget/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_09_grasp_evaluator](sim_09_grasp_evaluator/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_10_mission_feasibility](sim_10_mission_feasibility/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_11_coupled_dynamics](sim_11_coupled_dynamics/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_12_strategy_feasibility](sim_12_strategy_feasibility/) | 冻结科学基线 | 保留模型、配置、原始数据、测试及裁决。 |
| [sim_13_physics_gated_embodied_grasping](sim_13_physics_gated_embodied_grasping/README.md) | 混合谱系 | V1 历史 bootstrap 与后续候选/独立后端分目录保留。 |
| [sim_13_viability_extension_r1](sim_13_viability_extension_r1/README.md) | 现存候选支路 | 按目录内具名合同和结果使用；不合并不同运行或独立审计。 |
| [sim_14_m4_digital_prototype_grasping](sim_14_m4_digital_prototype_grasping/README.md) | 历史数字样机支路 | M4/M5 诊断合同；不替代新的整星工程候选。 |
| [sim_15_m5_geometry_gated_grasping](sim_15_m5_geometry_gated_grasping/README.md) | 历史数字样机支路 | M4/M5 诊断合同；不替代新的整星工程候选。 |

## 早期 v0 模型说明（2026-07-09）

<a id="simulation-baseline-v0"></a>

本节吸收原 `README_sim_baseline_v0.md`。以下质量、软件环境和简化模型结论只属于当时 v0 基线，不能用于替代 B601 完整模型或 WP03 工程候选。

## Stage-2 v0 Simulation Baseline

> Role: v0 digital-prototype simulation baseline | Last synced: 2026-07-09
> Physics implemented directly in numpy/scipy (Basilisk/SPART/42 not installed locally;
> they are the future cross-validation upgrade). All sims read mass/CoM/inertia from
> `../20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv`
> and use the frozen coordinate SSOT (frames S/M/T/D). Run with the Anaconda python.

### Layout
```
30_simulation/common/rigid_body.py      shared: inertia loader, torque-free Euler + quaternion, H/E diagnostics
30_simulation/sim_01_free_flight/       servicer_12U_v0 uncontrolled attitude drift
30_simulation/sim_02_target_tumble/     target_debris_v0 tumble + grasp-feature visibility
30_simulation/sim_03_arm_reaction/      manipulator-induced base reaction (reduced free-floating model)
```
Each `sim_XX/` has its script and `results/{*.csv,*.png}`. One-click: `python 30_simulation/sim_XX_*/sim_XX_*.py`.

### Results & validation

| sim | headline result | physics check |
|---|---|---|
| sim_01 | 120 s attitude/rate history for the 12U servicer | angular momentum \|H\| and rotational KE E conserved to ~0 (machine precision) |
| sim_02 | tumbling debris grasp feature visible only ~50% of the time to a +X-approaching servicer | \|H\|, E conserved |
| sim_03 | **arm reach induces ~13.1 deg peak base attitude disturbance**, returning to 0 after a reciprocal retract | exact angular-momentum conservation (reversible) |

### Key v0 finding
Manipulator motion cannot be neglected: on the 12U v0 configuration with a simplified planar arm,
a single reach swings the free-floating base by ~13 deg. A 5 deg base-pointing budget is therefore
**infeasible with naive (non-reaction-aware) arm motion** — motivating reaction-null-space / momentum-
compensated planning (see sim_04 capture corridor).

### Modeling honesty
- sim_03 is a **reduced planar free-floating model** (angular-momentum conservation about the instantaneous
  system CoM; base translation neglected). Full 3D generalized-Jacobian dynamics via SPART is future work.
- Target/debris inertia is self-defined (confidence low), never claimed as measured (risk RA-003).
