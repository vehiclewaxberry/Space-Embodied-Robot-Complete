# KB-B-02 结构假设审计与修正清单

## 1. 本轮结论

```text
STRUCTURE_CONFIG_ISSUE_B601_STOW_Z_AND_SOLAR_PACKAGE_WIDTH
```

选择该终止态的直接原因：

1. B601 唯一可审计的 O13 收拢向量仍为 `CANDIDATE_HOLD`。它只在项目内部横向检查中候选通过，Z 向仍越出当前 bus 顶部，完整连续释放路径也未验证。
2. 已验收保留的太阳翼负证据为 `238.3 mm > 226.3 mm`，且根部布置下界宽度为 `302.3 mm`；当前封装不能被写成 12U 合规。
3. 当前 Cal Poly 12U 规范、所选部署器 ICD、任务发射环境和物理 BOM 均未准入，所以不能用另一组“看起来合理”的外部包络或质量上限覆盖上述问题。

如果两个构型问题被关闭，本轮仍会因外部文档和物理 BOM 缺失降为 `STRUCTURE_BASELINE_PARTIAL`，而不是自动升级为 `STRUCTURE_BASELINE_READY`。

## 2. 裁定口径

- `CONFIRMED`：当前受控文件或机器状态明确支持该命题，且只在其声明的适用范围内成立。
- `CORRECTED`：原命题混淆了数字模型、候选、显示层、仿真层、物理层或资格层；本文给出缩窄后的正确表述。
- `UNSOURCED_BLOCKED`：缺少用户指定的现行规范、供应商 datasheet、测量、已发布 ICD 或合格试验；修正值必须保持 `PLACEHOLDER`。

本轮不以“文件存在”替代准入，也不把 CAD、仿真或历史标准升级为发射资格。

## 3. 逐条假设裁定

### 3.1 12U 规范、包络与质量

| ID | 原假设 | 裁定 | 修正值 | provenance | 对角动量预算 / GJM / 仿真的影响 |
|---|---|---|---|---|---|
| S-01 | 旧 `servicer_12U_v0` 中的 12U 外形可以作为当前合规包络 | `UNSOURCED_BLOCKED` | 当前 12U 外包络、导轨/凸耳、keepout 均为 `PLACEHOLDER` | `20_engineering/cad/spacecraft_layout/servicer_12U_v0/servicer_12U_v0.json`；`DOC-CDS-01`、`DOC-DEP-01` 未准入 | 不得用旧包络判定收拢 PASS；碰撞世界和边界条件不能冻结 |
| S-02 | 旧模型的 `24.0 kg` 是当前 12U 质量上限 | `CORRECTED` | `24.0 kg` 仅是低置信度 primitive 被等效密度强制到的历史目标，已从 BOM 和上限比较中排除；真实上限为 `PLACEHOLDER` | 同上；`structure/BOM_12U.yaml` 的 `excluded_legacy_aggregates` | 角动量预算与 GJM 不得把该值当总线质量或资格上限 |
| S-03 | `23.3032134 kg` 是已确认的平台物理质量 | `CORRECTED` | 仅保留为旧数字总线模型质量快照，不是称重值，也不是完整可加 BOM | `20_engineering/config/geometry/service_spacecraft_v1.yaml`；`20_engineering/design_review/V2_PDR_package/09_digital_thread/mass_owner.yaml` | 不能发布新 GJM 总线质量/惯量；姿态反作用只能算历史模型结果 |
| S-04 | 旧左右太阳翼数字质量可作为飞行件 BOM | `CORRECTED` | 两翼质量均恢复为 `PLACEHOLDER`；旧几何质量仅在审计快照中保留 | `20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv`；现有太阳翼无 released BOM/datasheet | 不得进入轮组卸载、柔性翼或整星惯量模型 |
| S-05 | 旧 PDR 合计 `29.8955559493429862 kg` 是“臂 + 平台总质量” | `CORRECTED` | 仅为 bus、两翼、适配器和数字臂的未闭合历史求和，状态 `AUDIT_ONLY_NOT_BASELINE` | `20_engineering/design_review/V2_PDR_package/09_digital_thread/mass_owner.yaml` | 不能和任何 12U 上限比较，也不能作为 GJM 总质量 |
| S-06 | 当前可以回答“臂 + 平台是否超过 12U 质量上限” | `UNSOURCED_BLOCKED` | 结论为 `PLACEHOLDER / NOT_COMPUTABLE`；合格上限与可加物理 BOM 均缺失 | `structure/MASS_BUDGET.md`；`DOC-CDS-01`；`BOM_12U.yaml` | 质量余量、CoM、惯量、轮组选型和仿真基线全部保持阻塞 |
| S-07 | 可以先给主结构、设备、线缆、紧固件和余量填合理分配质量 | `UNSOURCED_BLOCKED` | 各项 `mass_kg = PLACEHOLDER`；ESTIMATED 项只保留估算方法和不确定度字段 | `structure/BOM_12U.yaml`；用户禁止凭记忆填数 | 防止缺失质量被隐式当零；任何加总器遇到 `PLACEHOLDER` 必须 fail closed |

### 3.2 B601、安装座与载荷路径

| ID | 原假设 | 裁定 | 修正值 | provenance | 对角动量预算 / GJM / 仿真的影响 |
|---|---|---|---|---|---|
| I-01 | B601 的 `4.6955559493429862 kg` 是实物称重质量 | `CORRECTED` | 该值只确认是 accepted hybrid URDF 的逐连杆数字求和，已移到 `model_only_reference`；物理 `mass_kg`、惯量与不确定度均为 `PLACEHOLDER` | `20_engineering/config/geometry/arm_b601_v1.yaml`；`20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf` | 可维持旧模型重放连续性，但机器可加 BOM 和新物理 GJM 必须拒绝该值 |
| I-02 | 臂根安装 X 位置有一个统一值 | `CORRECTED` | 动力学 PDR 轨为 `[185.25,0,0] mm`，显示 CAD 轨为 `[198,0,0] mm`；两者各自 `CONFIRMED`，物理飞行位置为 `[PLACEHOLDER,0,0]` | `20_engineering/config/geometry/frame_tree_v1.yaml`；`20_engineering/cad/B5_0_B601_space_manipulator_candidate/01_KINEMATICS/FRAME_AND_LAYER_LEDGER.md` | GJM/可视化必须显式选轨，禁止静默合并；物理载荷臂尚不能冻结 |
| I-03 | `[0, 1.5707963, 0] rad` 是已发布的物理安装姿态 | `CORRECTED` | 该姿态只 `CONFIRMED` 为现有动力学模型合同；物理飞行 `mount_orientation_rpy=[PLACEHOLDER,PLACEHOLDER,PLACEHOLDER]` | `20_engineering/config/geometry/frame_tree_v1.yaml`；`structure/INTERFACE_ARM_BUS.yaml` 的双轨裁定 | 旧 GJM 可显式重放；新惯量变换、载荷方向和物理接口模型不得消费该姿态 |
| I-04 | 现有 160 × 160 适配件和中心凸台已经定义物理接口 | `CORRECTED` | 只确认为 proposal reference envelope；孔位、材料、厚度许用、连接和定位仍 `PLACEHOLDER` | `20_engineering/config/geometry/arm_mount_v1.yaml`；B5 native adapter 证据 | 可用于空间占位，不能用于连接刚度、预紧、强度或模态 |
| I-05 | B601 根部螺栓分布、等级、预紧和防松已经确定 | `UNSOURCED_BLOCKED` | 数量、孔型、螺纹/配合、等级、预紧、力矩、定位销和防松全部 `PLACEHOLDER` | `20_engineering/design_review/V2_PDR_package/05_robot_mount/robot_mount_load_interface.yaml`；`DOC-B601-ICD-01` | 接头刚度、载荷分配、局部应力和安装重复性无法计算 |
| I-06 | 适配器到主结构的载荷路径未知 | `CONFIRMED` | 已确认拓扑：`A0 → 参考上法兰/扩散板/中心凸台 → task-face 扩散区 → 前横框 → 四根纵向主承载件 → 所选部署器/外部支承接口`；只确认拓扑 | `20_engineering/design_review/V2_PDR_package/02_structure/primary_load_path_contract.yaml` | 可建立模型连接图；材料、截面、接头和边界未定，不能出强度/模态结论 |
| I-07 | 已有载荷路径拓扑即可证明结构承载 | `CORRECTED` | 材料、截面、接头、刚度、边界和载荷全部 `PLACEHOLDER` | 同上；`robot_mount_load_interface.yaml` 的 wrench 字段为空 | 有限元只能停留在模板/拓扑阶段；不得输出安全系数 |
| I-08 | 外板可默认闭合主载荷路径 | `UNSOURCED_BLOCKED` | 当前设计规则为外板不允许静默承担主载荷；若参与承载，必须由接头与边界模型显式发布 | `structure/BOM_12U.yaml`、`structure/LOAD_PATH.md` | 避免仿真因默认 bonded panel 获得虚假刚度和虚高一阶模态 |

### 3.3 收拢构型、发射锁与模态

| ID | 原假设 | 裁定 | 修正值 | provenance | 对角动量预算 / GJM / 仿真的影响 |
|---|---|---|---|---|---|
| C-01 | `q0 = [0,0,0,0,0,0]°` 是发射收拢位形 | `CORRECTED` | q0 仅是建模/展示参考构型，`CONFIGURATION_MATRIX.csv` 的 STOWED 行仍为 TBD | `20_engineering/cad/B5_0_B601_space_manipulator_candidate/03_CAD/CONFIGURATION_MATRIX.csv`；`07_VERIFICATION/GATE_STATUS.json` | q0 不得用于发射包络、锁点、质量特性或环境分析 |
| C-02 | O13 向量已解决 B601 收拢 | `CORRECTED` | 仅存候选：`clock=25°`，`q=[145.572,-168,-57,-41.143,-20.954,-3]°`，状态 `CANDIDATE_HOLD` | `20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/O13_STOW_VECTOR_V3_REPORT.md`；phase-1 machine verdict | 可作为搜索种子，不能写入发射构型或 GJM 初始条件 |
| C-03 | O13 候选已证明符合当前 12U/部署器包络 | `CORRECTED` | 现有证据只确认：项目内部横向候选检查通过，而 O13 超出当前项目 bus 顶面，故 `inside_current_project_bus=false`；当前 CDS/所选部署器合规仍为 `UNSOURCED_BLOCKED` | 同一 O13 报告；其 Z 限值未发布 | 当前项目几何必须保留 CONFIG_ISSUE；外部合规仿真仍不得冻结边界 |
| C-04 | 候选位形的完整释放路径已验证 | `CORRECTED` | `released_trajectory=false`、`full_continuous_sweep=false` | 同一 O13 报告 | 不能安排解锁后全臂展开；仿真需先做连续扫掠和第一运动检查 |
| C-05 | 现有太阳翼能在当前项目包络内收拢 | `CORRECTED` | 保留负证据：`238.3 mm > 226.3 mm`；根部布置下界宽度 `302.3 mm` | `20_engineering/cad/B5_0_B601_space_manipulator_candidate/07_VERIFICATION/ACCEPTANCE_REPORT.md` | 太阳翼几何必须重构；其质量/惯量也不得冻结 |
| C-06 | 发射载荷可由谐波/QDD 减速器和关节保持力承担 | `CORRECTED` | 硬约束：发射载荷必须经具名锁点直接旁路到主结构，减速器不得承载 | 用户许可硬约束；`structure/INTERFACE_ARM_BUS.yaml` | 发射工况模型需禁用“关节刚性锁死即承载”的捷径 |
| C-07 | 烧断线、SMA、分离螺母三种方案之一已经选型 | `UNSOURCED_BLOCKED` | 分离螺母仅为 `DESIGN_ONLY` 候选；产品、数量、预紧、冲击、冗余和资格均 `PLACEHOLDER` | `DOC-HDRM-01`；`INTERFACE_ARM_BUS.yaml` | 不能计算锁点刚度、释放冲击或故障概率 |
| C-08 | 只需在根部设一个锁点 | `CORRECTED` | 设计意图为主根部硬点 + 远端/腕部辅助鞍座，必要时加中间支承；精确坐标和接触预紧为 `PLACEHOLDER` | 用户“减速器不得承载”约束；`INTERFACE_ARM_BUS.yaml` | 仿真必须建立多点直接载荷旁路，不能把柔长臂悬臂化 |
| C-09 | 解锁可在分离后立即执行 | `CORRECTED` | 顺序改为：分离/姿控确认 → 太阳翼释放确认 → B601 电源/数据/制动安全 → inhibit 清除 → 主/辅 HDRM 释放确认 → 有界第一运动 → 完整展开授权；时间值 `PLACEHOLDER` | `INTERFACE_ARM_BUS.yaml`；当前无发布任务 ICD | 任务状态机需按门控事件而非固定延时建模 |
| C-10 | 收拢构型一阶模态目标可按常识填写 | `UNSOURCED_BLOCKED` | `stowed_target_Hz = PLACEHOLDER`；依据必须来自所选部署器与任务 ICD | `DOC-DEP-01`；`DOC-ENV-01` | 模态门、网格收敛和刚度选型均不得设置虚假验收线 |

### 3.4 在轨反力、ADCS 与模型输入

| ID | 原假设 | 裁定 | 修正值 | provenance | 对角动量预算 / GJM / 仿真的影响 |
|---|---|---|---|---|---|
| D-01 | `sim_05` 已给出臂根作业反力矩量级 | `CORRECTED` | `Fx/Fy/Fz/Mx/My/Mz` 与量级全部 `PLACEHOLDER`；现有模型明确不计算关节力矩 | `30_simulation/sim_05_free_floating_arm/README_sim_05.md`；PDR wrench 合同为空 | 不能把运动学反作用输出提升为结构设计载荷 |
| D-02 | 名义轨迹足以定义根部载荷 | `UNSOURCED_BLOCKED` | 至少需要名义运动、急停、捕获瞬态、发射锁定和地面搬运五类已发布工况 | `structure/LOAD_PATH.md`；`DOC-ENV-01` | GJM、结构和控制模型必须共用工况 ID，当前仍未闭合 |
| D-03 | 旧仿真中的反作用轮档位是产品角动量容量 | `CORRECTED` | `momentum_capacity_Nms = PLACEHOLDER`，`max_torque_Nm = PLACEHOLDER`；两字段均已强制写入 BOM | `30_simulation/sim_10_mission_feasibility/` 的 placeholder scan classes；`DOC-RW-01` | 角动量预算不得宣告闭合；饱和、卸载和作业时间窗不可冻结 |
| D-04 | 数字臂质量 + 旧总线质量足以形成新 GJM 基线 | `CORRECTED` | 只能重放历史数字模型；新的物理 GJM 需 M4 发射构型称重、CoM/惯量和已冻结物理安装轨 | `ASSEMBLY_GROUND.md` 的 M4 门；`BOM_12U.yaml` | GJM 输出不得被标为物理预测或结构载荷 |

### 3.5 地面 AIT 与在轨装配

| ID | 原假设 | 裁定 | 修正值 | provenance | 对角动量预算 / GJM / 仿真的影响 |
|---|---|---|---|---|---|
| A-01 | PDR 已验证装配工具净空和可维护性 | `CORRECTED` | 当前明确为 `TOOL_CLEARANCE_OR_ASSEMBLY_VALIDATION: NOT_PERFORMED` | `20_engineering/design_review/V2_PDR_package/06_serviceability/serviceability_review.md` | CAD/仿真必须增加工具体、拆装路径和连接器可达性检查 |
| A-02 | 紧固力矩可从常用表补齐 | `UNSOURCED_BLOCKED` | 所有安装力矩、润滑、预紧、防松和复用限制均 `PLACEHOLDER` | `DOC-FASTENER-01`；`DOC-MAT-01`；`DOC-OUT-01` | 接头刚度与预紧散差不可计算；AIT 只能发布流程骨架 |
| A-03 | RBF 和 inhibits 的数量与实现已经确定 | `UNSOURCED_BLOCKED` | 电池、臂 HDRM、太阳翼 HDRM 等候选 RBF 已列项；独立 inhibit 数量、逻辑与移除责任均 `PLACEHOLDER` | `DOC-CDS-01`、`DOC-DEP-01`、连接器/电气 ICD 未准入 | 状态机可保留门，不得仿真为“已具备飞行安全” |
| A-04 | Flatsat PASS 可覆盖整星结构与收拢验证 | `CORRECTED` | Flatsat 只覆盖电气/软件接口；真实线束、HDRM、包络、质量特性、模态和环境只能由整星验证 | `structure/ASSEMBLY_GROUND.md` | 仿真和试验报告必须保留责任边界，避免证据越级 |
| A-05 | 在轨捕获包络、导向半径、销距、倒角、摩擦和间隙已经有基线 | `UNSOURCED_BLOCKED` | 全部 `PLACEHOLDER`；旧值为 literature/provisional，未准入 | `30_simulation/asm_00_interface_preflight/results/asm_00_gate_check.json` | 接触求解器、容差蒙特卡洛和退出策略尚不能运行合格工况 |
| A-06 | ASM-00 已完成装配物理仿真 | `CORRECTED` | 当前机器状态：`ASM00_AG0_BLOCKED_BY_INTERFACE`，`physics_solver_run=false`，`monte_carlo_run=false`，`next_stage_authorized=false` | 同一 machine gate JSON | 所有锥面/RCC/锁紧/退出结论标 `DESIGN_ONLY`，不得声称仿真或实验支撑 |
| A-07 | 锥面/倒角会自动把任何误差转成安全接触 | `CORRECTED` | 只有在几何、摩擦锥、表面、柔顺和力限共同闭合时才可能收敛；所有数值 `PLACEHOLDER` | `structure/ASSEMBLY_ONORBIT.md`；ASM-00 缺口 | 仿真必须覆盖滑入、卡滞、楔紧和安全退出，而不只跑成功轨迹 |
| A-08 | 自锁等于不可逆楔紧 | `CORRECTED` | 候选为可正锁止、断电保持、可受控重复解锁且有独立状态确认的机构；具体实现 `DESIGN_ONLY` | `ASSEMBLY_ONORBIT.md` | 失败状态必须能 SAFE_HOLD 或重抓持，不能默认强拔 |

### 3.6 外部参考资产

| ID | 原假设 | 裁定 | 修正值 | provenance | 对角动量预算 / GJM / 仿真的影响 |
|---|---|---|---|---|---|
| R-01 | OreSat 的 1U–3U BOM 可提供本项目 12U 数值 | `UNSOURCED_BLOCKED` | 只采用“固定项 + 随卡位增长项 + COTS 分层”的方法，不迁入任何数量、质量或材料值 | `oresat_structure@4c02299`；`Frames/build/framesBOM.xlsx`；`COTS/BoM.md` | 不污染 BOM、总质量、惯量或紧固件质量 |
| R-02 | OreSat 的历史 CDS keepout 与振动夹具可补当前规范和环境 | `CORRECTED` | 只作为组织方法；当前 12U 包络、载荷谱和模态仍 `PLACEHOLDER` | `VolumeKeepout/`、`VibrationJig/`；仓库冻结状态 | 仿真不得用历史 keepout/夹具反推合格边界 |
| R-03 | Space ROS Canadarm 演示可验证自由漂浮 B601 | `CORRECTED` | 上游示例是固定世界关节；零重力世界不等于自由漂浮动力学 | `spaceros_demos@c5e4784255bc1866af15cc2bf1136ba5ef6950e3` | 只采用 description/sim/planning/demo 分层，不能形成 GJM 验证 |
| R-04 | Space ROS demos 已提供充分动力学/端到端测试 | `CORRECTED` | 当前只确认静态 lint 和逐演示容器构建；本项目需自建模型一致性、启动、时钟和自由漂浮测试 | 同上 | 防止“能构建”被升级为“动力学正确” |
| R-05 | SRB 有可直接采用的 12U USD | `CORRECTED` | 没有直接 12U USD；Cubesat 是程序化占位，候选 USD 只作接触/场景原型 | `space_robotics_bench/assets/srb_assets@6b544013684996bb2649934e4a1f5a65f7a63394` | 不从视觉资产提取质量、惯量、B601 几何或结构数据 |
| R-06 | SRB 资产的单位、前向轴、质量和许可证全局统一 | `CORRECTED` | 运行 stage 可确认 Z-up、米制、四元数 `(w,x,y,z)`；单资产前向轴、部分元数据、质量注入与许可证仍需逐项审查 | `knowledge/B_assets_and_conventions.md` 的只读清点 | 资产进入仿真前必须有坐标/单位/许可适配单，不能直接进入 GJM |

## 4. 下游门控摘要

| 下游 | 当前可使用 | 当前禁止 |
|---|---|---|
| 角动量预算 | 字段合同、工况清单、旧数字模型回放 | 轮组容量/力矩、物理总质量/惯量、饱和结论 |
| GJM | accepted URDF 的历史数字连续性、明确选择的 185.25 mm 动力学轨 | 把 198 mm 显示轨或未称重质量写成物理基线 |
| 收拢/释放仿真 | O13 作为搜索种子、已知负证据、第一运动门 | 把 O13 或 q0 宣布为发射收拢；跳过连续扫掠 |
| 结构/模态仿真 | 已确认载荷路径拓扑、显式锁点旁路架构 | 材料、接头、载荷、边界、目标频率未准入时给 PASS |
| 在轨装配仿真 | 状态机、容差链字段、失败分类和退出原则 | 用 provisional 几何/摩擦运行资格蒙特卡洛或声称实验支持 |

## 5. 阻塞项与关闭顺序

1. 获取并准入当前 CDS、所选部署器/适配器 ICD 和任务级发射环境；
2. 选择真实 EPS、ADCS、通信、HDRM 等设备并取得 datasheet；
3. 发布 B601 物理接口、载荷工况、安装轨和锁点；
4. 重构 B601/太阳翼收拢方案，完成全包络连续扫掠与释放路径；
5. 发布材料、表面处理、禁限用材料、出气、紧固件和线束工艺；
6. 完成可加 BOM、M4 发射构型称重、CoM/惯量测量；
7. 再冻结角动量预算和物理 GJM；
8. 关闭 ASM-00 接口字段只是必要条件；还必须关闭 HAG-A 授权缺失、gate registry / interface draft / task card 三项 raw-hash mismatch，并由 machine gate 明确授权后，才允许接触物理仿真与蒙特卡洛。

在上述门关闭前，`BOM_12U.yaml` 可作为完整的字段/所有权骨架交付，但不是 `STRUCTURE_BASELINE_READY`。
