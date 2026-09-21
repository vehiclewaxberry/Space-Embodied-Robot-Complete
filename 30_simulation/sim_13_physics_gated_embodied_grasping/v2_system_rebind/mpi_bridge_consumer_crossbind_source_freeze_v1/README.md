# MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_V1

## 裁决边界

本包只冻结 ODR-45 已确认的唯一 `physical → dynamics` 桥在未来 Unified-R2 / Sim13 consumer 中的不可绕过交叉绑定。最高状态只能是：

`PASS_MPI_BRIDGE_TO_SIM13_CROSSBIND_SOURCE_FREEZE_ONLY`

它不构成 current system binding，不提升父 Sim13 formal NC 的 `15/20`，不关闭 `NC18/NC19`，不实例化 `MECH_RL_SYSTEM_INTERFACE_V2`，不生成或修改 URDF/CAD/STEP/FCStd，不调用 Unified-R2 generator，也不执行动力学、碰撞、接触、抓取或训练。

本包不重复以下职责：

- `current_system_handoff_intake_v1`：当前系统交付 intake 与证据准入；该包仍为 `HOLD_INCOMPLETE`。
- `preexecution_binding_security_source_freeze_v1`：七类单项 receipt 的 strict JSON/HMAC 验证器、动作/上下文与时间边界。本包 source-pin 并直接复用其最终 verifier，但不把任何单项 receipt 称为“总体授权”。
- `mpi_phys_dyn_bridge/round1_bridge`：producer 侧桥推导、质量传播和 MPI Gate；本包只约束未来 consumer。
- contact / grasp / full-flex / flight / production release：全部不在本包授权范围。

## 冻结语义

矩阵约定为 row-major：

`p_parent = T_parent_child @ p_child`

唯一桥方向为：

`T_PHYSICAL_TO_DYNAMIC = inv(T_S_A0_dynamics) @ T_S_A0_physical`

即 `p_A0_dynamics = T_PHYSICAL_TO_DYNAMIC @ p_A0_physical`。反向桥不能替代它。`frame / mass / inertia / wrench / collision_geometry` 五个通道的**完整 lineage**均必须恰好包含一次同一桥。数值施桥位置则不同：`frame / wrench / collision_geometry` 在 consumer boundary 各施一次；`mass / inertia` 已在 `SYSTEM_MASS_PROPERTIES_BRIDGED_V1` upstream ledger 中施桥，consumer 只能 bind，数值施桥计数为 `0`，禁止二次施桥。skip、inverse、double lineage、平均、混用或选择性消费均 fail-closed。

桥的旋转、平移和矩阵均携带：单位、from/to frame、参考点、authority、status、source field 及 uncertainty。`mass_inertia_binding.bridge_transform_uncertainty.standard_uncertainty` 保持 `null/UNKNOWN`；各 member 的质量/惯量不确定度按 bridged ledger 原样保留，二者不得混为一个 generic `uncertainty`。历史差值 `0.3688895107529362 deg` 是确定性的 frame-consumption difference，不是随机不确定度。

`D_BUS_MATE_PHYSICAL` 与 `M_DYNAMICS_NONPHYSICAL` 即使数值变换相同也保持不同的不可变语义身份。物理载荷路径与 collision geometry 只能经 `D_BUS_MATE_PHYSICAL`；`M_DYNAMICS_NONPHYSICAL` 只用于非物理动力学报告参考。

## SYSTEM_BINDING_V3 signed composition fixture

当前不存在 production authenticated receipt，也不存在 production composite producer。状态明确为：

`NOT_IMPLEMENTED_NO_PRODUCER`

唯一可签发对象是 in-memory `SYNTHETIC_SIGNED_COMPOSITION_FIXTURE`。它消费七份 raw preexecution receipt bytes，并由 source-pinned 的最终 preexecution strict parser/HMAC verifier 逐份验证 kind、issuer/signature、action/context digest、UTC time 与 nonce；随后形成 canonical ordered receipt-set digest。fixture 的唯一决策为 `ABORT / SOURCE_FREEZE_SCOPE_LOCK`，无总体授权、无 release credit。

V3 envelope 一次性绑定：

- system URDF SHA；
- instantiated interface SHA；
- Unified-R2 frame-tree SHA；
- bridge 文件 SHA、独立 `bridge_semantic_digest` 与独立 `crossbind_record_digest`；
- bridged mass/inertia binding SHA；
- ODR-45 Owner authority SHA；
- intake Gate + terminal SHA；
- preexecution Gate + terminal SHA；
- 七份 preexec receipt 的 ordered SHA/nonce/status/time/evidence、`preexec_action_digest`、`preexec_context_digest` 与 receipt-set digest；
- exact 三字段 action；含 `episode_id/configuration_id/authority_epoch/target_class/mission_phase_id/reference_frame_id` 的 exact context；
- 显式 C01 configuration mapping、同一 target、trusted UTC time 与独立 V3 nonce。

V3 窗口必须 `<=300 s` 且完全包含于七份已验证 preexec receipt 的公共有效窗。成功完成全部验证后，独立 in-memory V3 replay store 原子消费 nonce；签名或语义失败消费 `0`。该 store 重启即丢失，绝不声称 production durable replay。旧 V2 单项 receipt、普通 dict 上的 `receipt_kind=AUTHENTICATED`、签名 production kind 均拒绝。

## 15 个 pinned source

每次 bundle load 中，每个源按 exact relative path、raw bytes、byte count 与 SHA-256 恰好读取一次并形成 immutable receipt：原 13 项工程/Gate/terminal 源，加最终 preexecution `receipts.py` 与 `strict_json.py` 两项 verifier 源。`each_source_read_once_per_bundle_load=true` 不声称跨命令或跨进程全局只读一次。任一字节漂移均拒绝。

## 完整 DAG 与 allowlist

证据链为：

`external/internal sources → manifest → pytest/negative-controls/validation/independent-audit → Gate → terminal`

包级 allowlist 是 exact file + exact directory 集合。影子 JSON、SDF、XACRO、URDF、STEP/FCStd/mesh、cache 或额外目录全部拒绝。只读 replay 比较运行前后完整 inventory 哈希，不写文件。

冻结 independent-audit evidence 是 Gate 写入前的 `79/79`；执行独审命令时再复核 Gate、terminal 与 allowlist，输出 `84/84`。两者阶段不同，不是计数漂移。

本轮首审 P1/P2 已由上述组合、strict/replay、terminal 与不确定度负控逐项关闭；重冻结 Gate/terminal 记录开放项 `P0/P1/P2 = 0/0/0`。这只表示本 source-freeze 包审计缺陷关闭，不改变父级 `15/20`、`NC18/NC19 HOLD` 或 production readiness。

## 复现命令

在本目录执行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest -q -p no:cacheprovider
python -B run_mpi_bridge_to_sim13_crossbind_negative_controls.py
python -B freeze_mpi_bridge_to_sim13_crossbind.py
python -B validate_mpi_bridge_to_sim13_crossbind_source_freeze.py
python -B independent_audit_mpi_bridge_to_sim13_crossbind.py
python -B verify_mpi_bridge_to_sim13_crossbind_read_only_replay.py
```

`freeze` 只写本包的 manifest/evidence/results。其余验证命令均为只读；不要在本包中放置任何未列入 allowlist 的临时文件。
