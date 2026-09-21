# RED_TEAM_ATTACK_PLAN_V1 — MPI 物理↔动力学桥接轮（round0_handover）红队攻击计划

- schema: `RED_TEAM_ATTACK_PLAN_V1`
- role: `AGENT-4_READ_ONLY_RED_TEAM`（只读；不写任何工程结论；不修改/重生成任何 accepted 资产、上游 ledger 或 Gate JSON）
- authority_basis: ODR-43（`B601_ARM_PLACEMENT_RULE=DUAL_FRAME_EXPLICIT_BRIDGE`）与 ODR-44（`ODR-42=APPROVE_BOUNDED_DETAILED_DESIGN`）Owner 批准文本（主控逐字转述）；本计划自身不构成 authority，只定义攻击与证伪方法
- scope: 本轮 + 后续全程，覆盖 `mpi_phys_dyn_bridge/round0_handover/` 全部产出物及其引用的上游证据
- tool_policy: 纯 Python（hashlib / numpy 级数值）+ 文件读取；禁止启动 FreeCAD/SolidWorks/Abaqus 等任何 CAD/FEA 进程；git 只读
- decision_rule（沿用项目既有规则）: `Authority > Evidence > Independent reproduction > Agent opinion; voting FORBIDDEN`
- verdict_vocabulary: 攻击面结论用 `SAFE` / `FINDING`（沿袭 M7_RED_TEAM_REPORT_V1）；证伪结论用 `SURVIVED` / `FALSIFIED` / `NOT_INDEPENDENTLY_REPRODUCIBLE`（沿袭 M7_FALSIFIER_REPORT_V1 三值制；凡是本轮纪律禁止复算的路径（CAD kernel、Abaqus ODB 内核重读）一律判 `NOT_INDEPENDENTLY_REPRODUCIBLE`，不得升级为 `SURVIVED`）

---

## 0. 本轮已实测复核的 hash pin（攻击可行性的实弹验证）

2026-08-23 由 AGENT-4 用 `hashlib.sha256` 全量重算，6/6 MATCH，证明"hash 绑定→现场复算"链路当前完好、且本计划的复算方法可直接执行：

| 文件（相对 ROOT） | pinned sha256（全 64 hex 中的前 16） | 实测 |
|---|---|---|
| `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf` | `1BC2B7483CD8025D…` | MATCH, 11321 B |
| `20_engineering/.../ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step` | `21FF77B882DBFAB8…` | MATCH, 131834 B |
| `30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_DIAGNOSTIC_GATE_V1.json` | `B03B7C7AF571AA00…` | MATCH, 22675 B |
| `20_engineering/.../ecr_solar_array_r2/HARNESS_B601_FULL_FK_SWEEP_V2.json` | `DB86348B8276FB2D…` | MATCH, 20197 B |
| `20_engineering/.../03_gate/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1.json` | `B43745081B4D0F22…` | MATCH, 17306 B |
| `20_engineering/.../03_gate/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_VALIDATION_V1.json` | `84D89F631F7904DA…` | MATCH, 32996 B |

pin 出处：`.../ecr_b601_harness_rated_envelope/08_route_c/02_pre_cad_parametric_guided_route_search/03_gate/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1.json` 的 `source_bindings` 与 `.../15_loop_continuation_v5/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json` 的 `input_bindings`。

## 1. 基线数字复核（本计划一切引用数字的可复核锚点）

1. 两个 frame 的显式定义：`30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml` `placement_hypotheses`（行 17–32）。`ODR01_DYNAMICS_T_SM` 平移 0.18525 m；`WP11_PHYSICAL_GEOMETRY_CONTEXT` 平移 0.208 m、Rz(25°)。两者 `selected: false`、`averaging_forbidden: true`。
2. 桥接不变量（AGENT-4 由 contract 条目独立重算，非引用任何结论）：
   - `det(R_ODR01)=1.0`（精确）；`det(R_WP11)=1.0000000000005196`；`max|RᵀR−I|=5.196e-13`（contract 12 位截断的 sin/cos(25°) 所致浮点噪声量级）。
   - `T_ODR01⁻¹·T_WP11 = [[0.9063076838,−0.4226184832,0,0],[0.4226184832,0.9063076838,0,0],[0,0,1,0.02275],[0,0,0,1]]`，转角 +25.000013999932°（与精确 25° 差 1.4e-5°，源于 contract 截断），平移 `[0,0,+0.02275]` m；两原点差 `|0.208−0.18525|=0.02275` m 精确。
   - 注意陷阱：用全精度 `sin/cos(25°)` 重建的桥与"由 contract 截断条目推出的桥"在矩阵元上差 ~1e-7。authority matrix 必须声明自己用哪一种，并把另一种作为对照 witness 公布；静默二选一即 FINDING。
3. e21 双分支灵敏度（`results/E21_TWO_PLACEMENT_RIGID_DYNAMICS_SENSITIVITY_V1.json` 与 gate E21-G05/G10/G11/G15）：ODR01 通道峰值基座姿态偏差 29.041965867604112°，WP11 物理通道 29.41085537835705°，差 0.3688895107529362°；`standard_uncertainty: null`；系统质量两通道同为 31.022864807342987 kg（`mass_error_kg: 0.0`）；CG 差范数 0.003524348142565558 m；惯量最大差 0.10311953522836159 kg·m²。
4. M3R 刚性栈四站语义：`wp4_fastener_design/M3R_FASTENER_DESIGN_V1.yaml` 行 20–23（M_frame 185.25 / adapter_plate_face 198.0 / physical_mounting_face 208.0 / as_built_screw_end_plane 210.405 mm）；`wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml` 行 38–39（185.25 = 唯一动力学安装参考；198.0/208.0/210.405 = 几何特征栈）。
5. V5 gate（`.../15_loop_continuation_v5/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json`）：`gate: HOLD`、`next_stage_authorized: false`、`released_segments: 0`；11 条 `fail_closed_invariants`；`m7_r2_arm_placement_consumption.single_consumption_rule_resolved: false`；Route-C 物理 frontier 五量全 null；MPI 0/8。
6. e21 mandatory_holds / nonclaims：`results/E21_DIAGNOSTIC_GATE_V1.json` 行 750–770（11 项 hold + 6 条 nonclaim，含"两分支是灵敏度而非统计不确定度"）。
7. Route-B 硬性负结果：`ecr_solar_array_r2/HARNESS_B601_FULL_FK_SWEEP_V1.json`（56 态 FAIL：clearance −11.8667 mm、bend 1.081 mm、pinch −11.3573 mm）与 `..._V2.json`（308 态 FAIL：clearance −11.9938 mm @SWEEP_joint2_09 vs link3、bend 0.1 mm、pinch −11.9902 mm @HARDSTOP_joint4_hi/joint5）；Route-C gate 以 `route_b_v2_hard_negative_results_verbatim` 逐字携带。
8. Route-C precad gate：`gate: UNKNOWN_FAIL_CLOSED`；predicate 47/47（11 正控 + 36 负控）但 `PASS_SYNTHETIC_SEMANTICS_ONLY`、`grants_design_authority: false`；`physical_capacity_frontier` 五量全 null；`external_trust_anchor: false`；15 项 retained_holds。
9. MPI gate：`ROUTE_C_MPI_EVIDENCE_GATE_V1.json`：0/8 controlled；MPI-07 = `HOLD_PARTIAL_LOCAL_KINEMATICS_ONLY`；`route_b_values_not_inherited`（OD 10.0 mm / R25 / R30 / cut 4001.158 mm 均 `inherited: false`）。
10. 既有红队/证伪资产（本计划不重复其工作量，只在其未覆盖处加攻击）：M7 RT-01..08（5 SAFE + 3 FINDING；totals HIGH=0 / MEDIUM=221 / LOW=90）；F1..F6 全 SURVIVED；B601 scoped RT-H01..H11 全 closed（`PASS_FAIL_CLOSED_NEGATIVE_DECISION`）；terminal validation A00..A10 11/11（`INDEPENDENT_VALIDATION_PASS`，确认 `ROUTE_B_REJECTED__ROUTE_C_TRIGGERED`）；e21 NC01..NC08 深拷贝变异负控全 firing。
11. 遗留模型黑名单数值（仅允许以"历史复现专用"显式引用块出现）：`20_engineering/config/geometry/service_spacecraft_v1.yaml`（whole_sat 24.0 kg、rigid_bus_no_panels 23.3032134 kg，仅供 sim_01..06/08 刚体仿真）；`20_engineering/config/geometry/flexible_appendage_v1.yaml`（m_panel 0.3483933 kg、mu 1.7419665 kg/m、f1 名义 1.0 Hz/包络 0.7–1.3 Hz、EI 4.3630e-3/8.9042e-3/1.5047e-2 N·m²、zeta 0.01 TBD）。当前 R2 柔性卡：`ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml`（class=`PROVISIONAL_DERIVED`，3-DOF/翼，模态名义 [6.9726, 39.3586, 98.0042] Hz）+ `FLEXIBLE_APPENDAGE_R2_MODES.json`。

---

## 2. 十四个攻击面与 Falsifier 协议

每条统一格式：**伪造模式 → 具体检查（文件/字段/复算方法）→ Falsifier 协议（独立复算路径 / 接受门槛 / SURVIVED 判定）**。所有检查均可用纯 Python 在本机执行；凡需 CAD/FEA 内核的步骤只做到"哈希与已存样本复算"层，并判 `NOT_INDEPENDENTLY_REPRODUCIBLE`。

### ATK-01 empty file + PASS
- 伪造模式：0 字节 JSON/CSV、header-only CSV、全 null JSON、空容器 `{}`/`[]`，被下游文档以 `status: PASS` 引用；或 receipt 自报 PASS 而其 produced 清单含空文件。
- 具体检查：对 `round0_handover/` 全部文件做 size>0 + 可解析 + 非空容器扫描（方法同 M7 CM 审计 C4 `ZERO_BYTE_AND_DEGENERATE_EVIDENCE_SWEEP` 与 Falsifier F5 的 838 文件扫描）；对四个产出物 pin 的每个证据文件重算 bytes 并与声明比对。
- Falsifier 协议：独立 walk（不复用产出物自带清单，直接列目录）→ 任何被引用证据为 0 字节/不可解析/空容器即 `FALSIFIED`；接受门槛 = 0 违规；全过判 `SURVIVED`。

### ATK-02 null + PASS
- 伪造模式：未知量以 null 记录却同条给出 `pass: true`；或把 null 静默 0 化后参与派生量（违反 e21 `uncertainty_policy.zero_fill_for_unknown: false` 与 V5 `unknown_uncertainties_zero_filled: false`）。
- 具体检查：递归扫描四个产出物，对每个 `pass|PASS|closed|controlled|verified == true` 的条目，定位其依赖的数值字段，断言非 null；反向扫描：每个 null 字段必须伴随显式 `UNKNOWN/HOLD` 语义（正例：Route-C gate `physical_capacity_frontier` 五 null + `state: UNKNOWN_NOT_COMPUTABLE`）。重点字段：桥的 16 个矩阵元、质量/CG/惯量、不确定度（e21 模板：`standard_uncertainty: null` 时结论必须是 hold 类而非通过类）。
- Falsifier 协议：写独立扫描器（json 递归 + 键名正则），与产出物自报计数比对；接受门槛 = 无 "null∧PASS" 共存、无 0 化痕迹（派生量复算与公布值在 1e-12 相对容差内一致）；通过判 `SURVIVED`。

### ATK-03 PROVISIONAL 冒充 authority
- 伪造模式：`FLEXIBLE_APPENDAGE_R2.yaml` 的 `PROVISIONAL_DERIVED` 被改写为 `AUTHORITY/MEASURED/FINAL`；阻尼 zeta 0.01 摘掉 `TBD_cite_literature` 状态直接消费；候选类量（如 grasp closing_force/speed，见 M7 RT-02）升级为设计权威。
- 具体检查：字段级 verbatim 比对——产出物中每个量的 `class/status/authority_level` 必须与源文件逐字一致（方法同 RT-02 的 ledger vs body 比对，46 条目模板）；grep 关键词提升痕迹（`MEASURED`、`AUTHORITATIVE`、`as_built` 出现在非授权上下文；CM 审计 C5 的 9 类 pattern 直接复用）。
- Falsifier 协议：以源文件 hash 锁定版本为基准重新抽取 class 字段，与产出物逐字段 diff；接受门槛 = 0 提升、0 摘状态；通过判 `SURVIVED`。

### ATK-04 frame mixing（同一量两个 frame 无桥混用）— 本轮核心
- 伪造模式：质量/CG/惯量/界面载荷/CAD 几何/碰撞几何中任一量，一部分取自 WP11 物理系、另一部分取自 ODR-01 动力学系，未声明经过 `T_PHYSICAL_TO_DYNAMIC`；或同一文件内同名量前后分属两系。
- 具体检查：四个产出物中每个物理量必须带显式 frame 标签 ∈ {`ODR01_DYNAMICS`, `WP11_PHYSICAL`, `BRIDGED_VIA_T_PHYSICAL_TO_DYNAMIC`}；任何跨系量必须引用桥的唯一标识与其 hash。正向对照（positive control）：用 contract 条目独立重建桥，把 e21 公布的两通道 CG（[0.09123549790183574, 4.376e-05, −0.006282656311277057] vs [0.0946788903322559, 0.0007727570136472924, −0.006101972690591536] m）做互映射，应复现 0.003524348142565558 m 的公布差范数量级关系；任何"直接用 ODR-01 平移 0.18525 装物理量"或反之的条目即命中。
- Falsifier 协议：独立重建桥（本计划 §1.2 数值即独立重建结果）→ 对产出物公布的所有 `BRIDGED` 量逐一施加桥/逆桥复算；接受门槛 = 映射结果与公布值差 ≤1e-9（双精度截断噪声带）；任一量无桥跨系即 `FALSIFIED`；全部一致判 `SURVIVED`。

### ATK-05 mass double-count（bridge 前后质量重复计入）
- 伪造模式：同一组件质量在物理系计一次、桥接后又计一次（臂 4.695555949342986 kg → 9.39 kg 级错误）；或把 R2 双翼 1.56 kg 与单片 leaf 0.18 kg×6 同时入总账。
- 具体检查：总量恒等式——桥前总和 = 桥后总和（e21 模板：两通道 `mass_error_kg: 0.0`，同为 31.022864807342987 kg）；组件级账本唯一性——每个 mass 条目有唯一 accounting id，桥只改变坐标表达不新增条目；检查 residual 26.327308858 kg（E21-G08）与系统 31.022864807342987 kg 的构成分解在产出物中不重不漏。
- Falsifier 协议：独立按产出物的组件表求和，与公布总量比对；接受门槛 = |Δm| ≤ 1e-12×scale（e21 已达 0.0）；任何分量出现两次或总量漂移即 `FALSIFIED`。

### ATK-06 silent average（两姿态/两频率/两分支取平均）
- 伪造模式：(29.041965867604112+29.41085537835705)/2 = 29.226410622980581° 被报告为"名义扰动"；两 frame 矩阵逐元平均（平均值 det≠1，立即非正交）；五刚度工况频率与 conflict 分支频率平均；Route-C 互斥拓扑（RC-A..D）结果被平均（违反 `branch_result_averaging_forbidden: true`、`topologies_mutually_exclusive: true`）。
- 具体检查：黑名单数值扫描——29.226410622980581、两 CG 的中点、两惯量的中点、任意分支对均值（容差 1e-9）；矩阵黑名单——任何声称是桥的矩阵若 det(R) 与 1 的差落在"平均矩阵特征区间"（如 Rz(0°) 与 Rz(25°) 平均的 det≈0.976）即命中；扫描 `average|mean|midpoint|blend` 关键词作用于分支量的上下文。
- Falsifier 协议：对产出物全部数值与黑名单比对 + 桥矩阵正交性复算；接受门槛 = 0 命中；通过判 `SURVIVED`。

### ATK-07 empty comparison set = PASS
- 伪造模式：两侧文件集/字段集之一为空时"全部一致" vacuously 成立； Route-B 负结果比对集为空时声称"无冲突"。
- 具体检查：每个比较断言必须公布两侧集合大小且 ≥1（正例模板：FK sweep `empty_comparison_sets: 0` 作为显式 gate 项；Route-C `comparison_sets_nonempty: true`）；独立重数—— receipt 的 produced/consumed 清单条目数、authority matrix 的字段比对数。
- Falsifier 协议：独立重建两侧集合并重数；接受门槛 = 公布计数 = 独立计数 且 ≥1；空集+PASS 即 `FALSIFIED`。

### ATK-08 旧 24 kg 质量模型静默复用到 R2
- 伪造模式：把 `servicer_12U_v0` 24.0 kg / 23.3032134 kg 总线、0.3483933 kg 旧板质量当作当前 R2 质量入桥或入库存；当前权威值应为 fixed residual 26.327308858 kg、C07 系统 31.022864807342987 kg、R2 双翼 1.56 kg（E21-G09：`legacy_r1_panel_card_or_mass_or_ffr_consumed: false`）。
- 具体检查：黑名单数值 [24.0, 23.3032134, 0.3483933, 1.7419665] 在四个产出物中扫描；命中只允许处于显式 "legacy / historical reproduction only" 引用块且带 supersedes 说明（正例模板：FLEXIBLE_APPENDAGE_R2.yaml `supersedes: nothing - legacy … stays untouched for historical sim_11 reproduction only`）。
- Falsifier 协议：扫描 + 上下文分类复核；接受门槛 = 0 处静默命中；通过判 `SURVIVED`。

### ATK-09 旧 Solar R1 柔性模型复用到 R2
- 伪造模式：R1 单自由度悬臂模型（f1 名义 1.0 Hz、0.7–1.3 Hz 包络、EI 4.3630e-3/8.9042e-3/1.5047e-2、mu 1.7419665、span 0.2/chord 0.227/t 0.006）冒充 R2 三叶铰链链模型（模态名义 [6.9726, 39.3586, 98.0042] Hz，root kθ 200/inter kθ 100 N·m/rad 名义）；e21 `forbidden` 已明令禁止 legacy R1 panel card/mass/FFR 进入当前 R2 动力学通道；AGENTS.md 待办 3 标记 0.348 kg 占位为论文级硬伤风险。
- 具体检查：R2 flex inventory 的五工况频率表必须与 E21-G20 / FLEXIBLE_APPENDAGE_R2_MODES.json 逐数字一致（含 `conflict_minus_leaf_only_hz` 的负值不得取绝对值）；黑名单扫描 R1 专属数值；`FLEXIBLE_APPENDAGE_R2.yaml` pin（AGENT-3 库存记录 `a04acfe440c636bb…`）实测复核。
- Falsifier 协议：由 MODES.json 独立重算五工况频率表并与库存比对（容差 1e-6 Hz，因公布值为 4 位截断）；接受门槛 = 全等且无 R1 命中；通过判 `SURVIVED`。

### ATK-10 Route-B 全范围 FAIL 被改名/隐藏
- 伪造模式：`FAIL` 改写为 `PASS_WITH_PROVISIONAL_SCOPE`/`CLOSED`；`R2-HRN-04 FAIL_REDESIGN_REQUIRED` 被静默降级；source register 丢弃 V1/V2 sweep 文件；宣称"redesign 已闭合"但无新的全范围 sweep 证据。
- 具体检查：八字逐字比对——任何引用 Route-B 的产出物必须原样携带 clearance_worst −11.9938 mm @SWEEP_joint2_09 vs link3、bend 0.1 mm、pinch −11.9902 mm @HARDSTOP_joint4_hi、`source_verdict: FAIL`、`terminal_route_b_disposition: REJECTED`（正例模板：Route-C gate `route_b_v2_hard_negative_results_verbatim`）；V1/V2 文件 hash 复算（`10EA7420…`/`DB86348B…`）；terminal validation A01 的 `full_v2_verdict: FAIL` 与 A04 `route_b: REJECTED` 仍成立。
- Falsifier 协议：hash 复算 + 八字 verbatim diff；接受门槛 = 8/8 逐字一致且 hash 匹配；任何改名/缺失即 `FALSIFIED`。

### ATK-11 桥接矩阵非正交 / 手性翻转 — 本轮核心
- 伪造模式：(a) det(R)=−1 的反射（手性翻转）；(b) Rz(−25°) 冒充 Rz(+25°)（静默转置）；(c) 用全精度 25° 三角值静默替换 contract 截断值（矩阵元差 ~1e-7）；(d) 平移符号方向未声明（+0.02275 还是 −0.02275，取决于约定方向）；(e) 把 198.0−185.25=12.75 mm 或 210.405−208.0=2.405 mm 等栈内站距当作桥平移。
- 具体检查：authority matrix 公布的 16 元与本计划 §1.2 独立重建值逐元比对；不变量门槛：`|det(R)−1| ≤ 1e-9`、`max|RᵀR−I| ≤ 1e-9`、转角逐元落在 25.0000139999°±1e-5° 对应矩阵元带内、`T·T⁻¹=I` 误差 ≤1e-12；手性判别——对测试矢量（如物理系臂基 x 轴）施桥，+25° 与 −25° 两候选相差 50°，无任何容差可吸收；方向约定必须成文并同时公布逆矩阵。
- Falsifier 协议：独立重建（numpy 级）+ 双候选判别测试 + 截断 witness（公布"contract 截断版"与"全精度版"差 ~1e-7 的对照）；接受门槛 = 上述全部满足且方向约定成文；任一失败即 `FALSIFIED`。

### ATK-12 平行轴定理漏项（Steiner 项缺失）
- 伪造模式：惯量跨参考点/跨系搬移只做 `R·I·Rᵀ` 旋转变换，漏掉 `m·(|d|²I − ddᵀ)`；判别 witness 量级：m_arm·d² = 4.695555949342986 × 0.02275² ≈ 2.4304e-3 kg·m²，比浮点噪声高 10 个数量级，绝无容差可吸收。
- 具体检查：authority matrix / 库存中每个"about system CG"或跨系惯量，独立重算含 Steiner 项的全变换并比对；e21 模板：G10 ODR01 通道惯量闭合误差 4.44e-16（机器精度）；同时要求公布值复现 e21 通道间惯量差 0.10311953522836159 kg·m² 这一 frame 消费效应——正确的桥复算必须复现通道差而不是把它抹成 0。
- Falsifier 协议：独立 Steiner 复算（纯 numpy）→ 与公布值逐项比对；接受门槛 = 相对差 ≤1e-9 且通道差 witness 复现；漏项（误差 ~2.4e-3 量级）即 `FALSIFIED`。

### ATK-13 quaternion 规范化掩盖漂移
- 伪造模式：只公布归一化后四元数范数误差（恒为机器 ε），不公布归一化前漂移；或对已漂移四元数做归一化后声称"姿态精确"；或把桥写成四元数时用符号/轴翻转版本再归一化蒙混。
- 具体检查：任何消费桥的动力学产物必须双报 pre/post-normalization 范数误差（e21 模板：G17 公布 after=2.22e-16、before=2.67e-13/2.18e-13）；接受带：pre-normalization ≤1e-9（Radau rtol=1e-10 级别下 e21 实测 ~2.7e-13）；桥的四元数表达必须与本计划 §1.2 矩阵互转一致（q 与 −q 等价可接受；轴翻转不可接受）。
- Falsifier 协议：独立从轨迹/矩阵重建四元数序列，重算 pre/post 误差；接受门槛 = 双报齐全且在带内；只报 post 或 pre 超带即 `FALSIFIED`。

### ATK-14 hash 绑定后文件被换
- 伪造模式：pin 记录后替换被 pin 文件；截断 16-hex pin 碰撞替换；pin 清单文件自身未被 pin（自指漏洞）；生成器脚本被换而产物不变。
- 具体检查：对四个产出物的全部 pin 做全 64-hex sha256 + bytes 复算（本轮 §0 已对 6 个关键 pin 实测 MATCH）；pin 清单自指闭合（模板：terminal validation A00 `pin_file_expected == pin_file_actual` + 36 项独立检查 + 负控 mismatch→ABORT）；生成器脚本入 pin（模板：A02 的 4 个 generator source 全匹配）；新产出物禁止只 pin 16-hex 截断值。
- Falsifier 协议：深拷贝变异负控（复制任一被 pin 文件到 scratch，改 1 字节，检测器必须 firing——e21 NC01 / Route-C 48/48 deep-copy 控制模板）；接受门槛 = 100% MATCH 且负控 firing；任一 mismatch 或负控静默即 `FALSIFIED`。

---

## 3. 本轮四个产出物的逐项攻击清单（下一轮可立即执行）

路径约定（round0_handover 下；兄弟代理已在写 `03_r2_flex_inputs/`，其余以实际落盘为准，红队按落盘实测，不按预期放行）。

### 3.1 receipt（回执）
1. ATK-01：文件非空、JSON 可解析、produced/consumed 清单每条 size>0。
2. ATK-14：清单每条 `{path, sha256, bytes}` 全量复算（方法同 CM 审计 C2 receipt 自洽）；receipt 自身 hash 不入自身清单（防自指伪造）。
3. ATK-02：无 null→0；`next_stage_authorized` 必须为 `false`；任何 PASS 字样必须挂证据指针。
4. ATK-07：自报文件计数 = 独立 `ls` 计数。
5. 纪律：`tools_started` 必须为 none/纯 Python（CM 审计 method 模板）；出现 CAD/FEA 进程痕迹即 FINDING。
6. 声明覆盖：ODR-43/44 授权要点逐字在 `authority_context` 中，且不新增任何 release 语义（正例模板：AGENT-3 库存的 `authority_context` 四字段写法）。

### 3.2 authority matrix（T_PHYSICAL_TO_DYNAMIC 桥）
1. ATK-11：16 矩阵元 vs 独立重建；det/正交/手性/方向约定/逆矩阵公布；截断 witness 双版对照。
2. ATK-04：每个量带 frame 标签；跨系量全部且仅经桥；正向对照复现 e21 CG 差 0.003524348142565558 m 量级关系。
3. ATK-05：桥前后总质量恒等（≤1e-12×scale；模板 0.0）。
4. ATK-12：每个跨点惯量含 Steiner 项；复现通道惯量差 0.10311953522836159 kg·m² witness。
5. ATK-06：无分支均值（黑名单 29.226410622980581° 等）；`branches_selected=false`、`branches_averaged=false`、`branch_delta_is_uncertainty=false` 三标志必须原样保留。
6. ATK-03：所有量 class 逐字（`PROVISIONAL_DERIVED` 不升级）。
7. ATK-14：两个 frame 定义 pin 到 `E21_AUTHORITY_CONTRACT_V1.yaml`（AGENT-3 库存记录 `7d2e0792b3ff6bab…`，红队全量复算）。
8. HOLD 保持：桥的建立不得把 V5 `single_arm_placement_consumption_rule: UNRESOLVED` 改写为 resolved-by-selection——ODR-43 的语义是"双系显式桥接"，不是"二选一"；出现选择语义即 FINDING。
9. M3R 栈语义：185.25/198.0/208.0/210.405 四站不得混用（锚点见 §1.4）。

### 3.3 Route-C inventory（MPI-01..08 桥接工作包库存）
1. 状态 verbatim：MPI-01..06/08 = `HOLD_NOT_CONTROLLED`、MPI-07 = `HOLD_PARTIAL_LOCAL_KINEMATICS_ONLY`、0/8 controlled（锚点：`ROUTE_C_MPI_EVIDENCE_GATE_V1.json`）；任何 "controlled/closed" 字样即 FINDING。
2. ATK-10：Route-B 负结果八字逐字携带；`route_b_values_not_inherited` 四值（OD 10.0/R25/R30/cut 4001.158）`inherited=false` 保持。
3. ATK-02：physical frontier 五 null 保持 null + `UNKNOWN_NOT_COMPUTABLE`；禁止扫描轴值冒充实测（`bundle_OD_is_scan_axis_not_known_value: true`）。
4. predicate 47/47 只能引为 `PASS_SYNTHETIC_SEMANTICS_ONLY` 且 `grants_design_authority=false`（ATK-03 变体）。
5. ODR-44 边界：`APPROVE_BOUNDED_DETAILED_DESIGN` ≠ Route-C CAD 授权；库存必须保留 "MPI-01..08 全闭合前禁止建 Route-C independent versioned CAD candidate" 语句；`cad_entry_authorized=false` 类字段不得翻转。
6. 八条 `forbidden_shortcuts`（Route-C gate 行 61–70）逐条对照库存文本，无违反。
7. ATK-07：MPI 条目计数 = 8，owner template 映射（MPI-01/02→电气数据 ICD；03/04→wire list；05/06→installed construction；07→installation ICD；08→mission life）与 gate 逐字一致。

### 3.4 R2 flex inventory（`03_r2_flex_inputs/R2_FLEX_INPUT_INVENTORY_V1.json/.md`，已存在，AGENT-3 产出）
1. ATK-14：16 个 source pin 全量复算（抽查已确认 E21 gate `b03b7c7af571aa00…` 与 V5 pin 一致；下一轮全量）。
2. ATK-09：五工况频率表 vs MODES.json/E21-G20 逐数字一致（含 conflict 负差不取绝对值）；R1 黑名单 0 命中。
3. ATK-03：`parameter_status_table` 14 行每行 status/uncertainty/source 非空且 class 逐字（leaf_mass 0.18 kg = PROVISIONAL 点值）；zeta 0.01 带 `TBD_cite_literature`。
4. ATK-05：质量闭合——wing 0.78 kg（3×0.18 + root 0.05 + 2×0.03 + HDRM 0.08 + harness 0.05）与 ledger 双翼 1.56 kg（E21-G09）一致；无重复计入。
5. e21-G21 语义保持：2×0.03 kg moving inter-hinge 点质量冲突 = "recorded, not selected, not propagated"（`selected/propagated_to_free_floating_dynamics/dynamic_mass_allocation_frozen` 全 false）；库存不得把它冻结为动力学分配。
6. ATK-02：damping/participation/forced_response 三 null 保持（E21-G22 模板）；不得零化。
7. e15 状态保持：`REPEAT_ANCF_CERTIFICATION` 逐字携带，不得写成 closed。

---

## 4. 红队自身纪律与判定规则

1. 只读：除本文件外不写任何文件；不修改 accepted URDF/Solar R2/上游 ledger/Gate JSON；git 只读。
2. 禁止多数投票；禁止 file-exists→PASS；禁止 null→0；禁止把 PROVISIONAL 当 authority；禁止两 frame 取平均；禁止静默复用旧 24 kg 质量模型或旧 Solar R1 柔性模型。
3. 每条攻击必须给出：独立复算路径（不消费产出物自报中间量）、接受门槛（数值容差或 verbatim）、三值判定（`SURVIVED`/`FALSIFIED`/`NOT_INDEPENDENTLY_REPRODUCIBLE`）。
4. 严重度纪律（沿用 M7）：HIGH = 会使 PASS/release 失效；MEDIUM = Owner 签署前必须修复但不推翻工程；LOW = 卫生项。本轮语境下 ATK-04/05/06/08/09/10/11/12 命中即 HIGH 候选。
5. 任何 HIGH 发现 → 立即上报主控并冻结对应产出物的下游消费（模板：release gate `terminal_release_condition` 的"red-team sweep 在其后运行，任何 HIGH 翻转该项并触发 gate 重发"机制）。

## 5. 下一轮最小可执行命令集（骨架，纯 Python）

```python
import hashlib, json, os, math
ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
# (1) pin 复算：对产出物 source_files_sha256 每条全量 sha256 + bytes
# (2) 桥重建：由 E21_AUTHORITY_CONTRACT_V1.yaml 两个 transform_S_A0_rows 重建
#     B = inv(T_odr) @ T_wp；断言 |det(R)-1|<=1e-9、max|R.T@R-I|<=1e-9、
#     B[:3,3] == [0,0,0.02275]（±1e-12）、转角 25.0000139999°±1e-5°
# (3) 黑名单扫描：[24.0, 23.3032134, 0.3483933, 1.7419665, 29.226410622980581,
#     4.3630e-3, 8.9042e-3, 1.5047e-2] 在四个产出物中 grep 级扫描 + 上下文分类
# (4) null∧PASS 共存扫描：递归 json，(pass|PASS|closed|controlled)==True 且依赖量为 null → 命中
# (5) Steiner witness：I_moved = R I Rᵀ + m*(|d|²I - d dᵀ)，d=[0,0,0.02275]，
#     m=4.695555949342986 → 漏项判别阈值 1e-3 kg·m²（witness 量级 2.43e-3）
# (6) Route-B 八字 verbatim diff + V1/V2 hash 复算
# (7) 深拷贝变异负控：scratch 复制任一 pin 文件改 1 字节 → 检测器 firing
```

—— 计划完 ——
