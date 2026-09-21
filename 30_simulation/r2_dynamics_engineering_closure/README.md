# R2 constrained-dynamics engineering closure candidate

This package adds an explicit `2P locked` KKT diagnostic to the hash-fixed
Unified R2 8-DOF free-floating backend. Red-team unit and independence review
keeps DG1 and DG2 on HOLD: the 6R/2P nondimensional reference metric is not
frozen, and the zero-momentum residual is a mechanical-connection algebraic
identity rather than an independently integrated full-state conservation test.
It is not a released plant and not a flight or full capture-control result.

## Implemented

- Hash-bound current configuration: 19 links, 18 joints, 6R+2P,
  `31.022864807342987 kg`.
- Locked gripper mode solved as
  `M ddq + b = tau + J^T reaction`, `J ddq = 0`.
- Explicit left/right prismatic constraint reactions in N.
- Coordinate-elimination cross-check reported separately for revolute
  (rad/s^2), prismatic (m/s^2), reaction (N), base-linear (m/s^2), and
  base-angular (rad/s^2) quantities.
- Falsifier proving that `tauP = 0` does not imply locked 2P.
- Full 8-DOF actuated acceleration interface with all hardware limits left
  fail-closed when measurement authority is absent.
- A 0.004 s short-time energy/solver smoke test and algebraic zero-momentum
  identity diagnostic, explicitly carrying no independent conservation credit.
- Arm-stop and locked/actuated reaction-equivalence degenerations.
- Solar R2 dual-wing 14-mode LOW/NOMINAL/HIGH free-ringdown and ROM-domain
  diagnostics.

## Deliberate holds

DG1 requires a frozen 6R/2P nondimensionalization or reference metric plus a
unit-reparameterization invariance test. DG2 requires independent integration
of base pose/twist and joint state, including a nonzero-total-momentum case.
The 14-mode flex test is a component ringdown; arm-to-flex time-domain coupling
and the full coupled rigid-limit test remain `HOLD`. Contact transition,
post-capture target attachment, wheel state, as-built actuator dynamics, and
as-built mass/contact data are not implemented or are `MEASUREMENT_PENDING`.
No result is inherited between `LEGACY_24KG`, `CURRENT_R2`, and
`TARGET_ATTACHED`.

## Build and test

From the repository root:

```powershell
python -B 30_simulation/r2_dynamics_engineering_closure/src/build_dynamics_gate.py --repo-root .
python -B -m pytest -p no:cacheprovider 30_simulation/r2_dynamics_engineering_closure/tests -q
```

Primary machine results:

- `results/R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1.json`
- `results/R2_DYNAMICS_ENGINEERING_GATE_V1.json`
- `results/R2_DYNAMICS_ENGINEERING_DIAGNOSTICS_V1.json`
- `results/R2_DYNAMICS_PACKAGE_MANIFEST_V1.json`

Every execution authorization and release field remains `false`.

## 2026-08-27 additive candidate follow-ups

The immutable parent Gate above has not been rewritten. Separate hash-bound
packages now close bounded evidence gaps without inheriting parent credit:

- `dg1_dg2_candidate_v2/`: explicit 6R+2P reference metric plus prescribed
  nonzero-momentum full-base-pose reconstruction;
- `dg3_arm_flex_coupling_candidate_v1/`: frozen-linearization C=0
  conservation, true modes-removed, and provisional Solar R2 sensitivity
  diagnostics; no mixed-coordinate spectral credit;
- `dg4_contact_hybrid_candidate_v1/`: two-separate-rigid-body
  precontact-to-post-impact impulse diagnostics at the 0.005 m/s consumer
  bound; no attachment or physical-contact authority;
- `dg5_uncertainty_candidate_v1/`: deterministic design-level mass-property
  screening and three discrete provisional Solar R2 corners; no probability,
  as-built, contact, or actuator uncertainty credit.

Their joint status is consumed by
`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V3.json`.
`R2_DYNAMICS_ENGINEERING_GATE_V1.json` remains the parent scientific truth and
continues to report HOLD until a new parent Gate is explicitly reissued from
the full time-varying, torque-driven, contact/post-capture validation chain.
