from pathlib import Path
import json
import numpy as np
from scipy.integrate import dblquad
from scipy.stats import qmc
from thermal_ray_bvh import build_bvh,ray_first_hit
A=Path(__file__).resolve().parents[1]
tri=np.array([[[-50,-40,100],[50,-40,100],[50,40,100]],[[-50,-40,100],[50,40,100],[-50,40,100]]],float)
tree=build_bvh(tri,np.array([0,0],np.int32));u=qmc.Sobol(2,scramble=True,seed=317).random_base2(18)
r=np.sqrt(u[:,0]);phi=2*np.pi*u[:,1];directions=np.column_stack([r*np.cos(phi),r*np.sin(phi),np.sqrt(1-u[:,0])])
hit,_=ray_first_hit(np.zeros_like(directions),directions,*tree)
expected,_=dblquad(lambda y,x:100**2/(np.pi*(x*x+y*y+100**2)**2),-50,50,lambda _: -40,lambda _:40,epsabs=1e-10)
value=float(np.mean(hit>=0));h,d=ray_first_hit(np.array([[0,0,0],[100,100,0],[0,0,200]],float),np.array([[0,0,1],[0,0,1],[0,0,-1]],float),*tree)
checks=[dict(name='cosine_ray_vs_independent_area_integral',passed=abs(value-expected)<.001,ray_estimate=value,quadrature=expected),
  dict(name='centre_miss_and_reverse_side_hit',passed=h.tolist()==[0,-1,0]),
  dict(name='hit_distance100mm',passed=abs(d[0]-100)<1e-10 and abs(d[2]-100)<1e-10)]
for c in checks:c['passed']=bool(c['passed'])
assert all(c['passed'] for c in checks)
(A/'results/THERMAL_RAY_BVH_VERIFICATION.json').write_text(json.dumps(dict(checks=checks,checks_passed=True,numerical_method_only=True,spacecraft_geometry_verified=False),indent=2),encoding='utf-8')
print(json.dumps(checks))
