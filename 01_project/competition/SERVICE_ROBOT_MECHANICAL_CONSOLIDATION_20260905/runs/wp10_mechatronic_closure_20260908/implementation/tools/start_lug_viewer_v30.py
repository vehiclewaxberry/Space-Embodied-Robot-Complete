"""Launch/reuse the pinned CAD viewer for the coupled design workspace."""
from pathlib import Path
import subprocess,os,sys,json,urllib.request,time
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';assert (C/'main_input_lugs_v30.step').is_file()
env=os.environ.copy();env.update(PYTHONPATH=str(A/'tools/cadgen_v30')+os.pathsep+str(A/'tools/cad_runtime'),CADGEN_DAEMON='0',CADGEN_COMPONENT_WORKERS='1',CADGEN_VALIDATE_WORKERS='1',WP10_FONT_SANITY='1')
cmd=[sys.executable,'-B','-X','utf8','-m','cadgen.viewer','--host','127.0.0.1','--json'];log=A/'logs/VIEWER_LAUNCH_V30.log';err=A/'logs/VIEWER_LAUNCH_V30.stderr.log'
with log.open('w') as o,err.open('w') as e:q=subprocess.Popen(cmd,cwd=C,env=env,stdout=o,stderr=e,creationflags=subprocess.CREATE_NO_WINDOW)
out=None
for _ in range(100):
 for line in log.read_text(encoding='utf-8').splitlines():
  try:
   d=json.loads(line)
   if 'url' in d:out=d
  except ValueError:pass
 if out:break
 time.sleep(.2)
assert out is not None,err.read_text(encoding='utf-8')
out['model_url']=out['url'].rstrip('/')+'/?file=main_input_lugs_v30.step';out['served_root']=str(C);out['command']=cmd
with urllib.request.urlopen(out['url'],timeout=15) as r:out['HTTP_status']=r.status
(C/'VIEWER_V30.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
