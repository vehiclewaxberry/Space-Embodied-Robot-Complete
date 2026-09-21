"""Serial native operations, to be called only under native_delta_guard."""
from pathlib import Path
import subprocess,sys,json,hashlib,collections
A=Path(__file__).resolve().parents[1]
ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').is_file())
KPY='G:/Windows_program_file/Kicad/bin/python.exe'
CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def native(phase):subprocess.run([KPY,'-B','-X','utf8','tools/cap_terminal_native.py',phase],cwd=A,check=True)
phase=sys.argv[1]
if phase=='normalize_extract':
 native('finalize')
 d=read('power/CAP_TERMINAL_DEFINITION.json');stack=read('results/CAP_TERMINAL_STACKUP.json')
 assert stack['native_board_sha256']==sha(d['board']) and stack['layers_mm']==d['native_stackup_mm']
 d['finished_copper_thickness_native_bound']=True
 d['thickness_scope']='Native readback of1.6mm finished stackup: F.Mask.01/F.Cu.07/core1.43/B.Cu.07/B.Mask.02. Material and fabrication tolerance remain unqualified.'
 dump('power/CAP_TERMINAL_DEFINITION.json',d)
 mount=read('mechanical/INPUT_CAP_MOUNT_DESIGN.json');mount['source_files']['power/CAP_TERMINAL_DEFINITION.json']=sha('power/CAP_TERMINAL_DEFINITION.json');dump('mechanical/INPUT_CAP_MOUNT_DESIGN.json',mount)
 native('extract')
elif phase=='drc':
 commands=[]
 for fmt,target in [('json','results/CAP_TERMINAL_DRC_NATIVE_V19.json'),('report','results/CAP_TERMINAL_DRC_V19.rpt')]:
  command=[str(CLI),'pcb','drc','--format',fmt,'--severity-all','--exit-code-violations','-o',str(A/target),str(A/'ecad/wp10_c203_terminal.kicad_pcb')]
  q=subprocess.run(command,cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
  commands.append(dict(command=command,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
  assert q.returncode in [0,5],commands[-1]
 drc=read('results/CAP_TERMINAL_DRC_NATIVE_V19.json')
 dump('results/C203_WIRE_PTH_DRC_EXECUTION_V19.json',dict(native_DRC_executed=True,commands=commands,inputs={p:sha(p) for p in ['ecad/wp10_c203_terminal.kicad_pcb','results/CAP_TERMINAL_DRC_NATIVE_V19.json','results/CAP_TERMINAL_DRC_V19.rpt','tools/c203_wire_pth_native_v19.py']},violations=len(drc['violations']),whole_PCB_qualified=False))
 print(json.dumps(dict(violations=len(drc['violations']),types=dict(collections.Counter(v['type'] for v in drc['violations'])))))
else:raise ValueError(phase)
