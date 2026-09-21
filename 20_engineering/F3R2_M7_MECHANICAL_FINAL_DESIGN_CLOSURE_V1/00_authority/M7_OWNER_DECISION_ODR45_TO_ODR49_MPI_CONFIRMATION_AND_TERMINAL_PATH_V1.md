# M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1 — Owner 决定登记记录（人读版）

- schema: `M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1`
- 生成时间：2026-08-23T20:37:08+08:00（宿主机本地时钟，Asia/Shanghai，UTC+08:00）
- 生成者：KIMI M7 机械终局接管 swarm Wave-4a (ODR-45..49 owner decisions + R2 full-flex closure) — AGENT-A1 OWNER_DECISION_REGISTER_RECORD
- class: OWNER_DECISION_REGISTER_ENTRY
- extends: `M7_OWNER_DECISION_ODR35_TO_ODR41_B601_HARNESS_RATED_ENVELOPE_V1.yaml`（sha256 `7655FA44BA4CD2B0369184100A18DF1001B8C40CC6B4D9731D4E4ACEE9D6433E`，本代理复算吻合）
- authority: OWNER_DIRECTIVE_20260823_MPI_CONFIRMATION_AND_TERMINAL_PATH
- review_status: RECORDED_AS_DIRECTED
- **next_stage_authorized: false ｜ release_credit: false**
- 机器文件：同目录同名 `.yaml`；**结构化字段与人读文本冲突时以 YAML 为准**

## 编号说明（numbering_note）

ODR-45..ODR-49 由本文件登记分配。登记链现状：`M7_OWNER_DECISION_REGISTER_V1.yaml` 承载 ODR-01..ODR-06；addendum 依次承载 ODR-18、ODR-19、ODR-20..ODR-26、ODR-27..ODR-34、ODR-35..ODR-41；ODR-07..ODR-17 在工作包/合同文件中被消费引用。**ODR-42 保持为申请编号**（`ROUTE_C_OWNER_DECISION_REQUEST_ODR42_V1.yaml`，APPROVAL_REQUEST_NOT_AUTHORIZATION_RECORD），由 ODR-44 裁决关闭，不占决定编号位。ODR-43/ODR-44 经本文件 ODR-45 正式并入登记链，原候选文件不改一字。禁止静默重号。

## 决定正文（逐字文本为权威；结构化分解仅为登记索引）

### ODR-45 — MPI_BRIDGE_OWNER_CONFIRMATION

> CONFIRM MPI bridge. Upgrade FROZEN_CANDIDATE_PENDING_OWNER_CONFIRMATION to CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE. WP11 remains physical-installation authority. ODR-01 T_SM remains dynamics-frame authority. All mass/CG/inertia/wrench/geometry transfers shall use the single explicit physical→dynamics bridge. No mixing, averaging or selective consumption is permitted.

登记要点：桥状态升级为 `CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE`（登记层升级；冻结桥文件 `B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml` 不改一字，其自记状态字段字面为 `FROZEN_CANDIDATE_PENDING_OWNER_CONFIRMATION_AND_MPI_FB08_GATE`；MPI-FB08 门肢体已落地 mpi_gate=PASS 21/21，本决定解除 Owner 确认肢体）。WP11 = PHYSICAL_INSTALLATION_AUTHORITY；ODR-01 T_SM = DYNAMICS_REFERENCE_AUTHORITY；B = T_PHYSICAL_TO_DYNAMICS = Trans(z,+0.02275 m)·Rot(z,+25.000014°) 为唯一显式桥，由冻结 frame 定义解析生成、永不重打为第二权威；mass/CG/inertia/wrench/collision-geometry 传递只能经 B；禁混用/平均/选择性消费。e21 29.041965867604112°/29.41085537835705° 保留为历史诊断，此后只消费桥接后的单一结果。本决定正式将 ODR-43/44 并入登记链（记录 sha256 `B695311B2885AEC601C336FFA4E1695BCAB063F725AD12133BA771F8BD25D06D`），并 Owner 确认 MC-A 裁决 `ENG-RULING-DYN-MASS-ALLOC-MC-A-V1`（文件 sha256 `9CCE829E1581B190C6FC50BAE56C47659C61319052268E7C9DFD25FAC8B8C9E4`，复算吻合）。

- closes: ODR43_ODR44_ADDENDUM_FORMAL_INCORPORATION；OI-R1-06_OWNER_CONFIRMATION；MPI_BRIDGE_OWNER_CONFIRMATION
- does_not_close: GAP-12（24 kg 预算重分配，OPEN）；r2_full_flexible_coupling（NOT_EVALUATED）；e15 REPEAT_ANCF_CERTIFICATION（逐字保持）
- does_not_grant: 任何 release/production/flight 权威；Route-C CAD 生成

### ODR-46 — ROUTE_C_RFI_AND_FREEZE

> ISSUE RFI-E, RFI-F and RFI-G using the already prepared scoped RFI definitions. Route-C remains FROZEN_PENDING_PHYSICAL_AUTHORITY. No Route-C CAD may be generated while any required physical capability field remains null.

登记要点：按 `ROUTE_C_RFI_GAP_MEMO_V1.md` §3.1–3.3 发出 RFI-E（微型电缆载体，覆盖 P12/P04）、RFI-F（导向/衬垫材料对，覆盖 P10）、RFI-G（夹具/固定硬件，覆盖 P13 与 P05 输入），非约束性、可索取样件。ROUTE_C = FROZEN_PENDING_PHYSICAL_AUTHORITY；C2-01 注册表 13 字段任一为 null 即禁止 Route-C CAD。可接受证据：manufacturer datasheet / vendor application note / traceable catalogue data / peer-reviewed or public engineering source / existing project test evidence；禁止：LLM-guessed values / generic web articles / unsourced rules-of-thumb。有可溯源源时字段可 null→CANDIDATE_RANGE 升级，无源保持显式 null。解禁要求 MPI PASS + C2-01 物理注册表齐备；准入门 `ROUTE_C_C2_ADMISSION_GATE`：bridge CONFIRMED 且 RFI-E/F/G resolved 且 13/13 non-null 且全部来源可溯源 → ROUTE_C_CAD_AUTHORIZED=true，否则 false。

- closes: （无）
- does_not_close: **OI-R1-05 remains HIGH OPEN pending responses**
- does_not_grant: Route-C CAD 生成；MPI-06/07 闭合（evidence_class_non_equivalence）

### ODR-47 — TOPOLOGY_NOMENCLATURE_FUNCTIONAL_RENAME

> Do not choose opaque M1/M2 as final canonical names. Freeze M1 and M2 as LEGACY_ALIAS only. Generate explicit functional canonical topology names and an alias register.

登记要点（解决 OI-R1-03）：**语义更正**——M1/M2 是两个处置选项（M1 = 交接侧改名；M2 = 双命名空间强制限定符），不是拓扑名；相冲突的拓扑标签是交接书 C-A/C-B/C-C 与仓库 RC-A..RC-D。裁决：对两套标签集按 `TOPOLOGY_<FUNCTION>_<ARCHITECTURE>_V1` 模式赋功能规范名（本登记不预造具体名称，`canonical_names_minted: null`）；交接书 C-*、仓库 RC-* 及 M1/M2 选项标签全部冻结为 LEGACY_ALIAS；生成 `TOPOLOGY_ALIAS_REGISTER_V1.yaml`（READ_ONLY_NO_API_LOOKUP）；历史不改写。共同禁令逐字：

> 无论 M1/M2，均禁止把交接书 C-C 与仓库 RC-C 互相绑定证据、需求或就绪度；禁止借改名/限定符把任何 HOLD 量提升为 AVAILABLE。

- closes: OI-R1-03
- does_not_grant: topology selection（CAD remains forbidden）；任何 HOLD 量升格

### ODR-48 — ROUTE_B_NEGATIVE_RESULT_TERMINAL_FREEZE

> Freeze Route-B full-range fixed external harness as: REJECTED_BY_EXACT_KINEMATIC_SWEEP. Preserve it as a documented negative result and a Route-C design requirement. Do not reopen Route-B.

登记要点：规范机器头条 `ROUTE_B_FULL_RANGE_FIXED_EXTERNAL_HARNESS = REJECTED_BY_EXACT_KINEMATIC_SWEEP`，锚定 V2 扫掠头条（clearance −11.9938 mm @SWEEP_joint2_09 vs link3；bend 0.1 mm @CORNER_110000:span_link5；pinch −11.9902 mm @HARDSTOP_joint4_hi joint5；`HARNESS_B601_FULL_FK_SWEEP_V2.json` sha256 `DB86348B8276FB2DCEB48DA30D1969948B37AAC4DF6D67D7588D928CF8281FAE`，复算吻合）。V1 机器头条（−11.8667/1.081/−11.3573）与圆整叙述（−11.86/2.26/−11.83）保留为逐字历史引用——三套拼写永不合并、永不取平均。根因保留：j2/j3 折叠包络消耗固定外置线束走廊，collision/bend/pinch 不能同时满足。措辞纪律——许可声明：**当前受测试的固定外置线束架构无法覆盖完整 accepted B601 hardware envelope**；禁止过度声明：**任何外部走线从数学上绝对不可能**。Route-B 不重开/不迭代/不改判据；成为 Route-C 需求输入（必须克服 Route-B 失效模式）。

- closes: OI-R1-04
- does_not_close: R2-HRN-04 FAIL_REDESIGN_REQUIRED（逐字保持）

### ODR-49 — SOLAR_R2_BUILD_REPORT_CM_REISSUE

> Solar R2 self-hash DRIFT is a CM defect, not a geometry defect. Reissue the build report using self-reference-excluded hashing. Do not modify Solar R2 geometry or frozen assets.

登记要点：OI-R1-01 是 CM/manifest 缺陷，不是几何缺陷。授权 `REISSUE_BUILD_REPORT_WITH_SELF_REFERENCE_EXCLUDED_HASHING`；Solar R2 STEP/FCStd/geometry/mass model/harness/flex input 一律不改；重发报告必须证明 old payload digest == new payload digest（仅 self-reference 字段除外）；OI-R1-01 在重发核验落入 CM 刷新后关闭。现状记录：`SOLAR_ARRAY_R2_BUILD_REPORT_V1.json` 实测 sha256 `6160C1D0970B7EA19075B4A83C988C16CA2F1AFCA782BCAD90A89B14F17E6586` ≠ 自记录 `AFE4CA26A2CC7A1838DEF4FAD3E068DB1F364F4265A85903D9407D462711CEC9`，DRIFT 持续；两个真实工件 STEP/FCStd 复算 PASS 结论不变。

- closes: OI-R1-01（条件：重发核验落入 CM 刷新后）
- does_not_grant: Solar R2 几何或任何冻结资产的修改；payload 非 self-reference 字段的任何改动

## autonomous_next_actions（Owner 十项指令）

1. continue R2 Full-Flex closure
2. build HF three-leaf/wing model
3. derive 3-5 mode/wing ROM
4. regress against 6.9726/39.3586/98.0042 Hz witnesses
5. run Rigid vs Legacy-R1-Flex vs R2-Flex at 22kg/0.5dps and 150kg/3dps anchors
6. propagate bounded EI/GJ/hinge/damping/latch uncertainties
7. prepare MECH_DYNAMICS_INTERFACE_V6 + EMBODIED_MECHANICAL_CONTRACT_R3 for candidate rebinding
8. no Route-C CAD until C2 admission gate passes
9. preserve all external/flight/full-range harness gaps as explicit deferred HOLDs
10. return only at Full-Flex Gate / Route-C C2 Admission Gate / Terminal Mechanical Release candidate

## terminal_release_policy（双层）

- **Gate A** = `MECHANICAL_ENGINEERING_DESIGN_RELEASED FOR_R2_OPERATIONAL_DIGITAL_TWIN_AND_EMBODIED_CONTROL WITH_BOUNDED_OPERATIONAL_ENVELOPE`，要求全部满足：bridge confirmed、R2 mass/frame consistent、Solar R2 frozen、Gripper R1 closed、mission harness envelope valid、R2 full-flex closed、MECH→Embodied gate PASS、HIGH open items = 0。
- **Gate B** = `FULL_HARDWARE_RANGE_AND_FLIGHT_MECHANICAL_QUALIFICATION`（FUTURE）。
- SCOPED_MECHANICAL_RELEASE 允许在 FULL_JOINT_RANGE_HARNESS = HOLD 下签发。
- TMG 板（Owner 指令快照）：TMG-1 Product = PASS；TMG-2 Mass = PASS_CONFIRMED；TMG-3 Mechanism = PASS；TMG-4 Harness = PARTIAL；TMG-5 Flexibility = ACTIVE；TMG-6 Mechanical-to-Embodied = CANDIDATE_REBIND_READY；TMG-7 Adversarial = PASS_WITH_CM_OPEN_ITEMS。

## standing_prohibitions_carried_unchanged（11 项，自 ODR-43/44 记录逐字携带）

no_flight_or_launcher_or_manufacturing_release_claims ｜ no_zero_fill_of_unknowns ｜ no_cad_mass_override_of_accepted_urdf_masses ｜ no_typical_property_as_design_allowable_for_flight_margin ｜ memory_gate_6gib_remains_failed ｜ no_file_exists_then_pass ｜ no_null_coerced_to_zero ｜ no_PROVISIONAL_as_authority ｜ no_frame_averaging ｜ no_silent_reuse_of_legacy_24kg_mass_model_or_Solar_R1_flex_model ｜ no_renaming_of_Route_B_negative_results

## nonclaims

- 本登记不授予任何 release、production、manufacturing、qualification、launcher 或 flight 权威
- 本登记不关闭 Route-C（ROUTE_C 保持 FROZEN_PENDING_PHYSICAL_AUTHORITY；OI-R1-05 保持 HIGH OPEN）
- 本登记不重开 Route-B（REJECTED_BY_EXACT_KINEMATIC_SWEEP 终态冻结）
- 本登记不修改 Solar R2 几何或任何冻结资产
- e15 REPEAT_ANCF_CERTIFICATION 逐字保持；R2-HRN-04 FAIL_REDESIGN_REQUIRED 逐字保持
- candidate ≠ authority；test PASS ≠ gate PASS；PROVISIONAL 不静默升格；unknown 保持显式 null 不压 0

## 哈希纪律

全部引用 pin 为 sha256 over raw bytes、64-hex 全长，本代理 2026-08-23T20:37+08:00 复算吻合（详见 YAML `verification_record` 与 `evidence_links`）。self_hash_policy: SELF_REFERENCE_EXCLUDED - this file carries no hash of itself; downstream consumers pin its sha256 after emission (same policy as e21/V5 manifests and 02_bridge)。
