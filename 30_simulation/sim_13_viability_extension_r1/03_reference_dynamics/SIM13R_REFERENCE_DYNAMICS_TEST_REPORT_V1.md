# SIM13R REFERENCE DYNAMICS TEST REPORT V1

`RESEARCH_COUPLED_CLOSURE_R1 / SEI-RC-04 lane C (D2)` — 2026-08-30. `review_status = PENDING_OWNER_REVIEW`.

## Result

An independent momentum-level free-floating model reproduces the frozen sim_05 headline anchor to **1.225e-09 deg** (6.379e-11 relative), with no parameter tuning.

- reference model peak base attitude deviation: `19.199851621919` deg
- frozen sim_05 direct solver: `19.199851620694` deg
- residual linear momentum: `3.103e-17` N*s
- residual angular momentum: `3.469e-17` N*m*s

## Consistency checks

| check | value | pass |
|---|---|---|
| `C1_total_system_mass_kg` | 29.895555949342985 | True |
| `C2_linear_momentum_residual_Ns` | 3.1031677655443737e-17 | True |
| `C3_angular_momentum_residual_Nms` | 3.4694470181280623e-17 | True |
| `C4_generalized_jacobian_vs_finite_difference` | 3.6472984736579672e-09 | True |
| `C5_zero_joint_rate_gives_zero_base_motion` | 0.0 | True |
| `C6_system_com_stationary_under_zero_momentum` | 3.644680582789418e-12 | True |
| `C7_orthonormality_drift` | 2.4961144262647394e-11 | True |
| `C8_joint2_antiparallel_to_joint3` | -1.0 | True |
| `C9_dual_prismatic_opposed_in_palm_frame` | [-3.673e-06, -1.0, 0.0] | True |

## What is NOT yet reproduced

sim_06 post-capture rate, sim_08 captured-momentum accounting and sim_11 finite-contact-window anchors are **PENDING**. The first two depend on the capture rigidization path and the sim_10 geometry classes, which are behind the frozen-input hash lock (DISC-010); the third needs the flexible modal model (DISC-001). All three are deferred to D3 CaptureMap and recorded in the discrepancy ledger.

## Declared independence limitation

The dynamics implementation is independent. The **system composition** (which rigid bodies, the `T_SM` mount, gripper locked at q=0) was read from sim_05's documented definition — an anchor cannot be reproduced without knowing which system it models. This is recorded as `DYN-006`, not hidden.

## Reproduction

```bash
python 30_simulation/sim_13_viability_extension_r1/03_reference_dynamics/build_d2_reference_dynamics.py
```
