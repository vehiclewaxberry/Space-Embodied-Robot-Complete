# B5.0 B601 Space Manipulator Candidate

Task ID:

`COMP-PROT-03-A4-B5.0-B601-SPACE-MANIPULATOR-ENGINEERING-CAD`

This is an isolated engineering candidate. It does not modify or supersede V1.0, V2.1, V2.2, V2.2_NATIVE, V2.3 or the accepted B601 URDF.

## Model layers

- L0 dynamics truth: accepted B601 URDF, read-only.
- L1 engineering visual CAD: native SolidWorks assets created in this root.
- L2 simulation visual/collision: derived from L1, with L0 link/joint names.

## Writer

The sole native-CAD writer for this candidate is:

`CODEX_PYWIN32_SOLIDWORKS_2024_SP5_EARLY_BOUND`

The writer may create or modify files only under this candidate root. It must start with no `SLDWORKS.exe` process, launch its own instance, and call `ExitApp` in a `finally` block.

## Status

Phase 0:

`B5_0_PHASE0_PASS_WITH_RECORDED_TOOL_DEVIATIONS`

Current native CAD milestone:

`B5_0_PHASE1_NATIVE_Q0_REFERENCE_PASS_WITH_G05_G08_HOLD_AND_RECORDED_TOOL_DEVIATIONS`

The authoritative run is
`03_CAD/native_runs/B50_NATIVE_20260727T2214Z`. It contains a master skeleton,
eight link-local native reference parts, a nine-component fixed-q0 SolidWorks
assembly, a model-backed drawing, and a cold-verified 388-solid STEP.

The assembly is intentionally a fixed q0 geometry reference. It does not retain
the six revolute joint degrees of freedom. Phase 2 engineering decomposition,
spacecraft integration, base/stowage/end-effector design, candidate simulation
models, and continuous-clearance evidence remain partial or HOLD. See
`07_VERIFICATION/GATE_STATUS.json`.

A separately gated Phase-3 reference-envelope run now exists at
`03_CAD/native_runs/B50_BASE_REF_20260728T0029Z`. It contains three native
base-adapter envelope parts and `B601_BASE_ADAPTER.SLDASM`. Its verdict is
`B5_0_PHASE3_BASE_ADAPTER_REFERENCE_ENVELOPE_PASS_WITH_PHYSICAL_INTERFACE_HOLD`;
it does not complete the physical adapter, loads, holes, fasteners, materials,
or spacecraft integration.

No generated geometry is authoritative for mass, inertia, strength, manufacturing, launch or flight qualification.
