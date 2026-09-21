"""Serial board creation, native DRC and copper/fab SVG exports."""
from pathlib import Path
import json,subprocess,sys
A=Path(__file__).resolve().parents[1];ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists())
CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe';commands=[]
args=[['G:/Windows_program_file/Kicad/bin/python.exe','-B','-X','utf8','tools/build_main_board_native_v25.py'],
 [str(CLI),'pcb','drc','--format','json','--severity-all','-o','results/MAIN_INPUT_BOARD_DRC_V25.json','ecad/wp10_main_input.kicad_pcb'],
 [str(CLI),'pcb','export','svg','--layers','F.Cu,B.Cu,F.Fab,F.SilkS,Edge.Cuts,Dwgs.User','--mode-single','--page-size-mode','2','-o','review/MAIN_INPUT_BOARD_V25.svg','ecad/wp10_main_input.kicad_pcb']]
for cmd in args:
 q=subprocess.run(cmd,cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace');commands.append(dict(args=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
 (A/'results/MAIN_INPUT_BOARD_COMMANDS_V25.json').write_text(json.dumps(commands,indent=2),encoding='utf-8')
 assert q.returncode==0,q.stdout+q.stderr
print(json.dumps(dict(native_commands=len(commands),executed=True,DRC_clean_not_asserted=True)))
