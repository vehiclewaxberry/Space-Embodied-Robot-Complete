# ROUTE_C_RFI_DECISION_PACKAGE_V1 — RFI-E/F/G 发放裁决包（Owner 一页裁决）

- schema 类标记：`ROUTE_C_RFI_DECISION_PACKAGE_V1`
- 生成时间：2026-08-23T20:15:00+08:00（宿主机本地钟，Asia/Shanghai）
- 作者：KIMI M7 机械终局接管 swarm 第三轮（R2 全柔性闭合 Wave-3a）CM 子代理
- 性质：**CANDIDATE / PROVISIONAL 裁决包草案**。`release_credit=false`、`next_stage_authorized=false`。本文件不发送任何 RFI、不选型、不产生受控值；是否发放由 Owner 裁决。
- 关联 open item：OI-R1-05（PROCUREMENT_RFI_GAP，HIGH，`STILL_HIGH__RFI_MEMO_RECORDED_GAP_OPEN`，PENDING_OWNER 保持）。
- 全部数字可复核：`round0_handover/02_route_c_inputs/ROUTE_C_PHYSICAL_INPUT_INVENTORY_V1.json`（sha256 `b91611f98376…`，summary：13 项盘点、0 AVAILABLE、13 HOLD、0 拓扑就绪）；`round1_bridge/route_c_prep/ROUTE_C_RFI_GAP_MEMO_V1.md`（sha256 `771dc8fcc4e4…`）。

## 1. 背景（三行）

1. Route-C 最小物理输入 13/13 全 null/HOLD：P10 导向摩擦候选、P11 导向曲率、P12 载体尺寸（另挂 P04 载体行程、P13 夹具间距、P05 制造坐标）均无候选源；8 个官方来源只有电缆/连接器，没有任何导向/载体/夹具硬件候选。
2. 既有 RFI shortlist 只覆盖 RFI-A..D（SpaceWire 数据线路、离散电源/控制、工程样件线）；RFI 决策门 `ROUTE_C_VENDOR_RFI_DECISION_GATE_V1.json` 维持 HOLD（RFI-G04 `HOLD_0_OF_8` 最小产品输入未受控、RFI-G05 `HOLD_PENDING` ODR-42 Owner 权威未裁决），其 `allowed_now` 已含"issue non-binding supplier RFIs for exact data and samples"——**发非约束性 RFI 本身在授权内，但扩围到硬件类别需 Owner 批准**。
3. 缺口备忘录（Wave-2a 已落盘）提出 RFI-E（微型电缆载体）/RFI-F（导向/衬垫材料对）/RFI-G（夹具/固定硬件）三项扩围提案，待 Owner 裁决。

## 2. 请 Owner 裁决的三件事（逐字引备忘录 §5）

1. 是否批准按备忘录 §3.1–3.3 发出 RFI-E/F/G（非约束性、可索取样件）；
2. RFI-E/F/G 的 vendor 类别清单是否需要先经一轮文献/市场检索补证再发；
3. P04（carrier_travel_mm）是否确认挂入 RFI-E（备忘录建议挂入）。

## 3. 发 / 不发的后果

| 选项 | 后果 |
|---|---|
| **批准发放** | 为 P12/P04（载体产品族尺寸系列/弯曲半径系列/单位长度质量/行程硬停）、P10（材料对摩擦/磨损/出气证据）、P13+P05（夹具产品族与安装设计规则）取得候选源；RFI 响应**永不单独闭合任何 MPI**（`evidence_class_non_equivalence`），目录值永不自动成为选定件；成本=供应商交互时间；不产生任何 CAD 权威含义。 |
| **不发放** | OI-R1-05 维持 HIGH 且无闭合路径；P10/P12（及挂载的 P04/P13/P05 输入侧）持续无候选源；Route-C MPI-06/07 不闭合、C-B（现 0/11 必需输入组受控）/C-C 维持 NOT_READY；2026-09-01 硬截止前 Route-C 物理车道整体停摆风险由 Owner 承担。 |

## 4. Route-C 解锁依赖链（RFI 在链中的位置）

```
RFI-E/F/G 响应（候选源入账，仍 HOLD 级、非选定）
  → 受控 CAD/ICD 分支内推导项目自有几何（P11 导向曲率、P13 夹具排布、P05 制造坐标）
      【前置：ODR-44 解除 = MPI-FB-01..08 全闭合 + Owner 正式并入 ODR-43/44 addendum】
  → MPI-06/07 闭合（物理输入受控）
  → C-B/C-C 拓扑就绪度重估（现 NOT_READY）
  → Route-C 独立版本化 CAD 候选（此前禁止）
```

明确不由 RFI 解决的项（备忘录 §3.4 逐字口径）：P11 只能来自受控 CAD 分支的命名有限导向体积（现 `guide_volumes_present=false`）；P13 排布依赖受控路径与接口基准；任何 MPI 闭合声明不得仅凭 RFI 响应/vendor BOM 作出。

## 5. 与 ODR-44 的关系

- RFI 是**纯文本/采购层动作**：不产生、不修改任何 CAD 候选，不触碰 accepted URDF/Solar R2 等冻结资产——发放 RFI 不违反 ODR-44。
- ODR-44 禁止的是"MPI-FB-01..08 全闭合前的 Route-C 独立版本化 CAD 候选"。MPI gate 现已 PASS（限域、工程级），但 CAD 入口仍**双重阻塞**（MPI_BRIDGE_GATE_V1.json `route_c_cad_entry=DOUBLY_BLOCKED` 逐字）：①ODR-43/44 addendum 的 Owner/CM 正式并入仍 pending；②C2-01 注册表骨架（`ROUTE_C_C2_01_REGISTRY_SKELETON_V1.yaml`）全 null/全 HOLD 无 AVAILABLE 项。
- 因此：RFI 发放与否**不影响** CAD 冻结状态；RFI 响应到位也**不解除** CAD 阻塞——两者是依赖链上前后相继的不同环节。

## 6. 签署区（Owner 裁决后生效）

| 裁决项 | 结论 |
|---|---|
| 事项 1：发放 RFI-E/F/G | ☐ 批准 / ☐ 不批准 / ☐ 部分（列明） |
| 事项 2：vendor 清单先补检索 | ☐ 需要 / ☐ 不需要 |
| 事项 3：P04 挂入 RFI-E | ☐ 确认 / ☐ 不挂 |
| Owner 签名 / 日期 | ____________________ |

裁决后动作：批准则按备忘录 §3 清单起草非约束性 RFI 文本（另件）；响应入账一律 HOLD 级登记、带 sha256；本包不授予任何 release credit。
