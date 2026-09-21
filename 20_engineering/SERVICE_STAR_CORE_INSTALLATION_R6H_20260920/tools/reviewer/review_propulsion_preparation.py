"""Independent R6H source/route/OEM/work-order projection audit; CAD read-only."""
from pathlib import Path
import csv,hashlib,json
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.gp import gp_Trsf
D=Path(__file__).resolve().parents[2];ROOT=D.parents[1]
R6=D.parent/'SERVICE_STAR_CORE_INSTALLATION_R6_20260920'
locks={};checks=[];bounds=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lock(p):
 p=Path(p);h=sha(p);k=str(p.resolve());assert k not in locks or locks[k]==h;locks[k]=h;return h
def read(p):lock(p);return json.loads(Path(p).read_text(encoding='utf8'))
def ck(n,v,d=None):checks.append(dict(name=n,passed=bool(v),detail=d))
p=D/'inputs/PROPULSION_ASSEMBLY_PREPARATION.json';prep=read(p)
prior=read(R6/'results/reviewer/INSTALLATION_INTAKE_REVIEW.json')['propulsion']
template=read(D/'inputs/PROPULSION_OEM_INPUT_TEMPLATE.json')
plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');lay=read(D/'inputs/INSTALLATION_LAYOUT.json')
leaves={r['id']:r for r in plan['expected_leaves']}
for r in prep['source_locks']:ck('source_lock:'+r['path'],lock(r['path'])==r['sha256'])
ck('OEM_9_gaps_exact',prep['oem_icd_missing_fields']==prior['oem_icd_missing_fields'] and len(prep['oem_icd_missing_fields'])==9)
ck('PA01_PA12_exact',prep['work_orders']==prior['next_12_engineering_actions'] and len(prep['work_orders'])==12)
pcsv=D/'docs/PROPULSION_NEXT_WORK_ORDERS.csv';lock(pcsv)
with pcsv.open(encoding='utf-8-sig',newline='') as f:workcsv=list(csv.DictReader(f))
ck('CSV12_work_orders_exact',workcsv==prior['next_12_engineering_actions'])
for k in ['mechanical_interface','electrical_interface','functional_routes']:ck(k+'_exact',prep[k]==prior[k])
ref={r['id']:r for r in prior['retained_CAD_objects']}
ck('10_reserved_objects',len(prep['retained_CAD_objects'])==10 and set(r['id'] for r in prep['retained_CAD_objects'])==set(ref))
ck('count9_unchanged1_revised',prep['unchanged_objects']==9 and prep['locally_revised_P60_tray']==1)
for r in prep['retained_CAD_objects']:
 a=ref[r['id']];n=leaves[r['id']]
 ck('native_identity:'+r['id'],Path(r['source_path']).resolve()==Path(n['step_path']).resolve() and r['source_sha256']==n['source_sha256'] and r['T_S_local']==n['T_S_local'])
 ck('STEP_SHA:'+r['id'],lock(r['source_path'])==r['source_sha256'])
 if r['id']!='P60_TRAY_B':
  ck('R4_retained:'+r['id'],r['T_S_local']==a['T_S_local'] and r['S_frame_AABB_mm']==a['S_frame_AABB_mm'] and r['representation_role']==a['representation_role'] and r['R4_identity_and_pose_preserved'] is True)
 else:
  t=next(x for x in lay['replacements'] if x['id']==r['id'])
  ck('tray_declared_change',r['R4_identity_and_pose_preserved'] is False and t['source_sha256']==r['source_sha256'] and r['representation_role']=='PHYSICAL_GEOMETRY')
 q=STEPControl_Reader();assert q.ReadFile(r['source_path'])==IFSelect_RetDone;assert q.TransferRoots()>0;s=q.OneShape();assert BRepCheck_Analyzer(s).IsValid()
 tr=gp_Trsf();tr.SetValues(*[float(r['T_S_local'][i][j]) for i in range(3) for j in range(4)]);s=BRepBuilderAPI_Transform(s,tr,True).Shape()
 b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b,False,False);v=b.Get();box=[list(v[:3]),list(v[3:])]
 # The inherited SOURCE_LOCAL_BOUNDS used Add, whose B-spline bounds can be
 # conservative. Reproduce that exact method; also require optimal containment.
 c=Bnd_Box();BRepBndLib.Add_s(s,c,False);v=c.Get();conservative=[list(v[:3]),list(v[3:])]
 error=float(np.max(np.abs(np.array(conservative)-r['S_frame_AABB_mm'])))
 declared=np.array(r['S_frame_AABB_mm']);actual=np.array(box)
 contained=bool(np.all(actual[0]>=declared[0]-1e-5) and np.all(actual[1]<=declared[1]+1e-5))
 bounds.append(dict(id=r['id'],optimal_bbox_mm=box,conservative_Add_bbox_mm=conservative,declared_method='BRepBndLib.Add',max_error_mm=error,optimal_contained=contained))
 ck('OCP_recorded_Add_AABB:'+r['id'],error<1e-5);ck('OCP_optimal_bbox_contained:'+r['id'],contained)
 print('OBJECT',r['id'],error,flush=True)
for k in ['selected_flight_MPN','nozzle_positions_S_mm','spacecraft_force_directions_S','plume_half_angle_deg','dry_mass_kg','wet_mass_kg','flight_pressure_contract']:ck('UNKNOWN_preserved:'+k,prep[k] is None)
for k in ['source_and_load_complete_wiring','nozzle_and_tank_assembly_frozen','thruster_firing_authorized','ready_to_power','flight_ready']:ck('HOLD_preserved:'+k,prep[k] is False)
for k,v in template.items():
 if k not in {'schema','units','purpose','mount_thread'}:ck('template_unknown:'+k,v is None)
ck('template_other_MPN_rebind','other MPN must rebind' in template['mount_thread'])
ck('R6H_layout_binding',prep['source_R6H_layout_sha256']==sha(D/'inputs/INSTALLATION_LAYOUT.json'))
ck('R6H_plan_binding',prep['source_R6H_plan_sha256']==sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json'))
for k,h in list(locks.items()):ck('read_only_preservation:'+k,sha(k)==h)
out=dict(schema='R6H_INDEPENDENT_PROPULSION_PREPARATION_REVIEW_V1',status='PREPARATION_PASS_WITH_OEM_HOLDS' if all(r['passed'] for r in checks) else 'FAIL',checks=dict(passed=sum(r['passed'] for r in checks),total=len(checks),failed=[r for r in checks if not r['passed']]),checks_detail=checks,source_locks=locks,coordinate_frame='S_mm',bounds= bounds,scope='Source and current horizontal-layout binding, 9 original reserved objects plus locally revised P60 tray, 9 exact OEM gaps and 12 exact work orders. No frozen propulsion MPN, pressure hardware, nozzle geometry, completed wiring, firing or flight qualification.',manufacturing_release=False,ready_to_power=False,flight_ready=False)
(D/'results/reviewer/PROPULSION_PREPARATION_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(status=out['status'],checks=out['checks']),ensure_ascii=False),flush=True)
raise SystemExit(0 if all(r['passed'] for r in checks) else 2)
