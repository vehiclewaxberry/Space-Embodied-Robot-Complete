# Canonical Architecture — 六层唯一研究架构

> 状态基线：HEAD `c7f09ab`；机器 Gate 高于报告和计划文字。  
> 本文件收敛现有资产，不创建第四条研究主线。

## 1. 六层

| 层级 | 职责 | 当前资产与状态 | 严格边界 |
|---|---|---|---|
| L0 任务层 | 目标/场景输入、任务可行域、捕获策略选择 | sim_10、sim_12 已 PASS 并冻结 | 不授予执行；域外或 UNKNOWN 不得解释为可执行 |
| L1 安全决策层 | 汇总任务、物理、控制、时效与 provenance，输出 EXECUTE/WAIT/ABORT | SAFE-00 PASS | 当前唯一合法决策核；模块自身 `next_stage_authorized=false`，不得暗示已有执行授权；VLA、FSM、控制器不得绕过 |
| L2 控制层 | 末端任务控制、反冲抑制、捕获后稳定、未来分阶段装配控制 | CTRL-01 真实负结果收口；CTRL-02 PASS 但 `PENDING_REVIEW`/provisional；ASM-02 未实施 | CTRL-01 不是通用控制已解决；CTRL-02 的 L0 硬件有效稳定性 `NOT_EVALUATED_NO_ACTUATOR_DYNAMICS` |
| L3 世界模型层 | 刚体、自由漂浮多体、FFR、有限接触带宽、ANCF 对照、未来 ROM | sim_11 PASS_WITH_PROVISIONAL_PARAMS；e15 认证受限；ASM-01 未实施 | 保真度必须显式；域外、未建模接触态、未收敛结果返回 UNKNOWN |
| L4 具身智能层 | 感知、技能/候选生成、Physics Tools、FSM/V2.5、未来 VLA | 当前只有协议/计划 | 只提候选，不输出力矩；合法链为 `L4 → L0/L3 → L1 → L2` |
| L5 地面验证层 | CAD 数字样机、离线孪生、H0–H3、未来气浮/HIL | DT0/DT1 与局部 DT2 已有；H0–H3 未启动 | 不得称实时孪生、硬件双向闭环、微重力或在轨实物验证 |

L5 是验证平面，不是高于 L4 的自治决策层，也不产生执行授权。

## 2. 三条路线

### 稳定比赛主线：冻结交付脊柱

`目标状态输入 → sim_10 可行域 → sim_12 策略 → SAFE-00 → 离线证据解释
→ EXECUTE/ABORT 展示`

- 承担比赛主叙事与材料保底。
- 只维护证据编排和展示，不再作为新科学开发主线。
- H2/VLA 未完成前，“观察”只能称离线输入或合作标记支路。
- 装配做到哪展示到哪，不能阻塞 8 月材料冻结。

### 当前唯一候选科学实施主线：On-Orbit Assembly Wave A

`ASM-00 → ASM-01 → ASM-02 → 唯一集成 → ASM-TWIN-00`

- ASM-00：RF-1/2/3、缺失字段、来源等级与 AG0。
- ASM-01：连续接触、卡滞状态机、动量/能量账本、待单源化的 8/9 success
  schema 与 AG2/AG4；目标侧 FFR 完成前上限 `SCREENING_ONLY`。
- ASM-02：5D 接近—柔顺插接—短程 6D 锁紧，AG1/AG3；继承 CTRL-01 负结果、
  CTRL-02 provisional 边界和 W1-R12。
- 唯一集成：只能有一个原始 machine verdict。
- ASM-TWIN-00：只把真实集成结果编成标准时程、Gate 溯源和离线回放。

### 后续智能与硬件扩展：延后队列

`ROM selector → Physics Tool 合约/装配扩展 → FSM/V2.5 → VLA → H0 → H1 → H2 → H3`

- Wave A 完成不自动授权后续队列。
- V2.5 必须先于 VLA 价值声明。
- H0 未过禁止控制 B601。
- H1 的夹爪 `T_c`、接口与执行器实测是参数转正重跑触发器。
- H3 只能称地面决策—执行验证。

## 3. 冻结边

1. `sim_10 → sim_12`：可行域与策略锚点冻结。
2. `sim_10/sim_12 → SAFE-00`：任务分类只能经 fail-closed 安全核转为执行决定。
3. `sim_11 J*/FFR/contact_window → ASM-01/02`：只读复用，不复制 sim_11。
4. `CTRL-01 REPEAT真实负结果 → ASM-02`：作为相位切换、任务维度和公平基线约束。
5. `CTRL-02 PASS_WITH_PROVISIONAL_SCOPE → ASM-02`：只复用动量分账；W1-R12/R13 开放。
6. `SAFE-00 PASS核 → 所有执行链`：只允许版本化扩展合同字段，不改已 PASS 核。
7. `Gate JSON → 论文/比赛/孪生`：展示只能解释 verdict，不能抬高 verdict。

## 4. 阻塞边

1. AG0 未过，ASM-01/02 不得正式使用接口参数。
2. RF-1/2/3、销距、倒角、公差和来源未闭合，接口不得称已验证。
3. SSOT/gate registry 的八项 success 与 ASM-01 的“八项+第九项”冲突未闭合，
   HAG-A 不得批准；必须先形成一个版本化、哈希绑定的 single-source evaluator schema。
4. W1-R12 的 `0.01 N·m/轴` 统一口径和 Stage-A 重评是 ASM-02 开工前置。
5. ASM-01 接触模型冻结前，ASM-02 AC2 不得正式裁决。
6. 目标侧柔性帆板未建模或 AG4 未过，ASM-01 与唯一集成都不得判 scientific PASS。
7. 接口、`T_c`、帆板、执行器实测到位后必须按 rerun triggers 重跑。
8. 任一 UNKNOWN、未收敛或 provenance 缺失均阻塞 Wave A success。

## 5. 人工批准门

| 门 | 权限 | 不具备的权限 |
|---|---|---|
| HAG-A | 在 8/9 success 冲突闭合后，批准 Wave A 开工；冻结三卡、阈值来源、目录所有权、单源 success schema 及其哈希 | 不能在 single-source schema 缺失时批准；不能把 planning readiness 当 scientific PASS |
| HAG-B | AG0 后批准 SSOT v1 供 ASM-01/02 正式引用 | 不能把 PROVISIONAL 改成 MEASURED |
| HAG-I | 在三卡各自到 Gate 并停止后，接受 AG0–AG4、输入哈希和 provenance，批准唯一物理集成 | 不能把 screening 改成 scientific PASS；不能授予装配执行 |
| HAG-C | 接受唯一集成的 PASS/REPEAT/BLOCKED 原始 verdict | 不能人工翻转机器裁决 |
| HAG-D | 单独批准 Wave B/C | Wave A 不自动授权 ROM/VLA/HIL |
| HAG-E | 单独批准 H0 硬件资格边界 | H0 前不得驱动 B601 |

## 6. 主张边界

允许：

- sim_10/11/12 已完成，其中 sim_11 带 provisional 限制；
- SAFE-00 在冻结合同/案例下 PASS；
- CTRL-01 的真实负结果已治理收口；
- CTRL-02 在冻结 R5 PROVISIONAL 执行器及时窗模型下为 PASS，但仍
  `PENDING_REVIEW`；7/16 为 `STABILIZED_WITHIN_WINDOW`，L0 硬件有效稳定性未评估；
- Wave A 规划 `READY_WITH_INTERFACE_BLOCKERS`。

禁止：

- Wave1 PASS；
- CTRL-01 通用轨迹控制已解决；
- CTRL-02 已获硬件认证；
- 已完成自主在轨组装；
- 已形成实时数字孪生或硬件双向闭环；
- VLA 已实现、输出力矩或绕过 SAFE-00；
- 固定基座等价于自由漂浮微重力验证。
