# B5.1R1 B601 canonical interface and native articulation rework research execution plan

Task ID:

`COMP-PROT-03-A4-B5.1R1-B601-CANONICAL-INTERFACE-AND-NATIVE-ARTICULATION-REWORK`

Status:

`S01_CR01_METADATA_REPAIR_AND_S02_R1_READ_ONLY_REOPEN_AUTHORIZED / S03_NOT_AUTHORIZED`

## Authorization and immutable parent

The user explicitly authorized starting the mechanical-design research described
in the attached B5.1R1 ruling. This authorizes evidence reading, a new controlled
research namespace, fail-closed contracts, and Phase 0 causal analysis. It does
not authorize modification of B5.1, V2.0/V2.1/V2.2, the accepted URDF, the
vendor STEP, simulation Gate files, native SolidWorks authoring, FEA, hardware
motion, manufacturing release, launch qualification, or flight claims.

On 2026-08-02 the owner supplied the S02_SR01 fail-closed recovery directive and
authorized execution of the next concrete recovery operations. This supersedes
the earlier native-CAD prohibition only for the following narrow scope:

- create a byte-identical isolated work copy from the protected Master Skeleton
  V2 candidate;
- add exactly the five registered missing document-level text properties with
  `Add3(swCustomPropertyOnlyIfNew)` and save only a new R1 revision;
- perform a separate-process, read-only cold reopen of R1 with zero save calls;
- preserve V2, Stage A, accepted URDF, input locks, and all prior evidence;
- stop fail-closed on any scope expansion, hash drift, or Critical/High finding.

This authorization does not permit geometry changes, Carrier or joint creation,
S03 entry, FEA, hardware motion, manufacturing release, launch qualification,
or flight claims.

The immutable parent is:

- parent task: `COMP-PROT-03-A4-B5.1-B601-INTERFACE-CLOSURE-ARTICULATION-STOWAGE`;
- parent verdict: `B51_REVISE_INTERFACE_COLLISION`;
- parent Gate SHA-256:
  `DD4286A1826AD6F47AEF81C3685A047786430A6F5BB31D797C206A5A2A91F8D0`;
- inherited blockers: H9 human decision, H10 28 open / 8 unacceptable,
  no accepted 6R run, native 2P missing, native limit mates missing.

## Engineering questions

1. Why did the B5.1 longeron datum use `105.65 mm` when the canonical V2.2
   native source uses `101.65 mm`?
2. Why do both saddle shoes remain exactly `3.0 mm` from primary structure,
   and which physical layer occupies that gap?
3. Which corrected datum and contact definitions can be promoted into Master
   Skeleton V2 without conflating skin, primary structure, pads, clearances,
   or the display and dynamics mount tracks?
4. Which adapter architecture can close all 28 H10 records while preserving
   the D100 passage, named load path, solar keep-outs, serviceability, and H9
   mode uncertainty?
5. Can the accepted `6R + 1 fixed + 2P` topology be represented with unique
   native drivers, native limits, explicit zero references, correct signs, and
   deterministic reset behavior?
6. How should base, G07, G08, contact compliance, and HDRM allocate restraint
   by spacecraft state without creating unqualified rigid overconstraint?

## Hypotheses and falsifiers

### H-DATUM-01 — authority escalation

The `4.0 mm` discrepancy is caused by promoting the V2.0/V2.1
`LONGERON_OFFSET_Y/Z=105.65` design proposal into an admitted B5.1 datum after
the canonical V2.2 native source changed the structural centre to
`101.65 mm`.

Falsifier: a higher-authority frozen source proving that `105.65 mm` is the
canonical V2.2 longeron centre.

### H-DATUM-02 — layer misclassification

The `3.0 mm` saddle-to-primary distance is the removable-panel thickness
layer: primary outer surface `110.15 mm`, panel outer surface `113.15 mm`, and
B5.1 saddle-shoe lower face `113.15 mm`.

Falsifier: exact BREP or a named interface detail showing a different
qualified load-transfer element between the saddle shoe and primary member.

### H-MATE-01 — state-dependent solver/mate defect

The T005 failure is not admissibly explained as cache alone. At least one of
mate ordering/redundancy, driver coverage, zero references, axis/sign,
configuration suppression leakage, rebuild state, or part-local placement can
produce a history-dependent post-rebuild error.

Falsifier: T005-A, T005-B, and T005-C all pass with one source model and no
hidden document reload between sequential poses.

### H-STOW-01 — compliant state allocation required

A base + G07 + G08 launch-restraint architecture requires explicit state and
direction allocation plus at least one qualified compliance/error-accommodation
mechanism to avoid unqualified six-DOF rigid overconstraint.

Falsifier: a contact/constraint model proving a determinate or intentionally
redundant qualified load path with tolerances and stiffness evidence.

## Governing checks

- Datum difference:
  `delta_d = d_B51 - d_canonical`, reported per axis and rotation, never as an
  instruction to translate geometry.
- Layer identity:
  compare canonical primary and panel BREP faces separately; zero common
  volume or zero minimum distance does not prove attachment.
- Interface placement:
  `p_S = T_SM * p_M`, with display-track and dynamics-track values kept as
  separate authorities until H9/track adjudication.
- Kinematic chain:
  `T_0_i(q) = product(T_parent_joint * JointMotion(axis_i, q_i))` from the
  accepted URDF only.
- Pose errors:
  position norm, relative-rotation angle, and maximum homogeneous-transform
  element are recorded separately.
- Restraint allocation:
  contact Jacobian rank and redundant constraint directions must be explicit;
  load sharing is not inferred from a sketch or three-point naming.
- H10 closure:
  every inherited row retains pre/post exact volume, pre/post minimum distance,
  classification, root-cause cluster, responsible part, geometry change,
  before/after local evidence, replacement hash, and closure status.

## Work packages and dependencies

1. **R0 Parent freeze** — record Gate and source hashes; verify B5.1 remains
   unchanged.
2. **R1 Phase 0 causality** — resolve the authority chain for 4 mm and the
   physical layer chain for 3 mm; keep mount-track and H9 conflicts explicit.
3. **R2 Master Skeleton V2 contract** — machine-readable frames, contact
   planes, normals, tangents, keep-outs, and authority records. Native CAD is a
   later human-authorized action.
4. **R3 Parallel rework contracts** — H10 row-by-row closure and complete
   `6R + 1 fixed + 2P` native articulation.
5. **R4 Stow restraint and adapter trade** — state/DOF matrix plus A/B/C
   architecture comparison; no selection by unsupported score.
6. **R5 Geometry implementation** — blocked until the named Phase 1 human
   Gate.
7. **R6 Continuous clearance and structural trends** — blocked until candidate
   G2/G3 closure and G4 geometry freeze.

## Files and ownership

- Research root:
  `10_research/comp_prot_03_a4_b5_1r1_b601_canonical_interface_native_articulation_rework/`
- Engineering research root:
  `20_engineering/cad/B5_1R1_B601_interface_collision_and_articulation_rework_candidate/`
- Immutable parent:
  `20_engineering/cad/B5_1_B601_interface_closure_candidate/`
- Frozen external truths: accepted B601 URDF, vendor STEP, canonical V2.2
  native tree and manifests, B5.0 evidence, all simulation and competition
  Gate files.

## Tests and acceptance Gate

Phase 0 exits only when:

1. the parent Gate hash is current and all locked source hashes match;
2. the 4 mm and 3 mm observations are tied to explicit source fields and BREP
   evidence;
3. alternative explanations are classified as confirmed, refuted, or
   measurement-required;
4. no B5.1 file or frozen source changes;
5. H9, mount-track, material, fastener, preload, tolerance, load, stiffness,
   and qualification unknowns remain open;
6. the Master Skeleton V2 CAD brief and later validation targets exist;
7. the next human Gate is explicitly named.

Phase 0 success is a research result, not G2/G3/G4 acceptance.

## Rollback and stop rules

- All B5.1R1 assets are additive; no overwrite of parent evidence.
- If any parent/frozen hash drifts, stop with
  `B51R1_BLOCKED_PARENT_BASELINE_DRIFT`.
- If source authorities conflict, preserve both and set
  `HUMAN_ADJUDICATION_REQUIRED`.
- Do not open/save native CAD, run FEA, execute hardware, or start continuous
  clearance under this plan-only/Phase-0 authorization.
- Failed or refuted hypotheses remain in the audit; they are not deleted.

## Next human Gate

`COMP-PROT-03-A4-B5.1R1-PHASE1-MASTER-SKELETON-V2-AND-NATIVE-REWORK-AUTHORIZATION`

Requested authorization at that Gate must separately state whether native
SolidWorks authoring and/or STEP-source modification is allowed. Approval does
not automatically authorize FEA, simulation, manufacturing, hardware motion,
launch qualification, or flight claims.
