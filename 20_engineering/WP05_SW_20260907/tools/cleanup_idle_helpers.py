"""User-authorized cleanup, limited to this Codex host's idle tool servers.
Never targets OS services, security/network tools, Codex, or active solver jobs.
"""
import psutil,time,json,datetime
from pathlib import Path
R=Path(__file__).resolve().parents[1]
markers=['/mcp/abaqus/','/mcp/ansys/fluent mcp/','/mcp/ansys/workbench mcp/','/mcp/ansys/aedt mcp/','/comsol_link/','/skills/vibration_control.py','/skills/ancf_kinematics.py','/mcp/qwen_vision/server.py','/skills_bridge_server.py','solidworks_mcp.server']
def eligible(p):
 try:
  cmd=' '.join(p.cmdline()).replace('\\','/').lower()
  return p.name().lower()=='python.exe' and any(m in cmd for m in markers)
 except (psutil.NoSuchProcess,psutil.AccessDenied):return False
before=psutil.virtual_memory().available
candidates=[]
for p in psutil.process_iter():
 if not eligible(p):continue
 try:
  # Do not terminate a bridge that owns an actual solver/application process.
  if any(not eligible(c) for c in p.children(recursive=True)):continue
  candidates.append((p,p.create_time(),sum(p.cpu_times()[:2])))
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
time.sleep(1)
rows=[]
for p,created,cpu in sorted(candidates,key=lambda q:len(q[0].parents()),reverse=True):
 try:
  if p.create_time()!=created or not eligible(p):continue
  if any(not eligible(c) for c in p.children(recursive=True)):continue
  delta=sum(p.cpu_times()[:2])-cpu
  row={'pid':p.pid,'exe':p.exe(),'reason':'Unused engineering/MCP helper without solver children','cpu_seconds_over_sample':delta,'working_set_bytes':p.memory_info().rss}
  if delta>.20:row['status']='RETAINED_ACTIVE_CPU'
  else:p.terminate();row['status']='TERMINATION_REQUESTED'
  rows.append(row)
 except psutil.NoSuchProcess:pass
 except psutil.AccessDenied:rows.append({'pid':p.pid,'status':'RETAINED_ACCESS_DENIED'})
time.sleep(1)
for row in rows:
 if row['status']=='TERMINATION_REQUESTED':row['status']='EXITED' if not psutil.pid_exists(row['pid']) else 'STILL_RUNNING'
result={'authorization':'User asked to close unnecessary background processes before continuing native assembly','available_before_mib':before/2**20,'available_after_mib':psutil.virtual_memory().available/2**20,'processes':rows,'system_security_network_codex_untouched':True,'active_cad_documents_not_force_closed':True}
result['recorded_local']=datetime.datetime.now().astimezone().isoformat()
receipt=R/'results'/('BACKGROUND_CLEANUP_RECHECK_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json')
receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'exited_helpers':sum(x['status']=='EXITED' for x in rows),'available_before_mib':result['available_before_mib'],'available_after_mib':result['available_after_mib']}))
