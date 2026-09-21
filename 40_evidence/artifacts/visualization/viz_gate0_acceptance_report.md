# VIZ-Gate 0 审阅与验收报告

日期：2026-07-14  
工作分支：`feat/sim09-grasp-evaluator`  
审阅对象：Claude Fable 5 中断前的 Stage 0–6 工作及其工作区遗留

## 1. 验收结论

**VIZ-Gate 0：PASS。** 当前工作区已形成可交付的“统一三维场景＋时序回放＋证据可视化层”。

这只代表可视化层通过，不改变科学门禁：

- 项目横幅仍为 `PROJECT_FROZEN_AT_REPEAT_E1_5`；
- `admissible 0/72`，不存在 SAFE 候选或名义 Top-3；
- 证据线 A `PASS`，B/C 均为 `REPEAT`；
- `UNKNOWN ≠ 不安全`，`证据缺失 ≠ 物理不安全`；
- 所有安全阈值仍为 `PROVISIONAL`。

## 2. 对原 Claude 工作的审阅

以下三个已提交阶段可作为有效基线接受：

- `7371403`：Stage 0，22 份 E1.5 冻结证据快照；
- `9763a2d`：Stage 1–2，资产审计与六张基础图；
- `ae87f34`：Stage 3–5，交互浏览器、六支视频、证据图。

原 Stage 6 不能原样接受，已完成以下修正：

1. 原“单文件”仍引用 MP4/浏览器旁车文件；现六支 MP4、10 张图、交互浏览器与 Plotly 均在一个 HTML 内，静态扫描无网络或相对路径请求。
2. 补齐 I/S/B/M/E/T/D/G1/G2/G3 坐标系登记；明确 B 是自由漂浮母体基座，M 是 B601 安装面/URDF 基准。
3. 把 P2/P3 的几何 `IK_FAIL` 与物理超限分开：几何失败使用橙色，红色仅保留给已有数值证明的 `PHYSICAL_LIMIT_EXCEEDED`。
4. 原 v05 在构建阶段重新积分一个名义 ANCF 工况；现仅读取既有 CSV、两张聚合 PNG 和冻结失败记录，ANCF 执行数为 0。
5. 仓库没有保存节点/变形时序，因此 v05 明示 `NO_REPLAYABLE_TIME_HISTORY`，不插值、不合成柔性变形动画。
6. 清理 v05 带/不带 `.mp4` 的重复关键帧组；最终为六个视频、44 条唯一关键帧。
7. 原 4.86 MB explorer 作为超长 data URL 时在 Chromium 中显示空白；现以内嵌载荷写入 iframe，并复用父页内联 Plotly，首次加载由约 90 s 降至本机约 11 s，仪表板由 19.93 MB 降至 13.57 MB（十进制）。

## 3. 最终交付件

| 交付件 | 路径/数量 | 状态 |
|---|---|---|
| 单文件仪表板 | `40_evidence/artifacts/visualization/project_visualization_v0.html` | PASS；13,571,036 bytes；SHA-256 `1F66454100AFB0A66E31E042C52C6B2A570801B72217F8709A2B50CA225B3166` |
| 独立交互浏览器 | `40_evidence/artifacts/visualization/grasp_geometry_explorer_v0.html` | PASS；完全离线 |
| 静态图 | `40_evidence/artifacts/visualization/figures/fig_v01..v10*.png` | 10/10 |
| 回放视频 | `40_evidence/artifacts/visualization/videos/anim_v01..v06*.mp4` | 6/6；均为 1280×720 |
| 坐标系登记 | `40_evidence/artifacts/visualization/tables/frame_registry_v1.csv` | 10 行；单位四元数校验通过 |
| 材料索引 | `40_evidence/artifacts/visualization/tables/viz_material_index.csv` | 已更新限制条件与用途 |
| 自动验收报告 | `70_tools/project_visualization/tests/viz_gate0_test_report.md` | 6/6 PASS |

视频最终指标：

| 视频 | 时长 | 关键帧 |
|---|---:|---:|
| v01 target tumble | 30.042 s | 7/7 |
| v02 B601 approach | 20.000 s | 7/7 |
| v03 base reaction | 27.040 s | 6/6 |
| v04 capture impulse | 27.000 s | 8/8 |
| v05 flex diagnostic | 28.000 s | 8/8；ANCF 执行数 0 |
| v06 gate explanation | 36.000 s | 8/8 |

## 4. 验收证据

### 自动化测试

最终 `70_tools/project_visualization/tests/run_all.py`：**6/6 PASS**。

- 资产/单位：45 行完整；15 个渲染网格均声明为米；B601 尺度比验证无 1000 倍错误；
- 场景变换：16 个旋转矩阵，最大正交误差 `5.55e-16`，最大 `|det(R)-1| = 6.66e-16`；
- FK 对齐：22 个构型，最大位置误差 `0.000000 mm`，最大姿态误差 `0.000002 deg`；
- 回放一致性：44/44 关键帧匹配，六个视频各出现一次；
- 状态语义：四类重算 `3/3/66/0`，无非零 VERIFIED_SAFE 声明；
- 单文件合同：六支 MP4 字节级内嵌，explorer 载荷确定性内嵌，17 个标记请求目标均为 data URI，v05 静态防回归检查通过。

### 浏览器验收

- 干净 Playwright/Chromium 会话：页面约 11.2 s 完成首次加载；三种模式可切换；控制台 0 error（仅 1 条 Canvas2D 性能 warning）；
- 内嵌 explorer：P2 点击成功；几何行显示橙色 `IK_FAIL`（`rgb(217,119,6)`），动力学行显示“本轮无新鲜证据”；
- 六支内嵌视频：全部 `readyState=4`、`currentSrc=data:`、媒体错误为空；
- Chrome 直接从 `file://` 打开并成功截图：`C:\Users\stude\.codex\visualizations\2026\07\14\019f6089-b4a5-74c1-b524-3394c31329a4\direct-file-dashboard.png`。

### 输入保护

- 构建前后 45/45 个可视化输入资产 SHA-256 完全不变；
- 22/22 个冻结 E1.5 快照与保护清单 SHA-256 一致；
- 受跟踪改动仅位于 `config/src/tests/figures/videos/40_evidence/artifacts/tables` 的 `visualization` 专用目录；
- 未修改 CAD、URDF、既有仿真结果或 `30_simulation/sim_09_grasp_evaluator/src`；工作区内与本任务无关的未跟踪文件保持原状。

## 5. 重建记录

本次验收曾实际执行完整 `--all` 七阶段链，7/7 完成，耗时约 2,111 s；该执行暴露了旧 v05 的名义 ANCF 重积分。修正后实际重渲染 v05、重新构建 explorer/仪表板并重跑全部六项测试；最终 `--all --dry-run` 再次确认七阶段输出全部齐备。最终代码路径不再触发 ANCF 求解。

完整重建：

```powershell
python 70_tools/project_visualization/src/build_visual_dashboard.py --all
```

仅从现有可视化产物快速重建仪表板：

```powershell
python 70_tools/project_visualization/src/build_visual_dashboard.py --dashboard-only
```

## 6. 仍须保留的科学边界

- E1/E1.5 的 P1/P2/P3 属于 150 kg `target_debris_v0`，不是装配图中的 22 kg 合作目标卫星；
- 22 kg 目标卫星目前仅完成几何展示映射，未被 E1/E1.5 的 72 工况验证；
- v05 是只读证据卷，不是柔性变形时序回放；
- B 系的 `T_SB` 仍为默认单位变换/未验证，待实测质心偏置；
- 不得宣称 E2、G3、视觉/AprilTag 或 HIL 闭环已完成。

## 7. 工作区状态

本报告生成时，Codex 未暂存、未提交、未推送本轮修正；应由负责人审阅后决定是否形成新提交。
