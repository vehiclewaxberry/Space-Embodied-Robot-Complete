"""Serial CAD CLI checks and actual-CAD snapshot generation. Never control hardware."""
from pathlib import Path
import subprocess,json,sys,os,time,contextlib,gc,hashlib
HERE=Path(__file__).resolve().parent
CAD=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
TARGETS=['body_equipment_cutaway','wing_module','retention_module','body_exploded','servicer_service','servicer_parking','servicer_released','ground_ait']

def run(args,out):
    t=time.monotonic();p=subprocess.run([sys.executable,*map(str,args)],cwd=HERE,env={**os.environ,'PYTHONUTF8':'1'},capture_output=True,text=True,encoding='utf-8',errors='replace')
    (HERE/'results'/out).write_text(p.stdout,encoding='utf-8')
    (HERE/'results'/(out+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    print(out,'exit',p.returncode,'seconds',round(time.monotonic()-t,1),flush=True)
    return {'output':out,'exit_code':p.returncode,'elapsed_s':time.monotonic()-t}

def main(mode):
    records=[]
    receipt_paths=[HERE/f'results/{n}_instances.json' for n in ['parking','released','service','parking_ground']]
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in receipt_paths}
    if mode=='inspect':
        for p in [CAD,CAD/'packages',CAD/'packages/cadgen/src',CAD/'inspect']:
            sys.path.insert(0,str(p))
        import cadgen
        from inspect_refs.cli import main as inspect_main
        def inspect_run(args,out):
            t=time.monotonic()
            with (HERE/'results'/out).open('w',encoding='utf-8') as stdout, (HERE/'results'/(out+'.stderr.txt')).open('w',encoding='utf-8') as stderr, contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
                rc=inspect_main(args)
            gc.collect()
            print(out,'exit',rc,'seconds',round(time.monotonic()-t,1),flush=True)
            return {'output':out,'exit_code':rc,'elapsed_s':time.monotonic()-t,'execution':'OFFICIAL_INSPECT_CLI_MAIN_IN_SERIAL_PROCESS_SHARED_PINNED_SOURCE_CACHE'}
    for name in TARGETS:
        entry=name+'.step.py'
        if mode=='inspect':
            records.append(inspect_run(['refs',entry,'--facts','--planes','--positioning'],name+'_refs.json'))
            if name=='servicer_service':
                records.append(inspect_run(['validate',entry,'--skip-self-intersection'],name+'_validate.json'))
            if name=='ground_ait':
                package=json.loads((HERE/f'__cadgen__/models/{entry}/assembly.json').read_text(encoding='utf-8'))
                matches=[]
                def walk(x):
                    if isinstance(x,dict):
                        if x.get('name')=='GSE__PHYSICAL_GEOMETRY' and str(x.get('id','')).startswith('o'):matches.append(x['id'])
                        for v in x.values():walk(v)
                    elif isinstance(x,list):
                        for v in x:walk(v)
                walk(package)
                if not matches:raise ValueError('Cannot resolve GSE product layer')
                records.append(inspect_run(['validate',entry,'--refs',','.join(sorted(set(matches))),'--skip-self-intersection'],'GSE_EXTRA_GEOMETRY_VALIDATION.json'))
        elif mode=='snapshot':
            views=[('iso','iso')]
            if name=='servicer_service':views += [('opposite',{'direction':[-1,1,-.8]}),('top','top')]
            if name=='body_equipment_cutaway':views += [('opposite',{'direction':[-1,1,-.8]})]
            if name=='servicer_parking':views += [('front','front')]
            job={'input':entry,'mode':'view','outputs':[{'path':str(HERE/'snapshots'/f'{name}_{suffix}.png'),'camera':camera} for suffix,camera in views], 'render':{'viewLabels':True,'padding':.16,'sizeProfile':'assembly-large'}}
            path=HERE/'snapshots'/f'{name}_job.json';path.write_text(json.dumps(job,indent=2),encoding='utf-8')
            records.append(run([CAD/'snapshot','--job',path,'--json'],name+'_snapshot.json'))
        else:raise ValueError(mode)
    if mode=='inspect':
        (HERE/'results/VALIDATION_COVERAGE.json').write_text(json.dumps({'whole_service_cli':'servicer_service_validate.json','non_arm_three_states':'GEOMETRY_CHECK.json','extra_gse':'GSE_EXTRA_GEOMETRY_VALIDATION.json','other_primary_variants':'Rigid placement / subset / illustrative explosion of the same source parts. Do not repeat identical source topology checks as new evidence. Imported arm source defects remain unresolved in every variant.','self_intersection':'NOT_CHECKED','full_continuous_collision':'NOT_CHECKED'},indent=2),encoding='utf-8')
        (HERE/'results/INSPECTION_RECEIPT_STABILITY.json').write_text(json.dumps([{'receipt':p.name,'before_sha256':before[p.name],'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'identical':before[p.name]==hashlib.sha256(p.read_bytes()).hexdigest()} for p in receipt_paths],indent=2),encoding='utf-8')
    (HERE/'results'/f'CAD_{mode.upper()}_RUNS.json').write_text(json.dumps(records,indent=2),encoding='utf-8')

if __name__=='__main__':main(sys.argv[1])
