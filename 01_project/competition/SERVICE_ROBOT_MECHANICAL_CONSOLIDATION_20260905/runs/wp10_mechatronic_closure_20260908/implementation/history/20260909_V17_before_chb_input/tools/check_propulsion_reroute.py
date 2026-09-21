"""Exact changed-neighborhood checks; no full harness or hardware release."""
from pathlib import Path
import json,hashlib,math,argparse
import numpy as np
from battery_variant_context import A,read,sha,baseline,propulsion_variant
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
def loadstep(path,T):
    r=STEPControl_Reader();assert int(r.ReadFile(str(path)))==1;r.TransferRoots();t=gp_Trsf();t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)]);return BRepBuilderAPI_Transform(r.OneShape(),t,True).Shape()
def vol(s):
    g=GProp_GProps();BRepGProp.VolumeProperties_s(s,g);return float(g.Mass())
def op(cls,a,b):
    q=cls(a,b);q.Build();assert q.IsDone();return q.Shape()
def bbox(s):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b);return list(b.Get())
def exact(a,b):
    q=BRepExtrema_DistShapeShape(a,b);q.Perform();assert q.IsDone();d=float(q.Value());v=vol(op(BRepAlgoAPI_Common,a,b)) if d<1e-7 else 0.;assert math.isfinite(v);return dict(distance_mm=d,common_volume_mm3=v)
def nearby(a,b,gap=0):return all(a[i]<=b[i+3]+gap+1e-7 and a[i+3]>=b[i]-gap-1e-7 for i in range(3))
ap=argparse.ArgumentParser();ap.add_argument('--state',choices=['service','parking','released'],default='service');args=ap.parse_args()
rows,changed=propulsion_variant(args.state);old=baseline(args.state);cache={};hashed={}
def shape(k):
    if k not in cache:
        r=rows[k];h=sha(r['step_path']);assert h==r['source_sha256'];hashed[r['step_path']]=h;cache[k]=loadstep(r['step_path'],r['T_S_step'])
    return cache[k]
for k in changed:rows[k]['bbox_S_mm']=bbox(shape(k))
cfg=read('mechanical/BATTERY_BAY_LAYOUT.json');d=read('mechanical/BATTERY_PROPULSION_ROUTING.json')['dual_clamp'];lo=cfg['battery']['min_S_mm'];size=cfg['battery']['size_S_mm'];batt=BRepPrimAPI_MakeBox(gp_Pnt(*lo),*size).Shape();battbox=[*lo,*[x+y for x,y in zip(lo,size)]]
# Old internal segments are replaced by the V8 continuous route; old8 trunk
# supports remain explicitly pending and are not silently deleted from design.
pending=[k for k in rows if k.startswith(('trunk_clip_','trunk_clip_standoff_'))]
old_internal={f'internal_harness_proxy_{n}' for n in range(3)}
newpath=A/'mechanical/battery_internal_route.step';rows['WP10_INTERNAL_BATTERY_BYPASS']=dict(id='WP10_INTERNAL_BATTERY_BYPASS',step_path=str(newpath),source_sha256=sha(newpath),T_S_step=np.eye(4).tolist(),is_ground_only=False);rows['WP10_INTERNAL_BATTERY_BYPASS']['bbox_S_mm']=bbox(shape('WP10_INTERNAL_BATTERY_BYPASS'))
allowed={tuple(sorted(['CLAMP_DUAL_BASE','CLAMP_DUAL_LID']))}
for n in range(2):
    for a,b in [(f'POST_DUAL_{n}','upper_equipment_deck_B'),(f'POST_DUAL_{n}','CLAMP_DUAL_BASE'),(f'CLAMP_DUAL_{n}_BW','upper_equipment_deck_B'),(f'CLAMP_DUAL_{n}_TW','CLAMP_DUAL_LID'),(f'CLAMP_DUAL_{n}_TW',f'CLAMP_DUAL_{n}_TN'),(f'CLAMP_DUAL_{n}_BW',f'CLAMP_DUAL_{n}_BN'),(f'TIEROD_DUAL_{n}',f'CLAMP_DUAL_{n}_TN'),(f'TIEROD_DUAL_{n}',f'CLAMP_DUAL_{n}_BN')]:allowed.add(tuple(sorted([a,b])))
paths=['mechanical/BATTERY_PROPULSION_ROUTING.json','mechanical/BATTERY_BAY_LAYOUT.json','mechanical/BATTERY_HARNESS_PASSAGE.json','mechanical/FIXED_HEAT_INSTANCE_PLAN.json','thermal/RADIATOR_OBSTACLE_BOUNDS.json','results/BATTERY_RELAYOUT_SEED_SCREEN.json','mechanical/battery_propulsion_common.py','mechanical/heat_layout_relocation.py','tools/battery_variant_context.py']
out=dict(schema='WP10_PROPULSION_BATTERY_REROUTE_EXACT_V1',status='RUNNING',source_script_sha256=sha(__file__),input_sha256={q:sha(A/q) for q in paths},changed_ids=changed,state=args.state,tests=[],battery_tests=[],nominal_support_contacts_allowed=[list(p) for p in sorted(allowed)],pending_trunk_support_ids=pending,old_internal_segments_replaced_by='WP10_INTERNAL_BATTERY_BYPASS',all_electrical_endpoints_bound=False,full_harness_release=False)
def save():
    text=json.dumps(out,indent=2);(A/f'results/BATTERY_PROPULSION_ROUTE_SCREEN_{args.state.upper()}.json').write_text(text,encoding='utf-8')
    if args.state=='service':(A/'results/BATTERY_PROPULSION_ROUTE_SCREEN.json').write_text(text,encoding='utf-8')
# Verify exact localized two-hole removal; any extra cut is a failure.
deck=shape('upper_equipment_deck_B');previous=loadstep(old['upper_equipment_deck_B']['step_path'],old['upper_equipment_deck_B']['T_S_step']);cutters=[]
for x,y in d['stud_xy_mm']:cutters.append(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,-14),gp_Dir(0,0,1)),d['clearance_bore_diameter_mm']/2,8).Shape())
tool=op(BRepAlgoAPI_Fuse,*cutters);removed=op(BRepAlgoAPI_Cut,previous,deck);expected=op(BRepAlgoAPI_Common,previous,tool)
out['deck_locality']=dict(added_mm3=vol(op(BRepAlgoAPI_Cut,deck,previous)),removed_mm3=vol(removed),outside_cut_mm3=vol(op(BRepAlgoAPI_Cut,removed,expected)),missing_cut_mm3=vol(op(BRepAlgoAPI_Cut,expected,removed)))
assert all(abs(out['deck_locality'][q])<1e-6 for q in ['added_mm3','outside_cut_mm3','missing_cut_mm3']);save()
seen=set()
for key in changed:
    if nearby(rows[key]['bbox_S_mm'],battbox,2):out['battery_tests'].append(dict(id=key,**exact(shape(key),batt)))
    for other,r in rows.items():
        pair=tuple(sorted([key,other]))
        if other==key or pair in seen or other in pending or other in old_internal or r['is_ground_only']:continue
        seen.add(pair)
        if key=='upper_equipment_deck_B' and other not in changed:
            # Zero-added-volume cannot create collision. Contact changes are
            # confined to specified cut cylinders, checked locally below.
            if not any(nearby(r['bbox_S_mm'],bbox(q)) for q in cutters):continue
        if not nearby(rows[key]['bbox_S_mm'],r['bbox_S_mm'],0):continue
        q=exact(shape(key),shape(other));out['tests'].append(dict(ids=list(pair),**q,nominal_contact_allowed=pair in allowed));save()
out['collisions']=[q for q in out['tests'] if q['common_volume_mm3']>1e-6]
out['unexpected_contacts']=[q for q in out['tests'] if q['distance_mm']<1e-7 and q['common_volume_mm3']<=1e-6 and not q['nominal_contact_allowed']]
out['battery_failures']=[q for q in out['battery_tests'] if q['distance_mm']<2-1e-7 or q['common_volume_mm3']>1e-6]
out['critical_clearances']=[dict(ids=[a,b],**exact(shape(a),shape(b))) for a,b in [('PROP_PWR_ROUTE','PROP_DATA_ROUTE'),('PROP_PWR_ROUTE','equipment_navigation_electronics'),('PROP_DATA_ROUTE','equipment_navigation_electronics'),('CLAMP_DUAL_BASE','equipment_navigation_electronics'),('CLAMP_DUAL_LID','equipment_navigation_electronics'),('PROP_PWR_ROUTE','CLAMP_PWR_BASE'),('PROP_PWR_ROUTE','CLAMP_DUAL_BASE'),('PROP_DATA_ROUTE','CLAMP_DUAL_BASE')]]
assert all(q['distance_mm']>1e-7 and q['common_volume_mm3']<=1e-6 for q in out['critical_clearances'])
out.update(status='GEOMETRY_COUNTEREXAMPLES' if any(out[q] for q in ['collisions','unexpected_contacts','battery_failures']) else 'PROP_ROUTES_AND_DUAL_SUPPORT_GEOMETRY_CLEAR__ELECTRICAL_AND_OTHER_HARNESS_OPEN',test_count=len(out['tests']),source_hashes=hashed,source_hashes_unchanged=all(sha(p)==h for p,h in hashed.items()),inputs_unchanged=all(sha(A/p)==h for p,h in out['input_sha256'].items()),actual_changed_bboxes={k:rows[k]['bbox_S_mm'] for k in changed})
assert out['source_hashes_unchanged'] and out['inputs_unchanged'];save();print(json.dumps({k:out[k] for k in ['status','test_count','collisions','unexpected_contacts','battery_failures','deck_locality']}))
