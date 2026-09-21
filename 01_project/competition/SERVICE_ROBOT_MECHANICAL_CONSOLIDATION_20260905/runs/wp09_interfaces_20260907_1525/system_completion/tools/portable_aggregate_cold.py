"""Bind three independently fresh SolidWorks process cold-open receipts."""
from pathlib import Path
import json,hashlib,sys
C=Path(__file__).resolve().parents[1]
location=sys.argv[1];assert location in ('primary','relocated')
suffix='_V4' if location=='relocated' else ''
states={};evidence=[];processes=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for state in ('service','parking','released'):
 p=C/'results'/('PORTABLE_COLD_'+location.upper()+'_'+state.upper()+suffix+'.json')
 r=json.loads(p.read_text());assert r['status']=='PASS_SINGLE_STATE_FRESH_PROCESS_COLD_PORTABLE'
 guard=C/'logs'/('portable_'+location+'_'+state+suffix.lower()+'.run.json')
 g=json.loads(guard.read_text());assert g['status']=='COMPLETED' and g['returncode']==0
 assert g['combined_python_and_sw_rss_limit_mib']==1400 and g['available_floor_mib']==512
 assert g['available_start_mib']>=2048 and r['session_start_empty']
 owner=g['owned_sw'];processes.append((owner['pid'],owner['create_time']))
 q=r['states'][state]
 assert q['component_count']==705 and q['external_dependency_count']==0 and q['max_transform_sw16_error']<=1e-8
 assert q['open_errors']==0 and q['dirty_after_inspection']==False
 assert r['all_parts_byte_identical_to_parent'] and r['source_inputs_unchanged'] and r['open_documents_after']==[]
 states[state]={k:q[k] for k in ('status','path','sha256','component_count','unique_part_files','max_transform_sw16_error','external_dependency_count','open_errors','open_warnings')}
 states[state].update(available_start_mib=g['available_start_mib'],peak_combined_python_sw_rss_mib=max(v['combined_rss_mib'] for v in g['samples']),actual_initial_document_count=0)
 evidence.extend([{'path':str(p),'sha256':sha(p)},{'path':str(guard),'sha256':sha(guard)}])
assert len(set(processes))==3,'Each state must use a newly started process'
out=C/'results'/('PORTABLE_COLD_'+location.upper()+'_V2.json');assert not out.exists()
r={'status':'PASS_ALL_THREE_COLD_PORTABLE_STATES','location':location,'fresh_process_per_state':True,'processes':processes,'states':states,'evidence':evidence,
   'all_external_dependencies_zero':True,'source_inputs_unchanged':True,'solid_measurements_this_task':0,
   'inherited_expected_solids_each':1086,'physical_path_relocation_test':location=='relocated'}
out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r))
