# 本轮收束增量与开放项

快照：2026-09-07T07:36:54.027131+00:00。本文件是工程交付台账，不是科学 Gate 或制造放行。

**本轮已完成 V6 增量几何、Service/Parking/Released 三态固定姿态原生装配核验与供电参考选型；整机实物机械、电气回路和连续运动仍开放。** 当前共 11 项限定关闭、13 项 OPEN，原生三态无待完成项。后续状态以对应机器文件为准。

| 核对对象 | 本轮事实 |
|---|---|
| 增量几何 | 82 个新实例，266 对增量检查，未批准相交/功能冲突均 0 |
| 原生零件传递 | 21 个典型依赖覆盖 82 个实例，几何传递核验通过 |
| Service 原生装配 | 701 个组件 / 1082 个实体，固定姿态冷检查通过 |
| Parking | V3 固定姿态通过：701 组件 / 1082 总实体，新 82 实读＋旧 1000 哈希绑定 |
| Released | 固定姿态通过：701 组件 / 1082 总实体，新 82 实读＋旧 1000 冻结 WP08 哈希绑定 |
| 完整电气回路 | **0** |
| 预制检验 | **24 项，全部 NOT_EXECUTED** |

每个姿态的 701 组件清单由 **619 个 WP08 继承组件＋82 个 V6 增量**构成。WP08 后肋 11 实例局部组件与 WP09 前轮 A3200 局部细化未因此自动回装；电池原生 HOLD 维持。真实集成成员以 V6 合同/清单为准。

“原生 material transfer”仅表示实体体积与边界的导入传递核验，不代表材料选型或力学、热性能合格。Service 记录的 native_rebuilt=false，也不表述为本轮重新构建了全部原生特征。

## 已关闭的限定范围

### C01　DM 与地面/星内供电参考架构已确定

用户确认 B601 DM；当前选外置 RSP-500-24 驱动臂，BPX 8S + P60/PDU 承担低功率航电与推进参考支路；双 i7C-PC3 仅为后续研发。

依据：[SELECTED_DM_ARCHITECTURE.json](../ecad/SELECTED_DM_ARCHITECTURE.json)；[FINAL_SELECTION_DM.json](../research/FINAL_SELECTION_DM.json)。

范围：是工程参考选型，不是实物已采购、针脚已接线或上电许可；15 A 不是实测任务峰值，BPX 6 A 不是整套 EPS 已分配能力。

### C02　旧 MiPS 非承压接口设计基准已绑定

X14029003-1 Rev6/15 作为外形、外支撑和未加压等包络接口样件基准；原厂源文件与本轮来源绑定可追溯。

依据：[INTEGRATION_HARNESS_CONTRACT_V6.json](../inputs/INTEGRATION_HARNESS_CONTRACT_V6.json)；[PROPULSION_BOUND_SOURCE_BINDING.json](../results/PROPULSION_BOUND_SOURCE_BINDING.json)。

范围：不代表真实推进器供货、压力容器设计、侧向螺钉完整啮合、喷流或推进能力已完成。

### C03　V6 增量几何问题已清理并检查

82 个新几何实例已发射；V6 增量检查 266 对，未批准相交与功能冲突清单为空；584 项来源锁保持不变。

依据：[EMISSION_V6.json](../results/EMISSION_V6.json)；[INTEGRATION_CHECK_V6.json](../results/INTEGRATION_CHECK_V6.json)。

范围：范围是本轮增量；未做全量父件两两检查、连续运动、喷流或强度验证。

### C04　原生零件几何传递核验完成

21 个典型原生依赖覆盖 82 个实例，V2 material-transfer 检查通过。

依据：[NATIVE_MATERIAL_CHECK_V2.json](../results/NATIVE_MATERIAL_CHECK_V2.json)。

范围：此处 material transfer 是实体几何体积/边界的导入传递核验，不是工程材料、制造公差、强度或热合格认证。

### C05　Service 固定姿态原生装配恢复并冷检查通过

NATIVE_SERVICE_RECOVERY 报告 701 个组件、1082 个实体；新 82 实例基向量探针和全 701 变换读回，依赖集与实际体数核验通过。

依据：[NATIVE_SERVICE_RECOVERY.json](../results/NATIVE_SERVICE_RECOVERY.json)。

范围：本项仅引用 service 固定姿态证据；native_rebuilt=false，不宣称已重建全部原生特征或连续运动通过。Parking/Released 的独立完成证据分别列在 P01/P02，未从 service 继承。

### C06　两条静态 ICD 交接截面路线几何闭合

V6 PWR/DATA 的 R21 中心线实测长度分别为 316.97344572538566 mm 和 204.97344572538566 mm，解析值与发射曲线一致。

依据：[INTEGRATION_CHECK_V6.json](../results/INTEGRATION_CHECK_V6.json)；[POWER_CONDITIONS_RESULTS.json](../ecad/POWER_CONDITIONS_RESULTS.json)。

范围：端点是 ICD 交接截面；OD6 是设计占位；真实线种、端接余量、下料长度与弯曲工艺均未闭合。

### C07　ECAD 可复算文件与检验清单已建立

V6 ECAD 文件完成 22 项一致性核验，From-To、条件电流/压降计算与两路各 12 项预制检验清单均已交付。

依据：[ECAD_ARTIFACT_CHECK.json](../ecad/ECAD_ARTIFACT_CHECK.json)；[PROP_PWR_PREFAB_CHECKLIST.csv](../ecad/PROP_PWR_PREFAB_CHECKLIST.csv)；[PROP_DATA_PREFAB_CHECKLIST.csv](../ecad/PROP_DATA_PREFAB_CHECKLIST.csv)。

范围：文件一致性不代表物理电气回路完成；完整电气支路为 0，全部 24 项预制检验步骤 NOT_EXECUTED。

### C08　名义机械接口表和装配步骤已交付

外载架、P60 抬高托盘、分体导向件和护线套的名义位置、装配步骤及样件范围已有对应文档。

依据：[NOMINAL_ASSEMBLY_AND_PREFAB_ZH.md](../docs/NOMINAL_ASSEMBLY_AND_PREFAB_ZH.md)；[MECHANICAL_INTERFACE_TABLE.csv](../docs/MECHANICAL_INTERFACE_TABLE.csv)。

范围：名义尺寸文件不授予真实板卡固定、扭矩、材料、螺纹、锁紧或制造放行信用。

### C09　旧推进参考的标量必要条件已复算并绑定来源

历史 3.65 N·m·s 背景下的必要条件明确采用旧 44 N·s 和 5×0.01 N，源型号/单位/哈希独立绑定。

依据：[PROPULSION_CAPABILITY_BOUNDS.json](../results/PROPULSION_CAPABILITY_BOUNDS.json)；[PROPULSION_BOUND_SOURCE_BINDING.json](../results/PROPULSION_BOUND_SOURCE_BINDING.json)。

范围：乐观标量上界/时间下界不证明同时喷射、三轴力矩配置、平动抵消或消旋任务通过；不混用新代 82 N·s。

### P01　Parking 固定姿态原生恢复通过

Parking recovery V3 固定姿态原生检查实际通过：701 个组件、总 1082 个实体；82 个新实体本轮实读，旧 1000 个实体沿用 WP08 哈希绑定证据，全部 701 身份/文件/变换/固定状态核对，依赖集与冻结输入核验完成。

依据：[NATIVE_PARKING_RECOVERY_V3.json](../results/NATIVE_PARKING_RECOVERY_V3.json)。

范围：没有声称 parking 本轮重新读取了旧 1000 实体的体数；body_counts_are_actual=false。固定姿态通过不升级连续运动、工具可达、材料、电气或释放态状态。

### P02　Released 固定姿态原生检查通过

Released 固定姿态原生检查实际通过：701 个组件、总 1082 个实体；82 个新实体本轮实读，旧 1000 个实体沿用冻结 WP08 哈希绑定证据，全部 701 身份/文件/变换/固定状态按本姿态回执核对。

依据：[NATIVE_RELEASED.json](../results/NATIVE_RELEASED.json)。

范围：没有声称 released 本轮重新读取了旧 1000 实体的体数；body_counts_are_actual=false。三态固定姿态通过不等于连续运动、实际设备装配、电气回路、材料/力学/热或制造放行完成。

## 仍开放的接口和验证

### O01　既有 B601 CAD 与 DM 出货机械修订未核对 — OPEN

供电版本已确定；10 个继承 B601 几何实例仅标注 WP01 nominal BRep/accepted URDF，未绑定 DM 厂家 CAD 修订。

下一产物：绑定准确 DM CAD/BOM 提交与实际出货机械修订，形成逐接口差异表。

验收：基座、关节壳体、夹爪、固定孔、接插件与线束出口逐项有证据对照；匹配前不标 DM 几何 PASS。

依据：[B601_DM_GEOMETRY_PROVENANCE_NOTE.json](../research/B601_DM_GEOMETRY_PROVENANCE_NOTE.json)。

### O02　RSP→DM 保护、针脚与回生处理未完成 — OPEN

RSP TB2 正 4–6/负 1–3 已知；目的端针号、配对件、保护整定、任务电流和回生能量仍未知。

下一产物：专用保护/断电与回生设计、针脚级线束图和电流测试记录。

验收：真实接点与配对件可追溯；往返/触点电阻完整；保护与回生在限定负载下有试验记录。

依据：[SELECTED_DM_ARCHITECTURE.json](../ecad/SELECTED_DM_ARCHITECTURE.json)；[DM_SELECTED_FROM_TO.csv](../ecad/DM_SELECTED_FROM_TO.csv)。

### O03　BPX/P60 选件和全栈供电预算未完成 — OPEN

BPX 6 A 是模块限制；完整 Dock 选件/限制及公共航电负载未绑定，不能视为所有支路可用 6 A。

下一产物：明确 BPX 8S 订单、P60/PDU 12 V 选件、全栈电流与热预算。

验收：每级限制均绑定准确硬件；24 V PDU 的电池 >25.5 V 门槛不被忽略；臂负载不进入当前低功率支路。

依据：[SELECTED_DM_ARCHITECTURE.json](../ecad/SELECTED_DM_ARCHITECTURE.json)；[FINAL_SELECTION_DM.json](../research/FINAL_SELECTION_DM.json)。

### O04　P60 PCB 自身支撑孔未绑定 — OPEN

托盘 Z=53..55 mm，参考盒 Z=57.5..86.5 mm；2.5 mm 空隙和托盘支柱不证明 PCB 已固定。

下一产物：用实板孔位/禁布/器件高度及连接器 ICD 设计板卡支柱与绝缘件。

验收：实板每个支承点有孔轴、紧固/绝缘堆叠与工具通道；板卡无需悬空，接口不干涉。

依据：[INTEGRATION_HARNESS_CONTRACT_V6.json](../inputs/INTEGRATION_HARNESS_CONTRACT_V6.json)；[NOMINAL_ASSEMBLY_AND_PREFAB_ZH.md](../docs/NOMINAL_ASSEMBLY_AND_PREFAB_ZH.md)。

### O05　MiPS 成品固定和外部接口未闭合 — OPEN

当前为非承压外部载架与旧 OEM 包络；侧孔有效啮合深度、电连接器、针脚和精确供货版未知。

下一产物：绑定厂商完整 ICD，完善侧向螺钉/垫片和推进成品安装图。

验收：每个承载连接有有效啮合与禁触依据；供应商完整推进单元与本次模型修订一致。

依据：[INTEGRATION_HARNESS_CONTRACT_V6.json](../inputs/INTEGRATION_HARNESS_CONTRACT_V6.json)；[FINAL_SELECTION_DM.json](../research/FINAL_SELECTION_DM.json)。

### O06　Ø8 导向孔不构成 Ø6 线束夹紧证明 — OPEN

名义直径差 2 mm、径向间隙 1 mm，当前只能获得导向/布线路径占位信用。

下一产物：按实际线束直径与护套，设计内衬/应力释放和受控夹持结构。

验收：夹持不损伤绝缘，轴向保持、接头载荷隔离及装配工艺均有实测或已批准依据。

依据：[INTEGRATION_HARNESS_CONTRACT_V6.json](../inputs/INTEGRATION_HARNESS_CONTRACT_V6.json)；[NOMINAL_ASSEMBLY_AND_PREFAB_ZH.md](../docs/NOMINAL_ASSEMBLY_AND_PREFAB_ZH.md)。

### O07　完整物理电气回路为 0 — OPEN

真实接插件、配对端子、针号、线径、端接余量、绞合影响和下料长度仍未绑定。

下一产物：将 ICD 截面预布线升级为具体设备间 From-To 与可下料线束图/BOM。

验收：每行源/目的物理接点完整且协议正确；长度包含端接和服务余量，压降/发热基于真实往返回路与触点。

依据：[POWER_CONDITIONS_RESULTS.json](../ecad/POWER_CONDITIONS_RESULTS.json)；[From-To.csv](../ecad/From-To.csv)；[DM_SELECTED_FROM_TO.csv](../ecad/DM_SELECTED_FROM_TO.csv)。

### O08　24 项预制检验步骤尚未执行 — OPEN

电源与数据清单各 12 项，execution_status 全为 NOT_EXECUTED，结果为空。

下一产物：在材料/线种/端子/标准与测试条件绑定后执行两路预制及检验，保存逐项记录。

验收：24 项均有实际执行人、日期、测量/审查记录和对应判据；记录完整前不将文件一致性当作工艺 PASS。

依据：[PROP_PWR_PREFAB_CHECKLIST.csv](../ecad/PROP_PWR_PREFAB_CHECKLIST.csv)；[PROP_DATA_PREFAB_CHECKLIST.csv](../ecad/PROP_DATA_PREFAB_CHECKLIST.csv)。

### O09　工具可达与装配拆卸通道未验证 — OPEN

合盖状态服务空间未通过：front_service_cover 与设计维护棱柱的交叠为 15842.56960512 mm³，service/parking/released 三态均有；其余所检查候选体交为 0。棱柱仍是设计假设，真实工具未绑定。

下一产物：维护装配顺序先拆前盖；另绑定拆盖动作、紧固工具与插拔操作空间，建立可复查维护工序和路径检查。

验收：只有假设前盖已移除，现有棱柱剩余候选才无体交；还须证明前盖能拆出、每个紧固/插拔点有实际工具路径。合盖状态不得给服务空间 PASS，开盖条件结果不替代拆盖动作或工具可达证明。

依据：[FRONT_SERVICE_PRISM_CHECK.json](../results/FRONT_SERVICE_PRISM_CHECK.json)；[FRONT_SERVICE_ACCESS_CONDITIONAL.json](../results/FRONT_SERVICE_ACCESS_CONDITIONAL.json)。

### O10　材料、公差、预紧、防松、力学与热路径未完成 — OPEN

原生几何传递核验不替代材料与承载设计；长拉杆仅名义平滑代理。

下一产物：材料/表面处理/公差与螺纹规范、紧固预紧防松、结构载荷与热传导接口图。

验收：准确工况下完成材料可追溯、连接/强度/热检查；有依据的扭矩与公差才进入图纸。

依据：[INTEGRATION_HARNESS_CONTRACT_V6.json](../inputs/INTEGRATION_HARNESS_CONTRACT_V6.json)；[NATIVE_MATERIAL_CHECK_V2.json](../results/NATIVE_MATERIAL_CHECK_V2.json)。

### O11　连续运动及动态线束仍未验证 — OPEN

固定姿态检查不覆盖 B601/帆板运动中的线束、结构间隙或旧动态保持项。

下一产物：在 DM 几何与真实线束边界绑定后生成限定任务运动包络与连续路径检查。

验收：检查完整轨迹中的线束最小弯曲、拉伸、碰撞、接头载荷和可恢复性；不能由三离散姿态推得连续通过。

依据：[INTEGRATION_CHECK_V6.json](../results/INTEGRATION_CHECK_V6.json)；[NATIVE_SERVICE_RECOVERY.json](../results/NATIVE_SERVICE_RECOVERY.json)；[INTEGRATION_HARNESS_CONTRACT_V6.json](../inputs/INTEGRATION_HARNESS_CONTRACT_V6.json)。

### O12　喷流与可达推进力矩未完成 — OPEN

喷嘴位置/方向、系统质心、脉冲时序、喷流半角未绑定；同时喷射与矢量配置未核实。

下一产物：厂商喷口 ICD、喷流禁入区与有约束推力/力矩配置检查。

验收：可达力矩/平动和喷流明确评估；历史标量必要条件不当作消旋任务 PASS。

依据：[PROPULSION_CAPABILITY_INPUTS.json](../results/PROPULSION_CAPABILITY_INPUTS.json)；[PROPULSION_CAPABILITY_BOUNDS.json](../results/PROPULSION_CAPABILITY_BOUNDS.json)；[PROPULSION_BOUND_SOURCE_BINDING.json](../results/PROPULSION_BOUND_SOURCE_BINDING.json)。

### O13　继承范围及未回装的局部细化保持项 — OPEN

本次三态清单各为 619 个 WP08 继承组件加 82 个 V6 增量，共 701 个。WP08 后肋 11 实例局部组件此前未回装、本轮也未回装；WP09 前轮 A3200 局部细化没有自动计入这 701 实例。电池原生 HOLD 与设备固定保持，ADCS 实件与 A3200 全器件/RS-422 收发器仍未闭合。

下一产物：按具体局部组件与现行 manifest 做差异登记，分别安排后肋、A3200、实际电池固定和 ADCS/收发器的接口集成；逐项生成明确替换/新增实例与验证记录。

验收：组件只有出现在实际 V6/后续 manifest 且完成自己的集成检查后才获得回装信用；701 组件计数不能解释为全部历史局部细化已集成。旧电池 native HOLD 不被本轮覆盖。

依据：[INTEGRATION_HARNESS_CONTRACT_V6.json](../inputs/INTEGRATION_HARNESS_CONTRACT_V6.json)；[INTEGRATION_MANIFEST_V6.json](../results/INTEGRATION_MANIFEST_V6.json)。

## 下一个执行顺序

维护顺序先拆前盖，合盖状态服务空间保持 HOLD。三态原生检查已完成，接续整机截图与最终源文件/原生文件/BOM 绑定复核；同时绑定 DM 出货几何与 RSP→DM 真实端点。随后以实板 ICD 关闭 P60 安装孔/支撑、BPX/PDU 选件和 MiPS 外部接口，再生成可下料线束与相应试制检验记录。Ø8 导向件与真实 Ø6 线束的夹持、材料/紧固/热路径和动态运动各自验收，不互相继承通过。

逐项状态、证据哈希与计数见 [机器台账](../results/CLOSURE_ISSUE_LEDGER.json)。本台账未运行 CAD、硬件或仿真，也未修改冻结结论。
