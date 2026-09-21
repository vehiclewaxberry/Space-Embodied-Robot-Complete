"""Rebind pending source metadata only; explicitly retain stale STEP status."""
from c203_surface_generation_contract_v19 import A,read,sha,SPECS
from prepare_cap_harness_plan_v19 import PLAN,PROFILE,validate_plan
import json
p=read(PLAN);assert p['surface_profile_pending'] and not p['source_geometry_fresh']
for st in p['states'].values():
 for spec in SPECS.values():
  r=next(r for r in st['rows'] if r['id']==spec['id']);assert r['geometry_regeneration_required']
  source=f"mechanical/{spec['stem']}.step.py"
  r.update(expected_generator_source=source,expected_generator_sha256=sha(source),native_geometry_current=False)
p['source_surface_profile_sha256']=sha(PROFILE)
p['inputs'].update({f:sha(f) for f in [PROFILE,'power/CAP_HARNESS_DEFINITION_V19.json','tools/prepare_cap_harness_plan_v19.py','tools/c203_surface_generation_contract_v19.py']})
validate_plan(p,require_generated=False)
(A/PLAN).write_text(json.dumps(p,indent=2),encoding='utf-8')
print('Pending source bindings refreshed; no STEP or native generation result changed')
