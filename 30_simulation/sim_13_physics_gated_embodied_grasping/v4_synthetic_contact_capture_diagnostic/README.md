# Sim13 V4A：合成全浮动接触路线 Phase A

## 工程裁决

本目录完成接触后端路线的 **Phase A（无接触算法诊断）**：一个手写的合成 6R+2P 自由漂浮服务星，与一个独立目标 6DOF 刚体，在同一时间轴上执行零重力、零外力、零接触传播。它建立的是后续接触算法所需的全浮动动力学底座，不是接触、捕获或现行 Unified-R2/B601 绑定证据。

最终审计裁决为：

`PASS_PHASE_A_SYNTHETIC_FULL_FLOATING_KERNEL_WITH_CONTACT_AND_CURRENT_SYSTEM_HOLD`

其中 `PASS` 只覆盖本目录的合成 Phase-A 数值内核；接触、当前系统、Owner、生产、发布和下一阶段授权全部保持 `false/HOLD`。主验证器不能直接签发该最终状态：它只生成 `PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT` 的 pre-audit Gate，最终 Gate 仅由独立审计脚本在全部检查通过后生成。

## 状态与物理合同

- 服务星速度：`nu_s=[v_b^I(3), omega_b^I(3), qdot_R(6), qdot_P(2)]`。
- 基座姿态：单位四元数 `q_BI=[w,x,y,z]`，不使用欧拉角作积分状态。
- R 通道：rad、rad/s、N·m；P 通道：m、m/s、N。完整 14×14 质量阵是混合单位块矩阵，禁止贴单一单位。
- 质量阵由每个刚体的平移/转动 Jacobian 显式求和，保留自由基座—8 关节耦合块。
- 无外力方程：`M(q) nu_dot + h(q,nu)=0`。`h` 由 `Jdot*nu` 和陀螺项组成；本阶段不施加接触或关节驱动力。
- 点运动学从 link-local 点映射到惯性系，平移 Jacobian 与构型切空间中心差分核验，并验证整体刚体变换协变性。
- 服务星、目标、组合体均分别报告线动量 `N·s`、关于同一惯性原点的角动量 `N·m·s` 和动能 `J`；绝不把线/角动量拼成六维异量纲范数。

## 验证范围

- 确定性非零速度场景和固定步长 RK4；
- 质量阵对称正定、基座—关节耦合、直接刚体动能交叉核对；
- 服务星与目标各自的 P/H/E 守恒、组合体 P/H/E 守恒、四元数单位范数；
- 步长减半收敛；
- 10 个显式冻结、无随机数的多构型应力点，覆盖全部 8 个 link 的 point Jacobian；
- 独立审计以五点构型有限差分重建各刚体 Jacobian 和质量阵，不导入 validator，也不调用主 `bias_effort`；
- 独立 Euler–Lagrange 关节方程审计：6 个显式冻结、无 RNG、R/P 构型与非零速度各异的状态（含名义态），每态使用 `5e-7/1e-6/2e-6 rad 或 m` 三个外层差分平台；使用哈希绑定的主加速度，以及独立 `M_fd`、`Mdot`、`∂M/∂q_j`，分别裁决 6 个 R 通道 N·m 残差和 2 个 P 通道 N 残差，并冻结全状态最坏值及状态 ID；
- EL 的 `scaled_by_reference_1_*` 仅表示除以固定 `1 N·m` 或 `1 N` 的诊断缩放，不称相对残差或物理归一化；
- 零基座广义动量率、零功率的内部错误加速度/广义力变异：真实运行粗/细两组 RK4 错误 ODE，必须同时证明该错误 ODE 自收敛、旧 P/H/E 守卫仍接受，而新 EL 残差拒绝；R/P 错误力分账；
- 六类故障注入：基座锁死、漏耦合块、R/P 单位缩放、NaN/非单位四元数、Jacobian 符号翻转、point offset 丢失。

## 治理边界

本目录：

- 不导入或调用 Unified-R2 私有构造器/生成器；
- 不创建 `.urdf`、正式机械—具身接口或授权文件；
- 不继承 M4/M7/Route-C/Owner/发布结论；
- 不关闭正式 NC19，也不关闭 NC15/NC16/NC18/NC20；
- 保持正式 Sim13 V2 状态为 **15/20 PASS，5/20 dependency HOLD**。

## 复现

在本目录执行：

```text
python -B -m pytest -q -p no:cacheprovider
python -B validate_phase_a.py
python -B independent_audit_phase_a.py
```

顺序不可颠倒：`validate_phase_a.py` 会先删除同版本旧 audit/final/terminal，重新冻结 source/ledger/validation/evidence，并仅签发 pre-audit Gate；`independent_audit_phase_a.py` 随后逐边核验 `path + bytes + SHA-256 + role`，拒绝重复路径、未知 role、自引用、回边和根逃逸，完成 IA01–IA12 后才签发最终 audited Gate。

证据 DAG 为：source inputs → source manifest → ledger/validation → evidence manifest → pre-audit Gate → independent audit receipt → final audited Gate → self-excluded terminal manifest。terminal 同时绑定 audit 与 final Gate，并复核下游写入前后所有上游哈希不变。
