from pathlib import Path
import subprocess,sys,json
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';cli=Path('F:/codex_skill/AgentSkills/agents-skills/cad/scripts');t='coupled_closure/main_input_lugs_v30.step.py';phase=sys.argv[1]
job=dict(input=t,mode='view',outputs=[dict(path=str(C/'LUG_ISO_V30.png'),camera='iso'),dict(path=str(C/'LUG_OPPOSITE_V30.png'),camera=dict(direction=[-1,1,-.8])),dict(path=str(C/'LUG_TOP_V30.png'),camera='top'),dict(path=str(C/'LUG_FRONT_V30.png'),camera='front')],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
if phase=='snapshot':(C/'LUG_SNAPSHOT_JOB_V30.json').write_text(json.dumps(job))
tasks={'generate':[('LUG_GENERATE_V30.json',[sys.executable,'-B','-X','utf8',str(cli/'gen'),t,'--write','--json']),('LUG_REFS_V30.json',[sys.executable,'-B','-X','utf8',str(cli/'inspect'),'refs',t,'--facts','--planes','--positioning'])], 'validate':[('LUG_TOPOLOGY_VALIDATION_V30.json',[sys.executable,'-B','-X','utf8',str(cli/'inspect'),'validate',t,'--skip-self-intersection']),('LUG_PROJECT_SELF_INTERSECTION_V30.json',[sys.executable,'-B','-X','utf8',str(cli/'inspect'),'validate',t,'--refs','o1.17,o1.18,o1.19,o1.20'])], 'snapshot':[('LUG_SNAPSHOT_RESULT_V30.json',[sys.executable,'-B','-X','utf8',str(cli/'snapshot'),'--job',str(C/'LUG_SNAPSHOT_JOB_V30.json'),'--json'])]}
records=[]
for name,cmd in tasks[phase]:
 q=subprocess.run(cmd,cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace');records.append(dict(command=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr));(C/f'LUG_CAD_{phase}_COMMANDS_V30.json').write_text(json.dumps(records,indent=2));assert q.returncode==0,q.stderr;(C/name).write_text(q.stdout)
print(phase,'complete')
