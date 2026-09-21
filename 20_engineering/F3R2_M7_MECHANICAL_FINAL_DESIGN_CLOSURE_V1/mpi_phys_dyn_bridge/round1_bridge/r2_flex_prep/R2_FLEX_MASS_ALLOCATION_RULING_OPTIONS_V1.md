# R2 柔性质量分配裁决选项备忘录 V1（AGENT-3 / round1_bridge / r2_flex_prep）

- schema: `R2_FLEX_MASS_ALLOCATION_RULING_OPTIONS_V1`
- 生成时间：2026-08-23T17:21+08:00（宿主机本地钟）
- 状态：**DRAFT_FOR_AUTHORITY_RULING —— 本备忘录不自我生效**。裁决权属 MPI/动力学权威（owner）。在权威下达唯一显式裁决并置 `dynamic_mass_allocation_frozen=true` 之前，`selected=false`、`propagated_to_free_floating_dynamics=false` 的 e21 现状逐字保持。
- 范围：纯文本裁决准备。本轮未启动任何 CAD/FEA/仿真进程；未修改/重生成任何 accepted 资产（URDF、Solar R2、e21 模块、上游 ledger、Gate JSON 全部只读）；全部数字经本代理以 numpy/scipy 复核（复核记录见 §6）。
- 输入基线：`round0_handover/03_r2_flex_inputs/R2_FLEX_INPUT_INVENTORY_V1.json/.md`（sha256:12 `82ded3493069`）。
- 纪律：禁止两矩阵取平均、禁止静默传播任一、禁止 null 填 0、禁止多数投票、禁止把 MC-A/B/C 之外的混合记账伪装成裁决。

## 0. 请求裁决的事项

每翼 2 个 0.03 kg 移动板间铰点质量在**质量脚本中存在、leaf-only ROM 动能中缺失**（e21 E21-G21 登记，`CONFLICT_NONSELECTING_NONPROPAGATED`）：

```
Mqq*  −  Mqq  =  [[0.006, 0.0024, 0   ],
                  [0.0024, 0.0012, 0   ],
                  [0,     0,     0   ]]  kg·m²        （e21 ROM JSON，逐字）
```

- `Mqq`（leaf-only，已发布于 `FLEXIBLE_APPENDAGE_R2.yaml wing_L2_reduced_model.mass_matrix_kgm2`，e21 复现误差 5.0e-10 kg·m²，E21-G19 PASS）；
- `Mqq* = Mqq + ΔM`（含移动铰点质量，e21 诊断量，未发布、未冻结）。

请 MPI/动力学权威在 MC-A / MC-B / MC-C 中下达**单一、显式、书面**裁决，并在 MPI ledger 记录 `ruling_id` 与 `dynamic_mass_allocation_frozen=true`。

## 1. 冲突事实复核（本代理 numpy/scipy 重算，可复核）

模型：每翼 3-DOF 相对铰转角链，`K = diag(k_root, k_inter, k_inter)`，广义特征值 `eigh(K, M)`。五工况逐数字复现已发布频率，最大误差 4.84e-05 Hz（与 E21-G20 一致）。

| 工况 (k_root, k_inter) N·m/rad | leaf-only 车道 Hz（=已发布） | 冲突车道（Mqq*）Hz | 冲突−leaf Hz | 相对漂移 %（本代理重算） |
|---|---|---|---|---|
| nominal (200, 100) | 6.972602 / 39.358623 / 98.004248 | 6.727892 / 36.626689 / 84.871646 | −0.244710 / −2.731933 / −13.132602 | **−3.5096 / −6.9411 / −13.4000** |
| all_low (50, 20) | 3.327765 / 18.295207 / 44.176340 | 3.214641 / 17.012669 / 38.241458 | −0.113124 / −1.282538 / −5.934882 | −3.3994 / −7.0102 / −13.4345 |
| all_high (800, 400) | 13.945204 / 78.717246 / 196.008496 | 13.455784 / 73.253379 / 169.743292 | −0.489419 / −5.463867 / −26.265204 | −3.5096 / −6.9411 / −13.4000 |
| root_low_inter_high (50, 400) | 4.342412 / 65.014613 / 190.531867 | 4.157820 / 60.858298 / 165.304162 | −0.184592 / −4.156315 / −25.227705 | −4.2509 / −6.3929 / −13.2407 |
| root_high_inter_low (800, 20) | 4.736852 / 30.298578 / 74.959663 | 4.614524 / 27.685679 / 65.481282 | −0.122327 / −2.612898 / −9.478382 | −2.5825 / −8.6238 / −12.6446 |

判读（供裁决参考，不构成裁决）：

- 第三阶模态漂移在全刚度带角上稳定 ≈ **−13%**（−12.64%..−13.43%）；第一阶（捕获激励主频带，已发布 3.33–13.95 Hz）漂移 −2.58%..−4.25%，冲突车道第一阶带变为 **3.2146–13.4558 Hz**。
- 反向表述：leaf-only 车道频率相对冲突车道高 +3.64% / +7.46% / +15.47%（nominal），即 MC-A 的柔性响应系统性偏刚。
- 质量闭合不受裁决影响：每翼 0.78 kg = 3×0.18（叶）+ 0.05（根铰）+ 2×0.03（板间铰）+ 0.08（HDRM）+ 0.05（harness）；两翼 1.56 kg；整星 24.8632134 kg（24 kg 预算重分配 OPEN，GAP-12，不在本备忘录裁决范围）。**两车道总质量相同，差别只在动能分配（ROM 内 vs 刚性界面）。**

## 2. 选项 MC-A：冻结 leaf-only Mqq 为 ROM/动力学权威

- **规则**：每翼 2×0.03 kg 铰点质量作为**刚性、非随动**界面质量集中记账在铰线处（结构质量账本已有此 0.06 kg/翼），不进入 ROM 动能；ROM/动力学唯一权威质量阵 = 已发布 `Mqq`。
- **物理含义**：铰点被处理为随铰线刚体运动的集中质量，其对翼内相对坐标的惯性贡献（ΔM）被忽略。对低阶模态影响小（第一阶仅 −2.6%..−4.3% 量级的记账差异），对第三阶（翼内反相模态）记账差异 ≈13%。
- **对 nominal 频率的影响**：保持已发布 6.9726 / 39.3586 / 98.0042 Hz 及五工况带角不变；无任何已发布证据失效。
- **对 e15 重认证的下游影响**：认证对象的质量阵不变 → 触发条件 T2（质量阵变更）不因此触发；T1（新全耦合模型消费 R2 柔性翼）仍必然触发。e15 重认证范围不因本裁决扩大。
- **对 sim_11 耦合的下游影响**：新 R2 耦合模型可直接引用已发布五工况频率带与 Mqq；GAP-03（参与因子）/GAP-04（强迫响应）仍需按 `R2_ROM_PARTICIPATION_DAMPING_SPEC_DRAFT_V1.md` 闭合后才有全耦合；旧 R1 卡（0.3483933 kg、1.0 Hz 包络）继续仅限历史复现，禁止入 R2 车道（e21 `forbidden` 逐字有效）。
- **所需证据/动作**：MPI 质量分配记录一行裁决（ruling_id + `dynamic_mass_allocation_frozen=true`）；铰点质量的刚性界面记账条目指认（`SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json mass_model.hinge_inter_kg_each`，已有）。**无需重发任何上游文件。**
- **残余风险**：若 WP5 实测铰点质量显著偏离 0.03 kg/个，或实测表明铰点随动惯性不可忽略（第三阶模态敏感），须按变更流程重开；该风险以显式备注入 ledger，不作静默。

## 3. 选项 MC-B：冻结 Mqq*（含移动铰点质量）为权威

- **规则**：ROM/动力学唯一权威质量阵 = `Mqq* = Mqq + ΔM`；铰点质量随翼内相对坐标运动进入动能。
- **物理含义**：记账物理更完整（铰链硬件确实随板间铰运动）；柔性整体偏柔。
- **对 nominal 频率的影响**：全部下移 −0.2447 / −2.7319 / −13.1326 Hz（−3.51% / −6.94% / −13.40%）；五工况带角同步下移（见 §1 表）。
- **对 e15 重认证的下游影响**：已发布 `FLEXIBLE_APPENDAGE_R2_MODES.json` 对动力学失效 → 五工况证据须以**新版本**重发（ODR-44 与本轮纪律禁止重生成上游 accepted 文件，只能下一轮授权后进行）；e15 认证对象改变（T2 触发），重认证范围扩大且须等新证据包。
- **对 sim_11 耦合的下游影响**：新 R2 耦合运行在新证据包到位前无权威频率可引用 → 柔性车道整体延后；刚性翼车道不受影响。带宽/模态能类结论（历史 sim_11 加密链 0.48%/0.027% 为 R1 卡口径，本就要重跑）将以新带重新评估。
- **所需证据/动作**：MPI 裁决 + 新版本 ROM 证据包（Mqq*、五工况重扫、e21 式独立复现 Gate）+ 铰点质量的设计权威确认或 WP5 实测。
- **残余风险**：证据断档期内全部柔性数字双轨悬空；任何提前消费 Mqq* 的行为属未授权传播（e21 `propagated_to_free_floating_dynamics=false` 逐字约束）。

## 4. 选项 MC-C：维持 HOLD（暂不冻结）

- **规则**：两矩阵并册登记，禁止任何柔性动力学消费，直至硬件实测到位。
- **物理含义**：不承认任一分配；频率二值歧义（最高 −13.40%）作为开放项携带。
- **对 nominal 频率的影响**：无权威值；已发布五工况继续保持 PROVISIONAL_DERIVED、仅限定基座自由振动口径。
- **对 e15 重认证的下游影响**：不触发也不闭合；`e15_ancf_certification=REPEAT_ANCF_CERTIFICATION` 维持。
- **对 sim_11 耦合的下游影响**：`r2_full_flexible_coupling=NOT_EVALUATED` 持续；仅刚性翼车道可走；论文硬伤（帆板质量/刚度占位，AGENTS.md 待办 3）继续挂起。
- **所需证据/动作**：显式 HOLD 记录一行。
- **残余风险**：与现状兼容但不推进闭合；提交硬截止 2026-09-01 前全柔性证据链保持缺口。

## 5. 三选项对比表

| 维度 | MC-A（leaf-only 权威） | MC-B（Mqq* 权威） | MC-C（维持 HOLD） |
|---|---|---|---|
| nominal 频率 | 6.9726/39.3586/98.0042 Hz 不变 | −3.51%/−6.94%/−13.40% 下移 | 无权威值 |
| 已发布证据 | 全部保持权威 | MODES.json 失效待重发 | 保持 PROVISIONAL |
| 刚体质量闭合 | 不变（0.78 kg/翼已含 0.06 kg） | 不变 | 不变 |
| e15 范围 | 不扩大（仅 T1 等常规触发） | 扩大（T2 触发+证据重发） | 不触发不闭合 |
| 柔性响应偏差 | 偏刚（第三阶 ≈+15.5% 相对冲突车道） | 物理更完整 | — |
| 上游文件再生 | 无 | 必须（下一轮授权后） | 无 |
| 闭合推进 | 立即解锁 ROM 扩展文本→计算 | 延后至证据包重发 | 不推进 |

## 6. 推荐意见（待 MPI/动力学权威裁决，本条不自我生效）

- **倾向 MC-A**：与已发布且经 e21 独立复现（G19 质量阵 5.0e-10、G20 频率 4.84e-05 Hz）的证据相容，扰动最小，立即解锁 GAP-03/04 的后续闭合；其物理近似（铰点刚化）的影响集中在第三阶模态（≈13% 记账差异），而捕获激励主频带为第一阶（差异 ≤4.3%），且整体方向是柔性响应偏刚=偏保守的一侧。
- MC-B 物理更全但强制重发证据链，在 2026-09-01 硬截止前制造断档期；MC-C 与现状兼容但不推进闭合。
- **裁决权属 MPI/动力学权威（owner）。本备忘录的任何倾向性表述不构成冻结；在书面裁决落账前，e21 三 false 状态逐字有效。**
- 复核记录：§1 全部数字由本代理以 `scipy.linalg.eigh(K, M)` 在 Mqq/Mqq* 双车道重算（五工况 K 取自 e21 ROM JSON；Mqq/Mqq* 取自 e21 ROM JSON 逐字）；质量闭合 0.78/1.56/+0.8632134/24.8632134 kg 重算一致。

## 7. 源文件哈希绑定（sha256:12，本代理 2026-08-23 实测）

| 文件 | sha256:12 |
|---|---|
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml` | `a04acfe440c6` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2_MODES.json` | `e068de078a0d` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json` | `d5b7dd16532f` |
| `30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json` | `57958a9f3ac1` |
| `30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_DIAGNOSTIC_GATE_V1.json` | `b03b7c7af571` |
| `30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml` | `7d2e0792b3ff` |
| `30_simulation/e15_ancf_certification/results/gate_summary.json` | `aab4d609e219` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round0_handover/03_r2_flex_inputs/R2_FLEX_INPUT_INVENTORY_V1.json` | `82ded3493069` |
