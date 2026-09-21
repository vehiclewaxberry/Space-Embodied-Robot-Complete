# DG3 arm-to-flex coupling candidate V1

This additive package evaluates the frozen CURRENT_R2 configuration in the
coordinate order:

```text
[ S-frame base tangent 6, articulated joint 8, Solar R2 modal 14 ]
```

Its maximum claim is a bounded, frozen-linear DG3 candidate. Parent DG3,
hardware validity, production dynamics, next-stage authorization, and release
credit remain false.

## Credited lanes

- LOW/NOMINAL/HIGH `C=0` prescribed-arm lanes gate Radau/BDF agreement,
  arm-to-base-to-modal response, work-energy closure, and total bus+modal
  canonical base linear/angular momentum.
- An unforced `C=0` free-response lane gates total mechanical-energy and
  canonical-momentum conservation.
- A true modes-removed constrained-rigid lane contains a 14 x 14
  base-plus-joint mass matrix, 12 integrated base states, and exactly zero modal
  DOF. Its analytic and Radau/BDF comparisons are separately gated as position
  (m), attitude (rad), linear rate (m/s), and angular rate (rad/s).
- The separate zero-base-modal-coupling falsifier retains all 14 modal DOF. It
  is not called or credited as rigid degeneration. Its comparison with the
  modes-removed lane uses the same four separately unit-labelled Gates.

The damped LOW/NOMINAL/HIGH cases remain sensitivity/design diagnostics only.
They carry no Gate credit.

## Mixed-coordinate spectral boundary

The 28 x 28 matrix mixes translation, rotation, revolute/prismatic joint, and
mass-normalized modal coordinates. No numerical eigenvalue, condition number,
spectral radius, or Cholesky pivot is emitted. The spectral record is only a
`DIAGNOSTIC_NO_SPECTRAL_CREDIT` policy marker with `units=null` and
`gate_credit=false`.

Every mass matrix used by a solver is checked by boolean Cholesky structure
tests: rigid 14 x 14, base Hbb 6 x 6, dual-wing modal 14 x 14, full 28 x 28,
and solved Muu 20 x 20. These checks assert finite, symmetric, positive-definite
structure without assigning physical meaning to a mixed-unit spectral scalar.

## Fail-closed contract boundary

The duplicate-key rejecting loader also verifies the canonical SHA-256 of the
entire parsed contract. Named checks additionally freeze the exact schema,
authority scope, allowed/forbidden claims, owner-review status, release holds,
all Gate-sensitive thresholds and units, solver controls, excitation authority,
execution-guard dictionary, frozen q0, and LOW/NOMINAL/HIGH parameter meaning.

Nine in-memory negative controls must all be rejected: authority promotion,
forbidden-claim deletion, threshold widening, unit tampering, corner tampering,
excitation-authority promotion, solver relaxation, execution-guard key removal,
and frozen-q0 mutation. The generated 30-check Gate directly depends on the
exact contract validator and these negative controls.

## ROM and frame binding

The evaluator machine-recomputes:

- mode order B1-B3 followed by T1-T4;
- `Mrom` against the mass-normalized identity;
- `Gamma_t = Phi^T B_t` and `Gamma_r = Phi^T B_r`;
- LEFT/RIGHT mirror signs and structural-zero masks;
- the spacecraft-bus `S` root and both Solar R2 root transforms against the
  ROM geometry and Unified R2 frame ledger.

The Unified URDF is parsed directly. Its two solar links are each 0.78 kg, and
the 31.022864807342987 kg system mass already contains their 1.56 kg total.
Modal-coordinate blocks add no second rigid-wing mass. A deliberate
`+1.56 kg` negative control must be detected.

## E23 compatibility boundary

E23 C07 consumes the legacy dynamics placement at x=0.18525 m with no clocking.
Unified R2 resolves the physical B601 root at x=0.208 m with 25.000014 degrees
clocking. The resulting Hbb relative Frobenius mismatch is
0.005153002326417072 (0.5153002326417072%). This is a representation change,
not flexibility error; E23 numerical values are not inherited.

## Reproduce

```powershell
python run_validation.py
python -m pytest -q
```
