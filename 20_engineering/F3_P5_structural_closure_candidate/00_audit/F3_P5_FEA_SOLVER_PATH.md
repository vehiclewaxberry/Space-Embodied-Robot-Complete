# F3-P5 FEA Solver and CAD-to-FEA Path Report

**文档编号：** `F3-P5-FEA-SOLVER-PATH-20260805`
**生成 UTC：** 2026-08-05
**状态：** `SOLVER_AVAILABLE_PATH_DEFINED`

---

## 1. 可用 FEA 求解器

| 求解器 | 路径 | 版本 | 状态 |
|---|---|---|---|
| **CalculiX (ccx)** | `G:\Windows_program_file\FreeCAD\bin\ccx.exe` | FreeCAD 1.1.3 内置 | **AVAILABLE** |
| **Gmsh** | `G:\Windows_program_file\FreeCAD\bin\gmsh.exe` | FreeCAD 1.1.3 内置 | **AVAILABLE** |
| **FreeCAD FEM** | `G:\Windows_program_file\FreeCAD\Mod\Fem` | FreeCAD 1.1.3 内置 | **AVAILABLE** |
| ANSYS | 未安装 | — | NOT_AVAILABLE |
| Abaqus | 未安装 | — | NOT_AVAILABLE |

**选择：** FreeCAD FEM + CalculiX（内置，无需额外安装）

---

## 2. CAD 到 FEA 安全转换路径

### 2.1 转换路径

```
V2_3 SolidWorks 原生 CAD (.SLDPRT/.SLDASM)
        │
        ▼ (SolidWorks STEP 导出)
STEP AP214 (.step)
        │
        ▼ (FreeCAD 导入)
FreeCAD 文档 (.FCStd)
        │
        ▼ (FreeCAD FEM 网格划分)
Gmsh 网格 (.msh 或 .unv)
        │
        ▼ (CalculiX 求解)
CalculiX 输入 (.inp)
        │
        ▼ (CalculiX 求解)
CalculiX 结果 (.frd)
        │
        ▼ (FreeCAD FEM 后处理)
FEA 结果（应力/位移/模态/反力）
```

### 2.2 关键转换点

| 转换点 | 工具 | 风险 | 缓解 |
|---|---|---|---|
| SolidWorks → STEP | SolidWorks 导出 | 特征丢失、装配关系丢失 | 使用 AP214 协议，保留装配结构 |
| STEP → FreeCAD | FreeCAD 导入 | 单位错误、几何错误 | 验证单位（mm）、验证几何有效性 |
| FreeCAD → Gmsh | FreeCAD FEM | 网格质量差、局部过细 | 控制网格尺寸、局部细化 |
| Gmsh → CalculiX | FreeCAD FEM | 单元类型不匹配、边界条件错误 | 验证单元类型、验证边界条件 |
| CalculiX → 结果 | FreeCAD FEM | 结果解读错误 | 验证反力平衡、验证能量误差 |

---

## 3. 当前可用 CAD 配置

| 配置 | 来源 | 状态 |
|---|---|---|
| **V2_3 SolidWorks 原生** | `20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/` | **AVAILABLE** |
| **F3-P1 HIFI 视觉包** | `F:/Space-Embodied-Robot-HAG_A_20260804/12_f3_p1_hifi_attachment/01_visual_packages/` | **AVAILABLE** |
| **F3-P3 顶层装配** | `F:/Space-Embodied-Robot-HAG_A_20260804/12_f3_p1_hifi_attachment/15_f3_p3_top_assembly/` | **AVAILABLE** |

**FEA 输入选择：** V2_3 SolidWorks 原生（结构件）+ F3-P1 HIFI 视觉包（B601 几何参考）

---

## 4. FEA 输入配置唯一性确认

| 检查项 | 结果 | 状态 |
|---|---|---|
| FEA 使用 CAD 配置唯一 | V2_3 SolidWorks 原生 + F3-P1 HIFI 视觉包 | CONFIRMED |
| 工程图配置与 FEA 配置一致 | 是（8 件继承结构） | CONFIRMED |
| 材料数据源唯一 | 标准手册（Al 7075-T6 / Al 6061-T6） | CONFIRMED |
| 单位体系统一 | mm / N / MPa | CONFIRMED |
| 载荷施加坐标系统一 | M（机械臂安装面坐标系） | CONFIRMED |

---

## 5. 结论

```text
SOLVER_AVAILABLE_PATH_DEFINED
```

- **求解器：** FreeCAD FEM + CalculiX（内置，可用）
- **转换路径：** SolidWorks → STEP → FreeCAD → Gmsh → CalculiX → 结果
- **CAD 配置：** V2_3 SolidWorks 原生 + F3-P1 HIFI 视觉包
- **材料数据源：** 标准手册
- **单位体系：** mm / N / MPa
- **载荷坐标系：** M（机械臂安装面坐标系）

**下一步：** 检查权威发射载荷谱 + 划分 UL/PL/AL 三轨。
