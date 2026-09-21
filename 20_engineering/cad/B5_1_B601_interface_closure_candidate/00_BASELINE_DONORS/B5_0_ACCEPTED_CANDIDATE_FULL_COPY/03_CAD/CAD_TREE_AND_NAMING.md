# B5.0 CAD Tree and Naming

Current accepted milestone:
`B5_0_PHASE1_NATIVE_Q0_REFERENCE_PASS_WITH_G05_G08_HOLD_AND_RECORDED_TOOL_DEVIATIONS`

Authoritative run:
`native_runs/B50_NATIVE_20260727T2214Z`

## Native tree

```text
00_skeleton/
  B50_B601_MASTER_SKELETON.SLDPRT
10_vendor_reference_parts/
  B50_REF_base_link_LINKLOCAL.SLDPRT
  B50_REF_link1_LINKLOCAL.SLDPRT
  B50_REF_link2_LINKLOCAL.SLDPRT
  B50_REF_link3_LINKLOCAL.SLDPRT
  B50_REF_link4_LINKLOCAL.SLDPRT
  B50_REF_link5_LINKLOCAL.SLDPRT
  B50_REF_link6_LINKLOCAL.SLDPRT
  B50_REF_gripper_detail_LINKLOCAL.SLDPRT
20_assembly/
  B50_B601_ENGINEERING_ARM_Q0.SLDASM
30_exports/
  B50_B601_ENGINEERING_ARM_Q0.step
  B50_B601_ENGINEERING_ARM_Q0.stl
  B50_B601_ENGINEERING_ARM_Q0.glb
40_drawings/
  B50_B601_ENGINEERING_ARM_Q0.SLDDRW
```

## Naming contract

- `B50`: isolated B5.0 candidate prefix.
- `REF`: imported geometry reference; not a manufacturing definition.
- `LINKLOCAL`: donor geometry has been registered into the corresponding
  accepted link-local frame.
- `Q0`: fixed zero-configuration geometry reference.
- No file may be named `Part1`, `Assembly1`, `NewPart`, or `Copy of ...`.
- New native assets must remain under the B5.0 candidate root.

## Authority contract

- Kinematic, mass, and inertia authority: accepted B601 URDF only.
- Native SLDPRT/SLDASM/SLDDRW: engineering visual/reference CAD.
- STEP: cold-verified geometry exchange authority for this q0 milestone.
- STL/GLB: preview and future collision-derivation inputs only.
- The current SLDASM has nine fixed top-level components. It is not a retained
  6R mechanism and must not be used to claim SolidWorks joint motion.

## Registration status

- Direct geometry reference: G01, G02, G03, G04, G06, G07.
- `CHAIN_DERIVED_HOLD`: G05, G08.
- B106: `NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH`.

Future engineered joint modules, base adapter, stowage restraint, end effector,
sensors, harness, and spacecraft integration must use new descriptive names
and separate append-only evidence.

## Base-adapter reference run

The separately gated reference-envelope run is
`native_runs/B50_BASE_REF_20260728T0029Z`:

```text
10_reference_parts/
  B50_BASE_ADAPTER_UPPER_FLANGE_ENVELOPE.SLDPRT
  B50_BASE_ADAPTER_SPREADER_PLATE_ENVELOPE.SLDPRT
  B50_BASE_ADAPTER_PRIMARY_BOSS_ENVELOPE.SLDPRT
20_assembly/
  B601_BASE_ADAPTER.SLDASM
30_exports/
  B601_BASE_ADAPTER_REFERENCE.step
40_drawings/
  B601_BASE_ADAPTER_REFERENCE.SLDDRW
```

These assets are `DESIGN_PROPOSAL_REFERENCE_ENVELOPE`; they do not close the
physical-interface or Phase-2 completeness gates.
