# B5.0 Mechanical CAD Acceptance Report

Task:
`COMP-PROT-03-A4-B5.0-B601-SPACE-MANIPULATOR-ENGINEERING-CAD`

Current program result:
`PARTIAL_ACCEPTANCE_WITH_EXPLICIT_HOLDS`

This report accepts two bounded native-CAD milestones. It does not accept the
complete spacecraft-integrated mechanism requested by the full B5.0 program.

## Accepted milestone 1: B601 fixed-q0 native reference

Verdict:
`B5_0_PHASE1_NATIVE_Q0_REFERENCE_PASS_WITH_G05_G08_HOLD_AND_RECORDED_TOOL_DEVIATIONS`

Run:
`B50_NATIVE_20260727T2214Z`

Accepted facts:

- accepted URDF SHA-256 remains
  `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`;
- accepted mass remains the source decimal
  `4.6955559493429862 kg`;
- topology remains 10 links and 9 joints: 6 revolute, 1 fixed, 2 prismatic;
- one zero-solid master skeleton plus eight native link-local geometry parts;
- nine fixed top-level assembly components;
- 388 solids in the STEP, all from the eight geometry parts;
- OCP cold read, model-backed drawing view, internal path checks, transform
  checks, and before/after hashes passed;
- CAD CLI inspect: 9 occurrences, 8 leaf occurrences, 388 shapes,
  24,667 faces, 64,405 edges;
- the accepted visual review shows a non-collapsed multi-joint arm with no
  coordinate spike.

Limits:

- the SolidWorks assembly retains no joint freedom: neither the six revolute
  arm joints nor the two prismatic gripper joints are movable components/mates;
- G05 and G08 remain `CHAIN_DERIVED_HOLD`;
- B106 remains `NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH`;
- the drawing is one reference isometric view, not a dimensioned manufacturing
  drawing;
- STL/GLB previews omit four null-triangulation faces; the 388-solid STEP
  remains the exchange authority.

## Accepted milestone 2: base-adapter reference envelopes

Verdict:
`B5_0_PHASE3_BASE_ADAPTER_REFERENCE_ENVELOPE_PASS_WITH_PHYSICAL_INTERFACE_HOLD`

Run:
`B50_BASE_REF_20260728T0029Z`

Accepted facts:

- three native one-body reference parts: 160 × 160 × 15 mm upper flange,
  160 × 160 × 12 mm spreader plate, and Ø100 × 15 mm boss;
- admitted X stack: `[156,171]`, `[171,183]`, and `[183,198] mm`;
- explicit `185.25 mm` dynamics track, `198.0 mm` display track, and
  `12.75 mm` delta;
- three fixed internal components with zero cold transform error;
- zero external references, zero auxiliary references, and zero 3D
  Interconnect features;
- one model-backed drawing view;
- three-solid STEP with maximum bounding-box error
  `9.999999406318238e-08 mm`;
- CAD CLI inspect: 4 occurrences, 3 leaf occurrences, 3 shapes, 16 faces,
  30 edges;
- snapshot review visibly distinguishes the two square envelopes and one
  circular boss envelope.

Limits:

- every file is marked
  `DESIGN_PROPOSAL_REFERENCE_ENVELOPE`,
  `PHYSICAL_QUALIFICATION=FALSE`,
  and `MANUFACTURING_AUTHORITY=NONE`;
- there are intentionally no holes, bolts, locating pins, connector passages,
  material assignments, or released tolerances;
- all six-dimensional installation and load cases remain
  `UNKNOWN_BLOCKED`;
- no CAD mass may replace the accepted URDF mass.

The failed diagnostic run `B50_BASE_REF_20260728T0024Z` is retained. It stopped
before creating CAD because the rectangle API was initially given global-plane
coordinates instead of sketch-local coordinates.

## Gate matrix

| Gate | Current state | Basis |
|---|---|---|
| G0 baseline protection | PASS | Protected assets rechecked 79/79 |
| G1 kinematic consistency | PASS for fixed q0 only | Accepted transforms and STEP bbox |
| G2 engineering form completeness | PARTIAL / HOLD | Detailed donor geometry exists; engineered joints, load paths, sensors, harness, EE not complete |
| G3 assembly and clearance | HOLD | No accepted spacecraft top-level or complete continuous sweep |
| G4 digital thread | PARTIAL | CAD→STEP trace passes; candidate URDF/MJCF/USD pending |
| G5 simulation runnable | HOLD | Fixed/free-floating simulation not executed |
| G6 claim compliance | PASS with limits | No manufacturing, flight, strength, or autonomous-capture claim |

## Solar-wing and stowage ruling

The following sequence is retained:

`SOLAR_RELEASE_AND_DEPLOY → SOLAR_DEPLOYMENT_CONFIRMED → B601_RELEASE`

Current evidence permits only static/diagnostic staging. It does not establish
a common native top-level assembly, complete continuous clearance, or the
first arm-release segment. The q0 reference is not an approved launch-stowed
joint vector.

The following negative or unresolved results remain controlling:

- full-platform solar/B601/HDRM/harness integration is absent;
- the earlier `|Y| ≤ 40 mm` corridor was invalidated by real B601 geometry;
- `238.3 > 226.3 mm` stowed-width and
  `302.3 > 226.3 mm` root-mechanism results remain negative evidence;
- candidate tracks and endpoint values from different branches may not be
  silently mixed;
- Z-direction stow limit remains `UNKNOWN`;
- `PARTIAL` and `SERVICE` have no unique approved joint vectors.

## Evidence

- `07_VERIFICATION/GATE_STATUS.json`
- `03_CAD/native_runs/B50_NATIVE_20260727T2214Z/evidence/native_q0_cold_verify.json`
- `03_CAD/native_runs/B50_NATIVE_20260727T2214Z/evidence/visual_review_adjudication.json`
- `03_CAD/native_runs/B50_NATIVE_20260727T2214Z/evidence/cad_cli_inspect_refs.json`
- `03_CAD/native_runs/B50_BASE_REF_20260728T0029Z/evidence/base_adapter_reference_gate.json`
- `03_CAD/native_runs/B50_BASE_REF_20260728T0029Z/evidence/base_adapter_reference_cold_verify.json`
- `07_VERIFICATION/protected_hash_verification.json`

## Next execution gate

The next safe work is engineering decomposition and interface closure, not
uncontrolled top-level expansion:

1. resolve or formally provision the G05/G08 geometry registrations;
2. obtain released base bolt/pin/connector fields and six-dimensional loads;
3. approve one stowed joint vector and rear-support contact frame;
4. establish one common spacecraft coordinate system and non-duplicated native
   integration assembly;
5. verify all named states and continuous solar/arm release clearances;
6. only then generate candidate URDF, collision meshes, MJCF, USD, and
   free-floating simulations.
