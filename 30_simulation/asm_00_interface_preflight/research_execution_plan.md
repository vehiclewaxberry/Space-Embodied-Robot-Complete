# ASM-00 Interface Preflight and Classifier — Research Execution Plan

## State truth

- Baseline commit: `c7f09ab80580f5810d75253fd836d412aa862460`.
- HAG-A, HAG-B, and HAG-I are absent at their canonical paths.
- `interface_ssot_draft.yaml` remains `PROVISIONAL_DRAFT_FOR_PLANNING` and
  contains eight success criteria.
- RF-1/RF-2/RF-3 and the pin-spacing/chamfer/source gaps are open.
- The PI launch manifest requires a versioned nine-criterion evaluator before
  HAG-A, while forbidding the implementation agent from creating approval.
- This worktree has Git-equivalent source content but CRLF raw bytes, so the
  PI-manifest raw SHA-256 bindings do not match locally. Raw and LF-normalized
  hashes must therefore be reported separately and raw mismatch must block.

## Scientific question

Can the current interface draft enter ASM-00 qualification without silently
resolving missing authorization, geometry, friction, or clearance semantics?

## Hypothesis

The current draft cannot enter scientific qualification. A deterministic
classifier will preserve RF-1/RF-2/RF-3 as blocked or repeat evidence, while a
separate nine-criterion contract can be frozen without conferring approval.

## Scope

Owned path only:

`30_simulation/asm_00_interface_preflight/`

No file under `10_research/on_orbit_assembly/`, `20_engineering/config/assembly/`, frozen
`30_simulation/`, SAFE, CTRL, geometry, ASM-01, or ASM-02 is modified. No physics solver,
Monte Carlo experiment, hardware action, VLA, Wave B, or HIL is run.

## Contract freeze

`contracts/assembly_success_evaluator_v1.yaml` is the only evaluator definition
in this owned implementation. It contains nine tri-state criteria, uses SSOT
references for numeric tolerances, and grants success only when all nine are
`PASS`. The contract is explicitly `FROZEN_PENDING_HAG_A_BINDING` and has no
authorization effect.

## Baseline and classifier

The preflight verifies:

1. execution HEAD and branch;
2. HAG-A/HAG-B/HAG-I absence across the execution and planning roots;
3. raw and LF-normalized hashes for the base task card, draft SSOT, and gate
   registry;
4. launch-manifest and authorization-overlay hashes;
5. success-contract structure and frozen hash;
6. owned/forbidden path guard;
7. RF-1 guide-radii and capture-closure inputs;
8. RF-2 friction/material/surface/margin inputs and nominal wedge inequality;
9. RF-3 clearance semantics and both diameter/radius angular branches;
10. pin spacing and chamfer critical fields.

The classifier reads the draft without changing it.

## Designed negative tests

- Missing HAG-A must block.
- Raw-byte mismatch must remain distinct from LF-normalized equivalence.
- RF-1 must block when mouth/throat radii are absent.
- RF-2 must block when material/surface/margin provenance is absent and must
  repeat when the wedge inequality fails.
- RF-3 must block when clearance semantics are absent and must repeat when the
  declared angular tolerance exceeds the derived limit.
- Eight or duplicated evaluator criteria must fail contract validation.
- Any `UNKNOWN`/`BLOCKED`/`REPEAT` RF state must prevent qualification.

## Acceptance gate

The current baseline is expected to produce:

- raw verdict: `ASM00_AG0_BLOCKED_BY_INTERFACE`;
- external status: `ASM00_BLOCKED_BY_MISSING_PARAMETERS`;
- `interface_qualification_granted=false`;
- `scientific_execution_authorized=false`;
- `next_stage_authorized=false`;
- `thresholds_widened=false`;
- an evidence manifest binding all inputs, source, tests, contract, and result.

This expected negative verdict is not a test fixture override; it is derived
from the live inputs.

## Rollback and stop

Rollback is removal or revert of this new owned directory only. Existing drafts
and frozen modules remain untouched. After tests, gate generation, evidence
freeze, and commit, Agent A0 stops. ASM-01/ASM-02 do not start.
