# R2_FULLFLEX_HF_MODEL_V1 — 人读版（机器字段以同basename YAML 为准）

- schema: `R2_FULLFLEX_HF_MODEL_V1`
- 生成时间：2026-08-23T20:45:41.771960+08:00（宿主机本地钟，Asia/Shanghai UTC+08:00）
- 生成方：KIMI M7 机械终局接管 swarm Wave-4a (ODR-45..49 owner decisions + R2 full-flex closure) / AGENT-B1 round2_hf_model builder (pure numpy/scipy; upstream read-only)
- 状态：**CANDIDATE_PROVISIONAL_BANDS__NOT_CERTIFIED**；`review_status=PENDING_OWNER_REVIEW`；`next_stage_authorized=false`；`release_credit=false`

## 模型（每翼，展开锁定平直构型）

根铰（kθ_root 50/200/800 N·m/rad）→ 叶1 柔性（EB 梁 FE，默认 20 单元/叶）→ 铰2
（kθ_inter 20/100/400）→ 叶2 柔性 → 铰3 → 叶3 柔性。铰轴 ∥ X_S，(y,z) 平面弯曲，
运动学登记逐字遵循 `FLEXIBLE_APPENDAGE_R2.yaml`。**新增扭转车道**：每叶携带绕展向
（+y）轴扭转 DOF φ，GJ 带为本包新推导。

## GJ 推导（PROVISIONAL_DERIVED，禁止声称为实测）

- 构造基础（登记候选）：2×0.2 mm CFRP 面板（E=70 GPa 准各向同性，ν=0.3 候选 →
  G_f=2.6923e+10 Pa）+ 2.1 mm 芯（G_c=100 MPa 候选），总厚 2.5 mm，弦长 0.300 m。
- 下限（开截面 St-Venant，自由翘曲）：GJ_low = chord/3·(2·G_f·t_f³ + G_c·t_c³)
  = **0.135687 N·m²**。
- 上限（闭室 Bredt-Batho，面板为唯一柔顺壁、边缘闭合刚性）：A_m=chord·(t_c+t_f)=
  6.9000e-04 m²，GJ_high = 4·A_m²/(∮ds/(G·t)) = **17.090769 N·m²**。
- 名义 = 几何均值 = **1.522824 N·m²**。带宽约两个数量级——这是诚实的有界区间，
  不是点估计；须由 WP5 R2 硬件选型 vendor 数据或实测替换。

## 阻尼（PROVISIONAL_DERIVED，新推导记录）

ζ 带 [0.002, 0.02]，名义 0.005（Wave-4a 指令名义）。双车道纪律：ζ=0 守恒审计车道
（本包全部 M/K 特征值证据）与 ζ≠0 耗散预测车道（仅 report-only 映射）分离。旧占位
（卡 ζ=0.01 TBD_cite_literature、sim_11 zeta_modal 占位）**不作为权威被消费**；
名义值与退役占位若有数字巧合，出处互相独立。

## Latch（HOLD 逐字）

独立 latch 刚度 = **null**（`HOLD_LATCH_GEOMETRY_NOT_MODELLED`）；按 SLOT-03，板间
kθ 带 [20,100,400] 作为含 latch 的展开锁定态柔顺传播。

## 质量记账（MC-A，BK-DYN-MASS-HINGE-ALLOC-MC-A）

动能只含叶质量（3×0.18=0.54 kg）；根铰 0.05 + 板间铰 2×0.03 + HDRM 0.08 + 线束
0.05 = 0.24 kg 作为刚性非随动界面质量记在铰线结构质量账；合计 **0.78 kg/翼精确闭合**。

## 范围限制（逐字保持，未零填）

SLOT-03 latch 独立刚度 null / SLOT-04 根支架柔顺 null / SLOT-05 自由间隙 null /
SLOT-07 基座耦合参与因子不在本包。e15 `REPEAT_ANCF_CERTIFICATION` 与
`r2_full_flexible_coupling=NOT_EVALUATED` 不因本文件改变。

## 纪律

HF-vs-ROM 对比为 **REPORT ONLY，禁止调参**；遗留 R1 车道数值禁止入 R2 车道（gate
黑名单机器核查）；本卡不授予任何生产/制造/鉴定/发射/飞行权威。
