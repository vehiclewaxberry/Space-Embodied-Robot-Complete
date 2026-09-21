# TOPOLOGY_ALIAS_REGISTER_V1 — 拓扑别名登记册（ODR-47 执行件）

- schema：`TOPOLOGY_ALIAS_REGISTER_V1`
- generated_local：2026-08-23T20:34:48+08:00（HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08）
- generator：KIMI M7 机械终局接管 swarm Wave-4a (ODR-45..49 owner decisions + R2 full-flex closure) — A4 topology alias register agent（ODR-47 执行）
- 状态：**ISSUED_PER_ODR47**；`selection_made: false`；`next_stage_authorized: false`；`release_credit: false`
- 配套机器文件：同目录 `TOPOLOGY_ALIAS_REGISTER_V1.yaml`（**冲突时以 YAML 结构化字段为准**）
- self_hash_policy：SELF_REFERENCE_EXCLUDED — 本文件不携带自哈希；下游消费方在签发后钉 sha256（同 e21/V5 manifests 与 02_bridge 口径）

## 0. 授权与锚点

- 执行裁决：ODR-47。ODR 记录件 `00_authority/M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml` 在本件签发时**尚未落盘**（2026-08-23T20:31..20:34+08:00 期间多次复核 00_authority/ 目录均无此文件）——其 sha256 钉值在 YAML 中保持显式 null，绝不压实；CM 代理须在该记录落盘后回填钉值。
- ODR-43 / ODR-44 纪律不变：CAD 仍禁止（Route-C 独立版本化 CAD 候选在 MPI-01..08 全闭合前禁止）。
- 裁决依据：`TOPOLOGY_ID_MAPPING_PROPOSAL_V1.md`（同目录），sha256 `42176da851274b9dcd5378a9d8f780c782f6fd5f625462c483cdf8434288fc9d`（已复算吻合任务钉值）。
- 本登记册性质：**只读别名登记**（READ_ONLY_ALIAS_NO_API_LOOKUP / READ_ONLY_HASH_GUARD）；不选型、不改上游一字、不改写历史、不闭合任何 MPI 行。

## 1. 受控规范名（canonical_names，命名型式 TOPOLOGY_<FUNCTION>_<ARCHITECTURE>_V1）

| canonical_name | 源命名空间 | 源标签 | 源逐字定义 / architecture | 源逐字状态 |
|---|---|---|---|---|
| TOPOLOGY_JOINT_LOCAL_OMEGA_LOOPS_V1 | 交接书 | C-A | joint-local Ω loops | NOT_READY（0/9 受控） |
| TOPOLOGY_SEMI_CAPTIVE_DRESS_PACK_V1 | 交接书 | C-B | semi-captive dress-pack | NOT_READY（0/11 受控） |
| TOPOLOGY_MINI_CARRIER_HYBRID_V1 | 交接书 | C-C | mini cable-carrier hybrid | NOT_READY（0/13 受控） |
| TOPOLOGY_CAPTIVE_GUIDED_HYBRID_V1 | 仓库 | RC-A | captive-guided-hybrid | PROPOSED_FOR_ODR42_NOT_SELECTED |
| TOPOLOGY_ALL_JOINT_SEMI_CAPTIVE_CARRIER_V1 | 仓库 | RC-B | all-joint-semi-captive-carrier | ALTERNATE_NOT_SELECTED |
| TOPOLOGY_DUAL_DRESS_PACK_HYBRID_V1 | 仓库 | RC-C | dual-dress-pack-hybrid | TRADE_ONLY |
| TOPOLOGY_IMPROVED_FREE_LOOP_V1 | 仓库 | RC-D | improved-free-loop | REJECTED_AS_PRIMARY_CONCEPT |

- RC-D 逐字 rejection_basis 随名携带："Does not eliminate the uncontrolled fold and snag mechanisms observed in Route-B."
- 硬件注记：TOPOLOGY_MINI_CARRIER_HYBRID_V1 含微型拖链载体硬件（需要 P04/P12，均 REQUIRED__HOLD 无候选源）；TOPOLOGY_DUAL_DRESS_PACK_HYBRID_V1 为电源/数据分离双 dress-pack，**无载体硬件**，拓扑级不需要 P04/P12。
- 证据钉（全部复算）：交接书盘点 JSON `b91611f9837641a0bf1bbf555534b2d87eb2a5005fde06ef04b3cdd3374353b7` / MD `8f52138f0d657f3fb99642daa17dfb61b73b539d2cd8ed6c46ef584376ad2c3d`；参数空间 YAML `230d8c3c6e45a9f6c7aa1d6d4d09385fdce0c6f614d8af105d57a0d4be01d489`；概念权衡 CSV `5553b3ca48023aee185380802b3378f99c71099db04bda91f52dedbca600411a`。

## 2. 遗留别名（legacy_aliases）

- 交接书 C-A/C-B/C-C 与仓库 RC-A/RC-B/RC-C/RC-D 各自 → 上表对应规范名；relation = **EQUAL_ALIAS**；`api_lookup_allowed: false`。
- `M1:` 与 `M2:` 条目 = 两个**处置方案**的 LEGACY_ALIAS（M1=交接侧改名方案；M2=双命名空间强制限定符方案），二者均 **SUPERSEDED_BY_ODR47_FUNCTIONAL_NAMING**，`api_lookup_allowed: false`。

## 3. 语义更正（semantic_correction）

M1/M2 曾是 C-C/RC-C 命名冲突的两个**处置方案**（改交接侧名 / 双命名空间加限定符），从来不是拓扑名（证据：TOPOLOGY_ID_MAPPING_PROPOSAL_V1.md §4，sha256 `42176da851274b9dcd5378a9d8f780c782f6fd5f625462c483cdf8434288fc9d`）。ODR-47 功能命名已直接覆盖实际相撞的标签集（交接书 C-A/C-B/C-C 与仓库 RC-A..RC-D 各得唯一规范名），新工件无需改名上游文本、无需限定符纪律即可无歧义。

## 4. 显式断言（explicit_assertions）

1. **TOPOLOGY_MINI_CARRIER_HYBRID_V1 NOT_EQUAL TOPOLOGY_DUAL_DRESS_PACK_HYBRID_V1**——ex-交接书 C-C ≢ ex-仓库 RC-C；硬件内容不同（前者含微型拖链载体，后者无载体、为电源/数据分离双 dress-pack）。
2. C-A ≈ RC-A：**INTERPRETIVE_NEAREST_NEIGHBOR_NON_AUTHORITATIVE**。语义差警示逐字：非等同：RC-A 除 J1 捕获式定曲率盒、J5/J6 定曲率腕部包络外，还含 J2/J3 父子半捕获移动导向或滚动环、J4 side-bypass 与 guided-loop 互斥权衡——不只是"关节局部 Ω 环"。
3. C-B ≈ RC-B：**INTERPRETIVE_NEAREST_NEIGHBOR_NON_AUTHORITATIVE**。语义差警示逐字：非等同：RC-B 逐字为全部六关节半捕获载体；交接书 C-B 的 "dress-pack" 表述未声明全部六关节均为载体。
4. TOPOLOGY_IMPROVED_FREE_LOOP_V1（RC-D）**无交接对应**；仓库侧已 REJECTED_AS_PRIMARY_CONCEPT。

## 5. 绑定护栏（binding_guards）

- P04 carrier_travel_mm / P12 carrier_size_mm **仅**挂 TOPOLOGY_MINI_CARRIER_HYBRID_V1；永不挂到 TOPOLOGY_DUAL_DRESS_PACK_HYBRID_V1。
- 就绪度矩阵行永不跨 NOT_EQUAL 对绑定：NOT_READY（0/13）行专属于 TOPOLOGY_MINI_CARRIER_HYBRID_V1；TRADE_ONLY 状态专属于 TOPOLOGY_DUAL_DRESS_PACK_HYBRID_V1。
- 随附仓库互斥规则（逐字携带）："Exactly one of RC-A, RC-B, RC-C or RC-D may be active in a diagnostic branch. Results shall never be averaged across branches."

## 6. 共同禁令（逐字）

无论 M1/M2，均禁止把交接书 C-C 与仓库 RC-C 互相绑定证据、需求或就绪度；禁止借改名/限定符把任何 HOLD 量提升为 AVAILABLE

## 7. 遗留策略（legacy_policy）

- `original_files_unchanged: true`；历史不改写（`history_rewritten: false`）。
- 登记册角色：READ_ONLY_ALIAS_NO_API_LOOKUP；模式：READ_ONLY_HASH_GUARD。
- 先例样式：`B51R1_G1A_FEATURE_NAMING_MACHINE_RATIFICATION.yaml`（sha256 `f598a6f286814b856507e3d643020e2cb839d237f1b005d2535fea53db0d01a4`）的 alias_register/legacy_policy 模式。

## 8. 验证记录（verification_record）

- 方法：sha256 over raw bytes；全 64 位十六进制钉值，新证据链中绝不截断。verified_at = 2026-08-23T20:34:48+08:00。
- 复算结果：提案 MD 5869 B / `42176da8…88fc9d` **MATCH_TASK_PIN**；盘点 MD 10892 B / `8f52138f…d2c3d` MATCH；盘点 JSON 31983 B / `b91611f9…353b7` MATCH；参数空间 YAML 8221 B / `230d8c3c…01d489` MATCH；概念权衡 CSV 1382 B / `5553b3ca…0411a` MATCH；B51R1 先例 YAML 3708 B / `f598a6f2…d01a4` MATCH。
- ODR45-49 记录件：**签发时缺席**，bytes/sha256 显式 null，未复算（ABSENT_AT_EMISSION）。

## 9. 收口声明

- `selection_made: false`——未选任何拓扑；CAD 仍禁止（ODR-44 不变）。
- 本件闭合 **OI-R1-03**（CONFIGURATION_NOMENCLATURE，Owner 裁决映射表已落地为受控规范名登记册）；OPEN_ITEMS 登记册的形式化刷新由后续波次 CM 代理执行，本代理不触碰。
- HOLD 逐字携带：0/9、0/11、0/13 NOT_READY；PROPOSED_FOR_ODR42_NOT_SELECTED；ALTERNATE_NOT_SELECTED；TRADE_ONLY；REJECTED_AS_PRIMARY_CONCEPT（含 rejection_basis 逐字）。
- nonclaims：未选型；未授权/未执行任何 CAD/FEA；未闭合任何 MPI 行；未把任何 HOLD 提升为 AVAILABLE；未合并/平均 Route-B 三套被拒数字口径、未消费 Route-B 隔离种子值；未消费任何 R1-lane 遗留值（0.3483933 kg、1.7419665、legacy 24.0 kg 质量模型、"measured_mass"）；candidate ≠ authority；test PASS ≠ gate PASS；PROVISIONAL 未被静默提升；本登记册不做 API 查询。
- `next_stage_authorized: false`；`release_credit: false`。
