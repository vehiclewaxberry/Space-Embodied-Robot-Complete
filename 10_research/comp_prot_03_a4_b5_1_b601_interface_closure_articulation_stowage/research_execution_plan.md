# B5.1 B601 interface closure, articulation, and stowage execution plan

Task:

`COMP-PROT-03-A4-B5.1-B601-INTERFACE-CLOSURE-ARTICULATION-STOWAGE`

Authorization basis: the user explicitly requested execution of the attached
B5.1 Phase A-H prompt. This does not authorize a MODE_A/MODE_B flight
architecture selection, manufacturing release, flight qualification, vendor
file modification, accepted-URDF modification, or changes to frozen
V2.0/V2.1/V2.2 baselines.

## Engineering questions

1. Can the accepted B601 URDF chain and admitted vendor link-local geometry be
   represented by a cold-reopenable native SolidWorks 6R engineering
   assembly, without changing the URDF truth?
2. Can the B601 installation load path and two independent stow supports be
   decomposed against the canonical frozen V2.2 native structure so that no
   unadjudicated or unacceptable solid collision remains?
3. What geometric and unit-load evidence can be produced for the 25 degree
   B5.1 engineering candidate while H9, formal loads, materials, fasteners,
   HDRM selection, and G08 finger partition remain HOLD?

## Hypotheses and fail-closed limits

- H-A: the canonical V2.2 native baseline can be copied into the B5.1
  isolation domain with all 108 frozen-manifest hashes unchanged.
- H-B: source-authored revolute mates can reproduce accepted-URDF forward
  kinematics at q=0, STOW, sign perturbations, and 20 deterministic legal
  random poses within inherited DIRECT/CHAIN_DERIVED registration bounds.
- H-C: replacing the legacy spreader/crossbeam overlaps with datum-driven
  bridge and saddle interfaces can reduce exact residual
  `UNACCEPTABLE_COLLISION` and unadjudicated interference counts to zero.
- G08 two-prismatic articulation is not assumed possible: without a traceable
  fixed-body/left-finger/right-finger partition and zero calibration, G3
  remains a 6R pass candidate plus 2P HOLD rather than a false 6R+2P pass.
- No absent launcher ICD, load spectrum, material, connection stiffness,
  preload, or HDRM model is inferred.

## Governing checks

- Rigid-chain forward kinematics:
  `T_0_i(q) = product(T_parent_joint * Rot(axis, q_i))`.
- Pose error: translational norm in millimetres and relative-rotation angle in
  radians, reported separately for DIRECT and CHAIN_DERIVED geometry.
- Interference: exact BREP common volume; clearance: minimum Euclidean
  distance. Expected contact pads are kept separate from unintended contact.
- Preliminary structural evidence, only after geometry closure:
  `K u = f_unit`, first eigenpairs of `(K - omega^2 M) phi = 0`, and
  parameterized slenderness/connection-stiffness sensitivity. These are trends,
  not launch qualification.

## Files and ownership

- Only writable engineering root:
  `20_engineering/cad/B5_1_B601_interface_closure_candidate/`.
- Frozen/read-only truths: accepted B601 URDF, vendor STEP, B5.0 accepted
  evidence, canonical `Space_Embodied_Robot_CAD_V2_2_NATIVE`, and the full
  120/130 evidence trees.
- The earlier B5.1 Phase-A lock that admitted the legacy V2.2 functional tree
  is retained as historical evidence and superseded by an append-only
  canonical-baseline reconciliation record.

## Implementation sequence

1. Reconcile Phase A to the canonical V2.2 native baseline and verify the
   108-file seal plus full 120/130 evidence hashes.
2. Preserve and revalidate the existing B5.1 bridge/saddle STEP candidates and
   snapshot packet.
3. Extend the demonstrated native 2R rigid-segment chain to 6R, then run cold
   reopen, q=0, STOW, sign, off-axis rejection, and 20 random-pose checks.
4. Build/verify the B5.1 master skeleton and canonical-V2.2 integration
   context; perform exact BREP disposition of all inherited V14 items.
5. Run continuous solar/B601 sequence clearance only where state geometry is
   genuinely bound; mark unsupported failure states UNKNOWN/UNSAFE.
6. Run unit-load/modal/slenderness sensitivity only after the geometry gate.
7. Issue G0-G7 and one of the four user-authorized final verdicts.

## Tests and acceptance gates

- G0: source hashes unchanged; copied tree hashes match; zero reference write
  outside B5.1.
- G1: remains HOLD until an authorized human selects MODE_A or MODE_B.
- G2: 28/28 dispositions include exact geometry evidence; zero unacceptable
  and zero unadjudicated residual collisions.
- G3: native 6R cold reopen and URDF consistency pass; 2P separately
  PASS/HOLD according to G08 partition evidence.
- G4: two physical saddle assemblies, three-direction load paths, HDRM
  functional keep-outs, and release direction are explicit.
- G5: nominal continuous sequence has zero unintended collision; failure
  states are fail-closed.
- G6: unit-load, modal, and slenderness evidence exists without qualification
  claims.
- G7: CAD-URDF-visual/collision frames agree; accepted URDF remains the mass
  authority.

## Rollback

- Never overwrite or delete frozen sources.
- Every native build uses a new run directory and run id.
- Failed runs remain as evidence; a new corrected run supersedes them.
- Any baseline hash drift produces
  `B51_FAIL_BASELINE_CONTAMINATION` and stops downstream claims.
