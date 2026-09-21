# V5R-RAPID 执行合同（Codex Phase 2+ 用）

- 合同建立：2026-08-20T04:52:28Z
- 依据：负责人 2026-08-20 执行提示词（`MODE: ISOLATED-WRITE / EVIDENCE-DRIVEN / FAIL-CLOSED`）
- 前置回执：[BACKUP_RECEIPT.json](../07_evidence/BACKUP_RECEIPT.json)、[INPUT_MANIFEST.json](INPUT_MANIFEST.json)、[WRITE_BOUNDARY.md](WRITE_BOUNDARY.md)、[LOOP1C1_OWNER_RULING_DRAFT.json](LOOP1C1_OWNER_RULING_DRAFT.json)

> **本合同在两项负责人裁决（L1C1-R1、L1C1-R2）签署前不得进入 Phase 2。**
> Phase 0 与 Phase 1 已由主智能体完成并核验，Codex 不需要重跑。

---

## 0. 交给 Codex 前必须先读的四项前提修正

原提示词里有四条假设已被本轮实测证伪。**Codex 若照原文执行会做错决策**，因此这四条优先于提示词正文：

### 修正 1 — Loop1C1 的 A/B/C 不是待决项

原文要求"读取 A/B/C 原文并选出匹配字母"。实况：**Option A 已于 2026-08-11 由负责人签署（`现在先执行A`）并执行完毕**，合同在 `V5_LOOP1C1_EXCEPTION_CONTRACT.yaml`。

- 三案原文与逐条原则映射已完成 → `LOOP1C1_OWNER_RULING_DRAFT.json`
- 匹配字母 = **A**（A 满足落在 Loop1C1 范围内的全部原则条款）
- 真正未决项 = **36 行 pose-induced 干涉**（OPEN 24 行 1266.93 mm³ / PREGRASP 12 行 779.63 mm³），签署的 A 修正案**不覆盖**它们
- Codex **不得**重新征询字母，也不得改写既签合同

### 修正 2 — V4 不是"全局几何"

原文写"采用 V4 中性 CAD 作为全局几何输入"。实况：V4 `02_neutral_cad/` 只有 **23 个 STEP**，内容是转接件、keep-out 包络、收拢支撑、翼根接头、夹爪 STL。

- **没有舱体主结构、没有太阳翼板、没有臂连杆**
- V4 自己的 Gate 声明范围是 `F3R2_V4_COMPETITION_NEUTRAL_MECHANICAL_DESIGN_BASIS`（delta 集），C14/C15/C16 全 HOLD
- 舱体与舱板的真实出处是 **`cad/Space_Embodied_Robot_CAD_V2_2_NATIVE/`（61 个原生 SLDPRT）**
- 原文的组件树（`BUS_PRIMARY` / `SOLAR_ARRAY_LEFT/RIGHT` 来自 V4）**按字面不可满足**，必须改为 V2_2 供源

### 修正 3 — V5 不是空白，已有 49 零件 + 10 子装配

原文按"V5 顶层不存在、需重建"估算成本。实况：

| 资产 | 数量 |
|---|---|
| 原生零件 SLDPRT | 49 |
| 原生子装配 SLDASM | 10 |
| LOOP1E staging 顶装（27 MB × 2） | 2 |
| 工程图 / 截图 / Pack-and-Go | 0 / 0 / 0 |

已存在的子装配包含 **`B601_GRIPPER.SLDASM`（Loop1C1 产物，四构型带驱动棱柱钳口）**、左右翼根真铰链、G07/G08/Mid 三支撑、`B601_BASE_ADAPTER_REV_B2`。

**"目标顶层 SLDASM 不存在"指的是目标文件名不存在，不是完全没有顶装。** 真实缺口是：工程图、截图、Pack-and-Go、以及顶装的最后一步提交。

### 修正 4 — Loop1E 死于 COM 绑定缺陷，不是内存、不是几何

原文把 V5 失败部分归因于低内存并建议放弃该路线。最后一次 Loop1E（2026-08-13T15:47:20Z）的实际死因：

```
V5_LOOP1E_UNEXPECTED_EXCEPTION
(-2147352567, '发生意外。', (61836, 'SOLIDWORKS', '无法读只写属性。', ..., 455052, 0), None)

execute:3509 → build_top:3013 → build_motion_contract:2807
             → relative_transform:2613 → IMathTransform.IInverse()
```

**这与本项目已两次解决过的 `IMateEntity2.Reference` 是同一类 makepy 静态绑定缺陷**（见 `V5_LOOP1C1_FIX_PROPOSAL_20260810.md` §2 第 6 项：改用后期绑定动态派发即可拿到返回值）。

失败前已通过：G0 session-B 冒烟回执、静态执行就绪审计、LOOP1C/LOOP1D 阶段审计、SOLAR_R2B_P9 提升、本地臂六关节 limit-angle 驱动器（冷开 errors 0 / warnings 0）。

**结论**：这是一处可能很小的可修缺陷，不构成"原生路线不可达"的证据。Codex 必须把"修 `IInverse` 后重跑 Loop1E"与"另建 V5R 轻量树"作为**两条候选**做成本对比，不得默认后者。

---

## 1. 本轮唯一写入目录

```
20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/
```

只读边界与长路径规程见 [WRITE_BOUNDARY.md](WRITE_BOUNDARY.md)。三条操作纪律（血泪换来的）：

1. **哈希清单禁用 `git ls-files`** —— `core.longpaths` 未启用，git 少看见 196 个文件（439 个路径超 260 字符，最长 348）。一律用 `99_tools/V5R_PHASE0_HASH_MANIFEST.py`。
2. **robocopy 必须 `MSYS_NO_PATHCONV=1`** —— 否则 Git Bash 把 `/E` 改写成 `E:/`，robocopy 什么都不拷而 shell 仍报 exit 0。
3. **冷备份只能落 E:（Disk 0）** —— G: 与 F: 同属物理 Disk 1，往 G: 备份等于假灾备。

## 2. 内存门（当前实测阻断）

- 门限：≥ 6.0 GiB 可用物理内存；此前人工 override 不计为门通过
- **2026-08-20T04:52Z 实测：可用 1.14 GiB / 共 15.21 GiB，SLDWORKS 进程 0**
- 即：**此刻原生 SolidWorks 工作被内存门阻断**，与其他任何裁决无关
- SolidWorks 启动前必须重测并写入回执；连续两次内存型崩溃即停止攻击同一路线，转 `NEUTRAL_CAD_PROTOTYPE_BASELINE_CLOSED_NATIVE_CAD_HOLD`

## 3. 固定工程裁决（沿用原文，含修正）

1. 不在原 V5 目录原地修补 —— 但**允许只读引用其 49 零件 / 10 子装配**（修正 3）
2. 不重建完整 166 零件 B601 donor 原生树
3. 不修改 accepted URDF（质量真值 4.695555949 kg，CAD 计算值只作 comparison）
4. 不修改 V2_2_NATIVE donor —— 但它是舱体/舱板的**唯一供源**（修正 2）
5. 不修改 F3R1/F3R2 冻结顶装
6. 不修改既有 Gate JSON 与阈值 registry
7. V4 作为**接口与 delta 几何**输入，不是全局几何（修正 2）
8. accepted B601 URDF = 拓扑/关节/质量真值
9. `M3R_INTERFACE_AUTHORITY_GATE.json` + `M3R_ADAPTER_INTERFACE_SSOT.yaml` = 臂侧物理接口真值
10. 原 V5 作失败证据与建模参考

## 4. M3R 接口真值（禁止再用 8×M3）

```
4 × M4-class，64 × 64 mm 方形布局
等效 PCD             90.509641772 mm
绕航天器 X 定位角      25.000014°
最佳拟合中心 (y,z)    [0.015994151, -0.08636607] mm
转接件通孔 / 沉孔      Ø4.6 / Ø7.5 mm
连续安装面            不存在（continuous_mount_face_present_in_active_top = false）
```

**注意与原文组件树的差异**：原文写 `M3R_STANDOFF_01..04`（四个凸台）。而既有权威架构是 **Stage A 环 + Stage B 载荷扩散板**：

| 级 | 件号 | 关键尺寸 |
|---|---|---|
| Stage A | `B601_BASE_INTERFACE_RING_F3R2` | AL6061-T6，Ø150 外径，Ø40 中央通道，厚 8.0，环形载荷裙 Ø150/Ø100.6 |
| Stage B | `B601_LOAD_SPREADING_ADAPTER_F3R2` | AL6061-T6，160×160 底板，厚 12.0，中央承接孔 Ø100，止口径向间隙 0.2 |

过渡紧固 8×M5 @R62.5，定位 = 中央止口 + 1×Ø4.1 非对称销 @(55,0)，航天器侧 4×M6 @140×140（`COMPETITION_PRIMARY_LOAD_PATTERN_CANDIDATE`）。

**Rev-B2 几何已存在于 V4 STEP**（`V4_B601_TWO_STAGE_ADAPTER_REVB2.step` 等 3 件，B-rep 已独立校验，Stage A/B 接触无穿透，M6 净韧带 11.7 mm，provisional 质量 761.904197 g）。**V5R 不需要从零设计转接件，只需导入核验。** Codex 必须先解决"四凸台 vs 环+扩散板"的架构冲突再动手。

## 5. Phase 2+ 执行序（原文照录，加前置条件）

| Phase | 内容 | 前置 |
|---|---|---|
| 2 | 建立 V5R 机械架构与顶层装配 | L1C1-R1 + L1C1-R2 已签 **且** 内存 ≥6 GiB **且** 修正 2/3/4 已消化 |
| 3 | B601 简化原生模型（10 links / 9 joints / 6R+1fixed+2P） | Phase 2 |
| 4 | M3R 两级转接（解决架构冲突后） | Phase 2 |
| 5 | 构型闭合（含 PARTIAL 与 STOWED 132.72 mm 超包络处置） | Phase 3+4 |
| 6 | 质量/惯量/坐标映射 + 等效惯量重算 + 结构筛查 | Phase 5 |
| 7 | 工程图 / BOM / Pack and Go / 22 张截图 | Phase 6 |
| 8 | `V5R_RAPID_MECHANICAL_GATE.json` 交负责人审查 | Phase 7 |

### Phase 5 两个不可回避项

- **PARTIAL 与 DEPLOYED_NOMINAL 几何不可区分** —— 不得保留"不同名同几何"的假构型
- **STOWED 超包络 132.72 mm** —— 只有两种合法结果：(A) 改到满足包络；(B) 正式写入 `EXCLUDED_FROM_ACCEPTED_BASELINE` **并把终裁降级为 `DEPLOYED_PROTOTYPE_BASELINE_ONLY`**。禁止同时"排除 STOWED"又宣称全构型闭环。

### Phase 5 干涉排除必须两类分账（不是一类）

原文写"donor 内部 81 处不计入外部干涉，逐项保留"。**81 是 donor 零件的静态内部计数，不含那 36 行 pose-induced。** 混为一类会把真实缺陷洗进"既存 donor 几何"标签。必须：

| 类 | 行数 | 依据 | 可声明为 |
|---|---|---|---|
| CLASS_1 донor 继承静态 | 84 | 6 位小数逐位吻合 donor 体积 | 已文档化的 donor 继承接触界面 |
| CLASS_2 pose-induced articulation 缺陷 | 36 | 无 donor 体积对应，随行程单调增长 | **不可声明任何东西**，挂 `B601_GRIPPER_PALM_RAIL_SLOT_GEOMETRY_HOLD` |

CLASS_2 禁止声明：`GRIPPER_OPENS_WITHOUT_SELF_COLLISION`、`ALL_GRIPPER_INTERFERENCE_IS_DONOR_INHERITED`、`GRIPPER_INTERNAL_GEOMETRY_VALIDATED`。

## 6. Gate 规范

终裁文件 `08_gate/V5R_RAPID_MECHANICAL_GATE.json`，字段照原文。硬约束：

- `next_stage_authorized` 必须是**真布尔** —— 禁止字符串 `"true"` / `"false"`（既有 Gate 存在字符串型授权与 `PENDING_HUMAN_REVIEW` + `next_stage_authorized=true` 并存的 fail-open）
- `review_status` 只能由负责人改为 `ACCEPTED`；机器不得自写
- 不得修改旧 `G8_FINAL_FREEZE`（当前 `NOT_AUTHORIZED`），另建 `G8R_COMPETITION_PROTOTYPE_MECHANICAL_BASELINE`
- 保留 `flight_qualification: HOLD`
- 不得把 competition prototype PASS 传播为 flight PASS

建议终裁：`COMPETITION_PROTOTYPE_MECHANICAL_BASELINE_READY_FOR_OWNER_ACCEPTANCE_WITH_FLIGHT_QUALIFICATION_HOLD`

## 7. 停机条件（原文 14 条 + 本轮新增 2 条）

原 14 条全部保留。Phase 0 已实测通过：可核验备份 ✅、冻结哈希未变 6/6 ✅、未开 SolidWorks ✅、未改预存资产 ✅。

新增：

15. **内存门未过即禁止启动 SolidWorks** —— 当前 1.14 GiB，实测阻断
16. **CLASS_2 的 36 行被并入 CLASS_1 单一标签** —— 即触发停机

## 8. 执行节奏

最多四个只读/隔离子任务（A 权威+Loop1C1 / B URDF-CAD 映射 / C M3R 接口与构型 / D 验收图纸 Pack Gate）。**SolidWorks 会话只能由主智能体独占。** 每轮汇报必须含：实际创建文件、实际修改文件、PRE/POST 哈希、PASS/HOLD/FAIL、下一步、是否需要负责人裁决。

## 9. 附：卡在 Loop1E 的那个 COM 缺陷

若选择"修 Loop1E"路线，缺陷点与已知解法：

```python
# 99_tools/F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py:2613
inverse_raw = first_transform.IInverse()   # makepy 静态绑定 → 61836 无法读只写属性
```

本项目对同类缺陷的既有解法（FIX_PROPOSAL §2.6）：改用后期绑定动态派发取值。另注意 §2 已记录的相关陷阱：配置切换后组件/特征句柄必须重取（否则 `Transform2` 读零），`GetSystemValue2` 在新句柄上回读滞后一次写入。
