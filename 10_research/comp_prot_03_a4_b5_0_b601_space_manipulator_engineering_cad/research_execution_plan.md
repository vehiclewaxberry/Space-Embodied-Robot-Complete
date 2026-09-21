# COMP-PROT-03-A4-B5.0 B601 Space Manipulator Engineering CAD

## Approval basis

The user authorized decision-related geometry work, including native SolidWorks CAD, on 2026-07-28. The attached authorization explicitly permits new isolated SLDPRT, SLDASM, SLDDRW, STEP, STL, candidate URDF, MJCF/USD support assets, and validation scripts while prohibiting changes to frozen baselines and the accepted B601 dynamics truth.

This plan records that authorization before implementation. It does not expand it.

## Scientific and engineering question

Can an isolated engineering-readable B601 space-manipulator candidate be built so that:

1. the accepted B601 URDF remains the sole kinematic and model mass/inertia truth;
2. vendor B601 geometry is used only as a visual geometry reference;
3. the spacecraft interface, stowage restraint, end-effector and sensor provisions are mechanically readable;
4. L0 dynamics, L1 native CAD and L2 collision/visual models are traceably separated;
5. every configuration can be reopened and verified without modifying V2.x donors?

## Hypothesis

A clean B5.0 candidate can avoid the V2.3 three-representation failure if it:

- starts from an empty isolated root rather than copying a mixed donor top assembly;
- builds link and joint frames directly from the accepted URDF;
- creates native engineering geometry with explicit functional-envelope labels;
- excludes visual and collision geometry from dynamics mass authority;
- validates every exported STEP geometrically and visually;
- keeps all UNKNOWN, HOLD and negative results intact.

## Governing equations and mapping

The accepted serial chain is preserved as:

`T_S_E(q) = T_S_M · T_M_A0 · Π_j T_parent_joint_j · R_axis_j(q_j)`

For prismatic joints, `R_axis_j(q_j)` is replaced by the signed translation along the accepted joint axis.

The model mass truth remains:

`m_B601 = Σ_i m_i = 4.695555949342986 kg`

where every `m_i`, center of mass and inertia tensor is read from the accepted URDF. No CAD-computed material mass may overwrite these values.

The model-layer contract is:

- L0: accepted URDF topology, axes, limits, mass and inertia;
- L1: native SolidWorks engineering visual geometry and interfaces;
- L2: simplified visual/collision geometry derived from L1 while retaining L0 names and frames.

## Frozen inputs

- `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`
- `20_engineering/cad/spacecraft_layout/arm_b601_v1/meshes_b601_gripper/`
- external pinned vendor STEP `reBot_B601_DM_v1.1_20260425.step`
- V2.2 and V2.2_NATIVE CAD trees, Gates and evidence
- `20_engineering/config/geometry/`
- all `30_simulation/` and SAFE/CTRL Gates

## Owned paths

- `10_research/comp_prot_03_a4_b5_0_b601_space_manipulator_engineering_cad/`
- `20_engineering/cad/B5_0_B601_space_manipulator_candidate/`

All other paths are read-only for this task.

## Implementation phases

### Phase 0 — audit, truth freeze and writer smoke

- generate the source inventory and protected hash seal;
- record truth hierarchy, tools and the clean-empty candidate decision;
- run an isolated SolidWorks part/assembly/drawing/STEP smoke;
- cold reopen and verify all references remain inside the candidate root;
- verify frozen source hashes are unchanged.

Gate: `B5_0_PHASE0_PASS`.

### Phase 1 — accepted chain and Master Skeleton

- parse all accepted links, joints, origins, axes, limits, inertials and meshes;
- emit a frame and assumption ledger;
- create a native B601 skeleton with named joint axes and link frames;
- create the spacecraft body/reference interface skeleton.

Gate: `B5_0_G1_KINEMATIC_SKELETON_PASS`.

### Phase 2 — engineering joint and link geometry

- create six primary revolute joint modules and the accepted auxiliary/fixed/prismatic elements;
- create mechanically readable link shells, flanges, ribs, access panels and harness ports;
- assemble in accepted q0 using source-defined transforms;
- preserve revolute/prismatic DOF semantics.

Gate: `B5_0_G2_ENGINEERING_FORM_PASS_WITH_PROVISIONAL_COMPONENTS`.

### Phase 3 — spacecraft integration

- create base adapter, load-path frame, primary and wrist support, HDRM envelope;
- create provisional capture tool, F/T and camera envelopes;
- create harness routing envelopes and service directions.

Gate: `B5_0_G3_INTEGRATION_HOLD_OR_PASS`, fail-closed on unresolved clearance.

### Phase 4 — configurations, exports and drawings

- build the top assembly and required task configurations;
- export STEP and derived STL;
- create review drawings, BOM and interface views;
- perform cold-reopen, dependency, configuration and collision checks.

Gate: `B5_0_G4_DIGITAL_THREAD_PASS`.

### Phase 5 — candidate simulation model

- create a candidate URDF generator that inherits accepted topology and inertials;
- use L1-derived visual meshes and independently simplified collision meshes;
- emit the layer mapping and kinematic consistency report;
- prepare MJCF/Isaac import reports only when the local runtime exists.

Gate: `B5_0_G5_SIMULATION_MODEL_PASS_OR_TOOL_HOLD`.

## Tests

- accepted URDF 12-file package hash check;
- link/joint count, parent-child, type, axis, origin, limit and inertial equality;
- native document cold reopen;
- non-empty solid and component counts;
- all active production references inside the candidate root;
- configuration existence and suppression readback;
- STEP OCP/CLI cold read;
- `refs --facts --planes --positioning`;
- required measurement/frame/alignment checks;
- mandatory STEP snapshots and visual review;
- candidate output hash manifest;
- before/after protected-baseline hash equality.

## Acceptance policy

Allowed final labels:

- `PASS`
- `PASS_WITH_PROVISIONAL_COMPONENTS`
- `HOLD`
- `FAIL`
- `UNKNOWN`
- `NOT_EVALUATED`

Prohibited unsupported labels:

- flight qualified;
- manufacturing ready;
- launch-load verified;
- space-environment verified;
- generic non-cooperative capture;
- real-time digital twin;
- autonomous VLA grasping implemented.

## Rollback and stop policy

All implementation is additive inside the owned paths. On failure:

- stop SolidWorks writes;
- close and exit the exclusive SolidWorks process;
- preserve logs and partial candidate evidence;
- do not delete or roll back user files;
- do not modify donors to repair broken references;
- mark the exact Gate `HOLD` and report the first blocking artifact.

Any external reference into a frozen CAD tree, accepted-URDF drift, axis mismatch, mass-authority conflict, unknown license, unresolved SolidWorks save state, or manual UI dependency stops the affected phase.
