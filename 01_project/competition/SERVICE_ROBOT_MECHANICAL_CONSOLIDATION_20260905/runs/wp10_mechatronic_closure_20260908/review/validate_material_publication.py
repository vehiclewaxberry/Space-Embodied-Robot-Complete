"""Independently bind the delivered inertia scope and recompute subset sums; no CAD calls."""
from pathlib import Path
import json,hashlib,math
import numpy as np
from datetime import datetime,timezone
D=Path(__file__).resolve().parents[1];M=D/'mechanical_inertia'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def ck(name,ok):
    checks.append({'id':name,'passed':bool(ok)});assert ok,name
def bound(r):
    p=Path(r['path']);p=p if p.is_absolute() else M/p
    ck('sha/'+str(p),p.is_file() and sha(p)==r['sha256'])
receipt=read(M/'MATERIAL_INERTIA_DELIVERY.json')
ck('exact_completed_scope',receipt['status']=='PASS_PARTIAL_MATERIAL_INERTIA_SUPPLEMENT__NO_COMPLETE_SPACECRAFT_MODEL')
ck('actual_coverage',receipt['instance_count']==receipt['target_instance_count']==306 and receipt['unique_source_count']==receipt['successful_unique_source_count']==237)
ck('no_failed_sources',not receipt['failed_unique_sources'] and not receipt['failed_checks'] and receipt['check_count']==receipt['checks_passed'])
ck('whole_model_unknown',receipt['whole_spacecraft_inertia_complete'] is False and receipt['whole_spacecraft_mass_kg'] is None and receipt['motion_tree_complete'] is False)
for r in receipt['outputs']+[receipt['source_packet'],receipt['source_jobs']]+receipt['worker_versions']:bound(r)
jobs=read(M/'SOURCE_JOBS.json');p=read(Path(receipt['source_packet']['path']));packet={r['id']:r for r in p['instances']}
source_hashes=set();ids=set()
for job in jobs['rows']:
    bound(job['source']);source_hashes.add(job['source']['sha256']);ids.update(job['instances'])
    g=read(M/'results'/f"G{job['index']:03d}.json")
    ck('source_read/'+str(job['index']),g['status']=='PASS_SOURCE_BREP_GEOMETRIC_INTEGRALS_AND_POSE_CHECKS' and g['source']==job['source'] and g['source_unchanged_after'] is True)
ck('job_count',len(jobs['rows'])==len(source_hashes)==237)
data=read(M/'MATERIAL_INERTIA_INSTANCES.json');rows=data['instances']
ck('instance_set',len(rows)==306 and len({r['id'] for r in rows})==306 and {r['id'] for r in rows}==ids)
ck('units',data['coordinate_and_units']['length']=='m' and data['coordinate_and_units']['mass']=='kg' and data['coordinate_and_units']['inertia']=='kg*m^2')
def physical(I):
    a=np.asarray(I,dtype=float)
    if a.shape!=(3,3) or not np.all(np.isfinite(a)):return False
    e=np.linalg.eigvalsh(a);tol=max(np.linalg.norm(a)*1e-9,1e-15)
    return np.max(np.abs(a-a.T))<=tol and e[0]>=-tol and e[2]<=e[0]+e[1]+tol
for row in rows:
    ck(row['id']+'/unmeasured',row['as_built_parameters'] is None)
    ck(row['id']+'/states',set(row['states'])=={'service','parking','released'})
    for state,r in row['states'].items():
        ck(row['id']+'/'+state+'/source_binding',r['source_geometry']==packet[row['id']]['geometry_by_state'][state]['source_step'] and r['source_geometry']['sha256'] in source_hashes)
        ck(row['id']+'/'+state+'/finite_physical_tensor',math.isfinite(r['mass_kg']) and r['mass_kg']>0 and np.asarray(r['COM_S_m']).shape==(3,) and np.all(np.isfinite(r['COM_S_m'])) and physical(r['inertia_about_instance_COM_expressed_S_kg_m2']))
states=read(M/'MATERIAL_MODEL_STATES.json')
for result in states['states']:
    st=result['state']; parts=[r['states'][st] for r in rows]
    mass=math.fsum(r['mass_kg'] for r in parts)
    com=np.array([math.fsum(r['mass_kg']*r['COM_S_m'][i] for r in parts)/mass for i in range(3)])
    tensors=[]
    for r in parts:
        offset=np.asarray(r['COM_S_m'])-com
        tensors.append(np.asarray(r['inertia_about_instance_COM_expressed_S_kg_m2'])+r['mass_kg']*(np.dot(offset,offset)*np.eye(3)-np.outer(offset,offset)))
    I=np.array([[math.fsum(x[i,j] for x in tensors) for j in range(3)] for i in range(3)])
    ck(st+'/aggregate_mass',abs(mass-result['partial_mass_kg'])<1e-12)
    ck(st+'/aggregate_COM',np.max(np.abs(com-np.asarray(result['partial_COM_S_m'])))<1e-12)
    ck(st+'/aggregate_I',np.max(np.abs(I-np.asarray(result['partial_inertia_about_partial_COM_S_kg_m2'])))<1e-12 and physical(I))
    ck(st+'/partial_scope',result['included_instance_count']==306 and result['whole_spacecraft'] is False)
ck('whole_aggregate_unknown',states['whole_spacecraft_mass_kg'] is None and states['whole_spacecraft_inertia_kg_m2'] is None and states['rigid_joint_tree_emitted'] is False)
out={'status':'PASS_EXACT_INERTIA_PUBLICATION_SCOPE_AND_INDEPENDENT_SUBSET_SUMS','utc':datetime.now(timezone.utc).isoformat(),'checks_passed':len(checks),'checks_total':len(checks),'checks':checks,'source_receipt':{'path':str(M/'MATERIAL_INERTIA_DELIVERY.json'),'sha256':sha(M/'MATERIAL_INERTIA_DELIVERY.json')},'instances':306,'unique_geometry_sources':237,'whole_spacecraft_model_complete':False,'new_CAD_or_simulation_executed':False,'checker_sha256':sha(Path(__file__))}
(D/'review/MATERIAL_PUBLICATION_CHECK.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='checks'},ensure_ascii=False))
