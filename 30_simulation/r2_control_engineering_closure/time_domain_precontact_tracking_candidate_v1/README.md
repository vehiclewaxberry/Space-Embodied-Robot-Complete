# Current-R2 Time-Domain Root-Frame Twist-Rate Diagnostic Candidate V1

本包是 append-only 控制诊断增量。它把已固定的 Current-R2 零总动量刚体 plant 与无量纲任务空间度量接入有限时域状态反馈；6 个转动关节主动，2 个夹爪移动关节作为理想完整约束锁定。

4 个物理运行实例构成两组同维对照：5D 与 6D 各包含无控基线和受控线。末端任务速度表达在瞬时 `spacecraft_bus` 根坐标系、作用点为 `gripper_link` URDF 原点；5D 后两项是随构型重建的局部接近轴平面分量。因此本包只审计加权 twist/velocity error，不是惯性系轨迹、位姿或姿态跟踪证明。

控制律为设计级速度伺服：

```text
qdd_cmd = Kv (qdot_cmd - qdot_R)
tau_R   = M_RR qdd_cmd + b_R
tau_P   = 0
```

每次 RHS 都重算自由漂浮广义 Jacobian、无量纲质量加权 DLS、秩与最小奇异值，并检查关节限位及 2P 锁定。证据分别核验线动量 `P`、关于固定惯性原点的角动量 `H_O`、控制做功—动能、约束反力零功、RK4/DOP853 交叉和确定性回放；禁止用混合量纲范数替代这些账本。

最高可能主张仅为：

```text
TIME_DOMAIN_TWIST_TRACKING_DIAGNOSTIC_EXECUTED
```

即使本包 Gate PASS，也不重发父 Dynamics/Control Gate，不验证 pre-contact 目标相对轨迹、硬件执行器、碰撞、接触、柔性、M01 路径、SAFE、Sim13、非 ABORT、下一阶段或发布。

## 复现

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
python -B build_time_domain_precontact_tracking_candidate.py
python -B -m pytest -q -p no:cacheprovider tests
```

本轮 6 GiB 内存门只用于执行资源准入；它不是科学阈值，也不产生控制或发布权限。
