# Unified R2 V2 预授权准备度只读工具

## 1. 边界

本目录只回答一个问题：**未来独立签发器是否已得到足够、可追溯且互不推导的 Owner 原始意图，可进入人工复核？**

它不是授权记录、签发器、生成器或执行器。任何结果（包括工具 Gate PASS）均保持：

- `authority_effect=NONE`
- `execution_authorized=false`
- `target_authorization_written=false`
- `owner_accepted=false`
- `next_stage_authorized=false`
- `release_credit=false`

工具不创建或修改未来 `UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json`，不创建 URDF、接口实例、消费标记或 active lock，也不调用 Unified R2 的公共生成入口或私有构造入口。

## 2. 四个且仅四个命令

在项目根目录执行：

```powershell
python -B 70_tools/preauthorization_readiness/unified_r2_v2/preauthorization_readiness.py audit-current
python -B 70_tools/preauthorization_readiness/unified_r2_v2/preauthorization_readiness.py assess-owner --owner-source <Owner原始附件.json> --expected-source-sha256 <64位SHA256> --valid-for-seconds 7200
python -B 70_tools/preauthorization_readiness/unified_r2_v2/preauthorization_readiness.py verify-readiness 40_evidence/artifacts/authorization_readiness/unified_r2_v2/PREAUTHORIZATION_READINESS_CURRENT_V1.json
python -B 70_tools/preauthorization_readiness/unified_r2_v2/preauthorization_readiness.py self-test
```

CLI 没有签发、运行、目标写入、强制覆盖或自选输出路径能力。四个 CLI 报告文件名固定，发布构建的验证、独立审计、pytest、manifest 与 Gate 文件名也固定；全部只能写入预先存在的：

`40_evidence/artifacts/authorization_readiness/unified_r2_v2/`

四个生产写入器共用 `safe_io.py`。写入器不接受路径参数：它拒绝 symlink/junction/reparse 分量，持有并复核证据目录句柄，以独占临时文件写入、flush/fsync、原子替换和写后稳定句柄复核完成持久化。证据根不存在时 fail-closed，工具不会自行创建它。

## 3. Owner 原始来源约束

`assess-owner` 只接受固定用户附件根下的 `.json`/`.txt` 原始字节，并要求操作员另传其期望 SHA-256。读取使用同一 no-follow 文件句柄，读取前后复核 fstat/文件身份；同时持有并复核父目录句柄，最终句柄路径必须仍位于固定附件根。平台不能提供这些能力时 fail-closed。以下任一情况均 fail-closed：

- 路径越过用户附件边界，或来源位于本项目仓库内；
- 任一路径分量为符号链接或 reparse point；
- 读取前后文件身份、长度或时间戳变化；
- SHA-256 不一致；
- 已知旧来源、时间超过 7200 s、未来时间超过 300 s；
- 非 UTF-8 JSON、重复键、额外顶层字段；
- 请求文件、建议模板、进展裁决、代理文本或机器授权形状冒充 Owner 原始来源。

直接来源使用 `DIRECT_OWNER_INTENT_SOURCE_V1` 语法。它只表达三项独立意图，不是机器授权：

1. `odr_gpt_07`：必须从原始字节给出 `decision_id`、`decision`、`selected_option` 和请求 SHA-256；
2. `odr_gpt_08`：同上；
3. `c01_unified_r2_research_candidate`：必须单独出现，前两项永远不能推导该段。

顶层必须且只能有：`schema`、`record_type`、`origin`、`owner_role_assertion`、`owner_statement_utc`、`decisions`；`decisions` 的键集合也必须精确等于 `odr_gpt_07`、`odr_gpt_08`、`c01_unified_r2_research_candidate`，别名或额外键一律拒绝。其固定值分别包括：

- `schema=DIRECT_OWNER_INTENT_SOURCE_V1`
- `record_type=DIRECT_OWNER_SOURCE_NOT_MACHINE_AUTHORIZATION`
- `origin=USER_OR_OWNER_DIRECT_EXPORT`
- `owner_role_assertion=PROJECT_OWNER`

ODR-07 请求绑定为 23043 bytes / `679DC5D2BA2B814F584379C28E47A9F487D03277F0F1EAA45DFB85D150367D25`；ODR-08 请求绑定为 46441 bytes / `5ED037AE057F7119678DECF890C9C0E64740C1443E5E9B9682FC09B8610046F6`。工具每次都现场复算，不能盲信文档数字。

C01 段必须固定：

- `configuration=C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT`
- `selected_bus_mass_mode=EXPLICIT_STRUCTURE_PLUS_RESIDUAL`
- `route_c_exclusion_accepted_for_this_sim_candidate=true`
- `route_c_cad_authorized=false`
- `scope` 恰含 `ANALYSIS_ONLY`、`RESEARCH_CANDIDATE`、`NON_PRODUCTION`
- 生产动力学、物理接触、Sim13 rebind、下一阶段与 release credit 全部为 false

当准备度测量的可用内存小于 6 GiB 或测量为 UNKNOWN 时，C01 段还必须含精确风险确认 `ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK`。即便存在该确认，报告中的 `memory_gate_passed` 仍为 false，且不产生 run id、override id、执行信用或 Owner override 效力；未来执行时仍须重新测量。

## 4. Runtime hash、身份与有效窗

准备度工具**按设计不计算 runtime/loaded-code hash**：`runtime_code_sha256_preview=null`，状态为 `NOT_COMPUTED_BY_DESIGN_NONAUTHORITATIVE`。它不 import、compile、exec 或调用生成器；因此 source/input pin 漂移也不会触发生成器源码执行。未来独立签发器必须在**将调用生成器的同一进程、同一已加载模块实例**中现场重算并绑定，不能复用本报告。

`valid-for-seconds` 只能是 1–7200 的整数；它只生成预览时间窗，不生成 run/override id，不消费任何一次性状态。若直接 Owner 来源在结构上满足三项意图，状态也只能是 `STRUCTURALLY_READY_FOR_AUTHENTICATED_ISSUER_REVIEW__IDENTITY_UNVERIFIED__NO_AUTHORITY_CREATED`。来源内的 `owner_role_assertion` 是自声明，绝不构成身份验证；预览过期时刻取“当前时刻＋请求时长”和“Owner statement＋7200 s”二者较早值。

`verify-readiness` 对一次稳定句柄读取的原始字节执行重复键拒绝、精确顶层白名单和完整 `additionalProperties=false` schema 校验，并分别输出 `structural_passed`、`live_readiness_passed` 与 `owner_intents_ready`。schema 的 READY 条件把来源 provenance、四份 pin、报告 checks、ODR-07/08、C01 和全部无权字段作跨字段约束；`DENY_NO_DIRECT_OWNER_SOURCE` 也必须与无来源证据一致。`owner_intents_ready` 不是状态字符串别名，而是上述证据、hash 相等性、decision 状态及 runtime 禁执行事实的严格合取，Owner 身份仍固定为未验证。

`live_readiness_passed` 只表示 readiness artifact 的预览时间窗仍有效：要求 `issued<=now<expires` 且窗口不超过 7200 s。它可以在当前 DENY 报告上为 true，绝不表示可签发或可执行；报告用 `ARTIFACT_TIME_WINDOW_ONLY__NOT_ISSUER_OR_EXECUTION_READINESS` 明示该范围，并保持 `signing_or_execution_ready=false`。顶层正式授权字段（包括 `owner_accepted`、`authority_flags`、`run_id`、正式 `issued_utc`/`expires_utc`）会导致失败。

## 5. 复验和机器裁决

```powershell
python -B -m pytest -q -p no:cacheprovider 70_tools/preauthorization_readiness/unified_r2_v2/tests
python -B 70_tools/preauthorization_readiness/unified_r2_v2/validate_release.py
python -B 70_tools/preauthorization_readiness/unified_r2_v2/independent_audit.py
python -B 70_tools/preauthorization_readiness/unified_r2_v2/build_release.py
```

`build_release.py` 只聚合本工具的固定证据输出，形成独立 pytest JSON、无环 manifest 与 Gate；manifest 绑定两份请求原始字节、冻结 source/input 原始 pin 和逐项测试/负控节点。受保护端点的 before/after 相等只是一项观测，不能单独证明从未发生瞬时写入；无生成结论还依赖工具没有 generator 执行路径以及静态调用审计。Gate 的 `PASS_PREAUTHORIZATION_READINESS_TOOLING_WITH_EXECUTION_DENIED` 只授予工具准备度信用，绝不授予任何工程、科学、执行或 Release 信用。

当前没有新的直接 Owner 原始来源，因此正式 current report 必须是 `DENY_NO_DIRECT_OWNER_SOURCE`。
