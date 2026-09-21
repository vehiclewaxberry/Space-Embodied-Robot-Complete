import unittest
from dataclasses import replace
from stop_supervisor import Observation,Supervisor,State

def good(i,**kw):
    d=dict(sequence=i,time_ms=i+1,binding_verified=True,independent_stop_chain_ok=True,bus_supply_ok=True,converter_thermal_ok=True,brake_thermal_ok=True,regen_path_available=True,return_path_ok=True,can_heartbeat_ok=True,aux_closed=False,load_bus_discharged=True,support_engaged=True,residual_energy_bounded=True)
    d.update(kw);return Observation(**d)

class StopTest(unittest.TestCase):
    def active(self):
        s=Supervisor();s.step(good(0,explicit_reset=True));s.step(good(1));s.step(good(2,run_request=True))
        self.assertTrue(s.step(good(3,aux_closed=True,load_bus_discharged=False)).motion_permit)
        return s
    def test_unknown_never_allows(self):
        c=Supervisor().step(Observation(1,1));self.assertFalse(c.motion_permit);self.assertFalse(c.coil_request)
    def test_startup_never_auto_starts(self):
        s=Supervisor();self.assertFalse(s.step(good(0,run_request=True)).coil_request)
    def test_reset_and_run_same_event_rejected(self):
        s=Supervisor();self.assertFalse(s.step(good(0,explicit_reset=True,run_request=True)).coil_request)
    def test_requires_new_run_edge(self):
        s=Supervisor();s.step(good(0,run_request=True));self.assertFalse(s.step(good(1,explicit_reset=True,run_request=True)).coil_request)
    def test_reset_without_support_rejected(self):
        c=Supervisor().step(good(0,explicit_reset=True,support_engaged=None));self.assertEqual(c.state,State.INHIBITED)
    def test_reset_aux_weld_disagreement_rejected(self):
        self.assertNotEqual(Supervisor().step(good(0,explicit_reset=True,aux_closed=True)).state,State.READY)
    def test_reset_bus_live_rejected(self):
        self.assertNotEqual(Supervisor().step(good(0,explicit_reset=True,load_bus_discharged=False)).state,State.READY)
    def test_fault_inputs_and_unknown_each_trip(self):
        for key in ('independent_stop_chain_ok','bus_supply_ok','converter_thermal_ok','brake_thermal_ok','regen_path_available','return_path_ok','can_heartbeat_ok'):
            for val in (False,None):
                with self.subTest(key=key,value=val):
                    c=self.active().step(good(4,**{key:val}));self.assertFalse(c.motion_permit);self.assertFalse(c.coil_request)
    def test_replay_trip(self):
        self.assertFalse(self.active().step(good(3)).coil_request)
    def test_binding_loss_trip(self):
        self.assertFalse(self.active().step(good(4,binding_verified=False)).coil_request)
    def test_no_auto_restart_after_fault_clear(self):
        s=self.active();s.step(good(4,can_heartbeat_ok=False));self.assertEqual(s.step(good(5,run_request=True)).state,State.FAULT)
    def test_normal_stop_preserves_supply_until_supported(self):
        s=self.active();c=s.step(good(4,stop_request=True,support_engaged=False,residual_energy_bounded=False));self.assertTrue(c.coil_request);self.assertFalse(c.motion_permit)
        c=s.step(good(5,support_engaged=True,residual_energy_bounded=None));self.assertEqual(c.state,State.DECELERATING)
        c=s.step(good(6));self.assertEqual(c.state,State.SUPPORTED);self.assertTrue(c.coil_request)
        c=s.step(good(7));self.assertEqual(c.state,State.CONTACT_OPEN);self.assertFalse(c.coil_request)
    def test_power_request_without_feedback_not_motion(self):
        s=Supervisor();s.step(good(0,explicit_reset=True));s.step(good(1));c=s.step(good(2,run_request=True,aux_closed=None));self.assertTrue(c.coil_request);self.assertFalse(c.motion_permit)

if __name__=='__main__': unittest.main()
