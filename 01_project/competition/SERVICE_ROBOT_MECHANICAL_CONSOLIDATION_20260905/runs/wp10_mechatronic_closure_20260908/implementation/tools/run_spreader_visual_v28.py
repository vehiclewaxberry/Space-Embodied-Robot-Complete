"""Serial native CAD inspection and one four-view snapshot packet."""
from pathlib import Path
import json,subprocess,sys
A=Path(__file__).resolve().parents[1];D=A/'coupled_closure'
cli=Path('F:/codex_skill/AgentSkills/agents-skills/cad/scripts')
target='coupled_closure/spreader_v28.step.py'
for name,args in [('SPREADER_REFS_V28.json',['refs',target,'--facts','--planes','--positioning']),
                  ('SPREADER_VALIDATION_V28.json',['validate',target])]:
    with (D/name).open('x',encoding='utf-8') as f:
        subprocess.run([sys.executable,'-B','-X','utf8',str(cli/'inspect'),*args],cwd=A,stdout=f,check=True)
    data=json.loads((D/name).read_text())
    assert data.get('ok',True),name
job=dict(input=target,mode='view',outputs=[
    dict(path=str(D/'SPREADER_ISO_V28.png'),camera='iso'),
    dict(path=str(D/'SPREADER_OPPOSITE_V28.png'),camera=dict(direction=[-1,1,-.8])),
    dict(path=str(D/'SPREADER_TOP_V28.png'),camera='top'),
    dict(path=str(D/'SPREADER_FRONT_V28.png'),camera='front')],
    render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
jobpath=D/'SPREADER_SNAPSHOT_JOB_V28.json'
with jobpath.open('x',encoding='utf-8') as f:json.dump(job,f)
with (D/'SPREADER_SNAPSHOT_RESULT_V28.json').open('x',encoding='utf-8') as f:
    subprocess.run([sys.executable,'-B','-X','utf8',str(cli/'snapshot'),'--job',str(jobpath),'--json'],cwd=A,stdout=f,check=True)
print('Native refs, validation and four-view snapshot packet completed.')
