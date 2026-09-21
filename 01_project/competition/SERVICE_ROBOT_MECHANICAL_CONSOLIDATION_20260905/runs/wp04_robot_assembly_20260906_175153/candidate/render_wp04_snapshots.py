from pathlib import Path
import sys,subprocess,json
H=Path(__file__).resolve().parent
for name in ['r07_local','servicer_structure_parking','servicer_structure_released','servicer_structure_service']:
    cameras=['iso','top',{'direction':[-1,1,-.8]}] if name=='r07_local' else ['iso']
    d=dict(input=name+'.step.py',mode='view',outputs=[dict(path=str(H/'results'/f'{name}_view_{i}.png'),camera=c) for i,c in enumerate(cameras)],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
    job=H/(name+'_snapshot.json');job.write_text(json.dumps(d,indent=2),encoding='utf-8')
    subprocess.run([sys.executable,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/snapshot','--job',str(job),'--json'],cwd=H,check=True)
