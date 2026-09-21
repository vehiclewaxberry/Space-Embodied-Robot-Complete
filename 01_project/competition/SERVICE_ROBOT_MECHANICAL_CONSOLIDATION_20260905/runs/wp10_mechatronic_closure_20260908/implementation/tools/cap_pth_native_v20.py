"""Current CAP PTH native normalization, extraction and DRC; run under serial guard."""
from pathlib import Path
import sys,json,hashlib,subprocess,collections
A=Path(__file__).resolve().parents[1];ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').is_file())
KPY='G:/Windows_program_file/Kicad/bin/python.exe';CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2),encoding='utf-8')
phase=sys.argv[1]
if phase=='normalize_extract':
 subprocess.run([KPY,'-B','-X','utf8','tools/cap_terminal_native.py','finalize'],cwd=A,check=True)
 d=read('power/CAP_TERMINAL_DEFINITION.json');d['finished_copper_thickness_native_bound']=True
 dump('power/CAP_TERMINAL_DEFINITION.json',d)
 m=read('mechanical/INPUT_CAP_MOUNT_DESIGN.json');m['source_files']['power/CAP_TERMINAL_DEFINITION.json']=sha('power/CAP_TERMINAL_DEFINITION.json');dump('mechanical/INPUT_CAP_MOUNT_DESIGN.json',m)
 subprocess.run([KPY,'-B','-X','utf8','tools/cap_terminal_native.py','extract'],cwd=A,check=True)
elif phase=='drc':
 commands=[]
 for fmt,path in [('json','results/CAP_TERMINAL_DRC_NATIVE_V20.json'),('report','results/CAP_TERMINAL_DRC_V20.rpt')]:
  cmd=[str(CLI),'pcb','drc','--format',fmt,'--severity-all','--exit-code-violations','-o',str(A/path),str(A/'ecad/wp10_c203_terminal.kicad_pcb')]
  q=subprocess.run(cmd,cwd=A,capture_output=True,text=True,encoding='utf-8');commands.append(dict(command=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr));assert q.returncode in [0,5],q.stderr
 drc=read('results/CAP_TERMINAL_DRC_NATIVE_V20.json')
 dump('results/CAP_PTH_DRC_EXECUTION_V20.json',dict(native_DRC_executed=True,commands=commands,inputs={p:sha(p) for p in ['ecad/wp10_c203_terminal.kicad_pcb','ecad/wp10_c203_terminal.kicad_pro','results/CAP_TERMINAL_DRC_NATIVE_V20.json','results/CAP_TERMINAL_DRC_V20.rpt','tools/cap_pth_native_v20.py']},violations=len(drc['violations']),whole_design_complete=False))
 print(json.dumps(dict(violations=len(drc['violations']),types=dict(collections.Counter(v['type'] for v in drc['violations'])))))
else:raise ValueError(phase)
