"""One bounded, local, single-thread route. Native serial guard required."""
from pathlib import Path
import hashlib,json,subprocess,os
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
src=A/'ecad/wp10_main_input_v26_fixed.dsn'
dsn=A/'ecad/wp10_main_input_v26_signals.dsn';ses=A/'ecad/wp10_main_input_v26_signals.ses'
if ses.exists():
 old=A/'history/20260910_V26_before_return_corridor'/ses.name
 assert old.exists() and sha(old)==sha(ses),'Previous routed experiment must be archived unchanged'
t=src.read_text(encoding='utf-8');assert t.count('(clearance 50 (type smd_smd))')==1
dsn.write_text(t.replace('(clearance 50 (type smd_smd))','(clearance 200 (type smd_smd))'),encoding='utf-8')
data=A/'logs/freerouting_v26';data.mkdir(exist_ok=True)
(data/'freerouting.json').write_text(json.dumps({'version':'2.0.1','usage_and_diagnostic_data':{'disable_analytics':True},'feature_flags':{'save_jobs':False},'api_server':{'enabled':False},'gui':{'enabled':False}}),encoding='utf-8')
cmd=['F:/AI_TOOLCHAIN/EDA-Agent-Hub/MCP/KiCAD-MCP-Server/local/runtime/jdk-21.0.12.1+1-jre/bin/java.EXE',
 '-Xms64m','-Xmx512m','-Djava.awt.headless=true','-jar','F:/AI_TOOLCHAIN/EDA-Agent-Hub/MCP/KiCAD-MCP-Server/local/freerouting-2.0.1.jar',
 '--user_data_path='+str(data),'--gui.enabled=false','--api_server.enabled=false','--usage_and_diagnostic_data.disable_analytics=true','--feature_flags.save_jobs=false',
 '-de',str(dsn),'-do',str(ses),'-mp','20','-mt','1']
rec=dict(command=cmd,input_sha256=sha(dsn),fixed_PCB_sha256=sha(A/'ecad/wp10_main_input_v26_fixed.kicad_pcb'),
 heap_max_MiB=512,timeout_s=180,smd_smd_clearance_um=200,
 acceptance='Only explicitly allowed low-current net copper may be merged into the fixed board; no router modification to fixed nets or footprints is accepted.')
try:
 q=subprocess.run(cmd,cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
 rec.update(returncode=q.returncode,stdout=q.stdout,stderr=q.stderr,session_exists=ses.exists())
 if ses.exists():rec['SES_sha256']=sha(ses)
except subprocess.TimeoutExpired as e:
 rec.update(status='TIMEOUT_NO_PROMOTION',stdout=str(e.stdout),stderr=str(e.stderr));raise
finally:
 (A/'results/MAIN_INPUT_AUTOROUTE_COMMAND_V26.json').write_text(json.dumps(rec,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in rec.items() if k not in ['command','stdout','stderr']}))
assert q.returncode==0 and ses.exists(),q.stderr
