# WP09R 服务星与 B601 DM：原生装配、电气与推进设计增量

2026-09-08。已接续用量中断完成本轮设计增量和文件交付。**整机详细设计仍有尚未完成的工程责任，当前不能签发总体机电设计完成。** 从 [统一查看页](REVIEW.html) 打开三态装配、两页电气原理图及具体证据。

## 实际交付

|对象|本轮完成|证据与边界|
|---|---|---|
|SolidWorks|三态各873叶零件、10个固定容器；19个唯一子装配；已保存、冷重开并实际搬迁复验|[原生回执](results/NATIVE_DELTA_DELIVERY.json)；1254为实体继承口径，新增138唯一件实读；不冒充全体实体重测或运动配合完成|
|停止电路|71器件、222已接脚、39网；120pF看门狗、复位/启动锁存、线圈驱动与辅助反馈|[电路说明](electrical_delta/README.md)；420项设计检查、837项独立检查含178个稳定逻辑场景，未做板级瞬态/硬件验证|
|系统电气|实际子页与设备接口集成；94元件、96网、72条外部接线；分层BOM|[两页原理图](ecad/exports/WP09_SYSTEM_AND_STOP.pdf)、[主接线表](ecad/MASTER_FROM_TO.csv)、[BOM](ecad/MASTER_BOM.csv)；191项网表检查；ERC仍3项供源问题|
|B601 DM|官方MotorBridge0.5.3 DLL实际加载与18项边界ABI检查；七个电机的公开型号/ID绑定|[软件说明](software_native/README.md)；真实DLL，未重编Rust、未运行原生MIT编码/串口后端，硬件I/O=0|
|推进|C-POD安装螺纹、PDU200源侧针位、电压/脉冲预算合同及20项检查|[推进接口增量](propulsion/resume_20260908/README_ZH.md)；.112-40 UNC-2B；实际推进模块针表/喷口/协议ICD仍未取得|
|质量|873实例/43责任owner结转；未知数值保留null|[质量账](review/MASS_ASSIGNMENT_873.csv)；472实例数值未闭合，全星质量/质心/惯量未知|

## 原生文件

- [WP09D_SERVICE](cad/WP09D_SERVICE.SLDASM)
- [WP09D_PARKING](cad/WP09D_PARKING.SLDASM)
- [WP09D_RELEASED](cad/WP09D_RELEASED.SLDASM)

- [873叶原生装配完整ZIP](mechanical/WP09D_NATIVE_873.zip)
- [系统电气、停止电路、DM与推进增量ZIP](electrical_reference/WP09_ELECTRICAL_RESUME.zip)
- [原705组件便携母版回执](results/PORTABLE_DELIVERY.json)
- [电气迁移验证](results/ELECTRICAL_RESUME_DELIVERY.json)

完整解压到短本机路径，再用SolidWorks打开总装；保留全部子装配/零件目录结构。新10个父容器变换为恒等，不重定义叶零件的源坐标。固定三态几何与冷读通过不能替代真实装配、机构运动、强度或载荷验证。图片若显示不可用，以文件和实际回执为准，未从旧模型替补新视图。

太阳翼采用4.5mm叠层步距，修订8边框与24旧实例并加入168面层实例；R01的128紧固件更换为绑定标准的几何代理。84 CIC仅表示玻璃投影，另84胶层的材料仍未绑定；螺纹代理不表示制造螺纹。指定六矩形面层四段路径776个连续区间的下界0.30064349mm保留，范围不包括完整框销、整星、臂、活动线束或焊片。8边框采用同内核回导与双向布尔差证明形状等价，没有将SW原始质量标量差异伪记为通过。

## 电气与推进的关键修正

Seeed公开DM配置将J1–J3定义为4340P，J4–J6及夹爪为4310，ID1–7/反馈0x11–0x17；默认通用配置指向RS，因此当前明确引用DM专用文件。公开参考不能代替实机方向、零位、限位、针位与固件。921600 baud的30字节TX格式下，七轴各500Hz需113.93%理想TX能力，不成立；250Hz臂轴+50Hz夹爪仅是预算例。

停止电路已用120pF定时电容修正此前170–230ms候选的不足。58.0716–70.9516ms定时窗包含声明的寄生范围，未包含未测板漏电。UCC输入吸收电流上界未知，驱动电平证明仍需≤1.12765mA条件。GX11原厂25°C表的12ms为释放最大值，旧“typical”已有勘误；全温停止、母线监测/故障诊断、PCB以及整链100ms仍未完成。

C-POD两个同料号同Rev的公开表冲突继续按各自来源分别保留。安装螺纹已排除M3；公开投影的两个2X标签不能直接固定总孔数。PDU200的12V/2A是单通道限额，两个并联针不是两个2A通道。MIB与阀响应时间分账，不据此编造允许的命令脉宽、并发喷口或CRC协议。

## 当前尚未完成的工程责任

[统一验收表](review/SYSTEM_ACCEPTANCE_MATRIX.csv) 当前有23项开放工作包；这不是原子要求计数或功能覆盖百分比。[机器状态](results/DELIVERY_STATUS.json)保留完整设计为false。仍需完成星上高功率支路的充电/BMS/均流/瞬态/热设计，两条停止辅助电源、实机接口、母线测量及PCB，受控推进ICD及任务分配，完整线束端接/动态弯曲/裁线，以及全星质量/热/强度/运动核验。已有公开资料允许关闭的子项已落到文件，剩余项没有改名为到货检查或未知填零。

资源保护采用启动可用内存2048MiB、运行可用512MiB和Python+自有SW组合RSS1400MiB采样门槛。触发后清理确认自有CAD，分批保存并用隐藏文档冷读；未关闭不明或用户未保存进程。采样保护不能保证绝不发生资源错误。[资源回执](results/MEMORY_CLOSEOUT.json)。

原24项物理检查仍未执行；未采购、制造、接电、动作、充装或承压，未给予飞行鉴定结论。原始705父包及1128份上游文件哈希保留；[完整性回执](results/FINAL_INTEGRITY.json)只证明文件完整性。

[原生装配说明](mechanical/ASSEMBLY_DELTA_ZH.md) · [电源计算](power/POWER_DESIGN_UPDATE.md) · [停止独立复核](review/STOP_CIRCUIT_REVIEW_ZH.md) · [DM独立复核](review/DM_NATIVE_REVIEW_ZH.md)
