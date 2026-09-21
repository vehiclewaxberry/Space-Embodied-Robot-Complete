# 推进硬件候选与安装准备

本目录是推进设计入口和装配准备，型号尚未冻结；没有已完成的储箱/阀/管路/喷嘴工程设计或点火资格。总装中的相关对象是接口和空间候选，不能视为已采购或厂家安装定版。

- [八候选比较](trade/PROPULSION_TRADE_MATRIX_20260917.json) 与 [比较说明](trade/PROPULSION_TRADE_STUDY_20260917.md) 保留筛选依据。B1、B20、HPGP 1N等推力窗口筛查不能替代总冲、功率、脉冲性能、并发与整星适用性。
- [WP09接口合同](interfaces/wp09/PROPULSION_INTERFACE_CONTRACT.json) 记录目录级CPOD等来源输入和UNKNOWN；不能直接移作其他候选的OEM ICD。[源侧接口表](interfaces/wp09/SOURCE_SIDE_INTERFACE_ROWS.csv) 与 [来源绑定](interfaces/wp09/SOURCE_BINDINGS.json) 只作精确来源记录，厂商全文不随包。
- [当前R6H准备参数](preparation/PROPULSION_ASSEMBLY_PREPARATION.json) 记录S坐标、保留对象及P60托盘局部变更、功能路线、机械/电气边界和9项OEM缺口。与 [机械总装](../01_mechanical/) 联合使用。
- [OEM输入模板](preparation/PROPULSION_OEM_INPUT_TEMPLATE.json) 与 [12项工作单](preparation/PROPULSION_NEXT_WORK_ORDERS.csv) 是下一阶段逐项设计入口。
- [电池/推进功能路线](routing/BATTERY_PROPULSION_ROUTING.json) 只是现有电源/数据路径参数；不是推进剂管路，也不是完成的OEM针脚连接。

仍待厂家闭合的内容包括指令最小脉宽、双喷并发、比冲/功率/总冲/干质量、孔位与实际配合接口、羽流和质心变化对力臂的影响。实际喷嘴位置/方向、禁入区、储箱、压力合同和全部接线尚未冻结，相关null不得填成零。4-40 UNC等厂家螺纹不能替换为M3假设。

本目录没有推进控制算法、在轨模式控制、动力学传播或研究论文。历史说明及JSON中的来源路径是原档案引用，未携带的源日志不是本包运行依赖。[逐文件来源](SYSTEM_COPY_MANIFEST.csv) 记录选入文件及原始哈希。
