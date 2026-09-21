# 机械终局 Loop Engineering 进展裁决（更新至 2026-08-25）

## 0. 文档角色与总裁决

本文件是机械终局总师的阶段进展裁决与 Owner 审签入口，不替代任何机器 Gate，也不构成 Owner 授权记录。科学和工程状态仍以文中引用的现行 JSON/YAML/CSV 为准。

本轮总裁决：

`LOOP_ENGINEERING_B4G_REGISTERED_EXECUTION_INVALIDATED__R1_FAILURE_CLOSURE_CONTRACT_PASS__R2_NUMERICAL_PREFLIGHT_CONTRACT_PASS__R2_EXECUTION_TOOLING_SOURCE_FREEZE_PASS__R2_RAW_EVIDENCE_ADAPTER_SOURCE_FREEZE_PASS__R2_FULL_RAW_INTEGRITY_BACKEND_SOURCE_FREEZE_PASS__MECH_TI_01_RECONSTRUCTED_NAVIGATION_INTEGRITY_PASS__M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_PASS__PASS_ROUTE_C_OFFICIAL_SOURCE_REFRESH_V2_ONLY__CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_PASS_ACTUAL_INTAKE_HOLD__PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_PASS_ABORT_ONLY__MPI_BRIDGE_TO_SIM13_CROSSBIND_SOURCE_FREEZE_PASS_CURRENT_BINDING_HOLD__M4_TO_M7_REQUIREMENT_AUDIT_CURRENT_SYSTEM_HOLD__R2_NUMERICAL_EXECUTION_HOLD__TERMINAL_RELEASE_HOLD`

已完成二十四个合法增量：

1. WP2 质量属性回执的配置管理自哈希缺陷已用无自引用链重发并独立验证；质量、质心、惯量和科学结论未改动。
2. Sim13 V3 Phase-A 已形成合成 6R+2P 纯内存广义力动力学诊断；数值内核通过，但没有绑定 Unified R2 当前系统。
3. Solar R2 非模态 ROM 探索已正规化为决策支持证据；10D 候选只达到探索性薄裕度，不获得 Round4、组件、e15 或 Release 信用。
4. Unified R2 V2 预授权工具链已完成 fail-closed 加固；当前唯一裁决仍是 `DENY_NO_DIRECT_OWNER_SOURCE`，未产生授权、run id、runtime hash、URDF 或接口实例。
5. Sim13 V4 运行时守卫诊断已用单实例 nonce、唯一协调器、真实 V3 合成状态推进与四源哈希绑定 Sim10 前置 veto 闭环；其信用仅限合作式 Python API 诊断，正式 V2 仍为 15/20。
6. Sim13 V4A 已建立服务星 6R+2P 与 22 kg 目标的完整全浮动、无接触联合数值核，并通过 Euler–Lagrange 与错误 ODE 负控；没有当前系统或接触信用。
7. Sim13 V4B1 已在 V4A 上闭合合成无摩擦单点柔顺接触、作用反作用、P/H/E+D、双积分器收敛和独立审计；摩擦、双指、soft capture、锁定、真实 B601 参数和正式 NC19 均保持 HOLD。
8. Sim13 V4B2 已加入公共作用点正则化 Coulomb 摩擦，并用显式力矩移置消除侵入状态下 pad 点—球面点分离造成的虚假净力偶；物理摩擦识别、双指与锁定仍保持 HOLD。
9. Sim13 V4B3 已审计合成双分支双点瞬态候选，但两 hard-finger 接触的抓取映射仅 rank 5，不具备六维 force closure。
10. Sim13 V4B4 已完成合成 6-DOF 约束获取—传播—移除合同冻结；冻结包 final/terminal 哈希保持不变，合同 PASS 不代表求解器或释放已执行。
11. Sim13 V4B4E 已完成后冻结求解器、真实执行路径负控和递归签名；B3 主分支在 `0.08 s` 内没有释放，另立的 nontrigger 算法夹具只证明有限事件与释放后传播实现。
12. Sim13 V4B4F 已完成合成 P-only 开指/制动可达性 campaign 的合同预注册与独立审计；求解器尚未实现，A0/A1/A2 尚未执行。
13. Sim13 V4B4G 已消费冻结 B4F 合同并执行 144 槽注册 campaign，但因 3 个 `MIDPOINT_COARSE` 能量—功恒等式案例超限而整体失效；随后 B4G-R1 仅完成失效机理、G04 合同分歧、G12 阴性结果和下一轮预检边界的注册收口，不授予原 B4G 科学或 campaign PASS。
14. Sim13 V4B4G-R2 已冻结 78-case 三轨数值预检矩阵、统一数值判据、区组顺序、46 项未来负控和递归证据链；该增量仅获得 contract-only PASS，rehydrator、R2 execution source-freeze、数值预检与完整 campaign 均未实现、未执行或未授权。
15. Sim13 V4B4G-R2 执行兄弟包已实现 typed donor rehydrator、A0/60/18/78 全局治理、G04/G06/G12 source-only evaluator、授权前置阻断和 46 项源级变异负控，并获得 `PASS_PHASE_B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_ONLY`；97/97 测试及只读 replay 证明 31 个包文件前后逐字节不变，但 78-case 数值预检、真实 NPZ 绑定和完整 campaign 仍未执行或授权。
16. Sim13 V4B4G-R2 原始证据适配器已冻结 exact 56-array NPZ/sidecar 合同、78 行角色/顺序绑定、无缓存 donor 双重实测、数值载荷唯一性及 86 项源级负控，并获得 `PASS_R2_RAW_EVIDENCE_ADAPTER_SOURCE_FREEZE_ONLY`；55/55 测试和 34 文件只读 replay 通过，但只覆盖 stored-array partial post、G04/G06 与 G12 raw 子谓词，不产生轨迹、完整 raw integrity、NC19 或数值预检信用。
17. Sim13 V4B4G-R2 完整 raw-integrity 后端已在新 sibling 包中实现 G03/G05/G07/G08/G09/G10/G11/G16 独立重算，并接回哈希冻结的 G04/G06；acquisition 初态/snapshot、外部 `Q_ref`、Hermite 全根连续净空、raw event index、post 5 ms 与 compact parent trace 均 fail-closed 绑定。该包获得 `PASS_R2_FULL_RAW_INTEGRITY_BACKEND_SOURCE_FREEZE_ONLY`，18/18 测试、14/14 负控、12/12 validator、12/12 independent audit 与整包只读零差异 replay 通过；但所有通过值来自临时非物理技术夹具，`actual_raw_case_count=0`、`trajectory_count=0`，不构成 R2 数值预检或科学信用。
18. A4-B2 历史清单所指 `10_research/knowledge_base/spacecraft_mechanical_design/` 原目录在当前工作区与 Git 历史中均不存在；按其 10 个 exact bytes+SHA-256 对全工作区复扫仍为 0 命中。现已建立 `RECONSTRUCTED_NAVIGATION_ENTRY_NOT_HISTORICAL` 的 MECH-TI-01 新入口，获得 `PASS_MECH_TI_01_RECONSTRUCTED_NAVIGATION_INTEGRITY_ONLY`；25/25 独立验证与 12/12 负控通过，但不重建或冒充历史知识卡，也不改变 M7 HOLD、Unified R2 6/20、MPI 0/8、P01-P13 全 null/HOLD 或任何执行/发布权限。
19. Sim13 V2 已新增 M7→Sim13 机械证据准入 source-only 包，27 个源按单次字节快照绑定 path/bytes/SHA/schema，并把数字绑定、设计候选、诊断、Owner 输入、实测输入与缺失证据分成六态；21/21 pytest、47/47 源判据、16/16 负控、13/13 validator 与 13/13 独立审计通过。Gate 上限仅为 `PASS_M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_ONLY`，`system_urdf_available/current_system_bound/physical_contact_ready/dynamics_capture_entry_authorized/next_stage_authorized` 均保持 false。
20. Route-C 官方来源刷新 V2 已把 17 条制造商/机构一手资料收敛为 RFI-E/F/G 的 4/2/3 个筛选候选，并以 20/20 pytest、20/20 fail-closed 校验及三路独立只读复核封住单材料系数、允许扭转、绑扎间距、航空资格和产品几何等非等价迁移；P01–P13 仍为 13/13 null/HOLD、精确产品选择数为 0，`RFI-G08`、CAD、几何执行、动力学抓取入口、下一阶段和 Release 均保持 false/HOLD。
21. 当前系统 handoff intake 已把 15 个受控源、9 个证据域和 14 个物理量冻结为带单位、坐标系、参考点、不确定度、authority、status 与 source 的只读合同；source-freeze Gate PASS，但实际 intake 仍为 `HOLD_INCOMPLETE`，12 项系统/执行/发布标志全为 false。
22. Sim13 预执行绑定安全包已冻结 strict JSON、七回执 join、一次性 nonce、原子生成事务与 exact URDF/interface bytes 合同；97/97 测试、3/3 注册 source-only NC（各双重复现）、17/17 validation 与 16/16 独审通过，但正式父 Gate 仍为 15/20、promotion=0，NC18/NC19 HOLD，最大运行态仍为 ABORT-only。
23. MPI 物理安装域→动力学域消费者交叉绑定已完成 source-only 冻结并经根级与独立终验；`T_PHYSICAL_TO_DYNAMIC = inv(T_S_A0_dynamics) @ T_S_A0_physical` 的元素残差为 0，frame/wrench/collision 各施桥一次，mass/inertia 只绑定上游已变换账本、消费者数值施桥次数为 0。28/28 测试、67/67 负控、25/25 validator、84/84 独审和零写入 replay 全过，但生产组合器仍为 `NOT_IMPLEMENTED_NO_PRODUCER`，当前决定固定为 `ABORT / SOURCE_FREEZE_SCOPE_LOCK`。
24. M4-L01..L08 已按现行 M7/Unified R2 证据重新审计：历史 M4 只证明受限静态工作样机；M7 当前为 5 PASS、12 `PASS_WITH_DECLARED_OPEN_ITEM`、1 HOLD，统一 R2、Route-C、完整柔性认证、制造/资格和当前 Sim13 绑定均未闭合。该项是只读工程裁决，不是新的机器 Gate，也不提升任何 Release 或下一阶段权限。

机械终局仍未放行：Checkpoint-A=`HOLD`，Checkpoint-B=`HOLD`，Checkpoint-C 未到达，`owner_accepted=false`、`next_stage_authorized=false`、`release_credit=false`。

## 1. 当前机械基线的真实状态

| 层级 | 现行状态 | 可用范围 | 不得扩张的边界 |
|---|---|---|---|
| M4 数字样机 | `PASS_SCOPED_WORKING_RELEASE`，根独立校核 34/34 | FreeCAD/STEP 静态构型、九构型数据合同、原型图纸和非采购 BOM | 非当前 Unified R2、非生产接触、非制造/资格/飞行放行 |
| M7 机械工程发布 | 5 PASS + 12 `PASS_WITH_DECLARED_OPEN_ITEM` + 1 HOLD；`next_stage_authorized=false` | 设计冻结总装、设计级质量/惯量、文档级图纸/BOM、design-indicative FEA | 唯一内部 HOLD 为 `HARNESS_AND_KEEPOUT`；更晚 Route-B 任务覆盖为 0/10 SAFE、0/8 released，不能包装为当前系统发布 |
| M7 MPI bridge | 9/9，五项底线差异为零 | 设计级质量/坐标/接口一致性 | 非 as-built 或硬件标定 |
| Full-Flex Checkpoint-A | `HOLD`，6/12 | 已冻结的组件、E22 与决策支持证据 | A07–A12 未闭合；E22 16/18，G11/G17 FAIL；e15 不继承 |
| Harness Checkpoint-B | `HOLD`；完整性 8/8，准入 2/8 | RFI-E/F/G 接收和物理注册表更新 | P01–P13 为 0/13 non-null、13/13 HOLD；Route-C CAD 禁止 |
| Route-C official source refresh V2 | `PASS_ROUTE_C_OFFICIAL_SOURCE_REFRESH_V2_ONLY` | 17 条一手来源；RFI-E/F/G 候选 4/2/3；20/20 校验与 20/20 负控 | 仅供 RFI/试验筛查；产品选择 0；P01–P13 全 null/HOLD；`RFI-G08`、CAD、动力学入口和下一阶段均未关闭/未授权 |
| Unified R2 source-only V2 | `PASS_SOURCE_STATIC_ONLY`，24/24 | C01 固定太阳翼快照的源级树、质量和坐标合同 | `urdf_emitted=false`；无 Sim13 rebind、接触或生产动力学授权 |
| Sim13 V2 prebind | 25/25；15/20 负控 PASS | 源级、历史回归和 fail-closed 预绑定诊断 | 当前最大运行状态仍为 `ABORT_ONLY_WITH_SOURCE_ONLY_ANALYTIC_PREBIND_DIAGNOSTICS` |
| Sim13 V3 Phase-A | `PASS_DIAGNOSTIC_WITH_UNIFIED_R2_EXECUTION_BINDING_HOLD` | 合成 6R+2P 数值内核 | `DYN-G01` 及生产动力学、接触、Release 全部 HOLD |
| Unified R2 V2 预授权工具 | `PASS_PREAUTHORIZATION_READINESS_TOOLING_WITH_EXECUTION_DENIED` | 三项 Owner 意图、时间窗、哈希与 fail-closed 结构校验工具 | 当前 `DENY_NO_DIRECT_OWNER_SOURCE`；不是授权；未加载生成器或计算 runtime hash |
| Sim13 V4 runtime guard | 合成预绑定诊断 25/25；正式 V2 不变 15/20 | nonce、唯一协调器、V3 状态推进、Sim10 前置物理 veto 的诊断逻辑 | NC15/16/18/19/20 仍 HOLD；非跨进程/重启保证，非恶意进程内安全，非生产守卫 |
| Sim13 V4A full-floating | `PASS_PHASE_A_SYNTHETIC_FULL_FLOATING_KERNEL_WITH_CONTACT_AND_CURRENT_SYSTEM_HOLD` | 服务星 14 速度自由度 + 独立目标 6DOF 的无接触联合核 | 无接触、无当前系统绑定、无生产/Release 信用 |
| Sim13 V4B1 contact | `PASS_PHASE_B1_SYNTHETIC_FRICTIONLESS_SINGLE_CONTACT_WITH_FRICTION_LOCK_AND_CURRENT_SYSTEM_HOLD` | 合成球—link7 pad 的无摩擦单点柔顺接触诊断 | 无摩擦、双指、soft capture、锁定、抓取成功、真实参数或正式 NC19 信用 |
| Sim13 V4B2 friction | `PASS_PHASE_B2_SYNTHETIC_REGULARIZED_FRICTION_SINGLE_CONTACT_WITH_PHYSICAL_FRICTION_DUAL_CONTACT_LOCK_AND_CURRENT_SYSTEM_HOLD` | 合成正则化摩擦、公共作用点力矩移置与独立耗散分账 | `μ=0.25`、`v_eps=0.005 m/s` 均为合成值；无物理摩擦识别、双指、锁定、当前系统或正式 NC19 信用 |
| Sim13 V4B3 dual contact | `PASS...TRANSIENT_CANDIDATE_WITH_RANK5_NO_6D_CLOSURE...` | 合成双分支双点瞬态 soft-capture candidate 与完整账本 | 非 held capture；rank 5；无六维闭合、物理锁定/释放、当前系统或正式 NC19 信用 |
| Sim13 V4B4 contract | `PASS_PHASE_B4_CONTRACT_FREEZE_ONLY...` | 合成 6-DOF 获取—主动传播—移除合同和递归证据链 | solver/execution=false；不保证有限释放事件存在；冻结包禁止原位修改 |
| Sim13 V4B4E solver | `PASS_PHASE_B4E_SOLVER_AUDIT...ALGORITHM_ONLY_NONTRIGGER_HYBRID_BRANCH_VERIFIED...` | 合成获取投影、active reduced dynamics、nontrigger 有限移除与 42D 释放后传播 | B3 主支路时域耗尽且无移除；nontrigger 夹具无 B3/主线/物理/当前/正式信用 |
| Sim13 V4B4F contract | `PASS_PHASE_B4F_CONTRACT_FREEZE_AUDIT_ONLY...` | P-only 合成回撤力、带符号功、离散 A0/A1/A2 与 22 项未来负控预注册 | solver/campaign/reachability=false；不得外推最小力、实体行程或硬件能力 |
| Sim13 V4B4G execution | `SIM13_V4B4G_EXECUTION_INVALIDATED_V1.active=true` | 保留 144 个规范 JSON、120 个数值 NPZ 和失效诊断原始证据 | 注册 campaign 整体无效；无 final summary/Gate/terminal 信用；A2 的 24 个 JSON 仅为 `NOT_EVALUATED_NO_A1_SUCCESS` 元数据，非执行结果 |
| Sim13 V4B4G-R1 closure | `PASS_PHASE_B4G_R1_REGISTERED_FAILURE_CLOSURE_CONTRACT_ONLY` | 只读复算、失效机理与下一轮预检合同 | 非 B4G 科学/campaign PASS；新 campaign 未授权；最小合成力、物理时序/夹爪、当前系统、NC19、Owner/生产/下一阶段信用均为 false |
| Sim13 V4B4G-R2 preflight contract | `PASS_PHASE_B4G_R2_NUMERICAL_PREFLIGHT_CONTRACT_ONLY`；execution readiness=`HOLD_R2_PREFLIGHT_EXECUTION_NO_IMPLEMENTED_REHYDRATOR_OR_R2_SOURCE_FREEZE` | 78-case 三轨预检设计、统一 G04/G06/阶数/G12 判据、区组顺序与 46 项未来负控注册 | 该合同包自身非数值预检 PASS，且不含 solver/rehydrator/source-freeze/已执行负控；实现层进展见下行；无科学、物理、当前系统、NC19、Owner、生产、Release、下一阶段或完整 campaign 信用 |
| Sim13 V4B4G-R2 execution tooling | `PASS_PHASE_B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_ONLY`；readiness=`HOLD_R2_NUMERICAL_PREFLIGHT_EXECUTION_NO_DIRECT_OWNER_SOURCE_AND_NO_IMPLEMENTED_AUTHORIZED_PATH` | typed donor 纯内存重建、78-case 静态治理、源级 evaluator、97/97 测试、46/46 source-only mutation、只读 validator/audit/replay | `trajectory_count=0`；非数值预检或科学 PASS；G04/G06/G12 尚未对真实 NPZ 独立重算；无 Owner、current、NC19、生产、Release、下一阶段或完整 campaign 信用 |
| Sim13 V4B4G-R2 raw adapter | `PASS_R2_RAW_EVIDENCE_ADAPTER_SOURCE_FREEZE_ONLY` | exact 56-array SI schema、sidecar/NPZ path+bytes+SHA、78 行顺序/角色、A0/common/fresh/G12 source-only 原始证据入口、86/86 负控 | 本 adapter 自身仍只提供严格入口与 partial 子谓词；完整后端见下一行。`trajectory_count=0`，未消费真实 R2 轨迹，candidate/eligible、Owner、current、NC19、科学、生产、Release 与下一阶段信用均为 false/HOLD |
| Sim13 V4B4G-R2 full raw integrity backend | `PASS_R2_FULL_RAW_INTEGRITY_BACKEND_SOURCE_FREEZE_ONLY` | G03–G11/G16 全 Gate 源级独立重算、acquisition/snapshot、外部参考力、连续净空、raw event、post 与 compact parent trace 绑定；18/18 测试、14/14 负控 | 只在临时技术夹具上证明判别能力；`actual_raw_case_count=0`、`trajectory_count=0`、`full_raw_integrity_recomputed=false`；无直接 Owner source、无 vNext runner、无真实 R2 raw、无 current/NC19/科学/生产/Release/下一阶段信用 |
| MECH-TI-01 真值入口 | `PASS_MECH_TI_01_RECONSTRUCTED_NAVIGATION_INTEGRITY_ONLY` | 当前机械权威图、PRB/MPI/P01-P13 阻断矩阵、历史缺失审计、25/25 验证与 12/12 负控 | 身份为 `RECONSTRUCTED_NAVIGATION_ENTRY_NOT_HISTORICAL`；历史 10 原件 0 命中且未重建；M7/Unified R2/Route-C/Sim13/Handoff 状态均不升级 |
| M7→Sim13 evidence admission | `PASS_M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_ONLY` | 27 源单次快照、六态权威分类、19/18/16/3/8 拓扑与质量反双计数、D/M 语义、速度/碰撞/轨迹非等价判据 | 不生成系统 URDF 或接口实例；current/contact/dynamics-entry/next 均 false；无 CAD/STEP/mesh/FEA/轨迹或物理参数信用 |
| Current-system handoff intake | source-freeze=`PASS_SOURCE_FREEZE_ONLY`；actual intake=`HOLD_INCOMPLETE` | 15 个源、9 个域、14 个物理量、exact 30-file allowlist 与完整 DAG | system URDF/interface/current/contact/dynamics/next/release 均 false；只冻结输入，不补写缺失实物证据 |
| Preexecution binding security | `PASS_SOURCE_FREEZE_ONLY__PRODUCTION_BINDING_HOLD` | strict JSON、七回执 join、in-memory nonce/replay、原子事务与 ABORT-only 接口合同 | 正式父 Gate 15/20、promotion 0；NC18/NC19 HOLD；无生产 key、trusted clock、durable replay、真实 URDF/interface 或 Owner 执行源 |
| MPI→Sim13 consumer crossbind | `PASS_MPI_BRIDGE_TO_SIM13_CROSSBIND_SOURCE_FREEZE_ONLY__CURRENT_BINDING_HOLD` | 15 源 exact pin；物理→动力学桥、五通道 lineage、D/M 分离、mass/inertia bind-only；28/28 测试、67/67 负控、84/84 独审 | production producer=`NOT_IMPLEMENTED_NO_PRODUCER`；fixture 固定 ABORT；正式 15/20、promotion 0，NC18/NC19 HOLD，10 项授权/就绪标志全 false |
| MECH→Embodied handoff | 11/12 | 已闭合的接口候选项 | G12 线束额定运行包络 FAIL；当前 Sim13 生产绑定失效 |
| Terminal Checkpoint-C | 未到达 | 无 | 未生成 terminal release candidate |

M7 R2 设计质量账本中的当前配置质量为：C01–C07 `31.022864807342987 kg`，C08（+22 kg 目标）`53.022864807342984 kg`，C09（+150 kg 目标）`181.02286480734298 kg`。这些是设计模型值，不是 as-built、采购、制造或飞行质量放行。

主要状态入口：

- `20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack/TERMINAL_DECISION_PACK_GATE_V1.json`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/R2_FULL_FLEX_GATE_V1.json`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/checkpoint_b/ROUTE_C_CHECKPOINT_B_GATE_V1.json`

## 2. 本轮已闭合的二十四个增量

### 2.1 WP2 CM-only 自哈希修复

目录：`20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/cm_reissue_v2/`

- 裁决：`PASS_CM_INTEGRITY_REISSUE_ONLY`。
- 独立只读验证：26/26 PASS。
- 根因已精确复现：旧构建器先输出空 `hashes` 回执并计算 `9C858FD5...E6491`，随后写入该摘要改变了回执字节；旧回执实际摘要为 `5CD4EAF4...D368`。
- R2 质量账本未改动，SHA-256 仍为 `3FD2557318E98748A37927977FA2925C18803668FE16391D824C184F646486BB`。
- 新回执、Gate、manifest 采用显式自排除链；不继承科学 Gate，不授予 Owner、下一阶段或 Release 权限。

### 2.2 Sim13 V3 合成动力学诊断

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v3_in_memory_dynamics_diagnostic/`

- 精确测试 17/17 PASS；主机器检查 18/18 PASS。
- 独立审计未导入主约化动力学模块，在三个状态上重算显式 Schur、逐坐标五点差分、三重 Christoffel、偏置、加速度及线/角动量，结果 PASS。
- R/P 单位分别冻结为 rad/rad·s⁻¹/N·m 与 m/m·s⁻¹/N；线动量 N·s 与角动量 N·m·s 分账，不构造异量纲范数。
- 目录中 `.urdf=0`、`.pyc=0`、测试缓存=0；没有调用 Unified R2 私有构造器或生成器。
- Gate SHA-256：`A657D015BA5ECFB2D79F5FB305191F981EBB74281F7341617090EEAC218E603F`。
- 该 PASS 只证明通用数值诊断，不证明当前机械系统、硬件执行器独立性、接触捕获或生产动力学。

### 2.3 Solar R2 非模态 ROM 决策支持

目录：`20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/decision_support/nonmodal_rom_exploration_v1/`

| 已检验候选 | 双翼、五窗、六指标最坏相对误差 | 1% 判据 | 裁决 |
|---|---:|---|---|
| 最佳已检验 5D 加权 POD | 4.001049% | FAIL | 不能支持现行 3–5 模态全窗合同 |
| 3B+6T POD（9D） | 1.375734% | FAIL | 负控有效 |
| 3B+7T POD（10D） | 0.966518% | 探索性低于阈值 | 薄裕度、方法和维数看过结果后选定，非盲验证 |
| 10D，5 ms post-contact 扭转峰密采 | 0.948126% | 探索性低于阈值 | 只加密控制峰，不增加 Gate 信用 |

主结果、独立复算、完整性 Gate 与无环 manifest 的 SHA-256 分别为：

- `0319D2C5AA35B3A5C6CA7A4D8717DEDACB2758EFE4FF80530D39497345D36AC4`
- `CEC3C021A2F81BF1C0E7BD80665BA96005CA6A0AD7E22C1099FB9B9571E5098D`
- `30ED9CB56CCB9402F4AA074101672F25769F1EFDFE958F03B0A5B7EAA42EB47F`
- `3FF5D2C32F75970DB3273C0005A929BB4B77BA5019A9F9E944EE62BE90417776`

证据等级严格为 `EXPLORATORY_DECISION_SUPPORT_ONLY`。不能据此声称任意 Grassmann 5D 子空间全局不可能，也不能把 10D 直接变成 Round4 或 M7 Release 候选。

### 2.4 Unified R2 V2 预授权准备工具

工具目录：`70_tools/preauthorization_readiness/unified_r2_v2/`  
证据目录：`40_evidence/artifacts/authorization_readiness/unified_r2_v2/`

- pytest 147/147、主验证 52/52、独立审计 39/39 PASS。
- 当前状态精确为 `DENY_NO_DIRECT_OWNER_SOURCE`；`execution_authorized=false`、`owner_accepted=false`、`target_authorization_written=false`、`next_stage_authorized=false`、`release_credit=false`。
- 生成器从未被加载、导入、编译或执行；runtime hash 有意不计算；未创建 run/override id，受保护的授权目标、URDF、接口实例与消费锁均保持不存在。
- Gate：`PASS_PREAUTHORIZATION_READINESS_TOOLING_WITH_EXECUTION_DENIED`。
- Gate SHA-256：`7B8EE30EDD4E845DD8AEE817FCA17DC30160C2DA792E967F10B054FC0C6FF0D1`；无环 manifest SHA-256：`20BD53171719717C4E7E003BFAA09798F304609AFB268A79BAA7DC4298CE2634`。

该 PASS 只说明未来收到直接 Owner 文本后，工具具备 fail-closed 审查能力；它没有替 Owner 作出 ODR-GPT-07、ODR-GPT-08 或 C01 决定，也没有授予 Unified R2 执行权限。

### 2.5 Sim13 V4 合成预绑定运行时守卫诊断

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_runtime_guard_diagnostic/`

- pytest 40/40、主验证 25/25、独立审计 20/20 PASS。
- NC15 信用仅覆盖单个 canonical module instance 生命周期内的线程安全 nonce；不覆盖 reload、重复模块实例、跨进程或重启持久化。
- NC16 只覆盖合作式 Python API 下的唯一协调器与一次性 opaque invocation；恶意 monkeypatch 或 closure introspection 不在范围内。
- NC18 调用公开 V3 合成动力学推进真实状态；NC20 在后端能力检查之前，以四个冻结 Sim10 来源和哈希重算 150 kg@3°/s 物理 veto，漂移/畸形输入时后端调用数为零且状态不变。
- 技术裁决：`PASS_SYNTHETIC_PREBIND_RUNTIME_GUARD_DIAGNOSTIC_ONLY__CURRENT_V2_FORMAL_NC_REMAINS_15_OF_20__NC19_HOLD__NO_PRODUCTION_OR_RELEASE_CREDIT`。
- Gate SHA-256：`104D6D25D1C4F05B5447639D1D1CCBE464E622241EC23098E14FF44003D885E0`。

这不关闭正式 NC15/16/18/19/20，也不构成当前系统、生产守卫、接触抓取或 Release PASS。

### 2.6 Sim13 V4A 全浮动联合数值核

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/`

- pytest 20/20、主验证 21/21、独立审计 12/12 PASS。
- 核心状态为完整全浮动 6R+2P 服务星与独立目标 6DOF；不沿用 V3 的零服务星动量约化假设，为内部接触力交换预留了物理正确的系统层状态。
- 六个冻结 Euler–Lagrange 状态、三档差分步长的最坏 R 残差为 `6.893479689851212e-8 N·m`，最坏 P 残差为 `1.990789007776106e-8 N`。
- 实际错误 ODE 两步推进虽仅形成 `8.14279e-14` 的末态差异，旧 P/H/E 守恒残差仍可自收敛，但 Euler–Lagrange 检查能明确拒绝，证明守恒检查不能替代方程一致性。
- Gate：`PASS_PHASE_A_SYNTHETIC_FULL_FLOATING_KERNEL_WITH_CONTACT_AND_CURRENT_SYSTEM_HOLD`，SHA-256 `82ECF267AA5F0DF0B79610AB4FBFD4DB4AE564EDE530A7F69AB579D1E15F7A40`。

### 2.7 Sim13 V4B1 合成无摩擦单点接触

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b1_frictionless_single_contact/`

- pytest 27/27、主验证 25/25、独立审计 17/17 PASS；证据顺序为 pre-audit→independent audit→final Gate 的严格无环链。
- 联合状态在同一 RHS 与积分子步中推进，服务星使用 `M(q)ν̇+h=J_pad^T F`，目标承受同一点反力；R/P 单位、线冲量与角冲量严格分账。
- 名义序列唯一为 `SEPARATED→APPROACH→SINGLE_CONTACT→SEPARATING_AFTER_CONTACT`；没有 `DUAL_CONTACT`、`SOFT_CAPTURE`、`LOCKED` 或 `GRASP_SUCCESS`。
- 参考事件：首次接触 `0.009999948020113437 s`，接触后分离 `0.03271921494918329 s`，峰值法向力 `4.199179682699102 N`，最大侵入 `0.000514319865428034 m`。
- 总线动量最大漂移 `3.614289112403416e-13 N·s`，关于同一惯性原点的总角动量最大漂移 `7.921802133864943e-13 N·m·s`，`T+U+D` 最大漂移 `3.2716002254518095e-8 J`。
- RK4 与独立中点法的步长减半判据逐物理量要求“误差严格下降，或粗细两级均低于该量原生单位的显式绝对下限”；本次证据中只有四元数测地误差实际调用了 `5e-8 rad` 的双精度分辨率下限，其他分量均严格下降，动量、角动量、能量和事件阈值未放宽。
- 最终 Gate：`PASS_PHASE_B1_SYNTHETIC_FRICTIONLESS_SINGLE_CONTACT_WITH_FRICTION_LOCK_AND_CURRENT_SYSTEM_HOLD`，SHA-256 `91F11FA541A336D9C3E073104CB15C215BCAEC4417090D9FA743D7D089604BE4`。

球半径、刚度、阻尼、初始间隙和速度全部为合成暂定值。该 PASS 不能关闭正式 NC19，也不能声称 B601 双指摩擦抓取、soft capture、锁定或当前系统接触成功。

### 2.8 Sim13 V4B2 合成正则化摩擦单点接触

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b2_regularized_friction_single_contact/`

- pytest 23/23、主验证 26/26、独立审计 19/19 PASS；审计器不导入 B2 求解器或验证器，而从哈希绑定原始时程重建几何、速度、摩擦力、广义力、P/H/E+D、事件与收敛。
- 正则化摩擦律为 `F_t=-μF_n v_t/sqrt(||v_t||²+v_eps²)`，因此机器检查 `||F_t||≤μF_n`、`F_t·v_t≤0`；本轮 `μ=0.25`、`v_eps=0.005 m/s` 均为 synthetic provisional。
- 侵入时 link7 pad 与目标球面公共点不重合；服务星广义力采用 `J_vᵀF+J_ωᵀ[(p_c-p_pad)×F]`，两物体在同一 `p_c` 形成等大反向内力，避免切向力产生虚假净角冲量。
- 参考事件：首次接触 `0.009999948020113437 s`，接触后分离 `0.03379763743349216 s`，峰值法向力 `4.333895285662195 N`，最大侵入 `0.0005317853042011017 m`。
- 峰值切向力 `0.979348733167129 N`，最终摩擦耗散 `0.0001689093662525985 J`；总线动量漂移 `4.3722728556932536e-13 N·s`，总角动量漂移 `9.529487788305724e-13 N·m·s`，`T+U+D_n+D_t` 漂移 `3.337195265962212e-8 J`。
- RK4/独立中点法参考事件差：首次接触 `2.84e-14 s`、分离 `1.22023e-6 s`、峰值法向力 `0.00452333 N`、最大侵入 `5.54289e-7 m`。
- 最终 Gate SHA-256：`475FE497F8C302AB163A399362A20D322A4753DA557C0116015D21D0E17FD2DE`；terminal self-excluded manifest SHA-256：`39495A00C9F832387E617FA5D84B960859F51D15CF7A53C702E5EB4B93DCF5C8`。

该 PASS 不代表真实 B601 材料对、真空/温度/寿命摩擦，亦不代表双指几何约束、soft capture、锁定、释放、抓取成功或当前系统接触。正式 Sim13 V2 继续保持 15/20，NC19 未关闭。

### 2.9 Sim13 V4B3 合成双分支双点瞬态捕获候选

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b3_branched_dual_contact_soft_capture/`

- pytest 44/44、主验证 33/33、独立审计 31/31 PASS；独立审计器不导入 B3 求解器或验证器，而是解析冻结 URDF、局部重建 6R 臂、固定 palm、两个 sibling-P 分支、左右接触、P/H/E/冲量账本、状态判据与抓取映射。
- 只读继承现有 B601 URDF 的拓扑事实：两个 prismatic finger 同属 `gripper_link` 子树，正运动在 palm 中分别沿 `-Y/+Y`；URDF 的 `velocity=15 m/s` 仍无物理速度/时序权威，真实左右接触框架继续为 null/HOLD。
- 联合模型为 free base + 6R arm + fixed palm + two independent P fingers，共 14 个广义速度。名义序列为 `PREGRASP_SEPARATED→BILATERAL_APPROACH→RIGHT_ONLY_CONTACT→DUAL_CONTACT→SOFT_CAPTURE_TRANSIENT_CANDIDATE→BILATERAL_RELEASE`；释放后再接触、初始未分离、P 行程越界和过侵入均 fail-closed。
- 左右接触均为 hard-finger frictional point contact，每点只传递三维力、不传递独立接触力矩。合成参数为 `R=0.04 m`、`k=8000 N/m`、`c=12 N·s/m`、`μ=0.25`、`v_eps=0.005 m/s`、初始闭合速度 `0.01 m/s`，均非物理识别值。
- 参考轨迹中：右/左首次接触分别为 `0.04989516372592913 s` / `0.050108296315394873 s`，瞬态候选首次出现于 `0.051250000000000004 s`，双侧释放转移为 `0.05675 s`；7 个 qualifying 样本同时通过连续 dwell、双侧力、法/切向速度、P 指未张开及完整在线账本。
- 左/右峰值法向力分别为 `0.14823003406516239 N` / `0.153697951892094 N`，最大侵入分别为 `1.4720119461825165e-5 m` / `1.5260517793692918e-5 m`。
- 总线动量最大漂移 `2.894236567356556e-13 N·s`，总角动量最大漂移 `5.772611802983431e-13 N·m·s`，`T+U_left+U_right+D_n,left+D_t,left+D_n,right+D_t,right` 最大漂移 `2.882133994137892e-9 J`；执行器模型不存在且 `actuator_work=0`。
- 对全部 qualifying 样本，以 `L_ref=0.5‖p_R-p_L‖` 归一化力矩行后，双 hard-finger 点接触抓取映射均为 rank 5；沿接触连线的纯力矩不可生成。因此机器裁决保持 `full_6d_wrench_span=false`、`full_6d_force_closure=false`，双点接触不得包装成六维保持抓取。
- 最终 Gate：`PASS_PHASE_B3_SYNTHETIC_BRANCHED_DUAL_HARD_FINGER_CONTACT_TRANSIENT_CANDIDATE_WITH_RANK5_NO_6D_CLOSURE_AND_ALL_PHYSICAL_CURRENT_LOCK_RELEASE_HOLDS`；SHA-256 `8D7674711CD27D563539AD1A94A7173707053B5B14A85DD187C1966F3B80A053`。terminal self-excluded manifest SHA-256：`444C64126A4F7B6CAFBB00BA50AFB953E037BCA3E6FCBD6A07177D3C27D20588`。

该 PASS 只说明合成双分支模型出现了受审计的瞬态候选，不说明 held capture、真实夹爪摩擦/压力/时序、锁定变换、抓取成功、消旋稳定、当前系统绑定、正式 NC19、生产、释放或下一阶段授权。正式 Sim13 V2 继续保持 15/20，NC15/16/18/19/20 均为 HOLD。

### 2.10 Sim13 V4B4 合成 6-DOF 约束获取—传播—移除合同冻结

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_synthetic_6d_constraint_acquisition_release/`

- 本轮只冻结合同，不实现或执行 B4 动力学求解器。pytest 精确 `62/62 passed`，且 skipped/xfailed/xpassed/deselected/errors 均为 0；validator `37/37`、独立审计 `22/22`、终端递归回验 `9/9` 全过。
- 源证据固定为 13 条 upstream + 16 条 local，共 29 条 exact path/role/bytes/SHA 记录；validator 在测试前后重拍快照，独审在签发前重验，签发后对 source→validation→evidence→pre-audit→receipt→final→terminal 做递归回读。任何写入或二次回验异常都会删除 PASS receipt/final/terminal 并非零退出。
- 唯一触发点仍是 B3 首个全谓词+全账本同时通过样本：索引 `205`、时刻 `0.051250000000000004 s`；原始 321 条记录中共 7 个 qualifying 样本，禁止后选时刻。
- 冻结快照变换为 `T_PALM_TARGET_SNAPSHOT_SYNTHETIC=inv(T_I_PALM) T_I_TARGET`，只表示触发时的合成相对位姿，不得别名为 `T_gripper_target_locked`，也不允许把 target 瞬移到名义位姿。
- 获取事件把 20D 独立速度状态投影到 14D 附着子空间：`z+=L eta+`、`J_c L=0`。主路为 `(L^T M L)eta+=L^T M z-`，独立路为直接带主元对称不定 KKT；获取路径禁用 inverse/pinv/lstsq。
- 异量纲秩阵只在审计坐标中用 `S_eta/S_z/D`尺度化；物理 KKT、冲量恢复和能量仍使用原生单位。`L_ref=0.03999999992105392 m`，B3 左/右接触弹性能为 `3.3837573393085704e-7 J` / `4.6759575924213813e-7 J`，切换时合计 `8.059714931729952e-7 J` 只能吸收一次。
- B3 双 hard-finger 抓取映射保持 rank 5。缺失通道标量为 `chi_missing=a·(ell-r_left×p)`，不能简化为 `a·ell`；新增第六约束只能归因于合成保持机构需求，不得回写成 B3 接触能力。
- 约束激活后 B3 接触核关闭，target 作为 palm 的固定刚体子体进入 reduced dynamics；只在双侧原始 gap 和 gap-rate 从最小 active dwell 后连续满足首个完整 clearance dwell 时移除。集合为空则 `DIAGNOSTIC_FAIL_CLOSED_NO_REMOVAL_EVENT`；移除映射速度连续、冲量为 0、理想约束储能为 0，本合同不保证移除路径存在。
- 最终合同 Gate：`PASS_PHASE_B4_CONTRACT_FREEZE_ONLY__SYNTHETIC_6DOF_CONSTRAINT_ACQUISITION_RELEASE_PREREGISTERED__IMPLEMENTATION_NOT_STARTED__ALL_PHYSICAL_CURRENT_LOCK_HELD_RELEASE_NC19_HOLDS`。final Gate SHA-256：`55441DFF42C92235B14DF9C810B013ADC2E59D5607D7697A5D85795149431D92`；terminal self-excluded manifest SHA-256：`09D26114D50358FD488BF51912C68FDB3993AB0035201B22478D7CD9A9B7B76E`。

该 PASS 仅授予“V4B4 合同已冻结并经审计”这一个布尔值。`b4_dynamics_solver_implemented=false`、`synthetic_constraint_executed=false`；物理接触/锁定/held capture/释放、当前系统绑定、正式 NC19、Owner/生产/下一阶段授权全部继续 false/HOLD。根据冻结治理，动力学求解器实现须通过一次独立 post-freeze 计划更新启动，不继承本 Gate 的 PASS。

### 2.11 Sim13 V4B4E 后冻结合成 6-DOF 约束求解器执行

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/`

- B4 冻结合同目录保持字节不变，递归回验仍为 `9/9 PASS`；B4E 另立兄弟执行包，并把 B4 final Gate、terminal、五份合同、B3 trace/model/kernel 与 full-floating primitives 逐字节绑定。
- 冻结 B4 合同没有 active 最大搜索时域。B4E 在实现前补充冻结 `t_end=0.08 s`（B3 已审计轨迹末端），分类为“有限数值搜索窗、非物理保持/释放时间”。时域耗尽只允许 `DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED`，不得伪装成无界 eligibility set 为空。
- 六条轨迹均由各自积分器独立定位首个 qualifying 触发：RK4 `1/0.5/0.25 ms`，midpoint `0.5/0.25/0.125 ms`。参考事件分别为 `0.051250000000000004 s` 与 `0.051125000000000004 s`，差 `0.000125 s < 0.00025 s`；没有强塞共享事件时刻。
- 主事件的尺度化秩为 `rank(L_hat)=14`、`rank(J_hat)=6`、`rank(G_bar)=5`。reduced SPD 与独立 pivoted symmetric KKT 最大原生分量差 `8.81e-15`；`W_bar` 最小特征值 `0.002630462777097634`、尺度化条件数 `2618.6890893443533`。
- 合成第六约束的目标 COM 冲量为 `p=[-0.02829537886642536, 0.016962265401890914, 0.014365187523206278] N·s`、`ell=[0.006543374067768591, 0.01703439003794772, -0.015292243190215096] N·m·s`。投影耗散 `0.0005268340970047839 J`；计入左右 B3 弹性能各一次后，切换耗散 `0.0005276400684979569 J`。
- active 段以 14D reduced dynamics 传播，目标作为 palm 的合成固定子体；B3 接触核精确关闭。主参考轨迹最大线/角动量漂移分别为 `4.4858999062017576e-13 N·s` / `8.803603430843038e-13 N·m·s`，机械能加既有耗散漂移 `2.5587171270657905e-15 J`；公式法与独立 fixed-child 质量矩阵最大差 `2.275957200481571e-14`。
- 主分支左/右 gap 从 `-9.197496044180409e-6 m` / `-1.0811981308277152e-5 m` 继续变为 `-0.00016088280688825868 m` / `-0.00019245215799178206 m`，gap-rate 仍为负。因此六条轨迹在冻结窗内均未达到双侧净空连续 dwell；removal-time 对拍为 `NOT_EVALUATED_NO_FINITE_EVENT`，`synthetic_removal_executed=false`。
- cubic-Hermite 全根分区事件器和“先展开 `z=L eta`、再逐原生速度分量复制、零冲量、零理想约束储能”的解除映射已由单独的 **algorithm-only nontrigger fixture** 验证。该夹具从哈希绑定的 B3 事件状态显式扰动：P 坐标 `-20 μm`、P 速度 `+20 mm/s`，并从扰动状态重算公共接触点和弹性能；B3 soft-capture 与全部主线账本资格均为 false，B3 耗散置零，禁止获得任何主分支触发信用。
- nontrigger 夹具通过真实 `propagate_active` 分支得到 off-grid 有限事件：`tau_c=0.05289636683828911 s`、`t_r=0.05389636683828911 s`、相对样本索引 `10.585467353156435`；事件后把完整服务星 29D 与目标 13D 状态独立自由飞行 `5 ms`。active 搜索 trace 只标记为 counterfactual attached search trace，执行的 hybrid 路径在移除时切换；这些结果不证明 B3 主轨迹、物理保持机构或实体释放。
- 全量验证为精确 `184/184 pytest`（nodeid SHA-256 `AEF1EA56A734E4C731DDAEC43F78DAC5965CA3ADADCA70A009522118B3DE3D90`）、validator `48/48`、不导入 B4E solver/validator/tests 的独立审计 `36/36`；22/22 负控均 unique/hit/killed，其中 20 项实际变异 raw artifact 或 executed path，NC21/NC22 分别逐一变异 8 个治理 false 字段与 7 个 null 物理字段。
- 最终 Gate：`PASS_PHASE_B4E_SOLVER_AUDIT__SYNTHETIC_ACQUISITION_ACTIVE_AND_ALGORITHM_ONLY_NONTRIGGER_HYBRID_BRANCH_VERIFIED__PRIMARY_BRANCH_HORIZON_EXHAUSTED_INCONCLUSIVE__NO_MAIN_REMOVAL__ALL_PHYSICAL_CURRENT_FORMAL_HOLDS`；SHA-256 `8F644E69F626793989488C8D8FF3803F9F1354C6D637E1E237044A55421C896E`。terminal self-excluded manifest SHA-256：`09047EF1B605BBE288545564EC1BF71D0184A330FAABDA11D8A1B123584D60A6`；独立审计回执 SHA-256：`A0F6B4B54CD06549CE51ECB48C719A50E062F0A141914210294C603196F67097`。
- 本包的 `memory_gate_applicable=false`、`memory_gate_passed=false`、`owner_override_used=false`：6 GiB 门不适用于该有界数值诊断，且本轮没有伪造 PASS 或调用 Owner Override。
- 终局只读审查独立复算 B4E 与递归 B4 共 97 条 path/bytes/SHA，`97/97` 一致且没有活动写进程。现行 schema 中 `synthetic_removal_executed=false` 的语义是“主/名义分支未移除”，而 nontrigger fixture 内部的算法分支已执行移除；因此对外引用必须成对写“算法分支已覆盖；B3 主轨迹未移除，release/physical/current/formal 均 HOLD”，禁止单独摘引 solver implemented=true。

工程含义：合成 6D 获取投影和主动约束动力学已经闭合，但“合成约束存在”不等于物理保持机构存在；当前无执行器模型的两 P 指在事件后继续闭合，故不会自行产生释放所需净空。下一数值循环若要研究释放可达性，必须另立合同并显式引入合成开指广义力/功或受控运动及其能量账本，不能改写 B4 的 `actuator_work=0`，更不能把占位命令升级成真实夹爪时序、保持力或释放能力。正式 Sim13 仍为 15/20，NC15/16/18/19/20 HOLD。

### 2.12 Sim13 V4B4F 合成夹指回撤可达性合同冻结

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4f_synthetic_jaw_retraction_reachability_contract/`

- 本目录只冻结和审计未来 B4F 数值试验合同，不实现 B4F 动力学求解器，也不执行 campaign。最终 `b4f_solver_implemented=false`、`b4f_campaign_executed=false`、`synthetic_reachability_passed=false`、`lowest_tested_reachable_alpha=null`。
- 广义力为 14D，只有零基索引 12、13 的两个 P 通道允许非零；opening sign 从获取状态的 gap Jacobian 冻结为 `[+1,+1]`，未来每次获取必须复核且保持不变。功率与功采用带符号账本 `P_act=Q_P,left qdot_P,left + Q_P,right qdot_P,right`、`W_act=∫P_act dt`，禁止在移除时重置或重复计入。
- A0 为 B4E 零输入精确重放；A1 为 `alpha=[0.5,1,2,4,8,16] × T_cmd=[5,10,20] ms` 的 18 例/块全因子离散网格；A2 只在 A1 观察到成功后执行左右镜像的半幅延迟和单侧失效。区组内顺序由冻结种子随机排列，并插入零输入 sentinel；时域固定 `0.08 s`，禁止事后延长。
- 合成几何域把左右 P 坐标均限制在闭区间 `[0,0.0715] m`；任意积分 stage、样本或事件越界均 fail-closed，禁止 clipping/extrapolation。该区间只是继承的 synthetic design-model domain，不是经硬件验证的实体行程。
- 即使未来离散 campaign 成功，也只能报告 `lowest_tested_reachable_alpha_in_registered_discrete_grid`；禁止把它包装成“最小所需力/功”，禁止跨层插值、逆阈值估计或提升为实体执行器规格。22 个 future solver negative controls 目前只完成预注册，没有声称执行或 PASS。
- 全量合同验证为精确 `107/107 pytest`（nodeid SHA-256 `973E6E52FAB4B91C8881558FD2203F95F1B7F87E389AB555737FCD82D5CB45C5`）、validator `34/34`、独立审计 `30/30`。独立审计从记录的 nodeid 列表自行复算摘要，并递归逐字节验证 B4E terminal→evidence→source DAG 和冻结 B4 terminal/final Gate。
- 最终 Gate：`PASS_PHASE_B4F_CONTRACT_FREEZE_AUDIT_ONLY__SYNTHETIC_P_ONLY_JAW_RETRACTION_REACHABILITY_CAMPAIGN_PREREGISTERED__SOLVER_NOT_IMPLEMENTED__CAMPAIGN_NOT_EXECUTED__ALL_PHYSICAL_CURRENT_FORMAL_OWNER_PRODUCTION_HOLDS`；SHA-256 `27FA21F23BD4FF7026BF25F3E7530868C4517FAC14643C55BCD23C6D4BDC0236`。terminal self-excluded manifest SHA-256：`753F443B5479A40FF8411D1139CEE473B243B2A76E73B000237E9E0CC4BCD42A`。
- 本包同样记录 `memory_gate_applicable=false`、`memory_gate_passed=false`、`owner_override_used=false`；没有 URDF、当前接口、实体参数、正式 NC19、Owner、生产或下一阶段信用。
- 只读终审未发现 P1/P2/P3 缺陷：B4E terminal 4 项、evidence 12 项、source 30 项递归记录全部字节/哈希一致，B4 冻结 final/terminal 根保持不变；B4F manifest 自排除且无环，无原子写临时文件。这里“无 URDF”严格限定为 B4F 包内未生成或修改 URDF，不扩张为全仓历史资产不存在。

工程含义：B4F 已把“为什么无执行器的 B4E 主分支不会自行释放”变成一个有界且可证伪的数值试验设计，但尚无任何可达结果。若继续执行，必须另立 post-freeze 工作授权和执行兄弟包，精确消费本合同，不能在本合同目录内追加求解器，也不能改动网格、时域或报告边界。

### 2.13 Sim13 V4B4G 注册执行失效与 R1 失效收口

B4G 执行目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4g_post_freeze_synthetic_jaw_retraction_execution/`

R1 收口目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4g_r1_registered_failure_closure_contract/`

- B4G 当前执行源冻结终端 SHA-256 为 `B22C4D5B4C0E15FF58484D252A2316E6B42458423079E2324D6455CC09EF3464`。冻结的 144 槽注册 campaign 已完整计算原始层：144 个规范 JSON、120 个数值 NPZ；24 个 A2 JSON 均为 `NOT_EVALUATED_NO_A1_SUCCESS` 元数据，没有 A2 数值执行。264 个原始文件的规范 inventory SHA-256 为 `916F395EFEEEE3C234C7D3F361BFFB6134D060577A05ADEE0166F8F19CD43DD5`。
- 注册 runner 精确在槽位 `82/84/88` fail-closed，均为 `MIDPOINT_COARSE__A1__ALPHA_16`，命令窗分别为 `10/5/20 ms`。其冻结发布的最大能量—功残差依次为 `2.416992812108443e-7 J`、`2.5554233711207186e-7 J`、`2.3470228460893694e-7 J`，分别为不变阈值 `1e-7 J` 的约 `2.42/2.56/2.35` 倍；因此不能豁免、抬阈值或删除 `alpha=16`。
- 失效记录 `SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json` 已激活，SHA-256 为 `2743FBD314CCA3EAA6FB5F4985DF8F65697E5BD968DE6DEB2AD58F0521FAB1D9`；prior-final-credit superseded 记录 SHA-256 为 `E8AB12C4B11706B3BE1EAF5AF44D79CE353754333E4B57059017046DD4E7E720`。原始诊断证据保留，campaign summary、final validation/audit/Gate/terminal 均未签发，`replacement_campaign_summary=null`。
- 独立复算把 G06 机理限定为冻结离散第一定律中的显式中点二阶截断误差：两次步长减半的经验阶为 `2.010994295233041–2.0803490936013893`。这是确定性数值离散缺陷诊断，不是物理缺失耗散项、随机代码故障或实体夹爪不确定度结论。
- G04 仍存在 runner/validator 合同分歧：冻结 runner 只验终点原生与隔点复合梯形误差，validator 另验“累计梯形功—增广 `W_act` 的全时域最大差 `≤1e-7 J`”。该附加检查不能静默删除，下一轮必须先版本化并统一两端同名规则；历史 `0.25 ms` 中点细步的最坏差为 `9.124409739671069e-8 J`，裕度仅 `8.755902603289308e-9 J`（约 `1.096×`），不足以跳过预检。
- G12 不是正结果：18 个 A1 水平中，9 个具有有限跨积分器配对、9 个为不适用；有限配对的科学谓词 `9/9=false`，带符号功超限倍数为 `10.9365–1001.858`，可选父水平数为 0，`selected_parent_level=null`。仅细化 G06 不能修复 G12，也不能触发 A2。
- R1 包没有启动新物理 campaign。pytest `14/14`、validator `20/20`、不导入 R1 validator 或原 B4G solver/validator 的独立审计 `16/16` 全过。失效收口 Gate SHA-256 为 `AE7E81F66CF6A5EC218CBB8E3FC4A1EC923A49E2CF0CAFC6681EEC449D855C68`；terminal self-excluded manifest SHA-256 为 `A1B2BD2FC051DC3CB853B7B081E0B56DB5776A48DEB7318E656F396ABAA516EC`，其全部引用项已再次按 path/bytes/SHA-256 独立回验一致。
- R1 登记的下一步已由下述 R2 包完成合同冻结：候选中点步长保持 `0.25/0.125/0.0625 ms`，lane-specific 获取收敛、common-initial-state 传播收敛、统一 G04 和 G12 事件/功判据均已预注册；这只消除了试验设计空白，不代表预检已经执行，更不授权完整 campaign。
- 正式 Sim13 V2 仍为 `15/20`，NC15/16/18/19/20 HOLD。R1 记录 `memory_gate_applicable=false`、`memory_gate_passed=false`、`owner_override_used=false`；本有界失效收口不适用 6 GiB 门，也没有伪造内存 PASS 或 Owner Override。

工程含义：本轮获得的是一个可复现、不可豁免的数值失效及其收口合同，而不是可达性成功。当前既没有最低测试可达 `alpha`，也没有最小合成力、物理开指时间、实体夹爪、当前系统或正式 NC19 结论；在版本化预检通过并获得后续授权前，不得重跑完整 B4G campaign。

### 2.14 Sim13 V4B4G-R2 三轨数值预检合同冻结

R2 合同目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4g_r2_numerical_preflight_contract/`

- 机器矩阵共 78 个唯一执行单元：60 个 `FRESH` 与 18 个 `COMMON_PROP`。60 个 fresh 案由 12 个 A0 PRE/POST bookend、18 个 `alpha=16` 三步长案和另外 30 个最细步长 reference 案无重叠组成；`FRESH_ACQ=6` 与 `G12 reference=36` 是这些执行单元上的分析视图，不是新增样本。5/10/20 ms 获取段的 technical repeat 只在精确排除 `/case_id`、`/event/run_id`、`/acquisition/run_id` 后校验同一性，不获得独立重复信用。
- 两种积分器均冻结 `0.25/0.125/0.0625 ms` 的 2:1 梯级；每条 fresh lane 由 A0 PRE/POST 包围，18 个 G12 两方法配对相邻，COMMON 按 `10/5/20 ms` 三个区组排列。NA 字段使用显式枚举而非 `null`。扩展矩阵 SHA-256 为 `D7B23B92DA46A6F9E96CF856914C7D5AECAD26240141C7F2B637A2AF119B7BEB`，blocked schedule SHA-256 为 `259EB3A99C0C0A45A6C80AEB979E2F15F3023804128517192C24D1B8A8F20EC7`。
- COMMON 轨绑定原 B4G 槽位 052 donor：raw SHA-256 `5DF0C19A71180E1BD91816235AAD50108613C2BC0F99F950018D786119CF9D4F`，acquisition payload SHA-256 `DA3E10D7D30DFD9BABFB71BF055D62A1BD06CF8DE3023E463A649FF92A952D15`，10 字段 common-state group SHA-256 `396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444`。未来每案必须由完整 typed roundtrip 后独立深拷贝，案前案后 donor payload/group 哈希不变；本合同冻结时 rehydrator 与 roundtrip 证据不存在，现已由 2.15 的执行工具源冻结补齐实现层证据。
- G04 已统一为同一 runner/validator 字段集和唯一布尔式，保留全时域累计梯形功、native terminal、every-second refinement、有限移除后 `W` 常值 carry 与 `Q=0`；G06 每案上限仍为 `1e-7 J`，没有抬阈值。直接误差阶数对 floor、零分母和回退分支采用全定义真值表；COMMON midpoint 收缩系数严格冻结为 `2^-1.8=0.2871745887492587`，不再使用与 `p_min=1.8` 不等价的 `0.30`。四元数距离也冻结了输入守卫、符号选择和稳定 `4*atan2` 测度。
- G12 只消费 36 个 fresh reference 案。其 aggregate PASS 仅表示 18 条记录完整且合法评估，科学谓词可真、假或注册的 NOT_APPLICABLE；只有 `eligible_count>=1` 才能支持另行审查含 A2 的 campaign，R2 合同自身始终不授权该 campaign。
- 本包 pytest `19/19`、validator `26/26`、独立 audit `24/24` 通过；另一次全新只读红队独立展开矩阵、复算 8 项 source binding、264-file raw inventory、donor/group、全部 21 个本地文件和哈希链，并对 250 组阶数分支及 10,000 组四元数进行反例/等价性对拍，未发现 P0/P1。validation SHA-256 为 `69A1DAE59F8550B8C016BAC028B9F90278DB5E4A5B4AAE47691D61156FE362AC`，evidence manifest 为 `CC651514BADF8E7FCDA559F81FC4089BF3C3B71A99B6BC16DEBACCAA5714B833`，audit 为 `18FB7DC253E73E8F424A593E2B518C943E00FA4729C0C6C10FBC4C9001492FFF`，Gate 为 `8DB747F8C57F898B25B15273C691A1007F4E452EB688865EEFAE2BA81E4A0298`，terminal 为 `286088014FD4B84263C17521E24224B8338B42214440DF8ED1593BE29A666C07`。
- 最终机器状态仅为 `PASS_PHASE_B4G_R2_NUMERICAL_PREFLIGHT_CONTRACT_ONLY`；执行状态明确为 `HOLD_R2_PREFLIGHT_EXECUTION_NO_IMPLEMENTED_REHYDRATOR_OR_R2_SOURCE_FREEZE`。46 项负控只是注册，`negative_controls_implemented=false`、`negative_controls_executed=false`；`r2_numerical_preflight_executed=false`、`r2_preflight_passed=false`、`full_campaign_authorized=false`。
- 正式 Sim13 V2 仍为 `15/20`，NC15/16/18/19/20 HOLD。R2 继续记录 `memory_gate_applicable=false`、`memory_gate_passed=false`、`memory_owner_override_used=false`；本有界合同冻结不适用 6 GiB 运行门，也没有伪造内存 PASS 或 Owner Override。

工程含义：R2 已把“下一次数值预检必须怎样做、怎样失败、怎样防止伪重复和实现分叉”冻结成可审计合同，但没有产生一条新物理轨迹。其 rehydrator、source-only evaluator、validator 与 46 项负控已由下述 2.15 执行兄弟包实现；future R2 NPZ 的 exact schema、不可变绑定与 raw 子谓词入口由 2.16 冻结；完整 G03/G05/G07/G08/G09/G10/G11/G16 源级重放能力又由 2.17 闭合。下一步仍须新的直接 Owner 授权源、独立 parent producer 与版本化一次性执行路径，之后才可运行 78-case 预检。只有该预检完成并审计后，才能决定是否授权新的完整 campaign。

### 2.15 Sim13 V4B4G-R2 执行工具源冻结与可重复验证

R2 执行工具目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4g_r2_post_freeze_numerical_preflight_execution/`

- 该兄弟包只实现并冻结 source-only 工具：严格 JSON、78-case 展开与 blocked schedule、slot 052 donor 的 typed 纯内存 rehydration/roundtrip、fresh/common 通道分离、A0 bookend、60 fresh/18 common/78 global 唯一性治理、G04/G06/G12 fail-closed evaluator 和无直接 Owner source 时的授权阻断。旧 `b4_solver`、`b4g_solver`、physics、trajectory 与 campaign 均未导入或调用，`trajectory_count=0`。
- 46 个登记项已全部改成调用生产校验钩子的 source-only mutation evidence：`registered=implemented=source_only_executed=killed=46`。这不等于 R2 运行时负控已执行；机器字段仍为 `r2_execution_negative_controls_executed=false`、`r2_numerical_preflight_executed=false`、`r2_preflight_passed=false`。
- A0 精确为 12 案/6 lane 的 PRE–POST 数值投影、Q14/W exact zero；fresh 精确 60 案，common 精确 18 案，全局 78 个 case id、证书和输出路径无未声明重叠。空历史、缺 raw、错误 provenance、重复 case/path、顺序漂移或 common/fresh 信用串用均不能获得对应数值 PASS。
- 主代理与独立终审均执行 source-only replay：pytest `97/97`、validator `13/13`、independent audit `14/14`。首次复核曾发现 standalone validator/audit 覆盖回执并使 Gate 引用 SHA 漂移；该 P0 已修复为 CLI 默认只读、只有 freeze 内部显式写回执。随后又关闭参数缩写写入、失败路径缺少 after snapshot、replay 未自动重验发布链三项硬化点。最终 replay 对整个包 31 个文件做前后快照，`added=[]`、`changed=[]`、`removed=[]`，并在运行前后均确认 Gate 四项 evidence、terminal→Gate 引用及 false/zero 状态语义有效；主代理外包 PowerShell 快照同样为 `31→31`、差异 0。
- 最终 source inventory 为 25 项，SHA-256 `2D42CD25ACFA0A5C1CE71F5AA6B529FBB9CD65C7E93457D565904511D68A3862`。manifest SHA-256 `81A574EFC0FA151E6762D30FC1224123BBA8B761EA3DA3EB1DC223BE52735102`；负控证据 `500F1D38AC23CC8F9B5EEDCF1DAC08D772770A5465E5E17F2F63705FD73C75AD`；validation `543A73323131FDA2D7DF617260D4F61AA1E50E1BA74863C3A2A6E9986831B004`；independent audit `47BBD4E6F78AEDBFF6882E770B1FB845A6E98660F54C57E2A014CBD095954C1F`；Gate `AC48841AB9C37CE04B466B51A51E91AEC3EDFA09271C66DDDD65A77B8EFA7308`；terminal `2CF4D4C5479485FFB579AC0E00FF59980665D73C4F9E23CA3FCCC45E58E6B634`。
- 最终机器裁决为 `PASS_PHASE_B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_ONLY`，执行准备仍为 `HOLD_R2_NUMERICAL_PREFLIGHT_EXECUTION_NO_DIRECT_OWNER_SOURCE_AND_NO_IMPLEMENTED_AUTHORIZED_PATH`，授权路径为 `NOT_VALIDATED_NO_DIRECT_OWNER_SOURCE`。`current`、科学 Gate、正式 NC15/16/18/19/20、Owner、生产、Release 与 `next_stage_authorized` 均保持 false。
- 本包冻结时仍存在的 raw P1 是：G04/G06 的 stage/功证据和 G12 clearance 尚无 future NPZ 的 `path/bytes/sha256`、exact arrays、outcome 与事件索引独立重建入口。该入口已由 2.16 的严格 raw adapter 收窄，完整 G03/G05/G07/G08/G09/G10/G11/G16 源级重放又由 2.17 闭合；但二者均未消费真实受权轨迹，禁止只解除外层 HOLD 后把技术夹具结果当成执行信用。

工程含义：执行工具源已具备可重复、不可自写污染的冻结基线，但没有获得执行权，也没有产生任何新抓取结果。2.16 已补上 future R2 NPZ 原始证据的严格接入层，2.17 又补上完整 raw-integrity 源级判据；下一合法动作仍不是直接启动完整 campaign，而是接收直接 Owner source、发行带独立 parent producer 的新受控执行版本，再运行并审计 78-case 数值预检。

### 2.16 Sim13 V4B4G-R2 原始证据适配器源码冻结

R2 raw adapter 目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4g_r2_raw_evidence_adapter_source_freeze/`

- 本包冻结 future R2 raw 的严格接入合同，不执行 physics、solver、trajectory 或 campaign。sidecar 与 NPZ 均要求项目根相对规范路径、单次读取、bytes 与 SHA-256 绑定；NPZ 只从已哈希字节以 `allow_pickle=false` 解包，exact 56 个数组采用 SI、固定 little-endian dtype/shape，暴露数组使用不可重新开启写权限的 bytes backing，sidecar 递归冻结。
- 78 行注册表必须按 blocked schedule 原始顺序逐位匹配 `schedule_index` 与角色；形成 6 个 A0 PRE/POST pair、2 个 fresh-acquisition triplet、6 个 common triplet、18 个 alpha16 raw 接口与 18 个 G12 pair。A0 用全部 56 数组的 identity-neutral 数值摘要约束 PRE/POST；G12 的 36 个 reference 还要求 36/36 数值载荷摘要唯一，改变 ZIP 包装或尾字节不能伪造独立 raw。
- COMMON 每案在读取 NPZ 前后分别重新读取、rehydrate 并哈希 slot 052 donor，不使用跨案成功缓存；三步长以 stride 1/2/4 投影到完整闭区间 `0.25 ms` 公共网格。finite removal 只允许末区间缩步；G06 使用实际末步长；no-event 必须保存 acquisition 后精确 `80 ms`；finite post 保存精确 `5 ms` 注册步长。
- 对抗复核先后关闭了可变 donor cache、跨案缓存绕过、同一数值 NPZ 重打包伪唯一、G12 一侧 finite 被 aggregate 接受、post subset 被误称完整 release pass、gap/rate 阈值和 saved/stage P 域混用等假阳性。最终 pytest `55/55`，source-only 负控 `86/86 killed`，validator `14/14`，stdlib independent audit `12/12`；只读 replay 的三个命令均返回 0，34 个包文件 `added=[]`、`changed=[]`、`removed=[]`，禁止持久化产物与缓存为 0。
- array-contract canonical document SHA-256 为 `1718C9858C5B7605F4F6C4EA8F8E20A2AB621869732E89FBB03E72D2CF0EAC04`，source inventory SHA-256 为 `3E6D698E140E9F78346679FE8641A66F9DE179A5FA4D48A9CE1F67B61020507B`；manifest、负控、validation、audit、Gate、terminal 文件 SHA-256 依次为 `C404526575EB3E344636D56F5E605F9ACF4912ED8D5988E9317EBFE14F39E63D`、`E8037CA37416F8D4DC5C3D4496AD188F96F8A22166BC40BD139FC2F22AE2751B`、`E352EAAB1702A4A1CEBE515112DE1EB90BCEAB8C9E969B3CE769E277829097CD`、`56EE6498F4F6BABE0C28D9B632F69352E66FB9A7EF537F6037FF9C7AEB3A5AFC`、`A67EE14F61E2DEB7AE6A03086E553528E23200D1AFF977691B0475F07FF86419`、`A01AC663F04E8728223C67FF313B23FEABE7A77C09995AB39762340BEFF4EB52`。
- 该 adapter 的最终机器状态仅为 `PASS_R2_RAW_EVIDENCE_ADAPTER_SOURCE_FREEZE_ONLY`。`trajectory_count=0`，`r2_numerical_preflight_executed=false`、`current_system_bound=false`、`formal_nc19_credit=false`、`science_credit=false`、`owner_authorized=false`、`production_ready=false`、`release_ready=false`、`next_stage_authorized=false`。adapter 自身只允许报告 stored-array partial post checks、G04/G06 raw 子谓词和 G12 raw-pair 子谓词；完整 G03/G05/G07/G08/G09/G10/G11/G16 后端由 2.17 的独立 sibling 包实现，但因真实 raw 为 0，`full_raw_integrity_recomputed=false`、candidate 与 eligible 仍为 false/HOLD。

工程含义：raw P1 在本增量时已从“没有可信原始入口”收窄为“已有严格入口，但缺完整冻结谓词重放与真实受权执行”；其谓词重放部分现由 2.17 消灭，剩余 P1 是直接 Owner source、独立 parent producer、版本化 vNext runner 与真实受权 raw 缺失。vNext runner 的 authorization consume、lazy import、output-root creation 和 run 四条成功路径仍无条件拒绝。本增量没有生成 CAD、STEP、FCStd 或 URDF，因此不触发几何快照或 CAD Viewer。

### 2.17 Sim13 V4B4G-R2 完整 raw-integrity 后端源码冻结

完整后端目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4g_r2_full_raw_integrity_backend_source_freeze/`

- 新 sibling 包不修改 2.16 冻结的 56-array adapter，也不导入 B3/B4/B4G solver。它逐次重验 raw adapter、R2/B4F 合同、参考力、solver-free geometry replay 及其五个上游源的 path/bytes/SHA；外部冻结绑定共 14 项，`Q_ref_per_finger=0.024542335689275555 N` 只来自外部参考力合同，禁止从本案命令峰值反推。
- G03/G05/G07/G08/G09/G10/G11/G16 均由 raw 独立重算，G04/G06 接回哈希冻结的 R2 actual-final-dt 实现。G09 使用两侧 gap/rate 的分段三次 Hermite 全实根区间划分和最早连续 `1 ms` dwell；sidecar outcome/removal time 仅作交叉核对。G10 取 raw removal index 而非猜测末行；G11 另绑定 acquisition payload/snapshot、精确 `5 ms` post 与独立文件形式的 compact parent mapping/terminal trace。G16 对 active 使用 attached snapshot 重建 target，对 post 使用独立 target state，禁止 clipping/extrapolation。
- 状态语义严格分层：临时技术夹具可得到 10 个 Gate 谓词全部为 true，但包级 `passed=false`；`full_raw_integrity_backend_implemented=true` 只表示源码能力闭合，实际 `full_raw_integrity_recomputed=false`、`actual_case_full_raw_integrity_recomputed=false`。任何 `gate_predicates`、`selector_case_integrity_pass`、child `post_release_passed`、`clearance.integrity_pass` 都不是判据输入。
- 最终 pytest `18/18`、负控 `14/14 killed`、validator `12/12`、independent audit `12/12`。只读 replay 再次执行验证、审计、负控和测试后，整包 `added=[]`、`changed=[]`、`removed=[]`；禁止持久化 NPZ/CSV/STEP/URDF/pyc 与缓存均为 0。
- source inventory 共 22 项，canonical SHA-256 为 `569E91FD76A50CC040F11C42B9AE2BD108B1EBF5F32AEA94BE55F78CA168AF02`。manifest、负控、validation、audit、Gate、terminal 文件 SHA-256 依次为 `D47811C657CE22F45B06331A8360DF8BB82C7E04E5EB5747B80112421A76F242`、`DDA6552EF6630BAB04EB260BC35C4D4C998005196A34D5A0EE44D31257AC4F2A`、`BD6DA405AA7BDC932AF8508C2A9158CB193322249FEE2C7FDBAC17A5420B91FC`、`B04315F7347C737AB235126EB618C50C8BE3BF59E70040AED518BB67E8E2A3B2`、`1EDADFE280BD788CF5D8A5A80C4FF79846FCEEC739C2504016586A08A349223E`、`A979214DA6DD5AB3754BE288A53A954CF56A2715206161473B9822E15ABE9503`。
- 最终机器状态仅为 `PASS_R2_FULL_RAW_INTEGRITY_BACKEND_SOURCE_FREEZE_ONLY`。`actual_raw_case_count=0`、`trajectory_count=0`，`r2_numerical_preflight_executed=false`、`current_system_bound=false`、`formal_nc19_credit=false`、`scientific_credit=false`、`owner_authorized=false`、`production_credit=false`、`release_authorized=false`、`next_stage_authorized=false`。

工程含义：R2 预检前最大的内部软件 P1 已在 source-only 层闭合，但执行 P1 仍未闭合。只有直接 Owner source、外部绑定的每案 context、独立 B4E parent producer 和版本化一次性 vNext runner 同时成立，才允许产生真实 R2 raw 并运行 78-case。该运行结果仍须重新通过本后端、G12 聚合、独立审计与新执行 Gate；本轮未生成 CAD、STEP、FCStd 或 URDF，因此不触发几何快照或 CAD Viewer。

### 2.18 MECH-TI-01 机械真值入口完整性闭环

目录：`10_research/knowledge_base/spacecraft_mechanical_design/`

- A4-B2 的 `v2_packet_hash_manifest.csv` 历史登记了该目录下 10 个原件；当前目录此前整体缺失，`git log --all` 无该路径记录，按 10 组 exact bytes+SHA-256 的全工作区复扫为 `NO_EXACT_HASH_MATCHES_FOUND`。这些信息只证明原件未找到，不能据此恢复原文。
- 新入口的统一身份为 `RECONSTRUCTED_NAVIGATION_ENTRY_NOT_HISTORICAL`。它只提供现行源注册、权威继承图及 PRB-01..20、MPI-01..08、P01..P13 的只读 fail-closed 投影；历史预期身份与当前恢复文件严格分离。
- 独立只读验证为 25/25，临时副本负控为 12/12 killed；再次执行 validator 与负控前后，12 个包文件的 path/bytes/SHA inventory 完全不变，缓存与 CAD/STEP/mesh/URDF/FEA/仿真产物均为 0。
- 包级 Gate 为 `PASS_MECH_TI_01_RECONSTRUCTED_NAVIGATION_INTEGRITY_ONLY`，Gate SHA-256 为 `5BC16D59BF819F53D9E2C9EA9ABC235261C618C06894D6E42D9563423BF6AF31`。该 PASS 仅关闭导航完整性，不恢复历史内容，不提升任何上游 Gate；当前仍为 M7 V5 HOLD、Unified R2 6/20、MPI 0/8、P01-P13 0/13 non-null、Checkpoint-B 2/8、Sim13 current binding invalid、Handoff V2 FAIL。

### 2.19 M7→Sim13 机械证据准入源码冻结

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/mechanical_evidence_admission_source_freeze_v1/`

- 新包不生成系统 URDF 或动力学核，而是把 27 个既有机械源按一次不可变字节读取绑定 path/bytes/SHA/schema，形成消费者侧证据账本。状态域固定为 `BOUND_DIGITAL / DESIGN_CANDIDATE / DIAGNOSTIC_ONLY / OWNER_REQUIRED / TEST_REQUIRED / ABSENT`；每个数值同时携带单位、坐标系、参考点、来源字段与 authority。
- 机器判据已明确分离：mesh 可加载不等于窄相碰撞权威；URDF `15 m/s` 不等于物理夹爪速度；候选/UNKNOWN 轨迹不等于发布轨迹；D/M 数值变换相同不等于语义身份相同；显式主结构与 residual bus 必须反双计数。
- 本地复核结果为 pytest 21/21、源证据 47/47、负控 16/16、validator 13/13、独立 audit 13/13；只读 replay 的 inventory 不变，缓存及禁止生成资产均为 0。
- Gate 为 `PASS_M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_ONLY`，Gate SHA-256 `D35F22099BF23A60A2948F14D42B02D70EFF1FF448622A037EA9BEB2A4CAE31A`，terminal SHA-256 `228FE375CEC464E888D8122F601F902A0CA8E86B8B7D59F3978520BE6DE19C48`。`system_urdf_available=false`、`current_system_bound=false`、`physical_contact_ready=false`、`dynamics_capture_entry_authorized=false`、`next_stage_authorized=false`，因此该 PASS 不能用于进入当前系统动力学抓取。

### 2.20 Route-C 官方来源与 RFI-E/F/G 筛查刷新 V2

目录：`20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/official_source_refresh_v2/`

- 本包登记 17 条官方制造商/机构来源，把 RFI-E/F/G 分别收敛为 4/2/3 个筛选候选；step.parts 相关精确检索为零命中，未下载或生成 STEP。公开资料只形成系列/件号、文档定位、单位、适用条件和缺口记录，不形成产品选择、采购释放或安装态物理参数。
- RFI-E 保留 igus E2 Micro、Tsubaki TKP13/PVDF 询证、KABELSCHLEPP 真空负面参照和 GORE 高柔扁平线缆架构比较；RFI-F 只冻结 TECASINT 8591×PFA 与 TECASINT 2391×XL-ETFE 两个 coupon 候选；RFI-G 只登记 TE THA-PDKG、Amphenol 75P/Omega。单材料摩擦系数、允许扭转角、绑扎间距、DO-160G 或材料级放气声明均不得迁移为 P08/P10/P13 或完整空间资格结论。
- P08 仅冻结安装态力/矩—位姿—速率—温度—真空—循环原始数据合同；P10 仅冻结精确衬材×精确外护套的真空摩擦、磨损、颗粒和电性能复验合同，且 `numeric_test_levels_authorized=false`。P01–P13 逐项保持 `registry_value=null`、`registry_status=HOLD`、`promotion=NONE`。
- 最终 pytest 20/20、机器校验 20/20；三路独立只读复核分别重放材料对系数注入、精确 YAML schema/来源双向映射和整包哈希清单，均 PASS。来源↔字段为 31↔31 精确集合，manifest 7/7，缓存、CAD、STEP、FCStd、URDF 均为 0。
- Input、validation、Gate、manifest 的 SHA-256 分别为 `ACB3E366B1E487AE66A86D99DA0BF227CD474FB6731286D92C76F930B328EF39`、`9B71C4DB78EB062E554857A40B7CAA4CFBAE719C031E13B4DE0F01A69F645FC3`、`04C1122AFC98AF066F2665E6CB1616113349C7287897037446E6BB1ED4CC7EF4`、`91256A27B408D3EC4AB493DD3055E8B9CF988641D2142AF422D4CA6CD11E907D`。
- 最终机器裁决仅为 `PASS_ROUTE_C_OFFICIAL_SOURCE_REFRESH_V2_ONLY`。精确产品选择数仍为 0，`RFI_G08_closed=false`、`ROUTE_C_CAD_AUTHORIZED=false`、`geometry_execution_authorized=false`、`dynamics_capture_entry_authorized=false`、`next_stage_authorized=false`、`release_credit=false`；必须在五类 Owner 输入、供应商正式回执、安装态 BOM/ICD、P08/P10 实测和 P05/P11/P13 受控几何全部闭合后，才可另行审查 C2-01 与 Route-C CAD 授权。

### 2.21 当前系统 handoff intake 源冻结

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/current_system_handoff_intake_v1/`

- 新包把 15 个现行机械源投影为 9 个交接域和 14 个带单位、坐标系、参考点、不确定度、authority、status、source field 的物理量；固定绑定摘要为 `D6CC48E6EEF2112AC9CA4E1C2F0D97D59D9FF2B64880DC44DF95109CD6A01F33`。它只读取并分类受控证据，不生成 CAD、STEP、mesh、FCStd、URDF 或动力学资产。
- 69/69 pytest、31/31 负控、21/21 validator、21/21 独审与 17/17 DAG 检查通过；exact allowlist 为 30 个文件，只读 replay 前后 inventory 不变。source manifest、intake evidence、negative controls 与 independent audit 的 SHA-256 分别为 `285D920B1D7D57D8BBA9D71D24708F6200813CAB56547EC956026E931D8B3C91`、`8E1419808AEDCD3332A3A6509DF69824EF763A05D993AF6D3920E7486D4E5FE0`、`618066F360148220159465CB758AC4B4BDA1BA88DCFB1E7E8F08D3709029A9E1`、`0469CC0069799086A3E724E529B99C6F96697AD5A56CE73B2C0B480A1C285FE7`。
- Gate 与 terminal 的 SHA-256 分别为 `23903C1AF1A6F7382A18E0685EF6A6010926B8C812163900BC3843B7A44BE5CE`、`543EC2247910E4E5B884EF27CC99F78ECE842B8DBF0AE55891656894ADCEBF10`。Gate ceiling 为 `PASS_SOURCE_FREEZE_ONLY`，而实际 intake 精确为 `HOLD_INCOMPLETE`；Route-C、e15、Full-Flex、线束任务覆盖和 current binding 的既有负结果全部原样保留，12 项系统/执行/发布标志全为 false。

### 2.22 Sim13 预执行绑定安全源冻结

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/preexecution_binding_security_source_freeze_v1/`

- 本包只冻结候选接口的 bounded strict JSON、规范摘要、七类回执 join、一次性 in-memory nonce、原子生成事务、exact URDF bytes/source-static broadphase 和 fail-closed ABORT 合同；没有生成真实 `MECH_RL_SYSTEM_INTERFACE_V2`、system URDF 或执行授权。JSON 上限固定为 262144 bytes、深度 64、复杂度 8192、节点 8193、单字符串 16384、总字符串 131072、数字字面量 256 字符；超限、非法 UTF-8、lone surrogate、非有限数和非 bytes 输入均不得消耗 nonce。
- 97/97 pytest、3/3 注册 source-only NC（NC15/NC16/NC20，各自双重复现）、17/17 validation、16/16 独审、9/9 committed-DAG validator 与 30/30 exact allowlist 通过；复核过程零写入。manifest、pytest、negative controls、validation、audit 的 SHA-256 分别为 `F1ED5740C7038D36E10CA86D9BA8A9465C86EC377E4C85A2C7AA2C2A8C24F8BD`、`FD32048A79E6AA0739E4B485FEAC0EA97EDC1FAC755BF04D85AA561E903537F0`、`77306EA7E2D382593B6CC56C735918014C0E701BA84CA3B12E664387EAED8FEE`、`7E1C9628698E82D3F5061372840D27DB7C795B8AA0ACDAB5DDDD715E0C8225CD`、`6DF6EDB9F10E1554B0286DE3EB11849C932B055E0622DA2D12FF4F93C6922B14`。
- Gate 与 terminal 的 SHA-256 分别为 `BBD13022F1462A59AC650EFC535C448C2004C113832E6C6ACD04C11F3EDE1F08`、`7E4AF02594E187942AAE67F7AD568B89E3BFD1BEA1369AAD6251F8C34EFD8D06`。source-only 可诊断覆盖为 18/20，但正式父 Gate 仍为 15/20、promotion=0；NC18 集成状态演化和 NC19 权威窄相接触继续 HOLD。无生产 key、trusted clock、durable replay、真实接口/URDF 或直接 Owner 执行源，因此 maximum runtime state 仍为 `ABORT_ONLY`。

### 2.23 MPI 物理→动力学消费者交叉绑定源冻结

目录：`30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/mpi_bridge_consumer_crossbind_source_freeze_v1/`

- 新包绑定 15 个外部源，包括 ODR45、物理—动力学 bridge、MPI/E21 Gate、bridged mass/inertia ledger、V6/R3 candidate、Unified R2 frame tree/source Gate，以及本轮 intake/preexec 的 Gate、terminal 和最终回执/strict-JSON verifier source。桥定义严格为 `T_PHYSICAL_TO_DYNAMIC = inv(T_S_A0_dynamics) @ T_S_A0_physical`，行主序语义为 `p_parent = T_parent_child @ p_child`；stored/recomputed 最大元素残差为 0，逆向矩阵分离量约为 `0.845236966386`。
- 五通道 lineage 均恰为一次，但数值应用位置按物理语义分离：frame=1、wrench=1、collision_geometry=1；mass=0、inertia=0，因为质量/惯量已在上游 bridged ledger 中施桥，消费者只能 bind-only。`bridge_semantic_digest=4BC7A99A1FAB4A5F2326FF35A3044E207295CC11BBAB6E337BD6814ADF1DEABD`，`crossbind_record_digest=F3D24534B611F412FDCBBFB9E57E1639D0D5A9E8E4E388508B85315F2DFC3132`，两者角色和规范字节明确分离；bridge-transform uncertainty 为 UNKNOWN，成员质量/惯量不确定度继续由上游账本承载。
- 首轮独立审查发现的 action/context 重绑、无签名伪认证、nonce replay、V2→V3 字段丢失、未定义总体回执、mass/inertia 二次施桥和 terminal 传递绑定等 P1/P2 已全部关闭。终版 28/28 pytest、67/67 负控、38/38 冻结 validation、79/79 pre-Gate 独审、25/25 post-freeze validator、84/84 完整独审与只读 replay 全过；独立机械符合性复核裁决 `ACCEPT`，P0/P1/P2=`0/0/0`。
- manifest、Gate、terminal 的 SHA-256 分别为 `006311DEDC73CF715279D9E60C047C082DF5FE2778FD64992001EA91BD49A6FF`、`3605DBB18F452297E5CCB195C57DA4C1983C348936B1A60AB334DEFF87E6BF14`、`7DC6501BD9C3DE77FFBACD9D224EC0A5846A6E0E742DFC39AC04435159C1D162`。机器状态仅为 `PASS_MPI_BRIDGE_TO_SIM13_CROSSBIND_SOURCE_FREEZE_ONLY`；production composer=`NOT_IMPLEMENTED_NO_PRODUCER`，合成 fixture 固定 `ABORT / SOURCE_FREEZE_SCOPE_LOCK`，正式父 Gate 15/20、promotion=0，NC18/NC19 HOLD，10 项授权/就绪标志全为 false。

### 2.24 M4-L01..L08 到现行 M7/Unified R2 的完成度复核

本项是只读工程裁决，不是新的机器 Gate：

- L01：M4 历史 FCStd/STEP 哈希分别为 `DEA1BC93AB182C0003B37B8B8D7D7BA2559AFB649769BDE59E52FAC0DB20D481`、`0FA64971512FAAA0B1D8EB026D4449DD513340BE8F047554D370ED359CD28020`；M7 R1 设计冻结总装有 71 个 FreeCAD object、7 个内部 Link、STEP 41 solids，但 B601 仍是 18-solid frame/axis witness，Solar R2 仍是独立候选，当前 Unified R2 总装未重建。
- L02/L03：九构型数据合同和设计级质量/质心/惯量已有；C01–C07=`31.022864807342987 kg`、C08=`53.022864807342984 kg`、C09=`181.02286480734298 kg`。没有九套现行物理碰撞配置，也不是 as-built、采购或飞行质量。
- L04/L05：6/6 材料族已有设计选材，但 flight allowable 数量为 0；公差链 12/14 分析闭合，TC13 相机指向和 TC14 HDRM 预紧仍开，Route-C 又引入新的实物公差域。
- L06/L07：D05–D08、BOM V3、装配/检验文件已达 document-level design release，明确禁止制造/采购使用；FEA1B 48/48 求解且反力平衡通过，但只属 `DESIGN_INDICATIVE`。Full-Flex Checkpoint-A 为 6/12 HOLD，E22 为 16/18 且 G11/G17 FAIL，e15 跨求解器差 `0.05637349419858036 > 0.05`，仍是 `REPEAT_ANCF_CERTIFICATION`。
- L08：历史 `MECH_RL_INTERFACE_V2` 与 M7 V4/V5-R2 可作候选证据，V6/R3 仍是 candidate；实际 `MECH_RL_SYSTEM_INTERFACE_V2`、统一 system URDF 与生产组合授权均不存在，旧 Sim13 production binding 已被新 M7 证据失效。Handoff V2 11/12，G12 线束额定运行包络仍 FAIL。
- 因此 M4 的 scoped PASS 不可外推为现行飞行级 CDR、制造发布或动力学抓取入口。真正不可由 Agent 内部补写的最小链是：Owner 受控的 Route-C P01–P13 与 RFI-E/F/G/线表/pinout/电气数据 ICD/安装 ICD/installed construction/mission life → Owner 选择精确产品与拓扑并单独授权 CAD → 重建 Unified R2 FCStd/STEP/system URDF/interface → 重跑全程线束、碰撞、mission coverage 与 Sim13 正式 rebind；并行还须完成 6D/7D ROM 决策、Full-Flex/e15 重认证和真实夹爪/目标接口试验数据绑定。
- 本轮没有调用 CAD 或 URDF generator，没有生成/修改 FCStd、STEP、URDF 或几何快照，因此 CAD Viewer 不适用。本轮工作全为 source-only 合同、验证与只读审计，6 GiB memory gate 不适用；没有使用 Owner Override，也不声明 `memory_gate_passed=true`。

## 3. Full-Flex 技术路线裁决建议

### 3.1 ODR-GPT-07

建议 Owner 选择：

`A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE`

原因：

- 现有固定 first-12 特征模态证据中，11D 是保留 B1/B2/B3 且覆盖 5/10/20/50/100 ms 五个登记离散窗的最低通过维数。
- 最坏相对误差为 `0.742603703% @ 5 ms`，比探索后选型 10D 的 `0.966518%` 有更合理的数值裕度。
- 10D 方法存在训练/选择泄漏且未做新载荷方向、LOW/HIGH 刚度角和离网接触窗盲验，当前不宜进入 Release 路径。

选择 A 只授权发布 P2 addendum 并构建、独立验证隔离 Round4 组件候选；不预授 E22、e15、Checkpoint-A 或 Release PASS。其他接触窗保持 UNKNOWN，禁止把五个离散点扩张成连续 `[5,100] ms` 有效域。

不可修改请求：`terminal_decision_pack/P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml`，SHA-256 `679DC5D2BA2B814F584379C28E47A9F487D03277F0F1EAA45DFB85D150367D25`。

### 3.2 ODR-GPT-08

建议 Owner 选择：

`A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR`

四条标准车道为：

1. `LEGACY_R1_SOLAR_SUBSYSTEM_RIGID_COUNTERFACTUAL_COMPARATOR`
2. `LEGACY_R1_SOLAR_SUBSYSTEM_FLEX_COUNTERFACTUAL_COMPARATOR`
3. `R2_RIGID_CURRENT`
4. `R2_SOLAR_FLEX_CURRENT`

只允许在同一设计族内作刚/柔因果比较；R1 与 R2 跨族只可报告 `DESIGN_FAMILY_DELTA__NO_CAUSAL_FLEX_ATTRIBUTION`。R2 flex 必须消费 ODR-GPT-07 后最终 Round4 ROM 及哈希，现行 ROM5 只可作为 preliminary。该路线最多闭合新版本 G17 的协议完整性，旧 E22-V1 的 G17 FAIL 必须保留。

不可修改请求：`terminal_decision_pack/LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml`，SHA-256 `5ED037AE057F7119678DECF890C9C0E64740C1443E5E9B9682FC09B8610046F6`。

### 3.3 获批后的顺序

1. 冻结两项独立 Owner 决定及请求哈希。
2. 发布 11D/wing 固定基底 P2 addendum。
3. 构建隔离 Round4，完成独立复算、确定性重放、负控和红队。
4. 在 Round4 PASS 后执行四车道、两场景共八个标准案例。
5. 新建 E22-V2/E23；旧 E22-V1 不原位修改。
6. 新模型闭合后重跑 e15；不得继承历史 PASS。
7. 仅在 Checkpoint-A 其余项全部闭合后重发 A01–A12 Gate。

## 4. Route-C 外部物理输入硬阻塞

这些值不得由 LLM、目录候选、Route-B 种子、零值或无来源工程猜测填充：

| ID | 受控字段 | 当前状态 | 需要的闭合来源 |
|---|---|---|---|
| P01 | `D_max_geometry_mm` | null/HOLD | 安装成品束外径、公差与有限导向/连接器包络 |
| P02 | `R_path_min_mm` | null/HOLD | 受控 Route-C 路径与 P06 动态弯曲限值 |
| P03 | `deltaL_mm` | null/HOLD | 受控路径、接口和余量推导 |
| P04 | `carrier_travel_mm` | null/HOLD | RFI-E：精确 carrier、行程和硬停 |
| P05 | `manufacturing_coordinates_mm` | null/HOLD | 安装 ICD 与真实连接器/夹具坐标 |
| P06 | `minimum_dynamic_bend_radius_mm` | null/HOLD | 精确构型供应商数据或弯扭试验 |
| P07 | `max_axial_extension_mm` | null/HOLD | 物理路径运动谱与任务寿命推导 |
| P08 | `torsional_compliance` | null/HOLD；单位未冻结 | 安装构型弯扭/温度试验和恢复矩曲线 |
| P09 | `linear_density_g_per_m` | null/HOLD | 精确安装子束实测或受控供应商数据 |
| P10 | `guide_friction_candidate` | null/HOLD；材料对未冻结 | RFI-F 与真空/温度摩擦磨损试验 |
| P11 | `guide_curvature` | null/HOLD | 受控 CAD 的有限导向体积与测量 |
| P12 | `carrier_size_mm` | null/HOLD | RFI-E：型号、尺寸、适配、质量与寿命 |
| P13 | `clamp_spacing_mm` | null/HOLD | RFI-G、安装 ICD 与夹具站位 |

还需外部闭合的五类 Owner 输入为：B601 electrical/data ICD、wire list/pinout、installed construction、installation ICD、mission-life allocation。现状为 RFI-E/F/G 已发放但供应商响应仍为 0；V2 官方公开资料筛查仅形成 17 条来源和 4/2/3 个候选，不能替代回执、产品选择或物理注册值。Mission Coverage 10 个必需状态 0 SAFE、8 条轨迹 0 released。冻结 Route-B 已被终局否证，不得重开或改名绕行。

## 5. Unified R2 单次研究候选与生产放行必须拆分

当前 Unified R2 V2 源级静态包已经通过 24/24，但执行授权记录不存在，目录内没有 `.urdf`，系统接口也未实例化。预授权工具虽已通过 147/147 + 52/52 + 39/39，其当前输出仍是 `DENY_NO_DIRECT_OWNER_SOURCE`，不能被解释为隐含授权。本轮没有生成 STEP/FCStd/URDF，因而没有可见几何变更；依 CAD 验证规则，本轮不产生快照，未来任何获批几何重发必须补四向总装和局部干涉快照。

若 Owner 希望先推进一个“不含 Route-C 的 C01 固定太阳翼研究候选”，必须另发一次性、最长两小时、哈希绑定的 `UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json`。它只能允许 `gen_urdf()` 返回内存 XML，不能授权落盘 URDF、Sim13 rebind、生产动力学或接触。

授权记录的五个 `authority_flags` 必须 exact true：

- `rebase_execution_authorized`
- `unified_r2_v2_generation_authorized`
- `system_urdf_generation_authorized`
- `route_c_exclusion_accepted_for_this_sim_candidate`
- `memory_admitted_for_this_execution`

并同时满足：

- top-level `owner_accepted=true`，但这不改变 Checkpoint-A/B/Terminal Gate 的全局 `owner_accepted=false`。
- `authority_flags.route_c_cad_authorized=false`。
- `selected_bus_mass_mode=EXPLICIT_STRUCTURE_PLUS_RESIDUAL`。
- 绑定 fresh `run_id`、`issued_utc`、`expires_utc`、`source_sha256`、`input_sha256`、`runtime_code_sha256`；有效窗不得超过 7200 s，run id 只消费一次。
- 运行时重新测量内存。若可用内存低于 6 GiB，必须使用同一 run id 和时间窗的 Owner Override，风险确认字符串精确为 `ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK`；此时记录 `memory_gate_status=OWNER_OVERRIDE_LOW_MEMORY`、`memory_gate_passed=false`，不得伪装为内存 Gate PASS。

即使完成该单次内存候选，以下状态仍必须保持 false/HOLD：工程规格完整性、几何执行、Route-C CAD、URDF 落盘、Sim13 基线修改与 rebind、生产动力学、物理接触、飞行资格、下一阶段和 Release credit。

## 6. Owner 最小审签文本

建议先只批准 Full-Flex 与比较器路线：

```text
我作为项目 Owner，作出以下两项独立决定：

1. ODR-GPT-07 选择 A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE，引用请求 SHA-256
   679DC5D2BA2B814F584379C28E47A9F487D03277F0F1EAA45DFB85D150367D25。
   授权发布 P2 addendum，并构建、独立验证隔离的 11D/wing Round4 组件候选。

2. ODR-GPT-08 选择 A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR，引用请求 SHA-256
   5ED037AE057F7119678DECF890C9C0E64740C1443E5E9B9682FC09B8610046F6。
   授权在最终 Round4 组件 PASS 后，按冻结的四车道、两场景、八案例协议执行新版本比较器。

上述决定不预授 Round4、E22-V2/E23、e15、Checkpoint-A、Handoff、生产接触、
制造、资格、飞行或 Terminal Release PASS；旧 FAIL/HOLD 不原位改写。
```

如还要同时启动 Unified R2 C01 单次研究候选，须在同一 Owner 回复中另加：

```text
另行批准一次 C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT、
EXPLICIT_STRUCTURE_PLUS_RESIDUAL、无 Route-C 的 Unified R2 研究候选内存生成。
接受仅对本研究候选排除 Route-C；route_c_cad_authorized=false。
范围仅为 ANALYSIS_ONLY / RESEARCH_CANDIDATE / NON_PRODUCTION。
生产动力学、接触、Sim13 rebind、下一阶段和 Release 均不授权。
若执行时可用内存低于 6 GiB，我接受一次、与 fresh run_id 和不超过两小时窗口绑定的低内存风险：
ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK；memory_gate_passed 必须继续记录为 false。
```

收到第二段授权后，执行代理仍须现场生成 fresh run id、UTC 窗口和三项哈希，形成一次性机器授权记录；不能复用测试夹具或历史 Owner Override。

## 7. 机械终局剩余主链

当前唯一合法的终局主链为：

`ODR-GPT-07/08 → Round4 → 四车道八案例 → E22-V2/E23 → e15 重认证 → Checkpoint-A 重发`

与之并行但不可相互继承 PASS 的物理主链为：

`Route-C P01–P13 + 五类 Owner 输入 → Checkpoint-B 8/8 → 独立 CAD 授权 → 物理 sweep + Mission Coverage → Handoff G12`

已经闭合 source-only 前端、但仍须由真实系统输入和执行授权继续推进的 Sim13 绑定链为：

`M7→Sim13 evidence admission（已冻结） → current-system handoff intake source freeze（已冻结，actual intake HOLD） → preexecution binding security source freeze（已冻结，ABORT-only） → MPI consumer crossbind source freeze（已冻结，current binding HOLD） → 直接 Owner 执行授权 + 实际 MECH_RL_SYSTEM_INTERFACE_V2 + 实际 system URDF + production trust/clock/durable replay → NC18 集成动力学状态演化 + NC19 权威窄相接触 → 正式父 Gate 重发`

三条主链及 Unified R2 版本化 loader、runtime fail-closed、广义力动力学、接触/抓取 Gate 全部闭合后，才允许重新聚合 Checkpoint-C。source-only PASS 只说明合同和拒绝路径可复核，不等于 current-system、dynamics、contact、manufacturing、qualification 或 flight ready。此前，“机械设计可继续研究”成立，“完整当前系统已可进入生产抓取仿真”不成立。

与上述终局链并行、但不得继承正式信用的接触诊断路线为：

`V4A 全浮动无接触核（已审计） → V4B1 无摩擦单点（已审计） → V4B2 正则化摩擦单点（已审计） → V4B3 双分支双点瞬态候选（已审计、rank5、非6D闭合） → V4B4 合成 6-DOF 获取—传播—移除合同（已冻结审计） → V4B4E 求解器+22项实际变异负控+六轨迹跨积分器审计（已完成；获取/主动段 PASS，有限窗无主分支释放；nontrigger 夹具只覆盖算法分支） → V4B4F 合成 P-only 回撤可达性合同（已冻结审计） → V4B4G 后冻结 144 槽注册执行（已失效；3 个 G06 超限；G12 有限配对 9/9 阴性；A2 未执行） → B4G-R1 注册失效收口（合同 PASS only） → B4G-R2 三轨数值预检合同（contract-only PASS） → R2 execution tooling source-freeze（source-only PASS） → R2 raw evidence adapter source-freeze（56-array/86-NC source-only PASS） → R2 full raw-integrity backend source-freeze（10 Gate/14-NC source-only PASS；actual raw=0） → 直接 Owner source + 独立 parent producer + 版本化 vNext runner → 授权后运行 78-case 预检 → 审计后的新 campaign 授权决定或真实执行器/锁止/释放数据绑定 → 当前系统 NC19 重审`

V4B4E 已实现并审计合成获取投影与 active reduced dynamics，但 B3 派生主分支在 `0.08 s` 有限窗内没有 release event；这不是无界不可达证明，也不是物理保持或释放能力。V4B4F 已冻结离散 campaign 合同，V4B4G 随后执行却因注册 G06 超限整体失效；在其保留证据中，9 个有限配对的 G12 科学谓词全部为 false，因而没有 eligible parent、没有 A2 数值执行，也没有可声明的 reachable alpha。R1 只关闭“为什么失败、哪些合同仍分歧、下一轮必须怎样预检”；R2 合同、execution tooling、raw adapter 与 full-integrity backend 依次只冻结预检设计、可重复源实现、严格原始证据入口和完整判据重放能力，均不恢复 B4G 信用。V4B3 仍不提供六维 force closure，V4B4E 的第六约束仍只是新机制假设。尤其在直接 Owner 执行源、独立 parent producer、版本化 runner、由现行 adapter 接收并由本后端重算的真实 R2 NPZ、B601 夹爪闭合/开指时间、接触材料对、摩擦/磨损数据、保持力、接触几何和锁定/释放接口未由受控来源提供前，任何后续结果都只能是 synthetic diagnostic，不能包装成当前机械系统抓取成功。
