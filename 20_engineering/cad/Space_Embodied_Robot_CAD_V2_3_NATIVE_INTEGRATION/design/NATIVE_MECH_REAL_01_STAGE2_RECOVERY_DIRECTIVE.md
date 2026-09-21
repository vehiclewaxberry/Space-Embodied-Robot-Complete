# NATIVE-MECH-REAL-01 Stage 2 recovery directive

## 1. Scope and process gate

- Continue the existing Claude Code writer session
  `f3fdd206-d339-4b1d-9c47-b86b3f1d5269`.
- `SOLIDWORKS_SOLE_WRITER=CLAUDE_CODE` remains binding.
- The only allowed CAD write root is
  `Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION`.
- At entry, require exactly one running and responding `SLDWORKS.exe`.
  The expected observed PID is `89180`; treat the PID as observational, not
  as a license to kill or restart it.
- Forbidden in this recovery slice:
  - `taskkill`, `Stop-Process`, `ExitApp`, or any forced/graceful SolidWorks
    process termination;
  - launching another SolidWorks instance;
  - HIFI STEP import;
  - top-level spacecraft insertion;
  - deleting or moving native CAD files;
  - editing V2.0, V2.1, V2_2_NATIVE, vendor, or URDF sources.
- If the SolidWorks process count is not exactly one, COM disconnects, an RPC
  failure occurs, a modal cannot be positively identified, or any required API
  call returns false, stop this recovery slice and emit a HOLD record. Do not
  retry by restarting SolidWorks.

## 2. Prior evidence adjudication

The existing `mass_surrogate_readback.json` is invalid as a PASS record:

- SolidWorks total mass readback:
  `0.005000000000000002 kg`;
- accepted URDF target:
  `4.695555949342986 kg`;
- absolute error:
  `4.690555949342986 kg`;
- `tolerance_1e9_met=false`;
- center of mass and inertia were stored only as custom properties;
- status was nevertheless written as `PASS`.

Do not overwrite or delete this historical evidence. Create
`mass_surrogate_evidence_adjudication.json` that marks it
`INVALID_PASS_DOWNGRADED_TO_HOLD` and binds its SHA-256.

## 3. Single-part native override probe

Before touching the ten final mass-surrogate parts, create one isolated native
scratch part under:

`evidence/stage2_b601_three_rep/scratch_mass_override_probe/`

Use the SolidWorks 2024 early-bound type library or an equivalent verified
dispatch that exposes `IMassProperty2` and
`IMassPropertyOverrideOptions`. Use this API chain:

```python
mp = model.Extension.CreateMassProperty2()
mp.UseSystemUnits = True
opt = mp.GetOverrideOptions()

opt.OverrideMass = True
assert opt.SetOverrideMassValue(mass_kg)

opt.OverrideCenterOfMass = True
assert opt.SetOverrideCenterOfMassValue(list(com_xyz_m), "")

opt.OverrideMomentsOfInertia = True
I9 = [
    ixx, ixy, ixz,
    ixy, iyy, iyz,
    ixz, iyz, izz,
]
assert opt.SetOverrideMomentsOfInertiaValue(0, I9, "")

assert mp.SetOverrideOptions(opt, 1, None)
assert mp.Recalculate()
```

Semantics:

- `UseSystemUnits=True` means kg, m, and kg*m^2;
- moment reference frame `0` means center of mass;
- configuration option `1` means this configuration.

Persist the scratch part, close it, reopen it without restarting SolidWorks,
and read back:

- all three override flags;
- override mass value;
- override center-of-mass vector;
- override 3x3 inertia tensor;
- calculated mass, center of mass, and moment of inertia.

Every setter, `SetOverrideOptions`, `Recalculate`, save, close, reopen, and
readback operation must be recorded with its actual return value. Do not infer
success from file presence.

If this probe does not pass, stop and write
`mass_override_recovery_readback.json` with
`status=HOLD_SINGLE_PART_PROBE_FAILED`.

## 4. Ten-link application

Only after the scratch probe passes:

- use the current ten `MASS_<urdf_link>.SLDPRT` files as the sole final mass
  objects;
- do not create a second `B601_MASS_<urdf_link>.SLDPRT` family;
- parse mass, inertial origin, and the six independent inertia components from
  `evidence/stage2_b601_three_rep/b601_authority_contract.json`;
- bind the accepted URDF SHA-256
  `1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164`;
- apply native mass, center-of-mass, and full inertia-tensor overrides to every
  link;
- save, close, and reopen each part before readback;
- rebuild `B601_MASS_SURROGATE.SLDASM` only if necessary, referencing exactly
  those ten `MASS_*` parts once each.

Assembly total mass target:

`4.695555949342986 kg`

Assembly absolute tolerance:

`<= 1e-9 kg`

If SolidWorks persistence precision cannot meet this tolerance, record the
actual precision and return HOLD.

## 5. Required evidence and exit

Create:

- `mass_surrogate_evidence_adjudication.json`;
- `mass_override_probe_readback.json`;
- `mass_override_recovery_readback.json`.

The recovery record must bind:

- producer script path and SHA-256;
- all ten native part paths and SHA-256 values;
- assembly path and SHA-256;
- source URDF path and SHA-256;
- configuration name;
- override flags;
- target/readback values and absolute errors for mass, COM, and inertia;
- assembly component paths and multiplicities;
- SolidWorks PID count at entry and exit;
- exact PASS/HOLD expression.

PASS is allowed only when:

`all_10_parts_present`
`AND no_duplicate_mass_family`
`AND all_native_override_calls_true`
`AND all_override_flags_persisted_after_reopen`
`AND all_readback_errors_within_declared_tolerances`
`AND assembly_has_exactly_10_unique_link_components`
`AND abs(total_mass - 4.695555949342986) <= 1e-9`
`AND solidworks_pid_count_at_exit == 1`

After writing evidence, stop. Do not continue to HIFI, three-representation
mutual-exclusion, top-level insertion, or global cold-start validation in this
recovery slice.
