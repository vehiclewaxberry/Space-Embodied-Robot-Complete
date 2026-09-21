# VIZ-Gate 0 fresh-worktree portability verification

Verified at `2026-07-15 00:34 +08:00`.

## Scope

- Accepted tag remains `viz-gate0-accepted-20260714` -> `6c15395f444f693adad6ff0dfc9a3cfc0b4cf310`.
- `project_visualization_v0.html` was not edited or regenerated.
- Accepted v0 SHA-256 remains `1F66454100AFB0A66E31E042C52C6B2A570801B72217F8709A2B50CA225B3166`.

## Defects found after acceptance

1. A fresh Git worktree applied platform line-ending conversion to the mixed-line-ending E1.5 snapshot. The live acceptance worktree matched `22/22` hashes, but a new worktree initially matched only `12/22`. The broader VIZ freeze manifest initially matched `24/29`.
2. Ten B601 STL files referenced by `40_evidence/artifacts/visualization/tables/asset_audit.csv` were present in the acceptance worktree but were not tracked. A fresh worktree therefore failed `test_asset_units` at `base_link.STL`.

These were packaging/reproducibility defects, not changes to the accepted visualization content or science state.

## Corrections

- Commit `e765194` adds path-specific Git line-ending rules that reproduce the byte-level hashes recorded at acceptance.
- Commit `86d50d1` tracks only the ten B601 STL inputs explicitly named by the 45-row asset audit; all ten pre-commit file hashes matched the audit.
- No accepted tag was moved and no v0 artifact was overwritten.

## Independent fresh-worktree result

Detached checkout at `86d50d1`:

| Check | Result |
|---|---:|
| E1.5 frozen evidence snapshot hashes | `22/22` |
| VIZ-Gate 0 freeze-manifest hashes | `29/29` |
| Asset-audit paths present | `45/45` |
| VIZ automated acceptance suite | `6/6 PASS` |
| Replay keyframes | `44/44` |
| Embedded replay videos | `6/6` |

The follow-up commits make the already accepted VIZ-Gate 0 package reproducible from a clean checkout while preserving the original v0 bytes and scientific verdict.
