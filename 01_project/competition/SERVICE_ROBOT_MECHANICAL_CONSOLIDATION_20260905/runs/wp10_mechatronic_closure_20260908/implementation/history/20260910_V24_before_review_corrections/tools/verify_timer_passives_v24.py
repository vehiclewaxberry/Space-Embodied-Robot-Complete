"""Selected timer/passive sensitivities. No energization or release credit."""
from pathlib import Path
import csv,hashlib,itertools,json,math,xml.etree.ElementTree as ET
from timer_passive_definition_v24 import TIMING_PASSIVES as T
from erc_source_contract import parse,children,val
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2),encoding='utf-8')
checks=[]
def ck(name,passed,**kw):checks.append(dict(name=name,passed=bool(passed),**kw))
paths=['tools/timer_passive_definition_v24.py','tools/verify_timer_passives_v24.py',
 'power/TIMER_PASSIVE_SELECTION_V24.json','power/POWER_LOOP_PARTS.json','power/SELECTED_BOM.csv',
 'ecad/wp10_system.xml','results/TIMER_PASSIVES_NATIVE_V24.json',
 'sources/wima_mkp2_v24.pdf','sources/tnpw_e3_20260410_v24.pdf','sources/lm5069_rev_g.pdf',
 'ecad/WP10_TIMING.pretty/C201_MKP2_1uF_P5_Slot2.kicad_mod',
 'mechanical/c201_mkp2_body_v24.step.py','mechanical/c201_mkp2_body_v24.step']
hashes={p:sha(p) for p in paths}
native=ET.parse(A/'ecad/wp10_system.xml').getroot()
cs={c.get('ref'):c for c in native.findall('./components/comp')}
for ref,v in T.items():
 ck('native_'+ref,cs[ref].findtext('value')==v['MPN'] and cs[ref].findtext('footprint')==v['footprint'])
 ck('OEM_pdf_'+ref,sha(v['source_file'])==v['source_sha256'])
 if ref.startswith('R'):
  token=v['MPN'][8:12];a,b=token.split('K');ohm=float(a+'.'+b)*1000
  ck('part_code_'+ref,abs(ohm-v['resistance_ohm'])<1e-8 and v['MPN'].endswith('BEEA'))
c=T['C201'];cn=c['C_nominal_F'];tol=c['initial_tolerance_fraction'];ir=c['insulation_resistance_ohm_lower']
def charge(C,V,I,R):
 assert I*R>V
 return -R*C*math.log1p(-V/(I*R))
initial_fault=[cn*(1-tol)*3.76/120e-6,charge(cn*(1+tol),4.16,51e-6,ir)]
initial_insertion=[cn*(1-tol)*3.76/8e-6,charge(cn*(1+tol),4.16,3e-6,ir)]
ck('finite_IR_charge_approaches_zero_leak',abs(charge(cn,4,85e-6,1e16)-cn*4/85e-6)<1e-9)
ck('selected_initial_band_within_requirement',c['effective_C_requirement_F'][0]<=cn*(1-tol) and cn*(1+tol)<=c['effective_C_requirement_F'][1])
# Divider power under explicit normal 29.4V, 100K/TCR and 1uA bias sensitivity.
tolR=.001+25e-6*100;resistor=[]
for up,low in [('R203','R204'),('R205','R206')]:
 ru=T[up]['resistance_ohm'];rl=T[low]['resistance_ohm'];samples=[]
 for tu,tl,bias in itertools.product([-tolR,tolR],[-tolR,tolR],[-1e-6,1e-6]):
  u=ru*(1+tu);l=rl*(1+tl);vm=(29.4/u-bias)/(1/u+1/l)
  samples.append(((29.4-vm)**2/u,vm*vm/l))
 for idx,ref in enumerate([up,low]):
  pm=max(q[idx] for q in samples)
  resistor.append(dict(ref=ref,worst_sampled_normal_W=pm,general_P70_W=.110,
   remaining_at70C_W=.110-pm,whole_thermal_verified=False))
  ck('normal_divider_power_'+ref,pm<.110)
resistor.append(dict(ref='R207',typical20uA_current_power_W=(20e-6)**2*30100,
 maximum_pin_current_guaranteed=False,maximum_resistor_power_verified_W=None))
fp=parse((A/'ecad/WP10_TIMING.pretty/C201_MKP2_1uF_P5_Slot2.kicad_mod').read_text())
pads={val(p[1]):p for p in children(fp,'pad')}
ck('slot_geometry_in_actual_footprint',any(p[0]=='drill' and p[1]=='oval' and abs(float(p[2])-2)<1e-9 and abs(float(p[3])-.9)<1e-9 for p in pads['2'] if isinstance(p,list)))
ck('only_one_C201_3D_model',len(children(fp,'model'))==1 and 'c201_mkp2_body_v24.step' in children(fp,'model')[0][1])
# Declared tolerances: slot length1.95min, lead diameter0.55max, two position errors0.05 each.
slot_margin=(2-.05-.55)/2-(.5+.05+.05)
round_margin=(.9-.05-.55)/2
ck('allocated_pitch_fits_slot',slot_margin>0,margin_mm=slot_margin)
ck('allocated_first_lead_fits_round_hole',round_margin>0,radial_margin_mm=round_margin)
out=dict(schema='WP10_TIMER_PASSIVE_SCREEN_V24',passed=all(q['passed'] for q in checks),
 source_bindings=hashes,checks=checks,
 selected_C201=dict(initial_C_range_F=[cn*(1-tol),cn*(1+tol)],
  initial_fault_threshold_s=initial_fault,initial_insertion_threshold_s=initial_insertion,
  TIMER4p16V_ohmic_leak_A=4.16/ir,IR_transfer_is_conditional=True,
  effective_C_requirement_F=c['effective_C_requirement_F'],
  permitted_additional_fraction_from_initial_edges=[.9/.95-1,1.1/1.05-1],
  board_leakage_unbound=True,full_temperature_C_and_leakage_verified=False,
  DC_allowed_at100C_V=63*(1-.0135*15),full_timer_gate_off_delay_verified=False),
 R207=dict(nominal_ohm=30100,initial_tolerance_fraction=.001,TCR_per_K=25e-6,
  deltaT_project_K=100,combined_initial_and_temperature_fraction=tolR,
  lifetime_drift_included=False,thermal_film_boundary_verified=False),
 normal_divider_power_sensitivity=resistor,slot_tolerance_allocation=dict(
  pitch_exit_OEM_mm=.5,PCB_hole_position_each_mm=.05,drill_size_mm=.05,
  lead_diameter_max_project_mm=.55,slot_pitch_margin_mm=slot_margin,
  lead_diameter_tolerance_OEM_verified=False,PCB_fabricator_tolerances_bound=False),
 whole_design_complete=False,manufacturing_release=False,physical_test_executed=False)
dump('power/TIMER_PASSIVE_CALCULATIONS_V24.json',out)
print(json.dumps(dict(passed=out['passed'],checks=len(checks),initial_fault_ms=[v*1000 for v in initial_fault],
 initial_insertion_ms=[v*1000 for v in initial_insertion],slot_margin_mm=slot_margin)))
assert out['passed'],[q for q in checks if not q['passed']]
