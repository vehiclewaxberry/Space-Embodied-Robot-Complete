# Route-C C9 analytic capsule candidate V1

This package emits deterministic local collision candidates for the nine logical
Route-C harness objects already enumerated by the frozen M01 registry.  It does
not edit that registry and does not execute pair, edge, path, TMG-4, G12, parent
Gate, next-stage, or release logic.

The source centerline is expressed in `A0 = B601 base_link at q=0`, in
millimetres.  Curved analytic primitives are divided at no more than 1.5 mm of
curve arc length.  Every emitted chord carries its own analytic Hausdorff upper
bound.  The design centerline-tube radius is the already-derated 10 mm design
diameter divided by two: exactly 5.0 mm.  The only legal narrowphase query
radius is the per-representation `effective_radius_mm = design_radius_mm +
hausdorff_bound_mm`.  Thus the chord encloses the analytic tube.  The 0.5 mm
nominal-to-design increment is already inside the 5.0 mm design radius and is
not added again; consumers must neither ignore the Hausdorff term nor debit it
a second time.  Either error is fail-closed.

The side-effect-free pose adapter parses the hash-pinned accepted URDF and the
current 12-decimal execution mount.  Ordinary sections use
`T_S_A0 T_A0_h(q) inv(T_A0_h(0))`.  J4 uses the frozen seven-section trombone
and annular-follower law.  J4 section 5 uses a fixed 139-chord topology at q=0
and every posed q4, selected from the accepted-URDF worst case q4=-1.87 rad;
its full-domain maximum dynamic arc-length step is 1.4992706602297674 mm.  J3
section 0--2 output both primary and alternate host representations; production
union acceptance remains `UNKNOWN` because no continuous q3 carrier law exists.

The reported current system state is not proved by this package's local
contract.  The independent validator and finalizer read four hash-pinned current
machine Gates: M01 registry, M01 scene/prebind, terminal release, and
mechanical-to-embodied handoff.  These external sources retain 1/150 operational
assets, 0/11166 pair queries, 0/3 stage instances, TMG-4 HOLD, G12 FAIL, and zero
pair/edge/path/release credit.

The superseded pre-repair Gate is preserved only as diagnostic lineage in
`07_reviews/C9_PRE_REPAIR_NOT_CLEAN_PASS_V1.json`; it carries zero credit.

## Reproduction

From the repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1/02_builder/build_c9_capsules.py --write
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1/02_builder/c9_pose_adapter.py --write-self-check
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1/04_validation/validate_c9_independent.py --write
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1/04_validation/verify_fresh_process_determinism.py --write
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1/04_validation/run_pytest_and_write_receipt.py --write
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1/04_validation/finalize_c9_gate.py --write
```

Use the same commands with `--check` for replay without changing the frozen
derived outputs.
