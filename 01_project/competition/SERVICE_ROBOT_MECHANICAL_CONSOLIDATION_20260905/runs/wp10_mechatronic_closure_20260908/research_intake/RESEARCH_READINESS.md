# 当前机电候选与后续研究的衔接审计

2026-09-08。工作模式：`STATE_AUDIT / QUESTION_ROUTING / THEORY_CHAIN_AUDIT / CONTRACT_DRAFT`。

**可以进入理论、证据分析和有明确假设的模型研究准备；当前尚不能将 873 叶零件装配交付为“完整闭环、可预测真实硬件行为的数字身体”。** 本文是 WP10 的派生研究任务合同，不是新的科学总裁决，也不签发数值执行、训练或硬件权限。用户“若可以交付便转入研究”的条件性意向未被解释成直接开训。

机电设计和动力学研究存在双向依赖。结构连接、载荷裕度、驱动与供电定型，需要动力学提供臂致反作用、捕获载荷、速度/力矩及能量需求。没有必要让全部理论与假设模型研究等待全部硬件完善；研究输出需要注明构型、假设、工况、来源与不确定性，交回工程线核查，而不能冒充实测设计包线。

## 已读取的权威证据

启动完整读取 `.codex/agents/space-embodied-intelligence-research-agent.md`、CLAUDE、PROJECT_MAP、project_context、Physics Agent 薄入口与规划合同，再读取 Q1–Q6 及下表原始证据。[SOURCE_BINDINGS.json](SOURCE_BINDINGS.json) 固定 26 份任务证据的路径、字节数与 SHA-256；[RESEARCH_READINESS.json](RESEARCH_READINESS.json) 保留 exact 状态。[UPSTREAM_HASH_AUDIT.json](UPSTREAM_HASH_AUDIT.json) 逐项列出另行检查的历史绑定。

| 来源 / 本地原始位置 | exact 状态及可用范围 | 对当前样机的限制 |
|---|---|---|
| `30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv` 与原 URDF/README | CSV 最大基座偏转 19.199852°；旧动力学系统约 29.895556 kg；没有定位到独立 sim05 总 Gate JSON | 不能直接当当前质量。q2=+60° 超过旧 URDF 的上限 0 rad，原 README 明确其为动力学基准；不是可执行轨迹 |
| `sim_10_mission_feasibility/results/sim_10_gate_check.json` | `SIM10_GATES_PASS`，9002 个物理点；`FLEX=UNKNOWN_NOT_IN_CRITERIA` | 24 kg 是质量比参考分母；不能当当前总质量或覆盖柔性/新推进设备 |
| `sim_12_strategy_feasibility/results/sim_12_gate_check.json` | `SIM12_PHASE1_GATES_PASS`，16 个工况×策略单元 | 绑定约束下比较，不是通用策略排名、训练结果或真实成功率 |
| `sim_11_coupled_dynamics/results/sim_11_gate_check.json` | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`；保留原 `next_stage_authorized=true` | 原许可只属该历史合同。20 ms 接触时间、解析模态、阻尼等 provisional，不能转为本轮执行许可 |
| `e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json` | 18/18，`PASS_WITH_DECLARED_PROVISIONAL_PHYSICS`；HF→7 模态相对差 0.0027143911284986865；next=false、release=false | 只属 R2；`sim10_authority_inheritance=NOT_INHERITED_THRESHOLD_HASH_DRIFT`；不能证明新帆板/CIC/胶层/机构性能 |
| `MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json` | `TERMINAL_CLOSURE_EXECUTED__GATE_A_NOT_PASSED__TMG4_TM6_INTERNAL_BLOCKERS_REGISTERED__NO_RELEASE_CREDIT` | 原终裁的 15/20 保持历史不变；不能套用至当前 873 CAD，也不能用当前 CAD 文件数量改写它 |
| Sim13 `runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json` | `SIM13_NC_REGISTRY_20_OF_20_PASS__PENDING_OWNER_REVIEW__NO_RELEASE_CREDIT` | 20/20 是负控注册表，仍 `ABORT_ONLY...PRODUCTION_NON_ABORT_STILL_MASKED...`、next=false；不是抓取/RL 成功 |
| Sim13 V4A audited Gate / B4G superseded / R2 tooling source freeze | 已有独立合成无接触内核证据；后续工具源冻结 `PASS_PHASE_B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_ONLY` | 合成模型未绑定当前 CAD；B4G旧终裁信用已标记 superseded，R2该冻结件明确数值预检未执行、trajectory_count=0，不能声称完整 campaign 通过 |
| SAFE-00 / ASM-00 原 Gate | SAFE `PASS` 但 next=false；ASM `ASM00_AG0_BLOCKED_BY_INTERFACE` | SAFE 不提供研究或硬件权限；机械静态装配不等于 Q6 在轨模块装配 |
| WP09 `system_completion/results/DELIVERY_STATUS.json`、`MASS_ROLLFORWARD_873.json`、`NATIVE_DELTA_DELIVERY.json` | 三态每态 873 叶部件、10 个容器；静态原生保存/冷重开/搬迁证据；数值质量覆盖 400，未知 472，另有 1 保留实例 | 整机质量/COM/惯量均 null，连续动作=false，整机机电完成=false；目录归属覆盖 873/873 不是质量已知率 |

## 本轮实际发现的复现冲突

只读核对 107 条原始 raw SHA 绑定：**78 匹配，29 漂移，缺失 0**。具体为 sim10 2/4（threshold registry、sim08 assumptions）、sim11 26/58（summary JSON）、E23 输入 1/25（accepted FK module）。E23 自身 14 条证据绑定、Sim13 20/20 registry 和 V4A 的 4 条直接上游绑定匹配。

这不等于历史数值结论被推翻，但意味着**不能承诺当前 checkout 可直接逐位复现原通过结果**。此次没有判定漂移原因，没有用规范化后哈希替代 raw SHA，也没有重写原 Gate。下一次数值复现必须先核对原快照及哈希；无法获得原字节时，应另立版本明确重绑定，并重做受影响检查。仅“文件存在”不满足复现条件。

旧 R2 C01 的 **31.022864807342987 kg** 是带设计不确定性的特定构型值。当前 WP09 的总质量未知，B601 厂家整机参考 4.5 kg 与旧 URDF 求和 4.695555949342986 kg 也不是同一可直接替换的惯性参数源。对应关系见 [MODEL_PARAMETER_CROSSWALK.csv](MODEL_PARAMETER_CROSSWALK.csv) 和 [JSON](MODEL_PARAMETER_CROSSWALK.json)。

## 可立即准备的研究与缺口

| 研究任务 | 现在可做的工作 | 转入数值研究前的最小内容 |
|---|---|---|
| Q1 / Q3：自由漂浮刚体、动量约束与反作用 | 阅读旧原始结果、推导方程、准备具有新版本身份的基准合同 | 输入帧、质量/惯量、关节模型；零外力/锁关节/刚化退化、P/H/E 与交叉解对照；历史精确复现另需原始哈希一致 |
| Q2 / Q3：有限接触与柔性 | 接触带宽、刚度/阻尼假设和模型适用域合同 | 载荷与作用点、模型阶次、接触窗及非线性边界；不能把仿真的接触窗直接当夹爪闭合实测 |
| Q3 / Q4：几何避障与抓取候选 | 用当前 CAD 准备 link、禁入区、代理几何误差和连续检查合同 | 873 实例→刚性 link 的唯一映射，关节轴/符号/零位/界限，碰撞代理保守误差、夹爪/线束/帆板运动包络。纯几何研究无需先准确称完整卫星，但不得称动力学可执行 |
| 当前硬件的动力学与控制性能预测 | 参数清单、工况与验证链准备 | 每个运动 link 的质量/COM/惯量与区间；全机拓扑；驱动力矩–速度–电压–温度/延迟；轮组/推进布局与饱和。当前这些缺口仍阻断真实样机预测 |
| Q3 / Q4：受物理约束强化学习 | 定义研究问题、确定性基线、观察/高层候选/奖励/终止/OOD 与消融协议 | 先有明确环境版本与适用域，再冻结训练测试隔离和评价指标，并明确数值/训练任务范围。本轮不启动训练；合成环境结果不得改称当前硬件性能 |

建议依赖路线是：**自由漂浮刚体守恒与反作用 → 有界接触/柔性 → 明确构型和误差的几何避障 → 确定性基线之上的策略学习**。这是技术依赖建议，不是要求各支线机械串行继承 PASS。几何合同和算法问题设计可并行进行，真实硬件有效性始终独立检查。

## 研究交回工程的合同

动力学/控制线未来应交付：构型身份与源哈希、载荷定义及参考点/坐标系、质量与惯量区间、关节速度/力矩包络、捕获工况、结构连接载荷、轮组/推进需求、供电/再生峰值与时窗，并明确适用域和未测项。工程线再据此完成连接、强度、驱动、供电、停止链及热设计。禁止用另一构型的标量峰值直接作为当前安装件设计载荷。

每个新任务应固定单一问题、输入、来源、假设、比较基线、预注册指标和停止条件，再选择实现工具。未知或 OOD 可作为数学研究对象；当任务声称“对当前真实机器人有效”时，未知输入必须保持 HOLD，不得零填充或由旧 PASS 补齐。

## 实际交付与验证边界

[validate_research_contract.py](validate_research_contract.py) 只检查源文件字节/哈希、任务模型身份、Q1–Q6 路由、文档权限语义和原始缺口保留，包含错误质量替换、873 归属覆盖冒充数值覆盖、旧模型移植、假哈希、训练授权注入、UNKNOWN/OOD/provisional 冒充硬件有效性等负控。[RESEARCH_CONTRACT_VALIDATION.json](RESEARCH_CONTRACT_VALIDATION.json) 是文档合同验证回执，不能解释为物理可行性评价器或科学 Gate。

合法下一出口为：工程线按本轮机电开项继续收束；研究线选择一个具有明确假设的 Q1/Q2/Q3/Q4 问题，完成输入与验证合同，并在明确数值任务范围后再交给相应执行职责。现有冻结 Gate、阈值、配置及结果均未修改。

本次仿真 0、训练 0、CAD/装配执行 0、硬件动作 0、外部获取 0、文献题录/阅读状态修改 0。未启动新算法栈或生成训练数据。涉及后续文献时仍由项目 Paper Knowledge Orchestrator 统一处理，不在本目录建立平行题录。
