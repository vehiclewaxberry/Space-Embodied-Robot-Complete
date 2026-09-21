from pathlib import Path
import sys,json,subprocess,hashlib,argparse
A=Path(__file__).resolve().parents[1];cad=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
stems=['bottom_radiator','lower_deck_bottom_mount','bottom_lower_deck_angle_-1_0','bottom_lower_deck_angle_-1_1','bottom_lower_deck_angle_1_0','bottom_lower_deck_angle_1_1','bottom_mount_screw','bottom_mount_washer','bottom_mount_nut','bottom_mount_assembly','fixed_heat_bay']
ap=argparse.ArgumentParser();ap.add_argument('--resume-index',type=int,default=0);args_cli=ap.parse_args();out=[]
for index,stem in enumerate(stems):
    if index<args_cli.resume_index:
        ref=json.loads((A/'logs'/f'bottom_review_{stem}_refs.stdout.log').read_text());val=json.loads((A/'logs'/f'bottom_review_{stem}_validate.stdout.log').read_text())
        assert ref['ok'] and val['ok'] and val['failureCount']==0
        assert ref['tokens'][0]['stepHash']==hashlib.sha256((A/'mechanical'/f'{stem}.step').read_bytes()).hexdigest()
        out.extend([dict(stem=stem,action=tag,returncode=0,reused_completed_command_from_timeout_batch=True) for tag in ['refs','validate']]);continue
    for tag,args in [('refs',['refs','mechanical/'+stem+'.step','--facts','--planes','--positioning']),('validate',['validate','mechanical/'+stem+'.step']+(['--skip-self-intersection'] if stem in ['bottom_mount_assembly','fixed_heat_bay'] else []))]:
        q=subprocess.run([sys.executable,'-B','-X','utf8',str(cad/'inspect'),*args],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
        for suffix,txt in [('stdout',q.stdout),('stderr',q.stderr)]:(A/'logs'/f'bottom_review_{stem}_{tag}.{suffix}.log').write_text(txt,encoding='utf-8')
        out.append(dict(stem=stem,action=tag,returncode=q.returncode));assert q.returncode==0,(stem,tag,q.stderr)
    print(stem,'validated',flush=True)
for stem,views in [('bottom_mount_assembly',['iso','bottom','top']),('fixed_heat_bay',['iso','bottom'])]:
    job=dict(input='mechanical/'+stem+'.step.py',mode='view',outputs=[dict(path=f'review/{stem}_bottom_revision_{v}.png',camera=v) for v in views],render=dict(viewLabels=True,padding=.12,sizeProfile='diagnostic'))
    path=A/'review'/f'{stem}_bottom_revision_snapshot.json';path.write_text(json.dumps(job),encoding='utf-8')
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(cad/'snapshot'),'--job',str(path)],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    for suffix,txt in [('stdout',q.stdout),('stderr',q.stderr)]:(A/'logs'/f'bottom_review_{stem}_snapshot.{suffix}.log').write_text(txt,encoding='utf-8')
    out.append(dict(stem=stem,action='snapshot',returncode=q.returncode));assert q.returncode==0,(stem,q.stderr)
(A/'results/BOTTOM_CAD_REVIEW_SEQUENCE.json').write_text(json.dumps(dict(commands=out,generic_assembly_self_intersection_skipped=True,independent_pairwise_volume_receipts='BOTTOM_MOUNT_GEOMETRY.json + FIXED_HEAT_{STATE}_INTERFACES.json'),indent=2),encoding='utf-8')
