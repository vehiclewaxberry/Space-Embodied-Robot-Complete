# REORG-01-R：空间具身智能机械臂文献统一归档与阅读入口

状态：`REORG01R_COMPLETE`

生成日期：2026-07-22

单一真值源：[manifest.yaml](./manifest.yaml)

## 1. 这份归档解决什么问题

这不是“列一些机器人论文”，而是把比赛项目缺失的物理与智能链分开补齐：

> 航天器姿态/轨道状态 → 自由漂浮基座与机械臂耦合 → 接触捕获/消旋 → 柔性臂与 ANCF → 视觉/语言任务理解 → 经安全门控的动力学控制 → 在轨搭建或碎片清除任务证据

文献按三种读法标注：

- **定调**：定义问题、术语、技术版图与声明边界。
- **推导**：提取方程、假设、控制律、参数与可复现实验。
- **对标**：提取场景、指标、曲线、硬件或软件基线。

等级不是期刊评价，而是对当前项目的直接可用度：

- **A**：可直接约束模型、控制器、场景或机器门。
- **B**：工程实现、近邻方法或重要横向比较。
- **C**：跨领域迁移线索，只能形成待验证假设。

本地 PDF 位于被 Git 忽略的 `50_literature/pdf/`；第三方源码位于被 Git 忽略的 `80_third_party/vendor/`。引用时使用 [refs.bib](./refs.bib)，元数据争议以 [manifest.yaml](./manifest.yaml) 为准。当前 44 份本地 PDF 均按 `50_literature/pdf/NN_category/bibkey.pdf` 统一落盘；其中 23 篇已有完整阅读卡，原补充目录的 21 篇已完成题录、页数与哈希归档。逐篇卡片状态见 [notes/INDEX.md](./notes/INDEX.md)，本次 21 篇对照表与裁决见 [reorg01r_report.md](./reorg01r_report.md)。


## REORG-01-R 增量入口

- 21 份补充 PDF：10 份匹配既有 key，11 份新增 key；无未匹配文件。
- 用户列出的 10 条 DOI 全部 Crossref VERIFIED；另补入漏列的 `10.1109/70.817666`。
- 唯一仍缺全文：`gerstmayr2013ancfreview`。
- 详细清单：[reorg01r_report.md](./reorg01r_report.md)；当前落盘验收：[landing_check.md](./landing_check.md)。

## 2. 建议阅读顺序

1. 先读 V0 的 Papadopoulos、Rybus、Alizadeh，冻结任务与机械臂构型语言。
2. 用 V1 的 Wilde 建立自由漂浮航天器—机械臂动力学，再用 Yoshida/Nenchev 定义零反作用与碰撞边界。
3. 用 V2 的虚拟质量和阻抗匹配定义“能否抓、如何抓、抓后如何消旋”。
4. 用 V3 的 ANCF 文献定义柔性梁模型与验证题；超材料只作为材料侧候选，不替代结构动力学验证。
5. 用 V4 把视觉、语言和技能调度接到已经验证的状态估计、安全门与低层控制；不要让 UNKNOWN 直接变成动作。
6. 最后读在轨组装与平台文献，决定装配场景、整器姿控和地面证据方案。

## 3. V0 —— 总体定调综述

| 条目 | 等级 | 读法 | 归档状态 | 读什么 / 为什么 | 对应输出或图 |
|---|---:|---|---|---|---|
| `rybus2024manipulators` | A | 定调+对标 | 本地 PDF（手工补充） | 各类 IOS/ADR 机械臂的自由度、臂长、质量和末端执行器；用于回答“为什么是该臂长和该构型”。 | 机械臂构型与参数选型对比表 |
| `papadopoulos2021survey` | A | 定调 | 本地 PDF | 建模、规划、捕获、捕获后镇定的完整方法链。 | 任务阶段—算法—证据链总览图 |
| `alizadeh2024comprehensive` | A | 定调+对标 | 本地 PDF | OSAM-1、SPIDER、Canadarm3 等较新系统；补足传统综述后的工程进展。 | 系统代际与任务能力对比图 |
| `sst2024autonomous` | B | 定调 | 本地 PDF（SciOpen） | 自主性层级；区分遥操作、监督自主、技能调度和闭环自主。 | 自主等级阶梯图 |
| `zhang2022adcr` | B | 定调 | 本地 PDF | 机械臂主动碎片清除方法与研究热点演化。 | ADR 方法谱系与趋势图 |
| `ellery2019tutorial` | B | 定调+推导 | 本地 PDF | 基座反作用的物理直觉和空间机械臂入门。 | 基座—机械臂动量交换示意图 |

## 4. V1 —— 自由漂浮基座、GJM 与 Reaction Null-Space

| 条目 | 等级 | 读法 | 归档状态 | 读什么 / 为什么 | 对应输出或图 |
|---|---:|---|---|---|---|
| `wilde2018tutorial` | A | 推导 | 本地 PDF | VM、DEM、GJM 的关系、方程假设和工程推导；这是机器人动力学主骨架。 | GJM/RNS 控制框图、基座姿态扰动曲线 |
| `yoshida2001zrm` | A | 推导+对标 | 本地 PDF（作者自存档） | ETS-VII 零反作用机动飞行对标；DOI 已裁决为 `10.1109/ROBOT.2001.932590`。 | RNS 与朴素轨迹的基座扰动对比 |
| `xu2017reactiontorque` | A | 推导 | 本地 PDF（手工补充） | 反作用力矩代价与 RNS 的统一；DOI 已按 Crossref 题名相似度 1.000000 裁决。 | 零空间投影与反作用力矩统一图 |
| `nenchev1999impact` | A | 推导 | 本地 PDF（手工补充） | 捕获冲量如何传到自由漂浮基座，是 V1 到 V2 的动力学接口。 | 冲量传播和捕获后姿态响应图 |

V1 最小研究入口不是直接训练策略，而是先建立可审计方程与交叉验证：

- SPART / SpaceDyn / 现有 Pinocchio 模型给出同一刚体参数下的质量矩阵、广义雅可比和基座扰动。
- 基线控制为末端轨迹跟踪；对照控制为带 RNS/反作用力矩惩罚的冗余分配。
- 关键曲线至少包括末端误差、基座姿态误差、基座角速度、关节速度和角动量残差。

## 5. V2 —— 接触捕获、阻抗与消旋

| 条目 | 等级 | 读法 | 归档状态 | 读什么 / 为什么 | 对应输出或图 |
|---|---:|---|---|---|---|
| `yoshida2004impedance` | A | 推导 | 本地 PDF（手工补充） | 虚拟质量和阻抗匹配原始定义；决定捕获瞬间等效惯量如何匹配目标。 | 等效惯量—目标惯量匹配图 |
| `uyama2012compliantwrist` | B | 推导+对标 | 本地 PDF（手工补充） | 柔顺腕和关节阻抗的工程实现。 | 接触力峰值、回弹与基座扰动对比 |
| `uyama2016hybrid` | B | 推导 | 本地 PDF（手工补充） | 捕获后的混合阻抗/位置控制和目标消旋。 | 捕获—消旋状态机、角速度衰减图 |
| `fujii2024gripping` | B | 定调+对标 | 本地 PDF（手工补充） | 合作/非合作目标的夹爪、包络、柔性抓取方案比较。 | 末端执行器方案权衡矩阵 |

V2 应同时包含两类场景，不能只做“机械臂碰到目标”：

- **空间碎片清除抓取**：非合作、初始自旋、几何/质量属性不确定，输出抓取可达性、接触冲量、捕获稳定性与消旋时间。
- **在轨搭建抓取**：接口几何已知、低相对速度、允许姿态预对准，输出插接误差、接触力、装配成功条件和结构振动。

## 6. V3 —— 柔性臂、ANCF 与超材料

| 条目 | 等级 | 读法 | 归档状态 | 读什么 / 为什么 | 对应输出或图 |
|---|---:|---|---|---|---|
| `gerstmayr2013ancfreview` | A | 定调+推导 | 付费/策略待办 | ANCF 单元族、锁死、应变和与浮动坐标法的取舍。 | 刚柔耦合建模方法选型树 |
| `gerstmayr2008elasticline` | A | 推导 | 本地 PDF（手工补充） | ANCF 梁弯曲/轴向表示；用于避免把数值锁死误判为高刚度。 | 梁单元收敛、锁死与模态验证图 |
| `gerstmayr2023exudyn` | A | 推导+对标 | 本地 PDF（手工补充） | EXUDYN 的柔性多体实现、积分器和验证题。 | 自研模型—EXUDYN 交叉验证图 |
| `tayebi2025vibrationeditorial` | B | 定调 | 本地 PDF | 空间机械臂振动控制、执行器、算法和材料的近期研究邻域。 | V3 文献地图与缺口图 |
| `ma2025latticemeta` | B | 定调 | 本地 PDF（PMC） | 点阵材料的轻量化、带隙与减振机理。它是**跨领域迁移证据**，不是航天机械臂或 ANCF 的系统验证。 | 材料机制候选图，必须标“待空间环境/结构验证” |

V3 的最小可信仿真应先于超材料宣传：

1. 刚性臂与 ANCF 柔性臂使用同一航天器、关节轨迹和载荷。
2. 两级初始误差 × AC0/AC1/AC2 六工况，输出末端误差、基座姿态、梁端挠度、应变能、主模态频率和能量残差。
3. ANCF 单元做网格/步长收敛，至少与 EXUDYN 或解析悬臂梁题交叉验证。
4. 点阵/超材料只在等效密度、刚度、阻尼或频散参数有来源时进入；否则使用 `_WITH_PROVISIONAL_PARAMS`。

## 7. V4 —— 空间具身智能、VLA、感知与技能层

| 条目 | 等级 | 读法 | 归档状态 | 读什么 / 为什么 | 对应输出或图 |
|---|---:|---|---|---|---|
| `spacemind2026` | A | 对标 | 本地 PDF | 模块化 VLM 智能体、工具/技能调度和自演化；最接近“空间具身智能”命题。 | 智能体—技能—动力学工具链对比图 |
| `kawaharazuka2025vlareview` | A | 定调 | 本地 PDF（arXiv 预印本） | VLA 架构、数据、动作表达、实时性与真实部署约束；正式版页码需另核。 | VLA 技术栈与选型定位图 |
| `ma2024vlasurvey` | A | 定调 | 本地 PDF | VLA 分类、训练范式和评测体系。 | VLA 分类树 |
| `kim2024openvla` | A | 推导+对标 | 本地 PDF | 动作 token、LoRA/OFT 和公开训练实现。 | 模态输入—动作输出—微调流程图 |
| `rodriguez2024lmspacecraft` | B | 对标 | 本地 PDF | 高层语言模型航天操作决策；不能替代状态估计、安全门和低层控制。 | 任务决策/控制分层图 |
| `park2021speedplus` | A | 对标 | 本地 PDF | 空间目标位姿估计和 sim-to-real 域间隙标准基准。 | 合成域—HIL 域位姿误差图 |
| `orsula2025srb` | A | 推导+对标 | 本地 PDF | Isaac Sim/Isaac Lab 的空间机器人学习环境和 RL 基线。 | 任务集与算法基线图 |
| `visualservoing2024survey` | B | 定调+推导 | 本地 PDF | 把视觉位姿/图像误差接到机械臂闭环控制。 | 感知—视觉伺服—动力学闭环图 |

### SpaceMind 与 VLA 的边界

SpaceMind 当前公开工作是模块化具身视觉语言**智能体**：核心是感知、推理、技能和工具调度。OpenVLA/π0 一类 VLA 的核心是从视觉/语言观测生成机器人动作。二者可以组成分层系统，但不能互相冒充：

- 上层智能体可以解释任务、选策略和组织证据。
- VLA 可以生成候选动作或短时策略。
- SAFE-00/约束检查必须把 UNKNOWN 保留为 UNKNOWN。
- GJM/RNS、阻抗、航天器姿态与资源控制必须承担可验证的低层闭环。

因此，当前资料只支持“构建并评估空间具身智能机械臂方法”，不支持“已完成无标记泛化”或“语言模型可直接安全控制航天器”的声明。

## 8. 在轨组装专线

| 条目 | 等级 | 读法 | 归档状态 | 读什么 / 为什么 | 对应输出或图 |
|---|---:|---|---|---|---|
| `li2022assemblysurvey` | A | 定调 | 本地 PDF（SciOpen） | 装配序列、运动规划、振动抑制、柔顺装配和地面验证全景。 | 在轨装配技术链总览图 |
| `hu2025ultralarge` | A | 定调+推导 | 本地 PDF（期刊官网） | 多柔体动力学、规划控制和地面模拟；连接 V3 柔性与装配任务。 | 大尺度结构组装与地面验证路线图 |

这里的文献用于设计场景和接口证明，不能据此声称项目已完成自主在轨装配。比赛主链也不能依赖 Assembly Wave A 通过。

## 9. 平台与整器动力学

| 条目 | 等级 | 读法 | 归档状态 | 读什么 / 为什么 | 对应输出或图 |
|---|---:|---|---|---|---|
| `kenneally2020basilisk` | A | 推导+对标 | 本地 PDF（手工补充） | 轨道、姿态、结构挠性、执行机构与 GNC 的模块化平台。 | 星平台—机械臂—姿态控制耦合图 |
| `alali2024hiltestbed` | B | 对标 | 本地 PDF | 主动重力补偿、双工业臂、力/触觉传感的六自由度地面 HIL。 | 地面验证台组成与证据层级图 |

平台研究的必要输出不是只有机械臂末端轨迹，还包括航天器四元数/角速度、反作用轮动量、推进剂或能量预算、关节力矩、角动量残差及任务授权状态。

## 10. 中文报告直引

| 条目 | 等级 | 读法 | 归档状态 | 读什么 / 为什么 | 对应输出或图 |
|---|---:|---|---|---|---|
| `ding2025spacerobotops` | A | 定调 | 本地 PDF（期刊官网） | 空间机器人操作技术现状、难点与发展方向。 | 国内外操作技术谱系图 |
| `liu2021spacemanipulator` | A | 定调 | 本地 PDF（期刊官网） | 空间机械臂构型、驱动、控制与任务脉络；正文以 RichHTML 与页图交叉核验。 | 空间机械臂关键技术分解图 |
| `sscae2024strategy` | A | 定调+对标 | 本地 PDF | 中国工程语境下的自主维护路线与能力边界。 | 自主维护能力路线图 |

## 11. 开源项目：只克隆、未安装、未编译、未运行

| 等级 | 仓库 | 本地路径 | 锁定提交 | 在本项目中的职责 |
|---:|---|---|---|---|
| A | SPART | `80_third_party/vendor/SPART` | `1365c7e6f345255a700936511b8abfd58d179016` | GJM/GIM/CIM 与 URDF 导入，交叉验证自由漂浮刚体动力学 |
| A | SpaceDyn | `80_third_party/vendor/SpaceDyn` | `57e5d608cb959338b1bcec6bc34249d959815036` | Yoshida 学派 GJM/RNS 参考实现与裁决基线 |
| A | SpaceRobotEnv | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv` | `155989c2ae94a3afeedf9b8601b6125d83b9c097` | 复用已有 MuJoCo 自由漂浮双臂捕获环境 |
| A | space_robotics_bench | `80_third_party/vendor/space_robotics_bench` | `7528ff81f1ac0b34ba259b1ae150fdb4f6a90b5e` | Isaac Sim/Isaac Lab 空间机器人学习基准 |
| A | EXUDYN | `80_third_party/vendor/EXUDYN` | `b428cda78ef745e2092e7d202e72d84881bf4667` | ANCF 柔性多体和 V3 交叉验证 |
| A | basilisk | `80_third_party/vendor/basilisk` | `6b9c222fc9ea8d4b478c26435b16ff71910e80e8` | 轨道、姿态、挠性与 GNC 整器仿真 |
| B | astrobee | `80_third_party/vendor/astrobee` | `bf43a42d5f89bf0679e51ab25e7a9b7800313e9c` | 自由飞行器感知、导航、栖靠工程范例 |
| B | chrono | `80_third_party/vendor/chrono` | `24c78cf889de1105be3742cec9586f662cc52b05` | 需要 V2×V3 接触—ANCF 联合验证时使用 |
| B | openvla | `80_third_party/vendor/openvla` | `c8f03f48af692657d3060c19588038c7220e9af9` | 动作表达与 LoRA/OFT 配方参考 |
| B | openpi | `80_third_party/vendor/openpi` | `15a9616a00943ada6c20a0f158e3adb39df2ccac` | π0/π0-FAST 训练/推理管线参考 |

第三方仓库不是本项目验证结果。锁定 SHA 只保证本次查阅对象可识别，不代表依赖可用、代码已运行或结果已复现。

## 12. 数据集：只登记，不下载

| 等级 | 数据集 | 官方地址 | 用途 | 状态 |
|---:|---|---|---|---|
| A | SPEED+ | <https://purl.stanford.edu/wv398fc4383> | 位姿估计域间隙与 HIL 图像对标 | `NOT_DOWNLOADED_BY_POLICY` |
| A | SPEED | <https://purl.stanford.edu/dz692fn7184> | SPEED+ 前代与 SPEC2019 对照 | `NOT_DOWNLOADED_BY_POLICY` |

## 13. 当前 DOI 与下载阻塞

> ⚠ 本节为 **LIT-01 轮历史快照（2026-07-21）**，数字未随 REORG-01-R 更新。
> 现行口径：44 份在盘 PDF、45 题录、仅缺 `gerstmayr2013ancfreview`，裁决
> `REORG01R_COMPLETE`——以 `manifest.yaml` 与 `reorg01r_report.md` 为准。

- 24 条 DOI 已核验，其中 `yoshida2001zrm` 与 `xu2017reactiontorque` 为 `VERIFIED_AFTER_ADJUDICATION`；`MISMATCH` 已归零。
- 3 条 `CROSSREF_NOT_FOUND`：`hu2025ultralarge`、`ding2025spacerobotops`、`liu2021spacemanipulator`；均已从期刊官网核验元数据。
- 白名单扩展后新增 8 份，当前在盘 23 份；`FAILED_AFTER_RETRY` 与 `POLICY_SKIPPED_NOT_ON_DOWNLOAD_ALLOWLIST` 已归零。
- 当前 11 条进入 [paywalled_todo.md](./paywalled_todo.md)，其中编目 P0 为 5 条。
- G-LIT-COV：`gjm_rns` 66.7%，`contact_capture` 0.0%，`flexible_ancf` 33.3%；后二者触发类别覆盖阻塞。
- 详细下载来源、文件哈希与逐条状态见 [download_report.md](./download_report.md)。

## 14. 已有内容与去重

- `SpaceRobotEnv` 在本任务前已存在，直接复用并锁定 SHA，没有二次克隆。
- Basilisk、SPART、SpaceDyn、Space Robotics Bench 等名称已在开放平台目录文档中出现，但此前没有形成可复现的本地源码归档。
- SpaceMind、Papadopoulos 等已在文献审计/扫描表中作为文本条目出现；LIT-01 在 LIT-00 单一真值源上增量补齐可读化。
- 盘点时没有发现这 34 条种子对应的目标 PDF，因此“跳过已有 PDF”为 0。

## 15. 精确声明边界

本归档不证明、也不得被引用为以下结论：

- 已完成自主在轨组装；
- 已实现实时数字孪生；
- 已完成自由漂浮硬件验证；
- 已证明无标记 VLA 泛化；
- 已达到飞行级安全；
- 已完成柔性装配最终认证；
- 超材料已在空间机械臂工况中验证；
- 某个开源仓库已成功集成、编译或复现实验。

任何参数缺失的柔性梁、点阵材料、接触或航天器模型必须显式使用 `_WITH_PROVISIONAL_PARAMS`。`UNKNOWN` 不得提升为 `SUCCESS` 或 `EXECUTE`。
