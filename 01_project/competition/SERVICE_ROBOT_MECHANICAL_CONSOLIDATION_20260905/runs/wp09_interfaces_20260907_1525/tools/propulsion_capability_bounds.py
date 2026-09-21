"""Necessary impulse limits; fail-closed wrench evaluation when nozzle ICD is absent."""
from pathlib import Path
import json,math,hashlib
R=Path(__file__).resolve().parents[1]
contract=dict(part_number='X14029003-1',document_revision='6/15',total_impulse_Ns=44.,thrust_per_jet_N=.010,jet_count=5,
              jet_positions_S_m=[None]*5,jet_directions_S_unit=[None]*5,spacecraft_CM_S_m=None,
              pulse_minimum_s=None,plume_half_angle_deg=None,actuator_delay_s=None,selected_flight_hardware=False)
def allocation_status(c):
    missing=[k for k in ['jet_positions_S_m','jet_directions_S_unit','spacecraft_CM_S_m','pulse_minimum_s','plume_half_angle_deg','actuator_delay_s'] if c[k] is None or (isinstance(c[k],list) and any(v is None for v in c[k]))]
    if missing:return dict(status='UNKNOWN_NO_CONSTRAINED_WRENCH_EVALUATION',missing=missing,rank=None,attainable_force_torque=None)
    raise RuntimeError('Complete future inputs require an independently reviewed constrained actuator solver; not implemented by this scalar screen')
H=3.65
cases=[]
for r in (.05,.1,.2,.3):
    # Optimistic all-thrust tangential upper bound, not a valid actual nozzle allocation.
    tau=r*contract['jet_count']*contract['thrust_per_jet_N'];angular_capacity=r*contract['total_impulse_Ns']
    cases.append(dict(assumed_effective_lever_arm_m=r,ideal_angular_impulse_upper_Nms=angular_capacity,
      ideal_all_jets_torque_upper_Nm=tau,ideal_time_lower_s=H/tau,necessary_total_impulse_test=angular_capacity>=H,
      necessary_test_not_sufficient=True,assumed_same_effective_arm_for_all_impulse=True))
result=dict(status='REFERENCE_SCALAR_NECESSARY_BOUNDS_ONLY',reference_H_Nms=H,reference_H_source='Project AGENTS.md sim_08 historical debris case; not a new simulation or current flight requirement',
  minimum_ideal_effective_arm_m=H/44.,cases=cases,wrench_allocation=allocation_status(contract),
  mission_desaturation_pass=None,plume_pass=None,new_simulation_executed=False,scientific_gates_modified=False,
  mass_or_inertia_updated=False,notes=['44 Ns belongs only to the bound old reference; do not combine with new 82 Ns/25 mN model.',
    'If r*44 < 3.65 then this idealized necessary condition fails; passing it does not establish actual torque direction, translation cancellation, plume safety, or mission duration.'])
assert abs(result['minimum_ideal_effective_arm_m']-0.08295454545454545)<1e-12
assert result['cases'][0]['necessary_total_impulse_test'] is False
for name,obj in [('PROPULSION_CAPABILITY_INPUTS.json',contract),('PROPULSION_CAPABILITY_BOUNDS.json',result)]:
    (R/'results'/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
print(result['status'])
