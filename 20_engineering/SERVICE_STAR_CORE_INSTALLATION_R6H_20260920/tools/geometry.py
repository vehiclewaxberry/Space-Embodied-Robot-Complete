"""Horizontal R6H branch, using immutable R4 host and R6 local component sources."""
from pathlib import Path
import importlib.util, json, numpy as np
D=Path(__file__).resolve().parents[1];ROOT=D.parents[1]
R6=D.parent/'SERVICE_STAR_CORE_INSTALLATION_R6_20260920'
sp=importlib.util.spec_from_file_location('r6_source_geometry',R6/'tools/geometry.py')
c=importlib.util.module_from_spec(sp);sp.loader.exec_module(c)
R4,R5,E,IMPL=c.R4,c.R5,c.E,c.IMPL
g=c.g;read,write,sha,load,moved=c.read,c.write,c.sha,c.load,c.moved
box,cyl,cut,union,common,distance=c.box,c.cyl,c.cut,c.union,c.common,c.distance
compound,source,world_bounds,candidates,state_rows=c.compound,c.source,c.world_bounds,c.candidates,c.state_rows
I=np.eye(4).tolist()
for p in ['inputs','results','cad','native','views','docs/hardware']:(D/p).mkdir(exist_ok=True,parents=True)
def emit(ident,s,role,**kw):
    p=D/'cad'/(ident+'.step');fact=g.dump(s,p)
    return dict(id=ident,step_path=str(p),source_sha256=fact['sha256'],native_path=str(D/'native'/(ident+'.SLDPRT')),T_S_local=I,
      expected_solids=fact['solids'],expected_sheets=0,expected_volume_mm3=fact['volume_mm3'],expected_local_bbox_mm={'min_mm':fact['bounds_mm'][0],'max_mm':fact['bounds_mm'][1]},representation_role=role,**kw)
