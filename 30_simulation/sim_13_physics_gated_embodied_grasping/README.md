# sim_13 physics-gated embodied grasping

## Current authority (2026-08-24)

The original package in `src/` is preserved as a historical deterministic V1
kinematic bootstrap.  Newer M7 evidence invalidated its production mechanical,
contact and RL binding authority.  Its maximum current use is historical
bootstrap/regression; it must not release a non-`ABORT` production action.

The new `v2_system_rebind/` package is a source-only prebind implementation. It
parses the Unified R2 19-link/18-joint system contract, exposes exactly eight
movable coordinates, resolves 12 fail-closed gates and supplies a momentum-level
free-floating backend. It is hard-locked to ABORT because the V2 system URDF,
interface instance and Owner scope acceptance do not yet exist.

Machine decision:

- `v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json`
- `prebind_source_implementation_passed=true`
- `next_stage_authorized=false`
- maximum state: `ABORT_ONLY_WITH_SOURCE_ONLY_ANALYTIC_PREBIND_DIAGNOSTICS`

## Historical V1 scope

The V1 environment:

- loads a SHA-256-bound `MECH_RL_INTERFACE_V1.yaml` package;
- treats the accepted B601 URDF as the sole arm mass authority;
- exposes state observations and high-level discrete actions only;
- masks every non-`ABORT` action unless all required facts are `PASS`;
- executes deterministic 22 kg / 0.5 deg/s and 150 kg / 3.0 deg/s anchors;
- never claims trained-policy, contact-physics, flexible-body, HIL, or flight
  qualification success.

## Run the tests

From this directory:

```powershell
python -m pytest
```

For the V2 source-only prebind:

```powershell
Set-Location v2_system_rebind
python -B validate_prebind_v2.py
```

To run the same eleven tests against the published production interface:

```powershell
$env:SIM13_PRODUCTION_INTERFACE = 'F:\path\to\MECH_RL_INTERFACE_V1.yaml'
python -m pytest
```

The historical V1 unit-test fixture binds the repository's accepted B601 URDF and existing
B601 meshes.  It is not the production whole-system mechanical package.  The
production manifest path is configured in `config/sim13_bootstrap.json`; the
environment-bootstrap gate must remain `HOLD` until that manifest and its
whole-system visual/collision meshes exist and pass the same loader checks.
