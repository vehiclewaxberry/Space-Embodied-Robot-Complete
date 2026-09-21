# sim_09 Gate E0 anchor regression report

generated: 2026-07-13 19:52:54  |  overall: ALL PASS

| test | status | worst residual | wall [s] | note |
|---|---|---|---|---|
| t1_impulse_anchor | PASS | 3.049e-05 | 0.1 | legacy_v0 scenario bit-matches build_capture_scenario; anchors from sim_06/sim_08 CSVs |
| t2_ik_roundtrip | PASS | 3.650e-08 | 15.9 | 5 FK-generated poses per mode, tol 1e-06 m / 1e-05 rad |
| t3_momentum | PASS | 1.579e-17 | 24.7 | |[P;L]|_inertial < 1e-10 at 200 samples (sim_05 momentum_inertial diagnostic) |
| t4_ancf_anchor | PASS | 8.977e-06 | 67.5 | sim_07a 6dof_rigid_lock/nominal case via the sim_09 adapter chain |
| t5_propagation | PASS | 2.322e-11 | 0.2 | const-omega analytic model + validated rigid_body torque-free core |
| t6_actuator_anchor | PASS | 0.000e+00 | 0.0 | digit-exact vs actuator_budget_sweep.csv (sim_08 rounding applied) |
| t7_determinism | PASS | 0.000e+00 | 109.3 | double evaluation bitwise identical (wall_time_ms excluded); hash sensitive to 1e-6 on v_app/t_c/omega/q0 |
| t8_e1_regression | PASS | 0.000e+00 | 25.4 | G0 anchors frozen; CSV integrity 72 rows / 24 admissible / hashes match deterministic grid |

## anchor detail rows

### t1_impulse_anchor

| anchor | expected | measured | residual | tol |
|---|---|---|---|---|
| omega_plus_dps | 3.0633 | 3.06333 | 3.04946e-05 | 0.001 |
| H_c_Nms | 3.651 | 3.65099 | 7.36445e-06 | 0.001 |
| L_grasp_Nms | 0.1217 | 0.121693 | 6.64012e-06 | 0.001 |

### t2_ik_roundtrip (per mode)

| mode | worst_pos_m | worst_ori_rad | nullity | limit_violations |
|---|---|---|---|---|
| pose_6d | 8.246e-10 | 3.650e-08 | [0] | 0 |
| approach_5d | 3.993e-10 | 3.650e-08 | [1] | 0 |
| position_3d | 7.091e-10 | 0.000e+00 | [3] | 0 |

### t4_ancf_anchor

| anchor | expected | measured | residual_rel | tol_rel |
|---|---|---|---|---|
| tip_peak_mm | 3.674 | 3.674 | 1.3526e-07 | 0.01 |
| U_max_J | 2.3444e-05 | 2.34438e-05 | 8.97736e-06 | 0.01 |

### t5_propagation

| check | residual | tol |
|---|---|---|
| P1_lever_invariance | 2.22045e-16 | 1e-12 |
| P2_central_difference | 1.66471e-11 | 1e-08 |
| P3_full_period_return | 1.70425e-16 | 1e-09 |
| P4_torque_free_vs_const | 2.32244e-11 | 1e-09 |

### t6_actuator_anchor

| row | expected_propellant_g | measured_propellant_g | residual |
|---|---|---|---|
| t_d=900s l=0.17 cold_gas_60s | 36.4998 | 36.4998 | 0 |
| t_d=900s l=0.17 green_mono_220s | 9.9545 | 9.9545 | 0 |
| t_d=60s l=0.05 cold_gas_60s | 124.099 | 124.099 | 0 |

### t8_e1_regression

| anchor | expected | measured | tol_rel | residual_rel |
|---|---|---|---|---|
| post_capture_rate_dps(live) | 3.05506 | 3.05506 | 1e-06 | 0 |
| H_RW_Nms(live) | 3.64714 | 3.64714 | 1e-06 | 0 |
| E_flex_J(csv) | 2.49005e-05 | 2.49005e-05 | 1e-09 | 0 |

