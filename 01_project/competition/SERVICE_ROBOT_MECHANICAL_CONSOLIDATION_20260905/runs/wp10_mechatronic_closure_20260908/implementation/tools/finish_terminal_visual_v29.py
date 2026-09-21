"""Record the explicit validation scope and produce review images."""
from pathlib import Path
import subprocess,sys,json
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';cli=Path('F:/codex_skill/AgentSkills/agents-skills/cad/scripts');target='coupled_closure/main_input_terminals_v29.step.py';R=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists());k=str(R/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe')
job=dict(input=target,mode='view',outputs=[dict(path=str(C/'TERMINAL_ISO_V29.png'),camera='iso'),dict(path=str(C/'TERMINAL_OPPOSITE_V29.png'),camera=dict(direction=[-1,1,-.8])),dict(path=str(C/'TERMINAL_TOP_V29.png'),camera='top'),dict(path=str(C/'TERMINAL_FRONT_V29.png'),camera='front')],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
j=C/'TERMINAL_SNAPSHOT_JOB_V29.json';j.write_text(json.dumps(job));records=[]
jobs=[('TERMINAL_VALIDATION_V29.json',[sys.executable,'-B','-X','utf8',str(cli/'inspect'),'validate',target,'--skip-self-intersection']),('TERMINAL_SNAPSHOT_RESULT_V29.json',[sys.executable,'-B','-X','utf8',str(cli/'snapshot'),'--job',str(j),'--json']),('TERMINAL_PCB_SVG_COMMAND_V29.json',[k,'pcb','export','svg','--layers','F.Cu,B.Cu,F.Fab,F.SilkS,Edge.Cuts','--mode-single','--page-size-mode','2','-o','coupled_closure/MAIN_INPUT_BOARD_V29.svg','ecad/wp10_main_input.kicad_pcb'])]
for name,cmd in jobs:
 q=subprocess.run(cmd,cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace');r=dict(command=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr);records.append(r);(C/'TERMINAL_VISUAL_COMMANDS_V29.json').write_text(json.dumps(records,indent=2));assert q.returncode==0,q.stderr
 if name!='TERMINAL_PCB_SVG_COMMAND_V29.json':(C/name).write_text(q.stdout)
print('Validation without expensive self-intersection, four-view snapshot, native PCB SVG complete.')
