# Red Team System Review — R2

> 审查角色：空间具身智能与竞赛系统审稿人  
> 审查对象：`10_research/framework_convergence/` 及其中央状态指针  
> 审查方式：只读；未运行仿真或测试

## 1. 总裁决

**支持 `FRAMEWORK_CONVERGED_WITH_INTERFACE_BLOCKERS`。**

该裁决只表示框架、唯一候选主线和授权边界已经收敛，不表示 Wave A 已获批或
已具备 scientific PASS 条件。

```text
R2_VERDICT = ACCEPT_WITH_MANDATORY_BLOCKERS
FRAMEWORK_STATUS = FRAMEWORK_CONVERGED_WITH_INTERFACE_BLOCKERS
WAVE_A_AUTHORIZATION = PLANNED_NOT_AUTHORIZED
HAG_A_AUTHORIZABLE_NOW = NO
FATAL = 0
```

## 2. 初审攻击与回修

| 初审问题 | 初审等级 | 最新状态 |
|---|---:|---|
| success 同时存在“八项”和“八项+第九项” | HIGH | 保留为 HAG-A 前硬阻塞；实施 Agent 禁止选边 |
| `/goal` 可在授权冲突下直接启动科学代码 | FATAL | 已统一 `PLANNED_NOT_AUTHORIZED`；授权缺失/过期/哈希不符/真实性不可验证均 BLOCKED |
| DAG 可跳过 HAG-B 或集成前人工门 | FATAL | 已分 HAG-A/B/I；ASM-01/02 采用显式 AND 放行；各任务到 Gate 后先停止 |
| 当前 SAFE-00 被误读为装配执行许可 | HIGH | 只作物理集成 fail-closed 语义审计；AG5 前不产生装配 `EXECUTE` |
| sim_12、SAFE、CTRL-02 中央状态过期或过强 | HIGH | README、state v4、比赛总览、CLAUDE、AGENTS 已最小同步 |
| Physics Tools 与 V2.5/VLA 成熟度被高估 | HIGH | C23/C24 已回到 `DRAFT_NOT_IMPLEMENTED/NOT_EVALUATED`，可信绑定和捕获 V2.5 缺口在案 |
| 新卡形成第二套规范且无真实批准 | HIGH | 降为 `AUTHORIZATION_REGISTRY_ONLY`；基卡哈希绑定；实际 HAG-A/B/I 均不存在 |
| 外部工具侵占比赛/Wave A | HIGH | `NOW=0`；仅保留后续、资源有上限的 cross-validation |
| 固定基座/气浮台冒充自由漂浮/微重力 | HIGH | twin、工具与禁止声明均已显式禁止 |
| `NO_UPDATE_REQUIRED` 掩盖中央冲突 | HIGH | 必要入口已实际更新，审计表与动作计划同步 |

## 3. 必须保留的 blockers

### HIGH-01 — 8/9 success schema 未闭合

实际 SSOT/Gate 与 ASM-01 任务卡仍存在成功判据基数冲突。本轮正确地没有替 PI
选择。HAG-A 前必须形成一个版本化、哈希绑定的
`single_source_success_schema`，并同步 SSOT、Gate registry、任务卡引用与授权记录。

```text
HAG_A = INVALID
ASM01_FORMAL_VERDICT = BLOCKED
ASSEMBLY_PHYSICS_PASS = UNAVAILABLE
```

### HIGH-02 — 人工授权记录不存在

当前以下 canonical records 均不存在：

- `10_research/on_orbit_assembly/approvals/HAG-A.yaml`
- `10_research/on_orbit_assembly/approvals/HAG-B.yaml`
- `10_research/on_orbit_assembly/approvals/HAG-I.yaml`

这是符合设计的 fail-closed 状态。实施 Agent 不得创建或修改这些记录；只能验证
PI/受信系统的外部签发与真实性证明。

### HIGH-03 — Physics Tools 尚无可信运行授权能力

`tool_contract_draft.yaml` 仍为 v0 draft：

- `scenario_hash` 由调用方自报；
- 缺 request ID、主体/阶段绑定、有效期与重放保护；
- provenance 未强制绑定全部源 Gate/CSV 哈希；
- `EXECUTE_UNDER_ASSUMPTIONS` 易被误读为令牌；
- 严格 schema 与结构化错误合同不足。

该项阻塞未来 Tools/VLA 波次，不阻塞当前 Wave A 物理研究。正式实施前应把输出
降为 `CANDIDATE_FOR_SAFE_REVIEW` 类建议语义，并在 T-Gate 攻击哈希漂移、过期与
重放。

### HIGH-04 — 捕获阶段缺同工具确定性 V2.5

装配协议已有严格 V3-vs-V2.5 配对；捕获协议仍只有 V0/V1/V2/V3。补齐相同
Physics Tools、Gate、scenario hash、种子和版本的确定性 V2.5 前，不得声明捕获
阶段 VLA 净增益。

## 4. 系统边界复核

- VLA 没有被写成已实现、端到端控制或力矩源。
- Physics Tools 没有被写成当前不可绕过的运行时安全系统。
- L4 只能提候选；合法意图链仍是 `L4 → L0/L3 → L1 → L2`。
- 当前 SAFE-00 对 Wave A 只提供审计语义，不提供装配执行许可。
- H0 未过禁止控制 B601。
- 固定基座、气浮台、CAD 和视频均不等于自由漂浮、微重力或在轨验证。
- 外部工具 `NOW=0`，不形成第二主线。
- 比赛冻结脊柱不依赖 Wave A PASS。

## 5. 回修后剩余 MEDIUM

1. `authorization_record_schema.yaml` 是机器可读规则清单，不是完整可执行 validator；
   正式 HAG-A 前仍需字段类型、时间格式、签名/验证者、前序授权依赖和未知字段
   拒绝规则。
2. 授权覆盖卡仍保留少量非规范性范围摘要；后续可进一步压成纯 delta，并机械校验
   基卡哈希。

本轮已按 R2 建议补：

- NW-03 将相位切换改为 prospective SAFE request；AG5 前不得装配 `EXECUTE`；
- state truth 同时引用捕获协议与装配 V2.5 配对协议；
- 两周/六周计划增加 owner、资源上限、`T0`、有效期和超时 BLOCKED/DEFERRED 合同。

## 6. 最终意见

回修后已消除多主线、隐式授权、SAFE-00 自动外推、VLA 抢跑、外部工具抢占以及
固定基座冒充空间验证等系统级缺陷。因此以下裁决准确：

**`FRAMEWORK_CONVERGED_WITH_INTERFACE_BLOCKERS`**

必须同时发布：

```text
WAVE_A = PLANNED_NOT_AUTHORIZED
HAG_A = NOT_YET_VALID
MANDATORY_PRE_HAG_A_BLOCKER = SUCCESS_SCHEMA_8_VS_9
NO_SCIENTIFIC_CODE_BEFORE_VALID_EXTERNAL_APPROVAL
```
