# MECH-INVENTORY-AUDIT-01 报告

日期：2026-07-28（UTC）　性质：**只读审计**——未创建/修改任何 SLDPRT/SLDASM，
未重跑位姿优化，未重导 STEP，未修复文件，未写入既有证据目录，未提交 Git。
SolidWorks 以 **ReadOnly+Silent** 打开、`CloseDoc` 不保存。

盘点规模：**1112 个文件 / 340 个原生 SolidWorks 文件 / 63 个 `~$` 锁文件**（锁文件已单列，
不计入交付）。现场打开+重建核验 **9 个目标，两遍（含一次杀进程冷启动），结果逐项一致**。

---

## ⚠ 首要更正：原生 SolidWorks 基线的生产者不是 Codex

你的判断中有一条前提与证据不符，且它直接决定分工裁决，必须先摆出来：

| 证据 | 内容 |
|---|---|
| `V2_0/evidence/b3_00/HUMAN_APPROVAL_RECORD.yaml` | `APPROVAL_CHANNEL: "Claude Code 会话人工指令"` |
| V2_0 构建日志 | `b3_02_*.jsonl … b3_10_*.jsonl`（B3 战役） |
| V2_1 构建日志 / 自动化 | `b4_1_acceptance.jsonl`、`automation/b3_lib` + `b4_1_acceptance.py` |
| V2_2 构建日志 / 自动化 | `asset00_*.jsonl`、`automation/b3_lib` + `b5_*.py` |
| Codex 自述（100 目录） | "当前资源仅约 2.25 GiB 可用物理内存…**因此未启动可见 SolidWorks 恢复**，也未生成或伪造原生配置/BOM 读回" |

**结论**：V2.0(57)、V2.1(60)、V2.2(102)、V2.2_NATIVE(63) 共 **282 个原生 SolidWorks 文件
全部由 Claude Code 经 `b3_lib` COM 层产出**；**Codex 的原生 SolidWorks 文件数 = 0**。
Codex 的产出是 `100_Mechanical_Continuation`（STEP-first build123d，38 文件，0 原生件）。

这不是争功——它意味着你拟定的分工「Codex 负责 SolidWorks 原生单写入」会把工具链交给
一个**从未在本机启动过 SolidWorks 的执行体**，而其未启动的原因（内存）至今未变。
分工方案需要据此重新裁决（见 H 项）。

---

## A. 当前最完整、最稳定的原生 SolidWorks 基线是哪一版？

**没有单一版本同时最优**，两条候选各有明确长短（详见 `current_top_assembly_comparison.md`）：

| | V2_2 | V2_2_NATIVE |
|---|---|---|
| 原生件 | **102** | 63 (+2 图纸) |
| 顶层组件 | **15** | 7 |
| 配置 / **独立抑制态** | 9 / **6** | 9 / 3 |
| 主结构形态 | 366 站位实体 + C1 真实穿舱孔 | **框-纵梁-甲板-可拆板真骨架（接触面纪律）** |
| 翼根 | 实体机构 | **每侧 14 件，已按 Codex SOLAR-ROOT-01 站位对齐** |
| 全树干涉 | 本审计未复测 | **0（本轮实测）** |
| 负结果继承 | — | **C5 238.3>226.3、机构宽 302.3 已入参数** |
| 原生工程图 | 无 | **2 张 .SLDDRW（四视图+A-A 真剖）** |

四个候选（含 V2_0/V2_1）**均可打开、均重建成功、均零缺件、均无导入哑实体特征**。

**V2_1 的一个硬事实**：8 个配置的组件抑制状态**完全相同**（独立抑制态 = 1）——
七态在 V2_1 中没有几何区分，与其 `ACCEPTANCE_HOLD` 定性一致。

## B. Claude 实际生成了哪些原生 SolidWorks 资产？

全部 282 个：V2_0 57、V2_1 60、V2_2 102、V2_2_NATIVE 63（+2 SLDDRW）。
另有 V0_1 15、V1_0 32（早期，生产者未逐件核验，建议封存）。

## C. Codex 实际生成了哪些原生 SolidWorks 资产？

**零个**。Codex 产出为 `100_Mechanical_Continuation`：
`v22_mechanical_continuation.step`（132 occurrence / 122 实体）+ 设计合同 + 验证 JSON
+ 5 张快照，机器门 16 PASS / 6 HOLD / 2 NA / 0 FAIL。**价值高，但不是原生 CAD。**

`110_Layout_and_Deployment_01`（115 文件，0 原生件）同为 STEP-first build123d 风格，
**生产者未在文件内留下标识，本审计不臆断**，标为 `STEP_TRACK_PRODUCER_UNCONFIRMED`。

## D. 哪些对象被两边重复创建？

见 `claude_codex_overlap_matrix.yaml`。最需人工收敛的是**整星布局/七态存在三套**：
V2_2 顶装（9 配置）、V2_2_NATIVE 顶装（9 配置）、110 STEP staging（7 态策略）。
其余三处（B601 安装接口、翼根机构、ARM-STOW）**数值已对齐或已由真实几何取代**，非冲突。

## E. 哪些对象只有分析或 reference，没有真实机械实体？

- `120_PoseMap_02`、`130_VendorCAD_03`、`100_Mechanical_Continuation`、
  `110_Layout_and_Deployment_01`、`ASSET_00`、`B601_SWAP_01` —— **全部 0 原生件**
- `V2_2/35_B601_HiFi_Visual/` —— **空目录**：`B601_STOWED_HIFI.SLDPRT` 从未生成，
  证实 B601-SWAP-01 未完成（`HOLD_NO_MULTIBODY_PART`）
- `B601_MASS_SURROGATE` —— 全树无此件
- V2_1 翼根 —— 零实体 named-only（V2_2_NATIVE 已用 14 实体/侧取代）

## F. 哪个文件应成为下一阶段唯一顶层装配？

**按任务书禁止自动选择，此处只列两条路线与代价，待人工裁决：**

**路线 1：以 `V2_2/Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM` 为基线**
- 得：102 原生件、15 顶层组件、6 种独立抑制态、C1 真实穿舱孔、既有八态语义
- 失：需把 V2_2_NATIVE 的骨架化主结构、接触面纪律、翼根 Codex 站位对齐、
  零干涉、C5 负结果、原生工程图**全部移植过去**

**路线 2：以 `V2_2_NATIVE/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM` 为基线**
- 得：真骨架主结构、零未裁决互穿、翼根已对齐 Codex、负结果已入参数、原生工程图齐备
- 失：需补回 V2_2 的 GNC/推进/热控/通信/捕获头等设备件与 C1 开口
  （V2_2_NATIVE 第一阶段范围只到 A–F）

**审计倾向（供参考，非裁决）**：路线 2 的缺口是"加设备件"，路线 1 的缺口是
"改结构纪律+清 28 处互穿+补负结果"。前者是增量，后者是返工。

## G. 哪些资产必须封存而不是继续开发？

`V0_1`、`V1_0`、`_failed_builds`、`130_VendorCAD_03`（保留为 B601 几何来源、
时钟角候选与诊断证据）、`120_PoseMap_02`（LOD2 已被真实厂商几何取代）。

## H. 下一阶段五个最小机械交付物

1. **人工选定唯一顶层装配**（F 项两条路线择一）——不选定就继续建会产生第四套并行模型
2. **B601 三表示**：`B601_STOWED_HIFI`（几何权威=vendor STEP，质量 EXCLUDED）、
   `B601_KINEMATIC_PROXY`（URDF 权威）、`B601_MASS_SURROGATE`（URDF 质量/惯量权威）
   —— 三者中前两者当前**均不存在或仅 bbox 级**
3. **翼板本体子装配**（substrate / perimeter frame / cell-area / junction box）——
   翼根已实体化但翼板本体不在第一阶段，缺它就无法闭合 C5 超宽
4. **设备件补齐**（前任务面板、捕获头壳、视觉窗、推进座与喷管、面板分缝、维修盖）
5. **收拢 Z 包络人工裁决 + 接触面分类**（allowable-contact vs required-clearance）——
   这是唯一能把 STOW_VECTOR 从 CANDIDATE_HOLD 推进的前置

### 关于分工（对你 H 项建议的修正意见）

原方案「Codex 单写 SolidWorks / Claude 只做分析」在证据面前不成立：
Codex 在本机**从未启动过 SolidWorks**，且其自述阻塞原因（内存 2.25 GiB）至今未变；
而 `b3_lib` COM 层（含 makepy 早绑定、9 项本机坑位规避）在 Claude 侧已验证 282 文件。
**建议改为**：Claude 继续单写 SolidWorks（工具链在此）；Codex 承担 STEP-first
几何来源、独立验证与红队复核（其 100 目录的负结果保全质量很高）；
人工保留 clock/Z 包络/接触面/接口裁决权。

---

## 审计裁决

```
AUDIT_COMPLETE_READY_FOR_HUMAN_BASELINE_SELECTION
```

9/9 目标现场打开+重建通过、零缺件、两遍（含冷启动）读回一致；
七件套输出齐备；基线选择按任务书交还人工。

## 输出清单

`artifact_inventory.csv`（1112 行）· `solidworks_native_matrix.yaml` ·
`claude_codex_overlap_matrix.yaml` · `supersession_graph.md` ·
`current_top_assembly_comparison.md` · `blocked_mechanical_functions.yaml` ·
本报告 · 原始数据 `inventory_walk_summary.json` / `sw_open_rebuild_check.json`
/ `sw_open_rebuild_check_run1.json`

## 本审计的限制

- 340 个原生件中**只对 9 个关键顶装/子装配做了现场打开**；其余按扩展名+区域归类，
  未逐件开验（任务书要求的"必须现场打开"清单已全覆盖）。
- `110_Layout_and_Deployment_01` 生产者未确认，不臆断。
- V2_0/V2_1/V2_2 的全树干涉**未在本审计中复测**（只读约束下不重跑既有 Gate）；
  仅 V2_2_NATIVE 有本轮实测 0 干涉。
- 早期 V0_1/V1_0 未做特征级核验。
