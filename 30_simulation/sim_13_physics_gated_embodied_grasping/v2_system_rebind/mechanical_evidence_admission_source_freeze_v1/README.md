# M7 → Sim13 mechanical evidence admission source freeze V1

This package is a **consumer-side, source-only admission boundary**. It does not create or modify CAD, STEP, mesh, URDF, FEA, trajectory, contact, solver, campaign, or physics data. Its maximum verdict is:

`PASS_M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_ONLY`

That PASS means only that the contracts, strict loader, evidence classifier, negative controls, independent audit, validator, and read-only replay are frozen and self-consistent. It is not a mechanical CDR, current-system binding, physical-contact authorization, dynamics-entry authorization, production release, or next-stage authorization.

## Admitted evidence classes

- `BOUND_DIGITAL`: source-bound 19-link/18-joint static tree and the accepted B601 10-link/9-joint digital kinematic/inertial subtree.
- `DESIGN_CANDIDATE`: C01 whole-system mass, center-of-mass, inertia, and CAD↔URDF design calibration; none are as-built/metrology/flight authority.
- `DIAGNOSTIC_ONLY`: hash-bound mesh loadability/broad phase and candidate/UNKNOWN trajectory descriptions.
- `OWNER_REQUIRED`: unified system URDF generation, Route-C disposition, V2 interface instantiation, and current-system rebind.
- `TEST_REQUIRED`: physical gripper speed/force/latency/holding and CT-01…CT-05 contact identification.
- `ABSENT`: authoritative target contact frames, normal, patch/area and released trajectories/system artifacts.

Every exposed numeric engineering quantity carries an explicit unit, coordinate frame, reference point, authority, status, source artifact, and source field. Source files are consumed from canonical project-root-relative paths by one immutable byte read; byte count, SHA-256, parser input, and schema validation all use that same snapshot. Absolute paths, traversal, aliases, symlinks/reparse points, duplicate keys, non-finite numbers, schema drift, and mutable post-load views are rejected.

## Frozen machine separations

1. A mesh being hash-bound and loadable does not make it authoritative collision or narrow-phase geometry.
2. The URDF `15.0 m/s` gripper velocity is an unvalidated model literal, not physical speed or timing authority.
3. A provisional/minimum-jerk trajectory seed is not a released mission trajectory; the current ledger has 8 required and 0 released segments.
4. D and M may share the same numerical transform while remaining different immutable semantic identities; the physical load path must never traverse M.
5. Explicit primary structure replaces the corresponding aggregate-bus content. The prohibited 37.05784541499227 kg double count is rejected.

## Validation

Run with bytecode and pytest caches disabled:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider
python validate_mechanical_evidence_admission_source_freeze.py
python independent_audit_mechanical_evidence_admission.py --check
python verify_mechanical_evidence_admission_read_only_replay.py
```

All published Gate, terminal, validation, negative-control, audit, and source-manifest records are strict JSON. The default validator and replay are read-only.

The following fields are invariantly false at this freeze:

- `system_urdf_available`
- `current_system_bound`
- `physical_contact_ready`
- `dynamics_capture_entry_authorized`
- `next_stage_authorized`
