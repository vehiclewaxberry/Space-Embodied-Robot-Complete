# CAD brief — B601 `base_link` operational collision proxy V2

## Object and purpose

- Object: one link-local, STEP-first collision assembly for accepted B601 URDF link `base_link`.
- Purpose: remove the phantom desktop plate and replace only source geometry that cannot produce a complete, auditable collision mesh. This is a local collision-asset closure, not a B601 hardware redesign and not Route-C path-search authority.
- Primary output: `B601_BASE_LINK_OPERATIONAL_COLLISION_PROXY_V2.step`.
- Derived outputs: deterministic meter-unit NPZ/STL collision assets plus validation and source-binding receipts.

## Frozen inputs

- Filtered B50 B-Rep: `20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN/vendor_reference_linklocal/B50_REF_base_link_LINKLOCAL.step`, SHA-256 `A451B9150D00EC8E381AE69C0BB9D62B3A1FED1B1CD1AD373A719E28290F07C5`.
- Accepted link-frame correction: `D_base_link = [-0.05732750272995675,-0.03253727084589079,+0.05006764302725364] mm`, rotation identity, from WP11 authority SHA-256 `7463C1309C3530A42BB32CB4A661FFA56575691DFB7A4BE801AAE9094BEB51E1`.
- Purchased-component candidate: step.parts `DAMIAO DM-J4340P-2EC`, SHA-256 `F70211997AB35E20FE9E17376C351A5FBEC83732508B57A18CB64A73D257894E`. It is a candidate geometry source only until the registration gate passes; the local donor identifies `DM-J4340P` but does not independently prove the `2EC` suffix.
- Historical V1 HOLD diagnostic remains immutable and is not overwritten.

## Geometry policy

- Preserve every source B-Rep solid whose topology and complete triangulation are independently valid.
- Remove only traversal solids `58`, `59`, and `68` (zero-based): the two local `DM-J4340P:3` solids and the thin base plate with five non-triangulating faces.
- Prefer the catalog DM-J4340P-2EC assembly for detailed motor geometry only if its B-Rep, meshing, link-frame registration, outer envelope, and mating-interface checks pass.
- Regardless of catalog-detail acceptance, the operational collision surface must be conservative with respect to the tolerance-aware local source envelope. Add explicit analytic guards where the detailed candidate is smaller or variant identity remains unproven.
- Replace the affected base plate by the smallest reproducible analytic prism justified by the tolerance-aware source bounds. Holes and recesses may be filled for collision safety; no protrusion may be omitted.
- The raw accepted-URDF `base_link.STL` containing the phantom desktop plate is forbidden as geometry input and may appear only as a hash-inequality sentinel.

## Frame and placement

- Model axis convention: accepted URDF `base_link`, right-handed, millimetres in STEP.
- Bake only the frozen WP11 `D_base_link` translation into the proxy. Do not bake spacecraft mount transform `T_SM`, mission pose, joint state, or Route-C dress-pack geometry.
- Keep collision proxy semantics separate from mass/inertia; no accepted URDF inertial is changed.

## Validation gates

- All source and catalog bytes/hashes match their receipts.
- Reopened STEP has positive-volume solids only; every solid passes BRepCheck.
- Every non-zero-area face triangulates; each derived per-solid mesh is closed, consistently oriented, and free of duplicate/degenerate triangles.
- Local-source containment is proved against tolerance-aware B-Rep bounds for every substituted region; no sampled-only claim may be labelled exact containment.
- Quantify substituted-region volume inflation and aggregate proxy inflation. Conservative inflation is allowed but must be reported, never hidden as exact hardware geometry.
- Final STEP bbox remains within the frozen B50 operational envelope after `D_base_link`; deleted desktop-plate exclusive regions remain clear.
- Fresh-process deterministic replay reproduces all derived collision bytes and hashes.
- Variant or interface mismatch, empty comparison set, unknown frame/unit, missing receipt, or raw-URDF mesh use fails closed.

## Claim limit

Passing V2 may establish only `base_link` operational collision geometry. It does not evaluate any of the 11,166 unassessed system pairs, does not authorize path search, does not close Route-C/TMG-4/G12, and grants no mechanical release credit by itself.
