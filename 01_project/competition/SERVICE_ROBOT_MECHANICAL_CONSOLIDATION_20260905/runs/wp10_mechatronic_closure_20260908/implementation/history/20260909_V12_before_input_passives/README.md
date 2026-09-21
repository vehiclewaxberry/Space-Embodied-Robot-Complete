# WP10 当前修订：共享电池接点的供电与热预算

已修正主／辅助支路共同承担的MC35接点压降。192组条件、34项模型和原生拓扑检查完成；发现16组欠压保持反例。25.2V、共享0.10Ω的保守场景下，欠压检测点23.122455V、接点损耗39.320039W，部分容差无法保证保持。这不是实测温升，也没有证明实际跳变下会持续产生该热量。

[设计说明及比较表](power/SHARED_BATTERY_PATH_DESIGN.md) · [模型与电气绑定](power/SHARED_BATTERY_PATH_CALCULATIONS.json) · [实际Python源](tools/shared_battery_path.py) · [新增热源账](thermal/SHARED_BATTERY_HEAT_LOADS.csv) · [当前交付判定](results/DELIVERY_DECISION.json)

整机机电设计仍未完成。电池／PMM保持和插口坐标、接点温升、充电、全热源、停止动态和受控推进接口继续开放。电气201位号／11页、V11完整936实例源表与局部136件STEP保持原版本，本轮没有重新生成整机原生SolidWorks。

下文为V11及更早机械增量，验证范围按各自源版本保留。

---

# WP10 当前修订：桥板线束衬套与侧向保持件

桥板过孔已加入可拆分衬套、一体开口金属压板和两颗名义螺钉；整机机电详细设计仍未完成。当前完整源表每态936实例，局部STEP136实例，衬套细节STEP5实例；没有生成当前936整星原生SolidWorks装配。

[旋转查看136件局部装配](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical%2Froot_bushing_integration.step.py) · [STEP](mechanical/root_bushing_integration.step) · [5件细节](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical%2Froot_bushing_detail.step.py) · [936完整源表](mechanical/ROOT_BUSHING_INSTANCE_PLAN.json) · [6行增量BOM](mechanical/ROOT_BUSHING_INSTANCE_BOM.csv) · [绑定证据](results/ROOT_BUSHING_REVIEW.json)

桥板新增两处名义螺纹主径盲孔，只减料63.617251mm³，原孔与其余源保留。两半衬套D9.8/内孔6.6，以D14法兰和0.1mm轴向间隙被保持；单件开口压板按20mm侧向通道设计，两固定轴移至S(53,-80)/(53,-70)。初版右螺钉工具杆被RB303挡住233.29788mm³，现已改件修复。

三态各18对改变近邻无穿透，6处必需接触成立；左右半衬套下降0.1mm的实际挡止面积54.286721/29.498275mm²，与只读审阅者独立复算一致。D5×25工具空间分配通过，压板20mm直线保守扫掠无穿透；未冒称已选工具或完整装配过程。7个CAD入口已检，8张快照已逐张查看。[尺寸、选材和装配顺序](mechanical/ROOT_BUSHING_BRIEF.md)

保护只到z115.15，M3RB上部边槽、应变释放和四段释放支路仍开放。当前桅杆实体已确认两个固定释放端点在折叠10°时进入管壁；释放器仍为未选型功能包络，不能直接改背面端口或切弱桅杆。公差场景计偏心后余量0.06mm，实际线束/孔位/热变形等未绑定，因此公差、螺纹、强度、材料放气和连续运动仍未获合格信用。

选材参考 [Victrex 450G March 2026官方数据表](https://www.victrex.com/-/media/downloads/datasheets/victrex_tds_450g.pdf?rev=66e2f2641768427097e4ad8ce08deb49)，成品料和批次未确认。电气仍是201位号/11页既有源。本轮未重算936布局的质量、惯量和热网络；旧894热证据、38件原生导热核心保持原范围。37行状态仍为13限定完成、19内部开放、4外部未绑定、1物理未执行。

![5件衬套及保持组件，桥板未显示](review/root_bushing_detail_iso_20260909T025450Z.png)

![压板下方双螺钉](review/root_bushing_detail_bottom_20260909T025450Z.png)

---

下文是V10及更早修订的历史验证范围。当前布局以上述V11源表为准。

# WP10 当前修订：连续主干线四站安装支撑

**四处主干支撑、固定孔和名义紧固件已实际集成；整机机电详细设计仍未完成。** 当前三态完整源表各931实例，局部STEP131实例；931是源表数量，没有生成当前整星原生SolidWorks或完整BRep装配。

[旋转查看131件局部装配](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical/trunk_support_integration.step.py) · [装配STEP](mechanical/trunk_support_integration.step) · [931源表](mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json) · [49行机械增量BOM](mechanical/TRUNK_SUPPORT_INSTANCE_BOM.csv) · [绑定证据](results/TRUNK_SUPPORT_REVIEW.json)

原4夹具/4高支柱ID已用四组split支座实际替换；增加8片半衬套和30件名义紧固件。低位支座贴甲板；高位支座轴S(-95,1.5,45)mm，柱通过设备间走廊，底脚直接承载于甲板。两块自制载板增加边缘避让，原安装孔保留；甲板新开8个Ø3.4孔。只在指定范围减料：甲板217.900866mm³、两载板各231mm³，增料、窗外减料及漏切均为零。[设计尺寸及装配顺序](mechanical/TRUNK_SUPPORT_BRIEF.md)

三态各129对变化近邻实际STEP检查均无正体积穿透、异常接触及电池间隙失败；各54处必需承载/衬套接触均为零距离且有正面积。10组名义紧固件覆盖完整螺母高度，最小伸出2.1mm。12个CAD入口几何有效，13张快照已查看。上述验证不等于螺纹、防松、夹持力、材料/放气、强度、公差、全线动态或实物合格。

初次检查确实发现高支架与驱动连接器460mm³穿透，以及悬臂填回螺钉通孔5.15638mm³；已移动高站15mm并重开通孔，通过同源复检。完整源表保留4段旧释放线路及其parking入口干涉，未通过删除反例取得整机通过。顶端穿孔护套/应变释放、真实电池/PMM保持和电气端接仍开放。

电气仍为201位号/11页既有原生源；本轮未改电路。当前931布局未重新完成质量、惯量、结构或热分析。894父布局的热计算和38件原生导热核心仍按原范围保留。原37行表仍13限定完成、19内部开放、4外部未绑定、1物理未执行。[当前机器裁决](results/DELIVERY_DECISION.json)

![当前局部装配](review/trunk_support_integration_iso_20260909T021553Z.png)

![高位可拆线束支座](review/trunk_high_base_iso_20260909T021604Z.png)

---

下文保留V9推进布线、V8电池布局及V7导热核心的历史范围；当前源表以上述V10为准。

# WP10 当前修订：推进两线与电池舱源装配

**推进线路与安装支撑已实际更新，整机机电详细设计仍OPEN。** 三态完整候选源表均为893实例；85件局部STEP已生成、检查并查看。893是完整源表数量，尚未生成当前整星原生SolidWorks装配，也未证明全件装配通过。

[旋转查看85件局部装配](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical/battery_route_integration.step.py) · [局部装配STEP](mechanical/battery_route_integration.step) · [三态893实例完整源表](mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json) · [17实例改件BOM](mechanical/BATTERY_PROPULSION_INSTANCE_BOM.csv) · [本轮源绑定与审阅](results/PROP_ROUTING_REVIEW.json)

本轮更新17实例：推进供电/数据两条OD6、中心线R21包络，双孔夹具底座/盖、两支柱、两根名义M3杆、8件原来源垫圈/螺母及甲板。原PWR起点和单路夹具保留；DATA原功能起点进入电池，因此迁到S(45,34,59)的功能交接位置。该位置没有厂家针脚依据，上游真实接续仍未完成。两个模块侧功能末端保持原坐标。

夹具孔径8mm，中心线y34/48、z59mm；支柱中心(72,41)/(88,41)，高度60.5mm。甲板增加两Ø3.4通孔，实际只移除54.475216613mm³指定材料，增料、柱外减料及漏切为零，旧孔保留。支撑孔与OD6存在约1mm径向空间，不能称为已夹紧；护套、夹持力、材料、防松、螺纹、强度及公差仍待完成。[设计源与说明](mechanical/BATTERY_PROPULSION_ROUTE_BRIEF.md)

三态分别完成66对变化邻域实际STEP检查，均无正体积穿透及意外零间隙；两推进线最小间隙3.123238mm，PWR/DATA到导航盒分别3/2mm，夹具到导航盒1mm。8个CAD入口通过refs及几何有效性检查，9张快照已实际查看。以上只证明相应固定状态的几何，不证明端接、温升、连续运动、完整整星或实物。

完整源表计数为894−3旧中央线段＋1新连续主线＋1电池最大盒＝893。8件旧主干夹具/支柱及4段旧释放线路均仍保留在表中并标明责任，未通过删除负例取得完整装配信用。旧电池功能也保留；新RRC仍是D版最大外包络，电池保持和PMM实际安装未完成。

释放支路的停车态入口已做实际STEP诊断：原功能端点中心到保持杆仅1mm，原末段每条与杆穿透约208.889mm³；特定R14侧向接近样点落在杆壁内。service/released旧末段也仍穿透约184.715mm³。保留原端点并登记局部接口需改，不改成背面端口冒充解决。该诊断不声称证明所有可能路线均不可行。[真实端部反例](results/RELEASE_PORT_CLEARANCE_COUNTEREXAMPLE.json)

当前893布局的质量/惯量、热分布与结构校核未完成，原894热布局和38件原生导热核心的限定证据单独保留，不自动授予本次迁移布局。37行闭环表仍为13项限定完成、19项内部开放、4项外部未绑定、1项物理未执行。[机器裁决](results/DELIVERY_DECISION.json)

本轮所有重型任务已串行结束，最低记录可用内存2014MiB、最大任务工作集998MiB；未突破原内存守卫阈值。[内存记录](results/PROP_ROUTING_MEMORY_AUDIT.json)

![当前85件局部修改](review/battery_route_integration_iso_20260909T013853Z.png)

---

下文保留V8电池布局基础和V7导热核心的具体范围；当前候选源表以上述V9为准。

# WP10 新增：电池舱重布置与主干线通道

**55件局部装配已生成并查看，整机机电设计仍未完成。** 当前894实例热设计父布局及38件原生SolidWorks导热核心保留；本次55件STEP是同一候选的局部修改验证件，尚未替代整舱或生成新的原生SolidWorks装配。

[旋转查看55件装配](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical/battery_bay_layout.step.py) · [下载局部STEP](mechanical/battery_bay_layout.step) · [改件说明](mechanical/BATTERY_BAY_BRIEF.md) · [本轮审阅与源绑定](results/BATTERY_BAY_REVIEW.json)

RRC3570-4 D最大矩形包络189.5×85.5×82.2mm，按S系轴序189.5×82.2×85.5mm布置。38个原设备/托盘/支撑实例整体迁移，保留原功能；实际增加四个甲板孔、四个导航壁面支座、驱动载板边缘避让。当前设备仍含功能盒表示；电池插座、夹持接触区及保持结构未绑定。初始反例与历次修复保留在history。

中央主线改为连续OD6、中心线弯曲半径≥21mm，从电池下方通过。对最大电池盒实体间隙4.107556mm；原上升段穿透桥板169.646003mm³、M3RB68.565260mm³，已通过桥板Ø10通孔和M3RB R5开边槽修复。两件各只移除规定区域471.238898mm³，柱外减料、漏切和增料均为0。原固定孔位保留；护套、应变释放、孔边强度及公差仍未完成。[主线窄相位及反例](results/BATTERY_INTERNAL_ROUTE_SCREEN.json)

**完整线束仍OPEN。** 两条原释放支路同轴重合105mm／1319.468915mm³，各与新M3RB仍穿透456.336140mm³。主线接续例外仅限终点附近10mm立方区，未把整条支路豁免。原27件待重做线路/夹具，加上这2条释放支路，均保留设计责任。未获得真实针脚、分线器、裁线、电流、动态寿命或全线束装配信用。

本次8个CAD入口均通过refs和几何有效性检查，主线检查38个邻近对象；局部装配采用固定根和部件局部基准。8张视图已实际检查。迁移后整舱热分布与强度须重算，原894布局的热结果不自动授予本次55件修改。37行责任表的完成等级保持不变。

本轮串行任务已结束并释放任务资源，记录中最低可用内存2032MiB、最大任务合计工作集944MiB；启动2GiB、运行512MiB及任务1400MiB约束保持。[内存回执](results/BATTERY_MEMORY_AUDIT.json)

![55件电池舱局部修改](review/battery_bay_layout_iso_20260909T010526Z.png)

---

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

电池安装已进一步核对：RRC3570-4 D版最大外形189.5×85.5×82.2mm，当前90×170×65mm旧电池占位保持原功能，未拿它冒充新高功率电池。保留现有设备，在当前service态CAD表示中，六种轴向姿态在声明舱域及2mm设计间隙下没有找到清晰的包围盒位置；忽略三件非凸热结构外包围盒的待精查分支也未找到位置。这不是实际STEP几何、全姿态或实物不可能的证明，该初筛现作为历史输入；本轮已完成上文局部迁移和主线窄相位，托架及整舱集成仍待完成。厂家MC35文件名A但页脚B，两个功率脚实际中心距29mm；电池插座相对外壳的定位、保持区、配合行程和允许夹紧仍没有受控依据。[电池接口输入](power/BATTERY_INSTALLATION_INTERFACE.json) · [同894候选包装初筛](results/RRC_BATTERY_PACKAGING_SCREEN.json)。

本轮出现一次启动前内存不足，任务未启动；对已识别闲置Codex工具服务回收可重新载入的工作集后，可用内存恢复并完成后续串行工作。没有结束应用/会话。启动≥2GiB、运行≥512MiB、任务与自有SW合计≤1400MiB的约束保持。[内存回收记录](results/COLD_PATH_MEMORY_RECOVERY.json) · [本轮运行记录](results/COLD_PATH_MEMORY_AUDIT.json) · [审阅处置](results/COLD_PATH_REVIEW_DISPOSITION.json)。

![当前导热核心](review/thermal_core_cold_path_iso_20260908T234051Z.png)
