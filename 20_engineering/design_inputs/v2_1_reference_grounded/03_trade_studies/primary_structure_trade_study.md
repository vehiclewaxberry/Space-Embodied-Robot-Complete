# V2.1 主结构 Trade Study（B4-0 冻结稿）

> `PHASE: B4-0`　`FEA: NOT_AUTHORIZED`（一切表述为 LOAD_PATH_INTENT 意图级）
> `SELECTED_REFERENCE: PS-C04_HYBRID_FRAME_LONGERON_LOCAL_SPREADERS`
> 依据：`05_adversarial_review/adversarial_design_record.yaml`（Chair 裁定）、
> `01_source_admission/source_admission_manifest.yaml`、`02_feature_adoption/` 矩阵

## 1. 候选比较

本表为概念拓扑与维护语义比较，不是强度、刚度、模态或质量评分。

| ID | 拓扑 | B601 载荷路径可读性 | 翼根隔离 | 三舱/维护 | V2.0 最小偏差 | 处置 |
|---|---|---|---|---|---|---|
| PS-C01 | 继承四框四纵梁开放笼架 | PARTIAL | PARTIAL | PASS | PASS | 作为最小基线保留 |
| PS-C02 | 可拆面板参与承载的半硬壳 | PARTIAL | PARTIAL | FAIL | PARTIAL | REJECT；会把维护面板并入主路径，且缺少面板接头/材料/剪切证据 |
| PS-C03 | 中央主脊 + 横隔框 | PASS | PARTIAL | PARTIAL | FAIL/PARTIAL | DEFER；与设备/线束空间竞争且改动基线较大 |
| PS-C04 | 框—纵梁混合主结构 + B601/翼根局部扩散节点 | PASS | PASS（拓扑级） | PASS | PASS | **SELECTED / CONDITIONAL** |

## 2. 冻结方案

**混合框架拓扑继承 V2.0 不变**：前端框(+170.25) + MID1(+56.75) + MID2(-56.75) +
后端框(-170.25) + 四角纵梁 + 两甲板 + 六可拆面板。V2.1 增量是**承载语义申明**而非拓扑
重构（PS-01，OreSat 端框-纵梁-卡笼组织原则）。

- **PS-02（FREEZE）四角纵梁=唯一轴向集中载荷通道**：一切集中载荷只许经机加节点件
  汇入纵梁（CDS 导轨承载原则的组织级移植，数值零继承）。
- **PS-06（FREEZE）节点唯一交换原则**：臂链/翼根链/地面支持链之间只在机加节点件
  交汇；薄壁共享区无合法定义。
- **PS-03（FREEZE_WITH_C1_RULING）B601 载荷扩散链**：boss→160 适配板（唯一可换牺牲件，
  B601 零重构）→前端框整周环支承+四角节点栓接（双路径）→角撑→四纵梁→MID1 收口。
  C1 人工裁决要求 LOAD_PATH_INTENT 构件的每个开口逐项登记 `doubler-intent + owner + 对抗复审`，
  与载荷链同包发布；这只是开口语义，不是开孔实体或强度批准。
- **PS-04（FREEZE_WITH_C2_RULING）翼根独立支座**：证据归宿=MID2 框（翼根冻结坐标 X=-56.75
  与 FRAME_MID2_X 逐位重合）；独立支座、基准只绑框站位、禁与面板配合、禁纵梁背衬直搭。
  C2 人工裁决选择 MID2 框 ±Y 节点垫；需要后向支撑时只允许经同一节点机制在 REAR 框加辅垫，
  禁止框腹板中跨和新增桥带。
- **PS-05（FREEZE_WITH_C1_RULING）语义五类三层落地**：命名前缀+STRUCT_CLASS 属性 /
  v2_1_structure_semantic_register.yaml / gate 校验。规则 1、3 冻结；规则 2
  按 C1 扩展为 LOAD_PATH_INTENT 开口的逐件受控通道。
- **PS-07（FREEZE_WITH_C3_RULING）面板统一安装合同**：拆装零扰动载荷路径；±Y 侧板
  在 MID1 站位 X=+56.75 分前/后段，前段任意翼态可拆，后段只在 DEPLOYED/SERVICE 可拆；
  分缝落框缘且全部为 NON_STRUCTURAL_PANEL。

## 3. 人工裁决状态

| ID | 裁决 | 状态 | B4-1 影响 |
|---|---|---|---|
| C1 | LOAD_PATH_INTENT 构件开口逐项走规则3；甲板不整类豁免 | RESOLVED_BY_HUMAN | 只允许 named opening/doubler intent；物理开孔仍 HOLD |
| C2 | MID2 ±Y 节点垫；必要时 REAR 同机制辅垫；驳回新增桥带 | RESOLVED_BY_HUMAN | 支撑零实体 reference 与节点垫实体 |
| C3 | ±Y 面板在 MID1 分段；前段全态可拆，后段仅 DEPLOYED/SERVICE | RESOLVED_BY_HUMAN | 分段板实体与服务语义 |
| C4 | HDRM 只许 MID2+REAR，禁止 MID1 | RESOLVED_BY_HUMAN | HDRM 仍 named-only UNKNOWN |
| C5 | 收拢叠厚 238.3>226.3 与翼尖约 ±313 的包络语义 | OPEN_OWNER_DECISION | named-only 表达先行；所有部署器/发射包络声明 HOLD |

## 4. 硬阻塞（H1–H9 摘要）

V2-UNK-001 不闭环（H1）；无 FEA 即无结构结论（H2）；五源数值防火墙（H3）；
外部几何零血缘+B601 禁顺手优化（H4）；八个 named-only UNKNOWN 执法（H5）；
载荷链与开口分配必须同包（H6，C1 已裁决但物理开孔未授权）；收拢拓扑声明已由人工记录（H7）；
质量 SSOT 保护——帆板 0.348kg
占位是项目最高优先级硬伤（H8）；SpeedPak 干涉纪律（H9）。
全文见 adversarial_design_record.yaml。

## 5. B4-1 验收候选

A1–A20（语义登记/参数账本/黑名单数值 lint/零血缘三层断言/许可登记/claim 防火墙/
UNKNOWN 完整性/keepout 家族/状态×SpeedPak 组合表/MR 系列维护验收）已入
adversarial_design_record.yaml，B4-1 入口 Gate 引用之。
