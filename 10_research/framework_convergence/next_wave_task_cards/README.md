# Next Wave Task Cards — Authorization Overlays

这些文件是对现有 `10_research/on_orbit_assembly/waveA_task_cards/` 的
**授权登记与 fail-closed 约束层**，不是平行计划，也不替代详细任务卡。卡内范围
摘要均为非规范性导航；正式范围以原卡、机器 Gate 与有效人工授权工件共同约束。

当前总状态：`PLANNED_NOT_AUTHORIZED / WITH_INTERFACE_BLOCKERS`。

机器授权 schema：
`authorization_record_schema.yaml`。它只是校验模板，不是批准。实际记录的 canonical
path 是 `10_research/on_orbit_assembly/approvals/HAG-{A,B,I}.yaml`；当前均不存在。
实施 Agent 不得创建或修改这些记录，只能验证由 PI/受信系统签发的真实性证明。

| 顺序 | 覆盖层 | 现行详细卡 | 当前放行状态 |
|---|---|---|---|
| 1 | `NW-01_ASM-00_INTERFACE_QUALIFICATION.md` | `ASM-00.md` | 待 HAG-A；获批后可立即做 RF/AG0 |
| 2 | `NW-02_ASM-01_CONTACT_DYNAMICS.md` | `ASM-01.md` | 可做独立骨架；正式参数消费等 AG0 |
| 3 | `NW-03_ASM-02_PHASED_CONTROL.md` | `ASM-02.md` | 被 W1-R12 与 AG0 阻塞 |
| 4 | `NW-04_ASM-TWIN-00_OFFLINE_REPLAY.md` | 无独立旧卡；受唯一集成约束 | 等真实 ASM 结果，不得先做演示 |

纪律：

1. 科学代码实施须另经人工批准。
2. 不修改冻结 sim_01–12、SAFE-00、CTRL-01/02 或现有 Gate。
3. 不修改阈值制造 PASS；负结果和 UNKNOWN 原样保留。
4. 一个 Wave A、三个互斥所有权子任务、一个唯一集成者。
5. 每张卡到 stop condition 后停止，等待人工批准。
6. HAG-A 前必须关闭 success 8/9 项冲突，把唯一 schema 的路径与 SHA-256 写入
   授权记录；不得由实施 Agent 自选八项或九项。
7. 优先级：机器 Gate/冻结结果 > 本目录 fail-closed 阻塞条件 > 已验证且未过期的
   人工授权所允许的窄范围 > 原详细卡 > 本目录非规范性摘要。授权不得放宽门槛。
