---
title: B2 在轨服务/抓捕航天器设计基准（Servicing & Capture Spacecraft Benchmark）
generated_at: 2026-08-27
author_agent: WEB-SERVICER（C 轨·F4R1 机械完善研究代理）
scope: 12U 自由漂浮服务星 + B601 六自由度机械臂项目的在轨服务/抓捕任务设计基准调研；C 轨研究阶段文档，不改动任何既有资产
---

# B2 在轨服务/抓捕航天器设计基准

## 0. 证据口径

- 本文一切外部事实均标注来源 URL，访问日期统一为 **2026-08-27**。
- 标记规则：**【事实】**=来源明确给出；**【估计】**=由来源信息推断或平台惯例外推；**【UNKNOWN】**=所查公开来源未披露，禁止编造。
- 仓内引用给路径；关键仓内文件给 sha256 前 12 位（见附录 A）。
- 本项目内部锚点（用于对比，不改写）：系统总质量 31.022864807342987 kg（Unified R2 URDF，19 link/18 joint）；B601 臂 4.6956 kg，基座冻结于 x=208.0 mm 前端面，经 M3R 两级接口 + 160×160×10.75 mm Load Bridge 传力；双翼帆板各 227×200×6 mm、0.348 kg（SSOT 占位，真实面密度 2–5 kg/m²）；夹爪双指行程 0–71.5 mm；任务对象 = 150 kg 翻滚碎片 / 22 kg 目标星。来源：`AGENTS.md`（sha256:3d2269562678）、`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml`（sha256:0f9897ef4e41）。

## 1. 任务基准总表

| 任务/项目 | 机构/国家 | 质量级【事实】 | 抓捕机构类型与安装位置 | 帆板配置 | 翻滚目标处置思路 | 项目状态（截至 2026-08-27） |
|---|---|---|---|---|---|---|
| ELSA-d | Astroscale（日/英） | 服务星 175 kg / 客户星 17 kg | 磁吸对接机构（冗余），服务星前端；客户星预装 Docking Plate（铁磁+光学标记盘，支架抬高） | 体装太阳能电池；展开翼细节 UNKNOWN | 目标为合作稳定星；未受控翻滚抓捕演示因推力器异常中止 | 2021-03-22 发射；2021-08-25 首次释放-重捕；2022-01 异常后 8 台推力器 4 台失效，抓捕演示未完成；2024-01 离轨操作结束任务 |
| ELSA-M | Astroscale（英） | 服务星 520 kg | 磁吸对接（针对预装对接板的"prepared"卫星，目标 OneWeb @1200 km） | UNKNOWN | 目标为可三轴稳定的失效星；非翻滚抓捕 | 2025-06 完成 CDR；2026-03 选定 Isar Aerospace Spectrum 发射，计划 2026 年发射 |
| MEV-1 / MEV-2 | Northrop Grumman SpaceLogistics（美） | MEV-1 ≈2330 kg（另一来源 2326 kg）/ MEV-2 2875 kg | 机械对接探针插入客户星液体远地点发动机（LAE）喷管 + 顶杆（stanchions）抵住星箭对接环；对接面位于星体前部中心线；兼容约 80% GEO 卫星 | 展开式太阳翼，10 kW（"arrays"复数表述；GEOStar-3 平台惯例为双翼【估计】） | 客户为在轨三轴稳定通信星（IS-901 主动升轨配合）；非翻滚抓捕 | MEV-1：2019-10-09 发射，2020-02-25 与 IS-901 对接（首次商业 GEO 对接），2025-04-09 完成延寿并分离；MEV-2：2020-08-15 发射，2021-04-12 与 IS-10-02 对接，在役 |
| Orbital Express（ASTRO+NextSat） | DARPA/Boeing/Ball（美） | 组合体 ≈1400 kg；ASTRO 干重 ≈900 kg（含 135 kg 肼）/ NextSat 湿重 ≈224 kg | 双通道：(1) MDA 6 自由度臂（71 kg、展长 3.3 m、131 W）抓 NextSat grapple fixture 后 berth；(2) OECS 三爪对接机构（主动/被动两半，滚珠丝杠驱动四连杆，锥杯对准+电机预紧刚化）；均装于 ASTRO 前端对接面 | ASTRO 单翼，展长 5.6 m、1.56 kW；NextSat 太阳阵 >550 W(EOL)、三结电池 27.5% | 合作目标（姿态受控）；演示自主逼近-抓捕-对接-分离全流程 | 2007-03-09 发射（Atlas V，STP-1/ESPA 首飞）；2007-04 起完成燃料（14.6 kg 肼）与 ORU 电池转移、自主自由飞行抓捕；2007-07 退役，任务成功 |
| e.Deorbit | ESA（OHB/Airbus DS/MDA/DLR 参研） | chaser ≈1600 kg 级（仿真取 1380 kg）/ 目标 Envisat ≈8000 kg | 7 自由度冗余臂（展长 4.3 m，谐波关节 ±80 Nm 名义/176 Nm 峰值，限速 10°/s）+ 直线双 bracket 夹爪抓 LAR（ACU 2624）；随后 MDA clamping 机构（顶甲板，弧长 300 mm、预紧 10 kN、包络 ±21 mm/±2°）+ 120° 俯仰对准机构使推力矢量过组合体 CoG | 所查来源未明确（UNKNOWN） | 完整翻滚处置链：V-bar 100→30 m→绕飞至角动量轴→沿轴逼近→旋转同步（臂收拢锁定）→约 4 m 臂交付点→抓捕→GNC 关断、臂阻抗阻尼残余→推力器消旋→重定位→clamp 刚化→离轨 | Phase B1 方案研究（2018 前后）；未转入飞行项目，ADR 任务线由 ADRIOS/ClearSpace-1 承接 |
| DEOS | DLR（德） | UNKNOWN（Phase A 公开资料未披露质量） | 服务星搭载机械臂 berth 非合作翻滚客户星；另有专用对接机构做合作对接；刚性臂接触属"冲击能耗散"类 | UNKNOWN | 目标即"非合作+翻滚"：演示逼近、绕飞、berthing、组合体服务与受控离轨；绝对/相对两级导航 | 2012-09 授出定义阶段合同（Astrium，约 1300 万欧元级【事实：金额以 SpaceRef 报道为准】）；定义阶段后取消；技术遗产转入 e.Deorbit 与 EPOS 设施 |
| RemoveDEBRIS | Surrey/SSTL/Airbus 等（英/欧） | 母船 ≈100 kg（SSTL X50/SSTL-42 平台）；目标为 2U CubeSat×2 | 非刚性接触两路线：网捕（RemDeb Net 捕获带充气八面体张拉结构的 DS-1，2018-09-16 成功）；鱼叉打靶（HTA 伸杆靶，2019 成功）；另演示 VBN 与拖帆 | 平台太阳能电池供电；翼构型 UNKNOWN | 目标为释放的立方星（非大翻滚刚体堆）；系留式捕获避免刚性冲击，无组合体消旋问题 | 2018-04-02 随 CRS-14 上天，2018-06-20 自 ISS 部署；2018–2019 完成全部关键演示；任务结束再入 |
| ClearSpace-1 | ESA / ClearSpace SA（瑞士） | 服务星 580 kg 湿重（含余量）；早期对外口径 <400 kg；目标 VESPA 上半 ≈100–112 kg | 四根铰接臂"抱合"（hug）捕获，机构装于服务星前端捕获容积四周 | 展开式太阳翼（ESA 展示图，复数"Solar Arrays"；翼数/刚度 UNKNOWN） | 非合作目标：服务星与目标"同步运动"下安全抱合，随后组合体受控再入 | 2020-12 签 ESA 服务合同（媒体报 €86M）；发射计划由 2025 滑至 2026 下半年（Vega C，Arianespace 合同）；截至 2026-08-27 未发射；另有 ESA 会议论文提及 end-2028 口径，进度不确定 |
| Starfish Otter | Starfish Space（美） | ≈200 kg，ESPA 级 | Nautilus 通用对接机构：静电附着，可粘附未做对接准备的表面，可重复使用，并提供服务星-客户星间动态阻尼 | UNKNOWN | 目标客户为受控卫星；Nautilus 阻尼特性用于对接后组合体动力学管理；未主张翻滚抓捕 | 在研。Otter Pup 2 于 2025-06 发射，计划在 D-Orbit ION 上测试 Nautilus 静电附着；获美太空军合同（2026 演示 $37.5M；2028 交付 APFIT $54.5M，媒体口径）；2026-04 完成 >$100M B 轮融资 |
| DARPA RSGS / MRV | DARPA + Northrop Grumman（SpaceLogistics）/NRL（美） | MRV 4400 kg | NRL 双臂：2×3 m、各 7 自由度，可换工具，20+ 态势感知相机；装于 MEV 平台继承的 MRV 前部载荷舱 | UNKNOWN（MEV 血统大翼【估计】） | 客户为 GEO 受控卫星：检查、加注/维修、安装 Mission Extension Pod；非翻滚抓捕 | **2026-07-21 由 Falcon 9（一次性构型）自卡角发射成功**，正电力升轨赴 GEO（约一年巡航），服务操作预计 2027 开始；首批客户 Optus（1 个 MEP）、Intelsat（2 个 MEP） |
| CPOD（补充·微纳级） | NASA / Tyvak（美） | 2×3U CubeSat，各 ≈5 kg | 计划星间对接机构 + RPOD 敏感器套件 + 多推力器推进 + 星间链路 | 体装（3U 惯例【估计】） | 双方受控；目标是 3U 级自主 RPO→对接演示 | 2022-05（Transporter-5）发射；完成多次 RPO；2023-06 因推进剂耗尽、未能完成对接即任务结束 |
| ADRAS-J（补充·微纳级） | Astroscale / JAXA（日） | ≈150 kg | 无抓捕机构（抵近检查星）；为后续 CRD2 抓捕相位做目标表征 | UNKNOWN | **翻滚非合作目标逼近的现役标杆**：对 H-IIA 末级（11 m×4 m、≈3 t、翻滚）RPO 逼近至 15 m；首次绕飞（2024-07）触发 FDIR 自动中止后安全恢复并完成全部观测 | 2024-02-18（Rocket Lab Electron）发射；观测任务完成；后续 CRD2 Phase II 规划实施抓捕离轨 |

> 帆板列说明：凡标 UNKNOWN 者为所查公开来源（Gunter's Space Page、eoPortal、NASA ISAM State of Play、ESA/机构官网与论文）未给出体装/翼式、刚性/柔性的明确规格；不写推测值。

## 2. 分任务详录

### 2.1 ELSA-d / ELSA-M（Astroscale，磁吸对接板）

**ELSA-d【事实】**
- 质量：服务星 175 kg、客户星 17 kg（SpaceNews 2021；NASA SOA 2024 同口径）。
- 抓捕机构：冗余磁吸捕获机构，服务星前端；客户星预装 Docking Plate（铁磁、带光学标记的圆盘，支架抬高安装），同时为服务星导航敏感器提供光学参考。磁吸对接=典型的"prepared/cooperative interface"路线。
- 帆板：Gunter 参数表仅"Solar cells, batteries"；展开翼规格 UNKNOWN。
- 内部布局/服务化特征：服务星载光学敏感仪器 + 冗余捕获机构；客户星载 Docking Plate 与 Space Debris Monitor；更细的内部布局未公开（UNKNOWN）。
- 翻滚处置：客户星全程姿态受控；原计划含"客户星不受控"高难演示，因 2022-01-25 异常（8 台推力器中 4 台失效）未再尝试抓捕，团队明示"为任务安全决定不再进行抓捕"。
- 状态：2021-03-22 Soyuz 发射；2021-08-25 首次释放并磁吸重捕；2022-05 完成复杂交会操作（绝对导航 1700 km→160 m 级）；2024-01-24 完成离轨操作、任务结论。
- 来源：[SpaceNews 2021-03（175/17 kg 与磁吸机构）](https://spacenews.com/as-astroscale-prepares-to-launch-landmark-debris-removal-mission-uk-eyes-in-orbit-servicing-leadership/)；[Gunter's Space Page: ELSA-d Servicer](https://space.skyrocket.de/doc_sdat/elsa-d-chaser.htm)；[SatNews 2022-04-07（4/8 推力器失效）](https://news.satnews.com/2022/04/07/astroscale-reports-on-their-elsa-d-satellite-servicer-anomalies-during-the-in-space-test-capture/)；[Astroscale 2024-01-24（任务结论与安全决策原文）](https://www.astroscale.com/en/news/astroscales-elsa-d-finalizes-de-orbit-operations-marking-successful-mission-conclusion)；[NASA SOA 2024（Deorbit 章）](https://ntrs.nasa.gov/api/citations/20250000142/downloads/SOA_2024_final.pdf?attachment=true)。

**ELSA-M【事实】**
- 质量：服务星 520 kg（Astroscale/APSCC 发射服务公告）；另有二手博客写 600 kg，以官方 520 kg 为准。
- 抓捕：磁吸对接板路线，目标是"prepared"卫星（Eutelsat OneWeb，1200 km 轨道），多客户 EOL 服务。
- 帆板/内部布局：UNKNOWN（CDR 级公开材料未含）。
- 状态：ESA+UKSA 资助约 €13.95M（$15M，2024-07 签约）；2025-06 完成 CDR；2026-03-16 选定 Isar Aerospace Spectrum，计划 2026 年发射。
- 来源：[Astroscale 2026-03-16 发射服务公告（520 kg）](https://www.astroscale.com/en/news/astroscale-selects-isar-aerospace-to-launch-elsa-m-in-orbit-demonstration-mission)；[APSCC 同文](https://apscc.or.kr/astroscale-selects-isar-aerospace-to-launch-elsa-m-in-orbit-demonstration-mission/)；[SpaceWatch.Global 2025-06-04（CDR）](https://spacewatch.global/2025/06/astroscales-elsa-m-spacecraft-completes-critical-design-review-to-launch-in-2026/)；[Via Satellite 2024-07-22（$15M 合同）](https://www.satellitetoday.com/technology/2024/07/22/astroscale-secures-new-funding-for-elsa-m-mission/)；[Astroscale ELSA-M 任务页](https://www.astroscale.com/en/missions/elsa-m)。

### 2.2 MEV-1 / MEV-2（Northrop Grumman，插探针式）

- 质量：MEV-1 ≈2330 kg（eoPortal；中文电推进综述给 2326 kg，两口径并存）、MEV-2 2875 kg；GEOStar-3 平台改型。
- 抓捕机构：简单机械对接系统——探针插入客户星 LAE 喷管（"probe-in-the-kick-motor"）+ 顶杆抵住星箭对接环；对接面位于星体前部中心线；官方口径兼容约 80% 在轨 GEO 卫星；可多次对接/分离（15 年设计寿命）。
- 帆板：10 kW 太阳阵（eoPortal 用复数"arrays"；GEOStar-3 惯例双翼展开【估计】）；290 Ah 锂电。
- 内部布局/服务化特征：全 6 自由度控制；冗余 RPOD 敏感器；混合推进=肼单组元 + 电推进（中文综述：4×5 kW 级 XR-5 Hall 推力器主推进/位保，化学推力器执行交会对接）；电推进推力矢量控制用于位保与动量管理；高精度星敏 + 动量轮姿控；双发射堆叠构型。
- 翻滚处置：不面向翻滚目标；IS-901 主动升轨配合交会。
- 状态：MEV-1 2019-10-09 Proton-M 发射，2020-02-25 对接 IS-901（人类首次商业 GEO 星间对接），2025-04-09 将 IS-901 送入墓地轨道后分离，转向 Optus D3；MEV-2 2020-08-15 Ariane 5 发射，2021-04-12 对接 IS-10-02，在役。
- 来源：[eoPortal: MEV-1 & 2（平台/质量/帆板/姿控/对接）](https://www.eoportal.org/satellite-missions/mev-1)；[Wikipedia: Mission Extension Vehicle（任务年表）](https://en.wikipedia.org/wiki/Mission_Extension_Vehicle)；[中文综述（2326/2875 kg、XR-5×4）](https://www.yunzhan365.com/basic/45250947.html)；[SpaceNews 2020-02-26（对接）](https://spacenews.com/northrop-grummans-mev-1-servicer-docks-with-intelsat-satellite/)。

### 2.3 Orbital Express（ASTRO + NextSat，2007 演示）

- 质量：组合体 ≈1400 kg、高约 2.5 m；ASTRO 干重 ≈900 kg、135 kg 肼；NextSat 湿重 ≈224 kg、星体长 99 cm。
- 抓捕机构（双通道，均装 ASTRO 前端对接面）：(1) MDA 6 自由度臂（71 kg、展长 3.3 m、功耗 131 W）抓 NextSat grapple fixture→berth，再由捕获机构完成最终对接；(2) OECS（Orbital Express Capture System，SpaceDev/Starsys）三爪对接机构：滚珠丝杠驱动三组四连杆收拢被动端，楔形导向→三点锥杯粗对准→电连接器容差对准→末段锥杯全约束+电机预紧刚化。
- 帆板：ASTRO 单翼、展长 5.6 m、功率 1.56 kW；NextSat 太阳阵 >550 W(EOL)、三结电池效率 27.5%。
- 内部布局/服务化特征：NextSat 为模块化可服务设计（ORU 电池、飞控计算机舱），演示 14.6 kg 肼转移（2007-04-01）与电池/飞控机更换；ARCSS 敏感器套件=2 可见光相机+红外相机+激光测距+AVGS（NASA/MSFC，后向反射靶双波长激光成像）；自主等级用 ATP（Approval-To-Proceed）逐级地面批准管理。
- 翻滚处置：合作受控目标；任务经历两次濒败故障（姿控符号错误致组合体偏离对日、飞控计算机间歇重启）均恢复——早期 fail-safe 实战案例。
- 状态：2007-03-09 Atlas V（STP-1，ESPA 首飞）；2007-05 完成自主自由飞行交会抓捕；2007-07-21/22 退役，任务判定成功。
- 来源：[eoPortal: STP-1/Orbital Express（质量/帆板/机构/ARCSS/ATP）](https://www.eoportal.org/satellite-missions/stp-1)；[Dubanchet 博士论文（ASTRO 1.1 t 级、NextSat 0.2 t、臂 71 kg/3.3 m/131 W）](https://publications.polymtl.ca/2362/1/2016_VincentDubanchet.pdf)；[SpaceNews 2007-04-17（首次自主燃料/部件转移）](https://spacenews.com/boeing-orbital-express-conducts-first-autonomous-spacecraft-to-spacecraft-fluid-and-component-transfer/)；[SpaceNews 2007-07（退役）](https://spacenews.com/after-successful-mission-orbital-express-put-out-pasture/)；[NTRS《Grappling Spacecraft》（两次濒败故障记述）](https://ntrs.nasa.gov/api/citations/20210020506/downloads/Grappling_Spacecraft%20Paper%20Final.pdf)。

### 2.4 e.Deorbit（ESA 方案研究）

- 质量：chaser ≈1600 kg 级（Corso 硕士论文"at around 1600 kg"；Jaekel 2018 仿真取 chaser 1380 kg）；目标 Envisat ≈8 t，惯量矩阵已公开于论文；当前翻滚约 3°/s，设计包线按任意轴 5°/s。
- 抓捕机构与安装：7 自由度冗余臂（展长 4.3 m；DH 参数公开；关节谐波传动，名义 ±80 Nm、峰值 176 Nm，限速 10°/s；除结构外驱动链单故障容错；发射段 Frangi-bolt 锁定收拢）+ OHB 直线双 bracket 夹爪抓 Envisat 星箭对接环 LAR（ACU 2624；初始容差 20 mm 横向/5°）；抓捕后由 MDA clamping 机构（chaser 顶甲板）刚化：弧长 300 mm、预紧 10 kN、捕获包络 ±21 mm/±2°，底部 120° 俯仰对准机构使 chaser 主推力矢量穿过组合体 CoG。布局（OHB 概念）：LAE 置于星箭对接环内（尾部），臂+clamp 载荷在星体另一侧（前部），剪力板结构，4 贮箱在下半舱。
- 抓取点选择逻辑【事实，对本项目直接相关】：候选 LAR、帆板发射锁、整星大抱合；大抱合因"抓点不确定 + Envisat 结构承载未知"被否决；LAR 因"rigid, strong, geometry well known"且对多数卫星通用而当选。
- 帆板：chaser 帆板规格 UNKNOWN；Envisat 大帆板位置不确定是逼近侧选择的驱动因素（选 +z 顶逼近以降低风险）。
- 翻滚处置（完整链，本项目最直接可比对象）：V-bar 100→30 m→球面绕飞至目标角动量矢量→沿矢量逼近→旋转同步（臂保持收拢）→距目标 CoM/最大惯量主轴约 4 m 的臂交付点→地面预规划+星上存储的臂轨迹→臂端立体相机视觉伺服闭环补偿 GNC 不确定盒→夹爪形/力闭合→**GNC 关断，臂力敏阻抗控制主动阻尼两星残余相对运动**→chaser 推力器消旋组合体→臂将 chaser 重定位到 LAR→clamp 刚化→离轨点火。臂杆柔性分析：berthing 机动 60 s 时最大弹性位移 3.6 mm、残余振动 0.2 mm@0.31 Hz；机动时间加倍到 120 s 则降到 0.9 mm。最坏工况（5°/s 绕不稳定中间轴 + 30 cm 定位误差）关节力矩达 195 Nm、触及峰值极限；4°/s 与 3.5°/s 时最大 85–110 Nm。视觉跟踪最差位姿误差 ±2.5 cm，直接决定 gripper/clamp 包络设计。
- 状态：Phase B1（OHB 与 Airbus DS 两条平行研究线，2018 前后）；未转入飞行项目，ESA ADR 线由 ADRIOS/ClearSpace-1 承接。
- 来源：[Jaekel et al. 2018, Frontiers in Robotics and AI（臂/夹爪/clamp/同步策略/柔性/关节载荷/视觉）](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2018.00100/full)（[PMC 镜像](https://pmc.ncbi.nlm.nih.gov/articles/PMC7805711/)）；[ESA SDC7 论文（任务与捕获技术选型）](https://conference.sdo.esoc.esa.int/proceedings/sdc7/paper/1053/SDC7-paper1053.pdf)；[Wieser et al.（OHB 布局：LAE/臂位置/贮箱）](https://elib.dlr.de/100732/1/96014_Wieser.pdf)；[Corso 硕士论文（1600 kg 口径、同步段分解）](https://elib.dlr.de/109429/1/CORSO_Mario_Master_Thesis_elib.pdf)；[Henry et al. 2019（同步/抓捕/刚化/稳定相位分解）](https://recil.ulusofona.pt/bitstream/10437/9796/1/Henry%20et%20al.%20-%202019%20-%20Model-based%20fault%20diagnosis%20and%20tolerant%20control%20.pdf)。

### 2.5 DEOS（DLR 方案）

- 质量：UNKNOWN（Phase A 公开数据表未含质量；定义阶段细节未见公开）。
- 任务参数【事实】：Servicer+Client 同箭发射，初始 600 km 圆轨道（任务后期降至 400 km），倾角 85°–90°（参考 87°），Dnepr/Rockot 兼容，一年任务期；地面站网 Fairbanks/Inuvik/Weilheim/Kiruna/Svalbard。
- 抓捕机构：服务星搭载机械臂 berth 非合作翻滚客户星；另有专用对接机构完成合作对接；刚性臂首触属"冲击能耗散（impact energy dissipation）"类（ET-Class 分类）。
- 布局：公开图示含发射堆叠构型、port-coupled 构型（berthing+docking 后）、臂耦合构型；导航=绝对（GPS+星敏+地面注入）与相对（相机+LIDAR）两级。
- 帆板：UNKNOWN。
- 状态：2012-09 DLR 授出定义阶段合同（Astrium Friedrichshafen 牵头）；定义阶段后项目取消；机器人捕获技术遗产转入 e.deorbit 研究，EPOS 2.0 半实物设施延续。
- 来源：[Gunter's Space Page: DEOS（取消状态）](https://space.skyrocket.de/doc_sdat/deos.htm)；[SpaceTech DEOS Phase A 数据表（任务概念/轨道/导航/构型图）](https://spacetech-i.com/fileadmin/user_upload/Systems/Missions_and_Satellites/SpaceTech_DEOS_PhaseA_datasheet.pdf)；[SpaceRef 2012-09（定义阶段合同）](https://spaceref.com/space-commerce/astrium-wins-deos-contract-to-demonstrate-in-orbit-servicing-2/)；[Boge et al. 2010（任务目标原文：capture tumbling non-cooperative client + de-orbit coupled configuration）](https://elib.dlr.de/74383/1/Kopie_von_AIAA_MST_2010_paper_v10.pdf)；[MDPI EPOS 2.0 十周年（DEOS 三大目标与取消）](https://www.mdpi.com/2226-4310/8/9/235)；[Frontiers ET-Class（DEOS 归 ET2 冲击耗能类）](https://www.frontiersin.org/articles/10.3389/frspt.2022.792944/full)。

### 2.6 RemoveDEBRIS（网捕/鱼叉演示）

- 质量：母船 ≈100 kg（SSTL X50/SSTL-42 平台）；DebrisSat 1/2 为 2U CubeSat。
- 抓捕机构：非刚性接触两路线——(1) RemDeb Net 网捕：DS-1 释放后展开充气八面体张拉结构作靶，2018-09-16 网捕成功并留轨；(2) 鱼叉：打母船伸杆上的 HTA 靶板（2019-02 成功）；另演示 DS-2 视觉导航（VBN）与末期 DragSail 拖帆。
- 帆板：母船太阳能电池供电；翼构型 UNKNOWN。
- 翻滚处置：目标是低复杂度释放靶星；系留式捕获以"距离+系绳"替代刚性冲击，从机制上回避组合体消旋/冲击传递问题。
- 状态：2018-04-02 Falcon 9/CRS-14 至 ISS，2018-06-20 部署；2018–2019 完成网捕、鱼叉、VBN、拖帆全部演示；任务结束再入。
- 来源：[Gunter's Space Page: RemoveDEBRIS（平台/质量/事件日期）](https://space.skyrocket.de/doc_sdat/removedebris.htm)；[University of Surrey（任务构成与两项演示）](https://www.surrey.ac.uk/people/andrew-viquerat)；[SpaceNews（100 kg 口径与 ISS 部署链）](https://spacenews.com/launch-of-space-debris-removal-experiment-delayed-due-to-safety-reviews/)。

### 2.7 ClearSpace-1（ESA / ClearSpace，四臂抱合）

- 质量：服务星 580 kg 湿重（含 SRR 余量，ESA Clean Space Days 展示）；2020 年早期对外口径 <400 kg，以 580 kg 现行口径为准；目标 VESPA 上半 ≈100–112 kg、锥形，2013 年滞留轨道。
- 抓捕机构：四根铰接臂"抱合"（hug）捕获，机构布置于服务星前端捕获容积四周；与本项目同属于"整臂包络非合作刚体"路线，但以四臂冗余换取形状适应性。
- 帆板：展开式太阳翼（ESA 展示图题注"with Solar Arrays deployed"；翼数与刚度 UNKNOWN）。
- 内部布局/推进：化学绿色推进剂；星体 1600 mm（宽）×1300 mm（高）；24 英寸标准发射接口。
- 翻滚处置：服务星与目标"同步运动（synchronised motion）"下安全捕获，随后组合体受控再入。
- 状态：2020-12-01 签 ESA 服务合同（媒体报道金额 €86M）；发射计划 2025→2026 下半年（Vega C，Arianespace）；截至 2026-08-27 未发射；ESA sdc9 会议摘要另有"end of 2028"口径，进度存在不确定性。
- 来源：[ESA Indico: ClearSpace-1 IOD Mission（580 kg/尺寸/推进/四臂图）](https://indico.esa.int/event/516/contributions/9983/attachments/6342/10932/ClearSpace-1%20IOD%20Mission_Clean%20Space%20Days.pdf)；[ClearSpace 2020-12-01 服务合同公告（四臂表述）](https://clearspace.today/news/clearspace-sa-signs-service-contract-with-esa-to-carry-out-the-first-mission-to-remove-space-debris-in-orbit-in-2025)；[ClearSpace/Arianespace 2023-12-14（Vega C，2026 下半年）](https://clearspace.today/clearspace-to-launch-the-first-active-debris-removal-mission-with-arianespace-vega-c/)；[SpaceNews 2020-12（<400 kg 早期口径、化学推进）](https://spacenews.com/swiss-startup-clearspace-wins-esa-contract-to-deorbit-vega-rocket-debris/)；[ESA sdc9 摘要（同步运动捕获、2028 口径）](https://conference.sdo.esoc.esa.int/proceedings/sdc9/paper/317)；[商业媒体汇总（€86M、112 kg、进度史）](https://nexi.fund/space-debris-removal-commercial-2026/)。

### 2.8 Starfish Space Otter（小型电推进服务星）

- 质量：≈200 kg，ESPA 级（NASA ISAM State of Play 2022）。
- 抓捕机构：Nautilus 通用对接机构——静电附着，可对未做对接准备的多种表面粘附，可重复使用，并在服务星-客户星间提供动态阻尼（NASA ISAM 2024/2025 技术条目）。
- 推进：Otter 全电推进完成自主 RPOD 与组合体操作（公司口径"首个纯电推进对接"目标）；Otter Pup 演示星为化学+电推进混合。
- 帆板/内部布局：UNKNOWN。
- 翻滚处置：面向受控客户星的延寿/离轨服务；Nautilus 阻尼用于对接后组合体动力学管理；未主张翻滚非合作抓捕。
- 状态：Otter Pup 2 于 2025-06 发射，计划在 D-Orbit ION 上测试 Nautilus 静电附着；获美太空军 SSC 合同（媒体报道：2026 演示 $37.5M；APFIT $54.5M、2028 交付 GEO 专用 Otter）；2026-04 完成 >$100M B 轮融资。
- 来源：[NASA ISAM State of Play 2022（Otter ≈200 kg、CEPHALOPOD GNC）](https://ntrs.nasa.gov/api/citations/20220010995/downloads/isam_state_of_play_final_2022.pdf?attachment=true)；[NASA ISAM State of Play 2024（Nautilus 条目）](https://ntrs.nasa.gov/api/citations/20240012414/downloads/ISAM_State_of_Play_2024_final.pdf)；[NASA ISAM State of Play 2025（Otter Pup 2 静电附着测试计划）](https://ntrs.nasa.gov/api/citations/20250008988/downloads/NASA_ISAM_State_of_Play_2025_Edition.pdf?attachment=true)；[Starfish 2025-05-20 Otter Pup 2 公告](https://www.starfishspace.com/press-release/starfish-space-unveils-otter-pup-2-mission/)；[Starfish 2022-11-09（纯电推进对接目标）](https://www.starfishspace.com/press-release/starfish-space-otter-pup-to-dock-with-a-satellite/)；[Market.us 行业汇总（太空军合同）](https://market.us/report/on-orbit-servicing-market/)。

### 2.9 DARPA RSGS / MRV（机械臂服务）

- 质量：MRV 4400 kg（Aerospace America 2026-07-17）。
- 抓捕机构：NRL 研制的双臂系统——2×3 m、各 7 自由度、可换工具、20+ 态势感知相机（媒体汇总口径）；集成于 MEV 平台血统的 MRV 前部载荷舱。
- 帆板：UNKNOWN（MEV 血统大翼【估计】）。
- 任务内容：GEO 卫星检查、维修、安装 Mission Extension Pod（MEP）延寿；客户为受控卫星，非翻滚抓捕。
- 状态：**2026-07-21 由 SpaceX Falcon 9（一次性构型）自卡角发射成功**，现处赴 GEO 的约一年升轨巡航段，服务操作预计 2027 年开始；Optus 购首个 MEP、Intelsat 订两个。
- 来源：[NASA 2026-07-22（发射确认，DARPA 提供臂组件）](https://www.nasa.gov/technology/robotic-servicing-mission-launches-with-nasa-support/)；[Aerospace America 2026-07-17（4400 kg、7-21 发射）](https://aerospaceamerica.aiaa.org/joint-darpa-northrop-robotic-servicing-spacecraft-to-launch-in-late-july/)；[NASA 2024-09-05（NASA-DARPA 跨局协议）](https://www.nasa.gov/directorates/stmd/nasa-to-support-darpa-robotic-satellite-servicing-program/)；[Naval Technology 2024-11-15（NRL/DARPA 机器人套件完成）](https://www.naval-technology.com/news/us-nrl-darpa-robotics-suite/)；[MLQ 2026-07-23（双臂 3 m/7DOF/20+ 相机、一年赴 GEO、MEP 客户）](https://mlq.ai/news/northrops-robotic-satellite-servicer-begins-yearlong-trip-to-geosynchronous-orbit/)；[SatNews 2026-05-21（发射计划确认）](https://satnews.com/2026/05/21/from-disposable-assets-to-multi-mission-robotics-us-prepares-for-first-in-orbit-servicing-mission/)。

### 2.10 微纳级补充案例

**CPOD（CubeSat Proximity Operations Demonstration，NASA/Tyvak）**
- 2×3U CubeSat、各 ≈5 kg；验证 3U 级 RPOD：星间链路共享 GPS、多推力器推进、RPOD 敏感器、计划星间对接。2022-05（Transporter-5）发射；完成多轮交会与近旁操作；2023-06 因推进剂耗尽、未完成对接即结束任务。启示：微纳级 RPO 已飞行验证，但"对接/抓捕"在 3U 级仍未被完成——推进剂预算与多轮逼近消耗是首要死因。
- 来源：[NASA CPOD factsheet](https://www.nasa.gov/wp-content/uploads/2015/11/factsheet_cpod_19_july2018-508.pdf)；[NTRS 编队/交会综述章（2×3U ≈5 kg）](https://ntrs.nasa.gov/api/citations/20190001374/downloads/20190001374.pdf)；[TU Delft 星间跟踪综述（2022-05 发射、2023-06 推进剂耗尽结束）](https://research.tudelft.nl/files/222770804/1-s2.0-S027311772400841X-main.pdf)；[Tyvak CPOD 任务页](https://tyvak.eu/missions/cpod/)。

**ADRAS-J（Astroscale/JAXA CRD2 Phase I）**
- ≈150 kg；无抓捕机构，任务是逼近并表征真实大型碎片：H-IIA 末级（11 m×4 m、≈3 t、翻滚、无 GPS 合作信息）。2024-02-18（Rocket Lab Electron）发射；从地面观测初值出发远距离逼近→50 m 后直线逼近→15 m（商业 RPO 对真实碎片的世界最近纪录）；2024-07 首次绕飞观测尝试中 FDIR 安全中止并恢复，随后完成全部计划观测。后续 CRD2 Phase II 规划实施抓捕离轨。
- 来源：[Astroscale 2024-12-11（15 m 逼近、50 m 直线逼近段）](https://www.astroscale.com/en/news/astroscales-adras-j-achieves-historic-15-meter-approach-to-space-debris)；[Universe Space Tech（150 kg、15 m 纪录）](https://universemagazine.com/en/15-meters-satellite-makes-record-breaking-approach-to-space-debris/)；[Rocket Lab 任务页（On Closer Inspection）](https://www.rocketlabusa.com/missions/missions-launched/on-closer-inspection/)；[Rocket Lab 新闻包（目标 11 m×4 m/3 t、无 GPS 合作信息）](https://rocketlabcorp.com/assets/Uploads/F44-On-Closer-Inspection-Press-Kit-web.pdf)；[TDnet PDF（FDIR 中止与恢复、全部观测完成）](https://tdnet-pdf.kabutan.jp/20241211/140120241211536979.pdf)；[Orbital Radar（CRD2 相位划分）](https://orbitalradar.com/active-debris-removal)。

## 3. 对 12U 级自由漂浮服务星概念设计的工程启示

以下每条均给出来源；"→ 12U"为针对本项目（质量 31.02 kg、B601 前置、双翼、目标 150 kg/22 kg）的设计推论（建议性质，非既成裁决）。

1. **"抓捕机构—组合体质心—主推力器"共轴是一级布局约束。** e.Deorbit 专门设置 120° 俯仰对准机构使 chaser 主推力矢量穿过抓捕后组合体 CoG，承认目标 CoM 不准、需可调（[Jaekel 2018 §4.4](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2018.00100/full)）；MEV 探针+顶杆使对接面居于星体中心线（[eoPortal](https://www.eoportal.org/satellite-missions/mev-1)）。→ 12U：B601 基座冻结于前端面 x=208 mm 居中（`02_PRODUCT_STRUCTURE.yaml`，sha256:0f9897ef4e41）与该惯例一致；内部配置完善时轨控推力器应布置在尾端面中心附近，并按"抓捕 150 kg 后组合体 CoG 明显外移"校核推力线偏差，预留安装角/矢量调节余量。

2. **臂基座相对质心的位置由"抓捕后关节内力矩"反推，而非由可用空间正推。** e.Deorbit 关节力矩 τ_g 随 chaser CoM 位置非线性增长，顶逼近方案因 CoM 到抓取点距离更短而降低内力矩；5°/s 最坏工况+30 cm 误差触及 176 Nm 峰值（[Jaekel 2018 §3/§5.3](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2018.00100/full)）。Orbital Express 臂紧邻前端对接环安装（[eoPortal](https://www.eoportal.org/satellite-missions/stp-1)）。→ 12U：臂前置使星体 CoM 与臂根距离约 0.2 m，但 150 kg 目标接入后组合体 CoG 向目标侧大幅外移，臂根 M3R 接口应按"组合体 CoG 口径"重算表观力臂载荷，而非只按星体 CoM 口径。

3. **大柔性附件在逼近/抓捕段的工程处置 = 收拢锁定 + 把附件不确定度作为逼近侧选择约束。** e.Deorbit 同步段臂以 Frangi-bolt 锁定收拢；Envisat 大帆板位置不确定直接驱动"+z 顶逼近"的选择（[Jaekel 2018 §3/§4.1](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2018.00100/full)）。→ 12U：双翼不可收拢时，应定义"翼根铰链锁定/卸载"的抓捕构型，把铰链 freeplay 列为抓捕瞬间载荷路径不确定源；本项目帆板质量 0.348 kg 为 SSOT 占位（真实 2–5 kg/m²，`AGENTS.md` sha256:3d2269562678 已标"结论可能翻转"），翼参数真实化后本条优先级最高。

4. **降速是最便宜的柔顺抑制旋钮，且有公开定量先例。** e.Deorbit berthing 机动 60→120 s，臂杆弹性位移 3.6→0.9 mm；关节限速 10°/s（[Jaekel 2018 §5.2/§4.2](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2018.00100/full)）。→ 12U：与 sim_07"点捕获激振 vs 刚性锁定 ≈92×"同向（`AGENTS.md`）；抓捕后重定向机动的速度剖面应以帆板模态能量为约束来规划，零硬件成本。

5. **两段式连接（先抓取容忍大误差、后刚化获得刚度）是机械臂路线的标准做法。** e.Deorbit：夹爪容忍 20 mm/5°，clamp 包络 ±21 mm/±2°、弧长 300 mm、预紧 10 kN，刚度分析显示 LAR 本身是最弱环、clamp 相当于局部加强（[Jaekel 2018 §4.3–4.4](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2018.00100/full)）；Orbital Express 同样"臂 berth→OECS 刚化"（[eoPortal](https://www.eoportal.org/satellite-missions/stp-1)）。→ 12U：夹爪（行程 71.5 mm）之后是否需要二级锁紧/拉紧机构，应列为内部配置完善的正式 trade；包络差距须由视觉伺服精度补齐，且锁紧件的传力路径要回到 M3R/Load Bridge 主承力结构。

6. **执行器容量分层惯例：轮组管姿态，化学/电推力器管大角动量卸载。** MEV：动量轮姿控 + 肼推进（[eoPortal 表 1](https://www.eoportal.org/satellite-missions/mev-1)）；e.Deorbit：用 chaser 推力器对 ≈8 t 组合体消旋（[Jaekel 2018 §3](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2018.00100/full)）。公开来源普遍不披露轮组具体角动量容量（N·m·s）——此为全行业信息缺口（UNKNOWN）。→ 12U：sim_08 结论（150 kg 碎片消旋 |H_c|=3.65 N·m·s = 12× 轮组容量→必须推力器，`AGENTS.md`）与该惯例完全一致；把"轮组可稳定域/需外力域"的事先分划做成门控，是工程惯例在 12U 量级的量化表达，可直接写入论文设计依据。

7. **抓捕瞬间的冲击/能量管理存在三条工程路线，应按量级选型。** (a) 刚性接触+关节阻抗耗能：e.Deorbit（±80/176 Nm 阻抗关节）、DEOS（ET2 冲击耗能类，[Frontiers ET-Class](https://www.frontiersin.org/articles/10.3389/frspt.2022.792944/full)）；(b) 系留式远程捕获回避刚性冲击：RemoveDEBRIS 网/鱼叉（[Gunter](https://space.skyrocket.de/doc_sdat/removedebris.htm)）；(c) 对接机构内导向+预紧刚化：OE OECS（[eoPortal](https://www.eoportal.org/satellite-missions/stp-1)）。→ 12U：本项目 20 ms 名义接触窗（PROVISIONAL，`AGENTS.md`）+ 夹爪属路线 (a) 的最小实现；路线 (b) 需要系留管理与二次捕获容积，12U 体量不可行，论文中可明示排除依据。

8. **感知采用"平台级 + 臂端级"两级配置，视觉伺服精度直接决定机械包络。** e.Deorbit：平台 LIDAR/VBS + 臂端立体相机闭环，最差位姿误差 ±2.5 cm 反推 gripper/clamp 包络（[Jaekel 2018 §6.1](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2018.00100/full)）；OE：ARCSS+AVGS（[eoPortal](https://www.eoportal.org/satellite-missions/stp-1)）；RSGS：20+ 相机（[MLQ 2026-07-23](https://mlq.ai/news/northrops-robotic-satellite-servicer-begins-yearlong-trip-to-geosynchronous-orbit/)）。→ 12U：相机"总线安装 vs 腕部安装"架构未决（`02_PRODUCT_STRUCTURE.yaml` 中 CAMERA_BRACKET 为 HOLD），基准证据支持以"抓捕点全程可见 + 闭环精度可覆盖夹爪包络"作为该 HOLD 的裁决准则。

9. **飞行任务的安全层是"程序性 fail-safe + FDIR"，不是形式化判据——这正是可贡献的空档。** Orbital Express 以 ATP 逐级地面批准放权（[eoPortal](https://www.eoportal.org/satellite-missions/stp-1)），并经历两次濒败故障靠地面干预恢复（[NTRS Grappling Spacecraft](https://ntrs.nasa.gov/api/citations/20210020506/downloads/Grappling_Spacecraft%20Paper%20Final.pdf)）；ELSA-d 推力器异常后中止抓捕、降级运行，结论原文"for the safety of the mission, the team decided not to proceed with the capture"（[Astroscale 2024-01-24](https://www.astroscale.com/en/news/astroscales-elsa-d-finalizes-de-orbit-operations-marking-successful-mission-conclusion)）；ADRAS-J 首次绕飞 FDIR 自动中止后安全恢复（[TDnet PDF](https://tdnet-pdf.kabutan.jp/20241211/140120241211536979.pdf)）。→ 12U：把 SAFE/UNKNOWN/UNSAFE 做成机器裁决门（UNKNOWN 永不 ALLOW），等于把上述程序性 fail-safe 形式化到策略选择层；仓内九构型寄存（LEFT/RIGHT/BOTH_PANEL_FAIL 等 attached-stuck 降级构型）与该思路同源，可在论文中对照引用。

10. **服务星/目标质量比决定设计难度区间，本项目落在"小抓大"极端区。** 质量比：OE ≈4.0（900/224）、ClearSpace-1 ≈5.2（580/112）、MEV ≈1.2（2330/≈2000 级）、e.Deorbit ≈0.17（1380/8000）；本项目 31.02/150 ≈0.21（碎片）、31.02/22 ≈1.41（目标星）（质量数据来源各任务节）。→ 12U：与 e.Deorbit 同区，该区共同后果是组合体 CoG 大幅外移、轮组必然不足、推力矢量对准成为一级问题；e.Deorbit 的解是可调对准机构，12U 需要在推力线布局与任务剖面上给出自己的解（建议）。

## 4. 论文 related-work 框架建议

**三段式结构建议：**

- **第 1 段：飞行验证的服务/抓捕工程惯例（本文 §1–§2 的表）。** 按"界面假设"分两类：prepared/cooperative（ELSA-d/M 磁吸对接板、MEV 探针插 LAE、Orbital Express grapple fixture+OECS、RSGS 双臂服务、Otter 静电附着）vs unprepared/non-cooperative（e.Deorbit、DEOS、ClearSpace-1、RemoveDEBRIS、ADRAS-J 逼近）。要点：非合作类尚无在轨抓捕成功案例（ClearSpace-1 未发射、ADRAS-J 只逼近），工程界以 CONOPS 程序与 FDIR 兜底安全。
- **第 2 段：翻滚非合作目标的控制研究。** 简引姿态同步、阻抗/柔顺抓捕、抓捕后稳定的控制文献；**注意红线**：momentum feedforward compensation、Koopman/model-free FFSR 控制、RL detumbling、data-driven post-capture robust MPC、多模态视觉+RL 自主抓取均已被查新裁决排除，只能作 baseline/工具层引用，不得包装为本文创新；momentum prebias 只作为 sim_12 S3a 候选策略（Dimitrov 2004 祖先线）引用。
- **第 3 段：空档定位=策略选择层的物理可行域门控。** 空档陈述（建议表述）：工程任务证明了抓捕可行但安全靠程序性 FDIR（ELSA-d 中止、ADRAS-J 绕飞中止、OE ATP）；控制文献把抓捕后稳定做成控制器问题（已被占位的方向）；**两端之间缺少"抓不抓、用什么策略抓、抓后能否在执行器容量内稳定"的可机器裁决判据**。本文位置：pre-capture→post-capture 可行性判据（ω_post≤ω_allow、H_required≤H_available）+ binding-gate 策略选择 + SAFE/UNKNOWN/UNSAFE fail-closed（UNKNOWN 永不 ALLOW）+ embodied candidate 与 independent physics veto 的分层。量级证据：12U/微纳级仅有 CPOD（RPO 未对接）与 ADRAS-J（逼近未抓捕），该量级"抓捕+策略门控"无先例。

**写作纪律：** 不使用"首次结构–接触–任务一体化仿真框架"类宽泛表述（已被 Lu 2026 占位）；所有与飞行任务的对比只做工程事实对比（质量、机构、执行器、安全行为），不暗示本项目达到飞行 TRL。

## 5. 数据缺口（UNKNOWN 清单）与后续建议

| 缺口 | 影响 | 建议补源渠道 |
|---|---|---|
| 各任务反作用轮/动量轮角动量容量（N·m·s） | 执行器容量对比只能定性 | 厂商手册（Honeywell/Blue Canyon/Rocketlab 轮组）、IAC 论文 |
| DEOS servicer/client 质量与帆板 | 质量比序列缺一点 | DLR Phase B 报告、Astrium 论文（IAC 2012–2013） |
| e.Deorbit chaser 帆板与功率配置 | 大柔性附件对比不完整 | ESA CDF 研究报告、OHB/Airbus 会议论文 |
| ClearSpace-1 帆板翼数/内部布局 | 四臂布局对比不完整 | ClearSpace 后续 PDR/CDR 公开材料、SpaceOps 2025 论文全文 |
| Starfish Otter 帆板/内部布局 | 小服务星对比不完整 | FCC 申报文件（公开，含结构/电源描述） |
| RSGS MRV 帆板功率与布局 | GEO 服务星对比不完整 | NRL/Northrop 后续技术论文 |
| RemoveDEBRIS 帆板构型、ELSA-d 内部布局 | 微纳级对比不完整 | SSTL/Astroscale 技术论文、IAC 报告 |

## 附录 A：仓内锚点文件（sha256 前 12 位）

| 文件 | sha256(12) | 用途 |
|---|---|---|
| `AGENTS.md` | 3d2269562678 | 项目口径、sim_05–sim_12 核心证据、查新红绿线 |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json` | 14d30fd40ac6 | 机械终裁与 Gate A 状态 |
| `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml` | 0f9897ef4e41 | 12U 产品结构树：臂基座 x=208 mm、M3R、双翼、夹爪、降级构型寄存 |
