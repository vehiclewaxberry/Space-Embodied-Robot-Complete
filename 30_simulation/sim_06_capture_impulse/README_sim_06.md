# sim_06 — capture-instant impulsive momentum transfer (v0)

## What it does
Computes the **exact** post-capture combined-body rate at the instant the arm rigidly
grasps the tumbling target (perfectly plastic rigidization), replacing the sim_04 v0
heuristic `post_rate ~ tumble * I_t/(I_s+I_t)`.

Conservation through the capture impulse (no external forces):

```
P_pre = P_post                         (linear momentum)
H_pre = H_post   about the COMBINED CoM (angular momentum)

H_pre  = Σ_i [ I_i ω_i + m_i (r_i - r_com) × (v_i - v_com) ]
I_comb = Σ_i [ I_i + m_i ((d_i·d_i)E - d_i d_iᵀ) ],  d_i = r_i - r_com
ω_after = I_comb⁻¹ H_pre
```

The parallel-axis (Steiner) terms and the `r × m v` linear→angular coupling are exactly
what the scalar shortcut `ω_c = H/(I_s+I_t+I_arm)` drops (cf. Dimitrov & Yoshida,
IROS 2004, momentum distribution for post-impact control).

## Model / inputs (all SSOT-consistent)
- Chaser stack = `servicer_12U_v0` + `robot_mount_adapter_v0` + reBot arm links
  (thin rods, extended along +X_S): **26.5 kg**, CoM x=0.0278 m,
  I_diag=[0.230, 0.661, 0.696] kg·m² (Steiner-grown vs servicer-only 0.354).
- Approach along grasp-feature normal +X (sim_02/04 convention), EE at the grasp point,
  residual closing speed `v_app` at contact, chaser attitude held (ω=0).
- Grasp points from CAD JSON metadata (lever arm from target CoM):
  debris nozzle rim `[0.660,0,0.950]−cg` → |r_g|=1.215 m (1.02 m lateral!);
  satellite adapter ring `[0.290,0,0]−cg` → |r_g|=0.252 m (center-aimed).
- Tumble axis = sim_04 convention `[1.0,0.15,0.4]/|·|`; grid: 2 targets × tumble
  {0.5,1,2,3,5}°/s × v_app {0.005,0.01,0.02,0.03} m/s = 40 cases, deterministic.

## Key v0 results (valid under the labeled assumptions below)
| | debris 150 kg | satellite 22 kg |
|---|---|---|
| post-capture rate @3°/s tumble | **3.06°/s** | 1.39°/s |
| 2°/s-budget tumble boundary (continuous, exact) | **1.96°/s** (heuristic: 2.01°/s) | **4.37°/s** (heuristic: 3.65°/s) |
| discrete-grid cases over budget | 12/20 | 4/20 |

- **Headline (stated conditionally):** under the current servicer mass properties,
  capture geometry, perfectly-plastic rigidization, and the 2°/s detumble budget, a 12U
  servicer capturing the 150 kg stage does NOT meaningfully detumble it by momentum
  exchange — the combined rate stays ≈ the target rate. General principle: **without an
  external control torque, capture can only redistribute and partially dissipate
  mechanical energy; it cannot remove the system's total angular momentum. Capture ≠
  detumbling.** Detumbling authority must come from post-capture control (sim_08 budget).
- **Heuristic error direction differs by target** (see sim_04_v2 boundary figure):
  for the heavy debris the heuristic was slightly optimistic (boundary 2.01 → 1.96°/s,
  −2.6%, which flips the discrete 2°/s grid point → 24 false-safe cases in sim_04_v2);
  for the light satellite the heuristic was **conservative by ~20%** (3.65 → 4.37°/s,
  the exact model *relaxes* the boundary). A single scalar correction factor cannot fix
  both directions — the full vector model is required.
- Scalar shortcut error: **−2.9% … −12.3%** across the grid; at zero tumble it predicts
  exactly 0 while the full result is nonzero (approach-momentum coupling) —
  `scalar_vs_full_error.png`.
- Approach-momentum coupling is real but small at ADR closing speeds
  (≤5% of |H| at v_app ≤ 0.03 m/s); it sign-flips the ω_y component for the debris
  rim grasp (1.02 m lateral lever).
- Post-capture nutation (torque-free, 120 s, I_comb): peak 3.13°/s from 3.06°/s.
- **ANCF excitation interface (sim_07): the per-body impulse and grasp-point couple**
  (nominal debris case: |J_t| in CSV, couple ≈ 0.12 N·m·s), or equivalently the base
  velocity jump (dv, dw) — NOT the scalar energy. The plastic loss dT ≈ 0.005 J serves
  only as an upper bound / consistency check on flexible-mode energy uptake.

## Verification (Gate A — PASSED 2026-07-10)
Solver lives in `30_simulation/common/capture_impulse.py`; suite in `tests/` (`python tests/run_all.py`),
report in `tests/verification_report_v0.md`. 21/21 passed:
- P conservation ~1e-16; H conservation about the origin AND arbitrary points ~1e-15
- plastic dT ≥ 0 on every case; already-rigid ensembles dissipate exactly 0 (~1e-16)
- rigid translation + rotation + Galilean boost invariance ~1e-12
- 9 limiting cases with closed-form expectations (central impact, eccentric translation,
  axisymmetric spin, vanishing mass, coincident CoMs, mass/velocity scaling, zero lever)
- independent 6×6 spatial-inertia (Featherstone) implementation agrees to ~1e-14

## Outputs
- `results/capture_impulse_matrix_v0.csv` — 40-case matrix (full vs scalar, ω⁺ vector,
  contact impulse |J|, grasp couple |L|, ΔKE, H-residual, budget flag)
- `results/before_after_momentum.png` — momentum allocation through capture + rate bars
- `results/post_capture_rate_map.png` — exact post-capture rate maps vs 2°/s budget
- `results/scalar_vs_full_error.png` — scalar-shortcut error vs grasp lever arm

## v0 assumptions (labeled, honest)
Instantaneous rigid capture, no slip/compliance; arm frozen at full extension; chaser
attitude held at contact; target body frame aligned with inertial at capture instant
(worst-case phase not swept yet); target inertia confidence=low (RA-003). Upgrades:
sweep capture phase/attitude, compliant-grasp impulse model, SPART/MuJoCo cross-check.
Downstream consumers: sim_04_v2 (exact corridor, done), sim_08 (actuator budget, done),
sim_07 ANCF (impulse/couple interface, pending).
