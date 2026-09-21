# 机械 Loop Engineering 续接裁决 V3

## 本轮工程增量

- e19 已把 M01、M05、M06、M07 从“哈希绑定输入分支”推进到“六条互不连接的隔离数值诊断”；机器 Gate 为 17/17，独立验证为 31/31、负控 85/85。
- M01 在历史刚性自由漂浮质量模型与显式 REORG 路径适配下，基座姿态偏转峰值为 `122.543080 deg`；M07 arm-only 为 `37.200771 deg`。两者均无已授权验收阈值，也不是当前发布质量模型下的工程预测。
- M05 的 Sim13 常角速运动学与静态展示坐标代数保持不可合并；M06 的 20 例半正弦等冲量数值积分最大相对误差为 `3.079e-16`，其幅值不是物理接触力。
- Sim15 的 4 个 22 kg 理想刚塑捕获案例由当前哈希绑定代码精确复现；M07 arm-only 未附着目标，锁定变换、选定质量属性和恢复合同仍为空。
- accepted URDF 与 Solar R2 哈希未变，本轮 CAD/STEP/网格增量为 0。

机器裁决：`MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_HASH_BOUND_ISOLATED_NONRELEASE_NUMERIC_DIAGNOSTIC_EXECUTION_CLOSED__PRE_CAD_PHYSICAL_CONTACT_ATTACHED_RECOVERY_MISSION_PRODUCTION_AND_FLIGHT_RELEASE_HOLD`

## 当前可合法使用的结果

1. 把 M01/M07 的大幅刚性基座反作用视为诊断风险信号，优先安排“当前选定质量惯量分支 → sim11 刚柔耦合”独立复算；在阈值授权前不得写成合格/不合格。
2. 继续分别使用 M05 运动学、M05 静态坐标、M06 标量波形、M07 arm-only 与 Sim15 刚塑代数做软件回归和输入敏感性检查。
3. 任一输入或求解器版本变化后，只能逐支路重跑并签发新哈希证据，禁止隐式串接旧状态。

## 仍未放行

- `end_to_end_diagnostic_dynamics_ready=false`：四任务段没有统一历元、公共帧、连续状态或任务 guard。
- `physical_contact_ready=false`、`attached_target_recovery_ready=false`：夹爪力速/时延、接触/锁定台架、锁定变换、法向、组合质量属性和恢复终端合同均未闭合。
- ODR-42 仍 PENDING，Route-C MPI 仍为 0/8 CONTROLLED；Route-C CAD、完整路径碰撞/Solar/束线 Gate、生产 Sim13、硬件和飞行均为 HOLD。

## 最短闭环

先用当前选定质量惯量分支复核 M01/M07，再进入 sim11 刚柔耦合诊断合同；治理主线仍是 ODR-42 + MPI-01..08，然后才是执行器/接触/锁定台架、M05→M06→M07 物理合同、M01 HDRM 合同、Route-C CAD 与完整路径 Gate。
