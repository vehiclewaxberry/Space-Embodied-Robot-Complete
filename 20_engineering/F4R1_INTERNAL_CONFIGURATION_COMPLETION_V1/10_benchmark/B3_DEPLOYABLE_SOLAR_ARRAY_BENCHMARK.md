---
title: B3 — CubeSat 展开式太阳帆板基准调研（WEB-PANEL）
generated_at: 2026-08-27
author_agent: WEB-PANEL（C 轨机械完善研究代理）
scope: 面向赛后论文的展开式刚性帆板结构层次、面密度/比功率、收拢/展开动力学参数的开源基准；含占位参数真实性检验方法与灵敏度参数集建议。仅研究文档，不修改任何 Gate/Gate JSON/SSOT/CAD 文件。
---

# B3 CubeSat 展开式太阳帆板基准（Deployable Solar Array Benchmark）

## 0. 摘要与证据口径

**一句话结论**：CubeSat 展开式刚性帆板的整板面密度公开实测/推算值集中在 **≈3.4–5.0 kg/m²（PCB 基板路线）**，CFRP/铝蜂窝定制路线可降至 **≈2–3.5 kg/m²**，综合合理区间 **~2–5 kg/m²**；展开态一阶悬臂频率在 CubeSat 尺度（0.2 m 级悬臂）由**铰链/根部刚度主导**，公开实测/指标值 **~8–20 Hz**，远大于本项目当前 1 Hz 占位假设；阻尼比公开锚点 0.2%–3%，工程惯例 0.5–2%；展开力矩惯例为**静力矩裕度 >1（驱动力矩 ≥2× 阻力矩）**。

**证据口径标记**：

- 【实测/手册】= 公开数据手册、同行评议论文或官方报告直接给出的数值（带 URL，访问日期一律 2026-08-27）。
- 【推算】= 由【实测/手册】数据经显式计算得到，计算式与假设随文给出。
- 【估计/建议】= 工程惯例或本文建议，无单一权威来源。
- UNKNOWN = 公开渠道查不到，禁止编造。

**本项目锚点**（仓内 SSOT，仅供对照，本文不改动）：

| 仓内文件 | sha256（前12位） | 关键占位值 |
|---|---|---|
| `20_engineering/config/geometry/flexible_appendage_v1.yaml` | `52fa88084c62` | 单板 L=0.200 m × b=0.227 m（A=0.0454 m²），t=6 mm（占位），m=0.3483933 kg（σ=7.67 kg/m²），f1=1.0 Hz（0.7–1.3 包络），ζ=0.01（TBD_cite_literature） |
| `20_engineering/config/coupled_scene/coupled_model_v0.yaml` | `67a532fb29c7` | 耦合场景占位模型 |
| `AGENTS.md`（根，待办3） | `3d2269562678` | 「帆板质量 0.348 kg 为 SSOT 占位（真实 2–5 kg/m²，差 5–10 倍）」 |

---

## 1. (a) 展开式刚性帆板结构层次（stack-up）

CubeSat/小卫星展开式刚性帆板的主流构造为「基板 + CIC（Coverglass-Interconnected Cell，盖片-互连片-电池片组件）+ 铰链/阻尼 + HDRM」。NASA Smallsat SOA Power 章明确指出：展开阵基板主要为三类——**PCB（印制板）、CFRP（碳纤维板）、铝蜂窝夹层板**【实测/手册，[NASA SOA Power §3.2.2](https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/)】；JAXA 设计标准 JERG-2-215A 定义轻量刚性翼 = **铝蜂窝 + CFRP 面板基板**【实测/手册，[JAXA JERG-2-215A](https://sma.jaxa.jp/TechDoc/Docs/E_JAXA-JERG-2-215A.pdf)】。

| 层次 | 功能 | 典型材料/构造 | 典型厚度 | 面密度贡献 | 依据 |
|---|---|---|---|---|---|
| 三结砷化镓电池片（TJ GaAs, ~30% BOL） | 光电转换 | GaInP/GaAs/Ge 三结，BOL 效率 28–31.5%（AZUR 3G30C 28%、Spectrolab XTJ-Prime 30.7%、CESI CTJ30 29.5%） | 裸片 140–150 μm（EMCORE BTJ 140 μm；CESI CTJ30 150±20 μm） | 裸片 81–89 mg/cm² ≈ 0.81–0.89 kg/m²（CESI CTJ30） | 【实测/手册】[CESI CTJ30 数据表](https://www.cesi.it/app/uploads/2025/04/CESI-CTJ30-v2025.1.pdf)、[NASA SOA Power Table 3-1](https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/)、[CubeSat wikidot 电池汇编](http://cubesat.wikidot.com/the-technology-of-solar-cells) |
| 盖片（coverglass） | 抗辐射/微流星保护 | 掺铈微晶玻璃 CMX/CMG | 100–150 μm（NASA 设计例取 150 μm CMX） | ≈0.22–0.38 kg/m²（密度 ~2.23–2.55 g/cm³）【推算】 | 【实测/手册】[NTRS 19930008780](https://ntrs.nasa.gov/api/citations/19930008780/downloads/19930008780.pdf)；面密度为推算 |
| 电池组件（SCA/CIC 成品态） | 电池+盖片+互连+旁路二极管 | CIC = cell+interconnect+coverglass | 整体 280–300 μm（EnduroSat SCA 厚度） | 含盖片 ~125 mg/cm² ≈ 1.25 kg/m²（CAVU SC-3G-3） | 【实测/手册】[EnduroSat 6U 帆板页](https://www.endurosat.com/products/6u-solar-panel/)、[CAVU SC-3G-3 数据表](https://satcatalog.s3.amazonaws.com/components/1828/SatCatalog_-_CAVU_AEROSPACE_-_30_Efficiency_Triple_Junction_GaAs_Solar_Cell_-_Datasheet.pdf) |
| 胶接层 | 电池-基板粘接 | 双面 Kapton 胶带（5 mil≈127 μm，CAPLINQ PIT2SD）+ 银导电胶（EPO-TEK H20E）；真空防 void 需 via stitching | ~0.13 mm | ≈0.15–0.30 kg/m²【推算】 | 【实测/手册】[arXiv:2407.19356 §Assembly](https://arxiv.org/html/2407.19356v1) |
| 基板（substrate） | 结构承载 | (i) PCB：FR4/聚酰亚胺，1.2–2.0 mm（ISIS 标称 1.2–2.0 mm；BCT 6U 1.6 mm）；(ii) 铝蜂窝+CFRP 面板（JAXA 标准构造；SJ-18 演示件 19 mm）；(iii) 铝基+flex-PCB 覆盖（ISIS 特色） | PCB 1.2–2.0 mm；蜂窝 4–19 mm | FR4 1.6 mm ≈ 2.96 kg/m²（ρ≈1850 kg/m³）【推算】；蜂窝 5–10 mm ≈ 0.5–1.0 kg/m²【估计】 | 【实测/手册】[ISIS 帆板产品页](https://www.isispace.nl/products/small-satellite-solar-panels/)、[JAXA JERG-2-215A](https://sma.jaxa.jp/TechDoc/Docs/E_JAXA-JERG-2-215A.pdf)、[Lan et al. 2021, AIAA J. 59(6)](https://smart.hit.edu.cn/_upload/article/files/15/97/be9e866a4167a0588f12fd1b56b1/96cff543-b2c6-4349-966a-1659f04a027b.pdf)（SJ-18 板 10 kg/m²）；蜂窝面密度为估计 |
| 铰链+阻尼 | 展开驱动/锁定/减振 | 铝合金弹簧铰链（Ex-Alta 2，校内机加+阳极化）；tape-spring 铰链（非线性滞回）；SMPC/SMA 智能铰链（SJ-18）；粘性/黏弹阻尼层可选 | — | 摊薄 ≈0.3–1.0 kg/m²【估计】 | 【实测/手册】[arXiv:2407.19356](https://arxiv.org/html/2407.19356v1)、[Kim et al. 2020, Appl. Sci. 10(21):7902](https://www.mdpi.com/2076-3417/10/21/7902)、[Lan et al. 2021](https://smart.hit.edu.cn/_upload/article/files/15/97/be9e866a4167a0588f12fd1b56b1/96cff543-b2c6-4349-966a-1659f04a027b.pdf) |
| HDRM（压紧释放机构） | 发射段压紧+入轨释放 | (i) 烧线式 burn-wire：5 V/10 Ω 电阻加热 ~200 °C 熔断 Dyneema 线（Ex-Alta 2、EnduroSat）；(ii) SMA/记忆合金「人工肌肉」（SJ-18 SMA+SMPC；DMSA-3U）；(iii) Frangibolt/ERM（MMA HaWK  restraint 选项 F/E）；(iv) 闸刀/切割式（常见类型，本文未取到 CubeSat 级公开型号参数 → 细节 UNKNOWN） | — | 摊薄计入上栏【估计】 | 【实测/手册】[arXiv:2407.19356](https://arxiv.org/html/2407.19356v1)、[EnduroSat 6U Deployable](https://www.endurosat.com/products/6u-deployable-solar-array/)、[DMSA-3U（CubeSat.Market）](https://www.cubesat.market/dmsa-3u-deployable-multifunction-solar-array)、[MMA HaWK 规格表](https://mmadesignllc.com/specs-table/)、[Damkjar et al. 2019, IEEE CCECE（烧线释放机构，二手引自 arXiv:2407.19356 文献[9]）](https://arxiv.org/html/2407.19356v1) |

**底层预算（面密度自下而上合成，【推算】）**：

| 路线 | CIC层 | 胶接 | 基板 | 线束/传感器 | 铰链+HDRM摊薄 | 合计 |
|---|---|---|---|---|---|---|
| PCB 基（FR4 1.2–1.6 mm） | ~1.1（覆盖因子0.9×1.25） | 0.2 | 2.2–3.0 | 0.2–0.4 | 0.3–0.8 | **≈4.0–5.5 kg/m²** |
| CFRP/铝蜂窝（5–10 mm） | ~1.1 | 0.2 | 0.5–1.0 | 0.2–0.4 | 0.3–0.8 | **≈2.3–3.5 kg/m²** |

与 §2 的 COTS 实测/推算值（3.4–5.0 kg/m²，PCB 路线为主）自洽。

---

## 2. (b) 定量数据点：面密度与比功率

### 2.1 直接给出质量 → 可推算面密度的数据点

| 来源 | 产品/对象 | 质量 | 几何 | 面密度【推算】 | 口径与假设 |
|---|---|---|---|---|---|
| ISISPACE | CubeSat 帆板 1U | 50 g | 1U 面 ~0.010 m²（假设满铺） | **≈5.0 kg/m²** | PCB 基（铝基+flex-PCB），含光敏/温度传感器；板厚 1.2–2.0 mm。[ISIS 产品页](https://www.isispace.nl/products/small-satellite-solar-panels/) |
| ISISPACE | 3U(XL) / 6U(XL) / 8U | 150 / 300 / 400 g | 按对应 U 面 | **≈4.4 / ~3.6–3.9 / ~4.3 kg/m²** | 同上；6U/8U 面面积按 0.366×0.226 / 0.226×0.4 m 估，偏差 ±10% |
| DHV Technology | SPC-CS10（1U 板） | 39 g | 1U 面 ~0.010 m² | **≈3.9 kg/m²** | Ge 三结电池，2.42 W。[SatNow 条目](https://www.satnow.com/products/solar-panels/dhv-technology/102-1287-spc-cs10)、[DHV 官网](https://dhvtechnology.com/products/solar-panels-cubesats/) |
| Blue Canyon（二手） | BCT 6U Solar Panel | 300 g | 360×189.5×1.6 mm = 0.0682 m² | **≈4.4 kg/m²** | 20 W，BOL 29.5%。二手来源：[UPC 学位论文表](https://upcommons.upc.edu/server/api/core/bitstreams/32124f0b-8713-49f3-a9e1-fc411eb71baf/content)；与 NASA SOA 表 BCT 6U–12U 档 48–118 W/kg 自洽（20 W/0.3 kg=67 W/kg） |
| Ex-Alta 2（开源） | 展开板（6×XTJ-Prime） | 76 g（66–86） | 板面积未公开，按 2U 级面 ~0.0226 m² 估 | **≈3.4 kg/m²** | PCB 基板+弹簧铝铰链；面积假设见 §4.1，偏差大 → 标【推算】。[arXiv:2407.19356](https://arxiv.org/html/2407.19356v1) |
| SJ-18 智能阵（演示件） | 0.5×0.5 m 铝蜂窝单板 | 2.5 kg | 0.25 m²，19 mm 厚 | **10 kg/m²** | GEO 平台级地面演示件，含大量金属嵌件，**不代表 CubeSat COTS**。[Lan et al. 2021](https://smart.hit.edu.cn/_upload/article/files/15/97/be9e866a4167a0588f12fd1b56b1/96cff543-b2c6-4349-966a-1659f04a027b.pdf) |

### 2.2 比功率（W/kg）数据点（整板/整翼口径）

主源：NASA Smallsat SOA Power 2024 版 Table 3-2（厂商自报，NASA 声明未独立核实）【实测/手册，[SOA 2024 Power 章 PDF](https://www.nasa.gov/wp-content/uploads/2025/02/3-soa-power-2024.pdf)、[在线版（2025/26 更新）](https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/)、[NTRS SOA 2024 全卷](https://ntrs.nasa.gov/api/citations/20250000142/downloads/SOA_2024_final.pdf)】。

| 厂商 | 产品 | 类型 | 比功率 W/kg | 峰值功率（BOL） | 备注 |
|---|---|---|---|---|---|
| EnduroSat | 3U/6U/8U Solar Panel/Array | 展开刚性 | 66 / 64 / 65 | 14.4 / 19.2 / 24.0 W | 6U 展开：32 片电池、每侧 19.2 W（LEO）、burn-wire 释放、SCA 280–300 μm、$59k–88k。[产品页](https://www.endurosat.com/products/6u-deployable-solar-array/) |
| DHV Technology | DSA/BMSA 系列 | 体装+展开 | 33–68 | 2–1268 W | CubeSat PCB 系列 41–67 W/kg。[官网](https://dhvtechnology.com/) |
| NPC Spacemind | SP 系列 | 体装+双翼展开 | 58–76 | 2.4–72 W | — |
| GomSpace | NanoPower TSP | 展开刚性（每翼） | 60 | 45 W | — |
| ISISPACE | Smallsat Solar Panels | 体装+展开刚性 | 46 | 2.3 W/U | 展开板用自研铰链+HDRM（3U–8U）。[产品页](https://www.isispace.nl/products/small-satellite-solar-panels/) |
| AAC Clyde Space | Photon | 体装+展开刚性 | 未列（UNKNOWN） | 9.25 W/3U–12 面 | [Photon 产品页](https://www.aac-clyde.space/what-we-do/space-products-components/photon-solar-arrays) |
| Blue Canyon | BCT Solar Array | 体装+展开刚性 | *（询价） | 28–42（3U）/ 48–118（6U–12U） | — |
| SatRev | Deployable panel | 3U–6U 展开 | 40 | 36 W（典型 6U） | — |
| Pumpkin | DCSA 等 | 展开刚性 | 30–44 | 135–350 W | — |
| Lockheed Martin | SmallSat Solar Array | 增材基板展开刚性 | 53.6 | 170 W/板 | — |
| SDL | Modular Solar Panels | 展开刚性 | 84.5 | 180 W/板 | — |
| **MMA Design** | HaWK / zHawk / Next-Gen HaWK | 展开刚性（PCB） | **121 / 95 / 100**（NASA 表） | 36–310 W | 厂商规格表：标准 89–108、高性能 107–135 W/kg（不含 SADA），收拢高度 6.5–12 mm，功率口径 BOL AM0 28 °C。[MMA 规格表](https://mmadesignllc.com/specs-table/)；121 W/kg 为公开综述报道最高值（[McMullan et al. 2025, Acta Astronautica/ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0094576525007295)）；在研 FDM-HAWK 目标 >300 W/kg（32% 电池）[NASA TechPort](https://techport.nasa.gov/projects/9694) |
| Sparkwing（Airbus NL） | 30+ 种现货板（600×570 至 1230×800 mm） | 刚性，体装+1–3 板展开 | **18–45（NASA 表）** | 88–366 W/板 | **口径存疑**，见 §2.3。[Airbus 产品页](https://www.airbus.com/en/products-services/space/equipment/power/solar-array-products)、[SatCatalog 数据表](https://satcatalog.s3.amazonaws.com/components/1209/SatCatalog_-_SparkWing_-_SmallSat_Solar_Array_-_Datasheet.pdf) |
| ExoTerra | FOSA | 展开**柔性** | 140 | 150 W | 柔性毯 |
| Redwire | ROSA | 柔性毯 | 100 | 1000 W | ISS/DART 级 |
| Redwire | Aladdin | 刚柔混合 | 80 | 300 W | — |
| NASA（研究） | LISA-T | 薄膜柔性 | **>250**（指向型） | >200 W | [NTRS 20160011095](https://ntrs.nasa.gov/api/citations/20160011095/downloads/20160011095.pdf)；同文给出历史对比：Clyde 3U 体装 ~53、MMA HAWK ~130、TUI ~89、iSAT ~58 W/kg |

**全局经验界**【实测/手册】：NASA SOA 对 389 次任务统计——太阳阵任务**强烈聚集在 ~30 W/kg**，下界 1 W/kg、上界 ~200 W/kg（[SOA Power §3.2.2 Fig 3.3](https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/)）。

### 2.3 面密度合理区间结论与口径差异

**结论（本文建议口径）**：

| 路线 | 面密度区间 | 依据强度 |
|---|---|---|
| PCB 基板（CubeSat COTS 主流） | **3.4–5.0 kg/m²** | 强：4 个独立实测/推算点（ISIS 4.4–5.0、DHV 3.9、BCT 4.4、Ex-Alta ~3.4）+ 底层预算 4.0–5.5 |
| CFRP/铝蜂窝定制 | **2–3.5 kg/m²** | 中：底层预算 2.3–3.5 + SJ-18 重演示件（10）为上界外反例；缺 CubeSat 级实测 |
| 柔性/薄膜毯（ROSA/FOSA/LISA-T） | **<1.5 kg/m²**（典型 0.5–1.5） | 弱-中：由 >100–250 W/kg 与 ~200–400 W/m² 反推【推算】，属不同物类 |
| **综合「真实帆板」区间** | **~2–5 kg/m²**（与项目预期一致） | 覆盖 PCB 与蜂窝两条刚性路线 |

**口径差异警示**：

1. **Sparkwing 异常**：NASA 表报 18–45 W/kg；以 600×965 mm/155 W/25 W/kg 反推单板 6.2 kg → 10.7 kg/m²，与 Airbus 官方「up to 200 W/m²、lightweight carbon-fibre panels」宣传明显不符（[Airbus](https://www.airbus.com/en/products-services/space/equipment/power/solar-array-products)）。疑为 NASA 表把**整翼（含 yoke/线束/SADA 摊销）**口径混入，或数据陈旧。本文**不采用** Sparkwing 面密度反推值，仅保留其功率密度 ~200 W/m² 口径。
2. **比功率分母不一**：厂商「mass」有的指裸板、有的含铰链/HDRM/线束、有的含 SADA（MMA 明确标注「without SADA」）。跨厂商比较时 ±30% 不确定度属正常【估计/建议】。
3. **功率基准不一**：BOL@AM0/28 °C（MMA、NASA 表）vs LEO 轨道实际（EnduroSat「per side in LEO」）vs EOL；比较前须统一到 BOL AM0。
4. NASA SOA 明确声明：表内数据来自厂商网站/手册，**未经 NASA 独立核实**（[SOA Power 免责声明](https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/)）。

---

## 3. (c) 动力学数据：收拢频率 / 展开频率 / 阻尼比 / 展开力矩裕度

> 总口径提醒：NASA SOA 原话——展开阵的 deployed frequency、deployment mechanism 等「**Most of these metrics are not listed on manufacturer datasheets**」（[SOA Power §3.2.2](https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/)）。故动力学数据主要来自论文/标准而非 COTS 手册；查不到的项标 UNKNOWN。

### 3.1 收拢态一阶频率（发射段）

| 指标 | 数值 | 对象/口径 | 来源 |
|---|---|---|---|
| 整星一阶频率下限 | **≥130 Hz** | ESA「Fly Your Satellite」规范对 CubeSat 的要求（分析值） | 【实测/手册】[Warwick WUSAT-3 报告引 ESA FYS](https://warwick.ac.uk/fac/sci/eng/meng/wusat/projects/wusat-3/2021-22/evidence_report.pdf) |
| 设计建议 | **>100 Hz** | 3U CubeSat 避免与运载火箭耦合的常用建议 | 【实测/手册】[UGA SSRL SPOC 结构分析](https://smallsat.uga.edu/images/documents/presentations/StructuralAnalysisSPOC_r2.pdf) |
| 帆板组件级（收拢压紧态） | **要求 ≥80 Hz；实测 79.70 Hz（X 向）** | SJ-18 智能太阳阵（GEO 平台级，含主框架）正弦扫频实测 | 【实测/手册】[Lan et al. 2021, AIAA J. 59(6), DOI 10.2514/1.J059281](https://smart.hit.edu.cn/_upload/article/files/15/97/be9e866a4167a0588f12fd1b56b1/96cff543-b2c6-4349-966a-1659f04a027b.pdf) |

量级判断：收拢压紧态（HDRM 锁定）频率要求 **~80–130 Hz 量级**成立；CubeSat 文献常见「>100 Hz」级。

### 3.2 展开态一阶悬臂频率

| 数据点 | 数值 | 对象/尺度 | 来源 |
|---|---|---|---|
| 小卫星带辅助支撑太阳翼 | **8 Hz（实测/分析）** | 小卫星级刚性翼，根部自锁定铰链+支撑臂 | 【实测/手册】[《带辅助支撑式太阳翼设计与验证》，南京航空航天大学学报 2019S02](https://jnuaa.nuaa.edu.cn/ch/reader/view_abstract.aspx?file_no=2019S02&flag=1) |
| 箱式小卫星展开态设计指标 | **≥8 Hz** | 全展开状态一阶频率设计要求 | 【实测/手册】[J. Mach. Eng. Sci. Tech. (UM) 2024](https://journal2.um.ac.id/index.php/jmest/article/download/50192/12640) |
| 大型柔性阵（对照组） | **0.79 Hz** | 大太阳阵 dummy panel 柔性模态（被动阻尼研究基准） | 【实测/手册】[Woo et al. 2025, Aerospace 12(1):29](https://www.mdpi.com/2226-4310/12/1/29) |
| SJ-18 智能阵展开态 | 模态试验已做，具体频率值本文未提取到 | 0.5 m 板×2 | 【UNKNOWN（部分）】[Lan et al. 2021 §V](https://smart.hit.edu.cn/_upload/article/files/15/97/be9e866a4167a0588f12fd1b56b1/96cff543-b2c6-4349-966a-1659f04a027b.pdf) |
| **CubeSat 0.2 m 悬臂刚性板（本项目尺度）** | **≈15–20 Hz（板弯曲上界）→ 系统级 ~5–15 Hz（铰链/根部主导）** | 本文 §5 公式推算 | 【推算】§5.2 |

**判断**：任务预期的「小型展开阵 1–10 Hz」对 **0.5 m 以上翼展/柔性毯**成立（0.79–8 Hz 有实测锚点）；但对 **CubeSat 0.1–0.25 m 悬臂刚性小板**，板弯曲上界本身就有 15–20 Hz，1 Hz 对应的是**大型柔性翼**动力学（见 §5 检验）。

### 3.3 阻尼比

| 数值 | 口径 | 来源 |
|---|---|---|
| **0.2%（ζ=0.002）** | 太阳阵柔性模态建模取值（NASA 输入整形减振研究，全模态） | 【实测/手册】[Doherty 1998, NTRS 19980232013](https://ntrs.nasa.gov/api/citations/19980232013/downloads/19980232013.pdf) |
| **3%（ζ=0.03）** | 蜂窝夹层板声激励频响分析「generally taken as a constant value of 0.03」 | 【实测/手册】[Zhang et al. 2025, PMC12737105](https://pmc.ncbi.nlm.nih.gov/articles/PMC12737105/) |
| **0.5–2%** | 航天结构模态阻尼工程惯例取值带 | 【估计/建议】——无单一权威标准来源；上述两锚点（0.2%、3%）将其夹住 |

本项目占位 ζ=0.01（1%）位于惯例带中值，**可保留为 NOMINAL**，但须以 0.2%–3% 做包络（`flexible_appendage_v1.yaml` 中 `status: TBD_cite_literature` 可由本节两条引用闭环）。

### 3.4 展开力矩裕度

| 惯例 | 内容 | 来源 |
|---|---|---|
| 定义 | 展开力矩裕度 = 展开力矩/阻力矩 − 1；阻力矩 = 线束阻力矩 + 铰链滑动力矩 | 【实测/手册】[JAXA JERG-2-215A §5.3.3](https://sma.jaxa.jp/TechDoc/Docs/E_JAXA-JERG-2-215A.pdf) |
| 设计规范 | 大型太阳阵设计规范要求**静力矩裕度 >1**（即 T_drive ≥ 2×T_resist），最不利工况下考核 | 【实测/手册】[MDPI Coatings 2023, 13(8):1351](https://www.mdpi.com/2079-6412/13/8/1351) |
| 分析方法 | 弹簧铰链展开力矩裕度随转角包络分析（SADM 案例） | 【实测/手册】[Calassa 1995, NTRS 19950020846](https://ntrs.nasa.gov/api/citations/19950020846/downloads/19950020846.pdf)；tape-spring 铰链滞回下裕度评估：[Kim et al. 2020](https://www.mdpi.com/2076-3417/10/21/7902) |
| CubeSat 铰链力矩绝对值 | — | **UNKNOWN**（COTS 手册不公开；Ex-Alta 2 开源铰链亦未给力矩值） |

任务预期「≥2× 阻力矩」与文献规范一致（裕度>1 ⟺ 驱动≥2×阻力）。

---

## 4. (d) 开源帆板设计案例

### 4.1 arXiv:2407.19356《Open-Source CubeSat Solar Panels》（2024，主案例）

Sorensen & Halliwell（Univ. Calgary / AlbertaSat），SSC24-WP2-33【实测/手册，[arXiv:2407.19356](https://arxiv.org/abs/2407.19356)、[HTML 全文](https://arxiv.org/html/2407.19356v1)】。已在 Northern SPIRIT 星座 3 颗星（Ex-Alta 2 3U + YukonSat/AuroraSat 2U）在轨验证（2023-04-24 由 ISS NanoRacks NRCSD25 部署），并将用于 Ex-Alta 3（2025）。

**其公开的设计数据清单**：

| 类别 | 公开内容 | 具体数值/型号 |
|---|---|---|
| 电设计 | 电路拓扑、MPP、轨道功率 | 6S1P，14.4 V/0.48 A MPP；单板轨道功率 5.2–7.4 W（typ 6.2 W）；6×Spectrolab XTJ-Prime（69×40 mm） |
| 质量 | 体装板 / 展开板质量（min-typ-max） | 72-82-92 g / 66-76-86 g |
| 材料/工艺 | 基板类型、胶接体系、固化流程 | **PCB 基板**；CAPLINQ PIT2SD 双面 Kapton 胶带（5 mil）；EPO-TEK H20E 银胶；120 °C/2 h 分步固化+真空脱气；via stitching（≥5 cm² 密度）+ 排气孔防真空 void（热像仪检查） |
| 机构 | 铰链、HDRM、展开到位检测 | 铝合金弹簧铰链（本科 capstone 设计，校内机加+阳极化）；burn-wire：5 V 加 10 Ω 金属膜电阻（CPF110R000FKEE6）升温 ~200 °C 熔断双股 Dyneema（Berkley BSBFS10-22）；SPDT 开关（PANA-AV4424）；PEEK 3D 打印件 |
| 传感集成 | 电流/电压/光电二极管×3/温度×3 + 太阳敏感器，I²C ADC | 单板传感功耗 60–75 mW |
| 测试 | TVAC、振动、电性能 | <10⁻⁶ Torr 保温 6 h 后全功能测试；CSA David Florida 实验室振动鉴定；AM1.2 太阳模拟器（G2V Sunbrick）I-V/P-V 曲线；反偏测试 |
| 任务分析 | 展开失效影响 | STK+SGP4 一年轨道仿真：名义 9.6 W±17% vs 双板失效 2.9 W；临界模式 20 mW 仍可存活 |
| 附加设计 | 板内嵌磁矩器 | 0.22 Am² @1 W/3.3 V（COMSOL 优化；10–30% 效率于独立磁棒） |
| 开放许可 | 设计文件+装配流程+最佳实践 | **Apache 2.0**（论文承诺在线公开） |

**未公开（对本项目的缺口）**：基板厚度、板面精确尺寸、**展开态频率、铰链力矩、阻尼比**——均 UNKNOWN；这正印证 §3 的口径判断（动力学指标普遍不公开），也是 §5 检验方法的必要性所在。

### 4.2 新概念阵列（Origami/薄膜类，各 1–2 例）

| 案例 | 概念 | 关键事实 | 来源 |
|---|---|---|---|
| **OrigamiSat-1（FO-98）** | 3U CubeSat 在轨折纸式多功能**薄膜**展开 | Tokyo Tech 等联合研制，2019-01-18 Epsilon 火箭入轨；膜面展开行为/形状在轨测量；为后续超轻薄膜阵（含薄膜太阳电池）铺路 | 【实测/手册】[Ikeya et al., Acta Astronautica（ScienceDirect S0094576520302204）](https://www.sciencedirect.com/science/article/pii/S0094576520302204)、[ITU Small Satellite Handbook](https://www.itu.int/dms_pub/itu-r/opb/hdb/R-HDB-65-2023-PDF-E.pdf)、[Gunter's Space Page](https://space.skyrocket.de/doc_sdat/origamisat-1.htm) |
| **BYU/JPL origami 太阳阵（「Flash」原型）** | 折纸（Miura 类）刚性厚板折叠 | Trease(JPL)+Zirbel/Howell(BYU)+R. Lang；原型收拢 ~1 cm 厚 → 展开直径 2.7 m；面向大功率舱外阵 | 【实测/手册】[NASA JPL 新闻](https://www.jpl.nasa.gov/news/solar-power-origami-style/)、[BYU CMR](https://compliantmechanisms.byu.edu/post/cmr-students-turn-to-origami-to-solve-astronomical-space-problem) |
| **LISA-T（NASA 薄膜阵）** | 薄膜柔性毯+弹性展开 | 比功率目标 >250 W/kg（指向型），收拢功率密度 >200 kW/m³ 级；CIGS 薄膜组件 2024 起搭载验证 | 【实测/手册】[NTRS 20160011095](https://ntrs.nasa.gov/api/citations/20160011095/downloads/20160011095.pdf) |

意义：新概念路线的面密度/比功率均优于刚性板 1 个量级以上，但**展开态频率更低（≪1–5 Hz）、动力学更「软」**——恰是本项目当前 1 Hz 占位假设真正对应的物理对象，而非 COTS 刚性小板【估计/建议】。

---

## 5. (e) 占位参数真实性检验方法（可直接套用）

### 5.1 方法一：面积 × 面密度区间 → 质量合理性

```
m_panel = σ · A,   A = L · b
```

| 输入 | 值 | 来源 |
|---|---|---|
| L（悬臂长） | 0.200 m | 仓内 SSOT `52fa88084c62` |
| b（板宽） | 0.227 m | 同上 |
| A | **0.0454 m²** | 【推算】 |
| σ 合理区间 | 2–5 kg/m²（§2.3） | 本文基准 |
| **m_panel 合理区间** | **0.091–0.227 kg** | 【推算】 |
| 当前占位 | 0.3483933 kg（σ=7.67 kg/m²） | 仓内 SSOT |

**判定**：占位面密度 7.67 kg/m² **超出** 2–5 kg/m² 带上界 ~1.5×，超 PCB COTS 中值 ~1.9×；占位质量偏重，真实 COTS 板应**更轻**（0.09–0.23 kg）。修正系数 1.5–3.8×（7.67/5 → 7.67/2）——注意：AGENTS.md 待办3 所称「差 5–10 倍」**方向正确（占位偏重）但量级偏大**；5–10× 仅当对标柔性/薄膜毯（σ<1.5 kg/m²）时成立【推算】。

### 5.2 方法二：悬臂板公式 → 一阶频率量级

```
f1 = (β1² / 2πL²) · √(EI/μ)     β1 = 1.87510407（一阶悬臂根）
均匀板： D = E·t³ / (12(1−ν²))， EI = D·b， μ = σ·b
夹层板： D ≈ E_f·t_f·h²/2（面板弯曲刚度，h=芯厚）
```

代入本项目 L=0.2 m：系数 β1²/(2πL²) = **13.99**。

| 构造方案 | E / t 或 E_f / h | D（N·m） | σ（kg/m²） | EI（N·m²） | μ（kg/m） | **f1【推算】** |
|---|---|---|---|---|---|---|
| FR4 PCB 1.6 mm | E=20 GPa, ν=0.18 | 7.06 | 3.5 | 1.60 | 0.79 | **≈20 Hz** |
| FR4 PCB 1.2 mm | E=20 GPa, ν=0.18 | 2.98 | 2.7 | 0.68 | 0.61 | **≈15 Hz** |
| CFRP/铝蜂窝 5 mm | E_f=70 GPa, t_f=0.1 mm×2 | 87.5 | 1.8 | 19.9 | 0.41 | ≈97 Hz（**上界失真**：实际受铰链/根部刚度限制，系统级回落至 ~5–15 Hz，与 §3.2 实测 8 Hz 一致） |
| 现占位（反算） | — | — | 7.67 | 8.90e-3（SSOT 给定） | 1.742 | 1.00 Hz（与 SSOT 自洽 ✓） |

**判定**：真实 0.2 m COTS 刚性板的板弯曲频率量级 **15–20 Hz**；计入铰链/根部/线束刚度后系统级 **~5–15 Hz**。当前占位 f1=1 Hz 隐含 EI 比真实 PCB 板**软 ~180×**（1.60/8.90e-3），对应的是大型柔性翼/薄膜毯动力学，而非 CubeSat 刚性小板。**质量误差（1.5–3.8×，偏重）远小于刚度误差（~10² 量级，偏软）**——这是本基准最重要的发现：占位参数的失真主要在**刚度/频率**轴而非质量轴。

### 5.3 方法三（交叉校核）：功率一致性

```
P_BOL ≈ S_AM0 · η_cell · A · coverage = 1366 · 0.30 · 0.0454 · 0.85 ≈ 15.8 W/板
```

（S_AM0=1366±10 W/m² 取 JAXA JERG-2-141 口径【实测/手册，[JERG-2-215A §5.1.1.2](https://sma.jaxa.jp/TechDoc/Docs/E_JAXA-JERG-2-215A.pdf)】；coverage 0.85 为【估计/建议】）
与 COTS 6U 级展开板每侧 15–20 W（EnduroSat 19.2 W、ISIS ~15 W 级）一致 → 几何/电池假设自洽。

---

## 6. (f) 面向论文灵敏度研究的参数集建议（LOW / NOMINAL / HIGH）

| 参数 | LOW | NOMINAL | HIGH | 依据（档位理由） |
|---|---|---|---|---|
| 面密度 σ（kg/m²） | **2.0** | **4.0** | **7.7** | LOW=CFRP/蜂窝定制下限（§2.3）；NOM=PCB COTS 中值（ISIS 4.4–5.0、DHV 3.9、BCT 4.4）；HIGH=现占位（保守上界；SJ-18 式重演示件 10 可作极端情景） |
| 单板质量 m（kg，×0.0454 m²） | **0.091** | **0.182** | **0.348** | = σ·A【推算】；HIGH 与现行 SSOT 一致保证回溯兼容 |
| 展开态一阶频率 f1（Hz） | **1.0** | **8** | **20** | LOW=现占位名义（保留为「超柔性界」，须标注对应大型翼/薄膜毯而非 COTS 刚性板，§5.2）；NOM=小卫星翼实测 8 Hz + ≥8 Hz 设计指标（§3.2，铰链/根部主导）；HIGH=0.2 m PCB 板弯曲上界 ≈20 Hz（§5.2） |
| 阻尼比 ζ | **0.002** | **0.01** | **0.03** | LOW=NASA 太阳阵柔性模态建模 0.2%（Doherty 1998）；NOM=工程惯例中值=现占位；HIGH=蜂窝板声振频响惯例 3%（Zhang 2025）（§3.3） |
| 展开力矩裕度 M_s = T_drive/T_resist − 1 | **≥1（最低可接受）** | **1.5–2（设计目标）** | **≥3（保守）** | LOW=文献设计规范静力矩裕度 >1（⟺ ≥2× 阻力矩，MDPI Coatings 2023；JAXA JERG-2-215A 定义）；NOM/HIGH 为工程惯例【估计/建议】；力矩绝对值 UNKNOWN，须实测或向厂商询价 |

**使用建议**：(1) 论文灵敏度扫描建议以 (σ, f1, ζ) 三轴为主，力矩裕度单列机构设计章节；(2) LOW f1=1 Hz 档在报告中必须带限定语「超出 COTS 刚性板物理范围，用于包络大型柔性翼类动力学」；(3) 质量与刚度**联动**改（真实板的 σ 与 EI 同源于基板构造），不建议独立随意组合 σ=7.7 与 f1=20 这类物理上不自洽的配对——自洽配对见 §5.2 表【估计/建议】。

---

## 7. 对本项目（C 轨主计划）的影响摘要

1. **占位修正方向**：现占位（0.348 kg、1 Hz、ζ=0.01）→ 真实 COTS 刚性板（~0.09–0.23 kg、~5–20 Hz、ζ=0.002–0.03）。质量轴失真 1.5–3.8×（AGENTS.md 待办3「5–10 倍」应下修）；**刚度/频率轴失真 ~10–180×，是主要矛盾**。
2. **Gate/仿真含义**：sim_11 帆板模态参数占位、sim_07 刚柔 92× 结论、「A1 柔性反馈可忽略」等结论在真实参数带（尤其 f1↑、m↓）下需按 §6 三档重扫；ζ=0.01 可用本节两引用闭环 `TBD_cite_literature`。
3. **UNKNOWN 清单（禁止编造）**：COTS 铰链力矩绝对值、展开态频率与阻尼的厂商手册值、SJ-18 展开态频率具体值、Sparkwing 单板质量、Ex-Alta 2 基板厚度/板面尺寸、闸刀式 HDRM CubeSat 级公开参数、ISISPACE 展开板（vs 体装板）分项质量。
4. **建议下一步**：若需 CubeSat 级实测展开频率/铰链力矩，唯一可靠路径是采购 1–2 款 COTS 板（EnduroSat/ISIS，价格公开 $59k 级）做锤击模态+展开力矩测试，或复刻 arXiv:2407.19356 开源设计（Apache 2.0）自建件实测。

---

## 8. 参考来源清单（访问日期均为 2026-08-27）

**仓内（sha256 前12位）**：`20_engineering/config/geometry/flexible_appendage_v1.yaml`(`52fa88084c62`)；`20_engineering/config/coupled_scene/coupled_model_v0.yaml`(`67a532fb29c7`)；`AGENTS.md`(`3d2269562678`)。

**公开资料（URL）**：
- NASA SOA Power（2024 PDF）：https://www.nasa.gov/wp-content/uploads/2025/02/3-soa-power-2024.pdf ；在线版：https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/ ；NTRS 全卷：https://ntrs.nasa.gov/api/citations/20250000142/downloads/SOA_2024_final.pdf
- ISISPACE 帆板：https://www.isispace.nl/products/small-satellite-solar-panels/ ；手册 PDF：https://www.isispace.nl/wp-content/uploads/2016/02/ISIS-Solar-Panels-brochure-v1.pdf
- AAC Clyde Space Photon：https://www.aac-clyde.space/what-we-do/space-products-components/photon-solar-arrays
- EnduroSat 6U 展开阵：https://www.endurosat.com/products/6u-deployable-solar-array/ ；6U 板：https://www.endurosat.com/products/6u-solar-panel/
- DHV Technology：https://dhvtechnology.com/products/solar-panels-cubesats/ ；SPC-CS10：https://www.satnow.com/products/solar-panels/dhv-technology/102-1287-spc-cs10
- Sparkwing：https://sparkwing.space/ ；数据表：https://satcatalog.s3.amazonaws.com/components/1209/SatCatalog_-_SparkWing_-_SmallSat_Solar_Array_-_Datasheet.pdf ；Airbus 产品页：https://www.airbus.com/en/products-services/space/equipment/power/solar-array-products
- MMA Design：https://mmadesignllc.com/specs-table/ ；FDM-HAWK：https://techport.nasa.gov/projects/9694 ；综述：https://www.sciencedirect.com/science/article/pii/S0094576525007295
- 电池/CIC：CESI CTJ30 https://www.cesi.it/app/uploads/2025/04/CESI-CTJ30-v2025.1.pdf ；CAVU SC-3G-3 https://satcatalog.s3.amazonaws.com/components/1828/SatCatalog_-_CAVU_AEROSPACE_-_30_Efficiency_Triple_Junction_GaAs_Solar_Cell_-_Datasheet.pdf ；coverglass https://ntrs.nasa.gov/api/citations/19930008780/downloads/19930008780.pdf
- 开源案例：arXiv:2407.19356 https://arxiv.org/abs/2407.19356 （HTML https://arxiv.org/html/2407.19356v1 ）
- 动力学：ESA FYS 130 Hz https://warwick.ac.uk/fac/sci/eng/meng/wusat/projects/wusat-3/2021-22/evidence_report.pdf ；UGA SPOC https://smallsat.uga.edu/images/documents/presentations/StructuralAnalysisSPOC_r2.pdf ；SJ-18（Lan et al. 2021, DOI 10.2514/1.J059281）https://smart.hit.edu.cn/_upload/article/files/15/97/be9e866a4167a0588f12fd1b56b1/96cff543-b2c6-4349-966a-1659f04a027b.pdf ；NUAA 翼 https://jnuaa.nuaa.edu.cn/ch/reader/view_abstract.aspx?file_no=2019S02&flag=1 ；≥8 Hz 指标 https://journal2.um.ac.id/index.php/jmest/article/download/50192/12640 ；0.79 Hz https://www.mdpi.com/2226-4310/12/1/29
- 阻尼：Doherty 1998 https://ntrs.nasa.gov/api/citations/19980232013/downloads/19980232013.pdf ；Zhang 2025 https://pmc.ncbi.nlm.nih.gov/articles/PMC12737105/
- 力矩裕度：JAXA JERG-2-215A https://sma.jaxa.jp/TechDoc/Docs/E_JAXA-JERG-2-215A.pdf ；MDPI Coatings 2023 https://www.mdpi.com/2079-6412/13/8/1351 ；Calassa 1995 https://ntrs.nasa.gov/api/citations/19950020846/downloads/19950020846.pdf ；Kim 2020 https://www.mdpi.com/2076-3417/10/21/7902
- 新概念：OrigamiSat-1 https://www.sciencedirect.com/science/article/pii/S0094576520302204 ；JPL origami https://www.jpl.nasa.gov/news/solar-power-origami-style/ ；LISA-T https://ntrs.nasa.gov/api/citations/20160011095/downloads/20160011095.pdf
- 其他：DMSA-3U（SMA 释放）https://www.cubesat.market/dmsa-3u-deployable-multifunction-solar-array ；BCT 6U 板（二手）https://upcommons.upc.edu/server/api/core/bitstreams/32124f0b-8713-49f3-a9e1-fc411eb71baf/content ；TU Delft PocketQube 展开阵（204.8 g/96.2 W/kg）https://repository.tudelft.nl/file/File_37a08b1f-1895-4e03-b3ad-54d2b31c1841
