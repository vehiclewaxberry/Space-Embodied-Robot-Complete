# B5.1R1 机械—控制协同设计要求

日期：2026-07-30  
用途：B601 空间机械臂原生 CAD、控制模型、仿真模型和后续具身智能研究的统一输入合同。

## 1. 当前工程判定

当前已证明：

- 10 links；
- 9 joints；
- `6R + 1 fixed + 2 independent P`；
- q0 中性拓扑；
- 末端两条 P 分支；
- 冻结 URDF、q0 台账、V2.2 顶层装配未变化。

当前尚未证明：

- 原生 Master Skeleton；
- 10 个原生 Carrier；
- 9 个原生关节配合；
- q0 显式复位；
- 原生角度/位移限位；
- T005-A/B/C；
- H10；
- G07/G08/HDRM；
- 连续间隙；
- 结构柔度和模态；
- 可发布控制模型。

## 2. 机械设计不得破坏的控制真值

### 2.1 拓扑与坐标

accepted URDF 是以下项目的唯一权威：

- link 名称；
- joint 名称；
- parent / child；
- joint type；
- joint axis；
- joint origin；
- lower / upper；
- mass；
- inertia。

CAD 不得重新定义这些真值。CAD 只能提供：

- 原生装配；
- 几何外形；
- 接口；
- 碰撞和扫掠；
- 结构柔度候选；
- 传感器与执行器安装空间。

### 2.2 不能假设冗余自由度

B601 为 6R 主链，不应在严格 6D 末端任务中假设存在关节冗余。控制研究应区分：

- 5D 接近与姿态容差；
- 短程 6D 对准/锁定；
- 夹爪 2P 操作；
- 自由漂浮基座耦合。

机械模型中不得增加虚拟第七旋转关节以制造冗余。

### 2.3 2P

两个 P 关节当前按独立关节处理，直到 accepted URDF 的 mimic / multiplier / offset 证据另有说明。

必须分别保存：

- joint coordinate；
- 物理指爪位移；
- 总夹爪开度；
- 接触中心；
- 左右接触面法向。

## 3. 控制可用的机械接口

每个 6R 关节至少需要以下机械—控制字段：

- `joint_name`
- `axis_in_parent`
- `zero_definition`
- `positive_direction`
- `lower_limit`
- `upper_limit`
- `hard_stop_margin`
- `continuous_or_bounded`
- `rated_torque`（若无权威则 provisional）
- `peak_torque`
- `rated_speed`
- `gear_ratio`
- `motor_inertia`
- `reflected_inertia`
- `friction_coulomb`
- `friction_viscous`
- `backlash`
- `torsional_stiffness`
- `torsional_damping`
- `encoder_resolution`
- `encoder_zero_repeatability`
- `thermal_derating`
- `harness_resisting_torque`

每个 2P 关节至少需要：

- 线性轴；
- 零位；
- 行程；
- 正方向；
- 软限位；
- 硬限位；
- 速度；
- 推力；
- 指爪刚度；
- 指爪接触面；
- 编码器/行程测量；
- 两爪同步策略。

没有本地权威的数据必须写入 provisional 参数表，不得填入虚构型号。

## 4. 基座与航天器接口

后续自由漂浮控制不能只接收“刚性固定基座”。

机械侧必须准备两个模型：

### 4.1 刚性调试模型

`FIXED_BASE_DEBUG`

用于：

- FK；
- IK；
- 关节限位；
- 轨迹；
- 碰撞；
- 相机标定。

### 4.2 自由漂浮模型

`FREE_FLOATING_VALIDATION`

至少包含：

- 服务星质量、质心和惯量；
- B601 质量、质心和惯量；
- 太阳翼展开状态；
- 基座接口坐标；
- 基座 6×6 柔度/刚度候选；
- 轮组和推力器资源接口；
- 关节运动对基座的反作用。

适配器和主结构的结构分析，应最终导出：

- 基座 6×6 刚度矩阵；
- 基座 6×6 阻尼候选；
- 一阶若干模态；
- 模态参与系数；
- 适用频带；
- provisional 状态。

## 5. 传感器坐标系

机械 CAD 必须预留并命名：

- `CS_CAMERA_BASE`
- `CS_CAMERA_WRIST`
- `CS_CAMERA_EE`
- `CS_FT_SENSOR`
- `CS_GRASP_CENTER`
- `CS_TOOL_FLANGE`
- `CS_STOW_G07`
- `CS_STOW_G08`
- `CS_SPACECRAFT_BODY`

相机额外保存：

- optical frame；
- FOV；
- 可视距离；
- 遮挡包络；
- 安装误差；
- 时间戳/延迟接口。

腕部六维力传感器保存：

- 安装面；
- 测量原点；
- 正方向；
- 过载保护包络；
- 结构旁路风险。

## 6. 线束和热控对控制的影响

机械设计不能只画扫掠线。至少记录：

- 关节各角度下弯曲半径；
- 线束扭矩方向；
- 最差恢复力矩；
- 夹点；
- 热控包覆；
- 连接器拉脱方向；
- 对零位回差的潜在影响。

没有实测数据时，以区间写入控制模型，并在敏感性分析中扫描。

## 7. 收拢—释放状态机

机械侧需输出离散状态合同：

- `STOWED_LOCKED`
- `SOLAR_DEPLOY_ARM_LOCKED`
- `SOLAR_DEPLOY_CONFIRMED`
- `HDRM_RELEASE_COMMAND`
- `HDRM_RELEASE_CONFIRMED`
- `ARM_CLEAR_OF_G07`
- `ARM_CLEAR_OF_G08`
- `DEPLOYED_NOMINAL`
- `SERVICE`
- `RELEASE_FAILED`
- `SOLAR_DEPLOY_FAILED`

每个状态保存：

- 允许的关节运动；
- 禁止的关节运动；
- 接触约束；
- 传感器判据；
- 超时；
- fail-closed动作。

## 8. 碰撞模型

后续控制必须同时获得：

- visual mesh；
- collision mesh；
- keepout volume；
- continuous swept volume；
- stowage contact geometry。

每个 link 的碰撞体不得跨越关节轴，不得用一个整臂包围盒替代逐 link 碰撞。

## 9. 必须生成的控制交接文件

- `B51R1_MECH_CONTROL_HANDOFF_CONTRACT.yaml`
- `B51R1_JOINT_ACTUATION_PARAMETER_REGISTER.csv`
- `B51R1_JOINT_ZERO_SIGN_LIMIT_REGISTER.yaml`
- `B51R1_SENSOR_FRAME_REGISTER.yaml`
- `B51R1_BASE_INTERFACE_COMPLIANCE.yaml`
- `B51R1_STOW_RELEASE_STATE_MACHINE.yaml`
- `B51R1_COLLISION_MODEL_MAPPING.yaml`
- `B51R1_CONTROL_MODEL_VALIDATION_MATRIX.csv`

## 10. 控制模型发布 Gate

只有满足以下项目，才允许把 CAD 结果交给控制研究：

1. 9 个原生关节逐个单测；
2. q0、正负方向和限位一致；
3. T005-A/B/C通过；
4. accepted URDF哈希不变；
5. CAD—URDF frame映射100%；
6. 质量惯量仍来自accepted URDF；
7. 2P关系已证明；
8. 传感器和工具坐标系已定义；
9. 固定基座和自由漂浮模式分开；
10. 所有 provisional 参数明确标记。

允许发布状态：

`CONTROL_MODEL_RELEASE_CANDIDATE_WITH_PROVISIONAL_ACTUATOR_AND_COMPLIANCE_PARAMETERS`

不得发布为：

- flight controller validated；
- hardware closed-loop validated；
- real-time digital twin；
- autonomous capture demonstrated。
