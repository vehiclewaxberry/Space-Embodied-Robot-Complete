# NW-02 — ASM-01 Continuous Contact and Single-Source Success

> 性质：现有 `10_research/on_orbit_assembly/waveA_task_cards/ASM-01.md` 的最小授权覆盖层。  
> 登记角色：`AUTHORIZATION_REGISTRY_ONLY`；范围摘要不替代原卡。  
> 基卡：`10_research/on_orbit_assembly/waveA_task_cards/ASM-01.md`。  
> 基卡 SHA-256：`979236ea4370d5dcaa72f916756cadea687b3a48b877b79aa954985617429c39`。  
> 授权记录：HAG-A/HAG-B canonical path 见 `authorization_record_schema.yaml`
> （当前不存在；实施 Agent 禁止创建/修改）。  
> 当前：`PLANNED_NOT_AUTHORIZED`；正式消费接口数值被 AG0 阻塞。  
> 优先级：P1；可与 ASM-00 并行准备无参数骨架。

## 科学问题

持续接触、摩擦、倒角穿越与卡滞状态如何决定插接载荷、基座反应和柔性响应？

## 最小范围

1. L1 单边 KV 接触与显式状态机。
2. 包含 PREENGAGE、倒角穿越、ENGAGED、卡滞、LOCKED/FAULT 等已审查状态。
3. PREENGAGE 只允许守卫式回退；ENGAGED/卡滞只允许冻结保持。
4. 实现 HAG-A 前已闭合 8/9 冲突、版本化并哈希绑定的 single-source success
   evaluator；本卡不得自行决定是八项还是九项，ASM-02 禁止另算 success。
5. 动量/能量/接触冲量账本与未收敛 fail-closed。
6. 在 AG0 SSOT v1 到位后运行参数扫掠与 L2 抽查，输出 AG2/AG4。

## 开工前必须冻结的守恒合同

1. 系统边界固定为封闭的 `chaser + target + flex` 组合系统；组合系统中的接触力
   是内力，不得作为外功重复计入。
2. 角动量同时报告关于惯性原点和系统质心、且均在同一惯性系表达的两种口径；
   二者不得交叉比较。若使用系统质心口径，必须同时审计线动量和质心迁移。
3. 组合系统总能量只以 `W_ext + W_actuator` 为外部输入；单侧 `W_contact` 只可
   表示子系统之间的能量转移，不能同时作为组合系统外功。
4. 接触弹性储能、模态阻尼、接触阻尼、摩擦耗散与 LOCK/质量转移的非弹性损失
   分项记账并冻结正负号。
5. 零附近残差必须同时使用预注册绝对容差和相对容差，禁止只用相对误差制造 PASS。

## 输入与冻结边

- 只读复用 sim_11 的 J*/FFR/contact-window 方法，不复制或改写 sim_11。
- AG0 前只做 schema、状态机和测试骨架，不得把 v0 provisional 数字写成正式输入。
- 目标侧 FFR 未建前，Phase A 上限为 `ASM01_SCREENING_ONLY`。
- Phase A 不产生装配 scientific success，也不得上推唯一集成 PASS。

## Gate

- 作用反作用、动量、能量和接触冲量账本闭合；
- 未注册状态 → `UNKNOWN_CONTACT_STATE`；
- 未收敛 → 不得 success；
- 冻结 evaluator 的全部判据、`geometry_consistent` 与 run 级相位账本全真；
- L1/L2 关键量按预注册口径比较，e15 认证债明确携带。

## Stop condition

AG2/AG4 原始裁决出具后停止；若目标侧 FFR 未建，只能交付 screening 结果。

## 禁止声明

- 装配成功已验证；
- MuJoCo/外部工具替代柔性真值；
- 未收敛接触或 UNKNOWN 判成功。
