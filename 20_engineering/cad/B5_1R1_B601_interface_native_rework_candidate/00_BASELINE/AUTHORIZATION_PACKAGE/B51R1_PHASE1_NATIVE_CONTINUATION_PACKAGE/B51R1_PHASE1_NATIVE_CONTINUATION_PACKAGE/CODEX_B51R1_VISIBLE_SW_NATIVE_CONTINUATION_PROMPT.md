# Codex 续跑提示词：B5.1R1 可见启动 SolidWorks 与原生整臂装配

## 0. 人工授权原文

`允许可见启动 SolidWorks 2024 一次，用于清除恢复对话框并继续 B5.1R1 原生 CAD 构建。`

附加边界：

- 仅允许在当前交互用户会话中可见启动一次；
- 不允许恢复或覆盖 V2.2、B5.0、B5.1、accepted URDF 或供应商 donor 原文件；
- 恢复对话框若涉及冻结资产，选择不恢复，并保存对话框截图和文件清单；
- 仅候选目录内的未保存恢复文件可以先只读打开，再另存到 B5.1R1 隔离目录；
- 出现许可、版本转换、缺失引用、宏安全、未来版本或外部引用警告时，不自动确认，截图并 fail-closed；
- 本授权不等于 H9 裁决，不授权制造、飞行、连续间隙或结构资格结论。

## 1. 继承状态

父中间 Gate：

`INTERMEDIATE_GATE_PARTIAL_PASS_WITH_SOLIDWORKS_SESSION_HOLD`

建议本轮开始时另写工程解释：

`B51R1_PHASE1A_1B_NEUTRAL_WITNESS_PASS_WITH_NATIVE_SOLIDWORKS_AUTHORING_SESSION_HOLD`

已验证：

- 4 mm：陈旧截面/层级基准偏差，禁止用整体平移修复；
- 3 mm：候选鞍座落在可拆面板层，禁止用普通垫片冒充主载荷路径；
- Master Skeleton V2 neutral STEP：关键尺寸和坐标构造闭合；
- Carrier q0 neutral STEP：10 links、6R + 1 fixed + 2P、末端分叉闭合；
- 冻结哈希未变化；
- H10 = 0/28；
- T005-A/B/C = NOT_RUN；
- 原生 SLDPRT/SLDASM 尚不存在。

## 2. SolidWorks 可见启动安全流程

按顺序执行：

1. 记录当前所有 `SLDWORKS.exe`、`swShellFileLauncher.exe`、`sldworks_fs.exe` 进程。
2. 确认没有用户正在编辑冻结基线。
3. 仅清理 B5.1R1 候选目录内明确属于本轮失败会话的 `~$` 临时锁；不得跨目录批量删除。
4. 可见启动 SolidWorks 2024，不使用隐藏窗口或后台会话。
5. 对恢复对话框截图并导出候选列表。
6. 冻结资产一律“不恢复”；候选资产只读打开并另存至隔离目录。
7. 新建一个空白测试零件：
   `00_BASELINE/SW_SESSION_SMOKE_TEST_20260729.SLDPRT`
8. 保存、关闭、重新打开该测试零件。
9. 通过 COM/API 重新连接当前可见实例。
10. 确认：
   - 只有一个主 SolidWorks 会话；
   - API 能读取版本；
   - 能新建、保存、关闭、重开；
   - 当前工作目录为 B5.1R1；
   - 无外部引用污染。
11. 输出：
   - `07_VERIFICATION/B51R1_SOLIDWORKS_VISIBLE_SESSION_RECOVERY.json`
   - `08_REVIEWS/B51R1_SOLIDWORKS_RECOVERY_DIALOG_LOG.md`
   - 对话框截图与进程清单。

任一步失败，停止原生CAD创建，保持 `SOLIDWORKS_SESSION_HOLD`。

## 3. 原生 Master Skeleton V2

创建：

`02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT`

要求：

- 优先使用参考平面、参考轴、坐标系、3D草图和参考曲面；
- 不创建影响质量的承力实体；
- 自定义属性：
  - `MODEL_ROLE=MASTER_SKELETON`
  - `MASS_AUTHORITY=NONE`
  - `BOM_EXCLUDE=TRUE`
  - `H9_STATUS=HUMAN_DECISION_REQUIRED`
- 建立：
  - `CS_SPACECRAFT_BODY`
  - `CS_B601_BASE_ACCEPTED`
  - `CS_B601_BASE_A0_25DEG_CANDIDATE`
  - 160×160接口边界
  - Ø100通道
  - X=183、185.25、198 基准
  - ±101.65纵梁轴
  - 真实主承力面
  - 可拆面板层
  - G07/G08接触窗
  - 太阳翼扫掠禁入体
  - 初始释放禁入体
- 配置：
  - `COMMON_CANONICAL`
  - `MODE_A_EVALUATION`
  - `MODE_B_EVALUATION`

生成原生后：

- 导出 STEP；
- 与 neutral witness R2 做几何比对；
- 报告关键平面/轴/圆柱/尺寸偏差；
- 冷重开验证特征树和命名实体仍存在。

中间退出条件：

`MASTER_SKELETON_NATIVE_PASS`

否则保持：

`MASTER_SKELETON_NATIVE_HOLD`

## 4. 10 个原生 Carrier 零件

建立10个无实体或仅含参考几何的 SLDPRT。文件名必须按 accepted link name 派生，禁止只写 Link01 而丢失真值名称。

每个 Carrier 包含：

- `CS_LINK_<accepted_link_name>`
- `CS_PARENT_JOINT_<accepted_joint_name>`
- `CS_CHILD_JOINT_*`
- `AXIS_<accepted_joint_name>`
- `PLANE_ZERO_<accepted_joint_name>`
- `CS_VISUAL_MOUNT_<accepted_link_name>`

自定义属性：

- `MODEL_ROLE=KINEMATIC_CARRIER`
- `DYNAMIC_AUTHORITY=ACCEPTED_URDF`
- `CAD_MASS_CONTRIBUTION=ZERO`
- `BOM_EXCLUDE=TRUE`
- `SOURCE_URDF_SHA256=<locked value>`

每创建一个 Carrier：

1. 冷重开；
2. 核对命名实体；
3. 导出中性 STEP 或 Parasolid 见证；
4. 与 q0 witness R2 对比；
5. 写入 carrier register。

输出：

- `04_CONFIGURATION/B51R1_CARRIER_REGISTER.csv`
- `04_CONFIGURATION/B51R1_URDF_CARRIER_FRAME_MAPPING.yaml`

## 5. 增量建立9个原生关节

禁止一次性建立全部关节后再排错。按 accepted 拓扑顺序逐个增加。

每增加一个关节，完成以下单元测试后才能继续下一个：

### R关节

- 关节原点一致；
- 关节轴一致；
- q=0一致；
- +1°和-1°符号测试；
- lower和upper限位测试；
- 返回q0；
- 保存、关闭、重开；
- q0误差复核。

### P关节

- 轴线一致；
- q=0一致；
- +1 mm或可用的小正位移测试；
- -1 mm或可用的小负位移测试；
- lower和upper限位测试；
- 返回q0；
- 保存、关闭、重开。

注意：

- `+71.5 mm/-71.5 mm` 先按各自 accepted joint coordinate 解释；
- 不得自动改写成每爪 `[-71.5,+71.5] mm`；
- 不得在未读URDF mimic字段前把两爪强制对称耦合；
- 关节行程、零位和夹爪总开度必须分开报告。

推荐配合命名：

- `MATE_<accepted_joint_name>_ORIGIN`
- `MATE_<accepted_joint_name>_AXIS`
- `MATE_<accepted_joint_name>_ZERO`
- `LIMIT_<accepted_joint_name>`

生成：

- `03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_CHAIN_NATIVE.SLDASM`
- `04_CONFIGURATION/B51R1_JOINT_MATE_REGISTER.csv`
- `04_CONFIGURATION/B51R1_JOINT_ZERO_AND_SIGN_REGISTER.yaml`

每个关节阶段保存独立检查点，不覆盖上一阶段：

`J00_BASELINE`、`J01_PASS` ... `J09_PASS`

## 6. Carrier-only 验证先于精细几何

在挂接供应商精细几何前，至少通过：

1. q0；
2. 所有关节小扰动；
3. 所有关节上下限；
4. 2P全开/中位/全闭定义；
5. 顺序：
   `q0 → 小扰动集合 → STOW候选 → q0`
6. 保存、关闭、冷重开。

先执行 carrier-only 版本的：

- T005-A0；
- T005-B0；
- T005-C0。

只有 carrier-only 全部通过，才允许挂接精细几何。

## 7. 精细几何挂接

将现有 B601 link-local 精细几何作为 rigid child 挂到对应 carrier。

规则：

- 只引用 `CS_VISUAL_MOUNT_<link>`；
- 不使用导入实体复杂圆柱面或边线作为运动配合；
- 不将精细几何设为运动链驱动者；
- 每个 link 几何挂接后单独重开验证；
- 检查几何是否跨越相邻关节轴；
- 检查每个link归属是否与 accepted URDF一致；
- 供应商精细几何质量不得覆盖URDF质量。

输出：

`03_CAD/20_B601_NATIVE_ARTICULATED/B51R1_B601_NATIVE_ARTICULATED.SLDASM`

然后重新执行完整 T005-A/B/C。

## 8. 与接口设计并行但不混淆Gate

原生 Skeleton 建立后，可以并行完成接口 A/B/C 贸易比较；在贸易决策前不得沿用旧桥接件。

特别要求：

- 适配器必须落到真实主承力框/纵梁；
- 可拆面板只能作为可拆覆盖或穿越层，不能成为主载荷路径；
- 3 mm不能用普通shim直接宣布闭合；
- 旧桥接件仅作为失败对照；
- H10仍逐行关闭28项，不允许按簇一次性改成CLOSED。

## 9. 本轮结束时必须汇报

### 允许的中间成功

`B51R1_NATIVE_SKELETON_AND_CARRIER_CHAIN_BUILT_WITH_INCREMENTAL_JOINT_TESTS_PASS`

前提：

- 原生 Skeleton存在并冷重开；
- 10个Carrier原生零件存在；
- 9个关节增量单测通过；
- 冻结哈希未变化；
- 引用100%隔离；
- 不代表H10或最终T005已通过。

### 若完成精细几何和完整T005

最多可写：

`B51R1_NATIVE_ARTICULATION_CANDIDATE_PASS_WITH_H10_H9_AND_STOWAGE_HOLDS`

### 禁止表述

- 整机设计完成；
- 接口闭合；
- H10通过；
- 运动包络安全；
- 制造就绪；
- 发射合格；
- 飞行可用。
