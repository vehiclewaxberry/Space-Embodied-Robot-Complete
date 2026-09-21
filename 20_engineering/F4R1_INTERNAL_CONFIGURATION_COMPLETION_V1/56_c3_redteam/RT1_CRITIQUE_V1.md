---
title: RT1 结构与传力红队审查（CA-A/CA-B/CA-C）
generated_at: 2026-08-27
status: DESIGN_RESEARCH_CANDIDATE
author_agent: RT1 redteam（结构/传力）；工具循环事故后由主代理按其完整报告落盘
verification: 数值为红队手工复核；机器验证见 rt_verify.py 输出 RT_VERIFY_OUT_V1.json，差异以脚本为准
---

# RT1 结构与传力红队审查

## 1. 证据基础（只读，sha256 前 12 位入册）
根 AGENTS.md；55_c3_design_basis/DESIGN_BASIS_V1.md、CANDIDATE_ARCHITECTURES_V1.yaml/.md、CANDIDATE_MASS_CG_V1.json、compute_candidates.py（重跑字节一致 3729c177…）；50_c1_layout/EQUIPMENT_LIST_V1.yaml（2f6b5163f5f5）；02_PRODUCT_STRUCTURE.yaml（M3R 4×M4 64×64/PCD 90.51）；SOLAR_R2_MECHANISM_ANALYTICAL_LEDGER（铰 2 控制工况 0.24 J/480 N；根铰 240 N/48 N·m 瞬态）；sim_06 CSV（40 工况，捕获峰值 60.9 N/17.6 N·m：max|J|=0.7749 N·s、力偶 0.2236 N·m·s、T_c=20 ms 半正弦）。材料常数 ASSUMED：E6061=68.9 / E7075=71.7 / E_CFRP=50 GPa；6061-T6 屈服 276 MPa ASSUMED。

## 2. 共享 kill 级发现（三候选同一构件，LC-4 全不达标）
帆板根铰支架 40×30×6 mm al6061，根铰瞬态 48 N·m：σ=6M/(w·t²)=6×48/(0.03×0.006²)≈267 MPa ≈ 6061-T6 屈服 276 MPa，MS≈0。**返工：t≥8–10 mm**（t=8 mm→σ=150 MPa、MS≈0.84；t=10 mm→σ=96 MPa、MS≈1.9，见 rt_verify.py）。

## 3. 包络几何违例（AABB=pos±dims/2，机器可复算）
| 候选 | 构件 | 违例 |
|---|---|---|
| CA-A | front_tray x∈[20,220] | 越前舱面 49.75 mm，撞冻结 M3R/bridge 区 |
| CA-A | rear_tray x∈[-223.5,-3.5] | 越后舱面 53.25 mm |
| CA-B | 前后腹板 | 各越 ±9.75 mm；gussets 与 bridge x-span 叠 4.75 mm |
| CA-C | rear_module_deck x∈[-260,-40] | 越后舱面 89.75 mm（最重）；压载越界 0.25 mm；front_deck 同 CA-A 违例 |

## 4. 模态筛查（一阶，简支/固支）
CA-A 后托盘（2.5 mm 载 ~1.2 kg）~46/92 Hz、前托盘 ~48/96 Hz——低于 100 Hz 惯例（ASSUMED）；CA-B 隔框板 ~350 Hz 通过、堆栈笼 ~111 Hz 临界（三候选共享）；CA-C 隔振器摇摆模态 18–182 Hz（k ASSUMED 1e3–1e5 N/m），且**弹性隔振无法隔离 19.2° 刚体姿态扰动——CA-C 头条收益机理不成立**。

## 5. 臂基座传力
冻结链 M3R 4×M4 栓组：捕获 17.6 N·m 下最大栓拉 ~137 N；发射 10 g 臂载 460.6 N + 悬伸 50/100/150 mm（ASSUMED）力矩 23/46/69 N·m 下栓拉 180/360/540 N——均 << M4 8.8 级保证载荷 ~5.6 kN，栓级无弱链。Stage-B 板/桥-法兰接头强度仓内无评级（UNKNOWN）。CA-A/CA-C 无次要路径（单路径依赖）；CA-B 角撑+腹板+隔框双路径量化成立、刚度优势成立。

## 6. CA-C kill-issue（K-C-1）
3.604 kg 钢压载（占候选结构质量 73%）无任何锚固/保持方案定义；由 3 mm 7075 甲板承载时一阶模态 ~31 Hz（简支）/~62 Hz（固支），远低于 100 Hz；10 g 惯性 353.5 N 对 4×M4 微不足道（剪 88 N/栓 vs ~3.3 kN），但方案缺失+低模态+失效灾难性（舱内 3.6 kg 自由钢块）构成架构级缺陷。

## 7. 评分与 verdict
| 候选 | S1 发射传力 | S2 臂基座 | S3 帆板根部 | S4 刚度模态 | S5 构件可校核/包络 | verdict |
|---|---|---|---|---|---|---|
| CA-A | 5 | 4 | 4 | 3 | 4 | ACCEPTABLE_WITH_CONDITIONS |
| CA-B | 8 | 9 | 7 | 8 | 7 | ACCEPTABLE_WITH_CONDITIONS |
| CA-C | 4 | 4 | 6 | 2 | 3 | **REJECT**（K-C-1） |

条件项：CA-A=托盘加厚/加筋、包络裁剪、托盘↔主结构接头与 HDRM Base_1 路径定义、冻结链强度评级核查；CA-B=消解 4.75–9.75 mm 包络干涉、接头定义、挖空率可制造性、减重；CA-C 修复=压载直锚主结构后面板+冗余锁定+甲板重构+撤销隔振声称（属架构级变更，不支持本轮修复）。
