# sim_12 Phase 1 — 16 例策略对比报告 + Binding-Gate 分析 — 2026-07-18

> 裁决：`results/sim_12_gate_check.json` = **SIM12_PHASE1_GATES_PASS**
> （GS1 守恒 3.85e-16 / S2 矢量闭合 2.2e-16；GS2 分化成立；GS3 清单已产）。
> tests 3/3（B-S1 与 sim_10 碎片锚点**逐位一致** 0.00e+00）。
> 图：`results/strategy_ladder_initial.png`（Selection Map 口径，无等级假设）。

## 结果矩阵（默认档 wheels 0.3 / cold_gas / l_T 0.17；燃料含策略前置成本）

| 例 | S1 被动 | S2 速度匹配 | S3a 轮组预置 | S4 消旋 | 选择 |
|---|---|---|---|---|---|
| A 22kg@0.5°/s | **FEAS**(0 g) | FEAS(~0.3 g) | FEAS(3.0 g) | FEAS(~2 g) | **S1**（最省） |
| C 48kg@2°/s | INFEAS(WHEEL) | INFEAS(WHEEL) | **FEAS**(3.0 g) | FEAS(~40 g) | **S3a**（3.0 vs ~40 g） |
| B 150kg@3°/s | INFEAS(RATE) | INFEAS(RATE) | INFEAS(RATE) | INFEAS(RATE) | **ABORT** |
| D 150kg@5°/s | INFEAS(RATE) | INFEAS(RATE) | INFEAS(RATE) | INFEAS(RATE) | **ABORT** |

## Binding-Gate 分析（核心科学结论）

1. **判据成立**：A 的瓶颈不存在→最省者胜；C 的瓶颈是轮组容量→唯一能平移
   容量球心的 S3a 成为分辨策略（对 S4 省 ~13× 推进剂）；B/D 的瓶颈是速率门
   （2°/s registry）→ 任何本策略集成员都救不了 → ABORT。
   **最优策略 = binding gate 的函数，不存在无条件排序**（GS2 机器证明）。
2. **REPEAT_CORE 在策略空间复现**：B 案四策略全灭于 RATE 门——e16 的
   "μ=6.25 碎片@3°/s 全策略不可行"从 216 例控制口径推广到策略类口径。
3. **Impulse–Momentum Decoupling**（B 案账本行）：S2 冲量 0.194 vs S1
   0.338 N·s（−43%）而 H 4.524 vs 3.651 N·m·s（+24%）——降低接触冲量
   不保证降低捕获后动量负担；两者由不同物理量支配（相对速度 vs 绝对状态）。
4. **S4 专属带存在但未被 4 例覆盖**：H∈(0.6, 5.47] ∧ ω⁺≤2°/s 区间为 S4
   独占（S3a 球心平移上限 0.6），策略维扫描（revision 弹药）将显式画出。

## 限制与纪律
S3b 不在集合（预注册断言待 sim_11 多体固化）；flex_energy 列 PROVISIONAL
（帆板占位参数，FLEX 不入判据）；S2 侧 e16 引用须复述其限制条款；
S3a 为 θ=0 名义（方向敏感性扫掠 [0..60°] 列 Phase 2）；
执行器档为 sim_08 placeholder CLASS 值。复现：`python src/strategy_eval.py`。
