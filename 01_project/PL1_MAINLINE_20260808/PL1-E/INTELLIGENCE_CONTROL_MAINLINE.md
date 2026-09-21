# INTELLIGENCE_CONTROL_MAINLINE.md — PL1-E 控制 / SAFE-00 / 具身智能 / 演示主线重建

- Recon agent: PL1-E (read-only reconstruction, no consolidation)
- Repo (ROOT A): `F:\China Graduate Future Flight Vehicle Innovation Competition`
- Verified git HEAD: `5c5addea00ddb70d86a5cc37a88bbcda50350e43` (branch `publication/stage3-integrity-closure`), lineage b75352c → e14b224 → cd0ea80 → 5849b72 → 5c5adde (matches mission context)
- Recon date basis: file mtimes 2026-08-07/08 (checkout time); evidence content dates from git commits stated per item.
- **Label note**: the project does NOT use "M7/M8/M12/M13" internally (grep confirms only metric names M1–M8 inside plans). Mapping used here: **M7 = control & SAFE-00 (L1/L2 of the six-layer frame)**; **M8 = embodied AI (L4: VLA / Physics Tool / policy candidate-execute / agent prototype)**; **M12 = competition demo lane (competition_convergence Lane C)**; **M13 = paper/research lane (Paper 1 + literature/knowledge system)**.

Authoritative frame sources actually read and verified:
- `10_research/README.md` (six-layer research framework + verdict index, 2026-07-23)
- `10_research/research_state_v4.md` (current snapshot, 2026-07-20)
- `10_research/framework_convergence/active_mainline_dag.md` (唯一科学主线授权图)
- `10_research/knowledge_base/project_context/current_state.md` (watermark 2026-07-23)

---

## M7 — Control & SAFE-00 (six-layer L1 安全决策层 + L2 控制层)

### M7a. CTRL-01 末端轨迹跟踪 (end-effector tracking)

- **Authority**: module `30_simulation/control_01_end_effector_tracking/**` + config `20_engineering/config/control_scene/control_01_v0.yaml` (schema control-01-v1, thresholds frozen, `thresholds_widened=false`). Task state: `task_current_state.md` (CTRL-01-R remediation round).
- **Current files**: src/ (controller.py, simulator.py, fast_plant.py, trajectories.py, collision_evidence.py, contracts.py, run_experiments.py, run_gates.py, freeze_evidence.py, repo_imports.py), tests/ (7 test files), results/ (gate JSON, timeseries/summary CSV, PNG, manifests), docs/control_01_report.md.
- **Status**: **DONE (evidence frozen) — machine verdict REPEAT** (`next_stage_authorized=false`); LOOP-6 independent red team **PENDING_REVIEW**.
- **Latest valid result**: `30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json`, content last committed `284c882` (2026-07-22 18:39 +0800). Ten-item gate: A1 PASS, A2 REPEAT (C1-T1 anchor 0.1550 > 0.05 deg), A3 PASS, B PASS (conservation 7.2e-16 / energy 5.6e-12), C PASS (ratio 1238.4), D REPEAT, E REPEAT (collision subitem PASS, combined min +0.01462 m), F REPEAT, G PASS, H PASS (fast-plant/SSOT 4.44e-16). Tests 22/22 PASS (tests ≠ Gate).
- **Superseded items**: v0 loop evidence base `20cc50b` superseded by CTRL-01-R remediation (R-2 T3 trigger freeze, R-3 energy ledger FOH+DOP853 fix); withdrawn −5° post-hoc probe explicitly not reused (CTRL-02 analog; for CTRL-01 the C1_MATCH5 comparator demoted to context in favor of C2_MATCH5 18-run matrix).
- **Open holds**: REPEAT items adjudicated TRUE NEGATIVES under frozen thresholds (T1 anchor limit conflict −1.048 rad, singular start σ 6.64e-5, C1-T3 bound 0.1902 m > 0.11 m, engage-transient accel 9.11); known preregistered conflict — 19.20° anchor uses joint2 +60° outside URDF interval [−π, 0], kept as reported constraint conflict. LOOP-6 review not self-certified.
- **Next task**: none authorized for CTRL-01 itself ("不再同题修复"); role is design-constraint input to ASM-02 skeleton ("负结果约束相位设计" per active_mainline_dag.md).

### M7b. CTRL-02 基座姿态分账 (base attitude / momentum attribution)

- **Authority**: module `30_simulation/control_02_base_attitude/**` + config `20_engineering/config/attitude_stab/attitude_stab_v0.yaml` (frozen PROVISIONAL actuator layer: wheel max 0.01 N·m/axis, thruster min pulse 20 ms, 300 s window criteria).
- **Current files**: src/ (phase_a.py, phase_b.py, transient_b.py, ledger.py, config_loader.py, run_experiments.py, run_gates.py, freeze_evidence.py), tests/ (6 files), results/ (gate JSON, stage A/B summaries, gc0 momentum ledger, sim12 independent crosscheck), docs/GC0_momentum_attribution.md.
- **Status**: **DONE (CTRL-02-R remediation complete) — machine verdict PASS with scope limits**; external wording fixed as `PASS_WITH_PROVISIONAL_SCOPE`; `review_status=PENDING_REVIEW`; deliberately unmerged, awaiting integrator-R + PI final adjudication.
- **Latest valid result**: `results/control_02_gate_check.json` — gate `control02-gate-v3`, GC0–GC7 ALL PASS, tests 24/24, content committed `284c882` (2026-07-22). Honest negatives preserved: A1 peak 9.24° > A0 8.73° on M2; A1 18.84° < A0 19.20° on M1; A3 = `NOT_APPLICABLE_WITH_MISSING_FROZEN_ACTUATOR_DYNAMICS`; 16 transient rows: 7 stable / 9 unstable; `thresholds_widened=false` + `repeat_revision.thresholds_changed=false` double machine assertions.
- **Superseded items**: first-round LOOP-0…7 REPEAT verdict (GC1 two independent causes: M2 zero-start limit margin 0.0 < 0.05 rad; A1 endpoint degradation 584.7/322.0 mm) — superseded by CTRL-02-R under preregistered R-4/R-5 authorized by CP3; withdrawn −5° probe not reused.
- **Open holds**: R-5 actuator values are PROVISIONAL (not hardware-qualified); L0 hardware-effective stability NOT_EVALUATED; W1-R12/R13 (0.01 N·m/axis unification & re-evaluation) open and blocking ASM-02 formal run.
- **Next task**: after hardware freeze, replace PROVISIONAL wheel torque / thruster min-pulse with measured values and re-run transient layer; re-check 0.05 °/s stability threshold vs pulse-quantum residual floor (~0.049 °/s lightest assembly).

### M7c. SAFE-00 运行时安全门 (runtime safety gate)

- **Authority**: module `30_simulation/safety_00_runtime_gate/**` + contracts `20_engineering/config/safety_gate/**` (3 closed schemas + `safety_policy_v1.yaml`, policy v1.2, status FROZEN_FOR_SAFE_00_WAVE1). Baseline commit `926522f`; task state `task_current_state.md`.
- **Current files**: src/ (safety_core.py 931 lines, run_gates.py, run_diagnostics.py, case_factory.py), tests/ (run_all.py, test_core/test_contract/test_bypass), docs/ (safety_gate_contract.md, safety_gate_design.md), results/ (gate check JSON, tests log, latency diagnostic, evidence manifest, 4 baseline reproduction log pairs), baseline_reproduction.json.
- **Status**: **DONE (frozen core) — verdict PASS, review PENDING** — LOOP-0…5, 7 PASS; LOOP-6 independent red team **PENDING_REVIEW** (defects fixed, not self-certified); `next_stage_authorized=false`.
- **Latest valid result**: `results/safety_00_gate_check.json` — verdict PASS; GS-A/GS-B/GS-C all pass (12 bypass cases, 0 successes; registry actual==expected `400bcedce5af…387b2873`); metrics unknown_allow=0, bypass=0, false_abort=0.0, provenance complete=1.0; determinism bitwise over 16 preregistered cases; gate payload SHA-256 `7a352fe3d511804da3c182ee6380e3c86003173796ab912f5390ec43bb66836c`; content committed `284c882` (2026-07-22); baseline reproduction executed 2026-07-19T02:14:30+08:00 (sim_05 22/22, sim_10 6/6, sim_11 27/27, sim_12 3/3).
- **Superseded items**: policy v1.1 raw-byte binding superseded by v1.2 canonical-semantic binding after Windows CRLF drift observation (raw drift documented, semantic content equal; registry stays raw-byte frozen). LOOP-6 findings (12 items: candidate row binding, pre-capture ω=0.5 deg/s, mass ratio 22/24, sim_11 GLOBAL_NON_SCENARIO marking, scenario hash time coverage, HMAC key discipline, latency moved out of gate JSON, determinism) all remediated.
- **Open holds**: sim_11 still carries PROVISIONAL params (panel modes, contact T_c); e15/L2 = `REPEAT_ANCF_CERTIFICATION`; assembly extension AG5 not implemented (Wave B per DAG blocker B7); production HMAC key intentionally absent (fail-closed by design).
- **Next task**: independent LOOP-6 re-review (external), then — only via HAG-style human approval — Wave B AG5 assembly-safety extension; currently serves Wave A only as fail-closed semantics audit input (grants no assembly execution).

---

## M8 — Embodied AI (six-layer L4 具身智能层) — 规划态，未实现

### M8a. VLA generalization protocol (research object ①②: L3 candidate generation + L4 skill selection)

- **Authority/ownership**: `10_research/vla/vla_generalization_plan.md` (protocol v0, 2026-07-19), role card `.codex/agents/physics-agent-architect.md`.
- **Status**: **NOT_STARTED — PROTOCOL_DRAFT** (explicit: 未实现、未采数、未训练; prompt-engineering + tool-interface + evaluation only, no model training, no RL, no end-to-end VLA).
- **Latest valid result**: none (design document). Closest machine anchor: preregistered metrics M1–M8 and 4-baseline ablation ladder (V0 marker rules / V1 generic vision / V2 VLA-candidate / V3 VLA+PhysicsTool+Gate) defined but never executed.
- **Superseded items**: none (first version).
- **Open holds**: rendering/domain-randomization pipeline NOT_STARTED; sim_12 Phase2 grid expansion unscheduled; panel real params (杨恒) and B601 T_c measurement BLOCKED_BY_EXTERNAL_INPUT (rigid-body scope not blocked); decision-vocabulary alignment with `.codex/agents/physics-agent-architect.md` pending (REOBSERVE added, EXECUTE_UNDER_ASSUMPTIONS spelling unification required before implementation).
- **Next task**: vocabulary unification edit to the agent card; then preregistered implementation proposal (new protocol review) — no execution authority exists today.

### M8b. Physics Tool contract (five read-only tools over frozen artifacts)

- **Authority/ownership**: `10_research/vla/tool_contract_draft.yaml` (v0-draft), paired with the VLA protocol.
- **Status**: **NOT_STARTED — DRAFT_NOT_IMPLEMENTED**.
- **Contract content (verified)**: tools `query_feasibility` (sim_10 scan CSV ~9k points × 8 tiers), `evaluate_capture` (sim_09 hard-constraints + collision geometry + λ折算 → sim_10), `compare_strategy` (sim_12 strategy_results.csv 16 rows), `check_resources` (sim_08-derived capacity columns via sim_10 + scan_v0.yaml), `recommend_action` (consumes prior responses only; five-word decision vocabulary). Every response must carry provenance {gate_json_path, registry_sha256 (`400bcedc…`), scenario_hash, data_row_refs}; fail-closed error semantics (REFUSE_OUT_OF_DOMAIN / REFUSE_ILLEGAL_CALL / REFUSE_STALE_ARTIFACT / ANSWER_WITH_ASSUMPTION); FLEX=UNKNOWN never translatable to unconditional executable.
- **Latest valid result**: none (no implementation).
- **Open holds / next task**: formal Physics Tool interface = PLANNED; implementation requires separate authorization wave (Wave B/C queue per DAG: "ROM→Tools→FSM/V2.5→VLA→H0-H3" deferred).

### M8c. Policy candidate-execute discipline (L4 decision → SAFE-00 hard gate)

- Verified design: L4 output restricted to five-word vocabulary {WAIT, REOBSERVE, CHANGE_CONFIG, ABORT, EXECUTE_UNDER_ASSUMPTIONS}; every EXECUTE must cite the provenance triple (gate JSON path + frozen registry hash + scenario hash); SAFE-00 (rule code, not a model) independently re-checks before anything reaches L5; VLA output may never map to torque/joint commands (L5 red line). Candidate row binding realized today only for `A_low-S1_passive` inside SAFE-00 (see SAFE00_DIGITAL_THREAD.md).
- **Status**: contract-level frozen (vla plan §6.2 + safety-gate-v1 contract); **implementation NOT_STARTED**.

### M8d. Space Embodied Agent Prototype (comp_prot_*) — PRESENT / CONTRACT-ONLY / HOLD

- `10_research/README.md` (current, in-git) and `knowledge_base/project_context/current_state.md` reference `10_research/space_embodied_robotics/` (space_embodied_agent_v1_contract.md, comp_prot_02, comp_prot_03_a0_a1, comp_prot_03_a2, comp_prot_03_a3_g0) with status `DIGITAL_BODY_METHOD_CONTRACT_ONLY` / `CAD_ENTRY_BLOCKED_BY_EVIDENCE`.
- **PL1-G copy-verify result**: `space_embodied_robotics/`、`research_questions/`、`theory_graph/`、`contribution_map/`、`research_os_01/02/` 及 `comp_prot_03_a4_b5_*` 已从治理临时区复制回 ROOT A；它们当前 **PRESENT_UNTRACKED_HASH_VERIFIED**，源区保留，逐文件哈希见 `PL1-G/manifests/EXTRAS_{source,dest}.sha256`。这关闭了“主仓物理缺失”，但不授予执行 authority。
- **Status: CONTRACT_ONLY / implementation NOT_STARTED** — PL1 补充抢救已将 `30_simulation/module_cards/` 9 文件与 `20_engineering/config/competition_prototype/` 6 文件 copy-verify 回 ROOT A，15/15 SHA-256 一致，关键合同直接链接已恢复。它们与前述 research 目录均仍 untracked、无执行 authority；可称“合同链物理完整”，不可称 prototype ready、模型已实现或闭环已执行。

### M8e. Embodied-AI ↔ simulation / B601-truth connectivity (what the stack actually reads)

- **AI layer → simulation**: by frozen design, the embodied stack consumes ONLY frozen machine-verdict artifacts: `30_simulation/sim_10_mission_feasibility/results/sim_10_scan_gates.csv` + `sim_10_gate_check.json`, `30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv` + `sim_12_gate_check.json`, `30_simulation/sim_09_grasp_evaluator/results/` + `20_engineering/config/grasp_evaluator/{hard_constraints_v1,collision_geometry_v1}.yaml`, `20_engineering/config/mission_feasibility/scan_v0.yaml`, threshold registry `30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml` (sha256 `400bcedce5af6ad5c4135e67f87bb524ee2fdafb1c26aeae07e495ff387b2873`). **No Isaac Sim / MuJoCo / ROS2 / Basilisk / Gazebo project integration exists in ROOT A**; SpaceRobotEnv/MuJoCo and several other upstream checkouts are reference-only source trees with no adapter, frozen result or runtime import. `10_research/README.md` explicitly lists "Isaac Sim/ROS/Basilisk 集成" as NOT authorized.
- **Control stack → B601 truth**: `30_simulation/sim_05_free_floating_arm/b601_model.py` parses the B601 URDF (pure xml.etree, FK/Jacobians; gripper merged into link6) and is imported by sim_05 dynamics, `sim_11_coupled_dynamics/src/coupled_dynamics.py:100`, `sim_09_grasp_evaluator/src/{ik.py,adapters.py}`, and CTRL-01's plant via `repo_imports.py`. Geometry/config truth: `20_engineering/config/geometry/arm_b601_v1.yaml` (SSOT), `20_engineering/config/control_scene/control_01_v0.yaml`, `20_engineering/config/attitude_stab/attitude_stab_v0.yaml`, `20_engineering/cad/spacecraft_layout/{target_satellite_v0,target_debris_v0,servicer_12U_v0,...}/*.json`.
- **HOLD / broken-at-HEAD link (verified by execution)**: `b601_model.py:39-40` computes `URDF_PATH = <repo_root>/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf` (two levels up from `30_simulation/sim_05_free_floating_arm`). There is **no top-level `cad/` in ROOT A** at HEAD — the URDF lives at `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf` (raw sha256 prefix `1bc2b7483cd8025d…`, matching PROJECT_START_HERE's accepted-truth hash). Verified: `B601Arm()` raises `FileNotFoundError` at HEAD. Cause: REORG04 (`284c882`, 2026-07-22) moved `cad/`→`20_engineering/cad/` and `sim/`→`30_simulation/` without updating this relative path (pre-REORG path was `sim/sim_05_free_floating_arm/` → root-relative `cad/` which existed then). **Frozen gate evidence remains valid (produced 2026-07-19/22), but fresh reproduction of sim_05/sim_09/sim_11/CTRL-01/CTRL-02 dynamics chain is broken at HEAD until this one-line path is repaired.** (Not repaired here — read-only mandate.)
- PROJECT_START_HERE 的 accepted-URDF 路径已由 PL1-G 修正到 `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`；旧 B5.1R1 authority 路径只保留在历史 CM 证据中，内容与当前权威副本哈希相同，不构成双真值。

---

## M12 — Competition demo lane (Lane C) — DONE, frozen, offline-only

- **Authority**: `10_research/competition_convergence/` (contract `mission_demo_contract.yaml`, `three_scenario_manifest.yaml`, claim-evidence matrix CSV, src/ gate + replay builders, tests, results/) with delivered media in `40_evidence/artifacts/competition_convergence/` (mp4 + pptx + manifests).
- **Status**: **DONE — `COMPETITION_DEMO_READY`** (demo spine frozen; evidence-orchestration only; does not compete with the science mainline — DAG discipline rule 1).
- **Latest valid result**: `10_research/competition_convergence/competition_gate_check.json`, committed `1c9183d` (2026-07-22 18:48 +0800): `final_verdict=COMPETITION_DEMO_READY`, checks 17/17, tests 19/19, red team 15/15, offline replay deterministic and byte-identical (replay content `2e2b715f…`), scenario actions A_low=EXECUTE (explanation only, execution_authority=false), B_anchor=ABORT (upstream, SAFE-00 NOT_APPLICABLE), C_transition=MODIFY (candidate binding MISSING → re-enter authorization later); `command_emitted=false`, `real_time_synchronization=false`, `next_stage_authorized=false`, `thresholds_widened=false`; stop rules all false (start_vla / start_wave_b / start_hil / move_b601 / start_asm01_asm02). Delivered media verified present: `competition_mission_intelligence_demo.mp4` (h264 1920×1080, ~55 s) and 9-slide PPTX (177,259 B, sha `9deff92b…`).
- **Superseded items**: first root-integration verification FAIL (CRLF-vs-LF raw hash on strategies_v0.yaml + pre-existing dirty-file scope misjudgment + non-NUL git status parsing) — superseded by repaired contract/verifier keeping LF raw bytes as sole runtime binding and CRLF observation as preserved negative evidence.
- **Open holds**: ASM-00 reported separately as `ASM00_BLOCKED_BY_MISSING_PARAMETERS` (RF-1 funnel reduction 2.1436 mm < 4.9 mm; RF-2 tan15°=0.2679 < μ=0.3; RF-3 clearance semantics unfrozen; shared pin/chamfer params missing; HAG-A/B/I do not exist); H0/H1/H2 NOT_STARTED chain; B601_MOTION=PROHIBITED.
- **Next task**: none in-lane (frozen). Any change → automatic demotion to COMPETITION_DEMO_REPEAT/BLOCKED per execution report §9. Demo dependency: demo does NOT require Assembly Wave A pass (`competition_chain_independent_of_assembly_wave_a_pass=true`).

---

## M13 — Paper / research lane — ACTIVE (architecture current, paper not written out)

- **Authority**: `10_research/paper1_architecture.md` v1.0 (现行 per 10_research/README) + literature system `50_literature/references/` + knowledge navigation `10_research/knowledge_base/`.
- **Status**: **ACTIVE (paper lane)**: Paper 1 architecture current ("Strategy Selection under Momentum and Stability Constraints for Non-Cooperative Spacecraft Capture", target Acta Astronautica, fallback JGCD/Adv.Space Res.); evidence base locked to machine verdicts (sim_10 PASS, sim_11 PASS_W_PROVISIONAL, sim_12 PHASE1 PASS, sim_09 e1 72-case). Writing red lines frozen (no "first/fully autonomous/on-orbit validated"; no unconditional S2 ranking; FLEX conclusions barred).
- **Latest valid result**: literature/knowledge machine state `10_research/knowledge_base/papers/controller_state.yaml` (generated 2026-07-22, verdict `PAPER_KNOWLEDGE_STATE_BUILT`, authority DERIVED_NAVIGATION_ONLY): 45 manifest entries, 44 local PDFs present, 34 reading cards complete, 10 PDF-ready, 1 blocked (gerstmayr2013ancfreview, no fulltext); DOI 33 VERIFIED + 2 VERIFIED_AFTER_ADJUDICATION. Note: 10_research/README + research_state_v4 quote "44 PDF/29 卡" — minor count drift vs controller_state's 34 cards (different date/criteria; non-blocking, recorded).
- **VLA/embodied literature base (M8 support)**: `50_literature/references/notes/` section V4 embodied_vla — spacemind2026 (closest competitor, P0), kawaharazuka2025vlareview, ma2024vlasurvey, kim2024openvla, orsula2025srb (Isaac Sim bench), park2021speedplus, park2024poseestimation, rodriguez2024lmspacecraft, visualservoing2024survey — all READING_CARD_COMPLETE per controller_state.
- **Superseded items**: research_state_v3 superseded by v4; 7 redundant framework docs archived in framework convergence sweep (commit c7f09ab/5a63fe3).
- **Open holds**: Paper 1 figures partly un-drawn (Fig.1/Fig.5 need Gate-0-assertion recomputation); contribution novelty pending systematic search ("在 59 条检索语料内未见" wording only); gerstmayr2013 fulltext missing; claim_evidence_rows=0 in controller (claim-evidence matrix population pending).
- **Next task**: populate claim–evidence matrix; complete Paper 1 draft per architecture (no new experiments authorized — run rule `NO_NEW_SIMULATION — STOP_AFTER_ARCHITECTURE_FREEZE`).

---

## Competition-lane vs paper-lane separation (explicit)

| | Competition lane (M12) | Paper/research lane (M13) |
|---|---|---|
| Root | `10_research/competition_convergence/` + `40_evidence/artifacts/competition_convergence/` | `10_research/paper1_architecture.md`, `50_literature/`, `10_research/knowledge_base/`, `10_research/framework_convergence/` |
| Verdict | COMPETITION_DEMO_READY 17/17 (frozen) | PAPER_KNOWLEDGE_STATE_BUILT; Paper 1 architecture v1.0 current |
| Consumes | Frozen replay of sim_10/sim_12/SAFE-00/CTRL-02 evidence; offline only, no commands | Same frozen machine verdicts as citable evidence; literature cards |
| Rule | 比赛链冻结，只做证据编排，不争夺"当前科学主线" (DAG rule 1) | Science mainline candidate = On-Orbit Assembly Wave A (`PLANNED_NOT_AUTHORIZED`, HAG-A gated) |
| Produces | Demo PPTX/MP4, replay JSONs | Paper draft, reading cards, claim-evidence matrix |

External item classified: **`F:\VLA算法论文`** (top-level check only) = independent research workspace for the paper idea "Action-Counterfactual Token Routing for Efficient VLA" (VLA token-pruning efficiency; own AGENTS.md/PROJECT_CHARTER.md/papers/notes/scripts/outputs; dated June 2026). It is NOT part of ROOT A, holds no competition assets, and no top-level reference into ROOT A was observed → **REFERENCE / external paper-lane workspace**, not a project asset. (Its topic is VLA-efficiency, distinct from ROOT A's VLA-generalization protocol; treat as separate research thread.)

---

## NEW_CONTRADICTION / HOLD register (for PL1-G)

1. **HOLD-1 (broken reproduction path, verified)**: `30_simulation/sim_05_free_floating_arm/b601_model.py:39-40` URDF path resolves to non-existent `<root>/cad/...` at HEAD; `B601Arm()` → FileNotFoundError (verified by execution). Affects fresh runs of sim_05/09/11, CTRL-01/02 plants. Frozen gate JSONs unaffected (they reference config/registry/CSV artifacts that all exist and hash-match). Pre-REORG04 location `sim/sim_05_free_floating_arm/` explains the stale `../../cad/` relative path. Fix = one-line path correction, but NOT applied (read-only mandate; touches frozen simulation behavior → needs governance).
2. **RESOLVED-2 (physical contract chain) / residual CM HOLD**: research/prototype directories、`20_engineering/parameter_registry/`、`30_simulation/module_cards/` 与 `20_engineering/config/competition_prototype/` 均已 PRESENT_UNTRACKED_HASH_VERIFIED；源区保留。残余问题仅为 Git/CM/备份状态与实现未授权，不再是缺失链接。
3. **RESOLVED-3 (accepted URDF path)**: PROJECT_START_HERE and CM SSOT now point to `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`; raw/normalized hashes remain frozen.
4. **Minor drift (not a contradiction)**: literature card count 29 (README/research_state_v4) vs 34 (`controller_state.yaml`, newer, 2026-07-22) — different snapshot dates/criteria.
5. **Not contradictions (re-verified intact)**: threshold registry hash `400bcedc…` consistent across SAFE-00 policy, VLA plan, tool contract, gate JSON; sim_12 gate JSON verdict/hash match policy binding (`9f94c1c7…`); SAFE-00 16-case payload hash `7a352fe3…` matches task state; competition gate JSON internally consistent with execution report; git HEAD matches CM closure lineage.
