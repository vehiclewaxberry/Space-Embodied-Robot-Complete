"""Independent OCC comparison of actual saved SolidWorks STEP re-export."""
from pathlib import Path
import json,sys
R=Path(__file__).resolve().parents[1]
from verify_joint_geometry import Geometry,sha,write
native=json.loads((R/'results/NATIVE_EXECUTION_V2.json').read_text())
assert native['status']=='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY',native['status']
data=json.loads((R/'results/LOCAL_PARTS.json').read_text())
source=R/'native/WP06_SIDE_JOINT_C02_ROUNDTRIP.step'
g=Geometry({'parts':data['parts'],'tolerances':{'linear_mm':1e-5,'volume_mm3':1e-5,'integration_eps':1e-9}},{})
tree=g.import_step(source);leaves=[]
def visit(n):
    if getattr(n,'children',()):
        for c in n.children:visit(c)
    else:
        shape=type(n)(n.wrapped).located(n.global_location)
        leaves.append(dict(label=n.label,shape=shape,facts=g.facts(shape)))
visit(tree)
out={'status':'RUNNING','actual_native_step':str(source),'native_step_sha256':sha(source),'leaf_count':len(leaves),'expected_count':len(data['parts']),'results':[],
     'inputs':{str(p):sha(p) for p in [Path(__file__),R/'results/NATIVE_EXECUTION_V2.json',R/'results/LOCAL_PARTS.json',R/'native/WP06_SIDE_JOINT_C02.SLDASM']},
     'scope':'Actual native STEP material and placement preservation; no engineering qualification'}
used=set()
for name,item in data['parts'].items():
    a=g.load(name);af=g.facts(a);matches=[]
    for i,row in enumerate(leaves):
        if i in used:continue
        bf=row['facts']
        err=max(abs(af['bbox_mm'][k][j]-bf['bbox_mm'][k][j]) for k in ['min_mm','max_mm'] for j in range(3))
        if err<=1e-5 and af['solid_count']==bf['solid_count'] and abs(af['volume_mm3']-bf['volume_mm3'])<=1e-4:matches.append((i,err))
    r={'id':name,'status':'INCOMPLETE','bbox_volume_candidates':len(matches)}
    for i,err in matches:
        b=leaves[i]['shape'];delta=g.volume(a-b)+g.volume(b-a)
        if delta<=1e-5:
            used.add(i);r.update(status='PASS',native_label=leaves[i]['label'],native_leaf_index=i,bbox_max_error_mm=err,symmetric_material_difference_mm3=delta,volume_difference_mm3=abs(af['volume_mm3']-leaves[i]['facts']['volume_mm3']),source_sha256=item['sha256']);break
        r.setdefault('rejected',[]).append(dict(index=i,symmetric_material_difference_mm3=delta))
    out['results'].append(r);write(R/'results/NATIVE_ROUNDTRIP_CHECK.json',out)
out['used_native_leaves']=len(used)
out['actual_source_sha256']=g.snapshots
out['inputs_unchanged']=all(sha(p)==h for p,h in {**out['inputs'],**g.snapshots,str(source):out['native_step_sha256']}.items())
out['status']='PASS_53_ACTUAL_NATIVE_MATERIAL_AND_POSE' if len(leaves)==len(used)==len(data['parts'])==53 and all(x['status']=='PASS' for x in out['results']) and out['inputs_unchanged'] else 'FAIL_OR_INCOMPLETE'
write(R/'results/NATIVE_ROUNDTRIP_CHECK.json',out);print(json.dumps({'status':out['status'],'count':len(out['results']),'failures':[x for x in out['results'] if x['status']!='PASS']}));sys.exit(0 if out['status'].startswith('PASS') else 1)
