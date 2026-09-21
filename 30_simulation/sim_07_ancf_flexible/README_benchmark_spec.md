# sim_07 — ANCF flexible-appendage response (benchmark spec, NOT yet implemented)

Status: **spec only** (2026-07-10). Per the converged plan, sim_07 starts with three
benchmarks; no capture coupling until all three pass. Gate B (2026-07-20): if no credible
benchmark curve by then, scope collapses to "planar ANCF beam + 3D rigid base + COMSOL
modal cross-check" — no multi-panel, no complex contact.

## Model ladder (all three REQUIRED for the comparison figure)
- **Model R** — rigid stack (existing sim_06/sim_04_v2 chain).
- **Model L** — linear modal appendage: 1–3 bending modes, `Mq η̈ + Cq η̇ + Kq η = Qq`.
- **Model N** — planar gradient-deficient ANCF beam (Berzeri–Shabana elastic forces),
  symbolic derivation via ancf_kinematics/sympy_mechanics MCPs, MATLAB/Python integration.

## Benchmark acceptance (phase 1, before ANY capture coupling)
1. Static cantilever tip deflection vs Euler–Bernoulli analytic: error < 1% (mesh-converged).
2. First/second natural frequencies vs analytic (and COMSOL cross-check): error < 5%.
3. Rigid-body translation + large rotation: elastic strain energy ≈ 0 (zero-strain test).
4. Free undamped oscillation: energy drift bounded over the sim window (report value).
5. Mesh + time-step convergence tables.

## Excitation interface (from sim_06 — do NOT use the scalar dT)
Input = grasp-point impulse + couple `(J_t, L_grasp)` or base velocity jump `(dv, dw)`
from `30_simulation/common/capture_impulse.py::junction_couple` (nominal debris case: couple
≈ 0.12 N·m·s). dT (~5 mJ) is only the upper bound / consistency check on flexible energy
uptake.

## Result metrics (phase 2)
Tip max displacement; root bending moment; 1st-mode frequency; decay time; base attitude
peak error; control torque peak; actuator saturation flag; and the headline figure:
**rigid corridor vs linear-modal corridor vs ANCF corridor** (SAFE-area change), i.e. the
flexible constraint folded back into sim_04_v2 — not a standalone displacement time trace.
