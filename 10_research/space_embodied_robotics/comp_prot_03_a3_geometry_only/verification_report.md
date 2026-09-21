# A3 Geometry Only 原生 CAD 验收报告

_2026-07-23；该报告不是科学 Gate。_

## 裁决

`A3_GEOMETRY_ONLY_COMPLETE_WITH_EXPLICIT_LIMITATIONS`

本轮建立了可由 SOLIDWORKS 2024 SP5 打开和编辑的 12U+B601 几何数字机械主机。证据仅支持几何样机、装配层级、命名参数、frame 放置和文件可追溯性，不支持动力学、结构强度、发射合规、工作空间、抓取可行性或“已实现空间具身智能”等结论。

## 自动复验结果

| 检查项 | 结果 | 证据 |
|---|---:|---|
| 原生 CAD 重新打开 | `15/15 PASS` | `evidence/native_inspection.log` |
| B601 源轴包络一致性 | `10/10 PASS` | `BBOX_SOURCE_AXIS_MATCH` |
| 命名尺寸可读取 | `56/56 PASS` | `NAMED_DIMENSION` |
| 强制边界属性可读取 | `105/105 PASS` | `PROPERTY` |
| 固定的一层组件 | `14/14 PASS` | B601 10，顶层 4 |
| `T_SM` 放置合同 | `2/2 PASS` | adapter 与 B601 assembly |
| 嵌入式 X 向堆叠 | `PASS` | `EMBEDDED_STACKUP_X` |
| 失败标记 | `0` | 原生检查日志全文统计 |
| 保守包络干涉 | `0` | `builder_stdout.log` |
| 构建错误输出 | `0 bytes` | `builder_stderr.log` |

顶层装配包络（S frame，单位 m）：

```text
[-0.17025, -0.11315, -0.26031015301125326]
[+0.46745023829891352, +0.11315, +0.27250014927116395]
```

## A3-GEO 验收

| ID | 状态 | 判定依据 |
|---|---|---|
| `A3-GEO-01` | `PASS` | 13 个零件和 2 个装配体均重新打开 |
| `A3-GEO-02` | `PASS` | 原生命名尺寸可读取；未宣称 Equation Manager 全局变量 |
| `A3-GEO-03` | `PASS` | 12U 显示 profile 为 `340.5 × 226.3 × 226.3 mm` |
| `A3-GEO-04` | `PASS` | `S/M/A0` 已绑定；`T_SB` 与 physical TCP 保持禁用 |
| `A3-GEO-05` | `PASS` | 160 mm 接口、160 × 160 × 12 mm 板、Ø100 × 15 mm boss 可追溯 |
| `A3-GEO-06` | `PASS` | 10-link/9-joint 身份与 q=0 参考装配存在 |
| `A3-GEO-07` | `PASS` | 未包含目标星、碎片或接触几何 |
| `A3-GEO-08` | `PASS` | 截图、日志、frame 导出和 SHA-256 清单齐备 |
| `A3-GEO-09` | `PASS` | 未改科学 Gate、仿真结果或冻结几何配置 |

## 明确限制

- B601 为基于既有 STL 轴对齐最小/最大坐标构造的长方体包络代理，不是供应商精确曲面。
- 供应商 STEP 未复制、未导入、未修改。
- Service Bus 是显示包络与接口参考几何；其中参考法兰独立成第二实体，不能据此推断载荷路径。
- 参数化由 SolidWorks 原生命名尺寸与自定义属性承担；本轮未建立 Equation Manager 全局变量表。
- 传感器、末端 Level 0 标记、目标、接触面、收拢状态、rail 合规、physical TCP、聚合 CoM/惯量仍未关闭。
- 干涉结果只针对当前 q=0 保守包络与当前总装，不等价于全工作空间无碰撞。

## 证据入口

- CAD 根目录：`20_engineering/cad/Space_Embodied_Robot_CAD_V0_1/`
- 主总装：`Assembly/12U_Master_Skeleton.SLDASM`
- 文件清单：`component_hash_manifest_v0_1.csv`
- 自动化清单：`automation_hash_manifest_v0_1.csv`
- 原生检查：`evidence/native_inspection.log`
- 构建记录：`evidence/builder_stdout.log`
- 等轴测截图：`evidence/12U_B601_geometry_only_isometric.bmp`
