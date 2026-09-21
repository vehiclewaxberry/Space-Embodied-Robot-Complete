# Sim13 V4 Phase B1：合成无摩擦单点柔顺接触诊断

本子包只回答一个受限问题：Phase A V3 的公开全浮动 `6R+2P` 服务星模型与独立 `22 kg` 合成目标，能否在同一 RHS、同一积分子步中形成可审计的无摩擦单点柔顺接触，并闭合几何、作用反作用、冲量、角冲量和能量—耗散账本。

这只是 **synthetic contact analogue**。球半径、刚度、阻尼、初始间隙和速度均为合成暂定值，不是 B601 或夹爪实测值。本包没有双指接触、摩擦、soft capture、锁定或抓取成功状态；也不是正式 contact backend，不能关闭正式 NC19。正式 Sim13 V2 仍为 **15/20**，NC15/NC16/NC18/NC19/NC20 全部 HOLD。

## 冻结物理合同

- 服务星速度：`nu_s=[v_b^I(3), omega_b^I(3), qdot_R(6), qdot_P(2)]`。
- 服务星方程：`M(q) nudot+h(q,nu)=J_pad^T F_service`，使用 Phase A V3 的完整 `14×14` 自由基座—关节耦合质量阵。
- 目标与服务星在一个组合状态中同步推进；姿态为 body-to-inertial 四元数，角速度在惯性系表达。
- 合成球与 link7 固定局部 pad 点：`g=||p_pad-p_t||-R`、`delta=max(-g,0)`、`n=(p_pad-p_t)/||p_pad-p_t||`。
- 公共作用点：`p_c=p_t+R n`。服务星受 `+Fn n`，目标受 `-Fn n`；目标转矩用同一个 `p_c`。
- `delta<=0` 时 `Fn=0`；否则 `Fn=k delta+c max(-v_rel,n,0)`，不允许拉力。
- R 通道按 `rad / rad/s / N·m` 分列，P 通道按 `m / m/s / N` 分列。线动量 `N·s` 与角动量 `N·m·s` 永不拼成一个范数。

状态机唯一名义序列为：

`SEPARATED → APPROACH → SINGLE_CONTACT → SEPARATING_AFTER_CONTACT`

非法值、NaN、过穿透、非法重接触或积分失败进入 `ABORTED_SAFE`。不存在 `DUAL_CONTACT`、`SOFT_CAPTURE`、`LOCKED` 或 `GRASP_SUCCESS`。

## 证据顺序

在本目录依次运行：

```powershell
python -B -m pytest -q -p no:cacheprovider
python -B validate_phase_b1.py
python -B independent_audit_phase_b1.py
```

验证器只生成 `PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT` 预审 Gate。独立审计重新计算接触几何、力律、冲量、P/H/E+D、事件和严格 DAG，审计通过后才生成最终 Gate：

`PASS_PHASE_B1_SYNTHETIC_FRICTIONLESS_SINGLE_CONTACT_WITH_FRICTION_LOCK_AND_CURRENT_SYSTEM_HOLD`

最终复现后检查目录不得留下 `__pycache__`、`.pytest_cache`、URDF、正式 interface 或 authorization 文件。

## 权限边界

以下标志始终为 `false` / `HOLD`：当前系统绑定、正式 contact backend、正式 NC19 关闭、接触抓取成功、Owner 授权、生产就绪、release、next stage、摩擦、双接触、soft capture、锁定。Phase B1 的 PASS 只代表这一合成单点接触诊断通过。
