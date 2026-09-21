"""Local outward driver envelopes; folded side access is an expected blockage."""
from pathlib import Path
import json,runpy,hashlib,gc,re
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir,gp_Trsf
A=Path(__file__).resolve().parents[1];core=runpy.run_path(str(A/'tools/check_bottom_tool_clearance.py'))
read=core['read'];prop=core['prop'];common=core['common'];plan=core['plan'];cfg=core['cfg'];bounds=core['bounds'];overlap=core['overlap'];c=cfg['chb_path'];out=[]
tools=[];x,y=c['center_xy_mm']
for i,(dx,dy) in enumerate(( (dx,dy) for dx in c['oem_hole_x_offsets_mm'] for dy in c['oem_hole_y_offsets_mm'])):
    tools.append(dict(id=f'CHB_{i}',family='BOTTOM_CHB',origin=[x+dx,y+dy,cfg['outer_z_mm']],direction=[0,0,-1]))
for side in [-1,1]:
    for i,(x,z) in enumerate(c['wall_screw_centers_xz_mm']):tools.append(dict(id=f'SIDE_{side}_{i}',family='SIDE_COLD',origin=[x,side*113.15,z],direction=[0,side,0]))
for state,st in plan['states'].items():
    br={r['id']:r for r in bounds['states'][state]};cache={}
    for spec in tools:
        tool=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*spec['origin']),gp_Dir(*spec['direction'])),2,20).Shape();tb=prop(tool)['bbox'];pairs=[]
        for r in st['rows']:
            if not overlap(tb,br[r['id']]['bbox_S_mm']):continue
            if r['id'] not in cache:
                path=Path(r['step_path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256'];M=r['T_S_step'];T=gp_Trsf();T.SetValues(*[float(M[j][k]) for j in range(3) for k in range(4)]);cache[r['id']]=BRepBuilderAPI_Transform(read(path),T,True).Shape()
            v=common(tool,cache[r['id']]);pairs.append(dict(id=r['id'],common_volume_mm3=v))
        positives=[r for r in pairs if r['common_volume_mm3']>1e-5];required=state=='service' or spec['family']=='BOTTOM_CHB'
        expected_wing_parts=lambda key:key.startswith('wing_') or bool(re.fullmatch(r'PV\d+_S\d+_C\d+_(CIC|BOND)',key))
        out.append(dict(state=state,tool=spec,intersections=positives,required_at_this_state=required,status='BLOCKED' if positives else 'LOCAL_WINDOW_CLEAR',criterion_satisfied=not positives if required else bool(positives) and all(expected_wing_parts(r['id']) for r in positives)))
    cache.clear();gc.collect()
r=dict(schema='WP10_COLD_PATH_LOCAL_TOOL_ACCESS_V1',source_plan_sha256=hashlib.sha256((A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json').read_bytes()).hexdigest(),checks=out,checks_passed=all(x['criterion_satisfied'] for x in out),count=len(out),local_clear=sum(x['status']=='LOCAL_WINDOW_CLEAR' for x in out),folded_side_blockages=sum(x['status']=='BLOCKED' for x in out),nominal_driver_diameter_mm=4,local_length_mm=20,full_insertion_path_verified=False,actual_tool_tolerance_bound=False,assembly_sequence='Install outward wall screws with both solar wings deployed; no folded-state access credit. Install CHB/bottom before PCB and wiring.')
(A/'results/COLD_PATH_TOOL_ACCESS.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(dict(checks_passed=r['checks_passed'],clear=r['local_clear'],blocked=r['folded_side_blockages'],failed=[x for x in out if not x['criterion_satisfied']])));assert r['checks_passed']
