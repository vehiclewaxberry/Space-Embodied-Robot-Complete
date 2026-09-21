# B601—12U 载荷路径与结构要求

状态：`TOPOLOGY_CONFIRMED / PHYSICS_UNSOURCED_BLOCKED`

## 1. 裁定

现有结果只确认了载荷责任链，未确认任何截面、材料、连接、刚度、强度、模态或安全系数。可保留的主路径为：

```text
B601 A0
→ IF-RM-002
→ 上法兰/适配器参考包络
→ 载荷扩散板与主承力凸台参考包络
→ 前任务面扩散区
→ 前横向框
→ 四条纵向主构件
→ 舱段横框
→ 所选部署器凸耳/导轨或外部支承接口
```

证据来自：

- `20_engineering/design_review/V2_PDR_package/02_structure/primary_load_path_contract.yaml`
- `20_engineering/design_review/V2_PDR_package/05_robot_mount/robot_mount_preliminary_design.md`
- `20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN/B601_BASE_ADAPTER_DESIGN.md`

这条路径的裁定是 `CONFIRMED_TOPOLOGY_ONLY`。外板、可拆设备托盘、线束曲线和视觉 CAD 不得被当作主承力闭合件。

## 2. 分工况载荷路径

### 2.1 发射收拢工况

发射载荷必须绕过谐波/QDD 减速器：

```text
臂各收拢支承接触区
→ 主/辅助 HDRM 硬点
→ 横梁或前任务面主结构
→ 纵梁/横框
→ 部署器接口
```

根部安装法兰仅承担其被明确分配的支路；不能默认整臂惯性载荷沿关节串联传回根部。当前 HDRM 产品、锁点精确坐标、接触垫、预紧和发射载荷均为 `PLACEHOLDER`。

本轮选择“分离螺母”作为 `DESIGN_ONLY` 候选，原因是它允许把保持力直接闭合到具名硬点。它不是采购或资格化结论；烧断线与记忆合金仍保留为未选方案。

### 2.2 在轨机械臂作业

在轨作业路径为：

```text
末端/各连杆惯性与接触载荷
→ 关节与臂基座
→ IF-RM-002 / IF-RM-001
→ 载荷扩散区
→ 前框与四纵梁
→ 整星刚体与姿控系统
```

当前不能给根部反力矩量级：

- PDR 六维载荷合同六个分量均为 null；
- `sim_05_free_floating_arm` 明确是零外力矩的运动学动量反作用模型，不计算关节力矩；
- 捕获或控制仿真结果不得未经独立载荷裁决直接升级为结构设计载荷。

因此 `Fx/Fy/Fz/Mx/My/Mz = PLACEHOLDER`，状态为 `UNSOURCED_BLOCKED`。未来至少要分别给出名义运动、急停、极限关节加速度、捕获瞬态和失效安全回撤工况，并绑定关节位形、时域、单位、符号、组合和不确定度。

### 2.3 在轨装配接触工况

装配接触载荷的责任链为：

```text
导向锥/销/孔接触
→ 末端工具与柔顺单元
→ B601
→ 臂根接口
→ 主结构与整星姿控
```

`ASM-00` 当前裁决为 `ASM00_AG0_BLOCKED_BY_INTERFACE`，缺销距、倒角、导向半径、摩擦来源和间隙语义，且未运行物理求解器。因此本轮只能定义载荷记录字段，不能给峰值力、冲量、接触刚度或成功包络。

### 2.4 地面装配与搬运

地面工装载荷不得复用发射或在轨载荷。必须单列：

- 裸框架搬运；
- 设备托盘插拔；
- B601 吊装与临时支承；
- HDRM 安装/释放地面测试；
- 最终收拢整星转运；
- 称重与质心测量工装。

重力方向、支承点、吊点、工装刚度和允许姿态均为 `PLACEHOLDER`。

## 3. 一阶模态与刚度

| 项目 | 当前值 | 裁定 |
|---|---|---|
| 收拢构型一阶模态目标 | `PLACEHOLDER Hz` | `UNSOURCED_BLOCKED` |
| 部署器/适配器边界刚度 | `PLACEHOLDER` | `UNSOURCED_BLOCKED` |
| 臂根平动刚度 | `PLACEHOLDER N/m` | `UNSOURCED_BLOCKED` |
| 臂根转动刚度 | `PLACEHOLDER N·m/rad` | `UNSOURCED_BLOCKED` |
| HDRM 接触刚度/预紧 | `PLACEHOLDER` | `UNSOURCED_BLOCKED` |

目标频率必须由所选部署器/发射任务文档给出并完成任务级裁剪，不能从通用 CubeSat 经验或记忆填入。文档入口见 `structure/DOC_ACQUISITION.md`。

## 4. 收拢构型对载荷路径的修正

现有 O13 候选为：

```text
clock = 25 deg
q = [145.572, -168.0, -57.0, -41.143, -20.954, -3.0] deg
```

它只能作为 `CANDIDATE_HOLD`：

- 可动段与当前结构的点—三角最小间隙、横向范围通过候选几何检查；
- 垂向仍显著超出当前项目 bus 顶面，`STOW_Z_LIMIT` 未释放；
- 支承垫材料、接触资格、预紧、发射载荷和 B601 壳体承载能力未定义；
- 完整解锁轨迹未验证。

因此载荷路径不能以“臂已收进 12U”作为边界条件。当前配置必须按 `STRUCTURE_CONFIG_ISSUE_B601_STOW_Z` 上报。

## 5. 下游消费规则

### 角动量预算

- 只允许消费选定反作用轮 datasheet 中的角动量容量和最大力矩。
- 旧 `sim_10` 轮组档位是扫描占位，不能回填 `BOM_12U.yaml`。
- 在轮组选型前，不得据此判断机械臂作业能否由轮组吸收。

### GJM

- 必须显式选择 `T_SM` 的 dynamics/PDR track 或未来 physical track；不得把 `185.25 mm` 与 `198.0 mm` 静默合并。
- `[0, 1.5707963, 0] rad` 只属于现有动力学模型合同；物理飞行安装姿态为 `PLACEHOLDER`，不得静默继承。
- 必须使用不重复计数的整星质量、CoM、惯量和 accepted B601 per-link 惯量。
- 根部柔度未知时只能使用刚性接口假设，并显式标记模型边界，不能声称结构闭环。

### 结构与仿真

- `PLACEHOLDER` 不能当零。
- CAD 体积或默认材料不能生成飞行质量/惯量。
- 仿真载荷需经过“来源—工况—坐标—时域—不确定度—组合—owner”七项审查后才能进入 FEA。
- 本轮未运行 FEA、模态、发射环境或装配物理仿真。
