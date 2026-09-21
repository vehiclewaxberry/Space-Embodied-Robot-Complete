# B5.1 spacecraft-context integration CAD brief

Status:

`ENGINEERING_CANDIDATE_RENDER_CONTEXT_WITH_EXPLICIT_H9_H10_MOTION_HOLDS`

- Model: isolated V2.2 spacecraft context with the admitted real B601 STOW
  geometry, B5.1 bridge adapter, G07/G08 double-triangle saddles, solar-wing
  state references, and Mode A/Mode B non-physical envelope witnesses.
- Task type: read-only donor composition and rendering assembly. No donor
  geometry is edited.
- Units: millimetres.
- Coordinate convention: all occurrences use the existing spacecraft frame
  `CS_S`; `+X` is outboard through the B601 task face. Every admitted STEP is
  inserted with an identity transform because it is already authored in
  `CS_S`.
- Geometry inputs:
  - V2.2 revised primary structure and solar-wing source from
    `110_Layout_and_Deployment_01/staging/layout_staging.py`;
  - real `B601_VENDOR_STOW.step` from VENDOR-CAD-03;
  - existing B5.1 `B51_BRIDGE_ADAPTER.step`,
    `B51_G07_MAIN_SADDLE.step`, and `B51_G08_GRIP_SADDLE.step`.
- Vendor-part policy: the exact, frozen local B601 vendor asset is already
  admitted, so no catalog substitute or simplified B601 envelope is created.
- Positioning/mating: source-authored identity placement in `CS_S`. This is a
  static STOW visualization binding, not a persistent native mate solution.
- Mode A witness: current core-box proxy
  `X=[-183,183]`, `Y=[-113.15,113.15]`,
  `Z=[-113.15,115.15] mm`. No launcher/deployer ICD is bound.
- Mode B witness: provisional two-file union
  `X=[-213,412.47]`, `Y=[-113.15,113.15]`,
  `Z=[-115,361.34] mm`. It is not a final flight envelope.
- Solar references: physical STOW (`0/0 deg`) in the primary integration;
  an additional diagnostic STEP shows the same STOW geometry plus transparent
  `90/90 deg` deployed moving-panel references. It is not a continuous sweep.
- Primary outputs:
  - `B51_SPACECRAFT_B601_STOW_INTEGRATION.step`;
  - `B51_SPACECRAFT_B601_STOW_INTEGRATION.glb`;
  - `B51_SOLAR_STATE_REFERENCE.step`;
  - `B51_SOLAR_STATE_REFERENCE.glb`.
- Validation targets:
  - exported STEP facts, occurrence labels, BREP status, and bounding boxes;
  - selected exact common-volume and minimum-distance checks where the vendor
    BREP permits them;
  - isometric, side, top, interface-local, and double-saddle-local CAD
    snapshots;
  - source/donor SHA-256 provenance.
- Claim limits:
  - H9 remains `HUMAN_DECISION_REQUIRED`;
  - H10 is not closed and the inherited 28 records are not reclassified here;
  - no continuous solar/arm motion or release path is verified;
  - no CAD mass value may replace accepted URDF mass
    `4.695555949342986 kg`;
  - not manufacturing, flight, structural, or contact qualification.

