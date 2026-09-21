"""Static wrench authority only. No dynamics, valve commands or legacy gate edits.

Run once with --prepare, then rerun without arguments to replay hash-bound inputs.
Every output is confined to this R2 package; candidates are not installed hardware.
"""
from __future__ import annotations
import argparse, copy, csv, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import linprog

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]
RUN = Path('01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs')
WP09 = RUN/'wp09_interfaces_20260907_1525'
WP10 = RUN/'wp10_mechatronic_closure_20260908/implementation'
R1 = Path('20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919')
SOURCE_PATHS = {
    'WP03_REGISTER': Path('20_engineering/service_robot_wp03_spacecraft_body_r1/source_register.json'),
    'WP03_PARAMETERS': Path('20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'),
    'R1_SOURCE_MAP': R1/'inputs/NEUTRAL_SOURCE_MAP.json',
    'R1_BUILD_STATUS': R1/'results/BUILD_STATUS.json',
    'R1_PUBLIC_REFERENCE': R1/'inputs/REFERENCE_MATERIAL_BASIS.json',
    'CPOD_CONTRACT': WP09/'system_completion/propulsion/resume_20260908/PROPULSION_INTERFACE_CONTRACT.json',
    'TRADE_MATRIX': WP10/'results/propulsion_trade_20260917/PROPULSION_TRADE_MATRIX_20260917.json',
    'RESOURCE_SCREEN': WP10/'coupled_closure/PROPULSION_RESOURCE_SCREEN.json',
    'SIM08_ASSUMPTIONS': Path('30_simulation/sim_08_detumble_actuator_budget/assumptions.yaml'),
    'SIM10_CONFIG': Path('20_engineering/config/mission_feasibility/scan_v0.yaml'),
    'SIM10_SCALAR_IMPLEMENTATION': Path('30_simulation/sim_10_mission_feasibility/src/feasibility_core.py'),
}
WEB_SOURCES = [
    {'id':'NASA_GNC', 'url':'https://www.nasa.gov/smallsat-institute/sst-soa/guidance-navigation-and-control/', 'read_scope':'5.1 and 5.2.2; wheel momentum, saturation and external unloading; 2026 edition', 'retrieved':'2026-09-19'},
    {'id':'NASA_PROPULSION', 'url':'https://www.nasa.gov/smallsat-institute/sst-soa/in-space_propulsion/', 'read_scope':'Chapter opened; system technology context only, no project hardware qualification inferred', 'retrieved':'2026-09-19'},
    {'id':'DAWN_B1', 'url':'https://www.dawnaerospace.com/thrusters', 'read_scope':'OEM page opened; R1 public PDF/page conflict retained, not resolved by selecting a favorable value', 'retrieved':'2026-09-19'},
]

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def objects(value):
    if isinstance(value,dict):
        yield value
        for child in value.values(): yield from objects(child)
    elif isinstance(value,list):
        for child in value: yield from objects(child)

def candidate(n, bus):
    # Positions lie on a conceptual bus-face box. This is NOT a collision/plume design.
    half=np.asarray(bus,dtype=float)/2000
    offsets=np.asarray([.140,.080,.080])  # independent declared placement choice, m
    rows=[]
    for axis in range(3):
        offaxes=[k for k in range(3) if k!=axis]
        patterns=([(s,0) for s in [-1,1]] if n==12 else [(s,t) for s in [-1,1] for t in [-1,1]])
        if n==12: offaxes=[(axis+1)%3, (axis+2)%3]
        for side in [-1,1]:
            for ss in patterns:
                p=np.zeros(3); p[axis]=side*half[axis]
                for k,s in zip(offaxes,ss): p[k]=s*offsets[k]
                d=np.zeros(3); d[axis]=-side  # spacecraft force; exhaust is -d
                rows.append({'id':f'C{n}_J{len(rows)+1:02}', 'position_S_m':p.tolist(), 'force_direction_S_unit':d.tolist(),
                             'force_max_N':.012, 'force_min_average_N':0.0, 'instantaneous_min_on_force_N':None,
                             'direction_kind':'FORCE_ON_SPACECRAFT_NOT_EXHAUST', 'command_channel':None})
    return {'id':f'CONCEPT_{n}_JETS', 'configuration_binding':f'R2_MATHEMATICAL_CONCEPT_{n}_NOT_HARDWARE',
            'status':'ABSTRACT_STATIC_CONCEPT_NOT_INSTALLED_NOT_PACKAGING_VERIFIED', 'units':'m_N', 'frame':'S_BUS_GEOMETRIC_CENTER',
            'combined_com_S_m':[0,0,0], 'com_status':'DESIGN_ASSUMPTION_NOT_MEASURED',
            'allowed_concurrency':'ALL_CHANNELS_UNRESTRICTED_DESIGN_ASSUMPTION', 'force_model':'CONTINUOUS_AVERAGE_CONVEX_OUTER_BOUND',
            'design_force_basis':'12 mN class is a declared comparison scale from existing trade R1; not a selected OEM guarantee',
            'face_dimensions_source':'WP03_PARAMETERS bus_mm', 'offset_choice_m':offsets.tolist(),
            'manufacturing_release':False, 'plume_validated':False, 'physical_command_allowed':False, 'thrusters':rows}

def prepare():
    paths=[OUT/'inputs/ACTUATION_SOURCE_LOCK.json',OUT/'inputs/ACTUATION_CURRENT.json',OUT/'inputs/ACTUATION_CANDIDATES.json']
    if any(p.exists() for p in paths): raise FileExistsError('Refuse re-freeze: existing actuation input(s).')
    lock={'schema':'ACTUATION_SOURCE_LOCK_R2','sources':[{ 'id':k,'path':p.as_posix(),'sha256':sha(ROOT/p)} for k,p in SOURCE_PATHS.items()], 'web_sources':WEB_SOURCES}
    source=read(ROOT/SOURCE_PATHS['WP03_REGISTER']); cpod=read(ROOT/SOURCE_PATHS['CPOD_CONTRACT'])
    sm=read(ROOT/SOURCE_PATHS['R1_SOURCE_MAP']); rows={x['id']:x for g in sm['groups'] for x in g['rows']}
    related=[{'id':k,'representation_role':v.get('representation_role'),'T_S_local':v.get('T_S_local')} for k,v in rows.items() if re.search('adcs|propulsion|thruster|reaction_wheel',k,re.I)]
    wheels=[x for x in objects(source) if re.fullmatch('EQ-RW[1-4]',str(x.get('id','')))]
    current={'schema':'CURRENT_ACTUATION_INTAKE_R2','id':'CURRENT_R1_HARDWARE_UNBOUND','configuration_binding':cpod['configuration_binding'],
        'units':'m_N','frame':'S_BUS_GEOMETRIC_CENTER','installed_thruster_count':None,'thrusters':None,
        'combined_com_S_m':cpod['combined_com_m'],'allowed_concurrency':cpod['allowed_concurrency'],
        'installation_transform':cpod['installation_transform'],'command_map':cpod['command_map'],
        'source_fields':{'nozzle_xyz_m':cpod['nozzle_xyz_m'],'force_directions_unit':cpod['force_directions_unit']},
        'actual_wheel_spin_axes_S_unit':None,'actual_wheel_torque_Nm':None,'actual_wheel_momentum_limits_Nms':None,
        'catalogue_candidates_only':{'CPOD_count':8,'MiPS_count':5,'source':'TRADE_MATRIX; not current installed counts',
            'CPOD_catalogue_thrust_range_N':cpod['pulse']['thrust_catalogue_range_N'],'CPOD_catalogue_MIB_Ns':cpod['pulse']['minimum_impulse_bit_catalogue_Ns']},
        'inherited_wheel_records_not_installed':wheels,'R1_related_unique_instances':related,
        'R1_related_scope':'Only allocation box/interface records found by identifier scan; source_register independently explicitly leaves nozzle and wheel authority unbound.',
        'wheel_conflict':'4 x 30 mNms catalogue candidates versus sim_10 3 x 100 mNms scalar study class; pyramid versus 3 orthogonal + 1 skew unresolved.',
        'unknown_policy':'Unknown is null; no source box corner or connector transform is interpreted as a nozzle or spin axis.',
        'physical_command_allowed':False,'flight_ready':False}
    bus=read(ROOT/SOURCE_PATHS['WP03_PARAMETERS'])['bus_mm']
    concepts={'schema':'ACTUATION_ABSTRACT_COMPARISON_R2','not_current_configuration':True,'bus_mm':bus,
        'geometry_credit':'None: face points do not include nozzle/valve envelope, structure attachments, feed lines, solar wing, arm, target or plume keep-outs.',
        'purpose':'Show why signed rank, positive thrust authority and single failure are distinct. Jet counts are not procurement recommendations.',
        'candidates':[candidate(12,bus),candidate(24,bus)]}
    for p,d in zip(paths,[lock,current,concepts]):write(p,d)

def verify_sources(lock):
    bad=[x['id'] for x in lock['sources'] if not (ROOT/x['path']).is_file() or sha(ROOT/x['path'])!=x['sha256']]
    if bad: raise ValueError('SOURCE_HASH_MISMATCH:'+','.join(bad))

def matrix(model,com_override=None):
    required=['configuration_binding','thrusters','combined_com_S_m','allowed_concurrency']
    missing=[k for k in required if model.get(k) is None]
    if missing: raise ValueError('UNKNOWN_REQUIRED:'+','.join(missing))
    if model.get('units')!='m_N': raise ValueError('UNITS_NOT_M_N')
    if model.get('frame')!='S_BUS_GEOMETRIC_CENTER': raise ValueError('FRAME_UNBOUND')
    if model['allowed_concurrency']!='ALL_CHANNELS_UNRESTRICTED_DESIGN_ASSUMPTION': raise ValueError('CONCURRENCY_MODEL_NOT_IMPLEMENTED')
    rows=model['thrusters']
    if not rows or len({x['id'] for x in rows})!=len(rows): raise ValueError('EMPTY_OR_DUPLICATE_JET_IDS')
    def strict_numbers(value):
        if isinstance(value,(list,tuple)):
            for item in value:strict_numbers(item)
        elif isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,float,np.integer,np.floating)):
            raise ValueError('PHYSICAL_NUMBER_TYPE_INVALID')
    for row in rows:
        for key in ['position_S_m','force_direction_S_unit','force_max_N','force_min_average_N']:strict_numbers(row[key])
    strict_numbers(model['combined_com_S_m'] if com_override is None else com_override)
    pos=np.asarray([x['position_S_m'] for x in rows],dtype=float)
    dirs=np.asarray([x['force_direction_S_unit'] for x in rows],dtype=float)
    cm=np.asarray(model['combined_com_S_m'] if com_override is None else com_override,dtype=float)
    maxima=np.asarray([x['force_max_N'] for x in rows],dtype=float)
    minima=np.asarray([x['force_min_average_N'] for x in rows],dtype=float)
    if pos.shape!=(len(rows),3) or dirs.shape!=pos.shape or cm.shape!=(3,): raise ValueError('SHAPE_ERROR')
    if not all(np.isfinite(x).all() for x in [pos,dirs,cm,maxima,minima]):raise ValueError('NONFINITE_INPUT')
    if np.any(abs(np.linalg.norm(dirs,axis=1)-1)>1e-10):raise ValueError('NONUNIT_FORCE_DIRECTION')
    if any(x.get('direction_kind')!='FORCE_ON_SPACECRAFT_NOT_EXHAUST' for x in rows):raise ValueError('FORCE_EXHAUST_SIGN_UNBOUND')
    if np.any(maxima<=0) or np.any(minima!=0):raise ValueError('AVERAGE_FORCE_BOUNDS_INVALID')
    return np.vstack([dirs.T,np.cross(pos-cm,dirs).T]),maxima

def axes(B,maxima):
    """Maximize pure signed wrench with all other five components constrained zero.

    SI force rows / torque rows are scaled by a declared 0.1 m characteristic
    length for numerical conditioning only. This does not modify rank or moment arm.
    """
    scale=np.array([1.,1.,1.,.1,.1,.1]); A=B/scale[:,None]; n=B.shape[1]; result=[]
    for axis,name in enumerate(['Fx','Fy','Fz','Tx','Ty','Tz']):
        for sign in [1,-1]:
            unit=np.zeros(6);unit[axis]=sign
            solved=linprog(np.r_[np.zeros(n),-1.],A_eq=np.column_stack([A,-unit]),b_eq=np.zeros(6),
                           bounds=[(0,float(v)) for v in maxima]+[(0,None)],method='highs',options={'dual_feasibility_tolerance':1e-9,'primal_feasibility_tolerance':1e-9})
            if not solved.success: raise ValueError(f'LP_FAILED:{name}:{sign}:{solved.message}')
            u=solved.x[:n]; achieved=B@u; cap=float(solved.x[-1]*scale[axis]); want=np.zeros(6);want[axis]=sign*cap
            residual=float(np.max(abs(achieved-want))); bounds_ok=bool(np.all(u>=-1e-9) and np.all(u<=maxima+1e-9))
            if residual>1e-9 or not bounds_ok:raise ValueError('LP_SOLUTION_VERIFICATION_FAILED')
            result.append({'axis':name,'sign':sign,'maximum_pure_axis':cap,'unit':'N' if axis<3 else 'Nm',
                'nonzero_authority':bool(cap>1e-8),'forces_N':[float(x) for x in u], 'max_SI_wrench_residual':residual,
                'active_jet_count':int(np.count_nonzero(u>1e-9))})
    return result

def evaluate(model):
    try:B,f=matrix(model)
    except (ValueError,TypeError,KeyError) as exc:
        return {'id':model['id'],'status':'BLOCKED_UNKNOWN_OR_INVALID_INPUT','reason':str(exc),'rank_force':None,'rank_rotation':None,'rank_6D':None,
                'bidirectional_pure_axis_authority':None,'single_failure_analysis':None,'mission_feasible':None,'physical_command_allowed':False}
    normal=axes(B,f); faults=[]
    for i,row in enumerate(model['thrusters']):
        ff=f.copy();ff[i]=0; alive=np.delete(B,i,axis=1); aa=axes(B,ff)
        faults.append({'failed_jet':row['id'],'rank_6D':int(np.linalg.matrix_rank(alive,tol=1e-10)),
            'rank_rotation':int(np.linalg.matrix_rank(alive[3:],tol=1e-10)), 'axes':aa,
            'all_12_signed_pure_axes_nonzero':all(x['nonzero_authority'] for x in aa)})
    comchecks=[]
    for cm in [[.1,0,0],[-.1,0,0],[0,.05,0],[0,-.05,0],[0,0,.05],[0,0,-.05]]:
        bc,fc=matrix(model,cm);aa=axes(bc,fc)
        comchecks.append({'combined_com_S_m':cm,'status':'SYNTHETIC_OFFSET_NOT_CAPTURED_TARGET_CoM',
            'rank_6D':int(np.linalg.matrix_rank(bc,tol=1e-10)),'axes':aa,
            'all_12_signed_pure_axes_nonzero':all(x['nonzero_authority'] for x in aa)})
    return {'id':model['id'],'status':'STATIC_CONVEX_OUTER_BOUND_COMPUTED_NOT_PULSE_OR_MISSION_FEASIBILITY',
            'B_SI':B.tolist(),'rank_force':int(np.linalg.matrix_rank(B[:3],tol=1e-10)),
            'rank_rotation':int(np.linalg.matrix_rank(B[3:],tol=1e-10)),'rank_6D':int(np.linalg.matrix_rank(B,tol=1e-10)),
            'nominal_axes':normal,'all_12_signed_pure_axes_nonzero':all(x['nonzero_authority'] for x in normal),
            'single_failure_analysis':faults,'single_failures_retaining_all_12_pure_axes':sum(x['all_12_signed_pure_axes_nonzero'] for x in faults),
            'single_failure_cases':len(faults),'synthetic_com_checks':comchecks,
            'mission_feasible':None,'physical_command_allowed':False,'old_gate_credit':False}

def controls(model,current,lock):
    tests=[]
    def rejects(name,mutate,base=model):
        x=copy.deepcopy(base); mutate(x); r=evaluate(x); ok=r['status']=='BLOCKED_UNKNOWN_OR_INVALID_INPUT'
        tests.append({'name':name,'pass':ok,'status':r['status'],'reason':r.get('reason')}); assert ok,name
    rejects('unknown_geometry_no_zero_fill',lambda x:x.update(thrusters=None))
    rejects('unknown_com',lambda x:x.update(combined_com_S_m=None))
    rejects('unknown_concurrency',lambda x:x.update(allowed_concurrency=None))
    rejects('mm_cannot_be_read_as_m',lambda x:x.update(units='mm_N'))
    rejects('exhaust_sign_ambiguous',lambda x:x['thrusters'][0].update(direction_kind='EXHAUST'))
    rejects('zero_direction',lambda x:x['thrusters'][0].update(force_direction_S_unit=[0,0,0]))
    rejects('nonunit_direction',lambda x:x['thrusters'][0].update(force_direction_S_unit=[2,0,0]))
    rejects('NaN_rejected',lambda x:x['thrusters'][0].update(force_max_N=float('nan')))
    rejects('duplicate_jet_ids',lambda x:x['thrusters'][1].update(id=x['thrusters'][0]['id']))
    rejects('negative_force_bound_rejected',lambda x:x['thrusters'][0].update(force_min_average_N=-.01))
    rejects('positive_min_on_not_silently_relaxed',lambda x:x['thrusters'][0].update(force_min_average_N=.008))
    rejects('boolean_force_rejected',lambda x:x['thrusters'][0].update(force_max_N=True))
    rejects('boolean_minimum_rejected',lambda x:x['thrusters'][0].update(force_min_average_N=False))
    rejects('boolean_position_rejected',lambda x:x['thrusters'][0].update(position_S_m=[True,0,0]))
    rejects('boolean_direction_rejected',lambda x:x['thrusters'][0].update(force_direction_S_unit=[True,0,0]))
    rejects('string_force_rejected',lambda x:x['thrusters'][0].update(force_max_N='0.012'))
    rejects('string_position_rejected',lambda x:x['thrusters'][0].update(position_S_m=['0.183',0,0]))
    rejects('string_direction_rejected',lambda x:x['thrusters'][0].update(force_direction_S_unit=['1',0,0]))
    B,f=matrix(model); newB,_=matrix(model,[.03,-.01,.07]); delta=np.array([.03,-.01,.07])
    expected=B[3:]-np.cross(np.broadcast_to(delta,(B.shape[1],3)),B[:3].T).T
    ok=bool(np.allclose(newB[3:],expected,rtol=0,atol=1e-14));assert ok
    tests.append({'name':'com_reference_shift_cross_product','pass':ok})
    aa=axes(np.eye(6),np.ones(6));ok=sum(x['nonzero_authority'] for x in aa)==6;assert ok
    tests.append({'name':'full_rank_does_not_imply_positive_bidirectional_authority','pass':ok,'rank':6,'signed_axes_nonzero':6})
    fake=copy.deepcopy(lock);fake['sources'][0]['sha256']='0'*64
    try:verify_sources(fake);ok=False
    except ValueError:ok=True
    assert ok;tests.append({'name':'source_hash_mutation_fail_closed','pass':ok,'physical_source_mutated':False})
    r=evaluate(current);ok=r['rank_6D'] is None and r['physical_command_allowed'] is False;assert ok
    tests.append({'name':'current_hardware_remains_unknown','pass':ok})
    return tests

def mode_decision(requirements,evidence):
    # Never interpret a string, missing key, or zero as a passed physical input.
    if not isinstance(requirements,list) or not requirements or any(not isinstance(k,str) or not k for k in requirements) or len(set(requirements))!=len(requirements) or not isinstance(evidence,dict):
        return 'BLOCKED_INVALID_CONTRACT'
    values=[evidence.get(k) for k in requirements]
    if any(v is False for v in values):return 'BLOCKED_FAILED_REQUIREMENT'
    if any(v is not True for v in values):return 'BLOCKED_UNKNOWN_REQUIREMENT'
    return 'REQUIREMENTS_COMPLETE_FOR_REVIEW_NOT_EXECUTION_AUTHORITY'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');args=parser.parse_args()
    if args.prepare:prepare()
    modepath=OUT/'inputs/ORBIT_MODE_CONTRACT.json'
    if not modepath.is_file():raise FileNotFoundError('REQUIRED_ORBIT_MODE_CONTRACT_MISSING; no fresh result emitted')
    modes=read(modepath)
    if not modes.get('modes'):raise ValueError('EMPTY_ORBIT_MODES; no fresh result emitted')
    for mode in modes['modes']:
        if mode_decision(mode.get('required_evidence'),modes.get('current_evidence'))=='BLOCKED_INVALID_CONTRACT':raise ValueError('INVALID_ORBIT_MODE_REQUIREMENTS')
    lock=read(OUT/'inputs/ACTUATION_SOURCE_LOCK.json');verify_sources(lock)
    current=read(OUT/'inputs/ACTUATION_CURRENT.json'); concepts=read(OUT/'inputs/ACTUATION_CANDIDATES.json')
    result={'schema':'STATIC_ACTUATION_REVIEW_R2','generated_utc':datetime.now(timezone.utc).isoformat(),
        'analysis_scope':'Static algebra/LP engineering comparison. No coupled dynamics, controller, pulses, pressure, valve actuation or legacy gate changed.',
        'source_lock_sha256':sha(OUT/'inputs/ACTUATION_SOURCE_LOCK.json'), 'source_hashes_verified':len(lock['sources']),
        'input_sha256':{name:sha(OUT/'inputs'/name) for name in ['ACTUATION_CURRENT.json','ACTUATION_CANDIDATES.json']},
        'script_sha256':sha(__file__),'runtime':{'numpy':np.__version__,'scipy':scipy.__version__},
        'current':evaluate(current),'candidates':[evaluate(c) for c in concepts['candidates']],
        'negative_and_algebra_controls':controls(concepts['candidates'][0],current,lock),
        'known_limitations':['Convex continuous average thrust is an outer bound; minimum impulse bit, binary valves and scheduling are unmodeled.',
            'Candidate unrestricted concurrency has no OEM or PDU permission; LP vectors are mathematical witnesses, not valve commands.',
            'Rotation-row rank allows force coupling; pure torque authority is separately tested with net force constrained zero.',
            'Signed-axis existence certifies neither robust tracking nor specified disturbance/impulse margins.',
            'Candidate points have no CAD collision, plume, thermal, feed/pressure, harness, mass or fatigue verification.',
            'Synthetic CoM offsets do not cover actual 150 kg/22 kg captured configurations.'],
        'mission_feasible':None,'ready_for_on_orbit_control':False,'physical_commands_emitted':0,'old_scientific_gates_modified':False}
    verify_sources(lock)
    write(OUT/'results/ACTUATION_ANALYSIS.json',result)
    evaluations=[]
    for mode in modes['modes']:
        evaluations.append({'id':mode['id'],'decision':mode_decision(mode['required_evidence'],modes['current_evidence']),
            'physical_execution_allowed':False,'required_evidence':mode['required_evidence']})
    mode_controls=[]
    for evidence,wanted in [({'k':None},'BLOCKED_UNKNOWN_REQUIREMENT'),({'k':'true'},'BLOCKED_UNKNOWN_REQUIREMENT'),
                            ({'k':False},'BLOCKED_FAILED_REQUIREMENT'),({'k':True},'REQUIREMENTS_COMPLETE_FOR_REVIEW_NOT_EXECUTION_AUTHORITY')]:
        got=mode_decision(['k'],evidence);assert got==wanted
        mode_controls.append({'input':evidence,'expected':wanted,'actual':got,'pass':got==wanted})
    got=mode_decision([],{});assert got=='BLOCKED_INVALID_CONTRACT'
    mode_controls.append({'requirements':[],'input':{},'expected':'BLOCKED_INVALID_CONTRACT','actual':got,'pass':True})
    write(OUT/'results/ACTUATION_MODE_REVIEW.json',{'schema':'ORBIT_MODE_DESIGN_REVIEW_R2','contract_sha256':sha(modepath),
        'script_sha256':sha(__file__),'modes':evaluations,'controls':mode_controls,
        'meaning':'Fail-closed requirement classifier only; no onboard state machine or execution authority implemented.',
        'physical_commands_emitted':0})
    with (OUT/'docs/PROPULSION_NOZZLE_CONCEPTS.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        fields=['concept','jet','rx_m','ry_m','rz_m','dx','dy','dz','fmax_N','status'];writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for c in concepts['candidates']:
            for x in c['thrusters']:
                vals=[c['id'],x['id'],*x['position_S_m'],*x['force_direction_S_unit'],x['force_max_N'],c['status']]
                writer.writerow(dict(zip(fields,vals)))
    with (OUT/'docs/PROPULSION_STATIC_AUTHORITY.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        fields=['concept','condition','axis','sign','maximum_pure_axis','unit','nonzero_authority','active_jet_count'];writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for c in result['candidates']:
            for condition,aa in [('nominal',c['nominal_axes'])]+[(f['failed_jet']+'_FAILED',f['axes']) for f in c['single_failure_analysis']]:
                for row in aa:writer.writerow({'concept':c['id'],'condition':condition,**{k:row[k] for k in fields[2:]}})
    print(json.dumps({'current':result['current']['status'],'controls':len(result['negative_and_algebra_controls']),
        'candidates':[{k:c[k] for k in ['id','rank_force','rank_rotation','rank_6D','all_12_signed_pure_axes_nonzero','single_failures_retaining_all_12_pure_axes','single_failure_cases']} for c in result['candidates']]},ensure_ascii=False))

if __name__=='__main__':main()
