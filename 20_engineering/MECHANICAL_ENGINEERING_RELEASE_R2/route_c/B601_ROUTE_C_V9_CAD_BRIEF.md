# B601 Route‑C V9 CAD Brief

## Model and task

- Model: B601 Route‑C V9 passive guided dress-pack accessory assembly.
- Task type: source modification of the rejected V8 local subassembly; no change to the spacecraft, manipulator, gripper, solar-array, accepted URDF, joint limits or inertials.
- Owner authority: ODR‑58.
- Primary architecture: `SEGMENTED_CONSTRAINED_MOVING_CARRIER + LOW_PROFILE_DUAL_PLANE_SADDLE`.
- Units: millimetres for geometry; kilograms, metres and kg·m² at dynamics interfaces.
- Coordinate convention: A0 equals accepted B601 `base_link`; host-local placements are derived from the immutable URDF frame tree.

## Geometry intent

1. Retain the V8 J1 semi-captive R66 annular guide and physical relief retainers unless V9 evidence requires the single authorized same-architecture repair.
2. Retain the J2 controlled service loop and J3 physical host-boundary correction.
3. Replace the V8 J4/J5 full-bundle R55 free external standoff family with a passive segmented carrier and a low-profile dual-plane transfer:
   - Plane A carries the fixed/transport run.
   - Plane B carries the return/service bend and length storage.
   - The major bend and storage volume must sit outside the registered narrow link4 corridor.
   - Each host transition must be a physical clamp/carrier boundary with section index, cumulative cable arclength window, bore-axis predicate and explicit host.
4. No active drive or new robot degree of freedom is permitted. A slider or articulated carrier is mechanical accessory hardware only.
5. Every guide, saddle, carrier, bracket, clamp, strain relief and connector support is a closed positive-volume solid with material candidate, fastener interface, attachment datum, assembly path and inspection datum.

## Controlled physical inputs

- Installed bundle OD: 9.0 mm nominal; 10.0 mm upper design bound.
- Minimum dynamic bend radius: 50.0 mm from registry P06. The source-level build target remains at least 54.0 mm as a conservative design allocation, not a supplier rating.
- J3 carrier travel: 110.0 mm and E2.10-class 10×16 mm inner section remain controlled inputs unless the V9 physical topology explicitly supersedes them without changing their evidence authority.
- Clamp spacing: 55–150 mm, 120 mm nominal on long fixed runs, from P13.
- Bundle linear density: 65.0 g/m nominal, bounded 56.5–72.5 g/m, from P09.
- Guide friction coefficient: bounded 0.06–0.20; torsional restoring curve remains UNKNOWN and must not be zero-filled.
- Tracking/calibration/manufacturing/thermal margins are inherited from the current evaluator and must remain non-zero.

## Positioning and attachment

- Root/fixed references: frozen spacecraft/master geometry and accepted B601 donor meshes, all read-only.
- V9 hardware attaches only to removable derived brackets on the relevant B601 link host.
- Plane-A/Plane-B separation, carrier stroke and saddle height are named source parameters.
- Moving/fixed ownership is authored in the generator, not inferred by an evaluator allowlist.
- Interface exceptions require the same section, bounded cumulative arclength around a registered station, explicit clamp ID and bore-axis fit. Euclidean proximity alone is forbidden.

## Primary outputs

- `B601_ROUTE_C_BUILD_V9.py`
- `B601_ROUTE_C_GUIDED_DRESS_PACK_V9.FCStd`
- `B601_ROUTE_C_GUIDED_DRESS_PACK_V9.step`
- `ROUTE_C_PRODUCT_STRUCTURE_V9.yaml`
- `ROUTE_C_HARNESS_CENTERLINE_V9.json`
- `ROUTE_C_CLAMP_GUIDE_REGISTER_V9.csv`
- `ROUTE_C_MISSION_COVERAGE_GATE_V9.json`
- `ROUTE_C_ROBUST_MARGIN_LEDGER_V9.csv`
- `ROUTE_C_MASS_DELTA_BY_LINK_V9.yaml`
- `ROUTE_C_JOINT_TORQUE_ENVELOPE_V9.yaml`
- `ROUTE_C_LOCAL_STRUCTURAL_SCREEN_V9.json`
- `ROUTE_C_ASSEMBLY_MAINTENANCE_V9.md`
- `ROUTE_C_RED_TEAM_V9.json`
- `ROUTE_C_FALSIFIER_V9.json`

## Validation targets

- STEP/FCStd: valid closed solids; source and generated hashes recorded; frozen assets byte-identical.
- Early filter: 10 mandatory key states evaluated; zero UNSAFE; zero raw solid penetration; D2 pinch margin positive; D3 retention predicate true.
- Full mission: all eight mandatory trajectory segments evaluated; `mandatory_mission_unsafe=0`; RC hardware cross-clearance evaluated; `empty_comparison_set=0`; `unknown_auto_allow=0`.
- Bend: analytic and Menger minimum at or above the controlled dynamic limit; tangent discontinuity at generated section junctions ≤3°.
- Capacity: take-up, extension and carrier travel margins non-negative after thermal/tolerance derates.
- Mechanical accessory: local analytical load-path/fastener screen before any local FEA ECR.
- Mass: actual product-definition volume and bundle length propagated once through `mass_delta_by_link`; accepted B601 URDF inertials remain byte-identical.
- Visual review: four-view snapshot packet of the V9 STEP plus focused section/transparent views of the dual-plane J4/J5 transfer.

## Fail-closed assumptions

- V9 is a design candidate until every required machine Gate passes.
- A local predicate PASS is not a mission PASS.
- Unknown supplier torsional stiffness, TVAC suitability and flex-life remain declared qualification holds.
- Full hardware joint-range harness remains `DEFERRED_HOLD` unless independently demonstrated; the target is the mandatory mission-rated envelope.
