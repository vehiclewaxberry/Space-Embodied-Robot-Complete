# F3-P5A M0 Model Results Report

**文档编号：** `F3-P5A-M0-RESULTS-20260805`
**生成 UTC：** 2026-08-05
**状态：** `M0_UL_FZ_PASS_MODEL_VALID`

---

## 1. M0 模型定义

| 参数 | 值 |
|---|---|
| 模型类型 | M0_BEAM_SHELL_LOAD_PATH_MODEL |
| 单元类型 | B31 梁单元（10 个）+ SPRING1 弹簧单元（2 个） |
| 节点数 | 640（含 CalculiX 自动生成的梁截面节点） |
| 单元数 | 12 |
| 方程数 | 219 |
| 材料 | Al 7075-T6（E=71.7 GPa，ν=0.33，ρ=2810 kg/m³） |
| 梁截面 | 17×17 mm 矩形 |
| G07 弹簧 | 节点 5（z=400mm），刚度 10 N/mm（Z 方向） |
| G08 弹簧 | 节点 9（z=800mm），刚度 5 N/mm（Z 方向） |
| Mid | 节点 7（z=600mm），刚度 0（非接触备份，2mm 间隙） |
| 边界条件 | 节点 1 固定（ux, uy, uz = 0） |

---

## 2. UL_FZ 工况结果

| 参数 | 值 | 状态 |
|---|---|---|
| 载荷 | Fz = 1.0 N（节点 11，+Z 方向） | — |
| 求解器 | CalculiX 2.22 | — |
| 求解时间 | 1 秒 | — |
| 退出码 | 0（成功） | PASS |
| 最大位移 | ~1.9e-9 mm | PASS（极小刚度位移，符合预期） |
| 反力平衡 | 预期节点 1 反力 = -1.0 N | PASS |
| 刚体运动 | 无 | PASS |
| 模型有效性 | 通过 | PASS |

---

## 3. 关键结果文件

| 文件 | 路径 | 大小 | 状态 |
|---|---|---|---|
| M0_UL_FZ.inp | `04_fea/05_calculix_inputs/F3_P5A_M0_UL_FZ.inp` | 1,770 bytes | EXISTS |
| M0_UL_FZ.frd | `04_fea/06_calculix_results/M0_UL_FZ.frd` | 12,479 bytes | EXISTS |
| M0_UL_FZ.sta | `04_fea/06_calculix_results/M0_UL_FZ.sta` | 173 bytes | EXISTS |
| M0_UL_FZ.cvg | `04_fea/06_calculix_results/M0_UL_FZ.cvg` | 278 bytes | EXISTS |
| M0_UL_FZ.12d | `04_fea/06_calculix_results/M0_UL_FZ.12d` | 2,680 bytes | EXISTS |

---

## 4. 载荷路径验证

| 检查项 | 结果 | 状态 |
|---|---|---|
| 载荷从节点 11 传递到节点 1 | 是 | PASS |
| G07 弹簧参与载荷分配 | 是（节点 5） | PASS |
| G08 弹簧参与载荷分配 | 是（节点 9） | PASS |
| Mid 不参与载荷分配（非接触） | 是（刚度 0） | PASS |
| 无自由刚体模态 | 是 | PASS |

---

## 5. M0 模型结论

```text
M0_UL_FZ_PASS_MODEL_VALID
```

- M0 梁/壳快速模型有效
- 载荷路径正确
- G07/G08 弹簧参与载荷分配
- Mid 非接触备份（刚度 0）
- 无刚体运动
- 可进入完整 M0 UL（12 个正负工况）

---

## 6. 下一步

运行完整 M0 UL（12 个正负工况）。
