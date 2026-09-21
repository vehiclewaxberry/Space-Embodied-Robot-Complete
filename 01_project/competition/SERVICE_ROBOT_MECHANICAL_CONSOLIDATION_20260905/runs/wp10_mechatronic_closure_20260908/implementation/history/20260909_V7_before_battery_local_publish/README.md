# WP10 当前候选：CHB 底部与双侧壁实际导热核心

已将厂家CHB实体改装到底部短台座，生成两根与底板一体的L形导热臂、侧壁接耳、两片TIM及8枚新增螺钉。**当前38实例/38实体的SolidWorks导热核心已保存并独立冷读；C09 CHB跨内核体积比较仍OPEN，整机机电详细设计未完成。** 894实例是同一候选的三个状态源表，尚非完整原生整星装配。

[统一查看](REVIEW.html) · [旋转查看导热核心](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical%2Fthermal_core.step.py) · [当前整舱改件](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical%2Ffixed_heat_bay.step.py) · [SolidWorks组件包](mechanical/WP10_THERMAL_CORE_SOLIDWORKS.zip) · [导热核心STEP](mechanical/thermal_core.step) · [全部当前增量包](WP10_IMPLEMENTATION_DELTA.zip)

CHB基面S(-25,0,-96.15)mm，针脚朝+Z；58×62mm台座面z=-96.353，TSP1800ST名义厚0.203mm（未验证压缩厚度）。底板、两根58mm宽的L臂为单一实体；两侧58×24mm接耳与冷指间由0.203mm项目裁切TIM填实。每侧净TIM接触面积1360.191374mm²，CHB双侧TIM接触面积3234.482749mm²。甲板实际开60×96窗口，原六组底板夹紧点保留。详见[设计参数](thermal/BOTTOM_RADIATOR_MOUNT.json)及[设计说明](mechanical/CHB_BOTTOM_COLD_PATH_BRIEF.md)。

三处TIM同时选为TSP1800ST：25psi典型面积热阻0.28K·in²/W，已含两个接触界面；不额外叠加TIM的t/kA。它仍是绝缘材料，但典型击穿由原TSP1600S的5500Vac降到3000Vac，且贯穿的金属螺钉形成电气旁路，组件绝缘未经证明。目标25psi对应CHB总平均承压力557.524N、每侧234.455N，实际压强分布、压缩厚度和预紧未验证。厂家放气TML0.23%/CVCM0.05%是材料筛选数据。[厂家资料与选择](sources/COLD_TIM_SELECTION.json)。

新增螺钉复用Würth4123 53 20公开尺寸，CAD为简化螺纹名义重建体。CHB名义伸入2mm，侧壁冷指3.147mm/孔深5mm；有效啮合、压紧、预紧、防松及公差仍未验收。厂家STEP孔距48.26与图纸48.3mm差异保留。CAD旧ID U202_CHB现明确绑定实际电气位号U203，无重复位号。

底部净平面辐射面积0.06676970m²，底板及一体臂按2700kg/m³估算质量2.100982kg；未将其冒充整星质量闭环。旧底部V6及其24实例原生文件保留历史，当前以38实例导热核心为准。

本次证据：24项冷路径接触/定位/螺钉检查、48项底部几何检查；三个状态各642对改件邻域精确STEP检查无正体积穿透与未知。原六夹紧点36个局部工具域通过；新增24个工具域中16个可用，8个折叠侧壁域被帆板遮挡，已明确展开预装顺序。以上不覆盖完整插入轨迹、连续动作、公差及未改件之间的全配对。

原生SolidWorks2024导热核心含14个SLDPRT及38个固定实例；各零件保存、关闭、重开，装配另启会话冷读38实体/0曲面、显式坐标变换与14个本地依赖。源STEP、原生SHA与三态源表绑定。目录迁移后的冷读、运动配合及894整星原生集成未执行。见[原生回执](results/NATIVE_COLD_COLD.json)。

C09 CHB的SW体积44063.953594mm³，与GK参考44064.004787mm³相差1.16178×10⁻⁶，超过未改变的1×10⁻⁶相对判据；原始失败和积分方法差异均保留，13件其它零件维持原体积检查。文件读回、实体数和定位通过不能替代源形状等价；STEP接触与干涉结论未自动授予SW C09。该体积不用于整星质量预算。[积分诊断](results/COLD_SOURCE_MATCH_DIAGNOSTIC.json) · [STEP序列化筛查及精度边界](results/THERMAL_CORE_SOURCE_MATCH.json)。

补充只读复算显式使用SolidWorks IMassProperty2，设置SI单位并分别在低、中、高精度重算；三档均返回44063.953594mm³，最高精度比较仍未通过。原生文件SHA未改变，不能将异常归因于“只需提高精度”；也不能单凭体积差异认定几何损坏。[三档精度实际回执](results/NATIVE_CHB_ACCURACY_SCREEN.json) · [当前源绑定复核及限定](results/NATIVE_CHB_ACCURACY_QUALIFICATION.json)。

热模型改为实际三面非等温网络：保持361W CHB输出（360W臂＋1W制动偏置），85%效率敏感性损耗63.705882W；底板热源与两个立柱足分别连接，未绕过底板扩散。当前894实例STEP局部遮挡场已重建，新增沉孔进入实际平面面积掩膜。每侧1D中心线热阻估算0.956317K/W，其中TIM典型值0.132808K/W；这不是实测或保证上界。被遮方向与指定温度部件换热，链接允许热流反向。

|状态|遮挡物温度K|+Y入射1361W/m²|CHB壳温°C|
|---|---:|---|---:|
|service|330|无|61.83|
|service|330|有|72.18|
|service|350|无|66.08|
|service|350|有|75.93|
|parking|330|无|91.05|
|parking|330|有|98.37|
|parking|350|无|100.06|
|parking|350|有|106.65|
|released|330|无|91.12|
|released|330|有|98.44|
|released|350|无|100.14|
|released|350|有|106.73|

表格为5mm网格条件算例。折叠330K/+Y光照工况加密到2.5mm得到98.52°C，原TSP1600S同口径为105.14°C。三片垫同时取相同参考压强的敏感性为：10psi → 99.72°C；25psi → 98.44°C；50psi → 97.73°C；100psi → 97.45°C；200psi → 97.31°C；这些数据不证明已经建立了所需压强。[当前TIM接口合同](thermal/COLD_TIM_INTERFACE_CONTRACT.json) · [38实例物料映射](mechanical/COLD_PATH_INSTANCE_BOM.csv)。

上述环境均为注明条件的敏感性，未绑定真实轨道/姿态。折叠330K/+Y光照条件下，增加5W未分配热源时103.25°C；增加10W未分配热源时107.97°C；这说明仍需给其它设备与接触误差留出真实热余量。网格加密和能量守恒检查仅验证数值实现，未升级为整星热通过。原单侧失败、底板单面失败与更热遮挡物反例均保留。[当前热网络](thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json) · [当前表面视场](thermal/RADIATOR_MESH_VIEW_SCREEN.json)。

电气维持201位号/11页KiCad以及各自已绑定的435原生网表、104制动、50启动静态、8全故障网清点回执；7个power_pin_not_driven ERC仍披露。本轮未代替电池/PMM受保护端、PCB及实际线束端接、制动能量与停止/启动动态、保险/电容/SOA、充电、推进同修订ICD和任务能力验证。37行责任表的完成等级保持原口径。[电气PDF](ecad/wp10_system.pdf) · [KiCad源](ecad/wp10_system.kicad_sch) · [BOM](power/SELECTED_BOM.csv) · [From–To](ecad/MASTER_FROM_TO.csv) · [闭环表](SYSTEM_CLOSURE_MATRIX.csv) · [机器裁决](results/DELIVERY_DECISION.json)。

电池安装已进一步核对：RRC3570-4 D版最大外形189.5×85.5×82.2mm，当前90×170×65mm旧电池占位保持原功能，未拿它冒充新高功率电池。保留现有设备，在当前service态CAD表示中，六种轴向姿态在声明舱域及2mm设计间隙下没有找到清晰的包围盒位置；忽略三件非凸热结构外包围盒的待精查分支也未找到位置。这不是实际STEP几何、全姿态或实物不可能的证明，下一步必须先确定设备局部迁移和窄相位检查，再生成托架。厂家MC35文件名A但页脚B，两个功率脚实际中心距29mm；电池插座相对外壳的定位、保持区、配合行程和允许夹紧仍没有受控依据。[电池接口输入](power/BATTERY_INSTALLATION_INTERFACE.json) · [同894候选包装初筛](results/RRC_BATTERY_PACKAGING_SCREEN.json)。

本轮出现一次启动前内存不足，任务未启动；对已识别闲置Codex工具服务回收可重新载入的工作集后，可用内存恢复并完成后续串行工作。没有结束应用/会话。启动≥2GiB、运行≥512MiB、任务与自有SW合计≤1400MiB的约束保持。[内存回收记录](results/COLD_PATH_MEMORY_RECOVERY.json) · [本轮运行记录](results/COLD_PATH_MEMORY_AUDIT.json) · [审阅处置](results/COLD_PATH_REVIEW_DISPOSITION.json)。

![当前导热核心](review/thermal_core_cold_path_iso_20260908T234051Z.png)
