# Master Plan — On-Orbit Assembly Closure Phase — 2026-07-20

> 规划轮完成态：只读规划，零科学代码、零仿真、零提交。实施前须人工批准。

## 最终裁决

**`READY_WITH_INTERFACE_BLOCKERS`**

依据：①R1 唯一 FATAL（AG3-b success 六/八合取洗白路径）**有明确修法**且已折入
ASM-01/02 卡（success 单源求值 + control_failure_rate 解耦），不构成控制地基
阻塞（CTRL-01 负结果反而是分阶段设计的证据基础）；②接口侧存在真实阻塞组：
RF-1 锥面聚拢 2.14mm<5mm 几何不自洽、RF-2 楔紧边界、RF-3 clearance 语义、
SSOT 缺销距/倒角字段、全卡无 MEASURED 出处——**这些是 ASM-00 的 LOOP-1 入口
判据而非停工理由**；③结构性缺口"目标星带帆板 vs sim_11 帆板在追踪星侧"以
`ASM01_SCREENING_ONLY` 上限治理（Phase B 目标侧 FFR 建成前禁判装配成功）；
④外部参数（接口实测/夹爪/帆板卡）只限制出处等级，verdict 词表强制
`_WITH_PROVISIONAL_PARAMS`。无状态冲突。

## 文件索引

| 文件 | 作者 |
|---|---|
| state_truth_and_scope.md（AG-A0 PASS） | PI |
| interface_ssot_draft.yaml（v0 + B 注释 + RF 红旗登记） | PI+B |
| interface_mechanics_plan.md / phased_control_plan.md / contact_flexible_dynamics_plan.md / rom_safety_plan.md / vla_sequence_plan.md | B/C/D/E/F |
| gate_registry.yaml、risk_register.csv、claim_evidence_matrix.csv、file_ownership_matrix.csv、dependency_dag.md | PI |
| red_team_assembly_control.md（1 FATAL 可修 + 6 组 NEEDS_FIX）/ red_team_assembly_safety.md（6 组 NEEDS_FIX 无 FATAL） | R1/R2 |
| waveA_task_cards/{ASM-00,ASM-01,ASM-02}.md（红队修订已折入卡尾） | PI |

## 红队修订清单（Wave A 开工前置，已入卡；此处为跨卡项）

1. **AG3-b FATAL**：success 由 ASM-01 单源函数求值，九判据（补接触历史合规）
   + geometry_consistent + run 级相位账本；"八项"硬编码 ≥4 处协同改；
2. 公式统一：两点接触角（直径口径）与 Whitney 归一化在 ASM-00/01 一致化（差因子 2）；
3. 安全语义：接触内过期 BACKOFF 拆双子态（ENGAGED/卡滞→冻结保持，
   PREENGAGE→守卫式回退）；reason_code 机器绑定（封 vla 计划中 4 个野码）；
   phase 需可信运动学见证字段；
4. AG6 增合法收口词 `AG6_NOT_EVALUATED_NO_VLA_ENTITY`（9/1 前无 VLA 实体时
   V2.5 先行，禁称 VLA 价值）；
5. PLANNED 工具转正须合约版本递增激活 + 三类转正负例（防静默转正）；
6. W1-R12：统一 0.01 N·m/轴 + 重评不关闭该风险项。

## Wave 结构（代码≤3 写入 + 唯一集成）

- **Wave A（待批）**：ASM-00 ∥ ASM-01 ∥ ASM-02 → 唯一集成 →
  `ASSEMBLY_PHYSICS_{PASS,REPEAT,BLOCKED}`（verdict 强制带
  `_WITH_PROVISIONAL_PARAMS`；ASM-01 上限 SCREENING_ONLY）；
- Wave B：ASM-03 序列 FSM + ASM-04 Physics Tools/SAFE-00 扩展（AG5）+ ROM 选择器；
- Wave C：ASM-05 VLA 对照（V2.5 先行）+ ASM-06 地面验证（H0→H3，禁称微重力）。

## 两周计划与比赛仲裁（AR7）

W1：三卡红队修订折入并 PI 冻结 → Wave A 三 worktree 开工（LOOP-0..2）；
W2：ASM-00 出 AG0 裁决（RF 全解或 BLOCKED 清单）、ASM-01 L1 最小闭环 +
状态机、ASM-02 QP 骨架 + AC0/AC1 先行。**比赛材料主线独立于装配线**：
以已闭合链（捕获→可行域→策略→SAFE-00→数字孪生）为主叙事，装配线做到哪
展示到哪，8 月中材料冻结时不依赖 Wave A 结果。

## 需求满足度快照

R4 刚柔耦合/R6 策略/安全裁决=已闭合可引用；R2 末端控制=CTRL-01 负结果限定
表述 + ASM-02 为装配语境续章；R3 姿态=CTRL-02 PASS 复用；R1 VLA=协议就绪、
实体待 Wave C；装配四能力（接口/接触控制/序列验证/VLA 语义）=本阶段主攻。
