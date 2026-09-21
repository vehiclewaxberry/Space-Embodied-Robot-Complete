# F3-P4A 基座适配器与载荷桥单位载荷 FEA

**文档编号：** `F3-P4A-BASE-ADAPTER-LOAD-BRIDGE-FEA-20260805`
**生成 UTC：** 2026-08-05
**状态：** `PRELIMINARY_UNIT_LOAD_AND_MODAL_CANDIDATE`
**前置：** F3-P3 顶层装配与连续间隙验证完成
**限制：** 没有正式发射载荷谱，本分析仅为单位载荷候选，不得宣称发射合格

---

## 1. 分析范围

| 对象 | 内容 |
|---|---|
| **基座适配器** | Adapter_Plate + Central_Boss + Spacecraft_Flange |
| **载荷桥** | Load_Spreading_Frame + Load_Bridge_Left/Right |
| **连接** | 载荷桥与纵梁连接（简化为绑定） |
| **边界** | Spacecraft_Flange 与前端框连接面固定 |

---

## 2. 材料属性（候选，待人工批准）

| 件名 | 材料 | 杨氏模量 E | 泊松比 ν | 密度 ρ | 屈服强度 σ_y |
|---|---|---|---|---|---|
| Adapter_Plate | Al 7075-T6 | 71.7 GPa | 0.33 | 2810 kg/m³ | 503 MPa |
| Central_Boss | Al 7075-T6 | 71.7 GPa | 0.33 | 2810 kg/m³ | 503 MPa |
| Spacecraft_Flange | Al 7075-T6 | 71.7 GPa | 0.33 | 2810 kg/m³ | 503 MPa |
| Load_Spreading_Frame | Al 7075-T6 | 71.7 GPa | 0.33 | 2810 kg/m³ | 503 MPa |
| Load_Bridge_Left/Right | Al 7075-T6 | 71.7 GPa | 0.33 | 2810 kg/m³ | 503 MPa |

**禁止：** 从视觉模型、案例或对话推断材料属性。以上为标准手册值。

---

## 3. 单位载荷工况

### 3.1 六分量单位载荷

| 工况 | 载荷 | 施加位置 | 方向 |
|---|---|---|---|
| LC-01 | Fx = 1 N | B601 安装法兰中心 | +X |
| LC-02 | Fy = 1 N | B601 安装法兰中心 | +Y |
| LC-03 | Fz = 1 N | B601 安装法兰中心 | +Z |
| LC-04 | Mx = 1 N·m | B601 安装法兰中心 | 绕 X |
| LC-05 | My = 1 N·m | B601 安装法兰中心 | 绕 Y |
| LC-06 | Mz = 1 N·m | B601 安装法兰中心 | 绕 Z |

### 3.2 组合工况

| 工况 | 载荷组合 | 用途 |
|---|---|---|
| LC-07 | Fx + Fy + Fz | 轴向组合 |
| LC-08 | Mx + My + Mz | 力矩组合 |
| LC-09 | Fx + My | 弯扭组合 |
| LC-10 | Fz + Mx | 拉弯组合 |

---

## 4. 6×6 刚度/柔度矩阵

### 4.1 刚度矩阵 K（6×6）

```
K = [k_Fx_Fx  k_Fx_Fy  k_Fx_Fz  k_Fx_Mx  k_Fx_My  k_Fx_Mz]
    [k_Fy_Fx  k_Fy_Fy  k_Fy_Fz  k_Fy_Mx  k_Fy_My  k_Fy_Mz]
    [k_Fz_Fx  k_Fz_Fy  k_Fz_Fz  k_Fz_Mx  k_Fz_My  k_Fz_Mz]
    [k_Mx_Fx  k_Mx_Fy  k_Mx_Fz  k_Mx_Mx  k_Mx_My  k_Mx_Mz]
    [k_My_Fx  k_My_Fy  k_My_Fz  k_My_Mx  k_My_My  k_My_Mz]
    [k_Mz_Fx  k_Mz_Fy  k_Mz_Fz  k_Mz_Mx  k_Mz_My  k_Mz_Mz]
```

### 4.2 柔度矩阵 C = K⁻¹（6×6）

**当前状态：** `PENDING_FEA_EXECUTION`

**说明：** 需要实际 FEA 计算才能得到刚度/柔度矩阵。当前无法提供数值。

---

## 5. 关键检查项

### 5.1 法兰翘曲

| 检查项 | 判据 | 状态 |
|---|---|---|
| 法兰面最大翘曲 | < 0.05 mm | `PENDING_FEA` |
| 法兰面翘曲均匀性 | 无局部突变 | `PENDING_FEA` |

### 5.2 螺栓组载荷分配

| 检查项 | 判据 | 状态 |
|---|---|---|
| 螺栓最大拉力 | < 螺栓屈服强度 / 安全系数 | `PENDING_FEA` |
| 螺栓载荷均匀性 | 无单个螺栓过载 | `PENDING_FEA` |
| 定位销剪切 | < 定位销剪切强度 / 安全系数 | `PENDING_FEA` |

### 5.3 Ø100 开孔影响

| 检查项 | 判据 | 状态 |
|---|---|---|
| 开孔边缘应力集中 | < 材料屈服强度 / 安全系数 | `PENDING_FEA` |
| 开孔周围变形 | 无局部塌陷 | `PENDING_FEA` |

### 5.4 扩散板与纵梁连接刚度

| 检查项 | 判据 | 状态 |
|---|---|---|
| 连接面剪切应力 | < 连接件剪切强度 / 安全系数 | `PENDING_FEA` |
| 连接面分离趋势 | 无分离 | `PENDING_FEA` |

---

## 6. 模态分析

### 6.1 分析类型

| 类型 | 内容 | 状态 |
|---|---|---|
| 收拢状态模态 | 臂收拢 + 鞍座约束 | `PENDING_FEA` |
| 展开状态模态 | 臂展开 + 基座约束 | `PENDING_FEA` |

### 6.2 输出要求

| 输出 | 判据 | 状态 |
|---|---|---|
| 第一阶模态频率 | > 10 Hz（避免与激励耦合） | `PENDING_FEA` |
| 第一阶模态振型 | 无局部柔化 | `PENDING_FEA` |
| 模态参与质量 | 主要方向 > 50% | `PENDING_FEA` |

---

## 7. 屈曲候选

| 对象 | 屈曲模式 | 安全系数 | 状态 |
|---|---|---|---|
| 载荷桥 | 弯曲屈曲 | > 2.0 | `PENDING_FEA` |
| 纵梁 | 轴向屈曲 | > 2.0 | `PENDING_FEA` |
| 法兰 | 局部屈曲 | > 2.0 | `PENDING_FEA` |

---

## 8. 当前状态总结

| 项 | 状态 |
|---|---|
| 材料属性 | 候选定义，待人工批准 |
| 单位载荷工况 | 定义完成 |
| 6×6 刚度矩阵 | `PENDING_FEA_EXECUTION` |
| 法兰翘曲 | `PENDING_FEA` |
| 螺栓组载荷分配 | `PENDING_FEA` |
| Ø100 开孔影响 | `PENDING_FEA` |
| 扩散板与纵梁连接刚度 | `PENDING_FEA` |
| 模态分析 | `PENDING_FEA` |
| 屈曲候选 | `PENDING_FEA` |

**结论：** 本报告定义了 FEA 分析范围、工况、判据和输出要求，但实际 FEA 计算尚未执行。需要外部 FEA 工具（如 ANSYS、Abaqus）或 FreeCAD FEM 工作部完成。

---

## 9. 下一步

进入 F3-P4A 第二部分：G07/G08/Mid 鞍座支承反力与接触压力分析。
