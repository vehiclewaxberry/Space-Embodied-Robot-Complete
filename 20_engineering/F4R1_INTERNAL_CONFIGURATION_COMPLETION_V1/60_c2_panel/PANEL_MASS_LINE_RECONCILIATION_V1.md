---
title: PANEL_MASS_LINE_RECONCILIATION_V1 — 帆板质量双线调和提案（C-ISS-02 闭合）
generated_at: 2026-08-27
status: DESIGN_RESEARCH_CANDIDATE
decision_status: PENDING_OWNER_SIGNOFF
scope: C-ISS-02（sim_11 0.3483933 kg/板 vs R2 0.78 kg/翼，差 2.24×）的口径裁决提案；不改任何冻结值
machine_check: PANEL_VERIFICATION_V1.json（compute_c2_checks.py 复算，8/8 self-checks pass）
---

# 帆板质量双线调和提案（C-ISS-02 闭合）

## 1. 双线定义与出处

| 项 | sim 线（动力学研究模型） | R2 线（机械设计模型） |
|---|---|---|
| 构型 | 单板/侧，刚性小板 proxy | 2 翼 × 3 叶折展（accordion） |
| 几何 | L=0.200 m（跨）× b=0.227 m（弦）× t=6 mm（占位） | 叶 300×200×2.5 mm；展开 600 mm/翼，tip-to-tip 1430.8 mm |
| 面积 | A=0.0454 m²/板（复算 L·b） | A_叶=0.06 m²；A_翼=0.18 m²；两翼 0.36 m² |
| 质量 | 0.3483933 kg/板（均匀密度份额，24 kg 整星块模型拆分） | 0.78 kg/翼 = 叶 3×0.18 + hinge_root 0.05 + hinge_inter 2×0.03 + HDRM 0.08 + harness 0.05；两翼 1.56 kg |
| 面密度 | σ=7.674 kg/m²（隐含，复算） | σ_叶=3.0 kg/m²（candidate，NOT measured） |
| 实测状态 | 占位（SSOT 自述真实帆板典型 2–5 kg/m²） | 候选未实测（`basis: areal-density candidate 3.0 kg/m2; NOT measured`） |
| 出处 | `20_engineering/config/geometry/flexible_appendage_v1.yaml`（sha256 `52fa88084c62`）；`02_PRODUCT_STRUCTURE.yaml`（sha256 `0f9897ef4e41`，HOLD_PANEL 自述占位） | `SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json`（sha256 `d5b7dd16532f`）；`SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V3.yaml`（sha256 `a70083014199`） |

面积映射（脚本复算，`PANEL_VERIFICATION_V1.json → extracted_inputs / a_mass_from_areal_density`）：

- 翼/板面积比 = 0.18/0.0454 = **3.96×**；翼/板质量比 = 0.78/0.3483933 = **2.24×**（即 CHARTER C-ISS-02 之差）；
- 面密度比 = 7.674/3.0 = **2.56×**；
- B3 真实带 σ≈2–5 kg/m²：sim 线 7.674 **超出上界 ~1.5×（偏重）**；R2 线 3.0 在带内（蜂窝路线中值 / PCB 路线低端）。出处：B3 §2.3/§5.1（`10_benchmark/B3_DEPLOYABLE_SOLAR_ARRAY_BENCHMARK.md`，sha256 `d42aa3867c52`）。

## 2. 两线各自的用途与适用范围

| 用途 | sim 线 | R2 线 |
|---|---|---|
| 服务对象 | 路线 A 耦合动力学研究（sim_05/06/07/11/12 证据链）：捕获冲量、柔性反馈、接触带宽、策略可行域 | R2 机械设计闭环：质量账本（V3 R2 冻结）、机构/HDRM/锁扣/线束设计、七模态 ROM、E23 重认证 |
| 质量语义 | 24 kg 整星均匀密度拆分份额（m_bus + 2·m_panel ≡ 24.000 kg，mass_split_check.py 强制闭合），是**退化链锚点**（G3c 组合体 29.8956 kg）的一部分 | 物理帆板子系统候选质量（含机构硬件 0.24 kg/翼），计入 C01 总质量 31.022864807342987 kg |
| 改动的连锁代价 | 改质量 → 破坏 24 kg 闭合与 G3b/G3c 退化锚 → 须重跑 sim_11 全部门 + 回归 tests 27/27 + sim_07 对拍 | 改质量 → 触碰冻结账本（V3 R2 sha256 `3fd2557318e9`）→ 治理禁止覆盖，须走 ECR + Owner 签署 |
| 物理真实性 | σ=7.674 kg/m² 超真实带（B3 判占位**偏重** 1.5–3.8×）；f1=1.0 Hz 低 8–20×（C-ISS-03） | σ=3.0 kg/m² 在真实带内但未实测；叶/铰链/HDRM 构型有几何实体（冻结 STEP） |

结论：两线回答**不同问题**——sim 线是「动力学方法学证据的占位载体」，R2 线是「机械设计质量/机构账本的候选实体」。两者都非实测值。

## 3. 选项评估与推荐

### 选项 A：统一为一个值

- 含义：择一值（如 R2 0.78 kg/翼，或 B3 带内某值）同时替换 sim 参数卡与冻结账本。
- 代价：触碰冻结区（治理红线，CHARTER §3「禁止覆盖」）；sim_11/E23 全 Gate 重跑（属 C4 范围）；统一值本身仍无实测支撑（R2 3.0 kg/m² 未实测，B3 带 2–5 内任选都仍是候选）。
- 评估：**现阶段不可执行**——统一动作 = Owner 决策 + C4 重跑，且统一后数值仍是候选而非真值。

### 选项 B：两模型两用途声明（**推荐**）

- 含义：维持两线并存，论文与 Gate 引用时各自带限定语——sim 线结论标注「占位参数（σ=7.67 kg/m²、f1=1 Hz 占位）下成立，真实参数灵敏度见 C2 三档包络与 C4 campaign」；R2 线标注「ENGINEERING_CANDIDATE，未实测」。
- 配套：C2 已交付三档参数包络 V2（`PANEL_PARAM_ENVELOPE_V2.yaml`）覆盖两条线（sim 板 0.091–0.350 kg、R2 翼 0.600–1.626 kg），并给出 A1 结论的解析重述（`A1_CONCLUSION_RESTATEMENT_V1.md`）与 C4 灵敏度 campaign 方案（`SENSITIVITY_CAMPAIGN_PLAN_V1.md`）——用包络而非单点回答「真实参数下结论是否成立」。
- 理由：
  1. 治理合规：冻结区零改动，新候选以 DESIGN_RESEARCH_CANDIDATE 入账；
  2. 科学诚实：真值未知（UNKNOWN：无 datasheet、无实测）时，包络 + 灵敏度比重选一个新占位更诚实；
  3. 成本可控：不触发 C4 前的任何重跑；C4 campaign 一次覆盖三档 × 策略 × T_c；
  4. B3 判据：占位失真主矛盾在**刚度/频率轴**（f1 低 8–20×、EI 软 ~180×），质量轴仅 1.5–3.8×——统一质量值不解决主矛盾，灵敏度包络才解决。

**推荐：选项 B（两模型两用途声明）。** 统一动作推迟到实测/datasheet 到位后（B3 §7 建议路径：COTS 采购实测或复刻 arXiv:2407.19356 开源设计自建件实测），届时按「新候选 + 差异声明」入账并重跑 Gate。

## 4. 对 sim_11 既有结论的影响评估

| 结论 | 对质量/刚度参数的敏感性 | 评估（依据） |
|---|---|---|
| G1 动量守恒（1e-14 量级）、G2 能量审计、G5 Radau/BDF 交叉 | 数值恒等式，与参数值无关 | **不受影响**（机器精度恒等式；sim_11 Gate JSON sha256 `9309f5325271`） |
| G3b 刚化退化 19.2° 锚点、G3c 全刚化退化 | 锚定于 24 kg 闭合与占位卡 | 数值随质量线变化；结论形式（退化链成立）不变，绝对值须带「占位参数下」限定（verdict 已含 `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`） |
| A1「柔性反馈可忽略」 | 敏感（σ、f1、ζ、T_c 四轴） | 解析重述：**三档均 HOLDS**（LOW 0.261 / NOMINAL 0.064 / HIGH 0.043 姿态反馈比），翻转边界 f1 < 0.26–0.65 Hz（仅薄膜毯类），PRE_CAMPAIGN_ANALYTIC，终稿待 C4——见 `A1_CONCLUSION_RESTATEMENT_V1.md` |
| sim_07 刚柔 92×（锁定 vs 点捕获 tip 比） | 激励模式比，一阶近似与 σ/f1 无关（分子分母同 ∝ 1/f1） | **一阶鲁棒**；二阶待 C4 确认（sim_07a README sha256 `02c321a85d76`） |
| 振铃 37–75 s | t5 = ln20/(ζ·2πf1) | 重标定：LOW 238.4 s / NOMINAL 6.0 s / HIGH 0.8 s（脚本复算）；占位 95.4 s（ζ=0.005） |
| T_c=20 ms 接触窗 | 独立占位（待夹爪实测） | 本包**不修改**（GAP-IF-01；scene_A2 sha256 `4b979a1dfd18`）；campaign 以 5–100 ms 已扫范围取档覆盖 |

## 5. 决策状态与差异声明

- **PENDING_OWNER_SIGNOFF**：C-ISS-02 属 Owner 决策项（CHARTER §4：「C2 统一口径或声明两模型用途」）。本提案推荐选项 B，待 Owner 签署；若 Owner 改判选项 A，则转入 C4 重跑流程（先签署 ODR、再动参数卡、再全 Gate）。
- 差异声明：本提案不改任何冻结值（帆板质量/模态冻结占位一律不动）；三档包络 V2 为新候选，与冻结口径的差异已在 `PANEL_PARAM_ENVELOPE_V2.yaml → metadata.difference_declarations` 逐项声明。
- C1 接口：帆板档质量变化对 CG 影响经脚本一阶核算（`PANEL_VERIFICATION_V1.json → f_c1_interface_panel_mass_to_cg`）：R2 线三档 ΔCG ≤ 4.3 mm 量级，**不能**缓解 C1 OI-1（CDS 变体 x 残余 −57.83 mm、y −9.30 mm）；后部压载 ~3.2 kg 需求不变（登记为 GATE_C2 open item）。
