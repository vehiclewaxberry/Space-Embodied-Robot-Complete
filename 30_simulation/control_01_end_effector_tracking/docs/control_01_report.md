# CTRL-01 Wave 1 execution report

Date: 2026-07-19
Machine verdict: **REPEAT**
Independent red team: **PENDING_REVIEW**

## 1. What was executed

CTRL-01 now contains a common resolved-rate skeleton for C0-C3, a fixed-step
zero-momentum plant backed by the read-only sim_11 coupled model, the frozen
T1-T3 references, 15 executed comparisons, 17 tests, and a nine-item GC1
machine Gate.

The old T1 frame conflict is closed explicitly. A1 base motion and arm FK are
composed into an inertial end-effector path; its twist is expressed in the
current service-frame S before J* is applied. A pure-S FK path is not used as
evidence for C1. The open-loop fixed-step replay returns
19.1998852108 degrees, only 4.19e-7 degrees from the frozen flexible anchor.

R1 items are frozen in the contract:

- T2 uses the capture-before rate 3.0 deg/s;
- reaction rows use the angular block of `Hbb^-1 Hbm`, with Hbm about the
  base origin;
- the wheel interface records the physical per-axis box of +/-0.100 N m s and
  the 89.1% single-axis occupancy. CTRL-01 does not actuate wheels.

C3 is only defined for a rank-5 approach task. A pose-6D request returns
`TASK_NULLITY_ZERO`; the exact SVD projector has measured leakage
5.51e-16 in the contract test.

## 2. Baseline and matrix

The prerequisite chain passed:

| Frozen module | Test result |
|---|---:|
| sim_05 | 22/22 PASS |
| sim_11 | 27/27 PASS |
| sim_10 | 6/6 PASS |
| sim_12 | 3/3 PASS |

The main matrix is `{C0,C1,C2,C3} x {T1,T2,T3}`, with C3 always in
`approach_5d`. Three `C1_MATCH5` runs provide the same-task comparator for C3.
All methods use the same gain, DLS damping, sample period, references, and
plant. No result-dependent tuning was performed.

The configuration and result files are committed together. The
`frozen_before_*` fields record the execution procedure, but the repository
history does not independently prove a strong preregistration timestamp.
Accordingly this report calls the evidence `PROCEDURAL_ONLY`, while retaining
the unchanged matrix, gains, and thresholds.

## 3. Main T2 result

| Method | Task | Position p95 [m] | Orientation p95 [rad] | Base peak [deg] | Integral base rate [deg] | Panel tip [mm] |
|---|---|---:|---:|---:|---:|---:|
| C0 | pose 6D | 1.3335e-2 | 5.2934e-2 | 15.703 | 17.328 | 0.0535 |
| C1 | pose 6D | 6.9846e-6 | 5.2366e-2 | 18.384 | 20.112 | 0.0785 |
| C2 | pose 6D | 1.0611e-5 | 6.0614e-5 | 19.890 | 21.691 | 0.3321 |
| C3 | approach 5D | 1.0568e-5 | 2.1737e-5 | 19.912 | 21.752 | 0.3430 |

The C0/C1 T2 position-p95 ratio is 1909.26. The correction-map identity
`Jstar - Jm = -Jb Hbb^-1 Hbm` closes to 3.47e-18, so the model
differentiation is machine-backed.

The preregistered incremental hypotheses are negative:

- C2 position p95 is 51.91% worse than C1, not at least 30% better. C2 does
  reduce orientation lag, but that does not satisfy the frozen position Gate.
- The C3 scheme has 7.99% more accumulated base rate and 52.76% worse
  position p95 than `C1_MATCH5`. This is an overall-scheme comparison, not an
  isolated nullspace-effect estimate: the current matrix has no feedforward
  `C2_MATCH5` control.
- The direct within-C3 primary-to-command reaction reduction is only
  9.98e-6%. C3 remains `NULL_RESULT`, not promoted as reaction suppression.

Panel values are relative-only and carry `PROVISIONAL`.

## 4. Nine-item GC1 result

| Gate | Status | Key evidence |
|---|---|---|
| A1 open-loop flexible anchor | PASS | delta 4.19e-7 deg <= 1e-6 |
| A2 C1-T1 closed-loop anchor | REPEAT | delta 0.1725 deg > 0.05 |
| A3 open-loop rigid anchor | PASS | delta 6.94e-7 deg <= 0.05 |
| B conservation and energy | REPEAT | momentum 8.28e-16 PASS; energy 7.90e-2 REPEAT |
| C C0/C1 differentiation | PASS | ratio 1909.26; map error 3.47e-18 |
| D C2/C3 increment | REPEAT | both preregistered benefits are negative |
| E constraints | REPEAT | joint margin -1.968 rad; static margin -0.02537 m; target/combined `NOT_EVALUATED` |
| F bounded error | REPEAT | C1-T3 and C1_MATCH5-T3 exceed 0.11 m |
| G portable hash lock | PASS | normalized semantic text hashes; raw binary hash |

The energy result is not softened. The fixed-step velocity-command loop closes
momentum algebraically, but its semi-implicit modal update and rectangular
joint-work accumulation do not meet the sim_11-quality `1e-9` energy audit.
That is a hard repeat reason for this implementation.

The constraint result is also not an implementation surprise to hide. The
19.20-degree benchmark itself uses q2=+60 degrees outside the URDF upper limit
of zero. T3 additionally drives multiple methods beyond joint limits, and its
static arm-versus-servicer/panel margin reaches -0.025374 m.

### T3 collision evidence and refusal

The frozen construction path is available and tested:

- arm/static/target primitives come from read-only sim_09
  `collision.py` and `collision_geometry_v1.yaml`;
- the target is `target_satellite_v0`; its primary
  `launch_adapter_ring=[0.290,0,0] m_T` comes from the frozen CAD JSON;
- the target primitive at the T2 capture pose closes the frozen EE/capture
  position to 1.30e-10 m and uses the existing
  `[0.23,0.313,0.213] m` half extents—no geometry was invented.

For each of five T3 runs, static geometry is evaluated at every one of the 501
fixed 0.01 s integration nodes. The dedicated CSV therefore contains 2,505
rows. This node coverage does not claim continuous between-node collision
coverage.

Target and combined margins are deliberately blank and machine-labelled
`NOT_EVALUATED`. The Wave 1 plan defines T3 as a 3+2 s retreat triggered from
the method-specific T2 state at 15 s, with the target continuing sim_09
constant-omega propagation at the frozen 3 deg/s rate. The implemented v0 T3
instead starts from `T2.q_initial_rad`; it does not freeze the corresponding
T2@15 s base/joint/modal state or target phase. Assuming an inertially static
target would manufacture a replacement contract, so the Gate records
`PLAN_CONTRACT_MISMATCH` and remains `REPEAT`.

## 5. What is supported now

Within the frozen simulation scope:

- the C0 and C1 models are strongly distinguishable on T2;
- all 15 runs conserve momentum below `1e-12`;
- the original C2 and C3 incremental hypotheses are not supported;
- the T1 mixed-frame ambiguity is resolved and tested.
- T3 static servicer geometry is covered at every fixed integration node.

Not supported:

- promotion to the next control stage;
- any general superiority of C1, C2, or C3;
- isolation of a C3 nullspace benefit from the C1_MATCH5 comparison;
- any T3 target or combined collision-clearance claim;
- absolute flexible-response meaning under real panel parameters;
- hardware, ground-performance, or flight-performance claims.

## 6. Required next loop

A new preregistration is required before rerun:

1. split the out-of-limit 19.20-degree benchmark from operational T1
   constraint adjudication;
2. replace the fixed-step work/energy audit with a discrete-work-consistent
   integrator and independently verify it before controller comparison;
3. freeze each method's full T2 state at 15 s, continue the frozen sim_09
   3 deg/s constant-omega target propagation, then re-register and rerun T3
   target/combined collision evaluation in a URDF-feasible corridor;
4. investigate the C2 frame/feedforward implementation without tuning against
   these results;
5. preregister `C2_MATCH5` before making any isolated nullspace comparison;
6. either redesign the C3 objective/gain analytically or retain the null result;
7. complete the independent three-reviewer red team.

No threshold may be widened to turn the current `REPEAT` into a pass.

## 7. CTRL-01-R remediation loop (2026-07-19)

Executed under
`10_research/partner_requirement_closure/wave1_repeat/repeat_preregistration.md`
(R-2/R-3). Every gate threshold above is unchanged. The matrix is
`{C0,C1,C2,C3,C1_MATCH5,C2_MATCH5} x {T1,T2,T3}` = 18 runs, 22/22 tests, a
ten-item machine Gate, and machine verdict **REPEAT** with the failure set
reduced to genuine negatives only.

### 7.1 Energy-audit diagnosis (v0 REPEAT -> PASS)

Diagnosis: the preregistration's first suspicion (missing `W_ctrl`) is
**refuted** - `W_ctrl = int tau.theta_dot dt` was already in the v0 ledger.
The 7.90e-2 residual was an accounting/discretization defect: a rectangle-rule
ledger accumulated over a first-order state map, so the audit compared
inconsistently discretized quantities. Fix (bookkeeping/numerics only, no
physics change, threshold kept at 1e-9): the velocity command is applied as a
first-order hold (constant theta_ddot per 10 ms sample, no velocity jumps),
and the state plus the `W_ctrl`/damping ledgers are integrated together by
per-interval adaptive DOP853 (rtol 1e-11) on the reduced zero-momentum
manifold - the sim_11-proven audit pattern. Result: worst relative audit
across all 18 runs is **5.63e-12** (was 7.90e-2); worst momentum residual
7.22e-16. The plant is evaluated through `fast_plant.py`, an equal-output
vectorized path machine-cross-checked against the frozen sim_11 SSOT at every
run (worst normalized error 4.44e-16; Gate item GC1_H, fail-closed). The
open-loop anchors sharpen accordingly: flexible delta 3.5e-11 deg, rigid
delta 3.6e-10 deg.

### 7.2 T3 collision evidence (v0 NOT_EVALUATED -> EVALUATED, subitem PASS)

Each method's T3 now starts from that method's frozen T2 t=15 s full state
(base position/attitude, joint angles and rates, modal state - recorded in
`control_01_run_summary.json:t3_trigger_states`) and the target continues the
frozen sim09 const-omega 3 deg/s propagation (phase = omega*(15 s + t)).
Static, target and combined margins are evaluated at all 501 fixed 10 ms
nodes of all six T3 runs (3,006 rows). All margins are positive:
combined minimum **+0.01462 m** (C3/C2_MATCH5), static minimum +0.01462 m,
target minimum +0.11476 m. The v0 static penetration of -0.02537 m is thereby
attributed to the contract-mismatched v0 T3 setup, not to the remediated
trajectory. Node coverage still does not claim between-node continuity.

### 7.3 C2_MATCH5 and the isolated nullspace comparison (REPEAT, genuine null)

`C2_MATCH5` (C2 on the rank-5 approach task) was added before any isolated
nullspace comparison. Against this matched-task, matched-feedforward
comparator, C3's isolated nullspace effect on frozen T2 is
**+1.84e-5 %** accumulated base rate (threshold >= 5%) with a within-C3
command reduction of 9.98e-6 % and tracking degradation -1.5e-5 %. The
NULL_RESULT is now established with the correct comparator, not inferred from
the confounded C1_MATCH5 comparison (context value: -7.95%). The v1.0
negatives (C2 -51.91%, C3 overall -7.99%) are preserved verbatim in the gate
JSON per the repeat preregistration.

### 7.4 Disposition of the remaining v0 failures

| Item | v0 | CTRL-01-R | Disposition |
|---|---|---|---|
| A2 closed-loop C1-T1 anchor | 0.1725 deg | 0.1550 deg > 0.05 | true negative: C2-T1 plant-fidelity diagnostic is 0.0064 deg, so the residual is frozen-gain pure-feedback lag, not integrator error |
| B energy audit | 7.90e-2 | 5.63e-12 | implementation defect fixed (7.1); threshold unchanged |
| D C2 position increment | -51.91% | -38.26% | true negative: T2 position reference is station-kept, feedforward adds joint motion; orientation improves +99.85% (context) but the frozen hypothesis pinned position |
| D C3 isolated nullspace | not measurable | +1.84e-5 % | genuine null with the preregistered C2_MATCH5 comparator (7.3) |
| E joint limits | -1.968 rad | -1.473 rad | true negatives: T1 anchor keeps the preregistered q2=+60 deg out-of-URDF conflict (-1.048 rad); the frozen 0.5 m retreat also folds the arm past limits from the 15 s state |
| E singularity | 3.78e-5 | 6.64e-5 < 1e-4 | true negative: frozen T1 starts at the singular stretched q=0 |
| E speed / accel | 3.26 / 11.36 | 1.84 / 9.11 | true negatives: T3 retreat rate demand and the t=0 command-engage transient (first 10 ms ramp onto an already-tumbling reference) exceed the frozen provisional class limits |
| E collision margin | -0.02537 m | +0.01462 m | fixed by the frozen trigger contract (7.2); subitem PASS |
| F bounded error | C1(-MATCH5)-T3 0.1901 m | 0.1902 m > 0.11 | true negative: T3 quintic peak rate 0.3125 m/s exceeds the frozen 0.12 m/s disturbance bound assumption, so pure-feedback C1 lag violates the bound by construction; C2/C3 T3 are within bound (0.0024 m) |

### 7.5 Updated claims

Newly supported (frozen simulation scope): the discrete energy ledger closes
to 5.6e-12; T3 static/target/combined keep-out margins are positive at every
fixed node under the frozen trigger; C3 vs C2_MATCH5 isolates the nullspace
term and it is null at the frozen gain. Still not supported: any general
controller superiority, C3 vs C1_MATCH5 isolation claims, between-node
collision continuity, absolute flexible-response meaning, hardware or flight
performance, promotion while the verdict is not PASS. Independent red team
remains `PENDING_REVIEW`.
