# CURRENT_R2 DG5 design-level uncertainty candidate V1

This additive package binds the C01 `DEPLOYED_NOMINAL` design mass, center of mass, inertia tensor and their stated standard uncertainties to a deterministic design-screening replay. It also replays the Solar R2 `LOW / NOMINAL / HIGH` seven-mode ROM corners and binds the current DG1/DG2 15/15 candidate gate.

## Measurement and unit boundary

- mass: `kg`;
- center of mass: `m`, in frame `S`;
- inertia: `kg*m^2`, about the system center of mass in `S`;
- Solar stiffness parameters: `N*m^2` or `N*m/rad` as declared;
- modal frequencies: `Hz`.

The source gives standard uncertainties but no top-level joint covariance, probability distributions, or degrees of freedom. The evaluator therefore exhaustively evaluates all `2^10 = 1024` lexicographic sign combinations at `estimate ± 1u`. This is a deterministic design screen, **not** a tolerance box or a 68%/95% coverage region. Combined standard uncertainty, expanded uncertainty, coverage factor, and probability remain `null`.

The screen finds 880 corners for which positivity, positive definiteness, and the rigid-body principal-moment triangle inequality are not falsified. This is only a basic-constraint result, not proof that those corners are physically realizable or statistically admissible. It also exposes 144 inertia-component corners that remain positive definite but violate the triangle inequality. They are explicitly quarantined; they are not silently dropped or treated as physical samples. This falsifier shows why a physically parameterized covariance model is still required.

## Claim boundary

Maximum claim:

`DG5_BOUNDED_DESIGN_UNCERTAINTY_CANDIDATE_PASS__PARENT_DG5_HOLD`

The following remain explicit nulls/HOLD:

- as-built mass, CG, inertia and metrology uncertainty budget;
- all 22 contact-model `as_built` fields and a contact uncertainty budget;
- all 8 × 19 actuator measurement fields and an actuator uncertainty budget;
- hardware validity, production validity, Dynamics Engineering completion, next-stage authorization, and release credit.

## Reproduce

From this directory:

```powershell
python run_validation.py
python -m pytest
```

The evaluator uses no random sampling. Two independent in-process builds must have identical canonical hashes, and the manifest binds all local artifacts plus 16 external inputs.
