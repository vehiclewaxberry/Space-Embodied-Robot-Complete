"""Narrow phase for the new continuous bundle against the same-source layout."""
from pathlib import Path
import hashlib,json,math
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common,BRepAlgoAPI_Cut
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Trsf,gp_Pnt,gp_Ax2,gp_Dir
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
c=read('mechanical/BATTERY_BAY_LAYOUT.json');p=read(c['source_plan']);s=read('results/BATTERY_RELAYOUT_SEED_SCREEN.json');b=read('thermal/RADIATOR_OBSTACLE_BOUNDS.json');route=read('mechanical/BATTERY_INTERNAL_ROUTE.json')
assert s['status']=='BODY_AND_MOVED_GROUPS_SCREEN_CLEAR__MOUNT_AND_REROUTE_PENDING'
inputs={q:sha(A/q) for q in ['mechanical/BATTERY_BAY_LAYOUT.json',c['source_plan'],'results/BATTERY_RELAYOUT_SEED_SCREEN.json','thermal/RADIATOR_OBSTACLE_BOUNDS.json','mechanical/BATTERY_INTERNAL_ROUTE.json','mechanical/battery_internal_route.step.py','mechanical/battery_internal_route.step','mechanical/heat_layout_relocation.py']}
assert all(inputs[q]==h for q,h in s['input_sha256'].items())
assert all(sha(A/q)==h for q,h in s['source_override_sha256'].items())
passage=read('mechanical/BATTERY_HARNESS_PASSAGE.json');assert passage['source_plan_sha256']==c['source_plan_sha256']
inputs.update({q:sha(A/q) for q in ['mechanical/BATTERY_HARNESS_PASSAGE.json','mechanical/battery_passage_common.py',*passage['rows'].values()]})
rows={r['id']:r for r in p['states']['service']['rows']};bounds={r['id']:r for r in b['states']['service']};moves={}
for g in c['rigid_group_moves']:
    ids=g.get('ids') or [k for k in rows if k.startswith(g['id_prefix'])]
    R=np.array(g['rotation_S']);D=np.eye(4);D[:3,:3]=R;D[:3,3]=np.array(g['to_center_S_mm'])-R@np.array(g['from_center_S_mm'])
    for k in ids:moves[k]=D
def transformed_bbox(box,M):
    bb=np.array(box).reshape(2,3);corners=np.array([[x,y,z,1] for x in bb[:,0] for y in bb[:,1] for z in bb[:,2]])@M.T
    return np.r_[corners[:,:3].min(0),corners[:,:3].max(0)]
world={k:transformed_bbox(v['bbox_S_mm'],moves.get(k,np.eye(4))) for k,v in bounds.items()}
def loadstep(path,M=np.eye(4)):
    r=STEPControl_Reader();assert int(r.ReadFile(str(path)))==1;r.TransferRoots();shape=r.OneShape();t=gp_Trsf();t.SetValues(*[float(M[i,j]) for i in range(3) for j in range(4)])
    return BRepBuilderAPI_Transform(shape,t,True).Shape()
def exact(a,b):
    d=BRepExtrema_DistShapeShape(a,b);d.Perform();assert d.IsDone();dist=float(d.Value());vol=0.
    if dist<1e-7:
        common=BRepAlgoAPI_Common(a,b);common.Build();assert common.IsDone();g=GProp_GProps();BRepGProp.VolumeProperties_s(common.Shape(),g);vol=float(g.Mass());assert math.isfinite(vol)
    return dict(distance_mm=dist,common_volume_mm3=vol)
def boolean_shape(op,a,b):
    q=op(a,b);q.Build();assert q.IsDone();return q.Shape()
def volume(shape):
    g=GProp_GProps();BRepGProp.VolumeProperties_s(shape,g);return float(g.Mass())
shape=loadstep(A/'mechanical/battery_internal_route.step');box=Bnd_Box();BRepBndLib.AddOptimal_s(shape,box);routebox=np.array(box.Get())
lo=np.array(c['battery']['min_S_mm']);battery=BRepPrimAPI_MakeBox(gp_Pnt(*lo),*c['battery']['size_S_mm']).Shape();batterycheck=exact(shape,battery)
out=dict(schema='WP10_BATTERY_INTERNAL_ROUTE_EXACT_V1',status='RUNNING',source_script_sha256=sha(__file__),input_sha256=inputs,source_override_sha256=s['source_override_sha256'],state='service',route_bbox_S_mm=routebox.tolist(),battery=batterycheck,tests=[],source_hashes={},omitted_pending_redesign=s['reroute_or_rework_required_ids'],branch_junctions_pending=route['branch_join_ids_requiring_junction_design'],whole_assembly_released=False,endpoint_binding=False,clamps_reworked=False)
out['passage_edits']=[]
out.update(branch_fit_proved=False,full_harness_geometry_status='OPEN_RELEASE_BRANCH_OVERLAPS_AND_PENDING_CLAMPS',branch_exempted_intersections=[],branch_existing_geometry_tests=[])
join_lo=np.array([60,-85,113]);join_size=[10,10,10];join_box=BRepPrimAPI_MakeBox(gp_Pnt(*join_lo),*join_size).Shape()
out['pending_functional_join_region_S_mm']=[*join_lo.tolist(),*(join_lo+join_size).tolist()]
cx,cy=passage['center_xy_mm'];cz0,cz1=passage['cut_z_mm'];tool=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(cx,cy,cz0),gp_Dir(0,0,1)),passage['diameter_mm']/2,cz1-cz0).Shape()
for key,path in passage['rows'].items():
    r=rows[key];assert sha(r['step_path'])==r['source_sha256']
    old=loadstep(r['step_path'],np.array(r['T_S_step']));new=loadstep(A/path)
    cut=BRepAlgoAPI_Cut(new,old);cut.Build();assert cut.IsDone();g=GProp_GProps();BRepGProp.VolumeProperties_s(cut.Shape(),g);added=float(g.Mass());assert abs(added)<=1e-6
    cut=BRepAlgoAPI_Cut(old,new);cut.Build();assert cut.IsDone();g=GProp_GProps();BRepGProp.VolumeProperties_s(cut.Shape(),g);removed=float(g.Mass());assert removed>0
    actual_removed=cut.Shape();expected_removed=boolean_shape(BRepAlgoAPI_Common,old,tool)
    outside_cut=volume(boolean_shape(BRepAlgoAPI_Cut,actual_removed,expected_removed));missing_cut=volume(boolean_shape(BRepAlgoAPI_Cut,expected_removed,actual_removed))
    assert abs(outside_cut)<=1e-6 and abs(missing_cut)<=1e-6,(key,outside_cut,missing_cut)
    analytic_removed=math.pi*(passage['diameter_mm']/2)**2*6
    assert abs(removed-analytic_removed)<=1e-6,(key,removed,analytic_removed)
    box=Bnd_Box();BRepBndLib.AddOptimal_s(new,box);nb=np.array(box.Get());assert np.all(nb[:3]>=world[key][:3]-1e-6) and np.all(nb[3:]<=world[key][3:]+1e-6)
    out['passage_edits'].append(dict(id=key,baseline_step=r['step_path'],baseline_sha256=r['source_sha256'],step_path=path,sha256=sha(A/path),coordinate_basis='S_WORLD_MM',added_volume_mm3=added,removed_volume_mm3=removed,analytic_removed_volume_mm3=analytic_removed,outside_specified_cut_removed_mm3=outside_cut,missing_specified_cut_mm3=missing_cut,contained_in_parent_bbox=True,clearance=exact(shape,new),strength_verified=False,liner_installed=False))
def save():(A/'results/BATTERY_INTERNAL_ROUTE_SCREEN.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
save()
for key,bb in world.items():
    if bounds[key]['is_ground_only'] or key in out['omitted_pending_redesign']:continue
    if not(np.all(bb[:3]<=routebox[3:]+2.0000001) and np.all(bb[3:]>=routebox[:3]-2.0000001)):continue
    r=rows[key];override=c['source_overrides'].get(key);pp=passage['rows'].get(key);path=A/pp if pp else (A/override['step_path'] if override else Path(r['step_path']));h=sha(path)
    assert h==(inputs[pp] if pp else (s['source_override_sha256'][override['step_path']] if override else r['source_sha256']))
    out['source_hashes'][str(path)]=h
    M=np.eye(4) if override or pp else moves.get(key,np.eye(4))@np.array(r['T_S_step'])
    target=loadstep(path,M);result=exact(shape,target);pending=key in out['branch_junctions_pending'];exempt=False
    if pending and result['distance_mm']<1e-7:
        common=BRepAlgoAPI_Common(shape,target);common.Build();assert common.IsDone()
        cb=Bnd_Box();BRepBndLib.AddOptimal_s(common.Shape(),cb);box=np.array(cb.Get())
        exempt=bool(np.all(box[:3]>=join_lo-1e-7) and np.all(box[3:]<=join_lo+join_size+1e-7))
        out['branch_exempted_intersections'].append(dict(id=key,**result,common_bbox_S_mm=box.tolist(),contained_in_pending_join_region=exempt,physical_join_verified=False))
    out['tests'].append(dict(id=key,**result,branch_junction_pending=pending,contact_local_to_pending_join=exempt));save()
branch_shapes={k:loadstep(rows[k]['step_path'],np.array(rows[k]['T_S_step'])) for k in out['branch_junctions_pending']}
branch_keys=list(branch_shapes);out['known_branch_overlap']=dict(ids=branch_keys,**exact(branch_shapes[branch_keys[0]],branch_shapes[branch_keys[1]]),source_nominal_collinear_overlap_length_mm=105,physical_shared_bundle_or_splitter_verified=False)
for key,branch in branch_shapes.items():
    for host,path in passage['rows'].items():out['branch_existing_geometry_tests'].append(dict(ids=[key,host],**exact(branch,loadstep(A/path)),branch_redesign_required=True))
collisions=[r for r in out['tests'] if r['common_volume_mm3']>1e-6 and not r['contact_local_to_pending_join']]
touches=[r for r in out['tests'] if r['distance_mm']<1e-7 and r['common_volume_mm3']<=1e-6 and not r['contact_local_to_pending_join']]
out.update(status='ROUTE_HAS_GEOMETRY_COUNTEREXAMPLES' if collisions or touches or batterycheck['distance_mm']<2-1e-7 else 'ROUTE_BODY_SCREEN_CLEAR__CLAMPS_AND_JUNCTIONS_PENDING',collisions=collisions,unexpected_touches=touches,nearby_within_2mm=[r for r in out['tests'] if r['distance_mm']<2],test_count=len(out['tests']),source_hashes_unchanged=all(sha(q)==h for q,h in out['source_hashes'].items()),inputs_unchanged=all(sha(A/q)==h for q,h in inputs.items()))
assert out['source_hashes_unchanged'] and out['inputs_unchanged'];save();print(json.dumps({k:out[k] for k in ['status','battery','test_count','collisions','unexpected_touches','nearby_within_2mm']}))
