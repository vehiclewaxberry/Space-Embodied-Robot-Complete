"""Serial bounded generation, inspection and snapshots for explicit entries."""
from pathlib import Path
import json,subprocess,sys,argparse
A=Path(__file__).resolve().parents[1];cad=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['gen','inspect','assembly','snapshots'],required=True);p.add_argument('--only',nargs='+');a=p.parse_args()
stems=['trunk_'+q.lower() for q in ['LOW_BASE','HIGH_BASE','CAP','LINER_LOW','LINER_HIGH','SCREW_12','SCREW_14','SCREW_20','DECK','DRIVE_ADAPTER','COMPUTE_ADAPTER']]
if a.only:
    assert set(a.only)<=set(stems);stems=a.only
out=[]
def run(tag,cmd):
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(cad/cmd[0]),*cmd[1:]],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    for k,t in [('stdout',q.stdout),('stderr',q.stderr)]:(A/f'logs/trunk_cad_{tag}.{k}.log').write_text(t,encoding='utf-8')
    out.append(dict(tag=tag,cmd=cmd,returncode=q.returncode));print(tag,q.returncode,flush=True);assert q.returncode==0,q.stderr[-2000:]
if a.phase=='gen':
    for stem in stems:run(stem+'_gen',['gen',f'mechanical/{stem}.step.py','--write'])
elif a.phase in ['inspect','assembly']:
    for stem in stems if a.phase=='inspect' else ['trunk_support_integration']:
        if a.phase=='assembly':run(stem+'_gen',['gen',f'mechanical/{stem}.step.py','--write'])
        run(stem+'_refs',['inspect','refs',f'mechanical/{stem}.step','--facts','--planes','--positioning'])
        run(stem+'_validate',['inspect','validate',f'mechanical/{stem}.step']+(['--skip-self-intersection'] if a.phase=='assembly' else []))
else:
    for stem in ['trunk_support_integration',*stems]:
        vs=['iso','top'] if stem=='trunk_support_integration' else ['top'] if stem.endswith('deck') or stem.endswith('adapter') else ['iso']
        job=dict(input=f'mechanical/{stem}.step.py',mode='view',outputs=[dict(path=f'review/{stem}_{v}.png',camera=v) for v in vs],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
        path=A/f'review/{stem}_snapshot.json';path.write_text(json.dumps(job),encoding='utf-8');run(stem+'_snapshot',['snapshot','--job',str(path)])
(A/f'results/TRUNK_CAD_{a.phase.upper()}.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
