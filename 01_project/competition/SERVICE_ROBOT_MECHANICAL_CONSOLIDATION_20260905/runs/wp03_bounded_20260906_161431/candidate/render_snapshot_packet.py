from pathlib import Path
import sys,subprocess,json
HERE=Path(__file__).resolve().parent
for name in ['r01_local','r01_context','r01_legacy','servicer_structure_parking','servicer_structure_released','servicer_structure_service']:
    print(json.dumps(dict(snapshot_start=name)),flush=True)
    subprocess.run([sys.executable,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/snapshot','--job',name+'_snapshot.json','--json'],cwd=HERE,check=True)
