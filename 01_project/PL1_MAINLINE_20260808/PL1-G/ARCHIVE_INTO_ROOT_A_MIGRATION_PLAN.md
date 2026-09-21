# ARCHIVE_INTO_ROOT_A_MIGRATION_PLAN.md — PL1-G (Task 2.4)

- **Date**: 2026-08-08 · **Status**: LOGICAL BINDING/POINTER LAYER ACTIVE；physical archive relocation remains PLAN ONLY（no Archive move/copy into ROOT A）。
- **Object**: `F:\SEI_PROJECT_ARCHIVE` (514 files / 2.134 GiB measured 2026-08-08 after CM3A copy: GIT_LINEAGE 3 + RECOVERY 200 + MIGRATION 142 + DESIGN_LINEAGE 100 + INTEGRATION 34 + CM 34 + W4_ARCHIVE_MANIFEST.json 1).
- **Binding decision**: the archive is **logically bound to ROOT A** (`ARCHIVE_BOUND_TO_A`). It is the L3 evidence + CM SSOT layer of the project; ROOT A entry docs already point at it.

## Why "bound", not "merge now"

1. The CM SSOT (`PROJECT_LIBRARY_INDEX.yaml`, `CANONICAL_ROOT_REGISTER.yaml`, `ASSET_AUTHORITY_MATRIX.csv`, `PROJECT_STORAGE_ARCHITECTURE.md`, `PROJECT_ROOT_HEALTH_CHECK.py`) lives at `F:\SEI_PROJECT_ARCHIVE\CONFIGURATION_MANAGEMENT\20260807_CONSOLIDATION\` and is referenced by absolute path from ROOT A docs (`PROJECT_START_HERE.md` header + §5 + §11) and governance scripts.
2. The archive holds the project's only git bundles (`GIT_LINEAGE\`, incl. `SEI_PRE_CONSOLIDATION_HISTORY.bundle` sha256 `16cebf6f…`, verify+fsck+clone tested) — it is part of disaster recovery. Physical relocation without a DR review would be reckless.
3. The archive is not git-tracked and contains 2.2 GB of binary evidence — importing it into ROOT A's git would be wrong; importing it as an untracked sibling inside ROOT A is possible but must be a deliberate CM decision.

## Phase 0 — index/pointer layer (NOW; done by PL1-G)

- `PROJECT_START_HERE.md` §8 now records **514 files**（pre-CM3A 508 + copy-verified CM3A 6）and is synchronized with CM SSOT/health. ✔ done 2026-08-08.
- This plan + `TWO_ROOT_CONSOLIDATION_MATRIX.csv` record the binding (`ARCHIVE_BOUND_TO_A`) formally.
- No physical change. No approval needed (doc-level).

## Phase 1 — path-dependency audit (next; REQUIRES HUMAN APPROVAL to action findings)

Inventory every live reference into the archive before any migration is contemplated:

1. **Entry docs**: `PROJECT_START_HERE.md` header/§5/§8/§11 pointers have been re-pointed to stable Archive, CM3A and current health; keep them in the future dependency inventory. ✔ current.
2. **Health check**: `PROJECT_ROOT_HEALTH_CHECK.py` has two byte-identical copies（stable Archive CM + `_SEI_PROJECT_CONSOLIDATION_20260807\13_CM_CLOSURE\`）and now validates ROOT A URDF/F3R1/F3R2 plus stable Archive=514. ✔ current; any future relocation must update both or retire the mirror explicitly.
3. **CM scripts/configs**: any script under `CONFIGURATION_MANAGEMENT\` that hard-codes `F:\SEI_PROJECT_ARCHIVE` or `F:\_SEI_PROJECT_CONSOLIDATION_20260807` paths.
4. **Git bundles**: confirm bundle integrity (`git bundle verify` + test clone) and record where bundle consumers expect them.
5. **`PROJECT_LIBRARY_INDEX.yaml` consumers**: grep ROOT A + archive for readers of the index; record the coupling.
6. Deliverable: a reference inventory table (path → consumer → breakage-if-moved). Output goes to `01_project\PL1_MAINLINE_20260808\` follow-up or a new CM wave.

## Phase 2 — optional physical migration (only if a human rules it worthwhile)

Candidate target: `F:\China Graduate Future Flight Vehicle Innovation Competition\90_archive\` (new dir; **untracked** — binary evidence does not belong in git) or leave in place permanently (a legitimate outcome — "bound" does not require co-location).

If approved, execute per the **copy-verify protocol** (same as TWO_ROOT_EXECUTION_PLAN.md):

1. `source → staging` copy; per-file sha256 manifest of source.
2. Semantic verification (spot-parse CM YAML/CSV; `git bundle verify` on all bundles; run the health check copy from staging).
3. `staging → destination` copy; per-file sha256 manifest; diff vs source manifest (must be IDENTICAL).
4. Path updates in entry docs + health check + index (single approved change set).
5. Runtime validation: re-run health check end-to-end; verify one bundle clone from the new location.
6. Provenance note appended to CM SSOT (what moved, when, manifest hashes).
7. Old location becomes a **retirement candidate** — deletion only after a soaking period + explicit human authorization. Never in the same wave as the move.

## Hard boundaries

- The archive copy of `PROJECT_ROOT_HEALTH_CHECK.py` is the reference copy (13_CM_CLOSURE is a byte-identical mirror; C8 register drift recorded).
- `15_CM3` gripper identity ruling (`B601_GRIPPER_SUBSYSTEM_IDENTITY_RULING.md`) should be copied **into** the archive CM3 dir (receipts live there already) before the temp area retires — that is a Stage 2/4 item in the execution plan, REQUIRES HUMAN APPROVAL.
- No archive content enters ROOT A git history (binary + evidence semantics). Ever.
