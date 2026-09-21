# Sim13 V4B4E：后冻结合成 6D 约束求解器执行包

本目录是已审计 B4 合同包的独立兄弟执行包。它不修改
`phase_b4_synthetic_6d_constraint_acquisition_release/`，也不继承或改写该目录的
“合同冻结、实现未开始”历史裁决。

## 本轮解决的问题

1. 从 B3 每条积分轨迹自己的首个
   `soft_capture_transient_qualifies && all_ledgers_closed` 样本触发；
2. 冻结当前 palm→target 相对位姿，不做 pose snap；
3. 构造 `M_minus / A / L / Jc / D / S_eta / S_z`；
4. 以 14D reduced SPD 解和独立 pivoted symmetric KKT 解双路获取；
5. 把 B3 左右接触势能各一次转入 `D_switch`，约束激活后关闭接触核；
6. 以 target 固定子体的 14D reduced 动力学传播，并用独立 fixed-child
   `BodyKinematics` 对拍质量矩阵和偏置项；
7. 以 cubic-Hermite 全根分区验证连续 gap/gap-rate dwell；
8. 在精确最早事件时刻重建状态，执行 `z_before=L(q_r)eta_r` 的逐分量零跳变
   解除，并切换为独立 29D service＋13D target 的 5 ms 自由飞行；任何 gap、
   gap-rate 重入或接触核复活均 fail-closed；
9. 用明确标注为算法输入、非硬件规格且**不满足 B3 soft-capture trigger** 的
   pre-acquisition fixture（两指 P 坐标各 `-20 µm`、P 速度各 `+20 mm/s`）覆盖
   非采样网格时刻的混合算法分支；扰动后重新计算接触点与弹性势能，acquisition 后
   禁止再改状态。该 fixture 只取得非触发 branch-coverage 信用；只有 B3 主分支真实
   出现最早有限事件且 5 ms 审查通过时，主 campaign 才允许
   `synthetic_removal_executed=true`；
10. 执行 RK4/midpoint 各 coarse/fine/reference 六条轨迹、22 个真实字节/矩阵/
    轨迹/调用路径负控、184 个精确 nodeid 测试、48 项 validator 和 36 项独立审计。

## 有限时域裁决

B4 冻结合同没有给出 active 最大搜索时域。B4E 在实施前补充冻结：

```text
active end time = 0.08 s
source          = B3 已审计轨迹末端
classification  = bounded numerical search horizon, not physical timing
```

因此，若 `0.08 s` 前没有 release event，只能输出：

```text
DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED
```

该结果不等价于无界时间内 eligibility set 为空，也不等价于 release capability
PASS。严禁看完结果后再伸缩时域挑选事件。

## 运行

从项目根目录执行：

```powershell
python 30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4_post_freeze_synthetic_6d_solver/run_phase_b4_solver.py
```

完整命令依次重建六轨迹原始证据、运行 validator，再运行不导入 solver 的独立审计。
运行时可用内存只作 B4E 性能诊断；本包不适用 Unified R2/V5 CAD 的 6 GiB
准入门，因此证据固定记录 `memory_gate_applicable=false`、
`memory_gate_passed=false`、`owner_override_used=false`，不得冒用历史 Override。
最终机器裁决只认：

```text
results/SIM13_V4B4E_AUDITED_GATE_V1.json
```

## 绝对 HOLD

本包始终不是以下任何一项：

- B3 两点接触的物理 6D force closure（B3 仍为 rank 5）；
- 真实夹爪接触、摩擦、执行器时序、保持力、锁止或释放模型；
- held capture、grasp success、target attached 或 released attached target；
- 当前系统绑定、正式 NC19、Owner 机械授权、生产、release 或下一阶段授权；
- URDF、统一系统接口、执行锁或私有生成器调用。

物理输入仍为 null/HOLD。差分步长扫描只是数值离散审计，不是测量不确定度，
不得包装成机械公差或硬件规格。
