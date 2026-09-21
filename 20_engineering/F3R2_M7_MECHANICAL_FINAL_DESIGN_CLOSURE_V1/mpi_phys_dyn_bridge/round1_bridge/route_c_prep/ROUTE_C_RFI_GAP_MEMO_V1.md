# ROUTE_C_RFI_GAP_MEMO_V1 — Route-C RFI 缺口备忘录（导向/载体/夹具硬件扩围提案）

- 生成时间：2026-08-23T17:22:11+08:00（宿主机本地时钟，Asia/Shanghai）
- 作者：AGENT-2（Wave-2a Route-C 文本准备）
- 配套机器文件：同目录 `ROUTE_C_C2_01_REGISTRY_SKELETON_V1.yaml`（13 项注册表骨架）
- 唯一输入：`round0_handover/02_route_c_inputs/ROUTE_C_PHYSICAL_INPUT_INVENTORY_V1.json`（sha256 `b91611f9837641a0bf1bbf555534b2d87eb2a5005fde06ef04b3cdd3374353b7`）
- 性质：**缺口识别与 RFI 扩围提案**。本备忘录不发送任何 RFI、不选型、不产生任何受控值；是否发 RFI 由 Owner 裁决。

## 1. 授权与边界

- ODR-43 / ODR-44 纪律不变：MPI-01..MPI-08 全闭合前禁止 Route-C 独立版本 CAD；本备忘录纯文本。
- RFI 决策门 `ROUTE_C_VENDOR_RFI_DECISION_GATE_V1.json` 的 `allowed_now` 已含 "issue non-binding supplier RFIs for exact data and samples"，因此**发非约束性 RFI 本身在授权内**；但现有 shortlist 的覆盖范围不含本备忘录所列硬件类别，需要 Owner 批准扩围。
- 现有 RFI shortlist（`ROUTE_C_VENDOR_RFI_SHORTLIST_V1.json`）只覆盖电缆与连接器：RFI-A/B（SpaceWire 数据线路）、RFI-C（离散电源/控制）、RFI-D（工程样件线，已排除飞行候选）。8 个官方来源中**没有任何导向（guide/liner）、载体（carrier）、夹具（clamp）硬件候选**。
- fail-closed 纪律：RFI 响应永不单独闭合 MPI（`evidence_class_non_equivalence`）；目录值永不自动成为项目选定件；null 不压 0。

## 2. 缺口定义（P10–P13，另挂 P04）

| ID | 量 | round0 状态 | 缺口性质 |
|----|----|------------|----------|
| P10 | guide_friction_candidate | HOLD，无候选源 | **vendor 可答**：材料对 + 摩擦/磨损证据 |
| P11 | guide_curvature | HOLD，无物理导向体积 | **vendor 不可直接答**：项目自有几何，需受控 CAD/ICD；vendor 只能提供产品几何约束输入 |
| P12 | carrier_size_mm | HOLD，无候选源 | **vendor 可答**：载体产品族尺寸系列/弯曲半径系列/单位长度质量 |
| P13 | clamp_spacing_mm | HOLD，无候选源 | **vendor 不可直接答**：项目自有排布，需受控路径与接口基准；vendor 只能提供夹具产品与设计规则输入 |
| P04 | carrier_travel_mm | HOLD，无候选源 | 挂载项：与 P12 同属载体硬件，行程/硬停位置需同一 RFI 覆盖 |

任务书原文点名 P10–P12 加 clamp spacing（即 P13）。P04 与 P12 共享同一载体硬件来源，在此一并登记，避免载体 RFI 发出后行程字段仍无源。

## 3. RFI 扩围需求清单（提案，待 Owner 裁决）

### 3.1 RFI-E（提案）：微型电缆载体（mini cable-carrier / energy chain）

- 目的：为 P12（载体尺寸）、P04（载体行程与硬停）取得候选源。
- 需要的参数项：
  1. 产品族与尺寸系列：内腔截面（高×宽，mm）、链节节距、可选弯曲半径系列（mm）；
  2. 每尺寸对应的行程/吊装能力、硬停定义方式；
  3. 单位长度质量（g/m）与链节材料；
  4. 温度范围、真空出气（TML/CVCM 或等效筛选声明）；
  5. 磨损/颗粒物数据、声明测试工况（半径/速率/循环数）下的动态循环寿命；
  6. 与所选线束护套（ETFE 类，见现有 shortlist 电缆）的相容性声明。
- 建议 vendor 类别（示例非选型）：①微型工程塑料拖链/能量链制造商；②已有航天电缆供应商的载体/走线附件线；③有航天机构应用记录的机构件供应商。
- 所需证据形式：供应商受控版次的数据表（带单位与公差）；声明工况下的动态弯折/磨损试验报告；出气试验报告或等效声明；可索取样件做台架实测（在 `allowed_now` 范围内）。

### 3.2 RFI-F（提案）：导向/衬垫材料对（guide/liner material pair）

- 目的：为 P10（导向摩擦候选）取得候选源。
- 需要的参数项：
  1. 材料对标识：导向/衬垫材料 × 线束护套材料（逐对命名，禁泛称）；
  2. 静/动摩擦系数，温度与真空工况声明；
  3. 磨损率与颗粒物生成证据（试验工况须声明）；
  4. 出气数据（TML/CVCM）或等效低出气筛选声明；
  5. 辐照耐受（如适用）与干润滑/无润滑状态声明。
- 建议 vendor 类别（示例非选型）：①航天电缆护套供应商（现有 shortlist 的 Gore/Axon/TE 线）配套的导向/衬垫方案；②低摩擦聚合物衬垫/导向件供应商；③干膜润滑/表面涂层供应商。
- 所需证据形式：同 3.1；材料对级别的摩擦/磨损试验记录优先于单材料目录页。

### 3.3 RFI-G（提案）：夹具/固定硬件（clamp / fastening hardware）

- 目的：为 P13（夹具间距排布）与 P05（制造坐标中的夹具接口）提供产品与设计规则输入。
- 需要的参数项：
  1. 夹具产品族与夹持直径范围、夹具质量、紧固件接口；
  2. 供应商的夹具间距/安装设计规则或安装指南（如有）；
  3. 缓冲/衬垫材料、温度范围、出气数据；
  4. 与 NASA-STD-8739.4A 类工艺口径的符合性说明（该标准在 preliminary contract 中已列为方法类官方来源，allowed_use 限于工艺/安装/检验规划，不作项目尺寸权威）。
- 建议 vendor 类别（示例非选型）：①航天线束夹具/卡箍供应商；②现有连接器供应商（Glenair/Omnetics/Axon）的尾附件与夹持附件线；③符合航天工艺标准的通用紧固硬件类别。
- 所需证据形式：受控数据表 + 安装指南文档版本；不含项目自有几何。

### 3.4 明确不由 RFI 解决的项

- **P11 guide_curvature**：导向曲率是项目自有物理几何，只能来自受控 CAD 分支中的命名有限导向体积（当前 `guide_volumes_present=false`）；RFI 至多提供产品几何约束（如载体弯曲半径系列、导向轮廓限制）供工程推导使用。
- **P13 clamp_spacing_mm**：夹具间距排布依赖受控路径与接口基准（P05 未闭合）；Route-B 派生夹具候选已随被拒路线隔离，禁止继承。
- **任何 MPI 闭合声明**：均不得仅凭 RFI 响应、vendor BOM/readme 作出（MPI gate `evidence_class_non_equivalence`）。

## 4. 与现有 shortlist 的关系

- 本扩围提案**不修改** RFI-A..D 的既有条目与状态；RFI-D 工程样件线的飞行排除规则维持不变。
- 扩围项全部沿用同一决策不变量：目录族数据永不在无精确件号与 Owner 批准时成为项目选定硬件；目录弯曲半径非动态寿命证据；组件电缆 OD/质量非安装束 OD/质量；null 不确定度保持 UNKNOWN。

## 5. 决策请求（供 Owner 裁决）

1. 是否批准按 §3.1–3.3 发出 RFI-E/F/G（非约束性、可索取样件）；
2. RFI-E/F/G 的 vendor 类别清单是否需要先经一轮文献/市场检索补证再发；
3. P04 是否确认挂入 RFI-E（本备忘录建议挂入）。

本备忘录自身不触发任何 RFI 动作；`gate_state` 维持 `HOLD__AWAITING_MPI_GATE`，`next_stage_authorized = false`。
