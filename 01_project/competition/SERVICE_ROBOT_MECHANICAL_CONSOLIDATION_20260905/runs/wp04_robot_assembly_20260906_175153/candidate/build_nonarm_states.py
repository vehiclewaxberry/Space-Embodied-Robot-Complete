"""Serial final nonarm generators and CAD validity inspection."""
from pathlib import Path
import subprocess,sys,json
HERE=Path(__file__).resolve().parent
GEN='F:/codex_skill/AgentSkills/codex-skills/cad/scripts/gen'
INSPECT='F:/codex_skill/AgentSkills/codex-skills/cad/scripts/inspect'
for state in ['parking','released','service']:
    name='servicer_structure_'+state+'.step.py'
    for cmd in [[sys.executable,GEN,name,'--write','--mesh-tolerance','0.3','--mesh-angular-tolerance','0.3','--json'],[sys.executable,INSPECT,'validate',name]]:
        print(json.dumps(dict(stage='START',state=state,command=cmd)),flush=True)
        subprocess.run(cmd,cwd=HERE,check=True)
    print(json.dumps(dict(stage='FINAL_NONARM_STEP_INSPECTED',state=state)),flush=True)
