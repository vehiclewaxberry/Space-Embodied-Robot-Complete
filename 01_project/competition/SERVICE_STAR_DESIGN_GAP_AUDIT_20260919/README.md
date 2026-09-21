# 服务星主要分系统完成度与缺口推进清单

日期：2026-09-19。审阅基点：`669ce052411971415cddccccfacf70dd486c09ba`。
近期目标：**按 owner 本轮选择，先闭合可装配、可上电的地面工程样机。**
这是派生评审与工作包建议，不是机器 Gate、采购批准、实物上电许可或飞行放行。未启动 CAD、ECAD 写操作、数值仿真、实物动作或厂家联系。

## 1. 专业判断

**主要分系统已有构型、候选器件和局部验证，但完整地面工程样机的同版本详细设计及采购级 BOM 尚未完成；可上星服务星的完整设计也尚未完成。**

“阶段一全部收口”准确覆盖 R01、R07-E1–E4、R17 和验证器/R14 的局部候选与复验链。它不覆盖整星采购、全机安装、真实载荷、电气故障行为和实物验收。已关闭的局部问题应继续复用，不重复列为待设计项。

- **机械：局部数字装配成熟，全机详细设计未闭合。** WP03 结构态 487、全态 497，R01 与 E1–E4 已有独立复验；保持器第6边 A/B 输入、同版本全机回装、实际机械臂物性、载荷与制造资料仍开放。后续 WP10 的 873 原生宿主/974 源计划是另一条表示链，不能直接以“497 是最新数量”覆盖。见 [移交记录](../../../01_project/competition/移交_ELECTRICAL_PROPULSION_INTEGRATION_HANDOFF_20260919.md)、[机械基线](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/baseline_load_closure_v31/mechanical/MECHANICAL_BASELINE.json)。
- **电气：三板已有设计及规则检查，采购与功能验证未闭合。** STOP 已布线，MAIN/AUX 也有各自检查；STOP 的 DRC 0/0 有 5 条声明忽略规则，`STOP_PCB_implemented=false`。V35 记录 `power_on_release=false`、`hardware_tests=0`，V36 的局部增量不能代替整机上电实证。见 [V36 工作修订](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/ecad/revisions/v36/WORKING_REVISION.json)、[STOP 工程评审](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/results/stop_v36/pcb/verify_20260917/ENGINEERING_REVIEW_20260917.json)、[V35 范围状态](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/coupled_closure/DELIVERY_STATUS_V35.json)。
- **热控与辐射散热：已有热网络、散热面与视因子筛查，尚非定版。** 不能说完全没做热设计；但 B2 双纵梁每侧并联方案的 83.2–86.92°C 是条件反解，并未证明实际装配和全部热源下满足裕度。95°C 是该载板筛查硬限、85°C 是留 10 K 的设计目标；86.92°C 仍高于 85°C。这些限值不能当成所有器件统一温度上限。地面样机先按实际空气环境和负载完成可安装散热方案及温升验证。见 [B2 设计目标](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/results/thermal_architecture_20260917/THERMAL_ARCHITECTURE_B_DESIGN_TARGETS_20260917.json)、[架构筛查](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/results/thermal_architecture_20260917/THERMAL_ARCHITECTURE_B_SCREEN_20260917.json)、[网格视因子筛查](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/thermal/RADIATOR_MESH_VIEW_SCREEN.json)。
- **空间辐射防护：未找到当前构型完整的环境—器件—验证闭环。** TID、单粒子效应、屏蔽与容错应在飞行线单独完成；不以“存在散热板”推定抗辐射设计完成，也不把未找到证据写成项目从未研究过。
- **推进：贸易研究完成，真实系统选型未冻结。** 8 候选及 9 项跨候选缺项已登记，B1/B20/HPGP 1N 的局部筛查通过不等于适配本任务；`selection_frozen=false`、`mission_budget_closed=false`、`hardware_qualification=false`。地面样机可先确定质量/安装/电气模拟方式，真实推进采购和压力/推力试验单独推进。见 [推进矩阵](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/results/propulsion_trade_20260917/PROPULSION_TRADE_MATRIX_20260917.json)。
- **具身智能、姿控与测控：需要单列系统级接口闭合。** 有边界符号、设备候选或历史预算不等于已落实算力、相机/力觉、时间同步、总线、失联停止及实际姿控能力。当前选型表中的 OBC 为模块边界；这不否认其他目录的候选，要求把选定实物与本次样机明确绑定。见 [选型表](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/results/electrical_selection_20260917/SELECTION_BOM_V36.csv)、[端点映射](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/ecad/SYSTEM_ENDPOINT_MAP.json)。
- **Master BOM：尚不具备一张表直接下单并装出同版本整机的条件。** 需要统一机械加工件、标准件、三板器件、线束、热件、工装和商业模块，区分随星与地面设备。

这里区分两个物理问题：真空中的热控依靠传导和辐射，需要热源、环境及光学边界；空间粒子辐射保障则涉及环境、器件选择/试验、布局和容错。通用评审依据为 [NASA 小卫星热控](https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/)及 [NASA 抗辐射保障说明](https://www.nasa.gov/centers-and-facilities/nesc/avionics-radiation-hardness-assurance-for-safe-exploration-beyond-low-earth-orbit/)。这些参考不替代项目验证。

## 2. BOM 的具体缺口

### 2.1 机械账与采购账

[WP03 BOM](../../../20_engineering/service_robot_wp03_spacecraft_body_r1/BOM.csv) 为 497 行、15 列，214 项分配质量、283 项未分配质量保持 null/空单元。它主要负责实例、用途、来源及质量分配，没有完整的厂家/订货码、采购数量汇总、公差、加工材料和工艺等采购发布字段。

**283 个 null 不是“缺 283 种器件”，也不能用零填来宣布完成。** 497 实例不是 497 个物料品种；通用物料应在保持实例映射的前提下汇总采购数量。

### 2.2 电气 45 行与其他缺项

[SELECTION_GAPS_UPDATE2](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/results/electrical_selection_20260917/SELECTION_GAPS_UPDATE2_20260917.json) 将 rating/substitution 缺口从 224 降到 45：
- 38 行系统侧无 MPN 占位/裸值，必须确认真实订货码。
- 3 行系统 IC 已指明型号但缺归档手册：U207 TPS26600PWPR、U303 MAX5048CAUT+T、U304 MAX16053AUT+T。U304 的 MPN 列仍空，型号在 value/说明中，因此按字段机械计数是 39 行 MPN 空值。
- 4 行 STOP 归类 UNKNOWN：U101 TPS3431SDRBR、U311/U312/U313 TLV6700DDCR，需完成对应手册/额定著录。

25 个模块/边界或退役符号与 224 个真实器件行合成选型表 249 位号；模块边界应绑定受控 ICD，不应硬塞一个芯片 MPN 来消除空值。`source=61`、`footprint=53`、`model=40` 为后续文件明确保留的其他缺口类别；它们与 45 行有交叉，**不能相加为 199 个不同器件**。既有手册或候选资料需核对并回写同一受控 BOM 才算该字段闭合。

逐行附件：[ELECTRICAL_45_GAPS.csv](ELECTRICAL_45_GAPS.csv)。此文件是原缺项的任务化摘录，未新增“已选定”结论。

### 2.3 推进 9 项的正确使用

附件 [PROPULSION_OEM_GAPS.csv](PROPULSION_OEM_GAPS.csv) 原样摘录矩阵的 9 项。它们跨越不同候选，最后一项还涉及项目羽流/质心与力臂分析；不是某一已选推进器都必须向厂家询问的 9 个通用字段。先明确选择条件与短名单，再判断适用项并关闭；已有厂家资料、项目计算和试验分别承担自己的证据责任。

冻结参考数字保持原口径：|H_c|=3.65 N·m·s，2×12 mN@0.17 m，推进剂预算54.735 g，42.9 N·s为目录盒假设下的总冲量下限。它们尚不能作为当前安装候选的已验证能力。

## 3. 地面样机逐项工作包

详细输入、产物、完成判据、建议负责专业与依赖见 [GAP_ACTION_REGISTER.csv](GAP_ACTION_REGISTER.csv)。P0 是先明确的关键输入，P1 为详细设计/采购资料，P2 为集成或功能验证。优先级不表示可以省略前面的设计工作；G15 的测试计划现在即可准备。

1. **G01｜P0｜统一版本。** 选择唯一整机宿主，建立 WP03 新紧固增量与 WP10 873/974 的映射，并处理 HANDOFF 中 WORKING_REVISION 哈希失配。
2. **G02｜P0｜核实实物 B601/DM。** 明确修订、逐关节型号、驱动与零位限位、重量组成和电流/停止参数。三个来源的臂质量不能直接互换。
3. **G03｜P1｜全机数字回装。** 安装三板、端子、线束、热路和推进代表件，检查孔位、工具空间及维护路径；不重复推翻已接受的 R01/E1–E4。
4. **G04｜P1｜机械加工与采购资料。** 定制件有可加工图纸；标准件有规格/等级/长度/数量；实际地面载荷与连接预紧有依据。
5. **G05｜P0｜地面工装和保持器。** 先定义固定/卸载方式、重力反力与失电状态，取得 A/B 接触刚度/预紧/装配误差输入。
6. **G06｜P1｜线束和动作路径。** 补逐端针号、线规、端子、长度、屏蔽、弯曲余量和导通检查；只验证实际准备执行的路径。
7. **G07｜P1｜电气选型缺项。** 逐行完成 45 项及其他缺项；把原理图引脚、封装焊盘、器件订货码绑定。
8. **G08｜P0｜地面电源与负载。** 可先以外部稳压电源作为候选，按实际电源能力、臂负载及峰值/启动/保持负载闭合电流、电压、压降和保护；不用在轨充电闭环阻塞地面样机。
9. **G09｜P0｜停止和回生。** 取得 K1/Q101 实际线圈与 DM 回生数据，覆盖掉电、短掉电、人工再启动、开关/保险配合和最坏回生能量。通信超时、陈旧命令、越限和失联停止属于所有手动/遥操作动作的基本验收，不等到 G13 自主功能再处理。
10. **G10｜P1｜三板制造与板级验证。** 同版 ERC/DRC/网表/制造输出对账；Q201 颈部偏差的接受记录不等于载流和温升实证。
11. **G11｜P1｜地面散热。** 分为 A 设计准备和 B 上电后热验收：A 先完成可安装热路、TIM 压紧、测温点和预估温升，冻结温度限值/停机阈值；B 在 G15 受限上电后逐步实测。首次上电不以已完成实测温升为前提，达到声明最坏工况前须逐级复核。空气环境结果不转用于真空。
12. **G12｜P1｜推进地面代表方式。** 建议先选无推进剂的质量/接口模拟器，验证安装、惯性和命令接口。是否改做真实推进功能试验留作此工单的 owner 决策，本轮未执行或购买。
13. **G13｜P2｜具身智能功能最小链。** 根据具体演示任务落实算力、相机/力觉、编码器、总线、标定和时延。它不阻塞基础无动作板级上电，但须在自主动作演示前完成。
14. **G14｜P1｜Master BOM 和库存。** 合并各分系统采购/加工清单，建立实例映射、物料数量、库存、替代及交期来源。
15. **G15｜P2｜分级装配与上电验收。** 无源装配 → 极性/导通 → 分板限能上电 → 代表负载与故障响应 → 受控低速动作 → 声明最坏工况与热验收。每一级有记录和独立审阅；本文件本身不触发任何硬件动作。

G15 的入场条件按级落实：无源阶段检查安装/接线/绝缘和极性；初次分板上电要求 G09/G10/G11 的设计准备通过、测量与保护可用；初次动作前要求停止、失联/陈旧命令/越限响应已经实际验证。电气与热控负责人共同冻结各级电压、电流、温度、通信超时和动作范围的数值限值、停机条件与观测时长，未冻结则不进入该级。G11-B 热实测在此流程中闭合，不与首次上电互设完成前置。CSV 中 `:design_ready` 明确表示设计准备阶段，不表示整个工作包已关闭。

第一批建议并行取输入：**G01、G02、G05、G08、G09**。同时可整理 G07 的既有手册和候选资料，不需等全部 CAD 完成。
第二批推进 G03/G04/G06/G07/G10/G11/G12，再汇总 G14。热、电、机械修改存在反馈，应在 G15 前统一重验，不能把这里的依赖图当成“一次算完不再迭代”。
G13 在基础电控与停止链可用后按演示目标推进；自主功能不作为“基础上电成功”的同义词。

## 4. 飞行后续差异

以下 F01–F07 在表中标为 `DEFERRED_FLIGHT_SCOPE`，不作为本轮地面样机全部前置要求：

- **F01** 轨道、寿命、日照/地影、目标任务与实际部署器/发射收拢。
- **F02** 太阳阵列—充电—电池—负载全轨能源周期，含寿命末期与低温边界。
- **F03** 真空热路、辐射面、MLI/涂层、冷热轨道瞬态与热试验相关。已有面积/视因子和稳态筛查继续复用，不从零重建。
- **F04** TID/SEE、器件等级/容错、屏蔽、真空材料与润滑适应。
- **F05** 真实完整推进模块的任务适配、储箱/阀/管路/推力器实选及压力/泄漏/推力验证。
- **F06** 真实轮组与姿态传感器、喷口分配、捕获后质心和惯量、禁喷/最小脉冲/并发约束。
- **F07** 同版本飞行环境验证与整星鉴定。

地面样机采用的外部电源、普通材料、模拟推进器或计算机应保留“地面用途”身份。以后转上星需重新评估适用性，而不是把本轮地面结果迁移成飞行 PASS。

## 5. 采购级 BOM 最低字段

每行至少需：物料ID、所属装配/实例、制造或采购、用途（地面/随星/模拟器）、厂家与完整MPN或图号修订、描述、数量与单位、材料/封装、关键额定及降额、来源/手册版本、配对件与接口、允许替代条件、采购/库存状态、未决项和验收方法。
定制件增加公差/表处/工艺；线束增加线规、端子、长度、屏蔽和from-to；热件增加材料、厚度、面积与压紧/热阻条件；推进增加受控ICD和适用试验范围。
本轮没有询价或锁定库存，不能把公开候选标为“已采购”。

## 6. 交付与边界

- [详细工作包](GAP_ACTION_REGISTER.csv)：15 个地面工作包 + 7 个飞行后续工作包，均未因本次评审获得关闭信用。
- [电气45行缺项](ELECTRICAL_45_GAPS.csv)：保留原位号/板卡分类/型号字段，附待办与验收。
- [推进9项摘录](PROPULSION_OEM_GAPS.csv)：保留原文，补适用范围提示。
- [来源索引](SOURCE_INDEX.json)：源路径、审阅时字节哈希和外部参考；仅用于导航与回溯。
- 每份交付物有 `.sha256` 边车，路径相对此目录。CSV 为 UTF-8，可导入 Excel。

本轮是选择性专业评审及缺口整理，非全仓逐文件穷尽审查。现有机器裁决、issues、CURRENT/HANDOFF 指针、设计参数、BOM 与原始证据未改写；既有负结果及 UNKNOWN 原样保留。

独立硬件审阅提出的两项流程修订已落入 G09/G11/G15：基础动作的失联/陈旧命令/越限停止不依赖可选自主功能；设计准备与上电后热实测分阶段关闭，明确数值限值责任与每级入场条件。该审阅针对清单可实施性，不赋予硬件通过信用。
