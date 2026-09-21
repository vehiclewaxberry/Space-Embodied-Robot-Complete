# R6 独立安装与接口输入审查

本报告仅审查本轮布局的来源、对象和接口边界；尚未审查 R6 完成装配。可继续数字设计，制造、上电和飞行放行保持 HOLD。

只读检查 262/262；源锁和完整数据见 `INSTALLATION_INTAKE_REVIEW.json`。本次没有修改旧包、ECAD 或 CAD。

## 可进入本轮数字安装的对象

- MAIN：可基于 V36 实际 PCB 的元件、孔位和电气身份建立数字装配；R5 导出 26 个叶体只覆盖 23/35 个逻辑物理部件，C201 为本体和两条引脚。缺失模型须补齐并区分库模型、OEM 目录包络和保守占位。
- STOP、AUX：受检 PCB 分别为 90×70×1.6 mm、60×70×1.6 mm，存在原理图/焊盘/网络来源；R4 没有识别到对应 PCB 源路径叶实例。如本轮纳入，仍需单独导出、映射、支撑和三态检查。
- 接口板热桥：允许 4 mm 铝块加 0.5 mm 名义绝缘垫的数字候选。一种堆叠为铝块 z=-6…-2 mm、绝缘垫 z=-2…-1.5 mm，下接现有 TIM 顶面、上接板底；须避开四支柱/螺栓及板底需绝缘的实际区域，受压厚度和公差另算。R4 接口板仍为功能包络，实际热源、热阻、耐压和接触压力为 UNKNOWN；因此只认几何安装信用。
- V30 支架、端子和大件可作有来源参考。当前 R202 为 0.5 mΩ，最大本体高度 3.15 mm；旧 V30 本体高 3.81 mm 不可沿用为当前型号。布置时须保留 Q201、Kelvin 分流器和端子的电气相对关系，并恢复被分离的导线路径。

## 未布板更新边界

45 项历史更新中，下列 39 项不属于三张已审 PCB：

U303, U304, C204, C205, C206, C208, C207, C304, C308, C209, C210, C301, C302, C303, C305, C306, R301, R302, R306, R309, R303, R308, R304, R307, R313, R316, R319, R310, R311, R314, R317, R312, R315, R318, R305, J200, J201, J202, J203。

另有 U301 仅恢复了器件型号，仍不属于三板。249 个符号中共 85 个不在三板，其中含模块、边界和待布局电路；不能把 39 理解为整套系统仅剩 39 个物理器件。R305 的 665k+11k 串联及新中点未实施。

## 推进预留区与真值来源

下表由 R4 `inputs/NATIVE_ASSEMBLY_PLAN.json` 的最终实例变换与 R2 `inputs/SOURCE_LOCAL_BOUNDS.json` 的源包围盒计算；对应 STEP SHA 已逐项复核。坐标为 S 系、单位 mm。包围盒仅供布局筛选，不能代替精确布尔体、装配可达性或 OEM 羽流边界。

| 对象 | S 系最小点 → 最大点 | 对象性质 |
|---|---|---|
| MIPS_CRADLE_B | [136.0, -57.0, -98.15] → [170.0, 57.0, -2.15] | PHYSICAL_GEOMETRY |
| MIPS_OEM_MAX_ENVELOPE | [140.0, -44.5008, -94.15] → [170.0, 44.5008, -5.1484] | FUNCTIONAL_ENVELOPE |
| equipment_adcs_propulsion_allocation | [20.0, -80.0, -95.65] → [130.0, 80.0, -20.65] | SIMPLIFIED_PROXY |
| adapter_adcs_propulsion_allocation | [16.0, -84.0, -98.15] → [134.0, 84.0, -96.15] | PHYSICAL_GEOMETRY |
| connector_adcs_propulsion_allocation | [66.0, -88.0, -89.15] → [84.0, -80.0, -79.15] | FUNCTIONAL_ENVELOPE |
| thermal_interface_adcs_propulsion_allocation | [25.0, -75.0, -96.15] → [125.0, 75.0, -95.65] | PHYSICAL_GEOMETRY |
| PROP_PWR_ROUTE | [-60.0, 43.0226, -69.9774] → [148.9774, 73.9774, 63.9774] | FUNCTIONAL_ENVELOPE |
| PROP_DATA_ROUTE | [45.0, 29.0226, -45.0] → [144.9774, 60.9774, 63.9774] | FUNCTIONAL_ENVELOPE |
| P60_REFERENCE_B | [-151.0, -2.0, 57.5] → [-55.0, 94.0, 86.5] | FUNCTIONAL_ENVELOPE |
| P60_TRAY_B | [-158.0, -13.0, 53.0] → [-44.0, 98.0, 55.0] | PHYSICAL_GEOMETRY |

保留旧推进/姿控分配盒、MIPS 预留、支架、端子/数据走廊和工具/拔插空间。它们不是已选 OEM 整机。喷口坐标、受力方向、羽流角、禁喷角和捕后质心均未绑定；不得从盒角或箭头补造这些参数。太阳翼、机械臂、捕获目标、导航视场及敏感热/光学表面的羽流排除域需由后续 ICD 和任务姿态确定。

功能线束来源：`implementation/mechanical/BATTERY_PROPULSION_ROUTING.json`。PROP_PWR 起点 [-60,69,45]，末端 [144,48,-65]；PROP_DATA 起点 [45,34,59]，末端 [140,56,-45]。两束 OD6、中心线 R21，水平 y=34/48、z=59，双孔夹具 x65…95/y29…53/z52…66。actual_endpoint_binding=false；无下料长度或 OEM 针脚信用。

目录级 CPOD 接口来源：`wp09_interfaces_20260907_1525/system_completion/propulsion/resume_20260908/PROPULSION_INTERFACE_CONTRACT.json`。孔螺纹为 #4-40 UNC-2B，直接 M3 安装已拒收；精确孔数/孔位/深度/扭矩仍 null。目录供电 9–12.6 V，候选 P60 为 12 V，具体供货和浪涌未绑定；推进侧连接器、针号、RS422 极性和机壳屏蔽连接均 null。不能因目录双机 5 W 将所有并发/预热电流视为已知。

## 9 项现行 OEM 缺口

精确列表来自 `implementation/results/propulsion_trade_20260917/PROPULSION_TRADE_MATRIX_20260917.json` 的 `oem_icd_missing_fields`；同目录 MD 归并成 8 条叙述。选型和任务预算均未闭合。原贸易 R1 只有推力下限，不能把全 PASS 解释为最小冲量、羽流和安装均已适用。

1. CPOD8 command_min_width_s
2. CPOD8 two_jet_concurrency_allowed_by_command_ICD
3. Dawn B1/B20 official PDF datasheet Isp and power breakdown
4. HPGP 1N pulsed-mode Isp at low-duty-cycle equivalent of 12 mN class
5. EPSS C1K dry mass and dual-module concurrency ICD
6. Moog module total impulse, concurrency, flight heritage
7. PBR-50 Isp, total impulse, dry mass, 12U mounting
8. OEM mating hole definitions (screen OEM_mating_holes_defined=false still open)
9. plume impingement / post-capture CoM shift effect on l_T=0.17 m assumption

## 下一步 12 个工程工作条目

逐条继承 R2 `docs/PROPULSION_GAP_ACTIONS.csv`；以下不是新增批准或已完成声明。

| ID / 优先级 | 内容 | 输入/动作 | 验收 |
|---|---|---|---|
| PA01 / P0 | 轮组型号与轴线 | 冻结4个实物ID/修订版、轮轴S、扭矩—轮速—功耗、动量上下界与当前轮速 | 轴线矩阵、动量多面体、每轮失效及真实能力通过独立复算 |
| PA02 / P0 | 喷口位置/方向/通道 | 逐喷口ID、孔系、喷口位置S、航天器受力方向、喷流方向、安装T、通道与控制版本 | 实物/CAD/通道唯一绑定；矩阵秩、正推力纯轴能力和任务裕量均通过 |
| PA03 / P0 | 组合体质量与COM | 空星与150kg/22kg目标各任务姿态的质量COM惯量及可信区间；不混旧URDF | 捕前/后状态账本与外部作用参考点一致；任务角冲量独立重算 |
| PA04 / P0 | 阀脉冲与并发 | 最小/最大命令宽度、延迟、重复率、on/off推力曲线、压力/温度范围及通道并发矩阵 | 所需序列经OEM模型/实测验证，电源/流量/热并发均满足 |
| PA05 / P0 | 轮组5V支路 | 确版DC/DC、稳态/启动/峰值/回灌、支路保护、返回线、线规与端子针号 | 最坏并发电压/电流/热与保护选择性验证；不可直接接24V |
| PA06 / P0 | 推进阀点火预热负载 | 独立驱动/电源、ARM/INHIBIT、通信/健康反馈、瞬态/预热/点火/回流电气合同 | 逐针和状态时序核验；无未知上电安全额定项 |
| PA07 / P1 | 喷流与安装共存 | OEM全尺寸、禁喷角/污染/温度/冲击域、阀管路布局、支架与隔热接口 | 三态+任务路径+捕后目标无不允许几何/喷流/视场干扰 |
| PA08 / P1 | 全任务冲量预算 | 明确每喷口/合计F和力臂；逐阶段Δv/角冲量/重试/撤退/卸载/结束处置 | 压力/EOL/duty约束后仍有预注册余量，不合并0.085与0.17m假设 |
| PA09 / P0 | 故障检测隔离与退避 | 卡关/卡开/轮失效/通信陈旧/欠压的检测与隔离、剩余能力、被动安全走廊 | 每种故障离线/电子模拟注入，阀卡开上游隔离与退避有效 |
| PA10 / P1 | 供给系统和储箱 | OEM工作压力/温度、容器与阀管路合格资料、干湿质量、固定/热与晃动合同 | 接口/载荷/热/流量及压力系统专门验收 |
| PA11 / P1 | 状态与模式合同 | 姿态/相对位姿/轮速/质量状态时间戳、阈值与滞回、抓捕静默窗口/撤退规则 | 未知/陈旧不放行；各模式转换和失败状态有可复现实验 |
| PA12 / P1 | 地面与飞行分层验收 | 被动装配→逐针→限能负载→电子模拟故障→受限运动；飞行另环境/任务资格 | 每级同版源与仪器证据、预注册限值、独立复验 |

R6 完成后独立复核：来源/材料标签、安装变换、三态增量布尔结果、接触白名单、导线连续性、保留区、固有端子/螺钉工具空间、原生冷打开及旧源哈希。完整五维评审随最终装配证据补充，不提前授予整星完成信用。
