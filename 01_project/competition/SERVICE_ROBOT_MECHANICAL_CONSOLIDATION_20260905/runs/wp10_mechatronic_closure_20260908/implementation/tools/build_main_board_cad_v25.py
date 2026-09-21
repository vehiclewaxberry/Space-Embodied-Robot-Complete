from pathlib import Path
import json,subprocess,sys
A=Path(__file__).resolve().parents[1];CAD=Path('F:/codex_skill/AgentSkills/agents-skills/cad');target='mechanical/main_input_board_v25.step.py';commands=[]
for args in [
 [str(CAD/'scripts/gen'),target,'--write','--json'],
 [str(CAD/'scripts/inspect'),'refs',target,'--facts','--planes','--positioning'],
 [str(CAD/'scripts/inspect'),'validate',target],
 [str(CAD/'scripts/snapshot'),'--input',target,'--output','review/MAIN_INPUT_PARTIAL_CAD_V25.png','--json']]:
 q=subprocess.run([sys.executable,'-B','-X','utf8',*args],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
 commands.append(dict(args=args,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
 (A/'results/MAIN_INPUT_BOARD_CAD_COMMANDS_V25.json').write_text(json.dumps(commands,indent=2),encoding='utf-8')
 assert q.returncode==0,q.stdout+q.stderr
print(json.dumps(dict(native_commands=len(commands),passed=True,partial_mechanical_model=True)))
