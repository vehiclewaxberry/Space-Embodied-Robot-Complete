"""Serial source-target CAD checks and mandatory visual review artifacts."""
from pathlib import Path
import sys,json,subprocess,hashlib,argparse
A=Path(__file__).resolve().parents[1];cad=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['leaves','assembly','snapshots','route','passage','generate_passage'],required=True);args=ap.parse_args();out=[]
def run(tag,argv):
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(cad/argv[0]),*argv[1:]],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    for suffix,s in [('stdout',q.stdout),('stderr',q.stderr)]:(A/'logs'/f'battery_cad_{tag}.{suffix}.log').write_text(s,encoding='utf-8')
    out.append(dict(tag=tag,argv=argv,returncode=q.returncode));assert q.returncode==0,(tag,q.stderr[-2500:]);print(tag,'OK',flush=True)
stems=['upper_deck_battery_layout','wall_navigation_bosses','arm_adapter_battery_layout','battery_max_envelope']
if args.phase=='generate_passage':
    for stem in ['bridge_harness_passage','m3rb_harness_relief']:run(stem+'_gen',['gen',f'mechanical/{stem}.step.py','--write'])
elif args.phase in ['leaves','assembly','route','passage']:
    if args.phase=='assembly':stems=['battery_bay_layout']
    elif args.phase=='route':stems=['battery_internal_route']
    elif args.phase=='passage':stems=['bridge_harness_passage','m3rb_harness_relief']
    for stem in stems:
        run(stem+'_refs',['inspect','refs',f'mechanical/{stem}.step','--facts','--planes','--positioning'])
        run(stem+'_validate',['inspect','validate',f'mechanical/{stem}.step']+(['--skip-self-intersection'] if args.phase=='assembly' else []))
else:
    for stem,views in [('battery_bay_layout',['iso','top']),('upper_deck_battery_layout',['top']),('wall_navigation_bosses',['iso']),('arm_adapter_battery_layout',['top']),('battery_internal_route',['iso']),('bridge_harness_passage',['top']),('m3rb_harness_relief',['top'])]:
        job=dict(input=f'mechanical/{stem}.step.py',mode='view',outputs=[dict(path=f'review/{stem}_{v}.png',camera=v) for v in views],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
        path=A/'review'/f'{stem}_snapshot.json';path.write_text(json.dumps(job),encoding='utf-8');run(stem+'_snapshot',['snapshot','--job',str(path)])
(A/'results'/f'BATTERY_CAD_{args.phase.upper()}.json').write_text(json.dumps(dict(commands=out,source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),generic_assembly_self_intersection_skipped=args.phase=='assembly',actual_pairwise_evidence='BATTERY_RELAYOUT_SEED_SCREEN.json; routing is separately qualified'),indent=2),encoding='utf-8')
