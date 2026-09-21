# sim_08 — post-capture detumbling actuator & propellant budget (v0)

## Question answered
The captured combined body carries all of the pre-capture angular momentum (sim_06:
capture ≠ detumbling). **How is it actually removed?** Reaction wheels only redistribute
momentum internally; bringing the stack to rest w.r.t. inertial space requires storing
|H_c| in the wheels or expelling it with external torque.

## Architecture (two-stage + unload)
```
coarse detumble : thruster couple, tau = |H_c|/t_d, F = tau/(2 l_T)
fine  stabilize : 3-axis reaction wheels (low-rate precision control)
unload          : thrusters (magnetorquers too weak for the coarse stage; future work)
```
Propellant: m_p = |H_c| / (l_T · Isp · g0). |H_c| from the validated sim_06 solver
(Gate A passed), NOT a heuristic. Constants in `assumptions.yaml` (class values from
NASA SmallSat SOA 2026; replace with selected COTS datasheets at report freeze).

## Key v0 numbers (v_app = 0.01 m/s, nominal grasp geometry)
| | debris 150 kg @3°/s | satellite 22 kg @3°/s |
|---|---|---|
| \|H_c\| after capture | **3.65 N·m·s** | 0.015 N·m·s |
| 3×100 mN·m·s wheel set (0.3 N·m·s) | **12× over capacity — wheels-only infeasible** | fits in ONE small wheel |
| coarse detumble 900 s, l_T=0.17 m | τ=4.1 mN·m, F=12 mN per thruster | not needed |
| propellant (l_T=0.17 m) | cold gas 36.5 g / green monoprop 10 g | ~0 |

**Design conclusion:** the two target classes demand different actuator architectures —
debris capture REQUIRES a thruster couple for coarse detumbling (10 mN-class is marginal,
100 mN-class comfortable); satellite capture is wheels-only feasible. This closes the loop
sim_06 opened ("capture does not detumble") into a concrete GNC sizing statement, and the
propellant cost (tens of grams) shows the mission is actually feasible.

## Outputs
- `results/actuator_budget_sweep.csv` — full sweep (2 targets × 20 tumbles × 4 t_d × 3 levers × 2 Isp)
- `results/budget_H_vs_wheels.png` — momentum to remove vs wheel storage classes
- `results/budget_force_vs_time.png` — detumble time vs required thruster force
- `results/budget_propellant.png` — propellant vs tumble rate (Isp × lever), wheel-feasible band

## v0 limits (see assumptions.yaml)
Scalar |H| budget (no vector allocation/nutation control); constant torque over t_d; no
plume impingement / CoM shift; target inertia confidence=low (RA-003). v1: vector momentum
management + wheel desaturation scheduling + selected COTS RW/thruster datasheets.
