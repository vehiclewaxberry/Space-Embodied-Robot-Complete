# DG4 contact hybrid candidate V1

This is an additive, deterministic and fail-closed **design diagnostic**. It does not
modify the parent R2 dynamics gate and does not instantiate a physically attached
post-capture plant.

The permitted state sequence is:

```text
PRECONTACT
  -> BOUNDED_CONTACT_DIAGNOSTIC
  -> POST_IMPACT_DIAGNOSTIC
```

The last state still contains two separate rigid bodies. `ATTACHED`, `CAPTURED`,
physical-contact, production, hardware and non-ABORT states are prohibited.

The candidate is hash-bound to the contact-velocity reconciliation, the bounded
provisional contact model, both target models, Unified R2 interface/URDF/frame tree,
the C01 mass ledger and the parent dynamics authority. The current speed is exactly
0.005 m/s. The original 0.05 m/s source value is retained as lineage and deliberately
rejected by this consumer.

For each 22 kg and 150 kg target, the solver evaluates the LOW/NOMINAL/HIGH provisional
restitution corners. It applies one frictionless normal impulse at a shared mathematical
contact origin and independently audits:

- restitution closure;
- equal-and-opposite linear impulse;
- total linear momentum;
- total angular momentum about the inertial origin;
- kinetic-energy non-increase and the effective-mass energy-loss identity;
- preservation of two independent bodies with no attachment.

The mathematical +Y normal and contact-at-service-COM construction are explicitly not
physical patch or surface-normal authority. All corresponding physical/as-built fields
remain null.

Run:

```powershell
python evaluate_dg4_candidate.py
python -m pytest -q -p no:cacheprovider tests --basetemp=.pytest_tmp
python run_validation.py
```

Machine truth is emitted under `results/`.

