# 原生装配、资产接入与产品链只读审计

审计日期：2026-09-05。结论：已有多代真实 CAD 零件和子装配；**当前完整服务星总装的身份一致性、部件完整性与配置验证仍为 UNKNOWN / HOLD**。这既不等于机械设计未开始，也不等于可以只改外形获得完整机械系统。

本报告仅静态读文件、FCStd ZIP/XML、已有原生验证收据及哈希，不调用 SolidWorks、FreeCAD GUI/内核，不重算碰撞、优化、FEA 或动力学。所有输出写于本审计目录，未写入原始 CAD、历史 Gate 或 CURRENT 指针。

## 1. 应查看哪一个装配

不存在本轮能够证明“打开后即可视为当前完整、已验证整星”的单一文件。以下是有证据的查看候选，**本轮没有冷开它们**。

| 用途 | 完整文件路径 | 配置或身份 | 可确认范围与限制 |
|---|---|---|---|
| R2 发布目录锁定的主几何 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\03_MASTER_GEOMETRY.FCStd` | XML 根对象 `DESIGN_FREEZE_ASSEMBLY_V1`；产品树默认 `DEPLOYED_NOMINAL__ARM_TASK_READY` | 静态可读 71 对象、7 个内部 App::Link；是受锁定主几何，但内容仅为有限中性冻结链 |
| R2 相邻 STEP | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\04_MASTER_GEOMETRY.step` | 同一冻结默认装配导出 | 发布哈希匹配；不是新 Route-C / F4R1 / Solar R2 已集成的证明 |
| 历史较完整 SW 总装 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\03_native_cad\F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM` | 历史报告列 `STOWED_ENGINEERING_CANDIDATE`、`SOLAR_DEPLOY_ARM_LOCKED`、`DEPLOYED_NOMINAL`、`L_FAIL`、`R_FAIL`、`DEPLOY_FAILED_BOTH`、`PARTIAL`、`SERVICE` 八个被检查配置 | 已有 82 组件/配置与历史引用记录；当前磁盘路径存在，但旧复制清单的顶装哈希已不一致，不能继承当时的当前性 |
| F3R1 原生前代 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\03_native_cad\F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM` | `V3_CONFIGURED`，历史八配置体系 | lineage 查看入口，非当前 R2 配置权威 |
| 历史 SW 中性完整导入 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5R_FREECAD_OPERATIONAL_CLOSURE_20260820\03_fcstd\FC02B_FULL_SYSTEM_REPAIRED.FCStd` | 457 个 Part::Feature 的单文档导入；无原生装配关节树 | ZIP/XML 可读；已有冷开收据，但收据裁决是 `FC02B_BREP_UNREPAIRED_HOLD`，6/457 无效 B-rep 未修复；文件名 REPAIRED 不表示修复成功 |
| V5 最近发现的顶装暂存文件 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE\03_top_assembly\SEI_MECH_B601_V5_NATIVE_BASELINE__LOOP1E_STAGING_20260820T140708.895028Z_PID31664.SLDASM` | staging，完整配置健康 UNKNOWN | 存在性/哈希已记录；同目录还有 20260813 两个 staging。较晚文件名不能成为权威证据 |

R2 的 `08_CONFIGURATION_LIBRARY.yaml` 选中质量模型配置 `C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT`，而主 FCStd 来自 `DESIGN_FREEZE_ASSEMBLY_V1`。质量配置引用和原生活动配置必须分别登记，不能仅据二者同时位于 R2 目录推断为同一完整硬件系统。

本报告的文件实际哈希、已保存收据哈希、是否匹配见 [assets_file_identity_audit.csv](assets_file_identity_audit.csv)。静态对象和链接分别见 [assets_fcstd_objects.csv](assets_fcstd_objects.csv)、[assets_fcstd_links.csv](assets_fcstd_links.csv)。

## 2. R2 主几何实际装了什么

XML 直接确认 7 个 App::Link，全部 `file=""`、内部目标存在；并未发现引用失效的外部 App::Link。这是静态引用结构成立，不是 CAD 内核重建成功或机械接触成立。

| 活动实例 | 实际内容/来源 | 与当前目标的差距 |
|---|---|---|
| `INST_BUS_12U_CORE` | 6 解析实体组成的整星包络代理，来源 `model_specs_v0.json` | 无内部结构/独立闭合面板/设备孔/线束通道；中性母线长度 340.5 mm 与旧原生结构 366.0 mm 未统一 |
| `INST_SOLAR_ARRAY_LEFT_DEPLOYED` / `RIGHT` | `SRC_SOLAR_ARRAY_*__DEPLOYED_PLATE_PROXY` | `11_SOLAR_R2_MECHANISM.yaml` 另锁定真实 Solar R2 候选；该候选并未被这些主装配实例消费 |
| `INST_B601_ARM_CORE_Q0` | `SRC_B601_ARM_CORE_Q0__FRAME_AXIS_WITNESS` | 18 个极小实体，整体体积约 817.65 mm³，仅坐标/轴见证，不是 accepted URDF 的连杆外形 |
| `INST_M3R_INTERFACE_ASSEMBLY` | 两级转接件 2-solid 复合体 | 几何存在；实配、紧固、公差和逐级 solid 在主复合体内的归属核查仍未闭合 |
| `INST_GRIPPER_R1_PALM` | R1 掌体 | 双指仍为 unresolved 槽位；不能视为完整两指抓手 |
| `INST_SPACECRAFT_LOAD_BRIDGE` | M6 中性承载桥候选 | 与旧原生 Load_Bridge_Left/Right 不是同一件；母线锚固、公差、紧固和承载连续性 HOLD |

主装配中另有隐藏的相机候选、六类 unresolved 槽位，但没有 Route-C V9F、F4R1 内部结构、真实 arm restraint/support、完整 Solar R2 的活动实例。

以上同时得到 R2 `02_PRODUCT_STRUCTURE.yaml` 与主 FCStd XML 的支持。前者本身保留旧 M7 生成时间及限定范围；后续独立候选不会自动写回这一主几何。

## 3. A3.4 八项“缺失”的重新分类

以下分类针对明确的文件/配置范围。完整三栏矩阵见 [02_ASSET_INTEGRATION_VERIFICATION.csv](02_ASSET_INTEGRATION_VERIFICATION.csv)。**A3 `missing_geometry=true` 仍是原始包的加载事实，未被本审计改写；它不再被解释为整个工程库无设计。**

| A3 槽位 | 找到的资产 | 审计分类与当前限制 |
|---|---|---|
| `M3R_STAGE_A_RING` | `M3R_STAGE_A_REVB_WORKING.FCStd/.step`；Stage B 同目录；R2 主装配 M3R 复合体 | 已存在且接入 R2 默认中性主装配；未加载 A3；不是新收拢姿态集成证明 |
| `M3R_STAGE_B_DIFFUSION` | `M3R_STAGE_B_REVB2_WORKING.FCStd/.step` | 同上。独立历史单件验证给出 `PASS_WORKING_GEOMETRY_EQUIVALENT_TO_PINNED_REVB2`，实配未执行 |
| `HDRM_ROOT` | V5 `ARM_HDRM_FUNCTIONAL_ENVELOPE.SLDASM` 及承载底座/滑块/硬止挡/传感器与连接器支架 | 已存在但未接入 R2/A3；generic ARM_HDRM 与 root 槽位身份尚未绑定，不能视为完成选型 |
| `HDRM_DISTAL` | 未找到独立映射到 A3 distal 槽位的第二套释放器；有 generic ARM_HDRM 与功能账本 | 在本次检索范围内未找到精确槽位资产；不能把太阳翼 HDRM 或相同 generic 候选再算为第二套 |
| `STOW_SADDLE_A` | V5 `G07_PRIMARY_SUPPORT_V2.SLDASM`，body/carrier/PTFE pad 分件 | 已存在但未接入；A 槽位与 G07 的一一身份/安装映射仍 UNKNOWN |
| `STOW_SADDLE_B` | V5 `G08_PRIMARY_SUPPORT_V2.SLDASM`；另有 MID 备份支承 | 已存在但未接入；旧 B51/G08 接触负结果需保留；B 槽位与 G08 不能凭名字自动等同 |
| `HARNESS_TRUNK` | Route-C V9F FCStd/STEP、9 段中心线、夹持导向件与增量质量 | 已存在但未接入 R2/A3；V9F 原始收据仅 `SOURCE_ONLY_DESIGN_CANDIDATE__NO_GATE_PASS__NO_RELEASE_CREDIT` |
| `CONNECTOR_SET` | V9F CN-BUS/CN-BASE 板、CN-WR-D1/P1 风格候选块；V5 connector mount | 有候选/占位几何；实际供应商型号、插拔/锁紧/防呆/应力释放与空间仍未绑定 |

M3R 单件文件所在目录：`F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_MECHANICAL_DETAILED_DESIGN_V1\06_parameterized_parts\m3r\`。

V5 子装配所在目录：`F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE\02_native_subassemblies\`。G07/G08/MID 的历史结果均为 `V5_NATIVE_SUBASSEMBLY_MATES_AND_COLD_REOPEN_PASS`，HDRM 为 `V5_LOOP1D1_NATIVE_FUNCTIONAL_ASSEMBLY_PASS`；此次相关 CAD 收据 pin 均与磁盘匹配。这些局部历史证据证明已有设计资产，不能自动升级成当前整星可用。

V5 HDRM 功能候选明确 `interference_closure_claimed=false`、`flight_qualification_claimed=false`。M7 HDRM 工程包还有装配图样、热环境、冲击、寿命、发射载荷未闭合项；候选 50 N 预紧在其声明的 5g 敏感性计算下比值约 0.217，不能当发射约束完成。相关历史数字仅转述，不在本轮重算。

## 4. 支承历史负结果和版本边界

不能沿用“所有鞍座都是空壳”的总括，也不能沿用“既然画过就已支撑”的反向判断。已有至少三种不同表示：旧 native cradle、V4 中性候选、V5 原生功能子装配；M7/R2 活动中性链则根本没装支承。

`F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1\wp12_secondary_structure_adjudication\SECONDARY_STRUCTURE_INTERFERENCE_RULING_V1.json` 纠正了旧支承对偶面口径：旧鞍座有 3 mm 凹槽，单一“塔顶高度”不能代表接触平面；旧 B51 收拢网格对 G08 存在约 2.254534 mm 正穿入；G07/MID 未见正公共体积。这个负结果的范围是旧 B51/native 几何，不能用于证明 accepted meshes 在 A3 新姿态也穿入或安全。

## 5. 太阳翼、线束与内部布局的集成分叉

Solar R2 候选 `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1\ecr_solar_array_r2\SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd` 静态包含 27 对象、23 Part::Feature；主 FCStd 仍链接两块 v0 平板代理。因此“冻结了 Solar R2”与“当前顶装装入了 Solar R2”是不同事实。

Route-C V9F 文件 `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\route_c\B601_ROUTE_C_GUIDED_DRESS_PACK_V9F.FCStd` 静态包含 138 对象（130 Part::Feature、7 Mesh::Feature、1 group）。这不是只有纸面路由；也不是完整机构工程验证。目录内早期 `ROUTE_C_MISSION_COVERAGE_GATE_V1.json` 为 `FAIL_DOCUMENTED`，source_bindings 指向 V1 中心线/夹持表，不能用这一失败或它的任一局部量为 V9F 作最终裁决；后续 M01 操作资产亦不自动构成原生总装。主报告另追后续机器 Gate。

F4R1 最新找到的结构候选 `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1\70_c3_cad\CA_A_R1_INTERNAL_STRUCTURE_V2.FCStd` 静态为 **32 个 Part::Feature**。V2 build receipt 解析 40 设备行用于布局检查，结构质量 **1244.9 g**；这并非 FCStd 已包含 40 个真实设备。V1 `MASS_CG_REPORT_V1.json` 的值不得替代 V2 收据。

V2 C3 Gate 为 `PASS_WITH_DECLARED_OPEN_ITEM`、`DESIGN_RESEARCH_CANDIDATE`。其干涉报告以 **1000 mm³** 为 VIOLATION 阈值，较小交叠可登记 CONTACT_NOTE，同时有安装接触/体积所有权/包络占用等分类。因此 `violation_count=0` 不等于绝对零干涉，不能当当前整星无碰撞证明；收拢 CG、墙穿支架路径等仍 deferred。V2 保持 R2 冻结 STEP 不变，反而直接说明它是新增候选分支，没有替换入主装配。

F4R1 设备清单 `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1\50_c1_layout\EQUIPMENT_LIST_V1.yaml` 已给 FRZ/EQ 两类行、质量/包络/位置/安装面/来源及 UNKNOWN 项。航电布局不是未做；但设备盒、冻结参考、供电未知与真实设备/采购型号/安装孔/维护空间验证仍须分开。

## 6. 原生引用、身份和现有验证强度

静态核验 F3R2 `F3R2_COMPONENT_INVENTORY.csv` 的 **656 行（8 × 82）**，含 **74 个不同文件路径，全部在当前磁盘存在**。这是已有报告路径的存在性检查；未调用 SW，因此不能报告当前引用实际解析率、当前配置抑制状态或配合健康。

旧复制凭据含 73 个 source/destination 配对，原 source 全部可找到；对 destination 的历史哈希比较发现 **8 个装配文件已变化**，包括 F3R2 顶装、母线顶装、主结构、设备板、臂根承载、支承、左右翼根子装配。变化可能有合法后续原因，本轮不认定污染；但旧复制等价/冷开证明不能未经后续收据绑定用于当前文件。

详见 [assets_sw_reference_disk_audit.csv](assets_sw_reference_disk_audit.csv)。它逐行给完整来源路径、配置、历史 referenced_config、当前存在性和哈希，并标为 `HISTORICAL_NATIVE_REFERENCE_REPORT_NOT_CURRENT_OPEN`。

R2 `01_BASELINE_MANIFEST.json` 列表中所有 22 个非本文件成员当前均匹配；其本文件的自引用摘要不同，且清单文本已声明避免自引用，该现象单列而不解释为核心 CAD 污染。发布 SHA 表/整体保护源的审计由主报告合并。

## 7. 图纸、BOM、承载和制造链

已有设计层材料，不应说“没有 BOM/图纸”。M7 `wp9_release_package` 有 8 条图纸/表索引、BOM V3、装配程序、检验计划和验证矩阵；M3R 还有紧固件与公差分配。所有 8 条图纸索引的 `manufacturing_use` 均为 `PROHIBITED`，BOM 元数据明确 `NONE_NOT_A_PROCUREMENT_BOM`。这是工程候选链，尚非制造发布或试验验收链。

当前必须分别补齐两种载荷路径：收拢发射时，臂保持点/支承/HDRM → 所连接主结构 → 分离/发射界面；展开操作时，臂根安装接口 → M3R 两级/桥接件 → 母线锚固。实际载荷分流与连接拓扑待同配置绑定。R2 主几何仅证明若干实体放置，不能代替对偶面、定位、紧固、预紧、实际材料/工艺、公差以及检验记录。先对齐现有资产身份可避免重复建模，但不免除缺失的集成和验证工作。

## 8. 换线复用与必须重验证

可以保留并复用：accepted URDF/mesh 的明确源身份、M3R 单件几何与参数表、V5 支承/HDRM 功能子件、Solar R2 机构资产、Route-C 导向与中心线候选、F4R1 设备布局/32 结构件候选、BOM/图纸/检验模板。复用表示可以作为输入或候选，不携带当前整星 PASS。

若改变母线尺寸、安装转角、收拢姿态、支承点、线束或翼根构型，应重新绑定并验证：产品身份与总装引用、外包络与干涉、保持/释放/展开序列、连接器可达性、线束运动域、接触与承载连续性、整星质量/CG/惯量、适用的结构/柔性/控制模型和测量输入。部分局部单件证据可以继续有效，但是否可继承必须在同一配置/版本/载荷条件下逐项判断。

**本审计停止于“已有资产—当前集成—当前验证”的对应关系，不授权 Mode B，不启动设计或仿真。**
