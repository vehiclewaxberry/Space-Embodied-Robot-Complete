from pathlib import Path
import json,math
R=Path(__file__).resolve().parents[1]
from verify_joint_geometry import Geometry,sha,write
from check_bearing_faces import contact_area
d=json.loads((R/'results/LOCAL_PARTS.json').read_text())
g=Geometry({'parts':d['parts'],'tolerances':{'linear_mm':1e-5,'volume_mm3':1e-5,'integration_eps':1e-9}},{})
out={'scope':'Actual planar contact area, nominal geometry only; contact stress and preload UNKNOWN','results':[],'inputs':{str(p):sha(p) for p in [Path(__file__),R/'tools/check_bearing_faces.py',R/'results/LOCAL_PARTS.json']}}
for s in [-1,1]:
    for z in [-94,94]:
        suf=f'{s}_{z}'
        pairs=[('WP06_washer_outer_'+suf,f'shear_clip_{s}_150_{z}',109.15,math.pi*(3.5**2-1.7**2)),
               (f'shear_clip_{s}_150_{z}',f'shear_web_{s}',103.15,1),
               (f'shear_web_{s}','WP06_washer_inner_'+suf,101.15,math.pi*(3.5**2-1.7**2)),
               ('WP06_washer_inner_'+suf,'WP06_nut_'+suf,100.65,1),
               ('WP06_screw_'+suf,'WP06_washer_outer_'+suf,109.65,1)]
        for a,b,offset,minimum in pairs:
            q=contact_area(g.load(a),g.load(b),(0,s,0),offset)
            q.update(pair=[a,b],minimum_geometric_contact_area_mm2=minimum,
                     check='PASS' if q['status']=='MEASURED' and q['contact_area_mm2']+1e-5>=minimum else 'FAIL_OR_INCOMPLETE')
            out['results'].append(q)
out['actual_step_sha256']=g.snapshots
out['inputs_unchanged']=all(sha(p)==h for p,h in {**out['inputs'],**g.snapshots}.items())
out['status']='PASS_NOMINAL_CONTACT_GEOMETRY' if all(x['check']=='PASS' for x in out['results']) and out['inputs_unchanged'] else 'FAIL_OR_INCOMPLETE'
write(R/'results/BEARING_CONTACTS.json',out)
print(json.dumps({'status':out['status'],'areas':[dict(pair=x['pair'],area=x['contact_area_mm2'],check=x['check'],detail=x['status']) for x in out['results']]}))
