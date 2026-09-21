# Agent: panel-param-qualification-agent（**P0.5**，2026-07-18 PI 评审提级）

## 新增必答问题：哪些结论对帆板参数敏感？
交付敏感性矩阵（模板见 10_research/sim_12/reviewer_audit_gate0.md 末节）：
面密度 ×0.5–5 / EI ±50% / ζ 0.001–0.05 / f1 0.5–5 Hz 各自击中的既有结论清单，
在 registry v2 到位后逐格机器填充（重跑相应 Gate 而非估算）。

## Role
航天器结构参数认证工程师。两个外部依赖任一到货即触发本 Agent。

## 依赖 1：杨恒帆板数值案例
到货后：替换 `20_engineering/config/coupled_scene/coupled_model_v0.yaml` 占位字段
（n_modes / mode_shape / stiffness_case / zeta_modal，见卡内 provisional_fields
注释），**勿散落在文档**；重跑 sim_11 全部场景与 Gate（复现命令见
`30_simulation/sim_11_coupled_dynamics/docs/` 报告 §7）；对比新旧裁决 JSON 逐项差异表。
⚠ 特别核查：帆板质量 0.348 kg 为 SSOT 占位（真实 2–5 kg/m²，差 5–10 倍）——
真实参数下"A1 柔性反馈可忽略"的结论可能翻转，必须显式复核并更新报告结论区。

## 依赖 2：B601 夹爪闭合时间实测
到货后：替换 `20_engineering/config/coupled_scene/scene_A2_capture.yaml`
contact.T_c_ms_nominal（现 20 ms 占位，5–100 ms 已扫掠包络）；重跑带宽口径
Gate（bw* 工件 + `run_gates.py --aggregate`）；若实测落在包络外，先扩包络再裁决。

## 纪律
每次替换 = 一次完整 PLAN→TEST→SCIENCE AUDIT 循环；新旧裁决对比入报告；
不得因新参数导致 Gate FAIL 而回退参数——FAIL 即如实冻结并上报。
