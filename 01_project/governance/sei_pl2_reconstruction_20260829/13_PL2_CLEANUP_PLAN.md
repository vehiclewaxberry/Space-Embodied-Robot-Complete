# PL2 CLEANUP PLAN (READ_ONLY_RECONSTRUCTION COMPLETE — NO MUTATION)

> 2026-08-29 · 所有动作均未执行;三个 Plan 互斥,必须先完成 Consolidation 对拍(P0)与比赛提交,再由 Owner 授权其中**一个**。

## P0 — Consolidation unique-file reconciliation(法证补全,先于任何清理)

- 输入:`F:\SEI_PROJECT_ARCHIVE\FILE_GOVERNANCE_20260808\CONSOLIDATION_RETIREMENT\_work\consolidation_inventory.tsv` + `stage5a_relpath_lists.json`
- 动作:对 4,063 个 `unique_history_only` 与 11 个 `DIFFERENT_VERSION` 文件,在 ROOT A 与 ARCHIVE 中做逐文件 SHA-256 对拍
- 产出:`PL2_CONSOLIDATION_RECONCILIATION.json`(landed / missing / diff 三表)
- 0 missing 后才能把 TEMP_CONSOLIDATION 升级为 `VERIFIED_MIGRATED`

## PLAN A — ARCHIVE_SUPERSEDED_CURRENT_VIEW(主线清洁)

| 项 | 文件 | 字节 | 风险 |
|---|---:|---:|---|
| 根级 V5R 残留 py/md/ps1 + 3 个中文总结 md | ~14 | ~0.1 MB | 低(有 V5R 目录内证据) |
| B51R1_PHASE1_START_PACKAGE(.zip+目录) | 4 | ~0 | 低 |
| PROJECT_CURRENT_STATUS / MECHANICAL_START_HERE / TRUTH_HIERARCHY | 3 | ~0 | 低 |
| structure/ + knowledge/ + PROJECT_ONBOARDING_PACKAGE/ | ~23 | ~0 | 低 |
| CURRENT_R2 V2–V7 delta/ledger/gap 历史增量 | ~30 | ~0.5 MB | 无(append-only,被 V8 引用为 pin) |
| CAD 谱系(B5_*/V2_*)退出 CURRENT 视图 | ~3,432 | ~4.2 GB | 仅归档索引,不删 |
| 诊断包 sim_14/15、e16–e20、Round3 ROM | 待清单 | — | 仅归档索引 |

- 回滚:90_archive 与源同盘,移动即回滚
- token:`PL2_ARCHIVE:<plan-sha256>`

## PLAN B — RETIRE_SAFE_WORKTREES_AND_EXTERNAL_REFERENCES

| 项 | 文件 | 字节 | 风险 |
|---|---:|---:|---|
| 14 个 codex worktree(11 clean + 3 dirty;分支全部仍可达) | 7,552 | 1.01 GiB | 低中;dirty 3 个需先审 untracked |
| 2 个 prunable 注册(路径已消失) | 0 | 0 | 无 |
| kb-worktrees 陈旧注册 | 0 | 0 | 无 |
| 80_third_party → Root B 迁移 | 20,351 | 4.83 GiB | 中;reBot-DevArm 为硬件供体、chrono 为 ROOT B 缺失的唯一 clean clone,迁移前须在 B 建立 pin 副本 |
| ROOT A 只留 pin(upstream/commit/license/manifest) | — | — | — |

- 回滚:worktree 由分支重建;Root B 保留原文件
- token:`PL2_WORKTREE_RETIRE:<plan-sha256>` + `PL2_MOVE_ROOT_B:<plan-sha256>`

## PLAN C — RETIRE_REBUILDABLE_HEAVY_OUTPUTS

| 项 | 文件 | 字节 | 风险 |
|---|---:|---:|---|
| R5 runs parquet(0.63 GiB/335 文件) | 335 | 0.63 GiB | 中;需 reproduction contract 逐 run 核验(gate+config+脚本+hash 齐备才放行) |
| .npz / 其他 solver 中间物 | 126 | 0.02 GiB | 同上 |
| 本轮认证可重建:0 项 | 0 | 0 | — |

- token:`PL2_REBUILDABLE_RETIRE:<plan-sha256>`

## 授权纪律

- PL2 无权覆盖 PL1 quarantine(硬删 >=2026-09-15,仍需 PL1 token)
- 三个 Plan 不一次性执行;每 Plan 独立 manifest + SHA + receipt
