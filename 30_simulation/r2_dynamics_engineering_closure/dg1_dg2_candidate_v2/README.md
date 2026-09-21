# R2 DG1/DG2 candidate V2

This additive package closes two **candidate diagnostic** gaps without changing
the parent dynamics gate or any mechanical release verdict.

- DG1 declares `q = S x`, where every diagonal entry of `S` is the finite URDF
  joint span. It verifies kinetic-energy, virtual-power, normalized-equation,
  and recovered physical-acceleration invariance under both the declared and
  an alternate scale. A condition number is reported only with its metric.
- DG2 prescribes a bounded 8-DOF joint-rate trajectory, reconstructs the base
  twist for fixed nonzero inertial linear/angular momentum, integrates base
  position and attitude with fixed-step RK4 and DOP853, and independently sums
  every physical body's momentum.

The DG2 solver is momentum-level prescribed-motion evidence. It is not a
torque-driven plant, contact solver, target-attachment model, actuator model,
or flight-qualified simulation. DG3, DG4, DG5, TMG-4, TMG-6, hardware validity,
next-stage authorization, and release credit remain open/false.

Run from this directory:

```powershell
python run_validation.py
python -m pytest -q tests
```
