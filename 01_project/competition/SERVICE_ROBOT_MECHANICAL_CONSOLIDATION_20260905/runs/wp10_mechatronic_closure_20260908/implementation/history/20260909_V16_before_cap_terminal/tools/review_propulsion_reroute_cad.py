"""Explicit serial CAD inspection and snapshot packet for this source revision."""
from pathlib import Path
import json,subprocess,sys,argparse,hashlib
A=Path(__file__).resolve().parents[1];cad=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['routes','supports','assembly','snapshots'],required=True);args=ap.parse_args();out=[]
def run(tag,argv):
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(cad/argv[0]),*argv[1:]],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    for ext,t in [('stdout',q.stdout),('stderr',q.stderr)]:(A/'logs'/f'prop_cad_{tag}.{ext}.log').write_text(t,encoding='utf-8')
    out.append(dict(tag=tag,argv=argv,returncode=q.returncode));print(tag,q.returncode,flush=True);assert q.returncode==0,q.stderr[-2400:]
groups={'routes':['battery_prop_power','battery_prop_data'],'supports':['battery_dual_base','battery_dual_lid','battery_dual_post','battery_dual_rod','battery_route_deck'],'assembly':['battery_route_integration']}
if args.phase!='snapshots':
    for stem in groups[args.phase]:
        run(stem+'_refs',['inspect','refs',f'mechanical/{stem}.step','--facts','--planes','--positioning'])
        run(stem+'_validate',['inspect','validate',f'mechanical/{stem}.step']+(['--skip-self-intersection'] if args.phase=='assembly' else []))
else:
    for stem,views in [('battery_route_integration',['iso','top']),('battery_prop_power',['iso']),('battery_prop_data',['iso']),('battery_dual_base',['iso']),('battery_dual_lid',['iso']),('battery_dual_post',['iso']),('battery_dual_rod',['iso']),('battery_route_deck',['top'])]:
        job=dict(input=f'mechanical/{stem}.step.py',mode='view',outputs=[dict(path=f'review/{stem}_{v}.png',camera=v) for v in views],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
        path=A/'review'/f'{stem}_snapshot.json';path.write_text(json.dumps(job),encoding='utf-8');run(stem+'_snapshot',['snapshot','--job',str(path)])
(A/f'results/PROP_CAD_{args.phase.upper()}.json').write_text(json.dumps(dict(source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),commands=out,assembly_generic_self_intersection_skipped=args.phase=='assembly',actual_pairwise_evidence='BATTERY_PROPULSION_ROUTE_SCREEN_{SERVICE,PARKING,RELEASED}.json'),indent=2),encoding='utf-8')
