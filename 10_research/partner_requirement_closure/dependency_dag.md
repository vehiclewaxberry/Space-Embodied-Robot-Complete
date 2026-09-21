# Research Dependency DAG — Partner Requirement Closure — 2026-07-19

```
[冻结证据层]
sim_01-08 ──┐
sim_09 ─────┤
sim_10(PASS)┼──────────────┐
sim_11(PASS*)┤              │
sim_12 P1(PASS)┘            │
                            ▼
            ┌── Physics Tool Contract（F 已设计，T1-T4 Gate）
            │   ↑ 数据源：sim_10_scan_gates.csv + strategy_results.csv
            │
sim_11 J* ──┼─→ control_01 末端轨迹（C0-C3；Gate GC1 九项）
            │        │ 反冲历史输出
            │        ▼
sim_08+12 ──┴─→ control_02 姿态稳定（A0-A3/B0-B3；Gate GC0-GC6）
                     │
FFR/带宽/ANCF ─→ 多保真 ROM（L0/L1/L2 + 六规则；Gate GR1-GR5，
                     │         L2 须重过 e15 5% 口径）
                     ▼
             在线 Physics Tool（查表→ROM 升级路径）
                     │
VLA 泛化协议（V0-V3）─┼─→ 候选/技能生成 → Physics Gate → 控制器
                     ▼
硬件 H0 资格 → H1 运动学表征（含 T_c 实测→反哺 sim_11）
            → H2 感知资格 → H3 任务决策演示
```

## 关键依赖边（不得绕过）

1. VLA/控制器/HIL 一律不得绕过上游 Gate（L3 物理层是唯一执行授权源）；
2. control_02 Phase A 需要 control_01 的反冲历史 → control_01 先行；
3. ROM L2 认证被 e15 REPEAT 阻塞口径 → GR5 含翻正项；
4. 帆板参数转正（外部）触发 sim_11 全 Gate 重跑 → 传染 control_01/02 的
   帆板相对指标与 ROM L1 —— rerun_triggers 已入各计划；
5. T_c 实测（外部，H1 产出）触发带宽 Gate 重跑 → 传染 ROM R2 规则常数；
6. Physics Tool Contract 仅依赖已 PASS 工件 → **可立即实施（无上游阻塞）**。

## 并行波次（规划≤6 只读；代码≤3 写入；集成最后单跑）

- Wave 0（本轮）：状态真值 + 需求映射 + 六计划 + 红队 —— 完成即停
- Wave 1（待批，PI 收口重组）：①SAFE-00 Runtime Safety Gate；②CTRL-01 末端
  轨迹基线；③CTRL-02 反冲/消旋（三写入 Agent 互斥；SIM12-P1B 条件触发）
- Wave 2：Physics Tool Contract、ROM 选择器、VLA V0/V1/V2.5 基线、帆板转正（若到货）
- Wave 3：Physics Tool 集成 + H0/H1/H2 + 比赛演示材料
