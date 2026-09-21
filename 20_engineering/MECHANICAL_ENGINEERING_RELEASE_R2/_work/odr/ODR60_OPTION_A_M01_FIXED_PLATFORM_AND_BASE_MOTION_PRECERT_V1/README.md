# ODR60 Option A — M01 fixed-platform pose and base-motion precertificate V1

## Purpose and maximum claim

This append-only package closes one deliberately narrow piece of the M01
mechanical-admission evidence chain without inventing Owner values or creating a
new whole-spacecraft CAD model:

- bind the existing `F::LOAD_BRIDGE`, `F::M3R_STAGE_A`, and
  `F::M3R_STAGE_B` placements at **design level only**;
- prove, over the full accepted six-joint domain and every state admitted by
  the still-uninstantiated M01 V2 scene schema, that the registered
  `A::base_link` collision proxy is stationary;
- issue exactly one system object-motion certificate (`1/150`) while retaining
  every scene, pair, edge, path, next-stage, and release hold.

The package does **not** promote any fixed-platform candidate to operational
collision authority. It does not execute a geometry-pair query. It does not
claim a system collision pass.

## Coordinate and placement rulings

All matrices transform child coordinates into parent coordinates; matrix
columns are child axes expressed in the parent.

- `F::LOAD_BRIDGE`: the candidate STEP reopens with coordinates already in
  spacecraft frame `S` (`x = 185.25…196.0 mm`). Therefore its runtime
  asset-to-`S` transform is identity. `T_S_LOAD_BRIDGE_LOCAL` is a design datum
  only and must never be applied again to this STEP.
- `F::M3R_STAGE_A/B`: each STEP is stored in `M3R_LOCAL`; its assembly-local
  placement is identity, followed once by the full-precision frozen
  `T_S_M3R_LOCAL` matrix.
- `A::base_link`: the operational proxy is stored in `base_link`, has identity
  collision registration, and consumes the full-precision physical execution
  mount in metres. The dynamics bridge is hash-pinned but is not reapplied in
  the collision scene.

## Why the base motion coefficient is exactly zero

Independent XML parsing establishes that `base_link` is the unique accepted
URDF root and is never the child of a joint. The registered proxy is rigid and
identity in that root. The spacecraft execution mount is constant, and no V2
scene-schema field acts on `base_link`. Thus, for every accepted joint vector
`q` and every schema-admissible scene state `s`, the same registered set is
obtained, giving:

```text
global_L_mm_per_rad = [0, 0, 0, 0, 0, 0]
```

The 15 boundary/midpoint evaluations are deterministic corroboration. The
domain proof is structural and does not depend on finite sampling.

The proxy radius is independently recomputed from the NPZ vertices and the
receipt's tight STEP/BRep bounding box. It is derivation evidence only and is
not a clearance debit.

## Pair-derating null policy

The following motion-contract fields are present but deliberately remain
`null`:

- `centerline_hausdorff_bound_mm`
- `radius_uncertainty_bound_mm`
- `model_uncertainty_bound_mm`
- `numeric_uncertainty_bound_mm`

They belong to later pair-oracle representation/numeric derating and are not
needed to prove that the registered base set does not move. Replacing an
unknown with `0` is a rejected negative control. Consequently the certificate
is `pair_eligible=false`.

## Retained counts and holds

```text
authoritative scene values       0 / 30
scene instances                  0 / 3
fixed-platform design poses      3 / 3
asset-level operational objects  1 / 150  (unchanged: A::base_link only)
system object-motion certs        1 / 150  (new narrow credit)
clearance policy rows             0 / 11166
pair queries                      0 / 11166
continuous edges                 0
path search                      false
next stage                       false
release credit                   false
```

The V9F signed Route-C penetration witness remains a historical negative
control with every current system-pair binding `null`. Its signed clearance is
never copied into the unsigned system-oracle separation field.

## Artifacts

- `M01_FIXED_PLATFORM_POSE_BINDING_V1.json` — three design-level placement
  bindings and explicit non-promotion flags.
- `INDEPENDENT_BASE_LINK_ZERO_MOTION_RECOMPUTE_V1.json` — URDF graph, joint
  limits, transform, NPZ bbox, STEP/BRep radius, and full-domain proof.
- `A_BASE_LINK_GLOBAL_MOTION_CERTIFICATE_V1.json` — the only new system motion
  authority (`1/150`), explicitly pair-ineligible.
- `ROUTE_C_NEGATIVE_WITNESS_QUARANTINE_V1.json` — current-binding null ledger
  for the legacy V9F witness.
- `M01_FIXED_PLATFORM_AND_BASE_MOTION_NEGATIVE_CONTROLS_V1.json` — 24-row
  builder-side pre-emission diagnostic structure. Its authority explicitly
  says `NOT_GATE_EVIDENCE`; G30 does not count or trust its rejection flags.
- `M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_GATE_V1.json` — append-only
  machine Gate; it does not reissue any parent Gate.
- `M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_SHA256_V1.csv` — self-excluded
  package manifest.

## Deterministic reproduction and validation

From the repository root:

```powershell
python -B 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_V1/build_m01_fixed_platform_and_base_motion_precert.py --check --repo-root .
python -B 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_V1/validate_m01_fixed_platform_and_base_motion_precert.py --repo-root .
python -B 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_V1/validate_m01_fixed_platform_and_base_motion_precert.py --negative-controls --repo-root .
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -q -p no:cacheprovider 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_V1/test_m01_fixed_platform_and_base_motion_precert.py
```

The validator is deliberately standalone: it never imports, executes, or
introspects the builder and carries its own 28-source lock and contract
expectations. All six released JSON artifacts have exact top-level-key
allowlists. Certificate claim/proof/review fields and Gate claim/review/HOLD
fields are frozen value-for-value. Counts require exact integer types and
continuous quantities reject Boolean masquerades. It strictly rejects
duplicate JSON/YAML keys and JSON
`NaN`/`Infinity`, independently recomputes the URDF root and six limits, mount
and registration, NPZ bbox/radius, parent 0/30 + 0/3 + 0/11166 truth,
certificate input-binding/replay hashes, permissions and counts. The manifest
must be an exact, unique, self-excluded list with no extra package files.
`__pycache__` and `.pytest_cache` are forbidden even though the builder omits
them from its manifest scan; therefore validation/tests must use `-B` and the
pytest cache provider must remain disabled.

The validator only checks that the 24-row builder diagnostic is structurally
present and demoted. It independently replays all 24 mutation categories with
exact expected rejection codes, then executes additional escape tests: 66
fresh in-memory mutations in total, without using receipt outcomes. These cover the
registry-with-rehash, replay-L-with-rehash and bbox-NaN escape attempts; source
and local pins; manifest duplicate/extra/hash mutations; strict parser
duplicate/NaN/Infinity inputs; six top-level allowlists; every frozen
certificate/Gate field with downstream Gate-pin or manifest-row rehash;
Boolean-as-number attacks; cache directories; and scene/pair/edge/path/authority promotions.
The `--negative-controls` envelope reports the canonical SHA-256 of this fresh
receipt so it can be cited without turning it into validator input authority.

Use `--write` instead of `--check` only to deterministically regenerate the
package after an intentional, reviewed source-pin update.

## CAD/URDF workflow note

No CAD or URDF geometry was created or edited. Existing STEP/NPZ/URDF assets
were hash-pinned and inspected read-only. Therefore CAD snapshot generation and
CAD Viewer handoff are not applicable to this package; no visible geometry
changed.
