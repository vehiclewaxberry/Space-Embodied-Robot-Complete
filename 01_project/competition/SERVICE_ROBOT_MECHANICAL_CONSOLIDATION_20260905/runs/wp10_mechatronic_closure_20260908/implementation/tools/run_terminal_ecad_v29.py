from pathlib import Path
import subprocess,json,sys
A=Path(__file__).resolve().parents[1];R=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists());cli=str(R/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe');receipt=[]
phase=sys.argv[1]
jobs={'sch':[[cli,'sch','export','netlist','--format','kicadxml','-o','ecad/wp10_system_v29.xml','ecad/wp10_system.kicad_sch'],[cli,'sch','erc','--format','json','--severity-all','-o','results/SYSTEM_ERC_V29.json','ecad/wp10_system.kicad_sch']],
 'pcb':[['G:/Windows_program_file/Kicad/bin/python.exe','-B','-X','utf8','tools/build_terminal_board_v29.py'],[cli,'pcb','drc','--format','json','--severity-all','-o','results/MAIN_INPUT_DRC_V29.json','ecad/wp10_main_input_v29_candidate.kicad_pcb'],['G:/Windows_program_file/Kicad/bin/python.exe','-B','-X','utf8','tools/read_terminal_board_v29.py']]}
for cmd in jobs[phase]:
 q=subprocess.run(cmd,cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace');receipt.append(dict(command=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr));(A/f'results/TERMINAL_ECAD_{phase}_COMMANDS_V29.json').write_text(json.dumps(receipt,indent=2));assert q.returncode==0,q.stderr
print(json.dumps(receipt))
