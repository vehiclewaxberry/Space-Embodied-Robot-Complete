# 研究目标、现有证据与下一阶段缺口审计

审计日期：2026-09-21。审计对象为本机工作树；只读代码、合同和机器裁决，不运行新仿真，不改写历史 Gate。本报告是导航和决策建议，不是新科学裁决。61 份机器文件的本次字节数、SHA-256 与关键字段保存在 [RESEARCH_EVIDENCE.json](RESEARCH_EVIDENCE.json)。

**目前适合定位为“服务星与 B601 数字工程候选、分模块物理验证和受限具身决策研究平台”。已经建立相当多的动力学、接触、控制与证据链软件，但尚未闭合“当前整星几何 → 当前物理参数 → 自由漂浮任务控制 → 实际捕获/保持 → SAFE → 具身决策”的同一构型整体验证。**

不能简单沿用 7–8 月导航中的“尚未实现”，也不能将后来候选子包的 PASS 合并成整星系统 PASS。当前父系统 Gate 为 4/13 条件满足，`joint_system_ready=false`、`ready_for_physics_gated_embodied_intelligence=false`；后续子包带来的真实进展需单独陈述。

## 1. 本项目研究目标应如何表述

| 层级 | 当前合理目标 | 可以承诺的阶段产物 |
|---|---|---|
| 当前工程基座 | 可装配、可参数化、可验证的服务星与 B601 地面数字工程样机 | CAD/BOM/接口与参数来源；装配和有界运动检查；候选与未知项明确 |
| 当前主要科学问题 | 自由漂浮条件下，捕获前动作如何影响捕获后的动量、稳定性、执行器资源与柔性响应 | 带适用域的可行域、策略对照、负结果和可复现证据 |
| 下一阶段核心 | 将最新工程构型绑定为一个可复算的数字身体，建立有界自由漂浮接近—接触—保持任务基线 | 同一源构型的质量/惯量、关节与执行器、碰撞/线束、接触和控制 Gate |
| 后续智能层 | 候选动作生成 + 独立物理评价 + fail-closed 决策；再研究学习方法的增量价值 | 确定性基线、数据合同、候选拒绝指标、策略消融；学习层不自行获得安全权 |
| 更远任务 | 预制接口模块装配与带界不确定目标操作 | 分别建立接口、持续接触、不确定性与组合体更新合同，重新验证 |

这与既有 [研究路线](../../../10_research/space_embodied_robotics/research_roadmap.md) 连续，但该文件带 2026-07-23 水印，不能代替下面最新子包的实际状态。

## 2. 已实现到哪里

下列 PASS 都保留其对象、物理假设和作用域；“诊断通过”不等于任务或飞行通过。

| 研究部分 | 当前证据与状态 | 仍不能据此声称 |
|---|---|---|
| 刚体捕获可行域 sim10 | 原机器 `SIM10_GATES_PASS`；9002 个物理点（含锚点），`flex_status=UNKNOWN_NOT_IN_CRITERIA` | 当前 R6H 整星已具备同一可行域；网格占比是成功概率；柔性安全已证实 |
| 策略选择 sim12 | 原 16 格 Gate 保留。8/29 的 GS2 V2 重发**仅替代旧排名字段的适用结论**：24 格为 9 UNKNOWN、15 UNSAFE、0 ROBUST_SAFE；过渡例最鲁棒与最省推进剂的排名不同 | 无条件“A→S1、C→S3a 最优”；旧四种标签构成完整策略比较 |
| 柔性/有限接触带宽 | sim11 为 provisional PASS；E23 七模态 18/18，HF→ROM 最大相对差 0.0027143911284986865（无量纲比例，约0.271439%），跨求解器最大相对差 1.8136532292893113e-05（无量纲比例，约0.001814%；对应Gate的`cross_solver_max_relative`） | 实测模态/接触已完成；E23 数值可直接继承到不同安装位姿或 R6H |
| 当前 R2 动力学候选 | 父 Gate 仍 HOLD。后续 DG1/2 15/15：无量纲参考度量、非零总动量预设关节运动；时变力矩刚体 plant 24/24 | 真实驱动器、柔性、目标附着与完整任务已统一到同一模型 |
| 臂—双翼柔性候选 | DG3 30/30，冻结线性 C=0 模型、14 模态、守恒和退化检查；阻尼分支仅敏感性诊断 | 变构型完整质量阵、全部 Coriolis/Euler–Poincaré 项和力矩驱动全柔性任务已验证 |
| 接触与捕获后质量组合 | DG4 15/15 是两刚体单个无摩擦法向冲量设计诊断，终态仍为两独立体。空间惯量组合 kernel 22/22、外审 18/18 | 真正锁紧、保持或捕获；C08/C09 仍因权威 attachment SE(3) 缺失而 NOT_EVALUATED |
| 设计不确定性 | DG5 16/16，设计质量标准不确定性与 Solar R2 三角点回放 | AS_BUILT 质量、接触与执行器的不确定性已测量/闭合 |
| 控制 | 旧 CTRL01 `REPEAT`、CTRL02 `PASS_WITH_PROVISIONAL_SCOPE`。后续任务度量17项通过；时域 twist 候选19/20（传递 source pin 未通过）；外审18项及 parent-HOLD 重绑定16/16保留原19/20 | 惯性系/目标相对位姿跟踪成功、完整轨迹有碰撞约束、控制硬件有效或整合放行 |
| 独立跨求解器 | MuJoCo 捕获前非接触6/6，19-link/18-joint、31.022864807342987 kg 的冻结 R2；含独立 P/H/能量与4组12 ms控制重放 | 当前 R6H 总质量已绑定；12 ms局部重放证明完整任务；MuJoCo接触/捕获已验证 |
| Sim13 软件与合成接触 | V3浮动基座、V4运行时guard、B1无摩擦、B2正则摩擦、B3双硬指接触已实现且有有界诊断；B3只有rank5，不能形成6D闭合 | “具身智能完全未实现”或反向“整星自主抓取已实现” |
| Sim13 后续 B4/B4G | B4E合成6D约束求解器有诊断，但主释放分支时域耗尽、不确定；B4G失败合同保留82/84/88号slot的离散能量缺陷；R2工具/原始证据适配/完整性后端仅源码冻结 | B4G科学PASS。最新完整性后端Gate为`actual_raw_case_count=0`、`trajectory_count=0`、`current_system_bound=false` |
| Sim13/SAFE整合 | 后端NC子范围20/20；父V2仍15/20、ABORT-only。SAFE原模块PASS、`review_status=PENDING_REVIEW`；当前系统绑定未通过 | 把20/20当整星20项任务通过；把SAFE PASS当执行授权 |
| digital-host/prebind | 数字主机R5有12 episode、单位安全P/H账本及失败生命周期；R5正式Gate仍HOLD缺绝对残差阈值authority。PB-G0/G1仍为诊断预绑定HOLD | 完整数字孪生、真实捕获数据集或当前任务控制通过 |
| 装配/智能学习 | ASM00为接口预检BLOCKED；具身Agent合同、动作接口及fail-closed程序存在。在审阅范围未见当前整星绑定的已训练RL/VLA策略、训练记录和独立任务验收链 | 在轨模块装配、自主VLA、HIL、地面实物或在轨试验已完成 |

Sim14/Sim15 另有刚性塑性捕获与几何载荷分配诊断；它们明确不产生物理接触、训练 RL 或生产动力学信用，不能当作上述整合缺口的替代品。

## 3. 三个需要在 GitHub 首页纠正的状态差异

1. **当前 CAD 与当前物理模型不是同一批新增构型。** R6H 已增补电气装配；上述 MuJoCo、R2 plant 和系统合同仍固定旧 Unified R2 19/18、31.022864807342987 kg。对 `30_simulation`/`10_research` 的 JSON/YAML/Python 内容检索未发现 R6H/R5E/R4 新装配标识的绑定；结合现有源 pin，应将“最新 CAD → 新版质量/惯量/动力学输入”的闭合列为首要任务。检索无命中本身并非数学不存在证明，不代替正式接入审计。
2. **父级 HOLD 与候选子包 PASS 并存。** 父系统 4/13 不能证明后续技术完全未做；DG1–DG5、力矩plant、MuJoCo与接触子包已经形成相当多候选证据。反之这些子包的 PASS 也未自动重发父系统 Gate。建议首页分别列“已实现的有界能力”和“尚未整合的系统能力”。
3. **纸面与摘要中的科学排名要跟随重发范围。** sim12 GS2 V2 明示旧排名的适用结论被不完整因子试验与策略相关 Gate 子集问题取代；原 Gate 字节应保留作历史，但当前论文与 README 不应继续无条件引用旧排名。Wave1 的 `WAVE1_REPEAT`、CTRL01 的真实负结果和 e15 历史重认证负结果均不得清除。

## 4. 下一阶段建议按六项推进

这些是建议工作包和验收定义，本审计没有执行它们；新结果应写入新版本证据，不追溯美化历史 Gate。用户当前选择是“先数字设计与地面样机”，因此数字阶段可使用有来源的设计候选与保守区间；未知实测量保持 null，待采购/试验后单独资格化。

| 优先级 / 工作包 | 具体补什么 | 完成验收条件 |
|---|---|---|
| P0 研究发布与复现封装 | 更新导航、主张—证据索引；分清冻结历史、候选、诊断与当前工程；处理迁移后的输入哈希与会写回原结果的runner | 干净clone在固定环境执行选定最小复现集；输入/输出清单完整；历史结果零覆盖；原负结果逐项保留；sim10四个frozen pin一致或明确使用有来源的新版本迁移层 |
| P1 当前 R6H 数字身体接入 | 以最新装配/BOM为源，逐件质量/质心/惯量与未知项；复核6R+2P、帆板、驱动器、推进/轮组系统边界；发布geometry→link→plant映射 | 统一坐标、单位与源哈希；设计质量不重复计数；惯量合法性与全体账本对齐；FK与装配基准交叉验证；所有未知项可阻断相关结论；新构型不能冒用旧31.022864807kg信用 |
| P2 有界动力学与执行器整合 | 合并已有无量纲/刚体力矩plant/冻结柔性成果；逐步接入变构型臂—双翼时域耦合、实际候选驱动器与轮组/推进器饱和、延迟及资源模型 | 独立全状态P与固定原点H账本；能量/外功；刚化、锁关节和去柔性退化；跨求解器、步长与范围扫描；与实际候选参数关联的速率/力矩/热/电源边界，缺项不得默认通过 |
| P3 接触—保持—释放与组合体 | 明确目标接触patch/normal、夹爪参数、attachment SE(3)、保持约束及释放条件；先修复B4G runner-validator/能量与配对谓词缺口，再开展新版本实验 | 接触/保持/释放分别定义；6D闭合能力不能由rank5两硬指推断；原始时序可独立复算；冲量、力、持续时间不混用；C08/C09真值输入完整后才能实例化目标附着plant；旧失败slot永久保留 |
| P4 当前构型任务控制与安全 | 建立目标相对完整接近轨迹、机械臂/帆板/线束/推进器禁入域、时序与控制；把已有twist短时诊断扩成可评审任务合同 | 全路径关节/执行器/资源限制；连续或有误差界的碰撞/线束证据；基座、柔性与末端误差分别有单位和门槛；SAFE在当前源树独立复验，UNKNOWN无误ALLOW；最终父系统用新版本汇合证据 |
| P5 具身决策与论文证据闭合 | 先确定性FSM/规划器+物理门控基线，再建立感知状态/不确定域/数据集；后续RL/VLA仅作为候选提议层 | 有训练/验证/测试隔离、OOD与false-ALLOW指标、相同预算基线/消融；每条主张绑定模型/数据/Gate/哈希；选择器评价包含不同策略统一Gate集合；本轮不新作“首次/创新性已证明”的声明 |

近期主线建议为 P0 → P1，同时准备 P2/P3 的参数合同；P4 在新构型plant可用后接入；P5的数据接口可并行设计，但完整训练与任务能力声明应等待相应基线。预制模块装配是独立后续支线，ASM00的接口参数、公差/摩擦/卡滞和锁紧后组合体更新需要单独验收。

## 5. 本次只读复核发现的公开复现阻断

2026-09-21直接重算 `20_engineering/config/mission_feasibility/scan_v0.yaml` 四个冻结输入：

| 输入 | 本机现状 |
|---|---|
| threshold_registry | 期望400bcedc…，实际75af082a…，不匹配 |
| sim08_assumptions | 期望850f49da…，实际006c6cc5…，不匹配 |
| sim06_anchor_csv | 匹配 |
| sim08_sweep_csv | 匹配 |

`feasibility_core.load_cfg()` 在验证开启时明确对这类失配抛出异常，因此目前不能向外承诺“按README即可完整复现sim10/sim12”。8/30已有隔离树迁移证明与append-only rebind附录，阈值数值未改变；本轮未应用该修复、未重跑旧仿真。CRLF不是这两个漂移的原因。

8/30复现审计还记录部分 CTRL02测试/runner会写回封存结果。GitHub最小复现入口应在隔离输出目录或一次性clone内执行，输出manifest与原结果比较；不能把“测试通过”作为覆盖历史 Gate 的理由。新平台/干净clone上的依赖与全部端到端重放仍待专门验证。

## 6. 精确证据入口

所有机器文件的完整路径和关键字段可在本报告配套 JSON 搜索；以下为接手顺序：

- 总系统父级：[R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json](../../../30_simulation/r2_dynamics_control_system_closure/results/R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json)，看 `required_condition_evaluation`、`joint_system_ready` 与 `conditions`。
- 新动力学增量：[r2_dynamics_engineering_closure](../../../30_simulation/r2_dynamics_engineering_closure/README.md) 及其 `dg1_dg2_candidate_v2`、`dg3_arm_flex_coupling_candidate_v1`、`dg4_contact_hybrid_candidate_v1`、`dg5_uncertainty_candidate_v1`、`time_varying_torque_plant_candidate_v1`、`post_capture_spatial_inertia_kernel_candidate_v1` 的 `results/*GATE*.json`。
- 控制增量：[r2_control_engineering_closure](../../../30_simulation/r2_control_engineering_closure/README.md)，看 `time_domain_precontact_tracking_candidate_v1/results/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_GATE_V1.json` 的 `summary.failed`，以及 `time_domain_precontact_tracking_metric_parent_rebind_v1` 的不继承字段。
- 跨求解器：[MuJoCo Gate](../../../30_simulation/r2_mujoco_free_floating_precontact_v1/results/R2_MUJOCO_FREE_FLOATING_PRECONTACT_GATE_V1.json)，看 `gate_groups`、`authority_boundaries`。
- 策略重发：[SIM12_GS2_REISSUE_V2.json](../../../30_simulation/sim_13_viability_extension_r1/02_sim12_factorial_reissue/SIM12_GS2_REISSUE_V2.json)，看 `supersedes_scope`、`classification_counts`、`gs2_reissue`、`layer_1_hard_pass`。
- 父子裁决关系：[SIM13_CURRENT_PARENT_CHILD_AUTHORITY_RECONCILIATION_V1.json](../../../30_simulation/sim_13_viability_extension_r1/00_authority/SIM13_CURRENT_PARENT_CHILD_AUTHORITY_RECONCILIATION_V1.json)，看 `sim13_authority_chain.reconciliation_ruling`。
- 当前研究装载候选：[SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_GATE_V1.json](../../../30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/system_binding_candidate_v1/results/SYSTEM_BINDING_V2_RESEARCH_CANDIDATE_GATE_V1.json)，看 `blockers`、`sim13_system_binding_gate_passed`、`maximum_operational_state`。
- B4G失败闭合：[SIM13_V4B4G_R1_FAILURE_CLOSURE_GATE_V1.json](../../../30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4g_r1_registered_failure_closure_contract/results/SIM13_V4B4G_R1_FAILURE_CLOSURE_GATE_V1.json)，看 `failure_closure`、`open_items`。
- B4G最新后端：[SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_GATE_V1.json](../../../30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4g_r2_full_raw_integrity_backend_source_freeze/results/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_GATE_V1.json)，看 `actual_raw_case_count`、`trajectory_count` 与 `required_false`。
- 预绑定数据：[R5_INCREMENT_GATE.json](../../../30_simulation/current_r2_digital_host_capture_data_v1/11_verification/R5_INCREMENT_GATE.json)，看 `threshold_authority_status`、`formal_gate_pass`、`scientific_result_scope`。
- 旧科学证据：[sim10](../../../30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json)、[sim11](../../../30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json)、[sim12](../../../30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json)、[E23](../../../30_simulation/e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json)、[Wave1](../../../10_research/partner_requirement_closure/wave1_results/wave1_gate_check.json)、[SAFE](../../../30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json)、[ASM00](../../../30_simulation/asm_00_interface_preflight/results/asm_00_gate_check.json)。
- 复现迁移：[CURRENT_TREE_REPRODUCIBILITY_GATE_V1.json](../../../30_simulation/sim_13_viability_extension_r1/09_reorg04_repro/CURRENT_TREE_REPRODUCIBILITY_GATE_V1.json)、[REORG04_HASH_REBIND_ADDENDUM_V1.json](../../../30_simulation/sim_13_viability_extension_r1/09_reorg04_repro/REORG04_HASH_REBIND_ADDENDUM_V1.json)。
