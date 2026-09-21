# GX11 停止控制器原理图候选

本子页已生成 **71 个元件、222 个已接脚、39 个实际电网**的可编辑 KiCad 原理图；本页 From-To 为 183 条本地连接。原始整机 MASTER_FROM_TO 未改写。入口：[原理图](wp09_stop_circuit.kicad_sch)、[PDF](WP09_STOP_CIRCUIT.pdf)、[针脚网表](wp09_stop_circuit.net.xml)、[BOM](STOP_BOM.csv)、[并入整机的端口地图](STOP_PORT_MAP.json)。

已执行 KiCad 10.0.6 网表导出、ERC 和 420 项针脚/断言/有限状态检查。**ERC 尚有 3 项实际未供源错误**：3.3 V、5.1 V 和回流电源针脚；24 V 与 MCU_VIO 也是外部供电责任，ERC 数量不代表全部缺口数。没有增加 PWR_FLAG。此处没有 PCB 布线、制造放行、上电或机械臂动作。

电路采用 TPS3431 的可编程 CWD，KEMET **C0603C121F5GACTU，120 pF ±1%、C0G、50 V**。按 ±30 ppm/°C、相对 25 °C 最大温差 100 °C，电容为 118.4436–121.5636 pF；再计本项目提出的 PCB 寄生 ≤5 pF 要求，TI 应用公式给出 **58.0716–70.9516 ms**。该数值是包含上述边界的设计计算；PCB 漏电、实际寄生、供电扰动还须验证。原来的 170–230 ms 固定超时不再作为故障检测窗，170–230 ms 仍是器件故障/重新使能保持时间。心跳下降沿间隔要求 ≤30 ms，高低脉冲均 ≥100 µs，由实际控制任务的健康判定触发。

WDO、ENOUT 和三个 TPS3808 欠压输出并联在 FAULT_N_RAW。施密特门整形后同时清除 ARMED、RUN 和 HB_SEEN；EN 禁止时，即使 WDO 高阻，ENOUT 仍把故障线拉低。3.3 V、5.1 V 和停止控制 24 V 均参与欠压锁止。24 V 监测采用 TNPW0805510KBEEA 与 TNPW060310K0BEEA 分压；510 kΩ 使用 0805，因为同系列 0603 上限 332 kΩ。

两片 SN74LVC74A 实现“首次有效心跳下降沿 → 显式 RESET → 释放 RESET → 新 START 上升沿”。PRE 固定接高，未用触发器明确清零。RESET 保持高时 RUN 一直被清零；故障恢复、START 保持高、心跳恢复都不会单独产生新的 RUN。按钮的 RC 加施密特电路已画入，按键按下/释放至少 100 ms 是样机操作约束；实际按钮抖动和电源斜率尚未实测。

线圈功率级为 UCC27517DBVR 与 IRL630PbF（200 V，TO-220AB），低边开关只切 X2−；X1+接受保护的上游 24 V。U119 SN74AHCT1G125DBVR 将 3.3 V RUN 电平变成同 UCC 电源域的 5.1 V 电平。AHCT 输入漏电在 VCC=0–5.5 V 条件下有界，不能将它说成具有输出 Ioff。UCC IN−直接接地，避免其内部上拉向未供电的 3.3 V 输出反灌。200 V 额定与 32+55=87 V 只构成额定筛选；电缆感性尖峰、负 VDS、短路和热条件未由此获得放行。保留 GX11 内部抑制，**不并接外部线圈二极管**。

LVC RUN 输出负载模型上界 79.079 µA，落在其 100 µA 规格内；它到 AHCT 的高电平裕度已有规格依据。AHCT 到 UCC 在未计 UCC 内部输入下拉电流时，分压后保守值为 3.44177 V。UCC 未给出的输入电流上界仍需补证；要保持 ≥2.4 V，实际 IN+吸收电流必须满足计算文件给出的约 1.13 mA 上限。不能把无负载分压值称为完整最坏情况保证。

GX11 辅助触点由 **5.1 V ±1%（5.049–5.151 V）**润湿，10 kΩ 下拉电流约 0.495–0.526 mA。这是一项新的外部电源最低值要求，未套用 PDU “5 V”标称值。T2 为馈电、T1 为返回，U113 接收 5 V 电平、向逻辑输出 3.3 V；辅助触点不是认证镜像触点。母线电压 ADC、阈值、焊死判别与时间窗仍由外部监测器负责，**BUS_MONITOR_OK 是已诊断健康状态，不是母线有电信号**。未接该端口时下拉禁止启动。

外来心跳先经带 Ioff 的 U115。给外部 MCU 的三个状态信号经 U116–118 开漏缓冲，只有同一接收 MCU 电源域的 MCU_VIO 可以上拉。STOP 电源掉电而 MCU 存活时，开漏输出可能读高；接收软件必须将失效供域/失联/无新鲜观测作为 UNKNOWN，不能仅凭状态电平允许动作。这些输出是观测端，实际停止允许链不从它们旁路回接。

现行生产源是 `../tools/stop_circuit_build_r2.py` 和 `stop_circuit_verify_r2.py`；无后缀生成器保留为此前开发版本，不能覆盖本页。器件封装在 BOM 中保留参考，未核验焊盘的 footprint 属性未写入原理图，以免把猜测的土地尺寸带进 PCB。本页仍需完成：受保护的实际供源、实际 MCU/GPIO 与健康诊断绑定、连接器和按钮型号/线束、PCB 与间距/回流、全温短路/瞬态/热测试、实际母线和触点测量。它是单通道工程样机候选，不具有 SIL/PL 或飞行鉴定结论。

GX11 来源勘误：原厂 Rev6 第 2 页 “COIL RATINGS at 25°C” 的 C 列，原文是 “Release Time, Max (ms)”，数值 12；此前把它写成 typical 不准确。官网二进制下载返回 403，本地保存的是原厂文本回执 SHA，不能编造 PDF 哈希或宣称已经完成原表图像核验。整链 0.1 s 合格仍未证实。

独立网表审查进一步计入 AUX 接收器 ±5 µA 漏电后，润湿电流范围为 0.490–0.530612 mA，开路输入上界 0.0561 V，闭合输入下界 5.0439 V；这些仍是边界计算。独立审查报告位于 [STOP_CIRCUIT_REVIEW_ZH.md](../review/STOP_CIRCUIT_REVIEW_ZH.md)。

原厂资料：[TPS3431](https://www.ti.com/lit/ds/symlink/tps3431.pdf)、[TPS3808](https://www.ti.com/lit/ds/symlink/tps3808.pdf)、[SN74LVC74A](https://www.ti.com/lit/ds/symlink/sn74lvc74a.pdf)、[UCC27517](https://www.ti.com/lit/ds/symlink/ucc27517.pdf)、[IRL630](https://www.vishay.com/docs/91303/irl630.pdf)、[AHCT 电平缓冲](https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf)、[状态开漏缓冲](https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf)、[定时电容规格](https://search.kemet.com/download/specsheet/C0603C121F5GACTU)。实际下载和 SHA 见 [17 份原厂 PDF 锁定表](sources/FINAL_SOURCE_LOCK.json)。
