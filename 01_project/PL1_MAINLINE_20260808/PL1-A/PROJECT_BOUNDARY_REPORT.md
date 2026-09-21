# PROJECT_BOUNDARY_REPORT.md — PL1-A Project Root Discovery & Relevance Boundary

- **Date**: 2026-08-08
- **Agent**: PL1-A (task SEI-PL1-PROJECT-MAINLINE-RECONSTRUCTION)
- **Mode**: discovery was read-only; this reconciliation revision modifies only the three PL1-A output files. No project asset was moved, renamed, deleted, or altered; no git mutation was performed and `.git` was untouched.
- **Method**: full enumeration of F:\ top level (37 directories + 2 zip files); SSOT reading; light 1–2 level sampling; recursive physical-file/logical-byte measurements for key roots; `git rev-parse/log/status`; SHA-256 checks; health-check execution; PL1-G salvage-manifest reconciliation; CM3A archive/source hash comparison. Big unrelated roots were classified from name + 1-level listing only, per mandate.
- **Measurement snapshot**: 2026-08-08 19:36 +08:00, after all PL1 parallel writers stopped.

---

## 1. Verdict (questions the mandate must answer)

1. **Every F:\ root enumerated and classified — UNKNOWN = 0.** All 39 top-level entries (37 dirs + 2 files) carry a classification and a boundary decision. Full table: `PL1_PROJECT_ASSET_DISCOVERY.csv`.
2. **Current git HEAD of ROOT A = `5c5addea00ddb70d86a5cc37a88bbcda50350e43`, branch `publication/stage3-integrity-closure`** (verified via `git rev-parse`). This **matches the mission-expected 5c5adde**. Lineage confirmed in `git log`: `b75352c → e14b224 → cd0ea80 → 5849b72 → 5c5adde`.
3. **`PROJECT_START_HERE.md` and the controlling CM SSOT now agree on `publication/stage3-integrity-closure@5c5adde`.** Older commit IDs remain only as explicit history; details are in §6.
4. **Health-check path from START_HERE §11 exists and both copies agree**: `F:\_SEI_PROJECT_CONSOLIDATION_20260807\13_CM_CLOSURE\PROJECT_ROOT_HEALTH_CHECK.py` and `F:\SEI_PROJECT_ARCHIVE\CONFIGURATION_MANAGEMENT\20260807_CONSOLIDATION\PROJECT_ROOT_HEALTH_CHECK.py` are **byte-identical** (`diff` empty). Both produce the same result.
5. **Updated health-check result is `PROJECT_STORAGE_HEALTH = FAIL` with exactly one issue: `PRIMARY_CLEAN porcelain_entries=26`.** HEAD, ROOT A F3R1/F3R2, ROOT B=17,527, Archive=514, GHMIG retirement, and three bundles all pass (§5).
6. **Boundary is closed**: in-scope = 3 included roots + 5 temporary-compatibility roots + tool list; everything else is PROJECT_BOUNDARY_EXCLUDED with one-line reasons (`SEI_PROJECT_RELEVANCE_BOUNDARY.yaml`). Future agents must not re-scan excluded roots.

## 2. In-scope (the project boundary)

| Entry | Root | Role | Measured |
|---|---|---|---|
| **A** | `F:\China Graduate Future Flight Vehicle Innovation Competition` | A_PROJECT_ACTIVE (L0 unique engineering truth) | 29,655 files / 9,173,802,039 B / 8.543769 GiB |
| **B** | `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY` | B_PROJECT_REFERENCE (L2 unique reference library) | 17,527 physical files / 3,745,466,618 B / 3.488238 GiB |
| **ARCHIVE** | `F:\SEI_PROJECT_ARCHIVE` | C_PROJECT_HISTORY (L3 evidence + CM SSOT) | 514 files / 2,291,409,325 B / 2.134041 GiB |

Temporary-compatibility (in-boundary but transitional — do not delete yet):

- `F:\_SEI_PROJECT_CONSOLIDATION_20260807` — 22,035 files / 22,718,018,719 B / 21.157804 GiB. At 18:12–18:13, PL1-G copy-salvaged F3R1 (363), F3R2 (482), and 364 verified extras into ROOT A; source/destination SHA manifests are identical and the source is untouched. The acute F3R1/F3R2 single-copy risk is therefore closed. **Retirement remains blocked**, because the WT still contains a 3,432-file / 4,217,117,467 B CAD lineage plus an 880-file / 92,536,924 B stage3 closure set and other unchecked deltas.
- `F:\Robotic arm` — D_PROJECT_DONOR, 3,575 files / 3,172,529,957 B / 2.954649 GiB, 12 full-depth `.git` directories, runtime dependency = 0. CM3A accounts for 100%; final retirement still needs authorization.
- `F:\Space_Embodied_Robot_GITHUB_MIGRATION` — retired GHMIG skeleton, 339 files / 5,411,587 B, **0 `.git` dirs remain** (retirement receipted, see C6).
- `F:\codex-worktrees`, `F:\kb-worktrees` — E_PROJECT_TOOL, live git worktrees of ROOT A branches (DO_NOT_MOVE).

External tools with project runtime relevance (kept in place): `F:\ffmpeg-master-latest-win64-gpl-shared`, `F:\condaenvs` (envs `ddpg-sim`, `rebot`), plus generic caches/app-data (`condapkgs`, `pip-cache`, `Soildworks Data`, `Solidworks_plugin`, `Windows_profile`, `NVIDIA Corporation`, `claude*`, `codex_skill`, `matlab_mcp_test`).

## 3. PROJECT_BOUNDARY_EXCLUDED (never re-scan for SEI truth)

- `F:\Mechanical structure modeling and simulation` — `NON_SEI_GENERAL_CAE_LIBRARY`, 642 files / 130,787,610,910 B / 121.805455 GiB logical file sum. No filename hit for SEI/B601/F3/SAFE; register L4 says it is not competition truth. Keep independently and do not merge wholesale.
- `F:\CAE-Agent-Hub` (31,919 files, own .git) — standalone generic CAE-agent software project.
- `F:\spirit_ai_mechanical` (1,695 files) — non-SEI mechanical design data (slip-ring / dual-arm).
- `F:\VLA算法论文` (369 files) + `F:\VLA算法论文.zip` — separate VLA-literature notes project.
- `F:\Undergraduate_project` (2,436), `F:\Project` (225), `F:\vehicle_2dof_steering` (9), `F:\zoo-design-studio-projects_backup_20260513_115728` (3) — coursework/hobby projects.
- `F:\实习工作文档` (78,221), `F:\实习证明_聘用` (4) — personal internship/HR documents.
- `F:\BaiduNetdiskDownload`, `F:\download` (1,371) — personal download stores (installers, loose PDFs; loose papers are NOT project references).
- `F:\Wechat`, `F:\WeChat_Backup_20260722`, `F:\回忆_jinyi`, `F:\回忆_jingyi.zip` — personal data.
- `F:\$RECYCLE.BIN`, `F:\System Volume Information` — OS internals.

## 4. Git HEAD verification (ROOT A)

```
$ git rev-parse HEAD            → 5c5addea00ddb70d86a5cc37a88bbcda50350e43
$ git rev-parse --abbrev-ref HEAD → publication/stage3-integrity-closure
$ git log --oneline -5:
  5c5adde docs(CM3): add PROJECT_START_HERE entry doc (project library SSOT pointer)
  5849b72 feat(CM3): import B601 gripper/hardware vendor + fix broken external runtime ref
  cd0ea80 chore(reconcile): preserve verified pre-Wave4 active worktree assets
  e14b224 chore(consolidation): import verified Wave3 C1 assets and reference lineage
  b75352c docs(refs): V2 接触捕获阅读卡 x6 + INDEX 更新（23->29 卡）
```

- Actual HEAD **5c5adde = mission expectation** ✔; lineage chain ✔.
- At the final 19:36 snapshot, default `git status --porcelain` shows **26 entries**. `--untracked-files=all` shows **1,242 entries: 2 tracked modified** (`.claude/settings.json`, `PROJECT_START_HERE.md`) **+ 1,240 untracked files**. Most untracked files are the verified PL1 salvage and generated mainline maps, but until governance decides tracking/disposition, `PRIMARY_CLEAN` is a real operational HOLD.
- Branch map note: local `main` = `0a6df16` ("Add stage 1 spacecraft layout library"), an ancestor of HEAD; the development baseline lives on `publication/stage3-integrity-closure`. Multiple `wave1/*`, `kb/*`, `codex/*`, `consolidation/*`, `reconciliation/*` worktree branches exist (consistent with codex-worktrees/kb-worktrees).

## 5. Health-check result (updated copies identical; archive copy rerun after reconciliation)

```
PROJECT_STORAGE_HEALTH = FAIL (1 issue(s))
  [FAIL] PRIMARY_CLEAN           porcelain_entries=26                      ← only current operational HOLD
  [PASS] PRIMARY_HEAD            expected=5c5addea00dd got=5c5addea00dd
  [PASS] F3R1_EXISTS/COUNT/MECH_REVIEW   363 / c065ce17…
  [PASS] F3R2_EXISTS/COUNT/BASELINE      482 / 19d85e9c…
  [PASS] REFERENCE_LIBRARY       files=17,527
  [PASS] ARCHIVE                 files=514 (`F:\SEI_PROJECT_ARCHIVE`)
  [PASS] GHMIG_GIT_RETIREMENT   git_dirs=0 receipt=True
  [PASS] BUNDLES                 found=3
```

The health-check update now validates the ROOT A accepted URDF plus salvaged F3R1/F3R2, current ROOT B and Archive totals, CM3 GHMIG retirement, deleted roots, and three bundles. The archive and temp `13_CM_CLOSURE` copies are byte-identical at SHA-256 `464EF3113DD82E6F540A3AFDDAA82EB953FDE4529E53B6972544A048B806E7CD`. **Only the dirty/untracked working tree remains a health HOLD.**

## 6. NEW_CONTRADICTION list (measured reality vs docs; nothing silently overwritten)

- **C1 — CLOSED.** ROOT A entry and controlling CM files now consistently identify `publication/stage3-integrity-closure@5c5adde`; older commit IDs remain only in the explicit history chain.
- **C2 — CLOSED.** `ASSET_AUTHORITY_MATRIX.csv` now identifies `publication/stage3-integrity-closure@5c5adde` as `GIT_ACTIVE_HISTORY` and labels `main@0a6df16` historical.
- **C3 — CLOSED except for the real dirty HOLD.** Both health-check copies were updated and are byte-identical. They now expect HEAD `5c5adde`, validate ROOT A F3R1/F3R2, check current Archive=514, accept receipted GHMIG `.git=0`, and find three bundles. Current result is FAIL 1 solely because `PRIMARY_CLEAN porcelain_entries=26`.
- **C4 — CLOSED.** `PROJECT_START_HERE.md`, `PROJECT_LIBRARY_INDEX.yaml` and `ASSET_AUTHORITY_MATRIX.csv` all identify ROOT A `20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf`; raw/normalized hashes match and there is no scientific-truth fork.
- **C5 — F3R1/F3R2 single-copy risk CLOSED by 18:12 salvage; governance retirement remains blocked.** PL1-G copied F3R1 363 files, F3R2 482 files, and 364 verified extras into their documented ROOT A paths. Source/destination SHA manifests are identical; sources remain untouched and destinations remain git-untracked. The remaining retirement HOLD is the WT 3,432-file CAD lineage, the 880-file stage3 closure set, and other unchecked deltas—not F3R1 absence.
- **C6 — CLOSED at registration level.** CM register/matrix now record **0 `.git`, 339 files, 5,411,587 B** and the CM3-C receipt；health passes `GHMIG_GIT_RETIREMENT`. Only final skeleton deletion remains unauthorized.
- **C7 — CLOSED: CM3A ruling is archived.** Six CM3A files, including `B601_GRIPPER_SUBSYSTEM_IDENTITY_RULING.md` and `ROBOTIC_ARM_ASSET_CLASSIFICATION.csv`, now reside at `F:\SEI_PROJECT_ARCHIVE\CONFIGURATION_MANAGEMENT\20260807_CONSOLIDATION\CM3\CM3A\`; all six SHA-256 values match their temporary-source counterparts. The temporary copy is no longer unique.
- **C8 — Controlling pointer CLOSED; temp comparison remains open.** `CANONICAL_ROOT_REGISTER.yaml` and health now use stable `F:\SEI_PROJECT_ARCHIVE` 514. Temp `12_WAVE4\ARCHIVE` 477 still needs a semantic-superset audit before temp retirement.
- **C9 — CLOSED.** `PROJECT_START_HERE.md`, CM SSOT and health all record **514**: GIT 3 + RECOVERY 200 + MIGRATION 142 + DESIGN 100 + INTEGRATION 34 + CM 34 + manifest 1.
- **C10 — Working tree HOLD expanded during PL1.** At the final snapshot, default porcelain=26 and `-uall`=1,242 (2 tracked modified + 1,240 untracked). Most new files are deliberate verified salvage/maps, but they are not yet under a closed tracking/disposition decision.
- **C11 — Reference physical-count semantics changed.** The reconciled external union remains 17,523 artifacts; ROOT B now has four project-generated root indexes, so the physical total is 17,527. This is an additive index change, not reference drift.

**Truth uniqueness remains intact**: accepted URDF copies are hash-identical, the F3R1/F3R2 salvage is hash-identical to its untouched source, and one mass ledger remains authoritative. Current HOLDs are operational/governance: dirty-untracked ROOT A, `F3R2=PENDING_HUMAN_REVIEW`, and blocked retirement of the still-unreconciled governance deltas. They are not competing truth forks.

## 7. SSOT set — read and cross-checked

All four read in full from `F:\SEI_PROJECT_ARCHIVE\CONFIGURATION_MANAGEMENT\20260807_CONSOLIDATION\`: `PROJECT_LIBRARY_INDEX.yaml`, `CANONICAL_ROOT_REGISTER.yaml`, `ASSET_AUTHORITY_MATRIX.csv`, and `PROJECT_STORAGE_ARCHITECTURE.md`. `PROJECT_LIBRARY_INDEX.yaml` exists only in Archive; the register, matrix, storage architecture, and health-check each also have a byte-identical mirror under `_SEI_PROJECT_CONSOLIDATION_20260807\13_CM_CLOSURE\`. CM3A's six-file ruling/diff/receipt set is now archived under `CM3\CM3A\` and hash-identical to its temp source. Where older configuration disagrees with measured reality, §6 records the contradiction instead of silently rewriting history.

## 8. UNKNOWN statement

**UNKNOWN = 0.** All 39 F:\ top-level entries are classified (A×1, B×2, C×5, D×3, E×2, F×9, G×13, H×7 — counts include second-level rows in the CSV; every top-level root has exactly one primary classification). Nothing required deep-scanning beyond mandate limits; excluded roots were classified from name + 1-level listing + (where cheap) measured file counts, which is sufficient for a boundary decision. Items that could not be *fully* verified internally (e.g. contents of personal archives) are irrelevant to the boundary and are marked UNVERIFIED-by-design in the CSV notes rather than UNKNOWN.

## 9. Hand-off notes for PL1-G (consolidation planner)

1. Preserve the synchronized current Git fields at `5c5adde`; treat older commit IDs only as explicit history.
2. Preserve the now-updated, byte-identical health-check copies; once ROOT A tracking/disposition closes, rerun them to clear the sole `PRIMARY_CLEAN` failure.
3. Preserve the 18:12 salvage and decide how its 1,209 untracked files enter configuration management. Before any governance-root retirement, fully reconcile the 3,432-file WT CAD lineage, 880-file stage3 closure set, and remaining WT deltas.
4. Preserve the now-synchronized accepted-URDF pointer `20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf` and its dual hashes.
5. Decide final disposition of the 5,411,587-byte GHMIG skeleton and the 3,575-file Robotic-arm donor root under explicit authorization.
6. Resolve the ROOT A dirty state, then refresh the live A/B/Archive byte totals and rerun CSV/YAML validation plus the updated health check.
