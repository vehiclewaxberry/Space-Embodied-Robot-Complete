# sim_09 Gate E1.5 统一证据报告

日期：2026-07-14｜集成分支：`codex/e15-integrate`｜最终裁决：**REPEAT_E1_5**

## 1. 执行结论

- 修正网格：72 个顶层工况；几何滚转明细：96 行 / 24 组。
- 功能回归：t1–t11 全部通过；旧 E1 冻结证据 10/10 Git blob 一致且工作树无改动。
- ANCF：保存 15 条逐次求解记录；历史 retry 复核 未通过；修正 Top-3 BDF 复核 未通过。
- MPCS 状态计数：{'SAFE': 0, 'UNKNOWN': 3, 'UNSAFE': 69}；阈值登记状态：`PROVISIONAL`；Top-3 扰动门禁：`REPEAT_E1_5`。

本轮只在 A/B/C 三条证据线、t1–t11 与旧 E1 冻结审计全部通过时允许 `GO_E2`。计算基础设施已经完整运行，因此证据不足时使用 `REPEAT_E1_5`，不以 `BLOCKED` 代替科学裁决。

## 2. 证据线 A：真实几何与两阶段捕获

统一服务航天器基座、完整抓取坐标系、捕获相位和末端滚转均进入同一变换链。接近速度定义为同步跟踪抓点速度之上的法向剩余闭合速度。

两阶段模型最大接触 twist 残差为 `1.388e-16`，最大分阶段动量残差为 `1.032e-12`，净目标 wrench 直接校核残差为 `8.001e-13`，能量闭合残差为 `3.553e-15`。
完整可比较速度组：2；每组必须严格覆盖 0.005 / 0.01 / 0.02 m/s，并验证首次接触冲量严格递增。

捕获指标分为首次接触 wrench、锁止完成 wrench 和目标净 wrench。抓取后角速度、轮组动量与 ANCF 激励使用 Stage-2 最终状态或两阶段基座总跳变。

## 3. 证据线 B：ANCF 数值可靠性

有限求解链为 Radau nominal → Radau reduced max-step → Radau tighter tolerance → BDF。只有数值不收敛或数值溢出允许进入 fallback；程序异常、非法输入、初值不一致和事件终止均立即 fail-closed。
逐次记录绑定 case hash、求解配置、收敛分类、残差/不可用原因、耗时和输出指标哈希。retry-level 结果只有在同一原始 Radau 证据与独立 BDF 结果严格小于 5% 差异时，才获得训练和安全评估资格；UNKNOWN 不填零，也不取得任何资格。

## 4. 证据线 C：MPCS 与 Pareto

名义 Pareto Top-3：`无`。
几何最大可操作度候选不在名义动力学 Top-3 中；本数据支持“几何指标不能单独预测抓取后系统后果”。
`M_PCS` 是登记约束归一化裕度的最小值，不是加权总分。推进剂由轮组动量线性派生，已从 Pareto 支配维度中剔除；所有安全表述均保留 `PROVISIONAL` 阈值限定。

## 5. 逐线裁决

| 证据线 | 结果 |
|---|---:|
| A 真实几何与两阶段捕获 | PASS |
| B ANCF 数值可靠性 | REPEAT |
| C MPCS / Pareto 有效性 | REPEAT |
| t1–t11 与旧 E1 冻结 | PASS |
| **总裁决** | **REPEAT_E1_5** |

## 6. 诚实边界

- 接触仍是完全塑性 6D 瞬时冲量，随后所有关节瞬时锁止；不能解释峰值接触力、柔顺接触、滑移或抓取成功概率。
- 8 s 接近轨迹为零终端速率 min-jerk，terminal qdot 是捕获瞬时边界；尚未闭合执行器连续速度匹配。
- E1.5 的 `point_3dof` 仍 fail-closed；5D/3D 的 roll 只作为未约束诊断。
- 阈值登记完整，但硬件与结构证据仍为 provisional；本轮 SAFE 不等于普适航天安全标准。
- 本轮没有进入 E2、G3、AprilTag 或 B601 HIL。

## 7. 核心图件

- `30_simulation/sim_09_grasp_evaluator/figures/fig_e15_geometry_roll_phase.png`
- `30_simulation/sim_09_grasp_evaluator/figures/fig_e15_geometry_vs_stability.png`
- `30_simulation/sim_09_grasp_evaluator/figures/fig_e15_pareto_knee.png`
- `30_simulation/sim_09_grasp_evaluator/figures/fig_e15_threshold_sensitivity.png`

最终机器可读裁决：`30_simulation/sim_09_grasp_evaluator/results/e15_gate_check.json`。
