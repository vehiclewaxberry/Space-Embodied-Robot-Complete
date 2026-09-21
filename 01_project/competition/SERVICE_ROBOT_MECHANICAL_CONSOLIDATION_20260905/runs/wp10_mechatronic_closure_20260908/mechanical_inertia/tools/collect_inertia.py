"""SI conversion and partial-set aggregation only. No CAD/COM imports."""
from pathlib import Path
import json,hashlib,csv,datetime,math,collections,shutil,psutil
import numpy as np
M=Path(__file__).resolve().parents[1];P=M.parent/'mechanical_intake/PARAMETER_PACKET.json'
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,j):(M/n).write_text(json.dumps(j,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
packet=load(P);jobs=load(M/'SOURCE_JOBS.json');assert jobs['source_packet_sha256']==sha(P)
geoms={}
for job in jobs['rows']:
    f=M/'results'/('G%03d.json'%job['index']);assert f.exists(),f
    q=load(f);assert q['source']['sha256']==job['source']['sha256'];q['receipt_path']=str(f);q['receipt_sha256']=sha(f)
    worker=M/'tools'/('read_material_inertia.py' if q['index']<14 else 'read_material_inertia_v2.py' if q['index']==14 else 'read_material_inertia_v3.py')
    if 'worker_sha256' in q:assert q['worker_sha256']==sha(worker)
    q['bound_worker']={'path':str(worker),'sha256':sha(worker)}
    geoms[q['source']['sha256']]=q
checks=[]
def ck(n,ok):checks.append(dict(id=n,passed=bool(ok)))
def inertia_ok(I):
    eig=np.linalg.eigvalsh(I);tol=max(float(np.max(np.abs(I)))*1e-9,1e-15)
    return bool(np.all(np.isfinite(I)) and np.max(np.abs(I-I.T))<=tol and eig[0]>=-tol and eig[2]<=eig[0]+eig[1]+tol)
def si(props,rho):
    return dict(mass_kg=props['volume_mm3']*1e-9*rho,COM_local_m=(np.asarray(props['COM_local_mm'])*1e-3).tolist(),
        inertia_COM_local_kg_m2=(np.asarray(props['I_COM_local_mm5'])*rho*1e-15).tolist())
rows=[];comparison=[];failures=[];integration_screens=[]
for g in geoms.values():
    if not g['status'].startswith('PASS_'):continue
    ck('source_%03d/source_unchanged_after_read'%g['index'],g['source_unchanged_after'])
    ck('source_%03d/declared_millimetre_units'%g['index'],g['declared_STEP_units'][0]==['millimetre'])
    A=np.asarray(g['default']['I_COM_local_mm5']);B=np.asarray(g['adaptive_eps1e9']['I_COM_local_mm5'])
    scale=max(float(np.linalg.norm(A,'fro')),float(np.linalg.norm(B,'fro')))
    difference=float(np.linalg.norm(A-B,'fro'));tolerance=1e-5*scale+1e-4
    ok=difference<=tolerance
    ck('source_%03d/inertia_cross_quadrature_engineering_screen'%g['index'],ok)
    integration_screens.append({'source_index':g['index'],'source_sha256':g['source']['sha256'],
        'default_method':g['default']['method'],'comparison_method':g['adaptive_eps1e9']['method'],
        'I_difference_Frobenius_mm5':difference,'I_scale_Frobenius_mm5':scale,
        'relative_difference':difference/max(scale,1e-30),'screen_relative_tolerance':1e-5,
        'screen_absolute_tolerance_mm5':1e-4,'passed':bool(ok),
        'strict_error_bound':None,'purpose':'Numerical cross-method usability screen only; not accuracy certification or physical uncertainty.'})
for body in packet['instances']:
    if body['mass']['identity']!='CANDIDATE_GEOMETRY_MATERIAL_MODEL':continue
    ident=body['id'];src=body['geometry_by_state']['service']['source_step'];g=geoms[src['sha256']];rho=body['material_density_SI']['estimate']
    ck(ident+'/all_state_source_hashes_in_read_receipts',all(x['source_step']['sha256'] in geoms for x in body['geometry_by_state'].values()))
    if not g['status'].startswith('PASS_'):
        failures.append(dict(id=ident,source_index=g['index'],reason=g.get('exception'),mass_COM_inertia=None));continue
    primary_key=g.get('primary_property_key','adaptive_eps1e9')
    primary=si(g[primary_key],rho);default=si(g['default'],rho)
    hist=body['mass']['estimate'];ddefault=default['mass_kg']-hist;dgk=primary['mass_kg']-hist
    ck(ident+'/positive_mass',primary['mass_kg']>0)
    Iloc=np.asarray(primary['inertia_COM_local_kg_m2']);cloc=np.asarray(primary['COM_local_m']);m=primary['mass_kg']
    ck(ident+'/local_inertia_physical',inertia_ok(Iloc))
    states={}
    for state,gb in body['geometry_by_state'].items():
        state_g=geoms[gb['source_step']['sha256']]
        ck(ident+'/'+state+'/state_specific_source_read_success',state_g['status'].startswith('PASS_'))
        state_primary=si(state_g[state_g.get('primary_property_key','adaptive_eps1e9')],rho)
        m=state_primary['mass_kg'];cloc=np.asarray(state_primary['COM_local_m']);Iloc=np.asarray(state_primary['inertia_COM_local_kg_m2'])
        T=np.asarray(gb['T_local_to_S_SI_m']);R=T[:3,:3];t=T[:3,3]
        ck(ident+'/'+state+'/Rorthogonal',np.max(np.abs(R.T@R-np.eye(3)))<1e-8 and abs(np.linalg.det(R)-1)<1e-8)
        c=R@cloc+t;I=R@Iloc@R.T;Io=I+m*(np.dot(c,c)*np.eye(3)-np.outer(c,c))
        ck(ident+'/'+state+'/Iphysical',inertia_ok(I) and inertia_ok(Io))
        ck(ident+'/'+state+'/trace_invariant',abs(np.trace(I)-np.trace(Iloc))<max(abs(np.trace(Iloc))*1e-10,1e-15))
        ck(ident+'/'+state+'/eigen_invariant',np.max(np.abs(np.linalg.eigvalsh(I)-np.linalg.eigvalsh(Iloc)))<max(np.max(np.abs(Iloc))*1e-10,1e-15))
        ck(ident+'/'+state+'/COM_roundtrip',np.max(np.abs(R.T@(c-t)-cloc))<1e-10)
        ck(ident+'/'+state+'/parallel_axis_back',np.max(np.abs((Io-m*(np.dot(c,c)*np.eye(3)-np.outer(c,c)))-I))<1e-12)
        states[state]=dict(mass_kg=m,COM_S_m=c.tolist(),inertia_about_instance_COM_expressed_S_kg_m2=I.tolist(),inertia_about_S_origin_expressed_S_kg_m2=Io.tolist(),
            static_pose_only=True,dynamic_link_id=None,state_specific_local_parameters=state_primary,
            source_geometry=gb['source_step'],source_read_receipt={'path':state_g['receipt_path'],'sha256':state_g['receipt_sha256']},
            primary_method=state_g.get('primary_method','GAUSS_KRONROD_EPS1E9_FULL_COM_AND_INERTIA'))
    ck(ident+'/state_material_mass_numerical_consistency',max(s['mass_kg'] for s in states.values())-min(s['mass_kg'] for s in states.values())<=max(primary['mass_kg']*1e-9,1e-12))
    conv=g['convergence'];unc={'identity':'UNIFORM_CANDIDATE_MATERIAL_GEOMETRIC_MODEL','standard_uncertainty':None,'distribution':None,'degrees_of_freedom':None,
        'as_built_material_density_uncertainty':None,'strict_inertia_error_bound_kg_m2':None,
        'comparison_method':g['adaptive_eps1e9']['method'],
        'observed_comparison_eps1e7_to1e9_COM_change_m':conv['COM_max_abs_change_mm']*1e-3,
        'observed_comparison_eps1e7_to1e9_inertia_max_element_change_kg_m2':conv['inertia_max_abs_change_mm5']*rho*1e-15,
        'returned_quadrature_relative_error_estimate':g['adaptive_eps1e9']['returned_volume_relative_error_estimate'],
        'returned_estimate_scope':'volume only' if g.get('method_revision','').startswith('V3') else 'requested full GK geometric properties; not rigorous bound',
        'warning':'Quadrature estimates/refinement differences are not strict inertia bounds, uncertainty distributions or manufacturing tolerances.'}
    rows.append(dict(id=ident,responsibility_owner=body['responsibility_owner'],representation_role=body['representation_role'],material_density_kg_m3=rho,
        primary_method=g.get('primary_method','GAUSS_KRONROD_EPS1E9_FULL_COM_AND_INERTIA'),primary=primary,legacy_method_readback=default,
        inherited_mass_kg=hist,legacy_default_mass_difference_kg=ddefault,primary_mass_difference_from_legacy_kg=dgk,
        legacy_default_mass_matches_numerical_screen=abs(ddefault)<=max(abs(hist)*1e-9,1e-12),
        mass_compatibility_screen_relative=1e-9,mass_compatibility_screen_absolute_kg=1e-12,
        as_built_parameters=None,uncertainty=unc,states=states,
        source_geometry=src,geometric_read_receipt={'path':g['receipt_path'],'sha256':g['receipt_sha256']},worker=g['bound_worker'],
        frame='Inherited STEP local frame, COM expressed in it; source identity fully matched. Not a joint frame or dynamic link.',
        selected_method_must_be_used_consistently_for_mass_COM_inertia=True,
        inherited_packet_mutated=False))
    comparison.append(dict(id=ident,owner=body['responsibility_owner'],legacy_mass_kg=hist,readback_default_mass_kg=default['mass_kg'],
        readback_default_minus_legacy_kg=ddefault,primary_mass_kg=m,primary_minus_legacy_kg=dgk,
        primary_method=g.get('primary_method','GAUSS_KRONROD_EPS1E9_FULL_COM_AND_INERTIA'),
        comparison_integral_mass_kg=g['adaptive_eps1e9']['volume_mm3']*1e-9*rho,
        comparison_integral_minus_default_kg=(g['adaptive_eps1e9']['volume_mm3']-g['default']['volume_mm3'])*1e-9*rho,
        default_vs_comparison_volume_relative_difference=g['default_vs_adaptive']['volume_relative_difference'],source_index=g['index']))

ck('selected_306_accounted',len(rows)+len(failures)==306)
fixtures=load(M/'results/ANALYTICAL_GEOMETRIC_FIXTURES.json')
ck('analytic_fixtures_real_GK_pass',all(x['pass'] for x in fixtures['tests']))
practical_fixtures=load(M/'results/PRACTICAL_QUADRATURE_ANALYTICAL_FIXTURES.json')
ck('analytic_fixtures_default_and_volume_adaptive_pass',all(x['passed'] for x in practical_fixtures['tests']))
box=next(x['observed'] for x in fixtures['tests'] if x['id']=='offset_box_1e-09')
bx=si(box,2000);expect=.012*(.02**2+.03**2)/12
ck('actual_OCC_box_SI_inertia_conversion',abs(bx['inertia_COM_local_kg_m2'][0][0]-expect)<1e-16 and abs(bx['mass_kg']-.012)<1e-14)
ck('wrong_linear_inertia_scaling_rejected',not math.isclose(box['I_COM_local_mm5'][0][0]*2000*1e-12,expect,rel_tol=1e-6))
ck('negative_inertia_eigenvalue_rejected',not inertia_ok(np.diag([-1e-5,2e-5,2e-5])))
ck('positive_inertia_triangle_violation_rejected',not inertia_ok(np.diag([1e-5,1e-5,3e-5])))
ck('asymmetric_inertia_rejected',not inertia_ok(np.array([[2e-5,1e-6,0],[0,2e-5,0],[0,0,2e-5]])))
ck('left_handed_frame_rejected',not abs(np.linalg.det(np.diag([-1.,1.,1.]))-1)<1e-8)
ck('nonorthogonal_frame_rejected',not np.max(np.abs(np.diag([1.,1.,1.01]).T@np.diag([1.,1.,1.01])-np.eye(3)))<1e-8)
partial=[]
for st in packet['state_names']:
    total=sum(x['states'][st]['mass_kg'] for x in rows)
    com=sum((x['states'][st]['mass_kg']*np.asarray(x['states'][st]['COM_S_m']) for x in rows),np.zeros(3))/total
    Io=sum((np.asarray(x['states'][st]['inertia_about_S_origin_expressed_S_kg_m2']) for x in rows),np.zeros((3,3)))
    Ic=Io-total*(np.dot(com,com)*np.eye(3)-np.outer(com,com))
    independent=sum((np.asarray(x['states'][st]['inertia_about_instance_COM_expressed_S_kg_m2'])+x['states'][st]['mass_kg']*(np.dot(np.asarray(x['states'][st]['COM_S_m'])-com,np.asarray(x['states'][st]['COM_S_m'])-com)*np.eye(3)-np.outer(np.asarray(x['states'][st]['COM_S_m'])-com,np.asarray(x['states'][st]['COM_S_m'])-com)) for x in rows),np.zeros((3,3)))
    ck(st+'/partial_set_parallel_axis_two_paths',np.max(np.abs(Ic-independent))<1e-10 and inertia_ok(Ic))
    partial.append(dict(state=st,scope='ONLY_SELECTED_MATERIAL_MODEL_SUBSET_NOT_SPACECRAFT',included_instance_count=len(rows),
        partial_mass_kg=total,partial_COM_S_m=com.tolist(),partial_inertia_about_partial_COM_S_kg_m2=Ic.tolist(),partial_inertia_about_S_origin_S_kg_m2=Io.tolist(),
        whole_spacecraft=False,flight_GSE_configuration_disposition_complete=False))

dump('MATERIAL_INERTIA_INSTANCES.json',dict(status='CANDIDATE_UNIFORM_MATERIAL_INERTIA_SUPPLEMENT',source_packet={'path':str(P),'sha256':sha(P)},
    adopted_method='Per-source recorded: first 15 sources full GK; remaining 222 sources default non-triangulated face quadrature with adaptive face comparison. Never mix one method mass with another method inertia.',
    coordinate_and_units={'length':'m','mass':'kg','inertia':'kg*m^2','source_length':'mm','geometric_integral':'mm^5','column_vectors':True},
    instances=rows,failed_instances=failures,whole_spacecraft_model_complete=False,accepted_URDF_modified=False))
dump('MATERIAL_MODEL_STATES.json',dict(states=partial,whole_spacecraft_mass_kg=None,whole_spacecraft_inertia_kg_m2=None,rigid_joint_tree_emitted=False))
with (M/'MASS_METHOD_COMPARISON.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(comparison[0]));w.writeheader();w.writerows(comparison)
guard_dir=M/'results/guard_receipts';guard_dir.mkdir(exist_ok=True)
guard_files=list((M/'logs').glob('native_delta_inertia_*.run.json'))
for f in guard_files:shutil.copy2(f,guard_dir/f.name)
guards=[load(f) for f in guard_files]
completed=[g for g in guards if g['status']=='COMPLETED']
samples=[s for g in guards for s in g.get('samples',[])]
ck('guard_thresholds_not_relaxed',all(g['minimum_start_available_mib']==2048 and g['available_floor_mib']==512 and g['max_child_tree_rss_mib']==1400 for g in guards))
ck('sampled_memory_limits_observed',all(s['available_mib']>=512 and s['child_tree_rss_mib']<=1400 for s in samples))
gk_fail=[g for g in geoms.values() if not g['status'].startswith('PASS_')]
dump('MATERIAL_INERTIA_LINEAGE.json',{'source_packet':{'path':str(P),'sha256':sha(P)},'source_jobs':{'path':str(M/'SOURCE_JOBS.json'),'sha256':sha(M/'SOURCE_JOBS.json')},
    'rows':[{'index':g['index'],'source':g['source'],'result':{'path':g['receipt_path'],'sha256':g['receipt_sha256']},
        'worker':g['bound_worker'],'primary_method':g.get('primary_method','GAUSS_KRONROD_EPS1E9_FULL_COM_AND_INERTIA'),
        'status':g['status'],'instance_ids':g['instances'],'declared_STEP_units':g.get('declared_STEP_units')}
        for g in geoms.values()]})
summary=dict(status='PASS_PARTIAL_MATERIAL_INERTIA_SUPPLEMENT__NO_COMPLETE_SPACECRAFT_MODEL' if not failures and all(x['passed'] for x in checks) else 'PARTIAL_OR_FAILED_MATERIAL_INERTIA_SUPPLEMENT',
    generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),instance_count=len(rows),target_instance_count=306,
    unique_source_count=len(geoms),successful_unique_source_count=len(geoms)-len(gk_fail),failed_unique_sources=[{'index':g['index'],'exception':g.get('exception')} for g in gk_fail],
    partial_mass_kg=partial[0]['partial_mass_kg'],legacy_material_subset_mass_kg=sum(x['inherited_mass_kg'] for x in rows),
    default_readback_material_subset_mass_kg=sum(x['legacy_method_readback']['mass_kg'] for x in rows),
    primary_mass_difference_from_legacy_subset_kg=sum(x['primary_mass_difference_from_legacy_kg'] for x in rows),
    legacy_default_mass_compatibility_count=sum(x['legacy_default_mass_matches_numerical_screen'] for x in rows),
    legacy_default_mass_mismatch_ids=[x['id'] for x in rows if not x['legacy_default_mass_matches_numerical_screen']],
    method='15 unique sources full GK local COM/inertia; 222 unique sources default face quadrature with adaptive comparison; all 237 default/full-GK-or-adaptive comparisons use relative Frobenius 1e-5 plus 1e-4 mm^5 engineering screen, not strict error bound',
    primary_method_source_counts=dict(collections.Counter(g.get('primary_method','GAUSS_KRONROD_EPS1E9_FULL_COM_AND_INERTIA') for g in geoms.values() if g['status'].startswith('PASS_'))),
    quadrature_comparison_pass_count=sum(s['passed'] for s in integration_screens),
    quadrature_comparison_max_relative_difference=max(s['relative_difference'] for s in integration_screens),
    all_unreported_numeric_error_bounds=None,as_built_mass_or_inertia=False,whole_spacecraft_inertia_complete=False,whole_spacecraft_mass_kg=None,
    remaining_physical_instances_without_complete_model=872-len(rows),motion_tree_complete=False,
    continuous_dynamics_control_RL_simulation_executed=False,SolidWorks_started=False,source_CAD_mutated=False,
    check_count=len(checks),checks_passed=sum(x['passed'] for x in checks),failed_checks=[x for x in checks if not x['passed']],
    actual_BRep_three_state_reintegration_checks=sum(len(g.get('actual_three_pose_BRep_checks',[])) for g in geoms.values()),
    reintegration_scope='Each unique source was rigidly placed at three representative transforms as a coordinate mathematics test; a transform is an actual configured state only when that state uses this same source SHA.',
    actual_configured_state_reintegration_checks=sum(1 for g in geoms.values() for c in g.get('actual_three_pose_BRep_checks',[]) if next(b for b in packet['instances'] if b['id']==c['representative_instance'])['geometry_by_state'][c['state']]['source_step']['sha256']==g['source']['sha256']),
    state_specific_geometry_instance_count=sum(len({s['source_geometry']['sha256'] for s in row['states'].values()})>1 for row in rows),
    guard_summary=dict(completed_geometry_processes=len(completed),max_sampled_child_RSS_MiB=max(s['child_tree_rss_mib'] for s in samples),
        minimum_sampled_available_MiB=min(s['available_mib'] for s in samples),startup_available_floor_MiB=2048,runtime_available_floor_MiB=512,RSS_limit_MiB=1400,
        historical_probe_failures=[{'name':g['name'],'status':g['status']} for g in guards if g['status']!='COMPLETED'],memory_guard_triggers=sum('MEMORY_GUARD' in g['status'] or 'WORKING_SET_GUARD' in g['status'] for g in guards)),
    outputs=[{'path':str(M/n),'sha256':sha(M/n)} for n in ['MATERIAL_INERTIA_INSTANCES.json','MATERIAL_MODEL_STATES.json','MASS_METHOD_COMPARISON.csv']],
    source_packet={'path':str(P),'sha256':sha(P)},source_jobs={'path':str(M/'SOURCE_JOBS.json'),'sha256':sha(M/'SOURCE_JOBS.json')},
    worker_versions=[{'path':str(M/'tools'/n),'sha256':sha(M/'tools'/n)} for n in ['read_material_inertia.py','read_material_inertia_v2.py','read_material_inertia_v3.py']],collector_source_sha256=sha(Path(__file__)))
dump('results/INERTIA_ALGEBRA_CHECKS.json',{'checks':checks,'scientific_GATE_credit':False})
dump('results/QUADRATURE_ENGINEERING_SCREENS.json',{'rows':integration_screens,'relative_tolerance':1e-5,'absolute_tolerance_mm5':1e-4,'strict_error_bound':None,'physical_uncertainty_assessed':False})
dump('results/RESOURCE_AUDIT.json',{'summary':summary['guard_summary'],'all_owned_guard_children_absent_now':all(not psutil.pid_exists(g.get('pid',-1)) for g in guards if g.get('pid')),
    'guard_receipts':[{'path':str(guard_dir/f.name),'sha256':sha(guard_dir/f.name),'status':load(f)['status']} for f in guard_files],
    'no_user_processes_terminated':True,'only_guard_owned_children_terminated_on_timeout':True})
summary['outputs'] += [{'path':str(M/n),'sha256':sha(M/n)} for n in ['MATERIAL_INERTIA_LINEAGE.json','results/INERTIA_ALGEBRA_CHECKS.json','results/QUADRATURE_ENGINEERING_SCREENS.json','results/RESOURCE_AUDIT.json','results/PRACTICAL_QUADRATURE_ANALYTICAL_FIXTURES.json','results/ANALYTICAL_GEOMETRIC_FIXTURES.json','results/NON_GK_INERTIA_NEGATIVE_CONTROL.json']]
dump('MATERIAL_INERTIA_DELIVERY.json',summary)
print(json.dumps({k:summary[k] for k in ['status','instance_count','successful_unique_source_count','partial_mass_kg','legacy_default_mass_compatibility_count','check_count','checks_passed','guard_summary']}))
