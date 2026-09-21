# ROUTE_C_RFI_EFG_ISSUANCE_V1 — RFI-E/F/G 发放登记（人读版）

- schema：`ROUTE_C_RFI_EFG_ISSUANCE_V1`（机器版：同目录 `ROUTE_C_RFI_EFG_ISSUANCE_V1.yaml`，冲突时以 YAML 结构化字段为准）
- 生成时间：2026-08-23T20:45:14+08:00（宿主机本地时钟，Asia/Shanghai）
- 作者：KIMI M7 机械终局接管 swarm Wave-4a（ODR-45..49 owner decisions + R2 full-flex closure）— AGENT-A3
- 状态：**ISSUED_PER_ODR46**；`next_stage_authorized=false`、`release_credit=false`
- Owner 权威来源：`00_authority/M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml`（sha256 `69473bc19e020c6422b23c1758cfc343874f641781c9782e982036614c0849b5`）

## 1. 授权依据（两行）

1. ODR-46 逐字裁决："ISSUE RFI-E, RFI-F and RFI-G using the already prepared scoped RFI definitions. Route-C remains FROZEN_PENDING_PHYSICAL_AUTHORITY."——发放范围 = 缺口备忘录 §3.1–3.3（`ROUTE_C_RFI_GAP_MEMO_V1.md`，sha256 `771dc8fcc4e448bfd007951d4d623c6ebaab7440730a94a635dabd06bd2ca74e`）。
2. 既有 RFI 决策门 `ROUTE_C_VENDOR_RFI_DECISION_GATE_V1.json` 的 `allowed_now` 本就含"issue non-binding supplier RFIs for exact data and samples"；扩围到导向/载体/夹具硬件类别的 Owner 批准由 ODR-46 给出。决策包三事项：事项 1 批准发放；事项 3 确认 P04 挂入 RFI-E；事项 2 未强制要求发放前补检索（按已定界范围直接发出）。

## 2. 三张 RFI 一览（均：非约束性、可在授权范围内索取样件、状态 ISSUED__NO_RESPONSE_RECEIVED）

| RFI | 目标 | 覆盖字段 | 核心提问域（范围逐字出自备忘录 §3.1–3.3） |
|-----|------|----------|--------------------------------------------|
| RFI-E | 微型电缆载体 / 能量链 | P12 carrier_size_mm、P04 carrier_travel_mm | 产品族与尺寸系列（内腔截面高×宽、链节节距、弯曲半径系列）；行程/吊装能力与硬停定义；单位长度质量与链节材料；温度范围；真空出气 TML/CVCM；磨损/颗粒物与声明工况下动态循环寿命；ETFE 护套相容性 |
| RFI-F | 导向/衬垫材料对 | P10 guide_friction_candidate | 材料对逐对命名（禁泛称）；静/动摩擦系数（温度/真空工况声明）；磨损率与颗粒物证据；出气 TML/CVCM；辐照耐受与干润滑状态 |
| RFI-G | 夹具/固定硬件 | P13 clamp_spacing_mm、P05 manufacturing_coordinates_mm（仅夹具接口输入） | 夹具产品族与夹持直径范围、夹具质量、紧固件接口；供应商间距/安装设计规则；缓冲/衬垫材料+温度+出气；NASA-STD-8739.4A 类工艺符合性（allowed_use 限工艺/安装/检验规划，不作尺寸权威） |

- 可接受证据类（三 RFI 共通）：manufacturer datasheet / vendor application note / traceable catalogue data / peer-reviewed or public engineering source / existing project test evidence。
- 禁用来源：LLM guessed value / generic web article / unsourced engineering rule-of-thumb。
- **命名冲突警示**：RFI-G（本硬件 RFI）与 `ROUTE_C_VENDOR_RFI_DECISION_GATE_V1.json` 门判据 ID RFI-G01..RFI-G08 无任何关系，禁止互相绑定。

## 3. 响应纪律（response_rules，逐字入 YAML）

1. 目录值永不在无精确件号 + Owner 批准时成为项目选定硬件；
2. RFI 响应永不单独闭合 MPI 行（evidence_class_non_equivalence）；
3. 有可溯源来源时字段可 null→CANDIDATE_RANGE 升级；CANDIDATE_RANGE ≠ AVAILABLE；无源保持显式 null，禁止压 0；
4. AVAILABLE 仍需"受控值 + 单位 + 公差/不确定度 + 出处"；
5. RFI-A..D 既有条目与 RFI-D 飞行排除规则不变；
6. 响应入账一律 HOLD 级、带 sha256，经 CM 注册后方可触发重估。

## 4. 明确不由 RFI 解决（备忘录 §3.4 口径）

- **P11 guide_curvature**：项目自有几何，只能来自受控 CAD 分支的命名有限导向体积（现 `guide_volumes_present=false`）；
- **P13 clamp_spacing_mm**：排布依赖受控路径与接口基准（P05 未闭合）；Route-B 派生夹具候选已隔离，禁止继承；
- **任何 MPI 闭合声明**：不得仅凭 RFI 响应 / vendor BOM / readme。

## 5. 发放记录与缺口状态（平实声明）

- 发放已记录；**未收到任何响应；未向 C2-01 注册表填入任何值；未升级任何字段**；注册表保持 13/13 HOLD、0 AVAILABLE。
- **OI-R1-05 保持 HIGH OPEN，不自我降级**。供 CM 刷新用状态文本：`RFI_ISSUED_PER_ODR46__GAP_REMAINS_OPEN_HIGH`（原 `STILL_HIGH__RFI_MEMO_RECORDED_GAP_OPEN` 的后续态）。OPEN_ITEMS 寄存器改写保留给后续波次 CM 代理，本代理不触碰。
- `route_c_status: FROZEN_PENDING_PHYSICAL_AUTHORITY`（ODR-46 铸造），前向工作以此取代旧 `gate_state HOLD__AWAITING_MPI_GATE`；历史文件一字不改。
- CAD 禁令逐字口径：C2-01 注册表 13 个物理能力字段任一为 null，即禁止生成任何 Route-C CAD；准入门 = `ROUTE_C_C2_ADMISSION_GATE`（定义与同轮评估见同目录 `ROUTE_C_C2_ADMISSION_GATE_V1.yaml/.md`）。

## 6. 哈希与验证

全部引用钉在 YAML `verification_record` / `evidence_links`（sha256 over raw bytes，完整 64-hex 小写，签发时逐一重算；round0 盘点复算结果与登记钉 `b91611f9…353b7` 一致）。本文件对自身哈希适用 SELF_REFERENCE_EXCLUDED 政策（同 e21/V5 manifest 与 02_bridge），下游消费者在签发后钉入。

`next_stage_authorized: false`；`release_credit: false`；候选 ≠ 权威；test PASS ≠ gate PASS。
