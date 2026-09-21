# Stage 1-B+ 标准约束汇总

## 1. 汇总说明

本表只汇总本轮从三份 PDF 文本层实际读取到的标准约束、系统工程流程和技术现状。CDS Appendix B 图纸页的具体尺寸细项因文本层解析失败，不写入已确认约束。

Priority 定义：

- P0：必须进入 Stage 1-C CAD/布局。
- P1：进入竞赛报告。
- P2：后续 Stage 2 动力学使用。
- P3：暂存参考。

## 2. 总表

| source | topic | extracted_item | project_impact | layout_impact | robot_arm_mount_impact | mass_inertia_impact | priority | next_action |
|---|---|---|---|---|---|---|---|---|
| CDS Rev.14.1 | Scope and authority | CDS 用于 1U-12U 初步兼容性设计，Launch Provider 要求优先。 | 作为布局约束来源，不作为最终发射合规声明。 | 6U/12U 先按 CDS 做包络检查。 | 安装面按标准约束先做保守设计。 | 质量属性仍需具体部署器/任务复核。 | P1 | 在报告中写清 CDS 是参考边界。 |
| CDS Rev.14.1 | Coordinate/envelope | 坐标系原点在几何中心；物理尺寸应符合 Appendix B；图纸尺寸文本解析失败。 | Stage 1-C 不能跳过图纸人工复核。 | CAD 需建立几何中心坐标系和包络检查层。 | `^S T_B` 应说明相对几何中心还是质心。 | 质心/惯量表需记录参考点。 | P0 | 人工复核 Appendix B 1U/3U/6U/12U 图纸。 |
| CDS Rev.14.1 | External protrusion | 指定侧面突出物不得超过 6.5 mm，导轨到首个突出物最小 8.5 mm。 | 建立收拢状态合规检查。 | 相机、天线、太阳板、机械臂折叠状态要避开外包络。 | reBot 法兰和折叠机械臂不得占用导轨接触区。 | 外部部件质量需单列，便于评估质心偏移。 | P0 | 在 Stage 1-C CAD 中画出 6.5 mm/8.5 mm 检查层。 |
| CDS Rev.14.1 | Rails/contact | 导轨粗糙度、边缘半径、端面接触区和 75% 导轨接触有要求。 | 结构参考不能只画外壳。 | 保留导轨和接触面。 | 安装座不得破坏导轨接触路径。 | 导轨/转接座质量计入结构子系统。 | P0 | CAD 中标注导轨、接触面和禁占区。 |
| CDS Rev.14.1 | Mass and CG | 典型最大质量：6U 12 kg，12U 24 kg；6U/12U 质心范围相对几何中心给出。 | 质量预算进入 Stage 1-C。 | 机械臂、电池、反作用轮和推进占位需服务配平。 | 安装点尽量靠近质心投影。 | 质量、CG、MOI/POI 表必须建立。 | P0 | 用质量表检查 6U/12U 质心范围。 |
| CDS Rev.14.1 | Deployables and inhibits | 太阳板/天线等部署件由 CubeSat 自身约束；至少三重独立抑制；部署延时不小于 30 min。 | 竞赛展示需区分在轨安全时序与地面演示。 | 太阳板、天线、机械臂收拢/展开包络分开检查。 | 机械臂若作为可展开/运动机构，应定义锁定与安全姿态。 | 部署状态变化影响碰撞包络，质量属性需状态说明。 | P0 | 建立 deployables 收拢/展开/安全姿态检查表。 |
| CDS Rev.14.1 | Dispenser systems | rail 与 tab 两类约束系统不一定兼容；额外质量/突出物/附加体积取决于部署器。 | 不能默认兼容所有部署器。 | 选择一个参考部署器约束系统。 | 转接座不能默认占用 Tuna Can 或扩展突出物空间。 | 额外结构会改变 CG/MOI。 | P0 | Stage 1-C 明确 rail-reference 或 tab-reference。 |
| CubeSat 101 | Mission concept | 概念开发从任务目标和基本任务细节开始。 | 三类任务叙事先行。 | 布局围绕目标捕获、在轨服务、碎片清除组织。 | 安装位服务任务面和目标接近方向。 | 不直接影响数值，但决定质量预算对象。 | P1 | 写入竞赛报告任务概念章节。 |
| CubeSat 101 | Design margin | 保持设计简单，重要部件靠外，不要设计到包络极限。 | Stage 1-C 不能只追求满占空间。 | 留装配、维修、测量和视频展示空间。 | reBot、相机、线缆接口保持可达性。 | 留质量裕度，估计值标注 margin。 | P0 | 给 CAD 设计增加装配/测量裕度说明。 |
| CubeSat 101 | ICD and verification | 任务协调提供 ICD、交付物、需求验证和环境测试要求。 | 本项目建立 ICD-lite。 | 每个布局约束要有检查证据。 | 安装座、基座坐标和接口要可验证。 | 质量属性报告作为交付物。 | P0 | 建立 Stage 1-C layout ICD-lite。 |
| CubeSat 101 | Mass properties report | 质量属性报告包括总质量、CG、MOI、POI，并核对坐标系。 | 质量惯量表是阶段交付物。 | 内部舱段布置必须能解释 CG。 | 机械臂和转接座质量单列。 | Stage 2 GJM/RNS 输入依赖该表。 | P0 | 更新质量惯量预算模板的填写说明。 |
| CubeSat 101 | Dimensional verification | 装配后、环境测试前检查尺寸，测试前后都应复核。 | 建立尺寸检查清单。 | 机械臂折叠、相机、太阳板、天线都纳入尺寸检查。 | 安装座/折叠臂进入验收图。 | 不直接给惯量，但影响几何包络。 | P0 | 形成 Stage 1-C CAD 尺寸验收表。 |
| CubeSat 101 | Risk and anomaly reporting | 可行性评审关注技术、韧性、风险；测试异常需记录和处理。 | 建立风险表。 | 布局风险要闭环。 | 目标碰撞、遮挡、接触失败进入风险清单。 | 质量估计不确定性进入风险清单。 | P1 | 生成 Stage 1 风险清单。 |
| CubeSat 101 | Component template | 组件模板记录外部/内部、数量、材料、形状、质量和尺寸。 | 作为分系统和质量预算模板依据。 | 结构、天线、太阳板、开关、电池、ADCS、C&DH、通信、线缆等都入表。 | reBot 转接座作为 80_third_party/external/major 或 robotics 子系统记录。 | 质量、尺寸和材料进入惯量估算来源。 | P0 | 把组件模板字段映射到质量惯量 CSV。 |
| SmallSat SOA 2026 | Scope and taxonomy | SOA 是公开技术综述；2023 后 201-600 kg mini-class 增长；ESPA-class 可 under 500 kg。 | 300-500 kg 概念服务星应用 mini-class/ESPA-class 语言。 | 12U 是缩比展示模型，不等同 300-500 kg 平台。 | 机械臂安装要分清缩比与概念平台。 | 缩比模型和概念平台质量惯量分开。 | P1 | 报告中统一质量级别表述。 |
| SmallSat SOA 2026 | Bus interfaces | 平台需定义 mass、volume、mounting、keep-out、CG、power、thermal、data、ADCS、环境和软件接口。 | 建立服务星总接口表。 | 三舱布局按接口字段组织。 | reBot 和相机作为 payload/robotics package 定义接口。 | CG、质量和功率热接口影响惯量布局。 | P0 | 生成 Stage 1-C 接口需求总表。 |
| SmallSat SOA 2026 | ESPA-class | under 500 kg 平台需确认 ring/adapter 机械兼容、分离系统、包络、接口载荷、冲击和振动。 | 支撑 300-500 kg 服务星工程背景。 | 推进通信舱和结构主承力需有概念说明。 | 机械臂真实平台安装需考虑接口载荷。 | 概念平台惯量不同于 12U 缩比模型。 | P1 | 竞赛报告加入 ESPA-class 背景说明。 |
| SmallSat SOA 2026 | EPS/power | EPS 占显著体积和质量，包含发电、储能、分配；小平台 EPS 体积常是约束。 | EPS/电池/PMAD 是平台舱核心。 | 太阳板、电池、PMAD 占位不能事后补。 | 机械臂功耗和电源接口需预留。 | EPS/电池通常显著影响 CG/MOI。 | P0 | Stage 1-C 固定 EPS/电池/PMAD 占位。 |
| SmallSat SOA 2026 | Propulsion | 小航天器推进技术种类多，成熟度和资料需独立验证。 | 推进只做占位，不宣称选型完成。 | 后舱保留推进接口、热隔离和安全边界。 | 机械臂任务面应与推进喷流/接口方向分离。 | 推进剂/推进器质量会显著改变惯量。 | P0 | 后舱建立推进占位和待验证字段。 |
| SmallSat SOA 2026 | GNC/RPOD sensors | RPO/RPOD 需要相对位置、速度和姿态估计；传感器含 star tracker、sun sensor、IMU、GPS、LiDAR 等。 | 目标捕获需要传感器闭环背景。 | 相机/视觉标记/LiDAR 占位服务目标接近。 | 机械臂抓取前需目标相对位姿输入。 | GNC 部件质量进入平台舱预算。 | P1 | 建立传感器与目标 AprilTag/抓取点映射。 |
| SmallSat SOA 2026 | Structures/materials | 材料选择需考虑密度、热膨胀、辐射、强度、韧性、出气和热变形。 | 结构不是单纯外观。 | CAD 需记录材料和热/出气假设。 | 转接座材料、刚度和表面处理需记录。 | 材料密度直接影响质量惯量。 | P0 | CAD 零件表加入材料/密度/来源字段。 |
| SmallSat SOA 2026 | Deployable structures | 天线、散热器、太阳板、booms 等可展开结构提升紧凑平台能力，但轻量低功耗设计有限。 | 展开机构要保守表述。 | 收拢/展开包络分别建图。 | 机械臂运动包络需避让太阳板/天线。 | 展开构型影响碰撞包络，质量模型需说明。 | P0 | 生成收拢/展开/碰撞包络图需求。 |
| SmallSat SOA 2026 | Robotic manipulator | 小航天器在轨服务和碎片捕获推动机器人操纵器；任务昂贵且高风险。 | reBot 作为等效机械臂和展示样机有报告背景。 | 任务舱需支持机械臂收拢、展开和目标接近。 | 安装刚度、基座坐标、力/力矩接口需定义。 | 机械臂质量惯量是 Stage 2 关键输入。 | P0 | Stage 1-C 完成转接座需求到 CAD 参数映射。 |
| SmallSat SOA 2026 | Thermal control | 小航天器热控受低热容、有限外表面积/体积/功率和功率密度约束。 | 热控纳入布局，而非后处理。 | 电子舱、太阳板、散热面和相机热路径要说明。 | 机械臂驱动与转接座热路径需预留。 | 热控件和散热面质量入表。 | P0 | 在布局图中标注散热面/热隔离区。 |
| SmallSat SOA 2026 | Avionics/CDH/FSW | CDH/FSW/OBC 管理命令、遥测、实时控制、网络、数据存储；趋势含 AI/ML 和自治。 | VLA 放在高层任务决策。 | OBC/C&DH 与相机处理占平台舱空间。 | 机械臂低层控制不由 VLA 直接输出力矩。 | 航电板卡质量和热耗散入预算。 | P1 | 报告中写清高层决策与低层控制分界。 |
| SmallSat SOA 2026 | Active debris removal | 服务星与目标会合、捕获/对接、降轨；核心技术含 autonomous navigation、RPO、robotics。 | 支撑目标捕获/碎片清除叙事。 | Target-1/2/3 模型具有任务背景。 | 机械臂抓取接口与非抓取区域必须定义。 | 目标模型质量惯量进入 Stage 2。 | P1 | 报告中作为任务背景，不写成已实现能力。 |

## 3. P0 约束数量

本表共有 P0 条目 18 项。它们必须进入 Stage 1-C CAD/布局或相应检查清单。

## 4. 当前不可直接进入 CAD 的项目

- CDS Appendix B 图纸页的 1U/3U/6U/12U 精确尺寸细项：`drawing_text_parse_failed`，需人工目视复核。
- NASA SOA 供应商/任务案例：只能作为报告背景，不作为本项目硬件选型。
- 真实发射许可、NASA CSLI 流程和飞行认证：只作为系统工程参考，不作为本项目当前状态。
