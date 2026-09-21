---
title: F4R1 C3 阶段第一步 设计依据整合 V1（DESIGN_BASIS_V1）
generated_at: 2026-08-27
status: DESIGN_RESEARCH_CANDIDATE
artifact_id: DESIGN_RESEARCH_CANDIDATE
scope: 内部结构架构设计依据：需求登记表 + 载荷工况表 + 接口冻结清单；供 CA-A/CA-B/CA-C 候选架构与后续红队/裁判直接引用
machine_check: CANDIDATE_MASS_CG_V1.json（compute_candidates.py 可重跑，stdlib-only，捕获峰值力 60.9 N / 17.6 N·m 由 sim_06 CSV 复算）
governance: 冻结区只读；本文件不修改任何 Gate/SSOT；估计标 ASSUMED，缺数据写 UNKNOWN
---

# F4R1 C3 设计依据整合 V1

## 0. 口径声明

- 坐标系 S frame（原点=12U 几何中心，x=纵轴，任务/臂方向为 +x，单位 mm）；全部坐标基于**冻结 340.5 mm 舱长口径**（GAP-IL-08/V2-UNK-001 的 340.5 vs 366.0 冲突登记为 C1 OI-6，post_paper HOLD）。
- 两质量口径并存：**DESIGN_POINT 31.0229 kg**（ODR-F4R1-01 主口径，ESPA 级登记，"12U-derived form factor"）与 **CDS_VARIANT ≤24 kg**（并行合规线，当前 17.660 kg 含 15% 余量，CG x/y 超差登记 OI-1）。
- 本阶段为结构架构候选设计（DESIGN_RESEARCH_CANDIDATE），不做选型裁决（ODR-F4R1-02 §2 设计法庭：红队+裁判职责）、不做 CAD 实体、不碰帆板参数（C2 已定档）、不碰 Route-C 线束实物参数（HOLD）。

## 1. 需求登记表（requirements_register，22 条）

| id | requirement | value | source | verifiability |
|---|---|---|---|---|
| DB-R-01 | 全星外包络（含收拢臂/收拢帆板/天线）不得超限 | 226.3×226.3×366.0 mm；侧突出 ≤6.5 mm；四角 8.5 mm 导轨带无穿透 | CDS Rev14.1 App B / §2.2.3/2.2.5（NASA 镜像 https://www.nasa.gov/wp-content/uploads/2018/01/cubesatdesignspecificationrev14_12022-02-09.pdf ，经 B1 §1.1/§6-R1 转引，B1 sha256_12 738bb4cf6402） | 几何检查（C3 CAD 阶段干涉核查；当前登记 OI-6 口径冲突） |
| DB-R-02 | 三舱划分沿 x 轴 | front_mission [56.75,170.25] / mid_avionics [-56.75,56.75] / rear_service [-170.25,-56.75] mm | EQUIPMENT_LIST_V1.yaml bay_bounds_mm（sha256_12 2f6b5163f5f5）；PDR-D-003（B1 §0，design_decision_matrix.yaml sha256_12 e54edecca043） | 全部设备坐标落舱界内（C1 已机器核查） |
| DB-R-03 | 臂基座站位冻结 | x=208.0 mm（F3R2 映射冻结，不可改） | 02_PRODUCT_STRUCTURE.yaml frame.arm_base（sha256_12 0f9897ef4e41） | frame 一致性检查（C3 Gate 项） |
| DB-R-04 | frame 权威 ODR-01 | T_SM=[185.25,0,0] mm + Ry(90°)；198.0/208.0/210.405 为几何特征栈而非第二动力学 frame | 02_PRODUCT_STRUCTURE.yaml frame.m_frame_authority（sha256_12 0f9897ef4e41） | frame 一致性检查 |
| DB-R-05 | B601 臂质量（含夹爪） | 4.6956 kg（ACCEPTED_URDF，永不覆盖） | SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml#C01（sha256_12 3fd2557318e9）；02_PRODUCT_STRUCTURE B601 mass_authority | 与冻结账本逐值比对（C1 已做，delta=0） |
| DB-R-06 | M3R 接口组件 | 0.7619 kg BUDGETED；installed x-span [196.0,210.405] mm；Stage A 环+Stage B 载荷扩散板；紧固 4×M4 64×64 mm | 02_PRODUCT_STRUCTURE.yaml M3R 节点（sha256_12 0f9897ef4e41）；MECHANICAL_INTERFACE_CONTROL_DOCUMENT_V2.yaml（sha256_12 b610c9dee359，AS_INSTALLED_METROLOGY_HOLD_EXTERNAL） | 接口跨度/质量与冻结文件比对 |
| DB-R-07 | spacecraft load bridge | 0.7022 kg MATERIAL_DERIVED 6061-T6 2700 kg/m³；x-span [185.25,196.0] mm | 02_PRODUCT_STRUCTURE.yaml SPACECRAFT_LOAD_BRIDGE（sha256_12 0f9897ef4e41）——本仓内唯一材料密度权威行 | 同上 |
| DB-R-08 | DESIGN_POINT 质量口径 | 31.022864807 kg（=冻结 C01），ESPA 级登记，12U 表述与 deployer 解绑 | ODR_F4R1_01_SIGNED.md clause 4（sha256_12 88fb25431d1a）；MASS_BUDGET_V1.csv TOTAL-DESIGN-POINT（sha256_12 365c9ebf9493） | 机器复算（C1 已 pass） |
| DB-R-09 | CDS_VARIANT 质量上限 | ≤24.00 kg 含 ≥15% 系统余量；当前 17.660 kg（干重 15.357 kg） | CDS §2.2.10 Table 1 + VMMO 15%（B1 §6-R2，https://openresearch.surrey.ac.uk/view/delivery/44SUR_INST/12139785870002346/13140667620002346 ）；MASS_BUDGET_V1.csv TOTAL-CDS-VARIANT-MARGINED | 机器复算（C1 pass；本包 compute_candidates.py 对候选复核） |
| DB-R-10 | CG 包络与 CDS 变体超差现状 | CDS：S_x ±70 / S_y/S_z ±45 mm；CDS 变体现状 CG=[127.83,-54.30,-39.10]，x 超 -57.83、y 超 -9.30；压载需求 ~3.2 kg 量级 | CDS §2.2.11 Table 2（B1 §1.1）；CG_INERTIA_CHECK_V1.json（sha256_12 c7759162f54d）；GATE_C1 OI-1（sha256_12 b07cca047146） | compute_candidates.py 对每候选复算两口径 CG |
| DB-R-11 | 结构质量预算 | 二级结构额度 1.0 kg（EQ-SEC-STRUCT，ASSUMED，待 C3 细化）；CDS 变体主结构 2.0 kg（ST-STRUCT-REAL，B1 表 3 取保守上限） | MASS_BUDGET_V1.csv 行 EQ-SEC-STRUCT/ST-STRUCT-REAL（sha256_12 365c9ebf9493）；B1 §2.1 表 3：12U 裸结构 1.2–2.0 kg（ISIS 2.0 kg https://www.satcatalog.com/component/12-unit-cubesat-structure/ ；SM12 1430 g https://catalog.orbitaltransports.com/sm12-12u-cubesat-structure/ ；VERSE-12 1190 g https://blog.satsearch.co/2020-09-25-satellite-structures-on-the-global-marketplace ） | 候选结构质量 vs 额度（est_mass_growth_vs_budget，机器复算） |
| DB-R-12 | 40 行设备全覆盖 | 每行 mounting_face 必须映射到候选安装面（6 FROZEN_REF + 33 EQ + 1 ST） | EQUIPMENT_LIST_V1.yaml（sha256_12 2f6b5163f5f5） | compute_candidates.py 覆盖核查（31 个 mounting_face，三候选均 31/31 pass） |
| DB-R-13 | 帆板 R2 三叶 + HDRM 根部接口 | 2 翼×3 叶（300×200×2.5 mm/叶，0.78 kg/翼）；HDRM 每翼 2 站（D-R2-05 内收拉杆；native Base_1 x∈[-172,-148]、Base_2 x∈[28,52]、y∈[113.15,121.15]）；根铰轴点 [-61,±143.15,0]；Hard_Stop [-64..-58,±121..129,23..37]；端止动能量 ≤0.2356 J | SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json（sha256_12 d5b7dd16532f）；02_PRODUCT_STRUCTURE.yaml ROOT_HINGE/HDRM/LATCH_STOP 节点（sha256_12 0f9897ef4e41）；SOLAR_R2_MECHANISM_ANALYTICAL_LEDGER_V1.yaml（sha256_12 11d585258597） | 站位坐标与冻结文件逐值比对（C3 干涉核查项） |
| DB-R-14 | 展开弹簧升级空间 | 升级后弹簧 ≥0.060 N·m（mid-travel）/ ≥0.080 N·m（final-5deg，控制工况）；现候选 0.05 N·m FAIL_2X_RULE；结构须留铰链舱 | GATE_C2_CHECK.json OI-2（sha256_12 69db708fbf30）；PANEL_PARAM_ENVELOPE_V2.yaml NOMINAL/HIGH verdict（sha256_12 074f868ee762） | 候选 spring_upgrade_accommodation 声明 + C3 空间核查 |
| DB-R-15 | 发射段准静态载荷 | ASSUMED ±10 g 三轴准静态（ rideshare 惯例量级；仓内无权威发射载荷文件 → 标 ASSUMED）；分离弹簧 <6.7 N / 行程 >2.5 mm | ASSUMED（无仓内来源）；CDS §2.2.14.1（B1 §1.2） | 本阶段不做强度校核（CHARTER §2 OUT）；仅作构件布置/传力路径定性依据 |
| DB-R-16 | 在轨捕获载荷（臂基座传递） | sim_06 40 工况：max |J| = 0.7749 N·s、max 力偶 = 0.2236 N·m·s；T_c=20 ms 半正弦窗 → 峰值 **60.9 N / 17.6 N·m**（机器复算） | capture_impulse_matrix_v0.csv（sha256_12 8cbad84b8ff6）；README_sim_06.md（sha256_12 9531497d5052）；T_c PROVISIONAL（scene_A2_capture.yaml sha256_12 4b979a1dfd18，待夹爪实测 GAP-IF-01） | compute_candidates.py capture_loads（可重跑） |
| DB-R-17 | 在轨臂操作基座扰动 | 臂致基座姿态扰动峰值 19.20°；peak |H_bm·q̇| 角向 0.0891 kg·m²/s、线向 0.1602 kg·m/s；关节力矩未建模 → 臂基座反复弯矩具体量值 UNKNOWN | README_sim_05.md（sha256_12 181eba2721e7） | 定性登记（结构疲劳/微振动评估留待后续，UNKNOWN 不编造） |
| DB-R-18 | 线束通道约束 | 内部走廊 rear→mid→front、power/data/RF 分离（B1 R11）；Route-C 外部线束 HOLD 不碰；P06=minimum_dynamic_bend_radius_mm 在 registry 为 **null/HOLD → MEASUREMENT_PENDING**；帆板根部 loop 293.3 mm / min bend 25 mm 相容 | CHECKPOINT_B_PHYSICAL_INPUT_MATRIX_V1.csv（sha256_12 a046340fcae8）；12_HARNESS_MISSION_ENVELOPE.yaml（sha256_12 6d5405e40c31）；HARNESS_R2_FUNCTIONAL_GATES_V1.yaml（sha256_12 a47cea1c48fd）；REPO_ASSET_INVENTORY.md Route-C/E_HRN 条目（sha256_12 d3326b44e4d4） | 候选 harness_channel 声明 + P06 状态核查（**注意**：任务简报示例"P06=50 mm LOW 档"未在 registry 查到，三候选一律按 MEASUREMENT_PENDING 处理） |
| DB-R-19 | CDS 材料/工艺条款 | 结构与导轨 Al 7075/6061/6082/5005/5052；接触 dispenser 面硬阳极化；材料 TML ≤1.0%/CVCM ≤0.1% | CDS §2.2.12/2.2.13/§2.1.7（B1 §1.2/§1.4） | 候选材料选择声明（al6061 仓内权威；al7075/cfrp/steel ASSUMED） |
| DB-R-20 | 热控布局 | 发热件（EPS/电台/推进 PPU）贴结构面板；电池独立安装面远离热源；纯被动热控（MLI+涂层 150 g ASSUMED） | B1 §6-R8/R9；EQUIPMENT_LIST_V1.yaml EQ-TH-MLI | 候选 thermal_notes 声明 |
| DB-R-21 | 泄压与密闭舱 | 上升段泄压 ventable volume/area < 50.8 m；密闭舱（电池/推进）开泄气孔 | CDS §2.1.9（B1 §1.4/§6-R14） | 候选声明（CA-B 封闭剪切盒专项） |
| DB-R-22 | 干涉/CMA 与维护 | 设备按含间隙 bounding box 建模；干扰体积 >1000 mm³ 候选拒绝；每设备登记 mount-plane/service-direction/harness-entry/thermal-keepout/mass 五 owner；托盘抽取方向未定前保持 null | B1 §6-R12/R13（MDPI 2025 GRASP 阈值 https://www.mdpi.com/2226-4310/12/6/506 ）；GAP-IL-07（post_paper） | C3 CAD 阶段全量干涉核查（本阶段包络级声明） |

## 2. 载荷工况表（load_cases）

| case_id | 工况 | 载荷量级 | 作用点/路径 | source | 备注 |
|---|---|---|---|---|---|
| LC-1 | 发射段准静态（收拢构型） | ASSUMED 10 g 三轴；臂 4.6956 kg → 基座等效约 460 N 量级惯性力 | 臂收拢→臂基座 x=208.0→M3R→bridge→前法兰→主结构 | DB-R-15（ASSUMED）；DB-R-03/05/06/07 | 收拢构型质量特性 NOT_EVALUABLE（OI-3）；本阶段仅定性传力路径依据 |
| LC-2 | 在轨臂操作 | 基座扰动 19.20°；反复弯矩量值 UNKNOWN（关节力矩未建模） | 臂基座 | DB-R-17（sim_05，sha256_12 181eba2721e7） | 定性登记；CA-C 前舱隔振针对此工况 |
| LC-3 | 在轨捕获冲量 | 峰值 **60.9 N / 17.6 N·m**（max |J|=0.7749 N·s、max 力偶 0.2236 N·m·s，T_c=20 ms 半正弦） | 夹爪→臂链→臂基座 x=208.0→M3R→bridge→主结构 | DB-R-16（sim_06 CSV 机器复算，sha256_12 8cbad84b8ff6） | T_c PROVISIONAL；150 kg 碎片 @5°/s、v_app=0.03 m/s 为最坏工况 |
| LC-4 | 帆板展开 | 升级弹簧 ≥0.080 N·m 驱动力矩；端止动能量 ≤0.2356 J；铰 2 控制工况 0.24 J / 480 N / 48 N·m | 根铰 [-61,±143.15,0]、Hard_Stop、HDRM 2 站/翼 | DB-R-13/14（mechanism ledger sha256_12 11d585258597；02_PRODUCT_STRUCTURE LATCH_STOP） | 弹簧/锁扣选型 OPEN（GATE_C2 OI-2）；结构预留铰链舱 |
| LC-5 | 地面操作/维护 | 托盘抽拉、检修盖开合、压载配平垫片 | 各安装面 | B1 R5/R13 | 服务方向登记；托盘抽取方向 null（GAP-IL-07） |

## 3. 接口冻结清单（frozen_interface_register，只引用不修改）

| id | 接口 | 冻结值 | source（sha256_12） |
|---|---|---|---|
| IF-01 | 臂基座站位 | x=208.0 mm | 02_PRODUCT_STRUCTURE.yaml（0f9897ef4e41） |
| IF-02 | frame ODR-01 | T_SM=[185.25,0,0] mm + Ry90° | 02_PRODUCT_STRUCTURE.yaml（0f9897ef4e41） |
| IF-03 | M3R 组件 | 0.7619 kg；x-span [196.0,210.405]；4×M4 64×64 mm | 02_PRODUCT_STRUCTURE.yaml（0f9897ef4e41）；ICD V2（b610c9dee359） |
| IF-04 | load bridge | 0.7022 kg 6061-T6；x-span [185.25,196.0] | 02_PRODUCT_STRUCTURE.yaml（0f9897ef4e41） |
| IF-05 | 前法兰几何栈 | 站位 170.25 / 185.25 / 196.0 / 198.0 / 208.0 / 210.405 mm | 02_PRODUCT_STRUCTURE.yaml（0f9897ef4e41） |
| IF-06 | 帆板根铰轴 | [-61,±143.15,0]，方向 +x；展开目标 90° DESIGN_TARGET_CANDIDATE | 02_PRODUCT_STRUCTURE.yaml（0f9897ef4e41） |
| IF-07 | 帆板 HDRM | 每翼 2 站（native Base_1/Base_2 坐标见 DB-R-13）；与 ARM_HDRM 不同物 | 02_PRODUCT_STRUCTURE.yaml（0f9897ef4e41） |
| IF-08 | 帆板 Hard_Stop/LATCH | [-64..-58,±121..129,23..37]；端止动 ≤0.2356 J | 02_PRODUCT_STRUCTURE.yaml（0f9897ef4e41） |
| IF-09 | 帆板质量/机构账本 | 0.78 kg/翼（3.0 kg/m² candidate 未实测）；铰链刚度/力矩全 PROVISIONAL_DERIVED | SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json（d5b7dd16532f）；C2 定档（074f868ee762）——本包不碰帆板参数 |
| IF-10 | bus 外包络 | y/z ±113.15 mm（冻结 proxy 外表面）；340.5 mm 舱长口径（OI-6） | 02_PRODUCT_STRUCTURE.yaml（0f9897ef4e41） |
| IF-11 | 夹爪/接触合同 | DESIGN_CONTACT_MODEL_V1 BOUNDED_PROVISIONAL（法向刚度 1e6 N/m nominal）；as_built=null MEASUREMENT_PENDING | 10_GRIPPER_INTERFACE.yaml（6ead2d9dd081） |
| IF-12 | Route-C 外部线束 | HOLD；rated envelope 0_SAFE_SAMPLES；ODR-42 有界任务包络；P01–P13 物理输入 null/HOLD | 12_HARNESS_MISSION_ENVELOPE.yaml（6d5405e40c31）；CHECKPOINT_B_PHYSICAL_INPUT_MATRIX_V1.csv（a046340fcae8） |
| IF-13 | 帆板内部线束 | root loop 293.3 mm；min bend 25 mm；板间 flex-PCB 2 mm 级 | HARNESS_R2_FUNCTIONAL_GATES_V1.yaml（a47cea1c48fd） |
| IF-14 | 收拢支撑 slot | G07/G08/MID_SUPPORT 为 SLOT_STOW_SUPPORTS__CANDIDATE_REF，候选架构不得抢占 | 02_PRODUCT_STRUCTURE.yaml unresolved_component_slots（0f9897ef4e41） |

## 4. 登记差异与 UNKNOWN（诚实声明）

1. **P06 差异**：任务简报示例"P06=50 mm 动态弯曲半径 LOW 档"经全仓检索未在 Route-C registry 找到（P06 在 CHECKPOINT_B_PHYSICAL_INPUT_MATRIX_V1.csv 为 null/HOLD）。三候选线束通道按 MEASUREMENT_PENDING 声明，≥50 mm 控制半径仅作 ASSUMED 设计余量，禁止当作 registry 值引用。
2. **发射载荷**：仓内无权威发射载荷文件，LC-1 的 10 g 为准静态惯例 ASSUMED，不做强度校核（CHARTER §2 OUT）。
3. **臂操作弯矩**：sim_05 为动量级运动学反作用模型，关节力矩未建模，LC-2 臂基座反复弯矩量值 UNKNOWN。
4. **材料密度**：仅 al6061 2700 kg/m³ 有仓内权威（02_PRODUCT_STRUCTURE）；al7075 2810 / cfrp 1600 / steel 7800 / isolator 3000 kg/m³ 均 ASSUMED。
5. **结构质量口径**：候选结构质量替换 C1 的 EQ-SEC-STRUCT 1.0 kg CG 中性占位；主口径总质量因此偏离 ODR 登记值（CA-C 装压载时 +3.93 kg），按"新候选+差异声明"入账，不改 ODR 登记。
