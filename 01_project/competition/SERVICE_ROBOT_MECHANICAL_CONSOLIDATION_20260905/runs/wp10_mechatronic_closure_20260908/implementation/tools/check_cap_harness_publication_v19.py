"""Exercise decision-metadata checks in memory; no delivery or CAD acceptance."""
import copy,json
from publish_cap_harness_v19 import A,read,sha,decision,check_decision,dump

def build():
 baseline=decision(read('results/CAP_HARNESS_PATH_V19.json'),None)
 check_decision(baseline)
 faults=[]
 def reject(name,mutate):
  value=copy.deepcopy(baseline);mutate(value)
  try:check_decision(value);rejected=False
  except AssertionError:rejected=True
  assert rejected,name
  faults.append(dict(name=name,rejected=True))
 reject('stale_source_sha256',lambda x:x.update(current_source_plan_sha256='0'*64))
 reject('stale_one_state_965_count',lambda x:x['current_source_instances_by_state'].update(service=965))
 reject('stale_candidate_count_alias',lambda x:x.update(source_candidate_components=965))
 reject('unsupported_goal_complete',lambda x:x.update(goal_complete=True))
 reject('unsupported_whole_native_assembly',lambda x:x.update(current_full_native_assembly_generated=True))
 reject('unsupported_manufacturing_release',lambda x:x.update(manufacture_release=True))
 reject('unsupported_power_on_authorization',lambda x:x.update(power_on_authorized=True))
 dump('results/CAP_HARNESS_PUBLICATION_TESTS_V19.json',dict(passed=True,scope='Pure in-memory decision metadata invariants only. Not native geometry, publication preflight or assembly acceptance.',publisher_sha256=sha('tools/publish_cap_harness_v19.py'),test_source_sha256=sha('tools/check_cap_harness_publication_v19.py'),source_plan='mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json',source_plan_sha256=sha('mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json'),faults=faults,publication_executed=False))
 print(json.dumps(dict(passed=True,faults=len(faults),publication_executed=False)))
if __name__=='__main__':build()
