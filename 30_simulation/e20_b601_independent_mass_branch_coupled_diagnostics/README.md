# e20 — independent mass-branch sim11 coupled diagnostics

This package evaluates four independent, ARM-ONLY numerical lanes: two held
mass branches (`Legacy-A`, `M3R-B`) crossed with the M01 and M07 arm-only
quintic trajectories. It does not create a mission timeline and does not
attach a target.

The only completion introduced here is the preregistered
`UNIFORM_BUS_DENSITY_SCALAR_CLOSURE_SURROGATE`: the 22 kg scenario target is
subtracted algebraically from each C08 diagnostic composite mass, all sim11
non-bus members remain unchanged, and only the bus scalar mass and bus inertia
are scaled. Bus geometry and bus CG remain fixed. This is an artificial model
sensitivity device, not a released mass-property set or an engineering
prediction.

M7 `SYSTEM_DESIGN_MASS_PROPERTIES_V2` is hash-bound only as the newer authority
boundary. Its 9/9 DESIGN mass/CG/inertia set is outside e20. The old M4 A/B
scalars remain transitional sensitivity branches and are not promoted over,
or substituted for, the current M7 design-mass authority.

sim11 is consumed through a scoped in-memory REORG adapter. Its legacy
`T_SM=[0.18525,0,0] m, Ry(+90 deg)` is labelled
`M_DYNAMICS_LEGACY_NUMERICAL`. M7 ODR-01 retains a numerically matching unique
dynamics M, but e20 does not consume or close that current-design authority.
The x=208.0 mm and +25.000014 deg values describe a separate geometric feature
stack, not a replacement dynamics-M frame. The e20 physical mount transform
remains `null/HOLD`.

Run from the repository root with bytecode disabled:

```text
python -B 30_simulation/e20_b601_independent_mass_branch_coupled_diagnostics/src/build_e20_diagnostics.py
python -B 30_simulation/e20_b601_independent_mass_branch_coupled_diagnostics/src/build_e20_diagnostics.py --check-only
python -B 30_simulation/e20_b601_independent_mass_branch_coupled_diagnostics/tests/validate_e20_diagnostics.py
```

The e20 diagnostic execution may be locally `PASS`, while the package Gate is
always `HOLD`: e15 remains `REPEAT_ANCF_CERTIFICATION`; panel and contact
parameters remain provisional; physical contact, attached recovery, CAD,
production, mission, hardware and flight authority remain absent.
