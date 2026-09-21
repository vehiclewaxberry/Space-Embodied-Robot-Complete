# NEW_CONTRADICTION_REGISTER.md — PL1-G consolidated register (Task 2.6)

- **Date**: 2026-08-08 · **Rule**: measured reality stands; docs are flagged stale. Nothing was silently overwritten. Statuses: `open` / `proposed-fix` / `needs-human` / `resolved-2026-08-08` (by PL1-G salvage or doc update).
- Sources: PL1-A (C1–C10), PL1-B (NC-1..6), PL1-C (NC-01/02 + observations), PL1-D (HOLD-2/3 + license HOLDs + refinement), PL1-E (HOLD-1..3 + drift), PL1-F (NC-1/2), PL1-G (G-1..5, new).

## 1. Storage/CM contradictions (PL1-A)

| ID | Contradiction | Status | Disposition |
|---|---|---|---|
| C1 | Pre-PL1 HEAD triple-skew: CM files named `cd0ea80`/`5849b72`, measured `5c5adde` | **resolved-2026-08-08**: START_HERE、LIBRARY_INDEX、CANONICAL_ROOT_REGISTER、STORAGE_ARCHITECTURE 均指向 `5c5adde` | stable CM 与 compatibility mirror hash 同步 |
| C2 | ASSET_AUTHORITY_MATRIX 曾把 GIT_MAIN_HISTORY 写成 `main@cd0ea80`；实际 current 是 `publication/stage3-integrity-closure@5c5adde` | **resolved-2026-08-08** | matrix 已区分 current publication branch 与祖先 main |
| C3 | Pre-PL1 health script 的 HEAD/GHMIG/Archive/F3 pins 过时，曾产生 3 个结构性失败 | **resolved-2026-08-08** | 结构项全 PASS；当前只剩 `PRIMARY_CLEAN`，总结果 `FAIL 1`（见 C10） |
| C4 | Accepted-URDF documented path (`20_engineering/cad/B5_1R1_.../accepted_urdf/`) absent in ROOT A; content-verified copy at `cad\spacecraft_layout\arm_b601_v1\` | **resolved-2026-08-08** in entry docs and controlling CM SSOT；hash 不变 | — |
| C5 | Pre-salvage finding: F3R1 was declared in ROOT A but physically absent, with the only copy in the pending-retirement temp area | **resolved-2026-08-08** (PL1-G salvage: 363/363 sha-identical into `20_engineering\`) | residual: untracked + no cold backup → G-4 needs-human |
| C6 | GHMIG register entry was two states behind (23 .git/14.28 GB vs actual 0 .git/339 files/5,411,587 B) | **resolved-2026-08-08** in CM register/matrix | final skeleton deletion remains separately unauthorized |
| C7 | Gripper identity ruling曾仅位于 temp `15_CM3\AGENTS\CM3A\`，而 START_HERE 指向 Archive | **resolved-2026-08-08**: CM3A 6/6 copy-verified into stable Archive；source retained | full Robotic arm retirement remains separate HOLD |
| C8 | Two historical "L3 archive" locations remain: temp `12_WAVE4\ARCHIVE` 477 vs stable `SEI_PROJECT_ARCHIVE` 514（pre-CM3A 508 + CM3A 6） | open | Stage 4 precondition: prove stable Archive is the required semantic superset, then retire temp copy only with authorization |
| C9 | Archive count drift: entry曾写 507，pre-CM3A 实测 508；CM3A 6-file copy 后为 514 | **resolved-2026-08-08** (§8/CM SSOT/health 均为 514) | — |
| C10 | Working tree dirty（2 tracked modifications + PL1/salvage 等大量 untracked；实时数见 health） | open | needs-human：选择 stage/commit/revert/保留范围；不得由 PL1 自动提交 |

## 2. Mechanical contradictions (PL1-B)

| ID | Contradiction | Status | Disposition |
|---|---|---|---|
| NC-1 | START_HERE §3/§4 + archive matrix disagree on mechanical-line residence (docs → ROOT A; reality → WT) | **resolved-2026-08-08** (salvage + §3/§4 rewrite) | — |
| NC-2 | START_HERE §12 "next task F3R2" while F3R2 already executed 2026-08-07 (gate 11/14, PENDING_HUMAN_REVIEW) | **resolved-2026-08-08** (§12 now points to F3R2 residual P0) | — |
| NC-3 | Three F3R2 orderings exist (F3R1 review#2 / W3-F / F3R1 G3) | proposed-fix: adopt `PL1-B/F3R2_EXECUTION_ORDER.md` residual order (W3-F is the CM-cited one) | needs-human ratification |
| NC-4 | "F3R2 built the baseline" vs "F3R2 modelled nothing new" both true (baseline = V3 bytes renamed; definitions/poses/thread added) | documented (no action; wording discipline) | — |
| NC-5 | F3R2 gate OI-3 "gripper single solid" falsified ~8 h later by G33 (58 solids); gate JSON not updated | documented: downstream readers MUST use G33; frozen gate JSON not touched | needs-human (formal addendum if desired) |
| NC-6 | Pre-PL1 health 的结构 pins 与 dirty 混在同一 `FAIL 3` 叙事 | **resolved-2026-08-08** | pins 已修；当前唯一失败是 C10 `PRIMARY_CLEAN`，总结果 `FAIL 1` |

## 3. Dynamics/simulation contradictions (PL1-C)

| ID | Contradiction | Status | Disposition |
|---|---|---|---|
| NC-01 | CM SSOT accepted_urdf path dangling; same-hash file at spacecraft_layout (path drift, content identical — NO dual truth) | **resolved-2026-08-08** in entry docs and controlling CM SSOT | — |
| NC-02 | LIBRARY_INDEX claims F3R1 in `20_engineering\`; absent at HEAD (pre-salvage) | **resolved-2026-08-08** (salvage) | — |
| obs-03 | LIBRARY_INDEX git_head `5849b72` vs measured `5c5adde` (SSOT 1-commit lag) | **resolved-2026-08-08** | current field = `5c5addea...` |
| obs-04 | `30_simulation/README.md:19` says e15/e16 at repo root; actually inside `30_simulation\` | proposed-fix (Stage 1 doc hygiene) | needs-human (doc edit in frozen tree) |

## 4. Reference-library HOLDs (PL1-D)

| ID | Item | Status | Disposition |
|---|---|---|---|
| HOLD-2 | basilisk divergent duplicates: ROOT A vendor `6b9c222f` vs ROOT B recorded `27eb48a2` | open | needs-human: pick reference of record (Stage 3.4) |
| HOLD-3 | chrono inverted duplication: ROOT B clone empty; only real clone inside ROOT A vendor `24c78cf8` | open | needs-human (Stage 3.4) |
| LIC-HOLD ×8 | License UNKNOWN/no-LICENSE: SpaceDyn, space-ros, ANCF_beam, High_performance_robotics_arm, reBotArmController_ROS2, spacedyn_freefloating_demo, Pendulum-DDPG, REFLIB ingestion toolset. Chrono removed from this list after its clean ROOT A checkout verified BSD-3-Clause; HOLD-3 remains a location/index issue | open | needs-human (license review); rule in force: read methods only, copy nothing |
| refinement | oresat_structure license = CERN-OHL-S-v2 (REFERENCE_INDEX.json said UNKNOWN_LICENSE — directory-named LICENSE missed by scan) | proposed-fix (index entry update) | needs-human |

## 5. Intelligence/control HOLDs & drift (PL1-E)

| ID | Item | Status | Disposition |
|---|---|---|---|
| HOLD-1 | `sim_05_free_floating_arm\b601_model.py:39` URDF path broken at HEAD (pre-REORG04 `cad/`); B601Arm() FileNotFoundError verified; frozen gate evidence intact; fresh reproduction of sim_05/09/11 + CTRL-01/02 blocked | proposed-fix (one-line path repair) | **needs-human** (touches frozen sim behavior → governance) |
| HOLD-2 | `10_research\{space_embodied_robotics,research_questions,theory_graph,contribution_map,research_os_01,research_os_02}` + comp_prot dirs referenced-but-absent at HEAD, never in git history, sole copies in temp area | **resolved-2026-08-08** (PL1-G salvage restored all into ROOT A, sha-verified) | authority ratification needs-human (were never CM-ruled per-asset) |
| HOLD-3 | START_HERE advertised accepted_urdf formal path absent (= C4/NC-01) | **resolved-2026-08-08** | — |
| drift | Literature card count 29 (README/research_state_v4) vs 34 (`controller_state.yaml`, newer) | open (minor, non-blocking) | — |

## 6. Donor/retirement contradictions (PL1-F)

| ID | Contradiction | Status | Disposition |
|---|---|---|---|
| NC-1 | F3R1 KEEP_UNTIL_F3R2 asset living only in to-be-retired zone (= C5) | **resolved-2026-08-08** (salvage) | — |
| NC-2 | `F:\Robotic arm` absent from CANONICAL_ROOT_REGISTER (neither roots nor deleted_roots) though in LIBRARY_INDEX retired_roots + START_HERE §10 | **resolved-2026-08-08**: registered as `D_PROJECT_DONOR / RETIREMENT_CANDIDATE_HOLD` | witness/backup/retirement authorization still open |

## 7. New entries from PL1-G consolidation (2026-08-08)

| ID | Finding | Status | Disposition |
|---|---|---|---|
| G-1 | ROOT A root junk: `$out\` (empty dir) + `grep.exe.stackdump` (untracked) | proposed-fix (delete) | needs-human |
| G-2 | WT holds OLDER snapshots of current ROOT A trees (`config\`, `stage1_spacecraft_layout\`, `system_design\`, plus mirrored `01_project/30_simulation/40_evidence/...`) — diff-verified older; largely recoverable from git history | open | phase-1 full diff audit before any WT retirement (Stage 4 precondition) |
| G-3 | `10_research\stage3_p1_p2_p3_closure` (880 files/91 MB) unique status vs archive UNVERIFIED at index depth | open | phase-1 audit, then disposition (needs-human) |
| G-4 | Salvaged F3R1/F3R2 now in ROOT A but git-untracked with no cold backup (DR gap persists in new form); reBot-DevArm vendor likewise gitignored without backup (DR P0) | open | needs-human: git-integration policy + backup decision (Stage 3.3) |
| G-5 | `PL1_INDEX.md` did not exist | **resolved-2026-08-08** (created by PL1-G) | — |
| G-6 | embodied-agent contract linked six `competition_prototype` files and nine `module_cards` that were still temp-only after first salvage | **resolved-2026-08-08**: 15/15 SHA-identical copy into ROOT A；source retained | contract/support only；untracked/CM and execution authority remain HOLD |

## 8. Summary counts

- **resolved-2026-08-08**: C1–C7、C9、NC-1/2/6、NC-01/02、obs-03、HOLD-2/3(E)、NC-1/2(F)、G-5/6 — **20**
- **proposed-fix, needs-human approval**: obs-04、NC-3、oresat index refinement、HOLD-1(E)、G-1 — **5**
- **open / needs-human decision**: C8、C10、HOLD-2(D)、HOLD-3(D)、LIC-HOLD×8、E drift、G-2、G-3、G-4 — **9**
- **documented, no action**: NC-4, NC-5 — **2**
