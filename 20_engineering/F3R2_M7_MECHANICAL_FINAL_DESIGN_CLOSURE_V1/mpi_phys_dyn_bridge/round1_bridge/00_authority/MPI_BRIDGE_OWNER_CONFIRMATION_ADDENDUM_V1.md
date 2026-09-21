# MPI_BRIDGE_OWNER_CONFIRMATION_ADDENDUM_V1（人读版）

- **schema**: `MPI_BRIDGE_OWNER_CONFIRMATION_ADDENDUM_V1`
- **generated_local**: `2026-08-23T20:42:34+08:00`（HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08）
- **generator**: KIMI M7 机械终局接管 swarm Wave-4a (ODR-45..49 owner decisions + R2 full-flex closure) — A2 MPI bridge owner-confirmation operational addendum agent
- **class**: `ADDENDUM_ONLY__ORIGINAL_FILES_UNTOUCHED`
- **冲突仲裁**: 本 MD 为人读版；与 YAML 结构化字段冲突时，**以 YAML 为准**。

## 0. 用途

登记 Owner 决定 **ODR-45**（载于 `00_authority/M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml`，sha256 `69473BC19E020C6422B23C1758CFC343874F641781C9782E982036614C0849B5`，26885 B）对 MPI 物理→动力学桥车道的确认迁移。全部迁移发生在登记/运行层；**任何原始/冻结文件不改一字**。

## 1. bridge_status_transition（桥状态迁移）

- `FROZEN_CANDIDATE_PENDING_OWNER_CONFIRMATION` → **`CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE`**（per ODR-45）。
- 冻结桥文件 `02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml` 字节不变，sha256 `0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C`（本 agent 复算吻合；文件内历史 status 字段逐字保留）。
- 权威地图复述：WP11 physical installation = 物理安装权威；ODR-01 T_SM = 动力学参考权威；**B = T_PHYSICAL_TO_DYNAMICS 为唯一显式桥**；流向 Physical CAD →(B)→ Dynamics frame；mass / CG / inertia / wrench / collision-geometry 的传递与登记只能经 B。
- 五项禁令：禁止二选一/选择性消费；禁止取平均；禁止静默坐标替换（隐式转换）；禁止按模块混用；禁止把 0.3688895107529362° 分支差重标为不确定度（`standard_uncertainty` 保持 null）。
- 解析生成规则：桥永远由冻结 frame 定义（hash-pinned e21 authority contract 放置假设）解析生成；闭式 `B = Trans(z_A0, +0.02275 m)·Rot(z_A0, +25.000014°)` 是解析结果；任何数值拼写永不成为第二权威。

## 2. odr43_odr44_incorporation（ODR-43/44 正式并入）

- ODR-43/44 候选记录经 ODR-45 **正式并入登记链**：review_status 由 `RECORDED_AS_DIRECTED__ADDENDUM_CANDIDATE_PENDING_OWNER_CM_FORMAL_INCORPORATION` 迁移为 **`INCORPORATED_BY_ODR45_CHAIN_RECORD`**（登记层迁移；原候选文件不改一字）。
- 双 pin：候选记录 `ODR43_ODR44_OWNER_AUTHORIZATION_RECORD_V1.yaml` sha256 `B695311B2885AEC601C336FFA4E1695BCAB063F725AD12133BA771F8BD25D06D`；ODR-45..49 记录 sha256 `69473BC1...0849B5`（全 64-hex 见 YAML）。

## 3. mc_a_owner_confirmation（MC-A 裁决 Owner 确认）

- `ENG-RULING-DYN-MASS-ALLOC-MC-A-V1`：`ISSUED_AND_EFFECTIVE_AT_ENGINEERING_LEVEL__PENDING_OWNER_CONFIRMATION__REVERSIBLE_VIA_ECR` → **`OWNER_CONFIRMED_BY_ODR45`**。
- 工程内容不变：leaf-only Mqq 唯一权威；每翼 2×0.03 kg 铰点质量作刚性非随动界面质量记于铰线；`dynamic_mass_allocation_frozen` 保持。
- 可逆性 RC-1..RC-4 逐字携带（ECR 或 Owner 显式动作）。
- OI-R1-06 → **OWNER_CONFIRMED**；寄存器转录属 CM agent 工作道，本 addendum 不写任何寄存器。
- 裁决文件 pin：`ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml` sha256 `9CCE829E1581B190C6FC50BAE56C47659C61319052268E7C9DFD25FAC8B8C9E4`（复算吻合）。

## 4. e21_forward_consumption_rule（e21 前向消费口径）

- `single_arm_placement_consumption_semantics` 前向状态 = **`RESOLVED_BY_ODR45_SINGLE_BRIDGED_CONSUMPTION`**；e21 权威合同中的历史冻结 `UNRESOLVED` 逐字保留（合同不动，V6/R3 候选继续逐字携带）。
- 历史结果 29.041965867604112°（ODR-01 车道）/ 29.41085537835705°（WP11 车道）保留为**历史诊断**。
- 此后只消费桥接单一结果 **29.41085537835705°，`standard_uncertainty: null`**。
- 验收规则逐字：acceptance NEVER uses proximity to 29.041965867604112 or 29.41085537835705——禁止对该数值对 proximity-accept，禁止平均。

## 5. rt2_f01_annotation_addendum（RT2-F01 注释登记）

按 `MPI_BRIDGE_GATE_V1.json` RT2-F01 的 action_required_by（Owner 签署前的 Owner/CM 注释 pass）登记：

- 冻结桥 `known_deviation_register[WP11-F-03_ROUNDED_CLOCK_SPELLING]` 的 `matrix_max_abs_vs_bridge = 5.180141831595542e-07` 属于**角度合成重建**：θ = atan2(0.422618, 0.906308) = 24.999981251686034°（登记显示拼写 24.999981252°），全精度三角（等价于 6 位拼写对的单位范数重建）。本 agent 复算 = `5.180141831595542e-07`，**逐位 MATCH**。
- **字面 6 位三角拼写本身**（sin/cos = 0.422618/0.906308，未归一化）给出 `4.83193000000437e-07`（rt2 复算值；本 agent 再复算，**逐位 MATCH**）。两数值均已登记。
- 冻结桥文件 **NOT modified**（字节不变，sha256 复算吻合）。
- 无工程影响：C01 arm-CG witness 在两种拼写下均复现（mutual 1.9e-14 m，引自 RT2-F01 disposition 原文）；~1.1e-4 mm 偏差量级不变；FB04-11/FB06-06 容差带不受影响。

## 6. rt2_f02_carry（RT2-F02 转携带）

- FB03-14/15/16 重新标记为 **SAME-PATH REPRODUCTION CHECKS**（同一 numpy/LAPACK 操作序列，恒满足）。
- 真正独立的证据：dense-vs-rigid inverse `4.709566070459914e-13`；stored-B × stored-invB 往返 `5.195843755245733e-13`；rt2 / FB-08 重建 `0.0`。
- 折叠进未来验证轮；不阻断门 PASS 范围；21/21 PASS 结论不变。

## 7. rebind_candidates_status（重绑候选状态）

- `MECH_DYNAMICS_INTERFACE_V6_CANDIDATE`（sha256 `4C52A68AA6E0749A2425D9E8CDB6C9F4477F5D4047C9D6C0BA6F0D95E97D184D`）与 `EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE`（sha256 `F3D6EC1D370FB26215A259391D5026CA4C261C7C4880AE6FD70AE2C0F0DDFC56`）**保持 CANDIDATE**（status 逐字：`CANDIDATE_ONLY__NOT_RELEASE_NOT_PRODUCTION_NOT_FLIGHT__PENDING_OWNER_REVIEW`）。
- ODR-45..49 记录 autonomous_next_actions 第 7 项授权**准备**其 rebinding review；candidate ≠ promotion；review ≠ promotion；base 文件字节不变。
- 注：两候选内嵌的桥 classification 字段为 ODR-45 之前的发射时拼写，按 addendum-only 纪律不改写，待 rebinding review 处理。

## 8. carried_holds_verbatim（逐字携带的 HOLD）

- `e15_ancf_certification`: **REPEAT_ANCF_CERTIFICATION**（逐字；ODR-45 不授权重认证运行）。
- `r2_harness_R2_HRN_04`: **FAIL_REDESIGN_REQUIRED**（逐字）。
- `r2_full_flexible_coupling`: **`IN_PROGRESS_PER_OWNER_DIRECTIVE`**（原 `NOT_EVALUATED`）——仅标记 Owner 授权的全柔性闭合工作包**启动**，不是闭合、不是评估结论；评估判定在全柔性 Gate 实际评估前保持 NOT_EVALUATED。
- MECHANICAL_LOOP **V5 门保持 HOLD**（今日复读核实 gate=HOLD、next_stage_authorized=false），待消费 FB-08 输入包的 V5 重评估。
- collision / contact / target_attachment / mission_capture = HOLD_NOT_EVALUATED；production = HOLD；flight = HOLD——均不变。
- **OI-R1-05 保持 HIGH** 不变（STILL_HIGH__RFI_MEMO_RECORDED_GAP_OPEN；ODR-46 发出 RFI-E/F/G 但不闭合本项）。

## 9. verification_record（复核记录）

- 14 项 sha256 pin 全部由本 agent 以 raw-bytes 全 64-hex 复算，**全部 PASS**（含 ODR-45..49 记录、桥、ODR43/44 记录、MC-A 裁决 yaml+md、V6/R3 候选、MPI 门、e21 桥接门 V2、e21 权威合同、V5 门、e15 gate_summary、登记链根、OPEN_ITEMS_UPDATE_V1.csv）。逐条明细见 YAML `verification_record.pins`。
- 2 项 RT2-F01 数值复算（角度合成 5.180141831595542e-07 / 字面 6 位 4.83193000000437e-07）**逐位 MATCH**，见 YAML `verification_record.numeric_recomputations`。

## 页脚（fail-closed）

- `next_stage_authorized: false`
- `release_credit: false`
- `nonclaims`：见 YAML（不授予任何 release/production/manufacturing/qualification/launcher/flight 权威；不改任何原始/冻结文件；不关闭任何 HOLD；不升格候选；不写寄存器；不授权 Route-C CAD；test PASS ≠ gate PASS；unknown 保持显式 null）。
- `self_hash_policy`: SELF_REFERENCE_EXCLUDED - this file carries no hash of itself; downstream consumers pin its sha256 after emission (same policy as e21/V5 manifests and 02_bridge)。
