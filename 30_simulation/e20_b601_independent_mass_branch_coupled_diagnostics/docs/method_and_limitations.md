# Method and limitations

The C08 values 50.69555594934299 kg and 51.081436764691 kg are two historical,
non-selected diagnostic composites that include a 22 kg scenario target. e20
subtracts exactly 22 kg to obtain service scalar branches
28.69555594934299 kg and 29.081436764691 kg. It does not recover a physical CG
or inertia from those scalars. Instead, it keeps every existing sim11 non-bus
member fixed, adjusts the bus mass only, holds the bus CG/geometry fixed, and
scales the sim11 bus inertia linearly with mass. The result is a controlled
surrogate sensitivity experiment.

The later M7 V2 design-mass package supplies 9/9 design mass/CG/inertia with
declared uncertainty for engineering-design analysis, while its enclosing
release remains Owner-review/HOLD. e20 deliberately does not consume those
properties. Binding them to dynamics is a separate e21-class task; the M4 A/B
surrogates here are legacy transitional sensitivity branches only.

The sim11 Gate retains its historical
`SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS` verdict. Its 58-artifact historical
manifest has 32 current byte matches and 26 summary-JSON byte drifts after
REORG; the drift set is recorded as route-only semantic migration. This does
not transfer sim11's historical `next_stage_authorized=true` into e20.

The stock sim11 configuration loader would read target and capture-interface
metadata even during A1. e20 therefore uses a local narrow ARM-only loader that
reads only the model card, legacy frame/panel data, mass CSV and accepted URDF.
Target/contact metadata is neither read nor passed into the dynamics model.

The panel mass, analytic modes, EI case and damping are provisional. e15's
5.637349% cross-solver discrepancy remains above its 5% limit, so ANCF stays
`REPEAT_ANCF_CERTIFICATION`. A local sim11 BDF agreement cannot clear that
debt.

The model uses `M_DYNAMICS_LEGACY_NUMERICAL`, not a current-design authority.
The current M7 unique dynamics-M authority is not consumed even though its
numeric T_SM is also 185.25 mm + Ry90; the 208 mm/+25.000014 deg geometric
feature stack is explicitly not substituted as dynamics M. No result is an M4
or M7 digital-prototype installation-dynamics property. Released
mass/CG/inertia, measured panel properties, contact/lock fields, attached-state
recovery, acceptance thresholds, actuator data and physical mount transform
remain null. All mechanical, production, mission, hardware and flight states
remain false/HOLD.
