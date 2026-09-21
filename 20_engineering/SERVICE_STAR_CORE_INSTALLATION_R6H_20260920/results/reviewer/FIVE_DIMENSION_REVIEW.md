# R6H 独立五维审查

状态：`DIGITAL_CANDIDATE_REVIEW_COMPLETE_WITH_ENGINEERING_HOLDS`。仅审水平、最小改动数字安装候选；制造、上电、飞行与整星完整性均保持 HOLD。

审阅者只写 reviewer 目录，没有修改设计源。当前受检布局 MAIN 原点 S[-164,86,11.5] mm，旋转矩阵 I；23 新增、4 改几何、6 姿态变更中杆件重复计入，合计32个不同受影响实例。

| Area | Status | Key Finding |
|------|--------|-------------|
| Completeness | PASS | 限定水平MAIN、最小P60支点变更、热桥和推进准备的数字安装范围完整。 |
| Risk Identification | CONCERN | 高度、孔间余肉、紧固与电热/绝缘风险已明确，等待工程数据验证。 |
| Implementability | CONCERN | 可供数字装配复核；托盘耳台工艺、紧固公差、工具路径和OEM实际接口未冻结。 |
| Cost Reasonableness | CONCERN | 保留现有模块的改动范围可核对，实物MPN、加工工艺、交期与报价未冻结。 |
| Validation Coverage | CONCERN | 数字检查须由逐实体增强与负控绑定；物理EVT/DVT/PVT和连续过程验证尚未执行。 |

## 第1轮：Completeness

- Status: PASS
- 已通过 Gate 的项：无可继承的Gate 1–5通过声明；既有电气选型沿用R5E独立审查，当前只复核改动与跨域接口。

## 第2轮：Risk Identification

- Status: CONCERN
- 已通过 Gate 的项：既有R5E器件选择不重审；本轮高度、支撑、电热与接地接口重新审。

**R6H-R01 — HIGH_BEFORE_HARDWARE**

Findings: D201、D202、U201、U205 高度仍为6 mm未验证包络；35个位号的混合模型并非35件受控OEM完整模型。

Recommendation: 以受控图纸或样品补四个高度和端子/线鼻/焊脚/底面尺寸后，保持来源版本并重跑受影响的静态、插装、工具和线束间距检查。

证据：[inputs/MAIN_GEOMETRY_COVERAGE.json](../../inputs/MAIN_GEOMETRY_COVERAGE.json)。

**R6H-R02 — HIGH_BEFORE_MANUFACTURING**

Findings: MAIN隔柱2附近保留旧Ø3.4孔，孔间名义余肉1.072136 mm。隔柱接触面积18.983580/19.195131 mm²，底垫接触28.195956/29.405307 mm²。新P60耳台、甲板和框架孔还未按真实材料、载荷和预载校核。

Recommendation: 将相邻两孔、偏置支点、耳台和框架同时纳入净截面/承压/疲劳与预载检查。用冻结的材料、公差、载荷和安全系数判定；几何接触面积不充当强度证明。

证据：[results/reviewer/BEARING_STACK_REVIEW.json](BEARING_STACK_REVIEW.json)、[results/reviewer/GEOMETRY_REVIEW.json](GEOMETRY_REVIEW.json)。

**R6H-R03 — HIGH_BEFORE_POWER**

Findings: 4 mm铝热桥+0.5 mm绝缘垫仅闭合接口板名义间隙；热垫MPN、压缩厚度、导热率、耐压、接触压力和保持方式未知。MAIN/Q201热路径没有因此闭合。

Recommendation: 选择热垫并绑定实测压力/厚度、最坏功耗、温度边界、接触热阻和绝缘/接地方案；完成限能热试验后再放行相应电功率。6061库赋值不等于热处理或飞行资格。

证据：[inputs/INSTALLATION_LAYOUT.json](../../inputs/INSTALLATION_LAYOUT.json)、[results/reviewer/GEOMETRY_REVIEW.json](GEOMETRY_REVIEW.json)、[results/NATIVE_ASSEMBLY_DELIVERY.json](../../results/NATIVE_ASSEMBLY_DELIVERY.json)。

**R6H-R04 — HIGH_BEFORE_POWER**

Findings: 安装孔附近铜皮净空、金属紧固件与机壳的隔离/受控连接、线鼻与接线应力尚未获得电气装配验证。STOP/AUX未安装，原R5E未布板候选也未安装。

Recommendation: 按真实PCB层叠/孔/铜皮、端子和回流路径核验绝缘、接地、ESD/EMC与应力释放；逐针完成后先做限能负载验证。制造、上电和飞行字段继续false。

证据：[inputs/INSTALLATION_LAYOUT.json](../../inputs/INSTALLATION_LAYOUT.json)、[inputs/MAIN_GEOMETRY_COVERAGE.json](../../inputs/MAIN_GEOMETRY_COVERAGE.json)。

## 第3轮：Implementability

- Status: CONCERN
- 已通过 Gate 的项：无新增Gate豁免；未实施的STOP/AUX和R5E候选保持原状态。

**R6H-I01 — MEDIUM_BEFORE_MANUFACTURING**

Findings: P60托盘新增5×12×2 mm耳台超出旧件外缘。安装BOM已改为LOCAL_BEARING_TAB_AND_HOLE_CHANGE_NEW_MACHINING_CANDIDATE，HORIZONTAL_INSTALLATION.md已明确新加工或经验证连接工艺。输入的LOCAL_MOUNTING_HOLE_CHANGE_ONLY旧标签为保持源哈希未改，change字段正确；该源标签仅保留为observation。

Recommendation: BOM/说明纠正已核验，无需继续要求修改。制造前仍须冻结整体新毛坯加工或经验证连接工艺、材料及强度，不可按单纯钻孔返工释放。

证据：[inputs/INSTALLATION_LAYOUT.json](../../inputs/INSTALLATION_LAYOUT.json)、[docs/INSTALLATION_BOM_DELTA.csv](../../docs/INSTALLATION_BOM_DELTA.csv)、[docs/hardware/HORIZONTAL_INSTALLATION.md](../../docs/hardware/HORIZONTAL_INSTALLATION.md)。

**R6H-I02 — MEDIUM_BEFORE_ASSEMBLY**

Findings: 最近隔柱/原适配器净距0.5 mm；四点贯穿安装和34处名义承压接触成立，但工具扫掠、插装顺序、真实螺纹啮合和压紧公差未验证。

Recommendation: 冻结M3x30、OD6×20隔柱、82 mm杆、螺母/垫片的实物图纸；按完整公差链确认最小间距、夹持长度和啮合长度。建立包括P60最后装入的顺序及工具包络，并以样件装配验收。

证据：[results/reviewer/GEOMETRY_REVIEW.json](GEOMETRY_REVIEW.json)、[results/reviewer/BEARING_STACK_REVIEW.json](BEARING_STACK_REVIEW.json)。

**R6H-I03 — HIGH_BEFORE_PROPULSION_FREEZE**

Findings: 推进准备已经绑定当前水平装配的9保留对象+1改托盘，9项OEM缺口与PA01–PA12工作单原样保留；未冻结推进型号、喷口/储箱及实际端点。

Recommendation: 按OEM模板补受控孔系、#4-40接口适用性、逐针/电流时序、喷口位置和方向、并发/脉冲、喷流禁入及捕后质心；先计算安装与控制可达性，再派生候选压力/热/馈线布局。功能路由不提供下料或点火信用。

证据：[inputs/PROPULSION_ASSEMBLY_PREPARATION.json](../../inputs/PROPULSION_ASSEMBLY_PREPARATION.json)、[inputs/PROPULSION_OEM_INPUT_TEMPLATE.json](../../inputs/PROPULSION_OEM_INPUT_TEMPLATE.json)、[docs/PROPULSION_NEXT_WORK_ORDERS.csv](../../docs/PROPULSION_NEXT_WORK_ORDERS.csv)、[results/reviewer/PROPULSION_PREPARATION_REVIEW.json](PROPULSION_PREPARATION_REVIEW.json)。

## 第4轮：Cost Reasonableness

- Status: CONCERN
- 已通过 Gate 的项：本轮无PCB布线/层数修改，既有层数不因装配改动重新裁决。

**R6H-C01 — MEDIUM_BEFORE_PROCUREMENT**

Findings: 本轮23新增、4几何改件、5仅复用姿态变更共32个不同实例；复用减少改动，但紧固件等级/材料、绝缘垫MPN、82 mm杆及带耳托盘工艺、采购单价/交期未冻结。

Recommendation: 建立目标数量的报价BOM，比较现货标准件与定制杆/托盘加工成本，记录单一来源和备选。现阶段不声称整机造价通过；电子选型未改。R5E的国产替代仍缺等效引脚、失效模式及时序证据，采购前另做ECO验证，不能假定直接替换。

证据：[docs/INSTALLATION_BOM_DELTA.csv](../../docs/INSTALLATION_BOM_DELTA.csv)。

## 第5轮：Validation Coverage

- Status: CONCERN
- 已通过 Gate 的项：既有静态证据仅在相同来源与范围内保留，不能继承制造/上电/飞行Gate。

**R6H-V01 — HIGH_BEFORE_RELEASE**

Findings: 5203项几何/来源检查、165对增量布尔、34处承压接触与146项推进准备检查仅证明限定数字候选。三离散姿态不等于连续装入/运动全包络。实际材料质量、全系统电热及制造强度尚未通过。

Recommendation: EVT依次做被动装配、工具与线束检查、逐针/绝缘、限能负载、温升与保护故障注入；DVT针对冻结工况做振动、循环与环境试验；PVT在量产需求成立后验证工艺一致性。每项先冻结量化限值与源版本，未知不得跳级。

证据：[results/reviewer/GEOMETRY_REVIEW.json](GEOMETRY_REVIEW.json)、[results/reviewer/PROPULSION_PREPARATION_REVIEW.json](PROPULSION_PREPARATION_REVIEW.json)。

**R6H-V02 — MEDIUM_SCOPE**

Findings: 1.60 mm整板是夹紧用总层包络，保留元件模型底面1.595 mm可能产生5 µm模型嵌入。它不是Cu/FR4/阻焊分层几何，也没有整板单一材料赋值。

Recommendation: 公开说明模型层级；将来需要真实层间质量、热阻或微小间隙时从ECAD层叠重建并另审。不得宣称PCBA内部逐元件零干涉或完整材料/质量真值。

证据：[inputs/MAIN_GEOMETRY_COVERAGE.json](../../inputs/MAIN_GEOMETRY_COVERAGE.json)、[results/reviewer/BOARD_INTEGRATION_DIAGNOSIS.json](BOARD_INTEGRATION_DIAGNOSIS.json)。

**R6H-V03 — HIGH_METHOD_BOUNDARY**

Findings: R7记录整体compound布尔漏检风险，其70.4 mm³历史反例没有探针坐标，本次未复现。R7的129对回执与当前R6H的layout/check哈希相同。独立增强已覆盖165对/70唯一对，含MAIN与宿主12对、与新增支撑/紧固12对，均为0碰撞/0UNKNOWN。有明确坐标的6.4 mm³穿板探针两种方法都检出，远离探针为0。

Recommendation: 以SOLIDWISE_CONFIRMATION_REVIEW.json逐实体增强和有坐标控制支撑当前碰撞结论；不把必须复现旧方法漏检当作放行条件，也不声称历史70.4反例已复现。结论限三离散姿态、受检新增/改装交互；不包括PCBA内部、未改宿主彼此、完整连续运动、工具或喷流。逐实体相交体积和不能用于质量或全局并集体积。

证据：[results/reviewer/SOLIDWISE_CONFIRMATION_REVIEW.json](SOLIDWISE_CONFIRMATION_REVIEW.json)。

## 已解决事项

- Tilted R6 is historical only; R6H MAIN rotation identity at [-164,86,11.5].
- Old 0.085 mm washer gap resolved by source-supported 1.60 mm total-stack envelope.
- Board default-volume failure preserved; adaptive/GK and independent empty symmetric difference restore the original 1e-7 ratio limit with two rejected wrong-thickness controls.
- No original adapter trimming, no exterior change, no battery/propulsion route move.
- Installation BOM and explanation now explicitly identify the new machined P60 bearing tab; only the source label remains as an observation.

## 独立检查回执

- [GEOMETRY_REVIEW.json](GEOMETRY_REVIEW.json)：PASS_WITH_DECLARED_ENGINEERING_HOLDS；SHA256 `ac206be86cc553a0a64601870f80e7061cfc2f32191d6168922b50fe9e4a6abe`。
- [BOARD_INTEGRATION_DIAGNOSIS.json](BOARD_INTEGRATION_DIAGNOSIS.json)：PASS_CAUSE_ESTABLISHED；SHA256 `b6d764270b00122ce07adbc8d5879db5e92255b11c3af27d51151dae616452ce`。
- [BEARING_STACK_REVIEW.json](BEARING_STACK_REVIEW.json)：PASS_NOMINAL_CONTACTS_WITH_STRENGTH_HOLD；SHA256 `d05321d9eb12a464ed0e2bca88f3f67e65858709ca40293a0175fe7ae132a9f8`。
- [PROPULSION_PREPARATION_REVIEW.json](PROPULSION_PREPARATION_REVIEW.json)：PREPARATION_PASS_WITH_OEM_HOLDS；SHA256 `ecab0c8d0abbe3240e7cbaee8907cc060c353ce2656a866581528c800f650854`。
- [ELECTRICAL_SOURCE_PRESERVATION.json](ELECTRICAL_SOURCE_PRESERVATION.json)：PASS_UNCHANGED_R5E_AND_V36；SHA256 `15be8072085cef663af01744dc30bb40904b2941107a01e1d615056e08b88f4c`。
- [NATIVE_ROUNDTRIP_REVIEW.json](NATIVE_ROUNDTRIP_REVIEW.json)：PASS_PARTS_GROUPS_TOP_CHAIN_WITH_SCOPE_HOLDS；SHA256 `65874c0fedb5ef492570096997278a76b232d467dc192f84e72c41449670ffbd`。
- [SOLIDWISE_CONFIRMATION_REVIEW.json](SOLIDWISE_CONFIRMATION_REVIEW.json)：PASS_R6H_INCREMENT_CONFIRMED_SOLID_BY_SOLID；SHA256 `a0cc37022c834799befdb36baa6fd73abbdd418c0a5331584666bb7e17362124`。
- [NATIVE_FINAL_REVIEW.json](NATIVE_FINAL_REVIEW.json)：PASS_SOURCE_LOCKED_HIERARCHICAL_NATIVE_REVIEW；SHA256 `ff99e7396b67cc0d1d16f9615f39c4e89fb949bfc8c5c0ae3570ad786340059f`。

原生总装完整复验：已通过独立回执绑定审阅。

名义承压接触不证明承载能力；功能推进包络及路由不证明OEM安装、真实针号或受压/点火能力。
