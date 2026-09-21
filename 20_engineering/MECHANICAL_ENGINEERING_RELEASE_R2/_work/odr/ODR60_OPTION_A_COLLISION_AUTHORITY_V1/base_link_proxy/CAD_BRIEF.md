# CAD brief — B601 `base_link` operational collision proxy

- Model: B601 `base_link` physical collision geometry; secondary NPZ/STL export from an existing STEP BRep.
- Task type: read-only STEP inspection plus deterministic collision-mesh derivation. No STEP and no URDF is created or modified.
- Primary input: `B50_REF_base_link_LINKLOCAL.step`, 69 retained solids, SHA-256 `A451B915…90F07C5`.
- Excluded input: accepted-URDF `base_link.STL`, SHA-256 `22641C07…3B65`; WP11 proves that mesh contains the deleted desktop plate. The generator does not open it.
- Units: source STEP millimetres; operational NPZ and binary STL metres.
- Coordinate convention: accepted URDF `base_link`, right-handed; WP11 translation `D_base_link=[-0.05732750272995675,-0.03253727084589079,+0.05006764302725364] mm`, identity rotation.
- Positioning: link-local only. The spacecraft 208 mm / 25° mount clocking and `T_SM` are intentionally not baked into the proxy.
- Expected conservative BRep bbox after `D_base_link`, mm: min `[-45.9756575386,-46.0578673067,2.4517376072]`, max `[46.0310025331,45.9487927650,82.6083976789]`.
- Bbox interpretation: this frozen contract uses OCCT `BRepBndLib.Add_s`, including the conservative native shape gap. A separate `AddOptimal_s` tight bbox is reported for mesh comparison.
- Meshing: OCCT single-process, 0.05 mm linear deflection, 0.15 rad angular deflection; vertices rounded at `1e-12 m` before canonical sorting.
- Outputs: `BASE_LINK_OPERATIONAL_COLLISION_V1.npz`, `BASE_LINK_OPERATIONAL_COLLISION_V1.stl`, and machine receipt.
- Validation targets: pinned source hashes; 69 positive-volume BRep solids; preserve the pinned negative fact that `BRepCheck` reports 67/69 valid (five `UnorientableShape` faces across two imported solids); bbox within 0.001 mm of contract; no duplicate/degenerate triangles; all 69 derived per-source-solid meshes closed and consistently oriented by exact edge audit; aggregate mesh/BRep volume error ≤0.1%; four exclusive outer regions of the removed desktop plate contain no triangle AABBs; fresh single-process byte-identical replay.
- Lifecycle caveat: a passing proxy remains `PENDING_OWNER_REVIEW`, grants no path-search authority, and grants no release credit.
