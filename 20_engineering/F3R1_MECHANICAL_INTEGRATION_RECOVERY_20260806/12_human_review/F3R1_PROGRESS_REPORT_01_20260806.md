# F3R1 机械集成恢复 · 首份实质进度报告（P1）

**日期：** 2026-08-06 · **ECR：** ECR-F3R1-001 · **循环：** 第 1/3 轮
**范围声明：** 本报告只陈述已执行的可核验机械集成结果，不升级任何科学 Gate，不声称飞行资格，人工签署栏留空（不伪造）。

---

## 0. 一句话结论

已在隔离候选目录内构建出**单一原生顶层装配** `F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM`，其中 B601 六轴臂为**一条连续刚性链**（不再散落），与航天器主结构、太阳翼、三鞍座同处一装配、可开可查可截图；同时根因定位并修复了两处会静默污染装配的 SolidWorks COM 缺陷。**收拢位相对鞍座为负间隙（穿模），列为 P6 HOLD，未消解。**

## 1. 本轮修复的两处根因（均经独立探针证明）

### 缺陷 A — 原始 list 传入 CreateTransform 静默损坏非单位变换
`IMathUtility.CreateTransform(python_list)` 对任何非单位矩阵产出错误变换（表现为 1.98 m 的"空写入"，组件其实没动）。共享 `b3_lib` 的 IDENT16 路径只因单位阵能幸存而"看起来能用"。
**修复：** 移植 donor 原语——先包成 `VARIANT(VT_ARRAY|VT_R8)` 再 CreateTransform，并对 ArrayData 回读做 1e-12 fail-closed；写入用 `SetTransformAndSolve3(xf, True)`，不用 `Transform2 =` 属性。
**结果：** 收拢位回读 **3.33e-16 m**、离群组件 **0**、顶层臂挂载插入误差 **0.0 m**、时钟符号打分首次分化（+1=-1614 优于 -1=-2162）。

### 缺陷 B — AddConfiguration2 的 LinkToParent=True 让新配置共享默认配置的位置
第一轮把收拢位写入 STOWED 配置后，**默认配置**被甩飞（跨度 2236 mm、Z=-2651 mm），`p2_arm_binding` 从 `G2_PARTIAL_REVOLUTE_OK` 翻为 `G2_FAIL`。我最初误判为"Transform2 全局共享"。
**决定性证伪（`diag_config_leak_test.py`，全程不保存、哈希核验）：** 改用 donor 配置标志 `AddConfiguration2(..., False, False)` 后，写收拢位（3.33e-16 m）时默认配置漂移 **0.0**。故组件位置**本就是按配置隔离的**；真凶是我原调用尾部的 `True`（LinkToParent），把新配置的位置链回了默认配置。
**修复：** 三处 `AddConfiguration2` 全部改为 donor 标志 `False, False`（P3 顶层、P4 臂、P4 顶层配置）；并加**fail-closed 默认守卫**——重激活默认配置、若漂移 > 1e-6 拒绝保存（旧代码只记录漂移仍照存，正是缺陷所在）。

## 2. 交付物（首张真实原生截图，非计划/非空装配）

- 顶层装配：`03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM`
  （SHA-256 `5F1CB650…C0F9ACF3`，冷重开含 3 配置：`STOWED_LOCKED` / `DEPLOYED_NOMINAL` / `默认`）
- STEP（配置绑定 STOWED_LOCKED）：`03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_STOWED.step`
- 见证渲染（FreeCAD 1.1.3 pinned，459 shapes）：`11_screenshots/RAW/` 下 S01 ISO / S02 顶 / S03 侧 / S04 前 共 4 视图
- **顶视图 S02（最完整见证）**：清晰可见**左右两片太阳翼**（各带翼根 HDRM 配件）+ 航天器中心框架 + **B601 折叠六轴链**同处一装配。
- ISO 图 S01：航天器主框架 + 中心 boss + 相机箱 + 一侧太阳翼（另一侧因视角遮挡）+ **B601 从高位挂载沿右侧连续下垂至夹爪的完整六轴链**——与上一轮腐化图中三处飞散零件形成鲜明对照。

## 3. 独立验证（复核用命令均可复现）

| 检查 | 工具 | 结果 |
|---|---|---|
| 收拢位刚性（无甩飞） | `diag_stow_outliers.py` | `OUTLIERS_0` |
| 默认配置未被污染 | `p2_arm_binding.py` | `G2_PARTIAL_REVOLUTE_OK`（缺 gripper_left/right，属 P5） |
| 双配置健康 | `diag_config_health.py` | STOWED 25/25 mate 抑制、跨度 230.6 mm；默认 0/25 抑制、跨度 250.4 mm |
| 配置隔离（决定性） | `diag_config_leak_test.py` | 默认漂移 0.0，臂文件哈希不变（未保存） |
| 只读资产守护 | `check_protected` P3/P4/P4B/LEAK 各 PRE+POST | 全 `ALL_PROTECTED_UNCHANGED` |

## 4. 未消解的负结果与 HOLD（不得当作已通过）

- **收拢位鞍座负间隙（P6 HOLD）：** O13-v3 收拢位下臂体侵入鞍座窗口——G07 **−27.0 mm**、MID **−19.3 mm**、G08 **−58.9 mm**。当前只做了时钟符号择优（+1 优于 −1），**未做连续间隙求解**；此 q_stow 为 `O13_V3_CANDIDATE_HOLD_PROVISIONAL`，不是可交付的停靠位。
- **夹爪二指缺失（P5）：** donor 臂为固定复合夹爪，URDF 中 `gripper_left/gripper_right` 两个 prismatic 指未建为独立零件。
- **S3 真实承托面（P5）尚未建：** 三鞍座仍无对手接触面（审计 R3-04 未闭合）。
- **HDRM / 相机支架 / 线束（P5-P6）未建。**
- q_stow、接触垫、T_c 等 PROVISIONAL 占位仍在；继承的科学负结果（e15 REPEAT、SAFE-00 next_stage_authorized=false、C5 收拢翼包超差等）不受本 ECR 影响。

## 5. 下一轮（第 2/3 循环）计划

1. P5：分离夹爪二指、建 S3 三鞍座对手承托面、ARM_HDRM（演示级）、相机支架、线束包络。
2. P6：连续间隙求解——在 O13 收拢带内搜 q_stow 使三鞍座间隙 ≥ 设计垫栈（约 +3 mm）而非当前负值；配置矩阵定稿。
3. 每步保持 PRE/POST 哈希守护 + fail-closed 回读 + 冷重开核验。

## 6. 签署

本报告为执行进度陈述。ECR 最终批准栏保持留空，待人工签署；本轮无触发人工确认的破坏性变更（未改 URDF/关节/质量惯量，未覆盖 donor 或历史冻结目录）。
