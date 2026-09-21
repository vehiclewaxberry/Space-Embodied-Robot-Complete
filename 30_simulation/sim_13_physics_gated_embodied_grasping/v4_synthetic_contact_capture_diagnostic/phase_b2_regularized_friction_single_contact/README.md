# Sim13 V4 Phase B2：合成正则化摩擦单点接触诊断

本子包在已审计的 V4A 全浮动联合核和 V4B1 无摩擦单点接触之上，研究一个严格受限问题：合成球—link7 pad 的单点接触加入平滑正则化 Coulomb 摩擦后，能否仍闭合作用反作用、公共作用点力矩、线/角动量和能量—耗散账本。

摩擦系数与正则化速度均为合成暂定值，不是 B601 夹爪材料对、真空/温度摩擦磨损或硬件标定结果。本包没有双指接触、soft capture、锁定、释放或抓取成功状态，不关闭正式 NC19。

## 预注册物理合同

- 法向力沿用 B1 的非拉伸弹簧—阻尼模型。
- 切向力为 `F_t=-μF_n v_t/sqrt(||v_t||²+v_eps²)`，因此 `||F_t||≤μF_n` 且 `-F_t·v_t≥0`。
- 两物体使用同一惯性系公共作用点 `p_c`。
- 服务星 pad 与 `p_c` 在侵入时不重合，故服务星广义力必须包含 `J_vᵀF + J_ωᵀ[(p_c-p_pad)×F]`；该力矩移置用于消除虚假净角冲量。
- 正常阻尼耗散与摩擦耗散分别积分，最终只在同量纲能量账本 `T+U+D_n+D_t` 中汇总。
- R/P 通道与 P/H 分账规则不变。

预期名义状态序列仍只允许：

`SEPARATED → APPROACH → SINGLE_CONTACT → SEPARATING_AFTER_CONTACT`

禁止状态：`DUAL_CONTACT`、`SOFT_CAPTURE`、`LOCKED`、`GRASP_SUCCESS`。

## 证据顺序

在本目录依次运行：

```powershell
python -B -m pytest -q -p no:cacheprovider
python -B validate_phase_b2.py
python -B independent_audit_phase_b2.py
```

验证器只可生成 `PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT`；不导入 B2 求解器的独立审计器通过后，才可签发：

`PASS_PHASE_B2_SYNTHETIC_REGULARIZED_FRICTION_SINGLE_CONTACT_WITH_PHYSICAL_FRICTION_DUAL_CONTACT_LOCK_AND_CURRENT_SYSTEM_HOLD`

该 PASS 只代表 synthetic-only Phase-B2 诊断。物理摩擦识别、双指接触、soft capture、锁定、当前系统、正式 NC19、生产、release 与 next stage 始终为 false/HOLD。
