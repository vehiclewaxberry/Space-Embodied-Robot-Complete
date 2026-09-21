# Master Plan — Partner Requirement Closure Phase — 2026-07-19

> 规划轮完成态。产出索引 + 红队修订清单 + 最终裁决。本轮未写任何科学代码、
> 未提交 git、未跑仿真。**实施前须人工批准本计划。**

## 最终裁决（2026-07-19 收口版，经 PI 十项强制修复指令更新）

**`READY_FOR_PARALLEL_WAVE1_WITH_FIXES`**

成立条件核验：R1 无 FATAL ✅（三处高严重度已折入 CTRL-01/02 卡）；
Safety Gate 升格为独立阻断主模块并列 Wave1 首位（SAFE-00 卡）✅；
C3 仅限任务零度>0（5D 口径）✅；sim_12 主张锁弱式（强式解锁条件=
SIM12-P1B GP2 出 PROVEN）✅；VLA 补 V2.5=FSM+同工具对照组（Wave2 前折入）✅。

### 十项强制修复落位表

| # | 修复 | 落位 |
|---|---|---|
| 1 | Safety Gate 独立阻断模块 | wave1_task_cards/SAFE-00.md（Wave1 首任务） |
| 2 | UNKNOWN 永不 ALLOW | SAFE-00 GS-A 机器断言 |
| 3 | L2 失败/域外行为显式定义（禁乐观回退，降级重查域） | SAFE-00 GS-A + ROM 规则修订项 |
| 4 | C3 仅 nullity>0 | CTRL-01（pose_6d 下机器拒绝） |
| 5 | V2.5 FSM 对照组 | vla_generalization_plan 修订（Wave2 前） |
| 6 | AprilTag 与无标记泛化声明分离 | VLA 计划红线 + perception_branch 入 scenario_hash |
| 7 | sim_12 Phase1 视为完成不重做 | state_truth ALREADY_COMPLETE 圈禁 |
| 8 | SIM12-P1b 靶向支配审计（条件触发） | wave1_task_cards/SIM12-P1B.md |
| 9 | ROM 验证含控制决策一致性 + unsafe FN=0 | GR 门修订 + CTRL×ROM 联合 Gate（Wave2） |
| 10 | H0 未过禁硬件控制 | 依赖 DAG 硬边 + Wave3 门禁 |

## 文件索引（本阶段全部产出）

| 文件 | 内容 | 作者 |
|---|---|---|
| state_truth_report.md | 磁盘真值 + ALREADY_COMPLETE 圈禁清单（Gate A0 PASS） | PI |
| claim_evidence_matrix.csv | 伙伴八需求 → 证据/缺口/最小任务/claim 边界 | PI |
| risk_register.csv / gate_registry.yaml / dependency_dag.md / file_ownership_matrix.csv | 风险/Gate/依赖/所有权 | PI |
| ../control/trajectory_control_research_plan.md | control_01：C0-C3×T1-T3，九 Gate | B |
| ../control/attitude_stabilization_research_plan.md | control_02：A0-A3/B0-B3，归属三标签机器判定 | C |
| ../rom/multifidelity_rom_plan.md + model_fidelity_selection_rules.yaml | L0/L1/L2 + 六规则 + 五认证门 | D |
| ../vla/vla_generalization_plan.md + tool_contract_draft.yaml | 五层分层 + V0-V3 + 七轴留出 + 五工具合约 | E |
| ../integration/sim12_status_and_next_gate.md + system_interface_plan.md | sim_12 验收 PASS + 直接工具化裁定 + 五层链 | F |
| red_team_control.md / red_team_vla.md | 红队报告（均无 FATAL，全 NEEDS_FIX） | R1/R2 |

## 红队修订清单（Wave1 fix-first，逐条折入对应计划书）

**control_01（R1 三处高严重度）**：①T2 锚点改捕获前 3.0°/s（1.3872 为捕获后
ω⁺，锚点声明为假）；②A1 反作用约束改用 (H_bb⁻¹H_bm) 角行（H_bm 参考点为
基座原点非质心）；③轮组容量按逐轴箱式包络重算占用（89.1% 非 29.7%，
"无饱和"预测待翻正）；另 C3 六个定义缺口、K_e 预注册、C0 ISS 论证替换。
**Physics Tool Contract（R2）**：①Safety Gate 本体规格必须先写（阻塞项）；
②插值与 EXACT_SOLVER 矛盾统一为查表+域外 UNKNOWN；③schema 加
additionalProperties:false + provenance 必填 + perception_branch 入
scenario_hash；④裁决时效校验（非仅启动时）。
**ROM 选择器（R2）**：五个绕过组合逐一封死——重点"升级到未认证 L2 行为
未定义"改为 fail-closed 返回 UNKNOWN；散文条件全部改可执行断言。
**VLA（R2，Wave2 前完成）**：补 V2.5=FSM+五工具对照组；prompt/model 哈希
入协议；泄漏三通道封堵。

## Wave1 三任务（PI 收口指令重组；≤3 写入 Agent，所有权互斥；Task Card 齐备）

1. **SAFE-00 Runtime Safety Gate**（wave1_task_cards/SAFE-00.md）——独立阻断
   主模块，R2 七绕过面全封；VLA 工具集成的先决条件。
2. **CTRL-01 末端轨迹基线 C0–C3**（wave1_task_cards/CTRL-01.md）——R1 三处
   高严重度先修（T2 锚 3.0°/s、A1 约束参考点、箱式容量 89.1%）；C3 仅 5D。
3. **CTRL-02 反冲抑制+捕获后消旋**（wave1_task_cards/CTRL-02.md）——GC0 动量
   归属账本 PI 批准制；目录改名避冲突。
（**SIM12-P1B** 为条件触发第四卡：论文需强式表述时启动，8–12 例靶向。）
Physics Tool Contract 与 ROM 选择器移至 Wave2（与 VLA V0/V1/V2.5 同波）。

## 三个当前不应执行

1. VLA 训练/数据采集（协议未固化、渲染管线未建、RK5 时间风险）；
2. sim_12 策略维 9000 点扫描（F 验收裁定降为 revision 弹药，触发条件已列）；
3. B601 任何控制或演示（H0 资格未过；仅允许 H0 清单准备）。

## 两周计划（7/19–8/02）

W1（Wave 0.5 收口 2–3 天）：R1/R2 修订折入两控制计划书 → Safety Gate 规格
冻结（SAFE-00 卡即规格骨架）→ PI 批准 → Wave1 三任务并行开工（独立 worktree）；
W2：SAFE-00 过 GS-A/B/C；CTRL-01 出 GC1 首轮裁决（C0/C1 先行）；CTRL-02 过
GC0 账本批准并完成 Phase A 骨架。ROM/VLA 保持只读规划完成 V2.5/绕过封堵修订。

## 六周比赛路线（→9/01）

7 月底 Wave1 收口 → 8/05–8/15 Wave2（control_02、VLA 基线 V0/V1、帆板转正
若到货）→ 8/10–8/18 Wave3 集成 + H0/H1（T_c 实测反哺）+ H2 → 8/15–8/25
比赛材料（Demo=数字孪生+gate 溯源决策，硬件为加分项）→ 8/25 冻结彩排。

## 论文分配

**Paper 1**（Constraint-Dependent Strategy Selection…）：sim_09 退化证据 +
sim_10 F1-F4 + sim_11 带宽方法节 + sim_12 账本与 16 例 + binding-gate 判据
（GS2 弱式表述，F 验收发现 F1）。**Paper 2**（多保真/控制候选）：ROM 三级
体系与认证 Gate + 接触带宽保真度研究 + control_01/02 若 C2/C3 出正结果。
Paper 3/Demo：VLA+工具合约架构（比赛后）。

## 伙伴需求满足度（详表见 claim_evidence_matrix.csv）

已满足：R4 刚柔耦合（参数受限 PASS）、R6 策略选择（16 例 PASS）、R5 组件层
（L0/L1/L2 均有裁决，选择器待建）。未满足：R2 末端控制（Wave1 主攻）、
R3 姿态稳定（Wave2）、R1 VLA 泛化（协议已立，证据最远）。R7 工具化（Wave1）、
R8 硬件（Wave3）。
