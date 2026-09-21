# Current R2 mechanical/dynamics additive increment V1

This package is an append-only convergence record. It does not modify or reissue
`CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4`.

It binds three new bounded evidence packages:

1. M4-L02 configuration/state and design mass traceability: 9/9 identities and
   design mass views, while current complete geometry, released collision,
   production-complete states and as-built properties remain 0/9.
2. M01 fixed-platform and `A::base_link` zero-motion precertification: three
   design-level fixed poses and exactly 1/150 motion certificates. The parent V4
   snapshot remains 0/150 until a formal parent reissue. Scene values remain
   0/30, scenes 0/3, clearance/pair queries 0/11166, edges 0 and path false.
3. A zero-total-momentum rigid, time-varying 6R+2P design-effort plant candidate:
   Gate 24/24, standalone validation 36/36 and independent negative controls
   28/28. Its 19 source pins include the seven transitive project modules used
   at runtime. It grants no flex, contact,
   target attachment, hardware, control, parent dynamics, Sim13 non-abort or
   release authority.

The source lock pins 13 current artifacts by byte count and SHA-256. The builder
and standalone validator do not import one another. The local manifest has a
frozen six-file payload allowlist, excludes itself to avoid circular hashing,
and explicitly excludes only the independent receipt because that receipt is
generated after and binds the manifest raw hash and entries hash. Cache,
bytecode and unlisted files fail validation.

Run from the repository root:

```powershell
python -B 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_increment_v1/build_increment_gate.py --check
python -B 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_increment_v1/validate_increment_gate.py --check
python -B -m pytest -q -p no:cacheprovider --basetemp=.tmp_r2_increment_pytest 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_increment_v1/test_increment_gate.py
```

To regenerate after an explicitly reviewed source-lock update:

```powershell
python -B 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_increment_v1/build_increment_gate.py --write
python -B 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_increment_v1/validate_increment_gate.py --write
```

Maximum claim:

```text
PASS_CONFIGURATION_TRACEABILITY_M01_BASE_MOTION_PRECERT_AND_TIME_VARYING_RIGID_PLANT_ADDITIVE_INCREMENT__CAD_SCENE_PAIR_CONTACT_POSTCAPTURE_CONTROL_NONABORT_PARENT_AND_RELEASE_HOLD
```
