"""Bounded offline source extraction and engineering accounting; standard library only.
No serial/socket/CAN, historical simulation, CAD, or pressure-system execution.
"""
from pathlib import Path
import csv, hashlib, json, math, re, sys
sys.dont_write_bytecode = True
N=Path(__file__).resolve().parents[1]; R=N.parent; S=N/'sources/atmos_px4'; P=N/'propulsion'; O=N/'results'
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(262144),b''):h.update(chunk)
 return h.hexdigest()
def save(p,x): Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def mv(A,v):return [sum(x*y for x,y in zip(row,v)) for row in A]
def transpose(a):return list(map(list,zip(*a)))
def rank(A,tol=1e-10):
 A=[r[:] for r in A];n=0
 for col in range(len(A[0])):
  idx=max(range(n,len(A)),key=lambda k:abs(A[k][col]),default=None)
  if idx is None or abs(A[idx][col])<tol:continue
  A[n],A[idx]=A[idx],A[n];scale=A[n][col];A[n]=[x/scale for x in A[n]]
  for k in range(len(A)):
   if k!=n:
    scale=A[k][col];A[k]=[x-scale*y for x,y in zip(A[k],A[n])]
  n+=1
  if n==len(A):break
 return n
checks=[]
def check(name,condition,details=None):
 checks.append({'id':name,'pass':bool(condition),'details':details});assert condition,name

lock=read(S/'SOURCE_LOCK.json'); bindings={x['local_path']:x['sha256'] for x in lock['files']}
legacy=read(R/'functional_closure/inputs/PROPULSION_SCREEN_INPUTS.json')
for x in legacy['source_bindings'].values():bindings[x['path']]=x['sha256']
m=read(R/'results/INTEGRATION_MANIFEST_V6.json');native=read(R/'results/NATIVE_BINDING_MANIFEST.json');em=read(R/'results/EMISSION_V6.json')
param=Path(r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'); rho=read(param)['candidate_aluminum_density_kg_mm3']
for p in [R/'results/INTEGRATION_MANIFEST_V6.json',R/'results/NATIVE_BINDING_MANIFEST.json',R/'results/EMISSION_V6.json',param,P/'vendor/Seeed_B601_DM_Product_Sheet.pdf']:
 bindings[str(p)]=sha(p)
for powerfile in ['P60_DOCK_3_1.pdf','ACU200_DS1014406_2_3.pdf','P60_PDU200_2_6.pdf','A3200_DS1006901_2_0.pdf','BPX100WH_DS1076870_1_1_0.pdf']:
 p=N/'sources/power'/powerfile;bindings[str(p)]=sha(p)
check('source_lock_before',all(sha(p)==h for p,h in bindings.items()))

# Read airframe as data; never source/execute the upstream shell script.
air=S/'px4/ROMFS/px4fmu_common/init.d/airframes/70000_atmos'; text=air.read_text();params={k:float(v) for k,v in re.findall(r'^param set(?:-default)? (\S+) ([-+\d.eE]+)$',text,re.M)}
outputs={int(i):desc for i,desc in re.findall(r'^# @output Motor(\d+) (.+)$',text,re.M)}
rotors=[]
for i in range(int(params['CA_ROTOR_COUNT'])):
 r=[params[f'CA_ROTOR{i}_P{a}'] for a in 'XYZ'];d=[params[f'CA_ROTOR{i}_A{a}'] for a in 'XYZ'];norm=math.sqrt(sum(x*x for x in d));d=[x/norm for x in d]
 rotors.append({'motor_output':i+1,'parameter_index':i,'description':outputs[i+1],'position_body_relative_CG_m':r,'force_axis_body_unit':d,'exhaust_axis_body_unit':[-x for x in d],'CT_config':params[f'CA_ROTOR{i}_CT'],'KM_fresh_default':0.05,'KM_explicit_in_airframe':f'CA_ROTOR{i}_KM' in params,'pwm_aux_function':int(params[f'PWM_AUX_FUNC{i+1}']),'position_basis':'LOCKED_70000_AIRFRAME_PARAMETER_NOT_AS_BUILT_MEASUREMENT'})
mod=(S/'px4/src/modules/control_allocator/module.yaml').read_text();kmblock=mod[mod.index('CA_ROTOR${i}_KM:'):mod.index('CA_ROTOR${i}_TILT:')]
check('KM_default_source_0_05','default: 0.05' in kmblock and not any(x['KM_explicit_in_airframe'] for x in rotors))
cpp=(S/'px4/src/modules/control_allocator/VehicleActuatorEffectiveness/ActuatorEffectivenessRotors.cpp').read_text();check('source_cross_product_and_reaction_term_present','ct * position.cross(axis) - ct * km * axis' in cpp)
B_geom=transpose([r['force_axis_body_unit']+cross(r['position_body_relative_CG_m'],r['force_axis_body_unit']) for r in rotors])
# PX4 rows are [moment, thrust], distinct from project [force, moment].
B_source=transpose([[r['CT_config']*(v-.05*d) for v,d in zip(cross(r['position_body_relative_CG_m'],r['force_axis_body_unit']),r['force_axis_body_unit'])]+[r['CT_config']*d for d in r['force_axis_body_unit']] for r in rotors])
B_noKM=transpose([[r['CT_config']*v for v in cross(r['position_body_relative_CG_m'],r['force_axis_body_unit'])]+[r['CT_config']*d for d in r['force_axis_body_unit']] for r in rotors])
check('eight_real_source_outputs',len(rotors)==8 and [r['pwm_aux_function'] for r in rotors]==list(range(101,109)))
check('planar_rank_three',rank(B_geom)==3)
check('z_force_roll_pitch_unavailable_in_geometry',all(all(abs(v)<1e-12 for v in B_geom[j]) for j in [2,3,4]))
u=[.5,0,.5,0,0,0,0,0];fault=mv(B_source,u);ideal=mv(B_noKM,u)
check('default_KM_extra_roll_detected',abs(fault[0]+.07)<1e-12 and abs(ideal[0])<1e-12,{'source':fault,'KM0_offline_comparison':ideal})
# Source-derived nonnegative planar proof controls; no allocation solver claim.
control_cases=[('plus_x',[.5,0,.5,0,0,0,0,0],[1,0,0]),('minus_x',[0,.5,0,.5,0,0,0,0],[-1,0,0]),('plus_y',[0,0,0,0,.5,0,.5,0],[0,1,0]),('minus_y',[0,0,0,0,0,.5,0,.5],[0,-1,0]),('plus_yaw',[.5,0,0,.5,0,0,0,0],[0,0,.12]),('minus_yaw',[0,.5,.5,0,0,0,0,0],[0,0,-.12])]
cases=[]
for name,u,want in control_cases:
 wrench=mv(B_geom,u);result=[wrench[0],wrench[1],wrench[5]];check('source_basis_'+name,max(abs(a-b) for a,b in zip(result,want))<1e-12);cases.append({'case':name,'geometric_unit_impulses_Ns':u,'result_Fxy_and_Hz':result,'control_only_not_hardware_command':True})
# Single motor 1 closed: use motors 5 & 8 for positive yaw, no net force.
u=[0,0,0,0,.5,0,0,.5];w=mv(B_geom,u);check('motor1_failed_closed_alternative_yaw',max(abs(x) for x in w[:5])<1e-12 and abs(w[5]-.12)<1e-12)
msg_pairs=[('VehicleThrustSetpoint.msg','VehicleThrustSetpoint.msg'),('VehicleTorqueSetpoint.msg','VehicleTorqueSetpoint.msg'),('versioned/ActuatorMotors.msg','ActuatorMotors.msg')]
msg=[]
for a,b in msg_pairs:
 pa=S/'px4/msg'/a;pb=S/'px4_msgs/msg'/b;equal=pa.read_bytes()==pb.read_bytes();check('message_exact_match_'+b,equal);msg.append({'message':b,'autopilot_sha256':sha(pa),'px4_msgs_sha256':sha(pb),'bytes_equal':equal})
ground={'schema':'ATMOS_SOURCE_GROUND_BASELINE_V1','status':'REAL_PUBLIC_CONFIG_EXTRACTED__OFFLINE_MATRIX_CHECKED__HARDWARE_NOT_EXECUTED','commits':{key:read(S/(key+'_tree.json'))['commit'] for key in ['atmos','px4','px4_msgs']},'frame':'PX4 body; parameter positions relative CG. No transform to spacecraft S or VACCO frame asserted.','airframe_id':70000,'rotors':rotors,'B_geometric_force_then_moment':B_geom,'B_fresh_source_moment_then_force':B_source,'B_KM0_offline_moment_then_force':B_noKM,'geometric_rank':rank(B_geom),'matrix_coefficient_scope':'CT=1.4 comes from source config; not calibrated thrust or solenoid nonlinear response. Source module.yaml describes rotor CT*u^2; spacecraft nonlinearity is TODO.','cases':cases,'messages':msg,'runtime_parameter_state':'NOT_READ; stored or other overrides unknown. Only reviewed source/default configuration diagnosed.','fresh_default_findings':['KM=0.05 from generic rotor parameters, no airframe override, geometry torque flags false. Source single-axis translation adds torque proportional to force.','KM=0 offline comparison is a project diagnostic, not a change to upstream source or an uploaded config.','airframe/rc.sc_defaults disable some checks and use mocap; no transplant into this spacecraft.'],'physical_coordinates_recovered':True,'physical_as_built_verified':False,'nonlinear_simultaneous_feed_model':'TODO_IN_SOURCE','hardware_execution_count':0,'flight_system_pass':False}
save(P/'ATMOS_GROUND_BASELINE.json',ground)

# Current instance ledger; use sourced allocations, not a density for COTS proxies.
rows=m['states']['service']['instances']; nr={r['id']:r for r in native['states']['service']}
newmetal={k for k,v in em['parts'].items() if k.startswith(('MIPS_CRADLE','MIPS_INTERFACE_SHIM','P60_TRAY','P60_HOST')) and v['representation_role']=='PHYSICAL_GEOMETRY'}|{k for k in em['parts'] if k.startswith(('POST_PWR','POST_DUAL','lower_equipment_deck','upper_equipment_deck'))}
ledger=[];sideids=set();armids=[r['id'] for r in rows if r.get('parent_assembly')=='B601_ARM']
for r in rows:
 id=r['id'];n=nr[id];source=r.get('source_mass_kg');allocation=source;basis=r.get('mass_source');owner=id;kind='INHERITED_'+str(basis);volume=None;density=None;note='';new=False
 if r.get('mass_source')=='UNKNOWN_UPDATED_GEOMETRY_ALLOCATION_PENDING' and r['representation_role']=='PHYSICAL_GEOMETRY':
  volume=r['actual_source_facts']['volume_mm3'];sideids.add(id);new=True
 elif id in newmetal:volume=em['parts'][id]['volume_mm3'];new=True
 if new:
  density=rho;allocation=volume*density;basis='DECLARED_AL_CANDIDATE_VOLUME_FROM_FROZEN_RECEIPT';kind='NEW_CANDIDATE_MATERIAL_ALLOCATION';note='AL_CANDIDATE 2700 kg/m3 engineering choice using prior policy; alloy/temper/tolerance and physical mass not certified.'
 if id in armids:owner='B601_DM_COMPLETE_GROUP';kind='GROUP_MEMBER_NO_DOUBLE_COUNT';note='Manufacturer whole-arm nominal 4.5 kg kept at group owner; individual link masses/inertias unassigned. Legacy URDF not imported or altered.'
 if id=='MIPS_OEM_MAX_ENVELOPE':owner='equipment_adcs_propulsion_allocation';kind='VENDOR_MODULE_WITHIN_PARENT_BUDGET';note='MiPS wet nominal 0.542 kg included within old 3 kg ADCS/propulsion aggregate, not added to total a second time.';allocation=None
 if id=='P60_REFERENCE_B':owner='EPS_CONFIG_GROUP_UNASSIGNED';note='Dock+ACU+PDU selected options not mapped to a single current mass owner; battery overlaps old equipment_battery allocation must be resolved.'
 item={'id':id,'mass_owner':owner,'representation_role':r['representation_role'],'parent_assembly':r.get('parent_assembly'),'source_mass_kg':source,'source_mass_basis':r.get('mass_source'),'candidate_allocated_mass_kg':allocation,'candidate_basis':basis,'accounting_kind':kind,'volume_mm3_used':volume,'density_kg_mm3_used':density,'physical_mass_kg':None,'COM_exact_S_m':None,'inertia_C_S_kg_m2':None,'geometry_path':r.get('step_path') or r.get('source_step',{}).get('path'),'geometry_sha256':r.get('source_sha256') or r.get('source_step',{}).get('sha256'),'native_path':n['native_path'],'native_sha256':n['native_sha256'],'geometry_T_S_local':r['T_S_local'],'native_T_S_local':n.get('native_T_local_to_S',n['T_S_local']),'service_bounds_mm':r['bounds_mm'],'note':note}
 ledger.append(item)
# All 701 rows accounted, new metal density never applied to simplified/functional items.
check('current_701_unique_instances',len(ledger)==701 and len({x['id'] for x in ledger})==701)
check('native_same_instance_identity',set(nr)=={r['id'] for r in rows})
check('no_proxy_density',all(x['representation_role']=='PHYSICAL_GEOMETRY' for x in ledger if x['density_kg_mm3_used'] is not None))
check('unknown_mass_not_zero',all(x['candidate_allocated_mass_kg'] is None for x in ledger if x['source_mass_kg'] is None and x['density_kg_mm3_used'] is None))
check('MiPS_no_double_count',next(x for x in ledger if x['id']=='MIPS_OEM_MAX_ENVELOPE')['candidate_allocated_mass_kg'] is None)
check('no_arm_URDF_mass_import',all(x['candidate_allocated_mass_kg'] is None for x in ledger if x['id'] in armids))
# Manufacturer nominal group mass, independently sourced from accepted digital URDF.
group={'owner':'B601_DM_COMPLETE_GROUP','members':armids,'candidate_nominal_mass_kg':4.5,'physical_mass_kg':None,'tolerance_kg':None,'source':read(P/'vendor/SOURCE.json'),'revision_match':'B601-DM family only; exact shipment revision unknown','individual_link_mass_allocation':None}
subset=sum(x['candidate_allocated_mass_kg'] or 0 for x in ledger);total= subset+group['candidate_nominal_mass_kg']
from collections import Counter
statebounds={};state_source_bindings={}
for state,manifest in m['states'].items():
 idx={x['id']:x for x in manifest['instances']};check('state_701_'+state,set(idx)==set(nr))
 nb={x['id']:x for x in native['states'][state]};state_source_bindings[state]=[{'id':i,'geometry_path':r.get('step_path') or r.get('source_step',{}).get('path'),'geometry_sha256':r.get('source_sha256') or r.get('source_step',{}).get('sha256'),'geometry_T_S_local':r['T_S_local'],'native_path':nb[i]['native_path'],'native_sha256':nb[i]['native_sha256'],'native_T_S_local':nb[i].get('native_T_local_to_S',nb[i]['T_S_local']),'bounds_mm':r['bounds_mm']} for i,r in idx.items()]
 # Interval COM of only the declared-mass ledger. Unknown residual mass not included.
 terms=[]
 for x in ledger:
  if x['candidate_allocated_mass_kg'] is not None:terms.append((x['candidate_allocated_mass_kg'],idx[x['id']]['bounds_mm']))
 b={'min_mm':[min(idx[i]['bounds_mm']['min_mm'][k] for i in armids) for k in range(3)],'max_mm':[max(idx[i]['bounds_mm']['max_mm'][k] for i in armids) for k in range(3)]};terms.append((4.5,b))
 comlo=[sum(mass*b['min_mm'][k]/1000 for mass,b in terms)/total for k in range(3)];comhi=[sum(mass*b['max_mm'][k]/1000 for mass,b in terms)/total for k in range(3)]
 # Upper bound about S origin for a subset whose each mass is contained in its AABB. No uniform-density model.
 diag=[]
 for k in range(3):
  axes=[j for j in range(3) if j!=k];diag.append(sum(mass*sum(max(abs(b['min_mm'][j]),abs(b['max_mm'][j]))**2/1e6 for j in axes) for mass,b in terms))
 statebounds[state]={'subset_COM_box_S_m':{'min':comlo,'max':comhi},'subset_I_about_S_diagonal_upper_kg_m2':diag,'scope':'Only declared CAD/nominal/budget masses; masses assumed contained within the named CAD envelopes. This is not the full-spacecraft COM or I and not an as-built guarantee.','full_COM_S_m':None,'full_inertia_C_S_kg_m2':None}
covered_ids={x['id'] for x in ledger if x['candidate_allocated_mass_kg'] is not None}|set(armids)|{'MIPS_OEM_MAX_ENVELOPE'}
summary={'schema':'CURRENT_V6_ENGINEERING_MASS_COVERAGE_V1','status':'CURRENT_INSTANCES_ACCOUNTED__PARTIAL_CANDIDATE_MASS__FULL_COM_INERTIA_UNKNOWN','scope_parent_component_count':701,'direct_parent_mass_fields_count':sum(x['source_mass_kg'] is not None for x in ledger),'direct_parent_mass_sum_kg':sum(x['source_mass_kg'] or 0 for x in ledger),'new_defined_metal_count':sum(x['density_kg_mm3_used'] is not None for x in ledger),'new_defined_metal_mass_kg':sum(x['candidate_allocated_mass_kg'] for x in ledger if x['density_kg_mm3_used'] is not None),'inherited_source_counts':dict(Counter(x['source_mass_basis'] for x in ledger)),'vendor_reference_coverage_without_extra_mass':[{'current_instance':'P60_REFERENCE_B','configuration':'Dock DS3.1 + ACU200 DS2.3 + PDU200 DS2.6, 1 each','nominal_reference_mass_kg':0.191,'scope':'No source/config binding to this proxy instance, not added'},{'current_instance':'equipment_battery','configuration':'BPX 100 Wh DS1.1.0','nominal_reference_mass_kg':0.5,'scope':'Nested reference within existing 1.6 kg budget, not added'},{'current_instance':'equipment_compute_communications','configuration':'A3200 DS2.0 single board','nominal_reference_mass_kg':0.024,'scope':'Nested reference within existing 0.5 kg budget, no second OBC'}],'candidate_direct_mass_sum_kg':subset,'manufacturer_whole_arm_group':group,'candidate_allocated_total_including_nominal_arm_kg':total,'allocated_mass_is_not_complete_or_minimum_mass':True,'covered_instance_ids_count_including_group_and_nested_vendor':len(covered_ids),'still_unassigned_instance_ids':[x['id'] for x in ledger if x['id'] not in covered_ids],'full_current_engineering_mass_kg':None,'complete_mass_COM_inertia':False,'mass_ownership_conflicts':[{'aggregate':'equipment_adcs_propulsion_allocation','budget_kg':3,'nested_module':'MIPS_OEM_MAX_ENVELOPE','vendor_wet_nominal_kg':.542,'remaining_budget_for_other_ADCS_propulsion_kg':2.458,'scope':'Design budget remainder, not actual hardware mass. P60 ownership still separate.'},{'aggregate':'equipment_battery','budget_kg':1.6,'BPX_configuration_match':None,'rule':'No standalone BPX mass added until battery responsibility is mapped.'}],'state_subset_bounds':statebounds,'source_binding_count':len(bindings),'accepted_URDF_modified':False,'scientific_Gate_modified':False}
save(P/'CURRENT_V6_MASS_LEDGER.json',{'summary':summary,'instances':ledger,'state_source_bindings':state_source_bindings})
with (P/'CURRENT_V6_MASS_LEDGER.csv').open('w',encoding='utf-8-sig',newline='') as f:
 fields=['id','mass_owner','representation_role','source_mass_kg','source_mass_basis','candidate_allocated_mass_kg','candidate_basis','accounting_kind','volume_mm3_used','density_kg_mm3_used','physical_mass_kg','geometry_path','geometry_sha256','native_path','native_sha256','note'];w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(ledger)
save(O/'PROP_MASS_COVERAGE.json',summary)

# Scalar necessary requirements and explicit direction bounds, without re-running a fictional array LP.
H=legacy['task_reference']['historical_capture']['H_combined_COM_magnitude_Nms_csv'];check('historical_H_preserved',H==3.65099)
require=[]
for r in [.025,.05,.075,.1,.12,.17]:
 for T in [300,900,3600]:
  J=H/r;F=H/(2*r*T);t10=H/(2*r*.01);t8=H/(2*r*.008)
  duty=t10/T;require.append({'effective_balanced_couple_lever_m':r,'window_s':T,'H_scalar_Nms':H,'required_shared_module_total_impulse_Ns':J,'required_each_thruster_force_N':F,'two_10mN_ideal_fire_time_s':t10,'two_8mN_ideal_fire_time_s':t8,'two_10mN_duty_required':duty,'two_10mN_window_necessary_condition':duty<=1,'MiPS44Ns_scalar_resource_necessary_condition':J<=44,'CPOD174Ns_scalar_resource_necessary_condition':J<=174,'CPOD_2jet_power_reference_W':5,'CPOD_conditioned_window_energy_Wh':(.25*T+4.75*t10)/3600 if duty<=1 else None,'power_note':'5 W two-jet published point; linear idle/burn mixture and no heater/startup energy assumed for this requirement only. It is not a bound on actual all-jet or thermal power.','is_actual_vendor_layout':False})
threshold=[]
for c in legacy['candidates']:
 for remaining in [1,.5,.1]:
  J=c['total_impulse_Ns']*remaining;threshold.append({'candidate':c['id'],'remaining_usable_impulse_fraction':remaining,'available_shared_total_impulse_Ns':J,'minimum_effective_couple_lever_m':H/J,'20percent_impulse_reserve_minimum_lever_m':H/(.8*J),'rule':'J_required=H/r_eff; necessary for one direction with zero net linear impulse, not sufficient vector controllability.'})
# Diagonal independent torque authority ellipsoid example: exact sphere-wide lower requirement L1<=sqrt(3)*H/r.
direction={'scope':'Mathematical directional requirement envelope only; no guessed actual post-capture vector','actual_H_vector_Nms':None,'reference_point':'historical combined center of mass','H_magnitude_Nms':H,'r_example_m':.1,'single_direction_best_necessary_impulse_Ns':H/.1,'orthogonal_independent_couples_equal_lever_all_directions_sufficient_resource_for_ideal_fixture_Ns':math.sqrt(3)*H/.1,'derivation':'For independently available orthogonal torque couples with common effective r, J=||H||_1/r and H<=||H||_1<=sqrt(3)H. Actual RCS may lack such couples. This analytic sphere bound is not finite sampling or an actual vendor guarantee.'}
check('scalar_requirement_examples',abs(H/.1-36.5099)<1e-9 and abs(H/(2*.05*.01)-3650.99)<1e-8)
check('module_resource_not_multiplied',all(x['available_shared_total_impulse_Ns']<=next(c['total_impulse_Ns'] for c in legacy['candidates'] if c['id']==x['candidate']) for x in threshold))
# Delta-v sensitivity after one ideal r=0.1m unloading; user has supplied no mission delta-v requirement.
dv=[]
for extra in [0,2,5,10]:
 mass=total+extra
 for c in legacy['candidates']:
  residual=max(0,c['total_impulse_Ns']-H/.1)
  dv.append({'candidate':c['id'],'candidate_allocated_mass_kg':total,'unassigned_mass_parameter_kg':extra,'conditional_total_mass_kg':mass,'unassigned_mass_zero_is_diagnostic_not_full_mass':True,'after_one_ideal_r0_1m_detumble_linear_impulse_remaining_Ns':residual,'delta_v_upper_small_impulse_approx_m_s':residual/mass,'target_captured_mass_150kg_delta_v_upper_m_s':residual/(mass+150),'scope':'J/m ideal single-direction upper accounting approximation; actual net thrust direction/propellant evolution and flight delta-v mission unbound.'})
package_bounds=[]
for c in legacy['candidates']:
 radius=math.sqrt(sum((x/2000)**2 for x in c['envelope_mm']))
 for remaining in [1,.5,.1]:
  upper=radius*c['total_impulse_Ns']*remaining
  package_bounds.append({'candidate':c['id'],'envelope_mm':c['envelope_mm'],'enclosing_sphere_radius_m':radius,'remaining_usable_impulse_fraction':remaining,'angular_impulse_norm_upper_Nms':upper,'historical_H_Nms':H,'necessary_magnitude_condition_met':upper>=H,'assumptions':['all nozzle force application points contained in adopted full module rectangular envelope','zero net spacecraft force at every instant (balanced couples), or frozen position-and-attitude integrated zero force as in a static allocation','catalogue impulse is available shared delivered total; no extra external actuator torque'], 'proof':'About the package center, |sum r_i cross J_i| <= R sum |J_i|. Instantaneous zero total force cancels offset from package center to spacecraft/captured COM. Therefore translating the complete module cannot increase this bound in the stated mode.','not_covered':'time-varying nonzero forces with allowed translational excursions; full manufacturer performance and operational environment'})
check('MiPS_complete_module_balanced_couple_bound_fails',package_bounds[0]['angular_impulse_norm_upper_Nms']<H)
check('CPOD_full_passes_only_necessary_bound',package_bounds[3]['angular_impulse_norm_upper_Nms']>H)
check('CPOD_10pct_balanced_couple_bound_fails',package_bounds[5]['angular_impulse_norm_upper_Nms']<H)
requirements={'schema':'PROPULSION_ENGINEERING_REQUIREMENTS_V1','status':'REQUIREMENTS_BACKSOLVED__ACTUAL_VENDOR_CAPABILITY_UNKNOWN','historical_H_Nms':H,'H_vector':None,'window_s':3600,'window_status':'HISTORICAL_PROVISIONAL_PARAMETER_NOT_CURRENT_ACCEPTANCE','couple_grid':require,'module_impulse_lever_thresholds':threshold,'direction_requirement':direction,'package_balanced_couple_bounds':package_bounds,'conditional_mass_delta_v_sensitivity':dv,'peak_power_requirements':[{'candidate':c['id'],'published_scope':c['published_power_scope'],'published_reference_W':c['published_power_W'],'reference_current_at_9V_A':c['published_power_W']/9,'reference_current_at_12V_A':c['published_power_W']/12,'source_output_required_V':'load terminal >=9 V and <=12.6 V over ripple/transient/drop; complete PDU path to be bound','actual_peak_heater_valve_current_A':None} for c in legacy['candidates']],'actual_system_pass':False}
save(P/'PROPULSION_REQUIREMENTS.json',requirements)

missing=['nozzle_id','nozzle_exit_position_in_vendor_frame_m','unit_force_axis_in_vendor_frame','installation_rotation_S_from_vendor','installation_translation_S_m','mount_hole_coordinates_datum_and_tolerances','permitted_concurrent_jet_sets','thrust_vs_pressure_temperature_and_simultaneous_count','minimum_command_pulse_s','MIB_vs_condition_Ns','latency_and_jitter_s','valve_peak_and_hold_current_A','heater_peak_and_thermostat','exact_RS422_connector_pinout','command_and_telemetry_dictionary_revision','default_power_loss_state','fail_open_leak_and_fail_closed_response','usable_impulse_vs_propellant_state','plume_cone_definition_and_impingement_limits','CG_and_inertia_wet_to_dry']
contracts=[]
for c in legacy['candidates']:
 d=dict(c);d['vendor_source_binding']=legacy['source_bindings'][c['source_id']];d['missing_external_ICD_fields']={key:None for key in missing};d['procurement_or_flight_selected']=False
 d['current_geometry_binding']=next(({'id':r['id'],'path':r['step_path'],'sha256':r['source_sha256'],'S_envelope_mm':r['bounds_mm'],'S_center_of_envelope_mm':[(a+b)/2 for a,b in zip(r['bounds_mm']['min_mm'],r['bounds_mm']['max_mm'])],'manufacturer_frame_to_S':None,'geometry_center_is_not_CG':True} for r in rows if r['id']=='MIPS_OEM_MAX_ENVELOPE'),None) if c['id']=='MIPS5_OLD' else None
 contracts.append(d)
check('vendor_ICD_null_not_filled_from_ground',all(all(v is None for v in c['missing_external_ICD_fields'].values()) for c in contracts))
save(P/'FLIGHT_CANDIDATE_EXTERNAL_ICD.json',{'schema':'COTS_PROPULSION_EXTERNAL_ICD_CANDIDATE_V1','candidates':contracts,'boundary':'Vendor owns internal tank/valves/controller. Project owns mounting power commands thermal/plume and task allocation. No pressure fabrication or live command package.','actual_capability':'UNKNOWN','build_approved':False,'physical_hardware_execution_count':0})
# Binding verifications stream original files; native and STEP sizes do not accumulate in memory.
asset_bindings={}
for row in [x for state_rows in state_source_bindings.values() for x in state_rows]:
 for key,hkey in [('geometry_path','geometry_sha256'),('native_path','native_sha256')]:
  p,h=row[key],row[hkey]
  if p and h:asset_bindings[p]=h
asset_checks=[{'path':p,'expected_sha256':h,'matches':sha(p)==h} for p,h in asset_bindings.items()]
check('all_current_source_assets_hash_bound',all(x['matches'] for x in asset_checks))
check('source_lock_after',all(sha(p)==h for p,h in bindings.items()))
# Read this process peak working set without starting additional programs.
import ctypes
from ctypes import wintypes
class PMC(ctypes.Structure):
 _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
pmc=PMC();pmc.cb=ctypes.sizeof(PMC);ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE
ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(PMC),wintypes.DWORD]
ok=ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(pmc),pmc.cb)
peak_mib=pmc.PeakWorkingSetSize/1048576 if ok else None
check('bounded_peak_working_set_lt250MiB',peak_mib is not None and peak_mib<250,peak_mib)
result={'schema':'WP_P_CLOSURE_EXECUTION_V1','status':'PASS_BOUNDED_SOURCE_EXTRACTION_AND_ACCOUNTING__FLIGHT_ICD_AND_FULL_MASS_HOLD','peak_working_set_MiB':peak_mib,'checks':checks,'check_count':len(checks),'checks_passed':sum(x['pass'] for x in checks),'current_source_asset_state_scope':'SERVICE_PARKING_RELEASED_SOURCE_HASH_ONLY_NOT_CAD_COLD_REOPEN','current_source_asset_checks':asset_checks,'source_bindings':bindings,'source_files_unchanged':True,'ground_real_source_geometry':True,'ground_compiled_or_hardware_executed':False,'fresh_default_KM_issue_preserved':True,'full_current_mass_COM_inertia_complete':False,'flight_candidate_actual_capability':'UNKNOWN','historical_math_fixture_not_rerun':True,'native_or_CAD_executed':False,'physical_execution_count':0,'approved_circuits':0,'build_approved':False,'accepted_URDF_or_scientific_gate_modified':False}
save(O/'PROP_REUSE_CLOSURE.json',result)
print(json.dumps({'checks':len(checks),'passed':sum(x['pass'] for x in checks),'parent_direct_mass_kg':summary['direct_parent_mass_sum_kg'],'new_metal_count':summary['new_defined_metal_count'],'new_metal_kg':summary['new_defined_metal_mass_kg'],'candidate_allocated_total_kg':total,'unassigned_instances':len(summary['still_unassigned_instance_ids']),'source_assets':len(asset_checks)}))
