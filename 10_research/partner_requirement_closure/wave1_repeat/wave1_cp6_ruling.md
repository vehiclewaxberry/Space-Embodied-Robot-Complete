# Wave 1 CP6 终裁 — 2026-07-20（PI: Fable 5，用户 CP1 总授权下）

## 机器裁决（不可改写）
`WAVE1_REPEAT`（integrator-R @ faa34e5，wave1_results 五件套为准）：
SAFE-00 PASS（47/47，Gate SHA 逐位）；CTRL-02 PASS（复跑逐位一致）；
CTRL-01 REPEAT——但余项全部为预注册第 2 条口径下的
genuine_negative_result_preserved（7 项，含 v0 −51.91%/−7.99% 逐字保留），
defect_resolved 3 项（能量账本 7.9e-2→5.63e-12、T3 碰撞合同伪影、比较器方法学）。

## PI 终裁：采纳方案 B——Repeat 周期就此关闭，以文档化负结果收口

理由：①无实现缺陷可修（红队 9/9 独立复认，能量修复独立复现）；②翻转余项
须换场景/换增益假设 = 新实验而非 Repeat（属 Wave 2+ 或论文修订议题）；
③公平比较器（C2_MATCH5）下的真零效应与设计空间边界本身是可发表结果。

**治理边界**：本终裁不改写机器 verdict；`WAVE1_REPEAT` 原样入档。合并主干
= 证据存档行为，非 PASS 声明；任何引用必须携带 verdict 原文与负结果清单。

## 随附裁定
1. **claims 限制**：CTRL-01 相关论文表述只允许"冻结增益与预注册轨迹下"的
   限定句式；C3 零空间效应按真零结果（+1.84e-5%）表述。
2. **硬件触发重跑登记**（并入 rerun_triggers）：W1-R12 Stage-A 隐含轮力矩
   0.033 N·m 超 PROVISIONAL 档 3.3×——轮组选型冻结后重评 Stage-A 可行性；
   W1-R13 GC7 量子残差=稳定门槛 21.5%——实测最小脉宽增大 ~4.6× 则 Stage-B
   裁决翻转，B601/执行器实测到货即重跑瞬态层。
3. Wave 2 不自动启动，等用户批准（范围见 master_plan：Physics Tool Contract、
   ROM 选择器、VLA V0/V1/V2.5、帆板转正、H0）。
