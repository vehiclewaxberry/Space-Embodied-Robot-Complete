import copy
import math
import unittest
from actuator_model import (wheel_storage_check, wheel_direction_capacity,
                            synthetic_reference, wrench_matrix, matrix_rank,
                            allocate_reference_impulse, current_cpod_capability)


class ActuatorModelTests(unittest.TestCase):
    def test_wheel_axis_storage_and_external_conservation(self):
        r = wheel_storage_check([0.08, -0.08, 0.0])
        self.assertTrue(r['storage_feasible'])
        self.assertEqual(r['system_external_angular_impulse_Nms'], [0, 0, 0])

    def test_scalar_sum_false_positive_rejected(self):
        self.assertLess(0.25, 0.3)
        self.assertFalse(wheel_storage_check([0.25, 0, 0])['storage_feasible'])

    def test_initial_storage_consumes_margin(self):
        self.assertFalse(wheel_storage_check([0.03, 0, 0], [0.09, 0, 0])['storage_feasible'])

    def test_directional_capacity_not_one_scalar(self):
        self.assertAlmostEqual(wheel_direction_capacity([1, 0, 0])['additional_storage_capacity_Nms'], 0.1)
        self.assertAlmostEqual(wheel_direction_capacity([1, 1, 1])['additional_storage_capacity_Nms'], math.sqrt(3)*0.1)

    def test_invalid_and_nonfinite_rejected(self):
        for v in ([float('nan'), 0, 0], [float('inf'), 0, 0], [0, 0]):
            with self.assertRaises(ValueError):
                wheel_storage_check(v)
        with self.assertRaises(ValueError):
            wheel_direction_capacity([0, 0, 0])

    def test_wrench_moment_sign_and_rank(self):
        ref = synthetic_reference()
        B = wrench_matrix(ref['nozzles'])
        self.assertEqual(matrix_rank(B), 6)
        self.assertAlmostEqual(B[0][0], 1)
        self.assertAlmostEqual(B[5][0], -0.15)
        self.assertEqual(matrix_rank([[0, 0], [0, 0]]), 0)

    def test_pure_torque_pair_reconstruction(self):
        r = allocate_reference_impulse([0, 0, 0, 0, 0, 0.00036], 1)
        self.assertTrue(r['plan_feasible_within_declared_constraints'])
        self.assertEqual(r['simultaneous_jet_count'], 2)
        self.assertTrue(all(abs(v) < 1e-12 for v in r['algebraic_linear_residual_Ns']))
        self.assertTrue(all(abs(v) < 1e-12 for v in r['algebraic_angular_residual_Nms']))
        self.assertAlmostEqual(r['pulse_plan'][0]['duration_s'], 0.1)

    def test_full_rank_does_not_prove_unilateral_feasibility(self):
        ref = synthetic_reference()
        ref['nozzles'] = [n for n in ref['nozzles'] if n['force_sign'] == 1]
        self.assertEqual(matrix_rank(wrench_matrix(ref['nozzles'])), 6)
        r = allocate_reference_impulse([-0.0012, 0, 0, 0, 0, 0], 1, ref)
        self.assertFalse(r['plan_feasible_within_declared_constraints'])
        self.assertIn('REQUIRED_UNILATERAL_DIRECTION_NOT_AVAILABLE', r['violations'])

    def test_full_rank_does_not_override_concurrency(self):
        r = allocate_reference_impulse([0, 0, 0, 0.00036, 0.00036, 0], 1)
        self.assertEqual(r['wrench_linear_rank'], 6)
        self.assertIn('MAXIMUM_CONCURRENCY_EXCEEDED_FOR_THIS_PLAN', r['violations'])

    def test_full_rank_does_not_override_minimum_pulse(self):
        r = allocate_reference_impulse([0, 0, 0, 0, 0, 0.00001], 1)
        self.assertIn('PULSE_BELOW_MINIMUM_FOR_THIS_EXACT_PLAN', r['violations'])
        self.assertFalse(r['global_reachability_proven'])

    def test_fixed_force_window_constraint(self):
        r = allocate_reference_impulse([0, 0, 0, 0, 0, 0.0036], 0.5)
        self.assertIn('PULSE_EXCEEDS_WINDOW_AT_FIXED_ON_FORCE', r['violations'])

    def test_reference_origin_must_be_explicit(self):
        ref = synthetic_reference()
        ref['reference_COM_m'] = [0.03, 0, 0]
        with self.assertRaises(ValueError):
            allocate_reference_impulse([0]*6, 1, ref)

    def test_hardware_claim_and_schema_guard(self):
        r = current_cpod_capability()
        self.assertIsNone(r['wrench_matrix'])
        self.assertIsNone(r['rank'])
        self.assertFalse(r['actual_6DOF_capability_verified'])
        ref = synthetic_reference()
        ref['classification'] = 'C_POD'
        with self.assertRaises(ValueError):
            allocate_reference_impulse([0]*6, 1, ref)

    def test_all_six_signed_basis_directions_have_bounded_plans(self):
        for axis in range(6):
            for sign in (-1, 1):
                desired = [0.0]*6
                desired[axis] = sign*(0.0012 if axis < 3 else 0.00036)
                r = allocate_reference_impulse(desired, 1)
                self.assertTrue(r['plan_feasible_within_declared_constraints'], (axis, sign, r))


if __name__ == '__main__':
    unittest.main()
