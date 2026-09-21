# CAD brief — B601 rigid-link operational collision proxies V1

- Model: six independent, link-local collision-only STEP parts for accepted B601 `link1` through `link6`.
- Task type: new L2 operational-collision proxy candidate package; no L0 inertial or accepted-URDF modification.
- Inputs: the six hash-pinned M5 CAD-surface PLY files already registered to accepted URDF link frames.
- Units: source and runtime collision arrays are metres; primary STEP geometry is millimetres.
- Coordinate convention: every part remains in its own accepted URDF link frame; no spacecraft mount, joint pose, mission pose, or WP11 datum correction is baked a second time.
- Geometry intent: a deterministic 12-slab axis-aligned cover of each source surface's full convex hull. Each slab contains the exact convex-hull cross-section at its two boundary planes plus all hull vertices inside the slab. A 0.005 mm transverse numerical guard is added. The result is conservative collision geometry, not hardware shape, contact geometry, strength geometry, or mass authority.
- Primary outputs: `03_assets/B601_LINK{1..6}_OPERATIONAL_COLLISION_PROXY_V1.step`.
- Secondary outputs: canonical per-solid NPZ/STL collision arrays and native GLB preview sidecars derived from the same STEP-first build.
- Validation targets: exact source SHA/byte pins; 12 positive BRep-valid solids per link; link-local frame and SI-unit locks; analytical convex-hull containment; exact source-surface containment; closed/oriented NPZ solids; deterministic replay; six asset-level geometry passes; zero parent-Gate/pair/path/release authority.
- Assumptions: convex-hull conservatism is acceptable for M01 fail-closed filtering. This package does not assert tight-contact fidelity and deliberately excludes `base_link` plus all three gripper bodies.

