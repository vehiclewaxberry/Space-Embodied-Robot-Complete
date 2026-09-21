# F3-P4A G07/G08/Mid 鞍座支承反力与接触压力分析

**文档编号：** `F3-P4A-SADDLE-REACTION-CONTACT-PRESSURE-20260805`
**生成 UTC：** 2026-08-05
**状态：** `PRELIMINARY_ANALYSIS_FRAMEWORK`
**前置：** F3-P4A 基座适配器与载荷桥 FEA 框架定义

---

## 1. 分析范围

| 对象 | 内容 |
|---|---|
| **G07 (Aft)** | 主承托鞍座，link6 接触 |
| **G08 (Fwd)** | 腕部支撑鞍座，gripper_link 接触 |
| **Mid** | 中段支承候选，link4 接触（待取舍） |
| **接触垫** | 柔性接触垫，材料/刚度 TBD |

---

## 2. 支承反力分析

### 2.1 单点支承反力

| 工况 | G07 反力 | G08 反力 | Mid 反力 | 状态 |
|---|---|---|---|---|
| LC-01 Fx = 1 N | TBD | TBD | TBD | `PENDING_FEA` |
| LC-02 Fy = 1 N | TBD | TBD | TBD | `PENDING_FEA` |
| LC-03 Fz = 1 N | TBD | TBD | TBD | `PENDING_FEA` |
| LC-04 Mx = 1 N·m | TBD | TBD | TBD | `PENDING_FEA` |
| LC-05 My = 1 N·m | TBD | TBD | TBD | `PENDING_FEA` |
| LC-06 Mz = 1 N·m | TBD | TBD | TBD | `PENDING_FEA` |

### 2.2 组合支承反力

| 工况 | G07 反力 | G08 反力 | Mid 反力 | 状态 |
|---|---|---|---|---|
| LC-07 Fx+Fy+Fz | TBD | TBD | TBD | `PENDING_FEA` |
| LC-08 Mx+My+Mz | TBD | TBD | TBD | `PENDING_FEA` |
| LC-09 Fx+My | TBD | TBD | TBD | `PENDING_FEA` |
| LC-10 Fz+Mx | TBD | TBD | TBD | `PENDING_FEA` |

---

## 3. 接触压力分析

### 3.1 接触压力分布

| 鞍座 | 接触面积 | 最大接触压力 | 平均接触压力 | 状态 |
|---|---|---|---|---|
| G07 | TBD | TBD | TBD | `PENDING_FEA` |
| G08 | TBD | TBD | TBD | `PENDING_FEA` |
| Mid | TBD | TBD | TBD | `PENDING_FEA` |

### 3.2 接触压力判据

| 判据 | 值 | 状态 |
|---|---|---|
| 最大接触压力 < 接触垫抗压强度 / 安全系数 | 安全系数 > 2.0 | `PENDING_FEA` |
| 接触压力均匀性 | 无局部过载 | `PENDING_FEA` |
| 接触垫压缩量 | < 允许压缩量 | `PENDING_FEA` |

---

## 4. 支承塔弯曲

| 鞍座 | 塔高 | 弯曲应力 | 变形 | 状态 |
|---|---|---|---|---|
| G07 | 147.93 mm | TBD | TBD | `PENDING_FEA` |
| G08 | 96.27 mm | TBD | TBD | `PENDING_FEA` |
| Mid | 101.77 mm | TBD | TBD | `PENDING_FEA` |

---

## 5. 局部屈曲

| 鞍座 | 屈曲模式 | 安全系数 | 状态 |
|---|---|---|---|
| G07 | 支承塔弯曲屈曲 | > 2.0 | `PENDING_FEA` |
| G08 | 支承塔弯曲屈曲 | > 2.0 | `PENDING_FEA` |
| Mid | 支承塔弯曲屈曲 | > 2.0 | `PENDING_FEA` |

---

## 6. 预紧敏感性

| 参数 | 变化范围 | 对反力的影响 | 对接触压力的影响 | 状态 |
|---|---|---|---|---|
| 预紧力 | ±20% | TBD | TBD | `PENDING_FEA` |
| 接触垫刚度 | ±20% | TBD | TBD | `PENDING_FEA` |
| 接触垫厚度 | ±10% | TBD | TBD | `PENDING_FEA` |

---

## 7. 摩擦敏感性

| 参数 | 变化范围 | 对反力的影响 | 对接触压力的影响 | 状态 |
|---|---|---|---|---|
| 摩擦系数 | 0.1 ~ 0.5 | TBD | TBD | `PENDING_FEA` |
| 接触面粗糙度 | Ra 1.6 ~ 6.3 μm | TBD | TBD | `PENDING_FEA` |

---

## 8. 接触丢失

| 工况 | G07 接触丢失 | G08 接触丢失 | Mid 接触丢失 | 状态 |
|---|---|---|---|---|
| LC-01 Fx = 1 N | TBD | TBD | TBD | `PENDING_FEA` |
| LC-02 Fy = 1 N | TBD | TBD | TBD | `PENDING_FEA` |
| LC-03 Fz = 1 N | TBD | TBD | TBD | `PENDING_FEA` |
| LC-04 Mx = 1 N·m | TBD | TBD | TBD | `PENDING_FEA` |
| LC-05 My = 1 N·m | TBD | TBD | TBD | `PENDING_FEA` |
| LC-06 Mz = 1 N·m | TBD | TBD | TBD | `PENDING_FEA` |

---

## 9. 刚性过约束趋势

| 检查项 | 判据 | 状态 |
|---|---|---|
| 基座 + G07 + G08 是否形成刚性过约束 | Jacobian 矩阵秩 < 6 | `PENDING_ANALYSIS` |
| 基座 + G07 + Mid + G08 是否形成刚性过约束 | Jacobian 矩阵秩 < 6 | `PENDING_ANALYSIS` |
| 约束 Jacobian 条件数 | < 100（避免病态） | `PENDING_ANALYSIS` |

---

## 10. 当前状态总结

| 项 | 状态 |
|---|---|
| 支承反力分析框架 | 定义完成 |
| 接触压力分析框架 | 定义完成 |
| 支承塔弯曲 | `PENDING_FEA` |
| 局部屈曲 | `PENDING_FEA` |
| 预紧敏感性 | `PENDING_FEA` |
| 摩擦敏感性 | `PENDING_FEA` |
| 接触丢失 | `PENDING_FEA` |
| 刚性过约束趋势 | `PENDING_ANALYSIS` |

**结论：** 本报告定义了鞍座支承反力与接触压力分析框架，但实际计算尚未执行。需要外部 FEA 工具完成。

---

## 11. 下一步

进入 F3-P4B：Mid 鞍座最终取舍（S1/S2/S3 三方案对比）。
