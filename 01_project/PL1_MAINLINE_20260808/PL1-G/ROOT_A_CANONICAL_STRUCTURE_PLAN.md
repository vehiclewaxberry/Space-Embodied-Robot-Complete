# ROOT_A_CANONICAL_STRUCTURE_PLAN.md — PL1-G (Task 2.2)

- **Date**: 2026-08-08 · **Scope**: ROOT A = `F:\China Graduate Future Flight Vehicle Innovation Competition` @ git HEAD `5c5adde` (branch `publication/stage3-integrity-closure`)
- **Rule**: this maps the mission's logical domains onto the **existing** layout. No renumbering, no mass migration is proposed. The current top-level scheme (`01_project / 08_REVIEWS / 10_research / 20_engineering / 30_simulation / 40_evidence / 50_literature / 70_tools / 80_third_party / knowledge / structure`) is the canonical one, set by REORG04 (`284c882`, 2026-07-22) and confirmed by all six recon agents.

## 1. ROLE → ACTUAL PATH map

| Mission logical domain | ACTUAL PATH (ROOT A) | Status | Notes |
|---|---|---|---|
| **project_control** (governance, gates-as-docs, tasking, PL1 outputs) | `01_project\` (`governance\`, `competition\`, `inbox\`, `PL1_MAINLINE_20260808\`) + entry docs at root (`PROJECT_START_HERE.md`, `PROJECT_MAP.md`, `CLAUDE.md`, `PROJECT_ONBOARDING_PACKAGE\`) | ACTIVE | PL1 deliverables under `01_project\PL1_MAINLINE_20260808\PL1-*\`; `PL1_INDEX.md` = master index |
| **system** (spacecraft system/layout/structure definitions) | `structure\` (ASSEMBLY_GROUND/ONORBIT, BOM_12U, INTERFACE_ARM_BUS, LOAD_PATH, MASS_BUDGET, STRUCTURE_DELTA) + `20_engineering\system_design\` + `20_engineering\stage1_spacecraft_layout\` | ACTIVE (v0, confidence low) | system mass budget `UNSOURCED_BLOCKED` (PL1-B §18) |
| **engineering** (mechanical CAD, configs, interface control) | `20_engineering\` — `cad\` (freecad_authoritative C1-A, reference_donors\HAGA_HIFI_FREECAD C1-B, spacecraft_layout incl. `arm_b601_v1`), `config\` (geometry/coupled_scene/safety_gate/...), `F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\`, `F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\`, `F3_MECHANICAL_TERMINAL_AUDIT_20260806\`, `F3_P5_structural_closure_candidate\`, `design_inputs\`, `design_review\`, `parameter_registry\` | ACTIVE | F3R1/F3R2 + 5 support dirs **restored by PL1-G salvage 2026-08-08** (sha-verified, untracked); current native baseline = F3R2 SLDASM (PENDING_HUMAN_REVIEW) |
| **dynamics_control** (dynamics models + control modules + safety gate) | `30_simulation\` — `common\`, `sim_01..sim_12`, `control_01_end_effector_tracking\`, `control_02_base_attitude\`, `safety_00_runtime_gate\`, `e15_*\`, `e16_sync_capture\`, `asm_00_interface_preflight\` | ACTIVE (all FROZEN gates) | HOLD: `sim_05_free_floating_arm\b601_model.py:39` URDF path broken at HEAD (pre-REORG04); one-line fix pending governance |
| **embodied_intelligence** (VLA protocol, agent prototype contracts, Physics Tool) | `10_research\vla\` + `10_research\space_embodied_robotics\` (restored by PL1-G) + `10_research\comp_prot_03_a4_b5_*\` (restored) + role card `.codex\agents\physics-agent-architect.md` | PLANNING LAYER ONLY | VLA = PROTOCOL_DRAFT; Physics Tool = DRAFT_NOT_IMPLEMENTED; no Isaac/MuJoCo/ROS2/Basilisk integration anywhere (verified by PL1-C/E) |
| **simulation** (as a domain distinct from dynamics_control: scenario map, freeze governance) | `30_simulation\` (same tree; governance docs at `10_research\00_project_architecture\simulation_scenario_map.md`, `10_research\framework_convergence\tool_stack_decision.md`) | FROZEN (`NO_NEW_SIMULATION`) | 15 gate JSONs registered; rerun forbidden except authorized triggers |
| **hil_experiment** | — | **NOT_STARTED** | No HIL dir exists; HIL route docs are historical plans only (`01_project\competition\archive\01_award_strategy_and_critical_path.md`); H0–H3 chain NOT_STARTED per M12 recon |
| **dataset** | — | **NOT_STARTED** | No dataset dir; ROOT B R5 holds speedplusbaseline *code* only (dataset never downloaded); rendering/domain-randomization pipeline NOT_STARTED (VLA plan) |
| **third_party** | `80_third_party\` (`vendor\` gitignored clones incl. reBot-DevArm runtime-referenced STEP; `external\`) | ACTIVE | reBot-DevArm = disk dependency, **no cold backup (DR P0)**; vendor duplicates of ROOT B repos pending dedupe ruling |
| **evidence** | `40_evidence\` (`c1_evidence\`, `artifacts\` incl. competition_convergence media, `tables\`) | ACTIVE (tracked, frozen) | historical evidence; not a current design input |
| **paper_competition** | Paper lane: `10_research\paper1_architecture.md` (v1.0, Acta Astronautica target), `50_literature\`, `10_research\knowledge_base\` · Competition lane: `10_research\competition_convergence\` + `40_evidence\artifacts\competition_convergence\` + `01_project\competition\` | PAPER ACTIVE / DEMO DONE | lanes separated per DAG rule 1 (competition = frozen evidence orchestration only) |
| **archive_index** | Pointer layer in `01_project\` + `PROJECT_START_HERE.md` §8 → physical archive `F:\SEI_PROJECT_ARCHIVE` (514 files after CM3A copy, ARCHIVE_BOUND_TO_A) | ACTIVE | see `ARCHIVE_INTO_ROOT_A_MIGRATION_PLAN.md` (phase 0 = pointer, no physical move) |
| **reviews** | `08_REVIEWS\` | EMPTY at HEAD | LOOP-6 independent reviews (SAFE-00, CTRL-01) have no records here — flagged as gap, needs-human |

## 2. Salvaged subtrees now resident (from PL1-G Task 1, 2026-08-08)

`20_engineering\`: F3R1 (363) · F3R2 (482) · F3_MECHANICAL_TERMINAL_AUDIT_20260806 (31) · F3_P5_structural_closure_candidate (129) · design_inputs (37) · design_review (39) · parameter_registry (5).
`10_research\`: space_embodied_robotics (89) · research_questions (7) · theory_graph (5) · contribution_map (3) · research_os_01 (4) · research_os_02 (6) · comp_prot_03_a4_b5_0/_1/_1r1 (4) · mechanical_design_progress_gallery_20260729 (5).
All sha256-verified identical to source; untracked; sources untouched (see `SALVAGE_COPY_MANIFEST.md`).

## 3. Explicit gaps (stated, not invented)

1. **HIL** — NOT_STARTED; no directory, no closed-loop or replay runtime. Do not create one without an authorized wave.
2. **Dataset** — NOT_STARTED; no dataset registry/dir. Any future dataset lands under a new top-level dir only via CM decision.
3. **`08_REVIEWS\` empty** — independent-review records (LOOP-6 for SAFE-00/CTRL-01) are absent everywhere in ROOT A; review status stays PENDING_REVIEW.
4. **Mass budget authority** — system-level mass budget `UNSOURCED_BLOCKED`; panel mass placeholder 5–10× off (Yang-Heng TODO-3).
5. **`knowledge\` stale citations** — 2 files cite retired `F:\space_robotics_references\...` paths (doc hygiene, Stage 1 fix, REQUIRES HUMAN APPROVAL).
6. **Root-level junk** — `$out\` (empty) and `grep.exe.stackdump` (untracked) present; housekeeping deletion flagged REQUIRES HUMAN APPROVAL (not done by PL1-G).

## 4. Non-goals (explicit)

- No renumbering of `01/08/10/20/30/40/50/70/80`; no merge of `knowledge\` into `50_literature\`; no move of `structure\` into `20_engineering\`. Such changes would break existing SSOT path references (health check, PROJECT_LIBRARY_INDEX, frozen configs) for zero engineering gain.
