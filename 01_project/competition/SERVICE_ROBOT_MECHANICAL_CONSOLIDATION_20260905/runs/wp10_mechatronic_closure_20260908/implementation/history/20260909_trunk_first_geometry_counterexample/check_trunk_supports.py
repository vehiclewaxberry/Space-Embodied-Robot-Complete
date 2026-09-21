"""Exact current-source support interfaces, plate cut locality and retained negatives."""
import json,math,argparse,numpy as np
from battery_variant_context import A,read,sha,baseline
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common,BRepAlgoAPI_Cut,BRepAlgoAPI_Fuse
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Trsf,gp_Pnt,gp_Ax2,gp_Dir
def load(path,T):
    r=STEPControl_Reader();assert int(r.ReadFile(str(path)))==1;r.TransferRoots();t=gp_Trsf();t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)]);return BRepBuilderAPI_Transform(r.OneShape(),t,True).Shape()
def vol(s):
    g=GProp_GProps();BRepGProp.VolumeProperties_s(s,g);return float(g.Mass())
def op(cls,a,b):
    q=cls(a,b);q.Build();assert q.IsDone();return q.Shape()
def bb(s):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b);return list(b.Get())
def near(a,b,g=0):return all(a[i]<=b[i+3]+g+1e-7 and a[i+3]>=b[i]-g-1e-7 for i in range(3))
def exact(a,b):
    q=BRepExtrema_DistShapeShape(a,b);q.Perform();assert q.IsDone();d=float(q.Value());v=vol(op(BRepAlgoAPI_Common,a,b)) if d<1e-7 else 0.;assert math.isfinite(v);return dict(distance_mm=d,common_volume_mm3=v)
p=argparse.ArgumentParser();p.add_argument('--state',choices=['service','parking','released'],required=True);args=p.parse_args()
cfg=read('mechanical/TRUNK_SUPPORT_DESIGN.json');plan=read('mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json');oldp=read(cfg['parent_source_plan']);old={q['id']:q for q in oldp['states'][args.state]['rows']};sp=plan['states'][args.state];rows={q['id']:q for q in sp['rows']};changed=sp['changed_ids']+sp['added_ids'];cache={};hashes={}
assert all(sha(A/q)==h for q,h in plan['inputs'].items()) and plan['source_script_sha256']==sha(A/'tools/prepare_trunk_variant.py')
def shape(k):
    if k not in cache:
        r=rows[k];assert sha(r['step_path'])==r['source_sha256'];hashes[r['step_path']]=r['source_sha256'];cache[k]=load(r['step_path'],r['T_S_step'])
    return cache[k]
bounds={k:r['bbox_S_mm'] for k,r in baseline(args.state).items() if k in rows}
over=set(read('mechanical/BATTERY_BAY_LAYOUT.json')['source_overrides'])|set(read('mechanical/BATTERY_HARNESS_PASSAGE.json')['rows'])|set(oldp['states'][args.state]['changed_this_round'])|set(changed)|{'WP10_INTERNAL_BATTERY_BYPASS','WP10_RRC3570_4_D_MAX_ENVELOPE'}
for k in over:bounds[k]=bb(shape(k))
assert set(bounds)==set(rows)
allowed=set()
def allow(a,b):allowed.add(tuple(sorted([a,b])))
wire='WP10_INTERNAL_BATTERY_BYPASS';deck='upper_equipment_deck_B'
for i,s in enumerate(cfg['stations']):
    base='trunk_clip_standoff_'+s['previous_suffix'];cap='trunk_clip_'+s['previous_suffix'];lo=f'TRUNK_{i}_LINER_LOW';hi=f'TRUNK_{i}_LINER_HIGH'
    for a,b in [(base,cap),(base,lo),(cap,hi),(lo,hi),(wire,lo),(wire,hi),(base,deck)]:allow(a,b)
    for j in range(2):
        screw=f'TRUNK_{i}_SCREW_{j}';washer=f'TRUNK_{i}_WASHER_{j}';nut=f'TRUNK_{i}_NUT_{j}'
        for a,b in [(screw,cap),(screw,nut),(washer,nut),(washer,base if i==0 else deck)]:allow(a,b)
for j in range(2):
    for a,b in [(f'TRUNK_HIGH_FOOT_SCREW_{j}','trunk_clip_standoff_-140'),(f'TRUNK_HIGH_FOOT_SCREW_{j}',f'TRUNK_HIGH_FOOT_NUT_{j}'),(f'TRUNK_HIGH_FOOT_WASHER_{j}',f'TRUNK_HIGH_FOOT_NUT_{j}'),(f'TRUNK_HIGH_FOOT_WASHER_{j}',deck)]:allow(a,b)
inputs=['mechanical/TRUNK_SUPPORT_DESIGN.json','mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json',cfg['parent_source_plan'],'tools/battery_variant_context.py','mechanical/BATTERY_BAY_LAYOUT.json','mechanical/BATTERY_HARNESS_PASSAGE.json','thermal/RADIATOR_OBSTACLE_BOUNDS.json','mechanical/trunk_support_common.py']
out=dict(schema='WP10_TRUNK_SUPPORT_EXACT_V1',status='RUNNING',state=args.state,source_script_sha256=sha(__file__),inputs={q:sha(A/q) for q in inputs},source_plan_sha256=sha(A/'mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json'),changed_ids=changed,tests=[],battery_tests=[],plate_locality={},unchanged_source_pairs_not_rechecked=True,known_release_segments_retained=sp['known_pending_release_ids'],nominal_contact_pairs=[list(q) for q in sorted(allowed)],full_harness_verified=False,whole_design_complete=False)
def save():(A/f'results/TRUNK_SUPPORT_SCREEN_{args.state.upper()}.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
localcut={}
for name,src in cfg['modified_sources'].items():
    k=src['id'];previous=load(src['path'],src['T_S_step'])
    if name=='DECK':
        ts=[BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,-14),gp_Dir(0,0,1)),1.7,8).Shape() for x,y in cfg['deck_holes_xy_mm']];tool=ts[0]
        for t in ts[1:]:tool=op(BRepAlgoAPI_Fuse,tool,t)
    else:ts=[BRepPrimAPI_MakeBox(gp_Pnt(-126.5,-15.5,-12),33,9,8).Shape()];tool=ts[0]
    removed=op(BRepAlgoAPI_Cut,previous,shape(k));expected=op(BRepAlgoAPI_Common,previous,tool)
    r=dict(removed_mm3=vol(removed),added_mm3=vol(op(BRepAlgoAPI_Cut,shape(k),previous)),outside_cut_mm3=vol(op(BRepAlgoAPI_Cut,removed,expected)),missing_cut_mm3=vol(op(BRepAlgoAPI_Cut,expected,removed)))
    out['plate_locality'][k]=r;assert all(abs(r[n])<1e-6 for n in ['added_mm3','outside_cut_mm3','missing_cut_mm3']);localcut[k]=[bb(t) for t in ts]
save();seen=set();battery='WP10_RRC3570_4_D_MAX_ENVELOPE'
for k in changed:
    if near(bounds[k],bounds[battery],2):out['battery_tests'].append(dict(id=k,**exact(shape(k),shape(battery))))
    for j,r in rows.items():
        pair=tuple(sorted([k,j]))
        if k==j or pair in seen or r['is_ground_only']:continue
        seen.add(pair)
        if k in localcut and j not in changed and not any(near(bounds[j],b) for b in localcut[k]):continue
        if not near(bounds[k],bounds[j]):continue
        q=exact(shape(k),shape(j));out['tests'].append(dict(ids=list(pair),**q,nominal_contact_allowed=pair in allowed));save()
out['collisions']=[r for r in out['tests'] if r['common_volume_mm3']>1e-6]
out['unexpected_contacts']=[r for r in out['tests'] if r['distance_mm']<1e-7 and r['common_volume_mm3']<=1e-6 and not r['nominal_contact_allowed']]
out['battery_failures']=[r for r in out['battery_tests'] if r['distance_mm']<2-1e-7 or r['common_volume_mm3']>1e-6]
out.update(status='TRUNK_SUPPORT_GEOMETRY_COUNTEREXAMPLES' if any(out[k] for k in ['collisions','unexpected_contacts','battery_failures']) else 'TRUNK_SUPPORT_STATIC_GEOMETRY_CLEAR__MATERIAL_PRELOAD_AND_RELEASE_BRANCHES_OPEN',test_count=len(out['tests']),source_hashes=hashes,changed_bboxes={k:bounds[k] for k in changed},inputs_unchanged=all(sha(A/q)==h for q,h in out['inputs'].items()),sources_unchanged=all(sha(q)==h for q,h in hashes.items()))
assert out['inputs_unchanged'] and out['sources_unchanged'];save();print(json.dumps({k:out[k] for k in ['status','test_count','plate_locality','collisions','unexpected_contacts','battery_failures']}))
