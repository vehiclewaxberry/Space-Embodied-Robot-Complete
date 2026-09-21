"""Build C203 footprint and check selected passives against the native circuit."""
from pathlib import Path
import csv,hashlib,json,math,re,xml.etree.ElementTree as ET
from input_passive_definition import PASSIVES
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
f,c,aux=PASSIVES['F201'],PASSIVES['C203'],PASSIVES['F202']
from input_passive_footprint import build_footprint
name=build_footprint()
parts=read('power/POWER_LOOP_PARTS.json')
xml=ET.parse(A/'ecad/wp10_system.xml').getroot()
comps={q.get('ref'):q for q in xml.findall('./components/comp')}
nets={(q.get('ref'),q.get('pin')):n.get('name') for n in xml.findall('./nets/net') for q in n.findall('node')}
checks=[]
def ck(name,flag,**kw):checks.append(dict(name=name,passed=bool(flag),**kw))
def same(a,b):return nets[tuple(a.split('.'))]==nets[tuple(b.split('.'))]
for ref in ['F201','F202','C203']:
 ck(ref+'_native_value_matches_selection',comps[ref].findtext('value')==PASSIVES[ref]['MPN'])
ck('C203_project_polarity_not_generic_AB',parts['C203']['pins']=={'1':'PLUS','2':'MINUS'})
ck('C203_plus_at_PRECHARGED',same('C203.1','U203.1') and same('C203.1','Q201.3'))
ck('C203_minus_at_input_return_not_arm_return',same('C203.2','J200.2') and not same('C203.2','J203.2'))
ck('C203_native_footprint_property',comps['C203'].findtext('footprint')==c['footprint'])
ck('F201_OEM_footprint_bound_to_native',comps['F201'].findtext('footprint')==f['footprint'] and f['footprint_bound'])
ck('F201_footprint_OEM_revision_bytes',sha(f['footprint_source_file'])==f['footprint_source_sha256'])
fpt=(A/('ecad/WP10_PASSIVES.pretty/'+f['footprint'].split(':')[1]+'.kicad_mod')).read_text()
fpads=re.findall(r'\(pad "([12])" smd rect \(at ([-\d.]+) ([-\d.]+)\) \(size ([-\d.]+) ([-\d.]+)\)',fpt)
pp={r[0]:[float(v) for v in r[1:]] for r in fpads}
ck('F201_two_exact_pad_sizes',len(pp)==2 and all(v[1]==0 and v[2:]==[3.25,3.43] for v in pp.values()))
ck('F201_outer_span_not_misread_as_pitch',len(pp)==2 and abs(pp['2'][0]+pp['2'][2]/2-(pp['1'][0]-pp['1'][2]/2)-12.6)<1e-12 and abs(pp['2'][0]-pp['1'][0]-9.35)<1e-12)
bom=list(csv.DictReader((A/'power/SELECTED_BOM.csv').open(encoding='utf-8-sig')))
for ref in ['F201','F202','C203']:
 rows=[r for r in bom if r['role'].startswith(ref+':')]
 ck(ref+'_single_current_BOM_row',len(rows)==1 and rows[0]['MPN']==PASSIVES[ref]['MPN'])
p=read('power/POWER_LOOP_CALCULATIONS.json'); sb=read('power/SHARED_BATTERY_PATH_CALCULATIONS.json')
cmin=c['C_nominal_F']*(1-c['tolerance_fraction']);cmax=c['C_nominal_F']*(1+c['tolerance_fraction'])
esr120=c['dissipation_factor_max']/(2*math.pi*120*cmin)
endurance_esr120=c['dissipation_factor_max']*c['endurance_DF_ratio_max']/(2*math.pi*120*cmin*(1-c['endurance_C_change_fraction']))
ck('Cmax_bound_to_actual_precharge_source',abs(p['precharge']['Cmax_F']-cmax)<1e-15)
ck('initial_120Hz_DF_derived_ESR_screen_below_OEM_0p12',esr120<.12)
ck('endurance_120Hz_worst_bound_does_not_inherit_initial_ESR',endurance_esr120>.12)
ck('all192_scenarios_include_distinct_leak',len(sb['cases'])==192 and all(q['inputs']['main_leak_a']==c['max_leakage_A'] for q in sb['cases']))
ck('cold_open_source_does_not_power_C203',all(q['cold']['main_leak_A']==0 and q['cold']['main_input_V'] is None for q in sb['cases']))
ck('fuse_typical_R_inside_pre_fuse_allocation_not_added_twice',all(q['inputs']['main_pre_r']>=f['typical_cold_R_ohm'] for q in sb['cases']))
ck('F202_between_protected_split_and_independent_THN',same('F202.1','F201.1') and same('F202.2','U202.1') and not same('F202.2','Q201.3'))
ck('F202_OEM_revision_bytes',sha(aux['source_file'])==aux['source_sha256'])
ck('F202_matches_THN_recommended_fuse_current',aux['rated_A']==aux['THN_recommendation']['slow_blow_A'] and sha(aux['THN_recommendation']['document'])==aux['THN_recommendation']['document_sha256'])
ck('F202_total_branch_includes_cold_R_once',all(q['inputs']['aux_r']>=aux['typical_cold_R_ohm'] for q in sb['cases']))
ck('F202_cold_R_not_full_current_hot_R_guarantee',aux['typical_drop_V_at_rated_current']*aux['rated_A']>aux['rated_A']**2*aux['typical_cold_R_ohm'])
ck('F202_unknown_formed_pitch_and_inrush_remain_open',aux['formed_lead_PCB_pitch_mm'] is None and aux['THN_input_inrush_waveform'] is None and not aux['protection_coordination_verified'])
# Ideal diagnostic only: CHB/bias/leakage/source impedance omitted.
tr=[]
for v in [25.2,29.4]:
 for pp in p['precharge']['power_limit_sensitivity_W']:
  for il in p['current_limit_screen_A']:
   sw=pp/il
   analytic=cmax*(v*v/(2*pp)+pp/(2*il*il)) if v>sw else cmax*v/il
   i2t=cmax*pp*(math.log(v/sw)+1) if v>sw else cmax*il*v
   n=10000;dv=v/n;amps=[min(il,pp/(v-(j+.5)*dv)) for j in range(n)]
   tn=sum(cmax*dv/x for x in amps);jn=sum(cmax*dv*x for x in amps)
   ck('ideal_precharge_quadrature_'+str(len(tr)),abs(tn-analytic)<1e-8 and abs(jn-i2t)<1e-6)
   tr.append(dict(V=v,limit_W=pp,current_limit_A=il,ideal_charge_s=analytic,
       ideal_FET_and_fuse_I2t_A2s=i2t,relative_to_fuse_10In_typical_melting_I2t=i2t/f['typical_melting_I2t_A2s'],
       pulse_survival_pass=None,SOA_and_timer_actual_trajectory_verified=False))
ck('LM5069_limit_does_not_guarantee_backup_fuse_open',max(p['current_limit_screen_A'])<f['rated_A'])
ck('test_LoverR_counterexample_not_approved',1e-6/.1>f['interrupt_test_L_over_R_s_lt'])
heat=[]
for q in sb['cases']:
 for state in ['run','cold']:
  r=q[state]
  if not r['equilibrium_found']:continue
  amps=r['main_A']+r['controller_A'];fuse_w=amps*amps*f['typical_cold_R_ohm']
  before=r['heat_W']['main_before_sense']
  aux_fuse_w=r['aux_A']**2*aux['typical_cold_R_ohm']
  ledger={k:v for k,v in r['heat_W'].items() if k not in ['main_before_sense','auxiliary_branch']}
  ledger.update(F201_typical_cold_R_transfer=fuse_w,main_before_sense_excluding_F201=before-fuse_w)
  ledger.update(F202_typical_cold_R_transfer=aux_fuse_w,auxiliary_branch_excluding_F202=r['heat_W']['auxiliary_branch']-aux_fuse_w)
  ledger.update(r['conversion_and_bias_heat_W'])
  assert min(ledger.values())>=0 and abs(sum(ledger.values())-(r['input_power_W']-r['delivered_output_allocation_W']))<1e-7
  for node,w in ledger.items():heat.append(dict(case_id=q['id'],state=state,node=node,heat_W=w,
      value_basis='F201 1.7mOhm and F202 18mOhm typical cold values transferred within original branch allocations; not hot resistance or measured temperature',
      mechanical_sink_node='',thermal_contact_R_K_W='',qualification='UNBOUND'))
with (A/'thermal/INPUT_PASSIVE_HEAT_LOADS.csv').open('w',encoding='utf-8-sig',newline='') as g:
 w=csv.DictWriter(g,fieldnames=list(heat[0]));w.writeheader();w.writerows(heat)
ck('thermal_split_closes_all_RUN_COLD_cases',len(heat)==4032)
result=dict(schema='WP10_INPUT_PASSIVES_V15',check_count=len(checks),checks=checks,passed=all(q['passed'] for q in checks),
 sources={p:sha(p) for p in c['source_files']},
 bindings={p:sha(p) for p in ['tools/input_passive_definition.py','tools/check_input_passives.py','power/INPUT_PASSIVE_SELECTION.json','power/SHARED_BATTERY_PATH_CALCULATIONS.json','ecad/wp10_system.xml','power/SELECTED_BOM.csv','thermal/INPUT_PASSIVE_HEAT_LOADS.csv','ecad/WP10_PASSIVES.pretty/'+name+'.kicad_mod',f['footprint_source_file'],'ecad/WP10_PASSIVES.pretty/'+f['footprint'].split(':')[1]+'.kicad_mod']},
 electrical=dict(Cmin_F=cmin,Cmax_F=cmax,energy_J_at29p4V_max_C=.5*cmax*29.4**2,
  initial_ESR120Hz_upper_from_DF_ohm=esr120,endurance_ESR120Hz_upper_from_DF_ohm=endurance_esr120,
  ESR_30kHz_upper_from_Z_ohm=c['impedance_max_ohm'],
  ESR_bound_scope='DF/C-derived series ESR at20C120Hz; Z-derived ESR at20C30kHz only. No broadband/full-temperature guarantee.',
  ripple_nominal_frequency_limits_Arms=[a*c['ripple_rms_A'] for a in c['ripple_frequency_multiplier']],
  actual_ripple_spectrum=None,leakage_environment_guaranteed=False,full_life_ESR_requirement_verified=False),
 precharge_ideal_diagnostics=tr,
 fuse_LoverR_counterexample=dict(assumed_L_H=1e-6,assumed_R_ohm=.1,tau_s=1e-5,OEM_test_tau_lt_s=1e-6,qualified=False),
 geometry=dict(C203_footprint_generated=True,OEM_BRep_acquired=False,mechanical_source_plan='mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json',
  seating_face_to_max_vent_keepout_top_mm=55,below_seating_max_lead_projection_mm=4.5,
  C203_assembly_transform=read('mechanical/INPUT_CAP_MOUNT_DESIGN.json')['cap_local_to_S'],
  C203_installation_scope='Nominal installed candidate; see separate CAD/ECAD interface and exact geometry check; retention and thermal qualification OPEN',
  F201_and_F202_assembly_transforms=None,PCB_layout_routed=False),
 scope='SELECTED_CANDIDATES_WITH_NATIVE_PIN_AND_MODEL_BINDING; not physical or flight qualification',
 physical_tests_executed=False,engineering_prototype_design_complete=False,power_on_release=False)
for q in [aux['source_file'],aux['THN_recommendation']['document'],'tools/input_passive_footprint.py','mechanical/INPUT_CAP_MOUNT_DESIGN.json','mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json']:
 result['bindings'][q]=sha(q)
dump('power/INPUT_PASSIVE_CALCULATIONS.json',result)
print(json.dumps(dict(checks=len(checks),passed=result['passed'],ESR_initial=esr120,ESR_after_endurance=endurance_esr120,heat_rows=len(heat))))
assert result['passed'],[q for q in checks if not q['passed']]

