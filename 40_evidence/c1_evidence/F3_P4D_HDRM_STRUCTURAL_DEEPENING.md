# F3-P4D HDRM 结构深化

**文档编号：** `F3-P4D-HDRM-STRUCTURAL-DEEPENING-20260805`
**生成 UTC：** 2026-08-05
**状态：** `FUNCTIONAL_INTERFACE_CLOSED_MODEL_PROCUREMENT_TBD`
**前置：** F3-P4C 接触垫详细设计
**限制：** 具体商业型号保持 `PROCUREMENT_TBD`，但安装接口必须闭合

---

## 1. HDRM 安装法兰

| 参数 | 候选值 | 状态 |
|---|---|---|
| 安装法兰尺寸 | 60×60×10 mm | `DESIGN_PROPOSAL` |
| 安装孔 PCD | Ø50 mm | `DESIGN_PROPOSAL` |
| 安装孔数量 | 4 | `DESIGN_PROPOSAL` |
| 螺栓规格 | M5×16 | `DESIGN_PROPOSAL` |
| 定位销 | Ø5 h7×16 | `DESIGN_PROPOSAL` |
| 定位销数量 | 2 | `DESIGN_PROPOSAL` |
| 材料 | Al 7075-T6 | `DESIGN_PROPOSAL` |
| 平面度 | 0.05 mm | `DESIGN_PROPOSAL` |
| 表面粗糙度 | Ra 1.6 μm | `DESIGN_PROPOSAL` |

---

## 2. 预紧载荷方向

| 参数 | 值 | 状态 |
|---|---|---|
| 预紧方向 | +X（沿臂长方向） | FROZEN |
| 预紧力 | 50 N | `DESIGN_PROPOSAL` |
| 预紧弹簧刚度 | 10 N/mm | `DESIGN_PROPOSAL` |
| 预紧量 | 0.2 mm | `DESIGN_PROPOSAL` |

---

## 3. 载荷传递面

| 参数 | 值 | 状态 |
|---|---|---|
| 主传递面 | 安装法兰底面（与航天器结构接触） | FROZEN |
| 辅助传递面 | 预紧弹簧座（与 HDRM 本体接触） | FROZEN |
| 传递面平面度 | 0.05 mm | `DESIGN_PROPOSAL` |
| 传递面粗糙度 | Ra 1.6 μm | `DESIGN_PROPOSAL` |

---

## 4. 释放行程

| 参数 | 值 | 状态 |
|---|---|---|
| 释放行程 | 5 mm | `DESIGN_PROPOSAL` |
| 释放时间 | < 1 s | `DESIGN_PROPOSAL` |
| 释放方向 | -X（与预紧方向相反） | FROZEN |
| 释放后位置 | 完全退出臂运动包络 | FROZEN |

---

## 5. 机械止挡

| 参数 | 值 | 状态 |
|---|---|---|
| 硬止挡位置 | 释放行程末端 | FROZEN |
| 硬止挡材料 | Al 7075-T6 | `DESIGN_PROPOSAL` |
| 硬止挡接触面 | 平面，Ra 1.6 μm | `DESIGN_PROPOSAL` |
| 硬止挡缓冲 | 碟形弹簧或聚氨酯垫 | `DESIGN_PROPOSAL` |

---

## 6. 执行器功能包络

| 参数 | 值 | 状态 |
|---|---|---|
| 执行器类型 | 功能包络（非飞行型号） | FROZEN |
| 执行器行程 | ≥ 5 mm | `DESIGN_PROPOSAL` |
| 执行器力 | ≥ 50 N | `DESIGN_PROPOSAL` |
| 执行器响应时间 | < 1 s | `DESIGN_PROPOSAL` |
| 执行器失效模式 | 失效安全（机械止挡保持） | FROZEN |
| 具体型号 | PROCUREMENT_TBD | FROZEN |

---

## 7. 弹簧或释放元件包络

| 参数 | 值 | 状态 |
|---|---|---|
| 弹簧类型 | 碟形弹簧或压缩弹簧 | `DESIGN_PROPOSAL` |
| 弹簧刚度 | 10 N/mm | `DESIGN_PROPOSAL` |
| 弹簧预紧量 | 0.2 mm | `DESIGN_PROPOSAL` |
| 弹簧工作行程 | 5 mm | `DESIGN_PROPOSAL` |
| 弹簧材料 | 不锈钢 17-7PH 或类似 | `DESIGN_PROPOSAL` |
| 弹簧寿命 | > 1000 次 | `DESIGN_PROPOSAL` |

---

## 8. 状态传感器接口

| 参数 | 值 | 状态 |
|---|---|---|
| 到位传感器类型 | 机械开关或接近开关 | `DESIGN_PROPOSAL` |
| 释放传感器类型 | 机械开关或接近开关 | `DESIGN_PROPOSAL` |
| 传感器安装位置 | HDRM 本体侧面 | `DESIGN_PROPOSAL` |
| 传感器行程 | ≥ 5 mm | `DESIGN_PROPOSAL` |
| 传感器重复精度 | ±0.1 mm | `DESIGN_PROPOSAL` |
| 传感器环境等级 | 航天级（真空、温度循环） | `DESIGN_PROPOSAL` |

---

## 9. 电连接

| 参数 | 值 | 状态 |
|---|---|---|
| 连接器类型 | 航天级圆形连接器（如 MIL-DTL-38999） | `DESIGN_PROPOSAL` |
| 芯数 | 4（电源 + 信号） | `DESIGN_PROPOSAL` |
| 电流 | ≤ 1 A | `DESIGN_PROPOSAL` |
| 电压 | 28 V DC 或 5 V DC | `DESIGN_PROPOSAL` |
| 屏蔽 | 屏蔽电缆 | `DESIGN_PROPOSAL` |
| 接地 | 单点接地 | `DESIGN_PROPOSAL` |

---

## 10. 残留体 Keepout

| 参数 | 值 | 状态 |
|---|---|---|
| 释放后残留突出 | < 2 mm | FROZEN |
| Latch 完全收回 | 是 | FROZEN |
| 执行器完全退出 | 是 | FROZEN |
| 弹簧完全释放 | 是 | FROZEN |
| 传感器不阻碍 | 是 | FROZEN |

---

## 11. 拆装方向

| 参数 | 值 | 状态 |
|---|---|---|
| 主拆装方向 | +Z（向上） | FROZEN |
| 辅助拆装方向 | +X（向前） | FROZEN |
| 工具空间 | 直径 50 mm 圆柱空间 | `DESIGN_PROPOSAL` |
| 拆装时间 | < 30 min | `DESIGN_PROPOSAL` |

---

## 12. 故障释放方案

| 故障模式 | 释放方案 | 状态 |
|---|---|---|
| 执行器失效 | 机械止挡保持，地面手动解锁 | FROZEN |
| 弹簧失效 | 执行器辅助释放，地面手动解锁 | FROZEN |
| 传感器失效 | 机械指示，地面确认 | FROZEN |
| 电源失效 | 机械保持，地面手动解锁 | FROZEN |

---

## 13. 手动地面解锁接口

| 参数 | 值 | 状态 |
|---|---|---|
| 解锁工具 | 内六角扳手或专用工具 | `DESIGN_PROPOSAL` |
| 解锁方向 | +Z（向上） | FROZEN |
| 解锁力 | < 50 N | `DESIGN_PROPOSAL` |
| 解锁行程 | 5 mm | `DESIGN_PROPOSAL` |
| 解锁后状态 | 与释放后一致 | FROZEN |

---

## 14. 安装接口闭合检查

| 检查项 | 结果 | 状态 |
|---|---|---|
| 安装法兰闭合 | ✅ | FROZEN |
| 预紧载荷方向闭合 | ✅ | FROZEN |
| 载荷传递面闭合 | ✅ | FROZEN |
| 释放行程闭合 | ✅ | FROZEN |
| 机械止挡闭合 | ✅ | FROZEN |
| 执行器包络闭合 | ✅ | FROZEN |
| 弹簧包络闭合 | ✅ | FROZEN |
| 状态传感器接口闭合 | ✅ | FROZEN |
| 电连接闭合 | ✅ | FROZEN |
| 残留 keepout 闭合 | ✅ | FROZEN |
| 拆装方向闭合 | ✅ | FROZEN |
| 故障释放方案闭合 | ✅ | FROZEN |
| 手动地面解锁接口闭合 | ✅ | FROZEN |

**结论：** 所有安装接口已闭合，具体商业型号保持 `PROCUREMENT_TBD`。

---

## 15. 下一步

进入 F3-P4E：8 件继承结构制造级深化（材料/毛坯/基准/GD&T/TechDraw/BOM）。
