---
title: RT3 制造/集成/线束/热红队审查（CA-A/CA-B/CA-C）
generated_at: 2026-08-27
status: DESIGN_RESEARCH_CANDIDATE
author_agent: RT3 redteam（制造/集成/线束/热）；工具循环事故后由主代理按其完整报告落盘
verification: 数值为红队手工复核；机器验证见 rt_verify.py 输出 RT_VERIFY_OUT_V1.json，差异以脚本为准
---

# RT3 制造/集成/线束/热红队审查

## 1. 证据基础
DESIGN_BASIS_V1.md；CANDIDATE_ARCHITECTURES_V1.yaml（77c932a87169 ✓ 与 CANDIDATE_MASS_CG_V1.json 记录一致）；EQUIPMENT_LIST_V1.yaml（2f6b5163f5f5）；B1 基准（738bb4cf6402）；GATE_C2_CHECK.json；02_PRODUCT_STRUCTURE.yaml；12_HARNESS_MISSION_ENVELOPE.yaml；ROUTE_C_ROBUST_MARGIN_LEDGER_V1.csv；GAP_REGISTRY.csv。成员质量独立重算与 JSON 一致（1.216836/2.0667609/4.927722 kg）。

## 2. 共性接口空洞（三候选同）
冻结壳体 INST_BUS_12U_CORE 是 solid envelope proxy（无内部结构/舱段/线束空腔/检修开口），BUS_PANELS=DEFINED_NOT_MODELLED 且 fastener/joint ABSENT（GAP-IL-06）。**40 行设备中 11 行（ST1/2、SS1-4/6、ANT-S/UHF、GPS-ANT、TH-MLI）映射的 outer_panel_inner_face 物理上不存在**；次结构↔主结构连接（螺接/铆接/嵌件/转接件）三候选全部未定义。

## 3. CA-B kill-issues（REJECT）
- **K1 线束走廊自相冲突**：声明的 -y/-z 内角 20×20 走廊（y,z∈[-113.15,-93.15]）被自身 shear_mid_right（y∈[-111.75,-110.25]）与 shear_mid_bottom（z∈[-111.75,-110.25]）在中舱全程剖断，干涉各约 113.5×1.5×16.85≈**2868 mm³ > 1000 mm³**（DB-R-22 阈值）；残余缝隙 1.4 mm 不可用；harness_channel 只声明隔框过线孔、未声明剪切板过线槽。
- **K2 装配矛盾**：步骤 2「剪切盒铆接成盒」→步骤 4「盒内装入堆栈/电池」——96×90 端板堆栈笼与 93×86×41 BPX 无法进入已铆合封闭盒，违反 B1 R5「堆栈先成组件整体入框」。
- **K3 CDS 不可救**：CDS 变体叠加 CA-C 式 3.2 kg 压载@[-163,40,0] 后 CG_x=(16.4234×120.07+3.2×(−163))/19.62=**73.9 mm > 70 仍 FAIL**；质量 19.62×1.15=22.57 kg（余量 1.43 kg，自述 21.5/2.5 偏乐观 1.1–1.9 kg）；二级结构 2.067 kg 单超 B1 全结构上限 2.0 kg。

## 4. CA-C 高危条件（AWC）
ballast_steel 字面盒（x∈[-170.5,-155.5],y∈[-30,110],z∈[-110,110]）与 EQ-ANT-S 干涉 ~121,500 mm³、与 EQ-RADIO/EQ-PROP-MIPS/EQ-SS6 各数千 mm³（>1000 阈值）；钢块距 EQ-MAG 仅 **152.5 mm**（磁清洁 UNKNOWN）；CDS x 裕度 1.135 mm，压载短缺 ~94 g 或位移 ~6 mm 即翻转；装配步骤 3 CG 配平在步骤 4–6 设备装入之前，顺序错误（应置末位）。

## 5. CA-A 条件项（AWC）
front_tray[200,210,2]@x=120 字面 x∈[20,220] 越前舱 49.75 mm 并与 FRZ-BRIDGE 干涉 ~9600 mm³；rear_tray x∈[-223.5,-3.5] 越后壁 53.25 mm——dims 方向语义未定义（UNKNOWN），需定义朝向+按舱长 113.5 重裁。共用件失配：battery_plate 180×96 对 y=±43 双 BPX（y 跨距 179 mm）每侧悬出 **41.5 mm**（沿 x 并置 2×86≤180 可行）；rw_cluster_bracket 70×70 对四轮 y/z 跨距 110 mm 每侧悬出 **20 mm**。弹簧舱 40×30×30 与根铰 [-61,±143.15,0] 在壁外、支架穿壁路径 UNKNOWN（三候选同）。

## 6. 线束背景
E_HRN rated envelope=0_SAFE_SAMPLES；Route-C margin ledger 4 项 FAIL（clearance_mission −13.85、key_states −13.69、bend_radius −4.8e-11 vs P06=50、cross_clearance −0.46/full_range −43.46）；P06=null/HOLD→三候选弯曲半径符合性只能 MEASUREMENT_PENDING（候选已诚实登记）。

## 7. 评分与 verdict
| 候选 | 制造 | 集成 | 线束 | 热 | 维护 | verdict |
|---|---|---|---|---|---|---|
| CA-A | 8 | 5 | 7 | 7 | 8 | ACCEPTABLE_WITH_CONDITIONS |
| CA-B | 4 | 3 | 3 | 5 | 4 | **REJECT**（K1/K2/K3） |
| CA-C | 5 | 4 | 7 | 6 | 6 | ACCEPTABLE_WITH_CONDITIONS |

CA-A 首要条件=托盘几何语义+电池板/轮支架尺寸修正+面板接口定义；CA-C 首要条件=压载块几何重构避让 ANT-S/RADIO/MiPS/SS6+磁清洁评估或改钨/无磁钢+配平顺序置末位。
