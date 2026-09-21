"""Negative checks of the real publisher preflight, no publication writes."""
from pathlib import Path
import importlib.util,json,hashlib,copy
A=Path(__file__).resolve().parents[1];p=A/'tools/publish_chb_input_revision.py'
sp=importlib.util.spec_from_file_location('chb_pub_checked',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before={q:sha(A/q) for q in ['README.md','REVIEW.html','results/DELIVERY_DECISION.json','SYSTEM_CLOSURE_MATRIX.csv']}
m.validate(False);original=m.read;faults=[]
def fault(name,path,mutate):
 value=copy.deepcopy(original(path));mutate(value);m.read=lambda x:value if x==path else original(x)
 try:
  m.validate(False);rejected=False
 except AssertionError:rejected=True
 finally:m.read=original
 faults.append(dict(name=name,rejected=rejected));assert rejected,name
fault('nonzero_native_DRC','results/CHB_INPUT_DRC_NATIVE_V18.json',lambda x:x['violations'].append(dict(severity='error',type='clearance')))
fault('empty_three_state_mechanical_result','results/CHB_INPUT_MECHANICAL_V18.json',lambda x:x.update(states={}))
fault('counterexample_not_rejected','results/CHB_INPUT_COPPER_V18.json',lambda x:x['faults'][0].update(rejected=False))
fault('wrong_published_snapshot_hash','results/CHB_INPUT_SNAPSHOT_V18.json',lambda x:x.update(published_sha256='0'*64))
fault('stale_independent_review_source','results/CHB_INPUT_READONLY_REVIEW_V18.json',lambda x:x['reviewed_files'].update({'mechanical/chb_input_common.py':'0'*64}))
assert all(sha(A/q)==h for q,h in before.items())
out=dict(passed=True,baseline_accepted=True,faults=faults,publisher_sha256=sha(p),test_source_sha256=sha(Path(__file__)),publication_files_unchanged=True,scope='Execution of publisher.validate only; publish was never called.')
(A/'results/CHB_INPUT_PUBLICATION_TESTS_V18.json').write_text(json.dumps(out,indent=2));print('Actual preflight baseline accepted,5 faults rejected; no publication writes')
