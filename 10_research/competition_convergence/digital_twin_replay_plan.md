# Competition DT2 Offline Evidence Replay Plan

> Agent C evidence freeze candidate — 2026-07-20
>
> Scope: `DT2_CURRENT_SCOPE_OFFLINE_EVIDENCE_REPLAY`
>
> This is not a real-time digital twin, produces no command, and grants no execution authority.

## 1. State truth and question

The approved source snapshot is Git commit
`c7f09ab80580f5810d75253fd836d412aa862460`. The replay reads the frozen
sim10, sim12, SAFE-00 and CTRL-02 artifacts; it does not run their solvers or
alter any Gate.

The engineering question is narrow: can the three competition cases be
replayed deterministically from verified artifacts while preserving every
join limitation, negative result, provisional field and missing authorization?

Hypothesis: strict raw/canonical hashes, unique row keys and fail-closed
scenario rules are sufficient to produce byte-stable records for A, B and C
without recomputing physics.

## 2. Frozen evidence contract

`mission_demo_contract.yaml` binds:

- the approved base commit and frozen threshold-registry hash;
- raw-byte hashes for every source;
- the source-native canonical JSON/YAML/CSV hash mode;
- the source commit for each artifact;
- exact Gate verdict/review/provisional fields;
- the record vocabulary and the `EXACT / GLOBAL_ONLY / REFERENCE_ONLY /
  NOT_APPLICABLE` join semantics;
- `command_emitted=false`, `execution_authority=false`, and
  `UNKNOWN` never upward-reclassified.

The verifier also checks that the approved-base and historical source-commit
blobs match current bytes. Any mismatch is a hard stop.

## 3. Scenario extraction rules

### A — EXECUTE explanation only

- Mission case: exact `strategies_v0.yaml:cases.A_low`.
- sim10: `GLOBAL_ONLY`. There is no exact 0.5 deg/s A row in the sim10 Gate;
  the satellite anchor must not be silently substituted.
- sim12: exact `A_low|S1_passive` row and exact GS2 best-strategy result.
- SAFE-00: exact registered candidate `A_low-S1_passive` and exact row hash.
  This proves a candidate binding, not a mission authorization. No actual
  authorization request/response exists; the Gate remains
  `PENDING_REVIEW` with `next_stage_authorized=false`.
- CTRL-02: exact A/B1 post-capture resource-evaluation row. It is not called
  the S1 capture strategy. Its transient result is limited to the R5
  `PROVISIONAL_L1_MOMENTUM_ACTUATOR` model; L0 hardware-valid stability is not
  evaluated.
- Display: `EXECUTE` means an explanation-only recommendation.
  `command_emitted=false` and `execution_authority=false` are immutable.

### B — upstream ABORT

- Mission case: exact `cases.B_anchor`.
- sim10: exact `debris_sim06` anchor, `INFEASIBLE_RATE`.
- sim12: all four exact B rows remain `INFEASIBLE`; GS2 selects `ABORT`.
- SAFE-00: `NOT_APPLICABLE_UPSTREAM_ABORT`; no request or response is created.
- CTRL-02: omitted from the executable chain. All B rows are preserved only as
  out-of-feasible-region counterfactual evidence.
- Display: `ABORT`, bounded to the frozen inputs and four-strategy set.

### C — strategy MODIFY

- Mission case: exact `cases.C_transition`.
- sim10: `GLOBAL_ONLY`; there is no exact C row in the sim10 Gate.
- sim12: exact S1 row is `INFEASIBLE/WHEEL_MOMENTUM`; exact S3a row is
  `FEASIBLE/NONE`; GS2 selects `S3a_wheel_bias`.
- SAFE-00: `MISSING_REGISTERED_CANDIDATE`; only
  `A_low-S1_passive` is registered. No C request or response is created.
- CTRL-02: all four C rows are retained as `REFERENCE_ONLY`. They are
  post-capture controllers, not the S3a capture strategy.
- Display: `MODIFY` means replace the candidate with S3a and re-enter a future
  authorization process.

## 4. Deterministic implementation

The implementation uses only Python, PyYAML, Git reads and the Python standard
library:

1. strict JSON/YAML duplicate-key rejection and finite-number enforcement;
2. strict CSV headers, row width and unique key checks;
3. raw and source-native canonical hash verification;
4. approved-base/source-commit blob verification;
5. exact selector, row and nested-object hashes;
6. scenario-specific fail-closed semantic checks;
7. deterministic sorted JSON with no timestamp or host-dependent absolute path.

The committed replay package is:

```text
10_research/competition_convergence/results/replay/
  replay_manifest.json
  scenario_A_low.json
  scenario_B_anchor.json
  scenario_C_transition.json
```

The files are evidence-neutral data records. PPT and video tooling may consume
them later, but media is not a Gate source.

## 5. Machine commands

Run from the repository root:

```powershell
python 10_research/competition_convergence/tests/run_all.py

python 10_research/competition_convergence/src/verify_evidence_contract.py `
  --contract 10_research/competition_convergence/mission_demo_contract.yaml `
  --scenarios 10_research/competition_convergence/three_scenario_manifest.yaml `
  --output 10_research/competition_convergence/results/evidence_verification.json

python 10_research/competition_convergence/src/build_offline_replay.py `
  --contract 10_research/competition_convergence/mission_demo_contract.yaml `
  --scenarios 10_research/competition_convergence/three_scenario_manifest.yaml `
  --output 10_research/competition_convergence/results/replay
```

The test runner is executed twice. The second run must reproduce the same
deterministic test report and replay hashes.

## 6. Machine Gate and red team

Agent C stops only when all of these are true:

- every frozen raw/canonical/source-commit/base-commit hash matches;
- all three cases and selected rows are unique and exact;
- A/B/C actions and joins match the frozen rules;
- the eleven-field claim matrix is complete and source-bound;
- no diff exists outside `10_research/competition_convergence/`;
- two consecutive test/build runs are byte-stable.

The test suite contains fifteen named adversarial units:

- physics/provenance: raw drift, canonical drift, duplicate row, case-key/hash
  mismatch, and cross-stage strategy/controller conflation;
- safety/claims: A candidate rebinding, command emission, fabricated B SAFE
  request, promoted C binding, and promoted SAFE next-stage authority;
- reproducibility/scope: promoted B counterfactual, missing watermark, widened
  ownership, removed provisional limitations, and stale hidden output.

An attack passes only when it is rejected fail-closed. A list of tests is not
evidence until the runner reports `planned=15, completed=15, passed=15`.

## 7. Claim boundaries

Allowed:

- verified-artifact-driven deterministic offline evidence replay;
- A `EXECUTE` explanation only, with exact candidate registration and no
  execution authority;
- B upstream `ABORT` under the frozen inputs and strategy set;
- C `MODIFY` to S3a with missing SAFE binding and CTRL-02 reference-only;
- CTRL-02 statements only with `PASS_WITH_PROVISIONAL_SCOPE`,
  `PENDING_REVIEW`, R5 provisional actuator/time-window and L0-not-evaluated
  limitations.

Forbidden:

- completed autonomous on-orbit assembly;
- real-time digital twin or online synchronization;
- command output, real SAFE authorization or flight-qualified safety;
- free-floating hardware validation;
- markerless VLA generalization;
- final flexible assembly certification;
- treating B counterfactual control as executed;
- treating C CTRL-02 rows as S3a validation;
- replacing `UNKNOWN`, `REPEAT`, `PROVISIONAL`, `PENDING_REVIEW` or a missing
  binding with success.

## 8. Rollback and stop

All outputs are confined to this owned directory. Rollback removes or reverts
only the Agent C commit; frozen artifacts remain untouched. On any hash drift,
duplicate key, missing row, ambiguous join, scope violation, upward
reclassification or nondeterministic output, freeze the negative evidence and
stop. Do not rerun sim10/sim12/SAFE-00/CTRL-02, widen thresholds, create a SAFE
request, or continue into report/PPT/video/final Gate work.
