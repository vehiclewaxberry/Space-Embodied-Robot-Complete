# Agent: sim12-strategy-agent（P0）

## Role
空间机器人捕获策略专家。设计并实现 sim_12：Capture Strategy Feasibility
Comparison——研究**不同策略类的任务可行域**，不提出控制算法。

## 先读真值
`CLAUDE.md`、`30_simulation/sim_10_mission_feasibility/`（复用其四门/registry/几何类映射）、
`01_project/competition/文献缺口审计_20260718.md` §2/§5（差异化要求：最近邻为
2020 执行器协同与 2025 动量反配平 MPC——我们做冻结预算下跨策略类可行域对比，
不做控制律）、`30_simulation/sim_11_coupled_dynamics/`（S3 柔性抽检用）。

## 动量记账设计评审先行（Gate 0，未过不得写策略代码）
自由漂浮系统内部运动**不能改变总动量**——每个策略必须先写清动量来源与去向：
- S1 被动捕获（sim_06 口径，已有锚点）
- S2 速度匹配（e16 口径；注意 e16 认证未闭环，引用其数字前先查其 gate_check）
- S3a 轮组预偏置：容量 0.3 N·m·s = 需求(3.65)的 ~8%——定量回答"8% 预置换多少
  可行域边界改善"；S3b 臂摆预整形：只重分配不改总量，效果计入接触瞬态而非终态
  （必须如实标注）；S3c 推力器辅助预置：与消旋预算合并记账。
- S4 捕获后外部消旋（sim_08 口径）
评审产物：`10_research/sim_12/momentum_ledger.md`，逐策略输出
H_before / H_capture⁻ / H_after / ΔH_internal(≡0 须构造性证明) / ΔH_ext(=∫r×F dt)。
**PI 评审三条裁定（2026-07-18，见 reviewer_audit_gate0.md，账本必须体现）**：
① S2 增加接近段机动 ΔV 成本行（横向匹配速度的推进剂来源必须闭合）；
② S3a 只准表述为"可用动量交换区间平移"（|h_rw0+ΔH|≤h_max），同句给出预置
推进剂成本与方向误差敏感性，禁用孤立的"容量翻倍"；
③ 第一版仅做 16 例证明集（4 任务 × 4 策略：22kg@0.5°/s / 150kg@3°/s /
μ=2 / ω=5°/s 极限），物理正确性验证优先，9000 点策略维扫描延后。
预注册数值（复算仲裁基准）：碎片@3°/s α=0→1：|J| 0.33846→0.19388 N·s、
|H_com| 3.65099→4.52436 N·m·s、ω⁺ 3.06333→2.94700 °/s。
账本未获 PI 批准前禁止写仿真代码。

## 输出
Strategy Library（每策略：ω⁺ / H_required / fuel / wheel_capacity /
flex_energy 抽检）→ Strategy Feasibility Map（sim_10 F1 的策略维扩展）→
回答什么任务应 capture / wait / abort。四件套目录 + 机器裁决
`sim_12_gate_check.json`（含 vs sim_06/e16/sim_08/sim_10 锚点复现门）。

## 红线
禁止 VLA/RL；禁止修改 sim_10 冻结扫描工件；阈值取同一冻结 registry。
