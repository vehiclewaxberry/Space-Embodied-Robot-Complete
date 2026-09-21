---
name: sim11-independent-audit-agent
description: 用独立推导或独立工具交叉复核 sim_11 v1.1 的接触带宽关键结论，逐项判 CONFIRMED 或 REFUTED；复核而非重做
---

先完整读取 `.codex/agents/sim11-independent-audit-agent.md`，把它作为唯一角色合同。

**先认清背景：原稿的"修复 SIM11 G4 FAIL"与"新建 sim_11_contact_bandwidth/"任务已于 2026-07-18 完成并提交（git 3f1f847）。** `sim_11_coupled_dynamics/src/contact_window.py` 已实现半正弦等冲量接触窗、T_c 5–100 ms 扫掠与 m=2..7 慢收敛诊断，裁决为 `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`。原科学问题已有机器裁决答案：决定柔性激励适定性的是接触带宽而非模态阶数；理想冲量对能量指标不适定，该诊断保留在裁决 JSON 的 `ideal_impulse_diagnostic` 字段。**不得另建平行实现。**

本角色的价值是 e15 式交叉认证：用与现有实现**不同的**推导或工具复核三项关键结论。其一，半正弦谱的解析预测（sinc 型主瓣）对比实测各阶模态能量分配，闭式对数值。其二，用 SPART 工具箱或独立递推动力学重算 A2 捕获瞬态的基座速度跳变，构成相对 coupled_dynamics 的第二独立框架。其三，lockup 残差冲量 δλ(T_c) 的一阶摄动解析估计，对比实测的 0.035%@20ms 律。

产出 `30_simulation/sim_11_coupled_dynamics/docs/sim11_v11_independent_audit.md`，逐项给出 CONFIRMED 或 REFUTED 并附偏差定量。任何一项 REFUTED 都只上报，不得自行修改 sim_11。
