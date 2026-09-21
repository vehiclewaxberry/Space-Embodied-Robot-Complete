from pathlib import Path
import json,subprocess
A=Path(__file__).resolve().parents[1];R=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists());commands=[]
for cmd in [
 ['G:/Windows_program_file/Kicad/bin/python.exe','-B','-X','utf8','tools/import_main_input_signals_v26.py'],
 [str(R/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'),'pcb','drc','--format','json','--severity-all','-o','results/MAIN_INPUT_ROUTED_DRC_V26.json','ecad/wp10_main_input_v26_routed.kicad_pcb']]:
 q=subprocess.run(cmd,cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace');commands.append(dict(command=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr));(A/'results/MAIN_INPUT_SIGNAL_IMPORT_COMMANDS_V26.json').write_text(json.dumps(commands,indent=2),encoding='utf-8');assert q.returncode==0,q.stderr
print('Signal-only routing merged; inspect DRC and fixed-copper invariants.')
