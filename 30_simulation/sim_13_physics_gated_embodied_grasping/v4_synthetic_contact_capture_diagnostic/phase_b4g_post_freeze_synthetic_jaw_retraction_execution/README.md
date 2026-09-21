# Sim13 V4B4G post-freeze synthetic jaw-retraction execution

This sibling package executes and audits only the frozen B4F synthetic,
P-joint-only command domain.  It does not authorize or claim a physical
actuator, gripper stroke, contact/lock/release implementation, current-system
binding, formal NC19 credit, Owner approval, production readiness, or any URDF
change.

## Test boundary

The tests under `tests/` pin the pre-run contract surface before any campaign
result can influence it.  They cover:

- byte-bound B4F/B4E sources and the recursively self-excluded B4F terminal DAG;
- the exact 144-slot schedule (12 A0, 108 A1, 24 conditional A2), keyed-SHA
  order, canonical schedule hash, and fresh-state/no-shared-event rules;
- the A0 absolute-time/common-interval disambiguation;
- the single algorithm-only `Q_ref`, P-only generalized force, exact-zero
  profile endpoints, P-domain fail-closed behavior without clipping, and signed
  actuator-work ledger;
- gate/outcome/selector semantics and all physical/current/formal governance
  holds;
- all 22 registered negative-control parents and their 65 real-path mutation
  subvariants.

Numerical unit tests are deliberately bounded to command primitives and small
or single-case solver paths.  They must not launch the full registered campaign;
campaign execution, evidence publication, validation, and independent audit are
owned by their dedicated workflow.

## Commands

From this directory:

```powershell
python -m pytest -q
python -m pytest --collect-only -q
python -m pytest -q tests/test_registered_schedule.py
python -m pytest -q tests/test_solver_primitives.py
```

No final node-id count or node-id digest is hand-maintained here.  The execution
validator must derive that inventory from a fresh `pytest --collect-only` run
after the solver and tests have reached their signed source state.

