---
title: F4R1 C1 布局 2D 图纸包说明 (LAYOUT_DRAWINGS_README)
generated_at: 2026-08-27
status: DESIGN_RESEARCH_CANDIDATE
data_sources:
  - "EQUIPMENT_LIST_V1.yaml (sha256_12 2f6b5163f5f5)"
  - "MASS_BUDGET_V1.csv (sha256_12 365c9ebf9493)"
  - "CG_INERTIA_CHECK_V1.json (sha256_12 c7759162f54d)"
---

# F4R1 C1 布局 2D 图纸包说明

本包为 F4R1 工作包 C1 阶段 2D 布局图，**全部由脚本生成、可复算**。状态 `DESIGN_RESEARCH_CANDIDATE`。

## 1. 交付清单与视图定义

| 文件 | 视图 | 内容 |
|---|---|---|
| `render_layout_svg.py` | — | 渲染脚本（仅 Python 标准库；YAML 用内置定向行解析器，不依赖 pyyaml，见脚本头注释） |
| `LAYOUT_SIDE_VIEW_V1.svg` | 侧视图 = **x–z 平面**（从 −y 侧向 +y 看入）：屏幕右 = +x，上 = +z | 12U 外廓、三舱分界与 x 范围、36 行几何设备色块 + 4 行 distributed 背景阴影、臂基座 x=208.0 标记线、三场景 CG 标记、CDS CG 包络框、+x/+z 方向标、比例尺、图例 |
| `LAYOUT_FRONT_VIEW_V1.svg` | 前视图 = **y–z 平面**（从 +x 任务端向 −x 看入）：右手系下屏幕右 = +y，上 = +z | 226.3×226.3 外廓、臂基座安装区（M3R+BRIDGE+F/T 同心块）、帆板根部菱形标记与展开 CG 投影 ×、中舱设备投影、图例 |
| `LAYOUT_BAY_MASS_V1.svg` | 三舱质量分配条形图 | DESIGN_POINT（读法 A，FRZ-* 按声明 bay 聚合）与 CDS_VARIANT（除 FRZ-BUS 外全部行 + 15% 余量段）两口径并排；段 = bay，标注 kg 与占比；CDS 24.00 kg 参考虚线 |

**侧视图平面选择理由**：三舱分界面均为 x=常数平面、臂基座站位 x=208.0 为 x 轴事实，x–y 与 x–z 表达能力等价；但帆板/B601 的 C01 CG 在 y 向达 ±346.6/−175.7 mm（超出 226.3 外包络），x–y 平面会严重压缩总线比例，故选 x–z。代价（已知局限）：左右帆板在 x–z 投影重合、B601 的 y 向偏置在侧视图不可见——两者由前视图表达。

## 2. 坐标映射与生成规则

- S frame：原点 = 12U 几何中心，x = 纵轴（任务/臂方向为正），单位 mm；全部坐标直接取自行内 `pos_mm`/`envelope_mm`。
- 像素映射：`px = (mm − min_mm) × PX_PER_MM + margin`，z 向取反；比例常数（侧视 1.6 px/mm、前视 1.8 px/mm）在脚本头部常量区。
- 状态线型：FROZEN_REF = 虚线灰、CANDIDATE = 实线蓝、ASSUMED = 点线橙（图例在每张图右上）。
- 设备标签 = `id + 质量(g)`；格式规则：质量/坐标 `%.6g`，占比 `%.1f%%`，CDS 限值 `%.2f`——**脚本内禁止手填工程数字**。
- 两个无结构化字段的 frame 事实由脚本从源文件文本正则提取：臂基座 x=208.0（FRZ-B601 `notes`/`mounting_face`）、CDS 现行标准 366.0 mm（yaml `bus_length_note`）；提取失败即报错中止，不回退手填。
- 每行设备在 SVG 中携带 `data-id / data-bay / data-status / data-mass_g / data-pos_mm / data-envelope_mm`（全精度源值），供机器审计“图上数字 = 源文件数字”。
- 质量条形图聚合口径：DESIGN_POINT = 全部 FRZ-* 行（读法 A，EQ 设备分摊于 FRZ-BUS 块内不加法，聚合和与 CSV `TOTAL-DESIGN-POINT` 校验差 <1e-9 否则中止）；CDS_VARIANT = 除 FRZ-BUS 外全部行（与 CSV `TOTAL-CDS-VARIANT` 同法校验）；余量段 = CSV `MARGIN-CDS-15PCT`；占比 = 段质量/该口径干重。

## 3. 复算方法

```
cd 20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/50_c1_layout
python render_layout_svg.py
```

- 输出三张 SVG（覆盖写），并向 stdout 打印 JSON 报告：输入 sha256_12、行计数、跳过登记、提取的臂基座 x、yaml↔csv 质量交叉核对。
- 确定性：`generated_at=2026-08-27` 为固定字面量，无时间戳/随机性；连续两次运行输出逐字节一致（已用 sha256 校验）。

## 4. 跳过/特殊处理登记（自检要求的崩溃防护）

脚本对每行设备做防护：`pos_mm`/`envelope_mm`/`mass_g` 缺失或不可解析、bay 值未登记 → **跳过该行、登记进 stdout 报告 `rows_skipped_invalid` 并 stderr 告警，不崩溃**。当前数据下：

- `rows_skipped_invalid` = 空（40/40 行全部有效）。
- `rows_distributed_background` = EQ-TH-MLI / EQ-HARNESS-INT / EQ-SEC-STRUCT / ST-STRUCT-REAL（bay=distributed，包络=全船）：几何视图中不单画色块，渲染为全船背景阴影层 + 角注列名（data 属性仍随行走），避免 4 个全船大包络互相覆盖导致图面不可读。

## 5. 已知局限

1. **包络块 ≠ 真实外形**：全部设备按含安装间隙的长方体包络投影，非 CAD 几何；干涉检查 R12 全量、托盘抽取方向在 C3（GAP-IL-06/07）。
2. **帆板收拢态未表达**：FRZ-SOLAR-L/R 的 pos/envelope 为 C01 在轨展开态冻结账本值（envelope 轴向按冻结账本原样绘制）；发射收拢构型质量特性在 CDR 口径 NOT_EVALUABLE（OI-3）。前视图中根部标记的 z 坐标取展开 CG 的 z（ASSUMED，已登记），根部 y = ±(226.3/2) 由 FRZ-BUS 包络推导。
3. **B601 为展开态粗包络**：600×300×300 mm 为 C01 (ARM_TASK_READY) 包络 proxy，侧/前视图均按原值绘制，不代表臂杆真实几何。
4. **FRZ-BUS 是集总 proxy 块**：23.303 kg 的 provenance 为 24 kg 整星块模型拆分余额，无内部结构/舱（M1 双读法见 LAYOUT_SCHEME_V1.md §3）；侧视/前视图中按 yaml 声明 bay=mid_avionics 绘制为近全船大块，标签置块内右下角。
5. **侧视图投影信息损失**：左右帆板在 x–z 平面重合（仅 y 不同）、B601 y 向偏置（−175.7 mm）不可见、CG 的 y 分量不可见——以前视图与 CG 数值标签补足。
6. **总线长度双口径**：图面按冻结 340.5 mm 基线绘制；CDS 现行标准 366.0 mm 冲突登记 OI-6/GAP-IL-08（post_paper HOLD），未在图上表达。
7. **CDS 变体 CG fail 是设计事实而非图纸错误**：x −57.827 / y −9.303 mm 超包络（INFEASIBLE_WITHIN_X_KNOBS，OI-1），图上以红 × 与底注如实标注。
8. 标签防重叠为确定性启发式（固定顺序逐标签上移 9 px 步进），密集区（中舱 RW/MTQ 簇）标签有移位但不改数字；小字号标签可能与包络边线相切，不影响数据一致性。

## 6. 自检结论（2026-08-27 执行）

- 三张 SVG 均通过 `xml.etree.ElementTree` 解析（合法 XML）。
- 抽查 5 行（EQ-OBC / EQ-BAT1 / FRZ-B601 / EQ-PROP-MIPS / EQ-SS1）：SVG `data-*` 属性与标签文本和 EQUIPMENT_LIST_V1.yaml 全精度一致；40/40 行均带 `data-id`。
- 脚本重跑三图 sha256 逐字节一致（确定性）。
- 图上工程数字全部由脚本从三个源文件读取/推导（含正则提取的 x=208.0 与 366.0）；无手填。
