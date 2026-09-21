"""Negative source/run-binding tests; synthetic fixtures never become native evidence."""
import copy,json,subprocess,sys,ast
from c203_surface_generation_contract_v19 import A,SPECS,check_record,validate_receipt,sha,receipt_path,PYTHON,CAD,GUARD_ID_FIELDS
def main():
 kind='pcb';inputs={'fixture.py':'a'*64};output='b'*64
 rec=dict(kind=kind,native_generation_executed=True,inputs=inputs,output='mechanical/input_cap_pcb.step',output_sha256=output,generator_returncode=0,output_bytes=1,guard_receipt='logs/native_delta_FIXTURE_ONLY.run.json',whole_fit_verified=False,native_geometry_qualified=False)
 guard=dict(name='native_delta_FIXTURE_ONLY',pid=100,started_local='2026-09-09T23:00:00+09:00',cwd=str(A),elapsed_s=20,status='COMPLETED',returncode=0,command=[PYTHON,'-B','-X','utf8','tools/generate_c203_surface_v19.py','pcb'],minimum_start_available_mib=2048,available_start_mib=2304,available_floor_mib=512,max_child_tree_rss_mib=1400,SW_processes_at_start=[],windows_job_commit_limit_mib=1400,kill_own_tree_on_monitor_exit=True,child_environment_limits={'CADGEN_COMPONENT_WORKERS':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
 rec.update(command=[PYTHON,'-B','-X','utf8',CAD,'mechanical/input_cap_pcb.step.py','--write'],started_local='2026-09-09T23:00:01+09:00',finished_local='2026-09-09T23:00:10+09:00',wrapper_pid=100,generator_pid=101,owner_guard_identity={k:guard[k] for k in GUARD_ID_FIELDS})
 assert check_record(kind,rec,guard,inputs,output)
 faults=[]
 def reject(name,mutate):
  r,g=copy.deepcopy(rec),copy.deepcopy(guard);mutate(r,g)
  try:check_record(kind,r,g,inputs,output);rejected=False
  except AssertionError:rejected=True
  assert rejected,name;faults.append(dict(name=name,rejected=True))
 reject('stale_source_hash',lambda r,g:r.update(inputs={'fixture.py':'c'*64}))
 reject('old_STEP_hash',lambda r,g:r.update(output_sha256='d'*64))
 reject('guard_still_running',lambda r,g:g.update(status='RUNNING'))
 reject('guard_memory_failure',lambda r,g:g.update(status='AVAILABLE_MEMORY_GUARD',returncode=-1))
 reject('wrong_generation_phase',lambda r,g:g['command'].__setitem__(-1,'plus'))
 reject('missing_actual_generation',lambda r,g:r.update(native_generation_executed=False))
 reject('low_memory_start',lambda r,g:g.update(available_start_mib=1536))
 reject('guard_limit_increased',lambda r,g:g.update(max_child_tree_rss_mib=4096))
 reject('simultaneous_SolidWorks',lambda r,g:g.update(SW_processes_at_start=[{'pid':1}]))
 reject('source_export_claimed_qualified',lambda r,g:r.update(native_geometry_qualified=True))
 reject('wrong_generator_command',lambda r,g:r.update(command=['unrelated.py']))
 reject('unrelated_guard_prefix',lambda r,g:g['command'].__setitem__(0,'unrelated.exe'))
 reject('generation_199_years_earlier',lambda r,g:r.update(started_local='1827-09-09T23:00:01+09:00'))
 reject('wrong_wrapper_PID',lambda r,g:r.update(wrapper_pid=999))
 reject('wrong_guard_start_identity',lambda r,g:r['owner_guard_identity'].update(started_local='2026-09-09T22:00:00+09:00'))
 reject('Windows_commit_limit_raised',lambda r,g:g.update(windows_job_commit_limit_mib=99999))
 reject('owned_tree_cleanup_disabled',lambda r,g:g.update(kill_own_tree_on_monitor_exit=False))
 assert not any((A/receipt_path(k)).exists() for k in SPECS),'This pending-state test must not replace actual native receipts'
 plan='mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json';before=sha(plan)
 q=subprocess.run([sys.executable,'-B','-X','utf8','tools/prepare_cap_harness_plan_v19.py'],cwd=A,capture_output=True,text=True,encoding='utf-8')
 assert q.returncode!=0 and 'FileNotFoundError' in q.stderr and 'C203_SURFACE_GENERATION_PCB_V19.json' in q.stderr
 assert before==sha(plan),'Rejected builder modified active source plan'
 paths=['tools/prepare_cap_harness_plan_v19.py','tools/c203_surface_generation_contract_v19.py','tools/generate_c203_surface_v19.py','tools/check_cap_harness_exact_v19.py','mechanical/cap_harness_assembly.step.py','tools/check_c203_regeneration_contract_v19.py']
 for p in paths:ast.parse((A/p).read_text(encoding='utf-8'))
 result=dict(passed=True,fixture_scope='Synthetic in-memory run records only; no native output or guard receipt fabricated',faults=faults,
  actual_plan_builder_rejected_missing_receipt=True,actual_builder_returncode=q.returncode,plan_bytes_unchanged_after_rejection=True,
  native_CAD_started=False,whole_design_complete=False,inputs={p:sha(p) for p in paths+[plan]})
 (A/'results/C203_REGENERATION_CONTRACT_TEST_V19.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(dict(passed=True,faults=len(faults),actual_builder_rejected=True,plan_unchanged=True,native_CAD_started=False)))
if __name__=='__main__':main()
