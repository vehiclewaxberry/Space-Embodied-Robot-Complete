"""Rebind changed native CAM surfaces and explicitly invalidate old STEP receipts."""
from pathlib import Path
import json,copy
from c203_surface_generation_contract_v19 import A,read,sha,SPECS,receipt_path
from c203_surface_source_contract_v19 import extract,validate_profile
from prepare_cap_harness_plan_v19 import PLAN,PROFILE,PARENT,CHANGED,ADDED,I,validate_plan
H=A/'history/20260909_V19_before_CAP_PTH'
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def main():
 old=read('history/20260909_V19_before_CAP_PTH/'+PROFILE)
 c=copy.deepcopy(old);c.update(extract());c.update(schema='WP10_C203_LOCAL_SURFACE_PROFILE_V20_CAP_PTH',status='NOMINAL_NATIVE_CAM_PROFILE__CAD_REGEN_AND_PROCESS_PENDING',mask_model='Actual KiCad10.0.6 CAM apertures: CAP front3.5mm exposes bare core around2mm finished hole. Copper layers use connected-board FlashLayer and CAM, not declared *.Cu. Conformal film; registration/flow/step coverage unqualified.')
 cam=read('results/CAP_CAM_ACTIVE_V20.json')
 deps=['ecad/wp10_c203_terminal.kicad_pcb','tools/configure_cap_pth_surface_v20.py','tools/c203_surface_source_contract_v19.py','tools/c203_cam_contract_v20.py','tools/cap_terminal_native.py','results/CAP_TERMINAL_NATIVE_GEOMETRY.json','results/CAP_CAM_ACTIVE_V20.json',*cam['files']]
 c['inputs']={p:sha(p) for p in deps};validate_profile(c);dump(PROFILE,c)
 d=read('power/CAP_TERMINAL_DEFINITION.json');drc=read('results/CAP_PTH_DRC_EXECUTION_V20.json')
 assert drc['inputs'][d['board']]==sha(d['board']) and drc['violations']==0
 d.pop('mechanical_STEP_current',None)
 d.update(DRC_current_revision_executed=True,DRC_local_process_issues_open=False,DRC_report='results/CAP_TERMINAL_DRC_NATIVE_V20.json',surface_profile_native_verified=True,mechanical_STEP_evidence_required='results/CAP_PTH_WORKING_STATUS_V20.json',solder_and_fabrication_qualified=False)
 dump('power/CAP_TERMINAL_DEFINITION.json',d)
 m=read('mechanical/INPUT_CAP_MOUNT_DESIGN.json');m['source_files']['power/CAP_TERMINAL_DEFINITION.json']=sha('power/CAP_TERMINAL_DEFINITION.json');dump('mechanical/INPUT_CAP_MOUNT_DESIGN.json',m)
 # Recompute wire source bindings; geometry is unchanged but generation records will be fresh.
 import subprocess,sys
 subprocess.run([sys.executable,'-B','-X','utf8','tools/define_cap_harness_v19.py'],cwd=A,check=True)
 p=read(PLAN);p.update(surface_profile_pending=True,source_geometry_fresh=False,source_surface_profile_sha256=sha(PROFILE))
 p['inputs']={f:sha(f) for f in [PARENT,PROFILE,'power/CAP_HARNESS_DEFINITION_V19.json','tools/prepare_cap_harness_plan_v19.py','tools/c203_surface_generation_contract_v19.py']}
 for st in p['states'].values():
  for spec in SPECS.values():
   row=next(r for r in st['rows'] if r['id']==spec['id']);source=f"mechanical/{spec['stem']}.step.py"
   for key in ['generation_receipt','generation_receipt_sha256']:row.pop(key,None)
   row.update(geometry_regeneration_required=True,native_geometry_current=False,geometry_state='OLD_STEP_RETAINED_FOR_HISTORY__NOT_CURRENT_SURFACE_REVISION',expected_generator_source=source,expected_generator_sha256=sha(source))
 validate_plan(p,require_generated=False);dump(PLAN,p)
 for kind in SPECS:
  rel=receipt_path(kind);active=(A/rel).resolve();archived=(H/rel).resolve()
  assert active.is_relative_to(A.resolve()) and archived.is_relative_to(H.resolve())
  if active.exists():
   assert active.read_bytes()==archived.read_bytes(),'Previous receipt not archived exactly'
   active.unlink()
 r=read('results/CAP_PTH_SOURCE_CHANGE_V20.json');r.update(archived_files=len(read('history/20260909_V19_before_CAP_PTH/ARCHIVE_SHA256.json')),status='ACTIVE_NATIVE_DRC_ZERO__CAM_VERIFIED__STEP_REGEN_PENDING',actual_active_DRC_errors=0,source_files={p:sha(p) for p in r['source_files']},surface_profile_sha256=sha(PROFILE));dump('results/CAP_PTH_SOURCE_CHANGE_V20.json',r)
 print('V20 physical mask surface changed; plan explicitly pending, archived old receipts removed')
if __name__=='__main__':main()
