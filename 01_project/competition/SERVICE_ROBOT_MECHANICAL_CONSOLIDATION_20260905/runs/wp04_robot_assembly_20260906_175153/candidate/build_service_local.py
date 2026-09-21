from pathlib import Path
import subprocess,sys
H=Path(__file__).resolve().parent
for target in ['servicer_structure_service.step.py','r07_local.step.py']:
    subprocess.run([sys.executable,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/gen',target,'--write','--mesh-tolerance','0.3','--mesh-angular-tolerance','0.3','--json'],cwd=H,check=True)
