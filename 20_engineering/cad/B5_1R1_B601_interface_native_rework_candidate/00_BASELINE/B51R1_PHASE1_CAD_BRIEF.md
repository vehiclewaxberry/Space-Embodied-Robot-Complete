# B51R1 Phase 1 CAD brief

- Model: B601 canonical interface rework, Master Skeleton V2, and a
  two-layer native articulated assembly.
- Task type: isolated native SolidWorks source creation plus STEP-first
  deterministic validation.
- Units: millimetres for CAD geometry; metres and radians only where the
  accepted URDF is quoted.
- Root convention: `CS_SPACECRAFT_BODY` is the spacecraft root;
  `CS_B601_BASE_ACCEPTED` is the accepted arm root; the 25 degree frame is
  a candidate-only child frame.
- Fixed truth: accepted URDF SHA-256
  `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`,
  mass string `4.6955559493429862 kg`, topology
  `6R + 1 fixed + 2P`.
- Canonical spacecraft donor: V2.2_NATIVE 108-file freeze; top assembly
  SHA-256
  `30C09B50A0D2967EC1F48050CAAC34D12A43565C44978D54E3785595202DEF7A`.
- Parent verdict: `B51_REVISE_INTERFACE_COLLISION`.
- H9 handling: retain `MODE_A_EVALUATION` and `MODE_B_EVALUATION`; freeze
  only shared datums.
- Positioning: named coordinate systems, axes, planes, occurrence
  transforms, and authored mates only. Screen pixels, bounding boxes,
  dragged positions, and imported-face topology are not mate authority.
- Phase 1A validation: durable named-entity measurements must reproduce
  the 4 mm longeron discrepancy and 3 mm saddle-to-primary separation or
  remain `MEASUREMENT_HOLD`.
- Phase 1B artifact: `B51R1_MASTER_SKELETON_V2.SLDPRT`, excluded from BOM
  and mass, with 160 x 160 mounting plane, diameter 100 central passage,
  shared structural datums, contact windows, keep-outs, maintenance
  envelopes, and both H9 evaluation branches.
- Phase 1C architecture: ten lightweight carriers; the six revolute, one
  fixed, and two prismatic relationships live between carriers. Detailed
  link geometry is rigidly attached later and never supplies moving mate
  topology.
- Primary output paths: `02_MASTER_SKELETON`, `03_CAD`,
  `04_CONFIGURATION`, `07_VERIFICATION`, and `08_REVIEWS`.
- Required validation: frozen hashes, internal reference ownership,
  source/STEP facts, datum positions and frames, q0 and joint signs,
  native limits, T005-A/B/C, H10 28/28, and mandatory snapshots for every
  created or visibly changed STEP.
- Fail-closed conditions: any frozen hash drift, unresolved/external
  reference, unavailable durable datum, silent H9 selection, URDF
  axis/sign conflict, unstable imported-face mate, hidden T005 reset
  failure, or unsupported H10 closure.

