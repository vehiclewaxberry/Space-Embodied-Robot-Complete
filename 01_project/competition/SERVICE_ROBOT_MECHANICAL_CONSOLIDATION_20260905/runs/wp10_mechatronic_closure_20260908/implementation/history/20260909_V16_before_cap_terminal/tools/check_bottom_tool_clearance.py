"""Nominal local tool envelopes; no full insertion trajectory or tolerance claim."""
from pathlib import Path
import json,hashlib,runpy,gc
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir,gp_Trsf
A=Path(__file__).resolve().parents[1];core=runpy.run_path(str(A/'tools/check_fixed_heat_geometry.py'))
read=core['read'];prop=core['prop'];common=core['common']
planpath=A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json';plan=json.loads(planpath.read_text());cfg=json.loads((A/'thermal/BOTTOM_RADIATOR_MOUNT.json').read_text())
bounds=json.loads((A/'thermal/RADIATOR_OBSTACLE_BOUNDS.json').read_text());assert bounds['source_plan_sha256']==hashlib.sha256(planpath.read_bytes()).hexdigest()
out=[]
def overlap(a,b):return all(min(a[i+3],b[i+3])-max(a[i],b[i])>1e-5 for i in range(3))
for state,st in plan['states'].items():
    br={r['id']:r for r in bounds['states'][state]};cache={}
    for i,(x,y) in enumerate(cfg['mount_centers_xy_mm']):
        axis=gp_Ax2(gp_Pnt(x,y,-97.65),gp_Dir(0,0,1));outer=BRepPrimAPI_MakeCylinder(axis,4,20).Shape();inner=BRepPrimAPI_MakeCylinder(axis,3.2,20).Shape();op=BRepAlgoAPI_Cut(outer,inner);op.Build();assert op.IsDone()
        driver=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,-134.15),gp_Dir(0,0,1)),2,20).Shape()
        for name,tool in [('NUT_OD8_ID6p4_20MM',op.Shape()),('OUTER_HEX_DRIVER_OD4_20MM',driver)]:
            tb=prop(tool)['bbox'];pairs=[]
            for r in st['rows']:
                bb=br[r['id']]['bbox_S_mm']
                if not overlap(tb,bb):continue
                if r['id'] not in cache:
                    path=Path(r['step_path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256'];s=read(path);M=r['T_S_step'];T=gp_Trsf();T.SetValues(*[float(M[j][k]) for j in range(3) for k in range(4)]);cache[r['id']]=BRepBuilderAPI_Transform(s,T,True).Shape()
                v=common(tool,cache[r['id']]);pairs.append(dict(id=r['id'],common_volume_mm3=v))
            out.append(dict(state=state,mount=i,tool=name,pairs=pairs,passed=all(abs(q['common_volume_mm3'])<1e-5 for q in pairs)))
    cache.clear();gc.collect()
res=dict(schema='WP10_BOTTOM_LOCAL_TOOL_ENVELOPE_CHECK_V1',source_plan_sha256=hashlib.sha256(planpath.read_bytes()).hexdigest(),tool_dimensions_basis='R01_OD8_ID6p4_nominal_socket; projectOD4_hex_driver_candidate',
 checks=out,checks_passed=all(r['passed'] for r in out),count=len(out),full_insertion_trajectory_checked=False,tool_vendor_and_tolerance_bound=False,assembly_sequence='Fit bottom plate and six fasteners before equipment/adapter installation; local20mm windows also checked against static final assembly.')
(A/'results/BOTTOM_LOCAL_TOOL_CLEARANCE.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print(json.dumps(dict(count=len(out),passed=res['checks_passed'],failed=[r for r in out if not r['passed']])));assert res['checks_passed']
