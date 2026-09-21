# CAD brief — B601 gripper 2P BRep extraction audit

- Model: three-piece B601 gripper local collision candidates; this temporary audit generates only the left- and right-finger STEP candidates and reuses the existing R1 palm STEP.
- Task type: direct STEP-source extraction and validation, not new geometry design.
- Frozen inputs: B50 neutral 57-solid STEP, V5 57-body receipt, terminal solid-assignment CSV, existing R1 palm/finger meshes, and M5 gripper-link-local PLY surfaces.
- Units: all BRep and STEP coordinates are millimetres; M5 PLY vertices are metres and are multiplied by 1000 only at the comparison boundary.
- Coordinate convention: preserve the B50 source coordinates exactly. Existing M5 evidence numerically binds these coordinates to `gripper_link`, despite the legacy `LINK6_LOCAL` label.
- Construction: reproduce the R1 builder's Hungarian one-to-one B50↔V5 fingerprint binding; select the frozen 24 left and 24 right solids; export each unchanged set as a labeled compound. Do not fuse, heal, offset, simplify, remesh, or reconstruct from STL.
- Primary outputs: temporary `B601_GRIPPER_LEFT_FINGER_GRIPPER_LINK_LOCAL_R1_SOURCE.step` and matching right-finger STEP. Existing `B601_GRIPPER_PALM_RAIL_SLOT_R1.step` remains the palm source and is not copied or modified as an authority asset.
- Validation targets: 24 valid positive-volume solids per finger; OCP compound validity; fixed-timestamp byte-repeatable STEP export; STEP reopen count/volume/bbox/canonical-digest parity; byte parity of a 0.05 mm/0.1 rad STL re-export against the frozen R1 finger STL; bbox and deterministic point-cloud registration against the M5 PLY after explicit m→mm conversion.
- Positioning: no assembly motion is authored. The output remains in the neutral `gripper_link`-local source coordinates. Runtime prismatic motion and child-link re-expression are outside this audit.
- Assumptions: exactness means exact extraction of B50 BRep solids selected by the frozen V5 receipt/assignment. It does not mean native V5 SLDPRT topology equivalence, as the frozen R1 receipt explicitly denies that claim.
- Scope limit: no M01 system pair, contact, strength, manufacturing, path, SAFE, or release credit.
