"""Serial explicit CAD entry generation, inspection and rendering."""
from pathlib import Path
import argparse,json,subprocess,sys
A=Path(__file__).resolve().parents[1];cad=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['gen','inspect','assembly','snapshots'],required=True);p.add_argument('--only',nargs='+');a=p.parse_args()
stems=['root_'+q.lower() for q in ['BUSH_LEFT','BUSH_RIGHT','KEEPER','SCREW_8','BRIDGE']]
assemblies=['root_bushing_integration','root_bushing_detail'];out=[]
if a.only:assert set(a.only)<=set(stems+assemblies);stems=a.only
def run(tag,cmd):
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(cad/cmd[0]),*cmd[1:]],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    for k,t in [('stdout',q.stdout),('stderr',q.stderr)]:(A/f'logs/root_cad_{tag}.{k}.log').write_text(t,encoding='utf-8')
    out.append(dict(tag=tag,cmd=cmd,returncode=q.returncode));print(tag,q.returncode,flush=True);assert q.returncode==0,q.stderr[-2500:]
if a.phase=='gen':
    for stem in stems:run(stem+'_gen',['gen',f'mechanical/{stem}.step.py','--write'])
elif a.phase in ['inspect','assembly']:
    for stem in stems if a.phase=='inspect' else assemblies:
        if a.phase=='assembly':run(stem+'_gen',['gen',f'mechanical/{stem}.step.py','--write'])
        run(stem+'_refs',['inspect','refs',f'mechanical/{stem}.step','--facts','--planes','--positioning'])
        run(stem+'_validate',['inspect','validate',f'mechanical/{stem}.step']+(['--skip-self-intersection'] if a.phase=='assembly' else []))
else:
    for stem in [*assemblies,*stems]:
        views=['iso','bottom'] if stem=='root_bushing_detail' else ['bottom'] if stem=='root_bridge' else ['iso']
        job=dict(input=f'mechanical/{stem}.step.py',mode='view',outputs=[dict(path=f'review/{stem}_{v}.png',camera=v) for v in views],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
        path=A/f'review/{stem}_snapshot.json';path.write_text(json.dumps(job),encoding='utf-8');run(stem+'_snapshot',['snapshot','--job',str(path)])
(A/f'results/ROOT_CAD_{a.phase.upper()}.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
