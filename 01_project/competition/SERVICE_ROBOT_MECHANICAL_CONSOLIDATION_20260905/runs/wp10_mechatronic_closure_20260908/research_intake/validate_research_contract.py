"""Validate documentary readiness semantics; not a Physics Tool or scientific Gate."""
from pathlib import Path
import copy, hashlib, json

OUT=Path(__file__).resolve().parent
ROOT=next(p for p in OUT.parents if (p/'PROJECT_MAP.md').exists())
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def require(ok,code):
 if not ok:raise ValueError(code)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

POLICY={
 'Q1_EXISTING_EVIDENCE':('LEGACY_SIM10_12','EVIDENCE_REVIEW','EVIDENCE_AUDIT_READY',{'sim10','sim12'}),
 'Q1_Q3_RIGID_BASELINE':('LEGACY_SIM05','THEORY_CONTRACT','THEORY_CONTRACT_READY',{'sim05_csv','arm_urdf','sim05_readme'}),
 'Q2_Q3_CONTACT_FLEX':('UNIFIED_R2_C01_E23','THEORY_CONTRACT','THEORY_CONTRACT_READY',{'e23','e23_config','sim11','contact_config'}),
 'Q3_Q4_GEOMETRY_AVOIDANCE':('WP09_873_CAD','CURRENT_SYSTEM_MODEL','CURRENT_SYSTEM_HOLD',{'current_native','current_dm','current_mass'}),
 'Q1_Q3_CURRENT_DYNAMICS_CONTROL':('WP09_873_CAD','CURRENT_SYSTEM_MODEL','CURRENT_SYSTEM_HOLD',{'current_native','current_mass','current_dm','current_delivery'}),
 'Q3_Q4_RL_PREREGISTRATION':('SIM13_SYNTHETIC','THEORY_CONTRACT','THEORY_CONTRACT_READY',{'sim13_20','sim13_phase_a','sim13_r2_source_only','safe'})}

def validate(document,sources):
 checks=[]
 def ck(ok,code):require(ok,code);checks.append(code)
 ck(document['authority_credit']=='NONE_ADVISORY_NOT_SCIENTIFIC_GATE','ADVISORY_SCOPE')
 for k in ['all_mechatronic_design_complete','current_873_hardware_predictive_model_ready','new_research_execution_authorized','new_training_authorized','hardware_authorized']:
  ck(document.get(k) is False,'NO_AUTHORITY:'+k)
 ck(len(sources['files'])>0,'NONEMPTY_SOURCES')
 index={s['id']:s for s in sources['files']}
 ck(len(index)==len(sources['files']),'UNIQUE_SOURCE_IDS')
 for s in sources['files']:
  p=(ROOT/s['path']).resolve()
  ck(p.is_relative_to(ROOT.resolve()) and p.is_file(),'READABLE_WORKSPACE_SOURCE:'+s['id'])
  ck(digest(p)==s['sha256'] and p.stat().st_size==s['bytes'],'SOURCE_SHA_BYTES:'+s['id'])
 mass=json.loads((ROOT/index['current_mass']['path']).read_text(encoding='utf-8-sig'))['summary']
 ck(document['current_mass_summary']==mass,'CURRENT_MASS_RAW_VALUES_NOT_SUBSTITUTED')
 for k in ['full_spacecraft_mass_kg','COM_S_mm','inertia_C_S_kg_mm2']:
  ck(mass[k] is None,'NULL_CURRENT_PHYSICS:'+k)
 ck(mass['coverage']['numeric_coverage']==400 and mass['coverage']['instances']==873,'OWNERSHIP_NOT_NUMERIC_COMPLETENESS')
 ids=[t['task_id'] for t in document['tasks']]
 ck(set(ids)==set(POLICY) and len(ids)==len(POLICY),'EXACT_TASK_SET')
 for t in document['tasks']:
  model,mode,state,source_ids=POLICY[t['task_id']]
  ck(t['model_id']==model and t['mode']==mode and t['readiness']==state,'COHORT_MODE_READINESS:'+t['task_id'])
  ck(set(t['source_ids'])==source_ids and source_ids<=set(index),'SOURCE_SEMANTIC_BINDING:'+t['task_id'])
  ck(t.get('documented_research_scope') is True and t.get('authority')=='NONE_PLANNING_CONTRACT_ONLY','DOCUMENT_NOT_OWNER_AUTHORITY:'+t['task_id'])
  ck(bool(t['assumptions']) and bool(t['missing_for_numerical_execution']),'ASSUMPTIONS_AND_GAPS:'+t['task_id'])
  ck(set(t['question_ids'])<=set('Q'+str(i) for i in range(1,7)),'EXISTING_QUESTION_ROUTING:'+t['task_id'])
  for k in ['execution_authorized','hardware_validity_established','hardware_commands_allowed','current_CAD_scientific_PASS_inherited']:
   ck(t.get(k) is False,'NO_IMPLICIT_PERMISSION:'+t['task_id']+':'+k)
 return checks

def main():
 doc=read('RESEARCH_READINESS.json');sources=read('SOURCE_BINDINGS.json')
 checks=validate(doc,sources)
 cases=[]
 def negative(name,mutator,source_mutator=None):
  bad=copy.deepcopy(doc);bs=copy.deepcopy(sources);mutator(bad)
  if source_mutator:source_mutator(bs)
  try:validate(bad,bs)
  except (ValueError,KeyError,TypeError) as e:cases.append({'id':name,'rejected':True,'reason':str(e)});return
  raise AssertionError('Negative control incorrectly accepted: '+name)
 negative('OLD_R2_MASS_REPLACES_CURRENT_NULL',lambda d:d['current_mass_summary'].__setitem__('full_spacecraft_mass_kg',31.022864807342987))
 negative('OWNERSHIP873_WRITTEN_AS_NUMERIC873',lambda d:d['current_mass_summary']['coverage'].__setitem__('numeric_coverage',873))
 negative('DOCUMENT_READY_AS_OWNER_AUTHORITY',lambda d:d['tasks'][0].__setitem__('execution_authorized',True))
 negative('OLD_SIM05_EVIDENCE_AS_CURRENT_BODY',lambda d:d['tasks'][1].__setitem__('model_id','WP09_873_CAD'))
 negative('STATIC_CAD_AS_DYNAMICS_READY',lambda d:d['tasks'][4].__setitem__('readiness','EVIDENCE_AUDIT_READY'))
 negative('FORGED_CURRENT_SOURCE_HASH',lambda d:None,lambda s:s['files'][0].__setitem__('sha256','0'*64))
 negative('TEST_PASS_AS_WHOLE_DESIGN_PASS',lambda d:d.__setitem__('all_mechatronic_design_complete',True))
 negative('SIM13_PASS_INHERITED_TO_CURRENT',lambda d:d['tasks'][5].__setitem__('current_CAD_scientific_PASS_inherited',True))
 negative('ASSUMPTIONS_OMITTED',lambda d:d['tasks'][2].__setitem__('assumptions',[]))
 negative('CRITICAL_MISSING_INPUTS_OMITTED',lambda d:d['tasks'][4].__setitem__('missing_for_numerical_execution',[]))
 for value in [None,'UNKNOWN','OOD','PROVISIONAL','false']:
  negative('HARDWARE_VALIDITY_NONBOOLEAN_'+str(value),lambda d,v=value:d['tasks'][4].__setitem__('hardware_validity_established',v))
 chain=read('UPSTREAM_HASH_AUDIT.json');chain_checks=[]
 for v in chain['bindings']:
  p=ROOT/v['path'];actual=digest(p) if p.is_file() else None
  require(actual==v['actual_sha256'],'AUDIT_SNAPSHOT_CHANGED:'+v['path'])
  expected_state='MATCH' if actual==v['expected_sha256'] else 'HASH_DRIFT' if actual else 'MISSING'
  require(v['status']==expected_state,'HASH_DRIFT_HIDDEN:'+v['path'])
  chain_checks.append(v['path'])
 result={'schema':'DOCUMENTARY_CONTRACT_VALIDATION_V1','status':'PASS_DOCUMENT_AND_NEGATIVE_CONTROLS_ONLY','positive_semantic_checks':len(checks),'positive_check_ids':checks,'negative_controls_total':len(cases),'negative_controls_rejected':sum(c['rejected'] for c in cases),'negative_controls':cases,'upstream_pin_snapshot_checks':len(chain_checks),'upstream_raw_pin_mismatches':sum(v['status']!='MATCH' for v in chain['bindings']),'upstream_integrity_PASS_claimed':False,'current_hardware_validity_granted':False,'research_execution_authorized':False,'physics_solver_executed':False,'RL_training_executed':False,'scope':'Validates evidence hashes and advisory documentary scope. Does not compute physical feasibility, implement SAFE, or issue engineering/scientific release.','validator_sha256':digest(Path(__file__)), 'readiness_sha256':digest(OUT/'RESEARCH_READINESS.json'),'source_manifest_sha256':digest(OUT/'SOURCE_BINDINGS.json')}
 (OUT/'RESEARCH_CONTRACT_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:result[k] for k in ['status','positive_semantic_checks','negative_controls_total','upstream_pin_snapshot_checks','upstream_raw_pin_mismatches']}))

if __name__=='__main__':main()
