# F3-P5D 比赛样机制造发布（8 件继承结构）

**文档编号：** `F3-P5D-MANUFACTURING-RELEASE-20260805`
**生成 UTC：** 2026-08-05
**状态：** `MANUFACTURING_RELEASE_FOR_COMPETITION_PROTOTYPE_ONLY`
**前置：** F3-P4E 工程定义深化（ENGINEERING_DEFINITION_DRAWING_NOT_MANUFACTURING_RELEASE）+ F3-P5C 构型闭合
**HOLD 处置：** HOLD-10 → `CLOSED_MANUFACTURING_RELEASE_FOR_COMPETITION_PROTOTYPE_ONLY`

---

## 1. 发布范围与边界

- **发布对象：** 8 件继承结构 + G07/G08 接触垫 + HDRM 竞赛演示配置，面向**比赛样机制造**。
- **非发布对象：** 任何飞行合格结论（`NOT_FLIGHT_QUALIFIED`）；AL 载荷下强度/屈曲裕度仍 TBD。
- **制造依据：** F3-P4E 材料/毛坯/基准/GD&T + 本文件工艺与检验要求；TechDraw 图纸在制造前由制造方按本文件出图确认。

## 2. 8 件材料与工艺路线（比赛样机）

| 件号 | 件名 | 材料 | 工艺 | 表面处理 | 状态 |
|---|---|---|---|---|---|
| 01 | Adapter_Plate | Al 7075-T6 | CNC 铣削 | 硬质阳极氧化（本色） | `MANUFACTURING_RELEASE` |
| 02 | Central_Boss | Al 7075-T6 | CNC 车铣复合 | 硬质阳极氧化 | `MANUFACTURING_RELEASE` |
| 03 | Spacecraft_Flange | Al 7075-T6 | CNC 铣削 | 硬质阳极氧化 | `MANUFACTURING_RELEASE` |
| 04 | Load_Spreading_Frame | Al 7075-T6 | CNC 铣削 | 硬质阳极氧化 | `MANUFACTURING_RELEASE` |
| 05 | Load_Bridge_Left | Al 7075-T6 | CNC 铣削 | 硬质阳极氧化 | `MANUFACTURING_RELEASE` |
| 06 | Load_Bridge_Right | Al 7075-T6 | CNC 铣削 | 硬质阳极氧化 | `MANUFACTURING_RELEASE` |
| 07 | Harness_Passage | Al 6061-T6 | CNC 铣削 | 阳极氧化 | `MANUFACTURING_RELEASE` |
| 08 | Maintenance_Access_Cover | Al 6061-T6 | CNC 铣削 | 阳极氧化 | `MANUFACTURING_RELEASE` |

**通用工艺要求：**
- 毛坯尺寸与加工余量：按 F3-P4E §3（余量 2.5 mm）
- 去毛刺、倒角 R0.3
- 螺纹：M5×0.8 通规止规检验
- 基准加工顺序：先基准 A（底面）后基准 B（中心线/孔位）

## 3. GD&T 关键项（比赛样机验收判据）

| 件号 | 关键项 | 公差 | 检验方法 |
|---|---|---|---|
| 01 | 基准 A 平面度 | 0.05 mm | 大理石平台 + 塞尺 |
| 01 | 与 02 配合孔位置度 | Ø0.1 mm | CMM |
| 02 | 中心轴线垂直度 | 0.05 mm | 千分表打表 |
| 03 | 基准 A 平面度 | 0.05 mm | 大理石平台 |
| 04 | 底面平面度 | 0.05 mm | 大理石平台 |
| 05/06 | 左右镜像对称度 | 0.1 mm | CMM 镜像比较 |
| 07/08 | 装配面平面度 | 0.1 mm | 大理石平台 |

## 4. 检验计划（MPI）

输出：`F3_P5D_MPI_CHECKLIST.csv`（每件 4–6 项，含尺寸/形位/螺纹/表面）

**放行规则：** 全部 MPI 项 PASS 后签发 `COMPETITION_PROTOTYPE_PARTS_ACCEPTED`；任一 FAIL → 返修或重新加工，禁止让步放行结构关键件（01–06）。

## 5. 装配程序要点

1. 顺序：03 → 01 → 02 → 04 → 05/06 → 07 → 08 → B601 基座适配 → G07/G08 接触垫（标定）→ HDRM 竞赛演示件
2. 紧固：M5×16 按 4 N·m 交叉拧紧，防松胶（中强度）
3. 接触垫标定：装配后按 F3-P5B 规则台架压缩标定，写入标定日志
4. HDRM 电磁锁：保持力-电流曲线验收，释放行程 6 mm 验证，微动开关状态验证
5. 总装后：干涉检查（Mode B 展开扫掠）、相机 FOV 抽检（时序按 F3-P5C）

## 6. BOM

输出：`11_bom/F3_P5D_COMPETITION_PROTOTYPE_BOM.csv`（零件 + 紧固件 + 接触垫 + HDRM 组件 + 线缆）

## 7. 裁决

```text
F3_P5D_PARTIAL_PASS_MANUFACTURING_RELEASE_FOR_COMPETITION_PROTOTYPE_ONLY
```

- 比赛样机可制造发布（8 件 + 接触垫 + HDRM 演示件）
- 非飞行合格；AL 强度/屈曲裕度保持 TBD
- HOLD-10 闭合（范围限定比赛样机）
