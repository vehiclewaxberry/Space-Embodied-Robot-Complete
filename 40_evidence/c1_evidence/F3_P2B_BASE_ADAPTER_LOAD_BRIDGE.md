# B601 基座适配器与载荷桥继承审查与制造级深化

**文档编号：** `F3-P2B-BASE-ADAPTER-LOAD-BRIDGE-20260805`
**生成 UTC：** 2026-08-05
**状态：** `FROZEN_FOR_F3_P2C`
**前置：** F3-P2A 载荷路径与约束自由度冻结

---

## 1. 继承审查（V2_3 现有 8 件）

| 件名 | 当前状态 | 继承决策 | 深化需求 |
|---|---|---|---|
| `Adapter_Plate.SLDPRT` | 160×160×12 适配板 | **继承** | 材料、基准、紧固件、GD&T、工程图 |
| `Central_Boss.SLDPRT` | Ø100×15 中央凸台 | **继承** | 材料、与适配板连接方式、定位销 |
| `Spacecraft_Flange.SLDPRT` | 航天器侧法兰 | **继承** | 材料、与前端框连接、螺栓圈 |
| `Load_Spreading_Frame.SLDPRT` | 载荷扩散板 | **继承** | 材料、与纵梁连接、加强筋 |
| `Load_Bridge_Left.SLDPRT` | 左载荷桥 | **继承** | 材料、截面、与纵梁连接 |
| `Load_Bridge_Right.SLDPRT` | 右载荷桥 | **继承** | 材料、截面、与纵梁连接 |
| `Harness_Passage.SLDPRT` | 线束通道 | **继承** | 材料、线束固定、弯曲半径 |
| `Maintenance_Access_Cover.SLDPRT` | 维修盖 | **继承** | 材料、密封、紧固件 |

**继承原则：** 不重新画一套，只做制造级深化。

---

## 2. 材料选择（候选，待人工批准）

| 件名 | 候选材料 | 候选来源 | 状态 |
|---|---|---|---|
| Adapter_Plate | Al 7075-T6 | 航天成熟、加工容易、质量可控 | `DESIGN_PROPOSAL` |
| Central_Boss | Al 7075-T6 | 同上 | `DESIGN_PROPOSAL` |
| Spacecraft_Flange | Al 7075-T6 | 同上 | `DESIGN_PROPOSAL` |
| Load_Spreading_Frame | Al 7075-T6 | 同上 | `DESIGN_PROPOSAL` |
| Load_Bridge_Left/Right | Al 7075-T6 | 同上 | `DESIGN_PROPOSAL` |
| Harness_Passage | Al 6061-T6 | 非承载、轻量 | `DESIGN_PROPOSAL` |
| Maintenance_Access_Cover | Al 6061-T6 | 非承载、轻量 | `DESIGN_PROPOSAL` |

**禁止：** 从视觉模型、案例或对话推断材料、板厚、紧固、载荷、刚度、强度、模态数值。

---

## 3. 基准系统（A/B/C）

### 3.1 基准定义

| 基准 | 定义 | 用途 | 公差 |
|---|---|---|---|
| **A** | Adapter_Plate 底面（与 Spacecraft_Flange 接触面） | 主安装基准 | 平面度 0.05 mm |
| **B** | Central_Boss 中心轴线 | 主定位基准 | 位置度 Ø0.1 mm |
| **C** | Adapter_Plate 前端面（与 Load_Spreading_Frame 接触面） | 辅助定位基准 | 垂直度 0.05 mm |

### 3.2 基准应用

- **A 基准：** 所有安装孔的位置度以 A 为基准
- **B 基准：** B601 安装法兰的位置度以 B 为基准
- **C 基准：** Load_Spreading_Frame 的位置度以 C 为基准

---

## 4. 紧固件与定位销

### 4.1 B601 安装法兰（与 Central_Boss 连接）

| 项目 | 候选值 | 状态 |
|---|---|---|
| 螺栓规格 | M6×20 | `DESIGN_PROPOSAL` |
| 螺栓数量 | 8 | `DESIGN_PROPOSAL` |
| PCD | Ø85 mm | `DESIGN_PROPOSAL` |
| 定位销 | Ø6 h7×20 | `DESIGN_PROPOSAL` |
| 定位销数量 | 2 | `DESIGN_PROPOSAL` |
| 预紧力 | 8 N·m | `DESIGN_PROPOSAL` |

### 4.2 Adapter_Plate 与 Spacecraft_Flange 连接

| 项目 | 候选值 | 状态 |
|---|---|---|
| 螺栓规格 | M5×16 | `DESIGN_PROPOSAL` |
| 螺栓数量 | 12 | `DESIGN_PROPOSAL` |
| PCD | Ø140 mm | `DESIGN_PROPOSAL` |
| 定位销 | Ø5 h7×16 | `DESIGN_PROPOSAL` |
| 定位销数量 | 2 | `DESIGN_PROPOSAL` |
| 预紧力 | 5 N·m | `DESIGN_PROPOSAL` |

### 4.3 Load_Spreading_Frame 与纵梁连接

| 项目 | 候选值 | 状态 |
|---|---|---|
| 螺栓规格 | M4×12 | `DESIGN_PROPOSAL` |
| 螺栓数量 | 8（每纵梁 2） | `DESIGN_PROPOSAL` |
| 定位销 | Ø4 h7×12 | `DESIGN_PROPOSAL` |
| 定位销数量 | 4（每纵梁 1） | `DESIGN_PROPOSAL` |
| 预紧力 | 3 N·m | `DESIGN_PROPOSAL` |

---

## 5. GD&T（几何尺寸与公差）

### 5.1 关键尺寸公差

| 特征 | 公差 | 基准 | 状态 |
|---|---|---|---|
| Adapter_Plate 平面度 | 0.05 mm | A | `DESIGN_PROPOSAL` |
| Central_Boss 位置度 | Ø0.1 mm | A, B | `DESIGN_PROPOSAL` |
| Central_Boss 垂直度 | 0.05 mm | A | `DESIGN_PROPOSAL` |
| 螺栓孔位置度 | Ø0.2 mm | A, B | `DESIGN_PROPOSAL` |
| 定位销孔位置度 | Ø0.1 mm | A, B | `DESIGN_PROPOSAL` |
| Load_Spreading_Frame 平面度 | 0.1 mm | C | `DESIGN_PROPOSAL` |
| 纵梁孔位置度 | Ø0.2 mm | C | `DESIGN_PROPOSAL` |

### 5.2 表面粗糙度

| 表面 | 粗糙度 Ra | 状态 |
|---|---|---|
| 安装接触面 | 1.6 μm | `DESIGN_PROPOSAL` |
| 螺栓孔 | 3.2 μm | `DESIGN_PROPOSAL` |
| 定位销孔 | 1.6 μm | `DESIGN_PROPOSAL` |
| 非接触面 | 6.3 μm | `DESIGN_PROPOSAL` |

---

## 6. 工程图要求

### 6.1 必须包含的视图

1. **主视图：** 显示 Adapter_Plate + Central_Boss 正面
2. **俯视图：** 显示螺栓孔分布与 PCD
3. **侧视图：** 显示载荷桥与纵梁连接
4. **剖视图 A-A：** 显示 Central_Boss 与 Adapter_Plate 连接
5. **剖视图 B-B：** 显示载荷桥截面
6. **局部放大图：** 显示定位销孔与螺栓孔细节

### 6.2 必须标注的尺寸

- 所有外形尺寸
- 所有孔的位置尺寸（以 A/B/C 为基准）
- PCD 与螺栓规格
- 定位销规格与位置
- 平面度、位置度、垂直度公差
- 表面粗糙度

### 6.3 必须包含的技术要求

- 材料与热处理状态
- 表面处理（阳极氧化、喷砂等）
- 紧固件预紧力
- 装配顺序
- 检验方法

---

## 7. BOM（物料清单）

| 件号 | 件名 | 数量 | 材料 | 备注 |
|---|---|---|---|---|
| 01 | Adapter_Plate | 1 | Al 7075-T6 | 160×160×12 |
| 02 | Central_Boss | 1 | Al 7075-T6 | Ø100×15 |
| 03 | Spacecraft_Flange | 1 | Al 7075-T6 | 与前端框连接 |
| 04 | Load_Spreading_Frame | 1 | Al 7075-T6 | 载荷扩散 |
| 05 | Load_Bridge_Left | 1 | Al 7075-T6 | 左载荷桥 |
| 06 | Load_Bridge_Right | 1 | Al 7075-T6 | 右载荷桥 |
| 07 | Harness_Passage | 1 | Al 6061-T6 | 线束通道 |
| 08 | Maintenance_Access_Cover | 1 | Al 6061-T6 | 维修盖 |
| 09 | 螺栓 M6×20 | 8 | 不锈钢 A2-70 | B601 安装法兰 |
| 10 | 定位销 Ø6 h7×20 | 2 | 不锈钢 A2-70 | B601 安装法兰 |
| 11 | 螺栓 M5×16 | 12 | 不锈钢 A2-70 | Adapter_Plate 连接 |
| 12 | 定位销 Ø5 h7×16 | 2 | 不锈钢 A2-70 | Adapter_Plate 连接 |
| 13 | 螺栓 M4×12 | 8 | 不锈钢 A2-70 | 纵梁连接 |
| 14 | 定位销 Ø4 h7×12 | 4 | 不锈钢 A2-70 | 纵梁连接 |

---

## 8. 单位载荷 FEA 要求（F3-P4 前置）

### 8.1 分析类型

- **静力学：** 六分量单位载荷下的应力、位移
- **模态：** 收拢状态与展开状态的第一阶模态
- **屈曲：** 局部屈曲候选（载荷桥、纵梁）

### 8.2 边界条件

- **固定：** Spacecraft_Flange 与前端框连接面
- **载荷：** B601 安装法兰六分量单位载荷
- **接触：** 载荷桥与纵梁螺栓连接（简化为绑定）

### 8.3 输出要求

- 最大 von Mises 应力
- 最大位移
- 第一阶模态频率
- 屈曲安全系数

---

## 9. 未消解 HOLD

1. **材料选择** — Al 7075-T6 是候选，待人工批准
2. **紧固件规格** — M6/M5/M4 是候选，待人工批准
3. **GD&T 公差** — 0.05/0.1/0.2 mm 是候选，待人工批准
4. **表面粗糙度** — 1.6/3.2/6.3 μm 是候选，待人工批准
5. **表面处理** — 阳极氧化、喷砂等未定义
6. **发射载荷谱** — 未定义，无法做强度/刚度校核
7. **T_SM_TRACK_CONFLICT** — 动力学 185.25 vs 显示 198，未裁决

---

## 10. 禁止声明

- 不得在没有人工批准的情况下将候选材料、紧固件、GD&T 作为工程真值
- 不得使用视觉模型或案例推断材料、板厚、紧固、载荷、刚度、强度、模态数值
- 不得在没有 FEA 验证的情况下宣称结构安全
- 不得在没有释放净空包络验证的情况下冻结接触面
