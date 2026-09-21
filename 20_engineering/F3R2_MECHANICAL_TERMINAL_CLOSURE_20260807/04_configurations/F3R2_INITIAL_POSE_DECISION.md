# F3R2 初始姿态决策书（G3-B）

任务标识：`F3R2_G3_TO_G8_MECHANICAL_TERMINAL_CLOSURE`
日期：2026-08-07
机器可读 SSOT：[F3R2_ARM_INITIAL_POSE.yaml](F3R2_ARM_INITIAL_POSE.yaml)

---

## 1. 为什么需要一次姿态搜索

`Q_AS_BUILT_REFERENCE`（即 CAD 中臂实际所处的 q=0）在八项硬指标中通过七项，
唯独 **第 7 项关节裕度失败**：

| 关节 | 下限 | 上限 | q=0 处裕度 |
|---|---|---|---|
| joint2 | −179.909° | **0.000°** | **0.0°** |
| joint3 | −179.909° | **0.000°** | **0.0°** |

joint2 与 joint3 的上限恰为 0.000°，因此 q=0 **正压在机械止挡上**。
控制系统不得从硬止挡初始化，故 `Q_AS_BUILT_REFERENCE` 降级为纯几何基准，
`runtime=false`。

这一失败是判据抓出来的，不是事后叙述：见
`F3R2_POSE_EVALUATION.json → home_gate_as_built`。

## 2. 修正层级（严格遵守授权顺序）

| 层级 | 动作 | 本轮是否使用 |
|---|---|---|
| 1 | 删除误参与计算的 reference/duplicate 组件 | 已做（`Release_Clearance_Envelope`、`Launch_Lock_Interface_Reference` 登记排除） |
| 2 | 修复配置压缩/mate 泄漏 | 不需要（G2 矩阵已核对一致） |
| 3 | **在 accepted joint limits 内优化 q** | **本轮采用** |
| 4 | 修改候选外部 base adapter/clocking/offset | 未使用 |
| 5 | 修改航天器非承力局部罩体 | 未使用 |
| 6 | 将状态排除出运行基线 | 仅对 STOW 使用 |

**未触碰**：B601 连杆几何、关节轴、accepted URDF、V2_2 donor、G0/G1/G2 历史资产。

## 3. 冻结结果

| 姿态 | q_deg | runtime | 最近关节裕度 | 运动链→本体 | 臂→翼 | 夹爪→本体 |
|---|---|---|---|---|---|---|
| `Q_AS_BUILT_REFERENCE` | [0, 0, 0, 0, 0, 0] | ✗ | **0.00°** | 74.05 | 166.25 | 163.71 |
| `Q_DEPLOYED_HOME` | [−90, −120, −60, 0, −30, 0] | ✓ | 59.91° | 74.05 | 123.52 | 124.58 |
| `Q_RELEASE_CLEAR` | [−90, −120, −120, −60, −30, 0] | ✓ | 47.14° | 74.05 | 166.25 | 548.25 |
| `Q_SERVICE_READY` | [−90, −60, −120, −30, 0, 0] | ✓ | 59.91° | 74.05 | 166.25 | 689.97 |
| `Q_STOW_ENGINEERING_CANDIDATE` | [145.572, −168, −57, −41.143, −20.954, −3] | ✗ | 11.91° | 74.05 | 166.25 | 106.04 |

单位 mm。末端位置（装配系）：HOME [187.1, −356.9, −267.5]、
RELEASE_CLEAR [834.9, −428.4, −300.9]、SERVICE_READY [1075.6, 31.6, 14.8]。

搜索规模：5 关节确定性网格 5625 点，其中 **4970 点满足限位+粗筛间隙**；
三个姿态均在按目标函数排序后的**首个候选**即通过全部网格级判据。

## 4. `Q_DEPLOYED_HOME` 九项判据逐条

| # | 判据 | 结果 | 实测 |
|---|---|---|---|
| 1 | 臂—本体干涉 = 0 | PASS | 0 对 |
| 2 | 臂—太阳翼干涉 = 0 | PASS | 0 对 |
| 3 | 臂—本体比较集非空 | PASS | 329 对 |
| 4 | 臂—翼比较集非空 | PASS | 16 对 |
| 5 | 关键最小距离均为有限数 | PASS | 无 None / 无 inf |
| 6 | 夹爪脱离本体 | PASS | 124.58 mm |
| 7 | 关节限位有效且有裕度 | PASS | 59.91° ≥ 3.0° |
| 8 | 不依赖 G07/G08/Mid 与 ARM HDRM | PASS | 鞍座接触 0，最近 60.33 mm |
| 9 | **运动链（link1..gripper）脱离本体** | PASS | 74.05 mm，294 对 |
| — | 相机所需视场可用 | **NOT_EVALUATED** | 装配中不存在相机 |

**第 9 项是本轮补加的**。原始八项中的"臂—本体最小距离"被**固定不动的
base_link 主导**（三姿态恒为 27.405 mm），对姿态不敏感，属 fail-open 指标。
补加运动链判据后该量才随姿态分化，夹爪间隙亦然（124.6 / 548.2 / 690.0 mm）。

相机项**不计为通过**：装配中没有相机，所有可视性主张一律
`NOT_EVALUATED_NO_CAMERA_IN_ASSEMBLY`。

## 5. 度量的权威边界

- **运动学**：accepted B601 URDF（只读，SHA-256 `408147DD…A3`）——拓扑、轴、限位、FK。
- **几何**：B51 CAD 连杆（来自哈希绑定的 G2 分配置 STEP）。
  **不是** URDF 的碰撞 STL——二者非同一版本（沿链偏差至 link6 达 46 mm，
  URDF base_link 反大 56 mm）。用 URDF 网格算机械间隙是 fail-open。
- **数值层级**：AABB（保守下界）→ 网格面距（0.5 mm 镶嵌公差）→
  **SolidWorks 原生 B-rep（权威，本轮未取得）**。

本文件中的间隙均为**网格层级**。原生裁决四次尝试全部失败，
证据见 [G3A_NATIVE_ATTEMPTS.json](../05_clearance/G3A_NATIVE_ATTEMPTS.json)。

## 6. ECR

`Q_DEPLOYED_HOME` 相对上游 as-built 姿态的关节变化远超 0.5°
（joint1 −90°、joint2 −120°、joint3 −60°、joint5 −30°），
按授权在候选目录内继续执行，ECR 记录见
[F3R2_CHANGE_CONTROL.md](../15_change_control/F3R2_CHANGE_CONTROL.md)。

## 7. 未闭合项（不得当作通过）

1. 相机不存在 → 所有可视性判据 `NOT_EVALUATED`。
2. 夹爪在 CAD 中是**单一实体**，URDF 声明两个移动指。
   所有夹爪间隙仅对该单实体成立，**张开态未验证**。
3. SolidWorks 原生干涉未取得。
4. `SERVICE_DOCKING`/`GRASP`/`TRANSPORT`/`ASSEMBLY`/`RETRIEVED_NOMINAL`
   没有任何权威 q 向量存在——本轮**不为其编造角度**，一律
   `NOT_DEFINED_NO_AUTHORISED_POSE`。
