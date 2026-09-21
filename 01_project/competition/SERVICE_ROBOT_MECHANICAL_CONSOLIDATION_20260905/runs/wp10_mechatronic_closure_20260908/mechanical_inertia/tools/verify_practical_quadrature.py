"""Independent analytic fixtures for the practical default/adaptive face method."""
from pathlib import Path
import json,math,hashlib
import numpy as np
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeCylinder
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Pnt
M=Path(__file__).resolve().parents[1]
tests=[]
for name,shape,V,C,I in [
    ('offset_box',BRepPrimAPI_MakeBox(gp_Pnt(11,22,33),10,20,30).Shape(),6000,np.array([16,32,48]),np.diag([650000,500000,250000])),
    ('cylinder',BRepPrimAPI_MakeCylinder(5,20).Shape(),math.pi*500,np.array([0,0,10]),np.diag([math.pi*500*475/12,math.pi*500*475/12,math.pi*500*25/2]))]:
    for eps in [None,1e-7,1e-9]:
        p=GProp_GProps();err=None
        if eps is None:BRepGProp.VolumeProperties_s(shape,p)
        else:err=BRepGProp.VolumeProperties_s(shape,p,eps,True,False)
        c=p.CentreOfMass();im=p.MatrixOfInertia();obs=np.array([[im.Value(i,j) for j in range(1,4)] for i in range(1,4)])
        norm=float(np.linalg.norm(obs-I,'fro'));tol=1e-5*float(np.linalg.norm(I,'fro'))+1e-4
        ok=abs(p.Mass()-V)<1e-7 and np.max(np.abs(np.array([c.X(),c.Y(),c.Z()])-C))<1e-8 and norm<=tol
        tests.append({'id':name+'_'+str(eps),'passed':bool(ok),'volume_mm3':p.Mass(),'analytic_volume_mm3':V,
            'inertia_COM_mm5':obs.tolist(),'analytic_inertia_COM_mm5':I.tolist(),
            'inertia_difference_Frobenius_mm5':norm,'screen_tolerance_mm5':tol,
            'returned_volume_relative_error_estimate':err,'inertia_strict_error_bound':None})
out={'status':'PASS_PRACTICAL_QUADRATURE_ANALYTICAL_FIXTURES' if all(t['passed'] for t in tests) else 'FAILED',
    'tests':tests,'pass_count':sum(t['passed'] for t in tests),'test_count':len(tests),
    'relative_inertia_screen':1e-5,'absolute_inertia_screen_mm5':1e-4,
    'scope':'Independent analytic box/cylinder screening; volume error estimate is not a bound on inertia; no claims for all shapes.',
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(M/'results/PRACTICAL_QUADRATURE_ANALYTICAL_FIXTURES.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:out[k] for k in ['status','pass_count','test_count']}))
assert all(t['passed'] for t in tests)
