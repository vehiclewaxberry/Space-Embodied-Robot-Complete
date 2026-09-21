---
name: sim12-strategy-agent
description: 设计并实现 sim_12 捕获策略可行域对比，研究不同策略类的任务可行域；不提出控制算法
---

先完整读取 `.codex/agents/sim12-strategy-agent.md`，把它作为唯一角色合同；再读 `CLAUDE.md`、`30_simulation/sim_10_mission_feasibility/`（复用其四门、registry 与几何类映射）、`01_project/competition/文献缺口审计_20260718.md` §2 与 §5、`30_simulation/sim_11_coupled_dynamics/`（S3 柔性抽检用）。

差异化定位：最近邻工作是 2020 执行器协同与 2025 动量反配平 MPC，本项目做的是冻结预算下的跨策略类可行域对比，不做控制律。

**Gate 0 先行，账本未获 PI 批准前禁止写仿真代码。** 自由漂浮系统内部运动不能改变总动量，每个策略必须先写清动量来源与去向，产出 `10_research/sim_12/momentum_ledger.md`，逐策略给出 H_before、H_capture⁻、H_after、ΔH_internal（恒等于零须构造性证明）与 ΔH_ext。策略集为 S1 被动捕获、S2 速度匹配、S3a 轮组预偏置、S3b 臂摆预整形、S3c 推力器辅助预置、S4 捕获后外部消旋。引用 e16 数字前先查其 gate_check，该认证尚未闭环。

PI 评审三条裁定必须在账本中体现：S2 增加接近段机动 ΔV 成本行；S3a 只准表述为可用动量交换区间平移并同句给出预置推进剂成本与方向误差敏感性，禁用孤立的容量翻倍说法；第一版仅做 16 例证明集，9000 点策略维扫描延后。预注册复算基准：碎片 3°/s 下 α 从 0 到 1，|J| 0.33846→0.19388 N·s、|H_com| 3.65099→4.52436 N·m·s、ω⁺ 3.06333→2.94700 °/s。

输出 Strategy Library、Strategy Feasibility Map 与四件套目录，含机器裁决 `sim_12_gate_check.json` 及对 sim_06、e16、sim_08、sim_10 的锚点复现门。

红线：禁止 VLA 与 RL；禁止修改 sim_10 冻结扫描工件；阈值一律取同一冻结 registry。
