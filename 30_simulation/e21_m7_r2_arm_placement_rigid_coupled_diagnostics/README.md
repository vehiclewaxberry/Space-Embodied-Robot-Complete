# e21 — M7 R2 安装语义、刚性翼自由漂浮臂与固定基座 ROM 诊断

本模块只形成当前 M7 R2 的非释放诊断证据。它不修改 CAD、URDF、质量账本或任何上游 Gate，也不执行接触、目标并入、任务捕获、碰撞、全柔性耦合或飞行鉴定。

三条相互隔离的证据链是：

1. 对 V2 与 V3_R2 九配置质量账本逐配置复算完整 B601 臂，并在 `ODR01_DYNAMICS_T_SM` 与 `WP11_PHYSICAL_GEOMETRY_CONTEXT` 两个互斥安装假设下报告误差。两个假设不选择、不平均；分支差不是不确定度。
2. 以 V3_R2/C07 总质量属性减去 ODR-01 安装下的完整臂，反演包含 bus、M3R、bridge 与部署锁定 R2 双翼的等效固定残余刚体；随后对 M07_ARM_ONLY 分别执行两条独立零状态、自由漂浮、刚性翼 Radau 动力学 lane。
3. 独立复算 R2 固定基座 3-DOF/wing ROM 的 leaf-only 发布矩阵与五个刚度角点；另加入质量脚本中的两个随动 inter-hinge 点质量形成冲突诊断，冲突矩阵不传播为动力学输入。

运行：

```powershell
python -B 30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/src/build_e21_diagnostics.py
python -B 30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/tests/validate_e21_diagnostics.py
python -B 30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/src/build_e21_diagnostics.py --check-only
python -B 30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/tests/validate_e21_diagnostics.py --check-only
```

机器结论只认 `results/E21_DIAGNOSTIC_GATE_V1.json`。测试 PASS 不授予任何 authority；模块总状态始终为 HOLD。
