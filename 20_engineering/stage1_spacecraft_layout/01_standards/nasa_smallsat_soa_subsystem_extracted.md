# NASA Small Spacecraft Technology SOA 2026 分系统资料提取

## 1. PDF 文件状态

| item | value |
|---|---|
| file | `NASA_Small_Spacecraft_Technology_SOA_2026.pdf` |
| sha256 | `3272266C06740C6FC9EE20AAC0EAB8A69FA1C8D6F3057B8D5CD7238D8B8D0AE0` |
| size_bytes | 16607339 |
| pages | 458 |
| text_extraction | read_ok_with_nonfatal_warnings |
| notes | `pypdf` 解析时出现若干 wrong pointing object 警告，但正文文本可读取；本轮仅写入可定位文本内容。 |

## 2. 提取范围

本轮重点提取支持 300-500 kg 空间服务微卫星概念和缩比 6U/12U 展示模型的内容：

- 前言、Scope 与平台章节：小航天器质量级别、完整平台、hosted services、ESPA-class under 500 kg。
- Power：EPS、太阳能、电池、PMAD。
- In-Space Propulsion：推进类别、成熟度和接口注意事项。
- GNC：ADCS、传感器、LiDAR、RPO/RPOD、相对导航。
- Structures, Materials, and Mechanisms：材料、主结构、可展开机构、机器人操纵器。
- Thermal Control：热平衡、被动/主动热控、小航天器热控限制。
- Small Spacecraft Avionics：CDH、FSW、OBC、AI/ML、集中/分布式架构。
- Deorbit Systems：主动碎片清除、服务星捕获/对接、机器人机构案例。

## 3. 与本项目直接相关的约束/流程/参数

| topic | PDF text basis | extracted item | project meaning |
|---|---|---|---|
| SOA 使用边界 | p.14 | SOA 是公开资料综述，不是原始标准；技术成熟度会随任务、环境和可靠性要求变化。 | 本项目可引用 SOA 作为技术现状论据，但不能把供应商/案例写成项目已采用。 |
| 质量级别 | p.12, p.15-p.16 | 2023 后出现 201-600 kg mini-class 小航天器星座；SOA 采用 minisatellite 100-180 kg、microsatellite 10-100 kg 等传统分类，并指出 CubeSat 已跨 nano/micro 范围。 | “300-500 kg 服务微卫星”在 SOA 传统分类中更接近新兴 mini-class/ESPA-class 表述；报告中要区分比赛用语与 SOA 质量分类。 |
| 完整平台分系统 | p.21 | spacecraft bus 通常提供 power generation/storage、thermal control、ADCS、navigation/timing、communications、propulsion、C&DH。 | 12U 展示模型分舱应覆盖任务舱、平台舱、推进通信舱，并能对应上述分系统。 |
| Payload/platform interface | p.21-p.22 | 平台服务/hosted service 通常定义 payload acceptance envelope、mass、volume、mounting constraints、keep-out zones、CG limits、power budgets、thermal、data、ADCS performance、environmental qualification、radiation、software/telemetry/ground data interfaces。 | Stage 1-C 应把 reBot 和相机当作 payload/robotics package，定义机械、质量、电源、热、数据和 ADCS 接口。 |
| ESPA-class under 500 kg | p.34 | ESPA-class 平台通常 under 500 kg，需确认 ring/adapter 机械兼容、分离系统、包络、接口载荷、冲击和振动环境。 | 300-500 kg 服务星概念可用 ESPA-class 作为报告参考；12U 缩比模型不能混同为真实 ESPA 平台。 |
| Power/EPS | p.45, p.47 | EPS 包括发电、储能和分配，通常占显著体积和质量；小平台 EPS 体积常是设计约束；预设计/已验证太阳板有助于降低成本、进度和制造风险。 | 平台舱必须留 EPS/电池/PMAD 占位；太阳板布置需同时服务功率、热控、机械臂避让和相机视场。 |
| Propulsion | p.80 | 小航天器推进类别包括 chemical、electric 和 propellant-less；市场资料存在未验证或不完整的情况，成熟度需独立验证。 | 后部推进/通信舱先做推进占位和接口预留，不在 Stage 1 宣称推进系统选型完成。 |
| GNC sensors and RPOD | p.160-p.187 | GNC 章节覆盖 reaction wheels、magnetic torquers、thrusters、star trackers、magnetometers、sun sensors、horizon sensors、inertial sensing、GPS、LiDAR；RPO/RPOD 需要估计相对位置、速度和姿态。 | 相机/视觉、LiDAR 或等效传感器应服务目标相对导航；机械臂抓取前需要目标相对位姿，不应只依赖 VLA 输出。 |
| RPO complexity | p.184-p.187 | 小航天器 PFF/RPO 任务在硬件、软件和运行设计上仍复杂；未来方向包括 autonomous formation flying、RPOD 和 PNT。 | 本项目可把 RPO/RPOD 作为高层任务背景；Stage 2 只承诺 free-flyer/GJM/RNS 仿真，不虚构完整在轨 RPO。 |
| Structures/materials | p.194 | 材料选择要满足密度、热膨胀、辐射、模量、强度、韧性；还要考虑热平衡、热应力、出气和热变形。 | OreSat 结构参考和 reBot 转接座需要记录材料、热/出气和结构载荷假设；CAD 不是只画外观。 |
| Deployable structures | p.202 | 常见可展开结构包括天线、散热器、太阳板、重力梯度杆和仪器；小航天器适合用可展开结构提升紧凑平台能力，但轻量、低功耗、紧凑展开设计有限。 | 太阳板、天线和机械臂必须分别记录收拢/展开包络；避免把展开机构写成已成熟设计。 |
| Robotic manipulator | p.204 | 小航天器社区更关注在轨服务；机器人操作可用于维修、组装、服务、碎片捕获、维护、建造和修复，但这些任务昂贵且高风险；小航天器机器人系统可小体积收拢并自动/半自动执行任务。 | reBot 等效机械臂作为展示和动力学等效模型是合理叙事；必须保留收拢体积、安装刚度、接口、质量惯量和风险说明。 |
| Thermal control | p.227-p.230, p.240 | 热控需要平衡太阳、反照、行星红外、内部发热、储热和辐射散热；小航天器受低热容、有限外表面积、有限体积、有限功率和功率密度影响；被动热控包括涂层、MLI、导热带、热管、遮阳、热接口等；主动热控受功耗、质量和体积限制。 | 相机、OBC/EPS、电池、反作用轮、机械臂驱动和太阳板的布置必须考虑散热路径和热隔离。 |
| Avionics/CDH/FSW | p.250-p.252 | 航电包括 CDH、FSW、payload/subsystem avionics；CDH 管理命令、遥测、实时控制、网络和数据存储；架构可集中或分布。 | 平台舱应给 OBC/C&DH、数据链路、相机处理和机械臂控制预留空间；VLA 只能作为高层任务决策，不直接替代低层控制。 |
| Avionics autonomy | p.251, p.271 | 现代 SmallSat 航电趋势包括更高数据接口、AI/ML onboard accelerators、cybersecurity、FSW middleware、autonomy、machine vision、digital twins 和机器人 manipulator 相关设计。 | 竞赛报告可以把 VLA/视觉决策归入高层自治/任务规划；低层仍由运动学、动力学和控制器承担。 |
| Active debris removal | p.443-p.445 | 主动碎片清除常涉及服务星与目标会合，通过 attachment/docking 捕获并降低轨道；核心技术包括 autonomous navigation、RPO 和 robotics；案例包括 ClearSpace 机器人臂和 KMI 多臂/黏附机构。 | 三类目标模型和机械臂抓取接口有 SOA 背景支撑；但本项目不能宣称已具备真实碎片清除能力。 |

## 4. 本项目采用方式

- 平台舱：按 SOA 的 bus 服务拆分，放置 OBC/C&DH、EPS/电池、GNC/反作用轮、热控和数据接口占位。
- 任务舱：放置 reBot 基座、相机/视觉传感器、照明/标记、抓取接口和目标接近方向；所有接口记录 mass/volume/power/thermal/data/ADCS 需求。
- 推进通信舱：保留推进、通信和调试接口占位；推进只作为 Stage 1 概念接口，不做未验证选型。
- 300-500 kg 概念服务星：报告中优先使用 SOA 的 mini-class/ESPA-class under 500 kg 语言；12U 仍作为缩比展示主模型。
- 机械臂安装：引用 SOA 的 robotic manipulator 与 servicing/debris capture 背景，转化为收拢体积、展开包络、安装刚度、质量惯量和控制接口需求。
- 热控与功率：太阳板布局不只服务外观，还要兼顾 EPS、散热、相机视场和机械臂避让。
- VLA/高层智能：仅进入任务决策、目标选择、抓取点候选和演示叙事，不直接输出关节力矩。

## 5. 需要后续验证的问题

- [ ] 300-500 kg “服务微卫星”在报告中是否改称为 “300-500 kg ESPA-class/mini-class service spacecraft concept” 或中文等效表述。
- [ ] 12U 缩比展示模型与 300-500 kg 概念服务星之间的比例、用途和边界是否分清。
- [ ] reBot、相机、OBC/EPS、GNC、通信、推进占位是否都有 mass/volume/power/thermal/data 接口字段。
- [ ] 太阳板面积、电源预算和热控面是否与机械臂工作空间冲突。
- [ ] GNC/RPOD 传感器需求是否与目标模型 AprilTag/视觉标记一致。
- [ ] 机械臂安装是否记录收拢体积、安装刚度、质心影响、惯量影响和控制接口。
- [ ] 主动碎片清除案例是否只作为报告背景，而非项目已实现能力。

## 6. 可进入未来飞行器大赛报告的内容

- 300-500 kg 服务星平台背景：SOA 中 mini-class 增长和 ESPA-class under 500 kg 的引用。
- 平台舱/任务舱/推进通信舱分系统图：对应 power、thermal、GNC、C&DH、propulsion、communications、robotics。
- 机械臂任务背景：小航天器在轨服务、碎片捕获、机器人操纵器的技术现状。
- 接口需求总表：mass、volume、mounting、keep-out、CG、power、thermal、data、ADCS。
- 热控与电源布局图：太阳板、散热面、电子舱、机械臂驱动之间的关系。
- RPOD/视觉感知背景：相机/LiDAR/相对导航为目标捕获服务。

## 7. 不适合直接采用的内容

- SOA 不是设计标准，不能直接作为 CAD 尺寸或合规条款。
- SOA 中具体供应商产品、任务案例和 TRL 不能写成本项目选型或已完成验证。
- ESPA-class under 500 kg 不能直接套到 12U 缩比展示模型。
- ClearSpace、Astroscale、KMI 等案例只能作为任务背景，不应写成本项目的技术实现结果。
- AI/ML、machine vision、digital twin 等趋势只能支撑高层叙事，不能替代 Stage 2 GJM/RNS 动力学建模。
