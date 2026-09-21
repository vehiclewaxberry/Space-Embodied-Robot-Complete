# 红队审查报告：VLA 泛化协议 / Physics Tool 合约 / 系统接口 / 多保真 ROM — 2026-07-19

> 角色：空间具身智能方向审稿人（红队，只读）。
> 审查对象：
> - `10_research/vla/vla_generalization_plan.md`（PROTOCOL_DRAFT）
> - `10_research/vla/tool_contract_draft.yaml`（DRAFT_NOT_IMPLEMENTED）
> - `10_research/integration/system_interface_plan.md`（规划文档）
> - `10_research/rom/multifidelity_rom_plan.md` + `10_research/rom/model_fidelity_selection_rules.yaml`（PLAN_ONLY）
> 审查方法：全部结论基于磁盘核实，非对话记忆。本轮独立复核项：
> - registry 哈希独立重算：`30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml`
>   实测 sha256=`400bcedce5af6ad5c4135e67f87bb524ee2fdafb1c26aeae07e495ff387b2873`，与三份文档引用**逐位一致**；
> - 全部 frozen_references 路径存在性核实（sim_10/sim_12 gate JSON 与 CSV、sim_09 e1、
>   collision/hard_constraints YAML、scan_v0.yaml、contact_window.py、e15 gate_summary.json：全部存在）；
> - `strategy_results.csv` 表头与枚举值（binding_gate/case/strategy）与合约枚举**逐项比对一致**；
>   `sim_10_scan_gates.csv` 列名与合约 gates 块比对一致；
> - `sim_12_gate_check.json` verdict=SIM12_PHASE1_GATES_PASS，GS3 allowed/forbidden 短语确为机器可读；
> - `.codex/agents/physics-agent-architect.md` 词表与工具签名核实；
> - `state_truth_report.md` 项 4/5 状态声明与磁盘一致（无"把已完成当新工作"或"把未做当已做"）。

**总裁决：无 FATAL 项；六个攻击点全部落为 NEEDS_FIX（其中 ⑤ 的 Safety Gate 规格缺失为实现前必须闭合的阻塞项）。**
四份文档的诚实基调（PLAN_ONLY 自我标注、PROVISIONAL 传染、e15 REPEAT 不回避）经查属实，未发现证据伪造或超磁盘声明。

---

## 攻击点① VLA 是否只是工具调用包装——为什么需要 VLA 而非确定性 FSM

**裁决：NEEDS_FIX（消融矩阵存在一处混杂变量；L4 的 VLA 必要性论证按现设计不可证伪）**

成立的部分：
- 协议并非回避此问题——V0/V1/V2 的 L4 决策来源就是"固定规则表"（即确定性 FSM），
  FSM 基线在消融阶梯中真实存在；L3 层的 VLA 必要性（语义候选："抓杆件不抓帆板"、
  G-G 未见接口类型）有 V1（无语义几何抓取网络）作对照，是可检验主张。这一层的论证成立。

不成立的部分：
1. **V2→V3 双变量混杂**。协议 §2 声称"唯一变量是表格中的两列"，但 V2→V3 同时改了两列：
   L4 决策来源（规则表→VLA）**和** Physics Tool（查表式→全量五工具）。因此
   "V3−V2 = L4 工具接地增益"这一预注册消融式无法区分"VLA 是更好的决策者"与
   "五工具接口比查表更丰富"。**缺一个格子：V2.5 = 规则 FSM + 全量五工具**。
   若 V2.5 ≈ V3，则 L4 的 VLA 贡献为零，"工具接地增益"应归功于接口而非模型——
   这正是攻击①成立的场景，协议目前无法排除它。
2. **L4 的 VLA 活动空间被自身架构挤压至近零**：`recommend_action` 已按硬规则产出决策草案
   （合约行 249–254），Safety Gate 再独立复核，M5(Gate 后)=0 是构造保证。V3 中 VLA 在 L4
   的实际自由度只剩：工具调用编排、WAIT vs REOBSERVE 的裁量、assumptions 措辞。
   协议未预注册"VLA 在哪些具体工况上应优于 FSM"（候选：G-F 延迟注入、G-E 遮挡、
   感知矛盾信号），导致 L4 主张事后不可判。

**修改建议**：(a) 消融矩阵增补 V2.5（FSM+五工具），并把"V3−V2.5 = L4 VLA 净增益"写为
预注册主张；(b) 在 §5 预注册"VLA 预期胜出的组轴×指标清单"（如 G-F/G-E 上 M6 细分项），
若 V3≈V2.5 则论文措辞降级为"VLA 贡献限于 L3 语义候选层"（该降级路径本身预注册）。

---

## 攻击点② 泛化协议的"未见目标"是否真的未见

**裁决：NEEDS_FIX（按组留出机制本身设计合格；三条泄漏/空转通道未封）**

成立的部分：
- 按组切分、单轴留出、禁止混合平均（§4）、分区种子入 scenario_hash：机制设计合格。
- 渲染管线 NOT_STARTED 时协议**不算空转**——它是预注册文档，冻结的是组轴与参数化要求，
  §8 依赖表如实标注。这一诚实性成立。

不成立的部分：
1. **预训练污染未被处理，"未见"只是"提示级未见"**。§6.3 明确不训练模型（只做提示工程），
   则"见过组（训练/提示可含）"中的"训练"实为空集，留出仅相对于提示/少样本内容。
   但 VLA 基座模型的预训练语料几乎必然含卫星、帆板缺失、天线弯折类图像——
   G-A 留出组（G3 致密体、变形外形）对基座模型**不是分布外**。协议通篇未声明此
   效度威胁，"泛化"一词有被审稿人击穿的风险。
2. **提示内容与模型版本不入溯源**。L4 溯源三元组（gate_json_path/registry_sha256/
   scenario_hash）不含 prompt_sha256 与 model_id/版本。留出组的破坏通道恰恰在提示侧：
   若少样本示例取自 sim_09 已评价过的抓点（M1 真值源），M1 召回被直接污染，且现有
   哈希体系**审计不到**。闭源 API 模型的版本漂移还会破坏可复现性。
3. **关键留出轴的真值源不存在**。M1/M3 真值 = sim_09 评价器口径（e1 已核实 72 例），
   但 `collision_geometry_v1.yaml` 是按 CAD 锚定目标配置的；G3 致密体与"帆板缺失/
   天线弯折"变形外形的禁抓区/硬约束配置**尚无对应版本**。若实施时临时补配置，
   等于在见过测试数据后定义真值——预注册失效。
4. 阈值"实施时冻结具体数值入 registry"（§5）弱化了预注册：冻结时点未绑定在
   "首次渲染/首次评测之前"。

**修改建议**：(a) 泛化主张措辞全部限定为"域随机化渲染分布上的组间迁移 +
提示级留出"，并把预训练污染列入 threats-to-validity 节；(b) 溯源三元组扩为五元组：
+`prompt_sha256` +`model_id_version`；(c) 增加"真值源冻结 Gate"：G3/变形外形的
`collision_geometry_vX.yaml` 与 hard_constraints 版本必须在任何渲染评测开始前提交并哈希
入 registry；(d) 增加"渲染器资格化 Gate"（遮挡率真值校验、几何对 `20_engineering/config/geometry/`
SSOT 的保真校验）作为 §8 依赖表的显式前置门；(e) 阈值冻结时点绑定"首个测试样本
生成之前"，违者该轴作废。

---

## 攻击点③ AprilTag 结果混入泛化声明的通道残留

**裁决：NEEDS_FIX（§6.1 红线文本是全套文档中最强条款；但机器层有三个残留通道）**

成立的部分：§6.1 措辞（"合作标记替身"、仅 V0/L1、违反即撤回）+ §7"L1 支路仅 V0 对照"
+ 接口计划 L1 信任边界（"感知声称可抓不构成授权"）——设计意图层面无懈可击。

残留通道（全部为 schema 级，即"人不犯规但机器拦不住"）：
1. `tool_contract_draft.yaml` 中 `perception_branch` 只出现在 `recommend_action` 的
   `perception_quality` 里，而 `perception_quality` **不在 required 列表**
   （required 仅 [feasibility_response, resource_response, scenario_hash]）——
   一次合法调用可以完全不带支路标注。
2. 协议 §3 的 L4 输出 schema（decision/assumptions/provenance/tool_call_trace）
   **没有 perception_branch 字段**；scenario_hash 的定义域（几何/光照/姿态/转速/留出组/
   种子）**不含感知支路**——同一场景走 L1 与走 L2 会得到相同 scenario_hash，
   结果 CSV 中两类行不可区分，§6.1 的"必须带标注"没有落点。
3. `vla_gate_check.json` 的机器断言清单（§7）只含 M5(Gate 后)=0 与哈希锁，
   **不含"M8/泛化表输入行 perception_branch==L2_markerless 全体成立"断言**——
   红线目前靠人执行。

**修改建议**：(a) `perception_branch` 升为 L4 输出 schema 与 provenance 的必填字段，
并纳入 scenario_hash 定义域；(b) `recommend_action` 的 `perception_quality` 移入 required；
(c) `vla_gate_check.json` 增加机器断言：M8 计算的每一输入行 branch==L2，出现 L1 行即
FAIL；(d) V0（L1 支路）行写入独立 CSV 或强制列隔离，禁止与 L2 行同表无标注共存。

---

## 攻击点④ Physics Tool 是否只是硬编码规则查表

**裁决：NEEDS_FIX（"不新算物理"的自我定位诚实；但两文档给出互相矛盾的求值路径，其中查表插值路径在过渡带不可靠；域外 UNKNOWN 有 schema 支撑但有三个洞）**

界线判定：查表与"物理工具"的合法界线 = **是否存在按需重解的冻结已验证求解器**。
`system_interface_plan.md` §1.1 走的是这条线（`feasibility_core.exact_point` 优先，
X1 solver identity <1e-12，网格行仅交叉核对）——这条路径下"Physics Tool"名副其实。
但：
1. **矛盾路径并存**：`tool_contract_draft.yaml` 的 `query_feasibility.data_source` 写
   "查表/网格内插值"，`.codex/agents/physics-agent-architect.md` 也写"插值 …csv（72k 行）"。
   插值路径有两个具体不可靠点：(a) region 是**类别量**，网格内插值在区域边界格
   无定义（相邻顶点 region 不同时插的是什么？）；(b) sim_10 X2 已实录 G1 过渡带
   μ≈0.51 存在 1.08% **亚分辨率非单调**凹陷——恰恰在插值最需要单调性假设的地方，
   证据表明假设不成立。若实现方选择合约/角色卡的插值路径，"物理工具"确实退化为
   一张在关键区域不可信的查找表——攻击④在该路径上成立。
2. **λ 的客户端就近取整是静默域外走私**：合约 `lambda_scale enum [0.2,0.5,1.0]` +
   "连续 λ 由客户端声明最近网格"——真实候选 λ=0.35 被客户端四舍五入后，工具端
   看不到原值、不留假设标注，回答的是**另一个杠杆比**的可行性。λ 直接进 ω⁺，
   边界附近可翻转判定。这违反 fail-closed 的自家定义。
3. **evaluate_capture 的 target_state 无界**：`mu`/`omega_dps` 无 minimum/maximum
   （对照 query_feasibility 有 [0.05,25]/[0.1,10]，已核实与 scan_v0.yaml 逐项一致）——
   域外拦截依赖"转发 query_feasibility 时才被拒"，入口即应拦。
4. 域外 UNKNOWN 能否真触发：`REFUSE_OUT_OF_DOMAIN` + schema 边界 + ROM 侧 GR4
   域外探针（返回数值即 FAIL）——机制存在且有对抗性测试设计，**能触发**；
   但上述 λ 取整与 evaluate_capture 无界是两个绕开它的旁路。

**修改建议**：(a) 合约与角色卡统一改为接口计划的 EXACT_SOLVER-first 口径，明文
"禁止对 region 类别量插值；网格仅作交叉核对"；(b) 输入同时携带 `lambda_actual` 与
`lambda_grid`，工具端计算取整偏差，偏差落在区域边界带内时拒绝或强制 assumption 条目；
过渡带（G1, μ∈[0.4,0.7]）内一律 exact 求解；(c) evaluate_capture.target_state 补齐
min/max 与 geometry_class 枚举校验；(d) 演示与论文措辞：称"冻结已验证求解器 + 裁决
工件的只读接口"，不称"物理引擎"。

---

## 攻击点⑤ Agent 绕过安全 Gate 的攻击面枚举

**裁决：NEEDS_FIX（七个攻击面；其中 A1 为实现前阻塞项）**

- **A1 Safety Gate 无规格（最重）**：三份文档共同把 M5(Gate 后)=0 押在 Safety Gate 上
  （"规则代码，非模型"），但 Gate 的输入来源、独立复核算法、可信状态获取路径**在任何
  文档中都没有规格**。若 Gate 消费的是 VLA 自报的状态/响应，则 garbage-in：整个
  =0 断言退化为"VLA 自证清白"。修：单独立一份 `safety_gate_spec.md`，规定
  (i) Gate 以**自有信道**取状态（评测=harness 真值；演示=L2 估计器输出，绝非 VLA 转述）；
  (ii) Gate **独立重调** query_feasibility/compare_strategy 并与 Agent 引用的
  data_row_refs 比对，不一致即 ABORT；(iii) Gate 代码与 VLA 提示词零共享。
- **A2 scenario_hash 自报**：合约注明 scenario_hash 为"调用方场景哈希"——三元组第三
  条腿由被审对象自己计算。Agent 可对简化状态（低估 μ/ω）查询工具，却贴上真实场景的
  hash；工具端无法核验参数与 hash 的绑定。修：评测中 scenario_hash 由 harness 生成并
  注入，Agent 只许透传；Gate 复核参数-哈希绑定（A1-ii 覆盖）。
- **A3 recommend_action 接受整段客户端回传响应**：`feasibility_response` 等以完整对象
  回传，"服务端校验 provenance"校验不了**内容与出处的绑定**——Agent 可拼装一个
  feasibility=FEASIBLE 的伪造响应配上真 provenance 块（重放/嫁接攻击）。修：工具响应
  加服务端签名（HMAC）或改为按 response_id 服务端缓存取回，recommend_action 只收 id。
- **A4 阈值覆盖检测是黑名单不是白名单**：所有 schema 均未声明
  `additionalProperties: false`。"请求体出现阈值覆盖字段即判非法"只能靠枚举已知字段名
  的黑名单，新造字段名即绕过。修：全部输入 schema 加 `additionalProperties: false`，
  任何未知字段 → REFUSE_ILLEGAL_CALL 计入 M4（这才是白名单式 fail-closed）。
- **A5 缓存过期裁决**：接口计划 T4 哈希校验发生在"工具启动时"；长驻 MCP 服务期间
  上游 gate JSON 被重跑翻转（如 e15 补认证失败、sim 重跑 FAIL），工具继续用启动时
  缓存的 PASS 供答。修：每次调用对 gate JSON + registry 做逐调用哈希/verdict 复核
  （文件极小，代价可忽略），或带 TTL 的强制重读；`REFUSE_STALE_ARTIFACT` 语义明文
  绑定"每调用"而非"每启动"。
- **A6 PROVISIONAL 透传丢失**：合约中全部诚实关键字段均为可选——`query_feasibility`
  的 `flex_status` 不在 required（required=[region,binding,gates,provenance]）、
  `evaluate_capture` 同、`compare_strategy` 同、`check_resources` 的 `provisional_flags`
  不在 required；接口计划对剥离的防护是"Agent 提示词层面同样要求转述"——提示词层
  要求不可执行。一个最小合规实现可以全程不带任何 PROVISIONAL/FLEX 标注。修：
  (i) 上述字段全部移入 required；(ii) Gate 增加机器断言：最终决策的 assumptions ⊇
  本次 tool_call_trace 中所有响应的 provisional/flex 条目并集，缺一即降级 ABORT 计 M4。
- **A7 提示注入回路与词表/合约分裂**：(i) `semantic_label` 为自由字符串且被工具回显——
  VLA 幻觉出的标签（可含指令样文本）经响应回流进自身上下文，且污染结果 CSV 与演示
  回放。修：工具不回显自由文本，只回 candidate_id；assumptions 改为结构化枚举条目+
  受控备注。(ii) 三套决策词表并存（协议五词表 / 角色卡四词表 / 接口计划
  EXECUTE/ABORT/INSUFFICIENT_EVIDENCE），且**两份并行工具合约**（vla 侧五工具
  provenance 信封 vs 集成侧四工具 evidence 信封，工具名、签名、μ vs m_t_kg 单位均不同）。
  两套都实现时，Agent 会被路由到较松的一套——这本身就是绕 Gate 面。修：合并为单一
  合约 SSOT 文件 + 单一词表枚举文件，其余文档只引用；协议 §6.2 已承诺回改角色卡，
  必须在实现前完成并把接口计划的 INSUFFICIENT_EVIDENCE 纳入或显式映射（建议映射为
  REOBSERVE/ABORT 的子码而非第六词）。另注：两份计划的 L1–L5 编号语义完全不同
  （协议 L3=VLA 候选层，接口计划 L3=Physics Tools）——同号异义是审稿与实现的混淆
  通道，建议改用不同前缀（如 P1–P5 / S1–S5）。

---

## 攻击点⑥ ROM 选择规则 fail-closed 的可绕过组合

**裁决：NEEDS_FIX(骨架真 fail-closed；但存在五个未定义组合，未定义=实现者裁量=绕过面)**

成立的部分（逐项核实 YAML）：priority 短路 + 每条规则均有 on_unevaluable +
`default_action_when_no_rule_fires: UNKNOWN_RULES_INCONCLUSIVE` 兜底 + R6
`forbidden: [widen_thresholds, skip_R5, downgrade_finalization_level]` + GR3 零容忍
一票 FAIL + GR4 数值预测即 FAIL + GR5 明文拒绝低幅锚点顶替（与 e15
`gate_summary.json max=5.637e-2 REPEAT` 对齐）——骨架无绕过。

可绕过/未定义组合：
1. **全局域定义使 L0 死锁或催生法外例外**：`in_domain` 把 T_c∈[5,100]ms 并入统一域，
   而 L0（刚体瞬时，无 T_c 概念）查询中 T_c 不可求值 → R1 on_unevaluable →
   一切 L0 查询返回 UNKNOWN_OUT_OF_DOMAIN，L0 整层不可用。实现者必然"修复"为
   L0 跳过 T_c 检查——一个规则文件之外的裁量例外，即绕过面。同理 R2a 的
   "T_c 未定义或 →0"分支在 R1 之后**不可达**（priority 10 已拦）。修：域定义按层
   拆分（levels[].domain），R1 按当前层求值。
2. **升级目标不可用时的行为未定义（最危险组合）**：R2b/R3/R4/R5 多处 `escalate_to: L2`，
   而 L2 带认证债（e15 REPEAT 未闭环；GR 失败层降 SCREENING_ONLY）。"升到一个不许
   定案的层"之后返回什么？规则未写。实现者若回退"用 L1 结果凑合定案"，则 R3 的
   r_defl≥0.05（L1 线性假设已失效）工况被 L1 定案——恰是规则要防的事。修：新增
   终态 `UNKNOWN_ESCALATION_UNAVAILABLE`：升级目标未认证/SCREENING_ONLY 时强制返回
   该值（或 BOUNDARY_UNRESOLVED），禁止回落定案。
3. **伪机器可执行条件**：R4 的 `if: "tau_tail >= 0.03 或连续两档不降"`（中文散文入
   条件式）、`goto: R2a`（goto 语义未定义）、R2a `escalate_to: L1_bandwidth_mode`
   （levels 注册表无此层名）。不可解析的条件在实现时必被改写，改写即裁量。修：
   "连续两档不降"形式化为显式状态机字段（refine_history 长度与单调性判据）；
   goto 改为显式 return/escalate；L1_bandwidth_mode 注册为 L1 的 mode 参数。
4. **eps_tot 自举循环**：R5 依赖 eps_tot，eps_tot 依赖 `rom_gate_check.json` GR1 认证
   残差——认证完成前 R5 不可求值。on_unevaluable=escalate_one_level 会把认证前的
   全部流量推向 L2（又撞上组合 2）。修：明文"选择器在 R2 认证 PASS 前整体锁定为
   SCREENING_ONLY 模式，禁止 finalize"，而非依赖逐条 on_unevaluable 的偶然合成。
5. **次序依赖漏洞**：R3 黄区动作 `boundary_candidates_escalate_to: L2` 需要"边界候选"
   判定，而边界性由 R5 的 d_margin（priority 50）定义——priority 30 的规则引用
   priority 50 才求值的量。另 R5 从 L2 的 on_unevaluable=escalate_one_level 无处可升，
   未定义。修：R3 黄区改为设 tag，边界性统一在 R5 判；R5 在 L2 层的 on_unevaluable
   显式改为 BOUNDARY_UNRESOLVED。

另记（非绕过，规格完备性）：GR2 的 tie 豁免引用 eps_tot，首次认证时须明文
"先 GR1 后 GR2"的求值次序；R6 shrink_top_k 与 GR2 top-3 恒等的 k≥3 下限须写死。

---

## 跨文档一致性核查表（本轮磁盘证据）

| 声明 | 核查结果 |
|---|---|
| registry sha256（三处引用） | 实测逐位一致 CONFIRMED_OK |
| frozen_references 全部路径 | 全部存在 CONFIRMED_OK |
| 合约 binding_sim12/case/strategy 枚举 vs strategy_results.csv 实际值 | 逐项一致 CONFIRMED_OK |
| 合约 gates 块列名 vs sim_10_scan_gates.csv 表头 | 一致 CONFIRMED_OK |
| scan_v0.yaml 域（μ[0.05,25]/ω[0.1,10]/λ/α/tier/54.735g/3600s PROVISIONAL） vs 合约 schema | 一致 CONFIRMED_OK |
| GS3 allowed/forbidden 短语机器可读（T3 前提） | sim_12_gate_check.json 内存在 CONFIRMED_OK |
| sim_09 e1 72 例 | e1_gate_check.json n_cases=72 CONFIRMED_OK |
| 合约 compare_strategy.ledger 声称"列直传不重命名" | **缺 `ledger_dH_internal`**（CSV 有该列）NEEDS_FIX（补列） |
| 接口计划引用 `strategy_definition.yaml` 未给路径 | 实际在 `10_research/sim_12/strategy_definition.yaml`，NEEDS_FIX（补路径防歧义） |
| `rom_certification_manifest.yaml` | 尚不存在——与"R1 阶段落地"声明一致，非缺陷 |

---

## Reviewer concerns（审稿人视角主要疑虑）

1. L4 层 VLA 的科学必要性在现消融矩阵下不可证伪（V2→V3 双变量混杂，缺 FSM+五工具格）。
2. "泛化到未见目标"的"未见"仅为提示级留出；基座模型预训练污染未进 threats-to-validity。
3. M5(Gate 后)=0 是构造性断言，其全部效力压在一份不存在规格的 Safety Gate 上（A1）。
4. 两套并行工具合约 + 三套决策词表 + 两套 L1–L5 编号语义——实现期路由到较松一套的风险。
5. 诚实关键字段（flex_status/provisional_flags/perception_branch）在 schema 中全部可选，
   红线条款没有机器落点。
6. ROM 规则的"机器可执行"名不副实处（散文条件、未注册层名、升级目标不可用未定义）
   将在实现期转化为裁量，裁量即绕过。
7. 查表插值路径与 X2 过渡带非单调实录直接冲突；λ 客户端取整是静默域外走私。

## Required evidence（结论成立前必须补齐的证据）

1. `safety_gate_spec.md` + Gate 独立复核实现（自有状态信道、独立重调工具、
   与 Agent 引用 data_row_refs 比对）；`vla_gate_check.json` 含 M5(Gate 后)=0 与
   "M8 输入行全为 L2 支路"两条机器断言。
2. 合并后的单一工具合约 SSOT + 单一决策词表枚举文件；角色卡词表回改完成的 commit。
3. V2.5 基线（FSM+五工具）实测行，及 V3−V2.5 的逐组轴差值表。
4. 溯源五元组（+prompt_sha256、+model_id_version）在结果 CSV 中逐行落盘。
5. G3/变形外形的真值配置（collision_geometry_vX + hard_constraints_vX）在首个测试
   样本生成前的冻结哈希记录；渲染器资格化 Gate 裁决 JSON。
6. 修订版 `model_fidelity_selection_rules.yaml`（按层域、UNKNOWN_ESCALATION_UNAVAILABLE、
   形式化 R4 条件、注册 L1_bandwidth_mode、认证前 SCREENING_ONLY 总锁）+ 负例单元测试
   （含"L2 未认证时 R3 红区工况不得被 L1 定案"判例）。
7. 工具端逐调用哈希/verdict 复核的测试证据（翻转上游 verdict 后旧答案必须被拒）。
8. `additionalProperties: false` 全 schema 生效 + 阈值覆盖白名单拒绝的负例测试。

## Allowed claims（现有证据下允许的表述）

- "我们预注册了一个分层消融协议，用以测量 VLA 在语义候选生成层（L3）相对无语义
  几何基线的增益与幻觉率。"
- "L4 决策被冻结机器裁决工件与规则式 Safety Gate 硬约束包裹；每个 EXECUTE 决策
  可回放其 gate JSON 字段、registry 哈希与场景哈希。"（vs SpaceMind 差异化，成立）
- "Physics Tool 是对冻结已验证求解器与机器裁决工件的只读接口，不新算物理，
  域外 fail-closed。"（须按④修复后，且采用 EXACT_SOLVER 口径）
- "AprilTag 仅作为实验室合作标记替身出现在 V0 对照支路。"
- "ROM 切换规则骨架为 fail-closed（短路求值、不可求值即升级/UNKNOWN、禁止放宽阈值）。"
- "多保真组件（L0/L1/L2）各自有既有机器裁决背书；选择器与认证 Gate 为 PLAN 状态。"

## Forbidden claims（禁止出现的表述）

- "VLA 实现了对未见目标的泛化抓取"（未处理预训练污染 + 渲染管线未建成 + 无实测前一律禁止）。
- "VLA 决策系统保证安全 / 错误执行率为零"（M5(Gate 后)=0 是 Gate 的构造性质，
  不是 VLA 的性质；只可说"Gate 后错误执行被硬约束清零，Gate 前裸决策错误率为 X"）。
- "Physics Tool 引擎实时计算物理可行性"（它是冻结工件接口；"实时新算"表述禁止）。
- "工具接地使 VLA 决策提升 X%"——在 V2.5 格补齐前禁止把 V3−V2 归因于任一单因素。
- 任何把 L1/AprilTag 支路指标并入泛化表、M8 或"无标记"叙事的表述（协议 §6.1 自身条款，红队确认为撤回级）。
- "ROM 三级体系已认证/已可自动调度"（rom_gate_check.json 不存在；现状只可说 PLAN_ONLY）。
- 任何柔性（FLEX）数值性结论（e15 REPEAT 未闭环；只许 PROVISIONAL_NOT_EVALUATED 透传）。
- GS3 forbidden 短语清单继续全量适用（无条件策略排序、momentum shaping 恒优等）。

---
*红队输出仅此一份文件；未修改任何被审文档或冻结证据。*
