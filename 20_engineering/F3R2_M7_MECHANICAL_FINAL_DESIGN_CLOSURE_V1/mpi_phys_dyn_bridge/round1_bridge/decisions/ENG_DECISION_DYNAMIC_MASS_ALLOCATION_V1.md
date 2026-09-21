# 工程权威裁决：R2 动态质量分配（采纳 MC-A）V1

- schema: `ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1`（人读版；结构化字段以同目录 `.yaml` 为准）
- ruling_id: `ENG-RULING-DYN-MASS-ALLOC-MC-A-V1`
- 生成时间：2026-08-23T18:25+08:00（宿主机本地钟）
- 裁决级别：**工程权威裁决（Frame/Mass/Dynamics authority）——非 Owner 级，可经 ECR 或 Owner 显式裁决逆转/修改/升格**
- 状态：ISSUED_AND_EFFECTIVE_AT_ENGINEERING_LEVEL / PENDING_OWNER_REVIEW / `next_stage_authorized=false` / `release_credit=false`

## 1. 裁决事项与裁决结果

事项（OI-R1-06 / GAP-09，E21-G21 登记）：每翼 2 个 0.03 kg 移动板间铰点质量在质量脚本中存在、leaf-only ROM 动能中缺失，`Mqq* − Mqq = [[0.006, 0.0024, 0], [0.0024, 0.0012, 0], [0, 0, 0]] kg·m²`（e21 逐字），冲突状态 `CONFLICT_NONSELECTING_NONPROPAGATED`。

**裁决：采纳 MC-A，单一、显式、书面：**

1. R2 太阳翼 ROM/自由漂浮动力学的**唯一权威质量阵 = 已发布 leaf-only Mqq**（`FLEXIBLE_APPENDAGE_R2.yaml wing_L2_reduced_model.mass_matrix_kgm2`；e21 独立复现 4.999999997368221e-10 kg·m²，E21-G19 PASS）。
2. 每翼 2×0.03 kg 移动铰点质量作**刚性、非随动界面质量**集中记账在铰线处：计入结构质量账本与系统质量闭合（`SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json mass_model.hinge_inter_kg_each=0.03`，0.78 kg/翼闭合已含此 0.06 kg），**不进入 ROM 动能**。
3. **`dynamic_mass_allocation_frozen=true` 自本裁决生效**（2026-08-23T18:25+08:00）。冻结面 = 下游全柔性工作包（ROM 扩展、参与因子计算、HF 模型、新全耦合模型、e15 重认证输入包）的质量阵唯一性。**不回溯改写 e21 既有 gate**：E21-G21 的三 false（`selected/propagated/frozen=false`）是 e21 时刻历史状态记录，逐字保持有效；本冻结是 MPI/工程级新增记录。
4. 否决 MC-B（强制失效已发布 MODES.json、证据链断档重发，2026-09-01 硬截止前不可接受）与 MC-C（不推进闭合）；两选项记录原样保留于备忘录，未删除。

## 2. 对 nominal 频率口径的影响（登记，不修正）

- **公布频率 = leaf-only 口径，原样继续权威**：nominal 6.9726 / 39.3586 / 98.0042 Hz；五工况带角不变（e21 复现最大误差 4.840419126761475e-05 Hz，E21-G20 PASS）。无任何已发布证据失效。
- 铰质量频移作为**已知记账差异**携带入不确定度寄存器（条目 `BK-DYN-MASS-HINGE-ALLOC-MC-A`，类型 KNOWN_BOOKKEEPING_DIFFERENCE__NOT_STANDARD_UNCERTAINTY）：若改按 Mqq* 随动计入，nominal 三阶频移 **−3.5096% / −6.9411% / −13.4000%**（五工况全表见 YAML）。**不作平均、不作修正、不零填；`standard_uncertainty` 保持 null。**
- 方向性判读：leaf-only 口径柔性响应偏刚（nominal 相对冲突车道 +3.64% / +7.46% / +15.47%），即落在偏保守一侧；捕获激励主频带为第一阶（3.33–13.95 Hz），其记账差异 ≤4.25%。

## 3. rationale 摘要

- 与已发布且经 e21 独立复现（23/23 判据 PASS）的证据完全相容，扰动最小，无需重发任何上游 accepted 文件（ODR-44 与本轮纪律禁止重生成）。
- 物理近似（铰点刚化）的影响集中于第三阶翼内反相模态（全带角稳定 ≈−13% 记账差异），主频带第一阶仅 −2.58%..−4.25%。
- 立即解除 GAP-03（参与因子）计算前置阻塞，推进全柔性闭合；MC-B/MC-C 均不具备此性质。

## 4. scope

- 适用：R2 柔性质量分配冲突及其下游（ROM 扩展、参与因子、HF 模型、新耦合模型、e15 输入口径）。
- 不适用：24 kg 整星预算重分配（GAP-12，OPEN）；B601 双框架桥（已冻结，不动）；Route-C CAD；e21/V5/上游 gate 文件；**R2 全柔性闭合本身——`r2_full_flexible_coupling` 保持 NOT_EVALUATED**；帆板质量/刚度占位（AGENTS.md 待办 3，最高优先级保持开放）。

## 5. reversibility（逆转条件）

经 ECR 或 Owner 显式裁决逆转；任一命中即解冻并重登记：

- RC-1：WP5 实物称重表明铰点质量显著偏离 0.03 kg/个（ECR-M5 族）。
- RC-2：铰链实测表明随动惯性不可忽略（第三阶 ≈13% 记账差异不可接受）。
- RC-3：全柔性 HF 模型闭合（GAP-01..08 补齐）后重估表明 leaf-only 分配不再适用。
- RC-4：Owner/CM 显式否决、修改或升格。

## 6. downstream_effects（解锁清单）

- **e15**：E1 重认证输入口径钉死（质量阵=leaf-only Mqq，T2 不触发、范围不扩大）；E2 E15R-T1 前置"MC 裁决已落账"工程级满足；E3 `REPEAT_ANCF_CERTIFICATION` 逐字保持，本裁决不授权运行。
- **ROM**：E4 GAP-09 工程级闭合、SLOT-10 按 MC-A 解除；E5 **SLOT-07 参与因子计算前置解除**（Φ 取自 `eigh(K, Mqq)`；禁用 Mqq* 预计算；禁从 R1 卡继承；稀疏性负控制逐字适用）；E6 其余 SLOT 的 null/PROVISIONAL 状态不变。
- **sim_11**：E7 新 R2 耦合模型可引用已发布五工况频率带与 Mqq 为权威，R1 旧卡仅限历史复现（e21 forbidden 逐字有效）；E8 全柔性耦合保持 NOT_EVALUATED；E9 刚性翼车道不受影响。
- **质量账本**：E10 闭合不变——0.78 kg/翼、两翼 1.56 kg、整星 24.8632134 kg；GAP-12 保持 OPEN。

## 7. 证据与复核

- evidence_links 全 64-hex sha256 见 YAML（执行红队 RT1-F01 教训：不用截断拼写）；14 项证据含备忘录、盘点 JSON/MD、e21 ROM/gate/权威合同、R2 三件 accepted 资产、e15 gate、B601 桥、open items 与两份规格草案。
- 本代理独立复算：`scipy.linalg.eigh(K, M)` 双车道五工况，与备忘录 §1 逐数字一致（nominal −3.5096/−6.9411/−13.4000%）；备忘录 §7 全部哈希钉 64-hex 复算吻合；e21 gate 23/23 PASS、三 false 与 ΔM 逐字复核一致。
- 本轮未启动任何 CAD/FEA/仿真进程；未修改任何上游文件；复算输出仅写入本目录两个裁决文件。

## 8. 纪律声明（forbidden/nonclaims 摘要）

- 禁止把本裁决表述为 Owner 裁决；禁止借此闭合 R2 full-flex；禁止下游消费 Mqq* 或两阵平均/混用；禁止把记账差异记为标准不确定度或修正发布频率；禁止静默复用旧 24 kg/R1 柔性模型；禁止 null 零填。
- 本裁决不授予生产/制造/鉴定/发射/飞行权威；不改变任何已发布数字；不评价 GAP-12；不授权 e15 重认证运行或任何仿真/CAD/FEA 进程。
