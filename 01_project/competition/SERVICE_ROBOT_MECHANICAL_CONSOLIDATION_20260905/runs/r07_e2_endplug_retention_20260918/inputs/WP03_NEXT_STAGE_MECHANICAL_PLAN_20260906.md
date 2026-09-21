# WP03 下一阶段机械设计与完成路径

日期：2026-09-06（Asia/Tokyo）。工作类型：基于本地证据的工程规划。用户已明确选择下一次阶段验收目标为“可装配工程样机设计：完成关键连接、机构接口和数字试装”。本规划据此安排近期工作，并保留数字模型、论文复现和后续飞行适配路径。

**建议现在进入“局部详细设计与数字装配整改”。第一轮聚焦 R01，并同步落实 R17 与严格验证器真实接入；完成对应子项后，主任务转为 R07 根框锚固及保持释放机构详细设计。**

本文件回应用户的规划请求。两份附件作为参考材料，其中“立即执行”“修改 CAD”等命令未自动转化为本轮执行授权。本轮实际完成源码/账本阅读、来源哈希核对、独立分工核查及本规划；CAD 构建、FEA、运动仿真、实物试验均未执行，现有问题票、CURRENT 指针和历史 Gate 均未改写。本文件不是工程通过回执、制造批准或父 Gate 重发。

## 1. 从本地现状出发

| 事项 | 本轮核实事实 | 对下一步的含义 |
|---|---|---|
| 当前设计对象 | WP03_SERVICER_ONBOARD_R1；OPEN_PARKING、released、service 是不同物理配置，exploded 是显示视图 | 沿现有候选和依赖做局部修订，锁定配置；不能把开放停放改名为发射收拢 |
| R01 | 原孔系仍为 X=[−150,−50,50,150]、Y=±89 mm，Ø3.4；X150 孔与柱避口解析连通 0.2 mm。上下各两处破边，状态 PATCH_PROPOSED | 实际改件尚未发生；必须连同角材、剪力板、紧固件和工具路径一起处理 |
| R07 | 根部横梁→主纵梁等五条连接缺实体定义；A/B 支承约束与反力亦未建立 | 接触几何不能代替接头；完整载荷模型应建立在真实连接之上 |
| R17 | 导出程序先读现存 HANDOFF，未校验其来源与实例完整性；README 仍先 BOM 后 HANDOFF | 修复真实生产顺序与逐项校验。11 项现存交接输入哈希本轮重算均匹配，不能称当前 BOM 已证明过期 |
| 验证器 | 现行 pose_screen 仍使用 checked == 35；严格汇总器为隔离原型 | 必须接入当前真实输入/worker/输出链；原型通过不构成实际集成通过 |
| 质量 | 服务态 361 实例，194 个已分配正质量原子，167 个未分配质量实例；361 个 mass_owner 均非空且唯一 | 167 不等于漏装件数或 owner 缺失。先明确总成含件与计量归属，再补质量 |
| 实物及飞行 | 18 步装配程序未执行；发射供应方接口和载荷为空；B601 实装与环境资格缺项 | 可以继续局部几何设计；实物承载、制造和飞行分别验收 |

质量细分是本轮对子代理所读服务态 JSON 的统计：167 个未分配实例中，33 个功能包络、122 个简化代理、12 个名义物理实体；后者为六个设备热界面与六个保持器接触垫。已有质量的 COM/惯量缺项为 0。这不证明真实质量或分布准确。填补前需判断是否已包含于设备总成预算，避免重复。

当前静态三态各 179 个非臂物理件的已有检查、71 个机构样点和 91 个翼叶样点仍可按原范围使用。这些数量是既有结果，本轮未重跑；完整臂、指对、包含、全部功能包络、线束和样点间连续运动不能据此放行。

定位：
[R01 当前源码](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/spacecraft_model.py:125>)；
[R01 原票完整验收](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json:165>)；
[R07 缺连接清单](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json:1501>)；
[R17 原票](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json:1900>)；
[装配与运动范围](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/ASSEMBLY_SEQUENCE.md:3>)；
[当前导出器](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/export_parts_and_bom.py:10>)；
[原计数判据](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/pose_screen.py:195>)。

CURRENT_candidate.md 已在 9 月 6 日变为文件整理入口。其更新时间不表示 CAD 更新；附件引用的旧摘要应回到 issues 和工程源文件查阅。295 件交付/41 项来源等历史计数未在本轮重编，不用作新快照完成证明。

## 2. 建议按五个阶段推进

以下是项目内建议的工作阶段，不是新增 NASA/ECSS 认证，也不覆盖历史机器裁决。

| 阶段 | 要完成的实际工作 | 退出条件 | 通过后可进入 |
|---|---|---|---|
| 一：局部数字装配整改 | R01 12 个现有实例及紧固关系；R17；严格验证器接入；受影响参数真实驱动 | R01 数字几何、名义数字装配、R17 来源时序、真实入口集成分别有独立证据；相关 UNKNOWN 显式保留 | 根框和保持器的受控局部详细设计；未受影响接口的数据提取和构思可提前并行 |
| 二：连接与机构详细设计 | R07 五条连接；A/B 支承；销/盖/鞋/枢轴导向、防脱、止挡、终位保持；翼接口及服务线束 | 每条主承载连接有实体对偶/紧固/工具路径；每个机构有负载—驱动—能源—确认关系，缺数据的功能不得报闭合 | 同配置集成验证及具备输入的局部结构分析 |
| 三：工程验证与设计定版准备 | R13 臂源表示与拓扑处置、参数扰动、装配公差、局部承载/刚度/模态、全机构配对与分段运动、质量惯量重算、维护逆序 | 所用几何表示适合相应判据；按声明工况和对象逐项验收；每个准备做样件的部件已有材料、制造要求、测量与试验准则 | 限定范围的尺寸/连接/机构工程样件设计发布评审 |
| 四：工程样件试装与相关性验证 | 尺寸检验、空载试配、独立托持下安装、接头和机构台架试验、称量/重心、必要的模态相关 | 实测偏差、故障和返修闭环；达到该工程样件用途规定的承载、动作和重复性要求 | 对应工程样机基线与实测参数模型交接 |
| 五：飞行产品适配和资格 | 实际发射 ICD/包络、器件空间适应性、真实载荷与环境、制造工艺/验收、环境前后功能 | 任务和供应方规定的飞行要求逐项满足，由对应责任方接受 | 对应飞行产品制造/交付与任务准入 |

“能开始某项设计”与“该阶段验收通过”分开。现有证据支持阶段一的任务定义，阶段一工作尚未执行。阶段二中不依赖 R01 结果的接口取数、连接构思可以并行；合并到统一候选时须使用阶段一通过的快照。

用户所选“可装配工程样机设计”的近期完成点是阶段一至三的相应设计成果齐备，进入阶段四的样件评审：关键连接有可制造定义，机构有真实或已冻结的工程样件接口，指定装配和动作范围有数字证据，图纸/BOM/参数同源，并具备该样件用途的材料、公差、载荷与试验依据。仅完成 R01 不等于达到这一整套目标。关键承载、释放或安装参数仍 UNKNOWN 时，应保留相应设计票；与该样件用途无关的飞行资格缺项单独列出。

下一步不宜先做整星轻量化、更多服务姿态动画或完整整星 FEA：这些工作的可信度依赖真实接头、有效参数和载荷输入。R16 保持器结构代价在功能/终位约束明确后比较，避免先删件再补功能。

飞行取向若被选为近期目标，阶段五的“发射接口/完整收拢包络决策”必须前移至阶段一并行；在获得接口边界前，仅将样机局部件定版，避免冻结会造成整体重做的布局。

## 3. 第一轮执行包：取得第一组可复验改件

### 3.1 输入与资源

用现有协调目录中的一个实际时间命名 run 保存最小受影响源快照、输入哈希、补丁、导出物和原始日志。沿用既有 issues/dependency/run 账本；本规划未创建执行 run 或改变权威指针。

WP03 仍读取 WP01/WP02 等来源。下一轮须解析实际依赖和 __file__ 相对路径，不能仅凭 git HEAD 声称整个候选已备份。唯一构建者写候选，审阅者只读最终导出；最多两个轻任务并行、一个 CAD 重任务，CAD 构建/inspect/重验串行，开工前读取当前资源，不引用历史空闲内存。

输入至少绑定：有效参数、代码、原子实例、URDF/关节树、材料与质量归属、三种物理配置、上游依赖、生成工具版本。此次附录只锁定规划所读关键文件，尚非完整可重建的执行输入清单。

### 3.2 R01：两甲板—八角材—两剪力板

保留原方案作为第一候选：X=[−150,−50,50,140]、Y=±92.65 mm，孔径 3.4 mm。提案含甲板—角材 16 组、角材—剪力板 16 组连接，共 32 组；必须输出实际逐组关系，不以计数代替真实硬件。

本轮应产生：参数化候选实体、对偶孔表、紧固叠层、插入/工具/退出路径、局部尺寸图、BOM/质量增量与旧反例对照。

逐项接受：

1. 最终 BRep/STEP 读回两甲板共 16 个所需闭孔，原四处破边被消除。
2. 两层连接的基准、孔轴、方向、单位、实际夹层与配对一致。
3. 头、垫、螺母/螺纹承压区完整，柱避口保留；名义几何余量与结构许用边距分别记录。
4. 装配用标准件长度、有效啮合和防脱意图可审查；材料/等级/预紧/防松未定项保留 UNKNOWN。
5. 紧固件、邻近设备、立柱、侧盖及工具进入/退出均纳入具名检查集合。
6. 独立读回能检出旧破边、一个缺对偶/错轴线、一个垫圈或工具冲突；新候选没有新增相关未处置干涉。
7. 新几何、局部图纸、BOM 和质量变动同源；R07 不自动关闭。

M3×12/M3×10、垫圈外径不超过 6 mm及 3.8/9.8 mm净材料均保留“候选名义几何”身份。原票还包括材料/载荷、有效啮合、预紧等要求，只有相应证据齐备才可关闭父票；否则仅关闭 digital_geometry / nominal_digital_assembly 子项。不得用重命名验收项缩短原要求。

### 3.3 R17：让交付始终来自同一几何

执行顺序：

有效输入 → 构建和必要 inspect → 锁定最终实际几何/实例身份 → 生成 HANDOFF → 最后导出 BOM → 独立逐项核对。

若 inspect 重写 STEP，绑定其最终文件，不能使用检查前哈希。BOM 消费 HANDOFF，不回写几何；避免循环哈希。现有 --bom-only 顶层仍导入 CAD 模块，不能假设它是纯轻量入口，应在最小修改时拆清读取/导出依赖。

除总质量，还核对每个状态、实例集合、mass_owner、分配质量、来源哈希及角色。至少拒绝旧交接配新 CAD、同总质量但错源、parking/service混用、exploded、缺/重复 owner、UNKNOWN零填、GSE混入、标准件与父总成双计。

**现有 HANDOFF 输入身份匹配，是可利用的现状；防止未来生成混配仍需落实到真实流程。**

### 3.4 验证器和参数有效性

复用既有 strict_surface_aggregator 原型，接到真实候选入口和 worker 完成记录；同时替换 pose_screen 对旧 WP01 参数/WP02 动态来源的隐含假设。实际检查所用关节、碰撞表示和场景必须来自本次输入快照，不能只换一个汇总函数。

验收要求：预期配对集合=实际唯一配对集合，配置和哈希相符，完整视图有效，worker 正常完成，异常/NaN/超时/缺数据均不能变成 PASS。对重复/缺失/错误 ID、过期来源、爆炸视图和不完整事件做负控。协议验收与机械碰撞验收分别给结果。

R14 与改件一起做小范围参数扰动：在有效范围内改变一个孔距或板厚，检查责任件、对偶件、叠层、BOM/惯量是否发生预期变化，恢复后结果可复现；遗留 JSON 字段应明确无效或拒绝使用。先覆盖本轮改动参数，后续按模块扩展。

### 3.5 第一轮收口与失败处理

各票“最小反例→固定判据→最小修改→独立复验→关联回归”。建议每票最多三次候选，两次连续无改进时定位缺输入/方法/几何原因。资源不足保留已完成数据与明确 NOT_RUN 范围，不降低判据。

分别报告 R01 数字几何、名义数字装配、R17 来源时序、验证器真实接入和参数驱动结果。第一轮成功后，**下一张主票为 R07 的根部横梁/桥承载链到主纵梁锚固**；如 R01 失败，则留在该局部票，修复已定位反例。

## 4. 第二阶段机械设计具体做什么

### 4.1 R07：逐边补成可装配、可承载的接头

| 顺序 | 接头 | 最小设计产物 |
|---|---|---|
| 1 | 根部桥/上下横梁→主纵梁 | 对偶孔、锚固/夹接候选、防压与承压面、工具空间；不靠理想固定代替连接 |
| 2 | 纵梁→端塞 | 为已有穿孔落实实际紧固件、啮合/防松和装入路径；端面轴向紧固不能代替此边 |
| 3 | 保持横梁→纵梁；足叉→屋顶耳座 | 真实夹接件、足座匹配孔、紧固叠层、防转与装配路径 |
| 4 | 端框→后保留隔框 | 星内侧连接先闭合；供应方侧按待确认 ICD 保持参数化，不臆造部署器孔系 |
| 并行 | A/B 保持约束 | 实现主定位/柔顺及浮动方向；结合接触刚度、装配误差与预紧求反力，不能默认两站均分 |

每条边记录 A/B 件、孔/轴/面、约束自由度、连接形式、标准件、材料、载荷、装配/工具路径、来源及验证层级。图连通只证明连接关系，承载另按工况验收。

### 4.2 保持器与太阳翼：补齐真实机构链

保持器优先补导杆双端安装、销俘获和实际拉拔连接、盖轴/主枢轴防脱、实体止挡、退后正向保持、cap_tie/clevis 到主体的固定、传感靶标和固定端到随动端线束。

26 mm 拔销、80 mm退鞋、100°开盖、90°折退只作为当前几何需求。按“接触负载/摩擦/预紧/公差 → 力或力矩/行程 → 驱动与能量 → 导向/保持 → 状态确认”建立可选型接口；没有输入不编造拉力、力矩、传感阈值。

先定性处置卡销、单站释放、上盖开而下接触未脱、确认矛盾、失电、线束受限、退出回弹；再根据实际驱动和传感器形成动作许可合同。不能假定失电自锁，也不继承地面 GSE 状态机为机载功能。

太阳翼同样补叶片/边框连接、铰链轴向保持、止挡/展开锁止、驱动或储能、释放与确认、根部及叶间活动线束。当前叶片样点结果不替代这些硬件。

六类功能包络与22类物理OBB候选逐对归因：真实材料用实形，正常接触限具体表面/状态，功能空间落实可容接口，失败/缺输入保留 UNKNOWN。约0.256 mm SAT候选量不得写成实材穿透深度。

### 4.3 设备、线束与维护

设备从“预算盒”推进到“设备—适配板—甲板—导热—连接器—维护方向”的完整接口。接口表至少含安装基准、真实孔系、紧固叠层、热面、连接器空间与插拔行程、线束应力释放和拆卸顺序。

线束须给外径、动态弯曲半径、扭转/寿命限制、自由段长、端接方向及固定点；几何曲线保持为候选。WP03 服务环与旧 E_HRN/Route-C 是不同安装拓扑，各自保留来源及负结果。

R16 在保持/退出后约束明确后，比较现折退架与一个近根承托/明确终位锁止方案；相同功能、误差、载荷下比较质量、偏心惯量、柔度/回弹、视场和扫掠，不能只以外观删件。

## 5. 第三、四阶段如何形成可信完成证据

**R13 源拓扑与表示资格是相关完整臂检查的前置工作包。** 六处继承臂源缺陷逐 link 登记 BRep/STL/代理身份、单位、变换、健全性和适用判据；先判断哪些影响臂根接口、保持接触、指对和碰撞。需要实体修复时，在登记的派生副本定点修复或取得供应方更正源，保留原件、前后差异、孔面/包络变化及哈希，不覆盖 accepted 或厂家来源。修复后重新验证相应接口；不得为了闭壳改变接触面而不记录。

对双指、相邻/非相邻 link 及闭体完全包含建立专项对象和反例，选择可支持对应判据的几何表示。表面分离检查不自动证明没有包含。未处置的缺陷或表示不适用，应阻塞对应的实体/接触结论；其余不受影响的局部设计可继续，但不能因严格汇总器接通而宣布完整数字试装通过。依据：[R13原票](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json:1662>)。

结构验证分三种真实边界：地面装调的重力与独立托持、运输/发射的实际接口和环境、在轨自由体的任务六分量载荷。目标质量不能直接乘 g 当在轨载荷，四柱固定梁模型不能替代整星边界。

顺序为接头与板件解析校核→关键部位有限元→完整声明边界的结构/模态模型→工程试验相关。每一分析先具备几何、公差、材料/工艺、紧固/接触、载荷及接受值；检查承压、净截面、剪切/拉脱、滑移/分离、局部屈曲、刚度及适用寿命项。阈值来自任务合同、材料和选定标准，不在本规划里补经验常数。

同配置运动从解锁→盖/鞋脱离→折退保持→臂首动→翼展开→服务路径逐段检查，绑定对象/配对、表示、配置、误差与允许接触。样点可报告样点证据；连续结论须有相应区间的有效距离下界、运动界或适用连续碰撞方法，包含和接触转换不得漏掉。

工程样件先按用途分清尺寸替身、连接试件、机构功能件和整机工程样机。每项准备试装须有可制造图纸、明确材料/标准件、公差与测量方法、合适工装、接头/支承依据和测试准则。空载尺寸试配不要求等飞行资格，但不能据此投入未验证的整臂载荷。实物运行由后续具体任务安排，本轮未采购、加工或驱动物体。

NASA 将验证、环境鉴定、逐件验收及认证区分，并要求验证与具体产品要求和配置绑定。本规划据此将数字几何、实物试装和飞行结论分层，不将局部通过升级为整星结论。[NASA Product Verification](https://www.nasa.gov/reference/5-3-product-verification/)

## 6. 现在并行收集的最小输入

| 输入包 | 主要提供方 | 最小内容 | 缺失具体阻塞什么 |
|---|---|---|---|
| B601 实装接口 | 硬件负责人/厂家资料与实测 | DM/RS及实际批次、根孔/基准、允许支承区、内部承压限制、关节失电状态、线缆出口 | 根接口定版、夹持预紧、真实质量与在载释放 |
| 材料与紧固 | 机械设计/加工方 | 板型材牌号与状态、公差/表面处理、真实螺钉与螺纹、嵌件/防压/防松选项 | 承载、公差和加工图发布 |
| 机构与能源 | 机构/电气负责人 | 所需负载/摩擦、可用母线与功率能量、执行器行程/力或扭矩、安装、确认/故障行为 | 真实释放与展开能力 |
| 线束与连接器 | 电气/供应商 | OD、动态弯扭/循环、端接、自由段、固定点与保持方式 | 全运动域电缆和接口设计 |
| 发射/分离与任务环境 | 总体/供应方 | 完整整机包络、接口基准/孔系/刚度、质量/CG/I限制、实际环境载荷与试验条件 | 发射收拢、结构飞行定版和环境资格 |
| 设备/翼/任务动力学 | 各子系统/动力学合作者 | 实际质量/COM/I、安装与热接口、翼刚度/阻尼；q/qdot/qddot及接触载荷边界 | 完整物理质量、结构/多体相关与任务能力 |

优先拿到“B601 实装接口＋材料紧固初选＋保持器接触/释放需求”。同时确认有没有可用发射供应方 ICD；没有时保持样机用途，发射接口单独开放。可依此列本地待输入表，不需要等待所有厂家数据齐备才开始 R01。

## 7. 与论文、仿真和飞行资格的衔接

当来源/计量/配置接口稳定，可以准备当前构型逐 link 的自由漂浮刚体模型交接，未知物理量采用有来源的区间或保持未知。姿态整体惯量只适用于锁定相对运动的该姿态；运动时保留关节与基座耦合。结构参数、执行器与柔性数据之后按实测更新并重验。

R2/E23/Sim13、旧 Route-C 和既有论文结果保留原适用配置。新 WP03 几何不会自动继承其科学 PASS，旧 R2 阻断也不自动扩展为所有 WP03 局部设计停工条件。新模型运行范围应在其具体任务中登记。

飞行路线需要 B601 的材料/打印件、润滑磨损、驱动热路径、真空放气、线缆、振动冲击、电气和辐射等证据；“有公开 CAD”不足以证明空间适应性。现有整理见 [动力学与环境缺项](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/DYNAMICS_AND_QUALIFICATION.md>)。

方法来源核对截至 2026-09-06：
- NASA 配置管理要求标识配置项、变更和对应证据，适用于规划同源输入与导出顺序。[NASA Configuration Management](https://www.nasa.gov/reference/6-5-configuration-management/)
- ECSS 机构标准覆盖概念、设计、分析、生产、试验验证及在轨运行，可按项目裁剪。[ECSS-E-ST-33-01C Rev.2](https://ecss.nl/standard/ecss-e-st-33-01c-rev-2-1-march-2019-space-engineering-mechanisms/)
- ECSS 测试标准区分鉴定、飞行件验收及原型飞行测试，并规定测试条件/不确定性管理；具体功能要求仍由项目定义。[ECSS-E-ST-10-03C Rev.1](https://ecss.nl/home/ecss-e-st-10-03c-rev-1-testing-31-may-2022/)
- NASA GEVS 的官方状态为 B 版 ACTIVE，提供 GSFC 载荷/分系统/部件环境验证指导；本星应据任务制订环境要求，不直接抄指导级别。[GSFC-STD-7000B](https://standards.nasa.gov/standard/gsfc/gsfc-std-7000)

本轮只核对以上官方网页的适用范围，不声称已逐条完成标准全文符合性评估。

## 8. 本轮核查与下一轮分工

本轮实际参与：
- /root：规划协调、本地入口/原始记录阅读、官方方法核对、关键来源哈希、统一文件撰写。
- /root/wp03_mechanical_readiness：独立只读核查 R01/R07 源码、原验收与连接缺口。
- /root/wp03_provenance_readiness：独立只读核查 R17、真实验证入口、质量实例及交接输入哈希。

这是同模型分工审阅，不称跨模型独立验证；没有执行候选构建、机械独立复验或原型重测。两代理读取的 issues、spacecraft_model、参数等身份与本文件附录一致。工作区已有84项受版本控制文件变化，本轮不处理这些既有更改。

规划独立审阅提出 R13 臂源拓扑处置缺少显式工作包，已补入阶段三前置及本文件第5节；其余检查未发现缩短 R01 原票或把规划写为完成的关键问题。这是文本与来源一致性审阅，不构成机械复验。

下一轮建议仍保持一个协调/唯一构建者，结构装配与验证来源两条独立复验线；机构专项在其工作包启动时参与。构建者不能独自接受自己的修改。所有结论有对象、配置、来源、方法和覆盖范围，不用代理投票代替证据。

下一轮第一优先任务固定为：**实现并独立复验 R01 的完整局部数字装配候选，同时保证 R17 和真实检查入口使该改件可追溯。** 第一轮达到限定验收后，转入 R07 根部锚固；整星承载、实物和飞行状态各自继续按证据推进。

## 附录：规划读取的关键文件身份

以下 SHA256 于本轮实际读取计算，仅用于说明规划所依据版本。执行前应复核依赖变化，不将这张表当完整执行快照。

| 文件 | SHA256 |
|---|---|
| [CURRENT_candidate.md](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/CURRENT_candidate.md>) | `a1316c48f16d58c66c3f5d1a5131b5f4d1774d355044fc155e53066fcdcd88e2` |
| [issues.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json>) | `5896a173710bfc4a00d6f87445b0d32feafd0991bff37dd4c3ccc981f44d32ce` |
| [dependency_manifest.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/dependency_manifest.json>) | `84d3de1552196855ff99694300efa6dd434c8c8054bbb13c15ab0c56f0d62701` |
| [run_manifest.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/run_manifest.json>) | `1d9f05847a290d51b318462df92562bf40e7c0c6cb514241c442fe6e100d0aa1` |
| [spacecraft_model.py](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/spacecraft_model.py>) | `11bd80a667505fc5fd0cf9bc79f7a892bcab5424ae16997de4fd0f163f53a2e9` |
| [root_structure.py](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/root_structure.py>) | `eaf7d17bba7b2bbabe215059bdc21f11b55944dac14858e4729022a6f3ef5c48` |
| [design_parameters.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json>) | `190c30ac8e3126ac44c9a7ea8408cf8b43642a0d94f1740082a900e44febc97b` |
| [export_parts_and_bom.py](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/export_parts_and_bom.py>) | `1321dc954dd363af578ae1c9811c5152df1362772404cc9fe2523f1a1a142f27` |
| [dynamics_handoff.py](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/dynamics_handoff.py>) | `b1f27bba24c7a3a09f84b4894583989f2051da654c62b2890a21233da3ce48fe` |
| [pose_screen.py](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/pose_screen.py>) | `5cf9493f5c9420839570df9ba74958b1d3a70484d184d40555e0cf60b78e558a` |
| [ASSEMBLY_SEQUENCE.md](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/ASSEMBLY_SEQUENCE.md>) | `1f4d5d4aa0e69d3e4859e3f18b018274e589eabdb21bbed291956cecc6bdb693` |
| [DYNAMICS_AND_QUALIFICATION.md](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/DYNAMICS_AND_QUALIFICATION.md>) | `a5f28a0d9fdb305b2b92415f7fd1b5ec895bb94b4af9d3717683d207006817d1` |
| [DYNAMICS_HANDOFF.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/results/DYNAMICS_HANDOFF.json>) | `b05d991ace5b707dbff950edff250b55f26c36e7f2067b7c7b36d58c1971e47a` |
| [BOM.csv](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/BOM.csv>) | `cfb4df9a60b7246cdeb77a8dc36dfef2847c3cba276d5668203f808776fb1b44` |

附加来源：WP02 parts_model.py 为 65826f624cdf1d756885cabbb84c4db856550cf2d0f31940c8b3e5b034083baf，WP02 design_parameters.json 为 cff91ebfa638aafb77cf42c4cdd461668eb71ce3ae4999a706aa395db187b117；服务态实例为 a9528798160b85d000a0f77b345d228df9f10f5790d65337116a698f356b0b2d；严格汇总器原型为 6cd2428850c3598b2ddf624a05d94748dd7935466f7c079cb8e09dab6c574369。以上附加哈希由对应只读代理实算。

FILES_CHANGED：仅新增本规划文件。原 issues/CURRENT/工程源码/参数/结果/Gate 保持本轮读入身份。
