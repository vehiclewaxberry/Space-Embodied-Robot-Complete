"""Scoped OCC checks of WP03 non-arm geometry; no full source-arm repair claim."""
from pathlib import Path
import json,hashlib,itertools,time
import numpy as np
from spacecraft_model import build,HERE
from OCP.BRep import BRep_Tool

def check(state):
    _,shapes,receipt=build(state,include_arm=False)
    rows=receipt['instances'];valid=[];pairs=[];narrow=0;sep=0
    physical=[r for r in rows if r['representation_role']=='PHYSICAL_GEOMETRY']
    for r in physical:
        shape=shapes[r['id']]
        valid.append({'id':r['id'],'valid':shape.is_valid,'solid_count':len(shape.solids()),'positive_volumes':all(s.volume>0 for s in shape.solids()),'shells_closed':all(BRep_Tool.IsClosed_s(s.wrapped) for s in shape.shells())})
    for a,b in itertools.combinations(physical,2):
        amin=np.array(a['bounds']['min_mm']);amax=np.array(a['bounds']['max_mm']);bmin=np.array(b['bounds']['min_mm']);bmax=np.array(b['bounds']['max_mm'])
        overlap=np.minimum(amax,bmax)-np.maximum(amin,bmin)
        if np.any(overlap<1e-5):sep+=1;continue
        narrow+=1
        try:
            common=shapes[a['id']]&shapes[b['id']];v=sum(s.volume for s in common.solids()) if common is not None else 0
            if v>1e-5:pairs.append({'ids':[a['id'],b['id']],'common_volume_mm3':v,'status':'POSITIVE_MATERIAL_OVERLAP_REQUIRES_DISPOSITION','parents':[a['parent_assembly'],b['parent_assembly']]})
        except Exception as e:pairs.append({'ids':[a['id'],b['id']],'status':'BOOLEAN_ERROR','error':str(e)})
    return {'state':state,'physical_instance_count':len(physical),'validity':valid,'pair_count':len(physical)*(len(physical)-1)//2,'strict_or_boundary_AABB_excluded_pairs':sep,'Boolean_narrow_pairs':narrow,'positive_or_error_pairs':pairs,'scope':'All pairs of non-arm PHYSICAL_GEOMETRY only; simplified proxies and functional spaces excluded. No continuous motion, self-intersection or full imported arm check.'}

if __name__=='__main__':
    start=time.monotonic();checks=[]
    for state in ['parking','released','service']:
        r=check(state);checks.append(r);print(state,'physical',r['physical_instance_count'],'findings',len(r['positive_or_error_pairs']),flush=True)
    data={'status':'GEOMETRY_CHECK_WITH_EXPLICIT_FINDINGS_NOT_QUALIFICATION','checks':checks,'source_sha256':hashlib.sha256((HERE/'spacecraft_model.py').read_bytes()).hexdigest(),'dependency_sha256':{n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ['design_parameters.json','root_structure.py','wing_kinematics.py','kinematics.py']},'elapsed_s':time.monotonic()-start}
    (HERE/'results/GEOMETRY_CHECK.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
