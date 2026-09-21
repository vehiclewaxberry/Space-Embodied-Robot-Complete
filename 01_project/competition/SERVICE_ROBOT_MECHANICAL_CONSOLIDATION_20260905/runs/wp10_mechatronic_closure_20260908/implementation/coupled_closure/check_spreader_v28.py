"""Native delta-volume validation against the unchanged three-state parent."""
from pathlib import Path
import hashlib,itertools,json,math
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common,BRepAlgoAPI_Cut
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Trsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID

HERE=Path(__file__).resolve().parent;A=HERE.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def step(path):
    r=STEPControl_Reader();assert int(r.ReadFile(str(path)))==1;r.TransferRoots();s=r.OneShape()
    assert BRepCheck_Analyzer(s).IsValid();return s
def volume(s):
    g=GProp_GProps();BRepGProp.VolumeProperties_s(s,g);return g.Mass()
def op(kind,a,b):
    q=kind(a,b);q.Build();assert q.IsDone();return q.Shape()
def transform(s,T):
    t=gp_Trsf();t.SetValues(*[v for row in T[:3] for v in row]);return BRepBuilderAPI_Transform(s,t,True).Shape()
def bbox(s):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b);return list(b.Get())

def run():
    dest=HERE/'SPREADER_GEOMETRY_V28.json';assert not dest.exists()
    p=read(HERE/'SPREADER_PARAMETERS_V28.json')
    assert all(sha(A/rel)==h for rel,h in p['source_lock'].items())
    baseline=step(A/'mechanical/bottom_radiator.step');new=step(HERE/'spreader_v28.step')
    added=op(BRepAlgoAPI_Cut,new,baseline);removed=op(BRepAlgoAPI_Cut,baseline,new)
    addv=volume(added);remv=volume(removed);bb=bbox(added)
    # Independent exact volume for this left-region design, excluding original
    # 58x62 seat, two 58x14 feet and the two internal radius4 support bosses.
    x0,y0,x1,y1=p['region_xy_mm']
    expected=(((x1-x0)*(y1-y0))-(58*62)-(2*58*14)-(2*math.pi*4**2))*p['height_mm']
    assert abs(addv-expected)<1e-3 and abs(remv)<1e-3
    ex=TopExp_Explorer(new,TopAbs_SOLID);n=0
    while ex.More():n+=1;ex.Next()
    assert n==1 and abs(volume(new)-volume(baseline)-addv)<1e-3
    parent=read(A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json')
    assert sha(A/parent['source_plan'])==parent['source_plan_sha256']
    cache={};sources={};states={}
    for state,rows in parent['states'].items():
        checked=[];deck_gap=None
        for r in rows:
            if r['id']==p['parent_instance_id']:continue
            b=r['bbox_S_mm'];hit=all(min(bb[i+3],b[i+3])-max(bb[i],b[i])>1e-6 for i in range(3))
            deck=r['id']=='lower_equipment_deck_B'
            angle=r['id'].startswith('lower_deck_angle_')
            if not hit and not deck and not angle:continue
            key=(r['source_sha256'],json.dumps(r['T_S_step']))
            if key not in cache:
                assert sha(r['step_path'])==r['source_sha256'];sources[r['step_path']]=r['source_sha256']
                host=transform(step(r['step_path']),r['T_S_step'])
                d=BRepExtrema_DistShapeShape(added,host);d.Perform();assert d.IsDone()
                v=volume(op(BRepAlgoAPI_Common,added,host)) if d.Value()<1e-7 else 0.
                cache[key]=dict(clearance_mm=d.Value(),common_volume_mm3=v)
            item=dict(id=r['id'],representation_role=r['representation_role'],**cache[key]);checked.append(item)
            if deck:deck_gap=item['clearance_mm']
        collisions=[r for r in checked if r['common_volume_mm3']>1e-3]
        states[state]=dict(checked=checked,new_volume_collisions=collisions,deck_gap_mm=deck_gap)
    out=dict(schema='WP10_V28_SPREADER_NATIVE_DELTA',script_sha256=sha(__file__),
        generator_sha256=sha(HERE/'spreader_v28.step.py'),parameter_sha256=sha(HERE/'SPREADER_PARAMETERS_V28.json'),
        baseline_step_sha256=sha(A/'mechanical/bottom_radiator.step'),new_step_sha256=sha(HERE/'spreader_v28.step'),
        source_plan_sha256=parent['source_plan_sha256'],source_lock=sources,
        solid_count=n,valid=True,new_volume_mm3=volume(new),baseline_volume_mm3=volume(baseline),
        added_volume_mm3=addv,removed_volume_mm3=remv,independent_added_volume_mm3=expected,
        added_mass_kg=addv*2700e-9,new_mass_kg=volume(new)*2700e-9,added_bbox_S_mm=bb,
        states=states,checks=dict(one_valid_solid=n==1,added_volume_analytic=abs(addv-expected)<1e-3,
            no_old_metal_removed=abs(remv)<1e-3,no_new_host_volume_collisions=all(not s['new_volume_collisions'] for s in states.values()),
            nominal_deck_gap_1p5=all(abs(s['deck_gap_mm']-1.5)<1e-5 for s in states.values()),
            side_angle_gap_at_least_1p5=all(r['clearance_mm']>=1.5-1e-5 for s in states.values()
                for r in s['checked'] if r['id'].startswith('lower_deck_angle_'))),
        whole_fit_verified=False,manufacturing_release=False,
        scope='Actual added metal versus current parent only; existing assembly contacts/defects retained. '
              'Mass uses project 2700kg/m3. No tolerance, load, fastener preload or thermal closure credit.')
    with dest.open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
    print(json.dumps(dict(checks=out['checks'],added_mass_kg=out['added_mass_kg'],
                         collisions={s:len(v['new_volume_collisions']) for s,v in states.items()})))
    assert all(out['checks'].values())

if __name__=='__main__':run()
