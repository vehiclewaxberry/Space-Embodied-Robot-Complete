# F3R1 G2 见证截图索引

**来源：** `04_configurations/G2/step/F3R1_V3_<CONFIG>.step`（由冷重开阶段逐配置导出，各 ~126 MB）
**渲染：** FreeCAD 1.1.3 pinned（`G:\Windows_program_file\FreeCAD\bin\FreeCAD.exe`），1920×1080，白底，强制可见性
**性质：** 原始见证图。每张图来自**该配置实际导出的几何**，不是靠移动零件为镜头摆拍。

> 单进程连续导入四个 126 MB STEP 会耗尽内存并静默退出（无 PNG）。已改为**每配置一个独立 FreeCAD 进程**渲染。

| 配置 | 图 | 形体数 | 字节 | 目视要点 |
|---|---|---:|---:|---|
| `STOWED_ENGINEERING_CANDIDATE` | `11_screenshots/RAW/G2/G2_STOWED_ENGINEERING_CANDIDATE_ISO_RAW.png` | 457 | 73 670 | 两翼均**收拢**（折叠下垂），B601 折叠六轴链在位 |
| `DEPLOYED_NOMINAL` | `11_screenshots/RAW/G2/G2_DEPLOYED_NOMINAL_ISO_RAW.png` | 457 | 56 464 | 两翼均**展开**（平板外伸），臂引用默认配置 |
| `L_FAIL` | `11_screenshots/RAW/G2/G2_L_FAIL_ISO_RAW.png` | 457 | 66 774 | **左收拢 / 右展开**：左前方可见外伸平板，另一侧折叠 |
| `R_FAIL` | `11_screenshots/RAW/G2/G2_R_FAIL_ISO_RAW.png` | 457 | 67 719 | **左展开 / 右收拢**：与 L_FAIL 明显相反，外伸平板消失、改为折叠板下垂 |

## 故障状态左右独立性（目视印证）

`L_FAIL` 与 `R_FAIL` 两图的翼板构型明显不同、且互为相反侧，印证机器实测结论：

```text
L_FAIL : live = WING_L_STOWED-1  + WING_R_DEPLOYED-1   实测角度 0.0 / 90.0
R_FAIL : live = WING_L_DEPLOYED-1 + WING_R_STOWED-1    实测角度 90.0 / 0.0
```

两者为独立构建的配置内容，**不是同一张图镜像复用**。

## 未在图中体现的 HOLD

- `PARTIAL` 未渲染：它无权威角度且**未几何分化**（与 `DEPLOYED_NOMINAL` 同为 90/90），渲染只会得到与展开态相同的图，故不出图以免被误读为"部分展开场景"。
- `SERVICE`、`SOLAR_DEPLOY_ARM_LOCKED`、`DEPLOY_FAILED_BOTH` 未单独出图：几何分别等同于展开态或收拢态，其差异体现在**配置属性与臂引用配置**（见 `F3R1_G2_CONFIGURATION_MATRIX.csv`），非翼板几何。
- 四张图中翼板与真实铰链销仍相距 **30.0 mm**（D-F3R1-06 未闭合）；图中不得读作物理铰链已连接。
