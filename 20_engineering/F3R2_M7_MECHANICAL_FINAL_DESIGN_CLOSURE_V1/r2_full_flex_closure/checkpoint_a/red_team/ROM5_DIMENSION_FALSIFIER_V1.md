# Checkpoint-A 独立红队证据：Solar R2 ROM5 维数证伪

## 裁决

`ROM5_FULL_FIELD_TRUNCATION_FALSIFIED_AT_1PCT`

Round3 的 183-DOF HF 模型、`B_t/B_r`、`Phi/Gamma` 与五类重构算子未发现接线错误；但是当前每翼五模态 `B1+B2+B3+T1+T2` 对 20 ms 无阻尼接触后的扭转峰值相对 HF 误差为 **3.505870603%**，不能满足全部已发布场量均不超过 1% 的判据。

本证据不修改 Round3，不继承 e15，不产生机械释放信用。

机器结果见 `ROM5_DIMENSION_FALSIFIER_V1.json`。独立复算命令：

```text
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/red_team/recompute_rom5_dimension_falsifier.py
```

## 输入与隔离边界

复算器只读取：

- `round3_hf_rom_v2/R2_HF_ROM_NUMERICAL_DATA_V2.npz`
  - SHA-256：`8D10E085385EDF2FACE92B9B48D1172939A31FD3B57E55242ED11C9EEEDF50DA`
- `round3_hf_rom_v2/R2_FIVE_MODE_ROM_V2.json`
  - SHA-256：`9E4FE903AE7E34584F39F16275EF20FC31831AFB7F78B3B625418B86D0FBC817`

脚本不 import、读取或修改 e22 实现。用于激励的 `base_delta_twist_6` 是独立红队收到的诊断输入；本证据不重新推导、也不授予该耦合捕获结果物理权威。

## 方程与解析交叉

HF 方程与 ROM 投影为：

```text
M qdd + K q = -Bt vbase_dot - Br omega_base_dot
Mrom = Phi.T M Phi
Krom = Phi.T K Phi
Gamma_t = Phi.T Bt
Gamma_r = Phi.T Br
```

基座速度变化对应的广义冲量为：

```text
f_impulse = -(Bt delta_vbase + Br delta_omega_base)
```

20 ms 单位积分半正弦为：

```text
g(t) = pi/(2 Tc) sin(pi t/Tc),  0 <= t <= Tc
integral(g dt) = 1
```

无阻尼单模态解析响应为：

```text
y_i(t) = F_i*pi/(2Tc)/(omega_i^2-Omega^2)
         * [sin(Omega*t) - Omega/omega_i*sin(omega_i*t)]
Omega = pi/Tc
```

独立 DOP853 两阶段数值积分与解析解交叉：

- 广义位移相对峰值尺度差：`3.7098e-12`
- 广义速度相对峰值尺度差：`5.9536e-12`
- tip peak 相对差：`3.5750e-12`
- torsion peak 相对差：`3.1940e-15`

401 点梯形积分为 `0.9999948595757563`；解析求解使用闭式单位积分，不以该离散积分近似驱动响应。

## 代数与接口审计

- `Phi.T @ M @ Phi - I` 最大绝对值：`2.22e-15`
- `Mrom - Phi.T @ M @ Phi`：0
- `Krom - Phi.T @ K @ Phi`：0
- `Gamma - Phi.T @ B`：0
- `R_HF @ Phi - R_ROM`：五类算子均为 0
- 实际激励下 HF 力投影与 Gamma 路径最大残差：
  - LEFT：`1.73e-18`
  - RIGHT：`2.60e-18`

因此 3.5% 差异不是 `B/Gamma`、符号、模态映射或输出算子错误。

## 当前 ROM5 的误差分量

20 ms、`zeta=0`、401 个接触点加 5001 个接触后点：

| 指标 | LEFT 相对误差 | RIGHT 相对误差 |
|---|---:|---:|
| `R_w_nodes` peak | 0.000530% | 0.001126% |
| `R_theta_dofs` peak | 0.002327% | 0.001644% |
| `R_hinge_relative` peak | 0.035073% | 0.021298% |
| `R_torsion_nodes` peak | **3.505871%** | **3.505871%** |
| `R_tip_w` peak | 0.000530% | 0.001126% |
| 总模态能峰值 | 0.000127% | 0.000121% |

扭转峰值：

```text
HF   = 5.496536692972348e-05 rad
ROM5 = 5.303835228846798e-05 rad
```

10 us 全窗扫描并在候选峰附近以 0.1 us 加密后：

```text
HF   = 5.496584867874807e-05 rad @ 0.529062 s
ROM5 = 5.303858599805212e-05 rad @ 0.0499424 s
error = 3.506291137%
```

HF 峰值约为分母保护值 `1e-14` 的 `5.5e9` 倍，故不是 near-zero denominator。官方采样与加密采样给出同一裁决。

## 物理根因

20 ms 半正弦的频谱中心为 25 Hz，位于 T2 与 T3 之间：

| 模态 | HF 0-based 索引 | 频率 | 家族 |
|---|---:|---:|---|
| T2 | 2 | 18.779307 Hz | 纯扭转 |
| T3 | 4 | 31.313147 Hz | 纯扭转 |
| T4 | 5 | 43.868450 Hz | 纯扭转 |

HF 峰值时，被 T1/T2 截掉的扭转尾部约为 `1.93003e-06 rad`，其中 T3 约 `1.33161e-06 rad`、T4 约 `4.42578e-07 rad`。T1/T2 对扭转子空间接触后能量的覆盖率为 `97.8504%`；总能量误差很小，是因为扭转能量被大得多的弯曲能量掩盖。

## 792 个五维特征模态子集

复算器穷举前 12 个 nominal HF 特征模态的全部 `C(12,5)=792` 个五维子集。每个子集对 LEFT/RIGHT 的 tip、node、slope、hinge、torsion 和总模态能峰值同时计分。

```text
score = max_wing,metric(
  abs(candidate_peak - HF_peak) / max(abs(HF_peak), 1e-14)
)
```

| 方案 | HF 0-based 索引 | 模态组成 | 最坏误差 | 控制项 |
|---|---|---|---:|---|
| Round3 | `[0,1,2,3,7]` | B1+B2+B3+T1+T2 | 3.505871% | torsion |
| 最佳 5D | `[0,1,2,3,4]` | B1+B2+T1+T2+T3 | **1.082964%** | torsion |
| 最小通过 6D | `[0,1,2,3,4,5]` | B1+B2+T1–T4 | 0.657581% | LEFT hinge |
| 保留三弯的 7D | `[0,1,2,3,4,5,7]` | B1–B3+T1–T4 | 0.271439% | torsion |

在该已声明的合理特征模态池中，没有五维方案满足 1%。最佳五维方案虽然仍符合 Owner P2 的数量范围，但违反 Round3 已发布的“三弯两扭”规则，且仍然失败，故不能作为修复。

nominal 20 ms 下，若允许删除 B3，最少需 6 模态；若保留三弯，最少需 7 模态。两者均超过 Owner P2 的 `3–5 dominant modes / wing` 上限，必须由 Owner 改权后作为 Round4 ROM 重新签发并重跑组件及耦合 Gate，不能静默替换。

## 接触窗敏感性

| 接触窗 | 当前 T1+T2 扭转峰值误差 | 达到 1% 所需最低扭转模态数 |
|---:|---:|---:|
| 5 ms | 7.8699% | 8 |
| 10 ms | 6.2600% | 5 |
| 20 ms | 3.5059% | 4 |
| 50 ms | 0.1186% | 2 |
| 100 ms | 0.1880% | 2 |

因此 nominal 20 ms 下的 6/7 模态结论不能外推为 5–100 ms 全窗覆盖。

## static/residual correction 裁决

标准静态 residual flexibility：

```text
q_res = (K^-1 - Phi Krom^-1 Phi.T) f(t)
```

在 `t > Tc` 时因 `f(t)=0` 而严格归零。HF 与 ROM 的控制峰值都出现在接触结束后，所以静态 residual 或自由响应中的 mode-acceleration correction 不能补回被截掉的 T3/T4 振铃。若引入持续的动态 residual 卷积核，它实质上是额外动态状态或 HF 卷积器，不能继续宣称为独立五模态 ROM。

## Checkpoint-A 合同处置

建议状态：

```text
DIAGNOSTIC_COMPLETE_WITH_PROVISIONAL_PHYSICS__
ROM5_FULL_FIELD_TRUNCATION_FAIL__
NO_E15_OR_RELEASE_CREDIT
```

- Round3 组件 HF/ROM Gate 不由本证据改写；本证据只证伪新的全场 1% 动态截断主张。
- 当前 nested `m3 -> m4 -> m5` 从 m3 起始终保留相同的 T1/T2，单看相邻阶差异会漏检扭转尾部；必须保留本 HF 对照。
- e15 维持 `REPEAT_ANCF_CERTIFICATION / NOT_INHERITED`。
- 不放宽 1% 阈值，不删除 torsion 指标，不把绝对幅值较小等同于相对 Gate PASS。
- `review_status=PENDING_OWNER_REVIEW`
- `owner_accepted=false`
- `next_stage_authorized=false`
- `release_credit=false`

## Nonclaims

- 未 import、修改或为 e22 提供自证。
- 未独立重建耦合捕获的 base delta twist。
- 前 12 特征模态穷举不是对任意非模态、响应训练基底的数学完备证明。
- 未作航天器—机械臂—目标全耦合动力学结论。
- 未作 ANCF/e15、飞行资格、Owner 接受或机械释放声明。
