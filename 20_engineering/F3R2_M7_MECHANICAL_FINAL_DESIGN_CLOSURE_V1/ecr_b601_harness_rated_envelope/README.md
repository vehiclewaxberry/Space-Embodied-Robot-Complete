# B601 Harness-Rated Envelope Terminal Closure

This is the isolated implementation package for ODR-35 through ODR-41.  It
does not edit the accepted B601 URDF, does not reopen Solar Array R2, and does
not overwrite the historical full-range negative result or the historical
11/11 handoff gate.

The release logic is fail-closed:

1. Preserve `E_HW` from the accepted URDF.
2. Evaluate the fixed external dress candidate with the exact geometry kernel.
3. Derive `E_HRN` as a coupled viability set; maps and boxes are advisory.
4. Evaluate the complete, authority-tagged mission set `E_MISSION` along every
   trajectory, not only at endpoints.
5. Release only `E_OP = E_HW intersect E_HRN intersect E_MISSION` when all
   binding gates pass.  Any mandatory UNSAFE or UNKNOWN case rejects Route B
   and triggers Route C.

The work package is allowed to produce a negative result.  A negative result
is a completed engineering decision when it is hash-bound, reproducible and
does not delete the failing mission case.

## Current machine decision (2026-08-23)

- Exact coupled map: 75 samples = 0 SAFE / 75 UNSAFE / 0 UNKNOWN.
- Mandatory key-state probe: 0 SAFE / 11 UNSAFE / 0 UNKNOWN.
- Mandatory mission set: 10/10 key states UNSAFE; all eight trajectory segments also lack released
  continuous trajectory authority.
- Mechanical-to-embodied handoff V2: 11/12; G12 is the sole failed check.
- Terminal decision: ROUTE_B REJECTED, ROUTE_C TRIGGERED,
  `next_stage_authorized=false`.
- Accepted B601 URDF SHA-256 remains
  `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`.

Primary truth files:

- `07_release/B601_HARNESS_TERMINAL_GATE_V1.json`
- `07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json`
- `07_release/B601_HARNESS_TERMINAL_INDEPENDENT_VALIDATION_V1.json`
- `04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json`
- `03_envelope/B601_HARNESS_RATED_ENVELOPE_V1.yaml`
- `08_route_c/ECR_HARNESS_FULL_RANGE_01.yaml`

## Authorization-front continuation (2026-08-23)

The Route-C trigger has now been converted into a bounded, hash-closed
authorization-front package without creating geometry or changing the accepted
URDF/Solar R2 assets:

- `08_route_c/ROUTE_C_OWNER_DECISION_REQUEST_ODR42_V1.yaml` is an approval
  request, not an authorization record.
- `08_route_c/ROUTE_C_PRELIMINARY_DESIGN_CONTRACT_V1.json`, the concept trade,
  CAD brief and verification matrix define the proposed guided dress-pack loop.
- `08_route_c/ROUTE_C_CAD_ENTRY_GATE_V1.json` remains `HOLD`; detailed-design
  start is blocked by Owner authorization and minimum product/interface inputs.
  The eight trajectories and final mass/restoring-load evidence are downstream
  release conditions, not circular preconditions to initial CAD work.
- `09_downstream_rebind/SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json`
  preserves the historical Sim13 kinematic bootstrap but invalidates its use as
  current production/contact/RL mechanical authority.
- `10_loop_integration/MECHANICAL_LOOP_ENGINEERING_STAGE_GATE_V1.json` preserves
  the first integrated pre-CAD ruling.
- `08_route_c/01_minimum_product_inputs/` now contains the traceable product
  input audit and four-route supplier RFI shortlist.  The research packages
  validate at 51/51 + 4/4 negative controls and 53/53 + 15/15 negative controls,
  respectively, but MPI-01..MPI-08 remain 0/8 controlled, no product is
  selected, and RC-CEG-03 remains HOLD.
- `30_simulation/e17_b601_mission_trajectory_candidates/` provides five
  deterministic arm-only numeric seeds, one symbolic contact scaffold and two
  intentionally uninstantiated segments.  Its independent validation is 42/42
  with 10/10 negative controls; mission release remains 0/8.
- `11_loop_continuation/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V1.json`
  is the preserved first continuation entry point.  It binds the RFI and e17
  evidence while preserving ODR-42, CAD, product-selection, mission, dynamics,
  contact, RL, hardware-motion and flight holds.
- `12_loop_continuation_v2/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V2.json`
  is the preserved second continuation entry point.  It additionally binds the corrected
  gripper velocity-unit semantics, the e18 isolated non-release numeric input
  branches and the Route-C MPI evidence audit.  The e18 validator closes 69/69
  positive checks and 29/29 deep-copy mutations through one fail-closed
  predicate; the MPI audit closes 133/133 and 21/21, while MPI remains 0/8
  controlled.  End-to-end diagnostic dynamics, CAD generation, mission release,
  physical contact, production dynamics and Sim13 production rebinding all
  remain false/HOLD.
- `13_loop_continuation_v3/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V3.json`
  is the preserved third continuation entry point.  It binds e19's 17/17 isolated
  diagnostic execution Gate and its independent 31/31 + 85/85 fail-closed
  validation.  The only new closed state is hash-bound, isolated, non-release
  numeric diagnostic execution and reproducibility.  The M01 and M07 arm-only
  base-reaction observations have no authorized acceptance threshold and do
  not use a released current mass model.  End-to-end dynamics, physical
  contact, attached-target recovery, Route-C CAD, mission, production,
  hardware and flight authority remain false/HOLD.
- `14_loop_continuation_v4/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V4.json`
  is the preserved fourth continuation entry point.  Its only new closed state is
  `independent_surrogate_mass_branch_sim11_coupled_arm_only_diagnostic_execution_closed=true`,
  bound to e20's independently reproduced 43/43 checks and 93/93 negative
  controls.  The e20 completion scales bus mass and inertia with one artificial
  uniform-density scalar; it is not M4 system mass/CG/inertia authority.  Its
  `M_DYNAMICS_LEGACY_NUMERICAL` mount model has no physical-mount semantics and
  does not consume or close the current-M7 design dynamics.  ODR-01 continues
  to define the current dynamics convention as `T_SM=[185.25,0,0] mm + Ry(90°)`,
  separate from the 208 mm + 25.000014° CAD/geometry mount context.  Which
  transform WP2 V2 used for each S-frame mass-property placement was not
  evaluated in e20; the frame-to-mass reconciliation remains HOLD pending e21.
  The V4 validator closes 38/38 checks and 116/116 deep-copy negative controls,
  while e15 remains `REPEAT_ANCF_CERTIFICATION` and physical mount, contact,
  attached-target, CAD, mission, production, hardware and flight authority all
  remain false/null/HOLD.
- `15_loop_continuation_v5/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json`
  is the current continuation entry point.  It binds the complete V4 Gate,
  brief, manifest and validation; e21's frozen Gate/validation/manifest; and the
  repaired, independently adversarially audited Route-C C1.5 evidence.  e21 machine-detects mixed arm
  placement contexts in both M7 mass-ledger generations, but does not select or
  average either branch and does not treat their difference as uncertainty.
  Only the current-R2 deployed-locked rigid-wing M07 arm-only two-placement
  sensitivity and fixed-base leaf-only ROM reproduction are closed; the
  moving-hinge mass conflict is nonselected/nonpropagated and full R2 flexible
  coupling remains `NOT_EVALUATED`.  Route-C C1.5 closes 11/11 positive and
  36/36 negative synthetic predicate checks, freezes the non-release parameter
  contract, and passes 26/26 generated validation checks, 48/48 deep-copy Gate
  controls, 7/7 physical-null controls and 12/12 canonical-parameter controls.
  It has no external trust anchor, finds no physical candidate, and leaves all
  capacity measurands null.  The V5 Gate top-level schema, all 12 facts,
  authority/human-ruling fields, HOLD ledger, blocking fronts and engineering
  sequence are canonical-exact; parallel authority/release/CAD/capacity fields
  fail closed.  Manifest Gate/Brief output and V5 builder/validator source
  records are runtime-exact; validation is explicitly excluded from self-hash
  recursion.  The V5 validator closes 45/45 checks and 185/185 deep-copy
  negative controls.  Overall Gate remains `HOLD`, released segments
  remain 0, e15 remains `REPEAT_ANCF_CERTIFICATION`, `R2-HRN-04` remains
  `FAIL_REDESIGN_REQUIRED`, and single-placement, physical capacity, contact,
  attached-target, CAD, mission, production, hardware and flight authority all
  remain false/null/HOLD.

After an independently issued ODR-42 approval that references the request hash,
the planned order is C2 separate STEP-first design, C3 eight continuous
trajectories, C4 exact mission-first coupled verification, C5 new Route-C
mass/CG/inertia and restoring-load evidence, C6 environmental/life verification,
and C7 a new runtime consumer with a real fail-closed harness gate.

The 0.68407 kg harness mass result is a provisional diagnostic candidate
overlay, with Type-B uncertainty propagated to mass, three CG coordinates and
six inertia components for the harness and all nine system configurations.
Every 8192-sample receipt is checked against positive mass, positive-definite
inertia and the principal-moment triangle inequality.
It is not the current mass SSOT because the corresponding routing architecture
was rejected. Harness restoring torque remains UNKNOWN/HOLD until bundle
stiffness, friction and rate tests exist.

The exact evaluator verifies 36 frozen direct/transitive input hashes at each
startup.  The legacy pose file retains its historical embedded URDF hash and
is not edited; `04_mission/B601_MISSION_POSE_AUTHORITY_REBIND_V1.yaml` provides
the current-URDF loadability rebind without granting trajectory/contact
authority.
