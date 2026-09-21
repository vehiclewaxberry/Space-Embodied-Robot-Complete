"""Serial four-source small batches; resume only missing source results."""
from pathlib import Path
import subprocess,sys,json,psutil
M=Path(__file__).resolve().parents[1];results=[]
for start in range(14,237,4):
    end=min(start+4,237);name=f'native_delta_inertia_v2batch{start:03d}'
    assert not any((M/'results'/f'G{i:03d}.json').exists() for i in range(start,end))
    cmd=[sys.executable,'-B','-X','utf8',str(M/'tools/native_delta_guard.py'),'--timeout','180',name,'--',sys.executable,'-B','-X','utf8',str(M/'tools/read_material_inertia_v2.py'),'--start',str(start),'--end',str(end)]
    p=subprocess.run(cmd,cwd=M,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
    receipt=json.loads((M/'logs'/(name+'.run.json')).read_text())
    summary={k:receipt.get(k) for k in ['name','status','returncode','elapsed_s','available_start_mib','pid']}
    summary['sampled_peak_rss_mib']=max((x['child_tree_rss_mib'] for x in receipt.get('samples',[])),default=None)
    summary['own_worker_no_longer_present_after_guard']=not psutil.pid_exists(receipt.get('pid',-1))
    results.append(summary)
    (M/'results/SERIAL_BATCH_PROGRESS_V2.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)
    if p.returncode!=0:
        print(p.stderr[-2000:],flush=True)
        raise SystemExit(2)
print('ALL_REMAINING_BATCHES_COMPLETED',flush=True)
