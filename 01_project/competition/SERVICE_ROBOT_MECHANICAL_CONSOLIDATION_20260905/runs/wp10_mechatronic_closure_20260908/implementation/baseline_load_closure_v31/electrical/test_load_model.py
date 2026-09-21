import math
import unittest
from load_model import (evaluate_axis_power, phase_copper_loss_W, phase_energy_Wh,
                        sampled_bus_metrics, complete_sensitivity_scenario)

class LoadModelTest(unittest.TestCase):
    def complete(self, **changes):
        p=dict(torque_output_Nm=2, omega_output_rad_s=3, phase_resistance_ohm=0.5,
               phase_currents_rms_A=[1,1,1], gearbox_loss_W=0.5,
               core_and_mechanical_loss_W=0.25, driver_loss_W=0.5,
               electronics_standby_W=0.25, internal_energy_rate_W=0, bus_voltage_V=24)
        p.update(changes)
        return evaluate_axis_power(**p)

    def test_unknown_is_not_zero(self):
        r=evaluate_axis_power(torque_output_Nm=0,omega_output_rad_s=0)
        self.assertIsNone(r['demanded_bus_power_W'])
        self.assertIn('driver_loss_W',r['missing_inputs'])

    def test_stall_holding_dissipates(self):
        r=self.complete(omega_output_rad_s=0)
        self.assertEqual(r['terms']['shaft_mechanical_power_W'],0)
        self.assertEqual(r['demanded_bus_power_W'],3)

    def test_phase_is_not_bus_current(self):
        r=self.complete()
        self.assertEqual(r['terms']['phase_copper_loss_W'],1.5)
        self.assertEqual(r['demanded_bus_current_A'],9/24)
        self.assertNotEqual(r['demanded_bus_current_A'],3)

    def test_regeneration_no_credit(self):
        r=self.complete(torque_output_Nm=-2)
        self.assertEqual(r['demanded_bus_power_W'],-3)
        self.assertEqual(r['regenerative_power_available_W'],3)
        self.assertIsNone(r['battery_recovery_credit_Wh'])

    def test_negative_mechanical_not_necessarily_regen(self):
        r=self.complete(torque_output_Nm=-0.1)
        self.assertGreater(r['demanded_bus_power_W'],0)
        self.assertEqual(r['regenerative_power_available_W'],0)

    def test_magnetic_storage_not_silently_ignored(self):
        self.assertIsNone(self.complete(internal_energy_rate_W=None)['demanded_bus_power_W'])

    def test_bad_inputs_rejected(self):
        for changes in ({'driver_loss_W':-1},{'bus_voltage_V':0},{'torque_output_Nm':float('nan')}):
            with self.assertRaises(ValueError): self.complete(**changes)
        with self.assertRaises(ValueError): phase_copper_loss_W(1,[1,1])

    def test_unknown_phase_current(self):
        self.assertIsNone(phase_copper_loss_W(.5,[1,None,1]))

    def test_energy_unit_conversion(self):
        self.assertEqual(phase_energy_Wh(360,10),1)
        self.assertIsNone(phase_energy_Wh(None,10))
        with self.assertRaises(ValueError): phase_energy_Wh(1,-1)

    def test_hold_independent(self):
        a=complete_sensitivity_scenario(60,hold_bus_power_W=None,standby_bus_power_W=5,gripper_bus_power_W=None)
        self.assertFalse(a['complete'])
        self.assertIsNone(a['hold_bus_power_W'])

    def test_split_consumption_and_return(self):
        samples=[{'time_s':0,'bus_voltage_V':24,'bus_current_A':1},
                 {'time_s':2,'bus_voltage_V':24,'bus_current_A':-1}]
        r=sampled_bus_metrics(samples)
        self.assertAlmostEqual(r['consumed_Wh'],12/3600)
        self.assertAlmostEqual(r['returned_Wh'],12/3600)
        self.assertEqual(r['net_Wh'],0)
        self.assertEqual(r['bus_current_mean_A'],0)
        self.assertGreater(r['bus_current_rms_A'],0)

    def test_missing_sample_not_interpolated(self):
        r=sampled_bus_metrics([dict(time_s=0,bus_voltage_V=24,bus_current_A=1),
                               dict(time_s=1,bus_voltage_V=24,bus_current_A=None)])
        self.assertEqual(r['status'],'UNKNOWN_MISSING_SAMPLES')

    def test_nonmonotonic_time_rejected(self):
        with self.assertRaises(ValueError):
            sampled_bus_metrics([dict(time_s=1,bus_voltage_V=24,bus_current_A=1)]*2)

if __name__=='__main__': unittest.main()
