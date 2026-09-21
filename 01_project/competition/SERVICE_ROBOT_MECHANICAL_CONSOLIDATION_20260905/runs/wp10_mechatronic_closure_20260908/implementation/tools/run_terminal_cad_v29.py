from pathlib import Path
import subprocess,sys,json
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';cli=Path('F:/codex_skill/AgentSkills/agents-skills/cad/scripts');target='coupled_closure/main_input_terminals_v29.step.py'
phase=sys.argv[1];jobs={'generate':[[sys.executable,'-B','-X','utf8','tools/check_terminal_geometry_v29.py'],[sys.executable,'-B','-X','utf8',str(cli/'gen'),target,'--write','--json']], 'inspect':[[sys.executable,'-B','-X','utf8',str(cli/'inspect'),'refs',target,'--facts','--planes','--positioning'],[sys.executable,'-B','-X','utf8',str(cli/'inspect'),'validate',target]]}
records=[]
for i,cmd in enumerate(jobs[phase]):
 q=subprocess.run(cmd,cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace');records.append(dict(command=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr));(C/f'TERMINAL_CAD_{phase}_COMMANDS_V29.json').write_text(json.dumps(records,indent=2));assert q.returncode==0,q.stderr
 if phase=='inspect':(C/('TERMINAL_REFS_V29.json' if i==0 else 'TERMINAL_VALIDATION_V29.json')).write_text(q.stdout)
print(json.dumps([dict(returncode=r['returncode'],command=r['command']) for r in records]))
