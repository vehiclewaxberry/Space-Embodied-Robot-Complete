# B5.1 CAD brief

- Model: B601 articulated engineering arm, bridge adapter, two independent
  triangular stow saddles, and a spacecraft-context candidate assembly.
- Task type: isolated SolidWorks native assembly and engineering-candidate
  mechanical design.
- Units: millimetres in CAD; metres/radians in the accepted URDF contract.
- Coordinate authority: accepted URDF link and joint frames. The 25 degree
  clock is a fixed spacecraft-to-arm installation transform, not a joint-zero
  offset.
- Geometry authority: admitted vendor B601 groups. G05 and G08 remain
  `CHAIN_DERIVED_HOLD`.
- Mass authority: accepted URDF exact source value
  `4.6955559493429862 kg`; CAD automatic mass is excluded.
- Root interface: 160 x 160 mm reference installation plane and diameter
  100 mm reference central passage. Hole pattern, fasteners, pins, material,
  tolerance, preload, and six-dimensional loads remain UNKNOWN/HOLD.
- Packaging: maintain mutually exclusive Mode A and Mode B ledgers. The 25
  degree clock is `RATIFIED_FOR_B5_1_ENGINEERING_CANDIDATE_ONLY`.
- Articulation target: six revolute joints from the accepted URDF. The two
  prismatic gripper joints are not authorized until G08 is partitioned and
  zero-calibrated.
- Positioning: source-authored transforms/mates only; no manually dragged pose
  may serve as configuration truth.
- Primary outputs: native SolidWorks files and STEP; GLB/STL are preview
  sidecars only.
- Validation: input hashes, reference ownership, cold reopen, component
  reference containment, joint sign checks, q0/STOW transforms, deterministic
  random poses where the native mate implementation supports them, STEP
  facts/planes/positioning, and mandatory multi-view snapshot review.
- Claim limit: engineering candidate only; not complete, flight ready,
  manufacturing ready, or structurally qualified.
