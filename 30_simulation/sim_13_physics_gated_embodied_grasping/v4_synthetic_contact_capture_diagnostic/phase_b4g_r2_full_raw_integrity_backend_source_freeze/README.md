# B4G R2 full raw-integrity backend — source freeze only

This sibling package closes the software-side recomputation gap left by the
56-array raw adapter. It independently evaluates G03/G05/G07/G08/G09/G10/G11
and G16, while reusing the hash-bound R2 raw implementations of G04 and G06.

The backend accepts no upstream `gate_predicates`, selector boolean,
child-reported post-release pass, or clearance-integrity boolean. It binds the
raw sidecar/NPZ, the acquisition payload and snapshot, the external reference
force, solver-free geometry replay, and a separate compact parent trace.

The persistent package contains source, contracts, tests, JSON receipts and
Gate records only. Test fixtures are temporary and nonphysical. No runner,
trajectory, CAD, STEP, URDF, CSV or NPZ is released here.

Highest possible status:

`PASS_R2_FULL_RAW_INTEGRITY_BACKEND_SOURCE_FREEZE_ONLY`

Even when every technical-fixture predicate is true, `passed=false`,
`trajectory_count=0`, and all current-system/scientific/Owner/production/
release/next-stage fields remain false.

Validation commands:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest
python freeze_phase_b4g_r2_full_integrity_sources.py
python validate_phase_b4g_r2_full_integrity_source_freeze.py
python independent_audit_phase_b4g_r2_full_integrity_source_freeze.py
python verify_phase_b4g_r2_full_integrity_read_only_replay.py
```
