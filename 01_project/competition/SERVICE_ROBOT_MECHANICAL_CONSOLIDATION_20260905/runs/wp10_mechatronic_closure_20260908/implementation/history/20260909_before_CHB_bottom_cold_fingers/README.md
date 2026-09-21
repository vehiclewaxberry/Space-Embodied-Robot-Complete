# WP10 当前候选：底部散热结构与原生安装组件

已完成底部散热板、甲板与四个下层角码改件，安装六组紧固件；生成并冷读验证24实例/24实体的SolidWorks底部安装组件。整机候选源表为884实例、三个离散状态。**整机机电详细设计仍未完成，尚不能按完整工程样机、通电或飞行设计交付。**

[统一查看](REVIEW.html) · [旋转查看当前整舱改件](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical%2Ffixed_heat_bay.step.py) · [旋转查看底部安装](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical%2Fbottom_mount_assembly.step.py) · [SolidWorks组件包](mechanical/WP10_BOTTOM_SOLIDWORKS.zip) · [当前全部设计增量包](WP10_IMPLEMENTATION_DELTA.zip)

底板344×196.3×8mm，外表面S z=-114.15；六座为(-140,±93.5)、(-60,±33)、(120,±93.5)。外四座接触角码底面，内两座接触甲板底面。四角码与甲板同轴新孔进入源文件。横梁、原拉杆/螺母、甲板螺钉和MiPS脚螺钉均有具体避让。净平面辐射面积0.06691157m²；按2700kg/m³估计底板质量1.426515kg，未计为整星质量收口。最薄盲孔底皮3.95mm；载荷、预紧、公差和热接触性能仍需验证。

紧固件按Würth4123 53 20（ISO10642 M3×20，头径6.72/头高1.86）、norelem07300-03（垫圈Ø7/Ø3.2/厚0.5）与07210-403（M3螺母高2.4/对边5.5）公开尺寸选取。CAD为项目名义重建体，螺纹简化；目录中垫圈实际1.1mm、螺钉头径约5.639mm的错误模型已拒绝。未采购、未绑定到货修订/涂层适用性。见[厂家证据](sources/BOTTOM_VENDOR_SOURCES.json)。

原873封存父本保持：移除14个旧盖系统件和旧battery_thermal_link，加入8个器件/TIM与18个紧固件，得到884；11个原ID形状替换、14夹具件移位不增计数。删除旧电池热连接是设计处置，**电池受控热接口仍开放**。当前24件原生组件不能替代884整星原生总装。

本轮验证：48项底部实体/接触/定位检查；工作、收拢、释放状态各531对改件邻域STEP精确相交检查均零正体积交集、零未知；36个局部工具包络检查通过。工具为OD8/ID6.4套筒及OD4外侧内六角杆、20mm局部长度，不代表完整插入路径或公差检查。11个STEP目标已完成refs及有效性检查；装配通用自交跳过，局部24体和改件邻域由上述独立成对布尔检查承担。五张快照已核阅。

SolidWorks2024原生结果：9个SLDPRT分别保存、关闭、重新打开核验单位/实体/极值包围盒/体积及无外部几何引用；SLDASM在新会话冷读24唯一实例、24实体、0曲面、全部坐标变换与9本地依赖。源级刚性基准被解析为固定实例，无运动配合。原生文件与依赖见[底部原生装配](mechanical/native/WP10_BOTTOM_MOUNT.SLDASM)、[冷读回执](results/NATIVE_BOTTOM_COLD.json)。

帆板后续间距曾在STEP实例变换恢复时丢失，现已用当前与基线原生刚性差修复；18个帆板STEP位置读回最大误差1.43e-14mm。表面遮挡重算绑定当前884实例及当前底板净面（含孔/缺口），结果为面积与余弦加权半球方向采样：

|状态|−Y遮挡|+Y遮挡|底部−Z遮挡|
|---|---:|---:|---:|
|service|30.87%|25.68%|0.17%|
|parking|89.85%|89.84%|0.17%|
|released|90.23%|89.84%|0.17%|

这些是当前CAD表示的有限采样结果，并非太阳入射阴影、严格误差界或实测。被遮方向仍与帆板/星体辐射换热，不能直接把面积乘(1−遮挡比例)视为散热能力；还需局部空间视因子、温度、其他热源和真实任务环境。旧单侧85%效率满功率热失败仍保留；旧两板桥计算仍仅为注明边界的方案研究。**CHB至新底板的实际导热连接尚未安装，新增面积没有获得满功率热通过信用。**

电气源保持201位号、11页KiCad；435原生网表检查、104制动检查、50启动静态检查、8故障网清点沿用各自已绑定回执，7个power_pin_not_driven ERC仍披露。360W臂任务不变。制动真实能量/动态、独立STOP和启动动态、PCB/保护配合、电池PMM/高电流接口、线束真实端接，以及推进同修订ICD/任务能力仍须完成。37行责任表的完成等级未因本轮局部进展升级。

[电气PDF](ecad/wp10_system.pdf) · [KiCad源](ecad/wp10_system.kicad_sch) · [电气BOM](power/SELECTED_BOM.csv) · [线束From–To](ecad/MASTER_FROM_TO.csv) · [37行责任表](SYSTEM_CLOSURE_MATRIX.csv) · [机器裁决](results/DELIVERY_DECISION.json)

[底部几何](results/BOTTOM_MOUNT_GEOMETRY.json) · [三态接口](results/FIXED_HEAT_INTERFACE_SUMMARY.json) · [工具检查](results/BOTTOM_LOCAL_TOOL_CLEARANCE.json) · [表面遮挡](thermal/RADIATOR_MESH_VIEW_SCREEN.json) · [源变换修复](results/FIXED_HEAT_STEP_FRAME_REPAIR.json) · [BOM增量](mechanical/FIXED_HEAT_BOM_DELTA.csv) · [源参数](thermal/BOTTOM_RADIATOR_MOUNT.json) · [审阅处置](results/BOTTOM_REVIEW_DISPOSITION.json) · [内存记录](results/BOTTOM_MEMORY_AUDIT.json)

运行采用启动≥2GiB、运行≥512MiB、任务/Python与自有SW合计≤1400MiB。未终止无关应用。一次240秒CAD批次超时已清理自有树；只复用源SHA一致的已完成检查。本包仍为同项目候选增量，CAD源复建引用工作区父源与已安装CAD运行时。

![本轮当前整舱改件](review/fixed_heat_bay_bottom_revision_iso_20260908T220527Z.png)
