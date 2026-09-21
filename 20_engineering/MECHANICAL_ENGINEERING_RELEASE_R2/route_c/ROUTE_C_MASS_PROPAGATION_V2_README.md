# Route-C Mass Propagation V2

## Purpose and authority

`ROUTE_C_MASS_PROPAGATION_V2.py` is the corrected, fail-closed RC-5/TMG-2
mass-property propagation utility. It is an analysis tool, not a Gate or release
authority. It never edits the frozen R2 mass baseline, the accepted URDF, Route-C
CAD, a prior V1 artifact, or any release Gate.

The V1 defect was structural: it searched each R2 configuration for
`components`, while the frozen schema stores the B601 member and its
`transform_ref` under `composition`. V1 therefore supplied q=0 to all nine
configurations. V2 has no fallback to `components`; every configuration must
contain exactly one B601 member, resolve exactly one named pose, and provide six
finite joint values. A missing or malformed binding aborts the whole run.

## Coordinate, unit, and reference-point contract

- Output frame: spacecraft frame `S`.
- Mass: `kg`; position: `m`; inertia: `kg*m^2`.
- CAD geometry enters in `mm` and is converted at the input boundary.
- The input inertia tensor is about the baseline configuration centre of mass.
- The output inertia tensor is about the updated centre of mass.
- Both before and after tensors are also reported about the fixed, directly
  comparable point `O_S = [0, 0, 0] m`.
- All six independent inertia components and the complete symmetric 3x3 matrix
  are emitted. The physical checks cover finiteness, symmetry, positive
  semidefiniteness, principal-moment triangle inequalities, positive mass,
  joint limits, and a parallel-axis round trip.

## Uncertainty is not an acceptance limit

The tool carries the frozen baseline standard uncertainties as metrology
metadata. It does not reinterpret them as tolerances. Route-C input uncertainty
is reported separately using three correlated-within-group scale variables:
aluminium hardware, polymer hardware, and bundle linear density. First-order
GUM sensitivities are accompanied by a deterministic Monte Carlo diagnostic.

The baseline/Route-C cross-covariance is unavailable, so V2 does not invent a
combined updated-system standard uncertainty. ODR-50 contains the qualitative
trigger “Route-C changes system mass/CG/inertia beyond current uncertainty
envelope” but supplies no approved numerical acceptance rule or guard-band
policy. Therefore every configuration reports:

`NOT_EVALUATED_NO_APPROVED_NUMERICAL_ACCEPTANCE_RULE`

This is neither a TMG-2 pass nor a TMG-2 fail.

## V7 non-authorizing self-test

From this directory:

```powershell
python -B .\ROUTE_C_MASS_PROPAGATION_V2.py `
  --variant V7 `
  --self-test `
  --output .\ROUTE_C_MASS_PROPAGATION_V2_SELFTEST_V7.json
```

For development checks without writing an artifact:

```powershell
python -B .\ROUTE_C_MASS_PROPAGATION_V2.py `
  --variant V7 `
  --self-test `
  --check-only `
  --mc-samples 2048
```

Output paths must remain below this Route-C directory and existing files are
refused. The V7 self-test is intentionally non-authorizing and must not be cited
as a V8, TMG-2, release, or flight-qualification conclusion.

## Known model boundary

The Route-C CAD builder splits each cable segment mass equally among its declared
`host_links`. V2 preserves that bookkeeping contract and rigidly hosts each share
for pose propagation. Distributed cable deformation between adjacent links is not
represented. Hardware mass is recomputed from the exact post-cut mesh-pack solids;
the builder's rounded candidate registry may differ because its receipt layer is
not the exact post-cut solid integration. Both values and residuals remain visible.
