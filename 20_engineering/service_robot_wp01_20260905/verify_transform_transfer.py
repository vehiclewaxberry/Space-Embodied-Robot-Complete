from pathlib import Path
import sys,json
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
import numpy as np
from service_robot_common import P,loc
from kinematics import tf,fk
root=tf([*P['root_xy_mm'],P['bus_mm'][2]/2+P['m3r_B_thickness_mm']])
rows=[]
for state,p in P['states'].items():
    for name,t in fk(p['q_deg'],root,p['finger_mm']).items():
        a=loc(t).wrapped.Transformation();matrix=np.array([[a.Value(i,j) for j in range(1,5)] for i in range(1,4)])
        rows.append(dict(state=state,link=name,max_abs_error=float(np.max(np.abs(matrix-t[:3,:4])))))
out=dict(method='gp_Trsf.SetValues from homogeneous matrix, no Euler intermediate',count=len(rows),max_abs_error=max(r['max_abs_error'] for r in rows),tolerance=1e-12,all_pass=all(r['max_abs_error']<=1e-12 for r in rows),rows=rows,historical_error='Earlier snapshot used extrinsic xyz angles with intrinsic XYZ CAD constructor; replaced before final delivery. Earlier STEP/GLB/views are superseded.')
(Path(__file__).parent/'results/TRANSFORM_TRANSFER.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in out.items() if k!='rows'}))
