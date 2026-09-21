# sim_06 verification report (Gate A)

| module | test | status | worst residual |
|---|---|---|---|
| test_linear_momentum | test_grid_linear_momentum | PASS | 0.00e+00 |
| test_linear_momentum | test_impulse_sum_zero | PASS | 4.02e-16 |
| test_linear_momentum | test_random_linear_momentum | PASS | 1.63e-16 |
| test_angular_momentum | test_arbitrary_origin | PASS | 1.83e-15 |
| test_angular_momentum | test_grid_angular_momentum_origin | PASS | 3.86e-16 |
| test_energy_dissipation | test_already_rigid_zero_dissipation | PASS | 8.16e-16 |
| test_energy_dissipation | test_grid_energy | PASS | 0.00e+00 |
| test_energy_dissipation | test_random_energy | PASS | - |
| test_frame_invariance | test_grid_frame_invariance | PASS | 8.47e-12 |
| test_frame_invariance | test_random_frame_invariance | PASS | 9.67e-13 |
| test_limiting_cases | test_1_coincident_coms | PASS | - |
| test_limiting_cases | test_2_zero_relative_translation | PASS | - |
| test_limiting_cases | test_3_target_mass_to_zero | PASS | - |
| test_limiting_cases | test_4_central_plastic_impact | PASS | - |
| test_limiting_cases | test_5_pure_eccentric_translation | PASS | - |
| test_limiting_cases | test_6_axisymmetric_spin_about_line_of_centers | PASS | - |
| test_limiting_cases | test_7_mass_inertia_scaling | PASS | - |
| test_limiting_cases | test_8_velocity_scaling | PASS | - |
| test_limiting_cases | test_9_project_grasp_at_target_com | PASS | - |
| test_spatial_inertia_crosscheck | test_grid_crosscheck | PASS | 6.80e-14 |
| test_spatial_inertia_crosscheck | test_random_crosscheck | PASS | 5.09e-14 |
| test_point_contact | test_central_impact_equals_rigid | PASS | - |
| test_point_contact | test_conservation_and_bounds | PASS | 1.03e-15 |
| test_point_contact | test_matched_velocity_noop | PASS | - |
| test_point_contact | test_project_scenario_point_vs_rigid | PASS | see log |

- total: 25, failed: 0
- residuals are normalized (relative); float column = worst case over the sweep.
- suites cover: P/H conservation (origin + arbitrary points), plastic dT bounds,
  rigid translation/rotation/Galilean-boost invariance, 9 limiting cases with
  closed-form expectations, and an independent 6x6 spatial-inertia implementation.
