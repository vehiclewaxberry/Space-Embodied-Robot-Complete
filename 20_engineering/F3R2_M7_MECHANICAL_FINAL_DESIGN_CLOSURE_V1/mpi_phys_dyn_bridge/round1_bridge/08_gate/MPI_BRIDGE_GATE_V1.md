# MPI_BRIDGE_GATE_V1 — MPI-FB-08 Gate 组装裁决（人读版）

- 生成时间：2026-08-23T19:37+08:00（宿主机本地钟，Asia/Shanghai）
- 机器裁决源：`MPI_BRIDGE_GATE_V1.json`（schema=MPI_BRIDGE_GATE_V1）；冲突时以 JSON 结构化字段为准
- 独立复算证据：`FB08_INDEPENDENT_RECOMPUTATION_V1.json`（42/42 PASS，sha256 A5678600AE04…）
- 清单刷新：`MPI_BRIDGE_PACKAGE_MANIFEST_V2.json`（50 条，sha256 EF9D71C697A1…）
- 纪律：本轮只读全部上游与 round0/round1 已落盘文件，只写 `08_gate/`；未启动任何 CAD/FEA 进程；git 只读

## 裁决：mpi_gate = PASS（限域 PASS）

PASS 仅覆盖**安装语义桥接**：frame / 质量 / 惯量 / 消费者 / 哈希五类歧义在 MPI-FB-02..07 主链上机器复算清零，FB-01 §f 九条判据全过。本 PASS 不授予任何 release / 生产 / 制造 / 鉴定 / 发射 / 飞行权威，不解除任何 HOLD。

### 交接书底线五条（全部显式为零）

| 底线 | 值 | 复算证据 |
|---|---|---|
| frame_ambiguity | 0 | 全包内唯一桥定义文件 = B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml；23 个引用文件全部带已验证 sha 0ACEB659284CAB86（V09-01） |
| mass_inconsistency | 0.0 | 九构型 candidate − V3_R2 stated 质量差逐构型精确 0.0（V05-01，独立重解析两文件复算） |
| inertia_inconsistency | 0.0 | 抽检 C01/C05/C07：candidate−stated 惯量差由臂行桥作用完全解释，残差 0.0（V05-02）；FB-06 全九构型最差 5.55e-16 ≤ 1e-12 |
| consumer_ambiguity | 0 | FB-05/V6/R3 的 consumer_ambiguity_count 字段全 0；FB-05 审计 mount 构造点=1、mount_used=T_S_A0_dyn@B==T_phys（0.0）；FB-06 九构型 9/9 单一 ODR01 消费语义（V04-01/V09-02/V09-03） |
| hash_mismatch | 0 | Manifest V2 复走：V1 42 条 41 条字节级吻合、0 缺失、1 条例行重跑有案（rt2_static_output.json）；31 条交叉引用 pin（26 上游 + 5 包内产物）复算零失配（V08-01） |

## 九条判据逐条结论（FB-01 §f）

1. **桥文件存在 + sha 自洽 + 双源逐位一致 → PASS**：桥内 T_S_A0_dynamics / T_S_A0_physical 与 e21 权威合同（sha 7D2E0792…）逐字段 max-abs = 0.0；B 由哈希钉入合同经刚体逆重建 vs 桥文件 max-abs = 0.0（V01-01/02/03）。
2. **往返/正交/行列式/手性 ≤1e-12 + 负控全捕 → PASS**：closure T_dyn@B==T_phys = 0.0；det(R_B)−1 = +5.196e-13（手性 +1）；‖RᵀR−I‖ = 5.196e-13；往返 5.196e-13；导出角 25.000013999932346°、轴 [0,0,1]；FB-08 自做变异负控（θ 取反→closure 0.845、t 取反→0.0455、两架取平均→det 0.9532）全部 firing；FB-03 报告 21/21 字段复核一致（V01/V02 组）。
3. **FB-04 验证清单 + 无逐元素旋转/无不确定度阵误用 → PASS**：质量不变 0；臂 CG 映射 1.7e-18 m；主惯量不变 1.31e-13；Steiner witness m·t² = 0.0024302436760318276 kg·m² 复算差 0.0；禁径字面读法偏差 0.0077107 明确非零并登记 FORBIDDEN；WP11 物理车道从 V3_R2 C07 成员经 C_S_inv 独立再聚合 vs FB-04 发布值：质量 0 差、CG 6.0e-17、惯量 1.2e-15；车道差 CG 0.0035243481425655 m / 惯量 0.1031195352285 kg·m² 由桥精确解释（V03 组）。不确定度政策确认：桥不确定度=null、成员声明不确定度逐字携带、无 R·U·Rᵀ。
4. **FB-05 consumer_ambiguity_count==0 + 不变式达标 + 未覆盖上游 → PASS**：单权威峰值 29.41085537835705°，standard_uncertainty=null；验收声明不以逼近 29.041965867604112°/29.41085537835705° 为据（字段在案）；dP 2.6e-16 / dL 2.4e-16 / 能量 4.0e-11 / 质量阵 SPD；e21 mandatory_holds 与合同逐字一致；红队独立重跑 23/23 PASS；未覆盖上游：FB05-13 目录哨兵空 + rt2 77 文件哨兵 0/0/0 + FB-08 复算 26 条上游 pin 零失配（V04 组、V08-01）。
5. **FB-06 九构型质量不变式 0 差 + 差异拼写级解释 → PASS**：C07..C09 与 stated 精确 0 差；C01/C05/C07 从 composition_candidate 六成员再聚合 vs bridged_candidate：0.0 / 0.0 / ≤8.7e-19；臂行经 C_S 重表达与 FB-06 臂行 max-abs 0.0；非臂成员与臂非桥字段（含不确定度块）与 V3_R2 深度相等；C05 的 HELD_CANDIDATE pose_status 逐字携带；FK 残差 C01 1.1314e-7 m / C05 1.0858e-7 m 落在登记拼写带、C07 机器零；候选惯量 SPD（V05 组）。
6. **FB-07 候选在案 + R2 基文件哈希未变 → PASS**：V5_R2 = 9B6D8025…、R2 = 5DDA6277…，与 round0 收据 pin 字节级一致；V6/R3 均 candidate:true、next_stage_authorized=false、桥 sha 钉入；逐字携带机器比对：e21 holds 11/11、V5 invariants 11/11、R2 holds 11/11、R2 prohibitions 8/8；V6/R3 source_register 全部 sha 复算吻合（V06 组）。
7. **纪律扫描 → PASS**：七件主链产物全数值叶黑名单（平均峰 29.226410622980581°、两车道 CG/惯量中点、旧 24 kg、R1 帆板 0.3483933/1.7419665，rel-tol 1e-9）0 命中；averag*/midpoint/blend 关键词 14 处全部处于禁令/否定/声明 false/检测器名语境；分支差未改标为不确定度；V6/R3 无 measured_mass 字段（唯一命中为禁令文本本身）（V07 组）。
8. **强制 HOLD 逐字携带 → PASS**：e15=REPEAT_ANCF_CERTIFICATION、R2-HRN-04=FAIL_REDESIGN_REQUIRED、r2_full_flexible_coupling=NOT_EVALUATED、collision/contact/target/mission=HOLD_NOT_EVALUATED、production/flight=HOLD、owner_review=PENDING；V5 总 gate 今日复读仍为 HOLD、single_consumption_rule_resolved=false（V04-04、V06-02、V10-01）。
9. **Gate 输出 = V5 重估输入包 + 不自授权 + Route-C CAD 禁入 → PASS**：输入包十件带复算哈希列于 JSON `input_package_for_mechanical_loop_v5_reevaluation`；本 gate 置 next_stage_authorized=false、release_credit=false；ODR-43/44 登记仍为 addendum candidate 待 Owner/CM 并入；C2-01 登记骨架复验全 null/全 HOLD（无 AVAILABLE）（V10-01）。

## RT2 四条 LOW 处置（finding_disposition，已入 JSON 附录）

- **RT2-F01（桥文件登记条目）**：文本级修正说明已记录、冻结文件未改——WP11-F-03 条目引用的 6 位 trig 拼写（0.422618/0.906308）与登记的 matrix_max_abs=5.180e-07 分属两种重构；5.180e-07 对应角度合成重构（θ=24.999981252° 全精度 trig），6 位拼写本身为 4.832e-07。Owner 签署前应由 Owner/CM 加注归属。工程影响为零：C01 臂 CG 见证在两种拼写下互相复现（差 1.9e-14 m），1.1e-4 mm 级偏差带不变。
- **RT2-F02（FB03-14/15/16）**：文本级改标已记录——该三条 1e-16 限值检查为同路径复现（同一 numpy/LAPACK 操作序列），本 gate 将其改标为 SAME-PATH REPRODUCTION CHECKS，独立证据引用跨路径见证（dense-vs-rigid 4.71e-13、B×inv(B) 往返 5.196e-13）+ rt2 独立代码复算 + 本 gate 刚体逆重建（0.0）。21/21 PASS 不受影响。
- **RT2-F03（UNRESOLVED 与 single-consumption 共存）**：本 gate 显式说明——V6/R3 中逐字携带的 e21 mandatory_holds `single_arm_placement_consumption_semantics: UNRESOLVED` 是 e21 权威合同的**权限级历史状态**，只能由 Owner/CM 解除；V6/R3 的 `single_consumption_semantics_block`（consumer_ambiguity_count: 0）是 FB-05 起经 ODR-43 桥引入的**前向候选级语义**，候选≠升格。二者共存不矛盾；V5 gate 今日仍 `single_consumption_rule_resolved: false`（已复验），与此读法一致。
- **RT2-F04（__pycache__ 卫生项）**：无需行动。本 gate 未 import 任何上游模块（全部按原始字节/yaml/json 解析），未触碰上游 __pycache__ 状态。

## 不解禁项（nonclaims，逐条在案）

- Route-C 物理输入全 HOLD：OI-R1-05 仍 STILL_HIGH（P10/P11/P12 全 null，RFI 缺口 OPEN）。
- r2_full_flexible_coupling 仍 NOT_EVALUATED；e15 仍 REPEAT_ANCF_CERTIFICATION；R2-HRN-04 仍 FAIL_REDESIGN_REQUIRED；V5 总 gate 仍 HOLD。
- owner_confirmation=PENDING：桥当前 FROZEN_CANDIDATE_PENDING_OWNER_CONFIRMATION；ODR-43/44 待 Owner/CM 正式并入；MC-A 裁决工程级生效、Owner 确认 pending。
- OI-R1-01（solar build report 自哈希 DRIFT）待上游 erratum——本轮复现与登记一致（实测 6160C1D0… ≠ 自记录 AFE4CA26…），非新失配；OI-R1-03/04 待 Owner。
- route_c_cad_entry：ODR-44 + C2-01 全 null 双重阻塞，本 gate 不解禁。
- downstream_unblocked：V6/R3 候选可进入正式重绑定评审（仍候选级）；ROM 参与因子计算前置（SLOT-07）由 MC-A 裁决在工程级解除。
- next_stage_authorized=false、release_credit=false、released_segments=0。

## Manifest V2 摘要

50 条（wave_2a_round0=10、wave_2a_round1=27、wave_2b=10、wave_2c_fb08_gate=3）；V1 42 条交叉核对：41 条字节级吻合、0 缺失、1 条例行重跑（rt2_static_output.json，红队重跑有案、110644 B 不变、现哈希 A0D0C269… 与红队报告 reproduction_package 钉值一致）、0 未登记失配。本 gate 两件文本在 manifest 快照后落盘，已在 `expected_post_snapshot_landings` 登记，待下一次 CM 复走补登。

## 遗留问题

1. Owner 级确认全部 pending：桥升格、ODR-43/44 并入登记链、MC-A 裁决确认、V6/R3 候选评审。
2. RT2-F01/F02 两处文本级加注/改标待 Owner 签署前落笔（不改冻结文件内容语义）。
3. OI-R1-01 待上游 erratum 重签发；OI-R1-05 HIGH RFI 缺口待硬件 RFI 工单；OI-R1-03/04 待 Owner 裁决。
4. 下一次 CM 复走需把本目录两件 gate 文本补登进 manifest（V3 或 addendum）。
