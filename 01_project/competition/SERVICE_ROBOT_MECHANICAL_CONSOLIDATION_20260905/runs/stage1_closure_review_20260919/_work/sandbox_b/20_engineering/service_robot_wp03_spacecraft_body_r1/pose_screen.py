"""Bounded WP03 pose screen using unchanged accepted STL; no CAD imports.

Only writes results/POSE_SCREEN.json and POSE_SCREEN.md. Known component envelope
includes arm, bus core, M3R receipt bounds and both wings. Pending WP03 hardware,
connectors and harness are explicitly incomplete until the CAD receipt exists.
"""
from pathlib import Path
import importlib.util
import itertools
import json
import math
import subprocess
import sys
import time
import hashlib
import numpy as np

sys.dont_write_bytecode=True
from wing_kinematics import frames as wing_frames,corners as wing_corners,REVISION as WING_REVISION
HERE=Path(__file__).resolve().parent
WP01=HERE.parent/'service_robot_wp01_20260905'
WP02=HERE.parent/'service_robot_wp02_20260905'
spec=importlib.util.spec_from_file_location('wp02_motion',WP02/'motion_analysis.py')
motion=importlib.util.module_from_spec(spec);spec.loader.exec_module(motion)
kin=motion.kin
ROOT_T=kin.tf([90,0,125.15])
FINGER=15.0
OUTPUT=HERE/'results/POSE_SCREEN.json'
LAYOUT=WP01/'LAYOUT_COMPARISON.json'
PARAMETERS=json.loads((WP01/'design_parameters.json').read_text(encoding='utf-8'))
OLD=json.loads(LAYOUT.read_text(encoding='utf-8'))
POSES=[{'id':'OPEN_PARKING_REFERENCE','q_deg':PARAMETERS['states']['stowed']['q_deg'],'wing_deg':0.0,
        'source':'WP01 design_parameters.states.stowed; meaning OPEN_PARKING, not launch stow'},
       {'id':'SERVICE_WORK_REFERENCE','q_deg':PARAMETERS['states']['work']['q_deg'],'wing_deg':90.0,
        'source':'WP01 design_parameters.states.work'}]
POSES += [{'id':f'EXISTING_CANDIDATE_{i+1}','q_deg':q,'wing_deg':0.0,
           'source':f'WP01 LAYOUT_COMPARISON.candidate_repair.candidate_sequence_q_deg[{i}]'}
          for i,q in enumerate(OLD['candidate_repair']['candidate_sequence_q_deg']) if i]

# R17B/validator integration: 期望配对集合与延期对由 accepted URDF 关节树推导（消除 35/36 硬编码）；
# 输入哈希合同使本次检查所用关节/碰撞表示/场景绑定本次输入快照（过期来源可被检出）。
INPUT_FILES=[WP01/'kinematics.py',WP01/'design_parameters.json',LAYOUT,WP01/'results/stowed_build_receipt.json',WP01/'results/FINGER_INTERFACE_CHECK.json',WP02/'motion_analysis.py',kin.URDF,HERE/'wing_kinematics.py']
def contract_input_hashes():return {str(p):sha(p) for p in INPUT_FILES}
def expected_nonadjacent_pairs():
    links=[l.get('name') for l in kin.TREE.findall('link')]
    adjacent={frozenset([j.find('parent').get('link'),j.find('child').get('link')]) for j in kin.TREE.findall('joint')}
    return sorted(tuple(sorted((a,b))) for a,b in itertools.combinations(links,2) if frozenset((a,b)) not in adjacent)
DEFERRED_PAIRS=[tuple(sorted(('gripper_left','gripper_right')))]
def screen_run_id(input_hashes):
    return hashlib.sha256(json.dumps({'inputs':input_hashes,'poses':[(p['id'],p['q_deg'],p['wing_deg']) for p in POSES]},sort_keys=True).encode()).hexdigest()
def snapshot_digest(input_hashes):
    return hashlib.sha256(json.dumps(input_hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bbox(points):
    lo=np.min(points,axis=0);hi=np.max(points,axis=0)
    return {'min_mm':lo.tolist(),'max_mm':hi.tolist(),'size_mm':(hi-lo).tolist()}
def corners(lo,hi):return np.array(list(itertools.product(*zip(lo,hi))))
def world_meshes(raw,q):
    frames=kin.fk(q,ROOT_T,FINGER)
    return {n:kin.place(t.reshape(-1,3),frames[n]).reshape(-1,3,3) for n,t in raw.items()}
def limit_checks(q):
    result=[];index=0
    for j in kin.TREE.findall('joint'):
        if j.get('type') not in ('revolute','prismatic'):continue
        limit=j.find('limit')
        if j.get('type')=='revolute':
            scale=180/math.pi;value=q[index];index+=1;unit='deg'
        else:scale=1000;value=FINGER;unit='mm'
        lower=float(limit.get('lower'))*scale;upper=float(limit.get('upper'))*scale
        result.append({'joint':j.get('name'),'value':value,'unit':unit,'lower':lower,'upper':upper,
                       'within_limit':bool(lower<=value<=upper)})
    return result
def geometry(raw,pose):
    world=world_meshes(raw,pose['q_deg']);parts=[];allpoints=[];tests=[]
    for name,tris in world.items():
        points=tris.reshape(-1,3);allpoints.append(points)
        parts.append({'instance':name,'representation_role':'ACCEPTED_STL_SOURCE_SURFACE',**bbox(points)})
    arm_bbox=bbox(np.vstack(allpoints))
    half=np.array(PARAMETERS['bus_mm'])/2
    fixtures=[{'name':'bus_core_reference','lo':-half,'hi':half,'representation':'FUNCTIONAL_CORE_ENVELOPE'}]
    receipt=json.loads((WP01/'results/stowed_build_receipt.json').read_text(encoding='utf-8'))
    assert np.allclose(receipt['T_S_arm_base'],ROOT_T,rtol=0,atol=1e-12)
    for rec in receipt['parts']:
        if 'M3R' in rec['part']:
            fixtures.append({'name':rec['part'],'lo':np.array(rec['min_mm']),'hi':np.array(rec['max_mm']),
                             'representation':'IMPORTED_M3R_BREP_AABB_ENVELOPE'})
    wing_angles=[0,0,0] if pose['wing_deg']==0 else [90,180,180]
    for side in [-1,1]:
        for leaf in wing_frames(side,wing_angles):
            wing=wing_corners(leaf);allpoints.append(wing);name=f'wing_substrate_{side}_leaf{leaf["index"]}'
            wb=bbox(wing);parts.append({'instance':name,'representation_role':'WP03_THREE_LEAF_PANEL_ENVELOPE',**wb})
            fixtures.append({'name':name,'lo':np.array(wb['min_mm']),'hi':np.array(wb['max_mm']),
                             'representation':'WP03_AXIS_ALIGNED_STATIC_LEAF_ENVELOPE'})
    for f in fixtures:
        if not f['name'].startswith('wing_'):
            allpoints.append(corners(f['lo'],f['hi']))
            parts.append({'instance':f['name'],'representation_role':f['representation'],**bbox(corners(f['lo'],f['hi']))})
        for link,tris in world.items():
            lo=tris.min(axis=(0,1));hi=tris.max(axis=(0,1))
            overlap=np.minimum(hi,f['hi'])-np.maximum(lo,f['lo'])
            row={'arm_link':link,'fixture':f['name'],'fixture_representation':f['representation'],'aabb_axis_overlap_mm':overlap.tolist()}
            if np.any(overlap < -1e-8):row.update(method='STRICT_AABB_SEPARATION',surface_hits=0)
            else:
                clip=motion.clipped_bounds(tris,{a:(f['lo'][a],f['hi'][a]) for a in range(3)})
                row.update(method='ORIGINAL_TRIANGLE_CLIP_TO_BOX',surface_hits=0 if clip is None else clip['intersecting_triangle_count'],clip=clip,
                           material_collision_status='UNKNOWN_ENVELOPE_OR_SURFACE_ONLY')
            tests.append(row)
    limits=limit_checks(pose['q_deg'])
    result=dict(pose,finger_mm=FINGER,root_transform_mm=ROOT_T.tolist(),joint_limits=limits,
                all_8_moving_joint_limits_satisfied=all(v['within_limit'] for v in limits),arm_bbox=arm_bbox,
                known_component_bbox=bbox(np.vstack(allpoints)),component_bounds=parts,arm_fixture_tests=tests,
                arm_fixture_surface_findings=[r for r in tests if r['surface_hits']],
                wing_angles_deg=wing_angles,wing_revision=WING_REVISION,
                known_component_envelope_scope='Accepted10-link arm incl palm/fingers + bus core + M3R sourceBRep bounds + six300x200x2.5 leaves ofWP03 serialwingR2; same fixedSframe.',
                full_wp03_onboard_assembly_evaluated=False,
                missing_scope=['WP03 physical structure/retention/wingroot instances pending owner receipt','Connectors and real harness routing','Sensor and actuator accessories'],
                self_surface_check={'status':'PENDING'},continuous_path_status='NOT_CHECKED_STATIC_CANDIDATE',
                volume_containment_status='UNKNOWN',launch_stow_status='NOT_ESTABLISHED')
    return result

def self_worker():
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray
    ih=contract_input_hashes();rid=screen_run_id(ih);sd=snapshot_digest(ih)
    raw,_=motion.read_triangles()
    adjacent={frozenset([j.find('parent').get('link'),j.find('child').get('link')]) for j in kin.TREE.findall('joint')}
    pairs=[(a,b) for a,b in itertools.combinations(raw,2) if frozenset([a,b]) not in adjacent]
    identity=vtk.vtkTransform();identity.Identity()
    def poly(tris):
        points=vtk.vtkPoints();points.SetData(numpy_to_vtk(np.ascontiguousarray(tris.reshape(-1,3)),deep=True))
        cells=np.column_stack([np.full(len(tris),3,dtype=np.int64),np.arange(3*len(tris),dtype=np.int64).reshape(-1,3)])
        triangles=vtk.vtkCellArray();triangles.SetCells(len(tris),numpy_to_vtkIdTypeArray(cells.ravel(),deep=True))
        out=vtk.vtkPolyData();out.SetPoints(points);out.SetPolys(triangles);return out
    for pose in POSES[2:]:
        world=world_meshes(raw,pose['q_deg'])
        triangle_bounds={n:(t.min(axis=1),t.max(axis=1)) for n,t in world.items()}
        bounds={n:(lo.min(axis=0),hi.max(axis=0)) for n,(lo,hi) in triangle_bounds.items()};rows=[]
        for a,b in pairs:
            rec={'links':[a,b],'surface_intersection':None,'vtk_tested':False}
            if {a,b}=={'gripper_left','gripper_right'}:
                rec['method']='ACCEPTED_STL_FINGER_PAIR_NOT_RETESTED_PRIOR_TIMEOUT'
            else:
                low=np.maximum(bounds[a][0],bounds[b][0]);high=np.minimum(bounds[a][1],bounds[b][1])
                if np.any(low>high):rec.update(surface_intersection=False,method='STRICT_LINK_AABB_SEPARATION')
                else:
                    crop={}
                    for name in [a,b]:
                        lo,hi=triangle_bounds[name];crop[name]=world[name][np.all(hi>=low,axis=1)&np.all(lo<=high,axis=1)]
                    rec['cropped_triangle_count']={n:len(t) for n,t in crop.items()}
                    if any(not len(t) for t in crop.values()):rec.update(surface_intersection=False,method='EMPTY_CONSERVATIVE_TRIANGLE_CROP')
                    else:
                        check=vtk.vtkCollisionDetectionFilter();check.SetInputData(0,poly(crop[a]));check.SetInputData(1,poly(crop[b]))
                        check.SetTransform(0,identity);check.SetTransform(1,identity);check.SetBoxTolerance(0);check.SetCellTolerance(0)
                        check.SetNumberOfCellsPerNode(16);check.SetCollisionModeToFirstContact();check.GenerateScalarsOff();check.Update()
                        contacts=int(check.GetNumberOfContacts())
                        rec.update(surface_intersection=bool(contacts),method='VTK_FIRST_CONTACT_ON_UNCHANGED_TRIANGLES',vtk_tested=True,contacts=contacts)
            rows.append(rec);print(json.dumps({'event':'pair','run_id':rid,'snapshot_digest':sd,'pose_id':pose['id'],'pose':pose['id'],'record':rec}),flush=True)
            if rec['surface_intersection']:break
        print(json.dumps({'event':'pose_complete','run_id':rid,'snapshot_digest':sd,'pose_id':pose['id'],'completed':True,'pose':pose['id'],'expected_pairs':len(pairs),'expected_pair_count':len(pairs),'rows':rows,
                          'vtk_version':vtk.vtkVersion.GetVTKVersion()}),flush=True)

def save(data):
    OUTPUT.parent.mkdir(exist_ok=True)
    data['script_sha256']=sha(__file__)
    OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# WP03 有限姿态筛查','',
           '固定根变换 S=[90,0,125.15] mm；所有候选双指15 mm。OPEN_PARKING保持开放停放语义，未定义发射收拢。','',
           '包络当前包含完整accepted臂、母线核心、M3R来源边界及两侧三叶翼（每叶300×200×2.5，WP03固定偏置R2）；WP03新增随星保持器/连接器/线束尚待实例收据，不能据本表宣称完整整星装箱可行。','',
           '| 姿态 | q/deg | 已知部件包络XYZ/mm | 8关节限位 | 自表面筛查 |','|---|---|---|---|---|']
    for p in data['poses']:
        size=' × '.join(f'{x:.3f}' for x in p['known_component_bbox']['size_mm'])
        lines.append(f"| {p['id']} | {p['q_deg']} | {size} | {p['all_8_moving_joint_limits_satisfied']} | {p['self_surface_check']['status']} |")
    lines += ['','仅评价已登记的三个候选；原stow自交负例保留在源JSON，未改名选用。筛查采用严格AABB分离、近区原始三角面裁剪和VTK FirstContact；AABB重叠不自动判碰撞。','',
              'accepted STL指/指、闭体包含和姿态间连续路径仍为UNKNOWN。已有名义BRep双指15 mm间隙3.8 mm单独引用，不替代accepted STL验证。','',
              '复现：`python pose_screen.py`；所有绝对极值、责任配对与来源hash见results/POSE_SCREEN.json。']
    (HERE/'POSE_SCREEN.md').write_text('\n'.join(lines),encoding='utf-8')

def main():
    start=time.monotonic();raw,sources=motion.read_triangles()
    ih=contract_input_hashes();rid=screen_run_id(ih);sd=snapshot_digest(ih)
    expected=expected_nonadjacent_pairs()
    deferred=[p for p in DEFERRED_PAIRS if frozenset(p) in {frozenset(x) for x in expected}]
    required=len(expected)-len(deferred)
    inputs=INPUT_FILES
    data={'schema':'WP03_BOUNDED_EXISTING_POSE_SCREEN_V2','status':'GEOMETRY_COMPLETE_SELF_SCREEN_PENDING','source_hashes':{str(p):sha(p) for p in inputs},'mesh_sources':sources,
          'self_screen_contract':{'run_id':rid,'snapshot_digest':sd,'expected_nonadjacent_pairs':[list(p) for p in expected],
                                  'explicit_unknown_pairs':[list(p) for p in deferred],'required_evaluated_pair_count':required,
                                  'input_sha256':ih,'configuration':{'poses':[p['id'] for p in POSES[2:]],'finger_mm':FINGER,'root_transform_mm':ROOT_T.tolist()}},
          'candidate_origin':'Existing WP01 list only; three uncompleted candidates, no new pose optimization','poses':[],
          'historical_rejected_pose':{'q_deg':[0,-15,-15,60,-30,0],'finger_mm':0,'source':'WP01 LAYOUT_COMPARISON.historical_trials','reason':'Recorded five nonadjacent surface intersection pairs; not used as feasible stow'},
          'nominal_finger_brep_evidence':{'source':'WP01 results/FINGER_INTERFACE_CHECK.json','gap_mm':3.7999999989137305,'applies_to':'Nominal BRep only, same15 mm relative finger state','accepted_stl_pair_status':'UNKNOWN'}}
    for pose in POSES:
        p=geometry(raw,pose)
        if pose['id'] in ('OPEN_PARKING_REFERENCE','SERVICE_WORK_REFERENCE'):
            old=OLD['self_intersection_by_pose']['stow' if pose['id']=='OPEN_PARKING_REFERENCE' else 'work']
            p['self_surface_check']={'status':'SOURCE_REFERENCE_35_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN','source':str(LAYOUT),'receipt':old,
                                     'scope':'Same accepted source, sameq and15 mm fingers; rigid base transform unchanged; no continuous/volume test inherited'}
        data['poses'].append(p);save(data)
        print(json.dumps({'event':'geometry','pose':p['id'],'q':p['q_deg'],'bbox':p['known_component_bbox'],'limits':p['all_8_moving_joint_limits_satisfied'],'fixture_hits':len(p['arm_fixture_surface_findings'])}),flush=True)
    del raw
    worker_rc=None;timed_out=False
    try:
        worker=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--self-worker'],capture_output=True,text=True,timeout=150)
        worker_rc=worker.returncode
        output=worker.stdout;error=worker.stderr[-2000:] if worker.returncode else None
    except subprocess.TimeoutExpired as exc:
        timed_out=True
        output=exc.stdout or '';output=output.decode('utf-8',errors='replace') if isinstance(output,bytes) else output
        error='BOUNDED150_SECOND_TIMEOUT_PARTIAL_ROWS_PRESERVED'
    partial={};completed={}
    for line in output.splitlines():
        try:event=json.loads(line)
        except json.JSONDecodeError:continue
        if event['event']=='pair':partial.setdefault(event['pose'],[]).append(event['record'])
        elif event['event']=='pose_complete':completed[event['pose']]=event
    for p in data['poses'][2:]:
        rows=partial.get(p['id'],[]);hits=[r for r in rows if r['surface_intersection']]
        checked=sum(r['surface_intersection'] is not None for r in rows)
        comp=completed.get(p['id'])
        completion_ok=(comp is not None and comp.get('completed') is True and comp.get('run_id')==rid
                       and comp.get('snapshot_digest')==sd and comp.get('expected_pair_count')==len(expected))
        if hits:status='EXPLICIT_SELF_SURFACE_INTERSECTION_REJECTED'
        elif not completion_ok or checked!=required or timed_out or worker_rc!=0:status='INCOMPLETE_UNKNOWN'
        else:status='NONADJACENT_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN'
        p['self_surface_check']={'status':status,'expected_nonadjacent_pairs':len(expected),'deferred_pairs':len(deferred),
                                 'required_evaluated_pairs':required,'evaluated_pairs':checked,'records':rows,'surface_intersection_pairs':hits,
                                 'worker_completed':completion_ok,'completion_event':({k:v for k,v in comp.items() if k!='rows'} if comp else None),
                                 'contains_status':'UNKNOWN'}
    data.update(status='BOUNDED_SCREEN_COMPLETE_NO_LAUNCH_STOW_CLAIM',self_worker_error=error,
                worker_returncode=worker_rc,worker_timed_out=timed_out,elapsed_seconds=time.monotonic()-start)
    save(data)
    print(json.dumps({'event':'complete','poses':[{'id':p['id'],'status':p['self_surface_check']['status']} for p in data['poses']],'elapsed_seconds':data['elapsed_seconds']}),flush=True)

if __name__=='__main__':self_worker() if '--self-worker' in sys.argv else main()
