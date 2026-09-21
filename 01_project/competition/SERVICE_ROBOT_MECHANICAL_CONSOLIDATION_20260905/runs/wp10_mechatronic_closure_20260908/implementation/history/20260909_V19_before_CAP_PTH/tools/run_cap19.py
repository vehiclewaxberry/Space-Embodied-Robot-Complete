"""Serial V19 jobs; retry only verified terminal memory-guard outcomes."""
from pathlib import Path
import subprocess,sys,psutil,os,time,json
A=Path(__file__).resolve().parents[1];tag=sys.argv[1];args=sys.argv[2:]
assert tag.replace('_','').isalnum()
os.environ['WP10_FONT_SANITY']='1';os.environ['PYTHONPATH']=str(A/'tools/cad_runtime')
attempts=[]
def save():
 (A/f'results/CAP_HARNESS_RESOURCE_{tag}_V19.json').write_text(json.dumps(dict(attempts=attempts,hard_start_mib=2048,hard_floor_mib=512,hard_child_mib=1400),indent=2))
for attempt in range(1,4):
 name=f'native_delta_cap19_{tag}_a{attempt}'
 assert not (A/f'logs/{name}.run.json').exists(), 'Do not overwrite an existing execution receipt'
 sw=[dict(pid=p.pid,created=p.create_time()) for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='sldworks.exe']
 if sw:
  attempts.append(dict(name=name,status='SOLIDWORKS_PRESENT_BEFORE_NATIVE_START',processes=sw,native_child_started=False));save()
  print('SolidWorks is running; native CAD remains stopped, no cleanup/launch retry',flush=True);raise SystemExit(2)
 if psutil.virtual_memory().available/2**20<2304:
  subprocess.run([sys.executable,'-B','-X','utf8','tools/reclaim_cap_terminal_memory.py',f'CAP19_{tag}_a{attempt}'],cwd=A,check=True)
 start=time.monotonic();samples=[]
 while True:
  free=psutil.virtual_memory().available/2**20;samples.append(dict(elapsed_s=time.monotonic()-start,available_mib=free))
  if free>=2304 or time.monotonic()-start>=30:break
  time.sleep(1)
 q=subprocess.run([sys.executable,'-B','-X','utf8','tools/native_delta_guard.py','--timeout','240',name,'--',sys.executable,'-B','-X','utf8',*args],cwd=A)
 receipt=A/f'logs/{name}.run.json'
 if not receipt.exists():
  # The legacy guard asserts the SW exclusion before writing its own receipt.
  # Do not mask its failure with FileNotFoundError or restart an unknown job.
  attempts.append(dict(name=name,status='GUARD_EXIT_WITHOUT_RECEIPT',returncode=q.returncode,headroom_samples=samples,native_status_unverified=True));save()
  raise SystemExit(q.returncode or 2)
 rec=json.loads(receipt.read_text())
 attempts.append(dict(name=name,headroom_samples=samples,status=rec['status'],returncode=q.returncode))
 save()
 if q.returncode==0:raise SystemExit(0)
 if rec['status'] not in ['RESOURCE_BLOCKED_BEFORE_START','AVAILABLE_MEMORY_GUARD']:raise SystemExit(q.returncode)
 print('Verified terminal memory-guard outcome; reclaim before next serial attempt',flush=True)
raise SystemExit(2)
