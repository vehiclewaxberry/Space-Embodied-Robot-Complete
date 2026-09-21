"""Independent numerical diagnosis; reads source STEP, never changes CAD."""
from pathlib import Path
import hashlib,json,math
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
from OCP.gp import gp_GTrsf

D=Path(__file__).resolve().parents[2]
OUT=D/'results/reviewer'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def topo(s,k):
 e=TopExp_Explorer(s,k);ss=[]
 while e.More():ss.append(e.Current());e.Next()
 return ss
def bbox(s):
 b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b,False,False);v=b.Get();return [list(v[:3]),list(v[3:])]
def load(r):
 assert sha(r['step_path'])==r['source_sha256'];s=STEPControl_Reader();assert s.ReadFile(r['step_path'])==IFSelect_RetDone
 assert s.TransferRoots()>0;return s.OneShape()
def board(s):
 for i,a in enumerate(topo(s,TopAbs_SOLID)):
  b=np.array(bbox(a))
  if max(abs(b[0,:2]-[0,-80]))<1e-5 and max(abs(b[1,:2]-[100,0]))<1e-5:return i,a
 raise ValueError('missing board')
def volume(s,method='default',eps=None):
 p=GProp_GProps();err=None
 if method=='default':BRepGProp.VolumeProperties_s(s,p)
 elif method=='adaptive':err=BRepGProp.VolumeProperties_s(s,p,Eps=eps,OnlyClosed=True,SkipShared=False)
 else:err=BRepGProp.VolumePropertiesGK_s(s,p,Eps=eps,OnlyClosed=True,IsUseSpan=True,CGFlag=False,IFlag=False,SkipShared=False)
 return {'volume_mm3':abs(p.Mass()),'estimated_relative_error':err}
def scale_z(s,z):
 g=gp_GTrsf();g.SetValue(3,3,z);return BRepBuilderAPI_GTransform(s,g,True).Shape()
def diff(a,b):
 q=BRepAlgoAPI_Cut(a,b);q.Build();assert q.IsDone();s=q.Shape();assert BRepCheck_Analyzer(s).IsValid()
 return dict(solids=len(topo(s,TopAbs_SOLID)),faces=len(topo(s,TopAbs_FACE)),**volume(s,'adaptive',1e-10))

c=json.loads((D/'inputs/MAIN_GEOMETRY_COVERAGE.json').read_text(encoding='utf8'))
oi,a=board(load(c['original_source_board']));ni,b=board(load(c['board']));factor=1.6/1.51
rows=[]
for meth,eps in [('default',None)]+[(meth,eps) for meth in ['adaptive','gk'] for eps in [1e-6,1e-9,1e-12]]:
 va=volume(a,meth,eps);vb=volume(b,meth,eps);ratio=vb['volume_mm3']/va['volume_mm3'];r=dict(method=meth,eps=eps,old=va,new=vb,ratio=ratio,expected_ratio=factor,ratio_error=ratio-factor,scaled_volume_error_mm3=vb['volume_mm3']-va['volume_mm3']*factor)
 rows.append(r);print(json.dumps(r),flush=True)
expected=scale_z(a,factor)
positive=dict(expected_minus_actual=diff(expected,b),actual_minus_expected=diff(b,expected))
print('SYMMETRIC',json.dumps(positive),flush=True)
negative={}
for name,z in [('unchanged_1p51',1.0),('wrong_1p61',1.61/1.51)]:
 s=scale_z(a,z);v=dict(candidate_minus_actual=diff(s,b),actual_minus_candidate=diff(b,s));v['rejected']=any(x['solids']>0 and x['volume_mm3']>1e-5 for x in v.values() if isinstance(x,dict));negative[name]=v
 print('NEGATIVE',name,json.dumps(v),flush=True)
strict=all(v['solids']==0 and v['faces']==0 and v['volume_mm3']==0 for v in positive.values())
hp=all(abs(r['ratio_error'])<1e-7 for r in rows if r['method']!='default')
passed=strict and hp and all(v['rejected'] for v in negative.values())
out=dict(schema='R6H_REVIEWER_BOARD_INTEGRATION_DIAGNOSIS_V1',status='PASS_CAUSE_ESTABLISHED' if passed else 'FAIL_UNRESOLVED',original_failed_report='GEOMETRY_REVIEW_ATTEMPT_01_FAILED_DEFAULT_VOLUME.json',original_failed_report_sha256=sha(OUT/'GEOMETRY_REVIEW_ATTEMPT_01_FAILED_DEFAULT_VOLUME.json'),old_board_index=oi,new_board_index=ni,old_bbox=bbox(a),new_bbox=bbox(b),integration_comparison=rows,independent_scaled_shape_symmetric_difference=positive,negative_controls=negative,source_locks={c[k]['step_path']:sha(c[k]['step_path']) for k in ['original_source_board','board']},pass_basis='Original 1e-7 ratio tolerance unchanged. Adaptive/GK integrations plus independently scaled shape must agree; both directed shape differences must contain no faces/solids. Wrong thickness controls must be rejected.',manufacturing_release=False)
(OUT/'BOARD_INTEGRATION_DIAGNOSIS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('RESULT',out['status'],flush=True)
raise SystemExit(0 if passed else 2)
