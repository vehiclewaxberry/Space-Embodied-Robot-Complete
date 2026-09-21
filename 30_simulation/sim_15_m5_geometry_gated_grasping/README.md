# Sim15 M5 geometry-gated grasping diagnostics

Sim15 is the isolated software successor to Sim14. It consumes the hash-bound
`MECH_DYNAMICS_INTERFACE_V3` handoff and implements only the M5-authorized scope:

- strict-SI authority loading with interface, artifact, frozen-input, geometry,
  snapshot, and release-gate SHA-256 verification;
- instantaneous two-body rigid perfectly-plastic capture diagnostics that
  conserve total linear and angular momentum;
- per-body COM linear impulse (`N*s`) and angular impulse (`N*m*s`), plus the
  target junction couple shifted to an explicitly sourced grasp point;
- frozen six-DOF geometric fastener-group influence-matrix evaluation with an
  independent force/moment equilibrium reconstruction;
- a computed physical-contact gate and a diagnostic-only reset/step facade.

This revision cannot compute contact force, pressure, duration, compliance,
friction, strength, preload margin, slip, plate stress, formal FEA, flight MOS,
trained RL reward, or production dynamics. Unknown values remain `None`/`null`
with `HOLD` metadata. The helper `impulse_to_force` always raises because an
impulse must not be divided by an invented duration.

## Public interfaces

- `src.authority.load_authority(interface_path) -> AuthorityBundle`
- `src.rigid_capture.body_from_mapping(record) -> RigidBodyState`
- `src.rigid_capture.RigidPlasticCaptureSolver.capture(service, target) -> CaptureResult`
- `src.rigid_capture.junction_couple_impulse_at_point(...) -> (Lx,Ly,Lz)`
- `src.joint_loads.JointLoadDistributor(authority).distribute(pattern_id, wrench_N_Nm)`
- `src.contact_gate.PhysicalContactGate.evaluate(authority)` and `.require(authority)`
- `src.env.Sim15DiagnosticEnv(authority, acknowledgement=...)`

`Sim15DiagnosticEnv.reset()` returns `(observation, info)`. `step(action)`
returns `(observation, None, False, False, info)`; `None` reward is deliberate
because this is not an authorized RL environment. Actions are exact mappings:

- `{"operation": "capture", "anchor_id": "..."}`
- `{"operation": "joint_load_distribution", "pattern_id": "...", "wrench_N_Nm": [...]}`

Unknown action fields, torque/effort aliases, production mode, and
`{"operation": "physical_contact"}` fail closed.

## Baseline and validation

The deterministic LG-019 baseline contains eight capture-envelope cases:

```text
2 hash-bound targets × v_app {0.005, 0.01, 0.02, 0.03} m/s
target velocity = [0, v_app, 0] m/s; service velocity = [0, 0, 0] m/s
```

Each case retains its anchor angular rate and inertia, records complete input
metadata (`estimate/u/distribution/dof/source/correlation`), binds input,
solver, and output hashes, checks equal/opposite COM linear impulses, and
reports
`junction_couple_impulse_at_grasp_N_m_s = dL_com_target - (p-r_target) × J_target`.
The grasp lever is derived from the hash-bound target-model grasp coordinate
and M4 target COM. Its low-confidence/HOLD status is preserved.

A separate six-row table evaluates three frozen joint patterns under two
six-DOF verification wrenches. Those rows are geometric software V&V and are
not included in the eight capture cases.

After the M5 interface is explicitly frozen, generate the receipt:

```powershell
python tools/generate_baseline.py
python tools/run_validation.py
```

Before the final interface freeze, a non-writing source smoke is available:

```powershell
python tools/generate_baseline.py --stdout-only
python tools/run_validation.py --allow-missing-baseline
```

Run tests only:

```powershell
python -m pytest -q
```

An LG-019 pass closes only Sim15 diagnostic reproducibility. It does not write
back to M5, change the M5 gap count, authorize physical loads/contact/formal
FEA, or upgrade production/flight authority.
