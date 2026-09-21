# F3 机械终局审计 — 首次进度报告

**审计标识：** `F3_MECHANICAL_TERMINAL_STATE_AUDIT_AND_HUMAN_VISUAL_REVIEW`
**执行日期：** 2026-08-06 · **授权范围：** 哈希复核 + CAD 只读打开 + 第一批截图
**本报告不构成 Gate 裁决，不修改任何冻结资产。**

---

## 1. §18 要求的十八项字段

| 字段 | 实测值 |
|---|---|
| 项目根目录 | `F:/China Graduate Future Flight Vehicle Innovation Competition` |
| Git HEAD | `b75352c1c226c0f3e9a4bc9c469b766e06f41616` |
| 当前分支 | `publication/stage3-integrity-closure` |
| 审计输出目录 | `20_engineering/F3_MECHANICAL_TERMINAL_AUDIT_20260806/`（新建，无同名冲突） |
| 找到的最终 Gate | `10_submission/F3_P5_TERMINAL_CLOSURE.json` → `F3_MECHANICAL_ARCHITECTURE_AND_COMPETITION_PROTOTYPE_CLOSED_CONTROL_AND_EMBODIED_HANDOFF_READY_AL_HOLD` |
| 找到的 SHA-256 清单 | `10_submission/F3_P5_TERMINAL_MANIFEST_SHA256.txt` |
| 清单声明文件数 | **46** |
| 实际找到文件数 | **46**（无缺失） |
| 当前已复算文件数 | **46/46，全部 MATCH，零漂移** |
| accepted URDF 路径与 hash | `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`<br>`408147DD…03B5A3A4` — **与基线逐位一致，未变化** |
| 质量账本路径与 hash | `20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv`<br>`073C8025…D0899392` — **未变化** |
| 当前权威顶层 CAD 路径 | ⚠️ **存在分歧，见 §3**。<br>登记为"装配"的是 `F:\Space-Embodied-Robot-HAG_A_20260804\…\15_f3_p3_top_assembly\SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3.FCStd`（**零几何**）；<br>唯一含几何的是同目录 `F3_P3_TOP_ASSEMBLY.FCStd`（206 实体，**不在任何清单内**） |
| CAD 是否成功只读打开 | **是**，FreeCAD 1.1.3（`G:/Windows_program_file/FreeCAD/bin/FreeCAD.exe`），206 对象 |
| 打开时是否有缺失引用 | 无外部缺失引用（几何内嵌为 206 个 `.brp`）；但有 **3 个 `INVALID_SHAPE`**，且文档打开即 `isTouched=True`、`mustExecute=True` |
| **保存调用次数** | **0**（宏内不含任何 `save`/`saveAs`；`closeDocument` 前 `save_calls=0` 已记录） |
| 已生成的第一批截图 | `03_screenshots/RAW/`：`S01_STOWED_ISOMETRIC`、`S02_STOWED_TOP`、`S03_STOWED_SIDE`、`S04_STOWED_FRONT`、`S13/S14/S15`（鞍座探针）共 7 张，1920×1080 |
| 当前发现的最高问题级别 | **R3（机械架构级）** — 详见 §3，共 **4 项 R3** + 2 项 R2 + 1 项 R1 + 2 项 R0 |
| 下一步唯一动作 | 提交本报告，等待人工确认 §3 四项 R3；不自行推进第二批图册 |

---

## 2. 已确证为真的部分（声明成立）

| 声明 | 核验结果 |
|---|---|
| 46 文件 SHA-256 清单覆盖 | ✅ **46/46 重算匹配，零漂移**（`00_authority/F3_TERMINAL_SHA256_RECHECK.json`） |
| 终局裁决已签发 | ✅ 文件真实存在，七级 Gate 链完整 |
| HOLD 已回写 | ✅ 10 项：8 项 CLOSED/CLOSED_COMPETITION，HOLD-04/06 诚实保留 `OPEN_TBD_NO_AL_SOURCE` |
| accepted URDF / 质量账本未变 | ✅ 逐位一致 |
| donor 未被修改 | ✅ `V2_2_NATIVE` 全 108 文件逐位匹配 |
| 外部飞行资格 HOLD 诚实保留 | ✅ `AL_NOT_AUTHORIZED_NO_SOURCE`、四项 `explicit_non_claims`（NOT_FLIGHT_RELEASED / NOT_QUALIFIED / …）均在册 |
| 三鞍座冻结坐标 | ✅ G07 x[-20,0] 顶面 z=261.08、G08 x[160,180] z=209.42、Mid x[80,100] z=214.92 —— **在 CAD 中逐位复现** |

**这一部分的治理质量是高的**：负面结论没有被粉饰，AL 无来源被明写，非声明清单齐全。

---

## 3. 发现的问题（按级别，均需人工裁定）

### 🔴 R3-01：被登记为"顶层装配"的文件里没有任何几何

`SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3.FCStd`（26.7 KB）：

- `.brp` 实体文件 **0 个**；442 个对象全是 `App::Part`/`App::Origin`/`App::Line`/`App::Plane` 空容器（48 组）
- 10 个 `App::Link` 的 XLink 目标文件名与目标对象名**均为空字符串**
- `f3_p3_top_assembly.log`：**15 个组件的 `COMPONENT_ADD` 全部 `ERROR`**
  （`Property …#spacecraft_reference.Type already exists` 等），包括 `g07_aft_saddle`/`g08_fwd_saddle`/`mid_saddle_candidate`/`hdrm_envelope`/`camera_fov`
- 尽管如此，同一脚本仍写出 `"stage": "SCRIPT_PASS", "components": 15, "states": 23`，
  且 `F3_P3_TOP_ASSEMBLY_RESULT.json` 顶层为 `"status": "PASS", "exceptions": []`

→ **顶层 PASS 与逐项 ERROR 并存**：状态机 23 态 `ADDED` 是真的（纯属性），组件几何 0 件也是真的。

### 🔴 R3-02：冻结的 CAD 基线摘要描述的不是工程在用的那份

`baseline_freeze_manifest.yaml` 自身未被改动，但：

- 它声明 `source_root: Space_Embodied_Robot_CAD_V2_2_NATIVE`、`unchanged_proof: PASS`
- 其 108 条摘要对 **donor 根 108/108 匹配**
- 对它所在的 `V2_3_NATIVE_INTEGRATION` 根：**106 匹配 / 2 不匹配**
- 不匹配的其中一项正是 `canonical_top`：
  声明 `30c09b50…`，V2_3 实测 `76a3b289…`（706,675 B vs donor 705,386 B）

→ **工程实际集成用的顶层 SLDASM 没有受控摘要**；"基线无漂移"成立于 donor，不成立于集成副本。

### 🔴 R3-03：真实装配中臂未装成，且存在悬浮件

只读打开 `F3_P3_TOP_ASSEMBLY.FCStd`（206 实体，唯一有几何者）后逐图核实：

- 星体为矩形箱体，**B601 仅基座关节装在前端框**，link1–6/腕/末端执行器**未接入装配**
- 顶视图可见 B601 的零件（两组带螺栓法兰的旋转关节、尖锥件、电机件）**散落在星体周围与上方，不与任何结构连接**
- 侧视图可见一组精细夹爪/滑块机构**悬在星体外部**
- 一个 z=264.08–354、体积 2.91e6 mm³ 的大方块（`native_STOWED046`）**悬浮于三鞍座之上**，
  由细柱连向星体 —— 属占位包络体，非工程结构
- **无太阳翼几何**（V2_3 中 `05/06_Solar_Array_Root_*` 存在，但未进入这份装配）
- 3 个 `INVALID_SHAPE`：`Part__Feature033`、`Part__Feature091`、（第三项见 JSON）

### 🔴 R3-04：S3 的承托关系在真实装配中不成立（本轮最重要的定量结果）

`02_configuration/F3_SADDLE_GAP_BBOX_ANALYSIS.json`（由只读打开导出的 bbox 计算）：

| 鞍座 | x 区间 | 顶面 z | 与冻结值 | 尺寸 | 顶面之上最近实体 |
|---|---|---|---|---|---|
| G07 (`native_STOWED041`) | [-20, 0] | 261.080 | **逐位吻合** | 20×60×147.9 mm | **占位包络块，间隙 3.0 mm** |
| G08 (`native_STOWED043`) | [160, 180] | 209.420 | **逐位吻合** | 20×60×96.3 mm | **无任何实体** |
| Mid (`native_STOWED042`) | [80, 100] | 214.920 | **逐位吻合** | 20×60×101.8 mm | **无任何实体** |

三项结论：

1. **位置正确，承托关系不存在。** 三鞍座的 x 区间与顶面 z 与冻结 S3 基线逐位吻合 ——
   坐标是真的。但 G07 顶面之上 3.0 mm 处**只有那个占位包络块**（`native_STOWED046`，
   z 264.08–354，2.91e6 mm³），G08 与 Mid 顶面之上**空无一物**。
   → 冻结 Gate 声明的 `g07_role: primary_support` / `g08_role: primary_support`
   在这份装配里**没有被承托对象**。

2. **Mid 的 2 mm 名义非接触无法评估。** 判定结果为
   `NO_SOLID_ABOVE_FOOTPRINT_CANNOT_EVALUATE` ——
   不是"间隙不对"，而是**没有对手件可以形成间隙**。
   §15 第 8 问（Mid 是否保持 2 mm 名义非接触）**当前无有效几何证据**。

3. **三鞍座截面完全相同**（均 20×60 mm），只有高度不同 → 属拉伸方柱占位，
   非承托鞍形面（登记为 R1-01）。

> ⚠️ 方法限定：bbox 间隙是真实表面间隙的**上界**，正间隙可证"不可能接触"，
> 零间隙只证"可能接触"。此处三项结论均依赖"上方无实体"这一**存在性**判断，
> 不受 bbox 保守性影响。

---

### 🟠 R2-01：F3-P3 的间隙/FOV 数值不是对 CAD 装配算的

`f3_p3_g8a_clearance.log` 首行即 `{"stage": "URDF_LOADED", "joints": 9}` —— 间隙由 **URDF 运动学**计算，全程未加载 CAD 装配。后果：

- `CL-02_ARM_TO_SOLAR_BOX` 与 `CL-03_ARM_TO_DEPLOYING_WING`：
  `min_clearance_mm = Infinity`、`clearances_at_min = {}` → **空比较集判 PASS（fail-open）**
- 根因已确证：accepted URDF 中 `grep -ic "solar|wing|panel"` = **0**，
  **无帆板几何可参与比较**，所以"臂—帆板间隙"从未被真正评估
- 5 条路径中 `STOW_TO_CLEAR`、`CLEAR_TO_DEPLOYED` 被 `state_not_defined` **跳过**，
  仍写 `"all_pass": true`
- 因此 §15 第 10 问"太阳翼—机械臂时序是否在真实装配中成立"
  → 目前**无有效证据支持**，`CAMERA_FOV_REPORT` 中"翼在两侧不遮挡"同属未经几何验证的表述

### 🟠 R2-02：6×6 刚度矩阵是解析近似，不是 FEA 提取

`F3_P5A_MATRIX_QUALITY.json` 自述：

```
"model": "M0_BEAM_SHELL_LOAD_PATH_MODEL"
"assumptions": ["Cantilever beam with springs",
                "Diagonal dominant compliance (simplified)",
                "No coupling between translation and rotation", ...]
```

矩阵为**纯对角**（非对角元全 0），`symmetry_error = 0.0` 是恒等结果而非验证结论。
这与终局 JSON 的 `6x6_coupling_terms: "NOT_EXTRACTED (analytical approximation)"` 一致——
**已被诚实登记**，但作为 F4 控制输入使用时必须带此限定。

---

## 4. 对"C 复核 9/9 PASS"的核验

`F3_C_POST_CLOSURE_REVIEW.json` 的 10 项结果字段全为 PASS/PRESENT，其中
`"baseline_hashes_drift": "NONE (46/46 manifest files match)"` —— **本审计独立复算确认此项为真**。

但需注意两点：

1. 该文件**本身不在 46 文件清单内**（生成于 2026-08-06，晚于清单），属清单外的自证文件；
2. 其 scope 限于 "Wave0 hash + Wave3 UL_FZ smoke"，**未覆盖 CAD 装配几何有效性** ——
   R3-01/R3-03 落在其检查范围之外，因此"9/9 PASS"与本审计发现不矛盾，是**检查面不同**。

---

## 5. 冻结资产未被修改的证据（本轮）

| 项 | 证据 |
|---|---|
| 保存调用 | **0** —— 宏源码不含 `save`/`saveAs`/`recompute+save`；运行日志 `CLOSED_WITHOUT_SAVE, save_calls=0` |
| 46 文件 | PRE 复算 46/46 MATCH（本轮唯一一次全量复算，作为 PRE 与 POST 共用基准） |
| accepted URDF / 质量账本 | 只经 `Read`/`grep`，哈希与基线逐位一致 |
| donor | 未打开；108/108 仍匹配 |
| 审计产物位置 | 全部写入 `F3_MECHANICAL_TERMINAL_AUDIT_20260806/`，**未写入任何冻结目录** |
| CAD 进程 | 宏结束调用 `getMainWindow().close()`；打开前后仅 `sldworks_fs.exe`（SolidWorks 文件服务，未被本审计启动） |

⚠️ 一项需登记的事实：`F3_P3_TOP_ASSEMBLY.FCStd` 打开时 FreeCAD 报告 `isTouched=True`、
`mustExecute=True`（因 3 个 INVALID_SHAPE 触发重算标记）。**我们未执行 recompute、未保存**，
故磁盘文件不变；但这说明该文档**处于"打开即需重算"的不稳定状态**。

---

## 6. 本轮授权范围内尚未完成项（诚实登记）

- Mid 2 mm 名义非接触的**真实装配**判定：脚本已就绪（`99_tools/analyze_saddle_gaps.py`），
  因执行环境权限拦截未跑完；bbox 数据已在 `01_native_cad/F3_TOP_ASSEMBLY_OPEN_REPORT.json` 中
- 鞍座单件隔离图（S13/S14/S15 现含占位包络块干扰，宏 v3 已就绪）
- HDRM 锁定/释放两态图：**V2_3 中 HDRM 件仅存在于帆板根部**
  （`HDRM_Base_1/2_*`、`HDRM_Rod_1/2_*`），而帆板未进入顶层装配 → 预判需标
  `MANUAL_CAPTURE_REQUIRED` 或 `GEOMETRY_ABSENT_FROM_TOP_ASSEMBLY`
- SolidWorks 侧原生打开（`F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe` 已定位，本轮未启动）
- FEA 证据截图（12 个 `.frd` 已确认存在于 `04_fea/06_calculix_results/`，未读取）

---

## 7. 本轮不做的裁决

按 §19 结束边界，本报告**不**给出最终机器裁决。理由：R3 级问题已出现 3 项，
但其中 R3-01/R3-03 涉及"CAD 装配是否只是可视化占位、真实工程意图为何"，
这需要项目负责人确认**原始设计意图**后才能区分是"记录失真"还是"架构失效"。

按 §16 推荐逻辑，若 R3 三项经人工确认成立，对应裁决将是：

```
F3_MECHANICAL_REOPEN_REQUIRED_VIA_ECR_F4_HOLD
```

但本轮**不写入该裁决**，等待你对 §3 三项 R3 的确认，以及是否授权第二批（完整图册）。
