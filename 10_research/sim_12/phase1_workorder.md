# SIM12 Phase 1 工单（PI 批准 2026-07-18）— 16 例 Strategy Proof Set

前置：Gate0 PASS（b40c239）。禁止：大扫描 / Physics Agent / 控制器。完成后停止。

## 语言纪律（冻结）
- 禁用 "velocity matching paradox" → 用 **Impulse–Momentum Decoupling Effect**
- Paper 1 定题：Constraint-Dependent Strategy Selection for Non-Cooperative
  Spacecraft Capture under Momentum and Stability Limits（C1 可行域视角 /
  C2 冲量-动量解耦 / C3 binding-gate 判据）
- Gate0 通过的是 Physics Ledger，非 Strategy Feasibility Final——表述边界保持

## 4 任务 × 4 策略（S1 被动/S2 速度匹配/S3a 轮组预置/S4 捕获后消旋）
- A 低难度：22 kg 卫星 @0.5°/s（证明 Passive 区）
- B 锚点：150 kg 碎片 @3°/s（S1/S2 失败核心案例）
- C 过渡带：μ≈2（48 kg，G1 类）@2°/s 附近（找策略切换）
- D 极端：150 kg @5°/s（证明 Abort）

## 统一输出 schema（未来 Physics Agent 直接调用）
strategy_result: {feasibility, binding_gate, post_capture_rate, H_required,
impulse, fuel_g, wheel_margin, flex_energy(占位标注), confidence}
+ 每例动量账本行（H_before/H_after/ΔH_int/ΔH_ext）

## 三 Gate
- GS1 守恒：ΔH_internal=0 全例机器断言（S3b 终态≡S1 逐位；账本闭合 ≤1e-12）
- GS2 策略分化：机器证明**无策略在全部 4 例最优**（每策略至少一例最优/一例劣）
- GS3 主张审计：自动生成 allowed/forbidden claims（模板见
  reviewer2_attack_response.md；"strategy selection depends on the active
  physical constraint" ∈ allowed；"momentum shaping always improves" ∈ forbidden）

## 交付物
30_simulation/sim_12_strategy_feasibility/{src,results,tests,docs}：
strategy_results.csv / strategy_comparison_report.md /
strategy_ladder_initial.png（Selection Map 口径，无等级假设）/
binding_gate_analysis.md / sim_12_gate_check.json（GS1-3）
复用 sim_10 feasibility_core（只读）+ Gate0 账本数字为仲裁基准；
阈值同一冻结 registry；帆板 registry v2 仅候选，flex_energy 列标 PROVISIONAL。

## Reviewer-2 三攻（16 例必须直接回应）
1"重命名控制策略?"→靠边界图回答；2"S2 只是特殊工况?"→C 过渡带覆盖；
3"为何不直接优化控制?"→先证策略存在性。
