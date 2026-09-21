import copy, unittest
from propulsion_contract import source_config,supply_screen,pulse_screen,mounting_screen,wrench_model,LOCKED_SHA

class ContractChecks(unittest.TestCase):
    def test_source_high_voltage_wrong_channel(self):
        self.assertEqual(source_config(24,0,2,12,True)['status'],'REJECT')
    def test_source_high_voltage_wrong_regulator(self):
        self.assertEqual(source_config(24,1,1,12,True)['status'],'REJECT')
    def test_source_default_is_not_12V(self):
        self.assertEqual(source_config(24,0,1,3.3,True)['status'],'REJECT')
    def test_nominal_does_not_bind_option(self):
        self.assertEqual(source_config(24,0,1,12)['status'],'UNKNOWN')
    def test_parallel_pins_not_four_amperes(self):
        self.assertEqual(source_config(24,0,1,12,True)['channel_total_current_A_catalog_max'],2)
    def test_source_headroom_strict_boundary(self):
        self.assertEqual(source_config(13.5,0,1,12,True)['status'],'REJECT')
    def test_source_config_is_not_energization(self):
        self.assertFalse(source_config(24,0,1,12,True)['energization_allowed'])
    def test_unknown_transient_stays_unknown(self):
        self.assertEqual(supply_screen(12,12,0,None,0)['status'],'UNKNOWN')
    def test_voltage_upper_includes_idle(self):
        self.assertEqual(supply_screen(12,12.55,0,.1,.8)['status'],'REJECT')
    def test_voltage_lower_includes_hot_loop(self):
        self.assertEqual(supply_screen(9.1,12,0,0,1)['status'],'REJECT')
    def test_conditional_steady_screen(self):
        r=supply_screen(11.8,12.2,.1,.1,.3)
        self.assertEqual(r['status'],'PASS_CONDITIONAL_STEADY_SCOPE')
        self.assertFalse(r['energization_allowed']);self.assertFalse(r['startup_heater_peak_covered'])
    def test_invalid_numeric_bounds(self):
        self.assertEqual(supply_screen(12,11,0,0,0)['status'],'REJECT')
        self.assertEqual(supply_screen(float('nan'),12,0,0,0)['status'],'UNKNOWN')
    def test_power_scope_not_eight_valves(self):
        self.assertEqual(supply_screen(12,12,0,0,0,20)['status'],'UNKNOWN')
    def test_valve_response_not_minimum_pulse(self):
        self.assertEqual(pulse_screen(.01*.01)['status'],'REJECT')
    def test_minimum_impulse_rectangular_only(self):
        r=pulse_screen(.0005)
        self.assertAlmostEqual(r['nominal_rectangular_equivalent_duration_s'],.05)
        self.assertAlmostEqual(r['steady_rectangular_equivalent_duration_s'][0],1/24)
        self.assertAlmostEqual(r['steady_rectangular_equivalent_duration_s'][1],.0625)
        self.assertIsNone(r['oem_command'])
    def test_foreign_revision_rejected(self):
        self.assertEqual(pulse_screen(.0005,'2bf995824f1c4f2374fe3f7707e6b86f6b138d80bcd75cfdee938938019813a3')['status'],'REJECT')
    def test_metric_fastener_rejected(self):
        self.assertEqual(mounting_screen('M3x0.5')['status'],'REJECT')
    def test_thread_alone_does_not_release_adapter(self):
        self.assertEqual(mounting_screen('.112-40 UNC-2B')['status'],'UNKNOWN')
    def test_no_synthetic_wrench(self):
        r=wrench_model({'source_sha256':LOCKED_SHA,'jet_count':8})
        self.assertIsNone(r['matrix']);self.assertEqual(r['physical_commands_emitted'],0)
    def test_required_geometry_cannot_be_zero_filled(self):
        r=wrench_model({'source_sha256':LOCKED_SHA,'nozzle_xyz_m':[[0,0,0]]*8})
        self.assertEqual(r['status'],'UNKNOWN_INPUTS_MISSING');self.assertIsNone(r['matrix'])

if __name__=='__main__': unittest.main(verbosity=2)
