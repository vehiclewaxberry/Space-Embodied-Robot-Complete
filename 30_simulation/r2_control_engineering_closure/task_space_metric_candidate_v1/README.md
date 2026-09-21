# R2 task-space metric candidate v1

This additive package closes one narrow control-predevelopment ambiguity: it
derives a characteristic length and reference mass from the hash-pinned
Unified R2 URDF.  It uses the length to nondimensionalize task rows and freezes
`I_ref = m_ref L_char^2` plus an explicit 6R generalized-rate scale before any
mass-weighted DLS diagnostic is credited.  Consequently both terms in
`J_bar M_bar^-1 J_bar^T + lambda^2 I` are dimensionless.

The derived value is **1.170431204685893 m**, computed as the sum of the
translation-vector norms on the unique `spacecraft_bus -> gripper_link` URDF
chain.  This is a conservative serial-chain translation bound and a declared
normalization convention; it is not an as-built measurement or a proof that
the selected weighting is control-optimal.

The package checks the 5D far-approach and 6D final-alignment task dimensions,
meter/millimeter and kilogram/gram reparameterization invariance, legal nullity (1 and 0), a
0.5x/1x/2x length sensitivity diagnostic, source hashes, deterministic
artifacts, and fail-closed boundaries.

It does **not** execute the time-domain plant, emit a command, query collision,
bind an M01 path, validate actuator hardware, reissue the parent control Gate,
or authorize the next stage.

Run:

```powershell
python build_task_space_metric_candidate.py
python -B standalone_validate_task_space_metric.py
python -B -m pytest -q -p no:cacheprovider
```

The package-local validator is explicitly `STANDALONE_INTERNAL`; it is not an
independent authority.  The sibling `task_space_metric_external_audit_v1`
package carries the immutable outside source lock.
