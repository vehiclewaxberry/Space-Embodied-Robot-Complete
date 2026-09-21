# B5.1R1 Phase 0 research findings

Task:

`COMP-PROT-03-A4-B5.1R1-B601-CANONICAL-INTERFACE-AND-NATIVE-ARTICULATION-REWORK`

Result:

`CAUSALITY_AND_ENGINEERING_CONTRACT_BASELINE_COMPLETE / FACE_LEVEL_MEASUREMENT_HOLD / PHASE1_NATIVE_REWORK_NOT_AUTHORIZED`

## Findings

1. The `4.0 mm` longeron-centre discrepancy and the `3.0 mm`
   saddle-to-primary distance are different causal chains, not one rigid-body
   translation.
2. The legacy branch used a `15×15 mm` longeron centred at `105.65 mm`, with
   outer surface `113.15 mm`. The canonical native source uses a `17×17 mm`
   longeron centred at `101.65 mm`, with primary outer surface `110.15 mm` and
   a `3 mm` removable panel extending to `113.15 mm`.
3. The centre difference decomposes as:

   `105.65 - 101.65 = 3.0 mm panel layer + 1.0 mm half-section change = 4.0 mm`.

4. B5.1 created its datum register and geometry from the earlier legacy donor
   before the canonical 108-file donor correction. Its datum fields were not
   regenerated with per-field authority binding.
5. Exact BREP diagnostics show both G07 and G08 saddle shoes at
   `3.000000000000014 mm` from primary structure and `0 mm` from the removable
   panels. This is panel-envelope contact, not a proved primary attachment.
6. Parent H10 remains `28/28 OPEN`: eight unacceptable collisions and twenty
   intended laps. The R1 ledger adds root-cause ownership and evidence fields
   but closes zero rows.
7. The accepted URDF remains `6R + 1 fixed + 2P`. Current native CAD does not
   implement unique native joint drivers, native limits, a named fixed-joint
   object, or either independent P joint.
8. T005 failed at the first random legal pose. Document reopen is a useful
   diagnostic control, not a repair and not G3 credit.
9. Existing G07/G08 STEP naming supports candidate `±Z` pads and `±Y` guides,
   but no named X axial stop exists. A G07 stop / G08 X-float allocation is
   retained only as `PROPOSED_NOT_RATIFIED`.
10. Adapter A/B/C evidence maturity is unequal, so weighted scoring and
    downselection are disabled.

## Durable engineering outputs

- source and parent freeze:
  `20_engineering/cad/B5_1R1_B601_interface_collision_and_articulation_rework_candidate/00_CONTROL/`
- datum causality and Master Skeleton V2 brief:
  `.../01_DATUM/`
- inherited H10 closure ledger:
  `.../02_H10/`
- accepted-topology gap register and T005-A/B/C contract:
  `.../03_ARTICULATION/`
- state/interface/6DOF restraint contract:
  `.../04_STOWAGE/`
- unscored adapter A/B/C trade:
  `.../05_TRADE/`

## Preserved holds

- H9 and mount-track decision: human decision required.
- G2: geometry redesign required.
- G3: no accepted native 6R run; fixed object, 2P, zero references, drivers,
  and native limits incomplete.
- G4: physical restraint/release interface unqualified.
- G5/G6: not run.
- No manufacturing, launch-qualification, or flight-readiness claim.

## Next human Gate

`COMP-PROT-03-A4-B5.1R1-PHASE1-MASTER-SKELETON-V2-AND-NATIVE-REWORK-AUTHORIZATION`

That Gate must state separately whether native SolidWorks authoring and STEP
source modification are allowed. It does not automatically authorize FEA,
continuous clearance, simulation, hardware motion, manufacturing, launch
qualification, or flight claims.

