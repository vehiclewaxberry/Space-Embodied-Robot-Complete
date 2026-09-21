"""Archive prior V20 receipts and refresh code bindings after review fixes."""
from c203_surface_generation_contract_v19 import A,read,sha,SPECS,receipt_path
from c203_surface_source_contract_v19 import validate_profile
from prepare_cap_harness_plan_v19 import PLAN,PROFILE,validate_plan
import json,shutil,subprocess,sys
suffix=sys.argv[1] if len(sys.argv)>1 else ''
assert suffix in ['', '_final']
H=A/('history/20260909_V20_before_CAM_contract_fix'+suffix)
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2),encoding='utf-8')
assert not H.exists()
paths=[PLAN,PROFILE,'results/CAP_HARNESS_EXACT_V19.json','power/CAP_HARNESS_DEFINITION_V19.json','results/C203_CAM_CHECK_V20.json']+[receipt_path(k) for k in SPECS if (A/receipt_path(k)).exists()]+[f"mechanical/{s['stem']}.step" for s in SPECS.values()]
for rel in paths:
 q=H/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(A/rel,q)
dump(H.relative_to(A).as_posix()+'/ARCHIVE_SHA256.json',{p:sha(p) for p in paths})
c=read(PROFILE);validate_profile(c);c['inputs']={p:sha(p) for p in [*c['inputs'],'results/CAP_TERMINAL_NATIVE_BINDING.json']};dump(PROFILE,c)
subprocess.run([sys.executable,'-B','-X','utf8','tools/define_cap_harness_v19.py'],cwd=A,check=True)
p=read(PLAN);p.update(surface_profile_pending=True,source_geometry_fresh=False,source_surface_profile_sha256=sha(PROFILE))
p['inputs']={f:sha(f) for f in p['inputs'] if not f.startswith(('logs/','results/C203_SURFACE_GENERATION_'))}
for st in p['states'].values():
 for spec in SPECS.values():
  row=next(r for r in st['rows'] if r['id']==spec['id']);source=f"mechanical/{spec['stem']}.step.py"
  for key in ['generation_receipt','generation_receipt_sha256']:row.pop(key,None)
  row.update(geometry_regeneration_required=True,native_geometry_current=False,geometry_state='OLD_STEP_RETAINED_FOR_HISTORY__NOT_CURRENT_SURFACE_REVISION',expected_generator_source=source,expected_generator_sha256=sha(source))
validate_plan(p,require_generated=False);dump(PLAN,p)
for kind in SPECS:
 rel=receipt_path(kind);p=(A/rel).resolve()
 if p.exists():
  assert p.is_relative_to(A.resolve()) and p.read_bytes()==(H/rel).read_bytes();p.unlink()
print('Physical design unchanged; revised code bindings pending fresh STEP receipts')
