# 机械 Loop Engineering 续接裁决 V2

## 当前工程结果

- 夹爪 URDF 速度字段的语义已纠正：棱柱关节字面值按 SI 为 `15 m/s`，只保留为未验证自动导出模型限制；物理速度、闭合时间及不确定度仍为 `null/HOLD`。
- e18 已形成四段哈希绑定的非发布输入：M01 纯关节五次候选、M05 两个不可合并的目标状态分支、M06 的 20 例求解器激励矩阵、M07 的臂轨迹/诊断质量/完整状态分支。
- Route-C MPI 证据审计完成，五份 Owner 模板可直接填写；实际受控输入仍为 `0/8`，MPI-07 只承认 J1..J6 局部运动学，不代表安装 ICD。
- accepted URDF 与 Solar R2 哈希未变，本轮新增 CAD/STEP/网格数量为 0。
- 当前仅是孤立、哈希绑定的非发布数值输入分支就绪；端到端诊断动力学仍为 `false`。

机器裁决：`MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_GRIPPER_SEMANTICS_AND_HASH_BOUND_NONRELEASE_INPUT_BRANCHES__PRE_CAD_PHYSICAL_CONTACT_MISSION_AND_PRODUCTION_RELEASE_HOLD`

## 可以立即做的离线诊断

1. 复算并扰动 M01 的 11.5 s、0.01 s 关节空间候选；`release_confirmed` 未绑定，所以不得执行或声称 HDRM 释放序列。
2. 分别计算 M05 的 Sim13 bootstrap 与静态展示分支，禁止合并、平均或伪装成任务不确定度。
3. 把 M06 的 4×5 半正弦等冲量矩阵作为求解器刺激输入；峰值不是实测/允许接触力。
4. 对 M07 已命名的臂轨迹、两种诊断质量分支和 Sim15 完整状态分支做敏感性分析；锁定变换和发布质量属性仍为空。

## 尚未放行

- ODR-42 仍为 `PENDING`；MPI-01..MPI-08 为 `0/8 CONTROLLED`。
- 任务序列可执行性、八段轨迹发布、物理夹爪速度、接触/锁定模型、全路径碰撞/Solar/束线 SAFE 均未闭合。
- Route-C CAD 入口、机械设计发布、生产动力学、物理接触 RL、Sim13 生产重绑定、硬件运动和飞行资格均为 `false/HOLD`。

## 最短闭环顺序

先独立处置 ODR-42，并由具名 Owner 填写五份 MPI 模板；随后取得夹爪力速/延迟与接触/锁定台架数据。任务合同按 `M05_22 → M06_22 → M07_22` 闭合，M01 单独等待真实 STOW 与 HDRM 释放权威。只有 ODR-42 与 8/8 MPI 同时闭合，才进入独立版本 Route-C CAD；生产 Sim13 必须等完整路径 Gate 后重绑。
