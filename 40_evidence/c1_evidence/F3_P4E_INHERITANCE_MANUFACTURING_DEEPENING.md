# F3-P4E 8 件继承结构制造级深化

**文档编号：** `F3-P4E-INHERITANCE-MANUFACTURING-DEEPENING-20260805`
**生成 UTC：** 2026-08-05
**状态：** `ENGINEERING_DEFINITION_DRAWING_NOT_MANUFACTURING_RELEASE`
**前置：** F3-P4D HDRM 结构深化
**限制：** 没有正式载荷、材料和 HDRM 型号关闭前，工程图标记为 `ENGINEERING_DEFINITION_DRAWING_NOT_MANUFACTURING_RELEASE`

---

## 1. 8 件继承结构清单

| 件号 | 件名 | 当前状态 | 深化内容 |
|---|---|---|---|
| 01 | Adapter_Plate | V2_3 已有 | 材料/毛坯/基准/尺寸/GD&T/表面/孔螺纹/紧固件/定位销/防松/接地/装配/工具/检验/TechDraw/BOM |
| 02 | Central_Boss | V2_3 已有 | 同上 |
| 03 | Spacecraft_Flange | V2_3 已有 | 同上 |
| 04 | Load_Spreading_Frame | V2_3 已有 | 同上 |
| 05 | Load_Bridge_Left | V2_3 已有 | 同上 |
| 06 | Load_Bridge_Right | V2_3 已有 | 同上 |
| 07 | Harness_Passage | V2_3 已有 | 同上 |
| 08 | Maintenance_Access_Cover | V2_3 已有 | 同上 |

**原则：** 不重新发明几何，只根据 F3-P3/P4 证据进行必要修改，并补齐制造级定义。

---

## 2. 材料与状态

| 件号 | 材料 | 状态 | 热处理 | 来源 |
|---|---|---|---|---|
| 01 | Al 7075-T6 | 固溶处理 + 人工时效 | T6 | 标准手册 |
| 02 | Al 7075-T6 | 固溶处理 + 人工时效 | T6 | 标准手册 |
| 03 | Al 7075-T6 | 固溶处理 + 人工时效 | T6 | 标准手册 |
| 04 | Al 7075-T6 | 固溶处理 + 人工时效 | T6 | 标准手册 |
| 05 | Al 7075-T6 | 固溶处理 + 人工时效 | T6 | 标准手册 |
| 06 | Al 7075-T6 | 固溶处理 + 人工时效 | T6 | 标准手册 |
| 07 | Al 6061-T6 | 固溶处理 + 人工时效 | T6 | 标准手册 |
| 08 | Al 6061-T6 | 固溶处理 + 人工时效 | T6 | 标准手册 |

---

## 3. 毛坯

| 件号 | 毛坯形式 | 毛坯尺寸 | 加工余量 | 状态 |
|---|---|---|---|---|
| 01 | 铝板切割 | 165×165×15 mm | 2.5 mm | `DESIGN_PROPOSAL` |
| 02 | 铝棒车削 | Ø105×20 mm | 2.5 mm | `DESIGN_PROPOSAL` |
| 03 | 铝板切割 | 170×170×15 mm | 2.5 mm | `DESIGN_PROPOSAL` |
| 04 | 铝板切割 | 200×200×20 mm | 2.5 mm | `DESIGN_PROPOSAL` |
| 05 | 铝板切割 | 150×50×20 mm | 2.5 mm | `DESIGN_PROPOSAL` |
| 06 | 铝板切割 | 150×50×20 mm | 2.5 mm | `DESIGN_PROPOSAL` |
| 07 | 铝板切割 | 100×50×10 mm | 2.5 mm | `DESIGN_PROPOSAL` |
| 08 | 铝板切割 | 120×80×10 mm | 2.5 mm | `DESIGN_PROPOSAL` |

---

## 4. 主基准 A/B/C

### 4.1 基准定义

| 件号 | 基准 A | 基准 B | 基准 C |
|---|---|---|---|
| 01 | 底面（与 03 接触） | 中心轴线（与 02 配合） | 前端面（与 04 接触） |
| 02 | 底面（与 01 接触） | 中心轴线 | — |
| 03 | 底面（与前端框接触） | 中心轴线（与 01 配合） | — |
| 04 | 底面（与纵梁接触） | 中心线 | — |
| 05 | 底面（与纵梁接触） | 中心线 | — |
| 06 | 底面（与纵梁接触） | 中心线 | — |
| 07 | 底面（与 01 接触） | — | — |
| 08 | 底面（与 01 接触） | — | — |

### 4.2 基准公差

| 基准 | 公差 | 状态 |
|---|---|---|
| A 平面度 | 0.05 mm | `DESIGN_PROPOSAL` |
| B 位置度 | Ø0.1 mm | `DESIGN_PROPOSAL` |
| C 垂直度 | 0.05 mm | `DESIGN_PROPOSAL` |

---

## 5. 关键接口尺寸

| 件号 | 尺寸 | 公差 | 基准 | 状态 |
|---|---|---|---|---|
| 01 | 160×160×12 mm | ±0.1 mm | A | FROZEN |
| 02 | Ø100×15 mm | ±0.05 mm | A, B | FROZEN |
| 03 | 与 01 配合孔 PCD Ø85 mm | ±0.1 mm | A, B | `DESIGN_PROPOSAL` |
| 04 | 与纵梁连接孔位置 | ±0.2 mm | C | `DESIGN_PROPOSAL` |
| 05 | 与纵梁连接孔位置 | ±0.2 mm | C | `DESIGN_PROPOSAL` |
| 06 | 与纵梁连接孔位置 | ±0.2 mm | C | `DESIGN_PROPOSAL` |
| 07 | 线束通道宽度 20 mm | ±0.5 mm | — | `DESIGN_PROPOSAL` |
| 08 | 维修盖开口 100×60 mm | ±0.5 mm | — | `DESIGN_PROPOSAL` |

---

## 6. 尺寸公差

| 件号 | 一般尺寸公差 | 关键尺寸公差 | 状态 |
|---|---|---|---|
| 01 | ±0.1 mm | ±0.05 mm | `DESIGN_PROPOSAL` |
| 02 | ±0.05 mm | ±0.02 mm | `DESIGN_PROPOSAL` |
| 03 | ±0.1 mm | ±0.05 mm | `DESIGN_PROPOSAL` |
| 04 | ±0.2 mm | ±0.1 mm | `DESIGN_PROPOSAL` |
| 05 | ±0.2 mm | ±0.1 mm | `DESIGN_PROPOSAL` |
| 06 | ±0.2 mm | ±0.1 mm | `DESIGN_PROPOSAL` |
| 07 | ±0.5 mm | ±0.2 mm | `DESIGN_PROPOSAL` |
| 08 | ±0.5 mm | ±0.2 mm | `DESIGN_PROPOSAL` |

---

## 7. GD&T

| 件号 | 特征 | 公差 | 基准 | 状态 |
|---|---|---|---|---|
| 01 | 平面度 | 0.05 mm | A | `DESIGN_PROPOSAL` |
| 01 | 位置度（孔） | Ø0.2 mm | A, B | `DESIGN_PROPOSAL` |
| 02 | 位置度 | Ø0.1 mm | A, B | `DESIGN_PROPOSAL` |
| 02 | 垂直度 | 0.05 mm | A | `DESIGN_PROPOSAL` |
| 03 | 平面度 | 0.05 mm | A | `DESIGN_PROPOSAL` |
| 03 | 位置度（孔） | Ø0.1 mm | A, B | `DESIGN_PROPOSAL` |
| 04 | 平面度 | 0.1 mm | C | `DESIGN_PROPOSAL` |
| 04 | 位置度（孔） | Ø0.2 mm | C | `DESIGN_PROPOSAL` |
| 05 | 平面度 | 0.1 mm | C | `DESIGN_PROPOSAL` |
| 06 | 平面度 | 0.1 mm | C | `DESIGN_PROPOSAL` |
| 07 | 平面度 | 0.1 mm | — | `DESIGN_PROPOSAL` |
| 08 | 平面度 | 0.1 mm | — | `DESIGN_PROPOSAL` |

---

## 8. 表面粗糙度

| 件号 | 接触面 Ra | 孔 Ra | 非接触面 Ra | 状态 |
|---|---|---|---|---|
| 01 | 1.6 μm | 3.2 μm | 6.3 μm | `DESIGN_PROPOSAL` |
| 02 | 1.6 μm | 3.2 μm | 6.3 μm | `DESIGN_PROPOSAL` |
| 03 | 1.6 μm | 3.2 μm | 6.3 μm | `DESIGN_PROPOSAL` |
| 04 | 1.6 μm | 3.2 μm | 6.3 μm | `DESIGN_PROPOSAL` |
| 05 | 1.6 μm | 3.2 μm | 6.3 μm | `DESIGN_PROPOSAL` |
| 06 | 1.6 μm | 3.2 μm | 6.3 μm | `DESIGN_PROPOSAL` |
| 07 | 3.2 μm | 6.3 μm | 6.3 μm | `DESIGN_PROPOSAL` |
| 08 | 3.2 μm | 6.3 μm | 6.3 μm | `DESIGN_PROPOSAL` |

---

## 9. 表面处理

| 件号 | 表面处理 | 目的 | 状态 |
|---|---|---|---|
| 01 | 阳极氧化（硬质） | 防腐、耐磨 | `DESIGN_PROPOSAL` |
| 02 | 阳极氧化（硬质） | 防腐、耐磨 | `DESIGN_PROPOSAL` |
| 03 | 阳极氧化（硬质） | 防腐、耐磨 | `DESIGN_PROPOSAL` |
| 04 | 阳极氧化（普通） | 防腐 | `DESIGN_PROPOSAL` |
| 05 | 阳极氧化（普通） | 防腐 | `DESIGN_PROPOSAL` |
| 06 | 阳极氧化（普通） | 防腐 | `DESIGN_PROPOSAL` |
| 07 | 阳极氧化（普通） | 防腐 | `DESIGN_PROPOSAL` |
| 08 | 阳极氧化（普通） | 防腐 | `DESIGN_PROPOSAL` |

---

## 10. 孔和螺纹

| 件号 | 孔类型 | 螺纹规格 | 数量 | 状态 |
|---|---|---|---|---|
| 01 | 通孔 | M6 | 8 | `DESIGN_PROPOSAL` |
| 01 | 盲孔 | M5 | 12 | `DESIGN_PROPOSAL` |
| 02 | 通孔 | M6 | 8 | `DESIGN_PROPOSAL` |
| 03 | 通孔 | M6 | 8 | `DESIGN_PROPOSAL` |
| 04 | 通孔 | M4 | 8 | `DESIGN_PROPOSAL` |
| 05 | 通孔 | M4 | 4 | `DESIGN_PROPOSAL` |
| 06 | 通孔 | M4 | 4 | `DESIGN_PROPOSAL` |
| 07 | — | — | — | — |
| 08 | 通孔 | M3 | 4 | `DESIGN_PROPOSAL` |

---

## 11. 紧固件

| 件号 | 螺栓规格 | 数量 | 材料 | 预紧力 | 状态 |
|---|---|---|---|---|---|
| 01-02 | M6×20 | 8 | 不锈钢 A2-70 | 8 N·m | `DESIGN_PROPOSAL` |
| 01-03 | M5×16 | 12 | 不锈钢 A2-70 | 5 N·m | `DESIGN_PROPOSAL` |
| 04-纵梁 | M4×12 | 8 | 不锈钢 A2-70 | 3 N·m | `DESIGN_PROPOSAL` |
| 05-纵梁 | M4×12 | 4 | 不锈钢 A2-70 | 3 N·m | `DESIGN_PROPOSAL` |
| 06-纵梁 | M4×12 | 4 | 不锈钢 A2-70 | 3 N·m | `DESIGN_PROPOSAL` |
| 08-01 | M3×10 | 4 | 不锈钢 A2-70 | 1.5 N·m | `DESIGN_PROPOSAL` |

---

## 12. 定位销

| 件号 | 定位销规格 | 数量 | 材料 | 配合 | 状态 |
|---|---|---|---|---|---|
| 01-02 | Ø6 h7×20 | 2 | 不锈钢 A2-70 | h7/g6 | `DESIGN_PROPOSAL` |
| 01-03 | Ø5 h7×16 | 2 | 不锈钢 A2-70 | h7/g6 | `DESIGN_PROPOSAL` |
| 04-纵梁 | Ø4 h7×12 | 4 | 不锈钢 A2-70 | h7/g6 | `DESIGN_PROPOSAL` |

---

## 13. 防松

| 件号 | 防松方式 | 适用 | 状态 |
|---|---|---|---|
| 所有 | 弹簧垫圈 | 所有螺栓 | `DESIGN_PROPOSAL` |
| 关键 | 螺纹锁固胶（Loctite 243） | M6/M5 螺栓 | `DESIGN_PROPOSAL` |
| 定位销 | 过盈配合 | 所有定位销 | `DESIGN_PROPOSAL` |

---

## 14. 接地搭接

| 件号 | 搭接方式 | 目的 | 状态 |
|---|---|---|---|
| 01 | 搭接片（铜镀锡） | 电磁兼容 | `DESIGN_PROPOSAL` |
| 03 | 搭接片（铜镀锡） | 电磁兼容 | `DESIGN_PROPOSAL` |
| 04 | 搭接片（铜镀锡） | 电磁兼容 | `DESIGN_PROPOSAL` |

---

## 15. 装配方向

| 件号 | 主装配方向 | 辅助装配方向 | 状态 |
|---|---|---|---|
| 02 → 01 | +Z（向下） | — | FROZEN |
| 01 → 03 | +Z（向下） | — | FROZEN |
| 04 → 纵梁 | +Z（向下） | — | FROZEN |
| 05 → 纵梁 | +X（向内） | — | FROZEN |
| 06 → 纵梁 | -X（向内） | — | FROZEN |
| 07 → 01 | +Z（向下） | — | FROZEN |
| 08 → 01 | +Z（向下） | — | FROZEN |

---

## 16. 工具可达

| 件号 | 工具 | 可达空间 | 状态 |
|---|---|---|---|
| 01-02 | 内六角扳手 | 直径 20 mm 圆柱 | `DESIGN_PROPOSAL` |
| 01-03 | 内六角扳手 | 直径 20 mm 圆柱 | `DESIGN_PROPOSAL` |
| 04-纵梁 | 内六角扳手 | 直径 15 mm 圆柱 | `DESIGN_PROPOSAL` |
| 05-纵梁 | 内六角扳手 | 直径 15 mm 圆柱 | `DESIGN_PROPOSAL` |
| 06-纵梁 | 内六角扳手 | 直径 15 mm 圆柱 | `DESIGN_PROPOSAL` |
| 08-01 | 十字螺丝刀 | 直径 15 mm 圆柱 | `DESIGN_PROPOSAL` |

---

## 17. 检验方法

| 件号 | 检验项 | 方法 | 设备 | 状态 |
|---|---|---|---|---|
| 01 | 平面度 | 三坐标测量 | CMM | `DESIGN_PROPOSAL` |
| 01 | 孔位置度 | 三坐标测量 | CMM | `DESIGN_PROPOSAL` |
| 02 | 位置度 | 三坐标测量 | CMM | `DESIGN_PROPOSAL` |
| 03 | 平面度 | 三坐标测量 | CMM | `DESIGN_PROPOSAL` |
| 04 | 孔位置度 | 三坐标测量 | CMM | `DESIGN_PROPOSAL` |
| 所有 | 表面粗糙度 | 粗糙度仪 | 粗糙度仪 | `DESIGN_PROPOSAL` |
| 所有 | 尺寸 | 卡尺/千分尺 | 卡尺/千分尺 | `DESIGN_PROPOSAL` |

---

## 18. TechDraw 要求

### 18.1 必须包含的视图

1. **主视图：** 显示正面外形与主要尺寸
2. **俯视图：** 显示孔分布与 PCD
3. **侧视图：** 显示截面与连接
4. **剖视图：** 显示内部结构与配合
5. **局部放大图：** 显示关键细节（孔、销、螺纹）

### 18.2 必须标注的内容

- 所有外形尺寸与公差
- 所有孔的位置尺寸与公差（以 A/B/C 为基准）
- GD&T（平面度、位置度、垂直度）
- 表面粗糙度
- 材料与热处理
- 表面处理
- 紧固件与定位销规格
- 防松方式
- 接地搭接
- 装配方向
- 检验方法

### 18.3 工程图标记

```
ENGINEERING_DEFINITION_DRAWING_NOT_MANUFACTURING_RELEASE
```

**原因：** 没有正式载荷、材料和 HDRM 型号关闭前，工程图仅为工程定义，不得作为制造发布依据。

---

## 19. BOM

| 件号 | 件名 | 数量 | 材料 | 毛坯 | 备注 |
|---|---|---|---|---|---|
| 01 | Adapter_Plate | 1 | Al 7075-T6 | 铝板切割 165×165×15 | 含 M6/M5 孔 |
| 02 | Central_Boss | 1 | Al 7075-T6 | 铝棒车削 Ø105×20 | 含 M6 孔 |
| 03 | Spacecraft_Flange | 1 | Al 7075-T6 | 铝板切割 170×170×15 | 含 M6 孔 |
| 04 | Load_Spreading_Frame | 1 | Al 7075-T6 | 铝板切割 200×200×20 | 含 M4 孔 |
| 05 | Load_Bridge_Left | 1 | Al 7075-T6 | 铝板切割 150×50×20 | 含 M4 孔 |
| 06 | Load_Bridge_Right | 1 | Al 7075-T6 | 铝板切割 150×50×20 | 含 M4 孔 |
| 07 | Harness_Passage | 1 | Al 6061-T6 | 铝板切割 100×50×10 | 线束通道 |
| 08 | Maintenance_Access_Cover | 1 | Al 6061-T6 | 铝板切割 120×80×10 | 含 M3 孔 |
| 09 | 螺栓 M6×20 | 8 | 不锈钢 A2-70 | 标准件 | 01-02 连接 |
| 10 | 螺栓 M5×16 | 12 | 不锈钢 A2-70 | 标准件 | 01-03 连接 |
| 11 | 螺栓 M4×12 | 8 | 不锈钢 A2-70 | 标准件 | 04-纵梁连接 |
| 12 | 螺栓 M4×12 | 4 | 不锈钢 A2-70 | 标准件 | 05-纵梁连接 |
| 13 | 螺栓 M4×12 | 4 | 不锈钢 A2-70 | 标准件 | 06-纵梁连接 |
| 14 | 螺栓 M3×10 | 4 | 不锈钢 A2-70 | 标准件 | 08-01 连接 |
| 15 | 定位销 Ø6 h7×20 | 2 | 不锈钢 A2-70 | 标准件 | 01-02 连接 |
| 16 | 定位销 Ø5 h7×16 | 2 | 不锈钢 A2-70 | 标准件 | 01-03 连接 |
| 17 | 定位销 Ø4 h7×12 | 4 | 不锈钢 A2-70 | 标准件 | 04-纵梁连接 |
| 18 | 弹簧垫圈 M6 | 8 | 不锈钢 A2-70 | 标准件 | 防松 |
| 19 | 弹簧垫圈 M5 | 12 | 不锈钢 A2-70 | 标准件 | 防松 |
| 20 | 弹簧垫圈 M4 | 16 | 不锈钢 A2-70 | 标准件 | 防松 |
| 21 | 弹簧垫圈 M3 | 4 | 不锈钢 A2-70 | 标准件 | 防松 |
| 22 | 螺纹锁固胶 Loctite 243 | 1 | — | 标准件 | M6/M5 螺栓防松 |
| 23 | 搭接片（铜镀锡） | 3 | 铜镀锡 | 标准件 | 接地搭接 |

---

## 20. 下一步

进入 F3-P4 Gate 裁决与最终报告。
