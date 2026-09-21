# sim_11 — 星-臂-帆板全耦合动力学（路线 A 主线）

中心刚体 + 两侧 FFR 柔性帆板 + B601 6R 机械臂的浮动基座树形多体模型
（决策 D-YH-1..4）。纯 numpy/scipy，参数经 `20_engineering/config/coupled_scene/` YAML 参数卡 +
几何 SSOT 装载，几何/质量参数不在代码中手抄。

| 位置 | 内容 |
|---|---|
| `src/config_loader.py` | 参数卡 + SSOT 装载（T_SM 与 sim_05 冻结常量一致性断言） |
| `src/ffr_panel.py` | 悬臂 EB 解析模态 FFR 帆板（模态频率、B_t/B_r 运行时生成） |
| `src/coupled_dynamics.py` | Kane 装配 M/c/A、reduced/full 双模式积分、帆板增广 J* |
| `src/capture_solver.py` | 柔性 Delassus 捕获冲量（6DOF/3DOF；刚性极限 == sim_06 rigidize） |
| `src/contact_window.py` | v1.1：有限接触带宽捕获（半正弦等冲量 + lockup 收口；G4 物理修复） |
| `src/scene_a1_arm_slew.py` | 场景 A1：臂展开（五次多项式，8 s + 保持 12 s） |
| `src/scene_a2_capture.py` | 场景 A2：A1 末态 + 150 kg 碎片@3°/s 捕获（`--contact-ms` 选带宽口径）+ 40 s 振铃 |
| `src/run_gates.py` | 五组 Gate 机器裁决 → `results/sim_11_gate_check.json` |
| `src/plot_g4_diagnostic.py` | G4 诊断双图：理想冲量 m 慢收敛尾 vs 带宽滤波曲线 |
| `tests/run_all.py` | 27 项 assert 回归（无 pytest；含接触带宽 5 项） |
| `results/sim_11_tests_22of22.log` | 2026-07-17 v1.0 全量回归留档（22/22 PASS） |
| `results/baseline_verification_20260717.log` | sim_05 22/22 + sim_07 benchmark/smoke 基线复跑留档 |
| `docs/sim_11_耦合动力学报告_20260717.md` | 中文报告（方程分块推导 / 退化对比 / 结果 / v1.1 §3.4） |
| `docs/sim_11_对抗式审查闭环_20260717.md` | 原后台工作流完成度、逐条修正与 G4 v1.0 阻断 |

**科学结论以 `results/sim_11_gate_check.json` 机器裁决为准；测试 PASS ≠ 科学 Gate PASS。**
当前裁决（v1.1，2026-07-18）为 **`SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`**：
v1.0 曾因理想冲量 Δt=0 下 A2 模态能量 m=2/3/4 变化 2.78%/1.27% >1% 判
`SIM11_GATES_FAIL: G4_convergence`（git 6c0035b）；v1.1 诊断其根因为理想冲量对
能量指标不适定（m=2..7 慢收敛尾，逐阶 +2.86/+1.29/+0.72/~+0.4%），引入有限接触
带宽（T_c=20 ms 名义，PROVISIONAL 待 B601 夹爪实测）后前向加密链 m3→m4→m5
收敛 0.48%/0.027%，同一 1% 判据通过。理想冲量诊断完整保留于裁决 JSON
`ideal_impulse_diagnostic` 字段。帆板模态参数为占位（`PROVISIONAL_PARAMS: true`），
杨恒数值案例到位后替换 `20_engineering/config/coupled_scene/coupled_model_v0.yaml`
并重跑全部 Gate（复现命令见报告 §7）。

编号说明：sim_10 已被 `01_project/competition/sim10_mission_feasibility_design.md` 预留，
本模块取 sim_11。只读 import sim_05（b601_model/dynamics）、30_simulation/common、sim_07
（Gate 对比），未修改任何冻结内容。
