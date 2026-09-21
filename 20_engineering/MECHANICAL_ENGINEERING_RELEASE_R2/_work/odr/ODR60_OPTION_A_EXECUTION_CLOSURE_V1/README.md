# ODR-60 Option A execution-closure candidate

This directory records the Owner's Option-A branch selection and closes only the
static bindings that can be derived without inventing physical state or clearance
data.

## What is closed

- Owner authority is recognized only from the fenced execution block immediately after
  the exact heading `# 十一、直接交给 Claude Code/Fable5 的执行提示词`, whose raw first
  non-empty line is the Option-A token and whose block contains neither Option B nor
  HOLD.  Quoted, recommended, non-first-line, and unrelated-fence token occurrences do
  not authorize anything.
- `ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK` is explicitly **not** authorized.  It remains a
  fresh, named-run-only request if immediately measured available physical memory is
  below 6 GiB.
- The physical spacecraft-to-accepted-B601 `base_link` execution mount has one
  canonical 12-decimal spelling, cross-checked against two Unified-R2 ledgers and the
  M3R physical stack (`208.0 mm`, `25.000014 deg`).  D6 and MPI-bridge reapplication
  are forbidden for collision execution.
- Ten A-category collision assets have an auditable asset-coordinate to accepted-URDF
  frame ledger.  Each row cross-checks the registry-selected asset, actual file hash,
  M5 carrier-frame/asset authority, accepted-URDF tree, WP11 applicability, and (for
  fingers) the accepted-URDF prismatic law against the M5 motion contract.  This is a
  **frame relationship ledger**, not a system collision PASS:
  only the `base_link` V2 proxy is an operational narrow-phase asset; the other nine
  remain design/screening candidates or state-dependent gripper assets.
- M01 is represented by three different schemas:
  `PRE_RELEASE_CONSTANT_SCENE`, `RELEASE_EVENT_SCENE`, and
  `POST_RELEASE_CONSTANT_SCENE`.  No object state is guessed; zero of three scene
  instances and zero of nine legacy required values are bound.
- The legacy V1 preflight file remains immutable.  Its duplicate
  `next_stage_authorized` and `release_credit` keys are superseded for machine
  consumption by the strict JSON `ODR60_OPTION_A_PREFLIGHT_GATE_V2.json`; the repair
  earns no scientific credit.

## What remains HOLD

- complete operational narrow-phase geometry for the system;
- per-stage scene instances and reissued object/pair universes;
- 11,166 numeric clearance-policy rows;
- 150 hash-bound object-motion certificates;
- 11,166 pair-oracle results;
- all continuous-edge certificates;
- a named-run runtime memory admission.

Consequently geometry loading/querying, pair evaluation, edge certification, and path
search are all unauthorized and were not executed by this package.

The main machine Gate is fixed at
`results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json`.  Its top-level native Boolean
fields are intended for strict joint-Gate aggregation.

`ODR60_OPTION_A_SOURCE_HASH_MANIFEST_V1.csv` binds all 22 upstream inputs, including
the external Owner attachment.  `ODR60_OPTION_A_EXECUTION_CLOSURE_PACKAGE_SHA256_V1.csv`
covers every local package file except itself.

## Rebuild and test

```powershell
python -B 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/build_execution_closure.py --repo-root .
python -B -m pytest -p no:cacheprovider 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/test_execution_closure.py -q
```

The package manifest intentionally excludes itself to avoid a recursive hash.

## CAD/URDF handling note

This work changes no STEP, mesh, CAD source, accepted URDF, or generated URDF.  It only
adds binding metadata and gates.  Therefore no CAD snapshot or CAD Viewer handoff is
applicable.
