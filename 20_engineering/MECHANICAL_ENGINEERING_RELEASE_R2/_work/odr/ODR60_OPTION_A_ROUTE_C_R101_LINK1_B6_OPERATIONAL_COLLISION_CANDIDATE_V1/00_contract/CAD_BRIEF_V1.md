# CAD brief — Route-C R101 link1 B6

- Model: six existing V9F physical Route-C parts whose current registry `parent_frame` is exactly `link1`.
- Task type: read-only source extraction, rigid frame rebake, STEP-first operational collision candidate emission, and motion-adapter validation. No geometry redesign is authorized here.
- Selection: the exact registry query `category == R && parent_frame == link1`, excluding the already frozen R20 root-static set, yielding exactly six objects named in the adjacent contract.
- Units: source FCStd `obj.Shape` is A0/q0 in millimetres; primary STEP is link1-local/q0 in millimetres; runtime PLY/NPZ/STL is link1-local in metres.
- Coordinate convention: `p_link1 = inv(T_A0_link1(0)) p_A0`; runtime pose is `p_S(q1) = T_S_A0 T_A0_link1(q1) p_link1`.
- Kinematics: parse the accepted URDF raw numeric spelling for joint1 origin, RPY, axis and limits. Sample the accepted lower limit, zero and accepted upper limit with q2–q6 fixed at zero.
- Mount: consume the 12-decimal strings in `EXECUTION_MOUNT_BINDING_V1.json` directly. Reconstruction from a rounded 25 degrees or any historical D6 mount is forbidden.
- Geometry output: six STEP files, each exactly one transferred root and one valid, closed, positive solid. FreeCAD `Object.Placement` is not applied separately because `obj.Shape` already contains it.
- Runtime output: one NPZ, binary PLY and binary STL per STEP, derived only after cold reopening the STEP, with a single mm-to-m scale.
- Validation: exact source mapping/pins; V9F receipt and mass-geometry cross-check; independent URDF FK; A0→link1→A0 bilateral BRep difference; q0 source/S closure; runtime manifold and volume checks; negative controls; fresh-process replay; pytest; mandatory CAD CLI inspection and snapshot review when tool runtime is available.
- Uncertainty: 1e-6 mm numerical transform derate and 0.05 mm runtime chordal derate are numerical only; as-built uncertainty remains null/measurement pending.
- Legal limit: these are six local host-frame candidates. Current system truth remains 1/150 operational geometry, 0/11166 pair queries, 0 SAFE, 0 edges, 0/3 stages, no path, TMG-4 HOLD, G12 FAIL, no next-stage authorization and no release credit.
