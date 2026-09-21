# PROJECT CURRENT STATE — 2026-08-29 (PL2 重建快照)

> 本文件只是 **导航 + 已验证状态索引**,不是新的科学 SSOT。数字只允许来自下列
> 机器 Gate;本文件与 Gate 冲突时以 Gate 为准。生成:`SEI-PL2 READ_ONLY_RECONSTRUCTION`。
> 证据目录:`01_project/governance/sei_pl2_reconstruction_20260829/`

## A. Competition(比赛)

- 裁决:**`COMPETITION_DEMO_READY` 17/17**(离线回放;`command_emitted=false`;不依赖装配 Wave A)
- 权威:`10_research/competition_convergence/competition_gate_check.json`
- 交付媒体:`40_evidence/artifacts/competition_convergence/`(mp4 55s + pptx 9p + 三场景回放包,2026-08-04)
- 阻塞/未知:**官方章程与申报书模板不在仓库**,提交格式需人工确认(截止 2026-09-01)
- 禁止声称:机械 release 完成 / 装配完成 / 硬件验证

## B. Scientific Core(科学主线)

| 模块 | 裁决 | 权威路径 |
|---|---|---|
| sim_10 可行域 | `SIM10_GATES_PASS` | `30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json` |
| sim_11 耦合+接触带宽 | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS` | `30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json` |
| sim_12 策略 Phase1 | `SIM12_PHASE1_GATES_PASS` | `30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json` |
| SAFE-00 安全门 | `PASS`(PENDING_REVIEW,不自动授权) | `30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json` |
| CTRL-01 末端控制 | `REPEAT`(负结果收口) | `30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json` |
| CTRL-02 姿态分账 | `PASS`(provisional 执行器/时窗) | `30_simulation/control_02_base_attitude/results/control_02_gate_check.json` |
| MuJoCo 预接触 | 6/6 诊断 PASS;**父链全 HOLD** | `30_simulation/r2_mujoco_free_floating_precontact_v1/results/R2_MUJOCO_FREE_FLOATING_PRECONTACT_GATE_V1.json` |
| Sim13 具身抓取 | v2 rebind(23/23 候选)+ v3/v4 诊断链;父 HOLD | `30_simulation/sim_13_physics_gated_embodied_grasping/` |
| E23 柔性重认证 | `E23_R2_FULL_FLEX_COUPLED_GATE_V1` | `30_simulation/e23_r2_full_flex_coupled_recert/results/` |

可引用核心数字(勿改):19.20° 基座扰动;3.0633°/s 捕获后;3.65 N·m·s=12× 轮组;92× 柔性激振;
S2 成本 1.69 g、矢量 |ΔH_vec|=1.435;HF→ROM 0.2714%。

## C. Mechanical(机械)

- Release 裁决:`TERMINAL_CLOSURE_EXECUTED__GATE_A_NOT_PASSED__TMG4_TM6_INTERNAL_BLOCKERS_REGISTERED__NO_RELEASE_CREDIT`(2026-08-25)
- 权威:`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json`
- R2 权威链:`01_project/competition/CURRENT_R2_AUTHORITY_DELTA_V8.json`(append-only;Link2-B12 24/24 本地;系统 1/150 operational、0/11166 pair;`release_credit=false`)
- TMG-4=HOLD(线束 0/75 SAFE);TMG-6=FAIL_15_OF_20(Sim13 依赖)
- **禁止声称**:碰撞有效 / M01 绑定 / 机械发布 / 任务放行

## D. Paper(论文)

- Paper 1:架构 v1.0 + 结构计划冻结;**正文未起草**;Fig.5–7 BLOCKED
- 权威:`10_research/paper1_architecture.md`、`10_research/00_project_architecture/paper_structure_plan.md`
- 文献:44 PDF/29 卡(`50_literature/references/manifest.yaml`);08-23 查新红线/绿线裁决;
  行动项:精读 Wang 2026 / Lu 2026 / Ma 2026(未完成)
- 不做:在轨装配、VLA、硬件验证入 Paper 1 贡献

## E. Repository / Governance(仓库与治理)

- Git:`publication/stage3-integrity-closure` @ `5c5adde`;porcelain dirty(~179,多为未跟踪治理输出)
- Root A:`F:\China Graduate Future Flight Vehicle Innovation Competition`(43k 文件 / 18.35 GiB)
- Root B:`F:\SPACE_ROBOTICS_REFERENCE_LIBRARY`(REFLIB1/2,物理名禁改)
- Archive:`F:\SEI_PROJECT_ARCHIVE`(CM/法证/灾难恢复)
- Worktrees:21 注册;14 codex(3 dirty)+ 2 prunable + kb 注册残留(目录已消失,分支仍在)
- PL1 清理:220 重复已隔离(`F:\_SEI_RETIREMENT_QUARANTINE_20260828`,硬删 >=2026-09-15)
- 三个消失根裁决:GHMIG=`VERIFIED_RETIRED`;kb-worktrees=`MISSING_BUT_FULLY_RECOVERABLE`;
  `_SEI_PROJECT_CONSOLIDATION_20260807`=`MISSING_WITH_UNIQUE_CONTENT_RISK`(待全量对拍)

## 一个入口 + 五条主线 + 明确历史

- 唯一入口:本文件 + `PROJECT_MAP.md` + `AGENTS.md`
- 五主线:A 比赛 / B 科学 / C 机械 / D 论文 / E 治理(状态表 `sei_pl2_reconstruction_20260829/03_CURRENT_DOMAIN_STATUS.csv`)
- 历史区:`90_archive`(PLAN A 授权后启用)+ ARCHIVE 根
