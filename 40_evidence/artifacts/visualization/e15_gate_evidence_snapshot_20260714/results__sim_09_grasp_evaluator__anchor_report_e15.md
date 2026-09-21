# sim_09 Gate E1.5 regression report

generated: 2026-07-14 08:08:08 | overall: ALL PASS

| test | status | worst residual | wall [s] | note |
|---|---:|---:|---:|---|
| t1_impulse_anchor | PASS | 3.049458e-05 | 0.096 | legacy_v0 scenario bit-matches build_capture_scenario; anchors from sim_06/sim_08 CSVs |
| t2_ik_roundtrip | PASS | 3.650024e-08 | 10.839 | 5 FK-generated poses per mode, tol 1e-06 m / 1e-05 rad |
| t3_momentum | PASS | 1.578631e-17 | 16.835 | \|[P;L]\|_inertial < 1e-10 at 200 samples (sim_05 momentum_inertial diagnostic) |
| t4_ancf_anchor | PASS | 8.977365e-06 | 43.771 | sim_07a 6dof_rigid_lock/nominal case via the sim_09 adapter chain |
| t5_propagation | PASS | 2.322442e-11 | 0.114 | const-omega analytic model + validated rigid_body torque-free core |
| t6_actuator_anchor | PASS | 0.000000e+00 | 0.006 | digit-exact vs actuator_budget_sweep.csv (sim_08 rounding applied) |
| t7_determinism | PASS | 0.000000e+00 | 73.688 | double evaluation bitwise identical (wall_time_ms excluded); hash sensitive to 1e-6 on v_app/t_c/omega/q0 |
| t8_e1_regression | PASS | 0.000000e+00 | 17.445 | G0 anchors frozen; CSV integrity 72 rows / 24 admissible / hashes match deterministic grid |
| t9_geometry_invariance | PASS | 5.156986e-13 | 49.396 |  |
| t10_ancf_reliability | PASS | nan | 0.187 |  |
| t11_mpcs_validity | PASS | nan | 17.469 |  |
