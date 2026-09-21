# Unified R2 System Binding V2 research candidate

This package is a deterministic, read-only evaluator for the **current** Unified R2 URDF and the current Sim13 V2 interface. It does not edit or replace the accepted B601 URDF, the emitted Unified R2 URDF, `MECH_RL_SYSTEM_INTERFACE_V2.yaml`, or any existing gate.

## What a PASS means

- all 23 frozen input byte/hash pins match;
- the Unified R2 URDF parses as one connected 19-link/18-joint tree rooted at `spacecraft_bus`;
- 16 physical links, three frame-only links, 10 fixed + six revolute + two prismatic joints, eight actuated DOF, and total mass `31.022864807342987 kg` are reproduced;
- the accepted 10-link/9-joint B601 subtree is semantically identical for names, parent/child, origins, axes, limits, and inertials;
- loader/runtime/dynamics/contact validation receipts are hash-bound and retain their declared bounded scope;
- the evaluator detects the current authority holds instead of promoting them.

The maximum claim is therefore:

`RESEARCH_CANDIDATE_LOAD__ABORT_ONLY`

It is **not** `SIM13_SYSTEM_BINDING_GATE_V2=PASS`, contact authorization, path-search authority, release credit, or flight qualification.

## Current fail-closed blockers

- `owner_accepted=false`;
- Route-C scope disposition and no-Route-C candidate acceptance are false;
- G12 remains `11/12`, failed at the harness rated operational envelope;
- M01 retains 11,166 unassessed required pairs and no completed scene, clearance, motion, oracle, edge, or path authority;
- consumer load, contact/grasp authorization, and the current System Binding gate are false.

## Reproduce

From this directory:

```powershell
python evaluate_system_binding_candidate_v1.py --write
python evaluate_system_binding_candidate_v1.py --check
python -m pytest
```

Generated outputs are canonical JSON with LF line endings and no wall-clock field. Any source-byte change, topology drift, B601 semantic drift, missing hold, or stale output fails closed.
