# Sim13 V4B4F：合成夹指回撤可达性合同冻结

## 当前裁决

本目录只冻结和审计未来 B4F 数值试验合同。它把 B4E 主支路中“两侧 P 关节继续闭合、截至 `0.08 s` 未出现移除事件”的负结果，转化为一个有界、可证伪的后续问题：在预注册的 **P-only 14D 内部广义力**离散网格内，是否能观察到完整的双侧 clearance dwell、零冲量移除和独立 `5 ms` 后释放审计。

当前没有 B4F 动力学求解器，没有执行 A0/A1/A2 campaign，也没有获得任何 synthetic reachability、实体驱动力、实体行程、保持捕获、释放、当前系统、正式 NC19、Owner、生产或下一阶段信用。

## 冻结边界

- 广义力向量为 14D，只允许零基索引 12、13 两个 P 关节通道非零；基座和 12 个 R 关节施加力严格为零。
- 功必须作为带符号状态积分：`W_act_dot = Q_P_left*qdot_P_left + Q_P_right*qdot_P_right`；能量账本为 `T + D - W_act = constant`，禁止重置或双计。
- A0 是零输入 B4E 重放；A1 是冻结的 `alpha × T_cmd` 全因子离散网格；A2 是延迟、半幅与单侧失效的左右镜像压力通道。
- 合成几何域严格为左右 P 坐标各自的闭区间 `[0, 0.0715] m`。任何积分 stage、样本或事件越界均 fail-closed，禁止截断和外推。
- 即使未来离散 campaign 出现成功，也只能报告 `lowest_tested_reachable_alpha_in_registered_discrete_grid`。禁止写成“最小所需力/功”，禁止层间插值或逆阈值估计。
- 数值合同预注册 22 个 future solver negative controls；合同审计只验证它们完整冻结，绝不声称这些未来执行路径已经运行或 PASS。

## 证据链

合同 validator 逐字节验证本地合同与 `PHASE_B4F_SOURCE_BINDINGS_V1.json`，并递归验证：

1. B4E terminal manifest 的全部记录；
2. B4E evidence manifest 的全部记录；
3. B4E source manifest 的全部源文件；
4. 冻结 B4 terminal manifest 与 final audited Gate（哈希必须分别保持 `09D261...B76E` 和 `55441D...1D92`）。

独立审计脚本不导入 B4F validator 或 pytest 测试，只读取 JSON/原始字节并用 `hashlib` 复算。JSON 采用同目录临时文件、`fsync`、`os.replace` 原子发布。evidence manifest 与 terminal manifest 均自排除，保持 DAG 无环。

## 执行

在项目根目录依次运行：

```powershell
python 30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4f_synthetic_jaw_retraction_reachability_contract/validate_phase_b4f_contract.py
python 30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4f_synthetic_jaw_retraction_reachability_contract/independent_audit_phase_b4f_contract.py
```

若 B4E 正在重签或 B4F 父绑定尚未刷新，validator 必须失败；不得绕过哈希门。最终 `PASS` 只表示“B4F 合同冻结且经审计”，不表示 solver implemented、campaign executed 或 reachability passed。

