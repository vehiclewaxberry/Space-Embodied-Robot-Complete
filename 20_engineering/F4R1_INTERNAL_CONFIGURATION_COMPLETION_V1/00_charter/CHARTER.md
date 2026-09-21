---
title: F4R1 内部构型完善工作包章程（C 轨）
generated_at: 2026-08-27
status: DRAFT_PENDING_OWNER_SIGNOFF
scope: 赛后论文导向的机械设计完善（内部构型闭环 + 帆板参数成熟化）
---

# F4R1 内部构型完善工作包章程（C 轨）

## 1. 目的

为赛后论文撰写准备一套**自洽、可复核、与公开实践对标**的机械设计闭环：内部设备布局（解决"卫星空心"观感与质量模型零设备行问题）+ 帆板参数成熟化（解决占位参数论文硬伤）。C 轨不改变 2026-09-01 比赛提交的任何内容与口径（B 轨照旧，优先级最高）。

## 2. 范围

**IN（本包负责）**
- 内部设备布局方案：三舱（front_mission / mid_avionics / rear_service）owner 体积 → 设备级清单、包络、安装面、二级结构方案。
- 质量模型内部行填充：R2 质量账本当前**无任何内部设备行**（V2 台账 9 行 placeholder 全 UNKNOWN_BLOCKED）→ 填入有出处的设备质量并做 CDS 符合性裁决。
- 帆板参数三档包络（质量/刚度/阻尼/展开力矩 LOW-NOMINAL-HIGH）+ 占位参数真实性检验 + 灵敏度仿真方案。
- 论文素材：布局图、质量预算表、对标表、灵敏度结果。

**OUT（本包不负责）**
- 冻结基线 `MECHANICAL_ENGINEERING_RELEASE_R2/` 及 23 个哈希钉住文件的任何修改。
- Route-C 线束实物参数（P01–P13 为 BLOCKED_EXTERNAL，维持 HOLD）。
- 制造级/飞行级 CAD、结构强度校核、环境试验。
- 比赛提交包内容（C 轨产物在 9-01 前不得进入提交包，避免两套口径冲突）。

## 3. 治理

- 冻结区只读；C 轨新产物只写入 `20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/`。
- 里程碑 Gate（C1–C4）新建于本包内，**不回写父 Gate**；冻结证据链（accepted URDF、V3 R2 质量账本、sim/e 系列裁决）只引用、不修改。
- **2026-09-01 前禁止任何 CAD 建模**（C3 阶段须待提交后 + ODR 签署）。
- 任何与冻结口径不一致的新数值（如帆板质量线统一值）必须以「新候选 + 声明与冻结口径的差异」方式入账，禁止覆盖。

### ODR 提案（待 Owner 签署）

```text
ODR-F4R1-01（提案）：
1) 授权成立 F4R1 内部构型完善工作包，范围如本章程 §2；
2) MECHANICAL_MAIN_BODY=FROZEN 维持不变，本包内新装配仅允许"引用冻结接口、不修改冻结实体"；
3) C1/C2 阶段（布局方案、帆板参数包络）立即授权；C3 阶段（CAD 建模）须 2026-09-02 后另行签署生效；
4) C-ISS-01 质量口径裁决（31.02 kg vs CDS 24 kg）在 C1 出口前由 Owner 三选一：减重设计 / 论文口径声明（非 12U deployer 约束）/ 升级 ESPA 级平台；
5) C 轨产物标注 DESIGN_RESEARCH_CANDIDATE，不进入正式 SSOT，不获得 release credit。
```

## 4. 关键问题登记（C0 研究发现）

| ID | 问题 | 证据 | 严重度 | 处置阶段 |
|---|---|---|---|---|
| C-ISS-01 | **质量超限**：C01=31.0229 kg vs CubeSat CDS Rev14.1 12U 上限 24 kg（+29%） | B1 §CDS；`07_SYSTEM_MASS_PROPERTIES.yaml` | 高（论文"12U"表述合法性） | C1 出口前 Owner 裁决 |
| C-ISS-02 | **帆板质量双线**：sim_11 用 0.3483933 kg/板（隐含 7.67 kg/m²）vs R2 候选 0.78 kg/翼（3.0 kg/m² 未实测），差 2.24× | REPO_ASSET_INVENTORY；B3 | 高（论文一致性） | C2 统一口径或声明两模型用途 |
| C-ISS-03 | **刚度轴失真**（比质量更严重）：模态占位 f1=1.0 Hz、ζ=0.005 vs 公开实测展开态 f1≈8–20 Hz、ζ≈0.002–0.03，f1 低 8–20×；纠正 AGENTS.md 待办 3 的"质量 5–10×"表述（实际质量差 1.5–3.8×） | B3 §c/§e；`config/coupled_scene/` 占位字段 | 高（A1"柔性可忽略"结论可能翻转） | C2 三档灵敏度 |
| C-ISS-04 | 内部设备零行：R2 质量账本 9 构型无一行内部设备；V2 9 行 placeholder 全 UNKNOWN_BLOCKED | GAP_REGISTRY；V2 unknown register | 中 | C1 填值 |
| C-ISS-05 | T_SB frame 自 V2-UNK-004 未闭合（ODR-01 其余已冻结：T_SM=[185.25,0,0]mm+Ry90°、臂基座 x=208.0mm） | GAP_REGISTRY frame 行 | 中 | C1 |
| C-ISS-06 | CDS CG 要求 ±4.5/±4.5/±7 cm：臂基座已冻结，CG 调节只能靠内部配重布局 → 须用布局优化（MDPI 2025 GRASP+NSGA-III 五目标法可移植） | B1 §a/§e | 中 | C1 |
| C-ISS-07 | 轮组角动量容量全行业不公开（B2）：论文 H_available 标定无外部基准，须自有设计值+裕度自证 | B2 §启示 | 中（论文方法节） | C4 |
| C-ISS-08 | COTS 普遍不公布展开频率/阻尼/铰链力矩：帆板论文参数须靠检验公式+三档包络自证 | B3 §f | 中 | C2 |

## 5. C0 已交付研究资产（2026-08-27）

- `10_benchmark/B1_12U_INTERNAL_STRUCTURE_AND_EQUIPMENT_BENCHMARK.md`（39.6 KB）：CDS Rev14.1 硬约束、设备质量/包络数据表、推进选项、布局优化方法、14 条设计规则。
- `10_benchmark/B2_SERVICING_CAPTURE_SPACECRAFT_BENCHMARK.md`（41.9 KB）：9+2 个在轨服务任务对标；确认空档——非合作抓捕无在轨成功案例、安全层均为程序性 FDIR，「策略选择层可机器裁决的 fail-closed 门控」在微纳量级无先例（论文 related-work 定位依据）。
- `10_benchmark/B3_DEPLOYABLE_SOLAR_ARRAY_BENCHMARK.md`：面密度 PCB 基 3.4–5.0 / 蜂窝 2–3.5 kg/m²、比功率 30–135 W/kg、展开 f1 实测 8 Hz、阻尼 0.2–3%、力矩裕度 ≥2×；占位真实性检验公式；三档参数集建议。
- `20_repo_assets/REPO_ASSET_INVENTORY.md`：五区资产盘点与复用评级（三舱 owner 登记、V2 质量台账 9 placeholder 行、IF-AV-001/IF-SV-001 接口壳、R2 三叶帆板+七模态 ROM 均可复用，无需从零建格式）。
- `30_gap_registry/GAP_REGISTRY.csv`：19 行缺口登记（12 pre_paper / 7 post_paper），证据路径全部核验存在。

## 6. 与 B 轨的关系

B 轨（`90_competition_closeout/` 五日收口计划）优先级绝对最高；C 轨在 9-01 前只运行 C0（文档）。C 轨人员/算力不得挤占 P0 四项（官方要求确认、报告母稿、claim 冻结、git 锚定+仓库安全）。若 C 轨发现可用于比赛的材料（如 B2 的行业空档确认），须经 B 轨 claim 冻结流程审核后方可进入提交材料。
