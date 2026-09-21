# B601 rigid-link operational collision proxy candidate V1

This append-only package closes one local part of the current M01 critical path: it turns the six accepted B601 rigid-link screening surfaces into deterministic, STEP-first, conservative collision proxy candidates.

It does **not** modify the accepted B601 URDF, Mechanical Release R2, the 150-object system registry, the 11,175-pair universe, the three M01 stage instances, any clearance row, any pair oracle, any continuous edge, or MuJoCo V1.

The maximum local claim is:

`B601_RIGID_LINK_OPERATIONAL_COLLISION_PROXY_CANDIDATE_6_OF_6_GEOMETRY_PASS__SYSTEM_REGISTRY_PAIR_EDGE_PATH_AND_RELEASE_HOLD`

The gripper remains excluded because its two prismatic runtime state values and physical actuation/contact timing are separate HOLDs. `base_link` remains owned by the existing V2 proxy and is not duplicated here.

## Reproduction order

1. Generate the six primary STEP files with the CAD skill `scripts/step`, one wrapper per link.
2. Run `02_builder/build_package.py --emit` to create canonical NPZ/STL assets, per-link receipts, the overlay, and aggregate evidence.
3. Run `04_validation/independent_validate.py --write`.
4. Run `04_validation/run_negative_controls.py --write`.
5. Run `02_builder/finalize_package.py --write`.
6. Run pytest, CAD `inspect refs`, and one mandatory snapshot per primary STEP.

