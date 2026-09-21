# CTRL-01 end-effector tracking baseline (CTRL-01-R remediated)

This module implements the Wave 1 minimum resolved-rate comparison:

- C0: fixed-base geometric Jacobian, feedback only;
- C1: free-floating generalized Jacobian J*, feedback only;
- C2: J* plus the frozen inertial-reference feedforward;
- C3: C2 plus an exact-SVD reaction nullspace term, only for `approach_5d`;
- C1_MATCH5 / C2_MATCH5: matched 5D-task controls (C2_MATCH5, added by the
  repeat preregistration, is the isolated-nullspace comparator for C3).

The plant is the read-only sim_11 `CoupledModel`, accessed through the
machine-cross-checked `fast_plant.py` equal-output path (fail-closed against
the frozen SSOT at every run; worst normalized error ~1e-16). The control
loop samples at 10 ms; the commanded joint rate is applied as a first-order
hold and the state plus the work/damping energy ledgers are propagated by
per-interval adaptive DOP853 (rtol 1e-11) on the reduced zero-momentum
manifold. T1 composes the actual base motion and arm FK into an inertial
end-effector reference; it does not feed a pure-S FK path to J*.

## CTRL-01-R remediation (2026-07-19)

Per `10_research/partner_requirement_closure/wave1_repeat/repeat_preregistration.md`
(R-2/R-3), with every gate threshold frozen:

1. Energy audit: diagnosed as an accounting/discretization defect. W_ctrl was
   already in the v0 ledger; the 7.9e-2 residual came from a rectangle-rule
   ledger over a first-order state map. The remediated solver-grade ledger
   closes the audit far below the unchanged 1e-9 threshold.
2. T3 collision evidence: every method's T3 now starts from that method's
   frozen T2 t=15 s full state (base/joint/modal) with the target continuing
   the frozen sim09 const-omega 3 deg/s propagation; static, target and
   combined margins are evaluated at every fixed 10 ms node.
3. C2_MATCH5 was added before any isolated nullspace comparison; the C3
   isolation claim is now adjudicated against C2_MATCH5, and the old
   C1_MATCH5 overall-scheme comparison is context only.
4. Remaining failures were triaged implementation-defect vs true negative;
   only defects were fixed, and true negatives are preserved (including the
   v1.0 C2 −51.91% and C3 −7.99% records, kept in the gate JSON).

## Current adjudication

`results/control_01_gate_check.json` is the only scientific adjudication;
tests are not the Gate. See the gate JSON for the current verdict and the
per-gate evidence, and `docs/control_01_report.md` section 7 for the
CTRL-01-R disposition of every v0 failure.

C3 with `pose_6d` is refused with `TASK_NULLITY_ZERO`. The independent
physics/control/implementation red-team review is `PENDING_REVIEW`.

## Reproduction

From the repository root:

```text
python 30_simulation/control_01_end_effector_tracking/src/run_experiments.py
python 30_simulation/control_01_end_effector_tracking/tests/run_all.py
python 30_simulation/control_01_end_effector_tracking/src/run_gates.py
```

The full frozen matrix contains 12 main runs plus six matched-5D controls
(C1_MATCH5, C2_MATCH5). With the solver-grade ledger it takes roughly
40-60 minutes on the recorded machine.

## Evidence

- `results/baseline_reproduction.json`: sim_05/10/11/12 baseline and hashes.
- `results/preregistered_matrix.csv`: the frozen 18-run matrix.
- `results/control_01_summary.csv`: one row per run (incl. ledger fields).
- `results/control_01_timeseries.csv`: 50 ms evidence samples with the
  energy/work/damping ledger columns.
- `results/control_01_collision_timeseries.csv`: all 3,006 T3 nodes with
  static, target and combined margins.
- `results/control_01_comparison.png`: comparison figure.
- `results/control_01_gate_check.json`: only scientific adjudication.
- `results/artifacts_sha256.json`: portable text + raw binary hashes.
- `results/loop7_evidence_manifest.json`: LOOP-7 evidence freeze.
- `docs/control_01_report.md`: scope, results, failures, remediation.

Panel response and actuator limits remain provisional. No result here is a
hardware or flight-performance claim.

The config/matrix and their result artifacts are committed together. Their
ordering is a procedural run record, not independent strong preregistration
proof.
