"""Independent STEP round-trip geometry and saved partial native chain audit; no COM."""
from pathlib import Path
import hashlib,json
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepCheck import BRepCheck_Analyzer
D=Path(__file__).resolve().parents[2];locks={};checks=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lock(p):
 k=str(Path(p).resolve());h=sha(p);assert k not in locks or locks[k]==h;locks[k]=h;return h
def read(p):lock(p);return json.loads(Path(p).read_text(encoding='utf8'))
def ck(n,v,d=None):checks.append(dict(name=n,passed=bool(v),detail=d))
def topo(s,k):
 a=[];e=TopExp_Explorer(s,k)
 while e.More():a.append(e.Current());e.Next()
 return a
def load(p):
 lock(p);q=STEPControl_Reader();assert q.ReadFile(str(p))==IFSelect_RetDone;assert q.TransferRoots()>0;s=q.OneShape();assert BRepCheck_Analyzer(s).IsValid();return topo(s,TopAbs_SOLID)
def bbox(s):
 b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b,False,False);return np.array(b.Get())
def empty_cut(a,b):
 q=BRepAlgoAPI_Cut(a,b);q.Build();assert q.IsDone();s=q.Shape();assert BRepCheck_Analyzer(s).IsValid();return dict(solids=len(topo(s,TopAbs_SOLID)),faces=len(topo(s,TopAbs_FACE)))
build=read(D/'results/NATIVE_ASSEMBLY_DELIVERY.json');resume=read(D/'results/NATIVE_SERVICE_TOP_RESUME.json');plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json')
ck('partial_build_failure_preserved',build['status']=='FAILED_CLOSED' and '512 MiB' in build['error'])
ck('resume_links_partial_build',resume['resumed_from_sha256']==sha(D/'results/NATIVE_ASSEMBLY_DELIVERY.json') and resume['resumed_from_status']=='FAILED_CLOSED')
ck('both_plan_locks',build['plan_sha256']==resume['plan_sha256']==sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json'))
ck('27_native_parts',len(build['parts'])==27)
for r in build['parts']:
 ck('saved_native_SHA:'+r['id'],lock(r['target'])==r['native_save']['sha256'])
 ck('input_STEP_SHA:'+r['id'],lock(r['source'])==r['source_sha256'])
 c=r['part_cold_reopen'];ck('part_cold_reopen:'+r['id'],r['status']=='NATIVE_PART_SAVED_CLOSED_REOPENED_VERIFIED_AND_CLOSED' and c['errors']==0 and c['warnings']==0 and c['facts']['solid_count']==r['expected_solids'] and c['facts']['sheet_count']==0)
ck('four_rebuilt_groups',len(build['groups'])==4)
for g in build['groups']:
 ck('group_file_SHA:'+g['id'],lock(g['saved']['path'])==g['saved']['sha256'])
 ck('group_cold_status:'+g['id'],g['cold_errors']==g['cold_warnings']==g['needs_rebuild2']==0)
s=resume['service'];ck('native_top_SHA',lock(s['saved']['path'])==s['saved']['sha256'])
ck('top_cold_status',resume['status']=='PASS_R6H_SERVICE_TOP_RESUMED_AND_COLD_VERIFIED' and s['cold_errors']==s['cold_warnings']==s['needs_rebuild2']==0 and s['direct_children']==15)
for k in ['geometry_changed','poses_changed','STOP_installed','AUX_installed','electrical_connections_completed','whole_design_complete','ready_to_power','flight_ready']:ck('resume_scope:'+k,resume[k] is False)
main=next(p for p in build['parts'] if p['id']=='R6H_MAIN_PCBA_INSTALLED');rt=main['geometric_roundtrip']
ck('roundtrip_source_binding',rt['source_sha256']==lock(main['source']) and rt['native_sha256']==lock(main['target']) and rt['roundtrip_sha256']==lock(rt['roundtrip_path']))
a=load(main['source']);b=load(rt['roundtrip_path']);ck('40_roundtrip_bodies',len(a)==len(b)==40);available=set(range(len(b)));bodyrows=[]
for i,s in enumerate(a):
 ba=bbox(s);j=min(available,key=lambda k:float(np.max(np.abs(ba-bbox(b[k])))));err=float(np.max(np.abs(ba-bbox(b[j]))));available.remove(j)
 x=empty_cut(s,b[j]);y=empty_cut(b[j],s);r=dict(source_body=i,roundtrip_body=j,bbox_error_mm=err,source_minus_roundtrip=x,roundtrip_minus_source=y);bodyrows.append(r)
 ck('body:'+str(i),err<1e-4 and x['solids']==x['faces']==y['solids']==y['faces']==0,r)
 print('BODY',i,err,x,y,flush=True)
mat=next(p for p in build['parts'] if p['id']=='R6H_IF_THERMAL_BRIDGE')['material_assignment']
ck('thermal_bridge_6061_readback',mat['name']=='6061 Alloy' and mat['readback'][0]=='6061 Alloy' and mat['heat_treatment_and_flight_qualification_frozen'] is False)
ck('material_database_hash',lock(mat['database'])==mat['database_sha256'])
for p,h in list(locks.items()):ck('read_only_preservation:'+p,sha(p)==h)
out=dict(schema='R6H_INDEPENDENT_NATIVE_ROUNDTRIP_REVIEW_V1',status='PASS_PARTS_GROUPS_TOP_CHAIN_WITH_SCOPE_HOLDS' if all(c['passed'] for c in checks) else 'FAIL',checks=dict(passed=sum(c['passed'] for c in checks),total=len(checks),failed=[c for c in checks if not c['passed']]),checks_detail=checks,source_locks=locks,roundtrip_body_count=len(bodyrows),roundtrip_bodies=bodyrows,material_readback=mat,native_total_leaf_body_recheck_pending=True,method='Independent direct OCP 40-body roundtrip paired by one-to-one world bbox; both directed cuts must contain zero faces and solids. Native cold statuses are source-locked builder receipts, not a second SW session.',manufacturing_release=False,ready_to_power=False,flight_ready=False)
(D/'results/reviewer/NATIVE_ROUNDTRIP_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:out[k] for k in ['status','checks']},ensure_ascii=False),flush=True)
raise SystemExit(0 if all(c['passed'] for c in checks) else 2)
