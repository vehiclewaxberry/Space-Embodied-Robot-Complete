# WP09 共享舱、推进接口与静态线束交付

已生成三套 SolidWorks 固定姿态总装，每套 **701 个组件、1082 个几何实体**。本轮保留619个旧组件，移除6个责任件，插入82个新/替换实例；新实例共享21个原生零件。实体统计包含设备与线束功能包络，不等于1082件可采购零件。

交付等级：**工程样机设计候选**。整星机械、电气、制造与飞行放行仍开放。

组件角色为231个PHYSICAL_GEOMETRY、430个SIMPLIFIED_PROXY、40个FUNCTIONAL_ENVELOPE。这些是源合同的表示类别；实体几何本身也不等于已经获得制造细节或实物符合性验证。

| 查看内容 | 文件 |
|---|---|
| 服务姿态总装 | [WP09_SERVICE.SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/native/WP09_SERVICE.SLDASM>) |
| 停放姿态总装 | [WP09_PARKING.SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/native/WP09_PARKING.SLDASM>) |
| 释放姿态总装 | [WP09_RELEASED.SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/native/WP09_RELEASED.SLDASM>) |
| 共享舱与推进线束局部 STEP | [integrated_bay_v6.step](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/candidate/integrated_bay_v6.step>) |
| 参数化源模型 | [integrated_bay.step.py](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/candidate/integrated_bay.step.py>) |
| 可旋转 CAD 查看 | [打开 CAD Viewer](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525?file=candidate%2Fintegrated_bay.step.py) |

SolidWorks使用2024版生成的原生SLDASM/SLDPRT，几何由经过回导验证的STEP导入。装配采用固定实例与明确变换；没有运动配合或可编辑的原生特征历史。总装仍引用本机既有项目零件，依赖清单见 [NATIVE_DEPENDENCIES.csv](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/results/NATIVE_DEPENDENCIES.csv>)；本目录不是独立Pack-and-Go包。完整整星STEP导出触发内存保护，因此只交付经验证的局部STEP及完整原生总装。

## 本轮具体改变

- 旧型号MiPS接口样件改至+X侧非承压托架，上甲板开缺口，原ADCS空间预留保留。旧MiPS与新版商品参数没有混用。
- P60保守包络移至上层，新增载板、支柱、拉杆和紧固件。真实PCB到载板的孔系与器件支撑仍待绑定。
- 推进电源和RS-422数据分路，新增穿舱护圈、可拆导向块及支承。名义束径6mm、中心线半径21mm；PWR路径316.9734mm、DATA路径204.9734mm。路径长度不是下料长度。
- 用户已确认B601 DM。工程样机选外置RSP-500-24（24V/21A），BPX 8S/P60限低功率支路。现有CAD与DM出货机械修订尚未核对。

选型理由和官方来源见 [DM选型说明](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/research/FINAL_SELECTION_DM_ZH.md>)；供电架构见 [供电与接口图](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/docs/SELECTED_DM_ARCHITECTURE_ZH.md>)。旧MiPS仅作非承压机械接口参考，实际飞行推进单元尚未选定。

## 验证与边界

V6完成266组去重BRep窄相检查，新件之间及新件对三态邻件未发现未许可材料重叠或原功能预留冲突。旧件之间不重复获得本轮检查信用。21个新原生零件均通过冷重开、实体/单位/包络核对和双向实体几何及体积回导比较。服务态实读全部701组件/1082实体；停放和释放态实读82个新实体，并核对全部701组件的身份、文件哈希、变换和固定状态；旧1000实体的体数继承经过哈希绑定的WP08冷读证据。

正面服务棱柱在合盖时被前维护盖遮挡，交叠15842.56960512mm³。仅在前盖已经移除这一条件下，其余已检查几何不挡该棱柱；真实工具、拆盖动作和羽流未验证。Ø8导向孔对Ø6束径是导向预留，不能认定已实现夹紧或应变释放。

目前完整端到端电气回路为0，24项试制检查均未执行。真实设备针脚、保护器件、导线截面、端部余量、DM实际任务电流仍待绑定；没有通电、承压、制造或连续运动验证。WP08后肋局部、前轮A3200局部细化和电池原生HOLD不会因这次总装生成而自动获得集成/通过信用。

## 设计与检查文件

- [线束路径图](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/docs/HARNESS_LAYOUT_S_WORLD.svg>) · [From–To表](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/ecad/From-To.csv>) · [DM供电/CAN分支表](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/ecad/DM_SELECTED_FROM_TO.csv>)
- [名义装配与局部试制步骤](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/docs/NOMINAL_ASSEMBLY_AND_PREFAB_ZH.md>) · [机械接口表](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/docs/MECHANICAL_INTERFACE_TABLE.csv>)
- [82实例增量BOM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/results/DELTA_BOM_82.csv>) · [整机服务态BOM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/results/ASSEMBLY_BOM_SERVICE.csv>)
- [关闭项与开放项](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/docs/CLOSURE_DELTA_AND_OPEN_ITEMS_ZH.md>) · [机器交付状态](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/results/DELIVERY_STATUS.json>)
- [原生独立绑定检查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/results/INDEPENDENT_NATIVE_BINDING_CHECK.json>) · [几何检查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/results/INTEGRATION_CHECK_V6.json>) · [原生材料回导](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/results/NATIVE_MATERIAL_CHECK_V2.json>)
- [执行限制与恢复记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/docs/EXECUTION_LIMITS_AND_RECOVERY_ZH.md>)

## 模型预览

![SolidWorks服务态实际整机视图](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/viewer/WP09_SERVICE_NATIVE.png>)

![共享舱实际CAD快照](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/viewer/bay_iso_20260907T065738Z.png>)

下一批实作优先绑定DM出货图、P60机械/电气接口、实际线材与保护器件，然后完成设备支撑、端接、工具路径与断电线束试制。实际压力推进选型和任务推力分配另需设备ICD与性能约束；本轮不由理想上界推导任务可行。
