# ROUTE_C_PHYSICAL_INPUT_INVENTORY_V1 — Route-C 物理输入盘点（round0 交接 / AGENT-2）

- 生成时间：2026-08-23T16:41:22+08:00（宿主机本地时钟）
- 配套机器文件：`ROUTE_C_PHYSICAL_INPUT_INVENTORY_V1.json`（同目录，含全部 sha256 绑定）
- 性质：**只读盘点**。不选型、不建模、不闭合任何 MPI、不产生任何 release credit。等 MPI Gate。
- 授权基线：ODR-43（双坐标架显式桥接，T_PHYSICAL_TO_DYNAMIC 尚未建立）+ ODR-44（APPROVE_BOUNDED_DETAILED_DESIGN，MPI-01..08 全闭合前禁止 Route-C 独立版本 CAD 候选）。Mechanical Loop V5 Gate = HOLD（`next_stage_authorized=false`，`released_segments=0`）。
- ID 解释说明：仓库内不存在字面 "C2-01"/"C2-02"；本盘点将 C2-01 解释为最低产品输入登记册 MPI-01..MPI-08，C2-02 解释为拓扑候选集（C-A/C-B/C-C 为主控标签，与仓库 RC-A..RC-D 的映射为解释性映射，已逐行标注；**注意仓库 RC-C = dual-dress-pack-hybrid，与主控 C-C = mini cable-carrier hybrid 是不同概念，命名冲突已标记**）。

## 1. 物理能力量逐项盘点（13 项，全部 HOLD，0 项 AVAILABLE）

状态口径：AVAILABLE = 存在带单位、公差/不确定度和来源的受控项目可用值；HOLD = 未受控（null、仅目录候选、或被隔离的 Route-B seed）。null 绝不压成 0。

| ID | 量 | 单位 | current_value | 主要证据锚点 | required_for | 状态 |
|----|----|------|---------------|--------------|--------------|------|
| P01 | D_max_geometry_mm | mm | null | 几何容量前沿 null（UNKNOWN，向导/夹具/连接器体积、HN-02/HN-03、CAD 分支均缺席）；V5 gate LC5-09 复核 null | MPI-05, MPI-07 | HOLD |
| P02 | R_path_min_mm | mm | null | 同上前沿 null；参数空间 vendor_minimum_bend_radius selected_value=null（5..100 mm 仅为扫描轴） | MPI-06, MPI-07 | HOLD |
| P03 | deltaL_mm | mm | null | 前沿 null；长度裕度依赖尚不存在的物理路径 | MPI-05/07 + C4 长度谓词 | HOLD |
| P04 | carrier_travel_mm | mm | null | 前沿 null；各关节 carrier_travel physical_value=null；carrier_hard_stop_positions_mm=null | MPI-07（仅 C-B/C-C 需要） | HOLD |
| P05 | manufacturing_coordinates_mm | mm | null | `NULL_UNTIL_HN_02_HN_03_...`；HN-00 null、HN-01 仅拓扑参考、HN-02 仅 x 站、HN-03 几何未调和 | MPI-07 | HOLD |
| P06 | minimum_dynamic_bend_radius_mm | mm | null | MPI-06 = HOLD_UNKNOWN_DYNAMIC_CLASS；动态/静态级别在所有已审来源中未声明 | MPI-06 | HOLD |
| P07 | max_axial_extension_mm | mm | null | 全部已审 Route-C 工件无此字段；须先有物理路径与受控接口基准 | MPI-05/07/08 | HOLD |
| P08 | torsional_compliance | 未受控 | null | 安装结构模板 torsion_limit_per_length / torsional_restoring_moment_curve 未填；explicit_non_findings 第 1 条 | MPI-06 + C5 | HOLD |
| P09 | linear_density_g_per_m | g/m | null（安装束） | 安装结构模板 linear_mass 未填；MPI-05 HOLD_UNKNOWN | MPI-05 + C5 | HOLD |
| P10 | guide_friction_candidate | 未受控 | null | 参数空间 guide_material_and_wear_pair=null；Preliminary contract 列为开放输入 | MPI-07 + C6 | HOLD |
| P11 | guide_curvature | mm | null | 语义合同 physical_authority_boundary.guide_volumes_present=false；physical_guide_volumes_evaluated=0 | MPI-06/07 | HOLD |
| P12 | carrier_size_mm | mm | null | 无任何 carrier 几何字段；carrier 硬件 RFI 不存在 | MPI-07（仅 C-C 需要） | HOLD |
| P13 | clamp_spacing_mm | mm | null | 安装 ICD 模板 clamp_and_guide_station_schedule 未填；HN-02 y/z 未定义 | MPI-07 | HOLD |

### RFI shortlist 里有什么、缺什么（candidate_sources 摘要）

- **有（仅组件级目录候选，均非项目选定）**：单根导线/电缆目录值——TE Spec55 22AWG（OD 1.1 mm、4.27 g/m）、24AWG（OD 0.95 mm、2.78 g/m）；Glenair 963-080-24（OD max 7.24 mm、最小弯曲 31.75 mm 级别未声明、62.336 g/m 派生）、-26（6.05 mm、28.575 mm 级别未声明、51.837 g/m）；Gore SpaceWire 28AWG（OD max 7.5 mm、85.0 g/m max、弯曲 45.0 mm 动态级别未声明）；Axon P551259（OD max 6.5 mm、42.0 g/m max、25.0 mm **仅全静态**）；TE 55/9960-26（0.72 mm、1.81 g/m）；连接器族（Omnetics Power Micro-D 3A/触点、Nano-D 1A/触点；Glenair Micro-D 3A/触点、9 芯尾线连接器名义质量 1.6 g +10% 界；Axon Nano-D 约 2.0 g 族近似值）。RFI-D 工程样件线（RE2633/RET2633）已排除出飞行候选。
- **缺（shortlist 自身登记的 blocking unknowns）**：B601 电流/负载/协议/引脚图权威；安装后整束 OD/公差与椭圆化；动态弯/扭限制与寿命谱；恢复力/力矩随角度/速率/温度/循环曲线；精确整件质量与公差；选定结构的环境与弯后电气证据。8 个官方来源中**没有任何动态级弯曲半径、扭转数据、导向/载体/夹具硬件候选**。
- **被隔离（禁止继承）**：Route-B seed——OD 10.0 mm、R25 legacy、R30 终端要求值、cut length 4001.158 mm、诊断质量 0.68406762184 kg。

## 2. Route-B 负结果引用锚点（DOCUMENTED_NEGATIVE_RESULT）

| 锚点 | 路径 | sha256（前 16 位） | 逐字数字 |
|------|------|--------------------|----------|
| NRB-01 | `ecr_solar_array_r2/HARNESS_B601_FULL_FK_SWEEP_V1.json` | 10EA7420BD30CEBA… | FAIL；clearance −11.8667 mm（LHS_06, link5）；bend 1.081 mm（SWEEP_joint5_00）；pinch −11.3573 mm（HARDSTOP_joint4_lo, joint5） |
| NRB-02 | `ecr_solar_array_r2/HARNESS_B601_FULL_FK_SWEEP_V2.json` | DB86348B8276FB2D… | FAIL；clearance −11.9938 mm（SWEEP_joint2_09, link3）；bend 0.1 mm（CORNER_110000:span_link5）；pinch −11.9902 mm（HARDSTOP_joint4_hi, joint5） |
| NRB-03 | `ecr_solar_array_r2/ECR_SOLAR_ARRAY_R2_WORK_ORDER_V1.yaml` | 1FC4CC686F8257BD… | 行 155："V1 FAIL (collision -11.86 mm, bend 2.26 mm, pinch -11.83 mm)" |
| NRB-04 | `ecr_solar_array_r2/HARNESS_R2_FUNCTIONAL_GATES_V1.json` | E0B6468E08A0022D… | 早期 PROVISIONAL 范围 gate，**不是 Route-C 通过证据** |
| NRB-05 | `ecr_b601_harness_rated_envelope/07_release/B601_HARNESS_TERMINAL_GATE_V1.json` | D65BD945B3F0C930… | route_b=REJECTED；route_c=TRIGGERED；TMG-4 FAIL；mechanical_design=NOT_RELEASED |

> 数字口径警示：基线引用的 (−11.86 / 2.26 / −11.83) 来自 NRB-02 内 `redesign_history[0].worst` 与 NRB-03 行 155 的**圆整叙述值**，与 V1 机器头条值 (−11.8667 / 1.081 / −11.3573) 和 V2 机器头条值 (−11.9938 / 0.1 / −11.9902) 是三套不同数字；已全部逐字锚定，禁止合并或取平均。完整 64 位哈希见配套 JSON。

## 3. C2-02 三拓扑候选输入就绪度矩阵

矩阵口径：单元格 = 该输入组对此拓扑的需求级别与就绪状态；由于所有物理输入组均为 HOLD，三个候选均不可选。

| 输入组 | C-A joint-local Ω loops（≈仓库 RC-A） | C-B semi-captive dress-pack（≈仓库 RC-B） | C-C mini cable-carrier hybrid（仓库无精确对应） |
|--------|----------------------------------------|--------------------------------------------|--------------------------------------------------|
| P01 束 OD | REQUIRED__HOLD | REQUIRED__HOLD | REQUIRED__HOLD |
| P02 路径弯曲半径 | REQUIRED__HOLD | REQUIRED__HOLD | REQUIRED__HOLD |
| P03 长度/take-up | REQUIRED__HOLD | REQUIRED__HOLD | REQUIRED__HOLD |
| P04 载体行程 | 不需要 | 不需要 | REQUIRED__HOLD（无候选源） |
| P05 制造坐标 | REQUIRED__HOLD | REQUIRED__HOLD | REQUIRED__HOLD |
| P06 动态弯曲半径 | REQUIRED__HOLD | REQUIRED__HOLD | REQUIRED__HOLD |
| P07 轴向伸展 | REQUIRED__HOLD | REQUIRED__HOLD | REQUIRED__HOLD |
| P08 扭转柔顺 | REQUIRED__HOLD | REQUIRED__HOLD | REQUIRED__HOLD |
| P09 线密度 | REQUIRED__HOLD（仅组件目录候选） | 同左 | 同左 |
| P10 导向摩擦 | 拓扑级不需要（加衬垫则重开） | REQUIRED__HOLD（无候选源） | REQUIRED__HOLD（无候选源） |
| P11 导向曲率 | 拓扑级不需要（环半径由 P06 决定） | REQUIRED__HOLD（无物理导向体积） | REQUIRED__HOLD（同左） |
| P12 载体尺寸 | 不需要 | 不需要 | REQUIRED__HOLD（无候选源） |
| P13 夹具间距 | REQUIRED__HOLD | REQUIRED__HOLD | REQUIRED__HOLD |
| **就绪度** | **NOT_READY（0/9 受控）** | **NOT_READY（0/11 受控）** | **NOT_READY（0/13 受控）** |

## 4. MPI Gate PASS 前禁止动作 checklist

1. 禁止创建/修改任何 CAD/STEP/STL/GLB/FCStd 几何，含 Route-C 独立版本 CAD 候选（ODR-44；CAD Entry Gate prohibited_now）。
2. 禁止修改 accepted URDF（sha256 1BC2B748…71C164）与 Solar R2 STEP（21FF77B8…9915795）。
3. 禁止任何产品选型/采购释放声明；RFI shortlist 族永远不因目录数据变成项目选定件。
4. 禁止继承 Route-B seed：OD 10.0 mm、R25、R30、4001.158 mm、0.68406762184 kg。
5. 禁止把扫描轴诊断范围（D_bundle 4..20、R_vendor_min 5..100、keepout 0..30 mm）当作实测/选定/发布值。
6. 禁止 null→0、file-exists→PASS、多数投票裁决、把 PROVISIONAL 当 authority。
7. 禁止两坐标架取平均/合并/静默替换；禁止把 0.36889° 差值当随机不确定度；mass/CG/inertia/interface loads/CAD/collision 几何只能经唯一显式桥 T_PHYSICAL_TO_DYNAMIC 进入动力学系（桥尚未建立）。
8. 禁止凭 RFI 响应、vendor BOM/readme、URDF 局部运动学或任务段名称宣称 MPI 闭合。
9. 本轮禁止启动 FreeCAD/SolidWorks/Abaqus 等任何 CAD/FEA 进程。
10. 禁止进入 production dynamics、physical-contact RL、hardware motion；禁止宣称全程/任务/飞行鉴定通过。
11. 禁止把本盘点编辑成 PASS 记录，或在无受控 owner 来源时回填任何 null 量。

## 5. 与基线的差异/边界记录

- 负结果三套数字口径差异（见 §2 警示）。
- 拓扑命名冲突：仓库 RC-C ≠ 主控 C-C；映射为解释性。
- `ROUTE_C_PRELIMINARY_DESIGN_CONTRACT_V1` 仅有 .json，无 .yaml 同名片。
- `02_mpi_evidence_audit/` 实为 5 个机器 JSON + 5 个未填 owner 模板；4 件核心机器件已全读（authority contract 内容经 validation 的 package_hashes 绑定复核：2F55B80F…/73D9D0A1…/348C9D60…/A65B8A4F…）。
- V2 scope_notes 记载 mount  supersession（x=208.0 mm、绕 +X_S 25° 取代简化 185.25+Ry90）——与 ODR-43 双架语义同源，和接管基线一致。
- HARNESS_ROUTING_V1.yaml 的 HN-01/02/03 声明坐标仅为拓扑参考（通道不是物理空腔），不是制造坐标。

## 6. 汇总

13 项物理能力量：0 AVAILABLE / 13 HOLD；MPI 0/8 受控；负结果锚点 5 条（哈希已复核与 gate 钉值一致）；拓扑候选 3 个、0 个就绪；编造数字 0；null 压 0 次数 0。`gate_state = HOLD__AWAITING_MPI_GATE`，`next_stage_authorized = false`。
