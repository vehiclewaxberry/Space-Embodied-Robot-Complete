# WP02 关键组合件：输入、几何注册与实物测量

日期：2026-09-05。继承配置：`WP01_ROOF_EXTERNAL_R1`；WP02 是在其基础上的关键组合件详细候选设计。本文件不改变 WP01，不把源文件中名称含 `as_built` 的 CAD 解析结果当作实物测量。

**用户已提供厂家唯一开源入口，本轮已核查并锁定 GitHub commit `8def0ebd8ea0785dcbfc58c00ab176ee42acba5d`。** 当前状态为 `VENDOR_REPOSITORY_VERIFIED_CONTENT_PARTIAL_FOR_INTERFACE`：存在 B601-DM 小件STEP、BOM、线缆端型/长度及装配资料，但所读来源没有给出完整制造公差或动态弯曲/扭转限制。厂家资料已在本包小量缓存，不能再表述为“只剩数字模型”或“图纸路径仍待提供”。[厂家固定版本](https://github.com/Seeed-Projects/reBot-DevArm/tree/8def0ebd8ea0785dcbfc58c00ab176ee42acba5d)

## 厂家源核查与本轮可用字段

GitHub API返回main提交时间为2026-09-05T04:35:34Z，完整递归树457项、未截断；该树没有PDF/DXF。已复制6份相关MD、6个小STEP/STP、1个当前DM URDF和LICENSE，另保存完整路径树及 [VENDOR_SOURCE_RECEIPT.json](inputs/vendor_reference/VENDOR_SOURCE_RECEIPT.json)。没有下载34–38MB整装或整个STL仓库；本输入分工未执行内核量测，同轮CAD分工已生成 [VENDOR_GEOMETRY_PROBE.json](results/VENDOR_GEOMETRY_PROBE.json)，按该收据读取实际OCC圆柱/平面和源哈希。其结论属于厂家数字STEP，不是实物计量。

| 字段 | 厂家源实际提供的内容 | 当前用途与边界 |
|---|---|---|
| 型号 | B601-DM使用Damiao43系列；B601-RS使用RobStride，是独立版本 | 继承项目DM来源，不能把RS零件/线束/电源参数混用。[DM BOM](https://github.com/Seeed-Projects/reBot-DevArm/blob/8def0ebd8ea0785dcbfc58c00ab176ee42acba5d/hardware/reBot_B601_DM/readme_zh.md#L24) |
| CAD版本 | BOM更新表到v1.1_20260425；树还包含v1.1_20260625整装；英文文件结构一行另写20260415 | 按实际文件路径/提交/哈希识别，不能仅凭v1.1称同版。已复制的当前根板SHA与旧M3R探针登记的根板SHA不同，尚不推断几何是否变化。[版本记录](https://github.com/Seeed-Projects/reBot-DevArm/blob/8def0ebd8ea0785dcbfc58c00ab176ee42acba5d/hardware/reBot_B601_DM/readme.md#L18-L30) |
| 根部小件 | 01_BASE_Plate、01_BASE_Link和02_Base_Reinforcement_Part均有STEP；BOM列HM4-75mm螺钉4+ | 根孔/承载/工具的当前数字依据见本轮[VENDOR_GEOMETRY_PROBE](results/VENDOR_GEOMETRY_PROBE.json)，仍非带公差完整实配ICD。[根板STEP](https://github.com/Seeed-Projects/reBot-DevArm/blob/8def0ebd8ea0785dcbfc58c00ab176ee42acba5d/hardware/reBot_B601_DM/3D_Printed_Parts/01_BASE_Plate.step) |
| 电机线束BOM | XT30 2+2，350mm两端弯头×2、一弯一直×1；200mm两端弯头×3、两端直头×1 | 端型与标称长度可用于候选选择；新根部样段的有效长度/安装对应仍须注册。[BOM 155–158行](https://github.com/Seeed-Projects/reBot-DevArm/blob/8def0ebd8ea0785dcbfc58c00ab176ee42acba5d/hardware/reBot_B601_DM/readme_zh.md#L155-L158) |
| 外部电源转接线 | XT30U母转XT60公，16AWG，300mm | 仅外部供电转接线，不是电机XT30 2+2活动线束的线规或护套外径。[BOM 178行](https://github.com/Seeed-Projects/reBot-DevArm/blob/8def0ebd8ea0785dcbfc58c00ab176ee42acba5d/hardware/reBot_B601_DM/readme_zh.md#L178) |
| 应力释放 | 厂家指出拖拽线束1会磨损电机接口，提供DM_Motor1_wiring_harness_clip.stp；末端也有线束卡口件 | 已复制电机1小夹件，可作接口参考；不直接继承其寿命/反力能力。[线夹说明](https://github.com/Seeed-Projects/reBot-DevArm/blob/8def0ebd8ea0785dcbfc58c00ab176ee42acba5d/hardware/reBot_B601_DM/readme_zh.md#L59-L67) |
| 壳体与内部件 | BOM同时列PLA装饰盖/填充、ABS件及5052金属连杆；03_Link2和03-Link2两个不同哈希文件并存 | 已复制两种小件供注册；不能按link2外表面bbox推断内部支承或允许夹持压力。[机械BOM](https://github.com/Seeed-Projects/reBot-DevArm/blob/8def0ebd8ea0785dcbfc58c00ab176ee42acba5d/hardware/reBot_B601_DM/readme_zh.md#L43-L113) |
| 当前URDF | 官方现在提供Rebot_Arm_description/DM/urdf/ReBot_Arm_DM.urdf及独立visual/collision表示 | 仅作源版本比较，不覆盖本项目accepted URDF/STL。[当前DM模型说明](https://github.com/Seeed-Projects/reBot-DevArm/blob/8def0ebd8ea0785dcbfc58c00ab176ee42acba5d/Rebot_Arm_description/DM/README.md) |

未在已审阅路径树和相关中英MD中发现：电机线束护套OD、其电线线规、动态最小弯曲半径、允许扭转、接头机械受力限值与根接口制造公差。该负发现限于所述范围：电源接线有图片，本分工未逐图转录，不能声称所有接线图都不存在；这些图片也不能自行补出动态机械规范。

追加的 [厂家基座STEP文本实体探针](inputs/vendor_reference/VENDOR_BASE_CYLINDER_TEXT_PROBE.json) 已解析当前根板的4组Ø4.6/Ø7.5同轴圆柱和base link的4个Ø4.5圆柱，XY均为(±32,±32)。这是当前文件的解析曲面参数，尚不是内核孔拓扑/沉孔深度/制造公差检查；轴支撑点z=-1.3或-63.7不等于承载面。它支持64×64方形轴线模式的候选比较，仍须与旧M3R旋转孔系和实物基准注册。

## 本轮共同输入

| 项目 | 当前采用值/含义 | 来源与用途 |
|---|---|---|
| 物理状态 | `OPEN_PARKING`；保留 WP01 的 `stowed` 文件键只为兼容 | 当前参数 stowed q=[0,-30,-60,40,0,0] deg，双指字段15 mm，翼角0；不是紧凑发射收拢 |
| 根部 | `p_S = T_S_A0 p_A0`；旋转 I，平移 [90,0,125.15] mm | WP01 当前参数和接口几何收据；承载接触面另在全局 z=127.555 mm |
| M3R | A/B/base_link 名义 BRep 同原点；B 底面全局 z=113.15；A 环嵌 B 槽5.595 mm | 不将 frame 原点与承载面混同；不把 A/B 当两整片顺序叠加 |
| 基座表示差异 | nominal BRep 底面局部 z=2.405；accepted STL bbox局部z=0 | 该2.405只描述此名义基座，不能普遍修正所有link/STL/实物 |
| A 站位 | S.x=-115 mm；下垫依据当前姿态的 accepted link2 截面；上垫对应link3 | 下垫旧截面z=[362.06827784535824,425.85019064932413] mm；只用于定位测量区域，不代表壳体可承压 |
| B 站位 | S.x=-40 mm；下垫依据当前姿态的 accepted link2 截面；上垫对应link3 | 下垫旧截面z=[338.90185801408774,384.04342600174647] mm；上/下垫、名义BRep/实物分别注册 |
| 初始设置间隙 | 支承/保持件相对源截面2 mm | 不是垫厚、压缩量或预紧；WP02 用可调结构、接触垫及测量定义闭合方式 |
| 退出布局 | 两站各向-X拔销48 mm、上垫+Z12 mm、下鞋-Z30 mm，随后保持组+Y180 mm；下鞋装调±8 mm独立 | 18 mm拔销已被CAD首段Y运动反例否决，160 mm为历史Y候选；当前行程仍需误差/停止超程/线束与完整扫掠验证，见[释放顺序](RELEASE_SEQUENCE.md) |
| GSE公共框架 | 正Y侧公共柱S.x=40、S.y=155/315、顶z=690 mm；公共吊梁z=660 mm；两站负侧柱y=-155 mm | 地面工装几何；实际翼动作需要独立托持接管后移开GSE并复查净空 |
| 数字臂质量 | 4.695555949342986 kg | accepted URDF 数字质量，不是实物称重；装上夹具/线缆/末端后单独实测 |
| 零件归属 | 根桥、根板、框梁锚固：`ONBOARD_HARDWARE_CANDIDATE`；高支承、保持Y滑台及其支架：`GROUND_SUPPORT_EQUIPMENT` | GSE进入地面载荷账，不进入飞行BOM；当前布局代理另列 `FUNCTIONAL_ENVELOPE` |

## 已读 M3R 孔系：只继承数字候选，不重命名为实测

坐标是 `M3R_LOCAL`，+Z由B朝臂；它与本候选根部frame同原点、同方向。长度单位mm。

| 接口 | 源中的候选几何 | 必须另核实的实配数据 |
|---|---|---|
| A→B601四孔 | 中心(15.494,42.4393)、(-42.5096,15.3917)、(-15.4621,-42.612)、(42.5416,-15.5644)；M4级通孔Ø4.6；沉孔Ø7.5、从顶面深4.5 | 实物/厂家图中的孔型、轴线、螺纹规格和有效深度、沉孔方向、定位基准及安装工具 |
| A/B八孔 | r=62.5，起始角22.5°，每45°一孔，Ø5.5 | 这是通孔候选，配对螺纹/螺母、头部沉孔/垫圈与扳手空间须完整设计 |
| B→承载板四孔 | (±70,±70)，Ø6.6 | 承载板真实对偶孔、螺纹/螺母、啮合/边距/预紧及工具方向 |
| A/B定位 | A Ø4.1通孔与B Ø4.0、深5.5盲孔，中心(55,0)；A止口Ø99.6；B中心孔Ø100.0；B外接收槽Ø150.4 | 定位销实选和可拆方向、公差与热差；名义直径差不是经过验证的配合等级 |

孔系来自 [M3R_PARAMETER_DRIVER_V2.json](../F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_PARAMETER_DRIVER_V2.json)。其上游 [M3R_B601_BREP_INTERFACE_MEASUREMENT.json](../F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_B601_BREP_INTERFACE_MEASUREMENT.json) 明确 `measurement_mode=READ_ONLY_ANALYTIC_BREP`，`as_built_pattern` 的4个实体是 HM4-75 螺钉轴，不是4个安装孔。该文件另有厂家几何对照：底板4×Ø4.6/Ø7.5沉孔、base_link 4×Ø4.5，局部中心(±32,±32)。两组坐标/形状须按基准注册，不能为“匹配”而静默改孔。

## 三层注册和误差账

1. **accepted STL**：用于既有运动学/碰撞源口径。登记源哈希、mesh单位、link frame、实体是否封闭和允许接触局部区域。
2. **nominal BRep**：用于当前详细装配候选。登记源哈希、实体身份、物理承载面/孔轴/定位特征。保留源拓扑缺陷；无效实体的体积或包含检查不得作实配依据。
3. **实物/厂家图**：实物需序列号、仪器/校准、测量方向、误差；厂家资料需型号、提交/修订、尺寸/基准/公差和适用范围。此次已核查的公开STEP/BOM与尚缺的实物/制造公差数据分别登记。

优先用承载平面定义法向和轴向基准，用定位圆/止口定义中心，用具名孔/关节轴定义绕法向的转角；保留所有孔的独立残差。不得只对齐bbox或用全局ICP隐去不同部件。若特征不能由同一个刚体变换解释，登记 `GEOMETRY_VARIANT`，不要声称“注册完成”。

每项分别填写 `T_target_source`、配准位置残差mm、方向残差deg、CAD建模差异、仪器测量不确定度、制造公差、装配复现误差和适用对象。WP01矩阵传递最大元素误差2.220446049250313e-16是数值矩阵传递误差，无量纲旋转项与mm平移项不能合并当作实体误差，更不是安装精度。[TRANSFORM_TRANSFER.json](../service_robot_wp01_20260905/results/TRANSFORM_TRANSFER.json)

## 支承约束候选

**A为主要定位支承**：在定义的局部接触区控制X站位，Z向支撑采用可调/柔顺接触，Y向采用有限刚度的柔顺侧向定位。不得把A三向刚性锁死后又与根部固定共同理想绑定。**B为Z向支承＋X向浮动**：B不作为第二个X基准；其X浮动行程与摩擦需登记，Y侧只设置间隙/柔顺导向候选，未经定义不计承载。两站不能靠紧抱薄壳强行形成定位。

反力由接触法向、间隙/预紧、垫/壳体/支架/关节刚度和根部柔度共同求得。可用仅受压接触 `R_n=k_n max(0,δ_n)` 作为初步模型，但刚度k、压缩δ、切向/摩擦律均须有输入；反力不能无刚度地均分。先用卸载/独立托持工装承住臂，缓慢调整垫并量测接触/压缩和支点反力，再校正分流模型。

## 最小待补输入与可先做的样件

利用已下载厂家小件优先核对：①根部四孔、承载面/定位及装配方向；②根部/腕部连接器与线缆的BOM对应；③两站下垫link2和上垫link3候选接触区域的金属/装饰壳体归属、内部传力依据。真实测量仍需实际机型/版本与实装照片、根部/附件质量与重心、两站上下表面/可承载证据、有效电缆长度及动态限制、台架/独立托持能力和指定试验工况。若能提供线缆供应商的动态机械数据，优先补OD、动态弯曲、扭转和接头允许力；目前公开BOM不足以取代这些字段。

可以继续设计并评审**独立非承载尺寸样件**：孔位置透明模板、连接器插拔/工具通道样件、线夹/护口样件、空载滑台/锁扣尺寸模型、link2/link3局部截面替身与支承调整机构。没有实配孔/接触/载荷证据时，其标签为 `NOT_FOR_MANUFACTURE_AS_LOAD_BEARING_PART`；不能托住真实臂、施加预紧或替代承载件。此区别不阻止本轮CAD详细设计，也不新增历史Gate许可流程。

## 来源和读取覆盖

本分工已读取附件文本、WP01输入/装配/接口文档、当前参数、来源清单；对下列JSON读取了本文件使用的字段。厂家公开资料读取范围/文件哈希另见VENDOR_SOURCE_RECEIPT。完整模型未在本分工重新加载，快照图像为 `NOT_READ_BY_THIS_SUBTASK`；CAD读回/几何验证由本轮相应设计工作承担。

| 来源ID | 路径/范围 | 本次SHA-256 |
|---|---|---|
| USER_WP02 | `C:/Users/stude/Downloads/WP02_KEY_ASSEMBLY_DESIGN_PROMPT_ZH (1).md`；建议内容已与本轮用户请求区分 | `0F7631CA1D07A8F7F0D089900D27D5AEB272B8510489B36C448D6B2E82F49979` |
| WP01_PARAM | [当前参数](../service_robot_wp01_20260905/design_parameters.json) | `9AB316460388C507C34B1BE83ED1616AFABAA34E51C835ECBFEA973C98F018B2` |
| WP01_SOURCES | [来源清单](../service_robot_wp01_20260905/SOURCE_INPUTS.json) | `D2163239B082BAB1454E89DAB23AA6BC83C1BD805FEE75FC8E6430F430F398F9` |
| WP01_IF | [接口几何](../service_robot_wp01_20260905/results/INTERFACE_GEOMETRY.json) | `4B5601F9808EA26F11D1B5029E3DB28407F552104AD36AC52F5EF3E58FB6EF39` |
| WP01_PARK | [开放停放构建收据](../service_robot_wp01_20260905/results/stowed_build_receipt.json)；根变换/支承/质量字段 | `75074CADCB7B67FECDF32ABC5866545E6E2A2FF000B145C79B2CEF26B6B38534` |
| WP01_DELIVERY | [交付收据](../service_robot_wp01_20260905/results/DELIVERY_RECEIPT.json)；交付级别/状态/源拓扑范围 | `F10E922D138470621369D1B9D91293523BB873D8B521E7DCA50E787D47F7FCCF` |
| WP01_T | [矩阵传递](../service_robot_wp01_20260905/results/TRANSFORM_TRANSFER.json)；误差范围 | `192CB0D5DEEB4802D12860EBA1DD4A87D5E87C89C8FE75534523BB352A6B5033` |
| M3R_DRV | 上文链接的 `M3R_PARAMETER_DRIVER_V2.json` | `643426E7C2868638EB469025E05F29FE7B77EC7293495A17234B7C026FC16970` |
| M3R_PROBE | 上文链接的 `M3R_B601_BREP_INTERFACE_MEASUREMENT.json` | `5FAF23CB7239219E895281E964A0FACAC5F7E6E47AC6E0A40F6B37D47AA6D11D` |
| ACCEPTED_URDF | [原URDF](../cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf)；数字质量/拓扑来源 | `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164` |

具体测量项和当前空值见 [MEASUREMENT_REGISTER.csv](MEASUREMENT_REGISTER.csv)；三类载荷见 [LOAD_CASES.json](LOAD_CASES.json)。CSV里的字面量 `null` 表示尚无数据，导入计算时必须解析为空值，禁止按0使用。
