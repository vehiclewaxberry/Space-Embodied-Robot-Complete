# R2 控制工程闭环候选

## 2026-08-27 单位度量审计处置

5D/6D 广义雅可比数值仍保留为可复现的原始诊断，但其线速度行使用 m/s、角速度行使用 rad/s，而当前没有权威合同冻结特征长度或任务空间权重矩阵。因此奇异值、欧氏残差范数、DLS 阻尼比较和残差改善百分比均属于**混合单位、非单位不变、无信用诊断**。运行时守卫保持 fail-closed，不发出控制命令；CG1 在物理度量绑定并重新验证前维持 HOLD。

本目录把控制预开发推进到一个可审计的工程候选包，但结论仍是：

```text
candidate_package_complete = false（任务空间单位度量未绑定）
control_engineering_complete = false
collision_constrained_tracking_valid = false
hardware_valid = false
safe_review_pass = false
next_stage_authorized = false
release_credit = false
```

它没有执行时域 plant、接触、碰撞查询、pair/edge 查询或 M01 路径搜索，也没有修改 CTRL01、CTRL02、SAFE、E23、URDF 或 CAD。

## 交付内容

- `results/CTRL01_R2_FAILURE_CAUSAL_LEDGER.json`：保留 CTRL01 `REPEAT` 和当前树复放 `HOLD`；把直接证据、有限推断和未验证假设分开。
- `contracts/CTRL_R2_PHASE_TASK_CONTRACT_V1.json`：物理 6R 主链上的远距 5D、近距 6D，以及两个独立 P 关节的夹爪操作合同。明确禁止虚拟第七转动关节。
- `results/CTRL_R2_PRECONTACT_TRACKING_GATE_V1.json`：在一个已声明、哈希固定的 Unified R2 构型上比较 fixed-base naive DLS 与 free-floating mass-weighted generalized-Jacobian DLS。
- `results/CTRL_R2_FLEX_ROBUSTNESS_GATE_V1.json`：绑定左右翼各 7 模态的 LOW/NOMINAL/HIGH 频率目录；因无授权任务时间历程和执行器带宽，不生成整形器系数。
- `contracts/CTRL_R2_SUPERVISOR_INTERFACE_V1.json`：基座姿态/轮组、柔性整形和接触后 supervisor 的 fail-closed 接口。硬件阈值与 as-built 接触值保持 `null / MEASUREMENT_PENDING`。
- `results/R2_CONTROL_ENGINEERING_GATE_V1.json`：CG0–CG7 总控 Gate。

## URDF／坐标语义账本

- 模型：哈希固定的 Unified R2 URDF；本目录只读，不重新生成。
- 根坐标系：`spacecraft_bus`。
- 工具坐标系：`gripper_link`；其原点作为末端速度点。
- 主链：`joint1`–`joint6`，六个 revolute，轴由 URDF joint frame 传播至 root frame。
- 夹爪：`gripper_joint1`、`gripper_joint2`，两个独立 prismatic；它们是 `gripper_link` 的子分支，不能伪装为第七转动冗余。
- 扭量顺序：线速度三维在前、角速度三维在后，均表达于 `spacecraft_bus` 根坐标系。
- 单位：转动关节 rad，移动关节 m，速度 rad/s 与 m/s。
- 几何、visual、collision 与 mesh scale 均未在本目录改动或查询。

诊断状态中的 `qP=[0.03575, 0.03575] m`、`qdotP=[0,0]` 只表示速度级取样构型，不能代替 KKT/坐标消元的锁止约束，也不产生 2P 约束反力；本目录明确禁止把 `tauP=0` 解释为锁止证明。

自由漂浮广义 Jacobian 使用：

```text
J* = Jm + Jb A
A  = -Hbb^-1 Hbm
```

其中质量块、机械连接和运动链全部来自哈希固定的 Unified R2 backend。5D 阶段仅在局部满秩时具有一维零空间；6D 满秩阶段零空间为零。

## 结论边界

本目录输出的关节速度只是单状态诊断参考，不是电机命令。由于速率、力矩、延迟、带宽、轮组阈值、M01 路径、碰撞/线束约束、2P 约束反力、任务柔性时间历程、as-built 接触与 SAFE 当前审查均未闭合，控制工程 Gate 必须保持 HOLD。

150 kg @ 3 deg/s 保持物理 veto（ABORT/RECOVERY）；22 kg @ 0.5 deg/s 仅是名义控制候选，不是捕获 PASS。

## 复现

```powershell
python -B 30_simulation/r2_control_engineering_closure/src/build_control_engineering.py --repo-root .
python -B -m pytest -p no:cacheprovider 30_simulation/r2_control_engineering_closure/tests -q
```
