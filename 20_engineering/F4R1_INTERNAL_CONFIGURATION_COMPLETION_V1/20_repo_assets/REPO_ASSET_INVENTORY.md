---
title: REPO_ASSET_INVENTORY — C轨（内部构型完善+帆板成熟化）仓内资产盘点
generated_at: 2026-08-27
author_agent: REPO-INV（C轨研究阶段子代理）
scope: 只读盘点 20_engineering 内与内部布局/质量模型/接口/frame/帆板相关资产；未打开任何 FCStd/STEP/SLDPRT 二进制；未改动任何现有文件
---

# 仓内资产盘点（F4R1 C轨 · 内部构型完善 + 帆板成熟化）

## 0. 盘点口径

- 盘点日期 2026-08-27；所有引用均为仓内文件（路径相对仓库根），关键文件给 sha256 前 12 位（`sha256sum` 实测）。
- 本盘点不含外部公开资料引用；文中「真实帆板 2–5 kg/m²」等表述均为仓内文件自述，非本代理外部核实值。
- **状态分类**：`现行冻结` = R2 发布线（MECHANICAL_ENGINEERING_RELEASE_R2 及其引用链）当前权威，多带 `review_status=PENDING_OWNER_REVIEW`；`V2 历史` = 2026-07-24 V2 PRE-CAD 线，已被 F3R2/M7 中性链接替但仍是三舱布局与 owner 唯一出处；`占位` = 字段为 null / proxy 几何 / SSOT 占位数值，禁止当实测值消费。
- **复用评级**：`直接复用` = C轨可不改语义直接继承；`需迁移` = 结构可继承、数值/命名需迁入 F4R1 新合同；`仅参考` = 不可作为设计依据（二进制不可消费或已被取代）。

## 1. 内部布局（internal layout）

| 资产 | 内容摘要 | 状态 | C轨复用 |
|---|---|---|---|
| `20_engineering/design_inputs/v2_system_mechanical/04_subsystem_layout/V2_subsystem_volume_owner_register.yaml`（sha256 `4e6b405cb65a`） | 12 个 volume owner：前任务舱（robot mount、sensor reserve）、中舱 AVIONICS_EPS_ADCS_BAY（VOL-MID-OBC/EPS/BAT/ADCS）、后舱（PROP/COMM/THERMAL/SERVICE）、两侧帆板。中舱四项均 `geometry_status=DESIGN_PROPOSAL`、`mount_plane=null`、`mass_owner=UNASSIGNED`；规则禁 null 填充、禁未授权 CAD | V2 历史（三舱 owner 唯一 SSOT） | 直接复用（owner 划分与禁填纪律即 C轨布局骨架） |
| `20_engineering/design_inputs/v2_system_mechanical/04_subsystem_layout/V2_serviceability_and_keepout_plan.md`（sha256 `824c315a4d0a`） | 六面板拆卸方向候选（±X_S/±Y_S/±Z_S，均 DESIGN_PROPOSAL）、中舱设备托盘抽取方向 `UNKNOWN_BLOCKED`、纵向线束通道 owner、装配顺序候选 | V2 历史 | 需迁移（方向候选可继承；托盘抽取与工具间隙需新设计） |
| `20_engineering/design_review/V2_PDR_package/11_loop_review/design_decision_matrix.yaml`（sha256 `e54edecca043`） | 三舱选择依据：PDR-D-003 `front_mission/mid_avionics/rear_service_three_bay`；PDR-D-004 主结构拓扑（四横框+四纵梁+两边界 deck，DESIGN_PROPOSAL）；PDR-D-006 owner-first 可更换 reserve 策略 | V2 历史 | 直接复用（布局决策依据与 reopen 触发条件） |
| `20_engineering/cad/audit/artifact_inventory.csv`（sha256 `6ca41827f12e`） | 第 23–27 行：`VOL_MID_ADCS/BAT/EPS/OBC.SLDPRT`（各约 62.6–63.0 KB）与 `SV2_Avionics_EPS_ADCS_Bay.SLDASM`（40.7 KB），class 均 `NATIVE_SOLIDWORKS_PENDING_SW_CHECK` | 占位（native SolidWorks 占位盒） | 仅参考（ODR-03 已将 SW native 线移出关键路径；中性链不可消费 SLDPRT；本任务禁开 CAD 二进制） |
| `20_engineering/cad/spacecraft_layout/model_specs_v0.json`（sha256 `712f4b6411b2`） | `servicer_12U_v0` 9 个解析基元：front/mid/rear 三舱 box 各 113.5×226.3×226.3 mm、flange 15×140×140 mm、camera/nozzle/antenna placeholder、两块帆板 box 227×200×6 mm | 占位（INST_BUS_12U_CORE 的基元定义源） | 需迁移（三舱外廓尺寸可继承；内部为空壳，无设备/结构） |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml`（sha256 `0f9897ef4e41`） | M7 产品树 38 节点（9 个 EXISTS_AS_GEOMETRY、24 个 DEFINED_NOT_MODELLED）；BUS_PRIMARY_STRUCTURE 自述「solid envelope proxy: no internal structure, no bays, no harness voids, no access cut-outs」；BUS_PANELS `DEFINED_NOT_MODELLED`；`unresolved_component_slots` 六项（SENSOR_PACKAGE/ARM_HDRM/TARGET_INTERFACE/GRIPPER_R1_FINGERS/SOLAR_STOW_AND_HINGE/STOW_SUPPORTS）；12U 外廓 340.5 vs 366.0 mm 未调和 HOLD | 现行冻结 | 直接复用（内部构型完善的直接起点与 HOLD 清单） |

## 2. 质量模型（mass）

| 资产 | 内容摘要 | 状态 | C轨复用 |
|---|---|---|---|
| `20_engineering/design_inputs/v2_system_mechanical/05_mass_budget/V2_mass_ownership_table.csv`（sha256 `096144350b15`） | 质量 owner 台账：5 个 source-bound 行（bus 23.3032134、板 ×2 各 0.3483933、adapter 1.2、B601 4.695555949）+ **9 个 subsystem placeholder 行**（OBC_CDH/EPS_PMAD/battery/reaction_wheel_IMU/perception/propulsion/communication/thermal/harness），全部 `UNKNOWN_BLOCKED / NO_HARDWARE_SELECTED / not included in current total` | 占位 | 直接复用（9 个 placeholder 行 = 现成的缺口登记雏形与 owner 字段） |
| `20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv`（sha256 `073c802527e3`） | 7 行 block-model 预算（12U 整星 24.0 kg、bus 23.3032134、单板 0.3483933 等），confidence 全 `low`；现行仿真质量 SSOT | 占位（几何分割 SSOT） | 直接复用（现行 sim 消费；但无内部设备行） |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml`（sha256 `3fd2557318e9`） | R2 设计质量账本（6562 行）：9 构型 C01–C09；C01 总质量 31.022864807342987 kg，行项目 = bus_primary_structure 23.3032134 + B601 4.695555949 + M3R 0.7619 + load_bridge 0.702195458 + solar_r2 L/R 各 0.78（C08/C09 附 target 场景行）；带标准不确定度与 checks（component_sum/no_zero_fill 等）。**全文无 OBC/EPS/BAT/ADCS/propulsion 等内部设备行** | 现行冻结（DESIGN_MODEL，CANDIDATE_ONLY_NOT_AS_BUILT） | 需迁移（行项目组织与 checks 纪律直接继承；内部设备行需 F4R1 新增） |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/07_SYSTEM_MASS_PROPERTIES.yaml`（sha256 `7f7c1ce66069`） | 质量属性三级引用壳：V3_R2（DESIGN_MODEL）/ bridged（E22/E23 已消费）/ AUTHORITY_V2（CDR 现行）；`as_built_metrology: HOLD_EXTERNAL_MEASUREMENT_PENDING` | 现行冻结 | 直接复用（as-built 计量 HOLD 的权威出处） |
| `20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/SYSTEM_MASS_PROPERTIES_AUTHORITY_V2.yaml`（sha256 `32e5b0eeec78`） | CDR 质量权威 V2，classification `CDR_AUTHORITY / CURRENT` | 现行冻结 | 直接复用 |
| `20_engineering/design_review/V2_PDR_package/09_digital_thread/inertia_placeholder.yaml`（sha256 `d7753b794b44`）与 `mass_owner.yaml`（sha256 `51bb0a0442ba`） | V2 数字线程：整车及三构型 mass/CoM/inertia 全 null `UNKNOWN_BLOCKED`；CAD 质量权限恒 false | 占位（V2 历史） | 仅参考（R2 已由 V3_R2 接替；禁从 CAD 填质量的纪律需继承） |

## 3. 接口（interface，含接触与线束合同）

| 资产 | 内容摘要 | 状态 | C轨复用 |
|---|---|---|---|
| `20_engineering/design_inputs/v2_system_mechanical/03_mechanical_interfaces/V2_mechanical_ICD.md`（sha256 `ac71c75cbc1f`）+ `V2_interface_register.yaml`（sha256 `3bf778fb2384`） | 接口总表 IF-RM-001/002、IF-SA-L/R、IF-PL-001、IF-EE-001、**IF-AV-001（主结构→avionics/EPS/ADCS）**、**IF-SV-001（主结构→后舱服务系统）**、IF-MA-001；IF-AV-001/IF-SV-001 已绑定 bay owner，设备尺寸/安装面/热/连接器全 null；含接口停止条件 | V2 历史 | 需迁移（接口 ID 与「已绑定/未闭合」两栏格式直接适用于 F4R1 内部接口 ICD） |
| `20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/MECHANICAL_INTERFACE_CONTROL_DOCUMENT_V2.yaml`（sha256 `b610c9dee359`） | 现行 M3R ICD V2：B601 质量权威=ACCEPTED_URDF；M3R 0.7619 kg BUDGETED（CoM/inertia null，HOLD）；`AS_INSTALLED_METROLOGY_HOLD_EXTERNAL`；惯量张量合同（URDF 约定） | 现行冻结 | 直接复用（F4R1 内部接口文件的格式基准） |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/09_M3R_ICD.yaml`（sha256 `4a051b42acc5`） | R2 对上述 ICD 与 M3R_MASS_RULING 的引用壳 | 现行冻结 | 直接复用 |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/10_GRIPPER_INTERFACE.yaml`（sha256 `6ead2d9dd081`）+ `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/DESIGN_CONTACT_MODEL_V1.yaml`（sha256 `e57c799768bf`） | T4 接触合同 `BOUNDED_PROVISIONAL`：法向刚度 1e6 N/m nominal（区间 1e5–1e7）、阻尼 100 N·s/m，`authority=LITERATURE_ANALOG_NONCOOPERATIVE_TARGET / confidence=LOW`、`as_built=null MEASUREMENT_PENDING`、零填充禁止 | 现行冻结（物理参数占位） | 直接复用（接触窗 T_c 缺口的现行合同与纪律） |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/12_HARNESS_MISSION_ENVELOPE.yaml`（sha256 `6d5405e40c31`） | 线束任务包络：rated envelope `0_SAFE_SAMPLES`、Route-B `REJECTED`（禁重开）、ODR-42 `APPROVE_BOUNDED_DETAILED_DESIGN`（Route-C 有界任务包络）；物理 Route-C 设计为 TMG-4 剩余内部阻断 | 现行冻结（内部阻断） | 需迁移（内部线束走廊设计须与 Route-C 拓扑相容） |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/02_mpi_evidence_audit/README.md`（sha256 `e4d86213d691`）+ 同目录 `B601_ELECTRICAL_AND_DATA_ICD_OWNER_INPUT_TEMPLATE_V1.yaml`（sha256 `0946ed79ddf4`）、`WIRE_LIST_PINOUT_OWNER_INPUT_TEMPLATE_V1.yaml` | MPI-01..08 owner 输入模板族：MPI-01/02=电气与数据 ICD、MPI-03/04=线表 pinout、MPI-05/06=安装构造、MPI-07=安装 ICD、MPI-08=任务寿命；机器 Gate `HOLD`，MPI controlled `0/8` | 占位（空白模板待 owner 填写） | 直接复用（外部输入登记表模板与 fail-closed 纪律） |

## 4. frame

| 资产 | 内容摘要 | 状态 | C轨复用 |
|---|---|---|---|
| `20_engineering/config/geometry/frame_tree_v1.yaml`（sha256 `958bff23bf83`） | frame SSOT v1：`T_SM = [185.25, 0, 0] mm + R_y(+90°)`（`nominal_frozen_v1`）；F_L/F_R origin `[-56.75, ±113.15, 0] mm`；E/C_sat/C_deb/B_int 定义 | 现行冻结（V2 时代建立，R2 继续消费） | 直接复用 |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml`（sha256 `f5b1572c0cfc`） | **ODR-01（frame 权威）**：T_SM 链为 M frame 唯一权威；198.0（plate 外面）/208.0（物理安装面）/210.405 mm（螺钉端面）为几何特征栈，**不得成为第二动力学 frame**。另有 ODR-02（帆板 fail=attached-stuck 禁 jettison）、ODR-03（SW native 线出关键路径）、ODR-05（M3R 质量权威） | 现行冻结 | 直接复用 |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml`（sha256 `0f9897ef4e41`） | frame 块：`arm_base: T_S_B601_ARM_BASE at x = 208.0 mm (frozen F3R2 mapping)`；B601 安装变换 `Ry(+90°)·Rz(+25.000014°)`；M3R installed x-span [196.0, 210.405] mm | 现行冻结 | 直接复用（臂基座 x=208.0 mm 出处文件） |
| `20_engineering/design_inputs/v2_system_mechanical/06_unknown_register/V2_unknown_register.yaml`（sha256 `51df9c560787`） | V2-UNK-004：`T_SB_free_flyer_base_transform` `UNKNOWN_BLOCKED`（自由漂浮动力学基座 B 从未闭合）；V2-UNK-001：12U 340.5 vs 366.0 mm 冲突 | V2 历史（未闭合项沿袭至今） | 需迁移（frame 迁移核对缺口登记的依据） |

## 5. 帆板（panel）

| 资产 | 内容摘要 | 状态 | C轨复用 |
|---|---|---|---|
| `20_engineering/config/geometry/flexible_appendage_v1.yaml`（sha256 `52fa88084c62`） | 帆板几何/质量/刚度 SSOT：`m_panel_kg=0.3483933`（均匀密度份额，文件自述真实帆板典型 2–5 kg/m² vs 本方隐含 7.67）；I_own 薄板值；刚度按一阶频率指派（nominal f1=1.0 Hz，包络 0.7/1.3 Hz，EI 4.36e-3–1.50e-2 N·m²，「NOT measured」）；zeta=0.01 `TBD_cite_literature` | 占位（PROVISIONAL） | 需迁移（帆板成熟化 = 替换此卡占位字段并重过 Gate） |
| `20_engineering/config/coupled_scene/coupled_model_v0.yaml`（sha256 `67a532fb29c7`） | FFR 参数卡：n_modes=3、`euler_bernoulli_cantilever_analytic`、zeta_modal=0.005；`provisional_fields` 明列五项（n_modes/mode_shape/stiffness_case/zeta_modal/contact_T_c） | 占位 | 需迁移（占位字段清单即成熟化工作项） |
| `20_engineering/config/coupled_scene/scene_A2_capture.yaml`（sha256 `4b979a1dfd18`） | A2 捕获场景：`contact.T_c_ms_nominal=20.0`（占位，待 B601 夹爪闭合时间实测，PROVISIONAL）、扫掠 [5,10,20,50,100] ms、half-sine 等冲量模型、窗末 Delassus 小冲量收口 | 占位（接触窗现行合同） | 直接复用 |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V1.yaml` | R2 三叶折展候选：2 翼 × 3 叶（300×200×2.5 mm/叶，accordion）、展开 600 mm/翼、tip-to-tip 1430.8 mm、收拢突出侧面 9.5 mm（HOLD vs 6.5 mm）；wing_total 0.78 kg（areal-density candidate, not measured） | 现行冻结（ENGINEERING_CANDIDATE） | 直接复用（帆板几何基线） |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json`（sha256 `d5b7dd16532f`） | 9 构型帆板质量/CG/惯量；翼组成 leaf 0.18×3 + hinge_root 0.05 + hinge_inter 0.03×2 + HDRM 0.08 + harness 0.05 = 0.78 kg；`basis: areal-density candidate 3.0 kg/m2; NOT measured; no legacy rescale used` | 现行冻结（候选，未实测） | 直接复用（质量行结构；数值待实测升级） |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_R2_MECHANISM_ANALYTICAL_LEDGER_V1.yaml`（sha256 `11d585258597`） | 展开扭矩裕度（候选弹簧 0.05 N·m vs 中途 0.030 / 末 5° 0.040）、端止动能量逐铰传播（铰 2 控制：0.24 J / 480 N / 48 N·m）、latch 不可 back-drive 条件、HDRM D-R2-05 内收拉杆 2 站/翼；全 `PROVISIONAL_DERIVED` | 现行冻结（分析闭合，硬件未选型） | 直接复用 |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_R2_DEPLOYMENT_TORQUE_LEDGER_V1.yaml`（sha256 `5c78e5916b1d`） | 扭矩账本（已被 analytical ledger 吸收）：地测重力矩 0.177 N·m > 弹簧候选 → 地面展开需卸载工装（test-config 结论）；R1 预载裕度不继承 | 现行冻结（分析） | 直接复用 |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/CLEARANCE_MARGIN_LEDGER_R2_V1.json`（sha256 `360da33f502b`） | 间隙裕度账本（as_found / as_fixed_standoff_1p0 两案与 verdict） | 现行冻结 | 直接复用 |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/HARNESS_R2_FUNCTIONAL_GATES_V1.yaml`（sha256 `a47cea1c48fd`） | 帆板线束 55 状态扫掠：root loop provisioned 293.3 mm、min bend 25 mm 达标、板间跳线 flex-PCB 2 mm 级、worst clearance 2.5 mm（对 LEAF3）；B601 时钟弹簧拓扑 take-up 裕度 16.5 mm | 现行冻结（设计） | 直接复用（帆板线束设计基线；内部线束格式参照） |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/11_SOLAR_R2_MECHANISM.yaml`（sha256 `ef02ecc2f283`） | R2 帆板机构引用壳：candidate STEP（FROZEN）+ 上述 mechanism/HDRM-latch/torque 账本指针 | 现行冻结 | 直接复用 |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/13_R2_FLEX_MODEL.yaml`（sha256 `8cadf790cf6a`） | R2 柔性模型引用：HF 183-DOF 组件模型 + 七模态 ROM V3（B1-B3+T1-T4），Gate 17/17 `PASS_WITH_DECLARED_PROVISIONAL_PHYSICS`；E23 重认证 18/18（HF→ROM 误差 0.2714%、Radau/BDF 交叉 1.81e-05）；`provisional_physics: EI/GJ/k_theta/zeta PROVISIONAL_DERIVED bounded intervals; independent latch stiffness null` | 现行冻结（物理参数占位） | 直接复用（ROM 可直接用于论文；物理参数替换 = 帆板成熟化核心动作） |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml` 中 SOLAR_ARRAY_LEFT/RIGHT.PANEL 节点（sha256 `0f9897ef4e41`） | 单板均质 proxy 0.3483933 kg（227×200×6 mm）；HOLD 自述：`HOLD_PANEL_MASS_0P348_KG_IS_AN_SSOT_PLACEHOLDER_REAL_AREA_DENSITY_2_TO_5_KG_PER_M2`；ROOT_HINGE/HDRM/LATCH_STOP 均 `DEFINED_NOT_MODELLED`（轴点有 native Hinge_Pin 旁证） | 占位 | 需迁移（R1 单板 proxy 与 R2 三叶候选并存，C轨须统一口径） |

## 6. 跨区核心发现（给主计划）

| # | 发现 | 证据 |
|---|---|---|
| F1 | **帆板质量双线不一致（最高风险）**：sim_11 coupled_scene 消费 0.3483933 kg/板（均匀密度份额占位，隐含面密度 7.67 kg/m²），R2 设计质量模型消费 0.78 kg/翼（三叶 @ 3.0 kg/m² candidate，未实测）——两线差约 2.24×，且模态参数（1.0 Hz、zeta 0.005）同为占位；根 AGENTS.md 待办 3 已判「论文最大硬伤，优先级最高」 | `flexible_appendage_v1.yaml`、`SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json`、`02_PRODUCT_STRUCTURE.yaml` HOLD 字段 |
| F2 | **R2 质量账本 9 构型无任何内部设备行**：C01 31.023 kg 中 bus 23.303 kg 为包络 proxy，OBC/EPS/BAT/ADCS/推进/通信/热/线束 9 行在 V2 台账中全部 UNKNOWN_BLOCKED；内部构型完善 = 把这 9 行从 null 变为有来源的设计行 | `SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml`（grep 无 internal/avionics 行）、`V2_mass_ownership_table.csv` |
| F3 | **frame 链完整但 T_SB 未闭合**：ODR-01（T_SM=[185.25,0,0]mm+Ry90°）、臂基座 x=208.0 mm、F_L/F_R 均已冻结；唯 `T_SB`（自由漂浮动力学基座）自 V2-UNK-004 起从未闭合——V2→M7 frame 迁移核对是低成本、纯文档动作 | `M7_OWNER_DECISION_REGISTER_V1.yaml`、`frame_tree_v1.yaml`、`V2_unknown_register.yaml` |
| F4 | **外部依赖集中且不可仓内自闭合**：T_c=20 ms 待夹爪实测、P08/P10/P11 与 MPI-01..04 待 owner 输入、as-built 计量 HOLD、内部设备 datasheet 待选型——全部须登记为外部输入请求 | `scene_A2_capture.yaml`、`ROUTE_C_PHYSICAL_INPUT_INVENTORY_V1.json`、mpi README、`07_SYSTEM_MASS_PROPERTIES.yaml` |
| F5 | **可复用骨架齐备（最高价值）**：三舱 owner 登记、质量 owner 台账（9 个 placeholder 行 = 现成缺口表）、IF-AV-001/IF-SV-001 接口壳、R2 帆板三叶候选 + 七模态 ROM、四本帆板机构/线束账本——C轨不需从零建任何登记格式，只需「填值 + 迁移 + 重过 Gate」 | 见 §1–§5 各表 |
