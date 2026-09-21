# Next Research Plan — Active Mainline Authorization

## Material Passport

- schema: `ARS-9`
- artifact_id: `FRAMEWORK-CONVERGENCE-NEXT-PLAN-20260720`
- artifact_type: `experiment_plan`
- mode: `plan`
- status: `DRAFT_PENDING_HUMAN_AUTHORIZATION`
- evidence_snapshot: HEAD `c7f09ab80580f5810d75253fd836d412aa862460`
- next_gate: `HAG-A`

## 1. 唯一最终裁决

**`FRAMEWORK_CONVERGED_WITH_INTERFACE_BLOCKERS`**

```text
NEXT_WAVE_SELECTED = ON_ORBIT_ASSEMBLY_WAVE_A
AUTHORIZATION = PLANNED_NOT_AUTHORIZED
START_CONDITION = HAG_A_APPROVED
CURRENT_BLOCKERS = RF_1_RF_2_RF_3 + SUCCESS_SCHEMA_8_VS_9 + TARGET_SIDE_FFR_AG4 + W1_R12_R13
EXTERNAL_MINIMAL_WAVE = DEFERRED_NON_BLOCKING_AUXILIARY
```

选择候选 A，不把候选 B 设为主要实施波次。Wave A 尚未自动获批：

- HAG-A 前必须先闭合 success 8/9 项冲突，冻结唯一 evaluator schema 和哈希；
- ASM-00 获批后可立即开始 RF-1/2/3 资格化；无法闭合则输出 `BLOCKED`；
- ASM-01 可并行准备不依赖正式接口值的状态机/账本骨架；
- ASM-02 被 W1-R12 与 AG0 阻塞；
- AG0 未过前，ASM-01/02 不得把 v0 参数当合格输入，不得出装配成功；
- ASM-01 Phase A 上限仍为 `ASM01_SCREENING_ONLY`；
- 比赛主线继续使用已闭合捕获链，不依赖 Wave A PASS。

## 2. 项目真正完成到哪

已完成并有当前证据支撑：

`冻结基础动力学 → sim_10 任务可行域 → sim_11 参数受限刚柔/有限带宽
→ sim_12 策略选择 → SAFE-00 → CTRL-02 参数受限 PASS
+ CTRL-01 真实负结果收口 → Wave1 负结果治理收口 → 局部 DT2 离线回放`

未完成：

- ASM-00/01/02 数值实施与 Gate；
- ASM-TWIN-00；
- 当前全链 DT2、DT3/DT4；
- ROM/Physics Tools/V2.5/VLA；
- B601 H0–H3；
- 外部独立框架对拍。

## 3. 唯一候选科学实施主线

`ASM-00 接口资格化 → ASM-01 持续接触与单源成功判据
→ ASM-02 5D接近—柔顺插接—6D锁紧
→ Wave A 唯一集成 → ASM-TWIN-00 离线装配回放`

比赛链是冻结交付脊柱；ROM/VLA/硬件/外部工具是延后队列，均不是第二主线。

## 4. 已冻结、禁止重做

- sim_01–08 基础数值资产；
- sim_10、sim_11 v1.1、sim_12 Phase1；
- SAFE-00；
- CTRL-01 已修缺陷与真实负结果；
- CTRL-02 当前 provisional 范围内裁决；
- Wave1 原始 `WAVE1_REPEAT` 与 CP6 收口；
- VIZ-Gate0 冻结包；
- 12U+B601 主构型、frame tree 与现行 SSOT 路径；
- 在轨组装现有 15 个规划/审计文件 + 3 张任务卡（共 18 个文件）；
- HEAD c7f09ab 已完成的七份归档。

## 5. 当前可发表/比赛引用的结论

1. 冻结任务模型下，捕获任务可行域可由转速、轮组、推进剂与时间门分区；
   sim_10 verdict=`SIM10_GATES_PASS`，执行机构档/时限/柔性限定必须随行。
2. sim_11 在占位帆板和 `T_c` 条件下通过 G1–G5；理想冲量的模态能量指标不适定，
   有限接触带宽恢复收敛。必须写 `PASS_WITH_PROVISIONAL_PARAMS`。
3. sim_12 的 16 例证明策略选择依赖 active binding gate；在 B_anchor 冻结案例中，
   S2 使接触冲量模 `|J|` 下降，但使关于系统质心、在惯性系表达的 `|H|` 上升；
   外部矢量角冲量 `|ΔH_vec|` 与 `|H|` 标量变化不得混用，也不能给无条件策略排序。
4. SAFE-00 在冻结合同与预注册案例下实现 UNKNOWN 永不 ALLOW 与绕过 fail-closed。
5. CTRL-01 的真实负结果可作为“严格 6D/冻结增益/预注册轨迹下的设计边界”，
   不是控制器普遍优越性。
6. CTRL-02 的 `review_status=PENDING_REVIEW`；7/16 在 R5 PROVISIONAL 执行器及时窗
   模型下满足 `STABILIZED_WITHIN_WINDOW`，9/16 未满足；L0 硬件有效稳定性
   `NOT_EVALUATED_NO_ACTUATOR_DYNAMICS`，不能外推硬件。
7. 项目已有 DT0、DT1 和旧 campaign 局部 DT2 离线回放。

## 6. 当前禁止的强结论

- Wave1、CTRL-01 或 e15 ANCF 已 PASS；
- 刚体 PASS 等于柔性/接触/装配安全；
- sim_10 是真实硬件可行域；
- CTRL-02 已证明硬件稳定或轮组可消除总角动量；
- 当前已有实时数字孪生、HIL 或双向硬件闭环；
- 已完成自主在轨装配；
- VLA 已实现、可输出力矩或可绕过 SAFE-00；
- Physics Tool 已实现、运行时不可绕过 SAFE-00，或其草案中的调用方
  `scenario_hash` 已构成可信授权；
- 捕获阶段 VLA 已具备同工具确定性 V2.5 对照或可归因净增益；
- MuJoCo/SPART/Pinocchio/Basilisk 是柔性或接触真值；
- 固定基座/气浮台等价于空间微重力六自由度验证；
- 测试 PASS 代替科学 Gate PASS。

## 7. 选择 Wave A 的证据

| 证据 | 决策含义 |
|---|---|
| `10_research/on_orbit_assembly/` 已有完整规划与三卡 | 不应再规划；应解除阻塞并实施 |
| `READY_WITH_INTERFACE_BLOCKERS` | 问题是接口资格，不是重新选题 |
| SSOT 无 MEASURED 且 RF-1/2/3 未闭合 | 这是首要接口资格阻塞；另有 8/9 success schema、FFR/AG4 与执行器阻塞 |
| ASM 接口/接触/控制均 NOT_STARTED | Wave A 可解锁新增科学声明 |
| 外部工具只能核对刚体/ADCS | 候选 B 不能解除接口、持续接触或目标侧柔性 |
| sim_10/11/12、SAFE、CTRL-02 可复用 | Wave A 可增量实施，不需重建 |
| 2026-09-01 与 AR7 | 外部接入不得占两周主线或比赛材料路径 |

## 8. 三项立即任务

### TASK-NOW-1：ASM-00 接口资格化

- 关闭 RF-1/2/3；
- 补锥口/喉半径、销距、倒角；
- 冻结 clearance 语义；
- 处理 `tan(15°)≈0.268 < μ=0.3` 楔紧边界；
- 建立单源公差链和解析/采样对拍；
- 输出 AG0 verdict；字段不可求值则输出 BLOCKED，不猜值。

### TASK-NOW-2：ASM-01 最小持续接触闭环

- 单边 KV、摩擦耗散、触离事件；
- 倒角穿越、双销、卡滞/楔紧状态；
- 未注册态 `UNKNOWN_CONTACT_STATE`；
- success 由 HAG-A 前闭合 8/9 冲突后的版本化单源 evaluator 求值；不得预设九项；
- 目标侧 FFR 未建时上限 `SCREENING_ONLY`；
- AG0 前只做合同/骨架，不出正式成功裁决。

### TASK-NOW-3：ASM-02 分阶段控制最小比较

- 先统一 W1-R12=`0.01 N·m/轴` 并重评，且不关闭风险；
- 形成 AC0 全程 6D 与 AC1 5D→短程6D 的公平基线；
- success 只消费解决 8/9 冲突后哈希绑定的 ASM-01 单源 evaluator；
- `control_failure_rate` 与物理 success 分开；
- ASM-01 模型冻结前不裁决 AC2；
- 不把 CTRL-01 负结果写成“控制已解决”。

## 9. 三项推迟任务

1. **外部最小对拍**：Pinocchio 三刚体锚点 + Basilisk 一 ADCS 锚点放在 Wave A
   首个 machine verdict 后，且只能用独立资源。
2. **MuJoCo/Isaac Sim/VLA 环境**：等 ASM-01 接触合同、ASM-03 FSM、V2.5 与
   SAFE-00 装配扩展冻结。
3. **气浮台、Adams、SpaceDyn 执行**：气浮台进入赛后 H0–H3；Adams
   `NOT_NEEDED`；SpaceDyn `AUDIT_ONLY`。

## 10. 两周研究计划

### 第 1 周：接口资格与最小骨架

- 先闭合 8/9 success schema；验证由 PI/受信系统外部签发且未过期的 HAG-A，
  再冻结 Wave A 输入、所有权、Gate 词表与禁止声明；
- ASM-00 集中关闭 RF-1/2/3、出处与公差链；
- ASM-01 并行完成状态机、UNKNOWN 合同、账本与名义骨架；
- ASM-02 完成 W1-R12 统一口径和 AC0/AC1 公平基线；
- 所有 v0 参数保持 PROVISIONAL。

周末：

- AG0 PASS → 允许正式消费 SSOT v1；
- AG0 BLOCKED → 冻结阻塞清单，ASM-01/02 维持骨架/SCREENING；
- 不因进度放宽公差或 success 判据。

### 第 2 周：最小证据链与唯一集成

- ASM-01 完成名义矩阵、卡滞例、账本和交叉求解检查；
- ASM-02 完成 AC0/AC1 首轮比较；AC2 只在接触模型冻结后进入；
- ASM-01/02 各自到 Gate 后停止；HAG-I 未批准前不运行唯一集成；
- HAG-I 有效后，唯一集成者核对输入哈希、单位、参考点和 Gate 依赖；
- 目标侧 FFR/AG4 未闭合时，scientific PASS 不可达；输出且只输出一个：
  `ASSEMBLY_SCREENING_COMPLETE_WITH_PROVISIONAL_PARAMS`、
  `ASSEMBLY_PHYSICS_REPEAT` 或 `ASSEMBLY_PHYSICS_BLOCKED`；
- 只有目标侧 FFR 完成且 AG4 PASS 后，才允许
  `ASSEMBLY_PHYSICS_PASS` 或 `ASSEMBLY_PHYSICS_PASS_WITH_PROVISIONAL_PARAMS`；
- 出具后停止，等待人工批准。

## 11. 六周比赛计划

| 周 | 主任务 | 禁止扩张 |
|---|---|---|
| 1–2 | HAG-A 有效后做 Wave A 最小实施；取得各自首轮 Gate，HAG-I 有效时才运行唯一集成 | 不扩场景、不接新求解器 |
| 3 | 只修证明过的实现缺陷；真实负结果/UNKNOWN 原样；独立资源可做四锚点外部对拍 | 不为 PASS 调参 |
| 4 | 比赛证据整合；主叙事固定捕获链；Wave A 只加入有 Gate 的部分 | 不启动 MuJoCo/Isaac/VLA/硬件 |
| 5 | 冻结正文、图表、视频、Gate 摘要与哈希；双红队主张审计 | 不隐去 PROVISIONAL/SCREENING/负结果 |
| 6 | 打包、链接、哈希、恢复演练、答辩演练、离线备份 | 不新增模型、VLA、气浮台或临时重写真值 |

### 责任、资源与超时合同

- `T0` 定义为有效 HAG-A 的 `approved_at`；两周计划使用 `T0+14d`，不把当前日期
  伪装成已开工日期。
- HAG-A 必须把 ASM-00/01/02 的实名 owner、唯一 integrator、owned paths 与
  `expires_at` 写入授权记录；未绑定即 BLOCKED。
- 资源上限：最多 3 个互斥写入 owner + 1 个唯一集成者；本波次不占用外部工具、
  VLA、B601、气浮台或大规模仿真资源。
- 任一 Gate 超过授权有效期、依赖未到位或 owner 冲突：原样输出
  `BLOCKED/DEFERRED`，不得延长授权、放宽阈值或自动进入下一阶段。
- 比赛硬截止仍为 2026-09-01；Wave A 延期不得移动比赛冻结脊柱。

## 12. 中央文件更新检查

| 文件 | 本轮动作 | 结论 |
|---|---|---|
| `10_research/README.md` | 已最小更新 | 补 review/provisional、现行框架索引与 Wave A 授权状态 |
| `10_research/research_state_v4.md` | 已最小更新 | 补 SAFE/CTRL-02 review/provisional 与 Wave A 授权阻塞 |
| `01_project/competition/项目现状总览_20260720.md` | 已最小更新 | 修正 sim_01–08 证据层级、J/H、SAFE/CTRL-02 和 DT2 边界 |
| `CLAUDE.md` | 已最小更新 | 修正 J/H、SAFE/CTRL-02 与当前唯一候选科学主线 |

`10_research/README.md` 也已最小更新并链接本证据矩阵；`.codex/AGENTS.md` 等活跃
状态指针同步去除了 sim_12 “仍在研”冲突。归档仍只产动作计划，未移动文件。

## 13. 下一条可直接执行的 `/goal`

```text
/goal
实施 ON-ORBIT ASSEMBLY WAVE A 的最小两周证据链：
申请 HAG-A 前，由 PI/Research Framework Curator 闭合 SSOT/gate registry 八项
与 ASM-01“八项+第九项”的冲突，形成唯一、版本化、哈希绑定的
single_source_success_schema；实施 Agent 不得自行选择八项或九项。
开工前必须存在有效的 machine-readable HAG-A approval record，绑定
authorization_id、approver、approved_at、approved_commit、任务卡哈希、owned paths
和 expires_at；任一字段缺失、过期或与当前 HEAD 不符时立即输出
BLOCKED_BY_MISSING_HAG_A_AUTHORIZATION 并停止，不写科学代码。
canonical record path 为 `10_research/on_orbit_assembly/approvals/HAG-A.yaml`，
按 `10_research/framework_convergence/next_wave_task_cards/authorization_record_schema.yaml`
验证；实施 Agent 禁止创建/修改该记录，真实性证明不可验证时同样 BLOCKED。
先完成 ASM-00 的 RF-1/RF-2/RF-3 与 AG0；
再让 ASM-01 形成持续接触、卡滞、守恒与已哈希绑定的单源成功评价；
让 ASM-02 在 W1-R12=0.01 N·m/轴统一口径下完成 AC0/AC1 公平比较；
三卡各自到 Gate 后停止；只有 HAG-I 接受 AG0–AG4、输入哈希和 provenance 后，
唯一集成者才能输出原始 ASSEMBLY_PHYSICS verdict。
不修改冻结 30_simulation/SAFE/CTRL/Gate，不放宽阈值，不自动进入下一波。
```

## 14. 下一条可直接执行的 `/plan`

```text
/plan
1. 先闭合 SSOT/gate registry 八项与 ASM-01“八项+第九项”的冲突，生成版本化
   single-source success schema 及哈希；然后校验 machine-readable HAG-A approval
   record 的 canonical path、schema 与外部真实性证明。实施 Agent 禁止创建或修改
   approval；任一缺失/过期/HEAD或任务卡哈希不符即 BLOCKED 并停止。
2. ASM-00 关闭 RF-1/2/3 并输出 AG0；不可求值则 BLOCKED。
3. ASM-01 仅做单边持续接触、状态机、账本、UNKNOWN 与已冻结的 single-source
   success evaluator；AG0 前不正式消费参数。
4. ASM-02 先统一 W1-R12=0.01 N·m/轴，完成 AC0/AC1；AG0/接触模型未过不裁决 AC2。
5. 三卡各自完成首轮 Gate 后停止；HAG-I 未批准前不运行唯一集成。
6. HAG-I 有效后，唯一集成者核对哈希、参考系、单位和 Gate 依赖，输出一个原始
   physics verdict；该 verdict 不构成 SAFE-00 装配执行授权。
7. 出具后停止，等待 PI 人工审批；不启动外部工具、ROM、VLA、Isaac Sim、气浮台或B601控制。
```
