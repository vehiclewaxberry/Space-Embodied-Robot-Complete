# ODR-60 Option A — Fixed Platform Operational-Collision Candidate V1

This append-only work package converts the already available fixed-platform design geometry into three auditable, STEP-first, spacecraft-frame (`S`) local collision candidates:

- `F::LOAD_BRIDGE` — source is already authored in `S`; no offline placement is allowed.
- `F::M3R_STAGE_A` — source is `M3R_LOCAL`; apply the current precert `T_S_M3R_LOCAL` exactly once.
- `F::M3R_STAGE_B` — source is `M3R_LOCAL`; apply the same current precert transform exactly once.

The package contract is in `00_contract/`. Primary geometry belongs in `01_cad/`; metre-based runtime sidecars belong in `02_runtime/`; production builders, independent validators, results, tests, and review images belong in their corresponding package-local directories.

Maximum legal claim:

> Three local, source-bound `S`-frame STEP-first operational-collision candidates may pass independent geometry validation while remaining pending Owner and system binding. They grant zero system pair-query, SAFE, edge, path, parent-Gate, next-stage, or release credit.

Current system truth is preserved: 150 object rows, 1 asset-level operational object, 0/11,166 pair queries, 0 SAFE certificates, 0 certified edges, 0/3 bound stage instances, no authorized path search, and no release.

As-built uncertainty is unknown (`null`, `MEASUREMENT_PENDING`) for all three objects and must never be zero-filled. No frozen/current source file may be modified, and no dormant upstream builder may be executed.
