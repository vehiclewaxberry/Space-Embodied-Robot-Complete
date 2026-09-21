---
title: B1 12U 内部结构与设备布局基准调研（WEB-STRUCT）
generated_at: 2026-08-27
author_agent: WEB-STRUCT（C 轨机械完善研究代理）
scope: 12U CubeSat 内部结构硬约束、商业结构/堆栈实践、星上设备包络与质量基准、12U 级推进、布局优化文献、内部布局设计规则；供 F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1 三舱内部布局完善直接引用
---

# B1 12U 内部结构与设备布局基准

> 证据规则：公开资料均给 URL，访问日期统一为 **2026-08-27**；仓内引用给路径，关键文件给 sha256 前 12 位。
> 凡标注「估计」者为代理基于来源数据的推断，标注 `UNKNOWN` 者为未查到可靠公开数值，均未编造。
> 本文只做研究/方案文档，不改写任何仓内既有文件、Gate 或 SSOT。

## 0. 仓内上下文（只读引用）

- 三舱分舱决策：`20_engineering/design_review/V2_PDR_package/11_loop_review/design_decision_matrix.yaml`（sha256 前 12 位 `e54edecca043`），`PDR-D-003: front_mission_mid_avionics_rear_service_three_bay`，重开触发条件为 `profile_or_bay_boundary_change`。
- 舱段 owner 定义：`20_engineering/design_review/V2_PDR_package/04_packaging/subsystem_packaging_review.md`（sha256 前 12 位 `b904bd1db800`）——front：`VOL-FM-ROBOT`/`VOL-FM-SENSOR`；mid：`VOL-MID-OBC/EPS/BAT/ADCS`；rear：`VOL-REAR-PROP/COMM/THERMAL/SERVICE`；另有 `LONGITUDINAL_HARNESS_CORRIDOR_OWNER` 与两侧 `VOL-SIDE-SOLAR-L/R`。
- 质量风险锚点：`AGENTS.md`（sha256 前 12 位 `3d2269562678`）记载 Unified R2 URDF 总质量 **31.022864807342987 kg**（19 link/18 joint，含臂与帆板组件）——已超出 CDS 12U 24 kg 上限，见 §1.2 与 §7。

---

## 1. (a) Cal Poly CDS Rev 14.1 的 12U 硬约束

主来源：[CubeSat Design Specification Rev. 14.1（Cal Poly，2022-02，NASA 镜像 PDF）](https://www.nasa.gov/wp-content/uploads/2018/01/cubesatdesignspecificationrev14_12022-02-09.pdf)，官方入口 [cubesat.org/cubesatinfo](https://www.cubesat.org/cubesatinfo)。条款号以下文引用为准。

### 1.1 包络、质量、质心（表 1：CDS Table 1/2 + Appendix B）

| 项目 | 数值 | 出处（CDS Rev 14.1 条款） |
|---|---|---|
| 12U 外包络 | **226.3 × 226.3 × 366.0 mm**（X×Y×Z） | Appendix B 规格图；[NASA SOA Structures 表](https://www.nasa.gov/smallsat-institute/sst-soa/structures-materials-and-mechanisms/) 同值佐证（访问 2026-08-27） |
| 最大质量 | **≤ 24.00 kg** | §2.2.10 Table 1（2 kg/U 系列：1U 2.00、3U 6.00、6U 12.00、12U 24.00 kg）；超出可按 mission-to-mission 与 dispenser/launch provider 协商（§2.2.10.1/2） |
| 质心（CG）允差 | 相对几何中心 **X ±4.5 cm、Y ±4.5 cm、Z ±7 cm** | §2.2.11 Table 2（[NASA 镜像 PDF 表 2](https://www.nasa.gov/wp-content/uploads/2018/01/cubesatdesignspecificationrev14_12022-02-09.pdf?emrc=f56c65) 与第三方整理 [cubesat-specs](https://github.com/JuliusPinsker/cubesat-specs) 一致） |
| 坐标系 | 原点在 CubeSat 几何中心，−Z 面先插入 dispenser | §2.2.1 / §2.2.2 |
| 附加容积「Tuna Can」 | 3U/6U/12U 可选 −Z 面外扩容积，尺寸 dispenser 相关 | §2.2.1.3 Note + Figure 3 |

注：部分旧资料（如 [nanosats.eu](https://www.nanosats.eu/cubesat.html)）仍按 340.5 mm 高度给出 12U 标称 20×20×34.05 cm；**现行 CDS Rev 14.1 与 NASA SOA 均为 366.0 mm**。本报告一律采用 366.0 mm。若选用老版 340.5 mm 结构件，须与 dispenser 单独确认（估计）。

### 1.2 导轨、keep-out 与机械接口（表 2：CDS §2.2 机械条款摘录）

| 条款 | 要求 | 对内部布局的含义 |
|---|---|---|
| §2.2.3 | 侧面（黄色区）突出物距 rail 平面 **≤ 6.5 mm** | 侧壁内侧器件/连接器布置受 ±X/±Y 面 6.5 mm keep-out 约束；太阳翼根部、外部 SMA 头计入 |
| §2.2.5 | 导轨宽度 **≥ 8.5 mm**（rail 边缘到首个突出物） | 四角纵向 8.5 mm 宽带内不得有内部件穿透；纵梁/线束走廊要避开 |
| §2.2.6/2.2.7 | rail 表面粗糙度 < 1.6 μm；棱边圆角 ≥ 1 mm | 结构外购件验收项 |
| §2.2.8 | rail 在 ±Z 端面与相邻 CubeSat 接触面积 **≥ 6.5 × 6.5 mm** | 共乘堆叠时端框设计约束 |
| §2.2.9 | ≥ 75% 导轨与 dispenser 导轨接触；允许 25% 内凹 | 长导轨可局部让位给侧舱门/维修口 |
| §2.2.4 | 可展开件必须由 CubeSat 自身约束，不得依赖 dispenser | 帆板/机械臂收拢锁定（HDRM）为星上责任 |
| §2.2.12/2.2.13 | 结构与导轨用 Al 7075/6061/6082/5005/5052；与 dispenser 接触面**硬阳极化**防冷焊 | 外购结构默认满足；自研结构须遵守 |
| §2.2.14.1 | 分离弹簧：最大力 **< 6.7 N**、行程 **> 2.5 mm** | 共乘时分离界面设计值 |
| 接口替代 | 不用 tab 约束法的 dispenser 通用上述条款；tab 式（PSC 等）另有规范 | 12U 亦可走 tab 式分配器（见 §1.3），接口选型影响侧框设计 |

### 1.3 分离/分配器接口与「分离环」说明

- 12U 主流仍是**导轨式 dispenser**（ISIPOD/QuadPack、Nanoracks、Exolaunch 等）。QuadPack 支持 12U(XL)/16U 及组合（[ISISPACE QuadPack，EO-Atlas](https://eo-atlas.org/launch_services/isispace-quadpack-deployer)，访问 2026-08-27）。
- **Tab 式**：CDS §2.2 注明 tab 约束法见 PSC（Planetary Systems Corp）规范；Spaceflight 任务规划指南列有「Specification for 3U, 6U, 12U AND 27U tab-type CubeSats, 2002367 Rev F」（[Spaceflight MPG Rev G](https://newspaceeconomy.ca/wp-content/uploads/2022/06/spaceflight-mission-planning-guide-rev-g-2.pdf)，访问 2026-08-27）。
- 「分离环（separation ring）」严格说是微卫星/ESPA 级接口（如 NanoAvionics MP42 用 15″ ESPA 分离环，[MP42 产品页](https://nanoavionics.com/small-satellite-buses/microsatellite-bus-mp42/)，访问 2026-08-27）；**12U CubeSat 标准接口是四角导轨+分离弹簧，不是分离环**（有来源事实）。若本项目因 31 kg 质量（§0）走向「12U 形 ESAP 级微星」路线，接口定义将整体改变，属 owner 级决策（建议，见 §7）。

### 1.4 与布局直接相关的电气/操作条款

| 条款 | 要求 | 布局含义 |
|---|---|---|
| §2.1.4 | 推进系统 **≥ 3 级 inhibit** 防误点火 | 推进舱需 3 级串联隔离的线束/阀门设计，rear 舱空间预留 |
| §2.1.3 | 推进按 AFSPCMAN 91-710 Vol 3 设计/集成/测试 | 压力容器安全因子与文件链 |
| §2.1.5 Note | 建议参考 FAA 锂电 100 Wh/块（携带行李类比） | 电池组单包能量与分隔布置的工程参考（非强制） |
| §2.1.7 | 材料 TML ≤ 1.0%、CVCM ≤ 0.1% | 内部非金属件（线束绝缘、胶、热控多层）选材约束 |
| §2.1.8 | 被动磁体磁场 ≤ 0.5 Gauss（超出地磁部分，包络外） | 磁部件（磁矩器、永磁 HDRM）与磁强计/星敏的布局间距 |
| §2.1.9 | 上升段泄压：ventable volume/area < 50.8 m（2000″） | 密闭舱段（电池舱、推进舱）开泄气孔设计 |

---

## 2. (b) 商业 12U 结构与堆栈实践

### 2.1 在售 12U 结构对比（表 3）

| 产品/厂商 | 主结构质量 | 安装模式 | 二级结构/可维护性 | 来源（访问 2026-08-27） |
|---|---|---|---|---|
| ISIS 12-Unit CubeSat Structure（ISISPACE，经 CubeSatShop 在售） | ~1.5–2.0 kg（不同来源口径：主结构 vs 主+二级；[SatCatalog: dry mass 2.0 kg](https://www.satcatalog.com/component/12-unit-cubesat-structure/)；[Técnico 论文: 1.5 kg, Al 6061](https://fenix.tecnico.ulisboa.pt/downloadFile/3096619880809190/Thesis.pdf)） | PC/104 堆栈，多种安装配置 | PCB/模块堆**先在二级结构中装成组件，最后整体装入承力框**，保证航电可达性（[CubeSatShop 12U structure](https://www.cubesatshop.com/product/12-unit-cubesat-structure/)） | 同左各链接 |
| Spacemind SM12（NPC Spacemind，Orbital Transports 在售） | 主结构 **1430 g**（二级结构另计） | 用户可配置 PCB 堆栈，**水平+垂直两种堆装方向**；6 个分离开关（标准）；可选剪切板 | 模块化堆栈、双方向装配利于分段集成与抽拉维护；按 JX-ESPC-101133-B / ECSS-E-ST-10-03 鉴定（[Orbital Transports SM12](https://catalog.orbitaltransports.com/sm12-12u-cubesat-structure/)） | 同左 |
| 2NDSpace VERSE-12 | **≈ 1190 g** | 兼容 CDS 与商用组件，用户可定义开孔布局 | 定制孔位 + 快速集成为卖点（[satsearch 结构综述](https://blog.satsearch.co/2020-09-25-satellite-structures-on-the-global-marketplace)） | 同左 |
| EnduroSat 12U XL Structure | UNKNOWN（官网仅表单索取 datasheet+CAD） | 12U XL（加高型） | 官网称模块快拆、在线配置器（[EnduroSat 12U structure](https://www.endurosat.com/products/12u-structure/)） | 同左 |
| KSF Space 12U frame | UNKNOWN（营销页无工程数表） | 低成本教学/入门定位 | 宣称符合发射方要求（[KSF 12U 介绍](https://iuee.university/12u-cubesat-structure/)、[4dbc 页](https://www.4dbc.net/portfolio/12u-chassis-frame-structure-cubesat-nanosatellite/)） | 同左 |

观察（估计）：12U 裸结构（含基本二级结构）质量集中在 **1.2–2.0 kg**，约占 24 kg 上限的 5–8%；结构质量不再是 12U 布局的主要矛盾，**设备与推进的体积/质心分配才是**。

### 2.2 堆栈 vs 托盘的行业实践

- **PC/104（90 × 96 mm）堆栈仍是 12U 航电二级结构的事实标准**：GomSpace NanoDock/NanoMind/NanoPower 全系 90×96 mm 板形（[GomSpace NanoMind A3200](https://gomspace.com/shop/subsystems/command-and-data-handling/nanomind-a3200.aspx)）；CubeSpace CubeADCS 核为最多 4 块 PC/104 堆叠（[CubeADCS 3-Axis ICD](https://www.cubesatshop.com/wp-content/uploads/2016/06/CubeADCS-3-Axis-ICD-v1.3.pdf)）；ISIS iMTQ 磁力矩器板可插在 ISIS 结构堆栈之间（[SatCatalog iMTQ](https://www.satcatalog.com/component/imtq/)）（均访问 2026-08-27）。
- **水平/垂直混合堆装 + 独立托盘/抽拉**：Spacemind SM12 明确支持 horizontal 与 vertical stack assembly（见表 3）；ISIS 模式是「组件先成堆、整堆入框」。12U 由于有 226 mm 见方底面，可在同一层并排放 2 个 90×96 堆栈，**层内分区比 3U/6U 自由得多**（基于尺寸的几何推断，估计）。
- **整星平台对载荷的空间分配**：ISIS 12U/16U 平台给载荷 **8–12 U** 体积、载荷平均功率 ≤ 40 W、峰值 ≤ 100 W（[SatNow: ISISPACE CubeSat 12U/16U Platform](https://www.satnow.com/products/satellite-bus-platforms/isispace/45-1233-cubesat-12u-16u-platform)，访问 2026-08-27）。即成熟商用 12U 平台把 **~50–70% 容积留给任务载荷**（由 8–12U/12–16U 推算，估计）。NanoAvionics M12P（12U 整星 bus，双展开太阳翼）已用于 NASA ACS3、Omnispace 首批双星、LANL GTO 双星（[NanoAvionics M12P](https://nanoavionics.com/small-satellite-buses/12u-cubesat-nanosatellite-m12p/)，访问 2026-08-27）——12U 平台承载复杂任务（含 GTO）已有在轨先例。

---

## 3. (c) 典型星上设备包络 + 质量数据表（核心交付）

说明：「质量范围」为同类 COTS 产品横截面（有来源），「代表型号」给 1–2 个具体型号与手册/产品页 URL（访问 2026-08-27）。所有 PC/104 板形均为 90 × 96 mm。

### 3.0 汇总表（类别 → 质量范围 → 典型包络 → 型号 → URL）

| 组件类别 | 典型质量范围 | 典型包络 (mm) | 代表型号（关键参数） | 来源 URL |
|---|---|---|---|---|
| OBC | 24–70 g | PC/104 单板，65–96 mm 见方 | NanoMind A3200：24 g，65×40×7.1；CubeSpace CubeComputer：~50–70 g，90×96×10 级（第三方论文值） | [satnow A3200](https://www.satnow.com/products/on-board-computers/gomspace/116-1279-nanomind-a3200)；[DUTH 论文](https://repo.lib.duth.gr/jspui/bitstream/123456789/16843/1/TourgaidisS_2018.pdf) |
| EPS | 80–300 g | PC/104 单板或模块组 | GomSpace NanoPower P60：基板 <80 g + 每 ACU 54 g + 每 PDU 47 g，≤4 模块；P31u（GOMX-3 在用） | [GomSpace P60](https://gomspace.com/product/nanopower-p60/)；[eoPortal GOMX-3](https://www.eoportal.org/satellite-missions/gomx-3) |
| 电池组 | 250–1000 g（40–100+ Wh） | PC/104 宽 × 20–41 mm 高 | GomSpace BP4：92×88.9×19.9–28.9，18650×4，2P-2S 6–8.4 V/6 Ah（≈44 Wh，估计）；BPX 100 Wh：93×86×41，≈500 g | [GomSpace BP4](https://gomspace.com/shop/subsystems/power/nanopower-bp4.aspx)；[GomSpace BPX](https://gomspace.com/product/nanopower-bpx/) |
| 反作用轮（单轮） | 60–400 g | 28–100 mm 见方/直径 | CubeWheel S 60 g 28×28×26.1（1.77 mN·m·s）；M 90 g（4 mN·m·s）；L 150 g（11 mN·m·s）；AAC RW400 197/210/375 g，50×50×27（15/30/50 mN·m·s） | [NASA SOA 2020 表](https://www.nasa.gov/wp-content/uploads/2017/03/soa2020_final8_0.pdf)；[AAC RW400](https://www.aac-clyde.space/what-we-do/space-products-components/adcs/rw400)；[CubeWheel Small ICD](https://satcatalog.s3.amazonaws.com/components/211/SatCatalog_-_CubeSpace_-_CubeWheel_Small_-_ICD.pdf) |
| 集成 ADCS（轮+磁+敏感器+处理器） | 0.4–1.7 kg | 0.5U–1U 级 | Blue Canyon XACT-15：0.89 kg，10×10×5 cm（0.5U）；MAI-400：694 g，10×10×5.16 cm（11.1 mN·m·s/轮）；CubeADCS Large：<1300 g（12–16U 用）；AAC iADCS-200：0.47 kg | [BCT XACT](https://www.bluecanyontech.com/spacecraft-subsystems/xact/)；[MAI-400 datasheet](https://satcatalog.s3.amazonaws.com/components/87/SatCatalog_-_Adcole_Maryland_Aerospace_-_MAI-400_-_Datasheet.pdf)；[CubeADCS Gen1](https://www.cubesatshop.com/wp-content/uploads/2023/05/GEN-1-ADCS-Jan-2023-web.pdf)；[NASA SOA 2024 表 5-2](https://www.nasa.gov/wp-content/uploads/2025/02/soa-2024.pdf?emrc=91b90c) |
| 星敏感器 | 42–350 g | 29–100 mm | AAC ST200：42 g，29×29×38.1，30″；Blue Canyon NST：350 g，100×55×50，6–40″；ST-16RT2：0.132 dm³（Rocket Lab/Sinclair） | [AAC ST200](https://www.aac-clyde.space/what-we-do/space-products-components/adcs/st200)；[satnow NST](https://www.satnow.com/news/details/2611-trending-star-trackers-of-2024)；[MDPI 2026 星敏表](https://www.mdpi.com/2226-4310/13/5/421) |
| 太阳敏感器 | 4–35 g | 27–35 mm | nanoSSOC-D60：4–7 g，27.4×14×5.9，±60°，<0.5°；SSOC-D60：35 g | [UPC 汇总表](https://upcommons.upc.edu/bitstreams/e7d7eca1-4e7d-a41d-8c39a3015f2d/download)；[NASA SOA 表](https://www.nasa.gov/wp-content/uploads/2021/10/soa_2021_1.pdf)；[Solar MEMS SSOC-D60](https://www.solar-mems.com/wp-content/uploads/2020/04/Solar-MEMS-SSOC-D60.pdf) |
| 磁力矩器 | 28–156 g | 60–96 mm 杆/板 | CubeTorquer S/M/L：28/36/72 g，0.24/0.66/1.90 A·m²；GomSpace GST-600：156 g，0.31–0.34 A·m²×3；ISIS iMTQ 板：0.2 A·m²，可插堆栈 | [NASA SOA 2021 磁矩器表](https://www.nasa.gov/wp-content/uploads/2021/10/5.soa_gnc_2021.pdf?emrc=1511ca)；[SatCatalog iMTQ](https://www.satcatalog.com/component/imtq/) |
| IMU | 50–100 g | <60 cm³ | Safran STIM300：<55 g，<2.2 in³（≈36 cm³），战术级 | [Safran STIM300](https://safran-navigation-timing.com/product/stim300/) |
| GPS/GNSS | 31–80 g | 71×46×11 级板卡 + 天线 | NovAtel OEM719：31 g，71×46×11，0.9–1.8 W，555 通道全星座 | [NovAtel OEM719](https://novatel.com/products/receivers/gnss-gps-receiver-boards/oem719)；[satnow OEM719](https://www.satnow.com/products/gnss-receivers/novatel/143-1435-oem719) |
| 数传电台 | 100–500 g | PC/104 板 ~ 0.5U | Syrlinks EWC31 S-band TT&C：96×90×24；ISIS TXS S-band（≤4.3 Mbps）；Syrlinks EWC27 X-band（OPS-SAT 在轨） | [eoPortal OPS-SAT](https://www.eoportal.org/satellite-missions/ops-sat)；[CubeSatShop ISIS TXS](https://www.cubesatshop.com/product/isis-txs-s-band-transmitter/) |
| 天线 | 50–300 g | Z 面贴装/展开 | EnduroSat S-band patch：Z 面安装、HPBW 70°、>7 dBi、低质量；UHF/VHF 展开鞭天线（ISIS 类） | [Orbital Transports EnduroSat S-band Antenna](https://catalog.orbitaltransports.com/s-band-antenna-commercial/) |

能量密度参考（估计）：18650 Li-ion 电池包工程比能量约 150–240 Wh/kg——BPX 100 Wh/500 g ≈ 200 Wh/kg 与此一致；据此 12U 配 2×100 Wh 电池约 1.0–1.3 kg（含结构/加热余量）。

### 3.1 对本表的使用注意

- 反作用轮选型决定 mid 舱高度：CubeWheel 系列直径 28–40 mm 级，XACT-15/MAI-400 这类 0.5U 集成件则直接占掉 10×10×5 cm 一整块。12U 任务若需消旋大角动量目标（仓内 sim_08 证据：|H_c|=3.65 N·m·s 为 12× 轮组容量），轮组仅能做姿态保持，**消旋主责在推进**——轮布置服从质心与隔振，不服从消旋需求（仓内证据，AGENTS.md sim_08）。
- 星敏感器需要无遮挡视场与遮光罩空间，太阳 exclusion 角 22–68°（[MDPI 2026 星敏表](https://www.mdpi.com/2226-4310/13/5/421)），布局时给遮光罩留圆柱 keep-out（估计）。
- GPS 天线与 S/X-band 天线有视场/无金属遮挡要求，通常布置在 ±Z 端面或顶角（行业惯例，估计）。

---

## 4. (d) 12U 级推进选项与对内部布局的影响

### 4.1 选项对比表（表 5）

| 类型 | 产品 | 包络/质量 | 工质/贮箱 | 关键性能 | 来源（访问 2026-08-27） |
|---|---|---|---|---|---|
| 冷气 | VACCO Standard MiPS | 0.3U；**542 g 含工质** | 自增压液态工质气化 | 总冲 44 N·s | [VACCO MiPS datasheet](https://www.vacco.com/images/uploads/pdfs/MiPS_standard_0714.pdf)、[产品页](https://cubesat-propulsion.com/standard-micro-propulsion-system/) |
| 冷气 | VACCO NEA Scout MiPS | ~2U | 同上，6×25 mN 推力器 | 总冲 500 N·s（14 kg 星 37 m/s） | [VACCO X16056000](https://www.cubesat-propulsion.com/wp-content/uploads/2017/08/X16056000-data-sheet-080217.pdf) |
| 冷气/双组元双模 | Dawn CubeDrive（B1 推力器） | **0.8U–4U** 模块 | N₂O + 丙烯（C₃H₆），贮箱与阀一体化 | 总冲 425–3500 N·s；B1 Isp 285 s，0.46–1.28 N，可纯冷气模式 | [Dawn CubeDrive](https://www.dawnaerospace.com/green-propulsion-cubedrives)、[NASA SOA 2026 §4](https://www.nasa.gov/wp-content/uploads/2026/05/soa-2026.pdf?emrc=d75388) |
| 单组元（肼/绿色） | Aerojet MPS-120 CHAMPS | 1U 级 | 肼或 AF-M315E，3D 打印贮箱 | UNKNOWN（推力 0.5 N 级，satnow 列表） | [Aerospace Corp 推进 compendium](https://aerospace.org/sites/default/files/2024-02/20231218%20Small%20Satellite%20Propulsion%20Survey_DISTRO_A.pdf)、[satnow Busek/Aerojet 列表](https://www.satnow.com/search/thrusters/filters?page) |
| 单组元（ADN 绿色） | NanoAvionics EPSS（LMP-103S） | UNKNOWN | ADN 基 | UNKNOWN（MIMPS-G 市场调查列为代表系统） | [MDPI Aerospace 2021 MIMPS-G](https://www.mdpi.com/2226-4310/8/6/169)、[NASA SOA §4](https://www.nasa.gov/smallsat-institute/sst-soa/in-space_propulsion/) |
| 电推（FEEP） | ENPULSION NANO R3 | **98×99×95.3 mm（≈1U）**；干/湿 UNKNOWN（工质 215 g） | 铟（In）固态贮存，无压力容器 | 推力 10–350 µN 级 | [ENPULSION NANO R3 页](https://www.enpulsion.com/products/nano-r3/)、[datasheet PDF](https://www.enpulsion.com/wp-content/uploads/DataSheet_Nano_20260317_V2.pdf) |
| 电推（FEEP） | ENPULSION MICRO R3 | 140×120×126.5 mm；干 2.7 kg（湿 UNKNOWN） | 铟 1.25 kg | 1 mN 级，Isp 1500–4500 s，30–120 W | [ENPULSION MICRO R3 页](https://www.enpulsion.com/products/micro-r3/)、[satnow](https://www.satnow.com/products/thrusters/enpulsion/36-1166-enpulsion-micro-r-) |
| 电推（RF 离子，碘） | Busek BIT-3 | **180×88×102 mm（1.6U）**；干 1.5 kg / 湿 2.9 kg | 碘（I₂）固体贮存 | 0.66–1.24 mN，Isp 1400–2640 s，56–80 W | [IEPC2017 BIT-3](https://iepc2017.org/sites/default/files/speaker-papers/iepc_2017_paper_-_tsay_v3.pdf)、[NASA TP-20210000201](https://ntrs.nasa.gov/api/citations/20210000201/downloads/TP-20210000201.pdf?attachment=true)、[MIT 论文表 4.4](https://dspace.mit.edu/bitstream/handle/1721.1/155314/Pettersson-gupet-PHD-AeroAstro-2024-thesis.pdf?sequence=1&isAllowed=y) |
| 电推（MEPT，碘） | T4i REGULUS-50 | **93.8×95×151 mm** | 碘 | 30–60 W，Isp ≤ 650 s；REGULUS-150 为 150 W 级，目标 >6U | [satnow REGULUS-50](https://www.satnow.com/products/thrusters/t4i-technology-for-propulsion-and-innovation/36-1178-regulus-50)、[Bellomo 2021](https://d-nb.info/1242243097/34) |
| 电推（RF 离子，碘） | ThrustMe NPT30-I2 | 1U；1.2 kg | 碘 230 g | 0.4–0.9 mN，Isp 1200–2450 s，38–60 W | [MIT 论文表 4.4](https://dspace.mit.edu/bitstream/handle/1721.1/155314/Pettersson-gupet-PHD-AeroAstro-2024-thesis.pdf?sequence=1&isAllowed=y) |

### 4.2 贮箱/工质对内部布局的影响（有来源事实 + 工程推断）

1. **压力容器 vs 固态工质是布局分叉点**：冷气/单组元/双组元均为压力贮箱（受 CDS §2.1.3/2.1.4 三重 inhibit 与 AFSPCMAN 约束），需要泄压、阀系与防爆间距；碘/铟电推（BIT-3、NPT30、REGULUS、ENPULSION）为**固体/低蒸气压工质，无高压容器**，对 rear 舱安全间距要求低（有来源：各 datasheet；推断：布局后果）。
2. **推力矢量过质心**：主推力器普遍布置在 −Z 面（可利用 Tuna Can 外扩容积，CDS §2.2.1.3），姿控小推力器成对/成簇斜置（Dawn B1 支持 clusters 与 cant angles，[Dawn CubeDrive](https://www.dawnaerospace.com/green-propulsion-cubedrives)）。
3. **贮箱近质心对称布置**：推进剂消耗时质心漂移最小化；大贮箱（双组元 2 贮箱）应对称于纵轴布置（工程惯例，估计）。
4. **羽流 keep-out**：推力器轴线不得扫过太阳翼、星敏感器视场与外部光学件；羽流对帆板的冲击与本项目帆板柔性（仓内 sim_07 92× 放大证据）耦合，rear 舱推力器间距需专项评审（仓内证据 + 工程推断）。
5. **质量占比**：12U 级电推系统 1.2–2.9 kg（表 5），化学系统 0.5–3 kg 级；本项目 31 kg 现状下任何 ≥1U 的推进都是 rear 舱第一大质量件（估计）。

---

## 5. (e) 布局优化文献

### 5.1 主文献：MDPI Aerospace 2025《Engineering-Oriented Layout Optimization and Trade-Off Design of a 12U CubeSat with In-Orbit Validation》

- 出处：Zhang J., Liu Z., Luo L., Zhao C., Li H. (哈工大卫星技术研究所)，*Aerospace* 2025, 12(6), 506，2025-06-03 出版，开放获取。[mdpi.com/2226-4310/12/6/506](https://www.mdpi.com/2226-4310/12/6/506)（访问 2026-08-27）。
- 方法：**GRASP（构造可行初始解，干扰 >1000 mm³ 即弃、RCL=10）+ NSGA-III（多目标精化）混合框架**；三阶段使用（初期可行域分析 → 详细设计 → 末期权衡），案例为中俄大学生联合 12U「ASRTU Friendship MicroSat」（2024-11-05 发射）。
- 公式化表述（可直接借鉴，论文 §2.3）：
  - 设计变量 L = {(xᵢ,yᵢ,zᵢ,θᵢ,ηᵢ, 尺寸缩放因子)}，ηᵢ 为安装面索引（六个安装面 + 底部 Tuna Can 扩展体）；
  - 五目标：max 容积利用 V(L)、min 质心偏移 C(L)=‖C−几何中心‖₂（式 9–10）、min 三轴主惯量和 I(L)（式 11–13，含平行移轴项）、min 六面功率密度标准差 T(L)（式 14–17，热均匀代理）、max 敏感器-执行器间距 D(L)=Σ‖c_s−c_a‖（式 18）；
  - 约束：单干扰约束 g(L)=ΣΔA_ij（干扰体积和），罚函数并入 φ(L)=Σωᵢfᵢ+λg(L)（式 19）；
  - CMA（Compatibility/Maintainability/Accessibility）以 bounding box 外扩计入；组件按长方体/圆柱包络、与坐标系对齐简化；
  - 假设：线缆质量 <5% 且近似均布，不计入质心/惯量；不约束固有频率（刚性标准结构+无大柔附件理由）。
- 工程结果：地面实测**质心偏差 ≤ ±2 mm**；在轨热数据正常；末段电池扩容案例（保护板并入 → 电池包络 +4%/+2% 可行）——证明「参数化包络 + 重优化」可吸收设计后期的设备变更。
- 运行成本：i7-12600K/64 GB 单次 4500–7300 s（Python multiprocessing）。

### 5.2 其他可借鉴文献（均为 MDPI 2025 综述引用 + 独立检索）

| 文献 | 要点 | 可借鉴处 | 来源（访问 2026-08-27） |
|---|---|---|---|
| Fakoor et al. 2016, SCALE（Adv. Space Res. 58） | 航天器组件自适应布局环境，联合 CAD+FEM+优化，考虑 CG/惯量/热/固有频率/强度 | 把 FEM 固有频率回环进布局优化的范式（本项目有帆板柔性与 ROM，可借鉴此耦合思路） | 经 [MDPI 2025](https://www.mdpi.com/2226-4310/12/6/506) 引文 [27] |
| Liang & Zheng 2019（J. Syst. Eng. Electron. 30） | 多目标优化+多属性决策，3D 模型 min CG 偏移与惯量积，引入碎片撞击风险指数 | Pareto 前沿 + 智能过滤选解的决策链 | 同上引文 [26] |
| Teng et al. 2009（IEEE TEC 14） | 双系统变粒度协同进化解卫星舱布局 | 布局问题协同进化分解的经典表述 | 同上引文 [16] |
| Cuco et al. 2015（Optim. Eng. 16） | 星上设备在结构板上的多目标布局 | 板级设备分配-布局两步法 | 同上引文 [24] |
| Chen et al. 2019（Acta Astronaut. 163） | 以**剩磁最小**为目标的微纳卫星布局优化 | 磁清洁目标函数化（磁矩器/永磁件相对磁强计的布置） | 同上引文 [20] |
| Zhang et al. 2022（Acta Astronaut. 198） | 多舱段微星「组件分配+布局」联合优化、可变舱段尺寸 | 舱段边界本身作为设计变量（对三舱边界 PDR-D-003 的 reopen 判据有参考价值） | 同上引文 [23] |
| Xu et al. 2020（SMO 61） | 轨道推进剂库：贮箱布置与设备定位分解优化 | 贮箱布局单列子问题处理 | 同上引文 [25] |

文献侧结论（估计）：12U 布局优化的**成熟公式化 = 包络 bounding box + 五目标（容积/质心/惯量/热均匀/敏感器间距）+ 单干扰罚约束 + CMA 间隙**；本项目可直接复用该目标体系，把 MDPI 的「六安装面」映射到三舱 owner 体积上，用 GRASP 思路先求可行、再谈最优。

---

## 6. (f) 12U 内部布局设计规则清单（14 条，供 F4R1 直接采用）

| # | 规则 | 依据来源 |
|---|---|---|
| R1 | 全星（含机械臂收拢态、帆板收拢态、天线）不得超出 226.3×226.3×366.0 mm；侧面突出 ≤6.5 mm；四角 8.5 mm 导轨带无内部件穿透 | CDS §2.2.3/2.2.5 + App B（§1） |
| R2 | 总质量预算 ≤ 24.00 kg，系统级余量 ≥10–15% 再分配到舱段 | CDS Table 1；[VMMO 12U 预研按 15% 余量](https://openresearch.surrey.ac.uk/view/delivery/44SUR_INST/12139785870002346/13140667620002346)（访问 2026-08-27） |
| R3 | 质心目标：CDS 硬约束 X/Y ±4.5 cm、Z ±7 cm；设计目标收严到 **±2 mm 级**（地面可测可达），并以实测值闭环 | CDS Table 2；MDPI 2025 实测 ±2 mm（§5.1） |
| R4 | 分舱沿纵轴：任务载荷/机构朝 +Z 任务面，推进朝 −Z（用 Tuna Can 外扩），航电居中——与商用平台同构 | ISIS/NanoAvionics M12P 实践（§2.2）；CDS §2.2.1.3/2.2.2 |
| R5 | 航电二级结构采用 PC/104 90×96 mm 堆栈；226 mm 见方层内可双堆栈并置；堆栈先成组件、整体入框，保证抽拉可达（CMA） | §2.2 行业实践；MDPI CMA（§5.1）；ISIS 二级结构模式（§2.1） |
| R6 | 重件（电池、推进贮箱、反作用轮组、集成 ADCS）靠近几何中心布置以压低 I(L)；最重单体不贴侧板悬臂安装 | MDPI I(L) 目标（§5.1 式 11–13） |
| R7 | 敏感器（星敏、IMU、磁强计）与执行器（反作用轮、磁矩器）间距最大化：星敏/陀螺远离开轮系；磁强计远离开磁矩器与永磁 HDRM | MDPI D(L)（式 18）；Chen 2019 剩磁目标；CDS §2.1.8 |
| R8 | 发热件（EPS、电池、电台、推进 PPU）贴结构面板安装，六面功率密度标准差最小化；纯被动热控下禁止大热源悬空 | MDPI T(L)（式 14–17）及其「贴面板」条款（§2.1 段） |
| R9 | 电池：独立 mount plane、带加热与保护板包络余量（≥+4%/+2% 可吸收后期扩容）；单包能量参考 100 Wh 分档 | CDS §2.1.5；MDPI 2025 §4.3 电池扩容案例（§5.1） |
| R10 | 推进：≥3 级 inhibit；主推力器置 −Z 面、推力矢量过质心；双贮箱对称于纵轴；贮箱近质心以减小消耗质心漂移；羽流不扫帆板/光学视场 | CDS §2.1.3/2.1.4；§4.2 第 2–4 条 |
| R11 | 线束：设纵向非实体走廊（rear→mid→front），power/data/RF 分离、弯曲半径预留；线缆质量 <5% 时可不计入质心模型但须登记 | 仓内 corridor owner（§0）；MDPI 线缆假设（§5.1） |
| R12 | 干涉控制：全部设备用含 CMA 间隙的 bounding box/cylinder 建模，干扰体积 >1000 mm³ 的候选直接拒绝；更换设备先改包络参数再重优化 | MDPI 2025 g(L) 与 GRASP 阈值（§5.1） |
| R13 | 可维护性：每个设备登记「mount-plane / service-direction / harness-entry / thermal-keepout / mass」五 owner；托盘抽取方向未定前保持 null，禁止外观推断 | 仓内 packaging review 方法（§0）+ MDPI CMA |
| R14 | 泄压与材料：密闭舱（电池、推进）开泄气孔满足 ventable volume/area < 50.8 m；内部非金属材料 TML ≤1.0%/CVCM ≤0.1% | CDS §2.1.9/2.1.7 |

---

## 7. 对本项目三舱布局（front_mission / mid_avionics / rear_service）的启示

1. **分舱拓扑与行业基准一致，可保留并补强依据**：商用 12U（ISIS、M12P、EnduroSat）与本仓 PDR-D-003 的「任务-航电-服务」三舱完全同构（§2.2、§6-R4）。本调研为 PDR-D-003 提供了外部基准背书，不构成 `profile_or_bay_boundary_change` 重开触发。
2. **最高风险：质量**。仓内 Unified R2 URDF 总质量 31.02 kg（AGENTS.md，§0）已超 CDS 12U 上限 24 kg 约 29%。路径只有三条（建议，待 owner 裁决）：(i) 减重 ≥7 kg（对照 §3 表，arm/帆板/结构是主变量）；(ii) 按 CDS §2.2.10.1 与 dispenser 协商超重特例；(iii) 脱离导轨式 12U、转 ESPA 级微星接口（§1.3）。**这是 C 轨内部布局工作必须先挂出的头号未知数**。
3. **mid 舱容量校核（基于 §3 实测包络）**：OBC（~0.05 kg）+ EPS（~0.2 kg）+ 2×100 Wh 电池（~1.0–1.3 kg，估计）+ 分布式 ADCS（CubeWheel×3–4 ≈ 0.3–0.6 kg + CubeTorquer×3 ≈ 0.11–0.22 kg + 星敏 0.04–0.35 kg + IMU 0.055 kg + GPS 0.031 kg）≈ **1.8–2.6 kg**；若改用 0.5U 集成 ADCS（XACT-15 0.89 kg / MAI-400 0.69 kg）则 mid 舱质量更集中、体积更整，但丧失绕质心配平自由度（权衡建议）。两类方案体积均 < 2U，mid 舱容积不是瓶颈，**质心位置才是**。
4. **质心工程的抓手在电池与推进**：B601 臂在前舱（front）形成大头质量，Z 向质心需靠 mid 电池组（可后移档位）与 rear 推进/贮箱后拉；CDS 给 Z ±7 cm 余量，MDPI 证明 ±2 mm 可达——建议本项目以「臂收拢态 + 推进剂耗尽态」双工况校核 CG 包线（结合 §4.2-3 与 §6-R3/R9/R10）。
5. **rear 舱即服务舱的容积现实**：1–2U 电推（BIT-3 1.6U/1.5–2.9 kg 或 ENPULSION NANO ≈1U）+ S/X-band 电台（0.2–0.5 kg）+ 天线下舱，是 12U 服务星标准配置（§4、§3）；rear-access 维修链（仓内 `VOL-REAR-SERVICE`）与 Dawn CubeDrive 这类 0.8U 模块快拆理念兼容（§4.1）。
6. **消旋职责划分决定 rear 舱优先级**：仓内 sim_08 证据（3.65 N·m·s = 12× 轮组容量）意味着消旋只能靠推进；**推进选型与 rear 舱空间是任务级刚需，不是可选项**（仓内证据 + §4）。
7. **文献方法直接可用**：MDPI 2025 的五目标+单干扰约束+GRASP/NSGA-III 流程（§5.1）可整体移植到本仓三舱 owner 体积上：把 `VOL-*` 12 个 owner 作为固定/半固定组件、设备表（§3）作为候选件库，先做 GRASP 式可行解扫描再谈 Pareto——这与仓内「fail-closed、先可行后最优」的治理风格一致（估计/建议）。
8. **帆板是文献外的新约束**：MDPI 2025 明确以「无大柔附件」为由忽略固有频率约束（§5.1）；本项目有 ANCF 帆板（sim_07 振铃 37–75 s）与 ROM（E23），布局对一阶频率/模态能的影响**不能免审**，建议将固有频率回环（SCALE 思路，§5.2）列为 C 轨后续工作项（建议）。

---

## 8. 数据缺口（UNKNOWN 清单，禁止臆造）

- EnduroSat 12U(XL) 结构质量、12U 平台质量/功率分配明细（官网仅表单索取）。
- KSF Space 12U 结构质量与鉴定状态（仅营销页）。
- ISIS 12U 结构质量的 1.5 vs 2.0 kg 口径差异（主结构 vs 主+二级，需原厂手册裁决）。
- GomSpace BP4 整包质量；NanoAvionics EPSS 详细包络/质量；Aerojet MPS-120 确切包络与质量。
- Syrlinks EWC27/EWC31、ISIS TXS 的确切质量（仅包络或在轨事实可查）。
- ENPULSION NANO R3 干/湿质量（datasheet 截断，工质 215 g 已确认）。
- Sinclair/Rocket Lab ST-16RT2 质量（仅体积 0.132 dm³）。
- CubeSpace CubeComputer Gen3 精确质量（仅第三方论文 50–70 g 级）。
- 所有商用件价格（均「price on request」）。

## 9. 参考来源清单（全部访问于 2026-08-27）

1. CDS Rev 14.1：https://www.nasa.gov/wp-content/uploads/2018/01/cubesatdesignspecificationrev14_12022-02-09.pdf ；入口 https://www.cubesat.org/cubesatinfo
2. NASA SOA Structures 6.0：https://www.nasa.gov/smallsat-institute/sst-soa/structures-materials-and-mechanisms/
3. cubesat-specs（CDS 表整理）：https://github.com/JuliusPinsker/cubesat-specs
4. MDPI Aerospace 2025 12U 布局优化：https://www.mdpi.com/2226-4310/12/6/506
5. CubeSatShop ISIS 12U 结构：https://www.cubesatshop.com/product/12-unit-cubesat-structure/ ；SatCatalog：https://www.satcatalog.com/component/12-unit-cubesat-structure/
6. Spacemind SM12：https://catalog.orbitaltransports.com/sm12-12u-cubesat-structure/
7. 2NDSpace VERSE-12（satsearch 综述）：https://blog.satsearch.co/2020-09-25-satellite-structures-on-the-global-marketplace
8. EnduroSat 12U 结构：https://www.endurosat.com/products/12u-structure/
9. KSF Space 12U：https://iuee.university/12u-cubesat-structure/ ；https://www.4dbc.net/portfolio/12u-chassis-frame-structure-cubesat-nanosatellite/
10. ISIS 12U/16U 平台（satnow）：https://www.satnow.com/products/satellite-bus-platforms/isispace/45-1233-cubesat-12u-16u-platform
11. NanoAvionics M12P：https://nanoavionics.com/small-satellite-buses/12u-cubesat-nanosatellite-m12p/ ；MP42：https://nanoavionics.com/small-satellite-buses/microsatellite-bus-mp42/
12. NASA SOA 2020（轮/磁矩器表）：https://www.nasa.gov/wp-content/uploads/2017/03/soa2020_final8_0.pdf ；SOA 2021 GNC：https://www.nasa.gov/wp-content/uploads/2021/10/5.soa_gnc_2021.pdf?emrc=1511ca ；SOA 2024：https://www.nasa.gov/wp-content/uploads/2025/02/soa-2024.pdf?emrc=91b90c
13. CubeWheel Small ICD：https://satcatalog.s3.amazonaws.com/components/211/SatCatalog_-_CubeSpace_-_CubeWheel_Small_-_ICD.pdf
14. AAC Clyde RW400：https://www.aac-clyde.space/what-we-do/space-products-components/adcs/rw400 ；ST200：https://www.aac-clyde.space/what-we-do/space-products-components/adcs/st200
15. BCT XACT：https://www.bluecanyontech.com/spacecraft-subsystems/xact/ ；NST（satnow 综述）：https://www.satnow.com/news/details/2611-trending-star-trackers-of-2024
16. MAI-400 datasheet：https://satcatalog.s3.amazonaws.com/components/87/SatCatalog_-_Adcole_Maryland_Aerospace_-_MAI-400_-_Datasheet.pdf
17. CubeADCS Gen1：https://www.cubesatshop.com/wp-content/uploads/2023/05/GEN-1-ADCS-Jan-2023-web.pdf ；3-Axis ICD：https://www.cubesatshop.com/wp-content/uploads/2016/06/CubeADCS-3-Axis-ICD-v1.3.pdf
18. MDPI 2026 星敏对比表：https://www.mdpi.com/2226-4310/13/5/421
19. nanoSSOC-D60：https://www.cubesatshop.com/wp-content/uploads/2016/06/nanoSSOC-D60-Technical-Specifications.pdf ；SSOC-D60：https://www.solar-mems.com/wp-content/uploads/2020/04/Solar-MEMS-SSOC-D60.pdf ；UPC 汇总：https://upcommons.upc.edu/bitstreams/e7d7eca1-4e7d-a41d-8c39a3015f2d/download
20. GomSpace：BP4 https://gomspace.com/shop/subsystems/power/nanopower-bp4.aspx ；BPX https://gomspace.com/product/nanopower-bpx/ ；P60 https://gomspace.com/product/nanopower-p60/ ；A3200 https://gomspace.com/shop/subsystems/command-and-data-handling/nanomind-a3200.aspx
21. NanoMind A3200（satnow）：https://www.satnow.com/products/on-board-computers/gomspace/116-1279-nanomind-a3200
22. eoPortal GOMX-3（P31u/BP4）：https://www.eoportal.org/satellite-missions/gomx-3
23. NovAtel OEM719：https://novatel.com/products/receivers/gnss-gps-receiver-boards/oem719 ；https://www.satnow.com/products/gnss-receivers/novatel/143-1435-oem719
24. eoPortal OPS-SAT（EWC27/EWC31）：https://www.eoportal.org/satellite-missions/ops-sat
25. ISIS TXS：https://www.cubesatshop.com/product/isis-txs-s-band-transmitter/
26. EnduroSat S-band 天线：https://catalog.orbitaltransports.com/s-band-antenna-commercial/
27. Safran STIM300：https://safran-navigation-timing.com/product/stim300/
28. VACCO MiPS：https://www.vacco.com/images/uploads/pdfs/MiPS_standard_0714.pdf ；https://cubesat-propulsion.com/standard-micro-propulsion-system/ ；NEA Scout：https://www.cubesat-propulsion.com/wp-content/uploads/2017/08/X16056000-data-sheet-080217.pdf
29. Dawn CubeDrive/B1：https://www.dawnaerospace.com/green-propulsion-cubedrives ；B1 datasheet：https://satcatalog.s3.amazonaws.com/components/1276/SatCatalog_-_Dawn_Aerospace_-_B1_Thruster_-_Datasheet.pdf?lastmod
30. ENPULSION NANO R3：https://www.enpulsion.com/products/nano-r3/ ；datasheet：https://www.enpulsion.com/wp-content/uploads/DataSheet_Nano_20260317_V2.pdf ；MICRO R3：https://www.enpulsion.com/products/micro-r3/
31. Busek BIT-3（IEPC2017）：https://iepc2017.org/sites/default/files/speaker-papers/iepc_2017_paper_-_tsay_v3.pdf ；NASA TP-20210000201：https://ntrs.nasa.gov/api/citations/20210000201/downloads/TP-20210000201.pdf?attachment=true
32. T4i REGULUS-50：https://www.satnow.com/products/thrusters/t4i-technology-for-propulsion-and-innovation/36-1178-regulus-50 ；Bellomo 2021：https://d-nb.info/1242243097/34
33. MIT 推进综述表 4.4：https://dspace.mit.edu/bitstream/handle/1721.1/155314/Pettersson-gupet-PHD-AeroAstro-2024-thesis.pdf?sequence=1&isAllowed=y
34. MDPI 2021 MIMPS-G：https://www.mdpi.com/2226-4310/8/6/169
35. NASA SOA 2026 §4 推进：https://www.nasa.gov/wp-content/uploads/2026/05/soa-2026.pdf?emrc=d75388 ；SOA §4 页：https://www.nasa.gov/smallsat-institute/sst-soa/in-space_propulsion/
36. Spaceflight MPG Rev G（tab 式 12U 规范 2002367）：https://newspaceeconomy.ca/wp-content/uploads/2022/06/spaceflight-mission-planning-guide-rev-g-2.pdf
37. ISISPACE QuadPack（EO-Atlas）：https://eo-atlas.org/launch_services/isispace-quadpack-deployer
38. VMMO 12U 预研（15% 质量余量）：https://openresearch.surrey.ac.uk/view/delivery/44SUR_INST/12139785870002346/13140667620002346
39. CubeSpace CubeComputer 第三方数据（DUTH 论文）：https://repo.lib.duth.gr/jspui/bitstream/123456789/16843/1/TourgaidisS_2018.pdf
40. 仓内引用：`20_engineering/design_review/V2_PDR_package/11_loop_review/design_decision_matrix.yaml`（sha256 `e54edecca043`）；`20_engineering/design_review/V2_PDR_package/04_packaging/subsystem_packaging_review.md`（sha256 `b904bd1db800`）；`AGENTS.md`（sha256 `3d2269562678`）
