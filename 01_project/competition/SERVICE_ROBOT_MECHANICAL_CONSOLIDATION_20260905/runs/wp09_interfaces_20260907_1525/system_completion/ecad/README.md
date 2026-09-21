# 系统电气与实际停止电路

此目录为现行系统电气增量。打开 [两页原理图](exports/WP09_SYSTEM_AND_STOP.pdf)，或用 KiCad 10 打开 [原生系统原理图](wp09_system.kicad_sch)。本地符号库及实际子页随目录提供。

系统图有 94 个元件（23 个设备/接口表示及 71 个实际停止电路元件）、96 个导出网络；[主接线表](MASTER_FROM_TO.csv) 有 72 条外部连接。保留父版 70 个 wire_id，其中四条 K1 线改接实际停止板，新增保护后 24 V 供电及回流。板内 183 条连接由 electrical_delta/STOP_FROM_TO_DELTA.csv 负责，不作为第二份外部主表。STOPBOARD 是同一子电路的顶层接口表示，不是另一块重复采购的设备。

[实际网表检查](../results/STOP_ECAD_INTEGRATION.json) 通过 191 项连接、分层端口及原身份检查。实际 ERC 仍有 3 项供源错误：切断后 U1.IN+ 边界、停止板 3.3 V、停止板 5.1 V。新接线绑定了保护后 24 V 和回流，未给两条辅助电源虚构供源标志。MCU 接口电压域、母线健康测量、完整 PCB 和连接器配对仍未完成。

[停止电路说明](../electrical_delta/README.md) 记录具体器件、可编程看门狗、复位/启动逻辑、线圈驱动及反馈。稳定逻辑计算不包含板级模拟瞬态、全温实物延迟或功能安全认证；整链 100 ms 未通过。5.1 V 指其设计供源需求，不能改称已实现的 5 V 电源。

[分层 BOM](MASTER_BOM.csv) 与 [计数说明](MASTER_BOM_NOTES.md) 区分顶层设备和子电路实件，未选料号保持明确待定。未执行硬件 I/O、生产或上电。

现行电气主表仅为此目录 MASTER_FROM_TO.csv；reuse_closure 的同名文件保留父版历史身份。完整机电设计仍由 [总交付状态](../results/DELIVERY_STATUS.json) 约束。

