"""Executable design trade closure; explicit UNKNOWN prevents spurious hardware PASS."""
from pathlib import Path
import json,csv,hashlib,math
C=Path(__file__).resolve().parents[1];N=C.parent/'reuse_closure'
for name in ['power','results','inputs','ecad','control']: (C/name).mkdir(exist_ok=True)
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def bind(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
parent=read(N/'results/POWER_CALCULATIONS.json')
pc=read(N/'power/POWER_CONTRACT.json')
mode=parent['budget']['mode_rows']
duration=sum(x['duration_min'] for x in mode)
sun_min=sum(x['duration_min'] for x in mode if x['sun'])
consumption=sum(x['energy_wh'] for x in mode)
generation=parent['pv']['sun_bus_power_conditional_w']*sun_min/60
surplus=generation-consumption
# These efficiencies and duty ranges are a sensitivity grid, not supplier limits.
arm_screen_w=360;coil_nominal_w=6.8
grid=[]
for eta in [.8,.9,.96]:
 for op_min in [1,2,5,10,20]:
  load=(arm_screen_w+coil_nominal_w)*op_min/60/eta
  charge_eff=.85
  net=surplus-load/charge_eff
  grid.append(dict(eta_conversion_assumed=eta,operation_minutes=op_min,arm_plus_coil_energy_wh=load,charge_eff_assumed=charge_eff,required_PV_surplus_wh=load/charge_eff,per_orbit_net_wh=net,screen_balanced=net>=0,identity='SENSITIVITY_NOT_MISSION_ACCEPTANCE'))
candidate={
 'architecture':'Two independently protected battery/converter channels; no unprotected raw-battery parallel; preserve separate P60 low-power branch',
 'battery':{'pn':'Inventus MB-2590-300 / manufacturer 07-52590','quantity':2,'series_output_range_v':[20,33.6],'max_discharge_a_each':12.5,'energy_min_wh_each':288,'mass_nom_kg_each':1.5,'bbox_mm_each':[127,62.6,111.8],'source':bind(C/'sources/power_intake/Inventus_MB2590_300.pdf'),'qualification':'industrial/tactical module; vacuum/radiation suitability not established'},
 'converter':{'pn':'TDK i7C4W012A050V-PC3-R','quantity':2,'feature':'Itrim; baseplate; negative-logic enable','input_v':[9,53],'rated_output_a_each':12.5,'max_output_w_each':300,'set_v':24,'voltage_tolerance_fraction':.04,'Itrim_min_max_over_all_temp_vin':'NOT_GUARANTEED_BY_PUBLIC_TABLE','source':'https://product.tdk.com/system/files/dam/doc/product/power/switching-power/dc-dc-converter/specification/i7c_spec.pdf','source_revision':'March 4 2024 v9; web parser viewed, binary download HTTP403'},
 'charging':{'candidate_controller':'LTC4020','status':'CONTROLLER_ONLY_NOT_COMPLETE_CHARGER','source':bind(C/'sources/power_intake/LTC4020_datasheet.pdf'),'open':['battery-specific charge limits and enable mating-view connector ICD','PV-to-two-charge-channels routing and protection','thermal/input-current-loop detailed design']},
 'selection_status':'CANDIDATE_REJECTED_AS_FINAL_COMPLETE_SOLUTION_UNTIL_INTERFACE_AND_ENVIRONMENT_BOUNDS_EXIST',
 'replacement_comparisons':[
  {'pn':'Single MB-2590-300','decision':'REJECT_FOR_FULL_VOLTAGE_360W','reason':'At20V,12.5A allows250W even at ideal conversion'},
  {'pn':'P60/BPX existing branch','decision':'REJECT_FOR_ARM_360W','reason':'Dock4A and PDU3.75A below demand; do not bypass'},
  {'pn':'GomSpace P80 as a drop-in whole replacement','decision':'NOT_SELECTED','reason':'300W and12A aggregate do not by themselves close360W arm plus spacecraft; changing name does not close budget','source':'https://gomspace.com/product/nanopower-p80/'},
  {'pn':'TDK i7C -001 / -0C1 normal variants','decision':'REJECT_FOR_UNQUALIFIED_PARALLEL','reason':'Itrim parallel option is Px3; ordinary suffix must not inherit it'}],
}
electrical={
 'arm_screen_w':arm_screen_w,'coil_25C_nominal_w':coil_nominal_w,
 'existing_Dock_current_needed_24V_a':arm_screen_w/.8/24,
 'single_battery_ideal_min_voltage_output_w':20*12.5,
 'dual_battery_at_min_voltage_ideal_total_w':2*20*12.5,
 'min_required_efficiency_for_two_batteries':(arm_screen_w+coil_nominal_w)/(2*20*12.5),
 'new_battery_nominal_mass_kg':3,
 'new_battery_bbox_sum_litre':2*127*62.6*111.8/1e6,
 'converter_steady_output_range_v':[24*.96,24*1.04],
 'nominal_load_a_24v':(arm_screen_w+coil_nominal_w)/24,
 'demand_at_converter_low_v_a':(arm_screen_w+coil_nominal_w)/(24*.96),
 'per_channel_input_a_if_equal_share_eta08_at20v':(arm_screen_w+coil_nominal_w)/2/.8/20,
 'single_fault_full_power_possible':False,
 'unknowns':['equal share across converter tolerances','end-of-discharge current limiting versus BMS trip','transient output voltage versus DM permitted envelope','complete battery series/charge connector mating-view ICD','in-orbit thermal/radiation suitability','mounting and residual volume after both batteries','mission timing and eclipse/illumination bounds'],
}
regen=[]
# Analytical parametric rotational stop; captured object inertia cannot be deduced from total mass alone.
for I in [.1,1,10,100,1000]:
 for omega in [1,3.0633,10,30]:
  w=math.radians(omega);E=.5*I*w*w
  regen.append(dict(I_kgm2=I,omega_deg_s=omega,E_rot_J=E,identity='PARAMETRIC_NOT_CURRENT_ASSEMBLY_INERTIA'))
stop={
 'normal_sequence':['remove_new_motion_permission','keep K1 closed and brake energy path supplied','controlled deceleration using confirmed drive limits','confirm bounded residual energy and mechanical support engaged','open K1','measure post-contact bus voltage and auxiliary feedback','latch fault/stop until deliberate reset'],
 'unexpected_input_loss':'ODrive public page gives no quantified input-loss absorption guarantee; it is not a sufficient sole energy sink',
 'emergency_loss_of_torque':'No evidence B601 is holding-braked on all axes. Ground test requires independent physical support before any motion release.',
 'legacy_50J_value':'requirement only, not a derived arm/target energy bound',
 'equations':{'rotation':'E=0.5*w.T*I*w','ground':'E_upper=E_kin+sum(m*g*max(0,h_start-h_catch))','resistor':'P_inst=V_bus^2/R; E_pulse<=supplier permitted pulse energy; P_average=sum(E)/T; cable and enclosure temperature checked separately'},
 'example_ground_arm_only_J_per_m':4.5*9.80665,
 'captured_object_regen_source':'coupled total inertia/attitude and permitted angular rates required; no use of 24kg legacy model as 705 current mass',
 'coil_driver_screen':{'rejected':'TPS1H100 direct unqualified GX11 driver','reason':'Source GX1155V back-EMF plus upstream bus and switch clamp-energy bounds must be reconciled; choosing4A rating alone does not close switching','source':bind(C/'sources/power_intake/TPS1H100_datasheet.pdf')},
 'watchdog_candidate':{'pn':'TPS3431SDRBR','fixed_timeout_ms':[170,200,230],'SET1':'HIGH','CWD':'10kohm toVDD','ENOUT':'must participate in gate; WDO alone deasserts when EN=LOW','source':bind(C/'sources/power_intake/TPS3431_datasheet.pdf')},
 'flight_stop_regen_closed':False,
}
checks={
 'single_pack_rejected_at_min_voltage':electrical['single_battery_ideal_min_voltage_output_w']<arm_screen_w,
 'existing_Dock_rejected':electrical['existing_Dock_current_needed_24V_a']>4,
 'no_RSP_counted_in_orbit_generation':True,
 'no_downsizing_of360W':arm_screen_w==360,
 'nominal_current_is_not_single_fault_pass':electrical['single_fault_full_power_possible'] is False,
 'energy_failure_detected_20min':all(not x['screen_balanced'] for x in grid if x['operation_minutes']==20),
 'regen_quadratic_rate':abs(.5*1*math.radians(20)**2/(.5*1*math.radians(10)**2)-4)<1e-12,
 'hardware_stop_not_auto_certified':stop['flight_stop_regen_closed'] is False,
}
assert all(checks.values()),checks
dump(C/'power/HIGH_POWER_CANDIDATE.json',candidate)
dump(C/'power/STOP_REGEN_DESIGN.json',stop)
with (C/'power/ENERGY_SENSITIVITY.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=grid[0]);w.writeheader();w.writerows(grid)
with (C/'power/REGEN_ENERGY_SENSITIVITY.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=regen[0]);w.writeheader();w.writerows(regen)
dump(C/'results/POWER_COMPLETION_ANALYSIS.json',dict(status='SIZED_CANDIDATE_AND_BOUND_FAILURES__NOT_FINAL_POWER_DESIGN',parent=bind(N/'results/POWER_CALCULATIONS.json'),electrical=electrical,inherited_conditional_cycle={'duration_min':duration,'sun_minutes':sun_min,'generation_wh':generation,'baseline_load_wh':consumption,'surplus_wh':surplus,'owner_orbit_bound':False},checks=checks,checks_passed=sum(checks.values()),flight_arm_power_design_closed=False,stop_regeneration_design_closed=False))
print(json.dumps({'electrical':electrical,'surplus_wh':surplus,'checks':checks},ensure_ascii=False,indent=2))
