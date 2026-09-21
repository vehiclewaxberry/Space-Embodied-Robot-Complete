# 推进系统选型贸易研究报告（PROPULSION_TRADE_STUDY_20260917）

- 日期：2026-09-17（全部 datasheet 事实检索日期 = 2026-09-17）
- 阶段：设计贸易研究。**选型未冻结**（冻结需 owner 授权）。
- 顶层裁决：`TRADE_STUDY_COMPLETE__SELECTION_NOT_FROZEN__MISSION_BUDGET_OPEN`
- 全程 fail-closed：查不到的字段 = null + NAMED_GAP，禁止估计；测试/目录 PASS ≠ 任务预算闭环。

## 1. 冻结需求侧证据（数字不改）

| 来源 | 冻结值 |
|---|---|
| sim_08（README + assumptions.yaml） | 150 kg 碎片 @3°/s 捕获后 \|H_c\| = 3.65 N·m·s；名义工况 2 推力器偶、力臂 l_T = 0.17 m、每推力器 12 mN、粗消旋 900 s；推进剂 cold gas (Isp 60) 36.5 g / green monoprop (Isp 220) 10 g；全部常数为 NASA SmallSat SOA 类别占位 |
| PROPULSION_RESOURCE_SCREEN.json | CPOD8_RCM 需总冲量下限 42.9 N·s；两台 12 mN 推算消旋时间下限 1788.9 s（按目录盒半径 0.085 m 计）；C_POD_hardware_qualification=false；mission_budget_closed=false；actual_task_feasibility=UNKNOWN |
| scan_v0.yaml（门3/门4） | propellant_budget_max_g = 54.735；thruster_isp_s = {cold_gas:60, green_mono:220}；lever_arm 0.05–0.17 m；t_detumble_max_s = 3600 s |
| 轮组包络 | 3×100 mN·m·s（wheels_large，0.3 N·m·s，碎片工况 12× 超容 → 推力器必需） |

### 判据（阈值来源逐项标注）

| # | 判据 | 阈值 | 来源 |
|---|---|---|---|
| R1 | 单推力器推力 | ≥ 12 mN @ l_T = 0.17 m（名义 900 s 消旋档位） | sim_08 README/assumptions.yaml |
| R2 | 系统总冲量 | ≥ 42.9 N·s（下限） | PROPULSION_RESOURCE_SCREEN.json CPOD8_RCM 行 |
| R3 | 推进剂质量 | ≤ 54.735 g | scan_v0.yaml 门3 propellant_budget_max_g |
| R4 | 包络/干重 | 适配 12U（226×226×~340 mm 总线，推进分配 ≤2U 量级）；干重无冻结预算 → 仅记录不判 | 12U CubeSat 形式因数（项目布局惯例）；无冻结干重门 |
| R5 | 并发双机能力 | 两台推力器可同时点火构成力偶（净力≈0） | sim_08 架构（2-thruster couple）；screen 中 two_jet_concurrency_allowed_by_command_ICD |
| R6 | 重算闭环 | 用冻结公式重算消旋时间/推进剂质量 | sim_08 公式（见 §4） |

## 2. 候选普查（8 个真实 COTS，跨冷气/绿色单组元/绿色双组元/丁烷/水推进）

### C1. Dawn Aerospace B1（绿色双组元 N₂O/C₃H₆，可冷气模式）
- 推力 0.49–1.35 N；MIB 双组元 74 mN·s / 冷气 1.4 mN·s；脉冲 4 Hz；重启 18,000+；干重 260 g；尺寸 108×79×40 mm；Isp 248 s（satnow 目录值；官方页未直接给 B1 Isp → NAMED_GAP: official_datasheet_isp）；并发："Operable together or independently"（datasheet 明示）；功耗平均 0.8 W（第三方转述，NAMED_GAP: official power breakdown）；飞行宣称 50+ 已入轨。
- 来源：[Dawn Aerospace Thrusters](https://www.dawnaerospace.com/thrusters "citation")，检索 2026-09-17。

### C2. Dawn Aerospace B20（绿色双组元，20N 级）
- 推力 6.1–18.11 N（2025 页面为 6.1–16.7 N，版本差异已记录）；MIB 双组元 0.98–1 N·s / 冷气 10–50 mN·s；干重 600–695 g（页面版本差异）；尺寸 176×80×79 mm；Isp 285 s（satnow 目录值）；并发 datasheet 明示；飞行宣称 100+ 已入轨。
- 来源：[Dawn Aerospace Thrusters](https://www.dawnaerospace.com/thrusters "citation")、[Dawn green-propulsion-2025](https://www.dawnaerospace.com/green-propulsion-2025 "citation")，检索 2026-09-17。

### C3. Bradford ECAPS HPGP 1N（绿色单组元 LMP-103S）
- 推力 0.25–1 N（进给压力节流；<0.2 N 有演示）；Isp 194–227 s（稳态真空 1900–2230 N·s/kg）；MIB 官方上限 0.1 N·s，0.25 N×10 ms 脉冲演示达 2.5 mN·s（Aerospace Corp 表列 4.70 mN·s）；干重 0.38 kg；全长 178 mm；功耗反应器预热 8–10 W；脉冲寿命 12,000+；公开宣称 TRL 9、PRISMA/SkySat 等 25+ 星在轨。并发双机：单推力器元件，VACCO IPS 集成 4 台并演示 off-pulse 矢量控制 → 多机并发有集成证据。
- 来源：[Aerospace Corp ATR-2026-00705](https://aerospace.org/sites/default/files/2026-05/ATR-2026-00705.pdf "citation")、[NASA Green Propulsion SOA 2020](https://ntrs.nasa.gov/api/citations/20205006456/downloads/Marshall%20StateoftheArt_2020Final%20(AFRL%20PA%20Approved)-Final.pdf "citation")、[VACCO IPS 测试报告（NASA S3VI）](https://s3vi.ndc.nasa.gov/ssri-kb/static/resources/Testing%20of%20a%20Green%20Monopropellant%20Integrated%20Propulsion%20System.pdf "citation")，检索 2026-09-17。

### C4. NanoAvionics EPSS C1K（ADN 基绿色单组元，落压式）
- 推力 1.0 N (BOL) / 0.22 N (EOL)；Isp 213 s；总冲量 >400 N·s（C1 构型文献值 650 N·s）；湿重 1.2 kg（干重 null → NAMED_GAP: dry_mass）；包络 1.3U；功耗预热 9.6 W / 点火 1.7 W；LituanicaSAT-2 (2017) 飞行宣称；单推力器模块，双模块并发无公开 ICD → R5 UNKNOWN。
- 来源：[NASA SmallSat SOA In-Space Propulsion](https://www.nasa.gov/smallsat-institute/sst-soa/in-space_propulsion/ "citation")、[TU Delft 绿色单组元综述](https://pure.tudelft.nl/ws/files/95522429/aerospace_08_00169_v2.pdf "citation")、[NanoAvionics EPSS](https://nanoavionics.com/cubesat-components/cubesat-propulsion-system-epss/ "citation")，检索 2026-09-17。

### C5. VACCO Standard MiPS（R134a 冷气，0.3U–1U）
- 推力 10 mN ×5 独立推力器；Isp 40 s；总冲量 44–250 N·s（-1/-4/-7/-9 四档）；MIB 0.05 mN·s；湿重 542–1245 g（干重 null → NAMED_GAP）；待机 0.25 W / 最大稳态 10 W；9.0–12.6 VDC；"Each thruster operates independently"（并发有证据）；对应 screen 中 MIPS5_OLD 历史行族。
- 来源：[VACCO MiPS datasheet](https://www.vacco.com/images/uploads/pdfs/MiPS_standard_0714.pdf "citation")、[Aerospace Corp ATR-2026-00705](https://aerospace.org/sites/default/files/2026-05/ATR-2026-00705.pdf "citation")，检索 2026-09-17。

### C6. VACCO CPOD 模块（CPOD8_RCM，R134a/R236fa 冷气，8 推力器）—— screen 已筛候选
- 推力 10 mN ×8（四角成对）；Isp 40 s；总冲量 ≤186 N·s；稳态功耗 5 W；真空耐久测试 70,000+ 次点火；CPOD 3U 双星 2022 飞行宣称；并发双机 ICD 公开缺失（screen 冻结字段 two_jet_concurrency_allowed_by_command_ICD = null；command_min_width_s = null）→ R5 UNKNOWN。
- 来源：[Padua 大学论文 §2.1.6](https://thesis.unipd.it/retrieve/4ae8323b-e0b0-49bd-a2f4-c0a48077d217/Tesser_Giorgio_1157041.pdf "citation")、[Politecnico di Torino 论文](https://webthesis.biblio.polito.it/secure/20036/1/tesi.pdf "citation")、[VACCO X13003000-01 RCM 文档](https://cubesat-propulsion.com/wp-content/uploads/2022/04/X13003000-01_RCM_2016update.pdf "citation")，检索 2026-09-17。

### C7. Moog Monopropellant Propulsion Module（1U 增材制造模块，绿色或传统单组元）
- 推力 0.1–1 N（0.5 N 基线）；Isp 224 s（30:1 喷管基线）；包络 1U（10×10×10 cm 基线，可扩展）；湿重 1.01 kg；功耗 2×22.5 W/推力器；ΔV 59 m/s；总冲量 datasheet 扫描件不可读 → NAMED_GAP: total_impulse；TRL 3–4、**无飞行heritage宣称**；并发无公开说明 → R5 UNKNOWN。
- 来源：[Moog datasheet](https://www.moog.com/content/dam/moog/literature/sdg/space/propulsion/moog-monopropellant-propulsion-module-datasheet.pdf "citation")、[Aerospace Corp ATR-2026-00705](https://aerospace.org/sites/default/files/2026-05/ATR-2026-00705.pdf "citation")，检索 2026-09-17。

### C8. Pale Blue PBR-50（水 resistojet）
- 推力 ~10 mN @ 50 W；包络 250×300 mm（超出 12U 226 mm 横截面 → R4 FAIL）；Isp null（仅 PBR-20 公开 >70 s）→ NAMED_GAP: isp/total_impulse/dry_mass；2024 初首发飞行宣称（厂商口径）；并发无公开说明 → R5 UNKNOWN。
- 来源：[SatNow Pale Blue 产品线](https://www.satnow.com/news/details/3669-pale-blue-pioneering-sustainable-future-in-space-with-water-based-thruster-innovation "citation")、[satsearch PBR-10（同族）](https://satsearch.co/products/pale-blue-pbr-10-water-based-resistojet-thruster "citation")，检索 2026-09-17。

## 3. 贸易矩阵（PASS / FAIL / UNKNOWN）

| 候选 | R1 推力≥12mN | R2 总冲量≥42.9 N·s | R3 推进剂≤54.735 g | R4 12U包络 | R5 并发双机 | 综合 |
|---|---|---|---|---|---|---|
| C1 Dawn B1 | PASS (490–1350 mN) | PASS (CubeDrive 0.8U ≈400 N·s) | PASS (8.83 g) | PASS (108×79×40, 260 g) | PASS (datasheet 明示) | **全 PASS** |
| C2 Dawn B20 | PASS (6.1–18.1 N，远超) | PASS (500–250,000+ N·s 模块谱) | PASS (7.68 g) | PASS | PASS (datasheet 明示) | **全 PASS（推力过量级，需评估冲量位/羽流）** |
| C3 ECAPS HPGP 1N | PASS (250–1000 mN) | PASS (VACCO IPS 3320 N·s；单机吞吐 5–8 kg) | PASS (9.65–11.29 g) | PASS (0.38 kg/178 mm) | PASS (IPS 四机集成证据) | **全 PASS** |
| C4 NanoAvionics EPSS C1K | PASS (220–1000 mN) | PASS (>400 N·s) | PASS (10.28 g) | PASS (1.3U/1.2 kg 湿) | UNKNOWN (单推力器模块，双模块并发无 ICD) | PASS + R5 UNKNOWN |
| C5 VACCO MiPS (R134a) | **FAIL (10 mN < 12 mN)** | PASS (44–250 N·s；最低档裕度仅 1.1 N·s) | **UNKNOWN (54.735 g vs 预算 54.7348 g，亚毫克级贴边，低于任何物理置信度 → fail-closed 不判 PASS)** | PASS (0.3–1U) | PASS (各机独立) | FAIL/UNKNOWN |
| C6 VACCO CPOD8 | **FAIL (10 mN < 12 mN)** | PASS (≤186 N·s) | **UNKNOWN（同 C5 贴边）** | PASS (1U) | UNKNOWN (ICD 冻结缺口) | FAIL/UNKNOWN |
| C7 Moog MP Module | PASS (100–1000 mN) | UNKNOWN (总冲量 NAMED_GAP) | PASS (9.77 g) | PASS (1U/1.01 kg 湿) | UNKNOWN | UNKNOWN 为主；且无飞行heritage |
| C8 Pale Blue PBR-50 | **FAIL (~10 mN)** | UNKNOWN (总冲量 NAMED_GAP) | UNKNOWN (Isp NAMED_GAP) | **FAIL (250×300 mm > 226 mm)** | UNKNOWN | FAIL/UNKNOWN |

**关键发现（新）**：R134a 冷气候选（C5/C6）在 Isp=40 s 下重算推进剂需求 = 54.7350 g，与 scan_v0 门3 预算 54.7348 g 之差仅 −0.0003 g（亚毫克、亚分辨率）。fail-closed 口径下既不能判 PASS 也不能诚实判 FAIL，记 UNKNOWN——这与 sim_10 对 X1 阈值分辨率的处置一致。**结论：R134a 冷气路线在冻结预算下无物理裕度，等价于被门3 实质排除**。

## 4. sim_08 占位常数替换映射与重算

冻结公式（sim_08 README/assumptions.yaml）：
- 角动量账目：J = H_c = 3.65 N·m·s（150 kg 碎片 @3°/s，sim_06 锚点）
- 力偶力矩：τ = 2·F·l_T，l_T = 0.17 m
- 消旋时间：t = H_c / (2·F·l_T)
- 推进剂质量：m_p = H_c / (l_T·Isp·g0)，g0 = 9.80665 m/s²（scan_v0）
- 中间值：H_c/(l_T·g0) = 2189.39 g·s（即 m_p[g] = 2189.39 / Isp[s]）；H_c/(2·l_T) = 10.7353 N·s（即 t[s] = 10.7353 / F[N]）

| 候选 | 替换 assumptions.yaml 字段 | 替换值 | t_detumble 重算 | m_p 重算 |
|---|---|---|---|---|
| C1 B1 | thrusters.isp_s.green_biprop（新键） | Isp 248 s | F=0.49 N → 21.91 s；F=1.35 N → 7.95 s | 8.83 g |
| C2 B20 | 同上 | Isp 285 s | F=6.1 N → 1.76 s；F=18.11 N → 0.59 s | 7.68 g |
| C3 HPGP 1N | thrusters.isp_s.green_monoprop 220 → 实测带 | Isp 194–227 s | F=0.25 N → 42.94 s；F=1.0 N → 10.74 s | 9.65–11.29 g |
| C4 EPSS C1K | 同上 | Isp 213 s | F=0.22 N(EOL) → 48.80 s；F=1.0 N(BOL) → 10.74 s | 10.28 g |
| C5 MiPS | thrusters.isp_s.cold_gas 60 → 40；force_classes 增 0.010 档实测 | Isp 40 s, F=10 mN | 1073.53 s（<3600 s 门4 内） | 54.735 g（贴边 → UNKNOWN） |
| C6 CPOD8 | 同 C5 | Isp 40 s, F=10 mN | 1073.53 s（l_T=0.17 m 口径）；screen 口径（盒半径 0.085 m、12 mN 假设）1788.86 s | 54.735 g（贴边 → UNKNOWN） |
| C7 Moog | thrusters.isp_s.green_monoprop → 224 | Isp 224 s | F=0.1 N → 107.35 s；F=0.5 N → 21.47 s；F=1.0 N → 10.74 s | 9.77 g |
| C8 PBR-50 | isp NAMED_GAP | null | F=10 mN → 1073.53 s（仅时间可算） | UNKNOWN（Isp 缺失） |

注：C6 的两个时间口径差异来自力臂定义——screen 用目录盒半径 0.085 m（保守安装包络），本报告用 sim_08 冻结名义力臂 0.17 m；两口径均记录，不做调和。所有替换仅写入本报告与 JSON，**未改动 sim_08/sim_10/scan_v0.yaml/PROPULSION_RESOURCE_SCREEN.json 任何既有文件**。

## 5. 开放项（oem_icd_missing_fields）

1. CPOD8：command_min_width_s、双机并发指令 ICD（screen 冻结 null 字段）；
2. B1/B20：官方 PDF datasheet 的 Isp 与功耗分解（当前仅官网规格页+第三方目录值）；
3. HPGP 1N：12 mN 等效低推力占空比下的脉冲模式 Isp 衰减（公开数据为稳态）；
4. EPSS C1K：干重、双模块并发 ICD；
5. Moog：总冲量、并发能力、飞行heritage（TRL 3–4）；
6. PBR-50：Isp、总冲量、干重、12U 安装适配；
7. OEM 安装孔位定义（screen：OEM_mating_holes_defined=false 仍未闭合）；
8. 羽流撞击/捕获后组合体质心偏移对 l_T=0.17 m 假设的影响（sim_08 v0 limits 已声明）。

## 6. 结论

- **第一梯队（全判据 PASS）**：Dawn B1、Dawn B20、ECAPS HPGP 1N。三者均有公开飞行heritage宣称（引用见 §2），但**本项目级 hardware_qualification 仍为 false**——尚无候选完成面向本任务的鉴定/选型冻结。
- **第二梯队（PASS+UNKNOWN）**：NanoAvionics EPSS C1K（并发 ICD 缺口）。
- **实质排除**：VACCO MiPS / CPOD8（R134a，推力不足 12 mN 且推进剂贴边 UNKNOWN）；Pale Blue PBR-50（推力不足 + 包络超出）；Moog 模块（关键字段 UNKNOWN + 无heritage）。
- **mission_budget_closed = false 维持**：总冲量下限 42.9 N·s 来自目录盒假设（screen derivation 明示该假设未对安装候选成立），实际任务可行性 UNKNOWN 不变。
- 选型冻结、ICD 索取、sim_08 占位常数正式替换均需 owner 逐项授权。
