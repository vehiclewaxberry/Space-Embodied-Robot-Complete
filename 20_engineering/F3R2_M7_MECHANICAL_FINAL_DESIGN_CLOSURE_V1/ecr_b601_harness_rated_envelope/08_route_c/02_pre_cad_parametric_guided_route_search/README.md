# Route-C C1.5 pre-CAD predicate qualification and parameter-space freeze

This package closes only the qualification contract needed before a physical
Route-C parametric search can be trusted.  It does **not** create a Route-C
route, guide, carrier, CAD model, manufacturing coordinate, product selection,
full-range result, mission result or release.

## Machine verdict

`UNKNOWN_FAIL_CLOSED__PREDICATE_QUALIFICATION_AND_PARAMETER_SPACE_FROZEN__PHYSICAL_GUIDE_VOLUMES_CAD_BRANCH_ODR42_MPI_VENDOR_MISSION_AND_RELEASE_HOLD`

Route-B remains `REJECTED`.  Its V2 hard negative results are retained exactly:

- worst clearance: `-11.9938 mm`;
- minimum bend radius: `0.1 mm`;
- worst pinch margin: `-11.9902 mm`.

The pure-standard-library kernel qualifies signed-distance, registry-scoped
guide/clamp/connector contact, failure serialization, curve
continuity/failure injection and monotonic feasible-set semantics using
synthetic analytic evidence. Its hardened 3-D segment-distance test covers
skew-frame intersections, collinear overlap and nonadjacent endpoint touch.
An analytic circular-arc claim must also pass common-plane, common-center and
common-radius checks, so a helix or a labelled piecewise-linear corner cannot
masquerade as C2 evidence. Circular-arc samples must also unwrap in one strict
direction with nonzero sub-π increments and a sweep below one revolution.
Scene comparisons cannot override scene `state` or `q`: a unique sample
registry is crossed exactly with the unique object registry, and every
comparison contains only `sample_id` and `object_id`. Omitted or duplicate
sample–object pairs fail closed. A passing test suite grants no engineering
authority.

## Null physical frontier

Until HN-02, HN-03, named finite guide/clamp/connector volumes and a separately
authorized physical Route-C CAD branch exist, all of the following remain
`null`:

- `D_max_geometry_mm`;
- `R_path_min_mm`;
- `deltaL_mm`;
- `carrier_travel_mm`;
- manufacturing coordinates.

Bundle OD and vendor minimum bend radius are scan axes only.  Their selected
values and uncertainties remain `null`.

The complete parameter mapping is code-bound by one canonical SHA-256 plus
separate hashes for top-level metadata, topology records, global axes, the
J1–J6/J4 variable schema, unknown physical inputs and search-output rules.
Names, units, ranges, records, required keys, nulls and forbidden shortcuts are
therefore checked as one exact contract, not inferred from summary booleans.

## Retained holds

ODR-42 is `PENDING`, MPI is `0/8 CONTROLLED`, and the existing Route-C CAD entry
gate remains `HOLD`.  Full-range, mission, vendor, mass/CG/inertia, restoring
torque, production dynamics, physical-contact RL, hardware and flight release
all remain held.  Accepted-URDF joint ranges may not be reduced to manufacture a
PASS; J4 side-bypass and guided-loop are separate mutually exclusive branches.

## Reproduction

From the repository root, run with Python bytecode disabled:

```powershell
python -B 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/02_pre_cad_parametric_guided_route_search/99_tools/build_route_c_precad_parametric_search.py --check-only --summary
python -B 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/02_pre_cad_parametric_guided_route_search/99_tools/validate_route_c_precad_parametric_search.py --check-only
```

`--check-only` performs an exact UTF-8 byte comparison. The validator is a
cross-entrypoint consistency check and also contains an independently written
recursive audit of parameter physical-null fields; it is not represented as a
second independent geometric implementation. It reruns deep-copy fail-closed
mutations and verifies that no `__pycache__`, CAD, mesh or URDF output exists in
this package.

The current hardened qualification suite contains 11 positive controls and 36
predicate negative controls. The Gate classifier separately exercises 48
deep-copy bypass controls, including duplicate/missing source bindings,
authority uplift, MPI/CAD state uplift, physical-value injection and accepted
URDF range reduction. Seven additional source-parameter negative controls inject
a selected OD, uncertainty, J1/J4 physical values, carrier hard stops and a
search-output capacity value. Every injection must be detected recursively,
must make the in-memory frontier and Gate fail closed, and must leave all
derived physical capacity measurands `null`. Twelve canonical-contract controls
separately mutate topology records, axis/variable names, units, bounds and
required keys.

The authority record also pins the semantics, parameter file, kernel, builder
and validator by local SHA-256. The manifest in turn binds the authority record.
This is explicitly `LOCAL_HASH_BOUND_REPRODUCIBILITY_AND_SELF_CONSISTENCY` with
no external trust anchor; it detects package drift but is not described as
external preregistration, immutability or an independent geometric
implementation.
