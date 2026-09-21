# R2 柔性输入盘点 V1（AGENT-3 / round0 handover / 03_r2_flex_inputs）

- 生成时间：2026-08-23T16:33:48+08:00（宿主机本地钟）
- 范围：R2 全柔性闭合所需输入的逐项盘点。**纯文本/数值准备**，本轮未启动任何 CAD/FEA 进程，未修改/重生成任何 accepted 资产（URDF、Solar R2、上游 ledger、Gate JSON 全部只读）。
- 授权上下文：ODR-43（双框架显式桥接；mass/CG/inertia/界面载荷/CAD/碰撞几何只能经唯一 T_PHYSICAL_TO_DYNAMIC 桥进入动力学系，桥尚未建立）；ODR-44（MPI-01..MPI-08 全闭合前禁止 Route-C CAD 候选）。
- 本盘点**不做任何选择**：不平均、不归并、不把 null 填 0、不把 PROVISIONAL 当 authority。
- 同名机器可读件：`R2_FLEX_INPUT_INVENTORY_V1.json`（含 16 个源文件 sha256 绑定）。

## 1. 参数逐项状态表

| 参数 | 现值 | 状态 | 不确定区间 | 来源（均可复核） |
|---|---|---|---|---|
| 叶质量（每叶，每翼 3 叶） | 0.18 kg | PROVISIONAL | 无（点值；面密度候选 3.0 kg/m²，未实测） | SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json `mass_model` |
| 叶 EI | 名义 11.109 N·m²，带 [3.333, 33.327] | PROVISIONAL_DERIVED | 有（0.3×–3.0× 工程角点） | FLEXIBLE_APPENDAGE_R2.yaml；MODES.json `leaf_standalone` |
| 叶 GJ | null（卡片称 PROVISIONAL_DERIVED 但"band not yet assigned"） | NULL_EFFECTIVE | 无 | FLEXIBLE_APPENDAGE_R2.yaml `per_leaf.GJ_Nm2` |
| 根铰 kθ（= ODR-32 展开锁定态根部柔顺） | 50 / 200 / 800 N·m/rad | PROVISIONAL_DERIVED | 有（三点带，五工况已扫） | FLEXIBLE_APPENDAGE_R2_MODES.json `stiffness_bands_Nm_per_rad.root` |
| 板间铰 kθ（每翼 2 个；latch 柔顺折叠在内） | 20 / 100 / 400 N·m/rad | PROVISIONAL_DERIVED | 有（三点带，五工况已扫） | 同上 `inter`；yaml `latch_compliance.folded_into` |
| 五工况翼模态（定基座、leaf-only ROM） | nominal 6.9726 / 39.3586 / 98.0042 Hz；all_low 3.3278 / 18.2952 / 44.1763；all_high 13.9452 / 78.7172 / 196.0085；root_low_inter_high 4.3424 / 65.0146 / 190.5319；root_high_inter_low 4.7369 / 30.2986 / 74.9597 | PROVISIONAL_DERIVED | 有（带角） | FLEXIBLE_APPENDAGE_R2_MODES.json；e21 复现最大误差 4.84e-05 Hz（E21-G20 PASS）、质量阵复现 5.0e-10 kg·m²（E21-G19 PASS） |
| 阻尼 | 卡片占位 ζ=0.01（TBD_cite_literature）；ROM 中 damping_matrix=null | NULL_IN_ROM | 无 | yaml `damping`；e21 ROM JSON（E21-G22） |
| latch 独立刚度 | null（折叠进板间 kθ 带） | NULL | 无 | HDRM_LATCH_DESIGN_V1.yaml holds（HOLD_LATCH_GEOMETRY_NOT_MODELLED） |
| 根部支架/星体界面柔顺 | null（除根铰弹簧外无界面柔顺模型） | NULL | 无 | 全 R2 账本未检出；机构账本仅有 48.0 N·m 根部支架反力瞬态候选 |
| 铰链自由间隙 | null | NULL | 无 | HDRM_LATCH_DESIGN_V1.yaml：HOLD_FREEPLAY_LIMITS_NO_NUMERIC_AUTHORITY |
| 模态参与因子（自由漂浮基座耦合） | null | NULL | 无 | e21 ROM JSON `participation_factors=null` |
| 强迫响应（捕获激励经 R2 柔性传递） | null | NULL | 无 | e21 ROM JSON `forced_response=null`；权威合同 `r2_full_flexible_coupling=NOT_EVALUATED` |
| 标准不确定度（任何柔性参数） | null | NULL | 无（带角≠标准不确定度） | e21 ROM JSON `standard_uncertainty=null`；权威合同 uncertainty_policy |
| 移动板间铰点质量（每翼 2×0.03 kg） | 质量脚本有、leaf-only ROM 无 | CONFLICT_NONSELECTING_NONPROPAGATED | — | e21 ROM JSON `nonselecting_conflict_diagnostic`（E21-G21 PASS） |

质量闭合复核（本代理重算）：每翼 0.78 kg = 3×0.18 + 0.05（根铰）+ 2×0.03（板间铰）+ 0.08（HDRM）+ 0.05（harness）；两翼 1.56 kg；较 R1 +0.8632134 kg；整星 24.8632134 kg（24 kg 预算重分配 **OPEN**）。

## 2. 每翼 HF 模型与 3–5 主导模态 ROM 的输入缺口（GAP-01..12）

目标 HF 模型：每翼 3 柔性叶 + 2 板间铰 + 根铰/latch 柔顺（铰轴平行 X_S 手风琴链）；目标 ROM：每翼 3–5 主导模态、自由漂浮基座耦合。缺口清单（详见 JSON `hf_model_and_rom_input_gap_list`）：

- GAP-01 叶 GJ 值与带 → 阻塞 HF 扭转模态；GAP-02 有出处的阻尼模型 → 阻塞任何振铃衰减预测（sim_07 曾见 37–75 s 振铃，R2 未量化）；GAP-03 模态参与因子/动量耦合系数 → 阻塞 ROM-动力学耦合；GAP-04 强迫响应定义（捕获冲量/接触窗经 R2 柔性）→ 阻塞 A2 类场景；GAP-05 latch 独立刚度；GAP-06 根部支架界面柔顺；GAP-07 铰链自由间隙数值；GAP-08 叶实测构造数据（铺层/胞元/真实面密度）；GAP-09 **动态质量分配冻结**（本轮阻塞点之一）；GAP-10 T_PHYSICAL_TO_DYNAMIC 桥的消费规则（MPI-01..08）；GAP-11 e15 重认证；GAP-12 24 kg 预算重分配决策。

## 3. 移动板间铰质量冲突的解决选项（不归并、不传播现状下）

冲突事实（e21，E21-G21）：质量脚本给每翼 2 个 0.03 kg 移动板间铰点质量，leaf-only ROM 动能中无此项；Mqq*−Mqq = [[0.006, 0.0024, 0], [0.0024, 0.0012, 0], [0, 0, 0]] kg·m²；`selected=false`、`propagated_to_free_floating_dynamics=false`、`dynamic_mass_allocation_frozen=false`。nominal 工况冲突频移（本代理重算相对值）：−0.2447 / −2.7319 / −13.1326 Hz = **−3.51% / −6.94% / −13.40%**；all_high 工况第三阶达 −26.2652 Hz。

纪律约束：禁止两矩阵取平均、禁止静默传播任一、禁止 null 填 0、禁止多数投票；冻结必须单一、显式、由 MPI/动力学权威记录。选项：

- **MC-A**：冻结 leaf-only Mqq 为 ROM/动力学权威；每翼 2×0.03 kg 作为**刚性**界面质量集中记账在铰线处（不进 ROM 动能）。后果：已发布五工况频率保持权威，刚体质量闭合不变（0.78 kg/翼已含此 0.06 kg）；柔性响应偏刚。动作最小——MPI 质量分配记录加一行裁决即可。
- **MC-B**：冻结 Mqq*（含移动铰点质量）为权威。后果：柔性频率整体下移（上数），已发布 FLEXIBLE_APPENDIX_R2_MODES 对动力学失效，五工况扫掠须以新版本重发（本轮禁止重生成上游文件），e15 范围扩大。
- **MC-C**：暂不冻结，两者并册，禁止任何柔性动力学消费直至硬件实测。后果：r2_full_flexible_coupling 维持 NOT_EVALUATED，仅刚性翼车道可走——与现状兼容但不推进闭合。

本盘点不选择（`this_inventory_selects=null`）。倾向性说明：MC-A 与已发布且经 e21 复现的证据相容、扰动最小；MC-B 物理更全但强制重发。裁决权属 MPI/动力学权威。

## 4. e15 重认证（REPEAT_ANCF_CERTIFICATION）触发条件清单

现状：e15 gate_summary.json `overall=REPEAT_ANCF_CERTIFICATION`；交叉求解最大相对差 0.05637349419858036 > 0.05 门槛；`final_candidate_cross_solver.available=false`（冻结 E1.5 为 SAFE=0 且无名义 Top-3，禁止用低振幅诊断锚点冒充最终候选）。证据位置：e15 gate/config 路径与 `30_simulation/sim_07_ancf_flexible/`（ancf_beam.py、benchmark_results_v1.md；标题证据：点捕获激振 vs 刚性锁定 ≈92×，振铃 37–75 s，见 AGENTS.md 第 23 行）。

新全耦合模型触发重认证的条件（T1–T7）：T1 任何消费 R2 柔性翼的新全耦合模型（刚性翼车道不免除但也不闭合任何柔性结论）；T2 动态质量分配冻结改变 Mqq→Mqq* 或 WP5 实测更新叶质量/EI；T3 阻尼模型引入（今 null）或 ζ 变更；T4 铰/latch 刚度带被实测值替换；T5 接触窗模型变更（scene A2 T_c 20 ms 占位 → 夹爪实测）；T6 积分器/容差偏离 Radau rtol=1e-10/atol=1e-12 + BDF 交叉约定；T7 自由漂浮基座耦合 + 参与因子（GAP-03 闭合）使认证对象从定基座梁变为耦合附件。

关闭条件（certification_v1.yaml）：历史分类分数 1.0、unclassified=0、silent_zero=0、低振幅 ANCF-模态相对差 ≤0.10、**冻结最终候选** Radau-vs-BDF 全比较相对差 ≤0.05、网格趋势与时间步趋势可观测。

## 5. 与 Route-C 的依赖/隔离边界

可立即并行文本准备：本盘点与缺口账（已完成）；WP5 硬件选型需求清单（叶/铰/latch/阻尼，文本）；ROM 输入 schema 起草（质量阵、刚度带、参与因子槽位以显式 null 字段占位）；e15 重认证测试规格起草（只起草不运行）；质量冲突选项纸（MC-A/B/C）供 MPI 裁决；不确定度记账约定（工程带角 vs standard_uncertainty=null）文档化。

必须等 MPI Gate：任何 Route-C 独立版本化 CAD 候选（ODR-44 明禁）；T_PHYSICAL_TO_DYNAMIC 对柔性/质量/界面输入的任何消费（桥不存在）；动态质量分配冻结在耦合动力学运行中的应用；叶/铰/latch 的任何 FEA（本轮全面禁止 CAD/FEA 进程）；新全耦合模型的 e15 重认证**运行**；A2 类捕获-经-R2-柔性评估（e21 范围明禁，仍 HOLD_NOT_EVALUATED）。

## 6. Blocker 与基线符合性

- BLOCKER-1：阻尼/参与因子/强迫响应/标准不确定度全 null——全柔性闭合没有任何耗散与耦合输入。
- BLOCKER-2：移动铰质量冲突未冻结（`dynamic_mass_allocation_frozen=false`），所有柔性频率带最高 −13.40%（nominal 第三阶）的二值歧义。
- BLOCKER-3：`r2_harness_R2_HRN_04=FAIL_REDESIGN_REQUIRED`（e21 强制 hold）——harness 0.05 kg/翼在翼质量闭合内，重设计可能再次扰动质量阵。
- BLOCKER-4：24 kg 预算重分配 OPEN（R2 +0.8632134 kg）。
- 符合性：未发现与接管基线不符之处。B601 0.36889° 双框架差值经 E21_AUTHORITY_CONTRACT_V1.yaml 确认为 frame-consumption 歧义而非不确定度（`averaging_forbidden=true`、`branch_delta_is_uncertainty=false`）；旧 R1 帆板卡（0.3483933 kg、0.7/1.0/1.3 Hz 包络）仅限历史 sim_11 复现，新 R2 耦合运行必须引用 FLEXIBLE_APPENDAGE_R2 带（AGENTS.md 待办 3：0.348 kg 占位 vs 真实 2–5 kg/m² 是论文最大硬伤，优先级最高）。

## 7. 建议下一轮动作

- R1：MPI/动力学权威发出唯一显式动态质量分配裁决（MC-A/B/C），置 `dynamic_mass_allocation_frozen=true`。
- R2：开 WP5 R2 硬件选型工单，覆盖 GAP-01/02/05/06/07/08。
- R3：R1 冻结后扩展 ROM 越过定基座——参与因子/模态动量系数（本轮先写文本规格）。
- R4：按 T1–T7 起草 e15 重认证测试规格（仅文本）。
- R5：Route-C CAD 保持冻结至 MPI-01..08 全闭合（ODR-44）；本盘点已把桥接需携带的全部柔性输入就位。
