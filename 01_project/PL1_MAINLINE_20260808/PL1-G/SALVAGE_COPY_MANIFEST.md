# SALVAGE_COPY_MANIFEST.md — PL1-G copy-only salvage (Task 1)

- **Date**: 2026-08-08
- **Agent**: PL1-G (task SEI-PL1-PROJECT-MAINLINE-RECONSTRUCTION, consolidation planner)
- **Operation class**: COPY-ONLY. No move, no delete, no rename, no git mutation (`git add`/`commit` NOT performed; copies are untracked in ROOT A). **Source trees were not touched in any way.**
- **Trigger**: TOP RISK from PL1 recon — the entire native mechanical lineage existed ONLY in the pending-retirement governance temp area `F:\_SEI_PROJECT_CONSOLIDATION_20260807\12_WAVE4\WORKTREE_RECONCILIATION\` (WT), absent from ROOT A, never git-tracked, no cold backup.

## 1. What was copied, where

Destination ROOT A = `F:\China Graduate Future Flight Vehicle Innovation Competition`. All destinations are the canonical documented residences (WT mirror layout = repo-relative layout).

| # | Source (WT, untouched) | Destination (ROOT A, new untracked copy) | Files | Size |
|---|---|---|---|---|
| 1 | `12_WAVE4\WORKTREE_RECONCILIATION\20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\` | `20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\` | **363** | 890 MB |
| 2 | `…\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\` | `20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\` | **482** | 738 MB |
| 3 | `…\20_engineering\F3_MECHANICAL_TERMINAL_AUDIT_20260806\` | `20_engineering\F3_MECHANICAL_TERMINAL_AUDIT_20260806\` | 31 | 424 KB |
| 4 | `…\20_engineering\F3_P5_structural_closure_candidate\` | `20_engineering\F3_P5_structural_closure_candidate\` | 129 | 679 KB |
| 5 | `…\20_engineering\design_inputs\` | `20_engineering\design_inputs\` | 37 | 408 KB |
| 6 | `…\20_engineering\design_review\` | `20_engineering\design_review\` | 39 | 253 KB |
| 7 | `…\20_engineering\parameter_registry\` | `20_engineering\parameter_registry\` | 5 | 28 KB |
| 8 | `…\10_research\space_embodied_robotics\` | `10_research\space_embodied_robotics\` | 89 | 860 KB |
| 9 | `…\10_research\research_questions\` | `10_research\research_questions\` | 7 | 44 KB |
| 10 | `…\10_research\theory_graph\` | `10_research\theory_graph\` | 5 | 44 KB |
| 11 | `…\10_research\contribution_map\` | `10_research\contribution_map\` | 3 | 17 KB |
| 12 | `…\10_research\research_os_01\` | `10_research\research_os_01\` | 4 | 24 KB |
| 13 | `…\10_research\research_os_02\` | `10_research\research_os_02\` | 6 | 52 KB |
| 14 | `…\10_research\comp_prot_03_a4_b5_0_b601_space_manipulator_engineering_cad\` | `10_research\comp_prot_03_a4_b5_0_…\` | 1 | 8 KB |
| 15 | `…\10_research\comp_prot_03_a4_b5_1_b601_interface_closure_articulation_stowage\` | `10_research\comp_prot_03_a4_b5_1_…\` | 1 | 8 KB |
| 16 | `…\10_research\comp_prot_03_a4_b5_1r1_b601_canonical_interface_native_articulation_rework\` | `10_research\comp_prot_03_a4_b5_1r1_…\` | 2 | 20 KB |
| 17 | `…\10_research\mechanical_design_progress_gallery_20260729\` | `10_research\mechanical_design_progress_gallery_20260729\` | 5 | 394 KB |

**Totals: 1,209 files, ≈1.63 GB** (F3R1 363 + F3R2 482 + extras 364). Well under the 5 GB stop threshold.

Selection rule (per mandate "list them, but only copy what you can verify"): rows 1–2 were pre-authorized; rows 3–17 were each **verified** (a) absent from ROOT A at HEAD `5c5adde` (file-system + PL1-E git-history check), (b) sole copies inside the pending-retirement area, (c) small and hash-verifiable, (d) referenced as current/canonical by in-repo docs (PL1-E HOLD-2 cluster, PL1-B lineage, PL1-F NC-1) — i.e. their restoration repairs documented structure rather than inventing new content.

## 2. Verification (copy-verify protocol)

Per-file sha256 manifests generated for source AND destination, then diffed:

| Tree | Source lines | Dest lines | Manifest diff | Manifest files (this dir, `manifests\`) |
|---|---|---|---|---|
| F3R1 | 363 | 363 | **IDENTICAL** | `F3R1_source.sha256` / `F3R1_dest.sha256` |
| F3R2 | 482 | 482 | **IDENTICAL** | `F3R2_source.sha256` / `F3R2_dest.sha256` |
| Extras (15 dirs, path-prefixed) | 364 | 364 | **IDENTICAL** | `EXTRAS_source.sha256` / `EXTRAS_dest.sha256` |

Spot-check against CM-registered frozen hashes (independent of the copy manifests):

- `20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\03_native_cad\F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM` → sha256 `19d85e9c703bec107396ae84dab7b12de5722434fc7d5474b3a5a144a1b590d0` — **matches** the registered baseline hash (`19D85E9C…B590D0`, byte-identical to F3R1 V3_CONFIGURED).
- `20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\05_clearance\F3R1_MECH_REVIEW.json` → sha256 `c065ce17964d6fb5421d3b012937567c178b4b52c6f83eb2a368daabfd121c50` — **matches** the health-check-registered mech-review hash (`c065ce17…`).

## 3. Checked but NOT copied (with reasons)

| Item (WT) | Why not copied |
|---|---|
| `20_engineering\cad\` full lineage (V0_1→V2_3, B5_0→B5_1R1; 3,432 files / 4.0 GB) | Would push this operation to ≈5.6 GB, over the ~5 GB stop threshold; historical lineage whose authority content is already extracted into F3R1/F3R2 donor copies + `SEI_PROJECT_ARCHIVE` registers. **At-risk, plan-only**: scheduled for phase-1 audit + its own CM wave with hash re-verification before any WT retirement (see TWO_ROOT_EXECUTION_PLAN.md Stage 4 precondition). |
| `…\cad\B5_1R1_B601_interface_native_rework_candidate\00_BASELINE\AUTHORITIES\accepted_urdf\arm_b601_v1.urdf` (the "CM-canonical copy") | Re-hashed by PL1-G 2026-08-08: raw sha256 `1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164` — **byte-identical** to the ROOT A in-repo authority `20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf`. Carries zero unique information; the stale *documented* path is fixed by doc updates (PROJECT_START_HERE.md §4), not by re-creating a second copy. |
| `20_engineering\config\`, `stage1_spacecraft_layout\`, `system_design\` (WT versions) | WT copies are **older** pre-Wave4 snapshots; ROOT A holds the current git-tracked versions (diff-verified 2026-08-08). Old versions recoverable from ROOT A git history. Not unique-at-risk. |
| `10_research\stage3_p1_p2_p3_closure\` (880 files / 91 MB) | Absent from ROOT A, but uniqueness vs `SEI_PROJECT_ARCHIVE` DESIGN_LINEAGE not established at index depth. Listed for phase-1 audit; not verified enough to copy under the mandate. |
| WT `01_project\` (47 MB), `30_simulation\` (31 MB), `40_evidence\` (31 MB), `50_literature\`, `70_tools\`, `80_third_party\`, `knowledge\`, `structure\`, `B51R1_PHASE1_START_PACKAGE\`, `PROJECT_ONBOARDING*` | Older snapshots of trees whose current versions live in ROOT A git; uniqueness unverified at index depth. Phase-1 full diff audit before any retirement decision (TWO_ROOT_EXECUTION_PLAN.md Stage 4). |

## 4. Statements

1. **Source untouched**: all WT source trees remain in place, unmodified (copy-only protocol; source file counts re-measured post-copy still 363/482/…).
2. **Retirement remains forbidden**: `F:\_SEI_PROJECT_CONSOLIDATION_20260807` retirement stays **blocked** until human disposition — this salvage removes the acute single-point-of-failure for rows 1–17 only; items in §3 (esp. the 4.0 GB cad lineage) still exist solely there.
3. **No git tracking**: the salvaged trees are intentionally untracked in ROOT A (binary CAD is git-unfriendly; F3R1/F3R2 were never git-tracked). Git-integration policy is a human/CM decision (TWO_ROOT_EXECUTION_PLAN.md Stage 2/3).
4. **Authority unchanged**: salvaged files are evidence/engineering carriers; their gate statuses (F3R2 `PENDING_HUMAN_REVIEW` etc.) are unaffected by the copy. No closed gate, hash, or history was overwritten.
