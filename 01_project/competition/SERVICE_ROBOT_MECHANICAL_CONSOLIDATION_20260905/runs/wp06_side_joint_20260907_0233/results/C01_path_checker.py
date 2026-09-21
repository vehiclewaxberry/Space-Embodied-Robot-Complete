"""Independent actual-STEP checks of frozen nominal installation envelopes.
No producer generator is imported. Continuous axial sweeps are conservative
coaxial cylinders/rings with catalogue containment checked independently.
"""
from pathlib import Path
import json,sys,math,hashlib,datetime
R=Path(__file__).resolve().parents[1]
from verify_joint_geometry import Geometry,sha,write
local=json.loads((R/'results/LOCAL_PARTS.json').read_text())
context=json.loads((R/'inputs/CONTEXT.json').read_text())
job={'parts':local['parts'].copy(),'tolerances':{'linear_mm':1e-5,'volume_mm3':1e-5,'integration_eps':1e-9}}
g=Geometry(job,{})
from build123d import Solid,Plane,export_step,Location
shapes={};fact_cache={}
def shape(k):
    if k not in shapes:shapes[k]=g.load(k)
    return shapes[k]
def facts(k):
    if k not in fact_cache:fact_cache[k]=g.facts(shape(k))
    return fact_cache[k]
def bound_dist(a,b):
    aa=a.bounding_box();bb=b.bounding_box()
    al,ah,bl,bh=map(list,[aa.min,aa.max,bb.min,bb.max])
    return math.sqrt(sum(max(al[i]-bh[i],bl[i]-ah[i],0)**2 for i in range(3)))
result={'status':'RUNNING','generated_local':datetime.datetime.now().astimezone().isoformat(),'tests':[],
    'inputs':{str(p):sha(p) for p in [Path(__file__),R/'results/LOCAL_PARTS.json',R/'inputs/CONTEXT.json',R/'CAD_BRIEF.md']},
    'scope':'Frozen nominal dimensions; continuous straight axial envelopes only; no helical thread/real hand tool or manufacturing qualification',
    'stage08_present':{},'stage08_absent':{},'thread_representation_exceptions':[]}
outfile=R/'results/PATH_AND_STATIC_CHECKS.json'
def save():
    from collections import Counter
    result['counts']=dict(Counter(x['status'] for x in result['tests']));write(outfile,result)
def record(id,a,b,minimum=0):
    lower=bound_dist(a,b)
    if lower>max(minimum,1e-5):
        q=dict(status='PASS',method='ACTUAL_BREP_AABB_SEPARATION_LOWER_BOUND',minimum_distance_lower_bound_mm=lower,intersection_volume_mm3=0)
    else:
        q=g.separation(a,b)
        q={k:v for k,v in q.items() if k not in ['a_facts','b_facts']}
        q.update(status='PASS' if q['intersection_volume_mm3']<=1e-5 and q['minimum_distance_mm']+1e-5>=minimum else 'FAIL',method='ACTUAL_BREP_DISTANCE_AND_COMMON')
    q.update(id=id,required_minimum_mm=minimum);result['tests'].append(q)
    return q
def cylinder(s,z,r,lo,hi):return Solid.make_cylinder(r,hi-lo,Plane(origin=(146,s*lo,z),x_dir=(1,0,0),z_dir=(0,s,0)))
def ring(s,z,ro,ri,lo,hi):return cylinder(s,z,ro,lo,hi)-cylinder(s,z,ri,lo-1,hi+1)
def keyrole(k):return k.rsplit('_',2)[0].removeprefix('WP06_')
changed=context['changed_ids'];hardware=[k for k in local['parts'] if k.startswith('WP06_')]
for state,rows in context['states'].items():
    others={k:shape(k) for k in changed}
    for row in rows:
        k=state+':'+row['id'];job['parts'][k]=row;others[k]=shape(k)
    for k in hardware:
        for other,b in others.items():record('static:'+state+':'+k+'->'+other,shape(k),b)
    save()
for i,a in enumerate(hardware):
    for b in hardware[i+1:]:
        same=a.rsplit('_',2)[1:]==b.rsplit('_',2)[1:]
        if same and {keyrole(a),keyrole(b)}=={'screw','nut'}:
            result['thread_representation_exceptions'].append(dict(pair=[a,b],measured_overlap_mm3=g.volume(shape(a)&shape(b)),status='NOMINAL_M3_THREAD_PROXY_PAIR_ONLY_PHYSICAL_ENGAGEMENT_UNKNOWN'))
        else:record('hardware:'+a+'->'+b,shape(a),shape(b))
save()
present={k:shape(k) for k in changed}
for row in context['states']['service']:
    if row['parent_assembly'] in ['COVERS','SOLAR_WING','HOLDING_MOVING']:
        result['stage08_absent'][row['id']]=row['parent_assembly'];continue
    k='service:'+row['id'];present[k]=shape(k);result['stage08_present'][row['id']]=row['parent_assembly']
result['stage08_present'].update({k:'CHANGED_STRUCTURE' for k in changed})
sweepdir=R/'results/sweep_geometry';sweepdir.mkdir(exist_ok=True)
for s in [-1,1]:
    for z0 in [-94,94]:
        z=-93.5 if z0<0 else 94;suffix=f'{s}_{z0}'
        envelopes={
          'washer_outer':ring(s,z,3.5,1.6,109.15,129.65),
          'screw':cylinder(s,z,1.5,97.65,129.65).fuse(cylinder(s,z,2.75,109.65,132.65)),
          'washer_inner':ring(s,z,3.5,1.6,80.65,101.15),
          'nut':cylinder(s,z,3.175,78.25,100.65),
          'tool_inner':ring(s,z,4,3.2,50.65,100.65),
          'tool_outer':cylinder(s,z,1.25,111.15,156.15)}
        for role,env in envelopes.items():
            name=f'{role}_{suffix}';path=sweepdir/(name+'.step');export_step(env,path)
            # Re-read the saved envelope before measurement.
            job['parts']['sweep:'+name]={'path':str(path),'T_S_local':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],'sha256':sha(path)}
            env=shape('sweep:'+name)
            if not role.startswith('tool_'):
                missing=g.volume(shape('WP06_'+name)-env)
                result['tests'].append(dict(id='envelope_contains_catalogue_final:'+name,status='PASS' if missing<=1e-5 else 'FAIL',uncontained_volume_mm3=missing))
            # Own-joint installation order is explicit. Other joints are present.
            earlier={'washer_outer':[], 'screw':['washer_outer'], 'washer_inner':['washer_outer','screw'], 'nut':['washer_outer','screw','washer_inner'], 'tool_inner':['screw','washer_outer','washer_inner','nut'],'tool_outer':['screw','washer_outer','washer_inner','nut']}[role]
            obstacles=present.copy()
            for k in hardware:
                same=k.endswith('_'+suffix)
                if same and keyrole(k) not in earlier:continue
                if same and role=='nut' and keyrole(k)=='screw':
                    result['thread_representation_exceptions'].append(dict(pair=['sweep:'+name,k],status='NUT_THREADING_NOT_PROVEN_BY_AXIAL_PROXY'));continue
                obstacles[k]=shape(k)
            for other,b in obstacles.items():
                minimum=.5 if role=='tool_inner' and other.endswith('lower_equipment_deck') else .2 if role=='tool_inner' and other==f'lower_deck_angle_{s}_1' else 0
                record('path:'+name+'->'+other,env,b,minimum)
            save()
        record('tools_simultaneous:'+suffix,envelopes['tool_inner'],envelopes['tool_outer'])
result['actual_step_input_hashes']=g.snapshots
result['inputs_unchanged']=all(sha(p)==h for p,h in result['inputs'].items()) and all(sha(p)==h for p,h in g.snapshots.items())
result['status']='PASS_NOMINAL_ENVELOPES_AND_STATIC_SCOPE' if all(x['status']=='PASS' for x in result['tests']) and result['inputs_unchanged'] else 'FAIL_OR_INCOMPLETE'
save();print(json.dumps({'status':result['status'],'counts':result['counts'],'failures':[x for x in result['tests'] if x['status']!='PASS']}))
sys.exit(0 if result['status'].startswith('PASS') else 1)
