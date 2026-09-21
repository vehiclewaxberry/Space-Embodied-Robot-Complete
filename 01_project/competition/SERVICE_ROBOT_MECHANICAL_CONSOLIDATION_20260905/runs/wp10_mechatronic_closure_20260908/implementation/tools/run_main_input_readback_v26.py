from pathlib import Path
import json,subprocess
A=Path(__file__).resolve().parents[1];R=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists());commands=[]
for cmd in [
 ['G:/Windows_program_file/Kicad/bin/python.exe','-B','-X','utf8','tools/check_main_input_candidate_v26.py'],
 [str(R/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'),'pcb','export','svg','--layers','F.Cu,B.Cu,F.Fab,F.SilkS,Edge.Cuts,Dwgs.User','--mode-single','--page-size-mode','2','-o','review/MAIN_INPUT_BOARD_V26.svg','ecad/wp10_main_input_v26_candidate.kicad_pcb']]:
 q=subprocess.run(cmd,cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace');commands.append(dict(command=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr));(A/'results/MAIN_INPUT_READBACK_COMMANDS_V26.json').write_text(json.dumps(commands,indent=2),encoding='utf-8');assert q.returncode==0,q.stderr
print('Readback and native SVG completed.')
