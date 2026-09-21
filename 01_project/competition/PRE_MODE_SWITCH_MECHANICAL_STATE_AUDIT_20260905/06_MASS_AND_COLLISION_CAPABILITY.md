# 质量、材料与碰撞能力审计

审计日期：2026-09-05。工作模式：READ_ONLY_SOURCE_AUDIT。结果只说明读取的模型与本次工具环境，不是新配置、资格鉴定或生产查询授权。

## 质量账本必须分开使用

独立 XML 求和得到 accepted B601 URDF 的 10 个 link 总质量 **4.695555949342986 kg**，关节为 6 revolute + 1 fixed + 2 prismatic。该值来自 accepted 模型；不代表当前装配已经包含正确臂几何，也不是实物称量。本次逐 link 读回与逐关节 limit 在 `root_mass_independent_readback.json`。

R2 C01 `DEPLOYED_NOMINAL` 账本六项算术之和为 **31.022864807342987 kg**，其登记标准不确定度为 **4.594921657121637 kg**。此数字属于 `DESIGN_MODEL_R2`，原入口还明确 `CANDIDATE_ONLY_NOT_AS_BUILT`。不能把小数位数当作工程精度。

| C01 成员 | 账本质量 kg | 证据性质 |
|---|---:|---|
| bus_primary_structure | 23.3032134 | BUDGETED bus core 与材料派生 legacy flange 合并；并非逐个真实母线零件称量 |
| B601 全臂含夹爪 | 4.695555949342986 | ACCEPTED_URDF |
| M3R 两级 | 0.7619 | BUDGETED envelope |
| load bridge | 0.702195458 | MATERIAL_DERIVED candidate |
| Solar R2 左翼 | 0.78 | 面密度模型候选，未实测 |
| Solar R2 右翼 | 0.78 | 面密度模型候选，未实测 |

同一源还保存 `legacy_simulation_reference_kg=24.0`、`r2_whole_sat_candidate_kg=24.8632134`，服务不同账本对象。F4R1 设备表明确将 23.303 kg bus 行标作整体块模型余额/proxy；另有设备新增与 CDS 变体方案。因此不能把真实内部设备质量直接加到旧 31.02286 kg 后称为最终产品重量，也不能用局部结构减重自动替换旧 bus 行。要先逐行定义替换、保留和新增，消除重复计数，再为选定配置建立新账本。

R2 的质量入口与 accepted URDF 入口合计六个带预期 SHA-256 的引用，本次 **6/6 哈希相符**，见 `root_mass_reference_hashes.csv`。哈希一致仅证明源身份一致。

## 帆板与内部结构的新旧结果

几何 SSOT `flexible_appendage_v1.yaml` 原值是 **0.3483933 kg/板**、span 0.200 m、chord 0.227 m、thickness 0.006 m（占位）；对应面积为 0.0454 m²，隐含面密度约 7.674 kg/m²。该卡自己已声明质量来自 24 kg 均匀密度块模型分摊、刚度来自指定频率而非实测。因此旧记忆中“占位板质量一定比真实板轻 5–10 倍”的方向判断不能不带几何口径直接沿用。

R2 0.78 kg/翼含多叶与机构。F4R1 C2 已有两模型两用途的调和提案与参数包络，`GATE_C2_CHECK.json` 是 `PASS_WITH_DECLARED_OPEN_ITEM`；其中 `PENDING_OWNER_SIGNOFF`、`PRE_CAMPAIGN_ANALYTIC` 与未实测限制仍在。这里不将解析缩放提案提升为新仿真结论。C2 的具体机构缺口包括：候选弹簧 0.05 N·m 在其账本控制工况下不足，要求至少 0.080 N·m；独立锁扣刚度仍 null，T_c=20 ms 仍待实测。此处数字是本地候选判据读回，不是采购规格或飞行标准。

F4R1 C3 的 `MASS_CG_REPORT_V1.json` 仍为 **1433.2 g**；后续 V2 `GATE_C3_CHECK_V2.json` 是 **1244.9 g**，`PASS_WITH_DECLARED_OPEN_ITEM / DESIGN_RESEARCH_CANDIDATE`。两者版本不同，V1 质量文件未因 V2 存在而自动更新。V2 还将 stowed CG、wall-pass bracket path、弹簧体积和估算质量比列在 deferred_registers。干涉报告以 **1000 mm³** 为 VIOLATION 阈值，小交叠可进入 CONTACT_NOTE；因此“0 violation”并非绝对零干涉，局部结果不能代表整星装配闭合（见 03 报告）。

## 结构与产品化边界

R2 原 `19_OPEN_QUALIFICATION_HOLDS.csv` 保留发射/分离 ICD、材料许用、实物质量惯量、接触标定、夹爪闭合时间、F/T 标定、振动、TVAC、HDRM 可靠性和原生再集成等缺口。其 15/16 两项内部阻断应同时参考后续 Route-C/Sim13 增量，不能只照抄旧表（见 `05_AUTHORITY_AND_EMBODIED_HANDOFF.md`）。

已存在 FEA/ROM/动力学来源可保留其原配置下的结论。新安装角、支撑、bus 布局或翼根结构会改变质量分布、边界条件和载荷路径；需说明适用性或重新验证。几何存在、尺寸参数化、图纸或局部计算存在，都不能单独给出制造完整或飞行通过结论。

## 碰撞能力实测

2026-09-05 使用 `G:\Windows_program_file\Anaconda\python.exe`（Python 3.13.9），以 `-B` 禁止本次 Python 写字节码。读取环境并实际导入 `vtkmodules.vtkFiltersModeling.vtkCollisionDetectionFilter` 成功：

| 项目 | 本次结果 |
|---|---|
| VTK | 9.6.2，碰撞类可导入 |
| cadquery-ocp | 7.9.3.1.1，包可发现（没有本轮 BREP 查询） |
| trimesh | 4.12.2 |
| numpy / scipy | 2.3.5 / 1.16.3 |
| fcl | 当前 Python 环境未找到；不是全机所有环境不存在的证明 |
| SolidWorks / FreeCAD | 本轮未启动、未连接或保存；读取进程时无对应主 CAD GUI 进程，sldworks_fs 文件服务进程不等于装配会话 |

详细原始收据：`root_collision_capability.json`。未实例化碰撞过滤器，未加载 CAD 到碰撞内核，未执行任何生产 pair/edge/path 查询，也未生成碰撞 PASS。

VTK 官方描述该类用于两个多面体**表面**的碰撞，输入可设变换与容差；因此它提供候选窄相路径，但“表面无交线”本身不能排除完全包含。官方网页本次显示 nightly 9.7；本机是 9.6.2，不能把 nightly 文档当作本机行为测试。[VTK 类文档](https://vtk.org/doc/nightly/html/classvtkCollisionDetectionFilter.html)

若评估 VTK 备选，其拟议资格化用例如下，仅是测试设计，本轮尚未执行；这不否定下文所述 OCP 既有合成验证：

| 控制用例 | 应核对什么 |
|---|---|
| 两闭合实体明显分离 | 无接触、距离符号与坐标单位正确 |
| 明显穿透 | 检出接触，反向顺序与共同刚体变换保持一致 |
| 精确相切及 ±epsilon | 固定容差语义，避免把浮点边缘当安全余量 |
| 薄片、退化面、非流形输入 | 拒绝无效输入或明确结果 UNKNOWN，不乐观回退 |
| 一闭合实体完全位于另一内部 | 通过独立包含判定识别，不能以表面无交线判安全 |
| 三角化/网格细化与刚体变换 | 区分离散误差、源文件精度和真实机械间隙 |
| pair→edge→完整路径 | 逐层覆盖并绑定同一几何/配置/容差，不继承孤立 pair PASS |

当前措辞应为“已有部分后端合成验证和可供资格化的工具路径，当前系统绑定与覆盖尚未闭合”。特别是 ODR60 的 OCP/BRep 单 pair 后端已经有 **25/25 合成 Gate、18/18 负控、5/5 独立验证**，只是明确不主张当前系统支持、生产查询仍为零（精确来源见 05 报告第 6 节）。后续应先评估复用这条已登记路径；本次发现 VTK 可导入并不意味着需要另起一套检查器，也不代表选择 VTK 或获得运行权限。

## 来源

精确本地绝对路径、现存字节数和 SHA-256 见 `09_SOURCE_SHA256.csv` 中 `root_sources.txt` 登记的来源。复算只涉及 XML、文件身份与账本加和。没有运行源脚本、FEA、优化、动力学或硬件。
