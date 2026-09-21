"""Bounded source-geometry evidence for the retained release entry conflict."""
from pathlib import Path
import json,math
from battery_variant_context import A,read,sha,baseline
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Trsf,gp_Pnt
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.TopAbs import TopAbs_IN
def load(r):
    assert sha(r['step_path'])==r['source_sha256'];q=STEPControl_Reader();assert int(q.ReadFile(r['step_path']))==1;q.TransferRoots();T=r['T_S_step'];t=gp_Trsf();t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)]);return BRepBuilderAPI_Transform(q.OneShape(),t,True).Shape()
def intersection(a,b):
    q=BRepAlgoAPI_Common(a,b);q.Build();assert q.IsDone();g=GProp_GProps();BRepGProp.VolumeProperties_s(q.Shape(),g);return float(g.Mass())
out=dict(schema='WP10_RETAINED_RELEASE_PORT_COUNTEREXAMPLE_V1',status='RUNNING',source_script_sha256=sha(__file__),source_plan='mechanical/FIXED_HEAT_INSTANCE_PLAN.json',source_plan_sha256=sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json'),endpoint_basis='WP03 unbound functional front-face allocation, not manufacturer pin',rows=[],global_path_impossibility_proved=False,new_route_pass=False,back_face_port_substitution_used=False)
for state in ['service','parking','released']:
    rows=baseline(state)
    for n,x in enumerate([-115,-40]):
        key=f'hold_fold_mast_{n}';r=rows[key];s=load(r);p=gp_Pnt(x,-110,149.15);v=BRepBuilderAPI_MakeVertex(p).Vertex();d=BRepExtrema_DistShapeShape(v,s);d.Perform();assert d.IsDone()
        samples=[]
        for sign in [-1,1]:
            point=(x+sign*(14-math.sqrt(14**2-2**2)),-108,149.15);q=BRepClass3d_SolidClassifier(s,gp_Pnt(*point),1e-7);samples.append(dict(point_S_mm=point,inside_mast=q.State()==TopAbs_IN))
        terminal=rows[f'release_power_data_route_{n}_1'];out['rows'].append(dict(state=state,station=n,endpoint_S_mm=[x,-110,149.15],mast_step=r['step_path'],mast_sha256=r['source_sha256'],T_S_step=r['T_S_step'],endpoint_center_distance_to_mast_mm=float(d.Value()),radius2_sphere_common_volume_mm3=intersection(BRepPrimAPI_MakeSphere(p,2).Shape(),s),old_terminal_segment_common_volume_mm3=intersection(load(terminal),s),old_terminal_sha256=terminal['source_sha256'],R14_side_approach_samples=samples))
park=[r for r in out['rows'] if r['state']=='parking'];assert len(park)==2 and all(abs(r['endpoint_center_distance_to_mast_mm']-1)<1e-6 for r in park);assert all(all(p['inside_mast'] for p in r['R14_side_approach_samples']) for r in park)
out.update(status='PARKING_LOCAL_RELEASE_ENTRY_GEOMETRY_COUNTEREXAMPLE_CONFIRMED',required_design_action='Redesign front entry/retention-mast interface with actual release-device connection and load path. Preserve both release functions; no new route or manufacturer interface credit from this diagnostic.',scope='Endpoint-center distance and specificR14 approach samples verified in currentSTEP; radius2 sphere is diagnostic, not a cable end or universal path proof.')
(A/'results/RELEASE_PORT_CLEARANCE_COUNTEREXAMPLE.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(status=out['status'],parking=park)))
