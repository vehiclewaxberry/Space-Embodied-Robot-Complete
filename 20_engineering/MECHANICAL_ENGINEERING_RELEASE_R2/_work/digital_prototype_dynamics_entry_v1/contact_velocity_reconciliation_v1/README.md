# Contact velocity reconciliation candidate V1

This additive package resolves the **consumer-semantics conflict** without editing or
upgrading either frozen source contract.

- The current first-contact design-target hard upper bound is **0.005 m/s**.
- The original **0.05 m/s** value remains preserved as an unverified provisional
  scenario input, but the machine gate rejects it for the current contact consumer.
- A separately and explicitly reduced candidate at **0.005 m/s** may be consumed only
  by bounded design diagnostics.
- As-built speed, its uncertainty, physical timing, production dynamics and non-ABORT
  grasping all remain **HOLD**.

The decision rule is deliberately one-way: a scenario with both estimate and upper
bound at or below 0.005 m/s can be semantically compatible; this never proves that the
hardware can execute it. Physical release still requires GVA-PI-01 through GVA-PI-07,
calibrated bench data, an uncertainty budget and a separately reviewed gate.

Run the deterministic evaluator and tests from this directory:

```powershell
python evaluate_contact_velocity_reconciliation.py
python -m pytest -q -p no:cacheprovider tests --basetemp=.pytest_tmp
python run_validation.py
```

Generated machine truth:

`CONTACT_VELOCITY_RECONCILIATION_GATE_V1.json`

Deterministic validation receipt:

`CONTACT_VELOCITY_RECONCILIATION_VALIDATION_V1.json`
