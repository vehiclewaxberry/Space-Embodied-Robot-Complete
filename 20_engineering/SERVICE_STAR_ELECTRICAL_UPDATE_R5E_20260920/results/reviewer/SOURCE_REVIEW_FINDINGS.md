# R5E 独立源一致性复验

项目：12U 服务星 / B601；日期：2026-09-20；阶段：本轮电气选型前的源一致性复验。

结论：经三板实际 PCB 冷读，选型主源应绑定 `implementation/results/stop_v36/pcb/thermal_filter_20260916/native_20260916_a/wp10_system.xml`（SHA256 `90497ad91d4b8ec2c39e6eda819b94e3fbcf9f908861aae22e6c90c5bf1a1939`）。该源含 249 refs / 795 pin-net 对。主源到三板的网络与器件 value 一致；只限数字设计一致性，不提供上电、制造或航天鉴定信用。

## 实际 PCB 复验

- MAIN：43 footprint = 35 XML 器件 + 4 安装孔 + 4 板级导线焊盘。135 pad = 122 精确网络匹配 + 5 显式 NC + 4 逐一溯源到指定原理图端点的导线焊盘 + 4 安装孔。35 个器件 value 和封装 ID 全匹配。四个 `PORT_*` 并未盲目跳过，而是逐端点验证。
- STOP：107 footprint = 103 XML 器件 + 4 安装孔。341 pad = 324 精确网络匹配 + 17 机械 pad。历史 337 的口径为排除 4 个安装孔，仍包含 13 个连接器机械 pad。103 个器件 value 和封装 ID 全匹配。
- AUX：32 footprint = 26 XML 器件 + 6 安装孔，其中 J210 为板上复位测试铜盘，采购数量不应作为连接器计算。104 pad = 90 精确网络匹配 + 14 机械 pad。26 个 value 全匹配，15 个封装 ID 完全相同，11 个板内封装缺 library nickname、但 item name 一致。对这 11 个额外比较归一化 pad 位置、尺寸、钻孔、形状、层、属性、旋转、圆角比例和偏置，11/11 相同；不将此等同于整个封装或制造约束一致。

复验未重复 DRC。既有 DRC 是历史受检范围；本轮对源、网络与元数据的变更重新核验。

## 需显式隔离的版本漂移

1. `ecad/revisions/v36/wp10_system.xml`（`15ca898b0272d5b7f2b55144fc03bf2f0323f72e67e3c19fa8beddb9630a0a7e`）仅 239 refs / 771 pin-net 对。缺少 C314–C319、R350–R352、J106；U311/U312/U313 pin 3 回退到未滤波网络；STOP 中另有 86 个空 footprint 字段和 27 个不同 value。不能作为当前实布 STOP PCB 的完整源。
2. 原 `HANDOFF_DELTA_20260917_STOP_REVIEW_COMPLETE.json` 的 9 个证据哈希中 8 个仍相符，`WORKING_REVISION.json` 期望 `50a6f1796f48dbfc0a6d18e4c65683920692bfed87bf625321653031fe8c6671`，实际 `9f95e871e5dc772d671ed4c0dad9f51727d648c5b0dfb4c6b96b4d96580e3fbb`。应保留原记录并新建受检入口，不可改写旧 receipt 使其表面通过。
3. AUX 继承 receipt 的 `stats.footprints=44` 与同 SHA 的实板 32 不符。新报告应写独立冷读 32，不沿用历史统计数字。

## R202 数据手册核验

原厂 [Vishay WSLP2726 数据手册](https://www.vishay.com/docs/30179/wslp2726.pdf)，修订 29-Jun-2026，p1–2：`WSLP2726L5000FEA` 的 L5000 是 0.0005 Ω，F 为 ±1%。成品 TCR 为 ±75 ppm/°C；6°C/W 是电阻元件至端子的热阻。该阻值本体高度 2.95±0.2 mm；12 W 额定值要求规定端子温度与散热条件。

与 R201 的 2 mΩ 相加为 2.5 mΩ。20 A 名义电阻损耗为 1.000 W；此前 R202=0.2 mΩ 模型为 0.880 W，差额 +0.120 W。终温仍需要安装导热边界，不能以额定功率直接判断温度合格。旧 CF1 / V30 几何与热输入仍需明确映射更新。

## 可复现证据

- `tools/reviewer/audit_current_v36.py` → `CURRENT_V36_SOURCE_AUDIT.json`：严格原始比较，故有显式 NC、机械 pad 和端口导致的原始差异，不能把该原始计数全部解释成电路错误。
- `tools/reviewer/audit_locked_xml_projection.py` → `LOCKED_249_XML_BOARD_AUDIT.json`：按有限、逐项记录的 NC / 机械 / 端口合同复验。
- `tools/reviewer/audit_aux_library_pads.py` → `AUX_EMBEDDED_LIBRARY_PADS.json`：11 个缺库昵称封装的 pad 几何复验。

三个脚本仅写本包 reviewer 目录；未保存、修改或重建原理图/PCB。PCB 和关键输入在冷读前后哈希未变。

本文件是源一致性审计，完整五维选型评审将在候选 BOM、约束和验收计划落地后进行。
