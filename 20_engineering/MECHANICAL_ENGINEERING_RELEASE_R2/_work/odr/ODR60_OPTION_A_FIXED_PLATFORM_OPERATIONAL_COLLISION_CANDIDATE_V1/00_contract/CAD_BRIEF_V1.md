# CAD Brief — Fixed Platform Operational-Collision Candidates V1

## Purpose and maximum claim

Create exactly three local, hash-bound, STEP-first collision candidates for `F::LOAD_BRIDGE`, `F::M3R_STAGE_A`, and `F::M3R_STAGE_B`. All primary outputs are stored in spacecraft frame `S` with millimetre coordinates. This package may prove local geometric readiness only. It may not promote the current 150-object system registry, execute any of the 11,166 pair queries, issue SAFE/UNSAFE/contact results, certify an edge or path, bind an Owner scene, or obtain release credit.

## Primary outputs

| Registry object | Primary STEP output | Source frame | Required operation |
|---|---|---|---|
| `F::LOAD_BRIDGE` | `01_cad/F_LOAD_BRIDGE_S_V1.step` | `S` | Identity; copy/re-emit only after direct reopen. Never apply `T_S_M3R_LOCAL`. |
| `F::M3R_STAGE_A` | `01_cad/F_M3R_STAGE_A_S_V1.step` | `M3R_LOCAL` | Apply the pinned `T_S_M3R_LOCAL` exactly once. |
| `F::M3R_STAGE_B` | `01_cad/F_M3R_STAGE_B_S_V1.step` | `M3R_LOCAL` | Apply the pinned `T_S_M3R_LOCAL` exactly once. |

The matrix maps child coordinates into parent coordinates; columns are child axes expressed in the parent:

```text
T_S_M3R_LOCAL (translation in mm)
[[ 0.000000000000,  0.000000000000, 1.000000000000, 208.000000000],
 [ 0.422618483193,  0.906307683772, 0.000000000000,   0.015994151],
 [-0.906307683772,  0.422618483193, 0.000000000000,  -0.086366070],
 [ 0.000000000000,  0.000000000000, 0.000000000000,   1.000000000]]
```

## Source discipline

- Reopen each pinned source STEP directly and independently verify its SHA-256 and byte count before any geometry operation.
- Do not run, patch, or import a dormant upstream builder. Do not modify frozen/current assets.
- The load-bridge STEP is already authored in `S`; its verified reopened bbox is `[185.25, -104.982394538, -105.084754759, 196.0, 105.01438284, 104.912022619]` mm and its volume is `260072.391934165 mm^3`.
- M3R Stage A and B source STEP files are in `M3R_LOCAL`. Their expected source volumes are respectively `127784.800333 mm^3` and `161966.032228 mm^3`. Each source and each output must reopen as exactly one valid, closed, strictly positive-volume solid.
- Preserve topology and volume. No fuse, hull, envelope, filler, healing that changes identity, mesh-to-BRep substitution, or invented hardware is allowed.

## Runtime sidecars

Derive `.ply`, `.npz`, and `.stl` sidecars only from the independently validated `S`-frame STEP outputs. Convert millimetres to metres exactly once with scale `0.001`; retain identity placement in `S`. Sidecars are secondary runtime artifacts and never replace STEP authority.

## Mandatory validation

1. Recheck every source pin in `SOURCE_AUTHORITY_LOCK_V1.json` fail-closed.
2. Independently reopen all three source STEP files and all three emitted STEP files.
3. Prove load-bridge identity in `S`; a non-identity or M3R transform is a hard failure.
4. Prove each M3R output equals exactly one application of the pinned transform. Zero or two applications are hard failures.
5. Verify solid count, validity, closure, finite positive volume, rigid-volume preservation, frame, and unit semantics.
6. Reopen every runtime sidecar and verify bounds equal STEP bounds scaled by `0.001` exactly once within declared numeric tolerances.
7. Produce at least one reviewed CAD snapshot for each primary STEP and record the review; use the CAD viewer handoff if available.
8. Run independent validation without importing the production builder, fresh-process determinism, a mutation/negative-control suite, and package manifest/inventory checks.

## Fail-closed boundary

Any missing/mismatched pin, missing output, invalid/open/non-positive solid, wrong frame, wrong transform count, wrong scale count, unbound as-built value, missing independent reopen, or attempted authority-counter promotion makes the local Gate fail. As-built uncertainty remains `null` / `MEASUREMENT_PENDING`; zero filling is forbidden.

Even a fully passing local Gate must retain: Owner review, operational system binding, all system pair queries, SAFE certificates, continuous-edge certificates, path search, parent Gate credit, and release credit.
