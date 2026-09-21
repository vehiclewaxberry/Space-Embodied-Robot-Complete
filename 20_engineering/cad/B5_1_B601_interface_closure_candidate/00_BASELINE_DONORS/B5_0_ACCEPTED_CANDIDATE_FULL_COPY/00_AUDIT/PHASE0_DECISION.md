# Phase 0 Decision

## Decision

`FRESH_EMPTY_B5_0_CANDIDATE`

The B5.0 candidate does not copy either V2.2 top assembly as a writable seed.

Reasons:

- canonical V2.2 has no complete final tree seal;
- V2.2_NATIVE has a stale all-files manifest and pending human review;
- both trees are currently untracked in a worktree with pre-existing changes;
- copying an assembly can preserve baked references into the frozen source tree;
- the requested deliverable is a B601 engineering candidate, not a silent V2.2 release.

## Reference inputs

- V2.2/V2.2_NATIVE remain read-only layout and interface donors.
- The candidate bus reference is regenerated from documented, named V2.2 display-track dimensions.
- The accepted URDF supplies the complete L0 chain and inertials.
- The pinned vendor STEP supplies visual geometry reference.
- O13 stow geometry is a comparator with `CANDIDATE_HOLD`.

## Isolation

Sole writable CAD root:

`20_engineering/cad/B5_0_B601_space_manipulator_candidate/`

No candidate native assembly may retain a production reference into a V2.x or external vendor CAD path.

## Writer ruling

`SOLE_WRITER=CODEX_PYWIN32_SOLIDWORKS_2024_SP5_EARLY_BOUND`

This ruling supersedes older writer records only for the new B5.0 candidate root. It does not authorize writing V2.x or V3 roots.

## Git/worktree ruling

The current worktree contains pre-existing user changes. The task therefore uses path isolation rather than switching the user's branch or moving existing files. No staging, commit or branch switch is authorized by this decision.

## Phase 0 status

Truth/source audit:

`PASS_WITH_RECORDED_BLOCKERS`

Toolchain precheck:

`PASS_WITH_CORRECTIONS`

Native-write authorization:

`PENDING_ISOLATED_TOOL_SMOKE`

Phase 1 authoring remains blocked until the smoke creates, cold-reopens and validates a new part, assembly, drawing and STEP entirely inside this candidate root while protected hashes remain unchanged.
