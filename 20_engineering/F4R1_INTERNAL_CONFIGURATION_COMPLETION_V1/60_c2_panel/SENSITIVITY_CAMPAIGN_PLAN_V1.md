---
title: SENSITIVITY_CAMPAIGN_PLAN_V1 — 帆板参数灵敏度 campaign 方案书（C4 执行预案）
generated_at: 2026-08-27
status: DESIGN_RESEARCH_CANDIDATE
execution_status: PLANNED_NOT_AUTHORIZED（C4 阶段执行；本阶段只出方案，不跑仿真批）
scope: C-ISS-03 正面回答 + A1 终稿 + FLEX 门对 sim_10 可行域边界的扰动评估
inputs: PANEL_PARAM_ENVELOPE_V2.yaml（三档）、PANEL_VERIFICATION_V1.json（解析基线）、sim_11/e23/sim_12 既有链
---

# 帆板参数灵敏度 Campaign 方案书（V1）

## 1. 目标与 Gate 映射

| 目标 | 对应问题 | 出口 |
|---|---|---|
| O1：A1「柔性反馈可忽略」逐档终判（HOLDS/FLIPS） | C-ISS-03、根 AGENTS.md 待办 3 | A1_CONCLUSION_RESTATEMENT 终稿（替换 PRE_CAMPAIGN_ANALYTIC） |
| O2：C-ISS-03「f1 低 8–20×」以灵敏度区间正面回答 | CHARTER C-ISS-03 | 论文灵敏度章图表（三档 × T_c 响应面） |
| O3：FLEX 门对 sim_10 可行域边界的扰动量化 | sim_10 FLEX=UNKNOWN 不入判据的遗留 | FLEX 边界扰动报告（锚点 Δω⁺ 与门归属迁移） |
| O4：binding-gate 策略选择对帆板参数的鲁棒性 | sim_12 GS2 结论的参数依赖 | GS2 逐档重推报告 |

## 2. 因子设计

| 因子 | 档位 | 出处 |
|---|---|---|
| 帆板参数档 | LOW / NOMINAL / HIGH（σ=2.0/4.0/7.7 kg/m²、f₁=1/8/20 Hz、ζ=0.002/0.01/0.03，铰链刚度随 V3 角点） | `PANEL_PARAM_ENVELOPE_V2.yaml` |
| 捕获策略子集 | A_low→S1_passive、C_transition→S3a_wheel_bias、B_anchor→ABORT（≥3 例；D_extreme→ABORT 可选第 4 例） | sim_12 GS2 冻结结果（`sim_12_gate_check.json` sha256 `a416c1348111`） |
| 接触窗 T_c | {5, 20, 100} ms（已扫范围 [5,10,20,50,100] ms 内取带边两端 + 名义；20 ms 仍为 PROVISIONAL 引用不改） | `scene_A2_capture.yaml`（sha256 `4b979a1dfd18`） |

主设计矩阵（确定性全因子 + 定点加密）：

| 区块 | 单元 | 运行数 |
|---|---|---|
| B1 A1 臂展开场景（策略/T_c 无关） | 3 档 | 3 |
| B2 A2 捕获接触窗主阵 | 3 档 × 3 策略 × 3 T_c | 27 |
| B3 收敛链（G4 等效 m3→m4→m5，名义 T_c，S1） | 3 档 × 3 m 值 | 9 |
| B4 交叉求解抽查（BDF，名义 T_c，S1） | 3 档 | 3 |
| B5 e23 R2 整翼链交叉（V3 角点 × 3 T_c × 1 参考目标场景） | 3 角点 × 3 | 9 |
| 合计 | — | **51** |

## 3. 执行链与纪律（复用 sim_11/e23 链）

- 主链：`30_simulation/sim_11_coupled_dynamics/src/scene_a1_arm_slew.py`、`scene_a2_capture.py --contact-ms {5,20,100}`（接触窗模型 `contact_window.py` sha256 `d6ad26e3f8da` 不改）；策略初条件由 sim_12 策略层供给（A_low/C_transition/B_anchor 锚点态）。
- 交叉链：`30_simulation/e23_r2_full_flex_coupled_recert/` 七模态 ROM 链（V3 角点原样消费 `R2_FLEXIBILITY_VALIDITY_ENVELOPE_V3.json` sha256 `5a15d0d3b8a1`），验证叶尺度档与整翼系统级包络的结论一致性（映射见包络 V2 metadata）。
- **不改冻结 config**：三档参数卡为**新文件**，写入新 campaign 目录（建议 `30_simulation/sim_16_panel_sensitivity/`，目录名 Owner 确认后生效）；`20_engineering/config/coupled_scene/`、`flexible_appendage_v1.yaml`、V3 包络等只读。
- **全部输出进新目录**：新 campaign 目录 `results/`；禁止写入 sim_11/results、e23/results 或任何冻结位置。
- **每 run 带 config 哈希**：run manifest 记录 {参数档、策略、T_c、参数卡 sha256、消费 SSOT sha256 清单、git commit、求解器统计（nfev/steps/rtol）、守恒审计值}；无 manifest 的 run 不计入判据。
- 确定性：Radau rtol=1e-10/atol=1e-12 与 sim_11 口径一致；关键单元 BDF 交叉（B4）；全部 run 确定性回放一次（重跑逐位一致）。

## 4. 验收指标（预注册）

| ID | 指标 | 判据 | 数据来源 |
|---|---|---|---|
| M1 | A1 逐档终判 | G3b 等效：柔性 vs 刚化基座姿态峰值相对差 < 1e-3（预注册阈值），且与解析预测（`PANEL_VERIFICATION_V1.json → e_a1_analytic_scaling`）偏差在 3× 内 → HOLDS；否则 FLIPS | B1/B2 输出 |
| M2 | FLEX 边界扰动 | sim_10 锚点（碎片 μ=6.25 → ω⁺=3.0633°/s INFEASIBLE_RATE；卫星 μ=0.917 → 1.3872°/s WHEELS_ONLY）在柔性帆板下的 Δω⁺ 报告；门归属是否迁移逐档登记 | B2 输出对拍 sim_10 锚点 |
| M3 | binding-gate 迁移 | GS2 等效重推 best_per_case 逐档对照冻结 {A_low:S1, C_transition:S3a, B_anchor:ABORT, D_extreme:ABORT}；**ABORT→非 ABORT 翻转为安全相关事件，立即升级 Owner**；非 ABORT→ABORT 记录为策略收缩 | B2 + sim_12 策略层重推 |
| M4 | 收敛 | m3→m4→m5 模态能相对变化 < 1%（G4 等效）逐档 | B3 |
| M5 | 守恒卫生 | 每 run 动量/能量审计达 sim_11 同量级机器精度；不达标 run 作废记 UNKNOWN | 全部 run manifest |

## 5. fail-closed 规则

1. 求解器不收敛 / 积分失败 → 该单元记 **UNKNOWN**，禁止插值、禁止跨档外推；
2. ROM 响应超 V3 线性合同（转角/挠度限）→ 该单元 UNKNOWN（继承 `FAIL_CLOSED__NO_LINEAR_ROM_EXTRAPOLATION`）；
3. 守恒审计（M5）不达标 → run 作废 UNKNOWN，不进入任何判据聚合；
4. 任一档内含 UNKNOWN 单元 → 该档 verdict 记 UNKNOWN_PARTIAL，campaign 总 verdict 不得给全 PASS；
5. config 哈希漂移（manifest 与冻结记录不符）→ 全批作废，回到配置审查。

## 6. 算力与时长估计（ASSUMED，未实测）

| 项 | 估计 | 依据 |
|---|---|---|
| 单 run 时长 | ~2–5 min（单核工作站） | ASSUMED；锚：e23 接触窗 run 求解器统计 nfev≈2002/steps≈273（E23 灵敏度 JSON），sim_11 bw20 同量级 |
| 主阵 51 runs | ~2–4 h | 51 × 2–5 min |
| 确定性回放 + 交叉求解 | ×2 | 合计 **~4–8 h wall-clock** |
| 存储 | 51 runs × (CSV+summary+manifest) ≈ 数百 MB 级 | ASSUMED |

## 7. 依赖与前置

- C4 阶段授权（CHARTER §2：灵敏度仿真方案在 C2 只出方案书）；
- T_c 实测（GAP-IF-01）：若 campaign 前到位，替换名义档并重标 \|H\| 表；不到位则以 {5,20,100} ms 覆盖申报；
- B 轨（比赛收口）优先级绝对最高：campaign 不得挤占 B 轨算力与人力窗口（CHARTER §6）；
- 不做 CAD、不碰 Route-C 线束（HOLD 维持）。
