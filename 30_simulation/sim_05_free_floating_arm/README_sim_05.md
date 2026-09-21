# sim_05 — free-floating base dynamics with the real 6R arm (arm_b601_v1)

Momentum-level free-floating model of the 12U servicer + arm_b601_v1
(Seeed reBot B601 hybrid URDF, decision D-5-final). Pure numpy/scipy.
Replaces the sim_03 2-DOF reduced planar model with the full 3D 6R chain.

## Files

| file | content |
|---|---|
| `b601_model.py` | URDF parsing (xml.etree), gripper merge into link6, FK, geometric Jacobian `J` (6×6), `Jp` (3×6), `J5` (5×6) |
| `dynamics.py` | composite base body, momentum matrices `H_bb`/`H_bm` (unit-velocity assembly), zero-momentum base reaction, generalized Jacobian `J_g`, base-pose trajectory integration (DOP853) |
| `tests/` | 6 test files + `run_all.py` (no pytest; plain asserts, each test returns its worst residual) |
| `sim_05_headline.py` | headline maneuver, CSV/PNG in `results/` |

## Model definition

- **Arm**: `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`. 6 revolute
  joints `joint1..joint6`, all about the local z axis (`joint2` axis is
  `(0,0,-1)`). URDF rpy = fixed-axis extrinsic XYZ, `R = Rz(yaw)·Ry(pitch)·Rx(roll)`.
  All `<inertial>` origins have rpy = 0 (checked; a non-zero rpy would be rotated
  into the link frame per the URDF standard — handled generally in the parser).
- **Gripper locked**: `gripper_joint` is fixed; prismatic fingers
  `gripper_joint1/2` locked at q = 0 (capture-ready). `gripper_link` +
  `gripper_left` + `gripper_right` are rigidly merged into **link6** (composite
  mass/CoM + parallel-axis inertia). link6 composite = 0.632756 kg.
  **Total arm mass = 4.695556 kg** (spec 4.6956 ± 0.001).
- **Mounting (frozen, SSOT §3.1 nominal_frozen_v1 / decision D-2)**:
  `t_SM = [0.18525, 0, 0] m`, `R_SM = R_y(+90°)` (columns = M axes in S:
  `+Z_M = +X_S`, `+Y_M = +Y_S`, `+X_M = −Z_S`). Arm base frame A0 = base_link = M
  (`T_MA0` = identity).
- **Composite base body (25.2 kg)** = `servicer_12U_v0` (24 kg whole-spacecraft
  rigid line from `mass_inertia_budget_v1.csv`, frame S, about CoM; solar panels
  are inside this 24 kg — rigid-line bookkeeping) + `robot_mount_adapter_v0`
  (1.2 kg, frame M, about CoM). The adapter is mapped into S via T_SM:
  `cg_S = t_SM + R_SM·cg_M = [0.16799, 0, 0] m` (its JSON cg `[0,0,−0.01726]` is
  along −Z_M = −X_S, i.e. from the mount face back toward the body — **not** a
  −Z_S offset), `I_S = R_SM·I_M·R_SMᵀ = diag(0.004117, 0.002119, 0.002119)`.
  Parallel-axis composite: cg = `[0.005695, 0, 0.000543] m`,
  `I = diag(0.231684, 0.388958, 0.421469)` (+ `Ixz = −0.000634`) kg·m².
- The arm **base_link** (0.8366 kg) is rigid with the mount and is carried as a
  separate base-fixed body in the momentum assembly (contributes to `H_bb`
  only), keeping the 25.2 kg composite-base bookkeeping exactly
  servicer + adapter. Total system = 29.8956 kg.

### E frame definition

E origin = origin of `gripper_link` (child of the fixed `gripper_joint`)
= **link6 origin + 0.15971 m along +z_link6** (URDF `<origin xyz="0 0 0.15971">`).
E axes are taken **aligned with link6**, so `+z_E` is the tool approach axis.
(The URDF gripper_link frame itself carries an extra `rpy = (0, −1.5708, 0)`;
its `+x` coincides with our `+z_E`. Keeping link6 axes makes "tool z" mean the
approach direction; the choice does not affect the angular Jacobian rows.)
At q = 0: E in A0 = `[0.26031, 0, 0.19170] m`, in S = `[0.37695, 0, −0.26031] m`,
tool axis in S = `[0, 0, −1]` (arm folded across the front face).

### Task Jacobians

- `Jp = J[0:3,:]` — 3-DOF position.
- `J5` (5×6) — rows 1–3 position; rows 4–5 = rate of the tool-axis alignment
  error `e = a × a_des` (a = current tool z), `de/dt = [a_des]×[a]× ω`, projected
  on two orthonormal directions spanning the plane ⊥ `a_des`.

### Free-floating dynamics

`p = H_bb·V_b + H_bm·q̇` with `V_b = [v_b; ω_b]` about the base (S) origin,
expressed in the base frame; assembled with the **unit-velocity method**
(12 columns = total system momentum for each unit velocity component).
Zero momentum ⇒ `V_b = −H_bb⁻¹·H_bm·q̇`.
Generalized Jacobian `J_g = J_m − J_b·H_bb⁻¹·H_bm`,
`J_b = [[I₃, −[r_E]×],[0, I₃]]`. Base pose (position + scalar-first quaternion)
integrated with `solve_ivp` DOP853, rtol 1e-11 / atol 1e-13.

## Acceptance results (`python tests/run_all.py` — 22/22 PASS, 2026-07-11)

| test | result | worst residual |
|---|---|---|
| urdf: 6 revolute joints, gripper fixed + 2 prismatic | PASS | 0 |
| urdf: single-root tree, no cycles | PASS | 0 |
| urdf: 20 mesh refs, all relative, all files exist | PASS | 0 |
| inertia: all masses > 0 | PASS | smallest mass 1.613e-01 kg |
| inertia: symmetric | PASS | 0 |
| inertia: positive definite | PASS | min eig 1.546e-04 kg·m² |
| inertia: triangle inequality on principal moments | PASS | min margin 9.524e-05 kg·m² |
| joints: unit axes, revolute about z, joint2 = −z | PASS | 0 |
| joints: FK world axes unit-norm | PASS | 3.3e-16 |
| joints: own axis/origin invariant to own angle | PASS | 0 |
| FK: zero-config origins vs independent scipy chain | PASS | 2.2e-16 m |
| FK: EE hand values (q=0) + 2 nonzero configs vs indep. chain | PASS | 7.0e-07 (hand value), 1e-12 class (chain) |
| FK: Jacobian vs central FD (ε=1e-7, 6 seeds-fixed configs) | PASS | rel 8.0e-10 (< 1e-6) |
| mass: arm total = 4.6956 ± 0.001 | PASS | 4.4e-05 kg |
| mass: link6 composite roll-up exact | PASS | 1.1e-16 kg |
| mass: composite base = 25.2 | PASS | 0 |
| mass: system 29.8956, H_bb linear block = m·I₃ | PASS | 4.4e-05 kg |
| dyn 1: q̇=0 ⇒ V_b=0 | PASS | 0 |
| dyn 2: total momentum about inertial origin along trajectory | PASS | 7.3e-17 (< 1e-10) |
| dyn 3: geometric phase after closed joint cycle | PASS | **2.6168°** (non-zero, reported below) |
| dyn 4: all masses ×3.7 ⇒ base motion unchanged | PASS | 6.5e-16 |
| dyn 5: J_g vs FD EE inertial velocity (lin + ang) | PASS | rel 9.0e-07 (< 1e-4) |

**Geometric phase**: phased rectangle cycle joint2 0→+60°→0, joint3 0→−40°→0
(4 s per edge, min-jerk) returns the joints exactly to zero but leaves the base
rotated by **2.6168°** (euler xyz final ≈ [−0.0012, −2.6168, −0.0035]°) — the
non-holonomic signature of free-floating manipulation.

## Headline (`python sim_05_headline.py`)

Maneuver: min-jerk **joint2 0 → +60°, joint3 0 → −40°, 8 s**, other joints 0,
hold to 12 s (sim_03-comparable magnitude).

| quantity | value |
|---|---|
| peak base attitude deviation | **19.20°** (at t = 8.0 s, stays after hold — no retract) |
| final euler xyz | [0.028, **19.20**, 0.001]° — almost purely about +Y_S |
| old sim_03 2-DOF planar model (1.6 kg rod arm) | 13.13° |
| ratio new/old | **1.46×** |
| peak \|H_bm·q̇\| angular | 0.0891 kg·m²/s |
| peak \|H_bm·q̇\| linear | 0.1602 kg·m/s |
| max base CoM shift | 4.9 mm |
| outputs | `results/sim_05_base_attitude.csv`, `results/sim_05_base_attitude.png` |

As predicted, the real 4.6956 kg arm (vs 1.6 kg rods) drives a substantially
larger base excursion; the increase is 1.46× rather than ~3× because the B601
links are shorter (0.264/0.243 m vs 0.30/0.25 m), much of the arm mass sits in
link2 near the shoulder, and the 25.2 kg composite base has slightly more
inertia. The reaction is >99% about +Y_S, cross-validating the sim_03 planar
assumption for this maneuver family. The `|H_bm·q̇|` history is the baseline
signal for subsequent reaction-minimizing trajectory work.

## Known simplifications

- Solar panels are **inside** the 24 kg / whole-spacecraft rigid line
  (`servicer_12U_v0` row) — rigid-body bookkeeping; the flexible-panel split
  (23.3032 kg bus + panels) is the separate ANCF line (sim_07).
- Gripper fingers locked at q = 0; gripper bodies rigidly merged into link6.
- Joint flexibility, gearbox friction, motor dynamics ignored (momentum-level
  kinematic reaction model; no joint torques computed).
- Zero initial momentum, no external forces/torques (thrusters/wheels off).
- `T_MA0` = identity nominal; arm inertials are vendor URDF values (physical
  weighing pending, confidence medium).
- Headline q2 = +60° exceeds the URDF joint2 limit [−180°, 0] (axis (0,0,−1)
  sign convention): kept deliberately as a dynamics benchmark comparable to
  sim_03, not a flight trajectory.

## Run

```
python tests/run_all.py     # 22/22 PASS, ~35 s
python sim_05_headline.py   # writes results/sim_05_base_attitude.{csv,png}
```
