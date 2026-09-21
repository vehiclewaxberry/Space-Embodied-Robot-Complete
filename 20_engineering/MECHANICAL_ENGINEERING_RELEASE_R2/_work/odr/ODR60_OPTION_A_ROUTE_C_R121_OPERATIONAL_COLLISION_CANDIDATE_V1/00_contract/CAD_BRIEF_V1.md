# CAD brief — Route-C R121 umbrella / Phase A root-static R20

- Model: twenty independent physical Route-C harness-support objects selected from the frozen V9F FCStd.
- Task type: direct STEP-first extraction and coordinate re-expression; no V10/V11 geometry redesign and no source regeneration.
- Inputs: hash-pinned V9F FCStd, V9F build receipt, M01 R121 registry, exact execution mount and retained V9F negative witness.
- Units: source BRep and primary STEP in millimetres; runtime PLY/STL/NPZ in metres.
- Source coordinate convention: `A0 = B601 base_link at q=0`; source geometry is already placed in this shared frame.
- Output coordinate convention: spacecraft bus `S`; apply the exact current `T_S_A0` once to the copied BRep. Do not separately reapply a FreeCAD object Placement.
- Object scope: exactly the 12 `base_link` and 8 `bus` R-class physical objects whose motion class is `HOST_FIXED_UNLESS_REGISTERED_OTHERWISE`.
- Geometry intent: preserve each selected source BRep exactly under one rigid transform; one output STEP and three runtime sidecars per object.
- Primary paths: `01_cad/R_*_S_V1.step`; runtime derivatives under `02_runtime/`.
- Validation targets: 13/13 source pins; exact 20-object bijection; source and output valid closed single positive BRep; volume/topology preservation; STEP cold reopen; exact frame/unit/transform count; independent source-to-output comparison; deterministic replay; mandatory CAD refs and snapshot review.
- Explicit exclusions: nine logical bundle envelopes; the q-dependent R101 objects; system registry promotion; pair/SAFE/edge/path credit; TMG-4, G12, next-stage or release credit.
- Uncertainty: numerical STEP derate `1e-6 mm/object`; runtime chordal derate `0.05 mm/object`; manufacturing/as-built derate remains `null / MEASUREMENT_PENDING`.
- Historical negative: the V9F straight-q witness at gated clearance `-17.313396996697108 mm` remains immutable and is not converted into a current pair result.
