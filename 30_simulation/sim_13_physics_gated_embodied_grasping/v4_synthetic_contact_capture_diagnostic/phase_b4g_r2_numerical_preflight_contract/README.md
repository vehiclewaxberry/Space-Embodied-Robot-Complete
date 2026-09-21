# Phase B4G-R2：数值预检合同冻结（不执行）

本目录只冻结 B4G-R2 的三轨数值预检合同、顺序、阈值、失败规则和证据链；不实现 solver/rehydrator，不运行任何新轨迹或 physics campaign。合同 Gate 可为 `PASS_PHASE_B4G_R2_NUMERICAL_PREFLIGHT_CONTRACT_ONLY`，但执行就绪状态必须保持：

`HOLD_R2_PREFLIGHT_EXECUTION_NO_IMPLEMENTED_REHYDRATOR_OR_R2_SOURCE_FREEZE`

## 三轨与 78 个唯一执行单元

1. `FRESH_ACQ`：RK4 与 midpoint 各用 `0.25/0.125/0.0625 ms` 三点 2:1 ladder。每 lane 取 fresh `alpha=16,T_cmd=10 ms` 案的 acquisition 段作为观测；同 lane 的 `5/20 ms` acquisition 仅允许 `/case_id`、`/event/run_id`、`/acquisition/run_id` 不同，且替换前各自必须等于注册 case ID；三处替换为 `CASE_IDENTITY_EXCLUDED_V1` 后，完整对象的 canonical bytes/hash 必须与 10 ms 案精确相同，其他 JSON pointer、key、shape、type、value 一律不得改变。事件和证书逐案 fresh、有效、唯一；5/20 ms 只是技术重复，证书 hash 本身不作收敛量。
2. `FRESH_REFERENCE_G12`：六个 fresh lane 各有 A0 PRE/POST；`alpha=16 × T_cmd{5,10,20 ms}` 在六 lane 上共 18 案。两条最细 `0.0625 ms` lane 另补其余 15 个 level，各自产生 fresh B3/acquisition/removal provenance，形成 18 对、36 案 G12 reference。
3. `COMMON_PROP`：`alpha=16 × 3 durations × 6 lanes = 18` 案严格使用同一 donor identity，只比较 acquisition-relative `[0,T_cmd]` 的传播。所有 descendants 的 G12 credit 和 selector input 永远为 false；不授信 shared removal。

Fresh 合计 `12 A0 + 18 alpha16 + 30 additional reference = 60`，COMMON_PROP 为 18，总计 78。六个最细 alpha16 fresh 案同时属于预注册的 alpha16 与 G12 分析视图；其中两个 `T_cmd=10 ms` acquisition 段也属于 ACQ 观测。这是同一执行单元的声明式多响应，不计作独立重复。Fresh 与 COMMON_PROP 的 case ID、证据路径和可变对象完全隔离。

78-case 机器矩阵不允许 `null`：A0 的 `alpha/command_duration_s` 固定为 `NOT_APPLICABLE_A0`，A1 的 `sentinel` 固定为 `NOT_APPLICABLE_A1`；validator、独立 audit 和 pytest 都验证字段适用性。旧 raw 的 technical-repeat 投影只作只读规则 sanity anchor，三案均为 31050 canonical bytes、SHA256 `29DFA8D35BBBA4E615B583B09EBB1B32144C0FE39B740898F1A0EB7ED838511C`，不产生新执行 credit。

## Common donor 与执行阻断

Donor 固定为旧 preserved raw slot 052：

- raw bytes/SHA256：`69249` / `5DF0C19A71180E1BD91816235AAD50108613C2BC0F99F950018D786119CF9D4F`
- payload pointer：`/event_provenance/acquisition_certificate_payload`
- payload canonical bytes/SHA256：`31092` / `DA3E10D7D30DFD9BABFB71BF055D62A1BD06CF8DE3023E463A649FF92A952D15`
- derived common-state group canonical bytes/SHA256：`1317` / `396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444`

group payload 的 10 项 JSON-pointer 来源、canonicalization 和 COMMON_PROP 的 16 个通道/量纲/floor 已逐项冻结在 design JSON。未来实现必须拒绝 duplicate key 与非有限数，完整重建 typed `EventInput/AcquisitionResult`，使用 event configuration 和 acquisition `z_plus_reduced` 后碰速度，完整 include-matrices roundtrip 后 canonical bytes/hash 与 donor 精确相同。每个 COMMON_PROP case 必须获得独立深拷贝；执行前后 donor payload/state group hash 均须不变。当前没有该实现或 roundtrip 证据，也没有 R2 execution source-freeze，因此禁止执行。

## 冻结判据

- ACQ 时间：`D_FR <= 6.25e-5 s + 1e-15 s` 且 `D_FR <= 0.60 D_CF + 1e-15 s`。每个 native channel 独立以 `Linf`（四元数用下述稳定 geodesic）检验 `D_FR <= 0.60 D_CF + floor`；各通道的量纲和 floor 已逐项写入 design JSON。四元数须为 finite shape-4 `wxyz`，范数误差 `<=1e-12` 后才归一化；令 `s=+1` 当 dot `>=0`、否则 `-1`，距离固定为 `4 atan2(||q1-sq2||,||q1+sq2||)` rad，非法输入直接 FAIL。
- Fresh alpha16：每方法/时长三步 outcome parity 与 finite removal；完整旧 G03–G11/G16 语义通过；G04/G06 均 `<=1e-7 J`；removal 与 signed-work 同时受绝对门和 `0.60` Cauchy contraction 约束。
- COMMON_PROP：midpoint `D_FR<=2^-1.8 D_CF+floor`，其中冻结常数为 `0.2871745887492587`；RK4 `D_FR<=2^-3 D_CF+floor=0.125 D_CF+floor`。最细跨方法差使用相同 `p_min=1.8/3.0` 的 Richardson denominator。旧 `0.30` 门不再成立。Signed work 使用原 G12 `max(1e-10 J,0.001 max|W|)`。
- empirical order 使用已知零极限的直接比值 `p_CF=log2(e_0.25/e_0.125)`、`p_FR=log2(e_0.125/e_0.0625)`，但由 total comparator 先做 finite/nonnegative 与 floor 分支。相关残差全在 floor 内时直接 floor PASS；coarse 在 floor、fine 越出时 regression FAIL；coarse 超 floor 且 fine 精确为零时以 `EXACT_ZERO_FINE_POSITIVE_ORDER_LIMIT` PASS，绝不把 Infinity/NaN 写进 JSON；仅两值均超 floor 才求 log2。G04 与 midpoint G06 的 floor scope 为 fine+reference，RK4 G06 为 all-three。

G04 runner/validator 统一为 `B4G_R2_G04_UNIFIED_STAGE_CUMULATIVE_TERMINAL_AND_POST_CARRY_V1`：`W[0]==0`；sample/stage power 独立从 `Q[12:14]·eta[12:14]` 复算，二者均 `atol=1e-14 W, rtol=0`；累计 trapezoid 与 augmented W 的全时刻最大误差、native terminal 误差均 `<=1e-7 J`；保留 every-second refinement；finite removal 后每个保存 post sample 的 W 必须精确等于 active terminal、reset 必须为 false、14 个 Q 分量必须逐个精确为零。18 个 required fields 和完整布尔表达式在 runner/validator 侧逐字相同。禁止删检查、把 RK4 冒充 midpoint、删 alpha16、调宽 G06 或令 `W=ΔT`。

G12 只消费 36 个 fresh reference 案。结构化 aggregate PASS 表示 18 个 record 均完整、合法评估；它不要求 18 个 scientific predicate 全真。两侧都无 finite event 可合法报告注册的 NA；仅一侧 finite 时 predicate 为 false。只有 `eligible_count>=1` 才可建议另行审查 A2-including campaign，且本合同始终不授权 full campaign。

## 绑定与运行

本包直接/递归绑定：B4G ACTIVE source-freeze terminal `B22C4D5...3464`、active invalidation `2743FBD3...B1D9`、RUN_SPEC、144-slot schedule、264-file raw inventory `916F395E...3DD5`，以及 R1 contract/Gate/terminal。

仅运行合同证据生成：

```powershell
python run_phase_b4g_r2_contract.py
```

runner 只运行本目录 pytest、合同 validator 与完全独立 audit，然后生成 contract-only Gate/terminal；它不导入或调用旧 solver。测试 PASS、validator PASS 或合同 Gate PASS 均不等于数值预检、科学 Gate、物理夹爪、current/formal/Owner/production/release/next-stage PASS。

全包递归护栏禁止 `null` JSON leaf、`.pyc/.tmp/.npz/.csv/.urdf/.step/.stp`、`__pycache__/.pytest_cache`、solver 模块或文件。生成顺序固定为 validation/snapshot → self-excluded manifest → independent audit → contract-only Gate → terminal；terminal 最后生成且自排除。
