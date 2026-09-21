# WP10 V13 输入保险与电容改件
F201、C203具体型号、C203正负极与封装已进入当前原生电气源。201位号、11页、原99位号父本保持；435项连接检查、36项共享电源检查、26项器件筛查通过。7项电源引脚未驱动ERC仍开放。检查结果不等于整机完成。

|位号|当前候选|本轮实际绑定|
|---|---|---|
|F201|Eaton 1025HC30-RTR|30A、72VDC；主支路后备保险；BOM/原生图纸|
|C203|Chemi-Con ELXG101VSN222MR50S|2200µF±20%、100V；工程pad1正、pad2负；VS两孔封装|
|F202|6A慢断，MPN未定|保留辅助支路，尚未完成保护协调|

## 选择依据和限制
[Eaton官方10572（June2025）](https://www.eaton.com/content/dam/eaton/products/electronic-components/resources/data-sheet/eaton-1025hc-surface-mount-ceramic-tube-fuses-data-sheet.pdf)给出的500A直流分断只对应电池源、72VDC、L/R小于1µs的试验。现有BMS故障电流与线束电感未知，不能继承分断通过。示例1µH/0.1Ω已有10µs。典型1.7mΩ冷阻为20°C、低于0.1额定电流参考；112A²s为10倍额定电流下典型熔化值，不是总清除能量。温度降额图和实际PCB散热尚未数值绑定。30A额定值保持，未为规避限制提高电流。

原候选0456030.ER因其数据表明确排除航空航天用途而被拒；记录见[来源与淘汰项](../sources/INPUT_PASSIVE_DECISION_RECORD.json)。Eaton未见该条排除不构成航天合格证明。其PDF正文已通过官方网页读取，但本地文件下载超时、推荐焊盘尚未完成视觉核对，因此F201封装与安装坐标保持空值。

[Chemi-Con产品页](https://www.chemi-con.co.jp/en/products/detail-condenser.php?part_number=ELXG101VSN222MR50S)与[LXG系列目录](https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/LXGN-e.PDF)支持C203的参数。由初始20°C、120Hz的tanδ及最小容量计算，ESR上界为0.113036Ω；同温30kHz的阻抗上界0.03Ω只能给该频点的ESR界限。按寿命试验后的容量/损耗角允许变化，120Hz上界可至0.376787Ω，不能把初始小于0.12Ω的结果延用到全寿命。

纹波额定2.4Arms对应105°C、120Hz；模型保存了频率系数，实际电流频谱仍为空。主支路约20A直流不能充当电容纹波RMS。Cincon应用说明的低于−20°C输入电容增配条件也未闭合。[电容使用注意事项](https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/al-precaution-e.pdf)要求航天用途预先协商；没有替用户联系厂商。

## 电路、预算与机械接口
实际源：[integrate_power_loop.py](../tools/integrate_power_loop.py)、[器件参数源](../tools/input_passive_definition.py)、[原生电路PDF](../ecad/wp10_system.pdf)。C203正极在Q201后的PRECHARGED，负极在INPUT_RETURN，与机械臂侧隔离返回分开。工程pin1/2是本项目编号，不冒充厂家针号。

电容3mA泄漏为20°C、5分钟测试条件下的目录值，本轮按工作电压场景移用，独立计入预充之后的负载；与主控3mA、启动0.25W分别记账。192场景重算后，SBP132锚点：电池电流19.832696950A、欠压检测23.122096491V、共享接点损耗39.333586832W、电容泄漏损耗0.067379294W。16组欠压保持反例仍在。冷态开关断开时不从电池端虚构电容泄漏供电，电容电压保持为空。COLD泄漏热记0仅指电池输入贡献；未知储能电容的实际放电热没有被算成0。

F201按典型冷阻移用的锚点损耗0.608977996W，从原主支路前段损耗中拆出，不重复增加总电阻。[新热源账](../thermal/INPUT_PASSIVE_HEAT_LOADS.csv)共3648行，包含RUN/COLD。它取代同场景的聚合前段记账，不能与旧CSV相加；安装热节点仍未绑定。

C203容量上界2.64mF、29.4V储能上界1.1409552J。预充积分与闭式解已对拍，但理想轨迹省略源阻抗、启动负载和实际时序，只作诊断；没有因此判保险寿命、MOSFET SOA或启动动态通过。LM5069限流低于30A，不能要求F201在正常限流值下承担快速断电。

C203最大外形Ø31×52mm；顶部泄压另留至少3mm，接脚向PCB下方最大4.5mm。VS端子为两Ø2mm圆孔、10mm孔距；本项目焊盘3.5mm是候选分配，未当制造保证。封装已通过KiCad原生解析：[SVG](../review/input_passive_footprint/CP_ChemiCon_VS_D30_P10_2mm_Candidate.svg)。正极矩形pad1在顶视图左侧、负极圆形pad2在右侧；实际装配须对照负极条纹。

厂家CAD下载返回维护页、step.parts精确检索无匹配，未取得OEM BRep。没有将该电容虚假计入现有936实例整机；保持、绝缘、顶部泄压区及与CHB输入端的短回路布置仍需实体设计。套管不能当绝缘保证。端封面下的铜箔避让尚未进入实际PCB，封装的二维外框不能代替该项检查。

## 复核和后续执行
[独立审阅](../results/INPUT_PASSIVE_READONLY_REVIEW.json)绑定本轮计算和源文件SHA。[V12历史](../history/20260909_V12_before_input_passives/power/SHARED_BATTERY_PATH_CALCULATIONS.json)保持原值；[当前V13共享模型](SHARED_BATTERY_PATH_CALCULATIONS.json)含C203泄漏。936机械源、局部136件STEP和既有38件SolidWorks热组件仍按各自旧验证范围使用。

接下来继续输入PCB/载板和器件保持、主辅保险与短路路径、C203全温纹波/寿命、完整SOA和STOP动态；电池/PMM受控接口、全热源和推进ICD仍开放。37行闭环表状态未升级。本轮没有制造、接电或实物试验。
