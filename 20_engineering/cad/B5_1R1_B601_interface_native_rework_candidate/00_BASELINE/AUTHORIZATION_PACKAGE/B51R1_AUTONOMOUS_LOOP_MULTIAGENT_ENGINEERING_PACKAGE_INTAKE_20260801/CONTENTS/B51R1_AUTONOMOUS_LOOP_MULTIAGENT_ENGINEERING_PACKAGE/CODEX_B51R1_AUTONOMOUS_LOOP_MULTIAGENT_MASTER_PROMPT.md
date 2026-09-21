# Codex Autonomous Master Prompt
# B5.1R1 Phase 2 Loop Engineering + Multi-Agent Mechanical Design

## 0. Operating mode

Adopt:

- `B51R1_AUTONOMOUS_ENGINEERING_CHARTER_V1`
- `B51R1_G1A_AUTONOMOUS_ADJUDICATION_V1`

The user's current directive establishes standing delegated authority for reversible,
isolated candidate engineering. Do not ask for routine per-step approval.

Never fabricate a human signature. Machine-ratified records must use:

- `authority_type=OWNER_STANDING_DELEGATION`
- `delegation_charter_path`
- `delegation_charter_sha256`
- `agent_quorum`
- `red_team_status`
- `machine_evidence_paths`

Human approval remains required only for non-delegable actions defined in the Charter.

## 1. First autonomous action: close G1A

Without starting SolidWorks:

1. Verify the 19-file S00/G1 workset and ZIP hash.
2. Apply the datum decision:
   - 101.65 axis
   - 110.15 load-bearing surface
   - 113.15 removable panel layer
   - 105.65 historical/no-drive.
3. Replace the counterintuitive pending naming scheme with
   `JOINT_SIDE_EXPLICIT_V2`.
4. Generate a read-only old-to-new alias register.
5. Refreeze all naming-dependent CSV/YAML/contracts.
6. Apply the 14 nominal numerical tolerances and the bounded repeatability policy.
7. Quarantine the exact 6-byte stale Stage A lock file after hash verification.
8. Prove Stage A bytes/hash unchanged.
9. Mark OS attributes accurately as policy-read-only with hash guard.
10. Regenerate:
    - comprehensive expected manifest V2;
    - input lock V2;
    - G1A machine ratification receipt;
    - findings disposition;
    - claim matrix;
    - G1B standing S01 admission.
11. Close only G1A-scoped findings with machine evidence.
12. Retain the 19 downstream findings as named `DEFERRED_HOLD`.
13. Run A7 red team.
14. If no G1A-scoped Critical/High remains, set:
    `G1A_PASS_DELEGATED_MACHINE_RATIFIED_AND_HASH_LOCKED`.

## 2. Automatic S01–S06 session progression

After G1A passes, automatically consume standing session budget.
Each session has one primary goal and must close normally before the next.

### S01 — Master Skeleton authoring

Create only:

`B51R1_MASTER_SKELETON_V2.SLDPRT`

Requirements:

- zero solid bodies;
- zero external references;
- zero mass contribution;
- configurations:
  - COMMON_CANONICAL
  - MODE_A_EVALUATION
  - MODE_B_EVALUATION
- exact authorized datum;
- JOINT_SIDE_EXPLICIT_V2 naming where applicable;
- keepout placeholders remain `TBD/HOLD`;
- Stage A, URDF, V2.2 and diagnostic part remain read-only.

### S02 — Skeleton cold reopen

Verify features, transforms, configurations, hash, zero body, references and mass.
No Carrier creation.

### S03 — Create 10 Carriers

Create in accepted link order. Stop at first failed Carrier.
Every Carrier uses:

- CS_LINK_<LINK>
- CS_JOINT_<incoming_joint>_CHILD_SIDE when applicable
- CS_JOINT_<outgoing_joint>_PARENT_SIDE when applicable
- AXIS_<incoming_moving_joint>
- PLANE_ZERO_<incoming_moving_joint>
- CS_VISUAL_MOUNT_<LINK>

Every Carrier:

- zero bodies;
- zero external references;
- zero CAD mass;
- BOM excluded;
- accepted URDF hash property.

### S04 — Cold reopen 10 Carriers

Read back each feature and transform.
No assembly creation until 10/10 pass.

### S05 — J00..J09 and T005-A0/B0

Build in exact order:

- J00 baseline
- J01 joint1
- J02 joint2
- J03 joint3
- J04 joint4
- J05 joint5
- J06 joint6
- J07 gripper_joint fixed
- J08 gripper_joint1 independent P
- J09 gripper_joint2 independent P

Rules:

- one native driver per moving joint;
- native Limit Angle/Distance;
- no imported face/edge mates;
- no Move Component or Transform2 as driver;
- no single gripper width parameter;
- joint2/joint3 sign probes use interior q_probe;
- J6 branch index recorded;
- explicit same-document q0 reset.

Run carrier-only T005-A0 and T005-B0.
T005-B0 failure blocks S06 and fine geometry.

### S06 — T005-C0

Controlled save, close, normal exit, new process cold reopen, read back all 9 joints,
limits, branch, q0, configurations, references and mass.

## 3. Autonomous Phase 2B — Fine B601 geometry

When G5 passes:

1. Attach geometry only by `CS_VISUAL_MOUNT_<LINK>`.
2. Maintain unique link ownership.
3. Do not allow fine imported geometry to drive motion.
4. Resolve missing URDF STL dependency by:
   - locating authoritative local meshes; or
   - exporting candidate visual/collision meshes from attached geometry;
   - never silently inventing files at referenced paths.
5. Produce B601-M01..M11 candidates.
6. Produce the 10 unified frames, but treat `CS_GRASP_CENTER` as a runtime
   q/contact/object-dependent definition plus reference configuration witnesses.
7. Run formal T005-A/B/C.

## 4. Autonomous Phase 2C — Interface and stowage candidates

Preserve H9 dual branch unless an authoritative launcher/deployer ICD exists.

Generate and score A/B/C adapter concepts using:

- real load path;
- panel bypass;
- root wrench path;
- channel/tool access;
- mass trend;
- stiffness trend;
- maintainability;
- H10 closure ability;
- Mode A/B compatibility.

Automatic downselect is permitted for a candidate branch when:

- A1, A4, A5 and A6 approve;
- A7 has no Critical/High;
- the result is marked `ENGINEERING_CANDIDATE_NOT_FLIGHT_ARCHITECTURE`.

Generate G07/G08/HDRM candidates with:

- contact frames;
- constraint Jacobian rank;
- unilateral contact;
- friction/preload/compliance placeholders;
- tolerance corner analysis;
- no rigid overconstraint;
- release residual keepout.

Close H10 only row-by-row with measurements and hashes.

## 5. Autonomous Phase 2D — Integration and clearance

Create the top integration candidate and all named states.

Split clearance into:

- G8a rigid nominal continuous clearance;
- G8b robust clearance with structural/thermal/tolerance/harness/backlash margins.

Do not substitute G8a for G8b.

Solar failure branches remain fail-closed:
no automatic arm release without solar deployment confirmation.

## 6. Autonomous Phase 2E — Preliminary structure, mass and controls

Only preliminary unit-load/modal work without formal load spectrum.

Generate:

- root interface 6×6 stiffness/compliance candidate;
- modal candidate and participation;
- three distinct mass/inertia ledgers;
- draft mechanics-control handoff;
- FIXED_BASE_DEBUG;
- FREE_FLOATING_VALIDATION candidate;
- typed SAFE/UNKNOWN/interlock contract draft;
- candidate drawings/BOM/ICD/STEP/PDF.

All unknown actuator, material, friction, compliance, sensor and load parameters remain
`PROVISIONAL_TBD`.

## 7. Autonomous exception handling

Do not ask the user for routine decisions.

On a delegated-scope failure:

1. preserve first failure;
2. attempt at most two technically distinct recovery methods;
3. run red team;
4. choose the lower-risk reversible branch;
5. continue if current Gate can pass;
6. otherwise produce `AUTONOMOUS_EXCEPTION_PACKAGE` and stop only the blocked branch.

Ask the user only if the issue is non-delegable.

## 8. Reporting

At major Gate boundaries report:

- authority/input hashes;
- assets created;
- machine tests;
- agent quorum;
- red-team findings;
- closed findings;
- deferred holds;
- current Gate;
- next autonomous action.

Do not request approval after every Gate.
