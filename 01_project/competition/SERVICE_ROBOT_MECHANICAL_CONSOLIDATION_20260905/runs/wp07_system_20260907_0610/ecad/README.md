# WP07 电源、通信与 ECAD 机电接口审阅包

这是可装配工程样机的接口设计草案。16 个功能域全部登记，实际硬件型号回复待收；电源转换、保护、电流、导线、接头针脚与设备热界面尚未完成。检查结果的一致性通过不等于电气完成、上电许可、制造放行或飞行资格。

- `ELECTRICAL_INTERFACE_REVIEW.html`：电源、通信、调试、搭接关系图。端点有固定 ID，虚线全部是待实现的逻辑关系；转换、隔离策略、保护、释放驱动用待选型方框表示。
- `ELECTRICAL_INTERFACE_CONTRACT.json`：16 功能域的条件化字段、连接端点、禁止直连的电压域、六项去重后的最小输入依赖。
- `ELECTRICAL_MODULE_MATRIX.csv`：按用户统一 M01–M16 功能域建立。功能域不是互斥实体分组，不对共用预算盒重复计质量。
- `ECAD_REFERENCE_CARDS.json`：四个真实 ECAD 源的外形、板厚、钻孔、源坐标/行号、连接焊盘网络、文件 SHA、本地 Git HEAD 和许可来源。
- `PCB_REFERENCE_MECH_CARDS.html`：上述实际板边与钻孔的二维可视化，保留原 PCB 坐标。裸板尺寸不代表已装设备包络。
- `ELECTRICAL_SOURCES.json`：原始文件 SHA、精确行号、原文摘录。冻结源全程只读。
- `../results/ELECTRICAL_TOOL_DISCOVERY.json`：PATH 和四个明确安装目录的有限 KiCad 探测；无软件安装、无 ECAD 进程执行。未找到不代表全盘证明未安装。
- `../results/ELECTRICAL_MECHANICAL_FIT_SCREEN.json`：四块参考裸板对现行六个设备预算外包络逐一枚举六种轴对齐方向。预算盒不是已证明的内腔；未计元件、支柱、接头和线弯，不推断任意倾斜不可安装。结果用于选型后修改安装架/预算，不允许缩放 PCB。

## 条件化字段与最小输入

M01 总布置、M02 主次结构没有独立电气负载，不要求电流或针脚；其未完项是设备分配、安装与接口可达。M14 当前只要求搭接/回流及设备热界面；没有选定加热器或风扇，不能假造主动热控负载。M09 背板、M13 线束是被动配线接口，电流表示承载支路需求，不是自身消耗。线径由 M13 单一负责，其他模块向其提交支路需求。

六个最小依赖输入组为：EI01 实际硬件/版本；EI02 状态负载与能源表；EI03 电源转换和保护；EI04 唯一逐针接线表；EI05 真实热界面；EI06 板卡/设备安装绑定。机械分配未完项与电气缺输入分开报告，不把机械结构当成缺少独立电源的设备。

## 已知来源与边界

B601 DM 本地厂商资料写 DC 24 V。可选 LRS-350-24 的 14.6 A 是地面电源额定值，不能代替臂实测/持续/峰值电流。厂商库当前版本与 WP02 冻结版本不同，accepted 模型到当前 OEM 硬件的注册仍待完成。

OreSat 背板参考母线为 6.0–8.4 V，不能与 B601 24 V 直接混接。PyCubed 3.3 V 稳压支路旁的 VBATT 4.5–18 V 注释不是整板允许输入范围；该电路同时有 2S 电池 8.4 V 浮充和 400 mA 太阳充电注释。VSOLAR 9–40 V 也不是 24 V 电机输出能力。

第三方板卡和针脚均为参考，未选为 WP07 硬件。图中隔离是否必要、隔离方式和 DC/DC 拓扑均未最终裁定。源码没有在本项目执行 ERC/DRC，未检查所有元件库/3D模型依赖，也未声明导体载流、EMC、热性能、辐射或环境合格。

## ECAD 几何提取方法

自有标准库解析器只读取 KiCad S 表达式。板外形来自实际 `Edge.Cuts` 直线/圆弧/矩形/圆，使用圆弧轴向极值求包围范围；支持太阳板板形足迹内的 Edge.Cuts 和足迹位置变换。孔来自明确 MountingHole 足迹中的实际 drill；太阳板八孔来自其板形足迹 NPTH，保留“安装意图需审阅”标记。没有按孔名字写入标准尺寸。

坐标为源 PCB 的 X 向右、Y 向下、单位 mm。`center_outline_min_mm` 仅是相对于实际外形最小坐标的派生值，不改变源文件。端点聚类闭合容差 1e-5 mm；边端点闭合不是无自交、无间隙、DRC 或制造验收。所有 `T_S_PCB`、已装元件高度和实物选型仍为空。

许可来源随卡记录。PyCubed 仓库 README 写 CC-BY-SA-4.0，而 battery-v01 README 另写 CC-BY-4.0；v01b 的适用许可需在实际派生前按文件范围复核。OreSat 按相应 README 的 CERN-OHL-S-2.0 记录。本包只做来源解析与接口研究，不将第三方许可/来源声明改写为自有设计。

## 复核

在项目根目录使用现有 Python：

```powershell
& 'G:/Windows_program_file/Anaconda/python.exe' '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/tools/check_electrical_contract.py' --self-test
```

默认退出 0 仅表示“草案一致且仍阻断”，报告为 `CONSISTENT_DRAFT_ELECTRICAL_COMPLETION_BLOCKED`。加 `--require-ready` 时，当前缺输入状态退出 2；不会给上电或电气完成信用。检查器核对来源字节/原文、派生文件与生成回执、模块条件字段、矩阵、端点和电压域。内存负控验证未知值填充、假选型、假完成、上电绕过、24 V 直接接 6–8.4 V 及删除活动模块必填字段均被拒绝。

`build_electrical_package.py` 只重建本目录自有派生文档和 `ELECTRICAL_*` 结果；不修改冻结源，不执行其代码，不启动 KiCad/CAD/COM/硬件。重建后应重跑检查器，以便全部哈希绑定到新一轮实际内容。
