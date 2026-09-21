# 电气、B601接口与线束

本目录保存 R5E 候选原理图和三块真实 V36 PCB，供继续数字设计。原理图可编辑不等于全部功能电路、PCB或三维模型已完成。制造、采购定版、上电与在轨使用均未放行。

## 打开与数据入口

- 用 KiCad 10.0.6 打开 [系统工程](kicad/wp10/wp10_system.kicad_pro) 与 [系统原理图](kicad/wp10/wp10_system.kicad_sch)。15张原理图及9个符号库、40个封装、两张库表随包保留。
- 实际PCB分别为 [MAIN](kicad/wp10/wp10_main_input.kicad_pcb)、[AUX](kicad/wp10/wp10_aux_protection.kicad_pcb)、[STOP](kicad/wp10/wp10_stop_control.kicad_pcb)。MAIN/STOP工程不各自带一个同名顶层原理图；电气完整系统以 `wp10_system.kicad_sch` 层级为准。
- 选型以 [249行选型BOM](bom/ELECTRICAL_SELECTION_BOM_R5E.csv)、[尚未实施的ECO](bom/ECAD_ECO_R5E.csv)、[候选采购表](bom/PROCUREMENT_CANDIDATES_NOT_RELEASED.csv) 为入口。本表已核对为249行、249个唯一位号；候选采购表为219个逻辑实物候选位号，表内已将R305建议拆分列为220行/220件候选（ECO尚未实施），均非整星BOM数量。
- [线束连接表](harness/ELECTRICAL_CONNECTION_MATRIX.csv)、[设计说明](harness/ELECTRICAL_HARNESS_DESIGN.md)、[功能路径参数](harness/INTERNAL_ROUTE_PARAMETERS.json) 保留 R2 输入；当前水平安装的 MAIN 局部端口补充见 [R6H端口表](interfaces/INSTALLED_PORT_DATUMS_R6H.csv)。路径包络和逻辑连接不能替代端子针脚/压接/线长制造数据。
- B601 使用 [驱动器基线](b601_interface/B601_DRIVER_BASELINE.json)、[板卡预留](b601_interface/BOARD_RESERVATION.json)、[项目逻辑接口](b601_interface/PROPOSED_INTERFACE_PINS.csv)。60×40 mm等预留尚未实现为完整接口控制板；逻辑针脚不等于厂商实物针号。

## 候选属性与实际PCB

R5E在11张原理图的46个位号上增加候选属性，保持原Value、Footprint和拓扑。三块PCB原样来自当前V36，只在本副本中重定位3D模型引用。候选BOM中的新器件尚未全部反映在PCB上，39个未布板候选不能称已安装。R305两电阻串联ECO与C301新容量也不是已实施电路变更。C301/C302/C305有效容量、保护协调、满载电热和接口电流仍待核验。R6H总装只有MAIN安装候选，AUX/STOP还未完成机械安装。

[后续电气工作](design/NEXT_ELECTRICAL_WORK.json) 与 [约束](notes_from_source/04-constraints.md) 保留这些边界；旧239位号导出及旧0.2 mΩ分流器表没有作为当前源收录。当前 R202 为0.5 mΩ，电热叠加见 [能源热控目录](../03_power_thermal/README.md)。

## 依赖与副本验证

[模型依赖表](MODEL_DEPENDENCIES.json) 列出19个精确引用：12个现存KiCad模型加Wurth端子和自建C201体共14个随准备包收录；5个Molex Micro-Fit模型在本机缺失，保留原引用并标明缺失，未以相似件替换。库表使用 `${KIPRJMOD}`；已有模型路径仅在副本改为本地路径。没有模型的自定义器件仍不具备完整3D覆盖。

[副本验证](verification/SYSTEM_COPY_VERIFICATION.json) 记录原源哈希、路径归一比较、层级网表导出和三板语义对照。[逐文件来源](SYSTEM_COPY_MANIFEST.csv) 保留原始与目标哈希。[第三方说明](third_party_notices/README.md) 记录库许可与待确认OEM资产。

`notes_from_source`、线束说明及JSON内历史路径为原设计档案来源记载，可能指向未随精简包携带的证据；它们不作为跨目录运行入口。本目录不包含控制算法、固件、上电测试结果或航天资格声明。
