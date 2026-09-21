# Post-capture spatial-inertia kernel candidate v1

## 裁决

本目录只验证一个可复用的刚性空间惯量组合内核：当服务星/机械臂现态质量属性、目标质量属性、当前末端位姿、**有权威的**末端—目标附着 `SE(3)` 和事件前总动量全部显式给定时，内核可合成捕获后组合体质量、质心和惯量，并生成一个“8 个关节位置保持、8 个关节速度锁零”的刚性聚合初态。

最大主张固定为：

```text
POST_CAPTURE_SPATIAL_INERTIA_KERNEL_SYNTHETIC_FIXTURE_PASS__CURRENT_C08_C09_NOT_EVALUATED__NO_CONTACT_ATTACHMENT_NONABORT_PARENT_OR_RELEASE_CREDIT
```

这不是接触模型、附着判定、冲量分配模型或完整捕获后 plant。刚性化事件允许耗散，**不验证也不声称动能守恒**。

## 为什么当前 C08/C09 必须停止在 NOT_EVALUATED

哈希冻结的现行状态合同对 C08/C09 都给出：

- `attachment_transform_S_rows.value = null`；
- `status = UNKNOWN_NOT_AUTHORITY_BOUND__M5_DISPLAY_TRANSFORM_NOT_PROMOTED`；
- `operational_attachment_authority = false`；
- `target_attached` 仅为 `MASS_PROPERTY_SCENARIO_SEMANTIC_ONLY__NO_PLANT_OR_CONTACT_AUTHORITY`。

现行动力学使用矩阵进一步限定：C08/C09 的设计目标质量/惯量只能用于 fixture，`target_attachment_plant_allowed=false`、`non_abort_operational_authority=false`、`parent_gate_credit=false`。M5 中的目标变换是 display-only，不能反推、零填或提升为 `T_E_T`。

因此两项当前系统实例的机器状态均为：

```text
NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3
```

## Frame、单位与公式

约定 `T_A_B` 把 B 坐标表达转换到 A：

```text
x_A = R_A_B x_B + p_A_B
T_B_T = T_B_E T_E_T
```

输入质量属性分别是：

- 服务星/机械臂现态聚合体：`m_s`、`c_s^B`、`I_s,C^B`；
- 目标：`m_t`、`c_t^T`、`I_t,C^T`；
- 事件位姿：`T_I_B`；
- 事件前总动量：惯性系线动量 `P_I`、关于明确定义点 O 的角动量 `H_O^I`，以及数值参考点 `origin_O_in_I_m`。

目标属性先旋转和平移到 B，然后计算：

```text
m = m_s + m_t
c^B = (m_s c_s^B + m_t c_t^B) / m
I_C^B = Σ [R I_i,C Rᵀ + m_i (||d_i||² E - d_i d_iᵀ)]
```

独立交叉链把每一刚体写成 `[v, ω]` 顺序的 `6×6` 空间惯量，关于 B 原点相加后反解 `m/c/I_C`。事件后刚性聚合体速度由：

```text
v_C^I = P_I / m
ω^I = (I_C^I)⁻¹ [H_O^I - (r_C^I-r_O^I) × P_I]
v_B^I = v_C^I - ω^I × (R_I_B c^B)
```

得到。输出含现有接口形状的 23 维物理状态 `[r_B^I(3), q_BI(4), q(8), qdot(8)]` 和派生 6 维基座 twist；当前时变 plant 明确拒绝非零总动量，因此该输出不能直接获得 plant 或父 Gate 信用。

质量采用 kg、位置采用 m、惯量采用 kg·m²、线动量采用 kg·m/s、角动量采用 kg·m²/s。6 个转动和 2 个移动关节始终分别保留 rad/m 与 rad/s、m/s，不用混合尺度条件数取得物理信用。没有硬件测量，也不传播或虚构测量不确定度。

## 合成 fixture 与 Gate

两个 fixture 仅沿用 C08 的 22 kg / 对角设计惯量和 C09 的 150 kg / 对角设计惯量作为数值测试值。服务体质量属性、目标 CG、末端位姿、附着变换、事件动量均为明确标注的合成精确值；尤其 `T_E_T` 的 authority 是 `SYNTHETIC_TEST_ONLY`。

`K01–K22` 覆盖：7 个源 pin、合同/frame/unit、C08/C09 fail-closed、display transform 禁止提升、合成输入与 `SE(3)`、平行轴组合、空间惯量独立交叉、惯量物理性、23+6 状态映射、P/H 守恒、零目标退化、共点刚性和、目标质量/惯量缩放、附着平移和旋转敏感性、frame covariance、能量不声称、确定性回放、变异负控、最小真实输入与全权限关闭。

## 接入现有 23 维 plant 前的最小真实输入

1. 当前构型服务星/机械臂聚合 `mass/CG/inertia`，必须来自哈希绑定的现态动力学后端。
2. 目标 `mass/CG/inertia`，含参考 frame、参考点和目标 ID。
3. 事件时 Unified R2 FK 的 `T_B_E` 与 8 维 `q`。
4. 真正 authority-bound 的 `T_E_T`、两端 frame ID 和附着权威 receipt；receipt 必须由内核内部加载且 canonical-hash 校验的合同预先 hash-pin，并绑定经实际 bytes/SHA 重算的构型状态合同与具体构型记录。API 不接受调用者提供的 contract，裸 status/boolean 不构成权限。
5. 同一事件的 `T_I_B`、`P_I`、`H_O^I`、O 的定义以及 `origin_O_in_I_m`。
6. 捕获后关节锁定集合、`qdot+` 策略以及约束冲量/锁闩权威。
7. 新的非零总动量 plant 合同：组合质量矩阵或空间惯量绑定、基座 twist 初始化 API；不能绕过当前 23 维 plant 的非零总动量拒绝。

## 验证

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B 30_simulation/r2_dynamics_engineering_closure/post_capture_spatial_inertia_kernel_candidate_v1/run_validation.py
```

`independent_validate_post_capture_spatial_inertia.py` 不导入核心源码或 evaluator，但它位于候选包内，因此如实分类为 **standalone internal**，不再声称组织独立。它从 evidence 原始 fixture 重算平行轴公式、6×6 空间惯量、事件状态、参考点平移后的 P/H、退化、缩放、敏感性和 frame covariance。真正的独立性由同级 `post_capture_spatial_inertia_kernel_external_audit_v1/` 包外冻结 pin 审计提供。

所有 `contact_valid`、`attachment_valid`、`target_attachment_plant_valid`、`hardware_valid`、`non_abort_authorized`、`parent_dynamics_engineering_complete`、`next_stage_authorized` 和 `release_credit` 均固定为 `false`。
