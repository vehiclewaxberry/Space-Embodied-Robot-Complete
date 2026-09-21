"""Actual STEP screening of a sourced battery outer envelope and rigid group moves.

This is an active counterexample search, not full mounting/harness qualification.
"""
from pathlib import Path
import json,hashlib,math,time,gc
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common,BRepAlgoAPI_Cut
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Trsf,gp_Pnt
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
cfg=read('mechanical/BATTERY_BAY_LAYOUT.json');plan=read(cfg['source_plan']);bounds=read('thermal/RADIATOR_OBSTACLE_BOUNDS.json')
assert cfg['source_plan_sha256']==bounds['source_plan_sha256']==sha(A/cfg['source_plan'])
rows={r['id']:r for r in plan['states']['service']['rows']};bb={r['id']:r for r in bounds['states']['service']}
assert set(rows)==set(bb)
matrices={};groups={}
for group in cfg['rigid_group_moves']:
    ids=group.get('ids') or [x for x in rows if x.startswith(group['id_prefix'])]
    assert ids and all(x in rows for x in ids)
    R=np.array(group['rotation_S'],float);assert np.max(np.abs(R.T@R-np.eye(3)))<1e-12 and abs(np.linalg.det(R)-1)<1e-12
    t=np.array(group['to_center_S_mm'])-R@np.array(group['from_center_S_mm']);M=np.eye(4);M[:3,:3]=R;M[:3,3]=t
    for key in ids:assert key not in matrices;matrices[key]=M;groups[key]=group['group']
reroute=set(cfg['mandatory_reroute_ids'])|{k for k in rows if any(k.startswith(p) for p in cfg['mandatory_rework_id_prefixes'])}
assert reroute.isdisjoint(matrices)
assert all(r['step_path'] and r['source_sha256'] for r in rows.values())
hashed={}
for r in rows.values():
    if r['step_path'] not in hashed:hashed[r['step_path']]=sha(r['step_path'])
    assert hashed[r['step_path']]==r['source_sha256']
def move_bounds(bounds,M):
    b=np.array(bounds).reshape(2,3);corners=np.array([[x,y,z,1] for x in b[:,0] for y in b[:,1] for z in b[:,2]])@M.T
    return np.r_[corners[:,:3].min(0),corners[:,:3].max(0)]
world={k:move_bounds(q['bbox_S_mm'],matrices.get(k,np.eye(4))) for k,q in bb.items()}
cache={}
overrides=cfg.get('source_overrides',{})
override_hashes={}
for key,q in overrides.items():
    assert q['coordinate_basis']==('S_WORLD_MM_AFTER_GROUP_MOVE' if key in matrices else 'S_WORLD_MM')
    path=A/q['step_path'];override_hashes[q['step_path']]=sha(path)
def shape(key):
    if key not in cache:
        r=rows[key];q=overrides.get(key);path=str(A/q['step_path']) if q else r['step_path']
        rr=STEPControl_Reader();assert int(rr.ReadFile(path))==1;rr.TransferRoots();s=rr.OneShape();M=np.eye(4) if q else matrices.get(key,np.eye(4))@np.array(r['T_S_step']);t=gp_Trsf();t.SetValues(*[float(M[i,j]) for i in range(3) for j in range(4)]);cache[key]=BRepBuilderAPI_Transform(s,t,True).Shape()
    return cache[key]
old_cache={}
def baseline_shape(key):
    if key not in old_cache:
        r=rows[key];rr=STEPControl_Reader();assert int(rr.ReadFile(r['step_path']))==1;rr.TransferRoots();s=rr.OneShape();M=matrices.get(key,np.eye(4))@np.array(r['T_S_step']);t=gp_Trsf();t.SetValues(*[float(M[i,j]) for i in range(3) for j in range(4)]);old_cache[key]=BRepBuilderAPI_Transform(s,t,True).Shape()
    return old_cache[key]
override_bbox_checks=[]
for key,q in overrides.items():
    box=Bnd_Box();BRepBndLib.AddOptimal_s(shape(key),box);actual=np.array(box.Get());old=world[key]
    assert np.all(actual[:3]>=old[:3]-1e-6) and np.all(actual[3:]<=old[3:]+1e-6),(key,actual,old)
    added_volume=None
    if q['only_material_removed']:
        cut=BRepAlgoAPI_Cut(shape(key),baseline_shape(key));cut.Build();assert cut.IsDone();prop=GProp_GProps();BRepGProp.VolumeProperties_s(cut.Shape(),prop);added_volume=float(prop.Mass());assert abs(added_volume)<=1e-6,(key,added_volume)
    override_bbox_checks.append(dict(id=key,actual_world_bbox_mm=actual.tolist(),contained_in_parent_world_bbox=True,only_material_removed=q['only_material_removed'],added_volume_vs_correctly_moved_source_mm3=added_volume))
lo=np.array(cfg['battery']['min_S_mm']);hi=lo+np.array(cfg['battery']['size_S_mm']);gap=cfg['battery']['minimum_nominal_body_clearance_mm'];battery=BRepPrimAPI_MakeBox(gp_Pnt(*lo),*cfg['battery']['size_S_mm']).Shape()
def exact(a,b):
    d=BRepExtrema_DistShapeShape(a,b);d.Perform();assert d.IsDone();dist=float(d.Value())
    volume=0.
    if dist<1e-7:
        c=BRepAlgoAPI_Common(a,b);c.Build();assert c.IsDone();g=GProp_GProps();BRepGProp.VolumeProperties_s(c.Shape(),g);volume=float(g.Mass());assert math.isfinite(volume)
    return dict(distance_mm=dist,common_volume_mm3=volume)
def nearby(b1,b2,gap):return np.all(b1[:3]<b2[3:]+gap+1e-7) and np.all(b1[3:]>b2[:3]-gap-1e-7)
out=dict(schema='WP10_BATTERY_RELAYOUT_SEED_EXACT_SCREEN_V1',status='RUNNING',source_script_sha256=sha(__file__),
 input_sha256={p:sha(A/p) for p in ['mechanical/BATTERY_BAY_LAYOUT.json',cfg['source_plan'],'thermal/RADIATOR_OBSTACLE_BOUNDS.json']},
 state='service',retained_rows=len(rows),battery_tests=[],moved_group_tests=[],reroute_or_rework_required_ids=sorted(reroute),
 moved_ids=groups,geometry_removed_from_candidate=False,whole_candidate_changed=False,full_fit_proved=False,
 source_override_sha256=override_hashes,
 source_override_bbox_checks=override_bbox_checks,
 interpretations=['Battery solid is the D-maximum rectangular envelope, not a manufacturer BRep/contact geometry.',
 'Reroute/clip IDs are explicitly pending redesign, not cleared or deleted.',
 'Zero-distance retained source interfaces need separate contact semantics; only positive-volume intersections are new collision counterexamples.',
 'This screen does not prove force retention, insertion, pins, temperature, tolerance or all motion states.'])
def save():(A/'results/BATTERY_RELAYOUT_SEED_SCREEN.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
save()
for key,b in world.items():
    if bb[key]['is_ground_only'] or key in reroute:continue
    if nearby(b,np.r_[lo,hi],gap):
        r=exact(battery,shape(key));out['battery_tests'].append(dict(id=key,**r,body_gap_pass=r['distance_mm']>=gap-1e-7 and r['common_volume_mm3']<=1e-6));save()
checked=set()
for key in matrices:
    for other,b in world.items():
        pair=tuple(sorted([key,other]))
        if key==other or pair in checked or bb[other]['is_ground_only'] or other in reroute:continue
        if key in groups and other in groups and groups[key]==groups[other]:continue # rigid intra-group geometry unchanged
        checked.add(pair)
        if nearby(world[key],b,0):
            r=exact(shape(key),shape(other));out['moved_group_tests'].append(dict(ids=list(pair),**r,positive_volume_collision=r['common_volume_mm3']>1e-6));save()
# Added wall supports can also meet untouched components. Check those pairs
# against their same-source predecessor, preserving old contact semantics.
out['host_override_vs_untouched_tests']=[];host_pairs=set()
for key,q in overrides.items():
    if q['only_material_removed']:continue # actual zero-added-volume verified above
    for other,b in world.items():
        pair=tuple(sorted([key,other]))
        if other==key or other in matrices or other in reroute or bb[other]['is_ground_only'] or pair in host_pairs:continue
        host_pairs.add(pair)
        if nearby(world[key],b,0):
            after=exact(shape(key),shape(other));before=exact(baseline_shape(key),baseline_shape(other))
            out['host_override_vs_untouched_tests'].append(dict(ids=list(pair),before=before,after=after,new_positive_volume=after['common_volume_mm3']>before['common_volume_mm3']+1e-6,new_zero_contact=after['distance_mm']<1e-7 and before['distance_mm']>1e-6));save()
bad=[r for r in out['battery_tests'] if not r['body_gap_pass']];collisions=[r for r in out['moved_group_tests'] if r['positive_volume_collision']]
allowed={tuple(sorted([key,'upper_equipment_deck_B'])) for key in ['adapter_arm_drive','adapter_compute_communications',*[f'P60_HOST_{i}_{suffix}' for i in range(4) for suffix in ['POST','BW']]]}
allowed.add(tuple(sorted(['adapter_navigation_electronics','shear_web_1'])))
unexpected=[r for r in out['moved_group_tests'] if r['distance_mm']<1e-7 and tuple(r['ids']) not in allowed and not r['positive_volume_collision']]
host_new=[r for r in out['host_override_vs_untouched_tests'] if r['new_positive_volume'] or r['new_zero_contact']]
out.update(status='CANDIDATE_HAS_GEOMETRY_COUNTEREXAMPLES' if bad or collisions or unexpected or host_new else 'BODY_AND_MOVED_GROUPS_SCREEN_CLEAR__MOUNT_AND_REROUTE_PENDING',
 battery_gap_failures=bad,moved_group_collisions=collisions,unique_STEPs_loaded=len(cache),source_hashes_checked=len(hashed),
 unexpected_zero_contacts=unexpected,new_host_override_counterexamples=host_new,nominal_support_contacts_allowed=[list(x) for x in sorted(allowed)],
 all_step_sources_unchanged=all(sha(p)==h for p,h in hashed.items()),all_override_sources_unchanged=all(sha(A/p)==h for p,h in override_hashes.items()))
assert out['all_step_sources_unchanged'] and out['all_override_sources_unchanged'];save();print(json.dumps(dict(status=out['status'],battery_tests=len(out['battery_tests']),moved_group_tests=len(out['moved_group_tests']),gap_failures=bad,collisions=collisions,unexpected_zero_contacts=unexpected)))
