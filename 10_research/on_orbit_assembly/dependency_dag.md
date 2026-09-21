# Assembly Research DAG — 2026-07-20

```
[冻结底座]                          [Wave1 产出]
sim_11 J*/FFR/接触带宽 ─┬─────────  SAFE-00(PASS) ── 扩展(装配reason_code)
sim_10/12 可行域+策略   │           CTRL-02(PASS) ── 轮/推分账复用(先解W1-R12)
CTRL-01 负结果(设计依据)│           CTRL-01 REPEAT──相位切换必要性证据
                        ▼
        ASM-00 接口SSOT（AG0）
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                │
  ASM-01 接触动力学   ASM-02 分阶段控制   │
  （AG2/AG4）◄────────►（AG1/AG3，互提供 │
        │      接触模型/轨迹激励）        │
        └───────┬────────┘               │
                ▼                        │
        Wave A 唯一集成（ASSEMBLY_PHYSICS_{PASS,REPEAT,BLOCKED}）
                ▼
  Wave B: ASM-03 序列FSM + ASM-04 Physics Tools 装配扩展 + ROM选择器 + SAFE-00扩展（AG5）
                ▼
  Wave C: ASM-05 VLA(V0..V3, AG6) + ASM-06 地面验证(H0→H1[T_c/接口实测]→H2→H3)
```

## 硬依赖边
1. ASM-00 的 AG0 未过 → ASM-01/02 禁用其参数（fail-closed 引用）；
2. **W1-R12 轮力矩档统一是 ASM-02 开工前置**（AR2）；
3. ASM-01 的接触模型冻结先于 ASM-02 的 AC2 阻抗基线正式裁决（内部基线可并行）；
4. SAFE-00 装配扩展仅新增合同字段，不改已 PASS 裁决核（回归界=47/47 原样绿）；
5. VLA/序列/硬件不得绕过 AG0–AG5 上游 Gate；
6. 外部触发继承：接口实测/夹爪 T_c/帆板参数卡/轮组选型 → rerun_triggers。

## 波次（代码≤3 写入 + 唯一集成；规划≤6 只读）
Wave A：ASM-00 ∥ ASM-01 ∥ ASM-02 → 集成裁决；
Wave B：序列+工具+ROM+安全扩展；Wave C：VLA 对照+地面演示（禁称微重力）。
与比赛线的资源仲裁见 risk_register AR7。
