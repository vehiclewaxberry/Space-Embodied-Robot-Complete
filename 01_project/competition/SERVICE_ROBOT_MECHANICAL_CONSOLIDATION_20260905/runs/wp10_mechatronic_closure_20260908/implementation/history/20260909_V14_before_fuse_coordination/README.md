# WP10 V14：C203输入电容机械安装候选

当前候选已增加29个安装实例、修改上甲板4个孔，总源表965实例。C203正负极、实际KiCad封装和整星坐标已绑定。整机详细设计尚未闭环，原37行裁决状态保持：13个有范围的子项完成，19个内部设计开放，4个外部接口未绑定，1个实物项目未执行。

[查看29件安装架](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical%2Finput_cap_detail.step.py) · [查看37件局部安装关系](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation?file=mechanical%2Finput_cap_integration.step.py) · [整合包](WP10_IMPLEMENTATION_DELTA.zip)

![安装架](review/input_cap_detail_20260909T043518Z.png)

本次新增真实源：[参数与安装约束](mechanical/INPUT_CAP_MOUNT_BRIEF.md)、[参数JSON](mechanical/INPUT_CAP_MOUNT_DESIGN.json)、[保持架构建器](mechanical/input_cap_mount_common.py)、[965实例源表](mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json)、[29行安装BOM](mechanical/INPUT_CAP_INSTALLATION_BOM.csv)、[CAD/ECAD接口](ecad/C203_MECHANICAL_INTERFACE.json)。C203沿用电气BOM已有物料，安装BOM明确禁止重复计购。STEP可导入SolidWorks；本轮没有声称生成965件原生SLDASM。

采用Chemi-Con ELXG101VSN222MR50S，名义Ø30×50、最大Ø31×52。本体端封贴PCB x=-7，厚1.6；pad1正极y=-5，pad2负极y=+5。最短引脚通过板后有1.9mm名义投影。最大外形末端沿−X保留3mm泄压空间。尺寸与使用限制依据[厂家产品页](https://www.chemi-con.co.jp/en/products/detail-condenser.php?part_number=ELXG101VSN222MR50S)和[厂家安装注意事项](https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/al-precaution-e.pdf)；本体是标识清楚的尺寸外形，未伪造OEM内部结构和引脚形状。

两处下挂分体箍中心x=-48/-20，PEEK名义衬套配合Ø30本体。甲板孔y=±32.5，下箍孔y=±22.5。实查发现并修复4个螺钉头埋入竖腿及2个被连接筋填回的板孔；原失败回执保留。三态分别执行79对精确BRep检查、35个必须接触、10个外形/端子/泄压空间检查、4个工具末段检查，均通过。甲板去料108.950433mm³，仅对应4个Ø3.4通孔。额外10项实际电路/封装/坐标判据通过。证据：[精确结果](results/INPUT_CAP_MOUNT_EXACT.json)、[只读复核](results/INPUT_CAP_MOUNT_READONLY_REVIEW.json)、[名义紧固件叠层](results/INPUT_CAP_FASTENER_STACK.json)。几何接触不代表夹紧力或载荷保持通过。

原生电气保持201位号、11页、原99位号父本；435项连接/反例检查通过。修正了先验证后生成封装库的顺序问题：原8条ERC违规由7个error和1个库链接warning构成，现仅消去该warning，仍有7个电源引脚未驱动error。没有更改忽略规则。之前查看页直接写7而机器为8的差异已披露并纠正。当前结论读自机器结果：[原生检查](results/POWER_LOOP_VERIFICATION.json)、[同源只读审阅](results/INPUT_PASSIVE_READONLY_REVIEW.json)。共享电源192场景、36项检查及26项无源器件检查的数值未变。

![局部安装关系](review/input_cap_chb_detail_20260909T044432Z.png)

查看范围和几何验证边界见[图像及验证说明](results/INPUT_CAP_VISUAL_REVIEW.json)。29件视图省略甲板，所以垫圈与法兰之间显示甲板预留厚度；37件三维文件含邻近源实体，以上截图为看清位置，仅显示29件安装架与CHB，隐藏甲板、散热板及两侧设备。这些实体仍参与精确检查。新增29件和修改甲板共30件完成含自交的完整验证；37件拓扑/闭合/正体积通过，但既有背景件全量自交因1400MiB任务保护中止，未取得通过信用。清理闲置内存后完成了上述分项检查。583个旧STEP文本引用审计未找到缺失编号，但原bounds刷新有一次未归因的OCP导入警告，不能据此宣称全部旧源完整或全整机间隙通过。

尚待完成：C203紧邻CHB的温度/纹波自热/寿命及低温条件；实际夹紧力、轴向抗滑、PEEK蠕变和全装配工具路径；板铜箔与CHB输入端接（当前引脚末端直线距离约56mm，不能称近端低阻抗回路）；F201/F202热降额与保护协调；电池/PMM受保护接口与固定、完整STOP/回生动态、全热路径、同修订推进ICD。当前所有整机交付、制造、接电、飞行和实物测试布尔均为false。

内存清理只回收80个闲置工具服务的驻留页，进程结束数0；约3002→3041MiB，页面可按需重新载入。重CAD串行运行，启动门槛2048MiB与512MiB运行保护保持。
