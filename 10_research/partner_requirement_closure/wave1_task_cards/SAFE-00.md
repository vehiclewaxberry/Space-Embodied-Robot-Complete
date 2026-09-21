# Task Card SAFE-00 — Runtime Safety Gate（独立阻断主模块）

- **task_id**: SAFE-00
- **scientific_question**: 在多保真模型、时效证据与不完整感知下，运行时安全裁决能否做到 fail-closed 且每个放行决策可溯源到冻结机器裁决？
- **hypothesis**: 三态判定（SAFE/UNSAFE/UNKNOWN）× 五动作（ALLOW/MODIFY/WAIT/BACKOFF/ABORT）+ 证据哈希链可以覆盖 R2 枚举的全部七个绕过面。
- **baseline**: 无（新模块）；语义基线 = sim_10 四门 fail-closed + sim_12 GS3 主张审计。
- **owned_paths**: 30_simulation/safety_00_runtime_gate/（新建）、20_engineering/config/safety_gate/（新建）
- **forbidden_paths**: sim_01–12 全部冻结区、10_research/（除自身报告）、.codex/
- **input_evidence**: sim_10/sim_12 gate JSON 与 CSV、threshold_registry（sha256 400bced…）、R2 红队七绕过面清单、model_fidelity_selection_rules.yaml（域护栏字段）
- **minimal_implementation**: 纯函数裁决核 `decide(scenario, evidence) -> {state, action, reason_code, provenance}`；provenance 强制三元组（gate_json 路径+registry sha+scenario_hash）；证据时效校验每次调用执行（非启动时）；schema additionalProperties:false。
- **experiment_matrix**: 七绕过面各一组对抗用例（伪造 provenance/过期裁决/域外参数/λ 取整走私/PROVISIONAL 字段缺失/未认证 L2 升级请求/散文条件）+ 正常放行组 + 降级链组（L2 失败→UNKNOWN，降 L1/L0 必须重查各自适用域）。
- **metrics**: 绕过成功次数（须=0）、UNKNOWN→ALLOW 次数（须=0）、误 ABORT 率、决策延迟、provenance 完整率（须=100%）。
- **machine_gates**: GS-A 硬规则五条机器断言（UNKNOWN 永不 ALLOW；数据超时→WAIT；L2 失败禁回退乐观 L0；降级重查域；无 provenance 禁 ALLOW）；GS-B 对抗用例全阻断；GS-C registry 哈希锁。
- **red_team_questions**: R2 七面逐条复测；新增"reason_code 可被下游忽略吗"、"MODIFY 动作的修改边界谁定义"。
- **stop_condition**: GS-A/B/C 全过 + R2 复测无新绕过 → 输出 safety_00_gate_check.json 停。
- **rollback_plan**: 模块独立新建，回滚 = 删目录；不触碰任何既有 Gate。
- **claim_unlocked**: "每个执行授权可溯源到冻结机器裁决"（Demo 核心句）。
- **claim_forbidden**: "系统绝对安全"；任何覆盖率外推；FLEX 相关安全声明。
