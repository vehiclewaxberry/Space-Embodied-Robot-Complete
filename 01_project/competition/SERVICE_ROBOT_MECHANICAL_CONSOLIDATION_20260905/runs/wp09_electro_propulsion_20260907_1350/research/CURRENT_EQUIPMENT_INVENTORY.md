# WP09 当前设备与载板接口清单

本检查仅读取现有 JSON/CSV/源码和 STEP、SLDPRT 文件字节，执行来源哈希与 AABB 筛查；没有导入 CAD/OCC、没有操作 SolidWorks，也没有把 AABB 相交判为实际材料干涉。原冻结文件未修改。

清单覆盖 49 个设备舱、热接口、外部设备与线束支柱实例；另列 1 个筛查邻件。所列 STEP/原生文件共 78 个唯一路径，当前 SHA256 全部与 WP08 清单一致。三态所有所列实例的原始源、S 变换及包围盒一致。

逐实例完整路径、SHA256、4×4 T_S_local、尺寸、安装责任及三态 24 孔筛查见 [EQUIPMENT_INSTANCE_INVENTORY.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/results/EQUIPMENT_INSTANCE_INVENTORY.json>).

## 当前真实几何与预算所有权

| 设备域 | 预算箱尺寸 XYZ mm | 当前 S 中心 mm | 适配板 XYZ mm | 共享责任 |
|---|---|---|---|---|
| battery | [90, 170, 65] | [-114.0, 0.0, -63.15] | [98.0, 178.0, 2.0] | M07 |
| adcs_propulsion_allocation | [110, 160, 75] | [75.0, 0.0, -58.15] | [118.0, 168.0, 2.0] | M10/M15 |
| arm_drive | [85, 70, 40] | [-100.0, -48.0, 14.0] | [93.0, 78.0, 2.0] | M03/M08 |
| compute_communications | [90, 75, 40] | [10.0, -48.0, 14.0] | [98.0, 83.0, 2.0] | M08/M11 |
| power_distribution | [65, 70, 30] | [-100.0, 48.0, 9.0] | [73.0, 78.0, 2.0] | M06 |
| navigation_electronics | [70, 70, 40] | [10.0, 48.0, 14.0] | [78.0, 78.0, 2.0] | M10/M12 |

六个设备本体全部是 SIMPLIFIED_PROXY，六个接插件全部是 FUNCTIONAL_ENVELOPE；六块适配板和六块热垫具有名义实体。实体角色不代表实选、加工或实物验证。当前预算设备合计 6.55 kg；ADCS 与平移推进共用一个 3 kg、110×160×75 mm 预算箱，不能按模块重复质量，也不能称其为储箱、阀组、管路、推力器或轮组。

WP03 参数记录的设备中心在模型生成时 Z 加 2.5 mm；甲板/适配板/热垫的实际变换应取当前清单，禁止直接以原参数中心替换设备实例。当前甲板为 344×196.3×3 mm，下甲板 Z=[-101.15,-98.15]、上甲板 Z=[-11.5,-8.5]。载板厚 2 mm，热垫厚 0.5 mm。

WP07 电气合同仍为 DRAFT_BLOCKED_BY_MISSING_HARDWARE_INPUTS；M06/M07/M08/M09/M10/M11/M12/M15 的实选型号、供电范围、电流、接插件及引脚等仍 UNKNOWN，interface_complete=false、energization_allowed=false。WP07 板卡适配只做裸板边界+厚度对预算外盒的六种轴排列算术筛查，没有内腔、元件高度、支柱、插拔或线缆弯曲通过信用。

## 可以直接推进的最小连接

**优先：电池适配板到下甲板的四点连接。** 现有适配板孔轴为 S-Z，Ø3.4，世界 XY=(-152,±78)、(-76,±78)。适配板底面与下甲板顶面同为 Z=-98.15，金属叠层 2+3=5 mm。当前配对甲板孔和紧固件缺失；已有甲板边缘孔不是这四个孔。

适配板顶面 Z=-96.15，预算电池底面 Z=-95.65，中间只有热垫。常规圆柱螺钉头和垫圈会进入热垫/设备保留空间，不能直接叠加。可选真实沉头件后按目录几何形成局部齐平座，或改用具有可达外伸耳的载板。仅作几何估算：90°、入口 Ø6.2、通孔 Ø3.4 的锥深为 1.4 mm，2 mm 载板残余直壁厚 0.6 mm；这不是选型、强度或加工放行结论，必须由实际紧固件头型与公差反求。

先固定载板，再装热垫和设备；此举只闭合载板到甲板，不会自动闭合电池到载板。实际电池允许夹持面、孔系、绝缘与热接触仍需设备输入。

四孔下方 OD8×40 工具 AABB 除相接下甲板外没有其它候选邻件；该结果仅用于挑选下一最小 CAD 样例。根代理仍需在当前 STEP 上串行检验真实通孔、座面接触、Common、工具与装配过程以及原生冷重开。

## 不能复制的孔位与维修障碍

| 载板 | 孔位 | 下方 OD8×40 额外 AABB 候选 |
|---|---|---|
| battery | [[-152.0, -78.0], [-152.0, 78.0], [-76.0, -78.0], [-76.0, 78.0]] | 无额外候选 |
| adcs_propulsion_allocation | [[27.0, -73.0], [27.0, 73.0]] | RB_lower_beam_20 |
| adcs_propulsion_allocation | [[123.0, -73.0], [123.0, 73.0]] | 无额外候选 |
| arm_drive | [[-135.5, -76.0], [-135.5, -20.0]] | equipment_battery |
| arm_drive | [[-64.5, -76.0], [-64.5, -20.0]] | 无额外候选 |
| compute_communications | [[-28.0, -78.5], [-28.0, -17.5]] | 无额外候选 |
| compute_communications | [[48.0, -78.5], [48.0, -17.5]] | equipment_adcs_propulsion_allocation |
| power_distribution | [[-125.5, 20.0], [-125.5, 76.0], [-74.5, 20.0], [-74.5, 76.0]] | equipment_battery |
| navigation_electronics | [[-18.0, 20.0], [-18.0, 76.0]] | 无额外候选 |
| navigation_electronics | [[38.0, 20.0], [38.0, 76.0]] | equipment_adcs_propulsion_allocation |

推进共享载板的 X=27、Y=±73 孔轴正落在 RB_lower_beam_20 的 +X 边界；该梁 X=[13,27]、Z=[-107.15,-101.15]，顶面与下甲板底面一致。螺母/垫圈及工具都是该梁的真实 BRep 检验候选，需调整局部孔位/夹持结构或重新规划载体，不能把预算箱开孔后称为推进模块安装完成。

上甲板若保持上下设备同时安装，多组底侧工具包络遇下层设备预算箱。可先装载板后装下层设备，但这种工艺顺序并不等于设备在位时可维修。应明确实际拆装方向、临时拆件清单与接插件拔出路径。

现有载板四孔位于设备投影内部，也位于热垫边界内约 2 mm；上侧工具均遇本载板、热垫与预算设备，所以装配顺序必须显式登记。

## 端口保留空间

| 端口包络 | 邻接实体 | AABB 正交叠 XYZ mm |
|---|---|---|
| connector_compute_communications | trunk_clip_standoff_0 | [5.0, 3.5, 10.0] |
| connector_navigation_electronics | trunk_clip_standoff_0 | [5.0, 1.0, 10.0] |

这两个端口仅为功能包络；结论是端口保留空间与支柱的待验证冲突候选。优先联动重定位 0 号线束支柱或真实端口，不能把包络当成已选接插件，也不能仅凭此 AABB 数值判定真实材料干涉。

## 当前源文件使用规则

所有实例均从当前 WP08 清单所指原始 STEP 加其 T_S_local 开始；SLDPRT 路径也逐件保留。两件 lower_deck_angle_±1_1 来自 WP06 世界坐标 STEP，当前 T_S_local=I；不得再用 WP03 局部角梁重建、覆盖或重复平移。其余大多数设备与甲板仍是 WP05 的局部 STEP 加平移。

WP08 INTEGRATION_MANIFEST 的 PREPARED 状态是准备时快照；实际三态原生执行以 NATIVE_SERVICE、NATIVE_RELEASED 与 NATIVE_PARKING_RECOVERY_V2 及 DELIVERY_STATUS 为准。本清单不把准备状态当作当前未执行，也不从原生加载通过推导设备选型通过。

## 源码与合同入口

- [六项设备尺寸、未偏移中心与预算质量](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/design_parameters.json:114>)
- [甲板既有孔/缺口/热通孔](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/r01_design.py:14>)
- [现有甲板边缘连接的先装结构后设备顺序](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/r01_design.py:85>)
- [甲板与角梁安装](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/spacecraft_model.py:126>)
- [适配板孔、热垫、预算箱 Z+2.5 和接插件包络](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/spacecraft_model.py:157>)
- [线束支柱实体](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/spacecraft_model.py:175>)
- [热扩散板与相机/天线候选安装](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/spacecraft_model.py:190>)
- [电气 UNKNOWN 与未上电边界](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/ecad/ELECTRICAL_INTERFACE_CONTRACT.json:1>)
- [机电模块现状与缺失责任](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/MECHANICAL_MODULE_MATRIX.csv:7>)
- [历史裸板算术筛查范围](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/ELECTRICAL_MECHANICAL_FIT_SCREEN.json:1>)

没有真实设备内构、推进系统架构或整星电气完成信用。下一最小闭环由主代理选择目录紧固件并完成真实局部几何与验证；本文件仅提供有来源的输入与候选障碍。
