import copy
import math
from pathlib import Path
import sys
import unittest

P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'tools'))
from power_phase_model import read,source_check,input_quantity,operating_point,phase_ledger,validate_timeline,ideal_radiating_area_m2

class ReferenceTradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=read(P/'inputs/REFERENCE_MISSION_V1.json')

    def test_source_identity(self):
        self.assertEqual(source_check(),7)

    def test_period_and_sun_eclipse(self):
        o=self.m['orbital_reference']
        self.assertTrue(validate_timeline(o['phases'],5700))
        self.assertEqual(sum(p['duration_s'] for p in o['phases'] if p['illumination']=='eclipse'),2100)

    def test_overlap_rejected(self):
        phases=copy.deepcopy(self.m['orbital_reference']['phases']);phases[1]['start_s']-=1
        with self.assertRaises(ValueError):validate_timeline(phases,5700)

    def test_unit_mismatch(self):
        with self.assertRaises(ValueError):input_quantity({'value':150,'unit':'g'},'kg')
        self.assertIsNone(input_quantity({'value':None,'unit':'kg'},'kg'))

    def test_radiation_uses_kelvin(self):
        # Independently evaluated Stefan-Boltzmann benchmark (100 W, 80 degC, 3 K, epsilon .89).
        self.assertAlmostEqual(ideal_radiating_area_m2(100,353.15,3,.89),0.1273976498957943,delta=1e-12)
        with self.assertRaises(ValueError):ideal_radiating_area_m2(100,290,300,.89)

    def test_radiation_area_increases_with_absorbed_heat(self):
        self.assertGreater(ideal_radiating_area_m2(100,353.15,3,.89,100),ideal_radiating_area_m2(100,353.15,3,.89))

    def test_energy_balance_and_no_extra_lug_double_count(self):
        r=operating_point(360,25.2,.01,.85)
        self.assertLess(abs(r['input_power_W']-360-r['known_nonarm_heat_W']),1e-8)
        self.assertIsNone(r['arm_internal_heat_W'])

    def test_low_voltage_cannot_be_certified(self):
        r=operating_point(360,20,.01,.85)
        self.assertEqual(r['protection_class'],'BLOCKED_BY_UVLO_SCREEN')
        self.assertFalse(r['hardware_ready'])

    def test_efficiency_changes_loss(self):
        self.assertLess(operating_point(360,25.2,.01,.9)['CHB_loss_W'],operating_point(360,25.2,.01,.85)['CHB_loss_W'])

    def test_unknown_stop_keeps_total_unknown(self):
        r=phase_ledger(self.m,120,20,5,initial_Wh=200)
        self.assertIsNone(r['full_cycle_energy_Wh'])
        self.assertIsNone(r['full_cycle_battery_remaining_Wh'])
        self.assertIsNone(r['solar_recharge_Wh'])
        self.assertIn('LIT_STOP_WINDOW',r['unknown_phases'])
        self.assertIn('ECLIPSE_COLD_HOLD_HEATER_SUPPLY_PATH',r['unknown_phases'])
        self.assertGreater(r['known_phase_subtotal_Wh'],r['prefix_before_first_unknown_Wh'])

    def test_holding_not_zero_filled(self):
        low=phase_ledger(self.m,120,20,5)['known_phase_subtotal_Wh']
        high=phase_ledger(self.m,120,60,5)['known_phase_subtotal_Wh']
        self.assertGreater(high,low)
        with self.assertRaises(ValueError):phase_ledger(self.m,120,None,5)

    def test_invalid_inputs(self):
        for power,V,R,eta in [(math.nan,25,.01,.85),(120,25,-.01,.85),(120,25,.01,1.1),(True,25,.01,.85)]:
            with self.assertRaises(ValueError):operating_point(power,V,R,eta)

    def test_negative_heater_cannot_create_energy_credit(self):
        m=copy.deepcopy(self.m);m['orbital_reference']['phases'][-1]['heater_thermal_output_W']=-20
        with self.assertRaises(ValueError):phase_ledger(m,120,20,5)

    def test_heater_is_separate_unsolved_budget(self):
        r=phase_ledger(self.m,120,20,5)
        self.assertAlmostEqual(r['heater_ideal_extra_budget_Wh'],25*600/3600)
        self.assertIsNone(r['rows'][-1]['combined_load_protection_status'])
        self.assertFalse(r['rows'][-1]['heater_supply_path_verified'])

    def test_unknown_heater_never_gets_protection_credit(self):
        m=copy.deepcopy(self.m);m['orbital_reference']['phases'][-1]['heater_thermal_output_W']=None
        r=phase_ledger(m,120,20,5)
        self.assertIsNone(r['rows'][-1]['heater_ideal_extra_input_Wh'])
        self.assertIsNone(r['rows'][-1]['combined_load_protection_status'])

    def test_brake_bias_is_an_explicit_input(self):
        a=operating_point(120,25.2,.01,.85,brake_bias_W=1)
        b=operating_point(120,25.2,.01,.85,brake_bias_W=2)
        self.assertEqual(b['main_output_W']-a['main_output_W'],1)
        self.assertGreater(b['input_power_W'],a['input_power_W'])

if __name__=='__main__':unittest.main()
