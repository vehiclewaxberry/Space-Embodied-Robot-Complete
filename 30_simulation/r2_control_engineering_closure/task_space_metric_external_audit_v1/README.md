# Task-space metric external audit v1

This sibling package is outside the candidate namespace.  Its immutable source
lock directly pins the candidate evaluator, builder, standalone validator,
tests, contract, Gate, evidence, manifest, SHA table, negative controls,
standalone receipt, and documentation.  It also directly freezes the seven
candidate sources and all 24 transitive control/backend dependencies.

The auditor does not import the candidate implementation.  It independently
recomputes the URDF chain length, total reference mass, reference inertia,
dimensionless normalized mass/Jacobian/normal matrices, joint-rate diagnostics,
residuals, and every candidate check C01--C17.  It requires its independently
constructed check dictionary to equal both the evidence and Gate dictionaries
key-for-key.  For the kg-to-g physical-source test, the auditor transforms all
16 URDF link masses and all 96 inertia-tensor components by 1000 in memory,
leaves lengths in metres, and passes the distinct XML bytes to
`URDFTreeDynamics` for a fresh reduced-matrix assembly.  No temporary file is
created.  The receipt distinguishes this physical reassembly diagnostic from
the exact analytic common-scale cancellation used by candidate C09, and reports
`M_g` versus `1000 M_kg`.  A synthetic
non-identity `S_q` case verifies the general change-of-variables formula.
All conclusions remain limited to the current hash-bound static probe.
It grants no collision, M01, SAFE, hardware, time-domain,
parent-control, next-stage, or release authority.

The external-audit package inventory is checked by exact set equality. Missing
required files—including this README—and undeclared extra files both fail A07.

Run with bytecode and pytest caches disabled:

```powershell
python -B audit_task_space_metric.py
python -B -m pytest -q -p no:cacheprovider
```
