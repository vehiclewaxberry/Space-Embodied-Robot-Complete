# Route-C 终局 Owner 系统边界决策包（2026-08-26）

## 总裁决

当前整星仍然是既定的：

```text
12U 服务航天器
├── 双侧 Solar R2 柔性太阳翼
├── M3R 侧挂承力/安装接口
├── accepted B601 六转动关节机械臂
├── Gripper R1
└── Route-C 被动外置线束附件（尚未获任务级接受）
```

并没有变成“只有线束的小装置”。V9F 的 FCStd/STEP 只是局部 dress-pack 子装配，并非整星 CAD；整星、B601、M3R、夹爪与 Solar R2 均未被它替换。

此前 Owner 对“分段受约束移动载体＋低型面双平面鞍座”的授权，已被 [ODR-58](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR-58_RECORD.json) 完整执行。当前再次提供的授权文本 SHA256 与 ODR-58 来源完全一致，因此它不是新的无限迭代授权。ODR-58 的 1 个主候选、1 个同构修复和 1 个异构 fallback 均已使用，剩余几何候选为 0。

V9F 的终局结果只证明：

> **现有 V9F 在当前 M01 直线关节空间路径上失败。**

它没有证明所有六自由度绕行路径不可能，也没有证明所有被动外置走线或 vendor 内走线绝对不可能。当前不能再继续 V10/V11 调线，也不能把 V9F 绑定到 TMG-2、Unified R2、handoff 或 Sim13。

建议 Owner 现在选择：

> **Option A：固定 STOW/RELEASE_CLEAR 端点，授权一次有界六自由度 M01 几何路径研究。**

这是对冻结硬件影响最小、且不缩减当前任务目标的最短路线。

## 1. 终局负证据

机器裁决见 [ROUTE_C_V9F_TERMINAL_RULING.json](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_V9F_TERMINAL_RULING.json)；独立红队和 falsifier 已逐位复算。

| 字段 | 结果 |
|---|---:|
| 任务段 | `M01_STOW_TO_RELEASE_CLEAR` |
| 路径分数 | `s = 0.5` |
| q（rad） | `[0.4849575, -2.513274, -1.5446165, -0.8826395, -0.4446575, -0.02618]` |
| Route-C 实体 | `SEG04_SECTION6_LINK4_DOWNSTREAM_CONDUIT` |
| 障碍物 | `vendor:link3` |
| 原始间隙 | `-10.729480331980062 mm` |
| 降额 | `6.583916664717045 mm` |
| 门控间隙 | `-17.313396996697108 mm` |

这是原始实体穿透，不是单纯由容差降额造成，也不属于注册的 65 mm 合法导向接口窗口。

当前 M01 合同的真实状态是：

```text
trajectory_authority      = MISSING
released_for_mission_gate = false
status                    = UNKNOWN
unknown_policy            = ABORT
```

当前 evaluator 使用 `q(s)=q_start+s(q_goal-q_start)` 的直线关节空间路径。合同中提到的 quintic minimum-jerk 只是时间插值种子；当前 evaluator 不计算时间、速度、加速度或 jerk，因此也没有正式 M01 时间轨迹权威。

## 2. Sim13 状态校正

历史 `00_RELEASE_GATE`、`18_SIM13_PREEXECUTION_GATE`、`19_OPEN_QUALIFICATION_HOLDS` 和 `15_UNIFIED_R2_SYSTEM_INTERFACE` 保留的是 15/20 后端、接口缺席的旧快照。

较新的 [SIM13_20_OF_20_GATE_V1.json](../../30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json) 与 [后端包验证](../../30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_V2_BACKENDS_PACKAGE_VALIDATION_V1.json) 已证明：

```text
NC registry = 20/20 PASS
tests       = 61/61 PASS
release     = false
maximum operational state
            = ABORT_ONLY ... MASKED_BY_12_GATE_AUTHORITY
```

因此，旧文档的“15/20、接口缺席”软件进度字段已被新证据 supersede；但旧文档的 `next_stage_authorized=false` 与 no-release 结论仍然正确。

为避免把后置 20/20 误写回冻结的 15/20 发布快照，现已新增 append-only [Sim13 后终局交接补充 Gate](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json)。它逐哈希绑定 26 个父工件并明确：M4 的九构型仍是身份/数据合同（released mass/CG/inertia 为 0/9）；M7/R2 另有 9/9 `DESIGN_MODEL_R2` 质量、质心和完整惯量；当前 MECH-RL 实例只消费 C01，尚未运行 C02–C09；五个后端工作单 5/5 与负控 20/20 已闭合，但完整 TMG-6 未重签，最大状态仍为 `ABORT_ONLY`。

当前 [机械→具身 handoff](../../20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json) 是 11/12，唯一失败项仍是 G12 `HARNESS_RATED_OPERATIONAL_ENVELOPE`。当前 Sim13 接口仍为：

```text
owner_accepted                    = false
route_c_scope_disposition_pass    = false
sim13_system_binding_gate_passed  = false
current_consumer_load_authorized  = false
current_contact_grasp_authorized  = false
```

所以 20/20 的含义是“所有负控和后端能安全拒绝错误输入”，不是“当前整星已经能执行抓取”。

## 3. Owner 三个合法选择

| 选项 | 做什么 | 最大合法成果 | 主要代价 | 推荐 |
|---|---|---|---|---:|
| A | 冻结全部硬件和端点，搜索一次有界 M01 六自由度绕行路径 | `VERIFIED_GEOMETRIC_PATH_CANDIDATE_PENDING_TIME_AND_OWNER_RELEASE` | 仍需时间参数、P08、8 段任务与完整系统碰撞 | **1** |
| B | 只读核查 vendor 内走线/滑环 Stage-0 可行性 | 允许以后申请详细 ECR；不改当前 B601 | 缺供应商剖面、电气、阻力矩、寿命与环境证据 | 2 |
| C | 保持 TMG-4 与总发布 HOLD | 不新增风险、不新增成果 | 无法进入正式抓取动力学 | 3 |

主动缩减任务域没有列为推荐选项，因为它会改变当前“完整数字样机＋抓取任务”的目标。如果将来确需缩任务，必须另发显式 scope-change ODR，不能由规划器失败自动触发。

### Option A：推荐

授权模板：[ODR-60_OPTION_A_M01_TRAJECTORY_SCOPE_TEMPLATE.yaml](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR-60_OPTION_A_M01_TRAJECTORY_SCOPE_TEMPLATE.yaml)

Option-A 静态预检已完成，机器真值见 [ODR60_OPTION_A_PREFLIGHT_GATE_V1.json](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_PREFLIGHT_V1/ODR60_OPTION_A_PREFLIGHT_GATE_V1.json)，复现入口见 [README](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_PREFLIGHT_V1/README.md)。裁决为：

```text
static integrity = PASS
collision registry = 150 objects / 11,175 pairs structurally enumerated
base_link proxy  = LOCAL GEOMETRY PASS (68/68 BRep valid)
system pairs     = HOLD (11,166 UNASSESSED_FAIL_CLOSED)
pre_search_ready = false
path search       = NOT RUN
release credit    = false
```

预检同时纠正了几个必须在启动规划器前闭合的系统语义：

- M01 只给出 6R 的两个关节空间端点，而 accepted URDF 有 6R＋2P；两条夹爪移动关节不能继续被 evaluator 静默设为零。
- `STOW` 目前只是命名的关节空间端点，不是获释的物理收拢状态；已有接触是占位支撑，ARM HDRM 实体与 `t0- / t0+` 释放序列均未获权威绑定。
- Solar R2 构型/锁定状态及目标的 `present/attached` 状态未绑定。
- accepted URDF 的原始 `base_link` 碰撞 STL 含 140×200×14.5 mm 非飞行桌面底板；它可保留作来源资产，但禁止充当整星运行间隙权威。新的系统登记不再消费该原始 STL，因此“幽灵底板污染当前碰撞场景”的冲突已经被隔离。现行 V2 代理保留 66 个精确 BRep 实体，并以严格公差包络分别替代 DM-J4340P 异常区和一个薄板异常实体；该局部代理几何已通过，但尚未评估任何系统对象对。
- 当前已登记 150 个活动对象：平台 4、臂/夹爪 10、Solar 6、Route-C 硬件 121、线束包络 9；全部 11,175 个无序对象对均有机器记录。只有 9 对直接相邻 URDF link 是活动排除，其余 11,166 对保持 `UNASSESSED_FAIL_CLOSED`。左右夹爪之间保持碰撞启用。
- 15 个 Route-C 局部接口规则展开为 55 个候选对象对窗口；由于精确表面 patch 与运行时谓词未闭合，它们尚未成为活动豁免。旧 evaluator 的 8 组非 J4 整段规则（91 个 segment/part memberships）与 fixed-own-host 整对象跳过均被拒绝继承，J4 整段豁免继续禁止。
- Solar R2 的 10 个条件式 keepout 候选尚未进入当前 pair universe；只有显式绑定 Solar/HDRM/latch 状态并发布新 registry 后，才可把它们激活并补齐所有 `K` 对。

### base_link 运行碰撞代理终裁

为恢复计划中的“12U 服务星＋B601 机械臂”统一模型，首轮从已删除桌面底板的 B50 filtered STEP、经 WP11 `D_base_link` 标定发射代理，得到 67/69 BRep 有效、11 个非零面积面不能三角化的真实负结果。该负结果保留为不可变 lineage。

V2 没有修改 accepted B601 URDF，也没有把外部目录中的 `DM-J4340P-2EC` 采购候选冒充当前装机件，而是采用可证明包络的局部保守替代：

```text
source B50 solids                    = 69
preserved exact BRep solids          = 66
strict containing replacement AABBs = 2
V2 proxy solids / BRep valid         = 68 / 68
final triangles                      = 207,490
boundary / non-manifold edges        = 0 / 0
orientation mismatch                 = 0
aggregate mesh/BRep volume error     = 7.8726e-05
aggregate conservative volume growth = 20.8803%
fresh-process deterministic replay   = PASS
```

V2 STEP、NPZ、binary STL、receipt 与独立 validation 已由顶层聚合 Gate 逐哈希复核，裁决为 `BASE_LINK_PROXY_VERIFIED_PASS`。这只关闭“能否形成无桌面底板、闭合且保守的 base_link 运行碰撞几何”这一项；它没有关闭 11,166 个系统对象对、Solar/HDRM 状态、完整 ACM、连续边证书、Owner 分支选择或运行时内存准入。因此 `pre_search_ready=false`、`path_search_authorized=false`、`next_stage_authorized=false` 维持不变。

### exact-q 适配器与连续边证书方法

查询基础设施已经形成独立、可确定性回放的机器包：[QUERY_INFRASTRUCTURE_GATE_V1.json](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_QUERY_INFRASTRUCTURE_V1/QUERY_INFRASTRUCTURE_GATE_V1.json)；方法与复现说明见同目录 [README](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_QUERY_INFRASTRUCTURE_V1/README.md)。经独立红队发现并修复 `FAIL→SAFE`、负门槛、非法数值异常、调用者自报内存门和不完整回执哈希五类缺陷后，静态审计与 17 个合成/对抗测试全部通过；二次构建的 audit、Gate、manifest 逐字节一致。机器状态仍明确写为 `STATIC_FIXTURES_PASS_ONLY__METHOD_SYSTEM_BINDING_HOLD`。

但这里关闭的是“接口和数学方法存在”，不是系统碰撞：冻结 V9F 的 `eval_clearance(q)` 是 `main()` 内局部闭包，只返回线束中心线对局部三角场的标量最小间隙。它的 mesh pack 仍使用 source SHA `22641C…` 的旧 raw `base_link`，未绑定 V2 operational proxy；1.5 mm 中心线采样也没有 capsule-chain 或空间离散 Hausdorff 降额。因而它只能命名为 `ROUTE_C_HARNESS_POINTWISE_MESH_CLEARANCE_ONLY`，不能充当 150 对象、11,166 个非例外 pair 的 system exact-q API。本轮未执行当前几何查询，也未做 binary64 golden 对拍。

连续边内核现按中点递归与哈希绑定的相对运动 Lipschitz 界工作；两对象运动贡献必须相加，门槛接触不判 SAFE，oracle `FAIL` 不能进入证明链，负 required-clearance 被拒绝，缺系数、非数值/NaN、后端异常或递归预算耗尽一律 UNKNOWN。系统级 motion bound 还必须绑定 pair/object ID、两侧几何、场景、ACM、oracle 实现、关节单位和有效 q 域。它已通过端点/中点/四分点碰撞、双侧运动、阈值接触、异常和确定性回放等合成反例，但当前系统尚无逐 pair exact/保守 lower-bound oracle，也无每对象每关节的全局运动系数，所以 `system_edge_evaluated=false`、`path_search_authorized=false`。当前 exact-q 入口也不再接受调用者自报的 `memory_gate_passed`；由于尚无哈希绑定的 ODR-60 单次 Owner 授权回执，本构建主动拒绝当前几何执行。

### 系统 pair oracle 与对象运动界结构合同

系统级绑定要求已经冻结为独立机器包：[SYSTEM_BINDING_READINESS_GATE_V1.json](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/SYSTEM_BINDING_READINESS_GATE_V1.json)；合同、测试和复现边界见同目录 [README](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/README.md)。独立红队裁决为 `PASS_WITH_STRICT_SCOPE`：30/30 测试、确定性重建逐字节一致、manifest 18/18；真实 registry 与 pair CSV 重算得到 150 个唯一对象、11,175 个唯一 pair、连续 pair index、11,166 个待查询对和恰好 9 个 accepted-URDF 相邻例外。

该 PASS 只表示“结构合同可实施且 fail-closed”，不表示系统碰撞已经通过。每个 q 必须稳定输出全部 11,175 行：9 个 `EXCEPTION_RESULT` 精确回显 ACM/规则哈希且不计 SAFE，11,166 个 `GEOMETRIC_RESULT` 不得缺失或重复。`SAFE` 只能来自严格正的认证下裕量；保守下界非正只能判 UNKNOWN，不能直接判 UNSAFE；`UNSAFE` 必须有认证上裕量或交叠/接触见证。逐 pair clearance policy 必须哈希绑定且满足 `required >= authorized_min >= 0`，负门槛、负降额、抬高下界、倒置上下界或空比较集均 fail-closed。

四阶段 `8,515 → +1,215 = 9,730 → +1,436 = 11,166` 只是计划覆盖，当前实际查询数仍为 0。150 个对象已互斥分类为 `124 direct + 8 J3 hidden + 9 J4 travel + 9 cable capsule`，但系统级运动证书仍为 0；连续边上界必须在完整关节域和完整 J3/J4 隐藏行程上证明，q=0 半径不能继承。

一次交叉审计纠正了原 Gate 中的错误前提：`1BC2B748…` 是 accepted URDF 当前磁盘 CRLF 原始哈希，`408147DD…` 是同一 11,321-byte 文件把 292 个 CRLF 规范化为 LF 后的哈希；规范化后 11,029 bytes，bare LF 为 0。二者不存在 URDF 语义、拓扑、轴系、限位或惯量冲突。208 mm/25° 是 WP11 物理安装轨，185.25 mm/`Ry(+90°)` 是 ODR-01 动力学参考轨；唯一显式桥 `0ACEB659…` 已由 ODR-45 确认为 `CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE`，禁止选边、混用或取平均。

相应的系统绑定 Gate 已 fail-closed 重发，真实 mount 阻断改为：执行期采用 D6 6 位还是 ODR-43 12 位/full 数值拼写尚未绑定；现行 V2 proxy、各 link/D_i 与 Route-C collision assets 到 accepted URDF frame 的 registration 尚未签发。逐 pair clearance policy、9 条 C-section capsule 的 Hausdorff/半径降额、system pair oracle backend 和 150 个对象的运动证书同样未闭合；11,166 对仍未评估。因此 `pair_evaluation_authorized=false`、`edge_evaluation_authorized=false`、`path_search_authorized=false`、`next_stage_authorized=false`、`release_credit=false`。本轮没有加载现役几何，也没有执行任何 pair、edge 或 path。

### mount、scene 与 clearance intake

新增只读机器包：[BINDING_INTAKE_GATE_V1.json](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/BINDING_INTAKE_GATE_V1.json)，人读边界见同目录 [README](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/README.md)。20/20 正负测试通过，Gate/manifest 确定性重建逐字节一致。它只冻结 intake schema，不创造执行值：

```text
accepted URDF content identity = BOUND
ODR-45 physical↔dynamics bridge = BOUND
execution mount spelling        = UNBOUND
collision-asset frame register  = UNBOUND
M01 required scene fields       = 0 / 9
numeric clearance policy rows   = 0 / 11,166
system object motion certs      = 0 / 150
```

M01 还不能被当作单一 constant-scene edge：释放前、释放事件、释放后必须分开；Solar HDRM 字段未进入上游 required list，单一 `solar_latch_state` 也不足以表达两翼六个 latch hardpoint。ARM HDRM、G07/G08/MID 支撑与 target 不在现行 150-object universe；其中任一激活都必须重发对象/pair universe。clearance intake 禁止 wildcard、pair-class default、继承、caller override 和自动补零；即使未来选择 0 mm，也必须是逐 pair、逐场景、Owner/来源/字段/SHA 完整绑定的显式 requirement。

本机具备 NumPy/SciPy、既有 V9F 精确核与 FreeCAD/OCCT；只有在 Owner Option A token、未来执行型系统绑定准入 Gate 和运行时准入全部通过后，才可构造确定性双向 RRT-Connect＋保守宽相＋单一候选精确复核链。但没有 OMPL、MoveIt2、FCL/Coal、SRDF 或现成连续碰撞后端。V9F 精确核实测单姿态约 17.6 s，不能直接放进规划器内循环。有限的 0.25° 采样也不是连续无碰证明，最终必须做递归边细分与保守相对运动界证书。

固定端点：

```text
STOW =
[ 2.540711, -2.932153, -0.994838,
 -0.718081, -0.365716, -0.052360 ] rad

RELEASE_CLEAR =
[-1.570796, -2.094395, -2.094395,
 -1.047198, -0.523599,  0.000000 ] rad
```

冻结项：accepted B601 URDF、硬件限位、vendor body、V9F 几何、bus、M3R、Gripper R1、Solar R2、R2 Full-Flex 与 Route-B 负结果。

一次授权包含固定计算预算：12 次 planner run、固定 seed 集、总节点上限 600000、内部 waypoint 上限 12、最多 1 个精确候选＋1 次平滑/时间律修复、wall-clock 14400 s、峰值常驻内存 5.5 GiB。超预算即 ABORT 并返回 Owner，不自动扩容。

每个实际 run 启动前必须重新测量可用物理内存，名义准入为 `≥6.0 GiB`。本轮只读观测低于 1 GiB，属于瞬时预检读数，不构成未来 run 的 Gate 测量；若届时仍低于 6.0 GiB，必须针对一个新 `run_id`、在不超过 7200 s 的窗口内另行收到精确确认 `ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK`。该确认不可复用，只允许单进程，并必须记录 `OWNER_OVERRIDE_LOW_MEMORY` 与 `memory_gate_passed=false`，不得伪装为内存 Gate 通过。

必须显式绑定：夹爪两移动关节构型、Solar R2 构型、Solar latch/HDRM、ARM HDRM/机械约束释放状态、现行 V2 `base_link` 代理、完整 allowed-collision matrix、11,166 个逐 pair clearance requirement 与 bus 几何权威；还必须选择唯一 execution mount 数值拼写，并把所有碰撞资产通过已确认桥注册到 accepted URDF frame，再实际评估全部非豁免对象对。隐式夹爪零位、手工碰撞豁免、把 D6 6 位与 ODR-43 12 位拼写静默混用、把 `408147…` 误判为旧 URDF，或用稀疏采样冒充连续证明均禁止。

候选必须通过冻结端点、robust joint limits、B601 自碰、整臂/夹爪对 bus/Solar、Route-C cable/hardware 全碰撞、弯曲、pinch、take-up、travel、接口窗口、完整比较集、有限数值、0.25° 或更严精扫、连续区间审计和独立冷进程 replay。

即使 Option A 找到无碰路径，第一阶段也只能输出“几何路径候选”。它不能自动授予：

```text
M01 trajectory release
8/8 mission trajectory release
Route-C/TMG-4 PASS
TMG-2 re-open/PASS
Unified R2 rebind
handoff 12/12
Sim13 non-ABORT
Mechanical Release
```

### Option B：供应商路线，只做 Stage-0

授权模板：[ODR-60_OPTION_B_INTERNAL_ROUTING_SCOPE_TEMPLATE.yaml](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR-60_OPTION_B_INTERNAL_ROUTING_SCOPE_TEMPLATE.yaml)

现有 vendor README 只说明外部 cable restraints 和 7 根 XT30 线束；STEP 中确有 `WIRE-CLIP`、`WIRE-SLIP-COVER` 和 5 个 `Cable Restraint` 命名件，但没有可继承的真实 cable/harness/XT30、slip-ring 或 hollow-shaft feedthrough 产品，也没有经验证的连续内通道。它只能裁为：

```text
validated internal route = UNKNOWN
vendor evidence required = true
```

这不等于“未来 vendor 重构绝对不可能”。Option B 只允许 RFI、逐关节剖面/通道 ledger、电气与质量接口收集、只读截面核查、直接内走线与滑环概念 trade。禁止修改 accepted URDF、禁止从外观推断通孔、禁止直接选滑环、禁止继承任何 TMG/handoff/Sim13 PASS。

若 Stage-0 有可信正证据，才可另行申请最小关节集的 ECR；不得默认六轴全部安装滑环。

## 4. Option A 后仍需闭合的工程链

```text
ODR-60A Owner 授权
  ↓
M01 几何路径候选＋完整系统碰撞/连续区间证书
  ↓
M01 时间参数、HDRM 释放时序、驱动与 P08 扭转恢复力矩
  ↓
完整 8 段任务 Route-C Gate
  ↓
ODR-59 数值规则＋TMG-2 九构型质量/CG/6惯量闭合
  ↓
包含获准 Route-C 的权威 CAD/mesh/Unified R2 重发射
  ↓
Mechanical→Embodied handoff 12/12（含 G12）
  ↓
Sim13 当前系统 12 门绑定＋20/20 在新哈希下重放
  ↓
22 kg 目标星与 150 kg 碎片抓取动力学运行
  ↓
Red Team＋Falsifier＋R2 V2 增量发布＋机械范围冻结
```

其中 P08 当前只有 `[0,10] deg/m` 的导向 clocking 设计分配，安装线束扭转恢复力矩曲线仍为 UNKNOWN。`deg/m` 不能转换成 `N·m`，所以即使碰撞路径通过，关节阻力矩仍保持 HOLD。

## 5. 现在需要的 Owner 回复

[ODR-60 决策请求](../../20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR-60_DECISION_REQUEST.json) 已准备好。请严格回复以下一个 token：

```text
AUTHORIZE_OPTION_A_FIXED_ENDPOINT_M01_TRAJECTORY_SEARCH
```

或：

```text
AUTHORIZE_OPTION_B_VENDOR_INTERNAL_ROUTING_OR_SLIP_RING_FEASIBILITY
```

或：

```text
KEEP_ROUTE_C_TMG4_AND_MECHANICAL_RELEASE_ON_HOLD
```

在收到唯一明确 token 前，所有 Gate 保持 fail-closed，不执行新路径搜索、不改 B601、不进入非 ABORT 抓取仿真。

即使收到 Option A token，也只先记录分支选择；V2 `base_link` 局部代理、查询基础设施、系统绑定结构合同以及 mount/scene/clearance intake 已不再是“完全缺失”，而 accepted URDF 双哈希与 ODR-45 frame bridge 已纠正并绑定。但仍须补齐 9 项显式场景状态与事件分段、execution mount 数值拼写、collision-asset frame registration、完整 ACM、11,166 行 clearance policy/碰撞覆盖、V2 proxy/capsule-chain 绑定的逐 pair exact 或保守 lower-bound API、当前系统每对象运动证书、V9F binary64 对拍和运行时内存准入。只有未来执行型系统绑定准入 Gate（不是本轮 readiness/intake Gate）将 `pre_search_ready` 转为 `true` 后，才允许启动任何搜索进程。
