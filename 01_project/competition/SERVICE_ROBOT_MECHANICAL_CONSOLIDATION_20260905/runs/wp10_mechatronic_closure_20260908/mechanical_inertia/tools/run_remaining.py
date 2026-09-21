"""Serial small batches; each monitored child exits before the next launch."""
from pathlib import Path
import subprocess,sys,json,datetime
M=Path(__file__).resolve().parents[1];results=[]
for start in range(4,237,12):
    end=min(start+12,237);name=f'native_delta_inertia_batch{start:03d}'
    cmd=[sys.executable,'-B','-X','utf8',str(M/'tools/native_delta_guard.py'),'--timeout','180',name,'--',sys.executable,'-B','-X','utf8',str(M/'tools/read_material_inertia.py'),'--start',str(start),'--end',str(end)]
    p=subprocess.run(cmd,cwd=M,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
    receipt=json.loads((M/'logs'/(name+'.run.json')).read_text())
    summary={k:receipt.get(k) for k in ['name','status','returncode','elapsed_s','available_start_mib','pid']}
    summary['sampled_peak_rss_mib']=max((x['child_tree_rss_mib'] for x in receipt.get('samples',[])),default=None)
    results.append(summary)
    (M/'results/SERIAL_BATCH_PROGRESS.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)
    if p.returncode!=0:
        print(p.stderr[-2000:],flush=True)
        raise SystemExit(2)
print('ALL_REMAINING_BATCHES_COMPLETED',flush=True)
