# 红队审查报告：装配阶段安全线（ROM×SAFE-00 扩展 / VLA 序列 / AG5-AG6）— 2026-07-20

> 角色：空间具身智能与安全审稿人（红队，只读）。本文件为本轮唯一输出；未修改任何被审文档或冻结证据。
> 被审对象：`10_research/on_orbit_assembly/{rom_safety_plan.md, vla_sequence_plan.md, gate_registry.yaml, claim_evidence_matrix.csv, state_truth_and_scope.md}`。
> 对照基线（逐项磁盘核实）：`20_engineering/config/safety_gate/`（v1 三 schema + `safety_policy_v1.yaml`）、
> `30_simulation/safety_00_runtime_gate/{src/safety_core.py, results/safety_00_gate_check.json}`（verdict=PASS，16 例逐一在案）、
> `10_research/vla/tool_contract_draft.yaml`、`10_research/rom/model_fidelity_selection_rules.yaml`、
> `10_research/partner_requirement_closure/red_team_vla.md`（攻击面⑤ A1–A7、攻击面⑥ 五组合）、
> `10_research/on_orbit_assembly/{interface_ssot_draft.yaml, contact_flexible_dynamics_plan.md}`。

---

## 攻击点① SAFE-00 装配扩展"零改裁决核"主张

**裁决：NEEDS_FIX（零改主张本身成立；但 reason_code 注册无机器绑定 + 相位声明无独立见证，两个真实缺口）**

**成立的部分（磁盘核实）**：
- 命名空间零冲突声明属实：从 `safety_core.py` 逐串提取 62 个大写常量（含全部 reason_code），无一以 `ASM` 起头；"40+ 项"数量声明成立。
- 判例引用全部核实：`safety_00_gate_check.json` cases 数组中 B1_FORGED_PROVENANCE→`GATE_ARTIFACT_HASH_MISMATCH`、B2→`EVIDENCE_STALE`、B5/B7→`REQUEST_SCHEMA_INVALID`、B6/D2→`L2_FAILED_NO_OPTIMISTIC_FALLBACK`、B10→`TEMPORAL_ORDER_INVALID`、B11→`SCENARIO_HASH_MISMATCH`、D1→`FALLBACK_DOMAIN_UNCHECKED` 与计划引文逐一对得上。
- 架构分离干净：v1 响应 schema `contract_version` 为 `const: safety-gate-v1` 且 `additionalProperties:false`——ASM 响应（`safety-gate-asm-v1`）**结构上不可能**冒充 v1 响应；§2.4 回归界五条均为机器可判。
- phase 入 scenario_hash 的实现路径成立：`compute_scenario_hash()`（safety_core.py L185–201）对**整个** request+evidence payload 做 canonical 哈希，只剔除 `scenario_hash`/`request_id` 自引用字段。只要 asm_request schema 把 `phase`/`phase_instance_id` 列为 required 并 import 复用该函数，phase 自动进入哈希定义域，无需改核。AG5-B 已含"旧口径无 phase 请求"负例。

**缺口 1：reason_code 注册表没有机器落点（pattern 过宽 = 词表漂移面）**。
v1 pattern `^[A-Z0-9_]{1,96}$` 在 v1 内不构成注入面（reason_code 由裁决核生成，非客户端字段），但扩展若照抄该 pattern，则**任何**未注册大写串都能通过 asm_response 校验。且词表分裂已经发生：`vla_sequence_plan.md` §6 末尾发明了 `ASM_CONTACT_OOD / ASM_LATCH_UNKNOWN / ASM_FLEX_WAIT / ASM_WHEEL_MARGIN` 四个码——**没有一个**出现在 `rom_safety_plan.md` §2.1 的 11 码注册表里。这正是红队 A7"两套并行词表，实现期路由到较松一套"在装配线的复发。修：
(i) `asm_response.schema.json` 的 reason_code 改为**闭枚举**（v1 全集 ∪ 11 个注册 ASM 码），放弃自由 pattern；
(ii) AG5 增加断言 **AG5-H：全部实测响应的 reason_codes ⊆ asm_policy_v0.yaml 注册集**，出现未注册码一票 FAIL；
(iii) 四个野码收编：`ASM_CONTACT_OOD`→并入 `ASM_CONTACT_PARAM_OUT_OF_SWEEP`（或 `OUT_OF_DOMAIN`）、`ASM_LATCH_UNKNOWN`→并入 `ASM_LATCH_STATE_INVALID` 的缺失分支、`ASM_FLEX_WAIT`/`ASM_WHEEL_MARGIN` 若确需保留则**先**登记进 §2.1 表与 asm_policy_v0.yaml，两文档由单一注册表引用（词表 SSOT 纪律）。
另记（继承性隐患）：v1 请求 schema/policy 用 `G3_dense`，而 `scan_v0.yaml` 与 `tool_contract_draft.yaml` 用 `G3_compact`——装配扩展同时消费两套栈，实现前必须声明单一映射，否则同一几何类在 Gate 侧与工具侧异名（A7 同型缺陷，v1 冻结面不改，映射放 asm_policy）。

**缺口 2：相位伪造——哈希绑定的是"声明的 phase"，不是"实际的运动"**。
HMAC+scenario_hash 封死的是**跨相位重放**（拿 APPROACH_5D 的授权响应冒充 LOCK_6D 授权，MAC/哈希必败——这条成立）。但另一条攻击路径未封：客户端**诚实地哈希一个不诚实的声明**——请求里写 phase=APPROACH_5D，哈希自洽、授权签发，随后执行的却是 6D 插入动作。`ASM_PHASE_SCOPE_MISMATCH` 的触发语义（"持 APPROACH_5D 授权执行 LOCK_6D"）预设了 Gate 能看到"实际执行的是什么"，而计划中**没有任何字段**从可信信道携带实际运动类。这与红队 A1"状态自证清白"同构：phase 目前是被审对象自报的。修：
(i) asm_evidence 增加 required 字段 `executed_motion_class_witness`（评测=harness 真值注入；演示=执行层/L5 控制器的指令自由度证书），来源限 `trusted_state_channels`；
(ii) 裁决核比对 declared phase vs witness，不一致 → `ASM_PHASE_SCOPE_MISMATCH`（UNKNOWN/ABORT）；witness 缺失 → UNKNOWN（不许默认一致）；
(iii) AG5-B 增补负例："声明 APPROACH_5D + 见证运动类=6D 插入"必须 0 成功——现有 12 例清单里的"相位越权"要明确写成这一形态，否则实现者只会测跨相位重放那半边。

---

## 攻击点② "接触相位内过期→BACKOFF 而非 WAIT"新语义

**裁决：NEEDS_FIX（方向正确但欠条件化；与 ASM-01 接触状态机的卡滞/楔紧物理存在三处冲突）**

WAIT=原地持锁承受持续不确定接触载荷，确实不是接触相位的安全中性动作——这个判断成立。但把 BACKOFF 写成接触内过期的**无条件**映射，有三个问题：

1. **与卡滞/楔紧物理冲突**：`contact_flexible_dynamics_plan.md` §3 明确定义楔紧（wedging）为**准静态不可恢复**（l/d<μ 几何自锁），卡滞（jamming）的脱困方式是**改变力旋量比例**而非沿轴硬拔——盲目轴向回退在两点接触/卡滞态下可能加大接触力甚至反向楔紧。而证据过期恰恰意味着 Whitney 平行四边形裕度 g_jam、接触态标志**全部不可求值**——按同一文档 AG4-3，"未知接触态 ⇒ UNKNOWN_CONTACT_STATE，任何数值预测即 FAIL"。一条盲退指令隐含"回退路径安全"的物理预测，与该硬门精神自相矛盾。
2. **LOCK_6D 段与 f6/f7 纪律冲突**：latch 已 ENGAGED（半锁）时回退等于带载拔锁，可能损伤机构；FSM 自己规定 LOCKED 后不自主解锁（f7）、FAULT 不重试（D4）。I-B B1 行把 LOCK_6D 的过期一律映射 BACKOFF，没有按 latch 末known 状态分支。
3. **鸡生蛋问题**：§3 注说 BACKOFF"沿 RETREAT 已授权运动类"，但 §2.2 规定相位切换即旧授权作废、新裁决需要新鲜 evidence——而触发 BACKOFF 的前提恰是 evidence 过期。若回退动作本身还要过一次需新鲜证据的裁决，则 BACKOFF 在其自身规则下**不可执行**。

修（三条，均有机器落点）：
- **准入分叉**：asm_policy 把 `ASM_STALE_IN_CONTACT` 拆为两个子态——
  `..._PREENGAGE`（末known latch=OPEN ∧ 末known g_jam≥0 ∧ 无楔紧旗标）→ BACKOFF；
  `..._ENGAGED_OR_JAM`（latch∈{ENGAGED,LOCKED} 或 g_jam<0 或接触态未注册）→ **冻结保持**（零指令扭速的 WAIT 变体，短 deadline）+ REOBSERVE，证据刷新后才允许 RETREAT/ABORT 升级。BACKOFF 的准入证据显式消费 ASM-01 M4 判据组输出（两点接触旗标/楔紧条件/τ_stall）。
- **预授权回退原语**：BACKOFF 的运动学定义为"进入接触相位时随相位授权一并裁决的守卫式回退原语"（低速、力限幅、沿末known 插入轴退至预插入路标，本地力觉超限即停）——写入 asm_request 的相位授权包络，解决鸡生蛋；这与 FSM f5"停进给→沿插入轴退至预插入路标"的既有语义对齐，须在 vla_sequence_plan §1.2 与 rom_safety_plan §3 两处交叉引用同一定义。
- **AG5-B 双向负例**：既测"stale+ENGAGED 时任何运动指令=绕过成功"（不许动），也测"stale+PREENGAGE 时无限期持锁=绕过成功"（不许赖着不动），防止实现者只封一边。

---

## 攻击点③ AG6 消融协议可行性（9/1 前无 VLA 实体）

**裁决：NEEDS_FIX（AG6 主对比在无 VLA 实体时空转且无合法收口词；V2.5 先行可支撑比赛叙事但须预注册降级路径）**

- **空转判定属实**：V2/V3 需要可运行的 VLA 实体。ASM-05 虽声明"提示工程不训练"，但仍需多模态模型接入 + 渲染/域随机化管线（自认 NOT_STARTED）+ ASM-01/02 真值面（NOT_STARTED）+ 词表统一回改（前置未完成）。今天 2026-07-20，硬截止 2026-09-01，前面还排着 ASM-00..04——V3 按期在场的概率不高。
- **更危险的是词表缺口**：AG6 裁决词表只有 `AG6_ABLATION_PASS / AG6_NO_VLA_GAIN / AG6_INVALID_PAIRING`。`AG6_NO_VLA_GAIN` 的语义是"**跑了** V3 且不优于 V2.5"——它不能用于"V3 根本没跑"。当前词表下，没跑 V3 的诚实收口**无词可用**，存在把"没做"报成"无增益负结果"的表述通道（这会是撤回级错误：负结果是科学结论，未实施是项目状态）。
- **V2.5 单独先行的支撑力评估**：足以支撑"确定性九技能 FSM + 冻结物理工件工具接地 + 运行时安全门（AG5）"的比赛叙事，且 V2.5−V1（工具接地增益）**不需要 VLA** 就能测；AM1/AM2/AM7 + AM4 几何子项也不依赖 ASM-01/02 真值（计划 §5 已诚实声明）。但 V2.5 先行**不能**支撑任何"VLA/具身大模型价值"表述——计划自己的归因协议（仅 SEQ_DIFF 计入 VLA 增益）已把这条路封死，这是对的。

修：
(i) AG6 词表增加 `AG6_NOT_EVALUATED_NO_VLA_ENTITY`（明示"消融未实施"，与负结果严格区分），同步进 `gate_registry.yaml` AG6 行；
(ii) 预注册**降级决策日**（建议 2026-08-10 前后）：届时 VLA 实体不可运行则正式降级为"V0/V1/V2.5 三组 + AG6_NOT_EVALUATED 收口"，比赛叙事主张改押 V2.5−V1 工具接地差量与 AG5 安全线——降级本身写入 claim_evidence_matrix，不许静默；
(iii) claim_evidence_matrix "装配VLA价值"行的 claim_allowed 增加限定：AG6 非 PASS/NO_VLA_GAIN 收口前，禁止出现"VLA 装配技能选择框架（已评估）"式措辞。

---

## 攻击点④ "UNKNOWN 永不 success"八判据枚举完备性

**裁决：NEEDS_FIX（存在第九条隐含判据——接触历史合规；另两处判据定义偏松）**

- **第九判据确实被遗漏：接触历史合规**。判据5 `contact_load_within_limit` 是终态布尔——按现定义，插入中途瞬时超载后恢复、接触积分段未收敛、接触日志有缺口的 run，在 VERIFY_ASSEMBLY 时刻八项全 PASS。而"未收敛接触禁判成功"目前只挂在 AG2（gate 层断言），**不在** success 判据集里——gate 断言管的是批量实验裁决，判据集管的是单 run 的 success 授予，二者作用点不同，前者盖不住后者。修：`interface_ssot_draft.yaml` `assembly_success_criteria` 增加第九项 `contact_history_compliant`：全接触历史峰值在限内 ∧ 全部接触段收敛 ∧ 日志无缺口；任一不可证 → UNKNOWN → 非 success。注意"八项"字样硬编码在至少四处（接口 SSOT、rom_safety_plan §2.1/§2.3、gate_registry `assembly_success_definition`、vla_sequence_plan AM4/f7）——改九须一次协同修订并复跑 AG-A0 式一致性核查，零散改必然漏。
- **判据4 偏松（假 LOCKED 通道）**：`latch_state: LOCKED` 未要求 `geometry_consistent`。AH-C 留出轴自己把"假 LOCKED（传感器报 LOCKED 几何未达位）"列为专门考题，`verify_latch_state` 工具也定义了交叉验证字段——但 success 判据不要求它，等于考题设了、判卷不看。判据1–3 的位姿/深度项只在其证据与 latch 传感器独立时才兜得住，这个独立性没被声明。修：判据4 改为 `latch_state==LOCKED ∧ geometry_consistent==true`（UNKNOWN 传染照旧）。
- **判据8 未覆盖 run 级授权账本**：`provenance_complete` 是逐决策五件套，管不到"整个 run 的每次相位切换都经过了重新裁决"。一个中途有一次未裁决切换的 run，到 VERIFY 时刻仍可八项全 PASS。AG5-F 在 gate 层测重放，但 success 授予层同样需要。修：判据8 定义扩为"逐决策 provenance 完整 ∧ 相位切换裁决账本完整（九技能路径上每条已走转移均有对应 asm response 记录）"，或单列第十项；缺账本 → `ASM_PHASE_TRANSITION_UNADJUDICATED` 语义在 VERIFY 处复用。
- 其余候选核查过不构成遗漏：残余柔性响应由判据7 包络覆盖；电源/数据状态位按 SSOT 语义是 LOCKED∧geometry_consistent 的派生量（判据4 修复后自动被盖住）；相对速率在锁定后由结构连接定义消解。

---

## 攻击点⑤ 五个 PLANNED 工具的 PLANNED_NOT_EXIST 静默转正

**裁决：NEEDS_FIX（拒绝服务的触发条件是"文件不存在"，不是"工件未认证"——转正通道敞开）**

vla_sequence_plan §6 的纪律是"工件不存在时拒绝服务，不得返回猜测值"——这只封了**缺位**，没封**转正**。对比捕获阶段合约：`tool_contract_draft.yaml` `frozen_references` 逐工件钉死 {path, sha256, gate_json, expected_verdict}；而 §6 五工具的 `data_source` 只是散文路径 + `PLANNED_NOT_EXIST` 注释，**无哈希锚、无 verdict 前置**。静默转正剧本：ASM-01 实现期在约定路径放一份草稿 CSV（未过 AG2/AG4），工具探测到文件存在即开始供答——五个工具从"拒绝"到"供答"的状态翻转不经过任何机器裁决，正是"实现期被静默转正"。修：
(i) 五工具激活仅允许经**合约版本递增**（v0→v1）完成，递增时逐工件登记 {path, canonical sha256, 背书 gate JSON 路径, expected_verdict ∈ 对应 AG 的 PASS 族（含 `_WITH_PROVISIONAL_PARAMS`）}——文件存在但未登记/哈希不符/verdict 不符 → `REFUSE_STALE_ARTIFACT`，沿用 A5"逐调用重读"纪律；
(ii) AG5-D / AG6 预注册三个负例探针：未登记工件在位、登记后上游 verdict 翻转（复用 SAFE-00 A5 修复的测试形态：翻转上游 verdict 后旧答案必须被拒）、哈希漂移；
(iii) `data_source_status` 的每次状态迁移（PLANNED_NOT_EXIST→ACTIVE）必须落 claim_evidence_matrix 一行（该 CSV 现有"装配接触动力学/序列与技能"行可挂），禁止只改 YAML 注释。
另：§6 末段四个野 reason_code 的收编见攻击点①缺口 1（同一修复项，勿双轨）。

---

## 攻击点⑥ ROM 五绕过组合落位声明与承诺一致性

**裁决：CONFIRMED_OK（逐项与磁盘证据一致；仅 §4.3 总结句一处措辞过强 + 一个依赖悬空）**

逐组合核对（红队原始承诺 `red_team_vla.md` ⑥ vs rom_safety_plan §4.3 vs 磁盘现状）：
- **组合1（统一域 L0 死锁）**：声明"已封于 SAFE-00 策略层"属实——`safety_policy_v1.yaml` domains.L0 确无 `contact_T_c_ms/panel_f1_hz` 且带注释；rules YAML 的统一 `in_domain` 与 R2a 不可达分支**仍在**（metrics.in_domain 定义未按层拆分），计划如实列为 R1 实现前置。一致。
- **组合2（升级目标不可用）**：SAFE-00 层封堵证据属实——B6/D2 `L2_FAILED_NO_OPTIMISTIC_FALLBACK`、D1 `FALLBACK_DOMAIN_UNCHECKED` 均在 cases；response schema `accepted_for_finalization: {const:false}` 在 L198。选择器终态由 `ASM_ROM_ESCALATION_UNAVAILABLE`+AG5-E 承接，与红队要求的 `UNKNOWN_ESCALATION_UNAVAILABLE` 语义等价（改名不改义，可接受），且 AG5-E 逐字落位了红队 Required evidence 第 6 条的"L2 未认证时 R3 红区不得被 L1 定案"负例。一致。
- **组合3（伪机器可执行条件）**：入口封堵属实（`machine_condition_language: STRUCTURED_V1` + B7 判例）；rules YAML 内部 R4 散文条件"或连续两档不降"、`goto: R2a`、未注册 `L1_bandwidth_mode` **仍在**（本轮复核 L103/L133–134 原样），计划如实列为 R1 修订+AG5 负例。一致。
- **组合4（eps_tot 自举）**：部分封堵属实（`SCREENING_ONLY` 在 v1 certification 枚举、`MODEL_CERTIFICATION_MISMATCH` 在 safety_core 词表）；"认证前 SCREENING_ONLY 总锁"待入 rules YAML，AG5-B 已含"SCREENING_ONLY 入 ALLOW provenance"负例。一致。
- **组合5（R3→R5 次序依赖）**：诚实标注"未封"，修复方案与红队原文逐字对应。一致。

两处小修：
(i) §4.3 结论句"五组合中 1/2/3 已在 SAFE-00 策略层封堵"对组合 3 **过强**——封的只是裁决入口（散文条件进不了 Gate），rules YAML 内部缺陷 SAFE-00 根本不消费；其自身表格行的"入口已封"才是准确措辞，结论句应向表格行对齐。组合 1 同理建议补"（Gate 路径；选择器本体待 R1）"。
(ii) **依赖悬空**：ASM-04 task card `depends_on` 第二项是"rules YAML 的 R1 修订"，但装配侧 `gate_registry.yaml`/`file_ownership_matrix.csv` 均无该修订项的 owner 与跟踪行（它属 ROM 线 R1 阶段，跨目录）。修：在装配 risk_register 或 dependency_dag 补一行显式跟踪（owner=ROM R1，阻塞 ASM-04-SAFETY），防止两个规划各自以为对方在管。

---

## Reviewer concerns（审稿人视角主要疑虑）

1. 装配安全线的全部"=0"断言（AG5-A/B）押在一份尚未实现的扩展上，而其 reason_code 词表已在两份规划文档间分裂（①）——捕获线 A7 缺陷在装配线复发，说明"单一词表 SSOT"仍无机器强制。
2. phase 是被审对象自报字段：哈希与 HMAC 封住了重放，封不住"诚实哈希的不诚实声明"（①缺口 2）——与 A1 同构的自证清白问题，规划未给可信见证信道。
3. BACKOFF 新语义在楔紧/半锁工况下可能比 WAIT 更危险，且其"沿已授权运动类"的执行前提与自家相位授权作废规则互斥（②）——盲退指令与 AG4-3"未知接触态禁数值预测"直接顶牛。
4. AG6 在无 VLA 实体时无合法收口词，存在把"未实施"包装成"负结果"的表述通道（③）。
5. success 判据集与 gate 断言集作用点混淆：AG2"未收敛禁判成功"管不住单 run 的 success 授予（④）。
6. 五个 PLANNED 工具的激活不经任何机器裁决，PLANNED_NOT_EXIST 是注释不是护栏（⑤）。
7. 计划密度远超 9/1 前可实现量（ASM-00..06 全 NOT_STARTED + R1 修订 + 词表回改），最大工程风险是"规划完备、实现半途、裁决缺位"的中间态被当作成果表述。

## Required evidence（结论成立前必须补齐的证据）

1. `asm_response.schema.json` reason_code 闭枚举 + AG5-H（响应码 ⊆ 注册集）断言 + 四个野码收编 commit（①）。
2. asm_evidence 的 `executed_motion_class_witness` 字段（trusted_state_channels 来源）+ "声明相位 vs 见证运动类不一致"负例 0 成功（①）。
3. `ASM_STALE_IN_CONTACT` 双子态准入表（消费 ASM-01 M4 输出）+ 预授权守卫式回退原语定义（相位授权包络内）+ AG5-B 双向负例（②）。
4. AG6 词表补 `AG6_NOT_EVALUATED_NO_VLA_ENTITY` + 降级决策日预注册记录（③）。
5. `assembly_success_criteria` 修订（+contact_history_compliant、判据4 加 geometry_consistent、判据8 扩 run 级账本）+ "八→九"跨文档协同修订的一致性核查记录（④）。
6. 五工具激活合约（逐工件 path/sha256/gate_json/expected_verdict 登记）+ 三类转正负例探针测试证据（⑤）。
7. rules YAML R1 修订项在装配侧的跟踪行（owner/阻塞关系）（⑥）。

## Allowed claims（现有证据下允许的表述）

- "装配安全线规划继承 SAFE-00 已 PASS 裁决核（47/47、12 绕过 0 成功、16 例逐位决定性），扩展为新增合同不改冻结面，回归界机器可判。"
- "相位授权语义（5D/6D 分相）的物理依据是 CTRL-01 预注册负结果——冻结增益与预注册轨迹下严格 6D 零空间真零、5D 段 1 维零空间。"（限定语必带）
- "装配 success 采用 fail-closed 多判据与门，任一 UNKNOWN 不判 success；判据集为 PLAN 态，接口参数全 PROVISIONAL/LITERATURE。"
- "ROM 五绕过组合中 Gate 路径已在 SAFE-00 策略层封堵（组合 1/2 及 3 的裁决入口），选择器本体修订与 4/5 为 R1 实现前置，均有 AG5 机器落点。"
- "V2.5（确定性 FSM+物理工具+安全门）是本协议的强对照与可独立交付基线。"

## Forbidden claims（禁止出现的表述）

- "装配安全扩展已实现/已验证"——全线 PLAN/DESIGN_DRAFT，`asm_gate_check.json` 不存在。
- 在 AG6 未以 PASS 或 NO_VLA_GAIN 收口前，任何"VLA 装配价值/具身智能增益"表述；V3 未跑时禁用 `AG6_NO_VLA_GAIN`。
- "UNKNOWN 永不 success 已被机器保证"——现状是设计承诺，AG5-A 跑通前只可说"已设计并预注册"。
- 任何不带 `_WITH_PROVISIONAL_PARAMS` 限定的装配安全 PASS 表述（接口 SSOT 无 MEASURED 字段 + 帆板质量占位待办 3）。
- "接触内过期的安全动作已定义"——②修复落地前，BACKOFF 语义不得写为已收口。
- 固定基座演示=微重力验证、AprilTag=非合作泛化、"自主在轨组装完成"（state_truth 科学边界原文继续全量适用）。

---
*红队输出仅此一份文件；所有判定均给出磁盘出处；未修改任何被审文档或冻结证据。*
