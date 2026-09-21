# F3-P5 S3 Geometry Verification Report

**文档编号：** `F3-P5-S3-GEOMETRY-VERIFICATION-20260805`
**生成 UTC：** 2026-08-05
**状态：** `S3_GEOMETRY_VERIFIED`

---

## 1. S3 架构定义

```text
S3_RATIFIED_AS_STRUCTURAL_BASELINE_PENDING_FEA
```

- **G07 (Aft)**：主承托点，link6 接触
- **G08 (Fwd)**：主承托点，gripper_link 接触
- **Mid**：非接触备份，名义间隙 2 mm

---

## 2. G07 (Aft) 几何核实

| 参数 | 值 | 来源 | 状态 |
|---|---|---|---|
| 接触中心 X | [-20, 0] mm | `o13_saddle_stations.json` | VERIFIED |
| 接触高 z | 261.08 mm | `o13_saddle_stations.json` | VERIFIED |
| 塔高 | 147.93 mm | `o13_saddle_stations.json` | VERIFIED |
| Y 范围 | [-71.33, 77.70] mm | `o13_saddle_stations.json` | VERIFIED |
| 接触 link | link6（腕部） | STOW FK | VERIFIED |
| 承载方向 | Tz + Tx + Rx | F3-P2A | VERIFIED |

---

## 3. G08 (Fwd) 几何核实

| 参数 | 值 | 来源 | 状态 |
|---|---|---|---|
| 接触中心 X | [160, 180] mm | `o13_saddle_stations.json` | VERIFIED |
| 接触高 z | 209.42 mm | `o13_saddle_stations.json` | VERIFIED |
| 塔高 | 96.27 mm | `o13_saddle_stations.json` | VERIFIED |
| Y 范围 | [2.99, 80.11] mm | `o13_saddle_stations.json` | VERIFIED |
| 接触 link | gripper_link（末端） | STOW FK | VERIFIED |
| 承载方向 | Ry | F3-P2A | VERIFIED |

---

## 4. Mid 几何核实

| 参数 | 值 | 来源 | 状态 |
|---|---|---|---|
| 接触中心 X | [80, 100] mm | `o13_saddle_stations.json` | VERIFIED |
| 接触高 z | 214.92 mm | `o13_saddle_stations.json` | VERIFIED |
| 塔高 | 101.77 mm | `o13_saddle_stations.json` | VERIFIED |
| Y 范围 | [7.72, 87.87] mm | `o13_saddle_stations.json` | VERIFIED |
| 接触 link | link4（中段） | STOW FK | VERIFIED |
| 承载方向 | 非接触备份（S3） | F3-P4B | VERIFIED |

---

## 5. Mid 2mm 名义间隙核实

| 参数 | 值 | 来源 | 状态 |
|---|---|---|---|
| 名义间隙 | 2.0 mm | F3-P4B | VERIFIED |
| 间隙类型 | 非接触备份 | F3-P4B | VERIFIED |
| 名义状态 | 不持续承载 | F3-P4B | VERIFIED |
| 备份状态 | 超限挠曲/冲击/异常姿态下接触 | F3-P4B | VERIFIED |
| 间隙性质 | 名义设计值，非显示误差或临时装配值 | F3-P4B | VERIFIED |

---

## 6. S3 几何基线确认

| 检查项 | 结果 | 状态 |
|---|---|---|
| G07 几何明确 | ✅ | VERIFIED |
| G08 几何明确 | ✅ | VERIFIED |
| Mid 几何明确 | ✅ | VERIFIED |
| Mid 2mm 间隙是名义设计值 | ✅ | VERIFIED |
| S3 架构未被无授权更改 | ✅ | VERIFIED |
| S1/S2 未作为当前基线 | ✅ | VERIFIED |

---

## 7. 结论

```text
S3_GEOMETRY_VERIFIED
```

- G07/G08/Mid 几何均已核实
- Mid 2mm 间隙是名义设计值
- S3 架构未被无授权更改
- 可进入 FEA 输入准备

**下一步：** 检查可用 FEA 求解器及版本 + CAD 到 FEA 安全转换路径。
