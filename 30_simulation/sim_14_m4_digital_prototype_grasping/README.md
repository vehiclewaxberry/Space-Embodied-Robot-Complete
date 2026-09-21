# Sim14 M4 digital-prototype grasping bridge

Sim14 is an isolated successor to the Sim13 bootstrap. It does not modify or
supersede Sim13. Its production path consumes `MECH_RL_INTERFACE_V2.yaml` and
fails closed while the M4 system mass, inertia, target, contact and collision
authorities remain incomplete.

The only executable non-abort path at this revision is an explicitly
acknowledged diagnostic fixture. That path validates software mechanics, not a
spacecraft prediction:

- SI-unit fields are explicit at every interface boundary;
- a free-floating rigid capture conserves total linear and angular momentum in
  an inertial frame, including parallel-axis terms;
- the event chain is `RESET_READY -> PREGRASP -> CONTACT_CANDIDATE -> CAPTURED`;
- unknown or failed runtime gates force the canonical `ABORT` action;
- direct joint torque commands are rejected;
- the fixture uses M4 ADR-aligned diagnostic Branch B (bus with the legacy
  flange subtraction + two panels + B601 + M3R) and provisional target digital
  properties; the branch remains non-authoritative and the still-unknown
  service-spacecraft inertia remains a positive-definite numeric test tensor;
- `MOVE_PREGRASP` is an event-interface action only in this revision; it does
  not claim IK, joint-trajectory, actuator, or contact execution;
- contact impulse history, compliance, friction, flexible modes, trained RL,
  HIL and flight qualification are outside the authorized scope.

Run validation from this directory:

```powershell
python tools/run_validation.py
```

Run tests only:

```powershell
python -m pytest
```

The production gate remains `HOLD` until the M4 interface is hash-complete and
its listed mechanical blockers are closed. A passing Sim14 diagnostic gate must
never be interpreted as a passing production dynamics or capture gate.
