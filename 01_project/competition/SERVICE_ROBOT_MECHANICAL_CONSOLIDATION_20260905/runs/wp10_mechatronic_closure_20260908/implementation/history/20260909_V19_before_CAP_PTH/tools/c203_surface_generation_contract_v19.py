"""Source and completed-run bindings; importing performs no CAD work."""
from pathlib import Path
import json,hashlib,datetime
A=Path(__file__).resolve().parents[1]
SPECS={
 'pcb':dict(id='C203_PCB',stem='input_cap_pcb',dependencies=['mechanical/c203_pcb_surface_profile.py']),
 'plus':dict(id='C203_W_PLUS',stem='cap_harness_plus',dependencies=['mechanical/cap_harness_common.py','mechanical/cap_harness_path.py']),
 'minus':dict(id='C203_W_MINUS',stem='cap_harness_minus',dependencies=['mechanical/cap_harness_common.py','mechanical/cap_harness_path.py'])}
COMMON=['mechanical/C203_SURFACE_PROFILE_V19.json','power/CAP_TERMINAL_DEFINITION.json','power/CAP_HARNESS_DEFINITION_V19.json','ecad/wp10_c203_terminal.kicad_pcb','tools/generate_c203_surface_v19.py','tools/c203_surface_generation_contract_v19.py','tools/native_delta_guard.py','tools/native_delta_win_job.py','tools/run_cap19.py']
GUARD_ID_FIELDS=['pid','started_local','cwd','name','command']
PYTHON=str(Path('G:/Windows_program_file/Anaconda/python.exe').resolve())
CAD=str(Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts/gen').resolve())
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def receipt_path(kind):assert kind in SPECS;return f'results/C203_SURFACE_GENERATION_{kind.upper()}_V19.json'
def sources(kind):
 spec=SPECS[kind];paths=COMMON+[f"mechanical/{spec['stem']}.step.py"]+spec['dependencies']
 for doc in ['mechanical/C203_SURFACE_PROFILE_V19.json','power/CAP_HARNESS_DEFINITION_V19.json']:
  d=read(doc);assert all(sha(f)==h for f,h in d['inputs'].items()),doc+' has stale source bindings'
  paths+=list(d['inputs'])
 return {p:sha(p) for p in sorted(set(paths))}
def check_record(kind,rec,guard,expected,output_hash):
 assert rec['kind']==kind and rec['native_generation_executed'] is True
 assert rec['inputs']==expected and rec['output']==f"mechanical/{SPECS[kind]['stem']}.step"
 assert rec['output_sha256']==output_hash and rec['generator_returncode']==0 and rec['output_bytes']>0
 assert guard['status']=='COMPLETED' and guard['returncode']==0
 assert guard['name']==Path(rec['guard_receipt']).name.removesuffix('.run.json')
 assert guard['command']==[PYTHON,'-B','-X','utf8','tools/generate_c203_surface_v19.py',kind]
 assert rec['command']==[PYTHON,'-B','-X','utf8',CAD,f"mechanical/{SPECS[kind]['stem']}.step.py",'--write']
 assert rec['owner_guard_identity']=={k:guard[k] for k in GUARD_ID_FIELDS}
 assert rec['wrapper_pid']==guard['pid'] and isinstance(rec['generator_pid'],int) and rec['generator_pid']>0 and rec['generator_pid']!=rec['wrapper_pid']
 assert Path(guard['cwd']).resolve()==A and (A/rec['guard_receipt']).resolve().parent==A/'logs'
 t0=datetime.datetime.fromisoformat(guard['started_local']).timestamp();t1=datetime.datetime.fromisoformat(rec['started_local']).timestamp();t2=datetime.datetime.fromisoformat(rec['finished_local']).timestamp()
 assert t0<=t1<=t2<=t0+guard['elapsed_s']+2
 assert guard['minimum_start_available_mib']>=2048 and guard['available_start_mib']>=2048
 assert guard['available_floor_mib']>=512 and guard['max_child_tree_rss_mib']<=1400 and not guard['SW_processes_at_start']
 assert guard['windows_job_commit_limit_mib']<=1400 and guard['kill_own_tree_on_monitor_exit'] is True
 assert guard['child_environment_limits']=={'CADGEN_COMPONENT_WORKERS':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
 assert not rec['whole_fit_verified'] and not rec['native_geometry_qualified']
 return True
def validate_receipt(kind):
 path=receipt_path(kind);r=read(path);guard=read(r['guard_receipt'])
 check_record(kind,r,guard,sources(kind),sha(r['output']))
 assert (A/r['output']).stat().st_size==r['output_bytes']
 return dict(r,receipt_path=path)
