# B5.0 Loop Engineering Review Log

## Round 1 — baseline and constraints

Finding:

- The accepted B601 URDF is the only kinematic, mass, and inertia authority.
- V2.x top-level/native assets and accepted evidence remain read-only.
- G05/G08 are not direct registrations.
- B106 was not found in the bounded Phase-0 search.

Action:

- Created an isolated candidate root and protected-hash seal.
- Extracted the accepted 10-link/9-joint chain and exact source mass.
- Kept display and dynamics tracks explicit.

Evidence:

- `00_AUDIT/phase0_gate.json`
- `01_KINEMATICS/accepted_chain.json`
- `07_VERIFICATION/protected_hash_verification.json`

Result:
`PASS_WITH_G05_G08_HOLD`

## Round 2 — mechanical structure

Finding:

- Vendor B601 geometry can provide detailed visual reference without replacing
  URDF truth.
- A fixed q0 reference is useful for geometry registration, but it cannot be
  called a retained SolidWorks mechanism.
- The approved evidence supports a three-layer base-adapter reference envelope,
  not released holes, bolts, pins, material, loads, or manufacture.
- The pre-existing V2.2 adapter proposal conflicts with the Gate-0 stack and
  has no manufacturing authority.

Action:

- Generated eight native link-local reference parts, a master skeleton, fixed
  q0 assembly, drawing, and STEP.
- Generated a separate three-part
  `B601_BASE_ADAPTER.SLDASM` reference run.
- Embedded `UNKNOWN`, `TBD`, `MANUFACTURING_AUTHORITY=NONE`, and
  `LOADS_UNKNOWN_BLOCKED` properties.
- Retained the first failed base-adapter diagnostic run.

Evidence:

- `03_CAD/native_runs/B50_NATIVE_20260727T2214Z`
- `03_CAD/native_runs/B50_BASE_REF_20260728T0029Z`
- `02_DESIGN/B601_BASE_ADAPTER_DESIGN.md`

Result:
`Q0_REFERENCE_PASS / BASE_REFERENCE_PASS / PHYSICAL_DESIGN_HOLD`

## Round 3 — digital thread

Finding:

- Early-bound `IMathUtility.CreateTransform(list)` silently produced identity
  transforms.
- The direct STEP sidecar path in cadpy 0.3.9 exited zero without producing
  requested STL/native GLB.
- The standard large-q0 CAD snapshot browser failed three times.
- Base-adapter geometry is small enough for the standard CAD snapshot path.

Action:

- Used a typed `VT_ARRAY|VT_R8` SAFEARRAY and verified transform input,
  post-set, post-fix, and cold-reopen values.
- Generated q0 previews through the validated internal output path without a
  STEP writer and preserved the STEP hash.
- Invalidated the first blank VTK fallback and accepted only the second image
  after an explicit foreground-pixel gate.
- Re-ran `inspect refs --facts --planes --positioning` and persisted receipts
  for both native runs.
- Cold-read both STEP files with OCP and reconciled solids and bounding boxes.

Evidence:

- `03_CAD/native_runs/B50_NATIVE_20260727T2214Z/evidence/math_transform_marshalling_diagnostic.json`
- `03_CAD/native_runs/B50_NATIVE_20260727T2214Z/evidence/step_sidecar_generation.json`
- `03_CAD/native_runs/B50_NATIVE_20260727T2214Z/evidence/visual_review_adjudication.json`
- `03_CAD/native_runs/B50_BASE_REF_20260728T0029Z/evidence/cad_cli_inspect_refs.json`

Result:
`CAD_TO_STEP_TRACE_PASS / SIMULATION_THREAD_PARTIAL`

## Round 4 — adversarial review

Independent checks found and resolved:

- Gate artifact paths initially mixed run-relative and candidate-relative
  bases; all q0 artifact paths were normalized.
- Gate time initially preceded the later CAD CLI receipt; amendment history was
  added without changing the original generation time.
- The nine q0 components were clarified as eight geometry parts plus one
  zero-solid skeleton; the 388 solids are not attributed to the skeleton.
- The no-DOF limit was expanded to include both the 6R arm and 2P gripper.
- The first q0 visual fallback was proven blank and explicitly invalidated.
- The first base-adapter rectangle run failed before CAD output and remains
  retained as HOLD evidence.
- The first base isometric view occluded the three layers; two additional
  review views were generated, including a right-face exploded view that shows
  two square layers and the circular boss.

Unresolved adversarial findings:

- q0 is neither an approved stowed state nor a continuous release path.
- Master Skeleton points/segments do not yet constitute named native joint
  mates.
- Phase-2 engineered joint support, load transfer, maintenance, sensor, and
  harness detail is incomplete.
- The base adapter has no released physical interface or load case.
- No common V2.2/B601/solar/HDRM/harness top-level model exists.
- No full-state or continuous-clearance evidence exists.
- No candidate URDF/MJCF/USD or free-floating simulation has been accepted.

Result:
`PARTIAL_ACCEPTANCE_WITH_EXPLICIT_HOLDS`
