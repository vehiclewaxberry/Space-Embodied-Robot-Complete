"""Serial resource-aware launch; arguments stay lists, no shell quoting."""
from pathlib import Path
import subprocess,sys,psutil,os,time,json
A=Path(__file__).resolve().parents[1];tag=sys.argv[1];mode=sys.argv[2];args=sys.argv[3:]
assert tag.replace('_','').isalnum()
if psutil.virtual_memory().available/2**20<2048:
 subprocess.run([sys.executable,'-B','-X','utf8',str(A/'tools/reclaim_cap_terminal_memory.py'),'CHB18_'+tag],cwd=A,check=True)
samples=[];start=time.monotonic()
while True:
 free=psutil.virtual_memory().available/2**20;samples.append(dict(elapsed_s=time.monotonic()-start,available_mib=free))
 if free>=2176 or time.monotonic()-start>=30:break
 time.sleep(1)
(A/f'results/CHB_INPUT_RESOURCE_WAIT_{tag}.json').write_text(json.dumps(dict(samples=samples,launch_headroom_target_mib=2176,hard_guard_threshold_unchanged_mib=2048),indent=2))
exe='G:/Windows_program_file/Kicad/bin/python.exe' if mode=='kicad' else sys.executable
if mode=='cad':
 os.environ['WP10_FONT_SANITY']='1';os.environ['PYTHONPATH']=str(A/'tools/cad_runtime')
q=subprocess.run([sys.executable,'-B','-X','utf8',str(A/'tools/native_delta_guard.py'),'--timeout','240','native_delta_chb18_'+tag,'--',exe,'-B','-X','utf8',*args],cwd=A)
raise SystemExit(q.returncode)
