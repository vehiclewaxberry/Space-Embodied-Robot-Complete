# 原生电气接口候选

已实际生成并用 KiCad10.0.6 读取两套原生设计：

- [直流与信号接口系统工程](wp09_system.kicad_pro)、[原理图](wp09_system.kicad_sch)、[真实导出网表](exports/wp09_system.xml)：24个外部边界符号、117端点、47网络。
- [地面RS-422转接板工程](rs422_gse_splice.kicad_pro)、[PCB](rs422_gse_splice.kicad_pcb)、[原理图](rs422_gse_splice.kicad_sch)、[真实导出网表](exports/rs422_gse_splice.xml)：15个焊线/测试焊盘、5个网络。
- [唯一主端点表](MASTER_FROM_TO.csv)、[原23条记录映射](LINEAGE_23.csv)、[现行电气BOM](MASTER_BOM.csv)、[转接板端点明细](RS422_PAD_MAP.csv)。`power/POWER_FROM_TO.csv` 是来源合同，旧 `functional_closure` 是冻结历史；两者不代替本轮主表。

70行是连接合同，包含未绑定逻辑端点。原A05双极回流触点撤销并入A04，A02/A03改GX11CAB A2(+)/A1(-)极性，L01/L02改3英寸短线。S01–S05端到端电气关系保留，实际地面拼接由A_i.1—TP_i.1—B_i.1的同网铜箔承担。主系统图作端到端表达，板级细节由独立PCB网表精确对应，未把三段实体导体谎报成单根可下料导线。

**这是外部接口设计，不是整机完整制造线束或市电电源柜电路。**PS1只画直流输出边界；市电入口、PE保护连接、壳体及端子防护要由完整GSE责任件实现。DM的VCC_REF/RET_REF/CANH_REF、分线板/USB-CAN逻辑端口、STOP_CONTROL/STOP_MONITOR及未定PV支路不是猜出的物理针脚。它们均不得按图直接压接。明确NC及不宜画成导线的8项要求保存在 [EXCLUDED_REQUIREMENTS_AND_NC.json](EXCLUDED_REQUIREMENTS_AND_NC.json)。RBF电阻、金属接地罩、PGND断路与部署开关仍须实现，未被主表中的逻辑连接替代。

## 实际检查结果

|对象|本轮结果|解释|
|---|---|---|
|系统网表↔主表|70行逐端点通过；117端点的47个连通分区完全一致|不是只比网络名称。|
|系统端点图|原始主表和KiCad实际导出网表均通过|Q/K四状态检查；理想U1穿通模型只用于拓扑。|
|独立反例|22/22通过；对实际导出网表另加PDU9–10短接也被拒绝|涵盖保护旁路、回流缺失、跨域、USB回灌、双源并接、伪批准和误标签。|
|系统ERC|1项error，0 warning|U1.IN+跨被动保护/切断器边界没有驱动电源声明；保留，不使用PWR_FLAG或排除规则。停止/回生硬件仍开放。|
|RS422板ERC|0违规|板本来就是5条无源导体，非把有源部件伪设passive。|
|RS422板DRC|0违规、0未布线、0板图一致性违规|包括原生PCB与原理图的值、属性、网络校对。保留工具默认忽略项，不称全制造规则认证。|
|OreSat上游主图/板|ERC11 warnings；DRC2 courtyard errors及其他warnings|真实负结果保留，不能继承上游PASS。|

机器结果：[ECAD_VERIFICATION](../results/ECAD_VERIFICATION.json)、[独立反例](../results/ECAD_SYSTEM_GRAPH_TESTS.json)、[KiCad真实命令](../results/KICAD_RUN.json)。初始排版格点、PCB语法和丝印/属性问题的失败输出保存在 `rejected_r0/`、`rejected_r1/`，后续报告不覆盖其身份。原24项物理检查仍在父本原文件中为NOT_EXECUTED。

## 地面板的机械责任

板外廓40×30 mm，标称总厚1.6 mm；10个Ø1.2 mm焊线孔、5个Ø0.7366 mm测试孔，孔位见PAD_MAP。KiCad `--board-only` 实际输出的基材厚度为**1.51 mm**，不含铜层、阻焊与端接；因此原生SolidWorks板件也是40×30×1.51 mm基材，不冒充完整1.6 mm成品。板件STEP由原生PCB直接导出，冷重开1实体、STEP往返差集体积为0，详见 [NATIVE_BOARD_MATERIAL](../results/NATIVE_BOARD_MATERIAL.json)。[SolidWorks板件](../mechanical/native/RS422_GSE_SPLICE_BOARD.SLDPRT)、[STEP](../mechanical/RS422_GSE_SPLICE_BOARD.step)。它是外部台架件，没有装入705组件整星。

上游测试孔铜箔/钻孔保留，参考丝印由0.56改1 mm并移到孔外2 mm处。新焊线孔、走线、板边和接线标识由本项目负责。每条走线30 mm、宽0.5 mm；无PE/屏蔽搭接、无附加端接电阻。实际FTDI修订/终端、剥线直径与绝缘、焊后清洁/固定、线束卸载和绝缘罩尚未验证。导线不能把拉力直接交给焊盘。默认没有Gerber、充压、带电或制造放行。

复算：在本候选目录运行 `python -X utf8 tools/verify_ecad.py`；原生工具检查用 `tools/run_kicad.py`（脚本会生成候选检查输出，不运行硬件）。源修改见 `tools/build_ecad.py`。BOM中actual_received均为UNCONFIRMED，不推断用户已经购买。
