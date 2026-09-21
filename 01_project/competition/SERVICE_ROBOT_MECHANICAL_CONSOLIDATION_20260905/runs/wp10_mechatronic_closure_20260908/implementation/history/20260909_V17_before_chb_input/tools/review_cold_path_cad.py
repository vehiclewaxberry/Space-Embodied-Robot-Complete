from pathlib import Path
import sys,json,subprocess,hashlib,argparse
A=Path(__file__).resolve().parents[1];cad=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['core','leaves','assemblies','snapshots'],required=True);args=ap.parse_args();out=[]
def run(tag,argv):
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(cad/argv[0]),*argv[1:]],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    for suffix,s in [('stdout',q.stdout),('stderr',q.stderr)]:(A/'logs'/f'cold_cad_{tag}.{suffix}.log').write_text(s,encoding='utf-8')
    out.append(dict(tag=tag,argv=argv,returncode=q.returncode));assert q.returncode==0,(tag,q.stderr[-2500:]);print(tag,'OK',flush=True)
if args.phase=='core':run('core_gen',['gen','mechanical/thermal_core.step.py','--write'])
elif args.phase in ['leaves','assemblies']:
    stems=['bottom_radiator','lower_deck_bottom_mount','cold_finger_tim','chb_bottom_tim','fixed_heat_wall_neg','fixed_heat_wall_pos'] if args.phase=='leaves' else ['fixed_heat_installation','bottom_mount_assembly','fixed_heat_bay','thermal_core']
    for stem in stems:
        run(stem+'_refs',['inspect','refs',f'mechanical/{stem}.step','--facts','--planes','--positioning'])
        run(stem+'_validate',['inspect','validate',f'mechanical/{stem}.step']+(['--skip-self-intersection'] if args.phase=='assemblies' else []))
else:
    for stem,views in [('thermal_core',['iso','front','top','bottom']),('fixed_heat_bay',['iso'])]:
        job=dict(input=f'mechanical/{stem}.step.py',mode='view',outputs=[dict(path=f'review/{stem}_cold_path_{v}.png',camera=v) for v in views],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
        path=A/'review'/f'{stem}_cold_path_snapshot.json';path.write_text(json.dumps(job),encoding='utf-8');run(stem+'_snapshot',['snapshot','--job',str(path)])
(A/'results'/f'COLD_CAD_{args.phase.upper()}.json').write_text(json.dumps(dict(commands=out,generic_assembly_self_intersection_skipped=args.phase=='assemblies',actual_pairwise_evidence='COLD_PATH_GEOMETRY.json; BOTTOM_MOUNT_GEOMETRY.json; FIXED_HEAT_{STATE}_INTERFACES.json'),indent=2),encoding='utf-8')
