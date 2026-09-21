# 机械 Loop Engineering 续接裁决 V4

## 唯一合法增量

- e20 已完成两个人工标量质量分支、两条 arm-only 轨迹的四条互不串接 sim11 耦合诊断；独立验证为 `43/43`，负控为 `93/93`。
- 本轮唯一新增闭合状态是 `independent_surrogate_mass_branch_sim11_coupled_arm_only_diagnostic_execution_closed=true`。V3 已有 `current_release` 字段逐项原值保留；总体 Gate、next-stage 与 release-credit 仍为 `HOLD/false/false`。
- 该闭合只说明哈希绑定的数值诊断可复现，不授予任何机械、任务、生产、硬件或飞行权限。

机器裁决：`MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_INDEPENDENT_SURROGATE_MASS_BRANCH_SIM11_COUPLED_ARM_ONLY_DIAGNOSTIC_EXECUTION_CLOSED__M4_SYSTEM_MASS_INERTIA_E15_PHYSICAL_MOUNT_CONTACT_ATTACHED_CAD_MISSION_PRODUCTION_AND_FLIGHT_HOLD`

## 模型边界

- 质量补全规则为 `UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE`：只调整 sim11 bus 的质量和惯量，保持其既有几何与质心；这是人工标量敏感性模型，不是 M4 全系统质量、质心或惯量。
- e20 数值安装系为 `M_DYNAMICS_LEGACY_NUMERICAL`，数值上与 M7 ODR-01 的当前 dynamics convention `T_SM=[185.25,0,0] mm + Ry(90 deg)` 相同；但 e20 明确没有消费 current-M7 unique dynamics M，也没有形成 current-M7 design dynamics closure。该 M frame 本身没有物理实体。`208 mm + 25.000014 deg` 是与 dynamics M 分离的 CAD/几何 mount context，不能互相替代。
- e20 未检查 WP2 V2 各配置在 S 系汇总 B601 COM/惯量时实际采用哪套受控变换；因此 `M7_FRAME_TO_MASS_RECONCILIATION_NOT_EVALUATED_IN_E20`，不能据此升级 M7/current-design mass dynamics。
- 两个质量分支没有被选择、合并、平均或解释为测量不确定度。e20 未执行 contact window、目标附着、锁定、恢复或任务段。

## 仍未放行

- e15 仍为 `REPEAT_ANCF_CERTIFICATION`：交叉求解最大相对差 `5.637349%` 高于 `5.00%`，最终候选仍不存在。
- sim11 的板质量、模态、EI、阻尼与接触窗仍为 provisional；局部 Radau/BDF 数值一致性不能清除 e15 债务。
- `physical_contact_ready=false`、`attached_target_recovery_ready=false`、`cad_generation_authorized=false`、`mission_trajectory_release_ready=false`、`production_dynamics_ready=false`、`hardware_motion_ready=false`、`flight_qualification_ready=false`。

## 下一闭环

先由 e21 对拍 ODR-01 dynamics convention、独立 CAD/几何 mount context 与 WP2 V2 每个配置的 S 系 B601 COM/惯量放置，再形成正式选定、含不确定度的全系统质量属性分支；随后用受控板参数独立复算并重过 e15。ODR-42、MPI、接触/锁定、附着恢复和任务合同仍按既有顺序分别闭合。
