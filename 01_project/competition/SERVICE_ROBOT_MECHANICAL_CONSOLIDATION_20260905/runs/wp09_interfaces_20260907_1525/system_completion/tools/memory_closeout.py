"""Summarize actual admission, guard samples and task-owned process exit after CAD."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
import psutil
C=Path(__file__).resolve().parents[1]
jobs=[]
for p in sorted((C/'logs').glob('native_delta_*.run.json')):
    r=json.loads(p.read_text(encoding='utf-8-sig')); samples=r.get('samples',[])
    jobs.append({'file':str(p.relative_to(C)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
      'status':r.get('status'),'available_start_MiB':r.get('available_start_mib'),
      'peak_sampled_combined_MiB':max((s.get('combined_rss_mib',s.get('child_tree_rss_mib',0)) for s in samples),default=None),
      'minimum_sampled_available_MiB':min((s['available_mib'] for s in samples),default=None),
      'owned_SW_stopped_by_guard':r.get('owned_sw_stopped_by_guard',False)})
owners=[]
for p in sorted((C/'results').glob('NATIVE_DELTA_OWNER_*.json')):
    r=json.loads(p.read_text(encoding='utf-8-sig')); active=False
    if 'pid' in r:
        try:
            q=psutil.Process(r['pid'])
            active=q.name().lower()=='sldworks.exe' and abs(q.create_time()-r['create_time'])<.01
        except psutil.NoSuchProcess:pass
    owners.append({'receipt':p.name,'pid':r.get('pid'),'same_owned_process_alive':active})
v=psutil.virtual_memory()
result={'status':'PASS_OWNED_CAD_PROCESSES_EXITED' if not any(r['same_owned_process_alive'] for r in owners) else 'OWNED_CAD_STILL_ACTIVE',
 'utc':datetime.now(timezone.utc).isoformat(),'available_after_MiB':v.available/2**20,'total_MiB':v.total/2**20,
 'processes_killed_by_this_readonly_tool':0,'startup_floor_MiB':2048,'runtime_global_available_floor_MiB':512,
 'combined_RSS_monitor_MiB':1400,'monitor_sampling_seconds':.25,
 'implementation_scope':'Windows Job Object hard allocation cap covers child Python tree; SW plus child combined RSS is sampled. This is not a guarantee against every resource or software failure.',
 'unknown_or_user_processes_closed':0,'owners':owners,'guarded_jobs':jobs,
 'previous_portable_cleanup_evidence':'results/PORTABLE_OWNED_STOP.json'}
(C/'results/MEMORY_CLOSEOUT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['owners','guarded_jobs']},ensure_ascii=False))
