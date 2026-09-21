# 项目记忆（CLAUDE.md）

## 项目定位

**航天服务星具身智能机械臂机器人** / *Space Service Robot with Embodied Intelligence*

面向在轨服务的长期硬件研发项目：12U CubeSat 服务星 + B601 六自由度机械臂，在自由漂浮工况下捕获翻滚非合作目标（150kg 碎片 / 22kg 目标星）。研究线为“面向抓取后可稳定性的预见式具身抓取”。

公开仓库：`https://github.com/vehiclewaxberry/Space-Embodied-Robot-Complete`

## 当前运行目标（2026-08-31 owner 覆盖）

- 当前目标是形成可装配、可参数化、可验证，并可支撑后续论文复现的 12U 服务星与 B601 机械设计。
- 交付重点是**整星机械机构与电气设计的完备性**，以支撑后续航天动力学 / 机器人学在轨服务开发。

## 历史来源（不作为当前授权依据）

项目起源于中国研究生未来飞行器创新大赛（第十二届）。**比赛期限和比赛交付不再作为当前工程工作的进度约束或授权 Gate。**既有比赛记录、机器 Gate 与负结果只作为历史证据保留，不得据此升级工程结论。`01_project/competition/` 是沿用的历史目录名，其中不少内容仍是现行工程来源，不得按目录名推定其为比赛专用或可弃。

## 当前目录冻结（REORG04）
- 根目录业务资产只允许进入 `01_project/`、`10_research/`、`20_engineering/`、`30_simulation/`、`40_evidence/`、`50_literature/`、`70_tools/`、`80_third_party/` 八个域。
- 禁止重新建立根级 `sim/`、`config/`、`docs/`、`results/`、`src/`、`pdf/` 或“补充论文”等平行目录。
- 本轮仅改变命名空间和路径引用；不据此升级科学结论。Gate 数值、布尔值、字段结构与裁决文本必须保持迁移前语义一致。

## 真值入口（先读这些，勿凭旧总结推断）
- 项目目录导航：`PROJECT_MAP.md`（只负责路径与资产所有权，不替代科学 Gate）
- Agent 快速入口：`10_research/knowledge_base/README.md`（只做现有证据导航，不是新的状态、题录或 Gate SSOT）；空间具身智能研究总控：`.codex/agents/space-embodied-intelligence-research-agent.md`；对应薄知识入口：`10_research/knowledge_base/physics_agent/README.md`；数字身体构建方法：`10_research/space_embodied_robotics/comp_prot_03_a3_g0_digital_body_method/README.md`；12U 服务航天器机械设计入口：`10_research/knowledge_base/spacecraft_mechanical_design/README.md` 与 `.codex/agents/spacecraft-mechanical-design-agent.md`（A4-B2 任务书/知识库已建立，V2.0 CAD 尚未授权）
- 项目全貌：`01_project/competition/项目现状总览_20260720.md`（研究治理域索引 `10_research/README.md`；历史文档在 `01_project/competition/archive/`，禁作现行依据）
- 离线研究仪表板：`70_tools/research_dashboard/`（输出保持 `40_evidence/artifacts/visualization/project_visualization_v1_research.html`；摘要不覆盖原始 Gate）
- 几何/质量 SSOT：`20_engineering/config/geometry/`、`20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/`
- 科学结论以各目录机器裁决 JSON（`*_gate_check.json`）为准；测试 PASS ≠ 科学 Gate PASS。
- 比赛交付链裁决：`10_research/competition_convergence/competition_gate_check.json`（`COMPETITION_DEMO_READY` 17/17，2026-07-20 晚；媒体已渲染于 `40_evidence/artifacts/competition_convergence/`）；装配预检裁决：`30_simulation/asm_00_interface_preflight/results/asm_00_gate_check.json`（`ASM00_AG0_BLOCKED_BY_INTERFACE`；九判据成功评估器合同已冻结待 HAG-A 绑定）。文献主清单：`50_literature/references/manifest.yaml`（`REORG01R_COMPLETE`，44 PDF/29 阅读卡，缺 gerstmayr2013；派生机器状态见 `10_research/knowledge_base/papers/controller_state.yaml`）；双任务综合：`10_research/on_orbit_assembly/dual_mission_literature_synthesis.md`。

## 已验证核心证据（引用时勿改数字）
- sim_05：B601 6R 自由漂浮，臂致基座姿态扰动峰值 **19.20°**，动量守恒 7.3e-17。
- sim_06：矢量式捕获冲量，碎片@3°/s 捕获后 3.06°/s（捕获≠消旋）。
- sim_07：ANCF 柔性帆板，点捕获激振 vs 刚性锁定 ≈**92×**，振铃 37–75s。
- sim_08：150kg 碎片消旋需推力器（|H_c|=3.65 N·m·s = 12× 轮组容量）。
- e15 认证：交叉求解最大差 5.64% > 5% 门槛 → `REPEAT_ANCF_CERTIFICATION`，全耦合新模型须重过该 Gate。
- sim_10（2026-07-18）：任务可行域已实现（`30_simulation/sim_10_mission_feasibility/`，参数卡 `20_engineering/config/mission_feasibility/scan_v0.yaml`），9000 点四门 fail-closed 扫描，裁决 `SIM10_GATES_PASS`（X1-X4+哈希锁五项全过，tests 6/6）。锚点精确落回：碎片 (μ=6.25) ω⁺=3.0633°/s→INFEASIBLE_RATE，卫星 (μ=0.917) 1.3872°/s→WHEELS_ONLY。两项科学发现入裁决 JSON：λ 边界单调性预期在过渡带 (G1 μ≈0.51) 被证伪（幅度 1.08%，亚分辨率）；X1 的 1e-6 阈值超出 sim_06 CSV 存储分辨率（对拍容差取半末位，恒等由求解器 <1e-12 承担）。刚体边界，FLEX=UNKNOWN 不入判据。
- sim_12 Phase1（2026-07-18）：16 例策略证明集，裁决 `SIM12_PHASE1_GATES_PASS`（GS1 守恒 3.85e-16、GS2 分化机器证明、B-S1 与 sim_10 锚点逐位）。核心：最优捕获策略=binding gate 的函数（A→S1、C 过渡带→S3a 轮组预置省 13×、B/D→ABORT=REPEAT_CORE 策略空间复现）。B_anchor 中 S2 使接触冲量模 `|J|` 下降，但使关于系统质心、在惯性系表达的 `|H|` 上升；外部矢量角冲量 `|ΔH_vec|` 与 `|H|` 标量变化不得混用。Gate0 账本经 Reviewer-2 独立复算修正（S2 成本 1.69 g、矢量 |ΔH_vec|=1.435）。S3b 为预注册断言未入集。
- Wave1 控制闭环（2026-07-20）：机器裁决 `WAVE1_REPEAT` 原样入档，CP6 终裁按方案 B 文档化负结果收口（10_research/partner_requirement_closure/wave1_repeat/wave1_cp6_ruling.md）。SAFE-00 运行时安全门 PASS（47/47，`review_status=PENDING_REVIEW`，`next_stage_authorized=false`；冻结合同/案例下 UNKNOWN 永不 ALLOW、七绕过面全封）；CTRL-02 姿态分账 `PASS_WITH_PROVISIONAL_SCOPE`（`review_status=PENDING_REVIEW`；7/16 仅在 R5 PROVISIONAL 执行器及时窗模型下 `STABILIZED_WITHIN_WINDOW`；L0 硬件有效稳定性 `NOT_EVALUATED_NO_ACTUATOR_DYNAMICS`；量子残差=门槛 21.5% 为 W1-R13 硬件触发项）；CTRL-01 三缺陷修复（能量账本 7.9e-2→5.63e-12、T3 碰撞合同伪影、C2_MATCH5 比较器）+ 七项真实负结果预注册保留（C3 孤立零空间真零 +1.84e-5%、冻结增益闭环锚超差等）——引用须带"冻结增益与预注册轨迹下"限定。W1-R12/R13 登记为硬件触发重跑。
- 框架收敛（2026-07-20）：稳定比赛脊柱已冻结；当前唯一候选科学实施主线为 On-Orbit Assembly Wave A，但在 HAG-A 前为 `PLANNED_NOT_AUTHORIZED`，并受 RF-1/2/3、success schema 八项/九项冲突、目标侧 FFR/AG4、W1-R12/R13 阻塞。Physics Tools、V2.5/VLA、ROM、H0–H3 与外部对拍均为后续计划态。
- 路线覆盖（2026-07-23）：近期唯一主动工作仍是 Paper 1 证据/查新收口；`BRIDGE-UT` 带界不确定目标操作与 Q6-L1 预制接口装配是两条可并行建合同、不可继承 PASS 的规划支线。Physics-Gated Agent 只完成规划冻结，状态信封正式合同、Physics Tool、SAFE 扩展、VLA、装配与新仿真均未实现/未授权。该覆盖不改写 2026-07-20 机器裁决或负结果。
- sim_11 v1.1（2026-07-18）：G4 阻断已按"有物理依据的捕获带宽"路径解除，裁决 `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`（七子项全过）。根因=理想冲量 Δt=0 对模态能指标不适定（m=2..7 慢收敛尾 +2.86/+1.29/+0.72/~+0.4%，保留为裁决 JSON `ideal_impulse_diagnostic` 非 Gate 诊断）；修复=等冲量半正弦有限接触窗（`src/contact_window.py`，T_c=20 ms 名义 **PROVISIONAL** 待 B601 夹爪实测，5–100 ms 已扫掠）。带宽下前向加密链 m3→m4→m5 模态能差 0.48%/0.027%；窗内组合动量守恒 2.7e-14、能量审计 8.5e-11、锁定收口冲量 0.035%。A2 守恒角动量 |H_O|=3.678 N·m·s（惯性原点）/ |L_C|=3.721 N·m·s（系统质心），帆板振铃 ~2.1 mm@1.0005 Hz；**帆板模态参数为占位**。v1.0 FAIL 历史见 git 6c0035b。

## 协作者记忆
### 杨恒（动力学建模合作者，微信）
- 2026-07-16 提交 `01_project/inbox/source_documents/建议.docx`：构型=中心刚体+两侧柔性帆板+机械臂；核心问题"**机械臂如何嵌入动力学模型**"（他未接触过，托 AI 出报告）；帆板 ANCF vs 浮动坐标法待决策；中心体质点 vs NCF 刚体待决策。
- 已回应：`01_project/competition/调研报告_机械臂嵌入刚柔耦合动力学模型_20260717.docx` + `01_project/competition/协作问题梳理_杨恒_20260717.md`。
- 决策记录：中心体按刚体（依据 sim_05 19.2°）；路线 A（浮动基座树形多体）为主线、路线 B（NCF+ANCF）作对标；帆板分阶段 FFR/ANCF。
- 2026-07-17 落地：路线 A 已实现为 `30_simulation/sim_11_coupled_dynamics/`（参数卡 `20_engineering/config/coupled_scene/`），场景 A1 臂展开 + A2 捕获冲量可复现。对抗审查补入 A2 能量/收敛、`base_scene` 级联、参考点与约束语义后 v1.0 判 G4 FAIL；科学结论只认 `results/sim_11_gate_check.json`。
- 2026-07-18 v1.1：G4 按待办 1 的"捕获带宽/接触柔顺性"路径闭环（见上方核心证据区），tests 27/27，`next_stage_authorized=true`。战略路线定案见 `01_project/competition/研究战略裁决_第二收敛点_20260717.md`（Paper 1 = 柔性耦合捕获任务可行域；接触带宽=Paper 1 §方法 + Paper 2 保真度候选）。
- 🔔 待办 1（更新）：杨恒提供"一般仿真的数值案例设置"后，替换 `20_engineering/config/coupled_scene/coupled_model_v0.yaml` 占位字段（勿散落在文档里），并**重跑 sim_11 全部场景与 Gate**（复现命令见报告第 7 节）。
- 🔔 待办 2（新）：硬件组实测 B601 夹爪闭合时间 → 替换 `scene_A2_capture.yaml` contact.T_c_ms_nominal（现 20 ms 占位）→ 重跑带宽口径 Gate。
- 🔔 待办 3（新）：向杨恒强调帆板质量 0.348 kg 为 SSOT 占位（真实 2–5 kg/m²，差 5–10 倍）——真实参数下"A1 柔性反馈可忽略"结论可能翻转，属论文最大硬伤，优先级最高。

## 约定
- 中文交流；文档进 `01_project/competition/`；每个 sim_XX/eXX 自带 results/tests/docs/机器裁决。
- 新耦合动力学模型验证链：锁关节后的帆板组件级同激励口径→对比 sim_07；帆板刚化→退化 sim_05；全刚化→同一组合体的 sim_01 式无力矩传播；动量守恒机器精度。
