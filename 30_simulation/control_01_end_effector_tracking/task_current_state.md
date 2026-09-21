# CTRL-01 current state (CTRL-01-R)

Date: 2026-07-19
Branch baseline: `926522f199cae3b9d88ee6797089d57300fea994`
Remediation base (v0 loop evidence): `20cc50b937f2effc9d8f6f151f2ffd231424362e`
Preregistration:
`10_research/partner_requirement_closure/wave1_repeat/repeat_preregistration.md`

## State truth

- Frozen evidence: sim_10 `SIM10_GATES_PASS`; sim_11
  `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS` with
  `next_stage_authorized=true`; sim_12 `SIM12_PHASE1_GATES_PASS`.
- Ownership is limited to `30_simulation/control_01_end_effector_tracking/**` and
  `20_engineering/config/control_scene/**`. No frozen sim, research file, registry, or other
  Wave 1 module is modified.
- This task does not emit a formal safety classification. The cross-module
  safety contract remains an integrator dependency.
- All gate thresholds are the frozen v0 values; none was rewritten.

## CTRL-01-R remediation ledger

| Repeat item | Status | Evidence |
|---|---|---|
| R-3 energy audit | FIXED (defect) | ledger 7.90e-2 -> 5.63e-12; W_ctrl was present in v0; defect was rectangle-rule ledger over first-order map; FOH + per-interval DOP853; threshold 1e-9 unchanged |
| R-2 T3 trigger freeze | DONE | method-specific T2 t=15 s full state + 3 deg/s phase continuation; `t3_trigger_states` recorded; all six T3 reruns |
| R-2 collision evidence | EVALUATED, subitem PASS | static/target/combined at all 3,006 nodes, combined min +0.01462 m (v0 static -0.02537 m was the mismatched-contract artifact) |
| R-3 C2_MATCH5 comparator | DONE | 18-run matrix; C3 isolated nullspace effect +1.84e-5 % = genuine null; C1_MATCH5 comparison demoted to context |
| Error-bound/limits/singularity/speed/accel triage | TRUE NEGATIVES | preserved: T1 anchor limit conflict (-1.048 rad), T1 singular start (sigma 6.64e-5), T3 retreat limits/speed, engage-transient accel 9.11, C1-T3 bound 0.1902 m > 0.11 m |
| v1.0 negative results | PRESERVED | C2 -51.91%, C3 overall -7.99% verbatim in gate JSON |

## Machine Gate (results/control_01_gate_check.json)

Verdict: **REPEAT** (`next_stage_authorized=false`). Tests 22/22 PASS
(tests are not the Gate).

| Gate | Status |
|---|---|
| A1 open-loop flexible anchor (3.5e-11 deg) | PASS |
| A2 closed-loop C1-T1 anchor (0.1550 > 0.05 deg; C2 diagnostic 0.0064) | REPEAT |
| A3 open-loop rigid anchor (3.6e-10 deg) | PASS |
| B conservation + energy (7.2e-16 / 5.6e-12) | PASS |
| C C0/C1 differentiation (ratio 1238.4) | PASS |
| D incremental effectiveness (C2 -38.26%; C3 isolated null) | REPEAT |
| E constraints (limits/singularity/speed/accel; collision subitem PASS) | REPEAT |
| F bounded error (C1-T3, C1_MATCH5-T3) | REPEAT |
| G portable hash lock | PASS |
| H fast-plant/SSOT equivalence (4.44e-16) | PASS |

The remaining REPEAT items are adjudicated true negatives under frozen
thresholds and scenarios (dispositions in `docs/control_01_report.md` sec 7.4);
turning them into passes would require preregistered scenario/threshold
changes that this loop is not authorized to make.

## LOOP ledger

| LOOP | Status | Evidence |
|---|---|---|
| 0 state truth | PASS | gate JSON audit, remediation base `20cc50b` |
| 1 contract freeze | PASS | `20_engineering/config/control_scene/control_01_v0.yaml` (v1 schema, thresholds unchanged) |
| 2 baseline reproduction | PASS | `results/baseline_reproduction.json` |
| 3 minimum implementation | PASS | FOH + solver-grade ledger + FastPlant equal-output path |
| 4 preregistered matrix | PASS | 18 runs incl. C2_MATCH5 (`experiment_matrix_v0.yaml` v1) |
| 5 machine Gate | REPEAT | ten-item `results/control_01_gate_check.json` |
| 6 independent red team | PENDING_REVIEW | deliberately not self-certified |
| 7 evidence freeze | see `results/loop7_evidence_manifest.json` | regenerated at the CTRL-01-R evidence commit |

## Frame conflict closure

Unchanged from v0: T1 composes the actual A1 base motion plus FK into an
inertial reference; the twist is rotated into the current S frame before J*.
A pure-S FK path remains a C0 kinematic diagnostic only.

## Known preregistered conflict

The exact 19.20 degree anchor uses joint2 `+60 deg`, outside the URDF interval
`[-pi, 0]`. The anchor is preserved and the constraint conflict reported;
the machine Gate therefore stays `REPEAT` on the joint-limit item even with
all software tests passing.
