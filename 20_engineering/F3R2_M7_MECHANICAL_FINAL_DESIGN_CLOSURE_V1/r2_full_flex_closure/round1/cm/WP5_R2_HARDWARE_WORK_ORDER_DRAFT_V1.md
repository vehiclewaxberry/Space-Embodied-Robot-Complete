# WP5_R2_HARDWARE_WORK_ORDER_DRAFT_V1 — R2 硬件取证工作单（Owner 签发草案）

- schema 类标记：`WP5_R2_HARDWARE_WORK_ORDER_DRAFT_V1`
- 生成时间：2026-08-23T20:15:00+08:00（宿主机本地钟，Asia/Shanghai）
- 作者：KIMI M7 机械终局接管 swarm 第三轮（R2 全柔性闭合 Wave-3a）CM 子代理
- 性质：**CANDIDATE / PROVISIONAL 工单草案**。`release_credit=false`、`next_stage_authorized=false`。本文件不授权任何采购、实测、CAD/FEA/仿真进程；Owner 签署前不生效。
- 覆盖缺口：GAP-01/02/05/06/07/08（R2_FLEX_INPUT_INVENTORY_V1.json `hf_model_and_rom_input_gap_list`）、MC-A 逆转条件 RC-1/RC-2（ENG-RULING-DYN-MASS-ALLOC-MC-A-V1）、AGENTS.md 待办 2（B601 夹爪 T_c 实测）。
- 既有文本基础：`round1_bridge/r2_flex_prep/R2_ROM_PARTICIPATION_DAMPING_SPEC_DRAFT_V1.md` §5（6 项清单，本工单扩为 8 项并补证据形式/阻塞 gate/责任方）。
- 纪律：null 不零填；目录值不自动升级为项目选定件；实测值到位即触发相应 e15 T2/T4/T5 重认证口径；一切证据落盘须带 sha256 登记。

## 工单总表

| 工单号 | 事项 | 覆盖缺口/触发 | 当前值（可复核出处） |
|---|---|---|---|
| WO-W3-01 | 叶板 GJ（扭转刚度）带实测/供应商证据 | GAP-01 / SLOT-01 | null（`FLEXIBLE_APPENDAGE_R2.yaml` leaf_L1_engineering_model.per_leaf.GJ_Nm2：status=PROVISIONAL_DERIVED、"band not yet assigned"） |
| WO-W3-02 | 模态阻尼出处 | GAP-02 / SLOT-02 | ROM `damping_matrix=null`；卡片 ζ=0.01 `TBD_cite_literature`（占位，禁止消费） |
| WO-W3-03 | latch 独立刚度 | GAP-05 / SLOT-03 | null（折叠进板间 kθ 带 20/100/400 N·m/rad；`SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V1.yaml` HOLD_LATCH_GEOMETRY_NOT_MODELLED） |
| WO-W3-04 | 根部支架/星体界面柔顺 | GAP-06 / SLOT-04 | null（根铰弹簧 50/200/800 N·m/rad 为唯一根柔顺模型；机构账本仅有 48.0 N·m 根部支架反力瞬态候选） |
| WO-W3-05 | 铰链自由间隙（freeplay） | GAP-07 / SLOT-05 | null（HOLD_FREEPLAY_LIMITS_NO_NUMERIC_AUTHORITY） |
| WO-W3-06 | 叶板实测构造与称重 | GAP-08 / SLOT-06 | 候选构造 2×0.2 mm CFRP + 2.1 mm 芯、面密度候选 3.0 kg/m²（未实测）；叶 0.18 kg、EI 名义 11.109 带 [3.333, 33.327] N·m² 均 PROVISIONAL_DERIVED |
| WO-W3-07 | 2×0.03 kg/翼 铰质量核验 | MC-A RC-1/RC-2；ECR-M5 触发族 | `SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json` mass_model.hinge_inter_kg_each=0.03（0.78 kg/翼闭合已含 2×0.03） |
| WO-W3-08 | B601 夹爪闭合时间 T_c 实测 | AGENTS.md 待办 2；e15 T5 | `20_engineering/config/coupled_scene/scene_A2_capture.yaml` contact.T_c_ms_nominal=20.0（占位 PROVISIONAL；扫掠域 5–100 ms） |

---

## WO-W3-01 叶板 GJ 带

- **需要什么**：每翼叶板（夹层构造）扭转刚度 GJ 的点值+工程带角，或可供推导 GJ 的供应商铺层/芯材剪切数据。
- **证据形式**（任一，优先级递降）：① 试样扭转实测报告（试样尺寸/边界/加载/扭矩-转角曲线，带测量不确定度声明）；② 供应商受控版次铺层数据表（面材 E/厚度、芯材剪切模量）+ 夹层剪切模型推导记录；③ 若均不可得，保持 NULL 并在 HF 模型中禁用扭转模态结论。
- **阻塞哪个 gate**：HF 模型扭转模态与 ROM 模态集完整性（GAP-01）→ 直接阻塞 `r2_full_flexible_coupling`（现 NOT_EVALUATED）；实测值替换现行卡片即触发 e15 T2/T4 重认证口径。
- **建议责任方**：硬件组（试样/实测）+ 复材供应商（铺层数据）；推导复核由动力学侧按 SLOT-01 消费规则执行。

## WO-W3-02 模态阻尼出处

- **需要什么**：每阶模态阻尼比 ζ_i（或带角）的可核查出处——夹层板+铰链链结构的模态阻尼文献引用，或地面自由衰减实测。
- **证据形式**：① 文献条目（可核查出处，禁止无出处占位）；② 锤击/自由衰减实测的对数减量法处理记录（原始时序+处理脚本+工况声明）；③ 双车道制声明：守恒审计车道 ζ=0 与耗散预测车道 ζ≠0 必须分离（沿用 sim_11 能量审计 Gate 纪律）。
- **阻塞哪个 gate**：一切衰减/振铃类预测（GAP-02；sim_07 历史口径 37–75 s 振铃仅供参考不继承）→ 阻塞 SLOT-08 强迫响应与任何 R2 振铃量化；阻尼模型引入即触发 e15 T3。
- **建议责任方**：研究组（文献检索）+ 硬件组（地面衰减实测方案）。

## WO-W3-03 latch 独立刚度

- **需要什么**：latch 硬件选型 + 展开锁定态独立刚度/反驱特性数据（现状折叠在板间 kθ 带内）。
- **证据形式**：供应商受控数据表（刚度、反驱力矩/保持力）或台架实测报告；反驱校核载荷口径=480 N 控制端停瞬态 + 带角一阶模态振动（机构账本 C_latch 逐字）。
- **阻塞哪个 gate**：展开锁定态刚度权威与 latch 反驱校核（GAP-05）；到位前根/板间带（50/200/800、20/100/400 N·m/rad）保持唯一柔顺模型。
- **建议责任方**：机构组（WP5 mechanisms 线，HDRM/LATCH 硬件选型）。

## WO-W3-04 根部支架/星体界面柔顺

- **需要什么**：根部支架结构在星体界面处的柔顺（平动+转动）估算或实测。
- **证据形式**：支架结构设计文件 + 后续授权轮次的 FEA 报告或实测刚度记录；校核参考载荷=机构账本 48.0 N·m 根部支架反力瞬态候选（仅为载荷参考，不是刚度）。
- **阻塞哪个 gate**：HF 模型根边界真实性（GAP-06）→ 阻塞 `r2_full_flexible_coupling` 闭合。
- **建议责任方**：结构组（WP1 结构设计线 + wp7 FEA 线，须待相应轮次授权）。

## WO-W3-05 铰链自由间隙（freeplay）

- **需要什么**：根铰与板间铰的自由间隙（backlash）数值，带测量记录。
- **证据形式**：铰链间隙测量报告（测量方法/仪器/样本数/统计量）；到位后作分段线性/死区模型，数值须带测量记录；到位前 HF/ROM 均不得含 backlash 项。
- **阻塞哪个 gate**：非线性微动力学（backlash）建模（GAP-07）。
- **建议责任方**：机构组（WP5）+ 实测台架。

## WO-W3-06 叶板实测构造与称重

- **需要什么**：叶板真实铺层/胞元构造、真实面密度（对照候选 3.0 kg/m² 与文献 2–5 kg/m² 区间）、每叶实测质量（对照 0.18 kg 点值）。
- **证据形式**：试样构造记录（铺层顺序/芯材/厚度实测）+ 校准秤称重记录（秤具编号/校准有效期/重复测量）；悬臂频率实测可同步校核 EI 带。
- **阻塞哪个 gate**：PROVISIONAL 质量/EI 的替换口径（GAP-08）；AGENTS.md 待办 3 登记为"论文最大硬伤，优先级最高"——真实面密度口径下"A1 柔性反馈可忽略"结论可能翻转；替换即触发 e15 T2/T4。
- **建议责任方**：硬件组 + 帆板/复材供应商。

## WO-W3-07 2×0.03 kg/翼 铰质量核验（MC-A RC-1/RC-2）

- **需要什么**：每翼 2 个移动板间铰点质量的实物称重（对照记账值 0.03 kg/个），以及铰链随动惯性可忽略性的工程判断证据。
- **证据形式**：校准秤称重记录（逐件编号）；若实测显著偏离 0.03 kg/个 → 命中 MC-A 逆转条件 RC-1（对应 ECR-M5 as-built mass correlation 触发族）；若铰链实测表明随动惯性不可忽略（第三阶模态敏感、记账差异约 13% 量级不可接受）→ 命中 RC-2，解冻 dynamic_mass_allocation_frozen 并按新裁决重登记。
- **阻塞哪个 gate**：MC-A 裁决的 Owner 级确认（OI-R1-06 残余项）；0.78 kg/翼质量闭合的 as-built 相关性。
- **建议责任方**：机构组（WP5）称重；动力学侧备查逆转口径。

## WO-W3-08 B601 夹爪闭合时间 T_c 实测

- **需要什么**：B601 夹爪从触发到闭合到位的实测时间（替换 scene_A2_capture.yaml `contact.T_c_ms_nominal=20.0` 占位）。
- **证据形式**：驱动实测记录（指令-行程时序，含多次重复与统计量）；替换后按既有扫掠域 5–100 ms 重跑带宽口径 Gate；占位值替换 = e15 T5 触发。
- **阻塞哪个 gate**：AGENTS.md 待办 2（接触窗带宽口径 Gate 重跑的前置）；SLOT-08 强迫响应激励模型的 T_c 权威值。
- **建议责任方**：B601 硬件/电气组（夹爪驱动实测）。

---

## 签署区（Owner 签发后生效）

| 栏位 | 内容 |
|---|---|
| 签发结论 | ☐ 批准全部 8 项 / ☐ 部分批准（列明工单号）/ ☐ 驳回 |
| Owner 签名 / 日期 | ____________________ |
| 备注 | ____________________ |

签发后动作：各责任方按上表取证，证据落盘 40_evidence 或指定目录并带 sha256 登记；任一实测值到位即按对应 e15 T2/T4/T5 口径处理；本工单不授予任何 release credit。
