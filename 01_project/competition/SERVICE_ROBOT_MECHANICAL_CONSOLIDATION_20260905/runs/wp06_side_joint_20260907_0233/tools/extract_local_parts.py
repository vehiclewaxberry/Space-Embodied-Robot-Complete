"""Split the actual generated STEP by labelled occurrences; no source geometry build."""
from pathlib import Path
import json,sys,hashlib
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'tools'))
from verify_joint_geometry import Geometry
job={'parts':{},'tolerances':{'linear_mm':1e-5,'volume_mm3':1e-5,'integration_eps':1e-9}}
g=Geometry(job,{})
from build123d import export_step
source=R/'candidate/wp06_side_joint.step'
tree=g.import_step(source)
outdir=R/'candidate/parts';outdir.mkdir(exist_ok=True)
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
parts={}
def visit(node):
    if getattr(node,'children',()):
        for c in node.children:visit(c)
    else:
        name=node.label
        assert name and name not in parts,name
        shape=type(node)(node.wrapped).located(node.global_location)
        path=outdir/(name+'.step');export_step(shape,path)
        parts[name]=dict(path=str(path),T_S_local=I,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),facts=g.facts(shape))
visit(tree)
assert len(parts)==53,len(parts)
result=dict(source_path=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),parts=parts,frame='S_mm_all_parts_identity',status='EXTRACTED_FROM_ACTUAL_ASSEMBLY')
(R/'results/LOCAL_PARTS.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
tests=[dict(id='facts:'+n,kind='facts',part=n) for n in parts]
for s in [-1,1]:
    for z0 in [-94,94]:
        z=-93.5 if z0<0 else 94
        suffix=f'{s}_{z0}'
        tests.extend([dict(id='screw_pillar:'+suffix,kind='clearance',a='WP06_screw_'+suffix,b='RB_pillar_'+str(2 if s<0 else 3),min_mm=.5),
                      dict(id='cross_screws:'+suffix,kind='clearance',a='WP06_screw_'+suffix,b=f'shear_rail_screw_{s}_150_{z0}',min_mm=.5)])
        for part,u,L in [(f'shear_web_{s}',100.15,4),(f'shear_clip_{s}_150_{z0}',102.15,8)]:
            tests.append(dict(id='axis_bore:'+part+':'+str(z0),kind='axis_bore',part=part,axis_point=[146,s*u,z],axis_dir=[0,s,0],diameter=3.4-2e-5,length=L))
        for part,offset,intervals in [(f'shear_web_{s}',2,[[101.15,103.15]]),(f'shear_clip_{s}_150_{z0}',2,[[103.15,109.15]]),('WP06_washer_outer_'+suffix,2,[[109.15,109.65]]),('WP06_washer_inner_'+suffix,2,[[100.65,101.15]]),('WP06_nut_'+suffix,2,[[98.25,100.65]])]:
            tests.append(dict(id='stack:'+part+':'+str(z0),kind='axis_line_intervals',part=part,point=[146+offset,0,z],dir=[0,s,0],t_min_mm=90,t_max_mm=115,expected_intervals_mm=intervals))
job.update(parts={k:{x:v[x] for x in ['path','T_S_local','sha256']} for k,v in parts.items()},tests=tests,output=str(R/'results/C01_GEOMETRY.json'))
(R/'inputs/c01_job.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
print('Actual assembly extracted',len(parts),'checks',len(tests))
