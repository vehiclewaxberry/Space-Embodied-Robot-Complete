# MISSING_ROOT_FORENSICS_20260829

三个消失根的裁决与证据(完整 JSON 见同目录 06 附档字段)。

## GHMIG_SKELETON -> VERIFIED_RETIRED

- ARCHIVE/FILE_GOVERNANCE_20260808/GHMIG_RETIREMENT/deletion_receipt.json
- GHMIG_RETIREMENT/retirement_report.md: GHMIG_SAFE_TO_DELETE, deletion executed+verified 2026-08-08T14:56:49Z
- unique_project_files=0 after rescue-archival of 2 unique files into MIGRATION_EVIDENCE/GHMIG_GITATTRIBUTES_20260808/ (sha matched)
- CM3/GHMIG_FINAL_RETIREMENT_RECEIPT.md in ARCHIVE/CONFIGURATION_MANAGEMENT/20260807_CONSOLIDATION/

## TEMP_CONSOLIDATION -> MISSING_WITH_UNIQUE_CONTENT_RISK

- 22,035-file inventory + per-file classification archived (stage1_classification.tsv / stage5_stats.json)
- disposition: already_in_root_A 12,488 (8.51GB, A-lineage 1,496/1,523 hash-equal), already_in_root_C 485, duplicate 3,419, temporary 1,580, unique_history_only 4,063 (490.9MB)
- PL1-G salvage 08-08 18:12: F3R1(363)+F3R2(482)+15 unique dirs(364)=1,209 files copied into ROOT A, SHA all-equal; servicer_6U_v0 / robot_mount_adapter_v0 verified present
- 3 git bundles verified dual-copy equal in ARCHIVE (SEI_PRE_CONSOLIDATION / wave3 / wave4)
- RISK: no GHMIG-style deletion receipt found; 08-08 ruling was CONSOLIDATION_RETIREMENT_BLOCKED (F3R2 gate !=PASS, no external backup, 97% lineage uncommitted, 11 v0 CAD DIFFERENT_VERSION unarchived); 4,063 unique_history_only lack per-file landing receipts
- **行动**: run full hash reconciliation of the 4,063 unique_history_only list against ROOT A + ARCHIVE (inputs: consolidation_inventory.tsv + stage5a_relpath_lists.json in ARCHIVE); promote to VERIFIED_MIGRATED only after 100% landing proof

## KB_WORKTREES -> MISSING_BUT_FULLY_RECOVERABLE

- branch kb/track-a and kb/track-b still present in repo refs (git branch -a)
- worktree registration remains (gitdir broken); directory absent
- recovery: git worktree add <path> kb/track-a (or prune stale registration); no unique content risk

