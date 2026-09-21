# F3R2 变更控制记录

任务标识：`F3R2_G3_TO_G8_MECHANICAL_TERMINAL_CLOSURE`
日期：2026-08-07
写入范围：**仅** `20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/`

---

## 0. 保护边界执行情况

四项受保护资产在本轮**每一个** Gate 的 PRE/POST 均校验，结果一律
`ALL_PROTECTED_UNCHANGED`：

| 资产 | SHA-256（前 20 位） |
|---|---|
| accepted B601 URDF | `408147DDC9CC0BBA0FAC…` |
| mass_inertia_budget_v1.csv | `073C802527E35C949518…` |
| V2_2 native donor top | `30C09B50A0D2967EC1F4…` |
| B51 articulated arm donor | `603B87BBD4398FDDB3F7…` |

校验记录：`00_authority/F3R2_PROTECTED_CHECK_*.json`（PRE/POST 成对）。

**未修改**：B601 URDF / 关节轴 / 连杆长度 / accepted 质量惯量、V2_2 donor、
G0/G1/G2 历史装配与报告、既有负面证据。
**未覆盖** V3：`F3R1_..._V3_CONFIGURED.SLDASM` 哈希 `19D85E9C703BEC107396…` 全程未变。

## 1. ECR-F3R2-001：控制初始姿态偏离 as-built

**触发**：`Q_DEPLOYED_HOME` 相对上游 as-built 姿态的关节变化超过 0.5° 阈值。

| 关节 | as-built | Q_DEPLOYED_HOME | Δ |
|---|---|---|---|
| joint1 | 0.0° | −90.0° | −90.0° |
| joint2 | 0.0° | −120.0° | −120.0° |
| joint3 | 0.0° | −60.0° | −60.0° |
| joint4 | 0.0° | 0.0° | 0.0° |
| joint5 | 0.0° | −30.0° | −30.0° |
| joint6 | 0.0° | 0.0° | 0.0° |

**原因**：as-built 姿态 q=0 使 joint2 与 joint3 恰好压在其 0.000° 上限
（机械止挡），关节裕度 0.0°，不能作为控制初始化真值。

**修正层级**：3（在 accepted joint limits 内优化 q）。未使用层级 4/5，
未触碰任何受保护资产。

**处置**：按本会话授权，在 F3R2 候选目录内继续执行，不停下等待确认。

**影响**：所有下游动力学/控制/具身消费者须以
`04_configurations/F3R2_ARM_INITIAL_POSE.yaml` 为姿态 SSOT，不得再用 q=0。

## 2. D-F3R2-01：SolidWorks 在本机不可用于全装配干涉

四次尝试全部失败（2 次低内存致死 RPC、1 次挂死 17 分钟、1 次低内存致死），
逐条记录于 `05_clearance/G3A_NATIVE_ATTEMPTS.json`。

**处置**：原生 B-rep 裁决**不报告为通过、不报告为零、不由离线结果替代**，
登记为未闭合项 `G3A_NATIVE_BREP_INTERFERENCE_NOT_OBTAINED`。
干涉与间隙改由 CAD 网格离线测量，仪器先自检
（`05_clearance/G3A_INSTRUMENT_SELFCHECK.json`，`SELFCHECK_PASS`）。

**闭合条件**：在可用内存 ≥ 6 GB 的机器上按配置运行
`99_tools/r2b3_g3a_chunked.py`；该脚本按配置 journal，可增量完成。

## 3. D-F3R2-02：崩溃残留锁文件

SolidWorks 崩溃会为每个已加载文档留下一个 `~$` 锁文件（本轮清理出 73 个），
陈旧锁会在下次打开时触发模态框。

**处置**：每次会话启动前扫除 F3R2 树内的 `~$` 文件（`r2_common.sweep_locks`）。

## 4. D-F3R2-03：`Removable_Panels-1` 陈旧存储指针

F3R2 baseline 中 81/82 组件解析在 F3R2 内；`Removable_Panels-1` 的存储路径
仍指向 F3R1。该组件**在全部 8 个配置中均被压缩**，从不解析，且其 F3R2 副本
已存在并与源逐位一致（SHA-256 `A023E19C9E0789A88A62…`）。

**处置**：登记为已知项，**不做无谓改写**。改写需重存 73 个文档，
每次额外写入都是一次腐蚀候选装配的机会，收益为零。

## 5. D-F3R2-04：CAD 臂几何 ≠ accepted URDF 碰撞网格

逐链接包围盒对拍（同一挂载变换、同一 q=0）：

| 链接 | 最大偏差 |
|---|---|
| link2 | 1.4 mm |
| link3 | 11.6 mm |
| link4 | 10.4 mm |
| link5 | 13.9 mm |
| **link6** | **46.1 mm** |
| gripper | 38.9 mm |
| base_link | **URDF 大 55.8 mm**（保留了集成时被替换的原厂底板） |

**处置**：机械间隙一律用 **CAD 网格**计算，运动学一律用 **URDF**。
二者不可混引。此前从 URDF 网格计算机械间隙的做法是 fail-open。
**不得**通过修改 accepted URDF 来"消除"该差异。

## 6. D-F3R2-05：`min_arm_to_bus` 曾是 fail-open 指标

首版 `Q_DEPLOYED_HOME` 八项判据中的"臂—本体最小距离"被**固定不动的
base_link** 主导，三个姿态恒为 27.405 mm，对姿态完全不敏感。

**处置**：补加第 9 项判据"运动链（link1..gripper）脱离本体"，
并重跑评估、搜索与冻结。补加后该量为 74.05 mm / 294 对比较集，
夹爪间隙亦随姿态分化（124.6 / 548.2 / 690.0 mm）。

## 7. D-F3R2-06：FreeCAD STEP 导入的父级放置陷阱

STEP 导入建立容器层级，`obj.Shape.BoundBox` 只给父级局部坐标。
首版环境网格因此整体偏移（由臂配准对拍抓出，X 方向差 480 mm）。

**处置**：对每个网格施加 `getGlobalPlacement() × Placement⁻¹` 修正
（施加于镶嵌网格而非 B-rep——复制 481 个 B-rep 形状会耗尽本机内存）。
修正后臂分解无损性 0.0009 mm。

## 8. D-F3R2-07：镶嵌不能回答解析几何问题

0.5 mm 挠度下，`Hinge_Pin` 的 Ø8 圆柱镶嵌成 8×8 方料，耳片孔消失。
我据此一度误判"销为方料、耳片无孔"。

**处置**：所有配合尺寸改由 B-rep 探针（OpenCascade 解析曲面）读取
（`05_clearance/mesh/BREP_PROBE_WINGROOT.json`）。真值：
销 r=**4.000** 真圆柱、耳孔 r=**4.200**、扭簧 r=4.2/8.0，三者严格同轴于
x 轴、|y|=143.15、z=0。三个鞍座为 10 面纯平面盒（确证为占位框）。

## 9. 新建资产清单（全部在 F3R2 内）

- `03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM`（+73 依赖文件）
- `04_configurations/`：姿态评估、搜索、冻结、YAML、登记表、过渡矩阵、决策书
- `05_clearance/`：干涉登记、仪器自检、原生尝试记录、B-rep 探针、网格集
- `06_supports/`：翼根接口、承托件定义与对手面搜索
- `07_hdrm/`、`08_camera_harness/`：G4 定义
- `10_digital_thread/`：质量预算、frame/collision/action-mask/state-machine
- `11_screenshots/RAW/`：12 张见证截图
- `99_tools/`：本轮全部脚本（可复现）
