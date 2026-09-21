# TWO_ROOT_EXECUTION_PLAN.md — PL1-G (Task 2.5)

- **Date**: 2026-08-08 · **Mode**: Stage 0 plus the explicitly listed low-risk copy/index/SSOT corrections have been executed under the PL1 consolidation task; all CAD writes, destructive retirement and remaining dependency-island moves are still PLAN ONLY and require scope-specific approval.
- **Roots**: ROOT A `F:\China Graduate Future Flight Vehicle Innovation Competition` · ROOT B `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY` · ARCHIVE (bound to A) `F:\SEI_PROJECT_ARCHIVE` · retirement candidates: `F:\_SEI_PROJECT_CONSOLIDATION_20260807`, `F:\Space_Embodied_Robot_GITHUB_MIGRATION`, `F:\Robotic arm` (HOLD).

## Copy-verify protocol (mandatory for every move/copy in Stages 1–4)

`source → staging → sha256 manifest → semantic verification (parse/spot-check; for CAD: count + key-file hashes vs register; for git bundles: git bundle verify + test clone) → copy to destination → sha256 manifest diff must be IDENTICAL → path/pointer updates (single approved change set) → runtime validation (health check / affected loaders) → provenance entry (what/when/manifest hashes) → source becomes retirement candidate only after soaking + explicit human authorization.`

Never move-delete in one step; never skip semantic verification; never retire a source in the same wave as its copy.

## Stage 0 — recon + acute salvage (DONE 2026-08-08)

- PL1-A..F read-only reconstruction complete (boundary closed UNKNOWN=0; mechanical/dynamics/intelligence/CAD-donor mainlines rebuilt; reference library mapped).
- **PL1-G salvage executed**: F3R1 (363 files) + F3R2 (482 files) + 15 verified-unique support dirs (364 files) copied from the pending-retirement temp area into ROOT A canonical residences; per-file sha256 manifests IDENTICAL; key frozen hashes re-verified (F3R2 baseline `19D85E9C…B590D0`; F3R1 mech-review `c065ce17…`). Source untouched. See `SALVAGE_COPY_MANIFEST.md`.
- **Supplemental contract chain executed**: `20_engineering/config/competition_prototype` (6) + `30_simulation/module_cards` (9) copied from the same verified worktree into ROOT A; 15/15 files and 58,711 B are SHA-identical, source untouched. This repairs document links only and grants no implementation/execution authority. See `SUPPLEMENTAL_CONTRACT_CHAIN_COPY_MANIFEST.md`.
- **CM3A identity island executed**: six gripper identity/ruling files copied from temp CM3A into stable Archive `.../CM3/CM3A`; 6/6 SHA-identical, source retained. See `CM3A_ARCHIVE_COPY_MANIFEST.md`.
- PL1-G deliverables + SSOT entry docs written/updated (see `PL1_INDEX.md`).
- **Effect**: TOP RISK (sole residence of native mechanical lineage in a to-be-retired area) is defused for the F3R1/F3R2 line. Residual single-residence items remain (see Stage 4 preconditions).

## Stage 1 — low-risk index & stale-doc fixes

1. **ROOT B index overlay install — DONE**: entry doc + three registers installed at ROOT B root; source/register copies are hash-synchronized. Remaining library-governance item: update the older `REFERENCE_INDEX.json` oresat license entry to CERN-OHL-S-v2.
2. **Health-check pin update — DONE**: stable Archive CM copy and `13_CM_CLOSURE` mirror now check HEAD `5c5adde`, stable Archive, ROOT A accepted URDF/F3R1/F3R2, F3R2 top hash and CM3-C GHMIG receipt; the two scripts are byte-identical. Structural checks pass; overall remains `FAIL 1` only because the worktree is dirty.
3. **CM SSOT correction — DONE for controlling files**: `CANONICAL_ROOT_REGISTER.yaml`, `ASSET_AUTHORITY_MATRIX.csv`, `PROJECT_STORAGE_ARCHITECTURE.md`, `PROJECT_LIBRARY_INDEX.yaml` and both health-script copies now use the measured PL1 state. Remaining doc hygiene: `knowledge/B_assets_and_conventions.md`, `B_cubesat_structure_practice.md` retired-path citations and `30_simulation/README.md:19` e15/e16 wording; these do not own current authority.
4. **Housekeeping** — delete `$out\` (empty) + `grep.exe.stackdump`; commit or revert `.claude/settings.json`. **REQUIRES HUMAN APPROVAL**.
5. **sim_05 parser path repair** — `30_simulation/sim_05_free_floating_arm/b601_model.py:39` one-line fix (`cad/...` → `20_engineering/cad/...`) unblocks fresh reproduction of sim_05/09/11 + CTRL-01/02 chain; frozen evidence unaffected. **REQUIRES HUMAN APPROVAL** (touches frozen sim behavior → governance).

## Stage 2 — Robotic arm witness capture (pre-retirement; copy-verify protocol)

Per `PL1-F/ROBOTIC_ARM_RETIREMENT_PLAN.md` Stage 1–2 (witness capture is bounded, but the zero-arm CAD/BOM diff is not trivial):
1. `git bundle create` HPRA full history (2 commits, no remote) + zero-robotic-arm `research` branch; also capture its 26 porcelain entries as staged/unstaged diff, untracked `frame0_ZERO_ARM.SLDPRT`, status listing and SHA manifest → `F:\SEI_PROJECT_ARCHIVE\DESIGN_LINEAGE\ROBOTIC_ARM_WITNESS\` (new dir). **REQUIRES HUMAN APPROVAL** (archive write).
2. Copy 2 URDF variants (`065bc4f8…`, `667a8905…`), `memory/local-machine-env.md`, sim README → same witness dir; sha256 manifest.
3. Coverage re-verification per manifest (reBot-DevArm ↔ ROOT A, meshes ↔ ROOT A, full `external/spacecraft_layout_refs` ↔ ROOT A).
4. **DONE 2026-08-08** — ROOT B root registers now contain metadata pointers for external refs / SpaceRobotEnv / zero-robotic-arm MuJoCo teaching / reBotArmController_ROS2 (upstream URLs, commits and licenses); no external asset was physically copied.
5. Register gap fix: add `F:\Robotic arm` to `CANONICAL_ROOT_REGISTER.yaml` (PL1-F NC-2). **REQUIRES HUMAN APPROVAL**.

## Stage 3 — CAD dependency-island migrations (each its OWN GATE, copy-verify protocol)

1. **WT cad lineage** (`…\WORKTREE_RECONCILIATION\20_engineering\cad\`, 3,432 files / 4.0 GB: V0_1→V2_3, B5_0→B5_1R1) → ROOT A `20_engineering\cad\` evidence subtree or archive. Own CM wave; hash re-verification against `MIGRATION_SOURCE_REGISTER` (14 items raw+LF dual-hash). **REQUIRES HUMAN APPROVAL.**
2. **WT stage3_p1_p2_p3_closure** (880 files / 91 MB) → uniqueness audit vs `SEI_PROJECT_ARCHIVE`, then disposition (archive or drop). 
3. **reBot-DevArm backup** (DR P0): cold copy of `80_third_party\vendor\reBot-DevArm` (177 files) into archive or designated backup location; verify `87a0537d…` STEP hash.
4. **Vendor dedupe ruling** (EXUDYN/SPART/SpaceDyn/space_robotics_bench/astrobee exact duplicates ROOT A ↔ ROOT B; basilisk skew HOLD-2; chrono inversion HOLD-3): pick reference of record per repo; execute chosen side's retirement via copy-verify (content is upstream-reobtainable; risk LOW). **REQUIRES HUMAN APPROVAL.**
5. **15_CM3 gripper ruling — DONE**: six-file CM3A dependency island copied into stable Archive with source/destination hash equality; temp source retained.
6. Optional CAE small copies CAD-D10/D11 → ROOT B R4 (license-unknown → human license review first).

## Stage 4 — temp-area & donor retirement (only after Stages 1–3 complete + human disposition)

Preconditions (ALL must hold, verified by audit):
- F3R1/F3R2 + support dirs: in ROOT A, sha-verified (✔ Stage 0) **and** human-confirmed.
- cad lineage + stage3 closure: dispositioned (Stage 3.1/3.2).
- 13_CM_CLOSURE / 12_WAVE4\ARCHIVE: controlling CM files and health entry have been re-pointed/synchronized; the remaining 477-file legacy archive still requires a full superset audit before temp-root retirement (C8).
- Robotic arm: Stage 2 complete + 6 retirement criteria in PL1-F plan §4 all PASS + explicit human deletion authorization (RETENTION_AND_DELETION_POLICY highest-privilege flow; QUARANTINE first — recoverable move, then cold-reopen independent acceptance, then FINAL_DELETE_MANIFEST).
- GHMIG skeleton: final root deletion authorization per CM3-C receipt §5.
Only then: retire `F:\_SEI_PROJECT_CONSOLIDATION_20260807` (largest reclaimable root, 22 GB), GHMIG skeleton (6.9 MB), `F:\Robotic arm` — each as its own authorized action, never batched silently.

## Discipline inherited by all stages

- No git mutations by agents (add/commit/branch/tag) anywhere; ROOT A stays on `publication/stage3-integrity-closure`.
- NEVER modify mechanical CAD content; no F3R2 redesign inside consolidation stages.
- Closed gates/history are never silently overwritten — conflicts go to `NEW_CONTRADICTION_REGISTER.md`.
- Fail-closed: any ambiguity → HOLD, documented.
