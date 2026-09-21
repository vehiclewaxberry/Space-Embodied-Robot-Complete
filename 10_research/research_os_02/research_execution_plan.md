# RESEARCH-OS-02 Q6 范围与证据规划执行合同

## 1. 任务裁决

- 任务编号：`RESEARCH-OS-02_Q6_SCOPE_AND_EVIDENCE`
- 执行日期：2026-07-23
- 基线 HEAD：`b75352c1c226c0f3e9a4bc9c469b766e06f41616`
- 工作性质：本地证据审计、权威在线先验核验、研究问题收敛和证据路线规划。
- 当前执行上限：文档与派生索引；不得运行科学仿真、修改 Gate、生成装配/VLA 实体或写入硬件。

## 2. 研究目标

把“在轨搭建”从宽泛愿景收敛为一个与当前项目资产一致、可证伪、可逐 Gate 解锁的问题，并回答：

1. 现有捕获/镇定证据中哪些可以复用为装配方法，哪些必须重新综合？
2. 哪些只是待写清楚的标准理论接口，哪些必须生成新的机器或实测证据？
3. Q6 如何与 Q1–Q5、Assembly Wave A、Paper Knowledge Controller 和比赛主线连接，而不升级当前科学结论？

## 3. 真值优先级

发生冲突时按以下顺序裁决：

1. 原始 Gate JSON、结果、哈希和授权记录；
2. 冻结合同、配置、接口和架构文件；
3. 当前状态与模块卡；
4. 本地 manifest、完整阅读卡和待精读 PDF；
5. NASA/NTRS 等权威在线来源与同行评议文献；
6. 本轮派生报告。

文献可以支持定义、方法、先验工作和限制，不能替代项目 Gate、实测或授权。

## 4. 当前机器边界

`30_simulation/asm_00_interface_preflight/results/asm_00_gate_check.json` 是当前装配前检真值：

- `ASM00_AG0_BLOCKED_BY_INTERFACE`
- `ASM00_BLOCKED_BY_MISSING_PARAMETERS`
- `scientific_execution_authorized=false`
- `next_stage_authorized=false`
- HAG-A/HAG-B/HAG-I 均缺失
- RF-1/2/3 均 BLOCKED
- 九判据合同结构 PASS，但合同冻结不是 HAG-A 批准

因此，本轮只能规划如何获得证据，不能开始 ASM-01/ASM-02，也不能补算或改写 RF 结果。

## 5. 方法

### 5.1 本地审计

读取 Q1–Q5、理论图谱、当前装配规划、Gate registry、ASM-00 机器裁决、文献 manifest、阅读卡和 Paper Knowledge Controller。保留所有逐字 verdict 与 UNKNOWN/PROVISIONAL/REPEAT 语义。

### 5.2 在线先验核验

优先使用 NASA、NTRS、政府战略和论文原始页面，核验三个问题：

1. servicing、assembly、manufacturing 的定义和边界；
2. 当前任务/项目状态，防止把已取消项目写成现行演示；
3. 预制接口模块装配与大型桁架装配分别需要哪些技术要素。

本轮不是 PRISMA 系统综述；在线检索结果只构成范围收敛与候选来源清单。学术新颖性继续标记 `UNASSESSED`。

### 5.3 证据分层

每项工作归入且只归入以下主类别之一：

| 类别 | 含义 | 当前是否允许 |
|---|---|---|
| `REUSE` | 原始 Gate/结果可在原适用域内直接引用 | 是，只读 |
| `RESYNTHESIS` | 重新组织既有项目/文献证据，不生成科学结果 | 是 |
| `DERIVATION_REQUIRED` | 写出待验证的理论接口、变量和证伪条件 | 是，但不得称证据已成立 |
| `MACHINE_EVIDENCE_REQUIRED` | 需要新模型运行、测试或 Gate | 否，待授权 |
| `MEASUREMENT_REQUIRED` | 需要 CAD、材料、台架或硬件实测 | 否，等待外部输入/实验合同 |
| `FUTURE_EXTENSION` | 大型桁架、多机器人、VLA、DT3/4 等后续研究 | 只登记 |

## 6. 分阶段路线

### Phase P0：问题与来源冻结（本轮）

- 建立 Q6-L1 模块装配主问题和 Q6.1–Q6.3 子问题。
- 把大型桁架降为 Q6-L2，不改现有 Wave A 主场景。
- 建立来源登记和证据待办。
- 补正 OSAM-1/2 的当前状态。

完成条件：本文档、Q6 合同、理论链、来源登记和验收报告全部通过。

### Phase P1：推导包与出处包（未来文档任务，可在不运行仿真的条件下进行）

1. 导向锥/销孔/倒角/公差的几何闭合推导；
2. 摩擦—楔紧条件、材料对、表面状态和安全裕度定义；
3. 接触事件、卡滞、过载、BACKOFF 和 UNKNOWN 状态合同；
4. 锁紧后质量、质心、惯量和目标侧柔性拓扑更新；
5. 位姿/参数误差到接触载荷、插入深度和柔性响应的传播变量定义；
6. `lee2016modulartelescope` 完整阅读卡和新在线候选来源的 SOURCE_VERIFY/DEEP_READ 裁决。

P1 只允许形成“待验证推导”，不得写成项目证据。

### Phase P2：AG0 资格化（阻塞，必须另立授权任务）

前置：HAG-A、原始哈希绑定、接口 SSOT v1、RF-1/2/3 和缺失字段全部闭合。

允许后才可建立：解析单元测试、几何/摩擦边界扫描、CAD 一致性、AG0 机器裁决。若任何前置不满足，保持 `BLOCKED`，不得启动 ASM-01/02。

### Phase P3：接触、控制、柔性和安全证据（阻塞）

按依赖顺序推进 AG1–AG5：

```text
AG0 interface
  -> AG2 contact/momentum + AG1 phase semantics
  -> AG3 control/performance
  -> AG4 flexible fidelity
  -> AG5 runtime safety
```

每一级必须产生独立 Gate、原始日志、失败样例和哈希绑定。现有 Gate 不被覆盖或重写。

### Phase P4：Q6-L2 与智能层（未来）

只有 Q6-L1 闭合后，才评估大型桁架的时变拓扑、序列优化、精度累积、多机器人和密集低频模态。VLA 只在 V2.5 确定性基线、AG5 和人工授权存在后进入 AG6 消融；数字孪生先停在 DT2 回放绑定。

## 7. 停止条件

出现任一情况立即停止并保持 BLOCKED：

1. 需要修改任何现有 Gate、结果、阈值、配置或科学代码；
2. HAG-A 缺失却要求启动 ASM-01/ASM-02；
3. 来源不能区分综述、地面演示、计划任务和在轨证据；
4. 任一 UNKNOWN 被建议改写为成功或允许；
5. 固定基座地面试验被拟称为自由漂浮/微重力等效验证；
6. 文献或外部项目被用来替代本项目机器证据。

## 8. 本轮验收 Gate

只有同时满足以下条件，才可裁决 `RESEARCH_OS_02_Q6_SCOPE_READY_EXECUTION_BLOCKED`：

1. Q6-L1/L2 分层明确，未创建与 `10_research/on_orbit_assembly/` 冲突的第二架构。
2. Q6 与 Q1–Q5 的复用和新增证据边界逐项明确。
3. OSAM-1/2 状态与 NASA 当前页面一致。
4. 每项待办标明证据类型、前置 Gate、禁止升级和优先级。
5. Q6 仍保留 `scientific_execution_authorized=false` 和 `next_stage_authorized=false`。
6. 所有新增 Markdown 路径与链接可解析，CSV 严格列宽、UTF-8 可读。
7. `30_simulation/` 科学资产、Gate、结果、`20_engineering/config/` 和冻结架构无本轮改动。

## 9. 回滚策略

若验收失败，只移除/修正本轮新增的 `research_os_02`、Q6 合同、Q6 理论导航和本轮明确更新的入口文字；不触碰用户既有未提交改动或任何科学资产。

