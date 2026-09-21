"""Read-only WP03 receipt/accepted-STL integration checks; no CAD imports.

Writes only results/INTEGRATE_CHECKS.json. Missing instance receipts are explicit.
R2 source discontinuities are measured, never silently repaired in the old source.
"""
from pathlib import Path
import hashlib
import importlib.util
import itertools
import json
import math
import re
import sys
import time
import numpy as np

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
R2_SOURCE=ROOT/'20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/v3_source_reissue/solar_array_r2_kinematics_v3.py'
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);out=importlib.util.module_from_spec(spec);spec.loader.exec_module(out);return out
R2=module('wp03_integration_r2_source',R2_SOURCE)
MOTION_PATH=HERE.parent/'service_robot_wp02_20260905/motion_analysis.py'
M=module('wp03_integration_motion',MOTION_PATH)
KIN=M.kin
BASE=KIN.tf([90,0,125.15])
Q_PARK=[0,-30,-60,40,0,0]
Q_WORK=[0,-80,-70,30,0,0]
OUTPUT=HERE/'results/INTEGRATE_CHECKS.json'
PARAMETERS=HERE/'design_parameters.json'
REQUIRED=['id','bounds','parent_assembly','mount_interface','representation_role','product_role','arm_link','motion_group']

def rigid_inverse(t):
    t=np.asarray(t,float);out=np.eye(4);out[:3,:3]=t[:3,:3].T;out[:3,3]=-out[:3,:3]@t[:3,3];return out

def row_obb(row,transform=None):
    t=np.asarray(row['T_S_local'] if transform is None else transform,float)
    if t.shape!=(4,4) or not np.allclose(t[3],[0,0,0,1],atol=1e-12):raise ValueError('Invalid homogeneous transform:'+row['id'])
    if not np.allclose(t[:3,:3].T@t[:3,:3],np.eye(3),atol=1e-10) or abs(np.linalg.det(t[:3,:3])-1)>1e-10:
        raise ValueError('Nonproper instance transform:'+row['id'])
    local=row['local_bounds'];lo=np.asarray(local['min_mm']);hi=np.asarray(local['max_mm'])
    pts=boxpoints(lo,hi)@t[:3,:3].T+t[:3,3]
    return {'row':row,'T':t,'local_lo':lo,'local_hi':hi,'world_lo':pts.min(axis=0),'world_hi':pts.max(axis=0),
            'center':t[:3,:3]@((lo+hi)/2)+t[:3,3],'axes':t[:3,:3],'half':(hi-lo)/2}

def obb_sat(a,b,tolerance=1e-8):
    axes=[a['axes'][:,i] for i in range(3)]+[b['axes'][:,i] for i in range(3)]
    axes += [np.cross(a['axes'][:,i],b['axes'][:,j]) for i in range(3) for j in range(3)]
    delta=b['center']-a['center'];minimum=float('inf')
    for axis in axes:
        length=np.linalg.norm(axis)
        if length<1e-10:continue
        axis=axis/length
        overlap=float(np.dot(a['half'],np.abs(a['axes'].T@axis))+np.dot(b['half'],np.abs(b['axes'].T@axis))-abs(delta@axis))
        if overlap < -tolerance:return {'relation':'STRICT_OBB_SEPARATION','axis_gap_mm':-overlap}
        minimum=min(minimum,overlap)
    return {'relation':'OBB_TOUCHING' if minimum<=tolerance else 'OBB_INTERIOR_OVERLAP_CANDIDATE','minimum_axis_overlap_mm':minimum,
            'actual_material_overlap_volume_mm3':None}

def triangle_obb_clip(tris,triangle_lo,triangle_hi,obb):
    """Original world triangles -> conservative crop -> exact rigid local box clip."""
    mask=np.all(triangle_hi>=obb['world_lo']-1e-8,axis=1)&np.all(triangle_lo<=obb['world_hi']+1e-8,axis=1)
    cropped=tris[mask]
    if not len(cropped):return None
    t=obb['T'];local=(cropped-t[:3,3])@t[:3,:3]
    clipped=M.clipped_bounds(local,{i:(obb['local_lo'][i],obb['local_hi'][i]) for i in range(3)})
    if clipped:
        clipped['world_triangle_aabb_candidates']=len(cropped)
        clipped['coordinate_frame']='INSTANCE_LOCAL_BOUNDS'
    return clipped

def world_mesh_data(raw,q):
    frames=KIN.fk(q,BASE,15.0);out={}
    for name,tris in raw.items():
        world=KIN.place(tris.reshape(-1,3),frames[name]).reshape(-1,3,3)
        lo=world.min(axis=1);hi=world.max(axis=1)
        out[name]={'triangles':world,'triangle_lo':lo,'triangle_hi':hi,'lo':lo.min(axis=0),'hi':hi.max(axis=0)}
    return out

def arm_obb_pairs(world,obbs):
    total=0;separated=0;narrow=0;findings=[]
    for name,mesh in world.items():
        for obb in obbs:
            total+=1;row=obb['row']
            if np.any(np.minimum(mesh['hi'],obb['world_hi'])-np.maximum(mesh['lo'],obb['world_lo']) < -1e-8):
                separated+=1;continue
            narrow+=1;clipped=triangle_obb_clip(mesh['triangles'],mesh['triangle_lo'],mesh['triangle_hi'],obb)
            if clipped:
                findings.append({'arm_link':name,'instance_id':row['id'],'motion_group':row['motion_group'],
                    'representation_role':row['representation_role'],'product_role':row['product_role'],
                    'local_box_clip':clipped,'T_S_local_used':obb['T'].tolist(),
                    'status':'ACCEPTED_SURFACE_IN_INSTANCE_OBB_REQUIRES_ACTUAL_GEOMETRY_OR_CONTACT_RULE'})
    return {'total_pairs':total,'strict_aabb_separation_count':separated,'triangle_obb_clip_pair_count':narrow,'obb_surface_findings':findings,
            'actual_material_collision_status':'NOT_TESTED_OBB_IS_ENVELOPE','contains_status':'UNKNOWN'}

def retention_class(row):
    match=re.fullmatch(r'(cradle|cap)_([01])',row.get('motion_group',''))
    if not match:return None
    station=int(match.group(2));name=row['id']
    if match.group(1)=='cap':kind='CAP'
    elif name.startswith('hold_cap_pin_'):kind='CAP_AXIS_PIN_ENVELOPE'
    elif name.startswith('hold_latch_pin_'):kind='LOWER_AND_WITHDRAW_PIN'
    elif name.startswith(('hold_saddle_','hold_contact_pad_','hold_latch_clevis_','hold_latch_puller_','hold_confirm_latch_')):kind='LOWER'
    else:kind='MAST_ONLY'
    return station,kind

def retention_key_states(retention):
    # The path and CAD consume the same explicit design parameters. No old
    # 30 mm endpoint is inherited after a source-level stroke revision.
    retreat=float(retention['shoe_retreat_mm'])
    withdraw=float(retention['latch_withdraw_mm'])
    opened=float(retention['cap_open_deg'])
    folded=float(retention['fold_deg_released'])
    if not all(np.isfinite([retreat,withdraw,opened,folded])) or min(retreat,withdraw,opened,folded)<=0:
        raise ValueError('Retention sequence requires positive finite design parameters')
    result=[]
    def put(stage,pin=0,cap=0,drop=0,fold=0,fraction=None):
        result.append({'stage':stage,'pin_negative_x_mm':pin,'cap_open_deg':cap,'lower_drop_mm':drop,'mast_fold_deg':fold,
                       'arm_path_fraction':fraction,'q_deg':Q_PARK if fraction is None else (np.asarray(Q_PARK)+fraction*(np.asarray(Q_WORK)-Q_PARK)).tolist()})
    put('PARKING_BASELINE')
    for p in [withdraw/2,withdraw]:put('PIN_WITHDRAW',pin=p)
    for a in sorted(set([min(v,opened) for v in [1,5,25,50,75,opened]])):
        put('CAP_OPEN',pin=withdraw,cap=a)
    for d in sorted(set([min(1.,retreat),retreat]+list(np.arange(5.,retreat,5.)))):
        put('LOWER_RELEASE',pin=withdraw,cap=opened,drop=d)
    for a in sorted(set([min(1.,folded),folded]+list(np.arange(5.,folded,5.)))):
        put('MAST_FOLD',pin=withdraw,cap=opened,drop=retreat,fold=a)
    for f in M.SAMPLES:put('ARM_FIRST_MOTION',pin=withdraw,cap=opened,drop=retreat,fold=folded,fraction=f)
    return result

def retention_transform(row,state,roots,cap_roots):
    classified=retention_class(row)
    if classified is None:return np.asarray(row['T_S_local'])
    station,kind=classified
    root=KIN.tf(roots[station]);fold=root@KIN.tf(rpy=[math.radians(state['mast_fold_deg']),0,0])@rigid_inverse(root)
    initial=np.asarray(row['T_S_local'])
    if kind in ['CAP','CAP_AXIS_PIN_ENVELOPE']:
        # CAD stores the circular hinge pin inTc. Following that local-box frame
        # does not assert that the rotationally symmetric real pin spins withcap.
        pivot=KIN.tf(cap_roots[station]);opened=pivot@KIN.tf(rpy=[math.radians(state['cap_open_deg']),0,0])@rigid_inverse(pivot)
        return fold@opened@initial
    shift=np.eye(4)
    if kind in ['LOWER','LOWER_AND_WITHDRAW_PIN']:shift[2,3]=-state['lower_drop_mm']
    if kind=='LOWER_AND_WITHDRAW_PIN':shift[0,3]=-state['pin_negative_x_mm']
    return fold@shift@initial

def retention_path_check(parking_path,service_path,raw,parameters):
    pmeta,parking=read_receipt(parking_path);smeta,service=read_receipt(service_path)
    by_id={r['id']:r for r in parking};service_id={r['id']:r for r in service}
    required_metadata=['local_bounds','T_S_local']
    missing=[{'id':r['id'],'fields':[k for k in required_metadata if k not in r]} for r in parking if any(k not in r for k in required_metadata)]
    if missing:return {'status':'UNKNOWN_MISSING_LOCAL_OBB_METADATA','missing':missing}
    roots={};cap_roots={}
    for station,x in enumerate([-115.,-40.]):
        roots[station]=np.asarray(by_id[f'hold_fold_mast_{station}']['T_S_local'])[:3,3]
        if not np.allclose(roots[station],[x,-99,135.15],rtol=0,atol=1e-10):
            return {'status':'UNKNOWN_RETENTION_ROOT_CONTRACT_MISMATCH','station':station,'actual_root':roots[station].tolist()}
        cap_roots[station]=np.asarray(by_id[f'hold_open_cap_{station}']['T_S_local'])[:3,3]
    moving=[r for r in parking if retention_class(r) is not None]
    fixed=[r for r in parking if not r.get('arm_link') and retention_class(r) is None]
    fixed_obbs=[row_obb(r) for r in fixed]
    world_park=world_mesh_data(raw,Q_PARK);states=[];baseline_arm=set();baseline_cross=set()
    key_states=retention_key_states(parameters['retention'])
    for index,state in enumerate(key_states):
        moving_obbs=[row_obb(r,retention_transform(r,state,roots,cap_roots)) for r in moving]
        world=world_park if state['arm_path_fraction'] is None else world_mesh_data(raw,state['q_deg'])
        arm=arm_obb_pairs(world,moving_obbs)
        arm_keys={(r['arm_link'],r['instance_id']) for r in arm['obb_surface_findings']}
        cross=[];cross_total=0;cross_separated=0
        pairs=[(a,b) for a in moving_obbs for b in fixed_obbs]
        pairs += [(a,b) for a,b in itertools.combinations(moving_obbs,2) if retention_class(a['row'])!=retention_class(b['row'])]
        for a,b in pairs:
            cross_total+=1
            if np.any(np.minimum(a['world_hi'],b['world_hi'])-np.maximum(a['world_lo'],b['world_lo']) < -1e-8):
                cross_separated+=1;continue
            relation=obb_sat(a,b)
            if relation['relation']=='STRICT_OBB_SEPARATION':cross_separated+=1;continue
            cross.append({'ids':[a['row']['id'],b['row']['id']],
                          'representation_roles':[a['row']['representation_role'],b['row']['representation_role']],
                          'parent_assemblies':[a['row']['parent_assembly'],b['row']['parent_assembly']],
                          'motion_classes':[retention_class(a['row']),retention_class(b['row'])],**relation})
        cross_keys={tuple(sorted(r['ids'])) for r in cross}
        if index==0:baseline_arm=arm_keys;baseline_cross=cross_keys
        stage=dict(state,arm_retention=arm,hardware_obb_total_pairs=cross_total,hardware_obb_separated_pairs=cross_separated,
                   hardware_obb_candidates=cross,new_arm_pair_candidates_vs_baseline=[list(k) for k in sorted(arm_keys-baseline_arm)],
                   new_hardware_pair_candidates_vs_baseline=[list(k) for k in sorted(cross_keys-baseline_cross)])
        # Fixed hardware is also checked along the26 arm samples, with wings folded.
        if state['arm_path_fraction'] is not None:stage['arm_fixed_at_folded_wings']=arm_obb_pairs(world,fixed_obbs)
        states.append(stage)
        print(json.dumps({'event':'retention_state','index':index,'stage':state['stage'],'fold_deg':state['mast_fold_deg'],
                          'q_fraction':state['arm_path_fraction'],'arm_obb_hits':len(arm_keys),'new_arm_pairs':stage['new_arm_pair_candidates_vs_baseline'],
                          'new_hardware_obb_pairs':len(stage['new_hardware_pair_candidates_vs_baseline'])}),flush=True)
    endpoint=key_states[-1];comparison=[]
    for row in moving:
        if row['id'] not in service_id:
            comparison.append({'id':row['id'],'status':'SERVICE_INSTANCE_MISSING'});continue
        actual=row_obb(service_id[row['id']]);predicted=row_obb(row,retention_transform(row,endpoint,roots,cap_roots))
        center_error=float(np.max(np.abs(actual['center']-predicted['center'])))
        axis_error=float(np.max(np.abs(actual['axes']-predicted['axes'])))
        half_error=float(np.max(np.abs(actual['half']-predicted['half'])))
        comparison.append({'id':row['id'],'center_max_error_mm':center_error,'axis_matrix_max_error':axis_error,'half_size_max_error_mm':half_error,
                           'status':'MATCH_TO_RECEIPT_OBB' if center_error<1e-6 and axis_error<1e-9 and half_error<1e-6 else 'ENDPOINT_OBB_DIFFERENCE_REQUIRES_EXPLANATION'})
    return {'status':'SAMPLED_RETENTION_SEQUENCE_WITH_EXPLICIT_OBB_CANDIDATES','state_count':len(states),'arm_pose_count':len(M.SAMPLES),
            'moving_instance_count':len(moving),'fixed_instance_count':len(fixed),'states':states,'endpoint_service_comparison':comparison,
            'receipt_sha256':{str(parking_path):sha(parking_path),str(service_path):sha(service_path)},
            'motion_classification':[{'id':r['id'],'class':retention_class(r)} for r in moving],
            'design_retention_parameters':parameters['retention'],
            'lower_retreat_samples_mm':[s['lower_drop_mm'] for s in key_states if s['stage']=='LOWER_RELEASE'],
            'fold_samples_deg':[s['mast_fold_deg'] for s in key_states if s['stage']=='MAST_FOLD'],
            'fixed_hardware_coverage':[{'id':r['id'],'parent_assembly':r['parent_assembly'],'representation_role':r['representation_role']} for r in fixed],
            'sequence_contract':f"pin-X{endpoint['pin_negative_x_mm']:g} -> cap+Rx{endpoint['cap_open_deg']:g} -> lower-Z{endpoint['lower_drop_mm']:g} -> mast+Rx{endpoint['mast_fold_deg']:g} aboutS[-115/-40,-99,135.15] ->26armposes; folded wings throughout this path.",
            'method':'World triangleAABB rejection then original acceptedSTL triangle clipping in each instance local OBB; hardware boxes use15-axisSAT.',
            'limits':['OBBs include holes/concavities and are not actual physical material; every positive record is a candidate, not an OCC collision verdict.',
                      'Cap-axis pin OBB follows the CADTc frame for endpoint agreement; this is not a physical pin-spin claim.',
                      'Baseline contacts remain candidates; no automatic allowed-contact suppression. Same motion-class pairs omitted as kinematically invariant, not passed.',
                      'Only finite key states, not a continuous swept-volume certificate. Whole closed-volume containment and accepted arm self-collision remainUNKNOWN.',
                      'Every sampled lower-retreat/fold state includes moving retention vs all fixed nonarm instance OBBs, including folded wing leaves/hardware and bus structure. Positive OBB intersections are not material intersections.',
                      'Leaf deployment with released retention hardware is not included; folded-wings arm sequence and service endpoint are separate evidence.']}

def method_fixture_checks():
    """Small analytic fixtures for the added OBB/local transform machinery."""
    base={'id':'fixture','T_S_local':np.eye(4).tolist(),'local_bounds':{'min_mm':[-1,-1,-1],'max_mm':[1,1,1]}}
    first=row_obb(base);tests=[]
    for label,translation,expected in [('separated',[3,0,0],'STRICT_OBB_SEPARATION'),('touching',[2,0,0],'OBB_TOUCHING'),('overlap',[1.5,0,0],'OBB_INTERIOR_OVERLAP_CANDIDATE')]:
        other=row_obb(base,KIN.tf(translation));actual=obb_sat(first,other)['relation']
        tests.append({'case':label,'expected':expected,'actual':actual,'matched':expected==actual})
    inside=dict(base,local_bounds={'min_mm':[-.1,-.1,-.1],'max_mm':[.1,.1,.1]})
    actual=obb_sat(first,row_obb(inside))['relation']
    tests.append({'case':'box_containment','expected':'OBB_INTERIOR_OVERLAP_CANDIDATE','actual':actual,'matched':actual=='OBB_INTERIOR_OVERLAP_CANDIDATE'})
    t=KIN.tf([7,8,9],[.3,.2,.7]);obb=row_obb(base,t)
    local=np.array([[[-2,0,0],[2,0,0],[0,2,0]]],float);world=local@t[:3,:3].T+t[:3,3]
    clipped=triangle_obb_clip(world,world.min(axis=1),world.max(axis=1),obb)
    matched=clipped is not None and np.allclose(clipped['min_mm'],[-1,0,0],atol=1e-10) and np.allclose(clipped['max_mm'],[1,1,0],atol=1e-10)
    tests.append({'case':'rotated_box_triangle_crossing_no_original_vertex_inside','matched':bool(matched),'actual':clipped})
    return {'scope':'Analytic method fixtures only; not assembly validation','cases':tests,'all_matched':all(t['matched'] for t in tests)}

def material_witness(mesh,obb):
    """Interior witness in source-defined clevis walls/saddle web, excluding bores.

    Only these exact3ee4b4 source primitives are supported. This is an accepted
    STL surface inside the modeled hardware material, not a full arm BRep test.
    """
    name=obb['row']['id'];lo=obb['local_lo'];hi=obb['local_hi'];center=(lo+hi)/2;eps=1e-4
    if name.startswith('hold_latch_clevis_'):
        assert np.allclose(hi-lo,[22,16,18],atol=1e-6)
        pieces=[(np.array([lo[0],lo[1],lo[2]]),np.array([-3.5,hi[1],hi[2]])),
                (np.array([3.5,lo[1],lo[2]]),hi.copy()),
                (np.array([-3.5,lo[1],lo[2]]),np.array([3.5,hi[1],center[2]-7]))]
        def bore_clearances(p):return [float(np.linalg.norm(p[1:]-[160,center[2]])-2.2)]
        definition='Box22x16x18 minus central7x18x17 upward1.5 and X-axisD4.4 throughbore; strict wall/bottom interior used.'
    elif name.startswith('hold_saddle_'):
        assert np.allclose(hi-lo,[28,181,8],atol=1e-6)
        pieces=[(np.array([-12,14,lo[2]]),np.array([12,167,hi[2]]))]
        def bore_clearances(p):return [float(np.linalg.norm(p[:2]-[0,y])-1.7) for y in [87,111]]
        definition='Main24x157x8 web,Y10..167; witnessrestrictedY>14 avoids mast notch/originblock and D4.4 guides; D3.4 holesY87/111 excluded.'
    else:return None
    mask=np.all(mesh['triangle_hi']>=obb['world_lo']-1e-8,axis=1)&np.all(mesh['triangle_lo']<=obb['world_hi']+1e-8,axis=1)
    indices=np.flatnonzero(mask);t=obb['T'];local=(mesh['triangles'][mask]-t[:3,3])@t[:3,:3]
    for piece_index,(a,b) in enumerate(pieces):
        for triangle_index,triangle in zip(indices,local):
            poly=triangle
            for axis in range(3):
                poly=M.clip_polygon(poly,axis,a[axis]+eps,True);poly=M.clip_polygon(poly,axis,b[axis]-eps,False)
                if not len(poly):break
            if not len(poly):continue
            points=[poly.mean(axis=0)]+list(poly)
            for point in points:
                cuts=bore_clearances(point)
                if min(cuts)>eps:
                    return {'status':'CONFIRMED_ACCEPTED_STL_SURFACE_INSIDE_SOURCE_HARDWARE_MATERIAL',
                        'instance_id':name,'source_triangle_index':int(triangle_index),'source_component':'link2',
                        'material_piece_index':piece_index,'witness_instance_local_mm':point.tolist(),
                        'witness_S_mm':(t[:3,:3]@point+t[:3,3]).tolist(),
                        'minimum_bore_boundary_clearance_mm':min(cuts),
                        'minimum_prismatic_piece_boundary_clearance_mm':float(min(np.min(point-a),np.min(b-point))),
                        'material_definition':definition,'full_nominal_arm_brep_collision':'NOT_COMPUTED'}
    return {'status':'NO_INTERIOR_MATERIAL_WITNESS_FOUND_UNKNOWN','instance_id':name,'material_definition':definition}

def refine_retention():
    data=json.loads(OUTPUT.read_text(encoding='utf-8'))
    parking_path=HERE/'results/parking_instances.json';meta,parking=read_receipt(parking_path)
    expected='3ee4b4e0a5d39d470d2f34d732f4b66e7fcbbc857840bef5e9b9597e2878ed5b'
    assert meta['source_sha256']==expected,'Analytic CSG witness definitions require source3ee4b4; do not silently apply to revisedCAD.'
    raw,sources=M.read_triangles();world=world_mesh_data(raw,Q_PARK);del raw
    by_id={r['id']:r for r in parking};roots={};caps={}
    for k in [0,1]:
        roots[k]=np.asarray(by_id[f'hold_fold_mast_{k}']['T_S_local'])[:3,3]
        caps[k]=np.asarray(by_id[f'hold_open_cap_{k}']['T_S_local'])[:3,3]
    moving=[r for r in parking if retention_class(r) is not None]
    findings=[]
    for state in data['retention_key_sequence']['states']:
        if state['stage']!='MAST_FOLD':continue
        for candidate in state['arm_retention']['obb_surface_findings']:
            row=by_id[candidate['instance_id']]
            if candidate['arm_link']!='link2' or not row['id'].startswith(('hold_latch_clevis_','hold_saddle_')):continue
            obb=row_obb(row,retention_transform(row,state,roots,caps));witness=material_witness(world['link2'],obb)
            record={'mast_fold_deg':state['mast_fold_deg'],'lower_drop_mm':state['lower_drop_mm'],**witness}
            findings.append(record);print(json.dumps({'event':'material_witness','data':record}),flush=True)
    scans=[]
    for drop in [50,60,80,100]:
        trials=[]
        for fold in sorted(set([1]+list(range(0,91,5)))):
            state={'pin_negative_x_mm':26,'cap_open_deg':100,'lower_drop_mm':drop,'mast_fold_deg':fold}
            obbs=[row_obb(r,retention_transform(r,state,roots,caps)) for r in moving]
            screen=arm_obb_pairs(world,obbs)
            trials.append({'mast_fold_deg':fold,'obb_surface_findings':screen['obb_surface_findings'],
                           'total_pairs':screen['total_pairs'],'narrow_pairs':screen['triangle_obb_clip_pair_count']})
        scan={'candidate_lower_drop_mm':drop,'fold_samples_deg':[r['mast_fold_deg'] for r in trials],
              'states_with_arm_obb_hits':sum(bool(t['obb_surface_findings']) for t in trials),
              'total_arm_obb_hit_pairs':sum(len(t['obb_surface_findings']) for t in trials),'trials':trials}
        scans.append(scan);print(json.dumps({'event':'drop_candidate','drop_mm':drop,'hit_states':scan['states_with_arm_obb_hits'],'hit_pairs':scan['total_arm_obb_hit_pairs']}),flush=True)
    clear=[r['candidate_lower_drop_mm'] for r in scans if r['total_arm_obb_hit_pairs']==0]
    data['retention_material_refinement']={'definition_source_sha256':expected,'accepted_mesh_sources':sources,'witnesses':findings,
        'classification':'Interior-point witnesses exclude actual source fork voids/bores; confirms intrusion of acceptedSTL surface into the modeled hardware material.',
        'drop_candidate_scans':scans,'smallest_tested_drop_without_arm_surface_in_retention_OBBs_mm':min(clear) if clear else None,
        'scope':'Only listed drops and20fold angles, fully openedcap100 andpin26, fixedparkedarm. No continuous or physical-hardware clearance pass.',
        'guide_warning':'Current70mmguide length is not an effective qualified stroke. Any increased drop requires new guide engagement, spring/jack, latch, puller and service geometry; no automatic approval.',
        'prior_path_findings':'results/INTEGRATE_PATH_R1_FINDINGS.json','prior_path_findings_sha256':sha(HERE/'results/INTEGRATE_PATH_R1_FINDINGS.json'),
        'supplement_script_sha256':sha(__file__)}
    OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'event':'refinement_complete','confirmed_witness_count':sum(r['status'].startswith('CONFIRMED') for r in findings),
                      'smallest_tested_no_obb_hit_drop_mm':min(clear) if clear else None}),flush=True)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def boxpoints(lo,hi):return np.array(list(itertools.product(*zip(lo,hi))))
def bbox(points):
    lo=points.min(axis=0);hi=points.max(axis=0)
    return {'min_mm':lo.tolist(),'max_mm':hi.tolist(),'size_mm':(hi-lo).tolist()}
def leaf_center(leaf):
    return np.array(leaf['start'])+R2.LEAF_SPAN/2*np.array(leaf['dir'])+leaf['midplane_offset']*np.array(leaf['normal'])
def leaf_corners(side,leaf):
    origin,e2,e3=R2.leaf_solid_frame(side,leaf)
    axes=np.column_stack(([1,0,0],e2,e3))
    local=boxpoints([0,0,0],[R2.LEAF_CHORD,R2.LEAF_SPAN,R2.LEAF_T])
    return local@axes.T+origin,axes
def r2_source_audit():
    experiments=[]
    cases=[('PH2_CROSS90_WITH_ROOT0',lambda e:((0,90-e,0),(0,90+e,0))),
           ('PH3_CROSS90_WITH_ROOT0_PH2_180',lambda e:((0,180,90-e),(0,180,90+e))),
           ('PH2_CROSS90_CANONICAL_ROOT90',lambda e:((90,90-e,0),(90,90+e,0))),
           ('CANONICAL_PH2_ENDPOINT180',lambda e:((90,180-e,0),(90,180,0))),
           ('CANONICAL_PH3_ENDPOINT180',lambda e:((90,180,180-e),(90,180,180)))]
    for epsilon in [1e-3,1e-6,1e-9]:
        for case,states in cases:
            before,after=states(epsilon)
            for side in [-1,1]:
                for a,b in zip(R2.leaf_segments(side,*before),R2.leaf_segments(side,*after)):
                    ca,ma=leaf_corners(side,a);cb,mb=leaf_corners(side,b)
                    delta=leaf_center(b)-leaf_center(a)
                    distances=np.linalg.norm(ca[:,None,:]-cb[None,:,:],axis=2)
                    experiments.append({'case':case,'epsilon_deg':epsilon,'side':side,'leaf':a['index'],
                        'before_angles_deg':before,'after_angles_deg':after,'normal_before':a['normal'],'normal_after':b['normal'],
                        'midplane_offset_mm':a['midplane_offset'],'center_before_yz_mm':leaf_center(a).tolist(),
                        'center_after_yz_mm':leaf_center(b).tolist(),'center_displacement_yz_mm':delta.tolist(),
                        'center_displacement_norm_mm':float(np.linalg.norm(delta)),
                        'corner_set_hausdorff_mm':float(max(distances.min(axis=0).max(),distances.min(axis=1).max())),
                        'frame_determinant_before':float(np.linalg.det(ma)),'frame_determinant_after':float(np.linalg.det(mb))})
    configurations=[]
    for cfg in [(0,0,0),(90,90,0),(90,180,180)]:
        for side in [-1,1]:
            for leaf in R2.leaf_segments(side,*cfg):
                points,axes=leaf_corners(side,leaf)
                configurations.append({'angles_deg':cfg,'side':side,'leaf':leaf['index'],'bounds':bbox(points),
                                       'frame_determinant':float(np.linalg.det(axes))})
    return {'source':str(R2_SOURCE),'source_sha256':sha(R2_SOURCE),'leaf_size_mm':[R2.LEAF_CHORD,R2.LEAF_SPAN,R2.LEAF_T],
            'hinge_root_y_abs_mm':R2.LEAF1_MID_Y,'hinge_root_z_mm':R2.HINGE_Z,'experiments':experiments,
            'canonical_frames':configurations,'status':'SOURCE_NORMAL_RESIGN_DISCONTINUITY_AND_REFLECTION_COUNTEREXAMPLES',
            'finding':'Offsets3/6mm reverse sign; center jumps approach6/12mm. Root0/phi90 and canonicalroot90/phi180 endpoint cases are distinct.',
            'static_geometry_scope':'Corners follow the old source literally, even where frame determinant is-1. This is not a valid proper-rotation transform.',
            'continuous_wing_motion_status':'UNKNOWN_SOURCE_KINEMATIC_DISCONTINUITY','old_source_modified':False}

def read_receipt(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data,list):return {},data
    for key in ['instances','parts','rows']:
        if isinstance(data.get(key),list):return {k:v for k,v in data.items() if k!=key},data[key]
    raise ValueError(f'No instances/parts/rows list in {path}')

def receipt_checks(path,raw):
    meta,rows=read_receipt(path)
    if 'T_S_arm_base' in meta and not np.allclose(meta['T_S_arm_base'],BASE,rtol=0,atol=1e-12):
        raise ValueError('Receipt root differs from the fixed authorized root; no implicit recentering allowed')
    q=meta.get('q_deg',Q_PARK if path.name.startswith('parking') else Q_WORK)
    finger=meta.get('finger_mm',15.0);frames=KIN.fk(q,BASE,finger)
    world={n:KIN.place(t.reshape(-1,3),frames[n]).reshape(-1,3,3) for n,t in raw.items()}
    missing=[];valid=[]
    for index,row in enumerate(rows):
        errors=[k for k in REQUIRED if k not in row]
        b=row.get('bounds',{})
        if not all(k in b for k in ['min_mm','max_mm']):errors.append('bounds.min_mm/max_mm')
        if errors:missing.append({'row_index':index,'id':row.get('id'),'missing':errors});continue
        lo=np.array(b['min_mm'],float);hi=np.array(b['max_mm'],float)
        if lo.shape!=(3,) or hi.shape!=(3,) or not np.all(np.isfinite([lo,hi])) or np.any(hi<lo):
            missing.append({'row_index':index,'id':row['id'],'invalid':'malformed bounds'});continue
        valid.append(row)
    by_role={};by_representation={}
    for row in valid:
        by_role[row['product_role']]=by_role.get(row['product_role'],0)+1
        by_representation[row['representation_role']]=by_representation.get(row['representation_role'],0)+1
    physical=[r for r in valid if r['representation_role']=='PHYSICAL_GEOMETRY']
    onboard_physical=[r for r in physical if r['product_role']=='ONBOARD_CANDIDATE']
    hull=lambda subset:None if not subset else bbox(np.vstack([boxpoints(r['bounds']['min_mm'],r['bounds']['max_mm']) for r in subset]))
    armpairs=[];candidates=[];separated=0
    fixtures=[r for r in valid if not r.get('arm_link')]
    obbs={r['id']:row_obb(r) for r in fixtures if 'local_bounds' in r and 'T_S_local' in r}
    for name,tris in world.items():
        lo=tris.min(axis=(0,1));hi=tris.max(axis=(0,1))
        triangle_lo=tris.min(axis=1);triangle_hi=tris.max(axis=1)
        for row in fixtures:
            f=row['bounds'];boxlo=np.array(f['min_mm']);boxhi=np.array(f['max_mm'])
            overlap=np.minimum(hi,boxhi)-np.maximum(lo,boxlo)
            if np.any(overlap < -1e-8):separated+=1;continue
            if row['id'] in obbs:
                clipped=triangle_obb_clip(tris,triangle_lo,triangle_hi,obbs[row['id']]);method='ORIGINAL_TRIANGLE_LOCAL_OBB_CLIP'
            else:
                clipped=M.clipped_bounds(tris,{a:(boxlo[a],boxhi[a]) for a in range(3)});method='WORLD_AABB_FALLBACK_LOCAL_METADATA_MISSING'
            pair={'arm_link':name,'instance_id':row['id'],'representation_role':row['representation_role'],
                  'product_role':row['product_role'],'parent_assembly':row['parent_assembly'],'mount_interface':row['mount_interface'],
                  'motion_group':row['motion_group'],'aabb_axis_overlap_mm':overlap.tolist(),'clipped_surface':clipped,
                  'method':method,
                  'finding':'BOX_ENVELOPE_SURFACE_OVERLAP_REQUIRES_REAL_GEOMETRY' if clipped else 'NO_STL_SURFACE_IN_BOX',
                  'actual_material_collision_status':'NOT_TESTED_RECEIPT_BOX_ONLY','contains_status':'UNKNOWN'}
            armpairs.append(pair)
            if clipped:candidates.append(pair)
    mixed_pairs=[];mixed_separated=0
    # Only different motion groups: parent performs physical-part OCC checking.
    for a,b in itertools.combinations(fixtures,2):
        if a['motion_group']==b['motion_group']:continue
        aa=a['bounds'];bb=b['bounds']
        overlap=np.minimum(aa['max_mm'],bb['max_mm'])-np.maximum(aa['min_mm'],bb['min_mm'])
        if np.any(overlap < -1e-8):mixed_separated+=1;continue
        relation=obb_sat(obbs[a['id']],obbs[b['id']]) if a['id'] in obbs and b['id'] in obbs else {'relation':'AABB_ONLY_LOCAL_METADATA_MISSING'}
        if relation['relation']=='STRICT_OBB_SEPARATION':mixed_separated+=1;continue
        mixed_pairs.append({'ids':[a['id'],b['id']],'motion_groups':[a['motion_group'],b['motion_group']],
                            'representation_roles':[a['representation_role'],b['representation_role']],
                            'axis_overlap_mm':overlap.tolist(),'obb_result':relation,'status':'BOX_CANDIDATE_NOT_MATERIAL_COLLISION'})
    present_arm={r['arm_link'] for r in valid if r.get('arm_link')}
    return {'receipt':str(path),'receipt_sha256':sha(path),'metadata':meta,'q_deg':q,'finger_mm':finger,'root_transform_mm':BASE.tolist(),
            'instance_count':len(rows),'validated_schema_count':len(valid),'schema_errors':missing,'product_role_counts':by_role,
            'arm_instances_present':sorted(present_arm),'expected_arm_instances_missing':sorted(set(raw)-present_arm),
            'representation_role_counts':by_representation,'onboard_physical_receipt_box_union':hull(onboard_physical),
            'all_role_receipt_box_union':hull(valid),'bounds_scope':'Conservative union of actual instance receipt bounds, not retessellated exact assembly extrema.',
            'arm_fixture_total_pairs':len(world)*len(fixtures),'arm_fixture_strict_separation_count':separated,
            'arm_fixture_triangle_clip_pair_count':len(armpairs),'arm_fixture_triangle_clip_pairs':armpairs,
            'arm_fixture_box_overlap_candidates':candidates,'mixed_motion_group_box_strict_separation_count':mixed_separated,
            'mixed_motion_group_box_candidates':mixed_pairs,'continuous_paths':'NOT_EVALUATED_RECEIPTS_ARE_STATIC',
            'contains_status':'UNKNOWN','allowed_contact_classification':'REQUIRES_OWNER_INTERFACE_RULES_NO_AUTOMATIC_ALLOW'}

def main():
    start=time.monotonic()
    data={'schema':'WP03_INTEGRATION_SCREEN_V1','r2_source_kinematics_audit':r2_source_audit(),'instance_checks':[],
          'missing_receipts':[],'status':'R2_AUDIT_COMPLETE_INSTANCE_RECEIPTS_PENDING','CAD_or_old_source_modified':False}
    data['method_fixtures']=method_fixture_checks()
    parameters=json.loads(PARAMETERS.read_text(encoding='utf-8'))
    data['historical_retention_findings']=[]
    for name in ['INTEGRATE_PATH_R1_FINDINGS.json','INTEGRATE_PATH_R1_MATERIAL_REFINEMENT.json']:
        archive=HERE/'results'/name
        if archive.exists():
            record={'path':str(archive),'sha256':sha(archive),'scope':'Historical 30 mm source/path; not a result for the current revised CAD.'}
            old=json.loads(archive.read_text(encoding='utf-8'))
            if 'retention_material_refinement' in old:
                ref=old['retention_material_refinement']
                record['confirmed_material_witnesses']=[{'instance_id':r['instance_id'],'mast_fold_deg':r['mast_fold_deg'],'lower_drop_mm':r['lower_drop_mm'],'status':r['status']} for r in ref['witnesses']]
                record['drop_candidate_summary']=[{k:r[k] for k in ['candidate_lower_drop_mm','states_with_arm_obb_hits','total_arm_obb_hit_pairs']} for r in ref['drop_candidate_scans']]
                record['scope']+=' Old guide70 geometry; tested80/100 clearance cannot replace checking the new guide150 geometry.'
            data['historical_retention_findings'].append(record)
    if not data['method_fixtures']['all_matched']:raise RuntimeError('OBB method fixture failed')
    wing_receipt=HERE/'results/WING_KINEMATICS_CHECK.json'
    if wing_receipt.exists():
        wing=json.loads(wing_receipt.read_text(encoding='utf-8'))
        data['wp03_revised_wing_candidate']={k:wing[k] for k in ['revision','status','interface_change','all_frame_determinants_plus1',
            'all_edge_lengths_preserved','sample_count','obb_pair_count','positive_interior_overlap_count','touching_count','touching_pairs','unknown']}
        data['wp03_revised_wing_candidate'].update(receipt=str(wing_receipt),receipt_sha256=sha(wing_receipt))
    paths=[HERE/'results/parking_instances.json',HERE/'results/service_instances.json']
    available=[p for p in paths if p.exists()]
    data['missing_receipts']=[str(p) for p in paths if not p.exists()]
    readiness=[]
    expected_arm={l.get('name') for l in KIN.TREE.findall('link')}
    for p in available:
        meta,rows=read_receipt(p)
        present={r.get('arm_link') for r in rows if r.get('arm_link')}
        missing_local=[r.get('id') for r in rows if 'local_bounds' not in r or 'T_S_local' not in r]
        source_matches=meta.get('source_sha256')==sha(HERE/'spacecraft_model.py')
        readiness.append({'receipt':str(p),'instance_count':len(rows),'missing_expected_arm_links':sorted(expected_arm-present),
                          'missing_local_metadata':missing_local,'model_source_matches_current':source_matches,
                          'ready':not(expected_arm-present) and not missing_local and source_matches})
    data['receipt_readiness']=readiness
    if len(available)==2 and all(r['ready'] for r in readiness):
        raw,sources=M.read_triangles();data['accepted_mesh_sources']=sources
        for path in available:
            result=receipt_checks(path,raw);data['instance_checks'].append(result)
            print(json.dumps({'event':'receipt_check','file':path.name,'instances':result['instance_count'],
                              'schema_errors':len(result['schema_errors']),'arm_box_candidates':len(result['arm_fixture_box_overlap_candidates'])}),flush=True)
        data['retention_key_sequence']=retention_path_check(paths[0],paths[1],raw,parameters)
        data['status']='STATIC_AND_SAMPLED_RETENTION_OBB_SCREEN_WITH_EXPLICIT_CANDIDATES_UNKNOWN_REMAINS'
    else:data['status']='WAITING_FOR_TWO_CURRENT_COMPLETE_RECEIPTS_NO_STALE_GEOMETRY_RUN'
    data['source_hashes']={str(p):sha(p) for p in [Path(__file__),R2_SOURCE,MOTION_PATH,KIN.URDF]}
    for p in [HERE/'wing_kinematics.py',wing_receipt]:
        if p.exists():data['source_hashes'][str(p)]=sha(p)
    for p in [HERE/'spacecraft_model.py',HERE/'design_parameters.json',HERE/'root_structure.py',*available]:
        if p.exists():data['source_hashes'][str(p)]=sha(p)
    data['elapsed_seconds']=time.monotonic()-start
    OUTPUT.parent.mkdir(exist_ok=True);OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':data['status'],'missing_receipts':data['missing_receipts'],'r2_source_status':data['r2_source_kinematics_audit']['status'],'elapsed_seconds':data['elapsed_seconds']}),flush=True)

if __name__=='__main__':refine_retention() if '--refine-retention' in sys.argv else main()
