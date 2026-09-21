# e20 preregistration

Before execution, e20 freezes four independent lanes: `Legacy-A × M01`,
`Legacy-A × M07_ARM_ONLY`, `M3R-B × M01`, and
`M3R-B × M07_ARM_ONLY`. Every lane starts from its own zero base/panel state;
no final state, force, impulse or target state is transferred between lanes.

The main run is sim11 reduced-momentum/Radau with three provisional analytic
FFR modes per panel, nominal stiffness and zeta=0.005. The bounded numerical
anchor is `M3R-B × M07_ARM_ONLY` over the first 1.5 s. It independently checks
zeta=0 energy accounting, rigid panels, m=3/4/5 refinement and a BDF solution.
These are local numerical criteria, not mission acceptance thresholds.

Pass limits are: scalar mass closure <=1e-12 kg, reduced momentum residual
<=1e-12, relative energy audit <=1e-8, quaternion norm error <=1e-12,
m4-to-m5 local observable change <1%, and Radau-to-BDF local observable change
<5%. All mass matrices must remain symmetric positive definite.

Scene A2, target attachment, contact-window forcing, capture, lockup and
post-capture propagation are excluded. A2 is hash-bound only as an explicitly
excluded provisional debt and is never imported or executed.
