# 结构文档获取清单

本文件是准入队列，不是数值来源。所有条目在下载、版本核验、哈希登记、适用性裁决和人工签署完成前一律为 `BLOCKED`；网页搜索命中或仓库中存在旧副本都不等于“文档到手”。

## 强制外部文档

### DOC-CDS-01 — Cal Poly CubeSat Design Specification 当前修订版

- 状态：`BLOCKED`
- 需要关闭的字段：12U 包络、质量上限、质心包络、导轨/凸耳与部署器接口、部署抑制要求。
- 官方候选入口：[Cal Poly CubeSat Information](https://www.cubesat.org/cubesatinfo)。
- 当前观察：官方页面指向 1U–12U 的 Rev.14.1；本仓库旧 Rev.14.1 副本不自动获得本轨道准入。
- 到手判据：从官方入口重新取得文件；记录修订、发布日期、页数、SHA-256、URL、获取日期；人工复核 12U 图纸页；确认是否被所选发射服务商覆盖或取代。
- 数值策略：全部 `PLACEHOLDER`。

### DOC-DEP-01 — 所选 12U 部署器与适配器 ICD

- 状态：`BLOCKED`
- 需要关闭的字段：rail/tab/CSD 选型、接口边界、预载荷路径、包络、质量/质心限制、载荷、刚度和收拢构型一阶模态要求。
- 官方候选入口：
  - [Rocket Lab / PSC 2002367F 3U/6U/12U CSD Payload Specification](https://www.rocketlabusa.com/assets/Uploads/PSC/Rocket%20Lab%20PSC%20-%202002367F%20Payload%20Spec%20for%203U%206U%2012U.pdf)
  - [Rocket Lab ASD payload-spec addendum](https://www.rocketlabusa.com/assets/Uploads/2004630-ASD-Payload-Spec-Addendum3.pdf)
  - [Moog ESPA User’s Guide](https://www.moog.com/content/dam/moog/literature/sdg/space/structures/moog-espa-users-guide-datasheet.pdf)
- 适用性警告：CSD、ASD 与 ESPA 类接口不是同一约束系统；必须先选择实际任务接口，禁止拼接最有利条款。
- 到手判据：选定一个任务级接口；取得供应商当前受控版和 mission-specific ICD；登记 SHA-256；由结构/总体 owner 签署。
- 数值策略：一阶模态、刚度、接口载荷和边界全部 `PLACEHOLDER`。

### DOC-ENV-01 — 发射环境与任务级裁剪

- 状态：`BLOCKED`
- 需要关闭的字段：准静态载荷、随机振动 PSD、正弦振动、冲击、持续时间、方向、组合和安全系数。
- 官方候选入口：[NASA GSFC-STD-7000 GEVS](https://standards.nasa.gov/standard/gsfc/gsfc-std-7000)。
- 当前观察：NASA 标准页列出 GSFC-STD-7000B 为 active；它仍不能替代具体任务/发射服务商的裁剪载荷。
- 到手判据：归档标准 PDF 和任务级环境/接口控制文件；登记版本、SHA-256 和适用层级；由载荷 owner 输出已签署 load-case 表。
- 数值策略：全部 `PLACEHOLDER`。

### DOC-MAT-01 — 6061-T6 / 7075 设计许用值

- 状态：`BLOCKED`
- 需要关闭的字段：具体合金、状态、产品形态、方向性、A/B/S basis、温度降额、疲劳/断裂与批次材料证明。
- 官方候选入口：[MMPDS](https://www.mmpds.org/)。
- 当前观察：官方站点公告 MMPDS-2026 已发布；本轮未获得受控正文或项目授权副本。
- 到手判据：取得授权版本；按实际材料采购规范和产品形态选择表项；记录页级定位与材料证书要求。
- 数值策略：全部 `PLACEHOLDER`。

### DOC-SURF-01 — 铝合金阳极氧化

- 状态：`BLOCKED`
- 需要关闭的字段：涂层类型、等级、厚度、封闭、尺寸补偿、接触/接地面掩膜和检验。
- 官方候选入口：[DLA ASSIST MIL-PRF-8625](https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=7074)。
- 到手判据：取得 active 受控版；由材料/工艺 owner 结合导轨或凸耳接口 ICD 选择工艺；输出图纸注释和检验要求。
- 数值策略：全部 `PLACEHOLDER`。

### DOC-MP-01 — 航天材料与禁用镀层

- 状态：`BLOCKED`
- 需要关闭的字段：禁限用材料/镀层、相容性、真空污染、异种金属和工艺控制。
- 官方候选入口：[NASA-STD-6016](https://standards.nasa.gov/standard/nasa/nasa-std-6016)。
- 当前观察：NASA 标准页列出 NASA-STD-6016C with Change 1 为 active；仍需任务级材料与工艺控制计划裁剪。
- 到手判据：取得受控正文，建立项目 prohibited/restricted materials 清单并由 M&P owner 签署。
- 数值策略：不从网页摘要摘录禁用条款；本轮仅登记入口。

### DOC-OUT-01 — 出气与非金属材料

- 状态：`BLOCKED`
- 需要关闭的字段：试验方法、TML/CVCM/WVR 判据、胶黏剂/线束/润滑剂/垫片的具体批次结果。
- 官方候选入口：
  - [NASA Outgassing Database](https://outgassing.nasa.gov/)
  - [NASA outgassing method description](https://outgassing.nasa.gov/Description)
- 到手判据：取得适用 ASTM E595 受控版；对每个实际非金属材料记录厂家、料号、批次、数据库/试验记录和适用温度。
- 数值策略：全部 `PLACEHOLDER`。

## BOM 与接口追加文档

### DOC-B601-ICD-01 — B601 基座机械接口

- 状态：`BLOCKED`
- 必需字段：孔数、孔位/孔圆、螺纹、定位销、平面度、允许载荷、接地、连接器、安装/拆卸工具空间。
- 当前影响：`INTERFACE_ARM_BUS.yaml` 的全部物理连接字段保持 `PLACEHOLDER`。

### DOC-RW-01 — 反作用轮选型数据

- 状态：`BLOCKED`
- 必需字段：单轮与轮组质量、安装方向、惯量、角动量容量、最大/连续力矩、转速、功耗、振动和寿命。
- 当前影响：角动量预算的输入端未闭合；旧仿真档位不得转入 BOM。

### DOC-HDRM-01 — 机械臂发射保持与释放机构

- 状态：`BLOCKED`
- 必需字段：产品类型、保持载荷、刚度、预紧、释放冲击、释放时间、冗余、循环寿命、温度/真空资格和失效模式。
- 当前影响：分离螺母仅为 `DESIGN_ONLY` 候选，不是选型。

### DOC-FASTENER-01 — 紧固件与力矩表

- 状态：`BLOCKED`
- 必需字段：规格、等级、表面处理、润滑状态、扭矩—预紧关系、锁紧方式、重复使用限制、见证标记和工具校准。
- 当前影响：AIT 中所有紧固力矩保持 `PLACEHOLDER`。

### DOC-HARNESS-01 — 连接器与线束 ICD

- 状态：`BLOCKED`
- 必需字段：连接器料号、键位、锁紧、插拔顺序、最小弯曲半径、应力释放、屏蔽/接地、活动关节寿命和 RBF 清单。

## 统一准入记录

每份文档到手后必须登记：

```text
document_id
title
revision
publisher
official_url_or_controlled_delivery
acquired_on
page_count
sha256
applicability
supersedes
page_or_section_locators
owner
admission_status
```

只有 `admission_status=ADMITTED_FOR_KB_B_02` 的文档才能替换 `PLACEHOLDER`。替换后必须同步重算 BOM、质量/质心/惯量、角动量预算、GJM 输入、载荷工况和模态门。
